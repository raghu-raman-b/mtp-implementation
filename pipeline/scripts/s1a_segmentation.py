"""Stage 1a: split each lecture into segments with the LLM (prompt: prompts/segmentation.txt).

    python scripts/s1a_segmentation.py nptel_vr --llm configs/gemma4_e4b_llamacpp.json [--only 1-5] [--sequential]

Reads   output/<course>/stage_0a_preprocess/lec_<n>.json
        input/<course>/input/course.json (course title), input/<course>/input/titles.tsv (lecture titles)
Writes  output/<course>/stage_1a_segmentation/
          raw/lec_<n>.json             the model's answer and how it was obtained: answer, ok, errors, attempts,
                                       history (earlier answers and their problems), tokens, time, thinking
          llm/cache.jsonl, calls.jsonl  answer cache and one line per call

The whole lecture goes into one prompt, numbered from [1]. The model answers with its segments in order, each
{"start": number of its first sentence, "subgoal": what the learner can do after it}. Every answer is checked with the
deterministic checks of stage 1b (s1b_verify_segments.check); when a check fails, the model is shown its answer and
the problems and answers again (up to the config's retries). Stage 1b then writes the segment maps.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the pipeline folder
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from scripts import s1b_verify_segments as verify  # noqa: E402
from scripts.llm import LLM, LLMConfig, Request  # noqa: E402

PROMPT = ROOT / "prompts" / "segmentation.txt"
SCHEMA = {"type": "array", "minItems": 1,
          "items": {"type": "object", "additionalProperties": False, "required": ["start", "subgoal"],
                    "properties": {"start": {"type": "integer"}, "subgoal": {"type": "string"}}}}


def stage0_dir(course: str) -> Path:
    return ROOT / "output" / course / "stage_0a_preprocess"


def out_dir(course: str) -> Path:
    return ROOT / "output" / course / "stage_1a_segmentation"


def lectures_of(course: str) -> list[int]:
    return sorted(int(p.stem.split("_")[1]) for p in stage0_dir(course).glob("lec_*.json"))


def load_sentences(course: str, n: int) -> dict:
    return json.loads((stage0_dir(course) / f"lec_{n}.json").read_text())


def course_title(course: str) -> str:
    return json.loads((ROOT / "input" / course / "input" / "course.json").read_text())["title"]


def lecture_titles(course: str) -> dict[int, str]:
    with open(ROOT / "input" / course / "input" / "titles.tsv", newline="") as f:
        return {int(r["number"]): r["title"] for r in csv.DictReader(f, delimiter="\t") if r["type"] == "lecture"}


def build_prompt(sentences: dict, course: str, lecture_title: str) -> str:
    numbered = "\n".join(f"[{i}] {s}" for i, s in enumerate(sentences.values(), 1))
    return (PROMPT.read_text().replace("{course}", course).replace("{lecture_title}", lecture_title)
            .replace("{transcript}", numbered))


def run(course: str, llm: LLM, lectures: list[int] | None = None, parallel: bool = True,
        max_tokens: int | None = None, think_budget: int | None = None) -> dict:
    """Segment the lectures (all by default). parallel=True sends every lecture at once; the engine batches them."""
    lectures = lectures or lectures_of(course)
    od = out_dir(course)
    for sub in ("raw", "llm"):
        (od / sub).mkdir(parents=True, exist_ok=True)
    ctitle, ltitles = course_title(course), lecture_titles(course)
    sents = {n: load_sentences(course, n) for n in lectures}
    reqs = []
    for n in lectures:
        ids = list(sents[n])
        reqs.append(Request(prompt=build_prompt(sents[n], ctitle, ltitles.get(n, f"Lecture {n}")), key=f"lec_{n}",
                            schema=SCHEMA, check=lambda ans, ids=ids: verify.check(ans, ids), feedback=True,
                            max_tokens=max_tokens, think_budget=think_budget, meta={"lecture": n}))
    t0 = time.time()
    results = llm.generate_many(reqs, parallel=parallel, cache_file=od / "llm" / "cache.jsonl",
                                log_file=od / "llm" / "calls.jsonl")
    failed, retried = [], []
    for n, res in zip(lectures, results):
        raw = {"lecture": n, "model": llm.model, "engine": llm.cfg.engine, "sentences": len(sents[n]),
               "ok": res.ok, "errors": res.errors, "answer": res.parsed, "content": res.content,
               "attempts": res.attempts, "history": res.history, "finish": res.finish,
               "input_tokens": res.input_tokens, "output_tokens": res.output_tokens,
               "latency_s": round(res.latency_s, 2), "cached": res.cached, "reasoning": res.reasoning}
        (od / "raw" / f"lec_{n}.json").write_text(json.dumps(raw, indent=1, ensure_ascii=False) + "\n")
        if not res.ok:
            failed.append(n)
        if res.history:
            retried.append(n)
    summary = {"lectures": len(lectures), "ok": len(lectures) - len(failed), "failed": failed, "retried": retried,
               "wall_s": round(time.time() - t0, 1), "out": str(od)}
    print(f"{summary['ok']}/{len(lectures)} lectures answered, {summary['wall_s']} s"
          + (f"; retried: {retried}" if retried else "") + (f"; failed: {failed} (see raw/)" if failed else ""))
    return summary


def parse_only(spec: str) -> list[int]:
    """'1-5,8' -> [1, 2, 3, 4, 5, 8]"""
    out = []
    for part in spec.split(","):
        a, _, b = part.partition("-")
        out += list(range(int(a), int(b or a) + 1))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("course", help="course folder name, e.g. nptel_vr")
    ap.add_argument("--llm", required=True, help="LLMConfig file (.json or .toml)")
    ap.add_argument("--only", help="lectures, e.g. 1-5,8")
    ap.add_argument("--sequential", action="store_true", help="one lecture at a time instead of all at once")
    a = ap.parse_args()
    with LLM(LLMConfig.load(a.llm)) as llm:
        run(a.course, llm, parse_only(a.only) if a.only else None, parallel=not a.sequential)


if __name__ == "__main__":
    main()
