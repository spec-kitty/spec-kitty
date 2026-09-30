"""Architectural gate: the run-index filename literal is single-homed in the port.

Mission runindex-feature-runs-port (#5390 / #5389, Stijn ratchet directive
2026-09-30 — *any gate you add closes with an EMPTY allowlist*).

Invariant: the string literal ``feature-runs.json`` appears as a real (non-docstring)
string constant in EXACTLY ONE module — ``src/runtime/next/run_index.py`` (the
RunIndex port, sole reader/writer of the index). Every other module composes the
name from :data:`run_index.FEATURE_RUNS_FILENAME`. This keeps the index's
filename and open sites single-homed so a second, unlocked/absolute-path writer
cannot silently reappear.

Comments and docstrings are excluded (they legitimately name the file when
explaining it); the gate scans code string constants only. The allowlist is
EMPTY — no module other than the port may carry the literal — and the gate is
non-vacuous: a floor asserts the port DOES define it, and a self-mutation test
proves the detector fails when the literal is injected elsewhere.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.architectural]

_LITERAL = "feature-runs.json"
_PORT_MODULE = Path("src/runtime/next/run_index.py")


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists() and (parent / "src").is_dir():
            return parent
    raise RuntimeError("could not locate repo root")


def _docstring_node_ids(tree: ast.AST) -> set[int]:
    """Ids of the Constant nodes that are module/class/function docstrings."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
                ids.add(id(body[0].value))
    return ids


def _module_has_literal_constant(source: str, literal: str) -> bool:
    """True when ``literal`` appears in a non-docstring string constant of ``source``.

    Covers plain strings AND f-string (``JoinedStr``) literal parts; ignores
    comments (absent from the AST) and docstrings (excluded explicitly).
    """
    tree = ast.parse(source)
    docstrings = _docstring_node_ids(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in docstrings:
                continue
            if literal in node.value:
                return True
    return False


def _modules_carrying_literal() -> set[Path]:
    root = _repo_root()
    src = root / "src"
    carriers: set[Path] = set()
    for path in src.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except OSError:  # pragma: no cover - defensive
            continue
        if _LITERAL not in source:
            continue
        if _module_has_literal_constant(source, _LITERAL):
            carriers.add(path.relative_to(root))
    return carriers


def test_run_index_literal_is_single_homed_in_the_port() -> None:
    """EMPTY allowlist: only the RunIndex port module carries the filename literal."""
    carriers = _modules_carrying_literal()
    assert carriers == {_PORT_MODULE}, (
        "the run-index filename literal must live only in the RunIndex port "
        f"({_PORT_MODULE}); found in: {sorted(str(p) for p in carriers)}. "
        "Import run_index.FEATURE_RUNS_FILENAME instead of duplicating the literal."
    )


def test_gate_floor_the_port_actually_defines_the_literal() -> None:
    """Non-vacuity floor: the port really does define the constant."""
    source = (_repo_root() / _PORT_MODULE).read_text(encoding="utf-8")
    assert _module_has_literal_constant(source, _LITERAL)


def test_gate_is_non_vacuous_self_mutation() -> None:
    """The detector flags an injected literal and ignores a docstring-only mention."""
    violating = 'X = "feature-runs.json"\n'
    assert _module_has_literal_constant(violating, _LITERAL) is True

    docstring_only = '"""mentions feature-runs.json in prose."""\nX = 1\n'
    assert _module_has_literal_constant(docstring_only, _LITERAL) is False

    fstring_violation = 'k = "a"\nX = f"{k} feature-runs.json"\n'
    assert _module_has_literal_constant(fstring_violation, _LITERAL) is True
