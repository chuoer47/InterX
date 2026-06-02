#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
ANSWERS_DIR = PROJECT / "tmp" / "answers"
PER_QUESTION_DIR = ANSWERS_DIR / "per_question"
IMAGE_DIR = PROJECT / "en-manual" / "插图"
TODO_PATH = PROJECT / "todo.csv"
CSV_PATH = ANSWERS_DIR / "answers.csv"
JSONL_PATH = ANSWERS_DIR / "answers.jsonl"
VALIDATION_PATH = ANSWERS_DIR / "validation_report.json"

REQUIRED_KEYS = {
    "id",
    "question",
    "content",
    "images",
    "ret",
    "manual_guess",
    "evidence_refs",
    "status",
    "notes",
}


def image_exists(image_id: str) -> bool:
    return any((IMAGE_DIR / f"{image_id}{suffix}").exists() for suffix in (".jpg", ".jpeg", ".png", ".webp"))


def expected_ret(content: str, images: list[str]) -> str:
    return f"{json.dumps(content, ensure_ascii=False)},{json.dumps(images, ensure_ascii=False)}".replace("\n", "\\n")


def validate_payload(path: Path) -> tuple[dict, list[str]]:
    errors: list[str] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"id": path.stem}, [f"invalid_json:{exc}"]

    missing = sorted(REQUIRED_KEYS - set(payload))
    if missing:
        errors.append(f"missing_keys:{','.join(missing)}")

    qid = str(payload.get("id") or path.stem).strip()
    content = str(payload.get("content") or "")
    images_raw = payload.get("images")
    images = images_raw if isinstance(images_raw, list) else []
    if not isinstance(images_raw, list):
        errors.append("images_not_list")
    images = [str(item).strip() for item in images if str(item).strip()]

    if content.count("<PIC>") != len(images):
        errors.append(f"pic_image_count_mismatch:{content.count('<PIC>')}!={len(images)}")
    if len(images) != len(set(images)):
        errors.append("duplicate_images")
    missing_images = [image for image in images if not image_exists(image)]
    if missing_images:
        errors.append(f"missing_image_files:{','.join(missing_images)}")
    if re.search(r"<PIC>\s*<PIC>", content):
        errors.append("consecutive_pic_placeholders")

    ret = str(payload.get("ret") or "")
    formatted = expected_ret(content.strip(), images)
    if ret != formatted:
        errors.append("ret_mismatch")

    payload["id"] = qid
    payload["content"] = content.strip()
    payload["images"] = images
    payload["ret"] = ret
    return payload, errors


def sort_key(value: str) -> tuple[int, str]:
    return (int(value), value) if value.isdigit() else (10**18, value)


def main() -> int:
    ANSWERS_DIR.mkdir(parents=True, exist_ok=True)
    PER_QUESTION_DIR.mkdir(parents=True, exist_ok=True)

    valid: dict[str, dict] = {}
    report: dict[str, dict] = {}
    for path in sorted(PER_QUESTION_DIR.glob("*.json"), key=lambda p: sort_key(p.stem)):
        payload, errors = validate_payload(path)
        qid = str(payload.get("id") or path.stem)
        report[qid] = {"path": str(path), "errors": errors}
        if not errors:
            valid[qid] = payload

    with CSV_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id", "ret"])
        writer.writeheader()
        for qid in sorted(valid, key=sort_key):
            writer.writerow({"id": qid, "ret": valid[qid]["ret"]})

    with JSONL_PATH.open("w", encoding="utf-8") as handle:
        for qid in sorted(valid, key=sort_key):
            handle.write(json.dumps(valid[qid], ensure_ascii=False) + "\n")

    if TODO_PATH.exists():
        with TODO_PATH.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
            fieldnames = list(rows[0].keys()) if rows else []
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for row in rows:
            qid = str(row.get("id") or "")
            if qid not in report:
                continue
            errors = report[qid]["errors"]
            if errors:
                row["status"] = "needs_review"
                row["evidence_status"] = "has_errors"
                row["notes"] = ";".join(errors)
            else:
                payload = valid[qid]
                row["status"] = "done"
                row["evidence_status"] = "checked"
                row["manual_guess"] = str(payload.get("manual_guess") or "")
                row["answer_path"] = f"agentic-rag/tmp/answers/per_question/{qid}.json"
                row["image_ids"] = json.dumps(payload.get("images") or [], ensure_ascii=False)
                row["notes"] = str(payload.get("notes") or "")
            row["updated_at"] = now
        with TODO_PATH.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    VALIDATION_PATH.write_text(
        json.dumps(
            {
                "valid_count": len(valid),
                "checked_count": len(report),
                "records": report,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"checked={len(report)} valid={len(valid)} csv={CSV_PATH} jsonl={JSONL_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
