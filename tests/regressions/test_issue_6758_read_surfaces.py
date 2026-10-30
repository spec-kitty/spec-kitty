"""Issue #6758: the remaining read surfaces ask the one read-side Mission predicate.

``materialize``, the charter-activate in-flight warning and the release-changelog
block each enumerate every directory child of ``kitty-specs/`` and decided for
themselves whether the child was a Mission. A leftover folder holding a
``spec.md`` and a ``tasks/`` tree (read-side residue: no ``meta.json``) was
therefore materialized, warned about and published in the release notes.

Every test runs on the shared fixture — a Mission beside that residue child, both
carrying an accepted ``WP01`` task file and an in-flight ``WP02`` status event —
so each absence assertion is paired with a positive control on the same tree and
would fail on a walker-local rule.

Git is real (``git init`` + commit) because file-presence mode would classify
the residue child as a Mission; hence ``git_repo`` and not the ``fast`` tier.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.charter_activate import _collect_inflight_missions
from specify_cli.cli.commands import materialize as materialize_command
from specify_cli.context import mission_resolver
from specify_cli.release.changelog import build_changelog_block
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


def test_mission_dirs_to_process_skips_residue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``materialize`` targets Missions only, and never probes a coordination surface for residue."""
    fixture = seed_mission_and_residue(tmp_path)
    calls = _spy_on_tracked_paths(monkeypatch)

    errors: list[str] = []
    targets = materialize_command._mission_dirs_to_process(tmp_path, fixture.repo_root / "kitty-specs", errors)

    assert [slug for slug, _status_dir in targets] == [MISSION_SLUG]
    assert errors == [], "a residue child must not produce a resolution error entry"
    assert len(calls) <= 1, f"one TrackedMissionPaths memo per walk, not one probe per child: {calls}"


def test_mission_dirs_to_process_keeps_tracked_idless_missions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An id-less Mission git tracks is still materialized, on one git probe for the walk."""
    children = seed_tracked_idless_missions(tmp_path)
    calls = _spy_on_tracked_paths(monkeypatch)

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
