from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from process_chunk.config import ProcessSettings
from process_chunk.vector_store import build_vector_store


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Build unified Milvus DB from all process chunks.")
    parser.add_argument("--config", default=None, help="Path to process config YAML.")
    parser.add_argument("--no-rebuild", action="store_true", help="Append to existing collection instead of dropping.")
    args = parser.parse_args()

    settings = ProcessSettings.load(args.config)
    manuals_dir = settings.paths.artifact_dir / "manuals"
    db_path = settings.paths.artifact_dir / "manual_chunks.db"

    if not manuals_dir.exists():
        print(f"Error: {manuals_dir} does not exist. Run build_chunks.py first.", file=sys.stderr)
        sys.exit(1)

    print(f"Building unified DB at {db_path}")
    print(f"Collection: {settings.vector_store.collection_name}")
    print(f"Rebuild: {not args.no_rebuild}")

    started = time.monotonic()
    count = build_vector_store(
        manuals_dir=manuals_dir,
        db_path=db_path,
        config=settings.vector_store,
        rebuild=not args.no_rebuild,
    )
    elapsed = time.monotonic() - started

    print(f"\nDone: {count} chunks ingested in {elapsed:.1f}s")
    print(f"DB: {db_path}")


if __name__ == "__main__":
    main()
