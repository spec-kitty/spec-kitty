"""#7000: every repository path a battery gate reads is declared, or inside the battery's code scope.

#6996 made each gate declare the paths it reads beyond its code scope
(``special_tiers.architectural.scan_scopes``) and proved the *routing* property over those
declarations (``test_battery_scan_scope_routing.py``). Nothing checked a declaration was
**complete**, so a gate that started reading a new root kept a stale row and routing missed it
again -- the #6994 defect class.

This gate closes that hole statically: ``_gate_read_scope`` extracts every repository-rooted
read from each battery gate (and from the ``tests.architectural`` helpers it imports), and this
module fails on any read that neither a ``scan_scopes`` glob of that gate nor the battery code
scope covers. The code scope is read from the router -- ``src/**``, ``tests/architectural/**``
and every group the ``architectural-heavy`` job selects besides ``arch_scan_scope`` -- so the
check follows the same authority that decides when the whole battery runs.

Two kinds of read are deliberately outside the property, both named in the scanner's docstring:
a read whose entire path is computed at runtime (``_REPO_ROOT / rel``) names no repository path,
and a read a gate roots somewhere other than ``Path(__file__).resolve().parents[2]`` is not
visible to the scan. ``EXEMPT_READS`` admits the two reads that are not repository reads at all.

Proven red first: before the declarations landed, this gate reported 41 uncovered reads over
18 gates (see the mission's red-first commit); the registry rows were then extended until it was
green, and ``test_gate_read_scope_controls.py`` pins that each failure mode still reds.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.architectural import _gate_read_scope as scope

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_SCAN = scope.scan()


def test_every_repo_root_read_is_declared() -> None:
    """The property: a read outside the gate's declared scope and the code scope is a defect."""
    assert not _SCAN.findings, "undeclared repository reads in the architectural battery:\n" + "\n".join(finding.describe() for finding in _SCAN.findings)


def test_the_scan_is_not_vacuous() -> None:
    """A scanner that silently finds nothing would pass the property above; floor it."""
    assert len(_SCAN.gates) >= scope.MIN_GATES, f"only {len(_SCAN.gates)} battery gates found (floor {scope.MIN_GATES})"
    assert len(_SCAN.reads) >= scope.MIN_READS, f"only {len(_SCAN.reads)} repository reads found (floor {scope.MIN_READS})"
    assert _SCAN.indirections, "no runtime-computed reads found at all: the extractor is broken, not the tree clean"


def test_every_declared_scan_scope_names_a_live_gate() -> None:
    """A declaration for a deleted gate is dead weight the routing property cannot see."""
    missing = sorted(gate for gate in scope.declared_scan_scopes() if not (scope._repo_root() / gate).is_file())
    assert not missing, f"scan_scopes declares gates that do not exist: {missing}"


def test_the_code_scope_comes_from_the_router() -> None:
    """Code scope is derived, never re-listed: the heavy job's non-scope groups plus its two trees."""
    router = scope.gs.load_router()
    groups = router.job_gates[scope.gs.HEAVY_BATTERY_JOB] - {scope.gs.BATTERY_SCOPE_GROUP}
    derived = {glob for group in groups for glob in router.filters.get(group, ())}
    assert set(scope.CODE_SCOPE_EXTRA) <= set(_SCAN.code_scope)
    assert derived <= set(_SCAN.code_scope), "the router selects a code group the scan does not treat as code scope"
    assert scope.gs.BATTERY_SCOPE_GROUP not in groups


def test_every_exemption_is_narrow_justified_and_needed() -> None:
    """An unexplained, wildcard or stale exemption is a silent hole in the property."""
    assert not scope.validate_exemptions(), "\n".join(scope.validate_exemptions())


def test_the_exemptions_are_the_three_non_repository_reads() -> None:
    """Guard the exemption table's size: a third entry needs a reviewer's attention, not a commit."""
    assert sorted(scope.EXEMPT_READS) == [
        "tests/architectural/test_events_cutover_absent.py",
        "tests/architectural/test_help_startup_third_party_imports.py",
        "tests/architectural/test_real_home_isolation_guard.py",
    ]
    for gate, entries in scope.EXEMPT_READS.items():
        assert entries, f"{gate} has an empty exemption mapping"
        assert all(reason.strip() for reason in entries.values())


def test_an_unparseable_gate_fails_loudly(tmp_path: Path) -> None:
    """A gate file the scan cannot parse must raise with its path, never be skipped."""
    (tmp_path / scope.BATTERY_TREE).mkdir(parents=True)
    broken = tmp_path / scope.BATTERY_TREE / "test_broken.py"
    broken.write_text("def oops(:\n", encoding="utf-8")
    with pytest.raises(SyntaxError) as caught:
        scope.repo_root_reads(broken, tmp_path)
    assert "test_broken.py" in str(caught.value.filename)

    (broken).write_text("_REPO_ROOT = Path(__file__).resolve().parents[2]\n", encoding="utf-8")
    assert scope.repo_root_reads(broken, tmp_path) == ()
