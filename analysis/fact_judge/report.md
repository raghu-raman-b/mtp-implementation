# Block 1 report: the fact judge (stage 2b)

2026-11-12. Plan: `pipeline/PLAN.md`, block 1. All numbers come from `analysis/fact_judge/compare.py` (its output:
`report_compare.md`, `compare.json`, `runs/*.json`, `rejudge.md`) unless a file is named.

## 1. What ran

| Run | What | Calls | Where it is |
|---|---|--:|---|
| Fresh 2b (block 0 item 5) | Sage-A1.5 judges the 62 facts of 2a on lectures 1, 4, 16; Qwen rewrites the failures | 12 + 5 | `pipeline/output/nptel_vr/stage_2b_verify_facts/`, log `pipeline/output/logs/facts_fresh_2b.log` |
| `base` | the same judge calls as 2b (their answers are 2b's, from 2b's cache), plus the 34 seeded entries | 12 + 34 | `runs/base.json` |
| `seed1`, `seed2` | the same calls with judge seeds 1 and 2 | 46 each | `runs/seed1.json`, `runs/seed2.json` |
| `old_1112` | the interrupted round of the morning: the same requests as `base`, same seed | 12 | `runs/old_1112.json` |
| Rewrites judged again (test only) | the final facts of every segment with a rewrite, one judge call each | see section 5 | `runs/rejudge.json`, `rejudge.md` |

Judge: `configs/sage_a15_vllm.json` (Sage-A1.5 FP8, temperature 1.0, thinking up to 16,384 tokens), prompt
`fact_judge.txt` + `fact_judge_system.txt` (hash 09a26b62f66a in every run). The model runs on the EC2; the scripts on
the local PC through the SSH forward. References: `gold.json` (62 facts: 55 pass, 7 fail, 7 borderline; one labeller,
not blind), `seeded.json` (34 entries, one per call, 11 kinds), `missed.json` (5 points 2a missed).

## 2. The numbers

**Gate (proposed targets), on `base`:**

| Target | `base` | `seed1` | `seed2` | Met |
|---|--:|--:|--:|---|
| Seeded errors caught ≥ 90% | 32/34 (94%) | 30/34 (88%) | 32/34 (94%) | yes on `base`; one seed below |
| False alarms on gold-pass facts ≤ 10% (judge) | 4/55 (7%) | 3/55 (5%) | 5/55 (9%) | yes |
| False alarms ≤ 10%, as 2b applies them (judge + code checks) | 7/55 (13%) | 6/55 (11%) | 8/55 (15%) | no |
| Flips ≤ 5% | 9/62 (15%) of gold facts over the three runs | | | **no** |
| No property with zero catches (seeded) | met | | | yes |

**What the gate does not show: the judge misses most real failures.** Gold fails 7 of the 62 facts; the judge fails
1 of them in `base` and `seed1`, none in `seed2` (2 in `old_1112`).

| Gold failure | Property (gold) | Caught in base / seed1 / seed2 / old |
|---|---|---|
| 1/S0/F1 a 120-word summary of motivating examples; "3D or 4D" | 1, 2, 6 | yes / no / no / yes |
| 1/S5/F0 "this field" named as the paper's title, not VR and AR | 8 | no in all |
| 16/S1/F5 the lecturer's "may not be required" became "is not required" | 8 | no / yes / no / yes |
| 16/S2/F3 "most VR headsets use outside-in" became a statement true by definition | 8 | no in all |
| 16/S3/F0 restates a recap of the previous segment | 2 | no in all |
| 16/S0/F0, F1 one point split into two thin facts (borderline) | 2 | no in all |

Per property (`base`): Faithful 0 of 3 caught (1 of 3 in `seed1` and in `old_1112`); Whole 1 of 4; Significant 1 of 1 and Terms in full 1 of 1 (the same
fact, 1/S0/F1, failed for another property). The seeded errors are caught because they are blatant; the real ones are
subtle, and the judge's reasons for passing them are generic ("passes all eight properties: it is significant, ...").

## 3. Failure kinds, with examples

1. **Faithfulness not checked against the sentence.** A dropped hedge (16/S1/F5, seeded E34: "in a very broad sense",
   "sometimes" removed) passes; the judge restates the fact and calls it faithful. The judge caught the hedge in 16/S1/F5
   in `seed1` and in the morning round, so it can see it; it does not look every time.
2. **Whole: recaps and thin splits.** 16/S3/F0 restates a recap that the previous segment taught (16/S2/F1); 16/S0/F0
   and F1 are one point in two. The judge reads each as "one complete point". It does apply Whole in the other
   direction, sometimes too eagerly (false alarms below).
3. **False alarms on Whole and Significant.** `base` fails 4 gold-pass facts: 1/S3/F4 (Whole: "the term's 30-year
   history and its role in the field's growth"), 1/S3/F5 (borderline; Whole), 4/S1/F0 (borderline; "a summary of the
   segment", while gold reads it as the list of the three characteristics the extraction prompt asks for), 16/S0/F4
   (Significant: a terminology note). 1/S3/F4 and 1/S3/F5 were then rewritten, and the rewrite of 1/S3/F4 dropped the
   history.
4. **An acronym alone passes.** Seeded E22 ("VR" without its full term) passes in all three runs; the judge says
   "uses full terms with acronyms as in the segment". The code check `bare_acronym` flags it but only reports.
5. **Noise.** 9 of 62 gold facts flip across three seeds (1/S0/F1, 1/S3/F4, 1/S3/F5, 1/S3/F8, 16/S0/F3, 16/S0/F4,
   16/S1/F5, 16/S2/F6, 16/S3/F1); 4 of 34 seeded entries flip. The same request with the same seed (`base` against
   `old_1112`) also gives different verdicts: vLLM does not reproduce a sampled answer across batches, so a fixed seed
   is not a fix.
6. **Seeded calls also fail other facts.** 7 non-seeded facts failed in seeded calls of `base`, 3 of them passed in
   `base`'s own call (1/S3/F8, 16/S2/F6, 16/S2/F3): the same noise.

## 4. The code checks against gold

| Check | Flagged | Agree with gold | False alarms | Gold failures it misses |
|---|--:|--:|---|---|
| `pointing` (property 5) | 3 | 0 | 4/S1/F3, 16/S1/F9, 16/S1/F11 | none (gold fails no fact on 5) |
| `acronym` (property 6) | 0 | 0 | none | 1/S0/F1 ("3D", "4D" start with a digit) |

All three code-only failures of 2b are false alarms by gold: each "this" points at something named in the same
sentence ("this immersive experience", "for this", "this is generally classified"). They were rewritten anyway. The
four seeded entries marked `code` (a leading pronoun, "the lecturer"/"here", "this type", an unused acronym) are all
flagged; the judge alone missed E20 ("the lecturer", "here") once. This is the evidence D1 asked for.

## 5. The rewrites judged again (test only)

`compare.py rejudge`: the 4 segments with a rewrite, each judged once more with its final facts (30 facts, 8 of them
rewrites), as 2b's judge would see them; `rejudge.md`, `runs/rejudge.json`, log `pipeline/output/logs/judge_test_rejudge.log`.

- **2 of 8 rewrites still fail (25%).** 4/S1/F0 (rewritten from "a summary of the segment") fails again for Whole.
  1/S3/F6, one half of the split of 1/S3/F5, fails for Whole because it is the same point as 1/S3/F7, a fact that was
  kept; the judge now fails 1/S3/F7 too. The split made the facts worse: before it, 1/S3/F5 held the point and F7 its
  detail; after it, F6 and F7 are two thin halves of one point.
- The other 6 pass, among them the three code-check rewrites (4/S1/F3, 16/S1/F9, F11), whose "this" is now spelled
  out (gold passed the originals).
- One more call fails 1 of the 22 kept facts (1/S3/F7): the noise of section 3.5 again.

So D2 (rewrites not judged again) leaves about a quarter of the rewrites failing, and a split can turn a passing
neighbour into a failure; a second judge call on rewrites would catch these but cost one call per segment with a
rewrite (4 of 12 segments here).

## 6. Weak points

1. The judge's recall on real, subtle failures is about 1 in 7; the proposed gate measures only blatant ones. A judge
   that passes everything subtle would still meet it.
2. One judge call is noisy (15% flips). One call decides whether a fact is rewritten, so a fact's fate is partly
   chance (1/S3/F4 was rewritten and lost a detail because of a verdict that flips).
3. Faithfulness is the property that matters most for answering questions (a dropped hedge becomes a wrong answer),
   and it is the one the judge never catches.
4. The `pointing` check fails facts whose "this" is resolved in the same sentence; 3 of 3 alarms were false.
5. Gold is one labeller and not blind; 7 of 62 labels are borderline.

## 7. Proposed changes

Prompt wording (`fact_judge.txt`), for F to write and the reviewer to check:
1. Faithful: before deciding, compare every qualifier in the evidence sentences (may, most, usually, sometimes, in a
   broad sense, some, for some people) with the fact, and fail the fact if one is missing or changed; check what
   "this field" and similar phrases refer to in the segment.
2. Whole: a fact that restates a recap of something taught earlier fails unless it adds something new; two facts
   that together make one point fail (name the other).
3. Terms in full: an acronym written without its full term in the same fact fails, even when the segment uses it.
4. The reason must name the evidence sentence it checked for Faithful and Grounded, so a generic "passes all eight"
   is not an answer.

Not prompt wording (proposals for "Decisions for you"):
- D1: make `pointing` report only (3 of 3 false alarms), or fail only a leading pronoun and "the lecturer".
- Judge noise: a majority over three judge calls per segment (a design change: 2b makes one call), or a lower judge
  temperature (a config change; Sage's recommended sampling is temperature 1.0, untested lower).
- The gate: add a target on gold failures caught (e.g. ≥ 60%), since the seeded target measures only blatant errors.

## 8. Decisions needed

- D1 (above), D2 (section 5), judge noise, the gold-recall target.
