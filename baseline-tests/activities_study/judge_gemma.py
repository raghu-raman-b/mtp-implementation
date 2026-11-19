"""GPU: our pipeline's activity judges (prompts/activity_judge_<kind>.txt, s5's judge_items / judge_request /
judge_round, one round, no rewrite) on ours, B1 and B2, with the study's model (Gemma 4 12B).

    python3 judge_gemma.py [--systems ours b1 b2] [--lectures 2 18]

The judge sees what the writer saw (s5 rebuilds ours' units from the layer: the facts, sub-goal, related material;
B2's units: the numbered transcript and "(not given)"/"(none)") and the items numbered as the learner sees them.
B1 cites nothing, so each B1 item is shown citing the transcript window the overlap rule finds for it (study.overlap
of its key text: the correct option, the point, the reference answer, the reason, the steps), on B2's blocks. Ours'
recap point facts come from the writer's cached answer (the point texts matched); a point not matched cites the
activity's facts. Writes out/judge/gemma.jsonl: one line per unit {system, lecture, kind, unit, round}.
Resumable through the answer cache (a rerun sends only what is missing).
"""
from __future__ import annotations

import argparse
import copy
import json

import study as st
from study import s5

LAYER = None
KEYTEXT = {"quiz": lambda q: q["options"][q["answer"]], "open_question": lambda q: q["reference_answer"],
           "odd_one_out": lambda it: it["reason"], "put_in_order": lambda it: " ".join(it["steps"])}


def layer():
    global LAYER
    LAYER = LAYER or s5.Layer(st.DATA / "knowledge")
    return LAYER


CACHES = {"ours": [st.DATA / d / "llm" / "cache.jsonl" for d in ("activities_local", "activities")],
          "ours_gemma": [st.OUT / "gen" / "ours_gemma" / "llm" / "cache.jsonl"]}


def recap_point_facts(u, a, caches) -> tuple[list, int]:
    """Ours / ours_gemma: the facts of each point of the recap activity, from the writer's cached answers of the
    unit (its first answer, retries and the rewrite)."""
    sid, by = u.segment, {}
    for p in caches:
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if f'"recap:{sid}"' not in line:
                continue
            rec = json.loads(line)
            if rec.get("key") not in (f"recap:{sid}", f"rewrite:recap:{sid}"):
                continue
            try:
                ans = json.loads(rec["content"])
            except (ValueError, TypeError):
                continue
            for pt in ans.get("points", []) if isinstance(ans, dict) else []:
                if isinstance(pt, dict):
                    by.setdefault(s5.norm(s5.strip_stop(s5.txt(pt.get("point")))), s5.ids_of(pt.get("facts"),
                                                                                               u.ctx["shown"]))
    out = [by.get(s5.norm(s5.strip_stop(p))) for p in a["data"]["points"]]
    return [x if x else a["facts"] for x in out], sum(1 for x in out if x)


def units(system: str, k: str):
    """(unit, acts, conv) per judged unit of the system in lecture k."""
    acts = st.activities(system, k)
    out = []
    if system in st.LAYERED:
        L = layer()
        for kind in st.JUDGED:
            mine = [a for a in acts if a["kind"] == kind]
            if not mine:
                continue
            if kind in ("quiz", "recap"):
                for a in mine:
                    u = s5.UNITS[kind](L, st.COURSE, k, a["segment"], None)
                    conv = {}
                    if kind == "recap":
                        pf, matched = recap_point_facts(u, a, CACHES[system])
                        conv = {"point_facts": pf, "matched": matched}
                    out.append((u, [a], conv))
            else:
                out.append((s5.LECTURE_UNITS[kind](L, st.COURSE, k, None), mine, {}))
    else:
        info = st.gen_info(system, k)
        for kind in st.JUDGED:
            mine = [a for a in acts if a["kind"] == kind]
            if not mine:
                continue
            u = st.b2_unit(kind, k)
            conv = {"point_facts": (info.get(kind) or {}).get("point_facts")} if kind == "recap" else {}
            if system == "b1":
                mine = copy.deepcopy(mine)
                for a in mine:
                    if kind == "recap":
                        conv = {"point_facts": [st.overlap(p, k)[1] for p in a["data"]["points"]]}
                    for it in st.items_of(kind, a["data"]) if kind != "recap" else []:
                        it["key_facts" if kind == "open_question" else "facts"] = st.overlap(KEYTEXT[kind](it), k)[1]
            out.append((u, mine, conv))
    for u, _, _ in out:
        u.key = u.key if u.key.startswith(f"{system}:") else f"{system}:{u.key}"
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--systems", nargs="*", default=list(st.SYSTEMS))
    ap.add_argument("--lectures", nargs="*")
    a = ap.parse_args()
    keys = a.lectures or st.sample()
    jobs = []
    for system in a.systems:
        for k in keys:
            for u, acts, conv in units(system, k):
                items = s5.judge_items(u, acts, conv, None)
                if not items:
                    continue
                req = s5.judge_request(u, items, 1, None)
                req.max_tokens = st.GEN_MAX_TOKENS
                jobs.append((system, k, u, items, conv, req))
    llm = st.make_llm()
    print(f"judge: {len(jobs)} calls ({', '.join(a.systems)}; lectures {' '.join(keys)})", flush=True)
    results = llm.generate_many([j[-1] for j in jobs], **st.cache_files())
    path = st.OUT / "judge" / "gemma.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    old = [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []
    new = {}
    for (system, k, u, items, conv, _), res in zip(jobs, results):
        rec = {"system": system, "lecture": k, "kind": u.kind, "unit": u.key, "segment": u.segment,
               "round": s5.judge_round(res, items)}
        if "matched" in conv:
            rec["recap_points_matched"] = f'{conv["matched"]}/{len(conv["point_facts"])}'
        new[u.key] = rec
    keep = [r for r in old if r["unit"] not in new]
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in keep + list(new.values())))
    print(f"judge: done; {sum(r['round'].get('status') != 'ok' for r in new.values())} units not ok", flush=True)


if __name__ == "__main__":
    main()
