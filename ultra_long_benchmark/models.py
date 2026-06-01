from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Capability(str, Enum):
    USER_POLICY_INDUCTION = "user_policy_induction"
    HABIT_GENERALIZATION = "habit_generalization"
    CONTEXTUAL_POLICY_SELECTION = "contextual_policy_selection"
    TOOL_ACTION_ALIGNMENT = "tool_action_alignment"
    WORKFLOW_BOUNDARY_RESPECT = "workflow_boundary_respect"
    POLICY_UPDATE_EXCEPTION_HANDLING = "policy_update_exception_handling"
    PROACTIVE_ROUTINE_RECOGNITION = "proactive_routine_recognition"
    PRIVACY_AUTHORIZATION_BOUNDARY = "privacy_authorization_boundary"
    HABIT_STORAGE_GATING = "habit_storage_gating"
    ABSTENTION_CLARIFICATION = "abstention_clarification"


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


class ActionBoundary(BaseModel):
    allowed_actions: List[str] = Field(default_factory=list)
    forbidden_actions: List[str] = Field(default_factory=list)
    conditions: List[str] = Field(default_factory=list)
    exceptions: List[str] = Field(default_factory=list)
    requires_approval: List[str] = Field(default_factory=list)
    requires_clarification: List[str] = Field(default_factory=list)
    authorized_tools: List[str] = Field(default_factory=list)
    forbidden_tools: List[str] = Field(default_factory=list)


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
    action_boundary: Optional[ActionBoundary] = None
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


class TraceAction(BaseModel):
    action_id: str
    tool: str
    action: str
    timestamp: Optional[datetime] = None
    args: Dict[str, Any] = Field(default_factory=dict)
    rationale: Optional[str] = None
    requires_approval: bool = False
    approval_obtained: bool = False
    clarification_requested: bool = False


class ActionTrace(BaseModel):
    trace_id: str
    project_id: str
    probe_id: str
    actions: List[TraceAction] = Field(default_factory=list)
    retrieved_memory_ids: List[str] = Field(default_factory=list)
    retrieved_event_ids: List[str] = Field(default_factory=list)
    final_answer: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProjectPrediction(BaseModel):
    prediction_id: str
    project_id: str
    probe_id: str
    prediction: str
    retrieved_memory_ids: List[str] = Field(default_factory=list)
    retrieved_event_ids: List[str] = Field(default_factory=list)
    retrieved_artifact_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AnnotationEvidenceSnippet(BaseModel):
    event_id: str
    source_dataset: str
    event_type: str
    timestamp: datetime
    actor: str
    content: str
    artifact_ids: List[str] = Field(default_factory=list)
    raw_pointer: str = ""
    uri: Optional[str] = None
    content_hashes: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PolicyAnnotationTask(BaseModel):
    annotation_id: str
    candidate_id: str
    repo: str
    candidate_type: str
    policy_candidate: str
    confidence: float
    supporting_evidence: List[AnnotationEvidenceSnippet] = Field(default_factory=list)
    negative_evidence: List[AnnotationEvidenceSnippet] = Field(default_factory=list)
    action_boundary_candidate: ActionBoundary = Field(default_factory=ActionBoundary)
    future_tasks: List[str] = Field(default_factory=list)
    mining_rule: str = ""
    llm_instructions: Dict[str, Any] = Field(default_factory=dict)
    verifier_expectations: Dict[str, Any] = Field(default_factory=dict)
    human_review_checklist: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)


class PolicyAnnotationPack(BaseModel):
    pack_id: str
    source_dataset: str
    input_path: str
    repo_filter: Optional[str] = None
    generated_at: datetime
    tasks: List[PolicyAnnotationTask] = Field(default_factory=list)
    constraints: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)


class PolicyRewriteProposal(BaseModel):
    proposal_id: str
    annotation_id: str
    candidate_id: str
    rewritten_policy: str
    future_probe_query: str
    expected_behavior: Dict[str, Any] = Field(default_factory=dict)
    positive_event_ids: List[str] = Field(default_factory=list)
    negative_event_ids: List[str] = Field(default_factory=list)
    action_boundary: ActionBoundary = Field(default_factory=ActionBoundary)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PolicyRewriteValidationReport(BaseModel):
    proposal_id: str
    annotation_id: str
    candidate_id: str
    passed: bool
    issues: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    checks: Dict[str, bool] = Field(default_factory=dict)


class VerifierReport(BaseModel):
    project_id: str
    generated_at: datetime
    checks: Dict[str, bool] = Field(default_factory=dict)
    counts: Dict[str, int] = Field(default_factory=dict)
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
