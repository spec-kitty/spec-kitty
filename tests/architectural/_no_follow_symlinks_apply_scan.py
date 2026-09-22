"""Shared scan scope + AST detector for the no-follow-symlinks apply ban gate (#4923, T004).

Not a test module (mirrors the existing underscore-prefixed non-test helpers
already in this directory -- ``_os_detection_scan.py``, ``_clock_gate_scan.py``):
pytest never collects it, so it carries no ``pytestmark``.

**Scan scope -- the managed-skill apply surface only.** Unlike the
``os``-detection gate (which scans all of ``src/``), this gate targets the
two packages that actually stage/apply managed-skill and tool-surface
filesystem effects: ``src/specify_cli/skills/`` and
``src/specify_cli/tool_surface/``. The canonical host-safe primitives
(``kernel.no_follow.chmod_no_follow`` / ``utime_no_follow``) legitimately
contain the literal ``follow_symlinks=False`` call this gate bans -- but
``src/kernel/`` is outside the scan roots, so no door/exemption dance is
needed the way the OS-detection gate needs one for ``kernel/paths.py``.

**What is banned.** Any ``chmod``/``utime`` call (as an attribute call --
``x.chmod(...)``/``os.utime(...)`` -- or a bare name call) carrying an
explicit ``follow_symlinks=False`` keyword argument. This is the exact
crash shape from #4923: on a host lacking ``follow_symlinks`` support,
passing the flag unconditionally raises
``NotImplementedError: utime/chmod: follow_symlinks unavailable on this
platform``. Every legitimate call-site must route through
``kernel.no_follow.chmod_no_follow`` / ``utime_no_follow`` instead, which
guard the flag behind ``os.supports_follow_symlinks``.

**What is NOT banned (over-fire boundaries).** A safe ``follow_symlinks``
use on ``stat``/``is_file``/``lstat`` (different function names entirely --
never matched), and the legitimate default-follow
``os.utime(dest, ns=...)`` at ``asset_preservation/backup.py:38`` (no
``follow_symlinks`` keyword at all, so the detector never fires on it).
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
SCAN_ROOTS: tuple[Path, ...] = (
    SRC_ROOT / "specify_cli" / "skills",
    SRC_ROOT / "specify_cli" / "tool_surface",
)

#: NOTE-3 (mirrors the OS-detection gate): a detector silently scanning zero
#: files must go red, not pass vacuously. 57 ``.py`` files live under the two
#: scan roots at T004 landing time; this floor stays comfortably below that
#: so ordinary file churn does not flake the gate, while still catching a
#: scan-root typo or an accidentally-emptied ``SCAN_ROOTS``.
MIN_SCANNED_FILES = 40

_BANNED_ATTRS = frozenset({"chmod", "utime"})


def iter_python_files() -> list[Path]:
    """Every ``.py`` file under the scan roots, ``__pycache__`` excluded."""
    files: list[Path] = []
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            files.append(path)
    return sorted(files)


def relpath(path: Path) -> str:
    """POSIX-style repo-relative path string -- the exemption-file key format."""
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def _is_chmod_or_utime_call(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr in _BANNED_ATTRS
    if isinstance(func, ast.Name):
        return func.id in _BANNED_ATTRS
    return False


def _has_follow_symlinks_false_keyword(node: ast.Call) -> bool:
    return any(kw.arg == "follow_symlinks" and isinstance(kw.value, ast.Constant) and kw.value.value is False for kw in node.keywords)


def find_no_follow_symlinks_apply_violations(tree: ast.AST) -> list[int]:
    """Line numbers of every banned ``chmod``/``utime`` ``follow_symlinks=False`` call.

    Full ``ast.walk`` (not module-level-only) so an in-function or in-``try``
    call is caught.
    """
    linenos: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_chmod_or_utime_call(node) and _has_follow_symlinks_false_keyword(node):
            linenos.append(node.lineno)
    return sorted(linenos)
