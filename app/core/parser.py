import re
from typing import List, Dict, Any

import fitz  # PyMuPDF
import pdfplumber #fallback



def clean_text(text: str) -> str:
    """Basic normalization + unicode cleanup"""
    if not text:
        return ""

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)

    # Remove weird unicode artifacts
    text = text.replace("\u00a0", " ")  # non-breaking space

    return text.strip()


def detect_repeated_lines(pages: List[str], threshold: float = 0.6):
    """
    Detect lines that repeat across many pages (headers/footers)
    """
    line_freq = {}

    for text in pages:
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        unique_lines = set(lines)

        for line in unique_lines:
            line_freq[line] = line_freq.get(line, 0) + 1

    total_pages = len(pages)
    repeated = {
        line
        for line, count in line_freq.items()
        if count / total_pages >= threshold
    }

    return repeated


def remove_headers_footers(text: str, repeated_lines: set):
    lines = text.split("\n")
    filtered = [l for l in lines if l.strip() not in repeated_lines]
    return "\n".join(filtered)


def extract_metadata(first_page_text: str) -> Dict[str, Any]:
    """
    Very heuristic-based extraction (legal docs are inconsistent)
    """
    metadata = {}

    # Case title (often first non-empty line)
    lines = [l.strip() for l in first_page_text.split("\n") if l.strip()]
    if lines:
        metadata["case_title"] = lines[0]

    # Court name (look for keywords) (add more)
    court_match = re.search(
        r"(SUPREME COURT.*|HIGH COURT.*|DISTRICT COURT.*)",
        first_page_text,
        re.IGNORECASE,
    )
    if court_match:
        metadata["court"] = court_match.group(1)

    # Date (simple pattern)
    date_match = re.search(
        r"\b\d{1,2}\s+[A-Za-z]+\s+\d{4}\b",
        first_page_text,
    )
    if date_match:
        metadata["date"] = date_match.group(0)

    return metadata

def is_garbled(text: str) -> bool:
    """
    Detect if extracted text is garbage (common with bad encodings)
    """
    if not text:
        return True

    # heuristic: too many weird characters or too short
    weird_ratio = sum(1 for c in text if not c.isalnum() and not c.isspace()) / max(len(text), 1)

    return weird_ratio > 0.4 or len(text.strip()) < 20


def extract_with_pdfplumber(file_path: str):
    pages = []

    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            pages.append(
                {
                    "page_number": i + 1,
                    "text": clean_text(text),
                    "tables": [],
                }
            )

    return pages


def parse_pdf(file_path: str) -> dict:
    import fitz

    doc = fitz.open(file_path)

    raw_pages = []
    page_texts = []

    # First pass (PyMuPDF)
    for page in doc:
        text = page.get_text("text")
        raw_pages.append(text)
        page_texts.append(text)

        # Detect garbled output
    if all(is_garbled(t) for t in page_texts):
        print("PyMuPDF failed, falling back to pdfplumber")

        pages_output = extract_with_pdfplumber(file_path)

        return {
            "pages": pages_output,
            "metadata": extract_metadata(pages_output[0]["text"] if pages_output else ""),
        }

    # Detect repeating headers/footers
    repeated_lines = detect_repeated_lines(page_texts)

    pages_output = []

    # Second pass: clean + structure
    for i, page in enumerate(doc):
        raw_text = raw_pages[i]

        # Remove headers/footers
        cleaned = remove_headers_footers(raw_text, repeated_lines)

        # Normalize
        cleaned = clean_text(cleaned)

        # Tables (basic placeholder)
        tables = []
        try:
            tables = page.get_text("blocks")
        except Exception:
            tables = []

        pages_output.append(
            {
                "page_number": i + 1,
                "text": cleaned,
                "tables": tables,
            }
        )

    # Extract metadata from first page
    metadata = extract_metadata(raw_pages[0] if raw_pages else "")

    return {
        "pages": pages_output,
        "metadata": metadata,
    }