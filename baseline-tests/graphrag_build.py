"""A light GraphRAG index over the 63 lecture transcripts, built with Gemma 4 12B (the same server as every system).

    python3 baseline-tests/graphrag_build.py probe 6        # time 6 extraction calls (the estimate)
    python3 baseline-tests/graphrag_build.py extract        # resumable: graphrag/extractions.jsonl
    python3 baseline-tests/graphrag_build.py graph          # merge, communities, community reports, embeddings

What it follows from Microsoft GraphRAG's default indexing pipeline (graphrag 0.x "standard" method), and what it drops:
- text units: transcript chunks of ~600 tokens with ~60 overlap, within one lecture (GraphRAG default: 1200/100;
  smaller chunks because a 12B model extracts more reliably from shorter text, as the GraphRAG docs suggest);
- entity and relationship extraction per text unit with GraphRAG's tuple format and an adapted prompt (entity types
  for a lecture course instead of the default person/organization/geo/event); NO gleaning (GraphRAG default 1 extra
  round) to fit the time;
- entities merged by upper-cased name (as GraphRAG does); their descriptions are NOT summarised by the LLM (GraphRAG
  does); the distinct descriptions are kept (up to 4, the longest first);
- relationships merged by (source, target) pair, weights summed;
- communities: Louvain (networkx; GraphRAG uses hierarchical Leiden), one level, max size cut by re-running Louvain
  inside a community over 40 entities;
- community reports: one LLM call per community of 3+ entities (title, summary, findings), GraphRAG-style;
- entity and report embeddings with Qwen3-Embedding-0.6B on CPU (as RAG and the pipeline use).
Provenance: every entity, relationship and report keeps the text units it came from, so lecture and time can be shown.
"""
from __future__ import annotations

import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from chunks import chunks, lecture_titles
from common import COURSE_TITLE, OUT, PIPE, chat, log

sys.path.insert(0, str(PIPE))

G = OUT / "graphrag"
G.mkdir(exist_ok=True)
EXTRACT = G / "extractions.jsonl"
PARALLEL = 6            # all 6 server slots (the first 176 units ran with 3 while the server was shared)
TD, RD, CD = "<|>", "##", "<|COMPLETE|>"
TYPES = ["concept", "technology", "device", "method", "phenomenon", "person", "organization", "metric"]

EXTRACT_PROMPT = """-Goal-
Given a text document from a lecture of the course "{course}" and a list of entity types, identify all entities of those types from the text and all relationships among the identified entities.

-Steps-
1. Identify all entities. For each identified entity, extract the following information:
- entity_name: Name of the entity, capitalized
- entity_type: One of the following types: [{types}]
- entity_description: Comprehensive description of the entity's attributes and activities, as stated in the text
Format each entity as ("entity"{td}<entity_name>{td}<entity_type>{td}<entity_description>)

2. From the entities identified in step 1, identify all pairs of (source_entity, target_entity) that are *clearly related* to each other.
For each pair of related entities, extract the following information:
- source_entity: name of the source entity, as identified in step 1
- target_entity: name of the target entity, as identified in step 1
- relationship_description: explanation as to why you think the source entity and the target entity are related to each other
- relationship_strength: a numeric score indicating strength of the relationship between the source entity and target entity
Format each relationship as ("relationship"{td}<source_entity>{td}<target_entity>{td}<relationship_description>{td}<relationship_strength>)

3. Return output in English as a single list of all the entities and relationships identified in steps 1 and 2. Use **{rd}** as the list delimiter.

4. When finished, output {cd}

-Real Data-
######################
Entity_types: {types}
Text: {text}
######################
Output:"""

REPORT_PROMPT = """You are an AI assistant that helps a human analyst to perform general information discovery. Information discovery is the process of identifying and assessing relevant information associated with certain entities (e.g., concepts, technologies, methods) within a network.

# Goal
Write a comprehensive report of a community, given a list of entities that belong to the community as well as their relationships. The report will be used to inform decision-makers about information associated with the community. The content of this report includes an overview of the community's key entities, their technical meaning, and how they relate, as taught in the lecture course "{course}".

# Report Structure
- TITLE: community's name that represents its key entities - title should be short but specific.
- SUMMARY: An executive summary of the community's overall structure, how its entities are related to each other, and significant information associated with its entities.
- FINDINGS: A list of 3-6 key insights about the community. Each insight should have a short summary followed by an explanatory paragraph grounded in the data below.

Return output as a well-formed JSON-formatted string with the following format:
{{"title": <report_title>, "summary": <executive_summary>, "findings": [{{"summary": <insight_1_summary>, "explanation": <insight_1_explanation>}}, ...]}}

Do not include information where the supporting evidence for it is not provided.

# Data
Entities
id,entity,description
{entities}

Relationships
id,source,target,description
{relations}

Output:"""


def text_units():
    titles = lecture_titles()
    out = chunks(600, 60)
    for c in out:
        c["title"] = titles[c["lecture"]]
    return out


def parse_extraction(text: str) -> tuple[list, list]:
    ents, rels = [], []
    for rec in re.split(re.escape(RD) + r"|\n", text.replace(CD, "")):
        m = re.search(r"\((.*)\)", rec.strip())
        if not m:
            continue
        body = re.sub(r"<\|>|<\||\|>", "\x1f", m.group(1))       # the model writes <|>, <| or |> between fields
        parts = [q for q in (p.strip().strip("<>").strip().strip('"').strip() for p in body.split("\x1f")) if q]
        if not parts:
            continue
        if parts[0].lower() == "entity" and len(parts) >= 4:
            ents.append({"name": parts[1].upper(), "type": parts[2].lower(), "description": parts[3]})
        elif parts[0].lower() == "relationship" and len(parts) >= 5:
            try:
                w = float(re.findall(r"[\d.]+", parts[4])[0])
            except (IndexError, ValueError):
                w = 1.0
            rels.append({"source": parts[1].upper(), "target": parts[2].upper(), "description": parts[3], "weight": w})
    return ents, rels


def extract_one(u: dict) -> dict:
    prompt = EXTRACT_PROMPT.format(course=COURSE_TITLE, types=", ".join(TYPES), td=TD, rd=RD, cd=CD,
                                   text=f'(Lecture {u["lecture"]}: "{u["title"]}")\n{u["text"]}')
    r = chat("", prompt, think=False, max_tokens=4096)
    ents, rels = parse_extraction(r["content"])
    return {"unit": u["id"], "lecture": u["lecture"], "start": u["start"], "raw": r["content"], "entities": ents,
            "relationships": rels, "input_tokens": r["input_tokens"], "output_tokens": r["output_tokens"],
            "seconds": r["seconds"], "finish": r["finish"]}


def extract(limit: int | None = None, probe: bool = False):
    units = text_units()
    done = set()
    if EXTRACT.exists() and not probe:
        done = {json.loads(x)["unit"] for x in EXTRACT.open()}
    todo = [u for u in units if u["id"] not in done]
    if probe:      # spread over the course
        step = max(1, len(units) // (limit or 6))
        todo = units[::step][: limit or 6]
    elif limit:
        todo = todo[:limit]
    log(f"{len(units)} text units, {len(done)} done, {len(todo)} to do")
    t0, n, out_tok = time.time(), 0, 0
    with ThreadPoolExecutor(PARALLEL) as ex:
        for res in ex.map(extract_one, todo):
            n += 1
            out_tok += res["output_tokens"]
            if not probe:
                with EXTRACT.open("a") as f:
                    f.write(json.dumps(res, ensure_ascii=False) + "\n")
            el = time.time() - t0
            log(f"{n}/{len(todo)} {res['unit']}: {len(res['entities'])} ent, {len(res['relationships'])} rel, "
                f"{res['output_tokens']} tok, {res['seconds']} s; {el:.0f} s elapsed, eta "
                f"{el / n * (len(todo) - n) / 60:.1f} min")
    el = time.time() - t0
    if probe:
        log(f"PROBE: {n} units in {el:.1f} s with {PARALLEL} parallel; {out_tok / n:.0f} output tokens per unit; "
            f"estimated extraction for {len(units)} units: {el / n * len(units) / 60:.1f} min")


def build_graph():
    import networkx as nx
    recs = [json.loads(x) for x in EXTRACT.open()]
    units = {u["id"]: u for u in text_units()}
    ents, rels = {}, {}
    for r in recs:
        r["entities"], r["relationships"] = parse_extraction(r["raw"])     # re-parsed with the current parser
        for e in r["entities"]:
            if not e["name"]:
                continue
            x = ents.setdefault(e["name"], {"name": e["name"], "types": {}, "descriptions": [], "units": []})
            x["types"][e["type"]] = x["types"].get(e["type"], 0) + 1
            if e["description"] and e["description"] not in x["descriptions"]:
                x["descriptions"].append(e["description"])
            if r["unit"] not in x["units"]:
                x["units"].append(r["unit"])
        for rel in r["relationships"]:
            if not rel["source"] or not rel["target"] or rel["source"] == rel["target"]:
                continue
            key = tuple(sorted((rel["source"], rel["target"])))
            x = rels.setdefault(key, {"source": key[0], "target": key[1], "descriptions": [], "weight": 0.0,
                                      "units": []})
            x["weight"] += rel["weight"]
            if rel["description"] not in x["descriptions"]:
                x["descriptions"].append(rel["description"])
            if r["unit"] not in x["units"]:
                x["units"].append(r["unit"])
    for key in list(rels):          # a relationship's ends must be entities (GraphRAG adds them; we add bare ones)
        for n in key:
            if n not in ents:
                ents[n] = {"name": n, "types": {}, "descriptions": [], "units": list(rels[key]["units"])}
    for e in ents.values():
        e["type"] = max(e["types"], key=e["types"].get) if e["types"] else "unknown"
        e["description"] = " ".join(sorted(e["descriptions"], key=len, reverse=True)[:4])
        e["degree"] = 0
    gr = nx.Graph()
    gr.add_nodes_from(ents)
    for (a, b), r in rels.items():
        gr.add_edge(a, b, weight=r["weight"])
        ents[a]["degree"] += 1
        ents[b]["degree"] += 1
    comms = []
    for c in nx.community.louvain_communities(gr, weight="weight", seed=7):
        if len(c) > 40:
            sub = nx.community.louvain_communities(gr.subgraph(c), weight="weight", seed=7, resolution=2.0)
            comms += [set(s) for s in sub]
        else:
            comms.append(set(c))
    comms = [c for c in comms if len(c) >= 3]
    comm_of = {}
    for i, c in enumerate(comms):
        for n in c:
            comm_of[n] = f"K{i}"
    for e in ents.values():
        e["community"] = comm_of.get(e["name"])
    rel_list = []
    for i, r in enumerate(sorted(rels.values(), key=lambda r: -r["weight"])):
        r["id"] = f"R{i}"
        r["description"] = " ".join(r["descriptions"][:3])
        rel_list.append(r)
    communities = []
    for i, c in enumerate(comms):
        members = sorted(c, key=lambda n: -ents[n]["degree"])
        inside = [r for r in rel_list if r["source"] in c and r["target"] in c]
        u = sorted({x for n in members for x in ents[n]["units"]}, key=lambda x: (units[x]["lecture"], x))
        communities.append({"id": f"K{i}", "entities": members, "relationships": [r["id"] for r in inside],
                            "units": u})
    json.dump({"entities": ents, "relationships": rel_list, "communities": communities},
              (G / "graph.json").open("w"), ensure_ascii=False)
    log(f"graph: {len(ents)} entities, {len(rel_list)} relationships, {len(communities)} communities "
        f"(sizes {sorted((len(c['entities']) for c in communities), reverse=True)[:10]} ...)")
    return ents, rel_list, communities


def report_one(args):
    c, ents, relmap = args
    el = "\n".join(f'{n},{n},"{ents[n]["description"][:400]}"' for n in c["entities"][:40])
    rl = "\n".join(f'{rid},{relmap[rid]["source"]},{relmap[rid]["target"]},"{relmap[rid]["description"][:300]}"'
                   for rid in sorted(c["relationships"], key=lambda r: -relmap[r]["weight"])[:60])
    r = chat("", REPORT_PROMPT.format(course=COURSE_TITLE, entities=el, relations=rl or "(none)"), think=False,
             max_tokens=2048)
    txt = r["content"]
    m = re.search(r"\{.*\}", txt, re.S)
    try:
        rep = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        rep = {}
    return {"id": c["id"], "report": rep, "raw": txt if not rep else "", "output_tokens": r["output_tokens"],
            "seconds": r["seconds"]}


def reports():
    g = json.load((G / "graph.json").open())
    ents, relmap = g["entities"], {r["id"]: r for r in g["relationships"]}
    path = G / "community_reports.jsonl"
    done = {json.loads(x)["id"] for x in path.open()} if path.exists() else set()
    todo = [c for c in g["communities"] if c["id"] not in done]
    t0 = time.time()
    with ThreadPoolExecutor(PARALLEL) as ex:
        for n, res in enumerate(ex.map(report_one, [(c, ents, relmap) for c in todo]), 1):
            with path.open("a") as f:
                f.write(json.dumps(res, ensure_ascii=False) + "\n")
            log(f"report {n}/{len(todo)} {res['id']} {res['seconds']} s; {time.time() - t0:.0f} s elapsed")


def embed():
    from scripts.embed import Embedder
    g = json.load((G / "graph.json").open())
    reps = {json.loads(x)["id"]: json.loads(x)["report"] for x in (G / "community_reports.jsonl").open()}
    emb = Embedder("Qwen/Qwen3-Embedding-0.6B", cache=G / "embed_cache.jsonl", device="cpu")
    names = list(g["entities"])
    texts = [f'{n}: {g["entities"][n]["description"][:600]}' for n in names]
    ev = emb.embed(texts)
    rids = [k for k, v in reps.items() if v]
    rv = emb.embed([f'{reps[k].get("title", "")}: {reps[k].get("summary", "")}' for k in rids])
    json.dump({"entities": dict(zip(names, ev)), "reports": dict(zip(rids, rv))}, (G / "embeddings.json").open("w"))
    log(f"embedded {len(names)} entities, {len(rids)} reports")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "probe":
        extract(int(sys.argv[2]) if len(sys.argv) > 2 else 6, probe=True)
    elif cmd == "extract":
        extract(int(sys.argv[2]) if len(sys.argv) > 2 else None)
    elif cmd == "graph":
        build_graph()
        reports()
        embed()
    elif cmd == "reports":
        reports()
    elif cmd == "embed":
        embed()
