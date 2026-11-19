"""GPU: the baselines' activities for the sample. One call per system, lecture and kind, all sent at once.

    python3 generate.py [--systems b1 b2] [--lectures 2 18] [--kinds quiz recap]

Writes out/gen/<system>/lec_<n>.json: {"lecture", "activities": [contract of pipeline/schemas/activities.md],
"units": {kind: {"status", "retry", "dropped", "flags", "point_facts"}}}. B2 goes through s5's own code checks with
retry (feedback) and s5's convert functions (option shuffle, drops of items with a hard problem, report flags); B1 is
one plain call per kind (schema-constrained JSON, parse retries only) taken as it is. Resumable: answers are cached
by request hash in out/llm/cache.jsonl, so a rerun sends only what is missing.
"""
from __future__ import annotations

import argparse
import json

import study as st
from study import s5


def convert_b1(kind: str, d: dict) -> tuple[list[dict], dict]:
    """B1's answer is already the contract's data; facts are empty (B1 cites nothing)."""
    if kind in ("quiz", "odd_one_out", "put_in_order", "open_question", "recall"):
        for it in st.items_of(kind, d):
            it.setdefault("key_facts" if kind == "open_question" else "facts", [])
            if kind == "open_question":
                it.setdefault("concepts", [])
    data = d
    if kind == "concept_map":
        ids = {n["id"] for n in d.get("nodes", [])}
        data = {"nodes": d.get("nodes", []), "edges": [e for e in d.get("edges", [])]}
        bad = [i for i, e in enumerate(data["edges"]) if e.get("from") not in ids or e.get("to") not in ids]
        return [act(kind, data)], {"edges_with_unknown_node": bad} if bad else {}
    return [act(kind, data)], {}


def act(kind: str, data: dict, facts=None) -> dict:
    return {"kind": kind, "scope": "lecture", "segment": None, "title": s5.TITLES[kind], "data": data,
            "facts": facts or [], "concepts": []}


def convert_b2_cited(kind: str, d: dict, shown: list[str]) -> tuple[list[dict], dict]:
    """B2's concept_map and recall: B1's form plus sentence numbers, mapped to sentence IDs."""
    data = json.loads(json.dumps(d))
    for it in data.get("edges" if kind == "concept_map" else "items", []):
        it["facts"] = s5.ids_of(it.get("facts"), shown)
    acts, flags = convert_b1(kind, data)
    acts[0]["facts"] = list(dict.fromkeys(f for it in st.items_of(kind, acts[0]["data"]) for f in it["facts"]))
    return acts, flags


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--systems", nargs="*", default=["ours_gemma", "b1", "b2"])
    ap.add_argument("--lectures", nargs="*")
    ap.add_argument("--kinds", nargs="*", default=list(st.KINDS))
    a = ap.parse_args()
    keys = a.lectures or st.sample()
    if "ours_gemma" in a.systems:
        # our own stage (s5) on the same model as the baselines, from the layer: code checks with retry, no judge
        # (the baselines get no judge either). Its cache: out/gen/ours_gemma/llm/cache.jsonl (resumable).
        kinds = [x for x in a.kinds if x in st.KINDS_OF["ours_gemma"]]
        print(f"generate: ours_gemma via s5 ({', '.join(kinds)}; lectures {' '.join(keys)})", flush=True)
        with st.make_llm() as llm:
            s5.run(st.COURSE, llm, only=list(keys), kinds=kinds, out=st.OUT / "gen" / "ours_gemma")
        a.systems = [s for s in a.systems if s != "ours_gemma"]
        if not a.systems:
            return
    jobs = []                                    # (system, lecture, kind, unit or None, request)
    for k in keys:
        for kind in a.kinds:
            if "b1" in a.systems:
                jobs.append(("b1", k, kind, None, st.b1_request(kind, k)))
            if "b2" in a.systems:
                u = st.b2_unit(kind, k)
                jobs.append(("b2", k, kind, u, u.request))
    llm = st.make_llm(concurrency=4)
    print(f"generate: {len(jobs)} calls ({', '.join(a.systems)}; lectures {' '.join(keys)})", flush=True)
    results = llm.generate_many([j[4] for j in jobs], **st.cache_files())
    files: dict[tuple, dict] = {}
    for (system, k, kind, u, _), res in zip(jobs, results):
        path = st.OUT / "gen" / system / f"{st.lec.stem_of(k)}.json"
        f = files.setdefault((system, k), json.loads(path.read_text()) if path.exists()
                             else {"lecture": k, "activities": [], "units": {}})
        f["activities"] = [x for x in f["activities"] if x["kind"] != kind]
        info = {"status": "ok" if res.ok else ("unresolved" if s5.s4a.answered(res) else "no_answer"),
                "attempts": res.attempts, "finish": res.finish}
        if res.history:
            info["retry"] = [h["errors"] for h in res.history]
        if not res.ok:
            info["problems"] = res.errors
        acts = []
        if s5.s4a.answered(res):
            if system == "b1":
                acts, flags = convert_b1(kind, res.parsed)
            elif kind in ("concept_map", "recall"):
                acts, flags = convert_b2_cited(kind, res.parsed, u.ctx["shown"])
            else:
                acts, dropped, flags = s5.CONVERT[kind](res.parsed, u.ctx, st.TLayer(k), u)
                for x in acts:                   # the whole lecture is the baseline's unit
                    x.update(scope="lecture", segment=None)
                info["dropped"] = dropped
                info["point_facts"] = u.ctx.get("_conv", {}).get("point_facts")
            info["flags"] = flags
        f["activities"] += [{"id": f"{k}/{system}:{kind}:{i}", "kind": kind, "title": s5.TITLES[kind],
                             **{f_: v for f_, v in x.items() if f_ not in ("kind", "title", "id")}}
                            for i, x in enumerate(acts)]
        f["units"][kind] = info
    for (system, k), f in files.items():
        path = st.OUT / "gen" / system / f"{st.lec.stem_of(k)}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(f, indent=1, ensure_ascii=False))
    bad = [(s, k, kind) for s, k, kind, _, _ in jobs if files[(s, k)]["units"][kind]["status"] == "no_answer"]
    print(f"generate: done; no answer: {bad or 'none'}", flush=True)


if __name__ == "__main__":
    main()
