"""Tokenizer for BM25 sparse retrieval over mixed Chinese and English text."""
from __future__ import annotations

import re

CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")
ASCII_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")

try:
    import jieba
except ImportError:
    jieba = None  # type: ignore[assignment]


def tokenize(text: str) -> list[str]:
    """
    Tokenize mixed Chinese and English text for BM25.

    Chinese retrieval benefits from multiple granularities at once: whole words
    from `jieba`, plus character n-grams that remain robust when segmentation is
    imperfect or the query contains short product terms.
    """
    normalized = re.sub(r"\s+", " ", text.strip())
    if not normalized:
        return []

    ascii_tokens = [token.lower() for token in ASCII_TOKEN_RE.findall(normalized)]
    chinese_chars = [char for char in normalized if CHINESE_RE.fullmatch(char)]

    char_bigrams = [
        "".join(chinese_chars[idx : idx + 2])
        for idx in range(len(chinese_chars) - 1)
    ]
    char_trigrams = [
        "".join(chinese_chars[idx : idx + 3])
        for idx in range(len(chinese_chars) - 2)
    ]

    words: list[str] = []
    if jieba is not None:
        words = [
            token.strip().lower()
            for token in jieba.lcut(normalized)
            if token.strip() and not token.isspace()
        ]

    tokens = ascii_tokens + words + chinese_chars + char_bigrams + char_trigrams
    return tokens if tokens else [normalized.lower()]
