from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Element:
    """
    A normalized markdown element produced by the parser.

    Both `text` and `markdown` are preserved because later stages need clean text
    for retrieval but still need structure-aware markdown for chunk reconstruction.
    """
    kind: str
    order: int
    text: str
    markdown: str
    token_count: int
    line_start: int
    line_end: int
    heading_level: int | None = None
    heading_text: str = ""
    image_paths: tuple[str, ...] = ()
    image_abs_paths: tuple[str, ...] = ()
    children: tuple["Element", ...] = ()


@dataclass(slots=True)
class Section:
    """A heading-scoped group of elements with its breadcrumb path attached."""
    order: int
    heading_level: int
    heading_text: str
    header_path: tuple[str, ...]
    line_start: int
    line_end: int
    elements: list[Element] = field(default_factory=list)
