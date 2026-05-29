# Codex Handoff Prompt: Reference-Grounded LongUserPolicyBench Engineering

You are working in `/home/jmzhang/Workspace/benchmark`, a Python benchmark-construction repository for longitudinal user-policy and habit induction in tool-using agents.

## Research Direction

The project is moving toward a reference-grounded, LLM-assisted, verifier-driven benchmark for learning how a user works from longitudinal tool-use trajectories.

Core formula:

```text
Memory as User Policy = Habit Induction + Contextual Exceptions + Tool Boundaries + Authorization Scope + Negative Examples + Future Action Alignment
```

Do not treat the task as longer dialogue QA. The key chain is:

```text
reference artifact -> canonical workflow event -> policy graph -> future tool-policy probe -> verifier
```

LLM generation, when added, should only rewrite/bridge/perturb grounded evidence or synthesize future probes; it must not become the source of gold policy facts.

## Current Verification Commands

```bash
python -m ultra_long_benchmark.cli smoke --all
python -m ultra_long_benchmark.cli grounded-pilot
python -m ultra_long_benchmark.cli github-fixture-pilot
python -m ultra_long_benchmark.cli validate
python -m ultra_long_benchmark.cli audit --json --output examples/generated/audit_report.json
.venv/bin/python -m pytest -q
```

The repository has a local conda environment at `.venv` with dev dependencies installed. CLI paths should still remain deterministic and offline.

## Engineering Constraints

- Do not introduce mandatory network/API dependencies into tests.
- Preserve generated project structure under `examples/generated/projects/`.
- Keep source provenance explicit.
- Probes should bind to policy/memory graph IDs.
- Verifier should fail loudly on missing artifacts, missing source events, missing positive evidence, invalid negative evidence, missing task-contract requirements, and missing distractors when required.
