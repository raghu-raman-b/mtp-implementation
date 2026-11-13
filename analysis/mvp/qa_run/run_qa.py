"""Ask the MVP question set in one process; logs and caches stay in analysis/mvp/qa_run (QA_OUTPUT). Read-only on pipeline/.
    QA_OUTPUT=analysis/mvp/qa_run/out QA_CONFIG=analysis/mvp/qa_run/gemma4_12b_llamacpp.json python3 analysis/mvp/qa_run/run_qa.py"""
import json, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "pipeline"))
import qa
Q = [
 ("Q01", "definition", "What is extended reality?", None),
 ("Q02", "definition", "What is presence in virtual reality?", None),
 ("Q03", "how", "How does inside looking out infrared tracking work?", None),
 ("Q04", "how", "How is a cheap gyroscope calibrated using the constants C1 and C2?", "17"),
 ("Q05", "compare", "How is augmented reality different from virtual reality?", None),
 ("Q06", "compare", "What is the difference between optical see-through and video see-through head-mounted displays?", None),
 ("Q07", "compare", "How do full gait, partial gait and gait negation locomotion techniques differ?", None),
 ("Q08", "list", "What are the causes of cybersickness?", None),
 ("Q09", "list", "What are the five stages of contextual inquiry?", None),
 ("Q10", "list", "What are the parts of the human hearing system?", None),
 ("Q11", "where", "In which lecture is stereoscopy taught?", None),
 ("Q12", "where", "Where does the course explain the uncanny valley?", None),
 ("Q13", "prereq", "What do I need to know before lecture 40?", None),
 ("Q14", "purpose", "What is lecture 51 for?", None),
 ("Q15", "acronym", "What is an IMU?", None),
 ("Q16", "acronym", "what is HRTF", None),
 ("Q17", "misspelling", "what is cybersicknes", None),
 ("Q18", "misspelling", "explain steroscopy", None),
 ("Q19", "not_covered", "How does a Kalman filter fuse IMU and camera data for tracking?", None),
 ("Q20", "not_covered", "What is the vergence-accommodation conflict in VR headsets?", None),
 ("Q21", "later_tracking", "What is drift correction in tracking and why is it needed?", None),
 ("Q22", "later_display", "What is the field of view and why does it matter for cybersickness?", None),
 ("Q23", "later_perception", "Why is peripheral vision better at detecting movement than central vision?", None),
 ("Q24", "later_interaction", "What is the world in miniature technique for object manipulation?", None),
 ("Q25", "later_cybersickness", "How does teleportation help reduce cybersickness?", None),
 ("Q26", "later_rendering", "Why are GPUs used for rendering in VR?", None),
 ("Q27", "later_haptics", "What kinds of haptic feedback devices does the course mention?", None),
 ("Q28", "later_methods", "Which statistical test should I use for a within-subject design with one factor at two levels?", None),
 ("Q29", "not_covered", "Who won the 2022 FIFA World Cup?", None),
 ("Q30", "list", "What are the three characteristics of a virtual reality system?", "4"),
 ("Q31", "compare", "What is the difference between immersion and presence?", None),
 ("Q32", "compare", "How do electromagnetic and acoustic tracking differ?", None),
 ("Q33", "purpose", "What is lecture 36 for?", None),
 ("Q34", "how", "How does the Wizard of Oz approach work?", None),
 ("Q35", "prereq", "What do I need to know before lecture 16?", None),
 ("Q36", "prereq", "What do I need to know before lecture 30?", None),
]
import os
if os.environ.get("QA_RUN_TAG"):
    out_name = "results_" + os.environ["QA_RUN_TAG"] + ".jsonl"
else:
    out_name = "results.jsonl"
only = set(sys.argv[1:])
out = HERE / out_name
t0 = time.time(); qa.warm("nptel_vr"); print(f"warm {time.time()-t0:.1f}s", flush=True)
for qid, kind, q, lec in Q:
    if only and qid not in only: continue
    t = time.time()
    r = qa.answer(q, course="nptel_vr", lecture=lec)
    dt = time.time() - t
    rec = {"id": qid, "kind": kind, "question": q, "lecture": lec, "seconds": round(dt, 1), "covered": r["covered"],
           "tools": [s["tool"] for s in r["steps"]], "steps": r["steps"], "answer": r["answer"],
           "citations": r["citations"]}
    with open(out, "a") as f: f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"{qid} {dt:6.1f}s tools={rec['tools']} cites={len(r['citations'])} covered={r['covered']}", flush=True)
