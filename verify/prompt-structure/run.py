#!/usr/bin/env python3
"""Prompt 结构验证：读取 data/checklist.json，输出 results/metrics.json + conclusion.md"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

ANSWER_DIR = ROOT / "answer" / "src" / "answer" / "prompts"
CHAT_DIR = ROOT / "chat" / "src" / "chat" / "prompts"
DIR_MAP = {"answer/": ANSWER_DIR, "chat/": CHAT_DIR}


def run() -> dict:
    checklist = json.loads((HERE / "data" / "checklist.json").read_text())
    results = []

    print("Prompt 结构验证\n")

    # 检查 prompt 文件
    for rel_path, required_tags in checklist["prompt_files"].items():
        prefix = rel_path.split("/")[0] + "/"
        file_path = DIR_MAP.get(prefix, ANSWER_DIR) / rel_path.split("/", 1)[1]

        if not file_path.exists():
            print(f"  ❌ {rel_path}: 文件不存在")
            results.append({"file": rel_path, "all_ok": False})
            continue

        content = file_path.read_text(encoding="utf-8").strip()
        expected_vars = checklist.get("template_vars", {}).get(rel_path, [])

        missing_tags = [t for t in required_tags if t not in content]
        missing_vars = [v for v in expected_vars if v not in content]
        unclosed = [t for t in required_tags if t.startswith("<") and not t.startswith("</")
                    and t.replace("<", "</", 1) not in content]

        ok = not missing_tags and not missing_vars and not unclosed
        mark = "✅" if ok else "❌"
        issues = []
        if missing_tags: issues.append(f"缺标签 {missing_tags}")
        if missing_vars: issues.append(f"缺变量 {missing_vars}")
        if unclosed: issues.append(f"未闭合 {unclosed}")
        print(f"  {mark} {rel_path:<35} {'OK' if ok else '; '.join(issues)}")
        results.append({"file": rel_path, "all_ok": ok, "missing_tags": missing_tags,
                        "missing_vars": missing_vars, "unclosed": unclosed})

    # 检查代码中的 XML 标签
    for cc in checklist["code_checks"]:
        fpath = ROOT / cc["file"].replace("answer/", "answer/src/answer/").replace("kg/", "kg/src/kg/")
        if not fpath.exists():
            continue
        content = fpath.read_text()
        checks = {tag: tag in content for tag in cc["tags"]}
        ok = all(checks.values())
        mark = "✅" if ok else "❌"
        if not ok:
            missing = [k for k, v in checks.items() if not v]
            print(f"  {mark} {cc['file']}: 缺少 {missing}")
        else:
            print(f"  {mark} {cc['file']}: 全部就位")
        results.append({"file": cc["file"], "all_ok": ok, "checks": checks})

    total = len(results)
    passed = sum(1 for r in results if r.get("all_ok"))
    summary = {"total": total, "passed": passed, "failed": total - passed, "all_pass": passed == total, "results": results}

    (HERE / "results" / "metrics.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\n{passed}/{total} 通过")
    print(f"结果已写入 results/")
    return summary


if __name__ == "__main__":
    run()
