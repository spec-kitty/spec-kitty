"""Tests for ``specify_cli.review.gate_bindings`` — WP06 of mission
``doctrine-controlled-transition-gates-01KY51Z7`` (epic #2535 half A).

Covers T026–T031: the named binding loader, mission-type resolution, the
lane-edge → (mission, action) → contract mapping, and the **pure** activation
⋈ binding join.

The load-bearing contract (post-task squad BLOCKER B1): the join gates on the
**owning review contract's URN** (``mission_step_contract:<mission>/review``),
NOT on the handler name. The handler is a plain ``GATE_REGISTRY`` dict key.
Gating on the handler URN would never match (there is no
``mission_step_contract:.../spec-kitty-pre-review`` node) → a permanently
decorative gate.

NFR-003 non-vacuity is enforced two ways:

* the **positive arm** computes its activated URN set from the *real*
  :func:`charter.activation.drg_activation.filter_graph_by_activation` applied to a *real*
  ``mission_step_contract:software-dev/review`` DRG node — not a fabricated
  frozenset — and the paired negative-control arm deactivates the owning
  mission type so the *same* real filter drops the URN;
* the **mission-type negative control** (MANDATORY, T031.2) resolves a real
  ``research`` mission — whose built-in contracts genuinely lack a ``review``
  action — and asserts the distinguishable ``NO_CONTRACT`` coverage, which
  would flip to a live binding if the loader ever dropped the ``mission``
  param.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from charter.drg import NodeKind
from charter.activation.drg_activation import filter_graph_by_activation
from charter.mission_steps import (
    MissionStepContract,
    MissionStepContractStep,
)
from charter.activation.pack_context import PackContext
from charter.offering.drg.models import DRGGraph, DRGNode
from charter.offering.missions.step_contracts import GateBinding
from specify_cli.mission_step_contracts.executor import StepContractExecutor
from specify_cli.review import gate_bindings
from specify_cli.review.gate_bindings import (
    GateCoverage,
    load_gate_bindings,
    resolve_active_gate_bindings,
    resolve_gate_bindings_for_transition,
    resolve_mission_type,
)
from tests.specify_cli.mission_step_contracts.test_executor import (
    ORG_FIXTURE_ACTION,
    ORG_FIXTURE_GATE_EDGE,
    ORG_FIXTURE_MISSION,
    write_org_pack_config,
    write_org_tier_step_contract_fixture,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

pytestmark = [pytest.mark.fast]

_EDGE = "in_progress->for_review"
_HANDLER = "spec-kitty-pre-review"
_SOFTWARE_DEV = "software-dev"
_REVIEW = "review"
_OWNING_URN = "mission_step_contract:software-dev/review"


# ---------------------------------------------------------------------------
# Fixtures / builders
# ---------------------------------------------------------------------------


def _binding(on_transition: str = _EDGE, handler: str = _HANDLER) -> GateBinding:
    return GateBinding(
        on_transition=on_transition,
        handler=handler,
        handler_kind="mission_step_contract",
        schema_version="1.0",
    )


def _graph_with_review_node() -> DRGGraph:
    """A minimal but *real* DRG carrying the owning review-contract node."""
    return DRGGraph(
        schema_version="1.0",
        generated_at="2026-01-01T00:00:00Z",
        generated_by="test",
        nodes=[
            DRGNode(urn=_OWNING_URN, kind=NodeKind.MISSION_STEP_CONTRACT),
            DRGNode(urn="mission_type:software-dev", kind=NodeKind.MISSION_TYPE),
        ],
        edges=[],
    )


def _pack(mission_types: Iterable[str], repo_root: Path) -> PackContext:
    return PackContext(
        activated_kinds=frozenset({"mission_step_contracts", "mission_types"}),
        activated_mission_types=frozenset(mission_types),
        pack_roots=(repo_root,),
        org_pack_names=(),
        repo_root=repo_root,
    )


def _real_activated_urns(mission_types: Iterable[str], repo_root: Path) -> frozenset[str]:
    """Compute the activated ``mission_step_contract`` URN set via the *real*
    activation filter — this is what makes the positive arm non-vacuous."""
    filtered = filter_graph_by_activation(_graph_with_review_node(), _pack(mission_types, repo_root))
    return frozenset(n.urn for n in filtered.nodes if n.kind == NodeKind.MISSION_STEP_CONTRACT)


class _SpySnapshot:
    def __init__(self, mission_slug: str, mission_type: str | None) -> None:
        self.mission_slug = mission_slug
        self.mission_type = mission_type


class _SpyRepository:
    """Repository stand-in counting ``get_by_action`` calls (NFR-005)."""

    def __init__(self, contract: MissionStepContract | None) -> None:
        self._contract = contract
        self.calls: list[tuple[str, str]] = []

    def get_by_action(self, mission: str, action: str) -> MissionStepContract | None:
        self.calls.append((mission, action))
        if self._contract is None:
            return None
        if self._contract.mission == mission and self._contract.action == action:
            return self._contract
        return None


def _contract(gates: list[GateBinding], *, mission: str = _SOFTWARE_DEV) -> MissionStepContract:
    return MissionStepContract(
        schema_version="1.0",
        id="review",
        action=_REVIEW,
        mission=mission,
        steps=[MissionStepContractStep(id="s1", description="d")],
        gates=gates,
    )


# ---------------------------------------------------------------------------
# T026 — load_gate_bindings (mission param mandatory)
# ---------------------------------------------------------------------------


def test_load_gate_bindings_software_dev_review_returns_binding(tmp_path: Path) -> None:
    bindings = load_gate_bindings(tmp_path, _SOFTWARE_DEV, _REVIEW)
    assert bindings, "built-in software-dev review contract must ship a gate binding"
    assert any(b.on_transition == _EDGE and b.handler == _HANDLER for b in bindings)


def test_load_gate_bindings_research_review_is_empty(tmp_path: Path) -> None:
    # research ships no review action contract -> empty (mission param is load-bearing).
    assert load_gate_bindings(tmp_path, "research", _REVIEW) == []


def test_load_gate_bindings_requires_mission_param() -> None:
    # The mission param has no default: a mission-blind call is a TypeError.
    with pytest.raises(TypeError):
        load_gate_bindings(Path("."), _REVIEW)  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# T028 — resolve_active_gate_bindings (PURE) — non-vacuous positive + negative
# ---------------------------------------------------------------------------


def test_resolve_active_positive_uses_real_activated_urn(tmp_path: Path) -> None:
    activated = _real_activated_urns([_SOFTWARE_DEV], tmp_path)
    assert _OWNING_URN in activated, "positive arm must use a REAL activated contract URN"
    active = resolve_active_gate_bindings(activated, [_binding()], _EDGE, _OWNING_URN)
    assert [b.handler for b in active] == [_HANDLER]


def test_resolve_active_negative_control_deactivated(tmp_path: Path) -> None:
    # Same real graph, owning mission type deactivated -> real filter drops the URN.
    activated = _real_activated_urns(["research"], tmp_path)
    assert _OWNING_URN not in activated
    active = resolve_active_gate_bindings(activated, [_binding()], _EDGE, _OWNING_URN)
    assert active == []


def test_resolve_active_edge_mismatch_returns_empty() -> None:
    active = resolve_active_gate_bindings(
        frozenset({_OWNING_URN}), [_binding(on_transition="for_review->in_review")], _EDGE, _OWNING_URN
    )
    assert active == []


def test_resolve_active_is_stable_declaration_order() -> None:
    b0 = _binding(handler="zeta-handler")
    b1 = _binding(handler="alpha-handler")
    active = resolve_active_gate_bindings(frozenset({_OWNING_URN}), [b0, b1], _EDGE, _OWNING_URN)
    # declaration index dominates the (index, handler) sort key -> input order preserved.
    assert [b.handler for b in active] == ["zeta-handler", "alpha-handler"]


def test_resolve_active_empty_activated_set_is_vacuous_and_rejected() -> None:
    # Documents the NFR-003 trap: against an empty activated set the join is empty.
    # The positive arm above therefore MUST supply a genuinely-populated set.
    assert resolve_active_gate_bindings(frozenset(), [_binding()], _EDGE, _OWNING_URN) == []


# ---------------------------------------------------------------------------
# T027 — mission-type resolution (never hardcoded software-dev)
# ---------------------------------------------------------------------------


def test_resolve_mission_type_prefers_populated_snapshot() -> None:
    assert resolve_mission_type(_SpySnapshot("034-x", "research")) == "research"


def test_resolve_mission_type_reads_meta_json_when_snapshot_blank(tmp_path: Path) -> None:
    (tmp_path / "meta.json").write_text(
        json.dumps(
            {
                "slug": "034-x",
                "mission_slug": "034-x",
                "friendly_name": "x",
                "mission_type": "documentation",
                "target_branch": "main",
                "created_at": "2026-01-01T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    resolved = resolve_mission_type(_SpySnapshot("034-x", None), feature_dir=tmp_path)
    assert resolved == "documentation"


# ---------------------------------------------------------------------------
# T029 — three distinguishable coverage outcomes
# ---------------------------------------------------------------------------


def test_resolver_active_positive(tmp_path: Path) -> None:
    result = resolve_gate_bindings_for_transition(
        tmp_path,
        _SOFTWARE_DEV,
        _EDGE,
        repository=_SpyRepository(_contract([_binding()])),
        graph_loader=lambda _root: _graph_with_review_node(),
        pack_resolver=lambda root: _pack([_SOFTWARE_DEV], root),
    )
    assert result.coverage is GateCoverage.ACTIVE
    assert [b.handler for b in result.active] == [_HANDLER]


def test_resolver_not_activated_is_distinct_from_no_coverage(tmp_path: Path) -> None:
    result = resolve_gate_bindings_for_transition(
        tmp_path,
        _SOFTWARE_DEV,
        _EDGE,
        repository=_SpyRepository(_contract([_binding()])),
        graph_loader=lambda _root: _graph_with_review_node(),
        pack_resolver=lambda root: _pack(["research"], root),  # owning type off
    )
    assert result.coverage is GateCoverage.NOT_ACTIVATED
    assert result.active == ()
    assert "NO_COVERAGE" not in result.reason  # distinct from the no-coverage warns


def test_resolver_no_contract_non_software_dev_negative_control(tmp_path: Path) -> None:
    # MANDATORY R-F1 guard: a REAL research mission has no review contract.
    result = resolve_gate_bindings_for_transition(tmp_path, "research", _EDGE)
    assert result.coverage is GateCoverage.NO_CONTRACT
    assert "NO_COVERAGE" in result.reason
    assert "research" in result.reason
    assert result.active == ()


def test_resolver_no_binding_when_contract_lacks_edge(tmp_path: Path) -> None:
    result = resolve_gate_bindings_for_transition(
        tmp_path,
        _SOFTWARE_DEV,
        _EDGE,
        repository=_SpyRepository(_contract([_binding(on_transition="for_review->in_review")])),
    )
    assert result.coverage is GateCoverage.NO_BINDING
    assert "NO_COVERAGE" in result.reason


def test_three_no_coverage_reasons_are_pairwise_distinct(tmp_path: Path) -> None:
    no_contract = resolve_gate_bindings_for_transition(tmp_path, "research", _EDGE)
    no_binding = resolve_gate_bindings_for_transition(
        tmp_path,
        _SOFTWARE_DEV,
        _EDGE,
        repository=_SpyRepository(_contract([_binding(on_transition="for_review->in_review")])),
    )
    not_activated = resolve_gate_bindings_for_transition(
        tmp_path,
        _SOFTWARE_DEV,
        _EDGE,
        repository=_SpyRepository(_contract([_binding()])),
        graph_loader=lambda _root: _graph_with_review_node(),
        pack_resolver=lambda root: _pack(["research"], root),
    )
    reasons = {no_contract.reason, no_binding.reason, not_activated.reason}
    assert len(reasons) == 3, f"reasons must be pairwise distinct, got {reasons}"


# ---------------------------------------------------------------------------
# T030 — bounded loads (one graph load + one binding load per transition)
# ---------------------------------------------------------------------------


def test_bounded_loads_single_graph_and_binding_load(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    graph_calls = {"n": 0}
    filter_calls = {"n": 0}

    def _spy_graph(
        _root: Path,
        *,
        org_roots: list[Path] | None = None,
        org_fragments: object = None,
    ) -> DRGGraph:
        # #3525 Fold B: the module-level default path now calls
        # ``load_validated_graph(repo_root, org_roots=...)`` -- this spy
        # patches that same module-level name, so it must accept (and can
        # ignore) the keyword its production caller now always passes.
        # DRG read-path bridge (WP02): that default also threads
        # ``org_fragments=load_org_drg(repo_root, strict=False)``, so the spy
        # accepts (and ignores) that keyword too.
        graph_calls["n"] += 1
        return _graph_with_review_node()

    def _spy_filter(graph: DRGGraph, _pack: PackContext) -> DRGGraph:
        filter_calls["n"] += 1
        return graph

    monkeypatch.setattr(gate_bindings, "load_validated_graph", _spy_graph)
    monkeypatch.setattr(gate_bindings, "filter_graph_by_activation", _spy_filter)

    repo = _SpyRepository(_contract([_binding()]))
    result = resolve_gate_bindings_for_transition(
        tmp_path,
        _SOFTWARE_DEV,
        _EDGE,
        repository=repo,
        pack_resolver=lambda root: _pack([_SOFTWARE_DEV], root),
    )

    assert result.coverage is GateCoverage.ACTIVE
    assert graph_calls["n"] == 1, "graph must load exactly once per transition"
    assert filter_calls["n"] == 1, "activation filter must run exactly once per transition"
    assert repo.calls == [(_SOFTWARE_DEV, _REVIEW)], "contract must load exactly once"


# ---------------------------------------------------------------------------
# T010 (WP02, mission #3516) — FR-005: org-tier gates via the SAME shared
# fixture T008 built in tests/specify_cli/mission_step_contracts/test_executor.py
# (SC-003: one synthetic org-pack fixture, exercised by three separate test
# functions — this is the gate-bindings third).
# ---------------------------------------------------------------------------


def test_load_gate_bindings_resolves_org_only_step_contract_gates(tmp_path: Path) -> None:
    """FR-005 (User Story 3): an org-tier step contract's ``gates:`` block
    fires with no project-tier duplicate present.

    Red-first: on the pre-fix commit, ``_build_repository`` constructs a
    project-dir-only repository, so ``load_gate_bindings`` returns ``[]``
    for this org-only contract instead of its declared gate.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    org_root = tmp_path / "org-pack"
    write_org_tier_step_contract_fixture(org_root)
    write_org_pack_config(repo_root, org_root)

    bindings = load_gate_bindings(repo_root, ORG_FIXTURE_MISSION, ORG_FIXTURE_ACTION)

    assert bindings, "org-tier contract's gates: block must resolve with no project-tier duplicate"
    assert any(b.on_transition == ORG_FIXTURE_GATE_EDGE for b in bindings)


def test_build_repository_and_executor_resolve_identical_org_dirs(tmp_path: Path) -> None:
    """User Story 3 Acceptance Scenario 2 / lockstep proof: ``_build_repository``
    (site 3) and ``StepContractExecutor.__init__`` (site 6) resolve ``org_dirs``
    via the identical ``resolve_org_dirs`` call -- regression-tested so the two
    construction sites cannot silently drift apart again (the exact failure
    class this WP's mandatory lockstep constraint exists to close).
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    org_root = tmp_path / "org-pack"
    write_org_tier_step_contract_fixture(org_root)
    write_org_pack_config(repo_root, org_root)

    gate_bindings_repo = gate_bindings._build_repository(repo_root)
    executor_repo = StepContractExecutor(repo_root=repo_root)._contracts

    assert gate_bindings_repo._org_dirs == executor_repo._org_dirs
    assert gate_bindings_repo._org_dirs != []
