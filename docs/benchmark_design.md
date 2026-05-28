# Benchmark Design

This benchmark treats memory as an evaluated system capability rather than an incidental context-window feature. The data construction path creates temporally extended event streams, converts them into multi-session trajectories, and asks queries whose answers require retrieving, resolving, or refusing to use specific memories.

For the full protocol, quality rubric, evaluation guidance, and reproducibility checklist, see `docs/benchmark_protocol.md`.

## Capability Taxonomy

- Episodic recall: identify a specific prior event among many similar sessions.
- Semantic consolidation: infer stable facts from repeated events without losing provenance.
- Preference learning: preserve durable preferences and detect preference drift.
- Temporal reasoning: answer with correct ordering, deadlines, recency, and supersession.
- Provenance use: cite or condition on source events and source documents.
- Conflict resolution: handle contradictions and changing goals.
- Privacy refusal: avoid exposing private identifiers or unsafe memory content.
- Long-horizon planning: use commitments and goals spanning weeks or months.
- Abstention: say when the memory evidence is insufficient.

The taxonomy is intended for stratified reporting. Aggregate scores should not be used alone because an agent can perform well on direct recall while failing privacy, abstention, or stale-memory cases.

## Construction Contract

Each stage emits typed JSONL/JSON artifacts and should be replaceable by a stronger implementation without changing downstream schemas. The smoke implementation uses synthetic data to make CI and peer review reproducible.

Replacement implementations must preserve stable IDs, provenance links, privacy tags, timestamp semantics, and query evidence links. Any release that uses public data or LLM generation should include a separate QC and audit report so reviewers can distinguish method changes from dataset changes.
