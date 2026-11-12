"""Stage 1a: split each lecture into segments with the LLM (prompt: prompts/segmentation.txt). Generation only: one
answer per lecture, saved as it is. All checks and retries are stage 1b's.

    python scripts/s1a_segmentation.py nptel_vr --llm configs/gemma4_12b_llamacpp.json [--only 1-5] [--sequential]

Reads   output/<course>/stage_0a_preprocess/lec_<n>.json
        input/<course>/input/course.json (course metadata), input/<course>/input/titles.tsv (lecture titles)
Prompt  prompts/segmentation.txt; {course} is the course block (outline and syllabus, scripts/course_meta.py),
        {lecture_title} the lecture's title, {transcript} the numbered sentences
Writes  output/<course>/stage_1a_segmentation/
          raw/lec_<n>.json             the answer: answer (parsed), content (as sent back, for the retry history),
                                       prompt_sha (1b checks that it rebuilds the same prompt), tokens, time, thinking
          llm/cache.jsonl, calls.jsonl  answer cache and one line per call

The whole lecture goes into one prompt, numbered from [1]. The model answers with a JSON object (constrained by a
JSON schema): {"reasoning": why it chose this segmentation, in a few sentences; "segments": [{"start": number of the
segment's first sentence, "subgoal": what the learner can do after it}, ...] in order}. The reasoning is part of the
answer 1b sends back in its retry conversation, so a retry starts from why the cuts were made.
The only retry here is the LLM API's own when an answer is not JSON at all (e.g. cut off at max_tokens).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the pipeline folder
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from scripts import course_meta, lectures as lec  # noqa: E402
from scripts.llm import LLM, LLMConfig, Request  # noqa: E402

PROMPT = ROOT / "prompts" / "segmentation.txt"
SEGMENTS = {"type": "array", "minItems": 1,
            "items": {"type": "object", "additionalProperties": False, "required": ["start", "subgoal"],
                      "properties": {"start": {"type": "integer"}, "subgoal": {"type": "string"}}}}
# reasoning first, so the segments follow from it; 1b sends the answer back as it is, reasoning included
SCHEMA = {"type": "object", "additionalProperties": False, "required": ["reasoning", "segments"],
          "properties": {"reasoning": {"type": "string"}, "segments": SEGMENTS}}


def stage0_dir(course: str) -> Path:
    return ROOT / "output" / course / "stage_0a_preprocess"


def out_dir(course: str) -> Path:
    return ROOT / "output" / course / "stage_1a_segmentation"


def lectures_of(course: str) -> list[str]:
    """The keys of the course's lectures and tutorials (scripts/lectures.py), in order."""
    return lec.keys(stage0_dir(course))


def load_sentences(course: str, n) -> dict:
    return json.loads((stage0_dir(course) / f"{lec.stem_of(n)}.json").read_text())


def build_prompt(sentences: dict, course: str, n) -> str:
    """prompts/segmentation.txt with the course block (scripts/course_meta.py), the lecture title and the transcript."""
    numbered = "\n".join(f"[{i}] {s}" for i, s in enumerate(sentences.values(), 1))
    block, template = course_meta.course_prompt(course), PROMPT.read_text()
    if not block:                                      # no outline or syllabus: no course section at all
        template = template.replace("{course}\n\n", "")
    return (template.replace("{course}", block)
            .replace("{lecture_title}", course_meta.lecture_title(course, n))
            .replace("{transcript}", numbered))        # last, so text in the transcript is never replaced


def prompt_sha(prompt: str) -> str:
    return hashlib.sha256(prompt.encode()).hexdigest()[:16]


def run(course: str, llm: LLM, lectures: list | None = None, parallel: bool = True,
        max_tokens: int | None = None, think_budget: int | None = None) -> dict:
    """Segment the lectures (all by default). parallel=True sends every lecture at once; the engine batches them."""
    lectures = lec.normalize(lectures) or lectures_of(course)
    od = out_dir(course)
    for sub in ("raw", "llm"):
        (od / sub).mkdir(parents=True, exist_ok=True)
    sents = {n: load_sentences(course, n) for n in lectures}
    prompts = {n: build_prompt(sents[n], course, n) for n in lectures}
    reqs = [Request(prompt=prompts[n], key=lec.stem_of(n), schema=SCHEMA, max_tokens=max_tokens,
                    think_budget=think_budget, meta={"lecture": n}) for n in lectures]
    t0 = time.time()
    print(f"1a: segmenting {len(reqs)} lectures with {llm.model} (all at once)" if parallel else
          f"1a: segmenting {len(reqs)} lectures with {llm.model} (one at a time)", flush=True)
    results = llm.generate_many(reqs, parallel=parallel, cache_file=od / "llm" / "cache.jsonl",
                                log_file=od / "llm" / "calls.jsonl")
    no_answer = []
    for n, res in zip(lectures, results):
        raw = {"lecture": n, "model": llm.model, "engine": llm.cfg.engine, "sentences": len(sents[n]),
               "prompt_sha": prompt_sha(prompts[n]), "answer": res.parsed, "content": res.content,
               "errors": res.errors, "attempts": res.attempts, "finish": res.finish,
               "input_tokens": res.input_tokens, "output_tokens": res.output_tokens,
               "latency_s": round(res.latency_s, 2), "cached": res.cached, "reasoning": res.reasoning}
        (od / "raw" / f"{lec.stem_of(n)}.json").write_text(json.dumps(raw, indent=1, ensure_ascii=False) + "\n")
        if not res.ok:
            no_answer.append(n)
    summary = {"lectures": len(lectures), "answered": len(lectures) - len(no_answer), "no_answer": no_answer,
               "wall_s": round(time.time() - t0, 1), "out": str(od)}
    print(f"{summary['answered']}/{len(lectures)} lectures answered, {summary['wall_s']} s"
          + (f"; no JSON answer: {no_answer} (1b will retry them)" if no_answer else ""))
    return summary


parse_only = lec.parse_only   # '1-5,8,24b,tut_1' -> ['1', ..., '5', '8', '24b', 'tut_1']


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("course", help="course folder name, e.g. nptel_vr")
    ap.add_argument("--llm", required=True, help="LLMConfig file (.json or .toml)")
    ap.add_argument("--only", help="lectures, e.g. 1-5,8,24b,tut_1")
    ap.add_argument("--sequential", action="store_true", help="one lecture at a time instead of all at once")
    a = ap.parse_args()
    with LLM(LLMConfig.load(a.llm)) as llm:
        run(a.course, llm, parse_only(a.only) if a.only else None, parallel=not a.sequential)


if __name__ == "__main__":
    main()
