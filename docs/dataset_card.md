# Dataset Card Draft

The committed examples are synthetic and deterministic. They are designed to validate construction logic, not to represent population-level behavior.

Intended uses:

- Pipeline smoke testing.
- Memory-benchmark method development.
- Schema and annotation workflow review.

Out-of-scope uses:

- Training production assistants.
- Making claims about real users or real domains.
- Evaluating privacy behavior on undisclosed real personal data.

Future public-data releases must include source licenses, consent/provenance review, deduplication reports, privacy filtering logs, and split contamination analysis.

Current public-data status: GHArchive-style fixtures exercise the public GitHub event adapter, policy-candidate mining path, annotation-pack release path, prompt export path, and release-integrity verifier. The active raw-data staging root is `/home/jmzhang/Workspace/data`; it currently contains 60 GHArchive hourly `.json.gz` files from January 2024 plus a derived pilot slice. Discovery finds GHArchive workflow event sources there, and the pilot stage plan is ready for annotation. No full Enron, Avocado, or other real email corpus has been ingested into the committed release. Email data must pass the manifest/license/privacy gate in `EmailWorkflowAdapter` before use.
