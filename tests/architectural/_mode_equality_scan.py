"""Scan scope and AST detector for the mode-equality authority gate (#4927, #4810).

Not a test module (it mirrors the underscore-prefixed helpers beside it, such as
``_no_follow_symlinks_apply_scan.py``), so pytest never collects it.

**The defect class.** A planner, or a recheck, compares an *observed* node's
mode with a *planned* POSIX mode exactly. On Windows (NTFS) a directory always
reads ``0o777`` and a file ``0o666``/``0o444``, so such a comparison plans a
``chmod`` the host can never apply, or refuses a state the host cannot change.
That is how #4776, #4777 and #4927 happened, each time in a path the previous
point fix had not reached.

**The authority.** ``kernel.file_modes.modes_equivalent`` owns the one
host-aware rule, at the kernel floor so the charter layer can use it too;
``specify_cli.tool_surface.operations`` adds its ``FileState`` forms
(``mode_equivalent``, ``state_equivalent``, ``expected_with_mode``) and
``effect_action``. Every other module in the scan roots must decide mode
equality through them.

**What the detector reports.** One finding per AST node, of four shapes:

* ``P1`` -- an ``==``/``!=``/``in``/``not in`` comparison whose two sides both carry a mode
  (a ``.mode`` or ``.st_mode`` attribute, or a ``stat.S_IMODE(...)`` call);
* ``P2`` -- such a comparison where exactly one side *is* a planned stamp (an
  ``<x>.after`` attribute, or a name ``after``/``planned``), or a tuple, list
  or set holding one: a whole node state compared with a planned one carries
  the mode with it;
* ``P3`` -- a ``replace(..., mode=<x>.after.mode)`` call, under any name that
  ``from dataclasses import replace as <name>`` binds: a planned mode stamped
  into an observation that is then compared exactly;
* ``P4`` -- such a comparison of a planned mode (``<x>.after.mode``, or the
  ``.mode`` of a name ``after``/``planned``/``prepared``/``desired``/``expected``)
  with an operand the detector cannot see a mode in, such as a local variable
  holding ``stat.S_IMODE(...)`` (the original ``installer.py`` shape).

A mode is carried by a ``.mode``/``.st_mode`` attribute, a ``stat.S_IMODE(...)``
call, a ``getattr(x, "mode")`` call, or a name that is ``mode`` or ends in
``_mode``.

Each finding records the comparison's source text (``ast.unparse``), so an
adjudication exempts exactly one comparison, never a whole function.

**Out of scope (known evasions).** The detector is syntactic. It does not
follow:

* a planned mode held in a name that is not a planned name or ``*_mode``
  (``cur != target.mode``), or reached through a dictionary lookup;
* a comparison against a literal (``S_IMODE(st) != 0o644``), an ordering
  comparison (``<``, ``>``), arithmetic or a bitwise test (``a.mode ^ b.mode``);
* ``operator.eq``/``operator.ne``, a custom ``__eq__``, a ``match`` statement
  or a ``functools`` partial;
* a helper defined outside the scan roots.

An adjudication also exempts a byte-identical duplicate of its comparison in
the same scope. Review owns these residuals; a new helper that compares modes
belongs in ``kernel/file_modes.py`` or ``tool_surface/operations.py``.

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
    # The one charter module that writes files and checks their mode; the rest
    # of charter/activation compares configuration values, not node states.
    SRC_ROOT / "charter" / "activation" / "charter_yaml_io.py",
)

#: The authority modules and the functions in them that may compare modes.
AUTHORITY_FILE = "src/specify_cli/tool_surface/operations.py"
AUTHORITY: dict[str, frozenset[str]] = {
    AUTHORITY_FILE: frozenset({"mode_equivalent", "state_equivalent", "expected_with_mode", "effect_action"}),
    "src/kernel/file_modes.py": frozenset({"modes_equivalent"}),
}

_MODE_ATTRS = frozenset({"mode", "st_mode"})
#: A whole planned state (P2). Kept narrow: ``expected``/``desired`` also name
#: planned bytes, sets and paths, which are not node states.
_PLANNED_NAMES = frozenset({"after", "planned"})
#: The holder of a planned mode (P4): ``<holder>.mode``. Wider, since the
#: ``.mode`` attribute itself restricts it to modes.
_PLANNED_MODE_HOLDERS = _PLANNED_NAMES | {"prepared", "desired", "expected"}
_EQUALITY_OPS = (ast.Eq, ast.NotEq, ast.In, ast.NotIn)


@dataclass(frozen=True, order=True)
class Finding:
    """One reported comparison: where it is and which shape it has."""

    path: str
    qualname: str
    pattern: str
    lineno: int
    text: str

    @property
    def key(self) -> tuple[str, str, str, str]:
        """The adjudication key: one exact comparison in one scope."""
        return (self.path, self.qualname, self.pattern, self.text)


def iter_python_files(roots: tuple[Path, ...] = SCAN_ROOTS) -> list[Path]:
    """Every ``.py`` file under *roots* (a root may be a single file), ``__pycache__`` excluded."""
    files: list[Path] = []
    for root in roots:
        if root.is_file():
            files.append(root)
            continue
        files.extend(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)
    return sorted(files)


def relpath(path: Path) -> str:
    """POSIX-style repository-relative path, the key the adjudicated table uses."""
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def _call_name(node: ast.Call) -> str:
    func = node.func
    return func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""


def _is_mode_getattr(node: ast.Call) -> bool:
    if _call_name(node) != "getattr" or len(node.args) < 2:
        return False
    attr = node.args[1]
    return isinstance(attr, ast.Constant) and attr.value in _MODE_ATTRS


def _is_mode_carrier(child: ast.AST) -> bool:
    if isinstance(child, ast.Attribute):
        return child.attr in _MODE_ATTRS
    if isinstance(child, ast.Name):
        return child.id == "mode" or child.id.endswith("_mode")
    if isinstance(child, ast.Call):
        return _call_name(child) == "S_IMODE" or _is_mode_getattr(child)
    return False


def _carries_mode(node: ast.AST) -> bool:
    return any(_is_mode_carrier(child) for child in ast.walk(node))


def _is_planned_stamp(node: ast.AST) -> bool:
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return any(_is_planned_stamp(element) for element in node.elts)
    if isinstance(node, ast.Attribute):
        return node.attr == "after"
    return isinstance(node, ast.Name) and node.id in _PLANNED_NAMES


def _is_planned_mode(node: ast.AST) -> bool:
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return any(_is_planned_mode(element) for element in node.elts)
    if not (isinstance(node, ast.Attribute) and node.attr == "mode"):
        return False
    holder = node.value
    return _is_planned_stamp(holder) or (isinstance(holder, ast.Name) and holder.id in _PLANNED_MODE_HOLDERS)


def _compare_patterns(node: ast.Compare) -> list[str]:
    if not any(isinstance(op, _EQUALITY_OPS) for op in node.ops):
        return []
    operands = [node.left, *node.comparators]
    patterns = []
    if sum(_carries_mode(operand) for operand in operands) >= 2:
        patterns.append("P1")
    elif any(_is_planned_mode(operand) for operand in operands) and not all(_is_planned_mode(operand) for operand in operands):
        patterns.append("P4")
    if sum(_is_planned_stamp(operand) for operand in operands) == 1:
        patterns.append("P2")
    return patterns


def _replace_aliases(tree: ast.AST) -> frozenset[str]:
    """``replace`` plus every local name ``from dataclasses import replace as <name>`` binds."""
    names = {"replace"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "dataclasses":
            names.update(alias.asname for alias in node.names if alias.name == "replace" and alias.asname)
    return frozenset(names)


def _call_patterns(node: ast.Call, replace_names: frozenset[str]) -> list[str]:
    if _call_name(node) in replace_names and any(kw.arg == "mode" and _is_planned_mode(kw.value) for kw in node.keywords):
        return ["P3"]
    return []


class _Detector(ast.NodeVisitor):
    def __init__(self, path: str, replace_names: frozenset[str]) -> None:
        self.path = path
        self.replace_names = replace_names
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
        if self.scope and self.scope[-1] in AUTHORITY.get(self.path, frozenset()):
            return
        text = ast.unparse(node)
        self.findings.extend(Finding(self.path, self.qualname, pattern, node.lineno, text) for pattern in patterns)

    def visit_Compare(self, node: ast.Compare) -> None:
        self._report(node, _compare_patterns(node))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        self._report(node, _call_patterns(node, self.replace_names))
        self.generic_visit(node)


def scan_source(source: str, path: str) -> list[Finding]:
    """Findings for one module's *source*, keyed under the repository-relative *path*."""
    tree = ast.parse(source, filename=path)
    detector = _Detector(path, _replace_aliases(tree))
    detector.visit(tree)
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
