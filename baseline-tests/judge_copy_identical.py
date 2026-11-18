"""Copy a judgment to every unjudged (qid, system, run) whose answer text is identical to an already judged answer."""
import json, sys
sys.path.insert(0, ".")
from render_for_judge import run_files
from common import OUT
runs = run_files()
p = OUT / "judgments.jsonl"
J = {(j["qid"], j["system"], j["run"]): j for j in map(json.loads, p.open())}
by_text = {}
for (q, s, r), j in J.items():
    a = (runs.get((s, r), {}).get(q, {}).get("answer") or "").strip()
    if a: by_text.setdefault((q, a), j)
n = 0
with p.open("a") as f:
    for (s, r), recs in runs.items():
        for q, rec in recs.items():
            if (q, s, r) in J: continue
            a = (rec.get("answer") or "").strip()
            src = by_text.get((q, a)) if a else None
            if src:
                j = {k: src[k] for k in ("qid", "correct", "hallucinations", "not_covered_handled", "note")}
                j.update(system=s, run=r, judge=f"Opus (identical answer to {src['system']} r{src['run']})")
                f.write(json.dumps(j) + "\n"); n += 1
print("copied", n)
