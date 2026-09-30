"""Binding loader + activation ⋈ binding join (WP06, mission
``doctrine-controlled-transition-gates-01KY51Z7``, epic #2535 half A).

Delivers **FR-007** (the explicit binding-resolution join + named loader),
**FR-008** (lane-edge → ``(mission, action)`` → contract ownership + the
mission-type axis), **NFR-003** (non-vacuous resolution) and **NFR-005**
(bounded loads).

The load-bearing correctness fix (post-task squad BLOCKER B1): the DRG carries
**no** binding payload (:class:`charter.offering.drg.models.DRGNode` holds only
``urn/kind/label/provenance/tags``), so bindings are loaded separately (off the
runtime-wired ``mission_step_contract`` model) and **joined** against the
activated-URN set. The join gates on the **owning review contract's URN**
(``mission_step_contract:<mission>/review``) — *not* on the handler name. The
handler is a plain :data:`~specify_cli.review.gate_registry.GATE_REGISTRY` dict
key, resolved at dispatch by
:func:`~specify_cli.review.gate_registry.get_gate_handler`; it is never matched
against a DRG URN. Gating on the handler URN would never match (there is no
``mission_step_contract:.../spec-kitty-pre-review`` node) → a permanently
decorative gate.

Layering: :func:`resolve_active_gate_bindings` is a **pure** function (inputs
in, list out, no I/O). The impure orchestration — mission-type resolution,
contract load, one graph load + one activation filter — lives in
:func:`resolve_gate_bindings_for_transition`, which mirrors the executor's
activation pattern (``mission_step_contracts/executor.py:179-183``) and copies
its **fail-closed** ``PackContext`` discipline (``executor.py:275``). WP09 wires
this resolver into the live transition hook; WP08 owns verdict aggregation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from charter.activation._drg_helpers import load_validated_graph
from charter.drg import (
    NodeKind,
    OrgPackEnvVarUnsetError,
    OrgPackSubdirEscapeError,
    resolve_existing_org_roots,
    resolve_org_dirs,
)
from charter.activation.drg_activation import filter_graph_by_activation, load_org_drg
from charter.mission_steps import MissionStepContract, MissionStepContractRepository
from specify_cli.mission_metadata import resolve_mission_identity

if TYPE_CHECKING:
    from collections.abc import Callable

    from charter.activation.pack_context import PackContext
    from charter.drg import DRGGraph
    from charter.mission_steps import GateBinding

# Only names consumed cross-module (the transition-gate hook) are exported; the
# resolution primitives (``resolve_active_gate_bindings``,
# ``owning_contract_urn``, ``OWNING_ACTION_FOR_EDGE``, ``GateCoverage``) stay
# module-internal — they are composed by ``resolve_gate_bindings_for_transition``
# and exercised directly by unit tests, which do not need ``__all__`` membership.
__all__ = [
    "GateBindingResolution",
    "resolve_gate_bindings_for_transition",
    "resolve_mission_type",
]

# --- constants (Sonar S1192: hoisted repeated literals) --------------------
_REVIEW_ACTION = "review"
_IN_PROGRESS_TO_FOR_REVIEW = "in_progress->for_review"
_FOR_REVIEW_TO_IN_REVIEW = "for_review->in_review"
_IN_REVIEW_TO_APPROVED = "in_review->approved"
_MSC_URN_PREFIX = "mission_step_contract"
_PROJECT_CONTRACTS_SUBPATH = (".kittify", "doctrine", "mission_step_contracts")
_NO_COVERAGE = "NO_COVERAGE"

# Lane-edge → owning action (FR-008, data-model.md §6). Half A gates **only**
# ``in_progress->for_review`` (C-006); the other two edges are schema-admitted
# but not required to gate, and map to the same ``review`` action.
OWNING_ACTION_FOR_EDGE: dict[str, str] = {
    _IN_PROGRESS_TO_FOR_REVIEW: _REVIEW_ACTION,
    _FOR_REVIEW_TO_IN_REVIEW: _REVIEW_ACTION,
    _IN_REVIEW_TO_APPROVED: _REVIEW_ACTION,
}


class GateCoverage(StrEnum):
    """The four distinguishable resolution outcomes for one transition edge.

    ``ACTIVE`` and ``NOT_ACTIVATED`` presuppose a matching binding exists; the
    two ``NO_*`` outcomes are the mission-type-axis coupling guard (FR-008,
    FR-012) — each is a **separately-worded** ``NO_COVERAGE`` warn, never a
    silent skip. ``NOT_ACTIVATED`` is the *handler-not-activated* advisory and
    is deliberately worded WITHOUT the ``NO_COVERAGE`` marker so an operator
    (and the tests) can tell it apart from a missing contract / binding.
    """

    ACTIVE = "active"
    NO_CONTRACT = "no_contract"
    NO_BINDING = "no_binding"
    NOT_ACTIVATED = "not_activated"


@dataclass(frozen=True)
class GateBindingResolution:
    """Outcome of resolving the active gate bindings for one lane edge."""

    coverage: GateCoverage
    edge_key: str
    owning_contract_urn: str
    reason: str
    active: tuple[GateBinding, ...] = field(default_factory=tuple)


class _ContractSource(Protocol):
    """Minimal repository surface the loader needs (eases test injection)."""

    def get_by_action(self, mission: str, action: str) -> MissionStepContract | None: ...


# ---------------------------------------------------------------------------
# T027 — mission-type resolution + owning-URN construction
# ---------------------------------------------------------------------------


def resolve_mission_type(snapshot: object, *, feature_dir: Path | None = None) -> str:
    """Resolve the mission type from identity — never hardcoded (FR-008).

    Prefers a populated ``mission_type`` on the WP-lane ``snapshot`` (the
    ``WPStateSnapshot.mission_type`` boundary field); when that is absent it
    reads the mission's ``meta.json`` via
    :func:`specify_cli.mission_metadata.resolve_mission_identity`. A blank
    snapshot with no ``feature_dir`` is a programming error, not a silent
    fallback to ``software-dev``.
    """
    populated = getattr(snapshot, "mission_type", None)
    if isinstance(populated, str) and populated.strip():
        return populated.strip()
    if feature_dir is not None:
        return str(resolve_mission_identity(feature_dir).mission_type)
    raise ValueError(
        "cannot resolve mission type: snapshot carries no mission_type and no "
        "feature_dir was supplied to read meta.json"
    )


def owning_contract_urn(mission: str, action: str) -> str:
    """Canonical owning-contract URN ``mission_step_contract:<mission>/<action>``.

    This is the URN of the contract ``get_by_action(mission, action)`` locates
    (``drg.py:271`` canonical form). Its membership in the activated
    ``mission_step_contract`` URN set is what gates whether the contract's
    bindings fire — the handler name never participates in this join.
    """
    return f"{_MSC_URN_PREFIX}:{mission}/{action}"


# ---------------------------------------------------------------------------
# T026 — the named binding loader (mission param mandatory)
# ---------------------------------------------------------------------------


def _build_repository(repo_root: Path) -> MissionStepContractRepository:
    """Construct the contract repository the way the executor does.

    FR-005: mirrors ``StepContractExecutor.__init__``
    (``mission_step_contracts/executor.py``) exactly — same
    ``resolve_org_dirs(repo_root, "mission_step_contracts")`` call, same
    ``subdir`` string — so an org-tier contract's ``gates:`` block fires at
    WP review-transition time instead of resolving delegations correctly
    while never gating anything (User Story 3).
    """
    return MissionStepContractRepository(
        project_dir=repo_root.joinpath(*_PROJECT_CONTRACTS_SUBPATH),
        org_dirs=resolve_org_dirs(repo_root, "mission_step_contracts"),
    )


def _load_review_contract(
    repo_root: Path,
    mission: str,
    action: str,
    *,
    repository: _ContractSource | None = None,
) -> MissionStepContract | None:
    repo = repository or _build_repository(repo_root)
    return repo.get_by_action(mission, action)


# ---------------------------------------------------------------------------
# T028 — the PURE join (activated-URN ⋈ bindings)
# ---------------------------------------------------------------------------


def resolve_active_gate_bindings(
    activated_msc_urns: frozenset[str],
    bindings: list[GateBinding],
    edge_key: str,
    owning_contract_urn: str,
) -> list[GateBinding]:
    """PURE join: which bindings are active for ``edge_key`` (FR-007, NFR-003).

    Retains a binding iff ``b.on_transition == edge_key`` **and**
    ``owning_contract_urn in activated_msc_urns``. The activation gate is the
    **owning contract's URN**, never the handler: ``b.handler`` is resolved
    separately by a plain ``GATE_REGISTRY`` dict lookup at dispatch (WP04/WP09).

    Survivors are returned in a **stable** order keyed on
    ``(declaration_index, handler)`` (FR-008 precedence). Because the
    declaration index is unique per binding it dominates the sort, so the
    original authoring order is preserved; the handler tiebreak documents intent
    and never actually fires. When more than one binding matches, **all** fire
    (no last-wins).

    No I/O — the caller supplies ``activated_msc_urns`` (computed once from the
    real activation filter) so this function stays trivially testable and
    ≤ 15 complexity. Against an **empty** activated set the result is empty;
    NFR-003 therefore requires the positive test arm to pass a genuinely
    populated set (see the module tests).
    """
    if owning_contract_urn not in activated_msc_urns:
        return []
    matched = [
        (index, binding)
        for index, binding in enumerate(bindings)
        if binding.on_transition == edge_key
    ]
    matched.sort(key=lambda pair: (pair[0], pair[1].handler))
    return [binding for _index, binding in matched]


# ---------------------------------------------------------------------------
# activation set (mirrors executor.py:179-183) + fail-closed pack context
# ---------------------------------------------------------------------------


def _resolve_pack_context(repo_root: Path) -> PackContext | None:
    """Construct a ``PackContext`` for activation filtering — fail-CLOSED.

    Mirrors ``executor.py:275``: an unset org-pack env var or a symlink-escape
    is operator-actionable, so it propagates rather than silently degrading to
    an unfiltered graph; any other error leaves the filter optional (``None``).
    """
    from charter.activation.pack_context import PackContext  # noqa: PLC0415 — mirrors executor

    try:
        return PackContext.from_config(repo_root)
    except (OrgPackEnvVarUnsetError, OrgPackSubdirEscapeError):
        raise
    except Exception:  # noqa: BLE001 — defensive; activation filter is optional
        return None


def _activated_msc_urns(
    repo_root: Path,
    *,
    graph_loader: Callable[[Path], DRGGraph] | None,
    pack_resolver: Callable[[Path], PackContext | None] | None,
) -> frozenset[str]:
    """One graph load + one activation filter → surviving contract URNs (NFR-005).

    #3525 Fold B: the production default (no *graph_loader* override) now
    threads the full declaration-ordered org-pack chain into
    ``load_validated_graph`` — previously this call carried NO org roots at
    all (inert even for a single configured pack), so org-tier
    ``mission_step_contract`` nodes never participated in gate-binding
    activation. An explicit *graph_loader* override (test doubles) is called
    exactly as before — single ``repo_root`` argument, no org-roots
    threading — so existing overrides are unaffected.

    DRG read-path bridge (mission ``drg-read-path-bridge-01M0CHVZ``, WP02): the
    production default additionally threads ``org_fragments=load_org_drg(
    repo_root, strict=False)`` so a ``mission_step_contract`` node (and its
    ``requires``/``suggests`` edges) authored only in an org pack's
    ``drg/fragment.yaml`` is visible to gate-binding activation too — mirroring
    the ``activate``/``deactivate`` cascade call sites (D4). ``strict=False``
    keeps the diagnostic ``load_org_drg`` default untouched (NFR-001); the
    no-org-pack path is unchanged (``load_org_drg`` returns ``[]``).
    """
    graph = (
        graph_loader(repo_root)
        if graph_loader is not None
        else load_validated_graph(
            repo_root,
            org_roots=resolve_existing_org_roots(repo_root),
            org_fragments=load_org_drg(repo_root, strict=False),
        )
    )
    pack = (pack_resolver or _resolve_pack_context)(repo_root)
    if pack is not None:
        graph = filter_graph_by_activation(graph, pack)
    return frozenset(n.urn for n in graph.nodes if n.kind == NodeKind.MISSION_STEP_CONTRACT)


# ---------------------------------------------------------------------------
# T029 / T030 — the bounded, distinguishable resolver
# ---------------------------------------------------------------------------


def _no_contract(mission: str, action: str, edge_key: str, urn: str) -> GateBindingResolution:
    return GateBindingResolution(
        coverage=GateCoverage.NO_CONTRACT,
        edge_key=edge_key,
        owning_contract_urn=urn,
        reason=f"{_NO_COVERAGE}: no gate contract for ({mission}, {action}) governing edge {edge_key}",
    )


def _no_binding(mission: str, action: str, edge_key: str, urn: str) -> GateBindingResolution:
    return GateBindingResolution(
        coverage=GateCoverage.NO_BINDING,
        edge_key=edge_key,
        owning_contract_urn=urn,
        reason=(
            f"{_NO_COVERAGE}: gate contract ({mission}, {action}) declares "
            f"no binding for edge {edge_key}"
        ),
    )


def _not_activated(edge_key: str, urn: str) -> GateBindingResolution:
    return GateBindingResolution(
        coverage=GateCoverage.NOT_ACTIVATED,
        edge_key=edge_key,
        owning_contract_urn=urn,
        reason=(
            f"gate binding present for edge {edge_key} but owning contract "
            f"{urn} is not activated"
        ),
    )


def _active(active: list[GateBinding], edge_key: str, urn: str) -> GateBindingResolution:
    return GateBindingResolution(
        coverage=GateCoverage.ACTIVE,
        edge_key=edge_key,
        owning_contract_urn=urn,
        reason=f"{len(active)} active gate binding(s) for edge {edge_key} on {urn}",
        active=tuple(active),
    )


def resolve_gate_bindings_for_transition(
    repo_root: Path,
    mission: str,
    edge_key: str,
    *,
    repository: _ContractSource | None = None,
    graph_loader: Callable[[Path], DRGGraph] | None = None,
    pack_resolver: Callable[[Path], PackContext | None] | None = None,
) -> GateBindingResolution:
    """Resolve the active gate bindings for one lane transition (FR-007/008).

    Bounded (NFR-005): at most one contract load, one graph load, one activation
    filter per transition — the graph is loaded only when a matching binding
    actually exists to gate. Returns one of four **distinguishable** outcomes
    (:class:`GateCoverage`); the two ``NO_COVERAGE`` outcomes and the
    ``NOT_ACTIVATED`` advisory are pairwise-distinct, separately-worded reasons,
    never a silent skip.
    """
    action = OWNING_ACTION_FOR_EDGE.get(edge_key, _REVIEW_ACTION)
    urn = owning_contract_urn(mission, action)

    contract = _load_review_contract(repo_root, mission, action, repository=repository)
    if contract is None:
        return _no_contract(mission, action, edge_key, urn)

    bindings = list(contract.gates)
    if not any(b.on_transition == edge_key for b in bindings):
        return _no_binding(mission, action, edge_key, urn)

    activated = _activated_msc_urns(repo_root, graph_loader=graph_loader, pack_resolver=pack_resolver)
    active = resolve_active_gate_bindings(activated, bindings, edge_key, urn)
    if active:
        return _active(active, edge_key, urn)
    return _not_activated(edge_key, urn)
