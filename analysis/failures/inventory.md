# Failure inventory: nptel_vr (code-only)

Written by `analysis/failures/inventory.py` from `pipeline/output/nptel_vr/` (read only) and the QA records in `analysis/`. Every count comes from a deterministic rule, a pipeline check file or judge verdict, or a stored similarity: no language model and no agent decided what a failure is. Handling is one of: **fixed in the pipeline**; **fixed in the viewer**; **display rule**; **hidden from learners**; **not fixed (future work)**.

## Table

| Row | Stage | What fails | Count | Handling |
|---|---|---|---|---|
| `act.quiz.judge_failed` | 5 activities | quiz questions the activities judge fails (first judgement, then one rewrite, the better version kept) | 102 of 1,163 (8.8%) questions | hidden from learners |
| `act.recap.points_failed` | 5 activities | recap points the judge fails (supported/faithful/stands_alone/...) | 371 of 1,360 (27.3%) points | display rule |
| `act.recap.text_failed` | 5 activities | recap summary texts the judge fails | 222 of 347 (64.0%) recap texts | display rule |
| `act.recap.no_passing_point` | 5 activities | whole recaps with no judge-passing point (nothing left to show) | 6 of 347 (1.7%) recaps | display rule |
| `act.crossword.clue_failed` | 5 activities | crossword clues the judge fails (readable, from_text, unique, ...) | 82 of 645 (12.7%) clues | display rule |
| `act.odd_one_out.judge_failed` | 5 activities | odd-one-out puzzles the judge fails | 39 of 133 (29.3%) items | hidden from learners |
| `act.put_in_order.judge_failed` | 5 activities | put-in-order items the judge fails | 25 of 42 (59.5%) items | hidden from learners |
| `act.open_question.judge_failed` | 5 activities | open questions the judge fails | 24 of 219 (11.0%) items | hidden from learners |
| `act.whole_hidden` | 5 activities | whole activities with every item hidden from learners (judge-failed under the per-kind rule; recaps with no passing point) | 40 of 855 (4.7%) activities | hidden from learners |
| `act.units_empty_skipped` | 5 activities | units that made no activity (status empty or skipped) | 33 of 1,198 (2.8%) units | not fixed (future work) |
| `act.retried` | 5 activities | units whose first model output broke a code check and was regenerated (the client's retry loop) | 197 of 1,198 (16.4%) units | fixed in the pipeline |
| `act.judge_unresolved` | 5 activities | items still judge-failed after the judge's one rewrite round | 865 of 3,911 (22.1%) items | fixed in the pipeline |
| `act.quiz.correct_longest` | 5 activities | quiz questions whose correct option is the longest of the four (test-wise bias) | 160 of 1,163 (13.8%) questions | fixed in the pipeline |
| `act.crossword.clue_has_answer` | 5 activities | crossword entries whose clue contains the whole answer | 0 of 645 (0.0%) entries | fixed in the pipeline |
| `act.crossword.clue_has_part` | 5 activities | crossword entries whose clue contains a word of the answer's concept name/aliases (a part of the answer) | 1 of 645 (0.2%) entries | not fixed (future work) |
| `act.crossword.clue_masked` | 5 activities | clues containing a `___` mask (word of the answer blanked by code) | 0 of 645 (0.0%) entries | fixed in the pipeline |
| `act.crossword.clue_duplicate` | 5 activities | two answers of one grid with the same clue text | 0 of 645 (0.0%) entries | not fixed (future work) |
| `act.match.truncated` | 5 activities | match-pair definitions cut off with '…' (read as unfinished) | 383 of 502 (76.3%) pairs | not fixed (future work) |
| `act.match.term_in_definition` | 5 activities | match pairs where the definition (right) contains the whole term (left): the answer is given away | 1 of 502 (0.2%) pairs | not fixed (future work) |
| `act.match.twin_rows` | 5 activities | pairs of definitions in one match set that are near-identical (token Jaccard >= 0.7) | 0 of 502 (0.0%) pair-pairs | not fixed (future work) |
| `act.match.bad_start` | 5 activities | match-pair definitions that start lower-case or with '…' | 0 of 502 (0.0%) pairs | not fixed (future work) |
| `act.map.too_big` | 5 activities | concept maps with more than 60 nodes (unreadable at 'Fit') | 40 of 63 (63.5%) maps | display rule |
| `act.map.long_edge_label` | 5 activities | map edges whose label has 9 or more words (a sentence fragment) | 1,065 of 7,450 (14.3%) edges | not fixed (future work) |
| `act.completemap.blank_twice` | 5 activities | complete-the-map activities that blank the same edge twice | 0 of 63 (0.0%) activities | not fixed (future work) |
| `act.code_flags` | 5 activities | report-only code flags on the kept items (not judge verdicts) | 186 of 1,168 (15.9%) flags | not fixed (future work) |
| `con.shared_key` | 3 registry / 2c | a name, alias or acronym text that identifies two or more concepts | 93 of 4,738 (2.0%) name keys | not fixed (future work) |
| `con.name_is_other_alias` | 3 registry / 2c | a concept's name equals another concept's alias or acronym | 45 of 3,122 (1.4%) name keys | not fixed (future work) |
| `con.acronym_expansion` | 3 registry | two concepts that are the same term with an acronym expanded in one (HMD / head-mounted display, VR headset / virtual reality headset, iOS / iPhone operating system, 3D / three-dimensional) | 17 of 3,122 (0.5%) concept pairs | not fixed (future work) |
| `con.generic_modifier` | 3 registry | a concept whose name is another concept's name plus a generic modifier (interaction / user interaction) | 22 of 3,122 (0.7%) concept pairs | not fixed (future work) |
| `con.embedding_similar` | 3 registry | two distinct concepts whose stored entry vectors have cosine >= 0.9 and whose names share a word (likely duplicates or near-synonyms) | 676 of 16,556 (4.1%) concept pairs (cross-concept pairs with cosine >= 0.70) | not fixed (future work) |
| `con.alias_short` | 2c / 3 registry | aliases of 1-2 characters that are not the concept's acronym or its initials | 44 of 1,741 (2.5%) aliases | not fixed (future work) |
| `con.alias_generic` | 2c / 3 registry | aliases that are a single generic word from a small stoplist | 10 of 1,741 (0.6%) aliases | not fixed (future work) |
| `con.alias_fragment` | 2c / 3 registry | single-word aliases that are only one word of a longer name (fragment aliases) | 98 of 1,741 (5.6%) aliases | not fixed (future work) |
| `con.alias_shared_by_many` | 3 registry | a name key shared by 3 or more concepts | 6 of 4,738 (0.1%) name keys | not fixed (future work) |
| `con.acronym_of_other_concept` | 2c / 3 registry | an acronym on a concept that is not the initials of its name but is the initials of another concept (FOV on horizontal field of view) | 4 of 158 (2.5%) acronyms | not fixed (future work) |
| `con.connecting` | 4a definitions | connecting concepts (defined: false): no segment defines them, so their 'definition' is a model-written gloss | 1,806 of 3,122 (57.8%) concepts | display rule |
| `con.2c.no_triple` | 2c concepts | concept in no relation of its segment | 184 of 5,805 (3.2%) flags | not fixed (future work) |
| `con.2c.name_not_in_facts` | 2c concepts | concept name that does not occur in its facts' text | 322 of 5,805 (5.5%) flags | not fixed (future work) |
| `con.2c.reverse` | 2c concepts | relation written in the opposite direction to its sentence (code check) | 437 of 7,502 (5.8%) flags | not fixed (future work) |
| `con.2c.acronym_in_name` | 2c concepts | acronym written inside the concept name (VR headset) | 38 of 5,805 (0.7%) flags | not fixed (future work) |
| `con.2c.no_shared_fact` | 2c concepts | relation whose two concepts share no fact | 113 of 7,502 (1.5%) flags | not fixed (future work) |
| `con.2c.alias_not_in_facts` | 2c concepts | alias that does not occur in the facts | 3 of 5,805 (0.1%) flags | not fixed (future work) |
| `con.2c.fact_without_concept` | 2c concepts | fact with no concept | 1 of 2,006 (0.0%) flags | not fixed (future work) |
| `con.4a.defined_mismatch` | 4a definitions | concepts 4a marks defined, with no segment that defines them (defined_in empty) | 276 of 1,316 (21.0%) concepts | not fixed (future work) |
| `con.4a.misplaced` | 4a definitions | definition facts that 4a flags as misplaced (cited under another concept's segment) | 29 of 3,122 (0.9%) concepts | not fixed (future work) |
| `con.4a.capped` | 4a definitions | concepts with more facts than the 4a cap (40), so the definition saw a subset | 15 of 3,122 (0.5%) concepts | not fixed (future work) |
| `con.4a.definition_no_verb` | 4a definitions | defined concepts whose definition does not read like a definition (no 'is / are / refers to / means / denotes / stands for / describes' within the first 90 characters of the first 20 words) | 0 of 1,316 (0.0%) defined concepts | fixed in the pipeline |
| `fact.0a.null_start` | 0a preprocess | transcript sentences with no start time (the sentence begins inside a subtitle cue) | 201 of 11,893 (1.7%) sentences | fixed in the pipeline |
| `fact.2a.long` | 2a facts | facts over about 50 words (several points in one fact?) | 117 of 2,006 (5.8%) facts | not fixed (future work) |
| `fact.2a.bare_acronym` | 2a facts | facts using an acronym without its full term | 84 of 2,006 (4.2%) facts | not fixed (future work) |
| `fact.2a.pointing` | 2a facts | facts with an unresolved pointing word (this, that) | 52 of 2,006 (2.6%) facts | not fixed (future work) |
| `fact.2a.acronym` | 2a facts | facts with an acronym flag | 1 of 2,006 (0.0%) facts | not fixed (future work) |
| `fact.2a.sentences_uncited` | 2a facts | transcript sentences that no fact cites as evidence | 4,460 of 11,893 (37.5%) sentences | not fixed (future work) |
| `fact.2b.not_judged` | 2b verify facts | facts never checked by the fact judge (2b skipped: every fact kept unjudged) | 2,006 of 2,006 (100.0%) facts | not fixed (future work) |
| `fact.no_segment` | 4d assemble | facts whose segment is missing from the lecture layer | 0 of 2,006 (0.0%) facts | fixed in the pipeline |
| `fact.null_time` | 4d assemble | facts with a null start or end time | 0 of 2,006 (0.0%) facts | fixed in the pipeline |
| `fact.shared_start` | 4d assemble | facts that share their start time with 2 or more other facts of the same segment (coarse time links) | 462 of 2,006 (23.0%) facts | not fixed (future work) |
| `seg.no_facts` | 2a / 4d | segments with no fact (nothing to ask, recap or link) | 39 of 386 (10.1%) segments | not fixed (future work) |
| `seg.4b.in_no_objective` | 4b goals | segments that serve no lecture objective | 60 of 386 (15.5%) segments | not fixed (future work) |
| `seg.1b.flagged_left` | 1b verify segments | lectures where a flagged segment problem was left after the retries | 1 of 63 (1.6%) lectures | not fixed (future work) |
| `seg.4c.assumed` | 4c lecture graph | concepts a lecture uses but no earlier lecture defines (assumed knowledge) | 2,074 of 3,122 (66.4%) concepts | display rule |
| `seg.4d.broken_refs` | 4d assemble | broken references, duplicate IDs or schema errors in the knowledge layer | 0 of 206,903 (0.0%) references | fixed in the pipeline |
| `qa.markdown_raw` | QA / viewer | answers containing markdown (** bold, bullets) or LaTeX that the page showed as raw characters | 32 of 56 (57.1%) answers | fixed in the viewer |
| `qa.slow` | QA | answers slower than 15 s | 3 of 56 (5.4%) answers | fixed in the pipeline |
| `qa.bench_slow` | QA | bench answers slower than 8 s after the latency fixes | 4 of 34 (11.8%) answers | not fixed (future work) |
| `qa.not_covered_padded` | QA | not-covered answers that decline but then pad with loosely related facts, and are the slowest type | 2 of 36 (5.6%) questions | fixed in the pipeline |
| `qa.prereq_odd` | QA / 4c | prerequisite answers listing odd concepts (location awareness, markers before lecture 40; augmented virtuality before 16) | 2 of 36 (5.6%) questions | fixed in the pipeline |
| `qa.two_times` | QA | 'where is X taught' answers showing two different times (text 14:25, citation 11:44) | 2 of 36 (5.6%) questions | fixed in the pipeline |
| `seg.part_titles` | 4e part titles | part titles failing the code check (ok: false) | 0 of 2 (0.0%) segments | not fixed (future work) |

Self-check: failed judge items found here 865, the pipeline's own total (checks.json totals.judge.still_failed_items) 865: equal.

## Rows

### `act.quiz.judge_failed` (5 activities)

- **Fails:** quiz questions the activities judge fails (first judgement, then one rewrite, the better version kept)
- **Detected by:** checks.json units[quiz].judge.failed_items of the kept round (code reads the pipeline's own verdicts); criteria from the verdicts' `failed` lists
- **Count:** 102 of 1,163 (8.8%) questions
- **Examples:**
  - `12/A9 item 4 [answerable,no_giveaway]`: What do controlled breathing, pleasant background music, and adequate airflow have in common as sickness-reduction strategies? | …
  - `13/A9 item 4 [no_giveaway,no_source_talk]`: How can a bare-hand input device translate a user's hand gestures into virtual commands? | correct: Infrared LEDs can illuminate …
  - `35/A9 item 4 [answerable,no_giveaway]`: Why are observations and interaction with users valuable in contextual inquiry? | correct: They expose the task domain, work cult…
  - `58/A10 item 3 [one_answer,no_source_talk]`: How can a computer-graphics programmer avoid always implementing pipeline stages from scratch? | correct: by importing a graphics…
  - `60/A5 item 3 [one_answer,clear]`: Which camera determines what the Unity game view renders for the final published or deployed application? | correct: The develope…
- **Handling:** hidden from learners. viewer rule HIDE_JUDGE_FAILED[quiz] = ['answerable', 'clear', 'no_source_talk', 'one_answer']: 35 of the 102 failed questions are hidden; the other 67 (no_giveaway / worth_asking only) are shown. First judgement failed 285; judge-and-rewrite repaired 183. Criteria on the remaining: no_giveaway 68, no_source_talk 13, one_answer 11, answerable 10
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Counts are the pipeline's own judge verdicts, so precision is the judge's, which is itself unmeasured (the judge seed set, analysis/activities/review_prompts.md section 8, was not run). Mapping verified by code: every failed item resolves to the item the verdict is about (0 mismatches over quiz, recap, put-in-order, odd-one-out and open-question items; crossword by concept name), and the per-kind sums equal totals.judge.still_failed_items (865). Read 2 verdicts: 1/A0 Q1 (correct option is the only hedged one) is a fair no_giveaway.

### `act.recap.points_failed` (5 activities)

- **Fails:** recap points the judge fails (supported/faithful/stands_alone/...)
- **Detected by:** checks.json units[recap].judge.failed_items, item >= 1 (point number); criteria from the kept round
- **Count:** 371 of 1,360 (27.3%) points
- **Examples:**
  - `1/A3 point 2 [supported,faithful]`: The X in Extended Reality is a variable whose values denote augmented, virtual, and mixed reality.
  - `1/A8 point 3 [faithful]`: The thirty-year-old metaverse term is a broader natural 3D digital-interaction vision, not merely an XR application, and has stim…
  - `3/A2 point 4 [supported,faithful,one_idea]`: AR can reveal hidden archaeological details, reconstruct lost structures, and help with industrial repair or troubleshooting.
  - `3/A6 point 5 [supported,faithful]`: Projection-based and outlining-based markerless augmented reality applications use light projectors or object recognition to enha…
  - `3/A8 point 4 [supported,faithful]`: Markerless augmented reality overcomes marker maintenance mainly with computer vision, sometimes GPS, superimposition, outline, o…
- **Handling:** display rule. 2026-11-18 decision: recaps show only judge-passing points. Display-side only (no regeneration). Criteria: faithful 507, supported 299, stands_alone 44, one_idea 28, clear 19
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Counts are the pipeline's own judge verdicts, so precision is the judge's, which is itself unmeasured (the judge seed set, analysis/activities/review_prompts.md section 8, was not run). Mapping verified by code: every failed item resolves to the item the verdict is about (0 mismatches over quiz, recap, put-in-order, odd-one-out and open-question items; crossword by concept name), and the per-kind sums equal totals.judge.still_failed_items (865). Read 2: 1/A3 point 2 and 1/A1 text ('different immersive experiences' goes beyond the facts) are fair. Recaps fail most often (faithful 507, supported 299 on first judgement): the criteria are strict.

### `act.recap.text_failed` (5 activities)

- **Fails:** recap summary texts the judge fails
- **Detected by:** checks.json units[recap].judge.failed_items contains item 0 (the text)
- **Count:** 222 of 347 (64.0%) recap texts
- **Examples:**
  - `1/A1 text [supported,faithful]`: The names XR, VR, AR, and MR are defined by their full forms. These terms can be ambiguous because different people associate the…
  - `1/A3 text [supported,faithful]`: Extended Reality groups present and future immersive technologies under one umbrella name rather than naming a single technology.…
  - `1/A8 text [supported,faithful]`: Extended reality is becoming an important emerging field. Broad application use, expected market growth, and the metaverse vision…
  - `3/A2 text [supported,faithful]`: XR has broad application potential across many fields, but AR is the form that adds digital content to the real world rather than…
  - `3/A6 text [faithful,summary]`: Augmented reality applications divide into marker-based and markerless systems according to their technology. Marker-based system…
- **Handling:** display rule. 2026-11-18 decision: the summary text is hidden when it failed (shown only if it passed).
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Counts are the pipeline's own judge verdicts, so precision is the judge's, which is itself unmeasured (the judge seed set, analysis/activities/review_prompts.md section 8, was not run). Mapping verified by code: every failed item resolves to the item the verdict is about (0 mismatches over quiz, recap, put-in-order, odd-one-out and open-question items; crossword by concept name), and the per-kind sums equal totals.judge.still_failed_items (865). 222 of 347 is high; the summary text adds connecting words the facts do not state.

### `act.recap.no_passing_point` (5 activities)

- **Fails:** whole recaps with no judge-passing point (nothing left to show)
- **Detected by:** every point number 1..n is in the unit's judge failed_items
- **Count:** 6 of 347 (1.7%) recaps
- **Examples:**
  - `15/A9`: Spatial AR devices are projector-based, room-scale systems that place virtual content on physical objects, no…
  - `19/A2`: VR software does not merely drive VR or AR hardware; it creates sensory stimuli for a VR experience.
  - `23/A10`: Human factors in XR system design require knowing users' characteristics, because users in the same task need…
  - `48/A7`: Use the Human-Computer Interaction book and NPTEL weeks 4, 5, 10-12 for prototype building, evaluation, empir…
  - `6/A2`: Virtual reality's evolution has four mostly distinct, sometimes overlapping phases: before digital computers,…
- **Handling:** display rule. 2026-11-18 decision: such recaps are dropped; that break shows only the quiz.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Exact given the verdicts (same source as the recap rows). Matches the 6 stated in PROMPT.md.

### `act.crossword.clue_failed` (5 activities)

- **Fails:** crossword clues the judge fails (readable, from_text, unique, ...)
- **Detected by:** checks.json units[crossword].judge.failed_items (entry number = position in the grid's entry list)
- **Count:** 82 of 645 (12.7%) clues
- **Examples:**
  - `5/A12 item 4 [from_text,unique,readable]`: MIXEDREALITY: Immersive technology like augmented, overlaying digital content on the actual view (5,7)
  - `1/A14 item 3 [readable,from_text]`: MIXEDREALITY: Immersive tech identical to augmented, with interactive digital content overlaying physical view (5,7)
  - `6/A16 item 9 [from_text,unique]`: OCULUSRIFT: Low-cost virtual-reality headset using a development kit (6,4)
  - `13/A19 item 4 [from_text,unique]`: PINCHGLOVE: hand input with sensors only on fingertips detecting limited thumb-index gestures (5,5)
  - `45/A20 item 2 [from_text,unique]`: EXPERIMENT: Planned, executed comparison of measured outcomes to answer a research question (10)
- **Handling:** display rule. 2026-11-18 decision: the grid is kept, the failed words are shown pre-filled and their clues are never shown. Criteria: from_text 58, unique 23, readable 9, no_giveaway 4, leads_to_answer 2
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Counts are the pipeline's own judge verdicts, so precision is the judge's, which is itself unmeasured (the judge seed set, analysis/activities/review_prompts.md section 8, was not run). Mapping verified by code: every failed item resolves to the item the verdict is about (0 mismatches over quiz, recap, put-in-order, odd-one-out and open-question items; crossword by concept name), and the per-kind sums equal totals.judge.still_failed_items (865). Read 3: 1/A14 MIXEDREALITY ('identical to augmented', a dangling fragment) and 6/A16 OCULUSRIFT are fair.

### `act.odd_one_out.judge_failed` (5 activities)

- **Fails:** odd-one-out puzzles the judge fails
- **Detected by:** checks.json units[odd_one_out].judge.failed_items of the kept round
- **Count:** 39 of 133 (29.3%) items
- **Examples:**
  - `39/A26 item 3 [in_facts,real_group,one_answer,clear]`: Spindle technique | Virtual hand technique | Synchronous | Asynchronous (odd: Spindle technique)
  - `2/A10 item 1 [near_miss,no_giveaway]`: Healthcare | Defense | Education | Virtual Boot Camp (odd: Virtual Boot Camp)
  - `2/A10 item 2 [near_miss,no_giveaway]`: Semi-Immersive VR | Immersive Simulation | Non-Immersive VR | Fully Immersive VR (odd: Immersive Simulation)
  - `15/A16 item 2 [near_miss,no_giveaway]`: Sony Xperia Touch | Nintendo Device | Tablet | Smartphone (odd: Sony Xperia Touch)
  - `17/A14 item 2 [in_facts,near_miss]`: Tag | Computer Vision | Fiducial Marker | Reflector (odd: Computer Vision)
- **Handling:** hidden from learners. viewer rule HIDE_JUDGE_FAILED[odd_one_out] = True: 39 of 39 hidden. First judgement failed 39. Criteria: no_giveaway 17, one_answer 13, near_miss 9, in_facts 9, real_group 2
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Counts are the pipeline's own judge verdicts, so precision is the judge's, which is itself unmeasured (the judge seed set, analysis/activities/review_prompts.md section 8, was not run). Mapping verified by code: every failed item resolves to the item the verdict is about (0 mismatches over quiz, recap, put-in-order, odd-one-out and open-question items; crossword by concept name), and the per-kind sums equal totals.judge.still_failed_items (865). Read 2: 2/A10 #1 (Virtual Boot Camp is itself a defense use) and #2 are fair near_miss failures.

### `act.put_in_order.judge_failed` (5 activities)

- **Fails:** put-in-order items the judge fails
- **Detected by:** checks.json units[put_in_order].judge.failed_items of the kept round
- **Count:** 25 of 42 (59.5%) items
- **Examples:**
  - `48/A5 item 1 [in_facts,real_sequence,one_order,no_giveaway,worth_doing]`: Order the stages of the agile development process
  - `28/A3 item 1 [in_facts,real_sequence,one_order]`: Order the media a light ray passes through before it reaches the retina
  - `1/A6 item 1 [in_facts,one_order]`: Order the positions on the reality-virtuality continuum from the completely real end to the completely virtual end
  - `2/A5 item 1 [real_sequence,worth_doing]`: Order the VR system categories from the least sensory blocking to the greatest sensory blocking
  - `31/A3 item 1 [one_order,worth_doing]`: Order the stages of somatosensory touch processing and motor response
- **Handling:** hidden from learners. viewer rule HIDE_JUDGE_FAILED[put_in_order] = True: 25 of 25 hidden. First judgement failed 25. Criteria: in_facts 11, worth_doing 11, one_order 6, real_sequence 5, no_giveaway 5
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Counts are the pipeline's own judge verdicts, so precision is the judge's, which is itself unmeasured (the judge seed set, analysis/activities/review_prompts.md section 8, was not run). Mapping verified by code: every failed item resolves to the item the verdict is about (0 mismatches over quiz, recap, put-in-order, odd-one-out and open-question items; crossword by concept name), and the per-kind sums equal totals.judge.still_failed_items (865). Read 2: 1/A6 (the two middle steps are not an order the facts fix) is fair. 25 of 42 is a high failure rate.

### `act.open_question.judge_failed` (5 activities)

- **Fails:** open questions the judge fails
- **Detected by:** checks.json units[open_question].judge.failed_items of the kept round
- **Count:** 24 of 219 (11.0%) items
- **Examples:**
  - `21/A13 item 4 [answerable,answers_question,open]`: How does the desktop-versus-mobile categorization of augmented reality software tools correspond to the deployment meaning of a p…
  - `6/A19 item 4 [answerable,answers_question]`: How did the 2016 commercial virtual reality headset releases extend the effect that inexpensive headsets had already had near the…
  - `23/A16 item 2 [open,clear]`: Why can a traveler and a database administrator who both obtain railway ticket information need different interfaces in an intera…
  - `35/A18 item 2 [clear,answerable]`: Why are usability requirements classified as non-functional requirements instead of functional requirements in the specification …
  - `61/A19 item 2 [answers_question,clear]`: How do a rigid body and a collider work together to give a Unity game object realistic physical behavior?
- **Handling:** hidden from learners. viewer rule HIDE_JUDGE_FAILED[open_question] = True: 24 of 24 hidden. First judgement failed 62. Criteria: answerable 16, answers_question 8, clear 4, open 2
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Counts are the pipeline's own judge verdicts, so precision is the judge's, which is itself unmeasured (the judge seed set, analysis/activities/review_prompts.md section 8, was not run). Mapping verified by code: every failed item resolves to the item the verdict is about (0 mismatches over quiz, recap, put-in-order, odd-one-out and open-question items; crossword by concept name), and the per-kind sums equal totals.judge.still_failed_items (865).

### `act.whole_hidden` (5 activities)

- **Fails:** whole activities with every item hidden from learners (judge-failed under the per-kind rule; recaps with no passing point)
- **Detected by:** per activity: hidden items (HIDE_JUDGE_FAILED parsed by ast from pipeline/viewer/serve.py; recap rule of 2026-11-18) cover all its items
- **Count:** 40 of 855 (4.7%) activities
- **Examples:**
  - `put_in_order 1/A6`: all items hidden
  - `put_in_order 13/A11`: all items hidden
  - `recap 15/A9`: all items hidden
  - `recap 19/A2`: all items hidden
  - `odd_one_out 2/A10`: all items hidden
- **Handling:** hidden from learners. per kind: quiz 1/347, recap 6/347, put_in_order 24/41, odd_one_out 9/57, open_question 0/63
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Exact given the rule parsed from serve.py. The recap number follows the 2026-11-18 decision, which serve.py HIDE_JUDGE_FAILED implements since 2026-11-18 (075f045).

### `act.units_empty_skipped` (5 activities)

- **Fails:** units that made no activity (status empty or skipped)
- **Detected by:** checks.json units[*].status != ok
- **Count:** 33 of 1,198 (2.8%) units
- **Examples:**
  - `recall lecture 1`: skipped: no concept needed from an earlier lecture with a definition
  - `odd_one_out lecture 1`: empty: no reason recorded: the model answer made no activity (nothing to order / no group found)
  - `odd_one_out lecture 8`: empty: no reason recorded: the model answer made no activity (nothing to order / no group found)
  - `odd_one_out lecture 16`: empty: no reason recorded: the model answer made no activity (nothing to order / no group found)
  - `odd_one_out lecture 54`: empty: no reason recorded: the model answer made no activity (nothing to order / no group found)
- **Handling:** not fixed (future work). By contract a kind may be missing; kinds: recall {'skipped': 1, 'ok': 62}, put_in_order {'ok': 38, 'empty': 25}, crossword {'ok': 62, 'skipped': 1}, odd_one_out {'empty': 6, 'ok': 57}. Lecture 1 has no recall (no earlier concept) and lecture 63 has no crossword (5 facts): expected.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Exact (status field).

### `act.retried` (5 activities)

- **Fails:** units whose first model output broke a code check and was regenerated (the client's retry loop)
- **Detected by:** checks.json units[*].retry (attempts, problems)
- **Count:** 197 of 1,198 (16.4%) units
- **Examples:**
  - `1/A2`: In questions 1, 3 the correct option is the longest of the four, so a learner can score by picking the longes…
  - `1/A8`: The text has "The segment", which speaks of the lecture or the facts. The learner never sees them: say it as …
  - `9/A15`: Clue 11: the clue writes ['input'], words of the answer or its other names: say it in other words.
  - `13/A20`: Puzzle 3: the odd item is much longer than the three others. Write the four items alike.
  - `54/A7`: Exercise 1: step 3 has "The video", which speaks of the lecture or the facts. The learner never sees them: sa…
- **Handling:** fixed in the pipeline. code checks + retry (s5_activities). Units with status unresolved after retries: 0. Retries by kind: quiz 104, recap 59, crossword 22, odd_one_out 9, put_in_order 1, open_question 2. Last-attempt problems seen: {'correct option longest': 110, 'The text has "The segment", which speaks of the le': 44, 'answer in clue': 33, 'The text has "This segment", which speaks of the l': 10}
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Exact (a retry record exists). Retries repaired the code-check problems listed; none stayed unresolved.

### `act.judge_unresolved` (5 activities)

- **Fails:** items still judge-failed after the judge's one rewrite round
- **Detected by:** totals.judge: failed_items (first judgement) vs still_failed_items; per unit judge.kept
- **Count:** 865 of 3,911 (22.1%) items
- **Examples:**
  - `totals.judge`: first judgement failed 1086 of 3911; rewrote 246 units, kept 160 rewrites; 865 still fail
- **Handling:** fixed in the pipeline. activities judge v3 + rewrite repaired 221 of 1086 first-judgement failures; the rest are hidden or pre-filled by the display rules in the rows above (nothing is dropped from the data).
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Exact (pipeline totals).

### `act.quiz.correct_longest` (5 activities)

- **Fails:** quiz questions whose correct option is the longest of the four (test-wise bias)
- **Detected by:** len(options[answer]) > max(len(other options)) (characters); tied-longest and >=1.5x variants in extra
- **Count:** 160 of 1,163 (13.8%) questions
- **Examples:**
  - `15/A1 Q1`: 25 vs 19 chars: Spatial augmented reality
  - `15/A3 Q4`: 48 vs 37 chars: Eye movements, voice commands, and hand gestures
  - `13/A3 Q1`: 33 vs 26 chars: hardware-generated sensory inputs
  - `32/A13 Q2`: 47 vs 38 chars: broader interactive system development concerns
  - `13/A1 Q2`: 11 vs 9 chars: stimulation
- **Handling:** fixed in the pipeline. Was 52% (751/1,443) in the 2026-11-13 MVP (analysis/mvp/test_report.md); the retry check 'correct option is the longest' brought it to 14% (chance for a unique longest is 25%, including ties 20%). Longest-or-tied: 235; at least 1.5x the next: 0.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Exact (character counts of the stored options). Read 3: 13/A1 Q2 (11 vs 9 chars) is a small margin; no question is 1.5x longer.

### `act.crossword.clue_has_answer` (5 activities)

- **Fails:** crossword entries whose clue contains the whole answer
- **Detected by:** the answer's letters equal one word, or up to 7 consecutive words joined, of the clue (length hint removed; whole words only)
- **Count:** 0 of 645 (0.0%) entries
- **Examples:**
  - (none)
- **Handling:** fixed in the pipeline. s5 blanks answer words in clues with `___` and retries (clue_masked); this rule re-checks the final text.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Whole-word rule. 0 matches. A first version using letter substrings matched 42/A19 CYCLE ('lifecycle'), a false positive, so it was changed. Misses leaks by a different word form (e.g. 'tracker' for TRACKING).

### `act.crossword.clue_has_part` (5 activities)

- **Fails:** crossword entries whose clue contains a word of the answer's concept name/aliases (a part of the answer)
- **Detected by:** a clue word of >= 4 letters (not a function word) equals a >=4-letter word of the concept's name or alias (or shares its first 6 letters when both have >= 6)
- **Count:** 1 of 645 (0.2%) entries
- **Examples:**
  - `17/A13 ACCELEROMETER (acceleration)`: Inertial sensor reading three-axis linear acceleration (13)
- **Handling:** not fixed (future work). Partly handled: s5 masks name words with `___` (over-masking: 'graphics' for SCENEGRAPH); what slips through is counted here.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Read the 1 match: 17/A13 ACCELEROMETER / 'acceleration' is a real leak. A first version also matched 44/A17 'with' (an alias 'evaluation with self-reports'); function words are excluded now. Under-counts other word forms.

### `act.crossword.clue_masked` (5 activities)

- **Fails:** clues containing a `___` mask (word of the answer blanked by code)
- **Detected by:** '___' in clue
- **Count:** 0 of 645 (0.0%) entries
- **Examples:**
  - (none)
- **Handling:** fixed in the pipeline. The 5 masked MVP crosswords (13/A19, 21/A11, 29/A11, 51/A21, 58/A20) were regenerated by the Qwen judge-v3 run; no clue is masked now.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Exact.

### `act.crossword.clue_duplicate` (5 activities)

- **Fails:** two answers of one grid with the same clue text
- **Detected by:** identical clue text (length hint removed) twice in one crossword
- **Count:** 0 of 645 (0.0%) entries
- **Examples:**
  - (none)
- **Handling:** not fixed (future work)
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Exact (identical text); near-identical clues for sibling answers (the MVP's three ear parts) are not caught.

### `act.match.truncated` (5 activities)

- **Fails:** match-pair definitions cut off with '…' (read as unfinished)
- **Detected by:** right side ends with '…' or '...'
- **Count:** 383 of 502 (76.3%) pairs
- **Examples:**
  - `1/A13 extended reality`: An umbrella term, not a specific technology, that covers all present or future immersive technologies, such as augmented reality (AR), virt…
  - `1/A13 augmented reality`: An enhanced version of reality created by technology, in which computer-generated digital content is overlaid on the real world in real tim…
  - `1/A13 mixed reality`: An immersive technology that is the same as augmented reality, in which digital content is overlaid on the view of reality and …
  - `1/A13 immersive technology`: A technology that produces an experience in which a person perceives an environment through sensory organs as real, so that they cannot …
  - `1/A13 immersive experience`: A perceived experience through sensory organs that appears real, because a person cannot distinguish the experienced environment from their…
- **Handling:** not fixed (future work). The right side is the 4a definition cut to a word cap by s5; no judge exists for match pairs (code-made kind).
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Exact (text ends with the ellipsis). Read 5 (57/A15): each is the 4a definition cut mid-clause.

### `act.match.term_in_definition` (5 activities)

- **Fails:** match pairs where the definition (right) contains the whole term (left): the answer is given away
- **Detected by:** the term's words occur as a whole-word phrase in `right` (case-insensitive)
- **Count:** 1 of 502 (0.2%) pairs
- **Examples:**
  - `62/A23 vector3`: A data type that represents the position of a three-dimensional point by storing three coordinates as three elements of a vector.
- **Handling:** not fixed (future work). Masking artefact: the right side is the 4a definition, which usually opens with the term; s5 trims the opening but not later mentions. A looser rule (any >=5-letter word of the term in the definition) matches 231 pairs and mostly flags legitimate overlap (view plane / plane).
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Whole-phrase rule, 1 match, read: fair. A looser any-word version gave 231 and, in a read of 5, flagged only legitimate overlap (view plane / plane), so it was not used. Does not see the masking artefacts that need meaning (an article left after a removed term).

### `act.match.twin_rows` (5 activities)

- **Fails:** pairs of definitions in one match set that are near-identical (token Jaccard >= 0.7)
- **Detected by:** Jaccard of word sets of two right sides in one activity >= 0.7
- **Count:** 0 of 502 (0.0%) pair-pairs
- **Examples:**
  - (none)
- **Handling:** not fixed (future work). Twin rows make a match ambiguous; no judge for this kind.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Exact; 0 at Jaccard >= 0.7 (the MVP's near-identical right sides no longer occur).

### `act.match.bad_start` (5 activities)

- **Fails:** match-pair definitions that start lower-case or with '…'
- **Detected by:** right[0] is lower-case or right starts with '…'
- **Count:** 0 of 502 (0.0%) pairs
- **Examples:**
  - (none)
- **Handling:** not fixed (future work)
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Exact; 0.

### `act.map.too_big` (5 activities)

- **Fails:** concept maps with more than 60 nodes (unreadable at 'Fit')
- **Detected by:** len(nodes) > 60 in concept_map data
- **Count:** 40 of 63 (63.5%) maps
- **Examples:**
  - `62/A21`: 159 nodes, 265 edges
  - `20/A15`: 157 nodes, 234 edges
  - `61/A14`: 138 nodes, 218 edges
  - `58/A17`: 135 nodes, 206 edges
  - `18/A22`: 133 nodes, 190 edges
- **Handling:** display rule. median 71 nodes, max 159. The viewer shows ~20 key concepts by default with 'all N, by part' as an option (2026-11-13, commit 0965ba9). Maps are code-made: no judge verdicts.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Exact count of nodes. 60 is the line from analysis/mvp/test_report.md, not a pipeline value.

### `act.map.long_edge_label` (5 activities)

- **Fails:** map edges whose label has 9 or more words (a sentence fragment)
- **Detected by:** len(label.split()) >= 9 on concept_map edges
- **Count:** 1,065 of 7,450 (14.3%) edges
- **Examples:**
  - `1/A11 C0002->C0005`: is most commonly perceived as involving a user wearing a
  - `1/A11 C0002->C0006`: is most commonly perceived as involving a user transported to a
  - `1/A11 C0004->C0010`: in a broad sense is the entire space between the real and virtual extremes of the
  - `1/A11 C0013->C0012`: has a market in the extended reality market that is about 60 percent of the
  - `1/A11 C0014->C0012`: has a market in the extended reality market that is about 40 percent of the
- **Handling:** not fixed (future work)
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Heuristic (>= 9 words). Read 5: all are fragments cut at a dangling preposition ('...projected onto the'); other long labels may be complete, so over-counts.

### `act.completemap.blank_twice` (5 activities)

- **Fails:** complete-the-map activities that blank the same edge twice
- **Detected by:** duplicate `edge` among blanks
- **Count:** 0 of 63 (0.0%) activities
- **Examples:**
  - (none)
- **Handling:** not fixed (future work)
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Exact; 0 (the MVP's 5/A10 case no longer occurs).

### `act.code_flags` (5 activities)

- **Fails:** report-only code flags on the kept items (not judge verdicts)
- **Detected by:** checks.json units[*].flags other than judge_failed (counted per item or per unit)
- **Count:** 186 of 1,168 (15.9%) flags
- **Examples:**
  - `quiz.rotated_options 1/A4`: [3]
  - `put_in_order.no_order_word 1/A6`: [1]
  - `crossword.small 1/A14`: 5
  - `crossword.filled_from_used 1/A14`: True
  - `recap.facts_uncovered 2/A4`: ['2/S1/F4']
- **Handling:** not fixed (future work). By flag: odd_one_out.not_a_concept 85, recap.facts_uncovered 42, crossword.filled_from_used 20, put_in_order.no_order_word 14, quiz.correct_not_in_facts 10, put_in_order.three_steps 6, put_in_order.title_cue 3, crossword.small 2, recap.duplicate_points 2, quiz.rotated_options 1, open_question.key_fact_unused 1
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** The pipeline's own report-only flags; odd_one_out.not_a_concept counts items, the others units/items as stored.

### `con.shared_key` (3 registry / 2c)

- **Fails:** a name, alias or acronym text that identifies two or more concepts
- **Detected by:** knowledge/names.json: a normalised key mapped to >= 2 different concept IDs
- **Count:** 93 of 4,738 (2.0%) name keys
- **Examples:**
  - `'f'`: C2440 alias of "instantaneous step frequency"; C2517 alias of "importance"; C2519 alias of "total importance"
  - `'hardware'`: C0013 name of "hardware"; C0585 alias of "virtual reality hardware"; C2816 alias of "hardware layer"
  - `'p'`: C0916 alias of "point"; C2502 alias of "optimal path"; C2800 alias of "decision parameter"
  - `'sx'`: C2666 alias of "scaling factor"; C2667 alias of "shearing factor"; C2675 alias of "x-direction scaling factor"
  - `'vr tour'`: C0043 alias of "virtual reality tour"; C1855 alias of "Majuli virtual reality tour"; C2474 alias of "semi-interactive virtual tour"
- **Handling:** not fixed (future work). 100 concept pairs. By role: alias+name 43, alias+alias 34, acronym+acronym 8, alias+alias+alias 5, acronym+alias 1. Planned: O2 (alias rules; merge list) in the 2026-11-18 task list.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Exact collision count. Read 19 (every 5th key): about 16 are defects (true duplicates such as 2d, ios, vr headset, empirical research, or over-broad aliases such as library, source, screen, feedback); 3 are harmless ambiguity (os, sy, alpha).

### `con.name_is_other_alias` (3 registry / 2c)

- **Fails:** a concept's name equals another concept's alias or acronym
- **Detected by:** names.json key has an entry as=name for one concept and as=alias/acronym for another
- **Count:** 45 of 3,122 (1.4%) name keys
- **Examples:**
  - `'audio'`: C1498 alias "audio component"; C1752 name "audio"
  - `'code'`: C1680 alias "coding"; C1847 name "code"
  - `'computer'`: C0065 name "computer"; C0675 alias "personal computer"
  - `'controller'`: C0598 name "controller"; C2340 alias "joystick-based controller"
  - `'data flow diagram'`: C0587 alias "data flow"; C2369 name "data flow diagram"
- **Handling:** not fixed (future work). Subset of con.shared_key.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Exact collision count. Read 15: all are alias collisions; only about 3 are true duplicates to merge (noise cancelling microphone, operating system, exploration), the rest are hypernym aliases (model, system, controller) that should be removed.

### `con.acronym_expansion` (3 registry)

- **Fails:** two concepts that are the same term with an acronym expanded in one (HMD / head-mounted display, VR headset / virtual reality headset, iOS / iPhone operating system, 3D / three-dimensional)
- **Detected by:** for each form F of concept A, replace a token that equals the initials of another multi-word name (content words, hyphens split; plus 2d/3d) by that name; if the result equals a form of concept B != A (plural-stripped) -> pair
- **Count:** 17 of 3,122 (0.5%) concept pairs
- **Examples:**
  - `C0002 "virtual reality" / C0075 "virtual reality headset"`: "VR" with VR = "virtual reality" matches "virtual reality" of C0002
  - `C0005 "head-mounted display" / C0075 "virtual reality headset"`: "VR headset" with VR = "virtual reality" matches "virtual reality headset" of C0075
  - `C0018 "artificial intelligence" (connecting) / C0020 "generative artificial intelligence" (connecting)`: "AI" with AI = "artificial intelligence" matches "artificial intelligence" of C0018
  - `C0043 "virtual reality tour" / C1855 "Majuli virtual reality tour"`: "VR Tour" with VR = "virtual reality" matches "virtual reality tour" of C0043
  - `C0043 "virtual reality tour" / C2474 "semi-interactive virtual tour"`: "VR tour" with VR = "virtual reality" matches "virtual reality tour" of C2474
- **Handling:** not fixed (future work). 3b synonym merge (rebuilt 2026-11-17: 262 model merges) removed many; the rest is counted here. Planned: O2 merge list. The MVP's six acronym/expansion twins (analysis/mvp/test_report.md): 5 now resolve to one concept, open: Majuli virtual reality tour / Majuli VR Tour. The headset family ['C0005', 'C0075', 'C0735'] still appears together on 7 lecture concept maps (11 in the MVP). Strong rule only (the registry lists the acronym on the expanded concept); 4 more pairs match through unambiguous initials alone (e.g. dx / delta x, but also false ones such as IoT / inside-out tracking) and are listed in extra.weak_pairs, not counted.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Strong rule (the registry lists the acronym on the expanded concept). Read all 17: about 14 are real defects (duplicates: operating system / operating system layer, data flow / data flow diagram, two-dimensional form / two-dimensional, iOS / ios, 3D transformation pair, HMD / VR headset; or a wrong alias: VR on 'virtual reality headset', AI on 'generative AI'); about 3 are false (ASQ is two different questionnaires, the Majuli VR Tour pairs are different concepts). Under-counts: needs the acronym listed on the expansion.

### `con.generic_modifier` (3 registry)

- **Fails:** a concept whose name is another concept's name plus a generic modifier (interaction / user interaction)
- **Detected by:** name = leading words all in a small stoplist ['basic', 'certain', 'common', 'current', 'different', 'general', 'important', 'key', 'main', 'major', 'new', 'normal', 'other', 'overall', 'particular', 'primary', 'several', 'simple', 'specific', 'standard', 'typical', 'user', 'users', 'various'] + another concept's full name (plural-stripped)
- **Count:** 22 of 3,122 (0.7%) concept pairs
- **Examples:**
  - `C0137 "user interaction" / C0138 "interaction"`: "user interaction" = generic modifier + "interaction"
  - `C0225 "tracking" / C0819 "user tracking" (connecting)`: "user tracking" = generic modifier + "tracking"
  - `C0406 "locomotion" / C1013 "user locomotion"`: "user locomotion" = generic modifier + "locomotion"
  - `C0590 "user motion" (connecting) / C0829 "motion" (connecting)`: "user motion" = generic modifier + "motion"
  - `C0652 "input" (connecting) / C2420 "user input" (connecting)`: "user input" = generic modifier + "input"
- **Handling:** not fixed (future work). Planned: O2 reviewed merge list.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Read all 22: about 11 are plausible duplicates (every 'user X' / 'X': interaction, tracking, locomotion, motion, input, movement, behavior, feedback); about 11 are different concepts (user interface / interface, main camera / camera, main thread / thread, simple polygon / polygon, primary color / color). Candidate list for a reviewer only.

### `con.embedding_similar` (3 registry)

- **Fails:** two distinct concepts whose stored entry vectors have cosine >= 0.9 and whose names share a word (likely duplicates or near-synonyms)
- **Detected by:** stage_3_registry/clusters.json `candidates` (cosine of the 3a entry embeddings 'name; also called: ...; first facts', Qwen3-Embedding-0.6B, stored; no model call), entries mapped to final concepts through concepts.json merged[]; pairs with different final concepts; threshold 0.9 (3a's own is 0.70) and at least one shared name word of >= 3 letters (without it siblings such as ARKit / ARCore fill the list)
- **Count:** 676 of 16,556 (4.1%) concept pairs (cross-concept pairs with cosine >= 0.70)
- **Examples:**
  - `C0844 "measured angular velocity" / C0845 "actual angular velocity" (connecting)`: cos 0.993
  - `C1761 "Bihu" / C1765 "Bhogali Bihu" (connecting)`: cos 0.993
  - `C0420 "x axis" (connecting) / C0421 "y axis" (connecting)`: cos 0.990
  - `C1500 "audio recording" / C1501 "audio reproduction"`: cos 0.990
  - `C0371 "prior exposure to virtual reality systems" (connecting) / C0372 "repeated exposure to virtual reality" (connecting)`: cos 0.989
- **Handling:** not fixed (future work). Counts by threshold, all pairs / sharing a word: >= 0.8: 5877 / 1688, >= 0.85: 3637 / 1107, >= 0.9: 1881 / 676, >= 0.95: 559 / 272. Of the 676 at >= 0.9, 8 were cut by the 3b cap (12 per cluster) and never judged; the others were judged and kept apart by the 3b model. Vectors embed names plus facts, not names alone (no name-only vectors are stored).
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Weak. Read 40 pairs (every 34th at >= 0.90 and every 14th at >= 0.95): about 6 are plausible duplicates (physics event / physics-related event, thread / main thread, force feedback / force feedback mouse, virtual reality modeling language / modeling language, spotlight effect / region); the rest are siblings (x axis / y axis, box collider / capsule collider, entry- / exit-controlled loop). Vectors embed names plus facts, so siblings that share a passage score high. Use as candidates for review, not as a verdict.

### `con.alias_short` (2c / 3 registry)

- **Fails:** aliases of 1-2 characters that are not the concept's acronym or its initials
- **Detected by:** len(norm(alias)) <= 2 and alias not in acronyms and alias != initials of the name
- **Count:** 44 of 1,741 (2.5%) aliases
- **Examples:**
  - `C1442 "hertz" (connecting)`: alias 'Hz'
  - `C1523 "decibel" (connecting)`: alias 'dB'
  - `C1552 "exponent"`: alias 'x'
  - `C2317 "t value" (connecting)`: alias 't'
  - `C2440 "instantaneous step frequency"`: alias 'f'
- **Handling:** not fixed (future work). Planned: O2 alias rules (fragments) with a reviewed removal list.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Read all of them: units (Hz, dB) and symbols (V, E, G, dx, dt) are legitimate; single letters shared across concepts (f, t, P, x) are defects. About half are defects.

### `con.alias_generic` (2c / 3 registry)

- **Fails:** aliases that are a single generic word from a small stoplist
- **Detected by:** norm(alias) in a 50-word stoplist (system, model, data, user, device, method, ...)
- **Count:** 10 of 1,741 (0.6%) aliases
- **Examples:**
  - `C0055 "virtual reality system"`: alias 'system'
  - `C0226 "interaction technique" (connecting)`: alias 'techniques'
  - `C1671 "end user" (connecting)`: alias 'user'
  - `C2064 "tool" (connecting)`: alias 'tools'
  - `C2266 "independent variable"`: alias 'factor'
- **Handling:** not fixed (future work). Planned: O2 alias rules.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Read all 10: about 7 are defects (system, user, factor, factors, values, model, objects for a more specific concept); tools / techniques / components plural forms are borderline.

### `con.alias_fragment` (2c / 3 registry)

- **Fails:** single-word aliases that are only one word of a longer name (fragment aliases)
- **Detected by:** alias is one token, equals a content token of a multi-word name, and is not an acronym/initials
- **Count:** 98 of 1,741 (5.6%) aliases
- **Examples:**
  - `C0006 "virtual environment"`: alias 'environment'
  - `C0055 "virtual reality system"`: alias 'system'
  - `C0288 "Adobe Flash"`: alias 'Flash'
  - `C0296 "Android operating system" (connecting)`: alias 'Android'
  - `C0313 "display resolution" (connecting)`: alias 'resolution'
- **Handling:** not fixed (future work). Planned: O2 alias rules.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Read 20 (every 5th): about 12 are defects (environment, electromagnetic, library, source, social, constant, asset, mismatch); code identifiers (Destroy, isKinematic) and clear short forms (gaze, plugin) are legitimate. Precision about 60%.

### `con.alias_shared_by_many` (3 registry)

- **Fails:** a name key shared by 3 or more concepts
- **Detected by:** names.json key -> >= 3 concept IDs
- **Count:** 6 of 4,738 (0.1%) name keys
- **Examples:**
  - `'f'`: C2440 alias "instantaneous step frequency"; C2517 alias "importance"; C2519 alias "total importance"
  - `'hardware'`: C0013 name "hardware"; C0585 alias "virtual reality hardware"; C2816 alias "hardware layer"
  - `'p'`: C0916 alias "point"; C2502 alias "optimal path"; C2800 alias "decision parameter"
  - `'sx'`: C2666 alias "scaling factor"; C2667 alias "shearing factor"; C2675 alias "x-direction scaling factor"
  - `'vr tour'`: C0043 alias "virtual reality tour"; C1855 alias "Majuli virtual reality tour"; C2474 alias "semi-interactive virtual tour"
- **Handling:** not fixed (future work). Planned: O2 alias rules (shared alias kept only where defined).
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Exact collision count; read all 6: f, p, sx, sy-like single symbols and 'hardware', 'vr tour' are all alias defects.

### `con.acronym_of_other_concept` (2c / 3 registry)

- **Fails:** an acronym on a concept that is not the initials of its name but is the initials of another concept (FOV on horizontal field of view)
- **Detected by:** acronym != initials of own name, but equals the initials of another concept's multi-word name that is written inside this concept's name
- **Count:** 4 of 158 (2.5%) acronyms
- **Examples:**
  - `C0020 "generative artificial intelligence" (connecting)`: acronym 'AI' = initials of artificial intelligence
  - `C0075 "virtual reality headset"`: acronym 'VR' = initials of virtual reality
  - `C0296 "Android operating system" (connecting)`: acronym 'OS' = initials of operating system
  - `C1468 "horizontal field of view" (connecting)`: acronym 'FOV' = initials of field of view
- **Handling:** not fixed (future work). Planned: O2 (the FOV alias on horizontal field of view).
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Read all 4: FOV on horizontal field of view, VR on virtual reality headset, AI on generative AI, OS on Android operating system; the first three are clear defects, OS is a plausible but loose alias. Under-counts: needs the shorter concept to exist and sit inside the name.

### `con.connecting` (4a definitions)

- **Fails:** connecting concepts (defined: false): no segment defines them, so their 'definition' is a model-written gloss
- **Detected by:** concepts.json defined == false
- **Count:** 1,806 of 3,122 (57.8%) concepts
- **Examples:**
  - `C0012 "market size" (connecting)`: Market size is the monetary value of the extended reality market, split into hardware and software portions.
  - `C0013 "hardware" (connecting)`: Hardware is a part of an extended reality (XR) system, including input devices, output devices, processing devices, cen…
  - `C0014 "software" (connecting)`: Software is a resource in extended reality that is used to process input data, generate output data, and create a relat…
  - `C0016 "three-dimensional environment" (connecting)`: A three-dimensional environment is an all-around environment in the metaverse in which people act as they do in the rea…
  - `C0017 "natural interaction" (connecting)`: Natural interaction is a form of interacting with digital content in an all-around three-dimensional environment, in wh…
- **Handling:** display rule. 2026-11-18 decision: no concept card, not in the glossary, muted non-clickable node in the concept graph, never use their definition; QA gets their facts only. On concept maps: 1779 connecting concepts appear, 2244 of 4625 map node slots (49%). Used in definition-based kinds (crossword, match pairs, recall, spaced-review cards): {'spaced_review': 0}.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Exact (defined == false). Not a defect by itself: these are concepts no segment defines.

### `con.2c.no_triple` (2c concepts)

- **Fails:** concept in no relation of its segment
- **Detected by:** stage_2c_concepts/checks/summary.json flags.no_triple (per-segment checks/lec_N.json resolve the examples)
- **Count:** 184 of 5,805 (3.2%) flags
- **Examples:**
  - `1/S0 no_triple`: extended reality
  - `1/S0 no_triple`: augmented reality
  - `1/S0 no_triple`: mixed reality
  - `1/S0 no_triple`: virtual object
  - `1/S3 no_triple`: artificial intelligence
- **Handling:** not fixed (future work). Report-only in 2c; the registry (3) and 4a use the concepts as extracted.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** The pipeline's own flag. Read 4: extended reality, augmented reality, mixed reality as concepts in no relation of 1/S0: real isolated nodes in that segment.

### `con.2c.name_not_in_facts` (2c concepts)

- **Fails:** concept name that does not occur in its facts' text
- **Detected by:** stage_2c_concepts/checks/summary.json flags.name_not_in_facts (per-segment checks/lec_N.json resolve the examples)
- **Count:** 322 of 5,805 (5.5%) flags
- **Examples:**
  - `2/S0 name_not_in_facts`: virtual reality device
  - `2/S0 name_not_in_facts`: simulation
  - `2/S1 name_not_in_facts`: mouse
  - `2/S1 name_not_in_facts`: device-based virtual tour
  - `2/S1 name_not_in_facts`: web-based virtual tour
- **Handling:** not fixed (future work). Report-only in 2c; the registry (3) and 4a use the concepts as extracted.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** The pipeline's own flag. Read 5: e.g. 'virtual reality device', 'web-based virtual tour' are paraphrases of the facts, so many are harmless.

### `con.2c.reverse` (2c concepts)

- **Fails:** relation written in the opposite direction to its sentence (code check)
- **Detected by:** stage_2c_concepts/checks/summary.json flags.reverse (per-segment checks/lec_N.json resolve the examples)
- **Count:** 437 of 7,502 (5.8%) flags
- **Examples:**
  - `2/S0 reverse`: virtual reality --has as major current application domains--> gaming and entertainment
  - `2/S0 reverse`: virtual reality --has as major current application domains--> healthcare
  - `2/S0 reverse`: virtual reality --has as major current application domains--> automobile industry
  - `2/S0 reverse`: virtual reality --has as major current application domains--> real estate and architecture
  - `2/S0 reverse`: virtual reality --has as major current application domains--> defense
- **Handling:** not fixed (future work). Report-only in 2c; the registry (3) and 4a use the concepts as extracted.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** The pipeline's own flag (relation direction opposite to its sentence). Read 5: the 'virtual reality --has as major current application domains--> healthcare' family looks like a direction the code check disagrees with, but the relation reads sensibly: over-flags.

### `con.2c.acronym_in_name` (2c concepts)

- **Fails:** acronym written inside the concept name (VR headset)
- **Detected by:** stage_2c_concepts/checks/summary.json flags.acronym_in_name (per-segment checks/lec_N.json resolve the examples)
- **Count:** 38 of 5,805 (0.7%) flags
- **Examples:**
  - `2/S1 acronym_in_name`: {'concept': 'VR box', 'acronyms': ['VR']}
  - `2/S1 acronym_in_name`: {'concept': 'VR headset', 'acronyms': ['VR']}
  - `3/S1 acronym_in_name`: {'concept': 'IKEA Place app', 'acronyms': ['IKEA']}
  - `6/S3 acronym_in_name`: {'concept': 'CAVE system', 'acronyms': ['CAVE']}
  - `6/S3 acronym_in_name`: {'concept': 'Java 3D', 'acronyms': ['3D']}
- **Handling:** not fixed (future work). Report-only in 2c; the registry (3) and 4a use the concepts as extracted.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** The pipeline's own flag; read 5: VR box, VR headset, CAVE system are real (the acronym sits inside the name).

### `con.2c.no_shared_fact` (2c concepts)

- **Fails:** relation whose two concepts share no fact
- **Detected by:** stage_2c_concepts/checks/summary.json flags.no_shared_fact (per-segment checks/lec_N.json resolve the examples)
- **Count:** 113 of 7,502 (1.5%) flags
- **Examples:**
  - `2/S1 no_shared_fact`: semi-immersive virtual reality system --is in between--> non-immersive virtual reality system
  - `2/S1 no_shared_fact`: semi-immersive virtual reality system --is in between--> fully immersive virtual reality system
  - `2/S1 no_shared_fact`: semi-immersive virtual reality system --is the most cost-effective and commonly used form of--> virtual reali…
  - `2/S1 no_shared_fact`: semi-immersive virtual reality system --is the form of which most commercial immersive applications are--> vi…
  - `8/S1 no_shared_fact`: matching --refers to congruence between--> sensory modality
- **Handling:** not fixed (future work). Report-only in 2c; the registry (3) and 4a use the concepts as extracted.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** The pipeline's own flag; read 3: the semi-immersive relations are real (the concepts are in different facts of the segment).

### `con.2c.alias_not_in_facts` (2c concepts)

- **Fails:** alias that does not occur in the facts
- **Detected by:** stage_2c_concepts/checks/summary.json flags.alias_not_in_facts (per-segment checks/lec_N.json resolve the examples)
- **Count:** 3 of 5,805 (0.1%) flags
- **Examples:**
  - `13/S4 alias_not_in_facts`: {'concept': 'joystick', 'alias': 'joysticks'}
  - `37/S3 alias_not_in_facts`: {'concept': 'large geographical area', 'alias': 'large space'}
  - `59/S0 alias_not_in_facts`: {'concept': 'virtual reality tour', 'alias': 'virtual tour'}
- **Handling:** not fixed (future work). Report-only in 2c (alias_not_in_facts / lost-and-added items are retried: turn-1 retries 63, turn-2 22, none unresolved).
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** The pipeline's own flag; read all 3: real (joysticks, large space, virtual tour absent from the facts).

### `con.2c.fact_without_concept` (2c concepts)

- **Fails:** fact with no concept
- **Detected by:** stage_2c_concepts/checks/summary.json flags.fact_without_concept (per-segment checks/lec_N.json resolve the examples)
- **Count:** 1 of 2,006 (0.0%) flags
- **Examples:**
  - `31/S4 fact_without_concept`: 3
- **Handling:** not fixed (future work). Report-only in 2c; the registry (3) and 4a use the concepts as extracted.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** The pipeline's own flag; 1 fact (31/S4/F3).

### `con.4a.defined_mismatch` (4a definitions)

- **Fails:** concepts 4a marks defined, with no segment that defines them (defined_in empty)
- **Detected by:** stage_4a_definitions/checks.json flags.defined_mismatch; split by concepts.json defined
- **Count:** 276 of 1,316 (21.0%) concepts
- **Examples:**
  - `C0007 "virtual object"`: A virtual object is an object that does not exist in the real world and can be seen in a virtual world or added to the real world…
  - `C0072 "three-dimensional virtual environment"`: Three-dimensional virtual environment is a virtual reality environment in which users can move by themselves through a computer s…
  - `C0083 "virtual shooting game zone"`: A virtual shooting game zone is a dedicated fully immersive virtual reality system that detects and translates the user's actual …
  - `C0095 "augmented reality application"`: An augmented reality application is an application that emphasizes augmenting digital content onto the real-world view rather tha…
  - `C0114 "computer vision"`: Computer vision (CV) is an enabling technology for augmented reality and mixed reality applications that detects, recognizes, and…
- **Handling:** not fixed (future work). 272 are defined:true with empty defined_in (they keep a card and a glossary entry); 4 are defined:false with a defining segment. The definition text is the real 4a one (one Qwen call per concept, cap 40 facts).
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Exact (the pipeline's flag). 272 of the 276 are defined:true with no defined_in; read 5: the definitions are real 4a text, but no segment is recorded as defining them.

### `con.4a.misplaced` (4a definitions)

- **Fails:** definition facts that 4a flags as misplaced (cited under another concept's segment)
- **Detected by:** stage_4a_definitions/checks.json flags.misplaced
- **Count:** 29 of 3,122 (0.9%) concepts
- **Examples:**
  - `C0109 "marker"`: misplaced facts ['40/S5/F10']
  - `C0269 "model" (connecting)`: misplaced facts ['7/S3/F6']
  - `C0487 "machine learning-based cybersickness evaluation"`: misplaced facts ['26/S1/F2', '63/S1/F2']
  - `C0611 "trigger"`: misplaced facts ['13/S4/F3', '39/S3/F0', '39/S8/F4']
  - `C0647 "pitch"`: misplaced facts ['13/S5/F1', '28/S2/F2']
- **Handling:** not fixed (future work)
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** The pipeline's own flag.

### `con.4a.capped` (4a definitions)

- **Fails:** concepts with more facts than the 4a cap (40), so the definition saw a subset
- **Detected by:** stage_4a_definitions/checks.json totals.capped
- **Count:** 15 of 3,122 (0.5%) concepts
- **Examples:**
  - `totals.capped`: 15 concepts, cap 40
- **Handling:** not fixed (future work)
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** The pipeline's own count.

### `con.4a.definition_no_verb` (4a definitions)

- **Fails:** defined concepts whose definition does not read like a definition (no 'is / are / refers to / means / denotes / stands for / describes' within the first 90 characters of the first 20 words)
- **Detected by:** regex ^.{0,90}?\b(is|are|refers? to|means|denotes|stands for|describes|was|were)\b fails on the first 20 words
- **Count:** 0 of 1,316 (0.0%) defined concepts
- **Examples:**
  - (none)
- **Handling:** fixed in the pipeline. Real 4a (2026-11-17): the old facts-based 'definition' read like a definition in only 26% of cards (analysis/mvp/test_report.md); this rule is a cheap lower bound of what remains.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Cheap lower bound. 0 matches; two false positives of an earlier regex (names containing a dot, three.js and debug.log) were fixed. Does not test that the definition is correct.

### `fact.0a.null_start` (0a preprocess)

- **Fails:** transcript sentences with no start time (the sentence begins inside a subtitle cue)
- **Detected by:** stage_0a_preprocess/times/lec_N.json start == null
- **Count:** 201 of 11,893 (1.7%) sentences
- **Examples:**
  - `1/31`: You might be wondering, why so much interest?
  - `1/54`: Many of you might have done that.
  - `1/90`: So, note here that XR is an umbrella term.
  - `1/92`: It is an umbrella term.
  - `1/94`: So, that is the first thing.
- **Handling:** fixed in the pipeline. By design of 0a; 1b estimates segment boundaries inside a cue and 4d fixed null times for facts (2026-11-13). Also 201 with null end, 38 with both null.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Exact.

### `fact.2a.long` (2a facts)

- **Fails:** facts over about 50 words (several points in one fact?)
- **Detected by:** stage_2a_fact_extraction/checks/lec_N.json flags kind == 'long'
- **Count:** 117 of 2,006 (5.8%) facts
- **Examples:**
  - `1/S0/F1`: 118 words: several points in one fact? | To different people, hearing extended reality (XR), virtual reality (VR), augmented reality (AR), or mixed r…
  - `2/S0/F0`: 88 words: several points in one fact? | Although adoption statistics can be misleading, earlier use forecasts discussed in the course indicate that e…
  - `2/S0/F9`: 63 words: several points in one fact? | Defense is a major virtual reality (VR) application area for training, including specialized military trainin…
  - `2/S1/F9`: 81 words: several points in one fact? | Fully immersive virtual reality (VR) systems, such as dedicated virtual shooting game zones, use many devices…
  - `3/S1/F1`: 70 words: several points in one fact? | Augmented reality (AR) customer-experience applications that let a customer preview a product before purchase…
- **Handling:** not fixed (future work). Report-only in 2a; the 2b judge (which would act on them) was not run.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** The pipeline's own flag.

### `fact.2a.bare_acronym` (2a facts)

- **Fails:** facts using an acronym without its full term
- **Detected by:** stage_2a_fact_extraction/checks/lec_N.json flags kind == 'bare_acronym'
- **Count:** 84 of 2,006 (4.2%) facts
- **Examples:**
  - `1/S3/F1`: Written without the full term: US | A market study reports that the extended reality market size was about 20.5 billion US dollars in 2021 and is exp…
  - `1/S3/F3`: Written without the full term: US | In India, the extended reality industry was estimated at about 1.83 billion US dollars in 2020 and is expected to…
  - `3/S1/F1`: Written without the full term: IKEA | Augmented reality (AR) customer-experience applications that let a customer preview a product before purchase i…
  - `6/S3/F1`: Written without the full term: CAVE | The CAVE system, invented in 1992 at the University of Illinois at Chicago's Electronic Visualization Laborator…
  - `6/S3/F2`: Written without the full term: WTK | In 1992, the company Sense8 developed the WTK software package for higher-level application development in virtu…
- **Handling:** not fixed (future work). Report-only in 2a; the 2b judge (which would act on them) was not run.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** The pipeline's own flag.

### `fact.2a.pointing` (2a facts)

- **Fails:** facts with an unresolved pointing word (this, that)
- **Detected by:** stage_2a_fact_extraction/checks/lec_N.json flags kind == 'pointing'
- **Count:** 52 of 2,006 (2.6%) facts
- **Examples:**
  - `4/S1/F3`: The text has a pointing word that a reader cannot resolve: "this". Name what it refers to. | The sensory experience characteristic of a virtual reali…
  - `5/S2/F1`: The text has a pointing word that a reader cannot resolve: "this". Name what it refers to. | The dictionary definition of mixed reality (MR) describe…
  - `5/S2/F2`: The text has a pointing word that a reader cannot resolve: "this". Name what it refers to. | One definition of mixed reality (MR) is that MR comprise…
  - `5/S2/F6`: The text has a pointing word that a reader cannot resolve: "this". Name what it refers to. | Because most definitions of mixed reality (MR) are confu…
  - `5/S3/F0`: The text has a pointing word that a reader cannot resolve: "this". Name what it refers to. | In this course, mixed reality (MR) is assumed to be the …
- **Handling:** not fixed (future work). Report-only in 2a; the 2b judge (which would act on them) was not run.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** The pipeline's own flag.

### `fact.2a.acronym` (2a facts)

- **Fails:** facts with an acronym flag
- **Detected by:** stage_2a_fact_extraction/checks/lec_N.json flags kind == 'acronym'
- **Count:** 1 of 2,006 (0.0%) facts
- **Examples:**
  - `3/S0/F0`: The lecturer does not use "XR" in the segment. Write the term in full without it. | Extended reality (XR) technologies have huge application potentia…
- **Handling:** not fixed (future work). Report-only in 2a; the 2b judge (which would act on them) was not run.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** The pipeline's own flag.

### `fact.2a.sentences_uncited` (2a facts)

- **Fails:** transcript sentences that no fact cites as evidence
- **Detected by:** 0a sentence IDs minus the union of facts.json evidence
- **Count:** 4,460 of 11,893 (37.5%) sentences
- **Examples:**
  - `1/0`: Hello, welcome to the NPTEL MOOCs course on Foundation for Virtual and Augmented Reality Systems.
  - `1/1`: We are going to start lecture number 1, which is on introductory concepts.
  - `1/2`: I am Dr. Samit Bhattacharya, a member of the Department of Computer Science and Engineering, IIT Guwahati.
  - `33/51`: So those are two broad aspects of heritage that are part of cultural heritage.
  - `33/53`: Now the question is, so far so good, all are there.
- **Handling:** not fixed (future work). Many are greetings, recaps and asides (expected); the share is not a defect by itself.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Exact. Read 5: greetings and asides ('You might be wondering, why so much interest?') are legitimately uncited; the row is a coverage figure, not a defect count.

### `fact.2b.not_judged` (2b verify facts)

- **Fails:** facts never checked by the fact judge (2b skipped: every fact kept unjudged)
- **Detected by:** stage_2b_verify_facts/judgements/lec_N.json judged == false per segment
- **Count:** 2,006 of 2,006 (100.0%) facts
- **Examples:**
  - `segments`: 347 of 347 segments judged:false
- **Handling:** not fixed (future work). Block 1 of the plan is open (PROMPT.md weak point 3); the 2b check files are copies of 2a's. Deferred to the 27B runs.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Exact.

### `fact.no_segment` (4d assemble)

- **Fails:** facts whose segment is missing from the lecture layer
- **Detected by:** facts.json segment not in knowledge/lectures/*.json segments
- **Count:** 0 of 2,006 (0.0%) facts
- **Examples:**
  - (none)
- **Handling:** fixed in the pipeline. 4d reference check: 0 broken references of 206,903.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Exact; 0.

### `fact.null_time` (4d assemble)

- **Fails:** facts with a null start or end time
- **Detected by:** facts.json start/end is null
- **Count:** 0 of 2,006 (0.0%) facts
- **Examples:**
  - (none)
- **Handling:** fixed in the pipeline. 4d fixed null sentence times (2026-11-13).
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Exact; 0.

### `fact.shared_start` (4d assemble)

- **Fails:** facts that share their start time with 2 or more other facts of the same segment (coarse time links)
- **Detected by:** count of (segment, start) >= 3
- **Count:** 462 of 2,006 (23.0%) facts
- **Examples:**
  - `1/S2/F0`: 930.721s: The reality-virtuality continuum is a scale whose extremes are a completely real environment with n…
  - `1/S2/F1`: 930.721s: Augmented reality on the reality-virtuality continuum is the intermediate state in which the real e…
  - `1/S2/F2`: 930.721s: Augmented virtuality on the reality-virtuality continuum is the intermediate state, opposite augmen…
  - `1/S2/F3`: 930.721s: Mixed reality, in a broad sense, is the entire space between the real environment extreme and the v…
  - `1/S3/F4`: 1353.071s: The metaverse is a term that has been in use for more than 30 years and has heavily stimulated gro…
- **Handling:** not fixed (future work). The citation time is the start of the fact's first evidence sentence, often the topic's introduction (test_report.md: 462 with >= 2 others).
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Exact (>= 3 facts in a segment at one start time). Matches the 462 of analysis/mvp/test_report.md.

### `seg.no_facts` (2a / 4d)

- **Fails:** segments with no fact (nothing to ask, recap or link)
- **Detected by:** knowledge/lectures/lec_N.json segments[*].facts == []
- **Count:** 39 of 386 (10.1%) segments
- **Examples:**
  - `1/S4`: Outline the course's objectives, scope, and the digital heritage preservation case study used for practical l…
  - `2/S2`: Summarize the main points of this part of the lecture and preview the next part on AR applications.
  - `4/S3`: Summarize the main points of the lecture.
  - `11/S8`: Summarize the main points of the lecture and preview the remaining topics.
  - `12/S5`: Summarize the main points of the lecture and preview the next topic.
- **Handling:** not fixed (future work). Mostly intros and closing summaries; 4b: segments in no objective 60 (of which 13 define a concept).
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Exact. Read 5: intros and closing summaries ('Summarize the main points...') have no facts by design.

### `seg.4b.in_no_objective` (4b goals)

- **Fails:** segments that serve no lecture objective
- **Detected by:** stage_4b_goals/checks.json in_no_objective
- **Count:** 60 of 386 (15.5%) segments
- **Examples:**
  - `1/S4`: Outline the course's objectives, scope, and the digital heritage preservation case study used for practical l…
  - `1/S5`: Summarize the main points of the lecture and note the seminal reference for the reality-virtuality continuum.
  - `2/S2`: Summarize the main points of this part of the lecture and preview the next part on AR applications.
  - `3/S3`: Summarize the lecture by contrasting VR and AR applications and their system categories.
  - `4/S3`: Summarize the main points of the lecture.
- **Handling:** not fixed (future work). Mostly closing summaries.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** The pipeline's own flag.

### `seg.1b.flagged_left` (1b verify segments)

- **Fails:** lectures where a flagged segment problem was left after the retries
- **Detected by:** stage_1b report.json flagged_left non-empty
- **Count:** 1 of 63 (1.6%) lectures
- **Examples:**
  - `lec_41`: ['Segment 9 (sentences 168 to 178, "Explain how controlled navigation, careful vehicle speed, and consistent …
- **Handling:** not fixed (future work)
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** The pipeline's own flag.

### `seg.4c.assumed` (4c lecture graph)

- **Fails:** concepts a lecture uses but no earlier lecture defines (assumed knowledge)
- **Detected by:** stage_4c_lecture_graph/checks.json totals.assumed_concepts
- **Count:** 2,074 of 3,122 (66.4%) concepts
- **Examples:**
  - `C0007`: virtual object
  - `C0012`: market size
  - `C0013`: hardware
  - `C0014`: software
  - `C0016`: three-dimensional environment
- **Handling:** display rule. Same set as the connecting concepts (2,074 listed; 1,806 have defined:false); shown as assumed knowledge, not as cards. 3 lectures with no prerequisite, 70 lecture pairs where everything is redefined (all_redefined).
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** The pipeline's own list.

### `seg.4d.broken_refs` (4d assemble)

- **Fails:** broken references, duplicate IDs or schema errors in the knowledge layer
- **Detected by:** stage_4d_assemble/checks.json (schema, broken_references, duplicate_ids, coverage, unchecked_files)
- **Count:** 0 of 206,903 (0.0%) references
- **Examples:**
  - `checks.json`: ok: True, 72 files
- **Handling:** fixed in the pipeline. 4d reference check; also re-run independently by analysis/mvp/integrity.py (2026-11-13).
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Exact; 0 of 206,903 (also rechecked independently in analysis/mvp/test_report.md).

### `qa.markdown_raw` (QA / viewer)

- **Fails:** answers containing markdown (** bold, bullets) or LaTeX that the page showed as raw characters
- **Detected by:** regex ** / list bullet / $...$ in answer of analysis/mvp/qa_run/results.jsonl and results_run2.jsonl (2026-11-13 run, not rerun)
- **Count:** 32 of 56 (57.1%) answers
- **Examples:**
  - `Q02 6.8s`: Presence is the psychological side of virtual reality that captures whether a user perceives the immersive qu…
  - `Q04 7.5s`: To calibrate a cheap gyroscope, the constants $C_1$ and $C_2$ are used to mathematically transform the measur…
  - `Q05 11.5s`: Augmented reality (AR) and virtual reality (VR) differ in how they treat the user's perception of reality and…
  - `Q07 8.8s`: Walking-based locomotion is divided into three categories: * **Full gait techniques**: These involve the user…
  - `Q08 6.1s`: Cybersickness is caused by a variety of factors rather than a single one (lecture 10, 4:23; lecture 49, 8:25)…
- **Handling:** fixed in the viewer. Bold and lists rendered since 2026-11-13; formulas typeset with KaTeX (vendored, offline) since 2026-11-18 (7620342); LaTeX in 1 of them. Source: analysis/mvp/test_report.md section 5, issue 1.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Exact on the recorded 2026-11-13 run (56 answers = 36 + 20 reruns). The regex counts ** bold, bullets and $...$; not rerun.

### `qa.slow` (QA)

- **Fails:** answers slower than 15 s
- **Detected by:** seconds > 15 in analysis/mvp/qa_run/results*.jsonl
- **Count:** 3 of 56 (5.4%) answers
- **Examples:**
  - `Q19 20.9s`: How does a Kalman filter fuse IMU and camera data for tracking?
  - `Q07 19.0s`: How do full gait, partial gait and gait negation locomotion techniques differ?
  - `Q19 18.4s`: How does a Kalman filter fuse IMU and camera data for tracking?
- **Handling:** fixed in the pipeline. Round-1+ thinking off and early exit for unknown names (2026-11-17, analysis/qa/STATE.md): bench_after median 4.8 s, max 9.3 s.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Exact on the recorded run.

### `qa.bench_slow` (QA)

- **Fails:** bench answers slower than 8 s after the latency fixes
- **Detected by:** seconds > 8 in analysis/qa/bench_after.jsonl (34 answers, 2026-11-17)
- **Count:** 4 of 34 (11.8%) answers
- **Examples:**
  - `B07 run 0 9.29s`: What is the difference between immersion and presence?
  - `B05 run 1 8.06s`: How do full gait, partial gait and gait negation locomotion techniques differ?
  - `B06 run 1 8.13s`: How is augmented reality different from virtual reality?
  - `B07 run 1 9.29s`: What is the difference between immersion and presence?
- **Handling:** not fixed (future work). Compare questions (two cards, long answers) remain the slowest; analysis/qa/STATE.md.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Exact on the recorded bench.

### `qa.not_covered_padded` (QA)

- **Fails:** not-covered answers that decline but then pad with loosely related facts, and are the slowest type
- **Detected by:** quoted from analysis/mvp/test_report.md section 3 (Q19 20.9 s, Q20); not recomputed
- **Count:** 2 of 36 (5.6%) questions
- **Examples:**
  - `Q19`: Kalman filter: correct refusal after 20.9 s, then related facts
  - `Q20`: Vergence-accommodation: declines, pads with loosely related facts
- **Handling:** fixed in the pipeline. Time fixed 2026-11-17 (unknown name -> early exit; B01 Kalman now one round, analysis/qa/STATE.md); the padding itself is unchanged.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Quoted from a human read of the answers; not recomputed.

### `qa.prereq_odd` (QA / 4c)

- **Fails:** prerequisite answers listing odd concepts (location awareness, markers before lecture 40; augmented virtuality before 16)
- **Detected by:** quoted from analysis/mvp/test_report.md section 3 (Q13, Q35) and 5 (issue 10); not recomputed
- **Count:** 2 of 36 (5.6%) questions
- **Examples:**
  - `Q13`: prerequisites for lecture 40 include location awareness, markers
  - `Q35`: lecture 16: augmented virtuality; HMD = 'displays from the 1950s'
- **Handling:** fixed in the pipeline. lecture_dependencies rewritten 2026-11-17: single mentions listed 'in passing', ranked by uses (analysis/qa/STATE.md); hand-checked on lectures 16, 40, 30.
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Quoted; not recomputed.

### `qa.two_times` (QA)

- **Fails:** 'where is X taught' answers showing two different times (text 14:25, citation 11:44)
- **Detected by:** quoted from analysis/mvp/test_report.md section 3 (Q11, Q12); not recomputed
- **Count:** 2 of 36 (5.6%) questions
- **Examples:**
  - `Q11`: text says 14:25 but cites the segment at 11:44
- **Handling:** fixed in the pipeline. cite() removes a model-written time before a citation; the card cites one time (2026-11-17, analysis/qa/STATE.md).
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Quoted; not recomputed.

### `seg.part_titles` (4e part titles)

- **Fails:** part titles failing the code check (ok: false)
- **Detected by:** stage_4e_part_titles/titles.json ok == false
- **Count:** 0 of 2 (0.0%) segments
- **Examples:**
  - (none)
- **Handling:** not fixed (future work)
- **Sample read (an agent's reading of a few hits; not code, not used for any count):** Pending.

## History: failures found earlier and fixed

| Date | Failure found | Fix |
|---|---|---|
| 2026-11-13 | Activities had no judges; quiz correct option uniquely longest in 52% (751 of 1,443); 5 unresolved crosswords with masked clues; match pairs ~70% problematic | Activities judge v3 (judge + one rewrite round, per-item verdicts in checks.json) and the retry check for the longest option; unique-longest is now computed above. |
| 2026-11-13 | 4a skipped: each 'definition' was the concept's first defining fact (only 26% read like a definition; 1,107 cards) | Real 4a, one Qwen call per concept, cap 40 facts, checks with retry (2026-11-17): 1,316 defined / 1,806 connecting concepts. |
| 2026-11-13 | 3b skipped: duplicate concepts on screen (headset / head-mounted display / VR headset on 11 lecture maps; 6 acronym/expansion twins) | 3b synonym merge rebuilt 2026-11-17 (425 clusters, 262 model merges, 2,795 kept apart); activity concept IDs remapped. Residual duplicates are counted in the con.* rows. |
| 2026-11-13 | 4d: null sentence times broke fact times | 4d fixed for null sentence times (2026-11-13). |
| 2026-11-17 | QA answers slow (median 5.4 s, max 16.2 s) and showing odd prerequisites | Thinking off after round 0, early exit on unknown names, lecture_dependencies rewritten, citations tidied (analysis/qa/STATE.md): median 4.8 s, max 9.3 s. |
| 2026-11-17/18 | Judge-failed items shown to learners | Per-kind hide rule in serve.py (HIDE_JUDGE_FAILED) and the 2026-11-18 display decisions: recaps show passing points only, crosswords pre-fill failed words and hide their clues, connecting concepts get no card / glossary entry / definition. |
