"""Plumbing test of stage 4f (course structure) with a scripted fake model, on the local PC.

    python3 tests/fake_course_structure.py

Runs scripts/s4f_course_structure.py over lecture 1 (first segments) in a temporary folder. Fake answers by segment:
  1/S0  attempt 1: an ID that does not exist and a duplicate (retried; then sentences 1/0, 1/1 and 1/3)
  1/S1  always an empty list
  other empty list
Checks: retry shown the problems, neighbours 1/0 and 1/1 merge into one statement and 1/3 is a second one, text is
verbatim, shape of the JSON, a second run sends no request.
"""
from __future__ import annotations

import json
import re
import shutil
import socket
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import s4f_course_structure as s4f  # noqa: E402
from scripts.llm import LLM, LLMConfig  # noqa: E402
from scripts.llm.fake_server import FakeServer  # noqa: E402

FAILURES: list[str] = []


def check(ok: bool, what: str):
    print(("  ok    " if ok else "  FAIL  ") + what, flush=True)
    if not ok:
        FAILURES.append(what)


def free_port() -> int:
    while True:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        if not 8091 <= port <= 8095:
            return port


class Fake(FakeServer):
    bodies: list = []

    def answer(self, body: dict) -> dict:
        self.bodies.append(body)
        user = next(m["content"] for m in body["messages"] if m["role"] == "user")
        retry = any("Your answer has these problems" in (m.get("content") or "") for m in body["messages"])
        ids = re.findall(r"^\[(1/\d+)\]", user, re.M)
        if "[1/0] Hello" in user:
            out = ["1/0", "1/1", "1/3"] if retry else ["1/0", "1/99", "1/99"]
        else:
            out = []
        return {"choices": [{"message": {"content": json.dumps({"sentence_ids": out}), "reasoning_content": "x"},
                             "finish_reason": "stop"}], "usage": {"prompt_tokens": 100, "completion_tokens": 10}}


def main():
    work = Path(tempfile.mkdtemp(prefix="fake_cs_"))
    port = free_port()
    cfg = LLMConfig.load(ROOT / "configs" / "gemma4_12b_llamacpp.json").with_(
        port=port, model="fake-gemma", model_path="fake/gemma", launch=False, cache_file="", log_file="",
        server_log=str(work / "server.log"))
    server = Fake(port, cfg.model)
    server.start()
    out = work / "stage_4f"
    try:
        with LLM(cfg) as llm:
            info = s4f.run("nptel_vr", llm, ["1"], out=out)
            n1 = len(server.bodies)
            s4f.run("nptel_vr", llm, ["1"], out=out)
            n2 = len(server.bodies)
    finally:
        server.stop()
    data = json.loads((out / "course_structure.json").read_text())
    st = data["statements"]
    check(set(data) == {"run", "statements"}, "top-level keys")
    check(all(k in data["run"] for k in ("model", "prompt_sha256", "date", "segments", "calls", "retries")), "run keys")
    check(info["retries"] == 1, f"one retry ({info['retries']})")
    check(any("not sentences of this text" in json.dumps(b["messages"]) for b in server.bodies), "problems shown")
    check(len(st) == 2 and st[0]["sentence_ids"] == ["1/0", "1/1"] and st[1]["sentence_ids"] == ["1/3"],
          "neighbours merged, 1/3 separate")
    t = json.loads((ROOT / "output/nptel_vr/stage_0a_preprocess/lec_1.json").read_text())
    check(st[0]["text"] == t["1/0"] + " " + t["1/1"] and st[1]["text"] == t["1/3"], "text verbatim")
    check(st[0]["id"] == "CS0001" and st[0]["lecture"] == "1" and st[0]["segment"] == "1/S0", "id, lecture, segment")
    check(st[0]["start"] < st[0]["end"], "times")
    check(s4f.check_ids({"sentence_ids": ["1/0", "1/0"]}, ["1/0"]) != [], "duplicate fails")
    check(n2 == n1, "second run sent no request")
    check((out / "course_structure.md").exists(), "md written")
    shutil.rmtree(work, ignore_errors=True)
    print("\nALL OK" if not FAILURES else f"\n{len(FAILURES)} FAILED: {FAILURES}")
    sys.exit(1 if FAILURES else 0)


if __name__ == "__main__":
    main()
