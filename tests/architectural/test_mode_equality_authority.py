"""Mode-equality authority gate (#4927, #4810): close the Windows-mode defect class by construction.

Every planner and recheck in ``src/specify_cli/{skills,tool_surface,runtime}``
decides whether an observed mode satisfies a planned one through the one
host-aware predicate in ``specify_cli.tool_surface.operations``. A direct
comparison reintroduces the #4927 defect: on Windows a ``chmod`` is planned
that NTFS can never apply, on every CLI start and every upgrade preview.

The detector lives in ``tests.architectural._mode_equality_scan``. The table
below lists the comparisons that are *meant* to stay exact on every host,
each adjudicated by kind:

* ``guard`` -- two observations of the same node (concurrency/identity checks);
* ``conflict`` -- two planned states (conflicting outputs from two owners);
* ``fidelity`` -- an observed mode copied onto a copy of that node.

They are permanent classifications, not drain-debt, so the table needs no
``_baselines.yaml`` entry (ADR ``2026-09-30-1``). An entry that no longer
matches a live site fails the gate, so the table cannot rot.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.architectural import _mode_equality_scan as scan

pytestmark = [pytest.mark.architectural]

_PROJECTION = "src/specify_cli/tool_surface/bundles/projection.py"


@dataclass(frozen=True)
class Adjudicated:
    """One comparison allowed to stay exact, keyed by (path, qualname, pattern)."""

    path: str
    qualname: str
    pattern: str
    kind: str
    rationale: str

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.path, self.qualname, self.pattern)


ADJUDICATED: tuple[Adjudicated, ...] = (
    Adjudicated(
        _PROJECTION,
        "observe_bundle_path",
        "P1",
        "guard",
        "Two lstat reads of the same node around a content read: detects a concurrent change, so exact on every host.",
    ),
    Adjudicated(
        _PROJECTION,
        "_finalize_staged_directories",
        "P1",
        "guard",
        "The open descriptor's (dev, ino, mode) against the observation taken when the directory was created: identity check.",
    ),
    Adjudicated(
        _PROJECTION,
        "_unique_members",
        "P1",
        "conflict",
        "Two planned staged members for one path must agree on bytes and mode; no observation is involved.",
    ),
    Adjudicated(
        "src/specify_cli/skills/installer.py",
        "_archive_existing_path",
        "P1",
        "fidelity",
        "Re-applies a symlink's observed mode to its backup copy on the same host; both sides are observations.",
    ),
)

#: A scan that silently visits nothing must go red. At landing: 77 files and
#: 1616 comparisons under the three roots; the floors leave room for churn.
MIN_SCANNED_FILES = 60
MIN_SCANNED_COMPARISONS = 1200


def _unadjudicated(findings: list[scan.Finding]) -> list[scan.Finding]:
    allowed = {entry.key for entry in ADJUDICATED}
    return [f for f in findings if (f.path, f.qualname, f.pattern) not in allowed]


def test_no_planner_decides_mode_equality_outside_the_predicate() -> None:
    findings, _files, _comparisons = scan.scan_tree()

    offending = _unadjudicated(findings)

    assert not offending, (
        "Decide observed-vs-planned mode equality through specify_cli.tool_surface.operations "
        "(effect_action / mode_equivalent / state_equivalent / modes_equivalent), or adjudicate the site "
        "as a guard/conflict/fidelity comparison in ADJUDICATED:\n" + "\n".join(f"  {f.path}:{f.lineno} {f.qualname} [{f.pattern}]" for f in offending)
    )


def test_every_adjudicated_site_is_still_live() -> None:
    findings, _files, _comparisons = scan.scan_tree()
    live = {(f.path, f.qualname, f.pattern) for f in findings}

    stale = [entry for entry in ADJUDICATED if entry.key not in live]

    assert not stale, "Remove stale entries from ADJUDICATED: " + ", ".join(f"{e.path}::{e.qualname} [{e.pattern}]" for e in stale)


def test_adjudicated_entries_are_classified_and_justified() -> None:
    for entry in ADJUDICATED:
        assert entry.kind in {"guard", "conflict", "fidelity"}, entry
        assert len(entry.rationale) > 40, entry
    assert len({entry.key for entry in ADJUDICATED}) == len(ADJUDICATED), "duplicate ADJUDICATED keys"


def test_scan_is_not_vacuous() -> None:
    _findings, files, comparisons = scan.scan_tree()

    assert files >= MIN_SCANNED_FILES, files
    assert comparisons >= MIN_SCANNED_COMPARISONS, comparisons
    for root in scan.SCAN_ROOTS:
        assert scan.iter_python_files((root,)), f"scan root has no Python files: {root}"


# ── self-mutation: every pattern is caught in a synthetic module ───────────

_SYNTHETIC = "src/specify_cli/tool_surface/synthetic.py"


@pytest.mark.parametrize(
    ("source", "pattern"),
    [
        ("def f(before, after):\n    return before.mode != after.mode\n", "P1"),
        ("import stat\ndef f(p, after):\n    return stat.S_IMODE(p.lstat().st_mode) != after.mode\n", "P1"),
        ("def f(observed, effect):\n    return observed != effect.after\n", "P2"),
        ("def f(item, effect):\n    return effect.after == item.state\n", "P2"),
        ("from dataclasses import replace\ndef f(o, effect):\n    return replace(o, mode=effect.after.mode)\n", "P3"),
    ],
)
def test_each_pattern_is_detected(source: str, pattern: str) -> None:
    assert [f.pattern for f in scan.scan_source(source, _SYNTHETIC)] == [pattern]


@pytest.mark.parametrize(
    "source",
    [
        "def f(previous, effect):\n    return previous.after == effect.after\n",  # two planned states
        "def f(mode):\n    return mode & 0o700 != 0o700\n",  # a bit test, not a comparison of two modes
        "def f(before, after):\n    return before.kind != after.kind\n",  # no mode involved
        "def f(state):\n    return state.mode is None\n",  # identity, not equality
    ],
)
def test_non_mode_comparisons_are_not_reported(source: str) -> None:
    assert scan.scan_source(source, _SYNTHETIC) == []


def test_the_authority_functions_are_allowed_to_compare() -> None:
    source = "def effect_action(before, after):\n    return before.mode != after.mode\n"

    assert scan.scan_source(source, scan.AUTHORITY_FILE) == []
    assert [f.pattern for f in scan.scan_source(source, _SYNTHETIC)] == ["P1"]


def test_qualname_names_the_enclosing_scope() -> None:
    source = "class Owner:\n    def plan(self, before, after):\n        return before.mode != after.mode\n"

    assert [(f.qualname, f.lineno) for f in scan.scan_source(source, _SYNTHETIC)] == [("Owner.plan", 3)]


# ── review cycle 1: the evasions a function-wide or one-sided key let through ──


def test_a_second_comparison_in_an_adjudicated_function_is_caught() -> None:
    """B1: an adjudicated entry exempts one comparison text, never its whole function."""
    path = scan.SRC_ROOT / "specify_cli" / "tool_surface" / "bundles" / "projection.py"
    source = path.read_text(encoding="utf-8")
    anchor = "                chmod_fd(descriptor, effect.destination, effect.after.mode)\n"
    assert anchor in source, "control: the finalize chmod is where the #4927 shape would be reintroduced"
    mutated = source.replace(
        anchor,
        "                if current.state.mode != effect.after.mode:\n    " + anchor,
        1,
    )

    offending = _unadjudicated(scan.scan_source(mutated, scan.relpath(path)))

    assert [(f.qualname, f.pattern) for f in offending] == [("_finalize_staged_directories", "P1")]


@pytest.mark.parametrize(
    ("source", "pattern"),
    [
        # B2: one side extracted into a variable -- the original installer.py:1040 shape.
        ("import stat\ndef f(path, after):\n    current = stat.S_IMODE(path.lstat().st_mode)\n    return current != after.mode\n", "P4"),
        ("def f(value, effect):\n    return value == effect.after.mode\n", "P4"),
        # Mode-named names and getattr carry a mode too.
        ("def f(observed_mode, effect):\n    return observed_mode == effect.after.mode\n", "P1"),
        ("def f(observed_mode, planned_mode):\n    return observed_mode != planned_mode\n", "P1"),
        ("def f(x, after):\n    return getattr(x, 'mode') != after.mode\n", "P1"),
    ],
)
def test_one_sided_and_aliased_mode_comparisons_are_caught(source: str, pattern: str) -> None:
    assert [f.pattern for f in scan.scan_source(source, _SYNTHETIC)] == [pattern]


# ── live mutation: reverting a real planner to a raw compare is caught ─────


def test_reverting_the_global_planner_to_a_raw_compare_is_caught() -> None:
    path = scan.SRC_ROOT / "specify_cli" / "runtime" / "asset_preparation.py"
    source = path.read_text(encoding="utf-8")
    assert "effect_action(before, after)" in source, "control: the global planner delegates to effect_action"
    mutated = source.replace(
        "effect_action(before, after)",
        "(None if before.mode == after.mode else 'chmod')",
        1,
    )

    findings = scan.scan_source(mutated, scan.relpath(path))

    assert [(f.qualname, f.pattern) for f in findings] == [("AssetPreparation._effect", "P1")]


def test_the_retired_relaxation_helper_is_gone() -> None:
    for path in scan.iter_python_files():
        assert "windows_dir_mode_only_divergence" not in path.read_text(encoding="utf-8"), Path(path).name
