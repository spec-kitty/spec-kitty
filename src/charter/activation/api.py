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

#: The curated activation public surface. Keep it sorted and explicit; every entry
#: MUST be an identity re-export of a ``charter.activation`` symbol (never a
#: ``charter.offering`` one) and carry an identity-contract row in
#: ``tests/architectural/test_charter_activation_api_reexport.py``.
__all__ = [
    "canonical_mission_type_key",
    "read_mission_type",
    "requires_substantive_spec_for",
]
