from __future__ import annotations

import sys
from pathlib import Path


# The helper script keeps `python scripts/...` usage working without requiring the
# package to be installed into the active environment first.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from process_chunk.cli import main


if __name__ == "__main__":
    main()
