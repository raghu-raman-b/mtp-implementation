# Fable's review of the user's decisions (2026-11-13)

The user answered on 2026-11-12/13: D8 "Concepts can never be acronyms; the canonical name must always be the full
name. Only aliases can be acronyms." D9 "Yes that works (test options)." D12 "Yes, retry them. Check all outputs. The
quality is important!" D11 "All links are directed, so keep that in mind." D13 "Check with Fable agent." And: "Ensure
to check all decisions with Fable." This is the F role's review (a Fable agent, read-only), kept here verbatim in
substance so a new session can act on it. Status of each item: `pipeline/continue/PROMPT.md`.

## DECISIONS

### D8 (acronyms)
Reading: the name is the full term in words, including an acronym inside a longer name ("VR headset" -> "virtual
reality headset"). Acronyms live only in aliases. The 2c trial already behaves this way.
1. `is_acronym` as first proposed ("two or more capitals") also matches HoloLens, OpenXR, SteamVR, PlayStation,
   YouTube, OpenGL, JavaScript, McGurk, Wi-Fi, DisplayPort and single letters. In the 2,006 facts: ARToolKit 13,
   HoloLens 10, OpenGL 7, PlayStation 4, Direct3D 3, WebGL 3. Use: a token is an acronym when it has at least two
   capitals, or a digit plus a capital, and no run of two or more lower-case letters (keeps VR, HMD, FoV, DoF, LiDAR,
   IMUs, 3D, 6DoF). One shared helper for 2b (`fact_checks.py`), 2c, 3a, 4d; today 2b's CAPS/_is_acronym miss "3D".
2. Two tiers: `name_is_acronym` (the whole name is one acronym token): retry. `acronym_in_name` (an acronym token
   inside a longer name): report only (code cannot tell "VR headset" from "PlayStation VR").
3. A still-failing name must not cost the segment (see D12.1): keep the answer, list the name as unresolved.
4. About 89 of the 2,006 facts write an acronym they never expand (3D 17, GPU 8, FLAR 7, VR 6, SDK 3; HTC, NVIDIA,
   NASA, CAVE, IKEA, MP3, 4K). The model must then expand from its own knowledge; `name_not_in_facts` must report
   every such name for reading. 2b's `bare_acronym` matters more (only reported; the judge passes seeded E22).
5. Stage 3: limit the s3b group name to the entries' own names (2c's names, not aliases) that are not acronyms; fall
   back to non-acronym aliases only when every entry is named by an acronym. Keep the "acronym names never merge
   exactly" safeguard; the cap problem behind D8 goes away; the `cut` list stays.
6. 4a/4d: only the shared helper in 4d and one line in `concept_definition.txt`.
7. Change the wording of `concept_extraction.txt` and `concept_same.txt` (below). "3D" is an abbreviation: name
   "three-dimensional space", alias "3D space"; "three-dimensional" alone is an adjective, not a concept.

### D9 (embedding text)
Reading: use the other facts, decide by test.
1. Default `any-if-none` from now; keep `defining` as the comparison.
2. In the trial 100 of 129 segment concepts are not defined: this covers most entries.
3. `embed_compare.py` should also report per option: candidate pairs between entries of the same segment with
   identical fact sets (16/S0: anchor, pose, position, orientation, field of view, three-dimensional space all cite
   only F3); "different" gold pairs that become candidates; the largest cluster and the "same" pairs the cap cuts.
4. A third option `any`: fill every entry up to the same number (defining first, then others).
5. Record the option in `clusters.json` settings; the instruction says "names and facts" when other facts are used;
   compare with the same instruction on both options.

### D11 (links)
The answer states a constraint (links are directed, earlier to later; triples keep the fact's direction), which 4c
already follows; it does not choose between counting and leaving out `redefined` concepts. Keep the default (counted,
marked `redefined`) and ask the user again. Recommendation: keep counting (2c's `defined` over-fires, e.g. "immersive
experience" marked defined in 4/S1 from a hallmark sentence; a second definition is usually one restating sentence;
the mark keeps the other option derivable). Add to `graph.txt` the links whose concepts are all `redefined`.
Consequences of "directed": sharper rule 5 in `concept_relations.txt` (below; the trial has the same statement turned
round, 16/S1 R45/R46, R21/R23); the 2c `reverse` check stays report-only; 3c and 4d already keep direction.

### D12 (retries)
Reading: every model answer of every stage gets a code check and a retry, the retried answer is checked again; reading
by people (F) comes second. O reports.
1. Today a failed check throws the answer away (2c: `concepts: []`; 4a: empty definition; 4b: no goals). Required:
   keep the attempt with the fewest problems (ties: the latest), apply the code repairs, flag it `unresolved`. Only an
   unparseable answer is "no answer".
2. `appears` (2c) has a bug: all 8 `alias_not_written` hits and 5 of 9 `name_not_in_facts` hits in the trial are
   false. Apostrophes ("tracking the user's sense organs") and brackets ("three-dimensional (3D) space" matches neither
   "three-dimensional space" nor "3D space"; also "virtual reality (VR) system", "computer-aided design (CAD) system").
   Fix before any retry hangs on these checks.
3. 2c retry, turn 1: `out_of_range`, `name_is_acronym`, an empty name, `alias_not_written` (after the fix). Turn 2:
   `out_of_range`, `vague_label`, a triple from a concept to itself, an exact duplicate triple. Report only:
   `name_not_in_facts`, `alias_not_in_facts`, `fact_without_concept`, `acronym_in_name`, `merged`, `no_shared_fact`,
   `reverse`, `no_triple`. Turn 2 continues from the prompt and the accepted answer only.
4. 4a retry: `outside_list`, `empty_definition`, an empty `facts` list, a number in both `facts` and `misplaced`, the
   concept name absent from the definition, "the lecturer" or "this lecture" in the definition. Report:
   `defined_mismatch`, `misplaced`.
5. 4b lecture retry: `out_of_range`, `segment_twice`, `out_of_order`, an empty goal or achieves, `not_consecutive`
   (computed ignoring segments in no objective). Report: `in_no_objective`, with whether the segment defines concepts.
6. 4b course retry: `lecture_in_no_goal` (except lectures whose own call gave no answer). Fix in code: order and
   repeats. Report: a goal that lists more than half the lectures.
7. Log, per retried answer, what was lost and added between the first and the final attempt; count it in each report.
8. `FEEDBACK` in `llm/client.py`: "Your answer has these problems:\n{problems}\n\nAnswer again in the same format,
   fixing these problems and changing nothing else." Problem lines for 2c: `The name "{name}" is an acronym. A
   concept's name is always the full term in words; put "{name}" in its aliases. If your list already has this
   concept under its full name, join the two.` and `The alias "{alias}" of "{name}" is written in none of the facts.
   Remove it.`

## D13 (Fable's recommendation)
Revise the judge prompt first, add gate targets on real failures, leave the temperature, hold the majority of three in
reserve. Of 7 gold failures, 5 are missed in all four runs (1/S5/F0, 16/S2/F3, 16/S3/F0, 16/S0/F0, 16/S0/F1).
Majority of 2 of 3 over base/seed1/seed2: 0/7 caught, 3/55 false alarms; any of three: 2/7, 8/55. The rules are in
the prompt but not applied: add a HOW TO CHECK procedure and make the answer carry the comparison. 4/S1/F0 and
16/S3/F1 are list facts the extraction prompt asks for (a conflict between prompts). On gold the judge causes about 7
rewrites of good facts for 1 of a bad one. Method: the revision is made with the gold failures in view, so add a subtle
seeded set (~21 entries: hedge dropped, quantifier widened, referent swapped, recap restated, statement changed or made
true by definition, point split, acronym alone) and a held-out set (lectures 2 and 17, labelled blind; F writes both).

Proposed gate targets (pooled over three seeds, on the verdict as 2b applies it):
| # | Target | Now |
|---|---|---|
| 1 | Blatant seeded errors (34) caught >= 90%, no run below 85% | 92% pooled; lowest 88% |
| 2 | Clear gold failures (5) caught >= 60% (9 of 15 verdicts), at most one never caught | 2 of 15; three never |
| 3 | Subtle seeded errors caught >= 70%, no kind with zero | not measured |
| 4 | No property with zero catches, seeded and real separately; Faithful and Whole caught in every run | Faithful on gold 0, 1, 0 of 3 |
| 5 | False alarms <= 10% on the 55 gold-pass facts and <= 8% on the 50 clear ones | 13% and 10% |
| 6 | Flips <= 5% (3 of 62) | 15% |
| 7 | Held-out set: real failures caught >= 50%, false alarms <= 10% | not measured |
Target 5 needs D1 narrowed: `pointing` fails only a leading pronoun, "the lecturer", "the slide"; an inner "this" is
report only. Target 6 is the trigger for the majority of three. If target 2 or 3 is unmet after two revisions, back to
the user. `compare.py` should print the majority-of-three and any-of-three verdicts in every run.

## PROMPT FIXES (exact text)

### fact_judge.txt
Replace property 2:
```
2. Whole. It is one complete point, not one detail of a point. It fails if another fact in the list is about the same point (a definition split into what the thing is and what it is not; one list split member by member; one figure split from its year or source; several facts about one paper or person): name the other facts. It also fails if it holds different points that could be asked about separately (what a thing is, how it works, where it comes from), or if it reads as a summary of the segment. A fact that gives a list by naming its members (the kinds, parts, steps or characteristics of something) is one point and not a summary, even when other facts each describe one member. It fails if its cited sentences only repeat what was taught earlier ("as we saw", "we have seen", "to sum up") and the fact restates that; such a fact passes only when it holds just what the repeat adds.
```
Replace property 6:
```
6. Terms in full. Every term is written in full words. An acronym or abbreviation appears only in brackets after the full term ("extended reality (XR)"), and only if the lecturer uses it in the segment. A fact that writes an acronym or abbreviation without giving its full term fails, even when the lecturer uses the acronym alone ("2D" for "two-dimensional" counts too). Once a fact has given the full term with its acronym, the acronym alone later in the same fact is not a failure; neither is an acronym that is part of the name of a product or company. A missing acronym is not a failure.
```
Replace property 8:
```
8. Faithful. It says what the cited sentences say, no more strongly and no more widely. It adds nothing the lecturer did not say, even if it is true. It keeps every hedge ("may", "can", "usually", "in a broad sense") and every limit on who or what the statement holds for ("most", "some", "today", "for some people"): "can reduce" must not become "reduces", and "many systems" must not become "systems". It keeps the lecturer's point: a fact that turns the statement into a different one, or into one that is true whatever the lecturer said, fails. Where the lecturer said "this field" or "these technologies", the fact names what the lecturer meant in the lecture, not the nearest noun or a title mentioned nearby. If the lecturer corrects themselves, it keeps only the corrected version.
```
Insert before ANSWER:
```
HOW TO CHECK
Take the facts one at a time. For each fact, read its cited sentences again before you decide; do not judge it from your memory of the segment.
- Find every word in the cited sentences that hedges or limits the statement the fact makes (may, might, can, usually, often, sometimes, generally, most, many, some, about, today, so far, in a broad sense, for some people). Each one must be in the fact with the same strength.
- Find every pointing phrase in the cited sentences that the fact had to replace with a name ("this", "these", "it", "this field", "the area"). Check in the segment what the lecturer meant, and that the fact names that.
- See whether the cited sentences only repeat something taught earlier in this lecture or in an earlier one.
- Compare the fact with every other fact in the list for the same point.
A fact that fails one of these fails, however well it reads.
```
Replace ANSWER (needs user approval, question 4; changes the judge call's format, not 2b's output; O adds the schema
and a consistency check with retry: any `kept` or `named` false with `pass` true):
```
ANSWER
Answer with a JSON object with one field, "verdicts": a list with one entry per fact, in the order given, each with these fields in this order:
"fact": the fact's ID.
"hedges": a list with one entry for each hedging or limiting word of the cited sentences that bears on the fact: {"word": the word as the lecturer said it, "kept": true or false}. An empty list if there is none.
"refers": a list with one entry for each pointing phrase of the cited sentences that the fact replaced: {"phrase": the phrase, "means": what the lecturer meant, "named": true if the fact names that, false if it names something else}. An empty list if there is none.
"recap": true if the cited sentences only repeat what was taught earlier, otherwise false.
"reason": one or two sentences. If the fact fails, which properties it fails and why, with the IDs of the other facts or the numbers of the sentences involved. If it passes, what it teaches, in a few words; do not list the eight properties.
"pass": true or false. false whenever a hedge is not kept or a phrase is not named.
Answer with the JSON only.
```
Fallback if the format must not change: require the same three items inside "reason".

### concept_extraction.txt
Replace rule 4:
```
4. Name. Give the concept the name a textbook glossary would use: the full
   term in words, singular, lower case except for proper names, no article
   ("head-mounted display", not "HMDs" or "the headset"). The name is never
   an acronym or abbreviation and never contains one: "virtual reality
   headset", not "VR headset"; "three-dimensional space", not "3D space".
   When a fact gives the full term with its acronym in brackets ("field of
   view (FoV)", "three-dimensional (3D) space"), the name is the full term.
   When the facts write only the acronym, still name the concept by the
   full term the acronym stands for, and list the acronym as an alias. The
   name of a product or company is kept as it is written ("Microsoft
   HoloLens").
```
Replace rule 5:
```
5. Aliases. List every other name the facts use for the concept, written as
   in the facts: its acronym or abbreviation ("XR") and other wordings
   ("headset"). When part of the name is abbreviated in the facts, the
   abbreviated wording is an alias ("3D space" for "three-dimensional
   space"). Acronyms belong here and only here. Do not add an alias the
   facts do not use. Most concepts have one or none.
```

### concept_relations.txt
Replace rule 5:
```
5. Directed, and once. Every relationship has a direction, from the subject to the object; the concept map draws it as an arrow that way. Take the direction from the fact: the subject is the concept the fact's statement is about. Do not write the same statement a second time turned round ("A consists of B" and "B is part of A"; "A may use B" and "B may be used in A"). Write triples in both directions between two concepts only when the facts state two different things, one about each. Two concepts may have more than one triple in the same direction when the facts state different relationships between them.
```

### concept_same.txt
Add a bullet under SAME OR DIFFERENT (the `mixed` field needs user approval, question 5):
```
- An entry was itself collected by name, so its own facts may be about two different things (the "resolution" of a display in one lecture and of a tracker in another). Do not merge such an entry with another on the strength of some of its facts: keep it apart and list it under "mixed".
```
Replace the THE ENTRIES paragraph:
```
Each entry is given with its number, its name, its other names, its lectures, and its facts. Facts marked * come from a segment that defines the concept. An entry with many facts shows only some of them, and a last line says how many are not shown; judge it by the facts shown.
```
Replace ANSWER:
```
ANSWER
Answer with a JSON object with two fields, in this order.
"groups": a list of groups. Every entry number appears in exactly one group. Each group has these fields in this order:
"entries": the numbers of the entries in the group.
"reason": one sentence. For a group of several entries, what in their facts shows that they are the same concept. For a group of one, what makes it different from the entry closest to it.
"name": the name of the group's concept: the name of one of its entries (the name on the entry's first line, not one of its other names), the one that is the full term in words, singular, in the wording the course uses most. Never an acronym or abbreviation: an acronym stays among the other names. If every entry of the group is named by an acronym, take the full term from their other names instead.
"mixed": the numbers of the entries whose own facts are about two different things. Usually an empty list.
Answer with the JSON only.
```
(O: schema enum and `problems()` follow the name rule; `mixed` logged in decisions.jsonl and reported; nothing split.)

### concept_definition.txt
Replace the THE FACTS paragraph:
```
The facts from the course that name the concept, in lecture order, each with its number in brackets and the lecture it comes from. Facts marked * come from a segment that defines the concept. When the course has more facts about the concept than fit here, the facts of the defining segments are given first and a last line says how many are left out; write the definition from the facts given.
```
In THE DEFINITION, replace the second sentence of the first bullet with:
```
Begin with the name exactly as given above, followed by its acronym in brackets when one of the other names is an acronym.
```
(O: add "(n more facts not shown)" as the last line when capped, as 3b does.)

### course_goals.txt
Replace the THE LECTURES paragraph:
```
Each lecture is given with its key in square brackets, its title, its goal, what the goal achieves, and its objectives. The key is the lecture's identifier in the course: usually its number ("4"), sometimes with a letter or a word ("24b", "tut_1" for a tutorial).
```
Replace the "lectures" bullet:
```
- "lectures": the keys of the lectures whose goals work toward this course goal, written exactly as in the square brackets, in course order. Every lecture serves at least one course goal. A lecture may serve more than one when its objectives belong to different aims. The lectures of a goal need not be consecutive.
```
(O: `lecture_block` becomes `[{key}] {Lecture 4 | Tutorial 1}: {title}`, then `Goal:`, `Achieves:` (the lecture goal's
line only), then `Objectives:`.)

### lecture_goals.txt
Replace the first OBJECTIVES bullet:
```
- An objective covers one or more consecutive segments. Every segment belongs to exactly one objective, except a segment that teaches nothing of the subject: one that only recaps earlier lectures, outlines the course or the lecture, or summarises or closes the lecture. Such a segment belongs to none.
```

## CHOICES
Entry name = majority wording (accept; never an acronym while a non-acronym wording exists). Triples identical up to
case and spacing (accept; same direction). Cluster without a valid answer kept apart (accept). Threshold 0.70, cap 12,
5 facts in the embedding text, 8 per entry in the prompt (provisional; from the pair gold with the D9 options; report
entries hitting the 8-fact cap). 4a cap 40 (accept, with the "not shown" line). Objectives from 1 (accept).
`defined_later` (accept). `knowledge/` layout (accept). Block 2 inputs from the trial, no change now: adjectives as
concepts ("inside-out"); `defined` set on a mere mention; names the model coins ("body-part tracking").

## QUESTIONS FOR THE USER (open)
1. D11: lecture 1 defines "augmented virtuality"; lecture 16 uses it and restates it in one sentence. Does lecture 16
   still need lecture 1 for it? (Now: yes, marked `redefined`; Fable: yes.)
2. D8: names that are themselves acronyms or products (CAVE, NASA, MP3, 4K, HTC Vive, PlayStation VR): expand where a
   real full form exists (NASA, CAVE), keep product names as written?
3. D12/D2: does "check all outputs" include judging rewritten facts again (2 of 8 rewrites still fail)?
4. D13: approve the judge answer gaining `hedges`, `refers`, `recap`; the majority of three only if flips stay above
   5% after the revision; D1 narrowed (pointing fails only a leading pronoun, "the lecturer", "the slide"). And: could
   the user look at the 14 gold labels the gate hangs on (7 fail, 7 borderline; one labeller who had seen the verdicts)?
5. `concept_same.txt`: a report-only `mixed` field acceptable?
