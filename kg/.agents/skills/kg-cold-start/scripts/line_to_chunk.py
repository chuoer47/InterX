"""Map line ranges from evidence refs to chunk_ids using source_span.

Loads chunks for each manual, builds an interval lookup, and resolves
every evidence_ref record's line_ranges to concrete chunk_ids.

Usage:
    python line_to_chunk.py \
        --evidence InterX/kg/state/evidence_resolved.json \
        --process-dir InterX/process/artifacts/manuals \
        --output InterX/kg/state/evidence_mapped.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_chunks_for_manual(manual_dir: Path, chunk_type: str = "small") -> list[dict[str, Any]]:
    """Load chunks from a jsonl file."""
    path = manual_dir / f"{chunk_type}_chunks.jsonl"
    chunks: list[dict[str, Any]] = []
    if not path.exists():
        return chunks
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    return chunks


def build_line_index(chunks: list[dict[str, Any]]) -> list[tuple[int, int, str]]:
    """Build a sorted list of (start_line, end_line, chunk_id) for interval matching.

    Assumes chunks are in document order (start_line monotonically increasing).
    """
    intervals: list[tuple[int, int, str]] = []
    for c in chunks:
        span = c.get("source_span", {})
        start = span.get("start_line", 0)
        end = span.get("end_line", 0)
        if start > 0 and end > 0:
            intervals.append((start, end, c["chunk_id"]))
    # Sort by start line
    intervals.sort(key=lambda x: x[0])
    return intervals


def find_chunk_for_line(
    line_num: int,
    intervals: list[tuple[int, int, str]],
) -> str | None:
    """Find the chunk_id whose source_span contains the given line number.

    Uses binary search for efficiency. Returns None if no match.
    """
    lo, hi = 0, len(intervals) - 1
    best: str | None = None
    while lo <= hi:
        mid = (lo + hi) // 2
        start, end, chunk_id = intervals[mid]
        if line_num < start:
            hi = mid - 1
        elif line_num > end:
            lo = mid + 1
        else:
            # Line falls within this interval
            best = chunk_id
            break
    return best


def resolve_line_range(
    start: int,
    end: int,
    intervals: list[tuple[int, int, str]],
) -> list[str]:
    """Resolve a line range to one or more chunk_ids.

    A line range may span multiple chunks. We collect all chunks
    whose intervals overlap with [start, end].
    """
    chunk_ids: list[str] = []
    for s, e, cid in intervals:
        if e < start:
            continue  # chunk ends before range starts
        if s > end:
            break  # chunk starts after range ends (sorted, so we can stop)
        # Overlap exists
        if cid not in chunk_ids:
            chunk_ids.append(cid)
    return chunk_ids


def main():
    parser = argparse.ArgumentParser(description="Map line ranges to chunk_ids")
    parser.add_argument("--evidence", required=True, help="Path to evidence_resolved.json")
    parser.add_argument("--process-dir", required=True, help="Path to process/artifacts/manuals")
    parser.add_argument("--output", required=True, help="Output JSON path")
    args = parser.parse_args()

    evidence_path = Path(args.evidence)
    process_dir = Path(args.process_dir)
    output_path = Path(args.output)

    with open(evidence_path, encoding="utf-8") as f:
        evidence_data = json.load(f)

    records = evidence_data["records"]

    # Group records by manual_id to load chunks once per manual
    manual_ids: set[str] = set()
    for r in records:
        mid = r.get("manual_id")
        if mid:
            manual_ids.add(mid)

    # Load chunk intervals per manual
    print(f"Loading chunks for {len(manual_ids)} manuals...")
    manual_intervals: dict[str, list[tuple[int, int, str]]] = {}
    for mid in sorted(manual_ids):
        manual_dir = process_dir / mid
        chunks = load_chunks_for_manual(manual_dir, "small")
        intervals = build_line_index(chunks)
        manual_intervals[mid] = intervals

    # Resolve each record
    stats = {"total_records": len(records), "mapped": 0, "unmapped": 0, "multi_chunk": 0}
    for r in records:
        mid = r.get("manual_id")
        line_ranges = r.get("line_ranges", [])

        if not mid or not line_ranges:
            r["chunk_ids"] = []
            r["map_confidence"] = "none"
            stats["unmapped"] += 1
            continue

        intervals = manual_intervals.get(mid, [])
        all_chunk_ids: list[str] = []

        for lr in line_ranges:
            start, end = lr["start"], lr["end"]
            cids = resolve_line_range(start, end, intervals)
            all_chunk_ids.extend(cids)

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_ids: list[str] = []
        for cid in all_chunk_ids:
            if cid not in seen:
                seen.add(cid)
                unique_ids.append(cid)

        r["chunk_ids"] = unique_ids

        if unique_ids:
            stats["mapped"] += 1
            if len(unique_ids) > 1:
                stats["multi_chunk"] += 1
            r["map_confidence"] = "high"
        else:
            stats["unmapped"] += 1
            r["map_confidence"] = "none"

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fp:
        json.dump({"stats": stats, "records": records}, fp, ensure_ascii=False, indent=2)

    print(f"Mapped: {stats['mapped']}/{stats['total_records']} records")
    print(f"Multi-chunk refs: {stats['multi_chunk']}")
    print(f"Unmapped: {stats['unmapped']}")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
