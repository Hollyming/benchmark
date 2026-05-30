from pathlib import Path

from ultra_long_benchmark.pipelines.annotation_pack import build_gharchive_annotation_pack
from ultra_long_benchmark.pipelines.annotation_pack import build_gharchive_annotation_pack_batch
from ultra_long_benchmark.pipelines.annotation_pack import build_project_from_policy_rewrites
from ultra_long_benchmark.pipelines.annotation_pack import build_projects_from_policy_rewrite_batch
from ultra_long_benchmark.pipelines.annotation_pack import export_annotation_pack_release
from ultra_long_benchmark.pipelines.annotation_pack import export_policy_rewrite_prompts_batch
from ultra_long_benchmark.pipelines.annotation_pack import package_policy_rewrite_jobs
from ultra_long_benchmark.pipelines.annotation_pack import validate_policy_rewrite_proposals_batch
from ultra_long_benchmark.pipelines.baseline_configs import run_baseline_config_dir
from ultra_long_benchmark.pipelines.evaluation import run_project_release_baseline_evaluation
from ultra_long_benchmark.pipelines.evaluation import score_project_release_predictions
from ultra_long_benchmark.pipelines.gharchive_pilot import DEFAULT_FIXTURE_PATH as DEFAULT_GHARCHIVE_FIXTURE_PATH
from ultra_long_benchmark.pipelines.gharchive_pilot import build_gharchive_slice
from ultra_long_benchmark.pipelines.gharchive_pilot import plan_gharchive_stage
from ultra_long_benchmark.pipelines.grounded_pilot import run_manual_grounded_pilot
from ultra_long_benchmark.pipelines.github_fixture import run_github_fixture_pilot
from ultra_long_benchmark.pipelines.rewrite_audit import export_policy_rewrite_human_audit_pack
from ultra_long_benchmark.pipelines.rewrite_audit import validate_policy_rewrite_human_audit
from ultra_long_benchmark.pipelines.verifier import run_project_verifier
from ultra_long_benchmark.paper_tables import export_paper_tables
from ultra_long_benchmark.project_release import export_project_benchmark_release
from ultra_long_benchmark.project_release import export_project_submission_inputs
from ultra_long_benchmark.readiness import build_readiness_report
from ultra_long_benchmark.shared.io import read_json, read_jsonl, write_json, write_jsonl


ROOT = Path(__file__).resolve().parents[1]


def test_readiness_report_passes_with_required_evidence(tmp_path: Path):
    generated = _minimal_smoke_generated(tmp_path / "generated")
    projects_dir = generated / "projects"
    run_manual_grounded_pilot(projects_dir)
    run_github_fixture_pilot(projects_dir)
    pack_dir = generated / "annotation_packs" / "gharchive_policy"
    build_gharchive_annotation_pack(DEFAULT_GHARCHIVE_FIXTURE_PATH, repo="acme/docs", output_dir=pack_dir)
    batch_dir = generated / "annotation_packs" / "gharchive_batch"
    build_gharchive_annotation_pack_batch(ROOT / "tests" / "fixtures" / "gharchive_multi_repo_sample.jsonl", output_dir=batch_dir)
    release_dir = generated / "release_packaging" / "gharchive_annotation_pack"
    export_annotation_pack_release(batch_dir, release_dir)
    prompt_dir = generated / "annotation_packs" / "gharchive_prompt_exports"
    export_policy_rewrite_prompts_batch(batch_dir, prompt_dir)
    package_policy_rewrite_jobs(prompt_dir, generated / "annotation_packs" / "rewrite_jobs", max_prompts_per_job=4)
    validation_report = validate_policy_rewrite_proposals_batch(
        batch_dir,
        ROOT / "examples" / "annotation_rewrites" / "gharchive_batch_rewrite_examples.jsonl",
        generated / "annotation_packs" / "gharchive_rewrite_validation_batch",
    )
    assert validation_report["passed"] is True
    audit_dir = generated / "annotation_packs" / "rewrite_human_audit"
    export_policy_rewrite_human_audit_pack(
        generated / "annotation_packs" / "gharchive_rewrite_validation_batch" / "batch_rewrite_validation_report.json",
        audit_dir,
        sample_size=4,
        seed=0,
    )
    write_jsonl(
        audit_dir / "audit_decisions.jsonl",
        [
            row | {"decision": "accept", "reviewer_id": "reviewer_1", "notes": "grounded"}
            for row in read_jsonl(audit_dir / "audit_decisions_template.jsonl")
        ],
    )
    audit_report = validate_policy_rewrite_human_audit(
        audit_dir,
        audit_dir / "audit_decisions.jsonl",
        output_path=audit_dir / "audit_validation_report.json",
    )
    assert audit_report["passed"] is True
    batch_project_report = build_projects_from_policy_rewrite_batch(
        generated / "annotation_packs" / "gharchive_rewrite_validation_batch" / "batch_rewrite_validation_report.json",
        projects_dir,
        project_prefix="project_gharchive_rewrite_batch",
    )
    assert batch_project_report["passed"] is True
    project_release_dir = generated / "release_packaging" / "project_benchmark"
    export_project_benchmark_release(
        [Path(project["project_dir"]) for project in batch_project_report["projects"]],
        project_release_dir,
    )
    export_project_submission_inputs(
        project_release_dir,
        generated / "evaluation_harness" / "project_submission_inputs",
    )
    run_project_release_baseline_evaluation(
        project_release_dir,
        generated / "evaluation_harness" / "project_release_baselines.json",
        baseline_names=["raw_rag", "oracle_policy_graph"],
    )
    prediction_path = generated / "evaluation_harness" / "project_release_predictions.jsonl"
    _write_project_release_predictions(project_release_dir, prediction_path)
    score_project_release_predictions(
        project_release_dir,
        prediction_path,
        generated / "evaluation_harness" / "project_release_prediction_report.json",
        system_name="readiness_fixture_submission",
    )
    export_paper_tables(
        generated / "evaluation_harness" / "paper_tables",
        release_baseline_report=generated / "evaluation_harness" / "project_release_baselines.json",
        prediction_reports=[generated / "evaluation_harness" / "project_release_prediction_report.json"],
    )
    build_project_from_policy_rewrites(
        pack_dir / "annotation_pack.json",
        ROOT / "examples" / "annotation_rewrites" / "gharchive_rewrite_examples.jsonl",
        projects_dir,
        project_id="project_gharchive_rewrite_001",
    )
    report = run_project_verifier(projects_dir / "project_gharchive_rewrite_001")
    assert report.passed is True
    run_baseline_config_dir(_local_config_dir(tmp_path, generated), generated / "evaluation_harness" / "baseline_batch")
    discovery_path = _local_discovery_report(generated)
    build_gharchive_slice(
        ROOT / "tests" / "fixtures" / "gharchive_multi_repo_sample.jsonl",
        generated / "gharchive_staged_slice.jsonl",
        manifest_path=generated / "gharchive_staged_slice_manifest.json",
    )
    plan_gharchive_stage(
        ROOT / "tests" / "fixtures" / "gharchive_multi_repo_sample.jsonl",
        profile="fixture",
        output_path=generated / "gharchive_stage_plan.json",
    )

    readiness = build_readiness_report(
        generated,
        output_path=generated / "readiness_report.json",
        paper_scale_profile="fixture",
        public_data_discovery_path=discovery_path,
    )

    assert readiness["passed"] is True
    assert readiness["summary"]["failed"] == 0
    assert readiness["checks"]["baseline_batch"]["status"] == "pass"
    assert readiness["checks"]["release_integrity"]["status"] == "warn"
    assert readiness["checks"]["release_integrity"]["evidence"]["summary"]["warning_codes"] == ["empty_split"]
    assert readiness["checks"]["paper_scale"]["status"] == "warn"
    assert readiness["checks"]["paper_scale"]["evidence"]["profile"] == "fixture"
    assert readiness["checks"]["public_data_discovery"]["status"] == "warn"
    assert readiness["checks"]["workflow_source_audit"]["status"] == "warn"
    assert readiness["checks"]["workflow_source_audit"]["evidence"]["annotation_budget_ready"] is False
    assert readiness["checks"]["batch_rewrite_validation"]["status"] == "pass"
    assert readiness["checks"]["batch_rewrite_projects"]["status"] == "pass"
    assert readiness["checks"]["batch_rewrite_projects"]["evidence"]["summary"]["projects_passed"] == 2
    assert readiness["checks"]["project_benchmark_release"]["status"] == "warn"
    assert readiness["checks"]["project_benchmark_release"]["evidence"]["summary"]["warning_codes"] == ["empty_project_split"]
    assert readiness["checks"]["project_submission_inputs"]["status"] == "pass"
    assert readiness["checks"]["project_release_baselines"]["status"] == "pass"
    assert readiness["checks"]["project_release_prediction_scoring"]["status"] == "pass"
    assert readiness["checks"]["paper_tables"]["status"] == "pass"
    assert readiness["checks"]["rewrite_human_audit"]["status"] == "pass"
    assert readiness["checks"]["rewrite_jobs"]["status"] == "pass"
    assert readiness["checks"]["rewrite_jobs"]["evidence"]["summary"]["jobs_total"] == 2
    assert readiness["checks"]["gharchive_stage_plan"]["status"] == "warn"
    assert readiness["checks"]["gharchive_stage_plan"]["evidence"]["decision"]["recommended_mode"] == "engineering_fixture"
    assert readiness["checks"]["prompt_exports"]["evidence"]["summary"]["prompts_total"] == 8
    assert (generated / "readiness_report.json").exists()


def test_readiness_report_can_require_paper_scale(tmp_path: Path):
    generated = _minimal_smoke_generated(tmp_path / "generated")
    projects_dir = generated / "projects"
    run_manual_grounded_pilot(projects_dir)
    pack_dir = generated / "annotation_packs" / "gharchive_policy"
    build_gharchive_annotation_pack(DEFAULT_GHARCHIVE_FIXTURE_PATH, repo="acme/docs", output_dir=pack_dir)
    batch_dir = generated / "annotation_packs" / "gharchive_batch"
    build_gharchive_annotation_pack_batch(ROOT / "tests" / "fixtures" / "gharchive_multi_repo_sample.jsonl", output_dir=batch_dir)
    release_dir = generated / "release_packaging" / "gharchive_annotation_pack"
    export_annotation_pack_release(batch_dir, release_dir)
    prompt_dir = generated / "annotation_packs" / "gharchive_prompt_exports"
    export_policy_rewrite_prompts_batch(batch_dir, prompt_dir)
    discovery_path = _local_discovery_report(generated)

    readiness = build_readiness_report(
        generated,
        annotation_release_dir=release_dir,
        prompt_export_dir=prompt_dir,
        rewrite_project_dir=projects_dir / "missing_rewrite_project",
        public_data_discovery_path=discovery_path,
        require_paper_scale=True,
    )

    assert readiness["passed"] is False
    assert readiness["checks"]["paper_scale"]["status"] == "fail"
    assert readiness["checks"]["workflow_source_audit"]["status"] == "fail"
    assert "paper_scale" in readiness["summary"]["blocking_checks"]
    assert "workflow_source_audit" in readiness["summary"]["blocking_checks"]


def test_readiness_report_accepts_paper_ready_workflow_source_audit(tmp_path: Path):
    generated = _minimal_smoke_generated(tmp_path / "generated")
    discovery_path = generated / "public_data_discovery_report.json"
    stage_plan_path = generated / "gharchive_stage_plan.json"
    audit_path = generated / "workflow_data_source_audit.json"
    write_json(
        discovery_path,
        {
            "summary": {
                "candidates_total": 1,
                "usable_sources": 1,
                "gharchive_event_sources": 1,
                "email_manifest_sources": 0,
                "github_code_only_sources": 0,
                "by_kind": {"gharchive_public_events": 1},
            },
            "usable_sources": [{"path": "/data1/public/gharchive/sample.jsonl", "dataset_kind": "gharchive_public_events"}],
            "recommended_next_actions": [],
            "authoritative_source_plan": [],
        },
    )
    write_json(
        stage_plan_path,
        {
            "profile": "paper",
            "summary": {"passed": True, "failed": 0, "warnings": 0},
            "decision": {
                "ready_for_annotation_budget": True,
                "recommended_mode": "paper_scale_annotation",
                "blocking_checks": [],
                "rationale": "ready",
            },
        },
    )
    write_json(
        audit_path,
        {
            "discovery_report_path": str(discovery_path),
            "gharchive_stage_plan_path": str(stage_plan_path),
            "passed": True,
            "annotation_budget_ready": True,
            "paper_ready": True,
            "summary": {
                "issues": 0,
                "warnings": 0,
                "issue_codes": [],
                "warning_codes": [],
                "usable_sources": 1,
                "gharchive_sources": 1,
                "email_manifest_sources": 0,
                "require_paper_ready": True,
            },
            "issues": [],
            "warnings": [],
            "stage_plan_decision": {
                "ready_for_annotation_budget": True,
                "recommended_mode": "paper_scale_annotation",
                "blocking_checks": [],
            },
            "recommended_next_actions": [],
        },
    )

    readiness = build_readiness_report(
        generated,
        public_data_discovery_path=discovery_path,
        gharchive_stage_plan_path=stage_plan_path,
        workflow_source_audit_path=audit_path,
        require_paper_scale=True,
    )

    assert readiness["checks"]["workflow_source_audit"]["status"] == "pass"


def test_readiness_report_fails_when_required_reports_are_missing(tmp_path: Path):
    generated = _minimal_smoke_generated(tmp_path / "generated")

    readiness = build_readiness_report(generated, public_data_discovery_path=_local_discovery_report(generated))

    assert readiness["passed"] is False
    assert "baseline_batch" in readiness["summary"]["blocking_checks"]
    assert readiness["checks"]["staged_slice_manifest"]["status"] == "warn"


def _minimal_smoke_generated(generated: Path) -> Path:
    write_jsonl(
        generated / "seed_corpora_ingestion" / "source_documents.jsonl",
        [
            {
                "doc_id": "doc_1",
                "title": "Seed",
                "text": "Seed document.",
                "created_at": "2026-01-01",
                "provenance": {"source_id": "local", "origin": "fixture"},
                "metadata": {},
            }
        ],
    )
    write_jsonl(
        generated / "persona_life_event_simulation" / "personas.jsonl",
        [
            {
                "persona_id": "p1",
                "display_name": "User",
                "baseline_profile": {},
                "events": [
                    {
                        "event_id": "e1",
                        "persona_id": "p1",
                        "timestamp": "2026-01-01T00:00:00Z",
                        "event_type": "policy",
                        "summary": "Policy event",
                        "details": {},
                        "capabilities": ["user_policy_induction"],
                        "provenance": [],
                        "privacy_tags": [],
                    }
                ],
            }
        ],
    )
    write_jsonl(
        generated / "multi_session_agent_trajectory_generation" / "trajectories.jsonl",
        [
            {
                "trajectory_id": "t1",
                "persona_id": "p1",
                "sessions": [
                    {
                        "session_id": "s1",
                        "persona_id": "p1",
                        "start_time": "2026-01-01T00:00:00Z",
                        "messages": [],
                        "linked_event_ids": ["e1"],
                    }
                ],
                "metadata": {},
            }
        ],
    )
    write_jsonl(
        generated / "memory_challenge_query_generation" / "queries.jsonl",
        [
            {
                "query_id": "q1",
                "trajectory_id": "t1",
                "persona_id": "p1",
                "capability": "user_policy_induction",
                "prompt": "What should the agent do?",
                "answer": "Follow policy.",
                "evidence_event_ids": ["e1"],
                "memory_task": "implicit_policy_induction",
                "expected_behavior": "answer",
                "privacy_sensitive": False,
                "rubric": {},
            }
        ],
    )
    write_json(generated / "annotation_and_quality_control" / "qc_report.json", {"passed": True, "issues": [], "counts": {}})
    return generated


def _local_config_dir(tmp_path: Path, generated: Path) -> Path:
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    project_dir = generated / "projects" / "project_gharchive_rewrite_001"
    (config_dir / "raw_rag.yaml").write_text(
        f"""
baseline:
  name: raw_rag_project
  family: retrieval
  entrypoint: ultra_long_benchmark.cli:evaluate-project
  requires_llm_api: false
  requires_gpu: false
  memory_backend: none
data:
  project_dir: {project_dir}
  output_path: {generated / "evaluation_harness" / "raw_rag.json"}
evaluation:
  mode: project_probe_text
  top_k: 3
  baselines: [raw_rag]
  metrics: [must_include_recall, evidence_recall]
resources:
  partition: cpu
  gpus: 0
  cpus_per_task: 2
  mem: 8G
  time: "00:20:00"
reproducibility:
  seed: 0
""",
        encoding="utf-8",
    )
    return config_dir


def _local_discovery_report(generated: Path) -> Path:
    path = generated / "public_data_discovery_report.json"
    write_json(
        path,
        {
            "summary": {
                "candidates_total": 1,
                "usable_sources": 0,
                "gharchive_event_sources": 0,
                "email_manifest_sources": 0,
                "github_code_only_sources": 1,
                "by_kind": {"github_code_corpus_not_workflow": 1},
            },
            "recommended_next_actions": ["stage GHArchive workflow events"],
        },
    )
    return path


def _write_project_release_predictions(release_dir: Path, output_path: Path) -> None:
    manifest = read_json(release_dir / "project_release_manifest.json")
    rows = []
    for project in manifest["projects"]:
        project_dir = Path(project["project_dir"])
        project_id = read_json(project_dir / "project_profile.json")["project_id"]
        for probe in read_jsonl(project_dir / "probes.jsonl"):
            rows.append(
                {
                    "prediction_id": f"pred_{project_id}_{probe['probe_id']}",
                    "project_id": project_id,
                    "probe_id": probe["probe_id"],
                    "prediction": (
                        " ".join(probe["expected_behavior"].get("must_include", []))
                        + " do not "
                        + " ".join(probe["expected_behavior"].get("must_not_include", []))
                        + " "
                        + " ".join(_positive_boundary_terms(project_dir, probe))
                    ),
                    "retrieved_memory_ids": probe["evidence"]["positive"],
                    "retrieved_event_ids": _positive_event_ids(project_dir, probe),
                    "retrieved_artifact_ids": [],
                }
            )
    write_jsonl(output_path, rows)


def _positive_event_ids(project_dir: Path, probe: dict) -> list[str]:
    graph = read_json(project_dir / "memory_graph.json")
    memory_by_id = {memory["memory_id"]: memory for memory in graph["memories"]}
    event_ids = []
    for memory_id in probe["evidence"]["positive"]:
        event_ids.extend(memory_by_id[memory_id]["source_events"])
    return sorted(set(event_ids))


def _positive_boundary_terms(project_dir: Path, probe: dict) -> list[str]:
    graph = read_json(project_dir / "memory_graph.json")
    memory_by_id = {memory["memory_id"]: memory for memory in graph["memories"]}
    terms = []
    for memory_id in probe["evidence"]["positive"]:
        boundary = memory_by_id[memory_id].get("action_boundary") or {}
        for key in ["allowed_actions", "forbidden_actions", "requires_approval", "requires_clarification", "authorized_tools", "forbidden_tools"]:
            terms.extend(str(value).replace("_", " ") for value in boundary.get(key, []))
    return terms
