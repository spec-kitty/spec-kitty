"""Scan scope + AST detector for the root-vacuous denial-test gate (#5691).

Not a test module (mirrors ``_no_follow_symlinks_apply_scan.py``): pytest never
collects it, so it carries no ``pytestmark``.

**The defect class.** Root ignores mode bits. A test that denies access by
``chmod`` and then skips as root, or passes as root without ever reaching the
denied branch, gives no coverage in CI containers and cloud sessions, which run
as uid 0. ``tests/_support/eacces.py`` injects ``PermissionError`` at the
filesystem seam instead, which gives the same verdict for every uid.

**What is flagged.** Each finding is keyed by ``(repo-relative path, qualname)``
of the enclosing function (``<module>`` at module level):

- ``uid-skip`` -- ``os.geteuid()`` / ``os.getuid()`` compared with ``0`` or
  negated (``not os.geteuid()``), or ``getpass.getuser()`` compared with
  ``"root"``;
- ``mode-bits-skip`` -- a call to ``mode_bits_enforced(...)``;
- ``access-skip`` -- ``os.access(...)`` inside a ``skipif(...)``, or in the test
  of an ``if`` whose body skips or returns;
- ``chmod-denial`` -- a ``chmod`` / ``lchmod`` / ``fchmod`` call whose mode
  denies its owner: no read bit, or no write bit with an execute bit
  (``0o000``, ``0o200``, ``0o500``, ``0o555``, ...), in a function whose own
  body calls none of the ``eacces`` seam helpers. Any other ``monkeypatch``
  does not count: the destructive-guard rmtree test patched
  ``sys.version_info`` and still never reached its retry hook as root.

**What is not flagged.** Owner ``r--`` and ``rw-`` (``0o444``, ``0o400``,
``0o600``, ``stat.S_IREAD``): on a file that is the managed read-only idiom,
which replacing does not need write permission for, and the detector cannot
tell a file from a directory. Modes it cannot evaluate statically (a named
constant, a parameter default, ``p.stat().st_mode & ~...``) are not flagged
either. Two functions with the same qualname in one file (conditional
definitions) share one key. These are accepted residuals; review catches them.
"""

from __future__ import annotations

import ast
import stat
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCAN_ROOT = REPO_ROOT / "tests"

#: A detector that silently scans zero files must go red, not pass vacuously.
#: ``tests/`` holds several thousand ``.py`` files; the floor stays well below
#: that so file churn never flakes the gate.
MIN_SCANNED_FILES = 1000

#: The helper module and this gate name the patterns they guard against.
EXCLUDED = frozenset(
    {
        "tests/_support/eacces.py",
        "tests/architectural/_root_vacuous_denial_scan.py",
        "tests/architectural/test_no_root_vacuous_denial_tests.py",
    }
)

_STAT_NAMES: dict[str, int] = {name: value for name in dir(stat) if name.startswith("S_I") and isinstance(value := getattr(stat, name), int)}
_UID_CALLS = frozenset({"geteuid", "getuid"})
_CHMOD_CALLS = frozenset({"chmod", "lchmod", "fchmod"})
#: The seam helpers of ``tests/_support/eacces.py``.
SEAM_HELPERS = frozenset({"deny_open_in", "deny_path_method", "deny_removal_from"})

Finding = tuple[str, str, str]


def relpath(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def iter_python_files() -> list[Path]:
    """Every ``.py`` file under ``tests/``, ``__pycache__`` and the excluded files left out."""
    return sorted(p for p in SCAN_ROOT.rglob("*.py") if "__pycache__" not in p.parts and relpath(p) not in EXCLUDED)


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _mode_value(node: ast.expr) -> int | None:
    """Evaluate an int literal, a ``stat.S_I*`` name, or ``|`` / ``&`` / ``~`` of those; ``None`` otherwise."""
    if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.Attribute) and node.attr in _STAT_NAMES:
        return _STAT_NAMES[node.attr]
    if isinstance(node, ast.Name) and node.id in _STAT_NAMES:
        return _STAT_NAMES[node.id]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Invert):
        inner = _mode_value(node.operand)
        return None if inner is None else ~inner & 0o7777
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.BitOr, ast.BitAnd)):
        left, right = _mode_value(node.left), _mode_value(node.right)
        if left is None or right is None:
            return None
        return left | right if isinstance(node.op, ast.BitOr) else left & right
    return None


def denies_owner(mode: int) -> bool:
    """No owner read (an unreadable file or directory), or no owner write with an execute bit (a locked directory)."""
    owner = (mode >> 6) & 0o7
    return not owner & 0o4 or (not owner & 0o2 and bool(owner & 0o1))


def _chmod_mode(node: ast.Call) -> ast.expr | None:
    """The mode argument of ``os.chmod(path, mode)``, ``Path.chmod(p, mode)`` or ``path.chmod(mode)``."""
    for keyword in node.keywords:
        if keyword.arg == "mode":
            return keyword.value
    if len(node.args) > 1:
        return node.args[1]
    return node.args[0] if node.args else None


def _is_uid_call(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and _call_name(node) in _UID_CALLS


def _is_root_check(node: ast.AST) -> bool:
    """``geteuid() == 0``, ``not geteuid()`` or ``getpass.getuser() == "root"``."""
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return _is_uid_call(node.operand)
    if not isinstance(node, ast.Compare):
        return False
    operands = [node.left, *node.comparators]
    constants = {o.value for o in operands if isinstance(o, ast.Constant)}
    if any(_is_uid_call(o) for o in operands):
        return 0 in constants
    return "root" in constants and any(isinstance(o, ast.Call) and _call_name(o) == "getuser" for o in operands)


def _is_access_skip(node: ast.AST) -> bool:
    """``skipif(os.access(...))``, or ``if os.access(...):`` whose body skips or returns."""
    if isinstance(node, ast.Call) and _call_name(node) == "skipif":
        return any(_calls(arg, "access") for arg in [*node.args, *(k.value for k in node.keywords)])
    if isinstance(node, ast.If) and _calls(node.test, "access"):
        return any(_calls(stmt, "skip") or isinstance(stmt, ast.Return) for stmt in node.body)
    return False


def _installs_seam(scope: ast.AST) -> bool:
    """Whether *scope*'s own body calls a seam helper from ``tests/_support/eacces.py``."""
    return any(isinstance(node, ast.Call) and _call_name(node) in SEAM_HELPERS for node in _own_nodes(scope))


def _calls(node: ast.AST, name: str) -> bool:
    return any(isinstance(n, ast.Call) and _call_name(n) == name for n in ast.walk(node))


def _own_nodes(scope: ast.AST) -> list[ast.AST]:
    """Nodes of *scope* that do not belong to a nested function or class."""
    found: list[ast.AST] = []
    stack = list(ast.iter_child_nodes(scope))
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        found.append(node)
        stack.extend(ast.iter_child_nodes(node))
    return found


def _scope_kinds(scope: ast.AST, decorators: list[ast.expr]) -> set[str]:
    kinds: set[str] = set()
    nodes = _own_nodes(scope) + [n for d in decorators for n in ast.walk(d)]
    for node in nodes:
        if _is_root_check(node):
            kinds.add("uid-skip")
        elif isinstance(node, ast.Call) and _call_name(node) == "mode_bits_enforced":
            kinds.add("mode-bits-skip")
        elif _is_access_skip(node):
            kinds.add("access-skip")
        elif isinstance(node, ast.Call) and _call_name(node) in _CHMOD_CALLS:
            mode_node = _chmod_mode(node)
            mode = None if mode_node is None else _mode_value(mode_node)
            if mode is not None and denies_owner(mode) and not _installs_seam(scope):
                kinds.add("chmod-denial")
    return kinds


def find_findings(tree: ast.Module, path: str) -> list[Finding]:
    """``(path, qualname, kind)`` for every flagged site in *tree*."""
    findings: set[Finding] = set()

    def visit(scope: ast.AST, qualname: str, decorators: list[ast.expr]) -> None:
        for kind in _scope_kinds(scope, decorators):
            findings.add((path, qualname, kind))
        for child in ast.iter_child_nodes(scope):
            _visit_defs(child, qualname)

    def _visit_defs(node: ast.AST, prefix: str) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = node.name if prefix == "<module>" else f"{prefix}.{node.name}"
            visit(node, name, list(node.decorator_list))
        elif not isinstance(node, ast.expr):
            for child in ast.iter_child_nodes(node):
                _visit_defs(child, prefix)

    visit(tree, "<module>", [])
    return sorted(findings)
