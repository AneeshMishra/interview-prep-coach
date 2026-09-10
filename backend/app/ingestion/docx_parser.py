"""
DOCX -> raw text/table extraction.
Keep this dumb on purpose: structuring/interpretation happens in structurer.py.
"""
import hashlib
from dataclasses import dataclass, field

import docx


@dataclass
class RawSection:
    heading: str | None
    paragraphs: list[str] = field(default_factory=list)
    tables: list[list[list[str]]] = field(default_factory=list)


def content_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def parse_docx(file_path: str) -> list[RawSection]:
    """
    Walk the document splitting on heading paragraphs.
    Anything before the first heading is grouped under heading=None.
    """
    document = docx.Document(file_path)
    sections: list[RawSection] = [RawSection(heading=None)]

    for para in document.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        if para.style.name and para.style.name.lower().startswith("heading"):
            sections.append(RawSection(heading=text))
        else:
            sections[-1].paragraphs.append(text)

    # Tables aren't anchored to paragraph position in python-docx; attach to
    # the last section as a reasonable default for v1.
    for table in document.tables:
        rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
        sections[-1].tables.append(rows)

    return [s for s in sections if s.paragraphs or s.tables]
