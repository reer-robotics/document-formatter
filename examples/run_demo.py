"""Offline end-to-end demonstration. No model or network is used."""

import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from create_inputs import create
from document_formatter.engine import Project, check

root = Path(__file__).resolve().parent
inputs, extra = create()
with TemporaryDirectory() as tmp:
    project = Project.create(Path(tmp) / "demo", title="Synthetic pickup investigation")
    project.ingest([inputs])
    first = project.propose()
    project.accept(first["id"])
    doc = project.load()["document"]
    doc["sections"][0]["content"] = (
        "Manual note: This is an extraction demonstration; interpretation is still pending."
    )
    project.edit(doc)
    project.ingest([extra])
    second = project.propose()
    assert "Manual note:" in second["document"]["sections"][0]["content"]
    assert any(i["kind"] == "possible_value_conflict" for i in second["checks"])
    project.accept(second["id"])
    output = root / "expected"
    output.mkdir(exist_ok=True)
    shutil.copyfile(project.root / "document.md", output / "extractive-draft.md")
    (output / "checks.json").write_text(
        json.dumps(
            check(
                project.load()["document"],
                project.load()["template"],
                project.load()["sources"],
            ),
            indent=2,
        )
        + "\n"
    )
    (output / "update.diff").write_text(second["diff"])
    print(
        "PASS: six formats ingested; proposal accepted; manual edit retained; added TXT evidence; possible numerical discrepancy flagged."
    )
    print(
        "Outputs are extraction-only examples. No AI prose or image interpretations were generated."
    )
