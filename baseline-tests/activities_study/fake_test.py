"""Plumbing test of the whole study with the pipeline's fake model server (no GPU, no real model).

    python3 fake_test.py [--work DIR]

Starts pipeline/scripts/llm/fake_server.py on a free port (answers that fit each request's JSON schema), a copy of the
Gemma config pointing at it (attach only), ACT_OUT in a temporary folder; runs generate, judge_gemma, checks,
packets, fake Sonnet judgments (random answers in the instructed format, from the key), summarize; then generate and
judge again, which must send no request (resumable from the cache). Fails on: a step's error, a prompt with an
unfilled {placeholder}, a B2 prompt without the numbered transcript or with a layer block filled, a B1 prompt with
sentence numbers, a missing output, a summary section missing, a rerun sending requests, the real output changed.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PIPE = HERE.parent.parent / "pipeline"


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p if p not in (8092, 8094, 8095) else free_port()


def snapshot(d: Path) -> dict:
    return {str(p): p.stat().st_mtime for p in d.rglob("*") if p.is_file()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work")
    a = ap.parse_args()
    work = Path(a.work or tempfile.mkdtemp(prefix="act_study_fake_"))
    work.mkdir(parents=True, exist_ok=True)
    port = free_port()
    cfg = json.loads((PIPE / "configs" / "gemma4_12b_llamacpp.json").read_text())
    cfg.update(port=port, launch=False, attach_wait_s=0)
    (work / "fake.json").write_text(json.dumps(cfg))
    log = work / "requests.jsonl"
    env = {**os.environ, "ACT_OUT": str(work / "out"), "ACT_LLM": str(work / "fake.json")}
    real = PIPE / "output" / "nptel_vr"
    before = snapshot(real / "activities") | snapshot(real / "knowledge")
    srv = subprocess.Popen([sys.executable, "-m", "scripts.llm.fake_server", "--port", str(port), "--model",
                            cfg["model"], "--log", str(log)], cwd=PIPE, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
    problems = []
    try:
        time.sleep(1.5)

        def run(*cmd):
            r = subprocess.run([sys.executable, *cmd], cwd=HERE, env=env, capture_output=True, text=True)
            print(f"$ {' '.join(cmd)} -> {r.returncode}; {r.stdout.strip().splitlines()[-1:] if r.stdout else ''}")
            if r.returncode:
                problems.append(f"{cmd} failed:\n{r.stderr[-3000:]}")
            return r

        for step in (["generate.py"], ["judge_gemma.py"], ["checks.py"], ["packets.py"]):
            run(*step)
        out = work / "out"
        sys.path.insert(0, str(HERE))
        os.environ.update(env)
        import study as st
        reqs = [json.loads(x) for x in log.read_text().splitlines()]
        for r in reqs:
            msgs = r.get("messages") or r.get("body", {}).get("messages") or []
            prompt = msgs[0]["content"] if msgs else ""
            left = set(re.findall(r"\{(course|facts|lecture_title|subgoal|objective|goal|related|relations|concepts|"
                                  r"count|questions|recap|puzzles|exercises|title|transcript|task|form)\}", prompt))
            if left:
                problems.append(f"unfilled placeholders {left} in a prompt starting {prompt[:80]!r}")
        prompts = [(json.loads(x).get("messages") or [{}])[0].get("content", "") for x in log.read_text().splitlines()]
        b1 = [p for p in prompts if p.startswith("You make learning activities") and "numbered in brackets" not in p]
        b2 = [p for p in prompts if p.startswith("TASK") and "[1] " in p and ("(not given)" in p or "(none)" in p)]
        if not b1 or any(re.search(r"^\[\d+\] ", p, re.M) for p in b1):
            problems.append("B1 prompts missing or numbered")
        if not b2:
            problems.append("no B2 prompt with the numbered transcript and the layer blocks emptied")
        for s in ("b1", "b2"):
            for k in st.sample():
                f = out / "gen" / s / f"lec_{k}.json"
                if not f.exists() or set(json.loads(f.read_text())["units"]) != set(st.KINDS):
                    problems.append(f"gen {s} {k}: missing or incomplete")
        judged = [json.loads(x) for x in (out / "judge" / "gemma.jsonl").read_text().splitlines()]
        by = {s: sum(r["system"] == s for r in judged) for s in st.SYSTEMS}
        if not all(by.values()):
            problems.append(f"judge units per system {by}")
        key = json.loads((out / "sonnet_key.json").read_text())
        if len(list((out / "sonnet" / "packets").glob("*.md"))) != 6:
            problems.append("packets: not 6 files")
        for p in (out / "sonnet" / "packets").glob("*.md"):
            t = p.read_text()
            if re.search(r"\b(ours|b1|b2|C\d{4}|R\d{4})\b", t) or re.search(r"\b\d+/S\d+/F\d+\b", t):
                problems.append(f"{p.name}: a system name or a layer ID leaks into the blind packet")
        rnd = random.Random(0)
        with (out / "sonnet" / "judgments.jsonl").open("w") as f:
            for uid, u in key["units"].items():
                for item in u["items"]:
                    f.write(json.dumps({"unit": uid, "item": item, "correct": rnd.random() < .8,
                                        "grounded": rnd.choice(["yes", "partly", "no"]),
                                        "distractors": rnd.choice(["good", "weak", "poor"]) if u["kind"] in
                                        ("quiz", "odd_one_out") else None, "goals": rnd.choice(["yes", "partly", "no"]),
                                        "cross_lecture": rnd.choice(["yes", "no", "wrong"]), "reason": "fake"}) + "\n")
        run("summarize.py")
        summ = (out / "summary.md").read_text()
        for sec in ("## Generation", "## Code checks", "## Pipeline judges", "## Sonnet judge (blind",
                    "## Only possible with the knowledge layer"):
            if sec not in summ:
                problems.append(f"summary lacks {sec!r}")
        n0 = len(log.read_text().splitlines())
        run("generate.py")
        run("judge_gemma.py")
        n1 = len(log.read_text().splitlines())
        if n1 != n0:
            problems.append(f"rerun sent {n1 - n0} requests (should be answered from the cache)")
        if snapshot(real / "activities") | snapshot(real / "knowledge") != before:
            problems.append("the real pipeline output changed")
        print(f"requests: {n0}; judge units {by}; sonnet items {sum(len(u['items']) for u in key['units'].values())}")
    finally:
        srv.terminate()
    print("\n".join(problems) if problems else f"FAKE TEST OK ({work})")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
