Read docs/codex_prompts/grounded_compresearchmem_handoff.md and implement this focused step only.

In E:/work/benchmark:
1. Refactor manual grounded pilot so its seed data is loaded from examples/manual_grounded_seed/project_manual_001.json instead of being entirely hardcoded.
2. Keep run_manual_grounded_pilot(output_dir) public API and generated output paths unchanged.
3. Add/adjust tests for seed loading and at least one verifier failure case.
4. Strengthen verifier with: (a) event artifacts required for non-synthetic/reference events, (b) probes with negative evidence must reference negative_evidence memories.
5. Update docs/comp_research_mem_alignment.md briefly.
6. Run: python -m ultra_long_benchmark.cli smoke --all; python -m ultra_long_benchmark.cli grounded-pilot; python -m ultra_long_benchmark.cli validate; python -m ultra_long_benchmark.cli audit --json --output examples/generated/audit_report.json; pytest -q

No commit, no push, no network data download.