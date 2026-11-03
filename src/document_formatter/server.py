"""Single-user loopback demonstration. Not a production hosting service."""

import secrets
import tempfile
import uuid
from importlib.resources import files
from pathlib import Path

from flask import Flask, Response, abort, jsonify, request, send_file
from werkzeug.utils import secure_filename

from .engine import Project, read_json, template_names


def create_app(workspace):
    root = Path(workspace).resolve()
    root.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

    @app.before_request
    def local_request():
        if request.host.split(":")[0] not in {"localhost", "127.0.0.1"}:
            abort(403)
        if request.method == "POST" and not secrets.compare_digest(
            request.headers.get("X-Local-Token", ""), token
        ):
            abort(403)

    @app.after_request
    def headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    def project(ident):
        try:
            if str(uuid.UUID(ident)) != ident:
                abort(404)
        except ValueError:
            abort(404)
        p = Project(root / ident)
        if not p.state.exists():
            abort(404)
        return p

    @app.errorhandler(ValueError)
    def invalid(error):
        return jsonify(error=str(error)), 400

    @app.errorhandler(Exception)
    def failure(error):
        from werkzeug.exceptions import HTTPException

        if isinstance(error, HTTPException):
            return error
        return jsonify(error=f"{type(error).__name__}: {error}"), 400

    @app.get("/")
    def index():
        return Response(
            files(__package__)
            .joinpath("web/index.html")
            .read_text()
            .replace("__TOKEN__", token),
            mimetype="text/html",
        )

    @app.get("/api/projects")
    def projects():
        return jsonify(
            projects=[
                {"id": p.parent.name, "title": read_json(p)["title"]}
                for p in root.glob("*/project.json")
            ],
            templates=template_names(),
        )

    @app.post("/api/projects")
    def create():
        body = request.get_json()
        ident = str(uuid.uuid4())
        if body.get("template") not in template_names():
            raise ValueError(
                "Choose a bundled template; custom templates are supported through the CLI"
            )
        Project.create(
            root / ident, body["template"], body.get("title") or "Untitled collection"
        )
        return jsonify(id=ident)

    @app.get("/api/projects/<ident>")
    def detail(ident):
        p = project(ident)
        state = p.load()
        proposal = (
            read_json(p.root / "proposal.json")
            if (p.root / "proposal.json").exists()
            else None
        )
        return jsonify(state=state, proposal=proposal)

    @app.post("/api/projects/<ident>/ingest")
    def ingest(ident):
        p = project(ident)
        uploads = request.files.getlist("files")
        if not 1 <= len(uploads) <= 50:
            raise ValueError("Upload between 1 and 50 files")
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for n, upload in enumerate(uploads):
                folder = Path(tmp) / str(n)
                folder.mkdir()
                path = folder / (secure_filename(upload.filename) or "unnamed.txt")
                upload.save(path)
                paths.append(path)
            return jsonify(added=p.ingest(paths))

    @app.post("/api/projects/<ident>/demo")
    def demo(ident):
        demo_path = Path(__file__).resolve().parents[2] / "examples" / "inputs"
        if not demo_path.exists():
            raise ValueError(
                "Run examples/create_inputs.py in the repository checkout first"
            )
        return jsonify(added=project(ident).ingest([demo_path]))

    @app.post("/api/projects/<ident>/propose")
    def propose(ident):
        body = request.get_json()
        return jsonify(
            project(ident).propose(
                body.get("model") or None, body.get("vision_model") or None
            )
        )

    @app.post("/api/projects/<ident>/accept")
    def accept(ident):
        project(ident).accept(request.get_json()["proposal_id"])
        return jsonify(ok=True)

    @app.post("/api/projects/<ident>/edit")
    def edit(ident):
        body = request.get_json()
        project(ident).edit(body["document"], body["version"])
        return jsonify(ok=True)

    @app.get("/api/projects/<ident>/download")
    def download(ident):
        path = project(ident).root / "document.md"
        if not path.exists():
            abort(404)
        return send_file(path, as_attachment=True, download_name="document.md")

    return app
