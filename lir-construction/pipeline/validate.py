"""Layer-2 validation: deterministic checks. Each returns a list of error messages (empty = pass).

The messages are written for the model: on a retry they are appended to the prompt.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

ALLOWED_VERBS = set("""
analyze analyse apply appreciate argue assess build calculate categorize characterize choose classify compare
compute connect construct contrast convert create critique decide decompose define demonstrate derive describe
design determine develop diagnose differentiate discover discuss distinguish estimate evaluate examine explain
explore express extend find formulate generalize generalise identify illustrate implement infer interpret
investigate justify learn link list locate map measure model name observe obtain organize outline perform plan
predict prove quantify rank reason recall recognize recognise reconstruct relate represent review see select
show simplify sketch solve state summarize summarise trace transform translate understand use verify visualize
visualise write appraise break check combine complete conclude convince count debug detect draw encode
enumerate familiarize frame get grasp handle highlight integrate introduce know master motivate navigate note
practice practise prepare present prioritize realize realise recap reflect reformulate remember set specify
study test think track train tune walk work examine apply contextualize
""".split())

STOP = set("a an the of to in on for and or with by from is are be as at this that these those its it".split())


def norm_words(text: str) -> list[str]:
    return [stem(w) for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP]


def stem(w: str) -> str:
    """A crude stemmer: enough to match plural/verb forms of keywords and terms."""
    for suf in ("ization", "isation", "ations", "ation", "ings", "ing", "ies", "ied", "ers", "er", "es", "ed", "s", "ly"):
        if len(w) > len(suf) + 2 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf in ("ies", "ied") else "")
    return w


def first_word(text: str) -> str:
    m = re.match(r"\s*([A-Za-z]+)", text)
    return m.group(1).lower() if m else ""


def check_verb_first(text: str, what: str) -> list[str]:
    w = first_word(text)
    if w not in ALLOWED_VERBS:
        return [f'{what} "{text}" must start with an action verb such as Explain, Derive, Compare, Apply, Identify '
                f'or Understand (it starts with "{w}")']
    return []


def check_ids(ids: list[int], lo: int, hi: int, what: str) -> list[str]:
    bad = [i for i in ids if not lo <= i <= hi]
    if bad:
        return [f"{what} cites sentence IDs {bad}, which are not in this segment (valid IDs: {lo} to {hi})"]
    if not ids:
        return [f"{what} cites no sentence IDs"]
    return []


def fuzzy_in(term: str, text: str, threshold: float = 0.8) -> bool:
    """True if the term (or a close variant) occurs in the text."""
    tw, xw = norm_words(term), norm_words(text)
    if not tw:
        return False
    if all(w in xw for w in tw):
        return True
    n = len(tw)
    target = " ".join(tw)
    for i in range(max(1, len(xw) - n + 1)):
        if SequenceMatcher(None, target, " ".join(xw[i:i + n])).ratio() >= threshold:
            return True
    # abbreviations: "MSE" for "mean squared error"
    words = term.split()
    if len(words) == 1 and term.isupper():
        return term.lower() in text.lower()
    return False


def check_quiz_options(options: list[str], correct: int, what: str) -> list[str]:
    errs = []
    normed = [re.sub(r"\W+", " ", o.lower()).strip() for o in options]
    if len(set(normed)) < len(normed):
        errs.append(f"{what}: options must all be different")
    if len(options) > 2:
        others = [len(o) for i, o in enumerate(options) if i != correct]
        mean_other = sum(others) / len(others)
        if len(options[correct]) > 1.5 * mean_other + 20:
            errs.append(f"{what}: the correct option is much longer than the others "
                        f"({len(options[correct])} vs about {mean_other:.0f} characters); make them similar in length")
    if any(re.search(r"\b(all|none) of the above\b", o, re.I) for o in options):
        errs.append(f'{what}: do not use "all of the above" or "none of the above"')
    return errs


def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, " ".join(norm_words(a)), " ".join(norm_words(b))).ratio()


def sentence_count(text: str) -> int:
    return len([s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s])


def missing_keywords(keywords: list[str], answer: str) -> list[str]:
    aw = " ".join(norm_words(answer))
    return [k for k in keywords if " ".join(norm_words(k)) not in aw]


def display_name(name: str) -> str:
    """Names start with a capital letter ("Real environment"); "iPhone"-style words are left alone."""
    name = name.strip()
    if not name or re.match(r"^[a-z][A-Z]", name):
        return name
    return name[0].upper() + name[1:]


PRONOUN_START = re.compile(r"^\s*(it|this|these|they|that|those|here)\b", re.I)


def check_definition(term: str, definition: str, what: str) -> list[str]:
    """A key-term definition must stand on its own: start with the term, say more than the term's own words,
    and not merely spell out an abbreviation."""
    errs = []
    name = re.sub(r"\s*\([^)]*\)\s*$", "", term).strip()          # "Augmented reality (AR)" -> "Augmented reality"
    if PRONOUN_START.match(definition):
        errs.append(f'{what}: the definition starts with "{definition.split()[0]}"; start it with the term itself, '
                    f'e.g. "{display_name(name)} is ..."')
    head = norm_words(name)
    first = norm_words(" ".join(definition.split()[:10]))
    if head and not any(w in first for w in head):
        errs.append(f'{what}: start the definition with the term itself, e.g. "{display_name(name)} is ..."')
    extra = [w for w in norm_words(definition) if w not in set(head) and len(w) > 2]
    if len(extra) < 5:
        errs.append(f"{what}: the definition is too thin; say what kind of thing it is and what sets it apart")
    if re.search(r"\b(stands for|is short for|abbreviat\w*|acronym)\b", definition, re.I) and len(extra) < 9:
        errs.append(f"{what}: do not just spell out the abbreviation; explain what the concept is")
    if "," in name or len(name.split()) > 5:
        errs.append(f'{what}: "{term}" is not one concept; give each concept as its own short term')
    parts = [s for s in re.split(r"(?<=[.!?])\s+", definition.strip()) if s]
    if len(parts) >= 2 and similar(parts[0], parts[1]) > 0.6:
        errs.append(f"{what}: the definition repeats itself; say it once, clearly")
    t = term.replace(".", "").strip()
    if 2 <= len(t) <= 6 and t.isalnum() and sum(c.isupper() for c in t) >= 2:
        errs.append(f'{what}: "{term}" is a bare abbreviation; write the full name with the abbreviation in '
                    f'brackets, e.g. "Augmented reality (AR)"')
    return errs


LECTURE_TALK = re.compile(r"\b(according to the (lecture|instructor|speaker|course|video)|(does|did) the (lecture|instructor|"
                          r"speaker|course)|the (lecture|instructor|speaker|course) (says?|states?|describes?|mentions?|"
                          r"suggests?|explains?|discuss\w*|cover\w*|plans?|intends?)|(this|the) (course|lecture|segment)"
                          r"('s)? (goal|aim|objective|focus|structure)|(primary|main) (goal|focus|objective) of (this|the) "
                          r"course|stand for\b|stands for\b|(mentioned|described|discussed|covered|listed|stated|presented|"
                          r"given|shown|introduced) (in|by) (the|this) (lecture|course|segment|video|instructor|speaker)|"
                          r"(in|from) (the|this) (lecture|segment|video)\b|(will|does) (this|the) course)", re.I)


def check_subject_question(stem: str, what: str) -> list[str]:
    """Quiz and review questions test the subject, not what the lecture or course says, and not abbreviations."""
    m = LECTURE_TALK.search(stem)
    if m:
        return [f'{what}: "{m.group(0)}" — test the subject itself, not what the lecture or course says, and do not '
                f"ask what an abbreviation stands for"]
    return []


def check_label(label: str, what: str) -> list[str]:
    if re.search(r"\b(and|or|the|a|an|between|of the)\s*$", label.strip(), re.I):
        return [f'{what}: the label "{label}" is unfinished; "src label dst" must read as a complete sentence']
    return []
