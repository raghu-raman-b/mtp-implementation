# The answer stream: `POST /api/ask_stream` events

`viewer/serve.py` answers `POST /api/ask_stream` (`{"question": str, "lecture": str | null}`) with one JSON object per
line (`application/x-ndjson`, chunked, each line sent as soon as it exists). The events come from
`qa.answer_stream()` (`qa/answer.py`); the viewer passes them on unchanged and makes sure the last one is `done`.

This page is for the chat screen that shows "what the model is doing". Rules for a reader:

- **Ignore event kinds you do not know**, and fields you do not know. New ones may be added; none will be removed.
- Every event has `"event"` and `"t"`: seconds since qa received the question (float, ms precision). `t` never
  goes down. (`t` is measured in the viewer process; the browser adds only the local hop, under a millisecond.)
- The fields marked **(original)** are the ones the page read before this schema (2026-11-17); they keep their
  meaning.
- No event carries a fact ID or a raw citation: `label` texts and `draft` texts are ready to show.

## Order

```
round(0) [thinking ...] { call step }*            # round 0: the model chooses tools (thinking on)
round(1) [answer_start draft* reset] { call step }*   # more tool rounds when the model asks for more
...
round(n) answer_start draft draft ... draft       # the answer being written
done
```

A question the model answers without tools: `round(0)`, `thinking`..., `answer_start`, drafts, `done`.
At most 6 rounds; the last one (or the one after every search found nothing close) is `final: true`.

## Events

### `round`: a request goes to the model
`{"event": "round", "t", "round": 0, "final": false, "thinking": true}`

- `round`: 0, 1, 2 ... The first `round` event comes at once (t ~ 0.01 s): the earliest sign of progress.
- `final`: true when this round must answer (no more tools may be called): "Writing the answer..." can show now.
- `thinking`: whether the model thinks first in this round (round 0 only, with the shipped settings; never when
  `think=False` / `$QA_THINK=0` was set).

### `thinking`: the model is thinking (before it chooses tools)
`{"event": "thinking", "t", "round": 0, "chars": 640}`

At most one every 0.5 s while thinking streams. `chars`: the length of the thinking so far (about 4 characters per
token). The thinking text itself is never sent.

### `call`: a tool is about to run
`{"event": "call", "t", "round": 0, "index": 0, "tool": "check_concept", "args": {"names": ["HMD"]}}`

- `index`: the step's number in this answer (0, 1, 2 ... across rounds); its `step` event has the same index.
- `args`: what the model asked for (a dict; a string when the model sent arguments that are not JSON).
- Several calls of one round come as `call, step, call, step` (they run one after the other; each takes 0-0.7 s).

### `step`: the tool has run
```json
{"event": "step", "t": 1.62, "round": 0, "index": 0,
 "tool": "check_concept", "args": {"names": ["HMD", "vergence lens"]},
 "result_summary": "card of head-mounted display (matched 'HMD', acronym); 10 facts | unknown name 'vergence lens'; closest fact 0.21 (low)",
 "label": "Concepts loaded: head-mounted display (lecture 14), vergence lens (not in the course)",
 "found": true, "seconds": 0.004,
 "detail": {"names": ["HMD", "vergence lens"], "known": 1, "facts": 15, "lectures": ["14", "15"],
            "items": [{"name": "HMD", "known": true, "matched": "HMD", "how": "exact", "lecture": "14",
                       "concepts": [{"id": "C0004", "name": "head-mounted display", "defined": true, "defined_in": ["14"]}],
                       "facts": 10, "lectures": ["14", "15"], "label": "Looked up ..."},
                      {"name": "vergence lens", "known": false, "lecture": null, "suggestions": [], "facts": 5,
                       "lectures": ["15"], "best_score": 0.21, "close": false, "label": "..."}]}}
```

- (original) `tool`, `args`, `result_summary` (developer wording, shown in developer mode).
- `label`: one display line in plain words, no IDs. For `check_concept` it names each concept ("Concepts loaded:
  immersion (lecture 4), presence (lecture 4)"; "Concept loaded: ..." for one name; an unknown name reads "name (not
  in the course)"); for `course_structure`: "Course structure read: 5 statements from lectures 1 and 2" (or "The course
  structure is not available"). The viewer shows "Loading concepts: immersion, presence" from the call's `args`
  while it runs.
- `found`: true = the course has something close; false = nothing close (an unknown name whose closest facts score
  low, a search with no close fact: the answer will say the course does not cover it); null = not a search, or the
  call failed.
- `seconds`: how long the tool took (the fact search embeds the query: on the instance through the tunnel, ~1 round
  trip; the other tools take milliseconds).
- `detail`, per tool (lecture numbers are strings, in course order: "4", "24b", "tut_1"):

| tool | `detail` fields |
|---|---|
| `check_concept` | `names` (as asked, de-duplicated, in order), `known` (how many are concepts of the course), `facts` (total facts shown), `lectures` (of those facts), `items`: one per name, in order. A known name: `name` (as asked), `known: true`, `matched`, `how` ("exact", "plural", "close"), `concepts`: [{`id`, `name`, `defined`, `defined_in` (lectures)}] (a name may stand for up to 3 concepts), `facts`, `lectures`, `lecture` (where it is defined; else its first lecture), `label`. An unknown name: `name`, `known: false`, `suggestions`, `facts` (closest facts shown), `lectures`, `best_score` (0-1), `close` (best_score over the cut-off 0.55), `lecture: null`, `label`. `found` is false only when every name is unknown and nothing close |
| `fact_lookup` | `query`, `wordings` (how many wordings were searched), `lecture` (the lecture it was limited to, or null), `facts`, `lectures`, `best_score`, `close` |
| `lecture_dependencies` | `lecture`, `title`, `revise` (lectures to revise first, most needed first), `relies_on` (concept names, most used first, up to 8), `general` (course-wide concepts it uses), `in_passing` (count), `assumed` (count) |
| `lecture_overview` | `lecture`, `title`, `segments`, `objectives`, `introduced` (counts) |
| `course_goals` | `goals` (count) |
| `course_structure` | `statements` (count), `lectures` (those the statements are from), `lecture` (the one asked for, or null), `available` (false: the stage's file is missing; `found` false) |
| any, on a bad call | `error` (the message; the model is told and usually corrects itself) |
| any, repeated call | `repeated: true` (label "Already looked that up") |

### `answer_start`: the model starts writing text
`{"event": "answer_start", "t": 2.9, "round": 1, "forced": false}`

Comes just before the round's first `draft`. `forced`: the round was `final` (tools were not allowed). If the round
then ends in tool calls after all (rare: "Let me look that up..."), a `reset` follows and a later round sends
`answer_start` again.

### `draft`: the answer so far (original)
`{"event": "draft", "t": 3.1, "text": "A head-mounted display (HMD) is ... (lecture 14, 12:26)"}`

The whole answer so far, Markdown, citations already written as "(lecture 14, 12:26)"; a half-written citation or
the closing COVERED line is held back. Each draft **replaces** the one before (the tidying can move a label), so
render the latest one. Drafts come per streamed token piece (tens per second).

### `reset`: the text so far was not the answer (original)
`{"event": "reset", "t", "round": 1}`: clear the draft.

### `done`: the answer (original), always last
```json
{"event": "done", "t": 5.4,
 "result": {"answer": "...", "citations": [{"fact", "lecture", "segment", "start", "end", "text"}],
            "steps": [{"tool", "args", "result_summary"}], "covered": true, "available": true},
 "timing": {"think": true, "first_step": 1.62, "answer_start": 2.9, "first_draft": 3.1, "total": 5.4,
            "rounds": [{"round": 0, "model_s": 1.5, "ttft_s": 0.31, "in": 1906, "out": 52, "think_chars": 120,
                        "cache_n": 1880, "prompt_n": 26, "slot": 0, "tools": [{"tool": "check_concept", "s": 0.004}]}]}}
```

- `result`: exactly what `POST /api/ask` answers for the question (`error` when something failed; `available`
  false when qa is not installed).
- `timing` (absent when qa failed before answering): `think` (whether round 0 was allowed to think), when the stream first showed each thing, and per model round
  its seconds, time to the first streamed piece (`ttft_s`), prompt and output tokens, and on llama.cpp the prompt
  tokens reused from the cache (`cache_n`) and computed (`prompt_n`), and the server slot. For developer mode.

## Timing to expect (demo questions, through an SSH tunnel; analysis/demo/remote_setup.md)

`round` at ~0.01 s; first `step` 1-3 s; `answer_start` / first `draft` 2-5 s; `done` 4-10 s.
