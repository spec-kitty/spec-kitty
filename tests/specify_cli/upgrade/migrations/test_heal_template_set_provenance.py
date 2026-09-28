"""Forward migration tests for legacy built-in template-set provenance."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
from typing import Any

import pytest
from ruamel.yaml import YAML

from specify_cli.upgrade.migrations import m_4_0_0rc5_heal_template_set_provenance as provenance_migration
from specify_cli.upgrade.migrations.m_4_0_0rc5_heal_template_set_provenance import (
    MIGRATION_ID,
    TARGET_VERSION,
    HealTemplateSetProvenanceMigration,
    describe_template_set_ambiguities,
    _matches_mission_source,
)
from specify_cli.upgrade.registry import MigrationRegistry
from charter.offering.provenance import is_built_in_pack_path

pytestmark = [pytest.mark.unit]


@pytest.fixture
def packs_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "packs"
    (root / "built-in" / "missions" / "software-dev").mkdir(parents=True)
    monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(root))
    return root


def _charter_path(project_root: Path) -> Path:
    return project_root / ".kittify" / "charter" / "charter.yaml"


def _write_charter(path: Path, refs: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    YAML().dump(
        {
            "schema_version": "2.0.0",
            "governance": {"testing": {}},
            "directives": [],
            "catalog": {
                "mission": "software-dev",
                "template_set": "software-dev-default",
                "languages": [],
                "references": refs,
            },
            "overrides": {},
            "metadata": {"bundle_schema_version": 2},
        },
        path.open("w", encoding="utf-8"),
    )


def _template_ref(source_path: str) -> dict[str, str]:
    return {
        "id": "TEMPLATE_SET:software-dev-default",
        "kind": "template_set",
        "title": "software-dev-default",
        "summary": "Built-in template set",
        "source_path": source_path,
        "local_path": "_LIBRARY/template-set-software-dev-default.md",
    }


def _former_checkout_source(checkout: Path, *, remove_source: bool = False) -> Path:
    """Create a verifiable former Spec Kitty checkout containing the source."""
    source = checkout / "packs" / "built-in" / "missions" / "software-dev" / "mission.yaml"
    source.parent.mkdir(parents=True)
    source.write_text("name: software-dev\ndescription: Tracked built-in mission.\n", encoding="utf-8")
    (checkout / "pyproject.toml").write_text(
        '[project]\nname = "spec-kitty-cli"\n\n[project.urls]\nRepository = "https://github.com/spec-kitty/spec-kitty"\n',
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "--quiet", str(checkout)], check=True)
    subprocess.run(
        ["git", "-C", str(checkout), "remote", "add", "origin", "https://github.com/spec-kitty/spec-kitty.git"],
        check=True,
    )
    subprocess.run(["git", "-C", str(checkout), "add", "pyproject.toml", "packs/built-in/missions/software-dev/mission.yaml"], check=True)
    if remove_source:
        source.unlink()
    return source


def test_forward_migration_is_registered_at_current_release_version() -> None:
    migration = MigrationRegistry.get_by_id(MIGRATION_ID)

    assert migration is not None
    assert migration.target_version == TARGET_VERSION == "4.0.0rc5"
    assert migration.runs_on_worktrees is False


def test_current_version_project_still_selects_new_migration_when_needed(tmp_path: Path, packs_root: Path) -> None:
    path = packs_root / "built-in" / "missions" / "software-dev" / "mission.yaml"
    _write_charter(_charter_path(tmp_path), [_template_ref(str(path))])

    applicable = MigrationRegistry.get_applicable(TARGET_VERSION, TARGET_VERSION, tmp_path)

    assert any(migration.migration_id == MIGRATION_ID for migration in applicable)


def test_template_set_migration_rewrites_only_builtin_absolute_source(tmp_path: Path, packs_root: Path) -> None:
    abs_source = packs_root / "built-in" / "missions" / "software-dev" / "mission.yaml"
    abs_paradigm = packs_root / "built-in" / "paradigms" / "atomic-design.yaml"
    charter_path = _charter_path(tmp_path)
    _write_charter(
        charter_path,
        [
            _template_ref(str(abs_source)),
            {
                "id": "PARADIGM:atomic-design",
                "kind": "paradigm",
                "title": "Atomic Design",
                "summary": "other migration owns this row",
                "source_path": str(abs_paradigm),
                "local_path": "_LIBRARY/paradigm-atomic-design.md",
            },
        ],
    )
    migration = HealTemplateSetProvenanceMigration()

    assert migration.detect(tmp_path) is True
    result = migration.apply(tmp_path)

    data = YAML(typ="safe").load(charter_path.read_text(encoding="utf-8"))
    refs = {ref["id"]: ref for ref in data["catalog"]["references"]}
    assert result.success is True
    assert len(result.changes_made) == 1
    assert refs["TEMPLATE_SET:software-dev-default"]["source_path"] == ("${SPEC_KITTY_PACKS_ROOT}/built-in/missions/software-dev/mission.yaml")
    assert refs["PARADIGM:atomic-design"]["source_path"] == str(abs_paradigm)


def test_template_set_migration_recognizes_missing_path_from_another_checkout(tmp_path: Path, packs_root: Path) -> None:
    stale_source = _former_checkout_source(tmp_path / "former-checkout", remove_source=True)
    charter_path = _charter_path(tmp_path)
    _write_charter(charter_path, [_template_ref(str(stale_source))])
    migration = HealTemplateSetProvenanceMigration()

    assert not stale_source.exists()
    assert migration.detect(tmp_path) is True
    result = migration.apply(tmp_path)
    data = YAML(typ="safe").load(charter_path.read_text(encoding="utf-8"))
    assert result.success is True
    assert data["catalog"]["references"][0]["source_path"] == ("${SPEC_KITTY_PACKS_ROOT}/built-in/missions/software-dev/mission.yaml")


def test_template_set_migration_repairs_path_while_former_checkout_still_exists(tmp_path: Path, packs_root: Path) -> None:
    stale_source = _former_checkout_source(tmp_path / "former-checkout")
    charter_path = _charter_path(tmp_path)
    _write_charter(charter_path, [_template_ref(str(stale_source))])
    migration = HealTemplateSetProvenanceMigration()

    assert migration.detect(tmp_path) is True
    assert migration.apply(tmp_path).success is True
    data = YAML(typ="safe").load(charter_path.read_text(encoding="utf-8"))
    assert data["catalog"]["references"][0]["source_path"] == ("${SPEC_KITTY_PACKS_ROOT}/built-in/missions/software-dev/mission.yaml")


def test_template_set_migration_rejects_symlinked_former_checkout_root(tmp_path: Path, packs_root: Path) -> None:
    real_checkout = tmp_path / "external-authority" / "former-checkout"
    _former_checkout_source(real_checkout)
    checkout_alias = tmp_path / "former-checkout"
    checkout_alias.symlink_to(real_checkout, target_is_directory=True)
    stale_source = checkout_alias / "packs" / "built-in" / "missions" / "software-dev" / "mission.yaml"
    token = "${SPEC_KITTY_PACKS_ROOT}/built-in/missions/software-dev/mission.yaml"
    charter_path = _charter_path(tmp_path)
    _write_charter(charter_path, [_template_ref(str(stale_source))])
    original = charter_path.read_text(encoding="utf-8")
    migration = HealTemplateSetProvenanceMigration()

    assert stale_source.is_file()
    assert _matches_mission_source(str(stale_source), token) is False
    assert migration.detect(tmp_path) is False
    assert migration.apply(tmp_path, dry_run=True).changes_made == []
    assert migration.apply(tmp_path).changes_made == []
    assert charter_path.read_text(encoding="utf-8") == original


@pytest.mark.parametrize("classification", ["classifier", "detect", "dry_run"])
def test_template_set_migration_rejects_file_swapped_to_symlink_during_git_query(
    tmp_path: Path,
    packs_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    classification: str,
) -> None:
    checkout = tmp_path / "former-checkout"
    stale_source = _former_checkout_source(checkout)
    external = tmp_path / "external-authority.yaml"
    external.write_text("name: mutable-external-authority\n", encoding="utf-8")
    charter_path = _charter_path(tmp_path)
    _write_charter(charter_path, [_template_ref(str(stale_source))])
    migration = HealTemplateSetProvenanceMigration()
    original_run = subprocess.run
    swapped = False

    def swap_source_after_git_query(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        nonlocal swapped
        result = original_run(*args, **kwargs)
        command = args[0] if args else kwargs.get("args")
        if not swapped and isinstance(command, list) and "ls-files" in command:
            stale_source.unlink()
            stale_source.symlink_to(external)
            swapped = True
        return result

    monkeypatch.setattr(provenance_migration.subprocess, "run", swap_source_after_git_query)
    token = "${SPEC_KITTY_PACKS_ROOT}/built-in/missions/software-dev/mission.yaml"

    if classification == "classifier":
        result = _matches_mission_source(str(stale_source), token)
    elif classification == "detect":
        result = migration.detect(tmp_path)
    else:
        result = bool(migration.apply(tmp_path, dry_run=True).changes_made)

    assert swapped is True
    assert stale_source.is_symlink()
    assert result is False


@pytest.mark.parametrize(
    ("symlink_component", "expected_index_mode"),
    [("mission.yaml", "120000"), ("missions", "100644")],
)
def test_template_set_migration_rejects_symlinked_former_checkout_paths(
    tmp_path: Path,
    packs_root: Path,
    symlink_component: str,
    expected_index_mode: str,
) -> None:
    checkout = tmp_path / "former-checkout"
    stale_source = _former_checkout_source(checkout)
    relative_source = stale_source.relative_to(checkout).as_posix()
    external_source = tmp_path / "external-authority" / "missions" / "software-dev" / "mission.yaml"
    external_source.parent.mkdir(parents=True)
    external_source.write_text("name: mutable-external-authority\n", encoding="utf-8")

    if symlink_component == "mission.yaml":
        stale_source.unlink()
        stale_source.symlink_to(external_source)
        subprocess.run(["git", "-C", str(checkout), "add", "--", relative_source], check=True)
    else:
        missions_root = stale_source.parents[1]
        shutil.rmtree(missions_root)
        missions_root.symlink_to(external_source.parents[1], target_is_directory=True)

    index_entry = subprocess.run(
        ["git", "-C", str(checkout), "ls-files", "--stage", "--", relative_source],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert index_entry.split()[0] == expected_index_mode

    charter_path = _charter_path(tmp_path)
    _write_charter(charter_path, [_template_ref(str(stale_source))])
    original = charter_path.read_text(encoding="utf-8")
    migration = HealTemplateSetProvenanceMigration()
    dry_run = migration.apply(tmp_path, dry_run=True)
    ambiguities = describe_template_set_ambiguities(tmp_path)

    assert (
        migration.detect(tmp_path),
        dry_run.changes_made,
        len(ambiguities),
    ) == (False, [], 1)
    assert "ambiguous" in ambiguities[0]

    result = migration.apply(tmp_path)
    assert result.success is True
    assert result.changes_made == []
    assert charter_path.read_text(encoding="utf-8") == original


def test_template_set_migration_is_dry_run_safe_and_idempotent(tmp_path: Path, packs_root: Path) -> None:
    abs_source = packs_root / "built-in" / "missions" / "software-dev" / "mission.yaml"
    charter_path = _charter_path(tmp_path)
    _write_charter(charter_path, [_template_ref(str(abs_source))])
    original = charter_path.read_text(encoding="utf-8")
    migration = HealTemplateSetProvenanceMigration()

    dry_run = migration.apply(tmp_path, dry_run=True)
    assert dry_run.changes_made
    assert charter_path.read_text(encoding="utf-8") == original

    migration.apply(tmp_path)
    assert migration.detect(tmp_path) is False
    assert migration.apply(tmp_path).changes_made == []


def test_external_template_set_path_is_preserved_without_healing(tmp_path: Path, packs_root: Path) -> None:
    external = tmp_path / "external-authority" / "packs" / "built-in" / "missions" / "software-dev" / "mission.yaml"
    external.parent.mkdir(parents=True)
    external.write_text("name: unrelated-mutable-mission\ndescription: Keep this authority.\n", encoding="utf-8")
    charter_path = _charter_path(tmp_path)
    _write_charter(charter_path, [_template_ref(str(external))])
    migration = HealTemplateSetProvenanceMigration()

    token = "${SPEC_KITTY_PACKS_ROOT}/built-in/missions/software-dev/mission.yaml"
    assert external.is_file()
    assert is_built_in_pack_path(external) is False
    assert _matches_mission_source(str(external), token) is False
    assert migration.detect(tmp_path) is False
    assert migration.apply(tmp_path).changes_made == []
    data = YAML(typ="safe").load(charter_path.read_text(encoding="utf-8"))
    assert data["catalog"]["references"][0]["source_path"] == str(external)


def test_missing_template_path_without_checkout_evidence_stays_ambiguous(tmp_path: Path, packs_root: Path) -> None:
    from specify_cli.upgrade.migrations.m_4_0_0rc5_heal_template_set_provenance import describe_template_set_ambiguities

    stale_source = tmp_path / "former-checkout" / "packs" / "built-in" / "missions" / "software-dev" / "mission.yaml"
    charter_path = _charter_path(tmp_path)
    _write_charter(charter_path, [_template_ref(str(stale_source))])
    migration = HealTemplateSetProvenanceMigration()

    assert not stale_source.exists()
    assert migration.detect(tmp_path) is False
    result = migration.apply(tmp_path)
    data = YAML(typ="safe").load(charter_path.read_text(encoding="utf-8"))

    assert result.success is True
    assert result.changes_made == []
    assert data["catalog"]["references"][0]["source_path"] == str(stale_source)
    assert "ambiguous" in describe_template_set_ambiguities(tmp_path)[0]


@pytest.fixture
def registry_restore() -> Any:
    original = MigrationRegistry._migrations.copy()
    yield
    MigrationRegistry._migrations = original


@pytest.mark.parametrize(
    ("from_version", "target_version"),
    [("4.0.0rc4", "4.0.0rc5"), ("4.0.0rc5", "4.0.0rc6")],
    ids=["upgrade-into-rc5", "upgrade-past-rc5"],
)
def test_unreadable_charter_fails_the_upgrade_closed_without_stamping(
    tmp_path: Path, packs_root: Path, registry_restore: Any, from_version: str, target_version: str
) -> None:
    """An unreadable charter.yaml must fail the upgrade, never skip this migration.

    A "skipped" verdict would let the runner stamp the target version, and
    ``get_applicable`` never reconsiders an older migration once the project is
    past it: the legacy path would stay committed after the charter is
    repaired. ``detect`` raises ``MigrationStateUnreadableError`` instead, the
    runner records a failure and leaves the version where it was, and once the
    charter is repaired the next upgrade heals the stale path.
    """
    from kernel.clock import now_utc  # noqa: PLC0415

    from specify_cli.upgrade.metadata import ProjectMetadata  # noqa: PLC0415
    from specify_cli.upgrade.runner import MigrationRunner  # noqa: PLC0415

    kittify_dir = tmp_path / ".kittify"
    kittify_dir.mkdir()
    ProjectMetadata(
        version=from_version,
        initialized_at=now_utc(),
        python_version="3.11",
        platform="test",
        platform_version="test",
    ).save(kittify_dir)
    charter_path = _charter_path(tmp_path)
    charter_path.parent.mkdir(parents=True)
    charter_path.write_bytes(b"catalog: [unclosed\n")
    MigrationRegistry.clear()
    MigrationRegistry.register(HealTemplateSetProvenanceMigration)

    result = MigrationRunner(tmp_path).upgrade(target_version, include_worktrees=False, force=True)

    assert not result.success
    assert any(MIGRATION_ID in error for error in result.errors)
    assert MIGRATION_ID not in result.migrations_skipped
    reloaded = ProjectMetadata.load(kittify_dir)
    assert reloaded is not None
    assert reloaded.version == from_version
    assert charter_path.read_bytes() == b"catalog: [unclosed\n"

    stale_source = packs_root / "built-in" / "missions" / "software-dev" / "mission.yaml"
    _write_charter(charter_path, [_template_ref(str(stale_source))])

    retried = MigrationRunner(tmp_path).upgrade(target_version, include_worktrees=False, force=True)

    assert retried.success, retried.errors
    assert MIGRATION_ID in retried.migrations_applied
    healed = YAML().load(charter_path.read_text(encoding="utf-8"))
    assert healed["catalog"]["references"][0]["source_path"] == "${SPEC_KITTY_PACKS_ROOT}/built-in/missions/software-dev/mission.yaml"
