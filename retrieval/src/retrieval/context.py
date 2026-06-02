"""Prompt-context assembly helpers for retrieval results."""
from __future__ import annotations

from .types import BigHit, MidHit, SearchHit


def _format_hit_block(hit: SearchHit) -> str:
    """Format a small-chunk hit into a compact prompt block."""
    lines: list[str] = []
    lines.append(f"[{hit.doc_name}] {hit.section_title} (小块: {hit.chunk_id})")
    if hit.header_path:
        lines.append(f"  章节路径：{' > '.join(hit.header_path)}")
    lines.append(f"  来源：{hit.retrieval_source}")
    lines.append("  内容：")
    lines.append(hit.content)
    if hit.image_abs_paths:
        lines.append(f"  附图：{', '.join(hit.image_abs_paths)}")
    return "\n".join(lines)


def _format_mid_hit(hit: MidHit, *, include_images: bool) -> str:
    """Format a mid-level hit with its child small hits."""
    lines: list[str] = []
    lines.append(f"[{hit.doc_name}] {hit.section_title} (中块: {hit.chunk_id})")
    if hit.header_path:
        lines.append(f"  章节路径：{' > '.join(hit.header_path)}")
    lines.append("  内容：")
    lines.append(hit.content)
    if hit.image_abs_paths and include_images:
        lines.append(f"  附图：{', '.join(hit.image_abs_paths)}")
    if hit.small_hits:
        lines.append(f"  包含 {hit.small_count} 个小块:")
        for sh in hit.small_hits:
            lines.append(f"    - [{sh.rank}] {sh.section_title}: {sh.content[:80]}...")
    return "\n".join(lines)


def _format_big_hit(hit: BigHit, *, include_images: bool) -> str:
    """Format a big-level hit with its aggregated hierarchy counts."""
    lines: list[str] = []
    lines.append(f"[{hit.doc_name}] {hit.section_title} (大块: {hit.chunk_id})")
    if hit.header_path:
        lines.append(f"  章节路径：{' > '.join(hit.header_path)}")
    lines.append("  内容：")
    lines.append(hit.content)
    if hit.image_abs_paths and include_images:
        lines.append(f"  附图：{', '.join(hit.image_abs_paths)}")
    lines.append(f"  包含 {hit.mid_count} 个中块, {hit.small_count} 个小块")
    return "\n".join(lines)


def assemble_context(
    hits: list[SearchHit | MidHit | BigHit],
    *,
    level: str | None = None,
    max_tokens: int = 12000,
    include_images: bool = True,
) -> str:
    """
    Assemble ranked hits into a prompt-ready context string.

    The optional `level` argument is kept for backward compatibility with older
    callers; formatting is determined from the actual hit types at runtime.

    The function uses a rough character budget instead of exact tokenization to
    stay lightweight inside the answer pipeline while still keeping context size
    bounded.
    """
    char_budget = max_tokens * 3
    blocks: list[str] = []
    total_chars = 0

    for i, hit in enumerate(hits):
        if isinstance(hit, BigHit):
            block = _format_big_hit(hit, include_images=include_images)
        elif isinstance(hit, MidHit):
            block = _format_mid_hit(hit, include_images=include_images)
        else:
            block = _format_hit_block(hit)

        block_cost = len(block)
        if total_chars + block_cost > char_budget and blocks:
            blocks.append(f"\n... (截断，共 {len(hits)} 个结果，仅展示前 {i} 个)")
            break
        blocks.append(block)
        total_chars += block_cost

    return "\n\n---\n\n".join(blocks)
