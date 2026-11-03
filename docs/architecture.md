# Architecture and integration boundary

The package has six small components: `ingest` (bounded parsers), `engine` (project state and proposals), `model` (local Ollama transport), `workflow` (fixed role passes and skill contracts), `cli` (commands), and `server` (single-user demonstration). Neither Docusaurus nor Decap is a dependency.

## Local project files

- `project.json`: versioned template, source manifest, extracted segments and accepted document.
- `assets/`: normalized image copies; original image metadata is not retained.
- `proposal.json`: latest proposed document, base version, checks, model identity, visual interpretations, organization plan, workflow audit and suggested relationships.
- `proposal.md`: human-readable proposed writing with source register.
- `document.md`: exported accepted writing.
- `history/`: snapshots of the previous state and acceptance/manual-edit audit records.

Original source files are not modified. Text is extracted into the manifest; source IDs use a SHA-256 prefix and segment IDs are stable within an extraction. Full hashes are stored. Identical files are deduplicated; changed content with the same filename is retained as another version and flagged. Hashes identify inputs; they do not validate claims.

Operations use a per-project directory lock and atomic JSON replacement. An interrupted operation can leave orphan image assets or a lock directory. The manifest remains authoritative; after confirming no process is running, an operator can remove a stale lock. This is not a transactional database or multi-user collaboration service. The export is derived and can be regenerated from accepted state.

A proposal is tied to the exact project version. Adding content or editing a document invalidates older proposals. In offline mode, existing accepted text is preserved verbatim and new source excerpts are appended. Model mode receives existing writing and is instructed to preserve manual changes, but may still rewrite them: the diff and human acceptance are the control.

## Logical review

Deterministic checks identify missing required sections, missing/unknown reference markers, absolute language, and different numeric values under identical explicit `Label: number unit` headings. The latter is a possible discrepancy, not a contradiction verdict: source dates or scopes may explain it. Unit conversion, causality, numerical reasoning, spreadsheet formula evaluation, and general contradictions are not implemented as deterministic checks.

Optional model review proposes logical concerns and segment relationships (`related_to`, `possible_conflict`, `adds_context`). Vision descriptions include uncertainties. These are not verified facts or an independently reviewed graph. No graph visualization or recommendation product is implemented in this release.

## Future journal integration

Pin a toolkit version in an adapter maintained by the journal. Provide authorized source inputs, show the proposal in the editor, and save author-accepted Markdown through the existing GitHub branch/PR process. The formatting service must not merge PRs, grant maturity, or publish company content. A deployed service would additionally need authenticated access, authorization, job isolation, quotas, and operational monitoring.

## Verification boundary

The example and unit tests exercise real parsers, state transitions, stale-proposal rejection, HTTP controls and model response contracts. Mock model responses verify plumbing only. Semantic quality and real vision inference must be evaluated with a chosen installed model in a later step.


## One-model workflow

The executable workflow loads `workflow.json` and the five `skills/*.json` instruction files. Roles have no shell, network-search, publishing, or acceptance tools. A single Ollama adapter instance executes all AI steps against one selected local model. Capability preflight runs before any generation. The three initial model passes are organization, writing and review, plus one interpretation call per extracted image; an update substitutes the revision skill for writing.

Structured schemas and source-accounting checks execute in Python. Invalid output or provider errors abort the run with no automatic retry, leave accepted content unchanged, and do not replace an earlier proposal. Failed attempts are surfaced as errors; this prototype does not persist a separate failed-run audit. Extraction-only mode bypasses the entire AI workflow and records `workflow: null`.

Skill/model changes must be evaluated against fixed regression cases. Recorded instructions and metadata improve traceability but cannot guarantee deterministic output or prevent the same model repeating its own error.
