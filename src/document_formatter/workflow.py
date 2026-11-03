"""Fixed, versioned role passes executed by one local multimodal model."""

import base64
import hashlib
import json
from datetime import datetime, timezone
from importlib.resources import files

from jsonschema import validate

from .model import Ollama


def fingerprint(data):
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def resource(name):
    return json.loads(files(__package__).joinpath(name).read_text())


def run_workflow(
    state, assets, model, endpoint, draft_schema, validate_draft, check_draft
):
    template = state["template"]
    segments = [s for source in state["sources"] for s in source["segments"]]
    ids = [s["id"] for s in segments]
    keys = [s["key"] for s in template["sections"]]
    manifest = resource("workflow.json")
    expected = [
        "interpret",
        "organize",
        "compose",
        "validate",
        "review",
        "human_acceptance",
    ]
    if manifest["steps"] != expected or manifest["automatic_retries"] != 0:
        raise ValueError(
            "Unsupported workflow manifest; executable workflow must be updated together"
        )
    client = Ollama(model, endpoint)
    metadata = client.inspect(require_multimodal=True)
    skills = {
        name: resource(f"skills/{name}.json")
        for name in ["interpret", "organize", "write", "revise", "review"]
    }
    trace = []
    audit = {
        "id": manifest["id"],
        "version": manifest["version"],
        "manifest_sha256": fingerprint(manifest),
        "model": model,
        "endpoint": client.endpoint,
        "model_metadata_sha256": fingerprint(metadata),
        "capabilities": metadata.get("capabilities", []),
        "template_sha256": fingerprint(template),
        "template_id": template["id"],
        "template_schema_version": template["schema_version"],
        "base_version": state["version"],
        "sources": [{"id": s["id"], "sha256": s["sha256"]} for s in state["sources"]],
        "skills": {
            key: {"version": skill["version"], "sha256": fingerprint(skill)}
            for key, skill in skills.items()
        },
        "steps": trace,
    }

    def run(name, context, schema, images=None):
        skill = skills[name]
        prompt = json.dumps({"skill": skill, "input": context}, ensure_ascii=False)
        if len(prompt) > 80_000:
            raise ValueError(
                f"{name}: request exceeds 80,000 characters; split the project. No silent truncation."
            )
        started = datetime.now(timezone.utc).isoformat()
        result = client.generate(prompt, schema, images)
        # Enforce the contract here as well as in the adapter.
        validate(result, schema)
        trace.append(
            {
                "step": name,
                "role": skill["role"],
                "skill_version": skill["version"],
                "model": model,
                "status": "completed",
                "started_at": started,
                "output_sha256": fingerprint(result),
            }
        )
        return result

    descriptions = []
    for segment in segments:
        if not segment.get("image"):
            continue
        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["description", "uncertainties"],
            "properties": {
                "description": {"type": "string"},
                "uncertainties": {"type": "string"},
            },
        }
        result = run(
            "interpret",
            {"source_id": segment["id"], "location": segment["location"]},
            schema,
            [base64.b64encode((assets / segment["image"]).read_bytes()).decode()],
        )
        descriptions.append({"source": segment["id"], **result, "model": model})
        trace[-1]["source"] = segment["id"]
    if not descriptions:
        trace.append(
            {"step": "interpret", "status": "skipped", "reason": "No extracted images"}
        )

    context = {
        "template": template,
        "current_document": state["document"],
        "sources": state["sources"],
        "visual_interpretations": descriptions,
        "new_source_ids": [
            s["id"]
            for s in state["sources"]
            if s["id"] not in state["document_source_ids"]
        ],
    }
    outline_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["sections", "unassigned"],
        "properties": {
            "sections": {
                "type": "array",
                "minItems": len(keys),
                "maxItems": len(keys),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["key", "plan", "source_ids"],
                    "properties": {
                        "key": {"enum": keys},
                        "plan": {"type": "string"},
                        "source_ids": {
                            "type": "array",
                            "uniqueItems": True,
                            "items": {"enum": ids},
                        },
                    },
                },
            },
            "unassigned": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["source_id", "reason"],
                    "properties": {
                        "source_id": {"enum": ids},
                        "reason": {"type": "string", "minLength": 1},
                    },
                },
            },
        },
    }
    outline = run("organize", context, outline_schema)
    if [s["key"] for s in outline["sections"]] != keys:
        raise ValueError("Organization plan must match template section order")
    assigned = {sid for section in outline["sections"] for sid in section["source_ids"]}
    unassigned = [s["source_id"] for s in outline["unassigned"]]
    if (
        assigned | set(unassigned) != set(ids)
        or assigned & set(unassigned)
        or len(unassigned) != len(set(unassigned))
    ):
        raise ValueError(
            "Organization plan must account for every source segment without contradictory assignments"
        )
    compose_skill = manifest["compose_skills"][
        "incremental" if state["document"] else "initial"
    ]
    if compose_skill not in {"write", "revise"}:
        raise ValueError("Unsupported compose skill")
    doc = run(compose_skill, {**context, "outline": outline}, draft_schema)
    validate_draft(doc)
    checks = check_draft(doc)
    trace.append(
        {
            "step": "validate",
            "status": "completed",
            "findings": len(checks),
            "executor": "deterministic",
        }
    )
    analysis_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["issues", "relationships"],
        "properties": {
            "issues": {"type": "array", "items": {"type": "string"}},
            "relationships": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["from", "to", "type", "reason"],
                    "properties": {
                        "from": {"enum": ids},
                        "to": {"enum": ids},
                        "type": {
                            "enum": ["related_to", "possible_conflict", "adds_context"]
                        },
                        "reason": {"type": "string"},
                    },
                },
            },
        },
    }
    analysis = run(
        "review",
        {**context, "document": doc, "deterministic_checks": checks},
        analysis_schema,
    )
    trace.append({"step": "human_acceptance", "status": "pending"})
    return {
        "document": doc,
        "outline": outline,
        "checks": checks,
        "analysis": analysis,
        "descriptions": descriptions,
        "audit": audit,
    }
