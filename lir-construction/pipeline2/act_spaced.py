"""Spaced review after each part, with intervals that double.

A concept counts as tested when a quiz item or an open question is tagged with it (recall and check-yourself
questions do not count). Each tested concept keeps a gap, in lectures: 1 after its first test, doubled each time it is
tested when due (1, 2, 4, 8, ...). It is due in lecture k when k - (lecture it was last tested) >= gap. A concept is
counted at most once per lecture, so one tested after part 2 is not due again after part 5.

After each part, the candidates are the earlier concepts the part teaches something about (a facet that is not "only
mentioned": it must be related to the part, never a random one) that are due. Ranked: concepts that a concept
introduced in this part depends on first, then the most overdue, then the longest untested. For each candidate, the
earlier quiz item on it (multiple choice, true/false, yes/no; already judged) used least so far, then the oldest.
Up to MAX_CANDIDATES per part are stored; the first DEFAULT are the default schedule, and only those count as tested.
A renderer that knows the learner's answers can choose differently from the candidates.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from .assemble import _public
from .context import Run

MAX_CANDIDATES, DEFAULT = 4, 2


def _tested(state: dict, cid: str, pos: int):
    st = state.get(cid)
    if st is None:
        state[cid] = {"last": pos, "gap": 1}
    elif st["last"] != pos:
        if pos - st["last"] >= st["gap"]:
            st["gap"] *= 2
        st["last"] = pos


def run(R: Run):
    C = R.registry.concepts
    lid_at = {l.pos: l.id for l in R.lectures}
    state: dict[str, dict] = {}                   # concept -> {last: lecture position, gap: lectures}
    uses: Counter = Counter()                     # item id -> times used as spaced review
    pool: dict[str, list] = defaultdict(list)     # concept -> [(lecture position, quiz item)] from earlier lectures
    for lec in R.lectures:
        k = lec.pos
        for p in lec.parts:
            pa = R.acts[lec.id]["parts"][p.id]
            for it in pa["quiz"]:
                for cid in it["concept_ids"]:
                    _tested(state, cid, k)
            here = {t["concept_id"] for t in p.terms}
            needed = {e["dst"] for e in R.edges if e["rel"] == "depends_on" and e["src"] in here}
            due = []
            for c in C.values():
                if c.intro_pos >= k or not pool[c.id]:
                    continue
                facet = next((f for f in c.facets if f["part"] == p.id and not f["only_mentioned"]), None)
                st = state.get(c.id)
                if facet is None or st is None or k - st["last"] < st["gap"]:
                    continue
                due.append((c, facet, dict(st), k - st["last"] - st["gap"]))
            due.sort(key=lambda t: (t[0].id not in needed, -t[3], t[2]["last"]))
            cands = []
            for n, (c, facet, st, _) in enumerate(due[:MAX_CANDIDATES]):
                pos, item = min(pool[c.id], key=lambda t: (uses[t[1]["id"]], t[0]))
                default = n < DEFAULT
                if default:
                    uses[item["id"]] += 1
                    _tested(state, c.id, k)
                cands.append({"concept_id": c.id, "from_lecture": lid_at[pos], "item": _public(item), "default": default,
                              "last_tested": lid_at[st["last"]], "gap": st["gap"],
                              "reason": f"{c.name} comes back in this part ({facet['says']}); last tested in "
                                        f"{lid_at[st['last']]}, due after {st['gap']} lecture(s)"
                                        + ("; a concept introduced here depends on it" if c.id in needed else "")})
            pa["spaced_review"] = cands
            if cands:
                R.decisions.add("spaced_review", [p.id], f"{sum(x['default'] for x in cands)} default, "
                                f"{len(cands)} candidate(s)", "; ".join(x["reason"] for x in cands),
                                items=[x["item"]["id"] for x in cands])
            R.count("spaced_review_default", sum(x["default"] for x in cands))
            R.count("spaced_review_candidates", len(cands))
        for q in R.acts[lec.id]["open_questions"]:
            for cid in q["concept_ids"]:
                _tested(state, cid, k)
        for p in lec.parts:  # this lecture's quiz items can be reused from the next lecture on
            for it in R.acts[lec.id]["parts"][p.id]["quiz"]:
                for cid in it["concept_ids"]:
                    pool[cid].append((k, it))
