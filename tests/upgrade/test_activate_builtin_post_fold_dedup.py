"""Finding-1 residual: the rc35 activation migration must not fight the fold.

Mission ``migration-ledger-01M55SFA`` closeout finding 1 (assessment leg).

``m_3_2_0rc35_activate_builtin_mission_types`` adds ``mission_type_activations``
to ``config.yaml``; ``consolidate_charter_bundle_fold`` later RELOCATES that key
from ``config.yaml`` into the resolved charter write target (``charter.yaml``
for a pointer/migrated project). The two own the same key, and the fold is the
newer intent.

Because the rc35 migration records a non-settling ``skipped`` whenever the key
was already present (fresh-init provisioning / rc39+ projects), a project whose
fold has already run is RE-SELECTED on every subsequent upgrade: its
``config.yaml`` no longer carries the key (the fold moved it), so the migration's
``detect()`` flips True and it RE-ADDS the key to ``config.yaml`` — standing
drift (the key ends up in BOTH ``config.yaml`` and ``charter.yaml``) plus an
auto-commit, breaking NFR-002. The ``4.0.0rc8`` backfill replays exactly such
metadata histories, so this is reachable for real rc39..rc7 projects upgrading
to rc8, independent of the init-seed fix.

The fix: the rc35 migration recognises the post-fold state (the resolved
activation write target already carries the key, via the same single authority
``resolve_activation_write_target`` the upgrade provisioning heal trusts) and
reports itself satisfied, so it never re-adds the key.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.upgrade.migrations.m_3_2_0rc35_activate_builtin_mission_types import (
    ActivateBuiltinMissionTypesMigration,
)
from specify_cli.upgrade.migrations.m_unify_charter_activation_finalize import (
    ConsolidateCharterBundleMigration,
)
from tests.upgrade.test_consolidate_charter_bundle_migration import _write_legacy_fixture

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _post_fold_project(tmp_path: Path) -> Path:
    """A canonical post-fold project, built by running the REAL fold migration.

    Starts from a legacy project whose ``config.yaml`` embeds
    ``mission_type_activations: [software-dev]`` and runs
    ``consolidate_charter_bundle_fold``, which relocates the key into
    ``charter.yaml`` and strips it from ``config.yaml`` — the exact state a
    fold-migrated project is left in.
    """
    _write_legacy_fixture(tmp_path)
    result = ConsolidateCharterBundleMigration().apply(tmp_path)
    assert result.success, result.errors
    return tmp_path


def test_rc35_detect_is_false_after_the_fold_relocated_the_key(tmp_path: Path) -> None:
    """Post-fold, the rc35 migration is satisfied and must NOT re-select."""
    project = _post_fold_project(tmp_path)

    # Sanity: the fold really stripped the key from config.yaml.
    from ruamel.yaml import YAML

    config = YAML(typ="safe").load((project / ".kittify" / "config.yaml").read_text(encoding="utf-8")) or {}
    assert "mission_type_activations" not in config, "fold did not relocate the key off config.yaml"

    migration = ActivateBuiltinMissionTypesMigration()
    assert migration.detect(project) is False, (
        "rc35 migration still reports 'needed' after the fold relocated the key — it would re-add mission_type_activations to config.yaml (standing drift)"
    )


def test_rc35_apply_is_a_no_op_after_the_fold(tmp_path: Path) -> None:
    """Even if applied, the post-fold rc35 migration must not re-add the key."""
    project = _post_fold_project(tmp_path)
    from ruamel.yaml import YAML

    before = (project / ".kittify" / "config.yaml").read_bytes()
    migration = ActivateBuiltinMissionTypesMigration()
    migration.apply(project)
    after = (project / ".kittify" / "config.yaml").read_bytes()
    config = YAML(typ="safe").load(after.decode("utf-8")) or {}
    assert "mission_type_activations" not in config, "rc35 apply re-added the relocated key to config.yaml"
    assert after == before, "rc35 apply mutated config.yaml on a post-fold project"
