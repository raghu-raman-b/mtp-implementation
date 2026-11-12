"""A fake model server for plumbing tests: answers the OpenAI chat API like vLLM, with no model behind it.

    python3 -m scripts.llm.fake_server --port 8094 --model qwen3.8-27b-fp8 [--log requests.jsonl] [--delay 0.2]

Serves /health, /v1/models, /v1/chat/completions, /tokenize and /metrics. A request with a JSON schema
(response_format) gets an answer that fits the schema, built from the schema alone:
- an object has its required properties; a string is "fake <property> <request>.<index>" (different in every
  request and place, so no two fake facts are exact repeats); an integer is its minimum plus the index, within its
  maximum; a boolean is false for every third item (index 1, 4, ...), so a judge's answer fails some facts;
- an array has max(minItems, 2) items (at most maxItems); when its items carry a property with an enum (a judge's
  "fact": [ids]), it has one item per enum value and item i takes value i, so every fact gets exactly one entry;
- anyOf takes its first option; const and enum give their (first) value.
A request without a schema gets "fake answer". Every request can be logged (--log, one JSON line: the messages and
the schema), so a test can check what a stage sent. Not for measuring anything: the answers mean nothing.
"""
from __future__ import annotations

import argparse
import itertools
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def fake(schema: dict, name: str, req: int, index: int = 0):
    """A value that fits the schema (the subset the pipeline's schemas use)."""
    if "const" in schema:
        return schema["const"]
    if "enum" in schema:
        return schema["enum"][index % len(schema["enum"])]
    if "anyOf" in schema:
        return fake(schema["anyOf"][0], name, req, index)
    t = schema.get("type")
    if t == "object":
        props = schema.get("properties", {})
        return {k: fake(props[k], k, req, index) for k in schema.get("required", list(props))}
    if t == "array":
        items = schema.get("items", {})
        n = max(schema.get("minItems", 0), len(_enum_of(items)) or 2)
        if "maxItems" in schema:
            n = min(n, schema["maxItems"])
        return [fake(items, name, req, i) for i in range(n)]
    if t == "integer":
        lo = schema.get("minimum", 0)
        return min(lo + index, schema.get("maximum", lo + index))
    if t == "number":
        return float(schema.get("minimum", 0))
    if t == "boolean":
        return index % 3 != 1
    return f"fake {name} {req}.{index}"


def _enum_of(items: dict) -> list:
    """The enum of a property of the items (first option of an anyOf), or []."""
    obj = items.get("anyOf", [items])[0]
    return next((p["enum"] for p in obj.get("properties", {}).values() if "enum" in p), [])


class FakeServer:
    def __init__(self, port: int, model: str, log: str = "", delay: float = 0.0, host: str = "127.0.0.1"):
        self.model, self.log, self.delay = model, log, delay
        self.count = itertools.count()
        self.requests = 0
        self.lock = threading.Lock()
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, code: int, body, ctype: str = "application/json"):
                data = body.encode() if isinstance(body, str) else json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                if self.path == "/health":
                    self._send(200, {})
                elif self.path == "/v1/models":
                    self._send(200, {"data": [{"id": server.model}]})
                elif self.path == "/metrics":
                    self._send(200, f"vllm:num_requests_running 0\nvllm:num_requests_waiting 0\n"
                                    f"vllm:generation_tokens_total {server.requests * 10}\n", "text/plain")
                else:
                    self._send(404, {"error": "not found"})

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                if self.path == "/tokenize":
                    text = body.get("prompt") or body.get("content") or ""
                    self._send(200, {"count": len(text.split())})
                    return
                if self.path != "/v1/chat/completions":
                    self._send(404, {"error": "not found"})
                    return
                if body.get("model") != server.model:
                    self._send(404, {"error": f"model {body.get('model')!r} does not exist"})
                    return
                self._send(200, server.answer(body))

        self.httpd = ThreadingHTTPServer((host, port), Handler)

    def answer(self, body: dict) -> dict:
        n = next(self.count)
        fmt = (body.get("response_format") or {}).get("json_schema", {})
        content = json.dumps(fake(fmt["schema"], "answer", n)) if fmt else "fake answer"
        if self.delay:
            time.sleep(self.delay)
        with self.lock:
            self.requests += 1
            if self.log:
                with open(self.log, "a") as f:
                    f.write(json.dumps({"n": n, "model": body.get("model"), "messages": body.get("messages"),
                                        "schema": fmt.get("schema"), "seed": body.get("seed")}) + "\n")
        prompt_chars = sum(len(m.get("content") or "") for m in body.get("messages", []))
        return {"choices": [{"message": {"content": content, "reasoning_content": "fake thinking"},
                             "finish_reason": "stop"}],
                "usage": {"prompt_tokens": prompt_chars // 4, "completion_tokens": len(content) // 4}}

    def serve_forever(self):
        self.httpd.serve_forever()

    def start(self) -> "FakeServer":
        """Serve in a background thread (for tests in the same process)."""
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        return self

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--model", required=True, help="the model name it serves (the config's \"model\")")
    ap.add_argument("--log", default="", help="append every chat request to this JSON lines file")
    ap.add_argument("--delay", type=float, default=0.0, help="seconds per answer")
    a = ap.parse_args()
    print(f"fake model {a.model!r} at http://127.0.0.1:{a.port}", flush=True)
    FakeServer(a.port, a.model, a.log, a.delay).serve_forever()


if __name__ == "__main__":
    main()
