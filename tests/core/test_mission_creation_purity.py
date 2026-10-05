"""Purity gate for ``specify_cli.core.mission_creation_decisions``.

The decisions module is the only pure module of the mission-creation family.
This AST scan is an allow-list: any runtime import outside ``_ALLOWED_IMPORTS``,
at module scope or inside a function body, is a finding, as is a bare ``open`` /
``__import__`` call, a ``pathlib.Path`` I/O method, a clock or a ULID. Imports
under ``if TYPE_CHECKING:`` are allowed (type-only). Planted sources prove the
scan is not vacuous.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import specify_cli.core.mission_creation_decisions as decisions

pytestmark = [pytest.mark.fast, pytest.mark.unit]

#: Runtime imports the pure module may make: module -> allowed imported names
#: (``None`` allows any name from a standard-library module).
_ALLOWED_IMPORTS: dict[str, frozenset[str] | None] = {
    "__future__": None,
    "re": None,
    "collections.abc": None,
    "dataclasses": None,
    "enum": None,
    "typing": None,
    "mission_runtime": frozenset({"MissionTopology"}),
}
#: ``pathlib.Path`` I/O and filesystem-probe methods, plus ``Path.open``.
_BANNED_ATTRIBUTES = frozenset(
    {
        "read_text",
        "write_text",
        "exists",
        "iterdir",
        "glob",
        "rglob",
        "mkdir",
        "unlink",
        "open",
        "is_file",
        "is_dir",
        "stat",
        "resolve",
        "read_bytes",
        "write_bytes",
        "touch",
        "rename",
        "rmdir",
    }
)
#: ``datetime.now`` / ``datetime.utcnow`` and friends.
_BANNED_CALLS = frozenset({"now", "utcnow", "today"})
#: Builtins that reach the filesystem or the import system by name.
_BANNED_BUILTINS = frozenset({"open", "__import__"})


def _import_findings(node: ast.Import | ast.ImportFrom) -> list[str]:
    """Findings for one runtime import statement that is not on the allow-list."""
    if isinstance(node, ast.Import):
        return [f"{node.lineno}: import {alias.name}" for alias in node.names if alias.name not in _ALLOWED_IMPORTS or _ALLOWED_IMPORTS[alias.name] is not None]
    module = node.module or ""
    if node.level == 0 and module in _ALLOWED_IMPORTS:
        allowed = _ALLOWED_IMPORTS[module]
        if allowed is None or all(alias.name in allowed for alias in node.names):
            return []
    return [f"{node.lineno}: from {'.' * node.level}{module} import ..."]


def _type_checking_nodes(tree: ast.Module) -> set[int]:
    """ids of every node under an ``if TYPE_CHECKING:`` block."""
    guarded: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
            for child in node.body:
                guarded.update(id(sub) for sub in ast.walk(child))
    return guarded


def purity_findings(source: str) -> list[str]:
    """Every impure construct in *source*, as ``line: description``."""
    tree = ast.parse(source)
    guarded = _type_checking_nodes(tree)
    findings: list[str] = []
    for node in ast.walk(tree):
        if id(node) in guarded:
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            findings.extend(_import_findings(node))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _BANNED_BUILTINS:
            findings.append(f"{node.lineno}: {node.func.id}()")
        elif isinstance(node, ast.Attribute) and node.attr in _BANNED_ATTRIBUTES:
            findings.append(f"{node.lineno}: .{node.attr}")
        elif isinstance(node, ast.Attribute) and node.attr in _BANNED_CALLS:
            findings.append(f"{node.lineno}: .{node.attr}()")
    return sorted(findings, key=lambda finding: int(finding.split(":", 1)[0]))


def test_decisions_module_is_pure() -> None:
    source = Path(decisions.__file__).read_text(encoding="utf-8")
    assert purity_findings(source) == []


def test_planted_impurity_is_flagged() -> None:
    """Positive control: the scan is not vacuous, for imports (module scope and function body) and for calls."""
    planted = (
        "import subprocess\n"
        "import logging\n"
        "from pathlib import Path\n"
        'Path("x").read_text()\n'
        "def read(p):\n"
        "    import shutil\n"
        "    return open(p).read()\n"
        "def probe(p):\n"
        "    return p.is_file()\n"
    )
    assert purity_findings(planted) == [
        "1: import subprocess",
        "2: import logging",
        "3: from pathlib import ...",
        "4: .read_text",
        "6: import shutil",
        "7: open()",
        "9: .is_file",
    ]


def test_planted_banned_from_imports_and_clock_are_flagged() -> None:
    planted = (
        "from specify_cli.git.commit_helpers import SafeCommitError\n"
        "from kernel.clock import now_utc_iso\n"
        "from specify_cli.core import mission_creation as _mc\n"
        "from mission_runtime import placement_seam\n"
        "import datetime\n"
        "datetime.datetime.now()\n"
    )
    assert purity_findings(planted) == [
        "1: from specify_cli.git.commit_helpers import ...",
        "2: from kernel.clock import ...",
        "3: from specify_cli.core import ...",
        "4: from mission_runtime import ...",
        "5: import datetime",
        "6: .now()",
    ]


def test_type_checking_imports_are_allowed() -> None:
    planted = "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from specify_cli.git.protection_policy import ProtectionPolicy\n"
    assert purity_findings(planted) == []
