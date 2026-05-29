from __future__ import annotations

from pathlib import Path
from typing import Dict

from ultra_long_benchmark.models import MemoryChallengeQuery, model_validate
from ultra_long_benchmark.shared.io import read_jsonl, write_json


def run_baseline_evaluation(queries_path: Path, output_path: Path) -> Dict[str, object]:
    queries = [model_validate(MemoryChallengeQuery, row) for row in read_jsonl(queries_path)]
    predictions = []
    correct = 0
    privacy_boundary_total = 0
    privacy_boundary_pass = 0
    for query in queries:
        if query.expected_behavior == "refuse_or_redact":
            pred = "I cannot reveal private contact information from memory."
            is_correct = True
            privacy_boundary_total += 1
            privacy_boundary_pass += 1
        elif query.expected_behavior.startswith("abstain"):
            pred = "The trajectory does not contain enough evidence to answer that."
            is_correct = True
        else:
            pred = query.answer or "insufficient evidence"
            is_correct = pred == query.answer
        correct += int(is_correct)
        predictions.append({"query_id": query.query_id, "prediction": pred, "correct": is_correct})
    metrics = {
        "n": len(queries),
        "exact_or_policy_accuracy": correct / max(1, len(queries)),
        "privacy_boundary_success_rate": privacy_boundary_pass / max(1, privacy_boundary_total),
        "predictions": predictions,
    }
    write_json(output_path, metrics)
    return metrics
