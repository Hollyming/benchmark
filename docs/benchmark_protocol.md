# Benchmark Protocol

This repository defines an offline-runnable construction and evaluation protocol for **Longitudinal User Policy / Habit Induction** benchmarks. The committed examples are intentionally small, deterministic, and synthetic; they exercise the complete protocol without requiring API keys, downloads, or network access.

## Unit of Evaluation

The benchmark unit is a future tool-policy probe grounded in one longitudinal user trajectory. A valid probe must identify:

- `trajectory_id` and `persona_id` for the user history being evaluated.
- `capability` from the policy/habit taxonomy.
- `prompt` shown to the evaluated system.
- `answer` or structured expected behavior when applicable.
- `evidence_event_ids` linking the correct action to positive timeline events.
- Optional `negative_evidence_event_ids`, `obsolete_evidence_event_ids`, and `distractor_event_ids` for overgeneralization diagnostics.
- `memory_task`, the paper-facing task family, such as policy update handling or tool-action alignment.
- `expected_behavior`, including answer, refusal/redaction, or clarification behavior.
- `rubric` with capability-specific scoring requirements.

Systems should be evaluated against the complete trajectory context or against a documented memory interface over the same trajectory. Reports must state which memory interface was used, whether retrieval was learned or fixed, and whether source metadata was hidden from the model.

## Capability Taxonomy

| Capability | Required behavior | Common failure modes |
| --- | --- | --- |
| `user_policy_induction` | Infer an implicit work policy from historical user/tool behavior. | Treats a policy as a fact, misses approval boundary. |
| `habit_generalization` | Generalize stable recurring habits across days or weeks. | Overfits a single event, ignores recurring pattern. |
| `contextual_policy_selection` | Select the policy matching task context and scope. | Applies the wrong domain policy or ignores preconditions. |
| `tool_action_alignment` | Take allowed tool actions and avoid forbidden ones. | Completes task while sending/merging/paying without authorization. |
| `workflow_boundary_respect` | Preserve review, approval, channel, and role boundaries. | Skips review, shares too early, uses wrong channel. |
| `policy_update_exception_handling` | Apply updates and narrow exceptions without overgeneralizing. | Uses stale policy or expands exception globally. |
| `proactive_routine_recognition` | Recover ordered routines and next expected steps. | Reorders workflow, omits human review, acts prematurely. |
| `privacy_authorization_boundary` | Use sensitive data only in authorized tools or contexts. | Leaks private data or refuses allowed secure-form use. |
| `habit_storage_gating` | Store durable habits and suppress one-off examples. | Learns transient style as normal policy. |
| `abstention_clarification` | Ask for clarification when authorization is absent. | Hallucinates permission or over-refuses authorized work. |

Every release should include per-capability counts, per-capability metrics, and examples of both passing and failing model outputs.

## Construction Protocol

1. Literature and taxonomy: record paper seeds and map each task to policy/habit capabilities.
2. Seed corpora ingestion: normalize source artifacts with provenance, license, and content hash fields.
3. User timeline simulation or ingestion: create temporally ordered workflow events with privacy tags and provenance.
4. Multi-session trajectory generation: convert events into dated user/assistant/tool/environment/collaborator sessions while preserving linked event IDs; include cross-tool workflows, distractors, topic switches, updates, negative examples, privacy boundaries, and authorization gaps.
5. Future tool-policy probe generation: create prompts, expected behavior, answers, positive/negative/obsolete/distractor evidence links, memory-task labels, and rubrics across all capability labels.
6. Annotation and quality control: run automatic checks and prepare human annotation templates.
7. Evaluation harness: score outputs by policy behavior, boundary violations, evidence use, and capability-specific rubric items.
8. Release packaging: emit cards, splits, provenance manifest, and audit reports.

The offline smoke path must remain deterministic. Optional public-data or LLM-assisted variants must be treated as separate releases with their own provenance and QC reports.

## Data Quality Rubric

| Dimension | Minimum bar | Evidence to report |
| --- | --- | --- |
| Schema validity | All JSONL rows validate against package models and JSON Schemas. | Audit report plus validation command output. |
| Provenance completeness | Each document and event has source ID, origin, license, and hash when available. | Provenance manifest and missing-field counts. |
| Temporal integrity | Events and sessions are timestamped, ordered, and timezone-explicit. | QC checks for ordering and malformed timestamps. |
| Policy evidence linkage | Each probe cites sufficient positive evidence and relevant negative/obsolete/distractor evidence. | Query-to-event coverage table plus invalid-evidence counts. |
| Capability coverage | All claimed capabilities appear in train/dev/test or are explicitly excluded. | Per-capability count table. |
| Action boundary clarity | Expected behavior states allowed, forbidden, or clarification-required actions and reflects positive evidence action boundaries. | Must-include/must-not-include checks plus verifier `action_boundaries_present` and `action_boundaries_aligned`. |
| Privacy handling | Sensitive facts are tagged and paired with channel/tool-specific boundary probes. | Privacy tag counts and leak-rate evaluation. |
| Contamination control | Splits avoid duplicate trajectories, near-duplicate prompts, and source leakage. | Split manifest and deduplication notes. |
| Annotation reliability | Human labels include instructions, adjudication rules, and agreement statistics. | Annotation template, IAA metrics, adjudication log. |
| Baseline sanity | At least one deterministic baseline and one stronger system are reported when publishing claims. | Metrics table with confidence intervals or bootstrap notes. |

## Evaluation Protocol

A model evaluation report should include:

- Dataset version, split name, commit or release manifest hash, and audit status.
- Prompting format, memory retrieval policy, context budget, decoding parameters, and system instructions.
- Aggregate score and per-capability scores.
- Boundary violation rate for high-risk actions such as send, merge, pay, reveal, delete, or share.
- Separate reporting for answerable, refusal/redaction, and clarification queries.
- Evidence sufficiency score when the model is asked to cite memories.
- Error analysis over stale policy, overbroad exception, transient-as-habit, wrong tool action, privacy leak, unsupported authorization, and over-refusal.

Recommended primary metrics:

- `policy_action_accuracy`: final action matches the user's induced policy.
- `boundary_violation_rate`: unauthorized send/merge/pay/reveal/delete/share actions.
- `exception_scope_accuracy`: narrow exceptions are neither missed nor globalized.
- `negative_example_suppression`: one-off examples are not stored or applied as durable habits.
- `clarification_accuracy`: missing authorization leads to a question rather than action.
- `evidence_recall`: required evidence event IDs are cited or retrieved.
- `boundary_action_recall`: allowed, forbidden, approval, clarification, and tool boundary entries recovered from positive evidence.
- `trace_boundary_violation_rate`: fraction of submitted action traces that violate forbidden actions/tools, approval requirements, clarification requirements, or authorized-tool constraints.
- `memory_task_accuracy`: accuracy grouped by paper-facing task family.
- `trajectory_stressor_coverage`: per-split counts for cross-tool workflows, distractors, policy updates, negative examples, privacy boundaries, and authorization gaps.

## Reproducibility Checklist

Before submitting results or releasing a dataset version:

- Run `python -m ultra_long_benchmark.cli smoke --all`.
- Run `python -m ultra_long_benchmark.cli validate`.
- Run `python -m ultra_long_benchmark.cli audit --json --output examples/generated/audit_report.json`.
- Run `python -m ultra_long_benchmark.cli grounded-pilot`.
- Run `python -m ultra_long_benchmark.cli github-fixture-pilot`.
- Run `python -m ultra_long_benchmark.cli gharchive-pilot`.
- Run `python -m ultra_long_benchmark.cli gharchive-quality-report --input tests/fixtures/gharchive_multi_repo_sample.jsonl --output examples/generated/gharchive_quality_report.json`.
- Run `python -m ultra_long_benchmark.cli gharchive-window-report --input tests/fixtures/gharchive_window_sample.jsonl --window-days 7 --output examples/generated/gharchive_window_report.json`.
- Run `python -m ultra_long_benchmark.cli gharchive-mine-candidates --input examples/source_fixtures/gharchive_public_events/project_gharchive_001.jsonl --repo acme/docs --output examples/generated/gharchive_candidate_report.json`.
- Run `python -m ultra_long_benchmark.cli gharchive-annotation-pack --input examples/source_fixtures/gharchive_public_events/project_gharchive_001.jsonl --repo acme/docs --output-dir examples/generated/annotation_packs/gharchive_policy`.
- Run `python -m ultra_long_benchmark.cli gharchive-annotation-pack-batch --input tests/fixtures/gharchive_multi_repo_sample.jsonl --output-dir examples/generated/annotation_packs/gharchive_batch`.
- Run `python -m ultra_long_benchmark.cli export-annotation-pack-release examples/generated/annotation_packs/gharchive_batch --output-dir examples/generated/release_packaging/gharchive_annotation_pack`.
- Run `python -m ultra_long_benchmark.cli gharchive-scale-summary examples/generated/annotation_packs/gharchive_batch --release-dir examples/generated/release_packaging/gharchive_annotation_pack --output examples/generated/gharchive_scale_summary.json`.
- Run `python -m ultra_long_benchmark.cli validate-policy-rewrites examples/generated/annotation_packs/gharchive_policy/annotation_pack.json examples/annotation_rewrites/gharchive_rewrite_examples.jsonl --output examples/generated/annotation_packs/gharchive_policy/rewrite_validation.json`.
- Run `python -m ultra_long_benchmark.cli build-project-from-rewrites examples/generated/annotation_packs/gharchive_policy/annotation_pack.json examples/annotation_rewrites/gharchive_rewrite_examples.jsonl --output-dir examples/generated/projects --project-id project_gharchive_rewrite_001`.
- Run `python -m ultra_long_benchmark.cli gharchive-batch-pilot --input tests/fixtures/gharchive_multi_repo_sample.jsonl`.
- Run `python -m ultra_long_benchmark.cli evaluate-project examples/generated/projects/project_manual_001 --output examples/generated/evaluation_harness/project_manual_baselines.json --top-k 3`.
- Run `python -m ultra_long_benchmark.cli evaluate-project examples/generated/projects/project_gharchive_001 --output examples/generated/evaluation_harness/project_gharchive_baselines.json --top-k 3`.
- Optionally run selected project baselines with repeated `--baseline`, for example `--baseline temporal_raw_rag`.
- Run `python -m ultra_long_benchmark.cli score-action-traces examples/generated/projects/project_gharchive_001 examples/action_traces/gharchive_trace_examples.jsonl --output examples/generated/evaluation_harness/gharchive_action_trace_report.json`.
- Run `python -m ultra_long_benchmark.cli validate-baseline-config configs/baselines --output examples/generated/evaluation_harness/baseline_config_validation.json`.
- Run `python -m ultra_long_benchmark.cli run-baseline-config configs/baselines/no_memory_project.yaml --output examples/generated/evaluation_harness/no_memory_config_run.json`.
- Run `python -m ultra_long_benchmark.cli run-baseline-config configs/baselines/raw_rag_project.yaml --output examples/generated/evaluation_harness/raw_rag_config_run.json`.
- Run `python -m ultra_long_benchmark.cli run-baseline-config configs/baselines/temporal_raw_rag_project.yaml --output examples/generated/evaluation_harness/temporal_raw_rag_config_run.json`.
- Run `python -m ultra_long_benchmark.cli run-baseline-config configs/baselines/gharchive_action_trace_scoring.yaml --output examples/generated/evaluation_harness/action_trace_config_run.json`.
- Run `python -m ultra_long_benchmark.cli run-baseline-config-dir configs/baselines --output-dir examples/generated/evaluation_harness/baseline_batch`.
- Dry-run gated external baselines with `python -m ultra_long_benchmark.cli run-baseline-config configs/baselines/mem0_project_placeholder.yaml --dry-run --output examples/generated/evaluation_harness/mem0_dry_run.json` and the analogous A-MEM config.
- Run `pytest` when the test dependency is installed.
- Record package version, Python version, operating system, and dependency versions.
- Publish configs, generation seeds, split manifests, dataset card, benchmark card, QC report, and audit report.
- Confirm no API keys, raw restricted corpora, or unreviewed personal data are committed.
- Document any optional network, LLM, or public-data steps separately from the offline smoke path.
