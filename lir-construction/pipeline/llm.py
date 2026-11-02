"""LLM engine: a local llama.cpp server or the OpenAI API, behind one batching client.

Every stage sends all of its prompts at once. A local server batches them over its parallel slots; the API runs them
concurrently. Outputs are constrained to the stage's JSON schema, cached on disk by input hash, and every call's tokens,
latency and (for the API) cost are logged. API calls are checked against the budget before they are sent.
"""
from __future__ import annotations

import atexit
import copy
import hashlib
import json
import os
import queue
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from pydantic import BaseModel, ValidationError

from .config import PORTS, BudgetExhausted, Config, Ledger, ModelSpec

HERE = Path(__file__).resolve().parent.parent
LLAMA_SERVER = Path.home() / "Documents/llama.cpp/build/bin/llama-server"   # default; [engine] llama_server overrides
TOOLBOX = "llm-engine"


def in_toolbox() -> bool:
    return Path("/run/.toolboxenv").exists()


def toolbox_prefix() -> list[str]:
    """Run inside the llm-engine toolbox unless we already are in it (or there is no toolbox)."""
    if in_toolbox() or not shutil.which("toolbox"):
        return []
    return ["toolbox", "run", "-c", TOOLBOX]


def stop_port(port: int):
    """Stop a llama-server or vLLM server on this port (it may live inside the toolbox, outside our process group)."""
    pattern = f"(llama-server|vllm serve).*--port {port}"
    subprocess.run(["pkill", "-f", pattern], check=False)
    for _ in range(60):
        if subprocess.run(["pgrep", "-f", pattern], capture_output=True).returncode:
            return
        time.sleep(1)


# ---------------------------------------------------------------------------- server
class Server:
    """One model behind an OpenAI-compatible endpoint: a local llama-server, or the OpenAI API."""

    def __init__(self, spec: ModelSpec, cfg: Config, log_dir: Path, ledger: Ledger | None = None):
        self.spec, self.cfg, self.ledger = spec, cfg, ledger
        self.engine = spec.engine
        self.slots, self.ctx_total = spec.slots, spec.kv_tokens
        self.port = spec.port
        self.url = f"http://127.0.0.1:{self.port}" if spec.local else cfg.api.get("base_url", "https://api.openai.com/v1")
        self.log_path = log_dir / f"{spec.role}_server.log"
        self.proc: Optional[subprocess.Popen] = None
        self.startup_s = 0.0
        self.key = cfg.api_key() if not spec.local else None
        self._start_lock = threading.Lock()
        if not spec.local:
            cfg.prices(spec.name)  # fail early if the budget cannot be tracked

    @property
    def think_budget(self) -> int:
        return self.spec.think_budget

    @property
    def model(self) -> str:
        if self.engine == "vllm":
            return f"{self.spec.name} (vLLM)"
        return (f"{self.spec.name} (llama.cpp, KV f16)" if self.spec.local
                else f"{self.spec.name} (OpenAI API, reasoning {self.spec.reasoning_effort})")

    def health(self) -> bool:
        if not self.spec.local:
            return True
        try:
            with urllib.request.urlopen(self.url + "/health", timeout=3) as r:
                return r.status == 200
        except (urllib.error.URLError, OSError):
            return False

    def command(self) -> list[str]:
        if self.engine == "vllm":
            return self.vllm_command()
        from huggingface_hub import hf_hub_download
        binary = self.cfg.engine.get("llama_server") or os.environ.get("LLAMA_SERVER") or str(LLAMA_SERVER)
        return toolbox_prefix() + [
            str(Path(binary).expanduser()), "-m", hf_hub_download(self.spec.repo, self.spec.file), "--no-mmproj", "-ngl", "99",
            # one unified KV pool (f16, not quantized) shared by all slots
            "-c", str(self.ctx_total), "-np", str(self.slots), "--kv-unified",
            "-fa", "on", "--jinja", "--reasoning", "on", "--reasoning-format", "deepseek",
            # a cap on thinking: without it a call can loop in its reasoning until max_tokens
            "--reasoning-budget", str(self.think_budget),
            "--reasoning-budget-message", "I have thought enough; now I give the final answer.",
            "--host", "127.0.0.1", "--port", str(self.port), "--metrics",
        ] + [str(x) for x in self.cfg.engine.get("extra_args", [])]   # e.g. batch sizes for a big GPU

    def vllm_command(self) -> list[str]:
        """vLLM: continuous batching, automatic prefix caching, text only (no vision tower), thinking parsed out."""
        e = self.cfg.engine
        binary = e.get("vllm") or os.environ.get("VLLM") or "vllm"
        return [str(Path(binary).expanduser()), "serve", self.spec.name, "--served-model-name", self.spec.name,
                "--host", "127.0.0.1", "--port", str(self.port),
                "--max-num-seqs", str(self.slots), "--max-model-len", str(self.spec.max_model_len),
                "--gpu-memory-utilization", str(e.get("gpu_memory_utilization", 0.92)),
                # prefix caching on a hybrid model (Qwen 3.5+) keeps a linear-attention state every block: much memory
                "--enable-prefix-caching" if e.get("prefix_caching", True) else "--no-enable-prefix-caching",
                "--reasoning-parser", str(e.get("reasoning_parser", "qwen3")),
                "--limit-mm-per-prompt", json.dumps({"image": 0, "video": 0}), "--seed", "0",
                ] + [str(x) for x in e.get("vllm_args", [])]

    def env(self, cmd: list[str]) -> dict:
        env = dict(os.environ)
        if self.engine == "vllm":  # vLLM compiles kernels with tools from its venv (ninja) and CUDA's nvcc
            env["PATH"] = f"{Path(cmd[0]).parent}:/usr/local/cuda/bin:{env.get('PATH', '')}"
        elif not toolbox_prefix():  # llama-server needs the CUDA 13 runtime; outside the toolbox it is in the main venv
            cu = HERE.parent / "lib/python3.14/site-packages/nvidia/cu13/lib"
            if cu.exists():
                env["LD_LIBRARY_PATH"] = f"{cu}:{env.get('LD_LIBRARY_PATH', '')}"
        return env

    def start(self, log=print):
        if not self.spec.local:
            return
        with self._start_lock:
            self._start(log)

    def ensure_up(self, log=print):
        """Restart a local server that died or was stopped by another run sharing it."""
        if self.spec.local and not self.health():
            log(f"  ! the {self.spec.role} server is down; restarting it")
            self.start(log)

    def _start(self, log=print):
        if self.health():
            log(f"  using the {self.spec.role} server already running on port {self.port}")
            return
        if self.cfg.engine.get("exclusive_gpu", True):  # only one local model fits on a 12 GB card at a time
            for p in PORTS.values():
                if p != self.port:
                    stop_port(p)
        t0 = time.time()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = self.command()
        log(f"  starting {self.spec.role}: {self.spec.name}, {self.slots} slots, {self.ctx_total:,}-token KV pool")
        self.proc = subprocess.Popen(cmd, stdout=open(self.log_path, "a"), stderr=subprocess.STDOUT, env=self.env(cmd),
                                     start_new_session=True)
        atexit.register(self.stop)
        while not self.health():
            if self.proc.poll() is not None:
                tail = self.log_path.read_text(errors="replace")[-2000:]
                raise RuntimeError(f"{self.spec.role} server exited ({self.proc.returncode}); log tail:\n{tail}")
            time.sleep(1)
        self.startup_s = time.time() - t0
        log(f"  server ready in {self.startup_s:.0f}s")

    def stop(self, force: bool = False):
        if not self.spec.local or (self.proc is None and not force):
            return
        import signal
        if self.proc is not None and self.proc.poll() is None:
            try:
                os.killpg(self.proc.pid, signal.SIGTERM)
                self.proc.wait(timeout=30)
            except Exception:
                self.proc.kill()
        stop_port(self.port)
        self.proc = None

    def count_tokens(self, text: str) -> int:
        if not self.spec.local:
            return len(text) // 4
        body = ({"model": self.spec.name, "prompt": text, "add_special_tokens": False} if self.engine == "vllm"
                else {"content": text})
        req = urllib.request.Request(self.url + "/tokenize", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return len(json.load(r)["tokens"])


def api_schema(schema: dict) -> dict:
    """OpenAI strict mode: every object closed with all properties required; drop length keywords it rejects."""
    s = copy.deepcopy(schema)

    def walk(x):
        if isinstance(x, dict):
            for k in ("maxLength", "minLength"):
                x.pop(k, None)
            if x.get("type") == "object" and "properties" in x:
                x["additionalProperties"] = False
                x["required"] = list(x["properties"])
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(s)
    return s


# ---------------------------------------------------------------------------- requests
@dataclass
class Call:
    """One LLM request. `check(parsed, ctx)` returns a list of error strings (empty = pass)."""
    key: str                                   # unique within the stage, e.g. "L03/S2/annotate"
    lecture_id: str
    prompt: str
    schema: type[BaseModel] | dict
    prompt_id: str
    prompt_version: str = "1"
    max_tokens: int = 8192
    check: Optional[Callable[[Any], list[str]]] = None
    required: bool = True
    ctx: dict = field(default_factory=dict)    # anything the caller wants back
    stage: str = ""                            # overrides the batch's stage name (cache file and cost report)
    group: str = ""                            # calls in one group share a prompt start: run in order on one slot


@dataclass
class Outcome:
    call: Call
    ok: bool
    parsed: Any
    content: str
    reasoning: str
    errors: list[str]
    retries: int
    input_tokens: int
    output_tokens: int
    latency_s: float                           # sum over attempts, wall time of each HTTP call
    cached: bool
    input_hash: str

    def origin(self, model: str, engine: str, stage: str) -> dict:
        return {"item": self.call.key, "stage": stage, "model": model, "engine": engine,
                "prompt_id": self.call.prompt_id, "prompt_version": self.call.prompt_version,
                "input_hash": self.input_hash, "thinking": True,
                "validator": {"passed": self.ok, "errors": self.errors}, "retries": self.retries,
                "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
                "latency_s": round(self.latency_s, 2), "cached": self.cached}


def schema_of(s) -> dict:
    return s.model_json_schema() if isinstance(s, type) and issubclass(s, BaseModel) else s


def parse(s, content: str):
    if isinstance(s, type) and issubclass(s, BaseModel):
        return s.model_validate_json(content)
    return json.loads(content)


class LLM:
    """Batching client with disk cache, retries with feedback, and per-call cost logging."""

    def __init__(self, server: Server, cache_dir: Path, workers: int, temperature: float = 0.0, log=print, ui=None,
                 records: list | None = None, slot_offset: int = 0):
        self.server, self.workers, self.temperature, self.log, self.ui = server, workers, temperature, log, ui
        # runs sharing one server each use their own slots (slot_offset .. slot_offset + workers - 1)
        self.slot_offset = slot_offset
        self.cache_dir = cache_dir
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.model = server.model
        self.records: list[dict] = records if records is not None else []  # one per HTTP call (cost report)
        self._lock = threading.Lock()
        self._caches: dict[str, dict] = {}
        # admission control: llama.cpp's slots share one KV pool, so cap the tokens in flight
        # (a run using only some of the slots gets the same share of the pool)
        share = min(1.0, workers / server.slots) if server.slots else 1.0
        self._budget = int(server.ctx_total * 0.85 * share) if server.engine == "llamacpp" else 10 ** 12
        self._in_flight = 0
        self._cv = threading.Condition()
        self._tl = threading.local()           # the server slot the current thread is pinned to (prefix cache)

    # -- disk cache: one JSONL per stage, keyed by input hash
    def _cache(self, stage: str) -> dict:
        if stage not in self._caches:
            path = self.cache_dir / f"{stage}.jsonl"
            d = {}
            if path.exists():
                for line in path.read_text(encoding="utf-8").splitlines():
                    try:
                        r = json.loads(line)
                        d[r["hash"]] = r
                    except json.JSONDecodeError:
                        pass
            self._caches[stage] = d
        return self._caches[stage]

    def _cache_put(self, stage: str, rec: dict):
        with self._lock:
            self._cache(stage)[rec["hash"]] = rec
            with open(self.cache_dir / f"{stage}.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def _hash(self, prompt: str, schema: dict, max_tokens: int) -> str:
        parts = [self.model, prompt, schema, max_tokens, self.temperature]
        spec = self.server.spec
        if spec.sampling or spec.max_tokens is not None:   # only then: older caches keep their keys
            parts.append([spec.sampling, spec.max_tokens])
        blob = json.dumps(parts, sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()[:20]

    # -- one HTTP call
    def _post(self, prompt: str, schema: dict, max_tokens: int, stage: str = "") -> dict:
        if self.server.engine == "openai":
            return self._post_api(prompt, schema, max_tokens, stage)
        body = {
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens, "temperature": self.temperature, "seed": 0,
            "response_format": {"type": "json_schema", "json_schema": {"name": "answer", "schema": schema, "strict": True}},
            "chat_template_kwargs": {"enable_thinking": True},
        }
        if self.server.engine == "vllm":   # vLLM reuses shared prompt starts by itself: no slots, no admission
            spec = self.server.spec
            body["model"] = spec.name
            body.update(spec.sampling)
            if spec.max_tokens == 0:
                body.pop("max_tokens")         # no cap: up to max_model_len
            elif spec.max_tokens:
                body["max_tokens"] = spec.max_tokens
            req = urllib.request.Request(self.server.url + "/v1/chat/completions", data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json"})
            return self._post_admitted(req)
        slot = getattr(self._tl, "slot", None)
        if slot is not None:
            body["id_slot"] = slot
        req = urllib.request.Request(self.server.url + "/v1/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        # rough prompt tokens + the most a call can generate (thinking is capped by the server's budget)
        need = min(len(prompt) // 3 + min(max_tokens, self.server.think_budget + 1500), self._budget)
        with self._cv:
            self._cv.wait_for(lambda: self._in_flight + need <= self._budget)
            self._in_flight += need
        try:
            return self._post_admitted(req)
        finally:
            with self._cv:
                self._in_flight -= need
                self._cv.notify_all()

    def _post_api(self, prompt: str, schema: dict, max_tokens: int, stage: str) -> dict:
        """OpenAI chat completions with a strict JSON schema; cost checked against the budget before sending."""
        spec, ledger = self.server.spec, self.server.ledger
        out_cap = min(max_tokens, spec.think_budget + 2000)
        est = ledger.reserve(spec.name, len(prompt) // 3, out_cap)   # raises BudgetExhausted
        body = {"model": spec.name, "messages": [{"role": "user", "content": prompt}],
                "max_completion_tokens": out_cap, "reasoning_effort": spec.reasoning_effort,
                "response_format": {"type": "json_schema",
                                    "json_schema": {"name": "answer", "schema": api_schema(schema), "strict": True}}}
        req = urllib.request.Request(self.server.url.rstrip("/") + "/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json",
                                              "Authorization": f"Bearer {self.server.key}"})
        t0 = time.time()
        try:
            for attempt in range(20):
                try:
                    with urllib.request.urlopen(req, timeout=600) as r:
                        d = json.load(r)
                    break
                except urllib.error.HTTPError as e:
                    msg = e.read().decode(errors="replace")[:500]
                    if e.code in (429, 500, 502, 503) and attempt < 5:   # rate limit or transient: back off
                        time.sleep(min(60, 4 * 2 ** attempt))
                        continue
                    raise RuntimeError(f"API rejected the request ({e.code}): {msg}")
                except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
                    # network down (dropped Wi-Fi, captive portal): wait up to ~15 min in total before giving up
                    if attempt == 19:
                        raise
                    if attempt in (0, 5, 10, 15):
                        self.log(f"    ! API unreachable ({e}); retrying")
                    time.sleep(min(60, 5 * 2 ** min(attempt, 4)))
        except Exception:
            ledger.release(est)
            raise
        u = d.get("usage", {})
        inp, out = u.get("prompt_tokens", 0), u.get("completion_tokens", 0)
        cached = (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
        usd = ledger.commit(est, spec.name, stage, inp, cached, out)
        msg = d["choices"][0]["message"]
        return {"content": (msg.get("content") or "").strip(), "reasoning": "",
                "input_tokens": inp, "output_tokens": out, "cached_tokens": cached, "usd": round(usd, 6),
                "latency_s": time.time() - t0, "finish": d["choices"][0].get("finish_reason")}

    def _post_admitted(self, req) -> dict:
        t0 = time.time()
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=3600) as r:
                    d = json.load(r)
                break
            except urllib.error.HTTPError as e:
                raise RuntimeError(f"server rejected the request ({e.code}): {e.read().decode(errors='replace')[:500]}")
            except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
                if attempt == 2:
                    raise
                self.log(f"    ! request failed ({e}); retrying")
                time.sleep(5)
                self.server.ensure_up(lambda m: self.log(m))
        msg = d["choices"][0]["message"]
        u = d.get("usage", {})
        return {"content": (msg.get("content") or "").strip(),
                "reasoning": msg.get("reasoning_content") or msg.get("reasoning") or "",
                "input_tokens": u.get("prompt_tokens", 0), "output_tokens": u.get("completion_tokens", 0),
                "latency_s": time.time() - t0, "finish": d["choices"][0].get("finish_reason")}

    def _attempt(self, stage: str, call: Call, prompt: str, schema: dict, max_tokens: int) -> dict:
        h = self._hash(prompt, schema, max_tokens)
        hit = self._cache(stage).get(h)
        if hit:
            return {**hit, "cached": True, "latency_s": 0.0}
        r = self._post(prompt, schema, max_tokens, stage)
        if r["finish"] == "length" and not r["content"] and self.server.spec.max_tokens != 0:
            # thinking used the whole budget; give it more room once
            r2 = self._post(prompt, schema, max_tokens * 2, stage)
            r2["latency_s"] += r["latency_s"]
            r = r2
        rec = {"hash": h, "key": call.key, **r}
        self._cache_put(stage, rec)
        with self._lock:
            self.records.append({"stage": stage, "lecture_id": call.lecture_id, "key": call.key, "model": self.model,
                                 "input_tokens": r["input_tokens"], "output_tokens": r["output_tokens"],
                                 "usd": r.get("usd", 0.0), "latency_s": r["latency_s"], "t_end": time.time()})
        return {**rec, "cached": False}

    def _run_one(self, stage: str, call: Call, max_retries: int) -> Outcome:
        schema = schema_of(call.schema)
        prompt = call.prompt
        errors: list[str] = []
        parsed = None
        tot_in = tot_out = 0
        lat = 0.0
        cached_all = True
        r = {"content": "", "reasoning": "", "hash": ""}
        h0 = self._hash(call.prompt, schema, call.max_tokens)
        for attempt in range(max_retries + 1):
            try:
                r = self._attempt(stage, call, prompt, schema, call.max_tokens)
            except BudgetExhausted as e:  # not sent: the caller decides what an unjudged item means
                return Outcome(call, False, None, "", "", [f"budget: {e}"], attempt, tot_in, tot_out, lat, False, h0)
            tot_in += r["input_tokens"]
            tot_out += r["output_tokens"]
            lat += r["latency_s"]
            cached_all &= r["cached"]
            try:
                parsed = parse(call.schema, r["content"])
                errors = call.check(parsed) if call.check else []
            except (ValidationError, json.JSONDecodeError, ValueError) as e:
                parsed, errors = None, [f"answer is not valid JSON for the schema: {str(e)[:300]}"]
            if not errors:
                return Outcome(call, True, parsed, r["content"], r["reasoning"], [], attempt, tot_in, tot_out, lat,
                               cached_all, h0)
            # retry: same prompt (keeps the cached prefix) plus the failure message at the end
            prompt = (call.prompt + "\n\nYour previous answer was rejected for these reasons:\n- "
                      + "\n- ".join(errors) + "\nWrite a corrected answer.")
        return Outcome(call, False, parsed, r["content"], r["reasoning"], errors, max_retries, tot_in, tot_out, lat,
                       cached_all, h0)

    def run(self, stage: str, calls: list[Call], desc: str, max_retries: int = 2) -> list[Outcome]:
        """Send every call of a stage at once; return outcomes in the same order.

        Calls with the same `group` share a prompt start: they run one after another on one server slot, so the
        slot's prefix cache is reused. Ungrouped calls run independently."""
        if not calls:
            return []
        out: list[Optional[Outcome]] = [None] * len(calls)
        if self.ui:
            self.ui.calls(desc, len(calls))
        retries = 0
        units: dict[str, list[int]] = {}
        for i, c in enumerate(calls):
            units.setdefault(c.group or f"\0{i}", []).append(i)
        # longest work first, so the long tail does not start last
        order = sorted(units.values(), key=lambda u: -sum(len(calls[i].prompt) for i in u))
        slots = self._slot_queue()

        def unit(idx: list[int]):
            with self._pinned(slots, len(idx) > 1):
                return [(i, self._run_one(calls[i].stage or stage, calls[i], max_retries)) for i in idx]

        with ThreadPoolExecutor(self.workers) as ex:
            for f in as_completed([ex.submit(unit, u) for u in order]):
                for i, o in f.result():
                    out[i] = o
                    retries += o.retries
                    if self.ui:
                        self.ui.advance(1, tokens=0 if o.cached else o.output_tokens, retries=retries)
        return out  # type: ignore[return-value]

    def run_jobs(self, stage: str, jobs: list[Callable], desc: str, max_retries: int = 2) -> list[Any]:
        """Run jobs that each make several dependent calls on one shared prompt start (e.g. one window's candidates:
        keep? -> name -> define -> check). A job is `fn(send)`, where `send(call)` returns the call's Outcome; all of a
        job's calls run in order on one server slot. Returns the jobs' results in order."""
        if not jobs:
            return []
        if self.ui:
            self.ui.calls(desc, len(jobs))
        slots = self._slot_queue()
        stats = {"retries": 0}
        lock = threading.Lock()

        def send(call: Call) -> Outcome:
            o = self._run_one(call.stage or stage, call, max_retries)
            if self.ui:
                with lock:
                    stats["retries"] += o.retries
                    self.ui.advance(0, tokens=0 if o.cached else o.output_tokens, retries=stats["retries"])
            return o

        def job(fn):
            with self._pinned(slots, True):
                return fn(send)

        out: list[Any] = [None] * len(jobs)
        with ThreadPoolExecutor(self.workers) as ex:
            futs = {ex.submit(job, fn): k for k, fn in enumerate(jobs)}
            for f in as_completed(futs):
                out[futs[f]] = f.result()
                if self.ui:
                    self.ui.advance(1)
        return out

    # -- slot pinning: one slot per worker thread while it runs a group
    def _slot_queue(self) -> "queue.Queue[int]":
        q: queue.Queue[int] = queue.Queue()
        for k in range(self.workers):
            q.put(self.slot_offset + k)
        return q

    @contextmanager
    def _pinned(self, slots: "queue.Queue[int]", pin: bool):
        slot = slots.get()
        # pin only on a local server whose slots match the workers (an out-of-range id_slot is an error)
        self._tl.slot = slot if pin and self.server.engine == "llamacpp" and self.slot_offset + self.workers <= self.server.slots else None
        try:
            yield
        finally:
            self._tl.slot = None
            slots.put(slot)
