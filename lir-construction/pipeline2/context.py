"""State shared by the steps of one v2.1 run: lectures and parts, the models, the decision log, the flow."""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pipeline.config import Config, Ledger
from pipeline.llm import LLM, Call, Outcome, Server
from pipeline.transcript import CourseInput, LectureInput, Sentence, numbered

from . import addr as A

# which model runs each step; lir2_config.toml [steps] overrides. The generator writes, the verifier decides what is
# the same and what is related, the judge checks every item (and rewrites the ones that fail, once).
DEFAULT_STEPS = {
    "parts": "generator", "annotate": "generator", "terms": "generator", "goals": "generator",
    "facets": "generator", "activities": "generator", "oq": "generator", "recall": "generator",
    "calibrate": "generator",
    "registry": "verifier", "links": "verifier",
    "judge": "judge",
}
# thinking budget per step, in tokens (vLLM ends the thinking with the server's think_end and the answer follows);
# lir2_config.toml [think] overrides
DEFAULT_THINK = {
    "parts": 8192, "annotate": 8192, "terms": 8192, "facets": 8192, "links": 8192, "activities": 8192, "oq": 8192,
    "judge": 4096, "registry": 4096, "goals": 4096, "recall": 4096, "calibrate": 4096,
}


@dataclass
class Part:
    id: str                     # "L05/P03"
    n: int                      # 1-based position in the lecture
    a: int                      # first sentence (inclusive)
    b: int                      # last sentence (inclusive)
    start: float
    end: float
    objective: str = ""
    objective_id: str = ""
    key_points: list[dict] = field(default_factory=list)   # {id, text, sentences: [int]}
    terms: list[dict] = field(default_factory=list)        # term occurrences, see s3_terms
    facets: list[dict] = field(default_factory=list)       # this part's facets (the same dicts as in the concepts)

    def contains(self, i: int) -> bool:
        return self.a <= i <= self.b


@dataclass
class Lecture:
    inp: LectureInput
    pos: int                    # 1-based position in the run (course order)
    parts: list[Part] = field(default_factory=list)
    objectives: list[dict] = field(default_factory=list)    # {id, text, part_ids}
    lecture_goal: str = ""
    links: list[dict] = field(default_factory=list)         # links found in this lecture (after its judge)
    flags: list[str] = field(default_factory=list)
    origin: list[dict] = field(default_factory=list)

    @property
    def id(self) -> str:
        return self.inp.lecture_id

    @property
    def sentences(self) -> list[Sentence]:
        return self.inp.sentences

    def s(self, i: int) -> str:
        return A.sent(self.id, i)

    def part(self, pid: str) -> Part:
        return next(p for p in self.parts if p.id == pid)

    def part_of(self, i: int) -> Part:
        return next((p for p in self.parts if p.contains(i)), self.parts[-1])

    def numbered(self, a: int, b: int) -> str:
        return numbered(self.sentences[a:b + 1])

    def text(self, ids) -> str:
        return " ".join(self.sentences[i].text for i in ids if 0 <= i < len(self.sentences))


class Decisions:
    """Every decision the pipeline makes about content: what, about which addresses, why, and from which call."""

    def __init__(self):
        self.items: list[dict] = []
        self._lock = threading.Lock()

    def add(self, step: str, subject, decision: str, reason: str = "", outcome: Outcome | None = None,
            model: str | None = None, **extra) -> str:
        with self._lock:
            did = f"D{len(self.items) + 1:05d}"
            rec = {"id": did, "step": step, "subject": subject if isinstance(subject, list) else [subject],
                   "decision": decision, "reason": reason}
            if outcome is not None:
                rec["call"] = {"key": outcome.call.key, "prompt_id": outcome.call.prompt_id,
                               "prompt_version": outcome.call.prompt_version, "input_hash": outcome.input_hash,
                               "model": model}
            rec.update(extra)
            self.items.append(rec)
            return did

    def write(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for r in sorted(self.items, key=lambda r: (str(r["subject"][:1]), r["step"], r["id"])):
                f.write(json.dumps(r, ensure_ascii=False) + "\n")


class Models:
    """One client per role (generator, verifier, judge). Roles that name the same model share one server, so one
    model for all three loads once. Without a [judge] section, the verifier judges."""

    def __init__(self, cfg: Config, out: Path, ledger: Ledger, log, ui, records: list,
                 slot_range: tuple[int, int] | None = None):
        self.cfg, self.log = cfg, log
        if cfg.verifier is None:
            raise SystemExit(f"{cfg.path} has no [verifier] model")
        specs = {"generator": cfg.generator, "verifier": cfg.verifier, "judge": cfg.judge or cfg.verifier}
        by_model: dict[str, tuple] = {}
        self.servers, self.llms = {}, {}
        for role, spec in specs.items():
            if spec.name not in by_model:
                srv = Server(spec, cfg, out / "logs", ledger)
                first, count = slot_range or (0, srv.slots)
                by_model[spec.name] = (srv, LLM(srv, out / "cache", workers=count, log=log, ui=ui, records=records,
                                                slot_offset=first))
                by_model[spec.name][1].calls_log = out / "calls.jsonl"
            self.servers[role], self.llms[role] = by_model[spec.name]
        self._lock = threading.Lock()

    def start_all(self):
        """Start every server one after another (two vLLM servers sharing a GPU must not profile memory at once)."""
        for srv in {id(s): s for s in self.servers.values()}.values():
            srv.start(lambda m: self.log(m, "dim"))

    def get(self, role: str) -> LLM:
        with self._lock:
            srv = self.servers[role]
            if not srv.health():
                srv.start(lambda m: self.log(m, "dim"))
            return self.llms[role]

    def stop_all(self):
        for srv in {id(s): s for s in self.servers.values()}.values():
            srv.stop(force=True)


@dataclass
class Run:
    course: CourseInput
    lectures: list[Lecture]
    cfg: Config
    models: Any
    out: Path
    timer: Any
    log: Any
    ui: Any = None
    seg_max_prompt_tokens: int = 28000
    decisions: Decisions = field(default_factory=Decisions)
    registry: Any = None                                   # s4_registry.Registry
    mentions: dict = field(default_factory=dict)           # (concept id, part id) -> sentence numbers naming it
    edges: list[dict] = field(default_factory=list)        # all links, merged across lectures (after the last judge)
    course_goals: list[dict] = field(default_factory=list)
    lecture_map: list[dict] = field(default_factory=list)
    course_origin: list[dict] = field(default_factory=list)
    counts: dict = field(default_factory=dict)
    acts: dict = field(default_factory=dict)               # lecture id -> activities (see pipeline2/act_*.py)
    scoring: dict = field(default_factory=dict)            # calibrated open-answer scorer settings
    flow: Any = None                                       # pipeline2.flow.Flow
    lock: Any = field(default_factory=threading.RLock)

    # -------------------------------------------------------------------------------------------- models
    def role(self, step: str) -> str:
        return self.cfg.steps.get(step, DEFAULT_STEPS[step])

    def llm(self, step: str) -> LLM:
        return self.models.get(self.role(step))

    def think(self, step: str) -> int | None:
        t = self.cfg.think.get(step, DEFAULT_THINK.get(step))
        return int(t) if t else None

    def send(self, step: str, call: Call, max_retries: int = 2) -> Outcome:
        """Send one call with the step's model and thinking budget; its origin is recorded on the lecture."""
        llm = self.llm(step)
        if call.think is None:
            call.think = self.think(step)
        o = llm.one(f"v2_{step}", call, max_retries)
        self.record(o, step, llm, call.key)
        return o

    def model_of(self, step: str) -> str:
        return self.llm(step).model

    # -------------------------------------------------------------------------------------------- lookups
    def lec(self, lid: str) -> Lecture:
        return next(l for l in self.lectures if l.id == lid)

    def pos(self, lid: str) -> int:
        return self.lec(lid).pos

    def order(self, address: str) -> tuple[int, int]:
        """Course order of a sentence address."""
        lid, i = A.parse_sent(address)
        return self.pos(lid), i

    def sentence(self, address: str) -> str:
        lid, i = A.parse_sent(address)
        return self.lec(lid).sentences[i].text

    # -------------------------------------------------------------------------------------------- records
    def record(self, o: Outcome, step: str, llm: LLM, item: str | None = None):
        p = o.origin(llm.model, llm.server.engine, step)
        if item:
            p["item"] = item
        with self.lock:
            if o.call.lecture_id == "_course":
                self.course_origin.append(p)
            else:
                self.lec(o.call.lecture_id).origin.append(p)

    def count(self, k: str, n: int = 1):
        with self.lock:
            self.counts[k] = self.counts.get(k, 0) + n

    def flag(self, lid: str, msg: str):
        with self.lock:
            self.lec(lid).flags.append(msg)
        self.log(f"  ! {lid}: {msg}", "warn")

    def dump(self, name: str, obj):
        d = self.out / "stages"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.json").write_text(json.dumps(obj, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
