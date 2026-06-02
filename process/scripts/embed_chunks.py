from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from process_chunk.config import ProcessSettings
from process_chunk.embedding import embed_file
from process_chunk.utils import read_jsonl


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Embed InterX process small chunks.")
    parser.add_argument("--config", default=None, help="Path to process config YAML.")
    parser.add_argument("--manual", default=None, help="Only embed a specific manual name (stem).")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be embedded without calling API.")
    args = parser.parse_args()

    settings = ProcessSettings.load(args.config)
    manuals_dir = settings.paths.artifact_dir / "manuals"

    if not manuals_dir.exists():
        print(f"Error: {manuals_dir} does not exist. Run build_chunks.py first.", file=sys.stderr)
        sys.exit(1)

    manual_dirs = sorted(d for d in manuals_dir.iterdir() if d.is_dir())
    if args.manual:
        manual_dirs = [d for d in manual_dirs if args.manual in d.name]
        if not manual_dirs:
            print(f"Error: no manual matching '{args.manual}'", file=sys.stderr)
            sys.exit(1)

    total_embedded = 0
    total_chunks = 0
    started = time.monotonic()

    for manual_dir in manual_dirs:
        chunks_path = manual_dir / "small_chunks.jsonl"
        embeddings_path = manual_dir / "embeddings.jsonl"
        if not chunks_path.exists():
            print(f"  SKIP {manual_dir.name}: no small_chunks.jsonl")
            continue

        chunks = read_jsonl(chunks_path)
        total_chunks += len(chunks)

        if args.dry_run:
            existing = read_jsonl(embeddings_path) if embeddings_path.exists() else []
            print(f"  DRY  {manual_dir.name}: {len(chunks)} chunks, {len(existing)} already embedded")
            continue

        print(f"  {manual_dir.name}: {len(chunks)} chunks ... ", end="", flush=True)
        enriched = embed_file(
            input_path=chunks_path,
            output_path=embeddings_path,
            api_config=settings.api,
            config=settings.embedding,
            incremental=True,
        )
        total_embedded += len(enriched)
        print(f"done ({len(enriched)} rows written)")

    elapsed = time.monotonic() - started
    print(f"\nSummary:")
    print(f"  Manuals processed: {len(manual_dirs)}")
    print(f"  Total chunks: {total_chunks}")
    if not args.dry_run:
        print(f"  Embedded rows written: {total_embedded}")
        print(f"  Elapsed: {elapsed:.1f}s")


if __name__ == "__main__":
    main()
