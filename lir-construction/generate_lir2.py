#!/usr/bin/env python3
"""Build LIR v2 for a course: the knowledge layer, then the activity layer on top of it.

    python3 generate_lir2.py --lecture ../dataset/virtual_and_augmented_reality --only 1-10

    0  sentences          SRT -> sentences with addresses (no SRT: transcript aligned to YouTube captions)
    generator  1 parts · 2 objective and key points per part · 3a term candidates
    judge      part objectives and key points · verifier 3b-e key terms (keep, name, define, grounded) · 4 registry
    generator  7 goals (lecture objectives, lecture goals, course goals) · 5 facets
    judge      goals and facets · verifier 6 edges (relation, evidence, label)
    code       8 lecture map
    generator  9 activities: recall, quiz (plan, items), recap, review questions, open questions (plan, write),
               calibration answers
    judge      every activity item (one rewrite, then dropped)
    code       concept maps, spaced review after each part, scorer calibration; assemble -> lir-v2/<course>/

Steps are grouped so the models swap as few times as possible when only one fits on the GPU
(lir2_config.toml [engine] exclusive_gpu). Build files (cache, step outputs, report) go to output/<course>/v2/.
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

try:  # run with the project venv if the current interpreter lacks the dependencies
    import numpy, pydantic, rich, sentence_transformers, huggingface_hub  # noqa: F401,E401
except ImportError:
    venv_py = HERE.parent / "bin/python"
    if venv_py.exists() and Path(sys.executable).resolve() != venv_py.resolve():
        os.execv(str(venv_py), [str(venv_py), __file__, *sys.argv[1:]])
    raise

import argparse
import shutil
import time

sys.path.insert(0, str(HERE))

from pipeline import ui as UImod  # noqa: E402
from pipeline.config import Ledger, load as load_config  # noqa: E402
from pipeline.context import Timer  # noqa: E402
from pipeline.media import align_transcript, fetch_auto_captions, write_srt  # noqa: E402
from pipeline.transcript import discover, load_sentences  # noqa: E402
from pipeline.ui import UI  # noqa: E402
from pipeline2 import (activities, assemble, judge_knowledge, report, s1_parts, s2_parts, s3_terms,  # noqa: E402
                       s4_registry, s5_facets, s6_edges, s7_goals, s8_lecture_map)
from pipeline2.context import Lecture, Models, Run  # noqa: E402

STAGES = {  # stage -> (label, share of the run time, for the progress bar)
    "transcripts": ("0 · sentences", 1), "v2_parts": ("1 · parts", 3), "v2_part_annotate": ("2 · objective, key points", 5),
    "v2_candidates": ("3a · term candidates", 5), "v2_judge_parts": ("judge · objectives, key points", 6),
    "v2_terms": ("3b-e · key terms", 14), "v2_registry": ("4 · registry", 10), "v2_goals": ("7 · goals", 2),
    "v2_facets": ("5 · facets", 9), "v2_judge_goals_facets": ("judge · goals, facets", 7), "v2_edges": ("6 · edges", 11),
    "v2_lecture_map": ("8 · lecture map", 1), "v2_activities": ("9 · activities", 12),
    "v2_judge_activities": ("judge · activities", 12), "v2_finish": ("concept maps, review, scorer", 1),
    "v2_assemble": ("assemble", 1),
}


def parse_only(spec):
    if not spec:
        return None
    out = set()
    for part in spec.split(","):
        a, _, b = part.partition("-")
        out.update(range(int(a), int(b or a) + 1))
    return out


def load_lectures(course, out, ui, log) -> list[Lecture]:
    lectures = []
    ui.calls("load and align transcripts", len(course.lectures))
    for inp in course.lectures:
        if inp.srt is None:  # align the official transcript to YouTube's automatic captions
            j = fetch_auto_captions(inp.youtube_id, out / "subs" / f"{inp.lecture_id}.json3", out / "logs" / "videos.log")
            if j is None:
                log(f"  ! {inp.lecture_id}: no captions to align to; skipped", "warn")
                ui.advance()
                continue
            inp.sentences = align_transcript(inp.txt, j)
            inp.srt = out / "subs" / f"{inp.lecture_id}.srt"
            write_srt(inp.sentences, inp.srt)
        else:
            inp.sentences = load_sentences(inp.srt)
        lectures.append(Lecture(inp, len(lectures) + 1))
        ui.advance()
    return lectures


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lecture", required=True, type=Path, help="course folder (subs/, transcripts/, titles.tsv)")
    ap.add_argument("--only", help="lecture numbers to process, e.g. 1-10 or 1,4,7 (default: all)")
    ap.add_argument("--config", type=Path, default=HERE / "lir2_config.toml", help="models per role and per step")
    ap.add_argument("--seg-max-tokens", type=int, default=28000,
                    help="longest transcript split into parts in one call; longer lectures use windows")
    ap.add_argument("--fresh", action="store_true", help="ignore cached LLM answers for this course")
    ap.add_argument("--keep-server", action="store_true", help="leave the model servers running afterwards")
    args = ap.parse_args()
    cfg = load_config(args.config)

    t_start = time.time()
    course = discover(args.lecture, parse_only(args.only))
    if not course.lectures:
        sys.exit("no lectures to process")
    out = HERE / "output" / course.course_id / "v2"
    lir_dir = HERE / "lir-v2" / course.course_id
    (out / "logs").mkdir(parents=True, exist_ok=True)
    if args.fresh and (out / "cache").exists():
        shutil.rmtree(out / "cache")

    UImod.STAGE_LABEL.update({k: v[0] for k, v in STAGES.items()})
    ui = UI()
    ui._weights = {k: v[1] for k, v in STAGES.items()}
    with ui:
        log = ui.log
        log(f"Course  {course.title}  ({course.course_id})  ·  LIR v2", "stage")
        log(f"        {len(course.lectures)} lectures · LIR → lir-v2/{course.course_id}/ · build files → "
            f"output/{course.course_id}/v2/", "dim")
        for s in course.skipped:
            log(f"  ! skipped {s}", "warn")
        if args.only and min(parse_only(args.only)) > 1:
            log("  ! earlier lectures are not processed: the registry only knows the selected lectures", "warn")

        timer = Timer(ui)
        with timer.stage("transcripts"):
            lectures = load_lectures(course, out, ui, log)
        ledger = Ledger(cfg, course.course_id)
        records: list = []
        models = Models(cfg, out, ledger, log, ui, records)
        ui.server(f"  generator: {cfg.generator.name} · verifier: {cfg.verifier.name} · "
                  f"judge: {(cfg.judge or cfg.verifier).name}")
        R = Run(course, lectures, cfg, models, out, timer, log, ui, args.seg_max_tokens)
        try:
            # generator
            with timer.stage("v2_parts"):
                s1_parts.run(R)
            with timer.stage("v2_part_annotate"):
                s2_parts.run(R)
            with timer.stage("v2_candidates"):
                by_window = s3_terms.candidates(R)
            # verifier
            with timer.stage("v2_judge_parts"):
                judge_knowledge.run_parts(R)
            with timer.stage("v2_terms"):
                s3_terms.run(R, by_window)
            with timer.stage("v2_registry"):
                s4_registry.run(R)
            # generator
            with timer.stage("v2_goals"):
                s7_goals.run_objectives(R)
                s7_goals.run_lecture_goals(R)
                s7_goals.run_course_goals(R)
            with timer.stage("v2_facets"):
                s5_facets.run(R)
            # verifier
            with timer.stage("v2_judge_goals_facets"):
                judge_knowledge.run_goals_facets(R)
            with timer.stage("v2_edges"):
                s6_edges.run(R)
            with timer.stage("v2_lecture_map"):
                s8_lecture_map.run(R)
            # generator, then verifier
            with timer.stage("v2_activities"):
                activities.generate(R)
            with timer.stage("v2_judge_activities"):
                activities.judge(R)
        finally:
            if not args.keep_server:
                models.stop_all()
                ui.server("  servers stopped")
        with timer.stage("v2_finish"):
            activities.finish(R)
        with timer.stage("v2_assemble"):
            assemble.run(R, lir_dir)
        text = report.write(R, records, time.time() - t_start)

    ui.console.print(text.split("## Per lecture")[0].strip())
    ui.log(f"\nLIR v2   → lir-v2/{course.course_id}/", "ok")
    ui.log(f"Report   → output/{course.course_id}/v2/report.md", "ok")


if __name__ == "__main__":
    main()
