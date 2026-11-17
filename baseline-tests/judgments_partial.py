"""PARTIAL judgments (Opus judge), questions D01-L03 (24 of 53), systems ours / plain / rag (graphrag not run yet).
Written from judge/packet_00..03.txt. Run to (re)write judgments_partial.jsonl.
Fields: correct, complete (1 / 0.5 / 0), hallucination (false claim, contradiction of the course, or non-course
content presented as taught), outside (substantive claims the course does not teach), says_not_covered, citations
(lecture+time citations counted), valid (citations whose lecture/time hold the claim; RAG cites chunk starts, judged
valid when the claim is within 30 s before to 240 s after the cited time), reason.
"""
import json
from pathlib import Path

J = [
    # id, system, correct, complete, halluc, outside, says_nc, cit, valid, reason
    ("D01", "ours", 1, 1, 0, 0, 0, 4, 4, "all gold points"),
    ("D01", "plain", 1, .5, 0, 1, 0, 0, 0, "right definition; no per-person uniqueness / average listener; adds torso, 360 field"),
    ("D01", "rag", 1, 1, 0, 0, 0, 6, 6, "all gold points; cites chunk start 23:01 for content at 24:39-25:17"),
    ("D02", "ours", 1, 1, 0, 0, 0, 6, 6, "sensors and roles, drift role; adds lecture 18 inertial-tracker facts"),
    ("D02", "plain", 1, .5, 0, 1, 0, 0, 0, "three sensors right; no tracking/drift role; adds gravity, compass"),
    ("D02", "rag", 1, .5, 0, 0, 0, 3, 3, "three sensors, no per-sensor measure, no drift role"),
    ("D03", "ours", 1, 1, 0, 0, 0, 2, 2, "umbrella term, present/future, X as variable"),
    ("D03", "plain", 1, .5, 0, 1, 0, 0, 0, "umbrella term; not the course's present/future framing"),
    ("D03", "rag", 1, 1, 0, 0, 0, 5, 4, "umbrella term present/future; c5 (29:25) does not hold the AR/VR/MR list"),
    ("D04", "ours", 1, 1, 1, 0, 0, 10, 9, "full definition; but 'immersion can ... be limited by presence' reverses the course (presence is limited by immersion)"),
    ("D04", "plain", 1, .5, 0, 1, 0, 0, 0, "'being there', subjective; no failure-to-acknowledge definition; adds agency"),
    ("D04", "rag", 1, 1, 0, 0, 0, 6, 6, "ISPR definition, subjective, relation to immersion"),
    ("D05", "ours", 1, 1, 0, 0, 0, 10, 10, "VIMS, symptoms, many causes (misspelling handled)"),
    ("D05", "plain", 1, .5, 0, 1, 0, 0, 0, "right; fewer symptoms, adds eye strain, vestibular"),
    ("D05", "rag", 1, 1, 0, 0, 0, 3, 3, "VIMS and full symptom list"),
    ("D06", "ours", 1, 1, 0, 0, 0, 2, 2, "illusion of self-motion, conflict, peripheral, CS link"),
    ("D06", "plain", 1, .5, 0, 1, 0, 0, 0, "right in general; not the peripheral/CS points; adds optic flow"),
    ("D06", "rag", 0, 0, 0, 0, 1, 0, 0, "FALSE 'not covered': retrieval missed lectures 11 and 26"),
    ("D07", "ours", 1, 1, 0, 0, 0, 2, 2, "all gold points"),
    ("D07", "plain", 1, .5, 0, 1, 0, 0, 0, "memory for pixel data; no size = resolution; adds depth data, GPU"),
    ("D07", "rag", 1, 1, 0, 0, 0, 3, 3, "all gold points"),
    ("E01", "ours", 1, 1, 0, 0, 0, 4, 4, "parallelism, CPU not built for it, complex scenes"),
    ("E01", "plain", 1, .5, 0, 1, 0, 0, 0, "parallelism right; adds 90 FPS, two views (not in course)"),
    ("E01", "rag", 1, 1, 0, 0, 0, 9, 8, "complete; c2 (58, 17:19) does not hold the parallelism claim"),
    ("E02", "ours", 1, 1, 0, 0, 0, 4, 4, "definition + IBM 1984 example"),
    ("E02", "plain", 1, .5, 0, 1, 0, 0, 0, "right method; no IBM example"),
    ("E02", "rag", 1, 1, 0, 0, 0, 5, 5, "method and the speech example (IBM not named)"),
    ("E03", "ours", 1, .5, 0, 0, 0, 3, 2, "camera on user sees external targets; no emitting/reflecting targets; c2 (16, 15:14) does not hold the robustness claim"),
    ("E03", "plain", .5, .5, 1, 1, 0, 0, 0, "camera on HMD right, but 'IR emitters on the user's head' seen by the internal cameras is wrong"),
    ("E03", "rag", 1, .5, 0, 0, 0, 2, 2, "camera with user detects external targets; no target properties"),
    ("E04", "ours", 1, 1, 0, 0, 0, 8, 8, "definition, reduce helps, too narrow hurts, optimum"),
    ("E04", "plain", 1, .5, 0, 1, 0, 0, 0, "roughly right, no reduction-as-mitigation or optimum"),
    ("E04", "rag", 1, 1, 0, 0, 0, 6, 5, "complete + presence trade-off; c1 (11, 4:00) does not hold the definition"),
    ("E05", "ours", 1, 1, 0, 0, 0, 3, 3, "lacks immersion; three characteristics rule"),
    ("E05", "plain", 1, .5, 0, 1, 0, 0, 0, "lacks immersion; not the three-characteristics rule; adds presence"),
    ("E05", "rag", 1, 1, 0, 0, 0, 4, 4, "characteristic check, as taught"),
    ("E06", "ours", 1, 1, 0, 0, 0, 1, 1, "trade-off with presence"),
    ("E06", "plain", .5, .5, 0, 1, 0, 0, 0, "frames it as immersion/realism with general examples, not the course's presence point"),
    ("E06", "rag", 1, 1, 0, 0, 0, 3, 3, "trade-off with presence"),
    ("E07", "ours", 1, .5, 0, 0, 0, 1, 1, "reduce size, 5.1 GB (lecture 44); not the Quest's limits or the network cost"),
    ("E07", "plain", .5, 0, 1, 1, 0, 0, 0, "storage limit right; invents reasons (quality, scalability) as the project's"),
    ("E07", "rag", 1, .5, 0, 0, 0, 4, 4, "size, videos larger, memory access; no network cost"),
    ("C01", "ours", 1, 1, 0, 0, 0, 6, 6, "all gold points"),
    ("C01", "plain", 1, .5, 0, 1, 0, 0, 0, "tech vs psychological; no 'does not ensure'"),
    ("C01", "rag", 1, 1, 0, 0, 0, 9, 9, "all gold points"),
    ("C02", "ours", 1, 1, 0, 0, 0, 6, 6, "replace vs alter, physical existence, + hardware"),
    ("C02", "plain", 1, .5, 0, 0, 0, 0, 0, "replace vs overlay; no physical-existence point"),
    ("C02", "rag", 1, 1, 0, 0, 0, 7, 7, "replace vs alter, physical existence, tracking"),
    ("C03", "ours", 1, 1, 0, 0, 0, 4, 4, "three techniques right, examples"),
    ("C03", "plain", 0, 0, 1, 1, 0, 0, 0, "partial gait = partial body tracking and gait negation = joystick: both wrong"),
    ("C03", "rag", 1, 1, 0, 0, 0, 5, 5, "three techniques right"),
    ("C04", "ours", 1, 1, 0, 0, 0, 4, 4, "position of sensors, area restriction"),
    ("C04", "plain", 1, .5, 0, 0, 0, 0, 0, "right; no area restriction"),
    ("C04", "rag", 1, 1, 0, 0, 0, 4, 4, "right with area restriction"),
    ("C05", "ours", 1, 1, 0, 0, 0, 5, 5, "all gold points"),
    ("C05", "plain", 1, 1, 0, 1, 0, 0, 0, "breadth vs depth right; adds database"),
    ("C05", "rag", 1, 1, 0, 0, 0, 5, 5, "all gold points"),
    ("C06", "ours", 1, 1, 0, 0, 0, 5, 5, "all gold points + tests"),
    ("C06", "plain", 1, .5, 0, 0, 0, 0, 0, "right; no practice effect"),
    ("C06", "rag", 1, 1, 0, 0, 0, 4, 4, "all gold points + Latin square"),
    ("C07", "ours", 1, 1, 0, 0, 0, 4, 4, "all gold points"),
    ("C07", "plain", 1, .5, 0, 1, 0, 0, 0, "CRT-beam framing; no cost/precision"),
    ("C07", "rag", 1, 1, 0, 0, 0, 7, 7, "all gold points"),
    ("L01", "ours", 1, 1, 0, 0, 0, 1, 1, "five stages in order"),
    ("L01", "plain", 0, 0, 1, 1, 0, 0, 0, "invented stages (introduction, mapping, interpretation...)"),
    ("L01", "rag", 1, 1, 0, 0, 0, 7, 7, "five stages in order"),
    ("L02", "ours", 1, 1, 0, 0, 0, 11, 11, "internal/external, hardware, content, mismatch"),
    ("L02", "plain", .5, .5, 0, 1, 0, 0, 0, "sensory conflict, latency, FOV only"),
    ("L02", "rag", 1, 1, 0, 0, 0, 11, 11, "internal/external/hardware/content in detail"),
    ("L03", "ours", 1, 1, 0, 0, 0, 4, 4, "three fidelities with ranges"),
    ("L03", "plain", 0, 0, 1, 1, 0, 0, 0, "low/medium/high fidelity: not the course's three fidelities"),
    ("L03", "rag", 1, 1, 0, 0, 0, 3, 3, "three fidelities with definitions"),
]

if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "judgments_partial.jsonl"
    with out.open("w") as f:
        for i, s, c, comp, h, o, nc, cit, val, why in J:
            f.write(json.dumps({"id": i, "system": s, "correct": c, "complete": comp, "hallucination": bool(h),
                                "outside": bool(o), "says_not_covered": bool(nc), "citations": cit, "valid": val,
                                "reason": why, "judge": "Opus (partial pass)"}) + "\n")
    for s in ("ours", "plain", "rag"):
        rs = [x for x in J if x[1] == s]
        n = len(rs)
        print(s, n, "correct", round(sum(x[2] for x in rs) / n, 3), "halluc", sum(x[4] for x in rs),
              "cit valid", f"{sum(x[8] for x in rs)}/{sum(x[7] for x in rs)}")
