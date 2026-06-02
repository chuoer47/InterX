from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect one process manual manifest.")
    parser.add_argument("manual_id_or_name")
    args = parser.parse_args()

    manuals_dir = ROOT / "artifacts" / "manuals"
    matches = [
        path / "manifest.json"
        for path in manuals_dir.iterdir()
        if path.is_dir() and args.manual_id_or_name in path.name
    ]
    if not matches:
        raise SystemExit(f"No manifest matched: {args.manual_id_or_name}")

    # This helper is aimed at quick human inspection, so pretty-printing is more
    # useful here than streaming raw JSONL records.
    payload = json.loads(matches[0].read_text(encoding="utf-8"))
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
