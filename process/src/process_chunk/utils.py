from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable


def safe_id(value: str, *, prefix: str = "id") -> str:
    """
    Build a stable filesystem-safe identifier.

    The readable slug is kept when possible, while the digest prevents collisions
    across manuals with similar names after normalization.
    """
    digest = hashlib.md5(value.encode("utf-8")).hexdigest()[:12]
    slug = re.sub(r"[^0-9A-Za-z_]+", "_", value.strip()).strip("_")
    if slug and slug[0].isalpha():
        return f"{slug[:80]}_{digest}"
    return f"{prefix}_{digest}"


def content_hash(value: str) -> str:
    """Return a stable content hash used by incremental rebuild steps."""
    return hashlib.md5(value.encode("utf-8")).hexdigest()


def normalize_text(value: str) -> str:
    """Normalize spacing noise that commonly appears in OCR-style manuals."""
    value = value.replace("\ufeff", "")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL file into a list of dictionaries."""
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    """Write dictionaries as UTF-8 JSONL, creating parent directories when needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
