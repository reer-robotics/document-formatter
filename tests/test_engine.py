import copy
import importlib.util
import json
from pathlib import Path

import pytest

from document_formatter.engine import Project, check, load_template
from document_formatter.ingest import extract
from document_formatter.model import Ollama
from document_formatter.server import create_app


@pytest.fixture
def samples(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "fixtures", Path(__file__).parents[1] / "examples/create_inputs.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.create(tmp_path / "inputs")


@pytest.fixture
def project(tmp_path, samples):
    p = Project.create(tmp_path / "project")
    p.ingest([samples[0]])
    return p


def test_all_formats_and_dedup(project, samples):
    sources = project.load()["sources"]
    assert {s["format"] for s in sources} == {"md", "csv", "png", "pdf", "docx", "xlsx"}
    assert all(s["segments"] for s in sources)
    assert project.ingest([samples[0]]) == []
    assert any("=SUM" in seg["text"] for s in sources for seg in s["segments"])
    assert any(
        "No production authorization" in seg["text"]
        for s in sources
        for seg in s["segments"]
    )


def test_incremental_preserves_edit_and_history(project, samples):
    first = project.propose()
    project.accept(first["id"])
    doc = project.load()["document"]
    doc["sections"][0]["content"] = "Human-authored scope correction."
    project.edit(doc)
    project.ingest([samples[1]])
    # Manual edits after ingest must not accidentally mark new sources as incorporated.
    project.edit(project.load()["document"])
    next_draft = project.propose()
    assert (
        next_draft["document"]["sections"][0]["content"]
        == "Human-authored scope correction."
    )
    assert "25 runs" in json.dumps(next_draft["document"])
    assert any(x["kind"] == "possible_value_conflict" for x in next_draft["checks"])
    project.accept(next_draft["id"])
    assert len(list((project.root / "history").glob("*.json"))) == 4


def test_stale_proposal_rejected(project, samples):
    proposal = project.propose()
    project.ingest([samples[1]])
    with pytest.raises(ValueError, match="Stale"):
        project.accept(proposal["id"])
    assert project.load()["document"] is None


def test_invalid_batch_does_not_change_manifest(project, tmp_path):
    before = project.load()
    good, bad = tmp_path / "new.txt", tmp_path / "bad.exe"
    good.write_text("New information")
    bad.write_bytes(b"not supported")
    with pytest.raises(ValueError, match="Unsupported"):
        project.ingest([good, bad])
    assert project.load() == before


def test_template_checks_duplicate_keys(tmp_path):
    data = load_template("technical-report")
    data["sections"][1]["key"] = data["sections"][0]["key"]
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="unique"):
        load_template(p)


def test_unknown_refs_and_required_sections(project):
    proposal = project.propose()
    doc = proposal["document"]
    doc["sections"][0]["content"] = "Always succeeds [S0000000000000000-1]"
    issues = check(doc, project.load()["template"], project.load()["sources"])
    assert {"unknown_reference", "strong_claim", "incomplete_section"} <= {
        x["kind"] for x in issues
    }


def test_corrupt_input_and_stale_edit(project, tmp_path):
    p = tmp_path / "bad.pdf"
    p.write_bytes(b"corrupted")
    with pytest.raises(Exception):
        extract(p, tmp_path / "assets")
    proposal = project.propose()
    with pytest.raises(ValueError, match="changed"):
        project.edit(proposal["document"], "old-version")


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://remote.example",
        "http://localhost:11434",
        "http://127.0.0.1:11434@evil.example",
        "http://127.0.0.1:11434/path",
    ],
)
def test_nonlocal_endpoints_rejected(endpoint):
    with pytest.raises(ValueError):
        Ollama("local-test", endpoint)


def test_model_contract_and_unknown_reference(project, monkeypatch):
    calls = []
    original = project.propose()["document"]

    def generate(self, prompt, schema, images=None):
        calls.append(prompt)
        return (
            copy.deepcopy(original)
            if "sections" in schema["properties"]
            else {
                "issues": ["Mock result; not actual AI evaluation."],
                "relationships": [],
            }
        )

    monkeypatch.setattr(Ollama, "generate", generate)
    result = project.propose(model="mock-local")
    assert result["mode"] == "ollama" and len(calls) == 2
    original["sections"][0]["content"] = "Invented reference [S0000000000000000-1]"
    with pytest.raises(ValueError, match="invented"):
        project.propose(model="mock-local")


def test_server_requires_token_and_safe_host(tmp_path):
    app = create_app(tmp_path / "web")
    client = app.test_client()
    assert client.post("/api/projects", json={}).status_code == 403
    assert client.get("/", headers={"Host": "evil.example"}).status_code == 403
    html = client.get("/").get_data(as_text=True)
    token = html.split("const token='")[1].split("'")[0]
    created = client.post(
        "/api/projects",
        json={"template": "technical-report", "title": "Test"},
        headers={"X-Local-Token": token},
    )
    assert created.status_code == 200
    assert (
        client.get("/api/projects/" + created.json["id"]).json["state"]["title"]
        == "Test"
    )


def test_scanned_pdf_is_not_claimed_as_extracted(tmp_path):
    from PIL import Image
    from reportlab.pdfgen import canvas

    img = tmp_path / "scan.png"
    Image.new("RGB", (30, 30), "white").save(img)
    path = tmp_path / "scan.pdf"
    pdf = canvas.Canvas(str(path))
    pdf.drawImage(str(img), 20, 20)
    pdf.save()
    source = extract(path, tmp_path / "assets")
    assert any("no extracted text" in w for w in source["warnings"])
    assert any(s.get("image") for s in source["segments"])


def test_ollama_transport_uses_structured_local_requests(monkeypatch):
    import httpx

    requests = []
    original_client = httpx.Client

    def respond(request):
        requests.append((str(request.url), json.loads(request.content)))
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"capabilities": ["completion", "vision"]})
        return httpx.Response(
            200,
            json={"message": {"content": '{"description":"Mock chart description"}'}},
        )

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original_client(
            transport=httpx.MockTransport(respond), **kwargs
        ),
    )
    schema = {
        "type": "object",
        "required": ["description"],
        "properties": {"description": {"type": "string"}},
    }
    result = Ollama("mock-local").generate("Describe", schema, ["encoded-example"])
    assert result["description"] == "Mock chart description"
    assert requests[1][0] == "http://127.0.0.1:11434/api/chat"
    assert requests[1][1]["format"] == schema
    assert requests[1][1]["stream"] is False
    assert requests[1][1]["messages"][1]["images"] == ["encoded-example"]


def test_ollama_refuses_remote_model_metadata(monkeypatch):
    import httpx

    original_client = httpx.Client
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, json={"remote_host": "https://example.invalid"}
        )
    )
    monkeypatch.setattr(
        httpx, "Client", lambda **kwargs: original_client(transport=transport, **kwargs)
    )
    with pytest.raises(ValueError, match="Remote/cloud"):
        Ollama("mock-local").generate("Test", {"type": "object"})


def test_vision_descriptions_are_labeled_proposals(project, monkeypatch):
    original = project.propose()["document"]

    def generate(self, prompt, schema, images=None):
        if images:
            return {
                "description": "Mock-only: two bars",
                "uncertainties": "No real model was used",
            }
        if "sections" in schema["properties"]:
            return copy.deepcopy(original)
        return {"issues": [], "relationships": []}

    monkeypatch.setattr(Ollama, "generate", generate)
    result = project.propose("mock-text", "mock-vision")
    assert result["visual_interpretations"][0]["model"] == "mock-vision"
    assert (
        result["visual_interpretations"][0]["uncertainties"] == "No real model was used"
    )
    assert project.load()["document"] is None
