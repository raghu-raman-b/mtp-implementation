# Rule precision, written by reading samples of each rule's matches against the raw files (executed by inventory.py).
# "read n" = n matches (or all, when fewer) were read in the raw JSON; "defect" = a real problem of the kind the row names.
JUDGE = ("Counts are the pipeline's own judge verdicts, so precision is the judge's, which is itself unmeasured (the judge seed set, "
         "analysis/activities/review_prompts.md section 8, was not run). Mapping verified by code: every failed item resolves to the item "
         "the verdict is about (0 mismatches over quiz, recap, put-in-order, odd-one-out and open-question items; crossword by concept name), "
         "and the per-kind sums equal totals.judge.still_failed_items (865).")
PRECISION.update({
    "act.quiz.judge_failed": JUDGE + " Read 2 verdicts: 1/A0 Q1 (correct option is the only hedged one) is a fair no_giveaway.",
    "act.recap.points_failed": JUDGE + " Read 2: 1/A3 point 2 and 1/A1 text ('different immersive experiences' goes beyond the facts) are fair. "
                               "Recaps fail most often (faithful 507, supported 299 on first judgement): the criteria are strict.",
    "act.recap.text_failed": JUDGE + " 222 of 347 is high; the summary text adds connecting words the facts do not state.",
    "act.recap.no_passing_point": "Exact given the verdicts (same source as the recap rows). Matches the 6 stated in PROMPT.md.",
    "act.crossword.clue_failed": JUDGE + " Read 3: 1/A14 MIXEDREALITY ('identical to augmented', a dangling fragment) and 6/A16 OCULUSRIFT are fair.",
    "act.odd_one_out.judge_failed": JUDGE + " Read 2: 2/A10 #1 (Virtual Boot Camp is itself a defense use) and #2 are fair near_miss failures.",
    "act.put_in_order.judge_failed": JUDGE + " Read 2: 1/A6 (the two middle steps are not an order the facts fix) is fair. 25 of 42 is a high failure rate.",
    "act.open_question.judge_failed": JUDGE,
    "act.whole_hidden": "Exact given the rule parsed from serve.py. The recap number follows the 2026-11-18 decision, which serve.py HIDE_JUDGE_FAILED "
                        "(recap: no_source_talk only) does not implement yet (task S1).",
    "act.units_empty_skipped": "Exact (status field).",
    "act.retried": "Exact (a retry record exists). Retries repaired the code-check problems listed; none stayed unresolved.",
    "act.judge_unresolved": "Exact (pipeline totals).",
    "act.quiz.correct_longest": "Exact (character counts of the stored options). Read 3: 13/A1 Q2 (11 vs 9 chars) is a small margin; no question is 1.5x longer.",
    "act.crossword.clue_has_answer": "Whole-word rule. 0 matches. A first version using letter substrings matched 42/A19 CYCLE ('lifecycle'), a false positive, so "
                                     "it was changed. Misses leaks by a different word form (e.g. 'tracker' for TRACKING).",
    "act.crossword.clue_has_part": "Read the 1 match: 17/A13 ACCELEROMETER / 'acceleration' is a real leak. A first version also matched 44/A17 'with' (an alias "
                                   "'evaluation with self-reports'); function words are excluded now. Under-counts other word forms.",
    "act.crossword.clue_masked": "Exact.",
    "act.crossword.clue_duplicate": "Exact (identical text); near-identical clues for sibling answers (the MVP's three ear parts) are not caught.",
    "act.match.truncated": "Exact (text ends with the ellipsis). Read 5 (57/A15): each is the 4a definition cut mid-clause.",
    "act.match.term_in_definition": "Whole-phrase rule, 1 match, read: fair. A looser any-word version gave 231 and, in a read of 5, flagged only legitimate overlap "
                                    "(view plane / plane), so it was not used. Does not see the masking artefacts that need meaning (an article left after a removed term).",
    "act.match.twin_rows": "Exact; 0 at Jaccard >= 0.7 (the MVP's near-identical right sides no longer occur).",
    "act.match.bad_start": "Exact; 0.",
    "act.map.too_big": "Exact count of nodes. 60 is the line from analysis/mvp/test_report.md, not a pipeline value.",
    "act.map.long_edge_label": "Heuristic (>= 9 words). Read 5: all are fragments cut at a dangling preposition ('...projected onto the'); other long labels may be complete, so over-counts.",
    "act.completemap.blank_twice": "Exact; 0 (the MVP's 5/A10 case no longer occurs).",
    "act.code_flags": "The pipeline's own report-only flags; odd_one_out.not_a_concept counts items, the others units/items as stored.",
    "con.shared_key": "Exact collision count. Read 19 (every 5th key): about 16 are defects (true duplicates such as 2d, ios, vr headset, empirical research, or over-broad aliases "
                      "such as library, source, screen, feedback); 3 are harmless ambiguity (os, sy, alpha).",
    "con.name_is_other_alias": "Exact collision count. Read 15: all are alias collisions; only about 3 are true duplicates to merge (noise cancelling microphone, operating system, exploration), "
                               "the rest are hypernym aliases (model, system, controller) that should be removed.",
    "con.acronym_expansion": "Strong rule (the registry lists the acronym on the expanded concept). Read all 17: about 14 are real defects (duplicates: operating system / operating system layer, "
                             "data flow / data flow diagram, two-dimensional form / two-dimensional, iOS / ios, 3D transformation pair, HMD / VR headset; or a wrong alias: VR on 'virtual reality headset', "
                             "AI on 'generative AI'); about 3 are false (ASQ is two different questionnaires, the Majuli VR Tour pairs are different concepts). Under-counts: needs the acronym listed on the expansion.",
    "con.generic_modifier": "Read all 22: about 11 are plausible duplicates (every 'user X' / 'X': interaction, tracking, locomotion, motion, input, movement, behavior, feedback); "
                            "about 11 are different concepts (user interface / interface, main camera / camera, main thread / thread, simple polygon / polygon, primary color / color). Candidate list for a reviewer only.",
    "con.embedding_similar": "Weak. Read 40 pairs (every 34th at >= 0.90 and every 14th at >= 0.95): about 6 are plausible duplicates (physics event / physics-related event, thread / main thread, "
                             "force feedback / force feedback mouse, virtual reality modeling language / modeling language, spotlight effect / region); the rest are siblings (x axis / y axis, "
                             "box collider / capsule collider, entry- / exit-controlled loop). Vectors embed names plus facts, so siblings that share a passage score high. Use as candidates for review, not as a verdict.",
    "con.alias_short": "Read all of them: units (Hz, dB) and symbols (V, E, G, dx, dt) are legitimate; single letters shared across concepts (f, t, P, x) are defects. About half are defects.",
    "con.alias_generic": "Read all 10: about 7 are defects (system, user, factor, factors, values, model, objects for a more specific concept); tools / techniques / components plural forms are borderline.",
    "con.alias_fragment": "Read 20 (every 5th): about 12 are defects (environment, electromagnetic, library, source, social, constant, asset, mismatch); code identifiers (Destroy, isKinematic) and "
                          "clear short forms (gaze, plugin) are legitimate. Precision about 60%.",
    "con.alias_shared_by_many": "Exact collision count; read all 6: f, p, sx, sy-like single symbols and 'hardware', 'vr tour' are all alias defects.",
    "con.acronym_of_other_concept": "Read all 4: FOV on horizontal field of view, VR on virtual reality headset, AI on generative AI, OS on Android operating system; "
                                    "the first three are clear defects, OS is a plausible but loose alias. Under-counts: needs the shorter concept to exist and sit inside the name.",
    "con.connecting": "Exact (defined == false). Not a defect by itself: these are concepts no segment defines.",
    "con.2c.reverse": "The pipeline's own flag (relation direction opposite to its sentence). Read 5: the 'virtual reality --has as major current application domains--> healthcare' "
                      "family looks like a direction the code check disagrees with, but the relation reads sensibly: over-flags.",
    "con.2c.name_not_in_facts": "The pipeline's own flag. Read 5: e.g. 'virtual reality device', 'web-based virtual tour' are paraphrases of the facts, so many are harmless.",
    "con.2c.no_triple": "The pipeline's own flag. Read 4: extended reality, augmented reality, mixed reality as concepts in no relation of 1/S0: real isolated nodes in that segment.",
    "con.2c.no_shared_fact": "The pipeline's own flag; read 3: the semi-immersive relations are real (the concepts are in different facts of the segment).",
    "con.2c.acronym_in_name": "The pipeline's own flag; read 5: VR box, VR headset, CAVE system are real (the acronym sits inside the name).",
    "con.2c.alias_not_in_facts": "The pipeline's own flag; read all 3: real (joysticks, large space, virtual tour absent from the facts).",
    "con.2c.fact_without_concept": "The pipeline's own flag; 1 fact (31/S4/F3).",
    "con.4a.defined_mismatch": "Exact (the pipeline's flag). 272 of the 276 are defined:true with no defined_in; read 5: the definitions are real 4a text, but no segment is recorded as defining them.",
    "con.4a.misplaced": "The pipeline's own flag.",
    "con.4a.capped": "The pipeline's own count.",
    "con.4a.definition_no_verb": "Cheap lower bound. 0 matches; two false positives of an earlier regex (names containing a dot, three.js and debug.log) were fixed. "
                                 "Does not test that the definition is correct.",
    "fact.0a.null_start": "Exact.",
    "fact.2a.long": "The pipeline's own flag.", "fact.2a.bare_acronym": "The pipeline's own flag.", "fact.2a.pointing": "The pipeline's own flag.",
    "fact.2a.acronym": "The pipeline's own flag.",
    "fact.2a.sentences_uncited": "Exact. Read 5: greetings and asides ('You might be wondering, why so much interest?') are legitimately uncited; the row is a coverage figure, not a defect count.",
    "fact.2b.not_judged": "Exact.",
    "fact.no_segment": "Exact; 0.", "fact.null_time": "Exact; 0.",
    "fact.shared_start": "Exact (>= 3 facts in a segment at one start time). Matches the 462 of analysis/mvp/test_report.md.",
    "seg.no_facts": "Exact. Read 5: intros and closing summaries ('Summarize the main points...') have no facts by design.",
    "seg.4b.in_no_objective": "The pipeline's own flag.",
    "seg.1b.flagged_left": "The pipeline's own flag.",
    "seg.4c.assumed": "The pipeline's own list.",
    "seg.4d.broken_refs": "Exact; 0 of 206,903 (also rechecked independently in analysis/mvp/test_report.md).",
    "qa.markdown_raw": "Exact on the recorded 2026-11-13 run (56 answers = 36 + 20 reruns). The regex counts ** bold, bullets and $...$; not rerun.",
    "qa.slow": "Exact on the recorded run.", "qa.bench_slow": "Exact on the recorded bench.",
    "qa.not_covered_padded": "Quoted from a human read of the answers; not recomputed.", "qa.prereq_odd": "Quoted; not recomputed.",
    "qa.two_times": "Quoted; not recomputed.",
    "seg.part_titles": "Pending.",
})
