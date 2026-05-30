# Reproducibility Checklist

## Determinism

- [ ] All synthetic stages accept an explicit seed.
- [ ] Split generation is deterministic and persona-disjoint.
- [ ] Generated artifact IDs are stable across reruns with the same config.

## Environment

- [ ] Python version recorded.
- [ ] Dependencies pinned for release experiments.
- [ ] `.env.example` documents optional provider keys without exposing secrets.

## Data Provenance

- [ ] Every source document has origin, URI when available, license, and content hash.
- [ ] Raw public data is staged outside committed generated examples.
- [ ] License compatibility is checked before release.
- [ ] Email corpora use reviewed manifests with redistribution and PII-redaction gates.

## Validation

- [ ] `python -m ultra_long_benchmark.cli smoke --all` passes.
- [ ] `python -m ultra_long_benchmark.cli validate` passes.
- [ ] `python -m ultra_long_benchmark.cli audit` passes.
- [ ] `python -m ultra_long_benchmark.cli validate-baseline-config configs/baselines` passes.
- [ ] `python -m ultra_long_benchmark.cli discover-public-data --root /home/jmzhang/Workspace/data --output examples/generated/public_data_discovery_report.json` records whether local staging contains usable GHArchive workflow events or approved email manifests.
- [ ] `python -m ultra_long_benchmark.cli audit-workflow-data-sources --discovery-report examples/generated/public_data_discovery_report.json --gharchive-stage-plan examples/generated/gharchive_stage_plan.json --output examples/generated/workflow_data_source_audit.json` records whether discovered workflow sources and stage-plan readiness justify LLM/API or human annotation.
- [ ] `python -m ultra_long_benchmark.cli audit-workflow-data-sources --discovery-report examples/generated/public_data_discovery_report.json --gharchive-stage-plan examples/generated/gharchive_stage_plan.json --output examples/generated/workflow_data_source_audit_paper_required.json --require-paper-ready` passes before paper-scale annotation budget is spent.
- [ ] `python -m ultra_long_benchmark.cli gharchive-build-slice <local-gharchive-dir-or-file> --output <slice.jsonl> --manifest <slice_manifest.json> --max-records-per-source-file <n>` records source files, selected records, eligible repos, and no-network/no-LLM constraints for real GHArchive runs.
- [ ] `INPUT=<local-gharchive.jsonl> bash scripts/prepare_gharchive_slice.sh` writes quality, window, candidate, and stage-plan reports for any real GHArchive slice used in a paper-scale run.
- [ ] `INPUT=<local-gharchive.jsonl> REQUIRE_READY_FOR_ANNOTATION=1 bash scripts/prepare_gharchive_slice.sh` passes before spending LLM/API or human rewrite budget on paper-scale annotation.
- [ ] `python -m ultra_long_benchmark.cli gharchive-annotation-pack --input examples/source_fixtures/gharchive_public_events/project_gharchive_001.jsonl --repo acme/docs` passes before any LLM-assisted rewrite.
- [ ] `python -m ultra_long_benchmark.cli gharchive-annotation-pack-batch --input tests/fixtures/gharchive_multi_repo_sample.jsonl` emits per-repo packs and a skipped-repo report.
- [ ] `python -m ultra_long_benchmark.cli export-annotation-pack-release examples/generated/annotation_packs/gharchive_batch` emits a repo-disjoint release manifest and split task files.
- [ ] `python -m ultra_long_benchmark.cli gharchive-scale-summary examples/generated/annotation_packs/gharchive_batch --release-dir examples/generated/release_packaging/gharchive_annotation_pack` emits scale stats for the annotation release.
- [ ] `python -m ultra_long_benchmark.cli export-policy-rewrite-prompts examples/generated/annotation_packs/gharchive_policy/annotation_pack.json --output examples/generated/annotation_packs/gharchive_policy/rewrite_prompts.jsonl` emits provider-agnostic prompt records without calling an LLM.
- [ ] `python -m ultra_long_benchmark.cli export-policy-rewrite-prompts-batch examples/generated/annotation_packs/gharchive_batch --output-dir examples/generated/annotation_packs/gharchive_prompt_exports` emits one prompt file per pack plus a batch report.
- [ ] `python -m ultra_long_benchmark.cli package-policy-rewrite-jobs examples/generated/annotation_packs/gharchive_prompt_exports --output-dir examples/generated/annotation_packs/rewrite_jobs --max-prompts-per-job 100` writes no-provider rewrite annotation job shards with empty proposal templates and token estimates.
- [ ] `python -m ultra_long_benchmark.cli collect-policy-rewrite-job-outputs examples/generated/annotation_packs/rewrite_jobs --output examples/generated/annotation_packs/rewrite_jobs/collected_rewrite_proposals.jsonl --report examples/generated/annotation_packs/rewrite_jobs/rewrite_job_collection_report.json` passes after LLM/API or human annotation has filled each job output.
- [ ] `python -m ultra_long_benchmark.cli validate-policy-rewrites-batch examples/generated/annotation_packs/gharchive_batch examples/generated/annotation_packs/rewrite_jobs/collected_rewrite_proposals.jsonl --output-dir examples/generated/annotation_packs/gharchive_rewrite_validation_batch` validates every LLM/human proposal pack before release.
- [ ] `python -m ultra_long_benchmark.cli build-projects-from-rewrite-batch examples/generated/annotation_packs/gharchive_rewrite_validation_batch/batch_rewrite_validation_report.json --output-dir examples/generated/projects --project-prefix project_gharchive_rewrite_batch` converts passed rewrite batches into verifier-checked projects.
- [ ] `python -m ultra_long_benchmark.cli export-project-benchmark-release examples/generated/projects/project_gharchive_rewrite_batch_* --output-dir examples/generated/release_packaging/project_benchmark` emits project-level manifests, project-disjoint splits, probe JSONL files, and project file hashes.
- [ ] `python -m ultra_long_benchmark.cli verify-project-benchmark-release examples/generated/release_packaging/project_benchmark --output examples/generated/project_release_integrity_report.json` verifies project-release hashes and split/probe consistency.
- [ ] `python -m ultra_long_benchmark.cli verify-release-integrity examples/generated/release_packaging/gharchive_annotation_pack --prompt-export-dir examples/generated/annotation_packs/gharchive_prompt_exports` verifies pack hashes, repo-disjoint splits, task counts, prompt coverage, and no-LLM constraints.
- [ ] `python -m ultra_long_benchmark.cli assess-paper-scale examples/generated/release_packaging/gharchive_annotation_pack --profile paper --scale-summary examples/generated/gharchive_scale_summary.json --window-report examples/generated/gharchive_window_report.json --release-integrity-report examples/generated/release_integrity_report.json --output examples/generated/paper_scale_assessment.json --allow-fail` writes an explicit paper-scale readiness report.
- [ ] `python -m ultra_long_benchmark.cli validate-policy-rewrites examples/generated/annotation_packs/gharchive_policy/annotation_pack.json examples/annotation_rewrites/gharchive_rewrite_examples.jsonl` passes for any released rewrite/probe proposal batch.
- [ ] `python -m ultra_long_benchmark.cli build-project-from-rewrites examples/generated/annotation_packs/gharchive_policy/annotation_pack.json examples/annotation_rewrites/gharchive_rewrite_examples.jsonl` emits a verifier-checked project.
- [ ] `python -m ultra_long_benchmark.cli run-baseline-config configs/baselines/no_memory_project.yaml` passes after the GHArchive pilot project exists.
- [ ] `python -m ultra_long_benchmark.cli run-baseline-config configs/baselines/full_event_log_project.yaml` passes after the GHArchive pilot project exists.
- [ ] `python -m ultra_long_benchmark.cli run-baseline-config configs/baselines/raw_rag_project.yaml` passes after the GHArchive pilot project exists.
- [ ] `python -m ultra_long_benchmark.cli run-baseline-config configs/baselines/temporal_raw_rag_project.yaml` passes after the GHArchive pilot project exists.
- [ ] `python -m ultra_long_benchmark.cli run-baseline-config configs/baselines/gharchive_action_trace_scoring.yaml` passes after the GHArchive pilot project exists.
- [ ] `python -m ultra_long_benchmark.cli score-project-predictions examples/generated/projects/project_gharchive_001 examples/project_predictions/gharchive_prediction_examples.jsonl` passes for external prediction submissions.
- [ ] `python -m ultra_long_benchmark.cli export-project-submission-inputs examples/generated/release_packaging/project_benchmark --output-dir examples/generated/evaluation_harness/project_submission_inputs` writes no-gold release inputs for external systems.
- [ ] `python -m ultra_long_benchmark.cli verify-project-submission-inputs examples/generated/evaluation_harness/project_submission_inputs --output examples/generated/evaluation_harness/project_submission_input_report.json` verifies the no-gold input package.
- [ ] `python -m ultra_long_benchmark.cli run-submission-input-baseline examples/generated/evaluation_harness/project_submission_inputs --baseline raw_event_rag_input --top-k 5 --predictions examples/generated/evaluation_harness/submission_input_raw_event_rag_predictions.jsonl --report examples/generated/evaluation_harness/submission_input_raw_event_rag_report.json` emits prediction JSONL from no-gold inputs.
- [ ] `python -m ultra_long_benchmark.cli validate-project-prediction-submission examples/generated/release_packaging/project_benchmark examples/generated/evaluation_harness/submission_input_raw_event_rag_predictions.jsonl --output examples/generated/evaluation_harness/submission_input_raw_event_rag_submission_validation.json` checks external submission schema and release-probe coverage before scoring.
- [ ] `python -m ultra_long_benchmark.cli score-project-release-predictions examples/generated/release_packaging/project_benchmark examples/generated/evaluation_harness/submission_input_raw_event_rag_predictions.jsonl --output examples/generated/evaluation_harness/submission_input_raw_event_rag_score.json --system-name submission_input_raw_event_rag` scores the no-gold baseline submission.
- [ ] `python -m ultra_long_benchmark.cli validate-project-prediction-submission examples/generated/release_packaging/project_benchmark examples/project_predictions/project_release_prediction_examples.jsonl --output examples/generated/evaluation_harness/project_release_prediction_submission_validation.json` passes for the checked-in external release submission.
- [ ] `python -m ultra_long_benchmark.cli score-project-release-predictions examples/generated/release_packaging/project_benchmark examples/project_predictions/project_release_prediction_examples.jsonl --output examples/generated/evaluation_harness/project_release_prediction_report.json --system-name example_release_submission` passes for release-level external submissions.
- [ ] `python -m ultra_long_benchmark.cli score-project-release-prediction-dir examples/generated/release_packaging/project_benchmark examples/project_predictions/release_submissions --output-dir examples/generated/evaluation_harness/prediction_scoring_batch --system-name-prefix external` scores one JSONL per external system and writes a batch manifest.
- [ ] `python -m ultra_long_benchmark.cli evaluate-project-release examples/generated/release_packaging/project_benchmark --output examples/generated/evaluation_harness/project_release_baselines.json --top-k 3` writes release-level deterministic baseline metrics.
- [ ] `python -m ultra_long_benchmark.cli export-paper-tables --release-baseline-report examples/generated/evaluation_harness/project_release_baselines.json --prediction-report examples/generated/evaluation_harness/project_release_prediction_report.json --prediction-report examples/generated/evaluation_harness/submission_input_raw_event_rag_score.json --prediction-batch-report examples/generated/evaluation_harness/prediction_scoring_batch/prediction_scoring_batch_report.json --bootstrap-samples 1000 --bootstrap-seed 0 --output-dir examples/generated/evaluation_harness/paper_tables` writes main, task, capability, failure-breakdown, and project-bootstrap confidence interval result tables.
- [ ] `python -m ultra_long_benchmark.cli run-baseline-config configs/baselines/gharchive_prediction_submission_example.yaml` passes after the GHArchive pilot project exists.
- [ ] `python -m ultra_long_benchmark.cli run-baseline-config-dir configs/baselines` executes deterministic baselines and dry-runs gated external baselines.
- [ ] `python -m ultra_long_benchmark.cli readiness-report --output examples/generated/readiness_report.json` passes as the final fixture/pilot release-readiness gate and records workflow-source audit warnings when real data is not staged.
- [ ] `python -m ultra_long_benchmark.cli readiness-report --output examples/generated/readiness_report_paper_required.json --require-paper-scale` passes only for paper-scale releases with paper-ready workflow sources and GHArchive stage decision.
- [ ] Mem0/A-MEM configs are dry-run validated unless their runner, dependency lockfile, and credentials are explicitly available.
- [ ] `python -m pytest -q` passes.

## Documentation

- [ ] Benchmark protocol is versioned.
- [ ] Dataset card describes intended use and non-use.
- [ ] Risk notes cover privacy, synthetic bias, and contamination.
- [ ] Evaluation protocol includes metrics, baselines, and confidence intervals.

## Release

- [ ] Dataset card and benchmark card generated.
- [ ] Release manifest includes counts and file hashes.
- [ ] Train/dev/test split files are present.
- [ ] Release integrity has zero blocking issues; fixture-scale empty-split warnings are resolved before paper-scale claims.
- [ ] Paper-scale assessment passes with `--profile paper` before reporting main-experiment results.
- [ ] Human annotation rubric is included.
