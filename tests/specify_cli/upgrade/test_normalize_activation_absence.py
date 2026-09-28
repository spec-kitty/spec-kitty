"""Tests for m_3_2_x_normalize_activation_absence (WP07/T037, FR-018).

The migration writes an explicit ``[]`` for every per-artifact
``activated_<kind>`` key absent from the project's *resolved* activation store
(``charter.yaml`` when the ``charter:`` pointer is present, else ``config.yaml``)
so absence means "nothing activated" rather than "all built-ins", and ensures
the ``charter:`` pointer is present.

All tests call ``detect()``/``can_apply()``/``apply()`` directly on a migration
instance (not the upgrade pipeline) so the ``target_version`` guard never
interferes. Fixtures are constructed synthetic projects.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from specify_cli.upgrade.migrations.m_3_2_x_normalize_activation_absence import (
    MIGRATION_ID,
    NormalizeActivationAbsenceMigration,
    _config_carries_any_activation,
    _legacy_bundle_present,
    _per_artifact_activation_keys,
    _should_defer_bare_config_write,
    _unify_promotion_pending,
)
from specify_cli.upgrade.registry import MigrationRegistry

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _load(path: Path) -> dict:
    data = YAML(typ="safe").load(path.read_text(encoding="utf-8")) if path.exists() else {}
    return data or {}


_POINTER_CONFIG = """\
vcs:
  type: git
charter: .kittify/charter/charter.yaml
"""


def _charter_yaml(body: str) -> str:
    return f"""\
schema_version: "2.0.0"
governance:
  testing: {{}}
directives: []
catalog: {{}}
{body}metadata:
  bundle_schema_version: 2
"""


# ---------------------------------------------------------------------------
# Auto-discovery / registration
# ---------------------------------------------------------------------------


def test_migration_is_registered() -> None:
    """The migration is auto-discovered and retrievable by id from the registry.

    Identity is asserted by ``migration_id`` and class *name*, not by
    ``isinstance`` against the imported class: ``auto_discover_migrations``
    reloads migration modules after ``MigrationRegistry.clear()`` (exercised by
    other tests in the suite), which rebinds the class object, so a registered
    instance is not an ``isinstance`` of this module's collection-time import.
    """
    found = MigrationRegistry.get_by_id(MIGRATION_ID)
    assert found is not None
    assert type(found).__name__ == NormalizeActivationAbsenceMigration.__name__
    assert found.migration_id == "normalize_activation_absence"
    assert found.runs_on_worktrees is False


# ---------------------------------------------------------------------------
# charter.yaml store (pointer present) — the migrated case
# ---------------------------------------------------------------------------


def test_absent_keys_become_empty_in_charter_yaml(tmp_path: Path) -> None:
    """A charter.yaml activating one kind gets explicit [] for the other eight."""
    _write(tmp_path / ".kittify" / "config.yaml", _POINTER_CONFIG)
    _write(
        tmp_path / ".kittify" / "charter" / "charter.yaml",
        _charter_yaml("activated_directives:\n  - 010-specification-fidelity-requirement\n"),
    )
    migration = NormalizeActivationAbsenceMigration()

    assert migration.detect(tmp_path) is True
    result = migration.apply(tmp_path)
    assert result.success

    charter = _load(tmp_path / ".kittify" / "charter" / "charter.yaml")
    # The populated key is preserved; every other per-artifact key is explicit [].
    assert charter["activated_directives"] == ["010-specification-fidelity-requirement"]
    for key in _per_artifact_activation_keys():
        assert key in charter, key
        if key != "activated_directives":
            assert charter[key] == [], key


def test_does_not_clobber_populated_or_explicit_empty(tmp_path: Path) -> None:
    """Populated lists and pre-existing explicit [] survive untouched."""
    _write(tmp_path / ".kittify" / "config.yaml", _POINTER_CONFIG)
    _write(
        tmp_path / ".kittify" / "charter" / "charter.yaml",
        _charter_yaml(
            "activated_tactics:\n  - tdd-red-green-refactor\n"
            "activated_paradigms: []\n"
        ),
    )
    migration = NormalizeActivationAbsenceMigration()
    migration.apply(tmp_path)

    charter = _load(tmp_path / ".kittify" / "charter" / "charter.yaml")
    assert charter["activated_tactics"] == ["tdd-red-green-refactor"]
    assert charter["activated_paradigms"] == []


def test_does_not_touch_activated_kinds_or_mission_types(tmp_path: Path) -> None:
    """The coarse gates keep their own built-in-default absence semantics."""
    _write(tmp_path / ".kittify" / "config.yaml", _POINTER_CONFIG)
    _write(
        tmp_path / ".kittify" / "charter" / "charter.yaml",
        _charter_yaml("activated_directives:\n  - 010-specification-fidelity-requirement\n"),
    )
    NormalizeActivationAbsenceMigration().apply(tmp_path)

    charter = _load(tmp_path / ".kittify" / "charter" / "charter.yaml")
    assert "activated_kinds" not in charter
    assert "mission_type_activations" not in charter


def test_idempotent_second_apply_is_noop(tmp_path: Path) -> None:
    """Once every per-artifact key is explicit, detect() is False and apply() no-ops."""
    _write(tmp_path / ".kittify" / "config.yaml", _POINTER_CONFIG)
    _write(
        tmp_path / ".kittify" / "charter" / "charter.yaml",
        _charter_yaml("activated_directives:\n  - 010-specification-fidelity-requirement\n"),
    )
    migration = NormalizeActivationAbsenceMigration()
    migration.apply(tmp_path)

    assert migration.detect(tmp_path) is False
    second = migration.apply(tmp_path)
    assert second.changes_made == []


# ---------------------------------------------------------------------------
# config.yaml store (legacy, no pointer)
# ---------------------------------------------------------------------------


def test_absent_keys_become_empty_in_legacy_config(tmp_path: Path) -> None:
    """With no charter: pointer, absence is normalized in config.yaml itself."""
    _write(
        tmp_path / ".kittify" / "config.yaml",
        "vcs:\n  type: git\nactivated_directives:\n  - 010-specification-fidelity-requirement\n",
    )
    migration = NormalizeActivationAbsenceMigration()

    assert migration.detect(tmp_path) is True
    migration.apply(tmp_path)

    config = _load(tmp_path / ".kittify" / "config.yaml")
    assert config["activated_directives"] == ["010-specification-fidelity-requirement"]
    for key in _per_artifact_activation_keys():
        if key != "activated_directives":
            assert config[key] == [], key


# ---------------------------------------------------------------------------
# Two-invocation churn guard predicates (NFR-006, landing-fold fix for #3070)
#
# ``_should_defer_bare_config_write`` only defers when config.yaml is the
# resolved store (no charter.yaml) AND none of three signals already arms
# the sibling fold migration this pass: a legacy bundle file, an
# already-activation-carrying config, or a pending answers-only promotion.
# These tests exercise each predicate's true/false branches directly, then
# the detect()/apply() decisions they gate.
# ---------------------------------------------------------------------------


def test_legacy_bundle_present_true_when_a_bundle_file_exists(tmp_path: Path) -> None:
    _write(tmp_path / ".kittify" / "charter" / "governance.yaml", "testing: {}\n")
    assert _legacy_bundle_present(tmp_path) is True


def test_legacy_bundle_present_false_when_no_charter_dir(tmp_path: Path) -> None:
    assert _legacy_bundle_present(tmp_path) is False


def test_config_carries_any_activation_true_for_per_artifact_key() -> None:
    assert _config_carries_any_activation({"activated_directives": []}) is True


def test_config_carries_any_activation_true_for_coarse_key() -> None:
    """The coarse gates (excluded from FR-018 normalization) still arm the guard."""
    assert _config_carries_any_activation({"activated_kinds": ["directive"]}) is True


def test_config_carries_any_activation_false_for_bare_config() -> None:
    assert _config_carries_any_activation({"vcs": {"type": "git"}}) is False


def test_unify_promotion_pending_false_without_answers_yaml(tmp_path: Path) -> None:
    """No answers.yaml -> the sibling migration's own detect() short-circuits False."""
    _write(tmp_path / ".kittify" / "config.yaml", "vcs:\n  type: git\n")
    assert _unify_promotion_pending(tmp_path) is False


def test_unify_promotion_pending_true_with_answers_only_selection(tmp_path: Path) -> None:
    """An answers-only selection not yet mirrored into config.yaml is pending promotion."""
    _write(tmp_path / ".kittify" / "config.yaml", "vcs:\n  type: git\n")
    _write(
        tmp_path / ".kittify" / "charter" / "interview" / "answers.yaml",
        "selected_directives:\n  - 010-specification-fidelity-requirement\n",
    )
    assert _unify_promotion_pending(tmp_path) is True


def test_should_defer_bare_config_write_false_when_charter_path_given(tmp_path: Path) -> None:
    """Once charter.yaml exists, config.yaml is never the resolved store -- never defer."""
    assert (
        _should_defer_bare_config_write(tmp_path, {}, tmp_path / ".kittify" / "charter" / "charter.yaml")
        is False
    )


def test_should_defer_bare_config_write_false_when_legacy_bundle_present(tmp_path: Path) -> None:
    _write(tmp_path / ".kittify" / "charter" / "governance.yaml", "testing: {}\n")
    assert _should_defer_bare_config_write(tmp_path, {}, None) is False


def test_should_defer_bare_config_write_false_when_config_carries_activation(tmp_path: Path) -> None:
    config_data = {"vcs": {"type": "git"}, "activated_kinds": ["directive"]}
    assert _should_defer_bare_config_write(tmp_path, config_data, None) is False


def test_should_defer_bare_config_write_true_on_bare_project(tmp_path: Path) -> None:
    """No charter.yaml, no legacy bundle, no config activation, no pending promotion -> defer."""
    _write(tmp_path / ".kittify" / "config.yaml", "vcs:\n  type: git\n")
    config_data = {"vcs": {"type": "git"}}
    assert _should_defer_bare_config_write(tmp_path, config_data, None) is True


# ---------------------------------------------------------------------------
# detect()/apply() decisions the guard gates
# ---------------------------------------------------------------------------


def test_bare_config_defers_normalization_when_nothing_arms_the_fold(tmp_path: Path) -> None:
    """A freshly-init'd project (no charter.yaml/legacy bundle/activation/answers)
    reports detect() False and apply() is a true no-op -- the write is deferred
    rather than becoming the sole, premature trigger for the sibling fold.
    """
    _write(tmp_path / ".kittify" / "config.yaml", "vcs:\n  type: git\n")
    migration = NormalizeActivationAbsenceMigration()

    assert migration.detect(tmp_path) is False
    result = migration.apply(tmp_path)
    assert result.success
    assert result.changes_made == []

    config = _load(tmp_path / ".kittify" / "config.yaml")
    for key in _per_artifact_activation_keys():
        assert key not in config, key


def test_proceeds_immediately_when_legacy_bundle_present(tmp_path: Path) -> None:
    """A surviving legacy bundle file already arms the fold -- write now, not deferred."""
    _write(tmp_path / ".kittify" / "config.yaml", "vcs:\n  type: git\n")
    _write(tmp_path / ".kittify" / "charter" / "governance.yaml", "testing: {}\n")
    migration = NormalizeActivationAbsenceMigration()

    assert migration.detect(tmp_path) is True
    result = migration.apply(tmp_path)
    assert result.success
    assert result.changes_made != []

    config = _load(tmp_path / ".kittify" / "config.yaml")
    for key in _per_artifact_activation_keys():
        assert config[key] == [], key


def test_proceeds_immediately_when_config_already_carries_coarse_activation(tmp_path: Path) -> None:
    """A pre-existing coarse activation key already arms the fold -- write now."""
    _write(
        tmp_path / ".kittify" / "config.yaml",
        "vcs:\n  type: git\nactivated_kinds:\n  - directive\n",
    )
    migration = NormalizeActivationAbsenceMigration()

    assert migration.detect(tmp_path) is True
    migration.apply(tmp_path)

    config = _load(tmp_path / ".kittify" / "config.yaml")
    assert config["activated_kinds"] == ["directive"]
    for key in _per_artifact_activation_keys():
        assert config[key] == [], key


def test_proceeds_immediately_when_answers_only_promotion_pending(tmp_path: Path) -> None:
    """A pending answers->config promotion already arms the fold -- write now."""
    _write(tmp_path / ".kittify" / "config.yaml", "vcs:\n  type: git\n")
    _write(
        tmp_path / ".kittify" / "charter" / "interview" / "answers.yaml",
        "selected_directives:\n  - 010-specification-fidelity-requirement\n",
    )
    migration = NormalizeActivationAbsenceMigration()

    assert migration.detect(tmp_path) is True
    migration.apply(tmp_path)

    config = _load(tmp_path / ".kittify" / "config.yaml")
    for key in _per_artifact_activation_keys():
        assert config[key] == [], key
