"""Compact judge packets: for each question, the gold answer and sources, then every (system, run) answer that is not
yet in judgments.jsonl. Citations are not shown: their validity is checked by code (citations.py, summarize.py).

    python3 baseline-tests/render_for_judge.py            # judge/todo_<NN>.txt, about 24 answers per packet
"""
import json

from common import OUT

SYSTEMS = ["ours", "plain", "rag", "rag_think", "graphrag_text", "graphrag_notext", "abl_facts", "abl_graph",
           "ours_v2", "ours_v2_nothink"]
J = OUT / "judge"
J.mkdir(exist_ok=True)
PER_PACKET = 24


def run_files():
    """{(system, run): {qid: record}} for every runs/<system>.jsonl (run 1) and runs/<system>_r<N>.jsonl."""
    out = {}
    for s in SYSTEMS:
        for p in sorted((OUT / "runs").glob(f"{s}*.jsonl")):
            rest = p.stem[len(s):]
            if rest == "":
                run = 1
            elif rest.startswith("_r") and rest[2:].isdigit():
                run = int(rest[2:])
            else:
                continue
            out[(s, run)] = {json.loads(x)["id"]: json.loads(x) for x in p.open()}
    return out


def judged():
    p = OUT / "judgments.jsonl"
    return {(j["qid"], j["system"], j["run"]) for j in map(json.loads, p.open())} if p.exists() else set()


def main():
    qs = [json.loads(x) for x in (OUT / "questions.jsonl").open()]
    runs, done = run_files(), judged()
    for old in J.glob("todo_*.txt"):
        old.unlink()
    packets, cur, n_cur = [], [], 0
    for q in qs:
        todo = [(s, r) for (s, r) in sorted(runs, key=lambda k: (SYSTEMS.index(k[0]), k[1]))
                if q["id"] in runs[(s, r)] and (q["id"], s, r) not in done]
        if not todo:
            continue
        lines = [f"## {q['id']} [{q['category']}, expect {q['expect']}] {q['question']}", f"GOLD: {q['gold_answer']}"]
        for s, r in todo:
            a = (runs[(s, r)][q["id"]].get("answer") or "").strip() or "(empty)"
            lines.append(f"-- {s} r{r}: {a}")
        cur.append("\n".join(lines))
        n_cur += len(todo)
        if n_cur >= PER_PACKET:
            packets.append(cur)
            cur, n_cur = [], 0
    if cur:
        packets.append(cur)
    for i, p in enumerate(packets):
        (J / f"todo_{i:02d}.txt").write_text("\n\n".join(p) + "\n")
    print(f"{len(packets)} packets in {J}")


if __name__ == "__main__":
    main()
