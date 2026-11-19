"""Shared bits of the activities study: paths, the sample, the transcripts, the three systems' activities, the B2
units (our prompts with the transcript where the facts go), the B1 prompts, the model, the overlap rule.

Environment: ACT_OUT (output folder, default activities_study/out), ACT_LLM (model config, default
pipeline/configs/gemma4_12b_llamacpp.json). The fake test sets both.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BT = HERE.parent                                     # baseline-tests
PIPE = BT.parent / "pipeline"
DATA = PIPE / "output" / "nptel_vr"
COURSE = "nptel_vr"
OUT = Path(os.environ.get("ACT_OUT") or HERE / "out")
LLM_CFG = Path(os.environ.get("ACT_LLM") or PIPE / "configs" / "gemma4_12b_llamacpp.json")
sys.path.insert(0, str(PIPE))
sys.path.insert(0, str(BT))

from scripts import course_meta, lectures as lec  # noqa: E402
from scripts import s5_activities as s5  # noqa: E402
from scripts.llm import LLM, LLMConfig, Request  # noqa: E402

SYSTEMS = ("ours_gemma", "b1", "b2", "ours")    # ours_gemma: our stage re-run on Gemma; ours: shipped (Qwen)
LAYERED = ("ours", "ours_gemma")                 # built from the knowledge layer (fact IDs, concepts)
KINDS = ("quiz", "recap", "open_question", "odd_one_out", "put_in_order", "concept_map", "recall")
JUDGED = ("quiz", "recap", "open_question", "odd_one_out", "put_in_order")   # kinds with a pipeline judge
# the kinds each system makes: ours_gemma only the model-made ones (recall and concept_map are code from the layer,
# the same whatever the model, so ours' are the layer's)
KINDS_OF = {"ours": KINDS, "ours_gemma": JUDGED, "b1": KINDS, "b2": KINDS}
N_SAMPLE = 6
GEN_MAX_TOKENS = 24576   # thinking (server budget 8192) + a whole-lecture answer; the pipeline's 12288 cuts them
STOP = set("""a an the of and or to in on for with by is are was were be been it its this that these those as at from
which what how why when where who can may not no do does into than then so such their there they them he she we you
your our also only more most other each any all both one two three four five six about between through used use uses
using also lecture course""".split())         # baseline-tests/citations.py's list


def words(t: str) -> set[str]:
    """Content words (citations.py's rule)."""
    return {w for w in re.findall(r"[a-z0-9]+", str(t).lower()) if w not in STOP and len(w) > 2}


# ---------------------------------------------------------------- the course
INDEX = json.loads((DATA / "knowledge" / "index.json").read_text())
KEYS = list(INDEX["lectures"])
TITLES = {k: json.loads((DATA / "knowledge" / "lectures" / f"{lec.stem_of(k)}.json").read_text())["title"]
          for k in KEYS}


def ours_file(k: str) -> dict:
    return json.loads((DATA / "activities" / f"{lec.stem_of(k)}.json").read_text())


def sample() -> list[str]:
    """The rule: the lectures whose activities (ours) have every kind of the study (recall needs an earlier
    lecture, put_in_order and odd_one_out a lecture whose facts allow them), in course order; then 6 of them evenly
    spaced: positions round(i * (n - 1) / 5), i = 0..5 (the first and the last always in)."""
    full = [k for k in KEYS if (DATA / "activities" / f"{lec.stem_of(k)}.json").exists()
            and set(KINDS) <= {a["kind"] for a in ours_file(k)["activities"]}]
    n = len(full)
    return [full[round(i * (n - 1) / (N_SAMPLE - 1))] for i in range(N_SAMPLE)]


def sentences(k: str) -> list[tuple[str, str]]:
    """Stage 0a's sentences of the human subtitles: [(id, text)] in order."""
    return list(json.loads((DATA / "stage_0a_preprocess" / f"{lec.stem_of(k)}.json").read_text()).items())


def numbered(k: str) -> str:
    return "\n".join(f"[{i}] {t}" for i, (_, t) in enumerate(sentences(k), 1))


def plain_transcript(k: str) -> str:
    return " ".join(t for _, t in sentences(k))


def earlier(k: str) -> list[str]:
    return [x for x in KEYS if lec.order(x) < lec.order(k)]


ITEMS = {"quiz": "questions", "open_question": "questions", "odd_one_out": "items", "put_in_order": "items",
         "recall": "items", "concept_map": "edges", "recap": "points"}


def items_of(kind: str, data: dict) -> list:
    """The items of an activity's data, as judged and counted (recap: its points)."""
    return data.get(ITEMS[kind]) or []


def ours_counts(k: str) -> dict:
    """Items per kind of our activities of lecture k (the baselines are asked for the same counts)."""
    c = {x: 0 for x in KINDS}
    for a in ours_file(k)["activities"]:
        if a["kind"] in c:
            c[a["kind"]] += len(items_of(a["kind"], a["data"]))
    return c


def activities(system: str, k: str) -> list[dict]:
    """The activities (contract of pipeline/schemas/activities.md) of a system for lecture k, study kinds only."""
    if system == "ours":
        acts = ours_file(k)["activities"]
    elif system == "ours_gemma":
        p = OUT / "gen" / "ours_gemma" / f"{lec.stem_of(k)}.json"
        acts = json.loads(p.read_text())["activities"] if p.exists() else []
    else:
        p = OUT / "gen" / system / f"{lec.stem_of(k)}.json"
        acts = json.loads(p.read_text())["activities"] if p.exists() else []
    return [a for a in acts if a["kind"] in KINDS_OF[system]]


def gen_info(system: str, k: str) -> dict:
    p = OUT / "gen" / system / f"{lec.stem_of(k)}.json"
    return json.loads(p.read_text()).get("units", {}) if p.exists() else {}


# ---------------------------------------------------------------- the transcript as the "facts" (B2)
class TLayer:
    """What s5's convert functions read of the layer, with the transcript sentences in place of the facts."""

    def __init__(self, k: str):
        self.facts = {i: {"text": t, "lecture": k, "segment": None, "concepts": []} for i, t in sentences(k)}
        self.lectures = {k: {"concept_map": {"relations": [], "concepts": []}, "segments": {}}}
        self.relations, self.cards = {}, {}

    def fact_concepts(self, fids):
        return []


NG, NONE = "(not given)", "(none)"
O, A, S = s5.obj, s5.arr, s5.S


def b2_unit(kind: str, k: str) -> s5.Unit:
    """Our prompt of the kind, filled with the whole lecture transcript, numbered by sentence, where the facts go.
    Inputs the knowledge layer makes are given as "(not given)" (segment sub-goal, objective, lecture goal) or
    "(none)" (related concepts and other facts, concepts, relationships). Counts: ours' items of the lecture."""
    sents = sentences(k)
    shown, n, c = [i for i, _ in sents], len(sents), max(1, ours_counts(k)[kind])
    blocks = dict(course=course_meta.course_prompt(COURSE), lecture_title=TITLES[k])
    facts = numbered(k)
    ctx = {"shown": shown, "lo": c, "hi": c, "blocks": blocks}
    if kind == "quiz":
        blocks.update(subgoal=NG, facts=facts, related=NONE)
        q = O({"facts": s5.nums_schema(n), "question": S, "correct": S, "wrong": A(S, 3, 3), "explanation": S})
        schema, prompt = O({"questions": A(q, c, c)}), s5.fill("quiz", **blocks, count=s5.count_text(c, c))
    elif kind == "recap":
        blocks.update(subgoal=NG, objective=NG, facts=facts)
        schema = O({"points": A(O({"facts": s5.nums_schema(n), "point": S}), c, c), "text": S})
        prompt = s5.fill("recap", **blocks, count=s5.count_text(c, c))
    elif kind == "open_question":
        blocks.update(goal=NG, facts=facts, relations=NONE, concepts=NONE)
        ctx.update(names={}, earlier=[])
        q = O({"key_facts": s5.nums_schema(n, 2), "question": S, "reference_answer": S,
               "concepts": {"type": "array", "items": S, "maxItems": 0}})
        schema, prompt = O({"questions": A(q, c, c)}), s5.fill("open_question", **blocks, count=s5.count_text(c, c))
    elif kind == "odd_one_out":
        blocks.update(concepts=NONE, relations=NONE, facts=facts)
        ctx["names"] = set()
        item = O({"facts": s5.nums_schema(n), "group": A(S, 3, 3), "odd": S, "reason": S})
        schema, prompt = O({"items": A(item, c, c)}), s5.fill("odd_one_out", **blocks)
    elif kind == "put_in_order":
        blocks.update(facts=facts)
        item = O({"facts": s5.nums_schema(n), "title": S, "steps": A(S, 3, 8)})
        schema, prompt = O({"items": A(item, c, c)}), s5.fill("put_in_order", **blocks)
    else:                     # concept_map, recall: code-made from the layer in ours, so no prompt of ours exists
        prompt, schema = b1_prompt(kind, k, cite=True)
        u = s5.Unit(kind, k, None, f"b2:{kind}:{k}", ctx)
        u.request = Request(prompt=prompt, key=u.key, schema=schema, max_tokens=GEN_MAX_TOKENS,
                            meta={"system": "b2", "kind": kind, "lecture": k})
        return u
    u = s5.Unit(kind, k, None, f"b2:{kind}:{k}", ctx)
    u.request = s5.request(u, prompt, schema, None)
    u.request.max_tokens = GEN_MAX_TOKENS
    u.request.meta["system"] = "b2"
    return u


# ---------------------------------------------------------------- B1: plain prompts
B1_TEMPLATE = """You make learning activities for one lecture of the online course "Foundation for Virtual and Augmented Reality Systems" (NPTEL). Below is the full transcript of the lecture.

LECTURE: {title}

TRANSCRIPT
{transcript}

TASK
{task}

Answer with the JSON only, in this form:
{form}"""

B1_TASKS = {
    "quiz": ("Write {n} multiple-choice questions on the lecture, to check what a learner understood. Each question has "
             "four options, exactly one of them correct. \"answer\" is the index (0 to 3) of the correct option; "
             "\"explanation\" says why it is correct.",
             '{"questions": [{"question": "...", "options": ["...", "...", "...", "..."], "answer": 0, "explanation": "..."}]}'),
    "recap": ("Write a recap of the lecture for a learner: a short text of a few sentences, and {n} key points, one "
              "sentence each.", '{"text": "...", "points": ["...", "..."]}'),
    "open_question": ("Write {n} open questions that make a learner think about what the lecture teaches, each with a "
                      "reference answer.", '{"questions": [{"question": "...", "reference_answer": "..."}]}'),
    "odd_one_out": ("Write {n} odd-one-out puzzles on the lecture. Each has four items: three belong to a group the "
                    "lecture teaches and one does not. \"odd\" is the index (0 to 3) of the odd item; \"reason\" says "
                    "why.", '{"items": [{"options": ["...", "...", "...", "..."], "odd": 0, "reason": "..."}]}'),
    "put_in_order": ("Write {n} put-in-order exercises on the lecture: each a title and 3 to 8 steps of a process or "
                     "sequence the lecture teaches, in the correct order.",
                     '{"items": [{"title": "...", "steps": ["...", "...", "..."]}]}'),
    "concept_map": ("Make a concept map of the lecture: its main concepts as nodes and the relationships between them "
                    "as labelled edges from one node to another (labels such as \"is a kind of\", \"causes\", "
                    "\"is part of\").",
                    '{"nodes": [{"id": "n1", "label": "..."}], "edges": [{"from": "n1", "to": "n2", "label": "..."}]}'),
    "recall": ("This lecture builds on earlier lectures of the course (listed below). Write {n} recall questions to "
               "show before the lecture, each on a concept from an earlier lecture that this lecture needs: the "
               "concept, the question \"What is <concept>?\", a short answer, and the number of the earlier lecture "
               "that teaches it.\n\nEARLIER LECTURES\n{earlier}",
               '{"items": [{"concept": "...", "prompt": "What is ...?", "answer": "...", "from_lecture": "4"}]}'),
}
CITE = ("\n\nThe transcript sentences are numbered in brackets. With each {what} give \"facts\": the numbers of the "
        "sentences it is taken from.")


def b1_prompt(kind: str, k: str, cite: bool = False) -> tuple[str, dict]:
    """B1's prompt and schema (the contract's data of the kind); with cite (B2's concept_map and recall) the
    transcript is numbered and each edge or item cites its sentence numbers."""
    n = max(1, ours_counts(k)[kind])
    task, form = B1_TASKS[kind]
    task = task.format(n=n, earlier="\n".join(f"{x}: {TITLES[x]}" for x in earlier(k)))
    nums = {"facts": s5.nums_schema(len(sentences(k)))} if cite else {}
    if cite:
        task += CITE.format(what="edge" if kind == "concept_map" else "item")
        form = form.replace('"label": "..."}]}', '"label": "...", "facts": [1, 2]}]}') if kind == "concept_map" \
            else form.replace('"from_lecture": "4"', '"from_lecture": "4", "facts": [1, 2]')
    prompt = B1_TEMPLATE.format(title=TITLES[k], transcript=numbered(k) if cite else plain_transcript(k),
                                task=task, form=form)
    four = A(S, 4, 4)
    idx = {"type": "integer", "minimum": 0, "maximum": 3}
    schema = {
        "quiz": O({"questions": A(O({"question": S, "options": four, "answer": idx, "explanation": S}), n, n)}),
        "recap": O({"text": S, "points": A(S, n, n)}),
        "open_question": O({"questions": A(O({"question": S, "reference_answer": S}), n, n)}),
        "odd_one_out": O({"items": A(O({"options": four, "odd": idx, "reason": S}), n, n)}),
        "put_in_order": O({"items": A(O({"title": S, "steps": A(S, 3, 8)}), n, n)}),
        "concept_map": O({"nodes": A(O({"id": S, "label": S}), 2, 40),
                          "edges": A(O({"from": S, "to": S, "label": S, **nums}), 1, 60)}),
        "recall": O({"items": A(O({"concept": S, "prompt": S, "answer": S, "from_lecture": S, **nums}), n, n)}),
    }[kind]
    return prompt, schema


def b1_request(kind: str, k: str) -> Request:
    prompt, schema = b1_prompt(kind, k)
    return Request(prompt=prompt, key=f"b1:{kind}:{k}", schema=schema, max_tokens=GEN_MAX_TOKENS,
                   meta={"system": "b1", "kind": kind, "lecture": k})


# ---------------------------------------------------------------- model
def make_llm(concurrency: int = 0) -> LLM:
    """The config's model; concurrency > 0 caps the requests in flight (generation: long whole-lecture answers
    share the server's one 131k KV pool)."""
    cfg = LLMConfig.load(LLM_CFG)
    return LLM(cfg.with_(concurrency=concurrency) if concurrency else cfg)


def cache_files() -> dict:
    (OUT / "llm").mkdir(parents=True, exist_ok=True)
    return {"cache_file": OUT / "llm" / "cache.jsonl", "log_file": OUT / "llm" / "calls.jsonl"}


# ---------------------------------------------------------------- overlap rule (traceability without fact IDs)
def overlap(text: str, k: str, width: int = 3) -> tuple[float | None, list[str]]:
    """Share of the text's content words found in the best window of `width` consecutive transcript sentences of
    lecture k, and that window's sentence IDs (None when the text has no content word)."""
    kw = words(text)
    sents = sentences(k)
    if not kw or not sents:
        return None, []
    sw = [words(t) for _, t in sents]
    best, at = -1, 0
    for i in range(max(1, len(sents) - width + 1)):
        got = len(kw & set().union(*sw[i:i + width]))
        if got > best:
            best, at = got, i
    return round(best / len(kw), 3), [i for i, _ in sents[at:at + width]]


TRACE_MIN = 0.6
