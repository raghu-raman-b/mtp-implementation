"""Lecture keys: how a lecture (or tutorial) is named across the pipeline, from its subtitle file's name.

    lec_7.srt -> "7"     lec_24b.srt -> "24b"     tutorials/tut_1.srt -> "tut_1"     tut_1_part2.srt -> "tut_1_part2"

Sentence IDs are "<key>/<i>" (7/0, 24b/0, tut_1/0) and segment IDs "<key>/S<k>". Every stage names a lecture's files
after its subtitle file: lec_7.json, lec_24b.json, tut_1.json. Lectures come first in order of number (24 before 24b),
then tutorials in order of number and part.
"""
from __future__ import annotations

import re
from pathlib import Path

STEM = re.compile(r"lec_(?P<lec>\d+[a-z]?)|(?P<tut>tut_\d+(?:_part\d+)?)")


def key_of(stem: str) -> str:
    """The key of a file stem: lec_24b -> "24b", tut_1 -> "tut_1"."""
    m = STEM.fullmatch(stem)
    if not m:
        raise ValueError(f"not a lecture or tutorial file name (want lec_<n>[letter] or tut_<n>[_part<k>]): {stem}")
    return m["lec"] or m["tut"]


def stem_of(key) -> str:
    """The file stem of a key: "24b" -> lec_24b, "tut_1" -> tut_1 (an int is taken as a lecture number)."""
    key = str(key)
    return f"lec_{key}" if key[:1].isdigit() else key


def order(key) -> tuple:
    """Sort key: lectures by number then letter, then tutorials by number then part."""
    key = str(key)
    if key[:1].isdigit():
        m = re.fullmatch(r"(\d+)([a-z]?)", key)
        return (0, int(m[1]), m[2], 0)
    m = re.fullmatch(r"tut_(\d+)(?:_part(\d+))?", key)
    return (1, int(m[1]), "", int(m[2] or 0))


def files(folder: Path) -> list[Path]:
    """A stage folder's per-lecture JSON files (lec_*.json, tut_*.json), in lecture order."""
    paths = [p for p in Path(folder).glob("*.json") if STEM.fullmatch(p.stem)]
    return sorted(paths, key=lambda p: order(key_of(p.stem)))


def keys(folder: Path) -> list[str]:
    return [key_of(p.stem) for p in files(folder)]


def normalize(lectures) -> list[str] | None:
    """A list of keys from ints and strings (None stays None)."""
    return [str(x) for x in lectures] if lectures else None


def parse_only(spec: str) -> list[str]:
    """'1-5,8,24b,tut_1' -> ['1', '2', '3', '4', '5', '8', '24b', 'tut_1'] (a range takes plain numbers)."""
    out = []
    for part in spec.split(","):
        a, _, b = part.strip().partition("-")
        out += [str(i) for i in range(int(a), int(b) + 1)] if b else [a]
    return out
