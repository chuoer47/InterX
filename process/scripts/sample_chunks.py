from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Print a few chunk samples from one manual artifact directory.")
    parser.add_argument("manual_id_or_name")
    parser.add_argument("--kind", choices=["big", "mid", "small"], default="small")
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()

    manuals_dir = ROOT / "artifacts" / "manuals"
    matches = [path for path in manuals_dir.iterdir() if path.is_dir() and args.manual_id_or_name in path.name]
    if not matches:
        raise SystemExit(f"No manual matched: {args.manual_id_or_name}")

    target = matches[0] / f"{args.kind}_chunks.jsonl"
    if not target.exists():
        raise SystemExit(f"Missing file: {target}")

    with target.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle):
            if index >= args.limit:
                break
            row = json.loads(line)
            print(f"[{index}] {row['chunk_id']} tokens={row.get('token_count')} images={row.get('image_count')}")
            print(row.get("content", "")[:600])
            print("-" * 80)


if __name__ == "__main__":
    main()
