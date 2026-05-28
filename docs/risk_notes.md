# Risk Notes

Key risks and mitigations:

- Synthetic artifacts can make benchmark shortcuts possible. Mitigation: mix source corpora, perturb templates, and report template leakage checks.
- Long trajectories can accidentally preserve private data. Mitigation: schema-level privacy tags, redaction, human review, and refusal tasks.
- LLM-generated traces can hallucinate inconsistent facts. Mitigation: event-linked evidence IDs, contradiction checks, and provenance manifests.
- Public corpora can contain license restrictions. Mitigation: require per-document license metadata and exclude unknown-license sources from releases.
- Evaluation can overemphasize exact match. Mitigation: report capability-specific metrics, evidence sufficiency, refusal behavior, abstention calibration, and qualitative audits.

