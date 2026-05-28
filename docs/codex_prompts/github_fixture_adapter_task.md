Read docs/codex_prompts/grounded_compresearchmem_handoff.md first.

Task: implement a deterministic local GitHub/SWE-like adapter scaffold using checked-in fixture data. Do not download network data.

Context:
- Repo: E:/work/benchmark
- Existing source adapter contract: ultra_long_benchmark/pipelines/source_adapters.py with AdapterResult and ManualSeedAdapter.
- Existing grounded pilot and verifier pass.

Implement:
1. Add a small fixture under examples/source_fixtures/github_issue_ci/project_github_001.json (or similar). It should represent a GitHub issue + CI log + patch/review style source stream for failure-aware experiment planning and negative evidence suppression.
2. Extend source_adapters.py with GitHubIssueCIAdapter (name can vary) that reads this fixture and emits AdapterResult using ProjectProfile, SourceArtifact, CanonicalEvent. It should not access network.
3. Add a CLI command if simple, e.g. `python -m ultra_long_benchmark.cli github-fixture-pilot`, that writes project-centric output under examples/generated/projects/project_github_001 and runs verifier. If too much, expose a function and tests only.
4. Add tests for the adapter and generated project verifier. Include at least one event with invalidates and one failure/recovery pair.
5. Update docs/comp_research_mem_alignment.md briefly describing this fixture adapter as the first real-dataset-shaped adapter.
6. Run full verification:
   python -m ultra_long_benchmark.cli smoke --all
   python -m ultra_long_benchmark.cli grounded-pilot
   python -m ultra_long_benchmark.cli validate
   python -m ultra_long_benchmark.cli audit --json --output examples/generated/audit_report.json
   pytest -q

Constraints:
- No external downloads/network.
- Do not commit or push.
- Keep changes small, deterministic, and compatible with existing tests.

Final response: changed files and test results.