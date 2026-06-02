"""Resolve agentic-rag evidence refs to structured (manual_id, line_range) tuples.

Parses both dict-format and string-format evidence refs from EN and CH answers.
Handles all line number formats: single, dash-range, bracket-list, mixed.

Usage:
    python resolve_refs.py \
        --answers-dir InterX/agentic-rag/answers \
        --process-dir InterX/process/artifacts/manuals \
        --output InterX/kg/state/evidence_resolved.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


def build_manual_lookup(process_dir: Path) -> dict[str, str]:
    """Map source markdown filename → process manual folder name.

    Reads the first chunk of each manual's small_chunks.jsonl to get source_path,
    then extracts the basename for lookup.
    """
    lookup: dict[str, str] = {}
    for folder in sorted(process_dir.iterdir()):
        if not folder.is_dir():
            continue
        chunk_file = folder / "small_chunks.jsonl"
        if not chunk_file.exists():
            continue
        with open(chunk_file, encoding="utf-8") as f:
            first_line = f.readline().strip()
            if not first_line:
                continue
            chunk = json.loads(first_line)
            source = os.path.basename(chunk["source_path"])
            lookup[source] = folder.name
    return lookup


def parse_line_ranges(lines_str: str) -> list[tuple[int, int]]:
    """Parse a lines field into a list of (start, end) tuples.

    Handles formats:
        "115-119"       → [(115, 119)]
        "290"           → [(290, 290)]
        "[125, 127, 129]" → [(125, 125), (127, 127), (129, 129)]
        "7, 35-37"      → [(7, 7), (35, 37)]
        "[154,155,157]" → [(154, 154), (155, 155), (157, 157)]
        "970, 976, 980" → [(970, 970), (976, 976), (980, 980)]
    """
    if not lines_str:
        return []

    s = lines_str.strip().strip("[]")
    if not s:
        return []

    ranges: list[tuple[int, int]] = []
    # Split on comma
    parts = [p.strip() for p in s.split(",") if p.strip()]
    for part in parts:
        # Try dash range: "115-119" or "115 - 119"
        m = re.match(r"^(\d+)\s*[-–—]\s*(\d+)$", part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            ranges.append((min(a, b), max(a, b)))
            continue
        # Try tilde range (Chinese): "115～119"
        m = re.match(r"^(\d+)\s*[～~]\s*(\d+)$", part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            ranges.append((min(a, b), max(a, b)))
            continue
        # Single number
        m = re.match(r"^(\d+)$", part)
        if m:
            n = int(m.group(1))
            ranges.append((n, n))
            continue
        # If we can't parse, skip this part
        # (handles edge cases like "image" or empty strings)

    return ranges


def parse_string_ref(ref_str: str) -> tuple[str, str]:
    """Parse a string-format evidence ref into (file_path, lines_str).

    Format: "agentic-rag/en-manual/Philips Airfryer.md:115-119"
    or:     "agentic-rag/ch-manual/洗碗机手册.md:290"
    """
    # Split on last colon to handle filenames with colons (unlikely but safe)
    m = re.match(r"^(.+):(\d[\d\-~, \[\]]*)$", ref_str)
    if m:
        return m.group(1), m.group(2)
    # If no line numbers, return the whole string as file path
    return ref_str, ""


def file_path_to_display_name(file_path: str) -> str:
    """Extract the display name from an agentic-rag file path.

    "agentic-rag/en-manual/Philips Airfryer.md" → "Philips Airfryer.md"
    "agentic-rag/ch-manual/洗碗机手册.md" → "洗碗机手册.md"
    """
    return os.path.basename(file_path)


def resolve_one_answer(
    answer: dict,
    manual_lookup: dict[str, str],
) -> list[dict]:
    """Resolve evidence refs for a single answer into structured records."""
    results: list[dict] = []
    evidence_refs = answer.get("evidence_refs", [])

    for ref in evidence_refs:
        record: dict = {
            "answer_id": str(answer.get("id", "")),
            "question": answer.get("question", ""),
        }

        if isinstance(ref, str):
            file_path, lines_str = parse_string_ref(ref)
            display_name = file_path_to_display_name(file_path)
            record["ref_format"] = "string"
            record["summary"] = ""
        elif isinstance(ref, dict):
            file_path = ref.get("file", "") or ref.get("source", "") or ref.get("manual", "")
            display_name = file_path_to_display_name(file_path)
            lines_str = ref.get("lines", "")
            record["ref_format"] = "dict"
            record["summary"] = ref.get("text", "") or ref.get("note", "") or ref.get("summary", "")
        else:
            continue

        # Skip meta-file (手册内容总览.md is a routing index, not a real manual)
        if "手册内容总览" in display_name:
            continue

        manual_id = manual_lookup.get(display_name)
        line_ranges = parse_line_ranges(str(lines_str))

        record["display_name"] = display_name
        record["manual_id"] = manual_id
        record["line_ranges"] = [{"start": s, "end": e} for s, e in line_ranges]
        record["parse_confidence"] = "high" if (manual_id and line_ranges) else "low"

        if not manual_id:
            record["parse_issue"] = "manual_not_found"
        elif not line_ranges:
            record["parse_issue"] = "no_lines_parsed"
        else:
            record["parse_issue"] = None

        results.append(record)

    return results


def main():
    parser = argparse.ArgumentParser(description="Resolve agentic-rag evidence refs")
    parser.add_argument("--answers-dir", required=True, help="Path to agentic-rag/answers")
    parser.add_argument("--process-dir", required=True, help="Path to process/artifacts/manuals")
    parser.add_argument("--output", required=True, help="Output JSON path")
    args = parser.parse_args()

    answers_dir = Path(args.answers_dir)
    process_dir = Path(args.process_dir)
    output_path = Path(args.output)

    # Build manual name lookup
    manual_lookup = build_manual_lookup(process_dir)
    print(f"Loaded {len(manual_lookup)} manual mappings")

    # Process all answers
    all_records: list[dict] = []
    stats = {"total_answers": 0, "total_refs": 0, "resolved": 0, "unresolved": 0}

    for lang, subdir in [("en", "en-answers/per_question"), ("ch", "ch-answers/per_question")]:
        answer_dir = answers_dir / subdir
        if not answer_dir.exists():
            print(f"Warning: {answer_dir} not found, skipping")
            continue

        for f in sorted(answer_dir.glob("*.json")):
            with open(f, encoding="utf-8") as fp:
                answer = json.load(fp)
            answer["_lang"] = lang
            stats["total_answers"] += 1

            records = resolve_one_answer(answer, manual_lookup)
            stats["total_refs"] += len(records)

            for r in records:
                r["lang"] = lang
                if r["manual_id"] and r["line_ranges"]:
                    stats["resolved"] += 1
                else:
                    stats["unresolved"] += 1

            all_records.extend(records)

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fp:
        json.dump({"stats": stats, "records": all_records}, fp, ensure_ascii=False, indent=2)

    print(f"Resolved {stats['resolved']}/{stats['total_refs']} refs "
          f"({stats['unresolved']} unresolved)")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
