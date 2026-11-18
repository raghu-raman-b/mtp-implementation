"""The laptop side of the demo: the viewer and the question box's tool loop run here (Windows, Linux or macOS); the
model and the query embedder run on the GPU instance (demo/ec2_model_server.sh), reached through an SSH tunnel.

Run from the pipeline folder (setup_windows.ps1 and run_demo.ps1 call these):

    python -m demo setup --instance ubuntu@1.2.3.4 --key C:\\keys\\demo.pem [--media D:\\videos] [--local-embed]
        saves these settings in demo/local.json (gitignored) and checks this machine (Python, packages, ssh, key)
    python -m demo run [--instance ...] [--key ...] [--media ...] [--port 8765] [--no-browser]
        opens the tunnel (ssh -N -L 8096:127.0.0.1:8096 -L 8097:127.0.0.1:8097 user@host; reopened if it drops),
        finds which engine the instance serves (llama.cpp or vLLM, from its model name), starts the viewer pointed at
        it (QA_CONFIG = a copy of that engine's demo config with "url" = the tunnel; QA_EMBED_URL = the tunnel's
        embedder port), waits until qa is warm (layer, embedder, model server, prompt prefix cached), opens the
        browser. Ctrl+C stops the viewer and the tunnel (the instance keeps serving).
    python -m demo check [--url http://127.0.0.1:8765]
        PASS/FAIL lines: the model server and its model, the embedder and its vectors (cosine >= 0.999 against the
        layer's fact_embeddings.json for 24 fact texts), the viewer's routes, one streamed question with its timings
    python -m demo bench [--url ...] [--runs 1] [--out FILE]
        the DEMO_PLAN questions through /api/ask_stream: seconds to the first event, the first step, the answer's
        start, the first words and the end, per question and the medians (several --url: each question is asked of
        each in turn, so two setups compare fairly on one shared GPU)
    python -m demo push --instance ubuntu@1.2.3.4 --key ... [--engine llamacpp|vllm] [--no-start]
        copies what the instance needs (demo/, configs/, scripts/llm/, prompts/qa_tools.json: ~150 kB) to
        ~/mtp-demo/pipeline on the instance over ssh, and runs ec2_model_server.sh there in tmux, showing its output
    python -m demo tunnel [--instance ...]
        only the tunnel, in the foreground

Standard library only (qa needs numpy for the fact search; sentence-transformers only with --local-embed).
"""
from __future__ import annotations

import argparse
import http.client
import io
import json
import os
import shutil
import signal
import socket
import statistics
import subprocess
import sys
import tarfile
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from urllib.parse import urlsplit

DEMO = Path(__file__).resolve().parent
PIPELINE = DEMO.parent
SETTINGS = DEMO / "local.json"
LOGS = DEMO / "logs"
COURSE = "nptel_vr"
ENGINE_CONFIGS = {"gemma-4-12b-qat": ("llamacpp", "configs/gemma4_12b_demo.json"),
                  "gemma-4-12b": ("vllm", "configs/gemma4_12b_vllm_demo.json")}
WARMUP_Q = "How does a Kalman filter fuse IMU and camera data for tracking?"
DEMO_QUESTIONS = [            # continue/DEMO_PLAN.md, "The questions, in order"
    "What is the difference between immersion and presence?",
    "What are the causes of cybersickness?",
    "What is the field of view and why does it matter for cybersickness?",
    "Why are GPUs used for rendering in VR?",
    "What is an IMU?",
    "what is HRTF",
    "what is cybersicknes",
    "How does the Wizard of Oz approach work?",
    "What is lecture 36 for?",
    "What do I need to know before lecture 9?",
    "What is vergence-accommodation conflict?",
    "Who won the 2022 FIFA World Cup?",
]
PUSH_FILES = ["demo/ec2_model_server.sh", "demo/demo_tool.py", "demo/embed_server.py", "demo/.gitignore",
              "configs/gemma4_12b_demo.json", "configs/gemma4_12b_vllm_demo.json", "scripts/__init__.py",
              "scripts/llm/__init__.py", "scripts/llm/client.py", "scripts/llm/config.py",
              "scripts/llm/progress.py", "scripts/llm/serve.py", "scripts/llm/server.py", "scripts/llm/http_pool.py",
              "prompts/qa_tools.json"]


def say(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------- settings and small helpers
def load_settings() -> dict:
    try:
        return json.loads(SETTINGS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def http_get(url: str, timeout: float = 5) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except (OSError, ValueError, http.client.HTTPException):
        return 0, b""


def http_json(url: str, timeout: float = 5):
    code, body = http_get(url, timeout)
    try:
        return code, json.loads(body) if body else None
    except ValueError:
        return code, None


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def ssh_base(a) -> list[str]:
    exe = shutil.which("ssh")
    if not exe:
        sys.exit("ssh not found. Windows: Settings > System > Optional features > OpenSSH Client (built in on "
                 "Windows 10 1809 and later); Linux: install openssh-client.")
    cmd = [exe, "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=3", "-o", "ConnectTimeout=15",
           "-o", "StrictHostKeyChecking=accept-new"]
    if a.key:
        cmd += ["-i", str(Path(a.key).expanduser())]
    if a.ssh_port:
        cmd += ["-p", str(a.ssh_port)]
    return cmd


def tunnel_cmd(a) -> list[str]:
    fwd = ["-L", f"{a.model_port}:127.0.0.1:{a.remote_model_port}"]
    if not a.local_embed:
        fwd += ["-L", f"{a.embed_port}:127.0.0.1:{a.remote_embed_port}"]
    return ssh_base(a) + ["-N", "-o", "ExitOnForwardFailure=yes"] + fwd + [a.instance]


class Tunnel:
    """ssh -N -L ... kept open: started again when it exits (a dropped Wi-Fi, a laptop that slept)."""

    def __init__(self, a):
        self.a, self.proc, self.restarts = a, None, 0

    def start(self):
        cmd = tunnel_cmd(self.a)
        say("  tunnel: " + " ".join(f'"{x}"' if " " in x else x for x in cmd))
        self.proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL)

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def keep(self):
        if self.proc is not None and not self.alive():
            self.restarts += 1
            say(f"  the tunnel closed (exit {self.proc.returncode}); opening it again ({self.restarts})")
            time.sleep(min(10, 2 * self.restarts))
            self.start()

    def stop(self):
        if self.alive():
            self.proc.terminate()
            try:
                self.proc.wait(5)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def wait_until(what: str, test, timeout: float, every: float = 1.0, note_every: float = 30):
    t0, note = time.time(), 0.0
    while True:
        r = test()
        if r:
            return r
        waited = time.time() - t0
        if waited > timeout:
            return None
        if waited >= note and waited > 2:
            say(f"  {time.strftime('%H:%M:%S')}  waiting for {what} ({waited:.0f} s)")
            note += note_every
        time.sleep(every)


def served_models(base: str) -> list[str]:
    code, d = http_json(base + "/v1/models", 10)
    return [m.get("id") for m in (d or {}).get("data", [])] if code == 200 else []


def layer_embed_model(output: Path | None) -> str:
    idx = (output or PIPELINE / "output") / COURSE / "knowledge" / "index.json"
    try:
        return json.loads(idx.read_text(encoding="utf-8"))["embedding"]["model"]
    except (OSError, ValueError, KeyError):
        return "Qwen/Qwen3-Embedding-0.6B"


def write_qa_config(model_id: str, model_url: str) -> tuple[str, Path]:
    engine, rel = ENGINE_CONFIGS[model_id]
    cfg = json.loads((PIPELINE / rel).read_text(encoding="utf-8"))
    cfg.update(url=model_url, launch=False, attach_wait_s=120, server_log="", toolbox="")
    LOGS.mkdir(parents=True, exist_ok=True)
    out = LOGS / f"qa_remote_{engine}.json"
    out.write_text(json.dumps(cfg, indent=1) + "\n", encoding="utf-8")
    return engine, out


# ---------------------------------------------------------------- run
def cmd_run(a) -> int:
    model_url = a.model_url or f"http://127.0.0.1:{a.model_port}"
    embed_url = None if a.local_embed else (a.embed_url or f"http://127.0.0.1:{a.embed_port}")
    tunnel = None
    if not a.no_tunnel and not a.model_url:
        if not a.instance:
            sys.exit("give --instance user@host (or save it with python -m demo setup), or --no-tunnel")
        if http_get(model_url + "/health", 3)[0] == 200:
            say(f"  something already answers on {model_url} (a tunnel left open?): using it")
        else:
            if not port_free(a.model_port):
                sys.exit(f"port {a.model_port} on this machine is taken by another program: --model-port N")
            tunnel = Tunnel(a)
            tunnel.start()
    try:
        return run_viewer(a, model_url, embed_url, tunnel)
    finally:
        if tunnel:
            tunnel.stop()


def run_viewer(a, model_url: str, embed_url: str | None, tunnel) -> int:
    t0 = time.time()

    def model_up():
        if tunnel:
            tunnel.keep()
        return http_get(model_url + "/health", 3)[0] == 200

    if not wait_until(f"the model server at {model_url} (through the tunnel; still loading on the instance?)",
                      model_up, a.wait_model, every=2):
        say(f"STOP: no model server answers at {model_url} after {a.wait_model} s. On the instance: "
            "bash ~/mtp-demo/pipeline/demo/ec2_model_server.sh --status")
        return 1
    models = served_models(model_url)
    known = [m for m in models if m in ENGINE_CONFIGS]
    if not known:
        say(f"STOP: the server serves {models}; expected one of {list(ENGINE_CONFIGS)}")
        return 1
    engine, qa_cfg = write_qa_config(known[0], model_url)
    say(f"  model server: {engine}, {known[0]} at {model_url} ({time.time() - t0:.1f} s)")
    want = layer_embed_model(a.output)
    if embed_url:
        code, h = http_json(embed_url + "/health", 5)
        if code != 200 or (h or {}).get("model") != want:
            say(f"  the embedding server at {embed_url} answers {code} {h}; expected {want}")
            try:
                import sentence_transformers  # noqa: F401
                say("  falling back to embedding on this machine's CPU (sentence-transformers is installed)")
                embed_url = None
            except ImportError:
                say("STOP: no embedder: start it on the instance (ec2_model_server.sh, without --no-embed), or "
                    "install the local one (setup_windows.ps1 -LocalEmbed) and use --local-embed")
                return 1
        else:
            say(f"  embedder: {h.get('model')} on the instance ({h.get('device')}) at {embed_url}")
    if not embed_url:
        say(f"  embedder: {want} on this machine's CPU (loads in 10-20 s at the warm-up)")
    port = a.port
    while not port_free(port):
        port += 1
        if port > a.port + 20:
            say(f"STOP: no free port from {a.port}")
            return 1
    if port != a.port:
        say(f"  port {a.port} is taken on this machine: the viewer uses {port}")
    env = dict(os.environ, QA_CONFIG=str(qa_cfg), QA_KEEP_WARM="1", PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    env.pop("QA_EMBED_URL", None)
    if embed_url:
        env["QA_EMBED_URL"] = embed_url
    cmd = [sys.executable, str(PIPELINE / "viewer" / "serve.py"), COURSE, "--port", str(port), "--warm"]
    if a.media:
        cmd += ["--media", str(Path(a.media).expanduser())]
    if a.output:
        cmd += ["--output", str(a.output)]
    if a.activities:
        cmd += ["--activities", a.activities]
    if a.prefer_youtube:
        cmd += ["--prefer-youtube"]
    viewer = subprocess.Popen(cmd, cwd=str(PIPELINE), env=env)
    url = f"http://127.0.0.1:{port}"
    try:
        if not wait_until("the viewer", lambda: viewer.poll() is not None or http_get(url + "/api/home", 3)[0] == 200,
                          60, 0.5) or viewer.poll() is not None:
            say("STOP: the viewer did not start (see its output above)")
            return 1
        st = wait_until("qa to warm up (layer, embedder, model server, prompt prefix)",
                        lambda: (lambda d: d if d and d.get("state") in ("ready", "failed", "off") else None)(
                            http_json(url + "/api/qa_status", 3)[1]), a.wait_warm, 1)
        if st and st.get("state") == "ready":
            say(f"  question answering warm in {st.get('seconds')} s {json.dumps(st.get('parts') or {})}")
        else:
            say(f"  WARNING: question answering is not warm ({(st or {}).get('error') or 'timed out'}); the first "
                "question may be slow or fail")
        say(f"\nReady in {time.time() - t0:.0f} s: {url}/   (Ctrl+C here stops the viewer and the tunnel)")
        if not a.no_browser:
            webbrowser.open(url + "/")
        while viewer.poll() is None:
            if tunnel:
                tunnel.keep()
            time.sleep(2)
        say(f"the viewer exited (code {viewer.returncode})")
        return viewer.returncode or 0
    except KeyboardInterrupt:
        say("\nstopping")
        return 0
    finally:
        if viewer.poll() is None:
            viewer.terminate()
            try:
                viewer.wait(5)
            except subprocess.TimeoutExpired:
                viewer.kill()


def cmd_tunnel(a) -> int:
    if not a.instance:
        sys.exit("give --instance user@host")
    t = Tunnel(a)
    t.start()
    try:
        while True:
            t.keep()
            time.sleep(2)
    except KeyboardInterrupt:
        t.stop()
    return 0


# ---------------------------------------------------------------- the stream, timed
def ask_stream(url: str, question: str, lecture=None, timeout: float = 300) -> dict:
    """One question through /api/ask_stream: when (s after sending) each kind of event first came, and the result."""
    u = urlsplit(url)
    conn = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=timeout)
    body = json.dumps({"question": question, "lecture": lecture}).encode()
    t0 = time.perf_counter()
    first: dict = {}
    steps, result, timing = [], None, None
    try:
        conn.request("POST", "/api/ask_stream", body, {"Content-Type": "application/json"})
        r = conn.getresponse()
        for raw in r:
            line = raw.strip()
            if not line:
                continue
            ev = json.loads(line)
            k = ev.get("event")
            first.setdefault("event", round(time.perf_counter() - t0, 3))
            first.setdefault(k, round(time.perf_counter() - t0, 3))
            if k == "step":
                steps.append(ev.get("label") or f"{ev.get('tool')}: {ev.get('result_summary')}")
            if k == "done":
                result, timing = ev.get("result") or {}, ev.get("timing")
                break
    except (OSError, http.client.HTTPException, ValueError) as e:
        result = {"error": f"{type(e).__name__}: {e}"}
    finally:
        conn.close()
    res = result or {}
    return {"question": question, "first_event": first.get("event"), "first_step": first.get("step"),
            "answer_start": first.get("answer_start"), "first_draft": first.get("draft"), "done": first.get("done"),
            "citations": len(res.get("citations") or []), "covered": res.get("covered"), "error": res.get("error"),
            "steps": steps, "server_timing": timing, "answer": res.get("answer", "")}


def fmt(x) -> str:
    return "  -  " if x is None else f"{x:5.2f}"


def cmd_bench(a) -> int:
    """Each question is asked of every --url in turn (several viewers: a fair comparison on a shared GPU)."""
    qs = DEMO_QUESTIONS if not a.questions else [x for x in Path(a.questions).read_text(encoding="utf-8").splitlines()
                                                 if x.strip()]
    urls = a.url or ["http://127.0.0.1:8765"]
    labels = (a.label or []) + [f"url{i}" for i in range(len(a.label or []), len(urls))]
    rows = []
    out = open(a.out, "a", encoding="utf-8") if a.out else None
    if a.warmup:
        for u, lab in zip(urls, labels):
            r = ask_stream(u, WARMUP_Q)
            say(f"{lab}: warm-up question: done in {fmt(r['done'])} s")
    say(f"{'question':50} {'label':>8} {'event':>6} {'step':>6} {'start':>6} {'draft':>6} {'done':>6} cites")
    for run in range(a.runs):
        for q in qs:
            for u, lab in zip(urls, labels):
                r = ask_stream(u, q)
                r["run"], r["label"] = run, lab
                rows.append(r)
                say(f"{q[:50]:50} {lab[:8]:>8} {fmt(r['first_event']):>6} {fmt(r['first_step']):>6} "
                    f"{fmt(r['answer_start']):>6} {fmt(r['first_draft']):>6} {fmt(r['done']):>6} {r['citations']:>3}"
                    + (f"  ERROR {r['error']}" if r["error"] else ""))
                if out:
                    out.write(json.dumps(r, ensure_ascii=False) + "\n")
                    out.flush()
    if out:
        out.close()
    for lab in labels:
        mine = [r for r in rows if r["label"] == lab]

        def med(k):
            xs = [r[k] for r in mine if r[k] is not None]
            return statistics.median(xs) if xs else None
        say(f"{'median':50} {lab[:8]:>8} {fmt(med('first_event')):>6} {fmt(med('first_step')):>6} "
            f"{fmt(med('answer_start')):>6} {fmt(med('first_draft')):>6} {fmt(med('done')):>6}")
    return 1 if any(r["error"] for r in rows) else 0


# ---------------------------------------------------------------- check
def cmd_check(a) -> int:
    fails = []

    def item(ok, what, detail=""):
        tag = "PASS" if ok is True else "SKIP" if ok is None else "FAIL"
        say(f"{tag}  {what}" + (f"  ({detail})" if detail else ""))
        if ok is False:
            fails.append(what)

    base = a.url.rstrip("/")
    code, st = http_json(base + "/api/qa_status", 5)
    item(code == 200, "viewer answers", f"{base}/api/qa_status -> {code}")
    cfg_path = os.environ.get("QA_CONFIG") or next(iter(sorted(LOGS.glob("qa_remote_*.json"),
                                                               key=lambda p: p.stat().st_mtime)[-1:]), None)
    model_url = a.model_url
    if not model_url and cfg_path:
        model_url = json.loads(Path(cfg_path).read_text(encoding="utf-8")).get("url")
    model_url = model_url or f"http://127.0.0.1:{a.model_port}"
    t = time.perf_counter()
    code, _ = http_get(model_url + "/health", 5)
    item(code == 200, "model server healthy through the tunnel", f"{model_url} -> {code}, "
                                                                 f"{(time.perf_counter() - t) * 1000:.0f} ms")
    models = served_models(model_url)
    item(any(m in ENGINE_CONFIGS for m in models), "model server serves a demo model", f"{models}")
    item((st or {}).get("state") == "ready", "question answering warm", f"{st}")
    embed_url = a.embed_url or (None if a.local_embed else f"http://127.0.0.1:{a.embed_port}")
    want = layer_embed_model(a.output)
    if embed_url:
        code, h = http_json(embed_url + "/health", 5)
        item(code == 200 and (h or {}).get("model") == want, "embedding server serves the layer's model",
             f"{embed_url}: {h}")
        if code == 200:
            ok, detail = check_vectors(embed_url, want, a.output)
            item(ok, "embedder vectors equal the layer's (fact texts, cosine >= 0.999)", detail)
    else:
        item(None, "embedding server", "--local-embed: this machine embeds")
    for route in ("/", "/api/home", "/api/view/4", "/api/glossary"):
        code, _ = http_get(base + route, 30)
        item(code == 200, f"viewer route {route}", str(code))
    r = ask_stream(base, a.question)
    item(not r["error"] and r["citations"] > 0 and r["done"] is not None, "a question answered through the stream",
         f"{a.question!r}: first event {fmt(r['first_event'])} s, first step {fmt(r['first_step'])} s, first words "
         f"{fmt(r['first_draft'])} s, done {fmt(r['done'])} s, {r['citations']} citations"
         + (f", error {r['error']}" if r["error"] else ""))
    say("\nALL PASS" if not fails else f"\n{len(fails)} FAILED: {', '.join(fails)}")
    return 1 if fails else 0


def check_vectors(embed_url: str, model: str, output: Path | None, n: int = 24) -> tuple[bool, str]:
    kd = (output or PIPELINE / "output") / COURSE / "knowledge"
    try:
        emb = json.loads((kd / "fact_embeddings.json").read_text(encoding="utf-8"))
        facts = json.loads((kd / "facts.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return None, f"no layer to compare with: {e}"
    ids = list(emb["vectors"])
    ids = ids[:: max(1, len(ids) // n)][:n]
    sys.path.insert(0, str(PIPELINE))
    from scripts.embed import Embedder
    t = time.perf_counter()
    vecs = Embedder(model, url=embed_url).embed([facts[i]["text"] for i in ids])
    secs = time.perf_counter() - t
    cos = [sum(x * y for x, y in zip(v, emb["vectors"][i])) for v, i in zip(vecs, ids)]
    return min(cos) >= 0.999, f"{len(ids)} facts, min cosine {min(cos):.5f}, mean {statistics.mean(cos):.5f}, " \
                              f"{secs:.2f} s"


# ---------------------------------------------------------------- setup and push
def cmd_setup(a) -> int:
    s = load_settings()
    for k in ("instance", "key", "media", "local_embed", "ssh_port"):
        v = getattr(a, k, None)
        if v not in (None, "", False):
            s[k] = str(Path(v).expanduser().resolve()) if k in ("key", "media") else v
    SETTINGS.write_text(json.dumps(s, indent=1) + "\n", encoding="utf-8")
    say(f"settings saved in {SETTINGS}: {json.dumps(s)}")
    ok = True
    say(f"  Python {sys.version.split()[0]} at {sys.executable}" + ("" if sys.version_info >= (3, 11) else
                                                                    "  FAIL: 3.11 or newer is needed"))
    ok &= sys.version_info >= (3, 11)
    try:
        import numpy
        say(f"  numpy {numpy.__version__}")
    except ImportError:
        say("  FAIL: numpy is missing (pip install -r demo/requirements-local.txt)")
        ok = False
    if s.get("local_embed"):
        try:
            import sentence_transformers
            say(f"  sentence-transformers {sentence_transformers.__version__} (local embedder)")
        except ImportError:
            say("  FAIL: --local-embed needs demo/requirements-local-embed.txt")
            ok = False
    say(f"  ssh: {shutil.which('ssh') or 'MISSING (install the OpenSSH client)'}")
    ok &= bool(shutil.which("ssh"))
    if s.get("key") and not Path(s["key"]).is_file():
        say(f"  FAIL: no key file {s['key']}")
        ok = False
    if s.get("media"):
        vids = sorted(Path(s["media"]).glob("L*.mp4")) if Path(s["media"]).is_dir() else []
        say(f"  videos: {len(vids)} files in {s['media']}" + ("" if vids else " (none: lectures play from YouTube)"))
    kd = PIPELINE / "output" / COURSE / "knowledge" / "index.json"
    say(f"  course layer: {'found' if kd.exists() else 'MISSING: ' + str(kd)}")
    ok &= kd.exists()
    say("setup OK" if ok else "setup has problems (above)")
    return 0 if ok else 1


def bundle() -> bytes:
    """The files the instance needs, as a .tar.gz under pipeline/ (line endings LF: a Windows checkout may have
    CRLF, which bash and the shebangs do not take)."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for rel in PUSH_FILES:
            p = PIPELINE / rel
            if not p.exists():
                continue
            data = p.read_bytes().replace(b"\r\n", b"\n")
            info = tarfile.TarInfo("pipeline/" + rel)
            info.size, info.mtime = len(data), int(p.stat().st_mtime)
            info.mode = 0o755 if rel.endswith(".sh") else 0o644
            tar.addfile(info, io.BytesIO(data))
        tok = PIPELINE / ".hf_token"
        if tok.exists():
            data = tok.read_bytes().strip()
            info = tarfile.TarInfo("pipeline/.hf_token")
            info.size, info.mode = len(data), 0o600
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def cmd_push(a) -> int:
    if not a.instance:
        sys.exit("give --instance user@host")
    data = bundle()
    say(f"copying {len(data) // 1024} kB to {a.instance}:~/mtp-demo/pipeline")
    p = subprocess.run(ssh_base(a) + [a.instance, "mkdir -p ~/mtp-demo && tar -xzf - -C ~/mtp-demo"], input=data)
    if p.returncode:
        say("STOP: the copy failed (ssh above)")
        return 1
    if a.no_start:
        say("copied. On the instance: bash ~/mtp-demo/pipeline/demo/ec2_model_server.sh --engine llamacpp|vllm")
        return 0
    engine = a.engine or input("Which model server? [1] llama.cpp (default)  [2] vLLM: ").strip()
    engine = "vllm" if engine in ("2", "vllm") else "llamacpp"
    log = "~/mtp-demo/ec2_model_server.log"
    run = (f"tmux kill-session -t setup 2>/dev/null; : > {log}; tmux new -d -s setup "
           f"'bash ~/mtp-demo/pipeline/demo/ec2_model_server.sh --engine {engine} 2>&1 | tee {log}'")
    if subprocess.run(ssh_base(a) + [a.instance, run]).returncode:
        say("STOP: could not start the setup on the instance (is tmux installed? sudo apt-get install tmux)")
        return 1
    say(f"the setup runs on the instance in tmux 'setup' ({engine}); its output follows (Ctrl+C stops watching, "
        "not the setup)")
    follow = subprocess.Popen(ssh_base(a) + [a.instance, f"tail -n +1 -f {log}"], stdout=subprocess.PIPE)
    code = 1
    try:
        for raw in follow.stdout:
            line = raw.decode("utf-8", "replace").rstrip()
            say(line)
            if "STOP:" in line:
                break
            if line.lstrip().startswith("Here:"):
                code = 0
                break
    except KeyboardInterrupt:
        pass
    finally:
        follow.terminate()
    return code


# ---------------------------------------------------------------- arguments
def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(errors="replace")           # a Windows console that cannot show a character
        except (AttributeError, ValueError):
            pass
    # Ctrl+C, Ctrl+Break (Windows) and a plain kill all end in the same clean stop (viewer and tunnel closed)
    def interrupt(*_):
        raise KeyboardInterrupt
    for name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        if hasattr(signal, name):
            try:
                signal.signal(getattr(signal, name), interrupt)
            except (OSError, ValueError):
                pass
    st = load_settings()
    ap = argparse.ArgumentParser(prog="python -m demo", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def conn(p):
        p.add_argument("--instance", default=st.get("instance"), help="user@host of the GPU instance")
        p.add_argument("--key", default=st.get("key"), help="the SSH private key (.pem)")
        p.add_argument("--ssh-port", type=int, default=st.get("ssh_port"))
        p.add_argument("--model-port", type=int, default=8096, help="this machine's end of the model tunnel")
        p.add_argument("--embed-port", type=int, default=8097, help="this machine's end of the embedder tunnel")
        p.add_argument("--remote-model-port", type=int, default=8096)
        p.add_argument("--remote-embed-port", type=int, default=8097)
        p.add_argument("--local-embed", action="store_true", default=bool(st.get("local_embed")),
                       help="embed queries on this machine's CPU (needs requirements-local-embed.txt)")
        p.add_argument("--model-url", help="the model server's URL when there is no tunnel to open (e.g. a test)")
        p.add_argument("--embed-url", help="the embedding server's URL when there is no tunnel to open")
        p.add_argument("--output", type=Path, help="the output folder to read the layers from (default: output/)")

    p = sub.add_parser("setup", help="save the instance, key and videos folder; check this machine")
    p.add_argument("--instance")
    p.add_argument("--key")
    p.add_argument("--ssh-port", type=int)
    p.add_argument("--media")
    p.add_argument("--local-embed", action="store_true")
    p = sub.add_parser("run", help="tunnel + viewer + browser")
    conn(p)
    p.add_argument("--media", default=st.get("media"), help="the folder of the lecture videos (L01.mp4 ...)")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--activities", help="activities folder name under output/<course>")
    p.add_argument("--prefer-youtube", action="store_true")
    p.add_argument("--no-tunnel", action="store_true", help="the model and embedder ports are already reachable")
    p.add_argument("--no-browser", action="store_true")
    p.add_argument("--wait-model", type=int, default=1800, help="seconds to wait for the model server")
    p.add_argument("--wait-warm", type=int, default=180, help="seconds to wait for qa's warm-up")
    p = sub.add_parser("tunnel", help="only the SSH tunnel, in the foreground")
    conn(p)
    p = sub.add_parser("check", help="PASS/FAIL checks of a running demo")
    conn(p)
    p.add_argument("--url", default="http://127.0.0.1:8765")
    p.add_argument("--question", default="What is an HMD?")
    p = sub.add_parser("bench", help="time the DEMO_PLAN questions through the stream")
    p.add_argument("--url", action="append", help="a viewer (default http://127.0.0.1:8765); give several to compare "
                                                  "them question by question")
    p.add_argument("--runs", type=int, default=1)
    p.add_argument("--questions", help="a file with one question per line (default: the DEMO_PLAN questions)")
    p.add_argument("--warmup", action="store_true", help="ask the off-stage warm-up question first (not timed)")
    p.add_argument("--out", help="append one JSON line per question to this file")
    p.add_argument("--label", action="append", help="a name per --url, in order")
    p = sub.add_parser("push", help="copy the instance's files over ssh and start ec2_model_server.sh there")
    conn(p)
    p.add_argument("--engine", choices=["llamacpp", "vllm"])
    p.add_argument("--no-start", action="store_true")
    a = ap.parse_args(argv)
    return {"setup": cmd_setup, "run": cmd_run, "tunnel": cmd_tunnel, "check": cmd_check, "bench": cmd_bench,
            "push": cmd_push}[a.cmd](a)
