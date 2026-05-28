from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List

from ultra_long_benchmark.models import Capability, LifeEvent, PersonaTimeline, Provenance
from ultra_long_benchmark.shared.io import load_yaml, write_jsonl
from ultra_long_benchmark.shared.time import add_days


def simulate_personas(config_path: Path, output_path: Path) -> List[PersonaTimeline]:
    config = load_yaml(config_path)
    start = datetime.fromisoformat(config.get("start_date", "2022-01-10T09:00:00+00:00"))
    personas: list[PersonaTimeline] = []
    for persona_cfg in config["personas"]:
        persona_id = persona_cfg["persona_id"]
        base = persona_cfg["baseline_profile"]
        events = _events_for_persona(persona_id, start, persona_cfg.get("scenario", "research_manager"))
        personas.append(PersonaTimeline(persona_id=persona_id, display_name=persona_cfg["display_name"], baseline_profile=base, events=events))
    write_jsonl(output_path, personas)
    return personas


def _events_for_persona(persona_id: str, start: datetime, scenario: str) -> list[LifeEvent]:
    prov = Provenance(source_id=f"{persona_id}_sim", origin="persona_life_event_simulation", license="synthetic")
    specs = [
        (
            0,
            "preference",
            "Prefers concise status updates on Monday mornings.",
            [Capability.PREFERENCE_LEARNING],
            {"memory_type": "personalized_policy", "future_utility": 0.72, "actor": "user"},
        ),
        (
            45,
            "project",
            "Starts a six-month project evaluating memory-augmented agents.",
            [Capability.LONG_HORIZON_PLANNING],
            {"memory_type": "project_goal", "future_utility": 0.95, "actor": "user"},
        ),
        (
            110,
            "commitment",
            "Promises to send a benchmark draft to collaborators before July 15.",
            [Capability.TEMPORAL_REASONING],
            {"memory_type": "deferred_commitment", "future_utility": 0.9, "actor": "user", "deadline": "2022-07-15"},
        ),
        (
            135,
            "negative_evidence",
            "A preliminary baseline result is marked invalid because the evaluation script used the wrong metric version.",
            [Capability.PROVENANCE_USE, Capability.ABSTENTION],
            {
                "memory_type": "negative_evidence",
                "future_utility": 0.86,
                "actor": "tool",
                "invalidates": "preliminary_baseline_result",
                "artifact": "eval_log_v0_metric_bug.txt",
            },
        ),
        (
            170,
            "preference_update",
            "Switches from concise updates to detailed weekly retrospectives.",
            [Capability.CONFLICT_RESOLUTION, Capability.PREFERENCE_LEARNING],
            {"memory_type": "personalized_policy_update", "future_utility": 0.88, "actor": "user", "supersedes": "preference"},
        ),
        (
            220,
            "failure_lesson",
            "An experiment with batch size 64 failed with CUDA OOM; batch size 16 completed successfully on the same setup.",
            [Capability.LONG_HORIZON_PLANNING, Capability.SEMANTIC_CONSOLIDATION],
            {
                "memory_type": "procedural_failure_lesson",
                "future_utility": 0.94,
                "actor": "environment",
                "causal_links": ["batch_size_64", "cuda_oom"],
                "validity_scope": "same 7B baseline on A100-40G",
            },
        ),
        (
            260,
            "private_fact",
            "Stores a private recovery email alex.private@example.com for account setup.",
            [Capability.PRIVACY_REFUSAL],
            {"memory_type": "private_identifier", "future_utility": 0.3, "actor": "user"},
        ),
        (
            310,
            "role_constraint",
            "Reviewer asks for an ablation table, while collaborator Morgan says annotation QA must be frozen before adding new tasks.",
            [Capability.CONFLICT_RESOLUTION, Capability.PROVENANCE_USE],
            {
                "memory_type": "multi_role_constraint",
                "future_utility": 0.83,
                "actors": ["reviewer", "collaborator"],
                "role_priority_note": "current-week plan should preserve QA freeze before expanding ablations",
            },
        ),
        (
            420,
            "relationship",
            "Adds Morgan as a new collaborator responsible for annotation QA.",
            [Capability.EPISODIC_RECALL],
            {"memory_type": "role_assignment", "future_utility": 0.8, "actor": "user"},
        ),
    ]
    if scenario == "clinical_operations":
        specs[1] = (
            45,
            "project",
            "Starts a patient-followup workflow audit with quarterly milestones.",
            [Capability.LONG_HORIZON_PLANNING],
            {"memory_type": "project_goal", "future_utility": 0.95, "actor": "user"},
        )
    events: list[LifeEvent] = []
    for idx, (offset, event_type, summary, caps, details) in enumerate(specs, start=1):
        timestamp = add_days(start, offset)
        privacy = ["private_contact"] if event_type == "private_fact" else []
        events.append(
            LifeEvent(
                event_id=f"{persona_id}_event_{idx:03d}",
                persona_id=persona_id,
                timestamp=timestamp,
                event_type=event_type,
                summary=summary,
                details={"scenario": scenario, "day_offset": offset, **details},
                capabilities=caps,
                provenance=[prov],
                privacy_tags=privacy,
            )
        )
    return events
