"""v2 prompts. One task per prompt. Each has an ID and a version, recorded in origin and in the decision log.

Prompts that read one stretch of transcript put that stretch first (the "excerpt block") and the task last, so all
calls on the same stretch share a prompt start and the server reuses its cache.
"""
ROLE = "You are helping turn a recorded university lecture into a guided, interactive learning experience for students."


def excerpt_block(course: str, title: str, numbered_text: str, what: str = "one part of the lecture") -> str:
    return (f"{ROLE}\n\nCourse: {course}\nLecture: {title}\n\n"
            f"Transcript of {what}, one sentence per line with its sentence number in brackets:\n"
            f"{numbered_text}\n\n")


def objective_line(objective: str) -> str:
    return f"The part of the lecture this excerpt belongs to has this goal for the learner: {objective}\n\n"


# ---------------------------------------------------------------- 1 parts
# the standalone-segments prompt of v1 (pipeline/prompts.py SEGMENT, WD 0.09), unchanged

# ---------------------------------------------------------------- 2 per part
OBJECTIVE = ("part.objective", "1", """Task: state what a learner achieves by watching this part: what they will be \
able to do afterwards, as one phrase that starts with a verb, for example "Explain why ...", "Derive ..." or \
"Compare ...". Be specific to this part, in at most 20 words, using only what is said in this part.""")

KEY_POINTS = ("part.key_points", "1", """Task: list the key points this part teaches about the subject.
A key point is one atomic, self-contained statement of a fact, claim, step or result of the subject, understandable \
without the transcript. Write it as a fact of the subject ("Optical flow is ..."), not as a report of the lecture \
("The lecturer explains ..."). Cover everything the part teaches about the subject, one point per idea, without \
repeating yourself. Leave out course logistics: what the course or lecture will cover, its schedule, assignments or \
the instructor's plans.
For each key point give the numbers of the sentences that state it.
If the part teaches nothing about the subject, return an empty list.""")

# ---------------------------------------------------------------- 3 key terms
CANDIDATES = ("terms.candidates", "1", """Task: list every term that the lecturer explains in this excerpt.
A term is explained when the lecturer says what it is, how it works, what it consists of, or what kinds of it exist. \
A term that is only named or used, without being explained, does not count. Named systems, devices, products, \
methods and people count when the lecturer explains what or who they are.
For each term give:
- term: the term as the lecturer says it,
- sentence_ids: the numbers of the sentences that explain it.
List each term once. If the excerpt explains no term, return an empty list.""")

KEEP = ("terms.keep", "1", """Candidate key term: "{term}", explained in sentences {ids}.
Task: decide whether this term belongs in the glossary of key terms of the course "{course}".
keep is true only if all three hold:
1. It names a concept of the subject, or a specific system, device, product, method or person that the subject \
studies. It is not a generic word (such as "system", "approach", "example" or "categories"), not a phrase that \
describes the lecture or a story told in it, and not course logistics.
2. The lecturer explains it in the cited sentences: says what it is, how it works, what it consists of or what kinds \
of it exist, not just names or uses it.
3. A student of this course should still know it after the lecture.
Give the reason first, in one or two sentences, then keep.""")

NAME = ("terms.name", "1", """Key term: "{term}", explained in sentences {ids}.
Task: give the term's glossary name and, if the lecturer uses one, its abbreviation.
- name: the name of the concept as a glossary would list it: a noun phrase in the singular, in the lecturer's words. \
If the term is an adjective or a fragment (for example "non-immersive"), name the thing it describes \
("non-immersive VR system"). Do not put an abbreviation in the name.
- abbreviation: the abbreviation the lecturer uses for this term in this excerpt, exactly as it is written in the \
transcript, or "" if the lecturer uses none. Never make one up.
- abbreviation_sentence: the number of a sentence in which the lecturer uses that abbreviation, or -1 if there is \
none.""")

DEFINE = ("terms.define", "1", """Key term: "{name}", explained in sentences {ids}.
Task: write its glossary definition: one or two sentences that start with the term, say what kind of thing it is \
and what sets it apart from related ideas, in clear words of your own, based only on what the lecturer says in this \
excerpt. A student who has never heard the term must understand what it is from the definition alone. Do not copy \
the lecturer's spoken sentences.""")

REWRITE = """

A reviewer rejected your previous answer:
"{previous}"
Reason: {reason}
Write a corrected answer."""

GROUND_TASK = """Task: check this definition against what the lecturer says{where}. supported is true only if every \
claim in the definition is stated or clearly implied by the lecturer; clear rewording is fine, but anything the \
lecturer does not say is not. Give the reason first, then supported."""

GROUND = ("terms.grounded", "1", """Definition of the key term "{name}":
"{definition}"
""" + GROUND_TASK)

# ---------------------------------------------------------------- 4 registry
SAME = ("registry.same", "1", """{role}

Two key terms from the course "{course}".

A: "{a_name}"{a_alias}
Definition: {a_def}
What the lecturer said ({a_where}):
{a_sents}

B: "{b_name}"{b_alias}
Definition: {b_def}
What the lecturer said ({b_where}):
{b_sents}

Task: decide whether A and B name the same concept, so that a learner should treat them as one idea with one \
definition. Different wording, spelling, singular and plural, or an abbreviation of the same thing count as the same. \
They are not the same if one is a kind, a part, an example or a property of the other, or if they are related but \
different ideas. Give the reason first, then same.""")

REFINE = ("registry.refine", "1", """{role}

Concept: "{name}", from the course "{course}".
Definitions written for it so far, each from the lecture where it was explained:
{defs}

What the lecturer said, by sentence:
{sents}

Task: write one definition of the concept that combines these: one to three sentences that start with the \
concept's name, say what kind of thing it is and what sets it apart, and keep every important point of the \
definitions above. Say nothing the lecturer does not say.""")

GROUND_ALL = ("registry.grounded", "1", """{role}

What the lecturer said about "{name}", by sentence:
{sents}

Definition of "{name}":
"{definition}"
""" + GROUND_TASK)

# ---------------------------------------------------------------- 5 facets
FACET = ("facets.part", "1", """Concept: "{name}"{aliases}. {definition}
It is named in sentences {ids} of this part.
Task: say what this part teaches about this concept.
- only_mentioned: true if the part only names or uses the concept without teaching anything about it.
- says: if only_mentioned is false, one short statement (at most 25 words) of what the learner learns about the \
concept in this part, written as a fact of the subject; otherwise "".
- sentence_ids: the numbers of the sentences that teach it (empty if only_mentioned is true).""")

# ---------------------------------------------------------------- 6 edges
RELATION = ("edges.relation", "1", """{role}

Two concepts from the course "{course}":
A: "{a}": {a_def}
B: "{b}": {b_def}

What the lecturer said, by sentence:
{sents}

Task: decide which one of these statements the lecturer states or clearly implies in these sentences:
- a_kind_of_b: A is a specific kind of the more general B
- b_kind_of_a: B is a specific kind of the more general A
- a_part_of_b: A is a component or part of B
- b_part_of_a: B is a component or part of A
- a_depends_on_b: to understand A as it is explained here, a learner must first understand B
- b_depends_on_a: to understand B as it is explained here, a learner must first understand A
- none: none of these holds, or the sentences do not support it
Give the reason first, then relation, then evidence: the labels of the sentences that support it (such as \
"{example}"); empty for none.""")

REL_TEXT = {"kind_of": "is a kind of", "part_of": "is part of", "depends_on": "builds on"}

LABEL = ("edges.label", "1", """{role}

What the lecturer said, by sentence:
{sents}

A concept-map link goes from "{src}" to "{dst}": "{src}" {rel_text} "{dst}".
Task: write the label of this link: a short phrase of 2 to 6 words that sits between the two concept names, so that \
"{src} <label> {dst}" reads as one true, natural sentence a student would understand, for example "provides the \
display for" or "is a type of". Use what the lecturer says to make it specific. Do not repeat the concept names in \
the label.""")

LABEL_CHECK = ("edges.label_check", "1", """{role}

What the lecturer said, by sentence:
{sents}

A concept-map link reads: "{src} {label} {dst}".
Task: check the link. ok is true only if the sentence is true according to what the lecturer says, it expresses \
that "{src}" {rel_text} "{dst}", and it reads as a natural, complete sentence. Give the reason first, then ok.""")

# ---------------------------------------------------------------- 7 goals
OBJECTIVES = ("goals.objectives", "1", """{role}

Lecture: {title}
The lecture's parts, in playback order, each with what a learner achieves in it:
{parts}

Task: group the parts into {lo} to {hi} learning objectives. Each objective covers a contiguous run of parts (no \
gaps, no reordering), and every part belongs to exactly one objective. Write each objective as what the learner will \
be able to do, starting with a verb in lower case, for example "explain how ..." or "compute ...": it is shown after \
the words "You'll be able to".""")

LECTURE_GOAL = ("goals.lecture", "1", """{role}

Lecture: {title}
Its learning objectives, in order (each completes "You'll be able to ..."):
{objectives}

Task: write the overall goal of the lecture as one sentence that starts with a verb.""")

COURSE_GOALS = ("goals.course", "1", """{role}

Course: {course}
Its lectures, each with its overall goal:
{lectures}

Task: write {lo} to {hi} course-level goals that summarise what a learner gains from these lectures, bottom-up from \
the lecture goals. Each goal starts with a verb and lists the IDs of the lectures that serve it. Every lecture must \
serve at least one goal.""")


# ---------------------------------------------------------------- judge (verifier), knowledge and activities
JUDGE = ("judge.item", "1", """You are now a strict reviewer of learning material that was generated automatically \
from this lecture. An item passes only if the material above supports it.

{item}

Task: {criteria} Give the reason first, in one or two sentences, then ok.""")

KP_REWRITE = ("judge.key_point_rewrite", "1", """Key point: "{text}", citing sentences {ids}.
Task: rewrite this key point as one atomic, self-contained statement of a fact, claim, step or result of the subject, \
supported by the sentences it cites, understandable without the transcript, and written as a fact of the subject \
(not a report of the lecture). Give the text and the numbers of the sentences that state it.""")

OBJ_REWRITE = ("judge.objective_rewrite", "1", """Learning objective for parts {pids}: "{text}".
Task: rewrite this objective as what the learner will be able to do after these parts, starting with a verb in lower \
case (it is shown after the words "You'll be able to"), covering their main content and claiming nothing they do not \
teach.""")

COURSE_GOAL_REWRITE = ("judge.course_goal_rewrite", "1", """Course goal for lectures {lids}: "{text}".
Task: rewrite this goal as one sentence that starts with a verb and sums up what a learner gains from these \
lectures.""")

# ---------------------------------------------------------------- activities (generator writes, verifier judges)
RECALL = ("act.recall", "1", """{role}

The learner is about to watch lecture {lid}: "{title}". It builds on "{name}"{aliases}, which they met in earlier \
lectures.
What they learned about it before this lecture:
{material}

Task: write one recall question that makes the learner retrieve what they learned about this concept, in the \
subject's own terms: it must not give the answer away and must not just ask what an abbreviation stands for. Then \
write its answer in one or two sentences, based only on what they learned before this lecture.""")

QUIZ_PLAN = ("act.quiz_plan", "1", """Task: plan a short quiz that checks whether a learner understood this part. Its \
key points, by ID:
{points}
Choose the key points worth testing, at most {hi}: ideas a learner should understand, not trivia, and never two \
questions on the same idea. Choose none if nothing is worth testing. For each, choose the item type that suits it:
- multiple_choice: when there are plausible wrong answers (misconceptions) to choose from,
- true_false: when the point is a clear claim that a learner might get backwards,
- yes_no: when the point answers a clear yes-or-no question.
Give the reason for each choice.""")

QUIZ_RULES = """The question tests understanding of the subject (what something is, how or why it works, how ideas \
relate, when to use it), is answerable from this part alone, never asks what the lecture, the course or the \
instructor says, never asks what an abbreviation stands for, and does not copy the point."""

QUIZ_MC = ("act.quiz_mc", "1", """Task: write one multiple-choice question that tests this point: {point}
{rules}
- question: ends with "?".
- correct: the one correct option.
- wrong: exactly 3 wrong options: plausible misconceptions, each of similar length and style to the correct option; \
no "all of the above" or "none of the above".
- explanation_correct: one sentence on why the correct option is right.
- explanations_wrong: one sentence for each wrong option, in order, on why it is wrong.""")

QUIZ_TF = ("act.quiz_tf", "1", """Task: write one true/false statement that tests this point: {point}
{rules}
- statement: a statement (not a question) that this part makes clearly true or clearly false.
- answer: "True" or "False".
- explanation_true: one sentence on why "True" is right or wrong.
- explanation_false: one sentence on why "False" is right or wrong.""")

QUIZ_YN = ("act.quiz_yn", "1", """Task: write one yes/no question that tests this point: {point}
{rules}
- question: ends with "?" and has a clear yes or no answer.
- answer: "Yes" or "No".
- explanation_yes: one sentence on why "Yes" is right or wrong.
- explanation_no: one sentence on why "No" is right or wrong.""")

RECAP = ("act.recap", "1", """Task: write a recap of this part for a learner who has just watched it: 2 to 3 sentences \
in plain language that tie its key points together. Say nothing that is not in this part, and do not start with \
"In this part". Key points:
{points}""")

REVIEW = ("act.review", "1", """Task: write one check-yourself question on this point, with a short answer the learner \
can reveal after thinking: {point}
- question: about the subject (not about the lecture), does not give the answer away, ends with "?".
- answer: one or two sentences.""")

OQ_TYPES = {
    "explain_mechanism": "explain why or how something works",
    "compare_contrast": "how two ideas are alike and different, and when each applies",
    "apply_new_case": "use an idea or method on a new situation, different from the lecture's examples",
    "fill_in_steps": "complete the missing steps of a procedure or derivation and say why each is needed",
    "troubleshooting": "diagnose and fix a case that goes wrong in a way the lecture warns about",
    "explain_to_someone": "explain the main idea to a classmate who missed the lecture",
}

OQ_PLAN = ("act.oq_plan", "1", """{role}

Lecture: {title}
Its parts, each with its goal and key points:
{parts}

Task: plan {lo} to {hi} open-ended questions that make the learner think about this lecture and put it in their own \
words. For each choose:
- type, the kind of thinking it asks for:
{types}
  Choose a type the content supports: compare only what the lecture compares, fill in steps only where it works \
through steps, troubleshoot only where it discusses how things go wrong.
- parts: the IDs of the one to three parts it draws on,
- focus: one sentence on what the question is about.
Prefer different types and different parts. Give the reason for each choice.""")

OQ_WRITE = ("act.oq_write", "1", """Task: write one open-ended question that asks the learner to {type_text}.
It is about: {focus}
- question: addressed to the learner (for example "Explain ..." or "Your friend asks ..."), answerable from the \
sentences above. The learner never sees part numbers, so name the topic itself.
- reference_answer: 3 to 6 sentences, based only on the sentences above.
- key_points: 3 to 5 points a good answer must contain. For each: text (one short statement); keywords (2 to 6 \
words or short phrases of at most 3 words that appear word for word in your reference answer and that a learner \
covering the point would likely use); sentence_ids (the numbers of the sentences above that support it).""")

CALIBRATE = ("act.calibrate", "1", """Task: write three answers to this open-ended question, as three different \
students would, in their own words (do not copy the reference answer):
Question: {q}
Reference answer: {ref}
Key points a good answer covers:
{kps}

- good: a correct answer that covers every key point.
- partial: a correct but incomplete answer that covers about half of the key points.
- wrong: a plausible-sounding answer that misses or misunderstands the key points.
Each answer is 2 to 5 sentences.""")
