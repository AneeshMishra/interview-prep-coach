import io

import docx
import pytest

from app.ingestion.docx_parser import content_hash, parse_docx


def make_docx(tmp_path, paragraphs_with_headings):
    document = docx.Document()
    for text, is_heading in paragraphs_with_headings:
        if is_heading:
            document.add_heading(text, level=1)
        else:
            document.add_paragraph(text)
    path = tmp_path / "sample.docx"
    document.save(path)
    return path


def test_parse_docx_splits_on_headings(tmp_path):
    path = make_docx(
        tmp_path,
        [
            ("Amazon - Backend Engineer", True),
            ("Round 1: Tell me about yourself.", False),
            ("Round 2: System Design", True),
            ("Design a URL shortener.", False),
        ],
    )
    sections = parse_docx(str(path))
    headings = [s.heading for s in sections]
    assert "Amazon - Backend Engineer" in headings
    assert "Round 2: System Design" in headings


def test_content_hash_is_deterministic():
    data = b"same bytes"
    assert content_hash(data) == content_hash(data)


def test_content_hash_differs_for_different_content():
    assert content_hash(b"a") != content_hash(b"b")
