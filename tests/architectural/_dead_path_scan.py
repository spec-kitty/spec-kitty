"""Shared scan machinery for the dead-path architectural gates.

Mission ``doctrine-consumer-surface-missions-extraction-01KZ6G6H`` WP01
(FR-001, NFR-003, NFR-004). Promoted out of the original monolithic
``test_no_dead_doctrine_paths.py`` (mission ``doctrine-silence-guards-01KYFV7Q``
WP07), which mixed three distinct scan scopes behind one shared set of
helpers. That file is now split by *actual scan scope*:

``tests/architectural/test_no_dead_cli_paths.py`` -- Gate A + Gate B, both
``src/``-wide (CLI-wide, not doctrine-scoped).

``tests/architectural/test_no_dead_doctrine_paths.py`` -- Gate C alone, the
only ``src/charter/offering/``-scoped gate; the file keeps its original name because
that name now means what it says.

``tests/architectural/test_dead_builtin_doc_paths.py`` -- Gate D alone, the
only ``docs/``-scoped gate.

This module carries the machinery all three of the above import so nothing is
duplicated: the ``Site`` dataclass, the repo-root constants, the text-file
reader, and the shared error-message renderer. Mirrors the existing
convention of underscore-prefixed shared modules in this directory
(``_gate_coverage.py``, ``_sole_door_scan.py``). **Not a test module** --
pytest collects zero tests from it (no ``def test_`` functions, no ``Test*``
classes).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_ROOT = _REPO_ROOT / "src"
#: Relocated doctrine source root (mission ``charter-code-topology-01M152G1``).
#: ``src/doctrine/`` moved to ``src/charter/offering/`` (the ``src/doctrine.py``
#: compat shim has since been deleted, #805).
_DOCTRINE_ROOT = _SRC_ROOT / "charter" / "offering"

#: Relocated built-in pack root (mission ``relocate-builtin-doctrine-packs-01KYT87F``).
#: The shipped built-in doctrine content that names paths -- agent profiles,
#: glossary packs, toolguide markdown, and the per-kind ``*.graph.yaml`` fragments
#: -- moved out of ``src/charter/offering/`` into this top-level pack root. The dead-path
#: defect class now spans BOTH trees (consuming code under ``src/``; authored pack
#: content under ``packs/built-in/``), so every shipped gate scans the pair and
#: merges the result. ``_rel`` addresses each site repo-relatively, so a merged
#: site keeps its true ``src/...`` or ``packs/...`` prefix.
_PACKS_ROOT = _REPO_ROOT / "packs" / "built-in"

#: Text suffixes worth scanning for path-shaped guidance.
_TEXT_SUFFIXES = frozenset({".py", ".md", ".yaml", ".yml", ".json", ".toml", ".txt"})


@dataclass(frozen=True, order=True)
class Site:
    """One matched occurrence, addressed repo-relatively."""

    path: str
    line: int
    text: str


def _rel(path: Path, root: Path) -> str:
    """Repo-relative address, falling back to *root* for scanner unit tests."""
    try:
        return path.relative_to(_REPO_ROOT).as_posix()
    except ValueError:
        return path.relative_to(root).as_posix()


def _read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


@lru_cache(maxsize=8)
def _text_files(root: Path) -> tuple[tuple[Path, tuple[str, ...]], ...]:
    """Read every scannable text file under *root* once per root.

    **Caveat for future consumers: the cache is keyed on the root PATH, not on its contents**
    (same boundary as ``tests/architectural/_home_pin_scan.py::_corpus``, which documents the
    live incident this sweep addressed, planning#88). A caller that materialises a synthetic
    tree, scans it, then rewrites files under the **same** root within one process gets the
    first read back. This bites hardest under ``tmp_path_retention_policy = failed``:
    ``_pytest.tmpdir._mk_tmp`` truncates node names at ``MAXVAL = 30`` chars, so parametrizations
    of one long test name can share an identical truncated prefix and, once each dir is
    rmtree'd at its own teardown, ``make_numbered_dir``'s sibling scan can hand two
    parametrizations the SAME physical directory. Give a parametrized caller a distinct subroot
    per parametrization (``tmp_path / param``), never a bare ``tmp_path``.
    """
    found: list[tuple[Path, tuple[str, ...]]] = []
    for candidate in sorted(root.rglob("*")):
        if candidate.is_file() and candidate.suffix in _TEXT_SUFFIXES:
            found.append((candidate, tuple(_read_lines(candidate))))
    return tuple(found)


def _render(sites: tuple[Site, ...]) -> str:
    return "\n".join(f"  {site.path}:{site.line}: {site.text}" for site in sites)
