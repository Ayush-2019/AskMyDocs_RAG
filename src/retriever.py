"""
Hybrid retriever — parallel vector + BM25 search fused via Reciprocal Rank Fusion.

Why hybrid?
- Vector search excels at semantic paraphrasing ("How do I authenticate?" → "OAuth2 login flow")
- BM25 catches exact keyword matches on acronyms, config keys, error codes
- RRF merges both rank lists without needing score normalization
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.config import settings
from src.db import vector_search as db_vector_search
from src.indexer import bm25_index, embed_query
from src.models import Chunk, ScoredChunk

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=4)


# ---------------------------------------------------------------------------
# Individual retrievers (run in parallel)
# ---------------------------------------------------------------------------
def _vector_retrieve(query: str, top_k: int) -> list[ScoredChunk]:
    """Embed query and search pgvector."""
    query_vec = embed_query(query)
    results = db_vector_search(query_vec, top_k=top_k)
    return [
        ScoredChunk(chunk=chunk, score=sim, source="vector")
        for chunk, sim in results
    ]


def _bm25_retrieve(query: str, top_k: int) -> list[ScoredChunk]:
    """Search the in-memory BM25 index."""
    return bm25_index.search(query, top_k=top_k)


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion
# ---------------------------------------------------------------------------
def reciprocal_rank_fusion(
    *result_lists: list[ScoredChunk],
    k: int = 60,
) -> list[ScoredChunk]:
    """
    Merge multiple ranked result lists using Reciprocal Rank Fusion (RRF).

    For each chunk, its fused score = Σ 1/(k + rank_i) across all lists
    where it appears. The constant k (default 60) dampens the influence
    of top ranks so one retriever can't dominate.

    This is parameter-light and consistently outperforms linear score
    normalization because BM25 scores and cosine similarities live on
    incomparable scales.
    """
    fused_scores: dict[str, float] = {}
    chunk_map: dict[str, Chunk] = {}
    source_map: dict[str, list[str]] = {}

    for result_list in result_lists:
        for rank, scored in enumerate(result_list, start=1):
            cid = scored.chunk.chunk_id
            fused_scores[cid] = fused_scores.get(cid, 0.0) + 1.0 / (k + rank)
            chunk_map[cid] = scored.chunk
            source_map.setdefault(cid, []).append(scored.source)

    ranked = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)

    return [
        ScoredChunk(
            chunk=chunk_map[cid],
            score=score,
            source="rrf:" + "+".join(sorted(set(source_map[cid]))),
        )
        for cid, score in ranked
    ]


# ---------------------------------------------------------------------------
# Public API: hybrid retrieve
# ---------------------------------------------------------------------------
def hybrid_retrieve(query: str) -> list[ScoredChunk]:
    """
    Run vector search and BM25 search in parallel, then fuse results with RRF.

    Returns up to (vector_top_k + bm25_top_k) unique chunks, ranked by
    fused score. Downstream reranking narrows this to the final top_n.
    """
    cfg = settings.retrieval

    # Submit both searches concurrently
    futures = {
        _executor.submit(_vector_retrieve, query, cfg.vector_top_k): "vector",
        _executor.submit(_bm25_retrieve, query, cfg.bm25_top_k): "bm25",
    }

    results: dict[str, list[ScoredChunk]] = {}
    for future in as_completed(futures):
        name = futures[future]
        try:
            results[name] = future.result()
            logger.debug(f"{name} returned {len(results[name])} results.")
        except Exception as e:
            logger.error(f"{name} search failed: {e}")
            results[name] = []

    # Fuse with RRF
    fused = reciprocal_rank_fusion(
        results.get("vector", []),
        results.get("bm25", []),
        k=cfg.rrf_k,
    )

    logger.info(
        f"Hybrid retrieval: {len(results.get('vector', []))} vector + "
        f"{len(results.get('bm25', []))} BM25 → {len(fused)} fused results."
    )
    return fused
