---
name: contextual-chunking
description: >-
  The hierarchy-aware chunking and context-header convention used across Ask My Docs. Use
  this whenever you ingest a new document type, change chunk size or overlap, modify
  src/ingest.py, or debug why retrieval is missing content that is clearly in the corpus.
  Follow it so every chunk stays self-describing and embeds well.
---

# Contextual Chunking

Chunks in this project are not raw text slices. Each chunk is embedded together with its
place in the document's section hierarchy, so a passage like "set this to true" still
retrieves correctly for a query about "OAuth2 refresh token rotation."

## The rules

1. **Parse into a section hierarchy.** Track the full heading path for every piece of
   text, e.g. `Guide > Auth > OAuth2`. Store it on the chunk as `section_path`.
2. **Split within sections**, not across them, into chunks of `chunking.max_tokens`
   (~512) with `chunking.overlap_tokens` (50) of overlap. Drop fragments shorter than
   `chunking.min_tokens` (30) — they add noise, not signal.
3. **Build the context header.** Every chunk gets:
   ```
   [section_path]
   <chunk text>
   ```
   stored as `context_header`. **This is the string that gets embedded**, not the bare
   text. The raw `text` is kept separately for BM25 and for the generation prompt.
4. **Deterministic chunk IDs.** Derive `chunk_id` from `doc_id` + section + position so
   re-ingesting the same document produces the same IDs and replaces cleanly.

## Why

- The header gives the embedding model the ancestry a human would infer from the page,
  which is exactly what plain splitting throws away.
- Keeping embed-text (`context_header`) separate from prompt-text (`text`) means the model
  reads clean passages while retrieval benefits from the extra context. Don't collapse
  the two.

## Parameters live in config

All of `max_tokens`, `overlap_tokens`, `min_tokens` are in the `chunking:` block of
`config.yaml`. Never hardcode them in `src/ingest.py`. Changing them is a
retrieval-quality change — re-run the eval harness afterward
(`.claude/skills/rag-eval-harness/`).

## Invariant on re-ingest

Before inserting new chunks for a document, delete its old ones
(`delete_document_chunks`) so the vector store never accumulates stale slices. The
in-memory BM25 index must likewise be rebuilt or kept in sync so lexical search doesn't
double-count.
