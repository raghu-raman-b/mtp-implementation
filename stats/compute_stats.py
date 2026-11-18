"""Per-lecture statistics for the dataset -> stats/lecture_stats.csv

Text = subtitle cue text exactly as stored in dataset/<course>/subs (no index/timestamp lines).
Lectures only; tutorials are excluded.

Usage: python stats/compute_stats.py
"""
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "dataset"
OUT = Path(__file__).resolve().parent / "lecture_stats.csv"

COURSES = {  # folder: (short name, provider)
    "virtual_and_augmented_reality": ("VR/AR", "NPTEL"),
    "introduction_to_machine_learning": ("Intro ML", "NPTEL"),
    "problem_solving_through_programming_in_c": ("C Prog.", "NPTEL"),
    "mit_18_06_linear_algebra": ("Lin. Alg.", "MIT"),
    "mit_9_00sc_introduction_to_psychology": ("Psychology", "MIT"),
    "mit_6_7960_deep_learning": ("Deep Learn.", "MIT"),
}

TIME = re.compile(r"^(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2}):(\d{2}):(\d{2}),(\d{3})$")
WORD = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z]+)?")
LABEL = re.compile(r"(?:^|(?<=[.?!\]] ))([A-Z][A-Z.'\- ]{1,30}[A-Z]):")  # e.g. "AUDIENCE:", "SARA BEERY:"
AUDIENCE_LABEL = re.compile(r"^(AUDIENCE|STUDENTS?)$")
TAG = re.compile(r"\[[^\]]{1,40}\]")
DECILES = 10
MATTR_WINDOW = 500

# lecture framing (matched on lowercased, punctuation-free token text)
OPEN_WORDS, CLOSE_WORDS = 100, 100
GREETING = re.compile(r"\b(welcome|hello|good (morning|afternoon|evening)|hi everyone|hi everybody|hi)\b")
SIGNOFF = re.compile(r"\b(thank you|thanks|see you|goodbye|bye|that's all|that is all|end of (this|the) lecture"
                      r"|next (lecture|class|time|week))\b")
BACKWARD = re.compile(r"\b(last|previous|earlier) (lecture|lectures|class|time|week|session)\b")
FORWARD = re.compile(r"\b(next|coming|upcoming|later) (lecture|lectures|class|time|week|session)\b")

# word lists (per 1000 words)
MARKERS = {
    "i": {"i", "i'm", "i've", "i'll", "i'd", "me", "my"},
    "we": {"we", "we're", "we've", "we'll", "we'd", "us", "our", "let's"},
    "you": {"you", "you're", "you've", "you'll", "you'd", "your"},
    "so": {"so"},
    "okay": {"okay", "ok"},
    "right": {"right"},
    "yeah": {"yeah", "yes"},
    "um_uh": {"um", "uh", "uhm", "er", "erm", "hmm"},
}


def ms(h, m, s, f):
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(f)


def read_cues(path):
    blocks = path.read_text(encoding="utf-8").rstrip("\n").split("\n\n")
    cues = []
    for b in blocks:
        _, t, text = b.split("\n")
        g = TIME.match(t).groups()
        cues.append((ms(*g[:4]) / 1000, ms(*g[4:]) / 1000, text))
    return cues


def mattr(tokens, w=MATTR_WINDOW):
    """Moving-average type-token ratio (length-independent vocabulary diversity)."""
    if len(tokens) < w:
        return len(set(tokens)) / max(len(tokens), 1)
    counts, types, total = {}, 0, 0.0
    for i, t in enumerate(tokens):
        counts[t] = counts.get(t, 0) + 1
        types += counts[t] == 1
        if i >= w:
            old = tokens[i - w]
            counts[old] -= 1
            types -= counts[old] == 0
        if i >= w - 1:
            total += types / w
    return total / (len(tokens) - w + 1)


def lecture_row(course, provider, short, srt):
    cues = read_cues(srt)
    text = " ".join(c[2] for c in cues)
    tokens = [w.lower() for w in WORD.findall(text)]
    n = len(tokens)
    end = cues[-1][1]
    duration_min = end / 60
    labels = [m.group(1).strip() for c in cues for m in LABEL.finditer(c[2])]
    sentences = [s for s in re.split(r"(?<=[.?!])\s+", text) if WORD.search(s)]
    # speaking rate per decile of lecture time (words at cue midpoints)
    dec = [0] * DECILES
    for s, e, t in cues:
        k = min(int((s + e) / 2 / end * DECILES), DECILES - 1)
        dec[k] += len(WORD.findall(t))
    dec_wpm = [d / (duration_min / DECILES) for d in dec]
    row = {
        "course": course, "short": short, "provider": provider, "lecture": srt.stem,
        "duration_min": round(duration_min, 2),
        "first_speech_s": round(cues[0][0], 1),
        "words": n,
        "wpm": round(n / duration_min, 1),
        "cues": len(cues),
        "words_per_cue": round(n / len(cues), 2),
        "mattr": round(mattr(tokens), 4),
        "sentences": len(sentences),
        "words_per_sentence": round(n / max(len(sentences), 1), 1),
        "questions_per_1k": round(1000 * text.count("?") / n, 2),
        "speaker_labels": len(labels),
        "audience_turns": sum(bool(AUDIENCE_LABEL.match(l)) for l in labels),
        "audience_turns_per_hour": round(60 * sum(bool(AUDIENCE_LABEL.match(l)) for l in labels) / duration_min, 2),
        "tags": len(TAG.findall(text)),
        "laughter": len(re.findall(r"\[(LAUGHTER|LAUGHS|CHUCKLES)\]", text)),
        "inaudible": text.count("[INAUDIBLE]"),
    }
    low = " ".join(tokens)
    head, tail = " ".join(tokens[:OPEN_WORDS]), " ".join(tokens[-CLOSE_WORDS:])
    row["opens_with_greeting"] = int(bool(GREETING.search(head)))
    row["closes_with_signoff"] = int(bool(SIGNOFF.search(tail)))
    row["backward_refs"] = len(BACKWARD.findall(low))
    row["forward_refs"] = len(FORWARD.findall(low))
    counts = {k: sum(1 for t in tokens if t in v) for k, v in MARKERS.items()}
    for k, v in counts.items():
        row[f"{k}_per_1k"] = round(1000 * v / n, 2)
    for i, v in enumerate(dec_wpm):
        row[f"wpm_d{i + 1}"] = round(v, 1)
    return row


rows = []
for course, (short, provider) in COURSES.items():
    subs = DATASET / course / "subs"
    for srt in sorted(subs.rglob("lec_*.srt")):
        if "tutorials" in srt.parts:
            continue
        rows.append(lecture_row(course, provider, short, srt))

with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
print(f"{len(rows)} lectures -> {OUT}")
