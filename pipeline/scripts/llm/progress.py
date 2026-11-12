"""Live progress for LLM calls, written as plain lines (they stay readable through tee, in tmux and in log files).

    02:31:05  ✓ lec_5           in 6,214  out 9,832  412 s                  [12/63 done]
    02:31:09  ✗ lec_7           cut off at max_tokens -> attempt 2 of 3
    02:31:40  … 51 in flight, 12/63 done, 7m 12s | vllm: 51 running, 0 waiting, 1,150 tok/s, KV 66%

One line per finished request (✓ answered, ✗ failed after its last attempt, ↻ an attempt failed and is retried,
· answered from the cache); a heartbeat every HEARTBEAT_S seconds while requests are in flight, with the server's own
numbers (vLLM's /metrics: requests running and waiting, generation speed, KV cache use; llama.cpp: none).
"""
from __future__ import annotations

import re
import sys
import threading
import time
import urllib.request

HEARTBEAT_S = 30


def clock() -> str:
    return time.strftime("%H:%M:%S")


def span(s: float) -> str:
    s = int(s)
    return f"{s // 3600}h {s % 3600 // 60:02d}m" if s >= 3600 else f"{s // 60}m {s % 60:02d}s" if s >= 60 else f"{s}s"


class Progress:
    def __init__(self, llm, out=sys.stdout):
        self.llm, self.out = llm, out
        self.lock = threading.Lock()
        self.in_flight = 0
        self.batch_total = self.batch_done = 0
        self.t0 = time.time()
        self._thread: threading.Thread | None = None
        self._last_gen: tuple[float, float] | None = None    # (time, generation_tokens_total)

    # ------------------------------------------------------------------ output
    def line(self, text: str):
        with self.lock:
            self.out.write(f"  {clock()}  {text}\n")
            self.out.flush()

    # ------------------------------------------------------------------ batches (generate_many)
    def batch_start(self, n: int):
        with self.lock:
            self.batch_total, self.batch_done, self.t0 = n, 0, time.time()

    def batch_end(self):
        with self.lock:
            n, self.batch_total, self.batch_done = self.batch_total, 0, 0
        self.line(f"batch of {n} finished in {span(time.time() - self.t0)}")

    # ------------------------------------------------------------------ requests
    def start(self):
        with self.lock:
            self.in_flight += 1
            if self.batch_total == 0 and self.in_flight == 1:
                self.t0 = time.time()
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._beat, daemon=True)
                self._thread.start()

    def retry(self, key: str, errors: list[str], next_attempt: int, attempts: int):
        self.line(f"↻ {key:<16} {'; '.join(errors)[:120]} -> attempt {next_attempt} of {attempts}")

    def finish(self, key: str, res):
        with self.lock:
            self.in_flight -= 1
            if self.batch_total:
                self.batch_done += 1
            count = f"[{self.batch_done}/{self.batch_total} done]" if self.batch_total else ""
        if res.cached and res.ok:
            mark, what = "·", "from the cache"
        elif res.ok:
            mark = "✓"
            what = (f"in {res.input_tokens:,}  out {res.output_tokens:,}  {res.latency_s:.0f} s"
                    + (f"  (attempt {res.attempts})" if res.attempts > 1 else ""))
        else:
            mark, what = "✗", "FAILED: " + "; ".join(res.errors)[:120]
        self.line(f"{mark} {key:<16} {what:<52} {count}".rstrip())

    # ------------------------------------------------------------------ heartbeat
    def _beat(self):
        while True:
            time.sleep(HEARTBEAT_S)
            with self.lock:
                if self.in_flight == 0:
                    self._thread = None
                    return
                flight, done, total, t0 = self.in_flight, self.batch_done, self.batch_total, self.t0
            parts = [f"{flight} in flight"] + ([f"{done}/{total} done"] if total else []) + [span(time.time() - t0)]
            server = self.server_status()
            self.line("… " + ", ".join(parts) + (f" | {server}" if server else ""))

    def server_status(self) -> str:
        if not self.llm._started:
            return "waiting for the server to start"
        if self.llm.cfg.engine != "vllm":
            return ""
        try:
            with urllib.request.urlopen(self.llm.server.url + "/metrics", timeout=3) as r:
                text = r.read().decode()
        except OSError:
            return "vllm: no answer"
        def metric(name):
            m = re.search(rf"^vllm:{name}(?:{{[^}}]*}})? ([0-9.e+-]+)$", text, re.M)
            return float(m[1]) if m else None
        running, waiting = metric("num_requests_running"), metric("num_requests_waiting")
        kv, gen = metric("kv_cache_usage_perc"), metric("generation_tokens_total")
        out = []
        if running is not None:
            out.append(f"{running:.0f} running, {waiting or 0:.0f} waiting")
        if gen is not None:
            now = time.time()
            if self._last_gen:
                out.append(f"{(gen - self._last_gen[1]) / max(1e-6, now - self._last_gen[0]):,.0f} tok/s")
            self._last_gen = (now, gen)
        if kv is not None:
            out.append(f"KV {kv * 100:.0f}%")
        return "vllm: " + ", ".join(out) if out else ""
