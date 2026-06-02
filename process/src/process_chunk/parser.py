from __future__ import annotations
"""
Markdown parser for product manuals.

This module turns markdown files into a structured list of sections and elements
that the chunk builder can reason about. The parser preserves source line spans,
image references, and enough markdown structure to later rebuild chunks without
falling back to raw text-only processing.
"""

import re
from pathlib import Path

from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode

from .models import Element, Section
from .tokenization import TokenCounter
from .utils import normalize_text


IMAGE_LINE_RE = re.compile(r"!\[[^\]]*\]\((?P<src>[^)]+)\)")
HEADING_TAG_RE = re.compile(r"^h([1-6])$")
LIST_LINE_RE = re.compile(r"^(?P<indent>\s*)(?P<marker>(?:[-+*])|(?:\d+[.)]))\s+")
CODE_FENCE_RE = re.compile(r"^(```+|~~~+)")
SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?。！？;；])\s+")


def _markdown_parser() -> MarkdownIt:
    """Return the markdown-it parser with table support enabled."""
    return MarkdownIt("commonmark").enable("table")


def _node_line_span(node: SyntaxTreeNode) -> tuple[int, int]:
    """
    Recover the source line span for an AST node.

    Some container nodes do not carry a direct `map`, so the span has to be
    inferred from the range covered by their children.
    """
    if node.map:
        return int(node.map[0]), int(node.map[1])
    starts: list[int] = []
    ends: list[int] = []
    for child in node.children or []:
        start, end = _node_line_span(child)
        starts.append(start)
        ends.append(end)
    if starts:
        return min(starts), max(ends)
    return 0, 0


def _slice_lines(lines: list[str], start: int, end: int) -> str:
    """Slice original source lines defensively to rebuild raw markdown."""
    if start < 0:
        start = 0
    if end < start:
        end = start
    return "\n".join(lines[start:end]).strip()


def _extract_image_paths(markdown: str, *, image_dir: Path) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """
    Extract both relative and absolute image paths from markdown.

    The builder stores the short name for manifests and the resolved absolute
    path for multimodal embedding calls later in the pipeline.
    """
    rel_paths: list[str] = []
    abs_paths: list[str] = []
    seen: set[str] = set()
    for match in IMAGE_LINE_RE.finditer(markdown):
        raw = match.group("src").strip()
        if not raw:
            continue
        name = Path(raw).name
        if not name or name in seen:
            continue
        seen.add(name)
        rel_paths.append(name)
        abs_paths.append(str((image_dir / name).resolve()))
    return tuple(rel_paths), tuple(abs_paths)


def estimate_markdown_tokens(
    markdown: str,
    *,
    token_counter: TokenCounter,
    image_token_cost: int,
) -> int:
    """
    Estimate markdown cost including a fixed surcharge for images.

    Images have no textual token length, but they still consume model budget in
    later multimodal stages, so the parser carries that cost into chunk sizing.
    """
    value = markdown.strip()
    if not value:
        return 0
    image_count = len(IMAGE_LINE_RE.findall(value))
    return token_counter.count(value) + image_count * image_token_cost


def _flatten_inline_text(node: SyntaxTreeNode) -> str:
    """Collapse inline AST nodes into plain text while preserving line breaks."""
    parts: list[str] = []
    for child in node.children or []:
        if child.type in {"text", "code_inline"}:
            if child.content:
                parts.append(child.content)
            continue
        if child.type in {"softbreak", "hardbreak"}:
            parts.append("\n")
            continue
        if child.type == "image":
            # Image alt text is often the only textual clue available once the
            # markdown image tag itself is removed from retrieval-oriented text.
            alt = _flatten_inline_text(child).strip()
            if alt:
                parts.append(alt)
            continue
        value = _flatten_inline_text(child)
        if value:
            parts.append(value)
    return "".join(parts)


def _render_list(node: SyntaxTreeNode, *, depth: int = 0) -> str:
    """Render nested markdown lists back into text while preserving indentation."""
    lines: list[str] = []
    ordered = node.type == "ordered_list"
    for index, child in enumerate(node.children or [], start=1):
        if child.type != "list_item":
            continue
        marker = f"{index}." if ordered else "-"
        lines.extend(_render_list_item(child, marker=marker, depth=depth))
    return "\n".join(lines).strip()


def _render_list_item(node: SyntaxTreeNode, *, marker: str, depth: int) -> list[str]:
    """
    Render one list item and align wrapped lines with the item body.

    The continuation indent keeps the visual structure readable after the AST has
    been flattened back into plain markdown-like text.
    """
    lines: list[str] = []
    prefix = "  " * depth + f"{marker} "
    continuation = "  " * depth + " " * (len(marker) + 1)
    first_line_written = False
    for child in node.children or []:
        if child.type in {"bullet_list", "ordered_list"}:
            nested = _render_list(child, depth=depth + 1)
            if nested:
                lines.extend(nested.splitlines())
            continue
        text = _render_node_text(child)
        if not text:
            continue
        for raw_line in text.splitlines():
            line = raw_line.rstrip()
            if not line:
                continue
            if not first_line_written:
                lines.append(f"{prefix}{line}")
                first_line_written = True
            else:
                lines.append(f"{continuation}{line}")
    return lines


def _render_table(node: SyntaxTreeNode) -> str:
    """
    Rebuild a markdown table from the parsed tree.

    Tables are normalized into a regular pipe-delimited layout so later splitting
    can reason about the header separately from the body rows.
    """
    rows: list[list[str]] = []
    for group in node.children or []:
        if group.type not in {"thead", "tbody"}:
            continue
        for row in group.children or []:
            if row.type != "tr":
                continue
            cells: list[str] = []
            for cell in row.children or []:
                cells.append(normalize_text(_render_node_text(cell)))
            rows.append(cells)

    if not rows:
        return ""

    max_cols = max(len(row) for row in rows)
    padded_rows = [row + [""] * (max_cols - len(row)) for row in rows]
    lines = ["| " + " | ".join(row) + " |" for row in padded_rows]
    if len(lines) >= 1:
        lines.insert(1, "| " + " | ".join("---" for _ in range(max_cols)) + " |")
    return "\n".join(lines).strip()


def _render_node_text(node: SyntaxTreeNode) -> str:
    """
    Convert an AST node back into normalized text or markdown-like text.

    This renderer intentionally keeps code fences and tables in structured form,
    because later chunk splitting behaves much better on those formats than on a
    fully flattened text blob.
    """
    if node.type == "inline":
        return normalize_text(_flatten_inline_text(node))
    if node.type in {"paragraph", "heading"}:
        return normalize_text(
            " ".join(part for child in node.children or [] if (part := _render_node_text(child)))
        )
    if node.type in {"bullet_list", "ordered_list"}:
        return _render_list(node)
    if node.type == "list_item":
        return "\n".join(_render_list_item(node, marker="-", depth=0)).strip()
    if node.type == "fence":
        info = node.info.strip()
        body = node.content.rstrip("\n")
        return f"```{info}\n{body}\n```".strip() if info else f"```\n{body}\n```".strip()
    if node.type == "code_block":
        body = node.content.rstrip("\n")
        return f"```\n{body}\n```".strip()
    if node.type == "table":
        return _render_table(node)
    parts: list[str] = []
    for child in node.children or []:
        value = _render_node_text(child)
        if value:
            parts.append(value)
    return normalize_text("\n".join(parts))


def _element_kind(node: SyntaxTreeNode, markdown: str) -> str:
    """Map markdown-it node types to the simplified element taxonomy used downstream."""
    if node.type == "heading":
        return "heading"
    if node.type in {"bullet_list", "ordered_list"}:
        return "list"
    if node.type == "table":
        return "table"
    if node.type in {"fence", "code_block"}:
        return "code"
    if IMAGE_LINE_RE.search(markdown):
        return "image"
    if node.type == "paragraph":
        return "paragraph"
    return "block"


def _make_element(
    node: SyntaxTreeNode,
    *,
    order: int,
    lines: list[str],
    token_counter: TokenCounter,
    image_dir: Path,
    image_token_cost: int,
) -> Element | None:
    """
    Convert one AST node into the normalized `Element` model.

    Both raw markdown and rendered text are retained so later stages can choose
    between structure-preserving reconstruction and retrieval-friendly text.
    """
    line_start, line_end = _node_line_span(node)
    markdown = _slice_lines(lines, line_start, line_end)
    if not markdown and node.type != "heading":
        return None
    text = _render_node_text(node)
    if not text and not markdown:
        return None
    image_paths, image_abs_paths = _extract_image_paths(markdown, image_dir=image_dir)
    heading_level = None
    heading_text = ""
    if node.type == "heading":
        match = HEADING_TAG_RE.match(node.tag or "")
        if match:
            heading_level = int(match.group(1))
        heading_text = normalize_text(text)
    return Element(
        kind=_element_kind(node, markdown),
        order=order,
        text=text,
        markdown=markdown or text,
        token_count=estimate_markdown_tokens(
            markdown or text,
            token_counter=token_counter,
            image_token_cost=image_token_cost,
        ),
        line_start=line_start,
        line_end=line_end,
        heading_level=heading_level,
        heading_text=heading_text,
        image_paths=image_paths,
        image_abs_paths=image_abs_paths,
    )


def _split_sentences(text: str) -> list[str]:
    """Split text by broad sentence boundaries used in both Chinese and English manuals."""
    value = normalize_text(text)
    if not value:
        return []
    parts = [item.strip() for item in SENTENCE_BOUNDARY_RE.split(value) if item.strip()]
    return parts or [value]


def split_paragraph_text(
    text: str,
    *,
    token_counter: TokenCounter,
    max_tokens: int,
    overlap_tokens: int,
) -> list[str]:
    """
    Split a paragraph at sentence boundaries before falling back to raw overlap splitting.

    This preserves local semantic coherence better than a blind token window and is
    especially important for step-by-step instructions in product manuals.
    """
    value = normalize_text(text)
    if not value:
        return []
    if token_counter.count(value) <= max_tokens:
        return [value]
    sentences = _split_sentences(value)
    parts: list[str] = []
    current: list[str] = []
    current_tokens = 0
    for sentence in sentences:
        sentence_tokens = token_counter.count(sentence)
        if sentence_tokens > max_tokens:
            if current:
                parts.append(" ".join(current).strip())
                current = []
                current_tokens = 0
            parts.extend(
                token_counter.split_with_overlap(
                    sentence,
                    max_tokens=max_tokens,
                    overlap_tokens=overlap_tokens,
                )
            )
            continue
        if current and current_tokens + sentence_tokens > max_tokens:
            parts.append(" ".join(current).strip())
            current = [sentence]
            current_tokens = sentence_tokens
            continue
        current.append(sentence)
        current_tokens += sentence_tokens
    if current:
        parts.append(" ".join(current).strip())
    return [part for part in parts if part]


def split_list_markdown(
    markdown: str,
    *,
    token_counter: TokenCounter,
    max_tokens: int,
    overlap_tokens: int,
) -> list[str]:
    """
    Split a list while trying to preserve item boundaries.

    Breaking in the middle of a bullet item often destroys the local instruction
    context, so the algorithm first segments into items and only then packs them.
    """
    lines = [line.rstrip() for line in markdown.splitlines()]
    items: list[str] = []
    current: list[str] = []
    for line in lines:
        if LIST_LINE_RE.match(line):
            if current:
                items.append("\n".join(current).strip())
            current = [line]
            continue
        if current:
            current.append(line)
        elif line.strip():
            current = [line]
    if current:
        items.append("\n".join(current).strip())
    if not items:
        return token_counter.split_with_overlap(markdown, max_tokens=max_tokens, overlap_tokens=overlap_tokens)

    parts: list[str] = []
    current_lines: list[str] = []
    current_tokens = 0
    separator_cost = token_counter.count("\n")
    for item in items:
        item_tokens = token_counter.count(item)
        if item_tokens > max_tokens:
            if current_lines:
                parts.append("\n".join(current_lines).strip())
                current_lines = []
                current_tokens = 0
            parts.extend(token_counter.split_with_overlap(item, max_tokens=max_tokens, overlap_tokens=overlap_tokens))
            continue
        projected = current_tokens + item_tokens if not current_lines else current_tokens + separator_cost + item_tokens
        if current_lines and projected > max_tokens:
            parts.append("\n".join(current_lines).strip())
            current_lines = [item]
            current_tokens = item_tokens
            continue
        current_lines.append(item)
        current_tokens = projected
    if current_lines:
        parts.append("\n".join(current_lines).strip())
    return [part for part in parts if part]


def split_table_markdown(
    markdown: str,
    *,
    token_counter: TokenCounter,
    max_tokens: int,
    overlap_tokens: int,
) -> list[str]:
    """
    Split a table by rows while repeating the header on every fragment.

    Repeating the header is important because a table row without column labels is
    almost useless once it becomes an independent retrieval unit.
    """
    lines = [line.rstrip() for line in markdown.splitlines() if line.strip()]
    if len(lines) <= 2:
        return [markdown.strip()] if markdown.strip() else []
    header = lines[0]
    separator = lines[1]
    rows = lines[2:]
    parts: list[str] = []
    current_rows: list[str] = []
    current_tokens = token_counter.count(f"{header}\n{separator}")
    separator_cost = token_counter.count("\n")
    for row in rows:
        row_tokens = token_counter.count(row)
        if row_tokens > max_tokens:
            if current_rows:
                parts.append("\n".join([header, separator, *current_rows]).strip())
                current_rows = []
                current_tokens = token_counter.count(f"{header}\n{separator}")
            parts.extend(
                token_counter.split_with_overlap(
                    "\n".join([header, separator, row]),
                    max_tokens=max_tokens,
                    overlap_tokens=overlap_tokens,
                )
            )
            continue
        projected = current_tokens + row_tokens if not current_rows else current_tokens + separator_cost + row_tokens
        if current_rows and projected > max_tokens:
            parts.append("\n".join([header, separator, *current_rows]).strip())
            current_rows = [row]
            current_tokens = token_counter.count(f"{header}\n{separator}") + row_tokens
            continue
        current_rows.append(row)
        current_tokens = projected
    if current_rows:
        parts.append("\n".join([header, separator, *current_rows]).strip())
    return [part for part in parts if part]


def split_code_markdown(
    markdown: str,
    *,
    token_counter: TokenCounter,
    max_tokens: int,
    overlap_tokens: int,
) -> list[str]:
    """
    Split fenced code while preserving the fence on every fragment.

    This keeps the output syntactically recognizable and prevents later prompt
    stages from seeing orphaned code bodies without opening or closing fences.
    """
    value = markdown.strip()
    if not value:
        return []
    lines = value.splitlines()
    if len(lines) < 2 or not CODE_FENCE_RE.match(lines[0]):
        return token_counter.split_with_overlap(value, max_tokens=max_tokens, overlap_tokens=overlap_tokens)
    open_fence = lines[0]
    close_fence = lines[-1] if CODE_FENCE_RE.match(lines[-1]) else open_fence[:3]
    body_lines = lines[1:-1] if CODE_FENCE_RE.match(lines[-1]) else lines[1:]
    body = "\n".join(body_lines).strip("\n")
    pieces = token_counter.split_with_overlap(
        body,
        max_tokens=max(1, max_tokens - token_counter.count(f"{open_fence}\n{close_fence}")),
        overlap_tokens=overlap_tokens,
    )
    return ["\n".join([open_fence, piece, close_fence]).strip() for piece in pieces if piece.strip()]


def split_element_markdown(
    element: Element,
    *,
    token_counter: TokenCounter,
    max_tokens: int,
    overlap_tokens: int,
    image_token_cost: int,
) -> list[str]:
    """
    Split an oversized element with the best strategy for its type.

    The dispatcher prefers structure-aware splitting first and only falls back to
    generic token windows when the element type does not offer a better boundary.
    """
    value = element.markdown.strip()
    if not value:
        return []
    if estimate_markdown_tokens(value, token_counter=token_counter, image_token_cost=image_token_cost) <= max_tokens:
        return [value]
    if element.kind == "paragraph":
        return split_paragraph_text(
            element.text or value,
            token_counter=token_counter,
            max_tokens=max_tokens,
            overlap_tokens=overlap_tokens,
        )
    if element.kind == "list":
        return split_list_markdown(value, token_counter=token_counter, max_tokens=max_tokens, overlap_tokens=overlap_tokens)
    if element.kind == "table":
        return split_table_markdown(value, token_counter=token_counter, max_tokens=max_tokens, overlap_tokens=overlap_tokens)
    if element.kind == "code":
        return split_code_markdown(value, token_counter=token_counter, max_tokens=max_tokens, overlap_tokens=overlap_tokens)
    return token_counter.split_with_overlap(value, max_tokens=max_tokens, overlap_tokens=overlap_tokens)


def parse_markdown_sections(
    path: Path,
    *,
    token_counter: TokenCounter,
    image_dir: Path,
    image_token_cost: int,
) -> list[Section]:
    """
    Parse a markdown manual into hierarchical sections.

    The section stack mirrors heading nesting. A heading starts a new section,
    while non-heading nodes are appended to the most recent open section.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    root = SyntaxTreeNode(_markdown_parser().parse(text))

    sections: list[Section] = []
    preamble = Section(
        order=0,
        heading_level=0,
        heading_text="",
        header_path=(),
        line_start=0,
        line_end=len(lines),
    )
    sections.append(preamble)
    stack: list[Section] = []
    order = 0

    for child in root.children or []:
        if child.type == "heading":
            element = _make_element(
                child,
                order=order,
                lines=lines,
                token_counter=token_counter,
                image_dir=image_dir,
                image_token_cost=image_token_cost,
            )
            order += 1
            if element is None:
                continue
            level = element.heading_level or 1

            # Pop until the stack parent is shallower than the new heading.
            while stack and stack[-1].heading_level >= level:
                stack.pop()

            header_path = tuple(section.heading_text for section in stack if section.heading_text) + (
                element.heading_text,
            )
            section = Section(
                order=len(sections),
                heading_level=level,
                heading_text=element.heading_text,
                header_path=header_path,
                line_start=element.line_start,
                line_end=len(lines),
                elements=[element],
            )
            if len(sections) == 1 and not sections[0].elements:
                sections[0].line_end = element.line_start
            sections.append(section)
            stack.append(section)
            continue

        element = _make_element(
            child,
            order=order,
            lines=lines,
            token_counter=token_counter,
            image_dir=image_dir,
            image_token_cost=image_token_cost,
        )
        order += 1
        if element is None:
            continue
        sections[-1].elements.append(element)
        sections[-1].line_end = max(sections[-1].line_end, element.line_end)

    if sections:
        sections[0].line_end = max(
            sections[0].line_end,
            max((element.line_end for element in sections[0].elements), default=0),
        )
    return [section for section in sections if section.elements]
