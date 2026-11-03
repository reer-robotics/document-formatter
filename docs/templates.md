# Template schema

A template specifies document structure, not organization authority. The v1 schema includes `schema_version`, stable `id`, display `name`, `description`, and ordered `sections`. Each section has a unique `key`, a `title`, an instruction, and a boolean `required` flag.

```json
{
  "schema_version": 1,
  "id": "lab-note",
  "name": "Lab note",
  "description": "An observation with evidence and limits",
  "sections": [
    {"key":"evidence","title":"Evidence","instruction":"Present observations with source markers.","required":true},
    {"key":"limitations","title":"Limits","instruction":"Explain uncertainty and missing information.","required":true}
  ]
}
```

Use `docformat init workspace/lab --template ./lab-note.json`. Unknown fields, duplicate keys and malformed values are rejected. In extraction-only mode, source excerpts go into `evidence`, or the first section when that key is absent. Other sections remain explicitly incomplete. With a model, instructions guide synthesis into all sections.

Documents store a title and ordered `{key, content}` sections. Citations use stable segment markers like `[S0123456789abcdef-1]`. Checks verify that these IDs exist. They do not verify semantic entailment.

For manual JSON edits, copy the `document` object from `project.json` to a separate JSON file, change it, and run `docformat edit PROJECT --document-json FILE`. The command saves revision history. Do not edit `project.json` directly. The browser provides a section editor.

To try a different template in v0.2, create another project and import the same sources. Automatic migration of accepted writing between templates is deferred.
