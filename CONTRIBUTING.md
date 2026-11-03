# Contributing

Start with a small issue describing the input, expected output, and observed failure. Use synthetic or openly licensed samples only. Never attach private organization content, credentials or customer files.

1. Fork and clone the repository.
2. Create a Python 3.11+ virtual environment and install `python -m pip install -e '.[dev]'`.
3. Make a focused branch. Keep the engine independent of a specific journal or model.
4. Add a regression test for parser, provenance, proposal or revision behavior.
5. Run `pytest -q` and `python examples/run_demo.py`.
6. Update the format limitations and examples when behavior changes.
7. Open a pull request explaining the problem, behavior change and validation.

Template changes must remain compatible with the published schema. Parser extensions must preserve source locations, declare unsupported features, and avoid silently dropping content. Model extensions must not introduce network calls in offline mode or hide failures with a generated-looking fallback. Do not claim semantic quality from mock tests.

The owner is collecting feedback on v0.2 before adding more modules. Suggested follow-ups include real local-model evaluation, OCR, additional export formats and richer manual review. The reading-assistant and graph products are deliberately separate future work.

Skill changes must update the skill version and, when behavior or ordering changes, the workflow version. Preserve the one-model contract, source accounting, human acceptance gate, and absence of automatic fallback. Add tests for new skill output contracts. The model-free test suite checks orchestration, not real-model quality.
