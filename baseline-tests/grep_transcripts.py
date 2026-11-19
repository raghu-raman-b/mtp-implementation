"""Helper: transcript sentences (with times) that contain a word, to check what the course says (or does not).

    python3 baseline-tests/grep_transcripts.py kalman vergence "redirected walking"
"""
import sys

from chunks import lecture_keys, sentences
from common import fmt_time

terms = [t.lower() for t in sys.argv[1:]]
hits = {t: [] for t in terms}
for k in lecture_keys():
    for s in sentences(k):
        low = s["text"].lower()
        for t in terms:
            if t in low:
                hits[t].append(f"  [{s['id']}] ({fmt_time(s['start'])}) {s['text'][:300]}")
for t in terms:
    print(f"=== {t}: {len(hits[t])}")
    print("\n".join(hits[t][:6]))
