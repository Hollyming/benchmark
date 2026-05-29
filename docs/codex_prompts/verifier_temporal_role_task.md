Read docs/codex_prompts/grounded_longuserpolicy_handoff.md first.

Task: strengthen verifier with temporal/role checks in the grounded benchmark pipeline.

Context:
- Repo: E:/work/benchmark
- Current tests pass.
- Existing verifier: ultra_long_benchmark/pipelines/verifier.py
- Existing grounded projects: manual grounded pilot and GitHub issue/CI fixture pilot.

Implement a small deterministic improvement:
1. In verifier.py, add role attribution coverage check for probes whose task_type or capabilities mention multi_role/role_attribution/constraint_resolution. Such probes should have positive memories whose source events include at least two distinct actors in the canonical events.
2. In verifier.py, add temporal relation sanity for event causal_links/supersedes: every referenced event id must exist and should not point to a later timestamp than the event that references it. Keep invalidates behavior as-is for claim/event targets.
3. Add tests for passing current projects and at least one broken role/temporal case.
4. Keep all existing CLI behavior and generated artifacts compatible.
5. Run:
   python -m ultra_long_benchmark.cli smoke --all
   python -m ultra_long_benchmark.cli grounded-pilot
   python -m ultra_long_benchmark.cli github-fixture-pilot
   python -m ultra_long_benchmark.cli validate
   python -m ultra_long_benchmark.cli audit --json --output examples/generated/audit_report.json
   pytest -q

Constraints:
- Do not commit or push.
- No network downloads.
- Keep changes focused.

Final response: changed files and test results.
