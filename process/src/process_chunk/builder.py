from __future__ import annotations
"""
Chunk builder for product manuals.

Builds three levels of chunks from parsed markdown manuals:
- Small chunks: precise facts, definitions, single steps (~220 tokens)
- Mid chunks: operational procedures, multi-step guides (~520 tokens)
- Big chunks: background context, full sections (~900 tokens)

The builder uses a greedy packing algorithm that respects token limits
while preserving semantic boundaries (paragraphs, sections).
"""

from pathlib import Path
from typing import Any

from .config import ChunkScheme
from .models import Element, Section
from .parser import estimate_markdown_tokens, split_element_markdown
from .tokenization import TokenCounter
from .utils import content_hash


def _ordered_unique(values: list[str]) -> list[str]:
    """Remove duplicates from list while preserving insertion order."""
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        item = str(value).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _separator_cost(token_counter: TokenCounter) -> int:
    """Return token count of a paragraph separator (double newline)."""
    return token_counter.count("\n\n")


def _render_header_path(header_path: tuple[str, ...]) -> str:
    """Format a header path tuple as a breadcrumb string, e.g. 'A > B > C'."""
    return " > ".join(item for item in header_path if item.strip())


def _big_prefix(doc_name: str, header_path: tuple[str, ...]) -> str:
    """Build the retrieval prefix for a big chunk."""
    lines = [f"手册：{doc_name}"]
    if header_path:
        lines.append(f"章节：{_render_header_path(header_path)}")
    return "\n".join(lines).strip()


def _mid_prefix(doc_name: str, big: dict[str, Any], header_path: tuple[str, ...]) -> str:
    """Build the retrieval prefix for a mid chunk including its parent big chunk."""
    lines = [f"手册：{doc_name}"]
    if header_path:
        lines.append(f"章节：{_render_header_path(header_path)}")
    lines.append(f"大块：{big['chunk_id']}")
    return "\n".join(lines).strip()


def _small_prefix(
    doc_name: str,
    big: dict[str, Any],
    mid: dict[str, Any],
    header_path: tuple[str, ...],
) -> str:
    """Build the retrieval prefix for a small chunk including its parent chain."""
    lines = [f"手册：{doc_name}"]
    if header_path:
        lines.append(f"章节：{_render_header_path(header_path)}")
    lines.append(f"大块：{big['chunk_id']}")
    lines.append(f"中块：{mid['chunk_id']}")
    return "\n".join(lines).strip()


def _element_effective_markdown(element: Element, *, include_heading: bool) -> str:
    """
    Return the markdown that should participate in chunk construction.

    Headings are only injected into the first chunk of a section so later chunks
    do not keep repeating the same title and waste the token budget.
    """
    if include_heading and element.kind == "heading":
        return element.markdown.strip()
    if element.kind == "heading":
        return ""
    return element.markdown.strip()


def _element_effective_text(element: Element, *, include_heading: bool) -> str:
    """
    Return the plain-text form used for retrieval and diagnostics.

    The builder keeps markdown for reconstruction, but retrieval text should stay
    as clean as possible to avoid ranking noise from markdown syntax.
    """
    if include_heading and element.kind == "heading":
        return element.text.strip()
    if element.kind == "heading":
        return ""
    return element.text.strip()


def _entry_from_element(
    *,
    element: Element,
    include_heading: bool,
    token_counter: TokenCounter,
    image_token_cost: int,
) -> dict[str, Any] | None:
    """
    Normalize an element into a chunk-builder entry.

    The builder keeps both markdown and plain text because markdown is used to
    reconstruct the final chunk content, while plain text is used for retrieval
    fields and for downstream embedding payload construction.
    """
    markdown = _element_effective_markdown(element, include_heading=include_heading)
    if not markdown:
        return None
    return {
        "element": element,
        "markdown": markdown,
        "text": _element_effective_text(element, include_heading=include_heading),
        "token_count": estimate_markdown_tokens(
            markdown,
            token_counter=token_counter,
            image_token_cost=image_token_cost,
        ),
        "image_paths": list(element.image_paths),
        "image_abs_paths": list(element.image_abs_paths),
        "line_start": element.line_start,
        "line_end": element.line_end,
    }


def _pack_elements(
    *,
    elements: list[Element],
    token_counter: TokenCounter,
    target_tokens: int,
    max_tokens: int,
    include_heading: bool,
    image_token_cost: int,
) -> list[list[Element]]:
    """
    Greedily pack raw elements into coarse groups.

    This is the first pass of the chunking algorithm. It aims for the target size,
    but it always respects the hard max limit. Images are treated specially and are
    allowed to stay with their surrounding text when possible, because separating an
    image from its explanation tends to hurt downstream answer quality.
    """
    groups: list[list[Element]] = []
    current: list[Element] = []
    current_tokens = 0
    separator_cost = _separator_cost(token_counter)

    for element in elements:
        element_markdown = _element_effective_markdown(element, include_heading=include_heading)
        element_tokens = (
            estimate_markdown_tokens(
                element_markdown,
                token_counter=token_counter,
                image_token_cost=image_token_cost,
            )
            if element_markdown
            else 0
        )

        if not current:
            current = [element]
            current_tokens = element_tokens
            continue

        should_flush = False
        if current_tokens >= target_tokens and element.kind != "image":
            should_flush = True
        elif current_tokens + separator_cost + element_tokens > max_tokens and element.kind != "image":
            should_flush = True

        if should_flush:
            groups.append(current)
            current = [element]
            current_tokens = element_tokens
            continue

        current.append(element)
        current_tokens += element_tokens

    if current:
        groups.append(current)
    return groups


def _split_oversized_group(
    *,
    elements: list[Element],
    token_counter: TokenCounter,
    max_tokens: int,
    overlap_tokens: int,
    image_token_cost: int,
    include_heading: bool = False,
) -> list[list[dict[str, Any]]]:
    """
    Split a coarse group when it still exceeds the hard token limit.

    The first pass preserves semantic boundaries as much as possible. When a group
    is still too large, the second pass breaks individual elements into smaller
    pieces with overlap so a procedure can continue across chunk boundaries without
    losing the sentence or step that bridges both sides.
    """
    result: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_tokens = 0
    separator_cost = _separator_cost(token_counter)

    for element in elements:
        element_value = _element_effective_markdown(element, include_heading=include_heading)
        if not element_value:
            continue

        if include_heading and element.kind == "heading":
            parts = [element_value]
        else:
            parts = split_element_markdown(
                element,
                token_counter=token_counter,
                max_tokens=max_tokens,
                overlap_tokens=overlap_tokens,
                image_token_cost=image_token_cost,
            )

        for index, part in enumerate(parts):
            row = {
                "element": element,
                "markdown": part.strip(),
                "text": _element_effective_text(element, include_heading=include_heading)
                if len(parts) == 1
                else part.strip(),
                "token_count": estimate_markdown_tokens(
                    part,
                    token_counter=token_counter,
                    image_token_cost=image_token_cost,
                ),
                "image_paths": list(element.image_paths),
                "image_abs_paths": list(element.image_abs_paths),
                "line_start": element.line_start,
                "line_end": element.line_end,
                "part_index": index,
                "part_count": len(parts),
            }
            if (
                current
                and current_tokens + separator_cost + row["token_count"] > max_tokens
                and row["token_count"] <= max_tokens
            ):
                result.append(current)
                current = []
                current_tokens = 0

            addition = row["token_count"] if not current else separator_cost + row["token_count"]
            current.append(row)
            current_tokens += addition

            if current_tokens >= max_tokens:
                result.append(current)
                current = []
                current_tokens = 0

    if current:
        result.append(current)
    return result


def _pack_entry_groups(
    *,
    entries: list[dict[str, Any]],
    token_counter: TokenCounter,
    target_tokens: int,
    max_tokens: int,
    max_images: int | None = None,
) -> list[list[dict[str, Any]]]:
    """
    Greedily pack already-normalized entries.

    This helper is reused by mid and small chunk construction after entries may
    have been pre-split. At this stage the hard problem is not semantic parsing
    anymore, but balancing token budget and image count constraints.
    """
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_tokens = 0
    current_images = 0
    separator_cost = _separator_cost(token_counter)

    for entry in entries:
        entry_tokens = int(entry["token_count"])
        entry_images = len(entry["image_paths"])

        if current:
            if max_images is not None and current_images + entry_images > max_images:
                groups.append(current)
                current = []
                current_tokens = 0
                current_images = 0
            elif current_tokens >= target_tokens and entry["element"].kind != "image":
                groups.append(current)
                current = []
                current_tokens = 0
                current_images = 0
            elif current_tokens + separator_cost + entry_tokens > max_tokens:
                groups.append(current)
                current = []
                current_tokens = 0
                current_images = 0

        current.append(entry)
        current_tokens += entry_tokens if len(current) == 1 else separator_cost + entry_tokens
        current_images += entry_images

    if current:
        groups.append(current)
    return groups


def _entries_to_markdown(entries: list[dict[str, Any]]) -> str:
    """Reconstruct chunk markdown from normalized entry fragments."""
    return "\n\n".join(item["markdown"].strip() for item in entries if item["markdown"].strip()).strip()


def _entries_to_text(entries: list[dict[str, Any]]) -> str:
    """Reconstruct clean text used by retrieval and diagnostics."""
    return "\n\n".join(item["text"].strip() for item in entries if item["text"].strip()).strip()


def _entries_image_paths(entries: list[dict[str, Any]], field: str) -> list[str]:
    """Collect image references while preserving original order."""
    values: list[str] = []
    for entry in entries:
        values.extend(entry[field])
    return _ordered_unique(values)


def _entries_span(entries: list[dict[str, Any]]) -> dict[str, int]:
    """Return the line span covered by a chunk for traceability back to the source file."""
    starts = [int(entry["line_start"]) for entry in entries]
    ends = [int(entry["line_end"]) for entry in entries]
    return {"start_line": min(starts) + 1, "end_line": max(ends)}


def _entries_element_kinds(entries: list[dict[str, Any]]) -> list[str]:
    """Expose the element mix inside a chunk for inspection and debugging."""
    return _ordered_unique([entry["element"].kind for entry in entries])


def _section_content_elements(section: Section) -> list[Element]:
    """Drop the leading heading element because it is handled separately during packing."""
    if section.elements and section.elements[0].kind == "heading":
        return section.elements[1:]
    return section.elements[:]


def _make_big_entries(
    *,
    section: Section,
    token_counter: TokenCounter,
    scheme: ChunkScheme,
    image_token_cost: int,
) -> list[list[dict[str, Any]]]:
    """
    Turn a parsed section into one or more big-chunk entry groups.

    The first big chunk of a section inherits the heading so retrieval can keep
    the section title as context. Later chunks within the same section omit the
    repeated heading to spend more room on body content.
    """
    heading_element = section.elements[0] if section.elements and section.elements[0].kind == "heading" else None
    content_elements = _section_content_elements(section)
    if not content_elements:
        if heading_element is None:
            return []
        heading_entry = _entry_from_element(
            element=heading_element,
            include_heading=True,
            token_counter=token_counter,
            image_token_cost=image_token_cost,
        )
        return [[heading_entry]] if heading_entry is not None else []

    grouped = _pack_elements(
        elements=content_elements,
        token_counter=token_counter,
        target_tokens=scheme.big_target_tokens,
        max_tokens=scheme.big_max_tokens,
        include_heading=False,
        image_token_cost=image_token_cost,
    )

    entries_groups: list[list[dict[str, Any]]] = []
    for group_index, group in enumerate(grouped):
        include_heading = heading_element is not None and group_index == 0
        group_elements = [heading_element, *group] if include_heading and heading_element is not None else group
        group_markdown = "\n\n".join(
            _element_effective_markdown(element, include_heading=include_heading)
            for element in group_elements
            if _element_effective_markdown(element, include_heading=include_heading)
        ).strip()

        if estimate_markdown_tokens(
            group_markdown,
            token_counter=token_counter,
            image_token_cost=image_token_cost,
        ) <= scheme.big_max_tokens:
            entry_group = [
                _entry_from_element(
                    element=element,
                    include_heading=include_heading,
                    token_counter=token_counter,
                    image_token_cost=image_token_cost,
                )
                for element in group_elements
            ]
            entries_groups.append([entry for entry in entry_group if entry is not None])
            continue

        entries_groups.extend(
            _split_oversized_group(
                elements=group_elements,
                token_counter=token_counter,
                max_tokens=scheme.big_max_tokens,
                overlap_tokens=scheme.small_overlap_tokens,
                image_token_cost=image_token_cost,
                include_heading=include_heading,
            )
        )
    return [group for group in entries_groups if group]


def _big_chunk_payload(
    *,
    entries: list[dict[str, Any]],
    scheme: ChunkScheme,
    doc_id: str,
    doc_name: str,
    source_path: Path,
    header_path: tuple[str, ...],
    chunk_index: int,
) -> dict[str, Any]:
    """Create the final payload for a big chunk."""
    content = _entries_to_markdown(entries)
    text = _entries_to_text(entries)
    prefix = _big_prefix(doc_name, header_path)
    image_paths = _entries_image_paths(entries, "image_paths")
    image_abs_paths = _entries_image_paths(entries, "image_abs_paths")
    return {
        "chunk_id": f"{doc_id}_big_{chunk_index:04d}",
        "chunk_type": "big",
        "scheme": scheme.name,
        "doc_id": doc_id,
        "doc_name": doc_name,
        "product_name": doc_name.replace("手册", ""),
        "source_path": str(source_path),
        "text": text,
        "content": content,
        # Prefix fields are embedded into retrieval text so dense and sparse search
        # can match both the body content and the structural location of the chunk.
        "retrieval_text": f"{prefix}\n{text}".strip() if text else prefix,
        "image_paths": image_paths,
        "image_abs_paths": image_abs_paths,
        "token_count": sum(int(entry["token_count"]) for entry in entries),
        "image_count": len(image_paths),
        "source_span": _entries_span(entries),
        # The hash lets later stages skip unchanged chunks during rebuilds.
        "content_hash": content_hash(content),
        "header_path": list(header_path),
        "section_title": header_path[-1] if header_path else "",
        "element_kinds": _entries_element_kinds(entries),
    }


def _make_mid_entries(
    *,
    big_entries: list[dict[str, Any]],
    token_counter: TokenCounter,
    scheme: ChunkScheme,
    image_token_cost: int,
) -> list[list[dict[str, Any]]]:
    """
    Build mid-level entry groups from a big chunk.

    Mid chunks start from big-chunk entries instead of raw markdown elements so the
    hierarchical relationship remains stable: big -> mid -> small all point back to
    the same original element lineage.
    """
    split_entries: list[dict[str, Any]] = []
    for entry in big_entries:
        element = entry["element"]
        part_source = entry["markdown"].strip()
        if not part_source:
            continue
        if estimate_markdown_tokens(
            part_source,
            token_counter=token_counter,
            image_token_cost=image_token_cost,
        ) <= scheme.mid_max_tokens:
            split_entries.append(entry)
            continue
        parts = split_element_markdown(
            element,
            token_counter=token_counter,
            max_tokens=scheme.mid_max_tokens,
            overlap_tokens=scheme.small_overlap_tokens,
            image_token_cost=image_token_cost,
        )
        for index, part in enumerate(parts):
            split_entries.append(
                {
                    **entry,
                    "markdown": part.strip(),
                    "text": part.strip(),
                    "token_count": estimate_markdown_tokens(
                        part,
                        token_counter=token_counter,
                        image_token_cost=image_token_cost,
                    ),
                    "part_index": index,
                    "part_count": len(parts),
                }
            )
    return _pack_entry_groups(
        entries=split_entries,
        token_counter=token_counter,
        target_tokens=scheme.mid_target_tokens,
        max_tokens=scheme.mid_max_tokens,
    )


def _mid_chunk_payload(
    *,
    big: dict[str, Any],
    entries: list[dict[str, Any]],
    scheme: ChunkScheme,
    header_path: tuple[str, ...],
    mid_index_in_big: int,
) -> dict[str, Any]:
    """Create the final payload for a mid chunk."""
    content = _entries_to_markdown(entries)
    text = _entries_to_text(entries)
    prefix = _mid_prefix(big["doc_name"], big, header_path)
    image_paths = _entries_image_paths(entries, "image_paths")
    image_abs_paths = _entries_image_paths(entries, "image_abs_paths")
    big_suffix = big["chunk_id"].rsplit("_", 1)[-1]
    return {
        "chunk_id": f"{big['doc_id']}_mid_{big_suffix}_{mid_index_in_big:04d}",
        "chunk_type": "mid",
        "scheme": scheme.name,
        "doc_id": big["doc_id"],
        "doc_name": big["doc_name"],
        "product_name": big["product_name"],
        "source_path": big["source_path"],
        "big_chunk_id": big["chunk_id"],
        "mid_index_in_big": mid_index_in_big,
        "text": text,
        "content": content,
        "retrieval_text": f"{prefix}\n{text}".strip() if text else prefix,
        "image_paths": image_paths,
        "image_abs_paths": image_abs_paths,
        "token_count": sum(int(entry["token_count"]) for entry in entries),
        "image_count": len(image_paths),
        "source_span": _entries_span(entries),
        "content_hash": content_hash(content),
        "header_path": list(header_path),
        "section_title": header_path[-1] if header_path else "",
        "element_kinds": _entries_element_kinds(entries),
    }


def _small_chunk_payloads(
    *,
    big: dict[str, Any],
    mid: dict[str, Any],
    entries: list[dict[str, Any]],
    token_counter: TokenCounter,
    scheme: ChunkScheme,
    header_path: tuple[str, ...],
    image_token_cost: int,
) -> list[dict[str, Any]]:
    """
    Build small chunks from a mid chunk.

    Small chunks are the primary retrieval unit, so this stage is the most strict
    about token size and image count. Oversized entries are split again to keep the
    final search unit concise and precise.
    """
    split_entries: list[dict[str, Any]] = []
    for entry in entries:
        parts = split_element_markdown(
            entry["element"],
            token_counter=token_counter,
            max_tokens=scheme.small_max_tokens,
            overlap_tokens=scheme.small_overlap_tokens,
            image_token_cost=image_token_cost,
        )
        if len(parts) <= 1:
            split_entries.append(entry)
            continue
        for index, part in enumerate(parts):
            split_entries.append(
                {
                    **entry,
                    "markdown": part.strip(),
                    "text": part.strip(),
                    "token_count": estimate_markdown_tokens(
                        part,
                        token_counter=token_counter,
                        image_token_cost=image_token_cost,
                    ),
                    "part_index": index,
                    "part_count": len(parts),
                }
            )

    groups = _pack_entry_groups(
        entries=split_entries,
        token_counter=token_counter,
        target_tokens=scheme.small_target_tokens,
        max_tokens=scheme.small_max_tokens,
        max_images=scheme.max_images_per_small,
    )
    prefix = _small_prefix(big["doc_name"], big, mid, header_path)
    rows: list[dict[str, Any]] = []
    mid_suffix = mid["chunk_id"].rsplit("_", 2)[-2:]
    mid_suffix_text = "_".join(mid_suffix)

    for index, group in enumerate(groups):
        content = _entries_to_markdown(group)
        text = _entries_to_text(group)
        image_paths = _entries_image_paths(group, "image_paths")
        image_abs_paths = _entries_image_paths(group, "image_abs_paths")
        retrieval_text = f"{prefix}\n{text}".strip() if text else prefix
        payload: dict[str, Any] = {"text": retrieval_text}

        # The multimodal embedding endpoint accepts a single image alongside text,
        # so the first image becomes the visual anchor for this small chunk.
        if image_abs_paths:
            payload["image"] = image_abs_paths[0]

        rows.append(
            {
                "chunk_id": f"{big['doc_id']}_small_{mid_suffix_text}_{index:04d}",
                "chunk_type": "small",
                "scheme": scheme.name,
                "doc_id": big["doc_id"],
                "doc_name": big["doc_name"],
                "product_name": big["product_name"],
                "source_path": big["source_path"],
                "big_chunk_id": big["chunk_id"],
                "mid_chunk_id": mid["chunk_id"],
                "mid_index_in_big": mid["mid_index_in_big"],
                "text": text,
                "content": content,
                "retrieval_text": retrieval_text,
                "image_paths": image_paths,
                "image_abs_paths": image_abs_paths,
                "embedding_payload": payload,
                "token_count": sum(int(entry["token_count"]) for entry in group),
                "image_count": len(image_paths),
                "source_span": _entries_span(group),
                "content_hash": content_hash(content),
                "header_path": list(header_path),
                "section_title": header_path[-1] if header_path else "",
                "element_kinds": _entries_element_kinds(group),
            }
        )
    return rows
