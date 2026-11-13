# Showcase shortlist for the staged demo (MVP, 2026-11-13)

Picked from a full test of the MVP (`analysis/mvp/test_report.md`). Every item below was read against its cited facts,
and every question was asked on the real layer with Gemma 4 12B on this PC with the GPU free. IDs are the layer's;
on screen, keep dev mode off.

## Three lectures to demo besides lecture 4

| Lecture | Why | What to click | Watch out |
|---|---|---|---|
| **30 Auditory Sense & Immersive Experience (II)** | The richest lecture. It covers psychophysics (Stevens' power law, Weber's law, JND), sound localization (azimuth/elevation/radius, ILD/ITD) and HRTFs. All ten kinds are there, and the quizzes and recaps are accurate. It also has the best crossword in the course | Crossword **30/A15**; quiz **30/A9** (binaural cues, HRTF); recap **30/A8**; open question **30/A17** (JND → minimum audible angle; ILD/ITD + HRTF); odd one out **30/A16** (azimuth/elevation/radius vs direction); then ask "what is HRTF" (Q16) and "What do I need to know before lecture 30?" (Q36) | The map has 43 nodes and renders as a thin strip at Fit: zoom with + on "Psychoacoustics" or "Sound localization". Recall card "What is frequency?" shows a list sentence, so skip it. Match pairs 30/A14 are list clozes |
| **36 Usability requirement gathering and specification** | The best structured activities. The five contextual-inquiry stages run as quiz, order, crossword, complete-the-map and odd-one-out, all consistent with each other and with the facts | Put in order **36/A5** (stages described without their names) and **36/A8** (affinity-diagram steps); crossword **36/A14**; complete the map **36/A12**; odd one out **36/A15**; quiz **36/A6**; open question **36/A16** (apprentice, not teacher); ask "What is lecture 36 for?" (Q33) | The map (29 nodes) is wide: zoom on "Contextual inquiry". Match pairs 36/A13 repeat the same stage sentence |
| **23 XR as Interactive Systems** | **The most readable concept map in the course at Fit** (32 nodes, laid out tall). It shows the "disappearing technology is the same thing as presence" link and the lay-person / jargon cluster. Its activities are accurate and easy to follow | Concept map tab (no zoom needed); odd one out **23/A16** (Event log / Security accounts manager / Safe mode vs Error message); quiz **23/A3** (error messages and lay users); open question **23/A17** Q2 | The quizzes are on the easy side (23/A1 Q2 has a mirror distractor). The crossword 23/A15 is small (4 answers) |

**Alternate: lecture 9, Issues & Challenges.** The uncanny valley and the three fidelities make a crowd-pleaser
(quiz **9/A6**, recap **9/A7**, put in order **9/A5**, Q12 "Where does the course explain the uncanny valley?").
The map needs zooming.

## Per kind: the 2 most impressive real activities

| Kind | Pick 1 | Pick 2 | Why |
|---|---|---|---|
| quiz | **9/A6** (lecture 9, the three fidelities) | **30/A9** (lecture 30, ILD/ITD/HRTF) | Each wrong option is a real sibling concept (another fidelity type, another binaural cue), so the learner has to know the difference. Correct options are not the longest. Alternates: **17/A3** (IMU calibration, omega_cal = C1 + C2 omega_g) and **46/A10** (which significance test) |
| recap | **9/A7** (fidelities, presence without photorealism) | **18/A8** (vision-based tracking: infrared, outside-in vs inside-out) | Five tight points, each a faithful restatement of a fact, with no drift |
| open_question | **24/A17** (lecture 24: why a word processor offers both a menu and a hotkey; novice/intermittent/expert users) | **42/A22** (lecture 42: prototype vs full implementation; horizontal vs vertical; Wizard of Oz and the 1984 IBM listening typewriter) | Real "why" questions. The reference answers combine 3-7 facts and are fully supported. 24/A17 Q3 pulls in lecture 23's user-centric approach |
| odd_one_out | **26/A18** (axon/cell body/dendrite vs **synapse**; fatigue/headache/dizziness vs **presence**) | **36/A15** (plan/initiate/execute vs **affinity diagram**; the refined calendar headers vs **work scheduling**) | Each odd item is a real near-miss, and the facts state the reason. Alternate: **45/A22** #2 (empirical study / usability study / empirical research vs prototype evaluation) |
| put_in_order | **36/A5** (the five contextual-inquiry stages, described by what happens in each) | **28/A3** (light through the eye: air, cornea, aqueous fluid, lens, vitreous fluid, retina) | 5-6 real steps stated in the facts. Ordering descriptions, not names, takes understanding. Alternates: **56/A5** (3D graphics pipeline), **20/A11** (VR software layers) |
| crossword | **30/A15** (10 answers: ELEVATION, AZIMUTH, STEVENSPOWERLAW, PSYCHOPHYSICS, WEBERSLAW, ACOUSTICSHADOW...) | **36/A14** (10 answers: the five stages, ACTIVEMODE / PASSIVEMODE, AFFINITYDIAGRAM, GROUPHEADER, REQUIREMENT) | Every clue is a definition in other words, with no give-away word. 30/A15 is the cleanest grid in the sample. Alternate: **49/A12** (cybersickness factors) |
| complete_map | **36/A12** (reflect stage --[analyzes data collected during the]--> execute stage, among 3 other stage activities) | **8/A12** (immersion --[does not ensure]--> presence; virtual reality system --[has the overall goal of creating a high degree of]--> presence) | The options are other true labels from the same lecture, so choosing needs the concept. Short, readable labels |
| concept_map | **4/A7** (lecture 4, 19 nodes: CAD / video conferencing / 3D movie vs the three VR characteristics) | **23/A12** (lecture 23, 32 nodes: disappearing technology = presence; jargon vs lay person) | The only two maps that read well at Fit. Every edge comes from a relationship with its facts |
| match_pairs | **7/A17** (AR history: Tom Caudell, the Sutherland-Sproull prototype, Chameleon, the super cockpit) | none recommended | The weakest kind; see Avoid. 7/A17 is the one set where every right side differs, but its "experimental phase" pair is a list sentence |
| recall | **5/A0** (before lecture 5: AR, MR, reality-virtuality continuum, VR; all four answers are real definitions from lectures 1 and 4) | **3/A0** (XR, AR, immersive experience, metaverse) | Short, definitional, from the lectures they come from. Most other recall cards show non-definition sentences |

## The 10 best questions (verified; answers verbatim as the API returns them)

Ask them in this order. Run 1 was asked in one process, after warm-up, with the GPU free; run 2 is the repeat. All
answers are grounded, with no wrong citation. **On screen the `**` and `* ` markdown shows literally** (the viewer
prints plain text). The four with the least markdown are Q26, Q16, Q15 and Q33. Fix the rendering before the demo
if you can.

The two "does not cover" questions are the last two (Q19, Q29).

### Q31: "What is the difference between immersion and presence?"

Opens the box: a clean comparison across lectures 2, 8 and 9. Time: 6.9 s / 6.7 s (run 1 / run 2). Tools: check_concept, check_concept. 9 citations (lectures 2, 8, 9). Covered: yes.

> The main difference between immersion and presence is that immersion is a technological issue, while presence is a psychological one (lecture 8, 21:49; lecture 9, 23:22). 
>
> * **Immersion** is the objective degree to which a system projects stimuli onto a user's sensory receptors in an extensive, matching, and surrounding way (lecture 8, 10:12). It is the technological experience of having senses blocked from the real world to receive input only from the virtual world (lecture 2, 18:51).
> * **Presence** is the subjective psychological state or sense of being in a virtual environment (lecture 8, 23:14; lecture 8, 26:40). It captures whether a user actually perceives the immersive qualities generated by the system (lecture 8, 22:49).
>
> While immersion can aid and potentially produce presence, it does not ensure it; presence is limited by the level of immersion provided by the system (lecture 8, 26:40).

Citations: L8 21:49 `8/S1/F7`; L9 23:21 `9/S4/F0`; L8 10:11 `8/S1/F0`; L2 18:50 `2/S1/F0`; L8 23:14 `8/S2/F1`; L8 26:39 `8/S3/F1`; L8 22:49 `8/S2/F0`; L8 26:39 `8/S3/F2`; L8 26:39 `8/S3/F3`

### Q08: "What are the causes of cybersickness?"

A full taxonomy assembled from lectures 10, 11 and 49. Time: 6.1 s. Tools: check_concept. 7 citations (lectures 10, 11, 49). Covered: yes.

> Cybersickness is caused by a variety of factors rather than a single one (lecture 10, 4:23; lecture 49, 8:25). These causes are broadly divided into internal factors and external factors (lecture 10, 5:35).
>
> * **Internal factors** include the user's age, gender, physical condition, emotional condition, and individual susceptibility to motion sickness (lecture 49, 8:25; lecture 10, 25:13).
> * **External factors** are split into:
>  * **Hardware factors:** Display resolution, latency, latency jitter, type of display, and type of input (lecture 49, 8:25; lecture 10, 25:13).
>  * **Virtual reality (VR) content factors:** Visual motion, means of locomotion, field of view, type of content, duration, and visual complexity (lecture 49, 8:25; lecture 10, 25:13).
>
> Additionally, specific content elements like larger height, faster speed, and increasing angular velocity (particularly around the x and y axes) can increase the severity of cybersickness (lecture 11, 4:36; lecture 11, 5:48).

Citations: L10 4:23 `10/S0/F2`; L49 8:25 `49/S1/F0`; L10 5:34 `10/S1/F1`; L49 8:25 `49/S1/F1`; L10 25:13 `10/S3/F0`; L11 4:35 `11/S0/F4`; L11 5:47 `11/S0/F7`

### Q22: "What is the field of view and why does it matter for cybersickness?"

Nuance: a narrower FOV helps, but too narrow hurts (lectures 11, 12, 28). Time: 7.4 s / 6.6 s (run 1 / run 2). Tools: check_concept. 8 citations (lectures 11, 12, 28). Covered: yes.

> Field of view (FOV) is the extent to which a VR headset display captures a user's field of vision (lecture 11, 9:19), or the amount of virtual environment visible at any single moment (lecture 12, 16:24). It is also described as the view frustum, which is an angular measure of what can be seen at one point in time (lecture 28, 11:54).
>
> FOV matters for cybersickness (CS) because it is a content-related factor that affects susceptibility to it (lecture 11, 9:19; lecture 11, 1:08). Specifically:
> * Restricting the field of view can mitigate the onset or severity of cybersickness because it reduces peripheral optical flow (lecture 12, 16:42).
> * Research has shown that reducing FOV can be an effective way to alleviate cybersickness symptoms (lecture 11, 10:03).
> * However, an excessively narrow FOV can increase cybersickness because it may decrease immersion and force users to move their heads more to see things in the environment (lecture 11, 10:18).
> * Adjusting the FOV can reduce presence and impair performance in visual tasks because it restricts certain visual content (lecture 12, 17:37).

Citations: L11 9:19 `11/S2/F0`; L12 16:24 `12/S3/F1`; L28 11:54 `28/S1/F0`; L11 1:08 `11/S0/F1`; L12 16:41 `12/S3/F2`; L11 10:02 `11/S2/F2`; L11 10:17 `11/S2/F3`; L12 17:36 `12/S3/F4`

### Q26: "Why are GPUs used for rendering in VR?"

Joins hardware (lecture 14) and rendering (lecture 58). Time: 4.6 s / 5.4 s (run 1 / run 2). Tools: check_concept. 3 citations (lectures 14, 58). Covered: yes.

> GPUs are used for rendering in VR because they have inherent parallel processing abilities, which are well-suited for the inherent parallelism of the rendering process (lecture 14, 8:38). This makes them very useful for rendering the complex graphics and complex scenes required for realistic VR experiences (lecture 14, 8:38). 
>
> Unlike central processing units (CPUs), which are generally not designed for large-scale parallel activities, GPUs are designed to exploit the parallelism of graphics operations (lecture 58, 25:27). For example, a GPU can perform modeling transformations by applying transformations to millions of vertex vectors simultaneously (lecture 58, 26:06).

Citations: L14 8:38 `14/S1/F3`; L58 25:27 `58/S6/F0`; L58 26:05 `58/S6/F3`

### Q15: "What is an IMU?"

Resolves the acronym. Time: 4.2 s / 4.2 s (run 1 / run 2). Tools: check_concept. 4 citations (lectures 17). Covered: yes.

> An inertial measurement unit (IMU) is a composite hardware unit that typically contains a gyroscope, an accelerometer, and a magnetometer (lecture 17, 3:26). It is a type of sensor commonly used in modern devices like mobile phones and head-mounted displays (HMDs; lecture 17, 3:26).
>
> In an IMU:
> * The gyroscope captures angular velocity (lecture 17, 3:26).
> * The accelerometer captures linear acceleration along the x, y, and z axes (lecture 17, 3:26).
> * The magnetometer captures magnetic field strength along the x, y, and z axes (lecture 17, 3:26).
>
> For sensor tracking, the IMU relies mainly on gyroscope readings of angular velocity, while the accelerometer and magnetometer can be used to detect and correct drift errors (lecture 17, 3:26; lecture 17, 18:29).

Citations: L17 3:26 `17/S0/F0`; L17 3:26 `17/S0/F1`; L17 3:26 `17/S0/F2`; L17 18:28 `17/S3/F1`

### Q16: "what is HRTF"

Lower case, no question mark, acronym. Time: 6.7 s / 6.7 s (run 1 / run 2). Tools: check_concept. 4 citations (lectures 30). Covered: yes.

> Head-related transfer functions (HRTF) model how a listener receives sound from a specific location in space (lecture 30, 24:39). These functions depend on the unique size and shape of an individual's head, ears, and ear canal (lecture 30, 24:39).
>
> In extended reality (XR) systems, a pair of HRTFs for both ears can be used to synthesize binaural sound (lecture 30, 21:08). By placing sound receivers or generating effects according to the HRTF, a localization effect can be implemented (lecture 30, 21:08). Because every person has a unique HRTF, systems typically use an HRTF developed for an average listener instead (lecture 30, 24:39).

Citations: L30 24:39 `30/S4/F5`; L30 24:39 `30/S4/F6`; L30 21:07 `30/S4/F8`; L30 24:39 `30/S4/F7`

### Q17: "what is cybersicknes"

Misspelt, still matched; the richest answer (10 citations). Time: 7.3 s / 7.4 s (run 1 / run 2). Tools: check_concept. 10 citations (lectures 10, 26, 49). Covered: yes.

> Cybersickness (CS), also known as visually induced motion sickness (VIMS), is a condition that can affect individuals when they interact with virtual reality (VR) technology (lecture 10, 2:10; lecture 49, 8:25). It is primarily relevant to virtual reality and is not caused by a single factor, but rather a variety of influences (lecture 10, 4:23; lecture 49, 8:25).
>
> Common symptoms of cybersickness include:
> * Nausea and vomiting or a tendency to vomit (lecture 10, 3:08)
> * Headache and dizziness (lecture 10, 3:08; lecture 26, 19:14)
> * Excessive sweating and dryness of mouth (lecture 10, 3:08)
> * Fatigue and disorientation (lecture 10, 3:08; lecture 26, 19:14)
> * Strange hand-eye coordination where coordination does not happen in the expected way (lecture 10, 3:08)
>
> The causes are broadly divided into internal factors (such as age, gender, and physical/emotional condition) and external factors (such as hardware factors like latency and resolution, and VR content factors like visual motion and locomotion; lecture 10, 5:35; lecture 10, 25:13; lecture 49, 8:25). Reducing the impact of cybersickness is important for the usability, acceptability, and overall user experience of VR systems (lecture 10, 4:35; lecture 49, 8:25).

Citations: L10 2:09 `10/S0/F0`; L49 8:25 `49/S1/F0`; L10 4:23 `10/S0/F2`; L10 3:07 `10/S0/F1`; L26 19:13 `26/S5/F2`; L10 5:34 `10/S1/F1`; L10 25:13 `10/S3/F0`; L49 8:25 `49/S1/F1`; L10 4:34 `10/S0/F3`; L49 8:25 `49/S1/F2`

### Q34: "How does the Wizard of Oz approach work?"

A story learners remember (IBM, 1984). Time: 7.0 s / 7.0 s (run 1 / run 2). Tools: check_concept, fact_lookup. 4 citations (lectures 42). Covered: yes.

> The Wizard of Oz approach is a prototype-creation technique where a human subject believes they are interacting with an autonomous computer (lecture 42, 35:43). In reality, an unseen human operator, known as a "wizard," operates the computer and provides the responses or results to the subject (lecture 42, 35:43). 
>
> An example of this is the 1984 IBM listening typewriter experiment (lecture 42, 36:40):
> - A user spoke into a microphone while facing a computer, believing the computer was processing their speech (lecture 42, 36:40).
> - A hidden wizard, separated by a wall, heard the speech through a speaker and typed the characters (lecture 42, 36:40).
> - These characters were transmitted to the user's screen, making the user believe speech was being automatically converted into text (lecture 42, 36:40).
> - This was used to test the acceptability of a speech recognition system before committing resources to build it, as the technology was not yet available (lecture 42, 36:40).

Citations: L42 35:43 `42/S6/F0`; L42 36:40 `42/S6/F1`; L42 36:40 `42/S6/F2`; L42 36:40 `42/S6/F3`

### Q33: "What is lecture 36 for?"

What a lecture is for, from the goals tree. Time: 3.7 s / 3.3 s (run 1 / run 2). Tools: lecture_overview. 4 citations (lectures 36). Covered: yes.

> Lecture 36, "Usability requirement gathering and specification," aims to explain how to use contextual inquiry and affinity diagrams to convert observed user behavior into usability requirements and design recommendations (lecture 36, 0:24; lecture 36, 3:55). It provides a user-centered method for moving from requirement gathering to usability specification during XR system development (lecture 36, 0:24). 
>
> The lecture covers the following objectives:
> - Explain contextual inquiry as a staged observational method, including its active and passive modes, the master-apprentice observer stance, and reflection through affinity diagrams (lecture 36, 0:24; lecture 36, 3:55).
> - Apply affinity diagrams to group observations into design recommendations and requirement categories, while distinguishing requirements from implementation choices (lecture 36, 9:23; lecture 36, 23:54).

Citations: L36 0:24 `segment`; L36 3:55 `segment`; L36 9:22 `segment`; L36 23:53 `segment`

### Q36: "What do I need to know before lecture 30?"

What to watch first: the course graph (shown: run 2). Time: 5.2 s / 6.0 s (run 1 / run 2). Tools: lecture_dependencies. 7 citations (lectures 1, 4, 8, 10, 29). Covered: yes.

> To prepare for lecture 30, "Auditory Sense & Immersive Experience", you should first complete lecture 29, which covers the following concepts:
> * **Sound wave**: A plot of pressure variation against time, where pressure varies like a sinusoidal wave (lecture 29, 10:21).
> * **Frequency**: The number of alterations between one maximum and another maximum per second, measured in hertz (Hz; lecture 29, 11:19).
> * **Sound wave properties**: Sound waves are primarily characterized by frequency, amplitude, and phase (lecture 29, 10:59).
>
> Additionally, lecture 30 builds on several concepts from earlier in the course:
> * **Extended Reality (XR)**: An umbrella term for immersive technologies like AR, VR, and MR (lecture 1, 11:38).
> * **Virtual Reality (VR)**: An artificial environment experienced through sensory stimuli, primarily sights and sounds, provided by a computer (lecture 4, 2:14).
> * **Presence**: The psychological state where a user perceives the immersive qualities of an experience as real, failing to acknowledge the role of the technology (lecture 8, 23:14).
> * **Cybersickness**: A condition like motion sickness that can occur when interacting with VR technology (lecture 10, 2:10).

Citations: L29 10:20 `29/S1/F3`; L29 11:18 `29/S1/F5`; L29 10:59 `29/S1/F4`; L1 11:38 `1/S1/F0`; L4 2:13 `4/S0/F2`; L8 23:14 `8/S2/F1`; L10 2:09 `10/S0/F0`

### Q19: "How does a Kalman filter fuse IMU and camera data for tracking?"

Near-domain, not covered: declines, then offers what the course does say. Time: 20.9 s / 18.4 s (run 1 / run 2). Tools: check_concept, fact_lookup. 3 citations (lectures 17, 18). Covered: no.

> The course does not cover Kalman filters or the specific mechanism of how IMU and camera data are fused for tracking. 
>
> However, it does provide the following related information:
> * Inertial measurement unit (IMU) tracking relies primarily on gyroscope readings of angular velocity, while the accelerometer and magnetometer can be used to detect and correct drift errors (lecture 17, 3:26).
> * Vision-based trackers determine poses, such as position and orientation, using optical sensors or cameras (lecture 18, 9:58).
> * Simultaneous Localization and Mapping (SLAM) is used to provide drift-free tracking of unknown environments (lecture 18, 20:22).

Citations: L17 3:26 `17/S0/F2`; L18 9:57 `18/S3/F0`; L18 20:21 `18/S6/F3`

### Q29: "Who won the 2022 FIFA World Cup?"

Off-topic: one-line refusal. Time: 5.2 s / 2.4 s (run 1 / run 2). Tools: course_goals. 0 citations. Covered: no.

> The course does not cover the 2022 FIFA World Cup. It is focused on the foundations of Virtual and Augmented Reality systems, including hardware, software, human factors, and system design.

## Avoid on stage

- **Match pairs (every lecture).** List sentences with the blank moved around (30/A14 social / warning / primitive),
  truncated right sides, twin rows (61/A17 material / texture), and right sides that are another concept's sentence
  (10/A11 motion sickness, 45/A20 controlled experiment).
- **Recall and spaced-review cards in general.** Most backs are not definitions (4a was skipped). Examples:
  "What is head-mounted display (HMDs)?" → the history of the formative years (7/A0); "What is neuron?" (31/A0);
  "What is lighting?" (56/A0). Only show 5/A0 or 3/A0. When flipping review cards, pre-check the first three.
- **Crosswords:**
  - the five unresolved: 13/A19, 21/A11, 29/A11, **51/A21** (SHORTESTPATH is clued with the TSP tour: wrong), 58/A20
  - **60/A13** (UNITYPREFAB clue is wrong; SCENEVIEW and GAMEVIEW are interchangeable)
  - **16/A13** ("The second of the four steps" with no context)
  - **2/A8** (DEFENSE "about 4%").
- **Concept maps of big lectures at Fit** (42 of 63 have more than 60 nodes; lectures 20, 39, 56, 58, 61, 62 have
  140-170). Zoom on a hub first, or use lecture 4 / 23.
- **Duplicate concepts that show on screen:**
  - headset, head-mounted display, virtual reality headset (and VR headset) appear together on the maps of lectures
    2, 6, 10, 11, 13, 15, 16, 17, 20, 28 and 44
  - AR Toolkit next to augmented reality toolkit (21/A8)
  - 3D model and three-dimensional model; xr engine and extended reality engine; ios and iPhone operating system.

  Don't open those concept cards or search those names in the glossary.
- **Weak activities seen in testing:**
  - 59/A5 (a "sequence" that is not one)
  - 11/A18 (trivial 3 steps)
  - 15/A16 #2 (battery puzzle is contestable)
  - 51/A22 #2 ("Model")
  - 57/A1 Q1 and 28/A4 Q4-Q5 (give-away options)
  - 3/A3 Q2 (two defensible answers)
  - 18/A27 Q4 and 60/A15 Q4 (forced links to lecture 1)
  - 5/A10 (the same edge blanked twice).
- **Question types:**
  - Not-covered questions take about 20 s (Q19): talk while it runs, or use the FIFA one (2-5 s). Vergence-
    accommodation (Q20) declines but pads with loosely related facts.
  - Multi-concept comparisons can spike to about 19 s (Q07, gait).
  - Q04 (calibration formula) shows raw LaTeX.
  - "What do I need before lecture 16 / 40?" includes odd items: "HMDs: displays from the 1950s" and augmented
    virtuality for 16; location awareness and markers for 40. Lecture 30's version is cleaner.
  - "Where is X taught" shows two different times (the fact's time in the text, the segment's time in the citation).
  - Q09 (contextual-inquiry stages) repeats one citation five times.
- **Warm-up:** the first question after a start loads the embedder and the server (12-16 s). Ask one throw-away
  question before the audience arrives, as DEMO_PLAN.md says.
