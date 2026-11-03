#!/usr/bin/env python3
"""GPU and vLLM sampler, and the live dashboard for a LIR v2 run (started by run_v2.sh).

    python3 run_monitor.py sample runs/<name>     # every 5 s: GPU + vLLM metrics -> runs/<name>/server.csv
    python3 run_monitor.py dash   runs/<name>     # live dashboard: GPU, server, each course's progress

The dashboard only reads files (server.csv, <course>/build/status.json), so closing it does not affect the run.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
VLLM_URLS = ["http://127.0.0.1:8091", "http://127.0.0.1:8097"]   # generator, verifier/judge (pipeline/config.py PORTS)
EVERY_S = 5.0

GPU_FIELDS = ["utilization.gpu", "memory.used", "memory.total", "power.draw", "temperature.gpu", "clocks.sm"]
# vLLM Prometheus metrics (summed over labels); counters become rates in the report
METRICS = {
    "running": ["vllm:num_requests_running"],
    "waiting": ["vllm:num_requests_waiting"],
    "kv_pct": ["vllm:kv_cache_usage_perc", "vllm:gpu_cache_usage_perc"],
    "prompt_tokens": ["vllm:prompt_tokens_total"],
    "gen_tokens": ["vllm:generation_tokens_total"],
    "prefix_queries": ["vllm:prefix_cache_queries_total", "vllm:gpu_prefix_cache_queries_total"],
    "prefix_hits": ["vllm:prefix_cache_hits_total", "vllm:gpu_prefix_cache_hits_total"],
    "preemptions": ["vllm:num_preemptions_total"],
    "spec_drafts": ["vllm:spec_decode_num_drafts_total"],
    "spec_draft_tokens": ["vllm:spec_decode_num_draft_tokens_total"],
    "spec_accepted": ["vllm:spec_decode_num_accepted_tokens_total"],
    "requests_done": ["vllm:request_success_total"],
}
COLUMNS = ["t", "gpu_util", "mem_used_mib", "mem_total_mib", "power_w", "temp_c", "sm_mhz", *METRICS]


def gpu() -> dict:
    try:
        out = subprocess.run(["nvidia-smi", f"--query-gpu={','.join(GPU_FIELDS)}", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10).stdout.splitlines()[0]
        v = [float(x) for x in out.split(",")]
        return dict(zip(["gpu_util", "mem_used_mib", "mem_total_mib", "power_w", "temp_c", "sm_mhz"], v))
    except Exception:
        return {}


def _metrics(url: str) -> dict:
    try:
        with urllib.request.urlopen(url + "/metrics", timeout=5) as r:
            text = r.read().decode()
    except Exception:
        return {}
    sums: dict[str, float] = {}
    for line in text.splitlines():
        if not line or line[0] == "#":
            continue
        name = line.split("{", 1)[0].split(" ", 1)[0]
        try:
            sums[name] = sums.get(name, 0.0) + float(line.rsplit(" ", 1)[1])
        except ValueError:
            pass
    out = {}
    for k, names in METRICS.items():
        for n in names:
            if n in sums:
                out[k] = sums[n]
                break
    return out


def vllm() -> dict:
    """Every running server's metrics, added up (KV cache use: the fuller server)."""
    out: dict[str, float] = {}
    for url in VLLM_URLS:
        for k, v in _metrics(url).items():
            out[k] = max(out.get(k, 0.0), v) if k == "kv_pct" else out.get(k, 0.0) + v
    return out


def sample(run: Path):
    path = run / "server.csv"
    new = not path.exists()
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, COLUMNS)
        if new:
            w.writeheader()
        while not (run / "STOP_SAMPLER").exists():
            t0 = time.time()
            w.writerow({"t": round(t0, 1), **gpu(), **vllm()})
            f.flush()
            time.sleep(max(0.0, EVERY_S - (time.time() - t0)))


# ------------------------------------------------------------------------------------------------ dashboard
def read_rows(path: Path, since: float = 0) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            try:
                d = {k: float(v) for k, v in r.items() if v not in ("", None)}
            except ValueError:
                continue
            if d.get("t", 0) >= since:
                rows.append(d)
    return rows


def rate(rows: list[dict], key: str, window_s: float) -> float | None:
    rs = [r for r in rows if key in r]
    if len(rs) < 2:
        return None
    end = rs[-1]
    start = next((r for r in rs if r["t"] >= end["t"] - window_s), rs[0])
    dt = end["t"] - start["t"]
    return (end[key] - start[key]) / dt if dt > 0 else None


def spark(vals: list[float], width: int = 60) -> str:
    bars = "▁▂▃▄▅▆▇█"
    if not vals:
        return ""
    vals = vals[-width:]
    hi = max(vals) or 1.0
    return "".join(bars[min(7, int(v / hi * 7.999))] for v in vals)


def hms(s: float) -> str:
    s = int(max(0, s))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"


# the v2 steps in run order (generate_lir2.py STAGES); status.json carries the list too
STEPS = ["0 · sentences", "1 · parts", "2 · objective, key points", "3a · term candidates",
         "judge · objectives, key points", "3b-e · key terms", "4 · registry", "7 · goals", "5 · facets",
         "judge · goals, facets", "6 · edges", "8 · lecture map", "9 · activities", "judge · activities",
         "concept maps, review, scorer", "assemble"]


def mins(s: float) -> str:
    return f"{s / 60:.1f}m" if s >= 60 else f"{s:.0f}s"


class Tail:
    """Reads the lines appended to a JSONL file since the last call."""

    def __init__(self, path: Path):
        self.path, self.pos, self.buf = path, 0, b""

    def new(self) -> list[dict]:
        if not self.path.exists():
            return []
        with open(self.path, "rb") as f:
            f.seek(self.pos)
            data = f.read()
            self.pos = f.tell()
        lines = (self.buf + data).split(b"\n")
        self.buf = lines.pop()
        out = []
        for line in lines:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return out


def last_record(path: Path, max_bytes: int = 2_000_000) -> dict | None:
    """The last complete line of a JSONL file (answer cache lines carry the thinking, so they can be long)."""
    try:
        size = path.stat().st_size
        with open(path, "rb") as f:
            f.seek(max(0, size - max_bytes))
            lines = f.read().rstrip(b"\n").split(b"\n")
        return json.loads(lines[-1])
    except Exception:
        return None


def clip(s: str, n: int) -> str:
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[:n - 1] + "…"


def dash(run: Path):
    from collections import defaultdict, deque

    from rich import box
    from rich.console import Group
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress_bar import ProgressBar
    from rich.table import Table
    from rich.text import Text

    from rich.console import Console

    DIM, LBL = "grey35", "grey58"
    con = Console()
    meta = {}
    tails: dict[Path, Tail] = {}
    types = defaultdict(lambda: {"sent": 0, "hits": 0, "retries": 0, "length": 0, "out": 0, "lat": 0.0,
                                 "think": 0, "answer": 0, "last": 0.0})
    recent: deque = deque(maxlen=7)

    def bar(frac: float, width: int = 28, style: str = "cyan") -> ProgressBar:
        return ProgressBar(total=100, completed=max(0.0, min(100.0, frac * 100)), width=width, complete_style=style,
                           style="grey23")

    def panel(body, title: str, color: str) -> Panel:
        return Panel(body, title=f"[{color}]{title}[/]", title_align="left", border_style=DIM, box=box.ROUNDED,
                     padding=(0, 1))

    def short(cid: str) -> str:
        return {"nptel-virtual-and-augmented-reality": "VR", "mit-6-7960-deep-learning": "DL"}.get(cid, cid[:10])

    def ingest():
        for p in run.glob("*/build/calls.jsonl"):
            t = tails.setdefault(p, Tail(p))
            cid = p.parent.parent.name
            for r in t.new():
                k = types[(short(cid), r.get("stage", "?").replace("v2_", ""), r.get("prompt_id", "?"))]
                if r.get("cached"):
                    k["hits"] += 1
                    continue
                k["sent"] += 1
                k["retries"] += r.get("attempt", 0) > 0
                k["length"] += r.get("finish") == "length"
                k["out"] += r["output_tokens"]
                k["lat"] += r["latency_s"]
                k["think"] += r.get("reasoning_chars", 0)
                k["answer"] += r.get("answer_chars", 0)
                k["last"] = r["t_end"]
                recent.append((short(cid), r))

    def latest_answer():
        best = None
        for p in run.glob("*/build/cache/*.jsonl"):
            m = p.stat().st_mtime
            if best is None or m > best[0]:
                best = (m, p)
        if not best:
            return None
        r = last_record(best[1])
        return (best[1].parent.parent.parent.name, best[1].stem, best[0], r) if r else None

    def render():
        nonlocal meta
        if (run / "meta.json").exists():
            meta = json.loads((run / "meta.json").read_text())
        t_run = meta.get("started", time.time())
        ingest()
        rows = read_rows(run / "server.csv", since=t_run)
        last = rows[-1] if rows else {}
        now = time.time()
        done = (run / "DONE").exists()

        head = Table.grid(expand=True)
        head.add_column(); head.add_column(justify="right")
        state = "[green]finished[/]" if done else "[cyan]running[/]"
        head.add_row(f"[bold]LIR v2 run[/] [cyan]{run.name}[/]  {state}  [{LBL}]{meta.get('gpu', '').split(',')[0]}[/]",
                     f"[{LBL}]elapsed[/] [bold]{hms((meta.get('finished') or now) - t_run)}[/]  [{LBL}]started "
                     f"{time.strftime('%H:%M', time.localtime(t_run))}[/]")

        # GPU
        g = Table.grid(padding=(0, 1))
        g.add_column(style=LBL, no_wrap=True); g.add_column(no_wrap=True); g.add_column(no_wrap=True)
        util = last.get("gpu_util", 0)
        utils = [r["gpu_util"] for r in rows if "gpu_util" in r]
        avg_util = sum(utils) / len(utils) if utils else 0
        mem, memt = last.get("mem_used_mib", 0) / 1024, last.get("mem_total_mib", 1) / 1024
        g.add_row("utilization", bar(util / 100, style="green4"), f"[bold]{util:.0f}%[/] [{LBL}]avg {avg_util:.0f}%[/]")
        g.add_row("power", bar(last.get("power_w", 0) / 600, style="dark_orange3"),
                  f"{last.get('power_w', 0):.0f} W [{LBL}]of 600[/]")
        g.add_row("memory", bar(mem / memt if memt else 0, style="steel_blue"), f"{mem:.0f} / {memt:.0f} GB")
        g.add_row("temp · clock", "", f"{last.get('temp_c', 0):.0f} °C · {last.get('sm_mhz', 0):.0f} MHz")
        g.add_row("power, 10 min", Text(spark([r.get("power_w", 0) for r in rows][-120:], 28), style="dark_orange3"), "")

        # server
        s = Table.grid(padding=(0, 1))
        s.add_column(style=LBL, no_wrap=True); s.add_column(no_wrap=True); s.add_column(no_wrap=True)
        if "running" not in last:
            s.add_row("vLLM", "[yellow]not reachable (starting, or stopped)[/]", "")
        else:
            gen = rate(rows, "gen_tokens", 30) or 0
            gen_all = rate(rows, "gen_tokens", 1e9) or 0
            pr = rate(rows, "prompt_tokens", 30) or 0
            gens = [max(0.0, (b["gen_tokens"] - a["gen_tokens"]) / (b["t"] - a["t"])) for a, b in zip(rows, rows[1:])
                    if "gen_tokens" in a and "gen_tokens" in b and b["t"] > a["t"]]
            ph = (last.get("prefix_hits", 0) / last["prefix_queries"]) if last.get("prefix_queries") else 0
            acc = (last.get("spec_accepted", 0) / last["spec_draft_tokens"]) if last.get("spec_draft_tokens") else 0
            mal = (1 + last.get("spec_accepted", 0) / last["spec_drafts"]) if last.get("spec_drafts") else 0
            per_req = gen / last["running"] if last["running"] else 0
            s.add_row("requests", bar(last["running"] / 128, style="medium_purple3"),
                      f"[bold]{last['running']:.0f}[/] running · {last.get('waiting', 0):.0f} waiting "
                      f"[{LBL}]· {last.get('requests_done', 0):,.0f} done[/]")
            s.add_row("output tok/s", Text(spark(gens[-120:], 28), style="green4"),
                      f"[bold green]{gen:,.0f}[/] now · {gen_all:,.0f} avg [{LBL}]· {per_req:.0f} per request[/]")
            s.add_row("KV cache", bar(last.get("kv_pct", 0), style="medium_purple3"),
                      f"{last.get('kv_pct', 0) * 100:.0f}% [{LBL}]· prompt {pr:,.0f} tok/s[/]")
            s.add_row("prefix cache", "", f"{ph * 100:.0f}% of prompt tokens reused")
            s.add_row("MTP drafts", "", f"{acc * 100:.0f}% accepted · {mal:.2f} tokens/step "
                                         f"[{LBL}]· {last.get('preemptions', 0):,.0f} preemptions[/]")
        top = Table.grid(expand=True, padding=(0, 1))
        top.add_column(ratio=2); top.add_column(ratio=3)
        top.add_row(panel(g, "GPU", "green4"), panel(s, "vLLM server", "medium_purple3"))

        # courses
        c = Table(expand=True, header_style=f"bold {LBL}", box=box.SIMPLE_HEAD, border_style=DIM, pad_edge=False,
                  show_edge=False)
        for col, j in [("Course", "left"), ("Step", "left"), ("Batch", "left"), ("", "left"), ("Overall", "left"),
                       ("ETA (rough)", "right"), ("Requests", "right"), ("Out tokens", "right"), ("Time", "right")]:
            c.add_column(col, justify=j, no_wrap=True)
        warns, prog = [], []
        for st_path in sorted(run.glob("*/build/status.json")):
            try:
                st = json.loads(st_path.read_text())
            except Exception:
                continue
            code = st_path.parent.parent / "exit_code"
            state = st["state"]
            if code.exists() and code.read_text().split()[-1] != "0":
                state = "failed"
            label = {"done": "[green]✓ done[/]", "failed": "[bold red]✗ failed[/]"}.get(state, "")
            frac_b = st["batch_done"] / st["batch_total"] if st["batch_total"] else 0
            elapsed = (st["now"] if state != "running" else now) - st["t0"]
            n_done = len(st.get("stages_done", []))
            c.add_row(f"[bold]{short(st['course_id'])}[/] [{LBL}]{st['lectures']} lect.[/]",
                      label or f"{st['stage']} [{LBL}]({n_done + 1}/16)[/]",
                      f"{st['batch'][:34]} [{LBL}]{st['batch_done']:,.0f}/{st['batch_total']:,.0f}[/]",
                      bar(frac_b, 14, "green4"), bar(st["overall_pct"] / 100, 14, "steel_blue"),
                      "" if state != "running" else st["eta"], f"{st['calls']:,}",
                      f"{st['output_tokens'] / 1e6:,.2f} M", hms(elapsed))
            steps = st.get("all_stages") or STEPS
            done_w = dict((k, w) for k, w in st.get("stages_done", []))
            cur_el = (now if state == "running" else st["now"]) - st["t0"] - sum(done_w.values())
            chips = []
            for lab in steps:
                if lab in done_w:
                    chips.append(f"[green4]✓ {lab}[/] [{LBL}]{mins(done_w[lab])}[/]")
                elif lab == st["stage"] and state == "running":
                    chips.append(f"[bold cyan]▶ {lab} {mins(cur_el)}[/]")
                elif state == "failed" and lab == st["stage"]:
                    chips.append(f"[bold red]✗ {lab}[/]")
                else:
                    chips.append(f"[grey42]○ {lab}[/]")
            left = sum(1 for lab in steps if lab not in done_w)
            prog.append(Text.from_markup(
                f"[bold]{short(st['course_id'])}[/] [{LBL}]{len(done_w)}/{len(steps)} steps done in "
                f"{mins(sum(done_w.values()))}, {left} left:[/]  " + "  ".join(chips)))
            if st.get("last_warn"):
                warns.append(f"{short(st['course_id'])}: {clip(st['last_warn'], 160)}")
        if not c.rows:
            c.add_row(f"[{LBL}]waiting for the runs to start…[/]", "", "", "", "", "", "", "", "")

        # request types: the most recently active first
        t = Table(expand=True, header_style=f"bold {LBL}", box=box.SIMPLE_HEAD, border_style=DIM, pad_edge=False,
                  show_edge=False)
        for col in ["Course", "Step", "Type", "Sent", "Retries", "Cut", "Avg out tok", "Thinking", "Avg time",
                    "tok/s per req", "Last"]:
            t.add_column(col, justify="left" if col in ("Course", "Step", "Type") else "right", no_wrap=True)
        for (cs, stg, pid), k in sorted(types.items(), key=lambda kv: -kv[1]["last"])[:9]:
            if not k["sent"]:
                continue
            tc = k["think"] + k["answer"]
            t.add_row(cs, stg, pid, f"{k['sent']:,}", f"{k['retries']:,}" if k["retries"] else "",
                      f"[yellow]{k['length']}[/]" if k["length"] else "", f"{k['out'] / k['sent']:,.0f}",
                      f"{k['think'] / tc * 100:.0f}%" if tc else "", f"{k['lat'] / k['sent']:.0f} s",
                      f"{k['out'] / k['lat']:.0f}" if k["lat"] else "", f"{hms(now - k['last'])} ago")
        if not t.rows:
            t.add_row(f"[{LBL}]no requests finished yet[/]", *[""] * 10)

        # recent requests
        rr = Table(expand=True, header_style=f"bold {LBL}", box=box.SIMPLE_HEAD, border_style=DIM, pad_edge=False,
                  show_edge=False)
        for col in ["Done", "Course", "Request", "In", "Out", "Time", "tok/s", "End"]:
            rr.add_column(col, justify="left" if col in ("Done", "Course", "Request", "End") else "right",
                          no_wrap=True)
        for cs, r in reversed(recent):
            fin = r.get("finish") or ""
            rr.add_row(time.strftime("%H:%M:%S", time.localtime(r["t_end"])), cs,
                       f"{r['key'][:44]}" + (f" [yellow](retry {r['attempt']})[/]" if r.get("attempt") else ""),
                       f"{r['input_tokens']:,}", f"{r['output_tokens']:,}", f"{r['latency_s']:.0f} s",
                       f"{r['output_tokens'] / max(r['latency_s'], 0.1):.0f}",
                       fin if fin == "stop" else f"[yellow]{fin}[/]")

        # latest answer written to the cache: the end of the thinking and the start of the answer
        la = latest_answer()
        if la:
            cid, stage, m, r = la
            ans = Group(Text.from_markup(f"[bold]{short(cid)}[/] [{LBL}]{stage.replace('v2_', '')} · {r.get('key', '')} · "
                                         f"{r.get('output_tokens', 0):,} tokens · {hms(now - m)} ago[/]"),
                        Text("thinking … " + clip((r.get("reasoning") or "")[-600:], 330), style="grey50"),
                        Text("answer:   " + clip(r.get("content", ""), 330), style="grey82"))
        else:
            ans = Text("no answers yet", style=LBL)

        foot = [Text("Ctrl-b w: windows (dashboard · control · each course · server log)   Ctrl-b d: detach, the run "
                     "keeps going   tmux attach -t lir2: come back", style=DIM)]
        if done and (run / "report.md").exists():
            foot.insert(0, Text(f"Report: {run / 'report.md'}", style="bold green"))
        # fit the terminal: GPU, server and courses always; then the latest answer, request types, recent requests
        pp = panel(Group(*prog) if prog else Text("waiting…", style=LBL), "Pipeline progress", "steel_blue")
        prog_h = 2 + sum(len(con.render_lines(x, con.options.update(width=con.size.width - 4))) for x in prog)
        free = con.size.height - (1 + 7 + 4 + len(c.rows) + prog_h + len(foot) + min(2, len(warns)))
        parts = [head, top, panel(c, "Courses", "steel_blue"), pp]
        extra = []
        if free >= 6:
            extra.append((3, panel(ans, "Latest answer", "cyan")))
            free -= 6
        k = min(len(t.rows), free - 4)
        if k >= 1:
            t.rows[:] = t.rows[:k]
            t.columns[:] = t.columns
            for col in t.columns:
                col._cells[:] = col._cells[:k]
            extra.append((1, panel(t, "Request types (most recent first)", "cyan")))
            free -= 4 + k
        k = min(len(rr.rows), free - 4)
        if k >= 1:
            for col in rr.columns:
                col._cells[:] = col._cells[:k]
            rr.rows[:] = rr.rows[:k]
            extra.append((2, panel(rr, "Recent requests", "cyan")))
        parts += [x for _, x in sorted(extra, key=lambda e: e[0])]
        if free < 6 + 5:
            foot = [Text("Enlarge the terminal to see request types, recent requests and the latest answer. "
                         "Ctrl-b d detaches.", style=DIM)]
        return Group(*parts, *(Text(w, style="yellow") for w in warns[-2:]), *foot)

    with Live(render(), refresh_per_second=1, screen=True) as live:
        while True:
            time.sleep(2)
            try:
                live.update(render())
            except Exception as e:  # keep the dashboard alive on a half-written file
                live.update(Text(f"dashboard error: {e}"))


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("sample", "dash"):
        sys.exit(__doc__)
    {"sample": sample, "dash": dash}[sys.argv[1]](Path(sys.argv[2]).resolve())
