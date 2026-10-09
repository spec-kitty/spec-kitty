"""Every single-owner doctrine artifact stays delivered to the actions that need it.

Rules are stated once, in one owner, and every other artifact references the
owner by id. Trimming a copy can remove the only path that carried an owner
into an agent's context, so this guard checks the owners through the SAME
resolution ``charter context --action`` uses: the action doctrine bundle
(``_load_action_doctrine_bundle``: shipped DRG -> activation filter ->
``resolve_context``) for ``software-dev`` implement and review, at both the
compact (d=1) and bootstrap (d=2) depths.

Two activation profiles are pinned:

* ``default-pack`` -- a project whose ``.kittify/config.yaml`` is the shipped
  built-in ``default`` preset (``packs/built-in/presets/default.yaml``);
* ``unfiltered`` -- no activation filter (``pack_context=None``), i.e. every
  built-in artifact admitted, which is where the DRG edges themselves are
  measured.

The delivery floors are literal sets, not derived from a file this test
protects: with no activation filter every owner must be delivered to every
cell; under the default pack the four directives listed in
``_DEFAULT_PACK_FLOOR`` must be. A delivery cell may gain owners freely; it
may not lose one.

Two further delivery facts are asserted directly:

* ``DIRECTIVE_052`` reaches ``implement`` (unfiltered) through
  ``test-first-bug-fixing`` -- the ``test-first-bug-fixing --suggests-->
  DIRECTIVE_052`` edge is asserted so the delivery does not silently depend on
  a prose copy.
* The findings-disposition contract is not a node: it is delivered as part of
  ``procedure:adversarial-squad-deployment``, so wherever the procedure is
  delivered the contract text must be in it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.action_doctrine_bundle import _load_action_doctrine_bundle
from charter.activation.pack_context import PackContext
from charter.offering.drg.loader import load_built_in_graph
from charter.offering.drg.models import Relation

pytestmark = [pytest.mark.doctrine]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_PACK = _REPO_ROOT / "packs/built-in/presets/default.yaml"

_SQUAD = "procedure:adversarial-squad-deployment"

#: The single-owner artifacts whose delivery is guarded.
_OWNERS: frozenset[str] = frozenset(
    {
        "styleguide:quadruple-a-test-format",
        "directive:DIRECTIVE_025",
        "directive:DIRECTIVE_030",
        "directive:DIRECTIVE_034",
        "directive:DIRECTIVE_037",
        "directive:DIRECTIVE_051",
        "directive:DIRECTIVE_052",
        _SQUAD,
    }
)

#: Owners the shipped default pack must deliver at every action and depth.
_DEFAULT_PACK_FLOOR: frozenset[str] = frozenset(
    {
        "directive:DIRECTIVE_025",
        "directive:DIRECTIVE_030",
        "directive:DIRECTIVE_034",
        "directive:DIRECTIVE_037",
    }
)

#: Delivery floor per (activation profile, action, depth): with no activation
#: filter every owner is delivered; under the default pack the floor above is.
_FLOOR: dict[tuple[str, str, int], frozenset[str]] = {
    (profile, action, depth): (_DEFAULT_PACK_FLOOR if profile == "default-pack" else _OWNERS)
    for profile in ("default-pack", "unfiltered")
    for action in ("implement", "review")
    for depth in (1, 2)
}


def _delivered(tmp_path: Path, *, profile: str, action: str, depth: int) -> frozenset[str]:
    root = tmp_path / profile
    (root / ".kittify").mkdir(parents=True, exist_ok=True)
    (root / ".kittify" / "config.yaml").write_text(_DEFAULT_PACK.read_text(encoding="utf-8"), encoding="utf-8")
    pack_context = PackContext.from_config(root) if profile == "default-pack" else None
    bundle = _load_action_doctrine_bundle(
        repo_root=root,
        action=action,
        effective_depth=depth,
        mission_type="software-dev",
        pack_context=pack_context,
    )
    return frozenset(
        {f"directive:{i}" for i in bundle.directive_ids}
        | {f"tactic:{i}" for i in bundle.tactic_ids}
        | {f"styleguide:{i}" for i in bundle.styleguide_ids}
        | {f"toolguide:{i}" for i in bundle.toolguide_ids}
        | {f"procedure:{i}" for i in bundle.procedure_ids}
    )


@pytest.mark.parametrize(("profile", "action", "depth"), sorted(_FLOOR), ids=lambda v: str(v))
def test_owner_delivery_meets_the_floor(tmp_path: Path, profile: str, action: str, depth: int) -> None:
    delivered = _delivered(tmp_path, profile=profile, action=action, depth=depth) & _OWNERS
    missing = _FLOOR[(profile, action, depth)] - delivered
    assert not missing, f"{profile}/{action}/d={depth} lost delivery of {sorted(missing)}"


def test_directive_052_is_carried_by_test_first_bug_fixing(tmp_path: Path) -> None:
    """052 reaches implement through the bug-fixing procedure's own edge."""
    graph = load_built_in_graph()
    assert any(e.source == "procedure:test-first-bug-fixing" and e.target == "directive:DIRECTIVE_052" and e.relation is Relation.SUGGESTS for e in graph.edges)
    assert any(e.source == "action:software-dev/implement" and e.target == "procedure:test-first-bug-fixing" and e.relation is Relation.SCOPE for e in graph.edges)
    assert "directive:DIRECTIVE_052" in _delivered(tmp_path, profile="unfiltered", action="implement", depth=1)


def test_disposition_contract_ships_inside_the_delivered_procedure() -> None:
    """The contract is part of the procedure, so procedure delivery carries it."""
    from charter.offering.service import DoctrineService

    procedure = DoctrineService().procedures.get("adversarial-squad-deployment")
    assert procedure is not None
    text = procedure.model_dump_json()
    for disposition in ("accepted", "changed", "deferred_with_rationale"):
        assert disposition in text
    assert "no finding may be dropped silently" in text
