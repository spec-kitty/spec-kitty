"""Tier vulture's unused-symbol candidates by where their name is referenced.

Run from the repository root after producing the vulture listing::

    vulture src --min-confidence 60 > "$DEADCODE_WORKDIR/vulture_src.txt"
    python docs/reports/dead-code-review/2026-09-30/tooling/candidate_tiers.py

Writes ``cands.json`` into ``$DEADCODE_WORKDIR`` (default: the current directory).
Tiers: FRAMEWORK (Typer/pydantic/migration-registered or a dunder/stdlib hook),
T1_unreferenced (token appears only in its own module), T2_test_only (only
tests/ mention it), T3_name_collides (token appears elsewhere, needs reading).
Variables are skipped: vulture's variable hits are dominated by model fields.
"""

from __future__ import annotations

import ast
import collections
import json
import os
import re
import subprocess
from pathlib import Path

WORKDIR = Path(os.environ.get("DEADCODE_WORKDIR", "."))
CODE_AREAS = ["src", "tests", "packs", "scripts", ".github", "pyproject.toml", ".kittify", "Makefile", "kitty-ops"]
TEXT_SUFFIXES = (".py", ".yaml", ".yml", ".toml", ".md", ".json", ".j2", ".jinja", ".txt", ".cfg", ".ini", ".sh", ".html", ".js")
TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
VULTURE_LINE = re.compile(r"^(src/[^:]+):(\d+): unused (\w+) '([^']+)' \((\d+)% confidence")
FRAMEWORK_DECORATOR = re.compile(r"(\.command$|\.callback$|^MigrationRegistry\.register$|validator$|^model_serializer$|^pytest\.fixture)")
STDLIB_HOOKS = {"handle_starttag", "redirect_request", "model_post_init", "row_factory", "emit", "log_message"}


def _token_index() -> dict[str, collections.Counter[str]]:
    listed = subprocess.run(["git", "ls-files", *CODE_AREAS], capture_output=True, text=True, check=True)
    index: dict[str, collections.Counter[str]] = collections.defaultdict(collections.Counter)
    for name in listed.stdout.split():
        if not (name.endswith(TEXT_SUFFIXES) or name == "Makefile"):
            continue
        text = Path(name).read_text(encoding="utf-8", errors="ignore")
        for token in TOKEN.findall(text):
            index[token][name] += 1
    return index


def _area(path: str) -> str:
    if path.startswith("src/"):
        return "src"
    if path.startswith("tests/"):
        return "tests"
    return "other"


def _decorators(path: str, line: int, name: str) -> list[str]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) or node.name != name:
            continue
        if abs(node.lineno - line) <= 6 or any(d.lineno == line for d in node.decorator_list):
            return [ast.unparse(d.func if isinstance(d, ast.Call) else d) for d in node.decorator_list]
    return []


def _tier(name: str, decorators: list[str], src_other: int, tests: int, other: int) -> str:
    if any(FRAMEWORK_DECORATOR.search(d) for d in decorators):
        return "FRAMEWORK"
    if name in STDLIB_HOOKS or (name.startswith("__") and name.endswith("__")) or name.startswith("visit_"):
        return "FRAMEWORK"
    if src_other == 0 and other == 0:
        return "T1_unreferenced" if tests == 0 else "T2_test_only"
    return "T3_name_collides"


def main() -> None:
    index = _token_index()
    rows: list[dict[str, object]] = []
    with (WORKDIR / "vulture_src.txt").open(encoding="utf-8") as listing:
        for raw in listing:
            match = VULTURE_LINE.match(raw)
            if not match or match[3] == "variable":
                continue
            path, line, kind, name = match[1], int(match[2]), match[3], match[4]
            refs = index.get(name, collections.Counter())
            src_other = sum(v for k, v in refs.items() if _area(k) == "src" and k != path)
            tests = sum(v for k, v in refs.items() if _area(k) == "tests")
            other = sum(v for k, v in refs.items() if _area(k) == "other")
            decorators = _decorators(path, line, name)
            rows.append(
                {
                    "file": path,
                    "line": line,
                    "kind": kind,
                    "name": name,
                    "confidence": int(match[5]),
                    "src_other": src_other,
                    "tests": tests,
                    "other": other,
                    "decorators": decorators,
                    "tier": _tier(name, decorators, src_other, tests, other),
                }
            )
    (WORKDIR / "cands.json").write_text(json.dumps(rows, indent=0), encoding="utf-8")
    print(collections.Counter((r["tier"], r["kind"]) for r in rows))


if __name__ == "__main__":
    main()
