"""Main multi-turn chat pipeline."""
from __future__ import annotations

import sys
from pathlib import Path

from .config import ChatSettings
from .memory import get_context_for_query, maybe_update_summary
from .models import ChatResponse, Session, Turn
from .query_rewrite import rewrite_query
from .store import load_session, save_session

_ANSWER_SRC = str(Path(__file__).resolve().parents[3] / "answer" / "src")
if _ANSWER_SRC not in sys.path:
    sys.path.insert(0, _ANSWER_SRC)


def _get_answer_fn():
    """Lazy import of the answer pipeline to avoid circular dependency issues."""
    from answer.pipeline import answer as answer_fn
    return answer_fn


def chat(
    user_message: str,
    *,
    session_id: str | None = None,
    user_id: str = "default",
    images: list[str] | None = None,
    settings: ChatSettings | None = None,
) -> ChatResponse:
    """
    Handle one multi-turn chat request.

    History is used only to rewrite the current user question into a more complete
    standalone query. The downstream answer layer then runs unchanged on that query.
    """
    if settings is None:
        settings = ChatSettings.load()

    if session_id:
        loaded = load_session(session_id, settings.session_dir, user_id=user_id)
        session = loaded if loaded else Session.create(session_id, user_id=user_id)
    else:
        session = Session.create(user_id=user_id)

    history_context, turns_used, summary_used = get_context_for_query(session, settings=settings)
    rewritten = rewrite_query(user_message, history_context=history_context, settings=settings)

    answer_fn = _get_answer_fn()
    result = answer_fn(rewritten, settings=None, user_images=images)

    assistant_message = result.final_answer.content
    image_ids = list(result.final_answer.images or [])

    turn = Turn.create(
        user_message=user_message,
        assistant_message=assistant_message,
        image_ids=image_ids,
        rewritten_query=rewritten,
    )
    session.turns.append(turn)
    session.summary = maybe_update_summary(session, settings=settings)
    save_session(session, settings.session_dir, user_id=user_id)

    return ChatResponse(
        session_id=session.session_id,
        user_message=user_message,
        assistant_message=assistant_message,
        rewritten_query=rewritten,
        turn_id=turn.turn_id,
        history_turns_used=turns_used,
        summary_used=summary_used,
        image_ids=image_ids,
    )


def get_session(session_id: str, *, user_id: str = "default", settings: ChatSettings | None = None) -> Session | None:
    """Load one persisted session."""
    if settings is None:
        settings = ChatSettings.load()
    return load_session(session_id, settings.session_dir, user_id=user_id)


def reset_session(session_id: str, *, user_id: str = "default", settings: ChatSettings | None = None) -> Session:
    """Reset a session by replacing it with a fresh empty one."""
    if settings is None:
        settings = ChatSettings.load()
    session = Session.create(session_id, user_id=user_id)
    save_session(session, settings.session_dir, user_id=user_id)
    return session
