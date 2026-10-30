"""Stage 1: segment each lecture with the standalone-segments prompt, then let code fix the boundaries."""
from __future__ import annotations

from . import prompts as P
from .context import Lec, Run, Seg
from .llm import Call
from .transcript import numbered

MIN_SEG_S = 120     # shorter segments are merged into a neighbour
MAX_SEG_S = 720     # longer segments are flagged
WINDOW, OVERLAP = 300, 50
THINK_BUDGET = 12288

BOUNDARIES = {"type": "array", "items": {"type": "integer"}}


def _calls(R: Run, lec: Lec) -> list[Call]:
    s = lec.sentences
    prompt = P.SEGMENT[2].format(transcript=numbered(s, 1))
    if R.server.count_tokens(prompt) <= R.seg_max_prompt_tokens:
        wins = [(0, len(s) - 1)]
    else:  # overlapping windows, boundaries reconciled afterwards
        wins, a = [], 0
        while True:
            b = min(a + WINDOW - 1, len(s) - 1)
            wins.append((a, b))
            if b == len(s) - 1:
                break
            a = b + 1 - OVERLAP
        R.log(f"  {lec.id}: transcript too long for one call, segmenting in {len(wins)} overlapping windows")
    calls = []
    for w, (a, b) in enumerate(wins):
        text = numbered(s[a:b + 1], 1)  # numbers stay global (1-based) inside windows
        calls.append(Call(key=f"{lec.id}/segment/w{w}", lecture_id=lec.id, prompt=P.SEGMENT[2].format(transcript=text),
                          schema=BOUNDARIES, prompt_id=P.SEGMENT[0], prompt_version=P.SEGMENT[1],
                          max_tokens=THINK_BUDGET, ctx={"window": (a, b), "n_windows": len(wins), "w": w},
                          check=lambda nums, a=a, b=b: [] if all(isinstance(x, int) for x in nums) else ["not integers"]))
    return calls


def _segments(lec: Lec, starts: list[int]) -> list[Seg]:
    s = lec.sentences
    starts = sorted({x for x in starts if 0 < x < len(s)})
    bounds = [0] + starts + [len(s)]
    ranges = [[bounds[i], bounds[i + 1] - 1] for i in range(len(bounds) - 1)]
    dur = lambda r: s[r[1]].end - s[r[0]].start
    # merge segments under MIN_SEG_S into the shorter neighbour, shortest first
    while len(ranges) > 1:
        i = min(range(len(ranges)), key=lambda k: dur(ranges[k]))
        if dur(ranges[i]) >= MIN_SEG_S:
            break
        if i == 0:
            j = 1
        elif i == len(ranges) - 1:
            j = i - 1
        else:
            j = i - 1 if dur(ranges[i - 1]) <= dur(ranges[i + 1]) else i + 1
        lo, hi = min(i, j), max(i, j)
        ranges[lo:hi + 1] = [[ranges[lo][0], ranges[hi][1]]]
    segs = []
    for k, (a, b) in enumerate(ranges, 1):
        seg = Seg(f"S{k}", a, b, s[a].start, s[b].end)
        if seg.end - seg.start > MAX_SEG_S:
            seg.flags.append("long_segment")
        segs.append(seg)
    return segs


def run(R: Run):
    calls = [c for lec in R.lectures for c in _calls(R, lec)]
    outs = R.llm.run("stage1_segment", calls, "segment lectures")
    by_lec: dict[str, list] = {}
    for o in outs:
        by_lec.setdefault(o.call.lecture_id, []).append(o)
    for lec in R.lectures:
        starts, raw_errors = [], []
        for o in by_lec[lec.id]:
            a, b = o.call.ctx["window"]
            w, n = o.call.ctx["w"], o.call.ctx["n_windows"]
            # each window owns its middle; in an overlap the boundary comes from the window it is deeper inside
            own_lo = a if w == 0 else a + OVERLAP // 2
            own_hi = b if w == n - 1 else b - OVERLAP // 2
            nums = o.parsed or []
            if not o.ok or o.parsed is None:
                R.flag(lec.id, f"segmentation answer unusable ({o.errors}); window {w} left uncut")
            bad = [k for k in nums if not (a + 1 <= k <= b + 1)]
            if bad:
                raw_errors.append(f"boundary numbers out of range: {bad}")
            if nums != sorted(set(nums)):
                raw_errors.append("boundaries not strictly increasing (sorted by code)")
            starts += [k - 1 for k in nums if own_lo <= k - 1 <= own_hi and k >= 2]
            R.record(o, "stage1_segment", f"{lec.id}.segmentation.w{w}")
        lec.origin[-1]["validator"]["code_repairs"] = raw_errors
        lec.segments = _segments(lec, starts)
        R.log(f"  {lec.id}: {len(lec.sentences)} sentences, {len(starts)} proposed cuts -> {len(lec.segments)} segments "
              f"({', '.join(f'{(s.end - s.start) / 60:.1f}' for s in lec.segments)} min)")
        for s in lec.segments:
            if "long_segment" in s.flags:
                R.log(f"    {lec.id}/{s.id} is {(s.end - s.start) / 60:.1f} min long (flagged)")
    R.dump("stage1_segments", {l.id: [vars(s) for s in l.segments] for l in R.lectures})
