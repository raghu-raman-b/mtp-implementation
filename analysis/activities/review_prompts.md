# Activities: review of the prompts, the judge prompts, checks for O

F, 2026-11-15. Reviewed against the MVP outputs in `pipeline/output/nptel_vr/activities/` at commit fd91ee7
(quiz, open question, odd one out, put in order written by Qwen 3.8 27B; recap and crossword clues by Gemma 4 12B).

**Not tested on a model.** The revised prompts were only rendered through `s5_activities.py` on lecture 4 (every
placeholder fills, nothing is left over). No writer or judge call was made: that needs the EC2 and your go-ahead.
Every "should" below is a prediction until lectures 1, 4 and 16 have been rerun and read.

## What was read

| Kind | Read with the cited facts | Read without | Counted over all 63 lectures |
|---|---|---|---|
| quiz | lectures 3, 28, 57 (64 questions) | lectures 11, 47, 52, 63 | 1,443 questions |
| recap | lectures 5, 27, 41 (about 20 recaps) | | 347 recaps |
| put in order | 12 exercises (lectures 1, 16, 17, 30, 39, 41, 47, 59, 62) | all 76 | 76 exercises |
| odd one out | | all 176 puzzles | 176 puzzles |
| open question | lectures 1, 18, 33, 50, 60 (20 questions) | | 240 questions |
| crossword | 9 grids with their definitions (2, 13, 16, 21, 29, 30, 51, 58, 60) | | 608 clues |

Counts come from small scripts over the lecture files; the rules are the ones proposed as code checks below, so the
same counts can be taken again after the rerun.

## Files

| File | State |
|---|---|
| `pipeline/prompts/activity_quiz.txt`, `activity_recap.txt`, `activity_put_in_order.txt`, `activity_odd_one_out.txt`, `activity_open_question.txt`, `activity_crossword.txt` | Revised in place. Same `{placeholders}`, same answer fields in the same order, same counts: `s5_activities.py` needs no change to run them |
| `pipeline/prompts/activity_judge_<kind>.txt` (six files) | New. One judge prompt per model-made kind |
| `pipeline/prompts/activity_rewrite.txt` | New. The message sent to the writer with the judge's reasons (`{problems}`) |

Two things hold for all six writer prompts:
- Every example inside a rule is now from another subject. Two of the old rules quoted this course ("head-mounted
  display"), and the pipeline is meant to run on other courses.
- The model is told what the learner sees (for odd one out: four items and no hint; for the crossword: clue and letter
  count only). Most of the weak items come from writing for a reader who can see the facts.

## 1. Quiz

**Found.** Keys are right and the wrong options are mostly real neighbouring concepts (57/A6, 28/A1). The weakness is
form: a learner can often find the key without knowing the segment.

| Problem | Count (of 1,443 questions) | Examples |
|---|---|---|
| Correct option is the single longest | 751 (52%; chance is 25%). Longer than the longest wrong option by over 20% and 12 characters: 332 (23%). Longest in more than half of a quiz's questions: 161 of 347 quizzes | 18/A18 Q2, 48/A1 Q4, 6/A5 Q1, 38/A3 Q2. The correct option carries the fact's qualifications ("..., such as furniture in a scanned room or paint on a wall", 3/A3 Q2), the wrong ones are short |
| Wrong options made false with "only", "always", "never" (two or more of them, none in the correct option) | 155 (11%); 85 questions have an option starting with "Only" | 12/A1 Q4, 11/A16 Q3, 54/A3 Q2, 8/A7 Q2 |
| Only the correct option ends with a full stop | 44 | 28/A8 Q1 to Q5 (all five), 6/A3 Q1 and Q2, 25/A10 Q5 |
| Options are the combinations of two halves, or a mirror set | not counted (read) | 11/A1 Q2 and Q5, 11/A5 Q2, 57/A1 Q1 (more / fewer / same), 28/A4 Q4 and Q5 |
| A wrong option is also right | 1 in 64 read | 3/A3 Q2: "try cosmetic looks on a digital face" is also a product preview (fact 3/S1/F3, same segment) |
| The same statements rotate as key and wrong options through a quiz, so the learner answers by elimination | 19 questions by a strict rule; more by reading | 3/A3 Q1 to Q5, 24/A5 Q3 and Q4, 27/A3 Q1 and Q2 |
| Question, option or explanation speaks of the segment or the facts | 69 by a wide rule; 31 explanations by a narrow one | 2/A1 Q1 "The segment says that ...", 25/A8 Q4 "the facts say", 57/A12 Q1 "is identified as the fifth stage" |
| Not a full question (a sentence to complete) | 12 | 11/A9 Q4 and Q5 |
| Trivia or a repeat inside one quiz | read | 57/A12 Q1 (which stage is fifth), 47/A5 Q2 (a numeric range); 57/A10 has 3 questions on 2 facts, Q3 is Q1 plus Q2 |

**Changed.**
- The purpose line now says what a good question resists (longest option, striking out). The model was told the options
  should be "about the same length" before and did not act on it: it now gets an order of work (write the correct
  option first, as short as it can be; build each wrong option to its length; at least one wrong option as long or
  longer) and a last check before answering (cover the options; compare lengths; argue for each wrong option).
- "correct" is cut down: examples and side details go out, a needed detail moves into the question. This is the cause of
  the length problem, so it is fixed at the cause and not only by padding wrong options.
- Wrong options: wrong *for this question* (read each against all facts and the material; 3/A3 Q2), tempting, same
  shape and number of parts; no absolutes added to make an option false; at most one reversed copy of the key and no
  two-by-two sets.
- All four options end the same way, without a full stop. The question is a full question. The explanation is a
  statement about the subject.
- Fewer questions when the facts are few, and no passing the same statements around the quiz.
- A second example with a long answer whose wrong options are longer than the key. The old single example had a
  two-word key, which shows nothing about length.

## 2. Recap

**Found.** Faithful on the whole. The problems:

| Problem | Count (of 347) | Examples |
|---|---|---|
| The text is the points again, pasted together | 142 (41%) have half or more of their sentences copied from points; 119 add at most three new content words | 5/A2, 5/A4, 27/A2, 27/A4, 27/A6 |
| A point cannot be read alone | read | 41/A2 "The VR tour's design" (which tour), 41/A5 "24 specific information points" |
| Meaning shifted in rewording | 2 of 8 in the test report, more by reading | 27/A15 "focused on the fovea" (fact: pointed straight at an object); 41/A2 drops "if the tour is not carefully designed"; 27/A15 drops that peripheral vision gives no effective colour |
| Two points on one idea, or an important fact left out while an aside is kept | read; `facts_uncovered` 92 | 41/A5 points 4 and 5; 27/A10 leaves out the iris (27/S4/F2) |
| Figures copied into the text | read | 27/A13 ("4.3 times 10 to the power 14 hertz ...") |

"This course treats mixed reality and augmented reality as the same" (5/A6, 5/A8) is not a fault: it is a convention
the course sets, and the learner needs it. The prompt and the judge now say so.

**Changed.**
- The two parts get different jobs, said in the task line: points are what to remember; the text says what the segment
  explains as a whole and how the ideas connect. It may connect only as the facts, the sub-goal and the objective do.
- Points: one idea each and no idea twice; when there are more facts than points, join facts into one point rather than
  drop a needed one; each point names its subject in full, since it is read again when revising; keep hedges,
  conditions and both sides of a comparison; do not swap a term.
- The example now has four facts, three points (one joining two facts) and a text that is not the points.

**For you to confirm:** the text's new job is my reading of "a summary that joins the points into one explanation". If
you want the text to be a plain restatement, say so and I revert that bullet.

## 3. Put in order

**Found.** 76 exercises in 54 lectures. The good ones describe stages instead of naming them and come from facts that
state an order (36/A5, 16/A9, 28/A3, 13/A11, 18/A13, 54/A7). The weak ones:

| Problem | Count (of 76) | Examples |
|---|---|---|
| Not a sequence | read: at least 5 | 59/A5 (a limit, a design choice, its effect, a requirement); 30/A11 (three statements about HRTFs); 41/A3 and 41/A6 (a project's story turned into "stages"); 47/A9 (a list of "important stages") |
| Solvable without the lecture | read: about 10; 25 exercises have three steps | 38/A12 (started / executed / completed), 11/A11 and 14/A5 (input / process / output), 33/A3 and 38/A5 (design / implement or prototype / evaluate), 11/A18, 25/A7, 46/A9 |
| Two orders are right | read | 1/A6 (a continuum: either end first), 20/A11 (layers: top down or bottom up), 62/A9 (script and game object can be made in either order), 39/A19 (one event split in two steps) |
| The wording sorts the steps | 1 with years, 1 title | 33/A6 (areas with their years), 58/A3 ("the first four stages") |
| No cited fact has an order word | 23 | 62/A9, 61/A5, 33/A3, 1/A6, 11/A11 |

**Changed.**
- An order must be *stated* by the facts (order words, numbered stages, dates), never taken from the order of a list.
  A test the model can run: can two neighbouring steps be swapped without contradicting a fact?
- A list of what is not a sequence, taken from the failures above (kinds and parts; problem, cause, solution, effect; a
  project's doings without stated order; choices in any order).
- No exercise solvable from the wording; four or more steps preferred, three only when the order is a point the lecture
  makes. A scale or a stack needs its starting end in the title.
- Steps: describe the stage where the facts say what it does; one moment per step; no dates or years.
- A second example whose right answer is the empty list. The old prompt had only a positive example, which pulls
  towards always writing one.

## 4. Odd one out

**Found.** 176 puzzles. Most are real near misses (26/A18, 36/A15, 31/A14, 46/A16, 56/A29). About a quarter have one of
these problems:

| Problem | Count (of 176) | Examples |
|---|---|---|
| The odd item is of another sort: the group's own name, the whole, a measure of the three | read: about 12 | 1/A15 #1 (extended reality), 24/A16 #2 (usability), 24/A16 #3 (user-centered design), 23/A16 #1 (error message), 30/A16 #2 (direction), 10/A19 #3 (severity), 28/A14 #1 (axis), 58/A21 #2 (line) |
| The group is only things mentioned together; the odd item is "not in the list" | read: about 12 | 6/A20 #3 (features of the Sensorama), 7/A19 #1 (universities), 15/A16 #2 (battery), 20/A19 #1 (SDKs usable with one headset), 2/A9 #3, 50/A16 #1 to #3, 59/A14 #1 |
| Another item can be defended | read: about 8 | 29/A12 #2 and #3 (volume and frequency: each puzzle contradicts the other), 2/A9 #1 and #2 (helmet or headset; glove or controller), 7/A19 #3, 51/A22 #2 ("Model"), 4/A11 #2 and #3 (same items, different odd one) |
| The form gives it away: three items share a word the odd one lacks | 28 (16%) | 9/A16 #2 (three "... fidelity"), 34/A16 #3 (three "two-dimensional ..."), 30/A16 #1, 11/A23 #2 (three "... subscale"), 7/A19 #1 (three universities) |
| The reason speaks of the facts or of what "is listed" | 24 | 50/A16 #1 "The facts state that ...", 15/A16 #2 "are listed as" |
| Capitals differ between items or between lectures | 7 puzzles mixed; lectures differ | 1/A15 (lower case), 2/A9 (capitals) |

**Changed.**
- The task line says that the learner gets no hint, so the three members must bring the group to mind by themselves.
  The old prompt did not say what the learner sees.
- Group: one that a fact names as a group of the subject, not things mentioned together; absence from a list does not
  place an item outside.
- Odd item: same sort and level, with a fact that says what it is instead; a list of what it must never be.
- One answer: try another grouping; do not reuse four items with another odd one; if another choice can be defended,
  drop the puzzle.
- Form: same kind of phrase, capital first letter, and the shared-word rule.
- Reason as a statement about the subject.

## 5. Open question

**Found.** Reference answers are supported by their facts (as the test report found). The problems are in what is
asked and in how the answer is built:

| Problem | Count (of 240) | Examples |
|---|---|---|
| Two questions joined by "and" | 81 (34%) | 1/A16 Q1 and Q3, 18/A27 Q1, 33/A16 Q1 and Q2 |
| The reference answer sets facts side by side and never states the link asked for | read: 3 of 20 | 18/A27 Q2 (never says how hybrid tracking helps), 1/A16 Q1 (answers in another order than asked), 1/A16 Q2 |
| Forced link to an early lecture | read: 3 of 20; 64 questions use an earlier fact | 18/A27 Q4, 60/A15 Q4 (a settings tab and the continuum), 1/A16 Q2 |
| Always the maximum | 51 of 63 lectures have four questions; the fourth is often the forced one | 18/A27, 60/A15 |
| Asks for figures | read | 1/A16 Q4 (market size) |
| Long reference answers | 44 over 90 words; longest 133 (the prompt asked for two to four sentences) | 50/A17 Q1 |
| Odd presupposition | read | 1/A16 Q2 "Why can a headset ... be understood as an example of immersive technology?", 18/A27 Q3 |
| Speaks of the video, the course, "according to" | 9 | 54/A20 Q4, 55/A21 Q2 |

The old prompt said "prefer questions that use ... an earlier lecture's facts", and the model obeyed in every lecture.

**Changed.**
- Earlier lectures only when the lecture really builds on them; a forced tie is named as a fault.
- Ask "why" or "how" only when the facts give the reason or the way.
- One thread per question; no odd presupposition; the question does not contain its answer.
- Reference answer: the direct answer first, then the support; every part answered; about eighty words at most.
- Stay at the lower count unless the lecture has material for more.
- The example's reference answer now starts with the direct answer.

## 6. Crossword clues

**Found.** Much of the damage is the data (a "definition" that is the concept's first fact); that part goes away with
real definitions. What the prompt can fix:

| Problem | Count (of 608 clues) | Examples |
|---|---|---|
| The clue gives a place in a list or "one of the ..." | 50 (8%) | 16/A13 (four clues "The second of the four steps"), 13/A19 DISPLAY and COMPUTER ("listed first / last in the sequence"), 2/A8 EDUCATION, DEFENSE ("about 4%") |
| Two answers of one grid have the same clue | 17 clues in 4 grids | 29/A11 (inner, middle, outer ear), 17/A13, 15/A15, 62/A24; nearly the same: 60/A13 SCENEVIEW and GAMEVIEW |
| The clue describes another thing that the text is about | read | 51/A21 SHORTESTPATH (the travelling salesman tour), 60/A13 UNITYPREFAB (an asset), 29/A11 AUDIORECORDING |
| The clue points at something it does not name | 9 by rule, more by reading | 58/A20 DELTAY ("their y coordinates"), 60/A13 ("the standalone application", "the software") |
| Not a phrase that can stand for the answer | read | 2/A8 IMMERSION ("When a user's senses are blocked ..."), 29/A11 RECEIVERPART |
| Ends with a full stop in some grids and not in others | 332 with, 276 without | 2/A8 against 16/A13 |
| Masked by code | 5 | 21/A11 ("graphics" for SCENEGRAPH), 29/A11 ("user" for PRESENCE), 13/A19, 51/A21, 58/A20 |

**Changed.**
- A clue says what the concept is or does; not a place in a list and not a figure. When the text only lists the
  answer, the clue says what the list is of and what sets this member apart, from the plain meaning of its name. This
  is the one place where the model may go beyond the text, and only as far as the name's own words: without it, three
  ear parts or four steps can only get the same clue. **Yours to overrule.**
- When the text is about another thing, use only what it says of the answer.
- Read each clue against every other answer; no two clues that could be swapped.
- Stands alone (name the setting, no pointing words); a phrase that can stand for the answer; at most fifteen words; no
  full stop.
- The word rule now also names longer words built on an answer word, because the code check rejects them
  ("graphics" for "graph"); before, the model was failed for a rule it had not been given.
- The example has two answers, one of them with a text about the other.

## 7. Code checks for O

"Retry" means: returned by the kind's `*_problems` function, so the text is shown to the model. Two classes:
- **hard**: as now, an item that still has the problem after the last attempt is dropped;
- **soft**: retried, but an item that still has the problem is **kept and flagged** in `checks.json`. The judge then
  decides. This needs a small change in the `*_convert` functions, which now drop every item with any problem. Without
  it, the length rule alone could drop a fifth of the questions.

"MVP" is how many items of the MVP run the rule catches.

### All kinds

| Check | Class | Rule | Feedback |
|---|---|---|---|
| `source_talk` | soft | In learner-facing text (quiz: question, options, explanation; recap: points, text; put in order: title, steps; odd one out: reason; open question: question, reference answer; crossword: clue), case ignored: `\b(the\|this) (segment\|lecture\|lecturer\|instructor\|video\|transcript)\b`, `\bthe facts? (state\|say\|place\|show\|list)s?\b`, `\baccording to the (lecture\|segment\|facts)\b`, `\bas we (saw\|discussed)\b`, `\bis (listed\|identified) as\b`. Not "this course" (a course convention is allowed) and not "is described as" (often legitimate; left to the judge) | `{where}: "{match}" speaks of the lecture or the facts. The learner never sees them: say it as a statement about the subject.` |

### Quiz

| Check | Class | Rule | MVP | Feedback |
|---|---|---|---|---|
| `correct_longest` (replaces the report-only flag) | soft | `len(correct) > 1.2 * max(len(w))` and `len(correct) - max(len(w)) >= 12` (characters) | 332 | `Question {i}: the correct option ({n} characters) is clearly longer than every wrong option (the longest has {m}). Cut it down to what the answer needs, or rewrite the wrong options to its length and shape: at least one wrong option must be as long as the correct one.` |
| `correct_longest_share` | soft, per quiz | the correct option is strictly the longest of the four in more than half of the quiz's questions | 161 quizzes | `In questions {list} the correct option is the longest of the four, so a learner can score by picking the longest. In at least {k} of them make one wrong option as long as the correct one or longer, or shorten the correct one.` (`k`: how many must change to get to half) |
| `absolute_wrong` | soft | two or more wrong options match `\b(only\|always\|never\|all\|none\|must\|cannot\|solely\|entirely)\b` and the correct one does not | about 155 | `Question {i}: the wrong options {list} are made false with "only", "always", "never" or the like, and the correct option has no such word. Replace them with options that are wrong in substance.` |
| `not_a_question` | hard | the question does not end with "?" | 12 | `Question {i}: write one full question that ends with a question mark, not a sentence to complete.` |
| `option_end` | no retry: code | strip one trailing "." from every option | 45 with mixed endings | none |
| `rotated_options` | report | two or more wrong options of a question match (content-word Jaccard at least 0.6, five words or more) the correct options of other questions of the quiz | 19 | none (the judge sees the whole quiz) |

Keep `correct_not_in_facts` as it is.

### Recap

| Check | Class | Rule | MVP | Feedback |
|---|---|---|---|---|
| `text_repeats_points` | soft | split the text into sentences; half or more of them match a point (word Jaccard at least 0.8) | 142 | `The text repeats the points almost word for word (its sentences {list}). The text has another job: say what the segment is about as a whole and how the points connect.` |
| `point_long` | soft | a point has more than 28 words | a few (longest 33) | `Point {i} has {n} words: one sentence of about twenty words at most, with one idea.` |
| `text_length` | soft | the text has fewer than 2 or more than 4 sentences, or more than 90 words | a few (longest 94) | `The text has {n} sentences and {m} words: write two to four sentences.` |
| `duplicate_points` | report | two points with content-word Jaccard at least 0.6 | 2 (one a false alarm: 1/A5) | none |

Keep `facts_uncovered` as a report.

### Put in order

| Check | Class | Rule | MVP | Feedback |
|---|---|---|---|---|
| `order_cue` (now a retry) | soft | as now (a step starting with "first", "then", "next", "finally", "lastly", "step" or a digit), plus a year anywhere in a step (`\b(1[5-9]\d\d\|20\d\d)\b`) or "previous step". Do not match "final" or "initial" anywhere: 36/A8 "final observer notes" and 41/A3 "Initial prototypes" would be false alarms | 1 (33/A6) | `Exercise {i}: the step "{step}" carries an order word or a year, which sorts it without understanding. Say what happens in the step without it.` |
| `title_cue` | report | the title has "first", "last" or a number | 1 (58/A3) | none |
| `no_order_word` | report | no cited fact matches `\b(first\|then\|after\|before\|next\|follow\w*\|order\|steps?\|stages?\|sequence\|finally\|subsequently\|once\|pipeline\|phases?\|until\|later)\b` | 23 | none (these are the exercises to read first) |
| `three_steps` | report | exactly three steps | 25 | none |

### Odd one out

| Check | Class | Rule | MVP | Feedback |
|---|---|---|---|---|
| `shared_word` | soft | a word of four letters or more (not a stop word) that all three group items contain and the odd item does not | 28 | `Puzzle {i}: the three group items all contain "{word}" and the odd item does not, so its form gives it away. Choose an odd item that carries the word too, or use another group.` |
| `length_tell` | soft | the odd item is over 1.5 times the longest group item or under half the shortest, and differs by 8 characters or more | 6 | `Puzzle {i}: the odd item is much {longer\|shorter} than the three others. Write the four items alike.` |
| `same_items` | hard, the later puzzle | two puzzles of the lecture share three or four items | 2 lectures (1/A15, 4/A11) | `Puzzles {i} and {j} show the same items with a different odd one. Use another group for puzzle {j}.` |
| `capitals` | no retry: code | capitalise the first letter of every item | 7 mixed | none |

Keep `not_a_concept` as a report.

### Open question

| Check | Class | Rule | MVP | Feedback |
|---|---|---|---|---|
| `two_questions` | soft | more than one "?" in the question, or `,? and (how\|why\|what\|which\|when\|where)\b` | 81 | `Question {i} asks two things ("... and {word} ..."). Ask one of them.` |
| `reference_long` | soft | the reference answer has more than 100 words or more than 4 sentences | about 30 | `Question {i}: the reference answer has {n} words. Give the direct answer first and the support after it, in two to four sentences of about eighty words in all.` |
| `key_fact_unused` | report | a key fact shares fewer than three content words with the reference answer | not counted | none |

Keep `no_earlier_or_relation` as a report (the prompt no longer pushes earlier lectures, so expect more of it; that is
not a fault by itself).

### Crossword

| Check | Class | Rule | MVP | Feedback |
|---|---|---|---|---|
| `clue_same` | hard | two answers with the same clue (normalised) | 17 clues, 4 grids | `Answers {i} and {j} have the same clue. Give each the detail that tells it apart from the other.` |
| `clue_list_place` | soft | `\bone of (the )?(\w+ )?(two\|three\|four\|five\|six\|seven\|eight\|\d+)\b`, `\b(first\|second\|third\|fourth\|fifth\|sixth\|last) (of\|in) the\b`, `\blisted (first\|last)\b` | about 50 | `Clue {i}: "{match}" only says where the answer stands in a list. Say what the thing is or does.` |
| `clue_points` | report | the clue has "their", "these", "those" or "the above" | 9 (some are fine: the clue names what "their" refers to) | none |
| `clue_end` | no retry: code | strip one trailing "." | 332 | none |
| clue length | fix | `CLUE_MAX_WORDS` is 20, the prompt and the feedback text say fifteen. Set it to 15 (6 MVP clues are over) | | as now |
| masking | fix | `same_word` counts any word that *starts with* an answer word of four letters as a form of it, and `ctx["words"]` holds every word of every alias. Keep that wide rule for the **check** (the prompt now states it). For the final **masking**, mask only the answer's own name and its plain forms (plural, "-ed", "-ing"), not alias words such as "user" and not longer words such as "graphics". A masked clue goes to the judge like any other (criterion `readable`) | 2 of the 5 masked clues were over-masked | none |

### Code-made kinds (no prompt; seen while reading)

- `complete_map`: allow one blank per pair of concepts. 5/A10 blanks edges 21 and 24, both mixed reality to augmented
  reality, and each answer fits the other blank. Also leave out a label as an option when it is a prefix of the answer
  or the reverse (37/A12 "is for" beside "is for covering a"), and prefer blanks whose answer is no longer than its
  options (12/A13).
- `match_pairs`: with real definitions most of this goes away. Until then: skip a right side that still has "___"
  inside it (the name was not at the head of the sentence, so the sentence is not a definition: 30/A14, 61/A17), skip
  one cut with "…", and skip a right side that shares 70% of its words with one already taken (twin rows).

## 8. How the judge plugs in

**One call per unit**, the same units as the writer: a segment's quiz, a segment's recap, a lecture's exercises,
puzzles, questions or clues. The judge sees what the writer saw, with the same fact numbers, plus the items as they
came out of `*_convert` (after the code checks and normalisations), so its reasons can name fact numbers the writer
understands.

| Judge prompt | Placeholders (the same blocks as the writer unless said) | How to render the items |
|---|---|---|
| `activity_judge_quiz.txt` | `course`, `lecture_title`, `subgoal`, `facts`, `related`, `questions` | Per question: `Question 2 (cites facts 3, 5)`, the question, the options as `A.` to `D.` **in the shuffled order the learner sees**, `Marked correct: C`, `Explanation: ...` |
| `activity_judge_recap.txt` | `course`, `lecture_title`, `subgoal`, `objective`, `facts`, `recap` | `Point 1 (cites facts 1, 2): ...` per point, then `Text: ...` |
| `activity_judge_put_in_order.txt` | `course`, `lecture_title`, `facts`, `exercises` | `Exercise 1 (cites facts 12, 13)`, `Title: ...`, then the steps numbered in the correct order |
| `activity_judge_odd_one_out.txt` | `course`, `lecture_title`, `concepts`, `relations`, `facts`, `puzzles` | `Puzzle 1 (cites facts 4, 9)`, the four items in the shuffled order, `Marked as odd: ...`, `Reason: ...` |
| `activity_judge_open_question.txt` | `course`, `lecture_title`, `goal`, `facts`, `relations`, `questions` | `Question 1 (key facts 2, 5, 31)`, `Question: ...`, `Reference answer: ...` |
| `activity_judge_crossword.txt` | `course`, `lecture_title`, `answers`, `clues` | `[3] scene graph (5,5): <clue>` per entry, the clue without the appended letter count |

**The answer**, the same for all six: `{"verdicts": [{"item", "check", "reason", "failed", "pass"}]}`, one verdict per
item in order. `item` is the item's number (recap: the point's number, and 0 for the text). `check` is a short piece of
work the judge must do before deciding (quiz: the letters of all options the facts make correct, found before reading
the key; put in order: the least fixed pair of steps; odd one out: the group and any other defensible item; open
question: the direct answer in one sentence; crossword: other answers the clue fits; recap: the words changed in
meaning). `failed` holds criterion names, from a list fixed per kind (use a schema `enum`):

| Kind | Criteria |
|---|---|
| quiz | `answerable`, `one_answer`, `no_giveaway`, `worth_asking`, `clear`, `no_source_talk` |
| recap | `supported`, `faithful`, `stands_alone`, `clear`, `no_source_talk`; points also `one_idea`; the text also `summary`, `coverage` |
| put in order | `in_facts`, `real_sequence`, `one_order`, `no_giveaway`, `worth_doing`, `clear`, `no_source_talk` |
| odd one out | `in_facts`, `real_group`, `near_miss`, `one_answer`, `no_giveaway`, `clear`, `no_source_talk` |
| open question | `answerable`, `answers_question`, `open`, `one_thread`, `no_giveaway`, `clear`, `no_source_talk` |
| crossword | `from_text`, `leads_to_answer`, `unique`, `no_giveaway`, `readable`, `no_source_talk` |

Code checks on the judge's answer (retry with feedback, as for the fact judge): one verdict per item and none twice;
`pass` is true exactly when `failed` is empty; a failed verdict has a reason.

Each prompt tells the judge which way to lean when in doubt: fail on the criteria where a learner would be taught
something wrong or arguable (answerable, one answer, the order, the group), pass on the criteria of form.

**On a fail** (proposal; the choice is yours, see the questions):

1. One rewrite round. The writer gets `activity_rewrite.txt` as the next turn of the same conversation (the way the
   code checks give feedback), with `{problems}` one line per failed item: `Question 2 (one_answer): <the judge's
   reason>`. It answers with the full JSON; passed items stay as they were.
2. The code checks run again, then the judge once more, on the rewritten unit.
3. What still fails:

| Kind | After the second fail |
|---|---|
| quiz, open question | drop the item; drop the activity when fewer than 2 questions are left |
| odd one out, put in order | drop the item; no activity when none is left (the contract allows it) |
| crossword | a clue cannot be dropped without changing the grid: keep it and flag it (`judge_failed`), or lay the grid out again without that answer. Your choice |
| recap | a point that fails on `supported` or `faithful`: drop it. A text that fails: keep and flag; the contract needs a text |

4. `checks.json` gets, per unit, the verdicts of both rounds, and in the totals: items judged, failed per criterion,
   rewritten, dropped by the judge. The Block 7 gate asks F to read the judge's failures and a sample of passes: I
   need the verdicts with their `check` and `reason` next to each item in `activities.txt`.

**The rerun need not wait for the judge.** The judge reads only finished activities and the layer, so it can be a
second pass (`--judge`) over the new run. Order of value for the next hours: the revised prompts (done), then the code
checks of section 7, then the judge.

**Before trusting the judge, measure it**, as Block 1 did for the fact judge (which caught 2 of 7 real failures and
flipped 15% of verdicts between runs). The MVP outputs at commit fd91ee7 give a seed set of known failures:

| Kind | Should fail, with the criterion |
|---|---|
| quiz | 3/A3 Q2 `one_answer`; 57/A1 Q1, 28/A4 Q4 and Q5, 11/A1 Q2 and Q5 `no_giveaway`; 57/A12 Q1 `worth_asking` and `no_source_talk`; 2/A1 Q1 `no_source_talk`; 11/A9 Q4 `clear`; 57/A10 Q3 `worth_asking` (repeats Q1 and Q2) |
| recap | 27/A15 point 2 `faithful`; 41/A2 point 2 `faithful`, point 1 `stands_alone`; 41/A5 point 5 `one_idea`; 5/A2 text `summary` |
| put in order | 59/A5 and 30/A11 `real_sequence`; 1/A6 and 20/A11 `one_order`; 38/A12 and 11/A11 `worth_doing`; 33/A6 `no_giveaway`; 39/A19 `one_order` |
| odd one out | 15/A16 #2 `in_facts` or `real_group`; 29/A12 #2 and #3 `one_answer`; 24/A16 #2 and 1/A15 #1 `near_miss`; 9/A16 #2 and 34/A16 #3 `no_giveaway`; 50/A16 #1 `no_source_talk`; 4/A11 #3 `one_answer` |
| open question | 18/A27 Q2 `answers_question`; 18/A27 Q4 and 60/A15 Q4 `open`; 1/A16 Q1 `one_thread`; 1/A16 Q4 `open` |
| crossword | 51/A21 SHORTESTPATH and 60/A13 UNITYPREFAB `from_text`; 29/A11 the three ear parts `unique`; 16/A13 the four steps `leads_to_answer`; 58/A20 DELTAY `readable`; 21/A11 SCENEGRAPH `readable` (masked) |

and of passes the judge must not fail: quiz 9/A6, 30/A9, 17/A3; recap 9/A7, 18/A8; put in order 36/A5, 28/A3; odd one
out 26/A18, 36/A15; open question 24/A17, 42/A22; crossword 30/A15, 36/A14 (the showcase picks). Run the judge three
times on these and report catches, false alarms and flips before it is allowed to drop anything.

## 9. Open questions for you

1. **Judge model.** PLAN section 1 gives judging to Sage-A1.5 (port 8095). Is that still so for activities, or does
   Qwen judge its own writing in this run? A second model is the safer judge.
2. **On a fail:** one rewrite round and then drop, as proposed? Or drop at once, or only flag?
3. **Crossword clue that still fails:** keep and flag, or lay the grid out again without the answer? And for a recap
   text that still fails: keep and flag?
4. **Soft checks:** may an item that still breaks a soft rule after the retries be kept and flagged (proposed), where
   now every item with a problem is dropped?
5. **Odd one out shows no hint of the group.** Several contestable puzzles would be fine with a hint ("Which is not a
   part of ...?"), but that is a new field, so a design change. Keep without a hint?
6. **Crossword, a text that only lists the answer:** the prompt now lets the clue use the plain meaning of the answer's
   name. Accept, or should such answers be kept out of the grid (a change to how answers are chosen)?
7. **Put in order with three steps:** the prompt now discourages them; the schema still allows three. Raise the
   minimum to four?
8. **The recap text's job** (section 2): connect the points, as now written, or restate them?
9. **Small first:** rule 1 of the plan says lectures 1, 4 and 16 before the full course. I recommend that for these
   prompts too, since they have not met a model: about 40 calls, then the counts of section 7 before and after.
