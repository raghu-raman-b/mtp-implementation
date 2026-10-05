"""Subgoal labeling and goal-hierarchy construction with a local llama-server LLM."""
import json
import math
import re
import urllib.error
import urllib.request

from tqdm import tqdm

NON_VERBS = {"the", "a", "an", "this", "that", "these", "to", "in", "on", "for", "of", "goal",
             "lecturer", "lecture", "segment", "it", "he", "she", "they", "we", "i", "introduction",
             "overview", "explanation", "discussion", "definition", "understanding", "description"}


class LLM:
    def __init__(self, base_url="http://127.0.0.1:8080", seed=0, temperature=0.0):
        self.base_url = base_url.rstrip("/")
        self.seed, self.temperature = seed, temperature
        self.log = []  # (label, prompt, reasoning, answer) for every call

    def health(self):
        try:
            with urllib.request.urlopen(self.base_url + "/health", timeout=3) as r:
                return r.status == 200
        except (urllib.error.URLError, OSError):
            return False

    def chat(self, prompt, label, max_tokens=4096):
        """Stream one completion, showing a live thinking/answering token counter."""
        body = json.dumps({
            "messages": [{"role": "user", "content": prompt}],
            "stream": True, "max_tokens": max_tokens,
            "temperature": self.temperature, "seed": self.seed,
        }).encode()
        req = urllib.request.Request(self.base_url + "/v1/chat/completions", data=body,
                                     headers={"Content-Type": "application/json"})
        reasoning, answer = [], []
        bar = tqdm(desc=f"    {label}: thinking", unit="tok", leave=False, dynamic_ncols=True)
        with urllib.request.urlopen(req, timeout=1800) as r:
            for raw in r:
                line = raw.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                choices = json.loads(data).get("choices") or [{}]
                delta = choices[0].get("delta", {})
                if delta.get("reasoning_content"):
                    reasoning.append(delta["reasoning_content"])
                    bar.update(1)
                if delta.get("content"):
                    if not answer:
                        bar.set_description(f"    {label}: answering")
                    answer.append(delta["content"])
                    bar.update(1)
                    bar.set_postfix(think=len(reasoning), answer=len(answer))
        bar.close()
        reasoning, answer = "".join(reasoning).strip(), "".join(answer).strip()
        self.log.append((label, prompt, reasoning, answer))
        return answer

    def chat_nonempty(self, prompt, label):
        for max_tokens in (4096, 8192, 16384):
            out = self.chat(prompt, label, max_tokens)
            if out:
                return out
            tqdm.write(f"    ! {label}: empty answer (thinking hit {max_tokens} tokens), retrying with more")
        raise RuntimeError(f"{label}: model produced no answer")


def clean_goal(text):
    line = next((l for l in text.splitlines() if l.strip()), "").strip()
    line = re.sub(r"^\s*(?:[-*•>#]+|\d+[.)])\s*", "", line)
    line = re.sub(r"^\**\s*(?:goal|answer|subgoal)\s*:\s*\**\s*", "", line, flags=re.I)
    line = line.strip(" *\"'`“”‘’").rstrip(".")
    if line.lower().startswith("to "):
        line = line[3:]
    return line[:1].upper() + line[1:]


def looks_verb_first(goal):
    first = re.match(r"[A-Za-z-]+", goal)
    return bool(first) and first.group().lower() not in NON_VERBS


def _ask_goal(llm, prompt, label):
    goal = clean_goal(llm.chat_nonempty(prompt, label))
    if not looks_verb_first(goal):
        tqdm.write(f"    ! {label}: '{goal}' does not start with a verb, retrying")
        goal = clean_goal(llm.chat_nonempty(
            prompt + "\n\nYour previous answer did not start with a verb. The goal MUST start with a verb "
                     "(e.g. 'Explain ...', 'Define ...', 'Compare ...').", label))
    return goal


# Goals are shown to learners on a learning platform: they should read a goal and
# instantly recall what that part of the lecture covered.
STYLE = """Write the goal for a learner, so that when they look back at it they immediately remember what was covered.
- First work out what this part of the lecture mainly does, for example: raises questions, looks at everyday examples, defines terms, compares things, explains why something matters, or previews the course. The goal must describe that main activity.
- If the part mainly previews the course or recaps earlier material, the goal is about that preview or recap (e.g. "See what this course covers: its aims, main topics and hands-on parts"), not about the individual topics it lists.
- Do not name topics that are only mentioned in passing.
- Start with a simple verb such as Learn, Understand, See, Compare, Explore or Find out.
- Name the concrete topics, terms or examples covered, e.g. "Learn the differences between viruses and bacteria".
- Use plain, everyday words. Avoid vague or academic words such as delineate, contextualize, establish, foundational, framework, paradigm.
- Keep it short: one line, at most 15 words."""

SUBGOAL_PROMPT = (
    "Given this segment of a lecture transcript, what goal do you think the lecturer is trying to "
    "achieve in this segment? Name the goal starting with a verb. Be fine-grained.\n\n"
    + STYLE + "\n\nReply with only the goal.\n\nSegment:\n{text}"
)


def label_subgoal(llm, seg):
    return _ask_goal(llm, SUBGOAL_PROMPT.format(text=seg["text"]), f"{seg['id']} subgoal")


REFINE_PROMPT = (
    "Given this segment of a lecture transcript, what goal do you think the lecturer is trying to "
    "achieve in this segment? Name the goal starting with a verb. Be fine-grained.\n\n"
    "The lecture is split into these segments, in order, with a draft goal for each:\n{outline}\n\n"
    "The goal for this segment must be clearly different from the goals of the other segments, "
    "especially the ones just before and after it. Name what is specific to this segment "
    "(the concrete topics, examples, names or time periods it covers), not what the whole lecture is about.\n\n"
    + STYLE + "\n\nReply with only the goal.\n\nSegment ({sid}):\n{text}"
)


def refine_subgoal(llm, seg, drafts):
    """drafts: [(segment id, draft goal)] for the whole lecture, in order."""
    outline = "\n".join(f"{sid}: {g}" + ("   <- THIS SEGMENT" if sid == seg["id"] else "") for sid, g in drafts)
    return _ask_goal(llm, REFINE_PROMPT.format(outline=outline, sid=seg["id"], text=seg["text"]),
                     f"{seg['id']} refine")


GROUP_PROMPT = """The following are the goals a lecturer pursues, in order, across consecutive parts of one lecture video:

{goals}

Group these goals into higher-level goals so that they form a hierarchical roadmap of the lecture.
Rules:
- Each group must contain consecutive goals, in the order given.
- Every ID must appear in exactly one group.
- Create between {lo} and {hi} groups.
- Each higher-level goal must cover everything in its group, while still naming the concrete topics.

How to write each higher-level goal:
{style}

Answer with only a JSON array, for example:
[{{"goal": "Understand ...", "children": ["{ex1}", "{ex2}"]}}, {{"goal": "Learn ...", "children": ["{ex3}"]}}]"""


def _extract_json_array(text):
    text = re.sub(r"```(?:json)?", "", text)
    a, b = text.find("["), text.rfind("]")
    if a < 0 or b < a:
        raise ValueError("no JSON array found in the answer")
    return json.loads(text[a:b + 1])


def _validate_groups(groups, ids, lo, hi):
    if not isinstance(groups, list) or not all(isinstance(g, dict) for g in groups):
        raise ValueError("answer must be a JSON array of objects")
    seen = []
    for g in groups:
        if not isinstance(g.get("goal"), str) or not g["goal"].strip():
            raise ValueError("every group needs a non-empty 'goal' string")
        if not isinstance(g.get("children"), list) or not g["children"]:
            raise ValueError("every group needs a non-empty 'children' list")
        seen += g["children"]
    unknown = [c for c in seen if c not in ids]
    missing = [i for i in ids if i not in seen]
    dupes = sorted({c for c in seen if seen.count(c) > 1})
    if unknown or missing or dupes:
        raise ValueError(f"unknown IDs {unknown}, missing IDs {missing}, duplicated IDs {dupes}")
    if not lo <= len(groups) <= hi:
        raise ValueError(f"made {len(groups)} groups, need between {lo} and {hi}")


def group_goals(llm, goals, level):
    """goals: list of (id, text) in lecture order -> list of (goal_text, [child ids])."""
    ids = [i for i, _ in goals]
    lo, hi = 2, max(2, math.ceil(len(goals) / 2))
    base = GROUP_PROMPT.format(goals="\n".join(f"{i}: {t}" for i, t in goals), lo=lo, hi=hi, style=STYLE,
                               ex1=ids[0], ex2=ids[1], ex3=ids[2])
    prompt, err = base, None
    for attempt in range(1, 4):
        answer = llm.chat_nonempty(prompt, f"level {level} grouping (try {attempt})")
        try:
            groups = _extract_json_array(answer)
            _validate_groups(groups, ids, lo, hi)
        except (ValueError, json.JSONDecodeError) as e:
            err = e
            tqdm.write(f"    ! invalid grouping: {e}")
            prompt = base + f"\n\nYour previous answer was invalid ({e}). Fix it and answer with only the JSON array."
            continue
        order = {i: k for k, i in enumerate(ids)}
        out = []
        for g in sorted(groups, key=lambda g: min(order[c] for c in g["children"])):
            kids = sorted(g["children"], key=order.get)
            if [order[c] for c in kids] != list(range(order[kids[0]], order[kids[-1]] + 1)):
                tqdm.write(f"    ! note: group '{g['goal']}' has non-consecutive children {kids}")
            out.append((clean_goal(g["goal"]), kids))
        return out
    raise RuntimeError(f"level {level} grouping failed after 3 attempts: {err}")


TOP_PROMPT = """The following is the roadmap of goals a lecturer pursues, in order, in one lecture video. Higher-level goals are listed with the fine-grained goals under them:

{outline}

What is the overall goal of this lecture video? Name the goal starting with a verb.

{style}

Reply with only the goal."""


def top_goal(llm, outline):
    return _ask_goal(llm, TOP_PROMPT.format(outline=outline, style=STYLE), "top goal")
