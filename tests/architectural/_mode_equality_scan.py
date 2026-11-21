"""Scan scope and AST detector for the mode-equality authority gate (#4927, #4810).

Not a test module (it mirrors the underscore-prefixed helpers beside it, such as
``_no_follow_symlinks_apply_scan.py``), so pytest never collects it.

**The defect class.** A planner, or a recheck, compares an *observed* node's
mode with a *planned* POSIX mode exactly. On Windows (NTFS) a directory always
reads ``0o777`` and a file ``0o666``/``0o444``, so such a comparison plans a
``chmod`` the host can never apply, or refuses a state the host cannot change.
That is how #4776, #4777 and #4927 happened, each time in a path the previous
point fix had not reached.

**The authority.** ``specify_cli.tool_surface.operations`` owns the one
host-aware equivalence: ``modes_equivalent``, ``mode_equivalent``,
``state_equivalent`` and ``effect_action``. Every other module in the scan
roots must decide mode equality through it.

**What the detector reports.** One finding per AST node, of three shapes:

* ``P1`` -- an ``==``/``!=`` comparison whose two sides both carry a mode
  (a ``.mode`` or ``.st_mode`` attribute, or a ``stat.S_IMODE(...)`` call);
* ``P2`` -- an ``==``/``!=`` comparison where exactly one side *is* a planned
  stamp (an ``<x>.after`` attribute, or a name ``after``/``planned``): a whole
  node state compared with a planned one carries the mode with it;
* ``P3`` -- a ``replace(..., mode=<x>.after.mode)`` call: a planned mode
  stamped into an observation that is then compared exactly.

A comparison between two observations of the same node (a concurrency guard)
or between two planned states (a conflict check) is legitimately exact on every
host. Such sites are listed, with their rationale, in the gate's adjudicated
table; they are permanent classifications, not debt to drain (ADR
``2026-09-30-1``), so the gate needs no ``_baselines.yaml`` entry.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
SCAN_ROOTS: tuple[Path, ...] = (
    SRC_ROOT / "specify_cli" / "skills",
    SRC_ROOT / "specify_cli" / "tool_surface",
    SRC_ROOT / "specify_cli" / "runtime",
)

#: The authority module and the functions in it that may compare modes.
AUTHORITY_FILE = "src/specify_cli/tool_surface/operations.py"
AUTHORITY_FUNCTIONS = frozenset({"modes_equivalent", "mode_equivalent", "state_equivalent", "effect_action"})

_MODE_ATTRS = frozenset({"mode", "st_mode"})
_PLANNED_NAMES = frozenset({"after", "planned"})
_EQUALITY_OPS = (ast.Eq, ast.NotEq)


@dataclass(frozen=True, order=True)
class Finding:
    """One reported comparison: where it is and which shape it has."""

    path: str
    qualname: str
    pattern: str
    lineno: int


def iter_python_files(roots: tuple[Path, ...] = SCAN_ROOTS) -> list[Path]:
    """Every ``.py`` file under *roots*, ``__pycache__`` excluded."""
    files: list[Path] = []
    for root in roots:
        files.extend(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)
    return sorted(files)


def relpath(path: Path) -> str:
    """POSIX-style repository-relative path, the key the adjudicated table uses."""
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def _carries_mode(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Attribute) and child.attr in _MODE_ATTRS:
            return True
        if isinstance(child, ast.Call):
            func = child.func
            name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""
            if name == "S_IMODE":
                return True
    return False


def _is_planned_stamp(node: ast.AST) -> bool:
    if isinstance(node, ast.Attribute):
        return node.attr == "after"
    return isinstance(node, ast.Name) and node.id in _PLANNED_NAMES


def _is_planned_mode(node: ast.AST) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "mode" and _is_planned_stamp(node.value)


def _compare_patterns(node: ast.Compare) -> list[str]:
    if not any(isinstance(op, _EQUALITY_OPS) for op in node.ops):
        return []
    operands = [node.left, *node.comparators]
    patterns = []
    if sum(_carries_mode(operand) for operand in operands) >= 2:
        patterns.append("P1")
    if sum(_is_planned_stamp(operand) for operand in operands) == 1:
        patterns.append("P2")
    return patterns


def _call_patterns(node: ast.Call) -> list[str]:
    func = node.func
    name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""
    if name == "replace" and any(kw.arg == "mode" and _is_planned_mode(kw.value) for kw in node.keywords):
        return ["P3"]
    return []


class _Detector(ast.NodeVisitor):
    def __init__(self, path: str) -> None:
        self.path = path
        self.scope: list[str] = []
        self.findings: list[Finding] = []

    def _visit_scope(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_FunctionDef = _visit_scope
    visit_AsyncFunctionDef = _visit_scope
    visit_ClassDef = _visit_scope

    @property
    def qualname(self) -> str:
        return ".".join(self.scope) or "<module>"

    def _report(self, node: ast.expr, patterns: list[str]) -> None:
        if self.path == AUTHORITY_FILE and self.scope and self.scope[-1] in AUTHORITY_FUNCTIONS:
            return
        self.findings.extend(Finding(self.path, self.qualname, pattern, node.lineno) for pattern in patterns)

    def visit_Compare(self, node: ast.Compare) -> None:
        self._report(node, _compare_patterns(node))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        self._report(node, _call_patterns(node))
        self.generic_visit(node)


def scan_source(source: str, path: str) -> list[Finding]:
    """Findings for one module's *source*, keyed under the repository-relative *path*."""
    detector = _Detector(path)
    detector.visit(ast.parse(source, filename=path))
    return sorted(detector.findings)


def scan_tree(roots: tuple[Path, ...] = SCAN_ROOTS) -> tuple[list[Finding], int, int]:
    """``(findings, files scanned, comparisons visited)`` over every file under *roots*."""
    findings: list[Finding] = []
    comparisons = 0
    files = iter_python_files(roots)
    for path in files:
        source = path.read_text(encoding="utf-8")
        comparisons += sum(isinstance(node, ast.Compare) for node in ast.walk(ast.parse(source)))
        findings.extend(scan_source(source, relpath(path)))
    return sorted(findings), len(files), comparisons
