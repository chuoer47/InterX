from __future__ import annotations

import argparse

from .config import ProcessSettings
from .pipeline import build_all


def main() -> None:
    """Run the end-to-end chunk build pipeline from the command line."""
    parser = argparse.ArgumentParser(description="Build InterX process small/mid/big chunks.")
    parser.add_argument("--config", default=None, help="Path to process config YAML.")
    parser.add_argument("--no-clean", action="store_true", help="Keep existing artifacts before building.")
    args = parser.parse_args()

    settings = ProcessSettings.load(args.config)
    results = build_all(settings=settings, clean=not args.no_clean)

    # The summary keeps the CLI usable in scripts without requiring users to open
    # the generated manifest files just to confirm the build succeeded.
    print(f"built {len(results)} manuals")
    print(f"big={sum(row.big_count for row in results)}")
    print(f"mid={sum(row.mid_count for row in results)}")
    print(f"small={sum(row.small_count for row in results)}")


if __name__ == "__main__":
    main()
