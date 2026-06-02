#!/usr/bin/env python3
"""
扫描 InterX 包目录，报告依赖、入口文件、配置文件和项目结构。
输出为 Markdown 格式，可直接用于文档编写。

用法:
    python3 scan_deps.py <package_dir>
    python3 scan_deps.py /home/amax01/lingchen/YanD/InterX/process
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

# ── Python 标准库模块（3.11+）─────────────────────────────────────────────────
STDLIB_MODULES: set[str] = {
    "__future__", "abc", "aifc", "argparse", "array", "ast", "asynchat",
    "asyncio", "asyncore", "atexit", "audioop", "base64", "bdb", "binascii",
    "binhex", "bisect", "builtins", "bz2", "calendar", "cgi", "cgitb",
    "chunk", "cmath", "cmd", "code", "codecs", "codeop", "collections",
    "colorsys", "compileall", "concurrent", "configparser", "contextlib",
    "contextvars", "copy", "copyreg", "cProfile", "crypt", "csv", "ctypes",
    "curses", "dataclasses", "datetime", "dbm", "decimal", "difflib", "dis",
    "distutils", "doctest", "email", "encodings", "enum", "errno",
    "faulthandler", "fcntl", "filecmp", "fileinput", "fnmatch", "fractions",
    "ftplib", "functools", "gc", "getopt", "getpass", "gettext", "glob",
    "graphlib", "grp", "gzip", "hashlib", "heapq", "hmac", "html", "http",
    "idlelib", "imaplib", "imghdr", "imp", "importlib", "inspect", "io",
    "ipaddress", "itertools", "json", "keyword", "lib2to3", "linecache",
    "locale", "logging", "lzma", "mailbox", "mailcap", "marshal", "math",
    "mimetypes", "mmap", "modulefinder", "multiprocessing", "netrc", "nis",
    "nntplib", "numbers", "operator", "optparse", "os", "ossaudiodev",
    "pathlib", "pdb", "pickle", "pickletools", "pipes", "pkgutil", "platform",
    "plistlib", "poplib", "posix", "posixpath", "pprint", "profile",
    "pstats", "pty", "pwd", "py_compile", "pyclbr", "pydoc", "queue",
    "quopri", "random", "re", "readline", "reprlib", "resource", "rlcompleter",
    "runpy", "sched", "secrets", "select", "selectors", "shelve", "shlex",
    "shutil", "signal", "site", "smtpd", "smtplib", "sndhdr", "socket",
    "socketserver", "spwd", "sqlite3", "sre_compile", "sre_constants",
    "sre_parse", "ssl", "stat", "statistics", "string", "stringprep",
    "struct", "subprocess", "sunau", "symtable", "sys", "sysconfig",
    "syslog", "tabnanny", "tarfile", "telnetlib", "tempfile", "termios",
    "test", "textwrap", "threading", "time", "timeit", "tkinter", "token",
    "tokenize", "tomllib", "trace", "traceback", "tracemalloc", "tty",
    "turtle", "turtledemo", "types", "typing", "unicodedata", "unittest",
    "urllib", "uu", "uuid", "venv", "warnings", "wave", "weakref",
    "webbrowser", "winreg", "winsound", "wsgiref", "xdrlib", "xml",
    "xmlrpc", "zipapp", "zipfile", "zipimport", "zlib",
    "_thread", "typing_extensions",
}

# 跳过的目录
SKIP_DIRS = frozenset({
    ".agents", ".codex", ".git", "__pycache__", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", "node_modules", ".venv", "venv", "env", ".env",
    ".tox", ".nox", "htmlcov", "dist", "build",
})

ENTRY_PATTERNS = (
    "__main__.py", "app.py", "main.py", "server.py", "cli.py", "run.py",
)

CONFIG_PATTERNS = (
    ".env.example", ".env", "config.py", "settings.py", "config.yaml",
    "config.yml", "config.json", "settings.yaml", "settings.yml",
    "pyproject.toml", "setup.py", "setup.cfg",
)

REQ_PATTERNS = (
    "requirements.txt", "requirements-dev.txt", "requirements-test.txt",
    "requirements.in", "constraints.txt",
)


def _should_skip(path: Path) -> bool:
    """路径中包含需要跳过的目录时返回 True。"""
    return any(part in SKIP_DIRS or part.endswith(".egg-info")
               for part in path.parts)


def extract_imports(filepath: Path) -> list[str]:
    """提取 Python 文件中的顶层模块名。"""
    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError):
        return []
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                modules.append(node.module.split(".")[0])
    return modules


def classify_imports(modules: list[str]) -> tuple[set[str], set[str]]:
    """将导入分为（第三方, 本地）。"""
    third, local = set(), set()
    local_prefixes = ("kg", "retrieval", "process", "answer", "chat",
                      "web", "gateway", "agentic_rag", "interx",
                      "process_chunk")
    for m in modules:
        if m in STDLIB_MODULES:
            continue
        if m in local_prefixes or any(m.startswith(p + ".") for p in local_prefixes):
            local.add(m)
        else:
            third.add(m)
    return third, local


def tree_str(root: Path, prefix: str = "", depth: int = 0, max_depth: int = 3) -> list[str]:
    """ASCII 目录树，最大深度 3 层，跳过隐藏目录和 vendor 目录。"""
    if depth > max_depth:
        return []
    lines: list[str] = []
    try:
        entries = sorted(root.iterdir(), key=lambda e: (not e.is_dir(), e.name))
    except PermissionError:
        return []
    entries = [e for e in entries
               if e.name not in SKIP_DIRS and not e.name.endswith(".egg-info")]
    for i, entry in enumerate(entries):
        connector = "└── " if i == len(entries) - 1 else "├── "
        lines.append(f"{prefix}{connector}{entry.name}")
        if entry.is_dir():
            ext = "    " if i == len(entries) - 1 else "│   "
            lines.extend(tree_str(entry, prefix + ext, depth + 1, max_depth))
    return lines


def find_files(root: Path, patterns: tuple[str, ...]) -> list[Path]:
    """在 3 层深度内查找匹配模式的文件，跳过 vendor 目录。"""
    found = []
    for pattern in patterns:
        for p in root.rglob(pattern):
            if _should_skip(p.relative_to(root)):
                continue
            if len(p.relative_to(root).parts) <= 4:
                found.append(p)
    return sorted(set(found))


def parse_requirements_file(path: Path) -> list[str]:
    """从 requirements.txt 中提取包名。"""
    pkgs = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+)", line)
        if match:
            pkgs.append(match.group(1))
    return pkgs


def scan_package(root: Path) -> dict:
    """主扫描逻辑。"""
    result: dict = {
        "name": root.name,
        "path": str(root),
        "tree": [],
        "py_files": 0,
        "entry_points": [],
        "config_files": [],
        "requirements_files": [],
        "requirements_packages": [],
        "third_party_imports": [],
        "local_imports": [],
        "has_tests": False,
        "has_dockerfile": False,
        "has_docker_compose": False,
        "env_vars": [],
    }

    # 目录树
    result["tree"] = [root.name + "/"] + tree_str(root, depth=0, max_depth=3)

    # Python 文件（跳过 vendor 目录）
    py_files = [f for f in root.rglob("*.py") if not _should_skip(f.relative_to(root))]
    result["py_files"] = len(py_files)

    # 入口文件
    for name in ENTRY_PATTERNS:
        for f in root.rglob(name):
            rel = f.relative_to(root)
            if not _should_skip(rel):
                result["entry_points"].append(str(rel))

    # 配置文件
    for name in CONFIG_PATTERNS:
        for f in root.rglob(name):
            rel = f.relative_to(root)
            if not _should_skip(rel) and len(rel.parts) <= 3:
                result["config_files"].append(str(rel))

    # 依赖文件
    req_files = find_files(root, REQ_PATTERNS)
    result["requirements_files"] = [str(f.relative_to(root)) for f in req_files]
    all_pkgs: list[str] = []
    for rf in req_files:
        all_pkgs.extend(parse_requirements_file(rf))
    result["requirements_packages"] = sorted(set(all_pkgs))

    # 导入分析
    all_third: set[str] = set()
    all_local: set[str] = set()
    for pf in py_files:
        mods = extract_imports(pf)
        third, local = classify_imports(mods)
        all_third |= third
        all_local |= local
    result["third_party_imports"] = sorted(all_third)
    result["local_imports"] = sorted(all_local)

    # 测试
    result["has_tests"] = any(
        (root / d).is_dir() and any(
            t for t in (root / d).rglob("test_*.py")
            if not _should_skip(t.relative_to(root))
        )
        for d in ["tests", "test"]
    )

    # Docker
    result["has_dockerfile"] = (root / "Dockerfile").exists()
    result["has_docker_compose"] = any(root.glob("docker-compose*"))

    # .env.example 中的环境变量
    env_file = root / ".env.example"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                var = line.split("=", 1)[0].strip()
                result["env_vars"].append(var)

    return result


def format_report(data: dict) -> str:
    """将扫描结果格式化为 Markdown。"""
    lines: list[str] = []
    lines.append(f"# 依赖扫描报告：`{data['name']}`\n")
    lines.append(f"**路径**：`{data['path']}`\n")
    lines.append(f"**Python 文件数**：{data['py_files']}\n")

    # 入口文件
    lines.append("## 入口文件\n")
    if data["entry_points"]:
        for ep in data["entry_points"]:
            lines.append(f"- `{ep}`")
    else:
        lines.append("- _未检测到_")
    lines.append("")

    # 目录树
    lines.append("## 项目结构\n")
    lines.append("```")
    for line in data["tree"][:80]:
        lines.append(line)
    lines.append("```\n")

    # 依赖文件
    lines.append("## 依赖文件\n")
    if data["requirements_files"]:
        for rf in data["requirements_files"]:
            lines.append(f"- `{rf}`")
    else:
        lines.append("- _未找到_")
    lines.append("")

    # 依赖包（来自 requirements 文件）
    lines.append("## 依赖包（来自 requirements 文件）\n")
    if data["requirements_packages"]:
        for pkg in data["requirements_packages"]:
            lines.append(f"- `{pkg}`")
    else:
        lines.append("- _未检测到_")
    lines.append("")

    # 第三方导入
    lines.append("## 第三方导入（来自源码分析）\n")
    if data["third_party_imports"]:
        for pkg in data["third_party_imports"]:
            lines.append(f"- `{pkg}`")
    else:
        lines.append("- _未检测到_")
    lines.append("")

    # 本地导入
    lines.append("## 本地 / 内部导入\n")
    if data["local_imports"]:
        for pkg in data["local_imports"]:
            lines.append(f"- `{pkg}`")
    else:
        lines.append("- _未检测到_")
    lines.append("")

    # 配置文件
    lines.append("## 配置文件\n")
    if data["config_files"]:
        for cf in data["config_files"]:
            lines.append(f"- `{cf}`")
    else:
        lines.append("- _未找到_")
    lines.append("")

    # 环境变量
    lines.append("## 环境变量（来自 .env.example）\n")
    if data["env_vars"]:
        for v in data["env_vars"]:
            lines.append(f"- `{v}`")
    else:
        lines.append("- _未找到 .env.example_")
    lines.append("")

    # 标志
    lines.append("## 特征标志\n")
    lines.append(f"- 有测试：**{'是' if data['has_tests'] else '否'}**")
    lines.append(f"- 有 Dockerfile：**{'是' if data['has_dockerfile'] else '否'}**")
    lines.append(f"- 有 docker-compose：**{'是' if data['has_docker_compose'] else '否'}**")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="扫描 InterX 包目录，报告依赖和项目结构。"
    )
    parser.add_argument("path", type=str, help="要扫描的包目录路径")
    parser.add_argument("--json", action="store_true",
                        help="输出原始 JSON 而非 Markdown")
    args = parser.parse_args()

    root = Path(args.path).resolve()
    if not root.is_dir():
        print(f"错误：{root} 不是目录", file=sys.stderr)
        sys.exit(1)

    data = scan_package(root)

    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(format_report(data))


if __name__ == "__main__":
    main()
