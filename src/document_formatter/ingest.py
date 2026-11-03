"""Extract bounded, source-addressable evidence. Never execute source macros/formulas."""

import csv
import hashlib
import io
import zipfile
from pathlib import Path

from PIL import Image
from docx import Document
from openpyxl import load_workbook
from pypdf import PdfReader

SUPPORTED = {
    ".txt",
    ".md",
    ".pdf",
    ".docx",
    ".xlsx",
    ".csv",
    ".tsv",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}
MAX_FILE = 20 * 1024 * 1024
MAX_TEXT = 120_000


def expand(paths):
    files = []
    for raw in paths:
        p = Path(raw)
        if p.is_symlink():
            raise ValueError("Symbolic-link inputs are not supported")
        if p.is_dir():
            files.extend(
                x
                for x in sorted(p.rglob("*"))
                if x.is_file()
                and not x.is_symlink()
                and not any(part.startswith(".") for part in x.relative_to(p).parts)
            )
        else:
            files.append(p)
    if not files or len(files) > 50:
        raise ValueError("Choose between 1 and 50 files")
    return files


def extract(path, assets):
    path = Path(path)
    ext = path.suffix.lower()
    if ext not in SUPPORTED:
        raise ValueError(
            f"Unsupported format: {path.name}; supported: {', '.join(sorted(SUPPORTED))}"
        )
    if path.stat().st_size > MAX_FILE:
        raise ValueError(f"{path.name}: exceeds the 20 MB input limit")
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    sid = "S" + digest[:16]
    result = {
        "id": sid,
        "name": path.name,
        "sha256": digest,
        "format": ext[1:],
        "segments": [],
        "warnings": [],
    }

    def add(text, location, image=None):
        text = str(text).strip()
        if not text and not image:
            return
        segment = {
            "id": f"{sid}-{len(result['segments']) + 1}",
            "location": location,
            "text": text,
        }
        if image:
            segment["image"] = image
        result["segments"].append(segment)

    def picture(blob, location):
        with Image.open(io.BytesIO(blob)) as im:
            if im.width * im.height > 25_000_000:
                raise ValueError("Image exceeds 25 million pixels")
            im.load()
            width, height = im.size
            im = im.convert("RGB")
            im.thumbnail((1600, 1600))
            buf = io.BytesIO()
            im.save(buf, format="PNG")
        filename = hashlib.sha256(buf.getvalue()).hexdigest() + ".png"
        assets.mkdir(parents=True, exist_ok=True)
        (assets / filename).write_bytes(buf.getvalue())
        add(
            f"Image attachment ({width} x {height}); visual content not yet interpreted.",
            location,
            filename,
        )

    if ext in {".txt", ".md"}:
        for n, chunk in enumerate(raw.decode("utf-8-sig").split("\n\n"), 1):
            add(chunk, f"paragraph {n}")
    elif ext in {".csv", ".tsv"}:
        rows = list(
            csv.reader(
                io.StringIO(raw.decode("utf-8-sig")),
                delimiter="\t" if ext == ".tsv" else ",",
            )
        )
        if sum(map(len, rows)) > 10_000:
            raise ValueError("Spreadsheet exceeds 10,000 cells")
        for n, row in enumerate(rows, 1):
            add(" | ".join(row), f"row {n}")
    elif ext == ".pdf":
        pdf = PdfReader(io.BytesIO(raw))
        if pdf.is_encrypted:
            raise ValueError("Encrypted PDF: provide an unlocked copy")
        if len(pdf.pages) > 100:
            raise ValueError("PDF exceeds 100 pages")
        result["warnings"].append(
            "PDF layout, vector diagrams, and reading order may be lost. No OCR is performed."
        )
        for n, page in enumerate(pdf.pages, 1):
            stream = page.get_contents()
            if stream and len(stream.get_data()) > 5_000_000:
                raise ValueError("PDF page content stream exceeds 5 MB")
            text = page.extract_text() or ""
            add(text, f"page {n}")
            if not text.strip():
                result["warnings"].append(
                    f"Page {n} has no extracted text; inspect scan/image evidence."
                )
            for j, img in enumerate(page.images, 1):
                picture(img.data, f"page {n}, embedded image {j}")
    elif ext in {".docx", ".xlsx"}:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            if sum(x.file_size for x in z.infolist()) > 80_000_000:
                raise ValueError("Expanded Office file exceeds 80 MB")
        if ext == ".docx":
            doc = Document(io.BytesIO(raw))
            # Preserve the document's interleaved paragraph/table order.
            from docx.table import Table

            for n, block in enumerate(doc.iter_inner_content(), 1):
                if isinstance(block, Table):
                    for r, row in enumerate(block.rows, 1):
                        add(
                            " | ".join(c.text for c in row.cells),
                            f"block {n}, table row {r}",
                        )
                else:
                    add(block.text, f"block {n}")
            result["warnings"].append(
                "DOCX headers, comments, tracked changes, text boxes and drawing relationships are not reconstructed."
            )
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                for name in z.namelist():
                    if name.startswith("word/media/"):
                        if Path(name).suffix.lower() in {
                            ".png",
                            ".jpg",
                            ".jpeg",
                            ".webp",
                        }:
                            picture(z.read(name), "embedded image " + Path(name).name)
                        else:
                            result["warnings"].append(
                                "Unsupported embedded image: " + Path(name).name
                            )
        else:
            book = load_workbook(io.BytesIO(raw), read_only=True, data_only=False)
            cells = 0
            result["warnings"].append(
                "XLSX formulas are preserved as expressions, not recalculated. Charts, images and styling are not interpreted."
            )
            for sheet in book:
                if sheet.max_row * sheet.max_column > 10_000:
                    raise ValueError("Spreadsheet exceeds 10,000 cells")
                for n, row in enumerate(sheet.iter_rows(values_only=True), 1):
                    cells += len(row)
                    if cells > 10_000:
                        raise ValueError("Workbook exceeds 10,000 cells")
                    if any(v is not None for v in row):
                        add(
                            " | ".join("" if v is None else str(v) for v in row),
                            f"{sheet.title}!row {n}",
                        )
            book.close()
    else:
        picture(raw, "image")
    if (
        sum(len(s["text"]) for s in result["segments"]) > MAX_TEXT
        or len(result["segments"]) > 2000
    ):
        raise ValueError(
            "Extracted content exceeds limit; split this collection into smaller projects"
        )
    if not result["segments"]:
        result["warnings"].append("No usable content was extracted")
    return result
