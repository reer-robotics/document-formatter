# Security and data boundaries

This is a local, single-user prototype. Do not expose the Flask development server to the internet or a shared network. It binds to loopback, validates the Host header, requires a session token for POST requests, and escapes source text through DOM textContent. This does not provide user authentication or operating-system isolation.

No content is sent to a cloud provider by the formatter. Ollama calls occur only when a model is explicitly selected and target a numeric loopback address. The application rejects redirects, environment proxies, obvious cloud model names and remote model metadata. A local service administrator can still configure forwarding; local execution is ultimately a deployment responsibility.

Input parsers are third-party software. File, page, cell and extracted-text limits reduce accidental overload but do not fully isolate malicious PDFs, decompression bombs or parser exploits. Use trusted files for v0.2; a production ingestion service needs process isolation and resource limits. Embedded macros and spreadsheet formulas are not executed by this application.

Project manifests, image assets, drafts and revision history contain the imported material. Keep `workspace/` out of Git and delete/archive it according to your own retention policy. There is no automatic telemetry. Model suggestions can be wrong or influenced by hostile instructions within sources; human review is required before use.

Report issues through GitHub private vulnerability reporting when enabled. Otherwise contact the repository maintainer privately rather than posting sensitive reproduction material in a public issue.
