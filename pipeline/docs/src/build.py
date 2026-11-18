"""Build pipeline/docs/pipeline.html from head.html + body_*.html, filling in the prompts and real samples.

Macros in the body files:
  {{PROMPT:name.txt}}   the full prompt file, escaped, in a collapsible block
  {{S:key}}             a real sample (escaped text) computed below from the pipeline's files
"""
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WT = Path(sys.argv[1])                      # the worktree root
P = WT / "pipeline"
O = P / "output" / "nptel_vr"
A = WT / "analysis"


def J(path):
    return json.loads(Path(path).read_text())


def dump(o, indent=1):
    return json.dumps(o, indent=indent, ensure_ascii=False)


def first_lines(path, n):
    return "\n".join(Path(path).read_text().splitlines()[:n])


S = {}
# ---- 0a
srt = sorted((P / "input/nptel_vr/input/subs").rglob("lec_30.srt"))[0]
S["srt30"] = first_lines(srt, 15)
sent = J(O / "stage_0a_preprocess/lec_30.json")
times = J(O / "stage_0a_preprocess/times/lec_30.json")
S["sent30"] = dump({k: sent[k] for k in list(sent)[:3]}) + "\n\n" + dump({k: times[k] for k in list(times)[:3]})
# ---- 1a / 1b
retry = J(O / "stage_1b_verify_segments/retry/lec_30.json")
a0, a1 = retry["attempts"][0], retry["attempts"][1]
S["seg30_first"] = dump({"reasoning": a0["reasoning"], "segments": a0["segments"]})
S["seg30_problem"] = "\n".join(a0["logical_problems"]) + "\nminutes per segment: " + str(a0["minutes"])
S["seg30_retry"] = dump({"reasoning": a1["reasoning"], "segments": a1["segments"][3:5]}) + \
    "\nminutes per segment: " + str(a1["minutes"])
S["segmap30"] = dump({k: v for k, v in J(O / "stage_1b_verify_segments/segment_maps/lec_30.json").items()
                      if k in ("30/S3", "30/S4")})
S["report30"] = dump(J(O / "stage_1b_verify_segments/report.json")["lec_30"])
S["segtext30"] = first_lines(O / "stage_1c_segment_texts/lec_30/S4.txt", 6)
# ---- 2a
fm = J(O / "stage_2a_fact_extraction/fact_maps/lec_30.json")
S["facts30"] = dump({k: fm[k] for k in ("30/S4/F1", "30/S4/F2", "30/S4/F7")})
ft = [l for l in (O / "stage_2a_fact_extraction/fact_text/lec_30.txt").read_text().splitlines() if l.startswith("[30/S4/")]
S["facttext30"] = "\n".join(ft)
ck = J(O / "stage_2a_fact_extraction/checks/lec_30.json")["30/S4"]
S["factchecks30"] = dump(ck)
old = (A / "fact_extraction/data/history/test1_lec1_gemma12b").rglob("*.txt")
oldlines = []
for f in sorted(old):
    for l in f.read_text().splitlines():
        if l.startswith("[1/S0/F0]") or l.startswith("[1/S5/F4]") or l.startswith("[1/S5/F5]"):
            oldlines.append(l)
S["oldfacts1"] = "\n".join(dict.fromkeys(oldlines))
newl = (O / "stage_2b_verify_facts/fact_text/lec_1.txt").read_text().splitlines()
S["newfacts1"] = "\n".join(l for l in newl if l.startswith("[1/S1/F0]") or l.startswith("[1/S2/F0]"))
# ---- 2c
cm = J(O / "stage_2c_concepts/concept_maps/lec_30.json")
rl = J(O / "stage_2c_concepts/relations/lec_30.json")
S["concepts30"] = dump({k: cm[k] for k in ("30/S4/C3", "30/S4/C5", "30/S4/C8")})
S["relations30"] = dump({k: rl[k] for k in ("30/S4/R2", "30/S4/R4", "30/S4/R7")})
# ---- 3
dec = [json.loads(l) for l in (O / "stage_3_registry/decisions.jsonl").read_text().splitlines() if l.strip()]
S["dec_headset"] = dump([d for d in dec if d.get("kind") == "model" and d.get("concept") == "C0005"][0])
S["dec_exact"] = dump(dec[0])
reg = J(O / "stage_3_registry/concepts.json")["C1574"]
reg = {k: v for k, v in reg.items()}
S["reg_hrtf"] = dump(reg)
# ---- 4a
d = J(O / "stage_4a_definitions/definitions.json")
S["def_hrtf"] = dump(d["C1574"])
S["def_control"] = dump({k: d["C2091"][k] for k in ("name", "definition", "defined", "facts")})
# ---- 4b
S["goals30"] = dump(J(O / "stage_4b_goals/lecture_goals/lec_30.json"))
cg = J(O / "stage_4b_goals/course_goals.json")
S["coursegoal"] = dump({"G5": cg["goals"]["G5"]})
# ---- 4c
need = J(O / "stage_4c_lecture_graph/needed/lec_30.json")
S["needed30"] = dump({"lecture": need["lecture"], "direct": need["direct"]})
gck = J(O / "stage_4c_lecture_graph/checks.json")["totals"]
S["graphtotals"] = dump({k: v for k, v in gck.items() if k != "assumed_concepts"} | {"assumed_concepts": f"[{len(gck['assumed_concepts'])} concept IDs]"})
# ---- 4d
kc = J(O / "knowledge/concepts.json")["C1574"]
kc = {k: v for k, v in kc.items() if k not in ("merged",)}
S["card_hrtf"] = dump(kc)
S["fact_store"] = dump({"30/S4/F6": J(O / "knowledge/facts.json")["30/S4/F6"]})
names = J(O / "knowledge/names.json")
S["names"] = dump({"hrtf": names["hrtf"], "2d": names["2d"]})
idx = J(O / "knowledge/index.json")
S["index"] = dump({k: v for k, v in idx.items() if k not in ("lectures", "files")})
# ---- 5
acts = {x["id"]: x for x in J(O / "activities/lec_30.json")["activities"]}
q = acts["30/A9"]["data"]["questions"][0]
S["quiz30"] = dump(q)
cw = acts["30/A14"]["data"]
S["cross30"] = dump({"width": cw["width"], "height": cw["height"], "entries": cw["entries"][:2]})
S["odd30"] = dump(acts["30/A15"]["data"]["items"][0])
S["recap30"] = dump(acts["30/A10"]["data"])
S["open30"] = dump(acts["30/A16"]["data"]["questions"][0])
S["recall30"] = dump({"items": acts["30/A0"]["data"]["items"][:2]})
S["pairs30"] = dump(acts["30/A13"]["data"]["pairs"][2])
cmd = acts["30/A12"]["data"]
S["blank30"] = dump({"blank": cmd["blanks"][1], "edge": cmd["edges"][cmd["blanks"][1]["edge"]]})
cards = J(O / "activities/course.json")["spaced_review"]["cards"]
S["card30"] = dump([c for c in cards if c["concept"] == "C1574"][0])
chk = J(O / "activities/checks.json")
cwj = chk["lectures"]["30"]["crossword"]
cwj = cwj if "judge" in cwj else list(cwj.values())[0]
S["verdict30"] = dump(cwj["judge"]["rounds"][0]["verdicts"][3])
S["judgetotals"] = dump(chk["totals"]["judge"])
S["acttotals"] = dump({"activities": chk["totals"]["activities"], "retried": chk["totals"]["retried"],
                       "unresolved": chk["totals"]["unresolved"], "dropped_items": chk["totals"]["dropped_items"]})
# ---- QA
bench = {(r["id"], r["run"]): r for r in map(json.loads, (A / "qa/bench_vllm_shipped.jsonl").read_text().splitlines())}
def qa(i):
    r = bench[(i, 0)]
    return dump({"question": r["question"], "seconds": r["seconds"], "steps": r["steps"], "covered": r["covered"]}) + \
        "\n\n" + r["answer"]
S["qa_b14"] = qa("B14")
S["qa_b04"] = qa("B04")
S["qa_b02"] = qa("B02")
S["qa_b09"] = qa("B09")
nl = {(r["id"], r["run"]): r for r in map(json.loads, (A / "qa/bench_think_newlayer.jsonl").read_text().splitlines())}
r = nl[("B07", 0)]
S["qa_b07"] = dump({"question": r["question"], "seconds": r["seconds"], "timing": r["timing"], "steps": r["steps"]}) + \
    "\n\n" + r["answer"]

# ---- MVP quiz example (git tag), passed in as a file
mvpq = HERE / "mvp_18.json"
if mvpq.exists():
    a = json.loads(mvpq.read_text())
    x = [x for x in a["activities"] if x["id"] == "18/A18"][0]
    S["mvp_quiz"] = dump(x["data"]["questions"][1])
v1 = HERE / "v1_course.json"
if v1.exists():
    c = json.loads(v1.read_text())
    x = [x for x in c["concepts"] if x["id"] == "C001"][0]
    S["v1_xr"] = dump({k: x[k] for k in ("id", "name", "aliases", "definition")})
kc1 = J(O / "knowledge/concepts.json")["C0001"]
S["v3_xr"] = dump({"id": "C0001", "name": kc1["name"], "aliases": kc1["aliases"], "definition": kc1["definition"],
                   "defined_in": [{k: d[k] for k in ("lecture", "segment", "start")} for d in kc1["defined_in"]]})
for f in ("old_fact_prompt.txt", "mvp_quiz_prompt.txt", "v1_segment_prompt.txt", "v2_links_prompt.txt",
          "old_recap_judge.txt"):
    p = HERE / f
    if p.exists():
        S[f] = p.read_text().rstrip("\n")


sys.path.insert(0, str(HERE))
import evals  # noqa: E402
S_EVAL = evals.build(WT, HERE)
_q30 = J(O / "activities/checks.json")["lectures"]["30"]["quiz"]["quiz:30/S0"]["retry"]
S["retry30"] = "\n".join(_q30["problems"][0]) if isinstance(_q30["problems"][0], list) else str(_q30["problems"][0])


def prompt_block(name):
    text = (P / "prompts" / name).read_text()
    n = len(text.splitlines())
    return (f'<details class="prompt"><summary><span class="mono">prompts/{name}</span>'
            f'<span class="meta">{n} lines · {len(text):,} characters · the full file</span></summary>'
            f'<pre data-lang="{"json" if name.endswith(".json") else "prompt"}">{html.escape(text)}</pre></details>')


body = "".join(f.read_text() for f in sorted(HERE.glob("body_*.html")))
missing = []


def sub_s(m):
    k = m.group(1)
    if k not in S:
        missing.append(k)
        return f"[missing sample {k}]"
    return html.escape(S[k])


body = re.sub(r"\{\{PROMPT:([\w.]+)\}\}", lambda m: prompt_block(m.group(1)), body)
body = re.sub(r"\{\{S:([\w.]+)\}\}", sub_s, body)
body = re.sub(r"\{\{FILE:([\w./-]+)\}\}", lambda m: html.escape((WT / m.group(1)).read_text().rstrip("\n")), body)
body = re.sub(r"\{\{EVAL:(\w+)\}\}", lambda m: S_EVAL.get(m.group(1), f"[missing eval {m.group(1)}]"), body)
out = (HERE / "head.html").read_text().replace("{{BODY}}", body)
dest = P / "docs" / "pipeline.html"
dest.write_text(out)
print(dest, len(out), "bytes; missing samples:", missing)
used = set(re.findall(r"\{\{PROMPT:([\w.]+)\}\}", "".join(f.read_text() for f in HERE.glob("body_*.html"))))
allp = {p.name for p in (P / "prompts").iterdir()}
print("prompts not included:", sorted(allp - used))
