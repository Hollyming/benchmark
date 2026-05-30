You are Codex working in `/home/jmzhang/Workspace/benchmark`.

Read `docs/codex_prompts/grounded_longuserpolicy_handoff.md` first. Then implement the next engineering step for LongUserPolicyBench.

Goal: extend the reference-grounded, LLM-assisted, verifier-driven pipeline for longitudinal user-policy and habit induction without breaking the deterministic smoke path.

Current context:
- The repo has a synthetic smoke pipeline and grounded pilots.
- Grounded pilots cover manual cross-tool workflow policies and a GitHub/CI policy fixture.
- Current CLI commands should continue to work:
  - `python -m ultra_long_benchmark.cli smoke --all`
  - `python -m ultra_long_benchmark.cli grounded-pilot`
  - `python -m ultra_long_benchmark.cli github-fixture-pilot`
  - `python -m ultra_long_benchmark.cli gharchive-pilot`
  - `python -m ultra_long_benchmark.cli gharchive-quality-report --input tests/fixtures/gharchive_multi_repo_sample.jsonl --output examples/generated/gharchive_quality_report.json`
  - `python -m ultra_long_benchmark.cli gharchive-window-report --input tests/fixtures/gharchive_window_sample.jsonl --window-days 7 --output examples/generated/gharchive_window_report.json`
  - `python -m ultra_long_benchmark.cli gharchive-mine-candidates --input examples/source_fixtures/gharchive_public_events/project_gharchive_001.jsonl --repo acme/docs --output examples/generated/gharchive_candidate_report.json`
  - `python -m ultra_long_benchmark.cli gharchive-annotation-pack --input examples/source_fixtures/gharchive_public_events/project_gharchive_001.jsonl --repo acme/docs --output-dir examples/generated/annotation_packs/gharchive_policy`
  - `python -m ultra_long_benchmark.cli gharchive-annotation-pack-batch --input tests/fixtures/gharchive_multi_repo_sample.jsonl --output-dir examples/generated/annotation_packs/gharchive_batch`
  - `python -m ultra_long_benchmark.cli export-annotation-pack-release examples/generated/annotation_packs/gharchive_batch --output-dir examples/generated/release_packaging/gharchive_annotation_pack`
  - `python -m ultra_long_benchmark.cli gharchive-scale-summary examples/generated/annotation_packs/gharchive_batch --release-dir examples/generated/release_packaging/gharchive_annotation_pack --output examples/generated/gharchive_scale_summary.json`
  - `python -m ultra_long_benchmark.cli validate-policy-rewrites examples/generated/annotation_packs/gharchive_policy/annotation_pack.json examples/annotation_rewrites/gharchive_rewrite_examples.jsonl --output examples/generated/annotation_packs/gharchive_policy/rewrite_validation.json`
  - `python -m ultra_long_benchmark.cli build-project-from-rewrites examples/generated/annotation_packs/gharchive_policy/annotation_pack.json examples/annotation_rewrites/gharchive_rewrite_examples.jsonl --output-dir examples/generated/projects --project-id project_gharchive_rewrite_001`
  - `python -m ultra_long_benchmark.cli gharchive-batch-pilot --input tests/fixtures/gharchive_multi_repo_sample.jsonl`
  - `python -m ultra_long_benchmark.cli evaluate-project examples/generated/projects/project_manual_001 --output examples/generated/evaluation_harness/project_manual_baselines.json --top-k 3`
  - `python -m ultra_long_benchmark.cli evaluate-project examples/generated/projects/project_gharchive_001 --output examples/generated/evaluation_harness/project_gharchive_baselines.json --top-k 3`
  - `python -m ultra_long_benchmark.cli score-action-traces examples/generated/projects/project_gharchive_001 examples/action_traces/gharchive_trace_examples.jsonl --output examples/generated/evaluation_harness/gharchive_action_trace_report.json`
  - `python -m ultra_long_benchmark.cli validate-baseline-config configs/baselines --output examples/generated/evaluation_harness/baseline_config_validation.json`
  - `python -m ultra_long_benchmark.cli run-baseline-config configs/baselines/raw_rag_project.yaml --output examples/generated/evaluation_harness/raw_rag_config_run.json`
  - `python -m ultra_long_benchmark.cli run-baseline-config configs/baselines/gharchive_action_trace_scoring.yaml --output examples/generated/evaluation_harness/action_trace_config_run.json`
  - `python -m ultra_long_benchmark.cli run-baseline-config-dir configs/baselines --output-dir examples/generated/evaluation_harness/baseline_batch`
  - `python -m ultra_long_benchmark.cli run-baseline-config configs/baselines/mem0_project_placeholder.yaml --dry-run --output examples/generated/evaluation_harness/mem0_dry_run.json`
  - `python -m ultra_long_benchmark.cli validate`
  - `python -m ultra_long_benchmark.cli audit --json --output examples/generated/audit_report.json`

Recommended next tasks:
1. Run GHArchive repo/window quality reports, candidate mining, and project baselines on locally downloaded public GHArchive data.
2. Replace the current Mem0/A-MEM dry-run placeholders with concrete runners once dependencies and provider/model credentials are available.
3. Add generated action-trace adapters for model outputs once a concrete baseline runner exists.
4. Add LLM-assisted grounded rewriting/probe generation from `gharchive-annotation-pack` outputs only after an API key/provider is available.
