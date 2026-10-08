"""Extract project number, profile numbers and quantities from Rollecate PDFs.

Implements docs/pdf-profiel-extractie.md. Do not change that spec from here.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

from pypdf import PdfReader

HEADING_PROFIELEN = "Artikeloverzicht - Profielen"
HEADING_OPPERVLAK = "Artikeloverzicht - Oppervlaktebehandeling"

PROJECT_RE = re.compile(r"Project\s*:\s*([0-9]{9}[A-Za-z][0-9]{2})")
ROW_START_RE = re.compile(r"^\s*(\d{6,})-(\d+)\b")
# §6.2 tail: {Aantal} {Staflengte} {Meters} {Gewicht} {Afval%}
# OppBeh `L60`/`L20` is often glued to Aantal (`L6025` = 25). Optional prefix.
TAIL_RE = re.compile(
    r"(?:L\d{2})?(\d+)\s+(\d\.\d{3})\s+(\d+)\s+(\d+,\d{2})\s+(\d+,\d{2})\s*$"
)


class PdfExtractError(ValueError):
    """PDF is not an in-scope Artikeloverzicht - Profielen export."""


@dataclass
class ExtractedLine:
    profielnummer: str
    aantal: int


@dataclass
class ExtractedProject:
    project: str
    rows: list[ExtractedLine] = field(default_factory=list)


def extract_from_bytes(data: bytes) -> ExtractedProject:
    reader = PdfReader(io.BytesIO(data))
    pages_text: list[str] = []
    for page in reader.pages:
        pages_text.append(page.extract_text() or "")
    return extract_from_page_texts(pages_text)


def extract_from_page_texts(pages: list[str]) -> ExtractedProject:
    """Same algorithm as PDF bytes, useful for tests without a binary PDF."""
    in_scope_texts: list[str] = []
    for text in pages:
        if _page_in_scope(text):
            in_scope_texts.append(text)

    if not in_scope_texts:
        raise PdfExtractError(
            "Dit bestand is geen Artikeloverzicht - Profielen. "
            "Pagina's met Oppervlaktebehandeling worden overgeslagen."
        )

    project = ""
    rows: list[ExtractedLine] = []
    for text in in_scope_texts:
        if not project:
            match = PROJECT_RE.search(text)
            if match:
                project = match.group(1)
        rows.extend(_rows_from_page(text))

    if not project:
        raise PdfExtractError(
            "Geen projectnummer gevonden (verwacht label 'Project:' "
            "met 9 cijfers + letter + 2 cijfers)."
        )
    if not rows:
        raise PdfExtractError("Geen profielregels gevonden op de Profielen-pagina's.")

    return ExtractedProject(project=project, rows=rows)


def _page_in_scope(text: str) -> bool:
    head = _head_sample(text)
    if HEADING_OPPERVLAK in head or HEADING_OPPERVLAK in text:
        # Heading may sit slightly below the first 15 lines; still skip.
        if HEADING_OPPERVLAK in text and HEADING_PROFIELEN not in text:
            return False
        if HEADING_OPPERVLAK in head:
            return False
    return HEADING_PROFIELEN in text


def _head_sample(text: str) -> str:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines[:15])


def _rows_from_page(text: str) -> list[ExtractedLine]:
    raw_lines = text.splitlines()
    joined: list[str] = []
    buf = ""
    for line in raw_lines:
        stripped = line.strip()
        if not stripped:
            continue
        if ROW_START_RE.match(stripped):
            if buf:
                joined.append(buf)
            buf = stripped
            continue
        if buf and not _is_page_chrome(stripped):
            buf = buf + " " + stripped
            continue
        if buf:
            joined.append(buf)
            buf = ""
    if buf:
        joined.append(buf)

    rows: list[ExtractedLine] = []
    for line in joined:
        start = ROW_START_RE.match(line)
        if not start:
            continue
        aantal = _aantal_from_line(line)
        if aantal is None:
            continue
        rows.append(ExtractedLine(profielnummer=start.group(1), aantal=aantal))
    return rows


def _is_page_chrome(line: str) -> bool:
    if line.startswith("Categorie:"):
        return True
    if line.startswith("Totaal:"):
        return True
    if line.startswith("Profiel"):
        return True
    if line.startswith("Artikeloverzicht"):
        return True
    if line.startswith("Pagina"):
        return True
    if line.startswith("Rollecate"):
        return True
    if line.startswith("Project"):
        return True
    return False


def _aantal_from_line(line: str) -> int | None:
    tail = TAIL_RE.search(line)
    if not tail:
        return None
    return int(tail.group(1))
