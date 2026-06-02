"""Configuration models for the answer pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
@dataclass(frozen=True, slots=True)
class LLMEndpoint:
    """Connection settings for one gateway-backed LLM endpoint."""
    env_file: Path
    api_key_env: str
    base_url_env: str
    model_name: str | None = None
    model_name_env: str = ""
@dataclass(frozen=True, slots=True)
class AnswerLayerConfig:
    """Per-layer generation limits for small, mid, big, and ensemble answers."""
    max_context_chars: int
    max_images: int | None
    temperature: float
    max_tokens: int
    timeout_seconds: float
    max_retries: int
    retry_backoff_seconds: float
    response_format_json: bool = True
@dataclass(frozen=True, slots=True)
class QueryRewriteConfig:
    """Settings for optional multi-query rewrite before retrieval."""
    enabled: bool
    num_variants: int
    temperature: float
    max_tokens: int
    timeout_seconds: float
    max_retries: int

@dataclass(frozen=True, slots=True)
class KGConfig:
    """Settings for knowledge graph expansion of retrieval hits."""
    enabled: bool = True
    max_expanded: int = 8
    graph_db_root: Path = Path("")
@dataclass(frozen=True, slots=True)
class QASettings:
    """Top-level answer pipeline settings."""
    root: Path
    config_path: Path
    llm: LLMEndpoint
    rewrite_llm: LLMEndpoint
    judge_llm: LLMEndpoint
    small_layer: AnswerLayerConfig
    mid_layer: AnswerLayerConfig
    big_layer: AnswerLayerConfig
    ensemble_layer: AnswerLayerConfig
    query_rewrite: QueryRewriteConfig
    retrieval_top_k: int
    mid_top_k: int
    big_top_k: int
    include_images: bool
    image_dir: Path
    max_workers: int
    kg: KGConfig

    @classmethod
    def load(cls, config_path: str | Path | None = None) -> "QASettings":
        """Load answer settings and resolve package-relative filesystem paths."""
        root = Path(__file__).resolve().parents[2]
        final_config_path = Path(config_path) if config_path else root / "configs" / "default.yaml"
        if not final_config_path.is_absolute():
            final_config_path = root / final_config_path

        raw = yaml.safe_load(final_config_path.read_text(encoding="utf-8")) or {}

        def resolve(value: str) -> Path:
            path = Path(value)
            return path if path.is_absolute() else root / path

        def _endpoint(raw_section: dict[str, Any], *, fallback_model_env: str = "") -> LLMEndpoint:
            return LLMEndpoint(
                env_file=resolve(raw_section.get("env_file", ".env")),
                api_key_env=str(raw_section.get("api_key_env", "INTERX_GATEWAY_API_KEY")),
                base_url_env=str(raw_section.get("base_url_env", "INTERX_GATEWAY_BASE_URL")),
                model_name=raw_section.get("model_name"),
                model_name_env=str(raw_section.get("model_name_env", fallback_model_env)),
            )

        def _layer(raw_section: dict[str, Any]) -> AnswerLayerConfig:
            return AnswerLayerConfig(
                max_context_chars=int(raw_section.get("max_context_chars", 12000)),
                max_images=raw_section.get("max_images"),
                temperature=float(raw_section.get("temperature", 0.1)),
                max_tokens=int(raw_section.get("max_tokens", 4096)),
                timeout_seconds=float(raw_section.get("timeout_seconds", 90.0)),
                max_retries=int(raw_section.get("max_retries", 2)),
                retry_backoff_seconds=float(raw_section.get("retry_backoff_seconds", 1.0)),
                response_format_json=bool(raw_section.get("response_format_json", True)),
            )

        raw_llm = raw.get("llm", {})
        raw_rewrite = raw.get("query_rewrite", {})
        raw_qr_llm = raw.get("rewrite_llm", {})
        raw_judge = raw.get("judge_llm", {})
        raw_kg = raw.get("kg", {})

        return cls(
            root=root,
            config_path=final_config_path,
            llm=_endpoint(raw_llm),
            rewrite_llm=_endpoint(raw_qr_llm),
            judge_llm=_endpoint(raw_judge),
            small_layer=_layer(raw.get("small_layer", {})),
            mid_layer=_layer(raw.get("mid_layer", {})),
            big_layer=_layer(raw.get("big_layer", {})),
            ensemble_layer=_layer(raw.get("ensemble_layer", {})),
            query_rewrite=QueryRewriteConfig(
                enabled=bool(raw_rewrite.get("enabled", True)),
                num_variants=int(raw_rewrite.get("num_variants", 3)),
                temperature=float(raw_rewrite.get("temperature", 0.7)),
                max_tokens=int(raw_rewrite.get("max_tokens", 512)),
                timeout_seconds=float(raw_rewrite.get("timeout_seconds", 30.0)),
                max_retries=int(raw_rewrite.get("max_retries", 2)),
            ),
            retrieval_top_k=int(raw.get("retrieval_top_k", 10)),
            mid_top_k=int(raw.get("mid_top_k", 5)),
            big_top_k=int(raw.get("big_top_k", 3)),
            include_images=bool(raw.get("include_images", True)),
            image_dir=resolve(raw.get("image_dir", "../process/data/插图")),
            max_workers=int(raw.get("max_workers", 4)),
            kg=KGConfig(
                enabled=bool(raw_kg.get("enabled", True)),
                max_expanded=int(raw_kg.get("max_expanded", 8)),
                graph_db_root=resolve(raw_kg.get("graph_db_root", "../kg/state/graph.db")),
            ),
        )
