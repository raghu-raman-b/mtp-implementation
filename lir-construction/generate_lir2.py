#!/usr/bin/env python3
"""Build LIR v2.1 for a course: the knowledge layer, then the activity layer on top of it (pipeline2/TASKS.md).

    python3 generate_lir2.py --lecture ../dataset/virtual_and_augmented_reality --only 1-10
    python3 generate_lir2.py --lecture ../dataset/virtual_and_augmented_reality --config lir2_config_small.toml

Each part and each lecture moves on as soon as its inputs are ready (pipeline2/orchestrate.py):

    critical   1 parts -> 2 objective + key points -> judge -> 3 key terms -> judge   (per part)
               4 registry (the whole course) -> 5 facets, lecture by lecture in course order
    behind     judge facets -> 6 links -> judge -> open questions -> judge; recall -> judge   (per lecture)
    filling    part activities -> judge (per part); objectives + goal -> judge (per lecture); course goals -> judge
    end        calibration answers; code: lecture map, concept maps, spaced review, scorer; assemble -> lir-v2/<course>/

Build files (cache, step outputs, report, calls.jsonl) go to output/<course>/v2/ (or --run-dir).
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
from pipeline2 import assemble, orchestrate, report  # noqa: E402
from pipeline2.context import Lecture, Models, Run  # noqa: E402
from pipeline2.flow import Flow  # noqa: E402

STAGES = {"transcripts": ("0 · sentences", 1), "v2_build": ("build (all steps)", 97), "v2_assemble": ("assemble", 2)}


def parse_only(spec):
    if not spec:
        return None
    out = set()
    for part in spec.split(","):
        a, _, b = part.partition("-")
        out.update(range(int(a), int(b or a) + 1))
    return out


def load_lectures(course, subs_dir, ui, log) -> list[Lecture]:
    lectures = []
    ui.calls("load and align transcripts", len(course.lectures))
    for inp in course.lectures:
        if inp.srt is None:  # align the official transcript to YouTube's automatic captions
            j = fetch_auto_captions(inp.youtube_id, subs_dir / f"{inp.lecture_id}.json3", subs_dir.parent / "logs" / "videos.log")
            if j is None:
                log(f"  ! {inp.lecture_id}: no captions to align to; skipped", "warn")
                ui.advance()
                continue
            inp.sentences = align_transcript(inp.txt, j)
            inp.srt = subs_dir / f"{inp.lecture_id}.srt"
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
    ap.add_argument("--run-dir", type=Path,
                    help="write this run's files to DIR/build (cache, steps, report, calls.jsonl, status.json) and its "
                         "LIR to DIR/lir, instead of output/<course>/v2/ and lir-v2/<course>/ (run_v2.sh sets it)")
    ap.add_argument("--slots", help="use only these server slots, e.g. 0-47, so two courses can share one server "
                                    "(start it first with serve_lir2.py; implies --keep-server)")
    args = ap.parse_args()
    cfg = load_config(args.config)

    t_start = time.time()
    course = discover(args.lecture, parse_only(args.only))
    if not course.lectures:
        sys.exit("no lectures to process")
    subs_dir = HERE / "output" / course.course_id / "v2" / "subs"   # captions for lectures without subtitles
    if args.run_dir:
        out, lir_dir = args.run_dir.resolve() / "build", args.run_dir.resolve() / "lir"
    else:
        out, lir_dir = HERE / "output" / course.course_id / "v2", HERE / "lir-v2" / course.course_id
    (out / "logs").mkdir(parents=True, exist_ok=True)
    if args.fresh and (out / "cache").exists():
        shutil.rmtree(out / "cache")

    UImod.STAGE_LABEL.update({k: v[0] for k, v in STAGES.items()})
    ui = UI()
    ui._weights = {k: v[1] for k, v in STAGES.items()}
    status = UImod.StatusWriter(ui, out / "status.json", course, len(course.lectures))
    with ui, status:
        log = ui.log
        log(f"Course  {course.title}  ({course.course_id})  ·  LIR v2", "stage")
        rel = lambda p: p.relative_to(HERE) if p.is_relative_to(HERE) else p  # noqa: E731
        log(f"        {len(course.lectures)} lectures · LIR → {rel(lir_dir)}/ · build files → {rel(out)}/", "dim")
        for s in course.skipped:
            log(f"  ! skipped {s}", "warn")
        if args.only and min(parse_only(args.only)) > 1:
            log("  ! earlier lectures are not processed: the registry only knows the selected lectures", "warn")

        timer = Timer(ui)
        with timer.stage("transcripts"):
            lectures = load_lectures(course, subs_dir, ui, log)
        ledger = Ledger(cfg, course.course_id)
        records: list = []
        slot_range = None
        if args.slots:
            a, _, b = args.slots.partition("-")
            slot_range = (int(a), int(b) - int(a) + 1)
            args.keep_server = True   # the server is shared: the other run may still need it
        models = Models(cfg, out, ledger, log, ui, records, slot_range)
        status.records = records
        ui.server(f"  generator: {cfg.generator.name} · verifier: {cfg.verifier.name} · "
                  f"judge: {(cfg.judge or cfg.verifier).name}")
        R = Run(course, lectures, cfg, models, out, timer, log, ui, args.seg_max_tokens)
        R.flow = Flow(log, ui)
        try:
            with timer.stage("v2_build"):
                models.start_all()
                orchestrate.build(R)
        finally:
            R.flow.shutdown()
            if not args.keep_server:
                models.stop_all()
                ui.server("  servers stopped")
        with timer.stage("v2_assemble"):
            assemble.run(R, lir_dir)
        timer.stages = timer.stages + R.flow.spans()      # whole build, assembly, then every step's span
        text = report.write(R, records, time.time() - t_start)

    ui.console.print(text.split("## Per lecture")[0].strip())
    ui.log(f"\nLIR v2   → {lir_dir}/", "ok")
    ui.log(f"Report   → {out / 'report.md'}", "ok")


if __name__ == "__main__":
    main()
