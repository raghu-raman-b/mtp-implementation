# Judging learning activities (blind)

Each file in `packets/` is one lecture of the NPTEL course "Foundation for Virtual and Augmented Reality Systems":
its title, goal and objectives, the titles of the earlier lectures, then units. A unit is one kind of activity; it
holds three or four sets (X, Y, Z, W) made for the same lecture by different systems, in no particular order. The
lecture's transcript (the lecturer's words, human-written subtitles, sentences numbered) is in
`transcripts/lec_<n>.txt`: read it before judging the lecture.

Judge every item of every set on its own (do not rank the sets). For each item answer:

- `correct` (true / false): what the item marks as right is right: the quiz option marked correct (and only it),
  the odd item and its reason, the order of the steps, the reference answer, the recap point or text, the recall
  answer, the concept-map edge as stated (from --label--> to). Judge by the transcript and sound subject knowledge.
- `grounded` ("yes" / "partly" / "no"): the item is taught in this lecture's transcript ("partly": some of it is,
  some is added from elsewhere). For a recall item (shown before the lecture, on a concept from an earlier
  lecture): "yes" when this lecture uses the concept and the named earlier lecture, by its title, is a plausible
  place where it was taught.
- `distractors` ("good" / "weak" / "poor" / null): quiz wrong options and odd-one-out items only (null otherwise).
  good: tempting to a learner who half understood, clearly wrong to one who understood, same form as the key;
  weak: some can be struck out without understanding, or the key stands out by its form; poor: absurd or off-topic
  options, or more than one defensible answer.
- `goals` ("yes" / "partly" / "no"): the item serves the lecture's goal or one of its objectives as stated in the
  packet (not trivia, not off the lecture's point).
- `cross_lecture` ("yes" / "no" / "wrong"): "yes" when the item correctly links this lecture to another lecture of
  the course (a concept taught earlier, a lecture named rightly), "no" when it makes no such link, "wrong" when it
  makes a link that is false (a wrong lecture, a concept the lecture does not use).
- `reason`: one short sentence, required whenever an answer is not the best one (false, "partly", "no", "weak",
  "poor", "wrong").

## Output

One JSON object per line, one line per item, in a file `judgments.jsonl` (write it next to this file):

{"unit": "U01", "item": "X3", "correct": true, "grounded": "yes", "distractors": null, "goals": "partly", "cross_lecture": "no", "reason": "..."}

- `unit`: the unit's ID as given ("U01"); `item`: the item's label as given ("X3").
- `correct`: true or false; `grounded`: "yes" | "partly" | "no"; `distractors`: "good" | "weak" | "poor" | null;
  `goals`: "yes" | "partly" | "no"; `cross_lecture`: "yes" | "no" | "wrong"; `reason`: a string ("" when nothing
  is wrong).
- Every item of every unit gets exactly one line. No other output in the file.
