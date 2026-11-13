"""python -m qa "question" [--lecture 4] [--course nptel_vr] [--config FILE] [--think | --no-think] [--json]

Answers one question with the tool loop and prints the answer, its citations and the tool steps. Run it from the
pipeline folder. The model server (Gemma 4 12B by default) is started if none answers on the config's port, and is
left running for the next question; `python -m qa --stop` stops the llama-server on the config's port.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

from . import answer, get_llm
from .answer import DEFAULT_CONFIG
from .knowledge import fmt_time


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("question", nargs="?", help="the learner's question")
    ap.add_argument("--lecture", help="the lecture the learner is watching (e.g. 4)")
    ap.add_argument("--course", default="nptel_vr")
    ap.add_argument("--config", default=str(DEFAULT_CONFIG), help="LLM config (default: $QA_CONFIG, else Gemma 4 12B on llama.cpp)")
    th = ap.add_mutually_exclusive_group()
    th.add_argument("--think", dest="think", action="store_true", default=None, help="thinking on (config default)")
    th.add_argument("--no-think", dest="think", action="store_false", help="thinking off for these requests")
    ap.add_argument("--json", action="store_true", help="print the result as JSON")
    ap.add_argument("--stop", action="store_true", help="stop the model server on the config's port and exit")
    a = ap.parse_args()
    if a.stop:
        port = get_llm(a.config).cfg.port
        subprocess.run(["pkill", "-f", f"llama-server.*--port {port}"], check=False)
        print(f"stopped any llama-server on port {port}")
        return 0
    if not a.question:
        ap.error("give a question")
    r = answer(a.question, course=a.course, lecture=a.lecture, llm=get_llm(a.config, a.think))
    if a.json:
        print(json.dumps(r, indent=1, ensure_ascii=False))
        return 0
    print(r["answer"])
    print(f"\ncovered: {r['covered']}")
    for i, c in enumerate(r["citations"], 1):
        print(f"  [{i}] lecture {c['lecture']} {fmt_time(c['start'])}-{fmt_time(c['end'])} "
              f"{c['fact'] or c['segment']}: {c['text']}")
    print("steps:")
    for s in r["steps"]:
        print(f"  {s['tool']}({json.dumps(s['args'], ensure_ascii=False)}) -> {s['result_summary']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
