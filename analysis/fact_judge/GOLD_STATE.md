# Gold state: block 1, gate review 1, CHANGES 8 and 9

Written by Fable on 2026-11-15. Branch `fable-block1-gold-changes-8-9`, worktree
`.claude/worktrees/fable-block1-gold`. Commits to cherry-pick: `4902d66` (`gold.json`), `0a6c5c4`
(`gold_rewrites.json`, `seeded_subtle.json`), and the commit that adds this file. Nothing is pushed by Fable.

## Done

- **CHANGE 8, `gold.json`.** 1/S0/F1 fails [1, 2, 3, 6] (3 added). 16/S0/F3 and 4/S1/F0 decided again. Counts now:
  62 facts, 53 pass, 9 fail, 7 borderline, 5 failures that are not borderline. `about.revisions` records the change.
- **CHANGE 8, `gold_rewrites.json`.** The 8 rewrites of the fresh 2b run of 2026-11-12 labelled per property:
  5 pass, 3 fail, 1 borderline. Keys are that run's final IDs; each entry has `rewrite_of`, `evidence`, `text`.
- **CHANGE 9, `seeded_subtle.json`.** 13 entries, E35 to E47, 15 seeded facts: 3 hedges, 2 scope, 2 wrong thing named,
  2 thin splits, 2 restated recaps, 2 acronyms alone.
- All three files parse and load through `compare.py`'s own loaders (`gold()`, `seeded_segment()`, `fact_checks.flags`).
  No subtle entry trips a code check that causes a rewrite.

## Decisions made

- **16/S0/F3: fail [8], borderline.** The lecturer says tracking in AR "is more about tracking objects and how they are
  moving in the field of view" and gives registration as what AR requires; the fact puts "primarily about" on the
  registering.
- **4/S1/F0: fail [2], borderline.** The list of the three characteristics plus a second point, their use to categorise
  systems ("Another thing to note", 4/36 to 4/39; 4/S2/F0 holds it). The list alone would pass.
- **Rewrites.** Fail: 1/S0/F1 [1, 2, 3], 1/S3/F5 [2], 1/S3/F6 [2]. Pass: 1/S3/F4, 4/S1/F0 (borderline), 4/S1/F3,
  16/S1/F9, 16/S1/F11. The kept fact 1/S3/F7 is now the same point as the rewrite 1/S3/F6 (`neighbours`).
- **Seeded IDs** go on from E34 so both files can run together. The two wrong-thing entries have `breaks` [4, 8]; the
  others one property. Each entry has an extra `changed` field, which `compare.py` ignores.

## Half-done

Nothing is half-written. Open by design:

- The labels are not fully blind: no verdict under `runs/`, `data/` or the history run's judgements was read, but the
  review states the old judge's counts on 4/S1/F0, which two rewrites failed the rejudge, and its own reading of three
  rewrites. This is in the caveats of both gold files.
- Property 1 on 1/S0/F1 (the 2a fact and its rewrite) is arguable under the revised wording of property 1. It is kept
  on both for consistency; the right outcome for the fact is a rewrite that keeps the headset point, not removal.

## Next steps

1. **O** `compare.py`: read `seeded_subtle.json` as well as `seeded.json` and report the two separately; replace the
   hardcoded "62 facts, 55 pass, 7 fail, 7 borderline" and "34 entries" in the report header (near line 489); score
   rewrites against `gold_rewrites.json` by text, not by ID.
2. **O** `pipeline/PLAN.md`, block 1: "(55 pass, 7 fail)" is now 53 pass, 9 fail.
3. **O** (EC2) CHANGE 12: rerun base, seed1, seed2 on gold and both seeded files with the revised prompt; fresh 2b;
   the rejudge.
4. **F** Second half of CHANGE 8: label the rewrites of the new fresh 2b run before reading their rejudge verdicts
   (take only `final` texts and evidence of rewritten facts; add them to `gold_rewrites.json` under their own run).
5. **F** CHANGE 10 (at least 25 real failures that are not borderline, labelled blind): waits for the user's word on
   the source.
6. **U** Say whether property 1 should be dropped from 1/S0/F1 and its rewrite.
