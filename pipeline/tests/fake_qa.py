"""Plumbing test of question answering (qa/) with a scripted fake model over the synthetic knowledge layer.

    python3 tests/fake_qa.py [--layer DIR] [--keep]

The synthetic layer is the one tests/fake_knowledge.py builds (8 lectures, 11 concepts, fake embeddings); it is built
in a new temporary folder (or taken from --layer, a folder holding output/nptel_vr/knowledge) and copied into a
second temporary folder that $QA_OUTPUT points at, so qa reads and logs only there. The fake model (QAFake below,
over scripts/llm/fake_server.py) listens on a free port (never 8091/8092, the local Gemma servers, nor 8094/8095,
the SSH forward to the EC2) and answers by script, keyed by the question: it asks for tool calls through the OpenAI
tools API and writes its answer from the IDs in the tool results it was sent.

What it looks for (each line is what a broken piece would show):
  client   a request without tools carrying "tools" or "tool_choice" (the request hashes of the stages would change);
           tool calls not returned on the Result, or lost when answered from the cache
  tools    the tool list sent not matching prompts/qa_tools.json and qa/tools.py; the system prompt without the
           lectures; the learner's lecture not passed on
  loop     a tool call not executed, executed with other arguments, or its result not sent back under its call ID;
           two calls in one message not both run in order; a repeated call run again; a bad tool name or bad
           arguments ending the loop instead of going back to the model; the loop not forcing an answer
           (tool_choice "none") after MAX_ROUNDS rounds; thinking not on in round 0 and off in every later round
           (the config's other chat-template switches kept)
  early    when every tool result so far found nothing close (an unknown name whose closest facts score low, a
           fact_lookup with no close fact), the next round not being the answer (tool_choice "none", the nudge
           last) or the log not saying so; an early answer forced when one result found something, or after a
           bad tool call
  names    an acronym, a plural or a misspelt name not finding its concept; an unknown name not saying "unknown",
           not pointing to fact_lookup, or not showing its closest facts (which the answer may cite)
  answers  a citation that is not a fact (or segment) of the layer, or whose lecture, segment, time or text differ
           from the layer's; an ID no tool returned kept; a raw ID left in the answer; the lecture and time not
           written into the answer; an uncovered question giving covered true; covered not following the COVERED
           line, or a missing line not falling back to "anything cited"
  tidy     a time the model wrote before a citation ("at 26:57 [ID]", "(26:57-27:07) [ID]") kept, or a number
           without a lead-in ("16:9 [ID]") removed; a run of the same label not written once (at its end); a list
           whose items share one label not getting it once on its lead-in line; a label dropped from a list item
           when the items do not all share it; a citation lost by the tidying
  graph    lecture_dependencies not giving the hand-worked answers: lecture 6 relies on stereoscopy (2 of its
           facts; first defined in lecture 2, with its defining facts 2/S2/F3, 2/S2/F4) and so revises lecture 2,
           names extended reality and virtual reality as in passing and latency as introduced; lecture 8 relies on
           nothing earlier (display resolution, rendering, stereoscopy and virtual reality once each: in passing)
  cli      python -m qa not printing the result as JSON
  log      a question not logged to <output>/<course>/qa/answers.jsonl
  output   any file under the real output/ created or changed
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the pipeline folder
sys.path.insert(0, str(ROOT))

from scripts.llm import LLM, LLMConfig, Request  # noqa: E402
from scripts.llm.fake_server import FakeServer  # noqa: E402

COURSE = "nptel_vr"
FORBIDDEN = {8091, 8092, 8094, 8095}
FAILURES: list[str] = []
ID = re.compile(r"\b\d+/S\d+(?:/F\d+)?\b")


def check(ok: bool, what: str):
    print(f"  {'ok  ' if ok else 'FAIL'} {what}", flush=True)
    if not ok:
        FAILURES.append(what)


def snapshot(folder: Path) -> dict:
    return {str(p.relative_to(folder)): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in folder.rglob("*") if p.is_file()}


def free_port() -> int:
    while True:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        if port not in FORBIDDEN:
            return port


# ---------------------------------------------------------------- the scripted fake model
def call(name: str, args, i: int = 0) -> dict:
    return {"id": f"call_{name}_{i}", "type": "function",
            "function": {"name": name, "arguments": args if isinstance(args, str) else json.dumps(args)}}


def ids_in(text: str, facts_only: bool = True) -> list[str]:
    return [i for i in dict.fromkeys(ID.findall(text)) if "/F" in i or not facts_only]


class QAFake(FakeServer):
    """Answers by the question (the user message's first line). bodies: every request, for the checks."""
    bodies: list = []

    def answer(self, body: dict) -> dict:
        self.bodies.append(body)
        msgs = body["messages"]
        q = next(m["content"] for m in msgs if m["role"] == "user").split("\n")[0]
        rnd = sum(1 for m in msgs if m["role"] == "assistant")
        tools = [m["content"] for m in msgs if m["role"] == "tool"]
        last = tools[-1] if tools else ""
        out = self.script(q, rnd, last, tools, msgs, body)
        msg = {"content": out, "tool_calls": None} if isinstance(out, str) else {"content": "", "tool_calls": out}
        return {"choices": [{"message": {**msg, "reasoning_content": "fake thinking"},
                             "finish_reason": "stop" if isinstance(out, str) else "tool_calls"}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 10}}

    @staticmethod
    def script(q: str, rnd: int, last: str, tools: list, msgs: list, body: dict):
        if q == "What is an HMD?":
            if rnd == 0:
                return [call("check_concept", {"name": "HMD"})]
            a, b = ids_in(last)[:2]
            return f"An HMD is a display worn on the head [{a}]. It is defined early [{b}, 9/S9/F9].\nCOVERED: yes"
        if q == "What is a vergence lens?":
            if rnd == 0:
                return [call("check_concept", {"name": "vergence lens"})]
            if body.get("tool_choice") == "none":     # the closest facts came with "unknown": answer from them
                return f"The course mentions something close [{ids_in(last)[0]}].\nCOVERED: partly"
            if "unknown" in last and "fact_lookup" in last:
                return [call("fact_lookup", {"query": "vergence lens", "rephrasings": ["lens for vergence"]})]
            return "I do not know.\nCOVERED: no"
        if q == "Vergence lens and HMD":
            if rnd == 0:
                return [call("check_concept", {"name": "vergence lens"}, 0), call("check_concept", {"name": "HMD"}, 1)]
            return f"An HMD is worn on the head [{ids_in(tools[-1])[0]}].\nCOVERED: partly"
        if q == "Repeated labels":
            if rnd == 0:
                return [call("check_concept", {"name": "stereoscopy"})]
            a, b, c = ids_in(last)[:3]
            return (f"Stereoscopy is taught at 26:57 [{a}]. It is a fake concept [{a}]. Its screens are 16:9 [{c}]. "
                    f"It goes on from 26:57 to 27:07 [{a}, {b}], (26:57-27:07) [{b}].\n\nIts points are:\n"
                    f"- point 0 [{a}]\n- point 1 [{a}]\n\nAgain [{a}] and [{c}].\n\nMixed:\n- one [{a}]\n"
                    f"- two [{a}]\n- three [{c}]\nCOVERED: yes")
        if q == "Who won the 1998 football world cup?":
            if rnd == 0:
                return [call("fact_lookup", {"query": "1998 football world cup winner"})]
            return "The course does not cover this.\nCOVERED: no"
        if q == "What do I need before lecture 6?":
            if rnd == 0:
                return [call("lecture_dependencies", {"lecture": "6"})]
            return f"Lecture 6 builds on stereoscopy from lecture 2 [{ids_in(last)[0]}].\nCOVERED: yes"
        if q == "What is this lecture for?":
            if rnd == 0:
                m = re.search(r"watching lecture (\w+)", msgs[1]["content"])
                return [call("lecture_overview", {"lecture": int(m[1]) if m else 0})]
            s = ids_in(last, facts_only=False)
            return f"It explains the meanings of the words [{s[0]}] and the defining characteristics [{s[1]}].\n" \
                   "COVERED: yes"
        if q == "How do HMDs and tracking relate?":
            if rnd == 0:
                return [call("check_concept", {"name": "HMDs"}, 0), call("check_concept", {"name": "tracking"}, 1)]
            a, b = ids_in(tools[-2])[0], ids_in(tools[-1])[0]
            return f"An HMD shows the virtual world [{a}] and tracking follows the head [{b}].\nCOVERED: yes"
        if q == "What is strereoscopy?":
            if rnd == 0:
                return [call("check_concept", {"name": "strereoscopy"})]
            return f"Stereoscopy is explained in lecture 2 ({ids_in(last)[0]}).\nCOVERED: yes"
        if q == "Keep calling tools":
            if body.get("tool_choice") == "none":
                return "Here is what I found [7/S9/F9].\nCOVERED: yes"
            return [call("check_concept", {"name": "VR"} if rnd % 2 == 0 else {"name": "rendering"})]
        if q == "Call a broken tool":
            if rnd == 0:
                return [call("no_such_tool", {}, 0), call("check_concept", "{not json", 1),
                        call("lecture_overview", {"lecture": "99"}, 2)]
            return "Sorry, nothing found.\nCOVERED: no"
        if q == "No covered line, with a citation":
            if rnd == 0:
                return [call("check_concept", {"name": "rendering"})]
            return f"Rendering is taught in lecture 4 [{ids_in(last)[0]}]."
        if q == "No covered line, nothing cited":
            return "I cannot tell."
        if q == "Yes without citations":
            if rnd == 0:
                return [call("check_concept", {"name": "rendering"})]
            return "Rendering is a big topic.\nCOVERED: yes"
        if q == "What is this course about?":
            if rnd == 0:
                return [call("course_goals", {})]
            return "It explains the basics and then applies them.\nCOVERED: yes"
        return "fake answer\nCOVERED: no"


# ---------------------------------------------------------------- the tests
def build_layer(work: Path) -> Path:
    """Run tests/fake_knowledge.py into work/layer and return its knowledge folder."""
    layer = work / "layer"
    r = subprocess.run([sys.executable, str(ROOT / "tests" / "fake_knowledge.py"), "--work", str(layer), "--keep"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-3000:], r.stderr[-3000:])
        sys.exit("tests/fake_knowledge.py failed: no synthetic layer")
    return layer / "output" / COURSE / "knowledge"


def test_client(cfg: LLMConfig, server: QAFake, work: Path):
    print("client: tools on Request and Result", flush=True)
    llm = LLM(cfg, log=lambda *a: None)
    plain = llm._body(Request(prompt="hi"), 0)
    check("tools" not in plain and "tool_choice" not in plain,
          "a request without tools sends neither 'tools' nor 'tool_choice' (stage hashes unchanged)")
    from qa import tool_specs
    req = Request(prompt="What is an HMD?", tools=tool_specs(), tool_choice="auto")
    cache = work / "client_cache.jsonl"
    r1 = llm.generate(req, cache_file=cache)
    r2 = llm.generate(req, cache_file=cache)
    check(r1.tool_calls and r1.tool_calls[0]["function"]["name"] == "check_concept" and not r1.cached,
          "tool calls returned on the Result")
    check(r2.cached and r2.tool_calls == r1.tool_calls, "tool calls kept in the cache and returned from it")
    sent = server.bodies[-1]
    check([t["function"]["name"] for t in sent.get("tools", [])] == ["check_concept", "fact_lookup",
                                                                    "lecture_dependencies", "lecture_overview",
                                                                    "course_goals"]
          and sent.get("tool_choice") == "auto", "the five tools and tool_choice sent to the server")


def facts_of(layer: Path) -> tuple[dict, dict]:
    facts = json.loads((layer / "facts.json").read_text())
    lectures = {p.stem.removeprefix("lec_"): json.loads(p.read_text()) for p in (layer / "lectures").glob("*.json")}
    return facts, lectures


def real_citations(r: dict, facts: dict, lectures: dict) -> bool:
    for c in r["citations"]:
        if c["fact"]:
            f = facts.get(c["fact"])
            if not f or (f["lecture"], f["segment"], f["start"], f["end"], f["text"]) != \
                    (c["lecture"], c["segment"], c["start"], c["end"], c["text"]):
                return False
        else:
            s = lectures.get(c["lecture"], {}).get("segments", {}).get(c["segment"])
            if not s or (s["start"], s["end"], s["subgoal"]) != (c["start"], c["end"], c["text"]):
                return False
    return True


def test_answers(cfg: LLMConfig, server: QAFake, layer: Path):
    import qa
    from qa.answer import MAX_ROUNDS, FINAL_NUDGE
    llm = LLM(cfg, log=lambda *a: None)
    facts, lectures = facts_of(layer)
    ask = lambda q, **kw: qa.answer(q, course=COURSE, llm=llm, **kw)  # noqa: E731
    tools_of = lambda r: [s["tool"] for s in r["steps"]]  # noqa: E731

    print("a concept by its acronym", flush=True)
    n0 = len(server.bodies)
    r = ask("What is an HMD?")
    b0, b1 = server.bodies[n0], server.bodies[n0 + 1]
    check(set(r) == {"answer", "citations", "steps", "covered"}, "the result has exactly the four keys")
    check(tools_of(r) == ["check_concept"] and r["steps"][0]["args"] == {"name": "HMD"}
          and "head-mounted display" in r["steps"][0]["result_summary"],
          f"check_concept('HMD') run and finds head-mounted display ({r['steps'][0]['result_summary']})")
    check("THE LECTURES OF THE COURSE" in b0["messages"][0]["content"] and "4: Definitions" in
          b0["messages"][0]["content"], "the system prompt lists the course's lectures")
    tm = [m for m in b1["messages"] if m["role"] == "tool"]
    check(len(tm) == 1 and tm[0]["tool_call_id"] == "call_check_concept_0" and "CONCEPT head-mounted display"
          in tm[0]["content"], "the tool's result sent back under its call ID, after the assistant's call")
    check([c["fact"] for c in r["citations"]] == ["2/S0/F2", "2/S0/F3"] and real_citations(r, facts, lectures),
          "citations: the cited facts, with the layer's lecture, segment, time and text")
    check("9/S9/F9" not in r["answer"] and not ID.search(r["answer"]) and "(lecture 2, 0:24)" in r["answer"],
          f"IDs replaced by lecture and time, the made-up ID dropped: {r['answer']!r}")
    check(r["covered"] is True, "covered true")
    ctk = lambda b: b.get("chat_template_kwargs") or {}  # noqa: E731
    check(ctk(b0).get("enable_thinking") is True and ctk(b1).get("enable_thinking") is False
          and ctk(b1).get("extra_switch") == 1 and ctk(b0).get("extra_switch") == 1,
          f"thinking on in round 0, off in round 1, the config's other switch kept ({ctk(b0)}, {ctk(b1)})")
    log = lambda: json.loads((Path(os.environ["QA_OUTPUT"]) / COURSE / "qa" / "answers.jsonl")  # noqa: E731
                             .read_text().splitlines()[-1])
    check(log()["early_exit"] is False, "a card found: no early answer logged")

    print("an unknown concept: its closest facts come with it, and nothing close means answer now", flush=True)
    n0 = len(server.bodies)
    r = ask("What is a vergence lens?")
    sent = server.bodies[n0:]
    unknown = [m for m in sent[1]["messages"] if m["role"] == "tool"][0]["content"] if len(sent) > 1 else ""
    check(r["steps"][0]["result_summary"].startswith("unknown") and "fact_lookup" in unknown
          and "facts closest to" in unknown and "None of these is a close match" in unknown,
          f"check_concept says unknown, points to fact_lookup and shows the closest facts, none close "
          f"({r['steps'][0]['result_summary']})")
    check(tools_of(r) == ["check_concept"] and len(sent) == 2 and sent[1].get("tool_choice") == "none"
          and sent[1]["messages"][-1] == {"role": "user", "content": FINAL_NUDGE}
          and ctk(sent[1]).get("enable_thinking") is False and log()["early_exit"] is True,
          f"nothing close: round 1 is the answer (tool_choice none, the nudge last, thinking off; early_exit logged) "
          f"({len(sent)} requests)")
    check(len(r["citations"]) == 1 and r["citations"][0]["fact"] in unknown and real_citations(r, facts, lectures)
          and r["covered"] is True, "the answer cites one of the closest facts shown; 'partly' counts as covered")
    n0 = len(server.bodies)
    r = ask("Vergence lens and HMD")
    sent = server.bodies[n0:]
    check(tools_of(r) == ["check_concept", "check_concept"] and sent[1].get("tool_choice") == "auto"
          and log()["early_exit"] is False and len(r["citations"]) == 1,
          "one name unknown and one found: no early answer (round 1 may still call tools)")

    print("a question the course does not cover", flush=True)
    n0 = len(server.bodies)
    r = ask("Who won the 1998 football world cup?")
    sent = server.bodies[n0:]
    check(tools_of(r) == ["fact_lookup"] and r["covered"] is False and r["citations"] == []
          and "does not cover" in r["answer"] and "COVERED" not in r["answer"],
          f"covered false, nothing cited, the COVERED line removed: {r['answer']!r}")
    check(len(sent) == 2 and sent[1].get("tool_choice") == "none" and log()["early_exit"] is True,
          "no close fact: round 1 is the answer (tool_choice none), early_exit logged")

    print("before lecture 6 and 8 (the lecture graph)", flush=True)
    from qa import Knowledge, run_tool
    kb = Knowledge.load(COURSE)
    d6, d8 = run_tool(kb, "lecture_dependencies", {"lecture": "6"}), run_tool(kb, "lecture_dependencies", {"lecture": 8})
    check(d6.summary.startswith("lecture 6: revise 2; relies on 1 earlier concepts, 0 general, 2 in passing")
          and "- stereoscopy (2 uses; first defined in lecture 2)" in d6.text and d6.shown == {"2/S2/F3", "2/S2/F4"}
          and 'Lectures to revise first, by how much lecture 6 relies on what they teach: lecture 2 "' in d6.text
          and "only mentions in passing (not needed beforehand): extended reality, virtual reality" in d6.text
          and "Concepts lecture 6 itself introduces (most used first): latency" in d6.text,
          f"lecture 6: relies on stereoscopy (2 uses, lecture 2, facts 2/S2/F3, 2/S2/F4), revise 2; extended and "
          f"virtual reality in passing; introduces latency ({d6.summary})")
    check(d8.summary.startswith("lecture 8: revise none; relies on 0 earlier concepts, 0 general, 4 in passing")
          and "in passing (not needed beforehand): display resolution, rendering, stereoscopy, virtual reality"
          in d8.text and not d8.shown,
          f"lecture 8: relies on nothing earlier; display resolution, rendering, stereoscopy, virtual reality in "
          f"passing ({d8.summary})")
    r = ask("What do I need before lecture 6?")
    check(tools_of(r) == ["lecture_dependencies"] and r["steps"][0]["result_summary"].startswith("lecture 6: revise 2")
          and [c["fact"] for c in r["citations"]] == ["2/S2/F3"] and real_citations(r, facts, lectures),
          f"the loop: lecture_dependencies(6) and its defining fact cited ({r['steps'][0]['result_summary']})")

    print("tidy citations (times the model wrote, repeated labels)", flush=True)
    r = ask("Repeated labels")
    a, b = "(lecture 2, 26:57)", "(lecture 2, 27:07)"
    want = (f"Stereoscopy is taught. It is a fake concept {a}. Its screens are 16:9 (lecture 6, 0:24). "
            f"It goes on {a[:-1]}; lecture 2, 27:07).\n\nIts points are {a}:\n- point 0\n- point 1\n\n"
            f"Again {a} and (lecture 6, 0:24).\n\nMixed:\n- one {a}\n- two {a}\n- three (lecture 6, 0:24)")
    check(r["answer"] == want, f"times before citations removed, '16:9' kept, runs in a line and a list sharing one "
                               f"label labelled once, items of a mixed list each keep theirs: "
                               f"{r['answer']!r}")
    check([c["fact"] for c in r["citations"]] == ["2/S2/F3", "6/S0/F2", "2/S2/F4"]
          and real_citations(r, facts, lectures), "every cited fact still a citation, in order of first use")

    print("this lecture (the learner's lecture passed on)", flush=True)
    n0 = len(server.bodies)
    r = ask("What is this lecture for?", lecture="Lecture 4")
    check('watching lecture 4 "Definitions"' in server.bodies[n0]["messages"][1]["content"],
          "the learner's lecture is in the user message")
    check(tools_of(r) == ["lecture_overview"] and r["steps"][0]["args"] == {"lecture": 4}
          and [c["segment"] for c in r["citations"]] == ["4/S0", "4/S1"]
          and all(c["fact"] is None for c in r["citations"]) and real_citations(r, facts, lectures),
          "lecture_overview(4) with an integer argument; segment citations with the segment's time and sub-goal")

    print("two calls in one message", flush=True)
    n0 = len(server.bodies)
    r = ask("How do HMDs and tracking relate?")
    tm = [m for m in server.bodies[n0 + 1]["messages"] if m["role"] == "tool"]
    check(tools_of(r) == ["check_concept", "check_concept"]
          and [s["args"]["name"] for s in r["steps"]] == ["HMDs", "tracking"]
          and [m["tool_call_id"] for m in tm] == ["call_check_concept_0", "call_check_concept_1"],
          "both run in order, each result under its own call ID ('HMDs' found by its plural)")
    check(len(r["citations"]) == 2 and real_citations(r, facts, lectures), "a citation from each card")

    print("a misspelt name", flush=True)
    r = ask("What is strereoscopy?")
    check("stereoscopy" in r["steps"][0]["result_summary"] and "close" in r["steps"][0]["result_summary"]
          and len(r["citations"]) == 1 and real_citations(r, facts, lectures),
          f"'strereoscopy' finds stereoscopy ({r['steps'][0]['result_summary']}); a bare ID in parentheses cited")

    print("the loop's guards", flush=True)
    n0 = len(server.bodies)
    r = ask("Keep calling tools")
    sent = server.bodies[n0:]
    check(len(sent) == MAX_ROUNDS + 1 and sent[-1].get("tool_choice") == "none"
          and sent[-1]["messages"][-1] == {"role": "user", "content": FINAL_NUDGE}
          and all(b.get("tool_choice") == "auto" for b in sent[:-1]),
          f"after {MAX_ROUNDS} rounds the model must answer (tool_choice none, the nudge last)")
    check([s["result_summary"] for s in r["steps"]].count("repeated call") == MAX_ROUNDS - 2,
          "a repeated call is not run again")
    check(r["citations"] == [] and r["covered"] is False,
          "'COVERED: yes' with an ID no tool showed: nothing cited, covered false")
    n0 = len(server.bodies)
    r = ask("Call a broken tool")
    sums = [s["result_summary"] for s in r["steps"]]
    check(len(sums) == 3 and sums[0] == "unknown tool no_such_tool" and sums[1] == "bad arguments"
          and sums[2].startswith("error: There is no lecture 99") and r["covered"] is False
          and server.bodies[n0 + 1].get("tool_choice") == "auto",
          f"a bad tool name, bad JSON and a bad lecture go back to the model, which may call tools again ({sums})")

    print("covered without the COVERED line", flush=True)
    r = ask("No covered line, with a citation")
    check(r["covered"] is True and len(r["citations"]) == 1, "no line, a citation: covered true")
    r = ask("No covered line, nothing cited")
    check(r["covered"] is False and r["citations"] == [], "no line, nothing cited: covered false")
    r = ask("Yes without citations")
    check(r["covered"] is False, "'yes' with nothing cited after a concept card: covered false")
    r = ask("What is this course about?")
    check(tools_of(r) == ["course_goals"] and r["covered"] is True and "2 course goals" in r["steps"][0]["result_summary"],
          "course_goals: 'yes' without citations stays covered (goals have no times)")


def test_cli(cfg_path: Path, env: dict):
    print("command line", flush=True)
    p = subprocess.run([sys.executable, "-m", "qa", "What is an HMD?", "--config", str(cfg_path), "--json"],
                       cwd=ROOT, env=env, capture_output=True, text=True)
    try:
        r = json.loads(p.stdout)
    except json.JSONDecodeError:
        r = {}
    check(p.returncode == 0 and r.get("covered") is True and len(r.get("citations", [])) == 2,
          f"python -m qa ... --json prints the result (exit {p.returncode}{', ' + p.stderr[-300:] if p.returncode else ''})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--layer", help="a folder holding output/nptel_vr/knowledge (default: build one)")
    ap.add_argument("--keep", action="store_true", help="keep the temporary folder")
    a = ap.parse_args()
    before = snapshot(ROOT / "output")
    work = Path(tempfile.mkdtemp(prefix="fake_qa_"))
    src = Path(a.layer) / "output" / COURSE / "knowledge" if a.layer else build_layer(work)
    out = work / "output"
    layer = out / COURSE / "knowledge"
    shutil.copytree(src, layer)
    os.environ["QA_OUTPUT"] = str(out)
    port = free_port()
    cfg = LLMConfig.load(ROOT / "configs" / "gemma4_12b_llamacpp.json").with_(
        port=port, model="fake-gemma", model_path="fake/gemma", launch=False, cache_file="", log_file="",
        server_log=str(work / "server.log"), chat_template_kwargs={"extra_switch": 1})
    cfg_path = work / "fake_gemma.json"
    cfg.save(cfg_path)
    print(f"layer copy in {layer}; fake model on port {port}", flush=True)
    server = QAFake(port, cfg.model).start()
    try:
        test_client(cfg, server, work)
        test_answers(cfg, server, layer)
        test_cli(cfg_path, {**os.environ, "QA_OUTPUT": str(out)})
    finally:
        server.stop()
    print("log", flush=True)
    log = [json.loads(x) for x in (out / COURSE / "qa" / "answers.jsonl").read_text().splitlines()]
    check(len(log) == 16 and all(r["steps"] is not None and "raw_answer" in r for r in log)
          and log[0]["dropped_ids"] == ["9/S9/F9"] and "result" in log[0]["steps"][0],
          f"every question logged with its full tool results and dropped IDs ({len(log)} lines)")
    print("output", flush=True)
    check(snapshot(ROOT / "output") == before, "nothing under the real output/ created or changed")
    if not a.keep and not FAILURES:
        shutil.rmtree(work)
    print(f"\n{'PASS' if not FAILURES else 'FAIL'}: {len(FAILURES)} failed"
          + (f"; folder kept: {work}" if FAILURES or a.keep else ""))
    sys.exit(1 if FAILURES else 0)


if __name__ == "__main__":
    main()
