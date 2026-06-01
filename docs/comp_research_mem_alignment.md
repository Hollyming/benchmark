# LongUserPolicyBench Alignment Summary

LongUserPolicyBench targets **Longitudinal User Policy / Habit Induction for Tool-Using Agents**. The benchmark asks whether a system can infer durable workflow policy from longitudinal traces and apply that policy to future tool decisions, including approval gates, exception scope, negative examples, privacy boundaries, and action constraints.

```text
Memory as User Policy = Habit Induction + Contextual Exceptions + Tool Boundaries + Authorization Scope + Negative Examples + Future Action Alignment
```

## SOTA Gap

- Mem0 focuses on long-term memory extraction, consolidation, retrieval, and graph memory; this benchmark adds future action-boundary and authorization scoring.
- A-MEM organizes agent memories with note/link/evolution mechanics; this benchmark checks whether those memories encode allowed, forbidden, approval, clarification, and exception-scope constraints.
- Graphiti/Zep-style temporal KGs model dynamic relationships; this benchmark requires deontic workflow policy and negative-example handling, not only temporal entity links.
- Long-context and virtual-memory systems can expose history, but the metric asks whether retrieved history actually constrains irreversible or externally visible tool actions.
- Agent benchmarks such as AppWorld, WorkArena, and tau-bench are useful substrates; LongUserPolicyBench differs by making policy latent in longitudinal behavior rather than explicit task instructions.

See `docs/sota_failure_diagnostic_matrix.md` for diagnostic labels such as `retrieved_but_not_applied`, `overbroad_exception`, `stale_policy_reuse`, `negative_example_stored`, and `approval_gate_bypassed`.

## Current Formal Surface

The first release-ready domain is GHArchive public GitHub developer workflow data:

- 60,000 staged public events from January 2024;
- 30 selected repos;
- 168 verifier-checked probes;
- train/dev/test split of 102/37/29 probes;
- 4 task types and 5 capability enum values covered;
- hardened no-gold submission inputs for external methods.

The current release artifacts use the `gharchive_formal` prefix and are the canonical GHArchive benchmark release artifacts.

## Task Families

The task taxonomy is represented in `tasks/` and in Chapter 7/9 of the main document. The formal benchmark focuses on:

- implicit policy induction;
- contextual workflow policy selection;
- tool/action policy alignment;
- negative-example storage gating;
- privacy/authorization boundaries;
- habit generalization;
- routine step ordering;
- policy update and exception handling;
- authorization-gap clarification;
- artifact-management habit transfer;
- cross-tool boundary composition.

The current GHArchive release covers a GitHub/developer-workflow subset. Email, calendar, docs, chat, and browser/web-search are planned domains but are not release claims.

## Evaluation Interface

External systems receive no-gold submission inputs:

- `projects.jsonl`
- `artifacts.jsonl`
- `events.jsonl`
- `probes.jsonl`
- `prediction_template.jsonl`
- `submission_manifest.json`

They must output `ProjectPrediction` JSONL. Gold memories, probe expected behavior, and gold evidence IDs are used only by validation and scoring commands after submission.

Current checked-in baseline configs are:

- `memory_submission_event_profile_stub.yaml`
- `memory_submission_event_profile_stub_hardened.yaml`
- `external_memory_runner_echo_contract.yaml`
- `mem0_submission_placeholder.yaml`
- `a_mem_submission_placeholder.yaml`
- `graphiti_submission_placeholder.yaml`

The Mem0/A-MEM/Graphiti rows available now are OpenAI-compatible prompt adapters over hardened no-gold inputs. Upstream package baselines still require method-specific runners, dependency isolation, provider credentials, storage configuration where applicable, and Slurm resource profiles.

## Gate Boundary

The formal release gate is `scripts/run_benchmark_release_gate.sh`. It refreshes or verifies baseline config hashes, baseline batch outputs, claim-boundary reports, claim lint, artifact bundle hashes, taxonomy coverage, domain-expansion status, readiness, and the final gate report.

`readiness-report` aggregates annotation release, prompt exports, rewrite jobs, release integrity, paper-scale status, public-data discovery, workflow source audit, batch rewrite validation, rewrite-derived projects, no-gold inputs, deterministic baselines, prediction scoring, paper tables, taxonomy/domain coverage, claim boundaries, artifact bundle verification, staged-slice provenance, and baseline batch status.

Domain expansion remains gated: the Enron/email path has a redacted preflight, and calendar/docs/chat/browser-web have manifest-first fixtures, but none of these are formal release domains until they pass the same data-source, verifier, no-gold, baseline, readiness, artifact, and claim-boundary gates as GHArchive.
