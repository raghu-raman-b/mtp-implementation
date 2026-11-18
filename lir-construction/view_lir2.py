#!/usr/bin/env python3
"""Serve the v2 viewer (viewer2/) over one or more LIR v2 builds, for reading a course and evaluating it by hand.

    python3 view_lir2.py                                   # every v2 build under runs/
    python3 view_lir2.py runs/v2-20261103-0755/small       # one run setup
    python3 view_lir2.py path/to/<course>/lir --port 9000  # one LIR folder
    then open http://localhost:8001  (add ?dev=1 for dev mode: answers, sources, judge verdicts, hand-eval marks)

A build is any folder that holds lir/course.json (runs/<run>/<setup>/<course>/lir/...). Each one shows up as a course
in the viewer's course list. Videos come from media/<course_id>/Lxx.mp4 (the same files as the v1 viewer).

Endpoints
    GET  /lir2/index.json             the builds found
    GET  /lir2/<key>/<file>.json      LIR files of a build (course.json, Lxx.json, activities/Lxx.json)
    GET  /api/dev?c=<key>&l=<Lxx>     judge verdicts and other decisions for each item of a lecture, its links, and the
                                      decisions not tied to a shown item (dropped key points, questions, ...)
    GET  /api/concept?c=<key>&id=<C>  a concept's facets with their judge verdicts, and its registry decision
    GET  /api/eval?c=<key>            hand-eval marks;  POST /api/eval {c, item, verdict, note, ...}  saves one
    POST /api/score, /api/cmap        open-answer and concept-map scoring (same scorer as serve.py)

Hand-eval marks are kept in <build>/hand_eval.json (next to lir/ and build/), so they stay with the run.
"""
import os
import sys
from pathlib import Path

try:
    import numpy as np
except ImportError:  # run in the project venv (numpy, sentence-transformers), like serve.py
    venv_py = Path(__file__).resolve().parent.parent / "bin/python"
    if venv_py.exists() and Path(sys.executable).resolve() != venv_py.resolve():
        os.execv(str(venv_py), [str(venv_py), __file__, *sys.argv[1:]])
    raise

import argparse
import json
import re
import threading
import time
from collections import defaultdict
from functools import lru_cache
from http import HTTPStatus
from urllib.parse import parse_qs, urlparse

import serve  # noqa: E402  (the scorer, the CPU embedder and the file/video handler)

HERE = serve.HERE
scorer = serve.scorer
BUILDS: dict[str, Path] = {}      # key -> the build's lir/ folder
_eval_lock = threading.Lock()


# ------------------------------------------------------------------ builds
def find_builds(roots: list[Path]) -> dict[str, Path]:
    found = []
    for root in roots:
        root = root.resolve()
        if (root / "course.json").is_file():
            found.append(root)
        elif (root / "lir" / "course.json").is_file():
            found.append(root / "lir")
        else:
            found += sorted(p.parent for p in root.glob("**/lir/course.json") if ".venv" not in p.parts)
    out = {}
    for lir in found:
        try:
            rel = lir.parent.relative_to(HERE)
        except ValueError:
            rel = Path(*lir.parent.parts[-3:])
        key = re.sub(r"[^\w.-]+", "~", str(rel)).strip("~") or "build"
        out[key] = lir
    return out


def build_dir(key: str) -> Path:
    if key not in BUILDS:
        raise KeyError(f"unknown build {key}")
    return BUILDS[key]


@lru_cache(maxsize=512)
def load(key: str, name: str) -> dict:
    if not re.fullmatch(r"(activities/)?[\w.-]+", name):
        raise ValueError("bad name")
    return json.loads((build_dir(key) / f"{name}.json").read_text(encoding="utf-8"))


def index() -> dict:
    courses = []
    for key, lir in BUILDS.items():
        c = load(key, "course")
        parts = key.split("~")
        label = " · ".join(p for p in parts[-3:-1] if p not in ("runs",)) or key
        courses.append({"key": key, "course_id": c["course_id"], "title": c["title"], "label": label,
                        "lir_version": c.get("lir_version")})
    return {"courses": courses}


# ------------------------------------------------------------------ decisions
def _scope(call_key: str) -> str:
    """'L16/P01/annotate/judge' -> 'L16/P01'; 'L16/recall/judge' -> 'L16'."""
    p = call_key.split("/")
    return f"{p[0]}/{p[1]}" if len(p) > 1 and re.fullmatch(r"P\d+", p[1]) else p[0]


def _lecture_of(d: dict):
    if d.get("call") and d["call"].get("key"):
        lid = d["call"]["key"].split("/")[0]
        if re.fullmatch(r"L\d+", lid):
            return lid
    for s in d.get("subject") or []:
        m = re.match(r"(L\d+)(/|$)", s)
        if m:
            return m.group(1)
    return None


def _slim(d: dict) -> dict:
    out = {k: v for k, v in d.items() if k != "call"}
    if d.get("call"):
        out["prompt"] = f"{d['call'].get('prompt_id')} v{d['call'].get('prompt_version')}"
        out["model"] = (d["call"].get("model") or "").split(" (")[0].split("/")[-1]
        out["call_key"] = d["call"].get("key")
    return out


@lru_cache(maxsize=8)
def decisions(key: str) -> dict:
    path = build_dir(key) / "decisions.jsonl"
    D = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []
    judged = defaultdict(list)            # (kind, scope, sorted subject) -> judge decisions
    by_lecture = defaultdict(list)
    link_judge = defaultdict(list)        # lecture -> judge decisions on links
    link_other = defaultdict(list)        # frozenset(pair) -> links-step decisions (dropped, flipped, conflict)
    registry = {}
    quiz_intent = defaultdict(list)       # (part, "type on Kn") -> quiz-step decision
    for d in D:
        kind, step = d.get("kind"), d.get("step")
        if step == "judge" and d.get("call") and kind != "link":
            judged[(kind, _scope(d["call"]["key"]), tuple(sorted(d.get("subject") or [])))].append(d)
        if kind == "link" and d.get("call"):
            link_judge[d["call"]["key"].split("/")[0]].append(d)
            continue
        if step == "links":
            link_other[frozenset(d.get("subject") or [])].append(d)
            continue
        if step == "registry":
            registry[d.get("concept")] = d
            continue
        if step == "quiz" and (d.get("subject") or [None])[0]:
            quiz_intent[(d["subject"][0], d["decision"])].append(d)
        lid = _lecture_of(d)
        if lid:
            by_lecture[lid].append(d)
    return {"judged": judged, "by_lecture": by_lecture, "link_judge": link_judge, "link_other": link_other,
            "registry": registry, "quiz_intent": quiz_intent}


def lecture_dev(key: str, lid: str) -> dict:
    X = decisions(key)
    L, A, C = load(key, lid), load(key, f"activities/{lid}"), load(key, "course")
    items, used = {}, set()

    def attach(item_id, kind, scope, subject, extra=()):
        ds = list(X["judged"].get((kind, scope, tuple(sorted(subject))), [])) + list(extra)
        if ds:
            items[item_id] = [_slim(d) for d in ds]
            used.update(d["id"] for d in ds)

    attach(f"{lid}/goal", "lecture_goal", lid, [lid])
    for o in L["objectives"]:
        attach(o["id"], "lecture_objective", lid, [o["id"]])
    for p in L["parts"]:
        attach(f"{p['id']}/objective", "part_objective", p["id"], [p["id"]])
        for k in p["key_points"]:
            attach(k["id"], "key_point", p["id"], k["sources"])
        for t in p["terms"]:
            attach(t["id"], "key_term", p["id"], t["sources"])
    for pa in A["parts"]:
        pid = pa["part_id"]
        for q in pa["quiz"]:
            attach(q["id"], "quiz", pid, q["sources"], X["quiz_intent"].get((pid, f"{q['type']} on {q.get('key_point')}"), []))
        for v in pa["review"]:
            attach(v["id"], "review", pid, v["sources"])
        if pa.get("recap"):
            attach(f"{pid}/recap", "recap", pid, [pid])
    for r in A["recall"]:
        attach(r["id"], "recall", lid, r["sources"])
    for q in A["open_questions"]:
        attach(q["id"], "open_question", lid, [s for k in q["key_points"] for s in k["sources"]])
    # the rest: what was dropped or decided about this lecture without a shown item (facets go with their concept)
    rest = [_slim(d) for d in X["by_lecture"].get(lid, [])
            if d["id"] not in used and d.get("kind") != "facet" and not (d.get("step") == "terms" and d.get("decision") == "kept")]
    # links whose evidence is in this lecture: kept edges and the ones the judge or the code dropped
    edges = {frozenset((e["src"], e["dst"])): e for e in C["edges"] if e["lecture_id"] == lid}
    pairs = defaultdict(list)
    for d in X["link_judge"].get(lid, []):
        pairs[frozenset(d.get("subject") or [])].append(d)
    for k in edges:
        pairs.setdefault(k, [])
    names = {c["id"]: c["name"] for c in C["concepts"]}
    links = []
    for k, ds in pairs.items():
        e = edges.get(k)
        other = [d for d in X["link_other"].get(k, [])]
        ab = [e["src"], e["dst"]] if e else (ds[0].get("subject") if ds else sorted(k))
        links.append({"id": e["id"] if e else "link:" + "-".join(sorted(k)), "pair": ab,
                      "names": [names.get(x, x) for x in ab], "edge": e,
                      "decisions": [_slim(d) for d in ds + other]})
    links.sort(key=lambda x: (x["edge"] is None, x["id"]))
    for x in links:
        if x["edge"] and x["decisions"]:
            items[x["id"]] = x["decisions"]
    return {"items": items, "rest": rest, "links": links}


def concept_dev(key: str, cid: str) -> dict:
    X = decisions(key)
    C = load(key, "course")
    c = next(x for x in C["concepts"] if x["id"] == cid)
    facets = []
    for f in c["facets"]:
        ds = X["judged"].get(("facet", f["part"], tuple(sorted(f["sentences"]))), []) if f["sentences"] else []
        facets.append({**f, "decisions": [_slim(d) for d in ds]})
    reg = X["registry"].get(cid)
    return {"facets": facets, "registry": _slim(reg) if reg else None}


# ------------------------------------------------------------------ hand eval
def eval_path(key: str) -> Path:
    return build_dir(key).parent / "hand_eval.json"


def eval_load(key: str) -> dict:
    p = eval_path(key)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"build": key, "items": {}}


def eval_save(req: dict) -> dict:
    key, item = req["c"], req["item"]
    with _eval_lock:
        E = eval_load(key)
        if not req.get("verdict") and not (req.get("note") or "").strip():
            E["items"].pop(item, None)
        else:
            E["items"][item] = {k: req.get(k) for k in ("verdict", "note", "kind", "lecture", "text", "where")}
            E["items"][item]["t"] = time.strftime("%Y-%m-%d %H:%M:%S")
        p = eval_path(key)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(E, indent=1, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)
    return {"ok": True, "count": len(E["items"])}


# ------------------------------------------------------------------ scoring
def score_answer(req: dict) -> dict:
    A = load(req["c"], f"activities/{req['lecture_id']}")
    oq = next(q for q in A["open_questions"] if q["id"] == req["oq_id"])
    cfg = A["scoring"]["open_answer"]
    res = scorer.score(req.get("answer", ""), oq["key_points"], cfg["m"], cfg["tau"], serve.embed_or_none())
    missed = next((kp for kp in oq["key_points"] if kp["text"] in res["missed"]), None)
    res["hint"] = (f"Your answer does not yet say anything about “{missed['keywords'][0]}”. What role does it play here?"
                   if missed and missed.get("keywords") else None)
    return res


@lru_cache(maxsize=8)
def concept_vectors(key: str) -> dict:
    p = build_dir(key) / "embeddings.json"
    if not p.exists():
        return {}
    return {k: np.asarray(v, dtype="float32") for k, v in json.loads(p.read_text())["concepts"].items()}


def score_map(req: dict) -> dict:
    """Same rule as serve.py: match each learner node to a reference concept (name or alias, then meaning); a learner
    link matches a reference link joining the same two concepts; a similar label earns a bonus."""
    key = req["c"]
    A, C = load(key, f"activities/{req['lecture_id']}"), load(key, "course")
    cm = A["concept_map"]
    cfg = A["scoring"].get("concept_map", {"node_match_tau": 0.75, "label_bonus_tau": 0.6, "label_bonus": 0.25})
    concepts = {c["id"]: c for c in C["concepts"]}
    ref_ids = [n["concept_id"] for n in cm["nodes"]]
    by_name = {}
    for cid in ref_ids:
        c = concepts.get(cid, {"name": cid, "aliases": []})
        for n in [c["name"], *[a["text"] if isinstance(a, dict) else a for a in c.get("aliases", [])]]:
            by_name[serve.norm(n)] = cid
    emb, E = serve.embed_or_none(), concept_vectors(key)
    nodes = {}
    for name in req.get("nodes", []):
        cid, how = by_name.get(serve.norm(name)), "name"
        if cid is None and emb is not None and E:
            v = emb([name])[0]
            cands = [(float(np.dot(v, E[c])), c) for c in ref_ids if c in E]
            if cands:
                s, c = max(cands)
                if s >= cfg["node_match_tau"]:
                    cid, how = c, f"meaning ({s:.2f})"
        nodes[name] = {"concept_id": cid, "matched_by": how if cid else None,
                       "concept": concepts[cid]["name"] if cid in concepts else None}
    ref = {frozenset((e["src"], e["dst"])): e for e in cm["edges"]}
    matched = {n["concept_id"] for n in nodes.values() if n["concept_id"]}
    reachable = [e for k, e in ref.items() if k <= matched]
    links, found, bonus = [], set(), 0.0
    for l in req.get("links", []):
        a, b = nodes.get(l.get("a"), {}).get("concept_id"), nodes.get(l.get("b"), {}).get("concept_id")
        e = ref.get(frozenset((a, b))) if a and b else None
        st = {"a": l.get("a"), "b": l.get("b"), "label": l.get("label", ""), "in_reference": e is not None}
        if e is not None:
            k = frozenset((a, b))
            if k not in found:
                found.add(k)
                if l.get("label") and emb is not None:
                    s = float(np.dot(*emb([l["label"], e["label"]])))
                    st["label_similarity"] = round(s, 2)
                    if s >= cfg["label_bonus_tau"]:
                        bonus += cfg["label_bonus"]
            st["reference_label"], st["reference_rel"] = e["label"], e["rel"]
        else:
            st["note"] = "not in the reference map"
        links.append(st)
    denom = len(reachable)
    sc = min(1.0, (len(found) + bonus) / denom) if denom else 0.0
    return {"score": round(sc, 3), "tier": scorer.tier(sc), "nodes": nodes, "links": links,
            "reference_edges_reachable": denom, "found": len(found),
            "missing": [{"src": concepts.get(e["src"], {}).get("name", e["src"]), "rel": e["rel"],
                         "dst": concepts.get(e["dst"], {}).get("name", e["dst"]), "label": e["label"]}
                        for k, e in ref.items() if k <= matched and k not in found]}


# ------------------------------------------------------------------ http
class Handler(serve.Handler):
    def _json(self, obj, code=HTTPStatus.OK):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if u.path in ("/", "/index.html"):  # the viewer, with or without ?dev=1
            u = urlparse("/viewer2/index.html")
        try:
            if u.path == "/lir2/index.json":
                return self._json(index())
            elif u.path.startswith("/lir2/"):
                key, _, name = u.path[len("/lir2/"):].partition("/")
                return self._json(load(key, name.removesuffix(".json")))
            elif u.path == "/api/dev":
                return self._json(lecture_dev(q["c"], q["l"]))
            elif u.path == "/api/concept":
                return self._json(concept_dev(q["c"], q["id"]))
            elif u.path == "/api/eval":
                return self._json(eval_load(q["c"]))
        except (KeyError, ValueError, FileNotFoundError, StopIteration) as e:
            return self._json({"error": str(e) or type(e).__name__}, HTTPStatus.NOT_FOUND)
        if u.path.startswith("/viewer2/") and "/." not in u.path and ".." not in u.path:
            self.path = u.path
            return super(serve.Handler, self).do_GET()  # plain static file (serve.py only allows its own folders)
        return super().do_GET()                         # /viewer/ (styles, vendor), /media/ (videos, with Range)

    def do_POST(self):
        try:
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            if self.path == "/api/score":
                return self._json(score_answer(req))
            if self.path == "/api/cmap":
                return self._json(score_map(req))
            if self.path == "/api/eval":
                return self._json(eval_save(req))
            return self.send_error(HTTPStatus.NOT_FOUND)
        except Exception as e:
            return self._json({"error": str(e)}, HTTPStatus.BAD_REQUEST)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", type=Path, help="run folders, build folders or lir/ folders (default: runs/)")
    ap.add_argument("--port", type=int, default=8001)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    BUILDS.update(find_builds(args.paths or [HERE / "runs"]))
    if not BUILDS:
        sys.exit("no LIR v2 build found (a folder with lir/course.json)")
    for k, p in BUILDS.items():
        print(f"  {k}  ->  {p}")
    if serve.embed_or_none():
        threading.Thread(target=lambda: serve.embed(["warm up"]), daemon=True).start()
    else:
        print("sentence-transformers is not installed: open answers are scored by keywords only")
    print(f"LIR v2 viewer: http://localhost:{args.port}   (?dev=1 for dev mode and hand eval; Ctrl+C to stop)")
    serve.ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
