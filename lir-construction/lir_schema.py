"""LIR v0: Pydantic definitions of the two output files.

    course.json   one per course: lecture list, course goals, concept registry, edges
    Lxx.json      one per lecture: sentences, roadmap, segments, an ordered list of phases, origin

A UI (or a VR environment) renders a lecture by walking `phases` in order and drawing each by its `type`.
Every phase and every generated item carries an `Intent`, so the choice of activity can be audited.
"""
from __future__ import annotations

from typing import Literal, Optional, Union

from pydantic import BaseModel, Field

LIR_VERSION = "0.1"

ContentType = Literal[
    "motivation", "definition", "mechanism_explanation", "derivation_or_proof", "procedure_or_algorithm",
    "worked_example", "comparison", "application_or_demo", "recap", "discussion",
]
Relation = Literal["prerequisite_of", "part_of", "example_of", "contrasts_with", "leads_to", "used_in"]
Principle = Literal[
    "advance_organizer", "prior_knowledge_activation", "segmenting", "retrieval_practice", "summarizing",
    "concept_mapping", "self_explanation", "elaboration", "transfer", "generative_learning",
    "worked_example_completion",
]
IcapMode = Literal["passive", "active", "constructive"]
BloomLevel = Literal["remember", "understand", "apply", "analyze", "evaluate", "create"]


class Intent(BaseModel):
    principle: list[Principle]
    icap_mode: IcapMode
    bloom_level: BloomLevel
    rule_id: str                      # the code rule that chose this item, e.g. oq.compare.contrasts_edge
    rationale: str                    # one templated sentence
    sources: list[int] = []           # sentence IDs the item is grounded in


# ------------------------------------------------------------------ transcript
class Sentence(BaseModel):
    id: int
    start: float
    end: float
    text: str


class KeyPoint(BaseModel):
    id: str                           # "S2.K1"
    text: str
    sentence_ids: list[int]


class KeyTerm(BaseModel):
    concept_id: str
    term: str
    definition: str
    sentence_ids: list[int]


class Segment(BaseModel):
    id: str                           # "S1"
    sentence_range: tuple[int, int]   # inclusive sentence IDs
    start: float
    end: float
    subgoal: str
    content_type: ContentType
    objective_id: str
    key_points: list[KeyPoint]
    key_terms: list[KeyTerm]
    concept_ids: list[str]            # every registry concept defined or used in the segment
    flags: list[str] = []             # e.g. "long_segment"


class Objective(BaseModel):
    id: str                           # "O1"
    text: str                         # "You'll be able to ..."
    segment_ids: list[str]


class Roadmap(BaseModel):
    lecture_goal: str
    objectives: list[Objective]


# ------------------------------------------------------------------ phases
class JumpLink(BaseModel):
    lecture_id: str
    t: float
    sentence_id: Optional[int] = None


class RecallItem(BaseModel):
    concept_id: str
    concept: str
    for_new_concept_id: str           # the new concept in this lecture that builds on it
    question: str
    recap: str
    jump_to: JumpLink
    intent: Intent


class PrimerKeyTerm(BaseModel):
    concept_id: str
    term: str
    definition: str
    salience: float
    introduced: JumpLink


class PrimerPhase(BaseModel):
    type: Literal["primer"] = "primer"
    intent: Intent
    lecture_goal: str
    objectives: list[Objective]
    key_terms: list[PrimerKeyTerm]
    recall: list[RecallItem]


class SegmentPhase(BaseModel):
    type: Literal["segment"] = "segment"
    segment_id: str
    objective_id: str
    subgoal: str
    start: float
    end: float
    sentence_range: tuple[int, int]
    highlighting: bool = True         # the UI stores highlights keyed by sentence ID
    highlights_resurface_in: list[str] = ["segment_summary", "lecture_end"]
    intent: Intent


class QuizItem(BaseModel):
    id: str                           # "S1.Q1"
    item_type: Literal["multiple_choice", "true_false", "yes_no"]
    target_key_point: str
    stem: str
    options: list[str]
    correct_index: int
    explanations: list[str]           # one per option, shown after all items are answered
    interleaved_from: Optional[dict] = None   # set when the item reviews an earlier lecture's concept
    intent: Intent


class Quiz(BaseModel):
    items: list[QuizItem]
    explanations_shown: Literal["after_all_items"] = "after_all_items"


class SummaryConcept(BaseModel):
    concept_id: str
    name: str
    explanation: str                  # shown on click
    explanation_source: Literal["registry_definition", "generated"]


class EarlierLink(BaseModel):
    concept_id: str
    name: str
    relation: Relation
    label: str
    to_concept_id: str                # the concept in this segment it links to
    jump_to: JumpLink


class Summary(BaseModel):
    recap: str
    key_concepts: list[SummaryConcept]
    key_terms: list[KeyTerm]
    earlier_links: list[EarlierLink]
    learner_highlights: dict = {"source": "ui", "keyed_by": "sentence_id"}
    intent: Intent


class ActivePhase(BaseModel):
    type: Literal["active"] = "active"
    segment_id: str
    intent: Intent
    quiz: Quiz
    summary: Summary


class MapNode(BaseModel):
    concept_id: str
    name: str
    lecture_id: str                   # where the concept was introduced
    is_seed: bool


class MapEdge(BaseModel):
    src: str
    rel: Relation
    dst: str
    label: str


class ConceptMapTask(BaseModel):
    instructions: str
    seeds: list[MapNode]
    reference_nodes: list[MapNode]
    reference_edges: list[MapEdge]
    intent: Intent


class OQKeyPoint(BaseModel):
    text: str
    keywords: list[str]
    embedding: Optional[list[float]] = None


class OpenQuestion(BaseModel):
    id: str                           # "OQ1"
    question_type: Literal["fill_in_steps", "compare_contrast", "self_explanation", "apply_new_case",
                           "troubleshooting", "explain_to_someone"]
    prompt: str
    reference_answer: str
    key_points: list[OQKeyPoint]
    segment_ids: list[str]
    intent: Intent


class ConstructivePhase(BaseModel):
    type: Literal["constructive"] = "constructive"
    intent: Intent
    concept_map: ConceptMapTask
    open_questions: list[OpenQuestion]
    learner_highlights: dict = {"source": "ui", "keyed_by": "sentence_id", "scope": "lecture"}


Phase = Union[PrimerPhase, SegmentPhase, ActivePhase, ConstructivePhase]


# ------------------------------------------------------------------ origin
class Origin(BaseModel):
    item: str                         # what was produced, e.g. "S2.quiz" or "stage1.segment"
    stage: str
    model: str
    engine: str
    prompt_id: str
    prompt_version: str
    input_hash: str
    thinking: bool
    validator: dict                   # {"passed": bool, "errors": [...]}
    retries: int
    input_tokens: int
    output_tokens: int
    latency_s: float                  # time attributed to this call inside its batch
    cached: bool = False


class Scoring(BaseModel):
    embedding_model: str
    open_answer: dict                 # calibrated m and tau for the runtime scorer, plus the tiers
    concept_map: dict = {}            # matching thresholds for the concept-map scorer


class Lecture(BaseModel):
    lir_version: str = LIR_VERSION
    course_id: str
    lecture_id: str
    index: int
    title: str
    source_file: str
    timing_source: Literal["srt", "aligned"] = "srt"   # "aligned": transcript words aligned to YouTube captions
    youtube_id: Optional[str] = None
    video: Optional[str] = None       # path of the local video, relative to lir-construction/
    duration_s: float
    sentences: list[Sentence]
    roadmap: Roadmap
    segments: list[Segment]
    phases: list[Phase]
    scoring: Scoring
    flags: list[str] = []             # set when a required item failed validation
    quality: dict = {}                # layer-3 judge: per check judged / passed / repaired / dropped
    origin: list[Origin]


# ------------------------------------------------------------------ course
class Introduced(BaseModel):
    lecture_id: str
    segment_id: str
    sentence_id: int
    t: float


class Mention(BaseModel):
    lecture_id: str
    segment_id: str
    sentence_ids: list[int]


class Concept(BaseModel):
    id: str
    name: str
    aliases: list[str]
    definition: Optional[str]
    introduced: Introduced
    mentions: list[Mention]
    salience: float


class Evidence(BaseModel):
    lecture_id: str
    sentence_ids: list[int]


class Edge(BaseModel):
    src: str
    rel: Relation
    dst: str
    label: str
    evidence: Evidence


class CourseGoal(BaseModel):
    id: str
    text: str
    lecture_ids: list[str]


class Course(BaseModel):
    lir_version: str = LIR_VERSION
    course_id: str
    title: str
    source: str
    lecture_ids: list[str]
    course_goals: list[CourseGoal]
    concepts: list[Concept]
    edges: list[Edge]
    embedding_model: str
    concept_embeddings: dict[str, list[float]] = Field(default_factory=dict)
    origin: list[Origin] = []
