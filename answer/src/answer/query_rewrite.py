"""Query rewriting for multi-query recall in the answer pipeline."""
from __future__ import annotations

from .config import QASettings
from .utils import extract_json, get_openai_client, load_prompt, resolve_model_name


def rewrite_query(question: str, *, settings: QASettings) -> list[str]:
    """
    Generate alternative phrasings for the original question.

    Query rewriting is kept best-effort only. Retrieval should still work when the
    rewrite model fails or returns malformed JSON.
    """
    config = settings.query_rewrite
    if not config.enabled:
        return []

    try:
        client = get_openai_client(
            settings.rewrite_llm.env_file,
            settings.rewrite_llm.api_key_env,
            settings.rewrite_llm.base_url_env,
        )
        model = resolve_model_name(
            settings.rewrite_llm.env_file,
            settings.rewrite_llm.model_name,
            settings.rewrite_llm.model_name_env,
        )
        prompt_template = load_prompt("query_rewrite.md")
        prompt = prompt_template.format(question=question, num_variants=config.num_variants)

        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            timeout=config.timeout_seconds,
        )
        raw = (response.choices[0].message.content or "").strip()
        data = extract_json(raw)
        variants = data.get("variants") or []
        return [str(v).strip() for v in variants if str(v).strip()][: config.num_variants]
    except Exception:
        return []
