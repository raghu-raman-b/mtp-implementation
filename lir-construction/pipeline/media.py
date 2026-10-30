"""Lecture videos (yt-dlp, in a background thread) and timestamps for lectures that have no subtitle file.

Videos go to media/<course_id>/<lecture_id>.mp4 and are matched to lectures through titles.tsv's youtube_id.

A lecture without an .srt but with an official transcript gets timestamps by aligning the transcript's words to
YouTube's automatic captions (json3 has a time for every word). The transcript keeps its clean punctuation; the
captions only supply the times.
"""
from __future__ import annotations

import json
import re
import threading
import time
from difflib import SequenceMatcher
from pathlib import Path

from .transcript import Sentence

FORMAT = "bv*[height<={h}][ext=mp4]+ba[ext=m4a]/b[height<={h}][ext=mp4]/bv*[height<={h}]+ba/b[height<={h}]/b"


class _Quiet:
    def __init__(self, log_path: Path):
        self.f = open(log_path, "a", encoding="utf-8")

    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg):
        self.f.write(f"WARNING {msg}\n")
        self.f.flush()

    def error(self, msg):
        self.f.write(f"ERROR {msg}\n")
        self.f.flush()


class VideoDownloader(threading.Thread):
    """Downloads every lecture video one after another, reporting progress to the UI."""

    def __init__(self, items: list[tuple[str, str]], out_dir: Path, ui, log_path: Path, height: int = 720):
        super().__init__(daemon=True)
        self.items, self.out_dir, self.ui, self.height = items, out_dir, ui, height
        self.log_path = log_path
        self.done = 0
        self.failed: list[str] = []
        self.bytes = 0
        self.t0 = time.time()

    def path(self, lid: str) -> Path:
        return self.out_dir / f"{lid}.mp4"

    def run(self):
        import yt_dlp
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.ui.videos(len(self.items))
        for lid, yid in self.items:
            if self.path(lid).exists():
                self.done += 1
                self.ui.video_progress(self.done, f"{lid} already here")
                continue
            if not yid:
                self.failed.append(f"{lid}: no youtube_id in titles.tsv")
                continue

            def hook(d, lid=lid):
                if d["status"] == "downloading":
                    tot = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                    pct = f"{100 * d.get('downloaded_bytes', 0) / tot:.0f}%" if tot else ""
                    spd = f"{(d.get('speed') or 0) / 1e6:.1f} MB/s"
                    self.ui.video_progress(self.done, f"{lid} {pct} {spd}")
                elif d["status"] == "finished":
                    self.bytes += d.get("total_bytes") or 0

            opts = {"format": FORMAT.format(h=self.height), "outtmpl": str(self.out_dir / f"{lid}.%(ext)s"),
                    "merge_output_format": "mp4", "progress_hooks": [hook], "quiet": True, "noprogress": True,
                    "logger": _Quiet(self.log_path), "retries": 5, "fragment_retries": 5, "concurrent_fragment_downloads": 4}
            ok = False
            for attempt in range(2):
                try:
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        ydl.download([f"https://www.youtube.com/watch?v={yid}"])
                    ok = self.path(lid).exists()
                    if ok:
                        break
                except Exception as e:  # network hiccups: one retry, then record and move on
                    _Quiet(self.log_path).error(f"{lid}: {e}")
                    time.sleep(3)
            if ok:
                self.done += 1
            else:
                self.failed.append(f"{lid}: download failed (see {self.log_path.name})")
            self.ui.video_progress(self.done, f"{lid} {'✓' if ok else '✗'}")
        self.ui.video_progress(self.done, "all done" if not self.failed else f"{len(self.failed)} failed")


# ---------------------------------------------------------------------------- alignment
def fetch_auto_captions(youtube_id: str, dest: Path, log_path: Path) -> Path | None:
    import yt_dlp
    dest.parent.mkdir(parents=True, exist_ok=True)
    opts = {"skip_download": True, "writeautomaticsub": True, "subtitleslangs": ["en"], "subtitlesformat": "json3",
            "outtmpl": str(dest.with_suffix("")), "quiet": True, "logger": _Quiet(log_path)}
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([f"https://www.youtube.com/watch?v={youtube_id}"])
    hits = sorted(dest.parent.glob(dest.with_suffix("").name + "*.json3"))
    return hits[0] if hits else None


def _caption_words(json3: Path):
    words = []
    for ev in json.loads(json3.read_text(encoding="utf-8")).get("events", []):
        t0 = ev.get("tStartMs", 0)
        for seg in ev.get("segs") or []:
            for w in re.findall(r"[a-z0-9']+", (seg.get("utf8") or "").lower()):
                words.append((w, (t0 + seg.get("tOffsetMs", 0)) / 1000))
    return words


def align_transcript(txt: Path, json3: Path) -> list[Sentence]:
    body = txt.read_text(encoding="utf-8").split("\n\n", 1)[-1]
    sents = [s for p in body.splitlines() for s in re.split(r"(?<=[.?!])\s+(?=[A-Z\"'(])", p.strip()) if s]
    cap = _caption_words(json3)
    cw = [w for w, _ in cap]
    tw, owner = [], []
    for i, s in enumerate(sents):
        for w in re.findall(r"[a-z0-9']+", s.lower()):
            tw.append(w)
            owner.append(i)
    times: list[float | None] = [None] * len(tw)
    for a, b, n in SequenceMatcher(None, tw, cw, autojunk=False).get_matching_blocks():
        for k in range(n):
            times[a + k] = cap[b + k][1]
    # interpolate unmatched words between matched neighbours
    known = [i for i, t in enumerate(times) if t is not None]
    if not known:
        raise ValueError("no words matched between transcript and captions")
    for i in range(len(times)):
        if times[i] is None:
            lo = max((k for k in known if k < i), default=None)
            hi = min((k for k in known if k > i), default=None)
            if lo is None:
                times[i] = times[hi]
            elif hi is None:
                times[i] = times[lo]
            else:
                times[i] = times[lo] + (times[hi] - times[lo]) * (i - lo) / (hi - lo)
    out = []
    for i, s in enumerate(sents):
        idx = [k for k, o in enumerate(owner) if o == i]
        if not idx:
            continue
        start = times[idx[0]]
        out.append([start, s])
    res = []
    for j, (start, s) in enumerate(out):
        end = out[j + 1][0] if j + 1 < len(out) else start + max(2.0, 0.4 * len(s.split()))
        res.append(Sentence(len(res), round(start, 3), round(max(end, start + 0.5), 3), s))
    return res


def write_srt(sentences: list[Sentence], path: Path):
    def ts(t):
        h, r = divmod(t, 3600)
        m, s = divmod(r, 60)
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s % 1) * 1000)):03d}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(f"{i + 1}\n{ts(s.start)} --> {ts(s.end)}\n{s.text}\n" for i, s in enumerate(sentences)),
                    encoding="utf-8")
