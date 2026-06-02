"""Tests for images, context, and normalizer modules."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from answer.context import format_context, _chunk_to_evidence
from answer.normalizer import normalize_answer, repair_inline_markers
from answer.models import AnswerPayload


# ---------------------------------------------------------------------------
# context
# ---------------------------------------------------------------------------

def _make_chunk(**overrides) -> dict:
    defaults = {
        "chunk_id": "c_001",
        "doc_name": "Test Manual",
        "section_title": "Section A",
        "header_path": ["Manual", "Section A"],
        "content": "Some content text here.",
        "text": "Some content text here.",
        "image_abs_paths": ["/tmp/img_001.jpg"],
        "rank": 1,
    }
    defaults.update(overrides)
    return defaults


def test_format_context_empty():
    ctx = format_context([], max_chars=5000)
    data = json.loads(ctx)
    assert data["evidence"] == []


def test_format_context_basic():
    chunks = [_make_chunk()]
    ctx = format_context(chunks, max_chars=5000)
    data = json.loads(ctx)
    assert len(data["evidence"]) == 1
    assert data["evidence"][0]["doc_name"] == "Test Manual"


def test_format_context_truncation():
    chunks = [_make_chunk(content="x" * 10000)]
    ctx = format_context(chunks, max_chars=500)
    data = json.loads(ctx)
    assert len(ctx) <= 600  # some slack for JSON overhead


def test_format_context_multiple():
    chunks = [_make_chunk(chunk_id=f"c_{i}", content=f"Content {i}") for i in range(5)]
    ctx = format_context(chunks, max_chars=2000)
    data = json.loads(ctx)
    assert len(data["evidence"]) >= 1


# ---------------------------------------------------------------------------
# normalizer
# ---------------------------------------------------------------------------

def test_repair_inline_markers():
    content = "Turn on the camera [图片:Manual24_0] then press OK."
    repaired, slots = repair_inline_markers(content, allowed=["Manual24_0"])
    assert "<PIC>" in repaired
    assert slots == ["Manual24_0"]


def test_repair_inline_markers_unknown():
    content = "See [图片:unknown_img] for details."
    repaired, slots = repair_inline_markers(content, allowed=["Manual24_0"])
    assert "<PIC>" not in repaired
    assert slots == []


def test_normalize_answer_basic():
    answer = AnswerPayload(content="Answer with <PIC> here", images=["img_001"])
    norm = normalize_answer(answer, allowed_images=["img_001"])
    assert "<PIC>" in norm.content
    assert "img_001" in norm.images


def test_normalize_answer_no_images():
    answer = AnswerPayload(content="No images needed", images=[])
    norm = normalize_answer(answer, allowed_images=[])
    assert "<PIC>" not in norm.content
    assert norm.images == []


def test_normalize_answer_dedup():
    answer = AnswerPayload(
        content="A <PIC> B <PIC>",
        images=["img_001", "img_001"],
    )
    norm = normalize_answer(answer, allowed_images=["img_001"])
    assert len(norm.images) <= 2


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
