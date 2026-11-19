# Activities study: what the knowledge layer buys

Two questions: (1) which activities are only possible with the knowledge layer, and (2) how activity quality drops
without it, at the same kinds and counts.

## What is compared

Sample: 6 lectures chosen by code (`study.sample()`): the lectures whose activities (ours) have every kind of the
study (quiz, recap, open_question, odd_one_out, put_in_order, concept_map, recall), in course order, then 6 evenly
spaced among them (positions round(i·(n−1)/5), i = 0..5). With today's output: n = 35, lectures **2, 18, 28, 39,
51, 62**.

| system | what it is |
|---|---|
| ours | the existing activities, `pipeline/output/nptel_vr/activities/lec_<n>.json` (not regenerated) |
| B1 plain | the whole lecture transcript (stage 0a, human subtitles) and a short plain prompt per kind asking for the contract's JSON (`study.B1_TASKS`); one call per lecture and kind; the JSON schema is enforced; no code checks, no retry beyond unparsable answers |
| B2 prompt-fair | our own prompts (`pipeline/prompts/activity_<kind>.txt`), filled by `study.b2_unit` with the whole transcript, numbered by sentence, where the facts go; layer inputs given as "(not given)" (segment sub-goal, objective, lecture goal) or "(none)" (related concepts and other facts, concepts, relationships; open-question concepts forced empty); s5's own code checks with retry and feedback and s5's convert functions (option shuffle, drops, flags) |

Counts: B1 and B2 are asked, per lecture, for as many items as ours has in that lecture (quiz questions and recap
points summed over the segments; one baseline unit per lecture, as the baselines have no segments). concept_map and
recall are made by code from the layer in ours, so no prompt of ours exists: both baselines get B1's prompt (recall:
with the titles of the earlier lectures), B2 with the numbered transcript and sentence citations per edge or item.
Model for B1, B2 and the Gemma judges: Gemma 4 12B, `pipeline/configs/gemma4_12b_llamacpp.json` (thinking on, the
pipeline's sampling, the pipeline's LLM client and cache); max_tokens 24576 for every study request (a whole-lecture
answer after 8192 thinking tokens does not fit the config's 12288).

**Caveat (ours' writer):** ours' quiz, open_question, odd_one_out and put_in_order were written by Qwen 3.8 27B on
the EC2 (with Qwen judge and one rewrite), recap by Gemma 4 12B (`activities_local`); recall and concept_map are
code. The baselines are Gemma 4 12B. So the quality comparison of the model-made kinds mixes the layer with the
writer model; recap is the clean same-model comparison.

## Judging

1. **Pipeline judges** (`judge_gemma.py`): s5's `judge_items` / `judge_request` / `judge_round` with
   `prompts/activity_judge_<kind>.txt`, Gemma, one round, no rewrite, for quiz, recap, open_question, odd_one_out,
   put_in_order. The judge sees what the writer saw (ours: s5 rebuilds the units from the layer; B2: its blocks).
   B1 cites nothing, so each B1 item is shown citing the 3-sentence transcript window the overlap rule finds for its
   key text, on B2's blocks. Ours' recap point facts are recovered from the writer's cached answers (all 187 points
   of the sample matched).
2. **Code checks** (`checks.py`, every item): schema valid, duplicate, cites sources (ours: fact IDs that exist;
   B2: sentence numbers; B1: never), traceable (≥ 60% of the key text's content words in one 3-sentence window of
   the transcript: citations.py's overlap rule; recall: in the transcript of the lecture it names), quiz key
   position / key longest / all-none-of-the-above, source talk (s5's patterns), concept_map both ends found
   together and typed relation, recall names an earlier lecture and the concept is found in that lecture.
3. **Sonnet, blind** (`packets.py`): `out/sonnet/` holds `INSTRUCTIONS.md` (criteria and exact output format),
   `packets/lec_<n>.md` (per lecture: title, goal and objectives from `knowledge/goals.json`, the earlier lectures'
   titles, then per kind a unit with sets X/Y/Z = the three systems shuffled per unit, items rendered alike with no
   IDs; at most 12 items per set, seeded sample) and `transcripts/lec_<n>.txt`. The key is `out/sonnet_key.json`
   (outside the folder). Sonnet writes `out/sonnet/judgments.jsonl`, one line per item:

   ```json
   {"unit": "U01", "item": "X3", "correct": true, "grounded": "yes", "distractors": null, "goals": "partly", "cross_lecture": "no", "reason": "..."}
   ```
   `correct` true/false; `grounded` yes/partly/no; `distractors` good/weak/poor/null (quiz, odd_one_out only);
   `goals` yes/partly/no; `cross_lecture` yes/no/wrong; `reason` string.

`summarize.py` joins it all into `out/summary.md` / `summary.json`: generation status, code checks, Gemma judge
pass rates and most-failed criteria, Sonnet rates, per kind and system; and the "only possible with the layer" list
(recall, typed concept maps, complete_map, match_pairs, crossword, spaced-review cards, fact IDs, concept links,
open questions on earlier lectures' facts), counted from ours over the course and the sample.

## Commands

```bash
cd baseline-tests/activities_study
python3 fake_test.py                       # whole flow on the pipeline's fake model server (no GPU)
flock ../gpu.lock bash gpu.sh              # GPU: generate.py, judge_gemma.py; then checks, packets, summarize
                                           # (plain `bash gpu.sh` takes the lock per GPU step itself)
# Sonnet: give it out/sonnet/ (INSTRUCTIONS.md says the rest), output out/sonnet/judgments.jsonl
python3 summarize.py                       # tables -> out/summary.md
```
The queue (`baseline-tests/queue.sh`) starts `gpu.sh` under the lock once `READY` exists. Every step is rerunnable:
model answers are cached by request hash (`out/llm/cache.jsonl`), so a rerun sends only what is missing.
Environment for tests: `ACT_OUT` (output folder), `ACT_LLM` (model config).
