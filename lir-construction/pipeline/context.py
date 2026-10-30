"""State shared by the stages of one run: the course, per-lecture working data, timing, origin."""
from __future__ import annotations

import json
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .llm import LLM, Outcome, Server
from .transcript import CourseInput, LectureInput, Sentence


@dataclass
class Seg:
    id: str
    a: int                      # first sentence ID (inclusive)
    b: int                      # last sentence ID (inclusive)
    start: float
    end: float
    flags: list[str] = field(default_factory=list)
    subgoal: str = ""
    content_type: str = "discussion"
    key_points: list[dict] = field(default_factory=list)      # {id, text, sentence_ids}
    key_terms: list[dict] = field(default_factory=list)       # {term, definition, sentence_ids, concept_id}
    used_concepts: list[str] = field(default_factory=list)
    concept_ids: list[str] = field(default_factory=list)
    objective_id: str = ""

    def contains(self, sid: int) -> bool:
        return self.a <= sid <= self.b


@dataclass
class Lec:
    inp: LectureInput
    segments: list[Seg] = field(default_factory=list)
    lecture_goal: str = ""
    objectives: list[dict] = field(default_factory=list)      # {id, text, segment_ids}
    phases: list[dict] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    origin: list[dict] = field(default_factory=list)
    quality: dict = field(default_factory=dict)               # layer-3 judge results for this lecture

    @property
    def id(self) -> str:
        return self.inp.lecture_id

    @property
    def sentences(self) -> list[Sentence]:
        return self.inp.sentences

    def seg(self, sid: str) -> Seg:
        return next(s for s in self.segments if s.id == sid)

    def seg_of_sentence(self, sentence_id: int) -> Seg:
        return next((s for s in self.segments if s.contains(sentence_id)), self.segments[-1])


class Timer:
    def __init__(self, ui=None):
        self.stages: list[dict] = []   # {stage, start, end, wall_s}
        self.ui = ui

    @contextmanager
    def stage(self, name: str, log=None):
        t0 = time.time()
        if self.ui:
            self.ui.start_stage(name)
        yield
        t1 = time.time()
        self.stages.append({"stage": name, "start": t0, "end": t1, "wall_s": t1 - t0})
        if self.ui:
            self.ui.end_stage(name, t1 - t0)


@dataclass
class Run:
    course: CourseInput
    lectures: list[Lec]
    llm: LLM
    server: Server
    out: Path
    timer: Timer
    log: Any
    seg_max_prompt_tokens: int
    ui: Any = None
    judge: Any = None              # LLM client for the layer-3 judge
    lir_dir: Path | None = None    # where the final LIR files go
    calibration_answers: list = field(default_factory=list)
    state: Any = None              # CourseState, set by stage 4
    course_goals: list[dict] = field(default_factory=list)
    course_origin: list[dict] = field(default_factory=list)

    def lec(self, lid: str) -> Lec:
        return next(l for l in self.lectures if l.id == lid)

    def record(self, o: Outcome, stage: str, item: str | None = None, llm: LLM | None = None):
        """Store origin for an LLM outcome on its lecture (or the course)."""
        llm = llm or self.llm
        p = o.origin(llm.model, llm.server.engine, stage)
        if item:
            p["item"] = item
        if o.call.lecture_id == "_course":
            self.course_origin.append(p)
        else:
            self.lec(o.call.lecture_id).origin.append(p)

    def flag(self, lid: str, msg: str):
        self.lec(lid).flags.append(msg)
        self.log(f"  ! {lid}: {msg}", "warn") if self.ui else self.log(f"  ! {lid}: {msg}")

    def dump(self, name: str, obj):
        d = self.out / "stages"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.json").write_text(json.dumps(obj, indent=1, ensure_ascii=False, default=str), encoding="utf-8")


def intent(principle, icap, bloom, rule_id, rationale, sources=()) -> dict:
    return {"principle": list(principle) if isinstance(principle, (list, tuple)) else [principle],
            "icap_mode": icap, "bloom_level": bloom, "rule_id": rule_id, "rationale": rationale,
            "sources": sorted(set(int(s) for s in sources))}
