# Evaluation Protocol

## Baseline Families

A credible paper should compare at least four families:

1. **No-memory baseline:** answer from current query/session only.
2. **Full-context baseline:** concatenate available trajectory when feasible.
3. **Retrieval baseline:** embed and retrieve top-k messages/events, then answer.
4. **Agent-memory system:** tested method with write/read/update policies.

## Streaming Evaluation Loop

For each trajectory:

1. Sort sessions by timestamp.
2. Feed each session to the system in order.
3. Allow the system to update its memory after each session.
4. At benchmark query time, freeze memory and ask the query.
5. Record answer, retrieved evidence IDs, refusal/abstention decision, latency, token cost, and memory size.

## Reporting

Report:

- overall score;
- macro score by capability;
- score by horizon bucket (near, medium, long, extreme);
- score by evidence count;
- privacy refusal precision/recall;
- cost/latency and memory footprint;
- ablations over retrieval, summarization, forgetting, and conflict-resolution modules.

## Error Taxonomy

Label failures as:

- missing write: evidence was never stored;
- retrieval miss: evidence stored but not retrieved;
- synthesis error: evidence retrieved but answer wrong;
- temporal confusion: old/new preference or date order mixed;
- over-disclosure: privacy-sensitive answer leaked;
- over-refusal: benign answer refused;
- hallucinated memory: unsupported claim;
- provenance failure: correct answer but unsupported evidence IDs.

## Statistical Treatment

Use bootstrap confidence intervals over personas, not raw queries, because queries from the same persona are correlated. For leaderboard reporting, include capability-balanced macro averages to prevent systems from overfitting common recall questions.
