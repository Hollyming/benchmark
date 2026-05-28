# Data Quality Rubric

Use this rubric for human review and automatic QC. A top-tier benchmark should optimize for discriminative validity rather than just volume.

## A. Trajectory Realism

| Score | Criterion |
| --- | --- |
| 0 | Events are disconnected or obviously templated. |
| 1 | Persona has stable attributes but little temporal continuity. |
| 2 | Sessions refer back to prior events and show plausible day-to-day variation. |
| 3 | Long-range dependencies, drift, interruptions, and project continuity are natural. |

## B. Memory Necessity

| Score | Criterion |
| --- | --- |
| 0 | Query is answerable from the prompt alone. |
| 1 | Query needs short local context only. |
| 2 | Query needs evidence across sessions or dates. |
| 3 | Query needs cross-session integration, conflict resolution, or durable preference memory. |

## C. Evidence Grounding

| Score | Criterion |
| --- | --- |
| 0 | Expected answer has no traceable evidence. |
| 1 | Evidence exists but IDs are incomplete or ambiguous. |
| 2 | Evidence IDs are complete and sufficient. |
| 3 | Evidence also supports plausible distractor analysis and provenance audit. |

## D. Temporal Validity

| Score | Criterion |
| --- | --- |
| 0 | Dates are inconsistent or impossible. |
| 1 | Dates are valid but not meaningful. |
| 2 | Temporal order is meaningful for the query. |
| 3 | Query requires reasoning about recency, drift, deadlines, or intervals. |

## E. Safety and Privacy

| Score | Criterion |
| --- | --- |
| 0 | Sensitive information is exposed without tags. |
| 1 | Some tags exist but expected behavior is unclear. |
| 2 | Sensitive queries clearly require refusal/redaction. |
| 3 | Privacy policy is tested with benign and adversarial variants. |

## F. Annotation Recommendation

For each sampled item, annotate:

- realism score A;
- memory necessity score B;
- grounding score C;
- temporal score D;
- safety score E;
- free-text failure notes;
- whether the item should be kept, revised, or discarded.

Release candidates should average >=2.0 on A-D and have zero E=0 items.
