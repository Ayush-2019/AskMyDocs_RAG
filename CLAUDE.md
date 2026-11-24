# CLAUDE.md

Guidance for Claude Code (and any AI agent) working in this repository. Read this
first before making changes. It captures the architecture, the conventions, and the
invariants that must not be broken.

## What this project is

**Ask My Docs** is a production-grade Retrieval-Augmented Generation (RAG) service:
hybrid retrieval (vector + lexical), cross-encoder reranking, citation-enforced
generation, and a CI-gated evaluation harness. It answers natural-language questions
over a document corpus and returns an answer where every factual claim carries a
`[Source N]` citation.

## How the work was done

This repository was built and is maintained by a team of specialized Claude Code
subagents, each owning one stage of the pipeline. Their definitions live in
`.claude/agents/`. The main thread coordinates; each subagent is invoked for work
inside its domain:

| Subagent | Owns |
|---|---|
| `ingestion-engineer` | `src/ingest.py`, chunking + context headers, `src/db.py` schema |
| `retrieval-engineer` | `src/indexer.py`, `src/retriever.py`, `src/reranker.py` (RRF + rerank) |
| `generation-engineer` | `src/generator.py` — prompt, generation, citation validation |
| `eval-engineer` | `eval/`, `.github/workflows/rag-eval.yml`, quality gates |
| `api-frontend-engineer` | `src/api.py`, `src/pipeline.py`, `frontend/` |

Reusable project knowledge is packaged as skills in `.claude/skills/`. Custom
workflows are in `.claude/commands/` (`/eval`, `/ingest`).

## Architecture (data flow)

```
ingest → dual index → hybrid retrieve → rerank → generate → validate
```

1. **Ingest** (`src/ingest.py`) — parse markdown/HTML/text into a section hierarchy,
   split into ~512-token overlapping chunks, and prepend a `context_header`
   (`[section_path]\n<text>`) to each chunk before embedding. This "contextual
   retrieval" step is what the embedding sees.
2. **Dual index** (`src/indexer.py`, `src/db.py`) — embed each chunk with
   `BAAI/bge-base-en-v1.5` into PostgreSQL + pgvector, and index the same chunks in an
   in-memory BM25 index (`rank_bm25`).
3. **Hybrid retrieve** (`src/retriever.py`) — run vector and BM25 search in parallel
   (`ThreadPoolExecutor`), fuse with Reciprocal Rank Fusion (`rrf_k = 60`). RRF is used
   deliberately because cosine similarity and BM25 scores live on incomparable scales.
4. **Rerank** (`src/reranker.py`) — re-score the fused candidates with the
   `cross-encoder/ms-marco-MiniLM-L-12-v2` cross-encoder, keep the top 8.
5. **Generate** (`src/generator.py`) — build a numbered `[Source N]` prompt and call the
   LLM with a strict citation system prompt.
6. **Validate** (`src/generator.py`) — parse the answer, reject hallucinated source
   numbers, measure citation density, and flag uncited factual sentences.

`src/pipeline.py` wires all six stages together and exposes `ingest_file()` and
`ask()`. `src/api.py` is a thin FastAPI layer over the pipeline.

## Key conventions

- **Config is centralized.** Everything tunable lives in `config.yaml`, loaded through
  `src/config.py` into the `settings` singleton. Override at runtime with
  `ASKMYDOCS_SECTION__KEY=value` (double underscore = nesting). Never hard-code a value
  that belongs in config.
- **Import the singletons, don't re-instantiate.** `from src.config import settings`,
  `from src.indexer import bm25_index`, `from src.pipeline import pipeline`.
- **Dataclasses are the contract.** `Chunk`, `ScoredChunk`, `CitationReport`,
  `RAGResponse` in `src/models.py` are shared across stages. Change them deliberately —
  a field change ripples through the whole pipeline.
- **CLI scripts use `click`.** Entry points live in `scripts/` and `eval/`; importable
  logic lives in `src/`. Keep that separation.
- **The BM25 index is in-memory and must be rebuilt on startup** (`bm25_index.build()`
  in `pipeline.initialize()`) and kept in sync on ingest (`bm25_index.add_chunks()`).

## Invariants — do not break these

1. **Citations are load-bearing.** Any change to generation must keep the `[Source N]`
   contract and must still pass `validate_citations()`. Do not loosen the validator to
   make answers pass.
2. **Quality gates block merges.** `eval/check_gates.py` fails the build if retrieval
   recall, faithfulness, correctness, p95 latency, or citation pass-rate regress.
   Don't lower thresholds in `config.yaml` to get a green build — fix the regression.
3. **RRF before rerank.** Reranking runs on fused candidates, never on a single
   retriever's raw output.
4. **Re-ingesting a document deletes its old chunks first**
   (`delete_document_chunks`) so stale vectors never accumulate. Preserve this.

## Common commands

```bash
docker-compose up -d                         # Postgres + pgvector
python scripts/setup_db.py                   # create tables
python scripts/ingest_docs.py --path docs/   # ingest a file or directory
uvicorn src.api:app --reload --port 8000     # run the API
python eval/run_eval.py --dataset eval/golden.json --output eval/results.json
python eval/check_gates.py eval/results.json # CI quality gate
cd frontend && npm install && npm run dev    # React UI
```

## Before you finish any change

- Run the eval harness locally if you touched `src/`, `config.yaml`, or `eval/`.
- Keep `README.md` and `config.yaml` consistent with the code.
- See `HANDOFF.md` for current state and the open items worth knowing about.
