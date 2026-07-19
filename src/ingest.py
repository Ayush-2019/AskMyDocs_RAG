"""
Document ingestion pipeline.

Parses Markdown, HTML, or plain-text files into hierarchy-aware chunks
that preserve section context for better embedding quality.
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

from src.config import settings
from src.models import Chunk, Document

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Token counting (whitespace-based approximation; ~1.3 tokens per word)
# ---------------------------------------------------------------------------
def estimate_tokens(text: str) -> int:
    words = text.split()
    return int(len(words) * 1.3)


# ---------------------------------------------------------------------------
# Markdown section parser
# ---------------------------------------------------------------------------
class _Section:
    """A node in the document section tree."""

    def __init__(self, title: str, level: int, parent: _Section | None = None):
        self.title = title
        self.level = level
        self.parent = parent
        self.paragraphs: list[str] = []
        self.children: list[_Section] = []

    def ancestry(self) -> list[str]:
        """Return ancestor titles from root to this section."""
        chain: list[str] = []
        node: _Section | None = self
        while node and node.title:
            chain.append(node.title)
            node = node.parent
        chain.reverse()
        return chain


def _parse_markdown_sections(content: str) -> list[_Section]:
    """
    Parse markdown into a flat list of sections, each knowing its
    parent chain. Handles # through ###### heading levels.
    """
    lines = content.split("\n")
    root = _Section(title="", level=0)
    sections: list[_Section] = [root]
    current = root
    stack: list[_Section] = [root]

    for line in lines:
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
        if heading_match:
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()

            # Walk up the stack to find the correct parent
            while len(stack) > 1 and stack[-1].level >= level:
                stack.pop()

            parent = stack[-1]
            section = _Section(title=title, level=level, parent=parent)
            parent.children.append(section)
            sections.append(section)
            stack.append(section)
            current = section
        else:
            stripped = line.strip()
            if stripped:
                current.paragraphs.append(stripped)

    return sections


# ---------------------------------------------------------------------------
# Text splitter with overlap
# ---------------------------------------------------------------------------
def _split_text_with_overlap(
    text: str,
    max_tokens: int,
    overlap_tokens: int,
) -> list[str]:
    """
    Split text into chunks of approximately max_tokens,
    with overlap_tokens of overlap between consecutive chunks.
    Splits at sentence boundaries when possible.
    """
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    current_chunk: list[str] = []
    current_tokens = 0

    for sentence in sentences:
        sent_tokens = estimate_tokens(sentence)

        if current_tokens + sent_tokens > max_tokens and current_chunk:
            chunks.append(" ".join(current_chunk))

            # Build overlap from the tail of the current chunk
            overlap_chunk: list[str] = []
            overlap_count = 0
            for s in reversed(current_chunk):
                t = estimate_tokens(s)
                if overlap_count + t > overlap_tokens:
                    break
                overlap_chunk.insert(0, s)
                overlap_count += t

            current_chunk = overlap_chunk
            current_tokens = overlap_count

        current_chunk.append(sentence)
        current_tokens += sent_tokens

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def parse_document(filepath: Path, base_url: str = "") -> Document:
    """Read a file from disk and return a Document model."""
    content = filepath.read_text(encoding="utf-8")
    doc_id = hashlib.sha256(str(filepath).encode()).hexdigest()[:16]
    title = filepath.stem.replace("-", " ").replace("_", " ").title()
    source_url = base_url or filepath.as_uri() if hasattr(filepath, "as_uri") else str(filepath)

    suffix = filepath.suffix.lower()
    doc_type = {".md": "markdown", ".html": "html", ".htm": "html"}.get(suffix, "text")

    return Document(
        doc_id=doc_id,
        title=title,
        source_url=str(source_url),
        content=content,
        doc_type=doc_type,
    )


def chunk_document(doc: Document) -> list[Chunk]:
    """
    Split a Document into Chunks using hierarchy-aware parsing.

    Each chunk's context_header prepends the section path to the text,
    producing better embeddings via "contextual retrieval."
    """
    cfg = settings.chunking
    chunks: list[Chunk] = []

    if doc.doc_type == "markdown":
        sections = _parse_markdown_sections(doc.content)
    else:
        # For plain text or HTML, treat the whole doc as one section
        root = _Section(title=doc.title, level=1)
        root.paragraphs = [p for p in doc.content.split("\n\n") if p.strip()]
        sections = [root]

    for section in sections:
        if not section.paragraphs:
            continue

        section_text = " ".join(section.paragraphs)
        section_path = " > ".join(section.ancestry()) or doc.title
        heading = section.title or doc.title

        # Split into sub-chunks if the section is too long
        text_pieces = _split_text_with_overlap(
            section_text,
            max_tokens=cfg.max_tokens,
            overlap_tokens=cfg.overlap_tokens,
        )

        for i, piece in enumerate(text_pieces):
            token_count = estimate_tokens(piece)
            if token_count < cfg.min_tokens:
                continue

            chunk_id = hashlib.sha256(
                f"{doc.doc_id}:{section_path}:{i}".encode()
            ).hexdigest()[:20]

            # Contextual header: section ancestry prepended for richer embeddings
            context_header = f"[{section_path}]\n{piece}"

            chunks.append(Chunk(
                chunk_id=chunk_id,
                doc_id=doc.doc_id,
                section_path=section_path,
                text=piece,
                context_header=context_header,
                token_count=token_count,
                source_url=doc.source_url,
                page_or_heading=heading,
            ))

    logger.info(f"Chunked '{doc.title}' into {len(chunks)} chunks.")
    return chunks
