# Longitudinal User Policy Benchmark Workspace Brief

Owner goal: build top-tier-paper-quality data construction pipelines for evaluating whether tool-using agents can learn a user's implicit work policies, habits, routines, boundaries, and context-dependent exceptions from longitudinal workflow traces.

Working directory: `/home/jmzhang/Workspace/benchmark`

High-level research target:

- Construct longitudinal, multi-tool user workflow trajectories for agent evaluation.
- Emphasize future tool actions conditioned on how this user works, not long-context fact QA.
- Cover email, calendar, docs, chat, issues, PRs, browser, files, forms, code, and tool outputs.
- Use reference-grounded, LLM-assisted, verifier-driven data construction.
- Produce reproducible schemas, quality controls, evaluation hooks, and grounded pilots suitable for a strong systems/ML/NLP paper.

Core innovation:

```text
Memory as User Policy = Habit Induction + Contextual Exceptions + Tool Boundaries + Authorization Scope + Negative Examples + Future Action Alignment
```

Required abilities:

- implicit user-policy induction
- cross-day habit generalization
- contextual policy selection
- tool-action alignment
- workflow boundary respect
- policy update and exception handling
- proactive routine recognition
- privacy and authorization boundary handling
- habit storage gating
- clarification when authorization is missing

Task blocks:

1. `literature_and_taxonomy`: maintain paper seeds and policy/habit capability taxonomy.
2. `seed_corpora_ingestion`: normalize public/local source artifacts.
3. `persona_life_event_simulation`: synthesize or ingest longitudinal user workflow timelines.
4. `multi_session_agent_trajectory_generation`: build multi-session user/tool traces.
5. `memory_challenge_query_generation`: generate future tool-policy probes.
6. `annotation_and_quality_control`: automatic checks plus human annotation templates.
7. `evaluation_harness`: evaluate policy action accuracy, boundary violations, clarification, and evidence use.
8. `release_packaging`: dataset card, benchmark card, license/provenance manifest, splits.

Quality bar:

- Professional, reproducible, modular, typed Python.
- No hidden API key assumptions.
- Every task has an offline smoke path.
- Use schemas and validation everywhere.
- Preserve provenance and policy evidence links.
- LLMs may bridge, rewrite, and synthesize probes, but must not be the source of gold policy facts.
