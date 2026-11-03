# Changelog

## 0.2.0

- One configured local multimodal model for all AI roles, with completion/vision preflight.
- Versioned interpretation, organization, writing, revision and logic-review skills.
- Fixed sequence with source accounting, deterministic checks and human acceptance.
- Proposal outline and workflow audit exposed in the browser.
- Removed `--vision-model` and the separate browser vision field. Python `endpoint` is now keyword-only.
- Existing project data and accepted documents remain readable; extraction-only mode is unchanged.
- Real-model evaluation remains pending; no model was downloaded.

## 0.1.0

- Selectable JSON-schema-validated templates.
- Text, Markdown, PDF, DOCX, CSV, TSV, XLSX and raster image ingestion.
- Source-linked proposals, human acceptance, manual editing and revision snapshots.
- Incremental additions with stale-proposal rejection.
- Explicit extraction-only mode and optional loopback Ollama text/vision integration.
- Structural and simple numeric-discrepancy checks; optional model logical review.
- CLI, Python library, local browser demonstration and synthetic examples.

No AI model was downloaded or used to produce the checked-in demo outputs. Real-model evaluation is pending.
