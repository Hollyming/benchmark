# Negative Example Storage Gating

Core question: can a system avoid storing one-off, emergency, obsolete, or human-only behavior as durable habit?

Required gold fields:

- positive durable policy evidence
- negative evidence
- explicit `memory_type=negative_policy_example` or equivalent marker
- expected behavior that rejects broad storage or broad action

Primary metrics:

- Negative Example Suppression
- Overgeneralization Rate
- Boundary Violation Rate
- diagnostic label count for `negative_example_stored`

Current status: covered in the formal GHArchive release.
