"""Agreement between the two judges on the answers both judged: Opus (judgments_opus.jsonl, the earlier pass, 257
answers: ours, plain, rag, abl_facts on all 53 questions, abl_graph on 45) and Sonnet (judgments.jsonl, every answer;
for the ablations, its judgments of the same first, unrestricted runs: runs/invalid/).

    python3 baseline-tests/judge_agreement.py      # judge_agreement.json + judge_agreement.md
"""
import json
from collections import defaultdict

from common import OUT


def load(name, unrestricted=False):
    """unrestricted: label abl_* as abl_*_unrestricted (the first ablation runs, which had the full tool set by a bug
    in restrict_tools; Opus judged those texts, so they are compared with Sonnet's judgments of the same texts)."""
    out = {}
    for j in map(json.loads, (OUT / name).open()):
        s = j["system"] + ("_unrestricted" if unrestricted and j["system"].startswith("abl_") else "")
        out[(j["qid"], s, j["run"])] = j
    return out


def main():
    o = load("judgments_opus.jsonl", unrestricted=True)
    s = {k: v for k, v in load("judgments.jsonl").items() if not k[1].startswith("abl_")}
    s.update(load("runs/invalid/judgments_sonnet_unrestricted.jsonl", unrestricted=True))
    keys = sorted(set(o) & set(s))
    cats = {q["id"]: q["category"] for q in map(json.loads, (OUT / "questions.jsonl").open())}
    out = {"n": len(keys), "only_opus": len(set(o) - set(s))}
    exact = sum(o[k]["correct"] == s[k]["correct"] for k in keys)
    within = sum(abs(o[k]["correct"] - s[k]["correct"]) <= 0.5 for k in keys)
    h_both = sum((o[k]["hallucinations"] > 0) == (s[k]["hallucinations"] > 0) for k in keys)
    out.update(correct_exact=exact / len(keys), correct_within_half=within / len(keys),
               halluc_flag_agree=h_both / len(keys))
    # Cohen's kappa on the three correct levels
    levels = [0, 0.5, 1]
    po = exact / len(keys)
    pe = sum((sum(o[k]["correct"] == L for k in keys) / len(keys)) * (sum(s[k]["correct"] == L for k in keys) / len(keys))
             for L in levels)
    out["correct_kappa"] = (po - pe) / (1 - pe) if pe < 1 else 1.0
    # per system: mean correct under each judge (does the judge change the ranking?)
    per = defaultdict(lambda: [0, 0.0, 0.0, 0, 0])
    for k in keys:
        p = per[k[1]]
        p[0] += 1; p[1] += o[k]["correct"]; p[2] += s[k]["correct"]
        p[3] += o[k]["hallucinations"] > 0; p[4] += s[k]["hallucinations"] > 0
    out["per_system"] = {sy: {"n": n, "correct_opus": a / n, "correct_sonnet": b / n,
                              "halluc_answers_opus": ho, "halluc_answers_sonnet": hs}
                         for sy, (n, a, b, ho, hs) in sorted(per.items())}
    out["disagreements"] = [{"qid": k[0], "system": k[1], "run": k[2], "category": cats.get(k[0]),
                             "opus": o[k]["correct"], "sonnet": s[k]["correct"],
                             "opus_note": o[k].get("note"), "sonnet_note": s[k].get("note")}
                            for k in keys if o[k]["correct"] != s[k]["correct"]]
    (OUT / "judge_agreement.json").write_text(json.dumps(out, indent=1) + "\n")
    L = ["# Judge agreement (Opus vs Sonnet)", "",
         f"{out['n']} answers judged by both. correct: exact {out['correct_exact']:.3f}, within 0.5 "
         f"{out['correct_within_half']:.3f}, Cohen's kappa {out['correct_kappa']:.3f}; hallucination flag (any vs none) "
         f"agrees on {out['halluc_flag_agree']:.3f}.", "",
         "| system | n | correct (Opus) | correct (Sonnet) | answers with hallucination (Opus) | (Sonnet) |",
         "|---|---|---|---|---|---|"]
    for sy, d in out["per_system"].items():
        L.append(f"| {sy} | {d['n']} | {d['correct_opus']:.3f} | {d['correct_sonnet']:.3f} | "
                 f"{d['halluc_answers_opus']} | {d['halluc_answers_sonnet']} |")
    L += ["", f"## Disagreements on correct ({len(out['disagreements'])})", "",
          "| qid | system | run | Opus | Sonnet | Opus note | Sonnet note |", "|---|---|---|---|---|---|---|"]
    for d in out["disagreements"]:
        L.append(f"| {d['qid']} | {d['system']} | {d['run']} | {d['opus']} | {d['sonnet']} | {d['opus_note']} | "
                 f"{d['sonnet_note']} |")
    (OUT / "judge_agreement.md").write_text("\n".join(L) + "\n")
    print("\n".join(L[:12]))


if __name__ == "__main__":
    main()
