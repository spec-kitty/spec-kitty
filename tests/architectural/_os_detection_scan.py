"""Shared scan scope + AST detector for the OS-detection ban gate (FR-012).

Not a test module (mirrors the existing underscore-prefixed non-test helpers
already in this directory -- ``_clock_gate_scan.py``, ``_sole_door_scan.py``):
pytest never collects it, so it carries no ``pytestmark``.

**Scan scope -- ``src/`` ONLY (deliberate divergence, post-tasks squad
MF-1/R-05).** The sibling ``kernel.clock`` dual gate (``_clock_gate_scan.py``)
scans ``src/`` + ``tests/`` + ``scripts/``; this gate scans ``src/`` alone.
``tests/`` and ``scripts/`` legitimately exercise raw platform branches (the
Windows/POSIX lock-parity harness *must* simulate ``msvcrt``/``fcntl``
directly, and test doubles routinely force a platform via
``monkeypatch.setattr("sys.platform", ...)``), so widening the corpus would
red on dozens of legitimate hits with no achievable empty terminal. This gate
polices *production* OS-detection re-forking, not test-harness platform
simulation. Recorded here per contracts/safe-delete-and-os-seam.md Sec C.

**Idiom coverage (S-1).** All four spellings are banned:
``os.name == "nt"``, ``sys.platform == "win32"``,
``platform.system() == "Windows"``, ``sys.platform.startswith("win")``.
FR-005 explicitly enumerates ``platform.system()``; a gate that misses it
leaves the recurrence half-closed. A negated comparison
(``sys.platform != "win32"``) is NOT banned -- it appears in
``paths/windows_migrate.py`` as a "not Windows" guard and is a materially
different (and much rarer) idiom than the four the mission's census found
being re-forked.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
SCAN_ROOTS: tuple[Path, ...] = (SRC_ROOT,)
DOOR_FILE = SRC_ROOT / "kernel" / "paths.py"

#: NOTE-3 (mirrors the clock gate): a detector silently scanning zero files
#: must go red, not pass vacuously.
MIN_SCANNED_FILES = 100

#: Directories excluded even though they live under ``src/`` -- the frozen,
#: immutable one-off migration scripts (C-002 precedent from the clock gate).
_EXCLUDED_DIR_SEGMENT = ("upgrade", "migrations")


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


def _is_os_name_nt(node: ast.AST) -> bool:
    """``os.name == "nt"``."""
    return (
        isinstance(node, ast.Compare)
        and len(node.ops) == 1
        and isinstance(node.ops[0], ast.Eq)
        and isinstance(node.left, ast.Attribute)
        and node.left.attr == "name"
        and isinstance(node.left.value, ast.Name)
        and node.left.value.id == "os"
        and len(node.comparators) == 1
        and isinstance(node.comparators[0], ast.Constant)
        and node.comparators[0].value == "nt"
    )


def _is_sys_platform_win32(node: ast.AST) -> bool:
    """``sys.platform == "win32"``."""
    return (
        isinstance(node, ast.Compare)
        and len(node.ops) == 1
        and isinstance(node.ops[0], ast.Eq)
        and isinstance(node.left, ast.Attribute)
        and node.left.attr == "platform"
        and isinstance(node.left.value, ast.Name)
        and node.left.value.id == "sys"
        and len(node.comparators) == 1
        and isinstance(node.comparators[0], ast.Constant)
        and node.comparators[0].value == "win32"
    )


def _is_platform_system_windows(node: ast.AST) -> bool:
    """``platform.system() == "Windows"``."""
    if not (
        isinstance(node, ast.Compare)
        and len(node.ops) == 1
        and isinstance(node.ops[0], ast.Eq)
        and len(node.comparators) == 1
        and isinstance(node.comparators[0], ast.Constant)
        and node.comparators[0].value == "Windows"
    ):
        return False
    call = node.left
    return (
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == "system"
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "platform"
        and not call.args
        and not call.keywords
    )


def _is_sys_platform_startswith_win(node: ast.AST) -> bool:
    """``sys.platform.startswith("win")``."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "startswith"
        and isinstance(node.func.value, ast.Attribute)
        and node.func.value.attr == "platform"
        and isinstance(node.func.value.value, ast.Name)
        and node.func.value.value.id == "sys"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "win"
        and not node.keywords
    )


def find_os_detection_violations(tree: ast.AST) -> list[int]:
    """Line numbers of every banned OS-detection idiom in ``tree`` (full-AST walk).

    Full ``ast.walk`` (not module-level-only) so an in-function or in-``try``
    check is caught, matching the clock gate's import-ban walk depth.
    """
    linenos: list[int] = []
    for node in ast.walk(tree):
        if _is_os_name_nt(node) or _is_sys_platform_win32(node) or _is_platform_system_windows(node) or _is_sys_platform_startswith_win(node):
            linenos.append(node.lineno)
    return sorted(linenos)
