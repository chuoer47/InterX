#!/usr/bin/env python3
"""Print image references with nearby Markdown context."""

from __future__ import annotations

import argparse
import pathlib
import re


IMAGE_RE = re.compile(r"!\[[^\]]*]\(([^)]+)\)")


def non_empty_window(lines: list[str], start: int, end: int) -> list[str]:
    items: list[str] = []
    for lineno in range(max(1, start), min(len(lines), end) + 1):
        text = lines[lineno - 1].strip()
        if text:
            items.append(f"{lineno}: {lines[lineno - 1]}")
    return items


def nearest_heading(lines: list[str], image_lineno: int) -> str:
    for lineno in range(image_lineno - 1, 0, -1):
        if lines[lineno - 1].startswith("#"):
            return f"{lineno}: {lines[lineno - 1]}"
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("markdown", type=pathlib.Path)
    parser.add_argument("--before", type=int, default=4, help="Lines before each image to show")
    parser.add_argument("--after", type=int, default=5, help="Lines after each image to show")
    args = parser.parse_args()

    lines = args.markdown.read_text(encoding="utf-8").splitlines()
    count = 0
    for image_lineno, line in enumerate(lines, 1):
        match = IMAGE_RE.search(line)
        if not match:
            continue
        count += 1
        rel = match.group(1)
        path = args.markdown.parent / rel
        print("\n---")
        print(f"IMAGE {count} line {image_lineno}: {rel}")
        print(f"exists: {path.exists()}")
        heading = nearest_heading(lines, image_lineno)
        if heading:
            print(f"heading: {heading}")
        before = non_empty_window(lines, image_lineno - args.before, image_lineno - 1)
        after = non_empty_window(lines, image_lineno + 1, image_lineno + args.after)
        print("before:")
        for item in before:
            print(f"  {item}")
        print("after:")
        for item in after:
            print(f"  {item}")
    print(f"\nTotal images: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
