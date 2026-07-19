#!/usr/bin/env python3
"""
RAG evaluation runner.

Runs each test case from the golden dataset through the pipeline and
computes retrieval, generation, and citation quality metrics.

Usage:
    python eval/run_eval.py --dataset eval/golden.json --output eval/results.json
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path

import click
import numpy as np

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LLM-as-judge for faithfulness and correctness
# ---------------------------------------------------------------------------
def _llm_judge(prompt: str) -> float:
    """
    Call OpenAI to judge answer quality on a 1-5 scale.
    Returns a normalized score between 0.0 and 1.0.
    """
    try:
        from openai import OpenAI
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=256,
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an evaluation judge. Rate the quality on a scale of 1-5. "
                        "Respond with ONLY a JSON object: {\"score\": N, \"reason\": \"...\"}"
                    )
                },
                {"role": "user", "content": prompt},
            ],
        )
        text = response.choices[0].message.content.strip()
        
        # Parse the JSON response
        import re
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*", "", text)
        result = json.loads(text)
        return result["score"] / 5.0
    except Exception as e:
        logger.warning(f"LLM judge failed: {e}. Returning 0.0")
        return 0.0


def judge_faithfulness(answer: str, sources: list[dict]) -> float:
    """
    Judge whether every claim in the answer is grounded in the provided sources.
    """
    source_texts = "\n".join(
        f"[Source {s['source_index']}] {s.get('section_path', '')}"
        for s in sources
    )
    prompt = (
        f"SOURCES:\n{source_texts}\n\n"
        f"ANSWER:\n{answer}\n\n"
        f"Rate faithfulness (1-5): Is every factual claim in the answer "
        f"supported by the sources? 5 = fully grounded, 1 = mostly hallucinated."
    )
    return _llm_judge(prompt)


def judge_correctness(answer: str, expected: str) -> float:
    """
    Judge whether the answer is correct relative to the expected answer.
    """
    prompt = (
        f"EXPECTED ANSWER:\n{expected}\n\n"
        f"ACTUAL ANSWER:\n{answer}\n\n"
        f"Rate correctness (1-5): Does the actual answer convey the same "
        f"key information as the expected answer? 5 = fully correct, "
        f"1 = completely wrong or missing key info."
    )
    return _llm_judge(prompt)


# ---------------------------------------------------------------------------
# Retrieval quality metrics
# ---------------------------------------------------------------------------
def compute_retrieval_recall(
    retrieved_chunks: list[dict],
    expected_keywords: list[str],
) -> float:
    """
    Compute keyword-based retrieval recall.

    Checks what fraction of expected keywords appear in the retrieved
    chunk texts. This is a pragmatic proxy for chunk-level recall when
    you don't have exact chunk IDs in your golden set.
    """
    if not expected_keywords:
        return 1.0  # negative test — no expected chunks

    retrieved_text = " ".join(
        c.get("section_path", "") + " " for c in retrieved_chunks
    ).lower()

    # Also check the answer text since it reflects what was retrieved
    found = sum(
        1 for kw in expected_keywords
        if kw.lower() in retrieved_text
    )
    return found / len(expected_keywords)


# ---------------------------------------------------------------------------
# Main evaluation loop
# ---------------------------------------------------------------------------
def run_evaluation(dataset_path: Path) -> dict:
    """Run all test cases and compute aggregate metrics."""
    from src.pipeline import pipeline

    logger.info("Initializing pipeline for evaluation...")
    pipeline.initialize()

    with open(dataset_path) as f:
        dataset = json.load(f)

    test_cases = dataset["test_cases"]
    logger.info(f"Running {len(test_cases)} test cases...")

    results = {
        "cases": [],
        "metrics": {},
    }

    latencies = []
    retrieval_recalls = []
    faithfulness_scores = []
    correctness_scores = []
    citation_densities = []
    citation_pass_rates = []

    for i, case in enumerate(test_cases):
        case_id = case["id"]
        logger.info(f"[{i+1}/{len(test_cases)}] Running: {case_id}")

        t0 = time.perf_counter()
        try:
            response = pipeline.ask(case["question"])
            latency_ms = (time.perf_counter() - t0) * 1000

            # Compute metrics
            retrieval_recall = compute_retrieval_recall(
                response.sources,
                case.get("expected_chunk_keywords", []),
            )
            faithfulness = judge_faithfulness(response.answer, response.sources)
            correctness = judge_correctness(response.answer, case["expected_answer"])

            case_result = {
                "id": case_id,
                "question": case["question"],
                "answer": response.answer,
                "latency_ms": round(latency_ms, 1),
                "retrieval_recall": round(retrieval_recall, 3),
                "faithfulness": round(faithfulness, 3),
                "correctness": round(correctness, 3),
                "citation_density": response.citation_report["citation_density"],
                "citation_passed": response.citation_report["passed"],
                "sources_used": len(response.sources),
                "tags": case.get("tags", []),
                "status": "success",
            }

            latencies.append(latency_ms)
            retrieval_recalls.append(retrieval_recall)
            faithfulness_scores.append(faithfulness)
            correctness_scores.append(correctness)
            citation_densities.append(response.citation_report["citation_density"])
            citation_pass_rates.append(1.0 if response.citation_report["passed"] else 0.0)

        except Exception as e:
            logger.error(f"Case {case_id} failed: {e}")
            case_result = {
                "id": case_id,
                "question": case["question"],
                "status": "error",
                "error": str(e),
            }

        results["cases"].append(case_result)

    # Aggregate metrics
    if latencies:
        results["metrics"] = {
            "retrieval_recall_mean": round(float(np.mean(retrieval_recalls)), 4),
            "faithfulness_mean": round(float(np.mean(faithfulness_scores)), 4),
            "correctness_mean": round(float(np.mean(correctness_scores)), 4),
            "citation_density_mean": round(float(np.mean(citation_densities)), 4),
            "citation_pass_rate": round(float(np.mean(citation_pass_rates)), 4),
            "latency_p50_ms": round(float(np.percentile(latencies, 50)), 1),
            "latency_p95_ms": round(float(np.percentile(latencies, 95)), 1),
            "latency_p99_ms": round(float(np.percentile(latencies, 99)), 1),
            "total_cases": len(test_cases),
            "successful_cases": sum(1 for c in results["cases"] if c["status"] == "success"),
        }

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
@click.command()
@click.option(
    "--dataset", "-d",
    required=True,
    type=click.Path(exists=True),
    help="Path to the golden evaluation dataset JSON.",
)
@click.option(
    "--output", "-o",
    default="eval/results.json",
    help="Path to write evaluation results.",
)
def main(dataset: str, output: str):
    """Run the RAG evaluation suite."""
    results = run_evaluation(Path(dataset))

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    logger.info(f"Results written to {output_path}")

    # Print summary
    m = results.get("metrics", {})
    if m:
        logger.info("=" * 60)
        logger.info("EVALUATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"  Cases:              {m['total_cases']} ({m['successful_cases']} succeeded)")
        logger.info(f"  Retrieval recall:   {m['retrieval_recall_mean']:.3f}")
        logger.info(f"  Faithfulness:       {m['faithfulness_mean']:.3f}")
        logger.info(f"  Correctness:        {m['correctness_mean']:.3f}")
        logger.info(f"  Citation density:   {m['citation_density_mean']:.3f}")
        logger.info(f"  Citation pass rate: {m['citation_pass_rate']:.3f}")
        logger.info(f"  Latency P50:        {m['latency_p50_ms']:.0f} ms")
        logger.info(f"  Latency P95:        {m['latency_p95_ms']:.0f} ms")
        logger.info("=" * 60)


if __name__ == "__main__":
    main()