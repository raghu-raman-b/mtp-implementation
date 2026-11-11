"""Stage 1c: one text file per segment, from the segment maps of stage 1b.

    python scripts/s1c_segment_texts.py nptel_vr [--only 1-5]

Reads   output/<course>/stage_0a_preprocess/lec_<n>.json
        output/<course>/stage_1b_verify_segments/segment_maps/lec_<n>.json
Writes  output/<course>/stage_1c_segment_texts/<stem>/S<k>.txt   one line per sentence: "[<key>/<i>] text"
        (<stem>: the lecture's file name, lec_7 or tut_1; <key>: 7 or tut_1; see scripts/lectures.py)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the pipeline folder
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from scripts import lectures as lec  # noqa: E402


def segment_lines(sentences: dict, seg: dict) -> list[str]:
    """The "[id] text" lines of one segment (seg: an entry of a segment map)."""
    ids = list(sentences)
    a, b = ids.index(seg["first"]), ids.index(seg["last"])
    return [f"[{i}] {sentences[i]}" for i in ids[a:b + 1]]


def write(course: str, lectures: list | None = None) -> int:
    """Write the segment files of the lectures (all that have a segment map by default); returns the file count."""
    s0 = ROOT / "output" / course / "stage_0a_preprocess"
    maps_dir = ROOT / "output" / course / "stage_1b_verify_segments" / "segment_maps"
    out_root = ROOT / "output" / course / "stage_1c_segment_texts"
    maps = lec.files(maps_dir)
    if lectures:
        keep = lec.normalize(lectures)
        maps = [p for p in maps if lec.key_of(p.stem) in keep]
    count = 0
    for mp in maps:
        sentences = json.loads((s0 / mp.name).read_text())
        out = out_root / mp.stem
        out.mkdir(parents=True, exist_ok=True)
        for old in out.glob("S*.txt"):   # a re-run may have fewer segments
            old.unlink()
        for seg_id, seg in json.loads(mp.read_text()).items():
            (out / f"{seg_id.split('/')[1]}.txt").write_text("\n".join(segment_lines(sentences, seg)) + "\n")
            count += 1
    print(f"{count} segment files for {len(maps)} lectures -> {out_root.relative_to(ROOT)}")
    return count


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("course")
    ap.add_argument("--only", help="lectures, e.g. 1-5,8,24b,tut_1")
    a = ap.parse_args()
    write(a.course, lec.parse_only(a.only) if a.only else None)


if __name__ == "__main__":
    main()
