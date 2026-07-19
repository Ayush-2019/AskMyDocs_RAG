# Ask My Docs

A production-grade RAG (Retrieval-Augmented Generation) system with hybrid retrieval, cross-encoder reranking, citation enforcement, and CI-gated evaluation.

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Markdown/   │────▶│   Ingestion   │────▶│  Dual Index   │
│  HTML / Text  │     │   Pipeline    │     │  (pgvector +  │
│    files      │     │  (chunking)   │     │    BM25)      │
└──────────────┘     └──────────────┘     └──────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  User Query   │────▶│    Hybrid     │────▶│  Cross-Encoder│
│  (FastAPI)    │     │  Retrieval    │     │   Reranker    │
│               │     │  (RRF fusion) │     │               │
└──────────────┘     └──────────────┘     └──────────────┘
                                                   │
                     ┌──────────────┐     ┌────────▼───────┐
                     │   Citation    │◀────│    Claude      │
                     │  Validation   │     │   Generation   │
                     └──────┬───────┘     └──────────────  ┘
                            │
                     ┌──────▼───────┐
                     │   Response    │
                     │ + Sources +   │
                     │ Citation Rpt  │
                     └──────────────┘
```

**Data flow summary:**

1. **Ingest** — Documents are parsed into a section hierarchy, split into overlapping chunks (~512 tokens), and each chunk gets a `context_header` that prepends its section ancestry (e.g., `[Config > Auth > OAuth2]\nTo enable refresh tokens...`). This "contextual retrieval" trick dramatically improves embedding quality.

2. **Dual Index** — Each chunk is embedded with `BAAI/bge-base-en-v1.5` and stored in PostgreSQL via pgvector. The same chunks are also indexed in an in-memory BM25 index (via `rank_bm25`).

3. **Hybrid Retrieval** — At query time, vector search and BM25 search run in parallel. Results are merged via Reciprocal Rank Fusion (RRF), which combines rank positions without needing score normalization.

4. **Reranking** — The top ~30 RRF candidates are re-scored by a cross-encoder (`ms-marco-MiniLM-L-12-v2`) that attends across both query and passage. This narrows to the top 8 most relevant chunks.

5. **Generation** — Claude receives the ranked chunks as numbered `[Source N]` blocks with a strict citation prompt. Every factual claim must reference a source.

6. **Validation** — A post-generation validator checks that all `[Source N]` references point to real sources and that most sentences carry citations. Invalid responses are flagged.


## File Structure

```
ask-my-docs/
├── config.yaml                  # All tunable parameters
├── docker-compose.yml           # Postgres + pgvector
├── requirements.txt             # Python dependencies
│
├── src/
│   ├── __init__.py
│   ├── config.py                # YAML loader with env-var overrides
│   ├── models.py                # Chunk, ScoredChunk, RAGResponse, etc.
│   ├── db.py                    # Postgres + pgvector: tables, CRUD, vector search
│   ├── ingest.py                # Document parsing + hierarchy-aware chunking
│   ├── indexer.py               # Embedding (sentence-transformers) + BM25 index
│   ├── retriever.py             # Parallel vector+BM25 search, RRF fusion
│   ├── reranker.py              # Cross-encoder second-stage reranking
│   ├── generator.py             # Citation-enforced Claude generation + validation
│   ├── pipeline.py              # Orchestrator: ingest + ask (wires all stages)
│   └── api.py                   # FastAPI HTTP interface
│
├── eval/
│   ├── golden.json              # Evaluation dataset (question/answer/source triples)
│   ├── run_eval.py              # Runs test cases, computes metrics
│   └── check_gates.py           # CI gate: fails build if metrics drop
│
├── scripts/
│   ├── setup_db.py              # One-time database table creation
│   └── ingest_docs.py           # CLI to ingest files or directories
│
├── docs/
│   └── sample.md                # Sample doc to test with
│
└── .github/workflows/
    └── rag-eval.yml             # GitHub Actions CI pipeline
```


## How the Files Connect

The dependency graph flows like this:

```
config.py ◀─── (every module reads settings from here)
    │
models.py ◀─── (data structures shared by all modules)
    │
db.py ◀─────── (Postgres connection, tables, vector search)
    │
ingest.py ────▶ (parses files → Chunk objects)
    │
indexer.py ───▶ (embeds chunks → stores in db.py, builds BM25 index)
    │
retriever.py ─▶ (calls db.vector_search + indexer.bm25_index → RRF fusion)
    │
reranker.py ──▶ (cross-encoder re-scores retriever output)
    │
generator.py ─▶ (builds prompt from reranked chunks → calls Claude → validates)
    │
pipeline.py ──▶ (orchestrates: ingest calls ingest→indexer; ask calls retriever→reranker→generator)
    │
api.py ───────▶ (HTTP layer: delegates to pipeline.ask() and pipeline.ingest_file())
```

**Key singleton pattern:** `config.settings`, `indexer.bm25_index`, and `pipeline.pipeline` are module-level singletons. Import them directly:

```python
from src.config import settings       # typed config object
from src.indexer import bm25_index    # BM25 search index
from src.pipeline import pipeline     # the main orchestrator
```


## Setup (Step by Step)

### Prerequisites
- Python 3.11+
- Docker and Docker Compose
- An Anthropic API key ([get one here](https://console.anthropic.com/))

### 1. Clone and install

```bash
git clone <your-repo-url> ask-my-docs
cd ask-my-docs
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Start PostgreSQL + pgvector

```bash
docker-compose up -d
```

Wait a few seconds for the health check, then verify:

```bash
docker-compose ps    # should show "healthy"
```

### 3. Create database tables

```bash
python scripts/setup_db.py
```

### 4. Set your API key

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### 5. Ingest your documents

```bash
# Ingest the sample doc
python scripts/ingest_docs.py --path docs/

# Or ingest a specific file with a URL base for citations
python scripts/ingest_docs.py --path /path/to/your/docs --base-url https://docs.yourcompany.com
```

### 6. Start the API server

```bash
uvicorn src.api:app --reload --host 0.0.0.0 --port 8000
```

### 7. Ask a question

```bash
curl -s http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "How do I configure OAuth2 refresh token rotation?"}' | python -m json.tool
```

The response includes the answer with `[Source N]` citations, a sources array mapping each source number to its document URL and section, and a citation validation report.


## API Endpoints

| Method | Path      | Description                          |
|--------|-----------|--------------------------------------|
| POST   | /ask      | Ask a question, get a cited answer   |
| POST   | /ingest   | Ingest a file or directory           |
| GET    | /health   | Health check + chunk count           |
| GET    | /stats    | Detailed index statistics            |
| GET    | /docs     | Interactive Swagger UI               |


## Running the Evaluation Pipeline

### Locally

```bash
# Make sure docs are ingested first, then:
python eval/run_eval.py --dataset eval/golden.json --output eval/results.json

# Check if results pass quality gates
python eval/check_gates.py eval/results.json
```

### In CI (GitHub Actions)

The workflow at `.github/workflows/rag-eval.yml` runs automatically on PRs that touch retrieval, generation, or config files. It:

1. Spins up a Postgres+pgvector service container
2. Installs dependencies and sets up the database
3. Ingests test documents
4. Runs the full evaluation suite
5. Uploads results as a CI artifact (retained for 90 days)
6. Checks quality gates — **blocks merge** if any threshold fails

To enable: add `ANTHROPIC_API_KEY` as a repository secret in GitHub Settings > Secrets.

### Quality Thresholds (configurable in `config.yaml`)

| Metric             | Default | What it measures                                    |
|--------------------|---------|-----------------------------------------------------|
| Retrieval recall   | ≥ 0.85  | Did the right chunks appear in the retrieved set?   |
| Faithfulness       | ≥ 0.90  | Is the answer grounded in the retrieved sources?    |
| Correctness        | ≥ 0.80  | Does the answer match the expected answer?          |
| P95 latency        | ≤ 3000ms| End-to-end response time at the 95th percentile     |
| Citation pass rate | ≥ 0.80  | Fraction of answers passing citation validation     |


## Configuration

All parameters live in `config.yaml`. Override any value via environment variables:

```bash
# Pattern: ASKMYDOCS_SECTION__KEY=value
export ASKMYDOCS_DATABASE__HOST=my-prod-host
export ASKMYDOCS_RETRIEVAL__VECTOR_TOP_K=50
export ASKMYDOCS_GENERATION__MODEL=claude-sonnet-4-6
```


## Production Upgrade Path

This codebase is designed to run locally with minimal infrastructure. For production scale:

| Component         | Current (local)        | Production alternative               |
|-------------------|------------------------|--------------------------------------|
| BM25 search       | rank_bm25 (in-memory)  | Elasticsearch / OpenSearch           |
| Vector search     | pgvector               | Qdrant / Weaviate / Pinecone        |
| Embedding model   | bge-base (CPU)         | GPU inference or API (Voyage, Cohere)|
| Reranker          | ms-marco-MiniLM (CPU)  | Cohere Rerank v3 / Jina Reranker v2 |
| Caching           | None                   | Redis for query→response caching    |
| Auth              | None                   | API key middleware / OAuth           |
| Observability     | Logging                | OpenTelemetry + Grafana / Datadog   |
