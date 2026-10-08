"""FR-006 / #1771 regression: the retrospective record must be committable.

Before the cycle-2 relocation, ``retrospect create`` wrote the record to
``.kittify/missions/<mission_id>/retrospective.yaml`` — a path matched by the
``.kittify/missions/`` rule in ``.gitignore`` (line 61). The record was therefore
silently discarded on checkout/clone and uncommittable without ``git add -f``.

These tests prove the record now lands in the tracked feature_dir
(``kitty-specs/<slug>/retrospective.yaml``) and is NOT git-ignored, by running
``git check-ignore`` against a repo carrying the real ignore rule.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.retrospective.writer import (
    canonical_record_path,
    _legacy_record_path,
    write_record,
)

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

# Reuse the canonical fixture record from the round-trip suite.
from tests.retrospective.test_schema_roundtrip import make_completed_record  # noqa: E402


def _init_repo_with_gitignore(root: Path) -> None:
    """Initialise a git repo that ignores the .kittify tree like the real project."""
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    # The load-bearing rule from the project .gitignore (line 61).
    (root / ".gitignore").write_text(".kittify/missions/\n", encoding="utf-8")


def _is_git_ignored(root: Path, path: Path) -> bool:
    """Return True if *path* is matched by .gitignore (git check-ignore exit 0)."""
    rel = path.relative_to(root)
    result = subprocess.run(
        ["git", "check-ignore", str(rel)],
        cwd=root,
        capture_output=True,
    )
    # Exit 0 → ignored; exit 1 → not ignored (committable).
    return result.returncode == 0


def test_canonical_record_path_is_not_gitignored(tmp_path: Path) -> None:
    """The resolved record path is committable (NOT matched by .gitignore)."""
    _init_repo_with_gitignore(tmp_path)
    record = make_completed_record()

    record_path = canonical_record_path(tmp_path, record.mission.mission_slug)

    assert "kitty-specs" in record_path.parts
    assert ".kittify" not in record_path.parts
    assert not _is_git_ignored(tmp_path, record_path), (
        f"Retrospective record path {record_path} is git-ignored — #1771 regression"
    )


# Production-shaped identity for the coord-divergence re-pin (real ULID + mid8).
_COORD_MISSION_ID = "01KVYM1WQ4D5E6F7G8H9J0K1M2"
_COORD_MID8 = _COORD_MISSION_ID[:8]  # "01KVYM1W"
_COORD_SLUG_WITH_MID8 = f"record-committable-{_COORD_MID8}"


def _seed_divergent_coord_topology(repo_root: Path) -> None:
    """Materialize a coord mission: composed PRIMARY dir + a coord husk lacking meta.

    The #1771 trap shape (NFR-002 / DIR-041 re-pin): the primary ``meta.json``
    declares a ``coordination_branch`` + COORD topology, and the materialized coord
    worktree mission dir LACKS ``meta.json`` / ``lanes.json`` — so the coord surface
    genuinely diverges from primary. On this fixture the OLD coord-aware resolver
    leaks into ``.worktrees``; the durable-home authority must not.
    """
    from mission_runtime import MissionTopology
    from tests._meta_write_support import write_meta_canonical as _write_meta_canonical
    from specify_cli.missions._read_path_resolver import coord_feature_dir

    meta: dict[str, object] = {
        "mission_id": _COORD_MISSION_ID,
        "mid8": _COORD_MID8,
        "mission_slug": _COORD_SLUG_WITH_MID8,
        "coordination_branch": f"kitty/mission-{_COORD_SLUG_WITH_MID8}",
        "topology": MissionTopology.COORD.value,
    }
    primary_dir = repo_root / "kitty-specs" / _COORD_SLUG_WITH_MID8
    primary_dir.mkdir(parents=True, exist_ok=True)
    _write_meta_canonical(primary_dir / "meta.json", meta)

    coord_mission_dir = coord_feature_dir(repo_root, _COORD_SLUG_WITH_MID8, _COORD_MID8)
    coord_mission_dir.mkdir(parents=True, exist_ok=True)
    (coord_mission_dir / "status.json").write_text("{}\n", encoding="utf-8")
    assert not (coord_mission_dir / "meta.json").exists()
    assert not (coord_mission_dir / "lanes.json").exists()


def test_canonical_record_path_does_not_leak_into_coord_worktree(tmp_path: Path) -> None:
    """DIR-041 re-pin: the record path stays in the durable home under coord topology.

    The original ``"kitty-specs" in parts`` assertion above is a #1771 FALSE-GREEN
    on its own — it is true for BOTH the durable home AND a
    ``.worktrees/<slug>-coord/kitty-specs/...`` husk path, so it passes even when
    the record re-homes into the coord worktree. This re-pin drives a
    genuinely-divergent coord fixture and strengthens the contract to ALSO require
    ``".worktrees" not in record_path.parts`` — the record must NOT leak into the
    ephemeral coord worktree.
    """
    _init_repo_with_gitignore(tmp_path)
    _seed_divergent_coord_topology(tmp_path)

    record_path = canonical_record_path(tmp_path, _COORD_SLUG_WITH_MID8)

    # The strengthened guard: ``kitty-specs in parts`` ALONE is insufficient.
    assert "kitty-specs" in record_path.parts
    assert ".worktrees" not in record_path.parts, (
        f"Retrospective record path {record_path} re-homed into the coord "
        "worktree — the #1771 coord-leak the durable-home authority must cure."
    )
    assert ".kittify" not in record_path.parts
    assert not _is_git_ignored(tmp_path, record_path)
    expected = tmp_path / "kitty-specs" / _COORD_SLUG_WITH_MID8 / "retrospective.yaml"
    assert record_path.resolve() == expected.resolve()


def test_legacy_path_was_gitignored_control(tmp_path: Path) -> None:
    """Control: the OLD .kittify/missions/ path IS git-ignored (the original bug)."""
    _init_repo_with_gitignore(tmp_path)

    legacy = _legacy_record_path(tmp_path, "01KQ6YEGT4YBZ3GZF7X680KQ3V")

    assert _is_git_ignored(tmp_path, legacy), (
        "The legacy .kittify/missions/ path should be git-ignored — proves the "
        "relocation actually moves the record off an ignored path."
    )


def test_written_record_is_committable_end_to_end(tmp_path: Path) -> None:
    """write_record() lands the record where git can stage it (committable)."""
    _init_repo_with_gitignore(tmp_path)
    record = make_completed_record()

    written = write_record(record, repo_root=tmp_path)

    assert written.exists()
    assert not _is_git_ignored(tmp_path, written)

    # git add must actually stage it (no -f). A gitignored path would not stage.
    subprocess.run(
        ["git", "add", str(written.relative_to(tmp_path))],
        cwd=tmp_path,
        check=True,
    )
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "retrospective.yaml" in staged, (
        "Record was not staged — it is uncommittable (#1771 regression)"
    )
