"""Red-first tests for the ledger adoption baseline and the ``--target`` cap (#6431).

A pre-ledger project's ``metadata.yaml`` lists only the migrations that ran
since it was set up: pre-ledger ``init`` stamped ``version`` and wrote
``applied: []``, and the retired version window never selected a migration at
or below that version. Backfilling the list alone therefore left every older
migration pending, and the first ledger-era upgrade replayed them against a
current project (#6431: Mission ``meta.json`` / ``status.json`` rewritten, a
forced lane transition undone by ``3.0.0_canonical_context``).

These tests pin the adoption baseline (first adoption only, partition-correct,
never overriding a recorded ``skipped``/``failed`` result), the shared
clone-local "effect in place" predicate (no git repository means not in place),
and the run's requested target as an upper bound on selection.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.upgrade.init_seed import seed_migration_ledger_for_init
from specify_cli.upgrade.ledger import MigrationLedger, build_record, clone_local_effect_in_place
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.migrations.m_4_0_0rc8_backfill_migration_ledger import (
    BackfillMigrationLedgerMigration,
)
from specify_cli.upgrade.registry import MigrationRegistry, _within_target, migration_settled

_RECORDED_VERSION = "3.2.0"
_BELOW = "0.2.0_specify_to_kittify"
_LISTED_SKIPPED = "0.4.8_gitignore_agents"
_ABOVE = "4_0_0rc5_heal_run_index_paths"
_CLONE_LOCAL_BELOW = "0.13.1_exclude_worktrees"
_RC8_LATER = "4.0.0rc8_project_intent_directive_rename"


def _metadata(version: str, applied: str = " []\n") -> str:
    return f"spec_kitty:\n  version: '{version}'\n  initialized_at: '2026-01-01T00:00:00+00:00'\nmigrations:\n  applied:{applied}"


def _project(tmp_path: Path, version: str = _RECORDED_VERSION, applied: str = " []\n", *, git: bool = False) -> Path:
    auto_discover_migrations()
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True)
    (kittify / "metadata.yaml").write_text(_metadata(version, applied), encoding="utf-8")
    if git:
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path


def _tracked(project: Path) -> dict[str, str]:
    return {record.id: record.result for record in MigrationLedger(project).read_tracked()}


def _registered(migration_id: str) -> object:
    migration = MigrationRegistry.get_by_id(migration_id)
    assert migration is not None, f"{migration_id} must be a registered migration for this test to mean anything"
    return migration


# -- adoption baseline --------------------------------------------------------- #


def test_empty_applied_list_settles_every_tracked_migration_below_the_version(tmp_path: Path) -> None:
    project = _project(tmp_path)

    BackfillMigrationLedgerMigration().apply(project)

    ledger = MigrationLedger(project)
    assert migration_settled(ledger, _registered(_BELOW))  # type: ignore[arg-type]
    assert not migration_settled(ledger, _registered(_ABOVE))  # type: ignore[arg-type]
    below = [m for m in MigrationRegistry.get_all() if not m.clone_local_effect and m.migration_id != BackfillMigrationLedgerMigration.migration_id]
    from packaging.version import Version

    expected = {m.migration_id for m in below if Version(m.target_version) < Version(_RECORDED_VERSION)}
    assert expected <= set(_tracked(project))


def test_a_migration_at_the_recorded_version_stays_pending(tmp_path: Path) -> None:
    """The retired window still selected a same-version migration when its detect() held."""
    at_version = next(m for m in MigrationRegistry.get_all() if m.target_version == "3.2.4" and not m.clone_local_effect)
    project = _project(tmp_path, version="3.2.4")

    BackfillMigrationLedgerMigration().apply(project)

    assert at_version.migration_id not in _tracked(project)
    assert _tracked(project)[_BELOW] == "success"


def test_a_listed_skipped_record_keeps_its_result(tmp_path: Path) -> None:
    """The baseline never overrides a recorded result: a skipped one stays re-evaluable."""
    applied = f"\n  - id: {_LISTED_SKIPPED}\n    applied_at: '2026-01-01T00:00:00+00:00'\n    result: skipped\n"
    project = _project(tmp_path, applied=applied)

    BackfillMigrationLedgerMigration().apply(project)

    assert _tracked(project)[_LISTED_SKIPPED] == "skipped"
    assert _tracked(project)[_BELOW] == "success"


def test_a_listed_failed_record_stays_retriable(tmp_path: Path) -> None:
    applied = f"\n  - id: {_BELOW}\n    applied_at: '2026-01-01T00:00:00+00:00'\n    result: failed\n"
    project = _project(tmp_path, applied=applied)

    BackfillMigrationLedgerMigration().apply(project)

    assert _tracked(project)[_BELOW] == "failed"
    assert not migration_settled(MigrationLedger(project), _registered(_BELOW))  # type: ignore[arg-type]


def test_no_baseline_once_the_adoption_is_recorded(tmp_path: Path) -> None:
    """The floor is a one-time adoption stamp, never a revived selection window."""
    project = _project(tmp_path)
    migration = BackfillMigrationLedgerMigration()
    MigrationLedger(project).append(build_record(migration, "success"))

    assert migration.detect(project) is False
    migration.apply(project)
    assert set(_tracked(project)) == {migration.migration_id}


def test_a_lone_clone_local_ledger_does_not_suppress_the_baseline(tmp_path: Path) -> None:
    """A gitignored per-clone ledger survives a checkout of a pre-ledger branch; it is not adoption."""
    project = _project(tmp_path)
    MigrationLedger(project).clone_local_path.parent.mkdir(parents=True, exist_ok=True)
    MigrationLedger(project).clone_local_path.write_text("", encoding="utf-8")

    BackfillMigrationLedgerMigration().apply(project)

    assert _tracked(project)[_BELOW] == "success"


def test_an_rc8_stamp_does_not_settle_rc8_migrations(tmp_path: Path) -> None:
    """An rc8 build that predates the ledger never had the later rc8 migrations; they stay pending."""
    project = _project(tmp_path, version="4.0.0rc8")

    BackfillMigrationLedgerMigration().apply(project)

    assert _RC8_LATER not in _tracked(project)
    assert _tracked(project)[_BELOW] == "success"


# -- selection matches what the real run applies -------------------------------- #


@pytest.mark.parametrize("adopted", [False, True], ids=["before-apply", "after-apply"])
def test_selection_on_a_pre_ledger_project_skips_what_adoption_will_settle(tmp_path: Path, adopted: bool) -> None:
    """A preview or dry run lists only what the real run applies (no ~120 replays, then skips).

    After the real apply, the same migrations are settled and newer ones stay pending.
    """
    project = _project(tmp_path)
    if adopted:
        BackfillMigrationLedgerMigration().apply(project)

    selected = {m.migration_id for m in MigrationRegistry.get_applicable(_RECORDED_VERSION, "99.0.0", project)}

    if not adopted:
        assert BackfillMigrationLedgerMigration.migration_id in selected
    assert _BELOW not in selected
    assert _ABOVE in selected


def test_an_older_target_still_selects_the_adoption(tmp_path: Path) -> None:
    """``--target`` below the backfill's own version must not skip adoption, or its records would hide it for good."""
    project = _project(tmp_path, version="4.0.0rc3")

    selected = {m.migration_id for m in MigrationRegistry.get_applicable("4.0.0rc3", "4.0.0rc5", project)}

    assert BackfillMigrationLedgerMigration.migration_id in selected
    assert _BELOW not in selected


def test_unparseable_recorded_version_stamps_nothing(tmp_path: Path) -> None:
    project = _project(tmp_path, version="not-a-version")

    migration = BackfillMigrationLedgerMigration()

    assert migration.detect(project) is False
    migration.apply(project)
    assert MigrationLedger(project).read_tracked() == []


def test_backfill_is_idempotent_after_the_baseline(tmp_path: Path) -> None:
    project = _project(tmp_path)
    migration = BackfillMigrationLedgerMigration()
    migration.apply(project)
    before = MigrationLedger(project).tracked_path.read_text(encoding="utf-8")

    assert migration.detect(project) is False
    migration.apply(project)

    assert MigrationLedger(project).tracked_path.read_text(encoding="utf-8") == before


def test_clone_local_below_the_version_is_not_baselined_without_git(tmp_path: Path) -> None:
    project = _project(tmp_path)

    BackfillMigrationLedgerMigration().apply(project)

    assert MigrationLedger(project).read_clone_local() == []
    assert _CLONE_LOCAL_BELOW not in _tracked(project)


def test_clone_local_below_the_version_is_baselined_only_where_its_effect_is_present(tmp_path: Path) -> None:
    present = _project(tmp_path / "present", git=True)
    _registered(_CLONE_LOCAL_BELOW).apply(present)  # type: ignore[attr-defined]
    absent = _project(tmp_path / "absent", git=True)

    BackfillMigrationLedgerMigration().apply(present)
    BackfillMigrationLedgerMigration().apply(absent)

    assert _CLONE_LOCAL_BELOW in {r.id for r in MigrationLedger(present).read_clone_local()}
    assert _CLONE_LOCAL_BELOW not in {r.id for r in MigrationLedger(absent).read_clone_local()}
    assert _CLONE_LOCAL_BELOW not in _tracked(present), "a clone-local record never lands in the tracked partition"


# -- the shared clone-local predicate ----------------------------------------- #


class _Probe:
    clone_local_effect = True

    def __init__(self, detected: bool | Exception) -> None:
        self._detected = detected

    def detect(self, project_path: Path) -> bool:  # noqa: ARG002 - stub
        if isinstance(self._detected, Exception):
            raise self._detected
        return self._detected


def test_effect_is_not_in_place_without_a_git_repository(tmp_path: Path) -> None:
    assert clone_local_effect_in_place(_Probe(False), tmp_path) is False


def test_effect_is_in_place_when_detect_reports_nothing_to_do_in_a_repository(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)

    assert clone_local_effect_in_place(_Probe(False), tmp_path) is True
    assert clone_local_effect_in_place(_Probe(True), tmp_path) is False


def test_a_failing_detect_reads_as_not_in_place(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)

    assert clone_local_effect_in_place(_Probe(IsADirectoryError("probe")), tmp_path) is False
    assert clone_local_effect_in_place(object(), tmp_path) is False


def test_init_seed_outside_git_leaves_every_clone_local_migration_pending(tmp_path: Path) -> None:
    """``init`` before ``git init``: the first upgrade after ``git init`` must apply the local setup."""
    (tmp_path / ".kittify").mkdir()

    seeded = set(seed_migration_ledger_for_init(tmp_path))

    clone_local_ids = {m.migration_id for m in MigrationRegistry.get_all() if m.clone_local_effect}
    assert clone_local_ids, "the registry declares clone-local migrations"
    assert not seeded & clone_local_ids
    assert MigrationLedger(tmp_path).read_clone_local() == []


# -- the run's requested target caps selection --------------------------------- #


@pytest.mark.parametrize("target", ["1.0.0a1", _RECORDED_VERSION])
def test_selection_excludes_migrations_above_the_requested_target(tmp_path: Path, target: str) -> None:
    auto_discover_migrations()
    from packaging.version import Version

    selected = MigrationRegistry.get_applicable(target, target, tmp_path)

    assert selected, "an empty ledger leaves migrations at or below the target pending"
    assert all(Version(m.target_version) <= Version(target) for m in selected if not m.ledger_adoption)


def test_an_unparseable_target_caps_nothing() -> None:
    auto_discover_migrations()

    assert len(MigrationRegistry.get_applicable("0.0.0", "not-a-version")) == len(MigrationRegistry.get_all())


@pytest.mark.parametrize("declared", ["not-a-version", None])
def test_a_migration_with_an_unparseable_own_version_is_never_capped(declared: object) -> None:
    """get_all() sorts by version so the registry cannot hold one; the cap itself must still keep it."""

    class _Stub:
        target_version = declared

    assert _within_target(_Stub(), "0.0.1") is True  # type: ignore[arg-type]
