"""Anti-drift parity guard for ``DIRECT_WRITE_KINDS`` (WP01 / T005 / NFR-002).

The five registration-writing kinds are declared once in
``charter.offering.artifact_kinds.DIRECT_WRITE_KINDS``. Two live surfaces must
stay aligned with that single constant:

- the DRG **project scanner** (``charter.offering.drg.project_scan``), and
- the synthesis-manifest **``ManifestArtifactEntry.kind`` ``Literal``**
  (``charter.activation.synthesizer.manifest``).

The scanner binds the constant directly, so its half is by-construction; the
manifest ``Literal`` cannot consume a runtime tuple, so its alignment is
by-test — that is why this guard exists.

Scope boundary (post-tasks squad HIGH): WP01 asserts scanner + manifest ONLY.
The third surface ``bundle._KIND_SUFFIX`` is only 5-kind after WP02 and its
assertion is added by WP02 T006 in WP02's own test file — this WP01-owned test
never imports or reaches into ``bundle.py``.

Both assertions introspect the **live** definitions (module-bound tuple /
``typing.get_args`` on the live field annotation) — no hardcoded set literal,
which would prove nothing and be itself fakeable.
"""

from __future__ import annotations

import typing

import pytest

from charter.activation.synthesizer.manifest import ManifestArtifactEntry
from charter.activation.synthesizer.synthesize_pipeline import ProvenanceEntry
from charter.offering import artifact_kinds
from charter.offering.artifact_kinds import DIRECT_WRITE_KINDS
from charter.offering.drg import project_scan

pytestmark = [pytest.mark.unit]


def test_scanner_binds_the_canonical_constant() -> None:
    # The scanner references the single canonical constant rather than a
    # re-declared local five-kind tuple (`is` proves the exact object binding).
    assert project_scan.DIRECT_WRITE_KINDS is artifact_kinds.DIRECT_WRITE_KINDS
    assert set(project_scan.DIRECT_WRITE_KINDS) == set(DIRECT_WRITE_KINDS)


def test_manifest_literal_matches_direct_write_kinds() -> None:
    annotation = ManifestArtifactEntry.model_fields["kind"].annotation
    literal_args = set(typing.get_args(annotation))
    assert literal_args == set(DIRECT_WRITE_KINDS)


def test_synthesize_pipeline_literal_matches_direct_write_kinds() -> None:
    # Third by-test surface: the synthesis pipeline's ``ProvenanceEntry`` carries
    # the same five-kind ``Literal`` (via the module-level ``_ArtifactKind`` alias
    # reused by the field and both ``cast`` sites). Same rationale as the manifest
    # Literal — a Literal cannot consume the runtime tuple, so it is guarded here.
    annotation = ProvenanceEntry.model_fields["artifact_kind"].annotation
    literal_args = set(typing.get_args(annotation))
    assert literal_args == set(DIRECT_WRITE_KINDS)


def test_direct_write_kinds_order_is_paired_with_scanner_schemas() -> None:
    """Order guard (landing fold, #4852 second-opinion squad).

    ``project_scan`` pairs ``DIRECT_WRITE_KINDS`` positionally with a local
    ``schemas`` tuple via ``zip(..., strict=True)`` — but ``strict=True`` only
    checks equal length, and every other parity guard above compares by ``set``
    (order-blind). So a reorder of ``DIRECT_WRITE_KINDS`` that did NOT mirror the
    ``schemas`` tuple would silently validate each kind against the wrong Pydantic
    model (e.g. ``procedure`` against ``AgentProfile``) and pass every existing
    test. Pin the canonical order and its intended kind→schema pairing so such a
    reorder fails loud here and forces the mirror update the scanner docstring
    already demands.
    """
    from charter.offering.agent_profiles.profile import AgentProfile
    from charter.offering.directives.models import Directive
    from charter.offering.procedures.models import Procedure
    from charter.offering.styleguides.models import Styleguide
    from charter.offering.tactics.models import Tactic

    # Mirror of ``project_scan``'s positional ``(kinds, schemas)`` pairing.
    expected_pairing = (
        ("directive", Directive),
        ("tactic", Tactic),
        ("styleguide", Styleguide),
        ("procedure", Procedure),
        ("agent_profile", AgentProfile),
    )
    assert tuple(kind for kind, _ in expected_pairing) == DIRECT_WRITE_KINDS
