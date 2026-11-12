"""Stage 1b: verify each lecture's segmentation, send it back to the model when a check fails, write the segment maps.

    python scripts/s1b_verify_segments.py nptel_vr --llm configs/gemma4_12b_llamacpp.json [--only 1-5]

Flow for each lecture, starting from stage 1a's answer:

    answer --> structural checks --fail--> structural retry --> new answer --> structural checks ...
                     | pass
               logical checks ----flagged--> logical retry ----> new answer --> structural checks ...
                     | pass, or logical retries used up
               keep the answer that passes the structural checks with the fewest flagged segments (the later on ties)

Structural checks (hard: an answer that fails them is never kept), worded for the model, sentence numbers from 1:
  on the answer       a non-empty list; each item an integer "start" and a non-empty "subgoal"; the first segment
                      starts at sentence 1; every start within the lecture; starts strictly increase
  on the segments     1 exhaustive (every sentence in some segment), 2 mutually exclusive, 3 contiguous and ordered,
  (sets of sentences) 4 non-empty. Answers that pass the answer checks always pass these; kept as a guard.
Logical checks (soft, a heuristic): a segment under 2 min or over 15 min (MIN_S, MAX_S; durations as in the maps; the last segment may be short:
  the closing remarks may be a segment of their own). The bounds are not defensible as rules, so the model is told
  neither them nor the durations: only that a segment "looks too small" or "looks too big", to check it again against
  the instructions, and to keep it if it is right.

Budgets: up to STRUCTURAL_RETRIES structural retries for each answer that fails the structural checks in a row; up to
LOGICAL_RETRIES logical retries per lecture. A lecture fails (no segment map) only if no answer passes the structural
checks.

The retry conversation is the full history: [the 1a prompt, 1a's answer, retry prompt 1, answer 1, retry prompt 2, ...],
every answer as the model gave it. The server keeps no state, so 1b sends the whole conversation each time; the 1a
prompt is rebuilt and checked against 1a's prompt_sha. The model's thinking is not sent back. Instead, every answer is a
JSON object {"reasoning": ..., "segments": [...]}: in 1a's answer the reasoning says why it chose the segmentation; in a
retry answer, what the model changed, or kept and why. So each retry sees why the cuts were first made and every fix
since, and builds on them instead of starting again. (At most STRUCTURAL_RETRIES + LOGICAL_RETRIES rounds of a few
hundred tokens each: far inside the context.)

Prompts  prompts/segmentation_structural_retry.txt, prompts/segmentation_logical_retry.txt ({problems})
Reads    output/<course>/stage_0a_preprocess/, output/<course>/stage_1a_segmentation/raw/lec_<n>.json
Writes   output/<course>/stage_1b_verify_segments/
           segment_maps/lec_<n>.json   from the kept answer:
               {"<n>/S0": {"first": "<n>/0", "last": "<n>/41", "start": 24.297, "end": 292.435,
                           "duration_s": 268.138, "subgoal": "Explain ..."}, ...}
           retry/lec_<n>.json          lectures with retries: every attempt (kind, the retry prompt sent, the answer,
                                       its reasoning, the model's thinking, problems found, segment lengths, tokens)
           report.json                 per lecture: ok, kept attempt, retries, flagged segments left (with lengths)
           llm/cache.jsonl, calls.jsonl
start is the first sentence's start and end the last sentence's end. A boundary inside a subtitle cue (null in stage
0a) gets an estimated time (Timing: from the edges of the cue it falls in and the words on each side, at the course's
median speaking rate; stage 0a's times/meta.json and times/cues/) and the segment lists it: "estimated": ["start"].

Without an LLM (llm=None, no --llm) the stage only checks: no retries; a lecture that fails the structural checks fails.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the pipeline folder
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from scripts import lectures as lec  # noqa: E402
from scripts import s1a_segmentation as s1a  # noqa: E402
from scripts.llm import LLM, LLMConfig, Request  # noqa: E402

PROMPTS = ROOT / "prompts"
STRUCTURAL_PROMPT = PROMPTS / "segmentation_structural_retry.txt"
LOGICAL_PROMPT = PROMPTS / "segmentation_logical_retry.txt"
STRUCTURAL_RETRIES, LOGICAL_RETRIES = 2, 2
MIN_S, MAX_S = 120, 900    # logical checks: under 2 min looks too small, over 15 min too big
RETRY_SCHEMA = s1a.SCHEMA   # {"reasoning", "segments"}, the same as 1a's answer


# ---------------------------------------------------------------------------- structural checks
def answer_errors(answer, n_sentences: int) -> list[str]:
    """Problems with the model's answer, worded for the model (sentence numbers from 1)."""
    if not isinstance(answer, list) or not answer:
        return ["The answer must be a non-empty JSON list of segments."]
    errors, prev = [], None
    for k, seg in enumerate(answer, 1):
        if not (isinstance(seg, dict) and isinstance(seg.get("start"), int) and not isinstance(seg.get("start"), bool)):
            errors.append(f'Segment {k} must be an object with an integer "start".')
            continue
        start = seg["start"]
        if not isinstance(seg.get("subgoal"), str) or not seg["subgoal"].strip():
            errors.append(f'Segment {k} (starting at sentence {start}) has no "subgoal".')
        if k == 1 and start != 1:
            errors.append(f"The first segment must start at sentence 1, not at sentence {start}.")
        if not 1 <= start <= n_sentences:
            errors.append(f"Segment {k} starts at sentence {start}, but the lecture has sentences 1 to {n_sentences}.")
        if prev is not None and start <= prev:
            errors.append(f"Segment {k} starts at sentence {start}, which is not after the start of segment {k - 1} "
                          f"(sentence {prev}): segments must be in order and each must start after the one before.")
        prev = start
    return errors


def build(answer: list, ids: list[str]) -> list[list[str]]:
    """The segments as lists of sentence IDs: each runs from its start to the sentence before the next start."""
    starts = [seg["start"] - 1 for seg in answer]
    ends = [s - 1 for s in starts[1:]] + [len(ids) - 1]
    return [ids[a:b + 1] for a, b in zip(starts, ends)]


def segment_errors(segments: list[list[str]], ids: list[str]) -> list[str]:
    """Checks 1-4 on the segments as sets of sentences (sentence numbers from 1 in the messages)."""
    pos = {s: i for i, s in enumerate(ids)}
    num = lambda s: pos[s] + 1  # noqa: E731
    errors = []
    seen: dict[str, int] = {}
    for k, seg in enumerate(segments, 1):
        if not seg:
            errors.append(f"Segment {k} has no sentences.")                                         # 4 non-empty
        for s in seg:
            if s in seen:
                errors.append(f"Sentence {num(s)} is in segment {seen[s]} and segment {k}.")       # 2 exclusive
            seen.setdefault(s, k)
        if seg and [pos[s] for s in seg] != list(range(pos[seg[0]], pos[seg[-1]] + 1)):
            errors.append(f"Segment {k} is not a run of consecutive sentences.")                   # 3 contiguous
    missing = [num(s) for s in ids if s not in seen]
    if missing:
        errors.append(f"Sentences {missing} are in no segment.")                                   # 1 exhaustive
    flat = [s for seg in segments for s in seg]
    if not errors and flat != ids:
        errors.append("The segments do not follow the order of the lecture.")                      # 3 ordered
    return errors


def check(answer, ids: list[str]) -> list[str]:
    """All structural checks on one answer (a list of segments); [] when it is fine."""
    errors = answer_errors(answer, len(ids))
    return errors or segment_errors(build(answer, ids), ids)


def segments_of(parsed):
    """The list of segments in an answer: {"reasoning", "segments"} (1a and retries); a bare list (1a answers from
    before 1a asked for reasoning) is taken as the segments."""
    return parsed.get("segments") if isinstance(parsed, dict) else parsed


# ---------------------------------------------------------------------------- segment times
class Timing:
    """Times of a lecture's segment boundaries. A boundary at a subtitle cue's edge has the cue's time (exact). One
    inside a cue (null in stage 0a) is estimated from the course's speaking rate (stage 0a's times/meta.json,
    wpm_median) and the cue it falls in (stage 0a's times/cues/): forward from the cue's start by the words spoken
    before the boundary, backward from the cue's end by the words spoken after it; the mean of the two, kept inside
    the cue. Without a cue timeline the nearest exact sentence times on each side stand in for the cue's edges
    (they can be far apart where cues split sentences anywhere).
    method: "cue" (default; falls back to "sentences" without a timeline), "sentences", or "forward" (from the
    nearest exact time before the boundary only); the last two are kept to compare (see the preprocessing report)."""

    def __init__(self, ids: list[str], sentences: dict, times: dict, wpm: float, timeline: dict | None = None,
                 method: str = "cue"):
        self.ids, self.times, self.wpm = ids, times, wpm
        self.words = [len(sentences[i].split()) for i in ids]
        self.method = method if timeline or method != "cue" else "sentences"
        if timeline:
            self.cues = timeline["cues"]
            self.cue_first, w = [], 0                    # each cue's first word, counted over the whole lecture
            for c in self.cues:
                self.cue_first.append(w)
                w += c[2]
            self.sent_first, w = [], timeline["skip_words"]   # each sentence's first word
            for n in self.words:
                self.sent_first.append(w)
                w += n

    def _rate(self, words: int) -> float:
        return words / self.wpm * 60

    def before(self, i: int) -> tuple[float, bool]:
        """(time, estimated) of the boundary just before sentence i (its start)."""
        t = self.times[self.ids[i]]["start"]
        if t is not None:
            return t, False
        if self.method == "cue":
            w = self.sent_first[i]
            c = max(k for k, f in enumerate(self.cue_first) if f <= w)          # the cue the boundary is in
            t0, t1, n = self.cues[c]
            into = w - self.cue_first[c]
            t0, t1, before, after = t0, t1, into, n - into
        else:   # the nearest exact times on each side: an earlier sentence's start, a later sentence's end
            j = next((j for j in range(i - 1, -1, -1) if self.times[self.ids[j]]["start"] is not None), 0)
            k = next((k for k in range(i - 1, len(self.ids)) if self.times[self.ids[k]]["end"] is not None), None)
            t0 = self.times[self.ids[j]]["start"] or 0.0
            before = sum(self.words[j:i])
            if k is None or self.method == "forward":
                return round(t0 + self._rate(before), 3), True
            t1, after = self.times[self.ids[k]]["end"], sum(self.words[i:k + 1])
        forward, backward = t0 + self._rate(before), t1 - self._rate(after)
        return round(min(max((forward + backward) / 2, t0), t1), 3), True

    def after(self, i: int) -> tuple[float, bool]:
        """(time, estimated) of the boundary just after sentence i (its end)."""
        t = self.times[self.ids[i]]["end"]
        if t is not None or i + 1 == len(self.ids):
            return t, False
        return self.before(i + 1)

    def span(self, seg: list[str]) -> tuple[float, float, list[str]]:
        """(start, end, which of them are estimated) of a segment (a list of sentence IDs)."""
        (s, se), (e, ee) = self.before(self.ids.index(seg[0])), self.after(self.ids.index(seg[-1]))
        return s, e, [k for k, est in (("start", se), ("end", ee)) if est]

    def seconds(self, seg: list[str]) -> float:
        s, e, _ = self.span(seg)
        return e - s


def load_timing(course: str, n, sentences: dict | None = None, method: str = "cue") -> Timing:
    s0 = ROOT / "output" / course / "stage_0a_preprocess"
    meta = s0 / "times" / "meta.json"
    if not meta.exists():
        raise SystemExit(f"{meta} is missing: run stage 0a again (it writes the speaking rate)")
    stem = lec.stem_of(n)
    sentences = sentences or json.loads((s0 / f"{stem}.json").read_text())
    cues = s0 / "times" / "cues" / f"{stem}.json"
    return Timing(list(sentences), sentences, json.loads((s0 / "times" / f"{stem}.json").read_text()),
                  json.loads(meta.read_text())["wpm_median"],
                  json.loads(cues.read_text()) if cues.exists() else None, method)


# ---------------------------------------------------------------------------- logical checks
def length_problems(answer: list, ids: list[str], timing: Timing, min_s: float | None = MIN_S,
                    max_s: float | None = MAX_S, exempt_last: bool = True, show_time: bool = False) -> list[str]:
    """Segments under min_s or over max_s, worded for the model (no bounds, no durations; show_time=True adds the
    duration, for reports). The last segment is exempt from the minimum by default. None disables a bound."""
    out = []
    segs = build(answer, ids)
    for k, (seg, item) in enumerate(zip(segs, answer), 1):
        d = timing.seconds(seg)
        where = (f'Segment {k} (sentences {ids.index(seg[0]) + 1} to {ids.index(seg[-1]) + 1}, '
                 f'"{item["subgoal"].strip()}")')
        when = f" [{int(d // 60)} min {int(d % 60)} s]" if show_time else ""
        if min_s is not None and d < min_s and not (exempt_last and k == len(segs)):
            out.append(f"{where} looks too small.{when}")
        elif max_s is not None and d > max_s:
            out.append(f"{where} looks too big.{when}")
    return out


# ---------------------------------------------------------------------------- the verify loop
def fill(path: Path, **fields: str) -> str:
    """A prompt file with its {placeholders} replaced (plain replacement: JSON braces in the text stay as they are)."""
    text = path.read_text()
    for k, v in fields.items():
        text = text.replace("{" + k + "}", v)
    return text


def bullets(items: list[str]) -> str:
    return "\n".join(f"- {x}" for x in items)


def verify_lecture(raw: dict, ids: list[str], timing: Timing, ask=None) -> dict:
    """Run the flow on one lecture. ask(followup) -> llm Result sends a retry (None: checks only). Returns
    {"attempts": [...], "kept": index or None}."""
    attempts: list[dict] = []

    def add(kind: str, parsed, content: str, sent: str | None = None, fixing: list | None = None, res=None) -> dict:
        segs = segments_of(parsed)
        errs = check(segs, ids)
        a = {"attempt": len(attempts), "kind": kind, "sent": sent, "fixing": fixing, "content": content,
             "reasoning": parsed.get("reasoning") if isinstance(parsed, dict) else None,
             "segments": segs, "structural_errors": errs, "logical_problems": None,
             "minutes": None if errs else [round(timing.seconds(s) / 60, 2) for s in build(segs, ids)]}
        if res is not None:
            a.update(thinking=res.reasoning, input_tokens=res.input_tokens, output_tokens=res.output_tokens,
                     latency_s=round(res.latency_s, 2), cached=res.cached, finish=res.finish)
        attempts.append(a)
        return a

    history: list[dict] = []   # the conversation after the 1a prompt: answer, retry prompt, answer, retry prompt, ...

    def retry(kind: str, last: dict, problems: list[str]) -> dict:
        print(f"  {time.strftime('%H:%M:%S')}  → {lec.stem_of(raw.get('lecture', '?'))}: {kind} retry "
              f"(attempt {len(attempts)}), {len(problems)} problem(s): {problems[0][:90]}", flush=True)
        sent = fill(STRUCTURAL_PROMPT if kind == "structural" else LOGICAL_PROMPT, problems=bullets(problems))
        history.extend([{"role": "assistant", "content": last["content"] or ""}, {"role": "user", "content": sent}])
        res = ask(list(history), len(attempts))
        return add(kind, res.parsed, res.content, sent, problems, res)

    cur = add("1a", raw.get("answer"), raw.get("content", ""))
    s_used = l_used = 0
    while True:
        if cur["structural_errors"]:
            if ask is None or s_used == STRUCTURAL_RETRIES:
                break
            s_used += 1
            cur = retry("structural", cur, cur["structural_errors"])
            continue
        s_used = 0
        cur["logical_problems"] = length_problems(cur["segments"], ids, timing)
        if not cur["logical_problems"] or ask is None or l_used == LOGICAL_RETRIES:
            break
        l_used += 1
        cur = retry("logical", cur, cur["logical_problems"])
    valid = [a for a in attempts if not a["structural_errors"]]
    kept = min(reversed(valid), key=lambda a: len(a["logical_problems"]))["attempt"] if valid else None
    return {"attempts": attempts, "kept": kept}


# ---------------------------------------------------------------------------- segment maps
def segment_map(n, answer: list, ids: list[str], timing: Timing) -> dict:
    """The segments of the kept answer with their times. A boundary inside a subtitle cue gets an estimated time,
    listed in "estimated" (e.g. ["start"]); the key is there only when something is estimated."""
    out = {}
    for k, (seg, item) in enumerate(zip(build(answer, ids), answer)):
        start, end, est = timing.span(seg)
        out[f"{n}/S{k}"] = {"first": seg[0], "last": seg[-1], "start": start, "end": end,
                            "duration_s": round(end - start, 3), "subgoal": item["subgoal"].strip(),
                            **({"estimated": est} if est else {})}
    return out


def out_dir(course: str) -> Path:
    return ROOT / "output" / course / "stage_1b_verify_segments"


def run(course: str, lectures: list | None = None, llm: LLM | LLMConfig | str | Path | None = None) -> dict:
    """Verify the lectures (all that stage 1a answered, by default). llm: an LLM (started), or an LLMConfig or config
    file (the server is started only if some lecture needs a retry, and stopped after); None: checks only."""
    s0 = ROOT / "output" / course / "stage_0a_preprocess"
    raws_dir = s1a.out_dir(course) / "raw"
    out = out_dir(course)
    for sub in ("segment_maps", "retry", "llm"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    paths = lec.files(raws_dir)
    if lectures:
        keep = lec.normalize(lectures)
        paths = [p for p in paths if lec.key_of(p.stem) in keep]
    data = {}
    for p in paths:
        raw = json.loads(p.read_text())
        n = lec.key_of(p.stem)
        sents = json.loads((s0 / p.name).read_text())
        data[n] = {"raw": raw, "ids": list(sents), "timing": load_timing(course, n, sents),
                   "prompt": s1a.build_prompt(sents, course, n)}

    # the retry conversation starts from 1a's prompt: it must be the one 1a sent
    stale = [n for n, d in data.items()
             if d["raw"].get("prompt_sha") and d["raw"]["prompt_sha"] != s1a.prompt_sha(d["prompt"])]
    if stale:
        raise RuntimeError(f"the segmentation prompt changed since stage 1a for lectures {stale}; run 1a again")

    def needs_model(d):
        segs = segments_of(d["raw"].get("answer"))
        return bool(check(segs, d["ids"]) or length_problems(segs, d["ids"], d["timing"]))

    own = None
    if isinstance(llm, (str, Path)):
        llm = LLMConfig.load(llm)
    if isinstance(llm, LLMConfig):
        own = llm = LLM(llm) if any(needs_model(d) for d in data.values()) else None
        if own:
            own.start()

    def verify(n: int) -> tuple[int, dict]:
        d = data[n]

        def ask(followup: list, k: int):
            return llm.generate(Request(prompt=d["prompt"], key=f"{lec.stem_of(n)}/attempt_{k}", schema=RETRY_SCHEMA,
                                        followup=followup, meta={"lecture": n, "attempt": k}),
                                cache_file=out / "llm" / "cache.jsonl", log_file=out / "llm" / "calls.jsonl")
        return n, verify_lecture(d["raw"], d["ids"], d["timing"], ask if llm else None)

    try:
        workers = max(1, (llm.cfg.concurrency or llm.cfg.slots) if llm else 1)
        need = [lec.stem_of(n) for n, d in data.items() if needs_model(d)]
        print(f"1b: checking {len(data)} lectures; {len(need)} fail a check and go back to "
              f"{llm.model if llm else 'no model (checks only)'}: {', '.join(need) or 'none'}", flush=True)
        with ThreadPoolExecutor(max_workers=workers) as ex:
            results = dict(ex.map(verify, list(data)))
    finally:
        if own:
            own.stop()

    rp = out / "report.json"
    report = json.loads(rp.read_text()) if lectures and rp.exists() else {}   # --only updates the report
    for n, v in results.items():
        d, atts, kept = data[n], v["attempts"], v["kept"]
        kinds = [a["kind"] for a in atts]
        entry = {"ok": kept is not None, "kept_attempt": kept, "attempts": len(atts),
                 "structural_retries": kinds.count("structural"), "logical_retries": kinds.count("logical")}
        retry_file = out / "retry" / f"{lec.stem_of(n)}.json"
        smap_file = out / "segment_maps" / f"{lec.stem_of(n)}.json"
        if len(atts) > 1:
            retry_file.write_text(json.dumps({"lecture": n, "kept_attempt": kept, "attempts": atts},
                                             indent=1, ensure_ascii=False) + "\n")
        else:
            retry_file.unlink(missing_ok=True)
        if kept is not None:
            segs = atts[kept]["segments"]
            smap = segment_map(n, segs, d["ids"], d["timing"])
            smap_file.write_text(json.dumps(smap, indent=1, ensure_ascii=False) + "\n")
            entry["segments"] = len(smap)
            entry["flagged_left"] = length_problems(segs, d["ids"], d["timing"], show_time=True)
        else:
            smap_file.unlink(missing_ok=True)
            entry["structural_errors"] = atts[-1]["structural_errors"]
        report[lec.stem_of(n)] = entry
    rp.write_text(json.dumps(dict(sorted(report.items(), key=lambda kv: lec.order(lec.key_of(kv[0])))), indent=1,
                             ensure_ascii=False) + "\n")

    done = {lec.stem_of(n): report[lec.stem_of(n)] for n in results}
    failed = [k for k, e in done.items() if not e["ok"]]
    s_retried = [k for k, e in done.items() if e["structural_retries"]]
    l_retried = [k for k, e in done.items() if e["logical_retries"]]
    n_seg = sum(e.get("segments", 0) for e in done.values())
    n_flag = sum(len(e.get("flagged_left", [])) for e in done.values())
    print(f"{len(done) - len(failed)}/{len(done)} lectures pass, {n_seg} segments -> {out.relative_to(ROOT)}"
          + (f"; failed: {failed}" if failed else "")
          + (f"; structural retries: {s_retried}" if s_retried else "")
          + (f"; logical retries: {l_retried}" if l_retried else "")
          + f"; flagged segments left: {n_flag}")
    return {"lectures": len(done), "ok": len(done) - len(failed), "segments": n_seg, "failed": failed,
            "structural_retried": s_retried, "logical_retried": l_retried, "flagged_left": n_flag}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("course")
    ap.add_argument("--llm", help="LLMConfig file for the retries (without it: checks only)")
    ap.add_argument("--only", help="lectures, e.g. 1-5,8,24b,tut_1")
    a = ap.parse_args()
    run(a.course, s1a.parse_only(a.only) if a.only else None, a.llm)


if __name__ == "__main__":
    main()
