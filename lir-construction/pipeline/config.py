"""lir_config.toml: which model plays which role, and the API budget.

A model is either a Hugging Face GGUF reference "org/repo:file.gguf" (runs locally on llama.cpp) or an OpenAI model
name (runs on the API). The API key is read from the .env file named in [api].
"""
from __future__ import annotations

import json
import threading
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
PORTS = {"generator": 8091, "judge": 8093, "judge_fallback": 8095, "verifier": 8097}


@dataclass
class ModelSpec:
    role: str
    name: str
    slots: int
    kv_tokens: int
    think_budget: int
    reasoning_effort: str
    engine_name: str = ""          # "llamacpp" | "vllm" | "openai"; default from the model name
    sampling: dict = field(default_factory=dict)   # vLLM: temperature, top_p, top_k, ... (default: greedy)
    max_tokens: int | None = None  # vLLM: per-call output cap; 0 = none (up to max_model_len); None = the call's own
    max_model_len: int = 65536     # vLLM: longest prompt + answer
    opts: dict = field(default_factory=dict)       # the role's whole table (per-server vLLM settings, see Server)

    @property
    def engine(self) -> str:
        if self.engine_name:
            return self.engine_name
        return "llamacpp" if "/" in self.name and ":" in self.name else "openai"

    @property
    def local(self) -> bool:
        return self.engine in ("llamacpp", "vllm")

    @property
    def repo(self) -> str:
        return self.name.split(":", 1)[0]

    @property
    def file(self) -> str:
        return self.name.split(":", 1)[1]

    @property
    def port(self) -> int:
        return PORTS[self.role]


@dataclass
class Config:
    generator: ModelSpec
    judge: ModelSpec | None
    api: dict
    videos: dict
    path: Path
    judge_fallback: ModelSpec | None = None   # local judge for the items left when the API budget runs out
    verifier: ModelSpec | None = None         # v2: keep/drop, naming, definitions, same-concept and relation calls
    engine: dict = field(default_factory=dict)  # v2: llama_server path, exclusive_gpu
    steps: dict = field(default_factory=dict)   # v2: step name -> role
    think: dict = field(default_factory=dict)   # v2.1: step name -> thinking budget (tokens)

    def roles(self) -> list[ModelSpec]:
        return [s for s in (self.generator, self.judge, self.judge_fallback, self.verifier) if s is not None]

    def api_key(self) -> str:
        env = HERE / self.api.get("env_file", ".env")
        var = self.api.get("key_var", "OPENAI_API_KEY")
        if env.exists():
            for line in env.read_text().splitlines():
                k, _, v = line.partition("=")
                if k.strip() == var:
                    return v.strip().strip('"').strip("'")
        import os
        if os.environ.get(var):
            return os.environ[var]
        api = next((s.name for s in self.roles() if not s.local), "the API model")
        raise SystemExit(f"No API key: set {var} in {env} (needed for {api}).")

    def prices(self, model: str) -> dict:
        p = self.api.get("prices", {}).get(model)
        if not p:
            raise SystemExit(f"No prices for {model} in {self.path} [api.prices.\"{model}\"]; needed to track the budget.")
        return p


def load(path: Path | None = None) -> Config:
    path = path or HERE / "lir_config.toml"
    d = tomllib.loads(path.read_text())

    def spec(role):
        r = d[role]
        return ModelSpec(role, r["model"], int(r.get("slots", 8)), int(r.get("kv_tokens", 32768)),
                         int(r.get("think_budget", 4096)), r.get("reasoning_effort", "medium"),
                         r.get("engine", ""), dict(r.get("sampling", {})),
                         int(r["max_tokens"]) if "max_tokens" in r else None, int(r.get("max_model_len", 65536)),
                         dict(r))
    fb = spec("judge_fallback") if "judge_fallback" in d else None
    if fb is not None and not fb.local:
        raise SystemExit(f"[judge_fallback] in {path} must be a local GGUF model (it runs when the API budget is spent).")
    return Config(spec("generator"), spec("judge") if "judge" in d else None, d.get("api", {}),
                  d.get("videos", {"height": 720}), path, fb, spec("verifier") if "verifier" in d else None,
                  d.get("engine", {}), d.get("steps", {}), d.get("think", {}))


class BudgetExhausted(RuntimeError):
    pass


class Ledger:
    """API spending across all runs (api_spend.json). A call is sent only if its worst-case cost fits the budget."""

    def __init__(self, cfg: Config, course_id: str, path: Path | None = None):
        self.cfg, self.course_id = cfg, course_id
        self.path = path or HERE / "api_spend.json"
        self.budget = float(cfg.api.get("budget_usd", 0))
        self.lock = threading.Lock()
        d = json.loads(self.path.read_text()) if self.path.exists() else {"total_usd": 0.0, "runs": []}
        self.data = d
        self.run = {"date": time.strftime("%Y-%m-%d %H:%M"), "course_id": course_id, "usd": 0.0, "calls": 0,
                    "input_tokens": 0, "cached_tokens": 0, "output_tokens": 0, "by_stage": {}}
        d["runs"].append(self.run)
        self.reserved = 0.0
        self.on_update = None

    @property
    def spent(self) -> float:
        return self.data["total_usd"]

    def cost(self, model: str, inp: int, cached: int, out: int) -> float:
        p = self.cfg.prices(model)
        return ((inp - cached) * p["input"] + cached * p.get("cached_input", p["input"]) + out * p["output"]) / 1e6

    def reserve(self, model: str, est_in: int, est_out: int) -> float:
        est = self.cost(model, est_in, 0, est_out)
        with self.lock:
            if self.data["total_usd"] + self.reserved + est > self.budget:
                raise BudgetExhausted(f"API budget ${self.budget:.2f} reached (spent ${self.data['total_usd']:.3f})")
            self.reserved += est
        return est

    def commit(self, est: float, model: str, stage: str, inp: int, cached: int, out: int):
        usd = self.cost(model, inp, cached, out)
        with self.lock:
            self.reserved -= est
            self.data["total_usd"] = round(self.data["total_usd"] + usd, 6)
            r = self.run
            r["usd"] = round(r["usd"] + usd, 6)
            r["calls"] += 1
            r["input_tokens"] += inp
            r["cached_tokens"] += cached
            r["output_tokens"] += out
            r["by_stage"][stage] = round(r["by_stage"].get(stage, 0) + usd, 6)
            self.data["budget_usd"] = self.budget
            self.path.write_text(json.dumps(self.data, indent=1))
        if self.on_update:
            self.on_update(self)
        return usd

    def release(self, est: float):
        with self.lock:
            self.reserved -= est
