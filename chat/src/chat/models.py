"""Data models for the multi-turn chat layer."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid


@dataclass(slots=True)
class Turn:
    """
    One user/assistant exchange stored in session history.

    The chat layer stores only the user message and final assistant answer, not the
    full retrieval trace, to keep persisted history compact and easy to inspect.
    """
    turn_id: str
    user_message: str
    assistant_message: str
    timestamp: str
    image_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "user_message": self.user_message,
            "assistant_message": self.assistant_message,
            "timestamp": self.timestamp,
            "image_ids": self.image_ids,
            "metadata": self.metadata,
        }

    @classmethod
    def create(cls, user_message: str, assistant_message: str, image_ids: list[str] | None = None, **meta: Any) -> "Turn":
        return cls(
            turn_id=str(uuid.uuid4())[:8],
            user_message=user_message,
            assistant_message=assistant_message,
            timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            image_ids=image_ids or [],
            metadata=meta,
        )


@dataclass(slots=True)
class Session:
    """Persisted conversation session with user-isolated history."""
    session_id: str
    user_id: str = "default"
    turns: list[Turn] = field(default_factory=list)
    summary: str = ""
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "turns": [t.to_dict() for t in self.turns],
            "summary": self.summary,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @property
    def turn_count(self) -> int:
        return len(self.turns)

    @classmethod
    def create(cls, session_id: str | None = None, user_id: str = "default") -> "Session":
        return cls(
            session_id=session_id or str(uuid.uuid4())[:12],
            user_id=user_id,
            created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )


@dataclass(slots=True)
class ChatResponse:
    """Structured return value for one chat turn."""
    session_id: str
    user_message: str
    assistant_message: str
    rewritten_query: str
    turn_id: str
    history_turns_used: int
    summary_used: bool
    image_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_message": self.user_message,
            "assistant_message": self.assistant_message,
            "rewritten_query": self.rewritten_query,
            "turn_id": self.turn_id,
            "history_turns_used": self.history_turns_used,
            "summary_used": self.summary_used,
            "image_ids": self.image_ids,
        }
