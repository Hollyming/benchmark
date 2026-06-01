# Privacy / Authorization Boundary

Core question: can a system avoid revealing, sending, merging, paying, or submitting when authorization is absent or channel/tool use is forbidden?

Required gold fields:

- authorized tools
- forbidden tools
- `requires_approval` or `requires_clarification`
- private or restricted source artifacts where relevant
- expected abstain/clarify behavior

Primary metrics:

- Authorization Boundary Accuracy
- Clarification Accuracy
- Boundary Violation Rate
- `micro_must_not_violation_rate`

Current status: covered in the formal GHArchive release.
