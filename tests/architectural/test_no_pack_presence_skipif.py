"""Gate: no test may skip itself based on whether ``packs/built-in`` exists (#6451).

Skipping on the tree's presence hides a missing sync as a green run. Tests that need the pack must
fail loudly (``BuiltInPackMissing``), not skip.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TESTS_ROOT = _REPO_ROOT / "tests"
_SKIP = re.compile(r"\bskipif\b|\bpytest\.skip\b|\bimportorskip\b")
_PACK_PRESENCE = re.compile(r"packs\W+built-in|built_in_root|BUILT_IN_ROOT|built_in_pack_dir", re.IGNORECASE)
_EXISTS = re.compile(r"\.(exists|is_dir|is_file)\s*\(|os\.path\.(exists|isdir)")
_WINDOW = 3


def find_violations(root: Path, *, exclude: frozenset[Path] = frozenset()) -> list[str]:
    """Return ``path:line`` for each skip construct within a few lines of a line testing built-in presence."""
    hits: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if path in exclude:
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for idx, line in enumerate(lines):
            if not _SKIP.search(line):
                continue
            window = lines[max(0, idx - _WINDOW) : idx + _WINDOW + 1]
            if any(_PACK_PRESENCE.search(w) and _EXISTS.search(w) for w in window):
                hits.append(f"{path.relative_to(root)}:{idx + 1}")
    return hits


def test_no_skipif_keyed_on_built_in_presence() -> None:
    assert find_violations(_TESTS_ROOT, exclude=frozenset({Path(__file__).resolve()})) == []


def test_planted_violation_is_detected(tmp_path: Path) -> None:
    """Non-vacuity: the scanner flags a skipif on the tree's presence and spares unrelated skips."""
    (tmp_path / "test_bad.py").write_text(
        'import pytest\nfrom pathlib import Path\n\n@pytest.mark.skipif(not Path("packs/built-in").exists(), reason="no pack")\ndef test_x(): ...\n',
        encoding="utf-8",
    )
    (tmp_path / "test_ok.py").write_text(
        'import pytest, sys\n\n@pytest.mark.skipif(sys.platform == "win32", reason="posix")\ndef test_y(): ...\n',
        encoding="utf-8",
    )

    assert find_violations(tmp_path) == ["test_bad.py:4"]
