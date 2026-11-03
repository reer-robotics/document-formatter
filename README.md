# Document Formatter

A local-first formatting engine for collections of evidence. Import files, choose a standard template, inspect a proposed draft, and accept a revision. Add material later while preserving the accepted document and its edit history.

**Version 0.2 is a feedback prototype.** It is a standalone public project, not connected to any private company journal. All committed examples are synthetic.

## Two explicit operating modes

| Mode | What it does | What it does not do |
| --- | --- | --- |
| Extraction only (default) | Extract source text, organize excerpts in a template, preserve references, flag structural gaps and matching-label numerical discrepancies | No semantic synthesis, image understanding, or general contradiction detection |
| One local multimodal model | Interpret images, organize sources, draft or revise writing, and review logic in separate fixed passes | No proof of truth, automatic publication, or reliable scientific certification |

**No model is bundled or downloaded.** The first demonstration and CI tests run without a model. Ollama integration is contract-tested with mocks; real-model quality has not been evaluated in this release.

## Quick start

Requires Python 3.11 or newer. From a repository checkout:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python examples/create_inputs.py
docformat serve
```

On Windows, activate with `.venv\Scripts\activate` instead. Open **http://127.0.0.1:4173**. Create a collection, load the synthetic example files, generate a proposal, inspect the checks and diff, then accept. You can edit each accepted section and download Markdown.

Leave the model fields blank to try the extraction-only demonstration. The local server is a single-user development tool, not an internet-facing deployment.

## Input and output support

| Input | Extraction | Limits |
| --- | --- | --- |
| UTF-8 `.txt`, `.md` | Paragraphs with source IDs | Markdown layout is not semantically interpreted in offline mode |
| `.pdf` | Page text and supported embedded raster images | No OCR, vector diagram reconstruction, or layout fidelity; scans are flagged |
| `.docx` | Paragraphs and tables in document order, supported embedded raster images | No legacy `.doc`, tracked-change resolution, text boxes, headers, or image anchoring |
| `.xlsx` | Cell rows and formula expressions | No legacy `.xls`, formula evaluation, charts, images, or styling |
| `.csv`, `.tsv` | Rows and cell values | UTF-8 input; no type inference or formula evaluation |
| `.png`, `.jpg`, `.jpeg`, `.webp` | Image dimensions; normalized local image copy | Descriptions use the same configured multimodal model as writing |

Outputs are **Markdown and structured JSON**, with a source register, proposed-change diff, check results, and local revision history. Word and PDF export are not included in v0.2.

Limits: 20 MB per file, 50 files/project, 120,000 extracted characters/project, 100 PDF pages/file, 10,000 spreadsheet cells/workbook, 20 images per proposal. Model requests over 80,000 characters fail explicitly rather than silently dropping sources. Parsing trusted local files is assumed; these limits are not a complete hostile-file sandbox.

## Three ways to use it

### Command-line workflow

```bash
docformat init workspace/study --template technical-report --title "Pickup investigation"
docformat ingest workspace/study examples/inputs
docformat propose workspace/study
# Inspect workspace/study/proposal.md, proposal.json and the diff.
# Copy the actual proposal_id printed by the previous command:
docformat accept workspace/study --proposal-id YOUR_PROPOSAL_ID

docformat ingest workspace/study examples/additional
docformat propose workspace/study
# The previous accepted document is unchanged until you accept this new proposal.
docformat check workspace/study
```

`check` returns 1 when heuristic findings exist, 0 when none are found, and 2 on operational error. Zero findings is not a statement that the document is correct.

### Python library

```python
from document_formatter.engine import Project

project = Project.create('workspace/my-report', template='investigation-note', title='A test')
project.ingest(['notes.md', 'measurements.xlsx', 'photo.png'])
proposal = project.propose()  # extraction only
# Show the proposal and checks to a human before accepting.
project.accept(proposal['id'])
```

### Local browser demonstration

`docformat serve --workspace workspace --port 4173` opens the workflow through a loopback HTTP server. Upload multiple files, choose a template, review the proposal, edit accepted sections, and export. The UI uses the same engine as the CLI and library. Refreshing does not lose project state. The HTTP API is an internal demo interface, not a supported multi-user API.

## One-model framework

Choose **one installed local multimodal model**. Every AI role uses the same model and endpoint; separate text, vision and reviewer settings are not supported. Even text-only collections require the configured model to advertise both `completion` and `vision`, so the workflow has a consistent capability contract.

```bash
docformat propose workspace/study --model YOUR_INSTALLED_MULTIMODAL_MODEL
# Inspect the versioned workflow without connecting to a model:
docformat workflow
```

The fixed sequence is **interpret extracted images → organize evidence → write (or revise) → deterministic validation → logic review → human acceptance**. Each role has its own versioned skill instructions and structured output contract. Images are processed automatically when present; no separate vision-model option is needed. Without images, interpretation is recorded as skipped.

The organizer must account for every source segment, including explicit reasons for unassigned material. A proposed outline is an accounting plan, not proof that every fact made it into the draft. The writer receives that plan and source evidence. For later edits, the revision skill also receives the accepted writing and identifies newly imported sources. The same model then checks its work in a separate pass. This is **not an independent expert review**.

The default endpoint is `http://127.0.0.1:11434`; the CLI accepts a different numeric loopback address with `--endpoint`. No model is downloaded and there is no cloud or extraction fallback when a selected model fails. Redirects, environment proxies, remote endpoints and detected cloud models are refused. A locally administered service can still forward requests, so configure Ollama for local inference.

Every completed AI proposal records the workflow and skill versions/hashes, requested model, endpoint, capability metadata fingerprint, template fingerprint, input source hashes, stage results, and output fingerprints. The model metadata fingerprint is **not** a hash of the actual model weights. Review findings do not automatically approve or rewrite a draft.

[Workflow and skills](docs/workflow.md) describes the contracts and migration from v0.1. The official [Ollama chat API](https://docs.ollama.com/api/chat), [structured outputs](https://docs.ollama.com/capabilities/structured-outputs), and [vision guide](https://docs.ollama.com/capabilities/vision) describe the adapter protocol.

## Examples

- **Mixed collection:** six synthetic files covering Markdown, CSV, PNG, PDF, Word and Excel.
- **Incremental update:** add `examples/additional/follow-up.txt`; a sample-count discrepancy is flagged while existing manual text is preserved.
- **Selectable structures:** technical report, investigation note, knowledge article.

Run `python examples/run_demo.py` to reproduce the checked-in extraction-only [draft](examples/expected/extractive-draft.md), [check report](examples/expected/checks.json), and [incremental diff](examples/expected/update.diff). These are not precomputed AI results.

## Templates and extensions

Templates are versioned JSON documents validated against [the template schema](src/document_formatter/template.schema.json). Custom templates can be supplied as a path to `docformat init --template path/to/template.json`. The template is embedded in the project so later package updates do not silently change it. See [template documentation](docs/templates.md).

See [architecture](docs/architecture.md), [contributing](CONTRIBUTING.md), and [security boundaries](SECURITY.md). The private REER journal can consume a future tagged release; no journal integration, citation recommendation sidebar, or knowledge-graph application is included here.

## Development

```bash
python -m pip install -e '.[dev]'
pytest -q
python examples/run_demo.py
python -m pip wheel --no-deps . -w dist
```

MIT licensed. This is a repository release; it is not published to PyPI. This revision stays within the formatter repository; model downloads and additional repositories remain deferred.

![Local extraction and review demonstration](docs/demo.jpg)
