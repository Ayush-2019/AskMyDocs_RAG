"""
Cross-encoder reranker — second-stage precision reranking.

A cross-encoder takes (query, passage) as a single input and scores
relevance by attending across both sequences. This is far more accurate
than bi-encoder similarity but too slow for first-stage retrieval over
the full corpus — hence it runs only over the ~30-40 candidates from
hybrid retrieval.
"""

from __future__ import annotations

import logging

from sentence_transformers import CrossEncoder

from src.config import settings
from src.models import ScoredChunk

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton model loader
# ---------------------------------------------------------------------------
_reranker: CrossEncoder | None = None


def _get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        logger.info(f"Loading reranker model: {settings.reranker.model}")
        _reranker = CrossEncoder(settings.reranker.model, max_length=512)
    return _reranker


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def rerank(query: str, candidates: list[ScoredChunk]) -> list[ScoredChunk]:
    """
    Rerank candidate chunks using a cross-encoder model.

    Args:
        query: The user's question.
        candidates: Chunks from hybrid retrieval (typically 20-40).

    Returns:
        Top-n chunks sorted by cross-encoder relevance score,
        filtered by the score threshold from config.
    """
    cfg = settings.reranker

    if not candidates:
        return []

    model = _get_reranker()

    # Build (query, passage) pairs for the cross-encoder
    pairs = [(query, c.chunk.context_header) for c in candidates]

    # Score all pairs in one batch
    scores = model.predict(pairs, show_progress_bar=False)

    # Attach reranker scores
    reranked: list[ScoredChunk] = []
    for candidate, score in zip(candidates, scores):
        reranked.append(ScoredChunk(
            chunk=candidate.chunk,
            score=float(score),
            source="reranked",
        ))

    # Sort by reranker score (descending) and apply threshold + top_n
    reranked.sort(key=lambda c: c.score, reverse=True)

    filtered = [
        c for c in reranked
        if c.score >= cfg.score_threshold
    ][:cfg.top_n]

    logger.info(
        f"Reranked {len(candidates)} candidates → "
        f"{len(filtered)} passed threshold ({cfg.score_threshold})."
    )
    return filtered
