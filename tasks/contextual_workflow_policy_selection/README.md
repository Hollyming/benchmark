# Contextual Workflow Policy Selection

Core question: can a system choose the right policy only when the repo, issue, label, actor, or workflow context matches?

Required gold fields:

- contextual positive evidence
- negative or distractor evidence from a near-miss context
- `ActionBoundary.conditions`
- expected `must_include` and `must_not_include`

Primary metrics:

- Policy Action Accuracy
- Condition Accuracy
- Evidence Faithfulness
- Overgeneralization Rate

Current status: covered in the formal GHArchive release.
