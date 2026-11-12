# Pipeline v3: knowledge layer, activities, question answering

Plan of 2026-11-12. Tick a box in the same commit that finishes the item.

**Goal.** A knowledge layer for a lecture course that serves two uses: answering learners' questions, and generating
activities. "Quality" below always means: does this make those two uses more accurate or easier.

**Owners.** **F** Fable: plan, prompts, gold sets, review at each gate. **O** Opus: scripts, tests, reports, commits.
**U** you: design decisions, starting the instance. (EC2) marks an item that needs the model servers.

## 1. How the work runs

| Where | What |
|---|---|
| Local PC | The Opus session, all code, the repo, every output file and LLM cache, the embedding model, the viewer, Gemma 4 for the site's question answering, documentation |
| EC2 (GPU) | Only the model servers: Qwen 3.8 27B FP8 (port 8094, writes), Sage-A1.5 FP8 (port 8095, judges). Reached through an SSH port forward; the configs attach (`"launch": false`) |

Rules for the run:
1. **Small first.** Every stage is built and tuned on lectures 1, 4 and 16. The full course runs once, in block 5.
2. **One item, one commit, one push.** Outputs and `llm/cache.jsonl` are committed with the code that made them. Nothing
   stays unpushed for more than one item.
3. **A block ends with a report**, `analysis/<block>/report.md`: what ran, the numbers, every failure kind with examples,
   the weak points found, proposed improvements, decisions needed. The `block-reviewer` agent (Fable,
   `.claude/agents/block-reviewer.md`) reads it and answers "proceed" or "change" with a list. On "change", do the list
   and review again. On "proceed", commit `block N done` and start the next block.
4. **Prompt wording may be refined inside a block**, with before and after numbers in the report. **The design may not**
   (what a stage takes in, what it puts out, which stages exist, what a fact or concept is): write the proposal under
   "Decisions for you" below and carry on with the current design.
5. **Tests look for damage**, not for confirmation: each test lists what it would look like if the stage were broken, and
   seeds known errors where there is no reference.
6. Real models run only on an instance you started. Opus does not start or stop instances. Plumbing is checked with the
   fake model first.
7. The notebook `pipeline.ipynb` gets a section per stage and run notes per test, as for stages 0a to 2b.

## 2. Data model

| Thing | ID | Holds | Made in |
|---|---|---|---|
| Sentence | `4/17` | text, start and end time | 0a |
| Segment | `4/S1` | first and last sentence, sub-goal | 1a to 1c |
| Fact | `4/S1/F2` | text, evidence (sentence IDs) | 2a, 2b |
| Segment concept | `4/S1/C3` | name, aliases, facts, defined (true/false) | 2c |
| Segment relationship | `4/S1/R0` | subject, label, object (segment concepts), facts | 2c |
| Concept | `C0042` | canonical name, aliases, facts, lectures, segments, `defined_in` (the segments that define it), the segment concepts merged into it and how (exact name, model, with the reason), definition | 3, 4a |
| Relationship | `R0107` | subject and object (concept IDs), label, facts, segments | 3 |
| Objective | `4/O1` | goal, achieves, segments | 4b |
| Lecture goal | `4/G` | goal, achieves, objectives | 4b |
| Course goal | `G2` | goal, achieves, lectures | 4b |
| Lecture link | `4 -> 16` | the concepts lecture 16 uses that lecture 4 defines; direct or indirect | 4c |

Everything traces down to sentences, so every answer and activity can cite a lecture and a time.

## 3. Checklist

### Block 0: setup
- [x] **F** Prompts drafted: `concept_extraction.txt`, `concept_relations.txt`, `concept_same.txt`,
  `concept_definition.txt`, `lecture_goals.txt`, `course_goals.txt` (untested).
- [x] **F** Reviewer agent written: `.claude/agents/block-reviewer.md`.
- [x] **O** Check that the reviewer agent loads and runs on Fable; if it does not, stop and tell the user. (Ran as
  `claude-fable-5-2` with Read and Bash working, 2026-11-12.)
- [x] **O** Move the EC2 setup to `pipeline/setup_ec2.sh` (from `lir-construction/setup_ec2.sh`): vLLM, the two models,
  the embedding model download, a smoke test. Add `pipeline/ec2.md`: start a server, forward the port, swap models.
  (Servers start from the same config files with `scripts/llm/serve.py`; the old script stays for `lir-construction`.)
- [x] **O** Attach-only configs for the forwarded ports; fake-model run of 2a and 2b from the local PC.
  (`tests/fake_run.py`: 22 checks pass on lectures 1, 4, 16; the real caches still answer through the new configs.)
- [x] **O** Write the missing 2026-11-12 run notes into the notebook from the logs and caches (segmentation on the 27B;
  2a with the new fact definition: 65 to 20 facts on lecture 1, 62 on lectures 1, 4, 16; judge round: 8 failed).
- [ ] **O** (EC2) Finish the interrupted 2b round (segment 4/S1), so `stage_2b_verify_facts/` holds the 62-fact run.
  This is the baseline for block 1.

### Block 1: the fact judge (2b)
What the last round showed: 8 of 62 facts failed. 3 of them were passed by the judge and failed only by the code check
for "this" (at least one is a false alarm). The judge passed two thin facts in 1/S0 (full forms of the abbreviations;
what people associate with XR). Rewrites are not judged again. Nothing yet measures the judge against a reference.

- [x] **F** Gold labels for the 62 facts: pass or fail per property, with a note, in `analysis/fact_judge/gold.json` (55 pass, 7 fail).
- [x] **F** Seeded errors: about 30 facts made wrong on purpose, a few per kind (trivia, one detail of a point, two points
  in one, a summary of the segment, a question stated as fact, a missing evidence sentence, a pronoun, a bare acronym,
  course logistics, a dropped hedge, added outside knowledge), each with the property it breaks:
  `analysis/fact_judge/seeded.json` (34 entries, one per judge call).
- [x] **F** Missed facts: for 4 segments, list what the segment teaches that no fact holds (the judge cannot see these;
  this measures 2a): `analysis/fact_judge/missed.json` (all 15 segments read; 5 points, 1 major).
- [ ] **O** `analysis/fact_judge/compare.py`: judge against gold and against the seeded errors, per property: caught,
  missed, false alarms; the list of disagreements with both reasons.
- [ ] **O** (EC2) Run the judge three times on the same facts: how many verdicts flip.
- [ ] **O** The code checks against gold: false alarms and misses of `pointing` and `acronym`.
- [ ] **O** (EC2) Judge the rewritten facts once more (test only): how many rewrites still fail.
- [ ] **O** Report with proposed changes; **F** revises `fact_judge.txt` (and `fact_rewrite.txt` if needed); rerun; the
  report shows before and after.
- [ ] **Gate.** Proposed targets: seeded errors caught ≥ 90%; false alarms on gold-pass facts ≤ 10%; flips ≤ 5%; no
  property with zero catches.

### Block 2: concepts and relationships per segment (2c)
One conversation per segment with the extractor (Qwen). Turn 1 (`concept_extraction.txt`): the segment's verified facts
in, concepts out (name, aliases, facts, defined). Code checks. Turn 2 (`concept_relations.txt`): the checked concept
list in, triples out (subject, label, object, facts). Facts are numbered `[1]..[n]` in the prompt and mapped back in code.

- [ ] **O** `scripts/s2c_concepts.py`, writing `stage_2c_concepts/`: `concept_maps/lec_<n>.json`,
  `relations/lec_<n>.json`, a text view of both, `checks/lec_<n>.json`, `llm/`. The answer schema limits subject and
  object to the concept names of the segment.
- [ ] **O** Code checks, reported per segment: a fact number out of range; the same name twice (merged); a name or alias
  that appears in none of its facts; an alias not written in any fact; a fact with no concept; a triple whose two
  concepts never share a cited fact; a triple and its reverse; a vague label ("is related to"); a concept with no
  triple.
- [ ] **O** (EC2) Run on lectures 1, 4, 16 (15 segments), twice: counts per segment, and how much the two runs agree.
- [ ] **F** Gold for 4 segments: the concepts and triples a careful reader would list. Then precision and recall of the
  run, and a read of every concept and triple of the three lectures for: not a term of the subject, wrong `defined`,
  one thing under two names, a label the fact does not state, wrong direction, a missing relationship.
- [ ] **O** Report: numbers, failure kinds with examples, what the facts themselves made impossible (a concept or a
  relationship lost because 2a left it out). **F** revises the two prompts; rerun.
- [ ] **Gate.** Proposed targets on gold: concepts precision and recall ≥ 90%; triples stated by their facts ≥ 95%;
  triples recall ≥ 80%; `defined` right ≥ 90%.

### Block 3: the concept registry (across lectures)
1. **Exact merge (code).** Segment concepts with the same normalised name (case, plural, hyphen or space) become one.
   Facts, lectures, segments and `defined_in` are joined. A shared acronym alone is not an exact match: it goes to step 3.
2. **Candidates (code).** Embed each concept (name, aliases, its defining facts). Candidates: similar above a threshold,
   or sharing an alias. Clusters are the connected candidates, capped in size (a larger cluster is split).
3. **Same or different (model, one call per cluster, `concept_same.txt`).** Each entry with its names, lectures and
   facts (defining facts first, capped). The answer is the grouping, a reason per group and the group's name.
4. **Merge (code).** One concept per group: `C0001…` in course order, names that lost become aliases, lists joined.
   Relationships are rebuilt from the segment triples through the segment-concept-to-concept map, so a change to a
   concept always reaches its relationships: ends renamed, a triple that now joins a concept to itself dropped and
   logged, identical triples joined with their facts. Every merge is logged with its reason in `decisions.jsonl`.

- [ ] **O** Choose the embedding model on a labelled pair set: start with `Qwen/Qwen3-Embedding-0.6B` (must also run on
  the local PC for the site), against a larger one and the old pipeline's `all-mpnet-base-v2`. Check the IDs and for a
  newer model before fixing it; add the download to `setup_ec2.sh`.
- [ ] **O** `scripts/s3a_candidates.py` (steps 1, 2), `s3b_same.py` (step 3), `s3c_registry.py` (step 4), writing
  `stage_3_registry/`: `concepts.json`, `relations.json`, `clusters.json`, `decisions.jsonl`, a text view.
- [ ] **F** Pair gold: about 80 pairs from the test lectures labelled same or different, including the hard kinds (a
  kind of, a part of, a property of, same name with another meaning, synonym, acronym).
- [ ] **O** (EC2) Tests: candidate recall (a pair that is the same but never reaches the model can never merge) and the
  threshold that gives it; the model's grouping against the pair gold; seeded splits (one concept renamed in half its
  segments: does it come back together) and seeded traps (two different concepts given close names: do they stay
  apart); exact merges of the same name read for different meanings; relationships after the merge (no missing end,
  none lost without a log line, counts add up); near-duplicate labels between the same two concepts, counted.
- [ ] **O** Report; **F** revises `concept_same.txt`; rerun.
- [ ] **Gate.** Proposed targets: candidate recall ≥ 95%; wrong merges ≤ 2%; missed merges ≤ 10%; the registry rebuilds
  to the same result from the caches.

### Block 4: definitions, goals, the lecture graph, the assembled layer
- [ ] **O** `scripts/s4a_definitions.py` (one call per concept, `concept_definition.txt`): definition, the facts it is
  built from, `defined`, `misplaced`. The fact list is capped (defining facts first, then by lecture order). A concept
  with `misplaced` facts is reported, not split.
- [ ] **O** `scripts/s4b_goals.py`: one call per lecture (`lecture_goals.txt`: objectives and the lecture goal from the
  segment sub-goals and each segment's concepts), then one call for the course (`course_goals.txt`).
- [ ] **O** `scripts/s4c_lecture_graph.py` (code): lecture K is needed for lecture L when L uses a concept that K
  defines and K comes first. The link carries those concepts. Direct prerequisites are the links not already implied
  through another lecture; a concept used in most lectures counts for less, so that not every lecture depends on
  lecture 1. "What is needed before lecture 23" is then: its direct prerequisite lectures, all earlier ones behind
  them, the concepts it uses with their definitions and defining facts, and the concepts it uses that the course never
  defines.
- [ ] **O** `scripts/s4d_assemble.py` (code), writing `knowledge/`, checked against a schema. Derived from the layer:
  - the name index: every name, alias and acronym to its concept (what `check_concept` looks up);
  - a card per concept: definition, where it is defined (lecture, segment, time), its facts with the defining ones
    first, its relationships in both directions, the lectures that use it;
  - the fact store: each fact with its embedding, concepts, segment and time;
  - per lecture: concepts introduced, concepts met again, concepts assumed (never defined in the course); the
    lecture's own concept map; its goals;
  - the goal tree: course goal, lectures, objectives, segments, down to facts and concepts;
  - the lecture graph, and for each concept the path of lectures that leads to it;
  - the course's assumed knowledge: concepts used but never defined.
- [ ] **O** (EC2) Run on the test lectures. Tests: definitions against their facts (anything not in the facts, a
  definition that is a summary, a concept defined from outside knowledge); `defined` here against `defined_in` from 2c;
  goals against the sub-goals (an ability no segment teaches, a segment left out); the lecture graph read by hand for
  the test lectures; the assembled layer for broken references.
- [ ] **F** Read every definition and goal of the test lectures. **O** Report; **F** revises the prompts; rerun.
- [ ] **Gate.** Proposed targets: definitions with nothing outside their facts ≥ 95%; no broken reference in
  `knowledge/`.

### Block 5: the full course (EC2)
- [ ] **O** A run script for stages 2a to 4d over all 63 lectures: resumable from the caches, a commit and push after
  each stage and after every 10 lectures inside a stage, timing per stage.
- [ ] **O** Run it. Report: counts per stage, every flag and unresolved item, the 20 largest concepts and clusters, the
  concepts with `misplaced` facts, lectures with unusual numbers.
- [ ] **F** Review samples from lectures outside the test set (facts, concepts, merges, definitions, goals).
- [ ] **Gate.** No stage is worse on the samples than it was on the test lectures; otherwise fix and rerun that stage.

### Block 6: question answering
- [ ] **F** The question set, written from the transcripts and the syllabus, not from the knowledge layer: about 80
  questions with a reference answer and where the answer is taught. Kinds: what is X; how does X work; how do X and Y
  relate or differ; list the kinds or parts of X; where is X taught; what do I need before lecture N or before concept
  X; what is lecture N for; questions across several lectures; an acronym or a misspelt name; something the course
  does not cover (the right answer says so); an unclear question.
- [ ] **O** The tools, over `knowledge/`: `check_concept(name)` returns the card (definition, facts, relationships), or
  says the name is unknown and to use the fact lookup; `fact_lookup(query)` rephrases the query several ways, searches
  the fact store and returns the best facts; `lecture_dependencies(lecture)` reads the lecture graph. Proposed
  additions, yours to strike: `lecture_overview(lecture)` (goals, concepts, segments) and `course_goals()`.
- [ ] **F** The answering prompt and the tool descriptions: which tool for which kind of question, answer only from what
  the tools return, cite lecture and time, say when the course does not cover it.
- [ ] **O** `qa/`: the tool loop, a log of every call, the test runner.
- [ ] **O** (EC2) Run the question set with Qwen 27B, and locally with Gemma 4 (the site's model). Score: the right tool
  chosen; the reference facts found; the answer correct; every claim backed by a returned fact; refusal when the
  course does not cover it. Sort every failure by cause: missing knowledge, retrieval, tool choice, the answer.
- [ ] **O** Report; fix what the causes point to (the layer, the tools, or the prompt); rerun.
- [ ] **Gate.** Proposed targets with the 27B: correct ≥ 85%, backed by facts ≥ 95%. Gemma 4: reported, with what it
  costs to use it on the site.

### Block 7: activities
Starts while block 5 runs, on the test lectures. Generated per lecture after the lecture's knowledge is complete.
- [ ] **F + U** The activity list and where each one sits, agreed before any prompt is written. Starting point:
  - from the earlier pipelines, now fed by the layer: quiz per segment (from facts; wrong options from related
    concepts), recap per segment (from facts and the objective), recall before a lecture (the concepts the lecture
    graph says it needs), open questions per lecture (using relationships and prerequisites, with the reference answer
    and its key facts), the concept map (the lecture's concepts and relationships), spaced review (by concept);
  - new: crossword (concept names, clues from the definitions), match pairs (concept and definition), complete the map
    (a relationship or a concept left blank), odd one out (from kinds and parts), put in order (when facts give steps).
- [ ] **F** Prompts for each activity and its judge. **O** Scripts, code checks on format, tests on the test lectures,
  report. **F** Review. Then the full course (EC2).
- [ ] **Gate.** Every activity answerable from the cited facts; the judge's failures and a sample of passes read by F.

### Block 8: the viewer (local)
- [ ] **O** Rebuild for v3: the lecture with its segments and goals; concept cards and the glossary; the lecture and
  course concept maps; "before this lecture"; the activities; a question box that runs the tool loop with Gemma 4 on
  the PC. Learner-facing: no statistics or build numbers outside a developer mode.
- [ ] **Gate.** A walk through three lectures with every activity kind and ten questions from the set.

### Block 9: documentation and presentation
- [ ] **O** `pipeline/docs/pipeline.html`, in the manner of `lir-construction/docs/pipeline.html`: each stage with its
  input, prompt, output, checks and test results; the data model; how to run it on a new course.
- [ ] **O** A final report from the block reports: what was measured, what is weak, what is left.
- [ ] **F** The presentation, once you give the outline: minimal, built from the final report and the viewer.

## 4. Decisions for you
| # | Question | Until you decide |
|---|---|---|
| D1 | The code check fails a fact for "this" even when the judge passes it (3 of the 8 failures). Keep failing, or only report? | Kept; block 1 gives the numbers |
| D2 | Rewritten facts are not judged again. Add a second judge call for them? | Not added; block 1 measures how many rewrites still fail |
| D3 | Lectures 1, 4 and 16 share few concepts, so they test the registry weakly. Add about five lectures (2, 3, 5, 15, 17) for block 3? | Three lectures |
| D4 | Relationships are found only between concepts of one segment. A relationship between concepts taught in different segments is never found. Add a later pass? | Not added; block 3 counts the concept pairs that appear in one lecture but never in one segment |
| D5 | `defined` is true or false per segment. A list of the defining facts instead would let the definition and the answers start from them. | True or false, as you specified |
| D6 | Labels are free text, as you chose. The same relationship may then appear under several wordings and cannot be queried by kind. | Free text; block 3 counts the duplicates |
| D7 | The gate targets above are proposals. | Used as written |

Choices made in the prompt drafts, yours to overrule:
- A concept is a term of the subject, taken even when a segment only mentions it; ordinary words and sources are not.
- Aliases are only names the facts use; none from the model's own knowledge.
- The definition call also returns `defined` and `misplaced` (facts that use the name for another thing), as a check
  on exact-name merges.
- The level between a segment sub-goal and the lecture goal is called an objective. "Achieves" is read as: what
  reaching the goal gives the learner.
- Course goals: four to eight; a lecture may serve more than one.

## 5. Weak points seen in the design
1. **"Fact quality is good, it is up to the judge."** Mostly supported: lecture 1 went from 65 facts to 20, and 54 of 62
   passed. But the judge has never been measured against a reference, it passed two thin facts, and nothing measures
   what 2a misses (coverage is 44% of sentences). Block 1 adds all three measurements.
2. **Concepts come from facts only.** A term that 2a left out can never become a concept. Block 2 reports these.
3. **Exact-name merge** joins two meanings of one name without a model looking. The definition call's `misplaced` list
   and a read of the exact merges are the checks.
4. **Hub concepts.** A concept named in most lectures brings a very long fact list to the definition call and would
   make every lecture depend on the first ones. Both are capped or down-weighted (block 4).
5. **Gemma 4 for the site's answers.** Tool choice with a small model is the likely weak spot; block 6 measures it on
   the same question set before the viewer depends on it.
