# LongUserPolicyBench Core Tasks

This directory now tracks the benchmark task taxonomy, not the old construction-pipeline demos.

Each task spec defines the target behavior, required gold fields, verifier checks, and metrics that must be supported before a domain can claim coverage. Implementation code lives under `ultra_long_benchmark/`; release artifacts live under `examples/generated/`.

Current formal release coverage:

- `contextual_workflow_policy_selection`
- `tool_action_policy_alignment`
- `negative_example_storage_gating`
- `privacy_authorization_boundary`

Planned task specs remain here so new domains can be added without changing the benchmark objective.
