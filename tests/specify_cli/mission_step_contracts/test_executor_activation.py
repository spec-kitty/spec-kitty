"""T009 (WP03, mission ``drg-relation-parity-activation-gate-01KY48PD``, #2843).

Five-consumer regression net (NFR-002): ``mission_step_contracts/executor.py:182``
before/after the WP01-corrected activation gate
(``contracts/activation-gate-contract.md``, "Consumer observables").

**Named observable**: the resolved step delegation for a step whose
``delegates_to`` candidate is a directive -- ``resolved_delegations`` /
``unresolved_candidates`` on the executed step. This is driven directly by
``action_context.artifact_urns``, the set ``resolve_context`` computes over
the graph *already filtered* by ``filter_graph_by_activation`` at
executor.py:182-184 (``_resolve_step_delegations`` checks
``urn not in selected_urns`` -- ``executor.py:373``). A directive node the
gate drops never reaches ``artifact_urns``, so its delegation candidate is
unresolved; a directive the gate retains resolves to its canonical URN.

Real corpus stem/canonical pair reused from WP01's characterization test
(``tests/charter/test_drg_activation_gate.py``): the config stem
``001-architectural-integrity-standard`` resolves (via
``charter.activation.kind_vocabulary.resolve_artifact_urn``) to the canonical
``directive:DIRECTIVE_001``.

RED-on-merge-base reasoning (NFR-002 attribution, no dual-branch runtime
check needed -- WP01 already proved this at the gate level): on merge-base,
``_node_is_activated`` Step 3 (``drg.py:404-428`` pre-WP01) compared the
node's bare canonical id (``"DIRECTIVE_001"``) directly against the raw
config stem (``"001-architectural-integrity-standard"``); they never match,
so ANY populated ``activated_directives`` silently dropped every directive
node, including ``DIRECTIVE_001``. With the node dropped, the executor's
``action_context.artifact_urns`` would not contain
``directive:DIRECTIVE_001``, ``_directive_candidate_urn("001-architectural-
integrity-standard")`` (leading-numeric extraction, executor.py:344-351)
still resolves to ``directive:DIRECTIVE_001``, but the membership check
against ``selected_urns`` (executor.py:373) fails -- the candidate would be
``unresolved`` there, not resolved. After WP01 the stem resolves to its
canonical URN and the per-ID gate keeps the node, so ``artifact_urns``
contains it and the delegation resolves -- the assertion below is
discriminating.

Fixtures are built inline (real ``PackContext`` instances patched onto
``PackContext.from_config``, mirroring the existing
``test_resolve_pack_context_propagates_org_pack_env_var_unset_error``
pattern in ``test_executor.py``); no shared ``conftest.py`` addition per the
WP's instruction (owned by sibling WP01/WP02 lanes).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from ruamel.yaml import YAML

from charter.activation.pack_context import PackContext
from charter.offering.missions.step_contracts import MissionStepContractRepository
from specify_cli.mission_step_contracts.executor import (
    StepContractExecutionContext,
    StepContractExecutionResult,
    StepContractExecutor,
)
from tests.specify_cli.mission_step_contracts.test_executor import (
    ORG_FIXTURE_ACTION,
    ORG_FIXTURE_DIRECTIVE_STEM,
    ORG_FIXTURE_DIRECTIVE_URN,
    ORG_FIXTURE_MISSION,
    ORG_FIXTURE_PACK_NAME,
    write_org_pack_config,
    write_org_tier_step_contract_fixture,
)

pytestmark = pytest.mark.fast

# Real built-in stem/canonical pair (verified on disk -- NFR-001 requires the
# real corpus shape, not a hermetic id==stem fixture).
_REAL_DIRECTIVE_STEM = "001-architectural-integrity-standard"
_REAL_DIRECTIVE_CANONICAL_URN = "directive:DIRECTIVE_001"


class _FakeInvocationExecutor:
    """Stub matching the ``ProfileInvocationExecutor`` protocol used elsewhere
    in ``test_executor.py`` -- avoids exercising the real invocation/writer
    stack, which is orthogonal to the activation-gate consumer behavior under
    test here."""

    def invoke(self, _request_text: str, **_kwargs: object) -> object:
        return SimpleNamespace(invocation_id="inv-activation-1")

    def complete_invocation(self, _invocation_id: str, *, outcome: str, closed_by: str) -> None:
        assert outcome == "done"
        assert closed_by == "agent"


def _write_yaml(path: Path, data: dict[str, object]) -> None:
    yaml = YAML()
    yaml.default_flow_style = False
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        yaml.dump(data, fh)


def _write_directive_composer_graph(repo_root: Path) -> None:
    """Project-layer DRG: an action scoped directly to ``DIRECTIVE_001``.

    ``DIRECTIVE_001`` here is declared with its real canonical URN so the
    activation gate's stem->canonical resolution (which reads the real
    doctrine corpus on disk, independent of which graph the node lives in)
    recognizes it.
    """
    _write_yaml(
        repo_root / ".kittify" / "charter-packs" / "graph.yaml",
        {
            "schema_version": "1.0",
            "generated_at": "2026-07-22T00:00:00Z",
            "generated_by": "test",
            "nodes": [
                {
                    "urn": "action:fixture/directive-composer",
                    "kind": "action",
                    "label": "Fixture directive composer action",
                },
                {
                    "urn": _REAL_DIRECTIVE_CANONICAL_URN,
                    "kind": "directive",
                    "label": "Architectural Integrity Standard",
                },
            ],
            "edges": [
                {
                    "source": "action:fixture/directive-composer",
                    "target": _REAL_DIRECTIVE_CANONICAL_URN,
                    "relation": "scope",
                },
            ],
        },
    )


def _write_directive_contract(built_in_dir: Path) -> None:
    _write_yaml(
        built_in_dir / "directive-activation.step-contract.yaml",
        {
            "schema_version": "1.0",
            "id": "directive-activation-contract",
            "mission": "fixture",
            "action": "directive-composer",
            "steps": [
                {
                    "id": "quality_gate",
                    "description": "Run the activated quality-gate directive",
                    "delegates_to": {
                        "kind": "directive",
                        "candidates": [_REAL_DIRECTIVE_STEM],
                    },
                }
            ],
        },
    )


def _pack_context(*, activated_directives: frozenset[str] | None, repo_root: Path) -> PackContext:
    return PackContext(
        activated_kinds=frozenset({"directives"}),
        activated_mission_types=frozenset(),
        pack_roots=(),
        org_pack_names=(),
        repo_root=repo_root,
        activated_directives=activated_directives,
    )


def _run_directive_composer(
    repo_root: Path,
    contract_repo: MissionStepContractRepository,
    *,
    pack_context: PackContext | None,
) -> StepContractExecutionResult:
    with patch("charter.activation.pack_context.PackContext.from_config", return_value=pack_context):
        return StepContractExecutor(
            repo_root=repo_root,
            contract_repository=contract_repo,
            invocation_executor=_FakeInvocationExecutor(),
        ).execute(
            StepContractExecutionContext(
                repo_root=repo_root,
                mission="fixture",
                action="directive-composer",
                actor="pytest",
                profile_hint="implementer-fixture",
            )
        )


def _setup(tmp_path: Path) -> tuple[Path, MissionStepContractRepository]:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_directive_composer_graph(repo_root)
    built_in_dir = tmp_path / "contracts"
    _write_directive_contract(built_in_dir)
    return repo_root, MissionStepContractRepository(built_in_dir=built_in_dir)


# ---------------------------------------------------------------------------
# T009 -- populated-path: RED on merge-base, GREEN after WP01
# ---------------------------------------------------------------------------


def test_populated_activation_stem_resolves_directive_delegation(tmp_path: Path) -> None:
    """The corrected gate keeps ``DIRECTIVE_001`` reachable, so the step's
    directive delegation candidate (a config stem) resolves to its canonical
    URN -- the named observable proving the WP01 fix reaches this consumer."""
    repo_root, contract_repo = _setup(tmp_path)
    ctx = _pack_context(
        activated_directives=frozenset({_REAL_DIRECTIVE_STEM}), repo_root=repo_root
    )

    result = _run_directive_composer(repo_root, contract_repo, pack_context=ctx)

    step = result.steps[0]
    assert [d.urn for d in step.resolved_delegations] == [_REAL_DIRECTIVE_CANONICAL_URN]
    assert step.unresolved_candidates == ()


# ---------------------------------------------------------------------------
# T009 -- None-path: structural identity, not a merge-base literal
# ---------------------------------------------------------------------------


def test_none_activation_matches_no_filter_at_all(tmp_path: Path) -> None:
    """``activated_directives=None`` (default-allow) must produce the exact
    same delegation outcome as skipping the activation filter entirely
    (``pack_context=None``, the executor's own backward-compatible branch at
    ``executor.py:181-182``). This is a structural-identity check -- both
    runs execute live in this test, no merge-base literal is hand-typed."""
    repo_root, contract_repo = _setup(tmp_path)

    none_per_kind_ctx = _pack_context(activated_directives=None, repo_root=repo_root)
    with_default_allow_pack_context = _run_directive_composer(
        repo_root, contract_repo, pack_context=none_per_kind_ctx
    )

    with patch("charter.activation.pack_context.PackContext.from_config", return_value=None):
        no_pack_context_at_all = StepContractExecutor(
            repo_root=repo_root,
            contract_repository=contract_repo,
            invocation_executor=_FakeInvocationExecutor(),
        ).execute(
            StepContractExecutionContext(
                repo_root=repo_root,
                mission="fixture",
                action="directive-composer",
                actor="pytest",
                profile_hint="implementer-fixture",
            )
        )

    resolved_a = [d.urn for d in with_default_allow_pack_context.steps[0].resolved_delegations]
    resolved_b = [d.urn for d in no_pack_context_at_all.steps[0].resolved_delegations]
    assert resolved_a == resolved_b == [_REAL_DIRECTIVE_CANONICAL_URN]
    assert (
        with_default_allow_pack_context.steps[0].unresolved_candidates
        == no_pack_context_at_all.steps[0].unresolved_candidates
        == ()
    )


# ---------------------------------------------------------------------------
# T009 -- C-001 proof for an ORG-TIER node (WP02, mission #3516): FR-002
# makes the org-tier directive node reachable; activation filtering (C-001,
# unchanged by this mission) still gates whether it's usable. Both
# directions explicit -- none of the tests above exercise an org-tier node.
# ---------------------------------------------------------------------------


def test_org_tier_directive_visible_pre_filter_and_excluded_when_deactivated(
    tmp_path: Path,
) -> None:
    """C-001: the org-tier directive resolves when its kind+stem are
    activated, and is correctly EXCLUDED (unresolved, not resolved) when
    ``directives`` is not an activated kind -- proving FR-002 only makes the
    org node *reachable*, never bypassing the existing activation gate.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    org_root = tmp_path / "org-pack"
    write_org_tier_step_contract_fixture(org_root)
    write_org_pack_config(repo_root, org_root)

    def _pack(*, directives_activated: bool) -> PackContext:
        return PackContext(
            activated_kinds=frozenset({"directives"}) if directives_activated else frozenset(),
            activated_mission_types=frozenset(),
            pack_roots=(repo_root, org_root),
            org_pack_names=(ORG_FIXTURE_PACK_NAME,),
            repo_root=repo_root,
            activated_directives=frozenset({ORG_FIXTURE_DIRECTIVE_STEM}) if directives_activated else None,
        )

    def _run(*, directives_activated: bool) -> StepContractExecutionResult:
        with patch(
            "charter.activation.pack_context.PackContext.from_config",
            return_value=_pack(directives_activated=directives_activated),
        ):
            return StepContractExecutor(
                repo_root=repo_root,
                invocation_executor=_FakeInvocationExecutor(),
            ).execute(
                StepContractExecutionContext(
                    repo_root=repo_root,
                    mission=ORG_FIXTURE_MISSION,
                    action=ORG_FIXTURE_ACTION,
                    actor="pytest",
                    profile_hint="implementer-fixture",
                )
            )

    activated_result = _run(directives_activated=True)
    deactivated_result = _run(directives_activated=False)

    # Visible (resolved) when the org-tier kind+stem is activated.
    assert [d.urn for d in activated_result.steps[0].resolved_delegations] == [ORG_FIXTURE_DIRECTIVE_URN]
    assert activated_result.steps[0].unresolved_candidates == ()

    # Excluded (unresolved) when ``directives`` is not an activated kind at
    # all -- the org node is reachable in the merged graph (FR-002) but the
    # unchanged activation filter (C-001) still drops it before delegation
    # resolution sees it.
    assert deactivated_result.steps[0].resolved_delegations == ()
    assert deactivated_result.steps[0].unresolved_candidates == (ORG_FIXTURE_DIRECTIVE_STEM,)
