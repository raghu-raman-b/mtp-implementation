"""Load a course's pipeline outputs into dicts for browsing in the notebook (read only, display only).

    from scripts.view import Course
    c = Course("nptel_vr")                  # loads every stage that has output
    c.sentences["1/0"]                      # 'Hello, welcome to the NPTEL MOOCs course on ...'
    c.times["1/0"]                          # {'start': 24.297, 'end': 31.884}
    c.segments["1/S0"]                      # shows as Markdown: header (sentences, time) and its sentences
    c.lecture(1)                            # shows as Markdown: a table of the lecture's segments
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the pipeline folder


def clock(t: float | None) -> str:
    """Seconds as m:ss (or h:mm:ss); '?' for a time inside a subtitle cue (null)."""
    if t is None:
        return "?"
    h, rem = divmod(int(round(t)), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class Markdown(str):
    """A string that the notebook shows as Markdown."""

    def _repr_markdown_(self):
        return str(self)


@dataclass
class Segment:
    id: str
    first: str
    last: str
    start: float | None
    end: float | None
    duration_s: float | None
    sentences: dict          # {sentence id: text}, in order
    subgoal: str = ""        # what the learner can do after the segment (from the model)
    estimated: list = None   # "start" / "end" when that time is estimated (a boundary inside a subtitle cue)

    def times(self) -> str:
        """start – end (duration); an estimated time has a ~ in front."""
        est = self.estimated or []
        s, e = ("~" if "start" in est else "") + clock(self.start), ("~" if "end" in est else "") + clock(self.end)
        return f"{s} – {e} ({'~' if est else ''}{clock(self.duration_s)})"

    @property
    def text(self) -> str:
        """The segment as plain text, one "[id] text" line per sentence (as in segments/lec_<n>/S<k>.txt)."""
        return "\n".join(f"[{i}] {s}" for i, s in self.sentences.items())

    def markdown(self) -> str:
        head = f"#### {self.id} · {self.first} – {self.last} ({len(self.sentences)} sentences) · {self.times()}"
        goal = f"\n\n*Sub-goal: {self.subgoal}*" if self.subgoal else ""
        return head + goal + "\n\n" + "\n".join(f"**`{i}`** {s}  " for i, s in self.sentences.items())

    def _repr_markdown_(self):
        return self.markdown()


class Course:
    """Everything one course has produced so far, keyed by ID.

    course     folder name under output/ (e.g. "nptel_vr")
    lectures   only these lecture numbers (default: all)
    root       the pipeline folder (default: this repo's)
    """

    def __init__(self, course: str, lectures: list[int] | None = None, root: Path = ROOT):
        self.course, self.root = course, Path(root)
        s0 = self.root / "output" / course / "stage_0a_preprocess"
        s1 = self.root / "output" / course / "stage_1b_verify_segments" / "segment_maps"
        from scripts import lectures as lec
        wanted = lec.normalize(lectures)
        keep = (lambda p: lec.key_of(p.stem) in wanted) if wanted else (lambda p: True)  # noqa: E731

        self.sentences: dict[str, str] = {}
        self.times: dict[str, dict] = {}
        for p in filter(keep, lec.files(s0)):
            self.sentences.update(json.loads(p.read_text()))
            t = s0 / "times" / p.name
            if t.exists():
                self.times.update(json.loads(t.read_text()))
        self.lectures = [lec.key_of(p.stem) for p in filter(keep, lec.files(s0))]   # keys: "7", "24b", "tut_1"

        self.segments: dict[str, Segment] = {}
        for p in filter(keep, lec.files(s1)) if s1.exists() else []:
            n = lec.key_of(p.stem)
            ids = [k for k in self.sentences if k.split("/")[0] == n]
            for sid, s in json.loads(p.read_text()).items():
                a, b = ids.index(s["first"]), ids.index(s["last"])
                self.segments[sid] = Segment(sid, s["first"], s["last"], s["start"], s["end"], s["duration_s"],
                                             {i: self.sentences[i] for i in ids[a:b + 1]}, s.get("subgoal", ""),
                                             s.get("estimated"))

    def segments_of(self, n: int) -> list[Segment]:
        return [s for k, s in self.segments.items() if k.split("/")[0] == str(n)]

    def lecture(self, n: int) -> Markdown:
        """A Markdown table of lecture n's segments: ID, sentences, time, duration, sub-goal."""
        segs = self.segments_of(n)
        n_sent = sum(1 for k in self.sentences if k.split("/")[0] == str(n))
        rows = [f"### Lecture {n}: {n_sent} sentences, {len(segs)} segments", "",
                "| Segment | Sentences | Time | Duration | Sub-goal (or first sentence) |", "|---|---|---|---|---|"]
        for s in segs:
            first = s.subgoal or next(iter(s.sentences.values()))
            first = first[:110] + ("…" if len(first) > 110 else "")
            t = s.times()
            rows.append(f"| {s.id} | {s.first} – {s.last} ({len(s.sentences)}) | {t.rsplit(' (', 1)[0]} "
                        f"| {t.rsplit(' (', 1)[1].rstrip(')')} | {first.replace('|', '/')} |")
        return Markdown("\n".join(rows))

    def __repr__(self):
        return (f"Course({self.course!r}: {len(self.lectures)} lectures, {len(self.sentences)} sentences, "
                f"{len(self.segments)} segments)")
