"""Tests for ``m_unify_charter_activation_finalize`` (migration_id consolidate_charter_bundle_fold) (WP07 / T031).

Covers the migration contract (``contracts/migration-contract.md`` MG1-MG6):

* MG3 fail-loud: a charter op raises before migration runs against a legacy
  fixture (four files present, no ``charter.yaml``).
* MG1 deterministic compose + VERBATIM activation copy (absent stays absent).
* Four legacy files retired; ``config.yaml`` activation-free;
  ``charter:`` pointer minted.
* MG2 idempotency: re-run reports 0 changes.
* MG6 ordering: sequenced after the seed activation migrations.

Ref: kitty-specs/consolidate-charter-bundle-01KXSYB9/tasks/WP07-migration-failloud-state.md
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from specify_cli.upgrade.migrations.m_unify_charter_activation_finalize import (
    ACTIVATION_KEYS,
    LEGACY_BUNDLE_FILENAMES,
    ConsolidateCharterBundleMigration,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_GOVERNANCE_YAML = """\
testing:
  min_coverage: 90
  tdd_required: true
  framework: pytest
  type_checking: mypy --strict
quality:
  linting: ruff
  pr_approvals: 2
  pre_commit_hooks: true
commits:
  convention: conventional
performance:
  cli_timeout_seconds: 2.0
  dashboard_max_wps: 100
branch_strategy:
  main_branch: main
  dev_branch: null
  rules: []
charter:
  selected_paradigms:
  - atomic-design
  selected_directives:
  - DIRECTIVE_001
  available_tools:
  - pytest
  - ruff
  template_set: software-dev-default
enforcement: {}
"""

_DIRECTIVES_YAML = """\
directives:
- id: DIRECTIVE_001
  title: Keep migrations idempotent
  description: Every migration must be safe to re-run.
  severity: warn
  references: []
"""

_METADATA_YAML = """\
schema_version: 1.0.0
extracted_at: '2026-01-01T00:00:00Z'
charter_hash: sha256:deadbeef
source_path: .kittify/charter/charter.md
extraction_mode: deterministic
sections_parsed:
  structured: 3
  ai_assisted: 0
  skipped: 0
bundle_schema_version: 2
"""

_REFERENCES_YAML = """\
schema_version: 1.0.0
generated_at: '2026-01-01T00:00:00Z'
mission: software-dev
template_set: software-dev-default
languages:
- python
references:
- id: DIRECTIVE:DIRECTIVE_001
  kind: directive
  title: Keep migrations idempotent
  summary: Every migration must be safe to re-run.
  source_path: src/charter/offering/directives/built-in/001.directive.yaml
  local_path: _LIBRARY/directive-001.md
"""

_CONFIG_YAML_LEGACY = """\
agents:
  claude: {}
activated_directives:
- DIRECTIVE_001
activated_tactics: []
activated_styleguides:
- aggregate-design-rules
activated_toolguides: null
activated_paradigms:
- atomic-design
activated_procedures: []
activated_agent_profiles:
- python-pedro
activated_mission_step_contracts: []
activated_kinds:
- directives
- tactics
mission_type_activations:
- software-dev
"""


#: The config.yaml shape the 3.2.0rc35 seed migrations left behind: every
#: activation key written, alongside the project's own keys.
_SEEDED_CONFIG_YAML = """\
agents:
  claude: {}
activated_directives:
- DIRECTIVE_001
activated_tactics:
- adr-drafting-workflow
activated_styleguides: []
activated_toolguides: []
activated_paradigms: []
activated_procedures: []
activated_agent_profiles: []
activated_mission_step_contracts: []
activated_kinds:
- directives
- tactics
mission_type_activations:
- software-dev
"""

def _yaml() -> YAML:
    yaml = YAML(typ="safe")
    return yaml


def _load(path: Path) -> dict[str, Any]:
    return _yaml().load(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def _write_legacy_fixture(project_path: Path, *, config: str = _CONFIG_YAML_LEGACY) -> None:
    """A fully legacy project: four bundle files + config-embedded activation."""
    charter_dir = project_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "governance.yaml").write_text(_GOVERNANCE_YAML, encoding="utf-8")
    (charter_dir / "directives.yaml").write_text(_DIRECTIVES_YAML, encoding="utf-8")
    (charter_dir / "metadata.yaml").write_text(_METADATA_YAML, encoding="utf-8")
    (charter_dir / "references.yaml").write_text(_REFERENCES_YAML, encoding="utf-8")

    kittify = project_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text(config, encoding="utf-8")


@pytest.fixture
def migration() -> ConsolidateCharterBundleMigration:
    return ConsolidateCharterBundleMigration()


@pytest.fixture
def legacy_project(tmp_path: Path) -> Path:
    _write_legacy_fixture(tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# MG3: fail-loud pre-migration (ATDD red-first anchor)
# ---------------------------------------------------------------------------


def test_charter_op_fails_loud_before_migration(legacy_project: Path) -> None:
    """A charter.yaml-dependent op raises loud on a legacy (un-migrated) project.

    ``_raise_if_bundle_incomplete`` is the CLI-facing preflight the earlier
    WPs (WP01/WP03) already re-pointed onto ``charter.yaml`` presence
    (``BUNDLE_CONTENT_HASH_FILES = ("charter.yaml",)``): on a legacy fixture
    that carries the four retired files but no ``charter.yaml``, it must
    raise -- never silently proceed by reading the legacy files (MG3/C-003).
    The error message names this migration as the remediation.
    """
    from specify_cli.cli.commands.charter._synthesis import (
        BUNDLE_INCOMPLETE_MESSAGE,
        _raise_if_bundle_incomplete,
    )
    from specify_cli.task_utils import TaskCliError

    with pytest.raises(TaskCliError) as excinfo:
        _raise_if_bundle_incomplete(legacy_project)

    assert "charter.yaml" in str(excinfo.value)
    assert BUNDLE_INCOMPLETE_MESSAGE.split("{missing}")[0] in str(excinfo.value)


def test_charter_op_succeeds_after_migration(
    legacy_project: Path, migration: ConsolidateCharterBundleMigration
) -> None:
    """The SAME charter op no longer raises once the migration has run."""
    from specify_cli.cli.commands.charter._synthesis import _raise_if_bundle_incomplete

    result = migration.apply(legacy_project)
    assert result.success, result.errors

    # No exception == fixed.
    _raise_if_bundle_incomplete(legacy_project)


# ---------------------------------------------------------------------------
# MG1 / MG4: composition, retirement, pointer, metadata identity-safety
# ---------------------------------------------------------------------------


def test_apply_composes_charter_yaml_and_retires_four(
    legacy_project: Path, migration: ConsolidateCharterBundleMigration
) -> None:
    assert migration.detect(legacy_project) is True

    result = migration.apply(legacy_project)
    assert result.success, result.errors
    assert result.changes_made

    charter_dir = legacy_project / ".kittify" / "charter"
    charter_yaml_path = charter_dir / "charter.yaml"
    assert charter_yaml_path.exists()

    for name in LEGACY_BUNDLE_FILENAMES:
        assert not (charter_dir / name).exists(), f"{name} must be retired"

    composed = _load(charter_yaml_path)
    assert composed["schema_version"] == "2.0.0"
    assert composed["metadata"]["bundle_schema_version"] == 2
    assert composed["governance"]["testing"]["min_coverage"] == 90
    assert composed["governance"]["charter"]["template_set"] == "software-dev-default"
    assert composed["directives"]["directives"][0]["id"] == "DIRECTIVE_001"
    assert composed["catalog"]["mission"] == "software-dev"
    assert composed["catalog"]["references"][0]["id"] == "DIRECTIVE:DIRECTIVE_001"

    # Activation relocated verbatim onto the flat root keys.
    assert composed["activated_directives"] == ["DIRECTIVE_001"]
    assert composed["activated_styleguides"] == ["aggregate-design-rules"]
    assert composed["activated_paradigms"] == ["atomic-design"]
    assert composed["activated_agent_profiles"] == ["python-pedro"]
    # An explicit [] in config.yaml stays [] (not dropped, not re-invented).
    assert composed["activated_tactics"] == []
    assert composed["activated_procedures"] == []
    assert composed["activated_mission_step_contracts"] == []


def test_apply_relocates_activation_and_mints_pointer(
    legacy_project: Path, migration: ConsolidateCharterBundleMigration
) -> None:
    migration.apply(legacy_project)

    config_data = _load(legacy_project / ".kittify" / "config.yaml")
    for key in ACTIVATION_KEYS:
        assert key not in config_data, f"{key} must be removed from config.yaml"
    assert config_data["charter"] == ".kittify/charter/charter.yaml"
    # Non-doctrine keys survive untouched.
    assert config_data["agents"] == {"claude": {}}


def test_apply_touches_only_charter_metadata_yaml_never_project_metadata(
    legacy_project: Path, migration: ConsolidateCharterBundleMigration
) -> None:
    """MG4: ``.kittify/metadata.yaml`` (project identity) is never touched."""
    project_metadata = legacy_project / ".kittify" / "metadata.yaml"
    project_metadata.write_text(
        "schema_version: '1.0'\nproject_uuid: deadbeef-dead-beef-dead-beefdeadbeef\n",
        encoding="utf-8",
    )
    before = project_metadata.read_text(encoding="utf-8")

    migration.apply(legacy_project)

    after = project_metadata.read_text(encoding="utf-8")
    assert before == after, ".kittify/metadata.yaml (project identity) must be untouched"
    # And the CHARTER metadata.yaml (a different file, same basename) is gone.
    assert not (legacy_project / ".kittify" / "charter" / "metadata.yaml").exists()


# ---------------------------------------------------------------------------
# MG1: absent-key fidelity — never invent [] for a key config.yaml never had
# ---------------------------------------------------------------------------


def test_absent_activation_key_survives_as_absent(
    tmp_path: Path, migration: ConsolidateCharterBundleMigration
) -> None:
    """A config with an absent per-kind key migrates with that key still absent."""
    narrow_config = (
        "activated_directives:\n- DIRECTIVE_001\n"
        # every other activated_* key is intentionally OMITTED
    )
    _write_legacy_fixture(tmp_path, config=narrow_config)

    migration.apply(tmp_path)

    composed = _load(tmp_path / ".kittify" / "charter" / "charter.yaml")
    assert composed["activated_directives"] == ["DIRECTIVE_001"]
    for key in ACTIVATION_KEYS:
        if key == "activated_directives":
            continue
        assert key not in composed, (
            f"{key} was absent from config.yaml; it must stay absent in "
            f"charter.yaml, never become []"
        )


# ---------------------------------------------------------------------------
# MG2: idempotency
# ---------------------------------------------------------------------------


def test_reapply_after_migration_is_zero_change(
    legacy_project: Path, migration: ConsolidateCharterBundleMigration
) -> None:
    first = migration.apply(legacy_project)
    assert first.success
    assert first.changes_made

    assert migration.detect(legacy_project) is False

    second = migration.apply(legacy_project)
    assert second.success
    assert second.changes_made == []


def test_dry_run_does_not_write(
    legacy_project: Path, migration: ConsolidateCharterBundleMigration
) -> None:
    result = migration.apply(legacy_project, dry_run=True)
    assert result.success
    assert result.changes_made  # reports intent

    charter_dir = legacy_project / ".kittify" / "charter"
    for name in LEGACY_BUNDLE_FILENAMES:
        assert (charter_dir / name).exists(), "dry-run must not delete anything"
    assert not (charter_dir / "charter.yaml").exists(), "dry-run must not write anything"


def test_no_legacy_no_activation_is_zero_change_without_io(
    tmp_path: Path, migration: ConsolidateCharterBundleMigration
) -> None:
    """A brand new / already-migrated project (nothing to fold) stays a no-op."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True)
    (kittify / "config.yaml").write_text("agents:\n  claude: {}\n", encoding="utf-8")

    assert migration.detect(tmp_path) is False
    result = migration.apply(tmp_path)
    assert result.success
    assert result.changes_made == []
    assert not (tmp_path / ".kittify" / "charter" / "charter.yaml").exists()


# ---------------------------------------------------------------------------
# Landmine 3: a PRE-EXISTING (already authoritative) charter.yaml is never
# clobbered by a subsequent apply — only cleanup (legacy retirement +
# activation relocation) happens.
# ---------------------------------------------------------------------------


def test_pre_existing_charter_yaml_governance_survives_byte_for_byte(
    tmp_path: Path, migration: ConsolidateCharterBundleMigration
) -> None:
    _write_legacy_fixture(tmp_path)
    charter_dir = tmp_path / ".kittify" / "charter"

    # An authored charter.yaml ALREADY exists (e.g. hand-edited after a
    # previous `charter generate`), with governance content that does NOT
    # match the stale legacy triad sitting alongside it.
    hand_authored = (
        "schema_version: '2.0.0'\n"
        "governance:\n"
        "  testing:\n"
        "    min_coverage: 100\n"
        "  quality: {}\n"
        "  commits: {}\n"
        "  performance: {}\n"
        "  branch_strategy: {}\n"
        "  doctrine: {}\n"
        "  activations: []\n"
        "  enforcement: {}\n"
        "directives:\n"
        "  directives: []\n"
        "catalog:\n"
        "  mission: software-dev\n"
        "  template_set: software-dev-default\n"
        "  languages: []\n"
        "  references: []\n"
        "metadata:\n"
        "  generated_at: '2026-01-01T00:00:00Z'\n"
        "  bundle_schema_version: 2\n"
    )
    (charter_dir / "charter.yaml").write_text(hand_authored, encoding="utf-8")

    migration.apply(tmp_path)

    composed = _load(charter_dir / "charter.yaml")
    # Hand-authored governance survives untouched -- NOT overwritten by the
    # stale legacy triad's min_coverage: 90.
    assert composed["governance"]["testing"]["min_coverage"] == 100
    # Activation still gets relocated on top.
    assert composed["activated_directives"] == ["DIRECTIVE_001"]
    # And the stale legacy files are still retired.
    for name in LEGACY_BUNDLE_FILENAMES:
        assert not (charter_dir / name).exists()


# ---------------------------------------------------------------------------
# MG6: ordering vs the seed activation migrations
# ---------------------------------------------------------------------------


def test_target_version_tied_to_unify_and_ordered_by_filename() -> None:
    """The fold ships in the unreleased 3.2.6 cycle (no version bump), so its
    ``target_version`` is TIED with ``m_unify_charter_activation``. Because
    ``get_all()`` breaks same-version ties by ``pkgutil`` module-discovery
    (alphabetical) order, the fold's module filename prefix-extends the unify
    migration's so it deterministically sorts immediately after it (a string
    always precedes its extensions). A version bump would exceed the installed
    package and be skipped by ``spec-kitty upgrade`` — the runtime ordering is
    proven by :func:`test_registry_orders_fold_after_seed_migrations`.
    """
    from pathlib import Path

    from packaging.version import Version

    from specify_cli.upgrade.migrations import (
        m_unify_charter_activation,
        m_unify_charter_activation_finalize,
    )
    from specify_cli.upgrade.migrations.m_unify_charter_activation import (
        UnifyCharterActivationMigration,
    )
    from specify_cli.upgrade.migrations.m_unify_charter_activation_finalize import (
        TARGET_VERSION,
    )

    # Tied version — the fold shares the seed's 3.2.6 target (no bump).
    assert Version(TARGET_VERSION) == Version(UnifyCharterActivationMigration.target_version)

    # Ordering lever: the fold's module filename is a proper extension of the
    # unify migration's, so it sorts strictly after it in the tie-break.
    unify_stem = Path(m_unify_charter_activation.__file__).stem
    fold_stem = Path(m_unify_charter_activation_finalize.__file__).stem
    assert fold_stem.startswith(unify_stem) and fold_stem > unify_stem


def test_registry_orders_fold_after_seed_migrations() -> None:
    """``MigrationRegistry.get_all()`` places the fold strictly after every seed.

    Reproduces the PRODUCTION registration path: ``auto_discover_migrations()``
    imports modules in ``pkgutil`` (alphabetical) order, so the same-version
    (3.2.6) tie-break follows filename order — and the fold's filename
    prefix-extends ``m_unify_charter_activation`` to sort immediately after it.
    (Ambient import-order registration -- e.g. a test module importing the fold
    first -- would NOT reflect the real ``spec-kitty upgrade`` order, so the
    registry is rebuilt from discovery here.)
    """
    from specify_cli.upgrade.migrations import auto_discover_migrations
    from specify_cli.upgrade.registry import MigrationRegistry

    MigrationRegistry.clear()
    auto_discover_migrations()

    all_ids = [m.migration_id for m in MigrationRegistry.get_all()]
    seed_ids = {
        "3.2.0rc35_default_charter_pack",
        "3.2.0rc35_activate_builtin_mission_types",
        "unify_charter_activation_promote_answers",
    }
    fold_index = all_ids.index("consolidate_charter_bundle_fold")
    for seed_id in seed_ids:
        assert seed_id in all_ids, f"seed migration {seed_id} not registered"
        assert all_ids.index(seed_id) < fold_index, (
            f"{seed_id} must sequence before consolidate_charter_bundle_fold (MG6)"
        )


def test_fold_relocates_seed_migration_output(
    tmp_path: Path,
    migration: ConsolidateCharterBundleMigration,
) -> None:
    """End-to-end MG6: the fold relocates the seed migrations' post-state on a bare project.

    The seed migrations' post-state (config carries activated_*) is the
    fold's pre-state; it is written directly here because the rc35
    default-pack seed is a recorded no-op since the charter-pack cutover.
    The fold relocates then removes those keys (INV-2) and never re-fires
    against a re-seeded config (MG6 "must not perpetually re-fire").
    """
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True)
    (kittify / "config.yaml").write_text(_SEEDED_CONFIG_YAML, encoding="utf-8")

    config_after_seed = _load(kittify / "config.yaml")
    assert "activated_directives" in config_after_seed  # seed post-state

    assert migration.detect(tmp_path) is True
    result = migration.apply(tmp_path)
    assert result.success, result.errors

    config_after_fold = _load(kittify / "config.yaml")
    for key in ACTIVATION_KEYS:
        assert key not in config_after_fold
    assert config_after_fold["charter"] == ".kittify/charter/charter.yaml"

    composed = _load(kittify / "charter" / "charter.yaml")
    assert composed["activated_directives"] == config_after_seed["activated_directives"]

    # Re-seed + re-fold safety when the migration objects are invoked DIRECTLY
    # (bypassing the runner): the seed migrations key on absence, so after the
    # fold strips config.activated_*, they re-fire and the fold must relocate+
    # clear again without error. NOTE — in production this direct re-fire never
    # happens: MigrationRunner gates on the per-migration applied-ledger
    # (metadata.has_migration) BEFORE detect(), so each migration runs at most
    # once per upgrade. That ledger — not joint idempotency of the migration
    # objects — is the load-bearing guard against a seed-reseed/fold-overwrite
    # clobber; a future non-ledgered re-apply/repair path would need its own.
    (kittify / "config.yaml").write_text(_SEEDED_CONFIG_YAML, encoding="utf-8")  # re-seed post-fold
    assert migration.detect(tmp_path) is True
    second_fold = migration.apply(tmp_path)
    assert second_fold.success
    config_final = _load(kittify / "config.yaml")
    for key in ACTIVATION_KEYS:
        assert key not in config_final


def test_fold_refuses_legacy_governance_selection_key(
    tmp_path: Path, migration: ConsolidateCharterBundleMigration
) -> None:
    """A standalone governance.yaml with the pre-rename ``doctrine:`` key fails closed.

    The charter-pack cutover rewrites ``governance.doctrine`` first; the fold
    never drops the selection silently and leaves every legacy file in place.
    """
    _write_legacy_fixture(tmp_path)
    governance = tmp_path / ".kittify" / "charter" / "governance.yaml"
    governance.write_text(_GOVERNANCE_YAML.replace("\ncharter:\n", "\ndoctrine:\n", 1), encoding="utf-8")
    config_before = (tmp_path / ".kittify" / "config.yaml").read_bytes()

    result = migration.apply(tmp_path)

    assert result.success is False
    (error,) = result.errors
    assert "governance.doctrine" in error and str(governance) in error
    assert "charter-pack cutover" in error
    assert not (tmp_path / ".kittify" / "charter" / "charter.yaml").exists()
    for name in LEGACY_BUNDLE_FILENAMES:
        assert (tmp_path / ".kittify" / "charter" / name).exists()
    assert (tmp_path / ".kittify" / "config.yaml").read_bytes() == config_before
