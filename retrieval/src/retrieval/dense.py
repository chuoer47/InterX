"""Dense vector retrieval via Milvus."""
from __future__ import annotations

import base64
import mimetypes
import os
import time
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from pymilvus import MilvusClient

from .config import APIConfig, EmbeddingConfig, VectorStoreConfig


def _load_api_env(config: APIConfig) -> tuple[str, str]:
    """Load dense-retrieval API credentials from the configured env file."""
    load_dotenv(config.env_file, override=False)
    api_key = os.getenv(config.api_key_env, "").strip()
    base_url = os.getenv(config.base_url_env, "").strip().rstrip("/")
    missing = []
    if not api_key:
        missing.append(config.api_key_env)
    if not base_url:
        missing.append(config.base_url_env)
    if missing:
        raise ValueError(f"Missing API config in {config.env_file}: {', '.join(missing)}")
    return api_key, base_url


def _dashscope_base_url(base_url: str) -> str:
    """Normalize compatible-mode URLs back to the native DashScope base."""
    value = base_url.strip().rstrip("/")
    for suffix in ("/compatible-mode/v1", "/compatible-api/v1"):
        if value.endswith(suffix):
            return value[: -len(suffix)]
    if value.endswith("/v1"):
        return value[: -len("/v1")]
    return value


def _image_to_data_url(image: str | Path) -> str:
    """
    Convert an image input into the data URL expected by the embedding endpoint.

    The query path accepts either a local file, an already-formed data URL, or a
    raw base64 payload coming from the API layer.
    """
    if isinstance(image, str) and image.startswith("data:"):
        return image
    if isinstance(image, str) and len(image) > 200 and "/" not in image and "\\" not in image:
        return f"data:image/jpeg;base64,{image}"
    path = Path(image)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")
    mime_type, _ = mimetypes.guess_type(path.name)
    if not mime_type:
        mime_type = "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def _request_embedding(
    *,
    contents: list[dict[str, str]],
    api_config: APIConfig,
    config: EmbeddingConfig,
) -> list[float]:
    """
    Request one dense embedding vector with transient-failure retry.

    Retrieval keeps its own local copy of the embedding call path so the package
    stays decoupled from the process package implementation details.
    """
    api_key, base_url = _load_api_env(api_config)
    endpoint = f"{_dashscope_base_url(base_url)}/{config.endpoint_path.strip('/')}"
    body: dict[str, Any] = {
        "model": config.model_name,
        "input": {"contents": contents},
        "parameters": {
            "enable_fusion": config.enable_fusion,
            "dimension": config.dimension,
        },
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    response = None
    last_error: Exception | None = None
    for attempt in range(max(1, config.max_retries + 1)):
        try:
            response = requests.post(endpoint, headers=headers, json=body, timeout=config.timeout_seconds)
            if response.status_code not in {408, 409, 429, 500, 502, 503, 504}:
                break
        except requests.RequestException as exc:
            last_error = exc
        if attempt < config.max_retries:
            time.sleep(config.retry_backoff_seconds * (2**attempt))
    if response is None:
        raise RuntimeError(f"Embedding API request failed: {last_error}")
    if response.status_code >= 400:
        raise RuntimeError(f"Embedding API failed: {response.status_code} {response.text[:1000]}")
    payload = response.json()
    if payload.get("code"):
        raise RuntimeError(f"Embedding API error: {payload}")
    embeddings = (payload.get("output") or {}).get("embeddings") or []
    if not embeddings:
        raise RuntimeError(f"Embedding API returned no embeddings: {payload}")
    vector = embeddings[0].get("embedding")
    if not vector:
        raise RuntimeError(f"Embedding API returned empty vector: {payload}")
    return [float(item) for item in vector]


def embed_query(
    query: str,
    *,
    api_config: APIConfig,
    config: EmbeddingConfig,
    image_paths: list[str | Path] | None = None,
) -> list[float]:
    """
    Embed a user query, optionally with user-supplied images.

    This mirrors the multimodal format used during chunk embedding so query-side
    images participate in the same shared vector space.
    """
    value = f"{config.query_prompt}\n{query}".strip() if config.query_prompt else query.strip()
    contents: list[dict[str, str]] = [{"text": value}]
    for img in (image_paths or []):
        contents.append({"image": _image_to_data_url(img)})
    return _request_embedding(contents=contents, api_config=api_config, config=config)


def search_milvus(
    *,
    db_path: Path,
    query_vector: list[float],
    vs_config: VectorStoreConfig,
    top_k: int,
    filter_expr: str | None = None,
) -> list[dict[str, Any]]:
    """
    Run dense vector search against the unified Milvus Lite database.

    The gRPC keepalive interval is stretched to avoid noisy local warnings seen
    during long-running interactive development sessions.
    """
    client = MilvusClient(
        uri=str(db_path),
        grpc_options={"grpc.keepalive_time_ms": 600000},
    )
    collection = vs_config.collection_name
    client.load_collection(collection)

    kwargs: dict[str, Any] = {
        "collection_name": collection,
        "data": [query_vector],
        "limit": max(1, top_k),
        "output_fields": [
            "chunk_id", "big_chunk_id", "mid_chunk_id",
            "doc_id", "doc_name", "product_name",
            "source_path", "section_title",
            "image_count", "token_count",
        ],
        "timeout": vs_config.milvus_timeout,
    }
    if filter_expr:
        kwargs["filter"] = filter_expr

    results = client.search(**kwargs)
    hits = results[0] if results else []
    rows: list[dict[str, Any]] = []
    for rank, hit in enumerate(hits, start=1):
        entity = hit.get("entity", {})
        chunk_id = entity.get("chunk_id") or hit.get("id")
        if not chunk_id:
            continue
        rows.append(
            {
                "chunk_id": chunk_id,
                "score": float(hit["distance"]) if hit.get("distance") is not None else None,
                "rank": rank,
                **entity,
            }
        )
    return rows
