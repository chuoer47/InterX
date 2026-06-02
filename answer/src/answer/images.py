"""Image evidence collection and multimodal content assembly."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .utils import image_to_data_url


@dataclass(frozen=True, slots=True)
class ImageEvidence:
    """One retrieved image plus the chunk context that surfaced it."""
    image_id: str
    image_path: Path
    doc_name: str
    chunk_id: str
    rank: int
    source_text: str


def _resolve_image(value: str | Path, image_dir: Path) -> Path | None:
    """
    Resolve an image reference against the local artifact layout.

    Retrieval results may carry absolute paths or historical relative paths, so the
    resolver tries both forms before giving up.
    """
    path = Path(value)
    if path.exists():
        return path
    candidate = image_dir / path.name
    if candidate.exists():
        return candidate
    if len(path.parts) >= 2 and path.parts[-2] == "插图":
        candidate = image_dir / path.parts[-1]
        if candidate.exists():
            return candidate
    return None


def collect_image_evidences(
    chunks: list[dict[str, Any]],
    *,
    image_dir: Path,
    max_images: int | None = None,
) -> list[ImageEvidence]:
    """
    Collect unique images from ranked retrieval chunks.

    The first occurrence wins so the image order follows retrieval relevance rather
    than arbitrary filesystem order.
    """
    evidences: list[ImageEvidence] = []
    seen: set[str] = set()

    for rank, chunk in enumerate(chunks, start=1):
        for value in (chunk.get("image_abs_paths") or []):
            path = _resolve_image(value, image_dir)
            if path is None:
                continue
            image_id = path.stem.strip()
            if not image_id or image_id in seen:
                continue
            seen.add(image_id)
            evidences.append(
                ImageEvidence(
                    image_id=image_id,
                    image_path=path,
                    doc_name=str(chunk.get("doc_name") or "").strip(),
                    chunk_id=str(chunk.get("chunk_id") or "").strip(),
                    rank=rank,
                    source_text=str(chunk.get("content") or chunk.get("text") or "").strip(),
                )
            )
            if max_images is not None and len(evidences) >= max_images:
                return evidences
    return evidences


def format_image_manifest(evidences: list[ImageEvidence], *, english: bool = True) -> str:
    """Describe the available images in prompt-friendly text."""
    if not evidences:
        return "No images available." if english else "无可用图片。"
    delimiter = ", " if english else "、"
    items = delimiter.join(f"{e.image_id} ({e.image_path.name})" for e in evidences)
    if english:
        return (
            f"Available image_id values: {items}\n"
            "The attached images are provided below in the same order as this list.\n"
            "Image anchors in the evidence use the form [图片:image_id]."
        )
    return (
        f"可用图片image_id：{items}\n"
        "下面附带的图片顺序与该列表一致。\n"
        "图片位置已在检索证据中用 [图片:image_id] 标注。"
    )


def build_image_content_blocks(
    evidences: list[ImageEvidence],
    *,
    english: bool = True,
) -> list[dict[str, Any]]:
    """Build the multimodal content blocks appended to the user message."""
    blocks: list[dict[str, Any]] = []
    if evidences:
        blocks.append(
            {
                "type": "text",
                "text": (
                    "Attached images follow below in the same order as the image_id list above."
                    if english
                    else "下面附带的图片顺序与上方 image_id 列表一致。"
                ),
            }
        )
    for evidence in evidences:
        try:
            blocks.append(
                {
                    "type": "image_url",
                    "image_url": {"url": image_to_data_url(evidence.image_path)},
                }
            )
        except FileNotFoundError:
            continue
    return blocks
