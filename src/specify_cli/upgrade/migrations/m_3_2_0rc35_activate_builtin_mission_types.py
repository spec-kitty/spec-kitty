"""Migration m_3_2_0rc35_activate_builtin_mission_types: add mission_type_activations.

FR-019 — Existing projects that pre-date the charter mission-type-activation
feature (mission charter-doctrine-mission-type-configuration-01KSWJVX) have no
explicit ``mission_type_activations`` entry in their ``.kittify/config.yaml``.

After this mission, DRG traversal is activation-filtered (FR-018).  Without
this migration, upgrading a legacy project would silently make all mission types
invisible to charter-mediated resolution — breaking every existing project.

This migration writes ``mission_type_activations: [software-dev, documentation,
research, plan]`` into ``config.yaml`` for projects that lack the key, preserving
all prior functionality transparently.

Idempotency
-----------
If ``mission_type_activations`` is already present and non-empty the migration
is a no-op: it never removes or replaces existing configuration.
"""

from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult

#: The written set is resolved at ``apply()``-time from the filesystem accessor
#: ``charter.offering.missions.mission_type_repository.builtin_mission_type_ids()``
#: (a disk-scan of the built-in mission-type catalog) rather than a hardcoded
#: literal here.
#:
#: Drift caveat (mission resolution-activation-foundation-01KZ9FKG, WP04):
#: this accessor USED to be the source read by ``PackContext.from_config()``'s
#: config-absent default, which is why an earlier revision claimed the two
#: "can never drift." WP04 RETIRED that implicit backfill -- an absent key now
#: resolves to ``frozenset()`` (fail-closed), and the authored
#: built-in ``default`` preset (``packs/built-in/presets/default.yaml``) list is
#: the single authority that fresh-init / generation / upgrade provisioning seed
#: from. This migration
#: still seeds from the disk-scan roster, so if a fifth built-in mission type
#: is ever added under ``mission_types/`` WITHOUT also adding it to
#: ``default.yaml``, a pre-rc35 project upgraded through this migration and a
#: freshly-init'd project would disagree on the activated set. Keep the two
#: rosters in sync, or repoint this migration at ``default.yaml`` (tracked
#: follow-up) to make the authority uniform.


@MigrationRegistry.register
class ActivateBuiltinMissionTypesMigration(BaseMigration):
    """Add mission_type_activations to .kittify/config.yaml for legacy projects.

    Historically, projects without the ``mission_type_activations`` key were
    treated as implicitly activating all four built-ins (a backward-compat
    default in ``PackContext.from_config()``). That implicit default was
    RETIRED in mission resolution-activation-foundation-01KZ9FKG (WP04): an
    absent key now fails closed rather than defaulting. This migration makes
    the activation explicit for legacy (pre-rc35) projects so the config
    reflects a concrete, non-empty state instead of relying on the removed
    implicit default.
    """

    migration_id = "3.2.0rc35_activate_builtin_mission_types"
    description = (
        "Add mission_type_activations: [software-dev, documentation, research, plan] "
        "to .kittify/config.yaml for projects that do not yet have the key (FR-019)."
    )
    target_version = "3.2.0rc35"

    def detect(self, project_path: Path) -> bool:
        """Return True when config.yaml exists but lacks mission_type_activations.

        Args:
            project_path: Root of the consumer project (.kittify parent).

        Returns:
            True if the migration needs to run.
        """
        config_file = project_path / ".kittify" / "config.yaml"
        if not config_file.exists():
            return False
        yaml = YAML(typ="safe")
        try:
            data = yaml.load(config_file) or {}
        except Exception:
            return False
        if not isinstance(data, dict):
            return False
        existing = data.get("mission_type_activations")
        # Needs migration when key is absent or empty
        return not (isinstance(existing, list) and existing)

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        """Check that config.yaml is readable if it exists.

        Args:
            project_path: Root of the consumer project.

        Returns:
            (True, "") if safe to proceed; (False, reason) otherwise.
        """
        config_file = project_path / ".kittify" / "config.yaml"
        if not config_file.exists():
            return True, ""
        if not config_file.is_file():
            return False, "config path exists but is not a file"
        try:
            config_file.read_text(encoding="utf-8")
            return True, ""
        except OSError as exc:
            return False, f"config file not readable: {exc}"

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Write mission_type_activations into config.yaml when absent.

        Uses ruamel.yaml round-trip parser to preserve existing YAML
        formatting and comments.  Only adds the new key; never removes or
        overwrites existing configuration.

        Args:
            project_path: Root of the consumer project (.kittify parent).
            dry_run:      When True, report what would change but write nothing.

        Returns:
            MigrationResult describing the outcome.
        """
        from charter.missions import (  # noqa: PLC0415 — lazy; call-time live-read (C-004), avoids import-time filesystem I/O in the migration registry
            builtin_mission_type_ids,
        )

        config_file = project_path / ".kittify" / "config.yaml"

        if not config_file.exists():
            return MigrationResult(
                success=True,
                changes_made=["No .kittify/config.yaml found; nothing to migrate"],
            )

        yaml = YAML()
        yaml.preserve_quotes = True

        try:
            data = yaml.load(config_file) or {}
        except Exception as exc:
            return MigrationResult(success=False, errors=[f"Invalid YAML: {exc}"])

        if not isinstance(data, dict):
            return MigrationResult(
                success=False, errors=["config.yaml root must be a mapping"]
            )

        # Idempotency check — skip if already present and non-empty
        existing = data.get("mission_type_activations")
        if isinstance(existing, list) and existing:
            return MigrationResult(
                success=True,
                changes_made=["mission_type_activations already present; no changes needed"],
            )

        builtin_types = sorted(builtin_mission_type_ids())

        change_description = (
            f"Added mission_type_activations: {builtin_types}"
        )

        if dry_run:
            return MigrationResult(
                success=True,
                changes_made=[f"Would add: {change_description}"],
            )

        data["mission_type_activations"] = builtin_types

        try:
            with config_file.open("w", encoding="utf-8") as fh:
                yaml.dump(data, fh)
        except OSError as exc:
            return MigrationResult(
                success=False, errors=[f"Failed writing config.yaml: {exc}"]
            )

        return MigrationResult(success=True, changes_made=[change_description])
