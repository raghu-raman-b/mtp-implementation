#!/usr/bin/env python3
"""The query embedder as a small HTTP server, run on the demo's GPU instance next to the model server, so the laptop
that runs the viewer and qa needs neither torch nor the embedding model (1.2 GB) and does not load it at start.

    python demo/embed_server.py [--model Qwen/Qwen3-Embedding-0.6B] [--port 8097] [--host 127.0.0.1] [--device cuda]

Routes (OpenAI style, so any client can use it):
    GET  /health            200 {"status": "ok", "model", "device", "dim"} once the model is loaded; 503 while loading
    GET  /v1/models         {"data": [{"id": <model>}]}
    POST /v1/embeddings     {"model": <model>, "input": str | [str], "encoding_format": "float" | "base64"}
                            -> {"object": "list", "model", "data": [{"object": "embedding", "index", "embedding"}],
                                "usage": {"prompt_tokens", "total_tokens"}}
                            base64: the little-endian float32 vector (4 bytes per dimension), as scripts/embed.py packs
                            its cache; a request naming another model is refused (400), so a vector is never mixed
                            with the knowledge layer's

The vectors are computed exactly as scripts/embed.py computes them locally: sentence-transformers, encode(batch_size=
32, normalize_embeddings=True); the caller applies the query instruction ("Instruct: ...\\nQuery:") before sending,
as it does locally. Same model and library, so the vectors match the layer's fact_embeddings.json (checked by
`python -m demo check`: cosine >= 0.999 on fact texts). Listens on 127.0.0.1 only: reach it through the SSH forward.
Needs torch and sentence-transformers (the instance's ~/demo-venv).
"""
from __future__ import annotations

import argparse
import base64
import json
import struct
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STATE = {"model": None, "name": "", "device": "", "dim": 0, "error": ""}
LOCK = threading.Lock()                       # one encode at a time (the GPU is shared with the model server)


def load(name: str, device: str | None):
    t0 = time.time()
    try:
        from sentence_transformers import SentenceTransformer
        m = SentenceTransformer(name, device=device)
        v = m.encode(["warm up"], batch_size=32, normalize_embeddings=True, convert_to_numpy=True)
        STATE.update(model=m, device=str(m.device), dim=int(v.shape[1]))
        print(f"embedder {name} ready on {m.device} ({time.time() - t0:.0f} s), dimension {STATE['dim']}", flush=True)
    except Exception as e:                    # noqa: BLE001  shown by /health
        STATE["error"] = f"{type(e).__name__}: {e}"
        print(f"embedder failed to load: {STATE['error']}", file=sys.stderr, flush=True)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"             # keep-alive: the client reuses one connection through the SSH forward
    timeout = 900                             # an idle kept connection is closed after this

    def log_message(self, fmt, *args):
        pass

    def send(self, data: dict, code=HTTPStatus.OK):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            if STATE["model"] is None:
                return self.send({"status": "error" if STATE["error"] else "loading", "error": STATE["error"]},
                                 HTTPStatus.SERVICE_UNAVAILABLE)
            return self.send({"status": "ok", "model": STATE["name"], "device": STATE["device"], "dim": STATE["dim"]})
        if self.path == "/v1/models":
            return self.send({"object": "list", "data": [{"id": STATE["name"], "object": "model"}]})
        self.send({"error": "not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b""
        if self.path not in ("/v1/embeddings", "/embeddings"):
            return self.send({"error": "not found"}, HTTPStatus.NOT_FOUND)
        try:
            req = json.loads(raw or b"{}")
            texts = req.get("input")
            texts = [texts] if isinstance(texts, str) else texts
            if not isinstance(texts, list) or not all(isinstance(t, str) for t in texts):
                raise ValueError("input must be a string or a list of strings")
        except ValueError as e:
            return self.send({"error": f"bad request: {e}"}, HTTPStatus.BAD_REQUEST)
        if req.get("model") not in (None, "", STATE["name"]):
            return self.send({"error": f"this server embeds with {STATE['name']}, not {req.get('model')}"},
                             HTTPStatus.BAD_REQUEST)
        m = STATE["model"]
        if m is None:
            return self.send({"error": STATE["error"] or "the model is still loading"}, HTTPStatus.SERVICE_UNAVAILABLE)
        with LOCK:
            vecs = m.encode(texts, batch_size=32, normalize_embeddings=True, convert_to_numpy=True) if texts else []
        b64 = req.get("encoding_format") == "base64"
        data = [{"object": "embedding", "index": i,
                 "embedding": base64.b64encode(struct.pack(f"<{len(v)}f", *v.tolist())).decode() if b64
                 else [float(x) for x in v]} for i, v in enumerate(vecs)]
        toks = sum(len(t.split()) for t in texts)
        self.send({"object": "list", "model": STATE["name"], "data": data,
                   "usage": {"prompt_tokens": toks, "total_tokens": toks}})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="Qwen/Qwen3-Embedding-0.6B")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8097)
    ap.add_argument("--device", default=None, help="cuda, cpu (default: CUDA when there is one)")
    a = ap.parse_args()
    STATE["name"] = a.model
    ThreadingHTTPServer.daemon_threads = True
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    threading.Thread(target=load, args=(a.model, a.device), daemon=True).start()
    print(f"embedding server for {a.model} on http://{a.host}:{a.port} (loading the model)", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
