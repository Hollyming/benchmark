# GHArchive Staging Protocol

This protocol prepares real public GitHub workflow slices for LongUserPolicyBench without turning the benchmark into a pure LLM-generated dataset.

## Source

Primary source: GH Archive public GitHub event stream, staged outside the committed repository. The current adapter accepts local `.jsonl`, `.json`, and `.json.gz` files containing GitHub event rows. `gharchive-build-slice` can also scan a directory of staged hourly files and emit one filtered JSONL slice plus a manifest. Network download is intentionally not part of the default offline pipeline.

Recommended staging locations:

- `/home/jmzhang/Workspace/data/gharchive/<yyyy-mm>/`
- `/data1/public/gharchive/<yyyy-mm-dd>/`
- `/data1/public/hf/` only if an already mirrored GHArchive-style dataset exists.
- A project-local temporary path only for small reviewed samples, not for large raw data releases.

## Minimum Raw Slice Requirements

Each candidate slice should contain enough evidence for at least one repository:

- Pull request open/close events.
- Issue or PR comments that show review routing or summary behavior.
- PR review events or reviewer mentions.
- Execution-boundary events, preferably CI/workflow/status, and otherwise PR closed/merged/revert/blocked signals that constrain future agent actions.
- At least one negative or exception-like boundary signal, such as do-not-merge, blocked, failed CI, revert, hold/approval, or emergency human pre-CI merge text.
- Multiple days or windows when making longitudinal claims.

The current quality gate requires PR/comment, review, execution-boundary, and negative-boundary evidence before emitting a repo-level policy pack. CI/status/workflow events are the strongest execution-boundary subtype, but public GHArchive hourly samples often expose PR closed/merged or blocked/revert language without aligned CI events. Emergency pre-CI text is still preserved as a stronger negative subtype for storage-gating examples, but real GHArchive mining no longer requires every eligible repository to contain that exact phrase.

## License and Privacy Notes

GHArchive data is public GitHub event data, but release artifacts must still avoid republishing unnecessary raw payloads. Release packs should include event IDs, raw pointers, content hashes, selected snippets, and derived policy tasks. If full raw slices are redistributed, record the source URI, collection time, and applicable GitHub/GHArchive terms in the release manifest.

Do not mix private repository data, private issue exports, user email corpora, or browser histories into GHArchive release directories.

## Offline Commands After Staging

```bash
python -m ultra_long_benchmark.cli discover-public-data --root /home/jmzhang/Workspace/data --output examples/generated/public_data_discovery_report.json
python -m ultra_long_benchmark.cli verify-public-data-discovery examples/generated/public_data_discovery_report.json
python -m ultra_long_benchmark.cli gharchive-rank-repos --input /home/jmzhang/Workspace/data/gharchive/2024-01 --output examples/generated/gharchive_repo_rank_report.json --limit 200 --min-events 5
python -m ultra_long_benchmark.cli gharchive-build-slice /home/jmzhang/Workspace/data/gharchive/2024-01 --output /home/jmzhang/Workspace/data/gharchive/longuserpolicy_slice.jsonl --manifest /home/jmzhang/Workspace/data/gharchive/longuserpolicy_slice_manifest.json --max-records 200000 --max-records-per-source-file 4000
python -m ultra_long_benchmark.cli gharchive-quality-report --input /home/jmzhang/Workspace/data/gharchive/longuserpolicy_slice.jsonl --output examples/generated/gharchive_quality_report.json
python -m ultra_long_benchmark.cli gharchive-window-report --input /home/jmzhang/Workspace/data/gharchive/longuserpolicy_slice.jsonl --window-days 7 --output examples/generated/gharchive_window_report.json
python -m ultra_long_benchmark.cli gharchive-stage-plan --input /home/jmzhang/Workspace/data/gharchive/longuserpolicy_slice.jsonl --profile paper --window-days 7 --output examples/generated/gharchive_stage_plan.json --allow-fail
python -m ultra_long_benchmark.cli audit-workflow-data-sources --discovery-report examples/generated/public_data_discovery_report.json --gharchive-stage-plan examples/generated/gharchive_stage_plan.json --output examples/generated/workflow_data_source_audit.json
INPUT=/home/jmzhang/Workspace/data/gharchive/longuserpolicy_slice.jsonl OUTPUT_ROOT=examples/generated bash scripts/run_gharchive_annotation_pipeline.sh
python -m ultra_long_benchmark.cli verify-release-integrity examples/generated/release_packaging/gharchive_formal_annotation_pack --prompt-export-dir examples/generated/annotation_packs/gharchive_formal_prompt_exports --output examples/generated/release_integrity_report.json
python -m ultra_long_benchmark.cli assess-paper-scale examples/generated/release_packaging/gharchive_formal_annotation_pack --profile paper --scale-summary examples/generated/gharchive_formal_scale_summary.json --window-report examples/generated/gharchive_window_report.json --release-integrity-report examples/generated/release_integrity_report.json --output examples/generated/paper_scale_assessment.json --allow-fail
```

`gharchive-build-slice` supports repeated `--repo owner/name`, `--max-records`, `--max-records-per-repo`, `--max-records-per-source-file`, and `--require-eligible-repo`. For hourly GHArchive directories, prefer `--max-records-per-source-file` over only `--max-records`; otherwise the slice may overrepresent the earliest sorted hours. The manifest records source files, selected record counts, repo counts, event-type counts, eligible repos, skipped repos, and the fact that no network download or LLM generation was performed.

`gharchive-rank-repos` is the bridge from broad raw GHArchive hourly files to a useful benchmark slice. It scans raw files with streaming event-signal counts, ranks repositories by PR/comment, review, execution boundary, merge, actor, and negative-boundary signals, and emits recommended repos for a focused `gharchive-build-slice --repo ...` run. Broad random hourly sampling can produce many weak candidates but no repository with complete longitudinal policy evidence.

`gharchive-stage-plan` is the raw-slice preflight before any LLM-assisted rewrite work. It reuses the repo quality report, time-window report, and deterministic policy candidate miner to compare the staged slice against `fixture`, `pilot`, or `paper` thresholds. It reports eligible repositories, source events, candidate types, eligible windows, longitudinal span gaps, skipped repo reasons, and recommended next actions. Use `--allow-fail` for exploratory slices so the JSON report is written even when paper-scale thresholds are not yet met.

The stage-plan JSON includes a `decision` block. For `profile=paper`, `decision.ready_for_annotation_budget=true` only when all raw-slice checks pass. If it is false, do not spend LLM/API or human annotation budget yet; expand or rebalance the GHArchive slice first. `fixture` profile is explicitly marked as `engineering_fixture`, even when checks pass.

`audit-workflow-data-sources` combines public-data discovery with the GHArchive stage-plan decision. It fails when no local GHArchive workflow event source exists, warns when only GitHub code-text corpora are present, and treats email corpora as unusable until a reviewed manifest declares redistribution permission, privacy review pass, and PII redaction. With `--require-paper-ready`, a non-ready stage plan becomes a blocking source-readiness failure.

On Slurm:

```bash
sbatch --export=ALL,INPUT=/home/jmzhang/Workspace/data/gharchive/2024-01,SLICE_OUTPUT=/home/jmzhang/Workspace/data/gharchive/longuserpolicy_slice.jsonl,OUTPUT_ROOT=/home/jmzhang/Workspace/benchmark/examples/generated,MAX_RECORDS=200000 scripts/slurm/prepare_gharchive_slice.sbatch
sbatch --export=ALL,INPUT=/home/jmzhang/Workspace/data/gharchive/longuserpolicy_slice.jsonl,OUTPUT_ROOT=/home/jmzhang/Workspace/benchmark/examples/generated scripts/slurm/run_gharchive_annotation_pipeline.sbatch
```

## Scale Report Gate

A staged slice is paper-useful only if `gharchive-scale-summary` reports:

- Multiple eligible repositories or a documented single-repo longitudinal study.
- Nonzero authorization-boundary and negative-policy candidates.
- Repo-disjoint split files from `export-annotation-pack-release`.
- Pack hashes and explicit `llm_generation_allowed=false` constraints.
- `verify-release-integrity` has zero blocking issues. Empty dev/test splits are acceptable only for engineering fixtures, not for benchmark-scale claims.
- `assess-paper-scale --profile paper` passes before main-experiment reporting. If it fails, inspect `recommended_next_actions` and keep the slice as a fixture or pilot.
- `gharchive-stage-plan --profile paper` should already have no blocking raw-slice gaps before spending LLM/human annotation budget.

If the slice fails these gates, keep it as an engineering fixture rather than a benchmark release.
