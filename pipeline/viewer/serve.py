#!/usr/bin/env python3
"""The v3 viewer: a standard-library HTTP server for the static viewer, the course's JSON layers and the videos.

    python pipeline/viewer/serve.py nptel_vr [--port 8765] [--host 127.0.0.1] [--root PIPELINE_DIR] [--media DIR]
                                             [--qa-path DIR]

Then open http://localhost:8765 (add ?dev=1, or use the toggle, for developer mode).

Reads (never writes) under <root> (default: the pipeline folder this file sits in):
    input/<course>/input/course.json, titles.tsv           course title, syllabus, lecture titles and weeks
    output/<course>/stage_1b_verify_segments/segment_maps/  segments with sub-goals and times (used when knowledge/
                                                            has no file for a lecture)
    output/<course>/stage_0a_preprocess/lec_<n>.json, times/ sentences and their times (the transcript)
    output/<course>/knowledge/                              stage 4d's layer (optional, per lecture)
    output/<course>/activities/                             the activities (optional, per lecture; schemas/activities.md)
    input/<course>/media/L01.mp4 ...                        the videos (optional; or --media DIR)

Routes
    GET  /                          the viewer (index.html); /static/... its files
    GET  /api/course                the course: title, syllabus, goals, lectures (title, week, goal, which layers
                                    exist), the layers present
    GET  /api/lecture/<key>         one lecture: segments (from knowledge/, else 1b), sentences (0a), the knowledge
                                    lecture file or null, the activities file or null, where the segments came from
    GET  /data/knowledge/<file>     a knowledge/ file (concepts.json, facts.json, ..., lectures/lec_<n>.json);
                                    fact_embeddings.json is not served
    GET  /data/activities/<file>    an activities/ file (lec_<n>.json, course.json)
    GET  /media/<key>               a lecture's video, with HTTP Range (so seeking works)
    POST /api/ask                   {"question", "lecture"} -> qa.answer(question, course, lecture) from pipeline/qa/
                                    when importable, else {"available": false, "answer": "...not available..."}
A missing layer is never an error for the course or lecture routes: it comes back as null (or the segments fall back
to 1b), and the raw /data/ routes answer 404 for a file that does not exist.
"""
from __future__ import annotations

import argparse
import csv
import importlib
import importlib.util
import json
import mimetypes
import re
import sys
import threading
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


class Course:
    """Paths and loaders for one course; every load is fresh, so new outputs show on a reload."""

    def __init__(self, course: str, root: Path, media: Path | None = None):
        self.course, self.root = course, root
        self.inp = root / "input" / course / "input"
        self.out = root / "output" / course
        self.kd = self.out / "knowledge"
        self.ad = self.out / "activities"
        self.media = media or (root / "input" / course / "media")

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
        return read_json(self.kd / name) if self.kd.is_dir() else None

    def lecture_goal(self, goals, key):
        if not goals:
            return None
        for g in (goals.get("lecture_goals") or {}).values():
            if g.get("lecture") == key:
                return g.get("goal")
        return None

    def course_info(self) -> dict:
        meta = read_json(self.inp / "course.json") or {}
        titles = self.titles()
        index = self.knowledge("index.json")
        goals = self.knowledge("goals.json")
        graph = self.knowledge("lecture_graph.json")
        assumed = self.knowledge("assumed.json")
        acourse = read_json(self.ad / "course.json") if self.ad.is_dir() else None
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
                        "video": self.video(k) is not None}})
        return {"course": self.course, "title": meta.get("title") or (index or {}).get("title") or self.course,
                "meta": {f: meta.get(f) for f in ("platform", "institution", "instructor", "prerequisites",
                                                  "intended_audience", "outline", "syllabus")},
                "layers": {"knowledge": index is not None, "activities": self.ad.is_dir(),
                           "spaced_review": bool(acourse and acourse.get("spaced_review"))},
                "index": index, "goals": goals, "assumed": assumed, "lectures": lectures,
                "qa": qa_status()}

    def lecture(self, key: str) -> dict:
        stem = stem_of(key)
        kl = read_json(self.kd / "lectures" / f"{stem}.json") if self.kd.is_dir() else None
        segs = read_json(self.out / "stage_1b_verify_segments" / "segment_maps" / f"{stem}.json")
        source = "knowledge" if kl else ("segments" if segs else "none")
        segments = []
        for sid, s in ((kl or {}).get("segments") or segs or {}).items():
            segments.append({"id": sid, "first": s.get("first"), "last": s.get("last"), "start": s.get("start", 0.0),
                             "end": s.get("end", 0.0), "subgoal": s.get("subgoal", ""),
                             "objective": s.get("objective"), "facts": s.get("facts", []),
                             "concepts": s.get("concepts", [])})
        segments.sort(key=lambda s: s["start"] or 0)
        texts = read_json(self.out / "stage_0a_preprocess" / f"{stem}.json") or {}
        times = read_json(self.out / "stage_0a_preprocess" / "times" / f"{stem}.json") or {}
        sentences, prev = [], 0.0
        for sid, txt in texts.items():                       # a missing start (0a has some) is the previous end
            t = times.get(sid) or {}
            start = t.get("start") if t.get("start") is not None else prev
            end = t.get("end") if t.get("end") is not None else start
            sentences.append({"id": sid, "text": txt, "start": start, "end": end})
            prev = end
        acts = read_json(self.ad / f"{stem}.json") if self.ad.is_dir() else None
        t = self.titles().get(key, {})
        return {"key": key, "title": (kl or {}).get("title") or t.get("title") or f"Lecture {key}",
                "week": t.get("week", ""), "source": source, "segments": segments, "sentences": sentences,
                "knowledge": kl, "activities": acts, "video": self.video(key) is not None}


# ---------------------------------------------------------------- question answering
_qa_lock = threading.Lock()


QA_PATH = PIPELINE                                       # the folder holding the qa package (--qa-path)


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
            mod = sys.modules.get("qa") or importlib.import_module("qa")
        except Exception:                                   # noqa: BLE001  any import failure means "not available"
            sys.modules.pop("qa", None)
            return None, traceback.format_exc().strip().splitlines()[-1]
    fn = getattr(mod, "answer", None)
    return (fn, None) if callable(fn) else (None, "pipeline/qa has no answer(question, course, lecture)")


def qa_status() -> bool:
    qa_paths()
    try:
        return importlib.util.find_spec("qa") is not None
    except (ImportError, ValueError):
        return False


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
class Handler(BaseHTTPRequestHandler):
    C: Course = None                                         # set in main()
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        if len(args) >= 2 and ("/api/" in str(args[0]) or str(args[1])[:1] in "45"):
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def send_body(self, body: bytes, ctype: str, code=HTTPStatus.OK, head_only=False, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
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

    def send_file(self, path: Path, ctype: str, head_only=False):
        try:
            self.send_body(path.read_bytes(), ctype, head_only=head_only)
        except OSError:
            self.not_found(head_only=head_only)

    def do_HEAD(self):
        self.do_GET(head_only=True)

    def do_GET(self, head_only=False):
        path = unquote(urlparse(self.path).path)
        C = self.C
        try:
            if path in ("/", "/index.html"):
                return self.send_file(HERE / "index.html", STATIC[".html"], head_only)
            if path == "/favicon.ico":
                return self.send_body(b"", "image/x-icon", HTTPStatus.NO_CONTENT, head_only)
            if path.startswith("/static/"):
                rel = path[len("/static/"):]
                p = (HERE / rel).resolve()
                if ".." in rel or not p.is_file() or HERE not in p.parents or p.suffix not in STATIC:
                    return self.not_found(head_only=head_only)
                return self.send_file(p, STATIC[p.suffix], head_only)
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
                return self.send_file(folder / m[2], "application/json; charset=utf-8", head_only)
            m = re.fullmatch(r"/media/([\w]+)(?:\.mp4)?", path)
            if m:
                p = C.video(m[1]) if KEY.fullmatch(m[1]) else None
                if p is None:
                    return self.not_found("no video for this lecture", head_only)
                return self.send_video(p, head_only)
            return self.not_found(head_only=head_only)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def send_video(self, path: Path, head_only=False):
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
                end = min(int(m[2]), size - 1) if m[2] else size - 1
            else:                                            # suffix range: the last N bytes
                start, end = max(0, size - int(m[2])), size - 1
            if start > end or start >= size:
                return self._unsatisfiable(size)
            code = HTTPStatus.PARTIAL_CONTENT
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if code == HTTPStatus.PARTIAL_CONTENT:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if head_only:
            return
        with open(path, "rb") as f:
            f.seek(start)
            left = end - start + 1
            while left > 0:
                chunk = f.read(min(1 << 20, left))
                if not chunk:
                    break
                self.wfile.write(chunk)
                left -= len(chunk)

    def _unsatisfiable(self, size: int):
        self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
        self.send_header("Content-Range", f"bytes */{size}")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        path = urlparse(self.path).path
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b""
        if path != "/api/ask":
            return self.not_found()
        try:
            req = json.loads(raw or b"{}")
            if not isinstance(req, dict):
                raise ValueError("expected a JSON object")
        except ValueError as e:
            return self.send_json({"error": f"bad request: {e}"}, HTTPStatus.BAD_REQUEST)
        self.send_json(ask(self.C.course, req))


def make_server(course: str, root: Path, port: int, host="127.0.0.1", media: Path | None = None):
    Handler.C = Course(course, root, media)
    ThreadingHTTPServer.daemon_threads = True
    return ThreadingHTTPServer((host, port), Handler)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("course", help="course folder name, e.g. nptel_vr")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--root", type=Path, default=PIPELINE, help="the pipeline folder to read (default: this one)")
    ap.add_argument("--media", type=Path, help="folder of the videos (default: <root>/input/<course>/media)")
    ap.add_argument("--qa-path", type=Path, help="folder holding the qa package (default: the pipeline folder)")
    a = ap.parse_args()
    global QA_PATH
    if a.qa_path:
        QA_PATH = a.qa_path.resolve()
    root = a.root.resolve()
    if not (root / "input" / a.course).is_dir() and not (root / "output" / a.course).is_dir():
        sys.exit(f"no course {a.course!r} under {root}/input or {root}/output")
    srv = make_server(a.course, root, a.port, a.host, a.media.resolve() if a.media else None)
    C = Handler.C
    info = C.course_info()
    n = len(info["lectures"])
    has = lambda k: sum(1 for x in info["lectures"] if x["has"][k])  # noqa: E731
    print(f"viewer for {a.course} ({n} lectures): http://{a.host}:{a.port}/   (dev mode: /?dev=1; Ctrl+C to stop)")
    print(f"  segments {has('segments')}, knowledge {has('knowledge')}, activities {has('activities')}, "
          f"videos {has('video')} (from {C.media}); question answering "
          f"{'importable' if info['qa'] else 'not available (no pipeline/qa)'}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
