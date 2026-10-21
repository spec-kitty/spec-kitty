"""Public entry-point seam for the charter **activation** layer (#6188 / #6099).

This module is the curated public entry-point seam of ``charter.activation`` — the
stable seam that external consumers (``specify_cli``, ``runtime``, ``glossary``,
``mission_runtime``) import. Depending only on this seam lets the activation
*internals* behind it be rewritten, re-homed, or extracted to a separate service
(even a non-Python one) without impacting any consumer: only this module's
re-export targets change, never the consumer imports.

It is the one sanctioned door into the activation layer: the other doors that
resolve into it (a direct ``charter.activation.<submodule>`` import, and the lazy
root facade ``charter.<name>``) are ratcheted by the boundary gate, not blessed.
It is the activation analogue of :mod:`charter.offering.api` and is kept
**strictly separate** from it. The offering / activation split is an architectural
invariant (ADR ``2026-10-06-2`` §1; the gate
``tests/architectural/test_charter_offering_does_not_import_activation.py`` forbids
``charter.offering.*`` from importing ``charter.activation.*``): offering and
activation are two independent extractable units, each hidden behind its own seam.
This module therefore re-exports **only** ``charter.activation`` symbols — never a
``charter.offering`` symbol (that belongs on ``charter.offering.api`` / the
``charter.*`` offering facades). The negative guard
``tests/architectural/test_charter_activation_api_reexport.py`` pins both the
by-identity re-export and the no-offering-leak rule.

Re-exports use the explicit ``X as X`` form so the symbol's type survives
``mypy --strict`` (a bare ``from … import X`` re-export is treated as a private
import and would not be re-exported) and so the identity gate can assert
``charter.activation.api.X is charter.activation.<module>.X``.

Growth: the surface grows as consumers are drained onto it (owner: epic #6099,
the charter extraction). This is the first tranche (the mission-type-key access
cluster). The enforcing boundary gate that forbids external consumers from
reaching ``charter.activation.*`` internals
(``tests/architectural/test_runtime_charter_activation_boundary.py``) ships with
this seam as a shrink-only baseline ratchet: the pre-existing reaches are frozen
and drained tranche by tranche, while any *new* reach fails immediately.
"""

from __future__ import annotations

# Mission-type-key access — the canonical reader/normalizer pair the mission
# lifecycle, retrospective and diagnostics surfaces consume. Public per
# charter.activation.mission_type_key.__all__.
from charter.activation.mission_type_key import (
    canonical_mission_type_key as canonical_mission_type_key,
    read_mission_type as read_mission_type,
)

# Mission-type capability access — the substantive-spec requirement a consumer
# (the resume-probe prerequisite) reads instead of reaching the activation
# internals. Public per charter.activation.mission_type_profiles.__all__.
from charter.activation.mission_type_profiles import (
    requires_substantive_spec_for as requires_substantive_spec_for,
)

# Synthesis-manifest primitives — the manifest path/load/verify/finalize +
# canonical serialization the charter preflight safe-heal (#6366) consumes to
# re-stamp a lagging ``bundle_content_hash`` without reaching activation
# internals. Public per the respective modules' ``__all__``.
from charter.activation.synthesizer.manifest import (
    MANIFEST_PATH as MANIFEST_PATH,
    finalize_manifest as finalize_manifest,
    load_yaml as load_yaml,
    verify as verify,
)
from charter.activation.synthesizer.synthesize_pipeline import (
    canonical_yaml as canonical_yaml,
)

# Legacy project-intent directive convergence (#6443, FR-008) — the one helper the
# ``4.0.0rc8_project_intent_directive_rename`` migration and ``charter synthesize`` /
# ``resynthesize`` both call. Public per charter.activation.synthesizer.legacy_rename.__all__.
from charter.activation.synthesizer.legacy_rename import (
    LegacyRenameRefusedError as LegacyRenameRefusedError,
    RenameReport as RenameReport,
    rename_legacy_project_intent_directive as rename_legacy_project_intent_directive,
)

# Reach-only activation — the synthesis-run helpers the ``charter synthesize`` /
# ``resynthesize`` CLI commands consume (#6404, #6442) to append the tactics and
# styleguides a run created to an explicit ``activated_<kind>s`` list. Public per
# charter.activation.synthesizer.reach_only.__all__.
from charter.activation.synthesizer.reach_only import (
    append_synthesized_activations as append_synthesized_activations,
    created_slugs_by_kind as created_slugs_by_kind,
)

# Activation write-target resolution — the ``(path, data, save)`` triple a
# consumer (the rc35 mission-type activation migration's post-fold short-circuit)
# reads to decide whether ``mission_type_activations`` already lives in the
# resolved charter write target, instead of reaching the activation internals.
# Public per charter.activation.pack_manager.__all__.
from charter.activation.pack_manager import (
    resolve_activation_write_target as resolve_activation_write_target,
)

# Identity index — the per-invocation, layer-aware token <-> declared id <-> stem
# map every activation/selection consumer resolves through. Public per
# charter.activation.identity_index.__all__.
from charter.activation.identity_index import (
    IdentityEntry as IdentityEntry,
    IdentityIndex as IdentityIndex,
)

# Operator-confirmed project languages (``.kittify/config.yaml`` ``languages``): the read the
# synthesis request builder uses and the interview's detect/propose/confirm/store step (FR-020).
from charter.activation.language_authority import configured_languages as configured_languages
from charter.activation.language_settlement import (
    LanguageSettlement as LanguageSettlement,
    settle_project_languages as settle_project_languages,
    store_language_settlement as store_language_settlement,
)

# Activation result / effective-set / org-required-stem / selection-diagnostic
# primitives the ``charter activate`` / ``interview`` commands and the runtime
# doctor consume (#6099). Public per the respective modules' ``__all__``.
from charter.activation.activation_engine import EffectiveSet as EffectiveSet, deny_delta as deny_delta
from charter.activation.org_charter import org_required_stems as org_required_stems
from charter.activation.pack_manager import ActivationResult as ActivationResult

# The manifest bundle-hash restamp an activation writer runs after a committed
# promotion (the activation ledger is in the bundle hash, FR-018). Public per
# charter.activation.bundle_restamp.__all__.
from charter.activation.bundle_restamp import restamp_bundle_hash as restamp_bundle_hash
from charter.activation.resolver import (
    UNKNOWN_SELECTION_DIAGNOSTIC as UNKNOWN_SELECTION_DIAGNOSTIC,
)

# The activation reader's charter.yaml soundness rule, consumed by the ``charter synthesize``
# gate (#6415). Public per charter.activation.pack_context.__all__. Its typed refusal,
# ``ActiveCharterConfigError``, is re-exported once below from the activation ledger.
from charter.activation.pack_context import (
    load_charter_yaml_mapping as load_charter_yaml_mapping,
)

# Activation ledger seam (persistent-deactivation-ledger WP02) -- the typed
# ledger, its load, the explicit deny-list choice and the guard's refusal, for
# the specify_cli consumers re-pointed onto the ledger (list, doctor, charter
# activate/deactivate). Public per charter.activation.activation_ledger.__all__.
from charter.activation.activation_ledger import (
    ActivationLedger as ActivationLedger,
    DenyListChoice as DenyListChoice,
    DenyListWriteRefused as DenyListWriteRefused,
    load_activation_ledger as load_activation_ledger,
    refuse_unmigrated_deny_write as refuse_unmigrated_deny_write,
    resolve_ledger_source as resolve_ledger_source,
)

# Ledger migration (persistent-deactivation-ledger WP08) -- the pure planner and
# its apply, shared by the ``4.0.0rc8_activation_ledger`` upgrade migration and
# ``spec-kitty migrate activation-ledger``, plus the error the planner raises on
# an unreadable surface. Public per charter.activation.activation_ledger.__all__.
from charter.activation.activation_ledger import (
    ActiveCharterConfigError as ActiveCharterConfigError,
    LedgerMigrationPlan as LedgerMigrationPlan,
    LedgerMigrationRefusal as LedgerMigrationRefusal,
    LedgerMigrationRefused as LedgerMigrationRefused,
    LedgerMove as LedgerMove,
    apply_ledger_migration as apply_ledger_migration,
    plan_ledger_migration as plan_ledger_migration,
)

# Activation diagnostics (persistent-deactivation-ledger WP09) -- the doctor's
# activation-drift findings and the FR-023 required-but-omitted reader that
# ``doctor charter-packs`` and ``charter list`` consume. Public per
# charter.activation.activation_ledger.__all__.
from charter.activation.activation_ledger import (
    LedgerFinding as LedgerFinding,
    LedgerFindings as LedgerFindings,
    RequiredOmission as RequiredOmission,
    ledger_findings as ledger_findings,
    required_not_in_force as required_not_in_force,
)

# Agent Skills specification limits (#6475) -- the frontmatter name/description
# caps the command-skill renderer in specify_cli.skills enforces. Public per
# charter.activation.skill_preparation.
from charter.activation.skill_preparation import (
    MAX_SKILL_DESCRIPTION_LENGTH as MAX_SKILL_DESCRIPTION_LENGTH,
    MAX_SKILL_NAME_LENGTH as MAX_SKILL_NAME_LENGTH,
)

#: The curated activation public surface. Keep it sorted and explicit; every entry
#: MUST be an identity re-export of a ``charter.activation`` symbol (never a
#: ``charter.offering`` one) and carry an identity-contract row in
#: ``tests/architectural/test_charter_activation_api_reexport.py``.
__all__ = [
    "MANIFEST_PATH",
    "MAX_SKILL_DESCRIPTION_LENGTH",
    "MAX_SKILL_NAME_LENGTH",
    "UNKNOWN_SELECTION_DIAGNOSTIC",
    "ActivationLedger",
    "ActivationResult",
    "ActiveCharterConfigError",
    "DenyListChoice",
    "DenyListWriteRefused",
    "EffectiveSet",
    "IdentityEntry",
    "IdentityIndex",
    "LanguageSettlement",
    "LedgerFinding",
    "LedgerFindings",
    "LedgerMigrationPlan",
    "LedgerMigrationRefusal",
    "LedgerMigrationRefused",
    "LedgerMove",
    "LegacyRenameRefusedError",
    "RenameReport",
    "RequiredOmission",
    "append_synthesized_activations",
    "apply_ledger_migration",
    "canonical_mission_type_key",
    "canonical_yaml",
    "configured_languages",
    "created_slugs_by_kind",
    "deny_delta",
    "finalize_manifest",
    "ledger_findings",
    "load_activation_ledger",
    "load_charter_yaml_mapping",
    "load_yaml",
    "org_required_stems",
    "plan_ledger_migration",
    "read_mission_type",
    "refuse_unmigrated_deny_write",
    "rename_legacy_project_intent_directive",
    "required_not_in_force",
    "requires_substantive_spec_for",
    "resolve_activation_write_target",
    "resolve_ledger_source",
    "restamp_bundle_hash",
    "settle_project_languages",
    "store_language_settlement",
    "verify",
]
