#!/usr/bin/env python
"""Event segmentation + goal roadmap for NPTEL lecture videos.

    python run.py <lecture | week | course folder> [--stage segment|label|all] [--force]

Rerunnable: finished stages are skipped (unless --force or the segmentation
parameters change), and partially labeled lectures resume where they stopped.
"""
import argparse
import atexit
import json
import os
import re
import subprocess
import sys
import time
import traceback
from pathlib import Path

from tqdm import tqdm

HERE = Path(__file__).resolve().parent
OUT_ROOT = HERE / "outputs"


def say(msg=""):
    tqdm.write(msg)


def step(msg):
    say(f"    · {msg}")


def write_atomic(path, text):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write_json(path, obj):
    write_atomic(path, json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


# ----------------------------------------------------------------- discovery
def lecture_num(p):
    m = re.match(r"Lecture\s+(\d+)", p.name)
    return int(m.group(1)) if m else 10 ** 6


def find_lectures(root):
    root = Path(root).resolve()
    if (root / "raw").is_dir():
        dirs = [root]
    else:
        dirs = {p.parent.parent for p in root.rglob("raw/*.srt") if p.parent.parent.name.startswith("Lecture")}
    lectures = []
    for d in sorted(dirs, key=lecture_num):
        srts = sorted((d / "raw").glob("*.srt"))
        if srts:
            lectures.append((d, srts[0]))
    return lectures


def out_name(lec_dir):
    week = re.sub(r"\(.*?\)", "", lec_dir.parent.name).strip().lower()
    week = re.sub(r"\d+", lambda m: f"{int(m.group()):02d}", week)
    week = re.sub(r"[^a-z0-9-]+", "", week)
    return f"{week}_lecture{lecture_num(lec_dir):02d}"


# ----------------------------------------------------------------- stage 1
def run_segmentation(lec_dir, srt, out, args):
    from texttiling import fmt_dur, fmt_ts, segment

    params = {"window": args.window, "min_seg": args.min_seg, "smooth_k": args.smooth,
              "fine_window": args.fine_window, "refine_radius": args.refine_radius}
    seg_file = out / "segments.json"
    if seg_file.exists() and not args.force:
        prev = json.loads(seg_file.read_text())
        if all(prev["params"].get(k) == v for k, v in params.items()):
            say(f"  Phase 1/5 Segmentation: already done ({len(prev['segments'])} segments), skipping")
            return prev["segments"], False
        say("  Phase 1/5 Segmentation: parameters changed, recomputing")
    else:
        say("  Phase 1/5 Segmentation: parse SRT → embed → window similarity → depth → DP boundaries")

    t0 = time.time()
    segs, gaps, meta = segment(srt, window=args.window, min_seg=args.min_seg, smooth_k=args.smooth,
                               fine_window=args.fine_window, refine_radius=args.refine_radius, log=step)
    title = f"{lec_dir.parent.name} / {lec_dir.name}"

    lines = [f"# Event segmentation: {title}",
             f"# source: {srt.name}",
             f"# method: embedding TextTiling ({meta['embed_model']}), window {args.window:g}s, "
             f"smoothing ±{args.smooth}, DP boundaries with min segment {args.min_seg:g}s, tau={meta['tau']:.4f}, "
             f"refined with {args.fine_window:g}s window within ±{args.refine_radius:g}s",
             f"# format: ID | start --> end | duration", ""]
    for s in segs:
        lines += [f"{s['id']} | {fmt_ts(s['start'])} --> {fmt_ts(s['end'])} | {fmt_dur(s['end'] - s['start'])}",
                  s["text"], ""]
    write_atomic(out / "segments.txt", "\n".join(lines))
    write_atomic(out / "similarity.tsv", "time\tsim\tsim_smooth\tdepth\tsim_fine\tboundary\n" + "".join(
        f"{fmt_ts(g['time'])}\t{g['sim']:.4f}\t{g['sim_smooth']:.4f}\t{g['depth']:.4f}\t{g['sim_fine']:.4f}\t{int(g['boundary'])}\n"
        for g in gaps))
    # new segments invalidate any labels built on the old ones
    for f in ("subgoals_draft.json", "subgoals.json", "subgoals.txt", "hierarchy.json", "goal_hierarchy.txt", "reasoning_log.txt", "lecture.lir"):
        (out / f).unlink(missing_ok=True)
    write_json(seg_file, {"lecture": title, "srt": str(srt), "params": params, "meta": meta, "segments": segs})
    for s in segs:
        step(f"{s['id']}  {fmt_ts(s['start'])} → {fmt_ts(s['end'])}  ({fmt_dur(s['end'] - s['start'])})")
    say(f"    done in {time.time() - t0:.1f}s")
    return segs, True


# ----------------------------------------------------------------- LLM server
_server = None


def ensure_llm(llm, port):
    global _server
    if llm.health():
        return
    log_path = OUT_ROOT / "llm_server.log"
    say(f"  Starting llama-server (first run downloads the model; log: {log_path})")
    log_f = open(log_path, "w")
    _server = subprocess.Popen([str(HERE / "serve_llm.sh")], stdout=log_f, stderr=subprocess.STDOUT,
                               env={**os.environ, "LLM_PORT": str(port)})
    atexit.register(lambda: _server.poll() is None and _server.terminate())
    bar = tqdm(desc="    waiting for llama-server", bar_format="{desc} {elapsed} | {postfix}", leave=False)
    while not llm.health():
        if _server.poll() is not None:
            bar.close()
            raise RuntimeError(f"llama-server exited with code {_server.returncode}; see {log_path}")
        tail = log_path.read_text(errors="replace").replace("\r", "\n").strip().splitlines()[-1:] or [""]
        bar.set_postfix_str(tail[0][-90:])
        bar.update(0)
        time.sleep(1)
    bar.close()
    say("    llama-server ready")


# ----------------------------------------------------------------- stage 2
def run_labeling(lec_dir, segs, out, args, llm):
    import goals as G
    from texttiling import fmt_ts

    title = f"{lec_dir.parent.name} / {lec_dir.name}"
    if (out / "goal_hierarchy.txt").exists() and not args.force:
        say("  Phases 2-5 Labeling: already done, skipping")
        return
    ensure_llm(llm, args.port)
    llm.log.clear()

    # Phase 2: a draft subgoal per segment, from its transcript alone
    # Phase 3: refine each draft while showing the other segments' drafts, so neighbours stay distinct
    # (both cached per segment so interrupted runs resume)
    def label_pass(phase, name, path, fn):
        cache = json.loads(path.read_text()) if path.exists() and not args.force else {}
        todo = [s for s in segs if s["id"] not in cache]
        say(f"  Phase {phase}/5 {name}: {len(segs)} segments ({len(segs) - len(todo)} cached)")
        t0 = time.time()
        for s in tqdm(todo, desc="    segments", unit="seg", leave=False):
            cache[s["id"]] = fn(s)
            write_json(path, cache)
            step(f"{s['id']} → SG{s['id'][1:]}: {cache[s['id']]}")
        say(f"    done in {time.time() - t0:.1f}s")
        return cache

    drafts = label_pass(2, "Subgoal drafts", out / "subgoals_draft.json", lambda s: G.label_subgoal(llm, s))
    if len(segs) > 1:
        ordered = [(s["id"], drafts[s["id"]]) for s in segs]
        cache = label_pass(3, "Subgoal refinement with neighbouring segments", out / "subgoals.json",
                           lambda s: G.refine_subgoal(llm, s, ordered))
    else:
        say("  Phase 3/5 Subgoal refinement: single segment, nothing to compare against")
        cache = drafts
        write_json(out / "subgoals.json", cache)
    write_atomic(out / "subgoals.txt", "# segment ID\tsubgoal ID\tsubgoal\n" + "".join(
        f"{s['id']}\tSG{s['id'][1:]}\t{cache[s['id']]}\n" for s in segs))

    nodes = {}  # id -> {"text", "children", "level"}
    seg_of = {}
    for s in segs:
        sid = f"SG{s['id'][1:]}"
        nodes[sid] = {"text": cache[s["id"]], "children": [], "level": 0}
        seg_of[sid] = s
    level_ids = list(nodes)

    # Phase 4: group repeatedly until a handful of goals remain
    level = 0
    t0 = time.time()
    if len(level_ids) <= 3:
        say(f"  Phase 4/5 Hierarchy grouping: only {len(level_ids)} subgoals, no intermediate level needed")
    while len(level_ids) > 3:
        level += 1
        say(f"  Phase 4/5 Hierarchy grouping (level {level}): {len(level_ids)} goals → fewer")
        groups = G.group_goals(llm, [(i, nodes[i]["text"]) for i in level_ids], level)
        level_ids = []
        for k, (text, kids) in enumerate(groups, 1):
            gid = f"HG{level}.{k:02d}"
            nodes[gid] = {"text": text, "children": kids, "level": level}
            level_ids.append(gid)
            step(f"{gid}: {text}  ⟵ {', '.join(kids)}")
    say(f"    done in {time.time() - t0:.1f}s")

    # Phase 5: the video's goal
    say("  Phase 5/5 Top goal")
    t0 = time.time()
    def outline(i, depth=0):
        return [f"{'  ' * depth}{'- ' if depth else ''}{i}: {nodes[i]['text']}"] + \
            [l for c in nodes[i]["children"] for l in outline(c, depth + 1)]

    nodes["TOP"] = {"text": G.top_goal(llm, "\n".join(l for i in level_ids for l in outline(i))),
                    "children": level_ids, "level": level + 1}
    step(f"TOP: {nodes['TOP']['text']}")
    say(f"    done in {time.time() - t0:.1f}s")

    # outputs
    parent = {c: p for p, n in nodes.items() for c in n["children"]}

    def chain(i):
        out_ = [i]
        while out_[-1] in parent:
            out_.append(parent[out_[-1]])
        return out_

    lines = [f"# Goal hierarchy: {title}", "",
             "## Subgoal -> hierarchical goals (bottom to top)"]
    lines += [" -> ".join(chain(i)) for i in seg_of]
    lines += ["", "## Goals"]
    width = max(map(len, nodes))
    for i in sorted(nodes, key=lambda i: (-nodes[i]["level"], i)):
        lines.append(f"{i.ljust(width)}  {nodes[i]['text']}")
    lines += ["", "## Roadmap"]

    def tree(i, prefix="", last=True, root=False):
        n = nodes[i]
        label = f"{i}  {n['text']}"
        if i in seg_of:
            s = seg_of[i]
            label += f"  [{s['id']} {fmt_ts(s['start'])[:8]}–{fmt_ts(s['end'])[:8]}]"
        lines.append(label if root else f"{prefix}{'└── ' if last else '├── '}{label}")
        kid_prefix = "" if root else prefix + ("    " if last else "│   ")
        for k, c in enumerate(n["children"]):
            tree(c, kid_prefix, k == len(n["children"]) - 1)

    tree("TOP", root=True)
    write_json(out / "hierarchy.json", nodes)
    write_atomic(out / "reasoning_log.txt", "\n\n".join(
        f"===== {label} =====\n--- prompt ---\n{p}\n--- thinking ---\n{r}\n--- answer ---\n{a}"
        for label, p, r, a in llm.log) + "\n")
    write_atomic(out / "goal_hierarchy.txt", "\n".join(lines) + "\n")


# ----------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="a lecture folder, a week folder, or the whole course folder")
    ap.add_argument("--stage", choices=["segment", "label", "all"], default="all")
    ap.add_argument("--window", type=float, default=180.0, help="similarity window per side, seconds")
    ap.add_argument("--min-seg", type=float, default=360.0, help="minimum segment duration, seconds")
    ap.add_argument("--smooth", type=int, default=2, help="moving-average half width over gaps")
    ap.add_argument("--fine-window", type=float, default=60.0, help="window for boundary refinement, seconds")
    ap.add_argument("--refine-radius", type=float, default=60.0, help="max boundary shift in refinement, seconds")
    ap.add_argument("--port", type=int, default=8080, help="llama-server port")
    ap.add_argument("--force", action="store_true", help="redo stages even if outputs exist")
    args = ap.parse_args()

    lectures = find_lectures(args.path)
    if not lectures:
        sys.exit(f"no 'Lecture */raw/*.srt' found under {args.path}")
    OUT_ROOT.mkdir(exist_ok=True)
    say(f"Found {len(lectures)} lecture(s); outputs → {OUT_ROOT}")

    from goals import LLM
    llm = LLM(f"http://127.0.0.1:{args.port}")
    summary = []
    for k, (lec_dir, srt) in enumerate(lectures, 1):
        name = out_name(lec_dir)
        out = OUT_ROOT / name
        out.mkdir(exist_ok=True)
        say(f"\n[{k}/{len(lectures)}] {lec_dir.parent.name} / {lec_dir.name}  →  outputs/{name}")
        t0 = time.time()
        try:
            segs, _ = run_segmentation(lec_dir, srt, out, args)
            if args.stage in ("label", "all"):
                run_labeling(lec_dir, segs, out, args, llm)
                import build_ir
                say(f"  Intermediate representation → {build_ir.build(out).relative_to(HERE)}")
            summary.append((name, "ok", len(segs), time.time() - t0))
        except KeyboardInterrupt:
            say("\nInterrupted; rerun the same command to resume.")
            break
        except Exception as e:
            say(f"  ✗ failed: {e}")
            traceback.print_exc()
            summary.append((name, "FAILED", "-", time.time() - t0))

    say("\nSummary")
    say(f"  {'lecture':<26}{'status':<9}{'segments':>9}{'time':>9}")
    for name, status, n, dt in summary:
        say(f"  {name:<26}{status:<9}{n!s:>9}{dt:>8.1f}s")


if __name__ == "__main__":
    main()
