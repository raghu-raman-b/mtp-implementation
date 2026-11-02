"""The judge: the judge model checks an item against its sources (yes/no with a reason). If it fails and the item can
be rewritten, the judge model rewrites it once with the reason, and the rewrite is judged again. What still fails is
resolved by the caller (dropped, or kept and flagged), never left open. Every verdict goes to the decision log, and
the counts (judged / passed first / repaired / failed per kind) go to the run report.
"""
from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel

from pipeline.llm import Call

from . import prompts as P
from .context import Run


class Verdict(BaseModel):
    reason: str
    ok: bool


def verdict(send, R: Run, llm, *, key: str, lid: str, prefix: str, show: str, criteria: str, subject: list,
            kind: str) -> tuple[bool, str]:
    o = send(Call(key=f"{key}/judge", lecture_id=lid, prompt=prefix + P.JUDGE[2].format(item=show, criteria=criteria),
                  schema=Verdict, prompt_id=P.JUDGE[0], prompt_version=P.JUDGE[1]))
    R.record(o, "judge", llm, o.call.key)
    ok = bool(o.parsed and o.parsed.ok)
    reason = o.parsed.reason if o.parsed else f"no usable verdict: {o.errors}"
    R.decisions.add("judge", subject, "passed" if ok else "failed", reason, o, llm.model, item=key, kind=kind)
    return ok, reason


def judge_fix(send, R: Run, llm, *, key: str, lid: str, prefix: str, item: Any, show: Callable[[Any], str],
              criteria: str, subject: list, kind: str,
              rewrite: Callable[[Any, str], Any] | None = None) -> tuple[Any, bool]:
    """Judge `item`; on a failure, `rewrite(item, reason)` returns a new item (or None) that is judged once more.
    Returns (the item to keep, passed)."""
    R.count(f"judge.{kind}.judged")
    ok, reason = verdict(send, R, llm, key=f"{key}/0", lid=lid, prefix=prefix, show=show(item), criteria=criteria,
                         subject=subject, kind=kind)
    if ok:
        R.count(f"judge.{kind}.passed_first")
        return item, True
    if rewrite is not None:
        new = rewrite(item, reason)
        if new is not None:
            ok, _ = verdict(send, R, llm, key=f"{key}/1", lid=lid, prefix=prefix, show=show(new), criteria=criteria,
                            subject=subject, kind=kind)
            if ok:
                R.count(f"judge.{kind}.repaired")
                R.decisions.add("judge", subject, "repaired", reason, model=llm.model, item=key, kind=kind)
                return new, True
    R.count(f"judge.{kind}.failed")
    return item, False


def rewrite_call(send, R: Run, llm, *, key: str, lid: str, prompt: str, spec: tuple, schema, previous: str,
                 reason: str, check=None):
    """One rewrite by the judge model: the original task plus the rejected answer and the reason. Returns the parsed
    answer, or None."""
    o = send(Call(key=f"{key}/rewrite", lecture_id=lid, prompt=prompt + P.REWRITE.format(previous=previous, reason=reason),
                  schema=schema, prompt_id=spec[0], prompt_version=spec[1], check=check))
    R.record(o, "judge", llm, o.call.key)
    return o.parsed if o.ok else None
