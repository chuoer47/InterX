"""Context assembly helpers for the answer pipeline."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _truncate(text: str, max_chars: int) -> str:
    """Truncate text with an ellipsis while preserving a valid string payload."""
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _chunk_to_evidence(chunk: dict[str, Any]) -> dict[str, Any]:
    """
    Convert a retrieval chunk into the normalized evidence shape used in prompts.

    Image paths are converted to image ids because the downstream prompts only need
    stable anchors, not full filesystem paths.
    """
    text = str(chunk.get("content") or chunk.get("text") or "").strip()
    image_paths = chunk.get("image_abs_paths") or chunk.get("image_paths") or []
    image_ids = [Path(str(p)).stem for p in image_paths if str(p).strip()]
    return {
        "rank": chunk.get("rank"),
        "doc_name": chunk.get("doc_name"),
        "header_path": chunk.get("header_path") or [],
        "section_title": chunk.get("section_title") or "",
        "text": text,
        "images": image_ids,
    }


def format_context(
    chunks: list[dict[str, Any]],
    *,
    max_chars: int,
    language: str = "en",
) -> str:
    """
    Format retrieval evidence into a compact JSON block for LLM input.

    The function incrementally adds evidence and, when necessary, binary-searches
    the last chunk's text length so the final payload still fits the layer budget.
    """
    if not chunks:
        return json.dumps({"language": language, "evidence": []}, ensure_ascii=False)

    selected: list[dict[str, Any]] = []
    for chunk in chunks:
        evidence = _chunk_to_evidence(chunk)
        candidate = selected + [evidence]
        payload = json.dumps({"language": language, "evidence": candidate}, ensure_ascii=False, indent=2)
        if len(payload) <= max_chars:
            selected.append(evidence)
            continue

        text = str(evidence.get("text") or "")
        lo, hi = 0, len(text)
        best = None
        while lo <= hi:
            mid = (lo + hi) // 2
            truncated = dict(evidence)
            truncated["text"] = text if mid >= len(text) else _truncate(text, max(1, mid))
            trial = json.dumps(
                {"language": language, "evidence": selected + [truncated]},
                ensure_ascii=False,
                indent=2,
            )
            if len(trial) <= max_chars:
                best = truncated
                lo = mid + 1
            else:
                hi = mid - 1
        if best is not None:
            selected.append(best)
        break

    return json.dumps({"language": language, "evidence": selected}, ensure_ascii=False, indent=2)
