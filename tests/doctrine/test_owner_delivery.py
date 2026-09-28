"""SC-007: every epic owner is still delivered wherever it was delivered before.

Mission ``squad-doctrine-single-owner-01M3KBP7`` trimmed copies of rules down to
one owner each. A trimmed copy can be the only path that carried an owner into
an agent's context, so this regression guard checks the owners through the
SAME resolution ``charter context --action`` uses: the action doctrine bundle
(``_load_action_doctrine_bundle``: shipped DRG -> activation filter ->
``resolve_context``) for ``software-dev`` implement and review, at both the
compact (d=1) and bootstrap (d=2) depths.

Two activation profiles are pinned:

* ``default-pack`` -- a project whose ``.kittify/config.yaml`` is the shipped
  ``src/charter/activation/packs/default.yaml``;
* ``unfiltered`` -- no activation filter (``pack_context=None``), i.e. every
  built-in artifact admitted, which is where the DRG edges themselves are
  measured.

The BASE sets are hard-coded literals captured ONCE on a ``git worktree add``
of the pre-mission base (``git merge-base HEAD origin/main`` =
``dccf6aa7d523``) with ``scratchpad/probe_delivery.py`` -- never derived from a
golden this mission edits. The assertion is HEAD >= BASE, per cell.

Permitted additions (explicit):

* ``DIRECTIVE_052`` must be delivered at ``implement`` (unfiltered) through
  ``test-first-bug-fixing`` -- it was delivered at base too, and the
  ``test-first-bug-fixing --suggests--> DIRECTIVE_052`` edge is asserted here
  so the delivery does not silently depend on the prose copy WP05 trimmed.
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
_DEFAULT_PACK = _REPO_ROOT / "src/charter/activation/packs/default.yaml"

_SQUAD = "procedure:adversarial-squad-deployment"

#: The epic owners (spec.md SC-007).
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

_ALL_OWNERS_AT_BASE = _OWNERS

#: BASE owner x action x depth, captured on dccf6aa7 (see module docstring):
#:
#:   $ PYTHONPATH=$BASE/src SPEC_KITTY_PACKS_ROOT=$BASE/packs \
#:       python scratchpad/probe_delivery.py $BASE
#:   implement 1 ['directive:DIRECTIVE_025', 'directive:DIRECTIVE_030', 'directive:DIRECTIVE_034', 'directive:DIRECTIVE_037']
#:   implement 2 (same)   review 1 (same)   review 2 (same)
#:
#:   $ ... python scratchpad/probe_delivery.py $BASE --unfiltered
#:   implement 1 [all eight owners]   implement 2 [all eight]
#:   review 1 [all eight]             review 2 [all eight]
_BASE_DEFAULT_PACK: frozenset[str] = frozenset(
    {
        "directive:DIRECTIVE_025",
        "directive:DIRECTIVE_030",
        "directive:DIRECTIVE_034",
        "directive:DIRECTIVE_037",
    }
)

_BASE: dict[tuple[str, str, int], frozenset[str]] = {
    (profile, action, depth): (_BASE_DEFAULT_PACK if profile == "default-pack" else _ALL_OWNERS_AT_BASE)
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


@pytest.mark.parametrize(("profile", "action", "depth"), sorted(_BASE), ids=lambda v: str(v))
def test_owner_delivery_is_a_superset_of_base(tmp_path: Path, profile: str, action: str, depth: int) -> None:
    head = _delivered(tmp_path, profile=profile, action=action, depth=depth) & _OWNERS
    missing = _BASE[(profile, action, depth)] - head
    assert not missing, f"{profile}/{action}/d={depth} lost delivery of {sorted(missing)}"


def test_base_literals_are_non_vacuous() -> None:
    """The literal must name owners, or HEAD >= BASE would hold trivially."""
    assert all(_BASE.values())
    assert _BASE[("unfiltered", "implement", 1)] == _OWNERS


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
