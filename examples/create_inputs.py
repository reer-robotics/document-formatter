"""Generate small synthetic parser fixtures; no company data is used."""

from pathlib import Path

from docx import Document
from openpyxl import Workbook
from PIL import Image, ImageDraw
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent


def create(root=ROOT):
    inputs = root / "inputs"
    extra = root / "additional"
    inputs.mkdir(parents=True, exist_ok=True)
    extra.mkdir(parents=True, exist_ok=True)
    (inputs / "01-field-notes.md").write_text("""# Synthetic pickup investigation

Question: Does approach angle affect alignment in a simulator?

Sample count: 20 runs

Observed retries occurred at higher approach angles. This is an observation, not evidence of causation.

TODO: record simulator version and repeat the test with a fixed seed.
""")
    (inputs / "02-measurements.csv").write_text(
        "approach_degrees,attempts,retries\n0,10,1\n15,10,3\n"
    )
    image = Image.new("RGB", (800, 460), "#f4f5ef")
    draw = ImageDraw.Draw(image)
    draw.text((30, 25), "SYNTHETIC EXAMPLE - retries by approach angle", fill="#183c32")
    draw.line((100, 90, 100, 350), fill="#183c32", width=2)
    draw.line((100, 350, 720, 350), fill="#183c32", width=2)
    for x, height, label in [
        (220, 70, "0 degrees: 1 retry / 10 attempts"),
        (470, 210, "15 degrees: 3 retries / 10 attempts"),
    ]:
        draw.rectangle((x, 350 - height, x + 100, 350), fill="#287a58")
        draw.text((x - 35, 380), label, fill="#183c32")
    draw.text((110, 70), "Retries (count)", fill="#183c32")
    image.save(inputs / "03-retry-chart.png")
    pdf = canvas.Canvas(str(inputs / "04-method.pdf"), pagesize=(612, 792))
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(54, 730, "Synthetic method note")
    pdf.setFont("Helvetica", 11)
    for y, line in enumerate(
        [
            "This fixture describes a simulated pickup investigation.",
            "Two approach angles were compared: 0 and 15 degrees.",
            "Sample count: 20 runs",
            "No production authorization or real experiment is implied.",
        ]
    ):
        pdf.drawString(54, 690 - y * 22, line)
    pdf.save()
    doc = Document()
    doc.add_heading("Synthetic reviewer note", 0)
    doc.add_paragraph(
        "The measurements show an association. A controlled repeat is needed before assigning a cause."
    )
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Gap"
    table.rows[0].cells[1].text = "Action"
    table.add_row().cells[0].text = "Simulator version missing"
    table.rows[1].cells[1].text = "Record the version before repeating"
    doc.save(inputs / "05-review-note.docx")
    book = Workbook()
    sheet = book.active
    sheet.title = "Trials"
    for row in [
        ("Approach degrees", "Attempts", "Retries"),
        (0, 10, 1),
        (15, 10, 3),
        ("Total", "=SUM(B2:B3)", "=SUM(C2:C3)"),
    ]:
        sheet.append(row)
    sheet.column_dimensions["A"].width = 24
    sheet.column_dimensions["B"].width = 16
    sheet.column_dimensions["C"].width = 16
    book.save(inputs / "06-trials.xlsx")
    (extra / "follow-up.txt").write_text(
        "Synthetic follow-up memo\n\nSample count: 25 runs\n\nThe newer memo lists 25 runs but does not explain whether these replace or extend the original 20. Resolve the discrepancy before combining totals.\n"
    )
    return inputs, extra


if __name__ == "__main__":
    create()
    print(
        "Generated synthetic PDF, DOCX, XLSX, CSV, Markdown, PNG and incremental TXT examples."
    )
