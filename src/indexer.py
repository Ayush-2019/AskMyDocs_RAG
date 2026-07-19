"""
Dual indexer — vector embeddings (pgvector) + BM25 (rank-bm25).

Embeds chunks using sentence-transformers, stores them in Postgres,
and maintains an in-memory BM25 index for lexical search.
"""

from __future__ import annotations

import logging
from typing import Sequence

import nltk
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

from src.config import settings
from src.db import get_all_chunks, insert_chunks
from src.models import Chunk, ScoredChunk

logger = logging.getLogger(__name__)

# Ensure NLTK punkt tokenizer is available for word tokenization
try:
    nltk.data.find("tokenizers/punkt_tab")
except LookupError:
    nltk.download("punkt_tab", quiet=True)


# ---------------------------------------------------------------------------
# Singleton model loaders (loaded once, reused across calls)
# ---------------------------------------------------------------------------
_embed_model: SentenceTransformer | None = None


def _get_embed_model() -> SentenceTransformer:
    global _embed_model
    if _embed_model is None:
        logger.info(f"Loading embedding model: {settings.embedding.model}")
        _embed_model = SentenceTransformer(settings.embedding.model)
    return _embed_model


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------
def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts and return vectors as lists of floats."""
    model = _get_embed_model()
    embeddings = model.encode(
        texts,
        batch_size=settings.embedding.batch_size,
        show_progress_bar=len(texts) > 100,
        normalize_embeddings=True,
    )
    return [emb.tolist() for emb in embeddings]


def embed_query(query: str) -> list[float]:
    """Embed a single query string."""
    return embed_texts([query])[0]


# ---------------------------------------------------------------------------
# Index chunks: compute embeddings and persist to Postgres
# ---------------------------------------------------------------------------
def index_chunks(chunks: list[Chunk]) -> list[Chunk]:
    """
    Compute embeddings for a batch of chunks and store them in the database.
    Mutates each chunk's .embedding field in place and returns the list.
    """
    if not chunks:
        return chunks

    texts = [c.context_header for c in chunks]
    logger.info(f"Embedding {len(texts)} chunks...")
    vectors = embed_texts(texts)

    for chunk, vec in zip(chunks, vectors):
        chunk.embedding = vec

    insert_chunks(chunks)
    logger.info(f"Indexed {len(chunks)} chunks into pgvector.")
    return chunks


# ---------------------------------------------------------------------------
# BM25 index (in-memory, rebuilt from DB on startup or refresh)
# ---------------------------------------------------------------------------
class BM25Index:
    """
    In-memory BM25 index over all chunks in the database.

    This is rebuilt from scratch on startup. For corpora under ~200k chunks
    this is fast and simple. For larger corpora, swap this out for
    Elasticsearch or OpenSearch.
    """

    def __init__(self):
        self._chunks: list[Chunk] = []
        self._bm25: BM25Okapi | None = None
        self._tokenized_corpus: list[list[str]] = []

    @property
    def is_built(self) -> bool:
        return self._bm25 is not None and len(self._chunks) > 0

    def build(self, chunks: list[Chunk] | None = None) -> None:
        """Build or rebuild the BM25 index from all chunks."""
        if chunks is None:
            chunks = get_all_chunks()

        if not chunks:
            logger.warning("No chunks found — BM25 index is empty.")
            self._chunks = []
            self._bm25 = None
            return

        self._chunks = chunks
        self._tokenized_corpus = [
            nltk.word_tokenize(c.text.lower()) for c in chunks
        ]
        self._bm25 = BM25Okapi(self._tokenized_corpus)
        logger.info(f"BM25 index built with {len(chunks)} chunks.")

    def search(self, query: str, top_k: int = 30) -> list[ScoredChunk]:
        """Search the BM25 index and return top-k scored chunks."""
        if not self.is_built:
            logger.warning("BM25 index not built — returning empty results.")
            return []

        tokenized_query = nltk.word_tokenize(query.lower())
        scores = self._bm25.get_scores(tokenized_query)

        # Get top-k indices sorted by score descending
        scored_indices = sorted(
            enumerate(scores), key=lambda x: x[1], reverse=True
        )[:top_k]

        return [
            ScoredChunk(
                chunk=self._chunks[idx],
                score=float(score),
                source="bm25",
            )
            for idx, score in scored_indices
            if score > 0
        ]

    def add_chunks(self, new_chunks: list[Chunk]) -> None:
        """Add new chunks and rebuild the index."""
        self._chunks.extend(new_chunks)
        self._tokenized_corpus.extend(
            nltk.word_tokenize(c.text.lower()) for c in new_chunks
        )
        self._bm25 = BM25Okapi(self._tokenized_corpus)
        logger.info(f"BM25 index updated — now {len(self._chunks)} chunks.")


# Module-level singleton
bm25_index = BM25Index()
