"""Configuration models for the retrieval pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True, slots=True)
class APIConfig:
    """Environment-backed credentials for retrieval-time model calls."""
    env_file: Path
    api_key_env: str
    base_url_env: str


@dataclass(frozen=True, slots=True)
class EmbeddingConfig:
    """Query embedding configuration used by dense recall."""
    model_name: str
    query_prompt: str
    document_prompt: str
    endpoint_path: str
    enable_fusion: bool
    dimension: int
    max_images_per_request: int
    timeout_seconds: float
    max_retries: int
    retry_backoff_seconds: float


@dataclass(frozen=True, slots=True)
class VectorStoreConfig:
    """Milvus search settings."""
    collection_name: str
    metric_type: str
    index_type: str
    milvus_timeout: float


@dataclass(frozen=True, slots=True)
class RerankConfig:
    """Rerank model configuration for second-stage candidate ordering."""
    enabled: bool
    model_name: str
    prompt: str
    min_score: float | None
    timeout_seconds: float
    max_retries: int


@dataclass(frozen=True, slots=True)
class FusionConfig:
    """
    Fusion configuration for hybrid recall.

    Channel weights let dense and sparse recall contribute unequally without tying
    the implementation to a single fixed hybrid recipe.
    """
    method: str
    rrf_k: int
    channel_weights: dict[str, float]


@dataclass(frozen=True, slots=True)
class RetrievalParams:
    """Operational parameters for first-stage recall and hierarchy aggregation."""
    bm25_top_k: int
    dense_top_k: int
    hybrid_top_k: int
    rerank_candidate_k: int
    return_mid_top_k: int
    return_big_top_k: int
    allow_dense_fallback: bool


@dataclass(frozen=True, slots=True)
class RetrievalSettings:
    """Top-level settings for retrieval over process artifacts."""
    root: Path
    config_path: Path
    db_path: Path
    chunks_dir: Path
    api: APIConfig
    embedding: EmbeddingConfig
    vector_store: VectorStoreConfig
    rerank: RerankConfig
    fusion: FusionConfig
    params: RetrievalParams

    @classmethod
    def load(cls, config_path: str | Path | None = None) -> "RetrievalSettings":
        """Load retrieval settings and resolve package-relative paths."""
        root = Path(__file__).resolve().parents[2]
        final_config_path = Path(config_path) if config_path else root / "configs" / "default.yaml"
        if not final_config_path.is_absolute():
            final_config_path = root / final_config_path

        raw = yaml.safe_load(final_config_path.read_text(encoding="utf-8")) or {}

        def resolve(value: str) -> Path:
            path = Path(value)
            return path if path.is_absolute() else root / path

        raw_api = raw.get("api", {})
        api = APIConfig(
            env_file=resolve(raw_api.get("env_file", ".env")),
            api_key_env=str(raw_api.get("api_key_env", "KAFU_LLM_API_KEY")),
            base_url_env=str(raw_api.get("base_url_env", "KAFU_LLM_BASE_URL")),
        )

        raw_emb = raw.get("embedding", {})
        embedding = EmbeddingConfig(
            model_name=str(raw_emb.get("model_name", "qwen3-vl-embedding")),
            query_prompt=str(raw_emb.get("query_prompt", "")),
            document_prompt=str(raw_emb.get("document_prompt", "")),
            endpoint_path=str(raw_emb.get(
                "endpoint_path",
                "/api/v1/services/embeddings/multimodal-embedding/multimodal-embedding",
            )),
            enable_fusion=bool(raw_emb.get("enable_fusion", True)),
            dimension=int(raw_emb.get("dimension", 1024)),
            max_images_per_request=int(raw_emb.get("max_images_per_request", 5)),
            timeout_seconds=float(raw_emb.get("timeout_seconds", 60.0)),
            max_retries=int(raw_emb.get("max_retries", 3)),
            retry_backoff_seconds=float(raw_emb.get("retry_backoff_seconds", 1.0)),
        )

        raw_vs = raw.get("vector_store", {})
        vector_store = VectorStoreConfig(
            collection_name=str(raw_vs.get("collection_name", "manual_chunks")),
            metric_type=str(raw_vs.get("metric_type", "COSINE")),
            index_type=str(raw_vs.get("index_type", "AUTOINDEX")),
            milvus_timeout=float(raw_vs.get("milvus_timeout", 10.0)),
        )

        raw_rr = raw.get("rerank", {})
        rerank = RerankConfig(
            enabled=bool(raw_rr.get("enabled", True)),
            model_name=str(raw_rr.get("model_name", "qwen3-rerank")),
            prompt=str(raw_rr.get("prompt", "")),
            min_score=raw_rr.get("min_score"),
            timeout_seconds=float(raw_rr.get("timeout_seconds", 60.0)),
            max_retries=int(raw_rr.get("max_retries", 2)),
        )

        raw_fusion = raw.get("fusion", {})
        fusion = FusionConfig(
            method=str(raw_fusion.get("method", "rrf")),
            rrf_k=int(raw_fusion.get("rrf_k", 60)),
            channel_weights=dict(raw_fusion.get("channel_weights", {"dense": 0.65, "bm25": 0.35})),
        )

        raw_params = raw.get("params", {})
        params = RetrievalParams(
            bm25_top_k=int(raw_params.get("bm25_top_k", 20)),
            dense_top_k=int(raw_params.get("dense_top_k", 20)),
            hybrid_top_k=int(raw_params.get("hybrid_top_k", 10)),
            rerank_candidate_k=int(raw_params.get("rerank_candidate_k", 20)),
            return_mid_top_k=int(raw_params.get("return_mid_top_k", 5)),
            return_big_top_k=int(raw_params.get("return_big_top_k", 3)),
            allow_dense_fallback=bool(raw_params.get("allow_dense_fallback", True)),
        )

        raw_paths = raw.get("paths", {})
        db_path = resolve(raw_paths.get("db_path", "../process/artifacts/manual_chunks.db"))
        chunks_dir = resolve(raw_paths.get("chunks_dir", "../process/artifacts/manuals"))

        return cls(
            root=root,
            config_path=final_config_path,
            db_path=db_path,
            chunks_dir=chunks_dir,
            api=api,
            embedding=embedding,
            vector_store=vector_store,
            rerank=rerank,
            fusion=fusion,
            params=params,
        )

    def as_dict(self) -> dict[str, Any]:
        """Expose a compact serializable settings snapshot for debugging."""
        return {
            "root": str(self.root),
            "config_path": str(self.config_path),
            "db_path": str(self.db_path),
            "chunks_dir": str(self.chunks_dir),
            "api": {
                "env_file": str(self.api.env_file),
                "api_key_env": self.api.api_key_env,
                "base_url_env": self.api.base_url_env,
            },
            "embedding": {
                "model_name": self.embedding.model_name,
                "dimension": self.embedding.dimension,
                "enable_fusion": self.embedding.enable_fusion,
            },
            "vector_store": {
                "collection_name": self.vector_store.collection_name,
                "metric_type": self.vector_store.metric_type,
                "index_type": self.vector_store.index_type,
            },
            "rerank": {
                "enabled": self.rerank.enabled,
                "model_name": self.rerank.model_name,
                "min_score": self.rerank.min_score,
            },
            "fusion": {
                "method": self.fusion.method,
                "rrf_k": self.fusion.rrf_k,
                "channel_weights": dict(self.fusion.channel_weights),
            },
            "params": {
                "bm25_top_k": self.params.bm25_top_k,
                "dense_top_k": self.params.dense_top_k,
                "hybrid_top_k": self.params.hybrid_top_k,
                "rerank_candidate_k": self.params.rerank_candidate_k,
                "return_mid_top_k": self.params.return_mid_top_k,
                "return_big_top_k": self.params.return_big_top_k,
                "allow_dense_fallback": self.params.allow_dense_fallback,
            },
        }
