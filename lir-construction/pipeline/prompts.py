"""Prompt texts. Each has an ID and a version, recorded in origin.

Segment-level prompts are ordered as: shared role line, then the segment transcript, then the task. Calls on the
same segment then share a prompt prefix, which the server's prefix cache reuses.
"""
ROLE = "You are helping turn a recorded university lecture into a guided learning experience for students."


def segment_block(course: str, title: str, transcript: str) -> str:
    return (f"{ROLE}\n\nCourse: {course}\nLecture: {title}\n\n"
            f"Transcript of one segment of the lecture, one sentence per line with its sentence ID in brackets:\n"
            f"{transcript}\n\n")


# ---------------------------------------------------------------- stage 1
# The best-performing prompt from event-segmentation/compare/REPORT.md (WD 0.09 at temperature 0), unchanged.
SEGMENT = ("segment.standalone", "3", """Below is the transcript of a lecture video, one sentence per line, each with its number in brackets.

Split the lecture into segments. Find the apt boundaries: the points where the instructor has completed an \
instructional goal or a topic and moves on to the next one.

Each segment must stand alone: a learner who starts watching at the first sentence of any segment, without \
having seen what came before, must be able to follow it. Cut only at a logically concluded point, after the \
instructor has finished the thought, never while he is in the middle of explaining something. A question and \
the discussion of that question belong in the same segment. Do not cut at every change of example or \
sentence-level aside; prefer fewer, complete segments over many fragments.

Answer with a JSON list of the sentence numbers that START a new segment (do not include sentence 1), in \
order, and nothing else. Example of the format: [14, 52, 97]

Transcript:
{transcript}""")

# ---------------------------------------------------------------- stage 2
ANNOTATE = ("annotate.subgoal_points", "2", """Task: describe this segment.
- subgoal: what the learner achieves in this segment, as one short phrase that starts with a verb, for example \
"Explain why ...", "Derive ...", "Compare ...", "Apply ...". Be specific to this segment, at most 15 words.
- content_type: the one type that best describes what the instructor mainly does in this segment:
  motivation (why the topic matters), definition (introduces what something is), mechanism_explanation (how or \
why something works), derivation_or_proof, procedure_or_algorithm (steps to follow), worked_example (solves a \
specific instance), comparison, application_or_demo, recap (summarises earlier material), discussion (questions, \
opinions, course logistics).
- key_points: 2 to 5 key points. Each is one atomic, self-contained statement of something the segment teaches \
(a fact, claim, step or result), understandable without the transcript, with the IDs of the sentences that state it.
  For each key point, about: "subject" if it is about the subject matter itself, or "course" if it is about the \
course, the lecture or its organisation (what the course covers, its goals, structure, schedule, assignments or \
the instructor's plans). Write subject key points as facts of the subject ("Optical flow is ..."), not as \
reports of the lecture ("The lecture explains that ...").
Use only what is said in this segment.

""")

TERMS = ("annotate.terms", "3", """Task: list the key terms a student should learn from this segment, and the other concepts it relies on.
- key_terms: up to 5 terms of the subject that the instructor explains in this segment: concepts a student must \
understand to follow this course, the kind that belong in the subject's glossary. Leave out generic words (such as \
"system", "example", "technology", "approach", "application areas", "categories", "forecasts"), passing mentions \
that the instructor does not explain, course logistics, and names of people, institutions or courses. Never list \
an abbreviation on its own: write the full name with the abbreviation in brackets, for example \
"Augmented reality (AR)".
  For each key term give:
  - term: the name as the instructor says it, a short noun phrase in the singular.
  - definition: one or two self-contained sentences that start with the term itself and say what kind of thing \
it is and what sets it apart from related ideas, for example "Optical flow is the apparent motion of the scene \
that a viewer perceives when they or the objects around them move." Write it in your own clear words, faithful \
to what the instructor says: do not copy the instructor's spoken sentences and do not repeat yourself. A student \
who has never heard the term must understand what it is from the definition alone. Never start with "It", "This", \
"These" or "They", never just spell out an abbreviation, and do not define the term with its own words. One \
concept per term: never list several concepts as one term.
  - sentence_ids: the IDs of the sentences where it is defined or explained.
- used_concepts: up to 8 other technical concepts of the subject that the segment uses or mentions without \
explaining them (short noun phrases; no generic words, people, institutions or courses).
If the segment explains no subject terms, return an empty key_terms list.""")

# ---------------------------------------------------------------- stage 3
GOALS = ("goals.hierarchy", "1", """{role}

Lecture: {title}
The lecture is split into these segments, in playback order, each with what a learner achieves in it:
{subgoals}

Task: build the lecture's goal hierarchy.
- objectives: group the segments into {lo} to {hi} learning objectives. Each objective covers a contiguous run of \
segments (no gaps, no reordering), and every segment belongs to exactly one objective. Write each objective as \
what the learner will be able to do, starting with an action verb in lower case, for example "explain how ..." or \
"compute ...". It will be shown after the words "You'll be able to".
- lecture_goal: one sentence that starts with a verb: the overall goal of the lecture.""")

COURSE_GOALS = ("goals.course", "1", """{role}

Course: {course}
Its lectures, each with its overall goal:
{lectures}

Task: write {lo} to {hi} course-level goals that summarise what a learner gains from these lectures, bottom-up \
from the lecture goals. Each goal starts with a verb and lists the IDs of the lectures that serve it. Every lecture \
must serve at least one goal.""")

# ---------------------------------------------------------------- stage 4
SAME_CONCEPT = ("state.same_concept", "1", """Two terms from the same course:
A: "{a}" ({a_where}): {a_def}
B: "{b}" ({b_where}): {b_def}

Do A and B name the same concept (synonyms, abbreviations, or spelling variants), so a learner should treat them as \
one idea? Answer same=false if one is a special case, a part, or an example of the other.""")

EDGES = ("state.edges", "3", """{role}

Course: {course}
Lecture {lecture_id}: {title}

Concepts in this lecture:
{concepts}

Concepts from earlier lectures that may be related:
{earlier}

Evidence from this lecture, one statement per line with its sentence IDs:
{evidence}

Task: list the relationships between these concepts that this lecture states or clearly implies.
Every edge reads as a sentence "src rel dst", and that sentence must be true. Relation types:
- prerequisite_of: src must be understood before dst (e.g. "derivative prerequisite_of gradient")
- part_of: src is a component of dst (e.g. "encoder part_of transformer")
- example_of: src is an instance of the more general dst (e.g. "virtual reality example_of extended reality"; \
the specific thing is src, the general category is dst)
- contrasts_with: src is set against dst
- leads_to: src causes or produces dst
- used_in: src is used as a tool or step in dst
src and dst must be two different concepts.
label: a link phrase of 2 to 5 words that sits between the two concept names on a concept map, read as \
"src label dst", e.g. "is a kind of", "is computed by", "is needed for". "src label dst" must read as a complete, \
grammatical sentence: the label never ends in "and", "or", "the", "a" or "between". Do not repeat the concept \
names in the label.
evidence: the sentence IDs from the evidence list that support the edge.
At least one end of every edge must be a concept from this lecture. Give at most 20 edges, the most important first. \
Do not invent relations the lecture does not support.""")

# ---------------------------------------------------------------- stage 5
RECALL = ("primer.recall", "2", """{role}

The learner is about to watch lecture {lecture_id}: {title}
It builds on these concepts from earlier lectures:
{items}

Task: for each earlier concept, write
- question: a short recall question that makes the learner retrieve what the concept means or how it works, \
in the subject's own terms (the question must not give the answer away, and must not just ask what an \
abbreviation stands for),
- recap: one or two sentences that answer the question and remind the learner what the concept is.

""")

QUIZ = ("active.quiz", "3", """Task: write a short quiz that checks whether a learner understood the subject matter of this \
segment. These are the segment's key points, by ID:
{points}

Write {lo} to {hi} questions: as many as the segment has ideas worth testing, and no more. Do not pad the quiz \
with trivial questions. Each question tests one key point (give its ID), and no two questions test the same point.
For each question choose the item type that suits its point:
- multiple_choice: a question with exactly 4 options and exactly one correct option, the correct option first \
(the order is shuffled later). Wrong options are plausible misconceptions of similar length and style. No "all of \
the above" or "none of the above". correct_answer: "first option".
- true_false: a statement that the segment makes clearly true or clearly false; correct_answer: "True" or "False".
- yes_no: a question with a clear yes or no answer; correct_answer: "Yes" or "No".
explanations: one sentence per option saying why it is right or wrong (multiple choice: 4, in option order; \
true/false: 2, for True then False; yes/no: 2, for Yes then No).

Rules:
- Test understanding of the subject: what something is, how or why it works, how ideas relate, when to use it. \
Never test what the course, the lecture or the instructor says, covers or plans, and never write "according to \
the lecture" or "does the lecture describe". Do not ask what an abbreviation stands for.
- Every question must be answerable from this segment alone.
- Do not copy the key point. Multiple-choice and yes/no questions end with "?"; a true/false item is a statement.""")

SUMMARY = ("active.summary", "2", """Task: write an interactive summary of this segment for a learner who has just watched it.
- recap: 2 to 3 sentences in plain language, nothing that is not in the segment, and do not start with "In this \
segment".
- review: one check-yourself question for each of these key points, with a short answer (1 or 2 sentences) that \
the learner can reveal after thinking. The question asks about the subject (not about the lecture) and does not \
give the answer away.
{points}
{explain}""")

OQ_TASKS = {
    "fill_in_steps": "The question shows the steps of the derivation or procedure in this segment with one or two key "
                     "steps replaced by '___', and asks the learner to fill in the missing steps and say why each is "
                     "needed.",
    "compare_contrast": "The question asks the learner to compare and contrast {pair}: how they are similar, how they "
                        "differ, and when each applies.",
    "self_explanation": "The question asks the learner to explain, in their own words, why or how the mechanism "
                        "described in this segment works.",
    "apply_new_case": "The question describes a new situation, different from the example in this segment, and asks "
                      "the learner to apply the same idea or method to it.",
    "troubleshooting": "The question describes a case where the procedure in this segment goes wrong in the way the "
                       "instructor warns about, and asks the learner to diagnose the problem and fix it.",
    "explain_to_someone": "The question asks the learner to explain the main idea of this segment to a classmate who "
                          "missed the lecture.",
}

OPEN_Q = ("constructive.open_question", "3", """Task: write one open-ended question for the learner. {task}
Write the question itself, addressed to the learner (for example "Explain ..." or "Your friend asks ..."), not \
instructions about writing a question. The learner never sees segment numbers, so name the topic itself instead of \
saying "this segment".
Then write a reference answer of 3 to 6 sentences based only on the segment, and 3 to 5 key points that a good \
answer must contain. Each key point is one short statement with 2 to 6 keywords: single words or short phrases that \
appear word for word in your reference answer (at most 3 words each) and that a learner covering the point would likely use.""")
