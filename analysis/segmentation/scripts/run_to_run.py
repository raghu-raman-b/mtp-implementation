"""Run-to-run variability: the full segmentation pipeline (stage 1a + stage 1b with retries) on a sample of lectures,
once per seed, with everything else fixed (prompt, model, config, temperature 1.0).

    cd pipeline && python ../analysis/segmentation/scripts/run_to_run.py [--seeds 1,2,3] [--rebuild-main]

Seed 0 is the pipeline's own outputs (run 4, verified). --rebuild-main first re-runs stage 1b on the main outputs
(retries come from its cache) so that seed 0 uses the same code as the other seeds.

Each seed runs the pipeline's own stage code against a scratch root that links to the main inputs and stage 0a
outputs; its stage 1a and 1b outputs are copied to analysis/segmentation/data/runs/seed_<k>/.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import time
from pathlib import Path

PIPE = Path(__file__).resolve().parents[3] / "pipeline"
DATA = Path(__file__).resolve().parents[1] / "data" / "runs"
sys.path.insert(0, str(PIPE))

from scripts import course_meta, s1a_segmentation as s1a, s1b_verify_segments as s1b  # noqa: E402
from scripts.llm import LLM, LLMConfig  # noqa: E402

COURSE = "nptel_vr"
CONFIG = PIPE / "configs" / "gemma4_12b_llamacpp.json"
LECTURES = ["1", "4", "8", "14", "17", "18", "26", "36", "39", "45", "51", "57"]


def point_at(root: Path):
    for m in (s1a, s1b, course_meta):
        m.ROOT = root


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--rebuild-main", action="store_true")
    a = ap.parse_args()
    cfg = LLMConfig.load(CONFIG)
    with LLM(cfg) as llm:
        if a.rebuild_main:
            t0 = time.time()
            s1b.run(COURSE, llm=llm)
            print(f"main 1b rebuilt in {time.time() - t0:.0f} s", flush=True)
        for seed in [int(x) for x in a.seeds.split(",")]:
            t0 = time.time()
            llm.cfg = cfg.with_(seed=seed)            # the seed goes into every request body (and its cache key)
            root = Path(tempfile.mkdtemp(prefix=f"r2r_seed{seed}_"))
            (root / "input").mkdir()
            (root / "input" / COURSE).symlink_to(PIPE / "input" / COURSE)
            (root / "output" / COURSE).mkdir(parents=True)
            (root / "output" / COURSE / "stage_0a_preprocess").symlink_to(
                PIPE / "output" / COURSE / "stage_0a_preprocess")
            point_at(root)
            s1a.run(COURSE, llm, LECTURES)
            s1b.run(COURSE, LECTURES, llm=llm)
            point_at(PIPE)
            out = DATA / f"seed_{seed}"
            shutil.rmtree(out, ignore_errors=True)
            out.mkdir(parents=True)
            for stage in ("stage_1a_segmentation", "stage_1b_verify_segments"):
                shutil.copytree(root / "output" / COURSE / stage, out / stage)
            shutil.rmtree(root)
            print(f"seed {seed} done in {time.time() - t0:.0f} s -> {out}", flush=True)


if __name__ == "__main__":
    main()
