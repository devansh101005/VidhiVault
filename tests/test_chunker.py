# tests/test_chunker.py

from app.core.chunker import chunk_document, ChunkingConfig


def sample_pages():
    return [
        {
            "page_number": 1,
            "text": "SECTION 1. " + ("This is a legal paragraph discussing rights and duties. " * 10)
                    + "\n\n" + ("This is another paragraph with additional legal content. " * 10)
        },
        {
            "page_number": 2,
            "text": "SECTION 2. " + ("More legal content about procedures and remedies. " * 10)
                    + "\n\n" + ("Another paragraph here with further details. " * 10)
        }
    ]


def test_chunk_size_limit():
    config = ChunkingConfig(chunk_size=50, chunk_overlap=5, min_chunk_size=10)
    chunks = chunk_document(sample_pages(), config)

    assert len(chunks) > 0
    # chunk_size is the pre-overlap target; final content = chunk_size + chunk_overlap
    assert all(c["token_count"] <= config.chunk_size + config.chunk_overlap for c in chunks)


def test_overlap_exists():
    config = ChunkingConfig(chunk_size=50, chunk_overlap=5, min_chunk_size=10)
    chunks = chunk_document(sample_pages(), config)

    assert len(chunks) > 1
    prev = chunks[0]["content"].split()
    curr = chunks[1]["content"].split()

    assert prev[-5:] == curr[:5]


def test_page_numbers():
    chunks = chunk_document(sample_pages(), ChunkingConfig(min_chunk_size=10))

    assert len(chunks) > 0
    assert all("page_number" in c for c in chunks)


def test_section_headers():
    chunks = chunk_document(sample_pages(), ChunkingConfig(min_chunk_size=10))

    assert len(chunks) > 0
    assert any(c["section_header"] is not None for c in chunks)