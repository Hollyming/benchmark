# Benchmark Design

This benchmark treats long-term memory as a user-policy induction problem for tool-using agents. The construction path creates temporally extended workflow event streams and asks future tool tasks whose correct behavior depends on how this user normally works.

The motivating research position is **memory as user policy**, not memory as long-context QA:

```text
Memory as User Policy = Habit Induction + Contextual Exceptions + Tool Boundaries + Authorization Scope + Negative Examples + Future Action Alignment
```

For the full protocol, quality rubric, evaluation guidance, and reproducibility checklist, see `docs/benchmark_protocol.md`.

## Capability Taxonomy

- User policy induction: infer implicit work policies from traces rather than explicit profile text.
- Habit generalization: generalize recurring behavior across days or weeks while ignoring one-off requests.
- Contextual policy selection: choose the policy whose conditions match the future task.
- Tool action alignment: take allowed tool actions and avoid forbidden actions such as unauthorized send, merge, pay, or reveal.
- Workflow boundary respect: preserve approval gates, review gates, and channel-specific limits.
- Policy update and exception handling: apply narrow exceptions without globalizing them.
- Proactive routine recognition: recover ordered routines such as doc review chains.
- Privacy authorization boundary: use sensitive information only in authorized tools or contexts.
- Habit storage gating: decide what should become durable policy memory and what should be suppressed.
- Abstention clarification: ask when authorization is missing.

Aggregate scores should not be used alone because an agent can complete a tool task while violating the user's policy.

## Construction Contract

Each stage emits typed JSONL/JSON artifacts and should be replaceable by stronger implementations without changing downstream schemas. The smoke implementation uses deterministic synthetic data for CI and peer review.

Replacement implementations must preserve stable IDs, provenance links, privacy tags, timestamp semantics, policy evidence links, and action-boundary metadata. Public-data or LLM-assisted variants should include separate QC and audit reports.

Policy and habit memories should use the explicit `action_boundary` field rather than relying only on prose. Boundary metadata should include allowed actions, forbidden actions, conditions, exceptions, approval or clarification requirements, and authorized/forbidden tools when applicable.

## Trajectory Complexity Contract

Paper-scale trajectories should include:

- Cross-tool workflows spanning email, calendar, docs, chat, issues, PRs, browser, files, forms, or code.
- Distractor sessions with no durable policy target.
- Multi-event sessions where several policies are introduced together.
- Topic switching so transient requests are not over-consolidated.
- Policy updates and narrow exceptions.
- Negative examples that should suppress overgeneralization.
- Privacy and authorization boundaries.
- Ambiguous authorization gaps that require clarification.

The smoke generator records these in `trajectory.metadata.complexity_features`; releases should report them by split.

## Policy Memory Contract

The target object is a user policy model:

```text
User Policy Model = Durable Habits + Contextual Policies + Ordered Routines + Tool Boundaries + Exceptions + Negative Examples + Authorization Gaps
```

Current paper-facing tasks include:

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

Generated probes expose `memory_task`, positive evidence, and optional negative/obsolete/distractor evidence so policy induction quality and final tool-action quality can be analyzed separately.
