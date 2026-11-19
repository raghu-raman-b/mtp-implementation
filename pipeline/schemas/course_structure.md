# Stage 4f: `stage_4f_course_structure/course_structure.json`

Written by `scripts/s4f_course_structure.py` (Gemma 4 12B, one call per segment). The lecturers' own sentences about
the course itself (structure, logistics, objectives), chosen by the model, copied by code.

```
{"run": {...}, "statements": [...]}
```

**run**: `stage`, `model`, `prompt_sha256`, `think_budget`, `date`, `finished`, `seconds`, `lectures` (list of lecture
keys), `segments` (asked), `calls`, `retries`, `thinking_off_segments` (segments re-asked with thinking off after a
cut-off answer), `statements` (count), `failed` (segments whose attempts all failed the code check; they have no
statement).

**statements[]** (ordered by lecture, then time):

| field | meaning |
|---|---|
| `id` | `CS0001`, `CS0002`, ... (cited by QA like a fact ID) |
| `lecture` | lecture key, a string (`"1"`) |
| `segment` | segment ID from stage 1b, `"<lecture>/S<k>"` |
| `sentence_ids` | the chosen sentence IDs (`"1/40"`); consecutive neighbours in the segment merge into one statement |
| `start`, `end` | seconds: first sentence's start and last sentence's end (stage 0a times) |
| `time_from` | `"sentences"`, or `"segment"` when a boundary time was null in 0a and the segment's own start/end was used |
| `text` | the sentences joined, verbatim from the stage 1c segment text; never reworded |

**Read by**: the QA tool `course_structure(lecture=None)` (`qa/tools.py`, via `Knowledge.course_structure()`). It
lists each statement as `[CS0001] lecture N, m:ss: text`, for one lecture when given.

**File missing**: the tool returns "The course structure is not available." (`found: false`, `available: false`), so
the answer says it is not available; nothing else breaks. `launcher.py check` warns about it. A file with no
statements for the asked lecture gives "The lecturers say nothing about the course itself".

Beside it: `course_structure.md` (review list), `llm/` (cache and call log), `history/run1/` (first run).
