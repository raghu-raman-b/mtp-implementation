"""Code-only failure inventory of the pipeline's outputs for one course (default nptel_vr).

    python3 analysis/failures/inventory.py [course]        writes analysis/failures/inventory.json and inventory.md

Rule (the user's): failures are found by CODE ONLY. Nothing here calls a language model or an agent. The signals are
(a) deterministic rules written below, (b) the pipeline's own judge verdicts and check files (checks.json and the
2a/2c/4a/4b/4d check files), (c) similarity scores the pipeline already stored (stage_3_registry/clusters.json).
Read-only: nothing under pipeline/output/ is written. Standard library only (no numpy needed).

One row per failure kind: stage, what fails, how it is detected, count and denominator, example IDs with excerpts,
how it is handled (one of HANDLING below), and how precise the rule is (PRECISION, written after reading a sample
of the matches against the raw files).
"""
import ast
import collections
import glob
import json
import re
import sys
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COURSE = sys.argv[1] if len(sys.argv) > 1 else "nptel_vr"
OUT = ROOT / "pipeline" / "output" / COURSE
K = OUT / "knowledge"
HERE = Path(__file__).resolve().parent

HANDLING = ("fixed in the pipeline", "fixed in the viewer", "display rule", "hidden from learners", "not fixed (future work)")
EMBED_THRESHOLDS = (0.80, 0.85, 0.90, 0.95)
EMBED_MAIN = 0.90
GENERIC_MODIFIERS = {"user", "users", "general", "basic", "main", "common", "typical", "different", "various",
                     "overall", "simple", "standard", "normal", "specific", "certain", "particular", "key", "new",
                     "current", "other", "several", "important", "primary", "major"}
GENERIC_ALIAS_WORDS = {"system", "systems", "model", "models", "data", "user", "users", "thing", "things", "object",
                       "objects", "device", "devices", "method", "methods", "process", "type", "types", "tool",
                       "tools", "information", "application", "applications", "technology", "technologies",
                       "approach", "concept", "element", "part", "parts", "value", "values", "factor", "factors",
                       "item", "case", "example", "time", "way", "set", "model", "technique", "techniques",
                       "component", "components", "feature", "features", "property", "properties", "task", "tasks"}
STOP_INITIALS = {"of", "the", "and", "for", "in", "on", "a", "an", "to", "with", "by", "or"}
COMMON_WORDS = {"is", "as", "at", "it", "or", "an", "in", "on", "to", "be", "of", "us", "up", "we", "he", "so", "do",
                "go", "no", "my", "me", "if", "by", "am", "id", "ok", "pc"}
DEFINITION_WORDS = re.compile(r"^.{0,90}?\b(is|are|refers? to|means|denotes|stands for|describes|was|were)\b", re.I)


def jload(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def norm(s: str) -> str:
    """The pipeline's name key (knowledge/index.json name_key): lower case; hyphens and underscores become spaces;
    runs of spaces become one; surrounding spaces and punctuation removed."""
    s = re.sub(r"[-_]", " ", s.lower())
    s = re.sub(r"\s+", " ", s)
    return s.strip(" \t\n.,;:!?\"'()[]{}")


def sing(t: str) -> str:
    return t[:-1] if len(t) > 3 and t.endswith("s") and not t.endswith("ss") else t


def skey(s: str) -> str:
    """norm() plus a naive plural strip per word, used only to match forms."""
    return " ".join(sing(t) for t in norm(s).split())


def ex(i, text, n=110):
    text = re.sub(r"\s+", " ", str(text)).strip()
    return {"id": i, "excerpt": text if len(text) <= n else text[: n - 1] + "…"}


def lec_key(p):
    return int(Path(p).stem.split("_")[1])


rows: list[dict] = []


def row(rid, stage, what, how, count, denom, unit, examples, handling, note="", extra=None):
    assert handling in HANDLING, handling
    r = {"id": rid, "stage": stage, "what_fails": what, "detected_by": how, "count": count, "denominator": denom,
         "unit": unit, "examples": examples[:5], "handling": handling, "handling_note": note,
         "precision": PRECISION.get(rid, "not sampled")}
    if extra:
        r["extra"] = extra
    rows.append(r)


# Filled in after reading samples of each rule's matches against the raw files (see the notes in inventory.md).
PRECISION: dict = {}
exec((HERE / "precision.py").read_text(encoding="utf-8")) if (HERE / "precision.py").exists() else None

# --------------------------------------------------------------------------------------------- load
concepts = jload(K / "concepts.json")
names = jload(K / "names.json")
facts = jload(K / "facts.json")
relations = jload(K / "relations.json")
lectures = {p.stem.split("_")[1]: jload(p) for p in (K / "lectures").glob("lec_*.json")}
act_checks = jload(OUT / "activities" / "checks.json")
acts = {str(lec_key(p)): jload(p)["activities"] for p in glob.glob(str(OUT / "activities" / "lec_*.json"))}
act_total = sum(len(v) for v in acts.values())
defined_ids = {c for c, v in concepts.items() if v.get("defined")}
connecting_ids = set(concepts) - defined_ids

serve_src = ast.parse((ROOT / "pipeline" / "viewer" / "serve.py").read_text(encoding="utf-8"))
HIDE, ITEM_LIST = {}, {}
for node in serve_src.body:
    if isinstance(node, ast.Assign) and len(node.targets) == 1:
        tgt = node.targets[0]
    elif isinstance(node, ast.AnnAssign):
        tgt = node.target
    else:
        continue
    if isinstance(tgt, ast.Name) and tgt.id == "HIDE_JUDGE_FAILED":
        HIDE = ast.literal_eval(node.value)
    elif isinstance(tgt, ast.Name) and tgt.id == "ITEM_LIST":
        ITEM_LIST = ast.literal_eval(node.value)
assert HIDE and ITEM_LIST, "could not read HIDE_JUDGE_FAILED / ITEM_LIST from serve.py"


# --------------------------------------------------------------------------------------------- activities: judge
def kept_round(j):
    rounds = j.get("rounds") or []
    if not rounds:
        return {}
    return rounds[-1] if j.get("kept") == "rewrite" else rounds[0]


# item records: kind -> list of dict(act, idx (1-based item number inside the activity, 0 = recap text), crit, reason,
#               text); plus denominators per kind (items judged in the kept version) and first-judgement counts.
J_failed = collections.defaultdict(list)
J_judged = collections.Counter()
J_first_failed = collections.Counter()
J_units = collections.Counter()
J_units_failed = collections.Counter()
J_crit = collections.defaultdict(collections.Counter)
unit_status = collections.defaultdict(collections.Counter)
unit_reasons = collections.defaultdict(list)
retry_units = collections.defaultdict(list)
rewrite_stats = collections.Counter()
act_by_id = {a["id"]: a for L in acts.values() for a in L}


def item_text(a, n):
    d = a["data"]
    k = a["kind"]
    if k == "quiz":
        q = d["questions"][n - 1]
        return q["question"] + " | correct: " + q["options"][q["answer"]]
    if k == "recap":
        return d["text"] if n == 0 else d["points"][n - 1]
    if k == "crossword":
        e = d["entries"][n - 1]
        return f'{e["answer"]}: {e["clue"]}'
    if k == "odd_one_out":
        it = d["items"][n - 1]
        return " | ".join(it["options"]) + f' (odd: {it["options"][it["odd"]]})'
    if k == "put_in_order":
        return d["items"][n - 1]["title"]
    if k == "open_question":
        return d["questions"][n - 1]["question"]
    return ""


for lec, kinds in act_checks["lectures"].items():
    for kind, units in kinds.items():
        for uid, r in units.items():
            unit_status[kind][r.get("status")] += 1
            if r.get("status") != "ok":
                unit_reasons[kind].append((lec, uid, r.get("status"), r.get("reason", "")))
            if "retry" in r:
                retry_units[kind].append((r.get("activity") or uid, r["retry"]))
            j = r.get("judge")
            if not j:
                continue
            J_units[kind] += 1
            rnd = kept_round(j)
            verdicts = [v for v in rnd.get("verdicts", []) if isinstance(v, dict)]
            J_judged[kind] += len(verdicts)
            first = (j.get("rounds") or [{}])[0]
            J_first_failed[kind] += len(first.get("failed_items", []))
            if j.get("kept") == "rewrite" or len(j.get("rounds", [])) > 1:
                rewrite_stats["rewritten_units"] += 1
                rewrite_stats["rewrite_kept"] += j.get("kept") == "rewrite"
            nums = [n for n in j.get("failed_items", []) if isinstance(n, int)]
            aid = r.get("activity")
            if not nums or not aid or aid not in act_by_id:
                continue
            J_units_failed[kind] += 1
            why = {v.get("item"): v for v in verdicts}
            last = act_by_id[aid]
            group = [last]
            if kind == "put_in_order":   # one unit can make several activities; the numbers run on across them
                L = acts[lec]
                i = L.index(last)
                while i > 0 and L[i - 1]["kind"] == "put_in_order" and L[i - 1]["segment"] == last["segment"]:
                    i -= 1
                    group.insert(0, L[i])
            off = 0
            for a in group:
                n_items = len(a["data"].get(ITEM_LIST.get(kind, ""), []))
                for n in nums:
                    local = n - off if len(group) > 1 else n
                    if (len(group) > 1 and not (off < n <= off + n_items)) or (kind == "recap" and n == 0 and a is not last):
                        continue
                    v = why.get(n, {})
                    crit = [str(c) for c in v.get("failed") or []]
                    for c in crit:
                        J_crit[kind][c] += 1
                    try:
                        text = item_text(a, local)
                    except (IndexError, KeyError):
                        text = ""
                    J_failed[kind].append({"act": a["id"], "item": local, "crit": crit, "reason": v.get("reason", ""),
                                           "text": text, "lecture": lec})
                off += n_items


def crit_note(kind, n=4):
    return ", ".join(f"{c} {k}" for c, k in J_crit[kind].most_common(n))


def jex(kind, k=5, key=None):
    items = J_failed[kind]
    items = sorted(items, key=key or (lambda x: (-len(x["crit"]), int(x["lecture"]), x["act"], x["item"])))
    return [ex(f'{x["act"]} item {x["item"]} [{",".join(x["crit"])}]', x["text"], 130) for x in items[:k]]


def hidden_items(kind):
    """Failed items the viewer hides from learners by HIDE_JUDGE_FAILED (serve.py); recap by the 2026-11-18 rule."""
    rule = HIDE.get(kind, False)
    out = []
    for x in J_failed[kind]:
        if kind == "recap":
            if x["item"] > 0:
                out.append(x)          # 2026-11-18 decision: only passing points are shown
        elif rule is True or (rule and set(x["crit"]) & rule):
            out.append(x)
    return out


# -- quiz
nq = J_judged["quiz"]
hq = hidden_items("quiz")
row("act.quiz.judge_failed", "5 activities", "quiz questions the activities judge fails (first judgement, then one rewrite, "
    "the better version kept)", "checks.json units[quiz].judge.failed_items of the kept round (code reads the pipeline's "
    "own verdicts); criteria from the verdicts' `failed` lists", len(J_failed["quiz"]), nq, "questions",
    jex("quiz"), "hidden from learners",
    f"viewer rule HIDE_JUDGE_FAILED[quiz] = {sorted(HIDE.get('quiz'))}: {len(hq)} of the {len(J_failed['quiz'])} failed "
    f"questions are hidden; the other {len(J_failed['quiz']) - len(hq)} (no_giveaway / worth_asking only) are shown. "
    f"First judgement failed {J_first_failed['quiz']}; judge-and-rewrite repaired "
    f"{J_first_failed['quiz'] - len(J_failed['quiz'])}. Criteria on the remaining: {crit_note('quiz')}",
    extra={"criteria": dict(J_crit["quiz"]), "first_judgement_failed": J_first_failed["quiz"],
           "hidden_by_viewer_rule": len(hq)})

# -- recap
texts = [x for x in J_failed["recap"] if x["item"] == 0]
points = [x for x in J_failed["recap"] if x["item"] > 0]
rec_total_points = sum(len(a["data"]["points"]) for L in acts.values() for a in L if a["kind"] == "recap")
rec_total_texts = sum(a["kind"] == "recap" for L in acts.values() for a in L)
row("act.recap.points_failed", "5 activities", "recap points the judge fails (supported/faithful/stands_alone/...)",
    "checks.json units[recap].judge.failed_items, item >= 1 (point number); criteria from the kept round",
    len(points), rec_total_points, "points", [dict(ex(f'{x["act"]} point {x["item"]} [{",".join(x["crit"])}]', x["text"], 130)) for x in sorted(points, key=lambda x: (int(x["lecture"]), x["act"], x["item"]))[:5]],
    "display rule", "2026-11-18 decision: recaps show only judge-passing points. Display-side only (no regeneration). "
    f"Criteria: {crit_note('recap', 5)}", extra={"criteria": dict(J_crit["recap"])})
row("act.recap.text_failed", "5 activities", "recap summary texts the judge fails", "checks.json units[recap].judge.failed_items "
    "contains item 0 (the text)", len(texts), rec_total_texts, "recap texts",
    [ex(f'{x["act"]} text [{",".join(x["crit"])}]', x["text"], 130) for x in sorted(texts, key=lambda x: (int(x["lecture"]), x["act"]))[:5]],
    "display rule", "2026-11-18 decision: the summary text is hidden when it failed (shown only if it passed).")
recap_all_fail = []
for L in acts.values():
    for a in L:
        if a["kind"] == "recap":
            failed_pts = {x["item"] for x in J_failed["recap"] if x["act"] == a["id"] and x["item"] > 0}
            if len(failed_pts) >= len(a["data"]["points"]):
                recap_all_fail.append(a)
row("act.recap.no_passing_point", "5 activities", "whole recaps with no judge-passing point (nothing left to show)",
    "every point number 1..n is in the unit's judge failed_items", len(recap_all_fail), rec_total_texts, "recaps",
    [ex(a["id"], a["data"]["points"][0]) for a in recap_all_fail[:5]], "display rule",
    "2026-11-18 decision: such recaps are dropped; that break shows only the quiz.")

# -- crossword
cw_failed = J_failed["crossword"]
cw_total = sum(len(a["data"]["entries"]) for L in acts.values() for a in L if a["kind"] == "crossword")
row("act.crossword.clue_failed", "5 activities", "crossword clues the judge fails (readable, from_text, unique, ...)",
    "checks.json units[crossword].judge.failed_items (entry number = position in the grid's entry list)",
    len(cw_failed), J_judged["crossword"], "clues", jex("crossword"), "display rule",
    "2026-11-18 decision: the grid is kept, the failed words are shown pre-filled and their clues are never shown. "
    f"Criteria: {crit_note('crossword', 5)}", extra={"criteria": dict(J_crit["crossword"])})

# -- odd one out, put in order, open question
for kind, rid, label in (("odd_one_out", "act.odd_one_out.judge_failed", "odd-one-out puzzles"),
                         ("put_in_order", "act.put_in_order.judge_failed", "put-in-order items"),
                         ("open_question", "act.open_question.judge_failed", "open questions")):
    hk = hidden_items(kind)
    row(rid, "5 activities", f"{label} the judge fails", f"checks.json units[{kind}].judge.failed_items of the kept round",
        len(J_failed[kind]), J_judged[kind], "items", jex(kind), "hidden from learners",
        f"viewer rule HIDE_JUDGE_FAILED[{kind}] = {HIDE.get(kind)}: {len(hk)} of {len(J_failed[kind])} hidden. "
        f"First judgement failed {J_first_failed[kind]}. Criteria: {crit_note(kind, 5)}",
        extra={"criteria": dict(J_crit[kind]), "first_judgement_failed": J_first_failed[kind]})

# -- whole activities hidden
whole = collections.defaultdict(list)
kind_total = collections.Counter(a["kind"] for L in acts.values() for a in L)
for L in acts.values():
    for a in L:
        k = a["kind"]
        if k not in ITEM_LIST or k in ("crossword", "recall", "match_pairs"):
            continue
        n = len(a["data"].get(ITEM_LIST[k], []))
        fl = [x for x in hidden_items(k) if x["act"] == a["id"]]
        if k == "recap":
            if a in recap_all_fail:
                whole[k].append(a["id"])
        elif n and len(fl) >= n:
            whole[k].append(a["id"])
wtot = sum(len(v) for v in whole.values())
wden = sum(kind_total[k] for k in ("quiz", "recap", "put_in_order", "odd_one_out", "open_question"))
row("act.whole_hidden", "5 activities", "whole activities with every item hidden from learners (judge-failed under the "
    "per-kind rule; recaps with no passing point)", "per activity: hidden items (HIDE_JUDGE_FAILED parsed by ast from "
    "pipeline/viewer/serve.py; recap rule of 2026-11-18) cover all its items", wtot, wden, "activities",
    [ex(f"{k} {i}", "all items hidden") for k, v in whole.items() for i in v[:2]], "hidden from learners",
    "per kind: " + ", ".join(f"{k} {len(whole[k])}/{kind_total[k]}" for k in
                             ("quiz", "recap", "put_in_order", "odd_one_out", "open_question")),
    extra={"by_kind": {k: whole[k] for k in whole}})

# -- empty / skipped units
es = []
for kind, lst in unit_reasons.items():
    for lec, uid, st, reason in lst:
        es.append((kind, lec, uid, st, reason))
row("act.units_empty_skipped", "5 activities", "units that made no activity (status empty or skipped)",
    "checks.json units[*].status != ok", len(es), sum(sum(c.values()) for c in unit_status.values()), "units",
    [ex(f"{k} lecture {l}", f"{s}: {r or 'no reason recorded: the model answer made no activity (nothing to order / no group found)'}") for k, l, u, s, r in es[:5]],
    "not fixed (future work)", "By contract a kind may be missing; kinds: " +
    ", ".join(f"{k} {dict(c)}" for k, c in unit_status.items() if set(c) - {"ok"}) +
    ". Lecture 1 has no recall (no earlier concept) and lecture 63 has no crossword (5 facts): expected.")

# -- retried / unresolved
retried = sum(len(v) for v in retry_units.values())
unres = sum(c.get("unresolved", 0) for c in unit_status.values())
probs = collections.Counter()
for kind, lst in retry_units.items():
    for aid, rt in lst:
        for plist in rt.get("problems", [])[-1:]:
            for p in plist:
                key = ("correct option longest" if "longest" in p else "answer in clue" if "clue" in p.lower() and "answer" in p.lower()
                       else p[:50])
                probs[key] += 1
row("act.retried", "5 activities", "units whose first model output broke a code check and was regenerated (the client's retry loop)",
    "checks.json units[*].retry (attempts, problems)", retried, sum(sum(c.values()) for c in unit_status.values()), "units",
    [ex(aid, "; ".join(rt["problems"][-1])[:140] if rt.get("problems") else f'{rt["attempts"]} attempts') for k in retry_units for aid, rt in retry_units[k][:1]][:5],
    "fixed in the pipeline", "code checks + retry (s5_activities). Units with status unresolved after retries: "
    f"{unres}. Retries by kind: " + ", ".join(f"{k} {len(v)}" for k, v in retry_units.items()) +
    f". Last-attempt problems seen: {dict(probs.most_common(4))}", extra={"unresolved": unres})
tj = act_checks["totals"]["judge"]
row("act.judge_unresolved", "5 activities", "items still judge-failed after the judge's one rewrite round",
    "totals.judge: failed_items (first judgement) vs still_failed_items; per unit judge.kept", tj["still_failed_items"],
    tj["items"], "items", [ex("totals.judge", f'first judgement failed {tj["failed_items"]} of {tj["items"]}; rewrote '
                                          f'{tj["rewritten"]} units, kept {tj["rewrite_kept"]} rewrites; '
                                          f'{tj["still_failed_items"]} still fail')],
    "fixed in the pipeline", "activities judge v3 + rewrite repaired "
    f"{tj['failed_items'] - tj['still_failed_items']} of {tj['failed_items']} first-judgement failures; the rest are "
    "hidden or pre-filled by the display rules in the rows above (nothing is dropped from the data).")

# -- quiz correct is the longest
qs = [(a["id"], i, q) for L in acts.values() for a in L if a["kind"] == "quiz" for i, q in enumerate(a["data"]["questions"])]
uniq, tied, ratio15 = [], 0, 0
for aid, i, q in qs:
    ln = [len(o) for o in q["options"]]
    c = ln[q["answer"]]
    others = [l for j, l in enumerate(ln) if j != q["answer"]]
    if c > max(others):
        uniq.append((aid, i, q))
        if c >= 1.5 * max(others):
            ratio15 += 1
    elif c == max(others):
        tied += 1
row("act.quiz.correct_longest", "5 activities", "quiz questions whose correct option is the longest of the four (test-wise bias)",
    "len(options[answer]) > max(len(other options)) (characters); tied-longest and >=1.5x variants in extra",
    len(uniq), len(qs), "questions",
    [ex(f"{a} Q{i + 1}", f'{len(q["options"][q["answer"]])} vs {max(len(o) for j, o in enumerate(q["options"]) if j != q["answer"])} chars: {q["options"][q["answer"]]}', 130)
     for a, i, q in sorted(uniq, key=lambda t: -(len(t[2]["options"][t[2]["answer"]]) / max(len(o) for j, o in enumerate(t[2]["options"]) if j != t[2]["answer"])))[:5]],
    "fixed in the pipeline", f"Was 52% (751/1,443) in the 2026-11-13 MVP (analysis/mvp/test_report.md); the retry check "
    f"'correct option is the longest' brought it to {100 * len(uniq) / len(qs):.0f}% (chance for a unique longest is 25%, "
    f"including ties {100 * (len(uniq) + tied) / len(qs):.0f}%). Longest-or-tied: {len(uniq) + tied}; at least 1.5x the next: {ratio15}.",
    extra={"unique_longest": len(uniq), "tied_longest": tied, "ratio_1_5x": ratio15,
           "unique_longest_or_tied": len(uniq) + tied})

# -- crossword: clue contains answer or part of it
def words(s):
    return re.findall(r"[a-z]+", s.lower())


CLUE_STOP = {"with", "from", "that", "this", "into", "over", "using", "used", "than", "then", "when", "which", "their", "they"}


cw_entries = [(a, e) for L in acts.values() for a in L if a["kind"] == "crossword" for e in a["data"]["entries"]]
full, part, dup_pairs, masked = [], [], [], []
for a, e in cw_entries:
    clue = re.sub(r"\(\d[\d,\- ]*\)\s*$", "", e["clue"])        # drop the length hint "(5,3)"
    cw = words(clue)
    ans = e["answer"].lower()
    whole_hit = any("".join(cw[i:j]) == ans for i in range(len(cw)) for j in range(i + 1, min(len(cw), i + 7) + 1))
    c = concepts.get(e["concept"], {})
    forms = [c.get("name", "")] + c.get("aliases", [])
    toks = {t for f in forms for t in words(f) if len(t) >= 4 and t not in CLUE_STOP}
    if whole_hit:
        full.append((a, e))
    else:
        hit = [w for w in cw if len(w) >= 4 and any(w == t or (len(t) >= 6 and len(w) >= 6 and w[:6] == t[:6]) for t in toks)]
        if hit:
            part.append((a, e, hit))
    if "___" in e["clue"]:
        masked.append((a, e))
row("act.crossword.clue_has_answer", "5 activities", "crossword entries whose clue contains the whole answer",
    "the answer's letters equal one word, or up to 7 consecutive words joined, of the clue (length hint removed; whole words only)", len(full), len(cw_entries), "entries",
    [ex(f'{a["id"]} {e["answer"]}', e["clue"], 130) for a, e in full[:5]], "fixed in the pipeline",
    "s5 blanks answer words in clues with `___` and retries (clue_masked); this rule re-checks the final text.")
row("act.crossword.clue_has_part", "5 activities", "crossword entries whose clue contains a word of the answer's concept name/aliases "
    "(a part of the answer)", "a clue word of >= 4 letters (not a function word) equals a >=4-letter word of the concept's name or alias "
    "(or shares its first 6 letters when both have >= 6)", len(part), len(cw_entries), "entries",
    [ex(f'{a["id"]} {e["answer"]} ({",".join(h)})', e["clue"], 130) for a, e, h in part[:5]], "not fixed (future work)",
    "Partly handled: s5 masks name words with `___` (over-masking: 'graphics' for SCENEGRAPH); what slips through is counted here.")
row("act.crossword.clue_masked", "5 activities", "clues containing a `___` mask (word of the answer blanked by code)",
    "'___' in clue", len(masked), len(cw_entries), "entries", [ex(f'{a["id"]} {e["answer"]}', e["clue"], 130) for a, e in masked[:5]],
    "fixed in the pipeline", "The 5 masked MVP crosswords (13/A19, 21/A11, 29/A11, 51/A21, 58/A20) were regenerated by the Qwen "
    "judge-v3 run; no clue is masked now." if not masked else "Masked clues remain.")
clue_groups = collections.defaultdict(list)
for a, e in cw_entries:
    clue_groups[(a["id"], re.sub(r"\(\d[\d,\- ]*\)\s*$", "", e["clue"]).strip().lower())].append(e["answer"])
dups = {k: v for k, v in clue_groups.items() if len(v) > 1}
row("act.crossword.clue_duplicate", "5 activities", "two answers of one grid with the same clue text",
    "identical clue text (length hint removed) twice in one crossword", sum(len(v) for v in dups.values()), len(cw_entries), "entries",
    [ex(f"{k[0]} {'/'.join(v)}", k[1]) for k, v in list(dups.items())[:5]], "not fixed (future work)")

# -- match pairs
mp = [(a, p) for L in acts.values() for a in L if a["kind"] == "match_pairs" for p in a["data"]["pairs"]]
trunc = [(a, p) for a, p in mp if p["right"].rstrip().endswith(("…", "..."))]
giveaway = [(a, p) for a, p in mp if " ".join(words(p["left"])) and f' {" ".join(words(p["left"]))} ' in f' {" ".join(words(p["right"]))} ']
partword = [(a, p) for a, p in mp if any(w in words(p["right"]) for w in words(p["left"]) if len(w) >= 5)]
lowerstart = [(a, p) for a, p in mp if p["right"][:1].islower() or p["right"].startswith(("…", "..."))]
twins = []
for L in acts.values():
    for a in L:
        if a["kind"] != "match_pairs":
            continue
        ps = a["data"]["pairs"]
        for p, q in combinations(ps, 2):
            s1, s2 = set(words(p["right"])), set(words(q["right"]))
            if s1 and s2 and len(s1 & s2) / len(s1 | s2) >= 0.7:
                twins.append((a, p, q))
row("act.match.truncated", "5 activities", "match-pair definitions cut off with '…' (read as unfinished)",
    "right side ends with '…' or '...'", len(trunc), len(mp), "pairs",
    [ex(f'{a["id"]} {p["left"]}', p["right"], 140) for a, p in trunc[:5]], "not fixed (future work)",
    "The right side is the 4a definition cut to a word cap by s5; no judge exists for match pairs (code-made kind).")
row("act.match.term_in_definition", "5 activities", "match pairs where the definition (right) contains the whole term (left): the answer is given away",
    "the term's words occur as a whole-word phrase in `right` (case-insensitive)", len(giveaway), len(mp), "pairs",
    [ex(f'{a["id"]} {p["left"]}', p["right"], 140) for a, p in giveaway[:5]], "not fixed (future work)",
    f"Masking artefact: the right side is the 4a definition, which usually opens with the term; s5 trims the opening but not later mentions. "
    f"A looser rule (any >=5-letter word of the term in the definition) matches {len(partword)} pairs and mostly flags legitimate overlap (view plane / plane).")
row("act.match.twin_rows", "5 activities", "pairs of definitions in one match set that are near-identical (token Jaccard >= 0.7)",
    "Jaccard of word sets of two right sides in one activity >= 0.7", len(twins), len(mp), "pair-pairs",
    [ex(f'{a["id"]} {p["left"]} / {q["left"]}', p["right"], 120) for a, p, q in twins[:5]], "not fixed (future work)",
    "Twin rows make a match ambiguous; no judge for this kind.")
row("act.match.bad_start", "5 activities", "match-pair definitions that start lower-case or with '…'",
    "right[0] is lower-case or right starts with '…'", len(lowerstart), len(mp), "pairs",
    [ex(f'{a["id"]} {p["left"]}', p["right"], 120) for a, p in lowerstart[:5]], "not fixed (future work)")

# -- maps
cmaps = [a for L in acts.values() for a in L if a["kind"] == "concept_map"]
big = [a for a in cmaps if len(a["data"]["nodes"]) > 60]
cm_nodes = sorted(len(a["data"]["nodes"]) for a in cmaps)
long_labels = [(a, e) for a in cmaps for e in a["data"]["edges"] if len(e["label"].split()) >= 9]
twice = []
for L in acts.values():
    for a in L:
        if a["kind"] == "complete_map":
            es_ = [b["edge"] for b in a["data"].get("blanks", [])]
            if len(es_) != len(set(es_)):
                twice.append(a)
row("act.map.too_big", "5 activities", "concept maps with more than 60 nodes (unreadable at 'Fit')",
    "len(nodes) > 60 in concept_map data", len(big), len(cmaps), "maps",
    [ex(a["id"], f'{len(a["data"]["nodes"])} nodes, {len(a["data"]["edges"])} edges') for a in sorted(big, key=lambda a: -len(a["data"]["nodes"]))[:5]],
    "display rule", f"median {cm_nodes[len(cm_nodes) // 2]} nodes, max {cm_nodes[-1]}. The viewer shows ~20 key concepts by default "
    "with 'all N, by part' as an option (2026-11-13, commit 0965ba9). Maps are code-made: no judge verdicts.")
row("act.map.long_edge_label", "5 activities", "map edges whose label has 9 or more words (a sentence fragment)",
    "len(label.split()) >= 9 on concept_map edges", len(long_labels), sum(len(a["data"]["edges"]) for a in cmaps), "edges",
    [ex(f'{a["id"]} {e["from"]}->{e["to"]}', e["label"]) for a, e in long_labels[:5]], "not fixed (future work)")
row("act.completemap.blank_twice", "5 activities", "complete-the-map activities that blank the same edge twice",
    "duplicate `edge` among blanks", len(twice), kind_total["complete_map"], "activities",
    [ex(a["id"], "same edge blanked twice") for a in twice[:5]], "not fixed (future work)")

# -- report-only code flags
flag_counts = collections.Counter()
flag_ex = {}
for lec, kinds in act_checks["lectures"].items():
    for kind, units in kinds.items():
        for uid, r in units.items():
            for fl, v in (r.get("flags") or {}).items():
                if fl == "judge_failed":
                    continue
                flag_counts[f"{kind}.{fl}"] += len(v) if isinstance(v, list) else 1
                flag_ex.setdefault(f"{kind}.{fl}", (r.get("activity") or uid, v))
row("act.code_flags", "5 activities", "report-only code flags on the kept items (not judge verdicts)",
    "checks.json units[*].flags other than judge_failed (counted per item or per unit)", sum(flag_counts.values()),
    act_total, "flags", [ex(f"{k} {flag_ex[k][0]}", f"{flag_ex[k][1]}") for k in list(flag_counts)[:5]],
    "not fixed (future work)", "By flag: " + ", ".join(f"{k} {v}" for k, v in flag_counts.most_common()))

# --------------------------------------------------------------------------------------------- concepts
seg2concept = {}
for cid, c in concepts.items():
    for m in c.get("merged", []):
        seg2concept[m["segment_concept"]] = cid
forms = {}   # concept -> list of (kind, text)
for cid, c in concepts.items():
    f = [("name", c["name"])] + [("alias", a) for a in c.get("aliases", [])] + [("acronym", a) for a in c.get("acronyms", [])]
    forms[cid] = f


def cname(c):
    return f'{c} "{concepts[c]["name"]}"' + ("" if concepts[c].get("defined") else " (connecting)")


# C1: shared key
shared = {k: v for k, v in names.items() if len({x["concept"] for x in v}) > 1}
combo = collections.Counter(tuple(sorted(x["as"] for x in v)) for v in shared.values())
name_eq_other = {k: v for k, v in shared.items() if any(x["as"] == "name" for x in v)}
shared_pairs = set()
for k, v in shared.items():
    for a, b in combinations(sorted({x["concept"] for x in v}), 2):
        shared_pairs.add((a, b))
row("con.shared_key", "3 registry / 2c", "a name, alias or acronym text that identifies two or more concepts",
    "knowledge/names.json: a normalised key mapped to >= 2 different concept IDs", len(shared), len(names), "name keys",
    [ex(f"{k!r}", "; ".join(f'{x["concept"]} {x["as"]} of "{concepts[x["concept"]]["name"]}"' for x in v), 150) for k, v in
     sorted(shared.items(), key=lambda kv: (-len({x["concept"] for x in kv[1]}), kv[0]))[:5]], "not fixed (future work)",
    f"{len(shared_pairs)} concept pairs. By role: " + ", ".join(f"{'+'.join(k)} {v}" for k, v in combo.most_common(5)) +
    ". Planned: O2 (alias rules; merge list) in the 2026-11-18 task list.",
    extra={"pairs": len(shared_pairs)})
nm = [(k, v) for k, v in sorted(name_eq_other.items())]
row("con.name_is_other_alias", "3 registry / 2c", "a concept's name equals another concept's alias or acronym",
    "names.json key has an entry as=name for one concept and as=alias/acronym for another", len(nm), len(concepts), "name keys",
    [ex(f"{k!r}", "; ".join(f'{x["concept"]} {x["as"]} "{concepts[x["concept"]]["name"]}"' for x in v), 150) for k, v in nm[:5]],
    "not fixed (future work)", "Subset of con.shared_key.")

# C3: acronym expansion
def content_tokens(name):
    return [t for t in norm(name).split() if t not in STOP_INITIALS]


def initials_variants(name):
    """Initials of the content words, and of all words (FOV = field of view keeps the 'o')."""
    toks = norm(name).split()
    ct = content_tokens(name)
    out = set()
    if len(ct) >= 2:
        out.add("".join(t[0] for t in ct))
    if 2 <= len(toks) <= 6:
        out.add("".join(t[0] for t in toks))
    return out


acr = collections.defaultdict(set)      # STRONG: the registry itself lists the token as a form of the expansion's concept
acr_weak = collections.defaultdict(set)  # WEAK: the only name with those initials
init_names = collections.defaultdict(set)
for cid, c in concepts.items():
    if len(norm(c["name"]).split()) <= 6:
        own = {norm(x).replace(" ", "") for k_, x in forms[cid] if k_ != "name"}
        for ini in initials_variants(c["name"]):
            init_names[ini].add(norm(c["name"]))
            if ini in own:
                acr[ini].add(norm(c["name"]))
for ini, ns in init_names.items():
    if ini not in acr and len(ns) == 1:
        acr_weak[ini] |= ns
for d_ in (acr, acr_weak):
    d_["3d"].add("three dimensional")
    d_["2d"].add("two dimensional")
form_index = collections.defaultdict(set)
for cid in concepts:
    for kind, text in forms[cid]:
        form_index[skey(text)].add(cid)
def expand_pairs(table):
    out = {}
    for cid in concepts:
        for kind, text in forms[cid]:
            toks = norm(text).split()
            for i, t in enumerate(toks):
                if len(t) < 2 or t in COMMON_WORDS or t not in table:
                    continue
                for exp in table[t]:
                    new = " ".join(toks[:i] + exp.split() + toks[i + 1:])
                    for other in form_index.get(skey(new), ()):
                        if other != cid:
                            out.setdefault(tuple(sorted((cid, other))), f'"{text}" with {t.upper()} = "{exp}" matches "{new}" of {other}')
    return out


acr_pairs = expand_pairs(acr)
weak_pairs = {k: v for k, v in expand_pairs(acr_weak).items() if k not in acr_pairs}
acr_list = sorted(acr_pairs.items())
TWINS = [("VR headset", "virtual reality headset"), ("AR Toolkit", "augmented reality toolkit"), ("extended reality engine", "xr engine"),
         ("three-dimensional model", "3D model"), ("iPhone operating system", "ios"), ("Majuli virtual reality tour", "Majuli VR Tour")]
twin_state = []
for x, y in TWINS:
    cx, cy = form_index.get(skey(x), set()), form_index.get(skey(y), set())
    twin_state.append((x, y, bool(cx & cy), sorted(cx), sorted(cy)))
twins_merged = [t for t in twin_state if t[2]]
twins_open = [t for t in twin_state if not t[2]]
HEADSET = set()
for f_ in ("headset", "head-mounted display", "virtual reality headset", "VR headset"):
    HEADSET |= form_index.get(skey(f_), set())
headset_maps = [a["id"] for L in acts.values() for a in L if a["kind"] == "concept_map"
                if len({n["id"] for n in a["data"]["nodes"]} & HEADSET) >= 2]
row("con.acronym_expansion", "3 registry", "two concepts that are the same term with an acronym expanded in one (HMD / head-mounted display, "
    "VR headset / virtual reality headset, iOS / iPhone operating system, 3D / three-dimensional)",
    "for each form F of concept A, replace a token that equals the initials of another multi-word name "
    "(content words, hyphens split; plus 2d/3d) by that name; if the result equals a form of concept B != A (plural-stripped) -> pair",
    len(acr_list), len(concepts), "concept pairs",
    [ex(f"{cname(a)} / {cname(b)}", why, 170) for (a, b), why in acr_list[:5]], "fixed in the pipeline" if False else "not fixed (future work)",
    "3b synonym merge (rebuilt 2026-11-17: 262 model merges) removed many; the rest is counted here. Planned: O2 merge list. "
    f"The MVP's six acronym/expansion twins (analysis/mvp/test_report.md): {len(twins_merged)} now resolve to one concept, "
    f"open: {', '.join(f'{x} / {y}' for x, y, _, _, _ in twins_open) or 'none'}. The headset family {sorted(HEADSET)} still appears together on "
    f"{len(headset_maps)} lecture concept maps (11 in the MVP). "
    f"Strong rule only (the registry lists the acronym on the expanded concept); {len(weak_pairs)} more pairs match through unambiguous initials "
    "alone (e.g. dx / delta x, but also false ones such as IoT / inside-out tracking) and are listed in extra.weak_pairs, not counted.",
    extra={"twins": [list(t[:3]) for t in twin_state], "headset_family_maps": headset_maps,
           "pairs": [list(k) for k, _ in acr_list], "weak_pairs": [[a_, b_, w] for (a_, b_), w in sorted(weak_pairs.items())]})

# C4: generic modifier + same head
gen_pairs = {}
name_index = collections.defaultdict(set)
for cid, c in concepts.items():
    name_index[skey(c["name"])].add(cid)
for cid, c in concepts.items():
    toks = norm(c["name"]).split()
    for k in range(1, len(toks)):
        if all(t in GENERIC_MODIFIERS for t in toks[:k]):
            rest = skey(" ".join(toks[k:]))
            for other in name_index.get(rest, ()):
                if other != cid:
                    gen_pairs[tuple(sorted((cid, other)))] = f'"{c["name"]}" = generic modifier + "{concepts[other]["name"]}"'
gen_list = sorted(gen_pairs.items())
row("con.generic_modifier", "3 registry", "a concept whose name is another concept's name plus a generic modifier "
    "(interaction / user interaction)", f"name = leading words all in a small stoplist {sorted(GENERIC_MODIFIERS)} + another "
    "concept's full name (plural-stripped)", len(gen_list), len(concepts), "concept pairs",
    [ex(f"{cname(a)} / {cname(b)}", why, 170) for (a, b), why in gen_list[:5]], "not fixed (future work)",
    "Planned: O2 reviewed merge list.", extra={"pairs": [list(k) for k, _ in gen_list]})

# C5: embedding similarity of stored vectors
clusters = jload(OUT / "stage_3_registry" / "clusters.json")
ent2concept = {}
for eid, e in clusters["entries"].items():
    ms = [seg2concept.get(m) for m in e["members"]]
    ms = [m for m in ms if m]
    if ms:
        ent2concept[eid] = collections.Counter(ms).most_common(1)[0][0]
cut_pairs = {(p["a"], p["b"]) for p in clusters["cut"]}
emb = {}
for p in clusters["candidates"]:
    a, b = ent2concept.get(p["a"]), ent2concept.get(p["b"])
    if not a or not b or a == b:
        continue
    key = tuple(sorted((a, b)))
    cut = (p["a"], p["b"]) in cut_pairs
    prev = emb.get(key)
    if prev is None or p["sim"] > prev[0]:
        emb[key] = (p["sim"], cut or (prev[1] if prev else False), clusters["entries"][p["a"]]["name"], clusters["entries"][p["b"]]["name"])
emb_counts = {t: sum(1 for v in emb.values() if v[0] >= t) for t in EMBED_THRESHOLDS}


def share_token(x, y):
    tx = {t for t in norm(x).split() if len(t) >= 3 and t not in STOP_INITIALS}
    ty = {t for t in norm(y).split() if len(t) >= 3 and t not in STOP_INITIALS}
    return bool(tx & ty)


emb_tok = {k: v for k, v in emb.items() if share_token(concepts[k[0]]["name"], concepts[k[1]]["name"])}
emb_tok_counts = {t: sum(1 for v in emb_tok.values() if v[0] >= t) for t in EMBED_THRESHOLDS}
emb_main = sorted(((k, v) for k, v in emb_tok.items() if v[0] >= EMBED_MAIN), key=lambda kv: -kv[1][0])
never_asked = sum(1 for k, v in emb_main if v[1])
row("con.embedding_similar", "3 registry", f"two distinct concepts whose stored entry vectors have cosine >= {EMBED_MAIN} and whose names share a word "
    "(likely duplicates or near-synonyms)", "stage_3_registry/clusters.json `candidates` (cosine of the 3a entry embeddings "
    "'name; also called: ...; first facts', Qwen3-Embedding-0.6B, stored; no model call), entries mapped to final concepts "
    f"through concepts.json merged[]; pairs with different final concepts; threshold {EMBED_MAIN} (3a's own is 0.70) "
    "and at least one shared name word of >= 3 letters (without it siblings such as ARKit / ARCore fill the list)",
    len(emb_main), len(emb), "concept pairs (cross-concept pairs with cosine >= 0.70)",
    [ex(f"{cname(a)} / {cname(b)}", f"cos {v[0]:.3f}" + (" (cut by the 3b cap: the model never saw it)" if v[1] else ""), 150) for (a, b), v in emb_main[:5]],
    "not fixed (future work)", f"Counts by threshold, all pairs / sharing a word: " + ", ".join(f">= {t}: {emb_counts[t]} / {emb_tok_counts[t]}" for t in emb_counts) +
    f". Of the {len(emb_main)} at >= {EMBED_MAIN}, {never_asked} were cut by the 3b cap (12 per cluster) and never judged; "
    "the others were judged and kept apart by the 3b model. Vectors embed names plus facts, not names alone (no name-only vectors are stored).",
    extra={"counts_by_threshold_all": {str(t): n for t, n in emb_counts.items()},
           "counts_by_threshold_sharing_a_word": {str(t): n for t, n in emb_tok_counts.items()}, "cut_by_cap": never_asked,
           "pairs": [[a, b, v[0]] for (a, b), v in emb_main]})

# C6: odd aliases
short, generic, many, fragment = [], [], [], []
for cid, c in concepts.items():
    nt = content_tokens(c["name"])
    initials = "".join(t[0] for t in nt)
    acrs = {a.lower() for a in c.get("acronyms", [])}
    for a in c.get("aliases", []):
        al = norm(a)
        if len(al) <= 2 and al not in acrs and al != initials:
            short.append((cid, a))
        if al in GENERIC_ALIAS_WORDS:
            generic.append((cid, a))
        if len(al.split()) == 1 and len(nt) >= 2 and al in nt and al not in acrs and al != initials:
            fragment.append((cid, a))
many_keys = {k: v for k, v in names.items() if len({x["concept"] for x in v}) >= 3}
for k, v in many_keys.items():
    many.append((k, v))
alias_total = sum(len(c.get("aliases", [])) for c in concepts.values())
row("con.alias_short", "2c / 3 registry", "aliases of 1-2 characters that are not the concept's acronym or its initials",
    "len(norm(alias)) <= 2 and alias not in acronyms and alias != initials of the name", len(short), alias_total, "aliases",
    [ex(f"{cname(c)}", f"alias {a!r}") for c, a in short[:5]], "not fixed (future work)", "Planned: O2 alias rules (fragments) with a reviewed removal list.")
row("con.alias_generic", "2c / 3 registry", "aliases that are a single generic word from a small stoplist",
    f"norm(alias) in a {len(GENERIC_ALIAS_WORDS)}-word stoplist (system, model, data, user, device, method, ...)", len(generic), alias_total,
    "aliases", [ex(f"{cname(c)}", f"alias {a!r}") for c, a in generic[:5]], "not fixed (future work)",
    "Planned: O2 alias rules.")
row("con.alias_fragment", "2c / 3 registry", "single-word aliases that are only one word of a longer name (fragment aliases)",
    "alias is one token, equals a content token of a multi-word name, and is not an acronym/initials", len(fragment), alias_total,
    "aliases", [ex(f"{cname(c)}", f"alias {a!r}") for c, a in fragment[:5]], "not fixed (future work)", "Planned: O2 alias rules.")
row("con.alias_shared_by_many", "3 registry", "a name key shared by 3 or more concepts", "names.json key -> >= 3 concept IDs", len(many),
    len(names), "name keys", [ex(f"{k!r}", "; ".join(f'{x["concept"]} {x["as"]} "{concepts[x["concept"]]["name"]}"' for x in v), 170) for k, v in many[:5]],
    "not fixed (future work)", "Planned: O2 alias rules (shared alias kept only where defined).")

# C7: acronym pointing at a different concept than its initials
bad_acr = []
initials_idx = collections.defaultdict(set)
for cid, c in concepts.items():
    for ini in initials_variants(c["name"]):
        initials_idx[ini].add(cid)
for cid, c in concepts.items():
    own = initials_variants(c["name"])
    padded = " " + " ".join(norm(c["name"]).split()) + " "
    for a in c.get("acronyms", []):
        al = norm(a).replace(" ", "")
        if al in own:
            continue
        inside = [o for o in sorted(initials_idx.get(al, ())) if o != cid and f" {norm(concepts[o]['name'])} " in padded]
        if inside:
            bad_acr.append((cid, a, inside[:2]))
row("con.acronym_of_other_concept", "2c / 3 registry", "an acronym on a concept that is not the initials of its name but is the initials of "
    "another concept (FOV on horizontal field of view)", "acronym != initials of own name, but equals the initials of another "
    "concept's multi-word name that is written inside this concept's name", len(bad_acr), sum(len(c.get("acronyms", [])) for c in concepts.values()), "acronyms",
    [ex(f"{cname(c)}", f"acronym {a!r} = initials of " + ", ".join(concepts[o]["name"] for o in os_)) for c, a, os_ in bad_acr[:5]],
    "not fixed (future work)", "Planned: O2 (the FOV alias on horizontal field of view).")

# C8: connecting concepts
cmap_nodes = collections.Counter()
for a in cmaps:
    for n in a["data"]["nodes"]:
        cmap_nodes[n["id"]] += 1
conn_on_maps = [c for c in connecting_ids if c in cmap_nodes]
node_slots = sum(cmap_nodes.values())
conn_slots = sum(cmap_nodes[c] for c in conn_on_maps)
conn_used = collections.Counter()
for a in (a for L in acts.values() for a in L):
    if a["kind"] == "crossword":
        for e in a["data"]["entries"]:
            if e["concept"] in connecting_ids:
                conn_used["crossword"] += 1
    elif a["kind"] == "match_pairs":
        for p in a["data"]["pairs"]:
            if p["concept"] in connecting_ids:
                conn_used["match_pairs"] += 1
    elif a["kind"] == "recall":
        for it in a["data"]["items"]:
            if it["concept"] in connecting_ids:
                conn_used["recall"] += 1
cards = jload(OUT / "activities" / "course.json")["spaced_review"]["cards"]
conn_used["spaced_review"] = sum(c["concept"] in connecting_ids for c in cards)
row("con.connecting", "4a definitions", "connecting concepts (defined: false): no segment defines them, so their 'definition' is a "
    "model-written gloss", "concepts.json defined == false", len(connecting_ids), len(concepts), "concepts",
    [ex(cname(c), concepts[c]["definition"], 120) for c in sorted(connecting_ids)[:5]], "display rule",
    f"2026-11-18 decision: no concept card, not in the glossary, muted non-clickable node in the concept graph, never use their "
    f"definition; QA gets their facts only. On concept maps: {len(conn_on_maps)} connecting concepts appear, {conn_slots} of {node_slots} "
    f"map node slots ({100 * conn_slots / node_slots:.0f}%). Used in definition-based kinds (crossword, match pairs, recall, spaced-review "
    f"cards): {dict(conn_used) or 'none'}.",
    extra={"on_maps": len(conn_on_maps), "node_slots": node_slots, "connecting_node_slots": conn_slots, "used_in": dict(conn_used)})

# C9: 2c flags
s2c = jload(OUT / "stage_2c_concepts" / "checks" / "summary.json")
flag_examples = collections.defaultdict(list)
for f in sorted(glob.glob(str(OUT / "stage_2c_concepts" / "checks" / "lec_*.json")), key=lec_key):
    d = jload(f)
    lec = Path(f).stem.split("_")[1]
    rels = jload(OUT / "stage_2c_concepts" / "relations" / f"lec_{lec}.json")
    cmaps2 = jload(OUT / "stage_2c_concepts" / "concept_maps" / f"lec_{lec}.json")
    for seg, v in d.items():
        for flag, items in (v.get("flags") or {}).items():
            for it in items:
                if flag in ("reverse", "no_shared_fact"):
                    r = rels.get(f"{seg}/R{it}")
                    txt = (f'{cmaps2.get(r["subject"], {}).get("name")} --{r["label"]}--> {cmaps2.get(r["object"], {}).get("name")}' if r else str(it))
                elif flag == "no_triple":
                    txt = cmaps2.get(f"{seg}/C{it}", {}).get("name", str(it)) if isinstance(it, int) else str(it)
                else:
                    txt = str(it)
                flag_examples[flag].append((f"{seg} {flag}", txt))
den = {"reverse": s2c["relations"], "no_shared_fact": s2c["relations"], "no_triple": s2c["concepts"],
       "name_not_in_facts": s2c["concepts"], "acronym_in_name": s2c["concepts"], "alias_not_in_facts": s2c["concepts"],
       "fact_without_concept": len(facts)}
meaning = {"reverse": "relation written in the opposite direction to its sentence (code check)",
           "no_shared_fact": "relation whose two concepts share no fact",
           "no_triple": "concept in no relation of its segment",
           "name_not_in_facts": "concept name that does not occur in its facts' text",
           "acronym_in_name": "acronym written inside the concept name (VR headset)",
           "alias_not_in_facts": "alias that does not occur in the facts",
           "fact_without_concept": "fact with no concept"}
for flag, n in s2c["flags"].items():
    row(f"con.2c.{flag}", "2c concepts", meaning.get(flag, flag), f"stage_2c_concepts/checks/summary.json flags.{flag} "
        f"(per-segment checks/lec_N.json resolve the examples)", n, den.get(flag, s2c["concepts"]), "flags",
        [ex(*e) for e in flag_examples[flag][:5]], "not fixed (future work)",
        "Report-only in 2c (alias_not_in_facts / lost-and-added items are retried: " +
        f"turn-1 retries {s2c['retried']['turn 1']}, turn-2 {s2c['retried']['turn 2']}, none unresolved)." if flag == "alias_not_in_facts"
        else "Report-only in 2c; the registry (3) and 4a use the concepts as extracted.")

# C10: 4a
d4 = jload(OUT / "stage_4a_definitions" / "checks.json")
mism = [c for c, v in d4["concepts"].items() if "defined_mismatch" in v]
mism_true = [c for c in mism if concepts[c]["defined"]]
misp = d4["totals"]["misplaced"]
row("con.4a.defined_mismatch", "4a definitions", "concepts 4a marks defined, with no segment that defines them (defined_in empty)",
    "stage_4a_definitions/checks.json flags.defined_mismatch; split by concepts.json defined", len(mism), len(defined_ids), "concepts",
    [ex(cname(c), concepts[c]["definition"], 130) for c in mism_true[:5]], "not fixed (future work)",
    f"{len(mism_true)} are defined:true with empty defined_in (they keep a card and a glossary entry); {len(mism) - len(mism_true)} "
    "are defined:false with a defining segment. The definition text is the real 4a one (one Qwen call per concept, cap 40 facts).")
row("con.4a.misplaced", "4a definitions", "definition facts that 4a flags as misplaced (cited under another concept's segment)",
    "stage_4a_definitions/checks.json flags.misplaced", len(misp), len(concepts), "concepts",
    [ex(cname(c), f'misplaced facts {d4["concepts"][c]["misplaced"]}') for c in misp[:5]], "not fixed (future work)")
row("con.4a.capped", "4a definitions", "concepts with more facts than the 4a cap (40), so the definition saw a subset",
    "stage_4a_definitions/checks.json totals.capped", d4["totals"]["capped"], len(concepts), "concepts",
    [ex("totals.capped", f'{d4["totals"]["capped"]} concepts, cap {d4["cap"]}')], "not fixed (future work)")
nodef = []
for c in sorted(defined_ids):
    d = concepts[c]["definition"]
    head = " ".join(d.split()[:20])
    if not DEFINITION_WORDS.search(head):
        nodef.append(c)
row("con.4a.definition_no_verb", "4a definitions", "defined concepts whose definition does not read like a definition (no 'is / are / refers to / means / "
    "denotes / stands for / describes' within the first 90 characters of the first 20 words)", f"regex {DEFINITION_WORDS.pattern} fails on the first 20 words",
    len(nodef), len(defined_ids), "defined concepts", [ex(cname(c), concepts[c]["definition"], 130) for c in nodef[:5]],
    "fixed in the pipeline", "Real 4a (2026-11-17): the old facts-based 'definition' read like a definition in only 26% of cards "
    "(analysis/mvp/test_report.md); this rule is a cheap lower bound of what remains.")

# --------------------------------------------------------------------------------------------- facts and segments
sent_total, null_start, null_end, both = 0, 0, 0, 0
null_ex = []
for f in sorted(glob.glob(str(OUT / "stage_0a_preprocess" / "times" / "lec_*.json")), key=lec_key):
    t = jload(f)
    sent_total += len(t)
    for k, v in t.items():
        ns, ne = v["start"] is None, v["end"] is None
        null_start += ns
        null_end += ne
        both += ns and ne
        if ns and len(null_ex) < 5:
            null_ex.append(k)
sent_text = {}
for f in glob.glob(str(OUT / "stage_0a_preprocess" / "lec_*.json")):
    sent_text.update(jload(f))
row("fact.0a.null_start", "0a preprocess", "transcript sentences with no start time (the sentence begins inside a subtitle cue)",
    "stage_0a_preprocess/times/lec_N.json start == null", null_start, sent_total, "sentences",
    [ex(k, sent_text.get(k, "")) for k in null_ex], "fixed in the pipeline",
    f"By design of 0a; 1b estimates segment boundaries inside a cue and 4d fixed null times for facts (2026-11-13). Also {null_end} with null end, "
    f"{both} with both null.")
fl2a = collections.Counter()
fl_ex = collections.defaultdict(list)
for f in sorted(glob.glob(str(OUT / "stage_2a_fact_extraction" / "checks" / "lec_*.json")), key=lec_key):
    for seg, v in jload(f).items():
        for fid, lst in v["flags"].items():
            for x in lst:
                fl2a[x["kind"]] += 1
                fl_ex[x["kind"]].append((fid, x["note"] + " | " + facts.get(fid, {}).get("text", "")))
for kind, label in (("long", "facts over about 50 words (several points in one fact?)"),
                    ("bare_acronym", "facts using an acronym without its full term"),
                    ("pointing", "facts with an unresolved pointing word (this, that)"),
                    ("acronym", "facts with an acronym flag")):
    if fl2a[kind]:
        row(f"fact.2a.{kind}", "2a facts", label, f"stage_2a_fact_extraction/checks/lec_N.json flags kind == {kind!r}", fl2a[kind], len(facts),
            "facts", [ex(*e, n=150) for e in fl_ex[kind][:5]], "not fixed (future work)", "Report-only in 2a; the 2b judge (which would act on them) was not run.")
ev = set()
for fid, f in facts.items():
    for e in f.get("evidence", []):
        ev.add(e)
sent_in_segs = sum(len(jload(f)) for f in glob.glob(str(OUT / "stage_0a_preprocess" / "times" / "lec_*.json")))
all_sentences = set(sent_text)
uncited = sorted(all_sentences - ev, key=lambda s: tuple(int(p) for p in s.split("/")))
row("fact.2a.sentences_uncited", "2a facts", "transcript sentences that no fact cites as evidence",
    "0a sentence IDs minus the union of facts.json evidence", len(uncited), len(all_sentences), "sentences",
    [ex(s, sent_text[s]) for s in uncited[:3]] + [ex(s, sent_text[s]) for s in uncited[len(uncited) // 2:len(uncited) // 2 + 2]],
    "not fixed (future work)", "Many are greetings, recaps and asides (expected); the share is not a defect by itself.")
nj = sum(1 for f in glob.glob(str(OUT / "stage_2b_verify_facts" / "judgements" / "lec_*.json")) for s in jload(f) if not s["judged"])
nseg_j = sum(1 for f in glob.glob(str(OUT / "stage_2b_verify_facts" / "judgements" / "lec_*.json")) for s in jload(f))
row("fact.2b.not_judged", "2b verify facts", "facts never checked by the fact judge (2b skipped: every fact kept unjudged)",
    "stage_2b_verify_facts/judgements/lec_N.json judged == false per segment", sum(len(s["outcome"]) for f in glob.glob(str(OUT / "stage_2b_verify_facts" / "judgements" / "lec_*.json")) for s in jload(f) if not s["judged"]),
    len(facts), "facts", [ex("segments", f"{nj} of {nseg_j} segments judged:false")], "not fixed (future work)",
    "Block 1 of the plan is open (PROMPT.md weak point 3); the 2b check files are copies of 2a's. Deferred to the 27B runs.")
no_seg = [fid for fid, f in facts.items() if f.get("segment") not in {s for L in lectures.values() for s in L["segments"]}]
null_t = [fid for fid, f in facts.items() if f.get("start") is None or f.get("end") is None]
share = collections.Counter((f["segment"], f["start"]) for f in facts.values() if f.get("start") is not None)
shared_start = [fid for fid, f in facts.items() if share[(f["segment"], f.get("start"))] >= 3]
row("fact.no_segment", "4d assemble", "facts whose segment is missing from the lecture layer", "facts.json segment not in knowledge/lectures/*.json segments",
    len(no_seg), len(facts), "facts", [ex(f, facts[f]["text"]) for f in no_seg[:5]], "fixed in the pipeline", "4d reference check: 0 broken references of "
    f"{jload(OUT / 'stage_4d_assemble' / 'checks.json')['references']:,}.")
row("fact.null_time", "4d assemble", "facts with a null start or end time", "facts.json start/end is null", len(null_t), len(facts), "facts",
    [ex(f, facts[f]["text"]) for f in null_t[:5]], "fixed in the pipeline", "4d fixed null sentence times (2026-11-13).")
row("fact.shared_start", "4d assemble", "facts that share their start time with 2 or more other facts of the same segment (coarse time links)",
    "count of (segment, start) >= 3", len(shared_start), len(facts), "facts",
    [ex(f, f'{facts[f]["start"]}s: {facts[f]["text"]}') for f in shared_start[:5]], "not fixed (future work)",
    "The citation time is the start of the fact's first evidence sentence, often the topic's introduction (test_report.md: 462 with >= 2 others).")
seg_total = sum(len(L["segments"]) for L in lectures.values())
empty_seg = [(lec, s, v) for lec, L in lectures.items() for s, v in L["segments"].items() if not v["facts"]]
b4 = jload(OUT / "stage_4b_goals" / "checks.json")
row("seg.no_facts", "2a / 4d", "segments with no fact (nothing to ask, recap or link)", "knowledge/lectures/lec_N.json segments[*].facts == []",
    len(empty_seg), seg_total, "segments", [ex(s, v["subgoal"]) for lec, s, v in empty_seg[:5]], "not fixed (future work)",
    "Mostly intros and closing summaries; 4b: segments in no objective " + str(b4["totals"]["flags"]["in_no_objective"]) +
    f" (of which {b4['totals']['in_no_objective_defining']} define a concept).")
no_obj = [(lec, x) for lec, v in b4["lectures"].items() for x in v.get("in_no_objective", [])]
row("seg.4b.in_no_objective", "4b goals", "segments that serve no lecture objective", "stage_4b_goals/checks.json in_no_objective",
    b4["totals"]["flags"]["in_no_objective"], seg_total, "segments", [ex(x["segment"], x["subgoal"]) for lec, x in no_obj[:5]],
    "not fixed (future work)", "Mostly closing summaries.")
rep1b = jload(OUT / "stage_1b_verify_segments" / "report.json")
left = {k: v for k, v in rep1b.items() if v.get("flagged_left")}
row("seg.1b.flagged_left", "1b verify segments", "lectures where a flagged segment problem was left after the retries", "stage_1b report.json flagged_left non-empty",
    len(left), len(rep1b), "lectures", [ex(k, str(v["flagged_left"])) for k, v in list(left.items())[:5]], "not fixed (future work)")
c4 = jload(OUT / "stage_4c_lecture_graph" / "checks.json")["totals"]
row("seg.4c.assumed", "4c lecture graph", "concepts a lecture uses but no earlier lecture defines (assumed knowledge)",
    "stage_4c_lecture_graph/checks.json totals.assumed_concepts", len(c4["assumed_concepts"]), len(concepts), "concepts",
    [ex(c, concepts[c]["name"]) for c in c4["assumed_concepts"][:5]], "display rule",
    "Same set as the connecting concepts (2,074 listed; 1,806 have defined:false); shown as assumed knowledge, not as cards. "
    f"{len(c4['no_prerequisite'])} lectures with no prerequisite, 70 lecture pairs where everything is redefined (all_redefined).")
d4d = jload(OUT / "stage_4d_assemble" / "checks.json")
row("seg.4d.broken_refs", "4d assemble", "broken references, duplicate IDs or schema errors in the knowledge layer",
    "stage_4d_assemble/checks.json (schema, broken_references, duplicate_ids, coverage, unchecked_files)",
    len(d4d["broken_references"]) + len(d4d["duplicate_ids"]) + len(d4d["schema"]) + len(d4d["coverage"]), d4d["references"], "references",
    [ex("checks.json", f'ok: {d4d["ok"]}, {d4d["files"]} files')], "fixed in the pipeline", "4d reference check; also re-run independently by analysis/mvp/integrity.py (2026-11-13).")

# --------------------------------------------------------------------------------------------- QA
qa_res = [json.loads(l) for l in open(ROOT / "analysis/mvp/qa_run/results.jsonl")] + \
         [json.loads(l) for l in open(ROOT / "analysis/mvp/qa_run/results_run2.jsonl")]
md_re = re.compile(r"(\*\*|^\s*[*-] |\$[^$]+\$)", re.M)
md = [r for r in qa_res if md_re.search(r["answer"])]
latex = [r for r in qa_res if re.search(r"\$[^$]+\$", r["answer"])]
slow = [r for r in qa_res if r["seconds"] > 15]
nocite = [r for r in qa_res if r.get("covered") and not r.get("citations")]
row("qa.markdown_raw", "QA / viewer", "answers containing markdown (** bold, bullets) or LaTeX that the page showed as raw characters",
    "regex ** / list bullet / $...$ in answer of analysis/mvp/qa_run/results.jsonl and results_run2.jsonl (2026-11-13 run, not rerun)",
    len(md), len(qa_res), "answers", [ex(f'{r["id"]} {r["seconds"]}s', r["answer"][:120]) for r in md[:5]], "fixed in the viewer",
    f"Bold and lists rendered since 2026-11-13; formulas typeset with KaTeX (vendored, offline) since 2026-11-18 (7620342); LaTeX in {len(latex)} of them. Source: analysis/mvp/test_report.md section 5, issue 1.")
row("qa.slow", "QA", "answers slower than 15 s", "seconds > 15 in analysis/mvp/qa_run/results*.jsonl", len(slow), len(qa_res), "answers",
    [ex(f'{r["id"]} {r["seconds"]}s', r["question"]) for r in slow[:5]], "fixed in the pipeline",
    "Round-1+ thinking off and early exit for unknown names (2026-11-17, analysis/qa/STATE.md): bench_after median 4.8 s, max 9.3 s.")
bench = [json.loads(l) for l in open(ROOT / "analysis/qa/bench_after.jsonl")]
slowb = [r for r in bench if r["seconds"] > 8]
row("qa.bench_slow", "QA", "bench answers slower than 8 s after the latency fixes", "seconds > 8 in analysis/qa/bench_after.jsonl (34 answers, 2026-11-17)",
    len(slowb), len(bench), "answers", [ex(f'{r["id"]} run {r["run"]} {r["seconds"]}s', r["question"]) for r in slowb[:5]], "not fixed (future work)",
    "Compare questions (two cards, long answers) remain the slowest; analysis/qa/STATE.md.")
# Recorded by reading in analysis/mvp/test_report.md (2026-11-13); these cannot be detected by a rule, so they are quoted, not recomputed.
row("qa.not_covered_padded", "QA", "not-covered answers that decline but then pad with loosely related facts, and are the slowest type",
    "quoted from analysis/mvp/test_report.md section 3 (Q19 20.9 s, Q20); not recomputed", 2, 36, "questions",
    [ex("Q19", "Kalman filter: correct refusal after 20.9 s, then related facts"), ex("Q20", "Vergence-accommodation: declines, pads with loosely related facts")],
    "fixed in the pipeline", "Time fixed 2026-11-17 (unknown name -> early exit; B01 Kalman now one round, analysis/qa/STATE.md); the padding itself is unchanged.")
row("qa.prereq_odd", "QA / 4c", "prerequisite answers listing odd concepts (location awareness, markers before lecture 40; augmented virtuality before 16)",
    "quoted from analysis/mvp/test_report.md section 3 (Q13, Q35) and 5 (issue 10); not recomputed", 2, 36, "questions",
    [ex("Q13", "prerequisites for lecture 40 include location awareness, markers"), ex("Q35", "lecture 16: augmented virtuality; HMD = 'displays from the 1950s'")],
    "fixed in the pipeline", "lecture_dependencies rewritten 2026-11-17: single mentions listed 'in passing', ranked by uses (analysis/qa/STATE.md); hand-checked on lectures 16, 40, 30.")
row("qa.two_times", "QA", "'where is X taught' answers showing two different times (text 14:25, citation 11:44)",
    "quoted from analysis/mvp/test_report.md section 3 (Q11, Q12); not recomputed", 2, 36, "questions",
    [ex("Q11", "text says 14:25 but cites the segment at 11:44")], "fixed in the pipeline",
    "cite() removes a model-written time before a citation; the card cites one time (2026-11-17, analysis/qa/STATE.md).")

# --------------------------------------------------------------------------------------------- part titles
pt = OUT / "stage_4e_part_titles" / "titles.json"
if pt.exists():
    t = jload(pt)
    items = t.get("titles", t) if isinstance(t, dict) else t
    vals = items.values() if isinstance(items, dict) else items
    bad = [v for v in vals if isinstance(v, dict) and v.get("ok") is False]
    row("seg.part_titles", "4e part titles", "part titles failing the code check (ok: false)", "stage_4e_part_titles/titles.json ok == false",
        len(bad), len(list(items)), "segments", [ex(str(v.get("segment", "")), v.get("title", "")) for v in bad[:5]], "not fixed (future work)")
else:
    row("seg.part_titles", "4e part titles", "part titles failing the code check (ok: false)", "stage_4e_part_titles/titles.json (task S6, not run yet)",
        None, 386, "segments", [], "not fixed (future work)", "pending: the file does not exist yet.")

# --------------------------------------------------------------------------------------------- history
HISTORY = [
    ("2026-11-13", "Activities had no judges; quiz correct option uniquely longest in 52% (751 of 1,443); 5 unresolved crosswords with masked clues; "
     "match pairs ~70% problematic", "Activities judge v3 (judge + one rewrite round, per-item verdicts in checks.json) and the retry check for the longest option; "
     "unique-longest is now computed above."),
    ("2026-11-13", "4a skipped: each 'definition' was the concept's first defining fact (only 26% read like a definition; 1,107 cards)",
     "Real 4a, one Qwen call per concept, cap 40 facts, checks with retry (2026-11-17): 1,316 defined / 1,806 connecting concepts."),
    ("2026-11-13", "3b skipped: duplicate concepts on screen (headset / head-mounted display / VR headset on 11 lecture maps; 6 acronym/expansion twins)",
     "3b synonym merge rebuilt 2026-11-17 (425 clusters, 262 model merges, 2,795 kept apart); activity concept IDs remapped. Residual duplicates are counted in the con.* rows."),
    ("2026-11-13", "4d: null sentence times broke fact times", "4d fixed for null sentence times (2026-11-13)."),
    ("2026-11-17", "QA answers slow (median 5.4 s, max 16.2 s) and showing odd prerequisites", "Thinking off after round 0, early exit on unknown names, "
     "lecture_dependencies rewritten, citations tidied (analysis/qa/STATE.md): median 4.8 s, max 9.3 s."),
    ("2026-11-17/18", "Judge-failed items shown to learners", "Per-kind hide rule in serve.py (HIDE_JUDGE_FAILED) and the 2026-11-18 display decisions: recaps show passing "
     "points only, crosswords pre-fill failed words and hide their clues, connecting concepts get no card / glossary entry / definition."),
]

# --------------------------------------------------------------------------------------------- output
judge_sum = sum(len(J_failed[k]) for k in J_failed)
self_checks = {"judge_failed_items_sum": judge_sum, "pipeline_still_failed_items": tj["still_failed_items"],
               "equal": judge_sum == tj["still_failed_items"],
               "recap_failed_texts_pipeline_note": 222, "recap_failed_points_pipeline_note": 371,
               "recap_texts_here": len(texts), "recap_points_here": len(points)}
doc = {"course": COURSE, "self_checks": self_checks, "generated_from": "pipeline/output/" + COURSE + " (read only)", "rule": "code only: no language model, no agent judgement",
       "handling_values": list(HANDLING), "rows": rows, "history": [dict(date=d, failure=f, fix=x) for d, f, x in HISTORY]}
(HERE / "inventory.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def fmt(r):
    if r["count"] is None:
        return "pending"
    d = f" of {r['denominator']:,}" if r["denominator"] else ""
    pct = f" ({100 * r['count'] / r['denominator']:.1f}%)" if r["denominator"] and r["count"] is not None else ""
    return f"{r['count']:,}{d}{pct}"


md_lines = [f"# Failure inventory: {COURSE} (code-only)", "",
            f"Written by `analysis/failures/inventory.py` from `pipeline/output/{COURSE}/` (read only) and the QA records in `analysis/`. "
            "Every count comes from a deterministic rule, a pipeline check file or judge verdict, or a stored similarity: no language model "
            "and no agent decided what a failure is. Handling is one of: " + "; ".join(f"**{h}**" for h in HANDLING) + ".", "",
            "## Table", "", "| Row | Stage | What fails | Count | Handling |", "|---|---|---|---|---|"]
for r in rows:
    md_lines.append(f"| `{r['id']}` | {r['stage']} | {r['what_fails']} | {fmt(r)} {r['unit']} | {r['handling']} |")
md_lines += ["", f"Self-check: failed judge items found here {judge_sum}, the pipeline's own total (checks.json totals.judge.still_failed_items) "
             f"{tj['still_failed_items']}: {'equal' if judge_sum == tj['still_failed_items'] else 'DIFFERENT'}.", "", "## Rows", ""]
for r in rows:
    md_lines += [f"### `{r['id']}` ({r['stage']})", "", f"- **Fails:** {r['what_fails']}", f"- **Detected by:** {r['detected_by']}",
                 f"- **Count:** {fmt(r)} {r['unit']}", "- **Examples:**"]
    md_lines += [f"  - `{e['id']}`: {e['excerpt']}" for e in r["examples"]] or ["  - (none)"]
    md_lines += [f"- **Handling:** {r['handling']}" + (f". {r['handling_note']}" if r["handling_note"] else ""),
                 f"- **Sample read (an agent's reading of a few hits; not code, not used for any count):** {r['precision']}", ""]
md_lines += ["## History: failures found earlier and fixed", "", "| Date | Failure found | Fix |", "|---|---|---|"]
md_lines += [f"| {d} | {f} | {x} |" for d, f, x in HISTORY]
(HERE / "inventory.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
print(f"{len(rows)} rows -> {HERE / 'inventory.json'}, {HERE / 'inventory.md'}")
for r in rows:
    print(f"{r['id']:34s} {fmt(r):34s} {r['handling']}")
