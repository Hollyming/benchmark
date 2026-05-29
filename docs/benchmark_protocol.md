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
| Action boundary clarity | Expected behavior states allowed, forbidden, or clarification-required actions. | Must-include/must-not-include checks and boundary labels. |
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
- `memory_task_accuracy`: accuracy grouped by paper-facing task family.
- `trajectory_stressor_coverage`: per-split counts for cross-tool workflows, distractors, policy updates, negative examples, privacy boundaries, and authorization gaps.

## Reproducibility Checklist

Before submitting results or releasing a dataset version:

- Run `python -m ultra_long_benchmark.cli smoke --all`.
- Run `python -m ultra_long_benchmark.cli validate`.
- Run `python -m ultra_long_benchmark.cli audit --json --output examples/generated/audit_report.json`.
- Run `python -m ultra_long_benchmark.cli grounded-pilot`.
- Run `python -m ultra_long_benchmark.cli github-fixture-pilot`.
- Run `pytest` when the test dependency is installed.
- Record package version, Python version, operating system, and dependency versions.
- Publish configs, generation seeds, split manifests, dataset card, benchmark card, QC report, and audit report.
- Confirm no API keys, raw restricted corpora, or unreviewed personal data are committed.
- Document any optional network, LLM, or public-data steps separately from the offline smoke path.
