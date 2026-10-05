"""Embedding-based TextTiling over timestamped subtitles, with globally optimal
boundary selection under a minimum-segment-duration constraint."""
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

EMBED_MODEL = "sentence-transformers/all-mpnet-base-v2"


@dataclass
class Unit:
    start: float
    end: float
    text: str


def _ts(s):
    h, m, rest = s.strip().replace(",", ".").split(":")
    return int(h) * 3600 + int(m) * 60 + float(rest)


def fmt_ts(t):
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"


def fmt_dur(t):
    m, s = divmod(round(t), 60)
    return f"{m}m{s:02d}s"


def parse_srt(path):
    cues = []
    for block in re.split(r"\n\s*\n", Path(path).read_text(encoding="utf-8-sig").strip()):
        lines = block.strip().splitlines()
        i = next((k for k, l in enumerate(lines) if "-->" in l), None)
        if i is None:
            continue
        a, b = lines[i].split("-->")
        text = " ".join(l.strip() for l in lines[i + 1:]).strip()
        if text:
            cues.append(Unit(_ts(a), _ts(b), text))
    return cues


def to_sentences(cues):
    """Merge cues that end mid-sentence into the following cue."""
    units, cur = [], None
    for c in cues:
        cur = Unit(c.start, c.end, c.text) if cur is None else Unit(cur.start, c.end, cur.text + " " + c.text)
        if re.search(r"[.?!][\"')\]]*$", cur.text):
            units.append(cur)
            cur = None
    if cur is not None:
        units.append(cur)
    return units


_model = None


def embed(texts, show_progress=True):
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(EMBED_MODEL)
    return _model.encode(texts, batch_size=32, normalize_embeddings=True,
                         show_progress_bar=show_progress, convert_to_numpy=True)


def gap_similarity(units, emb, window):
    """Cosine similarity between the time windows [t-W, t] and [t, t+W] at every sentence gap."""
    starts = np.array([u.start for u in units])
    ends = np.array([u.end for u in units])
    sims = np.empty(len(units) - 1)
    for g in range(len(units) - 1):
        t = ends[g]
        lo = max(0, min(g, int(np.searchsorted(starts, t - window))))
        hi = max(g + 2, int(np.searchsorted(ends, t + window, side="right")))
        left, right = emb[lo:g + 1].mean(0), emb[g + 1:hi].mean(0)
        sims[g] = left @ right / (np.linalg.norm(left) * np.linalg.norm(right))
    return sims


def smooth(x, k):
    if k <= 0 or len(x) < 3:
        return x.copy()
    pad = np.pad(x, k, mode="edge")
    return np.convolve(pad, np.ones(2 * k + 1) / (2 * k + 1), mode="valid")


def depth_scores(s):
    """Hearst depth: climb to the nearest peak on each side of every gap."""
    d = np.zeros_like(s)
    for g in range(len(s)):
        lp = s[g]
        for i in range(g - 1, -1, -1):
            if s[i] < lp:
                break
            lp = s[i]
        rp = s[g]
        for i in range(g + 1, len(s)):
            if s[i] < rp:
                break
            rp = s[i]
        d[g] = (lp - s[g]) + (rp - s[g])
    return d


def select_boundaries(units, depth, min_seg):
    """Pick the boundary set maximising sum(depth - tau) such that every segment
    (first and last included) lasts at least `min_seg` seconds."""
    n = len(units)

    def dur(a, b):  # units a..b inclusive
        return units[b].end - units[a].start

    # only gaps leaving >= min_seg on both sides can ever be boundaries; this also keeps the
    # truncated-window artefacts at the very start/end out of the threshold statistics
    feasible = [g for g in range(len(depth)) if dur(0, g) >= min_seg and dur(g + 1, n - 1) >= min_seg]
    valleys = [g for g in feasible if depth[g] > 0
               and (g == 0 or depth[g] >= depth[g - 1]) and (g == len(depth) - 1 or depth[g] >= depth[g + 1])]
    if not valleys:
        return [], 0.0
    vd = depth[valleys]
    tau = float(vd.mean() - 0.5 * vd.std())
    cands = [g for g in valleys if depth[g] - tau > 0]

    best, prev = {}, {}
    for c in cands:
        options = []
        if dur(0, c) >= min_seg:
            options.append((0.0, None))
        options += [(best[p], p) for p in best if p < c and dur(p + 1, c) >= min_seg]
        if options:
            score, p = max(options, key=lambda o: o[0])
            best[c], prev[c] = score + depth[c] - tau, p
    ends = [(best[c], c) for c in best if dur(c + 1, n - 1) >= min_seg]
    if not ends:
        return [], tau
    _, c = max(ends, key=lambda o: o[0])
    out = []
    while c is not None:
        out.append(c)
        c = prev[c]
    return sorted(out), tau


def refine_boundaries(units, emb, bounds, min_seg, fine_window, radius):
    """Coarse-to-fine: the wide window finds *where* topics change, but only to within a
    few sentences. Move each boundary to the lowest point of a narrow-window similarity
    curve within +-radius seconds, keeping every segment >= min_seg."""
    fine = smooth(gap_similarity(units, emb, fine_window), 1)
    n = len(units)
    out = list(bounds)
    for k, b in enumerate(out):
        lo_t, hi_t = units[b].end - radius, units[b].end + radius
        prev_start = 0 if k == 0 else out[k - 1] + 1
        next_end = n - 1 if k == len(out) - 1 else out[k + 1]
        cands = [g for g in range(prev_start, next_end)
                 if lo_t <= units[g].end <= hi_t
                 and units[g].end - units[prev_start].start >= min_seg
                 and units[next_end].end - units[g + 1].start >= min_seg]
        if cands:
            out[k] = min(cands, key=lambda g: fine[g])
    return out, fine


def segment(srt_path, window=180.0, min_seg=360.0, smooth_k=2, fine_window=60.0, refine_radius=60.0, log=print):
    cues = parse_srt(srt_path)
    units = to_sentences(cues)
    log(f"parsed {len(cues)} cues -> {len(units)} sentence units "
        f"({fmt_dur(units[-1].end - units[0].start)} of speech)")
    log(f"embedding sentences with {EMBED_MODEL}")
    emb = embed([u.text for u in units])
    log(f"computing window similarity (W={window:g}s) and depth scores")
    raw = gap_similarity(units, emb, window)
    sm = smooth(raw, smooth_k)
    depth = depth_scores(sm)
    log(f"selecting boundaries by DP (min segment {min_seg:g}s)")
    bounds, tau = select_boundaries(units, depth, min_seg)
    log(f"{len(bounds)} boundaries (tau={tau:.4f}) -> {len(bounds) + 1} segments")
    coarse = bounds
    bounds, fine = refine_boundaries(units, emb, bounds, min_seg, fine_window, refine_radius)
    log(f"refined boundaries with a {fine_window:g}s window (±{refine_radius:g}s): " + ", ".join(
        f"{fmt_ts(units[c].end)[:8]}→{fmt_ts(units[b].end)[:8]}" for c, b in zip(coarse, bounds)))

    segs, a = [], 0
    for b in bounds + [len(units) - 1]:
        segs.append({
            "id": f"S{len(segs) + 1:02d}",
            "start": units[a].start,
            "end": units[b].end,
            "text": " ".join(u.text for u in units[a:b + 1]),
            "boundary_depth": float(depth[b]) if b < len(depth) else None,
        })
        a = b + 1
    gaps = [{"time": units[g].end, "sim": float(raw[g]), "sim_smooth": float(sm[g]), "depth": float(depth[g]),
             "sim_fine": float(fine[g]), "boundary": g in bounds} for g in range(len(raw))]
    return segs, gaps, {"window": window, "min_seg": min_seg, "smooth_k": smooth_k,
                        "fine_window": fine_window, "refine_radius": refine_radius,
                        "tau": tau, "embed_model": EMBED_MODEL, "n_units": len(units)}
