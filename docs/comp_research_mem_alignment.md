# LongUserPolicyBench Alignment Summary

This repository has shifted from a research-collaborator memory scaffold to **Longitudinal User Policy / Habit Induction for Tool-Using Agents**.

## Core Research Claim

Next-generation agent-memory benchmarks should move beyond long-context QA and fact recall. A useful personal or workplace agent must learn **how this user works** from longitudinal, cross-tool traces and apply that learned policy in future actions.

```text
Memory as User Policy = Habit Induction + Contextual Exceptions + Tool Boundaries + Authorization Scope + Negative Examples + Future Action Alignment
```

## SOTA Gap Summary

The paper-facing motivation should be anchored in concrete method boundaries:

- Mem0 demonstrates efficient long-term extraction, consolidation, retrieval, and graph memory, but its headline evaluation is still long-conversation QA; LongUserPolicyBench adds approval, clarification, negative-example storage, and future tool-action constraints.
- A-MEM dynamically organizes agent memories through Zettelkasten-style note/link/evolution, but links and tags do not prove that a memory encodes `allowed`, `forbidden`, `requires_approval`, or narrow exception scope.
- MemGPT/Letta manages virtual context over long histories; our task asks whether the retrieved context actually constrains irreversible or externally visible tool actions.
- Zep/Graphiti is a strong temporal-KG baseline for dynamic enterprise memory; our benchmark adds deontic labels that ordinary entity-relation graphs do not necessarily represent.
- MemoryArena and LongMemEval-V2 move memory evaluation toward agentic experience and workflow knowledge; our difference is user-specific policy induction from longitudinal work traces, scored through future action boundaries rather than compact evidence QA.
- AppWorld, WorkArena, and tau-bench are useful executable substrates, but their policies are mostly explicit or task-local. LongUserPolicyBench makes policy latent in the user history.

See `docs/sota_failure_diagnostic_matrix.md` for the concrete failure labels used when analyzing baselines, including `retrieved_but_not_applied`, `overbroad_exception`, `stale_policy_reuse`, `negative_example_stored`, and `approval_gate_bypassed`.

## Implemented Smoke Hooks

The deterministic smoke generator now includes compact examples of:

- External email draft-vs-send approval boundaries.
- Calendar deep-work habits.
- Ordered document review routines.
- Customer-visible issue filing preconditions.
- Narrow policy exceptions for a specific partner.
- One-off negative examples that must not become durable habits.
- PR review and CI-before-merge boundaries.
- Private-data channel/tool authorization boundaries.
- Missing authorization gaps that require clarification.
- Browser/file artifact naming habits.

## Paper-Facing Task Families

Generated probes include:

- `implicit_policy_induction`
- `cross_day_habit_generalization`
- `routine_step_ordering`
- `contextual_workflow_policy_selection`
- `policy_update_and_exception_handling`
- `negative_example_storage_gating`
- `tool_action_policy_alignment`
- `privacy_authorization_boundary`
- `authorization_gap_clarification`
- `artifact_management_habit_transfer`
- `cross_tool_boundary_composition`

Each query can include positive evidence plus optional negative, obsolete, and distractor evidence so policy induction and final action alignment can be analyzed separately.

## Grounded Pilot Flow

`examples/manual_grounded_seed/project_manual_001.json` now contains reference-grounded workflow artifacts across email, calendar, docs, issues, chat updates, negative examples, and privacy notes.

`examples/source_fixtures/github_issue_ci/project_github_001.json` exercises a GitHub/CI policy fixture: docs PR review routing, CI-before-merge boundary, and human emergency pre-CI merge as a negative example.

`GHArchiveEventAdapter` in `ultra_long_benchmark/pipelines/source_adapters.py` is the first real-public-data ingestion hook. It reads locally downloaded GHArchive `.jsonl`, `.json`, or `.json.gz` slices without network access, optionally filters by repo or actor, and normalizes public PR/review/issue/CI/workflow events into the same `SourceArtifact` and `CanonicalEvent` contract. This is the preferred next source for paper-scale reference-grounded developer-workflow data because it is public, longitudinal, and directly tied to future tool actions such as review, comment, CI waiting, and merge boundaries.

`python -m ultra_long_benchmark.cli gharchive-pilot` now turns a local GHArchive-style public event slice into a verifier-checked project under `examples/generated/projects/project_gharchive_001`. The default fixture in `examples/source_fixtures/gharchive_public_events/project_gharchive_001.jsonl` covers PR opening, summary comment, Nina review, CI in-progress/success, merge-after-CI, and a human emergency pre-CI merge that must remain negative evidence rather than an agent habit.

`python -m ultra_long_benchmark.cli gharchive-batch-pilot --input <local-gharchive.jsonl>` discovers repositories in a local event slice and emits one verifier-checked project per repo when the slice contains enough PR/review, execution-boundary, and negative-boundary evidence. CI/status/workflow events remain the strongest execution-boundary subtype, while PR closed/merged/revert/blocked signals are accepted when public GHArchive slices do not expose aligned CI events. Emergency pre-CI events remain a strong negative subtype, but real GHArchive mining also accepts do-not-merge, blocked, failed-CI, revert, hold, and approval-boundary language. This is the current bridge from checked-in fixtures to paper-scale GHArchive data.

`python -m ultra_long_benchmark.cli gharchive-quality-report --input <local-gharchive.jsonl>` scores local GHArchive slices before project generation. It reports per-repo PR/review/CI/execution-boundary/merge/negative-boundary counts, first/last timestamps, eligibility, and missing required signals. Batch generation now uses this quality gate and fails loudly when no repo is eligible.

`python -m ultra_long_benchmark.cli gharchive-window-report --input <local-gharchive.jsonl> --window-days 7` scores the same public event slice by repository-local time windows. This separates genuinely longitudinal evidence from one-day event bursts by reporting per-window PR/review/execution-boundary/negative-boundary coverage, eligible windows, and repos spanning multiple windows.

`python -m ultra_long_benchmark.cli gharchive-mine-candidates --input <local-gharchive.jsonl>` emits deterministic, source-grounded policy candidates before any LLM rewriting. Current candidates cover summary-comment review routing, CI-before-merge boundaries, issue label/assignee triage routing, and emergency/pre-CI negative examples, each with supporting event ids, negative evidence where relevant, action-boundary metadata, confidence, and the mining rule used.

`python -m ultra_long_benchmark.cli gharchive-annotation-pack --input <local-gharchive.jsonl>` packages those mined candidates into offline annotation tasks. Each task carries evidence snippets, raw pointers, content hashes, action-boundary candidates, LLM instructions, human-review checklist items, and verifier expectations. This is the intended bridge to LLM-assisted rewriting/probe generation without allowing the LLM to become the source of gold policy facts.

`python -m ultra_long_benchmark.cli gharchive-annotation-pack-batch --input <local-gharchive.jsonl>` applies the same quality gate across all eligible repositories and writes one annotation pack per repo plus a batch report. This is the current scale-up path from fixture-level GHArchive pilots to paper-scale public event slices.

`python -m ultra_long_benchmark.cli export-annotation-pack-release <batch_dir>` exports per-repo packs into a repo-disjoint release skeleton with manifest, split files, pack hashes, skipped repo metadata, and explicit constraints that LLM generation is not part of the gold source.

`python -m ultra_long_benchmark.cli gharchive-scale-summary <batch_dir> --release-dir <release_dir>` summarizes scale readiness across quality, annotation packs, candidate types, split counts, and release constraints. `scripts/run_gharchive_annotation_pipeline.sh` and `scripts/slurm/run_gharchive_annotation_pipeline.sbatch` stitch the GHArchive quality reports, batch packs, release export, and scale summary into one reproducible local or cluster run.

`python -m ultra_long_benchmark.cli export-policy-rewrite-prompts <annotation_pack.json>` exports provider-agnostic prompt records for LLM-assisted rewriting without making an API call. Each prompt carries source snippets, allowed event IDs, output schema, action-boundary constraints, and the validator command that must run after generation.

`python -m ultra_long_benchmark.cli export-policy-rewrite-prompts-batch <batch_dir>` applies the same prompt export to every per-repo annotation pack and writes a batch report. This is the scale path for preparing LLM-assisted annotation inputs after public-data mining while keeping generation separate from gold construction.

`python -m ultra_long_benchmark.cli validate-policy-rewrites-batch <batch_dir> <rewrite-proposals.jsonl-or-dir>` validates multi-pack LLM/human rewrite outputs. It supports one unified proposal JSONL or a directory of per-pack proposal files, writes per-pack reports, and produces a batch coverage summary before any project or release artifact consumes those rewrites.

`python -m ultra_long_benchmark.cli build-projects-from-rewrite-batch <batch_rewrite_validation_report.json>` converts only passed multi-pack rewrite batches into verifier-checked projects. It writes per-project validation artifacts, runs the normal project verifier, and emits `batch_rewrite_project_report.json`. This is the concrete implementation of the benchmark's construction rule: public workflow traces supply the policy evidence, LLMs may rewrite or draft probes, and verifier checks decide whether derived tasks enter the project-level benchmark.

`python -m ultra_long_benchmark.cli export-project-benchmark-release <project_dir...>` turns verifier-checked projects into the evaluation release consumed by external methods. It writes a project manifest, project-disjoint splits, probe JSONL files, and per-project file hashes without copying raw data by default. `verify-project-benchmark-release` recomputes hashes and checks split/probe consistency, so project-level tasks are release-verifiable rather than just local generated folders.

`python -m ultra_long_benchmark.cli validate-policy-rewrites <annotation_pack.json> <proposals.jsonl>` validates LLM/human rewrite outputs against that pack. It rejects invented event IDs, widened action boundaries, missing negative evidence, and weak expected behavior before a rewrite can become a benchmark probe.

`python -m ultra_long_benchmark.cli build-project-from-rewrites <annotation_pack.json> <proposals.jsonl>` converts validated rewrites into project-level `MemoryGraph` and `Probe` artifacts, then relies on the standard project verifier for grounding, task contracts, negative/distractor evidence, and action-boundary alignment.

`EmailWorkflowAdapter` provides the controlled entry point for future Enron/Avocado-style email trajectories. It is manifest-first and refuses to load records unless the manifest declares a known license, `redistribution.allowed=true`, `privacy_review.status=passed`, and `privacy_review.pii_redaction=true`. This keeps email workflow reuse grounded without silently admitting restricted or unreviewed personal data.

`python -m ultra_long_benchmark.cli evaluate-project <project_dir>` now runs deterministic project-level baselines. `no_memory` is a lower-bound clarification baseline, `full_event_log` exposes the whole chronological event stream without induced policy memory, `raw_rag` retrieves top-k canonical events lexically, `temporal_raw_rag` adds recency/update bonuses, and `oracle_policy_graph` uses gold memories/action boundaries/source evidence as an upper-bound sanity check. Reports include must-include recall, must-not violation rate, evidence recall, and boundary-action recall.

`python -m ultra_long_benchmark.cli score-action-traces <project_dir> <traces.jsonl>` scores concrete tool-call traces against the same action boundaries. It reports pass rate, boundary violation rate, allowed-action coverage, missing approval/clarification, forbidden action/tool violations, and unauthorized tool use. The checked-in GHArchive trace example includes one compliant docs-PR workflow and one pre-CI merge violation.

`python -m ultra_long_benchmark.cli score-project-predictions <project_dir> <predictions.jsonl>` scores external method submissions without integrating their runtime. Each row provides `probe_id`, final policy/action text, and optional retrieved evidence ids; the scorer reports pass rate, must-include recall, must-not violation rate, evidence recall, and boundary-action recall. This is the no-API bridge for Mem0/A-MEM/custom agents before full runners are available.

`python -m ultra_long_benchmark.cli score-project-release-predictions <project_release_dir> <predictions.jsonl>` applies the same scoring contract across every project in a project benchmark release. It reports project/probe coverage plus micro and macro policy-action metrics, making release-level external submissions possible without integrating a model runner.

`python -m ultra_long_benchmark.cli validate-project-prediction-submission <project_release_dir> <predictions.jsonl>` validates external submission JSONL before scoring. It checks ProjectPrediction schema, duplicate project/probe rows, unknown release keys, empty predictions, and full probe coverage, which is the lightweight CI gate for Mem0/A-MEM/custom runner outputs.

`python -m ultra_long_benchmark.cli export-project-submission-inputs <project_release_dir>` writes the no-gold input package for those external submissions. It includes project metadata, raw artifacts/events, public probe query/task metadata, and a prediction template, but excludes the gold memory graph, probe expected behavior, and evidence IDs. `verify-project-submission-inputs` checks that the package has no obvious gold-key leakage.

`python -m ultra_long_benchmark.cli run-submission-input-baseline <submission_input_dir>` runs deterministic no-gold baselines directly on the exported submission package and emits a standard `ProjectPrediction` JSONL. This verifies the same input/output contract that Mem0/A-MEM/custom runners should use, before any provider or model dependency is introduced.

Prediction scoring now emits `diagnostics.labels` per probe and `summary.diagnostic_label_counts` at project/release level. These labels are aligned with `docs/sota_failure_diagnostic_matrix.md` so paper error analysis can separate retrieval failure from action-boundary failure, stale-policy reuse, overbroad exceptions, negative-example storage, and approval/clarification omissions. Release summaries also include `by_task_type`, `by_capability`, `task_type_macro_pass_rate`, and `capability_macro_pass_rate` so headline scores cannot hide weak boundary or negative-example capabilities behind easier probes.

`python -m ultra_long_benchmark.cli evaluate-project-release <project_release_dir>` runs deterministic baselines across the whole release and emits micro/macro metrics per baseline. This is the table-generation path for no-memory, full-event-log, raw-RAG, temporal raw-RAG, and oracle-policy-graph rows before external Mem0/A-MEM runners are integrated.

Deterministic project/release baselines now emit the same `passed`, `issues`, `diagnostics.labels`, `by_task_type`, and `by_capability` structure as external submissions. This keeps no-memory/raw-RAG/oracle rows comparable to Mem0/A-MEM/custom-agent rows in one reporting table.

`python -m ultra_long_benchmark.cli score-project-release-prediction-dir <release_dir> <predictions_dir>` scores one release-level `ProjectPrediction` JSONL per external system and writes a batch manifest. This is the preferred bridge once Mem0/A-MEM/custom runners exist: each runner only needs to write one JSONL, then the repo handles scoring, diagnostics, and table export.

`python -m ultra_long_benchmark.cli export-paper-tables` merges deterministic release baselines and one or more external submission scoring reports into paper-ready JSON/CSV/Markdown tables. The export includes main results, task-type breakdowns, capability breakdowns, and failure-label breakdowns, so the paper can show whether a memory method improves longitudinal policy induction rather than only improving easy retrieval-heavy probes.

`python -m ultra_long_benchmark.cli validate-baseline-config configs/baselines` validates reproducible baseline YAMLs for no-memory, full-event-log, raw-RAG, temporal raw-RAG, oracle, action-trace scoring, prediction-submission scoring, and gated Mem0/A-MEM placeholders. `run-baseline-config` executes only deterministic in-repo baselines today; external memory systems remain dry-run gated until a concrete runner, dependency lock, and provider/model credentials are available.

`python -m ultra_long_benchmark.cli run-baseline-config-dir configs/baselines` runs the whole config directory, executing deterministic in-repo baselines and dry-running LLM/API baselines by default. `scripts/run_baseline_config_batch.sh` and `scripts/slurm/run_baseline_config_batch.sbatch` provide local and cluster entry points for this config-level evaluation harness.

`python -m ultra_long_benchmark.cli package-policy-rewrite-jobs <prompt_export_dir>` packages exported rewrite prompts into no-provider annotation handoff jobs. This creates prompt shards, empty proposal templates, token estimates, and validation command templates without calling an LLM, so the pipeline can stop cleanly when API credentials or human labeling are needed.

`python -m ultra_long_benchmark.cli collect-policy-rewrite-job-outputs <rewrite_job_dir>` is the no-provider return gate after LLM/API or human labeling. It combines completed job files into one proposal JSONL and blocks missing, empty, duplicate, schema-invalid, or still-empty template rows before rewrite validation runs.

`python -m ultra_long_benchmark.cli verify-release-integrity <release_dir> --prompt-export-dir <prompt_dir>` recomputes annotation-pack hashes, checks repo-disjoint split/task consistency, verifies prompt coverage for every release pack, and confirms no-LLM/no-unvalidated-rewrite constraints. Empty dev/test splits are warnings for fixtures and should be removed before paper-scale claims.

`python -m ultra_long_benchmark.cli assess-paper-scale <release_dir> --profile paper` checks whether the release is large, split-balanced, candidate-diverse, and longitudinal enough for main-paper claims. It intentionally fails the checked-in fixture while still writing a report with `--allow-fail`, so fixture correctness is not confused with paper-scale sufficiency.

`python -m ultra_long_benchmark.cli readiness-report` aggregates the current release evidence: smoke audit, annotation release, prompt exports, packaged rewrite jobs, release integrity, paper-scale status, public-data discovery, workflow source audit, GHArchive stage-plan decision, batch rewrite validation, batch rewrite project synthesis, project benchmark release integrity, no-gold project submission inputs, release-level deterministic baselines, release-level prediction scoring, paper table export, rewrite-project verifier, staged-slice provenance, and baseline batch status. This is the final no-provider release-readiness gate before paper-scale runs or external memory baselines. With `--require-paper-scale`, a non-ready GHArchive stage decision or non-paper-ready workflow source audit becomes blocking rather than advisory.

The verifier now includes task contracts for user-policy probes, catching schema-valid generations that lack the required policy memory type, negative evidence, distractor, future utility label, or cross-source coverage.

Policy memories now include explicit `action_boundary` metadata for allowed actions, forbidden actions, conditions, exceptions, approval/clarification requirements, and authorized/forbidden tools. The verifier checks that policy/habit memories do not remain prose-only and that probe `expected_behavior` reflects the positive evidence's action boundaries, including forbidden actions or approval/clarification requirements when present.

Latest validation commands:

```bash
python -m ultra_long_benchmark.cli smoke --all
python -m ultra_long_benchmark.cli validate
python -m ultra_long_benchmark.cli audit --json --output examples/generated/audit_report.json
python -m ultra_long_benchmark.cli grounded-pilot
python -m ultra_long_benchmark.cli github-fixture-pilot
python -m ultra_long_benchmark.cli gharchive-pilot
python -m ultra_long_benchmark.cli gharchive-quality-report --input tests/fixtures/gharchive_multi_repo_sample.jsonl --output examples/generated/gharchive_quality_report.json
python -m ultra_long_benchmark.cli gharchive-window-report --input tests/fixtures/gharchive_window_sample.jsonl --window-days 7 --output examples/generated/gharchive_window_report.json
python -m ultra_long_benchmark.cli gharchive-mine-candidates --input examples/source_fixtures/gharchive_public_events/project_gharchive_001.jsonl --repo acme/docs --output examples/generated/gharchive_candidate_report.json
python -m ultra_long_benchmark.cli gharchive-annotation-pack --input examples/source_fixtures/gharchive_public_events/project_gharchive_001.jsonl --repo acme/docs --output-dir examples/generated/annotation_packs/gharchive_policy
python -m ultra_long_benchmark.cli gharchive-annotation-pack-batch --input tests/fixtures/gharchive_multi_repo_sample.jsonl --output-dir examples/generated/annotation_packs/gharchive_batch
python -m ultra_long_benchmark.cli export-annotation-pack-release examples/generated/annotation_packs/gharchive_batch --output-dir examples/generated/release_packaging/gharchive_annotation_pack
python -m ultra_long_benchmark.cli gharchive-scale-summary examples/generated/annotation_packs/gharchive_batch --release-dir examples/generated/release_packaging/gharchive_annotation_pack --output examples/generated/gharchive_scale_summary.json
python -m ultra_long_benchmark.cli export-policy-rewrite-prompts examples/generated/annotation_packs/gharchive_policy/annotation_pack.json --output examples/generated/annotation_packs/gharchive_policy/rewrite_prompts.jsonl
python -m ultra_long_benchmark.cli export-policy-rewrite-prompts-batch examples/generated/annotation_packs/gharchive_batch --output-dir examples/generated/annotation_packs/gharchive_prompt_exports
python -m ultra_long_benchmark.cli verify-release-integrity examples/generated/release_packaging/gharchive_annotation_pack --prompt-export-dir examples/generated/annotation_packs/gharchive_prompt_exports --output examples/generated/release_integrity_report.json
python -m ultra_long_benchmark.cli assess-paper-scale examples/generated/release_packaging/gharchive_annotation_pack --profile paper --scale-summary examples/generated/gharchive_scale_summary.json --window-report examples/generated/gharchive_window_report.json --release-integrity-report examples/generated/release_integrity_report.json --output examples/generated/paper_scale_assessment.json --allow-fail
python -m ultra_long_benchmark.cli validate-policy-rewrites examples/generated/annotation_packs/gharchive_policy/annotation_pack.json examples/annotation_rewrites/gharchive_rewrite_examples.jsonl --output examples/generated/annotation_packs/gharchive_policy/rewrite_validation.json
python -m ultra_long_benchmark.cli build-project-from-rewrites examples/generated/annotation_packs/gharchive_policy/annotation_pack.json examples/annotation_rewrites/gharchive_rewrite_examples.jsonl --output-dir examples/generated/projects --project-id project_gharchive_rewrite_001
python -m ultra_long_benchmark.cli gharchive-batch-pilot --input tests/fixtures/gharchive_multi_repo_sample.jsonl
python -m ultra_long_benchmark.cli evaluate-project examples/generated/projects/project_manual_001 --output examples/generated/evaluation_harness/project_manual_baselines.json --top-k 3
python -m ultra_long_benchmark.cli evaluate-project examples/generated/projects/project_gharchive_001 --output examples/generated/evaluation_harness/project_gharchive_baselines.json --top-k 3
python -m ultra_long_benchmark.cli score-action-traces examples/generated/projects/project_gharchive_001 examples/action_traces/gharchive_trace_examples.jsonl --output examples/generated/evaluation_harness/gharchive_action_trace_report.json
python -m ultra_long_benchmark.cli score-project-predictions examples/generated/projects/project_gharchive_001 examples/project_predictions/gharchive_prediction_examples.jsonl --output examples/generated/evaluation_harness/gharchive_prediction_report.json --system-name example_external_submission
python -m ultra_long_benchmark.cli validate-baseline-config configs/baselines --output examples/generated/evaluation_harness/baseline_config_validation.json
python -m ultra_long_benchmark.cli run-baseline-config configs/baselines/no_memory_project.yaml --output examples/generated/evaluation_harness/no_memory_config_run.json
python -m ultra_long_benchmark.cli run-baseline-config configs/baselines/raw_rag_project.yaml --output examples/generated/evaluation_harness/raw_rag_config_run.json
python -m ultra_long_benchmark.cli run-baseline-config configs/baselines/temporal_raw_rag_project.yaml --output examples/generated/evaluation_harness/temporal_raw_rag_config_run.json
python -m ultra_long_benchmark.cli run-baseline-config configs/baselines/gharchive_action_trace_scoring.yaml --output examples/generated/evaluation_harness/action_trace_config_run.json
python -m ultra_long_benchmark.cli run-baseline-config configs/baselines/gharchive_prediction_submission_example.yaml --output examples/generated/evaluation_harness/prediction_submission_config_run.json
python -m ultra_long_benchmark.cli run-baseline-config-dir configs/baselines --output-dir examples/generated/evaluation_harness/baseline_batch
python -m ultra_long_benchmark.cli readiness-report --output examples/generated/readiness_report.json
python -m ultra_long_benchmark.cli run-baseline-config configs/baselines/mem0_project_placeholder.yaml --dry-run --output examples/generated/evaluation_harness/mem0_dry_run.json
```
