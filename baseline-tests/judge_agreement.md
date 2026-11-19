# Judge agreement (Opus vs Sonnet)

257 answers judged by both. correct: exact 0.864, within 0.5 1.000, Cohen's kappa 0.715; hallucination flag (any vs none) agrees on 0.930.

| system | n | correct (Opus) | correct (Sonnet) | answers with hallucination (Opus) | (Sonnet) |
|---|---|---|---|---|---|
| abl_facts_unrestricted | 53 | 0.915 | 0.877 | 2 | 1 |
| abl_graph_unrestricted | 45 | 0.922 | 0.878 | 2 | 1 |
| ours | 53 | 0.915 | 0.868 | 2 | 2 |
| plain | 53 | 0.396 | 0.255 | 22 | 29 |
| rag | 53 | 0.887 | 0.858 | 2 | 1 |

## Disagreements on correct (35)

| qid | system | run | Opus | Sonnet | Opus note | Sonnet note |
|---|---|---|---|---|---|---|
| C01 | plain | 1 | 1 | 0.5 | tech vs psychological; no 'does not ensure' | tech vs psych; misses does-not-ensure |
| C02 | plain | 1 | 1 | 0.5 | replace vs overlay; no physical-existence point | replace vs overlay; misses real-place requirement |
| C04 | plain | 1 | 1 | 0.5 | right; no area restriction | sensor location right; no area restriction |
| C05 | plain | 1 | 1 | 0.5 | breadth vs depth right; adds database | generic breadth/depth; misses look-feel, no functionality |
| C06 | abl_facts_unrestricted | 1 | 1 | 0.5 | definitions right; no practice effect | misses practice effect |
| C06 | abl_graph_unrestricted | 1 | 1 | 0.5 | definitions right; no practice effect | misses practice effect |
| C06 | ours | 1 | 1 | 0.5 | definitions right; no practice effect | misses practice effect |
| C06 | plain | 1 | 1 | 0.5 | right; no practice effect | generic definitions; no easier/practice effect |
| C07 | plain | 1 | 1 | 0.5 | CRT-beam framing; no cost/precision | generic beam description; no precision/cost |
| D01 | plain | 1 | 1 | 0.5 | right definition; no per-person uniqueness / average listener; adds torso, 360 field | generic; misses uniqueness, average, binaural pair |
| D02 | plain | 1 | 1 | 0.5 | three sensors right; no tracking/drift role; adds gravity, compass | components only; no drift role, phones/HMD |
| D02 | rag | 1 | 1 | 0.5 | three sensors, no per-sensor measure, no drift role | components right; misses drift role |
| D04 | plain | 1 | 1 | 0.5 | 'being there', subjective; no failure-to-acknowledge definition; adds agency | feeling of being there; misses technology non-acknowledgement |
| D05 | plain | 1 | 1 | 0.5 | right; fewer symptoms, adds eye strain, vestibular | generic; misses VIMS, many symptoms and causes |
| D06 | plain | 1 | 1 | 0.5 | right in general; not the peripheral/CS points; adds optic flow | illusion and conflict; misses peripheral, cybersickness link |
| D07 | plain | 1 | 1 | 0.5 | memory for pixel data; no size = resolution; adds depth data, GPU | generic; no raster scan, one location per pixel, size |
| E01 | plain | 1 | 1 | 0.5 | parallelism right; adds 90 FPS, two views (not in course) | parallel but generic; lacks CPU/complex-scene course points |
| E02 | plain | 1 | 1 | 0.5 | right method; no IBM example | concept right; generic, no IBM example |
| E04 | plain | 1 | 1 | 0.5 | roughly right, no reduction-as-mitigation or optimum | generic; wide-FOV claim contradicts course reduction |
| E05 | ours | 1 | 1 | 0.5 | three characteristics; lacks immersion | three criteria; wrongly says CAD lacks environment |
| E05 | plain | 1 | 1 | 0.5 | lacks immersion; not the three-characteristics rule; adds presence | lacks immersion; misses three-criteria framing |
| F01 | plain | 1 | 0.5 | 0 | x2.5 right; odd/even scoring wrong (5-r for odd) | wrong formula (odd items inverted) |
| F02 | plain | 1 | 0 | 0.5 | names complementary filter/EKF, no formula | no formula; complementary filter idea only |
| F03 | plain | 1 | 0 | 0.5 | Lambertian only, presented as the simple model | diffuse only; no ambient/specular/sum |
| F05 | rag | 1 | 1 | 0.5 | all gold tests; Friedman wrongly listed for two levels | adds Friedman, wrong for two levels |
| L03 | abl_facts_unrestricted | 1 | 1 | 0.5 | three fidelities with ranges | names right; experiential definition off |
| L03 | abl_graph_unrestricted | 1 | 1 | 0.5 | three fidelities with ranges | names right; experiential definition off |
| L03 | ours | 1 | 1 | 0.5 | three fidelities with ranges | names right; definitions are scale descriptions, off |
| P02 | abl_facts_unrestricted | 1 | 1 | 0.5 | lecture 16 tracking steps | lecture 16 steps; misses integration, trackers |
| P02 | abl_graph_unrestricted | 1 | 1 | 0.5 | lecture 16 tracking steps | lecture 16 steps; misses integration, trackers |
| P02 | ours | 1 | 1 | 0.5 | lecture 16 tracking steps | lecture 16 steps; misses integration, trackers |
| P03 | abl_facts_unrestricted | 1 | 1 | 0.5 | lecture 29, frequency; no ear structure | lecture 29 right; only frequency |
| P03 | abl_graph_unrestricted | 1 | 1 | 0.5 | lecture 29, frequency; no ear structure | lecture 29 right; only frequency |
| P03 | ours | 1 | 1 | 0.5 | lecture 29, frequency; no ear structure | lecture 29 right; only frequency, no ear/pressure wave |
| P04 | rag | 1 | 0.5 | 0 | points to lecture 38 design; no interaction types | human factors/lifecycle; not lecture 39 |
