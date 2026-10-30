"""Course discovery and SRT -> cleaned, timestamped sentences."""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

MAX_WORDS = 50  # a stretch without sentence punctuation is cut at a cue boundary after this many words

TAG = re.compile(r"\[[^\]]{0,40}\]")                                  # [SQUEAKING], [INAUDIBLE], [student gives answer]
SPEAKER = re.compile(r"(?:(?<=^)|(?<=[.?!]\s))[A-Z][A-Z'\-]+(?: [A-Z][A-Z'\-]+)*:\s+")  # SARA BEERY:, AUDIENCE:
OCW = re.compile(r"Creative Commons license|MIT OpenCourseWare|ocw\.mit\.edu|make a donation", re.I)


@dataclass
class Sentence:
    id: int
    start: float
    end: float
    text: str


@dataclass
class LectureInput:
    lecture_id: str            # "L01", "L24b"
    index: int                 # 1-based position in the course
    number: str
    title: str
    srt: Path | None
    youtube_id: str = ""
    sentences: list[Sentence] = field(default_factory=list)
    txt: Path | None = None            # official transcript (used for alignment when there is no .srt)
    timing_source: str = "srt"         # "srt", or "aligned" (transcript words aligned to YouTube captions)

    @property
    def duration(self) -> float:
        return self.sentences[-1].end if self.sentences else 0.0


@dataclass
class CourseInput:
    course_id: str
    title: str
    source: str
    root: Path
    lectures: list[LectureInput]
    skipped: list[str]


def _num_key(n: str):
    m = re.match(r"(\d+)(.*)", n)
    return (int(m.group(1)), m.group(2)) if m else (10 ** 6, n)


def discover(root: Path, only: set[int] | None = None) -> CourseInput:
    """Read a dataset course folder (subs/, transcripts/, titles.tsv) and list its lectures in order."""
    root = root.resolve()
    tsv = root / "titles.tsv"
    if not tsv.exists():
        raise SystemExit(f"{root} is not a course folder: no titles.tsv (expected subs/, transcripts/, titles.tsv)")
    rows = [r for r in csv.DictReader(tsv.open(encoding="utf-8"), delimiter="\t") if r["type"] == "lecture"]
    rows.sort(key=lambda r: _num_key(r["number"]))

    title = root.name.replace("_", " ").title()
    for r in rows:  # transcript header line 1 is the course title
        txt = root / "transcripts" / f"{r['id']}.txt"
        if txt.exists():
            title = txt.read_text(encoding="utf-8").splitlines()[0].strip()
            break
    source = "mit" if root.name.startswith("mit_") else "nptel"

    lectures, skipped = [], []
    for i, r in enumerate(rows, 1):
        srt = root / "subs" / f"{r['id']}.srt"
        m = re.match(r"(\d+)(.*)", r["number"])
        lid = f"L{int(m.group(1)):02d}{m.group(2)}" if m else f"L{r['number']}"
        if only and i not in only and (not m or int(m.group(1)) not in only):
            continue
        txt = root / "transcripts" / f"{r['id']}.txt"
        if not srt.exists():
            if txt.exists() and r.get("youtube_id"):
                # no subtitles: timestamps come from aligning the transcript to YouTube's automatic captions
                lectures.append(LectureInput(lid, i, r["number"], r["title"], None, r["youtube_id"], txt=txt,
                                             timing_source="aligned"))
            else:
                skipped.append(f"{lid} ({r['id']}): no subtitle file and no transcript + video to align")
            continue
        lectures.append(LectureInput(lid, i, r["number"], r["title"], srt, r.get("youtube_id", ""), txt=txt))
    cid = root.name if root.name.startswith(source) else f"{source}-{root.name}"
    return CourseInput(cid.replace("_", "-"), title, source, root, lectures, skipped)


def _ts(s: str) -> float:
    h, m, rest = s.strip().replace(",", ".").split(":")
    return int(h) * 3600 + int(m) * 60 + float(rest)


def parse_srt(path: Path):
    cues = []
    for block in re.split(r"\n\s*\n", path.read_text(encoding="utf-8-sig").strip()):
        lines = block.strip().splitlines()
        i = next((k for k, l in enumerate(lines) if "-->" in l), None)
        if i is None:
            continue
        a, b = lines[i].split("-->")
        text = " ".join(l.strip() for l in lines[i + 1:]).strip()
        if text:
            cues.append((_ts(a), _ts(b), text))
    return cues


def clean(text: str) -> str:
    text = TAG.sub(" ", text)
    text = SPEAKER.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def load_sentences(srt: Path) -> list[Sentence]:
    """Merge cues into sentences: a cue that ends mid-sentence joins the next one."""
    out: list[Sentence] = []
    cur = None  # [start, end, text]
    for a, b, raw in parse_srt(srt):
        text = clean(raw)
        if not text:
            continue
        cur = [a, b, text] if cur is None else [cur[0], b, cur[2] + " " + text]
        if re.search(r"[.?!][\"')\]]*$", cur[2]) or len(cur[2].split()) >= MAX_WORDS:
            out.append(Sentence(len(out), round(cur[0], 3), round(cur[1], 3), cur[2]))
            cur = None
    if cur is not None:
        out.append(Sentence(len(out), round(cur[0], 3), round(cur[1], 3), cur[2]))
    # the OCW licence notice opens every MIT 9.00SC lecture; it is not part of the lecture
    while out and out[0].start < 60 and OCW.search(out[0].text):
        out.pop(0)
    return [Sentence(i, s.start, s.end, s.text) for i, s in enumerate(out)]


def numbered(sentences: list[Sentence], offset: int = 0) -> str:
    """Sentences as '[id] text' lines. IDs are the global sentence IDs (plus offset when 1-based)."""
    return "\n".join(f"[{s.id + offset}] {s.text}" for s in sentences)


def fmt_ts(t: float) -> str:
    h, rem = divmod(int(t), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
