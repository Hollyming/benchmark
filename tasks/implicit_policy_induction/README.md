# Implicit Policy Induction

Core question: can a system infer durable user or workspace policy from repeated historical behavior?

Required gold fields:

- `memory_type=user_policy`
- positive source events
- distractor events with similar surface form but different condition
- `ActionBoundary.conditions`

Primary metrics:

- Policy Recall
- Policy Precision
- Condition Accuracy
- Evidence Faithfulness

Current status: covered through the broader GHArchive policy graph construction path, but not counted as a standalone GHArchive task type in the current release.
