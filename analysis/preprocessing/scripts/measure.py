"""Measurements for the preprocessing report: stage 0a on all six dataset courses (into a scratch folder: nothing is
written to the pipeline), sentence splitting vs pySBD, and the error of three ways to time a boundary inside a cue.

    cd pipeline && python ../analysis/preprocessing/scripts/measure.py

Writes analysis/preprocessing/data/: course_stats.csv, boundary_time_errors.csv, pysbd_comparison.csv,
pysbd_examples.json.

Reference time of a boundary inside a cue: its character position within the cue, as a fraction of the cue's
duration. It is itself an estimate (exact times would need forced alignment with the audio), but it is local to the
cue, so it shows how far an estimate drifts away from the cue the boundary is in.
"""
from __future__ import annotations

import csv
import json
import random
import re
import statistics as st
import sys
import tempfile
from pathlib import Path

PIPE = Path(__file__).resolve().parents[3] / "pipeline"
DATASET = PIPE.parent / "dataset"
OUT = Path(__file__).resolve().parents[1] / "data"
sys.path.insert(0, str(PIPE))

import pysbd  # noqa: E402

from scripts import lectures, s0a_preprocess as s0a, s1b_verify_segments as s1b  # noqa: E402

COURSES = [("VR (NPTEL)", "virtual_and_augmented_reality"),
           ("Intro to ML (NPTEL)", "introduction_to_machine_learning"),
           ("Programming in C (NPTEL)", "problem_solving_through_programming_in_c"),
           ("MIT 18.06 Linear Algebra", "mit_18_06_linear_algebra"),
           ("MIT 9.00SC Psychology", "mit_9_00sc_introduction_to_psychology"),
           ("MIT 6.7960 Deep Learning", "mit_6_7960_deep_learning")]
METHODS = ["forward", "sentences", "cue"]


def subs_of(folder: str) -> Path:
    return (PIPE / "input" / "nptel_vr" / "input" / "subs") if folder == "virtual_and_augmented_reality" \
        else DATASET / folder / "subs"


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    seg = pysbd.Segmenter(language="en", clean=False, char_span=True)
    stats, errors, sbd_rows, sbd_examples = [], [], [], {}
    for name, folder in COURSES:
        subs = subs_of(folder)
        tmpdir = tempfile.TemporaryDirectory(prefix="pre_")      # removed when this course is done
        tmp = Path(tmpdir.name)
        r = s0a.run(folder, subs=subs, out_dir=tmp)
        meta = json.loads((tmp / "times" / "meta.json").read_text())
        words, inside, total_bounds, labels, tags, inaudible, notice = [], 0, 0, 0, 0, 0, 0
        agree = only_mine = only_sbd = n_mine = n_sbd = 0
        ex_mine, ex_sbd = [], []
        for srt in sorted(subs.rglob("*.srt"), key=lambda p: lectures.order(lectures.key_of(p.stem))):
            stem, key = srt.stem, lectures.key_of(srt.stem)
            raw = srt.read_text(encoding="utf-8-sig")
            tags += len(s0a.SOUND.findall(raw))
            inaudible += raw.count("[INAUDIBLE]")
            sents = json.loads((tmp / f"{stem}.json").read_text())
            times = json.loads((tmp / "times" / f"{stem}.json").read_text())
            timeline = json.loads((tmp / "times" / "cues" / f"{stem}.json").read_text())
            notice += 1 if timeline["skip_words"] else 0
            words += [len(x.split()) for x in sents.values()]
            labels += sum(1 for p in sents.values() if s0a.LABEL.match(p) and s0a.speaker_labels(p)[:1] == [0])
            ids = list(sents)
            # sentence starts after the first: how many fall inside a cue
            total_bounds += len(ids) - 1
            inside += sum(times[i]["start"] is None for i in ids[1:])
            # boundary-time errors against the in-cue reference
            cues = s0a.parse_srt(srt)
            pos, spans_c = 0, []
            for a, b, t in cues:
                spans_c.append((pos, pos + len(t), a, b))
                pos += len(t) + 1
            text = " ".join(t for _, _, t in cues)
            spans = s0a.sentence_spans(text)
            while spans and s0a.NOTICE.search(text[spans[0][0]:spans[0][1]]):
                spans.pop(0)
            tms = {m: s1b.Timing(ids, sents, times, meta["wpm_median"], timeline, m) for m in METHODS}
            for i, (a, _) in enumerate(spans):
                if i == 0 or times[ids[i]]["start"] is not None:
                    continue
                c = next(c for c in spans_c if c[0] <= a <= c[1])
                ref = c[2] + (c[3] - c[2]) * (a - c[0]) / max(1, c[1] - c[0])
                for m in METHODS:
                    errors.append({"course": name, "method": m, "lecture": key,
                                   "error_s": round(abs(tms[m].before(i)[0] - ref), 3), "cue_s": round(c[3] - c[2], 3)})
            # pySBD on the same cleaned text: sentence-end positions compared
            mine = {len(text[:b].rstrip()) for _, b in s0a.sentence_spans(text)}
            sbd = {len(text[:sp.end].rstrip()) for sp in seg.segment(text)}
            n_mine, n_sbd = n_mine + len(mine), n_sbd + len(sbd)
            agree += len(mine & sbd)
            only_mine += len(mine - sbd)
            only_sbd += len(sbd - mine)
            ctx = lambda b: text[max(0, b - 70):b] + " ‖ " + text[b:b + 60]  # noqa: E731
            ex_mine += [ctx(b) for b in sorted(mine - sbd)]
            ex_sbd += [ctx(b) for b in sorted(sbd - mine)]
        rnd = random.Random(0)
        sbd_examples[name] = {"only_ours": rnd.sample(ex_mine, min(12, len(ex_mine))),
                              "only_pysbd": rnd.sample(ex_sbd, min(12, len(ex_sbd)))}
        sbd_rows.append({"course": name, "ours": n_mine, "pysbd": n_sbd, "agree": agree,
                         "only_ours": only_mine, "only_pysbd": only_sbd})
        stats.append({"course": name, "lectures": r["lectures"], "sentences": r["sentences"],
                      "words_per_sentence_median": st.median(words), "words_per_sentence_p90": pct(words, .9),
                      "words_per_sentence_max": max(words),
                      "sentence_starts_inside_cue": inside, "sentence_starts": total_bounds,
                      "inside_cue_pct": round(100 * inside / total_bounds, 1),
                      "wpm_median": meta["wpm_median"], "speaker_turns": labels, "sound_tags_removed": tags,
                      "inaudible_kept": inaudible, "licence_notices_dropped": notice})
        tmpdir.cleanup()
        print(name, "done", flush=True)
    with open(OUT / "course_stats.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(stats[0]))
        w.writeheader()
        w.writerows(stats)
    with open(OUT / "boundary_time_errors.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(errors[0]))
        w.writeheader()
        w.writerows(errors)
    with open(OUT / "pysbd_comparison.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(sbd_rows[0]))
        w.writeheader()
        w.writerows(sbd_rows)
    (OUT / "pysbd_examples.json").write_text(json.dumps(sbd_examples, indent=1, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
