from __future__ import annotations

import hashlib
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from ultra_long_benchmark.models import Probe, ProjectPrediction, ProjectProfile, model_to_dict, model_validate
from ultra_long_benchmark.pipelines.verifier import run_project_verifier
from ultra_long_benchmark.shared.io import read_json, read_jsonl, write_json, write_jsonl


PROJECT_RELEASE_SPLITS = ("train", "dev", "test")
PROJECT_RELEASE_FILES = (
    "project_profile.json",
    "source_manifest.json",
    "artifacts.jsonl",
    "events.jsonl",
    "memory_graph.json",
    "probes.jsonl",
    "verifier_report.json",
)
SUBMISSION_INPUT_FILES = (
    "submission_manifest.json",
    "projects.jsonl",
    "artifacts.jsonl",
    "events.jsonl",
    "probes.jsonl",
    "prediction_template.jsonl",
)


def export_project_benchmark_release(
    project_dirs: Iterable[Path],
    output_dir: Path,
    *,
    dataset_name: str = "longuserpolicy_project_benchmark",
    version: str = "0.1.0",
    copy_projects: bool = False,
    require_verifier_passed: bool = True,
    llm_generation_performed: bool = False,
    construction: str = "deterministic_or_human_verified",
) -> dict[str, Any]:
    """Export verifier-checked projects into a project-level benchmark release."""

    output_dir = Path(output_dir)
    project_paths = [Path(path) for path in project_dirs]
    if not project_paths:
        raise ValueError("at least one project directory is required")

    projects = []
    probes_by_split: dict[str, list[dict[str, Any]]] = {split: [] for split in PROJECT_RELEASE_SPLITS}
    project_ids: set[str] = set()
    for project_dir in project_paths:
        record = _project_record(project_dir, output_dir=output_dir, copy_project=copy_projects)
        if record["project_id"] in project_ids:
            raise ValueError(f"duplicate project_id in release input: {record['project_id']}")
        project_ids.add(record["project_id"])
        if require_verifier_passed and record["verifier_passed"] is not True:
            raise ValueError(f"project verifier did not pass for {record['project_id']}: {record['verifier_issues']}")
        projects.append(record)
        for probe in _release_probe_rows(project_dir, record):
            probes_by_split[record["split"]].append(probe)

    all_probes = [probe for split in PROJECT_RELEASE_SPLITS for probe in probes_by_split[split]]
    split_counts = {split: len(probes_by_split[split]) for split in PROJECT_RELEASE_SPLITS}
    manifest = {
        "dataset_name": dataset_name,
        "version": version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "release_type": "project_benchmark_release",
        "projects": projects,
        "counts": {
            "projects": len(projects),
            "probes": len(all_probes),
            "events": sum(int(project["counts"].get("events", 0)) for project in projects),
            "artifacts": sum(int(project["counts"].get("artifacts", 0)) for project in projects),
            "memories": sum(int(project["counts"].get("memories", 0)) for project in projects),
        },
        "splits": split_counts,
        "split_policy": "project_id_sha256_modulo",
        "constraints": {
            "requires_project_verifier_passed": require_verifier_passed,
            "llm_generation_performed": bool(llm_generation_performed),
            "llm_generation_validated": bool(llm_generation_performed),
            "construction": construction,
            "raw_data_copied": bool(copy_projects),
            "release_contains_project_references": True,
        },
    }

    write_json(output_dir / "project_release_manifest.json", manifest)
    write_json(output_dir / "splits.json", {split: [project["project_id"] for project in projects if project["split"] == split] for split in PROJECT_RELEASE_SPLITS})
    for split, rows in probes_by_split.items():
        write_jsonl(output_dir / "probes" / f"{split}.jsonl", rows)
    write_jsonl(output_dir / "probes" / "all.jsonl", all_probes)
    return manifest


def verify_project_benchmark_release(release_dir: Path, output_path: Path | None = None) -> dict[str, Any]:
    """Verify a project benchmark release manifest, splits, probes, and hashes."""

    release_dir = Path(release_dir)
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    checks: dict[str, Any] = {}
    manifest_path = release_dir / "project_release_manifest.json"
    splits_path = release_dir / "splits.json"
    manifest = _read_required_json(manifest_path, "project_release_manifest_missing", issues)
    splits = _read_required_json(splits_path, "project_release_splits_missing", issues)
    if manifest is None:
        report = _project_release_report(release_dir, issues, warnings, checks)
        if output_path is not None:
            write_json(output_path, report)
        return report

    projects = list(manifest.get("projects", []))
    project_by_id = {str(project.get("project_id")): project for project in projects if project.get("project_id")}
    _check_duplicate_ids("duplicate_release_project_id", [str(project.get("project_id", "")) for project in projects], issues)
    _check_project_manifest_counts(manifest, projects, issues)
    _check_project_release_constraints(manifest.get("constraints", {}), issues)
    project_split_members = _check_project_splits(splits or {}, project_by_id, issues)
    project_probe_counts = _check_release_project_records(projects, release_dir, issues)
    split_rows, all_rows = _check_project_probe_files(release_dir / "probes", manifest.get("splits", {}), manifest.get("counts", {}), project_by_id, issues, warnings)
    _check_project_probe_consistency(split_rows, all_rows, project_by_id, project_split_members, project_probe_counts, issues)
    checks["manifest"] = {
        "projects": len(projects),
        "declared_projects": manifest.get("counts", {}).get("projects"),
        "declared_probes": manifest.get("counts", {}).get("probes"),
        "constraints": manifest.get("constraints", {}),
    }
    checks["splits"] = {
        "projects_by_split": {split: len(project_split_members.get(split, [])) for split in PROJECT_RELEASE_SPLITS},
        "project_disjoint": not any(issue["code"] == "project_in_multiple_splits" for issue in issues),
    }
    checks["probes"] = {
        "split_counts": {split: len(split_rows.get(split, [])) for split in PROJECT_RELEASE_SPLITS},
        "all_probes": len(all_rows),
        "declared_splits": manifest.get("splits", {}),
    }
    report = _project_release_report(release_dir, issues, warnings, checks)
    if output_path is not None:
        write_json(output_path, report)
    return report


def export_project_submission_inputs(
    release_dir: Path,
    output_dir: Path,
    *,
    include_splits: list[str] | None = None,
    include_artifacts: bool = True,
    include_events: bool = True,
    harden_probe_queries: bool = False,
) -> dict[str, Any]:
    """Export no-gold input files for external memory-agent submissions.

    The resulting pack intentionally excludes `memory_graph.json`, probe gold
    evidence, and `expected_behavior`. External methods can consume raw
    longitudinal artifacts/events plus future probe queries, then submit a
    `ProjectPrediction` JSONL to `score-project-release-predictions`.
    """

    release_dir = Path(release_dir)
    output_dir = Path(output_dir)
    manifest = read_json(release_dir / "project_release_manifest.json")
    split_filter = set(include_splits or PROJECT_RELEASE_SPLITS)
    unknown_splits = sorted(split_filter - set(PROJECT_RELEASE_SPLITS))
    if unknown_splits:
        raise ValueError(f"unknown project release splits: {unknown_splits}")

    project_rows = []
    artifact_rows = []
    event_rows = []
    probe_rows = []
    template_rows = []
    for project in manifest.get("projects", []):
        split = str(project.get("split"))
        if split not in split_filter:
            continue
        project_id = str(project.get("project_id"))
        project_dir = _resolve_reference_path(project.get("project_dir"), release_dir)
        profile = read_json(project_dir / "project_profile.json")
        project_rows.append(
            {
                "project_id": project_id,
                "split": split,
                "title": profile.get("title"),
                "description": profile.get("description"),
                "source_streams": profile.get("source_streams", []),
                "synthetic_context": profile.get("synthetic_context"),
                "counts": {
                    "artifacts": len(read_jsonl(project_dir / "artifacts.jsonl")) if include_artifacts else 0,
                    "events": len(read_jsonl(project_dir / "events.jsonl")) if include_events else 0,
                    "probes": len(read_jsonl(project_dir / "probes.jsonl")),
                },
            }
        )
        if include_artifacts:
            for artifact in read_jsonl(project_dir / "artifacts.jsonl"):
                artifact_rows.append(_submission_artifact_row(project_id, split, artifact))
        if include_events:
            for event in read_jsonl(project_dir / "events.jsonl"):
                event_rows.append(_submission_event_row(project_id, split, event))
        for probe in read_jsonl(project_dir / "probes.jsonl"):
            probe_rows.append(_submission_probe_row(project_id, split, probe, harden_query=harden_probe_queries))
            template_rows.append(
                {
                    "prediction_id": f"pred_{project_id}_{probe['probe_id']}",
                    "project_id": project_id,
                    "probe_id": probe["probe_id"],
                    "prediction": "",
                    "retrieved_memory_ids": [],
                    "retrieved_event_ids": [],
                    "retrieved_artifact_ids": [],
                    "metadata": {"split": split},
                }
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "projects.jsonl", project_rows)
    write_jsonl(output_dir / "artifacts.jsonl", artifact_rows)
    write_jsonl(output_dir / "events.jsonl", event_rows)
    write_jsonl(output_dir / "probes.jsonl", probe_rows)
    write_jsonl(output_dir / "prediction_template.jsonl", template_rows)
    submission_manifest = {
        "release_dir": str(release_dir),
        "dataset_name": manifest.get("dataset_name"),
        "version": manifest.get("version"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "splits": sorted(split_filter),
        "counts": {
            "projects": len(project_rows),
            "artifacts": len(artifact_rows),
            "events": len(event_rows),
            "probes": len(probe_rows),
            "prediction_template_rows": len(template_rows),
        },
        "files": {filename: filename for filename in SUBMISSION_INPUT_FILES},
        "prediction_schema": {
            "required": ["prediction_id", "project_id", "probe_id", "prediction"],
            "optional": ["retrieved_memory_ids", "retrieved_event_ids", "retrieved_artifact_ids", "metadata"],
            "scoring_command": "python -m ultra_long_benchmark.cli score-project-release-predictions <release_dir> <predictions.jsonl>",
        },
        "constraints": {
            "contains_gold_memory_graph": False,
            "contains_probe_expected_behavior": False,
            "contains_gold_evidence_ids": False,
            "contains_verifier_report": False,
            "llm_generation_performed": False,
            "probe_queries_hardened": bool(harden_probe_queries),
        },
        "query_hardening": {
            "enabled": bool(harden_probe_queries),
            "strategy": "task_type_template_without_gold_action_terms" if harden_probe_queries else "original_probe_query",
            "gold_release_unchanged": True,
        },
    }
    write_json(output_dir / "submission_manifest.json", submission_manifest)
    return submission_manifest


def verify_project_submission_inputs(input_dir: Path, output_path: Path | None = None) -> dict[str, Any]:
    """Verify an external-submission input pack has no obvious gold leakage."""

    input_dir = Path(input_dir)
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    checks: dict[str, Any] = {}
    manifest_path = input_dir / "submission_manifest.json"
    manifest = _read_required_json(manifest_path, "submission_manifest_missing", issues)
    if manifest is None:
        report = _submission_input_report(input_dir, issues, warnings, checks)
        if output_path is not None:
            write_json(output_path, report)
        return report

    constraints = manifest.get("constraints", {})
    for key in ("contains_gold_memory_graph", "contains_probe_expected_behavior", "contains_gold_evidence_ids", "contains_verifier_report", "llm_generation_performed"):
        if constraints.get(key) is not False:
            _issue(issues, "submission_input_constraint_violation", f"submission input constraint {key} must be false")
    rows_by_file = {}
    for filename in ("projects.jsonl", "artifacts.jsonl", "events.jsonl", "probes.jsonl", "prediction_template.jsonl"):
        path = input_dir / filename
        if not path.exists():
            _issue(issues, "submission_input_file_missing", f"submission input file missing: {filename}", path=path)
            rows_by_file[filename] = []
            continue
        rows = read_jsonl(path)
        rows_by_file[filename] = rows
        _check_no_forbidden_keys(filename, rows, issues)
    _check_submission_manifest_counts(manifest, rows_by_file, issues)
    _check_submission_prediction_template(rows_by_file.get("prediction_template.jsonl", []), rows_by_file.get("probes.jsonl", []), issues)
    checks["manifest"] = {
        "counts": manifest.get("counts", {}),
        "constraints": constraints,
    }
    checks["files"] = {filename: len(rows) for filename, rows in rows_by_file.items()}
    report = _submission_input_report(input_dir, issues, warnings, checks)
    if output_path is not None:
        write_json(output_path, report)
    return report


def validate_project_prediction_submission(
    release_dir: Path,
    predictions_path: Path,
    output_path: Path | None = None,
    *,
    require_complete: bool = True,
) -> dict[str, Any]:
    """Validate an external ProjectPrediction JSONL before scoring."""

    release_dir = Path(release_dir)
    predictions_path = Path(predictions_path)
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    checks: dict[str, Any] = {}
    manifest = _read_required_json(release_dir / "project_release_manifest.json", "project_release_manifest_missing", issues)
    if manifest is None:
        report = _prediction_submission_report(release_dir, predictions_path, issues, warnings, checks)
        if output_path is not None:
            write_json(output_path, report)
        return report

    expected_keys = _release_probe_keys(release_dir, manifest, issues)
    expected_project_ids = {project_id for project_id, _ in expected_keys}
    rows = read_jsonl(predictions_path)
    predictions: list[ProjectPrediction] = []
    seen_keys: set[tuple[str, str]] = set()
    seen_prediction_ids: set[str] = set()

    if not predictions_path.exists():
        _issue(issues, "prediction_submission_file_missing", f"prediction submission file is missing: {predictions_path}", path=predictions_path)

    for index, row in enumerate(rows, start=1):
        try:
            prediction = model_validate(ProjectPrediction, row)
        except Exception as exc:
            _issue(issues, "prediction_submission_schema_invalid", f"row {index} does not match ProjectPrediction schema: {exc}", path=predictions_path)
            continue
        predictions.append(prediction)
        key = (prediction.project_id, prediction.probe_id)
        if prediction.prediction_id in seen_prediction_ids:
            _issue(issues, "prediction_submission_duplicate_prediction_id", f"duplicate prediction_id {prediction.prediction_id}", path=predictions_path)
        seen_prediction_ids.add(prediction.prediction_id)
        if key in seen_keys:
            _issue(issues, "prediction_submission_duplicate_probe", f"duplicate prediction for project/probe {key}", path=predictions_path)
        seen_keys.add(key)
        if key not in expected_keys:
            code = "prediction_submission_unknown_project" if prediction.project_id not in expected_project_ids else "prediction_submission_unknown_probe"
            _issue(issues, code, f"prediction references project/probe not present in release: {key}", path=predictions_path)
        if not prediction.prediction.strip():
            _issue(issues, "prediction_submission_empty_prediction", f"empty prediction for project/probe {key}", path=predictions_path)

    missing_keys = sorted(expected_keys - seen_keys)
    extra_keys = sorted(seen_keys - expected_keys)
    if require_complete and missing_keys:
        _issue(issues, "prediction_submission_missing_probes", f"missing predictions for {len(missing_keys)} release probes; first={missing_keys[:10]}", path=predictions_path)
    elif missing_keys:
        _warn(warnings, "prediction_submission_partial_coverage", f"partial submission is missing {len(missing_keys)} release probes", path=predictions_path)

    checks["coverage"] = {
        "release_probes": len(expected_keys),
        "prediction_rows": len(rows),
        "valid_prediction_rows": len(predictions),
        "covered_probes": len(expected_keys & seen_keys),
        "missing_probes": len(missing_keys),
        "extra_predictions": len(extra_keys),
        "probe_coverage": round(len(expected_keys & seen_keys) / max(1, len(expected_keys)), 4),
        "require_complete": require_complete,
    }
    checks["projects"] = {
        "release_projects": len(expected_project_ids),
        "submitted_projects": len({prediction.project_id for prediction in predictions}),
    }
    report = _prediction_submission_report(release_dir, predictions_path, issues, warnings, checks)
    if output_path is not None:
        write_json(output_path, report)
    return report


def _project_record(project_dir: Path, *, output_dir: Path, copy_project: bool) -> dict[str, Any]:
    project_dir = Path(project_dir)
    profile = model_validate(ProjectProfile, read_json(project_dir / "project_profile.json"))
    verifier = run_project_verifier(project_dir)
    probes = [model_validate(Probe, row) for row in read_jsonl(project_dir / "probes.jsonl")]
    file_hashes = _project_file_hashes(project_dir)
    release_project_path = str(project_dir)
    if copy_project:
        target = output_dir / "projects" / profile.project_id
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(project_dir, target)
        release_project_path = str(target)
    task_types: dict[str, int] = {}
    capabilities: dict[str, int] = {}
    for probe in probes:
        task_types[probe.task_type] = task_types.get(probe.task_type, 0) + 1
        for capability in probe.capabilities:
            capabilities[str(capability)] = capabilities.get(str(capability), 0) + 1
    source_manifest_path = project_dir / "source_manifest.json"
    source_manifest = read_json(source_manifest_path) if source_manifest_path.exists() else {}
    rewrite_manifest_path = project_dir / "rewrite_project_manifest.json"
    split_key = _project_split_key(profile, source_manifest)
    return {
        "project_id": profile.project_id,
        "title": profile.title,
        "split": _project_split(split_key),
        "split_key": split_key,
        "project_dir": release_project_path,
        "source_streams": list(profile.source_streams),
        "synthetic_context": profile.synthetic_context,
        "construction": source_manifest.get("construction"),
        "llm_role": source_manifest.get("llm_role"),
        "rewrite_project_manifest": str(rewrite_manifest_path) if rewrite_manifest_path.exists() else None,
        "verifier_passed": verifier.passed,
        "verifier_issues": list(verifier.issues),
        "counts": dict(verifier.counts),
        "probe_task_types": dict(sorted(task_types.items())),
        "capabilities": dict(sorted(capabilities.items())),
        "file_hashes": file_hashes,
    }


def _release_probe_rows(project_dir: Path, project_record: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in read_jsonl(project_dir / "probes.jsonl"):
        rows.append(
            row
            | {
                "split": project_record["split"],
                "source_project_id": project_record["project_id"],
                "source_project_dir": project_record["project_dir"],
            }
        )
    return rows


def _submission_artifact_row(project_id: str, split: str, artifact: dict[str, Any]) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "split": split,
        "artifact_id": artifact.get("artifact_id"),
        "artifact_type": artifact.get("artifact_type"),
        "title": artifact.get("title"),
        "content": artifact.get("content"),
        "uri": artifact.get("uri"),
        "created_at": artifact.get("created_at"),
        "metadata": artifact.get("metadata", {}),
    }


def _submission_event_row(project_id: str, split: str, event: dict[str, Any]) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "split": split,
        "event_id": event.get("event_id"),
        "timestamp": event.get("timestamp"),
        "source_dataset": event.get("source_dataset"),
        "actor": event.get("actor"),
        "event_type": event.get("event_type"),
        "content": event.get("content"),
        "artifacts": event.get("artifacts", []),
        "entities": event.get("entities", []),
        "claims": event.get("claims", []),
        "supersedes": event.get("supersedes", []),
        "invalidates": event.get("invalidates", []),
        "validity": event.get("validity"),
        "metadata": event.get("metadata", {}),
    }


def _submission_probe_row(project_id: str, split: str, probe: dict[str, Any], *, harden_query: bool = False) -> dict[str, Any]:
    original_query = str(probe.get("query") or "")
    query = _harden_probe_query(project_id, probe) if harden_query else original_query
    metadata = _public_probe_metadata(probe.get("metadata", {}))
    if harden_query:
        metadata = metadata | {"query_hardened": True, "original_query_hidden": True}
    return {
        "project_id": project_id,
        "split": split,
        "probe_id": probe.get("probe_id"),
        "trajectory_id": probe.get("trajectory_id"),
        "task_type": probe.get("task_type"),
        "query": query,
        "capabilities": probe.get("capabilities", []),
        "evaluation": probe.get("evaluation", {}),
        "difficulty": probe.get("difficulty"),
        "metadata": metadata,
    }


def _harden_probe_query(project_id: str, probe: dict[str, Any]) -> str:
    repo = _repo_from_project_id(project_id)
    task_type = str(probe.get("task_type") or "")
    base = f"In a future {repo} workflow, infer the user's policy from the provided longitudinal events and decide the compliant tool behavior."
    if task_type == "privacy_authorization_boundary":
        return (
            base
            + " The requested operation is externally visible or irreversible, and the current visible state may be missing a required workflow precondition. "
            "State whether to proceed, wait, or ask for clarification, and name the relevant boundary without copying a remembered action phrase."
        )
    if task_type == "negative_example_storage_gating":
        return (
            base
            + " A recent event is a negative, blocked, failed, or exceptional workflow signal. "
            "Decide whether it should become a durable habit for the agent or remain a scoped boundary/exception."
        )
    if task_type == "contextual_workflow_policy_selection":
        label_hint = _coarse_label_hint(str(probe.get("query") or ""))
        actor_hint = _coarse_actor_hint(str(probe.get("query") or ""))
        hint = " ".join(fragment for fragment in [label_hint, actor_hint] if fragment)
        return (
            base
            + (" " + hint if hint else "")
            + " Select the appropriate routing, labeling, ownership, and follow-up behavior for the current issue or pull request from the event history."
        )
    if task_type == "tool_action_policy_alignment":
        return (
            base
            + " The current task is low risk but still requires choosing only the tool actions supported by the user's prior workflow. "
            "Decide the allowed next steps and any actions that should be avoided."
        )
    return base + " Provide the policy-grounded decision and any action boundary that should constrain the tool plan."


def _repo_from_project_id(project_id: str) -> str:
    prefix = "project_gharchive_real_llm_paper_"
    if project_id.startswith(prefix):
        return project_id.removeprefix(prefix).replace("_", "/")
    generic_prefix = "project_gharchive_"
    if project_id.startswith(generic_prefix):
        return project_id.removeprefix(generic_prefix).replace("_", "/")
    return project_id


def _coarse_label_hint(query: str) -> str:
    normalized = query.replace("_", " ").replace("-", " ")
    match = re.search(r"(?:label|issue label)\s+([a-z0-9 ]+)", normalized, flags=re.IGNORECASE)
    if not match:
        match = re.search(r"under the ([a-z0-9 ]+?) (?:label|condition|workflow)", normalized, flags=re.IGNORECASE)
    if not match:
        return ""
    label = " ".join(match.group(1).split()[:5])
    return f"The visible work item includes a coarse label/context hint: {label}."


def _coarse_actor_hint(query: str) -> str:
    handles = re.findall(r"(?:assign|request(?: a)? review from|request)\s+([A-Za-z0-9_.\-\[\]/]+)", query)
    cleaned = [handle.strip(" .,:;()") for handle in handles if handle.strip(" .,:;()")]
    if not cleaned:
        return ""
    return f"The future task names candidate human/bot participants; verify their role from history before acting."


def _public_probe_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    forbidden = {"expected_behavior", "evidence", "gold", "answer", "must_include", "must_not_include"}
    return {key: value for key, value in metadata.items() if key not in forbidden}


def _check_no_forbidden_keys(filename: str, rows: list[dict[str, Any]], issues: list[dict[str, Any]]) -> None:
    forbidden_keys = {"expected_behavior", "evidence", "memory_graph", "memories", "verifier_report", "gold", "answer"}
    for index, row in enumerate(rows):
        present = sorted(forbidden_keys & set(row))
        if present:
            _issue(issues, "submission_input_gold_key_present", f"{filename} row {index} contains forbidden gold keys: {present}")
        metadata = row.get("metadata")
        if isinstance(metadata, dict):
            nested = sorted(forbidden_keys & set(metadata))
            if nested:
                _issue(issues, "submission_input_gold_metadata_present", f"{filename} row {index} metadata contains forbidden gold keys: {nested}")


def _check_submission_manifest_counts(manifest: dict[str, Any], rows_by_file: dict[str, list[dict[str, Any]]], issues: list[dict[str, Any]]) -> None:
    expected = manifest.get("counts", {})
    actual = {
        "projects": len(rows_by_file.get("projects.jsonl", [])),
        "artifacts": len(rows_by_file.get("artifacts.jsonl", [])),
        "events": len(rows_by_file.get("events.jsonl", [])),
        "probes": len(rows_by_file.get("probes.jsonl", [])),
        "prediction_template_rows": len(rows_by_file.get("prediction_template.jsonl", [])),
    }
    for key, value in actual.items():
        if _as_int(expected.get(key)) != value:
            _issue(issues, "submission_input_count_mismatch", f"counts.{key}={expected.get(key)} but {value} rows were found")


def _check_submission_prediction_template(template_rows: list[dict[str, Any]], probe_rows: list[dict[str, Any]], issues: list[dict[str, Any]]) -> None:
    template_keys = {(row.get("project_id"), row.get("probe_id")) for row in template_rows}
    probe_keys = {(row.get("project_id"), row.get("probe_id")) for row in probe_rows}
    missing = sorted(probe_keys - template_keys)
    extra = sorted(template_keys - probe_keys)
    if missing:
        _issue(issues, "submission_template_missing_probe", f"prediction template missing probes: {missing[:10]}")
    if extra:
        _issue(issues, "submission_template_extra_probe", f"prediction template has extra probes: {extra[:10]}")
    for index, row in enumerate(template_rows):
        if row.get("prediction", "") != "":
            _issue(issues, "submission_template_prediction_not_empty", f"prediction template row {index} must leave prediction empty")


def _release_probe_keys(release_dir: Path, manifest: dict[str, Any], issues: list[dict[str, Any]]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    all_probes_path = release_dir / "probes" / "all.jsonl"
    if all_probes_path.exists():
        for row in read_jsonl(all_probes_path):
            project_id = str(row.get("source_project_id") or row.get("project_id") or "")
            probe_id = str(row.get("probe_id") or "")
            if project_id and probe_id:
                keys.add((project_id, probe_id))
        return keys

    _issue(issues, "project_release_all_probes_missing", f"release probe file is missing: {all_probes_path}", path=all_probes_path)
    for project in manifest.get("projects", []):
        project_id = str(project.get("project_id", ""))
        project_dir = _resolve_reference_path(project.get("project_dir"), release_dir)
        for row in read_jsonl(project_dir / "probes.jsonl"):
            probe_id = str(row.get("probe_id") or "")
            if project_id and probe_id:
                keys.add((project_id, probe_id))
    return keys


def _submission_input_report(input_dir: Path, issues: list[dict[str, Any]], warnings: list[dict[str, Any]], checks: dict[str, Any]) -> dict[str, Any]:
    return {
        "input_dir": str(input_dir),
        "passed": not issues,
        "summary": {
            "issues": len(issues),
            "warnings": len(warnings),
            "issue_codes": sorted({issue["code"] for issue in issues}),
            "warning_codes": sorted({warning["code"] for warning in warnings}),
        },
        "checks": checks,
        "issues": issues,
        "warnings": warnings,
    }


def _prediction_submission_report(
    release_dir: Path,
    predictions_path: Path,
    issues: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    checks: dict[str, Any],
) -> dict[str, Any]:
    return {
        "release_dir": str(release_dir),
        "predictions_path": str(predictions_path),
        "passed": not issues,
        "summary": {
            "issues": len(issues),
            "warnings": len(warnings),
            "issue_codes": sorted({issue["code"] for issue in issues}),
            "warning_codes": sorted({warning["code"] for warning in warnings}),
        },
        "checks": checks,
        "issues": issues,
        "warnings": warnings,
        "constraints": {
            "scoring_not_performed": True,
            "requires_score_project_release_predictions": True,
        },
    }


def _project_file_hashes(project_dir: Path) -> dict[str, str]:
    hashes = {}
    for filename in PROJECT_RELEASE_FILES:
        path = project_dir / filename
        if path.exists():
            hashes[filename] = _file_sha256(path)
    return dict(sorted(hashes.items()))


def _check_project_manifest_counts(manifest: dict[str, Any], projects: list[dict[str, Any]], issues: list[dict[str, Any]]) -> None:
    counts = manifest.get("counts", {})
    declared_projects = _as_int(counts.get("projects"))
    declared_probes = _as_int(counts.get("probes"))
    if declared_projects <= 0:
        _issue(issues, "project_release_has_no_projects", "project release manifest declares no projects")
    if declared_probes <= 0:
        _issue(issues, "project_release_has_no_probes", "project release manifest declares no probes")
    if declared_projects != len(projects):
        _issue(issues, "project_count_mismatch", f"counts.projects={declared_projects} but projects list has {len(projects)} records")
    project_probe_total = sum(_as_int(project.get("counts", {}).get("probes")) for project in projects)
    if declared_probes != project_probe_total:
        _issue(issues, "project_probe_total_mismatch", f"counts.probes={declared_probes} but project probe counts sum to {project_probe_total}")
    split_total = sum(_as_int(manifest.get("splits", {}).get(split)) for split in PROJECT_RELEASE_SPLITS)
    if declared_probes != split_total:
        _issue(issues, "project_split_probe_total_mismatch", f"counts.probes={declared_probes} but manifest split probes sum to {split_total}")


def _check_project_release_constraints(constraints: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    if constraints.get("requires_project_verifier_passed") is not True:
        _issue(issues, "project_release_verifier_not_required", "project release must require project verifier pass")
    if constraints.get("llm_generation_performed") is True and constraints.get("llm_generation_validated") is not True:
        _issue(issues, "project_release_unvalidated_llm_generation", "LLM-assisted project release must set llm_generation_validated=true")


def _check_project_splits(
    splits: dict[str, Any],
    project_by_id: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
) -> dict[str, list[str]]:
    split_members = {split: [str(project_id) for project_id in splits.get(split, [])] for split in PROJECT_RELEASE_SPLITS}
    all_members = [project_id for members in split_members.values() for project_id in members]
    _check_duplicate_ids("duplicate_split_project_id", all_members, issues)
    unknown = sorted(set(all_members) - set(project_by_id))
    missing = sorted(set(project_by_id) - set(all_members))
    if unknown:
        _issue(issues, "split_references_unknown_project", f"splits.json references unknown projects: {unknown}")
    if missing:
        _issue(issues, "split_missing_manifest_project", f"splits.json omits manifest projects: {missing}")
    seen: dict[str, str] = {}
    for split, members in split_members.items():
        for project_id in members:
            previous = seen.get(project_id)
            if previous is not None and previous != split:
                _issue(issues, "project_in_multiple_splits", f"project {project_id} appears in both {previous} and {split}")
            seen[project_id] = split
            manifest_split = project_by_id.get(project_id, {}).get("split")
            if manifest_split is not None and manifest_split != split:
                _issue(issues, "split_project_assignment_mismatch", f"project {project_id} is in splits.{split} but manifest split is {manifest_split}")
    return split_members


def _check_release_project_records(projects: list[dict[str, Any]], release_dir: Path, issues: list[dict[str, Any]]) -> dict[str, int]:
    probe_counts: dict[str, int] = {}
    for project in projects:
        project_id = str(project.get("project_id", ""))
        if not project_id:
            _issue(issues, "project_id_missing", "project release record is missing project_id")
            continue
        if project.get("split") not in PROJECT_RELEASE_SPLITS:
            _issue(issues, "invalid_project_split", f"project {project_id} has invalid split {project.get('split')!r}")
        if project.get("verifier_passed") is not True:
            _issue(issues, "project_verifier_not_passed", f"project {project_id} verifier did not pass")
        project_dir = _resolve_reference_path(project.get("project_dir"), release_dir)
        if not project_dir.exists():
            _issue(issues, "project_dir_missing", f"project directory missing for {project_id}", path=project_dir)
            continue
        file_hashes = project.get("file_hashes", {})
        for filename in PROJECT_RELEASE_FILES:
            path = project_dir / filename
            if not path.exists():
                _issue(issues, "project_release_file_missing", f"project {project_id} is missing required file {filename}", path=path)
                continue
            expected_hash = file_hashes.get(filename)
            if not expected_hash:
                _issue(issues, "project_file_hash_missing", f"project {project_id} manifest lacks hash for {filename}", path=path)
            elif _file_sha256(path) != expected_hash:
                _issue(issues, "project_file_hash_mismatch", f"project {project_id} hash mismatch for {filename}", path=path)
        profile = read_json(project_dir / "project_profile.json") if (project_dir / "project_profile.json").exists() else {}
        if profile.get("project_id") != project_id:
            _issue(issues, "project_profile_id_mismatch", f"project {project_id} profile has project_id={profile.get('project_id')}", path=project_dir / "project_profile.json")
        probe_counts[project_id] = _as_int(project.get("counts", {}).get("probes"))
    return probe_counts


def _check_project_probe_files(
    probes_dir: Path,
    split_counts: dict[str, Any],
    counts: dict[str, Any],
    project_by_id: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    split_rows: dict[str, list[dict[str, Any]]] = {}
    for split in PROJECT_RELEASE_SPLITS:
        path = probes_dir / f"{split}.jsonl"
        if not path.exists():
            _issue(issues, "project_split_probe_file_missing", f"project release probe file missing: {split}", path=path)
            split_rows[split] = []
            continue
        rows = read_jsonl(path)
        split_rows[split] = rows
        declared = _as_int(split_counts.get(split))
        if len(rows) != declared:
            _issue(issues, "project_split_probe_count_mismatch", f"{split}.jsonl has {len(rows)} rows but manifest declares {declared}", path=path)
        if declared == 0:
            _warn(warnings, "empty_project_split", f"project release split {split} is empty; acceptable for fixtures but weak for paper-scale evaluation", path=path)
        for row in rows:
            if row.get("split") != split:
                _issue(issues, "project_probe_split_field_mismatch", f"probe {row.get('probe_id')} has split={row.get('split')} in {split}.jsonl", path=path)
            source_project_id = row.get("source_project_id")
            if source_project_id not in project_by_id:
                _issue(issues, "probe_unknown_source_project", f"probe {row.get('probe_id')} references unknown source_project_id {source_project_id}", path=path)
    all_path = probes_dir / "all.jsonl"
    if not all_path.exists():
        _issue(issues, "all_project_probes_file_missing", "probes/all.jsonl is missing", path=all_path)
        all_rows: list[dict[str, Any]] = []
    else:
        all_rows = read_jsonl(all_path)
        declared_all = _as_int(counts.get("probes"))
        if len(all_rows) != declared_all:
            _issue(issues, "all_project_probe_count_mismatch", f"all.jsonl has {len(all_rows)} rows but manifest declares {declared_all}", path=all_path)
    return split_rows, all_rows


def _check_project_probe_consistency(
    split_rows: dict[str, list[dict[str, Any]]],
    all_rows: list[dict[str, Any]],
    project_by_id: dict[str, dict[str, Any]],
    split_members: dict[str, list[str]],
    project_probe_counts: dict[str, int],
    issues: list[dict[str, Any]],
) -> None:
    split_probe_keys = [_probe_key(row) for split in PROJECT_RELEASE_SPLITS for row in split_rows.get(split, [])]
    all_probe_keys = [_probe_key(row) for row in all_rows]
    _check_duplicate_ids("duplicate_split_probe", [str(key) for key in split_probe_keys], issues)
    _check_duplicate_ids("duplicate_all_probe", [str(key) for key in all_probe_keys], issues)
    if set(split_probe_keys) != set(all_probe_keys):
        _issue(issues, "all_project_probes_not_equal_split_union", "probes/all.jsonl does not contain exactly the union of train/dev/test probe rows")
    split_by_project = {project_id: split for split, project_ids in split_members.items() for project_id in project_ids}
    rows_by_project: dict[str, int] = {}
    for row in all_rows:
        project_id = row.get("source_project_id")
        if project_id in project_by_id:
            rows_by_project[project_id] = rows_by_project.get(project_id, 0) + 1
            expected_split = str(project_by_id[project_id].get("split"))
            if row.get("split") != expected_split:
                _issue(issues, "probe_manifest_split_mismatch", f"probe {row.get('probe_id')} split={row.get('split')} but project {project_id} manifest split={expected_split}")
            if split_by_project and split_by_project.get(project_id) != expected_split:
                _issue(issues, "probe_splits_manifest_mismatch", f"project {project_id} has inconsistent split assignment between probe rows and splits.json")
    for project_id, expected_count in project_probe_counts.items():
        actual_count = rows_by_project.get(project_id, 0)
        if actual_count != expected_count:
            _issue(issues, "probe_count_per_project_mismatch", f"project {project_id} has {actual_count} release probe rows but manifest declares {expected_count}")


def _project_release_report(
    release_dir: Path,
    issues: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    checks: dict[str, Any],
) -> dict[str, Any]:
    return {
        "release_dir": str(release_dir),
        "passed": not issues,
        "summary": {
            "issues": len(issues),
            "warnings": len(warnings),
            "issue_codes": sorted({issue["code"] for issue in issues}),
            "warning_codes": sorted({warning["code"] for warning in warnings}),
        },
        "checks": checks,
        "issues": issues,
        "warnings": warnings,
    }


def _read_required_json(path: Path, code: str, issues: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not path.exists():
        _issue(issues, code, f"required JSON file is missing: {path}", path=path)
        return None
    return read_json(path)


def _resolve_reference_path(value: Any, base_dir: Path) -> Path:
    if value in (None, ""):
        return base_dir / "__missing_reference_path__"
    path = Path(str(value))
    if path.is_absolute():
        return path
    candidates = [path, Path.cwd() / path, base_dir / path, base_dir.parent / path]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return path


def _project_split(project_id: str) -> str:
    bucket = int(hashlib.sha256(project_id.encode("utf-8")).hexdigest(), 16) % 10
    if bucket < 6:
        return "train"
    if bucket < 8:
        return "dev"
    return "test"


def _project_split_key(profile: ProjectProfile, source_manifest: dict[str, Any]) -> str:
    user_profile = profile.user_profile or {}
    metadata = profile.metadata or {}
    for value in (
        user_profile.get("repo"),
        user_profile.get("repository"),
        metadata.get("repo"),
        metadata.get("repository"),
        source_manifest.get("repo"),
        source_manifest.get("repo_filter"),
    ):
        if value:
            return str(value)
    return profile.project_id


def _probe_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("source_project_id", "")), str(row.get("probe_id", "")))


def _check_duplicate_ids(code: str, values: list[str], issues: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if not value:
            continue
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    if duplicates:
        _issue(issues, code, f"duplicate ids detected: {sorted(duplicates)}")


def _issue(issues: list[dict[str, Any]], code: str, message: str, path: Path | None = None) -> None:
    item: dict[str, Any] = {"code": code, "message": message}
    if path is not None:
        item["path"] = str(path)
    issues.append(item)


def _warn(warnings: list[dict[str, Any]], code: str, message: str, path: Path | None = None) -> None:
    item: dict[str, Any] = {"code": code, "message": message}
    if path is not None:
        item["path"] = str(path)
    warnings.append(item)


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
