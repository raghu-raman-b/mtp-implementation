# The fact judge against the reference (block 1)

Made by `analysis/fact_judge/compare.py`. Gold: `gold.json` (62 facts, 55 pass, 7 fail, 7 borderline). Seeded: `seeded.json` (34 entries). Property numbers: 1 Significant, 2 Whole, 3 Established, 4 Grounded, 5 Self-contained, 6 Terms in full, 7 On the subject, 8 Faithful.

## Run `base`: sage-a1.5-fp8, the config's seed (as in 2b), prompt 09a26b62f66a

| Verdict | Labels | Gold fails caught | Missed | False alarms on gold-pass facts |
|---|---|--:|--:|--:|
| judge | all | 2/7 (29%) | 1/S5/F0, 16/S0/F0, 16/S0/F1, 16/S2/F3, 16/S3/F0 | 3/55 (5%) |
| judge | without borderline | 2/5 (40%) | 1/S5/F0, 16/S2/F3, 16/S3/F0 | 2/50 (4%) |
| 2b (judge + code checks) | all | 2/7 (29%) | 1/S5/F0, 16/S0/F0, 16/S0/F1, 16/S2/F3, 16/S3/F0 | 6/55 (11%) |
| 2b (judge + code checks) | without borderline | 2/5 (40%) | 1/S5/F0, 16/S2/F3, 16/S3/F0 | 5/50 (10%) |

Per property (judge, all labels): gold failures caught, of them with the property named in the reason; false alarms whose reason names the property.

| Property | Gold fails | Caught | Right reason | False alarms naming it |
|---|--:|--:|--:|--:|
| 1 Significant | 1 | 1 | 0 | 0 |
| 2 Whole | 4 | 1 | 0 | 2 |
| 3 Established | 0 | 0 | 0 | 0 |
| 4 Grounded | 0 | 0 | 0 | 1 |
| 5 Self-contained | 0 | 0 | 0 | 0 |
| 6 Terms in full | 1 | 1 | 1 | 0 |
| 7 On the subject | 0 | 0 | 0 | 0 |
| 8 Faithful | 3 | 1 | 1 | 0 |

Disagreements (judge, all labels):

- **1/S5/F0** gold fail [8], judge pass. Gold: The lecturer says the paper is one of the earliest 'in this field' and shaped 'the area', meaning virtual and augmented reality. The fact names the nearest noun instead: 'the field of mixed reality visual displays', taken from the paper's title. Judge: It passes all eight properties: the fact is significant, complete, established, grounded in sentences 16-18, self-contained, uses full terms, is on the subject, and is faithful to the lecturer's claims about the seminal reference.
- **16/S0/F0** gold fail [2] (borderline), judge pass. Gold: With F1 this is one point, that tracking is an essential part of an XR system, split into two thin facts. Judge: Passes all eight properties: it is a significant hardware fact, is distinct from other facts (e.g., F1 is about importance, not component), is asserted, grounded in sentences 5–6, self-contained, defines XR in full, is on subject, and faithful.
- **16/S0/F1** gold fail [2] (borderline), judge pass. Gold: See F0: the same point. Judge: Passes all eight properties: it is a significant point about why tracking matters, not covered by other facts, is asserted by the lecturer, grounded in sentence 10, self-contained, uses full terms XR and VR, is on subject, and faithful.
- **16/S2/F3** gold fail [8], judge pass. Gold: The lecturer says outside-in tracking is used by most VR headsets today. The fact says most VR headsets that use external sensors fall under outside-in tracking, which is true by definition and loses the point. Judge: It states the lecturer's assertion about most VR headsets using external sensors and falling under outside-in tracking, grounded in sentence 12, and is not trivial.
- **16/S3/F0** gold fail [2], judge pass. Gold: Sentences 102-103 recap the previous segment ('we have seen ... there are two ways'); the fact restates the recap and adds nothing (the same point is 16/S2/F1). Judge: Passes all eight properties: it is a significant classification of tracking input methods taught in the segment, is one complete point with no overlap, is asserted by the lecturer, grounded in sentences 3–4, self-contained, uses full terms, on-topic, and faithful.
- **1/S2/F0** gold pass, judge fail. Gold: Sentences 125 and 126 state both extremes ('nothing virtual there', 'nothing real here'); sentence 127 only repeats them, so it need not be cited. Judge: Fails property 4 (Grounded) because the modifiers 'completely real' and 'completely virtual' are stated only in sentence 7 ('completely virtual at one end, completely real at the other end'), which is not among the cited evidence sentences 1, 4, 5, 6.
- **4/S1/F0** gold pass (borderline), judge fail. Gold: The list of the three characteristics, naming its members without describing them, which is what the extraction prompt asks for; F1, F3 and F4 each describe one member. Long, and its last clause (telling VR systems from others) could go. Not a summary of the segment. Judge: Fails property 2: it reads as a summary of the segment, combining the three defining characteristics (covered separately by facts F1, F3, F4) with the categorization and distinction point, which could be asked about separately.
- **16/S1/F3** gold pass, judge fail. Gold: One point about eye tracking (when it is needed, and that it may be part of head tracking). Splitting it gives two thin facts. Judge: Fails property 2: it holds two points that could be asked separately—when eye tracking is required (sentence 14) and that eye tracking may be part of head tracking (sentence 15).

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

## Gate (block 1, PLAN.md)

For run `base`:

- False alarms on gold-pass facts <= 10%: 3/55 (5%)
- Seeded errors caught >= 90%: not measured in this run
- Flips <= 5%: not measured (one run of this prompt)
