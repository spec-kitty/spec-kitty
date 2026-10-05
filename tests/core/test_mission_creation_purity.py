"""Purity gate for ``specify_cli.core.mission_creation_decisions``.

The decisions module is the only pure module of the mission-creation family.
This AST scan fails on any runtime import of an I/O-bearing
module, or use of a ``pathlib.Path`` I/O method, clock or ULID. Imports under
``if TYPE_CHECKING:`` are allowed (type-only). A planted source proves the scan
is not vacuous.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import specify_cli.core.mission_creation_decisions as decisions

pytestmark = [pytest.mark.fast, pytest.mark.unit]

#: Modules (and their submodules) the pure module must never import at runtime.
_BANNED_MODULES = (
    "subprocess",
    "os",
    "shutil",
    "time",
    "ulid",
    "kernel.clock",
    "kernel.git",
    "specify_cli.core.git_ops",
    "specify_cli.git",
)
#: ``pathlib.Path`` I/O methods.
_BANNED_ATTRIBUTES = frozenset({"read_text", "write_text", "exists", "iterdir", "glob", "rglob", "mkdir", "unlink", "open"})
#: ``datetime.now`` / ``datetime.utcnow`` and friends.
_BANNED_CALLS = frozenset({"now", "utcnow", "today"})


def _is_banned(module: str) -> bool:
    return any(module == banned or module.startswith(f"{banned}.") for banned in _BANNED_MODULES)


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
        if isinstance(node, ast.Import):
            findings.extend(f"{node.lineno}: import {alias.name}" for alias in node.names if _is_banned(alias.name))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if _is_banned(module):
                findings.append(f"{node.lineno}: from {module} import ...")
        elif isinstance(node, ast.Attribute) and node.attr in _BANNED_ATTRIBUTES:
            findings.append(f"{node.lineno}: .{node.attr}")
        elif isinstance(node, ast.Attribute) and node.attr in _BANNED_CALLS:
            findings.append(f"{node.lineno}: .{node.attr}()")
    return findings


def test_decisions_module_is_pure() -> None:
    source = Path(decisions.__file__).read_text(encoding="utf-8")
    assert purity_findings(source) == []


def test_planted_impurity_is_flagged() -> None:
    """Positive control: the scan is not vacuous."""
    planted = 'import subprocess\nfrom pathlib import Path\nPath("x").read_text()\n'
    assert purity_findings(planted) == ["1: import subprocess", "3: .read_text"]


def test_planted_banned_from_imports_and_clock_are_flagged() -> None:
    planted = "from specify_cli.git.commit_helpers import SafeCommitError\nfrom kernel.clock import now_utc_iso\nimport datetime\ndatetime.datetime.now()\n"
    assert purity_findings(planted) == [
        "1: from specify_cli.git.commit_helpers import ...",
        "2: from kernel.clock import ...",
        "4: .now()",
    ]


def test_type_checking_imports_are_allowed() -> None:
    planted = "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from specify_cli.git.protection_policy import ProtectionPolicy\n"
    assert purity_findings(planted) == []


def test_decisions_module_does_not_import_the_adapter() -> None:
    """No import cycle: the pure module never imports ``mission_creation``."""
    tree = ast.parse(Path(decisions.__file__).read_text(encoding="utf-8"))
    imported = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert "specify_cli.core.mission_creation" not in imported
