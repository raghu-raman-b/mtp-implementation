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
answer time (analysis/qa/STATE.md). answer() and answer_stream() take think (True: round 0 thinks, the shipped
mode; False: no round thinks); None reads $QA_THINK (0 or 1) and then ROUND0_THINK. The mode that ran is "think" in
the answers.jsonl line and in the done event's timing.

The answer cites fact IDs ([4/S1/F2]), segment IDs ([4/S1]) or course-structure statement IDs ([CS0001]; its
citation has the statement's own time) in square brackets. Each one that a tool result showed
becomes a citation (lecture, segment, time, text) and is written into the answer as "(lecture 4, 6:03)"; an ID no
tool showed is dropped (and logged). A time the model wrote before a citation ("at 14:25 [28/S1]") is removed (the
label carries the time); the same label repeated over a run of sentences of one line is written once, at the end of
the run, and a list whose items all carry one label gets it once, on the line that leads into the list. The model's last line "COVERED: yes / partly / no" sets "covered" (yes and
partly: true); without that line, "covered" is whether anything was cited.

answer_stream(question, course, lecture) runs the same loop and yields events as it goes, for a viewer that shows the
answer while it is written and what the model is doing (the blocking answer() is unchanged). Every event carries "t",
the seconds since the question came in. In order: {"event": "round"} when a request goes to the model (the first one
at once: the earliest sign of progress), {"event": "thinking", "chars"} while it thinks (at most every 0.5 s),
{"event": "call", "tool", "args"} when a tool is about to run, {"event": "step", "tool", "args", "result_summary",
"label", "detail", "found", "seconds", ...} when it has run (label: a display line; detail: names, counts, lecture
numbers), {"event": "answer_start"} when the model starts writing text, {"event": "draft", "text"} with the answer so
far (IDs already shown as labels, a half-written bracket or COVERED line held back; each draft replaces the one
before, since the tidying can move a label), {"event": "reset"} when text written in a round turned out not to be the
answer (the round ended in tool calls), and last {"event": "done", "result": <what answer() returns>, "timing"}. The
fields of each event: schemas/qa_stream.md. Its rounds are sent with "stream": true on a kept-open connection
(scripts/llm/http_pool.py: no new SSH channel per round through the demo's port forward); on llama.cpp all rounds of a
question go to one server slot (id_slot), so each round reuses the KV cache of the one before.

Every question is logged to <output>/<course>/qa/answers.jsonl (question, steps with the full tool texts, the raw
and final answer, the dropped IDs, tokens, time) and every model call to <output>/<course>/qa/llm_calls.jsonl.
"""
from __future__ import annotations

import http.client
import json
import os
import re
import sys
import queue
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

from scripts.llm import LLM, LLMConfig, Request
from scripts.llm.client import Result
from scripts.llm.http_pool import POOL

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
# Round 0 (where the tools are chosen): thinking on or off, and its tool_choice. Later rounds: thinking off,
# tool_choice "auto" (the last: "none"). Kept as module switches so analysis/qa/bench.py can try both. Shipped: thinking
# on, "auto". With thinking off Gemma 4 answers some taught topics "not covered" without a search (B17, lecture 46),
# and on llama.cpp neither "required" (the model writes its answer, cannot stop, and runs to max_tokens: 3+ minutes)
# nor a named function (ignored) forces the call (analysis/qa/STATE.md, 2026-11-17).
ROUND0_THINK = True
ROUND0_TOOL_CHOICE = "auto"
FINAL_NUDGE = ("Answer the learner now, from the tool results above only, following the rules: IDs in square "
               "brackets after each claim, and the COVERED line at the end.")
NO_ANSWER = "Sorry, I could not answer that just now. Please try asking again in other words."
PIN_SLOTS = True                # llama.cpp: the rounds of one question go to one server slot (its KV cache is reused)
THINKING_EVERY_S = 0.5          # "thinking" events at most this often

ID = r"(?:(?:\d+[a-z]?|tut_\d+(?:_part\d+)?)/S\d+(?:/F\d+)?|CS\d{4,})"
BRACKET = re.compile(r"\s?[\[(【]([^\[\]()【】]*?" + ID + r"[^\[\]()【】]*?)[\])】]")
BARE = re.compile(r"(?<![\w/])(" + ID + r")(?![\w/])")
# a tool's name the model wrote as if it were a citation ("... lecture 8. [lecture_dependencies]")
TOOL_REF = re.compile(r"[ \t]*[\[(【]`?(?:check_concept|fact_lookup|lecture_dependencies|lecture_overview|course_goals|course_structure)`?[\])】]")
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


def want_think(think: bool | None = None) -> bool:
    """Whether round 0 thinks: the argument, else $QA_THINK (0 or 1), else ROUND0_THINK."""
    if think is not None:
        return bool(think)
    env = os.environ.get("QA_THINK", "").strip().lower()
    if env in ("0", "1", "false", "true", "off", "on"):
        return env in ("1", "true", "on")
    return ROUND0_THINK


def warm(course: str = "nptel_vr", llm=None) -> dict:
    """Load the layer and the query embedder, and start (or attach to) the model server, so that the first
    question does not wait for them (the embedder takes about 10 s to load on the CPU, the server longer). Then one
    request with the system prompt and the tools, as round 0 sends them (max_tokens 1, the slot the first question
    will use), so the server has that prefix cached. With $QA_KEEP_WARM=1 (the demo launcher sets it) the connections
    to the model server and the embedding server are kept open between questions (http_pool.keep_warm). Returns the
    seconds of each part."""
    out = {}
    t = time.time()
    kb = Knowledge.load(course)
    out["layer_s"] = round(time.time() - t, 2)
    t = time.time()
    emb = kb.embedder()
    if emb.model != "fake" and emb._st is None:
        emb._compute(["warm up"])          # loads the model, or reaches the embedding server ($QA_EMBED_URL)
    out["embedder_s"] = round(time.time() - t, 2)
    t = time.time()
    llm = get_llm(llm) if llm is None or isinstance(llm, (str, Path)) else llm
    llm.start()
    out["model_server_s"] = round(time.time() - t, 2)
    t = time.time()
    req = Request(prompt="Hello.", system=system_prompt(kb), tools=tool_specs(), tool_choice=ROUND0_TOOL_CHOICE,
                  key="qa.warm", max_tokens=1, sampling={} if want_think() else
                  {"chat_template_kwargs": {**llm.cfg.chat_template_kwargs, "enable_thinking": False}})
    if llm.cfg.engine == "llamacpp":
        try:                                    # which slots are busy now, so the prefix does not wait behind them
            with POOL.request("GET", llm.server.url + "/slots", timeout=10) as r:
                body = r.read()
                if r.status == 200:
                    _slots_seen(body)
        except (OSError, http.client.HTTPException, ValueError):
            pass
    with pinned_slot(llm) as slot:
        res = stream_round(llm, req, None, lambda _: None, slot=slot)
    out["prefix_s"] = round(time.time() - t, 2)
    out["prefix_tokens"] = res.input_tokens
    if res.errors:
        out["prefix_error"] = "; ".join(res.errors)
    if os.environ.get("QA_KEEP_WARM", "") not in ("", "0"):
        if llm.cfg.engine == "llamacpp":
            POOL.keep_warm(llm.server.url, "/slots", on_body=_slots_seen)
        else:
            POOL.keep_warm(llm.server.url)
        if getattr(emb, "url", None):
            POOL.keep_warm(emb.url)
        out["keep_warm"] = True
    return out


def system_prompt(kb: Knowledge) -> str:
    lectures = "\n".join(f"{k}: {kb.lecture_title(k)}" for k in kb.lectures)
    return SYSTEM_FILE.read_text(encoding="utf-8").format(course_title=kb.title or kb.course, lectures=lectures)


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
    if cid.startswith("CS"):
        s = structure_statements(kb)[cid]
        return {"fact": None, "lecture": str(s["lecture"]), "segment": s.get("segment"), "start": s["start"],
                "end": s.get("end", s["start"]), "text": s["text"]}
    if "/F" in cid:
        f = kb.facts[cid]
        return {"fact": cid, "lecture": f["lecture"], "segment": f["segment"], "start": f["start"], "end": f["end"],
                "text": f["text"]}
    k = cid.split("/")[0]
    s = kb.lectures[k]["segments"][cid]
    return {"fact": None, "lecture": k, "segment": cid, "start": s["start"], "end": s["end"],
            "text": s.get("subgoal", "")}


def structure_statements(kb: Knowledge) -> dict:
    """The course-structure statements by ID (empty without the stage's file)."""
    return {x["id"]: x for x in kb.course_structure() or []}


def cite(kb: Knowledge, text: str, shown: set) -> tuple[str, list[dict], list[str]]:
    """Replace the IDs in the answer by "(lecture 4, 6:03)"; return the text, the citations (in order of first use)
    and the IDs dropped (not shown by any tool, or not in the layer). Only the text is tidied (model-written times
    before a citation removed, repeated labels written once); the citations keep every valid ID cited."""
    citations, index, dropped = [], {}, []
    labels: list[list[str]] = []      # the labels, as their parts ("lecture 4, 6:03"); "\x00n\x00" in the text

    def valid(i: str) -> bool:
        if i.startswith("CS"):
            ok = i in shown and i in structure_statements(kb)
        else:
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

    out = TOOL_REF.sub("", MODEL_TIME.sub("", text))
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
    line leading into the list; then, of a run of equal labels in a row within one line (a paragraph line or a list
    item, never across items: each item is a claim of its own), only the last is kept."""
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
    for n, line in enumerate(lines):         # within one line: a list item is a claim of its own
        toks = list(TOKEN.finditer(line))
        drop = [t for t, nxt in zip(toks, toks[1:]) if key(int(t.group(1))) == key(int(nxt.group(1)))]
        for t in reversed(drop):
            line = line[:t.start()] + line[t.end():]
        lines[n] = line
    return "\n".join(lines)


def split_covered(text: str) -> tuple[str, bool | None]:
    m = None
    for m in COVERED.finditer(text):
        pass
    if not m:
        return text.strip(), None
    verdict = m.group(1).lower()
    return COVERED.sub("", text).strip(), verdict != "no"


# ---------------------------------------------------------------- the loop
def answer(question: str, course: str = "nptel_vr", lecture: str | None = None, llm=None,
           think: bool | None = None) -> dict:
    """{"answer", "citations": [{"fact", "lecture", "segment", "start", "end", "text"}], "steps": [{"tool", "args",
    "result_summary"}], "covered"}. `llm`: an LLM, an LLMConfig, a config path, or None for Gemma 4 12B.
    `think`: round 0 thinks (True, shipped), or no round does (False); None: $QA_THINK, then ROUND0_THINK."""
    return _answer(question, course, lecture, llm, think=think)


def answer_stream(question: str, course: str = "nptel_vr", lecture: str | None = None, llm=None,
                  think: bool | None = None) -> Iterator[dict]:
    """The events of one answer (module docstring), the last always {"event": "done", "result": {...}} with what
    answer() would return (an exception in the loop gives the NO_ANSWER result with "error")."""
    q: queue.Queue = queue.Queue()

    t0 = time.time()

    def run():
        try:
            res = _answer(question, course, lecture, llm, emit=q.put, think=think)
        except Exception as e:                    # noqa: BLE001  the viewer gets an answer, never a hung stream
            res = {"answer": NO_ANSWER, "citations": [], "steps": [], "covered": False,
                   "error": f"{type(e).__name__}: {e}"}
        q.put({"event": "done", "result": res, "t": round(time.time() - t0, 3),
               "timing": _last_timing.pop(threading.get_ident(), {})})

    threading.Thread(target=run, daemon=True).start()
    while True:
        ev = q.get()
        yield ev
        if ev["event"] == "done":
            return


_last_timing: dict = {}           # thread -> the timing of the answer it just streamed (read by answer_stream)


def draft_text(kb: Knowledge, raw: str, shown: set) -> str:
    """The answer so far as the learner may see it: up to the last whitespace (no half-written ID), without an
    unclosed bracket or a COVERED line begun, its IDs shown as labels."""
    cut = raw if not raw or raw[-1].isspace() else raw[:max(raw.rfind(" "), raw.rfind("\n")) + 1]
    opened = max(cut.rfind(c) for c in "[(【")
    if opened > max(cut.rfind(c) for c in "])】"):
        cut = cut[:opened]
    line = cut[cut.rfind("\n") + 1:].strip().lstrip("*").strip().upper()
    if line and ("COVERED".startswith(line[:7]) or line.startswith("COVERED")):
        cut = cut[:cut.rfind("\n") + 1]
    body, _ = split_covered(cut)
    return cite(kb, body, shown)[0] if body else ""


_slot_lock = threading.Lock()
_busy_slots: set = set()
_server_busy = {"at": 0.0, "slots": set()}     # llama.cpp's /slots as the keep-warm ping last saw it


def _slots_seen(body: bytes):
    d = json.loads(body)
    if isinstance(d, list):
        _server_busy.update(at=time.monotonic(), slots={s.get("id") for s in d if s.get("is_processing")})


@contextmanager
def pinned_slot(llm):
    """llama.cpp: the lowest server slot that no question of this process is using and that the server did not show
    busy in its last /slots answer (read by the keep-warm ping, at most a few seconds old; a pinned request waits
    for its slot, so a slot another client is using is skipped). None: vLLM, $QA_PIN_SLOTS=0, or no slot free (the
    server then chooses). One learner's questions thus use slot 0, which holds the system prompt from the one
    before."""
    cfg = getattr(llm, "cfg", None)
    sid = None
    if PIN_SLOTS and cfg is not None and cfg.engine == "llamacpp" and os.environ.get("QA_PIN_SLOTS", "1") != "0":
        with _slot_lock:
            other = _server_busy["slots"] if time.monotonic() - _server_busy["at"] < 6 else set()
            sid = next((i for i in range(max(1, cfg.slots)) if i not in _busy_slots and i not in other), None)
            if sid is not None:
                _busy_slots.add(sid)
    try:
        yield sid
    finally:
        if sid is not None:
            with _slot_lock:
                _busy_slots.discard(sid)


def stream_round(llm: LLM, req: Request, log_file: Path | None, on_text: Callable[[str], None],
                 on_reasoning: Callable[[int], None] | None = None, slot: int | None = None) -> Result:
    """One request sent with "stream": true (the body the client builds, so the same fields as llm.generate, plus on
    llama.cpp "cache_prompt" and the pinned "id_slot") on a kept-open connection; on_text(content so far) at each
    piece of content, on_reasoning(thinking characters so far) at each piece of thinking; the Result as llm.generate
    would give it (no retries: a failed stream is an error, as a failed request is), with meta "ttft_s" (seconds to
    the first streamed piece) and, from llama.cpp, "prompt_n" / "cache_n" (prompt tokens computed / reused)."""
    body = llm._body(req, 0, req.followup)
    res = Result(key=req.key, hash=llm._hash(body), attempts=1)
    body = {**body, "stream": True, "stream_options": {"include_usage": True}}
    if llm.cfg.engine == "llamacpp":
        body["cache_prompt"] = True
        if slot is not None:
            body["id_slot"] = slot
            res.meta["slot"] = slot
    llm.start()
    t0 = time.time()
    content, reasoning, calls = "", "", {}
    try:
        with POOL.request("POST", llm.server.url + "/v1/chat/completions", json.dumps(body).encode(),
                          {"Content-Type": "application/json", "Accept": "text/event-stream"},
                          timeout=llm.cfg.timeout_s) as r:
            if r.status != 200:
                raise RuntimeError(f"server rejected the request ({r.status}): "
                                   f"{r.read().decode(errors='replace')[:500]}")
            for raw in r:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                d = json.loads(data)
                res.meta.setdefault("ttft_s", round(time.time() - t0, 3))
                if d.get("usage"):
                    res.input_tokens = d["usage"].get("prompt_tokens", 0)
                    res.output_tokens = d["usage"].get("completion_tokens", 0)
                if d.get("timings"):
                    tm = d["timings"]
                    res.meta.update({k: tm[k] for k in ("prompt_n", "cache_n", "prompt_ms") if k in tm})
                for ch in d.get("choices") or []:
                    delta = ch.get("delta") or {}
                    piece = delta.get("reasoning_content") or delta.get("reasoning") or ""
                    if piece:
                        reasoning += piece
                        if on_reasoning:
                            on_reasoning(len(reasoning))
                    for tc in delta.get("tool_calls") or []:
                        c = calls.setdefault(tc.get("index", len(calls)), {"id": "", "type": "function",
                                                                          "function": {"name": "", "arguments": ""}})
                        c["id"] = tc.get("id") or c["id"]
                        fn = tc.get("function") or {}
                        c["function"]["name"] += fn.get("name") or ""
                        c["function"]["arguments"] += fn.get("arguments") or ""
                    if delta.get("content"):
                        content += delta["content"]
                        on_text(content)
                    res.finish = ch.get("finish_reason") or res.finish
    except RuntimeError as e:
        res.errors.append(str(e))
    except (OSError, http.client.HTTPException, json.JSONDecodeError) as e:
        res.errors.append(f"stream failed: {type(e).__name__}: {e}")
    res.content, res.reasoning, res.latency_s = content.strip(), reasoning, time.time() - t0
    res.tool_calls = [calls[i] for i in sorted(calls)]
    if res.finish == "length" and req.max_tokens != 1:
        res.errors.append("the answer was cut off at max_tokens")
    res.ok = not res.errors
    res.parsed = res.content
    llm._log_attempt(log_file, req, res, 0)
    return res


def _answer(question: str, course: str, lecture: str | None, llm, emit: Callable[[dict], None] | None = None,
            think: bool | None = None) -> dict:
    t0 = time.time()
    if llm is None or isinstance(llm, (str, Path)):
        llm = get_llm(llm)
    elif isinstance(llm, LLMConfig):
        llm = LLM(llm, log=lambda *a: print(*a, file=sys.stderr))
    if emit is None:
        return _answer_loop(question, course, lecture, llm, t0, None, None, want_think(think))
    with pinned_slot(llm) as slot:              # streamed: every round of this question on one llama.cpp slot
        return _answer_loop(question, course, lecture, llm, t0, emit, slot, want_think(think))


def _answer_loop(question: str, course: str, lecture: str | None, llm, t0: float,
                 emit: Callable[[dict], None] | None, slot: int | None, think_on: bool = True) -> dict:
    if emit is not None:
        raw_emit = emit
        emit = lambda ev: raw_emit({**ev, "t": round(time.time() - t0, 3)})  # noqa: E731
    marks: dict = {}                 # when the stream first showed each thing (for the done event's timing)
    kb = Knowledge.load(course)
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
                      tool_choice="none" if last else ROUND0_TOOL_CHOICE if rnd == 0 else "auto", key=f"qa.{rnd}",
                      sampling=no_think if rnd > 0 or not think_on else {})
        if emit is None:
            res = llm.generate(req, log_file=calls_log)
        else:
            sent, began, thought = [""], [False], [0.0]
            thinks = req.sampling.get("chat_template_kwargs", {}).get("enable_thinking", True) and \
                getattr(llm.cfg, "thinking", True)
            emit({"event": "round", "round": rnd, "final": last, "thinking": bool(thinks)})

            def on_text(raw: str, rnd=rnd, last=last):
                if not began[0] and raw.strip():
                    began[0] = True
                    marks.setdefault("answer_start", round(time.time() - t0, 3))
                    emit({"event": "answer_start", "round": rnd, "forced": last})
                d = draft_text(kb, raw, shown)
                if d and d != sent[0]:
                    sent[0] = d
                    marks.setdefault("first_draft", round(time.time() - t0, 3))
                    emit({"event": "draft", "text": d})

            def on_reasoning(n: int, rnd=rnd):
                now = time.time()
                if now - thought[0] >= THINKING_EVERY_S:
                    thought[0] = now
                    emit({"event": "thinking", "round": rnd, "chars": n})

            res = stream_round(llm, req, calls_log, on_text, on_reasoning, slot=slot)
            if began[0] and res.tool_calls and not last:
                emit({"event": "reset", "round": rnd})
        tokens["input"] += res.input_tokens
        tokens["output"] += res.output_tokens
        timing.append({"round": rnd, "model_s": round(res.latency_s, 2), "in": res.input_tokens,
                       "out": res.output_tokens, "think_chars": len(res.reasoning or ""), "tools": [],
                       **{k: res.meta[k] for k in ("ttft_s", "cache_n", "prompt_n", "slot") if k in res.meta}})
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
            if emit is not None:
                emit({"event": "call", "round": rnd, "index": len(steps), "tool": name,
                      "args": args if args is not None else raw})
            tt = time.time()
            res_found, label, detail = None, "A lookup went wrong; trying again", {"error": "bad arguments"}
            if args is None:
                text, summary, ids = f"The arguments are not valid JSON: {raw!r}", "bad arguments", set()
                found.append(None)
            elif sig in seen:
                text, summary, ids = (f"You already called {name} with these arguments (call {seen[sig]}); its "
                                      "result is above.", "repeated call", set())
                label, detail = "Already looked that up", {"repeated": True}
            else:
                r = run_tool(kb, name, args)
                text, summary, ids = r.text, r.summary, r.shown
                res_found, label, detail = r.found, r.label, r.detail
                found.append(r.found)
                seen[sig] = len(steps) + 1
                timing[-1]["tools"].append({"tool": name, "s": round(time.time() - tt, 3)})
            shown |= ids
            steps.append({"tool": name, "args": args if args is not None else raw, "result_summary": summary})
            if emit is not None:
                marks.setdefault("first_step", round(time.time() - t0, 3))
                emit({"event": "step", **steps[-1], "round": rnd, "index": len(steps) - 1,
                      "seconds": round(time.time() - tt, 3), "found": res_found, "label": label, "detail": detail})
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
           "rounds": len([m for m in conv if m["role"] == "assistant"]), "early_exit": early, "think": think_on, "tokens": tokens,
           "timing": timing, "seconds": round(time.time() - t0, 2)}
    try:
        logs.mkdir(parents=True, exist_ok=True)
        with (logs / "answers.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass
    if emit is not None:
        marks["total"] = round(time.time() - t0, 3)
        _last_timing[threading.get_ident()] = {**marks, "think": think_on, "rounds": timing}
    return out
