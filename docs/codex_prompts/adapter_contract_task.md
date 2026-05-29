Read docs/codex_prompts/grounded_longuserpolicy_handoff.md first.

Task: implement the next small engineering step for source dataset adapters.

Context:
- Repo: E:/work/benchmark
- The grounded pilot now loads examples/manual_grounded_seed/project_manual_001.json and emits project-centric artifacts/events/memory_graph/probes.
- We want to prepare for pulling real datasets later, but do NOT download network data in this task.

Implement:
1. Add a lightweight adapter contract module, e.g. `ultra_long_benchmark/pipelines/source_adapters.py`, defining:
   - a simple adapter result dataclass or Pydantic model
   - `ManualSeedAdapter` that reads one manual seed JSON file and returns project profile + source artifacts + canonical events using existing models/functions where appropriate
   - clear docstrings explaining future adapters like SWE-bench/GitHub/arXiv can implement the same contract.
2. Refactor `grounded_pilot.py` to use `ManualSeedAdapter` instead of directly calling seed helpers if that is clean. Keep `run_manual_grounded_pilot(output_dir)` behavior unchanged.
3. Add tests for the adapter contract and ManualSeedAdapter.
4. Update docs/comp_research_mem_alignment.md with one short paragraph about adapter contract.
5. Run full verification:
   python -m ultra_long_benchmark.cli smoke --all
   python -m ultra_long_benchmark.cli grounded-pilot
   python -m ultra_long_benchmark.cli validate
   python -m ultra_long_benchmark.cli audit --json --output examples/generated/audit_report.json
   pytest -q

Constraints:
- Do not commit or push.
- Do not fetch/download external data.
- Keep deterministic offline behavior.
- Keep changes small and maintainable.

Final answer: summarize changed files and test results.
