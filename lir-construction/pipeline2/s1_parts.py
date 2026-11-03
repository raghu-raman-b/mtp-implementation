"""Step 1: split each lecture into parts with the v1 standalone-segments prompt (WD 0.09). Code sorts the cuts and
merges parts shorter than MIN_PART_S into a neighbour; every lecture's cuts and merges are logged."""
from __future__ import annotations

from pipeline import prompts as P1
from pipeline.llm import Call
from pipeline.transcript import numbered

from . import addr as A
from .context import Lecture, Part, Run

MIN_PART_S = 120
WINDOW, OVERLAP = 300, 50          # long lectures: overlapping windows of sentences
BOUNDARIES = {"type": "array", "items": {"type": "integer"}}
STEP = "parts"


def _calls(R: Run, llm, lec: Lecture) -> list[Call]:
    s = lec.sentences
    prompt = P1.SEGMENT[2].format(transcript=numbered(s, 1))
    if llm.server.count_tokens(prompt) <= R.seg_max_prompt_tokens:
        wins = [(0, len(s) - 1)]
    else:
        wins, a = [], 0
        while True:
            b = min(a + WINDOW - 1, len(s) - 1)
            wins.append((a, b))
            if b == len(s) - 1:
                break
            a = b + 1 - OVERLAP
        R.log(f"  {lec.id}: transcript too long for one call; {len(wins)} overlapping windows")
    return [Call(key=f"{lec.id}/parts/w{w}", lecture_id=lec.id,
                 prompt=P1.SEGMENT[2].format(transcript=numbered(s[a:b + 1], 1)), schema=BOUNDARIES,
                 prompt_id=P1.SEGMENT[0], prompt_version=P1.SEGMENT[1], max_tokens=12288,
                 ctx={"window": (a, b), "w": w, "n": len(wins)},
                 check=lambda xs: [] if all(isinstance(x, int) for x in xs) else ["answer with integers only"])
            for w, (a, b) in enumerate(wins)]


def _parts(lec: Lecture, starts: list[int]) -> tuple[list[Part], list[str]]:
    s = lec.sentences
    starts = sorted({x for x in starts if 0 < x < len(s)})
    bounds = [0] + starts + [len(s)]
    ranges = [[bounds[i], bounds[i + 1] - 1] for i in range(len(bounds) - 1)]
    dur = lambda r: s[r[1]].end - s[r[0]].start
    merged = []
    while len(ranges) > 1:  # merge the shortest part under MIN_PART_S into its shorter neighbour
        i = min(range(len(ranges)), key=lambda k: dur(ranges[k]))
        if dur(ranges[i]) >= MIN_PART_S:
            break
        j = 1 if i == 0 else i - 1 if i == len(ranges) - 1 else (i - 1 if dur(ranges[i - 1]) <= dur(ranges[i + 1]) else i + 1)
        lo, hi = min(i, j), max(i, j)
        merged.append(f"{lec.s(ranges[i][0])} ({dur(ranges[i]):.0f}s) merged into its neighbour")
        ranges[lo:hi + 1] = [[ranges[lo][0], ranges[hi][1]]]
    parts = [Part(A.part(lec.id, k), k, a, b, s[a].start, s[b].end) for k, (a, b) in enumerate(ranges, 1)]
    return parts, merged


def run_lecture(R: Run, lec: Lecture):
    """Split one lecture into parts (one call, or one per window for a long transcript, windows in parallel)."""
    llm = R.llm(STEP)
    calls = _calls(R, llm, lec)
    outs = [R.send(STEP, c) for c in calls] if len(calls) == 1 else R.flow.map("parts window", lambda c: R.send(STEP, c), calls)
    starts, notes = [], []
    for o in outs:
        a, b = o.call.ctx["window"]
        w, n = o.call.ctx["w"], o.call.ctx["n"]
        if o.parsed is None:
            R.flag(lec.id, f"parts: answer unusable ({o.errors}); window {w} left uncut")
            continue
        # each window owns its middle; in an overlap the cut comes from the window it is deeper inside
        own_lo = a if w == 0 else a + OVERLAP // 2
        own_hi = b if w == n - 1 else b - OVERLAP // 2
        bad = [k for k in o.parsed if not a + 1 <= k <= b + 1]
        if bad:
            notes.append(f"cuts outside the transcript ignored: {bad}")
        starts += [k - 1 for k in o.parsed if own_lo <= k - 1 <= own_hi and k >= 2]
    lec.parts, merged = _parts(lec, starts)
    R.decisions.add(STEP, [lec.id], f"{len(lec.parts)} parts",
                    reason="; ".join([f"model proposed cuts at {[lec.s(k) for k in sorted(set(starts))]}"] + notes + merged))
    R.count("parts", len(lec.parts))
    R.log(f"  {lec.id}: {len(lec.sentences)} sentences -> {len(lec.parts)} parts "
          f"({', '.join(f'{(p.end - p.start) / 60:.1f}' for p in lec.parts)} min)", "dim")
