"""Ask every question of every system; one JSONL per system and run in baseline-tests/runs/.

    python3 baseline-tests/run_systems.py ours plain rag rag_think graphrag_text graphrag_notext abl_facts abl_graph
    python3 baseline-tests/run_systems.py rag --ids C01 N05                       # only some questions
    python3 baseline-tests/run_systems.py ours --run 2 --categories where formula # repeat 2 -> runs/ours_r2.jsonl

Systems (all Gemma 4 12B on the same llama-server, same sampling: temperature 1.0, top_p 0.95, top_k 64); see
README.md for each one's construction. Resumable: a question already in the run's file is skipped.
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
from common import CFG, COURSE_TITLE, OUT, PIPE, chat, fmt_time, log

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
def run_rag(q: str, think: bool = False) -> dict:
    import rag
    t0 = time.time()
    hits = rag.retrieve(q)
    t_ret = time.time() - t0
    blocks = []
    for n, c in enumerate(hits, 1):
        blocks.append(f'[Excerpt {n}] lecture {c["lecture"]} "{c["title"]}", from {fmt_time(c["start"])}:\n{c["text"]}')
    user = "Transcript excerpts:\n\n" + "\n\n".join(blocks) + f"\n\nQuestion: {q}"
    # thinking on: the server's --reasoning-budget (think_budget 8192, as ours' round 0) and the qa config's max_tokens
    r = chat(RAG_SYSTEM, user, think=True, max_tokens=CFG["max_tokens"]) if think else chat(RAG_SYSTEM, user)
    return {"answer": r["content"], "context": {"system": RAG_SYSTEM, "user": user},
            "reasoning_chars": r["reasoning_chars"],
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


# ---------------------------------------------------------------- graphrag local search with text units
# GraphRAG local search (graphrag 0.x defaults: max_tokens 12000, text_unit_prop 0.5, community_prop 0.25): the same
# entities / relationships / community reports as graphrag_notext, plus the source text units of the selected
# entities, ranked as GraphRAG ranks them (by the rank of the first selected entity that came from the unit, then by
# how many selected relationships came from it), added until they fill 50% of the 12000-token budget (6000 tokens,
# counted as characters / 4).
TU_BUDGET_TOKENS = 6000

GRAPH_TEXT_SYSTEM = (f'You answer a learner\'s questions about the lecture course "{COURSE_TITLE}". You know nothing '
                     "about this course except the data given with the question: entities, relationships and community "
                     "reports extracted from the lecture transcripts, and the transcript excerpts (the lecturer's words) "
                     "they were extracted from, each with its lecture and time.\n\n"
                     + GROUNDED_RULES.format(what="graph data and excerpts", item="entity, relationship, report or excerpt",
                                             lectures=LECTURE_LIST))


def graph_text_context(q: str) -> tuple[str, dict]:
    G = graph()
    ctx, picked = graph_context(q)
    ents = G["g"]["entities"]
    relunits = {}
    rel_by_id = {r["id"]: r for r in G["g"]["relationships"]}
    for rid in picked["relationships"]:
        for u in rel_by_id[rid]["units"]:
            relunits[u] = relunits.get(u, 0) + 1
    rank = {}
    for i, n in enumerate(picked["entities"]):
        for u in ents[n]["units"]:
            rank.setdefault(u, i)
    order = sorted(rank, key=lambda u: (rank[u], -relunits.get(u, 0)))
    blocks, used, chosen = [], 0, []
    for u in order:
        if u not in G["units"]:
            continue
        x = G["units"][u]
        b = f'[Excerpt {len(blocks) + 1}] lecture {x["lecture"]} "{x["title"]}", from {fmt_time(x["start"])}:\n{x["text"]}'
        t = len(b) // 4
        if used + t > TU_BUDGET_TOKENS:
            break
        blocks.append(b)
        used += t
        chosen.append(u)
    ctx += "\n\n-----Sources (transcript excerpts)-----\n" + "\n\n".join(blocks)
    return ctx, {**picked, "units": chosen}


def run_graphrag_text(q: str) -> dict:
    t0 = time.time()
    ctx, picked = graph_text_context(q)
    t_ret = time.time() - t0
    user = f"Knowledge graph data and transcript excerpts:\n\n{ctx}\n\nQuestion: {q}"
    r = chat(GRAPH_TEXT_SYSTEM, user)
    return {"answer": r["content"], "context": {"system": GRAPH_TEXT_SYSTEM, "user": user}, "retrieved": picked,
            "model_calls": 1, "context_tokens": r["input_tokens"], "output_tokens": r["output_tokens"],
            "retrieval_s": round(t_ret, 2), "seconds": round(r["seconds"] + t_ret, 2),
            "first_token_s": round(r["first_token_s"] + t_ret, 2) if r["first_token_s"] is not None else None,
            "finish": r["finish"]}


# ---------------------------------------------------------------- ablations of ours (tool subsets)
# The model is offered only these tools (qa.answer's tool_specs filtered); a call to any other tool gets qa's own
# "There is no tool ..." result. The system prompt and everything else in qa are unchanged.
ABLATIONS = {"abl_facts": ["fact_lookup"],
             "abl_graph": ["check_concept", "lecture_dependencies", "lecture_overview", "course_goals"]}


def restrict_tools(allowed: list[str] | None):
    sys.path.insert(0, str(PIPE))
    os.chdir(PIPE)
    import qa.answer  # noqa: F401
    # NOT "import qa.answer as qa_answer": qa/__init__.py re-exports the function `answer`, so that name binds the
    # function and the patches below would land on it silently (the first ablation runs were ours unchanged).
    qa_answer = sys.modules["qa.answer"]
    from qa import tools as qa_tools
    from qa.tools import ToolResult
    if allowed is None:
        qa_answer.tool_specs, qa_answer.run_tool = qa_tools.tool_specs, qa_tools.run_tool
        return
    qa_answer.tool_specs = lambda *a, **k: [t for t in qa_tools.tool_specs(*a, **k) if t["function"]["name"] in allowed]

    def run_tool(kb, name, args):
        if name not in allowed:
            return ToolResult(f"There is no tool {name!r}. The tools are: {', '.join(allowed)}.",
                              f"unknown tool {name}", label="A lookup went wrong; trying again",
                              detail={"error": f"unknown tool {name}"})
        return qa_tools.run_tool(kb, name, args)
    qa_answer.run_tool = run_tool


# ---------------------------------------------------------------- ours after the QA optimisation (T4, 2026-11-19)
# Same as ours (no tool restriction); ours_v2: thinking in the tool round (shipped mode), ours_v2_nothink: no round thinks.
V2 = {"ours_v2": True, "ours_v2_nothink": False}


# ---------------------------------------------------------------- ours
def run_ours(q: str, think: bool | None = None) -> dict:
    sys.path.insert(0, str(PIPE))
    os.chdir(PIPE)
    import qa
    from qa.knowledge import qa_dir
    log_path = qa_dir("nptel_vr") / "answers.jsonl"
    n0 = sum(1 for _ in log_path.open()) if log_path.exists() else 0
    t0 = time.time()
    first, res = None, None
    for ev in qa.answer_stream(q, course="nptel_vr", think=think):
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
            "first_token_s": round(first, 2) if first is not None else None, "error": res.get("error"),
            "think": rec.get("think", think)}


def warm(system: str):
    """Load what each system loads once per process (embedders, indexes) before its timed questions, so that no
    system's first question pays a cold start (qa.warm is what the viewer's --warm does)."""
    if system in V2:
        os.environ["QA_THINK"] = "1" if V2[system] else "0"   # qa.warm reads the mode from here
    if system == "ours" or system in V2:
        sys.path.insert(0, str(PIPE))
        os.chdir(PIPE)
        import qa
        qa.warm("nptel_vr")
    elif system == "rag":
        import rag
        rag.retrieve("warm up")
    elif system in ABLATIONS:
        restrict_tools(ABLATIONS[system])
        import qa
        qa.warm("nptel_vr")
    elif system == "rag_think":
        import rag
        rag.retrieve("warm up")
    elif system.startswith("graphrag"):
        graph_context("warm up")


RUN = {"ours": run_ours, "plain": run_plain, "rag": run_rag, "rag_think": lambda q: run_rag(q, think=True),
       "graphrag_notext": run_graphrag, "graphrag_text": run_graphrag_text,
       "abl_facts": run_ours, "abl_graph": run_ours,
       "ours_v2": lambda q: run_ours(q, think=True), "ours_v2_nothink": lambda q: run_ours(q, think=False)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("systems", nargs="+", choices=list(RUN))
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--categories", nargs="*")
    ap.add_argument("--run", type=int, default=1, help="repeat number: runs/<system>.jsonl for 1, <system>_r<N>.jsonl")
    a = ap.parse_args()
    qs = [json.loads(x) for x in (OUT / "questions.jsonl").open()]
    if a.ids:
        qs = [q for q in qs if q["id"] in a.ids]
    if a.categories:
        qs = [q for q in qs if q["category"] in a.categories]
    for system in a.systems:
        if system in ("ours",) or system in V2 or system in ABLATIONS:
            restrict_tools(ABLATIONS.get(system))
        warm(system)
        path = RUNS / (f"{system}.jsonl" if a.run == 1 else f"{system}_r{a.run}.jsonl")
        done = {json.loads(x)["id"] for x in path.open()} if path.exists() else set()
        for q in qs:
            if q["id"] in done:
                continue
            try:
                r = RUN[system](q["question"])
            except Exception as e:  # noqa: BLE001
                r = {"answer": "", "error": f"{type(e).__name__}: {e}"}
            rec = {"id": q["id"], "system": system, "run": a.run, "category": q["category"], "question": q["question"], **r,
                   "time": round(time.time(), 1)}
            with path.open("a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            log(f"{system} {q['id']}: {r.get('seconds')} s, {r.get('context_tokens')} ctx tok, "
                f"{(r.get('answer') or '')[:90]!r}")


if __name__ == "__main__":
    main()
