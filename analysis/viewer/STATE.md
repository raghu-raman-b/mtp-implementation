# Viewer speed work: state at the pause (2026-11-17, 10:50 IST)

Branch `worktree-agent-a761733a118c47330`. main is merged in. Nothing is pushed.

## Requirements
1. User, this morning: the live demo was choppy and slow, so make the viewer feel instant and smooth. Deadline: ready to merge by 13:30 IST.
2. Added later (coordinator): on demo day the viewer runs on the cloud instance and the browser reaches it through `ssh -L 8765:127.0.0.1:8765`, assuming 100-250 ms RTT and limited, variable bandwidth. This means:
   - few requests per page;
   - gzip, ETag and 304 on everything, and long caching for static files (version query);
   - video measured through a tunnel and made smooth, with a switch that prefers YouTube;
   - /api/ask shows progress at once and never blocks the page;
   - "through an SSH tunnel" numbers go into perf.md.

## Done (in this commit, not yet re-tested by the smoke test)
- **serve.py**
  - Lean routes from WIP 1f5b0b6 (memo cache, gzip, ETag).
  - `/api/view/<key>` has a new `before` field (the lecture-graph links into the lecture, with their concepts).
  - `/api/glossary` entries have a new `linked` field.
  - `/data/*` files are served cached, with gzip and ETag (`send_static`).
  - `index.html` is served with `?v=<hash>` on every /static file. Versioned static files get `Cache-Control: public, max-age=31536000, immutable`.
  - New flag `--prefer-youtube`; `/api/home` carries `prefer_youtube`.
  - Video:
    - an open Range (`bytes=N-`) is answered with at most 4 MB (`--video-chunk-mb`);
    - responses carry ETag and Last-Modified;
    - the server paces sending to 2x the bitrate after the first 1 MB (`--video-pace`, 0 turns it off). The bitrate comes from the MP4's mvhd duration (`mp4_duration`), or else from the lecture length. Pacing keeps the tunnel from queueing video, so seeks and page requests are not stuck behind it.
- **app.js**
  - Uses only the lean routes. It no longer loads the four big knowledge files (9.6 MB).
  - One concept and fact cache (`S.cc`, `S.fc`), filled by every payload.
  - Requests are cached as promises (`cget`).
  - Lectures load lazily (`lecture(key)` → `/api/view`). The neighbours are prefetched in idle time, and a lecture card is prefetched on hover or focus.
  - Tabs are built once and kept. Each map view (key / all by part) is laid out once and kept; the other view is pre-laid-out in idle time. A view that is not laid out yet shows "Arranging…" at once, keeping its height.
  - The glossary renders progressively (60 entries first, then slices), search is debounced, and there is no client-side sort.
  - Map activities and crosswords are drawn when scrolled near (IntersectionObserver).
  - Unresolved activities show only in dev mode (`.dev-only`).
  - render() keeps the old page and shows the spinner only after 120 ms, and drops stale results.
  - Concept map + explorer requests go out in parallel.
  - Ask: an elapsed-time progress line, and "Answer ready" on the Ask button if the drawer was closed.
  - `?yt=1` / `?yt=0` sets the YouTube preference (kept in localStorage).
- **index.html**: preconnect to YouTube, preload `/api/home`, scripts deferred.
- **style.css**: `.dev-only`; `content-visibility` on glossary entries; `.ask button.ready`.

## Numbers so far (tools in analysis/viewer/tools/)
Setup: headless Chrome 157 through CDP (`perf.mjs`), with YouTube blocked in the page timings. Base = main's viewer (copy kept in the scratchpad); new = this branch.

**Local, 1x CPU**

| Step | Base | New |
|---|---|---|
| First visit to home | 129 ms, 9636 kB, 9 requests | 77 ms, 126 kB |
| Home again (warm cache) | 174 ms, 9636 kB downloaded again | 24 ms, 1 kB |
| Lecture 5 opened directly | 208 ms, 9.7 MB | 26 ms |
| Glossary | 225 ms of long tasks | 0 ms |
| Lecture 62 "all, by part" | 89 ms task | 69 ms (pre-built in idle later; back to key view 2 ms) |

**Base, emulated tunnel (20 Mbit/s, 60 ms) + 4x CPU**
- home cold: 4364 ms
- glossary: 867 ms of long tasks (max 565 ms)
- lecture 62 parts view: 360 ms task
- activities: 157 ms of tasks

The new code has NOT been run in this setup yet.

**Route sizes (warm, gzip)**

| Route | gzip | raw |
|---|---|---|
| home | 6.9 kB | |
| view/5 | 13.7 kB | |
| view/62 | 59 kB | 295 kB |
| glossary | 336 kB | 1.3 MB |
| coursemap | 8 kB | |
| concept C0002 | 32 kB | |
| review | 74 kB | |

- Every route takes 0.3-15 ms server-side.
- Warm-up builds everything in 0.4 s.

**Video through an emulated SSH tunnel** (`tunnel.py`: 200 ms RTT, 10 Mbit/s shared, 2 MB window; real `ssh -L` was not possible because there is no key login to localhost and no root for tc). Test file: 10 min of 720p at 1.6 Mbit/s, faststart (`L05.mp4` in the scratchpad, made with `ffmpeg -c:v libopenh264 -movflags +faststart`). Output files: `tools/video_new.txt` and `tools/video_base.txt`.

| Step | Base | New (paced) |
|---|---|---|
| Page start → video metadata | 9980 ms | 1893 ms |
| Page request 3 s into playback | 1808 ms | 224 ms |
| Segment click (seek) | 1875 ms | 576 ms |
| Citation link seek | 1771 ms | 500 ms |
| Total stall time | 4219 ms | 1630 ms |

- 40 s of continuous play across the 4 MB chunks: no stall.
- Seeking never reloads the video element (same element each time).
- A buffered seek takes 10 ms.

## Next steps (exact)
1. Run `python pipeline/tests/viewer_smoke.py` and fix anything broken. Then extend it:
   - `/api/home`, `/api/view/<k>` (including `before`), glossary `linked`, coursemap, concept, review;
   - index.html has `?v=` and the versioned static files are immutable;
   - an open range is capped at the chunk size (needs a fake video larger than 4 MB, or a small `--video-chunk-mb`);
   - gzip, and 304 on If-None-Match;
   - check that app.js does not fetch `/data/knowledge/concepts.json` (grep).
2. Check visually with headless screenshots: home, lecture 5 tabs, lecture 62 map (key and parts), course map, explorer, glossary, concept page, review, activities (lazy maps), dev mode on and off.
3. Re-run `perf.mjs` for the new code: local 1x, and the tunnel profile.
   - Change the tunnel profile in perf.mjs to 200 ms latency / 10 Mbit (the NET arg), or put `tunnel.py` in front and use 4x CPU.
   - Write `analysis/viewer/perf.md` with the before/after tables above plus the new runs, including a section "through an SSH tunnel".
4. Update the serve.py docstring: the `?v=` static caching, `--prefer-youtube`, `--video-chunk-mb`, `--video-pace`, pacing. Note in perf.md that real lecture MP4s should be faststart (`ffmpeg -movflags +faststart -c copy`).
5. Commit with message "viewer: ..." (ending with the Co-Authored-By line) and report.
6. Optional if time is left: segment-cut playback, and activities shown between segments.

## How to run the measurements again
- `python base_viewer/serve.py` is main's viewer. Recreate it with `git show main:pipeline/viewer/<f>` into a folder, then run it with `--root <worktree>/pipeline`.
- `python pipeline/viewer/serve.py nptel_vr --port 8782 --media <dir with L05.mp4>`
- `python analysis/viewer/tools/tunnel.py 8792 8782 --rtt-ms 200 --mbit 10`
- `SP=<scratch> node analysis/viewer/tools/perf.mjs http://127.0.0.1:8792 new 1`. Argument 4 is the CPU rate; argument 5 `tunnel` sets the network emulation. Set YT=1 to allow YouTube.
- `SP=<scratch> node analysis/viewer/tools/video.mjs http://127.0.0.1:8792 new-tunnel`
- Do not use `pkill -f` with the pattern in the same shell line: it kills the shell.
