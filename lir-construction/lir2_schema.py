"""LIR v2.1: the knowledge layer. Pydantic definitions of the output files.

    course.json      lectures, course goals, the concept graph (concepts with aliases, a canonical course-wide
                     definition, facets; links), lecture map, alias index
    Lxx.json         one per lecture: sentences, parts (objective, key points, term occurrences with the lecture's own
                     definition and their concept), objectives, goal
    decisions.jsonl  every decision about content, with its reason and the call that made it
    embeddings.json  concept embeddings ("name: latest definition"), for matching learners' words to concepts
    activities/Lxx.json   the activity layer for one lecture (LectureActivities below)

Every reference is an address (see pipeline2/addr.py). The activity layer is kept apart from the knowledge: a renderer
(web, VR) can follow the default `sequence` or build its own from the same items.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

LIR_VERSION = "2.1"
Relation = Literal["kind_of", "part_of", "depends_on"]


# ------------------------------------------------------------------ lecture
class Sentence(BaseModel):
    id: str                           # "L05/S0412"
    start: float
    end: float
    text: str


class KeyPoint(BaseModel):
    id: str                           # "L05/P03/K2"
    text: str
    sources: list[str]
    concept_ids: list[str] = []       # registry concepts the key point names


class TermOccurrence(BaseModel):
    id: str                           # "L05/P03/T1"
    surface: str                      # as the lecturer says it
    name: str                         # glossary name
    abbreviation: Optional[str] = None
    abbreviation_at: Optional[str] = None   # the sentence where the lecturer uses it
    definition: str                   # this lecture's definition (what the learner sees here; judged)
    sources: list[str]
    concept_id: str
    concept_name: str                 # the concept's canonical name (the registry's)


class Part(BaseModel):
    id: str                           # "L05/P03"
    first: str                        # first sentence
    last: str                         # last sentence
    start: float
    end: float
    objective: str
    objective_id: str
    key_points: list[KeyPoint]
    terms: list[TermOccurrence]


class Objective(BaseModel):
    id: str                           # "L05/O2"
    text: str                         # completes "You'll be able to ..."
    part_ids: list[str]


class Lecture(BaseModel):
    lir_version: str = LIR_VERSION
    course_id: str
    lecture_id: str
    index: int
    title: str
    source_file: str
    timing_source: Literal["srt", "aligned"] = "srt"
    youtube_id: Optional[str] = None
    duration_s: float
    sentences: list[Sentence]
    parts: list[Part]
    objectives: list[Objective]
    lecture_goal: str
    flags: list[str] = []
    origin: list[dict] = []


# ------------------------------------------------------------------ course
class Alias(BaseModel):
    text: str
    kind: Literal["name", "abbreviation"]
    said_at: str                      # a sentence where the lecturer uses it


class Facet(BaseModel):
    id: str                           # "C0014@L05/P03"
    part: str
    only_mentioned: bool
    says: Optional[str] = None        # what the part teaches about the concept
    sentences: list[str] = []         # the sentences that teach it
    named_in: list[str] = []          # the sentences that name the concept


class Concept(BaseModel):
    id: str
    name: str
    aliases: list[Alias]
    introduced: str                   # sentence address
    introduced_part: str
    terms: list[str]                  # term occurrences
    definition: str                   # canonical, course-wide (the registry's, from all its term definitions)
    reason: str                       # why its terms are one concept
    sources: list[str]                # the sentences its term definitions rest on
    facets: list[Facet]


class Edge(BaseModel):
    id: str
    src: str
    rel: Relation                     # "src rel dst": kind_of, part_of, depends_on (src needs dst)
    dst: str
    label: str                        # link phrase for concept maps: "src label dst"
    evidence: list[str]
    lecture_id: str                   # where the evidence is
    flags: list[str] = []             # "forward": src introduced before the concept it depends on; "two_way": the
                                      # same kind_of / part_of both ways; "flipped": the judge reversed it


class LectureLink(BaseModel):
    src: str
    dst: str
    weight: int
    concepts: list[str]               # concepts introduced in src that dst builds on


class CourseGoal(BaseModel):
    id: str
    text: str
    lecture_ids: list[str]


class LectureRef(BaseModel):
    id: str
    index: int
    title: str
    duration_s: float
    youtube_id: Optional[str] = None


class Course(BaseModel):
    lir_version: str = LIR_VERSION
    course_id: str
    title: str
    source: str
    lectures: list[LectureRef]
    course_goals: list[CourseGoal]
    concepts: list[Concept]
    edges: list[Edge]
    lecture_map: list[LectureLink]
    alias_index: dict[str, list[str]]  # lower-case name or alias -> concept IDs
    embedding_model: str
    origin: list[dict] = []


# ------------------------------------------------------------------ activities
class RecallItem(BaseModel):
    id: str                           # "L05/R1"
    concept_ids: list[str]
    question: str
    answer: str
    sources: list[str]                # what the answer rests on (earlier lectures)
    jump_to: str                      # where the concept was introduced


class QuizItem(BaseModel):
    id: str                           # "L05/P03/Q1"
    type: Literal["multiple_choice", "true_false", "yes_no"]
    key_point: Optional[str] = None   # None for an item on an earlier concept
    concept_ids: list[str]
    stem: str
    options: list[str]
    correct_index: int
    explanations: list[str]           # one per option
    sources: list[str]


class Recap(BaseModel):
    text: str
    sources: list[str]
    source: Literal["generated", "key_points"]


class ReviewItem(BaseModel):
    id: str                           # "L05/P03/V1"
    key_point: str
    concept_ids: list[str]
    question: str
    answer: str
    sources: list[str]


class SpacedItem(BaseModel):
    concept_id: str                   # an earlier concept this part teaches about, due for review
    from_lecture: str
    item: QuizItem                    # a copy of the earlier quiz item, so a renderer needs only this file
    default: bool                     # in the default schedule (the first 2); the rest are alternatives
    last_tested: str                  # lecture where the concept was last tested
    gap: int                          # lectures it had to wait (doubles after each test when due)
    reason: str


class PartActivities(BaseModel):
    part_id: str
    quiz: list[QuizItem]
    spaced_review: list[SpacedItem]   # shown after the part's quiz
    recap: Optional[Recap] = None
    review: list[ReviewItem]


class MapNode(BaseModel):
    concept_id: str
    name: str
    introduced_in: str
    seed: bool


class MapEdge(BaseModel):
    edge_id: str
    src: str
    rel: Relation
    dst: str
    label: str


class ConceptMap(BaseModel):
    instructions: str
    nodes: list[MapNode]
    edges: list[MapEdge]


class OQKeyPoint(BaseModel):
    text: str
    keywords: list[str]
    sources: list[str]
    embedding: Optional[list[float]] = None


class OpenQuestion(BaseModel):
    id: str                           # "L05/OQ1"
    type: Literal["explain_mechanism", "compare_contrast", "apply_new_case", "fill_in_steps", "troubleshooting",
                  "explain_to_someone"]
    prompt: str
    reference_answer: str
    key_points: list[OQKeyPoint]
    part_ids: list[str]
    concept_ids: list[str]


class Step(BaseModel):
    type: Literal["recall", "watch", "quiz", "summary", "concept_map", "open_questions"]
    part_id: Optional[str] = None


class LectureActivities(BaseModel):
    lir_version: str = LIR_VERSION
    course_id: str
    lecture_id: str
    sequence: list[Step]              # the default order; renderers may build their own
    recall: list[RecallItem]
    parts: list[PartActivities]
    concept_map: ConceptMap
    open_questions: list[OpenQuestion]
    scoring: dict                     # open-answer scorer settings (m, tau, tiers) and concept-map matching
