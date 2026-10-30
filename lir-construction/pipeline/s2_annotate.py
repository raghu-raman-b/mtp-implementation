"""Stage 2: two narrow calls per segment: (1) sub-goal, content type, key points; (2) key terms."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from lir_schema import ContentType

from . import prompts as P
from . import validate as V
from .context import Lec, Run, Seg
from .llm import Call
from .transcript import numbered


class KP(BaseModel):
    text: str = Field(max_length=300)
    sentence_ids: list[int] = Field(min_length=1, max_length=8)
    about: Literal["subject", "course"]


class AnnA(BaseModel):
    subgoal: str = Field(max_length=160)
    content_type: ContentType
    key_points: list[KP] = Field(min_length=2, max_length=5)


class Term(BaseModel):
    term: str = Field(max_length=80)
    definition: str = Field(max_length=300)
    sentence_ids: list[int] = Field(min_length=1, max_length=6)


class AnnB(BaseModel):
    key_terms: list[Term] = Field(max_length=5)
    used_concepts: list[str] = Field(max_length=8)


def strip_ids(text: str) -> str:
    """The model sometimes copies sentence IDs into the text: 'is an umbrella term. [85, 88]'."""
    return re.sub(r"\s*\[\d+(?:\s*,\s*\d+)*\]", "", text).strip()


def prefix(R: Run, lec: Lec, seg: Seg) -> str:
    return P.segment_block(R.course.title, lec.inp.title, numbered(lec.sentences[seg.a:seg.b + 1]))


def _check_a(seg: Seg):
    def check(x: AnnA) -> list[str]:
        errs = V.check_verb_first(x.subgoal, "subgoal")
        for i, kp in enumerate(x.key_points, 1):
            errs += V.check_ids(kp.sentence_ids, seg.a, seg.b, f"key point {i}")
        return errs
    return check


def _bad_terms(lec: Lec, seg: Seg, x: AnnB) -> list[str]:
    errs = []
    for t in x.key_terms:
        e = V.check_ids(t.sentence_ids, seg.a, seg.b, f'term "{t.term}"')
        if not e:
            cited = " ".join(lec.sentences[i].text for i in t.sentence_ids)
            name = re.sub(r"\s*\([^)]*\)\s*$", "", t.term).strip()
            if not V.fuzzy_in(name, cited) and not V.fuzzy_in(t.term, cited):
                e = [f'term "{t.term}" does not occur in its cited sentences {t.sentence_ids}; cite the sentences '
                     f'where it is said, or leave it out']
            else:
                e = V.check_definition(t.term, t.definition, f'term "{t.term}"')
        errs += e
    return errs


def run(R: Run):
    calls = []
    for lec in R.lectures:
        for seg in lec.segments:
            pre = prefix(R, lec, seg)
            calls.append(Call(key=f"{lec.id}/{seg.id}/annotate", lecture_id=lec.id, prompt=pre + P.ANNOTATE[2],
                              schema=AnnA, prompt_id=P.ANNOTATE[0], prompt_version=P.ANNOTATE[1],
                              check=_check_a(seg), ctx={"seg": seg, "kind": "a"}))
            calls.append(Call(key=f"{lec.id}/{seg.id}/terms", lecture_id=lec.id, prompt=pre + P.TERMS[2],
                              schema=AnnB, prompt_id=P.TERMS[0], prompt_version=P.TERMS[1], required=False,
                              check=lambda x, lec=lec, seg=seg: _bad_terms(lec, seg, x), ctx={"seg": seg, "kind": "b"}))
    outs = R.llm.run("stage2_annotate", calls, "annotate segments")
    for o in outs:
        lec, seg = R.lec(o.call.lecture_id), o.call.ctx["seg"]
        R.record(o, "stage2_annotate", f"{lec.id}.{seg.id}.{'annotation' if o.call.ctx['kind'] == 'a' else 'terms'}")
        if o.call.ctx["kind"] == "a":
            x: AnnA | None = o.parsed
            if x is None:
                R.flag(lec.id, f"{seg.id}: annotation failed validation ({o.errors}); placeholder used")
                first = lec.sentences[seg.a]
                seg.subgoal, seg.content_type = f"Follow part {seg.id[1:]} of the lecture", "discussion"
                seg.key_points = [{"id": f"{seg.id}.K1", "text": first.text, "sentence_ids": [first.id], "about": "course"}]
                continue
            if not o.ok:
                R.flag(lec.id, f"{seg.id}: annotation kept despite failed checks: {o.errors}")
            seg.subgoal = x.subgoal.strip().rstrip(".")
            seg.subgoal = seg.subgoal[:1].upper() + seg.subgoal[1:]
            seg.content_type = x.content_type
            seg.key_points = [{"id": f"{seg.id}.K{i}", "text": strip_ids(kp.text), "about": kp.about,
                               "sentence_ids": sorted({j for j in kp.sentence_ids if seg.contains(j)}) or [seg.a]}
                              for i, kp in enumerate(x.key_points, 1)]
        else:
            x: AnnB | None = o.parsed
            if x is None:
                continue  # optional: the segment simply has no key terms
            terms = []
            for t in x.key_terms:  # after retries, drop the terms that still fail (optional items)
                if not _bad_terms(lec, seg, AnnB(key_terms=[t], used_concepts=[])):
                    terms.append({"term": V.display_name(t.term), "definition": strip_ids(t.definition),
                                  "sentence_ids": sorted(set(t.sentence_ids))})
            seg.key_terms = terms
            seg.used_concepts = [u.strip() for u in x.used_concepts if u.strip()]
    R.dump("stage2_annotations", {l.id: [{k: v for k, v in vars(s).items()} for s in l.segments] for l in R.lectures})
