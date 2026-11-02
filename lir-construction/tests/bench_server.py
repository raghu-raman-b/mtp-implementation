"""Engine benchmark (README, "Engines"): throughput of an OpenAI-compatible server on pipeline-like calls: transcript chunk + task, thinking on, JSON schema.

    python3 tests/bench_server.py http://127.0.0.1:8091 Qwen/Qwen3.8-27B-FP8 1,32,64,128   # server from serve_lir2.py
Each level sends C requests at once (one wave) and reports output tokens per second over the wave.
"""
import argparse, json, random, re, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("url"); ap.add_argument("model"); ap.add_argument("levels")
ap.add_argument("--max-tokens", type=int, default=1500)
ap.add_argument("--sampling", default='{"temperature": 1.0, "top_p": 0.95, "top_k": 20}')
a = ap.parse_args()

srts = sorted((Path(__file__).resolve().parents[2] / "dataset/virtual_and_augmented_reality/subs").rglob("*.srt"))
lines = []
for f in srts:
    txt = [l.strip() for l in f.read_text(errors="replace").splitlines()
           if l.strip() and not l.strip().isdigit() and "-->" not in l]
    lines.append(txt)
random.seed(0)
SCHEMA = {"type": "object", "properties": {"terms": {"type": "array", "items": {"type": "object", "properties": {
    "term": {"type": "string"}, "definition": {"type": "string"}, "sentences": {"type": "array", "items": {"type": "integer"}}},
    "required": ["term", "definition", "sentences"]}}}, "required": ["terms"]}


def prompt(k):
    t = lines[k % len(lines)]
    s = random.randrange(0, max(1, len(t) - 120))
    chunk = "\n".join(f"[{i}] {x}" for i, x in enumerate(t[s:s + 120]))
    return ("You are building study material for a university course on virtual and augmented reality.\n\n"
            f"Transcript sentences:\n{chunk}\n\nList every technical term this passage teaches, with a one-sentence "
            "definition from the passage and the sentence numbers it comes from. Answer in JSON.")


def call(k):
    body = {"model": a.model, "messages": [{"role": "user", "content": prompt(k)}], "max_tokens": a.max_tokens,
            "seed": k, "chat_template_kwargs": {"enable_thinking": True},
            "response_format": {"type": "json_schema", "json_schema": {"name": "a", "schema": SCHEMA, "strict": True}}}
    body.update(json.loads(a.sampling))
    req = urllib.request.Request(a.url + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=3600) as r:
        d = json.load(r)
    u = d["usage"]
    return u["prompt_tokens"], u["completion_tokens"], time.time() - t0


call(10_000)  # warm-up
for c in [int(x) for x in a.levels.split(",")]:
    t0 = time.time()
    with ThreadPoolExecutor(c) as ex:
        rs = list(ex.map(call, range(c)))
    wall = time.time() - t0
    out = sum(r[1] for r in rs); inp = sum(r[0] for r in rs)
    print(f"C={c:4d}  wall {wall:6.1f}s  out {out:7d} tok  -> {out / wall:7.0f} tok/s aggregate  "
          f"{out / c / (sum(r[2] for r in rs) / c):5.1f} tok/s per stream  (prompt avg {inp // c} tok)", flush=True)
