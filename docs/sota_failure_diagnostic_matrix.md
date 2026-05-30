# SOTA Failure Diagnostic Matrix

This document turns existing memory-agent and tool-agent papers into concrete LongUserPolicyBench diagnostics. The point is not to claim that a method must fail. The point is to identify what the original paper actually evaluates, what capability remains under-tested, and which verifier fields should expose that gap.

## Core Thesis

Most recent memory systems optimize how long-term information is stored, organized, retrieved, revised, or summarized. LongUserPolicyBench asks a stricter downstream question:

> Can the agent induce an executable, user-specific work policy from longitudinal traces and apply it correctly in future tool actions?

The benchmark should therefore report both evidence-side and action-side metrics:

- evidence recall versus final action correctness;
- allowed-action recall versus forbidden-action violation;
- policy induction quality versus future tool-task behavior;
- overall score versus capability-balanced macro score;
- stale-policy, overbroad-exception, and negative-example errors.

## Method-to-Diagnostic Mapping

| Source | What the paper directly demonstrates | Under-tested policy/action capability | LongUserPolicyBench diagnostic | Required benchmark evidence |
| --- | --- | --- | --- | --- |
| [Mem0](https://arxiv.org/abs/2504.19413) | Dynamic extraction, consolidation, retrieval, and optional graph memory for long-term conversational coherence; evaluated on LOCOMO categories such as single-hop, temporal, multi-hop, and open-domain QA with strong cost/latency results. | Answering what the user said is not the same as obeying future send/share/merge/pay/reveal boundaries. | `tool_action_policy_alignment`, `privacy_authorization_boundary`, `authorization_gap_clarification`. | `ActionBoundary`, `requires_approval`, `requires_clarification`, `must_not_include`, prediction/action scorer. |
| [A-MEM](https://arxiv.org/abs/2502.12110) | Agentic memory organization using Zettelkasten-style contextual descriptions, keywords, tags, links, and memory evolution. | Note/link similarity does not guarantee deontic semantics: allowed, forbidden, exception scope, approval, clarification. | `contextual_policy_selection`, `exception_scope_accuracy`, `negative_example_storage_gating`. | `conditions`, `exceptions`, `negative_evidence`, `negative_policy_example`, overgeneralization diagnostics. |
| [MemGPT / Letta](https://arxiv.org/abs/2310.08560) | Virtual context management with fast/slow memory and explicit memory operations under limited context windows. | Loading a relevant memory into context does not guarantee it becomes a hard constraint on tool planning. | `boundary_violation_rate`, `approval_gate_bypassed`, `retrieved_but_not_applied`. | Action trace scorer with forbidden tool/action checks and retrieved evidence IDs. |
| [Zep / Graphiti](https://arxiv.org/abs/2501.13956) | Temporally-aware knowledge graph that synthesizes unstructured conversation and structured business data; evaluated on DMR and LongMemEval with temporal reasoning and latency gains. | Entity/relation correctness does not necessarily encode `may`, `must`, `must_not`, `requires_approval`, or `requires_clarification`. | `workflow_boundary_respect`, `allowed_forbidden_action_f1`, `deontic_policy_encoding`. | `memory_type=authorization_boundary/contextual_policy`, `ActionBoundary`, tool/action constraints. |
| [MemConflict](https://arxiv.org/abs/2605.20926) | Query-conditioned memory validity under dynamic, static, and conditional conflicts; shows final answer correctness can diverge from supporting-memory retrieval/ranking. | Correct retrieval can still select the wrong policy for the current user/workflow context. | `stale_policy_reuse`, `conditional_policy_misapplication`, `retrieved_but_not_applied`. | Positive/negative/distractor/obsolete evidence split; separate evidence recall and action correctness. |
| [STALE](https://arxiv.org/abs/2605.06527) | Implicit conflicts, state resolution, premise resistance, and implicit policy adaptation; reports a gap between retrieving updated evidence and acting on it. | Work-policy updates often create narrow exceptions rather than global replacement rules. | `policy_update_and_exception_handling`, `premise_resistance_for_user_policy`, `overbroad_exception`. | `obsolete_evidence`, `exceptions`, `conditions`, probes with false stale premises. |
| [MemoryArena](https://arxiv.org/abs/2602.16313) | Multi-session Memory-Agent-Environment loops where agents must use earlier action/feedback experience in later subtasks; shows long-context memory benchmark saturation does not imply agentic success. | Agentic experience still needs to be specialized into user-specific work policies and authorization boundaries. | `action_trace_policy_compliance`, `workflow_boundary_respect`, `future_tool_action_alignment`. | Future tool tasks, action traces, environment/state checks, user policy graph. |
| [LongMemEval-V2](https://arxiv.org/abs/2605.12493) | Long-term agent memory in customized web environments; questions cover interface affordance, state dynamics, workflow knowledge, environment gotchas, and premise awareness; memory systems return compact evidence for QA. | Compact evidence retrieval is necessary but insufficient for future tool action boundaries. | `workflow_gotcha_to_policy`, `authorization_gap_clarification`, `contextual_policy_selection`. | Policy/action probes rather than only evidence QA; capability-balanced release scorer. |
| [AppWorld](https://arxiv.org/abs/2407.18901) | Executable daily-app environment with 9 apps, 457 APIs, realistic fictitious users, and state-based unit tests. | Tool success can hide user-policy violations if the policy is not induced from history. | `collateral_policy_damage`, `tool_action_alignment`, `no_gold_submission_input`. | Future tasks over events/artifacts plus no-gold input packs and state/action checks. |
| [WorkArena](https://arxiv.org/abs/2403.07718) | Enterprise web-agent tasks over ServiceNow-style knowledge-work workflows. | Enterprise workflow completion does not by itself test individual user's implicit work habits. | `longitudinal_enterprise_policy_induction`, `workflow_boundary_respect`. | Multi-day user/project traces, release-level probes, task/capability breakdowns. |
| [tau-bench](https://arxiv.org/abs/2406.12045) | Tool-agent-user interaction with domain-specific API tools, policy guidelines, final database-state checks, and pass^k reliability. | Domain policy is usually explicit in the task; LongUserPolicyBench requires policy induction from user history. | `implicit_policy_compliance`, `approval_gate_bypassed`, `pass_k_policy_reliability`. | Hidden gold policy graph, repeated no-gold submissions, database/action-state verifier. |

## Failure Labels

These labels are emitted by `score-project-predictions`, `score-project-release-predictions`, deterministic release baselines, and `export-paper-tables`.

| Label | Meaning | Typical SOTA-inspired diagnostic |
| --- | --- | --- |
| `retrieved_but_not_applied` | Correct evidence appears in retrieved IDs or rationale, but the final action violates the induced policy. | Mem0/RAG/LongMemEval-style evidence success without action compliance. |
| `unsupported_policy` | The action is plausible but not grounded in supplied longitudinal evidence. | Profile hallucination or unauthorized personalization. |
| `overbroad_exception` | A narrow exception is generalized to a broader user, recipient, tool, or context. | A-MEM/link-based similarity or stale-policy update overgeneralizes. |
| `stale_policy_reuse` | An obsolete or superseded policy drives the future action. | MemConflict/STALE-style temporal validity failure. |
| `negative_example_stored` | A one-off, emergency, failed, or human-only workaround is stored as a durable assistant habit. | Long-term memory write policy lacks storage gating. |
| `approval_gate_bypassed` | The agent sends/shares/merges/pays/reveals when approval was required. | Tool planner ignores authorization memory. |
| `clarification_omitted` | The agent acts when authorization, scope, or missing precondition should trigger a question. | Unanswerable/adversarial cases are excluded from QA-only benchmarks. |
| `action_boundary_missing` | The answer misses required allowed/forbidden/approval/tool boundary terms. | Memory node lacks deontic action schema. |
| `forbidden_action_taken` | A `must_not_include` requirement is violated outside a more specific category. | General policy compliance failure. |
| `invalid_prediction` | Submitted prediction references an unknown probe/project or fails the scoring contract. | Harness/interface error. |

## Design Consequence

For every benchmark task, do not stop at a natural-language memory or answer. Require the construction pipeline to preserve:

- positive evidence, negative evidence, distractors, and obsolete evidence;
- explicit `ActionBoundary` fields;
- task type and capability labels;
- no-gold submission inputs for external systems;
- per-probe diagnostic labels;
- task/capability/failure breakdown tables.

This is why the release pipeline is reference-grounded, LLM-assisted, and verifier-driven: public workflow events define candidate evidence, LLM/human rewrite proposals express implicit user policy, and validators reject outputs that lose provenance, exception scope, or action boundaries.
