from pathlib import Path

from ultra_long_benchmark.pipelines.annotation_pack import build_gharchive_annotation_pack
from ultra_long_benchmark.pipelines.annotation_pack import build_gharchive_annotation_pack_batch
from ultra_long_benchmark.pipelines.annotation_pack import build_projects_from_policy_rewrite_batch
from ultra_long_benchmark.pipelines.annotation_pack import export_annotation_pack_release
from ultra_long_benchmark.pipelines.annotation_pack import export_policy_rewrite_prompts_batch
from ultra_long_benchmark.pipelines.annotation_pack import package_policy_rewrite_jobs
from ultra_long_benchmark.pipelines.annotation_pack import validate_policy_rewrite_proposals_batch
from ultra_long_benchmark.pipelines.baseline_configs import run_baseline_config_dir
from ultra_long_benchmark.pipelines.evaluation import run_project_release_baseline_evaluation
from ultra_long_benchmark.pipelines.evaluation import score_project_release_predictions
from ultra_long_benchmark.pipelines.gharchive import DEFAULT_FIXTURE_PATH as DEFAULT_GHARCHIVE_FIXTURE_PATH
from ultra_long_benchmark.pipelines.gharchive import build_gharchive_slice
from ultra_long_benchmark.pipelines.gharchive import plan_gharchive_stage
from ultra_long_benchmark.pipelines.gharchive import build_gharchive_project_fixture
from ultra_long_benchmark.pipelines.rewrite_audit import export_policy_rewrite_human_audit_pack
from ultra_long_benchmark.pipelines.rewrite_audit import validate_policy_rewrite_human_audit
from ultra_long_benchmark.artifact_bundle import audit_artifact_bundle
from ultra_long_benchmark.claim_lint import lint_paper_claims
from ultra_long_benchmark.data_discovery import discover_public_data_sources
from ultra_long_benchmark.paper_tables import export_paper_tables
from ultra_long_benchmark.project_release import export_project_benchmark_release
from ultra_long_benchmark.project_release import export_project_submission_inputs
from ultra_long_benchmark.readiness import build_readiness_report
from ultra_long_benchmark.shared.io import read_json, read_jsonl, write_json, write_jsonl
from ultra_long_benchmark.source_audit import audit_workflow_data_sources


ROOT = Path(__file__).resolve().parents[1]


def test_readiness_report_passes_with_required_evidence(tmp_path: Path):
    generated = _minimal_release_generated(tmp_path / "generated")
    projects_dir = generated / "projects"
    pack_dir = generated / "annotation_packs" / "gharchive_policy"
    build_gharchive_annotation_pack(DEFAULT_GHARCHIVE_FIXTURE_PATH, repo="acme/docs", output_dir=pack_dir)
    batch_dir = generated / "annotation_packs" / "gharchive_batch"
    build_gharchive_annotation_pack_batch(ROOT / "tests" / "fixtures" / "gharchive_multi_repo_sample.jsonl", output_dir=batch_dir)
    release_dir = generated / "release_packaging" / "gharchive_formal_annotation_pack"
    export_annotation_pack_release(batch_dir, release_dir)
    prompt_dir = generated / "annotation_packs" / "gharchive_formal_prompt_exports"
    export_policy_rewrite_prompts_batch(batch_dir, prompt_dir)
    package_policy_rewrite_jobs(prompt_dir, generated / "annotation_packs" / "gharchive_formal_rewrite_jobs", max_prompts_per_job=4)
    validation_report = validate_policy_rewrite_proposals_batch(
        batch_dir,
        ROOT / "examples" / "annotation_rewrites" / "gharchive_batch_rewrite_examples.jsonl",
        generated / "annotation_packs" / "gharchive_formal_validation",
    )
    assert validation_report["passed"] is True
    audit_dir = generated / "annotation_packs" / "gharchive_formal_human_audit"
    export_policy_rewrite_human_audit_pack(
        generated / "annotation_packs" / "gharchive_formal_validation" / "batch_rewrite_validation_report.json",
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
        generated / "annotation_packs" / "gharchive_formal_validation" / "batch_rewrite_validation_report.json",
        generated / "projects" / "gharchive_formal_batch",
        project_prefix="project_gharchive_rewrite_batch",
    )
    assert batch_project_report["passed"] is True
    project_release_dir = generated / "release_packaging" / "gharchive_formal_project_benchmark"
    export_project_benchmark_release(
        [Path(project["project_dir"]) for project in batch_project_report["projects"]],
        project_release_dir,
    )
    export_project_submission_inputs(
        project_release_dir,
        generated / "evaluation_harness" / "gharchive_formal_submission_inputs_hardened",
        harden_probe_queries=True,
    )
    run_project_release_baseline_evaluation(
        project_release_dir,
        generated / "evaluation_harness" / "gharchive_formal_project_release_baselines.json",
        baseline_names=["raw_rag", "oracle_policy_graph"],
    )
    prediction_path = generated / "evaluation_harness" / "gharchive_formal_memory_profile_stub_hardened_predictions.jsonl"
    _write_project_release_predictions(project_release_dir, prediction_path)
    score_project_release_predictions(
        project_release_dir,
        prediction_path,
        generated / "evaluation_harness" / "gharchive_formal_memory_profile_stub_hardened_score.json",
        system_name="readiness_fixture_submission",
    )
    export_paper_tables(
        generated / "evaluation_harness" / "gharchive_formal_paper_tables",
        release_baseline_report=generated / "evaluation_harness" / "gharchive_formal_project_release_baselines.json",
        prediction_reports=[generated / "evaluation_harness" / "gharchive_formal_memory_profile_stub_hardened_score.json"],
    )
    run_baseline_config_dir(_local_config_dir(tmp_path, generated), generated / "evaluation_harness" / "baseline_batch_after_claim_boundary")
    claim_lint_path = generated / "evaluation_harness" / "paper_claim_lint.json"
    claim_lint_docs = []
    for index in range(4):
        doc = generated / f"paper_claim_lint_doc_{index}.md"
        doc.write_text("The current release is a GitHub developer workflow release.\n", encoding="utf-8")
        claim_lint_docs.append(doc)
    lint_paper_claims(claim_lint_docs, output_path=claim_lint_path, root=generated)
    discovery_path = _local_discovery_report(generated)
    build_gharchive_slice(
        ROOT / "tests" / "fixtures" / "gharchive_multi_repo_sample.jsonl",
        generated / "gharchive_staged_slice.jsonl",
        manifest_path=generated / "longuserpolicy_2024_01_release_slice_manifest.json",
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
        claim_lint_path=claim_lint_path,
        staged_slice_manifest=generated / "longuserpolicy_2024_01_release_slice_manifest.json",
    )

    assert readiness["passed"] is True
    assert readiness["summary"]["checks_total"] == 23
    assert readiness["summary"]["failed"] == 0
    assert readiness["checks"]["claim_lint"]["status"] == "pass"
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
    assert readiness["checks"]["taxonomy_coverage_audit"]["status"] == "warn"
    assert readiness["checks"]["taxonomy_coverage_audit"]["evidence"]["summary"]["current_release_domain_scope"] == "github_developer_workflow_only"
    assert readiness["checks"]["taxonomy_coverage_audit"]["evidence"]["claim_boundary"]["multi_domain_release_ready"] is False
    assert readiness["checks"]["claim_boundary_audit"]["status"] == "warn"
    assert readiness["checks"]["rewrite_jobs"]["status"] == "pass"
    assert readiness["checks"]["rewrite_jobs"]["evidence"]["summary"]["jobs_total"] == 2
    assert readiness["checks"]["gharchive_stage_plan"]["status"] == "warn"
    assert readiness["checks"]["gharchive_stage_plan"]["evidence"]["decision"]["recommended_mode"] == "engineering_fixture"
    assert readiness["checks"]["prompt_exports"]["evidence"]["summary"]["prompts_total"] == 8
    assert (generated / "readiness_report.json").exists()


def test_readiness_report_can_require_paper_scale(tmp_path: Path):
    generated = _minimal_release_generated(tmp_path / "generated")
    projects_dir = generated / "projects"
    pack_dir = generated / "annotation_packs" / "gharchive_policy"
    build_gharchive_annotation_pack(DEFAULT_GHARCHIVE_FIXTURE_PATH, repo="acme/docs", output_dir=pack_dir)
    batch_dir = generated / "annotation_packs" / "gharchive_batch"
    build_gharchive_annotation_pack_batch(ROOT / "tests" / "fixtures" / "gharchive_multi_repo_sample.jsonl", output_dir=batch_dir)
    release_dir = generated / "release_packaging" / "gharchive_formal_annotation_pack"
    export_annotation_pack_release(batch_dir, release_dir)
    prompt_dir = generated / "annotation_packs" / "gharchive_formal_prompt_exports"
    export_policy_rewrite_prompts_batch(batch_dir, prompt_dir)
    discovery_path = _local_discovery_report(generated)

    readiness = build_readiness_report(
        generated,
        annotation_release_dir=release_dir,
        prompt_export_dir=prompt_dir,
        public_data_discovery_path=discovery_path,
        require_paper_scale=True,
    )

    assert readiness["passed"] is False
    assert readiness["checks"]["paper_scale"]["status"] == "fail"
    assert readiness["checks"]["workflow_source_audit"]["status"] == "fail"
    assert "paper_scale" in readiness["summary"]["blocking_checks"]
    assert "workflow_source_audit" in readiness["summary"]["blocking_checks"]


def test_readiness_report_accepts_paper_ready_workflow_source_audit(tmp_path: Path):
    generated = _minimal_release_generated(tmp_path / "generated")
    discovery_path = generated / "public_data_discovery_report.json"
    stage_plan_path = generated / "gharchive_stage_plan.json"
    audit_path = generated / "workflow_data_source_audit.json"
    source_root = generated / "source_data"
    write_jsonl(
        source_root / "gharchive" / "2026-04-01.jsonl",
        [
            {
                "id": "evt_1",
                "type": "PullRequestEvent",
                "actor": {"login": "alice"},
                "repo": {"name": "acme/docs"},
                "payload": {"action": "opened", "pull_request": {"title": "Docs update"}},
                "created_at": "2026-04-01T00:00:00Z",
            }
        ],
    )
    discover_public_data_sources([source_root], output_path=discovery_path)
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
    audit_workflow_data_sources(
        discovery_path,
        output_path=audit_path,
        gharchive_stage_plan_path=stage_plan_path,
        require_paper_ready=True,
    )

    readiness = build_readiness_report(
        generated,
        public_data_discovery_path=discovery_path,
        gharchive_stage_plan_path=stage_plan_path,
        workflow_source_audit_path=audit_path,
        require_paper_scale=True,
    )

    check = readiness["checks"]["workflow_source_audit"]
    assert check["status"] == "warn"
    assert check["evidence"]["paper_ready"] is True
    assert check["evidence"]["verification_summary"]["issues"] == 0
    assert "workflow_source_audit" not in readiness["summary"]["blocking_checks"]


def test_readiness_report_warns_when_workflow_source_audit_inputs_drift(tmp_path: Path):
    generated = _minimal_release_generated(tmp_path / "generated")
    discovery_path = generated / "public_data_discovery_report.json"
    stage_plan_path = generated / "gharchive_stage_plan.json"
    audit_path = generated / "workflow_data_source_audit.json"
    source_root = generated / "source_data"
    write_jsonl(
        source_root / "gharchive" / "2026-04-01.jsonl",
        [
            {
                "id": "evt_1",
                "type": "PullRequestEvent",
                "actor": {"login": "alice"},
                "repo": {"name": "acme/docs"},
                "payload": {"action": "opened", "pull_request": {"title": "Docs update"}},
                "created_at": "2026-04-01T00:00:00Z",
            }
        ],
    )
    discover_public_data_sources([source_root], output_path=discovery_path)
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
    audit_workflow_data_sources(
        discovery_path,
        output_path=audit_path,
        gharchive_stage_plan_path=stage_plan_path,
        require_paper_ready=True,
    )
    discovery = read_json(discovery_path)
    discovery["summary"]["usable_sources"] = 0
    write_json(discovery_path, discovery)

    readiness = build_readiness_report(
        generated,
        public_data_discovery_path=discovery_path,
        gharchive_stage_plan_path=stage_plan_path,
        workflow_source_audit_path=audit_path,
    )

    check = readiness["checks"]["workflow_source_audit"]
    assert check["status"] == "warn"
    assert "workflow source audit inputs changed or lack digests" in check["issues"]
    assert "workflow_source_audit_discovery_verification_not_passed" in check["evidence"]["verification_summary"]["issue_codes"]


def test_readiness_report_fails_when_required_reports_are_missing(tmp_path: Path):
    generated = _minimal_release_generated(tmp_path / "generated")

    readiness = build_readiness_report(generated, public_data_discovery_path=_local_discovery_report(generated))

    assert readiness["passed"] is False
    assert "baseline_batch" in readiness["summary"]["blocking_checks"]
    assert readiness["checks"]["staged_slice_manifest"]["status"] == "pass"


def test_readiness_report_fails_when_baseline_batch_output_drifts(tmp_path: Path):
    generated = _minimal_release_generated(tmp_path / "generated")
    summary = build_gharchive_project_fixture(generated / "projects", input_path=DEFAULT_GHARCHIVE_FIXTURE_PATH, repo_full_name="acme/docs")
    project_release_dir = generated / "release_packaging" / "gharchive_formal_project_benchmark"
    export_project_benchmark_release([Path(summary["project_dir"])], project_release_dir)
    export_project_submission_inputs(
        project_release_dir,
        generated / "evaluation_harness" / "gharchive_formal_submission_inputs_hardened",
        harden_probe_queries=True,
    )
    batch_dir = generated / "evaluation_harness" / "baseline_batch_after_claim_boundary"
    batch = run_baseline_config_dir(_local_config_dir(tmp_path, generated), batch_dir)
    output_path = Path(batch["reports"][0]["output_path"])
    output = read_json(output_path)
    output["changed_after_batch"] = True
    write_json(output_path, output)

    readiness = build_readiness_report(generated, public_data_discovery_path=_local_discovery_report(generated))

    check = readiness["checks"]["baseline_batch"]
    assert check["status"] == "fail"
    assert "baseline batch runner reports or outputs changed or lack digests" in check["issues"]
    assert "baseline_batch_output_artifact_sha256_mismatch" in check["evidence"]["verification_summary"]["issue_codes"]


def test_readiness_report_surfaces_claim_boundary_limits(tmp_path: Path):
    generated = _minimal_release_generated(tmp_path / "generated")
    claim_path = generated / "evaluation_harness" / "claim_boundary.json"
    write_json(
        claim_path,
        {
            "passed": True,
            "summary": {
                "claims_total": 3,
                "supported": 1,
                "qualified": 1,
                "blocked": 1,
                "supported_claims": ["core_task_taxonomy"],
                "qualified_claims": ["external_memory_runner_contract_ready"],
                "blocked_claims": ["multi_domain_office_release"],
            },
            "recommended_language": {
                "supported": ["Use the core taxonomy."],
                "qualified": ["Qualify external runner contract readiness."],
                "blocked": ["Do not claim multi-domain coverage."],
            },
        },
    )

    readiness = build_readiness_report(
        generated,
        public_data_discovery_path=_local_discovery_report(generated),
        claim_boundary_audit_path=claim_path,
    )

    check = readiness["checks"]["claim_boundary_audit"]
    assert check["status"] == "warn"
    assert "1 paper-facing claims are blocked" in check["issues"]
    assert "1 paper-facing claims require qualification" in check["issues"]
    assert check["evidence"]["summary"]["blocked_claims"] == ["multi_domain_office_release"]


def test_readiness_report_fails_failed_claim_boundary_audit(tmp_path: Path):
    generated = _minimal_release_generated(tmp_path / "generated")
    claim_path = generated / "evaluation_harness" / "claim_boundary.json"
    write_json(
        claim_path,
        {
            "passed": False,
            "summary": {"claims_total": 1, "supported": 0, "qualified": 0, "blocked": 0},
            "recommended_language": {},
        },
    )

    readiness = build_readiness_report(
        generated,
        public_data_discovery_path=_local_discovery_report(generated),
        claim_boundary_audit_path=claim_path,
    )

    assert readiness["checks"]["claim_boundary_audit"]["status"] == "fail"
    assert "claim_boundary_audit" in readiness["summary"]["blocking_checks"]


def test_readiness_report_warns_when_claim_lint_is_missing(tmp_path: Path):
    generated = _minimal_release_generated(tmp_path / "generated")

    readiness = build_readiness_report(
        generated,
        public_data_discovery_path=_local_discovery_report(generated),
        claim_lint_path=generated / "evaluation_harness" / "missing_claim_lint.json",
    )

    assert readiness["checks"]["claim_lint"]["status"] == "warn"
    assert readiness["checks"]["claim_lint"]["issues"] == ["paper claim lint report missing"]


def test_readiness_report_fails_failed_claim_lint(tmp_path: Path):
    generated = _minimal_release_generated(tmp_path / "generated")
    claim_lint_path = generated / "evaluation_harness" / "paper_claim_lint.json"
    write_json(
        claim_lint_path,
        {
            "passed": False,
            "summary": {
                "files_scanned": 4,
                "files_total": 4,
                "issues": 1,
                "allowed_blocked_claim_mentions": 0,
            },
        },
    )

    readiness = build_readiness_report(
        generated,
        public_data_discovery_path=_local_discovery_report(generated),
        claim_lint_path=claim_lint_path,
    )

    assert readiness["checks"]["claim_lint"]["status"] == "fail"
    assert "paper claim lint did not pass" in readiness["checks"]["claim_lint"]["issues"]
    assert "1 affirmative blocked-claim mentions were found" in readiness["checks"]["claim_lint"]["issues"]
    assert "claim_lint" in readiness["summary"]["blocking_checks"]


def test_readiness_report_fails_stale_claim_lint_without_source_digest(tmp_path: Path):
    generated = _minimal_release_generated(tmp_path / "generated")
    claim_lint_path = generated / "evaluation_harness" / "paper_claim_lint.json"
    doc_path = generated / "paper.md"
    doc_path.write_text("The current release is GitHub-only.\n", encoding="utf-8")
    write_json(
        claim_lint_path,
        {
            "passed": True,
            "root": str(generated),
            "summary": {"files_scanned": 1, "files_total": 1, "issues": 0},
            "checks": {"paper.md": {"status": "pass", "path": str(doc_path), "issues": []}},
        },
    )

    readiness = build_readiness_report(
        generated,
        public_data_discovery_path=_local_discovery_report(generated),
        claim_lint_path=claim_lint_path,
    )

    assert readiness["checks"]["claim_lint"]["status"] == "fail"
    assert "claim-lint report does not record a source digest: paper.md" in readiness["checks"]["claim_lint"]["issues"]


def test_readiness_report_surfaces_artifact_bundle_warnings(tmp_path: Path):
    generated = _minimal_release_generated(tmp_path / "generated")
    bundle_path = generated / "evaluation_harness" / "bundle.json"
    write_json(
        bundle_path,
        {
            "passed": True,
            "summary": {
                "artifacts_total": 3,
                "artifacts_present": 3,
                "issues": 0,
                "warnings": 1,
                "warning_codes": ["github_only_release_scope"],
            },
            "artifacts": {
                "readiness_report": {"status": "present"},
                "claim_boundary_audit": {"status": "present"},
                "taxonomy_coverage_audit": {"status": "present"},
            },
            "issues": [],
            "warnings": [{"code": "github_only_release_scope", "message": "GitHub-only release"}],
        },
    )

    readiness = build_readiness_report(
        generated,
        public_data_discovery_path=_local_discovery_report(generated),
        artifact_bundle_manifest_path=bundle_path,
    )

    check = readiness["checks"]["artifact_bundle_manifest"]
    assert check["status"] == "warn"
    assert "GitHub-only release" in check["issues"]
    assert check["evidence"]["summary"]["warning_codes"] == ["github_only_release_scope"]
    assert check["evidence"]["artifact_names"] == ["claim_boundary_audit", "readiness_report", "taxonomy_coverage_audit"]


def test_readiness_report_fails_failed_artifact_bundle(tmp_path: Path):
    generated = _minimal_release_generated(tmp_path / "generated")
    bundle_path = generated / "evaluation_harness" / "bundle.json"
    write_json(
        bundle_path,
        {
            "passed": False,
            "summary": {"artifacts_total": 1, "artifacts_present": 0, "issues": 1, "warnings": 0},
            "artifacts": {},
            "issues": [{"code": "artifact_missing", "message": "required artifact is missing"}],
            "warnings": [],
        },
    )

    readiness = build_readiness_report(
        generated,
        public_data_discovery_path=_local_discovery_report(generated),
        artifact_bundle_manifest_path=bundle_path,
    )

    assert readiness["checks"]["artifact_bundle_manifest"]["status"] == "fail"
    assert "artifact_bundle_manifest" in readiness["summary"]["blocking_checks"]


def test_readiness_report_fails_drifted_artifact_bundle(tmp_path: Path):
    generated = _minimal_release_generated(tmp_path / "generated")
    artifact_path = generated / "evaluation_harness" / "claim.json"
    bundle_path = generated / "evaluation_harness" / "bundle.json"
    write_json(artifact_path, {"passed": True, "summary": {"blocked": 0}})
    audit_artifact_bundle({"claim_boundary_audit": artifact_path}, output_path=bundle_path, root=generated)
    write_json(artifact_path, {"passed": True, "summary": {"blocked": 1}})

    readiness = build_readiness_report(
        generated,
        public_data_discovery_path=_local_discovery_report(generated),
        artifact_bundle_manifest_path=bundle_path,
    )

    check = readiness["checks"]["artifact_bundle_manifest"]
    assert check["status"] == "fail"
    assert "artifact sha256 changed: claim_boundary_audit" in check["issues"]
    assert "artifact_bundle_manifest" in readiness["summary"]["blocking_checks"]


def _minimal_release_generated(generated: Path) -> Path:
    generated.mkdir(parents=True, exist_ok=True)
    return generated


def _local_config_dir(tmp_path: Path, generated: Path) -> Path:
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    release_dir = generated / "release_packaging" / "gharchive_formal_project_benchmark"
    input_dir = generated / "evaluation_harness" / "gharchive_formal_submission_inputs_hardened"
    (config_dir / "memory_submission_event_profile_stub.yaml").write_text(
        f"""
baseline:
  name: memory_submission_event_profile_stub
  family: memory_system_contract
  entrypoint: ultra_long_benchmark.cli:run-memory-submission-baseline
  requires_llm_api: false
  requires_gpu: false
  memory_backend: event_profile_stub
data:
  project_dir: {release_dir}
  submission_input_dir: {input_dir}
  predictions_path: {generated / "evaluation_harness" / "gharchive_formal_memory_profile_stub_hardened_predictions.jsonl"}
  output_path: {generated / "evaluation_harness" / "gharchive_formal_memory_profile_stub_hardened_report.json"}
evaluation:
  mode: memory_submission_prediction_generation
  adapter: event_profile_stub
  top_k: 3
  metrics: [prediction_coverage, no_gold_input_contract]
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
    source_root = generated / "source_data"
    write_jsonl(
        source_root / "github_sample.jsonl",
        [
            {
                "text": "def add(a, b):\n    return a + b\n",
                "meta": {"source": "github"},
            }
        ],
    )
    discover_public_data_sources([source_root], output_path=path)
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
