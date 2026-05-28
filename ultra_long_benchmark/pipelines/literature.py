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
            "capability": "episodic_recall",
            "definition": "Recover specific past interactions with temporal and contextual anchors.",
            "stressors": ["many distractor sessions", "similar repeated events", "delayed query"],
        },
        {
            "capability": "temporal_reasoning",
            "definition": "Order memories, resolve recency, and reason over changing states.",
            "stressors": ["preference drift", "deadline changes", "conflicting versions"],
        },
        {
            "capability": "privacy_refusal",
            "definition": "Refuse or redact sensitive memory use when policy requires it.",
            "stressors": ["private identifiers", "secret-like strings", "benign adjacent facts"],
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

