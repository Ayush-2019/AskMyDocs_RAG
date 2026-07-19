"""
Core data models shared across all pipeline stages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Document:
    """A source document before chunking."""
    doc_id: str
    title: str
    source_url: str
    content: str
    doc_type: str = "markdown"  # markdown | html | text
    ingested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Chunk:
    """A single retrievable unit produced by the ingestion pipeline."""
    chunk_id: str
    doc_id: str
    section_path: str          # e.g. "Guide > Auth > OAuth2"
    text: str                  # raw chunk text
    context_header: str        # "[section_path]\ntext" — used for embedding
    token_count: int
    source_url: str
    page_or_heading: str       # anchor for citation links
    embedding: list[float] | None = None


@dataclass
class ScoredChunk:
    """A chunk annotated with a retrieval or reranking score."""
    chunk: Chunk
    score: float
    source: str = ""           # "vector" | "bm25" | "rrf" | "reranked"


@dataclass
class CitationReport:
    """Result of post-generation citation validation."""
    valid_citations: set[int]
    invalid_citations: set[int]    # hallucinated source numbers
    uncited_sentences: list[str]   # factual sentences with no [Source N]
    citation_density: float        # fraction of sentences that are cited
    passed: bool                   # meets quality bar


@dataclass
class RAGResponse:
    """The final response returned to the caller."""
    answer: str
    sources: list[dict]            # [{source_index, doc_id, source_url, section_path}, ...]
    citation_report: dict
    query: str
    retrieval_count: int
    latency_ms: float
