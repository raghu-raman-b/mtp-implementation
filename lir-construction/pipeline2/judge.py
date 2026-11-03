"""The judge, one unit at a time (a part's items, a lecture's links, ...): one call gives a verdict for every item; the
items that fail are rewritten in one call with the reasons (when the kind can be rewritten), and only the rewritten
ones are judged again. What still fails is resolved by the caller (dropped, kept and flagged, or a fallback), never
left open. Every verdict goes to the decision log; the counts (judged / passed first / repaired / failed per kind)
go to the run report.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pipeline.llm import Call

from . import prompts as P
from .context import Run


@dataclass
class Item:
    obj: Any                    # the item itself (a dict)
    kind: str                   # "key_point", "objective", "quiz", ...
    subject: list               # addresses for the decision log
    ok: bool = False
    reason: str = ""
    reversed: bool = False      # links: the relation holds the other way round
    repaired: bool = False


def _schema(n: int, with_reversed: bool) -> dict:
    props = {"item": {"type": "integer", "enum": list(range(1, n + 1))}, "reason": {"type": "string"},
             "ok": {"type": "boolean"}}
    req = ["item", "reason", "ok"]
    if with_reversed:
        props["reversed"] = {"type": "boolean"}
        req.append("reversed")
    return {"type": "object", "additionalProperties": False, "required": ["verdicts"], "properties": {
        "verdicts": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                                "required": req, "properties": props}}}}


def _verdicts(R: Run, *, key: str, lid: str, prefix: str, items: list[Item], show: Callable[[Item], str],
              criteria: str, with_reversed: bool) -> dict[int, dict]:
    text = "\n\n".join(f"[{k}] {show(it)}" for k, it in enumerate(items, 1))
    crit = criteria + (P.JUDGE_LINKS_EXTRA if with_reversed else "")
    o = R.send("judge", Call(key=key, lecture_id=lid, prompt=prefix + P.JUDGE[2].format(items=text, criteria=crit),
                             schema=_schema(len(items), with_reversed), prompt_id=P.JUDGE[0],
                             prompt_version=P.JUDGE[1]))
    out = {}
    if o.parsed is not None:
        for v in o.parsed["verdicts"]:
            out.setdefault(v["item"], v)
    return out, o


def judge_unit(R: Run, *, key: str, lid: str, prefix: str, items: list[Item], show: Callable[[Item], str],
               criteria: str, rewrite: Callable[[list[Item]], dict[int, Any]] | None = None,
               with_reversed: bool = False) -> list[Item]:
    """Judge every item; `rewrite(failed)` returns {index in `failed`: new obj or None}. Sets ok / reason / repaired
    on each item and returns the items (objects replaced by their rewrites where those passed)."""
    if not items:
        return items
    model = R.model_of("judge")
    for it in items:
        R.count(f"judge.{it.kind}.judged")
    got, o = _verdicts(R, key=f"{key}/judge", lid=lid, prefix=prefix, items=items, show=show, criteria=criteria,
                       with_reversed=with_reversed)
    if o.parsed is None:   # no usable verdicts after the retries: keep the items, unjudged, and say so
        for it in items:
            it.ok, it.reason = True, f"not judged: {o.errors}"
            R.count(f"judge.{it.kind}.unjudged")
            R.decisions.add("judge", it.subject, "not judged", it.reason, o, model, kind=it.kind)
        return items
    failed = []
    for k, it in enumerate(items, 1):
        v = got.get(k)
        it.ok = bool(v and v["ok"])
        it.reason = v["reason"] if v else "no verdict for this item"
        it.reversed = bool(v and v.get("reversed"))
        R.decisions.add("judge", it.subject, "passed" if it.ok else ("reversed" if it.reversed else "failed"),
                        it.reason, o, model, kind=it.kind)
        if it.ok:
            R.count(f"judge.{it.kind}.passed_first")
        else:
            failed.append(it)
    if failed and rewrite is not None:
        new = rewrite(failed) or {}
        again = [(it, obj) for k, it in enumerate(failed) for obj in [new.get(k)] if obj is not None]
        if again:
            trial = [Item(obj, it.kind, it.subject) for it, obj in again]
            got2, o2 = _verdicts(R, key=f"{key}/rejudge", lid=lid, prefix=prefix, items=trial, show=show,
                                 criteria=criteria, with_reversed=False)
            for k, (it, obj) in enumerate(again, 1):
                v = got2.get(k)
                if v and v["ok"]:
                    it.obj, it.ok, it.repaired = obj, True, True
                    R.decisions.add("judge", it.subject, "repaired", it.reason, o2, model, kind=it.kind)
                    R.count(f"judge.{it.kind}.repaired")
                else:
                    R.decisions.add("judge", it.subject, "rewrite failed",
                                    v["reason"] if v else "no verdict for the rewrite", o2, model, kind=it.kind)
    for it in items:
        if not it.ok and not it.reversed:
            R.count(f"judge.{it.kind}.failed")
    return items


def rewrite_items(R: Run, *, key: str, lid: str, prefix: str, failed: list[Item], show: Callable[[Item], str],
                  item_schema: dict, rules: str, check: Callable[[Item, dict], list[str]] | None = None
                  ) -> dict[int, dict]:
    """One rewrite call (judge model) for failed items of one kind. `item_schema` describes one rewritten item (its
    properties, without "item"). Returns {index in `failed`: the rewritten fields} for rewrites that pass `check`."""
    if not failed:
        return {}
    text = "\n\n".join(f"[{k}] {show(it)}\nReason: {it.reason}" for k, it in enumerate(failed, 1))
    props = {"item": {"type": "integer", "enum": list(range(1, len(failed) + 1))}, **item_schema["properties"]}
    schema = {"type": "object", "additionalProperties": False, "required": ["items"], "properties": {
        "items": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                             "required": ["item"] + list(item_schema["properties"]),
                                             "properties": props}}}}
    o = R.send("judge", Call(key=f"{key}/rewrite", lecture_id=lid, schema=schema, prompt_id=P.REWRITE[0],
                             prompt_version=P.REWRITE[1],
                             prompt=prefix + P.REWRITE[2].format(items=text, rules=rules)))
    out = {}
    if o.parsed is None:
        return out
    for x in o.parsed["items"]:
        k = x.pop("item") - 1
        if k in out or not 0 <= k < len(failed):
            continue
        errs = check(failed[k], x) if check else []
        if errs:
            R.decisions.add("judge", failed[k].subject, "rewrite rejected by code", "; ".join(errs), o,
                            R.model_of("judge"), kind=failed[k].kind)
            continue
        out[k] = x
    return out
