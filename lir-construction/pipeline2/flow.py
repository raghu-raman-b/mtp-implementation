"""Per-item scheduling for LIR v2.1: each part and each lecture moves on as soon as its inputs are ready.

    flow.go(step, fn, *args, deps=[futures], prio=0)  -> Future

A task starts when all its dependencies are done and runs in its own thread; every model call it sends carries its
priority (lower goes first, see pipeline/llm.py PriorityGate), so the critical path is never queued behind work that
only fills the GPU. A task may wait on other tasks (threads are cheap: they mostly wait on HTTP).

The flow also keeps the time span and counts of every step for the run report and the progress display.
"""
from __future__ import annotations

import threading
import time
import traceback
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable

from pipeline.llm import set_priority

CRIT, MID, FILL = 0, 5, 10      # critical path; per-lecture work behind the facet chain; work that fills the GPU


class Flow:
    def __init__(self, log=print, ui=None, workers: int = 4096):
        self.log, self.ui = log, ui
        self.ex = ThreadPoolExecutor(workers, thread_name_prefix="flow")
        self.lock = threading.Lock()
        self.steps: dict[str, dict] = {}      # step -> {total, done, failed, start, end}
        self.t0 = time.time()
        self.order: list[str] = []
        self._ui_task = None

    # -------------------------------------------------------------------------------------------- tasks
    def go(self, step: str, fn: Callable, *args, deps=(), prio: int = FILL) -> Future:
        out: Future = Future()
        deps = [d for d in deps if d is not None]
        with self.lock:
            st = self.steps.get(step)
            if st is None:
                st = self.steps[step] = {"total": 0, "done": 0, "failed": 0, "start": None, "end": None}
                self.order.append(step)
            st["total"] += 1
        self._show()

        def run():
            set_priority(prio)
            with self.lock:
                if st["start"] is None:
                    st["start"] = time.time()
            ok = False
            try:
                out.set_result(fn(*args))
                ok = True
            except BaseException as e:  # noqa: BLE001 - passed on to whoever waits on the future
                self.log(f"  ! task {step} failed: {e!r}\n{traceback.format_exc(limit=6)}", "err")
                out.set_exception(e)
            finally:
                set_priority(None)
                with self.lock:
                    st["done"] += 1
                    st["failed"] += 0 if ok else 1
                    st["end"] = time.time()
                self._show()

        if not deps:
            self.ex.submit(run)
            return out
        left = [len(deps)]
        dlock = threading.Lock()

        def on_dep(f: Future):
            if f.exception() is not None:
                with dlock:
                    if out.done():
                        return
                    out.set_exception(f.exception())
                with self.lock:
                    st["done"] += 1
                    st["failed"] += 1
                return
            with dlock:
                left[0] -= 1
                ready = left[0] == 0 and not out.done()
            if ready:
                self.ex.submit(run)
        for d in deps:
            d.add_done_callback(on_dep)
        return out

    def map(self, step: str, fn: Callable, items, prio: int | None = None) -> list:
        """Run fn(item) for every item as parallel tasks and wait for all; results in order."""
        from pipeline.llm import current_priority
        p = current_priority() if prio is None else prio
        futs = [self.go(step, fn, x, prio=p) for x in items]
        return [f.result() for f in futs]

    @staticmethod
    def wait(futs) -> list:
        return [f.result() for f in futs]

    def shutdown(self):
        self.ex.shutdown(wait=False, cancel_futures=True)

    # -------------------------------------------------------------------------------------------- reporting
    def spans(self) -> list[dict]:
        """Every step's first start and last end (for the run report)."""
        out = []
        for s in self.order:
            st = self.steps[s]
            if st["start"] is not None:
                end = st["end"] or time.time()
                out.append({"stage": s, "start": st["start"], "end": end, "wall_s": end - st["start"],
                            "tasks": st["total"], "failed": st["failed"]})
        return sorted(out, key=lambda x: x["start"])

    def summary(self) -> str:
        with self.lock:
            active = [f"{s} {st['done']}/{st['total']}" for s in self.order
                      for st in [self.steps[s]] if st["done"] < st["total"]]
        return " · ".join(active[:6]) or "finishing"

    def _show(self):
        ui = self.ui
        if ui is None or not getattr(ui, "enabled", False):
            return
        with self.lock:
            total = sum(st["total"] for st in self.steps.values())
            done = sum(st["done"] for st in self.steps.values())
        try:
            if self._ui_task is None:
                ui.calls("tasks", max(total, 1))
                self._ui_task = ui._stage
            ui.stage.update(self._ui_task, total=max(total, 1), completed=done, description=self.summary()[:60])
            ui.set_stage_fraction(done / max(total, 1))
        except Exception:
            pass
