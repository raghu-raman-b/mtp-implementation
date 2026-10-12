#!/usr/bin/env python
"""LLM baseline: ask Gemma 4 (the pipeline's llama-server model) for the boundaries directly.

    python compare/gemma_baseline.py

The model sees the whole transcript as numbered sentences and returns the sentence numbers that
start a new segment (no hint about how many): methods.gemma.

Validation: each proposed cut is then checked on its own. The model sees the sentences around it and
judges whether the segment after it would stand alone. A cut that fails is either dropped, merging
the two segments (methods.gemma_merge), or moved to a concluded point nearby (methods.gemma_fix). Results go to
compare/results.json (run snap_slides.py afterwards for the slide-snapped variant).
"""
import json
import re
import sys
from pathlib import Path

import run_compare as rc

HERE = Path(__file__).resolve().parent
SEEDS = [0, 1, 2, 3, 4]
sys.path.insert(0, str(HERE.parent))
import run  # noqa: E402
from goals import LLM  # noqa: E402

PROMPT = """Below is the transcript of a lecture video, one sentence per line, each with its number in brackets.

Split the lecture into segments. Find the apt boundaries: the points where the instructor has completed an \
instructional goal or a topic and moves on to the next one.

Each segment must stand alone: a learner who starts watching at the first sentence of any segment, without \
having seen what came before, must be able to follow it. Cut only at a logically concluded point, after the \
instructor has finished the thought, never while he is in the middle of explaining something. A question and \
the discussion of that question belong in the same segment. Do not cut at every change of example or \
sentence-level aside; prefer fewer, complete segments over many fragments.

Answer with a JSON list of the sentence numbers that START a new segment (do not include sentence 1), in \
order, and nothing else. Example of the format: [14, 52, 97]

Transcript:
{transcript}"""

# second pass, one call per proposed cut: the single-pass answer still cuts mid-thought
CHECK = """A lecture video is being split into segments that learners can watch on their own. Below is a short \
stretch of the transcript with a proposed cut in it.

{before}
======== proposed cut ========
{after}

Decide whether this is a good place to cut.

GOOD: the instructor has finished the previous point, and what follows the cut opens a new topic or goal that \
a learner could follow without having heard what came before the cut.

BAD: the instructor is still in the middle of the same thought. For example, the text after the cut answers, \
comments on or continues what was said just before it, or its first sentence only makes sense because of the \
sentence before it.

Answer with one word: GOOD or BAD."""
CONTEXT = 5  # sentences shown on each side of a proposed cut

# "fix" option: instead of dropping a bad cut, let the model move it within the surrounding stretch
FIX = """A lecture video is being split into segments that learners can watch on their own. A cut was proposed \
just before sentence [{cut}] below, but there the instructor is still in the middle of a thought.

{window}

Find the nearest place in this stretch where a cut does work: the instructor has finished the previous point, \
and the sentence that follows opens a new topic or goal that a learner could follow without having heard what \
came before.

Answer with the number of the sentence that should START the new segment. If the whole stretch is one \
continuous thought and no such place exists, answer NONE. Answer with the number or NONE only."""
FIX_CONTEXT = 8  # sentences on each side offered as alternative positions


def main():
    res = json.loads((HERE / "results.json").read_text())
    units = [rc.tt.Unit(u["start"], u["end"], u["text"]) for u in res["units"]]
    gold = res["gold"]
    ev_of = lambda gaps: rc.evaluate(gaps, units, gold["gaps"], gold["times"])
    prompt = PROMPT.format(transcript="\n".join(f"[{i + 1}] {u.text}" for i, u in enumerate(units)))
    run.OUT_ROOT.mkdir(exist_ok=True)
    # proposals and verdicts from an earlier run of the same prompts are reused
    cache_file = HERE / "gemma_cache.json"
    cache = json.loads(cache_file.read_text()) if cache_file.exists() else {}
    if cache.get("prompts") != [PROMPT, CHECK, FIX]:
        cache = {"prompts": [PROMPT, CHECK, FIX], "seeds": {}}
    checker = LLM("http://127.0.0.1:8080", seed=0, temperature=0.0)
    single, merged, fixed = [], [], []
    for seed in SEEDS:  # seed 0 at temperature 0 is the headline run; the others show how stable the answer is
        c = cache["seeds"].setdefault(str(seed), {})
        temp = 0.0 if seed == 0 else 0.7
        if "answer" not in c:
            llm = LLM("http://127.0.0.1:8080", seed=seed, temperature=temp)
            run.ensure_llm(llm, 8080)
            llm.chat(prompt, f"gemma boundaries (seed {seed})")
            c["answer"] = llm.log[-1][3]
        nums = [int(x) for x in re.findall(r"\d+", re.search(r"\[[\d,\s]*\]", c["answer"]).group())]
        # sentence number k (1-based) starting a segment -> the gap after unit k-2
        proposed = sorted({k - 2 for k in nums if 2 <= k <= len(units)})

        # validation: is each proposed cut at a concluded point?
        verdicts = c.setdefault("verdicts", {})
        for g in proposed:
            if str(g) not in verdicts:
                run.ensure_llm(checker, 8080)
                checker.chat(CHECK.format(before="\n".join(u.text for u in units[max(0, g - CONTEXT + 1):g + 1]),
                                          after="\n".join(u.text for u in units[g + 1:g + 1 + CONTEXT])), f"check cut {g}")
                verdicts[str(g)] = "BAD" not in checker.log[-1][3].upper()
        good = [g for g in proposed if verdicts[str(g)]]
        bad = [g for g in proposed if not verdicts[str(g)]]

        # option 2: move each bad cut to a concluded point nearby, staying between its neighbouring cuts
        moves = c.setdefault("moves", {})
        for g in bad:
            if str(g) not in moves:
                lo = max([p + 2 for p in proposed if p < g] + [g - FIX_CONTEXT + 1, 1])
                hi = min([p for p in proposed if p > g] + [g + FIX_CONTEXT + 1, len(units) - 1])
                window = "\n".join(f"[{i + 1}] {units[i].text}" for i in range(lo - 1, hi + 1))
                run.ensure_llm(checker, 8080)
                checker.chat(FIX.format(cut=g + 2, window=window), f"fix cut {g}")
                m = re.search(r"\d+", checker.log[-1][3])
                k = int(m.group()) if m and "NONE" not in checker.log[-1][3].upper() else None
                moves[str(g)] = k - 2 if k and lo <= k - 2 <= hi - 1 and k - 2 != g else None
        fix = sorted(set(good) | {moves[str(g)] for g in bad if moves[str(g)] is not None})
        cache_file.write_text(json.dumps(cache, indent=1))

        base = {"seed": seed, "temperature": temp}
        single.append({**base, "answer": c["answer"], "sentence_numbers": nums, **ev_of(proposed)})
        merged.append({**base, "dropped": bad, **ev_of(good)})
        fixed.append({**base, "moved": {str(g): moves[str(g)] for g in bad if moves[str(g)] is not None},
                      "dropped": [g for g in bad if moves[str(g)] is None], **ev_of(fix)})
        ts = lambda g: f"{int(units[g + 1].start // 60):02d}:{int(units[g + 1].start % 60):02d}"
        print(f"seed {seed} T={temp}: single pass {len(proposed) + 1} segments WD {single[-1]['wd']:.3f} | "
              f"merge {len(good) + 1} segments WD {merged[-1]['wd']:.3f} | fix {len(fix) + 1} segments WD {fixed[-1]['wd']:.3f}", flush=True)
        if seed == 0:
            for g in proposed:
                what = "keep" if verdicts[str(g)] else ("drop" if moves[str(g)] is None else f"move to {ts(moves[str(g)])}")
                print(f"   {ts(g)} {what:<14} {units[g + 1].text[:80]}", flush=True)
                if not verdicts[str(g)] and moves[str(g)] is not None:
                    print(f"         {'':<14} -> {units[moves[str(g)] + 1].text[:80]}", flush=True)
    meta = {"model": "gemma-4-E4B-it (UD-Q8_K_XL, llama.cpp)", "prompt": PROMPT, "check_prompt": CHECK, "fix_prompt": FIX,
            "context_sentences": CONTEXT, "fix_context_sentences": FIX_CONTEXT}
    res["methods"]["gemma"] = {"runs": single, "meta": meta}
    res["methods"]["gemma_merge"] = {"runs": merged, "meta": meta}
    res["methods"]["gemma_fix"] = {"runs": fixed, "meta": meta}
    (HERE / "results.json").write_text(json.dumps(res, indent=1) + "\n")


if __name__ == "__main__":
    main()
