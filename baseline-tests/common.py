"""Shared bits for the baseline runs: paths, the model server, one chat call with timings."""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent
PIPE = ROOT / "pipeline"
DATA = PIPE / "output" / "nptel_vr"
CFG = json.loads((PIPE / "configs" / "gemma4_12b_llamacpp.json").read_text())
PORT = CFG["port"]
COURSE_TITLE = "Foundation for Virtual and Augmented Reality Systems"
# the sampling every system gets (the qa config's): temperature, top_p, top_k; thinking off for the single-call
# baselines (qa itself thinks in round 0 only, see README)
SAMPLING = {"temperature": CFG["temperature"], "top_p": CFG["top_p"], "top_k": CFG["top_k"]}
MAX_TOKENS = 2048


def chat(system: str, user: str, think: bool = False, max_tokens: int = MAX_TOKENS) -> dict:
    """One streamed chat completion; returns content, tokens, wall time, time to first content token."""
    body = {"messages": ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user}],
            "max_tokens": max_tokens, "stream": True, "stream_options": {"include_usage": True},
            "chat_template_kwargs": {"enable_thinking": think}, **SAMPLING}
    t0 = time.time()
    first = None
    content, reasoning, usage, finish = "", "", {}, None
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            d = json.loads(data)
            if d.get("usage"):
                usage = d["usage"]
            for ch in d.get("choices") or []:
                delta = ch.get("delta") or {}
                reasoning += delta.get("reasoning_content") or ""
                if delta.get("content"):
                    if first is None:
                        first = time.time() - t0
                    content += delta["content"]
                finish = ch.get("finish_reason") or finish
    return {"content": content.strip(), "reasoning_chars": len(reasoning), "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0), "seconds": round(time.time() - t0, 2),
            "first_token_s": round(first, 2) if first is not None else None, "finish": finish}


def fmt_time(t: float) -> str:
    t = int(round(float(t or 0)))
    h, m, s = t // 3600, t % 3600 // 60, t % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def log(*a):
    print(*a, file=sys.stderr, flush=True)
