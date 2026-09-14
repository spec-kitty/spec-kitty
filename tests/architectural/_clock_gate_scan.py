"""Shared file-scan scope for the kernel.clock dual gate (FR-012, C-008).

Both ``test_clock_import_ban.py`` and ``test_clock_call_ban.py`` scan the
exact same corpus (``src/`` + ``tests/`` + ``scripts/``, C-008) and must agree
on it byte-for-byte -- a divergent root set between the two detectors would
let a file slip through one gate but not the other. This module is the
single source for that scope; neither gate file re-derives it independently.

Not a test module (no ``def test_*`` here, mirroring the existing
underscore-prefixed non-test helpers already in this directory --
``_sole_door_scan.py``, ``_gate_coverage.py``): pytest never collects it, so
it carries no ``pytestmark``.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
SCAN_ROOTS: tuple[Path, ...] = (SRC_ROOT, REPO_ROOT / "tests", REPO_ROOT / "scripts")
DOOR_FILE = SRC_ROOT / "kernel" / "clock.py"

#: NOTE-3 (plan Sec 1.3): both detectors carry their own floor on this count --
#: a detector that silently scans zero files (a broken root, a moved corpus)
#: must go red, not pass vacuously.
MIN_SCANNED_FILES = 100


def iter_python_files() -> list[Path]:
    """Every ``.py`` file under the gate's scan scope, ``__pycache__`` excluded."""
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
