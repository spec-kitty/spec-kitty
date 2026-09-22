"""Migration ``consolidate_charter_bundle_fold``: fold the legacy bundle + activation into ``charter.yaml``.

Contract: ``kitty-specs/consolidate-charter-bundle-01KXSYB9/contracts/
migration-contract.md`` (MG1-MG6). Data model: ``../data-model.md`` INV-2/5/6.

This is the mission's finalizer migration (WP07). It folds the four legacy
charter bundle files (``governance.yaml``, ``directives.yaml``,
``metadata.yaml``, ``references.yaml``) plus the ``config.yaml``-embedded
``activated_*`` keys into the single, git-tracked ``charter.yaml``, then
retires the four files and mints the ``.kittify/config.yaml`` ``charter:``
pointer (INV-2). It lands LAST so no consumer of the retired surfaces is
left orphaned -- every earlier WP already re-points its readers onto
``charter.yaml`` directly (``charter.activation.sync.load_governance_config`` /
``load_directives_config``, ``charter.activation.pack_context.PackContext.from_config``,
``charter.activation.consistency_check``).

Body pattern: ``src/charter/offering/versioning.py:299 migrate_v1_to_v2``
(yaml -> yaml write-and-stamp), NOT the rc35 refresh-only shape. Registered
via ``@MigrationRegistry.register``; ``runs_on_worktrees = False`` (a
project-identity/config-level fold, not a worktree concern). ``charter.*``
imports are lazy inside the methods below (C-002 -- registry discovery must
stay import-cheap).

Ordering (MG6 -- paula MAJOR-3): sequenced strictly AFTER the existing
activation-seed migrations that write ``activated_*`` INTO ``config.yaml``:
``m_unify_charter_activation.py`` (``target_version = "3.2.6rc1"``, whose
"config is the activation authority" invariant is now REVERSED by this
migration -- see the docstring note on that class) and the rc35 pair
(``m_3_2_0rc35_default_charter_pack.py`` /
``m_3_2_0rc35_activate_builtin_mission_types.py``, ``target_version =
"3.2.0rc35"``, both ``detect()``-on-absence). Their post-state (config
carries ``activated_*``) is this migration's pre-state; this migration
relocates those keys into ``charter.yaml`` and then removes them from
``config.yaml``.

``target_version`` is ``"3.2.6rc1"`` -- tied with ``m_unify_charter_activation``.
``3.2.6`` is unreleased, so this fold ships within the same cycle rather than
advancing the package version (a migration whose ``target_version`` exceeds
the installed package is skipped by ``spec-kitty upgrade``; targeting an
unreleased ``3.2.7`` would silently never run).

Same-version ordering (MG6): ``MigrationRegistry.get_all()`` sorts by
``Version`` and breaks same-version ties by registry insertion order, which
follows alphabetical ``pkgutil`` module-discovery order. To guarantee this
fold runs strictly AFTER ``m_unify_charter_activation`` (whose post-state --
config carries ``activated_*`` -- is this fold's pre-state), this module's
filename is a proper extension of that migration's:
``m_unify_charter_activation_finalize.py`` sorts deterministically immediately
after ``m_unify_charter_activation.py`` (a string always precedes its
extensions), so the tie-break is guaranteed, not incidental. The public
``migration_id`` stays ``consolidate_charter_bundle_fold``; only the module
filename encodes the ordering.
"""

from __future__ import annotations

import functools
from kernel.clock import now_utc_stamp
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult

MIGRATION_ID = "consolidate_charter_bundle_fold"
TARGET_VERSION = "3.2.6rc1"

_KITTIFY_DIRNAME = ".kittify"
_CHARTER_DIRNAME = "charter"
_CONFIG_FILENAME = "config.yaml"
_CHARTER_POINTER_KEY = "charter"

_GOVERNANCE_YAML = "governance.yaml"
_DIRECTIVES_YAML = "directives.yaml"
_METADATA_YAML = "metadata.yaml"
_REFERENCES_YAML = "references.yaml"
_CHARTER_YAML = "charter.yaml"

#: The four legacy bundle files this migration folds and retires (data-model.md
#: "Entity: charter.yaml", contracts/migration-contract.md Inputs).
LEGACY_BUNDLE_FILENAMES: tuple[str, ...] = (
    _GOVERNANCE_YAML,
    _DIRECTIVES_YAML,
    _METADATA_YAML,
    _REFERENCES_YAML,
)

#: Flat root activation keys relocated from ``config.yaml`` onto ``charter.yaml``
#: (paula BLOCKER-1). Mirrors ``charter.activation.charter_yaml_io._ACTIVATION_KEYS``.
#:
#: WP05 / FR-010 / C4.2: this used to be a hand-written literal tuple
#: (duplicated, not imported, so this migration's registry-discovery import
#: stayed cheap -- C-002) that DRIFTED from the real vocabulary: it was
#: missing ``activated_glossary_packs`` (10 vs 11 keys), so this migration
#: silently DROPPED an activated glossary pack's activation on migration (a
#: live data-loss drift, SC-005). It is now DERIVED from the single authority
#: ``charter.activation.pack_manager.ACTIVATION_YAML_KEYS`` via :func:`_activation_keys`
#: (module ``__getattr__`` below), so the two vocabularies can never
#: independently drift again (guarded by
#: ``tests/charter/test_activation_vocabulary_setequal.py``). The
#: charter-layer import stays LAZY -- function-scoped inside
#: :func:`_activation_keys`, invoked only when a caller actually accesses
#: ``ACTIVATION_KEYS`` (i.e. when this migration's ``detect()``/``apply()``
#: methods run, not at module-import/registry-discovery time) -- preserving
#: the same cheap-registry-discovery property the literal used to provide.


@functools.lru_cache(maxsize=1)
def _activation_keys() -> tuple[str, ...]:
    """Return the flat activation-key vocabulary, derived from the authority.

    Lazy, function-scoped import of ``charter.activation.pack_manager.
    ACTIVATION_YAML_KEYS`` -- importing anything under the ``charter``
    package eagerly pulls its pydantic-heavy ``charter/__init__.py`` (the
    package re-exports its full public surface, including ``charter.activation.schemas``),
    which would make every ``spec-kitty`` invocation pay that cost merely by
    discovering this migration module (``auto_discover_migrations`` imports
    every migration module via ``pkgutil`` at CLI-startup time). Deferring the
    import to call time means only an actual migration run (or a test that
    calls this helper) pays it -- registry discovery itself stays cheap.
    """
    from charter.activation.pack_manager import ACTIVATION_YAML_KEYS  # noqa: PLC0415 -- lazy charter import (C-002); keeps registry-discovery cheap

    return ACTIVATION_YAML_KEYS


def __getattr__(name: str) -> object:
    """PEP 562 lazy module attribute: resolve ``ACTIVATION_KEYS`` on access.

    Mirrors the codebase's established lazy-module-attribute idiom (e.g.
    a PEP 562 lazy module attribute) so ``from ...m_unify_charter_activation_finalize
    import ACTIVATION_KEYS`` and ``module.ACTIVATION_KEYS`` both keep working
    for existing callers/tests without a module-level import that would
    reintroduce the heavy-import cost :func:`_activation_keys` avoids.
    """
    if name == "ACTIVATION_KEYS":
        return _activation_keys()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _charter_dir(project_path: Path) -> Path:
    return project_path / _KITTIFY_DIRNAME / _CHARTER_DIRNAME


def _config_path(project_path: Path) -> Path:
    return project_path / _KITTIFY_DIRNAME / _CONFIG_FILENAME


def _charter_yaml_path(project_path: Path) -> Path:
    return _charter_dir(project_path) / _CHARTER_YAML


# ---------------------------------------------------------------------------
# Read-side helpers
# ---------------------------------------------------------------------------


def _yaml_roundtrip_loader() -> YAML:
    """Comment/quote-preserving loader -- mirrors ``charter.activation.charter_yaml_io``."""
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096
    return yaml


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    """Safe-load a YAML mapping file. Returns ``{}`` for absent/empty/non-mapping."""
    if not path.exists():
        return {}
    yaml = YAML(typ="safe")
    data = yaml.load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _load_config_roundtrip(config_path: Path) -> tuple[dict[str, Any], YAML]:
    """Load ``config.yaml`` preserving comments/formatting for a later write."""
    yaml = _yaml_roundtrip_loader()
    if not config_path.exists():
        return {}, yaml
    with config_path.open("r", encoding="utf-8") as fh:
        data = yaml.load(fh)
    return (data if isinstance(data, dict) else {}), yaml


def legacy_bundle_present(project_path: Path) -> bool:
    """Return True when ANY of the four legacy bundle files exist on disk."""
    charter_dir = _charter_dir(project_path)
    return any((charter_dir / name).exists() for name in LEGACY_BUNDLE_FILENAMES)


def _config_has_activation(config_data: dict[str, Any]) -> bool:
    """Return True when config.yaml still carries any embedded ``activated_*`` key."""
    return any(key in config_data for key in _activation_keys())


# ---------------------------------------------------------------------------
# charter.yaml composition (MG1 -- deterministic, VERBATIM activation copy)
# ---------------------------------------------------------------------------


def _compose_charter_yaml_document(project_path: Path, config_data: dict[str, Any]) -> dict[str, Any]:
    """Compose the target ``charter.yaml`` document.

    Reads whichever of the four legacy files are present (a missing file
    contributes an empty/default section -- a project need not have all
    four, e.g. one that synced but never ran ``charter generate`` lacks
    ``references.yaml``). Governance/directives are validated through the
    existing pydantic models so a schema drift fails loud here, not on the
    first post-migration read. Activation is copied VERBATIM from
    *config_data* -- only keys ACTUALLY PRESENT there are transplanted, so
    an absent key stays absent (never invented as ``[]``, which would flip
    "all built-ins active" to "none active", MG1 / SC-008) and an explicit
    ``[]`` stays ``[]``.
    """
    from charter.activation.schemas import (  # noqa: PLC0415 -- lazy charter import (C-002)
        CharterCatalog,
        CharterCatalogReference,
        CharterYaml,
        CharterYamlMetadata,
        DirectivesConfig,
        GovernanceConfig,
    )
    from charter.activation.sync import (  # noqa: PLC0415 -- lazy charter import (C-002)
        apply_legacy_governance_selection_key_compat,
    )

    charter_dir = _charter_dir(project_path)
    governance_data = _load_yaml_mapping(charter_dir / _GOVERNANCE_YAML)
    directives_data = _load_yaml_mapping(charter_dir / _DIRECTIVES_YAML)
    references_data = _load_yaml_mapping(charter_dir / _REFERENCES_YAML)

    # CR-01 (charter-authority-flip-01M14RB3 WP03): the retired standalone
    # governance.yaml this migration reads predates the doctrine -> charter
    # selection-key rename, so it may still carry the legacy key. Apply the
    # same dict-level compat the canonical loader uses (charter.activation.sync.
    # load_governance_config) before validating -- otherwise pydantic's
    # default extra="ignore" would silently drop the whole selection block
    # instead of failing loud, defeating this function's own "schema drift
    # fails loud here" contract.
    governance_data = apply_legacy_governance_selection_key_compat(governance_data)
    governance = GovernanceConfig.model_validate(governance_data)
    directives = DirectivesConfig.model_validate(directives_data)
    catalog = CharterCatalog(
        mission=str(references_data.get("mission", "")),
        template_set=str(references_data.get("template_set", "")),
        languages=[str(lang) for lang in (references_data.get("languages") or [])],
        references=[CharterCatalogReference.model_validate(entry) for entry in (references_data.get("references") or [])],
    )
    # metadata.bundle_schema_version is always stamped 2 -- the retired
    # metadata.yaml's own value is NOT inherited (Landmine 2: charter_hash/
    # extraction_mode/sections_parsed are retired self-reference fields, not
    # carried forward).
    metadata = CharterYamlMetadata(
        generated_at=now_utc_stamp(),
        bundle_schema_version=2,
    )

    charter_yaml = CharterYaml(
        governance=governance,
        directives=directives,
        catalog=catalog,
        metadata=metadata,
    )
    document: dict[str, Any] = charter_yaml.model_dump(mode="json", exclude_none=True)

    for key in _activation_keys():
        if key in config_data:
            document[key] = config_data[key]

    return document


def _write_new_charter_yaml(charter_yaml_path: Path, document: dict[str, Any]) -> None:
    """Bootstrap-write a brand new ``charter.yaml``.

    Not the Landmine-3 clobber: this path only runs when ``charter.yaml``
    does not exist yet, so there is no prior authored content to destroy.
    """
    from charter.activation.charter_yaml_io import save_charter_yaml  # noqa: PLC0415

    save_charter_yaml(charter_yaml_path, document)


def _relocate_activation_onto_existing_charter_yaml(charter_yaml_path: Path, config_data: dict[str, Any]) -> None:
    """Merge config-embedded activation onto an ALREADY-authoritative ``charter.yaml``.

    Routed through the shared INV-9 write helper
    (:func:`charter.activation.charter_yaml_io.update_charter_yaml_section`) so
    governance/directives/catalog/metadata/overrides survive byte-for-byte
    (Landmine 3) -- this branch never reconstructs the whole document from
    the legacy files, because a pre-existing ``charter.yaml`` is presumed
    authoritative (hand-authored edits may already have diverged from
    whatever the retired triad last held).
    """
    from charter.activation.charter_yaml_io import update_charter_yaml_section  # noqa: PLC0415

    activation = {key: config_data[key] for key in _activation_keys() if key in config_data}
    if activation:
        update_charter_yaml_section(charter_yaml_path, "activation", activation)


# ---------------------------------------------------------------------------
# config.yaml relocation (INV-2 -- activation-free config + charter: pointer)
# ---------------------------------------------------------------------------


def _mint_pointer_value(charter_yaml_path: Path, project_path: Path) -> str:
    try:
        return charter_yaml_path.resolve(strict=False).relative_to(project_path.resolve(strict=False)).as_posix()
    except ValueError:
        return str(charter_yaml_path)


def _rewrite_config(
    config_path: Path,
    config_data: dict[str, Any],
    yaml_inst: YAML,
    charter_yaml_path: Path,
    project_path: Path,
) -> None:
    """Strip ``activated_*`` keys and mint/refresh the ``charter:`` pointer.

    Comment-preserving ``ruamel.yaml`` round-trip write -- every other
    ``config.yaml`` key (``agents:``, ``org_packs``, tooling) and its
    comments survive untouched; only the activation keys are removed and the
    single ``charter:`` pointer key is added/refreshed.
    """
    for key in _activation_keys():
        config_data.pop(key, None)
    config_data[_CHARTER_POINTER_KEY] = _mint_pointer_value(charter_yaml_path, project_path)

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as fh:
        yaml_inst.dump(config_data, fh)


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


@MigrationRegistry.register
class ConsolidateCharterBundleMigration(BaseMigration):
    """Fold the legacy charter bundle + relocated activation into ``charter.yaml``.

    One-pass, deterministic, idempotent (MG2): once ``charter.yaml`` is
    present, the four legacy files are gone, and ``config.yaml`` carries no
    ``activated_*`` key, ``detect()``/``apply()`` both report a clean 0-change
    no-op.

    Fail-loud (MG3/C-003) is enforced by the read-side charter chokepoints
    this migration's earlier sibling WPs already re-pointed onto
    ``charter.yaml`` (``charter.activation.pack_context.PackContext.from_config``,
    ``charter.activation.consistency_check``, ``specify_cli.cli.commands.charter.
    _synthesis._raise_if_bundle_incomplete``) -- those raise the re-homed
    #2530 error (naming this migration as the remediation) whenever a
    ``charter.yaml``-dependent operation runs against an un-migrated project.
    This migration is the ONE-TIME remediation those chokepoints point at.
    """

    migration_id = MIGRATION_ID
    description = (
        "Fold the four legacy charter bundle files plus config.yaml's "
        "activated_* keys into the git-tracked charter.yaml; retire the four "
        "files; add the config.yaml 'charter:' pointer (FR-010, FR-011, "
        "NFR-003, C-003)."
    )
    target_version = TARGET_VERSION
    runs_on_worktrees = False

    def detect(self, project_path: Path) -> bool:
        """True while ANY legacy file remains, or config still embeds activation."""
        config_data = _load_yaml_mapping(_config_path(project_path))
        return legacy_bundle_present(project_path) or _config_has_activation(config_data)

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        if self.detect(project_path):
            return True, ""
        return (
            False,
            "charter.yaml already composed; no legacy bundle file or config-embedded activation left to migrate",
        )

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        charter_dir = _charter_dir(project_path)
        charter_yaml_path = charter_dir / _CHARTER_YAML
        config_path = _config_path(project_path)

        legacy = legacy_bundle_present(project_path)
        config_data, yaml_inst = _load_config_roundtrip(config_path)
        has_activation = _config_has_activation(config_data)

        # MG2 idempotency: fully-migrated state -> 0 changes, no I/O.
        if not legacy and not has_activation:
            return MigrationResult(success=True, changes_made=[])

        if dry_run:
            return MigrationResult(
                success=True,
                changes_made=self._dry_run_summary(charter_dir, charter_yaml_path, legacy, has_activation),
            )

        changes: list[str] = []
        charter_already_present = charter_yaml_path.exists()

        if charter_already_present:
            if has_activation:
                _relocate_activation_onto_existing_charter_yaml(charter_yaml_path, config_data)
                changes.append(f"Relocated activation keys onto existing {charter_yaml_path}")
        else:
            document = _compose_charter_yaml_document(project_path, config_data)
            _write_new_charter_yaml(charter_yaml_path, document)
            changes.append(f"Composed {charter_yaml_path} from legacy bundle + config activation")

        # NFR-006 ownership proof (B4 — routed, not allowlisted). The four
        # legacy bundle files are retired here, but the charter_already_present
        # branch above does NOT re-fold them into a pre-existing (authoritative)
        # charter.yaml — so a bundle whose content diverges from charter.yaml
        # would be lost on a raw unlink. Ownership that "charter.yaml already
        # captures this file" is not provable on disk (a YAML bundle carries no
        # package version marker; name/directory identity is never proof —
        # charter L470), so route the removal through the asset-preservation
        # guard with an external backup_parent: unprovable ⇒ the bytes are
        # archived verbatim BEFORE removal (charter L472). The guard performs the
        # removal, so no raw unlink literal remains at this site.
        from specify_cli.asset_preservation import (  # noqa: PLC0415 -- lazy import (C-002); keeps registry-discovery cheap
            CanonicalContentProver,
            guard_destructive_removal,
        )

        bundle_prover = CanonicalContentProver()
        bundle_backup = project_path / _KITTIFY_DIRNAME
        for name in LEGACY_BUNDLE_FILENAMES:
            path = charter_dir / name
            verdict = guard_destructive_removal(
                path,
                project_path,
                prover=bundle_prover,
                backup_parent=bundle_backup,
            )
            if verdict.reason == "absent":
                continue
            if verdict.backup_path is not None:
                changes.append(f"Preserved divergent {path} to {verdict.backup_path}, then retired it")
            else:
                changes.append(f"Deleted {path}")

        if has_activation or _CHARTER_POINTER_KEY not in config_data:
            _rewrite_config(config_path, config_data, yaml_inst, charter_yaml_path, project_path)
            changes.append("Updated .kittify/config.yaml: removed activated_* keys, added charter: pointer")

        return MigrationResult(success=True, changes_made=changes)

    @staticmethod
    def _dry_run_summary(charter_dir: Path, charter_yaml_path: Path, legacy: bool, has_activation: bool) -> list[str]:
        summary: list[str] = []
        if legacy:
            if charter_yaml_path.exists():
                summary.append(f"dry-run: would delete stale legacy files under {charter_dir}")
            else:
                summary.append(f"dry-run: would compose {charter_yaml_path} from legacy bundle files")
            summary.extend(f"dry-run: would delete {charter_dir / name}" for name in LEGACY_BUNDLE_FILENAMES if (charter_dir / name).exists())
        if has_activation:
            summary.append("dry-run: would relocate activated_* keys from config.yaml onto charter.yaml and add the charter: pointer")
        return summary


#: Only the migration class is exported. ``MIGRATION_ID``/``TARGET_VERSION``/
#: ``ACTIVATION_KEYS``/``LEGACY_BUNDLE_FILENAMES``/``legacy_bundle_present``
#: stay unexported module internals -- the dead-symbol gate
#: (tests/architectural/test_no_dead_symbols.py) content-tier-hashes bare
#: module-level ``NAME = "<string>"`` constant declarations structurally, so
#: a second module also naming a public ``MIGRATION_ID``/``TARGET_VERSION``
#: constant (``m_3_2_0rc35_unified_bundle.py``) collides in the collision
#: index regardless of the two literals' actual values, escalating both to
#: the module_path tier and un-allowlisting them. Trimming ``__all__`` here
#: (rather than re-allowlisting two symbols) removes the collision at its
#: root; this module's own tests import these names directly by fully
#: qualified path (``__all__`` only governs ``from module import *``).
__all__ = [
    "ConsolidateCharterBundleMigration",
]
