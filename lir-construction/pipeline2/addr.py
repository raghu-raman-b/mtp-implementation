"""Addresses. Sentences are numbered per lecture and never change; everything else points at them.

    L05/S0412        sentence 412 of lecture L05
    L05/P03          part 3 of L05 (a range of sentences)
    L05/P03/K2       key point 2 of that part
    L05/P03/T1       term occurrence 1 of that part
    L05/O2           objective 2 of L05
    G3               course goal 3
    C0014            concept
    C0014@L05/P03    what part L05/P03 says about concept C0014 (a facet)
    E0031            edge
    D00420           decision
"""
from __future__ import annotations

import re


def sent(lid: str, i: int) -> str:
    return f"{lid}/S{i:04d}"


def part(lid: str, k: int) -> str:
    return f"{lid}/P{k:02d}"


def parse_sent(address: str) -> tuple[str, int]:
    m = re.fullmatch(r"(.+)/S(\d+)", address)
    if not m:
        raise ValueError(f"not a sentence address: {address}")
    return m.group(1), int(m.group(2))


def lecture_of(address: str) -> str:
    return address.split("/", 1)[0]
