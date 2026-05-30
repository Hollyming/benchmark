# annotation_and_quality_control

Runs automatic quality checks and emits a human annotation template with IAA hooks.

Offline demo:

```powershell
python -m ultra_long_benchmark.cli smoke --all
```

Task-only command after upstream artifacts exist:

```powershell
python tasks/annotation_and_quality_control/scripts/run_demo.py
```

Checks include unique IDs, evidence references, typed schema parsing, and the presence of privacy-sensitive refusal examples.

GHArchive policy annotation bridge:

```bash
python -m ultra_long_benchmark.cli gharchive-mine-candidates --input examples/source_fixtures/gharchive_public_events/project_gharchive_001.jsonl --repo acme/docs --output examples/generated/gharchive_candidate_report.json
python -m ultra_long_benchmark.cli gharchive-annotation-pack --input examples/source_fixtures/gharchive_public_events/project_gharchive_001.jsonl --repo acme/docs --output-dir examples/generated/annotation_packs/gharchive_policy
python -m ultra_long_benchmark.cli gharchive-annotation-pack-batch --input tests/fixtures/gharchive_multi_repo_sample.jsonl --output-dir examples/generated/annotation_packs/gharchive_batch
python -m ultra_long_benchmark.cli export-annotation-pack-release examples/generated/annotation_packs/gharchive_batch --output-dir examples/generated/release_packaging/gharchive_annotation_pack
python -m ultra_long_benchmark.cli gharchive-scale-summary examples/generated/annotation_packs/gharchive_batch --release-dir examples/generated/release_packaging/gharchive_annotation_pack --output examples/generated/gharchive_scale_summary.json
python -m ultra_long_benchmark.cli export-policy-rewrite-prompts examples/generated/annotation_packs/gharchive_policy/annotation_pack.json --output examples/generated/annotation_packs/gharchive_policy/rewrite_prompts.jsonl
python -m ultra_long_benchmark.cli export-policy-rewrite-prompts-batch examples/generated/annotation_packs/gharchive_batch --output-dir examples/generated/annotation_packs/gharchive_prompt_exports
python -m ultra_long_benchmark.cli package-policy-rewrite-jobs examples/generated/annotation_packs/gharchive_prompt_exports --output-dir examples/generated/annotation_packs/rewrite_jobs --max-prompts-per-job 100
python -m ultra_long_benchmark.cli collect-policy-rewrite-job-outputs examples/generated/annotation_packs/rewrite_jobs --output examples/generated/annotation_packs/rewrite_jobs/collected_rewrite_proposals.jsonl --report examples/generated/annotation_packs/rewrite_jobs/rewrite_job_collection_report.json
python -m ultra_long_benchmark.cli validate-policy-rewrites-batch examples/generated/annotation_packs/gharchive_batch examples/generated/annotation_packs/rewrite_jobs/collected_rewrite_proposals.jsonl --output-dir examples/generated/annotation_packs/gharchive_rewrite_validation_batch
python -m ultra_long_benchmark.cli build-projects-from-rewrite-batch examples/generated/annotation_packs/gharchive_rewrite_validation_batch/batch_rewrite_validation_report.json --output-dir examples/generated/projects --project-prefix project_gharchive_rewrite_batch
python -m ultra_long_benchmark.cli verify-release-integrity examples/generated/release_packaging/gharchive_annotation_pack --prompt-export-dir examples/generated/annotation_packs/gharchive_prompt_exports --output examples/generated/release_integrity_report.json
python -m ultra_long_benchmark.cli assess-paper-scale examples/generated/release_packaging/gharchive_annotation_pack --profile paper --scale-summary examples/generated/gharchive_scale_summary.json --window-report examples/generated/gharchive_window_report.json --release-integrity-report examples/generated/release_integrity_report.json --output examples/generated/paper_scale_assessment.json --allow-fail
python -m ultra_long_benchmark.cli validate-policy-rewrites examples/generated/annotation_packs/gharchive_policy/annotation_pack.json examples/annotation_rewrites/gharchive_rewrite_examples.jsonl --output examples/generated/annotation_packs/gharchive_policy/rewrite_validation.json
python -m ultra_long_benchmark.cli build-project-from-rewrites examples/generated/annotation_packs/gharchive_policy/annotation_pack.json examples/annotation_rewrites/gharchive_rewrite_examples.jsonl --output-dir examples/generated/projects --project-id project_gharchive_rewrite_001
```

This path is offline and deterministic. It packages mined policy candidates with supporting snippets, negative evidence, action-boundary candidates, LLM instructions, and verifier expectations before any LLM or human rewrite. `export-policy-rewrite-prompts` emits provider-agnostic prompt records but does not call an LLM. `package-policy-rewrite-jobs` creates no-provider annotation handoff shards. `collect-policy-rewrite-job-outputs` is the return gate after API/human annotation: it combines completed job outputs and rejects missing, empty, duplicate, schema-invalid, or unfilled template rows before `validate-policy-rewrites-batch`. `build-projects-from-rewrite-batch` converts only passed batches into verifier-checked project artifacts. `verify-release-integrity` checks pack hashes, repo-disjoint splits, task counts, and prompt coverage. `assess-paper-scale` separates engineering fixtures from paper-scale releases by checking repo/task volume, split balance, candidate-type diversity, and time-window coverage.

For a larger local GHArchive slice, run the stitched pipeline:

```bash
INPUT=/path/to/gharchive.jsonl OUTPUT_ROOT=examples/generated bash scripts/run_gharchive_annotation_pipeline.sh
INPUT=/path/to/gharchive.jsonl OUTPUT_ROOT=examples/generated REWRITE_PROPOSALS=/path/to/rewrite_proposals.jsonl bash scripts/run_gharchive_annotation_pipeline.sh
```
