"""Regression fixtures from docs/pdf-profiel-extractie.md §9."""

from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.pdf_extract import PdfExtractError, extract_from_bytes, extract_from_page_texts

GOLD_A50 = [
    ("0115850", 2), ("0170316", 2), ("0170320", 2), ("0170320", 25),
    ("0171336", 50), ("1006661", 14), ("3001924", 1), ("3001927", 53),
    ("3001939", 10), ("3001961", 18), ("3001964", 1), ("3001971", 1),
    ("3001971", 1), ("3001972", 4), ("3001973", 7), ("3001981", 13),
    ("3001983", 1), ("3001983", 4), ("3001992", 1), ("3001993", 2),
]
GOLD_B30 = [
    ("0170315", 2), ("0170316", 2), ("0170319", 20), ("0170320", 21),
    ("0170769", 2), ("0171336", 14), ("1006661", 29), ("3001927", 12),
    ("3001940", 19), ("3001964", 40), ("3002007", 20), ("803733", 3),
    ("803734", 3),
]


def _row(profiel, artikel, aantal, lengte="6.000"):
    meters = aantal * int(lengte.split(".")[0])
    # Glue L60 to aantal like naive pypdf (§6.2).
    return (
        f"{profiel} {artikel} KWN {profiel.split('-')[0]} LEKDORPEL "
        f"003 KP+ R9001 L60 / KP+ R9001 L60{aantal} {lengte} {meters} 2,69 6,96"
    )


def _page(project, rows, heading="Artikeloverzicht - Profielen 25-6-2026"):
    lines = [
        "Rollecate B.V.",
        heading,
        "14:27:34",
        "Pagina 1    van: 2",
        "Project Naam Rambo project Omschrijving",
        f"{project[:9]} Test {project[:9]}-01 WVB",
        f"Project: {project}",
        "Categorie: 200-10-1 Alcoa",
        "Profiel  Artikelnummer  Omschrijving  OppBeh  Omschrijving  Aantal  Staflengte  Meters  Gewicht (KG)  Afval %",
    ]
    for i, (nummer, aantal) in enumerate(rows):
        suffix = "60" if nummer == "1006661" else "00360"
        artikel = "1006661" if nummer == "1006661" else "1006211"
        if nummer == "1006661":
            lines.append(
                f"{nummer}-{suffix} {artikel} KWN 0117144-100-600 ESPAGNOLETSTANG TECHNISC "
                f"{aantal} 6.000 {aantal * 6} 12,68 15,41"
            )
        else:
            lines.append(_row(f"{nummer}-{suffix}", artikel, aantal))
    lines.append("Totaal: 1.297 1.341,22")
    return "\n".join(lines)


def test_gold_a50_from_text():
    page = _page("012510375A50", GOLD_A50)
    out = extract_from_page_texts([page, "Artikeloverzicht - Oppervlaktebehandeling\nProject: 012510375A50"])
    assert out.project == "012510375A50"
    assert [(r.profielnummer, r.aantal) for r in out.rows] == GOLD_A50
    assert sum(r.aantal for r in out.rows) == 212


def test_gold_b30_keeps_hueck_six_digits():
    page = _page("012510039B30", GOLD_B30)
    out = extract_from_page_texts([page])
    assert out.project == "012510039B30"
    assert [(r.profielnummer, r.aantal) for r in out.rows] == GOLD_B30
    assert sum(r.aantal for r in out.rows) == 187


def test_skips_oppervlaktebehandeling_only_pdf():
    with pytest.raises(PdfExtractError):
        extract_from_page_texts([
            "Rollecate B.V.\nArtikeloverzicht - Oppervlaktebehandeling 21-7-2025\nProject: 012510375A50"
        ])


def test_does_not_use_rambo_or_filename_shape():
    page = _page("012510375A50", GOLD_A50[:1])
    out = extract_from_page_texts([page])
    assert out.project == "012510375A50"
    assert "-" not in out.project


def test_duplicate_profile_rows_kept():
    page = _page("012510375A50", [("0170320", 2), ("0170320", 25)])
    out = extract_from_page_texts([page])
    assert [r.aantal for r in out.rows] == [2, 25]


def _write_pdf(path: Path, text: str) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    y = 800
    for line in text.splitlines():
        c.drawString(20, y, line[:120])
        y -= 12
        if y < 40:
            c.showPage()
            y = 800
    c.save()


def test_extract_from_real_pdf(tmp_path):
    page = _page("012510375A50", GOLD_A50)
    pdf = tmp_path / "a50.pdf"
    _write_pdf(pdf, page)
    out = extract_from_bytes(pdf.read_bytes())
    assert out.project == "012510375A50"
    assert len(out.rows) == 20
    assert sum(r.aantal for r in out.rows) == 212
