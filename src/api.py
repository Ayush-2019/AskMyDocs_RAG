"""
FastAPI application — HTTP interface for the RAG pipeline.

Endpoints:
    POST /ask              — Ask a question, get an answer with citations
    POST /ingest/file      — Upload and ingest a document
    POST /ingest/directory — Ingest all docs in a directory
    GET  /health           — Health check
    GET  /stats            — Index statistics
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from src.pipeline import pipeline
from src.db import get_chunk_count

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configure logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)


# ---------------------------------------------------------------------------
# Lifespan: initialize pipeline on startup
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing RAG pipeline...")
    pipeline.initialize()
    logger.info("Pipeline ready.")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="Ask My Docs",
    description="Production RAG with hybrid retrieval, reranking, and citation enforcement.",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------
class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000, description="Your question")


class SourceInfo(BaseModel):
    source_index: int
    chunk_id: str
    doc_id: str
    source_url: str
    section_path: str
    heading: str
    relevance_score: float


class CitationReportResponse(BaseModel):
    valid_citations: list[int]
    invalid_citations: list[int]
    uncited_sentences: list[str]
    citation_density: float
    passed: bool


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceInfo]
    citation_report: CitationReportResponse
    query: str
    retrieval_count: int
    latency_ms: float


class IngestRequest(BaseModel):
    path: str = Field(..., description="Path to file or directory to ingest")
    base_url: str = Field("", description="Optional URL prefix for citations")


class IngestResponse(BaseModel):
    results: list[dict]
    total_chunks: int


class HealthResponse(BaseModel):
    status: str
    chunk_count: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.post("/ask", response_model=AskResponse)
async def ask_question(req: AskRequest):
    """Ask a question and receive a cited answer from your documents."""
    try:
        response = pipeline.ask(req.question)
        return AskResponse(
            answer=response.answer,
            sources=[SourceInfo(**s) for s in response.sources],
            citation_report=CitationReportResponse(**response.citation_report),
            query=response.query,
            retrieval_count=response.retrieval_count,
            latency_ms=response.latency_ms,
        )
    except Exception as e:
        logger.error(f"Error processing question: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest", response_model=IngestResponse)
async def ingest_documents(req: IngestRequest):
    """Ingest a file or directory of documents into the RAG index."""
    target = Path(req.path)

    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {req.path}")

    try:
        if target.is_file():
            result = pipeline.ingest_file(target, base_url=req.base_url)
            results = [result]
        elif target.is_dir():
            results = pipeline.ingest_directory(target, base_url=req.base_url)
        else:
            raise HTTPException(status_code=400, detail="Path is neither a file nor directory.")

        total_chunks = sum(r.get("chunks", 0) for r in results)
        return IngestResponse(results=results, total_chunks=total_chunks)

    except Exception as e:
        logger.error(f"Ingestion error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Check system health and index size."""
    try:
        count = get_chunk_count()
        return HealthResponse(status="healthy", chunk_count=count)
    except Exception as e:
        return HealthResponse(status=f"unhealthy: {e}", chunk_count=0)


@app.get("/stats")
async def get_stats():
    """Return detailed index statistics."""
    try:
        chunk_count = get_chunk_count()
        bm25_built = pipeline._initialized
        return {
            "chunk_count": chunk_count,
            "bm25_index_built": bm25_built,
            "embedding_model": pipeline.__class__.__name__,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Run directly: python -m src.api
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api:app", host="0.0.0.0", port=8000, reload=True)
