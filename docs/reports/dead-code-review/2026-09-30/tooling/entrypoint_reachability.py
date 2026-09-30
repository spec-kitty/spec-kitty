"""List src/ modules that no import path from the CLI entry point can reach.

Roots: ``specify_cli`` (the ``spec-kitty = specify_cli:main`` script), every
auto-discovered ``upgrade.migrations.m_*`` module, the auto-registered
``cli.commands._*_doctor`` siblings and the ``doctrine`` shim. Edges are
static imports (including function-local ones) plus dotted module names that
appear in string literals (importlib / patch targets). Run from the repo root.

Unlike ``tests/architectural/test_no_dead_modules.py`` this walk does not
count a package's own ``__init__`` as a caller, so it finds packages that are
only alive through self-re-export. Data-only packages (``charter.activation.packs``,
``specify_cli.skills.data``) show up too and are false positives.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

SRC = Path("src")
MODULE_STRING = re.compile(r"\b((?:specify_cli|charter|glossary|kernel|mission_runtime|runtime)(?:\.[a-z_0-9]+)+)\b")
DOCTOR_SIBLING = re.compile(r"cli\.commands\._[a-z_]+_doctor$")


def _modules() -> dict[str, Path]:
    found: dict[str, Path] = {}
    for path in SRC.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        dotted = ".".join(path.relative_to(SRC).with_suffix("").parts)
        found[dotted.removesuffix(".__init__")] = path
    return found


def _resolve(current: str, is_package: bool, level: int, module: str | None) -> str:
    if level == 0:
        return module or ""
    parts = current.split(".") if is_package else current.split(".")[:-1]
    parts = parts[: len(parts) - (level - 1)]
    return ".".join(parts + ([module] if module else []))


def _edges(modules: dict[str, Path]) -> dict[str, set[str]]:
    edges: dict[str, set[str]] = {name: set() for name in modules}
    for name, path in modules.items():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        is_package = path.name == "__init__.py"
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                edges[name].update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                base = _resolve(name, is_package, node.level, node.module)
                edges[name].add(base)
                edges[name].update(f"{base}.{alias.name}" for alias in node.names)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                edges[name].update(MODULE_STRING.findall(node.value))
    return edges


def _prefixes(targets: set[str], modules: dict[str, Path]) -> set[str]:
    out: set[str] = set()
    for target in targets:
        parts = target.split(".")
        out.update(".".join(parts[:i]) for i in range(1, len(parts) + 1) if ".".join(parts[:i]) in modules)
    return out


def main() -> None:
    modules = _modules()
    edges = _edges(modules)
    roots = {"specify_cli", "doctrine"}
    roots |= {m for m in modules if ".upgrade.migrations.m_" in m or DOCTOR_SIBLING.search(m)}
    seen: set[str] = set()
    stack = [r for r in roots if r in modules]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend(_prefixes(edges[current], modules) - seen)
    for name in sorted(set(modules) - seen):
        lines = len(modules[name].read_text(encoding="utf-8").splitlines())
        print(f"{name}\t{lines}")


if __name__ == "__main__":
    main()
