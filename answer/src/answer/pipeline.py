"""Main multi-granularity answer pipeline."""
from __future__ import annotations

import sys
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .config import AnswerLayerConfig, LLMEndpoint, QASettings
from .context import format_context
from .images import ImageEvidence, build_image_content_blocks, collect_image_evidences, format_image_manifest
from .models import AnswerPayload, GranularityAnswer, QAResult, RecallMeta
from .normalizer import normalize_answer
from .query_rewrite import rewrite_query
from .router import answer_general, route_question
from .utils import extract_json, get_openai_client, load_prompt, resolve_model_name

log = logging.getLogger(__name__)

# The answer package depends on retrieval as a sibling package in the repo layout.
_RETRIEVAL_SRC = str(Path(__file__).resolve().parents[3] / "retrieval" / "src")
if _RETRIEVAL_SRC not in sys.path:
    sys.path.insert(0, _RETRIEVAL_SRC)

from retrieval import reload as retrieval_reload  # noqa: E402
from retrieval import search_hierarchical  # noqa: E402
from retrieval.types import BigHit, HierarchicalResult, MidHit, SearchHit  # noqa: E402

# KG expansion — lazy import so the answer package works even without kuzu installed
_KG_AVAILABLE = True
try:
    _KG_SRC = str(Path(__file__).resolve().parents[3] / "kg" / "src")
    if _KG_SRC not in sys.path:
        sys.path.insert(0, _KG_SRC)
    from kg.expander import ChunkExpander  # noqa: E402
    from kg.config import KGSettings  # noqa: E402
except Exception:
    _KG_AVAILABLE = False


def _call_llm(
    *,
    endpoint: LLMEndpoint,
    config: AnswerLayerConfig,
    messages: list[dict[str, Any]],
    response_format_json: bool = True,
) -> tuple[AnswerPayload, str]:
    """
    Call one LLM endpoint and parse the result into `AnswerPayload`.

    Some models reject strict JSON response formatting even when they otherwise
    support chat completions, so the helper can automatically retry without the
    `response_format` hint.
    """
    client = get_openai_client(endpoint.env_file, endpoint.api_key_env, endpoint.base_url_env)
    model = resolve_model_name(endpoint.env_file, endpoint.model_name, endpoint.model_name_env)

    last_error: Exception | None = None
    rf_enabled = response_format_json and config.response_format_json

    for attempt in range(max(1, config.max_retries + 1)):
        try:
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": config.temperature,
                "max_tokens": config.max_tokens,
            }
            if rf_enabled:
                kwargs["response_format"] = {"type": "json_object"}

            response = client.with_options(timeout=config.timeout_seconds).chat.completions.create(**kwargs)
            raw = (response.choices[0].message.content or "").strip()
            data = extract_json(raw)
            return AnswerPayload.model_validate(data), raw
        except Exception as exc:
            last_error = exc
            if rf_enabled and "response_format" in str(exc):
                rf_enabled = False
            if attempt < config.max_retries:
                time.sleep(config.retry_backoff_seconds * (2**attempt))

    raise RuntimeError(f"LLM call failed: {last_error}")


def _answer_at_level(
    question: str,
    *,
    level: str,
    chunks: list[dict[str, Any]],
    image_evidences: list[ImageEvidence],
    settings: QASettings,
) -> GranularityAnswer:
    """
    Generate one answer from one evidence granularity.

    Small, mid, and big answers all share the same execution shape but use
    different prompts and context budgets tailored to their evidence scale.
    """
    layer_config_map = {
        "small": settings.small_layer,
        "mid": settings.mid_layer,
        "big": settings.big_layer,
    }
    config = layer_config_map[level]
    prompt_map = {
        "small": "small_answer.md",
        "mid": "mid_answer.md",
        "big": "big_answer.md",
    }
    system_prompt = load_prompt(prompt_map[level])

    context_text = format_context(chunks, max_chars=config.max_context_chars)
    image_manifest = format_image_manifest(image_evidences)
    image_ids = [e.image_id for e in image_evidences]

    user_text = (
        f"<user_question>\n{question}\n</user_question>\n\n"
        f"<retrieved_evidence>\n{context_text}\n</retrieved_evidence>\n\n"
        f"<available_images>\n{image_manifest}\n</available_images>"
    )
    user_content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
    user_content.extend(build_image_content_blocks(image_evidences))

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    answer, raw = _call_llm(endpoint=settings.llm, config=config, messages=messages)
    answer = normalize_answer(answer, allowed_images=image_ids)

    return GranularityAnswer(
        level=level,
        answer=answer,
        context_text=context_text,
        chunk_ids=[str(c.get("chunk_id", "")) for c in chunks],
        image_ids=answer.images,
        raw_response=raw,
    )


def _ensemble_answer(
    question: str,
    *,
    small_ans: GranularityAnswer,
    mid_ans: GranularityAnswer,
    big_ans: GranularityAnswer,
    image_evidences: list[ImageEvidence],
    settings: QASettings,
) -> AnswerPayload:
    """
    Merge the three granularity answers into one final answer.

    The ensemble step lets the system combine precise facts, procedural details,
    and broader background context instead of forcing a single prompt to do all
    reasoning from raw retrieved evidence alone.
    """
    system_prompt = load_prompt("ensemble.md")

    image_manifest = format_image_manifest(image_evidences)
    image_ids = [e.image_id for e in image_evidences]

    user_text = (
        f"<user_question>\n{question}\n</user_question>\n\n"
        f"<granularity_answers>\n"
        f"<small_answer>\n{small_ans.answer.content}\n</small_answer>\n\n"
        f"<mid_answer>\n{mid_ans.answer.content}\n</mid_answer>\n\n"
        f"<big_answer>\n{big_ans.answer.content}\n</big_answer>\n"
        f"</granularity_answers>\n\n"
        f"<available_images>\n{image_manifest}\n</available_images>"
    )
    user_content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
    user_content.extend(build_image_content_blocks(image_evidences))

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    answer, _raw = _call_llm(endpoint=settings.llm, config=settings.ensemble_layer, messages=messages)
    return normalize_answer(answer, allowed_images=image_ids)


def _hits_to_dicts(hits: list[SearchHit]) -> list[dict[str, Any]]:
    """Convert small-chunk hits into generic dictionaries consumed by answer helpers."""
    return [h.to_dict() for h in hits]


def _mid_to_dicts(hits: list[MidHit]) -> list[dict[str, Any]]:
    """Convert mid-level hits into plain dictionaries for context formatting."""
    return [mid.to_dict() for mid in hits]


def _big_to_dicts(hits: list[BigHit]) -> list[dict[str, Any]]:
    """Convert big-level hits into plain dictionaries for context formatting."""
    return [big.to_dict() for big in hits]


def _merge_chunks_for_images(*chunk_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge ranked chunk dictionaries while preserving the first occurrence order."""
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for chunks in chunk_groups:
        for chunk in chunks:
            key = str(chunk.get("chunk_id") or id(chunk))
            if key in seen:
                continue
            seen.add(key)
            merged.append(chunk)
    return merged


def answer(
    question: str,
    *,
    settings: QASettings | None = None,
    top_k: int | None = None,
    user_images: list[str] | None = None,
) -> QAResult:
    """
    Run the full answer pipeline: recall -> image collection -> 3 parallel answers -> ensemble.

    The answer layer keeps the retrieval stage intact and adds orchestration on top
    instead of pushing conversation or business logic down into retrieval itself.
    """
    if settings is None:
        settings = QASettings.load()

    started = time.monotonic()

    # --- Router: classify question as manual or general ---
    if not route_question(question, settings=settings, user_images=user_images):
        log.info("Router: general question, skipping RAG")
        general_answer, general_raw = answer_general(question, settings=settings)
        elapsed = time.monotonic() - started
        empty_meta = RecallMeta(
            query=question,
            original_query=question,
            rewritten_queries=[],
            channels_used=[],
            channel_weights={},
            small_hit_count=0,
            mid_hit_count=0,
            big_hit_count=0,
            elapsed_seconds=0.0,
        )
        empty_payload = AnswerPayload(content="", images=[])
        empty_gran = GranularityAnswer(
            level="small",
            answer=empty_payload,
            context_text="",
            chunk_ids=[],
            image_ids=[],
            raw_response="",
        )
        return QAResult(
            question=question,
            final_answer=general_answer,
            small_answer=GranularityAnswer(level="small", answer=general_answer, context_text="", chunk_ids=[], image_ids=[], raw_response=general_raw),
            mid_answer=empty_gran,
            big_answer=empty_gran,
            recall_meta=empty_meta,
            elapsed_seconds=round(elapsed, 3),
        )

    retrieval_reload()

    rewritten = rewrite_query(question, settings=settings)

    # The current implementation still queries retrieval with the original question.
    # Rewrites are generated and surfaced in metadata now so they can be folded into
    # multi-query recall later without changing the answer contract again.
    result: HierarchicalResult = search_hierarchical(
        question,
        top_k=top_k or settings.retrieval_top_k,
        image_paths=user_images,
    )

    # --- KG expansion (toggle-able, graceful degradation) ---
    kg_expansion_count = 0
    if settings.kg.enabled and _KG_AVAILABLE:
        try:
            expander = ChunkExpander(KGSettings.load())
            expansion = expander.expand(
                [h.to_dict() for h in result.small_hits],
                max_expanded=settings.kg.max_expanded,
            )
            expander.close()
            if expansion.expanded_hits:
                # Merge expanded hits into small_hits (dedup by chunk_id)
                existing_ids = {h.chunk_id for h in result.small_hits}
                for eh in expansion.expanded_hits:
                    if eh["chunk_id"] not in existing_ids:
                        result.small_hits.append(SearchHit(
                            chunk_id=eh["chunk_id"],
                            score=eh.get("graph_score", 0.3),
                            rank=len(result.small_hits) + 1,
                            doc_id=eh.get("doc_id", ""),
                            doc_name=eh.get("doc_name", ""),
                            product_name=eh.get("product_name", ""),
                            content=eh.get("content", ""),
                            retrieval_text=eh.get("content", ""),
                            image_abs_paths=[],
                            token_count=len(eh.get("content", "")),
                            section_title=eh.get("section_title", ""),
                            header_path=[],
                            big_chunk_id=eh.get("big_chunk_id", ""),
                            mid_chunk_id=eh.get("mid_chunk_id", ""),
                            retrieval_source="kg_expand",
                        ))
                        existing_ids.add(eh["chunk_id"])
                kg_expansion_count = expansion.expansion_count
                log.info("KG expansion: +%d chunks", expansion.expansion_count)
            else:
                log.info("KG expansion: no new chunks found")
        except Exception as exc:
            log.warning("KG expansion failed, continuing without: %s", exc)
    elif settings.kg.enabled and not _KG_AVAILABLE:
        log.warning("KG enabled but kuzu not installed, skipping expansion")

    recall_elapsed = time.monotonic() - started
    recall_meta = RecallMeta(
        query=question,
        original_query=question,
        rewritten_queries=rewritten,
        channels_used=["dense", "bm25"],
        channel_weights={"dense": 0.65, "bm25": 0.35},
        small_hit_count=len(result.small_hits),
        mid_hit_count=len(result.mid_hits),
        big_hit_count=len(result.big_hits),
        elapsed_seconds=round(recall_elapsed, 3),
        kg_expansion_count=kg_expansion_count,
    )

    small_dicts = _hits_to_dicts(result.small_hits)
    mid_dicts = _mid_to_dicts(result.mid_hits)
    big_dicts = _big_to_dicts(result.big_hits)

    if settings.include_images:
        small_images = collect_image_evidences(
            small_dicts,
            image_dir=settings.image_dir,
            max_images=settings.small_layer.max_images,
        )
        mid_images = collect_image_evidences(
            mid_dicts,
            image_dir=settings.image_dir,
            max_images=settings.mid_layer.max_images,
        )
        big_images = collect_image_evidences(
            big_dicts,
            image_dir=settings.image_dir,
            max_images=settings.big_layer.max_images,
        )
        ensemble_images = collect_image_evidences(
            _merge_chunks_for_images(small_dicts, mid_dicts, big_dicts),
            image_dir=settings.image_dir,
            max_images=settings.ensemble_layer.max_images,
        )
    else:
        small_images = []
        mid_images = []
        big_images = []
        ensemble_images = []

    # The three answer branches are independent once retrieval is done, so they can
    # run in parallel to reduce total latency.
    level_chunks = {
        "small": small_dicts,
        "mid": mid_dicts,
        "big": big_dicts,
    }
    answers_by_level: dict[str, GranularityAnswer] = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(
                _answer_at_level,
                question,
                level=level,
                chunks=chunks,
                image_evidences={
                    "small": small_images,
                    "mid": mid_images,
                    "big": big_images,
                }[level],
                settings=settings,
            ): level
            for level, chunks in level_chunks.items()
        }
        for future in as_completed(futures):
            level = futures[future]
            answers_by_level[level] = future.result()

    small_answer = answers_by_level["small"]
    mid_answer = answers_by_level["mid"]
    big_answer = answers_by_level["big"]

    final_answer = _ensemble_answer(
        question,
        small_ans=small_answer,
        mid_ans=mid_answer,
        big_ans=big_answer,
        image_evidences=ensemble_images,
        settings=settings,
    )

    elapsed = time.monotonic() - started
    return QAResult(
        question=question,
        final_answer=final_answer,
        small_answer=small_answer,
        mid_answer=mid_answer,
        big_answer=big_answer,
        recall_meta=recall_meta,
        elapsed_seconds=round(elapsed, 3),
    )
