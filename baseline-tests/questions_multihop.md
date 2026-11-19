# Multihop question category (M01-M12)

Written without looking at any system output. Lecture numbers are the file indices used by the pipeline (the lecturers' own spoken numbering differs in places, e.g. lecture 10 introduces itself as lecture 6 of its module). Gold points were checked against the human-written subtitles; times are transcript times (fact start times can be a few seconds to 1 minute earlier than the sentence).

| id | kind | lectures spanned | why it needs more than one passage |
|---|---|---|---|
| M01 | chain | 11, 12, 27 (26) | The eye property (L27), the vection finding (L11) and the mitigation technique (L12) are in three lectures; no single passage states the whole chain. |
| M02 | chain | 11, 12, 40, 41, 51, 59 | Walking limits (L40), cybersickness effect of locomotion (L11, L12), the design rationale (L41) and the final combination (L59) are separate; the reason is only complete when combined. |
| M03 | chain | 11, 12, 51, 52, 53 | Cause (L11, L12) and the algorithmic response (L51-53) are taught weeks apart; the answer needs both. |
| M04 | spread | 44, 47, 59, 60 | Platform, SDK, evaluation hardware and optimisation consequences are scattered over four lectures, more than a top-8 passage search covers. |
| M05 | spread | 13, 14, 16, 17, 18 | Tracking is spread across five lectures (hardware overview, full-body, tracking I, IMU, tracking II); a top-8 search covers only part of it. |
| M06 | spread | 12, 38, 41, 51, 52, 53 | The answer has many parts across the mitigation lecture, the design guideline lecture, the Majuli design lecture and three optimisation lectures. |
| M07 | course order | 55, 56, 57, 58, 60, 61 | Needs the dependency of the Unity lectures on the whole graphics-pipeline sequence, stage by stage. |
| M08 | course order | 8, 11, 41, 44, 45, 46, 47 | The evaluation lecture reuses ideas from presence, cybersickness measurement, user-study method and the design lecture; the dependencies are spread across seven lectures. |
| M09 | course order | 14, 28, 54, 58, 59 | Needs the earlier hardware, human-factors and rendering lectures to explain the final optimisation choices; the final lecture alone gives only the choices. |
| M10 | connect | 11, 12, 26, 47, 49 | The link between the two concepts is stated in pieces in five lectures; none gives the combined picture. |
| M11 | connect | 28, 44, 59 (14) | Perception basis (L28) and the cardboard implementation and its cost (L44, L59) are far apart; the course does not link them in one sentence. |
| M12 | connect | 10, 12, 14, 26 | The mismatch explanation (L10, L26) and the cue-adding hardware (L12, L14) are not linked in one place; the link must be assembled. |

## Fact / transcript checks

No fact contradicted the transcript on the points used. Differences noted:

- 55/S1/F1 lists five stages including lighting; the lecture 55 closing summary (37:25) names only four (omits lighting) while the 12:30 passage names all five. M07 follows the 12:30 passage and the fact.
- Fact times for several segments (e.g. 12/S3/F15 at 23:02) are segment start times; the spoken sentence is later (phantom legs at 24:24). Gold sources use transcript times.
- 44/S4/F0 and 47/S1/F5 give segment-level times; transcript times used (44 at 18:21, 47 at 8:12).
- 47/S1/F5 says the HMD was connected to a PC; the transcript (47, 8:25) says via Oculus Link, used in M04.
- 16/S2/F4 (outside-in "used by most VR headsets today", 16 at 14:47) is not used as a gold point.
- M12 is an inference-style connect question: the course states the mismatch cause (L10, L26) and the cue-adding techniques (L12, L14) but no sentence links them; the gold only restates the course's own points side by side.
