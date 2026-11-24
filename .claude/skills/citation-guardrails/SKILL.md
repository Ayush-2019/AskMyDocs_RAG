---
name: citation-guardrails
description: >-
  The citation-enforcement and validation discipline that keeps Ask My Docs answers
  grounded. Use this whenever you change the generation prompt, the [Source N] format, the
  citation validator, or are investigating hallucinated or missing citations. Follow it so
  no answer ships with a fabricated or absent source.
---

# Citation Guardrails

The product promise is that every factual claim is traceable to a source. Two mechanisms
enforce it: a strict prompt and a post-generation validator. Changing one without the
other breaks the guarantee.

## The prompt contract

Sources are presented to the model as numbered blocks (`[Source 1] … [Source 2] …`). The
system prompt requires:

- Every factual claim ends with `[Source N]`; stack multiple as `[Source 2][Source 5]`.
- If no source supports the answer, return the fixed disclaimer ("I don't have enough
  information in the provided documents to answer this question.") rather than guessing.
- Never invent a source number that wasn't provided; never state facts absent from the
  sources.

Keep the numbering 1-based and aligned with the order chunks are passed in, because the
validator and the frontend's sources panel both rely on that alignment.

## The validator (`validate_citations`)

After generation, the answer is parsed and scored into a `CitationReport`:

- **valid_citations** — `[Source N]` where `1 ≤ N ≤ num_sources`.
- **invalid_citations** — any `N` outside that range = a hallucinated reference.
- **uncited_sentences** — substantive sentences (>3 words, not the disclaimer, not a short
  transition) with no citation.
- **citation_density** — fraction of substantive sentences that are cited.
- **passed** — `true` only when there are **zero invalid citations** and **at most two**
  uncited substantive sentences.

## Invariants

1. **Never loosen the validator to raise the pass rate.** If `citation_pass_rate` drops,
   the fix is better retrieval or a tighter prompt — not a weaker check.
2. The disclaimer string is matched by the validator; if you reword it, update the match
   in `validate_citations` too.
3. Keep `CitationReport` / `RAGResponse` shapes stable (`src/models.py`) — the API and UI
   depend on them.

## After any change here

Run the eval harness (`.claude/skills/rag-eval-harness/`) and confirm
`citation_pass_rate ≥ 0.80` and `faithfulness_mean ≥ 0.90` before declaring done.
