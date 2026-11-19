"""Long-context check: how many Gemma 4 tokens are all lecture transcripts (the server's own tokenizer).

    python3 baseline-tests/count_tokens.py      # writes baseline-tests/transcript_tokens.json
"""
import glob
import json
import urllib.request
from pathlib import Path

from common import PORT, ROOT, OUT

per = {}
for f in sorted(glob.glob(str(ROOT / "pipeline/output/nptel_vr/stage_0a_preprocess/lec_*.json"))):
    text = " ".join(json.load(open(f)).values())
    r = urllib.request.urlopen(urllib.request.Request(
        f"http://127.0.0.1:{PORT}/tokenize", data=json.dumps({"content": text}).encode(),
        headers={"Content-Type": "application/json"}))
    per[Path(f).stem] = {"tokens": len(json.load(r)["tokens"]), "words": len(text.split())}
tot = sum(v["tokens"] for v in per.values())
out = {"total_tokens": tot, "total_words": sum(v["words"] for v in per.values()), "lectures": len(per),
       "max_lecture": max(per.items(), key=lambda x: x[1]["tokens"]),
       "server_context": 131072, "server_slots": 6, "per_slot_context": 131072 // 6, "per_lecture": per}
(OUT / "transcript_tokens.json").write_text(json.dumps(out, indent=1))
print({k: v for k, v in out.items() if k != "per_lecture"})
