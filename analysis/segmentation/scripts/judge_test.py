"""A first test of a dependency judge: can a learner start the lecture at this segment and follow it?
(prompt: pipeline/prompts/segmentation_judge.txt). Measures only; changes nothing in the pipeline's outputs.

    cd pipeline && python ../analysis/segmentation/scripts/judge_test.py [--segments 45/S3,57/S1,...]

The judge sees the course block, the lecture title, the earlier part of the lecture (for reference) and the segment,
numbered as in the segmentation prompt. Writes analysis/segmentation/data/judge_test/results.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PIPE = Path(__file__).resolve().parents[3] / "pipeline"
OUT = Path(__file__).resolve().parents[1] / "data" / "judge_test"
sys.path.insert(0, str(PIPE))

from scripts import course_meta  # noqa: E402
from scripts.llm import LLM, LLMConfig, Request  # noqa: E402
from scripts.view import Course  # noqa: E402

COURSE = "nptel_vr"
PROMPT = PIPE / "prompts" / "segmentation_judge.txt"
CONFIG = PIPE / "configs" / "gemma4_12b_llamacpp.json"
SCHEMA = {"type": "object", "additionalProperties": False,
          "required": ["reasoning", "depends", "needs", "sentence", "explained_at"],
          "properties": {"reasoning": {"type": "string"}, "depends": {"type": "boolean"}, "needs": {"type": "string"},
                         "sentence": {"type": "integer"}, "explained_at": {"type": "integer"}}}
# suspected real dependencies, then controls expected to pass
SUSPECTS = ["45/S3", "57/S1", "51/S5", "37/S1", "10/S1", "8/S1", "60/S4", "4/S2", "46/S1", "1/S4"]
CONTROLS = ["27/S7", "29/S2", "23/S2", "39/S7", "49/S1", "17/S2"]


def build(c: Course, sid: str) -> str:
    n = sid.split("/")[0]
    ids = [k for k in c.sentences if k.split("/")[0] == n]
    seg = c.segments[sid]
    a, b = ids.index(seg.first), ids.index(seg.last)
    num = lambda i: f"[{i + 1}] {c.sentences[ids[i]]}"  # noqa: E731
    block = course_meta.course_prompt(COURSE)
    template = PROMPT.read_text()
    if not block:
        template = template.replace("{course}\n\n", "")
    return (template.replace("{course}", block)
            .replace("{lecture_title}", course_meta.lecture_title(COURSE, n))
            .replace("{earlier}", "\n".join(num(i) for i in range(a)) or "(none: this is the first segment)")
            .replace("{segment}", "\n".join(num(i) for i in range(a, b + 1))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--segments", help="comma-separated segment IDs (default: the suspects and controls)")
    a = ap.parse_args()
    sids = a.segments.split(",") if a.segments else SUSPECTS + CONTROLS
    c = Course(COURSE)
    reqs = [Request(prompt=build(c, s), key=s, schema=SCHEMA, meta={"segment": s}) for s in sids]
    OUT.mkdir(parents=True, exist_ok=True)
    with LLM(LLMConfig.load(CONFIG)) as llm:
        res = llm.generate_many(reqs, cache_file=OUT / "cache.jsonl", log_file=OUT / "calls.jsonl")
    out = []
    for s, r in zip(sids, res):
        seg = c.segments[s]
        v = r.parsed or {}
        a = int(seg.first.split("/")[1]) + 1                 # the segment's first sentence number in the prompt
        # a dependency counts only with evidence: a sentence in the earlier part that explains it
        if v.get("depends") and not 1 <= v.get("explained_at", 0) < a:
            v["depends_claimed"], v["depends"] = True, False
        out.append({"segment": s, "group": "suspect" if s in SUSPECTS else "control" if s in CONTROLS else "",
                    "first_sentences": list(seg.sentences.values())[:3], "subgoal": seg.subgoal,
                    "verdict": r.parsed, "thinking": r.reasoning, "ok": r.ok, "errors": r.errors,
                    "input_tokens": r.input_tokens, "output_tokens": r.output_tokens})
    (OUT / "results.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    for o in out:
        v = o["verdict"] or {}
        print(f"{o['segment']:6} {o['group']:8} depends={v.get('depends')}  needs: {v.get('needs', '')[:80]}")


if __name__ == "__main__":
    main()
