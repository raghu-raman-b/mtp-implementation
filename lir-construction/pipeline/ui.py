"""Terminal UI: color-coded log plus live progress bars for the whole run, the current stage and the video downloads.

    ━━ overall ━━━━━━━━━━━━━━━━━━  42%  0:12:31 elapsed  ~0:17:02 left
    ━━ stage 5 · generate ━━━━━━━  118/302 calls  611 tok/s  3 retries  ~0:04:10 left
    ━━ videos ━━━━━━━━━━━━━━━━━━━  17/63  L18 54%  6.2 MB/s  ~0:21:40 left

The overall bar is weighted by how long each stage usually takes, so its ETA is meaningful from the start.
"""
from __future__ import annotations

import threading
import time

from rich.console import Console, Group
from rich.live import Live
from rich.progress import (BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn,
                           TimeElapsedColumn, TimeRemainingColumn)
from rich.table import Table
from rich.text import Text

# share of total time per stage (measured on the VR and Deep Learning test runs)
STAGE_WEIGHTS = {
    "transcripts": 1, "stage1_segment": 6, "stage2_annotate": 27, "stage3_goals": 4, "stage4_course_state": 10,
    "stage5_generate": 30, "stage6_judge": 18, "stage6_calibrate": 2, "stage7_assemble": 1, "docs": 1,
}
STAGE_LABEL = {
    "transcripts": "0 · transcripts", "stage1_segment": "1 · segment", "stage2_annotate": "2 · annotate",
    "stage3_goals": "3 · goal hierarchy", "stage4_course_state": "4 · course state", "stage5_generate": "5 · generate",
    "stage6_judge": "6 · judge + repair", "stage6_calibrate": "6 · calibrate scorer", "stage7_assemble": "7 · assemble",
    "docs": "docs",
}
STYLE = {"stage": "bold cyan", "ok": "green", "warn": "yellow", "err": "bold red", "judge": "magenta",
         "info": "white", "dim": "grey58", "video": "blue"}


class UI:
    def __init__(self, enabled: bool = True, only_videos: bool = False):
        self.only_videos = only_videos
        self.console = Console(highlight=False)
        self.enabled = enabled and self.console.is_terminal
        self.overall = Progress(TextColumn("[bold]{task.description:<22}"), BarColumn(bar_width=None, complete_style="cyan"),
                                TaskProgressColumn(), TimeElapsedColumn(), TextColumn("elapsed"),
                                TextColumn("[cyan]~{task.fields[eta]} left"), expand=True, console=self.console)
        self.stage = Progress(SpinnerColumn(style="cyan"), TextColumn("{task.description:<26}"),
                              BarColumn(bar_width=None, complete_style="green"), MofNCompleteColumn(),
                              TextColumn("[green]{task.fields[rate]}"), TextColumn("[yellow]{task.fields[retries]}"),
                              TimeRemainingColumn(), expand=True, console=self.console)
        self.video = Progress(TextColumn("[blue]{task.description:<22}"), BarColumn(bar_width=None, complete_style="blue"),
                              MofNCompleteColumn(), TextColumn("[blue]{task.fields[current]}"), TimeRemainingColumn(),
                              expand=True, console=self.console)
        self.server_text = Text("", style="grey58")
        self._overall = self.overall.add_task("overall", total=100, eta="?")
        self._stage = None
        self._video = None
        self._weights = dict(STAGE_WEIGHTS)
        self._done_weight = 0.0
        self._cur = None
        self._cur_frac = 0.0
        self._t0 = time.time()
        self._prior_total_s: float | None = None
        self._lock = threading.Lock()
        self.live = None

    # ------------------------------------------------------------ lifecycle
    def __enter__(self):
        if self.enabled:
            self.live = Live(self._render(), console=self.console, refresh_per_second=4, transient=False)
            self.live.__enter__()
            threading.Thread(target=self._refresh_loop, daemon=True).start()
        return self

    def __exit__(self, *exc):
        if self.live:
            self.live.update(self._render())
            self.live.__exit__(*exc)
            self.live = None

    def _render(self):
        parts = [] if self.only_videos else [self.overall, self.stage]
        if self._video is not None:
            parts.append(self.video)
        parts.append(self.server_text)
        return Group(*parts)

    def _refresh_loop(self):
        while self.live:
            self._update_overall()
            try:
                self.live.update(self._render())
            except Exception:
                pass
            time.sleep(0.5)

    # ------------------------------------------------------------ logging
    def log(self, msg: str = "", kind: str = "info"):
        style = STYLE.get(kind, "white")
        if msg.lstrip().startswith("!"):
            style = STYLE["warn"]
        self.console.print(Text(msg, style=style))

    def table(self, title: str, header: list[str], rows: list[list], styles: list[str] | None = None):
        t = Table(title=title, title_style="bold", header_style="bold cyan", show_lines=False)
        for i, h in enumerate(header):
            t.add_column(h, justify="right" if i else "left", style=(styles or [None] * len(header))[i])
        for r in rows:
            t.add_row(*[str(x) for x in r])
        self.console.print(t)

    def server(self, text: str):
        self.server_text = Text(text, style="grey58")

    # ------------------------------------------------------------ overall + stage
    def set_prior(self, total_s: float):
        """A prior estimate of the whole run, used for the ETA until real progress takes over."""
        self._prior_total_s = total_s

    def skip(self, stage: str):
        self._weights.pop(stage, None)

    def start_stage(self, stage: str):
        with self._lock:
            self._cur, self._cur_frac = stage, 0.0
        self.log(f"\n━━ {STAGE_LABEL.get(stage, stage)} ━━", "stage")
        self.calls(STAGE_LABEL.get(stage, stage), 1)

    def end_stage(self, stage: str, wall: float):
        with self._lock:
            self._done_weight += self._weights.get(stage, 0)
            self._cur, self._cur_frac = None, 0.0
        if self._stage is not None:
            self.stage.update(self._stage, completed=self.stage.tasks[0].total)
        self.log(f"  ✓ {STAGE_LABEL.get(stage, stage)} done in {wall:.1f}s", "ok")

    def calls(self, desc: str, total: int):
        """Start a progress bar for a batch of calls inside the current stage."""
        if self._stage is not None:
            self.stage.remove_task(self._stage)
        self._stage = self.stage.add_task(desc, total=max(total, 1), rate="", retries="")
        self._calls_t0 = time.time()
        self._calls_tokens = 0

    def advance(self, n: int = 1, tokens: int = 0, retries: int = 0, frac_of_stage: float | None = None):
        if self._stage is None:
            return
        self._calls_tokens += tokens
        dt = max(time.time() - self._calls_t0, 1e-6)
        task = self.stage.tasks[0]
        self.stage.update(self._stage, advance=n, rate=f"{self._calls_tokens / dt:,.0f} tok/s" if self._calls_tokens else "",
                          retries=(f"{retries} retries" if retries else ""))
        if frac_of_stage is not None:
            self._cur_frac = frac_of_stage
        else:
            self._cur_frac = max(self._cur_frac, min(1.0, (task.completed) / max(task.total, 1)))

    def set_stage_fraction(self, f: float):
        self._cur_frac = max(0.0, min(1.0, f))

    def _update_overall(self):
        total_w = sum(self._weights.values()) or 1
        with self._lock:
            done = self._done_weight + self._weights.get(self._cur, 0) * self._cur_frac
        frac = done / total_w
        elapsed = time.time() - self._t0
        if frac > 0.03:
            est_total = elapsed / frac
            if self._prior_total_s and frac < 0.25:  # blend with the prior early on
                w = frac / 0.25
                est_total = w * est_total + (1 - w) * self._prior_total_s
        elif self._prior_total_s:
            est_total = self._prior_total_s
        else:
            est_total = None
        eta = _fmt(max(0.0, est_total - elapsed)) if est_total else "?"
        self.overall.update(self._overall, completed=100 * frac, eta=eta)

    # ------------------------------------------------------------ videos
    def videos(self, total: int):
        self._video = self.video.add_task("videos", total=total, current="")

    def video_progress(self, done: int, current: str):
        if self._video is not None:
            self.video.update(self._video, completed=done, current=current)


def _fmt(s: float) -> str:
    s = int(s)
    h, r = divmod(s, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
