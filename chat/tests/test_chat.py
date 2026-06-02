"""Tests for chat layer modules."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from chat.models import Turn, Session, ChatResponse
from chat.store import save_session, load_session, list_sessions
from chat.memory import get_context_for_query, _format_turns_text
from chat.config import ChatSettings, MemoryConfig


# ---------------------------------------------------------------------------
# models
# ---------------------------------------------------------------------------

def test_turn_create():
    t = Turn.create("hello", "hi there")
    assert t.user_message == "hello"
    assert t.assistant_message == "hi there"
    assert t.turn_id
    assert t.timestamp


def test_session_create():
    s = Session.create("test-001")
    assert s.session_id == "test-001"
    assert s.turn_count == 0


def test_session_to_dict():
    s = Session.create("s1")
    s.turns.append(Turn.create("q1", "a1"))
    d = s.to_dict()
    assert d["session_id"] == "s1"
    assert len(d["turns"]) == 1


def test_chat_response():
    r = ChatResponse(
        session_id="s1",
        user_message="q",
        assistant_message="a",
        rewritten_query="q rewrote",
        turn_id="t1",
        history_turns_used=0,
        summary_used=False,
    )
    d = r.to_dict()
    assert d["rewritten_query"] == "q rewrote"


# ---------------------------------------------------------------------------
# store
# ---------------------------------------------------------------------------

def test_save_and_load_session():
    with tempfile.TemporaryDirectory() as tmpdir:
        session_dir = Path(tmpdir)
        s = Session.create("test-123")
        s.turns.append(Turn.create("What is Canon?", "Canon is a camera brand."))
        s.turns.append(Turn.create("How to reset?", "Press MENU..."))
        save_session(s, session_dir)

        loaded = load_session("test-123", session_dir)
        assert loaded is not None
        assert loaded.session_id == "test-123"
        assert loaded.turn_count == 2
        assert loaded.turns[0].user_message == "What is Canon?"


def test_load_nonexistent_session():
    with tempfile.TemporaryDirectory() as tmpdir:
        assert load_session("nope", Path(tmpdir)) is None


def test_list_sessions():
    with tempfile.TemporaryDirectory() as tmpdir:
        session_dir = Path(tmpdir)
        for sid in ["s1", "s2", "s3"]:
            save_session(Session.create(sid), session_dir)
        sessions = list_sessions(session_dir)
        assert sessions == ["s1", "s2", "s3"]


# ---------------------------------------------------------------------------
# memory
# ---------------------------------------------------------------------------

def _make_session_with_turns(n: int) -> Session:
    s = Session.create("test-mem")
    for i in range(n):
        s.turns.append(Turn.create(f"Question {i}", f"Answer {i}"))
    return s


def test_sliding_window_context():
    settings = ChatSettings(
        root=Path("."), config_path=Path("."),
        llm=None,  # type: ignore[arg-type]
        memory=MemoryConfig(
            strategy="sliding_window", window_size=2, max_summary_tokens=500,
            summary_trigger_turns=10, temperature=0.3, timeout_seconds=30, max_retries=1,
        ),
        query_rewrite=None,  # type: ignore[arg-type]
        session_dir=Path("."),
    )
    session = _make_session_with_turns(5)
    ctx, turns_used, summary_used = get_context_for_query(session, settings=settings)
    assert turns_used == 2
    assert summary_used is False
    assert "Question 3" in ctx
    assert "Question 4" in ctx
    assert "Question 0" not in ctx


def test_sliding_summary_context():
    settings = ChatSettings(
        root=Path("."), config_path=Path("."),
        llm=None,  # type: ignore[arg-type]
        memory=MemoryConfig(
            strategy="sliding_summary", window_size=2, max_summary_tokens=500,
            summary_trigger_turns=10, temperature=0.3, timeout_seconds=30, max_retries=1,
        ),
        query_rewrite=None,  # type: ignore[arg-type]
        session_dir=Path("."),
    )
    session = _make_session_with_turns(5)
    session.summary = "User asked about Canon cameras."
    ctx, turns_used, summary_used = get_context_for_query(session, settings=settings)
    assert turns_used == 2
    assert summary_used is True
    assert "Canon cameras" in ctx
    assert "Question 4" in ctx


def test_empty_session_context():
    settings = ChatSettings(
        root=Path("."), config_path=Path("."),
        llm=None,  # type: ignore[arg-type]
        memory=MemoryConfig(
            strategy="sliding_summary", window_size=5, max_summary_tokens=500,
            summary_trigger_turns=10, temperature=0.3, timeout_seconds=30, max_retries=1,
        ),
        query_rewrite=None,  # type: ignore[arg-type]
        session_dir=Path("."),
    )
    session = Session.create("empty")
    ctx, turns_used, summary_used = get_context_for_query(session, settings=settings)
    assert ctx == ""
    assert turns_used == 0
    assert summary_used is False


def test_format_turns_text():
    turns = [Turn.create("Q1", "A1"), Turn.create("Q2", "A2")]
    text = _format_turns_text(turns)
    assert "用户: Q1" in text
    assert "客服: A1" in text
    assert "用户: Q2" in text


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
