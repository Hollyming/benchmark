# LongUserPolicyBench Alignment Summary

This repository has shifted from a research-collaborator memory scaffold to **Longitudinal User Policy / Habit Induction for Tool-Using Agents**.

## Core Research Claim

Next-generation agent-memory benchmarks should move beyond long-context QA and fact recall. A useful personal or workplace agent must learn **how this user works** from longitudinal, cross-tool traces and apply that learned policy in future actions.

```text
Memory as User Policy = Habit Induction + Contextual Exceptions + Tool Boundaries + Authorization Scope + Negative Examples + Future Action Alignment
```

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

The verifier now includes task contracts for user-policy probes, catching schema-valid generations that lack the required policy memory type, negative evidence, distractor, future utility label, or cross-source coverage.

Policy memories now include explicit `action_boundary` metadata for allowed actions, forbidden actions, conditions, exceptions, approval/clarification requirements, and authorized/forbidden tools. The verifier checks that policy/habit memories do not remain prose-only.

Latest validation commands:

```bash
python -m ultra_long_benchmark.cli smoke --all
python -m ultra_long_benchmark.cli validate
python -m ultra_long_benchmark.cli audit --json --output examples/generated/audit_report.json
python -m ultra_long_benchmark.cli grounded-pilot
python -m ultra_long_benchmark.cli github-fixture-pilot
```
