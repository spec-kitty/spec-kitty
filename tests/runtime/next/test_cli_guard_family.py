"""WP06 (#3407): CLI guard family — resolve the actual mission family.

``_check_cli_guards`` (``runtime_bridge.py``) used to hardcode
``mission_family="software-dev"`` into ``gather_artifact_presence``, routing
every mission type's CLI-guard evaluation *around* the per-type
``_GUARD_TABLES`` dispatch -- including the already-existing ``"plan"`` table
(``_evaluate_plan_guards``). The fix resolves the mission's actual family via
``get_mission_type(feature_dir)`` and threads it through, so
``evaluate_guards_strict``'s ``_GUARD_TABLES.get(family)`` dispatch reaches
the correct table.

This file pins three things (plan.md §6, spec.md AC-13/AC-14):

- AC-13 (latent-defect pin): a ``plan``-type mission's ``review`` step must
  route to ``_GUARD_TABLES["plan"]`` (``_evaluate_plan_guards`` -> ``[]``)
  instead of aliasing into ``_evaluate_wp_iteration_guard`` (the WP-block
  string), which is what happened while the family was hardcoded to
  ``"software-dev"``.
- AC-14 / NFR-003: a ``software-dev`` mission's CLI-guard evaluation is
  byte-identical to ``main`` -- the fix must not perturb the one family that
  was always being routed correctly by the hardcoded default.
- Family-key identity: ``get_mission_type`` must return exactly the
  ``_GUARD_TABLES`` family key for every built-in mission type. If a
  built-in's ``meta.json`` string ever diverged from its guard-table key, a
  legitimate mission would wrongly fail-closed via
  ``UnregisteredMissionFamilyError`` after this routing fix lands.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from runtime.next import runtime_bridge as rb
from runtime.next._internal_runtime import MissionRunRef
from runtime.next.decision import DecisionKind
from runtime.next.runtime_bridge import _check_cli_guards
from runtime.next.runtime_bridge_cores import (
    _GUARD_TABLES,
    _evaluate_plan_guards,
    UnregisteredMissionFamilyError,
    evaluate_guards_strict,
)
from runtime.next.runtime_bridge_composition import _check_composed_action_guard
from runtime.next.runtime_bridge_io import gather_artifact_presence
from specify_cli.mission import get_mission_type
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_meta(feature_dir: Path, mission_type: str) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(json.dumps({"mission_type": mission_type}), encoding="utf-8")


def _seed_wp(feature_dir: Path, wp_id: str, lane: str) -> None:
    """Seed one WP file plus a canonical status event placing it in *lane*."""
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    (tasks_dir / f"{wp_id}.md").write_text(
        f"---\nwork_package_id: {wp_id}\nlane: {lane}\ntitle: {wp_id} task\n---\n# {wp_id}\nDo something.\n",
        encoding="utf-8",
    )
    event = StatusEvent(
        event_id=f"test-{wp_id}-{lane}",
        mission_slug=feature_dir.name,
        wp_id=wp_id,
        from_lane=Lane.PLANNED,
        to_lane=Lane(lane),
        at="2026-01-01T00:00:00+00:00",
        actor="test",
        force=True,
        execution_mode="worktree",
    )
    append_event(feature_dir, event)


WP_BLOCK_REVIEW_MESSAGE = "Not all work packages are approved or done"


# ---------------------------------------------------------------------------
# AC-13 — latent-defect pin: plan-family review routes to the plan table
# ---------------------------------------------------------------------------


class TestAC13PlanReviewRoutesToPlanTable:
    def test_check_cli_guards_routes_plan_review_to_plan_table(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "042-plan-feature"
        _write_meta(feature_dir, "plan")
        # An unapproved lane -- under the (pre-fix) hardcoded software-dev
        # routing this alone was enough to make "review" fail via
        # `_evaluate_wp_iteration_guard`.
        _seed_wp(feature_dir, "WP01", "planned")

        failures = _check_cli_guards("review", feature_dir)

        assert failures == []
        assert WP_BLOCK_REVIEW_MESSAGE not in failures

    def test_routing_reaches_the_real_plan_guard_table_entry(self, tmp_path: Path) -> None:
        """Directly proves the dispatch, not just the resulting empty list."""
        feature_dir = tmp_path / "kitty-specs" / "042-plan-feature"
        _write_meta(feature_dir, "plan")
        _seed_wp(feature_dir, "WP01", "planned")

        family = get_mission_type(feature_dir)
        assert family == "plan"

        snapshot = gather_artifact_presence(feature_dir, mission_family=family, step_id="review")

        assert evaluate_guards_strict(snapshot) == _evaluate_plan_guards(snapshot) == []


# ---------------------------------------------------------------------------
# AC-14 / NFR-003 — software-dev evaluation is unchanged
# ---------------------------------------------------------------------------


class TestAC14SoftwareDevUnchanged:
    def test_review_still_blocks_on_unapproved_wps(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "042-sd-feature"
        _write_meta(feature_dir, "software-dev")
        _seed_wp(feature_dir, "WP01", "planned")

        failures = _check_cli_guards("review", feature_dir)

        assert failures == [WP_BLOCK_REVIEW_MESSAGE]

    def test_review_passes_once_all_wps_are_approved_or_done(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "042-sd-feature"
        _write_meta(feature_dir, "software-dev")
        _seed_wp(feature_dir, "WP01", "approved")
        _seed_wp(feature_dir, "WP02", "done")

        failures = _check_cli_guards("review", feature_dir)

        assert failures == []

    def test_specify_guard_still_requires_spec_md(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "042-sd-feature"
        _write_meta(feature_dir, "software-dev")

        failures = _check_cli_guards("specify", feature_dir)

        assert len(failures) == 1
        assert "spec.md" in failures[0]


# ---------------------------------------------------------------------------
# Family-key identity guard
# ---------------------------------------------------------------------------


BUILT_IN_MISSION_TYPES = ("research", "documentation", "software-dev", "plan")


class TestFamilyKeyIdentity:
    def test_guard_table_covers_exactly_the_four_built_ins(self) -> None:
        assert set(_GUARD_TABLES) == set(BUILT_IN_MISSION_TYPES)

    @pytest.mark.parametrize("mission_type", BUILT_IN_MISSION_TYPES)
    def test_get_mission_type_round_trips_to_the_guard_table_key(self, tmp_path: Path, mission_type: str) -> None:
        feature_dir = tmp_path / "kitty-specs" / "042-identity-feature"
        _write_meta(feature_dir, mission_type)

        resolved = get_mission_type(feature_dir)

        # If a built-in's meta.json string ever diverged from its
        # `_GUARD_TABLES` key, a valid mission of that type would wrongly
        # fail-close post-fix -- stop and report rather than silently
        # mapping around the mismatch.
        assert resolved == mission_type
        assert resolved in _GUARD_TABLES


# ---------------------------------------------------------------------------
# None / typeless family handling
# ---------------------------------------------------------------------------


class TestTypelessMissionFamily:
    def test_typeless_mission_fails_closed_not_crash(self, tmp_path: Path) -> None:
        """No meta.json at all -> ``get_mission_type`` degrades to ``""``
        (the neutral/typeless result, never ``None`` and never a silent
        ``software-dev`` default). ``""`` has no ``_GUARD_TABLES`` entry, so
        ``_check_cli_guards`` must fail closed via
        ``UnregisteredMissionFamilyError`` -- a clean, typed exception, not
        an ``AttributeError``/``TypeError`` crash from an unhandled ``None``.
        """
        feature_dir = tmp_path / "kitty-specs" / "042-typeless-feature"
        feature_dir.mkdir(parents=True)

        assert get_mission_type(feature_dir) == ""

        with pytest.raises(UnregisteredMissionFamilyError):
            _check_cli_guards("review", feature_dir)


# ---------------------------------------------------------------------------
# #3627 — WP-iteration branch must degrade, not raise, for an unregistered
# custom family (unlike the direct ``_check_cli_guards`` call above, whose
# fail-closed raise is deliberate and stays pinned by
# ``TestTypelessMissionFamily``).
# ---------------------------------------------------------------------------


CUSTOM_UNREGISTERED_FAMILY = "custom-onboarding-mission"


class TestIssue3627WpIterationUnregisteredFamilyDegrades:
    def _make_ctx(self, tmp_path: Path) -> rb.DecideNextContext:
        feature_dir = tmp_path / "kitty-specs" / "042-custom-mission"
        _write_meta(feature_dir, CUSTOM_UNREGISTERED_FAMILY)
        # Advance-ready: the single WP is already approved, so
        # ``_should_advance_wp_step`` returns True and execution reaches the
        # WP-iteration branch's ``_check_cli_guards`` call.
        _seed_wp(feature_dir, "WP01", "approved")

        run_dir = tmp_path / "run"
        run_dir.mkdir(parents=True, exist_ok=True)
        run_ref = rb.MissionRunRef(run_id="run-042", run_dir=str(run_dir), mission_key="042-custom-mission")

        return rb.DecideNextContext(
            agent="agent-x",
            mission_slug="042-custom-mission",
            result="success",
            repo_root=tmp_path,
            feature_dir=feature_dir,
            now="2026-08-22T00:00:00+00:00",
            mission_type=CUSTOM_UNREGISTERED_FAMILY,
            sync_emitter=cast(Any, object()),
            emitter_for_engine=cast(Any, object()),
            origin={"mission_tier": "custom", "mission_path": CUSTOM_UNREGISTERED_FAMILY},
            progress={"total_wps": 1},
            run_ref=run_ref,
            run_dir=run_dir,
            current_step_id="implement",
        )

    def test_wp_iteration_guard_degrades_instead_of_raising(self, tmp_path: Path) -> None:
        """A custom family with no ``_GUARD_TABLES`` entry, current step
        ``implement``, and advance-ready WPs must NOT raise
        ``UnregisteredMissionFamilyError`` out of the WP-iteration branch --
        it degrades to "no guard failures" and falls through (``None``),
        matching how every other custom family is already treated
        everywhere else in the runtime (composition-dispatch's own tolerant
        ``evaluate_guards``)."""
        ctx = self._make_ctx(tmp_path)

        decision = rb._dn_dependency_gate(ctx)

        assert decision is None

    def test_wp_iteration_guard_only_swallows_the_unregistered_family_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Companion negative case: the fix's ``except`` clause is scoped to
        ``UnregisteredMissionFamilyError`` alone -- any other exception
        raised by ``_check_cli_guards`` (a genuinely unexpected failure, not
        the "family not in the guard table" case) must still propagate out
        of ``_dn_dependency_gate`` uncaught."""
        ctx = self._make_ctx(tmp_path)

        def _raise_something_else(*_args: object, **_kwargs: object) -> list[str]:
            raise RuntimeError("unexpected guard evaluation failure")

        monkeypatch.setattr(rb, "_check_cli_guards", _raise_something_else)

        with pytest.raises(RuntimeError, match="unexpected guard evaluation failure"):
            rb._dn_dependency_gate(ctx)


# ---------------------------------------------------------------------------
# WP03 (#3704, FR-003/NFR-004) -- ``repo_root`` call-site convergence.
#
# WP01 (guard predicate) and WP02 (org-tier resolution in
# ``gather_artifact_presence``) are only reachable from a unit test that
# calls the leaf function directly -- NOT from the real
# CLI/WP-iteration/composed-action entry points, all three of which drop
# ``repo_root`` on the floor today even though the enclosing function
# already holds it as a local. These tests pin AC-1/AC-2 (via the
# composed-action guard, org-tier only -- no built-in manifest, so the
# defect is genuinely exercised) and AC-8 (via ``_dn_dependency_gate``'s two
# distinct ``_check_cli_guards`` call sites).
# ---------------------------------------------------------------------------


def _write_org_pack_config(repo_root: Path, *, packs: list[tuple[str, Path]]) -> None:
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    lines = ["charter_packs:", "  org:", "    packs:"]
    for name, local_path in packs:
        lines.append(f"      - name: {name}")
        lines.append(f"        local_path: {local_path}")
    (config_dir / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_org_manifest(org_root: Path, mission_type: str, yaml_text: str) -> None:
    target_dir = org_root / "missions" / mission_type
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "expected-artifacts.yaml").write_text(yaml_text, encoding="utf-8")


_QA_FAMILY = "qa"
_QA_ORG_YAML = """\
schema_version: "1.0"
mission_type: "qa"
manifest_version: "org-1"
required_always: []
required_by_step:
  accept:
    - artifact_key: "output.qa.coverage"
      artifact_class: "output"
      path_pattern: "qa-coverage.json"
      blocking: true
optional_always: []
"""


class TestAC1AC2ComposedActionGuardOrgTierConvergence:
    """AC-1/AC-2: a custom family ``qa`` with ONLY an org-tier manifest
    (deliberately no built-in manifest -- proves the composed-action guard
    genuinely reaches the org tier, not merely "some manifest happened to
    resolve"). Absent -> ``guard_failures`` non-empty and the resulting
    ``Decision.kind`` is ``blocked`` (AC-1); present -> ``guard_failures``
    is empty, provable by flipping presence (AC-2)."""

    def _make_project(self, tmp_path: Path) -> tuple[Path, Path]:
        project_root = tmp_path / "project"
        project_root.mkdir()
        org_root = tmp_path / "org-pack"
        _write_org_manifest(org_root, _QA_FAMILY, _QA_ORG_YAML)
        _write_org_pack_config(project_root, packs=[("acme", org_root)])
        feature_dir = project_root / "kitty-specs" / "042-qa-mission"
        feature_dir.mkdir(parents=True)
        return project_root, feature_dir

    def test_absent_artifact_blocks_via_org_tier(self, tmp_path: Path) -> None:
        project_root, feature_dir = self._make_project(tmp_path)

        failures = _check_composed_action_guard("accept", feature_dir, mission=_QA_FAMILY, repo_root=project_root)

        assert failures != []
        assert any("qa-coverage.json" in failure for failure in failures)

        run_dir = tmp_path / "run"
        run_dir.mkdir(parents=True, exist_ok=True)
        run_ref = MissionRunRef(run_id="run-qa", run_dir=str(run_dir), mission_key="042-qa-mission")
        ctx = rb.DecideNextContext(
            agent="agent-x",
            mission_slug="042-qa-mission",
            result="success",
            repo_root=project_root,
            feature_dir=feature_dir,
            now="2026-08-24T00:00:00+00:00",
            mission_type=_QA_FAMILY,
            sync_emitter=cast(Any, object()),
            emitter_for_engine=cast(Any, object()),
            origin={},
            progress=None,
            run_ref=run_ref,
            run_dir=run_dir,
            current_step_id="accept",
        )

        decision = rb._dn_composition_blocked_decision(ctx, "accept", failures)

        assert decision.kind == DecisionKind.blocked
        assert decision.guard_failures == failures

    def test_present_artifact_passes_via_genuine_evaluation(self, tmp_path: Path) -> None:
        project_root, feature_dir = self._make_project(tmp_path)

        failures_absent = _check_composed_action_guard("accept", feature_dir, mission=_QA_FAMILY, repo_root=project_root)
        assert failures_absent != []

        (feature_dir / "qa-coverage.json").write_text("{}", encoding="utf-8")
        failures_present = _check_composed_action_guard("accept", feature_dir, mission=_QA_FAMILY, repo_root=project_root)

        assert failures_present == []


# ---------------------------------------------------------------------------
# AC-8 -- ``resolve_org_roots`` (via ``resolve_existing_org_roots``, the
# primitive the manifest-loader authority's org-tier resolution calls --
# routed here through ``charter.activation.manifest_loader.load_manifest``,
# not the retired ``_resolve_org_manifest_mapping`` this comment used to
# name, #3847) is invoked with the real, non-``None`` ``repo_root`` the
# enclosing function already holds -- at BOTH of ``_dn_dependency_gate``'s
# two distinct ``_check_cli_guards`` call sites.
# ---------------------------------------------------------------------------

_CUSTOM_ORG_ONLY_FAMILY = "custom-onboarding-mission"
_CUSTOM_ORG_ONLY_YAML = f"""\
schema_version: "1.0"
mission_type: "{_CUSTOM_ORG_ONLY_FAMILY}"
manifest_version: "1"
required_always: []
required_by_step:
  implement:
    - artifact_key: "output.custom.thing"
      artifact_class: "output"
      path_pattern: "custom-thing.md"
      blocking: true
optional_always: []
"""

_SOFTWARE_DEV_ORG_OVERRIDE_YAML = """\
schema_version: "1.0"
mission_type: "software-dev"
manifest_version: "org-override-1"
required_always: []
required_by_step:
  specify:
    - artifact_key: "output.sd.org-extra"
      artifact_class: "output"
      path_pattern: "org-extra-artifact.md"
      blocking: true
optional_always: []
"""


class TestAC8RepoRootThreadedThroughDnDependencyGate:
    def test_wp_iteration_pre_check_threads_real_repo_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """TASKS-VERIFY-001: the WP-iteration pre-check call site
        (~line 1608) is the ONLY one a custom, guard-table-unregistered
        family can structurally reach."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        org_root = tmp_path / "org-pack"
        _write_org_manifest(org_root, _CUSTOM_ORG_ONLY_FAMILY, _CUSTOM_ORG_ONLY_YAML)
        _write_org_pack_config(project_root, packs=[("acme", org_root)])

        feature_dir = project_root / "kitty-specs" / "042-custom-mission"
        _write_meta(feature_dir, _CUSTOM_ORG_ONLY_FAMILY)
        _seed_wp(feature_dir, "WP01", "approved")

        run_dir = tmp_path / "run"
        run_dir.mkdir(parents=True, exist_ok=True)
        run_ref = MissionRunRef(run_id="run-custom", run_dir=str(run_dir), mission_key="042-custom-mission")
        ctx = rb.DecideNextContext(
            agent="agent-x",
            mission_slug="042-custom-mission",
            result="success",
            repo_root=project_root,
            feature_dir=feature_dir,
            now="2026-08-24T00:00:00+00:00",
            mission_type=_CUSTOM_ORG_ONLY_FAMILY,
            sync_emitter=cast(Any, object()),
            emitter_for_engine=cast(Any, object()),
            origin={"mission_tier": "custom", "mission_path": _CUSTOM_ORG_ONLY_FAMILY},
            progress={"total_wps": 1},
            run_ref=run_ref,
            run_dir=run_dir,
            current_step_id="implement",
        )

        # #3847: the org-root resolution this AC exercises now happens
        # exclusively through `charter.activation.manifest_loader`'s cached
        # authority (`_presence_filenames_for` -> `load_manifest`), which
        # lazily imports `resolve_existing_org_roots` directly from its
        # origin module (`charter.offering.drg.org_pack_config`) -- NOT
        # through the `charter.drg` re-export the now-deleted
        # `_resolve_org_manifest_mapping` used to call. Spy on the origin
        # module so the patch is visible to that lazy import.
        from charter.offering.drg import org_pack_config as charter_org_pack_config

        real_resolve_existing_org_roots = charter_org_pack_config.resolve_existing_org_roots
        spy = MagicMock(side_effect=real_resolve_existing_org_roots)
        monkeypatch.setattr(charter_org_pack_config, "resolve_existing_org_roots", spy)

        rb._dn_dependency_gate(ctx)

        assert spy.call_count >= 1
        assert spy.call_args_list[0].args[0] == project_root
        assert project_root is not None

    def test_cli_pre_check_threads_real_repo_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """TASKS-VERIFY-001 fix: the ``software-dev``-scoped CLI pre-check
        call site (~line 1643) is the one a custom family can NEVER reach
        (gated by ``get_mission_type(feature_dir) ==
        MISSION_TYPE_SOFTWARE_DEV``) -- exercised here via a ``software-dev``
        mission at a non-WP-iteration step. Presence-flip is NOT used
        (TASKS-FRESH-001): ``_evaluate_software_dev_guards`` never reads
        ``blocking_artifact_names``, so only the org-tier consult call
        itself -- unconditional inside ``gather_artifact_presence`` -- is
        assertable here."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        org_root = tmp_path / "org-pack"
        _write_org_manifest(org_root, "software-dev", _SOFTWARE_DEV_ORG_OVERRIDE_YAML)
        _write_org_pack_config(project_root, packs=[("acme", org_root)])

        feature_dir = project_root / "kitty-specs" / "042-sd-feature"
        _write_meta(feature_dir, "software-dev")
        (feature_dir / "spec.md").write_text("# spec\n", encoding="utf-8")

        run_dir = tmp_path / "run"
        run_dir.mkdir(parents=True, exist_ok=True)
        run_ref = MissionRunRef(run_id="run-sd", run_dir=str(run_dir), mission_key="042-sd-feature")
        ctx = rb.DecideNextContext(
            agent="agent-x",
            mission_slug="042-sd-feature",
            result="success",
            repo_root=project_root,
            feature_dir=feature_dir,
            now="2026-08-24T00:00:00+00:00",
            mission_type="software-dev",
            sync_emitter=cast(Any, object()),
            emitter_for_engine=cast(Any, object()),
            origin={},
            progress=None,
            run_ref=run_ref,
            run_dir=run_dir,
            current_step_id="specify",
        )

        # #3847: the org-root resolution this AC exercises now happens
        # exclusively through `charter.activation.manifest_loader`'s cached
        # authority (`_presence_filenames_for` -> `load_manifest`), which
        # lazily imports `resolve_existing_org_roots` directly from its
        # origin module (`charter.offering.drg.org_pack_config`) -- NOT
        # through the `charter.drg` re-export the now-deleted
        # `_resolve_org_manifest_mapping` used to call. Spy on the origin
        # module so the patch is visible to that lazy import.
        from charter.offering.drg import org_pack_config as charter_org_pack_config

        real_resolve_existing_org_roots = charter_org_pack_config.resolve_existing_org_roots
        spy = MagicMock(side_effect=real_resolve_existing_org_roots)
        monkeypatch.setattr(charter_org_pack_config, "resolve_existing_org_roots", spy)

        rb._dn_dependency_gate(ctx)

        assert spy.call_count >= 1
        assert spy.call_args_list[0].args[0] == project_root
