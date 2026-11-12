# Activities: output contract (MVP, 2026-11-13)

Written by `pipeline/scripts/s5_activities.py` into `pipeline/output/<course>/activities/`; read by the viewer.
All IDs are the knowledge layer's (`knowledge/`, stage 4d): facts `4/S1/F2`, segments `4/S1`, concepts `C0042`,
relationships `R0107`, lectures by key ("4").

`activities/lec_<n>.json`:
```json
{"lecture": "4",
 "activities": [{"id": "4/A0", "kind": "quiz", "scope": "segment", "segment": "4/S1", "title": "...",
                 "data": {...}, "facts": ["4/S1/F0"], "concepts": ["C0003"]}]}
```
`scope` is "segment" (with `segment`) or "lecture" (`segment` null). `facts` and `concepts`: what the activity is built
from (every activity must be answerable from its facts). `data` by `kind`:

| kind | scope | data |
|---|---|---|
| `quiz` | segment | `{"questions": [{"question", "options": [4 strings], "answer": index, "explanation", "facts": [IDs]}]}` |
| `recap` | segment | `{"text": "...", "points": ["..."]}` |
| `recall` | lecture (before it) | `{"items": [{"concept": "C..", "prompt": "...", "answer": "...", "from_lecture": "1"}]}` |
| `open_question` | lecture | `{"questions": [{"question", "reference_answer", "key_facts": [IDs], "concepts": [IDs]}]}` |
| `concept_map` | lecture | `{"nodes": [{"id": "C..", "label": "..."}], "edges": [{"from": "C..", "to": "C..", "label": "...", "relation": "R.."}]}` |
| `complete_map` | lecture | concept_map's `nodes`, `edges` plus `"blanks": [{"edge": index, "hide": "label"\|"from"\|"to", "answer": "...", "options": [strings]}]` |
| `crossword` | lecture | `{"width", "height", "entries": [{"number", "answer": "UPPERCASE LETTERS ONLY", "clue", "row", "col", "direction": "across"\|"down", "concept": "C.."}]}` |
| `match_pairs` | lecture | `{"pairs": [{"left": "term", "right": "short definition", "concept": "C.."}]}` |
| `odd_one_out` | lecture | `{"items": [{"options": [4 strings], "odd": index, "reason", "facts": [IDs]}]}` |
| `put_in_order` | segment or lecture | `{"items": [{"title", "steps": ["in the correct order"], "facts": [IDs]}]}` |

`activities/course.json`: `{"spaced_review": {"cards": [{"concept": "C..", "front": "name", "back": "definition",
"lectures": ["1", "4"]}]}}` (the viewer schedules the cards per learner in the browser).

A kind may be missing for a lecture or segment when its material does not allow it (no steps: no `put_in_order`).

Additions (2026-11-13, requested by the viewer; everything above unchanged):
- Optional per-item `"facts": [fact IDs]` (for time links): on each `concept_map` and `complete_map` edge (the
  relationship's facts), each `crossword` entry and each `match_pairs` pair (the concept's definition facts). Present
  whenever the material gives them; always a subset of the activity's `facts`.
- `complete_map`: a blank that hides `from` or `to` hides a concept that appears on no other edge of the map, so the
  answer is not visible elsewhere (blanks on shared concepts hide the `label` instead).
