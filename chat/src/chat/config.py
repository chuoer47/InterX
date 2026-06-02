"""Configuration models for the chat layer."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True, slots=True)
class LLMEndpoint:
    """Gateway-backed LLM endpoint configuration."""
    env_file: Path
    api_key_env: str
    base_url_env: str
    model_name: str | None = None
    model_name_env: str = ""


@dataclass(frozen=True, slots=True)
class MemoryConfig:
    """
    Memory strategy configuration.

    The chat layer supports direct sliding-window memory, summary-only memory, and
    a hybrid summary-plus-recent-window strategy.
    """
    strategy: str
    window_size: int
    max_summary_tokens: int
    summary_trigger_turns: int
    temperature: float
    timeout_seconds: float
    max_retries: int


@dataclass(frozen=True, slots=True)
class QueryRewriteConfig:
    """Configuration for history-aware query rewriting."""
    enabled: bool
    temperature: float
    max_tokens: int
    timeout_seconds: float
    max_retries: int


@dataclass(frozen=True, slots=True)
class ChatSettings:
    """Top-level settings for the multi-turn chat layer."""
    root: Path
    config_path: Path
    llm: LLMEndpoint
    memory: MemoryConfig
    query_rewrite: QueryRewriteConfig
    session_dir: Path

    @classmethod
    def load(cls, config_path: str | Path | None = None) -> "ChatSettings":
        """Load chat settings and resolve paths relative to the package root."""
        root = Path(__file__).resolve().parents[2]
        final_config_path = Path(config_path) if config_path else root / "configs" / "default.yaml"
        if not final_config_path.is_absolute():
            final_config_path = root / final_config_path

        raw = yaml.safe_load(final_config_path.read_text(encoding="utf-8")) or {}

        def resolve(value: str) -> Path:
            path = Path(value)
            return path if path.is_absolute() else root / path

        raw_llm = raw.get("llm", {})
        llm = LLMEndpoint(
            env_file=resolve(raw_llm.get("env_file", ".env")),
            api_key_env=str(raw_llm.get("api_key_env", "INTERX_GATEWAY_API_KEY")),
            base_url_env=str(raw_llm.get("base_url_env", "INTERX_GATEWAY_BASE_URL")),
            model_name=raw_llm.get("model_name"),
            model_name_env=str(raw_llm.get("model_name_env", "")),
        )

        raw_mem = raw.get("memory", {})
        memory = MemoryConfig(
            strategy=str(raw_mem.get("strategy", "sliding_summary")),
            window_size=int(raw_mem.get("window_size", 5)),
            max_summary_tokens=int(raw_mem.get("max_summary_tokens", 500)),
            summary_trigger_turns=int(raw_mem.get("summary_trigger_turns", 10)),
            temperature=float(raw_mem.get("temperature", 0.3)),
            timeout_seconds=float(raw_mem.get("timeout_seconds", 30.0)),
            max_retries=int(raw_mem.get("max_retries", 1)),
        )

        raw_qr = raw.get("query_rewrite", {})
        query_rewrite = QueryRewriteConfig(
            enabled=bool(raw_qr.get("enabled", True)),
            temperature=float(raw_qr.get("temperature", 0.1)),
            max_tokens=int(raw_qr.get("max_tokens", 256)),
            timeout_seconds=float(raw_qr.get("timeout_seconds", 30.0)),
            max_retries=int(raw_qr.get("max_retries", 1)),
        )

        return cls(
            root=root,
            config_path=final_config_path,
            llm=llm,
            memory=memory,
            query_rewrite=query_rewrite,
            session_dir=resolve(raw.get("session_dir", "sessions")),
        )
