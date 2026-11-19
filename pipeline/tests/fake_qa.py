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
  stream   answer_stream not giving a step event per tool call (in order), drafts (labels written, no raw ID, half
           bracket or COVERED line; the last one the answer), a reset when a round's text ended in tool calls, and
           last done with exactly what answer() returns; its rounds not sent with "stream" or not with the same
           tools, tool_choice and thinking; its tokens not logged
  events   (schemas/qa_stream.md) the first event not a "round" at once; a step not preceded by its "call"; a step
           without its display label, its detail (check_concept: the concept, whether it has a definition, the
           lectures of its facts; an unknown name: known false, the closest facts' lectures) or its time; no
           "answer_start" before the first draft; "t" going backwards; done without its timing; on llama.cpp the
           rounds of one question not all on one slot (id_slot) or without cache_prompt
  concepts check_concept with a list of names not giving one card per name in order (a repeated name once, an unknown
           name with its closest facts), or its label not naming each concept with its lecture ("not in the course"
           for an unknown one); a string or an empty list not handled
  structure course_structure without its file crashing instead of saying it is not available; its statements not
           shown verbatim with ID, lecture and time; a CS ID not cited with the statement's own time, or one no tool
           showed cited; the lecture limit not working
  think    think=False / $QA_THINK=0 not turning thinking off in every round (the config's other switches kept), an
           explicit argument not winning over the environment, the mode not logged and in done's timing
  round 0  the round-0 switches (qa.answer.ROUND0_THINK, ROUND0_TOOL_CHOICE) not reaching round 0, or leaking into
           round 1
  vllm     qa with configs/gemma4_12b_vllm_demo.json (fake vLLM on a free port) not sending repetition_penalty, sending
           thinking_token_budget, or answering differently from the llama.cpp config; python -m qa --stop not
           stopping a "vllm serve ... --port N" process, or stopping one on another port
  log      a question not logged to <output>/<course>/qa/answers.jsonl
  output   any file under the real output/ created or changed
"""
from __future__ import annotations

import argparse
import importlib
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
    """Size and mtime of every file under folder, except output/logs/ (a shared llama-server writes there)."""
    return {str(p.relative_to(folder)): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in folder.rglob("*") if p.is_file() and p.relative_to(folder).parts[:1] != ("logs",)}


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
        if isinstance(out, tuple):                     # (content, tool calls): text written before the calls
            msg = {"content": out[0], "tool_calls": out[1]}
        else:
            msg = {"content": out, "tool_calls": None} if isinstance(out, str) else {"content": "", "tool_calls": out}
        return {"choices": [{"message": {**msg, "reasoning_content": "fake thinking"},
                             "finish_reason": "tool_calls" if msg["tool_calls"] else "stop"}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 10}}

    @staticmethod
    def script(q: str, rnd: int, last: str, tools: list, msgs: list, body: dict):
        if q == "What is an HMD?":
            if rnd == 0:
                return [call("check_concept", {"names": ["HMD"]})]
            a, b = ids_in(last)[:2]
            return f"An HMD is a display worn on the head [{a}]. It is defined early [{b}, 9/S9/F9].\nCOVERED: yes"
        if q == "What is a vergence lens?":
            if rnd == 0:
                return [call("check_concept", {"names": ["vergence lens"]})]
            if body.get("tool_choice") == "none":     # the closest facts came with "unknown": answer from them
                return f"The course mentions something close [{ids_in(last)[0]}].\nCOVERED: partly"
            if "unknown" in last and "fact_lookup" in last:
                return [call("fact_lookup", {"query": "vergence lens", "rephrasings": ["lens for vergence"]})]
            return "I do not know.\nCOVERED: no"
        if q == "Vergence lens and HMD":
            if rnd == 0:
                return [call("check_concept", {"names": ["vergence lens"]}, 0), call("check_concept", {"names": ["HMD"]}, 1)]
            return f"An HMD is worn on the head [{ids_in(tools[-1])[0]}].\nCOVERED: partly"
        if q == "Repeated labels":
            if rnd == 0:
                return [call("check_concept", {"names": ["stereoscopy"]})]
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
                return [call("check_concept", {"names": ["HMDs"]}, 0), call("check_concept", {"names": ["tracking"]}, 1)]
            a, b = ids_in(tools[-2])[0], ids_in(tools[-1])[0]
            return f"An HMD shows the virtual world [{a}] and tracking follows the head [{b}].\nCOVERED: yes"
        if q == "What is strereoscopy?":
            if rnd == 0:
                return [call("check_concept", {"names": ["strereoscopy"]})]
            return f"Stereoscopy is explained in lecture 2 ({ids_in(last)[0]}).\nCOVERED: yes"
        if q == "Keep calling tools":
            if body.get("tool_choice") == "none":
                return "Here is what I found [7/S9/F9].\nCOVERED: yes"
            return [call("check_concept", {"names": ["VR"]} if rnd % 2 == 0 else {"names": ["rendering"]})]
        if q == "Call a broken tool":
            if rnd == 0:
                return [call("no_such_tool", {}, 0), call("check_concept", "{not json", 1),
                        call("lecture_overview", {"lecture": "99"}, 2)]
            return "Sorry, nothing found.\nCOVERED: no"
        if q == "No covered line, with a citation":
            if rnd == 0:
                return [call("check_concept", {"names": ["rendering"]})]
            return f"Rendering is taught in lecture 4 [{ids_in(last)[0]}]."
        if q == "No covered line, nothing cited":
            return "I cannot tell."
        if q == "Yes without citations":
            if rnd == 0:
                return [call("check_concept", {"names": ["rendering"]})]
            return "Rendering is a big topic.\nCOVERED: yes"
        if q == "Talk first, then search":
            if rnd == 0:
                return "Let me look this up in the course first.", [call("check_concept", {"names": ["rendering"]})]
            return f"Rendering is taught in lecture 4 [{ids_in(last)[0]}].\nCOVERED: yes"
        if q == "HMD, tracking and a vergence lens together":
            if rnd == 0:
                return [call("check_concept", {"names": ["HMDs", "tracking", "vergence lens", "HMDs"]})]
            return f"An HMD shows the virtual world [{ids_in(last)[0]}].\nCOVERED: partly"
        if q.startswith("How is the course organised? (page)"):
            if rnd == 0:
                return [call("course_structure", {})]
            ids = re.findall(r"\[((?:CP|CS)\d+)\]", last)
            return "It is taught by X [%s].\nCOVERED: yes" % ids[0]
        if q.startswith("How is the course organised?"):
            if rnd == 0:
                return [call("course_structure", {"lecture": "2"} if "lecture 2" in q else {})]
            ids = re.findall(r"\[(CS\d+)\]", last)
            if not ids:
                return "The lecturers do not say how it is organised.\nCOVERED: no"
            return "It has two modules at 1:05 [%s]. And an exam [%s].\nCOVERED: yes" % (ids[0], ids[-1])
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
                                                                    "course_goals", "course_structure"]
          and sent.get("tool_choice") == "auto", "the six tools and tool_choice sent to the server")


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
    check(tools_of(r) == ["check_concept"] and r["steps"][0]["args"] == {"names": ["HMD"]}
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
    from qa.answer import TOOL_REF
    check(TOOL_REF.sub("", "Revise lecture 8 first. [lecture_dependencies] See (fact_lookup).")
          == "Revise lecture 8 first. See.", "a tool's name written as a citation is removed")

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
    from qa import Knowledge as _K, run_tool as _rt
    _kb = _K.load(COURSE)
    SECRET = "SECRETDEF connecting concept definition text"
    tid = next(c for c, v in _kb.concepts.items() if v["name"] == "tracking")
    sid = next(c for c, v in _kb.concepts.items() if v["name"] == "stereoscopy")
    saved = {c: dict(_kb.concepts[c]) for c in (tid, sid)}
    for c in (tid, sid):                  # make them connecting concepts, with a definition that must not leak
        _kb.concepts[c].update(defined=False, definition=SECRET + " " + _kb.concepts[c]["name"])
    try:
        r = ask("How do HMDs and tracking relate?")
        tm = [m for m in server.bodies[n0 + 1]["messages"] if m["role"] == "tool"]
        cc = _rt(_kb, "check_concept", {"names": ["tracking"]})
        dp = _rt(_kb, "lecture_dependencies", {"lecture": "6"})
        transcript = json.dumps(server.bodies[n0:]) + cc.text + dp.text + json.dumps([(s["result_summary"], s.get("label")) for s in r["steps"]])
        facts_of_c = [f for f in saved[tid].get("facts", []) if f in _kb.facts]
        check(SECRET not in transcript and "Definition: none" in cc.text and "built from" not in cc.text
              and "Defined in:" not in cc.text and all(f in cc.text for f in facts_of_c[:3]) and facts_of_c
              and cc.detail["items"][0]["concepts"][0]["defined"] is False
              and "definition found" not in cc.detail["items"][0]["label"]
              and "facts found" in cc.detail["items"][0]["label"],
              f"connecting concept: no definition text anywhere, facts shown, defined false ({cc.label!r})")
        check(SECRET not in dp.text and "- stereoscopy (2 uses; first met in lecture 2)" in dp.text
              and "2/S2/F3" in dp.text, "lecture_dependencies: a connecting concept shows facts, no definition")
    finally:
        for c, v in saved.items():
            _kb.concepts[c].clear()
            _kb.concepts[c].update(v)
    dd = _rt(_kb, "check_concept", {"names": ["stereoscopy"]})
    check("Definition: Stereoscopy" in dd.text and dd.detail["items"][0]["concepts"][0]["defined"] is True
          and "definition found" in dd.detail["items"][0]["label"] and "first defined in lecture 2" in
          _rt(_kb, "lecture_dependencies", {"lecture": "6"}).text, f"a defined concept keeps its definition ({dd.label!r})")
    check(tools_of(r) == ["check_concept", "check_concept"]
          and [s["args"]["names"][0] for s in r["steps"]] == ["HMDs", "tracking"]
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


def stream_events(q: str, llm, **kw) -> list[dict]:
    import qa
    return list(qa.answer_stream(q, course=COURSE, llm=llm, **kw))


def check_drafts(evs: list[dict], result: dict, what: str):
    drafts = [e["text"] for e in evs if e["event"] == "draft"]
    clean = all(not ID.search(d) and "COVERED" not in d.upper() and d.count("(") == d.count(")")
                and "[" not in d and "\x00" not in d for d in drafts)
    check(len(drafts) >= 2 and clean and drafts[-1] == result["answer"],
          f"{what}: drafts grow with lecture labels, no raw ID, bracket or COVERED line; the last equals the answer "
          f"({len(drafts)} drafts{'' if clean else ', a dirty one: ' + repr(next(d for d in drafts if ID.search(d) or 'COVERED' in d.upper() or '[' in d))})")


def test_stream(cfg: LLMConfig, server: QAFake):
    import qa
    llm = LLM(cfg, log=lambda *a: None)
    ask = lambda q, **kw: qa.answer(q, course=COURSE, llm=llm, **kw)  # noqa: E731
    OLD = ("step", "draft", "reset", "done")         # the events the page has read since the stream was added
    kinds = lambda evs: [e["event"] for i, e in enumerate(old) if i == 0 or e["event"] != old[i - 1]["event"]] \
        if (old := [e for e in evs if e["event"] in OLD]) else []  # noqa: E731

    print("streaming (answer_stream)", flush=True)
    n0 = len(server.bodies)
    evs = stream_events("What is an HMD?", llm)
    sent = server.bodies[n0:]
    blocking = ask("What is an HMD?")
    s0 = next(e for e in evs if e["event"] == "step")
    check(kinds(evs) == ["step", "draft", "done"] and s0["tool"] == "check_concept"
          and s0["args"] == {"names": ["HMD"]} and "head-mounted display" in s0["result_summary"],
          f"events: the step, then drafts, then done ({kinds(evs)})")
    check(evs[-1]["result"] == blocking, "done's result equals answer()'s for the same question")
    check_drafts(evs, blocking, "one tool call")
    names = [e["event"] for e in evs]
    step, call_ = next(e for e in evs if e["event"] == "step"), next(e for e in evs if e["event"] == "call")
    ts = [e["t"] for e in evs]
    check(names[0] == "round" and evs[0]["round"] == 0 and evs[0]["final"] is False and evs[0]["t"] < 0.5
          and all(isinstance(t, float) or isinstance(t, int) for t in ts) and ts == sorted(ts),
          f"the first event is round 0, at once ({evs[0]}); every event has a non-decreasing t")
    check(names.index("call") < names.index("step") and call_["tool"] == step["tool"] == "check_concept"
          and call_["args"] == step["args"] and step["round"] == 0 and step["index"] == 0
          and isinstance(step["seconds"], float) and step["found"] is True,
          "a call event before its step; the step with round, index, seconds and found")
    d = step.get("detail") or {}
    it = (d.get("items") or [{}])[0]
    check(d.get("names") == ["HMD"] and d.get("known") == 1 and it.get("known") is True and it.get("concepts")
          and it["concepts"][0]["name"] == "head-mounted display"
          and isinstance(it["concepts"][0]["defined"], bool) and d.get("facts", 0) > 0 and d.get("lectures")
          and all(isinstance(k, str) for k in d["lectures"]) and isinstance(it.get("lecture"), str)
          and step.get("label") == f"Concept loaded: head-mounted display (lecture {it['lecture']})"
          and "/F" not in step["label"],
          f"check_concept's step: label and detail (concept, definition found, facts and their lectures) "
          f"({step.get('label')!r}, {d})")
    check(names.index("answer_start") < names.index("draft") and names.index("answer_start") > names.index("step")
          and next(e for e in evs if e["event"] == "answer_start")["round"] == 1 and "thinking" in names,
          f"thinking events, then answer_start (round 1) before the first draft ({names})")
    tm = evs[-1].get("timing") or {}
    check(tm.get("first_step") is not None and tm.get("first_draft") is not None
          and tm.get("first_step") <= tm.get("answer_start") <= tm.get("first_draft") <= tm.get("total")
          and len(tm.get("rounds", [])) == 2 and "ttft_s" in tm["rounds"][0] and evs[-1]["t"] >= tm["total"],
          f"done carries the timing: first step, answer start, first draft, total, the rounds ({tm})")
    check(all(b.get("cache_prompt") is True for b in sent) and sent[0].get("id_slot") == 0
          and sent[1].get("id_slot") == 0 and tm["rounds"][0].get("slot") == 0,
          f"llama.cpp: both rounds sent with cache_prompt and to one slot ({[b.get('id_slot') for b in sent]})")
    ctk = lambda b: b.get("chat_template_kwargs") or {}  # noqa: E731
    check(len(sent) == 2 and all(b.get("stream") is True and b.get("stream_options") == {"include_usage": True}
                                 for b in sent)
          and "stream" not in server.bodies[-1] and ctk(sent[0]).get("enable_thinking") is True
          and ctk(sent[1]).get("enable_thinking") is False and sent[0].get("tool_choice") == "auto"
          and [t["function"]["name"] for t in sent[0]["tools"]] == [t["function"]["name"] for t in qa.tool_specs()],
          "streamed rounds sent with stream and include_usage, the same tools, tool_choice and thinking as "
          "answer() (which does not stream)")
    log = json.loads((Path(os.environ["QA_OUTPUT"]) / COURSE / "qa" / "answers.jsonl").read_text().splitlines()[-2])
    check(log["tokens"] == {"input": 200, "output": 20} and len(log["timing"]) == 2,
          f"the streamed answer logged with the usage of both rounds ({log['tokens']})")

    evs = stream_events("How do HMDs and tracking relate?", llm)
    blocking = ask("How do HMDs and tracking relate?")
    steps = [e for e in evs if e["event"] == "step"]
    check(kinds(evs) == ["step", "draft", "done"] and [s["args"]["names"][0] for s in steps] == ["HMDs", "tracking"]
          and evs[-1]["result"] == blocking,
          "two calls in one message: two step events in order (tool-call deltas assembled by index); done == answer()")
    order = [(e["event"], e.get("tool")) for e in evs if e["event"] in ("call", "step")]
    check(order == [("call", "check_concept"), ("step", "check_concept")] * 2
          and [s["index"] for s in steps] == [0, 1],
          f"two calls: call, step, call, step, indexes 0 and 1 ({order})")
    check_drafts(evs, blocking, "two cards")

    evs = stream_events("Talk first, then search", llm)
    blocking = ask("Talk first, then search")
    check(kinds(evs) == ["draft", "reset", "step", "draft", "done"]
          and next(e for e in evs if e["event"] == "draft")["text"].startswith("Let me") and evs[-1]["result"] == blocking
          and "Let me look" not in blocking["answer"] and len(blocking["citations"]) == 1,
          f"text written before tool calls: drafted, then reset, then the step and the answer's drafts "
          f"({kinds(evs)}; answer {blocking['answer']!r})")

    print("round-0 switches (thinking off, tool_choice required)", flush=True)
    qa_answer = importlib.import_module("qa.answer")   # the module (qa.answer the attribute is the function)
    keep = qa_answer.ROUND0_THINK, qa_answer.ROUND0_TOOL_CHOICE
    qa_answer.ROUND0_THINK, qa_answer.ROUND0_TOOL_CHOICE = False, "required"
    try:
        n0 = len(server.bodies)
        r = ask("What is an HMD?")
        b0, b1 = server.bodies[n0], server.bodies[n0 + 1]
        check(ctk(b0).get("enable_thinking") is False and b0.get("tool_choice") == "required"
              and ctk(b0).get("extra_switch") == 1 and ctk(b1).get("enable_thinking") is False
              and b1.get("tool_choice") == "auto" and len(r["citations"]) == 2,
              f"round 0 sent with thinking off and tool_choice required, round 1 with auto ({ctk(b0)}, "
              f"{b0.get('tool_choice')}, {b1.get('tool_choice')})")
    finally:
        qa_answer.ROUND0_THINK, qa_answer.ROUND0_TOOL_CHOICE = keep


CS_FILE = {"run": {"fake": True}, "statements": [
    {"id": "CS0001", "lecture": "2", "segment": "2/S0", "sentence_ids": [1, 2], "start": 65.0, "end": 71.5,
     "text": "In this course there are two modules, the first in weeks one to four."},
    {"id": "CS0002", "lecture": "4", "segment": "4/S1", "sentence_ids": [9], "start": 130.2, "end": 140.0,
     "text": "We will not cover game engines in this course."}]}


FAKE_PAGE = {"title": "Fake Course", "platform": "NPTEL", "institution": "IIT Fake",
             "instructor": {"name": "Prof. A. Teacher", "department": "Department of Testing", "about": "Teaches testing."},
             "prerequisites": "Some programming.", "intended_audience": "UG students.", "outline": "An outline.",
             "syllabus": [{"week": 1, "theme": "Basics", "topics": ["Intro", "Terms"]},
                          {"week": 2, "theme": "More", "topics": ["Depth"]}]}


def test_new(cfg: LLMConfig, server: QAFake, out: Path):
    """Several names in one check_concept call, course_structure, and thinking off."""
    import qa
    qa_answer = importlib.import_module("qa.answer")
    llm = LLM(cfg, log=lambda *a: None)
    ctk = lambda b: b.get("chat_template_kwargs") or {}  # noqa: E731
    log = lambda: json.loads((out / COURSE / "qa" / "answers.jsonl").read_text().splitlines()[-1])  # noqa: E731

    print("check_concept with several names in one call", flush=True)
    n0 = len(server.bodies)
    evs = stream_events("HMD, tracking and a vergence lens together", llm)
    r = evs[-1]["result"]
    tm = [m for m in server.bodies[n0 + 1]["messages"] if m["role"] == "tool"]
    steps = [e for e in evs if e["event"] == "step"]
    d = steps[0]["detail"] if steps else {}
    it = d.get("items", [])
    check(len(steps) == 1 and len(tm) == 1 and d.get("names") == ["HMDs", "tracking", "vergence lens"]
          and [i["known"] for i in it] == [True, True, False] and d.get("known") == 2
          and tm[0]["content"].index("CONCEPT head-mounted display") < tm[0]["content"].index("CONCEPT tracking")
          < tm[0]["content"].index('"vergence lens" is not the name of a concept')
          and "facts closest to" in tm[0]["content"] and steps[0]["found"] is True,
          f"one call, one step, one card per name in order (a repeated name once; the unknown name with its closest "
          f"facts): {steps[0].get('label') if steps else None!r}")
    l0, l1 = it[0]["lecture"], it[1]["lecture"]
    check(steps[0]["label"] == f"Concepts loaded: head-mounted display (lecture {l0}), tracking (lecture {l1}), "
                               "vergence lens (not in the course)" and isinstance(l0, str) and isinstance(l1, str),
          f"the step label names each concept with its lecture, 'not in the course' for the unknown ({steps[0]['label']!r})")
    check(r["steps"][0]["args"]["names"] == ["HMDs", "tracking", "vergence lens", "HMDs"] and r["citations"],
          "the steps keep the call's arguments as sent")
    kb = qa.Knowledge.load(COURSE)
    one = qa.run_tool(kb, "check_concept", {"names": "tracking"})
    check(one.label.startswith("Concept loaded: tracking") and one.text == qa.run_tool(
        kb, "check_concept", {"names": ["tracking"]}).text and "CONCEPT tracking" in one.text,
          "a single name (or a bare string) gives the one card, as before")
    bad = qa.run_tool(kb, "check_concept", {"names": []})
    check(bad.summary.startswith("error") and "names" in bad.text, "an empty list is an error the model can correct")

    print("course_structure", flush=True)
    n0 = len(server.bodies)
    r = qa.answer("How is the course organised?", course=COURSE, llm=llm)
    sent = server.bodies[n0:]
    check(r["steps"][0]["tool"] == "course_structure" and "not available" in r["steps"][0]["result_summary"]
          and r["covered"] is False and len(sent) == 2 and sent[1].get("tool_choice") == "none",
          f"no course_structure.json: the tool says it is not available, no crash, early answer "
          f"({r['steps'][0]['result_summary']})")
    sdir = out / COURSE / "stage_4f_course_structure"
    sdir.mkdir(parents=True)
    (sdir / "course_structure.json").write_text(json.dumps(CS_FILE), encoding="utf-8")
    n0 = len(server.bodies)
    evs = stream_events("How is the course organised?", llm)
    r = evs[-1]["result"]
    tm = [m for m in server.bodies[n0 + 1]["messages"] if m["role"] == "tool"][0]["content"]
    st = next(e for e in evs if e["event"] == "step")
    check("[CS0001] lecture 2, 1:05: In this course there are two modules, the first in weeks one to four." in tm
          and "[CS0002] lecture 4, 2:10: We will not cover game engines in this course." in tm
          and st["label"] == "Course structure read: 2 statements from lectures 2 and 4" and st["found"] is True
          and st["detail"] == {"statements": 2, "lectures": ["2", "4"], "lecture": None, "available": True, "course_page": 0},
          f"the statements verbatim with ID, lecture and time; the step's label and detail ({st['label']!r})")
    c = r["citations"]
    check([(x["fact"], x["lecture"], x["segment"], x["start"], x["end"]) for x in c]
          == [(None, "2", "2/S0", 65.0, 71.5), (None, "4", "4/S1", 130.2, 140.0)]
          and c[1]["text"] == CS_FILE["statements"][1]["text"] and not re.search(r"CS\d", r["answer"])
          and "(lecture 2, 1:05)" in r["answer"] and "(lecture 4, 2:10)" in r["answer"] and r["covered"] is True,
          f"a CS ID is cited like a fact, with the statement's own time: {r['answer']!r}")
    r = qa.answer("How is the course organised? (lecture 2)", course=COURSE, llm=llm)
    check(r["steps"][0]["args"] == {"lecture": "2"} and r["steps"][0]["result_summary"] == "1 statements from lecture 2"
          and [x["lecture"] for x in r["citations"]] == ["2"], "the optional lecture limits the statements")
    from qa.answer import cite
    text, cits, dropped = cite(kb, "One [CS0001]. Two [CS0009]. Three [CS0002].", {"CS0001"})
    check(dropped == ["CS0009", "CS0002"] and [x["segment"] for x in cits] == ["2/S0"]
          and text == "One (lecture 2, 1:05). Two. Three.", f"only a CS ID some tool showed is cited ({text!r})")
    text, cits, dropped = cite(kb, "A (long system) [CS0001]; B [CS0001] [CS0002].", {"CS0001", "CS0002"})
    check(text.startswith("A (long system) (lecture 2, 1:05);") and "(long system; " not in text and text.count("(lecture 2") >= 1,
          f"a citation after a closing parenthesis stays outside it ({text!r})")

    print("thinking off (think=False, $QA_THINK)", flush=True)
    n0 = len(server.bodies)
    qa.answer("What is an HMD?", course=COURSE, llm=llm, think=False)
    b = server.bodies[n0:]
    check(len(b) == 2 and all(ctk(x).get("enable_thinking") is False for x in b) and ctk(b[0]).get("extra_switch") == 1
          and log()["think"] is False, f"think=False: no round thinks, the other switch kept, logged ({[ctk(x) for x in b]})")
    os.environ["QA_THINK"] = "0"
    try:
        n0 = len(server.bodies)
        qa.answer("What is an HMD?", course=COURSE, llm=llm)
        b = server.bodies[n0:]
        check(ctk(b[0]).get("enable_thinking") is False and log()["think"] is False, "$QA_THINK=0 turns round 0's thinking off")
        n0 = len(server.bodies)
        qa.answer("What is an HMD?", course=COURSE, llm=llm, think=True)
        check(ctk(server.bodies[n0]).get("enable_thinking") is True and log()["think"] is True,
              "an explicit think=True wins over $QA_THINK=0")
        evs = stream_events("What is an HMD?", llm)
        check(evs[0]["thinking"] is False and evs[-1]["timing"]["think"] is False,
              "$QA_THINK=0 on the stream: the round event says thinking false, the timing records the mode")
    finally:
        del os.environ["QA_THINK"]
    n0 = len(server.bodies)
    evs = stream_events("What is an HMD?", llm, think=False)
    b = server.bodies[n0:]
    check(ctk(b[0]).get("enable_thinking") is False and evs[-1]["timing"]["think"] is False
          and ctk(b[0]).get("extra_switch") == 1,
          "answer_stream(think=False): round 0 sent without thinking; done's timing says think false")
    n0 = len(server.bodies)
    evs = stream_events("What is an HMD?", llm)
    check(ctk(server.bodies[n0]).get("enable_thinking") is True and evs[-1]["timing"]["think"] is True
          and qa_answer.want_think() is True, "default: thinking on in round 0, timing says think true")


def test_vllm(work: Path, env: dict, ref: dict):
    """qa against configs/gemma4_12b_vllm_demo.json (the cloud demo), with a fake vLLM on a free port."""
    import qa
    print("the vLLM demo config (fake server)", flush=True)
    port = free_port()
    cfg = LLMConfig.load(ROOT / "configs" / "gemma4_12b_vllm_demo.json").with_(
        port=port, server_log=str(work / "server_vllm.log"), attach_wait_s=5)
    cfg_path = work / "vllm_demo.json"
    cfg.save(cfg_path)
    server = QAFake(port, cfg.model).start()
    try:
        llm = LLM(cfg, log=lambda *a: None)
        n0 = len(server.bodies)
        r = qa.answer("What is an HMD?", course=COURSE, llm=llm)
        b0, b1 = server.bodies[n0], server.bodies[n0 + 1]
        evs = stream_events("What is an HMD?", llm)
        ctk = lambda b: b.get("chat_template_kwargs") or {}  # noqa: E731
        check(cfg.engine == "vllm" and not cfg.launch and b0["model"] == "gemma-4-12b"
              and "repetition_penalty" in b0 and "repeat_penalty" not in b0 and "thinking_token_budget" not in b0
              and b0.get("top_k") == 64 and b0.get("tool_choice") == "auto"
              and [t["function"]["name"] for t in b0["tools"]] == [t["function"]["name"] for t in qa.tool_specs()]
              and ctk(b0).get("enable_thinking") is True and ctk(b1).get("enable_thinking") is False,
              "vLLM body: repetition_penalty (not repeat_penalty), no thinking_token_budget, the five tools, "
              "tool_choice auto, thinking on in round 0 and off after")
        streamed = [b for b in server.bodies[n0:] if b.get("stream")]
        check(streamed and not any("id_slot" in b or "cache_prompt" in b for b in streamed),
              "vLLM: streamed rounds carry no llama.cpp fields (id_slot, cache_prompt)")
        check(r == ref and evs[-1]["result"] == ref,
              "the same answer as through the llama.cpp config, blocking and streamed")
    finally:
        server.stop()

    print("python -m qa --stop with an engine vllm config", flush=True)
    other = free_port()
    sleeper = lambda p: subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)",  # noqa: E731
                                          "vllm", "serve", "google/fake", "--port", str(p)])
    mine, theirs, longer = sleeper(port), sleeper(other), sleeper(int(f"{port}1"))
    try:
        p = subprocess.run([sys.executable, "-m", "qa", "--stop", "--config", str(cfg_path)], cwd=ROOT, env=env,
                           capture_output=True, text=True, timeout=60)
        try:
            mine.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        check(p.returncode == 0 and mine.poll() is not None and theirs.poll() is None and longer.poll() is None,
              f"--stop stops the 'vllm serve ... --port {port}' process only (not port {other}, not {port}1) "
              f"({p.stdout.strip()})")
    finally:
        for x in (mine, theirs, longer):
            x.kill()


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


def test_course_page(cfg: LLMConfig, server: QAFake, out: Path, course_meta):
    """course_structure with the course page (CPnn items, cited as "course page"), with and without the statements."""
    import qa
    from qa.answer import cite
    from qa.knowledge import Knowledge
    print("course_structure with the course page", flush=True)
    llm = LLM(cfg, log=lambda *a: None)
    course_meta.load = lambda course: FAKE_PAGE
    n0 = len(server.bodies)
    evs = stream_events("How is the course organised? (page)", llm)
    r = evs[-1]["result"]
    tm = [m for m in server.bodies[n0 + 1]["messages"] if m["role"] == "tool"][0]["content"]
    st = next(e for e in evs if e["event"] == "step")
    i_page, i_cs = tm.index("[CP01]"), tm.index("[CS0001]")
    check(i_page < i_cs and "[CP01] Instructor: Prof. A. Teacher, Department of Testing, IIT Fake. Teaches testing." in tm
          and "[CP02] Prerequisites: Some programming." in tm and "[CP03] Intended audience: UG students." in tm
          and "[CP11] Week 1 \u2014 Basics: Intro; Terms." in tm and "[CP12] Week 2 \u2014 More: Depth." in tm
          and st["label"] == "Course structure read: 6 course page items and 2 statements from lectures 2 and 4"
          and st["detail"]["course_page"] == 6, f"the course page comes before the statements ({st['label']!r})")
    c = r["citations"]
    check(c[0]["lecture"] is None and c[0]["start"] is None and c[0]["source"] == "course page"
          and c[0]["text"].startswith("Instructor: Prof. A. Teacher") and "(course page)" in r["answer"]
          and "CP01" not in r["answer"], f"a CP ID is cited as (course page), no lecture or time: {r['answer']!r}")
    kb = Knowledge.load(COURSE)
    text, cits, dropped = cite(kb, "Taught by X [CP01]. Also [CP99] and [CP02] [CS0001].", {"CP01", "CP02", "CS0001"})
    check(dropped == ["CP99"] and text == "Taught by X (course page). Also and (course page; lecture 2, 1:05)."
          and [x.get("source") for x in cits] == ["course page", "course page", None],
          f"only a CP ID some tool showed is cited, groups mix ({text!r}, {dropped})")
    text, cits, dropped = cite(kb, "Not shown [CP01].", set())
    check(dropped == ["CP01"] and cits == [], "a CP ID no tool showed is dropped")
    n0 = len(server.bodies)
    r = qa.answer("How is the course organised? (lecture 2)", course=COURSE, llm=llm)
    tm = [m for m in server.bodies[n0 + 1]["messages"] if m["role"] == "tool"][0]["content"]
    check("[CP01]" not in tm and "[CS0001]" in tm, "with a lecture the course page is left out")
    sf = out / COURSE / "stage_4f_course_structure" / "course_structure.json"
    keep = sf.read_text(encoding="utf-8")
    sf.unlink()
    try:
        r = qa.answer("How is the course organised? (page)", course=COURSE, llm=llm)
        check(r["steps"][0]["result_summary"] == "6 course page items" and r["covered"] is True
              and "(course page)" in r["answer"], f"the course page alone works ({r['steps'][0]['result_summary']})")
    finally:
        sf.write_text(keep, encoding="utf-8")


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
        test_stream(cfg, server)
        from scripts import course_meta
        keep_load = course_meta.load

        def no_page(course):
            raise FileNotFoundError("course.json")
        course_meta.load = no_page                       # the real course.json is not part of the synthetic layer
        try:
            test_new(cfg, server, out)
            test_course_page(cfg, server, out, course_meta)
        finally:
            course_meta.load = keep_load
        import qa
        ref = qa.answer("What is an HMD?", course=COURSE, llm=LLM(cfg, log=lambda *a: None))
    finally:
        server.stop()
    test_vllm(work, {**os.environ, "QA_OUTPUT": str(out)}, ref)
    print("log", flush=True)
    log = [json.loads(x) for x in (out / COURSE / "qa" / "answers.jsonl").read_text().splitlines()]
    check(len(log) == 39 and all(r["steps"] is not None and "raw_answer" in r for r in log)
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
