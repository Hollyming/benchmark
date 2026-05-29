from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from ultra_long_benchmark.shared.io import load_yaml, write_json, write_text


def build_literature_map(seed_path: Path, output_dir: Path) -> Dict[str, Any]:
    seeds = load_yaml(seed_path) or []
    capabilities: dict[str, list[str]] = {}
    for paper in seeds:
        for cap in paper.get("capabilities", []):
            capabilities.setdefault(cap, []).append(paper["id"])

    taxonomy = [
        {
            "capability": "user_policy_induction",
            "definition": "Infer an implicit user work policy from longitudinal tool-use traces.",
            "stressors": ["implicit approvals", "draft-vs-send boundaries", "sparse policy evidence"],
        },
        {
            "capability": "habit_generalization",
            "definition": "Generalize stable habits across days or weeks without overfitting one-off events.",
            "stressors": ["recurring calendar patterns", "distractor sessions", "negative examples"],
        },
        {
            "capability": "tool_action_alignment",
            "definition": "Choose allowed tool actions and avoid forbidden actions under the user's policy.",
            "stressors": ["send/merge/pay boundaries", "CI or review gates", "authorization gaps"],
        },
        {
            "capability": "privacy_authorization_boundary",
            "definition": "Use private information only in authorized tools or contexts.",
            "stressors": ["private identifiers", "tool-specific permission", "overbroad refusal"],
        },
        {
            "capability": "policy_update_exception_handling",
            "definition": "Distinguish global policy changes, narrow exceptions, stale policies, and one-off counterexamples.",
            "stressors": ["implicit conflicts", "stale premises", "narrow exception scopes", "human-only emergency actions"],
        },
        {
            "capability": "workflow_boundary_respect",
            "definition": "Preserve user-specific gates in ordered workflows, such as review, approval, CI, or secure-channel requirements.",
            "stressors": ["CI-before-merge", "review-before-share", "secure-form-only fields", "multi-tool routines"],
        },
        {
            "capability": "abstention_clarification",
            "definition": "Ask for clarification when longitudinal history does not authorize a high-impact action.",
            "stressors": ["payment", "external send", "private data sharing", "ambiguous delegation"],
        },
    ]
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "papers": seeds,
        "capability_to_papers": capabilities,
        "taxonomy": taxonomy,
    }
    write_json(output_dir / "literature_map.json", result)
    write_text(output_dir / "taxonomy.md", render_taxonomy_markdown(taxonomy, capabilities))
    return result


def render_taxonomy_markdown(taxonomy: List[Dict[str, Any]], capability_to_papers: Dict[str, List[str]]) -> str:
    lines = ["# Benchmark Capability Taxonomy", ""]
    for item in taxonomy:
        lines.append(f"## {item['capability']}")
        lines.append("")
        lines.append(item["definition"])
        lines.append("")
        lines.append("Stressors: " + ", ".join(item["stressors"]) + ".")
        linked = capability_to_papers.get(item["capability"], [])
        if linked:
            lines.append("Seed papers: " + ", ".join(linked) + ".")
        lines.append("")
    return "\n".join(lines)
