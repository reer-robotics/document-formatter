# Single multimodal model workflow

One configured model performs several bounded roles. Roles are not separate autonomous services. They have separate instructions and schema contracts, share the same local adapter instance, and cannot approve content or execute tools.

## Fixed stages

| Stage | Skill | Input | Output and validation |
| --- | --- | --- | --- |
| Preflight | Ordinary code | Model name and loopback endpoint | Require `completion` and `vision`; reject remote metadata |
| Interpret | `skills/interpret.json` | Each extracted image and its source ID | Description and uncertainties; labeled as model interpretation |
| Organize | `skills/organize.json` | Sources, template, accepted text, new source IDs, visual interpretations | Ordered section plan with known source IDs; all segments assigned or explicitly unassigned |
| Compose initial draft | `skills/write.json` | Evidence and outline | Exact section structure; unknown citation IDs rejected |
| Compose update | `skills/revise.json` | Same inputs plus accepted manual writing | Proposed full revision; preservation of edits is instructed, not guaranteed |
| Validate | Ordinary code | Draft and sources | Structural, reference and heuristic logical findings |
| Review | `skills/review.json` | Draft, evidence, visual interpretations and deterministic findings | Tentative logical concerns and source relationships |
| Accept | Human action | Proposal, checks and diff | Version-checked commit and preserved revision history |

The initial and update composition stages are alternatives. The model does not choose its next role. Interpretation is skipped explicitly when no images were extracted. Diagram content that a parser could not extract is not magically recovered by the model.

## What is fixed

`workflow.json` declares the sequence, one-model policy, composition skills, version and zero automatic retries. `workflow.py` implements that sequence and validates outputs. Each skill file declares a version, role and instructions. Schemas are constructed from the current template and source IDs in code.

Contributors must update the executable validators and regression tests when changing a contract. Instructions alone are not an enforcement mechanism. No role can browse the web, invoke shell commands, publish content, or accept its own work.

## Failure and review

Invalid structure, missing source accounting, unknown citation IDs, model errors or oversized requests stop the operation. Existing accepted writing and any earlier proposal remain intact. Findings that require editorial judgment stay visible for the human; they do not trigger a repair loop. A failure during parsing may leave unreferenced local assets, as described in the architecture guide.

The workflow records fingerprints for inputs, template, skills, model metadata and role outputs. This is provenance, not a guarantee that the model was correct or that its weights stayed identical under a mutable model tag. Pin/manage the installed model separately if reproducibility matters.

## Migration from 0.1

- CLI: replace `--model TEXT --vision-model VISION` with `--model MULTIMODAL`.
- Python: use `project.propose('MULTIMODAL', endpoint='http://127.0.0.1:11434')`; the endpoint is keyword-only.
- Browser: one model field; image descriptions are automatically included when images are present.
- HTTP demo: `vision_model` is rejected rather than silently ignored. Reload any old browser tab after restarting the server.
- Existing project schemas, accepted documents and history are unchanged. Old proposals can still be inspected/accepted subject to their existing version check; they do not retroactively gain a workflow audit. Generate a new proposal to use this workflow.
- No model: `project.propose()` still performs extraction-only organization with no Ollama calls.

## Validation status

Tests use mock model outputs and HTTP transports. They cover one adapter/model across stages, automatic image interpretation, source coverage, incremental revision inputs, stale proposals, model failure and local-only controls. Real semantic quality, vision accuracy, and latency have not been measured with an installed model.
