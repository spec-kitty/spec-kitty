"""Red-first coverage for WP05: model-task-routing tactic + DRG resolution.

Covers FR-006 (new ``model-task-routing`` tactic + directive ``suggests`` edge
+ charter token repoint), FR-007 (one-line ``suggests`` edge for the
pre-existing ``autonomous-operation-protocol`` tactic), and C-002
(DRG-driven resolution -- ``references.yaml`` rows come from the graph, never
hand-written).

Pre-fix, both tactics dangle:

* ``model-task-routing`` does not exist as an artifact at all.
* ``autonomous-operation-protocol`` exists and is activated
  (``.kittify/config.yaml`` ``activated_tactics``) but has no inbound
  directive ``suggests`` edge in ``src/charter/offering/graph.yaml``, so it is not
  directive-reachable and does not resolve in the compiled charter
  references.

These tests assert resolution via two independent, non-fakeable routes:

1. Real DRG traversal over the shipped ``src/charter/offering/graph.yaml``
   (:func:`charter.offering.drg.query.resolve_transitive_refs`) starting from an
   activated directive -- proves the graph edge exists, not just that a
   string appears somewhere.
2. The real charter compiler (:func:`charter.activation.compiler.compile_charter`)
   against the project's own interview answers and a real
   ``charter.offering.service.CharterOfferingService`` rooted at ``src/doctrine`` -- proves
   the resolved reference carries the tactic's actual body (``purpose``),
   which is what ``charter context`` surfaces downstream, not merely an id
   string dropped into ``references.yaml`` by hand.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.compiler import compile_charter
from charter.activation.interview import read_interview_answers
from charter.offering.drg.loader import load_built_in_graph
from charter.offering.drg.models import DRGGraph, Relation
from charter.offering.drg.query import resolve_transitive_refs
from charter.offering.drg.validator import assert_valid
from charter.offering.service import CharterOfferingService

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

REPO_ROOT = Path(__file__).resolve().parents[2]
ANSWERS_PATH = REPO_ROOT / ".kittify" / "charter" / "interview" / "answers.yaml"
CHARTER_PATH = REPO_ROOT / ".kittify" / "charter" / "charter.md"

# The activated directive this WP wires the new/orphaned tactics to. Chosen
# because it is already activated (``.kittify/config.yaml``
# ``activated_directives``) and already carries the sibling suggests edges
# this WP's edges are patterned after (canonical-source-unification,
# ownership-map-leeway, reviewer-implementer-role-separation,
# terminology-guard).
_ANCHOR_DIRECTIVE_URN = "directive:DIRECTIVE_044"

# Pinned fragments of each tactic's real ``purpose`` body. A match proves the
# resolved reference carries the tactic's actual content, not a placeholder
# or a hand-written references.yaml string (T023 anti-fake requirement).
_MODEL_TASK_ROUTING_PURPOSE_FRAGMENT = "match model strength to task difficulty"
_AUTONOMOUS_OPERATION_PURPOSE_FRAGMENT = "clear decision boundaries"


def _load_shipped_graph() -> DRGGraph:
    graph = load_built_in_graph()
    assert_valid(graph)
    return graph


def _real_doctrine_service() -> CharterOfferingService:
    # Built-in pack content relocated to ``packs/built-in`` (relocate-builtin-doctrine-packs).
    # No explicit built-in root: the per-kind repositories self-resolve the flattened
    # ``packs/built-in/<kind>`` layout via the WP04 seam (as production does); passing an
    # explicit root would force the retired ``<root>/<kind>/built-in`` layout.
    return CharterOfferingService()


def test_model_task_routing_tactic_reachable_via_drg_traversal() -> None:
    """``tactic:model-task-routing`` must be reachable from an activated
    directive via a ``suggests`` edge in the real shipped graph -- not merely
    present as an unreferenced node."""
    graph = _load_shipped_graph()

    result = resolve_transitive_refs(
        graph,
        start_urns={_ANCHOR_DIRECTIVE_URN},
        relations={Relation.REQUIRES, Relation.SUGGESTS},
    )

    assert "model-task-routing" in result.tactics, (
        "tactic:model-task-routing is not reachable from an activated directive "
        "via a suggests edge in src/charter/offering/graph.yaml -- the charter's "
        "`model_task_routing` reference dangles."
    )


def test_autonomous_operation_protocol_reachable_via_drg_traversal() -> None:
    """FR-007: the pre-existing ``autonomous-operation-protocol`` tactic must
    gain an inbound directive ``suggests`` edge (it is activated but was
    never directive-reachable)."""
    graph = _load_shipped_graph()

    result = resolve_transitive_refs(
        graph,
        start_urns={_ANCHOR_DIRECTIVE_URN},
        relations={Relation.REQUIRES, Relation.SUGGESTS},
    )

    assert "autonomous-operation-protocol" in result.tactics, (
        "tactic:autonomous-operation-protocol has no inbound directive suggests "
        "edge -- it is activated (.kittify/config.yaml) but not "
        "directive-reachable, so it dangles in references.yaml."
    )


def test_charter_references_surface_model_task_routing_body() -> None:
    """The compiled charter references (the source ``charter context`` reads)
    must carry each tactic's real body -- proving resolution flows through
    the DRG + CharterOfferingService, never a hand-written references.yaml row."""
    interview = read_interview_answers(ANSWERS_PATH)
    assert interview is not None, "expected the project's real interview answers to load"

    compiled = compile_charter(
        mission=interview.mission,
        interview=interview,
        repo_root=REPO_ROOT,
        doctrine_service=_real_doctrine_service(),
    )

    by_id = {ref.id: ref for ref in compiled.references}

    tactic_ref = by_id.get("TACTIC:model-task-routing")
    assert tactic_ref is not None, "TACTIC:model-task-routing did not resolve into compiled references"
    assert _MODEL_TASK_ROUTING_PURPOSE_FRAGMENT in tactic_ref.summary.lower(), (
        "resolved reference does not carry the tactic's real purpose body "
        f"(got: {tactic_ref.summary!r})"
    )

    autonomous_ref = by_id.get("TACTIC:autonomous-operation-protocol")
    assert autonomous_ref is not None, (
        "TACTIC:autonomous-operation-protocol did not resolve into compiled references"
    )
    assert _AUTONOMOUS_OPERATION_PURPOSE_FRAGMENT in autonomous_ref.summary.lower(), (
        "resolved reference does not carry the tactic's real purpose body "
        f"(got: {autonomous_ref.summary!r})"
    )


def test_charter_repoints_snake_case_token_to_kebab() -> None:
    """C-002 / FR-006: the charter prose token must be REPOINTED from the
    dangling snake_case ``model_task_routing`` to the kebab tactic id
    ``model-task-routing`` -- no new snake_case artifact is minted, and the
    old token must not linger anywhere in the charter prose."""
    charter_text = CHARTER_PATH.read_text(encoding="utf-8")

    assert "`model-task-routing`" in charter_text, (
        "charter.md must reference the kebab tactic id `model-task-routing`"
    )
    assert "model_task_routing" not in charter_text, (
        "charter.md still contains the dangling snake_case token; repoint it, "
        "do not leave it alongside a new artifact"
    )
