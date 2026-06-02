from __future__ import annotations
"""DashScope multimodal embedding client used by the process package."""

import base64
import mimetypes
import os
import time
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from .config import APIConfig, EmbeddingConfig
from .utils import content_hash, read_jsonl, write_jsonl


def _load_api_env(config: APIConfig) -> tuple[str, str]:
    """Load embedding credentials lazily from the configured env file."""
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


def _dashscope_endpoint(api_config: APIConfig, endpoint_path: str) -> str:
    """Build a concrete embedding endpoint from the configured base URL."""
    _, base_url = _load_api_env(api_config)
    base = _dashscope_base_url(base_url)
    return f"{base}/{endpoint_path.strip('/')}"


def _image_to_data_url(image_path: str | Path) -> str:
    """Encode a local image as the data URL expected by the multimodal endpoint."""
    path = Path(image_path)
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
) -> tuple[list[float], dict[str, Any]]:
    """
    Send one embedding request with retry and exponential backoff.

    Retry is limited to transient HTTP failures because embedding jobs are often
    part of long-running batch builds where occasional rate limiting is expected.
    """
    api_key, _ = _load_api_env(api_config)
    body: dict[str, Any] = {
        "model": config.model_name,
        "input": {"contents": contents},
        "parameters": {
            "enable_fusion": config.enable_fusion,
            "dimension": config.dimension,
        },
    }
    endpoint = _dashscope_endpoint(api_config, config.endpoint_path)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    response: requests.Response | None = None
    last_error: Exception | None = None

    for attempt in range(max(1, config.max_retries + 1)):
        try:
            response = requests.post(
                endpoint,
                headers=headers,
                json=body,
                timeout=config.timeout_seconds,
            )
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
        raise RuntimeError(f"Embedding API returned empty embedding: {payload}")
    return vector, payload


def embed_payload(
    payload: dict[str, Any],
    *,
    api_config: APIConfig,
    config: EmbeddingConfig,
) -> tuple[list[float], dict[str, Any]]:
    """
    Convert a chunk payload into the request body expected by the embedding API.

    The process package currently emits at most one image per small chunk payload,
    which aligns with the way chunk construction picks a visual anchor image.
    """
    text = str(payload.get("text", "")).strip()
    image = payload.get("image")
    contents: list[dict[str, str]] = []
    if text:
        contents.append({"text": text})
    if image:
        contents.append({"image": _image_to_data_url(image)})
    if not contents:
        raise ValueError("Embedding payload must include text or image")
    return _request_embedding(contents=contents, api_config=api_config, config=config)


def embed_rows(
    rows: list[dict[str, Any]],
    *,
    api_config: APIConfig,
    config: EmbeddingConfig,
) -> list[dict[str, Any]]:
    """Embed rows in memory and attach the resulting vectors to each row copy."""
    result: list[dict[str, Any]] = []
    for row in rows:
        vector, payload = embed_payload(row["embedding_payload"], api_config=api_config, config=config)
        result.append({
            **row,
            "embedding": vector,
            "embedding_model": config.model_name,
            "embedding_response": payload,
        })
    return result


def embed_file(
    input_path: Path,
    output_path: Path,
    *,
    api_config: APIConfig,
    config: EmbeddingConfig,
    incremental: bool = True,
) -> list[dict[str, Any]]:
    """
    Embed a JSONL file and persist the enriched output.

    Incremental mode skips unchanged rows using the chunk content hash so long
    embedding runs can resume without recomputing finished work.
    """
    rows = read_jsonl(input_path)
    existing_by_hash: dict[str, dict[str, Any]] = {}
    if incremental and output_path.exists():
        for row in read_jsonl(output_path):
            row_hash = row.get("content_hash")
            if row_hash:
                existing_by_hash[str(row_hash)] = row

    enriched: list[dict[str, Any]] = []
    for row in rows:
        row_hash = str(row.get("content_hash") or content_hash(row.get("content", "")))
        cached = existing_by_hash.get(row_hash)
        if cached and cached.get("embedding"):
            enriched.append({**row, **{k: v for k, v in cached.items() if k in {"embedding", "embedding_model", "embedding_response"}}})
            continue
        vector, payload = embed_payload(row["embedding_payload"], api_config=api_config, config=config)
        enriched.append({
            **row,
            "embedding": vector,
            "embedding_model": config.model_name,
            "embedding_response": payload,
        })

    write_jsonl(output_path, enriched)
    return enriched
