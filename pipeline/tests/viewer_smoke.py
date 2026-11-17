"""Smoke test of the v3 viewer server (viewer/serve.py) over a temporary copy with a synthetic knowledge layer and
synthetic activities.

    python3 tests/viewer_smoke.py [--work DIR] [--keep] [--knowledge DIR]

The copy holds the course's input metadata (course.json, titles.tsv), the real 1b segment maps and 0a sentences and
times of all lectures, a synthetic knowledge/ (from tests/fake_knowledge.py, lectures 1 to 8, unless --knowledge
names an existing knowledge/ folder), synthetic activities for lectures 1 to 3 (every kind of schemas/activities.md)
plus activities/course.json, and a small fake video L01.mp4 (bytes only: the test checks the Range plumbing, not
playback). Lecture 63's segment map is removed in the copy, so one lecture has neither knowledge nor segments.
Servers listen on free ports (never 8094 or 8095, the SSH forward to the EC2).

What it looks for (each line is what a broken viewer server would show):
  static     the page, app.js, style.css or the vendored dagre not served, or served with the wrong type;
             a path outside the viewer folder served (../)
  course     /api/course missing a lecture of titles.tsv, the layers not reported, a lecture's goal or flags wrong
  lecture    a lecture route failing; segments missing; knowledge not used where it exists (1-8), the 1b fallback
             not used where it does not (9-62); a lecture with no layer at all (63) failing instead of answering
             with no segments; activities missing where they exist or invented where they do not
  data       a knowledge/ or activities/ file not served or not equal to the file; fact_embeddings.json served;
             a missing file answered with anything but 404
  range      a Range request answered with the whole file, wrong bytes, a wrong Content-Range or length; an open
             or suffix range wrong; an unsatisfiable range not 416; a lecture without a video not 404, or without
             the youtube_id of titles.tsv (the page's fallback player)
  ask        no qa package: anything but a clear "not available" answer; a qa package: the answer and citations
             not passed through, the lecture not passed in; a qa that raises: a server error instead of a message
  degrade    a copy without knowledge/ and activities/: the course or a lecture failing, the layers reported as
             present, a lecture not falling back to its 1b segments
  lean       the page's routes (/api/home, /api/view/<k> with "before", /api/glossary with "linked" and only the
             concepts 4a defined listed, /api/concept, /api/coursemap, /api/review) failing or missing fields; a
             connecting concept's card not opening; no gzip, no ETag, no 304 on If-None-Match
  judge      a judge-failed item (checks.json "flags": {"judge_failed"}) not reported with its criteria, or the
             per-kind rule not applied (a quiz item failed on "answerable" not hidden, one failed only on
             "no_giveaway" hidden; a crossword hidden)
  versioned  index.html without ?v= on its static files; a versioned file without the long immutable cache
  stream     /api/ask_stream: not one JSON event per line, the qa's step/draft/reset events not passed on in order,
             no final "done" with the answer; a qa without answer_stream or no qa: not a single "done" like /api/ask
  js         app.js not valid JavaScript (node --check, when node is installed); app.js fetching the big knowledge
             files (/data/knowledge/...) instead of the lean routes
  output     any file under the real output/ created or changed
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the pipeline folder
COURSE = "nptel_vr"
FORBIDDEN = {8094, 8095}
FAILURES: list[str] = []
VIDEO = bytes((i * 7 + 3) % 256 for i in range(600_000))   # larger than the open-range chunk the test sets (256 kB)
CHUNK = 256 << 10
N = len(VIDEO)


def check(ok: bool, what: str):
    print(f"  {'ok  ' if ok else 'FAIL'} {what}", flush=True)
    if not ok:
        FAILURES.append(what)


def free_port() -> int:
    while True:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        if port not in FORBIDDEN:
            return port


def snapshot(folder: Path) -> dict:
    return {str(p.relative_to(folder)): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in folder.rglob("*") if p.is_file()}


# ---------------------------------------------------------------- the copy
def make_root(root: Path, knowledge: Path | None, activities: bool):
    meta = root / "input" / COURSE / "input"
    meta.mkdir(parents=True)
    for f in ("course.json", "titles.tsv"):
        shutil.copy(ROOT / "input" / COURSE / "input" / f, meta / f)
    src, dst = ROOT / "output" / COURSE, root / "output" / COURSE
    shutil.copytree(src / "stage_1b_verify_segments" / "segment_maps", dst / "stage_1b_verify_segments" / "segment_maps")
    (dst / "stage_0a_preprocess").mkdir(parents=True)
    for p in (src / "stage_0a_preprocess").glob("lec_*.json"):
        shutil.copy(p, dst / "stage_0a_preprocess" / p.name)
    shutil.copytree(src / "stage_0a_preprocess" / "times", dst / "stage_0a_preprocess" / "times")
    (dst / "stage_1b_verify_segments" / "segment_maps" / "lec_63.json").unlink()
    media = root / "input" / COURSE / "media"
    media.mkdir(parents=True)
    (media / "L01.mp4").write_bytes(VIDEO)
    if knowledge:
        shutil.copytree(knowledge, dst / "knowledge")
    if activities and knowledge:
        write_activities(dst / "knowledge", dst / "activities", ["1", "2", "3"])


def build_knowledge(work: Path) -> Path:
    """tests/fake_knowledge.py in its own folder; its knowledge/ (lectures 1 to 8)."""
    fk = work / "fake_knowledge"
    r = subprocess.run([sys.executable, str(ROOT / "tests" / "fake_knowledge.py"), "--work", str(fk), "--keep"],
                       capture_output=True, text=True)
    kd = fk / "output" / COURSE / "knowledge"
    check(kd.is_dir(), f"tests/fake_knowledge.py built a synthetic knowledge layer (exit {r.returncode})")
    if not kd.is_dir():
        print(r.stdout[-2000:], r.stderr[-2000:])
        sys.exit(1)
    return kd


def write_activities(kd: Path, ad: Path, keys: list[str]):
    """Synthetic activities per schemas/activities.md: every kind, IDs from the knowledge layer."""
    concepts = json.loads((kd / "concepts.json").read_text())
    facts = json.loads((kd / "facts.json").read_text())
    relations = json.loads((kd / "relations.json").read_text())
    ad.mkdir(parents=True)
    names = {cid: c["name"] for cid, c in concepts.items()}
    allc = list(concepts)
    for k in keys:
        L = json.loads((kd / "lectures" / f"lec_{k}.json").read_text())
        acts, n = [], 0

        def add(kind, scope, seg, title, data, fids, cids):
            nonlocal n
            acts.append({"id": f"{k}/A{n}", "kind": kind, "scope": scope, "segment": seg, "title": title,
                         "data": data, "facts": fids, "concepts": cids})
            n += 1
        lc = L["concept_map"]["concepts"] or allc[:3]
        prev = [c for c in allc if concepts[c].get("first_defined") and concepts[c]["first_defined"] != k][:3]
        add("recall", "lecture", None, "What you met before",
            {"items": [{"concept": c, "prompt": f"What is {names[c]}?", "answer": concepts[c]["definition"] or "-",
                        "from_lecture": concepts[c]["first_defined"]} for c in prev or lc[:2]]}, [], prev)
        for sid, seg in L["segments"].items():
            fs = seg["facts"][:2]
            if not fs:
                continue
            others = [names[c] for c in allc if c not in seg["concepts"]][:3]
            right = names[seg["concepts"][0]] if seg["concepts"] else "virtual reality"
            add("quiz", "segment", sid, "Check this part",
                {"questions": [{"question": f"Which concept does this part explain? ({facts[fs[0]]['text']})",
                                "options": [right] + (others + ["none of these"] * 3)[:3], "answer": 0,
                                "explanation": facts[fs[0]]["text"], "facts": [fs[0]]}]}, fs[:1], seg["concepts"][:1])
            add("recap", "segment", sid, "In short",
                {"text": seg["subgoal"], "points": [facts[f]["text"] for f in fs]}, fs, seg["concepts"])
        f0 = [f for s in L["segments"].values() for f in s["facts"]]
        add("open_question", "lecture", None, "Think it through",
            {"questions": [{"question": f"How do the concepts of lecture {k} fit together?",
                            "reference_answer": " ".join(facts[f]["text"] for f in f0[:2]),
                            "key_facts": f0[:2], "concepts": lc[:2]}]}, f0[:2], lc[:2])
        rels = list(relations.items()) or []
        nodes = sorted({c for _, r in rels for c in (r["subject"], r["object"])} | set(lc[:3]))
        edges = [{"from": r["subject"], "to": r["object"], "label": r["label"], "relation": rid} for rid, r in rels]
        cmap = {"nodes": [{"id": c, "label": names[c]} for c in nodes], "edges": edges}
        add("concept_map", "lecture", None, "How the concepts connect", cmap, [f for _, r in rels for f in r["facts"]],
            nodes)
        if edges:
            blanks = [{"edge": 0, "hide": "label", "answer": edges[0]["label"],
                       "options": [edges[0]["label"], "is a part of", "is the opposite of"]}]
            if len(edges) > 1:
                blanks.append({"edge": 1, "hide": "from", "answer": names[edges[1]["from"]],
                               "options": [names[edges[1]["from"]], names[nodes[0]], "latency"]})
            add("complete_map", "lecture", None, "Fill in the map", {**cmap, "blanks": blanks},
                [f for _, r in rels for f in r["facts"]], nodes)
        add("crossword", "lecture", None, "Crossword",
            {"width": 8, "height": 6, "entries": [
                {"number": 1, "answer": "LATENCY", "clue": "Delay between a movement and its display", "row": 0,
                 "col": 0, "direction": "across", "concept": "C0010"},
                {"number": 2, "answer": "TRACKING", "clue": "Following the user's position", "row": 0, "col": 3,
                 "direction": "down", "concept": "C0007"},
                {"number": 3, "answer": "HMD", "clue": "A display worn on the head (acronym)", "row": 4, "col": 2,
                 "direction": "across", "concept": "C0004"}]}, [], ["C0010", "C0007", "C0004"])
        add("match_pairs", "lecture", None, "Match the terms",
            {"pairs": [{"left": names[c], "right": concepts[c]["definition"] or names[c], "concept": c}
                       for c in allc[:4]]}, [], allc[:4])
        add("odd_one_out", "lecture", None, "Odd one out",
            {"items": [{"options": ["head-mounted display", "field of view", "display resolution", "presence"],
                        "odd": 3, "reason": "Presence is an experience, the others are properties of a display.",
                        "facts": f0[:1]}]}, f0[:1], allc[:4])
        add("put_in_order", "lecture", None, "Steps",
            {"items": [{"title": "From movement to image", "steps": ["Track the head", "Update the view",
                                                                     "Render the frame", "Show it on the display"],
                        "facts": f0[:2]}]}, f0[:2], [])
        (ad / f"lec_{k}.json").write_text(json.dumps({"lecture": k, "activities": acts}, indent=1))
        if k == "1":
            write_checks(ad, acts)
    (ad / "course.json").write_text(json.dumps({"spaced_review": {"cards": [
        {"concept": cid, "front": c["name"], "back": c["definition"] or c["name"], "lectures": c["lectures"]}
        for cid, c in concepts.items()]}}, indent=1))


def write_checks(ad: Path, acts: list[dict]):
    """checks.json for lecture 1 as s5 writes it: two quizzes judge-failed (one on "answerable", one only on
    "no_giveaway"), a crossword judge-failed, an odd_one_out unresolved by the code checks."""
    quiz = [a["id"] for a in acts if a["kind"] == "quiz"][:2]
    cw = next(a["id"] for a in acts if a["kind"] == "crossword")
    odd = next(a["id"] for a in acts if a["kind"] == "odd_one_out")

    def judged(aid, crit):
        return {"status": "ok", "activity": aid, "flags": {"judge_failed": [1]},
                "judge": {"rounds": [{"status": "ok", "verdicts": [{"item": 1, "pass": False, "failed": crit,
                                                                    "reason": "a reason"}], "failed_items": [1]}],
                          "kept": "original", "failed_items": [1]}}
    (ad / "checks.json").write_text(json.dumps({"lectures": {"1": {
        "quiz": {"quiz:1/a": judged(quiz[0], ["answerable", "no_giveaway"]), "quiz:1/b": judged(quiz[1], ["no_giveaway"])},
        "crossword": {"crossword:1": judged(cw, ["clear"])},
        "odd_one_out": {"odd_one_out:1": {"status": "unresolved", "activity": odd, "problems": ["two odd ones"]}}}}}))


def write_fake_qa(folder: Path, raising: bool = False, stream: bool = False):
    (folder / "qa").mkdir(parents=True)
    body = ("def answer(question, course, lecture):\n"
            + ("    raise RuntimeError('model server down')\n" if raising else
               "    return {'answer': f'echo: {question} ({course}, {lecture})', 'covered': True, 'steps': [],\n"
               "            'citations': [{'fact': '1/S0/F0', 'lecture': '1', 'segment': '1/S0', 'start': 24.3,\n"
               "                           'end': 31.9, 'text': 'a fact'}]}\n"))
    if stream:
        body += ("def answer_stream(question, course, lecture):\n"
                 "    yield {'event': 'step', 'tool': 'fact_lookup', 'args': {'query': question}, 'result_summary': '2 facts'}\n"
                 "    yield {'event': 'draft', 'text': 'Wrong start'}\n"
                 "    yield {'event': 'reset'}\n"
                 "    yield {'event': 'draft', 'text': 'echo:'}\n"
                 "    yield {'event': 'done', 'result': answer(question, course, lecture)}\n")
    (folder / "qa" / "__init__.py").write_text(body)


# ---------------------------------------------------------------- HTTP
class Server:
    def __init__(self, root: Path, qa_path: Path, log: Path):
        self.port = free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        self.log = open(log, "w")
        self.p = subprocess.Popen([sys.executable, str(ROOT / "viewer" / "serve.py"), COURSE, "--port", str(self.port),
                                   "--root", str(root), "--qa-path", str(qa_path),
                                   "--video-chunk-mb", str(CHUNK / (1 << 20))], stdout=self.log, stderr=self.log)
        for _ in range(100):
            try:
                urllib.request.urlopen(self.base + "/api/course", timeout=2)
                return
            except (urllib.error.URLError, ConnectionError):
                time.sleep(0.1)
        check(False, f"the server started on port {self.port}")

    def get(self, path, headers=None, method="GET", data=None):
        req = urllib.request.Request(self.base + path, headers=headers or {}, method=method, data=data)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read()

    def json(self, path, **kw):
        code, hd, body = self.get(path, **kw)
        try:
            return code, json.loads(body or b"null")
        except ValueError:
            return code, None

    def ask(self, q, lecture):
        return self.json("/api/ask", method="POST", data=json.dumps({"question": q, "lecture": lecture}).encode(),
                         headers={"Content-Type": "application/json"})

    def stream(self, q, lecture):
        """/api/ask_stream: (status, content type, the events, every line parsed)."""
        req = urllib.request.Request(self.base + "/api/ask_stream", method="POST",
                                     data=json.dumps({"question": q, "lecture": lecture}).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            lines = r.read().decode().splitlines()
            evs = []
            for ln in lines:
                try:
                    evs.append(json.loads(ln))
                except ValueError:
                    evs.append(None)
            return r.status, r.headers.get("Content-Type", ""), evs

    def stop(self):
        self.p.terminate()
        self.p.wait(5)
        self.log.close()


# ---------------------------------------------------------------- tests
def test_full(srv: Server, root: Path):
    out = root / "output" / COURSE
    print("static", flush=True)
    for path, ctype in (("/", "text/html"), ("/static/app.js", "javascript"), ("/static/style.css", "text/css"),
                        ("/static/vendor/dagre.min.js", "javascript")):
        code, hd, body = srv.get(path)
        check(code == 200 and ctype in hd.get("Content-Type", "") and len(body) > 100, f"{path} served ({code})")
    code, _, _ = srv.get("/static/../serve.py")
    code2, _, _ = srv.get("/static/%2e%2e/serve.py")
    check(code == 404 and code2 == 404, "no file outside the viewer folder under /static/")

    print("course", flush=True)
    code, C = srv.json("/api/course")
    keys = [l["key"] for l in C["lectures"]]
    check(code == 200 and keys == [str(i) for i in range(1, 64)], f"/api/course lists lectures 1..63 ({len(keys)})")
    check(C["layers"] == {"knowledge": True, "activities": True, "spaced_review": True}, f"layers {C['layers']}")
    check(C["title"].startswith("Foundation"), "the course title from course.json")
    by = {l["key"]: l for l in C["lectures"]}
    check(all(by[k]["goal"] for k in map(str, range(1, 8))) and by["9"]["goal"] is None,
          "lecture goals for lectures with knowledge, none without")
    check([k for k in keys if by[k]["has"]["knowledge"]] == [str(i) for i in range(1, 9)]
          and [k for k in keys if by[k]["has"]["activities"]] == ["1", "2", "3"]
          and [k for k in keys if by[k]["has"]["video"]] == ["1"], "per-lecture layer flags")
    check(C["qa"] is False, "question answering reported as not importable")

    print("lecture", flush=True)
    bad = []
    for k in keys:
        code, L = srv.json(f"/api/lecture/{k}")
        if code != 200 or L is None:
            bad.append(f"{k}: {code}")
            continue
        want = "knowledge" if int(k) <= 8 else "none" if k == "63" else "segments"
        if L["source"] != want:
            bad.append(f"{k}: source {L['source']}, want {want}")
        if want != "none" and not (L["segments"] and all(s["subgoal"] and s["end"] > s["start"] for s in L["segments"])):
            bad.append(f"{k}: segments missing or without sub-goal/times")
        if want == "none" and L["segments"]:
            bad.append(f"{k}: segments without a source")
        if not L["sentences"] or any(s["start"] is None for s in L["sentences"]):
            bad.append(f"{k}: sentences or times missing")
        if (L["knowledge"] is not None) != (int(k) <= 8):
            bad.append(f"{k}: knowledge {'missing' if L['knowledge'] is None else 'invented'}")
        if (L["activities"] is not None) != (k in ("1", "2", "3")):
            bad.append(f"{k}: activities {'missing' if L['activities'] is None else 'invented'}")
        if L["video"] != (k == "1"):
            bad.append(f"{k}: video flag {L['video']}")
    check(not bad, f"every lecture route answers with the right sources ({len(keys)} lectures) {bad[:5]}")
    _, L1 = srv.json("/api/lecture/1")
    check(L1["segments"][0]["facts"] and L1["segments"][0]["concepts"] is not None and L1["knowledge"]["goal"],
          "a knowledge lecture carries facts, concepts and its goal")
    code, _ = srv.json("/api/lecture/..%2fsecret")
    check(code == 404, "a bad lecture key is 404")

    print("data", flush=True)
    kd, ad = out / "knowledge", out / "activities"
    files = sorted(str(p.relative_to(kd)) for p in kd.rglob("*.json") if p.name != "fact_embeddings.json")
    bad = [f for f in files if srv.get(f"/data/knowledge/{f}")[2] != (kd / f).read_bytes()]
    check(not bad and len(files) == 8 + len(list((kd / "lectures").glob("*.json"))) and len(files) > 8,
          f"every knowledge/ file served as is ({len(files)} files) {bad[:3]}")
    afiles = sorted(p.name for p in ad.glob("*.json"))
    bad = [f for f in afiles if srv.get(f"/data/activities/{f}")[2] != (ad / f).read_bytes()]
    check(not bad and len(afiles) == 5, f"every activities/ file served as is ({len(afiles)}) {bad[:3]}")
    check(srv.get("/data/knowledge/fact_embeddings.json")[0] == 404, "fact_embeddings.json not served")
    check(srv.get("/data/activities/lec_9.json")[0] == 404 and srv.get("/data/knowledge/lectures/lec_9.json")[0] == 404
          and srv.get("/data/knowledge/../index.json")[0] == 404, "missing or outside files are 404")
    kinds = {a["kind"] for k in ("1", "2", "3") for a in json.loads((ad / f"lec_{k}.json").read_text())["activities"]}
    check(kinds == {"quiz", "recap", "recall", "open_question", "concept_map", "complete_map", "crossword",
                    "match_pairs", "odd_one_out", "put_in_order"}, f"the synthetic activities hold every kind ({len(kinds)})")

    print("range", flush=True)
    code, hd, body = srv.get("/media/1")
    check(code == 200 and body == VIDEO and hd.get("Accept-Ranges") == "bytes" and "video/mp4" in hd.get("Content-Type", ""),
          f"the whole video without a Range ({code}, {len(body)} bytes)")
    code, hd, body = srv.get("/media/1", {"Range": "bytes=100-199"})
    check(code == 206 and body == VIDEO[100:200] and hd.get("Content-Range") == f"bytes 100-199/{len(VIDEO)}"
          and hd.get("Content-Length") == "100", f"bytes=100-199 -> 206 with those bytes ({code}, {hd.get('Content-Range')})")
    code, hd, body = srv.get("/media/1.mp4", {"Range": f"bytes={N - 10}-"})
    check(code == 206 and body == VIDEO[N - 10:] and hd.get("Content-Range") == f"bytes {N - 10}-{N - 1}/{N}",
          f"open range bytes={N - 10}- ({code})")
    code, hd, body = srv.get("/media/1", {"Range": "bytes=1000-"})
    check(code == 206 and body == VIDEO[1000:1000 + CHUNK] and hd.get("Content-Range") == f"bytes 1000-{1000 + CHUNK - 1}/{N}",
          f"an open range is answered with one chunk ({len(body)} bytes, {hd.get('Content-Range')})")
    check(hd.get("ETag") and hd.get("Last-Modified"), "the video carries ETag and Last-Modified")
    code, hd, body = srv.get("/media/1", {"Range": "bytes=-50"})
    check(code == 206 and body == VIDEO[-50:], f"suffix range bytes=-50 ({code})")
    code, hd, body = srv.get("/media/1", {"Range": f"bytes={N - 1000}-{N + 10000}"})
    check(code == 206 and body == VIDEO[N - 1000:], f"a range past the end is cut to the file ({code}, {len(body)})")
    code, hd, _ = srv.get("/media/1", {"Range": f"bytes={N + 10000}-"})
    check(code == 416 and hd.get("Content-Range") == f"bytes */{len(VIDEO)}", f"an unsatisfiable range is 416 ({code})")
    code, hd, body = srv.get("/media/1", {"Range": "bytes=0-9"}, method="HEAD")
    check(code == 206 and body == b"" and hd.get("Content-Length") == "10", f"HEAD with a Range ({code})")
    check(srv.get("/media/2")[0] == 404, "a lecture without a video is 404")
    yt = {r["id"].rsplit("_", 1)[-1]: r["youtube_id"] for r in
          csv.DictReader(open(root / "input" / COURSE / "input" / "titles.tsv", encoding="utf-8"), delimiter="\t")}
    _, L2 = srv.json("/api/lecture/2")
    check(L2["video"] is False and L2["youtube_id"] == yt["2"] and L1["youtube_id"] == yt["1"]
          and all(l["has"]["youtube"] for l in C["lectures"]),
          f"the YouTube ID of titles.tsv in the lecture route (for the fallback player) ({L2['youtube_id']})")

    test_lean(srv, root)

    print("ask", flush=True)
    code, _, evs = srv.stream("What is VR?", "1")
    check(code == 200 and len(evs) == 1 and evs[0]["event"] == "done" and evs[0]["result"]["available"] is False,
          f"no qa package: /api/ask_stream gives one 'done' with 'not available' ({evs[:1]})")
    code, r = srv.ask("What is VR?", "1")
    check(code == 200 and r["available"] is False and "not available" in r["answer"] and r["citations"] == [],
          f"no qa package: a clear 'not available' answer ({r.get('answer')!r})")
    code, r = srv.json("/api/ask", method="POST", data=b"not json", headers={"Content-Type": "application/json"})
    check(code == 400, f"a malformed question is 400 ({code})")


def test_lean(srv: Server, root: Path):
    kd = root / "output" / COURSE / "knowledge"
    concepts = json.loads((kd / "concepts.json").read_text())
    print("lean", flush=True)
    code, H = srv.json("/api/home")
    check(code == 200 and len(H["lectures"]) == 63 and H["layers"]["knowledge"] and "prefer_youtube" in H
          and H["lectures"][0]["goal"], f"/api/home ({code})")
    code, V = srv.json("/api/view/2")
    check(code == 200 and V["segments"] and V["sentences"] and V["goal"] and V["activities"]
          and isinstance(V["before"], list) and V["prev"] == "1" and V["next"] == "3"
          and all(c in V["concepts"] for sg in V["segments"] for c in sg["concepts"] or [] if c in concepts),
          f"/api/view/2: segments, sentences, goal, activities, before, prev/next, its concepts ({code})")
    lg = json.loads((kd / "lecture_graph.json").read_text())
    want = sorted(x["from"] for x in lg.get("links") or [] if x.get("to") == "5" and x.get("from") != "5")
    _, V5 = srv.json("/api/view/5")
    check(sorted(x["from"] for x in V5["before"]) == want and all(c in V5["concepts"] for x in V5["before"] for c in x["concepts"]),
          f"/api/view/5 'before': the lecture-graph links into it, with their concepts ({want})")
    check(srv.get("/api/view/99")[0] == 404 and srv.get("/api/view/..")[0] == 404, "an unknown lecture view is 404")
    code, G = srv.json("/api/glossary")
    listed = [c for c in G["concepts"] if c.get("listed") is not False]
    has_flag = any("defined" in c for c in concepts.values())
    want_listed = sorted(cid for cid, c in concepts.items() if not has_flag or c.get("defined") is True)
    check(code == 200 and sorted(c["id"] for c in listed) == want_listed and all("linked" in c for c in G["concepts"]),
          f"/api/glossary lists exactly the concepts 4a defined ({len(listed)} of {len(concepts)}), each with 'linked'")
    check(all(c.get("linked") and "definition" not in c for c in G["concepts"] if c.get("listed") is False)
          and G.get("connecting") == len(concepts) - len(want_listed),
          f"connecting concepts: only the linked ones, by name, for the explorer's search ({G.get('connecting')})")
    other = next((cid for cid, c in concepts.items() if has_flag and c.get("defined") is not True), next(iter(concepts)))
    code, CC = srv.json(f"/api/concept/{other}")
    check(code == 200 and CC["name"] and "relations" in CC and "facts" in CC, f"a connecting concept's card opens ({other})")
    check(srv.get("/api/concept/C9999")[0] == 404, "an unknown concept is 404")
    code, M = srv.json("/api/coursemap")
    check(code == 200 and "links" in M and "introduced" in M and "names" in M, f"/api/coursemap ({code})")
    code, R = srv.json("/api/review")
    check(code == 200 and R["cards"] and all(c["concept"] for c in R["cards"]), f"/api/review ({len(R['cards'])} cards)")
    code, hd, body = srv.get("/api/glossary", {"Accept-Encoding": "gzip"})
    tag = hd.get("ETag")
    check(code == 200 and hd.get("Content-Encoding") == "gzip" and tag and body[:2] == b"\x1f\x8b", "lean routes gzip with an ETag")
    code, hd, body = srv.get("/api/glossary", {"If-None-Match": tag})
    check(code == 304 and body == b"", f"If-None-Match gives 304 with no body ({code})")
    code, _, _ = srv.get("/data/knowledge/concepts.json", {"If-None-Match": srv.get("/data/knowledge/concepts.json")[1].get("ETag", "x")})
    check(code == 304, f"/data/ files give 304 too ({code})")

    print("judge", flush=True)
    _, V1 = srv.json("/api/view/1")
    by = {a["id"]: a for a in V1["activities"]}
    q = [a for a in V1["activities"] if a["kind"] == "quiz"][:2]
    cw = next(a for a in V1["activities"] if a["kind"] == "crossword")
    odd = next(a for a in V1["activities"] if a["kind"] == "odd_one_out")
    check(q[0].get("judge_failed") == {"1": ["answerable", "no_giveaway"]} and q[0].get("judge_hide") == [1],
          f"a quiz item failed on 'answerable' is hidden from learners ({q[0].get('judge_failed')}, {q[0].get('judge_hide')})")
    check(q[1].get("judge_failed") == {"1": ["no_giveaway"]} and q[1].get("judge_hide") == [],
          f"a quiz item failed only on 'no_giveaway' is kept ({q[1].get('judge_hide')})")
    check(cw.get("judge_failed") and cw.get("judge_hide") == [], "a judge-failed crossword is still shown")
    check(odd.get("unresolved") is True and not any(by[x].get("judge_failed") for x in by if by[x]["kind"] == "recap"),
          "an unresolved activity is marked; nothing invented for the others")

    print("versioned", flush=True)
    code, hd, body = srv.get("/")
    import re as _re
    refs = _re.findall(r'/static/([\w./-]+)\?v=(\w+)"', body.decode())
    check(code == 200 and {r[0] for r in refs} >= {"app.js", "style.css", "vendor/dagre.min.js"},
          f"index.html names its static files with ?v= ({len(refs)})")
    code, hd, _ = srv.get(f"/static/{refs[0][0]}?v={refs[0][1]}")
    check(code == 200 and "immutable" in hd.get("Cache-Control", "") and "max-age=31536000" in hd.get("Cache-Control", ""),
          f"a versioned static file is cached for good ({hd.get('Cache-Control')})")
    code, hd, _ = srv.get("/static/app.js")
    check(hd.get("Cache-Control") == "no-cache" and hd.get("ETag"), "an unversioned static file is revalidated (ETag)")


def test_ask(root: Path, work: Path):
    good, bad, streaming = work / "qa_good", work / "qa_bad", work / "qa_stream"
    write_fake_qa(good)
    write_fake_qa(streaming, stream=True)
    write_fake_qa(bad, raising=True)
    srv = Server(root, good, work / "server_qa.log")
    try:
        code, C = srv.json("/api/course")
        check(C["qa"] is True, "qa reported importable")
        code, r = srv.ask("What is VR?", "4")
        check(code == 200 and r["available"] and r["answer"] == f"echo: What is VR? ({COURSE}, 4)"
              and r["citations"][0]["lecture"] == "1" and r["citations"][0]["start"] == 24.3,
              f"the qa answer and citations passed through, with course and lecture ({r.get('answer')!r})")
        code, r = srv.ask("Across the course?", None)
        check(r["answer"].endswith(f"({COURSE}, None)"), "no lecture is passed as None")
        code, ctype, evs = srv.stream("What is VR?", "4")
        check(code == 200 and [e["event"] for e in evs] == ["done"] and evs[0]["result"]["answer"].startswith("echo:"),
              f"a qa without answer_stream: /api/ask_stream gives one 'done' with the answer ({[e['event'] for e in evs]})")
    finally:
        srv.stop()
    print("stream", flush=True)
    srv = Server(root, streaming, work / "server_qa_stream.log")
    try:
        code, ctype, evs = srv.stream("What is VR?", "4")
        check(code == 200 and "ndjson" in ctype and None not in evs
              and [e["event"] for e in evs] == ["step", "draft", "reset", "draft", "done"],
              f"answer_stream's events passed on in order, one JSON per line ({[e and e['event'] for e in evs]})")
        res = evs[-1]["result"]
        check(res["available"] and res["answer"] == f"echo: What is VR? ({COURSE}, 4)" and res["citations"][0]["start"] == 24.3,
              "the stream ends with 'done' carrying what /api/ask answers")
        code, r = srv.ask("What is VR?", "4")
        check(code == 200 and r["answer"].startswith("echo:"), "/api/ask still answers when qa streams")
    finally:
        srv.stop()
    srv = Server(root, bad, work / "server_qa_bad.log")
    try:
        code, r = srv.ask("What is VR?", "1")
        check(code == 200 and r["available"] and "went wrong" in r["answer"] and "model server down" in r["error"],
              f"a qa that raises gives a message, not a server error ({code})")
    finally:
        srv.stop()


def test_degrade(root: Path, work: Path):
    print("degrade", flush=True)
    srv = Server(root, work / "no_qa", work / "server_bare.log")
    try:
        code, C = srv.json("/api/course")
        check(code == 200 and C["layers"] == {"knowledge": False, "activities": False, "spaced_review": False}
              and C["goals"] is None and len(C["lectures"]) == 63, "a course with no knowledge/ or activities/ loads")
        code, L = srv.json("/api/lecture/4")
        check(code == 200 and L["source"] == "segments" and L["segments"] and L["knowledge"] is None
              and L["activities"] is None, "a lecture falls back to its 1b segments")
        check(srv.get("/data/knowledge/concepts.json")[0] == 404 and srv.get("/data/activities/course.json")[0] == 404,
              "the absent layers are 404")
        code, _, body = srv.get("/")
        check(code == 200, "the page loads")
    finally:
        srv.stop()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", help="folder for the copies (default: a new temporary folder)")
    ap.add_argument("--keep", action="store_true", help="keep the copies (serve them with serve.py --root <work>/full)")
    ap.add_argument("--knowledge", type=Path, help="an existing knowledge/ folder to use instead of building one")
    a = ap.parse_args()
    work = Path(a.work) if a.work else Path(tempfile.mkdtemp(prefix="viewer_smoke_"))
    work.mkdir(parents=True, exist_ok=True)
    before = snapshot(ROOT / "output")
    print(f"copies in {work}", flush=True)
    kd = a.knowledge.resolve() if a.knowledge else build_knowledge(work)
    full, bare = work / "full", work / "bare"
    make_root(full, kd, activities=True)
    make_root(bare, None, activities=False)
    (work / "no_qa").mkdir(exist_ok=True)
    srv = Server(full, work / "no_qa", work / "server.log")
    try:
        test_full(srv, full)
    finally:
        srv.stop()
    test_ask(full, work)
    test_degrade(bare, work)
    print("js", flush=True)
    if shutil.which("node"):
        r = subprocess.run(["node", "--check", str(ROOT / "viewer" / "app.js")], capture_output=True, text=True)
        check(r.returncode == 0, f"app.js parses {r.stderr.strip()[:200]}")
    else:
        print("  (node not installed: skipped)")
    js = (ROOT / "viewer" / "app.js").read_text()
    check("/data/knowledge" not in js and "/data/activities" not in js and "/api/ask_stream" in js,
          "app.js reads only the lean routes (no /data/knowledge files) and asks through /api/ask_stream")
    print("output", flush=True)
    check(snapshot(ROOT / "output") == before, "nothing under the real output/ created or changed")
    if not a.keep and not FAILURES:
        shutil.rmtree(work)
    print(f"\n{'PASS' if not FAILURES else 'FAIL'}: {len(FAILURES)} failed"
          + (f"; copies kept in {work}" if FAILURES or a.keep else ""))
    sys.exit(1 if FAILURES else 0)


if __name__ == "__main__":
    main()
