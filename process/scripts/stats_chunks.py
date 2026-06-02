from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    stats_path = ROOT / "artifacts" / "reports" / "chunk_stats.json"
    if not stats_path.exists():
        raise SystemExit(f"Missing stats file: {stats_path}")

    payload = json.loads(stats_path.read_text(encoding="utf-8"))
    print(json.dumps(payload.get("totals", {}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
