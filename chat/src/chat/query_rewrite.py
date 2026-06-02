"""History-aware query rewriting for the chat layer."""
from __future__ import annotations

from .config import ChatSettings
from .utils import extract_json, get_openai_client, load_prompt, resolve_model_name


def rewrite_query(
    question: str,
    *,
    history_context: str,
    settings: ChatSettings,
) -> str:
    """
    Rewrite the current user message using conversation history.

    If history is empty or rewriting is disabled, the original question is returned
    unchanged so the rest of the pipeline stays deterministic.
    """
    config = settings.query_rewrite
    if not config.enabled or not history_context.strip():
        return question

    try:
        client = get_openai_client(settings.llm.env_file, settings.llm.api_key_env, settings.llm.base_url_env)
        model = resolve_model_name(settings.llm.env_file, settings.llm.model_name, settings.llm.model_name_env)
        prompt_template = load_prompt("rewrite.md")
        prompt = prompt_template.format(history=history_context, question=question)

        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            timeout=config.timeout_seconds,
        )
        raw = (response.choices[0].message.content or "").strip()
        data = extract_json(raw)
        rewritten = str(data.get("rewritten_query") or "").strip()
        return rewritten if rewritten else question
    except Exception:
        return question
