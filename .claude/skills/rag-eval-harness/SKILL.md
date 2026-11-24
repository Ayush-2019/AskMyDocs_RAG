---
name: rag-eval-harness
description: >-
  Run and extend the Ask My Docs evaluation harness and quality gates. Use this whenever
  you change anything in src/, config.yaml, or the prompts and need to verify the RAG
  pipeline didn't regress, whenever you add cases to the golden dataset, or whenever a
  CI gate fails and you need to interpret which metric dropped and why. Always run this
  loop before declaring a pipeline change "done."
---

# RAG Evaluation Harness

This skill is the measurement discipline for the pipeline. A change isn't finished until
the gates pass.

## The loop

```bash
# 1. Make sure the corpus the golden set expects is ingested
python scripts/ingest_docs.py --path docs/

# 2. Run the suite → metrics land in results.json
python eval/run_eval.py --dataset eval/golden.json --output eval/results.json

# 3. Check the gates (exits non-zero on any regression)
python eval/check_gates.py eval/results.json
```

Prerequisites: Postgres+pgvector up (`docker-compose up -d`), tables created
(`python scripts/setup_db.py`), and the generation/judge API key exported.

## Metrics and gates

| Metric | Gate (default) | What a drop means |
|---|---|---|
| `retrieval_recall_mean` | ≥ 0.85 | right chunks aren't being retrieved → look at chunking or retrieval params |
| `faithfulness_mean` | ≥ 0.90 | answers drifting from sources → prompt or reranking |
| `correctness_mean` | ≥ 0.80 | answers wrong vs expected → retrieval or generation |
| `latency_p95_ms` | ≤ 3000 | tail latency → embedding/rerank cost or DB |
| `citation_pass_rate` | ≥ 0.80 | citations missing/hallucinated → generation |

Gate thresholds resolve as: CLI flag > `config.yaml` (`eval:` block) > hardcoded default.
Override a single gate for a one-off run, e.g.
`python eval/check_gates.py eval/results.json --min-faithfulness 0.92`.

## Reading a failure

`check_gates.py` prints each gate with a ✓/✗ and the actual vs required value, then lists
failures and exits 1. Map the failed metric to the owning stage (table above) and hand the
fix to that subagent. Do **not** lower the threshold to pass.

## Extending the golden set

Add cases to `eval/golden.json` under `test_cases`. Each case:

```json
{
  "id": "auth-003",
  "question": "…",
  "expected_answer": "…",
  "expected_chunk_keywords": ["…"],
  "tags": ["auth"]
}
```

`expected_chunk_keywords` drives retrieval-recall scoring, so choose terms that uniquely
identify the correct chunk. Grow toward 50+ cases, then 200+, spread across tags.

## CI

`.github/workflows/rag-eval.yml` runs this same loop on PRs touching `src/`, `eval/`,
`config.yaml`, or `requirements.txt`, uploads `results.json` as an artifact, and blocks
merge on a failed gate. Keep local and CI behavior identical — same scripts, same dataset.
