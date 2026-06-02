"""Optional second-stage reranking for retrieval candidates."""
from __future__ import annotations

import os
import time
from typing import Any

import requests
from dotenv import load_dotenv

from .config import RetrievalSettings, RerankConfig
from .types import SearchHit


class Reranker:
    """
    Lightweight wrapper around the rerank endpoint.

    The retrieval layer treats rerank as optional enhancement. If the service is
    unavailable, the caller can safely fall back to the fused first-stage order.
    """

    def __init__(self, *, settings: RetrievalSettings) -> None:
        self._settings = settings
        self._config = settings.rerank

    def _load_env(self) -> tuple[str, str]:
        load_dotenv(self._settings.api.env_file, override=False)
        api_key = os.getenv(self._settings.api.api_key_env, "").strip()
        base_url = os.getenv(self._settings.api.base_url_env, "").strip().rstrip("/")
        if not api_key or not base_url:
            raise ValueError("Missing rerank API credentials")
        return api_key, base_url

    def _request(self, query: str, documents: list[str]) -> list[float]:
        """Call the rerank model and return one score per candidate document."""
        api_key, base_url = self._load_env()
        # DashScope rerank uses the native API path, not the OpenAI-compatible path
        rerank_base = base_url.replace("/compatible-mode/v1", "/api/v1")
        endpoint = f"{rerank_base}/services/rerank/text-rerank/text-rerank"
        body: dict[str, Any] = {
            "model": self._config.model_name,
            "input": {
                "query": query,
                "documents": documents,
            },
            "parameters": {
                "prompt": self._config.prompt,
            },
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        response = None
        last_error: Exception | None = None
        for attempt in range(max(1, self._config.max_retries + 1)):
            try:
                response = requests.post(endpoint, headers=headers, json=body, timeout=self._config.timeout_seconds)
                if response.status_code not in {408, 409, 429, 500, 502, 503, 504}:
                    break
            except requests.RequestException as exc:
                last_error = exc
            if attempt < self._config.max_retries:
                time.sleep(2**attempt)
        if response is None:
            raise RuntimeError(f"Rerank request failed: {last_error}")
        if response.status_code >= 400:
            raise RuntimeError(f"Rerank failed: {response.status_code} {response.text[:1000]}")
        payload = response.json()
        data = (payload.get("output") or {}).get("results") or []
        return [float(item.get("relevance_score", 0.0)) for item in data]

    def rerank(self, query: str, hits: list[SearchHit]) -> list[SearchHit]:
        """
        Rerank first-stage hits and return a new ordered list.

        Each candidate is reranked on `retrieval_text` so the model sees both the
        raw chunk content and the structural prefix added during process time.
        """
        if not self._config.enabled or not hits:
            return hits

        documents = [hit.retrieval_text or hit.content for hit in hits]
        scores = self._request(query, documents)
        rescored: list[SearchHit] = []
        for hit, score in zip(hits, scores, strict=False):
            if self._config.min_score is not None and score < self._config.min_score:
                continue
            rescored.append(
                SearchHit(
                    chunk_id=hit.chunk_id,
                    score=score,
                    rank=hit.rank,
                    doc_id=hit.doc_id,
                    doc_name=hit.doc_name,
                    product_name=hit.product_name,
                    content=hit.content,
                    retrieval_text=hit.retrieval_text,
                    image_abs_paths=hit.image_abs_paths,
                    token_count=hit.token_count,
                    section_title=hit.section_title,
                    header_path=hit.header_path,
                    big_chunk_id=hit.big_chunk_id,
                    mid_chunk_id=hit.mid_chunk_id,
                    retrieval_source="rerank",
                    scores={**hit.scores, "rerank": score},
                )
            )

        rescored.sort(key=lambda item: item.score, reverse=True)
        return [
            SearchHit(
                chunk_id=hit.chunk_id,
                score=hit.score,
                rank=index + 1,
                doc_id=hit.doc_id,
                doc_name=hit.doc_name,
                product_name=hit.product_name,
                content=hit.content,
                retrieval_text=hit.retrieval_text,
                image_abs_paths=hit.image_abs_paths,
                token_count=hit.token_count,
                section_title=hit.section_title,
                header_path=hit.header_path,
                big_chunk_id=hit.big_chunk_id,
                mid_chunk_id=hit.mid_chunk_id,
                retrieval_source=hit.retrieval_source,
                scores=hit.scores,
            )
            for index, hit in enumerate(rescored)
        ]
