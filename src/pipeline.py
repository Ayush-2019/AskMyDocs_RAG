"""
RAG pipeline orchestrator.

This is the central coordinator that wires together:
    ingest → index → retrieve → rerank → generate → validate

It exposes two public methods:
    - ingest_file(): process and index a document
    - ask(): end-to-end question answering
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict
from pathlib import Path

from src.config import settings
from src.db import (
    create_tables,
    delete_document_chunks,
    get_chunk_count,
    insert_document,
)
from src.generator import (
    build_source_metadata,
    generate_answer,
    validate_citations,
)
from src.indexer import bm25_index, index_chunks
from src.ingest import chunk_document, parse_document
from src.models import RAGResponse
from src.reranker import rerank
from src.retriever import hybrid_retrieve

logger = logging.getLogger(__name__)


class RAGPipeline:
    """
    End-to-end RAG pipeline.

    Usage:
        pipeline = RAGPipeline()
        pipeline.initialize()                        # create tables, load BM25
        pipeline.ingest_file(Path("docs/setup.md"))  # add a document
        response = pipeline.ask("How do I configure OAuth?")
    """

    def __init__(self):
        self._initialized = False

    def initialize(self) -> None:
        """Create DB tables and build the BM25 index from existing chunks."""
        create_tables()
        bm25_index.build()
        self._initialized = True
        count = get_chunk_count()
        logger.info(f"Pipeline initialized. {count} chunks in database.")

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            self.initialize()

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------
    def ingest_file(self, filepath: Path, base_url: str = "") -> dict:
        """
        Parse, chunk, embed, and index a single document.

        Args:
            filepath: Path to a .md, .html, or .txt file.
            base_url: Optional URL prefix for source citations.

        Returns:
            Summary dict with doc_id and chunk count.
        """
        self._ensure_initialized()

        filepath = filepath.resolve()

        doc = parse_document(filepath, base_url=base_url)
        logger.info(f"Parsed document: {doc.title} ({doc.doc_id})")

        # Remove old chunks if re-ingesting the same document
        deleted = delete_document_chunks(doc.doc_id)
        if deleted:
            logger.info(f"Removed {deleted} old chunks for doc {doc.doc_id}.")

        # Register document in DB
        insert_document(doc.doc_id, doc.title, doc.source_url, doc.doc_type)

        # Chunk the document
        chunks = chunk_document(doc)
        if not chunks:
            logger.warning(f"No chunks produced from {filepath}")
            return {"doc_id": doc.doc_id, "chunks": 0}

        # Embed and store in pgvector
        index_chunks(chunks)

        # Update the in-memory BM25 index
        bm25_index.add_chunks(chunks)

        return {
            "doc_id": doc.doc_id,
            "title": doc.title,
            "chunks": len(chunks),
            "source_url": doc.source_url,
        }

    def ingest_directory(self, dirpath: Path, base_url: str = "") -> list[dict]:
        """Ingest all supported files in a directory."""
        self._ensure_initialized()
        supported = {".md", ".html", ".htm", ".txt"}
        results = []

        for filepath in sorted(dirpath.rglob("*")):
            if filepath.suffix.lower() in supported and filepath.is_file():
                try:
                    result = self.ingest_file(filepath, base_url=base_url)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Failed to ingest {filepath}: {e}")
                    results.append({"file": str(filepath), "error": str(e)})

        total_chunks = sum(r.get("chunks", 0) for r in results)
        logger.info(
            f"Ingested {len(results)} files, {total_chunks} total chunks."
        )
        return results

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------
    def ask(self, query: str) -> RAGResponse:
        """
        End-to-end RAG: retrieve → rerank → generate → validate.

        Args:
            query: The user's natural language question.

        Returns:
            RAGResponse with answer, sources, citation report, and latency.
        """
        self._ensure_initialized()
        t0 = time.perf_counter()

        # Stage 1: Hybrid retrieval (vector + BM25, fused via RRF)
        candidates = hybrid_retrieve(query)
        logger.info(f"Retrieved {len(candidates)} candidates.")

        # Stage 2: Cross-encoder reranking
        reranked = rerank(query, candidates)
        logger.info(f"Reranked to {len(reranked)} chunks.")

        # Stage 3: Generate answer with citations
        answer = generate_answer(query, reranked)

        # Stage 4: Validate citations
        citation_report = validate_citations(answer, num_sources=len(reranked))

        # Build response
        latency_ms = (time.perf_counter() - t0) * 1000
        sources = build_source_metadata(reranked)

        response = RAGResponse(
            answer=answer,
            sources=sources,
            citation_report={
                "valid_citations": sorted(citation_report.valid_citations),
                "invalid_citations": sorted(citation_report.invalid_citations),
                "uncited_sentences": citation_report.uncited_sentences,
                "citation_density": round(citation_report.citation_density, 3),
                "passed": citation_report.passed,
            },
            query=query,
            retrieval_count=len(candidates),
            latency_ms=round(latency_ms, 1),
        )

        logger.info(
            f"RAG complete: {latency_ms:.0f}ms, "
            f"citations={'PASS' if citation_report.passed else 'FAIL'}, "
            f"density={citation_report.citation_density:.2f}"
        )
        return response


# Module-level singleton
pipeline = RAGPipeline()
