"""WP01 (mission runtime-advance-guard-topology-wp-completion-01M1W6VZ, issue
#3884): coord-topology end-to-end reproduction (FR-004+FR-009 together), the
FR-010 raise-and-catch reproduction, and the no-op regression pins.

Reuses WP02's real coord-topology fixture builder
(``tests.runtime.next.test_coord_topology_fixture.build_coord_topology_fixture``)
rather than rebuilding an equivalent one -- a plain dotted cross-test-module
import, following this repo's own precedent
(``tests/agent/test_finalize_tasks_owned_files_validation.py`` already imports
from ``tests.tasks.test_finalize_tasks_owned_files_validation`` the same way).

See ``kitty-specs/runtime-advance-guard-topology-wp-completion-01M1W6VZ/plan.md``'s
Test Strategy items 2/3/4 for the reasoning this file implements (cited, not
re-derived).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest

from runtime.next import runtime_bridge as rb
from runtime.next._internal_runtime import MissionRunRef
from runtime.next.decision import DecisionKind
from tests.runtime.next.test_coord_topology_fixture import build_coord_topology_fixture
from runtime.next import runtime_bridge_guards as bridge_guards

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo_root, check=True, capture_output=True)


# ---------------------------------------------------------------------------
# T010 -- coord-topology end-to-end reproduction (FR-004+FR-009 TOGETHER)
# ---------------------------------------------------------------------------


class TestT010CoordReachabilityJointFix:
    """Proves FR-004's fix genuinely fires for the production scenario this
    mission exists to fix -- not just at the ``_wp_blocks_step`` unit level
    (T007 alone is necessary but not sufficient proof), and not only in
    isolation as WP02's own T003 proved FR-009 alone (that reproduction
    deliberately used an ``in_progress`` WP to avoid conflating the two bugs
    -- this one deliberately uses an uninitialized WP, WP02's builder
    default, to prove they resolve TOGETHER for the real #3884 scenario)."""

    def test_anchored_coord_call_blocks_for_never_claimed_wp(self, tmp_path: Path) -> None:
        fixture = build_coord_topology_fixture(tmp_path)  # default wp_events=None -> UNINITIALIZED

        result = bridge_guards._should_advance_wp_step(
            "implement",
            fixture.coord_feature_dir,
            repo_root=fixture.repo_root,
            mission_slug=fixture.mission_slug,
        )

        assert result is False, (
            "the coord-anchored call must block advancement for a never-claimed "
            "WP -- this requires BOTH T006 (the Lane.UNINITIALIZED disjunct) AND "
            "T008 (the anchoring extension); reverting either one alone makes "
            "this assertion fail (see TestT010JointFixIsolation below)"
        )

    def test_primary_dir_call_agrees_with_the_coord_anchored_answer(self, tmp_path: Path) -> None:
        """The parallel primary-dir call needs no anchoring keywords (it is
        already the primary checkout) and must agree with the coord-anchored
        answer above."""
        fixture = build_coord_topology_fixture(tmp_path)

        result = bridge_guards._should_advance_wp_step("implement", fixture.primary_dir)

        assert result is False


class TestT010JointFixIsolation:
    """Explicit proof (Definition of Done: "T010's coord-topology
    reproduction fails if either T006 or T008 alone is reverted") that the
    two fixes are genuinely joint, not merely coincidentally both present --
    demonstrated here by re-deriving each half's own necessity directly
    rather than only asserting the combined green result above.

    - Without T008's anchoring (call the un-anchored 2-arg signature against
      the SAME coord fixture): the early no-``tasks/``-dir return fires
      before the per-WP loop is ever reached, so the call wrongly returns
      True regardless of whether T006's disjunct exists. This is WP02's own
      T003 reproduction, re-asserted here against the uninitialized-WP
      variant to show the anchoring gap is not specific to the in_progress
      lane WP02 used.
    - Without T006's disjunct (direct ``_wp_blocks_step`` call against an
      ``UninitializedState``, independent of anchoring): NOT proven by a
      standing automated test. ``test_advance_guard_uninitialized_wp.py``'s
      ``TestT007DirectCallReproduction`` only asserts the CURRENT (post-fix)
      ``True`` result against today's fixed code -- it never reverts the
      disjunct, so it cannot by itself demonstrate necessity. The genuine
      single-revert probe for this half (reverting the disjunct alone makes
      the coord-topology assertion fail) was done by hand by WP01's
      reviewer during review and is recorded in
      ``tracer-design-decisions.md``'s "Joint-fix proof: neither disjunct is
      redundant" entry, not automated in the shipped suite.
    """

    def test_unanchored_call_against_the_same_coord_fixture_wrongly_permits(self, tmp_path: Path) -> None:
        fixture = build_coord_topology_fixture(tmp_path)

        result = bridge_guards._should_advance_wp_step("implement", fixture.coord_feature_dir)

        assert result is True, (
            "isolation check: WITHOUT T008's anchoring, the unanchored 2-arg "
            "call against the coord feature_dir wrongly permits advancement "
            "even for a never-claimed WP -- proving T008 alone is necessary, "
            "and (paired with TestT010CoordReachabilityJointFix's GREEN result) "
            "that T006+T008 together are what make the guard both reachable "
            "and correct"
        )


# ---------------------------------------------------------------------------
# T011 -- FR-010 raise-and-catch reproduction
# ---------------------------------------------------------------------------


def _build_ambiguous_slug_fixture(tmp_path: Path) -> tuple[Path, str]:
    """Two real mission directories under ``kitty-specs/`` sharing a common
    human-slug prefix, so a bare ``mission_slug`` handle matching that prefix
    non-uniquely makes
    ``placement_seam(repo_root, mission_slug).read_dir(WORK_PACKAGE_TASK)``
    raise ``MissionSelectorAmbiguous`` for REAL (never a monkeypatch) --
    verified directly against this exact fixture shape during T011's spike
    before wiring it into the full ``_dn_dependency_gate`` call below.

    Priority-4 human-slug ambiguity (``specify_cli.context.mission_resolver``):
    ``001-ambiguous-repro`` and ``002-ambiguous-repro`` both strip their
    numeric prefix to the bare human slug ``ambiguous-repro`` -- neither
    directory NAME equals that bare slug (ruling out the Priority-3 exact-slug
    match), so the handle resolves via Priority 4 and matches both.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-q", "-b", "main")
    _git(repo_root, "config", "user.email", "wp01-fixture@spec-kitty.test")
    _git(repo_root, "config", "user.name", "WP01 Fixture")
    _git(repo_root, "config", "commit.gpgsign", "false")
    (repo_root / ".kittify").mkdir()
    (repo_root / ".kittify" / "config.yaml").write_text("agents:\n  available:\n    - claude\n", encoding="utf-8")

    specs_dir = repo_root / "kitty-specs"
    specs_dir.mkdir()
    ambiguous_slug = "ambiguous-repro"
    for suffix, mid in (
        ("001", "01AMBIGUOUSMISSIONONEXXXX"),
        ("002", "01AMBIGUOUSMISSIONTWOXXXX"),
    ):
        mission_dir = specs_dir / f"{suffix}-{ambiguous_slug}"
        mission_dir.mkdir()
        (mission_dir / "meta.json").write_text(
            json.dumps(
                {
                    "mission_id": mid,
                    "mission_slug": f"{suffix}-{ambiguous_slug}",
                    "mission_type": "software-dev",
                    "topology": "single_branch",
                }
            ),
            encoding="utf-8",
        )

    _git(repo_root, "add", ".")
    _git(repo_root, "commit", "-q", "-m", "WP01 fixture: ambiguous-slug repro")

    return repo_root, ambiguous_slug


class TestT011Fr010RaiseAndCatch:
    def test_placement_seam_raises_for_real_on_the_ambiguous_fixture(self, tmp_path: Path) -> None:
        """Isolation check (per this WP's own step 1): confirm the raise
        happens directly, in isolation, before wiring it into the full
        ``_dn_dependency_gate`` call below."""
        from mission_runtime import MissionArtifactKind, placement_seam
        from specify_cli.missions._read_path_resolver import MissionSelectorAmbiguous

        repo_root, ambiguous_slug = _build_ambiguous_slug_fixture(tmp_path)

        with pytest.raises(MissionSelectorAmbiguous):
            placement_seam(repo_root, ambiguous_slug).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)

    def test_dn_dependency_gate_converts_the_raise_to_a_blocked_decision(self, tmp_path: Path) -> None:
        """RED (uncaught MissionSelectorAmbiguous propagates) before T009's
        except arm lands, GREEN after -- construction follows
        ``test_cli_guard_family.py``'s
        ``test_cli_pre_check_threads_real_repo_root`` pattern for
        ``DecideNextContext``."""
        repo_root, ambiguous_slug = _build_ambiguous_slug_fixture(tmp_path)
        # The coord-shaped feature_dir this call receives need not exist on
        # disk -- the raise fires during mission_slug canonicalization, before
        # any tasks_dir.is_dir() check against feature_dir itself.
        feature_dir = repo_root / "kitty-specs" / f"001-{ambiguous_slug}"

        run_dir = tmp_path / "run"
        run_dir.mkdir(parents=True, exist_ok=True)
        run_ref = MissionRunRef(run_id="run-ambiguous", run_dir=str(run_dir), mission_key=ambiguous_slug)
        ctx = rb.DecideNextContext(
            agent="agent-x",
            mission_slug=ambiguous_slug,
            result="success",
            repo_root=repo_root,
            feature_dir=feature_dir,
            now="2026-09-07T00:00:00+00:00",
            mission_type="software-dev",
            sync_emitter=cast(Any, object()),
            emitter_for_engine=cast(Any, object()),
            origin={},
            progress=None,
            run_ref=run_ref,
            run_dir=run_dir,
            current_step_id="implement",
        )

        decision = rb._dn_dependency_gate(ctx)

        assert decision is not None
        assert decision.kind == DecisionKind.blocked
        assert decision.reason is not None
        assert "ambiguous-repro" in decision.reason
        assert "matches multiple missions" in decision.reason


# ---------------------------------------------------------------------------
# T012 -- no-op regression pins
# ---------------------------------------------------------------------------


class TestT012NoOpRegressionPins:
    def test_single_branch_topology_anchored_call_is_a_no_op(self, tmp_path: Path) -> None:
        """This mission's own checkout IS ``single_branch`` topology -- a
        live dogfood fixture, not a synthetic one. Anchoring resolves to the
        SAME directory ``feature_dir`` already denotes for a PRIMARY-partition
        kind, for every topology (per ``PlacementSeam.read_dir``'s own
        contract), so the anchored and un-anchored answers must agree."""
        this_repo_root = Path(__file__).resolve().parents[3]
        this_feature_dir = this_repo_root / "kitty-specs" / "runtime-advance-guard-topology-wp-completion-01M1W6VZ"
        assert (this_feature_dir / "tasks").is_dir()

        unanchored = bridge_guards._should_advance_wp_step("implement", this_feature_dir)
        anchored = bridge_guards._should_advance_wp_step(
            "implement",
            this_feature_dir,
            repo_root=this_repo_root,
            mission_slug=this_feature_dir.name,
        )

        assert anchored == unanchored

    def test_anchored_no_tasks_dir_case_still_advances(self, tmp_path: Path) -> None:
        """Parallel assertion for the legitimate no-``tasks/``-dir case (a
        ``plan``-family-shaped fixture, or any fixture with genuinely no
        ``tasks/`` directory on primary) with ``repo_root`` set -- the
        "anchored" completion of AC-3, which the un-anchored pin in
        ``test_advance_guard_uninitialized_wp.py`` left deliberately
        incomplete."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        _git(repo_root, "init", "-q", "-b", "main")
        _git(repo_root, "config", "user.email", "wp01-fixture@spec-kitty.test")
        _git(repo_root, "config", "user.name", "WP01 Fixture")
        _git(repo_root, "config", "commit.gpgsign", "false")
        (repo_root / ".kittify").mkdir()
        (repo_root / ".kittify" / "config.yaml").write_text("agents:\n  available:\n    - claude\n", encoding="utf-8")

        mission_slug = "plan-family-no-tasks"
        feature_dir = repo_root / "kitty-specs" / mission_slug
        feature_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text(
            json.dumps(
                {
                    "mission_id": "01PLANFAMILYNOTASKSXXXXXX",
                    "mission_slug": mission_slug,
                    "mission_type": "plan",
                    "topology": "single_branch",
                }
            ),
            encoding="utf-8",
        )
        assert not (feature_dir / "tasks").is_dir()

        _git(repo_root, "add", ".")
        _git(repo_root, "commit", "-q", "-m", "WP01 fixture: no-tasks/-dir plan mission")

        result = bridge_guards._should_advance_wp_step(
            "implement",
            feature_dir,
            repo_root=repo_root,
            mission_slug=mission_slug,
        )

        assert result is True


class TestAnchoringRequiresExplicitMissionSlug:
    """Landing fold (#3981): anchoring (``repo_root=``) must be given an explicit
    ``mission_slug``. The removed silent ``feature_dir.name`` fallback would feed
    a non-handle (a coord-worktree / status dir name) into ``placement_seam``;
    fail closed instead, consistent with the function's no-silent-fallback stance
    on ``MissionSelectorAmbiguous`` (C-009)."""

    def test_repo_root_without_mission_slug_fails_closed(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="mission_slug is required when repo_root"):
            bridge_guards._should_advance_wp_step("implement", tmp_path, repo_root=tmp_path)

    def test_unanchored_call_is_unaffected(self, tmp_path: Path) -> None:
        # No repo_root -> no anchoring -> no raise (an empty dir has no tasks/).
        assert bridge_guards._should_advance_wp_step("implement", tmp_path) is True


class TestCompositionPhaseNeverSeesPendingWp:
    """Landing fold (#3981): reachability tripwire for the two DELIBERATELY
    unanchored `_should_advance_wp_step` call sites (`_check_cli_guards` and
    `_check_composed_action_guard`). Their safety rests on a prose invariant:
    they run only AFTER `_dn_dependency_gate` (the anchored phase) already
    short-circuited for a pending WP. The phase loop in `decide_next_via_runtime`
    (`for phase in (_dn_dependency_gate, _dn_composition_dispatch, ...)`) runs
    `_dn_composition_dispatch` only when `_dn_dependency_gate` returns None, so
    this pins that a pending (never-claimed / uninitialized) WP on a real
    coord-topology fixture makes the anchored gate return a non-None WP-level
    decision — the composition phase never evaluates its unanchored recompute on
    a pending WP.

    Reds if the FR-009 anchoring regresses (the coord gate would return None and
    let composition run) OR if the gate is changed to stop short-circuiting on a
    pending WP — the exact phase-reorder the two comments warn about.
    """

    def test_dn_dependency_gate_short_circuits_before_composition_for_pending_wp(self, tmp_path: Path) -> None:
        fixture = build_coord_topology_fixture(tmp_path)  # default -> UNINITIALIZED WP

        run_dir = tmp_path / "run"
        run_dir.mkdir(parents=True, exist_ok=True)
        run_ref = MissionRunRef(run_id="run-pending", run_dir=str(run_dir), mission_key=fixture.mission_slug)
        ctx = rb.DecideNextContext(
            agent="agent-x",
            mission_slug=fixture.mission_slug,
            result="success",
            repo_root=fixture.repo_root,
            feature_dir=fixture.coord_feature_dir,
            now="2026-09-07T00:00:00+00:00",
            mission_type="software-dev",
            sync_emitter=cast(Any, object()),
            emitter_for_engine=cast(Any, object()),
            origin={},
            progress=None,
            run_ref=run_ref,
            run_dir=run_dir,
            current_step_id="implement",
        )

        decision = rb._dn_dependency_gate(ctx)

        # Non-None => the phase loop short-circuits here; _dn_composition_dispatch
        # (phase 3) never runs, so its unanchored _should_advance_wp_step recompute
        # never evaluates this pending WP. This is the WP-iteration branch, so the
        # decision is a WP-level outcome (step or blocked), never an advance past
        # implement (which would be composition/materialize's job).
        assert decision is not None
        assert decision.kind in (DecisionKind.step, DecisionKind.blocked)
