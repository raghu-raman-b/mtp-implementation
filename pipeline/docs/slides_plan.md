# Slide and figure plan: pipeline v3

For a talk on the pipeline. Each slide: what it shows, the formal content, and a prompt for Claude Design. Numbers are
from the MVP run of 2026-11-13 (VR course, NPTEL, 63 lectures).

## Framing

Each stage is a **verified mapping** f: X -> Y with a declared input type, output type and checks. Two kinds:

- **Model stages** are small agents with one fixed pattern, **generate-verify-repair**: an LLM proposes y = G(x); code
  checks it, V(x, y) = set of problems; if the set is non-empty the problems are sent back and G proposes again (at
  most k times); the attempt with the fewest problems is kept and the rest are flagged unresolved. Stages 1a/1b, 2a,
  2b, 2c, 3b, 4a, 4b, 5.
- **Code stages** are deterministic transformers with integrity checks: 0a, 1c, 3a, 3c, 4c, 4d.
- **Question answering** is a tool-using agent: a policy chooses tools over the knowledge layer and must cite what they
  return.

Calling the code stages "agents" invites an objection; calling the model stages "agentic stages with verifiers" is
accurate.

## Global style prompt (prepend to every figure prompt)

> Academic paper figure, 16:9, white background. Flat vector style, thin black and dark-grey strokes (1.5 px), one
> accent colour only (dark blue #1F3B73) for the element being explained, light grey (#E6E6E6) fills for secondary
> boxes. Sans-serif font (Inter or Helvetica), labels in sentence case, math in italic serif (like LaTeX). No shadows,
> no gradients, no icons or clip art, no 3D. Generous whitespace, aligned to a grid, arrows with small solid heads.
> Every box is labelled; no decorative elements. Legible when projected.

## Notation (slide 3 and the backup slide)

| Object | Definition | In the MVP |
|---|---|---|
| Course | a sequence of lectures L = (l_1, ..., l_63) | 63 lectures |
| Sentence | s = (text, t_start, t_end); lecture l has S_l = (s_1, ..., s_n) | 11,893 sentences |
| Segment | sigma = (S_l[a..b], g): a contiguous block of sentences with a sub-goal g; the segments of l partition S_l in order | 386 segments |
| Fact | f = (text, E_f), evidence E_f a non-empty subset of the sentences of one segment | 2,006 facts |
| Segment concept | c = (name, aliases A_c, facts F_c, defined in {0, 1}), F_c a subset of the segment's facts | 5,805 |
| Segment relation | r = (c_s, label, c_o, F_r), c_s != c_o concepts of the same segment, F_r facts that state it | 7,502 |
| Concept | kappa = an equivalence class of segment concepts under "same thing" (same name, or judged the same); F_kappa = union of their facts | 3,384 |
| Relation | the image of r under pi: c -> kappa, self-loops dropped, identical triples joined | 7,479 |
| Objective / goals | objective o = (goal, achieves, a run of consecutive segments); lecture goal; course goals G | 127 objectives, 7 course goals |
| Lecture graph | an edge K -> L iff K < L and L uses a concept K defines; direct edges = transitive reduction of the weighted edges | a DAG over 63 lectures |
| Activity | a = (kind, data, F_a) answerable from its facts F_a | 10 kinds |
| Answer | answer(q) = (text, citations), citations a subset of the facts the tools returned; every citation resolves to a lecture and a time | |

Invariant shown throughout: **everything traces down to sentences**, so every answer and activity can cite a lecture
and a time.

---

## Slides

### 1. Title
Content: title, one line ("From lecture videos to a grounded learning companion"), author, date. No figure.

### 2. Problem and goal
Content: input = lecture videos with human-written transcripts; output = a knowledge layer that serves two uses,
answering learners' questions and generating activities; "quality" = making those two uses more accurate.
**Figure 2: input -> layer -> two uses.**
> [style] Three columns left to right. Left: a stack of three thin rectangles labelled "Lecture videos + transcripts
> (63 lectures)". Middle: one larger accent-blue rounded rectangle labelled "Knowledge layer" with four small grey rows
> inside: "facts", "concepts and relations", "goals", "lecture graph". Right: two grey boxes stacked: "Question
> answering (cites lecture and time)" and "Activities and games". Arrows left to middle, middle to both right boxes.

### 3. Data model
Content: the notation table (simplified to the five core objects), the invariant.
**Figure 3: nested containment.**
> [style] A horizontal timeline bar labelled "Lecture l" divided into consecutive blocks labelled sigma_1, sigma_2,
> sigma_3 (segments); under sigma_2 a magnified strip of small ticks labelled s_i (sentences, each with a time). Above
> sigma_2, three small rounded boxes "f_1, f_2, f_3" (facts) with thin lines down to the sentences they cite (evidence).
> Above the facts, circles "c" (concepts) linked to the facts they name, and one labelled arrow between two circles
> (a relation triple). Accent blue only on one fact and its evidence lines. Caption-style label: "every object points
> down to sentences".

### 4. System overview
Content: all stages as a DAG with their artifact types; model stages marked.
**Figure 4: pipeline DAG.**
> [style] A left-to-right flow of 11 boxes in two rows, each labelled with its stage id and name and, under it in small
> italic, its output type: "0a Preprocess: S_l", "1 Segment: sigma", "2a Facts: f", "2b Judge (measured)", "2c Concepts
> and relations: c, r", "3 Registry: kappa", "4a Definitions", "4b Goals: o, G", "4c Lecture graph", "4d Knowledge
> layer", "5 Activities". Model stages drawn with a small circular arrow at the top-right corner (generate-verify-repair
> loop); code stages plain. A side branch from "4d" to a box "Question-answering agent". 2b drawn with a dashed outline
> and a note "skipped in the MVP (see slide 9)". Accent blue on the arrows of the main path.

### 5. The stage pattern: generate-verify-repair
Content: the loop; what V checks (schema, references, domain rules); best attempt kept; nothing silently dropped
(unresolved is logged); answers cached by request hash, so reruns are free and reproducible.
**Figure 5: the loop.**
> [style] Centre: box "G: LLM (proposes y)". Right: box "V: code checks -> problems". Arrow G -> V labelled "y". From
> V, two exits: down-right "no problems -> output", and a curved arrow back to G labelled "problems shown, retry (<= k)".
> Bottom: a small grey box "after k: keep the attempt with the fewest problems, flag unresolved". Left: input x into G.
> A thin grey cylinder under G labelled "cache: hash(request) -> answer". Accent blue on the feedback arrow.

### 6. Stage 0a: from subtitles to timed sentences (code)
Content: f_0a: SRT cues -> S_l; sentence splitting across cue boundaries; times for sentences that start inside a cue
estimated from the cue edges (median error 0.2-0.6 s); 11,893 sentences.
**Figure 6: cues vs sentences.**
> [style] Two horizontal tracks against one time axis. Top track "subtitle cues": fixed-length grey rectangles. Bottom
> track "sentences s_i": variable-length accent-blue-outlined rectangles that cross cue boundaries. One sentence start
> inside a cue marked with a small triangle and the label "time estimated from the cue edges".

### 7. Stage 1: segmentation (model stage)
Content: f_1: S_l -> (sigma_1, ..., sigma_m), a partition into consecutive blocks with sub-goals; a sub-goal is a step
toward the course goals; structural checks (starts at 1, increasing, in range) and logical checks (too short / too long)
with retries; 386 segments; agreement between two models (Gemma 12B vs Qwen 27B) boundary F1 0.76, the same as between
seeds of one model (0.75).
**Figure 7: segmentation.**
> [style] Top: a long thin bar of sentence ticks "S_l = (s_1 ... s_n)". Below: the same bar cut into four blocks,
> each with a short label above it ("g_1: explain extended reality", ...). Right: a mini version of the generate-verify-
> repair loop with two check boxes "structural" and "logical". Bottom right: a small table "boundary F1: model vs
> model 0.76, seed vs seed 0.75".

### 8. Stage 2a: facts (model stage)
Content: f_2a: sigma -> {f}; a fact is one complete point of subject knowledge the segment teaches; eight properties
(significant, whole, established, grounded, self-contained, terms in full, on the subject, faithful); evidence as
local sentence numbers mapped back in code; 2,006 facts.
**Figure 8: facts with evidence.**
> [style] Left: a numbered list of 8 short sentence lines "[1] ... [8]". Right: three fact boxes. Thin connector lines
> from each fact to the sentence numbers it cites (fact 1 -> [2],[3]; fact 2 -> [5]; fact 3 -> [6],[7]). Under the facts,
> a compact grey legend listing the eight properties in two columns. Accent blue on one fact and its connectors.

### 9. Stage 2b: the fact judge, measured (model stage) - a negative result worth showing
Content: a judge model checks each fact against the eight properties, failures are rewritten. Measured against gold
labels, seeded errors and repeated runs: seeded (blatant) errors caught 94%; real (subtle) failures in gold caught
1 of 7; verdicts flip 15% between seeds; of the 8 facts 2b acted on, 7 were good. Decision: the MVP keeps the
extracted facts; the judge is redesigned (procedure-based prompt) before it returns.
**Figure 9: the judge study.**
> [style] Left half: the judge-rewrite loop as two boxes "Judge (per fact: pass/fail + reason)" -> "Rewrite (only the
> failed facts)". Right half: a minimal horizontal bar chart, grey bars with one accent bar, three rows: "seeded
> errors caught 94%", "real failures caught 14%", "verdict flips across seeds 15%". A thin vertical dashed line at 90%
> labelled "target". No gridlines except the target line.

### 10. Stage 2c: concepts and relations per segment (model stage, two turns)
Content: turn 1: facts -> segment concepts c (name always the full term; acronyms only as aliases); turn 2: the
checked concept list -> triples (c_s, label, c_o) with the schema limiting ends to the segment's concept names; checks
retried (acronym name, unwritten alias, vague label, self-loop, duplicate) or reported; 5,805 concepts, 7,502 triples,
no unresolved answers.
**Figure 10: from facts to a small graph.**
> [style] Three panels left to right. Panel 1 "facts": three short text boxes. Panel 2 "concepts (turn 1)": four
> labelled circles ("virtual reality system", "artificial environment", "sensory experience", "user interaction"),
> thin dotted lines back to the facts that name them. Panel 3 "relations (turn 2)": the same circles connected by
> labelled arrows ("has as a defining characteristic"). Accent blue on one arrow and the fact it cites.

### 11. Stage 3: the concept registry (code + model)
Content: kappa = equivalence classes of segment concepts. Step 1 exact merge (case, plural, hyphen); step 2 embedding
candidates (Qwen3-Embedding-0.6B) and clusters; step 3 the model decides same or different per cluster; step 4 merge
and rebuild the relations through pi: c -> kappa (self-loops dropped and logged). MVP: steps 1, 2, 4 (5,805 -> 3,384
concepts; 2,421 exact merges); step 3 (425 clusters) deferred.
**Figure 11: the merge funnel.**
> [style] A left-to-right funnel of four vertical bars with numbers on top: "5,805 segment concepts" -> "3,384 after
> exact merge" -> "425 candidate clusters" -> "concepts kappa". Under the funnel, a small example: three circles
> "headset", "head-mounted display", "HMD (alias)" joined by a dashed bracket labelled "same thing? (model, step 3)".
> Accent blue on the bracket.

### 12. Stage 4: definitions, goals, lecture graph
Content: 4a definitions from each concept's facts (defining facts first); 4b goal hierarchy course goal -> lecture goal
-> objective -> segment sub-goal -> facts (7 course goals, 127 objectives); 4c lecture graph: K -> L iff K < L and L
uses a concept K defines; concepts used by most lectures weigh less (so not everything depends on lecture 1); direct
prerequisites = transitive reduction.
**Figure 12a: the goal tree.**
> [style] A top-down tree: root "course goal G" -> two children "lecture goal" -> each with two "objective o" -> each
> with segment boxes "sigma (sub-goal)" -> leaves "facts". Thin grey edges, accent blue on one root-to-leaf path.

**Figure 12b: the lecture graph.**
> [style] Seven numbered circles (lectures) left to right in course order. Solid accent-blue arrows for direct
> prerequisites, thin dashed grey arrows for edges implied through another lecture. One arrow labelled with the concepts
> it carries ("tracking, registration"). A small note: "hub concepts down-weighted".

### 13. The knowledge layer (4d, code)
Content: one folder, checked against a schema: name index (every name, alias and acronym -> concept), a card per
concept, the fact store with embeddings and times, per-lecture files, the goal tree, the lecture graph, assumed
knowledge; integrity: 208,243 references checked, none broken.
**Figure 13: layer schema.**
> [style] A neat grid of eight small labelled boxes (files): "names", "concepts (cards)", "relations", "facts +
> embeddings", "lectures", "goals", "lecture graph", "assumed". Thin reference arrows between them (concept -> facts,
> relation -> concepts, lecture -> segments -> sentences). One accent-blue box "every reference checked: 208,243, 0
> broken".

### 14. Stage 5: activities (model + code)
Content: a = (kind, data, F_a), answerable from its facts. Ten kinds and how each is made: quiz, open question, odd
one out, put in order (Qwen 27B); recap, crossword clues (Gemma 4 12B, local); concept map, complete the map, match
pairs, crossword layout, recall before a lecture, spaced review (code). Checks with retry (answer index, duplicate
options, a clue that gives the answer away, cited facts out of range).
**Figure 14: knowledge -> activities matrix.**
> [style] A table-like figure: rows = activity kinds (10), columns = "built from" (facts, concepts, relations, lecture
> graph) with filled grey dots, and a last column "made by" with three text labels "code", "Gemma 12B", "Qwen 27B".
> Accent blue only on the "made by" header. No borders except a thin rule under the header.

### 15. The question-answering agent
Content: policy = Gemma 4 12B with tools check_concept (name index -> card), fact_lookup (rephrased queries,
embedding search over facts), lecture_dependencies, lecture_overview, course_goals; answers only from tool results,
every claim cited, citations resolved to lecture and time; ids not returned by a tool are dropped; refuses what the
course does not cover.
**Figure 15: the tool loop.**
> [style] Left: a speech box "question q". Centre: box "Agent (Gemma 4 12B)". Right: a column of five small tool boxes
> with their names. Arrows centre -> tools labelled "call", tools -> centre labelled "facts with ids". Bottom: box
> "answer with citations -> (lecture 4, 6:01)". A small grey side box: "ids not returned by a tool are dropped".
> Accent blue on the citation arrow.

### 16. Live demo
Content: the viewer (see `pipeline/continue/DEMO_PLAN.md`). Screenshot slide or switch to the browser.

### 17. Engineering: making it run in a day
Content: compute split (Qwen 27B on one cloud GPU; Gemma 12B and embeddings on a desktop); a job queue on the cloud
GPU and a local orchestrator; every answer cached by request hash (resumable, reproducible); outputs copied home and
committed after each stage (spot instance).
**Figure 17: compute split.**
> [style] Two large rounded rectangles side by side: "Cloud GPU (L40S): Qwen 27B - segmentation, facts, concepts,
> goals, complex activities" and "Desktop (RTX 5070, CPU): Gemma 12B - simple activities, question answering;
> embeddings". Between them two arrows labelled "inputs" and "outputs (copied home after every stage)". Under both, a
> thin grey bar "request-hash cache: reruns cost nothing".

### 18. Results and limitations
Content: numbers table (lectures, segments, facts, concepts, relations, goals, activities); what is measured (judge
study, segmentation agreement); what is not yet (synonym merge, model definitions, activity judges, the QA question
set); next steps.
**Figure 18: numbers strip.**
> [style] A single row of seven number tiles, each a large number over a small label: "63 lectures", "386 segments",
> "2,006 facts", "3,384 concepts", "7,479 relations", "127 objectives", "10 activity kinds". Thin grey outlines, numbers
> in accent blue.

### Backup: formal definitions
The notation table above, full, as text.
