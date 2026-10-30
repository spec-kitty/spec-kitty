"""Issue #6758: the doctor read surfaces ask the one read-side Mission predicate.

``doctor topology``, ``doctor coordination`` and ``doctor review-cycle-reconcile``
each enumerate every directory child of ``kitty-specs/``. Before the fix each one
decided for itself whether the child was a Mission, so a leftover folder holding
a ``spec.md`` and a ``tasks/`` tree (read-side residue: no ``meta.json``) was
reported as a broken Mission, scanned for coordination findings, and reconciled.

Every test here runs on one shared fixture — a Mission beside that residue child
— so each absence assertion is paired with a positive control on the same tree,
and each would fail on a walker-local rule. The pre-existing, non-git unit tests
in the modules' own test files stay the regression guard for selectable Missions.

Git is real (``git init`` + commit) because file-presence mode would classify
the residue child as a Mission; hence ``git_repo`` and not the ``fast`` tier.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.cli.commands import _coordination_doctor as coordination
from specify_cli.cli.commands import _identity_audit as identity_audit
from specify_cli.cli.commands import _review_cycle_reconcile_doctor as review_cycle
from specify_cli.context import mission_resolver
from tests._support.mission_residue_fixture import (
    MISSION_SLUG,
    RESIDUE_SLUG,
    seed_mission_and_residue,
    seed_tracked_idless_missions,
)

pytestmark = [pytest.mark.regression, pytest.mark.integration, pytest.mark.git_repo]


def _spy_on_tracked_paths(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Count the ``git ls-files`` probes ``tracked_mission_paths`` makes, keyed by repo root."""
    calls: list[Path] = []
    real = mission_resolver.tracked_paths

    def _counting(cwd: Path, **kwargs: object) -> tuple[str, ...]:
        calls.append(cwd)
        return real(cwd, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(mission_resolver, "tracked_paths", _counting)
    return calls


def test_collect_topology_rows_skips_residue(tmp_path: Path) -> None:
    """``doctor topology`` lists the Mission and not the residue child."""
    seed_mission_and_residue(tmp_path)

    rows = identity_audit._collect_topology_rows(tmp_path, None)
    slugs = [row["slug"] for row in rows]

    assert MISSION_SLUG in slugs, "the positive control: a selectable Mission must still be listed"
    assert RESIDUE_SLUG not in slugs, "a folder with no meta.json is not a Mission and must not get a row"
    assert all(row["error"] != "meta.json not found" for row in rows), "no row may describe residue as a broken Mission"


def test_run_topology_audit_json_excludes_residue(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The ``doctor topology --json`` payload a user sees carries Missions only."""
    seed_mission_and_residue(tmp_path)

    identity_audit.run_topology_audit(tmp_path, json_output=True, mission=None)
    report = json.loads(capsys.readouterr().out)

    assert [row["slug"] for row in report["missions"]] == [MISSION_SLUG]


def test_collect_topology_rows_keeps_tracked_idless_missions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An id-less Mission git tracks is still listed, and the walk probes git at most once."""
    children = seed_tracked_idless_missions(tmp_path)
    calls = _spy_on_tracked_paths(monkeypatch)

    rows = identity_audit._collect_topology_rows(tmp_path, None)

    assert sorted(row["slug"] for row in rows) == sorted(child.name for child in children)
    assert len(calls) <= 1, f"one TrackedMissionPaths memo per walk, not one probe per child: {calls}"


def test_collect_topology_rows_probes_git_at_all_only_when_needed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A walk whose children all carry a ``mission_id`` (or none at all) makes no git call."""
    seed_mission_and_residue(tmp_path)
    calls = _spy_on_tracked_paths(monkeypatch)

    identity_audit._collect_topology_rows(tmp_path, None)

    assert calls == [], "the predicate decides both children without git; the memo must not probe"


def test_resolve_mission_dirs_skips_residue(tmp_path: Path) -> None:
    """``doctor coordination`` scans Missions only."""
    seed_mission_and_residue(tmp_path)

    names = [path.name for path in coordination._resolve_mission_dirs(tmp_path, None)]

    assert MISSION_SLUG in names
    assert RESIDUE_SLUG not in names


def test_mission_dirs_for_skips_residue(tmp_path: Path) -> None:
    """``doctor review-cycle-reconcile`` scans Missions only."""
    seed_mission_and_residue(tmp_path)

    names = [path.name for path in review_cycle._mission_dirs_for(tmp_path, None)]

    assert MISSION_SLUG in names
    assert RESIDUE_SLUG not in names
