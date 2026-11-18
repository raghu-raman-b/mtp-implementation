"""Stage 0a: split each lecture's SRT into numbered sentences.

    python scripts/s0a_preprocess.py nptel_vr

Reads   input/<course>/input/subs/**/<stem>.srt   stem: lec_<n>[letter] or tut_<n>[_part<k>] (scripts/lectures.py)
Writes  output/<course>/stage_0a_preprocess/<stem>.json         {"<key>/0": "First sentence.", "<key>/1": ...}
        output/<course>/stage_0a_preprocess/times/<stem>.json   {"<key>/0": {"start": 24.567, "end": 30.033}, ...}
        output/<course>/stage_0a_preprocess/times/meta.json     speaking rate: {"wpm_median": ..., "lecture_wpm_median"}
        output/<course>/stage_0a_preprocess/times/cues/<stem>.json   the cue timeline, for stage 1b's estimates:
                                                  {"skip_words": 0, "cues": [[start, end, words], ...]}
The key is the lecture's name from its file: lec_7 -> 7, lec_24b -> 24b, tut_1 -> tut_1 (sentence IDs 7/0, 24b/0).

The cue text of a lecture is joined into one stream and split at sentence ends (. ? !), so a sentence that runs
across cues is kept whole and a cue holding several sentences is split. Sentence IDs run 0..n within a lecture.
A sentence end needs a capital, digit or opening quote after it: a lowercase word after a full stop does not start a
sentence (in the VR course it is a mid-sentence full stop: "...technologies. which, ..."; in MIT 18.06 a missed
capital: "OK. let's ..."; either way at worst two sentences stay one).

Caption conventions (MIT OpenCourseWare and others; a no-op where a course has none):
- Speaker labels ("PROFESSOR:", "AUDIENCE:", "PHILLIP ISOLA:", "A. STRANG:"): a turn always starts a new sentence;
  the label stays in front of it. A label is ALL-CAPS words with at least 4 letters, then a colon ("VR:" is not one).
- Sound tags ("[LAUGHTER]", "[CLICKING]"): removed; a cue left empty is dropped (its time stays a gap).
  "[INAUDIBLE]" is kept: it stands for words that were said.
- The OCW licence notice at the start of a lecture ("The following content is provided under a Creative Commons
  license. ... ocw.mit.edu."): its sentences are dropped.

Times come from the cues: a sentence that begins at the start of a cue gets that cue's start time, and one that ends
at the end of a cue gets that cue's end time. A boundary inside a cue has no time of its own and is null: a null start
means the sentence begins inside the cue where the previous sentence ends (whose end is null too).
The speaking rate is the median, over all cues of the course, of a cue's words per minute. With the cue timeline, stage
1b estimates the time of a segment boundary that falls inside a cue; sentences keep null.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the pipeline folder
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from scripts import lectures  # noqa: E402

TIMING = re.compile(r"^\d{1,2}:\d{2}:\d{2}[,.]\d{3}\s*-->")
TIME = re.compile(r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})")
TAG = re.compile(r"<[^>]+>")
SOUND = re.compile(r"\[(?!INAUDIBLE\])[A-Z][A-Z ]*\]")      # [LAUGHTER], [CLICKING]; not [INAUDIBLE]
# a sentence ends at . ? or ! (plus any closing quote or bracket), followed by space and a capital, digit or opening quote
END = re.compile(r"""(?<=[.?!])(["')\]]*)\s+(?=["'(\[]?[A-Z0-9])""")
# words whose full stop does not end a sentence (case-sensitive: "MR." in the VR course is Mixed Reality)
ABBREV = re.compile(r"\b(?:Dr|Prof|Mr|Mrs|Ms|vs|e\.g|i\.e|Fig|Eq)\.$")
# a speaker label: ALL-CAPS words (or initials like "A.") then a colon; at least 4 letters in all (checked in code)
LABEL = re.compile(r"(?<![\w'.])((?:[A-Z]\.|[A-Z][A-Z'-]+)(?: (?:[A-Z]\.|[A-Z][A-Z'-]+)){0,3}):(?=\s)")
NOTICE = re.compile(r"Creative Commons license|MIT OpenCourseWare|ocw\.mit\.edu|Your support will help|"
                    r"To make a donation", re.I)


def _secs(h: str, m: str, s: str, ms: str) -> float:
    return round(int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000, 3)


def parse_srt(srt: Path) -> list[tuple[float, float, str]]:
    """The cues of an SRT as (start, end, text), text with markup and sound tags removed and whitespace collapsed."""
    cues = []
    raw = srt.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    for block in re.split(r"\n\s*\n", raw.strip()):
        lines = [x.strip() for x in block.splitlines()]
        k = next((i for i, x in enumerate(lines) if TIMING.match(x)), None)
        if k is None:
            continue
        a, b = TIME.findall(lines[k])[:2]
        text = SOUND.sub(" ", html.unescape(TAG.sub("", " ".join(lines[k + 1:]))))
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            cues.append((_secs(*a), _secs(*b), text))
    return cues


def speaker_labels(text: str) -> list[int]:
    """Offsets where a speaker label starts."""
    return [m.start() for m in LABEL.finditer(text) if sum(c.isalpha() for c in m[1]) >= 4]


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """(start, end) character offsets of each sentence in text: split at sentence ends and before speaker labels."""
    cuts = {}                                    # start of the next sentence -> end of the previous one
    for m in END.finditer(text):
        if not ABBREV.search(text[:m.start()]):  # "Dr. Samit": not a sentence end
            cuts[m.end()] = m.end(1)             # keep a closing quote or bracket with its sentence
    for p in speaker_labels(text):
        if p > 0:
            cuts.setdefault(p, len(text[:p].rstrip()))
    spans, start = [], 0
    for nxt in sorted(cuts):
        spans.append((start, cuts[nxt]))
        start = nxt
    spans.append((start, len(text)))
    return [(a, b) for a, b in spans if text[a:b].strip()]


def split_lecture(srt: Path) -> tuple[list[str], list[dict], dict]:
    """Sentences of one lecture, their times ({"start", "end"}, null where the boundary is inside a cue), and the cue
    timeline {"skip_words": words dropped before the first sentence, "cues": [[start, end, words], ...]}: the
    sentences' words, in order, are the cues' words after skip_words (sentences split only at whitespace)."""
    cues = parse_srt(srt)
    cue_start, cue_end, pos = {}, {}, 0
    for a, b, t in cues:
        cue_start[pos], cue_end[pos + len(t)] = a, b
        pos += len(t) + 1  # cues are joined with one space
    text = " ".join(t for _, _, t in cues)
    spans = sentence_spans(text)
    skip = 0
    while spans and NOTICE.search(text[spans[0][0]:spans[0][1]]):   # the OCW licence notice at the start
        skip += len(text[spans[0][0]:spans[0][1]].split())
        spans.pop(0)
    timeline = {"skip_words": skip, "cues": [[a, b, len(t.split())] for a, b, t in cues]}
    return ([text[a:b] for a, b in spans], [{"start": cue_start.get(a), "end": cue_end.get(b)} for a, b in spans],
            timeline)


def cue_wpm(cues: list[tuple[float, float, str]]) -> list[float]:
    """Words per minute of each cue (cues with no duration are skipped)."""
    return [len(t.split()) / ((b - a) / 60) for a, b, t in cues if b > a]


def _median(xs: list[float]) -> float:
    xs = sorted(xs)
    m = len(xs) // 2
    return xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2


def _dump(path: Path, obj):
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def run(course: str, subs: Path | None = None, out_dir: Path | None = None) -> dict:
    """Preprocess every lecture and tutorial of a course; returns counts. subs and out_dir override the input folder
    (input/<course>/input/subs) and the output folder (output/<course>/stage_0a_preprocess), e.g. for a test."""
    subs = Path(subs) if subs else ROOT / "input" / course / "input" / "subs"
    try:
        srts = sorted(subs.rglob("*.srt"), key=lambda p: lectures.order(lectures.key_of(p.stem)))
    except ValueError as e:
        raise SystemExit(str(e))
    if not srts:
        raise SystemExit(f"no .srt files under {subs}")
    out_dir = Path(out_dir) if out_dir else ROOT / "output" / course / "stage_0a_preprocess"
    (out_dir / "times" / "cues").mkdir(parents=True, exist_ok=True)

    total = untimed = 0
    all_wpm, lec_wpm = [], {}
    for srt in srts:
        key = lectures.key_of(srt.stem)
        sents, times, timeline = split_lecture(srt)
        ids = [f"{key}/{i}" for i in range(len(sents))]
        _dump(out_dir / f"{srt.stem}.json", dict(zip(ids, sents)))
        _dump(out_dir / "times" / f"{srt.stem}.json", dict(zip(ids, times)))
        _dump(out_dir / "times" / "cues" / f"{srt.stem}.json", timeline)
        total += len(sents)
        untimed += sum(t["start"] is None or t["end"] is None for t in times)
        wpm = cue_wpm(parse_srt(srt))
        all_wpm += wpm
        lec_wpm[key] = round(_median(wpm), 1)
    meta = {"wpm_median": round(_median(all_wpm), 1), "cues": len(all_wpm),
            "method": "median over all cues of the course of (words in the cue) / (cue duration in minutes)",
            "used_for": "stage 1b estimates a segment boundary that falls inside a subtitle cue",
            "lecture_wpm_median": lec_wpm}
    _dump(out_dir / "times" / "meta.json", meta)
    shown = out_dir.relative_to(ROOT) if out_dir.is_relative_to(ROOT) else out_dir
    print(f"{len(srts)} lectures, {total} sentences ({untimed} with a boundary inside a cue), "
          f"median {meta['wpm_median']} words per minute -> {shown}")
    return {"lectures": len(srts), "sentences": total, "untimed": untimed, "wpm_median": meta["wpm_median"],
            "out": out_dir}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("course", help="course folder name under input/, e.g. nptel_vr")
    run(ap.parse_args().course)


if __name__ == "__main__":
    main()
