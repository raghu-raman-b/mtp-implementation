# Design C (Signal): the chosen design (user, 2026-11-18)

Source: the design canvas https://claude.ai/artifact/UDrY88AbBdhTbKoRHQ3HDm (row C). These are static mockups
(`.dc.html`: a design-canvas format with `<sc-for>`/`<sc-if>` templating and `{{holes}}` filled by the script block at
the bottom of each file); read them for layout, type, colour, spacing and motion, not as code to copy.
`B-Ask.dc.html` is design B's Ask screen, kept for its raw tool-call trace.

## The user's changes to the mockups (2026-11-18)
- Home (C-Roadmap): remove the "12 weeks / 63 lectures / 8 goals" stats and the whole "Course goals" section; keep the
  12-week route. Keep the dev mode toggle.
- Player (C-Player): subtitles centred on screen (centred text, centred block). When an activity shows: subtitles go
  away automatically, the video is blurred, the video controls are hidden; the activity takes their place.
- Everything else as designed.

## Designer's notes from the canvas
### sC
Signal: precision and momentum (recommended).

Idea: a light, airy product with one vivid cobalt and a lime highlight for progress. Hairline borders, tight type, generous space. The player goes dark glass so the video still dominates. Reads as a modern tool, not a course site.

Type: Geist (everything; tight tracking at large sizes), Geist Mono (times, IDs).

Colour: ground #F5F6F8, white cards, ink #0E1116, muted #596171, cobalt #2E5BFF, lime #C8F169 (fills only, always with dark text).

Motion: quick and springy, 180-220 ms, staggered. Recap cards expand and their points reveal one by one; the Ask steps tick in along a progress rail; quiz options settle with a small spring.

### mC
Motion (Signal, Activities): sections stagger in (40 ms apart). Crossword: the active word gets a cobalt band; each correct word fills lime from left to right in 180 ms; the clue list ticks the clue and moves it down. Completing the grid: the lime fills ripple once across all words.

### kA
Ask (all three rows): click a sample question to play it. The steps are the real stream events of the saved answers in qa/answers.jsonl: one {event: step} per tool call (check_concept, lecture_dependencies) with its real result_summary, then {event: draft} streams the answer, then {event: done}. Citation chips are the answer's own (lecture N, m:ss) citations and open the player at that moment. Folio shows plain-language steps; Theatre also shows the raw tool call; Signal shows a progress rail.

### nPh
Phone: the player is the whole screen; controls stay thumb-reachable at the bottom. Tap a caption sentence to save it (a toast shows the sentence ID and time). Activities rise as a bottom sheet over the paused video.
