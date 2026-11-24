---
description: Run the RAG evaluation suite and check quality gates
argument-hint: "[optional: path to a dataset, defaults to eval/golden.json]"
allowed-tools: Bash(python:*), Bash(docker-compose:*), Read
---

Run the full evaluation loop for Ask My Docs and report the result.

Dataset: use `$ARGUMENTS` if provided, otherwise `eval/golden.json`.

Steps:
1. Confirm Postgres+pgvector is up (`docker-compose ps`); start it if not.
2. Ensure `docs/` is ingested so the golden cases have a corpus.
3. Run `python eval/run_eval.py --dataset <dataset> --output eval/results.json`.
4. Run `python eval/check_gates.py eval/results.json`.
5. Summarize each metric (actual vs gate) and, for any failure, name the pipeline stage
   responsible (see the metric→stage table in `.claude/skills/rag-eval-harness/`) and
   suggest handing the fix to that subagent.

Do not modify `config.yaml` thresholds to make gates pass.
