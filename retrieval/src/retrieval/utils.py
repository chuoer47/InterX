"""Shared utilities for the retrieval package."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL file into memory."""
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_chunks_map(chunks_dir: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """
    Load all small, mid, and big chunk lookup tables from process artifacts.

    Retrieval uses small chunks for first-stage recall, but the mid and big maps are
    loaded alongside them so later aggregation can reconstruct the full hierarchy
    without additional disk lookups.
    """
    small_by_id: dict[str, dict[str, Any]] = {}
    mid_by_id: dict[str, dict[str, Any]] = {}
    big_by_id: dict[str, dict[str, Any]] = {}

    for manual_dir in sorted(chunks_dir.iterdir()):
        if not manual_dir.is_dir():
            continue
        for chunk in read_jsonl(manual_dir / "small_chunks.jsonl"):
            small_by_id[chunk["chunk_id"]] = chunk
        mid_path = manual_dir / "mid_chunks.jsonl"
        if mid_path.exists():
            for chunk in read_jsonl(mid_path):
                mid_by_id[chunk["chunk_id"]] = chunk
        big_path = manual_dir / "big_chunks.jsonl"
        if big_path.exists():
            for chunk in read_jsonl(big_path):
                big_by_id[chunk["chunk_id"]] = chunk

    return small_by_id, mid_by_id, big_by_id
