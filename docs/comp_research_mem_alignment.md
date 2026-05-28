# CompResearchMem Alignment Summary

This repository now aligns the offline smoke benchmark with the Feishu design proposal: **Agent Memory 超长程 Benchmark：组合式经验记忆调研与构建方案**.

## Core research claim

Next-generation Agent Memory benchmarks should move from **memory as recall/retrieval** to **memory as compositional experience model**:

```text
Memory = Causal + Versioned + Provenance-aware + Task-conditioned + Actionable Experience State
```

A long-running agent should construct, update, retrieve, and apply experience memory from heterogeneous trajectories involving conversations, tools, experiments, artifacts, collaborators, and evolving project goals.

## Implemented smoke-data hooks

The deterministic smoke generator now includes compact examples of:

- Distractor sessions: transient requests that should not become durable memory.
- Multi-event sessions: project goals and commitments introduced together.
- Delayed callbacks: deadlines that must remain active across sessions.
- Topic switching: side topics inside otherwise relevant sessions.
- Contradictory updates: newer user preferences supersede older ones.
- Negative evidence: invalidated baseline results should suppress citation/use.
- Procedural failure lessons: CUDA OOM and validated smaller batch-size alternative.
- Multi-role constraints: reviewer/collaborator constraints must be attributed and prioritized.

## Paper-facing memory task families

Generated queries include a `memory_task` label covering:

- `research_thread_resumption`
- `failure_aware_experiment_planning`
- `versioned_claim_tracking`
- `provenance_constrained_writing`
- `cross_source_evidence_composition`
- `task_conditioned_personalized_storage`
- `multi_role_constraint_resolution`
- `obsolete_negative_evidence_suppression`
- `long_horizon_aggregated_reasoning`
- plus `privacy_aware_memory_use` and `calibrated_non_answering`

Each query can now include positive evidence (`evidence_event_ids`) plus optional `negative_evidence_event_ids`, `obsolete_evidence_event_ids`, and `distractor_event_ids` so retrieval diagnostics and final-answer scoring can be separated.

## Current smoke artifact counts

After `python -m ultra_long_benchmark.cli smoke --all`:

- personas: 2
- events: 18
- trajectories: 2
- sessions: 22
- messages: 54
- queries: 24
- queries with negative evidence: 6
- queries with obsolete evidence: 6
- queries with distractors: 6

All examples remain deterministic and offline-runnable.

## Manual grounded pilot flow

The first reference-grounded pilot now uses a small checked-in seed file rather than keeping all seed data in Python:

```text
examples/manual_grounded_seed/project_manual_001.json
```

`ultra_long_benchmark.pipelines.grounded_pilot` treats that file as a manual seed adapter and then runs modular stages:

```text
manual seed adapter
 -> source artifacts / project profile
 -> canonical event conversion
 -> memory graph builder
 -> probe synthesizer
 -> project writer
 -> verifier
```

The adapter contract now lives in `ultra_long_benchmark.pipelines.source_adapters`: future SWE-bench, GitHub, arXiv, OpenReview, or search-trace adapters should emit the same `AdapterResult` shape (`ProjectProfile`, `SourceArtifact`, `CanonicalEvent`) before downstream memory-graph and probe stages run.

A first real-dataset-shaped local fixture adapter, `GitHubIssueCIAdapter`, reads `examples/source_fixtures/github_issue_ci/project_github_001.json` and normalizes GitHub issue / CI log / patch / review-style records into the same contract. It performs no network access, but its shape is intended to mirror a future SWE-bench or GitHub issue-commit adapter.

This keeps the pilot deterministic and offline while making the future SWE-bench/GitHub/arXiv/OpenReview adapters match the same output contract.

```bash
python -m ultra_long_benchmark.cli smoke --all
python -m ultra_long_benchmark.cli validate
python -m ultra_long_benchmark.cli audit --json --output examples/generated/audit_report.json
pytest -q
```

Latest verification passed: schema validation, audit, and 6 pytest tests.
