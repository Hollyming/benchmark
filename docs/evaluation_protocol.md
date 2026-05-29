# Evaluation Protocol

## Baseline Families

A credible paper should compare at least four families:

1. **No-memory baseline:** act from current query/session only.
2. **Full-context baseline:** concatenate available trajectory when feasible.
3. **Retrieval baseline:** retrieve top-k messages/events, then plan an action.
4. **User-policy memory system:** tested method with write/read/update policies.
5. **Oracle policy graph:** upper bound with gold policies and boundaries.

## Streaming Evaluation Loop

For each trajectory:

1. Sort sessions by timestamp.
2. Feed each session to the system in order.
3. Allow the system to update policy/habit memory after each session.
4. At future task time, freeze memory and ask the tool-policy probe.
5. Record action, rationale, retrieved evidence IDs, refusal/clarification decision, latency, token cost, and memory size.

## Reporting

Report:

- overall policy-action accuracy;
- macro score by capability;
- boundary violation rate for send/merge/pay/reveal/delete/share actions;
- exception-scope accuracy;
- negative-example suppression;
- clarification accuracy on missing authorization;
- score by horizon bucket and evidence count;
- cost/latency and memory footprint.

## Error Taxonomy

Label failures as:

- missing write: policy evidence was never stored;
- retrieval miss: policy evidence stored but not retrieved;
- action synthesis error: evidence retrieved but action wrong;
- overbroad exception: narrow exception applied globally;
- stale policy: older policy used after update;
- transient-as-habit: one-off example stored as durable habit;
- boundary violation: unauthorized send/merge/pay/reveal/delete/share;
- over-refusal: allowed action refused;
- unsupported authorization: permission inferred without evidence;
- evidence failure: correct action but unsupported evidence IDs.

## Statistical Treatment

Use bootstrap confidence intervals over users/workspaces, not raw probes, because probes from the same user are correlated. Include capability-balanced macro averages so systems cannot hide boundary failures behind easy policy cases.
