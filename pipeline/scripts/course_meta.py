"""Course metadata, and the course block for the prompts (platform agnostic: outline and syllabus only).

    from scripts import course_meta
    course_meta.load("nptel_vr")                  # input/<course>/input/course.json as a dict
    course_meta.course_prompt("nptel_vr")         # prompts/course_meta.txt filled in: outline and syllabus
    course_meta.lecture_title("nptel_vr", 36)     # from titles.tsv

course.json is written by hand from the course's syllabus (a copy is kept in dataset/<course>/course_meta/):
    title, platform, institution, instructor {name, department, about, url}, prerequisites, intended_audience,
    industry_support, outline, syllabus [{week?, theme?, topics}], source
The prompts use only outline and syllabus; the rest is kept as a record. The syllabus is shown as topics in order,
grouped by theme when it has themes (consecutive entries with the same theme are merged); weeks are not shown, since
not every course has them. A course without an outline or a syllabus just loses that line.

A stage's prompt puts the course block in its {course} placeholder. The block is the same for every lecture of a
course, so it should come before anything lecture-specific: the engines' prefix cache then reuses it across lectures.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from scripts import lectures

ROOT = Path(__file__).resolve().parent.parent  # the pipeline folder
TEMPLATE = ROOT / "prompts" / "course_meta.txt"


def input_dir(course: str) -> Path:
    return ROOT / "input" / course / "input"


def load(course: str) -> dict:
    return json.loads((input_dir(course) / "course.json").read_text())


def lecture_title(course: str, key) -> str:
    """A lecture's (or tutorial's) title from titles.tsv, matched by file name (key "24b" -> lec_24b, "tut_1" ->
    tutorials/tut_1); "Lecture <key>" when it has none."""
    stem = lectures.stem_of(key)
    with open(input_dir(course) / "titles.tsv", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["id"].rsplit("/", 1)[-1] == stem and r["title"].strip():
                return r["title"].strip()
    return f"Lecture {key}"


def syllabus_lines(syllabus: list[dict]) -> str:
    """'- Theme: topic; topic' per theme (consecutive entries with the same theme merged), or '- topic' without themes."""
    groups: list[tuple[str | None, list[str]]] = []
    for entry in syllabus:
        theme = entry.get("theme")
        if theme and groups and groups[-1][0] == theme:
            groups[-1][1].extend(entry["topics"])
        else:
            groups.append((theme, list(entry["topics"])))
    lines = []
    for theme, topics in groups:
        lines += [f"- {theme}: " + "; ".join(topics)] if theme else [f"- {t}" for t in topics]
    return "\n".join(lines)


def course_prompt(course: str) -> str:
    """prompts/course_meta.txt filled in from course.json. A line is left out when the course lacks its field; the
    line just before {syllabus} (its heading) goes with it."""
    m = load(course)
    fields = {"outline": m.get("outline"), "syllabus": syllabus_lines(m.get("syllabus", []))}
    if not any(fields.values()):
        return ""                                      # nothing about the course: no block at all
    out = []
    for line in TEMPLATE.read_text().splitlines():
        keys = re.findall(r"\{(\w+)\}", line)
        if any(not fields.get(k) for k in keys):
            if "syllabus" in keys and out:
                out.pop()
            continue
        out.append(line.format(**fields))
    return "\n".join(out).strip()
