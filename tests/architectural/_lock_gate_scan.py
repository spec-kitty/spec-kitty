"""Shared scan scope + AST detector for the canonical lock-primitive ban gate (FR-010).

Not a test module (mirrors the existing underscore-prefixed non-test helpers
already in this directory -- ``_clock_gate_scan.py``, ``_os_detection_scan.py``):
pytest never collects it, so it carries no ``pytestmark``.

**Scan scope -- ``src/`` ONLY (deliberate divergence, post-tasks squad
MF-1/R-05), mirroring the sibling OS-detection gate.** ``tests/`` and
``scripts/`` legitimately exercise raw ``msvcrt``/``fcntl``/``filelock``
directly: the lock-parity harness (``tests/kernel/test_lock_parity.py``)
*must* simulate raw locking and Windows-mandatory semantics, and the pre-move
test suite already exercised the concrete lock type. This gate bans
re-forking the raw primitive in *production* code only.

**Banned shapes** (R-05/contracts/lock-primitive.md):

- Import: ``import msvcrt``, ``import fcntl``, ``import filelock``,
  ``from filelock import ...`` (any name).
- Call: ``msvcrt.locking(...)``, ``fcntl.flock(...)``, ``fcntl.lockf(...)``,
  a bare ``FileLock(...)`` constructor call (the shape every current
  ``from filelock import FileLock`` call site uses) and the module-attribute
  form ``filelock.FileLock(...)``.

The one sanctioned door is ``src/kernel/locks.py`` (this same WP -- T010).
Every other occurrence is either routed through it or named in a per-owner
exemption file under ``tests/architectural/_exemptions/lock-ban-*.txt``
(unioned by ``tests.architectural._lock_ban_exemptions.load_lock_ban_exemptions``).
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
SCAN_ROOTS: tuple[Path, ...] = (SRC_ROOT,)
DOOR_FILE = SRC_ROOT / "kernel" / "locks.py"

#: NOTE-3 (mirrors the clock/OS-detection gates): a detector silently
#: scanning zero files must go red, not pass vacuously.
MIN_SCANNED_FILES = 100

#: Directories excluded even though they live under ``src/`` -- the frozen,
#: immutable one-off migration scripts (C-002 precedent from the clock gate).
_EXCLUDED_DIR_SEGMENT = ("upgrade", "migrations")

_BANNED_IMPORT_ROOTS = frozenset({"msvcrt", "fcntl", "filelock"})


def iter_python_files() -> list[Path]:
    """Every ``.py`` file under ``src/``, ``__pycache__`` and frozen migrations excluded."""
    files: list[Path] = []
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            if _EXCLUDED_DIR_SEGMENT[0] in path.parts and _EXCLUDED_DIR_SEGMENT[1] in path.parts:
                continue
            files.append(path)
    return sorted(files)


def relpath(path: Path) -> str:
    """POSIX-style repo-relative path string -- the exemption-file key format."""
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def _import_violation_linenos(node: ast.AST) -> list[int]:
    if isinstance(node, ast.Import):
        if any(alias.name.split(".", 1)[0] in _BANNED_IMPORT_ROOTS for alias in node.names):
            return [node.lineno]
    elif isinstance(node, ast.ImportFrom) and node.module and node.module.split(".", 1)[0] in _BANNED_IMPORT_ROOTS:
        return [node.lineno]
    return []


def _is_msvcrt_locking_call(node: ast.AST) -> bool:
    """``msvcrt.locking(...)``."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "locking"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "msvcrt"
    )


def _is_fcntl_flock_or_lockf_call(node: ast.AST) -> bool:
    """``fcntl.flock(...)`` or ``fcntl.lockf(...)``."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"flock", "lockf"}
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "fcntl"
    )


def _is_filelock_constructor_call(node: ast.AST) -> bool:
    """A bare ``FileLock(...)`` call, or the module-attribute ``filelock.FileLock(...)`` form."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name) and func.id == "FileLock":
        return True
    return isinstance(func, ast.Attribute) and func.attr == "FileLock" and isinstance(func.value, ast.Name) and func.value.id == "filelock"


def find_lock_ban_violations(tree: ast.AST) -> list[int]:
    """Line numbers of every banned raw-lock import/call in ``tree`` (full-AST walk).

    Full ``ast.walk`` (not module-level-only) so an in-function or in-``try``
    import/call is caught, matching the clock/OS-detection gates' walk depth.
    """
    linenos: list[int] = []
    for node in ast.walk(tree):
        linenos.extend(_import_violation_linenos(node))
        if _is_msvcrt_locking_call(node) or _is_fcntl_flock_or_lockf_call(node) or _is_filelock_constructor_call(node):
            linenos.append(node.lineno)
    return sorted(linenos)
