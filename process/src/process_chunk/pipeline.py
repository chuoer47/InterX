from __future__ import annotations
"""Build pipeline for turning manuals into hierarchical chunk artifacts."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import time
from typing import Any

from .builder import (
    _big_chunk_payload,
    _make_big_entries,
    _make_mid_entries,
    _mid_chunk_payload,
    _small_chunk_payloads,
)
from .config import ProcessSettings
from .parser import parse_markdown_sections
from .tokenization import TokenCounter
from .utils import safe_id


@dataclass(frozen=True, slots=True)
class ManualBuildResult:
    """Summary metrics for one manual build."""
    manual_id: str
    manual_name: str
    manual_dir: Path
    source_path: Path
    big_count: int
    mid_count: int
    small_count: int
    image_count: int
    header_count: int
    missing_image_count: int
    elapsed_seconds: float


def _now_iso() -> str:
    """Return a stable UTC timestamp for manifests and logs."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    """Write pretty JSON output, creating parent directories when needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write JSONL output used by downstream embedding and inspection scripts."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _append_log(path: Path, message: str) -> None:
    """Append a timestamped line to the build log."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{_now_iso()} {message}\n")


def _token_stats(rows: list[dict[str, Any]]) -> dict[str, float | int]:
    """Compute compact token distribution statistics for a chunk list."""
    values = sorted(int(row.get("token_count", 0)) for row in rows)
    if not values:
        return {"count": 0, "min": 0, "max": 0, "avg": 0.0}
    return {
        "count": len(values),
        "min": values[0],
        "max": values[-1],
        "avg": round(sum(values) / len(values), 2),
        "p50": values[len(values) // 2],
        "p90": values[int((len(values) - 1) * 0.9)],
    }


def _missing_images(rows: list[dict[str, Any]]) -> list[str]:
    """List missing image files referenced by chunk payloads."""
    missing: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for image_path in row.get("image_abs_paths", []):
            if image_path in seen:
                continue
            seen.add(image_path)
            if not Path(image_path).exists():
                missing.append(image_path)
    return missing


def build_manual(manual_path: Path, *, settings: ProcessSettings) -> ManualBuildResult:
    """
    Build all artifacts for one manual.

    The pipeline is intentionally hierarchical: parse -> big chunks -> mid chunks ->
    small chunks. Each level reuses the entry lineage from the previous level so the
    final artifacts can always be traced back to the original source section.
    """
    started = time.monotonic()
    token_counter = TokenCounter(settings.tokenizer.encoding_name)
    sections = parse_markdown_sections(
        manual_path,
        token_counter=token_counter,
        image_dir=settings.paths.image_dir,
        image_token_cost=settings.tokenizer.image_token_cost,
    )
    manual_id = safe_id(manual_path.stem, prefix="manual")
    manual_name = manual_path.stem
    manual_dir = settings.paths.artifact_dir / "manuals" / manual_id

    big_chunks: list[dict[str, Any]] = []
    big_entries_by_id: dict[str, list[dict[str, Any]]] = {}
    header_path_by_big_id: dict[str, tuple[str, ...]] = {}
    for section in sections:
        for entries in _make_big_entries(
            section=section,
            token_counter=token_counter,
            scheme=settings.scheme,
            image_token_cost=settings.tokenizer.image_token_cost,
        ):
            chunk = _big_chunk_payload(
                entries=entries,
                scheme=settings.scheme,
                doc_id=manual_id,
                doc_name=manual_name,
                source_path=manual_path,
                header_path=section.header_path,
                chunk_index=len(big_chunks),
            )
            big_chunks.append(chunk)
            big_entries_by_id[chunk["chunk_id"]] = entries
            header_path_by_big_id[chunk["chunk_id"]] = section.header_path

    mid_chunks: list[dict[str, Any]] = []
    mid_entries_by_id: dict[str, list[dict[str, Any]]] = {}
    mid_big_by_id: dict[str, dict[str, Any]] = {}
    header_path_by_mid_id: dict[str, tuple[str, ...]] = {}
    for big in big_chunks:
        header_path = header_path_by_big_id[big["chunk_id"]]
        mid_groups = _make_mid_entries(
            big_entries=big_entries_by_id[big["chunk_id"]],
            token_counter=token_counter,
            scheme=settings.scheme,
            image_token_cost=settings.tokenizer.image_token_cost,
        )
        for mid_index, entries in enumerate(mid_groups):
            mid = _mid_chunk_payload(
                big=big,
                entries=entries,
                scheme=settings.scheme,
                header_path=header_path,
                mid_index_in_big=mid_index,
            )
            mid_chunks.append(mid)
            mid_entries_by_id[mid["chunk_id"]] = entries
            mid_big_by_id[mid["chunk_id"]] = big
            header_path_by_mid_id[mid["chunk_id"]] = header_path

    small_chunks: list[dict[str, Any]] = []
    for mid in mid_chunks:
        small_chunks.extend(
            _small_chunk_payloads(
                big=mid_big_by_id[mid["chunk_id"]],
                mid=mid,
                entries=mid_entries_by_id[mid["chunk_id"]],
                token_counter=token_counter,
                scheme=settings.scheme,
                header_path=header_path_by_mid_id[mid["chunk_id"]],
                image_token_cost=settings.tokenizer.image_token_cost,
            )
        )

    # The manual directory stores both machine-readable payloads and summary files
    # so later steps can inspect one manual in isolation without opening global manifests.
    manual_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(manual_dir / "big_chunks.jsonl", big_chunks)
    _write_jsonl(manual_dir / "mid_chunks.jsonl", mid_chunks)
    _write_jsonl(manual_dir / "small_chunks.jsonl", small_chunks)

    manifest = {
        "build_time": _now_iso(),
        "manual_id": manual_id,
        "manual_name": manual_name,
        "source_path": str(manual_path),
        "counts": {
            "big": len(big_chunks),
            "mid": len(mid_chunks),
            "small": len(small_chunks),
        },
        "token_stats": {
            "big": _token_stats(big_chunks),
            "mid": _token_stats(mid_chunks),
            "small": _token_stats(small_chunks),
        },
        "header_count": sum(1 for section in sections if section.heading_text),
        "image_count": sum(int(row.get("image_count", 0)) for row in big_chunks),
        "missing_images": _missing_images(big_chunks + mid_chunks + small_chunks),
        "files": {
            "big_chunks": str(manual_dir / "big_chunks.jsonl"),
            "mid_chunks": str(manual_dir / "mid_chunks.jsonl"),
            "small_chunks": str(manual_dir / "small_chunks.jsonl"),
        },
    }
    _write_json(manual_dir / "manifest.json", manifest)

    return ManualBuildResult(
        manual_id=manual_id,
        manual_name=manual_name,
        manual_dir=manual_dir,
        source_path=manual_path,
        big_count=len(big_chunks),
        mid_count=len(mid_chunks),
        small_count=len(small_chunks),
        image_count=manifest["image_count"],
        header_count=manifest["header_count"],
        missing_image_count=len(manifest["missing_images"]),
        elapsed_seconds=round(time.monotonic() - started, 3),
    )


def build_all(*, settings: ProcessSettings, clean: bool = True) -> list[ManualBuildResult]:
    """Build every manual selected by the process configuration."""
    artifact_dir = settings.paths.artifact_dir
    log_path = artifact_dir / "logs" / "build.log"

    if clean and artifact_dir.exists():
        shutil.rmtree(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    results: list[ManualBuildResult] = []
    _append_log(log_path, f"start manuals={len(settings.manual_files())}")
    for manual_path in settings.manual_files():
        result = build_manual(manual_path, settings=settings)
        results.append(result)
        _append_log(
            log_path,
            f"manual={result.manual_name} big={result.big_count} mid={result.mid_count} "
            f"small={result.small_count} images={result.image_count} "
            f"missing_images={result.missing_image_count} elapsed={result.elapsed_seconds}",
        )

    write_global_outputs(settings=settings, results=results)
    _append_log(log_path, f"done manuals={len(results)}")
    return results


def write_global_outputs(*, settings: ProcessSettings, results: list[ManualBuildResult]) -> None:
    """Write cross-manual manifests and aggregate statistics."""
    manuals = [
        {
            "manual_id": row.manual_id,
            "manual_name": row.manual_name,
            "source_path": str(row.source_path),
            "manual_dir": str(row.manual_dir),
            "manifest_path": str(row.manual_dir / "manifest.json"),
            "big_count": row.big_count,
            "mid_count": row.mid_count,
            "small_count": row.small_count,
            "image_count": row.image_count,
            "header_count": row.header_count,
            "missing_image_count": row.missing_image_count,
            "elapsed_seconds": row.elapsed_seconds,
        }
        for row in results
    ]
    totals = {
        "manual_count": len(results),
        "big_count": sum(row.big_count for row in results),
        "mid_count": sum(row.mid_count for row in results),
        "small_count": sum(row.small_count for row in results),
        "image_count": sum(row.image_count for row in results),
        "missing_image_count": sum(row.missing_image_count for row in results),
        "elapsed_seconds": round(sum(row.elapsed_seconds for row in results), 3),
    }
    index = {
        "build_time": _now_iso(),
        "config_path": str(settings.config_path),
        "totals": totals,
        "manuals": manuals,
    }
    _write_json(settings.paths.artifact_dir / "manifests" / "index.json", index)

    stats = {
        **index,
        "averages": {
            "big_per_manual": round(totals["big_count"] / max(1, totals["manual_count"]), 2),
            "mid_per_manual": round(totals["mid_count"] / max(1, totals["manual_count"]), 2),
            "small_per_manual": round(totals["small_count"] / max(1, totals["manual_count"]), 2),
            "images_per_manual": round(totals["image_count"] / max(1, totals["manual_count"]), 2),
        },
        "anomalies": [
            row
            for row in manuals
            if row["big_count"] == 0
            or row["mid_count"] == 0
            or row["small_count"] == 0
            or row["missing_image_count"] > 0
        ],
    }
    _write_json(settings.paths.artifact_dir / "reports" / "chunk_stats.json", stats)
    _write_stats_markdown(settings.paths.artifact_dir / "reports" / "chunk_stats.md", stats)


def _write_stats_markdown(path: Path, stats: dict[str, Any]) -> None:
    """Render a lightweight human-readable summary alongside the JSON report."""
    totals = stats["totals"]
    averages = stats["averages"]
    lines = [
        "# InterX Process Chunk Stats",
        "",
        f"- Build time: `{stats['build_time']}`",
        f"- Manuals: `{totals['manual_count']}`",
        f"- Big chunks: `{totals['big_count']}`",
        f"- Mid chunks: `{totals['mid_count']}`",
        f"- Small chunks: `{totals['small_count']}`",
        f"- Images attached to big chunks: `{totals['image_count']}`",
        f"- Missing images: `{totals['missing_image_count']}`",
        "",
        "## Averages",
        "",
        f"- Big/manual: `{averages['big_per_manual']}`",
        f"- Mid/manual: `{averages['mid_per_manual']}`",
        f"- Small/manual: `{averages['small_per_manual']}`",
        f"- Images/manual: `{averages['images_per_manual']}`",
        "",
        "## Manuals",
        "",
        "| manual | big | mid | small | images | missing |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in stats["manuals"]:
        lines.append(
            f"| {row['manual_name']} | {row['big_count']} | {row['mid_count']} | "
            f"{row['small_count']} | {row['image_count']} | {row['missing_image_count']} |"
        )
    if stats["anomalies"]:
        lines.extend(["", "## Anomalies", ""])
        for row in stats["anomalies"]:
            lines.append(f"- `{row['manual_name']}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
