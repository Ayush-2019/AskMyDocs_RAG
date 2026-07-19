"""
Configuration loader.

Reads config.yaml from project root and exposes settings as a typed dataclass.
Override any value via environment variables prefixed with ASKMYDOCS_:
    ASKMYDOCS_DATABASE__HOST=myhost  (double underscore = nesting)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _PROJECT_ROOT / "config.yaml"


@dataclass
class DatabaseConfig:
    host: str = "localhost"
    port: int = 5432
    name: str = "askmydocs"
    user: str = "postgres"
    password: str = "postgres"

    @property
    def dsn(self) -> str:
        return (
            f"host={self.host} port={self.port} dbname={self.name} "
            f"user={self.user} password={self.password}"
        )

    @property
    def url(self) -> str:
        return (
            f"postgresql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.name}"
        )


@dataclass
class EmbeddingConfig:
    model: str = "BAAI/bge-base-en-v1.5"
    dimension: int = 768
    batch_size: int = 64


@dataclass
class RerankerConfig:
    model: str = "cross-encoder/ms-marco-MiniLM-L-12-v2"
    top_n: int = 8
    score_threshold: float = 0.0


@dataclass
class RetrievalConfig:
    vector_top_k: int = 30
    bm25_top_k: int = 30
    rrf_k: int = 60
    final_top_k: int = 8


@dataclass
class ChunkingConfig:
    max_tokens: int = 512
    overlap_tokens: int = 50
    min_tokens: int = 30


@dataclass
class GenerationConfig:
    model: str = "gpt-4.1-mini"
    max_tokens: int = 2048
    temperature: float = 0.1


@dataclass
class EvalConfig:
    faithfulness_threshold: float = 0.90
    correctness_threshold: float = 0.80
    retrieval_recall_threshold: float = 0.85
    max_p95_latency_ms: float = 3000


@dataclass
class Settings:
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    reranker: RerankerConfig = field(default_factory=RerankerConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    eval: EvalConfig = field(default_factory=EvalConfig)


def _apply_env_overrides(raw: dict) -> dict:
    """Apply ASKMYDOCS_SECTION__KEY=value environment overrides."""
    prefix = "ASKMYDOCS_"
    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue
        parts = key[len(prefix):].lower().split("__")
        target = raw
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = value
    return raw


def load_settings(config_path: Path | None = None) -> Settings:
    """Load settings from YAML file with env-var overrides."""
    path = config_path or _CONFIG_PATH
    if path.exists():
        with open(path) as f:
            raw = yaml.safe_load(f) or {}
    else:
        raw = {}

    raw = _apply_env_overrides(raw)

    return Settings(
        database=DatabaseConfig(**raw.get("database", {})),
        embedding=EmbeddingConfig(**raw.get("embedding", {})),
        reranker=RerankerConfig(**raw.get("reranker", {})),
        retrieval=RetrievalConfig(**raw.get("retrieval", {})),
        chunking=ChunkingConfig(**raw.get("chunking", {})),
        generation=GenerationConfig(**raw.get("generation", {})),
        eval=EvalConfig(**raw.get("eval", {})),
    )


# Module-level singleton — import this everywhere
settings = load_settings()
