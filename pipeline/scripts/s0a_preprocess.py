"""Stage 0a: split each lecture's SRT into numbered sentences.

    python scripts/s0a_preprocess.py nptel_vr

Reads   input/<course>/input/subs/**/lec_<n>.srt
Writes  output/<course>/stage_0a_preprocess/lec_<n>.json         {"<n>/0": "First sentence.", "<n>/1": ...}
        output/<course>/stage_0a_preprocess/times/lec_<n>.json   {"<n>/0": {"start": 24.567, "end": 30.033}, ...}

The cue text of a lecture is joined into one stream and split at sentence ends (. ? !), so a sentence that runs
across cues is kept whole and a cue holding several sentences is split. Sentence IDs run 0..n within a lecture.

Times come from the cues: a sentence that begins at the start of a cue gets that cue's start time, and one that ends
at the end of a cue gets that cue's end time. A boundary inside a cue has no time of its own and is null: a null start
means the sentence begins inside the cue where the previous sentence ends (whose end is null too).
"""
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the pipeline folder

TIMING = re.compile(r"^\d{1,2}:\d{2}:\d{2}[,.]\d{3}\s*-->")
TIME = re.compile(r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})")
TAG = re.compile(r"<[^>]+>")
# a sentence ends at . ? or ! (plus any closing quote or bracket), followed by space and a capital, digit or opening quote
END = re.compile(r"""(?<=[.?!])(["')\]]*)\s+(?=["'(\[]?[A-Z0-9])""")
# words whose full stop does not end a sentence (case-sensitive: "MR." in this course is Mixed Reality)
ABBREV = re.compile(r"\b(?:Dr|Prof|Mr|Mrs|Ms|vs|e\.g|i\.e|Fig|Eq)\.$")


def _secs(h: str, m: str, s: str, ms: str) -> float:
    return round(int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000, 3)


def parse_srt(srt: Path) -> list[tuple[float, float, str]]:
    """The cues of an SRT as (start, end, text), text with tags removed and whitespace collapsed."""
    cues = []
    raw = srt.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    for block in re.split(r"\n\s*\n", raw.strip()):
        lines = [x.strip() for x in block.splitlines()]
        k = next((i for i, x in enumerate(lines) if TIMING.match(x)), None)
        if k is None:
            continue
        a, b = TIME.findall(lines[k])[:2]
        text = re.sub(r"\s+", " ", html.unescape(TAG.sub("", " ".join(lines[k + 1:])))).strip()
        if text:
            cues.append((_secs(*a), _secs(*b), text))
    return cues


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """(start, end) character offsets of each sentence in text."""
    spans, start = [], 0
    for m in END.finditer(text):
        if ABBREV.search(text[:m.start()]):
            continue  # "Dr. Samit": not a sentence end
        spans.append((start, m.end(1)))  # keep a closing quote or bracket with its sentence
        start = m.end()
    if start < len(text):
        spans.append((start, len(text)))
    return [(a, b) for a, b in spans if text[a:b].strip()]


def split_lecture(srt: Path) -> tuple[list[str], list[dict]]:
    """Sentences of one lecture and their times ({"start", "end"}, null where the boundary is inside a cue)."""
    cues = parse_srt(srt)
    cue_start, cue_end, pos = {}, {}, 0
    for a, b, t in cues:
        cue_start[pos], cue_end[pos + len(t)] = a, b
        pos += len(t) + 1  # cues are joined with one space
    text = " ".join(t for _, _, t in cues)
    spans = sentence_spans(text)
    return [text[a:b] for a, b in spans], [{"start": cue_start.get(a), "end": cue_end.get(b)} for a, b in spans]


def lecture_number(srt: Path) -> int:
    m = re.fullmatch(r"lec_(\d+)", srt.stem)
    if not m:
        raise SystemExit(f"unexpected subtitle file name (want lec_<n>.srt): {srt}")
    return int(m.group(1))


def _dump(path: Path, obj):
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def run(course: str) -> dict:
    """Preprocess every lecture of a course; returns counts."""
    subs = ROOT / "input" / course / "input" / "subs"
    srts = sorted(subs.rglob("*.srt"), key=lecture_number)
    if not srts:
        raise SystemExit(f"no .srt files under {subs}")
    out_dir = ROOT / "output" / course / "stage_0a_preprocess"
    (out_dir / "times").mkdir(parents=True, exist_ok=True)

    total = untimed = 0
    for srt in srts:
        n = lecture_number(srt)
        sents, times = split_lecture(srt)
        ids = [f"{n}/{i}" for i in range(len(sents))]
        _dump(out_dir / f"lec_{n}.json", dict(zip(ids, sents)))
        _dump(out_dir / "times" / f"lec_{n}.json", dict(zip(ids, times)))
        total += len(sents)
        untimed += sum(t["start"] is None or t["end"] is None for t in times)
    print(f"{len(srts)} lectures, {total} sentences ({untimed} with a boundary inside a cue) "
          f"-> {out_dir.relative_to(ROOT)}")
    return {"lectures": len(srts), "sentences": total, "untimed": untimed, "out": out_dir}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("course", help="course folder name under input/, e.g. nptel_vr")
    run(ap.parse_args().course)


if __name__ == "__main__":
    main()
