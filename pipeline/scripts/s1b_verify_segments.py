"""Stage 1b: deterministic checks on the segmentation (code only), and the final segment maps.

    python scripts/s1b_verify_segments.py nptel_vr [--only 1-5]

The model's answer (stage 1a) is a list of segments in order, each {"start": number of its first sentence (from 1),
"subgoal": what the learner can do after it}.

Checks on the answer: a non-empty list; each item has an integer "start" and a non-empty "subgoal"; the first segment
starts at sentence 1; every start is within the lecture; starts strictly increase.
Checks on the segments built from it, each segment a set of sentences:
  1 exhaustive               every sentence belongs to some segment
  2 mutually exclusive       no sentence belongs to two segments
  3 contiguous and ordered   each segment is a run of consecutive sentences, following the previous segment
  4 non-empty                every segment has at least one sentence

Stage 1a runs check() on every answer and sends any problems back to the model to fix (up to its retries); answers that
pass the answer checks always pass 1-4, which are kept as a guard against bugs. This stage checks the saved answers
again and writes the segment maps.

Reads   output/<course>/stage_0a_preprocess/, output/<course>/stage_1a_segmentation/raw/lec_<n>.json
Writes  output/<course>/stage_1b_verify_segments/segment_maps/lec_<n>.json
            {"<n>/S0": {"first": "<n>/0", "last": "<n>/41", "start": 24.297, "end": 292.435, "duration_s": 268.138,
                        "subgoal": "Explain ..."}, ...}
        output/<course>/stage_1b_verify_segments/report.json   per lecture: ok, errors, attempts, errors fixed on retry
start is the first sentence's start and end the last sentence's end; null when that boundary is inside a subtitle cue
(see s0a_preprocess.py), and duration_s is then null too.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the pipeline folder


# ---------------------------------------------------------------------------- checks
def answer_errors(answer, n_sentences: int) -> list[str]:
    """Problems with the model's answer, worded for the model (sentence numbers from 1)."""
    if not isinstance(answer, list) or not answer:
        return ["The answer must be a non-empty JSON list of segments."]
    errors, prev = [], None
    for k, seg in enumerate(answer, 1):
        if not (isinstance(seg, dict) and isinstance(seg.get("start"), int) and not isinstance(seg.get("start"), bool)):
            errors.append(f'Segment {k} must be an object with an integer "start".')
            continue
        start = seg["start"]
        if not isinstance(seg.get("subgoal"), str) or not seg["subgoal"].strip():
            errors.append(f'Segment {k} (starting at sentence {start}) has no "subgoal".')
        if k == 1 and start != 1:
            errors.append(f"The first segment must start at sentence 1, not at sentence {start}.")
        if not 1 <= start <= n_sentences:
            errors.append(f"Segment {k} starts at sentence {start}, but the lecture has sentences 1 to {n_sentences}.")
        if prev is not None and start <= prev:
            errors.append(f"Segment {k} starts at sentence {start}, which is not after the start of segment {k - 1} "
                          f"(sentence {prev}): segments must be in order and each must start after the one before.")
        prev = start
    return errors


def build(answer: list, ids: list[str]) -> list[list[str]]:
    """The segments as lists of sentence IDs: each runs from its start to the sentence before the next start."""
    starts = [seg["start"] - 1 for seg in answer]
    ends = [s - 1 for s in starts[1:]] + [len(ids) - 1]
    return [ids[a:b + 1] for a, b in zip(starts, ends)]


def segment_errors(segments: list[list[str]], ids: list[str]) -> list[str]:
    """Checks 1-4 on the segments as sets of sentences (sentence numbers from 1 in the messages)."""
    pos = {s: i for i, s in enumerate(ids)}
    num = lambda s: pos[s] + 1  # noqa: E731
    errors = []
    seen: dict[str, int] = {}
    for k, seg in enumerate(segments, 1):
        if not seg:
            errors.append(f"Segment {k} has no sentences.")                                         # 4 non-empty
        for s in seg:
            if s in seen:
                errors.append(f"Sentence {num(s)} is in segment {seen[s]} and segment {k}.")       # 2 exclusive
            seen.setdefault(s, k)
        if seg and [pos[s] for s in seg] != list(range(pos[seg[0]], pos[seg[-1]] + 1)):
            errors.append(f"Segment {k} is not a run of consecutive sentences.")                   # 3 contiguous
    missing = [num(s) for s in ids if s not in seen]
    if missing:
        errors.append(f"Sentences {missing} are in no segment.")                                   # 1 exhaustive
    flat = [s for seg in segments for s in seg]
    if not errors and flat != ids:
        errors.append("The segments do not follow the order of the lecture.")                      # 3 ordered
    return errors


def check(answer, ids: list[str]) -> list[str]:
    """All checks on one answer; [] when it is fine."""
    errors = answer_errors(answer, len(ids))
    return errors or segment_errors(build(answer, ids), ids)


# ---------------------------------------------------------------------------- segment maps
def segment_map(n: int, answer: list, ids: list[str], times: dict) -> dict:
    out = {}
    for k, (seg, item) in enumerate(zip(build(answer, ids), answer)):
        start, end = times[seg[0]]["start"], times[seg[-1]]["end"]
        out[f"{n}/S{k}"] = {"first": seg[0], "last": seg[-1], "start": start, "end": end,
                            "duration_s": round(end - start, 3) if start is not None and end is not None else None,
                            "subgoal": item["subgoal"].strip()}
    return out


def run(course: str, lectures: list[int] | None = None) -> dict:
    s0 = ROOT / "output" / course / "stage_0a_preprocess"
    s1a = ROOT / "output" / course / "stage_1a_segmentation" / "raw"
    out = ROOT / "output" / course / "stage_1b_verify_segments"
    (out / "segment_maps").mkdir(parents=True, exist_ok=True)
    raws = sorted(s1a.glob("lec_*.json"), key=lambda p: int(p.stem.split("_")[1]))
    if lectures:
        raws = [p for p in raws if int(p.stem.split("_")[1]) in lectures]
    report, n_ok, n_seg = {}, 0, 0
    for p in raws:
        raw = json.loads(p.read_text())
        n = raw["lecture"]
        ids = list(json.loads((s0 / p.name).read_text()))
        times = json.loads((s0 / "times" / p.name).read_text())
        errors = check(raw["answer"], ids) if raw["ok"] else raw["errors"]
        entry = {"ok": not errors, "errors": errors, "attempts": raw["attempts"],
                 "fixed_on_retry": [h["errors"] for h in raw.get("history", [])]}
        if not errors:
            smap = segment_map(n, raw["answer"], ids, times)
            (out / "segment_maps" / p.name).write_text(json.dumps(smap, indent=1, ensure_ascii=False) + "\n")
            entry["segments"] = len(smap)
            n_ok += 1
            n_seg += len(smap)
        else:
            (out / "segment_maps" / p.name).unlink(missing_ok=True)
        report[f"lec_{n}"] = entry
    (out / "report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    failed = [k for k, v in report.items() if not v["ok"]]
    retried = [k for k, v in report.items() if v["fixed_on_retry"]]
    print(f"{n_ok}/{len(raws)} lectures pass, {n_seg} segments -> {out.relative_to(ROOT)}"
          + (f"; failed: {failed}" if failed else "") + (f"; fixed on retry: {retried}" if retried else ""))
    return {"lectures": len(raws), "ok": n_ok, "segments": n_seg, "failed": failed, "retried": retried}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("course")
    ap.add_argument("--only", help="lectures, e.g. 1-5,8")
    a = ap.parse_args()
    from scripts.s1a_segmentation import parse_only
    run(a.course, parse_only(a.only) if a.only else None)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT))
    main()
