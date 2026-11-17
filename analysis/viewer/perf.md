# Viewer speed: before and after (2026-11-17)

Base: main's viewer before this branch (it loads the four big knowledge files, 9.6 MB, on every visit).
New: this branch (lean routes, gzip + ETag + 304, versioned static files cached for good, lazy lectures, kept tabs and
map views, chunked and paced video, streamed answers).

Setup: headless Chrome 157 driven over CDP (`tools/perf.mjs`); YouTube blocked in the page timings. Both viewers
served the MVP layer (`pipeline/output/nptel_vr`) with one local video (`L05.mp4`: 10 min of 720p at 1.6 Mbit/s,
faststart). Raw output: `perf.mjs` prints one line per step. "ms" = trigger until the page shows the thing; long tasks =
main-thread tasks over 50 ms (what makes a page feel stuck).

## Local, 1x CPU

| Step | Base | New |
|---|---|---|
| Home, first visit | 129 ms, 9636 kB | 73 ms, 128 kB |
| Home again (warm cache) | 174 ms, 9636 kB again | 26 ms, 1 kB |
| Lecture 5 opened directly | 208 ms, 9.7 MB | 27 ms, 1 kB |
| Lecture 5 to lecture 6 | | 17 ms |
| Lecture 62 "all, by part" map | 89 ms task | 86 ms (one 68 ms task; pre-built in idle when the tab waits) |
| Back to the key view | | 2 ms |
| Glossary | 225 ms of long tasks | 17 ms, no long task (144 kB) |
| Glossary search | | 100 ms (90 ms of it is the typing debounce) |
| Concept card | | 19 ms |
| JS heap after the tour | 18 MB | 13 MB |

## Through an SSH tunnel

The demo runs on a cloud GPU instance; the browser reaches it through `ssh -L 8765:127.0.0.1:8765`. A real `ssh -L` and
`tc netem` were not possible here (no key login to localhost, no root), so `tools/tunnel.py` stands in for it: a TCP
proxy where every connection shares one link (one bandwidth budget per direction, like one SSH connection), a delay
of RTT/2 on every chunk each way, and a 2 MB window per connection (SSH's channel window). Profile: **200 ms RTT,
10 Mbit/s**, plus **4x CPU throttling** (a modest laptop). Both viewers measured the same way, same session.

| Step | Base | New |
|---|---|---|
| Home, first visit | 9297 ms (9636 kB) | 1082 ms (128 kB; first paint 652 ms) |
| Home again (warm cache) | 8894 ms (9636 kB again) | 426 ms (1 kB: two revalidations, 304) |
| Lecture 5 opened directly | 9127 ms | 641 ms |
| Lecture 5 to lecture 6 | 1900 ms | 467 ms (two round trips; 0 when the idle prefetch got there first) |
| Lecture 6 to lecture 62 | 383 ms | 267 ms (58 kB instead of 195 kB) |
| Lecture 62 "all, by part" map | 285 ms, 366 ms task | 294 ms, 275 ms task (layout cost, not network) |
| Lecture 62 parts: click a concept | 83 ms, 165 ms task | 40 ms |
| Lecture 2 activities | 380 ms, 162 ms of tasks | 238 ms, no long task |
| Course map / explorer | 24 / 68 ms (already loaded in the 9.6 MB) | 235 / 251 ms (one round trip each, then kept) |
| Glossary | 309 ms + 882 ms of long tasks (max 575 ms: the page freezes) | 343 ms, no long task |
| Concept card | 21 ms | 222 ms (one round trip, 2 kB) |

What the numbers say: the base pays ~9 s on every visit (the 9.6 MB is downloaded again each time: no caching) and
then has everything; the new viewer shows the first page in about a second, a reload in under half a second, and
pays one round trip (~200-250 ms) the first time a page needs data it does not have, never again in that visit. The
remaining cost of the new viewer through the tunnel is round trips, not bytes.

### Video through the tunnel (`tools/video.mjs`, same profile without CPU throttling; `tools/video_*.txt`)

| Step | Base | New (4 MB chunks, paced at 2x bitrate) |
|---|---|---|
| Page start to video metadata | 9980 ms | 1893 ms |
| A page request 3 s into playback | 1808 ms | 224 ms |
| Segment click (seek) | 1875 ms | 576 ms |
| Citation link seek | 1771 ms | 500 ms |
| Total stall time in the run | 4219 ms | 1630 ms |

40 s of continuous play across the chunk boundaries: no stall. A seek never reloads the video element; a buffered
seek takes 10 ms. (Measured before the pause on this branch; the video code has not changed since.)

### Streamed answers through the tunnel (fake qa that streams over ~3 s: no model)

| | Local | Tunnel |
|---|---|---|
| `/api/ask_stream`: first step shown | 305 ms | 705 ms |
| first words of the answer | 826 ms | 1226 ms |
| done | 2989 ms | 3389 ms |
| `/api/ask` (blocking, same fake) | 2001 ms | 2406 ms |

Events pass through the tunnel as they are produced (chunked, no gzip, nothing buffered); the tunnel adds its round
trips (~400 ms incl. connection setup) once. With the real model the learner sees the steps, then the answer being
written, instead of a spinner for the whole answer.

## For the demo day

- **Videos must be faststart** (the `moov` box first), or the browser has to fetch the end of the file before it can
  play anything (one more seek through the tunnel). Check with `ffprobe -v trace in.mp4 2>&1 | grep -m2 -o "type:'\(moov\|mdat\)'"`
  (moov must come first); fix without re-encoding: `ffmpeg -i in.mp4 -c copy -movflags +faststart out.mp4`.
- If the link is slower than ~2x a lecture's bitrate, start the server with `--prefer-youtube` (or open the page with
  `?yt=1`): the browser then fetches video from YouTube directly, not through the tunnel.
- `--video-chunk-mb` (default 4) and `--video-pace` (default 2; 0 = off) tune the video; the defaults were measured
  above.
- Open the page once before the audience arrives: the static files are then cached for good (`?v=` + immutable), and
  the server's `--warm` / route warm-up has built every route (0.4 s).
- Start command against a synced layer: `python pipeline/viewer/serve.py nptel_vr --output <dir>/output
  --activities activities_v3 --warm` (`--output` also points qa at that layer).

## How to run again

See `STATE.md` ("How to run the measurements again"). Tools: `tools/perf.mjs` (page timings), `tools/video.mjs`
(video), `tools/tunnel.py` (the SSH tunnel stand-in), `tools/shots.mjs` (screenshots of every page, dev mode off and
on, into `shots/`).
