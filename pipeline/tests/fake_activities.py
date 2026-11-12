"""Plumbing test of stage 5 (activities) with a scripted fake model, on the local PC.

    python3 tests/fake_activities.py [--work DIR] [--keep]

Builds a synthetic knowledge/ the way tests/fake_knowledge.py does (its copy of the pipeline folder, its synthetic
registry over the real segment maps of lectures 1 to 8, stages 4a to 4d with its fake answers), with seven more
concepts defined in lecture 4 (so it has a crossword of 6 or more answers) and three more relationships there ("is a
kind of" twice, "writes to"), and definitions that differ per concept. Everything runs in a new temporary folder;
the fake model listens on a free port (never 8094 or 8095, the SSH forward to the EC2) through a copy of the Qwen
config with model_path "fake/qwen" and no wait.

The fake's activity answers fit the schema (fake_server.fake); per unit (found by the first fact number in the
prompt, "Fact 4/S1/F0: ...", or a crossword answer's name) it seeds, by attempt:
  quiz 4/S1        attempt 1: a wrong option equal to the correct one, a fact number 99; then right (retried)
  quiz 5/S0        question 2 has two equal options in every attempt (unresolved: question 2 dropped, others kept)
  recap 2/S0       attempt 1: an empty text; then right
  open_question 3  attempt 1: question 1 cites one fact; then right
  crossword        "rasterization": attempt 1 a clue with "rasterized"; then right. "ray tracing": a clue with
                   "tracing" in every attempt (unresolved: masked "___")
  odd_one_out 6    never JSON (no answer: no activity)
  put_in_order     lecture 1 answers none (no activity); lecture 3 cites facts of two segments (lecture scope)

What it looks for (each line is what a broken stage would show):
  contract  a file not matching schemas/activities.md (checked by an independent validator here and by the stage's
            own --check); a cited fact or concept that does not exist, or a question's facts not in the activity's
  kinds     a kind missing (all ten, put_in_order on both scopes, spaced-review cards)
  quiz      the answer index not pointing at the model's correct option, or always the same position
  retry     a seeded bad answer not retried, retried without its problem shown, or not fixed; an unresolved
            answer thrown away instead of kept with its bad items dropped; a never-JSON answer making an activity;
            "none" making an empty activity
  crossword letters that clash, an entry outside the grid or crossing none, an answer not the concept's letters,
            a clue writing the answer or its words, fewer than 6 answers where 8 are defined
  maps      a blank's answer not the hidden value, a wrong option that is also right, a hidden concept that is on
            another edge; an edge, pair or entry without its facts
  recall    a concept not needed by the lecture, from a lecture not earlier, or lecture 1 with a recall
  prompts   a placeholder left unfilled, no course block, facts not numbered
  rerun     the model called again, or an output file different; --kinds of code-made kinds changing anything
  seeded    the stage's own contract check missing seeded damage (a clash, an unknown fact, an index out of range,
            a missing field)
  output    any file under the real output/ created or changed
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the pipeline folder
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import fake_knowledge as fk  # noqa: E402
from scripts import lectures as lec  # noqa: E402
from scripts import s5_activities as s5  # noqa: E402
from scripts.llm.client import FEEDBACK  # noqa: E402
from scripts.llm.fake_server import fake  # noqa: E402

COURSE = fk.COURSE
FAILURES = fk.FAILURES
check = fk.check

fk.SPEC += [("rasterization", [], [("4/S0", True, 1)]), ("ray tracing", [], [("4/S0", True, 1)]),
            ("shader", [], [("4/S1", True, 1)]), ("frame buffer", [], [("4/S1", True, 1)]),
            ("texture mapping", [], [("4/S2", True, 1)]), ("polygon mesh", [], [("4/S2", True, 1)]),
            ("depth buffer", [], [("4/S3", True, 1)])]
fk.RELS += [("rasterization", "is a kind of", "rendering", "4/S0"), ("ray tracing", "is a kind of", "rendering", "4/S0"),
            ("shader", "writes to", "frame buffer", "4/S1")]

FIRST_FACT = re.compile(r"^\[1\] (?:\([^)]*\) )?Fact (\S+?):", re.M)
ANSWER_LINE = re.compile(r"^\[(\d+)\] (.+?) \(other names", re.M)


def kind_of(schema: dict) -> str | None:
    p = schema.get("properties", {})
    if "clues" in p:
        return "crossword"
    if "points" in p:
        return "recap"
    if "questions" in p:
        return "quiz" if "wrong" in p["questions"]["items"]["properties"] else "open_question"
    if "items" in p:
        return "odd_one_out" if "group" in p["items"]["items"]["properties"] else "put_in_order"
    return None


class ActivitiesFake(fk.KnowledgeFake):
    """KnowledgeFake for stages 4a/4b (distinct definitions), and the seeded activity answers of the docstring."""

    @staticmethod
    def definition(name: str, n: int, attempt: int) -> str:
        a = fk.KnowledgeFake.definition(name, n, attempt)
        tag = hashlib.md5(name.encode()).hexdigest()[:6]
        return a.replace("a fake concept of the course.", f"the synthetic notion {tag} of the course. More text.")

    def answer(self, body: dict) -> dict:
        fmt = (body.get("response_format") or {}).get("json_schema", {})
        kind = kind_of(fmt.get("schema") or {})
        if kind is None:
            return super().answer(body)
        prompt = body["messages"][0]["content"]
        attempt = body.get("seed", 0) - self.base_seed
        m = FIRST_FACT.search(prompt)
        unit = m[1].rsplit("/", 1)[0] if m else ""
        lecture = unit.split("/")[0]
        with self.lock:
            self.requests += 1
            n = self.requests
        a = fake(fmt["schema"], "answer", n)
        content = None
        if kind == "quiz" and unit == "4/S1" and attempt == 0:
            a["questions"][0]["wrong"][0] = a["questions"][0]["correct"]
            a["questions"][1]["facts"] = [99]
        elif kind == "quiz" and unit == "5/S0":
            a["questions"][1]["wrong"][1] = a["questions"][1]["wrong"][0]
        elif kind == "recap" and unit == "2/S0" and attempt == 0:
            a["text"] = ""
        elif kind == "open_question" and lecture == "3" and attempt == 0:
            a["questions"][0]["key_facts"] = [1]
        elif kind == "odd_one_out" and lecture == "6":
            content = fk.NOT_JSON
        elif kind == "put_in_order" and lecture == "1":
            a = {"items": []}
        elif kind == "put_in_order" and lecture == "3":
            a["items"] = a["items"][:1]
            a["items"][0]["facts"] = [1, len(re.findall(r"^\[\d+\]", prompt, re.M))]
        elif kind == "crossword":
            names = {int(i): nm for i, nm in ANSWER_LINE.findall(prompt)}
            for c in a["clues"]:
                if names.get(c["number"]) == "rasterization" and attempt == 0:
                    c["clue"] = "Rasterized output of a pipeline"
                if names.get(c["number"]) == "ray tracing":
                    c["clue"] = "Tracing of light paths"
        if content is None:
            content = json.dumps(a)
        with self.lock:
            if self.log:
                with open(self.log, "a") as f:
                    f.write(json.dumps({"kind": kind, "unit": unit, "attempt": attempt, "messages": body["messages"],
                                        "schema": fmt["schema"]}) + "\n")
        return {"choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": len(prompt) // 4, "completion_tokens": len(content) // 4}}


# ---------------------------------------------------------------- an independent contract validator
DATA = {"quiz": {"questions"}, "recap": {"text", "points"}, "recall": {"items"}, "open_question": {"questions"},
        "concept_map": {"nodes", "edges"}, "complete_map": {"nodes", "edges", "blanks"},
        "crossword": {"width", "height", "entries"}, "match_pairs": {"pairs"}, "odd_one_out": {"items"},
        "put_in_order": {"items"}}
ITEM = {"quiz": ("questions", {"question", "options", "answer", "explanation", "facts"}),
        "recall": ("items", {"concept", "prompt", "answer", "from_lecture"}),
        "open_question": ("questions", {"question", "reference_answer", "key_facts", "concepts"}),
        "match_pairs": ("pairs", {"left", "right", "concept", "facts"}),
        "odd_one_out": ("items", {"options", "odd", "reason", "facts"}),
        "put_in_order": ("items", {"title", "steps", "facts"}),
        "crossword": ("entries", {"number", "answer", "clue", "row", "col", "direction", "concept", "facts"})}


def contract(act: Path, kd: Path) -> list[str]:
    facts = json.loads((kd / "facts.json").read_text())
    concepts = json.loads((kd / "concepts.json").read_text())
    relations = json.loads((kd / "relations.json").read_text())
    P = []
    for p in sorted(act.glob("lec_*.json")):
        d = json.loads(p.read_text())
        k = p.stem[4:]
        segs = json.loads((kd / "lectures" / p.name).read_text())["segments"]
        if sorted(d) != ["activities", "lecture"] or d["lecture"] != k:
            P.append(f"{p.name}: top level")
        for i, a in enumerate(d["activities"]):
            w = f"{p.name} {a.get('id')}"
            if list(a) != ["id", "kind", "scope", "segment", "title", "data", "facts", "concepts"]:
                P.append(f"{w}: fields {list(a)}")
                continue
            if a["id"] != f"{k}/A{i}" or not a["title"]:
                P.append(f"{w}: id or title")
            if (a["scope"] == "segment") != (a["segment"] is not None) or (a["segment"] and a["segment"] not in segs):
                P.append(f"{w}: scope/segment")
            want_scope = {"quiz": ["segment"], "recap": ["segment"], "put_in_order": ["segment", "lecture"]}
            if a["scope"] not in want_scope.get(a["kind"], ["lecture"]):
                P.append(f"{w}: scope {a['scope']} for {a['kind']}")
            if not a["facts"] or any(f not in facts for f in a["facts"]):
                P.append(f"{w}: facts empty or unknown")
            if not a["concepts"] or any(c not in concepts for c in a["concepts"]):
                P.append(f"{w}: concepts empty or unknown")
            data = a["data"]
            if set(data) != DATA[a["kind"]]:
                P.append(f"{w}: data fields {sorted(data)}")
                continue
            if a["kind"] in ITEM:
                name, fields = ITEM[a["kind"]]
                for it in data[name]:
                    if set(it) != fields:
                        P.append(f"{w}: item fields {sorted(it)}")
                    for fl in ("facts", "key_facts"):
                        if fl in it and (not it[fl] or not set(it[fl]) <= set(a["facts"])):
                            P.append(f"{w}: item {fl} empty or not in the activity's facts")
                    if "concept" in it and it["concept"] not in concepts:
                        P.append(f"{w}: item concept unknown")
                    if "concepts" in it and not set(it["concepts"]) <= set(concepts):
                        P.append(f"{w}: item concepts unknown")
            if a["kind"] == "quiz":
                for q in data["questions"]:
                    if len(q["options"]) != 4 or len(set(q["options"])) != 4 or q["answer"] not in range(4):
                        P.append(f"{w}: options or answer")
            if a["kind"] == "odd_one_out":
                for it in data["items"]:
                    if len(set(it["options"])) != 4 or it["odd"] not in range(4):
                        P.append(f"{w}: options or odd")
            if a["kind"] in ("concept_map", "complete_map"):
                ids = {n["id"] for n in data["nodes"]}
                for e in data["edges"]:
                    if set(e) != {"from", "to", "label", "relation", "facts"} or not {e["from"], e["to"]} <= ids \
                            or e["relation"] not in relations or not set(e["facts"]) <= set(a["facts"]):
                        P.append(f"{w}: edge")
            if a["kind"] == "crossword":
                P += [f"{w}: {m}" for m in grid_problems(data)]
            if a["kind"] == "recap" and (not data["text"] or not data["points"]):
                P.append(f"{w}: empty recap")
    course = json.loads((act / "course.json").read_text())
    for c in course["spaced_review"]["cards"]:
        if set(c) != {"concept", "front", "back", "lectures"} or c["concept"] not in concepts or not c["back"]:
            P.append(f"course.json card {c.get('concept')}")
    return P


def grid_problems(d: dict) -> list[str]:
    grid, cells, P = {}, [], []
    for e in d["entries"]:
        if not re.fullmatch(r"[A-Z]+", e["answer"]):
            P.append(f"answer {e['answer']}")
        dr, dc = (0, 1) if e["direction"] == "across" else (1, 0)
        cs = set()
        for j, ch in enumerate(e["answer"]):
            r, c = e["row"] + j * dr, e["col"] + j * dc
            if not (0 <= r < d["height"] and 0 <= c < d["width"]):
                P.append(f"{e['answer']} outside the grid")
            if grid.setdefault((r, c), ch) != ch:
                P.append(f"{e['answer']}: {ch} clashes with {grid[(r, c)]}")
            cs.add((r, c))
        cells.append(cs)
    for i, cs in enumerate(cells):
        if not any(cs & o for j, o in enumerate(cells) if j != i):
            P.append(f"{d['entries'][i]['answer']} crosses nothing")
    return P


# ---------------------------------------------------------------- the test
def acts(out: Path, k: str) -> list[dict]:
    return json.loads((out / f"lec_{k}.json").read_text())["activities"]


def requests_of(log: Path, kind: str, unit: str) -> list[dict]:
    return [r for r in fk.lines(log) if r.get("kind") == kind and r.get("unit") == unit]


def test_s5(work: Path, log: Path):
    print("5 activities", flush=True)
    rc = fk.stage(work, "s5_activities.py", ["--llm", "configs/fake_qwen.json"], work / "5.log", "activities")
    check(rc == 0, "s5 exits cleanly (its own contract check finds nothing)")
    out, kd = work / "output" / COURSE / "activities", work / "output" / COURSE / "knowledge"
    check(all((out / f).exists() for f in ("course.json", "checks.json", "activities.txt", "llm/cache.jsonl"))
          and all((out / f"lec_{k}.json").exists() for k in fk.KEYS), "every lecture file, course.json, checks, "
          "text view and cache written")
    P = contract(out, kd)
    check(not P, f"the independent validator finds nothing ({'; '.join(P[:4]) or 'all good'})")
    checks = json.loads((out / "checks.json").read_text())
    check(checks["contract"] == [], "checks.json: the stage's contract check is empty")
    every = [a for k in fk.KEYS for a in acts(out, k)]
    kinds = {a["kind"] for a in every}
    check(kinds == set(s5.KINDS) - {"spaced_review"}, f"every kind made ({sorted(kinds)})")
    check({a["scope"] for a in every if a["kind"] == "put_in_order"} == {"segment", "lecture"},
          "put_in_order on a segment and on a lecture")
    cards = json.loads((out / "course.json").read_text())["spaced_review"]["cards"]
    cards_ok = json.loads((kd / "concepts.json").read_text())
    check(len(cards) == sum(1 for c in cards_ok.values() if c["defined"] and c["definition"].strip()) > 10,
          f"a spaced-review card per defined concept ({len(cards)})")

    # quiz: the index points at the model's correct option
    qs = [q for a in every if a["kind"] == "quiz" for q in a["data"]["questions"]]
    check(all(q["options"][q["answer"]].startswith("fake correct") for q in qs)
          and len({q["answer"] for q in qs}) > 1, f"quiz: the answer index is the correct option, in "
          f"{len({q['answer'] for q in qs})} positions over {len(qs)} questions")

    # prompts
    sent = [r for r in fk.lines(log) if r.get("kind")]
    left = [r["kind"] for r in sent if re.search(r"\{(course|facts|related|count|subgoal|objective|goal|relations|"
                                                 r"concepts|answers|lecture_title)\}", r["messages"][0]["content"])]
    check(not left and all("THE COURSE" in r["messages"][0]["content"] for r in sent)
          and all(re.search(r"^\[1\] ", r["messages"][0]["content"], re.M) for r in sent),
          f"prompts: no placeholder left, the course block and numbered material in all {len(sent)}")

    # retries
    def retried(kind, unit, text):
        rs = requests_of(log, kind, unit)
        second = [r for r in rs if r["attempt"] == 1]
        shown = second and any(text in m["content"] for m in second[0]["messages"][1:] if m["role"] == "user") \
            and FEEDBACK.split("\n")[0] in second[0]["messages"][-1]["content"]
        return len(rs) >= 2 and bool(shown)
    lc = checks["lectures"]
    check(retried("quiz", "4/S1", "the options repeat") and retried("quiz", "4/S1", "[99], not in the list")
          and lc["4"]["quiz"]["quiz:4/S1"]["status"] == "ok", "retry: quiz options repeated and a fact out of "
          "range, shown to the model, fixed")
    q5 = lc["5"]["quiz"]["quiz:5/S0"]
    a5 = next(a for a in acts(out, "5") if a["kind"] == "quiz" and a["segment"] == "5/S0")
    check(q5["status"] == "unresolved" and [d["item"] for d in q5["dropped"]] == [2]
          and len(requests_of(log, "quiz", "5/S0")) == 3 and len(a5["data"]["questions"]) >= 2
          and "quiz:5/S0" in checks["totals"]["unresolved"],
          "unresolved quiz: three attempts, the bad question dropped, the others kept")
    check(retried("recap", "2/S0", '"text" is empty') and lc["2"]["recap"]["recap:2/S0"]["status"] == "ok",
          "retry: an empty recap text")
    u3 = next(r["unit"] for r in sent if r["kind"] == "open_question" and r["unit"].startswith("3/"))
    check(retried("open_question", u3, "cites 1 fact(s)"), "retry: an open question citing one fact")
    check(lc["6"]["odd_one_out"]["odd_one_out:6"]["status"] == "no_answer"
          and not any(a["kind"] == "odd_one_out" for a in acts(out, "6")),
          "never JSON: no answer, no activity")
    check(lc["1"]["put_in_order"]["put_in_order:1"]["status"] == "empty"
          and not any(a["kind"] == "put_in_order" for a in acts(out, "1")), "put_in_order answered none: no activity")
    po3 = [a for a in acts(out, "3") if a["kind"] == "put_in_order"]
    check(len(po3) == 1 and po3[0]["scope"] == "lecture", "put_in_order citing two segments: lecture scope")

    # crossword
    cw = next(a for a in acts(out, "4") if a["kind"] == "crossword")
    ents = cw["data"]["entries"]
    names = {e["concept"]: cards_ok[e["concept"]]["name"] for e in ents}
    check(len(ents) >= 6 and not grid_problems(cw["data"]), f"crossword of lecture 4: {len(ents)} answers, no "
          f"clashing letter, every entry inside the grid and crossing another")
    check(all(e["answer"] == re.sub(r"[^A-Z]", "", names[e["concept"]].upper()) for e in ents)
          and all(not s5.words_in(e["clue"], s5.term_words([names[e["concept"]]])) for e in ents)
          and all(e["facts"] for e in ents), "crossword: answers are the names' letters, no clue writes a word of "
                                             "its answer, every entry has facts")
    cl = lc["4"]["crossword"]["crossword:4"]
    rt = next(e for e in ents if names[e["concept"]] == "ray tracing")
    check(cl["status"] == "unresolved" and "___" in rt["clue"] and len(cl["retry"]["problems"]) == 3
          and any("rasteriz" in m for m in cl["retry"]["problems"][0]),
          f"crossword: the clue with 'rasterized' retried, 'tracing' masked when unresolved ({rt['clue']})")
    print("    " + "\n    ".join(s5.render(cw, s5.Layer(kd))[:cw["data"]["height"]]), flush=True)

    # maps and pairs
    cm = next(a for a in acts(out, "4") if a["kind"] == "complete_map")
    d = cm["data"]
    lab = {n["id"]: n["label"] for n in d["nodes"]}
    ok = bool(d["blanks"])
    for b in d["blanks"]:
        e = d["edges"][b["edge"]]
        if b["hide"] == "label":
            right = {x["label"] for x in d["edges"] if {x["from"], x["to"]} == {e["from"], e["to"]}}
            ok &= b["answer"] == e["label"]
        else:
            other = "from" if b["hide"] == "to" else "to"
            right = {lab[x[b["hide"]]] for x in d["edges"] if x[other] == e[other] and x["label"] == e["label"]}
            ok &= b["answer"] == lab[e[b["hide"]]]
            ok &= sum(e[b["hide"]] in (x["from"], x["to"]) for x in d["edges"]) == 1
        ok &= b["answer"] in b["options"] and not (set(b["options"]) - {b["answer"]}) & right
    check(ok and all(e["facts"] for e in d["edges"]), f"complete_map: {len(d['blanks'])} blanks, each the hidden "
          f"value with no other right option, a hidden concept on no other edge; edges with facts")
    mp = next(a for a in acts(out, "4") if a["kind"] == "match_pairs")
    check(all(not s5.words_in(p["right"].replace("___", ""), s5.term_words([p["left"]])) and p["facts"]
              for p in mp["data"]["pairs"]) and len(mp["data"]["pairs"]) >= 3,
          "match_pairs: no definition writes its term, every pair has facts")

    # recall
    graph = json.loads((kd / "lecture_graph.json").read_text())
    ok = not any(a["kind"] == "recall" for a in acts(out, "1"))
    for k in fk.KEYS:
        for a in acts(out, k):
            if a["kind"] == "recall":
                for it in a["data"]["items"]:
                    ok &= it["concept"] in graph["concept_kinds"][k]["met_again"]
                    ok &= lec.order(it["from_lecture"]) < lec.order(k)
                    ok &= it["from_lecture"] == cards_ok[it["concept"]]["first_defined"]
    r8 = next(a for a in acts(out, "8") if a["kind"] == "recall")
    check(ok and r8["data"]["items"], f"recall: needed concepts from earlier lectures only (lecture 8: "
          f"{[cards_ok[i['concept']]['name'] for i in r8['data']['items']]})")
    return out


def test_rerun(work: Path, out: Path, log: Path):
    print("rerun", flush=True)
    strip = lambda b: json.dumps({**json.loads(b), "run": None}).encode()  # noqa: E731

    def snap():
        t = fk.tree_bytes(out)
        t["checks.json"] = strip(t["checks.json"])
        return t
    before, n0 = snap(), len(fk.lines(log))
    rc = fk.stage(work, "s5_activities.py", ["--llm", "configs/fake_qwen.json"], work / "5_rerun.log", record=False)
    after = snap()
    diff = [f for f in set(before) | set(after) if before.get(f) != after.get(f)]
    check(rc == 0 and len(fk.lines(log)) == n0 and not diff,
          f"rerun answered from the cache ({len(fk.lines(log)) - n0} new requests), the same files "
          f"({', '.join(diff[:4]) or 'none differ'})")
    rc = fk.stage(work, "s5_activities.py", ["--kinds", "concept_map,complete_map,match_pairs,recall,spaced_review",
                                             "--only", "2-5"], work / "5_kinds.log", record=False)
    after = snap()
    diff = [f for f in set(before) | set(after) if before.get(f) != after.get(f)]
    check(rc == 0 and not diff, f"--kinds (code-made) --only 2-5 without --llm: nothing changes "
                                f"({', '.join(diff[:4]) or 'none differ'})")
    rc = fk.stage(work, "s5_activities.py", ["--check"], work / "5_check.log", record=False)
    check(rc == 0, "--check passes on the output")


def test_seeded(work: Path, out: Path):
    print("seeded damage (the stage's own contract check)", flush=True)
    kd = work / "output" / COURSE / "knowledge"
    layer = s5.Layer(kd)

    def damaged(edit) -> list[str]:
        seeded = work / "seeded_activities"
        if seeded.exists():
            shutil.rmtree(seeded)
        shutil.copytree(out, seeded)
        p = seeded / "lec_4.json"
        d = json.loads(p.read_text())
        edit(d["activities"])
        p.write_text(json.dumps(d))
        return s5.validate(seeded, layer)

    def clash(a):
        cw = next(x for x in a if x["kind"] == "crossword")["data"]
        crossing = next(e for e in cw["entries"] if e["direction"] == "down")
        crossing["answer"] = "Q" * len(crossing["answer"])
    def shared_blank(a):
        d = next(x for x in a if x["kind"] == "complete_map")["data"]
        lab = {n["id"]: n["label"] for n in d["nodes"]}
        i = next(i for i, e in enumerate(d["edges"]) if sum(e["to"] in (x["from"], x["to"]) for x in d["edges"]) > 1)
        right = lab[d["edges"][i]["to"]]
        d["blanks"][0] = {"edge": i, "hide": "to", "answer": right,
                          "options": [right] + [n for n in lab.values() if n != right][:3]}
    for what, edit, word in [
            ("a clashing crossword letter", clash, "clashes"),
            ("an unknown fact", lambda a: a[0]["facts"].append("4/S9/F9"), "unknown fact 4/S9/F9"),
            ("a quiz answer index 4", lambda a: next(x for x in a if x["kind"] == "quiz")["data"]["questions"][0]
             .__setitem__("answer", 4), "not an index"),
            ("a missing field", lambda a: a[1].pop("title"), "fields"),
            ("a blank hiding a concept on two edges", shared_blank, "on another edge")]:
        P = damaged(edit)
        check(bool(P) and (word is None or any(word in m for m in P)), f"seeded: {what} caught ({P[:1]})")
    shutil.rmtree(work / "seeded_activities")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", help="folder for the copy (default: a new temporary folder)")
    ap.add_argument("--keep", action="store_true", help="keep the copy afterwards")
    a = ap.parse_args()
    work = Path(a.work) if a.work else Path(tempfile.mkdtemp(prefix="fake_activities_"))
    work.mkdir(parents=True, exist_ok=True)
    before = fk.snapshot(ROOT / "output")
    cfg = fk.make_copy(work)
    fk.synthesize(work)
    c = json.loads(cfg.read_text())
    check(c["port"] not in fk.FORBIDDEN and c["model_path"] == "fake/qwen" and c["attach_wait_s"] == 0,
          f"fake config: port {c['port']}, model_path fake/qwen, no wait")
    log = work / "fake_qwen.jsonl"
    server = ActivitiesFake(c["port"], c["model"], str(log))
    server.base_seed = c.get("seed", 0)
    server.lectures = {next(iter(json.loads((work / "output" / COURSE / "stage_1b_verify_segments/segment_maps"
                                             / f"{lec.stem_of(k)}.json").read_text()).values()))["subgoal"]: k
                       for k in fk.KEYS}
    server.start()
    try:
        print(f"copy in {work}; fake model on port {c['port']}; the knowledge layer", flush=True)
        ok = all(fk.stage(work, s, args, work / f"{s[:3]}.log") == 0 for s, args in [
            ("s4a_definitions.py", ["--llm", "configs/fake_qwen.json"]), ("s4b_goals.py", ["--llm", "configs/fake_qwen.json"]),
            ("s4c_lecture_graph.py", []), ("s4d_assemble.py", ["--embed-model", "fake"])])
        check(ok, "stages 4a to 4d build the synthetic knowledge/ and it passes its own check")
        out = test_s5(work, log)
        test_rerun(work, out, log)
        test_seeded(work, out)
    finally:
        server.stop()
    print("output", flush=True)
    check(fk.snapshot(ROOT / "output") == before, "nothing under the real output/ created or changed")
    if not a.keep and not FAILURES:
        shutil.rmtree(work)
    print(f"\n{'PASS' if not FAILURES else 'FAIL'}: {len(FAILURES)} failed"
          + (f"; copy kept in {work}" if FAILURES or a.keep else ""))
    sys.exit(1 if FAILURES else 0)


if __name__ == "__main__":
    main()
