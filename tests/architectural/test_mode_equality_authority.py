"""Mode-equality authority gate (#4927, #4810): close the Windows-mode defect class by construction.

Every planner and recheck in ``src/specify_cli/{skills,tool_surface,runtime}``,
and the charter YAML writer, decides whether an observed mode satisfies a
planned one through the one host-aware predicate: ``kernel.file_modes`` and the
``FileState`` forms in ``specify_cli.tool_surface.operations``. A direct
comparison reintroduces the #4927 defect: on Windows a ``chmod`` is planned
that NTFS can never apply, on every CLI start and every upgrade preview.

The detector lives in ``tests.architectural._mode_equality_scan``. The table
below lists the comparisons that are *meant* to stay exact on every host,
each adjudicated by kind:

* ``guard`` -- two observations of the same node (concurrency/identity checks);
* ``conflict`` -- two planned states (conflicting outputs from two owners);
* ``fidelity`` -- an observed mode copied onto a copy of that node.

Each entry names the exact comparison text, so it exempts that one comparison.

They are permanent classifications, not drain-debt, so the table needs no
``_baselines.yaml`` entry (ADR ``2026-09-30-1``). An entry that no longer
matches a live site fails the gate, so the table cannot rot.

The detector is syntactic; its docstring lists the evasions it does not
follow, and ``test_documented_residuals_stay_out_of_scope`` pins a sample of
them. Review owns those.
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
    """One comparison allowed to stay exact, keyed by its exact source text in its scope.

    Keying on the comparison's ``ast.unparse`` text (not just the function)
    means a second, different comparison added to the same function is a new,
    unadjudicated finding (review cycle 1, B1).
    """

    path: str
    qualname: str
    pattern: str
    text: str
    kind: str
    rationale: str

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.path, self.qualname, self.pattern, self.text)


ADJUDICATED: tuple[Adjudicated, ...] = (
    Adjudicated(
        _PROJECTION,
        "observe_bundle_path",
        "P1",
        "(info.st_dev, info.st_ino, info.st_mode, info.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_mode, after.st_mtime_ns)",
        "guard",
        "Two lstat reads of the same node around a content read: detects a concurrent change, so exact on every host.",
    ),
    Adjudicated(
        _PROJECTION,
        "_finalize_staged_directories",
        "P1",
        "(info.st_dev, info.st_ino, stat.S_IMODE(info.st_mode)) != (created.device, created.inode, created.state.mode)",
        "guard",
        "The open descriptor's (dev, ino, mode) against the observation taken when the directory was created: identity check.",
    ),
    Adjudicated(
        _PROJECTION,
        "_unique_members",
        "P1",
        "(previous.content, previous.mode) != (member.content, member.mode)",
        "conflict",
        "Two planned staged members for one path must agree on bytes and mode; no observation is involved.",
    ),
    Adjudicated(
        "src/specify_cli/skills/installer.py",
        "_archive_existing_path",
        "P1",
        "stat.S_IMODE(backup_path.lstat().st_mode) != before.mode",
        "fidelity",
        "Re-applies a symlink's observed mode to its backup copy on the same host; both sides are observations.",
    ),
)

#: A scan that silently visits nothing must go red. At landing: 78 files and
#: 1700 comparisons under the scan roots; the floors leave room for churn.
MIN_SCANNED_FILES = 60
MIN_SCANNED_COMPARISONS = 1200


def _unadjudicated(findings: list[scan.Finding]) -> list[scan.Finding]:
    allowed = {entry.key for entry in ADJUDICATED}
    return [f for f in findings if f.key not in allowed]


def test_no_planner_decides_mode_equality_outside_the_predicate() -> None:
    findings, _files, _comparisons = scan.scan_tree()

    offending = _unadjudicated(findings)

    assert not offending, (
        "Decide observed-vs-planned mode equality through specify_cli.tool_surface.operations "
        "(effect_action / mode_equivalent / state_equivalent / expected_with_mode) or kernel.file_modes.modes_equivalent, or adjudicate the site "
        "as a guard/conflict/fidelity comparison in ADJUDICATED:\n" + "\n".join(f"  {f.path}:{f.lineno} {f.qualname} [{f.pattern}]" for f in offending)
    )


def test_every_adjudicated_site_is_still_live() -> None:
    findings, _files, _comparisons = scan.scan_tree()
    live = {f.key for f in findings}

    stale = [entry for entry in ADJUDICATED if entry.key not in live]

    assert not stale, "Remove or update stale entries in ADJUDICATED: " + ", ".join(f"{e.path}::{e.qualname} [{e.pattern}] {e.text}" for e in stale)


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
        "def f(previous, effect):\n    return previous.after in (effect.after,)\n",  # two planned states, one in a container
        "def f(o, effect):\n    return other_replace(o, mode=effect.after.mode)\n",  # not dataclasses.replace
        "def f(mode):\n    return mode & 0o700 != 0o700\n",  # a bit test, not a comparison of two modes
        "def f(before, after):\n    return before.kind != after.kind\n",  # no mode involved
        "def f(state):\n    return state.mode is None\n",  # identity, not equality
    ],
)
def test_non_mode_comparisons_are_not_reported(source: str) -> None:
    assert scan.scan_source(source, _SYNTHETIC) == []


def test_the_authority_functions_are_allowed_to_compare() -> None:
    source = "def effect_action(before, after):\n    return before.mode != after.mode\n"
    kernel = "def modes_equivalent(kind, observed_mode, planned_mode):\n    return observed_mode == planned_mode\n"

    assert scan.scan_source(source, scan.AUTHORITY_FILE) == []
    assert scan.scan_source(kernel, "src/kernel/file_modes.py") == []
    assert [f.pattern for f in scan.scan_source(source, _SYNTHETIC)] == ["P1"]
    assert [f.pattern for f in scan.scan_source(kernel, _SYNTHETIC)] == ["P1"]


def test_the_charter_writer_is_scanned() -> None:
    """The charter YAML writer checks a written file's mode: it is in scope and uses the predicate."""
    charter = scan.SRC_ROOT / "charter" / "activation" / "charter_yaml_io.py"
    assert charter in scan.iter_python_files()
    assert "modes_equivalent(" in charter.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "source",
    [
        "import stat\ndef f(st):\n    return stat.S_IMODE(st) != 0o644\n",  # a literal
        "def f(o, target):\n    cur = o.mode\n    return cur != target.mode\n",  # an unflagged holder
        "def f(a, b):\n    return bool(a.mode ^ b.mode)\n",  # a bitwise test
        "def f(a, b):\n    return a.mode < b.mode\n",  # an ordering comparison
        "import operator\ndef f(a, b):\n    return operator.ne(a.mode, b.mode)\n",  # operator functions
    ],
)
def test_documented_residuals_stay_out_of_scope(source: str) -> None:
    """Pins the evasions the scan docstring lists as review-owned; catching one later updates both."""
    assert scan.scan_source(source, _SYNTHETIC) == []


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
        # Squad round: a planned holder other than ``after``, and membership tests.
        ("import stat\ndef f(t, prepared):\n    cur = stat.S_IMODE(t.stat().st_mode)\n    return cur != prepared.mode\n", "P4"),
        ("def f(o, effect):\n    return o.mode not in (effect.after.mode,)\n", "P1"),
        ("def f(value, effect):\n    return value in {effect.after.mode}\n", "P4"),
        # Tier R review (MINOR 2): an aliased replace, and a planned state inside a container.
        ("from dataclasses import replace as r\ndef f(o, effect):\n    return r(o, mode=effect.after.mode)\n", "P3"),
        ("import dataclasses as dc\ndef f(o, effect):\n    return dc.replace(o, mode=effect.after.mode)\n", "P3"),
        ("def f(state, effect):\n    return state in (effect.after,)\n", "P2"),
        ("def f(state, effect):\n    return state not in [effect.after]\n", "P2"),
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
