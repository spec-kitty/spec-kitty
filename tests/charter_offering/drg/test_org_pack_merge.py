"""The org-tier edge bridge is a registry ``ModelBridge`` with full field coverage.

WP02 (mission ``doctrine-delivery-reachability``), contract ``writer-registry.md``
obligation **W-3**.

``bridge_org_edge_to_drg_edge`` mints a :class:`DRGEdge` from an org-fragment
edge (``_OrgDRGEdge``). WP01 registered it as the sole ``ModelBridge`` but left
its field coverage un-asserted: the bridge restated three of the edge's fields
(``source`` / ``target`` / ``relation``) and dropped the author's ``reason``
before any writer could run. A ``ModelBridge``'s defect class is model->model
field coverage, not serialisation, so this is where W-3 is proved.

The obligation, stated as a test
-------------------------------
For every ``DRGEdge`` field the *fragment schema* can express, the minted edge
carries the fragment's value. The expressible set is derived --
``set(_OrgDRGEdge.model_fields) & set(DRGEdge.model_fields)`` -- so a field added
to either model tomorrow is covered without editing this test. ``generated_reason``
(machine provenance on the projection subclass) is deliberately not a ``DRGEdge``
field and so is correctly outside the set; the author's ``reason`` is inside it.

The complementary guard -- a *projected* edge (author wrote no reason) must mint
``reason=None`` -- pins that carrying the field does not invent one, preserving
the "reason means an author wrote a reason" invariant the merge relies on.
"""

from __future__ import annotations

import pytest

from charter.offering.drg.merge import bridge_org_edge_to_drg_edge
from charter.offering.drg.models import DRGEdge, Relation
from charter.offering.drg.org_pack_loader import _OrgDRGEdge, _ProjectedOrgDRGEdge

pytestmark = [pytest.mark.doctrine, pytest.mark.fast]

_SOURCE_MARKER = "org:acme"

#: A fully-qualified endpoint resolves verbatim (precedence rule 2), so the
#: bridge needs no fragment-local or built-in index to mint the edge.
_QUALIFIED_SOURCE = "directive:DIRECTIVE_001"
_QUALIFIED_TARGET = "directive:DIRECTIVE_003"


def _fragment_expressible_edge_fields() -> set[str]:
    """Every ``DRGEdge`` field name the org fragment edge schema can also express."""
    return set(_OrgDRGEdge.model_fields) & set(DRGEdge.model_fields)


def _authored_fragment_edge(reason: str | None) -> _OrgDRGEdge:
    return _OrgDRGEdge(
        source=_QUALIFIED_SOURCE,
        target=_QUALIFIED_TARGET,
        relation=Relation.REQUIRES.value,
        reason=reason,
    )


def _bridge(edge: _OrgDRGEdge) -> DRGEdge:
    minted, conflict = bridge_org_edge_to_drg_edge(
        edge, {}, set(), _SOURCE_MARKER
    )
    assert conflict is None, f"unexpected endpoint conflict: {conflict}"
    assert minted is not None
    return minted


# ---------------------------------------------------------------------------
# Vacuity guard -- if ``reason`` ever leaves ``_OrgDRGEdge`` the coverage test
# below would silently stop exercising the drop, so pin the probe field.
# ---------------------------------------------------------------------------


def test_reason_is_a_fragment_expressible_edge_field() -> None:
    """The coverage assertion is only non-vacuous while ``reason`` is shared."""
    assert "reason" in _fragment_expressible_edge_fields()


# ---------------------------------------------------------------------------
# T010 (W-3) -- the bridge carries every fragment-expressible edge field
# ---------------------------------------------------------------------------


def test_the_org_bridge_carries_every_fragment_expressible_edge_field() -> None:
    """W-3: no fragment-expressible edge field the author set is dropped on mint."""
    fragment_edge = _authored_fragment_edge("because the pack author said so")

    minted = _bridge(fragment_edge)

    for name in _fragment_expressible_edge_fields():
        fragment_value = getattr(fragment_edge, name)
        if fragment_value is None:
            continue
        assert getattr(minted, name) is not None, (
            f"org bridge dropped fragment-expressible edge field {name!r} "
            f"(fragment set it to {fragment_value!r})"
        )


def test_the_org_bridge_preserves_the_author_reason() -> None:
    """T010/T011: the author's rationale survives the bridge verbatim."""
    fragment_edge = _authored_fragment_edge("because the pack author said so")

    minted = _bridge(fragment_edge)

    assert minted.reason == "because the pack author said so"


def test_a_projected_edge_without_a_reason_still_mints_reason_none() -> None:
    """Carrying ``reason`` must not invent one for machine-projected edges."""
    projected = _ProjectedOrgDRGEdge(
        source=_QUALIFIED_SOURCE,
        target=_QUALIFIED_TARGET,
        relation=Relation.ENHANCES.value,
        generated_reason="declared via directive.enhances field",
    )

    minted = _bridge(projected)

    assert minted.reason is None
