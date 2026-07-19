#!/usr/bin/env python3
"""
CI quality gate checker.

Reads the evaluation results JSON and exits non-zero if any quality
threshold is breached — blocking the PR merge.

Usage:
    python eval/check_gates.py eval/results.json
    python eval/check_gates.py eval/results.json --min-faithfulness 0.95

Thresholds default to values in config.yaml but can be overridden via CLI flags.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click


@click.command()
@click.argument("results_path", type=click.Path(exists=True))
@click.option("--min-retrieval-recall", type=float, default=None)
@click.option("--min-faithfulness", type=float, default=None)
@click.option("--min-correctness", type=float, default=None)
@click.option("--max-p95-latency-ms", type=float, default=None)
@click.option("--min-citation-pass-rate", type=float, default=0.80)
def main(
    results_path: str,
    min_retrieval_recall: float | None,
    min_faithfulness: float | None,
    min_correctness: float | None,
    max_p95_latency_ms: float | None,
    min_citation_pass_rate: float,
):
    """Check evaluation results against quality gates."""

    # Try loading thresholds from config as defaults
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from src.config import settings
        defaults = settings.eval
    except Exception:
        defaults = None

    # Resolve thresholds: CLI flag > config > hardcoded default
    thresholds = {
        "retrieval_recall_mean": min_retrieval_recall or (defaults.retrieval_recall_threshold if defaults else 0.85),
        "faithfulness_mean": min_faithfulness or (defaults.faithfulness_threshold if defaults else 0.90),
        "correctness_mean": min_correctness or (defaults.correctness_threshold if defaults else 0.80),
        "latency_p95_ms": max_p95_latency_ms or (defaults.max_p95_latency_ms if defaults else 3000),
        "citation_pass_rate": min_citation_pass_rate,
    }

    with open(results_path) as f:
        results = json.load(f)

    metrics = results.get("metrics", {})
    if not metrics:
        print("ERROR: No metrics found in results file.")
        sys.exit(1)

    # Check each gate
    failures: list[str] = []

    gate_checks = [
        ("retrieval_recall_mean", ">=", thresholds["retrieval_recall_mean"]),
        ("faithfulness_mean", ">=", thresholds["faithfulness_mean"]),
        ("correctness_mean", ">=", thresholds["correctness_mean"]),
        ("latency_p95_ms", "<=", thresholds["latency_p95_ms"]),
        ("citation_pass_rate", ">=", thresholds["citation_pass_rate"]),
    ]

    print("=" * 60)
    print("QUALITY GATE RESULTS")
    print("=" * 60)

    for metric_name, op, threshold in gate_checks:
        actual = metrics.get(metric_name, 0)
        if op == ">=" and actual < threshold:
            passed = False
        elif op == "<=" and actual > threshold:
            passed = False
        else:
            passed = True

        status = "PASS" if passed else "FAIL"
        symbol = "✓" if passed else "✗"
        print(f"  {symbol} {metric_name}: {actual:.4f} {op} {threshold:.4f} [{status}]")

        if not passed:
            failures.append(
                f"{metric_name}: {actual:.4f} (required {op} {threshold:.4f})"
            )

    print("=" * 60)

    if failures:
        print(f"\nFAILED {len(failures)} gate(s):")
        for f in failures:
            print(f"  - {f}")
        print("\nDeploy blocked. Fix quality issues before merging.")
        sys.exit(1)
    else:
        print("\nAll gates passed. Safe to deploy.")
        sys.exit(0)


if __name__ == "__main__":
    main()
