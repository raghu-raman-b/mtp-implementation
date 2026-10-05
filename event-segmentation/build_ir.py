#!/usr/bin/env python
"""Build the Lecture Intermediate Representation (LIR) from a lecture's outputs.

    python build_ir.py outputs/week01_lecture01      # one lecture
    python build_ir.py outputs                       # every lecture under outputs/

Reads segments.json, subgoals.json and hierarchy.json; writes lecture.lir.

LIR v1 grammar (one statement per line; lines starting with `//` are comments; strings are JSON string literals):

    file     := header lecture
    header   := "lir" VERSION
    lecture  := "lecture" ID "{" NL  meta*  goal*  segment+  "}"
    meta     := ("title" | "source") STRING
    goal     := "goal" GOAL_ID STRING ["under" GOAL_ID]      // goal tree above the subgoals;
                                                             // exactly one goal has no parent (the root)
    segment  := "segment" SEGMENT_ID "{" NL
                    PARENT_ID ":" GOAL_ID STRING              // the segment's subgoal and the goal it rolls up to
                    "time" TIMESTAMP "->" TIMESTAMP            // HH:MM:SS.mmm
                    "content" STRING                          // transcript of the segment
                "}"

Segments appear in playback order. Subgoals are declared inside their segment;
every other goal is declared with `goal`.
"""
import json
import sys
from pathlib import Path

VERSION = "1"


def fmt_ts(t):
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"


def q(s):
    return json.dumps(s, ensure_ascii=False)


def build(out_dir):
    out_dir = Path(out_dir)
    seg_doc = json.loads((out_dir / "segments.json").read_text())
    subgoals = json.loads((out_dir / "subgoals.json").read_text())
    nodes = json.loads((out_dir / "hierarchy.json").read_text())
    segs = seg_doc["segments"]

    parent = {c: p for p, n in nodes.items() for c in n["children"]}
    roots = [i for i in nodes if i not in parent]
    if roots != ["TOP"]:
        raise ValueError(f"{out_dir}: expected the single root TOP, found {roots}")

    def sg_id(seg):
        return "SG" + seg["id"][1:]

    for s in segs:
        if sg_id(s) not in nodes or s["id"] not in subgoals:
            raise ValueError(f"{out_dir}: segment {s['id']} has no subgoal")

    # goals above the subgoals, top-down then in roadmap order
    order = []

    def walk(i):
        if nodes[i]["level"] > 0:
            order.append(i)
            for c in nodes[i]["children"]:
                walk(c)

    walk("TOP")
    width = max(len(i) for i in order)

    lines = [
        f"lir {VERSION}",
        "",
        f"lecture {out_dir.name} {{",
        f"  title  {q(seg_doc['lecture'])}",
        f"  source {q(Path(seg_doc['srt']).name)}",
        "",
    ]
    for i in order:
        under = f" under {parent[i]}" if i in parent else ""
        lines.append(f"  goal {i.ljust(width)} {q(nodes[i]['text'])}{under}")
    for s in segs:
        sg = sg_id(s)
        lines += [
            "",
            f"  segment {s['id']} {{",
            f"    {parent[sg]}: {sg} {q(subgoals[s['id']])}",
            f"    time    {fmt_ts(s['start'])} -> {fmt_ts(s['end'])}",
            f"    content {q(s['text'])}",
            "  }",
        ]
    lines += ["}", ""]
    path = out_dir / "lecture.lir"
    tmp = path.with_suffix(".lir.tmp")
    tmp.write_text("\n".join(lines), encoding="utf-8")
    tmp.replace(path)
    return path


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    root = Path(sys.argv[1])
    dirs = [root] if (root / "segments.json").exists() else sorted(p.parent for p in root.glob("*/hierarchy.json"))
    if not dirs:
        sys.exit(f"no lecture outputs found under {root}")
    for d in dirs:
        if not (d / "hierarchy.json").exists():
            print(f"skip {d.name}: not labeled yet")
            continue
        print(f"wrote {build(d)}")


if __name__ == "__main__":
    main()
