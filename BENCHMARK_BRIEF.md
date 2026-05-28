# Ultra-Long Trajectory Benchmark Workspace Brief

Owner goal (from user): Build professional, top-tier-paper-quality data construction pipelines for ultra-long-horizon agent trajectories, aligned with an Agent Memory research direction. Each task block should have its own folder. Pipelines may reuse/download public data when useful and should support future LLM API calls after keys are provided.

Working directory: E:/work/benchmark

High-level research target:
- Construct ultra-long trajectory datasets for evaluating agent memory systems over long horizons.
- Emphasize realistic, multi-session, multi-source, temporally extended agent-user/environment interaction traces.
- Capture memory requirements that current short-context benchmarks miss.
- Produce reproducible pipelines, schemas, quality controls, and evaluation hooks suitable for a strong systems/ML/NLP paper.

Assumptions because prior survey notes are not present in this folder:
- Core innovation: benchmark ultra-long agent trajectories requiring durable memory, temporal grounding, preference/persona consistency, cross-session recall, evolving goals, and contradiction handling.
- Required abilities: episodic recall, semantic consolidation, preference learning, temporal reasoning, provenance-aware memory use, conflict resolution, privacy/safety filtering, long-horizon planning, and robust abstention when memory evidence is insufficient.

Expected workspace structure:
- README.md: clear overview, task map, quickstart, design principles.
- docs/: literature-grounded benchmark design, taxonomy, dataset cards, risk notes.
- schemas/: JSON Schemas / Pydantic models for events, trajectories, memories, queries, annotations.
- tasks/<task_name>/: one folder per data-construction task, with README, scripts, configs, tests/smoke checks, sample outputs.
- shared/: shared utilities for IO, validation, time simulation, LLM client abstraction, provenance, privacy filtering.
- configs/: YAML configs for all pipelines.
- examples/: tiny synthetic examples committed for smoke tests.

Task blocks to create:
1. literature_and_taxonomy
   - Output a literature map and benchmark capability taxonomy.
   - Include scripts to maintain paper metadata from a YAML/JSON seed list.
2. seed_corpora_ingestion
   - Pipeline to ingest public corpora and local seed materials into normalized source documents.
   - Avoid huge downloads by default; provide dry-run/sample mode and documented optional download commands.
3. persona_life_event_simulation
   - Pipeline to synthesize long-running user/persona timelines with preferences, projects, commitments, relationships, contradictions, and temporal drift.
4. multi_session_agent_trajectory_generation
   - Pipeline to generate multi-session agent-user trajectories from timelines and source docs.
   - Must support future LLM API providers through environment variables.
5. memory_challenge_query_generation
   - Pipeline to generate benchmark questions/tasks requiring memory: direct recall, temporal, preference, contradiction, provenance, summarization, planning, privacy-sensitive refusal.
6. annotation_and_quality_control
   - Pipeline for automatic checks plus human annotation templates/rubrics; inter-annotator agreement hooks.
7. evaluation_harness
   - Harness skeleton for evaluating memory-enabled agents/baselines with metrics.
8. release_packaging
   - Dataset card, model card-like benchmark card, license/provenance manifest, train/dev/test split tools.

Quality bar:
- Professional, reproducible, modular, typed Python.
- No hidden API key assumptions; .env.example only.
- Every task has a smoke test or demo command that runs offline.
- Use schemas and validation everywhere.
- Document top-tier paper rationale and potential failure modes.
- Prefer small examples over huge artifacts.

Codex should implement files, code, sample data, and docs. It should not wait for user input. If web/API unavailable, create seeds/placeholders and document how to extend.
