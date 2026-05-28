# Reproducibility Checklist

## Determinism

- [ ] All synthetic stages accept an explicit seed.
- [ ] Split generation is deterministic and persona-disjoint.
- [ ] Generated artifact IDs are stable across reruns with the same config.

## Environment

- [ ] Python version recorded.
- [ ] Dependencies pinned for release experiments.
- [ ] `.env.example` documents optional provider keys without exposing secrets.

## Data Provenance

- [ ] Every source document has origin, URI when available, license, and content hash.
- [ ] Raw public data is staged outside committed generated examples.
- [ ] License compatibility is checked before release.

## Validation

- [ ] `python -m ultra_long_benchmark.cli smoke --all` passes.
- [ ] `python -m ultra_long_benchmark.cli validate` passes.
- [ ] `python -m ultra_long_benchmark.cli audit` passes.
- [ ] `python -m pytest -q` passes.

## Documentation

- [ ] Benchmark protocol is versioned.
- [ ] Dataset card describes intended use and non-use.
- [ ] Risk notes cover privacy, synthetic bias, and contamination.
- [ ] Evaluation protocol includes metrics, baselines, and confidence intervals.

## Release

- [ ] Dataset card and benchmark card generated.
- [ ] Release manifest includes counts and file hashes.
- [ ] Train/dev/test split files are present.
- [ ] Human annotation rubric is included.
