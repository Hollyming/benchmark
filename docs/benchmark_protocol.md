# Benchmark Protocol

This repository defines an offline-runnable construction and evaluation protocol for ultra-long trajectory memory benchmarks. The committed examples are intentionally small, deterministic, and synthetic; they exercise the complete protocol without requiring API keys, downloads, or network access.

## Unit of Evaluation

The benchmark unit is a memory challenge query grounded in one multi-session trajectory. A valid query must identify:

- `trajectory_id` and `persona_id` for the conversation history being evaluated.
- `capability` from the benchmark taxonomy.
- `prompt` shown to the evaluated system.
- `answer` when the expected behavior is direct answering.
- `evidence_event_ids` linking the answer or refusal decision to positive timeline events.
- Optional `negative_evidence_event_ids`, `obsolete_evidence_event_ids`, and `distractor_event_ids` for retrieval/use diagnostics.
- `memory_task`, the paper-facing task family, e.g. failure-aware experiment planning or provenance-constrained writing.
- `expected_behavior`, including answer, refusal/redaction, or abstention behavior.
- `rubric` with capability-specific scoring requirements.

Systems should be evaluated against the complete trajectory context or against a documented retrieval interface over the same trajectory. Reports must state which memory interface was used, whether retrieval was learned or fixed, and whether any source metadata was hidden from the model.

## Capability Taxonomy

The schema-level capability labels are deliberately narrow so results can be reported by failure mode rather than only by aggregate score.

| Capability | Required behavior | Common failure modes |
| --- | --- | --- |
| `episodic_recall` | Retrieve a specific past event among many related sessions. | Confuses similar events, invents details, ignores event identity. |
| `semantic_consolidation` | Infer stable facts from repeated evidence while retaining support. | Overfits one mention, loses provenance, treats weak evidence as stable. |
| `preference_learning` | Track durable preferences and updates over time. | Uses stale preferences, collapses temporary and durable preferences. |
| `temporal_reasoning` | Resolve dates, ordering, recency, deadlines, and supersession. | Answers with wrong time scope, misses later updates. |
| `provenance_use` | Cite or condition on source documents and event IDs. | Gives unsupported answers, cites irrelevant evidence. |
| `conflict_resolution` | Handle contradictions, corrections, and changing goals. | Averages incompatible memories, ignores the newer or higher-authority fact. |
| `privacy_refusal` | Refuse or redact private memory content when requested unsafely. | Leaks identifiers, refuses benign summaries, misses privacy tags. |
| `long_horizon_planning` | Use commitments, milestones, and goals across long spans. | Optimizes only for the current session, forgets deferred constraints. |
| `abstention` | State when memory evidence is insufficient. | Hallucinates an answer, over-refuses answerable questions. |

Every release should include per-capability counts, per-capability metrics, and examples of both passing and failing model outputs.

## Construction Protocol

1. Literature and taxonomy: record paper seeds and map each task to a capability label.
2. Seed corpora ingestion: normalize source documents into schema-validated records with provenance, license, and content hash fields.
3. Persona timeline simulation: create temporally ordered life events with privacy tags and provenance.
4. Multi-session trajectory generation: convert events into dated user/assistant/tool/environment/collaborator sessions while preserving linked event IDs; include distractor sessions, multi-event sessions, delayed callbacks, topic switching, contradictory updates, invalidated evidence, procedural failures, and multi-role constraints.
5. Memory challenge query generation: create prompts, expected behavior, answers, positive/negative/obsolete/distractor evidence links, memory-task labels, and rubrics across all capability labels, including semantic consolidation, provenance use, long-horizon planning, and abstention.
6. Annotation and quality control: run automatic checks and prepare human annotation templates.
7. Evaluation harness: score outputs by exact answer, policy behavior, evidence use, and capability-specific rubric items.
8. Release packaging: emit cards, splits, provenance manifest, and audit reports.

The offline smoke path must remain deterministic. Optional public-data or LLM-generated variants must be treated as separate releases with their own provenance and QC reports.

## Data Quality Rubric

Use this rubric before publishing any generated split. A release should either pass each item or document the exception in the dataset card.

| Dimension | Minimum bar | Evidence to report |
| --- | --- | --- |
| Schema validity | All JSONL rows validate against package models and JSON Schemas. | Audit report plus validation command output. |
| Provenance completeness | Each document and event has source ID, origin, license, and hash when available. | Provenance manifest and missing-field counts. |
| Temporal integrity | Events and sessions are timestamped, ordered, and timezone-explicit. | QC checks for ordering and malformed timestamps. |
| Evidence linkage | Each answerable query cites sufficient positive event IDs and, when applicable, negative/obsolete/distractor IDs. | Query-to-event coverage table plus invalid-evidence counts. |
| Capability coverage | All claimed capabilities appear in train/dev/test or are explicitly excluded. | Per-capability count table. |
| Privacy handling | Sensitive facts are tagged and paired with refusal/redaction queries. | Privacy tag counts and refusal-query accuracy. |
| Contamination control | Splits avoid duplicate trajectories, near-duplicate prompts, and source leakage. | Split manifest and deduplication notes. |
| Annotation reliability | Human labels include instructions, adjudication rules, and agreement statistics. | Annotation template, IAA metrics, adjudication log. |
| Baseline sanity | At least one deterministic baseline and one stronger system are reported when publishing claims. | Metrics table with confidence intervals or bootstrap notes. |

## Evaluation Protocol

A model evaluation report should include:

- Dataset version, split name, commit or release manifest hash, and audit status.
- Prompting format, memory retrieval policy, context budget, decoding parameters, and any system instructions.
- Aggregate score and per-capability scores.
- Separate reporting for answerable, refusal/redaction, and abstention queries.
- Evidence sufficiency score when the model is asked to cite memories.
- Error analysis over stale memory, wrong event, unsupported answer, privacy leak, and over-refusal categories.

Recommended primary metrics:

- `exact_or_policy_accuracy`: direct answer exact match or correct refusal/redaction policy.
- `capability_accuracy`: the same score grouped by `capability`.
- `evidence_recall`: fraction of required evidence event IDs cited or retrieved.
- `privacy_leak_rate`: fraction of privacy-sensitive queries where protected content is exposed.
- `abstention_calibration`: accuracy on insufficient-evidence queries.
- `trajectory_stressor_coverage`: per-split counts for distractor sessions, multi-event sessions, delayed callbacks, topic switches, contradictory updates, negative evidence, procedural failures, and multi-role constraints.
- `negative_evidence_avoidance`: rate at which systems avoid using marked invalid, obsolete, or distractor evidence.
- `memory_task_accuracy`: accuracy grouped by paper-facing task family, not only schema-level capability.

## Innovation-Oriented Capability Framing

For agent-memory papers, the benchmark should be framed around memory *use* and **compositional experience modeling**, not only memory *storage*. The local smoke data follows the design document's formula:

```text
Memory = Causal + Versioned + Provenance-aware + Task-conditioned + Actionable Experience State
```

The query and trajectory blocks are intended to expose capability gaps that are easy to miss in simple recall datasets:

1. **Consolidation without contamination**: the agent must infer a stable user/project state from distributed evidence while refusing to promote side conversations into durable memory.
2. **Provenance-aware and versioned memory use**: the agent must justify recommendations with event IDs and source relations, especially when a newer memory supersedes an older one or a result is invalidated.
3. **Planning over deferred commitments and procedural failures**: the agent must carry callbacks, deadlines, and failure lessons across sessions instead of optimizing for the current message only.
4. **Task-conditioned storage**: the agent must decide what is worth preserving based on user/project/future-task utility rather than static universal rules.
5. **Multi-role constraint resolution**: the agent must separate user, collaborator, reviewer, tool, and environment constraints instead of conflating all messages into one stream.
6. **Calibrated non-answering**: the agent must abstain when the trajectory does not contain a decision, rather than hallucinating plausible venues, dates, or collaborators.

These should be reported separately from aggregate accuracy; otherwise a system can look strong by answering direct recall questions while failing the more novel agent-memory behaviors.

When outputs are free-form, exact match should be supplemented with human or model-assisted judging using the released rubric. Any model-assisted judge must be identified, versioned, and sanity-checked against human labels.

## Reproducibility Checklist

Before submitting results or releasing a dataset version:

- Run `python -m ultra_long_benchmark.cli smoke --all`.
- Run `python -m ultra_long_benchmark.cli validate`.
- Run `python -m ultra_long_benchmark.cli audit --json --output examples/generated/audit_report.json`.
- Run `pytest`.
- Record package version, Python version, operating system, and dependency versions.
- Publish configs, generation seeds, split manifests, dataset card, benchmark card, QC report, and audit report.
- Confirm no API keys, raw restricted corpora, or unreviewed personal data are committed.
- Document any optional network, LLM, or public-data steps separately from the offline smoke path.
