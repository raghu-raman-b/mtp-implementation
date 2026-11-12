"""Read access to a course's knowledge layer (output/<course>/knowledge/, written by scripts/s4d_assemble.py).

    kb = Knowledge.load("nptel_vr")           # cached per folder: the files are read once per process
    kb.lookup_name("HMDs")                    # -> (["C0004"], "acronym", "HMD")  or ([], None, None)
    kb.search(["what is an HMD?", "head-mounted display"], k=8)   # -> [(fact ID, score)]

The folder is <output>/<course>/knowledge, where <output> is $QA_OUTPUT when set (tests point it at a copy) and the
pipeline's output/ otherwise. The facts were embedded with no instruction; a query is embedded with QUERY_INSTRUCTION
(scripts/embed.py), by the model the layer names in index.json, on the CPU (the GPU holds the answering model).
"""
from __future__ import annotations

import difflib
import json
import os
import re
import threading
from pathlib import Path

from scripts import lectures as lec
from scripts.s4d_assemble import name_key, is_acronym

ROOT = Path(__file__).resolve().parent.parent  # the pipeline folder
QUERY_INSTRUCTION = "Given a learner's question about a lecture course, retrieve the course facts that answer it"
CLOSE_CUTOFF = 0.84          # difflib ratio for a misspelt name to count as that name
SUGGEST_CUTOFF = 0.6         # names shown as "did you mean" when nothing is close enough


def output_root() -> Path:
    return Path(os.environ.get("QA_OUTPUT") or ROOT / "output")


def knowledge_dir(course: str) -> Path:
    return output_root() / course / "knowledge"


def qa_dir(course: str) -> Path:
    """Where the answering logs and the query embedding cache go."""
    return output_root() / course / "qa"


def lecture_key(x) -> str:
    """"4", 4, "lecture 4", "Lecture 24B", "lec_4", "tut 1" -> the layer's key ("4", "24b", "tut_1")."""
    s = str(x).strip().lower()
    s = re.sub(r"^(?:lecture|lec)[\s_.#-]*", "", s)
    s = re.sub(r"^(?:tutorial|tut)[\s_.#-]*", "tut_", s)
    s = re.sub(r"\s+", "_", s)
    return s


def fmt_time(t: float) -> str:
    t = int(round(float(t or 0)))
    h, m, s = t // 3600, t % 3600 // 60, t % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def singular_forms(key: str) -> list[str]:
    """Plural foldings of a name key (the index does none): "displays" -> "display", "lenses" -> "lens",
    "hmds" -> "hmd"; only the last word changes."""
    out = []
    for suf, rep in (("ies", "y"), ("ses", "s"), ("xes", "x"), ("ches", "ch"), ("shes", "sh"), ("s", "")):
        if key.endswith(suf) and len(key) > len(suf) + 1:
            out.append(key[: -len(suf)] + rep)
    return out


class Knowledge:
    _cache: dict[str, "Knowledge"] = {}
    _lock = threading.Lock()

    def __init__(self, folder: Path):
        self.dir = Path(folder)
        if not (self.dir / "index.json").exists():
            raise FileNotFoundError(f"no knowledge layer at {self.dir} (run scripts/s4d_assemble.py first)")
        load = lambda name: json.loads((self.dir / name).read_text())  # noqa: E731
        self.index = load("index.json")
        self.names = load("names.json")
        self.concepts = load("concepts.json")
        self.relations = load("relations.json")
        self.facts = load("facts.json")
        self.goals = load("goals.json")
        self.graph = load("lecture_graph.json")
        self.assumed = load("assumed.json")
        self.lectures = {}
        for k in self.index["lectures"]:
            p = self.dir / "lectures" / f"{lec.stem_of(k)}.json"
            if p.exists():
                self.lectures[k] = json.loads(p.read_text())
        emb = load("fact_embeddings.json")
        self.embed_model = emb["model"]
        self.fact_ids = list(emb["vectors"])
        self._vectors = emb["vectors"]
        self._matrix = None
        self._embedder = None
        self._elock = threading.Lock()

    @classmethod
    def load(cls, course: str) -> "Knowledge":
        folder = knowledge_dir(course)
        key = str(folder.resolve())
        with cls._lock:
            if key not in cls._cache:
                cls._cache[key] = cls(folder)
            return cls._cache[key]

    @property
    def course(self) -> str:
        return self.index["course"]

    @property
    def title(self) -> str:
        return self.index.get("title", "")

    def lecture_title(self, k: str) -> str:
        return (self.lectures.get(k) or {}).get("title") or f"Lecture {k}"

    def concept_name(self, cid: str) -> str:
        return (self.concepts.get(cid) or {}).get("name", cid)

    # ------------------------------------------------------------ names
    def lookup_name(self, name: str) -> tuple[list[str], str | None, str | None]:
        """The concepts a name stands for, how it matched ("exact", "plural", "close") and the indexed name it
        matched. Close matches use difflib over every indexed name and must be unambiguous."""
        key = name_key(name)
        if not key:
            return [], None, None
        tries = [(key, "exact")] + [(s, "plural") for s in singular_forms(key)]
        tok = name.strip()
        if is_acronym(tok.rstrip("s")) and tok.endswith("s"):              # "HMDs"
            tries.append((name_key(tok[:-1]), "plural"))
        for k, how in tries:
            if k in self.names:
                return [e["concept"] for e in self.names[k]], how, self.names[k][0]["text"]
        if len(key) >= 4:
            close = difflib.get_close_matches(key, list(self.names), n=3, cutoff=CLOSE_CUTOFF)
            if close:
                ratio = lambda k: difflib.SequenceMatcher(None, key, k).ratio()  # noqa: E731
                top = [k for k in close if ratio(k) >= ratio(close[0]) - 0.03]
                sets = {frozenset(e["concept"] for e in self.names[k]) for k in top}
                if len(sets) == 1:                   # unambiguous: the near names all mean the same concepts
                    best = close[0]
                    return [e["concept"] for e in self.names[best]], "close", self.names[best][0]["text"]
        return [], None, None

    def suggestions(self, name: str, n: int = 4) -> list[str]:
        key = name_key(name)
        out = []
        for k in difflib.get_close_matches(key, list(self.names), n=n * 2, cutoff=SUGGEST_CUTOFF):
            for e in self.names[k]:
                nm = self.concept_name(e["concept"])
                if nm not in out:
                    out.append(nm)
        return out[:n]

    def expand_acronyms(self, text: str) -> str:
        """The text with each acronym the index knows replaced by its concept's name ("an HMD" -> "an head-mounted
        display"); unchanged when there is none."""
        def rep(m):
            t = m.group(0)
            for k in (name_key(t), name_key(t[:-1]) if t.endswith("s") else None):
                if k and k in self.names and any(e["as"] == "acronym" for e in self.names[k]):
                    return self.concept_name(self.names[k][0]["concept"])
            return t
        return re.sub(r"\b[A-Za-z0-9]{2,}\b", lambda m: rep(m) if is_acronym(m.group(0).rstrip("s")) else m.group(0),
                      text)

    # ------------------------------------------------------------ fact search
    def embedder(self):
        with self._elock:
            if self._embedder is None:
                from scripts.embed import Embedder
                qd = qa_dir(self.course)
                cache = qd / "query_embed_cache.jsonl" if self.embed_model != "fake" else None
                self._embedder = Embedder(self.embed_model, cache=cache, device="cpu")
            return self._embedder

    def _mat(self):
        if self._matrix is None:
            try:
                import numpy as np
                self._matrix = np.asarray([self._vectors[f] for f in self.fact_ids], dtype="float32")
            except ImportError:
                self._matrix = [self._vectors[f] for f in self.fact_ids]
        return self._matrix

    def search(self, queries: list[str], k: int = 8, lecture: str | None = None) -> list[tuple[str, float]]:
        """The k facts closest to any of the queries (cosine; a fact's score is its best over the queries), best
        first, optionally only from one lecture."""
        queries = [q for q in dict.fromkeys(q.strip() for q in queries) if q]
        if not queries or not self.fact_ids:
            return []
        qv = self.embedder().embed(queries, instruction=QUERY_INSTRUCTION)
        m = self._mat()
        try:
            import numpy as np
            scores = (m @ np.asarray(qv, dtype="float32").T).max(axis=1).tolist()
        except ImportError:
            scores = [max(sum(a * b for a, b in zip(row, q)) for q in qv) for row in m]
        ranked = sorted(zip(self.fact_ids, scores), key=lambda x: -x[1])
        if lecture is not None:
            ranked = [(f, s) for f, s in ranked if self.facts.get(f, {}).get("lecture") == lecture]
        return [(f, round(float(s), 4)) for f, s in ranked[:k]]
