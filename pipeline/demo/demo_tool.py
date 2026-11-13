#!/usr/bin/env python3
"""Helpers for setup_demo.sh and check_demo.sh (standard library only; any python3 runs it).

    python3 demo/demo_tool.py config CONFIG --gpu-mem-mib 24576 --binary ~/llama.cpp/build/bin/llama-server \
                                            --model-path /path/to/model.gguf
        tune the demo config for this instance: the llama-server binary, the model file, and the slots by GPU memory
        (the sampling and thinking settings are never touched); the file is rewritten only when something changes
    python3 demo/demo_tool.py wait-model CONFIG [--timeout 900]
        wait until the config's model server answers /health, showing the end of its log every 30 s
    python3 demo/demo_tool.py media [--course nptel_vr]
        how many lectures have their video file here, and how many play from YouTube instead
    python3 demo/demo_tool.py ask URL "question" [--lecture 4] [--min-citations 1]
        ask the viewer (POST URL/api/ask); print the answer, its citations and the time; exit 1 when it fails
    python3 demo/demo_tool.py check-http URL CONFIG [--course nptel_vr] [--question Q]
        the HTTP checks of check_demo.sh: one "PASS|FAIL|SKIP  item  detail" line each; exit 1 when any fails
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PIPELINE = Path(__file__).resolve().parent.parent
DEMO_QUESTION = "What is an HMD?"


def load_cfg(path: str) -> tuple[Path, dict]:
    p = Path(path).expanduser()
    if not p.is_absolute() and not p.exists():
        p = PIPELINE / p
    return p, json.loads(p.read_text())


def home_form(path: str) -> str:
    """/home/ubuntu/x -> ~/x (the configs name home paths with ~)."""
    p, home = str(Path(path).expanduser()), str(Path.home())
    return "~" + p[len(home):] if p == home or p.startswith(home + os.sep) else p


def slots_for(mem_mib: int) -> int:
    """llama.cpp slots (requests at once) by GPU memory. The KV pool is shared (kv_unified, context_length tokens),
    so a slot costs little memory; 6 run on the 12 GB card of the local PC."""
    return 16 if mem_mib >= 70_000 else 12 if mem_mib >= 40_000 else 8 if mem_mib >= 20_000 else 6


def get(url: str, timeout: float = 10, headers: dict | None = None) -> tuple[int, dict, bytes]:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()
    except (urllib.error.URLError, OSError) as e:
        return 0, {}, str(e).encode()


def post_json(url: str, data: dict, timeout: float = 600) -> tuple[int, dict | None, float]:
    t0 = time.time()
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read()), time.time() - t0
    except urllib.error.HTTPError as e:
        return e.code, None, time.time() - t0
    except (urllib.error.URLError, OSError, ValueError):
        return 0, None, time.time() - t0


def fmt_time(t) -> str:
    t = int(round(float(t or 0)))
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60}:{t % 60:02d}"


# ---------------------------------------------------------------- commands
def cmd_config(a) -> int:
    path, cfg = load_cfg(a.config)
    want = {"binary": home_form(a.binary), "model_path": home_form(a.model_path), "slots": slots_for(a.gpu_mem_mib),
            "toolbox": ""}
    changed = {k: v for k, v in want.items() if cfg.get(k, "") != v}
    if changed:
        cfg.update(changed)
        path.write_text(json.dumps(cfg, indent=1) + "\n")
        print(f"  {path.name}: set " + ", ".join(f"{k}={v}" for k, v in changed.items()))
    else:
        print(f"  {path.name}: already set for this instance")
    print(f"  model {cfg['model']}, port {cfg['port']}, {cfg['slots']} slots, context {cfg['context_length']}, "
          f"temperature {cfg['temperature']}, top_p {cfg['top_p']}, top_k {cfg['top_k']}, thinking {cfg['thinking']} "
          f"(budget {cfg['think_budget']})")
    return 0


def cmd_wait_model(a) -> int:
    path, cfg = load_cfg(a.config)
    url = f"http://{cfg.get('host', '127.0.0.1')}:{cfg['port']}"
    log = PIPELINE / cfg.get("server_log", "") if cfg.get("server_log") else None
    t0, note = time.time(), 0.0
    while True:
        code, _, _ = get(url + "/health", timeout=3)
        waited = time.time() - t0
        if code == 200:
            print(f"  model server ready at {url} ({waited:.0f} s)")
            return 0
        if waited > a.timeout:
            print(f"  the model server did not answer at {url} within {a.timeout} s; see {log}")
            return 1
        if waited >= note:
            last = ""
            if log and log.exists():
                lines = [x for x in log.read_text(errors="replace").replace("\r", "\n").splitlines() if x.strip()]
                last = lines[-1][:110] if lines else ""
            print(f"  {time.strftime('%H:%M:%S')}  waiting for the model server ({waited:.0f} s): {last}", flush=True)
            note += 30
        time.sleep(2)


def course_obj(course: str):
    sys.path.insert(0, str(PIPELINE / "viewer"))
    from serve import Course                                       # noqa: E402  pipeline/viewer/serve.py
    return Course(course, PIPELINE)


def cmd_media(a) -> int:
    C = course_obj(a.course)
    titles = C.titles()
    keys = C.keys()
    local = [k for k in keys if C.video(k)]
    yt = [k for k in keys if not C.video(k) and titles.get(k, {}).get("youtube_id")]
    none = [k for k in keys if not C.video(k) and k not in yt]
    print(f"  {len(keys)} lectures: {len(local)} video files in {C.media}, {len(yt)} from YouTube"
          + (f", {len(none)} with no video ({', '.join(none)})" if none else ""))
    return 0


def cmd_ask(a) -> int:
    code, r, secs = post_json(a.url.rstrip("/") + "/api/ask", {"question": a.question, "lecture": a.lecture},
                              timeout=a.timeout)
    if code != 200 or not r:
        print(f"  no answer (HTTP {code}, {secs:.1f} s)")
        return 1
    print(f"  Q: {a.question}" + (f"  (on lecture {a.lecture})" if a.lecture else ""))
    for line in (r.get("answer") or "").splitlines():
        print(f"  A: {line}" if line.strip() else "")
    cites = r.get("citations") or []
    for i, c in enumerate(cites, 1):
        print(f"     [{i}] lecture {c.get('lecture')} at {fmt_time(c.get('start'))}: {str(c.get('text', ''))[:90]}")
    print(f"  {secs:.1f} s, {len(cites)} citations" + (f", error: {r['error']}" if r.get("error") else ""))
    ok = r.get("available") is not False and not r.get("error") and len(cites) >= a.min_citations
    return 0 if ok else 1


def cmd_check_http(a) -> int:
    base = a.url.rstrip("/")
    fails = []

    def item(ok, what, detail=""):
        tag = "PASS" if ok is True else "SKIP" if ok is None else "FAIL"
        print(f"{tag}  {what}" + (f"  ({detail})" if detail else ""), flush=True)
        if ok is False:
            fails.append(what)

    # the model server
    _, cfg = load_cfg(a.config)
    murl = f"http://{cfg.get('host', '127.0.0.1')}:{cfg['port']}"
    code, _, _ = get(murl + "/health", timeout=5)
    item(code == 200, "model server healthy", f"{murl}/health -> {code or 'no answer'}")
    code, _, body = get(murl + "/v1/models", timeout=10)
    try:
        served = [m["id"] for m in json.loads(body).get("data", [])]
    except (ValueError, AttributeError):
        served = []
    item(cfg["model"] in served, "model server serves the config's model", f"{cfg['model']} in {served}")

    # the viewer
    code, hd, body = get(base + "/")
    item(code == 200 and b"app.js" in body, "viewer page", f"GET / -> {code}")
    code, hd, body = get(base + "/static/app.js")
    item(code == 200 and "javascript" in hd.get("Content-Type", ""), "viewer script", f"GET /static/app.js -> {code}")
    code, _, body = get(base + "/api/course", timeout=30)
    try:
        C = json.loads(body)
    except ValueError:
        C = {}
    lectures = C.get("lectures") or []
    item(code == 200 and len(lectures) > 0 and C.get("layers", {}).get("knowledge"), "course route",
         f"{len(lectures)} lectures, knowledge {C.get('layers', {}).get('knowledge')}, "
         f"activities {C.get('layers', {}).get('activities')}")
    item(bool(C.get("qa")), "question answering importable in the viewer")
    key = "4" if any(x["key"] == "4" for x in lectures) else (lectures[0]["key"] if lectures else "1")
    code, _, body = get(base + f"/api/lecture/{key}", timeout=30)
    try:
        L = json.loads(body)
    except ValueError:
        L = {}
    item(code == 200 and len(L.get("segments") or []) > 0 and len(L.get("sentences") or []) > 0,
         f"lecture route (lecture {key})", f"{len(L.get('segments') or [])} segments, "
         f"{len(L.get('sentences') or [])} sentences, knowledge {'yes' if L.get('knowledge') else 'no'}, "
         f"activities {'yes' if L.get('activities') else 'no'}")
    code, _, body = get(base + "/data/knowledge/index.json")
    item(code == 200, "knowledge files served", f"GET /data/knowledge/index.json -> {code}")

    # the video of that lecture: a Range request on the file, or the YouTube fallback
    n_local = sum(1 for x in lectures if x.get("has", {}).get("video"))
    n_yt = sum(1 for x in lectures if not x.get("has", {}).get("video") and x.get("has", {}).get("youtube"))
    if L.get("video"):
        code, hd, body = get(base + f"/media/{key}", headers={"Range": "bytes=100-199"})
        item(code == 206 and len(body) == 100 and hd.get("Content-Range", "").startswith("bytes 100-199/"),
             f"video Range request (lecture {key})", f"{code}, {len(body)} bytes, {hd.get('Content-Range')}")
    elif L.get("youtube_id"):
        item(None, f"video Range request (lecture {key})", f"no file here: plays from YouTube ({L['youtube_id']})")
    else:
        item(False, f"video for lecture {key}", "neither a file nor a youtube_id")
    item(n_local + n_yt == len(lectures), "every lecture has a video",
         f"{n_local} files, {n_yt} from YouTube, {len(lectures) - n_local - n_yt} without")

    # one question, through the viewer (the whole path: viewer -> qa -> embedder + model server)
    code, r, secs = post_json(base + "/api/ask", {"question": a.question, "lecture": None}, timeout=a.timeout)
    cites = (r or {}).get("citations") or []
    item(code == 200 and r and r.get("available") and not r.get("error") and len(cites) > 0,
         "question answered with citations",
         f"{a.question!r}: {secs:.1f} s, {len(cites)} citations"
         + (f", error {r.get('error')}" if r and r.get("error") else "")
         + (f"; {(r.get('answer') or '')[:120]!r}" if r else ""))
    return 1 if fails else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("config")
    p.add_argument("config")
    p.add_argument("--gpu-mem-mib", type=int, required=True)
    p.add_argument("--binary", required=True)
    p.add_argument("--model-path", required=True)
    p = sub.add_parser("wait-model")
    p.add_argument("config")
    p.add_argument("--timeout", type=int, default=900)
    p = sub.add_parser("media")
    p.add_argument("--course", default="nptel_vr")
    p = sub.add_parser("ask")
    p.add_argument("url")
    p.add_argument("question")
    p.add_argument("--lecture")
    p.add_argument("--min-citations", type=int, default=0)
    p.add_argument("--timeout", type=int, default=600)
    p = sub.add_parser("check-http")
    p.add_argument("url")
    p.add_argument("config")
    p.add_argument("--course", default="nptel_vr")
    p.add_argument("--question", default=DEMO_QUESTION)
    p.add_argument("--timeout", type=int, default=600)
    a = ap.parse_args()
    return {"config": cmd_config, "wait-model": cmd_wait_model, "media": cmd_media, "ask": cmd_ask,
            "check-http": cmd_check_http}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
