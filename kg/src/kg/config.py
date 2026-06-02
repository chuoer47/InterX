"""Configuration loader for the KG package."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class LLMConfig:
    base_url: str
    api_key: str
    model: str
    max_retries: int = 3
    timeout: float = 120.0


@dataclass(frozen=True, slots=True)
class GraphStoreConfig:
    backend: str
    db_path: Path


@dataclass(frozen=True, slots=True)
class BuilderConfig:
    max_chunk_pair_tokens: int = 3000
    batch_size: int = 10


@dataclass(frozen=True, slots=True)
class RetrieverConfig:
    max_hops: int = 2
    max_expanded_chunks: int = 8
    seed_count: int = 3
    graph_bonus_weight: float = 0.15


@dataclass(frozen=True, slots=True)
class KGSettings:
    root: Path
    chunks_dir: Path
    artifacts_dir: Path
    llm: LLMConfig
    graph_store: GraphStoreConfig
    builder: BuilderConfig
    retriever: RetrieverConfig

    @classmethod
    def load(cls, config_path: str | Path | None = None) -> "KGSettings":
        root = _ROOT
        cfg_path = Path(config_path) if config_path else root / "configs" / "default.yaml"
        if not cfg_path.is_absolute():
            cfg_path = root / cfg_path

        raw: dict = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}

        env_file = root / raw.get("env_file", ".env")
        if env_file.exists():
            load_dotenv(env_file, override=False)

        def _env(key: str, default: str = "") -> str:
            return os.getenv(key, default).strip()

        def _resolve(v: str) -> Path:
            p = Path(v)
            return p if p.is_absolute() else root / p

        llm_raw = raw.get("llm", {})
        llm = LLMConfig(
            base_url=llm_raw.get("base_url") or _env("LLM_BASE_URL"),
            api_key=llm_raw.get("api_key") or _env("LLM_API_KEY"),
            model=llm_raw.get("model") or _env("LLM_MODEL", "mimo-v2.5-pro"),
        )

        gs_raw = raw.get("graph_store", {})
        graph_store = GraphStoreConfig(
            backend=gs_raw.get("backend", "kuzu"),
            db_path=_resolve(gs_raw.get("db_path", "state/graph.db")),
        )

        builder_raw = raw.get("builder", {})
        builder = BuilderConfig(
            max_chunk_pair_tokens=int(builder_raw.get("max_chunk_pair_tokens", 3000)),
            batch_size=int(builder_raw.get("batch_size", 10)),
        )

        ret_raw = raw.get("retriever", {})
        retriever = RetrieverConfig(
            max_hops=int(ret_raw.get("max_hops", 2)),
            max_expanded_chunks=int(ret_raw.get("max_expanded_chunks", 8)),
            seed_count=int(ret_raw.get("seed_count", 3)),
            graph_bonus_weight=float(ret_raw.get("graph_bonus_weight", 0.15)),
        )

        paths_raw = raw.get("paths", {})
        return cls(
            root=root,
            chunks_dir=_resolve(paths_raw.get("chunks_dir", "../process/artifacts/manuals")),
            artifacts_dir=_resolve(paths_raw.get("artifacts_dir", "artifacts")),
            llm=llm,
            graph_store=graph_store,
            builder=builder,
            retriever=retriever,
        )
