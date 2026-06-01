# Public Data and LLM Extensions

The formal benchmark path is source-first and release-gated. To extend it:

1. Stage reviewed public data outside the committed repository.
2. Convert each source into a reviewed workflow manifest or a domain-specific public-event adapter.
3. Require license, redistribution, privacy, and provenance checks before project construction.
4. Export verifier-checked projects, no-gold submission inputs, deterministic baselines, and release-gate artifacts.
5. Use provider calls only for rewrite/probe proposal generation, then accept outputs only after validation and verifier gates.

For email corpora such as Enron or Avocado, use `EmailWorkflowAdapter` with a manifest-first workflow. The manifest must declare `dataset_name`, `source_dataset`, `license`, `redistribution.allowed=true`, `privacy_review.status=passed`, `privacy_review.pii_redaction=true`, `project_id`, and reviewed records. The adapter rejects unknown-license, non-redistributable, or unreviewed email data before loading records.

For future calendar, docs, chat, and browser/web-search traces, use `WorkflowManifestAdapter`. Its manifest adds `domain` with one of `calendar_workflow`, `docs_workflow`, `chat_workflow`, or `browser_web_workflow`, and uses the same license/redistribution/privacy-review gate before records are normalized. Passing this adapter only proves safe trace normalization; each domain still needs release, readiness, and artifact gates before release claims.

Validate a reviewed manifest before building any domain project:

```bash
python -m ultra_long_benchmark.cli validate-workflow-manifest /path/to/workflow_manifest.json --output examples/generated/workflow_manifest_validation.json
```

The validation report records adapter type, domain, manifest hash, normalized artifact/event counts, and privacy-tag counts without exporting raw content. It is a source-adapter contract check, not a release-readiness claim.

After the manifest has reviewed records plus reviewed `memory_graph` and `probes`, build a verifier-checked project without LLM/API generation:

```bash
python -m ultra_long_benchmark.cli build-project-from-workflow-manifest /path/to/workflow_manifest.json --output-dir examples/generated/projects --report examples/generated/workflow_manifest_project_report.json
python -m ultra_long_benchmark.cli export-project-benchmark-release examples/generated/projects/<project_id> --output-dir examples/generated/release_packaging/workflow_manifest_project_benchmark
python -m ultra_long_benchmark.cli export-project-submission-inputs examples/generated/release_packaging/workflow_manifest_project_benchmark --output-dir examples/generated/evaluation_harness/workflow_manifest_submission_inputs
```

`build-project-from-workflow-manifest` is a no-generation bridge: it refuses manifests without a supplied `memory_graph` and `probes`, writes redacted project files by default, runs `verify-project`, and marks `release_ready_claim=false`. A real non-GitHub domain still needs reusable traces, source audit coverage, taxonomy/claim-boundary support, baseline reports, readiness, and artifact gates before paper claims can include it.

To run the whole offline bridge in one preflight command:

```bash
python -m ultra_long_benchmark.cli preflight-workflow-manifest-release /path/to/workflow_manifest.json --output-dir examples/generated/workflow_manifest_preflight --harden-probe-queries
python -m ultra_long_benchmark.cli verify-workflow-manifest-preflight examples/generated/workflow_manifest_preflight/workflow_manifest_release_preflight.json
```

The preflight writes a verifier-checked project, project benchmark release, no-gold submission input pack, deterministic baseline report, taxonomy coverage audit, probe-leakage audits, and artifact hashes under the output directory. `verify-workflow-manifest-preflight` recomputes those hashes so drift in any generated project/release/input/report artifact is caught. This is still not a benchmark release gate by itself; use it to prove the manifest is structurally ready before adding source-audit, claim-boundary, readiness, and artifact-bundle integration.

Checked-in project-ready fixtures exist for the offline bridge across `calendar_workflow`, `docs_workflow`, `chat_workflow`, and `browser_web_workflow`:

```bash
for domain in calendar docs chat browser_web; do
  python -m ultra_long_benchmark.cli preflight-workflow-manifest-release \
    tests/fixtures/${domain}_workflow_project_manifest.json \
    --output-dir examples/generated/workflow_manifest_preflight/${domain} \
    --report examples/generated/workflow_manifest_preflight/${domain}/workflow_manifest_release_preflight.json \
    --baseline oracle_policy_graph \
    --harden-probe-queries
done
```

Those fixtures prove adapter/project/release/no-gold/baseline mechanics for planned domains. They are not reusable public corpora and must not be promoted into release claims.

For multiple reviewed manifests, the batch command writes one preflight report per manifest plus a hash-backed batch summary:

```bash
python -m ultra_long_benchmark.cli preflight-workflow-manifest-release-batch \
  tests/fixtures/calendar_workflow_project_manifest.json \
  tests/fixtures/docs_workflow_project_manifest.json \
  tests/fixtures/chat_workflow_project_manifest.json \
  tests/fixtures/browser_web_workflow_project_manifest.json \
  --output-dir examples/generated/workflow_manifest_preflight_batch \
  --report examples/generated/workflow_manifest_preflight_batch/workflow_manifest_preflight_batch_report.json \
  --baseline oracle_policy_graph \
  --harden-probe-queries

python -m ultra_long_benchmark.cli verify-workflow-manifest-preflight-batch \
  examples/generated/workflow_manifest_preflight_batch/workflow_manifest_preflight_batch_report.json
```

`scripts/run_workflow_manifest_preflight_batch.sh` and `scripts/slurm/run_workflow_manifest_preflight_batch.sbatch` wrap the same flow. Set `MANIFESTS` to a whitespace-separated list of reviewed manifest paths for staged data; the default script input is only the checked-in fixture set.

Optionally pass the preflight report into the domain-expansion audit to record that a domain has passed local scaffolding while still blocking paper claims:

```bash
python -m ultra_long_benchmark.cli audit-domain-expansion-readiness \
  --workflow-manifest-preflight examples/generated/workflow_manifest_preflight/workflow_manifest_release_preflight.json \
  --output examples/generated/evaluation_harness/domain_expansion_with_preflight.json

python -m ultra_long_benchmark.cli benchmark-release-gate-report \
  --workflow-manifest-preflight examples/generated/workflow_manifest_preflight/workflow_manifest_release_preflight.json \
  --report domain_expansion_readiness=examples/generated/evaluation_harness/domain_expansion_with_preflight.json \
  --output examples/generated/evaluation_harness/gate_with_workflow_preflight.json
```

For batch reports, pass the batch directly; domain expansion and the paper gate expand it internally:

```bash
python -m ultra_long_benchmark.cli audit-domain-expansion-readiness \
  --workflow-manifest-preflight-batch examples/generated/workflow_manifest_preflight_batch/workflow_manifest_preflight_batch_report.json \
  --output examples/generated/evaluation_harness/domain_expansion_with_preflight_batch.json

python -m ultra_long_benchmark.cli benchmark-release-gate-report \
  --workflow-manifest-preflight-batch examples/generated/workflow_manifest_preflight_batch/workflow_manifest_preflight_batch_report.json \
  --report domain_expansion_readiness=examples/generated/evaluation_harness/domain_expansion_with_preflight_batch.json \
  --output examples/generated/evaluation_harness/gate_with_workflow_preflight_batch.json
```

This records preflight report hashes under `inputs.workflow_manifest_preflight_*` and batch hashes under `inputs.workflow_manifest_preflight_batch_*`, live-verifies all preflight artifact hashes, and marks each domain roadmap as `workflow_manifest_preflight_passed_gate_integration_missing` until the benchmark release source audit, claim-boundary, readiness, and artifact gates include that domain. If any preflight project/release/input/report artifact drifts, domain expansion records `workflow_manifest_preflight_not_passed` and does not list the domain under `preflight_ready_domains`. `verify-domain-expansion-readiness` re-runs the preflight and batch verifiers, so artifact drift after domain-expansion report generation is also caught. The benchmark release gate accepts optional preflight or preflight-batch inputs only if domain expansion recorded the domains as preflight-ready and the verifiers still pass; it still keeps `release_ready_claim=false` and does not expand the current GHArchive release scope.

Before relying on local shared storage, write an auditable discovery report:

```bash
python -m ultra_long_benchmark.cli discover-public-data --root /home/jmzhang/Workspace/data --output examples/generated/public_data_discovery_report.json
python -m ultra_long_benchmark.cli verify-public-data-discovery examples/generated/public_data_discovery_report.json
```

The discovery report records byte counts and SHA-256 digests for every candidate file. Re-run `verify-public-data-discovery` before using a cached report so changed or missing source files cannot silently pass into source audit.

The prior `/data1/public` scan found no directly usable GHArchive workflow event source and no approved Enron/Avocado-style email manifest. It found GitHub code-text samples under `/data1/public/hf/togethercomputer/RedPajama-Data-1T-Sample/`, but those are not longitudinal user workflow traces and should not be used as substitutes for PR/review/CI event timelines. The active staging path for new public data is `/home/jmzhang/Workspace/data`.

For GHArchive, use the deterministic bridge before any provider call:

```bash
python -m ultra_long_benchmark.cli gharchive-build-slice /path/to/gharchive_dir --output /path/to/longuserpolicy_slice.jsonl --manifest /path/to/longuserpolicy_slice_manifest.json --max-records 200000 --max-records-per-source-file 4000
python -m ultra_long_benchmark.cli gharchive-rank-repos --input /path/to/gharchive_dir --output examples/generated/gharchive_repo_rank_report.json --limit 200 --min-events 5
INPUT=/path/to/gharchive.jsonl OUTPUT_ROOT=examples/generated bash scripts/prepare_gharchive_slice.sh
python -m ultra_long_benchmark.cli gharchive-mine-candidates --input <local-gharchive.jsonl> --repo owner/repo --output examples/generated/gharchive_candidate_report.json
python -m ultra_long_benchmark.cli gharchive-annotation-pack --input <local-gharchive.jsonl> --repo owner/repo --output-dir examples/generated/annotation_packs/gharchive_policy
python -m ultra_long_benchmark.cli gharchive-annotation-pack-batch --input <local-gharchive.jsonl> --output-dir examples/generated/annotation_packs/gharchive_formal
python -m ultra_long_benchmark.cli export-annotation-pack-release examples/generated/annotation_packs/gharchive_formal --output-dir examples/generated/release_packaging/gharchive_formal_annotation_pack
python -m ultra_long_benchmark.cli gharchive-scale-summary examples/generated/annotation_packs/gharchive_formal --release-dir examples/generated/release_packaging/gharchive_formal_annotation_pack --output examples/generated/gharchive_formal_scale_summary.json
python -m ultra_long_benchmark.cli audit-workflow-data-sources --discovery-report examples/generated/public_data_discovery_report.json --gharchive-stage-plan examples/generated/gharchive_stage_plan.json --output examples/generated/workflow_data_source_audit.json
python -m ultra_long_benchmark.cli export-policy-rewrite-prompts examples/generated/annotation_packs/gharchive_policy/annotation_pack.json --output examples/generated/annotation_packs/gharchive_policy/rewrite_prompts.jsonl
python -m ultra_long_benchmark.cli export-policy-rewrite-prompts-batch examples/generated/annotation_packs/gharchive_formal --output-dir examples/generated/annotation_packs/gharchive_formal_prompt_exports
python -m ultra_long_benchmark.cli package-policy-rewrite-jobs examples/generated/annotation_packs/gharchive_formal_prompt_exports --output-dir examples/generated/annotation_packs/gharchive_formal_rewrite_jobs --max-prompts-per-job 100
python -m ultra_long_benchmark.cli collect-policy-rewrite-job-outputs examples/generated/annotation_packs/gharchive_formal_rewrite_jobs --output examples/generated/annotation_packs/gharchive_formal_rewrite_jobs/collected_rewrite_proposals.jsonl --report examples/generated/annotation_packs/gharchive_formal_rewrite_jobs/rewrite_job_collection_report.json
python -m ultra_long_benchmark.cli validate-policy-rewrites-batch examples/generated/annotation_packs/gharchive_formal examples/generated/annotation_packs/gharchive_formal_rewrite_jobs/collected_rewrite_proposals.jsonl --output-dir examples/generated/annotation_packs/gharchive_formal_validation
python -m ultra_long_benchmark.cli build-projects-from-rewrite-batch examples/generated/annotation_packs/gharchive_formal_validation/batch_rewrite_validation_report.json --output-dir examples/generated/projects/gharchive_formal_batch --project-prefix project_gharchive_formal
python -m ultra_long_benchmark.cli export-project-benchmark-release examples/generated/projects/gharchive_formal_batch/project_gharchive_formal_* --output-dir examples/generated/release_packaging/gharchive_formal_project_benchmark --dataset-name longuserpolicy_gharchive_project_benchmark --copy-projects --llm-generated --construction gharchive_rewrite_validated_policy_project
python -m ultra_long_benchmark.cli verify-project-benchmark-release examples/generated/release_packaging/gharchive_formal_project_benchmark --output examples/generated/release_packaging/gharchive_formal_project_benchmark/project_release_verify_report.json
python -m ultra_long_benchmark.cli verify-release-integrity examples/generated/release_packaging/gharchive_formal_annotation_pack --prompt-export-dir examples/generated/annotation_packs/gharchive_formal_prompt_exports --output examples/generated/release_integrity_report.json
python -m ultra_long_benchmark.cli assess-paper-scale examples/generated/release_packaging/gharchive_formal_annotation_pack --profile paper --scale-summary examples/generated/gharchive_formal_scale_summary.json --window-report examples/generated/gharchive_window_report.json --release-integrity-report examples/generated/release_integrity_report.json --output examples/generated/paper_scale_assessment.json --allow-fail
```

The annotation pack contains source snippets, event ids, content hashes, action-boundary candidates, LLM instructions, and verifier expectations. `export-policy-rewrite-prompts` turns it into provider-agnostic prompt records without calling any model. LLMs may rewrite policy text or draft future probes from the pack, but must not invent supporting events or broaden the supplied action boundary.

`package-policy-rewrite-jobs` shards prompt exports into annotation handoff jobs without calling any model. Each job contains `prompts.jsonl`, an empty `proposals_template.jsonl`, a `job_manifest.json`, candidate-type counts, estimated token budget, and validation command templates. Treat this as the boundary where work pauses for LLM/API credentials or human annotation.

`collect-policy-rewrite-job-outputs` is the no-provider return path after annotation. It expects each job to contain a completed `proposals.jsonl` file, or a filled-in `proposals_template.jsonl`, then writes one unified JSONL for `validate-policy-rewrites-batch`. Missing files, empty jobs, unfilled template rows, duplicate outputs, schema errors, or prompt/proposal count mismatches are reported before the verifier consumes any rewrite.

`gharchive-annotation-pack-batch` discovers eligible repositories with the same PR/review/execution-boundary/negative-boundary quality gate used by project generation, then writes one rewrite-ready pack per repository plus a batch report of skipped repos and candidate counts. CI/status/workflow events are a strong execution-boundary subtype, but PR closed/merged/revert/blocked signals are also useful when public GHArchive slices do not expose aligned CI events. Emergency pre-CI events remain a strong negative subtype, but generic do-not-merge, blocked, failed-CI, revert, hold, and approval-boundary language can also ground storage-gating candidates. This is the offline entry point for paper-scale GHArchive slices.

`export-annotation-pack-release` writes a repo-disjoint release skeleton with `release_manifest.json`, `splits.json`, and split JSONL task files. The release still marks LLM generation as disallowed until rewrite outputs pass `validate-policy-rewrites`.

`gharchive-scale-summary` combines batch and release metadata into one report for paper-scale triage: eligible/skipped repos, tasks per pack, candidate type totals, split counts, and whether pack hashes and LLM constraints are present.

`validate-policy-rewrites-batch` validates LLM/human rewrite outputs for every per-repo annotation pack. It accepts either one unified proposal JSONL or a directory of per-pack proposal files, writes per-pack validation reports, and emits `batch_rewrite_validation_report.json`. This is the gate to run after provider-assisted annotation and before treating rewritten probes as release-ready.

`build-projects-from-rewrite-batch` consumes only a passed `batch_rewrite_validation_report.json`, builds one verifier-checked project per pack, and emits `batch_rewrite_project_report.json`. This closes the reference-grounded -> LLM-assisted -> verifier-driven loop for multi-repo GHArchive runs: generated text is never accepted just because an LLM produced it, and each derived project must pass the standard grounding, negative-evidence, and action-boundary verifier.

`export-project-benchmark-release` is the project-level release layer for evaluation. It takes verifier-checked project directories, writes `project_release_manifest.json`, project-disjoint `splits.json`, and `probes/{train,dev,test,all}.jsonl`, and records hashes for project files instead of blindly duplicating raw event payloads. `verify-project-benchmark-release` recomputes those hashes and checks split/probe consistency; fixture-scale empty project splits are warnings, not paper-scale success.

`verify-release-integrity` is the release-level verifier. It recomputes annotation pack hashes, checks repo-disjoint split assignments, validates `tasks/{train,dev,test,all}.jsonl` counts and pack coverage, verifies every release pack has prompt-export coverage, and confirms prompt records carry positive-event and action-boundary constraints. Empty dev/test splits are warnings for tiny fixtures and should be eliminated before paper-scale claims.

`assess-paper-scale` is stricter than integrity. It checks whether a release is large and longitudinal enough for main-paper claims. The default `paper` profile requires enough repos, tasks, non-empty train/dev/test splits, candidate-type diversity, source events, eligible time windows, and multi-window repositories. Use `--allow-fail` during staging so the report is written even when a fixture or small trial slice is not paper-ready.

`gharchive-stage-plan` also writes a machine-readable `decision` block. Treat `decision.ready_for_annotation_budget=false` as a stop signal before LLM/API or human rewrite work. `profile=fixture` always recommends `engineering_fixture`; `profile=pilot` can justify a small rewrite trial; `profile=paper` must pass all raw-slice checks before paper-scale annotation budget is spent.

`audit-workflow-data-sources` records whether the current run is grounded in reusable workflow traces. It fails source readiness when the active staging roots contain no GHArchive workflow event source and no approved email workflow manifest; previously the only discovered shared-storage source was a RedPajama GitHub code sample, which is code text rather than a longitudinal workflow timeline. This is a data-staging stop, not a benchmark-construction success.

For a local or Slurm run on a staged GHArchive slice:

```bash
INPUT=/path/to/gharchive_dir SLICE_OUTPUT=/path/to/longuserpolicy_slice.jsonl OUTPUT_ROOT=examples/generated MAX_RECORDS=200000 bash scripts/prepare_gharchive_slice.sh
sbatch --export=ALL,INPUT=/path/to/gharchive_dir,SLICE_OUTPUT=/path/to/longuserpolicy_slice.jsonl,OUTPUT_ROOT=/path/to/output,MAX_RECORDS=200000 scripts/slurm/prepare_gharchive_slice.sbatch
INPUT=/path/to/gharchive.jsonl OUTPUT_ROOT=examples/generated bash scripts/prepare_gharchive_slice.sh
sbatch --export=ALL,INPUT=/path/to/gharchive.jsonl,OUTPUT_ROOT=/path/to/output scripts/slurm/prepare_gharchive_slice.sbatch
INPUT=/path/to/gharchive.jsonl OUTPUT_ROOT=examples/generated bash scripts/run_gharchive_annotation_pipeline.sh
INPUT=/path/to/gharchive.jsonl OUTPUT_ROOT=examples/generated REWRITE_PROPOSALS=/path/to/rewrite_proposals.jsonl bash scripts/run_gharchive_annotation_pipeline.sh
sbatch --export=ALL,INPUT=/path/to/gharchive.jsonl,OUTPUT_ROOT=/path/to/output scripts/slurm/run_gharchive_annotation_pipeline.sbatch
sbatch --export=ALL,INPUT=/path/to/gharchive.jsonl,OUTPUT_ROOT=/path/to/output,REWRITE_PROPOSALS=/path/to/rewrite_proposals.jsonl scripts/slurm/run_gharchive_annotation_pipeline.sbatch
```

See `docs/gharchive_staging_protocol.md` for staging, license, privacy, and scale-report gates. Raw GHArchive slices should stay outside the committed repository; release packs should keep hashes, raw pointers, selected snippets, and derived tasks rather than blindly republishing full event payloads.

`validate-policy-rewrites` is the required gate after any LLM or human rewrite. It rejects proposals with unsupported event IDs, widened action boundaries, missing negative evidence, or weak expected behavior. Use `--allow-partial` only for debugging partial batches.

`build-projects-from-rewrite-batch` is the corresponding paper-scale command for multi-pack GHArchive runs. It refuses failed batch validation reports, writes per-project validation artifacts, runs `verify-project` internally, and records `projects_passed/projects_failed` in `batch_rewrite_project_report.json` for `readiness-report`.

`export-project-benchmark-release` and `verify-project-benchmark-release` close the final release step for external evaluators: the release can point to project directories or copy them with `--copy-projects`, but in both modes it publishes a stable project/probe manifest, file hashes, split membership, and no-LLM-generation constraints.

Never commit API keys, raw restricted corpora, or unreviewed personal data.
