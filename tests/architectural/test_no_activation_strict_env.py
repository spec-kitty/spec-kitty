"""The activation ledger has one mode: no transition switch survives in ``src/`` or ``tests/`` (WP14, FR-017).

The transition machinery of the ledger rollout (an environment switch, its
readers, the swept-file list and the pytest hooks that set it) is gone after
the reduced flip. This gate scans every file under ``src/`` and ``tests/``
(``__pycache__`` aside) for the names that machinery used and fails on any
mention. It excludes only itself, and a self-mutation case proves it is not
vacuous.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pytest

pytestmark = [pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCANNED = ("src", "tests")
_SELF = Path(__file__).resolve()

#: The names of the retired transition machinery.
FORBIDDEN: tuple[str, ...] = (
    "SPEC_KITTY_ACTIVATION_STRICT",
    "activation_strict",
    "legacy_save_accepts_deny",
    "SWEPT_PREFIXES",
    "activation_strict_mode",
    "D0 transition",
)


def mentions(text: str) -> tuple[str, ...]:
    """The forbidden names *text* mentions, in :data:`FORBIDDEN` order."""
    return tuple(name for name in FORBIDDEN if name in text)


def _scanned_files(roots: Iterable[Path]) -> list[Path]:
    found: list[Path] = []
    for root in roots:
        for path in sorted(root.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.resolve() != _SELF:
                found.append(path)
    return found


def violations(roots: Iterable[Path]) -> dict[str, tuple[str, ...]]:
    """``{relative path: names}`` for every scanned file that mentions a forbidden name."""
    hits: dict[str, tuple[str, ...]] = {}
    for path in _scanned_files(roots):
        names = mentions(path.read_bytes().decode("utf-8", errors="replace"))
        if names:
            hits[path.relative_to(_REPO_ROOT).as_posix() if path.is_relative_to(_REPO_ROOT) else str(path)] = names
    return hits


def test_no_file_in_src_or_tests_mentions_the_transition_machinery() -> None:
    assert violations(_REPO_ROOT / root for root in _SCANNED) == {}


def test_the_scan_covers_src_and_tests_and_excludes_only_itself() -> None:
    files = _scanned_files(_REPO_ROOT / root for root in _SCANNED)
    assert any(path.is_relative_to(_REPO_ROOT / "src") for path in files)
    assert any(path.is_relative_to(_REPO_ROOT / "tests") for path in files)
    assert _SELF not in {path.resolve() for path in files}
    assert (_REPO_ROOT / "tests" / "conftest.py") in files


@pytest.mark.parametrize("name", FORBIDDEN)
def test_self_mutation_a_planted_mention_is_found(tmp_path: Path, name: str) -> None:
    planted = tmp_path / "src" / "planted.py"
    planted.parent.mkdir(parents=True)
    planted.write_text(f"VALUE = {name!r}\n", encoding="utf-8")
    clean = tmp_path / "tests" / "clean.py"
    clean.parent.mkdir(parents=True)
    clean.write_text("VALUE = 1\n", encoding="utf-8")
    assert violations([tmp_path / "src", tmp_path / "tests"]) == {str(planted): (name,) if name != "activation_strict_mode" else ("activation_strict", name)}
