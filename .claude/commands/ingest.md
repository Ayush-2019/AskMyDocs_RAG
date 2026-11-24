---
description: Ingest a file or directory into the RAG index
argument-hint: "<path> [--base-url https://docs.example.com]"
allowed-tools: Bash(python:*), Bash(docker-compose:*), Read
---

Ingest documents into Ask My Docs.

Target: `$ARGUMENTS` (a file or directory path, plus any optional `--base-url`). If no
path is given, default to `docs/`.

Steps:
1. Confirm Postgres+pgvector is up and tables exist (`python scripts/setup_db.py` is
   idempotent).
2. Run `python scripts/ingest_docs.py --path <path> [--base-url <url>]`.
3. Report how many documents and chunks were added, and confirm against `GET /stats`
   (or `get_chunk_count`) that the count increased.
4. Remind that re-ingesting an existing document replaces its old chunks — flag if any
   doc was re-ingested.

Follow the chunking conventions in `.claude/skills/contextual-chunking/` if ingestion
behavior needs adjusting.
