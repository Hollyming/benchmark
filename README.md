# Longitudinal User Policy Benchmark

Offline-first workspace for constructing longitudinal user workflow trajectories for tool-using agent evaluation. The benchmark targets whether agents can induce a user's implicit work policies, habits, routines, authorization boundaries, and context-dependent exceptions from cross-day and cross-tool traces.

## Quickstart

```powershell
python -m ultra_long_benchmark.cli smoke --all
python -m ultra_long_benchmark.cli audit
```

Generated demo artifacts are written to `examples/generated/`. No API keys or network calls are required for the smoke path.

The repository currently includes reference-grounded manual and GitHub/CI fixtures plus a local `GHArchiveEventAdapter` for public GitHub event slices. Large Enron/Avocado/GHArchive/AppWorld-derived releases are not yet generated in-tree; those should be staged as separate provenance-tracked data builds.

## Task Map

| Task | Purpose | Offline demo |
| --- | --- | --- |
| `literature_and_taxonomy` | Maintain paper seeds and benchmark capability taxonomy. | `python tasks/literature_and_taxonomy/scripts/run_demo.py` |
| `seed_corpora_ingestion` | Normalize public/local seed materials into source documents. | `python tasks/seed_corpora_ingestion/scripts/run_demo.py` |
| `persona_life_event_simulation` | Synthesize temporally extended personas and life events. | `python tasks/persona_life_event_simulation/scripts/run_demo.py` |
| `multi_session_agent_trajectory_generation` | Build multi-session user-agent traces from timelines and sources. | `python tasks/multi_session_agent_trajectory_generation/scripts/run_demo.py` |
| `memory_challenge_query_generation` | Generate future tool-policy probes from user workflow histories. | `python tasks/memory_challenge_query_generation/scripts/run_demo.py` |
| `annotation_and_quality_control` | Run automatic QC and emit human annotation templates. | `python tasks/annotation_and_quality_control/scripts/run_demo.py` |
| `evaluation_harness` | Evaluate memory-agent outputs and baselines. | `python tasks/evaluation_harness/scripts/run_demo.py` |
| `release_packaging` | Build dataset card, split files, and provenance manifest. | `python tasks/release_packaging/scripts/run_demo.py` |

## Design Principles

- Longitudinal trajectories are represented as dated, provenance-bearing event streams across many tools and sessions.
- Probes target implicit policy induction, habit generalization, workflow boundaries, policy exceptions, negative examples, privacy/authorization boundaries, and clarification when authorization is missing.
- Every artifact carries stable IDs, source provenance, and schema validation paths.
- Public-data download and LLM generation are optional documented steps; committed smoke demos use deterministic synthetic data only.
- Data construction is modular so future papers can replace any stage while preserving downstream contracts.

## Repository Layout

- `ultra_long_benchmark/`: Python package with models, pipeline stages, shared utilities, and CLI.
- `schemas/`: JSON Schemas for data contracts.
- `configs/`: YAML configs for each pipeline.
- `tasks/`: task-local READMEs and executable demo scripts.
- `docs/`: benchmark rationale, taxonomy, dataset card, and risk notes.
- `examples/`: tiny committed seeds plus generated smoke-test outputs.

## Protocol and Review Artifacts

- `docs/benchmark_protocol.md`: benchmark protocol, capability taxonomy, data quality rubric, evaluation protocol, and reproducibility checklist.
- `docs/benchmark_design.md`: design rationale and construction contract.
- `python -m ultra_long_benchmark.cli audit --json --output examples/generated/audit_report.json`: lightweight offline audit over `examples/generated/` with counts, schema status, and QC status.

## Optional LLM/Public Data Use

Copy `.env.example` to `.env` and provide provider-specific keys only when running non-smoke generation. The default code path uses a deterministic offline client. Optional public data ingestion should be staged into `data/raw/` and then passed through `seed_corpora_ingestion`; raw data is intentionally git-ignored.
