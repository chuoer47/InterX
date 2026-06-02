"""Answer normalization — align <PIC> placeholders with image list."""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from .models import AnswerPayload


INLINE_IMAGE_MARKER_RE = re.compile(
    r"""
    (?P<open>[\[\(（【<])?
    \s*
    (?:图片|图示|图|PIC|pic)
    \s*[：:]\s*
    (?P<image>[A-Za-z0-9][A-Za-z0-9_-]*(?:\.[A-Za-z0-9]+)?)
    \s*(?P<close>[\]\)）】>])?
    """,
    flags=re.X,
)
INLINE_SENTINEL_RE = re.compile(r"@@INLINE_(\d+)@@|<PIC>")
TEXT_BETWEEN_PICS_RE = re.compile(r"[\w\u4e00-\u9fff]", flags=re.U)


def _normalize_image_name(name: str) -> str:
    return Path(name.strip()).stem


def repair_inline_markers(content: str, *, allowed: list[str]) -> tuple[str, list[str | None]]:
    """Convert model-emitted [图片:xxx] to <PIC>, aligning with allowed images."""
    allowed_map = {_normalize_image_name(a): _normalize_image_name(a) for a in allowed}
    marker_images: list[str] = []

    def replace_marker(m: re.Match) -> str:
        raw = m.group("image")
        norm = _normalize_image_name(raw)
        resolved = allowed_map.get(norm)
        if not resolved:
            return ""
        marker_images.append(resolved)
        return f"@@INLINE_{len(marker_images) - 1}@@"

    marked = INLINE_IMAGE_MARKER_RE.sub(replace_marker, content)
    slots: list[str | None] = []

    def replace_slot(m: re.Match) -> str:
        idx = m.group(1)
        if idx is None:
            slots.append(None)
        else:
            slots.append(marker_images[int(idx)])
        return "<PIC>"

    repaired = INLINE_SENTINEL_RE.sub(replace_slot, marked)
    repaired = re.sub(r"[ \t]{2,}", " ", repaired)
    repaired = re.sub(r"\s+([，。；、,.!?！？])", r"\1", repaired)
    return repaired.strip(), slots


def _has_text_between_pics(value: str) -> bool:
    return bool(TEXT_BETWEEN_PICS_RE.search(value.replace("<PIC>", "")))


def _remove_unsupported_or_duplicate(content: str, images: list[str]) -> tuple[str, list[str]]:
    parts = content.split("<PIC>")
    if len(parts) - 1 != len(images):
        return content.strip(), images

    rebuilt = parts[0]
    filtered: list[str] = []
    seen: set[str] = set()
    prev_kept = False
    for idx, img in enumerate(images):
        following = parts[idx + 1]
        has_before = _has_text_between_pics(parts[idx])
        has_after = _has_text_between_pics(following)
        keep = (
            img not in seen
            and (has_before or has_after)
            and (has_before or not prev_kept)
        )
        if keep:
            rebuilt += "<PIC>"
            filtered.append(img)
            seen.add(img)
        prev_kept = keep
        rebuilt += following
    return rebuilt.strip(), filtered


def normalize_answer(answer: AnswerPayload, *, allowed_images: list[str]) -> AnswerPayload:
    """Normalize an AnswerPayload: repair markers, deduplicate, align PIC↔images."""
    content, slots = repair_inline_markers(answer.content.strip(), allowed=allowed_images)
    pic_count = content.count("<PIC>")

    allowed_set = {_normalize_image_name(a) for a in allowed_images}
    answer_images = [_normalize_image_name(a) for a in answer.images if _normalize_image_name(a) in allowed_set]
    avail = Counter(answer_images)

    images: list[str] = []
    keep_mask: list[bool] = []
    ai = 0
    for slot in slots:
        norm = slot
        if norm is None:
            while ai < len(answer_images):
                candidate = answer_images[ai]
                ai += 1
                if avail[candidate] > 0:
                    avail[candidate] -= 1
                    norm = candidate
                    break
        if norm:
            images.append(norm)
            keep_mask.append(True)
        else:
            keep_mask.append(False)

    if pic_count == 0:
        images = []
    elif len(images) != pic_count:
        parts = content.split("<PIC>")
        if len(parts) - 1 == len(keep_mask):
            rebuilt = parts[0]
            for keep, part in zip(keep_mask, parts[1:]):
                if keep:
                    rebuilt += "<PIC>"
                rebuilt += part
            content = rebuilt.strip()

    content, images = _remove_unsupported_or_duplicate(content, images)
    return AnswerPayload(content=content, images=images)
