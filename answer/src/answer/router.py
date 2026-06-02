"""Router: classify questions as manual-related or general customer service."""
from __future__ import annotations

import json
import logging
from typing import Any

from .config import LLMEndpoint, QASettings
from .utils import extract_json, get_openai_client, load_prompt

log = logging.getLogger(__name__)


def route_question(
    question: str,
    *,
    settings: QASettings,
    user_images: list[str] | None = None,
) -> bool:
    """Return True if the question should go through RAG, False for general LLM.

    Routing is intentionally conservative: when in doubt, returns True (RAG).
    Questions with images always go to RAG (skipping the router entirely).
    """
    # Questions with images always go to RAG
    if user_images:
        return True

    try:
        prompt_template = load_prompt("router.md")
        prompt = prompt_template.format(question=question)

        client = get_openai_client(
            settings.llm.env_file,
            settings.llm.api_key_env,
            settings.llm.base_url_env,
        )
        model = settings.llm.model_name
        if not model:
            from .utils import resolve_model_name
            model = resolve_model_name(settings.llm.model_name_env)

        response = client.with_options(timeout=10.0).chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=32,
        )
        raw = response.choices[0].message.content or ""
        data = extract_json(raw)
        route = str(data.get("route", "manual")).strip().lower()
        return route == "manual"

    except Exception as exc:
        log.warning("Router failed, defaulting to RAG: %s", exc)
        return True


def answer_general(
    question: str,
    *,
    settings: QASettings,
) -> tuple[Any, str]:
    """Answer a general customer service question using LLM directly.

    Returns (AnswerPayload, raw_response).
    """
    from .models import AnswerPayload

    prompt_template = load_prompt("general_answer.md")
    system_prompt = prompt_template

    user_text = f"<user_question>\n{question}\n</user_question>"

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]

    client = get_openai_client(
        settings.llm.env_file,
        settings.llm.api_key_env,
        settings.llm.base_url_env,
    )
    model = settings.llm.model_name
    if not model:
        from .utils import resolve_model_name
        model = resolve_model_name(settings.llm.model_name_env)

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 2048,
    }

    response = client.with_options(timeout=90.0).chat.completions.create(**kwargs)
    raw = response.choices[0].message.content or ""
    data = extract_json(raw)
    answer = AnswerPayload.model_validate(data)
    return answer, raw
