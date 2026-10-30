#!/usr/bin/env python3
"""Build the Lecture Intermediate Representation (LIR) for a course, end to end, ready to view.

    python3 generate_lir.py --lecture ../dataset/virtual_and_augmented_reality
    python3 generate_lir.py --lecture ../dataset/mit_6_7960_deep_learning --only 1-3

--lecture is a course folder from the dataset (subs/, transcripts/, titles.tsv). One command runs everything:

    videos         downloaded from YouTube (titles.tsv youtube_id) in the background while the LIR is built
    0 transcripts  SRT -> sentences; lectures without an SRT are aligned to YouTube's captions
    1-5            segment, annotate, goal hierarchy, course state, generate          (Gemma 4 E4B, Q8)
    6              calibrate the answer scorer; judge every item and repair failures   (judge from lir_config.toml)
    7              assemble and validate the LIR -> lir/<course_id>/
    view           python3 serve.py, then open http://localhost:8000

Build files (cache, stage outputs, course state, logs, timing report) go to output/<course_id>/.
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

try:  # run with the project venv if the current interpreter lacks the dependencies
    import numpy, pydantic, rich, sentence_transformers, huggingface_hub, yt_dlp  # noqa: F401,E401
except ImportError:
    venv_py = HERE.parent / "bin/python"
    if venv_py.exists() and Path(sys.executable).resolve() != venv_py.resolve():
        os.execv(str(venv_py), [str(venv_py), __file__, *sys.argv[1:]])
    raise

import argparse
import json
import shutil
import time

sys.path.insert(0, str(HERE))

from pipeline import (calibrate, report, s1_segment, s2_annotate, s3_goals, s4_state, s5_generate,  # noqa: E402
                      s6_judge, s7_assemble)
from pipeline.context import Lec, Run, Timer  # noqa: E402
from pipeline.llm import LLM, Server  # noqa: E402
from pipeline.media import VideoDownloader, align_transcript, fetch_auto_captions, write_srt  # noqa: E402
from pipeline.transcript import discover, load_sentences  # noqa: E402
from pipeline.ui import UI  # noqa: E402
from pipeline.config import Ledger, load as load_config  # noqa: E402

DEFAULT_RATE = 0.12   # seconds of processing per second of video, until a previous run gives a better figure


def parse_only(spec):
    if not spec:
        return None
    out = set()
    for part in spec.split(","):
        a, _, b = part.partition("-")
        out.update(range(int(a), int(b or a) + 1))
    return out


def prior_rate() -> float:
    """Processing seconds per video second, from earlier runs' timing.json (judged runs only)."""
    rates = []
    for f in (HERE / "output").glob("*/timing.json"):
        try:
            d = json.loads(f.read_text())
            if d.get("judge") and d.get("video_s"):
                rates.append(d["pipeline_wall_s"] / d["video_s"])
        except Exception:
            pass
    return sum(rates) / len(rates) if rates else DEFAULT_RATE


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lecture", required=True, type=Path, help="course folder (subs/, transcripts/, titles.tsv)")
    ap.add_argument("--only", help="lecture numbers to process, e.g. 1-3 or 1,4,7 (default: all)")
    ap.add_argument("--config", type=Path, default=HERE / "lir_config.toml",
                    help="which models to use for generation and judging, and the API budget (lir_config.toml)")
    ap.add_argument("--seg-max-tokens", type=int, default=28000,
                    help="longest transcript prompt segmented in one call; longer lectures use windows")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--lir-only", action="store_true", help="build the LIR only; do not download videos")
    mode.add_argument("--videos-only", action="store_true", help="only download the videos; do not build the LIR")
    ap.add_argument("--no-judge", action="store_true", help="skip the layer-3 judge (faster, less checked)")
    ap.add_argument("--fresh", action="store_true", help="ignore cached LLM answers for this course")
    ap.add_argument("--keep-server", action="store_true", help="leave the generator server running afterwards")
    args = ap.parse_args()
    cfg = load_config(args.config)
    args.video_height = int(cfg.videos.get("height", 720))

    t_start = time.time()
    course = discover(args.lecture, parse_only(args.only))
    if not course.lectures:
        sys.exit("no lectures to process")
    out = HERE / "output" / course.course_id
    lir_dir = HERE / "lir" / course.course_id
    media_dir = HERE / "media" / course.course_id
    (out / "logs").mkdir(parents=True, exist_ok=True)
    if args.fresh and (out / "cache").exists():
        shutil.rmtree(out / "cache")

    ui = UI(only_videos=args.videos_only)
    with ui:
        log = ui.log
        log(f"Course  {course.title}  ({course.course_id})", "stage")
        log(f"        {len(course.lectures)} lectures · LIR → lir/{course.course_id}/ · build files → "
            f"output/{course.course_id}/", "dim")
        for s in course.skipped:
            log(f"  ! skipped {s}", "warn")
        if args.only and min(parse_only(args.only)) > 1:
            log("  ! earlier lectures are not processed, so cross-lecture links only see the selected lectures", "warn")
        if args.no_judge:
            ui.skip("stage6_judge")

        # ---- videos, in the background for the whole run
        downloader = None
        if not args.lir_only:
            downloader = VideoDownloader([(l.lecture_id, l.youtube_id) for l in course.lectures], media_dir, ui,
                                         out / "logs" / "videos.log", args.video_height)
            downloader.start()
            log(f"  downloading {len(course.lectures)} videos at {args.video_height}p in the background "
                f"→ media/{course.course_id}/", "video")
        if args.videos_only:
            downloader.join()
            log(f"Videos: {downloader.done}/{len(downloader.items)} in media/{course.course_id}/"
                + (f"; failed: {', '.join(downloader.failed)}" if downloader.failed else ""),
                "ok" if not downloader.failed else "warn")
            return

        # ---- 0: transcripts
        timer = Timer(ui)
        lectures = []
        with timer.stage("transcripts"):
            ui.calls("load and align transcripts", len(course.lectures))
            for inp in course.lectures:
                if inp.srt is None:  # align the official transcript to YouTube's automatic captions
                    j = fetch_auto_captions(inp.youtube_id, out / "subs" / f"{inp.lecture_id}.json3",
                                            out / "logs" / "videos.log")
                    if j is None:
                        log(f"  ! {inp.lecture_id}: no captions to align to; skipped", "warn")
                        ui.advance()
                        continue
                    inp.sentences = align_transcript(inp.txt, j)
                    inp.srt = out / "subs" / f"{inp.lecture_id}.srt"
                    write_srt(inp.sentences, inp.srt)
                    log(f"  {inp.lecture_id}: no subtitle file; aligned the official transcript to YouTube's "
                        f"captions ({len(inp.sentences)} sentences)")
                else:
                    inp.sentences = load_sentences(inp.srt)
                lectures.append(Lec(inp))
                ui.advance()
            video_s = sum(l.inp.duration for l in lectures)
            ui.set_prior(video_s * prior_rate() + 60)
            ui.table(f"{len(lectures)} lectures, {video_s / 3600:.1f} h of video",
                     ["Lecture", "Title", "Minutes", "Sentences", "Timing"],
                     [[l.id, l.inp.title[:48], f"{l.inp.duration / 60:.1f}", len(l.sentences), l.inp.timing_source]
                      for l in lectures], [None, None, "cyan", None, "grey58"])

        # ---- models, from lir_config.toml: local llama.cpp servers share the GPU one at a time; API models need none
        ledger = Ledger(cfg, course.course_id)
        gen = Server(cfg.generator, cfg, out / "logs", ledger)
        judge_srv = Server(cfg.judge, cfg, out / "logs", ledger)
        fb_srv = Server(cfg.judge_fallback, cfg, out / "logs", ledger) if cfg.judge_fallback and not cfg.judge.local else None

        def status(srv):
            spend = (f" · API spend ${ledger.spent:.3f} of ${ledger.budget:.2f}"
                     if not (cfg.generator.local and cfg.judge.local) else "")
            ui.server(f"  generator: {cfg.generator.name} · judge: {cfg.judge.name}{spend}")
        ledger.on_update = lambda l: status(None)

        def start_generator():
            if not gen.health():
                gen.start(lambda m: log(m, "dim"))
            status(gen)

        def start_judge():
            if judge_srv.health():  # an API judge is always ready: the generator can stay on the GPU
                return
            # a local judge needs the card to itself: fall back to fewer slots / a smaller KV pool if it does not fit
            tries = [(cfg.judge.slots, cfg.judge.kv_tokens), (6, 24576), (4, 16384)]
            for slots, ctx in tries:
                judge_srv.slots, judge_srv.ctx_total = slots, ctx
                try:
                    judge_srv.start(lambda m: log(m, "dim"))
                    R.judge.workers = slots
                    R.judge._budget = int(ctx * 0.85)
                    status(judge_srv)
                    return
                except RuntimeError:
                    log(f"  ! judge server did not fit with {slots} slots and a {ctx:,}-token KV pool", "warn")
            raise SystemExit(f"The judge model does not fit on the GPU (see {judge_srv.log_path}). "
                             f"Free GPU memory, or rerun with --no-judge.")

        def start_fallback():
            """The API budget ran out: put the local fallback judge on the GPU (the generator steps aside)."""
            if fb_srv.health():
                return
            for slots, ctx in [(cfg.judge_fallback.slots, cfg.judge_fallback.kv_tokens), (6, 24576), (4, 16384)]:
                fb_srv.slots, fb_srv.ctx_total = slots, ctx
                try:
                    fb_srv.start(lambda m: log(m, "dim"))
                    R.judge_fallback.workers = slots
                    R.judge_fallback._budget = int(ctx * 0.85)
                    ui.server(f"  fallback judge: {cfg.judge_fallback.name} ({slots} slots)")
                    return
                except RuntimeError:
                    log(f"  ! fallback judge did not fit with {slots} slots and a {ctx:,}-token KV pool", "warn")
            raise SystemExit(f"The fallback judge does not fit on the GPU (see {fb_srv.log_path}).")

        start_generator()
        records: list = []
        llm = LLM(gen, out / "cache", workers=cfg.generator.slots, log=log, ui=ui, records=records)
        R = Run(course, lectures, llm, gen, out, timer, log, args.seg_max_tokens, ui=ui, lir_dir=lir_dir)
        R.judge = LLM(judge_srv, out / "cache", workers=cfg.judge.slots, log=log, ui=ui, records=records)
        R.judge_fallback = (LLM(fb_srv, out / "cache", workers=cfg.judge_fallback.slots, log=log, ui=ui, records=records)
                            if fb_srv else None)
        R.start_fallback = start_fallback
        try:
            with timer.stage("stage1_segment"):
                s1_segment.run(R)
            with timer.stage("stage2_annotate"):
                s2_annotate.run(R)
            with timer.stage("stage3_goals"):
                s3_goals.run(R)
            with timer.stage("stage4_course_state"):
                s4_state.run(R)
            with timer.stage("stage5_generate"):
                s5_generate.run(R)
            with timer.stage("stage6_calibrate"):
                calibrate.generate_answers(R)
            if not args.no_judge:
                with timer.stage("stage6_judge"):
                    s6_judge.run(R, start_judge, start_generator)
            else:
                R.judge = None
        finally:
            if not args.keep_server:
                judge_srv.stop(force=True)
                if fb_srv:
                    fb_srv.stop(force=True)
                gen.stop(force=True)
                ui.server("  servers stopped")
        with timer.stage("stage7_assemble"):
            R.videos_expected = downloader is not None  # being downloaded now; otherwise link the files already there
            s7_assemble.run(R, media_dir)

        scoring = json.loads((lir_dir / f"{lectures[0].id}.json").read_text())["scoring"]["open_answer"]
        if downloader:
            if downloader.is_alive():
                log("\nWaiting for the video downloads to finish…", "video")
            downloader.join()
        extra = {"scoring": scoring,
                 "api": {"run_usd": round(ledger.run["usd"], 4), "total_usd": round(ledger.spent, 4),
                         "budget_usd": ledger.budget, "calls": ledger.run["calls"], "by_stage": ledger.run["by_stage"],
                         "unjudged": len(getattr(R, "unjudged", []))},
                 "videos": ({"done": downloader.done, "total": len(downloader.items), "failed": downloader.failed}
                            if downloader else None)}
        text = report.write(R, time.time() - t_start, extra)

    ui.console.print(text.split("## Per lecture")[0].strip().replace("**", ""))
    ui.log(f"\nLIR      → lir/{course.course_id}/  ({len(lectures)} lectures + course.json)", "ok")
    ui.log(f"Report   → output/{course.course_id}/timing_report.md", "ok")
    ui.log(f"\nReady to view:  cd {HERE} && python3 serve.py   →   http://localhost:8000", "stage")


if __name__ == "__main__":
    main()
