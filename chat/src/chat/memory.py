"""Memory strategies for multi-turn chat."""
from __future__ import annotations

from .config import ChatSettings
from .models import Session, Turn
from .utils import get_openai_client, load_prompt, resolve_model_name


def _format_turns_text(turns: list[Turn]) -> str:
    """Render turns into a compact dialogue transcript for prompts."""
    lines: list[str] = []
    for t in turns:
        lines.append(f"用户: {t.user_message}")
        lines.append(f"客服: {t.assistant_message}")
    return "\n".join(lines)


def _call_llm_for_summary(history_text: str, *, settings: ChatSettings) -> str:
    """
    Summarize the full history when the configured memory strategy requires it.

    Summaries let the system preserve long-range context without passing the full
    transcript into every later query rewrite prompt.
    """
    config = settings.memory
    try:
        client = get_openai_client(settings.llm.env_file, settings.llm.api_key_env, settings.llm.base_url_env)
        model = resolve_model_name(settings.llm.env_file, settings.llm.model_name, settings.llm.model_name_env)
        prompt_template = load_prompt("summarize.md")
        prompt = prompt_template.format(history=history_text)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=config.temperature,
            max_tokens=config.max_summary_tokens,
            timeout=config.timeout_seconds,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception:
        return ""


def get_context_for_query(session: Session, *, settings: ChatSettings) -> tuple[str, int, bool]:
    """
    Build the history context used for query rewriting.

    Only the rewrite step sees history. The answer layer still receives a rewritten
    standalone question instead of the raw conversation transcript.
    """
    config = settings.memory
    if not session.turns:
        return "", 0, False

    strategy = config.strategy
    if strategy == "sliding_window":
        recent = session.turns[-config.window_size:]
        return _format_turns_text(recent), len(recent), False

    if strategy == "summary":
        context_parts: list[str] = []
        summary_used = False
        if session.summary:
            context_parts.append(f"历史摘要: {session.summary}")
            summary_used = True
        if session.turns:
            last = session.turns[-1]
            context_parts.append(f"最近一轮:\n用户: {last.user_message}\n客服: {last.assistant_message}")
        return "\n\n".join(context_parts), min(1, len(session.turns)), summary_used

    if strategy == "sliding_summary":
        context_parts = []
        summary_used = False
        if session.summary:
            context_parts.append(f"历史摘要: {session.summary}")
            summary_used = True
        recent = session.turns[-config.window_size:]
        if recent:
            context_parts.append(f"最近 {len(recent)} 轮对话:\n{_format_turns_text(recent)}")
        return "\n\n".join(context_parts), len(recent), summary_used

    raise ValueError(f"Unknown memory strategy: {strategy}")


def maybe_update_summary(session: Session, *, settings: ChatSettings) -> str:
    """Update the rolling summary once the session becomes long enough."""
    config = settings.memory
    if len(session.turns) < config.summary_trigger_turns:
        return session.summary
    new_summary = _call_llm_for_summary(_format_turns_text(session.turns), settings=settings)
    return new_summary or session.summary
