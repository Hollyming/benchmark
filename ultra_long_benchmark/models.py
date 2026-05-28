from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Capability(str, Enum):
    EPISODIC_RECALL = "episodic_recall"
    SEMANTIC_CONSOLIDATION = "semantic_consolidation"
    PREFERENCE_LEARNING = "preference_learning"
    TEMPORAL_REASONING = "temporal_reasoning"
    PROVENANCE_USE = "provenance_use"
    CONFLICT_RESOLUTION = "conflict_resolution"
    PRIVACY_REFUSAL = "privacy_refusal"
    LONG_HORIZON_PLANNING = "long_horizon_planning"
    ABSTENTION = "abstention"


class Provenance(BaseModel):
    source_id: str
    origin: str
    uri: Optional[str] = None
    license: Optional[str] = None
    content_hash: Optional[str] = None


class SourceDocument(BaseModel):
    doc_id: str
    title: str
    text: str
    created_at: date
    provenance: Provenance
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Validity(BaseModel):
    scope: str
    start: Optional[str] = None
    end: Optional[str] = None
    status: str = "active"


class SourceArtifact(BaseModel):
    artifact_id: str
    source_dataset: str
    artifact_type: str
    uri: Optional[str] = None
    license: Optional[str] = None
    content_hash: Optional[str] = None
    raw_pointer: str
    content: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CanonicalEvent(BaseModel):
    event_id: str
    project_id: str
    timestamp: datetime
    source_dataset: str
    actor: str
    event_type: str
    content: str
    artifacts: List[str] = Field(default_factory=list)
    raw_pointer: str = ""
    project_tags: List[str] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)
    claims: List[str] = Field(default_factory=list)
    causal_links: List[str] = Field(default_factory=list)
    supersedes: List[str] = Field(default_factory=list)
    invalidates: List[str] = Field(default_factory=list)
    validity: Optional[Validity] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProjectProfile(BaseModel):
    project_id: str
    title: str
    project_goal: str
    user_profile: Dict[str, Any] = Field(default_factory=dict)
    roles: Dict[str, str] = Field(default_factory=dict)
    phases: List[str] = Field(default_factory=list)
    source_streams: List[str] = Field(default_factory=list)
    synthetic_context: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MemoryRelation(BaseModel):
    type: str
    target: str


class FutureUtility(BaseModel):
    score: float
    expected_tasks: List[str] = Field(default_factory=list)


class MemoryNode(BaseModel):
    memory_id: str
    project_id: str
    memory_type: str
    content: str
    source_events: List[str] = Field(default_factory=list)
    status: str = "active"
    validity: Optional[Dict[str, Any]] = None
    relations: List[MemoryRelation] = Field(default_factory=list)
    negative_evidence: List[str] = Field(default_factory=list)
    distractors: List[str] = Field(default_factory=list)
    future_utility: Optional[FutureUtility] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MemoryGraph(BaseModel):
    project_id: str
    memories: List[MemoryNode] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProbeEvidence(BaseModel):
    positive: List[str] = Field(default_factory=list)
    negative: List[str] = Field(default_factory=list)
    obsolete: List[str] = Field(default_factory=list)
    distractor: List[str] = Field(default_factory=list)


class ProbeEvaluation(BaseModel):
    answer_type: str = "free_text"
    metrics: List[str] = Field(default_factory=list)


class Probe(BaseModel):
    probe_id: str
    project_id: str
    trajectory_id: str
    task_type: str
    query: str
    expected_behavior: Dict[str, Any] = Field(default_factory=dict)
    evidence: ProbeEvidence = Field(default_factory=ProbeEvidence)
    capabilities: List[str] = Field(default_factory=list)
    evaluation: ProbeEvaluation = Field(default_factory=ProbeEvaluation)
    difficulty: str = "medium"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VerifierReport(BaseModel):
    project_id: str
    generated_at: datetime
    checks: Dict[str, bool] = Field(default_factory=dict)
    counts: Dict[str, int] = Field(default_factory=dict)
    issues: List[str] = Field(default_factory=list)
    passed: bool


class LifeEvent(BaseModel):
    event_id: str
    persona_id: str
    timestamp: datetime
    event_type: str
    summary: str
    details: Dict[str, Any] = Field(default_factory=dict)
    capabilities: List[Capability] = Field(default_factory=list)
    provenance: List[Provenance] = Field(default_factory=list)
    privacy_tags: List[str] = Field(default_factory=list)


class PersonaTimeline(BaseModel):
    persona_id: str
    display_name: str
    baseline_profile: Dict[str, Any]
    events: List[LifeEvent]


class Message(BaseModel):
    message_id: str
    role: str
    timestamp: datetime
    content: str
    provenance: List[Provenance] = Field(default_factory=list)
    privacy_tags: List[str] = Field(default_factory=list)


class Session(BaseModel):
    session_id: str
    persona_id: str
    start_time: datetime
    messages: List[Message]
    linked_event_ids: List[str] = Field(default_factory=list)


class Trajectory(BaseModel):
    trajectory_id: str
    persona_id: str
    sessions: List[Session]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MemoryChallengeQuery(BaseModel):
    query_id: str
    trajectory_id: str
    persona_id: str
    capability: Capability
    prompt: str
    answer: Optional[str] = None
    evidence_event_ids: List[str] = Field(default_factory=list)
    negative_evidence_event_ids: List[str] = Field(default_factory=list)
    obsolete_evidence_event_ids: List[str] = Field(default_factory=list)
    distractor_event_ids: List[str] = Field(default_factory=list)
    memory_task: str = "generic_memory_use"
    expected_behavior: str = "answer"
    privacy_sensitive: bool = False
    rubric: Dict[str, Any] = Field(default_factory=dict)


class QCReport(BaseModel):
    task: str
    generated_at: datetime
    counts: Dict[str, int]
    issues: List[str] = Field(default_factory=list)
    passed: bool


def model_to_dict(model: BaseModel) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")  # type: ignore[attr-defined]
    return model.dict()


def model_validate(cls: type[BaseModel], data: Dict[str, Any]) -> BaseModel:
    if hasattr(cls, "model_validate"):
        return cls.model_validate(data)  # type: ignore[attr-defined]
    return cls.parse_obj(data)

