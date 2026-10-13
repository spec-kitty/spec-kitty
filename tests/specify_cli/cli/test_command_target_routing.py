"""WP02 routing witness (#6142, Increment 1).

`mission_record_analysis` (record-analysis) resolves its declaration-first target branch
through the single command-entry producer :func:`resolve_command_repo_target`, not through
the ambient-biased `get_feature_target_branch` fallback. These are source-level assertions
(the ratchet idiom): they pin that the ambient-fallback seed is GONE at the routed site and
the target now comes from the entry.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_RECORD_ANALYSIS = _REPO_ROOT / "src" / "specify_cli" / "cli" / "commands" / "agent" / "mission_record_analysis.py"


def _module_source() -> str:
    return _RECORD_ANALYSIS.read_text(encoding="utf-8")


def test_record_analysis_imports_the_declaration_first_entry() -> None:
    source = _module_source()
    assert "from specify_cli.core.command_target import resolve_command_repo_target" in source


def test_record_analysis_no_longer_uses_the_ambient_fallback_seed() -> None:
    """The ambient-biased ``get_feature_target_branch`` seed is gone at this site.

    Code-token check (ignores docstrings/comments): no ``get_feature_target_branch``
    call remains, and the entry is called for the ``target_branch``.
    """
    tree = ast.parse(_module_source(), filename=str(_RECORD_ANALYSIS))
    called_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                called_names.add(func.id)
            elif isinstance(func, ast.Attribute):
                called_names.add(func.attr)
    assert "get_feature_target_branch" not in called_names, (
        "record-analysis still calls the ambient-biased get_feature_target_branch; route its target_branch through resolve_command_repo_target instead"
    )
    assert "resolve_command_repo_target" in called_names, "record-analysis no longer produces its target_branch via the declaration-first entry"


def test_record_analysis_does_not_import_get_feature_target_branch() -> None:
    assert "get_feature_target_branch" not in _module_source(), (
        "the get_feature_target_branch import/reference should be fully removed from the routed site (no dangling ambient-fallback seed)"
    )
