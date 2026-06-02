from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True, slots=True)
class ProcessPaths:
    """Filesystem locations used by the process pipeline."""
    manual_dir: Path
    image_dir: Path
    artifact_dir: Path


@dataclass(frozen=True, slots=True)
class TokenizerSettings:
    """Tokenizer-related settings used for chunk sizing heuristics."""
    encoding_name: str
    image_token_cost: int


@dataclass(frozen=True, slots=True)
class ChunkScheme:
    """
    Chunk size policy for the three-level hierarchy.

    The target size controls the preferred stopping point for greedy packing,
    while the max size is the hard ceiling that triggers splitting.
    """
    name: str
    big_target_tokens: int
    big_max_tokens: int
    mid_target_tokens: int
    mid_max_tokens: int
    small_target_tokens: int
    small_max_tokens: int
    small_overlap_tokens: int
    max_images_per_small: int


@dataclass(frozen=True, slots=True)
class APIConfig:
    """Environment-backed credentials for the embedding provider."""
    env_file: Path
    api_key_env: str
    base_url_env: str


@dataclass(frozen=True, slots=True)
class EmbeddingConfig:
    """DashScope multimodal embedding configuration."""
    provider: str
    model_name: str
    query_prompt: str
    document_prompt: str
    endpoint_path: str
    enable_fusion: bool
    dimension: int
    batch_size: int
    max_images_per_request: int
    timeout_seconds: float
    max_retries: int
    retry_backoff_seconds: float
    normalize_embeddings: bool


@dataclass(frozen=True, slots=True)
class VectorStoreConfig:
    """Milvus Lite ingestion settings."""
    provider: str
    collection_name: str
    metric_type: str
    index_type: str
    batch_size: int


@dataclass(frozen=True, slots=True)
class ProcessSettings:
    """Top-level settings for chunk building, embedding, and vector ingestion."""
    root: Path
    config_path: Path
    paths: ProcessPaths
    exclude_files: tuple[str, ...]
    tokenizer: TokenizerSettings
    scheme: ChunkScheme
    api: APIConfig
    embedding: EmbeddingConfig
    vector_store: VectorStoreConfig

    @classmethod
    def load(cls, config_path: str | Path | None = None) -> "ProcessSettings":
        """
        Load process settings from YAML.

        Relative paths in the YAML are resolved from the package root so the same
        config behaves consistently no matter where the CLI is launched from.
        """
        root = Path(__file__).resolve().parents[2]
        final_config_path = Path(config_path) if config_path else root / "configs" / "default.yaml"
        if not final_config_path.is_absolute():
            final_config_path = root / final_config_path

        raw = yaml.safe_load(final_config_path.read_text(encoding="utf-8")) or {}

        def resolve(value: str) -> Path:
            path = Path(value)
            return path if path.is_absolute() else root / path

        raw_paths = raw.get("paths", {})
        paths = ProcessPaths(
            manual_dir=resolve(raw_paths.get("manual_dir", "data")),
            image_dir=resolve(raw_paths.get("image_dir", "data/插图")),
            artifact_dir=resolve(raw_paths.get("artifact_dir", "artifacts")),
        )

        raw_tokenizer = raw.get("tokenizer", {})
        tokenizer = TokenizerSettings(
            encoding_name=str(raw_tokenizer.get("encoding_name", "cl100k_base")),
            image_token_cost=int(raw_tokenizer.get("image_token_cost", 256)),
        )

        raw_scheme: dict[str, Any] = raw.get("chunking", {}).get("scheme", {})
        scheme_name = str(raw_scheme.pop("name", "process_default"))
        scheme = ChunkScheme(name=scheme_name, **raw_scheme)

        raw_api = raw.get("api", {})
        api = APIConfig(
            env_file=resolve(raw_api.get("env_file", ".env")),
            api_key_env=str(raw_api.get("api_key_env", "DASHSCOPE_API_KEY")),
            base_url_env=str(raw_api.get("base_url_env", "DASHSCOPE_BASE_URL")),
        )

        raw_emb = raw.get("embedding", {})
        embedding = EmbeddingConfig(
            provider=str(raw_emb.get("provider", "dashscope_multimodal")),
            model_name=str(raw_emb.get("model_name", "qwen3-vl-embedding")),
            query_prompt=str(raw_emb.get("query_prompt", "")),
            document_prompt=str(raw_emb.get("document_prompt", "")),
            endpoint_path=str(raw_emb.get(
                "endpoint_path",
                "/api/v1/services/embeddings/multimodal-embedding/multimodal-embedding",
            )),
            enable_fusion=bool(raw_emb.get("enable_fusion", True)),
            dimension=int(raw_emb.get("dimension", 1024)),
            batch_size=int(raw_emb.get("batch_size", 1)),
            max_images_per_request=int(raw_emb.get("max_images_per_request", 5)),
            timeout_seconds=float(raw_emb.get("timeout_seconds", 60.0)),
            max_retries=int(raw_emb.get("max_retries", 3)),
            retry_backoff_seconds=float(raw_emb.get("retry_backoff_seconds", 1.0)),
            normalize_embeddings=bool(raw_emb.get("normalize_embeddings", True)),
        )

        raw_vs = raw.get("vector_store", {})
        vector_store = VectorStoreConfig(
            provider=str(raw_vs.get("provider", "milvus_lite")),
            collection_name=str(raw_vs.get("collection_name", "manual_chunks")),
            metric_type=str(raw_vs.get("metric_type", "COSINE")),
            index_type=str(raw_vs.get("index_type", "AUTOINDEX")),
            batch_size=int(raw_vs.get("batch_size", 128)),
        )

        return cls(
            root=root,
            config_path=final_config_path,
            paths=paths,
            exclude_files=tuple(raw.get("manuals", {}).get("exclude", [])),
            tokenizer=tokenizer,
            scheme=scheme,
            api=api,
            embedding=embedding,
            vector_store=vector_store,
        )

    def manual_files(self) -> list[Path]:
        """Return manual markdown files after applying the configured exclusion list."""
        return sorted(
            path
            for path in self.paths.manual_dir.glob("*.md")
            if path.name not in self.exclude_files
        )

    def as_dict(self) -> dict[str, Any]:
        """Expose a compact serializable view used by manifests and reports."""
        return {
            "root": str(self.root),
            "config_path": str(self.config_path),
            "paths": {
                "manual_dir": str(self.paths.manual_dir),
                "image_dir": str(self.paths.image_dir),
                "artifact_dir": str(self.paths.artifact_dir),
            },
            "exclude_files": list(self.exclude_files),
            "tokenizer": {
                "encoding_name": self.tokenizer.encoding_name,
                "image_token_cost": self.tokenizer.image_token_cost,
            },
            "api": {
                "env_file": str(self.api.env_file),
                "api_key_env": self.api.api_key_env,
                "base_url_env": self.api.base_url_env,
            },
            "embedding": {
                "provider": self.embedding.provider,
                "model_name": self.embedding.model_name,
                "dimension": self.embedding.dimension,
                "enable_fusion": self.embedding.enable_fusion,
            },
            "vector_store": {
                "provider": self.vector_store.provider,
                "collection_name": self.vector_store.collection_name,
                "metric_type": self.vector_store.metric_type,
            },
            "scheme": {
                "name": self.scheme.name,
                "big_target_tokens": self.scheme.big_target_tokens,
                "big_max_tokens": self.scheme.big_max_tokens,
                "mid_target_tokens": self.scheme.mid_target_tokens,
                "mid_max_tokens": self.scheme.mid_max_tokens,
                "small_target_tokens": self.scheme.small_target_tokens,
                "small_max_tokens": self.scheme.small_max_tokens,
                "small_overlap_tokens": self.scheme.small_overlap_tokens,
                "max_images_per_small": self.scheme.max_images_per_small,
            },
        }
