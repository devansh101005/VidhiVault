# tests/test_parser.py

import pytest
from app.core.parser import parse_pdf


# ---------------------------
# Test 1: Clean PDF
# ---------------------------
def test_parse_clean_pdf():
    result = parse_pdf("tests/sample_clean.pdf")

    assert "pages" in result
    assert len(result["pages"]) > 0

    first_page = result["pages"][0]
    assert "text" in first_page
    assert len(first_page["text"]) > 50


# ---------------------------
# Test 2: Scanned PDF
# ---------------------------
@pytest.mark.skip(reason="i dont have a scanned pdf lol")
def test_parse_scanned_pdf():
    result = parse_pdf("tests/sample_scanned.pdf")

    pages = result["pages"]

    # Expect minimal or empty text
    texts = [p["text"] for p in pages]

    assert all(len(t.strip()) < 50 for t in texts)
    

# ---------------------------
# Test 3: Multi-column PDF
# ---------------------------
def test_parse_multicolumn_pdf():
    result = parse_pdf("tests/sample_multicolumn.pdf")

    pages = result["pages"]

    assert len(pages) > 0

    # Ensure text is not empty
    assert any(len(p["text"]) > 100 for p in pages)


# ---------------------------
# Test 4: Metadata extraction
# ---------------------------
def test_metadata_extraction():
    result = parse_pdf("tests/sample_clean.pdf")

    metadata = result["metadata"]

    assert isinstance(metadata, dict)
    # Not strict because extraction is heuristic
    assert "case_title" in metadata or "court" in metadata