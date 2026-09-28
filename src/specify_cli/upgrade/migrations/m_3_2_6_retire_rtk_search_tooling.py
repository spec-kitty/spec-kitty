"""Migration m_3_2_6_retire_rtk_search_tooling: drop a retired toolguide activation.

Operator ruling 2026-07-28 removed the ``rtk-search-tooling`` toolguide outright:
the artefact, its guide, its DRG node, and its entry in the shipped default
charter pack (``src/charter/activation/packs/default.yaml``) are all gone. RTK will not be
pushed to the userbase.

Why a migration is required
---------------------------
``m_3_2_0rc35_default_charter_pack`` copied the default pack's
``activated_toolguides`` **verbatim** into every upgraded project's
``.kittify/config.yaml``, and — by design — writes only *absent* keys. A later
upgrade therefore never removes a stale member from an already-present key. So
every project that passed through rc35 still names ``rtk-search-tooling`` in
``activated_toolguides`` while the artefact no longer exists on disk.

The charter compiler is deliberately fail-closed: ``charter.activation.compiler`` raises
:class:`charter.activation.kind_vocabulary.UnknownArtifactIdError` rather than silently
dropping an unresolvable stem, and that raise is not caught on the compile
path. The observed consequence is a hard failure::

    UnknownArtifactIdError: No toolguide artifact with config ID
    'rtk-search-tooling' found under doctrine root src/doctrine.

This migration is the unmanaged-retirement backstop: it removes the stale
activation from ``config.yaml`` and also strips the two compiled blocks in
``.kittify/charter/`` (``charter.yaml`` and ``references.yaml``) that would
otherwise be left naming a deleted ``source_path``.

Scope
-----
Three project files, each optional:

* ``.kittify/config.yaml``            — ``activated_toolguides`` list member
* ``.kittify/charter/charter.yaml``   — ``catalog`` reference block + ``activated_toolguides`` member
* ``.kittify/charter/references.yaml``— ``references`` reference block

Nothing is ever created: a project that lacks any of these files (or lacks the
entry) is left untouched. No directory is created by this migration.

Idempotency
-----------
Every removal is conditional on the entry being present, so a second run finds
nothing to do and returns ``success=True`` with the "already absent" note.

Implementation (T002/T003, mission ``squad-doctrine-single-owner-01M3KBP7``)
------------------------------------------------------------------------------
The removal mechanics (round-trip YAML I/O, per-surface member/block
matching, the "nothing removed" no-op contract) are shared with
``m_4_0_0rc5_retire_single_owner_doctrine_ids`` via the generic engine in
``_retired_activation.py`` rather than duplicated a second time. This
migration's own public surface — ``migration_id``, ``target_version``, the
three project files it touches, and the exported
``RETIRED_TOOLGUIDE_STEM`` / ``RETIRED_TOOLGUIDE_REFERENCE_ID`` constants —
is unchanged; only the internals were extracted, and
``tests/specify_cli/upgrade/migrations/test_m_3_2_6_retire_rtk_search_tooling.py``
still passes unmodified against the rebuilt class (behaviour-preserving).
"""

from __future__ import annotations

from pathlib import Path

from ..registry import MigrationRegistry
from ._retired_activation import Retirement, apply_retirements, detect_retirements
from .base import BaseMigration, MigrationResult

#: Config/file-stem id of the retired toolguide, as it appears in
#: ``activated_toolguides`` in both ``config.yaml`` and ``charter.yaml``.
RETIRED_TOOLGUIDE_STEM = "rtk-search-tooling"

#: Catalog/reference block id of the same artefact, as compiled into
#: ``.kittify/charter/charter.yaml`` (``catalog``) and ``references.yaml``.
RETIRED_TOOLGUIDE_REFERENCE_ID = f"TOOLGUIDE:{RETIRED_TOOLGUIDE_STEM}"

_RETIREMENT = Retirement(
    kind_key="activated_toolguides",
    stem=RETIRED_TOOLGUIDE_STEM,
    reference_prefix="TOOLGUIDE",
)


@MigrationRegistry.register
class RetireRtkSearchToolingMigration(BaseMigration):
    """Remove the retired ``rtk-search-tooling`` toolguide from project charter surfaces.

    Without this, charter compilation hard-fails with ``UnknownArtifactIdError``
    on every project that received the entry from the rc35 default-pack write.
    """

    migration_id = "3.2.6_retire_rtk_search_tooling"
    description = (
        "Remove the retired rtk-search-tooling toolguide from "
        ".kittify/config.yaml and the compiled .kittify/charter/ blocks so "
        "charter compilation stops failing on the deleted artefact."
    )
    target_version = "3.2.6rc1"

    def detect(self, project_path: Path) -> bool:
        """Return True when any project surface still names the retired toolguide."""
        return detect_retirements(project_path, (_RETIREMENT,), include_answers_surface=False)

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        """Only applicable when at least one stale mention survives."""
        if self.detect(project_path):
            return True, ""
        return False, "rtk-search-tooling is not activated in this project"

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Strip the retired toolguide from every project surface that still names it."""
        result = apply_retirements(
            project_path,
            (_RETIREMENT,),
            include_answers_surface=False,
            dry_run=dry_run,
        )
        if not result.changes_made and not result.errors:
            return MigrationResult(
                success=True,
                changes_made=[f"{RETIRED_TOOLGUIDE_STEM} already absent; nothing to remove"],
            )
        return result
