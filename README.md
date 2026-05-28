# Ultra-Long Trajectory Benchmark

Offline-first workspace for constructing ultra-long-horizon agent trajectory datasets for memory-system evaluation. The repository is organized as a reproducible data-construction benchmark: typed schemas, deterministic synthetic examples, task-local scripts, validation hooks, and optional extension points for public corpora and LLM providers.

## Quickstart

```powershell
python -m ultra_long_benchmark.cli smoke --all
python -m ultra_long_benchmark.cli audit
```

Generated demo artifacts are written to `examples/generated/`. No API keys or network calls are required for the smoke path.

## Task Map

| Task | Purpose | Offline demo |
| --- | --- | --- |
| `literature_and_taxonomy` | Maintain paper seeds and benchmark capability taxonomy. | `python tasks/literature_and_taxonomy/scripts/run_demo.py` |
| `seed_corpora_ingestion` | Normalize public/local seed materials into source documents. | `python tasks/seed_corpora_ingestion/scripts/run_demo.py` |
| `persona_life_event_simulation` | Synthesize temporally extended personas and life events. | `python tasks/persona_life_event_simulation/scripts/run_demo.py` |
| `multi_session_agent_trajectory_generation` | Build multi-session user-agent traces from timelines and sources. | `python tasks/multi_session_agent_trajectory_generation/scripts/run_demo.py` |
| `memory_challenge_query_generation` | Generate memory-dependent benchmark queries. | `python tasks/memory_challenge_query_generation/scripts/run_demo.py` |
| `annotation_and_quality_control` | Run automatic QC and emit human annotation templates. | `python tasks/annotation_and_quality_control/scripts/run_demo.py` |
| `evaluation_harness` | Evaluate memory-agent outputs and baselines. | `python tasks/evaluation_harness/scripts/run_demo.py` |
| `release_packaging` | Build dataset card, split files, and provenance manifest. | `python tasks/release_packaging/scripts/run_demo.py` |

## Design Principles

- Ultra-long trajectories are represented as dated, provenance-bearing event streams across many sessions.
- Memory challenges target durable recall, temporal grounding, evolving preferences, contradiction handling, privacy-sensitive refusal, provenance use, and abstention.
- Every artifact carries stable IDs, source provenance, and schema validation paths.
- Public-data download and LLM generation are optional documented steps; committed smoke demos use synthetic data only.
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
