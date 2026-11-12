# The fact judge against the reference (block 1)

Made by `analysis/fact_judge/compare.py`. Gold: `gold.json` (62 facts, 55 pass, 7 fail, 7 borderline). Seeded: `seeded.json` (34 entries). Property numbers: 1 Significant, 2 Whole, 3 Established, 4 Grounded, 5 Self-contained, 6 Terms in full, 7 On the subject, 8 Faithful.

## Run `base`: sage-a1.5-fp8, the config's seed (as in 2b), prompt 09a26b62f66a

| Verdict | Labels | Gold fails caught | Missed | False alarms on gold-pass facts |
|---|---|--:|--:|--:|
| judge | all | 1/7 (14%) | 1/S5/F0, 16/S0/F0, 16/S0/F1, 16/S1/F5, 16/S2/F3, 16/S3/F0 | 4/55 (7%) |
| judge | without borderline | 1/5 (20%) | 1/S5/F0, 16/S1/F5, 16/S2/F3, 16/S3/F0 | 2/50 (4%) |
| 2b (judge + code checks) | all | 1/7 (14%) | 1/S5/F0, 16/S0/F0, 16/S0/F1, 16/S1/F5, 16/S2/F3, 16/S3/F0 | 7/55 (13%) |
| 2b (judge + code checks) | without borderline | 1/5 (20%) | 1/S5/F0, 16/S1/F5, 16/S2/F3, 16/S3/F0 | 5/50 (10%) |

Per property (judge, all labels): gold failures caught, of them with the property named in the reason; false alarms whose reason names the property.

| Property | Gold fails | Caught | Right reason | False alarms naming it |
|---|--:|--:|--:|--:|
| 1 Significant | 1 | 1 | 0 | 2 |
| 2 Whole | 4 | 1 | 0 | 3 |
| 3 Established | 0 | 0 | 0 | 0 |
| 4 Grounded | 0 | 0 | 0 | 0 |
| 5 Self-contained | 0 | 0 | 0 | 0 |
| 6 Terms in full | 1 | 1 | 0 | 0 |
| 7 On the subject | 0 | 0 | 0 | 0 |
| 8 Faithful | 3 | 0 | 0 | 0 |

Disagreements (judge, all labels):

- **1/S5/F0** gold fail [8], judge pass. Gold: The lecturer says the paper is one of the earliest 'in this field' and shaped 'the area', meaning virtual and augmented reality. The fact names the nearest noun instead: 'the field of mixed reality visual displays', taken from the paper's title. Judge: The fact is a complete point about the seminal reference for the reality-virtuality continuum, directly supported by sentences 16-18, and meets all eight properties.
- **16/S0/F0** gold fail [2] (borderline), judge pass. Gold: With F1 this is one point, that tracking is an essential part of an XR system, split into two thin facts. Judge: Passes all eight properties: it is a significant, central statement from sentences 5–6, one complete point about tracking as an integral XR hardware component, asserted by the lecturer and fully grounded, self-contained, on subject, and faithful.
- **16/S0/F1** gold fail [2] (borderline), judge pass. Gold: See F0: the same point. Judge: Passes all eight properties: it is a significant reason why tracking is essential, grounded in sentence 10, one complete point, asserted, self-contained, on subject, and faithful.
- **16/S1/F5** gold fail [8], judge pass. Gold: The lecturer says perfect matching 'may not be required'; the fact says it 'is not required'. Judge: Pass. It states that approximate tracking may be sufficient for other body parts, grounded in sentences 5 and 22; it is a separate point about quality.
- **16/S2/F3** gold fail [8], judge pass. Gold: The lecturer says outside-in tracking is used by most VR headsets today. The fact says most VR headsets that use external sensors fall under outside-in tracking, which is true by definition and loses the point. Judge: Passes all eight properties: it states the market adoption of outside-in tracking for external-sensor VR headsets, a distinct point grounded in sentence 12.
- **16/S3/F0** gold fail [2], judge pass. Gold: Sentences 102-103 recap the previous segment ('we have seen ... there are two ways'); the fact restates the recap and adds nothing (the same point is 16/S2/F1). Judge: Passes all eight properties. It is a significant core concept in tracking, stated as a complete point, established by the lecturer, grounded in sentences 3-4, self-contained, uses full terms, on subject, and faithful.
- **1/S3/F4** gold pass, judge fail. Gold: Rightly leaves out who made the word popular. Judge: It fails property 2 because it combines two different points that could be asked separately: the term’s 30-year history (sentence 43) and its role in stimulating growth (sentence 44), and it includes a passing remark about the term’s age that is not significant (property 1).
- **1/S3/F5** gold pass (borderline), judge fail. Gold: F6 is the detail of this fact's 'reimagines the way humans interact'; the two could be one point. Judge: It fails property 2 because it combines two different points: the metaverse is not merely an application of VR/MR/AR (sentence 45) and one broad view is that it reimagines human interaction with the digital world (sentence 47).
- **4/S1/F0** gold pass (borderline), judge fail. Gold: The list of the three characteristics, naming its members without describing them, which is what the extraction prompt asks for; F1, F3 and F4 each describe one member. Long, and its last clause (telling VR systems from others) could go. Not a summary of the segment. Judge: Fails property 2 (Whole): it reads as a summary of the segment and overlaps with facts F1–F4, which each explain one of the three defining characteristics.
- **16/S0/F4** gold pass, judge fail. Gold:  Judge: Fails property 1 (significant): the terminology note from sentences 17–18 is a passing remark relative to the segment’s goal of explaining why tracking is essential and how requirements differ; a student missing it would lose nothing. It passes the other properties.

Seeded errors: caught 32/34 (94%), all facts of the entry failed 32/34 (94%), caught for the right reason 31/34 (91%).

| Property broken | Entries | Caught | Right reason |
|---|--:|--:|--:|
| 1 Significant | 3 | 3 | 3 |
| 2 Whole | 7 | 7 | 6 |
| 3 Established | 4 | 4 | 4 |
| 4 Grounded | 5 | 5 | 5 |
| 5 Self-contained | 4 | 4 | 4 |
| 6 Terms in full | 3 | 2 | 2 |
| 7 On the subject | 6 | 6 | 6 |
| 8 Faithful | 7 | 6 | 6 |

Seeded entries not caught, or caught for another reason:

- **E07** (two unrelated points in one fact; breaks [2]): caught, other reason. Judge: It combines two distinct points: the factors that determine how to track and the examples of inside-out tracking, which could be asked about separately.
- **E22** (an acronym alone; breaks [6]): passed. Judge: Passes all eight properties: it is a significant point the segment teaches, one complete point, asserted by the lecturer, grounded in sentences 12 and 16, self-contained, uses full terms with acronyms as in the segment, on-topic, and faithful.
- **E34** (a limit dropped ('in a very broad sense', 'sometimes'); breaks [8]): passed. Judge: The fact defines mixed reality as the entire space between the real and virtual extremes of the continuum, grounded in sentences 1, 5, 6, 14, and 18. It is a significant, whole point that is self-contained and on the subject.

Other facts of the seeded calls failed: 7, of them passed in `base`: 3 (1/S3/F8 in E06, 16/S2/F6 in E27, 16/S2/F3 in E31).

## Run `seed1`: sage-a1.5-fp8, seed 1, prompt 09a26b62f66a

| Verdict | Labels | Gold fails caught | Missed | False alarms on gold-pass facts |
|---|---|--:|--:|--:|
| judge | all | 1/7 (14%) | 1/S0/F1, 1/S5/F0, 16/S0/F0, 16/S0/F1, 16/S2/F3, 16/S3/F0 | 3/55 (5%) |
| judge | without borderline | 1/5 (20%) | 1/S0/F1, 1/S5/F0, 16/S2/F3, 16/S3/F0 | 1/50 (2%) |
| 2b (judge + code checks) | all | 1/7 (14%) | 1/S0/F1, 1/S5/F0, 16/S0/F0, 16/S0/F1, 16/S2/F3, 16/S3/F0 | 6/55 (11%) |
| 2b (judge + code checks) | without borderline | 1/5 (20%) | 1/S0/F1, 1/S5/F0, 16/S2/F3, 16/S3/F0 | 4/50 (8%) |

Per property (judge, all labels): gold failures caught, of them with the property named in the reason; false alarms whose reason names the property.

| Property | Gold fails | Caught | Right reason | False alarms naming it |
|---|--:|--:|--:|--:|
| 1 Significant | 1 | 0 | 0 | 0 |
| 2 Whole | 4 | 0 | 0 | 2 |
| 3 Established | 0 | 0 | 0 | 0 |
| 4 Grounded | 0 | 0 | 0 | 0 |
| 5 Self-contained | 0 | 0 | 0 | 0 |
| 6 Terms in full | 1 | 0 | 0 | 1 |
| 7 On the subject | 0 | 0 | 0 | 0 |
| 8 Faithful | 3 | 1 | 1 | 0 |

Disagreements (judge, all labels):

- **1/S0/F1** gold fail [1, 2, 6], judge pass. Gold: A 120-word summary of the segment's motivating examples of what people associate with the terms; the lecturer raises each to ask whether it is XR, and teaches none of them. '3D or 4D' is not written in full. The one teachable point inside is the headset (sentences 59-61): worn on the head, blocks vision, the most common perception of VR. Judge: It captures the segment's core point about varying common associations, grounded in sentences 44–76, maintains the lecturer's hedges, and is a single complete point not split from other facts.
- **1/S5/F0** gold fail [8], judge pass. Gold: The lecturer says the paper is one of the earliest 'in this field' and shaped 'the area', meaning virtual and augmented reality. The fact names the nearest noun instead: 'the field of mixed reality visual displays', taken from the paper's title. Judge: The fact is significant and grounded in sentences 16-18, which state the reality-virtuality continuum was taken from Milgram and Kishino's 1994 paper and that the paper is an early influential work. It is complete, established, self-contained, avoids acronyms, is on the subject, and faithful to the lecturer's claims.
- **16/S0/F0** gold fail [2] (borderline), judge pass. Gold: With F1 this is one point, that tracking is an essential part of an XR system, split into two thin facts. Judge: It is a significant, complete point supported by sentences 5 and 6, with no overlap and all terms in full.
- **16/S0/F1** gold fail [2] (borderline), judge pass. Gold: See F0: the same point. Judge: It is a complete, significant point supported by sentence 10, stating that tracking motion is crucial for XR and VR without adding unsupported information.
- **16/S2/F3** gold fail [8], judge pass. Gold: The lecturer says outside-in tracking is used by most VR headsets today. The fact says most VR headsets that use external sensors fall under outside-in tracking, which is true by definition and loses the point. Judge: It states that most VR headsets using external sensors are outside-in, grounded in sentence 12, and uses 'virtual reality (VR)' correctly.
- **16/S3/F0** gold fail [2], judge pass. Gold: Sentences 102-103 recap the previous segment ('we have seen ... there are two ways'); the fact restates the recap and adds nothing (the same point is 16/S2/F1). Judge: This is a complete point about the two input methods for tracking; it is directly asserted in sentences 3–4, grounded, self-contained, and on the subject, so it has all eight properties.
- **1/S3/F5** gold pass (borderline), judge fail. Gold: F6 is the detail of this fact's 'reimagines the way humans interact'; the two could be one point. Judge: It fails property 2 because it holds two different points that could be asked separately: the metaverse is not merely an XR application, and one broad view reimagines human-digital interaction, which overlaps fact 1/S3/F6.
- **4/S1/F0** gold pass (borderline), judge fail. Gold: The list of the three characteristics, naming its members without describing them, which is what the extraction prompt asks for; F1, F3 and F4 each describe one member. Long, and its last clause (telling VR systems from others) could go. Not a summary of the segment. Judge: Fails property 2 (whole): it reads as a summary of the entire segment and combines three distinct characteristics (artificial environment, sensory experience, user interaction) that are separately covered by facts F1, F2, F3, and F4.
- **16/S2/F6** gold pass, judge fail. Gold:  Judge: It fails property 6: it uses the acronym 'VR' in 'VR820' without writing it as 'virtual reality (VR)', even though the lecturer uses 'VR' in the segment.

Seeded errors: caught 30/34 (88%), all facts of the entry failed 30/34 (88%), caught for the right reason 30/34 (88%).

| Property broken | Entries | Caught | Right reason |
|---|--:|--:|--:|
| 1 Significant | 3 | 2 | 2 |
| 2 Whole | 7 | 7 | 7 |
| 3 Established | 4 | 4 | 4 |
| 4 Grounded | 5 | 5 | 5 |
| 5 Self-contained | 4 | 3 | 3 |
| 6 Terms in full | 3 | 2 | 2 |
| 7 On the subject | 6 | 6 | 6 |
| 8 Faithful | 7 | 6 | 6 |

Seeded entries not caught, or caught for another reason:

- **E01** (trivia: who made a word popular; breaks [1]): passed. Judge: Passes: one complete point about Zuckerberg popularizing the term, asserted, grounded in 42-43, self-contained, full terms, on-topic, faithful.
- **E19** (a pointing word with nothing in the fact to point at; breaks [5]): passed. Judge: Pass. It is a significant, complete definition of augmented virtuality as the opposite of augmented reality; the lecturer asserts it; the information is grounded in sentences 8, 9, and 11; it is self-contained, on subject, and faithful.
- **E22** (an acronym alone; breaks [6]): passed. Judge: It is a complete point about VR tracking, supported by sentences 12 and 16, and it faithfully reports the lecturer's distinction without extra claims.
- **E34** (a limit dropped ('in a very broad sense', 'sometimes'); breaks [8]): passed. Judge: Passes all eight properties. It is a complete point about mixed reality as the space between the extremes, asserted by the lecturer, and grounded in sentences 1, 5, 6, 14, and 18. It is self-contained, uses full terms, is on the subject, and is faithful to the segment.

Other facts of the seeded calls failed: 7, of them passed in `base`: 4 (1/S3/F8 in E01, 1/S3/F7 in E13, 16/S3/F1 in E18, 16/S2/F3 in E27).

## Run `seed2`: sage-a1.5-fp8, seed 2, prompt 09a26b62f66a

| Verdict | Labels | Gold fails caught | Missed | False alarms on gold-pass facts |
|---|---|--:|--:|--:|
| judge | all | 0/7 (0%) | 1/S0/F1, 1/S5/F0, 16/S0/F0, 16/S0/F1, 16/S1/F5, 16/S2/F3, 16/S3/F0 | 5/55 (9%) |
| judge | without borderline | 0/5 (0%) | 1/S0/F1, 1/S5/F0, 16/S1/F5, 16/S2/F3, 16/S3/F0 | 3/50 (6%) |
| 2b (judge + code checks) | all | 0/7 (0%) | 1/S0/F1, 1/S5/F0, 16/S0/F0, 16/S0/F1, 16/S1/F5, 16/S2/F3, 16/S3/F0 | 8/55 (15%) |
| 2b (judge + code checks) | without borderline | 0/5 (0%) | 1/S0/F1, 1/S5/F0, 16/S1/F5, 16/S2/F3, 16/S3/F0 | 6/50 (12%) |

Per property (judge, all labels): gold failures caught, of them with the property named in the reason; false alarms whose reason names the property.

| Property | Gold fails | Caught | Right reason | False alarms naming it |
|---|--:|--:|--:|--:|
| 1 Significant | 1 | 0 | 0 | 1 |
| 2 Whole | 4 | 0 | 0 | 2 |
| 3 Established | 0 | 0 | 0 | 0 |
| 4 Grounded | 0 | 0 | 0 | 2 |
| 5 Self-contained | 0 | 0 | 0 | 0 |
| 6 Terms in full | 1 | 0 | 0 | 0 |
| 7 On the subject | 0 | 0 | 0 | 0 |
| 8 Faithful | 3 | 0 | 0 | 1 |

Disagreements (judge, all labels):

- **1/S0/F1** gold fail [1, 2, 6], judge pass. Gold: A 120-word summary of the segment's motivating examples of what people associate with the terms; the lecturer raises each to ask whether it is XR, and teaches none of them. '3D or 4D' is not written in full. The one teachable point inside is the headset (sentences 59-61): worn on the head, blocks vision, the most common perception of VR. Judge: Passes. It captures the segment's main point about the varied common associations of XR/VR/AR/MR, with every detail grounded in the cited sentences, and it is self-contained with full terms and no pronouns. It is significant, whole, established, grounded, on subject, and faithful.
- **1/S5/F0** gold fail [8], judge pass. Gold: The lecturer says the paper is one of the earliest 'in this field' and shaped 'the area', meaning virtual and augmented reality. The fact names the nearest noun instead: 'the field of mixed reality visual displays', taken from the paper's title. Judge: The fact passes all eight properties: it identifies the seminal reference and its significance exactly as asserted in sentences 16–18, is self-contained with full terms, and does not include course logistics or split the point.
- **16/S0/F0** gold fail [2] (borderline), judge pass. Gold: With F1 this is one point, that tracking is an essential part of an XR system, split into two thin facts. Judge: This fact is significant, whole, established, grounded in sentences 5 and 6, self-contained, uses full terms with acronyms as the lecturer used them, on the subject, and faithful, satisfying all eight properties.
- **16/S0/F1** gold fail [2] (borderline), judge pass. Gold: See F0: the same point. Judge: This fact is significant, whole, established, grounded in sentence 10, self-contained, uses full terms with acronyms as the lecturer used them, on the subject, and faithful, satisfying all eight properties.
- **16/S1/F5** gold fail [8], judge pass. Gold: The lecturer says perfect matching 'may not be required'; the fact says it 'is not required'. Judge: Passes all eight properties. It is a complete point that perfect matching is not required for other body parts, grounded in the cited sentences, and faithful.
- **16/S2/F3** gold fail [8], judge pass. Gold: The lecturer says outside-in tracking is used by most VR headsets today. The fact says most VR headsets that use external sensors fall under outside-in tracking, which is true by definition and loses the point. Judge: It is a significant, complete point about most VR headsets with external sensors falling under outside-in tracking; it is asserted in sentence 12, fully grounded in that sentence, self-contained, uses full terms with the acronym in brackets, and is faithful.
- **16/S3/F0** gold fail [2], judge pass. Gold: Sentences 102-103 recap the previous segment ('we have seen ... there are two ways'); the fact restates the recap and adds nothing (the same point is 16/S2/F1). Judge: Passes all eight properties: it is a complete point about input methods for tracking, directly asserted in sentences 3–4, with no overlap with other facts.
- **1/S3/F8** gold pass, judge fail. Gold:  Judge: Fails property 4: the causal claim that the growth of extended reality creates the need for manpower is stated in the segment but not in the cited sentences; sentences 37-41 and 56 would need to be added.
- **4/S1/F0** gold pass (borderline), judge fail. Gold: The list of the three characteristics, naming its members without describing them, which is what the extraction prompt asks for; F1, F3 and F4 each describe one member. Long, and its last clause (telling VR systems from others) could go. Not a summary of the segment. Judge: Fails Property 2 (Whole): it reads as a summary of the segment, listing all three defining characteristics together with the classification rule, and overlaps with F1, F2, F3, and F4 which each cover one characteristic or a specific nuance separately.
- **16/S0/F3** gold pass (borderline), judge fail. Gold: Turns 'AR requires virtual content to be registered' into 'tracking is primarily about registering'; the lecturer says AR tracking is more about tracking objects moving in the field of view. Close enough to pass. Judge: This fact fails property 4 and property 8 because it adds the word 'primarily' (not stated in the lecturer's sentences 13–16) and misattributes the primary aim of AR tracking; the lecturer emphasized tracking objects, not registering content.
- **16/S0/F4** gold pass, judge fail. Gold:  Judge: This fact fails property 1 because it is a terminology note (from sentences 17–18) about the popularity of the term 'tracking' and device naming, which is a passing remark rather than a core point the segment is there to teach; a student missing it would lose nothing.
- **16/S3/F1** gold pass, judge fail. Gold:  Judge: Fails property 2: it reads as a summary of the segment and lists all four steps, while facts F2–F5 each cover one of those steps, so it is not a single complete point.

Seeded errors: caught 32/34 (94%), all facts of the entry failed 32/34 (94%), caught for the right reason 29/34 (85%).

| Property broken | Entries | Caught | Right reason |
|---|--:|--:|--:|
| 1 Significant | 3 | 3 | 2 |
| 2 Whole | 7 | 7 | 6 |
| 3 Established | 4 | 4 | 4 |
| 4 Grounded | 5 | 5 | 5 |
| 5 Self-contained | 4 | 3 | 3 |
| 6 Terms in full | 3 | 2 | 2 |
| 7 On the subject | 6 | 6 | 4 |
| 8 Faithful | 7 | 7 | 7 |

Seeded entries not caught, or caught for another reason:

- **E03** (trivia: how hard something is; breaks [1]): caught, other reason. Judge: It is a passing remark about the complexity of deciding how to track; a student who missed it would lose nothing about the subject.
- **E10** (a recap of earlier lectures; breaks [2, 7]): caught, other reason. Judge: Fails property 1: it is a recap of previous lectures on why the terms matter, not a fact the segment is there to teach.
- **E20** ('the lecturer' and 'here'; breaks [5]): passed. Judge: Passes all eight properties: it is a complete point about the artificial environment characteristic, grounded in sentences 8-14 and 39, and self-contained without overlapping details.
- **E22** (an acronym alone; breaks [6]): passed. Judge: Passes all eight properties. It is one complete point about VR tracking from sentences 12 and 16, accurately stated and self-contained.
- **E25** (what the course will cover; breaks [7]): caught, other reason. Judge: It fails properties 2, 4, and 7. It reads as a summary of the segment's course objectives and lumps basic understanding, theoretical background, and practical knowledge, while the terms 'virtual and augmented reality' are not in the cited sentence 5 but in sentence 2, and the content concerns the course rather than the subject.

Other facts of the seeded calls failed: 10, of them passed in `base`: 5 (16/S2/F3 in E07, 1/S3/F8 in E13, 4/S1/F2 in E20, 16/S1/F0 in E30, 1/S3/F3 in E32).

## The code checks against gold

`pointing` stands for property 5, `acronym` for property 6; 2b fails a flagged fact whatever the judge says.

| Check | Flagged | Gold fails the property too | False alarms | Gold failures not flagged |
|---|--:|---|---|---|
| `pointing` | 3 | - | 4/S1/F3, 16/S1/F9, 16/S1/F11 | - |
| `acronym` | 0 | - | - | 1/S0/F1 |

False alarms with gold's note:

- `pointing` **4/S1/F3**: gold pass. 'this immersive experience' points at the experience named in the same sentence; the code check's flag is a false alarm.
- `pointing` **16/S1/F9**: gold pass. 'for this' points at the alerting named in the same sentence; the code check's flag is a false alarm.
- `pointing` **16/S1/F11**: gold pass. 'this is generally classified' points at the live capture named in the same sentence; the code check's flag is a false alarm.

Seeded entries and the code checks (expected: marked `code` in seeded.json):

- E18 (a leading pronoun): expected yes, flags ['pointing']
- E20 ('the lecturer' and 'here'): expected yes, flags ['pointing']
- E21 ('this type' with nothing in the fact to point at): expected yes, flags ['pointing']
- E23 (an acronym the lecturer does not use): expected yes, flags ['acronym']

## Flips between runs of the same judge and prompt

- sage-a1.5-fp8, prompt 09a26b62f66a, runs base, seed1, seed2: 9/62 (15%) gold facts flipped (1/S0/F1, 1/S3/F4, 1/S3/F5, 1/S3/F8, 16/S0/F3, 16/S0/F4, 16/S1/F5, 16/S2/F6, 16/S3/F1); seeded entries with a changed verdict: 4/34 (12%)

## Gate (block 1, PLAN.md)

For run `base` (the baseline); the other runs: `seed1`: false alarms 3/55 (5%), seeded caught 30/34 (88%); `seed2`: false alarms 5/55 (9%), seeded caught 32/34 (94%):

- False alarms on gold-pass facts <= 10%: 4/55 (7%)
- Seeded errors caught >= 90%: 32/34 (94%)
- No property with zero catches (seeded): met
- Flips <= 5%: 9/62 (15%)
