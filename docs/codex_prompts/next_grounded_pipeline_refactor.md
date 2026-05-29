You are Codex working in `/home/jmzhang/Workspace/benchmark`.

Read `docs/codex_prompts/grounded_longuserpolicy_handoff.md` first. Then implement the next engineering step for LongUserPolicyBench.

Goal: extend the reference-grounded, LLM-assisted, verifier-driven pipeline for longitudinal user-policy and habit induction without breaking the deterministic smoke path.

Current context:
- The repo has a synthetic smoke pipeline and grounded pilots.
- Grounded pilots cover manual cross-tool workflow policies and a GitHub/CI policy fixture.
- Current CLI commands should continue to work:
  - `python -m ultra_long_benchmark.cli smoke --all`
  - `python -m ultra_long_benchmark.cli grounded-pilot`
  - `python -m ultra_long_benchmark.cli github-fixture-pilot`
  - `python -m ultra_long_benchmark.cli validate`
  - `python -m ultra_long_benchmark.cli audit --json --output examples/generated/audit_report.json`

Recommended next tasks:
1. Promote the GHArchive local adapter into a repo-level policy extraction stage.
2. Add an Enron/Avocado email adapter skeleton with strict license/privacy metadata handling.
3. Strengthen verifier checks from action-boundary field presence to action-level execution trace validation.
4. Add an oracle policy graph baseline and a raw-RAG baseline for policy-action probes.
