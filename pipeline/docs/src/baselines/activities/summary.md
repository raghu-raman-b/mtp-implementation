# Activities study: ours vs baselines

Sample (lectures): 2, 18, 28, 39, 51, 62. Systems: ours (layer, shipped), ours on Gemma (layer), B1 plain, B2 prompt-fair. Model of the baselines and of the Gemma judges: gemma4_12b_llamacpp.json. Ours: the existing activities (pipeline/output/nptel_vr/activities).

## Generation (baselines; units = lectures)

| system | kind | ok | unresolved | no answer | not run | retried | items dropped (hard checks) |
|---|---|---|---|---|---|---|---|
| B1 plain | quiz | 6 | 0 | 0 | 0 | 0 | 0 |
| B1 plain | recap | 6 | 0 | 0 | 0 | 0 | 0 |
| B1 plain | open_question | 6 | 0 | 0 | 0 | 0 | 0 |
| B1 plain | odd_one_out | 6 | 0 | 0 | 0 | 0 | 0 |
| B1 plain | put_in_order | 6 | 0 | 0 | 0 | 0 | 0 |
| B1 plain | concept_map | 6 | 0 | 0 | 0 | 0 | 0 |
| B1 plain | recall | 6 | 0 | 0 | 0 | 0 | 0 |
| B2 prompt-fair | quiz | 5 | 1 | 0 | 0 | 6 | 0 |
| B2 prompt-fair | recap | 6 | 0 | 0 | 0 | 6 | 0 |
| B2 prompt-fair | open_question | 6 | 0 | 0 | 0 | 0 | 0 |
| B2 prompt-fair | odd_one_out | 4 | 2 | 0 | 0 | 5 | 0 |
| B2 prompt-fair | put_in_order | 6 | 0 | 0 | 0 | 0 | 0 |
| B2 prompt-fair | concept_map | 6 | 0 | 0 | 0 | 0 | 0 |
| B2 prompt-fair | recall | 6 | 0 | 0 | 0 | 0 | 0 |

## Code checks (every item; traceable = >= 60% of the key's content words in one 3-sentence window of the transcript)

| kind | system | items | schema ok | duplicate | cites sources | traceable | mean overlap | source talk | kind checks |
|---|---|---|---|---|---|---|---|---|---|
| quiz | ours on Gemma (layer) | 154 | 100% | 0% | 100% | 82% | 0.792 | 0 | key longest 24%; key position A/B/C/D 39/34/42/39; all/none-of-the-above 0 |
| quiz | B1 plain | 154 | 99% | 1% | 0% | 92% | 0.891 | 87 | key longest 64%; key position A/B/C/D 30/86/32/5; all/none-of-the-above 2 |
| quiz | B2 prompt-fair | 154 | 100% | 1% | 100% | 89% | 0.857 | 0 | key longest 39%; key position A/B/C/D 37/44/39/34; all/none-of-the-above 0 |
| quiz | ours (layer, shipped) | 154 | 100% | 0% | 100% | 77% | 0.736 | 0 | key longest 10%; key position A/B/C/D 36/37/45/36; all/none-of-the-above 0 |
| recap | ours on Gemma (layer) | 209 | 100% | 0% | 100% | 55% | 0.623 | 0 |  |
| recap | B1 plain | 193 | 100% | 0% | 0% | 63% | 0.645 | 12 |  |
| recap | B2 prompt-fair | 193 | 100% | 1% | 100% | 83% | 0.752 | 0 |  |
| recap | ours (layer, shipped) | 230 | 100% | 0% | 100% | 54% | 0.62 | 0 |  |
| open_question | ours on Gemma (layer) | 18 | 100% | 0% | 100% | 33% | 0.531 | 0 |  |
| open_question | B1 plain | 21 | 100% | 0% | 0% | 5% | 0.347 | 3 |  |
| open_question | B2 prompt-fair | 21 | 100% | 0% | 100% | 33% | 0.553 | 0 |  |
| open_question | ours (layer, shipped) | 21 | 100% | 0% | 100% | 10% | 0.435 | 0 |  |
| odd_one_out | ours on Gemma (layer) | 11 | 100% | 0% | 100% | 73% | 0.654 | 0 |  |
| odd_one_out | B1 plain | 14 | 100% | 0% | 0% | 21% | 0.499 | 4 |  |
| odd_one_out | B2 prompt-fair | 14 | 100% | 0% | 100% | 64% | 0.679 | 0 |  |
| odd_one_out | ours (layer, shipped) | 14 | 100% | 0% | 100% | 50% | 0.552 | 0 |  |
| put_in_order | ours on Gemma (layer) | 4 | 100% | 0% | 100% | 75% | 0.748 | 0 |  |
| put_in_order | B1 plain | 7 | 100% | 0% | 0% | 0% | 0.448 | 0 |  |
| put_in_order | B2 prompt-fair | 7 | 100% | 0% | 100% | 29% | 0.558 | 0 |  |
| put_in_order | ours (layer, shipped) | 7 | 100% | 0% | 100% | 29% | 0.552 | 0 |  |
| concept_map | ours on Gemma (layer) | 0 | - | - | - | - | - | 0 |  |
| concept_map | B1 plain | 138 | 100% | 0% | 0% | 78% | 0.707 | 0 | ends found together 48%; typed relation (R..) 0% |
| concept_map | B2 prompt-fair | 134 | 100% | 0% | 100% | 84% | 0.74 | 0 | ends found together 60%; typed relation (R..) 0% |
| concept_map | ours (layer, shipped) | 1076 | 100% | 0% | 100% | 79% | 0.73 | 0 | ends found together 52%; typed relation (R..) 100% |
| recall | ours on Gemma (layer) | 0 | - | - | - | - | - | 0 |  |
| recall | B1 plain | 35 | 100% | 0% | 0% | 9% | 0.346 | 0 | names an earlier lecture 100%; concept found in that lecture 80% |
| recall | B2 prompt-fair | 35 | 100% | 0% | 100% | 11% | 0.365 | 0 | names an earlier lecture 100%; concept found in that lecture 74% |
| recall | ours (layer, shipped) | 35 | 100% | 0% | 100% | 31% | 0.503 | 0 | names an earlier lecture 100%; concept found in that lecture 89% |

## Pipeline judges (Gemma 4 12B, prompts/activity_judge_<kind>.txt; recap items: points and the text)

| kind | system | items judged | pass | no verdict | units not ok | most failed criteria |
|---|---|---|---|---|---|---|
| quiz | ours on Gemma (layer) | 154 | 96% | 0 | 0 | answerable 3, worth_asking 2, one_answer 2 |
| quiz | B1 plain | 154 | 65% | 0 | 0 | no_source_talk 40, answerable 11, no_giveaway 3, worth_asking 1 |
| quiz | B2 prompt-fair | 154 | 99% | 0 | 0 | answerable 2, one_answer 1 |
| quiz | ours (layer, shipped) | 154 | 99% | 0 | 0 | no_giveaway 1, one_answer 1 |
| recap | ours on Gemma (layer) | 209 | 78% | 0 | 0 | faithful 34, supported 9, stands_alone 4, coverage 4 |
| recap | B1 plain | 193 | 91% | 0 | 0 | supported 8, faithful 4, no_source_talk 3, stands_alone 1 |
| recap | B2 prompt-fair | 193 | 98% | 0 | 0 | stands_alone 2, one_idea 1, supported 1 |
| recap | ours (layer, shipped) | 230 | 88% | 0 | 0 | faithful 15, one_idea 10, supported 5, clear 3 |
| open_question | ours on Gemma (layer) | 18 | 83% | 0 | 0 | answerable 2, clear 1 |
| open_question | B1 plain | 21 | 10% | 0 | 0 | answerable 16, one_thread 4, answers_question 3, no_source_talk 2 |
| open_question | B2 prompt-fair | 21 | 71% | 0 | 0 | answerable 4, one_thread 1, answers_question 1 |
| open_question | ours (layer, shipped) | 21 | 90% | 0 | 0 | answers_question 2 |
| odd_one_out | ours on Gemma (layer) | 11 | 73% | 0 | 0 | in_facts 2, one_answer 1, near_miss 1 |
| odd_one_out | B1 plain | 14 | 29% | 0 | 0 | in_facts 8, no_source_talk 5, one_answer 2, near_miss 1 |
| odd_one_out | B2 prompt-fair | 14 | 64% | 0 | 0 | no_giveaway 5, in_facts 1 |
| odd_one_out | ours (layer, shipped) | 14 | 71% | 0 | 0 | near_miss 3, no_giveaway 2, one_answer 2, in_facts 1 |
| put_in_order | ours on Gemma (layer) | 4 | 50% | 0 | 0 | real_sequence 2, one_order 2, worth_doing 2 |
| put_in_order | B1 plain | 7 | 0% | 0 | 0 | in_facts 7, real_sequence 1, one_order 1 |
| put_in_order | B2 prompt-fair | 7 | 43% | 0 | 0 | in_facts 3, real_sequence 3, one_order 2 |
| put_in_order | ours (layer, shipped) | 7 | 86% | 0 | 0 | in_facts 1, real_sequence 1, no_giveaway 1, worth_doing 1 |

## Sonnet judge (blind; at most 12 items per set)

Judged 1037 of 1037 items.

| kind | system | items | correct | grounded | not grounded | distractors good | serves goals | links lectures | wrong link |
|---|---|---|---|---|---|---|---|---|---|
| quiz | ours on Gemma (layer) | 67 | 100% | 97% | 0% | 55% | 78% | 0% | 0% |
| quiz | B1 plain | 69 | 99% | 100% | 0% | 43% | 61% | 0% | 0% |
| quiz | B2 prompt-fair | 69 | 100% | 99% | 0% | 51% | 64% | 0% | 0% |
| quiz | ours (layer, shipped) | 69 | 100% | 99% | 0% | 75% | 80% | 0% | 0% |
| recap | ours on Gemma (layer) | 69 | 99% | 97% | 0% | - | 77% | 3% | 0% |
| recap | B1 plain | 71 | 96% | 93% | 0% | - | 68% | 3% | 0% |
| recap | B2 prompt-fair | 71 | 100% | 100% | 0% | - | 75% | 1% | 0% |
| recap | ours (layer, shipped) | 72 | 99% | 99% | 0% | - | 85% | 1% | 0% |
| open_question | ours on Gemma (layer) | 18 | 100% | 100% | 0% | - | 100% | 11% | 0% |
| open_question | B1 plain | 21 | 95% | 57% | 0% | - | 86% | 5% | 0% |
| open_question | B2 prompt-fair | 21 | 100% | 100% | 0% | - | 86% | 0% | 0% |
| open_question | ours (layer, shipped) | 21 | 100% | 95% | 0% | - | 90% | 0% | 0% |
| odd_one_out | ours on Gemma (layer) | 11 | 100% | 73% | 0% | 64% | 36% | 9% | 0% |
| odd_one_out | B1 plain | 14 | 100% | 93% | 0% | 71% | 64% | 7% | 0% |
| odd_one_out | B2 prompt-fair | 14 | 100% | 100% | 0% | 86% | 57% | 0% | 0% |
| odd_one_out | ours (layer, shipped) | 14 | 86% | 100% | 0% | 86% | 43% | 0% | 0% |
| put_in_order | ours on Gemma (layer) | 4 | 100% | 100% | 0% | - | 75% | 0% | 0% |
| put_in_order | B1 plain | 7 | 100% | 100% | 0% | - | 86% | 0% | 0% |
| put_in_order | B2 prompt-fair | 7 | 100% | 100% | 0% | - | 71% | 0% | 0% |
| put_in_order | ours (layer, shipped) | 7 | 100% | 100% | 0% | - | 86% | 0% | 0% |
| concept_map | ours on Gemma (layer) | 0 | - | - | - | - | - | - | - |
| concept_map | B1 plain | 72 | 75% | 76% | 1% | - | 54% | 3% | 0% |
| concept_map | B2 prompt-fair | 72 | 69% | 79% | 0% | - | 67% | 1% | 0% |
| concept_map | ours (layer, shipped) | 72 | 97% | 96% | 0% | - | 62% | 1% | 0% |
| recall | ours on Gemma (layer) | 0 | - | - | - | - | - | - | - |
| recall | B1 plain | 35 | 97% | 66% | 11% | - | 23% | 89% | 11% |
| recall | B2 prompt-fair | 35 | 100% | 69% | 9% | - | 34% | 86% | 14% |
| recall | ours (layer, shipped) | 35 | 94% | 83% | 0% | - | 37% | 94% | 6% |

## Only possible with the knowledge layer (counts from ours: whole course of 63 lectures; the sample in brackets)

- recall, before each lecture (lecture graph: which earlier lectures it needs; concepts; their 4a definitions as answers): 62 (sample 6) activities, 348 (sample 35) items. The baselines attempted it from the titles of the earlier lectures (see the checks and Sonnet tables).
- concept_map with typed relationships (concepts C.., relationships R.. with their facts): 63 (sample 6) maps, 7450 / 7450 (sample 1076 / 1076) edges typed. The baselines drew maps from the transcript, with no relationship IDs or facts.
- complete_map (the map with blanks; options from the lecture's other labels and concepts): 63 (sample 6) activities, 252 (sample 24) blanks. Not attempted by the baselines.
- match_pairs (glossary: concept and its definition): 63 (sample 6) activities, 502 (sample 48) pairs. Not attempted.
- crossword (concepts with definitions; clues judged against the definition): 62 (sample 6) grids, 645 (sample 66) entries. Not attempted.
- spaced_review cards (one per defined concept, with every lecture that uses it): 1316 cards (course-wide).
- fact IDs (time links into the video; the judge checks each item against its cited facts): 1168 / 1168 (sample 135 / 135) activities carry facts; 1338 / 1338 (sample 175 / 175) quiz / odd-one-out / put-in-order items cite their own facts. B2 cites transcript sentences; B1 cites nothing.
- concepts on activities (glossary links in the viewer): 1168 / 1168 (sample 135 / 135).
- open questions built on an earlier lecture's facts (lecture graph): 31 / 219 (sample 0 / 21) questions; with concept links 219 / 219 (sample 21 / 21).
