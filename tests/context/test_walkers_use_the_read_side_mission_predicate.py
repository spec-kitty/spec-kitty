"""Every ``kitty-specs/`` walker asks the one read-side Mission predicate (#6758).

Six read surfaces enumerate the directory children of ``kitty-specs/``: the three
``doctor`` scans (``topology``, ``coordination``, ``review-cycle-reconcile``), the
``charter activate`` in-flight warning, ``materialize`` and the release-changelog
block. Each one used to decide for itself whether a child was a Mission, so a
leftover folder holding a ``spec.md`` and a ``tasks/`` tree (read-side residue:
no ``meta.json``) was reported as a broken Mission, scanned for findings,
materialized and published in the release notes.

The contract this file guards: **every one of them decides through
:func:`specify_cli.context.mission_resolver.is_selectable_mission_dir`**, the same
read-side rule Mission selection uses. The structural half of that contract is
pinned in ``tests/architectural/test_mission_resolver_walker_gate.py``
(``_PREDICATE_ROUTED_WALKERS``).

Every test runs on one shared fixture
(:mod:`tests._support.mission_residue_fixture`) — a Mission beside that residue
child, both carrying an accepted ``WP01`` and an in-flight ``WP02`` event — so
each absence assertion is paired with a positive control on the same tree and
would fail on a walker-local rule. The modules' own non-git tests stay the
regression guard for selectable Missions.

Git is real (``git init`` + commit) because file-presence mode would classify the
residue child as a Mission; hence ``git_repo`` and not the ``fast`` tier.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.charter_activate import _collect_inflight_missions
from specify_cli.cli.commands import _coordination_doctor as coordination
from specify_cli.cli.commands import _identity_audit as identity_audit
from specify_cli.cli.commands import _review_cycle_reconcile_doctor as review_cycle
from specify_cli.cli.commands import materialize as materialize_command
from specify_cli.release.changelog import build_changelog_block
from tests._support.mission_residue_fixture import (
    MISSION_SLUG,
    RESIDUE_SLUG,
    seed_mission_and_residue,
    seed_tracked_idless_missions,
    spy_on_tracked_paths,
)

pytestmark = [pytest.mark.regression, pytest.mark.integration, pytest.mark.git_repo]


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
    calls = spy_on_tracked_paths(monkeypatch)

    rows = identity_audit._collect_topology_rows(tmp_path, None)

    assert sorted(row["slug"] for row in rows) == sorted(child.name for child in children)
    assert len(calls) <= 1, f"one TrackedMissionPaths memo per walk, not one probe per child: {calls}"


def test_collect_topology_rows_probes_git_at_all_only_when_needed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A walk whose children all carry a ``mission_id`` (or none at all) makes no git call."""
    seed_mission_and_residue(tmp_path)
    calls = spy_on_tracked_paths(monkeypatch)

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


def test_mission_dirs_to_process_skips_residue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``materialize`` targets Missions only, and never probes a coordination surface for residue."""
    fixture = seed_mission_and_residue(tmp_path)
    calls = spy_on_tracked_paths(monkeypatch)

    errors: list[str] = []
    targets = materialize_command._mission_dirs_to_process(tmp_path, fixture.repo_root / "kitty-specs", errors)

    assert [slug for slug, _status_dir in targets] == [MISSION_SLUG]
    assert errors == [], "a residue child must not produce a resolution error entry"
    assert len(calls) <= 1, f"one TrackedMissionPaths memo per walk, not one probe per child: {calls}"


def test_mission_dirs_to_process_keeps_tracked_idless_missions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An id-less Mission git tracks is still materialized, on one git probe for the walk."""
    children = seed_tracked_idless_missions(tmp_path)
    calls = spy_on_tracked_paths(monkeypatch)

    targets = materialize_command._mission_dirs_to_process(tmp_path, tmp_path / "kitty-specs", [])

    assert sorted(slug for slug, _status_dir in targets) == sorted(child.name for child in children)
    assert len(calls) <= 1


def test_collect_inflight_missions_skips_residue(tmp_path: Path) -> None:
    """The charter-activate in-flight warning names Missions only."""
    fixture = seed_mission_and_residue(tmp_path)

    affected = _collect_inflight_missions(fixture.repo_root / "kitty-specs")

    assert {mission.mission_slug for mission in affected} == {MISSION_SLUG}
    assert all(mission.mission_slug != RESIDUE_SLUG for mission in affected)


def test_changelog_excludes_residue_folder(tmp_path: Path) -> None:
    """The release-changelog block lists Missions only."""
    seed_mission_and_residue(tmp_path)

    changelog, slugs = build_changelog_block(tmp_path, since_tag=None)

    assert slugs == [MISSION_SLUG]
    assert RESIDUE_SLUG not in changelog
