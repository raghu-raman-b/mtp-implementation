"""Print activities (readable view) with their cited facts and the facts' transcript sentences. Read-only.
    python3 analysis/mvp/show.py 4/A3 12/A7 ...      [--no-evidence]"""
import json, re, sys
from pathlib import Path
R = Path(__file__).resolve().parents[2] / "pipeline/output/nptel_vr"
facts = json.load(open(R / "knowledge/facts.json")); C = json.load(open(R / "knowledge/concepts.json"))
txt = (R / "activities/activities.txt").read_text()
blocks = {}
for b in re.split(r"\n(?=\d+/A\d+  )", txt):
    m = re.match(r"(\d+/A\d+)  ", b)
    if m: blocks[m.group(1)] = b.split("\n=====")[0].rstrip()
_sent = {}
def sent(sid):
    L = sid.split("/")[0]
    if L not in _sent:
        _sent[L] = {}
        for p in (R / f"stage_1c_segment_texts/lec_{L}").glob("*.txt"):
            for line in p.read_text().splitlines():
                m = re.match(r"\[(\d+/\d+)\] (.*)", line)
                if m: _sent[L][m.group(1)] = m.group(2)
    return _sent[L].get(sid, "?")
ev = "--no-evidence" not in sys.argv
for aid in [a for a in sys.argv[1:] if not a.startswith("--")]:
    L = aid.split("/")[0]
    a = next(x for x in json.load(open(R / f"activities/lec_{L}.json"))["activities"] if x["id"] == aid)
    print("#" * 100); print(blocks.get(aid, json.dumps(a)[:3000]))
    if a["kind"] == "crossword":
        for e in a["data"]["entries"]:
            print(f"   [{e['answer']}] concept {e['concept']} {C[e['concept']]['name']!r}: def: {C[e['concept']].get('definition','')[:250]}")
    print("  -- cited facts:")
    for f in a["facts"]:
        F = facts[f]; print(f"   {f} ({F['start']:.0f}s): {F['text']}")
        if ev: print("      ev: " + " | ".join(sent(s) for s in F["evidence"])[:350])
