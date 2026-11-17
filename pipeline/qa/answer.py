"""The tool loop: a question in, a short cited answer out.

    from qa import answer
    r = answer("What is an HMD?", course="nptel_vr", lecture="4")
    r["answer"], r["citations"], r["steps"], r["covered"]

The model (default: Gemma 4 12B, configs/gemma4_12b_llamacpp.json, on this PC; launched by the client when no server
answers on its port, and left running after the question so the next one does not wait; $QA_CONFIG names another
config, e.g. configs/gemma4_12b_demo.json on a cloud instance, see demo/README.md) gets the system prompt
(prompts/qa_system.txt with the course's lectures), the question, and the tools (prompts/qa_tools.json, run by
qa/tools.py). It calls tools for up to MAX_ROUNDS rounds; then it must answer (tool_choice "none"). It must answer at
once, too, when every tool result so far found nothing close in the course (ToolResult.found False: an unknown name
whose closest facts score low, a fact_lookup with no close fact): the answer is then "not covered", and another
search would only cost time. Thinking (when the config has it on) is used in round 0 only, where the tools are
chosen; later rounds are sent with enable_thinking false, since thinking before the final answer was most of the
answer time (analysis/qa/STATE.md).

The answer cites fact IDs ([4/S1/F2]) or segment IDs ([4/S1]) in square brackets. Each one that a tool result showed
becomes a citation (lecture, segment, time, text) and is written into the answer as "(lecture 4, 6:03)"; an ID no
tool showed is dropped (and logged). A time the model wrote before a citation ("at 14:25 [28/S1]") is removed (the
label carries the time); the same label repeated over a run of sentences is written once, at the end of the run, and
a list whose items all carry one label gets it once, on the line that leads into the list. The model's last line "COVERED: yes / partly / no" sets "covered" (yes and
partly: true); without that line, "covered" is whether anything was cited.

Every question is logged to <output>/<course>/qa/answers.jsonl (question, steps with the full tool texts, the raw
and final answer, the dropped IDs, tokens, time) and every model call to <output>/<course>/qa/llm_calls.jsonl.
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from pathlib import Path

from scripts.llm import LLM, LLMConfig, Request

from .knowledge import Knowledge, fmt_time, lecture_key, qa_dir
from .tools import run_tool, tool_specs

ROOT = Path(__file__).resolve().parent.parent
LOCAL_CONFIG = ROOT / "configs" / "gemma4_12b_llamacpp.json"


def default_config() -> Path:
    """$QA_CONFIG when set (a path as given, else relative to the pipeline folder), else the local Gemma config."""
    env = os.environ.get("QA_CONFIG", "").strip()
    if not env:
        return LOCAL_CONFIG
    p = Path(env).expanduser()
    return p if p.is_absolute() or p.exists() else ROOT / p


DEFAULT_CONFIG = default_config()
SYSTEM_FILE = ROOT / "prompts" / "qa_system.txt"
MAX_ROUNDS = 5                  # rounds of tool calls before the model must answer
FINAL_NUDGE = ("Answer the learner now, from the tool results above only, following the rules: IDs in square "
               "brackets after each claim, and the COVERED line at the end.")
NO_ANSWER = "Sorry, I could not answer that just now. Please try asking again in other words."

ID = r"(?:\d+[a-z]?|tut_\d+(?:_part\d+)?)/S\d+(?:/F\d+)?"
BRACKET = re.compile(r"\s?[\[(【]([^\[\]()【】]*?" + ID + r"[^\[\]()【】]*?)[\])】]")
BARE = re.compile(r"(?<![\w/])(" + ID + r")(?![\w/])")
TIME = r"\d{1,2}:\d{2}(?::\d{2})?"
RANGE = TIME + r"(?:\s*(?:-|–|—|to|and)\s*" + TIME + r")?"
# a time or range the model wrote before a citation: "at 14:25 [..]", "from 14:25 to 15:00 [..]", "(14:25-15:00) [..]";
# a lead-in word or a parenthesised range is needed, so that "an aspect ratio of 16:9 [..]" is kept
MODEL_TIME = re.compile(r"[ \t]*,?[ \t]*(?:\b(?:at|from|around|near|between|by)[ \t]+(?:about[ \t]+|roughly[ \t]+)?"
                        r"(?:the[ \t]+)?(?:time(?:stamp)?[ \t]+|minute[ \t]+)?\(?" + RANGE + r"\)?|\(" + TIME
                        + r"\s*(?:-|–|—|to)\s*" + TIME + r"\))(?=\s?[\[(【][^\[\]()【】]*?" + ID + ")")
TOKEN = re.compile(r"[ \t]*\x00(\d+)\x00")
LIST_ITEM = re.compile(r"^\s*(?:[*\-•]|\d+[.)])\s+")
COVERED = re.compile(r"^\s*\**\s*COVERED\s*:\s*\**\s*(yes|partly|partial|no)\b.*$", re.I | re.M)

_llms: dict[str, LLM] = {}
_llm_lock = threading.Lock()


def get_llm(config: str | Path | None = None, think: bool | None = None) -> LLM:
    """One LLM per config for the process (the viewer's server keeps it; the model server outlives the process)."""
    path = Path(config or DEFAULT_CONFIG)
    key = f"{path.resolve()}|{think}"
    with _llm_lock:
        if key not in _llms:
            cfg = LLMConfig.load(path)
            if think is not None:        # per request (chat template switch); the server's flags are not changed
                cfg = cfg.with_(chat_template_kwargs={**cfg.chat_template_kwargs, "enable_thinking": think})
            if cfg.server_log and not Path(cfg.server_log).is_absolute():
                cfg = cfg.with_(server_log=str(ROOT / cfg.server_log))
            llm = LLM(cfg, log=lambda *a: print(*a, file=sys.stderr))
            llm.progress.out = sys.stderr     # stdout stays for the answer (python -m qa --json)
            _llms[key] = llm
        return _llms[key]


def warm(course: str = "nptel_vr", llm=None) -> None:
    """Load the layer and the query embedder, and start (or attach to) the model server, so that the first
    question does not wait for them (the embedder takes about 10 s to load on the CPU, the server longer)."""
    kb = Knowledge.load(course)
    emb = kb.embedder()
    if emb.model != "fake" and emb._st is None:
        emb._compute(["warm up"])          # loads the model (embed() would not, for a text already in the cache)
    (get_llm(llm) if llm is None or isinstance(llm, (str, Path)) else llm).start()


def system_prompt(kb: Knowledge) -> str:
    lectures = "\n".join(f"{k}: {kb.lecture_title(k)}" for k in kb.lectures)
    return SYSTEM_FILE.read_text().format(course_title=kb.title or kb.course, lectures=lectures)


def user_message(kb: Knowledge, question: str, lecture: str | None) -> str:
    if lecture and lecture in kb.lectures:
        return f'{question.strip()}\n\n(The learner is watching lecture {lecture} "{kb.lecture_title(lecture)}".)'
    return question.strip()


def parse_args(raw) -> dict | None:
    if isinstance(raw, dict):
        return raw
    try:
        d = json.loads(raw or "{}")
    except (json.JSONDecodeError, TypeError):
        return None
    return d if isinstance(d, dict) else None


# ---------------------------------------------------------------- citations
def citation(kb: Knowledge, cid: str) -> dict:
    if "/F" in cid:
        f = kb.facts[cid]
        return {"fact": cid, "lecture": f["lecture"], "segment": f["segment"], "start": f["start"], "end": f["end"],
                "text": f["text"]}
    k = cid.split("/")[0]
    s = kb.lectures[k]["segments"][cid]
    return {"fact": None, "lecture": k, "segment": cid, "start": s["start"], "end": s["end"],
            "text": s.get("subgoal", "")}


def cite(kb: Knowledge, text: str, shown: set) -> tuple[str, list[dict], list[str]]:
    """Replace the IDs in the answer by "(lecture 4, 6:03)"; return the text, the citations (in order of first use)
    and the IDs dropped (not shown by any tool, or not in the layer). Only the text is tidied (model-written times
    before a citation removed, repeated labels written once); the citations keep every valid ID cited."""
    citations, index, dropped = [], {}, []
    labels: list[list[str]] = []      # the labels, as their parts ("lecture 4, 6:03"); "\x00n\x00" in the text

    def valid(i: str) -> bool:
        ok = i in shown and (i in kb.facts or ("/F" not in i and i.split("/")[0] in kb.lectures
                                                and i in kb.lectures[i.split("/")[0]].get("segments", {})))
        if not ok and i not in dropped:
            dropped.append(i)
        return ok

    def label(ids: list[str]) -> str:
        parts = []
        for i in ids:
            if i not in index:
                index[i] = len(citations)
                citations.append(citation(kb, i))
            c = citations[index[i]]
            p = f"lecture {c['lecture']}, {fmt_time(c['start'])}"
            if p not in parts:
                parts.append(p)
        if not parts:
            return ""
        labels.append(parts)
        return f" \x00{len(labels) - 1}\x00"

    def group(m):
        ids = [i for i in re.findall(ID, m.group(1)) if valid(i)]
        return label(list(dict.fromkeys(ids)))

    out = MODEL_TIME.sub("", text)
    out = BRACKET.sub(group, out)
    out = BARE.sub(lambda m: label([m.group(1)]) if valid(m.group(1)) else "", out)
    out = merge_adjacent(out, labels)
    out = "\n\n".join(dedup_block(b, labels) for b in re.split(r"\n[ \t]*\n", out))
    out = TOKEN.sub(lambda m: f" ({'; '.join(labels[int(m.group(1))])})", out)
    out = re.sub(r"\)\s*\(lecture", "; lecture", out)              # "(lecture 4, 1:00) (lecture 5, 2:00)"
    out = re.sub(r"[ \t]+([.,;:!?])", r"\1", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out.strip(), citations, dropped


def merge_adjacent(text: str, labels: list[list[str]]) -> str:
    """Two labels with only spaces between them ("[4/S1/F2] [4/S1/F3]") become one, their parts de-duplicated."""
    pair = re.compile(r"\x00(\d+)\x00[ \t]*\x00(\d+)\x00")
    while True:
        m = pair.search(text)
        if not m:
            return text
        a, b = int(m.group(1)), int(m.group(2))
        labels[a] = list(dict.fromkeys(labels[a] + labels[b]))
        text = text[:m.start()] + f"\x00{a}\x00" + text[m.end():]


def dedup_block(block: str, labels: list[list[str]]) -> str:
    """One paragraph (or list): a list of two or more items that all carry the same one label gets it once, on the
    line leading into the list; then, of a run of equal labels in a row, only the last is kept."""
    key = lambda n: tuple(labels[n])  # noqa: E731
    lines = block.split("\n")
    i = 0
    while i < len(lines):
        if not LIST_ITEM.match(lines[i]):
            i += 1
            continue
        j = i
        while j < len(lines) and LIST_ITEM.match(lines[j]):
            j += 1
        keys = [{key(int(n)) for n in TOKEN.findall(x)} for x in lines[i:j]]
        if j - i >= 2 and i > 0 and not LIST_ITEM.match(lines[i - 1]) and lines[i - 1].strip() \
                and all(len(k) == 1 for k in keys) and len(set.union(*keys)) == 1:
            n = TOKEN.search(lines[i]).group(1)
            lines[i:j] = [TOKEN.sub("", x) for x in lines[i:j]]
            lead = lines[i - 1].rstrip()
            lines[i - 1] = (lead[:-1] + f" \x00{n}\x00:") if lead.endswith(":") else lead + f" \x00{n}\x00"
        i = j
    block = "\n".join(lines)
    toks = list(TOKEN.finditer(block))
    drop = [t for t, nxt in zip(toks, toks[1:]) if key(int(t.group(1))) == key(int(nxt.group(1)))]
    for t in reversed(drop):
        block = block[:t.start()] + block[t.end():]
    return block


def split_covered(text: str) -> tuple[str, bool | None]:
    m = None
    for m in COVERED.finditer(text):
        pass
    if not m:
        return text.strip(), None
    verdict = m.group(1).lower()
    return COVERED.sub("", text).strip(), verdict != "no"


# ---------------------------------------------------------------- the loop
def answer(question: str, course: str = "nptel_vr", lecture: str | None = None, llm=None) -> dict:
    """{"answer", "citations": [{"fact", "lecture", "segment", "start", "end", "text"}], "steps": [{"tool", "args",
    "result_summary"}], "covered"}. `llm`: an LLM, an LLMConfig, a config path, or None for Gemma 4 12B."""
    t0 = time.time()
    kb = Knowledge.load(course)
    if llm is None or isinstance(llm, (str, Path)):
        llm = get_llm(llm)
    elif isinstance(llm, LLMConfig):
        llm = LLM(llm, log=lambda *a: print(*a, file=sys.stderr))
    lec_key = lecture_key(lecture) if lecture not in (None, "") else None
    tools = tool_specs()
    system, user = system_prompt(kb), user_message(kb, question, lec_key)
    logs = qa_dir(course)
    calls_log = logs / "llm_calls.jsonl"
    conv: list[dict] = []
    steps, full_steps, shown, seen = [], [], set(), {}
    final, error, tokens = "", "", {"input": 0, "output": 0}
    timing: list[dict] = []          # per round: model seconds, tokens, thinking chars; per tool call: seconds
    found: list = []                 # ToolResult.found of each tool run (None: an error or bad arguments)
    early = False                    # every result so far found nothing close: the next round is the answer
    no_think = {"chat_template_kwargs": {**getattr(getattr(llm, "cfg", None), "chat_template_kwargs", {}),
                                         "enable_thinking": False}}
    for rnd in range(MAX_ROUNDS + 1):
        last = rnd == MAX_ROUNDS or early
        followup = conv + ([{"role": "user", "content": FINAL_NUDGE}] if last else [])
        req = Request(prompt=user, system=system, followup=followup, tools=tools,
                      tool_choice="none" if last else "auto", key=f"qa.{rnd}",
                      sampling=no_think if rnd > 0 else {})
        res = llm.generate(req, log_file=calls_log)
        tokens["input"] += res.input_tokens
        tokens["output"] += res.output_tokens
        timing.append({"round": rnd, "model_s": round(res.latency_s, 2), "in": res.input_tokens,
                       "out": res.output_tokens, "think_chars": len(res.reasoning or ""), "tools": []})
        if res.errors and not res.content and not res.tool_calls:
            error = "; ".join(res.errors)
            break
        calls = [] if last else res.tool_calls
        if not calls:
            final = res.content
            break
        conv.append({"role": "assistant", "content": res.content or "", "tool_calls": calls})
        for i, call in enumerate(calls):
            fn = call.get("function") or {}
            name, raw = fn.get("name", ""), fn.get("arguments", "{}")
            args = parse_args(raw)
            sig = json.dumps([name, args], sort_keys=True)
            if args is None:
                text, summary, ids = f"The arguments are not valid JSON: {raw!r}", "bad arguments", set()
                found.append(None)
            elif sig in seen:
                text, summary, ids = (f"You already called {name} with these arguments (call {seen[sig]}); its "
                                      "result is above.", "repeated call", set())
            else:
                tt = time.time()
                r = run_tool(kb, name, args)
                text, summary, ids = r.text, r.summary, r.shown
                found.append(r.found)
                seen[sig] = len(steps) + 1
                timing[-1]["tools"].append({"tool": name, "s": round(time.time() - tt, 3)})
            shown |= ids
            steps.append({"tool": name, "args": args if args is not None else raw, "result_summary": summary})
            full_steps.append({**steps[-1], "result": text})
            conv.append({"role": "tool", "tool_call_id": call.get("id") or f"call_{rnd}_{i}", "name": name,
                         "content": text})
        early = bool(found) and all(f is False for f in found)
    body, marker = split_covered(final)
    text, citations, dropped = cite(kb, body, shown)
    if not text:
        text, marker = NO_ANSWER, False
    covered = marker if marker is not None else bool(citations)
    if marker and not citations and not any(s["tool"] in ("course_goals", "lecture_overview") for s in steps):
        covered = False                     # "yes" with nothing cited from the course is not an answer from it
    out = {"answer": text, "citations": citations, "steps": steps, "covered": bool(covered)}
    rec = {"time": round(t0, 3), "course": course, "lecture": lec_key, "question": question, "model": llm.model,
           "steps": full_steps, "raw_answer": final, "answer": text, "citations": [c["fact"] or c["segment"]
                                                                                   for c in citations],
           "dropped_ids": dropped, "covered": out["covered"], "covered_line": marker, "error": error,
           "rounds": len([m for m in conv if m["role"] == "assistant"]), "early_exit": early, "tokens": tokens,
           "timing": timing, "seconds": round(time.time() - t0, 2)}
    try:
        logs.mkdir(parents=True, exist_ok=True)
        with (logs / "answers.jsonl").open("a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return out
