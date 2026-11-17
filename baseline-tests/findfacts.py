"""Helper for writing the gold answers: print the facts (and concept cards) whose text matches all the words given.

    python3 baseline-tests/findfacts.py presence immersion       # facts with both words
    python3 baseline-tests/findfacts.py -c "head-related transfer function"   # the concept card
"""
import json
import sys

from common import DATA, fmt_time

K = DATA / "knowledge"
facts = json.loads((K / "facts.json").read_text())
if sys.argv[1] == "-c":
    concepts = json.loads((K / "concepts.json").read_text())
    names = json.loads((K / "names.json").read_text())
    q = " ".join(sys.argv[2:]).lower()
    for cid, c in concepts.items():
        if c["name"].lower() == q or q in [a.lower() for a in c.get("aliases", [])]:
            print(cid, c["name"], c.get("aliases"), "\nDEF:", c.get("definition"))
            for d in c.get("defined_in", []):
                print("  defined in", d["lecture"], fmt_time(d["start"]), d["facts"])
            print("  facts:", c["facts"][:25])
    sys.exit()
words = [w.lower() for w in sys.argv[1:]]
for fid, f in facts.items():
    t = f["text"].lower()
    if all(w in t for w in words):
        print(f"[{fid}] ({fmt_time(f['start'])}) {f['text']}")
