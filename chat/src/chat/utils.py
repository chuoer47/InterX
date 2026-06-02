"""Shared utilities for the chat package."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


def load_env(env_file: Path) -> None:
    """Load environment variables lazily from the configured env file."""
    load_dotenv(env_file, override=False)


def get_openai_client(env_file: Path, api_key_env: str, base_url_env: str) -> OpenAI:
    """Create the gateway-backed OpenAI-compatible client used by chat memory helpers."""
    load_env(env_file)
    api_key = os.getenv(api_key_env, "").strip()
    base_url = os.getenv(base_url_env, "").strip()
    if not api_key:
        raise ValueError(f"Missing {api_key_env} in {env_file}")
    if not base_url:
        raise ValueError(f"Missing {base_url_env} in {env_file}")
    return OpenAI(api_key=api_key, base_url=base_url)


def resolve_model_name(env_file: Path, explicit: str | None, model_name_env: str) -> str:
    """Resolve the model name from explicit config first, then environment fallback."""
    if explicit and explicit.strip():
        return explicit.strip()
    load_env(env_file)
    from_env = os.getenv(model_name_env, "").strip()
    if from_env:
        return from_env
    raise ValueError(f"Missing model: set model_name or {model_name_env}")


def extract_json(text: str) -> dict[str, Any]:
    """Extract a JSON object from an LLM response, tolerating markdown fences."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def load_prompt(name: str) -> str:
    """Load a prompt template from the chat package prompt directory."""
    path = Path(__file__).resolve().parent / "prompts" / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8").strip()
