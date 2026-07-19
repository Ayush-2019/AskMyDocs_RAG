"""
Database layer — PostgreSQL with pgvector.

Handles connection pooling, schema creation, chunk storage, and vector search.
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from typing import Generator

import psycopg2
import psycopg2.extras
import psycopg2.pool
from pgvector.psycopg2 import register_vector

from src.config import settings
from src.models import Chunk

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Connection pool (module-level singleton, lazily initialized)
# ---------------------------------------------------------------------------
_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            dsn=settings.database.dsn,
        )
    return _pool


@contextmanager
def get_conn() -> Generator:
    pool = get_pool()
    conn = pool.getconn()
    try:
        register_vector(conn)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


# ---------------------------------------------------------------------------
# Schema management
# ---------------------------------------------------------------------------
def create_tables() -> None:
    """Create the pgvector extension and all required tables."""
    dim = settings.embedding.dimension
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id      TEXT PRIMARY KEY,
                    title       TEXT NOT NULL,
                    source_url  TEXT NOT NULL,
                    doc_type    TEXT NOT NULL DEFAULT 'markdown',
                    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
            """)

            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id        TEXT PRIMARY KEY,
                    doc_id          TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
                    section_path    TEXT NOT NULL,
                    text            TEXT NOT NULL,
                    context_header  TEXT NOT NULL,
                    token_count     INTEGER NOT NULL,
                    source_url      TEXT NOT NULL,
                    page_or_heading TEXT NOT NULL DEFAULT '',
                    embedding       vector({dim})
                );
            """)

            # HNSW index for fast approximate nearest-neighbor search
            cur.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_chunks_embedding
                ON chunks USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 200);
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_chunks_doc_id
                ON chunks (doc_id);
            """)

    logger.info("Database tables created / verified.")


def drop_tables() -> None:
    """Drop all tables (useful for dev resets)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS chunks CASCADE;")
            cur.execute("DROP TABLE IF EXISTS documents CASCADE;")
    logger.info("Tables dropped.")


# ---------------------------------------------------------------------------
# Document + chunk CRUD
# ---------------------------------------------------------------------------
def insert_document(doc_id: str, title: str, source_url: str, doc_type: str = "markdown") -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO documents (doc_id, title, source_url, doc_type)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (doc_id) DO UPDATE SET title=EXCLUDED.title, source_url=EXCLUDED.source_url;""",
                (doc_id, title, source_url, doc_type),
            )


def insert_chunks(chunks: list[Chunk]) -> None:
    """Batch-insert chunks with embeddings into Postgres."""
    if not chunks:
        return
    with get_conn() as conn:
        with conn.cursor() as cur:
            values = []
            for c in chunks:
                emb = c.embedding if c.embedding else None
                values.append((
                    c.chunk_id, c.doc_id, c.section_path, c.text,
                    c.context_header, c.token_count, c.source_url,
                    c.page_or_heading, emb,
                ))
            psycopg2.extras.execute_values(
                cur,
                """INSERT INTO chunks
                   (chunk_id, doc_id, section_path, text, context_header,
                    token_count, source_url, page_or_heading, embedding)
                   VALUES %s
                   ON CONFLICT (chunk_id) DO UPDATE SET
                       embedding = EXCLUDED.embedding,
                       text = EXCLUDED.text,
                       context_header = EXCLUDED.context_header;""",
                values,
                template="(%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            )
    logger.info(f"Inserted {len(chunks)} chunks.")


def get_all_chunks() -> list[Chunk]:
    """Load all chunks from DB (used to build the BM25 index on startup)."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT chunk_id, doc_id, section_path, text, context_header, "
                "token_count, source_url, page_or_heading FROM chunks;"
            )
            rows = cur.fetchall()
    return [
        Chunk(
            chunk_id=r["chunk_id"],
            doc_id=r["doc_id"],
            section_path=r["section_path"],
            text=r["text"],
            context_header=r["context_header"],
            token_count=r["token_count"],
            source_url=r["source_url"],
            page_or_heading=r["page_or_heading"],
        )
        for r in rows
    ]


def vector_search(query_embedding: list[float], top_k: int = 30) -> list[tuple[Chunk, float]]:
    """
    Find the top-k closest chunks by cosine similarity using pgvector.
    Returns (Chunk, similarity_score) pairs ordered by descending similarity.
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT chunk_id, doc_id, section_path, text, context_header,
                          token_count, source_url, page_or_heading,
                          1 - (embedding <=> %s::vector) AS similarity
                   FROM chunks
                   WHERE embedding IS NOT NULL
                   ORDER BY embedding <=> %s::vector
                   LIMIT %s;""",
                (query_embedding, query_embedding, top_k),
            )
            rows = cur.fetchall()

    results = []
    for r in rows:
        chunk = Chunk(
            chunk_id=r["chunk_id"],
            doc_id=r["doc_id"],
            section_path=r["section_path"],
            text=r["text"],
            context_header=r["context_header"],
            token_count=r["token_count"],
            source_url=r["source_url"],
            page_or_heading=r["page_or_heading"],
        )
        results.append((chunk, float(r["similarity"])))
    return results


def delete_document_chunks(doc_id: str) -> int:
    """Delete all chunks for a document. Returns count deleted."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chunks WHERE doc_id = %s;", (doc_id,))
            count = cur.rowcount
            cur.execute("DELETE FROM documents WHERE doc_id = %s;", (doc_id,))
    return count


def get_chunk_count() -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM chunks;")
            return cur.fetchone()[0]
