"""Ask every question of every system; one JSONL per system in baseline-tests/runs/.

    python3 baseline-tests/run_systems.py ours plain rag graphrag      # systems in this order, questions in order
    python3 baseline-tests/run_systems.py rag --ids C01 N05             # only some questions

Systems (all Gemma 4 12B on the same llama-server, same sampling: temperature 1.0, top_p 0.95, top_k 64):
- ours: qa.answer_stream as shipped (pipeline/qa, the viewer's streamed route): the tool loop over the knowledge
  layer, thinking in round 0 only. Context = the tool results the model saw (from qa's answers.jsonl log).
- plain: one call, the course title and the question, no course data.
- rag: one call, the 8 transcript chunks closest to the question (rag.py), labelled with lecture, title and time.
- graphrag: one call, a GraphRAG-style local search over graphrag/ (entities, relationships, community reports; no
  transcript text), each item with the lecture and time of the text units it came from.
rag and graphrag get the same lecture list our system's prompt has, and answer rules modelled on ours (cite after
each claim, say when the course does not cover it, a COVERED line).
Resumable: a question already in runs/<system>.jsonl is skipped.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

from chunks import lecture_titles
from common import COURSE_TITLE, OUT, PIPE, chat, fmt_time, log

RUNS = OUT / "runs"
RUNS.mkdir(exist_ok=True)
TITLES = lecture_titles()
LECTURE_LIST = "\n".join(f"{k}: {v}" for k, v in TITLES.items())

PLAIN_SYSTEM = (f'You are a teaching assistant for the online lecture course "{COURSE_TITLE}" (NPTEL). Answer the '
                "learner's question. Write for a learner: short and plain, two to five sentences, or a short list for "
                "kinds, parts or steps.")

GROUNDED_RULES = """HOW TO ANSWER
1. Use only what the {what} below say. Add nothing from your own knowledge: no facts, examples, numbers or explanations that they do not contain, even when you know them to be true.
2. After each claim, cite where it is taught as (lecture N, m:ss), using the lecture and time shown with the {item} it comes from. Every sentence about the subject needs at least one citation.
3. If the {what} do not answer the question, say plainly that the course does not cover it. You may then add, with citations, what the course says that is closest. Do not answer it from your own knowledge.
4. If they answer only part of the question, answer that part and say which part the course does not cover.
5. Write for a learner: short and plain, two to five sentences, or a short list for kinds, parts or steps. Use the course's own terms. Do not mention excerpts, entities, reports or searches.
6. End with one line on its own: "COVERED: yes" if the course answers the question, "COVERED: partly" if it answers part of it, "COVERED: no" if it does not.

THE LECTURES OF THE COURSE
{lectures}"""

RAG_SYSTEM = (f'You answer a learner\'s questions about the lecture course "{COURSE_TITLE}". You know nothing about '
              "this course except the transcript excerpts given with the question (the lecturer's words, each with its "
              "lecture and the time in the video where it starts).\n\n"
              + GROUNDED_RULES.format(what="excerpts", item="excerpt", lectures=LECTURE_LIST))

GRAPH_SYSTEM = (f'You answer a learner\'s questions about the lecture course "{COURSE_TITLE}". You know nothing about '
                "this course except the knowledge graph data given with the question: entities, relationships and "
                "community reports extracted from the lecture transcripts, each with the lectures and times it was "
                "taken from.\n\n"
                + GROUNDED_RULES.format(what="graph data", item="entity, relationship or report", lectures=LECTURE_LIST))


# ---------------------------------------------------------------- plain
def run_plain(q: str) -> dict:
    user = f'Course: "{COURSE_TITLE}"\n\nQuestion: {q}'
    r = chat(PLAIN_SYSTEM, user)
    return {"answer": r["content"], "context": {"system": PLAIN_SYSTEM, "user": user}, "model_calls": 1,
            "context_tokens": r["input_tokens"], "output_tokens": r["output_tokens"], "seconds": r["seconds"],
            "first_token_s": r["first_token_s"], "finish": r["finish"]}


# ---------------------------------------------------------------- rag
def run_rag(q: str) -> dict:
    import rag
    t0 = time.time()
    hits = rag.retrieve(q)
    t_ret = time.time() - t0
    blocks = []
    for n, c in enumerate(hits, 1):
        blocks.append(f'[Excerpt {n}] lecture {c["lecture"]} "{c["title"]}", from {fmt_time(c["start"])}:\n{c["text"]}')
    user = "Transcript excerpts:\n\n" + "\n\n".join(blocks) + f"\n\nQuestion: {q}"
    r = chat(RAG_SYSTEM, user)
    return {"answer": r["content"], "context": {"system": RAG_SYSTEM, "user": user},
            "retrieved": [{"id": c["id"], "lecture": c["lecture"], "start": c["start"], "score": c["score"]}
                          for c in hits],
            "model_calls": 1, "context_tokens": r["input_tokens"], "output_tokens": r["output_tokens"],
            "retrieval_s": round(t_ret, 2), "seconds": round(r["seconds"] + t_ret, 2),
            "first_token_s": round(r["first_token_s"] + t_ret, 2) if r["first_token_s"] is not None else None,
            "finish": r["finish"]}


# ---------------------------------------------------------------- graphrag (local search, graph only)
_G = None
GQ_INSTRUCTION = "Given a learner's question about a lecture course, retrieve the knowledge graph entities that answer it"
N_ENT, N_REL, N_REP = 12, 24, 4


def graph():
    global _G
    if _G is None:
        import rag   # its embedder (the same model)
        g = json.loads((OUT / "graphrag" / "graph.json").read_text())
        e = json.loads((OUT / "graphrag" / "embeddings.json").read_text())
        reps = {}
        for line in (OUT / "graphrag" / "community_reports.jsonl").open():
            x = json.loads(line)
            if x["report"]:
                reps[x["id"]] = x["report"]
        units = {}
        from graphrag_build import text_units
        for u in text_units():
            units[u["id"]] = u
        names = list(e["entities"])
        rids = list(e["reports"])
        _G = {"g": g, "units": units, "reps": reps, "names": names,
              "E": np.asarray([e["entities"][n] for n in names], dtype="float32"), "rids": rids,
              "R": np.asarray([e["reports"][r] for r in rids], dtype="float32"),
              "comm": {c["id"]: c for c in g["communities"]}, "emb": rag.embedder()}
    return _G


def src(G, unit_ids, n=3) -> str:
    us = sorted({u for u in unit_ids if u in G["units"]}, key=lambda u: (len(u), u))[:n]
    return "; ".join(f'lecture {G["units"][u]["lecture"]}, {fmt_time(G["units"][u]["start"])}' for u in us)


def graph_context(q: str) -> tuple[str, dict]:
    G = graph()
    qv = np.asarray(G["emb"].embed([q], instruction=GQ_INSTRUCTION)[0], dtype="float32")
    es = G["E"] @ qv
    top = [G["names"][i] for i in np.argsort(-es)[:N_ENT]]
    ents = G["g"]["entities"]
    rels = [r for r in G["g"]["relationships"] if r["source"] in top or r["target"] in top]
    rels = sorted(rels, key=lambda r: (-(r["source"] in top) - (r["target"] in top), -r["weight"]))[:N_REL]
    comms = {}
    for n in top:
        c = ents[n].get("community")
        if c and c in G["reps"]:
            comms[c] = comms.get(c, 0) + 1
    rs = G["R"] @ qv
    by_sim = [G["rids"][i] for i in np.argsort(-rs)[:N_REP]]
    chosen = list(dict.fromkeys(sorted(comms, key=lambda c: -comms[c])[:2] + by_sim))[:N_REP]
    parts = ["-----Entities-----", "entity | type | description | taught in"]
    for n in top:
        e = ents[n]
        parts.append(f'{n} | {e["type"]} | {e["description"][:500]} | {src(G, e["units"])}')
    parts += ["", "-----Relationships-----", "source | target | description | taught in"]
    for r in rels:
        parts.append(f'{r["source"]} | {r["target"]} | {r["description"][:300]} | {src(G, r["units"], 2)}')
    parts += ["", "-----Community reports-----"]
    for cid in chosen:
        rep = G["reps"][cid]
        lects = sorted({G["units"][u]["lecture"] for u in G["comm"][cid]["units"] if u in G["units"]},
                       key=lambda k: int(k) if k.isdigit() else 999)
        find = " ".join(f'{f.get("summary", "")}: {f.get("explanation", "")}' for f in rep.get("findings", [])[:4]
                        if isinstance(f, dict))
        parts.append(f'## {rep.get("title", cid)} (from lectures {", ".join(lects[:12])})\n{rep.get("summary", "")}\n'
                     f'{find[:1500]}')
    return "\n".join(parts), {"entities": top, "relationships": [r["id"] for r in rels], "reports": chosen}


def run_graphrag(q: str) -> dict:
    t0 = time.time()
    ctx, picked = graph_context(q)
    t_ret = time.time() - t0
    user = f"Knowledge graph data:\n\n{ctx}\n\nQuestion: {q}"
    r = chat(GRAPH_SYSTEM, user)
    return {"answer": r["content"], "context": {"system": GRAPH_SYSTEM, "user": user}, "retrieved": picked,
            "model_calls": 1, "context_tokens": r["input_tokens"], "output_tokens": r["output_tokens"],
            "retrieval_s": round(t_ret, 2), "seconds": round(r["seconds"] + t_ret, 2),
            "first_token_s": round(r["first_token_s"] + t_ret, 2) if r["first_token_s"] is not None else None,
            "finish": r["finish"]}


# ---------------------------------------------------------------- ours
def run_ours(q: str) -> dict:
    sys.path.insert(0, str(PIPE))
    os.chdir(PIPE)
    import qa
    from qa.knowledge import qa_dir
    log_path = qa_dir("nptel_vr") / "answers.jsonl"
    n0 = sum(1 for _ in log_path.open()) if log_path.exists() else 0
    t0 = time.time()
    first, res = None, None
    for ev in qa.answer_stream(q, course="nptel_vr"):
        if ev["event"] == "draft" and first is None:
            first = time.time() - t0
        if ev["event"] == "done":
            res = ev["result"]
    wall = time.time() - t0
    lines = log_path.open().read().splitlines()
    rec = json.loads(lines[-1]) if len(lines) > n0 else {}
    ctx = [{"tool": s["tool"], "args": s["args"], "result": s.get("result", "")} for s in rec.get("steps", [])]
    return {"answer": res["answer"], "covered": res["covered"], "citations": res["citations"],
            "steps": res["steps"], "raw_answer": rec.get("raw_answer"), "dropped_ids": rec.get("dropped_ids"),
            "context": {"tool_results": ctx}, "model_calls": len(rec.get("timing", [])),
            "context_tokens": rec.get("tokens", {}).get("input"), "output_tokens": rec.get("tokens", {}).get("output"),
            "timing": rec.get("timing"), "seconds": round(wall, 2),
            "first_token_s": round(first, 2) if first is not None else None, "error": res.get("error")}


def warm(system: str):
    """Load what each system loads once per process (embedders, indexes) before its timed questions, so that no
    system's first question pays a cold start (qa.warm is what the viewer's --warm does)."""
    if system == "ours":
        sys.path.insert(0, str(PIPE))
        os.chdir(PIPE)
        import qa
        qa.warm("nptel_vr")
    elif system == "rag":
        import rag
        rag.retrieve("warm up")
    elif system == "graphrag":
        graph_context("warm up")


RUN = {"ours": run_ours, "plain": run_plain, "rag": run_rag, "graphrag": run_graphrag}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("systems", nargs="+", choices=list(RUN))
    ap.add_argument("--ids", nargs="*")
    a = ap.parse_args()
    qs = [json.loads(x) for x in (OUT / "questions.jsonl").open()]
    if a.ids:
        qs = [q for q in qs if q["id"] in a.ids]
    for system in a.systems:
        warm(system)
        path = RUNS / f"{system}.jsonl"
        done = {json.loads(x)["id"] for x in path.open()} if path.exists() else set()
        for q in qs:
            if q["id"] in done:
                continue
            try:
                r = RUN[system](q["question"])
            except Exception as e:  # noqa: BLE001
                r = {"answer": "", "error": f"{type(e).__name__}: {e}"}
            rec = {"id": q["id"], "system": system, "category": q["category"], "question": q["question"], **r,
                   "time": round(time.time(), 1)}
            with path.open("a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            log(f"{system} {q['id']}: {r.get('seconds')} s, {r.get('context_tokens')} ctx tok, "
                f"{(r.get('answer') or '')[:90]!r}")


if __name__ == "__main__":
    main()
