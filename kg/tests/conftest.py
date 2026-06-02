"""Shared fixtures for kg tests."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture()
def tmp_root(tmp_path: Path):
    """Provide a temporary root directory for graph store."""
    return tmp_path / "kg_state"


@pytest.fixture()
def sample_chunks() -> list[dict]:
    """Three minimal small chunks for testing."""
    return [
        {
            "chunk_id": "test_manual_small_0001",
            "chunk_type": "small",
            "doc_id": "test_manual",
            "doc_name": "Test Manual",
            "mid_chunk_id": "test_manual_mid_0001",
            "big_chunk_id": "test_manual_big_0001",
            "text": "To connect to WiFi, go to Settings > Network and select your network.",
            "section_title": "WiFi Setup",
            "retrieval_text": "WiFi Setup instructions",
            "header_path": ["Setup", "WiFi Setup"],
            "token_count": 50,
        },
        {
            "chunk_id": "test_manual_small_0002",
            "chunk_type": "small",
            "doc_id": "test_manual",
            "doc_name": "Test Manual",
            "mid_chunk_id": "test_manual_mid_0002",
            "big_chunk_id": "test_manual_big_0002",
            "text": "If WiFi connection fails, ensure network permissions are enabled in System > Permissions.",
            "section_title": "Troubleshooting",
            "retrieval_text": "WiFi troubleshooting",
            "header_path": ["Troubleshooting"],
            "token_count": 40,
        },
        {
            "chunk_id": "test_manual_small_0003",
            "chunk_type": "small",
            "doc_id": "test_manual",
            "doc_name": "Test Manual",
            "mid_chunk_id": "test_manual_mid_0002",
            "big_chunk_id": "test_manual_big_0002",
            "text": "Factory reset: hold the reset button for 10 seconds. This will erase all network settings.",
            "section_title": "Factory Reset",
            "retrieval_text": "Factory reset procedure",
            "header_path": ["Troubleshooting", "Factory Reset"],
            "token_count": 35,
        },
    ]


@pytest.fixture()
def manual_dir(tmp_path: Path, sample_chunks) -> Path:
    """Create a fake manual directory with small_chunks.jsonl."""
    d = tmp_path / "manuals" / "test_manual"
    d.mkdir(parents=True)
    with open(d / "small_chunks.jsonl", "w") as f:
        for c in sample_chunks:
            f.write(json.dumps(c) + "\n")
    # Write minimal mid/big
    with open(d / "mid_chunks.jsonl", "w") as f:
        f.write(json.dumps({"chunk_id": "test_manual_mid_0001", "big_chunk_id": "test_manual_big_0001"}) + "\n")
        f.write(json.dumps({"chunk_id": "test_manual_mid_0002", "big_chunk_id": "test_manual_big_0002"}) + "\n")
    with open(d / "big_chunks.jsonl", "w") as f:
        f.write(json.dumps({"chunk_id": "test_manual_big_0001", "section_title": "Setup"}) + "\n")
        f.write(json.dumps({"chunk_id": "test_manual_big_0002", "section_title": "Troubleshooting"}) + "\n")
    return d
