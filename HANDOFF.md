# Claude Code — Session Handoff

A running handoff for the next agent (or human) picking up this repo. Updated at the end
of each working session. Read `CLAUDE.md` first for architecture; this file is state.

**Last updated:** 2026-11-24
**Branch:** `main`
**Owner of this session:** main thread, coordinating the pipeline subagents in `.claude/agents/`

---

## Current state

The full pipeline is implemented end to end and runs locally:

- ✅ **Ingestion** — markdown/HTML/text parsing, hierarchy-aware chunking, context
  headers. (`ingestion-engineer`)
- ✅ **Dual index** — pgvector + in-memory BM25, kept in sync on ingest.
  (`retrieval-engineer`)
- ✅ **Hybrid retrieval** — parallel vector + BM25, RRF fusion (`rrf_k = 60`).
  (`retrieval-engineer`)
- ✅ **Reranking** — `ms-marco-MiniLM-L-12-v2` cross-encoder, top 8.
  (`retrieval-engineer`)
- ✅ **Generation + citation validation** — numbered-source prompt, hallucinated-source
  rejection, citation-density check. (`generation-engineer`)
- ✅ **FastAPI layer** — `/ask`, `/ingest`, `/upload`, `/health`, `/stats`.
  (`api-frontend-engineer`)
- ✅ **React frontend** — upload + chat UI with a sources panel.
  (`api-frontend-engineer`)
- ✅ **Eval harness + CI gate** — `golden.json`, `run_eval.py`, `check_gates.py`, GitHub
  Actions workflow that blocks merges on regression. (`eval-engineer`)

## How to get running from a cold start

```bash
docker-compose up -d
python scripts/setup_db.py
export OPENAI_API_KEY=...        # generation + eval judge (see note below)
python scripts/ingest_docs.py --path docs/
uvicorn src.api:app --reload --port 8000
```

Smoke test: `GET /health` should report a non-zero chunk count after ingest.

## Known discrepancies / open items

These are real inconsistencies in the current code. They're documented here rather than
silently "fixed" — confirm the intended direction before changing anything, since the
right fix depends on which LLM provider this project is meant to standardize on.

1. **Provider mismatch (Anthropic vs OpenAI).** `README.md`, the architecture diagram,
   and `requirements.txt` reference Anthropic/Claude, but `src/generator.py` and
   `eval/run_eval.py` actually import and call the **OpenAI** client (`from openai import
   OpenAI`). A clean `pip install -r requirements.txt` would also fail at runtime
   because `openai` and `python-dotenv` are imported but not listed. **Decision needed:**
   standardize on one provider, then align the README, requirements, and config.
2. **Generation model name drift.** `config.yaml` sets `generation.model: gpt-4o` while
   the `GenerationConfig` default in `src/config.py` is `gpt-4.1-mini`. The YAML wins at
   runtime; the default is dead but misleading.
3. **Unused config keys.** `retrieval.final_top_k` and the `api:` block in `config.yaml`
   are not read anywhere (the reranker's `top_n` is what narrows to the final set).
4. **BM25 re-ingest growth.** `bm25_index.add_chunks()` appends on re-ingest; the
   pgvector side correctly deletes old chunks first. Confirm the in-memory index is
   rebuilt (`bm25_index.build()`) often enough that re-ingested docs don't double-count
   in lexical search.

## Suggested next steps

- Resolve item #1 (provider) — it's the highest-leverage fix and unblocks a reproducible
  install.
- Grow `eval/golden.json` toward the 50+ cases its own metadata targets.
- Add a `/upload` path test to the eval set now that the frontend uses it.

## Notes for the next agent

- Don't lower `config.yaml` eval thresholds to get CI green — see invariant #2 in
  `CLAUDE.md`.
- When editing a single stage, invoke its subagent (`.claude/agents/`) so the change
  stays within that stage's conventions.
