# Stage 4f: `stage_4f_course_structure/course_structure.json`

Written by `scripts/s4f_course_structure.py` (Gemma 4 12B, one call per segment). The lecturers' own sentences about
the course itself (structure, logistics, objectives), chosen by the model, copied by code.

```
{"run": {...}, "statements": [...]}
```

**run**: `stage`, `model`, `prompt_sha256`, `think_budget`, `date`, `finished`, `seconds`, `lectures` (list of lecture
keys), `segments` (asked), `calls`, `retries`, `thinking_off_segments` (segments re-asked with thinking off after a
cut-off answer), `statements` (count), `failed` (segments whose attempts all failed the code check; they have no
statement), `manual_additions` (IDs of statements added by hand after the run, see `source`; only when there are some).

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
| `source` | optional: only on a statement added by hand, e.g. `"manual (user, 2026-11-19)"`; model-chosen statements have none. `CS0029` (lecture 1, `1/2`-`1/3`, the lecturer introducing themselves) is such a statement; manual statements are appended, so they come after the ordered ones |

**Read by**: the QA tool `course_structure(lecture=None)` (`qa/tools.py`, via `Knowledge.course_structure()`). It
returns two blocks. First the official NPTEL course page, read from `input/<course>/input/course.json` (via
`scripts/course_meta.py`): a header with title, platform and institution, then items with their own IDs: `[CP01]
Instructor` (name, department, institution, about), `[CP02] Prerequisites`, `[CP03] Intended audience`, `[CP04] Course
outline`, and one per syllabus entry `[CP11] Week 1 - <theme>: topics` (CP11, CP12, ... in syllabus order). Then the
lecturers' statements, each as `[CS0001] lecture N, m:ss: text`. With `lecture` given only that lecture's statements
are listed (no course page). QA cites a CP item as "(course page)" (citation: `lecture`, `segment`, `start`, `end`
null, `source` "course page", `text` "<label>: <text>"; the viewer shows a "Course page" chip that is not a link).
Without `course.json` the tool lists the statements only.

**File missing** (both the statements file and course.json): the tool returns "The course structure is not available." (`found: false`, `available: false`), so
the answer says it is not available; nothing else breaks. `launcher.py check` warns about it. A file with no
statements for the asked lecture gives "The lecturers say nothing about the course itself".

Beside it: `course_structure.md` (review list), `llm/` (cache and call log), `history/run1/` (first run).
