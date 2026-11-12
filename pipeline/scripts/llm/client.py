"""LLM: send prompts to a vLLM or llama.cpp server, one at a time (sequential) or all at once (parallel).

In parallel mode every request is sent at once (up to `concurrency` in flight) and the engine batches them: vLLM by
continuous batching, llama.cpp over its slots. Answers can be constrained to a JSON schema and parsed, checked and
retried, cached on disk by request hash, and every attempt is logged.
"""
from __future__ import annotations

import hashlib
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from .config import LLMConfig
from .progress import Progress
from .server import Server


@dataclass
class Request:
    prompt: str
    key: str = ""                   # your ID for the request (e.g. "lec_5"); shown in results and logs
    system: str = ""                # optional system message
    schema: dict | None = None      # JSON schema: the answer is constrained to it and parsed
    check: Callable[[Any], list[str]] | None = None   # problems with the parsed answer ([] = fine); any -> retry
    feedback: bool = False          # on a retry, show the model its answer and the problems found, and ask again
    # A conversation to continue: messages after the prompt, e.g. [{"role": "assistant", "content": earlier answer},
    # {"role": "user", "content": "That has problems: ..."}]. The server keeps no state, so the whole history is sent.
    followup: list = field(default_factory=list)
    max_tokens: int | None = None   # overrides LLMConfig.max_tokens
    think_budget: int | None = None  # overrides LLMConfig.think_budget (vLLM only; llama.cpp fixes it per server)
    sampling: dict = field(default_factory=dict)   # overrides, e.g. {"temperature": 0}
    meta: dict = field(default_factory=dict)       # anything you want back on the result
    # Tool calling (OpenAI tools API; llama.cpp needs --jinja). Sent only when set, so the request hash of a request
    # without tools is what it always was. A conversation with tool calls goes in followup: {"role": "assistant",
    # "content": ..., "tool_calls": [...]} then {"role": "tool", "tool_call_id": ..., "content": ...} per call.
    tools: list | None = None       # [{"type": "function", "function": {"name", "description", "parameters"}}]
    tool_choice: str | dict | None = None   # "auto", "none", "required", or a named function


@dataclass
class Result:
    key: str
    content: str = ""               # the answer (thinking removed)
    reasoning: str = ""             # the thinking, when the server returns it apart
    tool_calls: list = field(default_factory=list)   # the calls the model asked for, as the server sent them
    parsed: Any = None              # the answer as JSON, when the request had a schema
    ok: bool = False
    errors: list = field(default_factory=list)
    history: list = field(default_factory=list)   # earlier failed attempts: [{"answer", "errors"}]
    finish: str = ""                # "stop", or "length" when max_tokens cut the answer
    input_tokens: int = 0
    output_tokens: int = 0
    latency_s: float = 0.0
    attempts: int = 0
    cached: bool = False
    hash: str = ""
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


FEEDBACK = ("Your answer has these problems:\n{problems}\n\n"
            "Answer again in the same format, fixing these problems and changing nothing else.")


class RequestRejected(RuntimeError):
    """The server refused this request (4xx: too long, bad schema); retrying would not help."""


def _parse_json(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    s = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    for i, ch in enumerate(s):          # the first JSON value in the text
        if ch in "[{":
            try:
                return json.JSONDecoder().raw_decode(s[i:])[0]
            except json.JSONDecodeError:
                continue
    raise ValueError("the answer is not JSON")


class LLM:
    """llm = LLM(cfg); llm.start(); llm.generate("Hi"); llm.generate_many([...]); llm.stop()  (or `with LLM(cfg)`)."""

    def __init__(self, cfg: LLMConfig, log=print):
        self.cfg, self.log = cfg, log
        self.server = Server(cfg, log)
        self._lock = threading.Lock()
        self._start_lock = threading.Lock()
        self._started = False
        self._caches: dict[str, dict] = {}
        self.totals = {"requests": 0, "attempts": 0, "cached": 0, "input_tokens": 0, "output_tokens": 0}
        self.progress = Progress(self)     # a line per finished request, a heartbeat while requests are in flight

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> "LLM":
        """Attach to the server, or start it. Called by `with LLM(cfg)` only when the model name is unknown without a
        server; otherwise the server is started by the first request that is not in the cache, so a re-run answered
        wholly from the cache never loads the model."""
        with self._start_lock:
            if not self._started:
                self.server.start()
                self._started = True
        return self

    def stop(self):
        self.server.stop()
        self._started = False

    def __enter__(self):
        return self if self.server.model_name else self.start()

    def __exit__(self, *exc):
        self.stop()

    @property
    def model(self) -> str:
        return self.server.model_name

    # ------------------------------------------------------------------ public
    def generate(self, request: Request | str, *, cache_file: str | Path | None = None,
                 log_file: str | Path | None = None, **overrides) -> Result:
        """One request. A plain string is a prompt; keyword overrides are Request fields (schema=..., max_tokens=...)."""
        req = request if isinstance(request, Request) else Request(prompt=request, **overrides)
        return self._run(req, self._cache_path(cache_file), self._log_path(log_file), show=True)

    def generate_many(self, requests: list[Request | str], parallel: bool = True, *, progress: bool = True,
                      cache_file: str | Path | None = None, log_file: str | Path | None = None) -> list[Result]:
        """Many requests; results in the same order. parallel=True sends them all at once (the engine batches them),
        parallel=False one after another."""
        reqs = [r if isinstance(r, Request) else Request(prompt=r, key=str(i)) for i, r in enumerate(requests)]
        cache, logf = self._cache_path(cache_file), self._log_path(log_file)
        out: list[Result | None] = [None] * len(reqs)
        if progress:
            self.progress.batch_start(len(reqs))

        def one(i: int):
            out[i] = self._run(reqs[i], cache, logf, show=progress)

        if parallel:
            with ThreadPoolExecutor(max_workers=max(1, self.cfg.concurrency or self.cfg.slots)) as ex:
                list(ex.map(one, range(len(reqs))))
        else:
            for i in range(len(reqs)):
                one(i)
        if progress:
            self.progress.batch_end()
        return out

    def lookup(self, request: Request, cache_file: str | Path | None = None) -> dict | None:
        """The cached first-attempt answer to this request ({"content", "reasoning", ...}), or None. Never calls the
        server: a later stage uses it to rebuild an earlier stage's conversation exactly as the model answered."""
        cache = self._cache_path(cache_file)
        return self._cache(cache).get(self._hash(self._body(request, 0, request.followup))) if cache else None

    def count_tokens(self, text: str) -> int:
        """Tokens in text, counted by the server's own tokenizer."""
        self.start()
        body = ({"model": self.model, "prompt": text, "add_special_tokens": False} if self.cfg.engine == "vllm"
                else {"content": text})
        d = self._post("/tokenize", body, timeout=60)
        return d.get("count", len(d.get("tokens", [])))

    # ------------------------------------------------------------------ internals
    def _cache_path(self, p) -> Path | None:
        p = p if p is not None else self.cfg.cache_file
        return Path(p) if p else None

    def _log_path(self, p) -> Path | None:
        p = p if p is not None else self.cfg.log_file
        return Path(p) if p else None

    def _body(self, req: Request, attempt: int, followup: list | None = None) -> dict:
        c = self.cfg
        messages = ([{"role": "system", "content": req.system}] if req.system else []) + \
                   [{"role": "user", "content": req.prompt}] + (followup or [])
        body = {"model": self.model, "messages": messages, "seed": c.seed + attempt,
                "chat_template_kwargs": {"enable_thinking": c.thinking, **c.chat_template_kwargs},
                **c.sampling(), **req.sampling}
        if c.engine == "llamacpp":     # llama.cpp names it repeat_penalty
            body["repeat_penalty"] = body.pop("repetition_penalty")
        max_tokens = req.max_tokens if req.max_tokens is not None else c.max_tokens
        if max_tokens:
            body["max_tokens"] = max_tokens
        think = req.think_budget if req.think_budget is not None else c.think_budget
        if c.engine == "vllm" and c.thinking and think:
            body["thinking_token_budget"] = think
        if req.schema is not None:
            body["response_format"] = {"type": "json_schema",
                                       "json_schema": {"name": "answer", "schema": req.schema, "strict": True}}
        if req.tools:
            body["tools"] = req.tools
        if req.tool_choice is not None:
            body["tool_choice"] = req.tool_choice
        return body

    def _hash(self, body: dict) -> str:
        ident = {"engine": self.cfg.engine, "model_path": self.cfg.model_path, "body": body}
        if self.cfg.engine == "llamacpp":   # the thinking cap is a server setting there
            ident["think_budget"] = self.cfg.think_budget
        return hashlib.sha256(json.dumps(ident, sort_keys=True).encode()).hexdigest()[:20]

    def _cache(self, path: Path) -> dict:
        key = str(path)
        if key not in self._caches:
            entries = {}
            if path.exists():
                for line in path.read_text().splitlines():
                    if line.strip():
                        rec = json.loads(line)
                        entries[rec["hash"]] = rec
            self._caches[key] = entries
        return self._caches[key]

    def _append(self, path: Path, rec: dict):
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, path.open("a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def _post(self, route: str, body: dict, timeout: int) -> dict:
        req = urllib.request.Request(self.server.url + route, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:
                msg = e.read().decode(errors="replace")[:500]
                if 400 <= e.code < 500:
                    raise RequestRejected(f"server rejected the request ({e.code}): {msg}")
                if attempt == 3:
                    raise RuntimeError(f"server error ({e.code}): {msg}")
            except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
                if attempt == 3:
                    raise
                self.progress.line(f"! request failed ({e}); retrying")
            time.sleep(5 * (attempt + 1))

    def _attempt(self, req: Request, attempt: int, cache: Path | None, logf: Path | None,
                 followup: list | None = None) -> Result:
        body = self._body(req, attempt, followup)
        h = self._hash(body)
        res = Result(key=req.key, hash=h, meta=req.meta, attempts=attempt + 1)
        hit = self._cache(cache).get(h) if cache else None
        if hit:
            res.content, res.reasoning, res.finish = hit["content"], hit["reasoning"], hit["finish"]
            res.input_tokens, res.output_tokens, res.cached = hit["input_tokens"], hit["output_tokens"], True
            res.tool_calls = hit.get("tool_calls") or []
        else:
            self.start()                      # a no-op once started; the first cache miss starts the server
            t0 = time.time()
            try:
                d = self._post("/v1/chat/completions", body, self.cfg.timeout_s)
            except RequestRejected as e:
                res.errors, res.latency_s = [str(e)], time.time() - t0
                self._log_attempt(logf, req, res, attempt)
                return res
            choice, usage = d["choices"][0], d.get("usage") or {}
            msg = choice.get("message") or {}
            res.content = (msg.get("content") or "").strip()
            res.reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""
            res.finish = choice.get("finish_reason") or ""
            res.tool_calls = msg.get("tool_calls") or []
            res.input_tokens, res.output_tokens = usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
            res.latency_s = time.time() - t0
            if cache:
                rec = {"hash": h, "key": req.key, "content": res.content, "reasoning": res.reasoning,
                       "finish": res.finish, "input_tokens": res.input_tokens, "output_tokens": res.output_tokens}
                if res.tool_calls:            # only then, so cache lines of requests without tools are unchanged
                    rec["tool_calls"] = res.tool_calls
                self._cache(cache)[h] = rec
                self._append(cache, rec)
        # parse and check
        if res.finish == "length":
            res.errors.append("the answer was cut off at max_tokens")
        if req.schema is not None:
            try:
                res.parsed = _parse_json(res.content)
            except ValueError as e:
                res.errors.append(str(e))
        else:
            res.parsed = res.content
        if not res.errors and req.check is not None:
            res.errors += list(req.check(res.parsed) or [])
        res.ok = not res.errors
        self._log_attempt(logf, req, res, attempt)
        return res

    def _log_attempt(self, logf: Path | None, req: Request, res: Result, attempt: int):
        with self._lock:
            self.totals["attempts"] += 1
            self.totals["cached"] += res.cached
            self.totals["input_tokens"] += res.input_tokens
            self.totals["output_tokens"] += res.output_tokens
        if logf:
            self._append(logf, {"time": round(time.time(), 3), "key": req.key, "hash": res.hash, "attempt": attempt,
                                "model": self.model, "engine": self.cfg.engine, "cached": res.cached,
                                "ok": res.ok, "errors": res.errors, "finish": res.finish,
                                "input_tokens": res.input_tokens, "output_tokens": res.output_tokens,
                                "reasoning_chars": len(res.reasoning), "answer_chars": len(res.content),
                                "latency_s": round(res.latency_s, 2)})

    def _run(self, req: Request, cache: Path | None, logf: Path | None, show: bool = True) -> Result:
        with self._lock:
            self.totals["requests"] += 1
        if show:
            self.progress.start()
        try:
            res = self._run_attempts(req, cache, logf, show)
        except BaseException:
            if show:
                self.progress.finish(req.key, Result(key=req.key, errors=["exception (see the traceback)"]))
            raise
        if show:
            self.progress.finish(req.key, res)
        return res

    def _run_attempts(self, req: Request, cache: Path | None, logf: Path | None, show: bool) -> Result:
        """Up to 1 + retries attempts. When none passes its check, the result is the attempt with the fewest problems
        among those that parsed (ties: the latest), still with ok False and its errors, so a stage can keep the answer
        and mark what is unresolved instead of losing it; history holds every failed attempt."""
        followup, history, tried = list(req.followup), [], []
        attempts = 1 + self.cfg.retries
        for attempt in range(attempts):
            res = self._attempt(req, attempt, cache, logf, followup)
            tried.append(res)
            if res.ok or any(e.startswith("server rejected") for e in res.errors):
                break
            if show and attempt + 1 < attempts:
                self.progress.retry(req.key, res.errors, attempt + 2, attempts)
            history.append({"answer": res.content, "errors": res.errors})
            if req.feedback and res.content:   # the next attempt sees this answer and what is wrong with it
                followup = list(req.followup) + [
                    {"role": "assistant", "content": res.content},
                    {"role": "user", "content": FEEDBACK.format(problems="\n".join(f"- {e}" for e in res.errors))}]
        if not res.ok:
            parsed = [r for r in tried if r.parsed is not None and r.finish != "length"
                      and not any(e == "the answer is not JSON" for e in r.errors)]
            if parsed:
                res = min(reversed(parsed), key=lambda r: len(r.errors))   # fewest problems, the latest on a tie
        res.history = history
        return res
