"""Composition-dispatch seam tests for ``runtime_bridge_composition`` (#2531 WP08, FR-008).

Four concerns, mirroring the WP03/WP04/WP05 test-file pattern:

1. **Compat surface** (``test_seam_defines_every_relocated_symbol``,
   ``test_runtime_bridge_keeps_plain_reexports_for_untracked_helpers``) — the
   non-vacuousness + plain-reexport half of the split contract from
   contracts/compat-surface.md; the native-thin-delegate half was previously
   pinned by a dedicated frozen family guard, retired in #3285.

2. **FR-008 both-branch fixture** (``test_should_dispatch_via_composition_*``)
   — the selection seam exercised for BOTH outcomes (dispatch / no-dispatch),
   plus the C-005 audit that it imports no gates (#2535) code.

3. **Focused unit tests (FR-006)** against the moved cluster in isolation,
   stubbing collaborators at their source (charter / doctrine / mission_step_
   contracts / executor), mirroring the pattern
   ``tests/runtime/test_bridge_retrospective.py`` already uses.

4. **Intra-seam live-lookup regression** (the WP03-WP07 risk flagged in
   ``research.md`` §Compat and ``contracts/compat-surface.md``): now that the
   whole cluster lives together in one seam module, an intra-cluster call
   between two compat-guarded symbols (or a call back into a symbol that
   stays in the residual, e.g. ``_should_advance_wp_step``) MUST resolve via
   a live lookup back through ``runtime_bridge`` (never a bare intra-module
   call), or a ``monkeypatch.setattr(runtime_bridge, "<name>", …)`` becomes a
   no-op (false-green). ``test_*_uses_live_lookup_for_*`` pin this by
   patching the callee on ``runtime_bridge`` and asserting the (unpatched)
   caller in the seam still observes it.
"""

from __future__ import annotations

import ast
import json
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml

from runtime.next import runtime_bridge_composition as composition
from runtime.next import runtime_bridge_cores as cores_seam
from runtime.next import runtime_bridge_engine as engine_seam
from runtime.next import runtime_bridge_io as io_seam
from tests.specify_cli.mission_step_contracts.test_executor import (
    ORG_FIXTURE_CONTRACT_ID,
    write_org_pack_config,
    write_org_tier_step_contract_fixture,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# ---------------------------------------------------------------------------
# 1. Compat surface (non-vacuousness-checked)
# ---------------------------------------------------------------------------

_RUNTIME_BRIDGE_PATH = Path(__file__).resolve().parents[2] / "src" / "runtime" / "next" / "runtime_bridge.py"

# The 8 compat-guarded symbols (contracts/compat-surface.md) that MUST stay
# natively defined in runtime_bridge.py as thin delegates (never a plain
# re-export) -- see runtime_bridge_composition's module docstring for why.
_COMPAT_GUARDED_NAMES = frozenset(
    {
        "_should_dispatch_via_composition",
        "_normalize_action_for_composition",
        "_dispatch_via_composition",
        "_check_composed_action_guard",
        "_resolve_step_agent_profile",
        "_resolve_runtime_contract_for_step",
        "_count_source_documented_events",
        "_publication_approved",
    }
)

# Symbols that live on this seam but have NO ``runtime_bridge`` façade
# re-export -- callers reach them directly on the seam. WP18 (#2561) retired
# the ``_composition_dispatch_inputs`` / ``_has_generated_docs`` plain
# re-exports (nothing patched them via the façade path), joining the two
# helpers that were already re-export-free.
_INTERNAL_ONLY_NAMES = frozenset(
    {
        "_resolve_step_binding",
        "_LEGACY_TASKS_STEP_IDS",
        "_composition_dispatch_inputs",
        "_has_generated_docs",
    }
)


def test_seam_defines_every_relocated_symbol() -> None:
    """Non-vacuousness check: the seam must actually define every relocated
    name. Native-thin-delegate status for the compat-guarded set was pinned by
    a dedicated frozen family guard, retired in #3285; this check only guards
    against passing for the wrong reason (nobody needing the cluster at all)."""
    for name in sorted(_COMPAT_GUARDED_NAMES | _INTERNAL_ONLY_NAMES):
        assert hasattr(composition, name), f"seam is missing relocated symbol {name!r}"


def test_untracked_helpers_have_no_runtime_bridge_reexport() -> None:
    """WP18 (#2561): the two untracked helpers are reached directly on the
    seam -- the ``runtime_bridge`` façade re-export was retired, so nothing
    resolves them through ``runtime_bridge.<name>`` any more."""
    from runtime.next import runtime_bridge as rb

    for name in ("_composition_dispatch_inputs", "_has_generated_docs"):
        assert callable(getattr(composition, name)), f"{name!r} missing from the seam"
        assert not hasattr(rb, name), f"{name!r} unexpectedly still exported on runtime_bridge -- the WP18 façade-re-export retirement regressed"


@pytest.mark.architectural
def test_should_dispatch_via_composition_imports_no_gates_code() -> None:
    """FR-008 / C-005 (load-bearing): the selection seam must import NO gates
    (#2535) code and pull in no ``resolve_gates`` dependency -- the inversion
    that consumes this seam is gates mission WP14, landing after this
    mission. AST-scan the whole seam module (not just the one function) so a
    future edit anywhere in the file cannot quietly introduce the coupling."""
    source = _module_source()
    tree = ast.parse(source, filename=str(_composition_path()))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and "gates" in node.module.lower():
            offenders.append(f"line {node.lineno}: from {node.module} import ...")
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "gates" in alias.name.lower():
                    offenders.append(f"line {node.lineno}: import {alias.name}")
        # AST nodes only (never docstrings/comments, which are plain string
        # Constants, not Name/Attribute references) -- catches an aliased
        # `resolve_gates` call slipping in without a module name containing
        # "gates".
        if isinstance(node, ast.Name) and node.id == "resolve_gates":
            offenders.append(f"line {node.lineno}: reference to name resolve_gates")
        if isinstance(node, ast.Attribute) and node.attr == "resolve_gates":
            offenders.append(f"line {node.lineno}: reference to attribute resolve_gates")
    assert not offenders, (
        "runtime_bridge_composition.py imports gates (#2535) code -- FR-008/C-005 "
        "requires this seam stay clean for gates WP14 to route through later:\n" + "\n".join(offenders)
    )


def _composition_path() -> Path:
    return Path(composition.__file__)


def _module_source() -> str:
    return _composition_path().read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Frozen-template helper (self-contained -- this file owns it, mirrors
# tests/next/test_composition_gate_widening.py's established convention).
# ---------------------------------------------------------------------------


def _write_frozen_template(
    run_dir: Path,
    *,
    mission_key: str,
    steps: list[dict[str, object]],
) -> Path:
    """Write a minimal frozen template at the layout ``_load_frozen_template`` expects."""
    run_dir.mkdir(parents=True, exist_ok=True)
    template = {
        "mission": {
            "key": mission_key,
            "name": mission_key,
            "version": "1.0.0",
            "description": f"Test mission for {mission_key}",
        },
        "steps": steps,
    }
    frozen_path = run_dir / "mission_template_frozen.yaml"
    frozen_path.write_text(yaml.safe_dump(template), encoding="utf-8")
    return frozen_path


_REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# 2. FR-008 both-branch fixture for _should_dispatch_via_composition
# ---------------------------------------------------------------------------


def test_should_dispatch_via_composition_both_branches(tmp_path: Path) -> None:
    """The FR-008 selection seam's BOTH outcomes, driven without ``repo_root``
    (skips the charter lookup entirely, mirrors
    tests/next/test_composition_gate_widening.py) so only the custom-widening
    branch is exercised here."""
    dispatch_run_dir = tmp_path / "dispatch-run"
    _write_frozen_template(
        dispatch_run_dir,
        mission_key="custom-mission",
        steps=[{"id": "step1", "title": "Step One", "agent_profile": "implementer-ivan"}],
    )
    assert composition._should_dispatch_via_composition("custom-mission", "step1", run_dir=dispatch_run_dir) is True

    no_dispatch_run_dir = tmp_path / "no-dispatch-run"
    _write_frozen_template(
        no_dispatch_run_dir,
        mission_key="custom-mission",
        steps=[{"id": "step1", "title": "Step One"}],  # no agent_profile / contract_ref
    )
    assert composition._should_dispatch_via_composition("custom-mission", "step1", run_dir=no_dispatch_run_dir) is False


def test_should_dispatch_via_composition_both_branches_via_charter_lookup(tmp_path: Path) -> None:
    """Same both-branch requirement, but driven through the REAL charter
    lookup path (repo_root supplied) against this repo's actual doctrine
    data -- the built-in software-dev action sequence always dispatches;
    an unrelated custom mission with no run_dir cannot widen."""
    assert composition._should_dispatch_via_composition("software-dev", "specify", repo_root=_REPO_ROOT) is True
    assert composition._should_dispatch_via_composition("totally-unknown-mission", "step1", repo_root=_REPO_ROOT) is False


def test_should_dispatch_via_composition_uses_live_lookup_for_normalize(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Live-lookup regression: the charter branch must resolve
    ``_normalize_action_for_composition`` via ``runtime_bridge`` -- a bare
    intra-module call would silently bypass a patch on
    ``runtime_bridge._normalize_action_for_composition``."""
    from runtime.next import runtime_bridge as rb

    monkeypatch.setattr(
        "charter.activation.mission_type_profiles.resolve_mission_type_context",
        lambda repo_root, *, mission_type=None, feature_dir=None: SimpleNamespace(action_sequence=["patched-action"]),
    )
    calls: list[str] = []

    def _fake_normalize(step_id: str) -> str:
        calls.append(step_id)
        return "patched-action"

    monkeypatch.setattr(rb, "_normalize_action_for_composition", _fake_normalize)

    result = composition._should_dispatch_via_composition("software-dev", "unrelated-step", repo_root=tmp_path)

    assert calls == ["unrelated-step"]
    assert result is True  # only true because the patched normalize fired


# ---------------------------------------------------------------------------
# 3a. _normalize_action_for_composition
# ---------------------------------------------------------------------------


def test_normalize_action_for_composition_collapses_legacy_tasks_substeps() -> None:
    for legacy in ("tasks_outline", "tasks_packages", "tasks_finalize"):
        assert composition._normalize_action_for_composition(legacy) == "tasks"


def test_normalize_action_for_composition_passes_through_other_ids() -> None:
    for step_id in ("specify", "plan", "tasks", "implement", "review", "accept"):
        assert composition._normalize_action_for_composition(step_id) == step_id


# ---------------------------------------------------------------------------
# 3b. _resolve_step_binding / _resolve_step_agent_profile
# ---------------------------------------------------------------------------


def test_resolve_step_binding_missing_template_returns_none_pair(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"  # never created -- no frozen template
    assert composition._resolve_step_binding(run_dir, "step1") == (None, None)


def test_resolve_step_binding_missing_step_returns_none_pair(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_frozen_template(run_dir, mission_key="custom-mission", steps=[{"id": "other", "title": "Other"}])
    assert composition._resolve_step_binding(run_dir, "step1") == (None, None)


def test_resolve_step_binding_treats_blank_strings_as_none(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_frozen_template(
        run_dir,
        mission_key="custom-mission",
        steps=[{"id": "step1", "title": "Step One", "agent_profile": "  ", "contract_ref": "  "}],
    )
    assert composition._resolve_step_binding(run_dir, "step1") == (None, None)


def test_resolve_step_binding_returns_profile_and_contract_ref(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_frozen_template(
        run_dir,
        mission_key="custom-mission",
        steps=[{"id": "step1", "title": "Step One", "agent_profile": "implementer-ivan", "contract_ref": "ref-1"}],
    )
    assert composition._resolve_step_binding(run_dir, "step1") == ("implementer-ivan", "ref-1")


def test_resolve_step_agent_profile_returns_only_the_profile(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_frozen_template(
        run_dir,
        mission_key="custom-mission",
        steps=[{"id": "step1", "title": "Step One", "agent_profile": "implementer-ivan", "contract_ref": "ref-1"}],
    )
    assert composition._resolve_step_agent_profile(run_dir, "step1") == "implementer-ivan"


def test_resolve_step_binding_uses_live_lookup_for_normalize(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Live-lookup regression: patching ``runtime_bridge._normalize_action_for_composition``
    must still be observed from inside ``_resolve_step_binding`` even though
    both symbols now live in the same seam module."""
    from runtime.next import runtime_bridge as rb

    run_dir = tmp_path / "run"
    _write_frozen_template(
        run_dir,
        mission_key="custom-mission",
        steps=[{"id": "step1", "title": "Step One", "agent_profile": "implementer-ivan"}],
    )
    calls: list[str] = []

    def _fake_normalize(step_id: str) -> str:
        calls.append(step_id)
        return "step1"  # pretend "weird-id" normalizes to "step1"

    monkeypatch.setattr(rb, "_normalize_action_for_composition", _fake_normalize)

    profile, _contract_ref = composition._resolve_step_binding(run_dir, "weird-id")

    assert calls == ["weird-id"]
    # Only non-None because the patched normalize mapped "weird-id" -> "step1".
    assert profile == "implementer-ivan"


# ---------------------------------------------------------------------------
# 3c. _resolve_runtime_contract_for_step
# ---------------------------------------------------------------------------


def test_resolve_runtime_contract_for_step_returns_none_when_no_frozen_template(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"  # never created
    assert composition._resolve_runtime_contract_for_step(repo_root=tmp_path, run_dir=run_dir, mission="custom-mission", step_id="step1") is None


def test_resolve_runtime_contract_for_step_returns_none_when_step_has_no_binding(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_frozen_template(run_dir, mission_key="custom-mission", steps=[{"id": "step1", "title": "Step One"}])
    assert composition._resolve_runtime_contract_for_step(repo_root=tmp_path, run_dir=run_dir, mission="custom-mission", step_id="step1") is None


def test_resolve_runtime_contract_for_step_looks_up_by_contract_ref(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_frozen_template(
        run_dir,
        mission_key="custom-mission",
        steps=[{"id": "step1", "title": "Step One", "contract_ref": "ref-123"}],
    )
    sentinel_contract = object()
    seen_refs: list[str] = []

    monkeypatch.setattr(
        "charter.offering.missions.step_contracts.MissionStepContractRepository",
        lambda *, project_dir, org_dirs=None: object(),
    )

    def _fake_lookup(contract_ref: str, repository: Any) -> Any:
        seen_refs.append(contract_ref)
        return sentinel_contract

    monkeypatch.setattr("specify_cli.mission_loader.registry.lookup_contract", _fake_lookup)

    result = composition._resolve_runtime_contract_for_step(repo_root=tmp_path, run_dir=run_dir, mission="custom-mission", step_id="step1")
    assert result is sentinel_contract
    assert seen_refs == ["ref-123"]


def test_resolve_runtime_contract_for_step_synthesizes_for_agent_profile(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_frozen_template(
        run_dir,
        mission_key="custom-mission",
        steps=[{"id": "step1", "title": "Step One", "agent_profile": "implementer-ivan"}],
    )

    class _FakeContract:
        def __init__(self, contract_id: str) -> None:
            self.id = contract_id

    matching = _FakeContract("custom:custom-mission:step1")
    other = _FakeContract("custom:custom-mission:other-step")

    monkeypatch.setattr(
        "specify_cli.mission_loader.contract_synthesis.synthesize_contracts",
        lambda template: [other, matching],
    )

    result = composition._resolve_runtime_contract_for_step(repo_root=tmp_path, run_dir=run_dir, mission="custom-mission", step_id="step1")
    assert result is matching


def test_resolve_runtime_contract_for_step_uses_live_lookup_for_normalize(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Live-lookup regression: patching
    ``runtime_bridge._normalize_action_for_composition`` must still be
    observed from inside ``_resolve_runtime_contract_for_step``."""
    from runtime.next import runtime_bridge as rb

    run_dir = tmp_path / "run"
    _write_frozen_template(
        run_dir,
        mission_key="custom-mission",
        steps=[{"id": "step1", "title": "Step One", "contract_ref": "ref-xyz"}],
    )
    calls: list[str] = []

    def _fake_normalize(step_id: str) -> str:
        calls.append(step_id)
        return "step1"

    monkeypatch.setattr(rb, "_normalize_action_for_composition", _fake_normalize)
    monkeypatch.setattr(
        "charter.offering.missions.step_contracts.MissionStepContractRepository",
        lambda *, project_dir, org_dirs=None: object(),
    )
    sentinel = object()
    monkeypatch.setattr(
        "specify_cli.mission_loader.registry.lookup_contract",
        lambda ref, repo: sentinel,
    )

    result = composition._resolve_runtime_contract_for_step(repo_root=tmp_path, run_dir=run_dir, mission="custom-mission", step_id="weird-id")

    assert calls == ["weird-id"]
    assert result is sentinel


# ---------------------------------------------------------------------------
# 3c-bis. FR-006 org-tier resolution (T013, SC-003) + identical-absent-failure
# proof shared with tests/unit/mission_loader/test_command.py's T014 (User
# Story 2, Acceptance Scenario 3).
#
# SC-003 calls for ONE synthetic org-pack fixture reused by three test
# functions (WP02's executor/gate_bindings tests plus this WP's runtime/
# mission-load pair) -- the SAME ``write_org_tier_step_contract_fixture`` /
# ``write_org_pack_config`` / ``ORG_FIXTURE_CONTRACT_ID`` that
# tests/specify_cli/mission_step_contracts/test_executor.py (T008) and
# tests/review/test_gate_bindings.py (T010) already import, not a
# locally-duplicated copy. A prior revision of this file (and
# tests/unit/mission_loader/test_command.py) duplicated a smaller
# ``_write_org_step_contract_fixture`` verbatim in both files because WP02
# had not yet landed when this WP was authored; that duplication was
# retired here in favor of the canonical shared fixture now that it exists,
# per this mission's pre-merge review.
# ---------------------------------------------------------------------------


def test_resolve_runtime_contract_for_step_resolves_org_tier_contract_ref(
    tmp_path: Path,
) -> None:
    """FR-006 / T013 / SC-003: an org-tier ``contract_ref`` resolves at live
    dispatch time now that ``_resolve_runtime_contract_for_step`` threads
    ``resolve_org_dirs(repo_root, "mission_step_contracts")`` into the
    ``MissionStepContractRepository`` it constructs."""
    org_root = tmp_path / "org-pack"
    write_org_tier_step_contract_fixture(org_root)
    write_org_pack_config(tmp_path, org_root)

    run_dir = tmp_path / "run"
    _write_frozen_template(
        run_dir,
        mission_key="custom-mission",
        steps=[{"id": "step1", "title": "Step One", "contract_ref": ORG_FIXTURE_CONTRACT_ID}],
    )

    result = composition._resolve_runtime_contract_for_step(repo_root=tmp_path, run_dir=run_dir, mission="custom-mission", step_id="step1")

    assert result is not None
    assert result.id == ORG_FIXTURE_CONTRACT_ID


def test_resolve_runtime_contract_for_step_returns_none_when_org_pack_absent(
    tmp_path: Path,
) -> None:
    """User Story 2, Acceptance Scenario 3 -- identical-failure half, paired
    with ``test_resolve_contract_refs_returns_error_when_org_pack_absent`` in
    tests/unit/mission_loader/test_command.py. With the org pack not
    configured at all (no ``.kittify/config.yaml``), the SAME org-tier
    ``contract_ref`` used by the success test above fails to resolve at
    runtime dispatch too -- proving the lockstep pair's FAILURE mode is
    identical, not merely that both happen to pass independently in the
    success case."""
    run_dir = tmp_path / "run"
    _write_frozen_template(
        run_dir,
        mission_key="custom-mission",
        steps=[{"id": "step1", "title": "Step One", "contract_ref": ORG_FIXTURE_CONTRACT_ID}],
    )

    result = composition._resolve_runtime_contract_for_step(repo_root=tmp_path, run_dir=run_dir, mission="custom-mission", step_id="step1")

    assert result is None


def test_resolve_contract_refs_and_resolve_runtime_contract_for_step_resolve_identically(
    tmp_path: Path,
) -> None:
    """Lockstep pair B (FR-006 / FR-006a): mission-load-time
    ``_resolve_contract_refs`` (``specify_cli.mission_loader.command``) and
    runtime-dispatch-time ``_resolve_runtime_contract_for_step`` (this
    module) must resolve the identical org-tier ``contract_ref`` the same
    way, given the identical org-pack configuration.

    Mirrors lockstep pair A
    (``tests/review/test_gate_bindings.py::test_build_repository_and_executor_resolve_identical_org_dirs``),
    which directly compares the two construction sites' ``_org_dirs``
    attribute. Pair B's two call sites are free functions with no
    repository object exposed to the caller, so this guard proves lockstep
    behaviorally instead: with the SAME org-pack fixture, if either call
    site regresses (e.g. drops its ``org_dirs=`` argument and silently
    falls back to project-tier-only resolution), the two resolutions
    diverge -- one succeeds, one fails -- and this test goes red. Closes
    the gap flagged in this mission's pre-merge review ("Pair B has no
    equivalent").
    """
    from specify_cli.mission_loader.command import _resolve_contract_refs
    from runtime.next._internal_runtime.schema import MissionTemplate

    org_root = tmp_path / "org-pack"
    write_org_tier_step_contract_fixture(org_root)
    write_org_pack_config(tmp_path, org_root)

    load_error = _resolve_contract_refs(
        mission_key="custom-mission",
        template=MissionTemplate.model_validate(
            {
                "mission": {
                    "key": "custom-mission",
                    "name": "Custom Mission",
                    "version": "1.0.0",
                },
                "steps": [
                    {
                        "id": "step1",
                        "title": "Step One",
                        "contract_ref": ORG_FIXTURE_CONTRACT_ID,
                    }
                ],
            }
        ),
        source_path="irrelevant.yaml",
        repo_root=tmp_path,
    )

    run_dir = tmp_path / "run"
    _write_frozen_template(
        run_dir,
        mission_key="custom-mission",
        steps=[{"id": "step1", "title": "Step One", "contract_ref": ORG_FIXTURE_CONTRACT_ID}],
    )
    runtime_result = composition._resolve_runtime_contract_for_step(repo_root=tmp_path, run_dir=run_dir, mission="custom-mission", step_id="step1")

    assert load_error is None, "mission-load validation must resolve the org-tier contract_ref"
    assert runtime_result is not None, "runtime dispatch must resolve the SAME org-tier contract_ref"
    assert runtime_result.id == ORG_FIXTURE_CONTRACT_ID


# ---------------------------------------------------------------------------
# 3d. _composition_dispatch_inputs
# ---------------------------------------------------------------------------


def test_composition_dispatch_inputs_resolves_profile_even_when_action_in_charter_sequence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """FR-001/FR-003 regression (#3830): the canonical ``PromptStep.agent_profile``
    resolution path (``_resolve_step_agent_profile``, the FR-008-mandated path
    per ``mission_step_contracts/executor.py:68-71``) must run even when
    ``action`` is a member of the resolved mission type's own
    ``action_sequence`` -- the common case for every canonical step of every
    mission type. Before the fix, a misplaced early ``return None, None``
    short-circuited resolution exactly in this case, making the mandated path
    unreachable and forcing ``StepContractExecutor._resolve_profile_hint`` to
    fall through to the built-ins-only ``_ACTION_PROFILE_DEFAULTS`` table and
    raise ``profile_hint is required`` for any custom mission type."""
    monkeypatch.setattr(
        "charter.activation.mission_type_profiles.resolve_mission_type_context",
        lambda repo_root, *, mission_type=None, feature_dir=None: SimpleNamespace(action_sequence=["step1"]),
    )
    run_dir = tmp_path / "run"
    _write_frozen_template(
        run_dir,
        mission_key="qa",
        steps=[{"id": "step1", "title": "Step One", "agent_profile": "reviewer-renata"}],
    )

    profile, _contract = composition._composition_dispatch_inputs(repo_root=tmp_path, run_dir=run_dir, mission="qa", step_id="step1", action="step1")

    assert profile == "reviewer-renata"


def test_composition_dispatch_inputs_resolves_frozen_binding_when_no_action_default_exists(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """#397 regression: a custom mission type (e.g. an org-pack ``qa`` mission)
    can resolve a charter action sequence that includes an action with NO
    entry in ``StepContractExecutor._ACTION_PROFILE_DEFAULTS`` (that table is
    built-in-missions-only). The short-circuit to ``(None, None)`` must NOT
    fire for such an action -- it must fall through to the frozen template's
    explicit ``agent-profile`` binding, or the executor can never resolve a
    profile hint and blocks with "profile_hint is required when no action
    default exists"."""
    monkeypatch.setattr(
        "charter.activation.mission_type_profiles.resolve_mission_type_context",
        lambda repo_root, *, mission_type=None, feature_dir=None: SimpleNamespace(action_sequence=["discovery", "test_strategy"]),
    )
    run_dir = tmp_path / "run"
    _write_frozen_template(
        run_dir,
        mission_key="qa",
        steps=[{"id": "discovery", "title": "Discovery", "agent_profile": "researcher-robbie"}],
    )

    profile, contract = composition._composition_dispatch_inputs(repo_root=tmp_path, run_dir=run_dir, mission="qa", step_id="discovery", action="discovery")

    assert profile == "researcher-robbie"
    assert contract is not None
    assert contract.id == "custom:qa:discovery"


@pytest.mark.parametrize(
    ("mission", "step_id", "action"),
    [
        ("software-dev", "specify", "specify"),
        ("research", "scoping", "scoping"),
        ("documentation", "discover", "discover"),
    ],
)
def test_composition_dispatch_inputs_builtin_types_unaffected(mission: str, step_id: str, action: str, tmp_path: Path) -> None:
    """Blast Radius (plan.md): software-dev/research/documentation resolve
    ``profile_hint`` via ``_ACTION_PROFILE_DEFAULTS`` exactly as before --
    unaffected by the FR-001/FR-003 fix. None of their canonical steps set
    ``agent_profile`` on the frozen template, so ``_resolve_step_agent_profile``
    still resolves to ``None`` for them (the same value the removed early
    return also produced for these actions) -- ``StepContractExecutor.
    _resolve_profile_hint``'s built-ins-only table is the unaffected
    fallback. Driven live against this repo's actual doctrine data
    (repo_root=_REPO_ROOT, no mocking)."""
    profile, _contract = composition._composition_dispatch_inputs(
        repo_root=_REPO_ROOT,
        run_dir=tmp_path,  # no frozen template -- matches every real first-touch dispatch
        mission=mission,
        step_id=step_id,
        action=action,
    )
    assert profile is None


def test_composition_dispatch_inputs_uses_live_lookup_for_resolution_helpers(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Live-lookup regression: even when ``resolve_mission_type_context``
    genuinely raises, ``_composition_dispatch_inputs`` must still resolve
    ``_resolve_step_agent_profile`` / ``_resolve_runtime_contract_for_step``
    via a live lookup through ``runtime_bridge`` -- a bare intra-module call
    would silently bypass a monkeypatch on ``runtime_bridge.<name>``."""
    from runtime.next import runtime_bridge as rb

    def _raise_unknown(repo_root: Path, *, mission_type: str | None = None, feature_dir: Path | None = None) -> SimpleNamespace:
        from charter.activation.mission_type_profiles import UnknownMissionTypeError

        raise UnknownMissionTypeError(mission_type)

    monkeypatch.setattr("charter.activation.mission_type_profiles.resolve_mission_type_context", _raise_unknown)

    calls: list[str] = []

    def _fake_resolve_profile(run_dir: Path, step_id: str) -> str:
        calls.append("profile")
        return "patched-profile"

    def _fake_resolve_contract(**kwargs: Any) -> str:
        calls.append("contract")
        return "patched-contract"

    monkeypatch.setattr(rb, "_resolve_step_agent_profile", _fake_resolve_profile)
    monkeypatch.setattr(rb, "_resolve_runtime_contract_for_step", _fake_resolve_contract)

    profile, contract = composition._composition_dispatch_inputs(repo_root=tmp_path, run_dir=tmp_path, mission="custom-mission", step_id="step1", action="step1")
    assert profile == "patched-profile"
    assert contract == "patched-contract"
    assert calls == ["profile", "contract"]


def test_composition_dispatch_inputs_logs_genuine_resolve_mission_type_context_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """FR-002 (#3830): a genuine ``resolve_mission_type_context`` failure (e.g.
    a malformed org pack) must produce an ERROR-level log record via the
    module's own logger -- previously a bare ``except Exception: pass``
    swallowed it with no diagnostic surface at all. ``UnknownMissionTypeError``
    is NOT a genuine failure -- it is the expected outcome for any
    non-charter-activated custom mission type (the normal #3830
    frozen-template path), so it must log at DEBUG only and must never
    produce a WARNING/ERROR record on this ordinary happy path (#3830
    regression: an earlier revision logged a full ERROR traceback here on
    every dispatch for a custom type). Negative case (NFR-001, asserted in
    this SAME test function per SC-004's own established pattern in this
    file, so a future change cannot break the negative case while the
    positive cases still pass): the ordinary "resolution succeeded" case
    must continue to log nothing -- genuine failure, expected
    non-activation, and ordinary success must all be distinguishable by log
    presence/level, not conflated."""
    from charter.activation.mission_type_profiles import UnknownMissionTypeError

    run_dir = tmp_path / "run"
    _write_frozen_template(
        run_dir,
        mission_key="qa",
        steps=[{"id": "step1", "title": "Step One", "agent_profile": "reviewer-renata"}],
    )

    # Case 1 (expected/happy path): resolve_mission_type_context raises
    # UnknownMissionTypeError for a non-charter-activated custom type --
    # must log at DEBUG only, never WARNING/ERROR.
    def _raise_unknown(repo_root: Path, *, mission_type: str | None = None, feature_dir: Path | None = None) -> SimpleNamespace:
        raise UnknownMissionTypeError(mission_type)

    monkeypatch.setattr("charter.activation.mission_type_profiles.resolve_mission_type_context", _raise_unknown)

    with caplog.at_level(logging.DEBUG, logger="runtime.next.runtime_bridge"):
        profile, _contract = composition._composition_dispatch_inputs(repo_root=tmp_path, run_dir=run_dir, mission="qa", step_id="step1", action="step1")

    # Resolution still proceeds via the frozen-template fallback path.
    assert profile == "reviewer-renata"
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
    debug_records = [r for r in caplog.records if r.levelno == logging.DEBUG]
    assert len(debug_records) == 1
    assert "qa" in debug_records[0].getMessage()

    caplog.clear()

    # Case 2 (genuine failure): a non-UnknownMissionTypeError exception (e.g.
    # a malformed org pack) must still produce exactly one ERROR record via
    # logger.exception.
    def _raise_malformed(repo_root: Path, *, mission_type: str | None = None, feature_dir: Path | None = None) -> SimpleNamespace:
        raise ValueError("malformed org pack")

    monkeypatch.setattr("charter.activation.mission_type_profiles.resolve_mission_type_context", _raise_malformed)

    with caplog.at_level(logging.DEBUG, logger="runtime.next.runtime_bridge"):
        profile, _contract = composition._composition_dispatch_inputs(repo_root=tmp_path, run_dir=run_dir, mission="qa", step_id="step1", action="step1")

    assert profile == "reviewer-renata"
    error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert len(error_records) == 1
    message = error_records[0].getMessage()
    assert "qa" in message
    assert "step1" in message

    caplog.clear()

    # Case 3 (NFR-001): ordinary successful resolution logs nothing.
    monkeypatch.setattr(
        "charter.activation.mission_type_profiles.resolve_mission_type_context",
        lambda repo_root, *, mission_type=None, feature_dir=None: SimpleNamespace(action_sequence=["step1"]),
    )

    with caplog.at_level(logging.DEBUG, logger="runtime.next.runtime_bridge"):
        profile, _contract = composition._composition_dispatch_inputs(repo_root=tmp_path, run_dir=run_dir, mission="qa", step_id="step1", action="step1")

    assert profile == "reviewer-renata"
    assert not caplog.records


# ---------------------------------------------------------------------------
# 3e. _count_source_documented_events / _publication_approved / _has_generated_docs
# ---------------------------------------------------------------------------


def test_count_source_documented_events_counts_matching_entries(tmp_path: Path) -> None:
    events = [{"type": "source_documented", "name": f"src-{i}"} for i in range(3)]
    events.append({"type": "other_event"})
    (tmp_path / "mission-events.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    assert composition._count_source_documented_events(tmp_path) == 3


def test_count_source_documented_events_missing_log_returns_zero(tmp_path: Path) -> None:
    assert composition._count_source_documented_events(tmp_path) == 0


def test_publication_approved_true_when_gate_event_present(tmp_path: Path) -> None:
    events = [{"type": "gate_passed", "name": "publication_approved"}]
    (tmp_path / "mission-events.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    assert composition._publication_approved(tmp_path) is True


def test_publication_approved_false_when_missing(tmp_path: Path) -> None:
    assert composition._publication_approved(tmp_path) is False


def test_has_generated_docs_true_when_markdown_present(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.md").write_text("# Docs\n", encoding="utf-8")
    assert composition._has_generated_docs(tmp_path) is True


def test_has_generated_docs_false_when_docs_dir_absent(tmp_path: Path) -> None:
    assert composition._has_generated_docs(tmp_path) is False


# ---------------------------------------------------------------------------
# 3f. _check_composed_action_guard
# ---------------------------------------------------------------------------


def test_check_composed_action_guard_delegates_to_cores_and_io(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from runtime.next.runtime_bridge_io import ArtifactPresenceSnapshot

    def _fake_gather(
        feature_dir: Path,
        *,
        mission_family: str,
        step_id: str,
        legacy_step_id: str | None = None,
        repo_root: Path | None = None,
        owned: object | None = None,
    ) -> Any:
        return ArtifactPresenceSnapshot(
            present_artifacts=frozenset(),
            status_facts={},
            mission_family=mission_family,
            step_id=step_id,
            legacy_step_id=legacy_step_id,
        )

    monkeypatch.setattr(io_seam, "gather_artifact_presence", _fake_gather)
    monkeypatch.setattr(cores_seam, "evaluate_guards_strict", lambda snapshot: ["boom"])

    failures = composition._check_composed_action_guard("specify", tmp_path, mission="software-dev")
    assert failures == ["boom"]


def test_check_composed_action_guard_uses_live_lookup_for_should_advance_wp_step(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Live-lookup regression: ``_should_advance_wp_step`` stays defined in
    the residual (untouched by this WP) -- ``_check_composed_action_guard``
    must reach it via a live lookup through ``runtime_bridge``."""
    from runtime.next import runtime_bridge as rb
    from runtime.next.runtime_bridge_io import ArtifactPresenceSnapshot

    captured: dict[str, Any] = {}

    def _fake_gather(
        feature_dir: Path,
        *,
        mission_family: str,
        step_id: str,
        legacy_step_id: str | None = None,
        repo_root: Path | None = None,
        owned: object | None = None,
    ) -> Any:
        return ArtifactPresenceSnapshot(
            present_artifacts=frozenset(),
            status_facts={},
            mission_family=mission_family,
            step_id=step_id,
            legacy_step_id=legacy_step_id,
        )

    def _fake_evaluate(snapshot: Any) -> list[str]:
        captured["wp_advance_ready"] = snapshot.wp_advance_ready
        return []

    monkeypatch.setattr(io_seam, "gather_artifact_presence", _fake_gather)
    monkeypatch.setattr(cores_seam, "evaluate_guards_strict", _fake_evaluate)
    monkeypatch.setattr(rb, "_should_advance_wp_step", lambda step_id, feature_dir: True)

    failures = composition._check_composed_action_guard("implement", tmp_path, mission="software-dev")

    assert failures == []
    assert captured["wp_advance_ready"] is True


def test_check_composed_action_guard_warns_for_unregistered_mission_family(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """T002 step 3 (FR-003/FR-004/C-001): an unregistered ``mission_family``
    reaching the composed path must degrade to `[]` (not the software-dev
    misfire it falls through to today) AND log a WARNING-or-above record
    naming the family -- RED today for two independent reasons: (a) today's
    tolerant ``evaluate_guards`` falls through to the software-dev
    WP-iteration guard for step_id="review", returning a non-empty message,
    not `[]`; (b) no WARNING log call for this case exists anywhere in the
    module yet."""
    import logging

    from runtime.next.runtime_bridge_io import ArtifactPresenceSnapshot

    def _fake_gather(
        feature_dir: Path,
        *,
        mission_family: str,
        step_id: str,
        legacy_step_id: str | None = None,
        repo_root: Path | None = None,
        owned: object | None = None,
    ) -> Any:
        return ArtifactPresenceSnapshot(
            present_artifacts=frozenset(),
            status_facts={},
            mission_family=mission_family,
            step_id=step_id,
            legacy_step_id=legacy_step_id,
        )

    monkeypatch.setattr(io_seam, "gather_artifact_presence", _fake_gather)

    with caplog.at_level(logging.WARNING):
        failures = composition._check_composed_action_guard("review", tmp_path, mission="totally-unregistered-family")

    assert failures == []
    assert any(record.levelno >= logging.WARNING and "totally-unregistered-family" in record.getMessage() for record in caplog.records)


def test_check_composed_action_guard_does_not_thread_wp_advance_ready_for_non_wp_actions(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from runtime.next.runtime_bridge_io import ArtifactPresenceSnapshot

    captured: dict[str, Any] = {}

    def _fake_gather(
        feature_dir: Path,
        *,
        mission_family: str,
        step_id: str,
        legacy_step_id: str | None = None,
        repo_root: Path | None = None,
        owned: object | None = None,
    ) -> Any:
        return ArtifactPresenceSnapshot(
            present_artifacts=frozenset(),
            status_facts={},
            mission_family=mission_family,
            step_id=step_id,
            legacy_step_id=legacy_step_id,
        )

    def _fake_evaluate(snapshot: Any) -> list[str]:
        captured["wp_advance_ready"] = snapshot.wp_advance_ready
        return []

    monkeypatch.setattr(io_seam, "gather_artifact_presence", _fake_gather)
    monkeypatch.setattr(cores_seam, "evaluate_guards_strict", _fake_evaluate)

    composition._check_composed_action_guard("specify", tmp_path, mission="software-dev")

    assert captured["wp_advance_ready"] is None


# ---------------------------------------------------------------------------
# 3g/4. _dispatch_via_composition -- behavior + live lookup
# ---------------------------------------------------------------------------


def test_dispatch_via_composition_success_returns_none_when_guard_passes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from unittest.mock import MagicMock

    from runtime.next import runtime_bridge as rb

    monkeypatch.setattr(rb, "_check_composed_action_guard", lambda *a, **k: [])
    monkeypatch.setattr(
        "specify_cli.mission_step_contracts.executor.StepContractExecutor.execute",
        lambda self, context, contract=None: MagicMock(invocation_ids=("inv-1",)),
    )

    failures = composition._dispatch_via_composition(
        repo_root=tmp_path,
        mission="software-dev",
        action="specify",
        actor="implementer-pedro",
        profile_hint=None,
        request_text=None,
        mode_of_work=None,
        feature_dir=tmp_path,
    )
    assert failures is None


def test_dispatch_via_composition_returns_guard_failures(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from unittest.mock import MagicMock

    from runtime.next import runtime_bridge as rb

    monkeypatch.setattr(rb, "_check_composed_action_guard", lambda *a, **k: ["missing artifact"])
    monkeypatch.setattr(
        "specify_cli.mission_step_contracts.executor.StepContractExecutor.execute",
        lambda self, context, contract=None: MagicMock(invocation_ids=()),
    )

    failures = composition._dispatch_via_composition(
        repo_root=tmp_path,
        mission="software-dev",
        action="specify",
        actor="implementer-pedro",
        profile_hint=None,
        request_text=None,
        mode_of_work=None,
        feature_dir=tmp_path,
    )
    assert failures == ["missing artifact"]


def test_dispatch_via_composition_surfaces_structured_executor_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from specify_cli.mission_step_contracts.executor import StepContractExecutionError

    def _raise(self: Any, context: Any, contract: Any = None) -> Any:
        raise StepContractExecutionError("synthesized contract missing")

    monkeypatch.setattr("specify_cli.mission_step_contracts.executor.StepContractExecutor.execute", _raise)

    failures = composition._dispatch_via_composition(
        repo_root=tmp_path,
        mission="software-dev",
        action="specify",
        actor="implementer-pedro",
        profile_hint=None,
        request_text=None,
        mode_of_work=None,
        feature_dir=tmp_path,
    )
    assert failures is not None
    assert "composition failed for software-dev/specify" in failures[0]


def test_dispatch_via_composition_surfaces_unexpected_exception_as_structured_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def _raise(self: Any, context: Any, contract: Any = None) -> Any:
        raise ValueError("malformed contract yaml")

    monkeypatch.setattr("specify_cli.mission_step_contracts.executor.StepContractExecutor.execute", _raise)

    failures = composition._dispatch_via_composition(
        repo_root=tmp_path,
        mission="software-dev",
        action="specify",
        actor="implementer-pedro",
        profile_hint=None,
        request_text=None,
        mode_of_work=None,
        feature_dir=tmp_path,
    )
    assert failures is not None
    assert "composition crashed for software-dev/specify" in failures[0]
    assert "ValueError" in failures[0]


def test_dispatch_via_composition_plan_mission_keeps_distinct_step_contract_error(
    tmp_path: Path,
) -> None:
    """Blast Radius (plan.md, User Story 1 AC4, SC-001a): `plan` is NOT a
    beneficiary of the FR-001/FR-003 fix -- dispatching an action in
    `plan`'s own action_sequence must still raise the pre-existing, distinct
    ``StepContractExecutionError("No step contract found for mission/action
    plan/<action>")``, never ``profile_hint is required`` and no other
    newly-introduced behavior. Driven through the REAL charter/executor
    stack (repo_root=_REPO_ROOT, no mocking) against this repo's actual
    doctrine data: `plan` is a built-in mission type with no registered step
    contract for any of its actions (registering one is out of scope, per
    plan.md), so the executor's own ``get_by_action`` miss fires before
    ``_resolve_profile_hint`` is ever reached."""
    failures = composition._dispatch_via_composition(
        repo_root=_REPO_ROOT,
        mission="plan",
        action="specify",
        actor="implementer-ivan",
        profile_hint=None,
        request_text=None,
        mode_of_work=None,
        feature_dir=tmp_path,
    )

    assert failures is not None
    assert len(failures) == 1
    assert "No step contract found for mission/action plan/specify" in failures[0]
    assert "profile_hint is required" not in failures[0]


def test_dispatch_via_composition_uses_live_lookup_for_check_composed_action_guard(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Live-lookup regression: ``_dispatch_via_composition`` must resolve
    ``_check_composed_action_guard`` via a live lookup through
    ``runtime_bridge`` -- both symbols now live in this same seam module, the
    exact intra-seam false-green trap contracts/compat-surface.md warns
    about."""
    from unittest.mock import MagicMock

    from runtime.next import runtime_bridge as rb

    calls: list[str] = []
    repo_roots_seen: list[Path | None] = []

    def _spy_guard(
        action: str,
        feature_dir: Path,
        *,
        mission: str = "software-dev",
        legacy_step_id: str | None = None,
        repo_root: Path | None = None,
        owned: object | None = None,
    ) -> list[str]:
        calls.append(action)
        repo_roots_seen.append(repo_root)
        return ["patched-failure"]

    monkeypatch.setattr(rb, "_check_composed_action_guard", _spy_guard)
    monkeypatch.setattr(
        "specify_cli.mission_step_contracts.executor.StepContractExecutor.execute",
        lambda self, context, contract=None: MagicMock(invocation_ids=()),
    )

    failures = composition._dispatch_via_composition(
        repo_root=tmp_path,
        mission="software-dev",
        action="specify",
        actor="implementer-pedro",
        profile_hint=None,
        request_text=None,
        mode_of_work=None,
        feature_dir=tmp_path,
    )

    assert calls == ["specify"]
    assert failures == ["patched-failure"]
    # #3704 WP03: the live-lookup dispatch path must thread the caller's
    # ``repo_root`` through to ``_check_composed_action_guard`` unchanged --
    # not merely swallow it, since this is exactly the seam WP03 threaded.
    assert repo_roots_seen == [tmp_path]


def test_dispatch_via_composition_warns_on_unresolved_delegation_candidates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """FR-007 / T016 / SC-004: exactly one WARNING per step carrying 1+
    unresolved ``delegates_to`` candidates, naming the step id, contract id,
    and candidate string(s) -- and (negative case, asserted in this SAME test
    function per SC-004, so a future change cannot break the negative case
    while the positive case still passes) zero WARNING records when every
    candidate resolves."""
    from runtime.next import runtime_bridge as rb

    monkeypatch.setattr(rb, "_check_composed_action_guard", lambda *a, **k: [])

    # Positive case: one step with an unresolved candidate.
    unresolved_result = SimpleNamespace(
        contract_id="documentation-accept",
        invocation_ids=(),
        steps=(
            SimpleNamespace(
                step_id="confirm_publication_handoff",
                unresolved_candidates=("ghost-directive-999",),
            ),
        ),
    )
    monkeypatch.setattr(
        "specify_cli.mission_step_contracts.executor.StepContractExecutor.execute",
        lambda self, context, contract=None: unresolved_result,
    )

    with caplog.at_level(logging.WARNING, logger="runtime.next.runtime_bridge"):
        failures = composition._dispatch_via_composition(
            repo_root=tmp_path,
            mission="documentation",
            action="accept",
            actor="implementer-pedro",
            profile_hint=None,
            request_text=None,
            mode_of_work=None,
            feature_dir=tmp_path,
        )

    assert failures is None
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    message = warnings[0].getMessage()
    assert "confirm_publication_handoff" in message
    assert "documentation-accept" in message
    assert "ghost-directive-999" in message

    caplog.clear()

    # Negative case (SC-004): every candidate resolves -> zero WARNINGs.
    resolved_result = SimpleNamespace(
        contract_id="documentation-accept",
        invocation_ids=(),
        steps=(
            SimpleNamespace(
                step_id="confirm_publication_handoff",
                unresolved_candidates=(),
            ),
        ),
    )
    monkeypatch.setattr(
        "specify_cli.mission_step_contracts.executor.StepContractExecutor.execute",
        lambda self, context, contract=None: resolved_result,
    )

    with caplog.at_level(logging.WARNING, logger="runtime.next.runtime_bridge"):
        failures = composition._dispatch_via_composition(
            repo_root=tmp_path,
            mission="documentation",
            action="accept",
            actor="implementer-pedro",
            profile_hint=None,
            request_text=None,
            mode_of_work=None,
            feature_dir=tmp_path,
        )

    assert failures is None
    assert not any(r.levelno == logging.WARNING for r in caplog.records)


# ---------------------------------------------------------------------------
# 5. _advance_run_state_after_composition residual delegate -- untouched by
#    this WP, but pinned here so a future edit to the surrounding module
#    cannot silently break the compat surface WP03 established.
# ---------------------------------------------------------------------------


def test_advance_run_state_after_composition_delegate_still_forwards_to_engine_adapter(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from runtime.next import runtime_bridge as rb

    captured: dict[str, Any] = {}
    sentinel_decision = object()

    def _fake_advance(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return sentinel_decision

    monkeypatch.setattr(engine_seam, "advance_run_state_after_composition", _fake_advance)

    from runtime.next._internal_runtime import MissionRunRef

    run_ref = MissionRunRef(run_id="run-1", run_dir=str(tmp_path), mission_key="software-dev")
    result = rb._advance_run_state_after_composition(
        run_ref=run_ref,
        agent="agent-1",
        mission_slug="mission-1",
        mission_type="software-dev",
        repo_root=tmp_path,
        feature_dir=tmp_path,
        timestamp="2026-01-01T00:00:00Z",
        progress=None,
        origin={},
        sync_emitter=object(),
        plan=object(),
    )

    assert result is sentinel_decision
    assert captured["run_ref"] is run_ref
    assert captured["mission_slug"] == "mission-1"
