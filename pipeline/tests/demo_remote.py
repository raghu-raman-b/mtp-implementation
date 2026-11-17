"""Plumbing test of the remote demo's pieces (no GPU, no model, no network beyond 127.0.0.1).

    python3 tests/demo_remote.py

What it looks for (each line is what a broken piece would show):
  pool      two requests to one server not sharing one connection (scripts/llm/http_pool.py); a kept connection
            the server closed while idle failing the next request instead of it going out on a new connection; a
            streamed body read only to its "[DONE]" leaving the connection unusable; keep_warm not calling back with
            the answer of its path
  embed     demo/embed_server.py (with a stand-in model) not answering /health, or not refusing another model's
            name; scripts/embed.Embedder(url=...) not sending the instruction prefix with the text, not decoding the
            base64 float32 vectors, or giving other numbers than the server computed
  launcher  the bundle for the instance (python -m demo push) missing a file the instance needs, with CRLF line
            endings, or the .sh not executable; the tunnel command without both forwards, ExitOnForwardFailure or the
            key; the qa config for a served model name not attach-only with the tunnel's URL; ask_stream not timing
            the events of an NDJSON stream
"""
from __future__ import annotations

import base64
import io
import json
import socket
import struct
import sys
import tarfile
import threading
import time
from argparse import Namespace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FAILURES: list[str] = []


def check(ok: bool, what: str):
    print(f"  {'ok  ' if ok else 'FAIL'} {what}", flush=True)
    if not ok:
        FAILURES.append(what)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def serve(handler, idle_timeout=None) -> tuple[ThreadingHTTPServer, str]:
    if idle_timeout:
        handler.timeout = idle_timeout
    ThreadingHTTPServer.daemon_threads = True
    srv = ThreadingHTTPServer(("127.0.0.1", free_port()), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


class KeepAlive(BaseHTTPRequestHandler):
    """HTTP/1.1: /health (JSON), /stream (chunked SSE ending in [DONE]). Closes a connection idle for 1 s."""
    protocol_version = "HTTP/1.1"
    conns: set = set()

    def log_message(self, *a):
        pass

    def setup(self):
        super().setup()
        KeepAlive.conns.add(self.client_address)

    def do_GET(self):
        body = json.dumps([{"id": 0, "is_processing": True}, {"id": 1, "is_processing": False}]).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        for line in ('data: {"x": 1}\n\n', 'data: {"x": 2}\n\n', "data: [DONE]\n\n"):
            b = line.encode()
            self.wfile.write(b"%x\r\n%s\r\n" % (len(b), b))
        self.wfile.write(b"0\r\n\r\n")


def test_pool():
    from scripts.llm.http_pool import Pool
    print("pool", flush=True)
    srv, url = serve(KeepAlive, idle_timeout=1)
    pool = Pool()
    try:
        for _ in range(3):
            with pool.request("POST", url + "/v1/chat/completions", b"{}", timeout=5) as r:
                for raw in r:
                    if raw.strip() == b"data: [DONE]":
                        break                       # stops at [DONE], as qa does: the pool reads the rest
        check(pool.opened == 1 and len(KeepAlive.conns) == 1,
              f"three streamed requests on one kept connection ({pool.opened} opened)")
        time.sleep(1.6)                             # the server closes the idle connection
        with pool.request("GET", url + "/health", timeout=5) as r:
            ok = r.status == 200 and r.read()
        check(bool(ok) and pool.opened == 2, "a connection the server closed while idle: the request goes out again "
                                             f"on a new one ({pool.opened} opened)")
        seen = []
        pool.keep_warm(url, "/slots", on_body=seen.append)
        check(len(seen) == 1 and json.loads(seen[0])[0]["is_processing"] is True,
              "keep_warm calls back with its path's answer (llama.cpp's /slots)")
    finally:
        srv.shutdown()


class StubModel:
    device = "cpu"

    def encode(self, texts, **kw):
        import numpy as np
        out = np.zeros((len(texts), 8), dtype="float32")
        for i, t in enumerate(texts):
            out[i, len(t) % 8] = 0.6
            out[i, (len(t) + 3) % 8] = 0.8
        return out


def test_embed():
    print("embed", flush=True)
    sys.path.insert(0, str(ROOT / "demo"))
    import embed_server as es
    from scripts.embed import Embedder
    seen = []

    class H(es.Handler):
        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(n)
            seen.append(json.loads(body))
            self.rfile = io.BytesIO(body)
            self.headers.replace_header("Content-Length", str(n))
            super().do_POST()

    es.STATE.update(name="test/Qwen3-Embedding-stub", device="cpu", dim=8, model=None)
    srv, url = serve(H)
    try:
        import urllib.request
        import urllib.error
        try:
            urllib.request.urlopen(url + "/health", timeout=5)
            code = 200
        except urllib.error.HTTPError as e:
            code = e.code
        check(code == 503, f"/health is 503 while the model loads ({code})")
        es.STATE["model"] = StubModel()
        code = urllib.request.urlopen(url + "/health", timeout=5).status
        check(code == 200, "/health is 200 once loaded")
        emb = Embedder("test/Qwen3-Embedding-stub", url=url)
        v = emb.embed(["what is an HMD?", "abc"], instruction="Find facts")
        want = StubModel().encode([emb.prefix("Find facts") + "what is an HMD?", emb.prefix("Find facts") + "abc"])
        check(seen and seen[-1]["encoding_format"] == "base64" and seen[-1]["model"] == "test/Qwen3-Embedding-stub"
              and seen[-1]["input"] == [emb.prefix("Find facts") + "what is an HMD?", emb.prefix("Find facts") + "abc"],
              f"the texts go out with their instruction prefix, as base64 requests ({seen[-1] if seen else None})")
        check(all(abs(a - float(b)) < 1e-7 for x, y in zip(v, want) for a, b in zip(x, y)),
              "the vectors are the server's (base64 float32 decoded, normalised)")
        try:
            Embedder("other/model", url=url).embed(["x"])
            refused = False
        except RuntimeError as e:
            refused = "400" in str(e)
        check(refused, "a request naming another embedding model is refused (400)")
    finally:
        srv.shutdown()


class Events(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        for ev in ({"event": "round", "t": 0.0}, {"event": "step", "label": "Looked up x", "t": 0.1},
                   {"event": "answer_start", "t": 0.2}, {"event": "draft", "text": "A", "t": 0.2},
                   {"event": "done", "result": {"answer": "A", "citations": [{"fact": "1/S1/F1"}]},
                    "timing": {"total": 0.3}}):
            time.sleep(0.05)
            b = json.dumps(ev).encode() + b"\n"
            self.wfile.write(b"%x\r\n%s\r\n" % (len(b), b))
            self.wfile.flush()
        self.wfile.write(b"0\r\n\r\n")


def test_launcher():
    print("launcher", flush=True)
    from demo import launcher as L
    tar = tarfile.open(fileobj=io.BytesIO(L.bundle()), mode="r:gz")
    names = {m.name: m for m in tar.getmembers()}
    need = ["pipeline/demo/ec2_model_server.sh", "pipeline/demo/embed_server.py", "pipeline/demo/demo_tool.py",
            "pipeline/configs/gemma4_12b_demo.json", "pipeline/configs/gemma4_12b_vllm_demo.json",
            "pipeline/scripts/llm/serve.py", "pipeline/scripts/llm/http_pool.py", "pipeline/scripts/__init__.py",
            "pipeline/prompts/qa_tools.json"]
    crlf = [n for n, m in names.items() if m.isfile() and b"\r\n" in tar.extractfile(m).read()]
    check(all(n in names for n in need) and not crlf and names["pipeline/demo/ec2_model_server.sh"].mode == 0o755,
          f"the instance bundle: {len(names)} files, LF only, the script executable "
          f"(missing {[n for n in need if n not in names]}, CRLF {crlf})")
    # what serve.py imports from scripts/llm must be in the bundle
    llm_mods = {p.name for p in (ROOT / "scripts" / "llm").glob("*.py") if p.name != "fake_server.py"}
    check({f"pipeline/scripts/llm/{m}" for m in llm_mods} <= set(names),
          f"every scripts/llm module but the fake server is in the bundle ({sorted(llm_mods)})")
    a = Namespace(key="/k/demo.pem", ssh_port=None, model_port=8096, embed_port=8097, remote_model_port=8096,
                  remote_embed_port=8097, local_embed=False, instance="ubuntu@1.2.3.4")
    cmd = L.tunnel_cmd(a)
    check("-N" in cmd and "ExitOnForwardFailure=yes" in cmd and "8096:127.0.0.1:8096" in cmd
          and "8097:127.0.0.1:8097" in cmd and cmd[cmd.index("-i") + 1].endswith("demo.pem") and cmd[-1] == a.instance,
          f"tunnel command: {' '.join(cmd[1:])}")
    a.local_embed = True
    check("8097:127.0.0.1:8097" not in L.tunnel_cmd(a), "--local-embed: no embedder forward")
    for model, engine in (("gemma-4-12b-qat", "llamacpp"), ("gemma-4-12b", "vllm")):
        eng, path = L.write_qa_config(model, "http://127.0.0.1:18096")
        c = json.loads(path.read_text())
        check(eng == engine and c["url"] == "http://127.0.0.1:18096" and c["launch"] is False and c["model"] == model
              and c["engine"] == engine and c["server_log"] == "",
              f"qa config for {model}: {engine}, attach only, the tunnel's URL ({path.name})")
    srv, url = serve(Events)
    try:
        r = L.ask_stream(url, "q")
        check(r["first_event"] is not None and r["first_event"] <= r["first_step"] <= r["answer_start"]
              <= r["first_draft"] <= r["done"] and r["citations"] == 1 and r["steps"] == ["Looked up x"]
              and r["server_timing"] == {"total": 0.3},
              f"ask_stream times the events ({ {k: r[k] for k in ('first_event', 'first_step', 'answer_start', 'first_draft', 'done')} })")
    finally:
        srv.shutdown()


def main():
    test_pool()
    test_embed()
    test_launcher()
    print("\nPASS: 0 failed" if not FAILURES else f"\nFAIL: {len(FAILURES)} failed")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
