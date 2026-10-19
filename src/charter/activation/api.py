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

# Activation result / effective-set / org-required-stem / selection-diagnostic
# primitives the ``charter activate`` / ``interview`` commands and the runtime
# doctor consume (#6099). Public per the respective modules' ``__all__``.
from charter.activation.activation_engine import EffectiveSet as EffectiveSet
from charter.activation.org_charter import org_required_stems as org_required_stems
from charter.activation.pack_manager import ActivationResult as ActivationResult
from charter.activation.resolver import (
    UNKNOWN_SELECTION_DIAGNOSTIC as UNKNOWN_SELECTION_DIAGNOSTIC,
)

#: The curated activation public surface. Keep it sorted and explicit; every entry
#: MUST be an identity re-export of a ``charter.activation`` symbol (never a
#: ``charter.offering`` one) and carry an identity-contract row in
#: ``tests/architectural/test_charter_activation_api_reexport.py``.
__all__ = [
    "MANIFEST_PATH",
    "UNKNOWN_SELECTION_DIAGNOSTIC",
    "ActivationResult",
    "EffectiveSet",
    "IdentityEntry",
    "IdentityIndex",
    "append_synthesized_activations",
    "canonical_mission_type_key",
    "canonical_yaml",
    "created_slugs_by_kind",
    "finalize_manifest",
    "load_yaml",
    "org_required_stems",
    "read_mission_type",
    "requires_substantive_spec_for",
    "resolve_activation_write_target",
    "verify",
]
