"""Judge packets: for each question, the gold answer and sources, then each system's answer with every citation
and the course text at it (citations.py). Written to judge/packet_<first id>.txt in batches, read by the judge.

    python3 baseline-tests/render_for_judge.py            # all questions, batches of 6
"""
import json

from citations import ours_citations, written_citations
from common import OUT

SYSTEMS = ["ours", "plain", "rag", "graphrag"]
J = OUT / "judge"
J.mkdir(exist_ok=True)


def load():
    qs = [json.loads(x) for x in (OUT / "questions.jsonl").open()]
    runs = {}
    for s in SYSTEMS:
        p = OUT / "runs" / f"{s}.jsonl"
        runs[s] = {json.loads(x)["id"]: json.loads(x) for x in p.open()} if p.exists() else {}
    return qs, runs


def cites(system, rec):
    return ours_citations(rec) if system == "ours" else written_citations(rec.get("answer", ""))


def render(q, runs) -> str:
    out = [f"######## {q['id']} [{q['category']}, expect {q['expect']}] {q['question']}",
           f"GOLD: {q['gold_answer']}", f"SOURCES: {'; '.join(q['gold_sources'])}"]
    for s in SYSTEMS:
        rec = runs[s].get(q["id"])
        if not rec:
            out.append(f"--- {s}: (no run)")
            continue
        out.append(f"--- {s}  ({rec.get('seconds')} s, ctx {rec.get('context_tokens')} tok"
                   + (f", steps {[x['tool'] for x in rec.get('steps', [])]}" if s == "ours" else "") + ")")
        out.append(rec.get("answer", "").strip() or f"(empty; error {rec.get('error')})")
        for n, c in enumerate(cites(s, rec), 1):
            if s == "ours":
                out.append(f"   c{n} {c['id']} (L{c['lecture']} {c['time']}) ov={c['auto_overlap']}: {c['source_text']}")
            else:
                out.append(f"   c{n} L{c['lecture']} {c['time']} ov={c['auto_overlap']} n={c['window_sentences']}: "
                           + " || ".join(c["best_sentences"]))
    return "\n".join(out)


def main():
    qs, runs = load()
    for i in range(0, len(qs), 6):
        batch = qs[i:i + 6]
        (J / f"packet_{i // 6:02d}.txt").write_text("\n\n".join(render(q, runs) for q in batch) + "\n")
    print(f"{(len(qs) + 5) // 6} packets in {J}")


if __name__ == "__main__":
    main()
