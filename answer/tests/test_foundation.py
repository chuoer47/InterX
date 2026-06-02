"""Tests for answer foundation modules."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from answer.models import (
    AnswerPayload,
    GranularityAnswer,
    RecallMeta,
    QAResult,
    BatchRecord,
)


def test_answer_payload():
    p = AnswerPayload(content="Hello <PIC>", images=["img_001"])
    d = p.model_dump()
    assert d["content"] == "Hello <PIC>"
    assert d["images"] == ["img_001"]


def test_answer_payload_no_images():
    p = AnswerPayload(content="No images here")
    assert p.images == []


def test_granularity_answer():
    ga = GranularityAnswer(
        level="small",
        answer=AnswerPayload(content="small answer"),
        context_text="context",
        chunk_ids=["c1", "c2"],
        image_ids=["img1"],
        raw_response="raw",
    )
    d = ga.to_dict()
    assert d["level"] == "small"
    assert d["chunk_ids"] == ["c1", "c2"]


def test_recall_meta():
    meta = RecallMeta(
        query="test",
        original_query="test",
        rewritten_queries=["q1", "q2"],
        channels_used=["dense", "bm25", "rewrite_1", "rewrite_2"],
        channel_weights={"dense": 0.25},
        small_hit_count=10,
        mid_hit_count=5,
        big_hit_count=3,
        elapsed_seconds=1.5,
    )
    d = meta.to_dict()
    assert d["small_hit_count"] == 10
    assert len(d["rewritten_queries"]) == 2


def test_qa_result():
    small = GranularityAnswer(
        level="small",
        answer=AnswerPayload(content="s"),
        context_text="ctx_s",
        chunk_ids=["c1"],
        image_ids=[],
        raw_response="r",
    )
    mid = GranularityAnswer(
        level="mid",
        answer=AnswerPayload(content="m"),
        context_text="ctx_m",
        chunk_ids=["c2"],
        image_ids=[],
        raw_response="r",
    )
    big = GranularityAnswer(
        level="big",
        answer=AnswerPayload(content="b"),
        context_text="ctx_b",
        chunk_ids=["c3"],
        image_ids=[],
        raw_response="r",
    )
    meta = RecallMeta(
        query="q", original_query="q", rewritten_queries=[],
        channels_used=["dense"], channel_weights={},
        small_hit_count=1, mid_hit_count=1, big_hit_count=1,
        elapsed_seconds=0.5,
    )
    result = QAResult(
        question="q",
        final_answer=AnswerPayload(content="final"),
        small_answer=small,
        mid_answer=mid,
        big_answer=big,
        recall_meta=meta,
        elapsed_seconds=2.0,
    )
    d = result.to_dict()
    assert d["question"] == "q"
    assert d["final_answer"]["content"] == "final"
    assert d["small_answer"]["level"] == "small"


def test_batch_record():
    rec = BatchRecord(
        id="1",
        question="test",
        answer=AnswerPayload(content="ok"),
        success=True,
        attempts=1,
    )
    d = rec.to_dict()
    assert d["success"] is True
    assert d["error"] is None


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
