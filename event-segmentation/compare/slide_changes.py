#!/usr/bin/env python
"""Detect slide changes in a lecture video from frame differences + OCR.

    python compare/slide_changes.py <video.mp4> <work dir> [--step 2]

1. ffmpeg samples one frame per second.
2. Frame change: mean absolute grey-level difference between consecutive frames; a spike is a cut
   (speaker <-> slide, or slide <-> slide).
3. OCR (RapidOCR) every `step` seconds gives the on-screen text; frames with too little text are the
   speaker, not a slide.
4. A slide change is the first frame of a slide whose text differs from the last slide shown
   (word-set Jaccard < 0.5), placed on the frame-change spike that brought it on screen. Cutting back
   to a slide already on screen, or the speaker reappearing, is not a slide change.

Writes <work dir>/slide_changes.json.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

import cv2
import numpy as np

CUT = 8.0        # mean abs difference (0-255) that counts as a cut
MIN_WORDS = 4    # fewer OCR words than this: not a slide
SAME = 0.5       # Jaccard at or above this: same slide (builds, annotations, OCR noise)


def words(txts):
    return {w for t in txts for w in re.findall(r"[a-z0-9]{3,}", t.lower())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("work")
    ap.add_argument("--step", type=int, default=2)
    args = ap.parse_args()
    work = Path(args.work)
    frames_dir = work / "frames"
    if not frames_dir.exists():
        frames_dir.mkdir(parents=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", args.video, "-vf", "fps=1,scale=960:-2", "-q:v", "3",
                        str(frames_dir / "%05d.jpg")], check=True)
    frames = sorted(frames_dir.glob("*.jpg"))  # frame i shows second i + 0.5
    small = [cv2.resize(cv2.imread(str(f), 0), (160, 90)).astype(np.float32) for f in frames]
    diff = np.array([0.0] + [float(np.abs(small[i] - small[i - 1]).mean()) for i in range(1, len(small))])

    ocr_file = work / "ocr.json"
    ocr = json.loads(ocr_file.read_text()) if ocr_file.exists() else {}
    todo = [i for i in range(0, len(frames), args.step) if str(i) not in ocr]
    if todo:
        from rapidocr import RapidOCR
        engine = RapidOCR()
        for k, i in enumerate(todo):
            r = engine(str(frames[i]))
            ocr[str(i)] = list(r.txts) if r.txts else []
            if k % 100 == 0:
                print(f"ocr {k}/{len(todo)}", flush=True)
                ocr_file.write_text(json.dumps(ocr))
        ocr_file.write_text(json.dumps(ocr))

    changes, last, last_i = [], None, 0
    for i in sorted(map(int, ocr)):
        w = words(ocr[str(i)])
        if len(w) >= MIN_WORDS:
            if last is None or len(w & last) / len(w | last) < SAME:
                # the cut that brought this slide on screen: strongest frame change since the previous sample
                lo = max(last_i + 1, i - args.step * 3)
                j = lo + int(np.argmax(diff[lo:i + 1])) if i >= lo else i
                changes.append({"t": float(j), "frame_diff": float(diff[j]), "is_cut": bool(diff[j] >= CUT),
                                "text": " | ".join(ocr[str(i)])[:200]})
                last = w
            else:
                last = last | w if len(w) > len(last) else last  # keep the fullest build of the slide
        last_i = i
    out = {"video": args.video, "duration": len(frames), "step": args.step, "cut_threshold": CUT,
           "n_cuts": int((diff >= CUT).sum()), "cuts": [int(i) for i in np.where(diff >= CUT)[0]],
           "slide_frames": int(sum(len(words(v)) >= MIN_WORDS for v in ocr.values())), "ocr_frames": len(ocr),
           "changes": changes}
    (work / "slide_changes.json").write_text(json.dumps(out, indent=1) + "\n")
    print(f"{len(changes)} slide changes ({sum(c['is_cut'] for c in changes)} on a frame cut); {out['n_cuts']} cuts; "
          f"{out['slide_frames']}/{out['ocr_frames']} sampled frames show a slide")
    for c in changes:
        print(f"  {int(c['t'] // 60):02d}:{int(c['t'] % 60):02d}  diff={c['frame_diff']:6.1f}  {c['text'][:110]}")


if __name__ == "__main__":
    main()
