"""Data models for the answer layer."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field


class AnswerPayload(BaseModel):
    """
    Structured answer returned by the LLM.

    `content` may contain `<PIC>` placeholders, and `images` must stay aligned
    with those placeholders after normalization.
    """
    content: str = Field(
        description=(
            "Answer body, optionally containing <PIC> placeholders that must align "
            "positionally with the `images` list."
        )
    )
    images: list[str] = Field(default_factory=list, description="Image ids aligned with `<PIC>` placeholders.")


@dataclass(slots=True)
class GranularityAnswer:
    """LLM answer produced from one evidence granularity level."""
    level: str
    answer: AnswerPayload
    context_text: str
    chunk_ids: list[str]
    image_ids: list[str]
    raw_response: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "answer": self.answer.model_dump(),
            "context_text": self.context_text,
            "chunk_ids": self.chunk_ids,
            "image_ids": self.image_ids,
            "raw_response": self.raw_response,
        }


@dataclass(slots=True)
class RecallMeta:
    """Metadata describing the retrieval phase that fed the answer pipeline."""
    query: str
    original_query: str
    rewritten_queries: list[str]
    channels_used: list[str]
    channel_weights: dict[str, float]
    small_hit_count: int
    mid_hit_count: int
    big_hit_count: int
    elapsed_seconds: float
    kg_expansion_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "original_query": self.original_query,
            "rewritten_queries": self.rewritten_queries,
            "channels_used": self.channels_used,
            "channel_weights": self.channel_weights,
            "small_hit_count": self.small_hit_count,
            "mid_hit_count": self.mid_hit_count,
            "big_hit_count": self.big_hit_count,
            "elapsed_seconds": self.elapsed_seconds,
            "kg_expansion_count": self.kg_expansion_count,
        }


@dataclass(slots=True)
class QAResult:
    """Full output of the multi-granularity answer pipeline."""
    question: str
    final_answer: AnswerPayload
    small_answer: GranularityAnswer
    mid_answer: GranularityAnswer
    big_answer: GranularityAnswer
    recall_meta: RecallMeta
    elapsed_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "final_answer": self.final_answer.model_dump(),
            "small_answer": self.small_answer.to_dict(),
            "mid_answer": self.mid_answer.to_dict(),
            "big_answer": self.big_answer.to_dict(),
            "recall_meta": self.recall_meta.to_dict(),
            "elapsed_seconds": self.elapsed_seconds,
        }


@dataclass(slots=True)
class BatchRecord:
    """Result record used by batch evaluation or offline answer generation."""
    id: str
    question: str
    answer: AnswerPayload
    success: bool
    attempts: int
    error: str | None = None
    retrieved_chunk_ids: list[str] = field(default_factory=list)
    retrieved_doc_names: list[str] = field(default_factory=list)
    image_ids: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "answer": self.answer.model_dump(),
            "success": self.success,
            "attempts": self.attempts,
            "error": self.error,
            "retrieved_chunk_ids": self.retrieved_chunk_ids,
            "retrieved_doc_names": self.retrieved_doc_names,
            "image_ids": self.image_ids,
            "elapsed_seconds": self.elapsed_seconds,
        }

# Add kg_expanded field to RecallMeta - patching in place
