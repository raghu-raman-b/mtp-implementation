#!/usr/bin/env python3
"""The v3 viewer: a standard-library HTTP server for the static viewer, the course's JSON layers and the videos.

    python pipeline/viewer/serve.py nptel_vr [--port 8765] [--host 127.0.0.1] [--root PIPELINE_DIR] [--media DIR]
                                             [--qa-path DIR] [--warm]

Then open http://localhost:8765 (add ?dev=1, or use the toggle, for developer mode).

Reads (never writes) under <root> (default: the pipeline folder this file sits in):
    input/<course>/input/course.json, titles.tsv           course title, syllabus, lecture titles and weeks
    output/<course>/stage_1b_verify_segments/segment_maps/  segments with sub-goals and times (used when knowledge/
                                                            has no file for a lecture)
    output/<course>/stage_0a_preprocess/lec_<n>.json, times/ sentences and their times (the transcript)
    output/<course>/knowledge/                              stage 4d's layer (optional, per lecture)
    output/<course>/activities/                             the activities (optional, per lecture; schemas/activities.md)
    input/<course>/media/L01.mp4 ...                        the videos (optional; or --media DIR). A lecture
                                                            without its file plays from YouTube in the page, by
                                                            the youtube_id of titles.tsv (when it has one)

Routes
    GET  /                          the viewer (index.html); /static/... its files
    GET  /api/course                the course: title, syllabus, goals, lectures (title, week, goal, which layers
                                    exist), the layers present
    GET  /api/lecture/<key>         one lecture: segments (from knowledge/, else 1b), sentences (0a), the knowledge
                                    lecture file or null, the activities file or null, where the segments came from,
                                    whether the video file is here ("video") and the YouTube ID ("youtube_id")
    The page itself reads only the lean routes below; every one is built once, kept in memory until one of the files
    it is built from changes, and sent gzip-compressed when the browser accepts it (with an ETag, so a reload is a 304):
    GET  /api/home                  title, syllabus, course goals, the lectures (key, title, week, goal), the layers
    GET  /api/view/<key>            what the lecture page needs and nothing more: segments, sentences, goal, objectives,
                                    the links of the lecture graph into this lecture ("before"),
                                    activities (an activity a checks*.json marks "unresolved" carries "unresolved":
                                    true; the page hides it outside developer mode), the lecture's concept map, and only
                                    the concepts and facts this lecture refers to
    GET  /api/glossary              every concept: name, other names, definition, where it is first explained, whether
                                    it has relationships ("linked")
    GET  /api/concept/<C0042>       one concept card: definition, where it is explained, facts, relationships
    GET  /api/coursemap             the lecture graph for the course map (lectures, direct links, prerequisites)
    GET  /api/review                the spaced-review cards of activities/course.json
    GET  /data/knowledge/<file>     a knowledge/ file (concepts.json, facts.json, ..., lectures/lec_<n>.json);
                                    fact_embeddings.json is not served
    GET  /data/activities/<file>    an activities/ file (lec_<n>.json, course.json)
    GET  /media/<key>               a lecture's video, with HTTP Range (so seeking works)
    POST /api/ask                   {"question", "lecture"} -> qa.answer(question, course, lecture) from pipeline/qa/
                                    when importable, else {"available": false, "answer": "...not available..."}
--warm loads qa at start, in the background, and calls qa.warm(course) (the layer, the query embedder, the model
server; the config is qa's default: $QA_CONFIG or the local Gemma), so the first question does not wait for them.
A missing layer is never an error for the course or lecture routes: it comes back as null (or the segments fall back
to 1b), and the raw /data/ routes answer 404 for a file that does not exist.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import importlib
import importlib.util
import json
import mimetypes
import re
import sys
import threading
import time
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

HERE = Path(__file__).resolve().parent            # pipeline/viewer
PIPELINE = HERE.parent
KEY = re.compile(r"\d+[a-z]?|tut_\d+(?:_part\d+)?")
FILE = re.compile(r"(?:lectures/)?[\w.-]+\.json")
STATIC = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
          ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png", ".woff2": "font/woff2"}


def stem_of(key: str) -> str:
    return f"lec_{key}" if key[:1].isdigit() else key


def order(key: str) -> tuple:
    m = re.fullmatch(r"(\d+)([a-z]?)", key)
    if m:
        return (0, int(m[1]), m[2], 0)
    m = re.fullmatch(r"tut_(\d+)(?:_part(\d+))?", key)
    return (1, int(m[1]), "", int(m[2] or 0)) if m else (2, 0, key, 0)


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


_JSON: dict = {}                                         # path -> ((mtime_ns, size), parsed JSON)


def stat_sig(path: Path):
    try:
        st = path.stat()
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def load_json(path: Path):
    """read_json, kept in memory until the file changes (callers must not modify what it returns)."""
    sig = stat_sig(path)
    if sig is None:
        return None
    hit = _JSON.get(path)
    if hit and hit[0] == sig:
        return hit[1]
    data = read_json(path)
    _JSON[path] = (sig, data)
    return data


_MP4: dict = {}


def mp4_duration(path: Path) -> float | None:
    """An MP4's duration in seconds from its moov/mvhd box (kept until the file changes); None if not found."""
    sig = stat_sig(path)
    if sig is None:
        return None
    if path in _MP4 and _MP4[path][0] == sig:
        return _MP4[path][1]
    dur = None
    try:
        with open(path, "rb") as f:
            def boxes(start, stop):
                pos = start
                while pos + 8 <= stop:
                    f.seek(pos)
                    hdr = f.read(16)
                    if len(hdr) < 8:
                        return
                    n, kind = int.from_bytes(hdr[:4], "big"), hdr[4:8]
                    head = 8
                    if n == 1 and len(hdr) >= 16:
                        n, head = int.from_bytes(hdr[8:16], "big"), 16
                    elif n == 0:
                        n = stop - pos
                    if n < head:
                        return
                    yield kind, pos + head, pos + n
                    pos += n
            for kind, a, b in boxes(0, sig[1]):
                if kind == b"moov":
                    for k2, a2, b2 in boxes(a, b):
                        if k2 == b"mvhd":
                            f.seek(a2)
                            d = f.read(32)
                            if d[0] == 1:
                                scale, length = int.from_bytes(d[20:24], "big"), int.from_bytes(d[24:32], "big")
                            else:
                                scale, length = int.from_bytes(d[12:16], "big"), int.from_bytes(d[16:20], "big")
                            dur = length / scale if scale else None
                    break
    except (OSError, IndexError):
        dur = None
    _MP4[path] = (sig, dur)
    return dur


class Payload:
    """A JSON answer encoded once: the body, its gzip and an ETag."""

    def __init__(self, data, raw: bytes | None = None):
        self.body = raw if raw is not None else json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode()
        self.gz = gzip.compress(self.body, 6) if len(self.body) > 1024 else None
        self.etag = '"' + hashlib.sha1(self.body).hexdigest()[:20] + '"'

    @classmethod
    def raw(cls, body: bytes) -> "Payload":
        return cls(None, body)


FACT_ID = re.compile(r"(?:\d+[a-z]?|tut_\d+(?:_part\d+)?)/S\d+/F\d+")
CONCEPT_ID = re.compile(r"C\d{4,}")


def collect_ids(obj, cids: set, fids: set):
    """Every concept and fact ID an activity refers to (by the contract's field names)."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("concept", "id", "from", "to") and isinstance(v, str) and CONCEPT_ID.fullmatch(v):
                cids.add(v)
            elif k == "concepts" and isinstance(v, list):
                cids.update(x for x in v if isinstance(x, str) and CONCEPT_ID.fullmatch(x))
            elif k in ("facts", "key_facts") and isinstance(v, list):
                fids.update(x for x in v if isinstance(x, str) and FACT_ID.fullmatch(x))
            else:
                collect_ids(v, cids, fids)
    elif isinstance(obj, list):
        for v in obj:
            collect_ids(v, cids, fids)


class Course:
    """Paths and loaders for one course; every load is fresh (or cached until its files change), so new outputs show
    on a reload."""

    def __init__(self, course: str, root: Path, media: Path | None = None, output: Path | None = None,
                 activities: str = "activities"):
        self.course, self.root = course, root
        self.inp = root / "input" / course / "input"
        self.out = (output or root / "output") / course
        self.kd = self.out / "knowledge"
        self.ad = self.out / activities
        self.media = media or (root / "input" / course / "media")
        self._memo: dict = {}
        self._lock = threading.Lock()

    def memo(self, name: str, paths, build) -> Payload:
        """build() encoded once, until one of the paths (files or folders) changes."""
        sig = tuple(stat_sig(p) for p in paths)
        hit = self._memo.get(name)
        if hit and hit[0] == sig:
            return hit[1]
        pay = Payload(build())
        with self._lock:
            self._memo[name] = (sig, pay)
        return pay

    def kfile(self, name: str):
        return load_json(self.kd / name) if self.kd.is_dir() else None

    # ------------------------------------------------ inputs
    def titles(self) -> dict:
        rows = {}
        try:
            with open(self.inp / "titles.tsv", newline="", encoding="utf-8") as f:
                for r in csv.DictReader(f, delimiter="\t"):
                    stem = r["id"].rsplit("/", 1)[-1]
                    m = re.fullmatch(r"lec_(\d+[a-z]?)", stem)
                    key = m[1] if m else stem
                    rows[key] = {"title": (r.get("title") or "").strip(), "week": (r.get("week") or "").strip(),
                                 "type": (r.get("type") or "").strip(), "youtube_id": (r.get("youtube_id") or "").strip()}
        except OSError:
            pass
        return rows

    def keys(self) -> list[str]:
        found = set(self.titles())
        for folder in (self.out / "stage_1b_verify_segments" / "segment_maps", self.kd / "lectures", self.ad):
            if folder.is_dir():
                for p in folder.glob("*.json"):
                    m = re.fullmatch(r"lec_(\d+[a-z]?)|(tut_\d+(?:_part\d+)?)", p.stem)
                    if m:
                        found.add(m[1] or m[2])
        return sorted(found, key=order)

    def duration(self, key: str) -> float | None:
        """The lecture's length in seconds (its last segment or sentence end), for pacing its video; None if unknown."""
        stem = stem_of(key)
        ends = [s.get("end") or 0 for s in (load_json(self.out / "stage_1b_verify_segments" / "segment_maps"
                                                      / f"{stem}.json") or {}).values() if isinstance(s, dict)]
        ends += [t.get("end") or 0 for t in (load_json(self.out / "stage_0a_preprocess" / "times" / f"{stem}.json")
                                             or {}).values() if isinstance(t, dict)]
        return max(ends) if ends and max(ends) > 0 else None

    def video(self, key: str) -> Path | None:
        m = re.fullmatch(r"(\d+)([a-z]?)", key)
        names = ([f"L{int(m[1]):02d}{m[2]}.mp4", f"L{m[1]}{m[2]}.mp4"] if m else []) + [f"{stem_of(key)}.mp4",
                                                                                       f"{key}.mp4"]
        for n in names:
            p = self.media / n
            if p.is_file():
                return p
        return None

    # ------------------------------------------------ layers
    def knowledge(self, name: str):
        return load_json(self.kd / name) if self.kd.is_dir() else None

    def lecture_goal(self, goals, key):
        if not goals:
            return None
        for g in (goals.get("lecture_goals") or {}).values():
            if g.get("lecture") == key:
                return g.get("goal")
        return None

    def course_info(self) -> dict:
        meta = load_json(self.inp / "course.json") or {}
        titles = self.titles()
        index = self.knowledge("index.json")
        goals = self.knowledge("goals.json")
        graph = self.knowledge("lecture_graph.json")
        assumed = self.knowledge("assumed.json")
        acourse = load_json(self.ad / "course.json") if self.ad.is_dir() else None
        lectures = []
        for k in self.keys():
            t = titles.get(k, {})
            lectures.append({
                "key": k, "title": t.get("title") or f"Lecture {k}", "week": t.get("week", ""),
                "goal": self.lecture_goal(goals, k),
                "prerequisites": ((graph or {}).get("prerequisites") or {}).get(k),
                "has": {"segments": (self.out / "stage_1b_verify_segments" / "segment_maps" / f"{stem_of(k)}.json").is_file(),
                        "transcript": (self.out / "stage_0a_preprocess" / f"{stem_of(k)}.json").is_file(),
                        "knowledge": (self.kd / "lectures" / f"{stem_of(k)}.json").is_file(),
                        "activities": (self.ad / f"{stem_of(k)}.json").is_file(),
                        "video": self.video(k) is not None, "youtube": bool(t.get("youtube_id"))}})
        return {"course": self.course, "title": meta.get("title") or (index or {}).get("title") or self.course,
                "meta": {f: meta.get(f) for f in ("platform", "institution", "instructor", "prerequisites",
                                                  "intended_audience", "outline", "syllabus")},
                "layers": {"knowledge": index is not None, "activities": self.ad.is_dir(),
                           "spaced_review": bool(acourse and acourse.get("spaced_review"))},
                "index": index, "goals": goals, "assumed": assumed, "lectures": lectures,
                "qa": qa_status()}

    def lecture(self, key: str) -> dict:
        stem = stem_of(key)
        kl = load_json(self.kd / "lectures" / f"{stem}.json") if self.kd.is_dir() else None
        segs = load_json(self.out / "stage_1b_verify_segments" / "segment_maps" / f"{stem}.json")
        source = "knowledge" if kl else ("segments" if segs else "none")
        segments = []
        for sid, s in ((kl or {}).get("segments") or segs or {}).items():
            segments.append({"id": sid, "first": s.get("first"), "last": s.get("last"), "start": s.get("start", 0.0),
                             "end": s.get("end", 0.0), "subgoal": s.get("subgoal", ""),
                             "objective": s.get("objective"), "facts": s.get("facts", []),
                             "concepts": s.get("concepts", [])})
        segments.sort(key=lambda s: s["start"] or 0)
        texts = load_json(self.out / "stage_0a_preprocess" / f"{stem}.json") or {}
        times = load_json(self.out / "stage_0a_preprocess" / "times" / f"{stem}.json") or {}
        sentences, prev = [], 0.0
        for sid, txt in texts.items():                       # a missing start (0a has some) is the previous end
            t = times.get(sid) or {}
            start = t.get("start") if t.get("start") is not None else prev
            end = t.get("end") if t.get("end") is not None else start
            sentences.append({"id": sid, "text": txt, "start": start, "end": end})
            prev = end
        acts = load_json(self.ad / f"{stem}.json") if self.ad.is_dir() else None
        t = self.titles().get(key, {})
        return {"key": key, "title": (kl or {}).get("title") or t.get("title") or f"Lecture {key}",
                "week": t.get("week", ""), "source": source, "segments": segments, "sentences": sentences,
                "knowledge": kl, "activities": acts, "video": self.video(key) is not None,
                "youtube_id": t.get("youtube_id") or None}

    # ------------------------------------------------ lean routes for the page (built once, kept until files change)
    def _dirs(self):
        return [self.inp / "titles.tsv", self.out / "stage_1b_verify_segments" / "segment_maps", self.kd,
                self.kd / "lectures", self.ad, self.media]

    def check_units(self) -> dict:
        """unit -> its record, from every checks*.json in activities/ (for a unit several files report, the newest
        file wins)."""
        units = {}
        files = sorted(self.ad.glob("checks*.json"), key=lambda p: stat_sig(p) or (0, 0)) if self.ad.is_dir() else []
        for f in files:
            for kinds in ((load_json(f) or {}).get("lectures") or {}).values():
                for recs in (kinds or {}).values():
                    if isinstance(recs, dict):
                        units.update({u: r for u, r in recs.items() if isinstance(r, dict)})
        return units

    def flagged(self, units: dict) -> dict:
        """activity ID -> its check record, for every unit the checks mark "unresolved"."""
        return {r["activity"]: {"unit": u, "status": r.get("status"), "problems": r.get("problems") or []}
                for u, r in units.items() if r.get("status") == "unresolved" and r.get("activity")}

    @staticmethod
    def judge_failed(units: dict, acts: list[dict]) -> dict:
        """activity ID -> {item number: the criteria the judge failed it on} (s5's numbering: 1.. in the order of the
        activity's list; recap 0 is its text), from the judge round of the version kept. A put_in_order unit may have
        made several activities (the record names the last): its numbers run on across the unit's activities of that
        segment, in file order."""
        out = {}
        for r in units.values():
            j = r.get("judge") or {}
            nums = [n for n in (r.get("flags") or {}).get("judge_failed") or [] if isinstance(n, int)]
            aid = r.get("activity")
            if not nums or not aid:
                continue
            rounds = j.get("rounds") or []
            rnd = (rounds[-1] if j.get("kept") == "rewrite" else rounds[0]) if rounds else {}
            why = {v.get("item"): [str(c) for c in v.get("failed") or []]
                   for v in rnd.get("verdicts") or [] if isinstance(v, dict)}
            last = next((a for a in acts if a.get("id") == aid), None)
            if last is None:
                continue
            group = [last]
            if last.get("kind") == "put_in_order":
                i = acts.index(last)
                while i > 0 and acts[i - 1].get("kind") == "put_in_order" and acts[i - 1].get("segment") == last.get("segment"):
                    i -= 1
                    group.insert(0, acts[i])
            off = 0
            for a in group:
                n_items = len(((a.get("data") or {}).get(ITEM_LIST.get(a.get("kind")) or "") or []))
                mine = {n - off: why.get(n, []) for n in nums if off < n <= off + n_items} if len(group) > 1 else \
                    {n: why.get(n, []) for n in nums}
                if mine:
                    out[a["id"]] = mine
                off += n_items
        return out

    @staticmethod
    def judge_hidden(kind: str, failed: dict) -> list[int]:
        """The judge-failed items of an activity the page shows only in developer mode (HIDE_JUDGE_FAILED)."""
        rule = HIDE_JUDGE_FAILED.get(kind, False)
        if rule is False:
            return []
        return sorted(n for n, crit in failed.items()
                      if (kind != "recap" or n > 0) and (rule is True or set(crit) & rule))

    def slim_concept(self, cid: str, c: dict) -> dict:
        return {"name": c.get("name") or cid, "definition": c.get("definition") or "",
                "defined_in": [{"lecture": d.get("lecture"), "segment": d.get("segment"), "start": d.get("start")}
                               for d in c.get("defined_in") or []],
                "first_defined": c.get("first_defined")}

    def home(self) -> Payload:
        def build():
            meta = load_json(self.inp / "course.json") or {}
            titles = self.titles()
            goals = self.kfile("goals.json") or {}
            index = self.kfile("index.json")
            lgoal = {g.get("lecture"): g.get("goal") for g in (goals.get("lecture_goals") or {}).values()}
            lectures = []
            for k in self.keys():
                t = titles.get(k, {})
                lectures.append({"key": k, "title": t.get("title") or f"Lecture {k}", "week": t.get("week", ""),
                                 "goal": lgoal.get(k),
                                 "has": {"knowledge": (self.kd / "lectures" / f"{stem_of(k)}.json").is_file(),
                                         "activities": (self.ad / f"{stem_of(k)}.json").is_file(),
                                         "video": self.video(k) is not None, "youtube": bool(t.get("youtube_id"))}})
            acourse = load_json(self.ad / "course.json") if self.ad.is_dir() else None
            return {"course": self.course, "title": meta.get("title") or (index or {}).get("title") or self.course,
                    "meta": {f: meta.get(f) for f in ("platform", "institution", "instructor", "prerequisites",
                                                      "outline")},
                    "syllabus": [{"week": w.get("week"), "theme": w.get("theme")} for w in meta.get("syllabus") or []],
                    "goals": [{"id": gid, "goal": g.get("goal"), "achieves": g.get("achieves"),
                               "lectures": g.get("lectures") or []}
                              for gid, g in (goals.get("course_goals") or {}).items()],
                    "layers": {"knowledge": index is not None, "activities": self.ad.is_dir(),
                               "spaced_review": bool(acourse and (acourse.get("spaced_review") or {}).get("cards"))},
                    "counts": (index or {}).get("counts"), "qa": qa_status(), "prefer_youtube": PREFER_YOUTUBE,
                    "lectures": lectures}
        return self.memo("home", self._dirs() + [self.inp / "course.json", self.kd / "goals.json",
                                                 self.kd / "index.json", self.ad / "course.json"], build)

    def view(self, key: str) -> Payload:
        stem = stem_of(key)
        paths = self._dirs() + [self.kd / "lectures" / f"{stem}.json", self.ad / f"{stem}.json",
                                self.out / "stage_1b_verify_segments" / "segment_maps" / f"{stem}.json",
                                self.out / "stage_0a_preprocess" / f"{stem}.json",
                                self.out / "stage_0a_preprocess" / "times" / f"{stem}.json",
                                self.kd / "concepts.json", self.kd / "facts.json", self.kd / "relations.json",
                                self.kd / "goals.json", self.kd / "lecture_graph.json"] + (
                                    sorted(self.ad.glob("checks*.json")) if self.ad.is_dir() else [])

        def build():
            base = self.lecture(key)
            kl = base["knowledge"] or {}
            concepts = self.kfile("concepts.json") or {}
            facts = self.kfile("facts.json") or {}
            rels = self.kfile("relations.json") or {}
            goals = (self.kfile("goals.json") or {}).get("course_goals") or {}
            units = self.check_units()
            flagged = self.flagged(units)
            acts = None
            if base["activities"] is not None:
                acts = []
                raw = base["activities"].get("activities") or []
                failed = self.judge_failed(units, raw)
                for a in raw:
                    if a.get("id") in flagged:
                        a = {**a, "unresolved": True, "check": flagged[a["id"]]}
                    if a.get("id") in failed:       # judge_failed: item -> criteria (shown in developer mode only);
                        f = failed[a["id"]]             # judge_hide: the items learners do not see (HIDE_JUDGE_FAILED)
                        a = {**a, "judge_failed": {str(k): v for k, v in sorted(f.items())},
                             "judge_hide": self.judge_hidden(a.get("kind"), f)}
                    acts.append(a)
            cids, fids = set(), set()
            collect_ids(acts or [], cids, fids)
            kinds = kl.get("concepts") or {}
            for v in kinds.values():
                cids.update(v or [])
            cmap = kl.get("concept_map") or {}
            mrels = []
            for rid in cmap.get("relations") or []:
                r = rels.get(rid)
                if not r:
                    continue
                f0 = (r.get("facts") or [None])[0]
                mrels.append({"id": rid, "from": r.get("subject"), "to": r.get("object"), "label": r.get("label", ""),
                              "fact": f0})
                cids.update((r.get("subject"), r.get("object")))
                if f0:
                    fids.add(f0)
            cids.update(cmap.get("concepts") or [])
            for sg in base["segments"]:
                cids.update(sg.get("concepts") or [])
            before = [{"from": x.get("from"), "kind": x.get("kind"), "concepts": x.get("concepts") or [],
                       "redefined": x.get("redefined") or []}
                      for x in (self.kfile("lecture_graph.json") or {}).get("links") or []
                      if x.get("to") == key and x.get("from") != key]
            for x in before:
                cids.update(x["concepts"])
            keys = self.keys()
            i = keys.index(key) if key in keys else -1
            return {
                "key": key, "title": base["title"], "week": base["week"], "source": base["source"],
                "video": base["video"], "youtube_id": base["youtube_id"],
                "prev": keys[i - 1] if i > 0 else None, "next": keys[i + 1] if 0 <= i < len(keys) - 1 else None,
                "segments": [{k: sg.get(k) for k in ("id", "start", "end", "subgoal", "objective", "concepts")}
                             for sg in base["segments"]],
                "sentences": base["sentences"],
                "goal": kl.get("goal"), "objectives": kl.get("objectives") or [],
                "course_goals": [{"id": g, "goal": (goals.get(g) or {}).get("goal")} for g in kl.get("course_goals") or []],
                "kinds": {k: kinds.get(k) or [] for k in ("introduced", "met_again", "defined_later", "assumed")},
                "prerequisites": kl.get("prerequisites") or {"direct": [], "all": []},
                "before": before,
                "map": {"concepts": cmap.get("concepts") or [], "relations": mrels} if cmap else None,
                "activities": acts,
                "concepts": {c: self.slim_concept(c, concepts[c]) for c in sorted(x for x in cids if x in concepts)},
                "facts": {f: {"text": facts[f].get("text", ""), "lecture": facts[f].get("lecture"),
                              "segment": facts[f].get("segment"), "start": facts[f].get("start")}
                          for f in sorted(x for x in fids if x in facts)},
            }
        return self.memo("view:" + key, paths, build)

    def glossary(self) -> Payload:
        def build():
            out, connecting = [], 0
            concepts = self.kfile("concepts.json") or {}
            has_flag = any("defined" in c for c in concepts.values())     # an older layer without 4a's flag: list all
            for cid, c in concepts.items():
                name = c.get("name") or cid
                also = []
                for a in (c.get("acronyms") or []) + (c.get("aliases") or []):
                    if a and a.lower() != name.lower() and a not in also:
                        also.append(a)
                linked = bool((c.get("relations") or {}).get("out") or (c.get("relations") or {}).get("in"))
                if has_flag and c.get("defined") is not True:     # a connecting concept: on the maps, not listed
                    connecting += 1
                    if linked:                                       # the explorer's search still finds it by name
                        out.append({"id": cid, "name": name, "also": also, "linked": True, "listed": False})
                    continue
                d = (c.get("defined_in") or [None])[0]
                out.append({"id": cid, "name": name, "also": also, "definition": c.get("definition") or "",
                            "lecture": d["lecture"] if d else (c.get("lectures") or [None])[0],
                            "start": d["start"] if d else None, "linked": linked, "listed": True})
            out.sort(key=lambda x: x["name"].lower())
            return {"concepts": out, "connecting": connecting}
        return self.memo("glossary", [self.kd / "concepts.json"], build)

    def concept(self, cid: str) -> Payload | None:
        concepts = self.kfile("concepts.json") or {}
        if cid not in concepts:
            return None

        def build():
            c = concepts[cid]
            facts = self.kfile("facts.json") or {}
            rels = self.kfile("relations.json") or {}
            titles = self.titles()

            def fact(f):
                x = facts.get(f)
                return {"id": f, "text": x.get("text", ""), "lecture": x.get("lecture"), "start": x.get("start")} if x else None

            def side(r):
                o = concepts.get(r.get("concept")) or {}
                rf = (rels.get(r.get("relation")) or {}).get("facts") or []
                return {"relation": r.get("relation"), "label": r.get("label", ""), "concept": r.get("concept"),
                        "name": o.get("name") or r.get("name"), "definition": (o.get("definition") or "")[:400],
                        "defined_in": [{"lecture": d.get("lecture"), "segment": d.get("segment"), "start": d.get("start")}
                                       for d in (o.get("defined_in") or [])[:1]],
                        "lectures": len(o.get("lectures") or []), "fact": fact(rf[0]) if rf else None}
            r = c.get("relations") or {}
            return {"id": cid, **self.slim_concept(cid, c), "aliases": c.get("aliases") or [],
                    "acronyms": c.get("acronyms") or [],
                    "facts": [x for x in (fact(f) for f in (c.get("facts") or [])[:60]) if x],
                    "defining_facts": c.get("defining_facts") or [],
                    "relations": {"out": [side(x) for x in r.get("out") or []], "in": [side(x) for x in r.get("in") or []]},
                    "lectures": [{"key": k, "title": (titles.get(k) or {}).get("title") or f"Lecture {k}"}
                                 for k in c.get("lectures") or []],
                    "dev": {"defined": c.get("defined"), "definition_facts": c.get("definition_facts") or [],
                            "misplaced": c.get("misplaced") or [], "merged": c.get("merged") or []}}
        return self.memo("concept:" + cid, [self.kd / "concepts.json", self.kd / "facts.json",
                                            self.kd / "relations.json", self.inp / "titles.tsv"], build)

    def coursemap(self) -> Payload:
        def build():
            g = self.kfile("lecture_graph.json") or {}
            concepts = self.kfile("concepts.json") or {}
            kinds = g.get("concept_kinds") or {}
            spread = g.get("concepts") or {}
            links = [{"from": x.get("from"), "to": x.get("to"), "concepts": (x.get("concepts") or [])[:3],
                      "more": max(0, len(x.get("concepts") or []) - 3)}
                     for x in g.get("links") or [] if x.get("kind") == "direct"]
            intro = {}
            for k, v in kinds.items():
                ids = sorted(v.get("introduced") or [], key=lambda c: -((spread.get(c) or {}).get("lectures") or 0))
                intro[k] = {"n": len(ids), "top": ids[:8]}
            names = {c for v in intro.values() for c in v["top"]} | {c for x in links for c in x["concepts"]}

            def degree(c):
                r = (concepts.get(c) or {}).get("relations") or {}
                return len(r.get("out") or []) + len(r.get("in") or [])
            first = (g.get("lectures") or [None])[0]
            pool = [c for c, x in concepts.items() if degree(c)]
            early = [c for c in pool if concepts[c].get("first_defined") == first] or pool
            return {"introduced": intro, "links": links, "prerequisites": g.get("prerequisites") or {},
                    "names": {c: (concepts.get(c) or {}).get("name") or c for c in sorted(names)},
                    "start_concept": max(early, key=degree) if early else None}
        return self.memo("coursemap", [self.kd / "lecture_graph.json", self.kd / "concepts.json"], build)

    def review(self) -> Payload:
        def build():
            ac = (load_json(self.ad / "course.json") if self.ad.is_dir() else None) or {}
            return {"cards": [c for c in (ac.get("spaced_review") or {}).get("cards") or [] if c.get("concept")]}
        return self.memo("review", [self.ad / "course.json"], build)

    def warm(self):
        """Build the lean routes once in the background, so the first page does not wait for the big files."""
        t0 = time.time()
        try:
            self.home()
            keys = self.keys()
            if keys:
                self.view(keys[0])
            self.glossary()
            self.coursemap()
            for k in keys[1:]:
                self.view(k)
        except Exception as e:                               # noqa: BLE001  warming is only a speed-up
            print(f"viewer warm-up stopped: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
            return
        print(f"viewer routes ready ({time.time() - t0:.1f} s)", file=sys.stderr, flush=True)


# ---------------------------------------------------------------- question answering
_qa_lock = threading.Lock()


# Which judge-failed items (checks*.json "flags": {"judge_failed": [item numbers]}, the criteria from the judge's
# verdicts) the page shows only in developer mode, per kind (coordinator's decision, 2026-11-17): True hides every
# failed item, a set hides an item that failed any of those criteria; a kind not listed (crossword) is always shown.
# A recap's text (item 0) is never hidden, only its points. Developer mode marks every failed item with its criteria.
HIDE_JUDGE_FAILED: dict = {
    "put_in_order": True, "odd_one_out": True, "open_question": True,
    "quiz": {"answerable", "one_answer", "clear", "no_source_talk"},     # kept: only no_giveaway / worth_asking failed
    "recap": {"no_source_talk"},
}
ITEM_LIST = {"quiz": "questions", "recap": "points", "open_question": "questions", "odd_one_out": "items",
             "put_in_order": "items", "crossword": "entries", "recall": "items", "match_pairs": "pairs"}
QA_PATH = PIPELINE                                       # the folder holding the qa package (--qa-path)
PREFER_YOUTUBE = False                                   # --prefer-youtube: play from YouTube even when the file is here
VIDEO_CHUNK = 4 << 20                                    # an open range ("bytes=N-") is answered with at most this much
VIDEO_PACE = 2.0      # after a first burst, a video is sent at this many times its bitrate (0: as fast as possible); below
VIDEO_BURST = 1 << 20  # the link's speed, so a tunnel never queues video the viewer may skip, and the page's own
                      # requests are not stuck behind it


def qa_paths():
    for p in (PIPELINE, QA_PATH):                            # QA_PATH ends up first
        if str(p) in sys.path:
            sys.path.remove(str(p))
        sys.path.insert(0, str(p))


def load_qa():
    """<qa-path>/qa/ (default pipeline/qa/) as the module `qa`, imported on demand (so it can appear while the
    server runs)."""
    qa_paths()
    with _qa_lock:
        try:
            mod = sys.modules.get("qa")
            if mod is None:                                 # exactly <qa-path>/qa, never another `qa` on sys.path
                init = QA_PATH / "qa" / "__init__.py"
                if not init.exists():
                    raise ImportError(f"no qa package in {QA_PATH}")
                spec = importlib.util.spec_from_file_location("qa", init,
                                                              submodule_search_locations=[str(init.parent)])
                mod = importlib.util.module_from_spec(spec)
                sys.modules["qa"] = mod
                spec.loader.exec_module(mod)
        except Exception:                                   # noqa: BLE001  any import failure means "not available"
            sys.modules.pop("qa", None)
            return None, traceback.format_exc().strip().splitlines()[-1]
    fn = getattr(mod, "answer", None)
    return (fn, None) if callable(fn) else (None, "pipeline/qa has no answer(question, course, lecture)")


def warm_qa(course: str):
    """--warm: import qa and call qa.warm(course) (in a background thread; a failure is printed, not raised)."""
    t0 = time.time()
    fn, err = load_qa()
    mod = sys.modules.get("qa")
    if fn is None or not callable(getattr(mod, "warm", None)):
        print(f"question answering not warmed: {err or 'qa has no warm()'}", file=sys.stderr, flush=True)
        return
    try:
        mod.warm(course)
        print(f"question answering warm ({time.time() - t0:.0f} s)", file=sys.stderr, flush=True)
    except Exception as e:                                   # noqa: BLE001
        print(f"question answering not warmed: {type(e).__name__}: {e}", file=sys.stderr, flush=True)


def qa_status() -> bool:
    return (QA_PATH / "qa" / "__init__.py").exists()


def ask_stream(course: str, req: dict):
    """The events of one answer: qa.answer_stream's ({"event": "step" | "draft" | "reset" | ...}) when qa has it, else
    one "done" with what /api/ask answers; the last event is always {"event": "done", "result": <the /api/ask
    answer>}."""
    q = str(req.get("question") or "").strip()
    mod = None
    if q and load_qa()[0] is not None:
        mod = sys.modules.get("qa")
    stream = getattr(mod, "answer_stream", None) if mod else None
    if not callable(stream):
        yield {"event": "done", "result": ask(course, req)}
        return
    try:
        for ev in stream(q, course, req.get("lecture") or None):
            if not isinstance(ev, dict):
                continue
            if ev.get("event") == "done":
                res = ev.get("result")
                res = dict(res) if isinstance(res, dict) else {"answer": str(res)}
                res.setdefault("citations", [])
                res["available"] = True
                yield {"event": "done", "result": res}
                return
            yield ev
    except Exception as e:                                   # noqa: BLE001
        traceback.print_exc()
        yield {"event": "done", "result": {"available": True, "citations": [], "error": f"{type(e).__name__}: {e}",
                                           "answer": "Something went wrong while answering. Please try again."}}
        return
    yield {"event": "done", "result": {"available": True, "citations": [], "error": "the stream ended without done",
                                       "answer": "Something went wrong while answering. Please try again."}}


def ask(course: str, req: dict) -> dict:
    q = str(req.get("question") or "").strip()
    if not q:
        return {"available": True, "answer": "Please type a question.", "citations": []}
    fn, err = load_qa()
    if fn is None:
        return {"available": False, "citations": [], "error": err,
                "answer": "Question answering is not available yet on this server."}
    lecture = req.get("lecture") or None
    try:
        res = fn(q, course, lecture)
    except Exception as e:                                   # noqa: BLE001
        traceback.print_exc()
        return {"available": True, "citations": [], "error": f"{type(e).__name__}: {e}",
                "answer": "Something went wrong while answering. Please try again."}
    if not isinstance(res, dict):
        res = {"answer": str(res)}
    res.setdefault("citations", [])
    res["available"] = True
    return res


# ---------------------------------------------------------------- HTTP
STATIC_CACHE: dict = {}


def static_payload(path: Path):
    """The file as a Payload (body, gzip, ETag), read again only when it changes; None when it is not there."""
    sig = stat_sig(path)
    if sig is None:
        return None
    hit = STATIC_CACHE.get(path)
    if not hit or hit[0] != sig:
        try:
            STATIC_CACHE[path] = hit = (sig, Payload.raw(path.read_bytes()))
        except OSError:
            return None
    return hit[1]


class Handler(BaseHTTPRequestHandler):
    C: Course = None                                         # set in main()
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        if len(args) >= 2 and ("/api/" in str(args[0]) or str(args[1])[:1] in "45"):
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def send_body(self, body: bytes, ctype: str, code=HTTPStatus.OK, head_only=False, extra=None, cache="no-cache"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def send_json(self, data, code=HTTPStatus.OK, head_only=False):
        self.send_body(json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8", code,
                       head_only)

    def not_found(self, what="not found", head_only=False):
        self.send_json({"error": what}, HTTPStatus.NOT_FOUND, head_only)

    def send_payload(self, pay, ctype="application/json; charset=utf-8", head_only=False, cache="no-cache"):
        """An encoded answer: 304 when the browser has it, gzip when it accepts it."""
        if pay.etag in [t.strip() for t in (self.headers.get("If-None-Match") or "").split(",")]:
            self.send_response(HTTPStatus.NOT_MODIFIED)
            self.send_header("ETag", pay.etag)
            self.send_header("Cache-Control", cache)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        gz = pay.gz is not None and "gzip" in (self.headers.get("Accept-Encoding") or "")
        extra = {"ETag": pay.etag, "Vary": "Accept-Encoding"}
        if gz:
            extra["Content-Encoding"] = "gzip"
        self.send_body(pay.gz if gz else pay.body, ctype, head_only=head_only, extra=extra, cache=cache)

    def send_static(self, path: Path, ctype: str, head_only=False, immutable=False):
        """A file, encoded once until it changes. immutable: the URL carries the file's version (?v=), so the browser
        keeps it for good and never asks again (no round trip through a slow tunnel)."""
        pay = static_payload(path)
        if pay is None:
            return self.not_found(head_only=head_only)
        self.send_payload(pay, ctype, head_only, cache="public, max-age=31536000, immutable" if immutable else "no-cache")

    def send_index(self, head_only=False):
        """index.html with every /static/ file it names given its version (?v=<hash>)."""
        idx = static_payload(HERE / "index.html")
        if idx is None:
            return self.not_found(head_only=head_only)
        vers = tuple((n, (static_payload(HERE / n) or idx).etag.strip('"')[:10])
                     for n in re.findall(r'/static/([\w./-]+?)"', idx.body.decode()))
        key = (idx.etag, vers)
        hit = STATIC_CACHE.get("index")
        if not hit or hit[0] != key:
            html = idx.body.decode()
            for n, v in vers:
                html = html.replace(f'/static/{n}"', f'/static/{n}?v={v}"')
            STATIC_CACHE["index"] = hit = (key, Payload.raw(html.encode()))
        self.send_payload(hit[1], STATIC[".html"], head_only)

    def do_HEAD(self):
        self.do_GET(head_only=True)

    def do_GET(self, head_only=False):
        path = unquote(urlparse(self.path).path)
        C = self.C
        try:
            if path in ("/", "/index.html"):
                return self.send_index(head_only)
            if path == "/favicon.ico":
                return self.send_body(b"", "image/x-icon", HTTPStatus.NO_CONTENT, head_only)
            if path.startswith("/static/"):
                rel = path[len("/static/"):]
                p = (HERE / rel).resolve()
                if ".." in rel or not p.is_file() or HERE not in p.parents or p.suffix not in STATIC:
                    return self.not_found(head_only=head_only)
                return self.send_static(p, STATIC[p.suffix], head_only, immutable="v=" in (urlparse(self.path).query or ""))
            if path == "/api/home":
                return self.send_payload(C.home(), head_only=head_only)
            m = re.fullmatch(r"/api/view/([\w]+)", path)
            if m:
                if not KEY.fullmatch(m[1]):
                    return self.not_found("bad lecture key", head_only)
                if m[1] not in C.keys():
                    return self.not_found("no such lecture", head_only)
                return self.send_payload(C.view(m[1]), head_only=head_only)
            if path == "/api/glossary":
                return self.send_payload(C.glossary(), head_only=head_only)
            m = re.fullmatch(r"/api/concept/(C\d{4,})", path)
            if m:
                pay = C.concept(m[1])
                return self.send_payload(pay, head_only=head_only) if pay else self.not_found("no such concept", head_only)
            if path == "/api/coursemap":
                return self.send_payload(C.coursemap(), head_only=head_only)
            if path == "/api/review":
                return self.send_payload(C.review(), head_only=head_only)
            if path == "/api/course":
                return self.send_json(C.course_info(), head_only=head_only)
            m = re.fullmatch(r"/api/lecture/([\w]+)", path)
            if m:
                if not KEY.fullmatch(m[1]):
                    return self.not_found("bad lecture key", head_only)
                return self.send_json(C.lecture(m[1]), head_only=head_only)
            m = re.fullmatch(r"/data/(knowledge|activities)/(.+)", path)
            if m:
                folder = C.kd if m[1] == "knowledge" else C.ad
                if not FILE.fullmatch(m[2]) or m[2] == "fact_embeddings.json":
                    return self.not_found(head_only=head_only)
                return self.send_static(folder / m[2], "application/json; charset=utf-8", head_only)
            m = re.fullmatch(r"/media/([\w]+)(?:\.mp4)?", path)
            if m:
                p = C.video(m[1]) if KEY.fullmatch(m[1]) else None
                if p is None:
                    return self.not_found("no video for this lecture", head_only)
                return self.send_video(p, head_only, mp4_duration(p) or C.duration(m[1]))
            return self.not_found(head_only=head_only)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def send_video(self, path: Path, head_only=False, duration: float | None = None):
        size = path.stat().st_size
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        code = HTTPStatus.OK
        if rng:
            m = re.fullmatch(r"\s*bytes=(\d*)-(\d*)\s*", rng)
            if not m or (not m[1] and not m[2]):
                return self._unsatisfiable(size)
            if m[1]:
                start = int(m[1])
                # an open range gets one chunk: through a slow link the bytes of a position the viewer has left
                # do not keep filling the pipe after a seek (the browser asks for the next chunk as it plays)
                end = min(int(m[2]), size - 1) if m[2] else min(size - 1, start + VIDEO_CHUNK - 1)
            else:                                            # suffix range: the last N bytes
                start, end = max(0, size - int(m[2])), size - 1
            if start > end or start >= size:
                return self._unsatisfiable(size)
            code = HTTPStatus.PARTIAL_CONTENT
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        st = path.stat()
        self.send_header("ETag", f'"v{st.st_mtime_ns:x}-{size:x}"')
        self.send_header("Last-Modified", self.date_time_string(int(st.st_mtime)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(end - start + 1))
        if code == HTTPStatus.PARTIAL_CONTENT:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if head_only:
            return
        rate = VIDEO_PACE * size / duration if VIDEO_PACE and duration and duration > 60 else None   # bytes/s
        t0, sent = time.monotonic(), 0
        with open(path, "rb") as f:
            f.seek(start)
            left = end - start + 1
            while left > 0:
                chunk = f.read(min(64 << 10, left))
                if not chunk:
                    break
                self.wfile.write(chunk)
                left -= len(chunk)
                sent += len(chunk)
                if rate and sent > VIDEO_BURST:
                    ahead = (sent - VIDEO_BURST) / rate - (time.monotonic() - t0)
                    if ahead > 0:
                        time.sleep(ahead)

    def _unsatisfiable(self, size: int):
        self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
        self.send_header("Content-Range", f"bytes */{size}")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        path = urlparse(self.path).path
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b""
        if path not in ("/api/ask", "/api/ask_stream"):
            return self.not_found()
        try:
            req = json.loads(raw or b"{}")
            if not isinstance(req, dict):
                raise ValueError("expected a JSON object")
        except ValueError as e:
            return self.send_json({"error": f"bad request: {e}"}, HTTPStatus.BAD_REQUEST)
        if path == "/api/ask":
            return self.send_json(ask(self.C.course, req))
        # one JSON event per line, each sent as it comes (chunked; no gzip, nothing held back by the server)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        try:
            for ev in ask_stream(self.C.course, req):
                line = json.dumps(ev, ensure_ascii=False).encode() + b"\n"
                self.wfile.write(b"%x\r\n%s\r\n" % (len(line), line))
                self.wfile.flush()
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True


def make_server(course: str, root: Path, port: int, host="127.0.0.1", media: Path | None = None,
                output: Path | None = None, activities: str = "activities"):
    Handler.C = Course(course, root, media, output, activities)
    ThreadingHTTPServer.daemon_threads = True
    return ThreadingHTTPServer((host, port), Handler)


def main():
    global QA_PATH, PREFER_YOUTUBE, VIDEO_CHUNK, VIDEO_PACE
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("course", help="course folder name, e.g. nptel_vr")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--root", type=Path, default=PIPELINE, help="the pipeline folder to read (default: this one)")
    ap.add_argument("--media", type=Path, help="folder of the videos (default: <root>/input/<course>/media)")
    ap.add_argument("--output", type=Path,
                    help="the output folder to read the layers from (default: <root>/output; e.g. a synced copy)")
    ap.add_argument("--activities", default="activities",
                    help="the activities folder name under output/<course> (default: activities)")
    ap.add_argument("--qa-path", type=Path, help="folder holding the qa package (default: the pipeline folder)")
    ap.add_argument("--warm", action="store_true", help="load qa and call qa.warm(course) at start (background)")
    ap.add_argument("--prefer-youtube", action="store_true",
                    help="play every lecture that has a youtube_id from YouTube, even when its file is here (a slow "
                         "tunnel); the page's ?yt=1 / ?yt=0 does the same per browser")
    ap.add_argument("--video-chunk-mb", type=float, default=VIDEO_CHUNK / (1 << 20),
                    help="the most an open video range is answered with (default 4)")
    ap.add_argument("--video-pace", type=float, default=VIDEO_PACE,
                    help="send a video at most this many times its bitrate after the first MB (default 2; 0 = no limit)")
    a = ap.parse_args()
    PREFER_YOUTUBE = a.prefer_youtube
    VIDEO_PACE = max(0.0, a.video_pace)
    VIDEO_CHUNK = max(256 << 10, int(a.video_chunk_mb * (1 << 20)))
    if a.qa_path:
        QA_PATH = a.qa_path.resolve()
    root = a.root.resolve()
    output = a.output.resolve() if a.output else None
    if not (root / "input" / a.course).is_dir() and not ((output or root / "output") / a.course).is_dir():
        sys.exit(f"no course {a.course!r} under {root}/input or {output or root / 'output'}")
    srv = make_server(a.course, root, a.port, a.host, a.media.resolve() if a.media else None, output, a.activities)
    C = Handler.C
    info = C.course_info()
    n = len(info["lectures"])
    has = lambda k: sum(1 for x in info["lectures"] if x["has"][k])  # noqa: E731
    print(f"viewer for {a.course} ({n} lectures): http://{a.host}:{a.port}/   (dev mode: /?dev=1; Ctrl+C to stop)")
    yt = sum(1 for x in info["lectures"] if x["has"]["youtube"] and not x["has"]["video"])
    print(f"  segments {has('segments')}, knowledge {has('knowledge')}, activities {has('activities')}, "
          f"videos {has('video')} (from {C.media}; {yt} more from YouTube); question answering "
          f"{'importable' if info['qa'] else 'not available (no pipeline/qa)'}", flush=True)
    threading.Thread(target=C.warm, daemon=True).start()
    if a.warm and info["qa"]:
        threading.Thread(target=warm_qa, args=(a.course,), daemon=True).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
