"""The Ask screen's sample questions (pipeline/viewer/sample_questions.json), chosen by code from the judged runs.

    python3 baseline-tests/make_samples.py <path to pipeline/viewer/sample_questions.json>

Rule: a question is a sample when ours' mean correct over its runs is higher than every baseline's mean (plain, rag,
rag_think, graphrag_text, graphrag_notext) and no run of ours has a hallucination. Ordered by margin (ours minus the
best baseline), then by question ID. `lecture` is null: every sample is asked from the course-wide Ask screen.
"""
import json
import sys
from collections import defaultdict

from common import OUT

BASELINES = ["plain", "rag", "rag_think", "graphrag_text", "graphrag_notext"]


def main():
    dest = sys.argv[1]
    runs = defaultdict(list)
    for j in map(json.loads, (OUT / "judgments.jsonl").open()):
        runs[(j["qid"], j["system"])].append(j)

    def mean(q, s):
        v = [j["correct"] for j in runs[(q, s)]]
        return sum(v) / len(v) if v else None

    picks = []
    for q in map(json.loads, (OUT / "questions.jsonl").open()):
        ours = mean(q["id"], "ours")
        best = max((m for s in BASELINES if (m := mean(q["id"], s)) is not None), default=None)
        if ours is None or best is None or ours <= best:
            continue
        if any(j["hallucinations"] for j in runs[(q["id"], "ours")]):
            continue
        picks.append((-(ours - best), q["id"], q))
    picks.sort(key=lambda x: (x[0], x[1]))
    out = {"note": "The Ask screen's sample questions (GET /api/samples), made by baseline-tests/make_samples.py: "
                   "questions where our system's judged answers beat every baseline (plain LLM, RAG, RAG with "
                   "thinking, GraphRAG with and without text) and had no hallucination. category: definition | "
                   "explanation | comparison | list | formula | where | prerequisite | structure | not_covered | "
                   "multihop; lecture: null or the lecture the question is asked from.",
           "questions": [{"q": q["question"][0].upper() + q["question"][1:].rstrip("?") + "?",
                          "category": q["category"], "lecture": None, "id": q["id"]} for _, _, q in picks]}
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"{len(picks)} samples -> {dest}: {', '.join(i for _, i, _ in picks)}")


if __name__ == "__main__":
    main()
