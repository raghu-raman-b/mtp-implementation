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
PORTS = {"generator": 8091, "judge": 8093}


@dataclass
class ModelSpec:
    role: str
    name: str
    slots: int
    kv_tokens: int
    think_budget: int
    reasoning_effort: str

    @property
    def local(self) -> bool:
        return "/" in self.name and ":" in self.name

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
    judge: ModelSpec
    api: dict
    videos: dict
    path: Path

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
        raise SystemExit(f"No API key: set {var} in {env} (needed for {self.judge.name if not self.judge.local else self.generator.name}).")

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
                         int(r.get("think_budget", 4096)), r.get("reasoning_effort", "medium"))
    return Config(spec("generator"), spec("judge"), d.get("api", {}), d.get("videos", {"height": 720}), path)


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
