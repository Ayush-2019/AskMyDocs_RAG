"""
Citation-enforced generation layer.

Builds a prompt with numbered source chunks, calls the OpenAI API,
and validates that every factual claim in the response references a source.
"""

from __future__ import annotations

from dotenv import load_dotenv
import logging
import os
import re

from openai import OpenAI

from src.config import settings
from src.models import CitationReport, ScoredChunk

load_dotenv() 


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# OpenAI client (uses OPENAI_API_KEY env var)
# ---------------------------------------------------------------------------
def _get_client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY environment variable is required. "
            "Get one at https://platform.openai.com/"
        )
    return OpenAI(api_key=api_key)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a precise technical assistant that answers questions using ONLY the provided sources.

CITATION RULES — follow these exactly:
1. Every factual claim MUST end with a citation: [Source N].
2. If multiple sources support one claim, cite all: [Source 2][Source 5].
3. If no source supports the answer, respond with: "I don't have enough information in the provided documents to answer this question."
4. NEVER fabricate information that is not present in the sources.
5. NEVER invent source numbers that don't exist.
6. Use direct, specific answers. Avoid hedging when sources are clear.
7. If sources partially answer the question, answer what you can and note what's missing.

FORMATTING RULES:
- Use clear, organized prose.
- When listing steps or items, use numbered lists.
- Keep answers concise but complete."""


def build_prompt(query: str, chunks: list[ScoredChunk]) -> list[dict]:
    """Build the messages array for the OpenAI API call, including the system prompt."""
    sources_block = "\n\n".join(
        f"[Source {i + 1}] "
        f"(section: {c.chunk.section_path})\n"
        f"{c.chunk.text}"
        for i, c in enumerate(chunks)
    )

    user_message = (
        f"SOURCES:\n{sources_block}\n\n"
        f"QUESTION: {query}\n\n"
        f"Answer the question using only the sources above. "
        f"Cite every claim with [Source N]."
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message}
    ]


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------
def generate_answer(query: str, chunks: list[ScoredChunk]) -> str:
    """Call the OpenAI API with the RAG prompt and return the response text."""
    if not chunks:
        return (
            "I don't have enough information in the provided documents "
            "to answer this question."
        )

    client = _get_client()
    messages = build_prompt(query, chunks)

    response = client.chat.completions.create(
        model=settings.generation.model,
        max_tokens=settings.generation.max_tokens,
        temperature=settings.generation.temperature,
        messages=messages,
    )

    answer = response.choices[0].message.content
    if not answer:
        return "I don't have enough information in the provided documents to answer this question."

    logger.info(
        f"Generated answer: {len(answer)} chars, "
        f"tokens used: {response.usage.prompt_tokens}+{response.usage.completion_tokens}"
    )
    return answer


# ---------------------------------------------------------------------------
# Citation validation
# ---------------------------------------------------------------------------
def validate_citations(response: str, num_sources: int) -> CitationReport:
    """
    Parse the LLM response and check citation integrity.

    Validates:
    - All [Source N] references point to actual provided sources
    - Most factual sentences have at least one citation
    - No hallucinated source numbers
    """
    # Extract all cited source numbers
    cited_indices = set(int(m) for m in re.findall(r"\[Source (\d+)\]", response))
    valid = {i for i in cited_indices if 1 <= i <= num_sources}
    invalid = cited_indices - valid

    # Split into sentences and check each for citations
    sentences = re.split(r"(?<=[.!?])\s+", response.strip())
    sentences = [s for s in sentences if len(s.split()) > 3]  # skip tiny fragments

    uncited = []
    for sentence in sentences:
        has_citation = bool(re.search(r"\[Source \d+\]", sentence))
        is_disclaimer = "don't have enough information" in sentence.lower()
        is_transitional = len(sentence.split()) < 8  # short intro/transition

        if not has_citation and not is_disclaimer and not is_transitional:
            uncited.append(sentence)

    total_substantive = max(len(sentences), 1)
    cited_count = total_substantive - len(uncited)
    density = cited_count / total_substantive

    # Pass criteria: no invalid citations, and at most 2 uncited sentences
    # (allowing for intro and conclusion sentences)
    passed = len(invalid) == 0 and len(uncited) <= 2

    report = CitationReport(
        valid_citations=valid,
        invalid_citations=invalid,
        uncited_sentences=uncited,
        citation_density=density,
        passed=passed,
    )

    if not passed:
        logger.warning(
            f"Citation validation FAILED: "
            f"invalid_refs={invalid}, uncited_count={len(uncited)}"
        )
    else:
        logger.info(f"Citation validation passed: density={density:.2f}")

    return report


# ---------------------------------------------------------------------------
# Build source metadata for the response
# ---------------------------------------------------------------------------
def build_source_metadata(chunks: list[ScoredChunk]) -> list[dict]:
    """Create the source list that accompanies the answer in the API response."""
    return [
        {
            "source_index": i + 1,
            "chunk_id": c.chunk.chunk_id,
            "doc_id": c.chunk.doc_id,
            "source_url": c.chunk.source_url,
            "section_path": c.chunk.section_path,
            "heading": c.chunk.page_or_heading,
            "relevance_score": round(c.score, 4),
        }
        for i, c in enumerate(chunks)
    ]