import json, sys
from pathlib import Path
F = json.load(open(Path(__file__).resolve().parents[3] / "pipeline/output/nptel_vr/knowledge/facts.json"))
ids = set(sys.argv[1:])
import os
for l in open(Path(__file__).parent / os.environ.get("QA_FILE", "results.jsonl")):
    r = json.loads(l)
    if ids and r["id"] not in ids: continue
    print("=" * 90); print(r["id"], r["kind"], f"{r['seconds']}s", r["tools"], "covered", r["covered"], "lecture", r["lecture"])
    print("Q:", r["question"]); print("A:", r["answer"])
    for s in r["steps"]: print("   step", s["tool"], json.dumps(s["args"])[:150], "->", str(s.get("result_summary", ""))[:150])
    for c in r["citations"]:
        print(f"   cite {c['fact']} L{c['lecture']} {int(c['start'])//60}:{int(c['start'])%60:02d} {F.get(c['fact'],{}).get('text', c.get('text',''))[:220]}")
