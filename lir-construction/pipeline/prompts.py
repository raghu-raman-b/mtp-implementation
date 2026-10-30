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
ANNOTATE = ("annotate.subgoal_points", "1", """Task: describe this segment.
- subgoal: what the learner achieves in this segment, as one short phrase that starts with a verb, for example \
"Explain why ...", "Derive ...", "Compare ...", "Apply ...". Be specific to this segment, at most 15 words.
- content_type: the one type that best describes what the instructor mainly does in this segment:
  motivation (why the topic matters), definition (introduces what something is), mechanism_explanation (how or \
why something works), derivation_or_proof, procedure_or_algorithm (steps to follow), worked_example (solves a \
specific instance), comparison, application_or_demo, recap (summarises earlier material), discussion (questions, \
opinions, course logistics).
- key_points: 2 to 5 key points. Each is one atomic, self-contained statement of something the segment teaches \
(a fact, claim, step or result), understandable without the transcript, with the IDs of the sentences that state it.
Use only what is said in this segment.""")

TERMS = ("annotate.terms", "2", """Task: list the key terms this segment defines, and the other concepts it relies on.
- key_terms: up to 6 technical terms or named concepts that the instructor defines, explains or introduces in this \
segment: the terms a student would put in a glossary for this subject. For each give the term as it is said (a \
short noun phrase, singular), a one-sentence definition faithful to what the instructor says, and the IDs of the \
sentences where it is defined or explained. Do not list generic words (such as "example", "system", "technology", \
"basic understanding"), course logistics, or names of people, institutions or courses.
- used_concepts: up to 8 other technical concepts of the subject that the segment uses or mentions without \
explaining them (short noun phrases; no generic words, people, institutions or courses).
If the segment defines nothing, return an empty key_terms list.""")

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

EDGES = ("state.edges", "2", """{role}

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
"src label dst", e.g. "is a kind of", "is computed by", "is needed for". Do not repeat the concept names in the label.
evidence: the sentence IDs from the evidence list that support the edge.
At least one end of every edge must be a concept from this lecture. Give at most 20 edges, the most important first. \
Do not invent relations the lecture does not support.""")

# ---------------------------------------------------------------- stage 5
RECALL = ("primer.recall", "1", """{role}

The learner is about to watch lecture {lecture_id}: {title}
It builds on these concepts from earlier lectures:
{items}

Task: for each earlier concept, write
- question: a short recall question that makes the learner retrieve the concept from memory (the question must not \
give the answer away),
- recap: one sentence reminding the learner what the concept is.""")

QUIZ = ("active.quiz", "2", """Task: write a 4-item quiz that checks whether a learner understood this segment. Each item \
tests the key point assigned to it:
{items}

Rules:
- Every item must be answerable from this segment alone. Test understanding, not wording trivia.
- Do not copy the key point. Write multiple-choice stems and yes/no items as questions ending with "?", and do \
not let the correct option repeat the wording of the stem.
- Multiple choice: exactly 4 options and exactly one correct option. Wrong options are plausible misconceptions. \
All options have similar length and style. No "all of the above" or "none of the above". Put the correct option \
first (the order is shuffled later).
- True/false: write a statement whose correct answer is the one given above.
- Yes/no: write a question whose correct answer is the one given above.
- For every option, write a one-sentence explanation of why it is right or wrong.""")

SUMMARY = ("active.summary", "1", """Task: write a recap of this segment for a learner who has just watched it: 2 to 3 sentences, \
plain language, nothing that is not in the segment, and do not start with "In this segment".
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
