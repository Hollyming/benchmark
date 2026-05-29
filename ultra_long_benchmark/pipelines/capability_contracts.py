from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProbeContract:
    """Structural contract for longitudinal user-policy probes.

    The checks are deliberately conservative. They ensure generated probes test
    policy or habit induction from grounded traces instead of degenerating into
    fact recall or generic tool-task success.
    """

    required_positive_memory_types: set[str] = field(default_factory=set)
    required_any_memory_types: set[str] = field(default_factory=set)
    require_negative_evidence: bool = False
    require_distractor_evidence: bool = False
    require_invalidating_event: bool = False
    require_future_utility: bool = False
    min_supporting_artifact_types: int = 0
    min_supporting_source_datasets: int = 0
    min_positive_memories: int = 1


TASK_CONTRACTS: dict[str, ProbeContract] = {
    "implicit_policy_induction": ProbeContract(
        required_positive_memory_types={"user_policy"},
        require_future_utility=True,
    ),
    "policy_update_and_exception_handling": ProbeContract(
        required_positive_memory_types={"user_policy", "policy_exception"},
        require_future_utility=True,
        min_positive_memories=2,
    ),
    "cross_day_habit_generalization": ProbeContract(
        required_positive_memory_types={"work_habit"},
        require_future_utility=True,
    ),
    "routine_step_ordering": ProbeContract(
        required_positive_memory_types={"workflow_routine"},
        require_future_utility=True,
    ),
    "contextual_workflow_policy_selection": ProbeContract(
        required_positive_memory_types={"contextual_policy"},
        require_future_utility=True,
    ),
    "negative_example_storage_gating": ProbeContract(
        required_positive_memory_types={"negative_policy_example"},
        required_any_memory_types={"negative_policy_example"},
        require_negative_evidence=True,
        require_invalidating_event=True,
    ),
    "tool_action_policy_alignment": ProbeContract(
        min_positive_memories=1,
        require_future_utility=True,
    ),
    "privacy_authorization_boundary": ProbeContract(
        required_positive_memory_types={"authorization_boundary"},
        require_future_utility=True,
    ),
    "authorization_gap_clarification": ProbeContract(
        required_positive_memory_types={"authorization_gap"},
        require_future_utility=True,
    ),
    "artifact_management_habit_transfer": ProbeContract(
        required_positive_memory_types={"work_habit"},
        require_future_utility=True,
    ),
    "cross_tool_boundary_composition": ProbeContract(
        require_negative_evidence=True,
        require_distractor_evidence=True,
        min_supporting_source_datasets=3,
        min_positive_memories=3,
    ),
}
