You are Codex working in E:/work/benchmark.

Read `docs/codex_prompts/grounded_compresearchmem_handoff.md` first. Then implement the next engineering step for CompResearchMem.

Goal: refactor the current manual reference-grounded pilot into a more modular, dataset-adapter-ready pipeline without breaking the deterministic smoke path.

Current context:
- The repo has a synthetic smoke pipeline and a manual grounded pilot.
- Recent models include SourceArtifact, CanonicalEvent, ProjectProfile, MemoryGraph, Probe, VerifierReport.
- Current CLI commands should continue to work:
  - `python -m ultra_long_benchmark.cli smoke --all`
  - `python -m ultra_long_benchmark.cli grounded-pilot`
  - `python -m ultra_long_benchmark.cli validate`
  - `python -m ultra_long_benchmark.cli audit --json --output examples/generated/audit_report.json`
  - `pytest -q`

Task requirements:
1. Split `ultra_long_benchmark/pipelines/grounded_pilot.py` into composable pure functions or lightweight modules/stages that mirror:
   - manual seed adapter
   - canonical event conversion
   - project binding
   - memory graph builder
   - probe synthesizer
   - project writer
   Keep the public function `run_manual_grounded_pilot(output_dir: Path)` intact.
2. Add a small manually authored seed file under `examples/manual_grounded_seed/` and make the manual seed adapter read it, rather than having all data hardcoded only in Python. Keep tests deterministic and offline. Do not fetch network data.
3. Preserve the existing generated output structure:
   `examples/generated/projects/project_manual_001/{project_profile.json, source_manifest.json, artifacts.jsonl, events.jsonl, memory_graph.json, probes.jsonl, verifier_report.json}`.
4. Strengthen verifier with at least two additional rule checks from this list:
   - invalidates references a known claim or event
   - event artifacts are non-empty for reference-grounded source events
   - active/non-distractor memories must have source_events
   - probes with negative evidence must use memory nodes of type `negative_evidence` or with negative_evidence populated
   - role attribution coverage for multi-role probes
5. Add/update tests for the new seed adapter and verifier behavior, including at least one broken-project negative test.
6. Update docs briefly, ideally `docs/comp_research_mem_alignment.md` or a new small doc, to explain the new modular grounded pilot flow.

Constraints:
- Do not commit changes.
- Do not push.
- Do not introduce required network/API dependencies.
- Keep code simple and maintainable.
- Prefer small functions over large monoliths.

Verification before final response:
Run:
```bash
python -m ultra_long_benchmark.cli smoke --all
python -m ultra_long_benchmark.cli grounded-pilot
python -m ultra_long_benchmark.cli validate
python -m ultra_long_benchmark.cli audit --json --output examples/generated/audit_report.json
pytest -q
```

Final response should summarize changed files, tests run, and any caveats.
