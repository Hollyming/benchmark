# Codex Handoff Prompt: Reference-Grounded CompResearchMem Engineering

You are working in `E:/work/benchmark`, a Python benchmark-construction repository for Agent Memory research.

## Research direction

The project is moving from an offline synthetic smoke scaffold toward a reference-dataset-grounded, LLM-assisted, verifier-driven benchmark for compositional experience memory.

Core formula:

```text
Memory = Causal + Versioned + Provenance-aware + Task-conditioned + Actionable Experience State
```

Do not treat the task as simply making longer dialogue QA. The key chain is:

```text
reference artifact -> canonical event -> memory graph -> evidence-constrained probe -> verifier
```

LLM generation, when added, should only rewrite/bridge/perturb grounded evidence; it must not become the source of gold facts.

## Existing work

The repo already has:

- deterministic synthetic smoke pipeline
- Pydantic models and JSON schemas
- trajectory/query/QC/audit/stress pipelines
- docs describing CompResearchMem alignment
- current local commit `56070c3 Add reference-grounded pilot scaffold` may exist locally and may or may not be pushed depending on network

Recently added core objects:

- `SourceArtifact`
- `CanonicalEvent`
- `ProjectProfile`
- `MemoryGraph`
- `MemoryNode`
- `MemoryRelation`
- `Probe`
- `VerifierReport`

Recently added files:

- `ultra_long_benchmark/pipelines/grounded_pilot.py`
- `ultra_long_benchmark/pipelines/verifier.py`
- `tests/test_grounded_pilot.py`
- `schemas/source_artifact.schema.json`
- `schemas/canonical_event.schema.json`
- `schemas/project_profile.schema.json`
- `schemas/memory_graph.schema.json`
- `schemas/probe.schema.json`
- `schemas/verifier_report.schema.json`

CLI commands:

```bash
python -m ultra_long_benchmark.cli smoke --all
python -m ultra_long_benchmark.cli grounded-pilot
python -m ultra_long_benchmark.cli verify-project examples/generated/projects/project_manual_001
python -m ultra_long_benchmark.cli validate
python -m ultra_long_benchmark.cli audit --json --output examples/generated/audit_report.json
pytest -q
```

Current verification target:

```text
9 tests passing
```

## Coding standards

- Keep offline smoke path deterministic.
- Do not introduce mandatory network/API dependencies into tests.
- Preserve project-centric generated structure:

```text
examples/generated/projects/project_0001/
  project_profile.json
  source_manifest.json
  artifacts.jsonl
  events.jsonl
  memory_graph.json
  probes.jsonl
  verifier_report.json
```

- Keep source provenance explicit: every grounded event should point to artifacts or explicit synthetic bridge metadata.
- Probes should bind to `MemoryGraph` memory IDs, not directly to vague template facts.
- Verifier should fail loudly on missing artifacts, missing source events, missing positive evidence, missing negative/distractor evidence when required.

## Recommended next tasks

1. Refactor manual grounded pilot into composable stages:
   - manual seed adapter
   - canonical event conversion
   - project binding
   - memory graph builder
   - probe synthesizer
   - verifier

2. Add a minimal `manual_seed_adapter` task and docs:
   - input: manually authored `examples/manual_grounded_seed/*.jsonl`
   - output: project-centric artifacts/events/profile

3. Strengthen verifier checks:
   - temporal consistency for `supersedes` / `invalidates`
   - role attribution coverage
   - negative evidence validity
   - answer uniqueness placeholder check
   - split leakage placeholder check

4. Add tests for broken project cases:
   - missing artifact referenced by event
   - probe references missing memory
   - active memory has no source events

5. Update docs with the new grounded construction pipeline.

Before finishing, always run:

```bash
python -m ultra_long_benchmark.cli smoke --all
python -m ultra_long_benchmark.cli grounded-pilot
python -m ultra_long_benchmark.cli validate
python -m ultra_long_benchmark.cli audit --json --output examples/generated/audit_report.json
pytest -q
```

Report concise summary plus changed files and test results.
