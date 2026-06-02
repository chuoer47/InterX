#!/usr/bin/env python3
"""Create a labeled contact sheet for images referenced by a Markdown file."""

from __future__ import annotations

import argparse
import math
import pathlib
import re

from PIL import Image, ImageDraw


IMAGE_RE = re.compile(r"!\[[^\]]*]\(([^)]+)\)")


def parse_range(value: str, total: int) -> set[int] | None:
    if not value:
        return None
    selected: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start, end = int(start_s), int(end_s)
            selected.update(range(start, end + 1))
        else:
            selected.add(int(part))
    return {idx for idx in selected if 1 <= idx <= total}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("markdown", type=pathlib.Path)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--columns", type=int, default=3)
    parser.add_argument("--thumb-width", type=int, default=220)
    parser.add_argument("--thumb-height", type=int, default=160)
    parser.add_argument("--select", default="", help="1-based image indexes, e.g. 1,3,8-12")
    args = parser.parse_args()

    lines = args.markdown.read_text(encoding="utf-8").splitlines()
    refs: list[tuple[int, str, pathlib.Path]] = []
    for lineno, line in enumerate(lines, 1):
        match = IMAGE_RE.search(line)
        if match:
            rel = match.group(1)
            refs.append((lineno, rel, args.markdown.parent / rel))

    selected = parse_range(args.select, len(refs))
    if selected is not None:
        refs = [item for idx, item in enumerate(refs, 1) if idx in selected]

    thumbs = []
    for idx, (lineno, rel, path) in enumerate(refs, 1):
        image = Image.open(path).convert("RGB")
        original_size = image.size
        image.thumbnail((args.thumb_width, args.thumb_height))
        thumbs.append((idx, lineno, rel, image.copy(), original_size))

    if not thumbs:
        raise SystemExit("No images selected")

    label_height = 42
    padding = 14
    cell_w = args.thumb_width + padding * 2
    cell_h = args.thumb_height + label_height + padding
    columns = max(1, args.columns)
    rows = math.ceil(len(thumbs) / columns)
    sheet = Image.new("RGB", (columns * cell_w, rows * cell_h), "white")
    draw = ImageDraw.Draw(sheet)

    for pos, (idx, lineno, rel, image, original_size) in enumerate(thumbs):
        col = pos % columns
        row = pos // columns
        x = col * cell_w + padding
        y = row * cell_h + padding
        draw.text((x, y), f"#{idx} L{lineno} {rel}", fill=(0, 0, 0))
        draw.text((x, y + 17), f"{original_size[0]}x{original_size[1]}", fill=(80, 80, 80))
        sheet.paste(image, (x, y + label_height))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output, quality=94)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
