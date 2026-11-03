#!/usr/bin/env python3
"""Run report for a LIR v2 run: time, requests, tokens, GPU and server stats, and what was built, with charts.

    python3 run_report.py runs/<name>        # -> runs/<name>/report.md, report.json, charts/*.png

Reads what the run wrote: meta.json, server.csv (run_monitor.py sampler), and per course build/calls.jsonl (every
request), build/report.json (step times, counts, per-lecture output) and build/status.json. run_v2.sh calls it at the
end; it can be rerun at any time, also on a run in progress.

Time per lecture: the pipeline runs each step for all lectures at once (and both courses share the GPU), so a
lecture has no wall time of its own. A lecture's "GPU time" is the run's wall time split by the lecture's share of
all output tokens generated: output tokens are what the GPU spends its time on. The figures add up to the run's time.
"""
from __future__ import annotations

import csv
import json
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# reference palette (dataviz skill, light mode): categorical slots 1-2, text and chrome tokens
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]
SHORT = {"nptel-virtual-and-augmented-reality": "VR", "mit-6-7960-deep-learning": "Deep Learning"}


# ------------------------------------------------------------------------------------------------ loading
def jl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out


def server_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            try:
                rows.append({k: float(v) for k, v in r.items() if v not in ("", None)})
            except ValueError:
                pass
    return rows


def load(run: Path) -> dict:
    meta = json.loads((run / "meta.json").read_text()) if (run / "meta.json").exists() else {}
    courses = []
    for d in sorted(p for p in run.iterdir() if (p / "build").is_dir()):
        b = d / "build"
        rep = json.loads((b / "report.json").read_text()) if (b / "report.json").exists() else {}
        st = json.loads((b / "status.json").read_text()) if (b / "status.json").exists() else {}
        cid = rep.get("course", {}).get("id") or st.get("course_id") or d.name
        code = (d / "exit_code").read_text().split()[-1] if (d / "exit_code").exists() else None
        courses.append({"id": cid, "short": SHORT.get(cid, cid), "dir": d, "report": rep, "status": st,
                        "title": rep.get("course", {}).get("title") or st.get("title") or cid,
                        "calls": jl(b / "calls.jsonl"), "exit": code})
    return {"run": run, "meta": meta, "courses": courses, "server": server_rows(run / "server.csv")}


# ------------------------------------------------------------------------------------------------ helpers
def fmt_t(s: float) -> str:
    s = max(0.0, s)
    if s >= 3600:
        return f"{int(s // 3600)} h {int(s % 3600 // 60):02d} min"
    if s >= 60:
        return f"{s / 60:.1f} min"
    return f"{s:.0f} s"


def n(x) -> str:
    return f"{x:,.0f}" if isinstance(x, (int, float)) else str(x)


def pct(xs: list[float], q: float) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * (len(xs) - 1) + 0.5))]


def table(header: list[str], rows: list[list], align: str | None = None) -> str:
    align = align or "l" + "r" * (len(header) - 1)
    sep = ["---:" if a == "r" else "---" for a in align]
    return "\n".join(["| " + " | ".join(header) + " |", "| " + " | ".join(sep) + " |"]
                     + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows])


def style(ax, xlabel="", ylabel=""):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
        ax.spines[s].set_linewidth(0.8)
    ax.tick_params(colors=INK2, labelsize=9, length=0, pad=6)
    ax.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.set_xlabel(xlabel, color=INK2, fontsize=9)
    ax.set_ylabel(ylabel, color=INK2, fontsize=9)


def fig(w, h, rows=1, cols=1, **kw):
    f, axes = plt.subplots(rows, cols, figsize=(w, h), facecolor=SURFACE, **kw)
    return f, axes


def save(f, path: Path, title: str):
    f.suptitle(title, x=0.01, ha="left", color=INK, fontsize=12, fontweight="bold")
    f.tight_layout(rect=(0, 0, 1, 0.97))
    f.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(f)


# ------------------------------------------------------------------------------------------------ analysis
def analyse(D: dict) -> dict:
    meta, courses, srv = D["meta"], D["courses"], D["server"]
    sent_all = [c for C in courses for c in C["calls"] if not c.get("cached")]
    t_first = min((c["t_start"] for c in sent_all), default=meta.get("started", time.time()))
    t_last = max((c["t_end"] for c in sent_all), default=t_first)
    started = meta.get("started", t_first)
    finished = meta.get("finished") or max([t_last] + [C["status"].get("now", 0) for C in courses])
    gen_window = max(1.0, t_last - t_first)
    all_out = sum(c["output_tokens"] for c in sent_all) or 1

    A = {"started": started, "finished": finished, "wall_s": finished - started, "gen_window_s": gen_window,
         "server_start_s": max(0.0, t_first - started), "courses": []}
    for C in courses:
        calls = C["calls"]
        sent = [c for c in calls if not c.get("cached")]
        rep = C["report"]
        lect = rep.get("lectures") or []
        video_s = sum(l["duration_s"] for l in lect) or C["status"].get("video_s", 0)
        st = C["status"]
        c_start = st.get("t0") or (min((c["t_start"] for c in sent), default=started))
        c_end = (st.get("now") if st.get("state") in ("done", "failed") else None) or \
            max((c["t_end"] for c in sent), default=c_start)
        # per request type: (stage, prompt id)
        types = defaultdict(lambda: {"sent": 0, "hits": 0, "retries": 0, "length": 0, "in": 0, "out": 0,
                                     "lat": [], "think_chars": 0, "answer_chars": 0})
        for c in calls:
            t = types[(c["stage"], c.get("prompt_id", "?"))]
            if c.get("cached"):
                t["hits"] += 1
                continue
            t["sent"] += 1
            t["retries"] += c.get("attempt", 0) > 0
            t["length"] += c.get("finish") == "length"
            t["in"] += c["input_tokens"]
            t["out"] += c["output_tokens"]
            t["lat"].append(c["latency_s"])
            t["think_chars"] += c.get("reasoning_chars", 0)
            t["answer_chars"] += c.get("answer_chars", 0)
        # per lecture
        per_l = defaultdict(lambda: {"sent": 0, "in": 0, "out": 0})
        for c in sent:
            p = per_l[c["lecture_id"]]
            p["sent"] += 1
            p["in"] += c["input_tokens"]
            p["out"] += c["output_tokens"]
        lectures = []
        for l in lect:
            p = per_l.get(l["id"], {"sent": 0, "in": 0, "out": 0})
            gpu_s = gen_window * p["out"] / all_out
            lectures.append({**l, **p, "gpu_s": gpu_s,
                             "gpu_min_per_video_h": (gpu_s / 60) / (l["duration_s"] / 3600) if l["duration_s"] else 0})
        course_level = per_l.get("_course", {"sent": 0, "in": 0, "out": 0})
        steps = rep.get("steps") or []
        out_tok = sum(c["output_tokens"] for c in sent)
        think = sum(c.get("reasoning_chars", 0) for c in sent)
        ans = sum(c.get("answer_chars", 0) for c in sent)
        A["courses"].append({
            "id": C["id"], "short": C["short"], "title": C["title"], "dir": C["dir"], "exit": C["exit"],
            "state": st.get("state", "?"), "lectures": lectures, "n_lectures": len(lect) or st.get("lectures", 0),
            "video_s": video_s, "wall_s": c_end - c_start, "t0": c_start, "steps": steps,
            "sent": len(sent), "hits": len(calls) - len(sent), "retries": sum(c.get("attempt", 0) > 0 for c in sent),
            "length": sum(c.get("finish") == "length" for c in sent),
            "in": sum(c["input_tokens"] for c in sent), "out": out_tok,
            "think_share": think / (think + ans) if think + ans else 0,
            "gpu_s": gen_window * out_tok / all_out, "types": types, "course_level": course_level,
            "report": rep})
    # server
    S = {}
    if srv:
        # averages over the generation window (server start excluded); the whole series if nothing finished yet
        inwin = [r for r in srv if t_first <= r["t"] <= t_last] if t_last > t_first else []
        inwin = inwin or srv
        util = [r["gpu_util"] for r in inwin if "gpu_util" in r]
        S["gpu_util_mean"] = statistics.mean(util) if util else 0
        S["gpu_util_busy"] = sum(u >= 90 for u in util) / len(util) if util else 0
        S["mem_peak_gb"] = max((r.get("mem_used_mib", 0) for r in srv), default=0) / 1024
        S["mem_total_gb"] = max((r.get("mem_total_mib", 0) for r in srv), default=0) / 1024
        pw = [r for r in srv if "power_w" in r]
        pw_in = [r["power_w"] for r in inwin if "power_w" in r]
        S["power_mean"] = statistics.mean(pw_in) if pw_in else 0
        S["energy_kwh"] = sum((b["t"] - a["t"]) * a["power_w"] for a, b in zip(pw, pw[1:])) / 3.6e6
        rs = [r for r in srv if "running" in r]
        if rs:
            win = [r for r in inwin if "running" in r] or rs
            S["running_mean"] = statistics.mean(r["running"] for r in win)
            S["running_peak"] = max(r["running"] for r in rs)
            S["waiting_peak"] = max(r.get("waiting", 0) for r in rs)
            S["kv_mean"] = statistics.mean(r.get("kv_pct", 0) for r in win)
            S["kv_peak"] = max(r.get("kv_pct", 0) for r in rs)
            last, first = rs[-1], rs[0]
            S["gen_tokens"] = last.get("gen_tokens", 0) - first.get("gen_tokens", 0)
            S["prompt_tokens"] = last.get("prompt_tokens", 0) - first.get("prompt_tokens", 0)
            q = last.get("prefix_queries", 0) - first.get("prefix_queries", 0)
            S["prefix_hit"] = (last.get("prefix_hits", 0) - first.get("prefix_hits", 0)) / q if q else 0
            dt = last.get("spec_draft_tokens", 0) - first.get("spec_draft_tokens", 0)
            dr = last.get("spec_drafts", 0) - first.get("spec_drafts", 0)
            ac = last.get("spec_accepted", 0) - first.get("spec_accepted", 0)
            S["spec_accept"] = ac / dt if dt else 0
            S["spec_tokens_per_step"] = 1 + ac / dr if dr else 0
            S["preemptions"] = last.get("preemptions", 0) - first.get("preemptions", 0)
        # output tokens/s per sample interval
        S["series"] = []
        for a, b in zip(srv, srv[1:]):
            if "gen_tokens" in a and "gen_tokens" in b and b["t"] > a["t"]:
                S["series"].append((b["t"], max(0.0, (b["gen_tokens"] - a["gen_tokens"]) / (b["t"] - a["t"]))))
    A["server"] = S
    A["sent"] = len(sent_all)
    A["out"] = sum(c["output_tokens"] for c in sent_all)
    A["in"] = sum(c["input_tokens"] for c in sent_all)
    A["lectures"] = sum(c["n_lectures"] for c in A["courses"])
    A["video_s"] = sum(c["video_s"] for c in A["courses"])
    return A


# ------------------------------------------------------------------------------------------------ charts
def charts(D: dict, A: dict, out: Path) -> list[tuple[str, str]]:
    out.mkdir(exist_ok=True)
    made = []
    srv, t0 = D["server"], A["started"]
    color = {c["id"]: SERIES[i % len(SERIES)] for i, c in enumerate(A["courses"])}

    # 1. timeline: small multiples on one time axis, one measure per panel (no dual axes)
    if srv:
        mins = lambda t: (t - t0) / 60  # noqa: E731
        panels = [("Output tokens per second", [(mins(t), v) for t, v in A["server"].get("series", [])], SERIES[0]),
                  ("GPU power (W): how hard the GPU works (utilization reads 100% even with one request)",
                   [(mins(r["t"]), r["power_w"]) for r in srv if "power_w" in r], SERIES[0]),
                  ("KV cache in use (%)", [(mins(r["t"]), 100 * r["kv_pct"]) for r in srv if "kv_pct" in r], SERIES[0])]
        f, axes = fig(11, 9.2, 4, 1, sharex=True)
        for ax, (title, pts, col) in zip(axes, panels):
            style(ax)
            if pts:
                xs, ys = zip(*pts)
                ax.plot(xs, ys, color=col, linewidth=1.6)
            ax.set_title(title, loc="left", color=INK2, fontsize=10)
            ax.set_ylim(bottom=0)
        ax = axes[3]
        style(ax, xlabel="minutes since the run started")
        rs = [r for r in srv if "running" in r]
        if rs:
            ax.plot([mins(r["t"]) for r in rs], [r["running"] for r in rs], color=SERIES[0], linewidth=1.6,
                    label="running")
            ax.plot([mins(r["t"]) for r in rs], [r.get("waiting", 0) for r in rs], color=SERIES[1], linewidth=1.6,
                    label="waiting")
            ax.legend(frameon=False, fontsize=9, labelcolor=INK2, loc="upper right", ncol=2)
        ax.set_title("Requests on the server", loc="left", color=INK2, fontsize=10)
        ax.set_ylim(bottom=0)
        save(f, out / "timeline.png", "GPU and server over the run")
        made.append(("timeline.png", "GPU and server over the run"))

    # 2. steps: when each step ran, per course (Gantt)
    cs = [c for c in A["courses"] if c["steps"]]
    if cs:
        h = sum(len(c["steps"]) for c in cs) * 0.28 + 1.2 * len(cs)
        f, axes = fig(11, h, len(cs), 1, sharex=True, squeeze=False,
                      gridspec_kw={"height_ratios": [len(c["steps"]) for c in cs]})
        for ax, c in zip(axes[:, 0], cs):
            style(ax, xlabel="minutes since the run started" if c is cs[-1] else "")
            ax.grid(axis="y", visible=False)
            for i, s in enumerate(c["steps"]):
                ax.barh(i, (s["end"] - s["start"]) / 60, left=(s["start"] - t0) / 60, height=0.62,
                        color=color[c["id"]], linewidth=0)
                ax.text((s["end"] - t0) / 60, i, "  " + fmt_t(s["wall_s"]), va="center", fontsize=8, color=INK2)
            ax.set_yticks(range(len(c["steps"])), [s["stage"].replace("v2_", "") for s in c["steps"]])
            ax.invert_yaxis()
            ax.set_title(c["short"], loc="left", color=INK, fontsize=10, fontweight="bold")
        save(f, out / "steps.png", "When each step ran")
        made.append(("steps.png", "When each step ran"))

    # 3-4. requests and output tokens by request type (grouped bars, one color per course)
    for key, fname, title, scale, unit in [("sent", "requests_by_type.png", "Requests sent, by type", 1, "requests"),
                                           ("out", "tokens_by_type.png", "Output tokens (thinking + answer), by type",
                                            1e6, "million output tokens")]:
        tot = defaultdict(float)
        for c in A["courses"]:
            for (stg, pid), t in c["types"].items():
                tot[pid] += t[key]
        names = [k for k, v in sorted(tot.items(), key=lambda kv: -kv[1]) if v > 0]
        if not names:
            continue
        f, ax = fig(11, 0.32 * len(names) + 1.4)
        style(ax, xlabel=unit)
        ax.grid(axis="y", visible=False)
        k = len(A["courses"])
        bh = 0.8 / k
        for j, c in enumerate(A["courses"]):
            vals = defaultdict(float)
            for (stg, pid), t in c["types"].items():
                vals[pid] += t[key]
            ys = [i - 0.4 + bh * (j + 0.5) for i in range(len(names))]
            ax.barh(ys, [vals[nm] / scale for nm in names], height=bh * 0.9, color=color[c["id"]], linewidth=0,
                    label=c["short"])
        ax.set_yticks(range(len(names)), names)
        ax.invert_yaxis()
        if k > 1:
            ax.legend(frameon=False, fontsize=9, labelcolor=INK2, loc="lower right")
        save(f, out / fname, title)
        made.append((fname, title))

    # 5. GPU time per lecture (one panel per course)
    cs = [c for c in A["courses"] if c["lectures"]]
    if cs:
        f, axes = fig(11, 2.6 * len(cs) + 0.6, len(cs), 1, squeeze=False)
        for ax, c in zip(axes[:, 0], cs):
            style(ax, ylabel="GPU minutes")
            ax.grid(axis="x", visible=False)
            ls = c["lectures"]
            ax.bar(range(len(ls)), [l["gpu_s"] / 60 for l in ls], width=0.7, color=color[c["id"]], linewidth=0)
            step = max(1, len(ls) // 32)
            ax.set_xticks(range(0, len(ls), step), [l["id"] for l in ls][::step], rotation=90 if len(ls) > 16 else 0,
                          fontsize=8)
            mean = statistics.mean(l["gpu_s"] / 60 for l in ls)
            ax.axhline(mean, color=MUTED, linewidth=1)
            ax.text(len(ls) - 0.5, mean, f"mean {mean:.1f} min ", ha="right", va="bottom", fontsize=8, color=INK2)
            ax.set_title(c["short"], loc="left", color=INK, fontsize=10, fontweight="bold")
        save(f, out / "per_lecture.png", "GPU time per lecture (run time split by output tokens)")
        made.append(("per_lecture.png", "GPU time per lecture"))
    return made


# ------------------------------------------------------------------------------------------------ report
def write(D: dict, A: dict, made: list) -> str:
    meta, run, S = D["meta"], D["run"], A["server"]
    cfg = {}
    try:
        import tomllib
        cf = next((f for f in (run / "config.toml", run / "lir2_config.toml") if f.exists()), None)   # run_v2.sh saves config.toml
        cfg = tomllib.loads(cf.read_text()) if cf else {}
    except Exception:
        pass
    g = cfg.get("generator", {})
    e = cfg.get("engine", {})
    roles: dict[str, list[str]] = {}                 # model -> the roles that use it (they share one server)
    for r in ("generator", "verifier", "judge"):
        if cfg.get(r, {}).get("model"):
            roles.setdefault(cfg[r]["model"], []).append(r)
    num = lambda x: f"{x:,}" if isinstance(x, (int, float)) else "?"
    state = "finished" if meta.get("finished") else "in progress (partial numbers)"
    L = [f"# LIR v2 run `{meta.get('name', run.name)}`", "",
         f"{', '.join(c['title'] for c in A['courses'])}: {A['lectures']} lectures, "
         f"{A['video_s'] / 3600:.1f} h of video. Run {state}, "
         f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(A['started']))} to "
         f"{time.strftime('%H:%M', time.localtime(A['finished']))}.", ""]
    if meta.get("note"):
        L += [f"> Note: {meta['note']}.", ""]
    for c in A["courses"]:
        if c["exit"] not in (None, "0"):
            L += [f"> **{c['title']} failed** (exit {c['exit']}): see `{c['dir'].name}/stderr.log`.", ""]

    L += ["## Summary", ""]
    rows = [["Wall time", fmt_t(A["wall_s"]), "from launch to the last step, server start included"],
            ["Server start", fmt_t(A["server_start_s"]), "model load and kernel compile"],
            ["Time per lecture", fmt_t(A["gen_window_s"] / max(1, A["lectures"])),
             f"generation time / {A['lectures']} lectures, both courses sharing the GPU"],
            ["Time per hour of video",
             fmt_t(A["gen_window_s"] / (A["video_s"] / 3600)) if A["video_s"] else "not known yet", ""],
            ["Requests sent", n(A["sent"]), f"{sum(c['retries'] for c in A['courses']):,} were retries"],
            ["Input tokens", f"{A['in'] / 1e6:,.1f} M", ""],
            ["Output tokens", f"{A['out'] / 1e6:,.1f} M", "thinking + answer"],
            ["Output tokens per second", n(A["out"] / A["gen_window_s"]), "average over the generation time"]]
    if S:
        rows += [["GPU utilization", f"{S['gpu_util_mean']:.0f}%",
                  "mean while generating (nvidia-smi: busy at all, not how much; see power)"],
                 ["GPU memory", f"{S['mem_peak_gb']:.0f} of {S['mem_total_gb']:.0f} GB", "peak"],
                 ["Power", f"{S['power_mean']:.0f} W", f"{S['energy_kwh']:.2f} kWh in all"]]
    L += [table(["", "Value", ""], rows, "lrl"), ""]

    L += ["## Per course", ""]
    rows = []
    for c in A["courses"]:
        rows.append([c["title"], c["n_lectures"], f"{c['video_s'] / 3600:.1f} h", fmt_t(c["wall_s"]),
                     fmt_t(c["gpu_s"] / max(1, c["n_lectures"])), n(c["sent"]), n(c["retries"]), n(c["length"]),
                     f"{c['in'] / 1e6:.1f} M", f"{c['out'] / 1e6:.1f} M", f"{c['think_share'] * 100:.0f}%"])
    L += [table(["Course", "Lectures", "Video", "Wall time", "GPU time per lecture", "Requests", "Retries",
                 "Cut at length", "Input tokens", "Output tokens", "Thinking share"], rows), "",
          "Courses ran one after another, each with the whole GPU. GPU time per lecture is the "
          "generation time split by each lecture's share of all output tokens. Thinking share is estimated from "
          "the characters of thinking and answer text.", ""]

    L += ["## Setup", "",
          table(["", ""], [
              ["GPU", meta.get("gpu", "?")],
              *[[f"Model ({', '.join(rs)})", f"{m} on {cfg[rs[0]].get('engine', '?')} {meta.get('vllm', '')}, "
                 f"{cfg[rs[0]].get('slots', '?')} requests at once, GPU memory "
                 f"{cfg[rs[0]].get('gpu_memory_utilization', e.get('gpu_memory_utilization', '?'))}"]
                for m, rs in roles.items()],
              ["Context", f"{num(g.get('max_model_len'))} tokens; output cap: "
                          f"{'none' if not g.get('max_tokens') else g.get('max_tokens')}"],
              ["Sampling", ", ".join(f"{k} {v}" for k, v in (g.get("sampling") or {}).items())],
              ["Engine", f"prefix caching "
                         f"{'on' if e.get('prefix_caching') else 'off'}"
                         + (f", {' '.join(e['vllm_args'])}" if e.get('vllm_args') else "")
                         + (", priority scheduling" if e.get('priority') else "")],
              ["Code", f"commit {meta.get('git_commit', '?')}{' + local changes' if meta.get('git_dirty') else ''}"],
              ["Lectures", meta.get("only", "all")]], "ll"), ""]

    for fname, title in made:
        L += [f"![{title}](charts/{fname})", ""]

    if S:
        L += ["## Server", "", table(["", "Value"], [
            ["Requests running", f"{S.get('running_mean', 0):.0f} on average, {S.get('running_peak', 0):.0f} at most"],
            ["Requests waiting", f"{S.get('waiting_peak', 0):.0f} at most"],
            ["KV cache in use", f"{S.get('kv_mean', 0) * 100:.0f}% on average, {S.get('kv_peak', 0) * 100:.0f}% at most"],
            ["Prefix cache", f"{S.get('prefix_hit', 0) * 100:.0f}% of prompt tokens reused"],
            ["MTP drafts", f"{S.get('spec_accept', 0) * 100:.0f}% of draft tokens accepted, "
                           f"{S.get('spec_tokens_per_step', 0):.2f} tokens per step"],
            ["Preemptions", n(S.get("preemptions", 0))],
            ["Tokens counted by the server", f"{S.get('prompt_tokens', 0) / 1e6:.1f} M prompt, "
                                             f"{S.get('gen_tokens', 0) / 1e6:.1f} M generated"]], "ll"), ""]

    for c in A["courses"]:
        L += [f"## {c['title']}", "", "### Time per step", ""]
        tot = sum(s["wall_s"] for s in c["steps"]) or 1
        L += [table(["Step", "Wall time", "Share"],
                    [[s["stage"].replace("v2_", ""), fmt_t(s["wall_s"]), f"{s['wall_s'] / tot * 100:.0f}%"]
                     for s in c["steps"]]), ""]
        L += ["### Requests by type", ""]
        rows = []
        for (stg, pid), t in sorted(c["types"].items(), key=lambda kv: -kv[1]["out"]):
            if not t["sent"] and not t["hits"]:
                continue
            ts = t["think_chars"] + t["answer_chars"]
            rows.append([f"{pid}", stg.replace("v2_", ""), n(t["sent"]), n(t["retries"]), n(t["length"]), n(t["hits"]),
                         n(t["in"]), n(t["out"]), n(t["out"] / t["sent"]) if t["sent"] else "",
                         f"{t['think_chars'] / ts * 100:.0f}%" if ts else "",
                         f"{pct(t['lat'], 0.5):.0f} / {pct(t['lat'], 0.95):.0f}"])
        L += [table(["Type (prompt)", "Step", "Requests", "Retries", "Cut at length", "Cache hits", "Input tokens",
                     "Output tokens", "Output per request", "Thinking", "Latency p50 / p95 (s)"], rows, "llrrrrrrrrr"),
              "", "Latency includes time waiting in the server's queue.", ""]
        L += ["### Per lecture", ""]
        rows = [[l["id"], l["title"][:48], f"{l['duration_s'] / 60:.0f}", n(l["sent"]), f"{l['out'] / 1e3:,.0f} k",
                 f"{l['gpu_s'] / 60:.1f}", f"{l['gpu_min_per_video_h']:.1f}", l["parts"], l["key_points"], l["terms"],
                 l["concepts_introduced"], l.get("quiz_items", ""), l.get("open_questions", ""), l["flags"]]
                for l in c["lectures"]]
        cl = c["course_level"]
        if cl["sent"]:
            rows.append(["course", "course goals and other course-level requests", "", n(cl["sent"]),
                         f"{cl['out'] / 1e3:,.0f} k", f"{A['gen_window_s'] * cl['out'] / max(1, A['out']) / 60:.1f}",
                         "", "", "", "", "", "", "", ""])
        L += [table(["Lecture", "Title", "Video (min)", "Requests", "Output tokens", "GPU min", "GPU min per video h",
                     "Parts", "Key points", "Terms", "New concepts", "Quiz items", "Open questions", "Flags"],
                    rows, "llrrrrrrrrrrrr"), ""]
        rep = c["report"]
        if rep:
            lect = c["lectures"]
            s = lambda k: sum(l.get(k, 0) or 0 for l in lect)  # noqa: E731
            rel = rep.get("edges_by_relation", {})
            L += ["### What was built", "", table(["", "Count"], [
                ["Parts", n(s("parts"))], ["Key points", n(s("key_points"))], ["Key-term occurrences", n(s("terms"))],
                ["Concepts", n(rep.get("concepts", 0))],
                ["Links", f"{sum(rel.values()):,} (" + ", ".join(f"{k} {v}" for k, v in sorted(rel.items())) + ")"],
                ["Recall items", n(s("recall_items"))], ["Quiz items", n(s("quiz_items"))], ["Recaps", n(s("recaps"))],
                ["Check-yourself questions", n(s("review_questions"))],
                ["Spaced-review candidates", n(s("spaced_review"))], ["Concept-map nodes", n(s("concept_map_nodes"))],
                ["Open questions", n(s("open_questions"))], ["Flags", n(s("flags"))]], "lr"), ""]
            dec = rep.get("decisions", {})
            if dec:
                L += ["<details><summary>Every decision by step</summary>", "",
                      table(["Step: decision", "Count"], [[k, n(v)] for k, v in sorted(dec.items())], "lr"), "",
                      "</details>", ""]
        L += [f"Files: `{c['dir'].relative_to(run)}/lir/` (the LIR), `{c['dir'].relative_to(run)}/build/` "
              "(cache, step outputs, `calls.jsonl` with every request, `report.md`).", ""]
    return "\n".join(L)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    run = Path(sys.argv[1]).resolve()
    D = load(run)
    if not D["courses"]:
        sys.exit(f"no course runs in {run}")
    A = analyse(D)
    made = charts(D, A, run / "charts")
    (run / "report.md").write_text(write(D, A, made), encoding="utf-8")
    js = {k: v for k, v in A.items() if k != "courses"}
    js["courses"] = [{k: (v if k != "types" else {f"{a}|{b}": {**t, "lat": None} for (a, b), t in v.items()})
                      for k, v in c.items() if k not in ("dir", "report")} for c in A["courses"]]
    (run / "report.json").write_text(json.dumps(js, indent=1, default=str), encoding="utf-8")
    print(f"report: {run / 'report.md'} ({len(made)} charts in {run / 'charts'})")


if __name__ == "__main__":
    main()
