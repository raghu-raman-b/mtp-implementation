"""Plumbing test of stage 4e (part titles) with a scripted fake model, on the local PC.

    python3 tests/fake_part_titles.py [--keep]

Runs scripts/s4e_part_titles.py over lectures 1 and 2 of the real knowledge layer (read only), with its output in a
new temporary folder. The fake model listens on a free port (never 8091 to 8095) through a copy of the Gemma config
with launch false. Its answers by segment (found by the goal line of the prompt):
  1/S0  attempt 1: "Introduction to VR Systems." (filler and a final period); then a good title (retried, and the
        retry conversation shows the problems found)
  1/S1  always two words (unresolved: title null, ok false, the problems listed)
  1/S3  the title of 1/S2 until the prompt says titles are already used (repeat found after the first pass, asked again)
  other a title of words from the goal
What it checks: titles.json shape ({"run", "segments": {id: {title, ok, problems}}}), every segment present, the seeded
cases above, the code check on bad titles directly, the cache (a second run sends no request and gives the same
file), titles.txt, and that nothing under the real output/ changed.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the pipeline folder
sys.path.insert(0, str(ROOT))

from scripts import s4e_part_titles as s4e  # noqa: E402
from scripts.llm import LLM, LLMConfig  # noqa: E402
from scripts.llm.fake_server import FakeServer  # noqa: E402

FORBIDDEN = {8091, 8092, 8093, 8094, 8095}
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
        if port not in FORBIDDEN:
            return port


def title_from(goal: str) -> str:
    w = re.findall(r"[A-Za-z]+", goal)[1:5]
    return " ".join(x.capitalize() for x in w)


class Fake(FakeServer):
    bodies: list = []

    def answer(self, body: dict) -> dict:
        self.bodies.append(body)
        user = next(m["content"] for m in body["messages"] if m["role"] == "user")
        goal = re.search(r"Goal of the part: (.*)", user).group(1)
        retry = any("Your answer has these problems" in (m.get("content") or "") for m in body["messages"])
        goals = self.goals
        sid = next(s for s, g in goals.items() if g == goal)
        if sid == "1/S0":
            t = title_from(goal) if retry else "Introduction to VR Systems."
        elif sid == "1/S1":
            t = "Two Words"
        elif sid == "1/S3":
            t = title_from(goals["1/S2"]) if "already used" not in user else title_from(goal)
        else:
            t = title_from(goal)
        content = json.dumps({"title": t})
        return {"choices": [{"message": {"content": content, "reasoning_content": "fake thinking"},
                             "finish_reason": "stop"}], "usage": {"prompt_tokens": 100, "completion_tokens": 10}}


def snapshot(folder: Path) -> dict:
    return {str(p): p.stat().st_mtime_ns for p in folder.rglob("*") if p.is_file()}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--keep", action="store_true", help="keep the temporary folder")
    a = ap.parse_args()
    before = snapshot(ROOT / "output")
    work = Path(tempfile.mkdtemp(prefix="fake_titles_"))
    port = free_port()
    cfg = LLMConfig.load(ROOT / "configs" / "gemma4_12b_llamacpp.json").with_(
        port=port, model="fake-gemma", model_path="fake/gemma", launch=False, cache_file="", log_file="",
        server_log=str(work / "server.log"))
    segs = {}
    for k in ("1", "2"):
        d = json.loads((ROOT / "output/nptel_vr/knowledge/lectures" / f"lec_{k}.json").read_text())
        segs.update({s: v["subgoal"] for s, v in d["segments"].items()})
    server = Fake(port, cfg.model)
    server.goals = segs
    server.start()
    out = work / "stage_4e"
    try:
        with LLM(cfg) as llm:
            info = s4e.run("nptel_vr", llm, ["1", "2"], out=out)
            n1 = len(server.bodies)
            info2 = s4e.run("nptel_vr", llm, ["1", "2"], out=out)
            n2 = len(server.bodies)
    finally:
        server.stop()
    data = json.loads((out / "titles.json").read_text())
    s = data["segments"]
    print("shape", flush=True)
    check(set(data) == {"run", "segments"}, "top-level keys are run and segments")
    check(set(s) == set(segs), f"every segment present ({len(s)})")
    check(all(set(v) == {"title", "ok", "problems"} for v in s.values()), "each entry has title, ok, problems")
    check(all((v["title"] is None) == (not v["ok"]) for v in s.values()), "title null exactly when not ok")
    check(all(k in data["run"] for k in ("model", "prompt_sha256", "seconds")), "run has model, prompt hash, seconds")
    print("seeded cases", flush=True)
    check(s["1/S0"]["ok"] and s["1/S0"]["title"] == title_from(segs["1/S0"]), "1/S0 retried and fixed")
    retry_msgs = [b for b in server.bodies if "Introduction to VR" in json.dumps(b["messages"])
                  and any("Your answer has these problems" in (m.get("content") or "") for m in b["messages"])]
    check(bool(retry_msgs) and "filler" in json.dumps(retry_msgs[0]["messages"]), "retry shows the problems found")
    check(not s["1/S1"]["ok"] and s["1/S1"]["title"] is None and any("2 words" in p for p in s["1/S1"]["problems"]),
          "1/S1 unresolved: null title, problems listed")
    check(s["1/S2"]["ok"] and s["1/S3"]["ok"] and s["1/S2"]["title"] != s["1/S3"]["title"],
          "repeated title of 1/S3 asked again and now different")
    others = [v for k, v in s.items() if k not in ("1/S1",)]
    check(all(v["ok"] for v in others), "all other segments ok")
    check(info["failed"] == 1 and info["ok"] == len(segs) - 1, "run counts: one failed")
    print("code check", flush=True)
    g, f = "Explain how a head mounted display shows depth.", "- A head mounted display shows two images."
    c = s4e.check_title
    check(c("Depth in Head Mounted Displays", g, f, set()) == [], "a good title passes")
    check(any("words" in p for p in c("Depth", g, f, set())), "one word fails")
    check(any("words" in p for p in c("A Very Long Title About Depth In Displays", g, f, set())), "seven words fail")
    check(any("punctuation" in p for p in c("Depth in Head Displays.", g, f, set())), "final period fails")
    check(any("quotes" in p for p in c('"Depth in Head" Displays', g, f, set())), "quotes fail")
    check(any("ID" in p for p in c("Facts 1/S0/F1 About Depth", g, f, set())), "ID fails")
    check(any("Title Case" in p for p in c("depth in head mounted displays", g, f, set())), "lower case fails")
    check(any("filler" in p for p in c("Overview of Head Displays", g, f, set())), "filler fails")
    check(any("copies" in p for p in c("Explain How A Head Mounted", g, f, set())), "copy of the goal fails")
    check(any("already" in p for p in c("Depth in Displays", g, f, {"depth in displays"})), "repeat fails")
    check(any("no word" in p for p in c("Quantum Cat Tails", g, f, set())), "invented words fail")
    print("cache and files", flush=True)
    check(n2 == n1, f"second run sent no request ({n1} then {n2})")
    check(info2["ok"] == info["ok"], "second run gives the same counts")
    txt = (out / "titles.txt").read_text()
    check("1/S0" in txt and "goal:" in txt and "NO TITLE" in txt, "titles.txt has segments, goals and the failure")
    check((out / "llm" / "cache.jsonl").exists(), "llm cache written")
    check(snapshot(ROOT / "output") == before, "nothing under the real output/ changed")
    if a.keep:
        print(f"kept {work}")
    else:
        shutil.rmtree(work, ignore_errors=True)
    print("\nALL OK" if not FAILURES else f"\n{len(FAILURES)} FAILED: {FAILURES}")
    sys.exit(1 if FAILURES else 0)


if __name__ == "__main__":
    main()
