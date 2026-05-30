from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from ultra_long_benchmark.shared.io import read_json, read_jsonl, write_json


RELEASE_SPLITS = ("train", "dev", "test")


def verify_annotation_release_integrity(
    release_dir: Path,
    prompt_export_dir: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Verify a release skeleton is grounded, split-consistent, and prompt-covered."""

    release_dir = Path(release_dir)
    prompt_export_dir = Path(prompt_export_dir) if prompt_export_dir is not None else None
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    checks: dict[str, Any] = {}

    manifest_path = release_dir / "release_manifest.json"
    splits_path = release_dir / "splits.json"
    tasks_dir = release_dir / "tasks"
    manifest = _read_required_json(manifest_path, "release_manifest_missing", issues)
    splits = _read_required_json(splits_path, "splits_manifest_missing", issues)

    if manifest is None:
        report = _report(release_dir, prompt_export_dir, issues, warnings, checks)
        if output_path is not None:
            write_json(output_path, report)
        return report

    pack_records = list(manifest.get("packs", []))
    counts = manifest.get("counts", {})
    split_counts = manifest.get("splits", {})
    constraints = manifest.get("constraints", {})
    manifest_pack_ids = [str(pack.get("pack_id", "")) for pack in pack_records]
    pack_by_id = {str(pack.get("pack_id", "")): pack for pack in pack_records if pack.get("pack_id")}

    _check_release_constraints(constraints, issues)
    _check_manifest_counts(counts, split_counts, pack_records, issues)
    _check_duplicate_ids("duplicate_pack_id", manifest_pack_ids, issues)
    checks["manifest"] = {
        "packs": len(pack_records),
        "declared_packs": counts.get("packs"),
        "declared_tasks": counts.get("tasks"),
        "constraints": constraints,
    }

    pack_task_counts, pack_repo_split = _check_pack_records(pack_records, release_dir, issues)
    split_members = _check_splits_manifest(splits, pack_by_id, pack_repo_split, issues) if splits is not None else {}
    split_rows, all_rows = _check_split_task_files(tasks_dir, split_counts, counts, pack_by_id, issues, warnings)
    _check_task_pack_consistency(split_rows, all_rows, pack_by_id, split_members, pack_task_counts, issues)

    checks["tasks"] = {
        "split_counts": {split: len(split_rows.get(split, [])) for split in RELEASE_SPLITS},
        "all_tasks": len(all_rows),
        "declared_splits": split_counts,
    }
    checks["splits"] = {
        "packs_by_split": {split: len(split_members.get(split, [])) for split in RELEASE_SPLITS},
        "repo_disjoint": not any(issue["code"] == "repo_in_multiple_splits" for issue in issues),
    }

    if prompt_export_dir is not None:
        checks["prompt_exports"] = _check_prompt_exports(prompt_export_dir, pack_by_id, all_rows, issues)

    report = _report(release_dir, prompt_export_dir, issues, warnings, checks)
    if output_path is not None:
        write_json(output_path, report)
    return report


def _check_release_constraints(constraints: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    if constraints.get("llm_generation_allowed") is not False:
        _issue(issues, "release_llm_generation_allowed_not_false", "release constraints must set llm_generation_allowed=false")
    if constraints.get("requires_validate_policy_rewrites") is not True:
        _issue(issues, "release_rewrite_validation_not_required", "release constraints must require validate-policy-rewrites")


def _check_manifest_counts(
    counts: dict[str, Any],
    split_counts: dict[str, Any],
    pack_records: list[dict[str, Any]],
    issues: list[dict[str, Any]],
) -> None:
    declared_packs = _as_int(counts.get("packs"))
    declared_tasks = _as_int(counts.get("tasks"))
    split_task_total = sum(_as_int(split_counts.get(split)) for split in RELEASE_SPLITS)
    pack_task_total = sum(_as_int(pack.get("tasks")) for pack in pack_records)
    if declared_packs <= 0:
        _issue(issues, "release_has_no_packs", "release manifest declares no packs")
    if declared_tasks <= 0:
        _issue(issues, "release_has_no_tasks", "release manifest declares no tasks")
    if declared_packs != len(pack_records):
        _issue(issues, "pack_count_mismatch", f"counts.packs={declared_packs} but packs list has {len(pack_records)} records")
    if declared_tasks != split_task_total:
        _issue(issues, "split_task_total_mismatch", f"counts.tasks={declared_tasks} but manifest splits sum to {split_task_total}")
    if declared_tasks != pack_task_total:
        _issue(issues, "pack_task_total_mismatch", f"counts.tasks={declared_tasks} but pack task counts sum to {pack_task_total}")


def _check_pack_records(
    pack_records: list[dict[str, Any]],
    release_dir: Path,
    issues: list[dict[str, Any]],
) -> tuple[dict[str, int], dict[str, str]]:
    pack_task_counts: dict[str, int] = {}
    repo_split_by_repo: dict[str, str] = {}
    split_by_pack: dict[str, str] = {}
    for pack in pack_records:
        pack_id = str(pack.get("pack_id", ""))
        repo = str(pack.get("repo", ""))
        split = str(pack.get("split", ""))
        if not pack_id:
            _issue(issues, "pack_id_missing", "release pack record is missing pack_id")
            continue
        if split not in RELEASE_SPLITS:
            _issue(issues, "invalid_pack_split", f"pack {pack_id} has invalid split {split!r}")
        if repo:
            previous = repo_split_by_repo.get(repo)
            if previous is not None and previous != split:
                _issue(issues, "repo_in_multiple_splits", f"repo {repo} appears in both {previous} and {split}")
            repo_split_by_repo[repo] = split
        split_by_pack[pack_id] = split
        pack_task_counts[pack_id] = _as_int(pack.get("tasks"))
        pack_path_value = pack.get("path")
        if not pack_path_value:
            _issue(issues, "pack_path_missing", f"pack {pack_id} is missing path")
            continue
        pack_path = _resolve_reference_path(pack_path_value, release_dir)
        if not pack_path.exists():
            _issue(issues, "pack_file_missing", f"pack file missing for {pack_id}", path=pack_path)
            continue
        actual_hash = _file_sha256(pack_path)
        if actual_hash != pack.get("content_hash"):
            _issue(issues, "pack_content_hash_mismatch", f"pack {pack_id} content_hash does not match file", path=pack_path)
        pack_json = read_json(pack_path)
        if pack_json.get("pack_id") != pack_id:
            _issue(issues, "pack_id_mismatch", f"manifest pack_id {pack_id} does not match file pack_id {pack_json.get('pack_id')}", path=pack_path)
        if pack_json.get("repo_filter") and repo and pack_json.get("repo_filter") != repo:
            _issue(issues, "pack_repo_mismatch", f"pack {pack_id} repo mismatch: manifest={repo} file={pack_json.get('repo_filter')}", path=pack_path)
        if len(pack_json.get("tasks", [])) != pack_task_counts[pack_id]:
            _issue(
                issues,
                "pack_task_count_mismatch",
                f"pack {pack_id} declares {pack_task_counts[pack_id]} tasks but file has {len(pack_json.get('tasks', []))}",
                path=pack_path,
            )
    return pack_task_counts, split_by_pack


def _check_splits_manifest(
    splits: dict[str, Any],
    pack_by_id: dict[str, dict[str, Any]],
    split_by_pack: dict[str, str],
    issues: list[dict[str, Any]],
) -> dict[str, list[str]]:
    split_members = {split: [str(pack_id) for pack_id in splits.get(split, [])] for split in RELEASE_SPLITS}
    all_members = [pack_id for members in split_members.values() for pack_id in members]
    _check_duplicate_ids("duplicate_split_pack_id", all_members, issues)
    unknown = sorted(set(all_members) - set(pack_by_id))
    missing = sorted(set(pack_by_id) - set(all_members))
    if unknown:
        _issue(issues, "split_references_unknown_pack", f"splits.json references unknown packs: {unknown}")
    if missing:
        _issue(issues, "split_missing_manifest_pack", f"splits.json omits manifest packs: {missing}")
    for split, members in split_members.items():
        for pack_id in members:
            manifest_split = split_by_pack.get(pack_id)
            if manifest_split is not None and manifest_split != split:
                _issue(issues, "split_pack_assignment_mismatch", f"pack {pack_id} is in splits.{split} but manifest split is {manifest_split}")
    return split_members


def _check_split_task_files(
    tasks_dir: Path,
    split_counts: dict[str, Any],
    counts: dict[str, Any],
    pack_by_id: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    split_rows: dict[str, list[dict[str, Any]]] = {}
    for split in RELEASE_SPLITS:
        path = tasks_dir / f"{split}.jsonl"
        if not path.exists():
            _issue(issues, "split_task_file_missing", f"split task file missing: {split}", path=path)
            split_rows[split] = []
            continue
        rows = read_jsonl(path)
        split_rows[split] = rows
        declared = _as_int(split_counts.get(split))
        if len(rows) != declared:
            _issue(issues, "split_task_count_mismatch", f"{split}.jsonl has {len(rows)} rows but manifest declares {declared}", path=path)
        if declared == 0:
            _warn(warnings, "empty_split", f"release split {split} is empty; acceptable for fixtures but weak for paper-scale evaluation", path=path)
        for row in rows:
            if row.get("split") != split:
                _issue(issues, "task_split_field_mismatch", f"task {row.get('annotation_id')} has split={row.get('split')} in {split}.jsonl", path=path)
            source_pack_id = row.get("source_pack_id")
            if source_pack_id not in pack_by_id:
                _issue(issues, "task_unknown_source_pack", f"task {row.get('annotation_id')} references unknown source_pack_id {source_pack_id}", path=path)

    all_path = tasks_dir / "all.jsonl"
    if not all_path.exists():
        _issue(issues, "all_tasks_file_missing", "tasks/all.jsonl is missing", path=all_path)
        all_rows: list[dict[str, Any]] = []
    else:
        all_rows = read_jsonl(all_path)
        declared_all = _as_int(counts.get("tasks"))
        if len(all_rows) != declared_all:
            _issue(issues, "all_task_count_mismatch", f"all.jsonl has {len(all_rows)} rows but manifest declares {declared_all}", path=all_path)
    return split_rows, all_rows


def _check_task_pack_consistency(
    split_rows: dict[str, list[dict[str, Any]]],
    all_rows: list[dict[str, Any]],
    pack_by_id: dict[str, dict[str, Any]],
    split_members: dict[str, list[str]],
    pack_task_counts: dict[str, int],
    issues: list[dict[str, Any]],
) -> None:
    split_task_keys = [_task_key(row) for split in RELEASE_SPLITS for row in split_rows.get(split, [])]
    all_task_keys = [_task_key(row) for row in all_rows]
    _check_duplicate_ids("duplicate_split_task", [str(key) for key in split_task_keys], issues)
    _check_duplicate_ids("duplicate_all_task", [str(key) for key in all_task_keys], issues)
    if set(split_task_keys) != set(all_task_keys):
        _issue(issues, "all_tasks_not_equal_split_union", "tasks/all.jsonl does not contain exactly the union of train/dev/test task rows")

    split_by_pack = {pack_id: split for split, pack_ids in split_members.items() for pack_id in pack_ids}
    rows_by_pack: dict[str, int] = {}
    for row in all_rows:
        pack_id = row.get("source_pack_id")
        if pack_id in pack_by_id:
            rows_by_pack[pack_id] = rows_by_pack.get(pack_id, 0) + 1
            row_split = row.get("split")
            expected_split = str(pack_by_id[pack_id].get("split"))
            if row_split != expected_split:
                _issue(issues, "task_manifest_split_mismatch", f"task {row.get('annotation_id')} split={row_split} but pack {pack_id} manifest split={expected_split}")
            if split_by_pack and split_by_pack.get(pack_id) != expected_split:
                _issue(issues, "task_splits_manifest_mismatch", f"pack {pack_id} has inconsistent split assignment between task rows and splits.json")
    for pack_id, expected_count in pack_task_counts.items():
        actual_count = rows_by_pack.get(pack_id, 0)
        if actual_count != expected_count:
            _issue(issues, "task_count_per_pack_mismatch", f"pack {pack_id} has {actual_count} release task rows but manifest declares {expected_count}")


def _check_prompt_exports(
    prompt_export_dir: Path,
    pack_by_id: dict[str, dict[str, Any]],
    release_tasks: list[dict[str, Any]],
    issues: list[dict[str, Any]],
) -> dict[str, Any]:
    report_path = prompt_export_dir / "rewrite_prompt_batch_report.json"
    report = _read_required_json(report_path, "prompt_batch_report_missing", issues)
    if report is None:
        return {"path": str(report_path), "exports": 0, "prompts": 0}

    constraints = report.get("constraints", {})
    if constraints.get("llm_generation_performed") is not False:
        _issue(issues, "prompt_export_llm_generation_not_false", "prompt batch report must set llm_generation_performed=false", path=report_path)
    if constraints.get("requires_validate_policy_rewrites") is not True:
        _issue(issues, "prompt_export_validation_not_required", "prompt batch report must require validate-policy-rewrites", path=report_path)

    exports = list(report.get("exports", []))
    export_pack_ids = [str(item.get("pack_id", "")) for item in exports]
    _check_duplicate_ids("duplicate_prompt_export_pack_id", export_pack_ids, issues)
    missing_packs = sorted(set(pack_by_id) - set(export_pack_ids))
    extra_packs = sorted(set(export_pack_ids) - set(pack_by_id))
    if missing_packs:
        _issue(issues, "prompt_export_missing_release_pack", f"prompt exports are missing release packs: {missing_packs}", path=report_path)
    if extra_packs:
        _issue(issues, "prompt_export_unknown_pack", f"prompt exports contain packs absent from release manifest: {extra_packs}", path=report_path)

    release_annotations_by_pack: dict[str, set[str]] = {}
    for row in release_tasks:
        release_annotations_by_pack.setdefault(str(row.get("source_pack_id")), set()).add(str(row.get("annotation_id")))

    prompts_total = 0
    for export in exports:
        pack_id = str(export.get("pack_id", ""))
        output_path = _resolve_reference_path(export.get("output_path", ""), prompt_export_dir)
        if not output_path.exists():
            _issue(issues, "prompt_export_file_missing", f"prompt export file missing for pack {pack_id}", path=output_path)
            continue
        prompts = read_jsonl(output_path)
        prompts_total += len(prompts)
        declared_prompts = _as_int(export.get("prompts"))
        if declared_prompts <= 0:
            _issue(issues, "prompt_export_empty", f"prompt export for pack {pack_id} declares no prompts", path=output_path)
        if len(prompts) != declared_prompts:
            _issue(issues, "prompt_export_count_mismatch", f"prompt export for pack {pack_id} has {len(prompts)} rows but report declares {declared_prompts}", path=output_path)
        prompt_annotations = set()
        for prompt in prompts:
            if prompt.get("pack_id") != pack_id:
                _issue(issues, "prompt_pack_id_mismatch", f"prompt {prompt.get('prompt_id')} pack_id={prompt.get('pack_id')} but export pack is {pack_id}", path=output_path)
            annotation_id = str(prompt.get("annotation_id"))
            prompt_annotations.add(annotation_id)
            if pack_id in release_annotations_by_pack and annotation_id not in release_annotations_by_pack[pack_id]:
                _issue(issues, "prompt_unknown_annotation", f"prompt {prompt.get('prompt_id')} references annotation absent from release tasks", path=output_path)
            constraints = prompt.get("constraints", {})
            if not constraints.get("allowed_positive_event_ids"):
                _issue(issues, "prompt_missing_positive_event_constraints", f"prompt {prompt.get('prompt_id')} lacks allowed_positive_event_ids", path=output_path)
            boundary = constraints.get("must_preserve_action_boundary")
            if not isinstance(boundary, dict) or not boundary:
                _issue(issues, "prompt_missing_action_boundary_constraint", f"prompt {prompt.get('prompt_id')} lacks must_preserve_action_boundary", path=output_path)
        expected_annotations = release_annotations_by_pack.get(pack_id, set())
        if expected_annotations and prompt_annotations != expected_annotations:
            _issue(issues, "prompt_annotation_coverage_mismatch", f"prompt export for pack {pack_id} does not cover exactly its release annotations", path=output_path)

    summary = report.get("summary", {})
    if _as_int(summary.get("packs_total")) != len(exports):
        _issue(issues, "prompt_summary_pack_count_mismatch", "prompt summary packs_total does not match export records", path=report_path)
    if _as_int(summary.get("prompts_total")) != prompts_total:
        _issue(issues, "prompt_summary_total_mismatch", f"prompt summary prompts_total={summary.get('prompts_total')} but files contain {prompts_total}", path=report_path)
    return {
        "path": str(report_path),
        "exports": len(exports),
        "prompts": prompts_total,
        "constraints": report.get("constraints", {}),
    }


def _read_required_json(path: Path, code: str, issues: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not path.exists():
        _issue(issues, code, f"required JSON file is missing: {path}", path=path)
        return None
    return read_json(path)


def _report(
    release_dir: Path,
    prompt_export_dir: Path | None,
    issues: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    checks: dict[str, Any],
) -> dict[str, Any]:
    return {
        "release_dir": str(release_dir),
        "prompt_export_dir": str(prompt_export_dir) if prompt_export_dir is not None else None,
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


def _task_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (str(row.get("source_pack_id", "")), str(row.get("annotation_id", "")), str(row.get("candidate_id", "")))


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
