"""v2.1 prompts. One unit per prompt (a part, a window, a registry group, a lecture). Each prompt has an ID and a
version, recorded in origin and in the decision log.

Prompts that read one stretch of transcript put that stretch first (the "excerpt block") and the task last, so the
calls on the same part (annotate, judge, facets, activities) share a prompt start and the server reuses its cache.
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

# ---------------------------------------------------------------- 2 objective and key points (one call per part)
ANNOTATE = ("part.annotate", "1", """Task: describe what this part teaches.
- objective: what a learner achieves by watching this part: what they will be able to do afterwards, as one phrase \
that starts with a verb, for example "Explain why ...", "Derive ..." or "Compare ...". Specific to this part, at most \
20 words, using only what is said in this part.
- key_points: 2 to 5 key points. Each is one atomic, self-contained statement of something the part teaches (a fact, \
claim, step or result), understandable without the transcript, with the numbers of the sentences that state it. For \
each, about: "subject" if it is about the subject matter itself, or "course" if it is about the course, the lecture \
or its organisation (what the course covers, its goals, structure, schedule, assignments or the instructor's plans). \
Write subject key points as facts of the subject ("Optical flow is ..."), not as reports of the lecture ("The \
lecture explains that ...").""")

# ---------------------------------------------------------------- 3 key terms (one call per window)
TERMS = ("terms.window", "1", """Task: build the glossary entries for this excerpt.
First find every term the lecturer explains here: a term is explained when the lecturer says what it is, how it \
works, what it consists of, or what kinds of it exist; a term that is only named or used does not count. Named \
systems, devices, products, methods and people count when the lecturer explains what or who they are.
Then, for each term found:
- term: the term as the lecturer says it;
- sentence_ids: the numbers of the sentences that explain it;
- reason: one sentence on whether it belongs in the glossary of key terms of the course "{course}";
- keep: true only if all three hold: (1) it names a concept of the subject, or a specific system, device, product, \
method or person the subject studies; not a generic word (such as "system", "approach", "example"), not a phrase \
that describes the lecture or a story told in it, not course logistics; (2) the lecturer explains it in the cited \
sentences; (3) a student of this course should still know it after the lecture;
- name: its glossary name: a noun phrase in the singular, in the lecturer's words; if the term is an adjective or a \
fragment (for example "non-immersive"), name the thing it describes ("non-immersive VR system"); no abbreviation in \
the name;
- abbreviation: the abbreviation the lecturer uses for it in this excerpt, exactly as written in the transcript, or \
"" if none; never make one up;
- abbreviation_sentence: the number of a sentence in which the lecturer uses that abbreviation, or -1;
- definition: if keep is true, one or two sentences that start with the term, say what kind of thing it is and what \
sets it apart from related ideas, in clear words of your own, based only on what the lecturer says in this excerpt, \
so that a student who never heard the term understands it from the definition alone (do not copy the spoken \
sentences); "" if keep is false.
List each term once. If the excerpt explains no term, return an empty list.""")

# ---------------------------------------------------------------- 4 registry (one call per group of similar terms)
REGISTRY = ("registry.group", "1", """{role}

Course: {course}
Key terms from the lectures of this course that may name the same concept. Each entry is one term name, with the \
definitions written for it in the lectures that explain it and what the lecturer said there:

{entries}

Task: group the entries into concepts. Entries name the same concept when a learner should treat them as one idea \
with one definition: different wording, spelling, singular and plural, or an abbreviation of the same thing. They \
are different concepts if one is a kind, a part, an example or a property of the other, or if they are related but \
different ideas. Every entry belongs to exactly one concept. For each concept give:
- entries: the numbers of its entries;
- reason: one sentence on why these entries are one concept (or why this entry stands alone);
- name: the canonical glossary name: a noun phrase in the singular, as the lecturer says it, without an abbreviation;
- definition: one to three sentences that start with the name, say what kind of thing it is and what sets it apart, \
keep every important point of the entries' definitions, and say nothing the lecturer does not say.""")

# ---------------------------------------------------------------- 7 goals
GOALS = ("goals.lecture", "1", """{role}

Lecture: {title}
The lecture's parts, in playback order, each with what a learner achieves in it:
{parts}

Task:
- objectives: group the parts into {lo} to {hi} learning objectives. Each objective covers a contiguous run of parts \
(no gaps, no reordering), and every part belongs to exactly one objective. Write each as what the learner will be \
able to do, starting with a verb in lower case, for example "explain how ..." or "compute ...": it is shown after the \
words "You'll be able to".
- goal: the overall goal of the lecture, as one sentence that starts with a verb.""")

COURSE_GOALS = ("goals.course", "2", """{role}

Course: {course}
Its lectures, each with its overall goal and its learning objectives:
{lectures}

Task: write {lo} to {hi} course-level goals that summarise what a learner gains from these lectures, bottom-up from \
the lecture goals and objectives. Each goal starts with a verb and lists the IDs of the lectures that serve it. Every \
lecture must serve at least one goal.""")

# ---------------------------------------------------------------- 5 facets (one call per part, in course order)
FACETS = ("facets.part", "2", """Concepts named in this part, each with its definition, the sentences of this part \
that name it, and what earlier lectures taught about it:

{concepts}

Task: for each concept, say what this part teaches about it.
- concept: its label (C1, C2, ...);
- only_mentioned: true if the part only names or uses the concept without teaching anything about it;
- says: if only_mentioned is false, one statement (at most 30 words) of what the learner learns about the concept \
in this part, written as a fact of the subject; say what is new compared with the earlier lectures, without \
repeating them; otherwise "";
- sentence_ids: the numbers of the sentences of this part that teach it (empty if only mentioned).
Give exactly one entry per concept.""")

# ---------------------------------------------------------------- 6 links (one call per lecture)
# follows the concept block of pipeline2/s6_edges.py block(): each concept with its definition, what this lecture and
# earlier lectures teach about it, and the lecture's sentences that name it
LINKS = ("links.lecture", "1", """Task: list every relation between two of these concepts that this lecture states or clearly implies. Relations, \
read as "a relation b":
- kind_of: a is a specific kind of the more general b
- part_of: a is a component or part of b
- depends_on: to understand a, a learner must first understand b
For each relation give:
- a, relation, b: the concept labels and the relation;
- label: a phrase of 2 to 6 words that sits between the two names, so that "<name of a> <label> <name of b>" reads \
as one true, natural sentence a student would understand, for example "provides the display for" or "is a type \
of"; specific to what the lecture says; without the concept names;
- evidence: the numbers of the sentences above that show the relation.
Leave out relations the sentences do not support. List each pair of concepts at most once.""")

# ---------------------------------------------------------------- judge (one call per unit), rewrite (failed items)
JUDGE = ("judge.items", "1", """You are now a strict reviewer of learning material that was generated automatically \
from this lecture. An item passes only if the material above supports it.

{items}

Task: check every item. {criteria}
Give one verdict per item: item (its number), reason (one sentence), ok.""")

JUDGE_LINKS_EXTRA = """ If the relation holds, but the other way round ("b relation a"), set reversed to true \
(and ok to false); otherwise reversed is false."""

REWRITE = ("judge.rewrite", "1", """A reviewer rejected these items:

{items}

Task: rewrite each rejected item so that it passes the review, keeping what was right about it. {rules}
Give one rewritten item per number (item: its number).""")

# ---------------------------------------------------------------- activities
QUIZ_RULES = """Each quiz item tests understanding of the subject (what something is, how or why it works, how ideas \
relate, when to use it), is answerable from this part alone, never asks what the lecture, the course or the \
instructor says, never asks what an abbreviation stands for, and does not copy the key point."""

ACTIVITIES = ("act.part", "1", """Key points of this part, by ID:
{points}

Task: write the learning activities for this part, for a learner who has just watched it.
1. quiz: 0 to {hi} items on the key points worth testing: ideas a learner should understand, not trivia; never two \
items on the same idea; none if nothing is worth testing. For each item:
   - key_point: the ID of the key point it tests; type; reason: one sentence on why this point and this type;
   - type multiple_choice, when there are plausible wrong answers: stem is a question ending with "?"; correct is \
the one correct option; wrong are exactly 3 plausible misconceptions, each of similar length and style to the \
correct option; no "all of the above" or "none of the above";
   - type true_false, for a clear claim a learner might get backwards: stem is a statement (not a question) that \
this part makes clearly true or clearly false; correct is "True" or "False"; wrong is the other one;
   - type yes_no, for a clear yes-or-no question: stem ends with "?"; correct is "Yes" or "No"; wrong is the other;
   - explanation_correct: one sentence on why the correct answer is right; explanations_wrong: one sentence for each \
wrong answer, in order, on why it is wrong.
   {rules}
2. recap: 2 to 3 sentences in plain language that tie the key points together; nothing that is not in this part; do \
not start with "In this part".
3. review: one check-yourself question for each key point that the quiz does not test: key_point, question (about \
the subject, not about the lecture; does not give the answer away; ends with "?"), answer (one or two sentences).""")

OQ_TYPES = {
    "explain_mechanism": "explain why or how something works",
    "compare_contrast": "how two ideas are alike and different, and when each applies",
    "apply_new_case": "use an idea or method on a new situation, different from the lecture's examples",
    "fill_in_steps": "complete the missing steps of a procedure or derivation and say why each is needed",
    "troubleshooting": "diagnose and fix a case that goes wrong in a way the lecture warns about",
    "explain_to_someone": "explain the main idea to a classmate who missed the lecture",
}

OQ = ("act.oq", "2", """Task: write {lo} to {hi} open-ended questions that make the learner think about this lecture \
and put it in their own words. Prefer different types and different parts. For each question:
- type: the kind of thinking it asks for, one the content supports (compare only what the lecture compares, fill in \
steps only where it works through steps, troubleshoot only where it discusses how things go wrong):
{types}
- parts: the IDs of the one to three parts it draws on;
- question: addressed to the learner (for example "Explain ..." or "Your friend asks ..."), answerable from what the \
lecture teaches; the learner never sees part numbers, so name the topic itself;
- reference_answer: 3 to 6 sentences, based only on the material above;
- key_points: 3 to 5 points a good answer must contain. For each: text (one short statement); keywords (2 to 6 words \
or short phrases of at most 3 words that appear word for word in your reference answer and that a learner covering \
the point would likely use); sentence_ids (the numbers of the sentences above that support it).""")

RECALL = ("act.recall", "2", """{role}

The learner is about to watch lecture {lid}: "{title}". It builds on these concepts from earlier lectures, each with \
what the learner learned about it before this lecture:

{concepts}

Task: for each concept, write one recall question that makes the learner retrieve what they learned about it, in the \
subject's own terms: it must not give the answer away and must not just ask what an abbreviation stands for. Then \
its answer in one or two sentences, based only on what they learned before this lecture. Give concept (its label), \
question, answer.""")

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

REL_TEXT = {"kind_of": "is a kind of", "part_of": "is part of", "depends_on": "builds on"}
