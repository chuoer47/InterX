from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class TokenCounter:
    """
    Token counting helper with a graceful fallback when `tiktoken` is unavailable.

    Exact token counts matter for chunk sizing, but a character heuristic keeps the
    pipeline operational in lightweight environments where tokenizer packages are
    not installed.
    """
    encoding_name: str
    _encoding: object | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self._encoding = None
        try:
            import tiktoken

            self._encoding = tiktoken.get_encoding(self.encoding_name)
        except Exception:
            self._encoding = None

    def count(self, text: str) -> int:
        """Count tokens using `tiktoken` when available, else use a rough character proxy."""
        if not text:
            return 0
        if self._encoding is not None:
            return len(self._encoding.encode(text))
        return max(1, len(text) // 2)

    def split_with_overlap(
        self,
        text: str,
        *,
        max_tokens: int,
        overlap_tokens: int,
    ) -> list[str]:
        """
        Split text into overlapping windows.

        Overlap reduces the chance that an answer-critical phrase lands exactly on
        the boundary between two chunks and disappears from both retrieval results.
        """
        value = text.strip()
        if not value:
            return []
        if max_tokens <= 0:
            return [value]
        overlap = max(0, min(overlap_tokens, max_tokens - 1))
        if self._encoding is not None:
            tokens = self._encoding.encode(value)
            if len(tokens) <= max_tokens:
                return [value]
            step = max(1, max_tokens - overlap)
            parts: list[str] = []
            for index in range(0, len(tokens), step):
                piece = self._encoding.decode(tokens[index : index + max_tokens]).strip()
                if piece:
                    parts.append(piece)
                if index + max_tokens >= len(tokens):
                    break
            return parts

        max_chars = max(1, max_tokens * 2)
        overlap_chars = overlap * 2
        if len(value) <= max_chars:
            return [value]
        step = max(1, max_chars - overlap_chars)
        parts: list[str] = []
        for index in range(0, len(value), step):
            piece = value[index : index + max_chars].strip()
            if piece:
                parts.append(piece)
            if index + max_chars >= len(value):
                break
        return parts
