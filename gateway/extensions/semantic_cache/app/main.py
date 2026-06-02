from __future__ import annotations

import json
import os
import time
from hashlib import sha256
from typing import Any

import httpx
import redis
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from fastapi.responses import Response

app = FastAPI(title="InterX Semantic Cache")
redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
CACHE_NS = "interx:semantic"
THRESHOLD = float(os.getenv("SEMANTIC_CACHE_THRESHOLD", "0.92"))
MAX_CANDIDATES = int(os.getenv("SEMANTIC_CACHE_MAX_CANDIDATES", "5"))
LITELLM_URL = os.getenv("LITELLM_PROXY_URL", "http://127.0.0.1:4000")
LITELLM_MASTER_KEY = os.getenv("LITELLM_MASTER_KEY", "")
SEMANTIC_MODEL = os.getenv("SEMANTIC_CACHE_MODEL", "gpt-4o-mini")

REQS = Counter("semantic_cache_requests_total", "Total semantic cache requests")
HITS = Counter("semantic_cache_hits_total", "Semantic cache hits")
MISSES = Counter("semantic_cache_misses_total", "Semantic cache misses")
EXACT_HITS = Counter("semantic_cache_exact_hits_total", "Exact cache hits")
SEMANTIC_HITS = Counter("semantic_cache_semantic_hits_total", "Semantic cache hits after adjudication")
LAT = Histogram("semantic_cache_request_seconds", "Semantic cache latency")

class CacheRequest(BaseModel):
    model: str
    messages: list[dict[str, Any]]
    stream: bool = False
    metadata: dict[str, Any] | None = None


def exact_key(payload: dict[str, Any]) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return f"{CACHE_NS}:exact:" + sha256(text.encode("utf-8")).hexdigest()


def candidate_key(model: str) -> str:
    return f"{CACHE_NS}:candidates:{model}"


def summarize_messages(messages: list[dict[str, Any]]) -> str:
    parts = []
    for msg in messages[-6:]:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, list):
            flattened = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    flattened.append(item.get("text", ""))
                elif isinstance(item, dict):
                    flattened.append(f"<{item.get('type','item')}>")
            content = " ".join(flattened)
        parts.append(f"{role}: {content}")
    return "\n".join(parts)[:4000]


async def semantic_yes_no(current: str, candidate: str) -> tuple[bool, float]:
    if not SEMANTIC_MODEL:
        return False, 0.0
    prompt = (
        "You judge whether two customer-support requests are semantically equivalent enough "
        "to safely reuse the same answer. Reply JSON: {\"hit\": true|false, \"confidence\": 0..1}."
    )
    payload = {
        "model": SEMANTIC_MODEL,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Request A:\n{current}\n\nRequest B:\n{candidate}"},
        ],
        "stream": False,
    }
    headers = {"Authorization": f"Bearer {LITELLM_MASTER_KEY}"} if LITELLM_MASTER_KEY else {}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{LITELLM_URL}/v1/chat/completions", json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    try:
        text = data["choices"][0]["message"]["content"]
        parsed = json.loads(text)
        confidence = float(parsed.get("confidence", 0))
        return bool(parsed.get("hit")) and confidence >= THRESHOLD, confidence
    except Exception:
        return False, 0.0


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/v1/cache/chat/completions")
async def cached_completion(req: CacheRequest) -> dict[str, Any]:
    started = time.perf_counter()
    REQS.inc()
    if req.stream:
        raise HTTPException(status_code=400, detail="semantic cache endpoint does not support stream replay")

    payload = req.model_dump()
    ex_key = exact_key(payload)
    exact_hit = redis_client.get(ex_key)
    if exact_hit:
        EXACT_HITS.inc()
        HITS.inc()
        LAT.observe(time.perf_counter() - started)
        data = json.loads(exact_hit)
        data.setdefault('_cache', {})
        data['_cache'].update({'hit': True, 'type': 'exact', 'candidate_count': 0})
        return data

    summary = summarize_messages(req.messages)
    candidates = redis_client.lrange(candidate_key(req.model), 0, MAX_CANDIDATES - 1)
    for idx, raw in enumerate(candidates):
        row = json.loads(raw)
        decision, confidence = await semantic_yes_no(summary, row.get("summary", ""))
        if decision:
            cached = redis_client.get(row["cache_key"])
            if cached:
                SEMANTIC_HITS.inc()
                HITS.inc()
                LAT.observe(time.perf_counter() - started)
                data = json.loads(cached)
                data.setdefault('_cache', {})
                data['_cache'].update({
                    'hit': True,
                    'type': 'semantic',
                    'candidate_count': len(candidates),
                    'matched_candidate_index': idx,
                    'confidence': confidence,
                })
                return data

    headers = {"Authorization": f"Bearer {LITELLM_MASTER_KEY}"} if LITELLM_MASTER_KEY else {}
    async with httpx.AsyncClient(timeout=600) as client:
        resp = await client.post(f"{LITELLM_URL}/v1/chat/completions", json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    data.setdefault('_cache', {})
    data['_cache'].update({'hit': False, 'type': 'miss', 'candidate_count': len(candidates)})
    redis_client.setex(ex_key, 3600, json.dumps(data, ensure_ascii=False))
    candidate_record = {"cache_key": ex_key, "summary": summary}
    redis_client.lpush(candidate_key(req.model), json.dumps(candidate_record, ensure_ascii=False))
    redis_client.ltrim(candidate_key(req.model), 0, 49)
    MISSES.inc()
    LAT.observe(time.perf_counter() - started)
    return data
