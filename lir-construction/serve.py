#!/usr/bin/env python3
"""Serve the LIR viewer, the LIR files and the videos, plus the runtime scorers (CPU only).

    python3 serve.py            # then open http://localhost:8000
    python3 serve.py --port 9000

Endpoints
    GET  /                 the viewer (viewer/index.html)
    GET  /lir/...          LIR files;  GET /media/... videos (with HTTP Range, so seeking works)
    POST /api/score        {course_id, lecture_id, oq_id, answer}       -> tier, covered and missed key points
    POST /api/cmap         {course_id, lecture_id, nodes, links}        -> concept-map score against the reference

Scoring runs on the CPU: keyword matching, plus one small sentence-embedding model (the same model that embedded the
key points and concepts at build time). Without it, scoring falls back to keywords and names only.
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
try:
    import numpy  # noqa: F401
except ImportError:
    venv_py = HERE.parent / "bin/python"
    if venv_py.exists() and Path(sys.executable).resolve() != venv_py.resolve():
        os.execv(str(venv_py), [str(venv_py), __file__, *sys.argv[1:]])
    raise

import argparse
import json
import re
import threading
from functools import lru_cache
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import numpy as np

sys.path.insert(0, str(HERE))
import scorer  # noqa: E402

_model = None
_model_lock = threading.Lock()


def embed(texts):
    """CPU sentence embeddings, loaded on first use."""
    global _model
    with _model_lock:
        if _model is None:
            os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2", device="cpu")
        return _model.encode(list(texts), normalize_embeddings=True, convert_to_numpy=True)


def embed_or_none():
    try:
        import sentence_transformers  # noqa: F401
        return embed
    except ImportError:
        return None


@lru_cache(maxsize=256)
def load(course_id: str, name: str) -> dict:
    if not re.fullmatch(r"[\w.-]+", course_id) or not re.fullmatch(r"[\w.-]+", name):
        raise ValueError("bad id")
    return json.loads((HERE / "lir" / course_id / f"{name}.json").read_text(encoding="utf-8"))


def norm(name: str) -> str:
    t = re.sub(r"[-_/]+", " ", name.lower())
    t = re.sub(r"[^a-z0-9 ]+", "", t)
    out = []
    for w in t.split():
        if len(w) > 4 and w.endswith("ies"):
            w = w[:-3] + "y"
        elif len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
            w = w[:-1]
        out.append(w)
    return " ".join(out)


def score_answer(req: dict) -> dict:
    lec = load(req["course_id"], req["lecture_id"])
    oq = next(q for ph in lec["phases"] if ph["type"] == "constructive" for q in ph["open_questions"]
              if q["id"] == req["oq_id"])
    cfg = lec["scoring"]["open_answer"]
    res = scorer.score(req.get("answer", ""), oq["key_points"], cfg["m"], cfg["tau"], embed_or_none())
    # first feedback names the tier and gives a hint from one missed key point (the doc's revise loop)
    res["hint"] = res["missed"][0] if res["missed"] else None
    return res


def score_map(req: dict) -> dict:
    """Doc rule: match each learner node to a concept (alias / normalized name, then embedding); a learner link
    matches a reference edge if it joins the same two concepts; a similar label earns a bonus. Score = share of the
    reference edges among the learner's matched nodes that were found. Extra links are not penalized."""
    lec = load(req["course_id"], req["lecture_id"])
    course = load(req["course_id"], "course")
    cm = next(ph for ph in lec["phases"] if ph["type"] == "constructive")["concept_map"]
    cfg = lec["scoring"].get("concept_map", {"node_match_tau": 0.75, "label_bonus_tau": 0.6, "label_bonus": 0.25})
    concepts = {c["id"]: c for c in course["concepts"]}
    ref_ids = [n["concept_id"] for n in cm["reference_nodes"]]
    by_name = {}
    for cid in ref_ids:
        c = concepts.get(cid, {"name": cid, "aliases": []})
        for n in [c["name"], *c.get("aliases", [])]:
            by_name[norm(n)] = cid
    emb = embed_or_none()
    E = course.get("concept_embeddings", {})
    nodes = {}
    for name in req.get("nodes", []):
        cid, how = by_name.get(norm(name)), "name"
        if cid is None and emb is not None and E:
            v = emb([name])[0]
            cands = [(float(np.dot(v, E[c])), c) for c in ref_ids if c in E]
            if cands:
                s, c = max(cands)
                if s >= cfg["node_match_tau"]:
                    cid, how = c, f"meaning ({s:.2f})"
        nodes[name] = {"concept_id": cid, "matched_by": how if cid else None,
                       "concept": concepts[cid]["name"] if cid in concepts else None}
    ref = {frozenset((e["src"], e["dst"])): e for e in cm["reference_edges"]}
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
            st["reference_label"] = e["label"]
            st["reference_rel"] = e["rel"]
        else:
            st["note"] = "not in the reference map"
        links.append(st)
    denom = len(reachable)
    sc = (len(found) + bonus) / denom if denom else 0.0
    return {"score": round(min(1.0, sc), 3), "tier": scorer.tier(min(1.0, sc)), "nodes": nodes, "links": links,
            "reference_edges_reachable": denom, "found": len(found),
            "missing": [{"src": concepts.get(e["src"], {}).get("name", e["src"]), "rel": e["rel"],
                         "dst": concepts.get(e["dst"], {}).get("name", e["dst"]), "label": e["label"]}
                        for k, e in ref.items() if k <= matched and k not in found]}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(HERE), **kw)

    def log_message(self, fmt, *args):
        if "/api/" in (args[0] if args else ""):
            sys.stderr.write("%s\n" % (fmt % args))

    def end_headers(self):
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.path = "/viewer/index.html"
        if self.headers.get("Range") and self.path.startswith("/media/"):
            return self._range()
        return super().do_GET()

    def _range(self):
        path = Path(self.translate_path(self.path))
        if not path.is_file():
            return self.send_error(HTTPStatus.NOT_FOUND)
        size = path.stat().st_size
        m = re.match(r"bytes=(\d*)-(\d*)", self.headers["Range"])
        start = int(m.group(1)) if m and m.group(1) else 0
        end = int(m.group(2)) if m and m.group(2) else size - 1
        end = min(end, size - 1)
        if start > end:
            self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            self.send_header("Content-Range", f"bytes */{size}")
            return self.end_headers()
        self.send_response(HTTPStatus.PARTIAL_CONTENT)
        self.send_header("Content-Type", self.guess_type(str(path)))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(start)
            left = end - start + 1
            try:
                while left > 0:
                    chunk = f.read(min(1 << 20, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def do_POST(self):
        try:
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            if self.path == "/api/score":
                res = score_answer(req)
            elif self.path == "/api/cmap":
                res = score_map(req)
            else:
                return self.send_error(HTTPStatus.NOT_FOUND)
            body, code = json.dumps(res).encode(), HTTPStatus.OK
        except Exception as e:
            body, code = json.dumps({"error": str(e)}).encode(), HTTPStatus.BAD_REQUEST
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    if embed_or_none():  # load the CPU model in the background
        threading.Thread(target=lambda: embed(["warm up"]), daemon=True).start()
    else:
        print("sentence-transformers is not installed: open answers are scored by keywords only")
    print(f"LIR viewer: http://localhost:{args.port}   (Ctrl+C to stop)")
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
