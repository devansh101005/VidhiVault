# app/core/chunker.py

import re
from typing import List, Dict, Optional


class ChunkingConfig:
    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        min_chunk_size: int = 30,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size


# ---------------------------
# Tokenizer (simple)
# ---------------------------
def count_tokens(text: str) -> int:
    return len(text.split())


# ---------------------------
# Section detection
# ---------------------------
SECTION_PATTERNS = [
    r"(SECTION\s+\d+\.?)",
    r"(ARTICLE\s+[IVXLC]+)",
    r"(^\d+\.\s)",
    r"(ORDER\s+[IVXLC]+)",
]


def split_sections(text: str):
    pattern = "|".join(SECTION_PATTERNS)
    splits = re.split(pattern, text, flags=re.IGNORECASE)

    sections = []
    current_header = None

    for part in splits:
        if part is None:
            continue
        part = part.strip()
        if not part:
            continue

        if any(re.match(p, part, re.IGNORECASE) for p in SECTION_PATTERNS):
            current_header = part
        else:
            sections.append((current_header, part))

    return sections


# ---------------------------
# Paragraph + sentence split
# ---------------------------
def split_paragraphs(text: str):
    return [p.strip() for p in text.split("\n\n") if p.strip()]


def split_sentences(text: str):
    return re.split(r"(?<=[.!?])\s+", text)


# ---------------------------
# Core chunk builder
# ---------------------------
def build_chunks_from_text(
    text: str,
    page_number: int,
    section_header: Optional[str],
    config: ChunkingConfig,
):
    paragraphs = split_paragraphs(text)

    chunks = []
    current_chunk = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = count_tokens(para)

        # If paragraph itself is too big → split sentences
        if para_tokens > config.chunk_size:
            sentences = split_sentences(para)

            for sent in sentences:
                sent_tokens = count_tokens(sent)

                if current_tokens + sent_tokens > config.chunk_size:
                    if current_tokens >= config.min_chunk_size:
                        chunks.append((current_chunk, page_number, section_header))

                    current_chunk = []
                    current_tokens = 0

                current_chunk.append(sent)
                current_tokens += sent_tokens

        else:
            if current_tokens + para_tokens > config.chunk_size:
                if current_tokens >= config.min_chunk_size:
                    chunks.append((current_chunk, page_number, section_header))

                current_chunk = []
                current_tokens = 0

            current_chunk.append(para)
            current_tokens += para_tokens

    if current_chunk:
        chunks.append((current_chunk, page_number, section_header))

    return chunks


# ---------------------------
# Add overlap
# ---------------------------
def apply_overlap(chunks: List[Dict], config: ChunkingConfig):
    overlapped = []

    for i, chunk in enumerate(chunks):
        content_tokens = chunk["content"].split()

        if i > 0:
            prev_tokens = overlapped[-1]["content"].split()
            overlap_tokens = prev_tokens[-config.chunk_overlap:]
            content_tokens = overlap_tokens + content_tokens

        chunk["content"] = " ".join(content_tokens)
        chunk["token_count"] = len(content_tokens)

        overlapped.append(chunk)

    return overlapped


# ---------------------------
# Main function
# ---------------------------
def chunk_document(pages: List[Dict], config: ChunkingConfig) -> List[Dict]:
    all_chunks = []
    chunk_index = 0

    for page in pages:
        page_number = page["page_number"]
        text = page["text"]

        sections = split_sections(text)

        for section_header, section_text in sections:
            raw_chunks = build_chunks_from_text(
                section_text,
                page_number,
                section_header,
                config,
            )

            for chunk_text_parts, page_number, section_header in raw_chunks:
                content = " ".join(chunk_text_parts).strip()

                if count_tokens(content) < config.min_chunk_size:
                    continue

                all_chunks.append({
                    "content": content,
                    "page_number": page_number,
                    "chunk_index": chunk_index,
                    "section_header": section_header,
                    "token_count": count_tokens(content),
                })

                chunk_index += 1

    # apply overlap
    all_chunks = apply_overlap(all_chunks, config)

    return all_chunks