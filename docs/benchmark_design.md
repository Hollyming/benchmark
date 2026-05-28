# Benchmark Design

This benchmark treats memory as an evaluated system capability rather than an incidental context-window feature. The data construction path creates temporally extended event streams, converts them into multi-session trajectories, and asks queries whose answers require retrieving, resolving, refusing, or applying specific memories.

The motivating research position is **memory as a compositional experience model**: a long-running agent should construct, update, retrieve, and apply a versioned, provenance-aware, task-conditioned, and actionable model of experience from heterogeneous trajectories, rather than only recall facts from longer conversations.

For the full protocol, quality rubric, evaluation guidance, and reproducibility checklist, see `docs/benchmark_protocol.md`.

## Capability Taxonomy

- Episodic recall: identify a specific prior event among many similar sessions.
- Semantic consolidation: infer stable, durable user/project state from repeated or distributed evidence while retaining support and ignoring transient distractors.
- Preference learning: preserve durable preferences, distinguish them from one-off side requests, and detect preference drift.
- Temporal reasoning: answer with correct ordering, deadlines, recency, and supersession.
- Provenance use: cite or condition on source events and source documents, including supersession or contradiction relationships.
- Conflict resolution: handle contradictions, corrections, and changing goals.
- Privacy refusal: avoid exposing private identifiers or unsafe memory content.
- Long-horizon planning: use commitments, deferred callbacks, milestones, and goals spanning weeks or months.
- Abstention: say when the memory evidence is insufficient rather than filling gaps with plausible but unsupported facts.

The taxonomy is intended for stratified reporting. Aggregate scores should not be used alone because an agent can perform well on direct recall while failing privacy, abstention, or stale-memory cases.

## Construction Contract

Each stage emits typed JSONL/JSON artifacts and should be replaceable by a stronger implementation without changing downstream schemas. The smoke implementation uses synthetic data to make CI and peer review reproducible.

Replacement implementations must preserve stable IDs, provenance links, privacy tags, timestamp semantics, and query evidence links. Any release that uses public data or LLM generation should include a separate QC and audit report so reviewers can distinguish method changes from dataset changes.

## Trajectory Complexity Contract

Top-tier agent-memory evaluation should stress memory lifecycle management, not only clean retrieval. Trajectories should therefore include:

- Distractor sessions with no durable memory target.
- Multi-event sessions where several memories are introduced together.
- Delayed callbacks that require carrying commitments forward across sessions.
- Topic switching within a session, so transient requests are not over-consolidated.
- Contradictory updates where newer or higher-authority evidence supersedes stale memories.

The smoke generator now emits compact deterministic examples of each stressor and records them in `trajectory.metadata.complexity_features`; paper-scale releases should report these features by split.

## Compositional Experience Memory Contract

Following the benchmark proposal in the Feishu design document, the target object is:

```text
Memory = Causal + Versioned + Provenance-aware + Task-conditioned + Actionable Experience State
```

The smoke data therefore includes compact hooks for the following paper-facing tasks:

- Research thread resumption: recover project state and next actions from long-horizon goals and deferred commitments.
- Failure-aware experiment planning: reuse procedural failure lessons, such as OOM-causing configurations and validated alternatives.
- Versioned claim tracking: distinguish current beliefs from superseded preferences or invalidated results.
- Provenance-constrained writing/use: cite event IDs and suppress unsupported or invalid sources.
- Cross-source evidence composition: infer stable project state from multiple evidence events while ignoring distractors.
- Task-conditioned personalized storage: store durable user/project preferences while rejecting transient side requests.
- Multi-role constraint resolution: keep user, collaborator, reviewer, tool, and environment constraints separate.
- Obsolete/negative evidence suppression: identify evidence that is semantically related but not currently usable.
- Long-horizon aggregated reasoning under interference: answer across multiple sessions despite intervening updates.

Generated queries expose `memory_task`, positive evidence, and optional `negative_evidence_event_ids`, `obsolete_evidence_event_ids`, and `distractor_event_ids` so retrieval quality and final-answer quality can be analyzed separately.
