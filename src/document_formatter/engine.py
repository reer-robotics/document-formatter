import copy
import difflib
import json
import re
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path

from jsonschema import validate

from .ingest import expand, extract
from .workflow import run_workflow

REF = re.compile(r"\[(S[0-9a-f]{16}-\d+)\]")


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, data):
    path = Path(path)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    temp.replace(path)


def template_names():
    return ["technical-report", "investigation-note", "knowledge-article"]


def load_template(value):
    p = Path(value)
    data = (
        read_json(p)
        if p.is_file()
        else json.loads(
            files(__package__).joinpath(f"templates/{value}.json").read_text()
        )
    )
    validate(
        data,
        json.loads(files(__package__).joinpath("template.schema.json").read_text()),
    )
    keys = [s["key"] for s in data["sections"]]
    if len(set(keys)) != len(keys):
        raise ValueError("Template section keys must be unique")
    return data


def document_schema(template):
    section = {
        "type": "object",
        "additionalProperties": False,
        "required": ["key", "content"],
        "properties": {
            "key": {"enum": [s["key"] for s in template["sections"]]},
            "content": {"type": "string"},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["title", "sections"],
        "properties": {
            "title": {"type": "string", "minLength": 1},
            "sections": {
                "type": "array",
                "minItems": len(template["sections"]),
                "maxItems": len(template["sections"]),
                "items": section,
            },
        },
    }


def validate_document(doc, template):
    validate(doc, document_schema(template))
    if [s["key"] for s in doc["sections"]] != [s["key"] for s in template["sections"]]:
        raise ValueError("Document sections must match template keys in order")


def markdown(doc, template, sources):
    if not doc:
        return ""
    titles = {s["key"]: s["title"] for s in template["sections"]}
    body = "# " + doc["title"] + "\n\n"
    for section in doc["sections"]:
        body += f"## {titles[section['key']]}\n\n{section['content']}\n\n"
    body += "## Source register\n\n"
    for source in sources:
        for seg in source["segments"]:
            body += f"- [{seg['id']}] {source['name']} — {seg['location']}\n"
    return body


def check(doc, template, sources):
    """Heuristics only: structural checks and explicit key:value discrepancy detection."""
    validate_document(doc, template)
    issues = []
    known = {s["id"] for src in sources for s in src["segments"]}
    for rule, section in zip(template["sections"], doc["sections"]):
        text = section["content"]
        refs = set(REF.findall(text))
        if rule["required"] and (not text.strip() or "TODO:" in text):
            issues.append(
                {
                    "kind": "incomplete_section",
                    "message": f"{rule['title']}: content is missing or marked TODO.",
                }
            )
        if text.strip() and "TODO:" not in text and not refs:
            issues.append(
                {
                    "kind": "uncited_section",
                    "message": f"{rule['title']}: no source references; review support.",
                }
            )
        for ref in sorted(refs - known):
            issues.append(
                {
                    "kind": "unknown_reference",
                    "message": f"Unknown source reference [{ref}]",
                }
            )
        if re.search(r"\b(proves?|guarantees?|always|never)\b", text, re.I):
            issues.append(
                {
                    "kind": "strong_claim",
                    "message": f"{rule['title']}: absolute wording needs human review.",
                }
            )
    measures = {}
    for src in sources:
        for seg in src["segments"]:
            # Explicit matching labels only. Different values can represent legitimate revisions.
            for label, value, unit in re.findall(
                r"^([A-Za-z][A-Za-z _-]{2,40}):\s*([-+]?\d+(?:\.\d+)?)\s*([a-zA-Z%/]*)\s*$",
                seg["text"],
                re.M,
            ):
                key = (label.strip().lower(), unit.lower())
                measures.setdefault(key, {}).setdefault(float(value), []).append(
                    seg["id"]
                )
    for (label, unit), values in measures.items():
        if len(values) > 1:
            issues.append(
                {
                    "kind": "possible_value_conflict",
                    "message": f"{label}: different values {list(values)} {unit}; check scope, date and revision.",
                    "sources": [s for group in values.values() for s in group],
                }
            )
    return issues


@contextmanager
def lock(root):
    marker = root / ".operation-lock"
    try:
        marker.mkdir()
    except FileExistsError:
        raise ValueError(
            "Another operation is running. If a process crashed, remove .operation-lock after confirming it has stopped."
        ) from None
    try:
        yield
    finally:
        marker.rmdir()


class Project:
    def __init__(self, path):
        self.root = Path(path)
        self.state = self.root / "project.json"

    @classmethod
    def create(cls, path, template="technical-report", title="Untitled document"):
        project = cls(path)
        project.root.mkdir(parents=True, exist_ok=True)
        with lock(project.root):
            if project.state.exists():
                raise ValueError("Project already exists")
            write_json(
                project.state,
                {
                    "schema_version": 1,
                    "version": str(uuid.uuid4()),
                    "title": title,
                    "template": load_template(template),
                    "sources": [],
                    "document": None,
                    "document_source_ids": [],
                },
            )
        return project

    def load(self):
        data = read_json(self.state)
        if data.get("schema_version") != 1:
            raise ValueError("Unsupported project schema version")
        return data

    def ingest(self, paths):
        with lock(self.root):
            state = self.load()
            added = []
            known = {s["id"] for s in state["sources"]}
            # Commit the manifest only after the entire batch extracts successfully.
            for path in expand(paths):
                source = extract(path, self.root / "assets")
                if source["id"] not in known:
                    if any(s["name"] == source["name"] for s in state["sources"]):
                        source["warnings"].append(
                            "Same filename as earlier content; both versions retained. Review possible replacement."
                        )
                    state["sources"].append(source)
                    known.add(source["id"])
                    added.append(source["name"])
            if (
                len(state["sources"]) > 50
                or sum(
                    len(s["text"]) for src in state["sources"] for s in src["segments"]
                )
                > 120_000
            ):
                raise ValueError(
                    "Project exceeds 50 sources or 120,000 extracted characters; split it"
                )
            if added:
                state["version"] = str(uuid.uuid4())
                write_json(self.state, state)
            return added

    def propose(self, model=None, *, endpoint="http://127.0.0.1:11434"):
        with lock(self.root):
            state = self.load()
            if not state["sources"]:
                raise ValueError("Import at least one source first")
            template = state["template"]
            segments = [s for src in state["sources"] for s in src["segments"]]
            if not segments:
                raise ValueError(
                    "No usable source content; inspect extraction warnings"
                )
            images = [s for s in segments if s.get("image")]
            if len(images) > 20:
                raise ValueError("At most 20 images per project are supported")
            descriptions = []
            outline = None
            workflow = None
            if model:

                def validate_proposed(doc):
                    validate_document(doc, template)
                    if set(REF.findall(json.dumps(doc))) - {s["id"] for s in segments}:
                        raise ValueError(
                            "Model returned invented source IDs; proposal rejected"
                        )

                run = run_workflow(
                    state,
                    self.root / "assets",
                    model,
                    endpoint,
                    document_schema(template),
                    validate_proposed,
                    lambda doc: check(doc, template, state["sources"]),
                )
                doc, analysis = run["document"], run["analysis"]
                descriptions, outline, workflow = (
                    run["descriptions"],
                    run["outline"],
                    run["audit"],
                )
                mode = "ollama"
            else:
                # No model: preserve existing text and append source excerpts, not invented synthesis.
                doc = (
                    copy.deepcopy(state["document"])
                    if state["document"]
                    else {
                        "title": state["title"],
                        "sections": [
                            {"key": s["key"], "content": "TODO: " + s["instruction"]}
                            for s in template["sections"]
                        ],
                    }
                )
                evidence = next(
                    (s for s in doc["sections"] if s["key"] == "evidence"),
                    doc["sections"][0],
                )
                if evidence["content"].startswith("TODO:"):
                    evidence["content"] = ""
                for src in state["sources"]:
                    if src["id"] in state["document_source_ids"]:
                        continue
                    for seg in src["segments"]:
                        quoted = "\n".join(
                            "> " + line for line in seg["text"].splitlines()
                        )
                        evidence["content"] += (
                            f"\n\nSource excerpt — {src['name']}, {seg['location']} [{seg['id']}]\n\n{quoted}"
                        )
                mode = "extractive"
                analysis = {
                    "issues": [
                        "Semantic coherence and contradictions were not assessed: no model configured."
                    ],
                    "relationships": [],
                }
            result = {
                "id": str(uuid.uuid4()),
                "base_version": state["version"],
                "created_at": now(),
                "mode": mode,
                "model": model,
                "document": doc,
                "outline": outline,
                "workflow": workflow,
                "checks": check(doc, template, state["sources"]),
                "ai_review": analysis,
                "visual_interpretations": descriptions,
                "warnings": [w for src in state["sources"] for w in src["warnings"]]
                + (
                    [f"{len(images)} image(s) have not been visually interpreted."]
                    if images and not model
                    else []
                ),
                "diff": "".join(
                    difflib.unified_diff(
                        markdown(
                            state["document"], template, state["sources"]
                        ).splitlines(True),
                        markdown(doc, template, state["sources"]).splitlines(True),
                        fromfile="accepted",
                        tofile="proposed",
                    )
                ),
            }
            write_json(self.root / "proposal.json", result)
            (self.root / "proposal.md").write_text(
                markdown(doc, template, state["sources"])
            )
            return result

    def accept(self, proposal_id):
        with lock(self.root):
            state, proposal = self.load(), read_json(self.root / "proposal.json")
            if (
                proposal["id"] != proposal_id
                or proposal["base_version"] != state["version"]
            ):
                raise ValueError("Stale proposal: regenerate after imports or edits")
            if proposal.get("workflow"):
                proposal["workflow"]["steps"][-1] = {
                    "step": "human_acceptance",
                    "status": "accepted",
                    "at": now(),
                }
            self._commit(
                state, proposal["document"], {"action": "accept", "proposal": proposal}
            )

    def edit(self, document, expected_version=None):
        with lock(self.root):
            state = self.load()
            if expected_version and expected_version != state["version"]:
                raise ValueError(
                    "Document changed since it was opened; reload before editing"
                )
            self._commit(state, document, {"action": "manual_edit"})

    def _commit(self, state, document, audit):
        validate_document(document, state["template"])
        revision = str(uuid.uuid4())
        history = self.root / "history"
        history.mkdir(exist_ok=True)
        write_json(
            history / f"{revision}.json", {"at": now(), "before": state, **audit}
        )
        state.update(document=document, version=revision)
        if audit["action"] == "accept":
            state["document_source_ids"] = [s["id"] for s in state["sources"]]
        write_json(self.state, state)
        (self.root / "document.md").write_text(
            markdown(document, state["template"], state["sources"])
        )
