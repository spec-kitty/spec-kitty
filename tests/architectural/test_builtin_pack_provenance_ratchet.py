"""Architectural gate: shipped built-in doctrine must not grow in-house residue.

``packs/built-in/`` ships to every consumer (CLAUDE.md "Pack Tiers"). Two kinds
of text in it only make sense inside the Spec Kitty repository:

* **repo-local paths** -- ``src/specify_cli``, ``src/doctrine``,
  ``tests/architectural`` and ``kitty-specs/`` citations, which name a tree a
  consumer does not have;
* **provenance tokens** -- tracker numbers (``#1234``), work-package ids
  (``WP01``) and requirement ids (``FR-001``), which a consumer cannot resolve.

Some hits are legitimate product vocabulary (a template's ``WP01`` example, a
``kitty-specs/<mission>/`` placeholder), so the gate is a frozen,
**shrink-only** per-file census rather than a zero-tolerance ban
(``frozen-baseline-shrink-only-ratchet`` tactic). It fails when:

* a file's count for either class exceeds its baseline entry, or a file with
  hits has no entry (new residue -- move it to ``packs/internal/`` or reword it);
* a file's count dropped below its baseline entry, or an entry names a file
  that no longer has hits (lower the baseline in the same change so the
  ratchet cannot regrow).

Generated files (``*.graph.yaml``, ``pack-manifest.yaml``) are skipped: they
restate artifact content that is already counted at its source.

Refresh a baseline you have just shrunk with
``python -m tests.architectural.test_builtin_pack_provenance_ratchet``.
Issue #5203.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
from ruamel.yaml import YAML

pytestmark = [pytest.mark.architectural]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BUILTIN_ROOT = _REPO_ROOT / "packs" / "built-in"
_BASELINE_PATH = Path(__file__).with_name("_builtin_pack_provenance_baseline.yaml")

#: Census classes -> the pattern each one counts (one count per match).
PATTERNS: dict[str, re.Pattern[str]] = {
    "repo_paths": re.compile(r"src/specify_cli|src/doctrine|tests/architectural|kitty-specs/"),
    "provenance": re.compile(r"#\d{3,5}|WP\d\d|FR-\d+"),
}

_TEXT_SUFFIXES = frozenset({".yaml", ".yml", ".md", ".py", ".txt", ".json", ".toml"})


def _is_generated(path: Path) -> bool:
    return path.name.endswith(".graph.yaml") or path.name == "pack-manifest.yaml"


def census(root: Path = _BUILTIN_ROOT) -> dict[str, dict[str, int]]:
    """Count every census class per file under ``root`` (non-zero entries only)."""
    result: dict[str, dict[str, int]] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in _TEXT_SUFFIXES or _is_generated(path):
            continue
        text = path.read_text(encoding="utf-8")
        counts = {name: len(pattern.findall(text)) for name, pattern in PATTERNS.items()}
        counts = {name: count for name, count in counts.items() if count}
        if counts:
            result[path.relative_to(root).as_posix()] = counts
    return result


def load_baseline(path: Path = _BASELINE_PATH) -> dict[str, dict[str, int]]:
    data = YAML(typ="safe").load(path.read_text(encoding="utf-8")) or {}
    return {str(file): {str(k): int(v) for k, v in counts.items()} for file, counts in data.items()}


def ratchet_violations(live: dict[str, dict[str, int]], baseline: dict[str, dict[str, int]]) -> tuple[list[str], list[str]]:
    """Return ``(growth, stale)`` violation messages for ``live`` vs ``baseline``."""
    growth: list[str] = []
    stale: list[str] = []
    for file in sorted(set(live) | set(baseline)):
        for name in PATTERNS:
            now = live.get(file, {}).get(name, 0)
            frozen = baseline.get(file, {}).get(name, 0)
            if now > frozen:
                growth.append(f"{file}: {name} {frozen} -> {now}")
            elif now < frozen:
                stale.append(f"{file}: {name} baseline {frozen}, live {now}")
    return growth, stale


def test_builtin_pack_residue_does_not_grow() -> None:
    growth, _ = ratchet_violations(census(), load_baseline())
    assert not growth, (
        "New in-house residue in packs/built-in (ships to every consumer). Move "
        "repository-specific doctrine to packs/internal/ or reword it:\n  " + "\n  ".join(growth)
    )


def test_builtin_pack_residue_baseline_is_tight() -> None:
    _, stale = ratchet_violations(census(), load_baseline())
    assert not stale, (
        f"packs/built-in residue shrank; lower {_BASELINE_PATH.relative_to(_REPO_ROOT)} in the same change so the ratchet cannot regrow:\n  " + "\n  ".join(stale)
    )


def test_census_counts_each_class(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text("see src/specify_cli/x and #1234 and WP01\n", encoding="utf-8")
    (tmp_path / "clean.md").write_text("repository-agnostic prose\n", encoding="utf-8")
    (tmp_path / "x.graph.yaml").write_text("#1234\n", encoding="utf-8")
    assert census(tmp_path) == {"a.yaml": {"repo_paths": 1, "provenance": 2}}


def test_ratchet_flags_growth_new_files_and_stale_entries() -> None:
    baseline = {"a.yaml": {"provenance": 2}, "gone.yaml": {"repo_paths": 1}}
    live = {"a.yaml": {"provenance": 3}, "new.yaml": {"repo_paths": 1}}
    growth, stale = ratchet_violations(live, baseline)
    assert growth == ["a.yaml: provenance 2 -> 3", "new.yaml: repo_paths 0 -> 1"]
    assert stale == ["gone.yaml: repo_paths baseline 1, live 0"]


def _dump_census() -> None:
    YAML().dump(census(), sys.stdout)


if __name__ == "__main__":
    _dump_census()
