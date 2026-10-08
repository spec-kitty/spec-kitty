"""Red-first runtime acceptance for the owned-checkout ``next`` control loop.

Mission ``owned-checkout-lifecycle-authority-01M3M2ZB``, WP11 (T057).

Proves the FR-007/008/009/012/023 rows at the **runtime entry points**
(``decision.decide_next`` / ``runtime_bridge.decide_next_via_runtime`` /
``runtime_bridge.query_current_state``), with facts minted by the real
validator (:func:`resolve_owned_mission`) — never constructed directly.

On the pre-WP11 base every ``owned=`` call below is red with ``TypeError:
decide_next_via_runtime() got an unexpected keyword argument 'owned'`` (or
the analogous error for ``query_current_state``); the two #4867 injections
are additionally red because ``_has_stale_worktree_registration`` raises an
uncaught ``CalledProcessError`` there (``DecisionGitLogUnavailable`` on the
base, never a typed ``OwnedRefusalCode``).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from mission_runtime import MissionTopology, OwnedCheckout, OwnedRefusalCode
from specify_cli.cli.commands.agent.mission import app as mission_app
from specify_cli.core.owned_mission import NEXT_OWNED_TOPOLOGIES, resolve_owned_mission
from tests._factories import provision_test_charter
from tests.integration.conftest import OwnedCheckouts
from tests.runtime._next_mission_scaffold import advance_to_step, seed_wp_lane
from runtime.next import runtime_bridge_decision_mapping as decision_mapping

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()


def _provision_charter(checkouts: OwnedCheckouts) -> None:
    """Seed activated mission types on BOTH R and P.

    ``resolve_mission_type_context`` reads ``.kittify/config.yaml`` from the
    OWNED root for an owned call (root discipline) but some non-owned-aware
    residual reads may still anchor on R; provisioning both keeps this test
    robust to either.
    """
    provision_test_charter(checkouts.repository_root)
    provision_test_charter(checkouts.owned_root)


def _write_finalizable_tasks_md(checkouts: OwnedCheckouts, wp_ids: tuple[str, ...] = ("WP01", "WP02")) -> None:
    """Rewrite ``tasks.md`` with section headers ``finalize-tasks`` can match
    against P's ``tasks/WP*.md`` files (the shared fixture's own generic
    ``tasks.md`` has none), fix each WP file's ``owned_files: []`` (a
    ``code_change`` WP with no owned files is an authoring contradiction
    ``finalize-tasks`` refuses), and commit the change into P."""
    lines = ["# Tasks", ""]
    for wp_id in wp_ids:
        lines.append(f"## Work Package {wp_id}")
        lines.append("")
        lines.append("**Dependencies**: None")
        lines.append("")
        wp_file = checkouts.mission_dir / "tasks" / f"{wp_id}-owned.md"
        surface = f"{wp_id.lower()}.py"
        content = wp_file.read_text(encoding="utf-8")
        content = content.replace("owned_files: []", f"owned_files: [{surface}]")
        content = content.replace("authoritative_surface: app.py", f"authoritative_surface: {surface}")
        wp_file.write_text(content, encoding="utf-8")
        (checkouts.owned_root / surface).write_text(f"# {wp_id}\n", encoding="utf-8")
    (checkouts.mission_dir / "tasks.md").write_text("\n".join(lines), encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=checkouts.owned_root, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-qm", "finalizable tasks.md"],
        cwd=checkouts.owned_root,
        check=True,
        capture_output=True,
    )


def _finalize(checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
    """Finalize P's task board through the real CLI command.

    ``finalize-tasks --owned-checkout`` validates against
    ``LIFECYCLE_OWNED_TOPOLOGIES`` (``single_branch`` only) regardless of
    what ``next`` itself accepts (``NEXT_OWNED_TOPOLOGIES`` — WP02/FR-023) —
    a pre-existing CLI-surface restriction this WP does not own or widen.
    Callers finalizing a wider-topology fixture skip this and rely on the
    documented pre-finalize board decline instead (FR-006).
    """
    _write_finalizable_tasks_md(checkouts)
    monkeypatch.chdir(checkouts.owned_root)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(checkouts.owned_root))
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")
    result = runner.invoke(
        mission_app,
        [
            "finalize-tasks",
            "--mission",
            checkouts.mission_slug,
            "--owned-checkout",
            str(checkouts.owned_root),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output


def _mint(checkouts: OwnedCheckouts, *, allowed_topologies: frozenset[MissionTopology] = NEXT_OWNED_TOPOLOGIES) -> OwnedCheckout:
    """Mint the fact with the REAL validator — never construct ``OwnedCheckout`` directly."""
    return resolve_owned_mission(
        checkouts.repository_root,
        checkouts.owned_root,
        checkouts.mission_slug,
        allowed_topologies=allowed_topologies,
    )


class TestFr023RuntimeTwin:
    """FR-023: a ``lanes_with_coord`` owned fact is accepted by the runtime
    (``NEXT_OWNED_TOPOLOGIES``), and the runtime decision is non-error."""

    def test_lanes_with_coord_query_current_state_non_error(
        self,
        make_owned_checkouts,
        make_r_snapshot,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from runtime.next.runtime_bridge import query_current_state

        checkouts = make_owned_checkouts(topology="lanes_with_coord")
        _provision_charter(checkouts)
        # Not finalized: `finalize-tasks --owned-checkout` only accepts
        # `LIFECYCLE_OWNED_TOPOLOGIES` (single_branch); this row exercises
        # the pre-finalize board decline for a wider next-only topology
        # (FR-006), which needs no finalized board.
        snap = make_r_snapshot(checkouts)
        before = snap.take()

        fact = _mint(checkouts, allowed_topologies=NEXT_OWNED_TOPOLOGIES)

        # Red on the base only because `owned=` is not accepted there. (The
        # legacy `effective_root=` control that proved the scenario sound was
        # retired together with the keyword by WP18.)
        decision = query_current_state(
            "claude",
            checkouts.mission_slug,
            checkouts.repository_root,
            owned=fact,
        )
        assert decision.kind in ("query",)
        assert decision.mission_slug == checkouts.mission_slug

        snap.assert_unchanged(before, snap.take())


class TestFr007StaleRootCopyBoard:
    """FR-007: with a stale copy of M in R, the runtime never consults R --
    driven through ``decide_next`` (review cycle 1 finding 8), asserted
    unconditionally, and the WP set is P's (two WPs), not R's stale five."""

    def test_stale_root_copy_never_consulted(
        self,
        owned_checkouts,
        stale_root_copy,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Uses the bound ``owned_checkouts`` fixture (not
        ``make_owned_checkouts``) because ``stale_root_copy`` already depends
        on it under the SAME ``tmp_path``."""
        from runtime.next import decision as decision_mod

        checkouts = owned_checkouts
        fact = _walk_to_tasks(checkouts, monkeypatch)
        stale_root_copy()  # R now holds a DIFFERENT WP set / lane map for the same mission
        snap = _r_snapshot(checkouts)
        before = snap.take()

        decision = decision_mod.decide_next("claude", checkouts.mission_slug, "success", checkouts.repository_root, owned=fact)

        _assert_issues_implement_wp01_in_p(decision, fact)
        assert decision.mission_slug == checkouts.mission_slug
        assert decision.workspace_path is not None
        workspace = Path(decision.workspace_path).resolve()
        repository_root = checkouts.repository_root.resolve()
        if not fact.owned_root.resolve().is_relative_to(repository_root):
            assert not workspace.is_relative_to(repository_root)
        assert decision.progress is not None
        assert decision.progress["total_wps"] == 2, "the WP set must be P's (WP01-WP02), not R's stale WP01-WP05"

        snap.assert_unchanged(before, snap.take(), tolerate_status_mutex_for=checkouts.mission_slug)


def _coord_owned_with_removed_worktree(make_owned_checkouts) -> tuple[OwnedCheckouts, OwnedCheckout]:
    """An owned ``lanes_with_coord`` mission whose coordination branch EXISTS
    and whose coordination worktree was materialized and then removed from
    disk (T057 step 5(a)), so that a no-injection ``decide_next`` re-creates
    it and is non-blocked -- every injection below is the ONLY difference
    from that control (review cycle 1 finding 7)."""
    import shutil

    from specify_cli.coordination.workspace import CoordinationWorkspace

    checkouts = make_owned_checkouts(topology="lanes_with_coord")
    _provision_charter(checkouts)
    repo_root = checkouts.repository_root
    branch = CoordinationWorkspace.branch_name(checkouts.mission_slug, checkouts.mid8)
    subprocess.run(["git", "-C", str(repo_root), "branch", branch, "HEAD"], check=True, capture_output=True)
    coord_path = CoordinationWorkspace.resolve(repo_root, checkouts.mission_slug, checkouts.mid8)
    shutil.rmtree(coord_path)
    assert not coord_path.exists()
    return checkouts, _mint(checkouts)


def _coord_owned_never_materialized(make_owned_checkouts) -> tuple[OwnedCheckouts, OwnedCheckout]:
    """An owned ``lanes_with_coord`` mission whose coordination branch exists
    but whose coordination worktree was NEVER created: nothing is registered
    with git, so a no-injection ``decide_next`` materializes it cleanly and
    each single-seam injection below is the ONLY thing that can fail it."""
    from specify_cli.coordination.workspace import CoordinationWorkspace

    checkouts = make_owned_checkouts(topology="lanes_with_coord")
    _provision_charter(checkouts)
    branch = CoordinationWorkspace.branch_name(checkouts.mission_slug, checkouts.mid8)
    subprocess.run(["git", "-C", str(checkouts.repository_root), "branch", branch, "HEAD"], check=True, capture_output=True)
    return checkouts, _mint(checkouts)


def _inject_git_worktree_failure(monkeypatch: pytest.MonkeyPatch, subcommand: str) -> None:
    """Make ``git worktree <subcommand>`` exit 128 through the workspace
    module's subprocess seam, and nothing else."""
    from specify_cli.coordination import workspace as workspace_mod

    real_run = workspace_mod.subprocess.run

    def _fake_run(argv: list[str], *args: Any, **kwargs: Any) -> Any:
        if "worktree" in argv and subcommand in argv:
            return subprocess.CompletedProcess(argv, 128, stdout="", stderr=f"fatal: injected worktree-{subcommand} failure\n")
        return real_run(argv, *args, **kwargs)

    monkeypatch.setattr(workspace_mod.subprocess, "run", _fake_run)


def _truncate_a_sibling_commondir(repo_root: Path, tmp_path: Path) -> tuple[Path, bytes]:
    """Register a sibling worktree and truncate its ``commondir`` to zero
    bytes; pre-asserts git itself now fails (R-16), never skips.

    A zero-byte ``commondir`` is exactly what a sibling's in-flight ``git
    worktree add`` leaves for an instant (git writes it last, truncate then
    write; #5894). Returns the file and its original bytes so a test can play
    the sibling finishing its ``add``."""
    sibling_worktree = tmp_path / "sibling-registered-worktree"
    subprocess.run(["git", "-C", str(repo_root), "worktree", "add", "-q", "--detach", str(sibling_worktree)], check=True)
    git_dir = Path((sibling_worktree / ".git").read_text(encoding="utf-8").removeprefix("gitdir:").strip())
    commondir = git_dir / "commondir"
    original = commondir.read_bytes()
    commondir.write_bytes(b"")
    probe = subprocess.run(["git", "-C", str(repo_root), "worktree", "list", "--porcelain"], capture_output=True, text=True)
    if probe.returncode == 0:
        pytest.fail("git tolerated a zero-byte commondir with exit 0 -- the injection did not reproduce; refusing to skip (R-16).")
    return commondir, original


def _count_retry_sleeps(monkeypatch: pytest.MonkeyPatch, on_sleep: Any = None) -> list[float]:
    """Replace the bounded retry's back-off with a recorder (no wall-clock
    wait); ``on_sleep`` runs on each back-off, standing in for the sibling."""
    import time

    # Patching ``time.sleep`` module-wide reaches the bridge because it
    # imports ``time`` inside the retry function, not at module scope.
    sleeps: list[float] = []

    def _sleep(seconds: float) -> None:
        sleeps.append(seconds)
        if on_sleep is not None:
            on_sleep()

    monkeypatch.setattr(time, "sleep", _sleep)
    return sleeps


class TestO8CoordinationWorkspaceUnavailable:
    """#4867 / FR-012 / O8: a failing coordination-workspace probe produces a
    ``blocked`` decision with
    ``error_code == OwnedRefusalCode.OWNED_COORDINATION_WORKSPACE_UNAVAILABLE``,
    never a ``commondir`` fatal escaping as ``DecisionGitLogUnavailable``.
    The fixture has the coordination branch, so the no-injection control
    materializes and is NOT blocked with that code."""

    def test_control_without_injection_is_not_the_typed_refusal(self, make_owned_checkouts) -> None:
        from runtime.next import decision as decision_mod

        checkouts, fact = _coord_owned_with_removed_worktree(make_owned_checkouts)

        decision = decision_mod.decide_next("claude", checkouts.mission_slug, "success", checkouts.repository_root, owned=fact)

        assert decision.error_code != OwnedRefusalCode.OWNED_COORDINATION_WORKSPACE_UNAVAILABLE.value, (decision.kind, decision.reason)

    def test_zero_byte_commondir_returns_typed_refusal(self, make_owned_checkouts, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A ``commondir`` that STAYS empty through the whole bounded retry
        window is still refused, and the refusal carries git's own diagnostic."""
        from runtime.next import decision as decision_mod

        checkouts, fact = _coord_owned_with_removed_worktree(make_owned_checkouts)
        _truncate_a_sibling_commondir(checkouts.repository_root, tmp_path)
        sleeps = _count_retry_sleeps(monkeypatch)

        decision = decision_mod.decide_next("claude", checkouts.mission_slug, "success", checkouts.repository_root, owned=fact)

        assert decision.kind == "blocked"
        assert decision.error_code == OwnedRefusalCode.OWNED_COORDINATION_WORKSPACE_UNAVAILABLE.value
        assert sleeps, "the in-flight sibling diagnostic was refused without a single retry (#5894)"
        assert "commondir" in (decision.reason or ""), decision.reason

    def test_sibling_add_finishing_inside_the_retry_window_is_not_refused(self, make_owned_checkouts, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """#5894 (nightly run 37723696665): a sibling's in-flight ``git
        worktree add`` leaves a zero-byte ``commondir`` for an instant. When
        the sibling finishes while this process backs off, the coordination
        worktree materializes; the instant is never a durable refusal."""
        from runtime.next import decision as decision_mod

        checkouts, fact = _coord_owned_with_removed_worktree(make_owned_checkouts)
        commondir, original = _truncate_a_sibling_commondir(checkouts.repository_root, tmp_path)
        sleeps = _count_retry_sleeps(monkeypatch, on_sleep=lambda: commondir.write_bytes(original))

        decision = decision_mod.decide_next("claude", checkouts.mission_slug, "success", checkouts.repository_root, owned=fact)

        assert decision.error_code != OwnedRefusalCode.OWNED_COORDINATION_WORKSPACE_UNAVAILABLE.value, (decision.kind, decision.reason)
        assert sleeps, "the control injection never reached the retry (the race was not exercised)"

    def test_subprocess_seam_failure_returns_typed_refusal(self, make_owned_checkouts, monkeypatch: pytest.MonkeyPatch) -> None:
        from runtime.next import decision as decision_mod
        from specify_cli.coordination import workspace as workspace_mod

        checkouts, fact = _coord_owned_with_removed_worktree(make_owned_checkouts)
        real_run = workspace_mod.subprocess.run

        def _fake_run(argv: list[str], *args: Any, **kwargs: Any) -> Any:
            if "worktree" in argv and "list" in argv:
                return subprocess.CompletedProcess(argv, 128, stdout="", stderr="fatal: injected worktree-list failure\n")
            return real_run(argv, *args, **kwargs)

        monkeypatch.setattr(workspace_mod.subprocess, "run", _fake_run)

        decision = decision_mod.decide_next("claude", checkouts.mission_slug, "success", checkouts.repository_root, owned=fact)

        assert decision.kind == "blocked"
        assert decision.error_code == OwnedRefusalCode.OWNED_COORDINATION_WORKSPACE_UNAVAILABLE.value

    def test_control_never_materialized_worktree_is_not_the_typed_refusal(self, make_owned_checkouts) -> None:
        from runtime.next import decision as decision_mod

        checkouts, fact = _coord_owned_never_materialized(make_owned_checkouts)

        decision = decision_mod.decide_next("claude", checkouts.mission_slug, "success", checkouts.repository_root, owned=fact)

        assert decision.error_code != OwnedRefusalCode.OWNED_COORDINATION_WORKSPACE_UNAVAILABLE.value, (decision.kind, decision.reason)

    @pytest.mark.parametrize("subcommand", ["list", "add"])
    def test_each_worktree_seam_failing_alone_returns_the_typed_refusal(self, make_owned_checkouts, monkeypatch: pytest.MonkeyPatch, subcommand: str) -> None:
        """The registry probe (``worktree list``) and the materialization
        (``worktree add``) are two distinct raise sites; on a never-created
        worktree each one, failing alone, is the only possible cause."""
        from runtime.next import decision as decision_mod

        checkouts, fact = _coord_owned_never_materialized(make_owned_checkouts)
        _inject_git_worktree_failure(monkeypatch, subcommand)

        decision = decision_mod.decide_next("claude", checkouts.mission_slug, "success", checkouts.repository_root, owned=fact)

        assert decision.kind == "blocked"
        assert decision.error_code == OwnedRefusalCode.OWNED_COORDINATION_WORKSPACE_UNAVAILABLE.value

    def test_wp04_unmaterialized_surface_refusal_is_also_the_typed_blocked_decision(self, make_owned_checkouts, monkeypatch: pytest.MonkeyPatch) -> None:
        """WP04's ``ActionContextError(OWNED_COORDINATION_WORKSPACE_UNAVAILABLE)``
        (an unmaterialized surface read) maps to the same ``blocked`` decision
        as the registry probe's :class:`CoordinationWorkspaceUnavailable`."""
        import mission_runtime
        from mission_runtime import ActionContextError
        from runtime.next import decision as decision_mod

        checkouts, fact = _coord_owned_with_removed_worktree(make_owned_checkouts)
        real = mission_runtime.mission_context_for

        def _refuses(*args: Any, **kwargs: Any) -> Any:
            if kwargs.get("owned") is not None:
                raise ActionContextError(OwnedRefusalCode.OWNED_COORDINATION_WORKSPACE_UNAVAILABLE.value, "coordination surface not materialized")
            return real(*args, **kwargs)

        monkeypatch.setattr(mission_runtime, "mission_context_for", _refuses)

        decision = decision_mod.decide_next("claude", checkouts.mission_slug, "success", checkouts.repository_root, owned=fact)

        assert decision.kind == "blocked"
        assert decision.error_code == OwnedRefusalCode.OWNED_COORDINATION_WORKSPACE_UNAVAILABLE.value


def _requested_payload() -> Any:
    from spec_kitty_events.mission_next import DecisionInputRequestedPayload, RuntimeActorIdentity

    return DecisionInputRequestedPayload(
        run_id="run-001",
        decision_id="dec-001",
        step_id="specify",
        question="Which approach?",
        options=("A", "B"),
        actor=RuntimeActorIdentity(actor_id="test-agent", actor_type="llm"),
    )


class TestOwnedDecisionGitLogAnchor:
    """T060 step 4 / NFR-001 (review cycle 1 finding 6): an owned mission's
    ``DecisionGitLog`` is anchored on the owned checkout P (coord-less) or on
    the coordination worktree under R (coord-routing) -- never on R."""

    def test_coordless_owned_anchors_at_p_and_never_writes_r(self, make_owned_checkouts, make_r_snapshot) -> None:
        from runtime.next._internal_runtime.events import NullEmitter
        from runtime.next.runtime_bridge_decision_log import _wrap_with_decision_git_log

        checkouts = make_owned_checkouts(topology="single_branch")
        _provision_charter(checkouts)
        fact = _mint(checkouts)
        snap = make_r_snapshot(checkouts)
        before = snap.take()

        wrapped = _wrap_with_decision_git_log(NullEmitter(), checkouts.mission_slug, checkouts.repository_root, owned=fact)
        assert wrapped._repo_root == fact.owned_root
        assert wrapped._worktree_root == fact.owned_root

        wrapped.emit_decision_input_requested(_requested_payload())

        assert (fact.owned_root / "kitty-specs" / checkouts.mission_slug / "decisions.events.jsonl").is_file()
        assert not (checkouts.repository_root / "kitty-specs" / checkouts.mission_slug / "decisions.events.jsonl").exists()
        snap.assert_unchanged(before, snap.take(), tolerate_status_mutex_for=checkouts.mission_slug)

    def test_coord_routing_owned_keeps_the_coordination_worktree_under_r(self, make_owned_checkouts) -> None:
        from runtime.next._internal_runtime.events import NullEmitter
        from runtime.next.runtime_bridge_decision_log import _wrap_with_decision_git_log
        from specify_cli.coordination.workspace import CoordinationWorkspace

        checkouts, fact = _coord_owned_with_removed_worktree(make_owned_checkouts)

        wrapped = _wrap_with_decision_git_log(NullEmitter(), checkouts.mission_slug, checkouts.repository_root, owned=fact)

        expected = CoordinationWorkspace.worktree_path(checkouts.repository_root, checkouts.mission_slug, checkouts.mid8)
        assert wrapped._worktree_root == expected
        assert wrapped._worktree_root.is_relative_to(checkouts.repository_root / ".worktrees")


class TestFr008NoWedge:
    """FR-008 / O5: on a finalized owned mission, the runtime advances
    without a ``ValueError`` / wedge, and the WP-iteration step resolves the
    workspace to P (never R, never a fold-to-R crash)."""

    def test_owned_single_branch_board_resolves_implement_at_p(
        self,
        make_owned_checkouts,
        make_r_snapshot,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Exercises the board authority directly at the runtime entry point
        this WP owns (``_wp_iteration_action_and_state`` /
        ``_resolve_wp_board_action``), which is exactly where the pre-fix
        wedge lived (board decline -> ``_state_to_action`` fold-to-R ->
        uncaught ``ValueError``). Deliberately does not drive the full
        specify->plan->tasks composition pipeline (WP12/WP13 territory,
        outside this WP's owned files) to reach ``implement``."""

        checkouts = make_owned_checkouts(topology="single_branch")
        _provision_charter(checkouts)
        _finalize(checkouts, monkeypatch)
        snap = make_r_snapshot(checkouts)
        before = snap.take()
        fact = _mint(checkouts)

        action, wp_id, workspace_path, blocked_reason, mission_state = decision_mapping._wp_iteration_action_and_state(
            "implement",
            checkouts.mission_slug,
            "software-dev",
            checkouts.owned_root / "kitty-specs" / checkouts.mission_slug,
            checkouts.repository_root,
            owned=fact,
        )

        assert blocked_reason is None, blocked_reason
        assert action == "implement"
        assert wp_id is not None
        assert workspace_path is not None
        assert Path(workspace_path).resolve() == fact.owned_root.resolve()

        snap.assert_unchanged(before, snap.take(), tolerate_status_mutex_for=checkouts.mission_slug)

    def test_non_owned_control_stays_green(self, tmp_path: Path) -> None:
        """Same-fixture non-vacuity control: a non-owned lane mission through
        the same entry point (no ``owned=``) is unaffected by this WP's
        threading."""
        import json
        import subprocess as sp

        from runtime.next import decision as decision_mod

        repo_root = tmp_path / "control-repo"
        repo_root.mkdir()
        sp.run(["git", "init", "-q", "-b", "main"], cwd=repo_root, check=True)
        sp.run(["git", "config", "user.email", "t@t.invalid"], cwd=repo_root, check=True)
        sp.run(["git", "config", "user.name", "t"], cwd=repo_root, check=True)
        sp.run(["git", "config", "commit.gpgsign", "false"], cwd=repo_root, check=True)
        (repo_root / ".kittify").mkdir()
        provision_test_charter(repo_root)
        mission_dir = repo_root / "kitty-specs" / "control-mission-01M2D900"
        mission_dir.mkdir(parents=True)
        (mission_dir / "meta.json").write_text(json.dumps({"mission_type": "software-dev"}), encoding="utf-8")
        (repo_root / "README.md").write_text("seed\n", encoding="utf-8")
        sp.run(["git", "add", "."], cwd=repo_root, check=True)
        sp.run(["git", "commit", "-qm", "seed"], cwd=repo_root, check=True)

        decision = decision_mod.decide_next("claude", "control-mission-01M2D900", "success", repo_root)
        assert decision.mission_slug == "control-mission-01M2D900"
        assert decision.kind in ("step", "terminal", "blocked", "decision_required")


def _walk_to_tasks(checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> OwnedCheckout:
    """Finalize P's board, drive the REAL engine to the composed ``tasks``
    step inside P, and mint the fact. The next ``decide_next(..., "success")``
    completes ``tasks`` and must issue ``implement WP01`` in P (O5)."""
    _provision_charter(checkouts)
    _finalize(checkouts, monkeypatch)
    advance_to_step(checkouts.owned_root, checkouts.mission_slug, "software-dev", "tasks")
    return _mint(checkouts)


def _r_snapshot(checkouts: OwnedCheckouts) -> Any:
    """An :class:`RSnapshotter` over R (and P's git state) that leaves the
    global home out of scope: ``decide_next`` legitimately writes the step's
    prompt file under the global ``spec-kitty-prompts`` directory."""
    from tests._owned_fixtures import RSnapshotter

    return RSnapshotter(checkouts.repository_root, checkouts.owned_root, None)


def _run_state_bytes(checkouts: OwnedCheckouts, fact: OwnedCheckout) -> dict[str, bytes]:
    """``state.json`` / ``run.events.jsonl`` of the run the mission is on."""
    from runtime.next.runtime_bridge import get_or_start_run

    run_dir = Path(get_or_start_run(checkouts.mission_slug, checkouts.owned_root, "software-dev", owned=fact).run_dir)
    return {name: (run_dir / name).read_bytes() for name in ("state.json", "run.events.jsonl") if (run_dir / name).is_file()}


def _assert_issues_implement_wp01_in_p(decision: Any, fact: OwnedCheckout) -> None:
    """The contract of this WP's runtime: the step the run advanced to is
    ``implement WP01`` and its workspace is P. The step's PROMPT is built from P
    by ``prompt_builder`` (WP12), so the decision is a real ``step``."""
    assert decision.kind == "step", (decision.kind, decision.reason)
    assert decision.error_code is None
    assert decision.action == "implement"
    assert decision.wp_id == "WP01"
    assert decision.workspace_path is not None
    assert Path(decision.workspace_path).resolve() == fact.owned_root.resolve()


class TestFr008RuntimeWalk:
    """T057 step 2 / FR-008 / O5 at the REAL ``decide_next`` entry point
    (review cycle 1 finding 5): a finalized single_branch owned mission whose
    run sits at ``tasks`` advances to ``implement WP01`` in P with no
    ``ValueError`` / wedge."""

    def test_decide_next_from_tasks_issues_implement_wp01_in_p(
        self,
        make_owned_checkouts,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from runtime.next import decision as decision_mod
        from runtime.next.runtime_bridge import query_current_state

        checkouts = make_owned_checkouts(topology="single_branch")
        fact = _walk_to_tasks(checkouts, monkeypatch)
        snap = _r_snapshot(checkouts)
        before = snap.take()

        decision = decision_mod.decide_next("claude", checkouts.mission_slug, "success", checkouts.repository_root, owned=fact)

        _assert_issues_implement_wp01_in_p(decision, fact)

        follow_up = query_current_state("claude", checkouts.mission_slug, checkouts.repository_root, owned=fact)
        assert follow_up.mission_state == "implement", "the run must have advanced past the unadvanced decision"
        snap.assert_unchanged(before, snap.take(), tolerate_status_mutex_for=checkouts.mission_slug)

    def test_resolution_failure_leaves_run_state_untouched_and_propagates(
        self,
        make_owned_checkouts,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """FR-008: when the WP workspace cannot be resolved the typed error
        propagates (never a ``blocked`` wrapper) and NOTHING was persisted."""
        from mission_runtime import ActionContextError
        from runtime.next import decision as decision_mod

        checkouts = make_owned_checkouts(topology="single_branch")
        fact = _walk_to_tasks(checkouts, monkeypatch)
        before = _run_state_bytes(checkouts, fact)
        assert before, "fixture must have a persisted run state to compare"
        refusal = ActionContextError(OwnedRefusalCode.OWNED_REVIEW_BASE_UNAVAILABLE.value, "cannot resolve the workspace")

        def _fails(*_a: Any, **_k: Any) -> Any:
            raise refusal

        monkeypatch.setattr(decision_mapping, "_wp_iteration_action_and_state", _fails)

        with pytest.raises(ActionContextError) as excinfo:
            decision_mod.decide_next("claude", checkouts.mission_slug, "success", checkouts.repository_root, owned=fact)

        assert excinfo.value.code == OwnedRefusalCode.OWNED_REVIEW_BASE_UNAVAILABLE.value
        assert _run_state_bytes(checkouts, fact) == before, "the advance must not have been persisted"

    def test_non_owned_control_walks_from_tasks_to_implement(self, tmp_path: Path) -> None:
        """Same entry point, no ``owned=``: the identical walk on a plain
        (non-owned) mission is green -- the row is attributable to the fact."""
        from runtime.next import decision as decision_mod
        from tests.runtime._next_mission_scaffold import scaffold_software_dev

        repo = tmp_path / "control"
        slug = "042-owned-walk-control"
        scaffold_software_dev(repo, slug, with_spec=True, with_plan=True, with_tasks_md=True, wps={"WP01": "planned"})
        advance_to_step(repo, slug, "software-dev", "tasks")

        decision = decision_mod.decide_next("claude", slug, "success", repo)

        assert decision.kind == "step", (decision.kind, decision.reason)
        assert decision.action == "implement"
        assert decision.wp_id == "WP01"
        assert decision.progress is not None and decision.progress["total_wps"] == 1


class TestPreFinalizeFallbackPin:
    """T057 step 3 / T067: before ``finalize-tasks`` the board has no opinion
    and ``_state_to_action(owned=)`` reads P (never folds to R)."""

    def test_state_to_action_and_board_authority_resolve_p(self, make_owned_checkouts) -> None:
        from runtime.next.decision import _state_to_action

        checkouts = make_owned_checkouts(topology="single_branch")
        _provision_charter(checkouts)
        fact = _mint(checkouts)
        feature_dir = checkouts.owned_root / "kitty-specs" / checkouts.mission_slug
        # Unseeded WPs are GENESIS (Contract 3 / FR-008: not claimable before
        # finalize-tasks seeds them), so the pre-finalize fallback pin seeds
        # WP01 as planned on P's own status surface.
        seed_wp_lane(feature_dir, checkouts.mission_slug, "WP01", "planned")

        action, wp_id, workspace = _state_to_action("implement", checkouts.mission_slug, feature_dir, checkouts.repository_root, "software-dev", owned=fact)
        assert (action, wp_id) == ("implement", "WP01")
        assert workspace is not None and Path(workspace).resolve() == fact.owned_root.resolve()

        board = decision_mapping._wp_iteration_action_and_state(
            "implement", checkouts.mission_slug, "software-dev", feature_dir, checkouts.repository_root, owned=fact
        )
        assert board[0] == "implement" and board[3] is None
        assert board[2] is not None and Path(board[2]).resolve() == fact.owned_root.resolve()


class TestFr009CompositionSeams:
    """T057 step 4 / FR-009 (review cycle 1 finding 1): reached through the
    REAL ``decide_next`` entry, the composition seams receive the fact and P
    -- ``kwargs["owned"] is fact`` and ``repo_root == fact.owned_root`` for
    dispatch, and ``owned is fact`` for the run-state advance. The spies call
    through, so the walk itself is unchanged."""

    def test_composition_seams_receive_the_fact_and_p(
        self,
        make_owned_checkouts,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from runtime.next import decision as decision_mod
        from runtime.next import runtime_bridge
        from runtime.next import runtime_bridge_composition as composition

        checkouts = make_owned_checkouts(topology="single_branch")
        fact = _walk_to_tasks(checkouts, monkeypatch)
        seen: dict[str, dict[str, Any]] = {}

        def _spy(name: str, real: Any) -> Any:
            def _call(*args: Any, **kwargs: Any) -> Any:
                seen[name] = {"args": args, "kwargs": kwargs}
                return real(*args, **kwargs)

            return _call

        monkeypatch.setattr(composition, "_composition_dispatch_inputs", _spy("inputs", composition._composition_dispatch_inputs))
        monkeypatch.setattr(composition, "_dispatch_via_composition", _spy("dispatch", composition._dispatch_via_composition))
        monkeypatch.setattr(
            runtime_bridge._engine_adapter,
            "advance_run_state_after_composition",
            _spy("advance", runtime_bridge._engine_adapter.advance_run_state_after_composition),
        )

        decision_mod.decide_next("claude", checkouts.mission_slug, "success", checkouts.repository_root, owned=fact)

        assert seen["dispatch"]["kwargs"]["owned"] is fact
        assert Path(seen["dispatch"]["kwargs"]["repo_root"]) == fact.owned_root
        assert seen["advance"]["kwargs"]["owned"] is fact
        assert Path(seen["advance"]["kwargs"]["repo_root"]) == checkouts.repository_root
        inputs_repo_root = seen["inputs"]["kwargs"].get("repo_root", seen["inputs"]["args"][0] if seen["inputs"]["args"] else None)
        assert Path(inputs_repo_root) == fact.owned_root


class TestOwnedRunIdentity:
    """FR-007 (found while making the stale-copy row non-vacuous): the run
    store is keyed by the mission identity read from the VALIDATED fact's own
    mission dir on P -- the identity seam folds a worktree root to R, where a
    stale copy of the mission (possibly another mission's) must never decide
    which run is resumed."""

    def test_run_is_keyed_by_ps_identity_never_a_stale_copy_in_r(
        self,
        owned_checkouts,
        stale_root_copy,
    ) -> None:
        import json

        from runtime.next.runtime_bridge import get_or_start_run

        checkouts = owned_checkouts
        _provision_charter(checkouts)
        stale_root_copy(different_id=True)  # R holds a copy of M with ANOTHER mission_id
        fact = _mint(checkouts)

        get_or_start_run(checkouts.mission_slug, checkouts.owned_root, "software-dev", owned=fact)

        index = json.loads((checkouts.owned_root / ".kittify" / "runtime" / "feature-runs.json").read_text(encoding="utf-8"))
        assert list(index) == [checkouts.mission_id]
        assert index[checkouts.mission_id]["mission_id"] == checkouts.mission_id

    def test_unbound_legacy_run_is_adopted_under_the_verified_fact(self, owned_checkouts) -> None:
        """A run recorded before identity could be read from P (keyed
        ``legacy-<slug>``) is adopted, not wedged on: the validated fact IS the
        ownership verification ``RunIdentityMigrationRequired`` asks for."""
        import json

        from runtime.next.runtime_bridge import get_or_start_run
        from runtime.next.runtime_bridge_io import _existing_run_ref

        checkouts = owned_checkouts
        _provision_charter(checkouts)
        fact = _mint(checkouts)
        legacy = get_or_start_run(checkouts.mission_slug, checkouts.owned_root, "software-dev")  # pre-fix owned shape
        index_path = checkouts.owned_root / ".kittify" / "runtime" / "feature-runs.json"
        assert list(json.loads(index_path.read_text(encoding="utf-8"))) == [f"legacy-{checkouts.mission_slug}"]

        # Query mode adopts in memory only and never persists.
        existing = _existing_run_ref(checkouts.mission_slug, checkouts.owned_root, "software-dev", owned=fact)
        assert existing is not None and existing.run_id == legacy.run_id
        assert list(json.loads(index_path.read_text(encoding="utf-8"))) == [f"legacy-{checkouts.mission_slug}"]

        adopted = get_or_start_run(checkouts.mission_slug, checkouts.owned_root, "software-dev", owned=fact)

        assert adopted.run_id == legacy.run_id, "the same run must be resumed, not a new one started"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        assert list(index) == [checkouts.mission_id]
        assert index[checkouts.mission_id]["mission_id"] == checkouts.mission_id


class TestOwnedGuardFailurePaths:
    """Review cycle 1 finding 11: ``decide_next`` hands the runtime R plus the
    fact, so the guard-failure "looked for" paths must be resolved from P's
    mission home -- never from R's."""

    def test_paths_name_the_owned_checkout(self, owned_checkouts, stale_root_copy) -> None:
        from runtime.next.decision import Decision, _with_guard_failure_paths

        checkouts = owned_checkouts
        _provision_charter(checkouts)
        stale_root_copy()
        fact = _mint(checkouts)
        decision = Decision(
            kind="blocked",
            agent="claude",
            mission_slug=checkouts.mission_slug,
            mission="software-dev",
            mission_state="specify",
            timestamp="2026-09-29T00:00:00+00:00",
            guard_failures=["Required artifact missing: spec.md"],
        )

        with_paths = _with_guard_failure_paths(decision, checkouts.repository_root, owned=fact)

        assert with_paths.guard_failure_paths, "the missing spec.md must be reported with the path that was read"
        looked_for = Path(with_paths.guard_failure_paths["spec.md"])
        assert looked_for == fact.mission_dir / "spec.md"
        assert not looked_for.is_relative_to(checkouts.repository_root / "kitty-specs")


def _merge_stale_copy_in_r(copy_dir: Path, mission_slug: str) -> None:
    """Make R's stale copy of M look MERGED: a committed ``mission_number`` and
    every WP at an acceptable ending on its own status log."""
    import json

    from specify_cli.status.models import Lane, StatusEvent
    from specify_cli.status.store import append_event

    meta_path = copy_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["mission_number"] = 7
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    for wp_id in ("WP01", "WP02", "WP03", "WP04", "WP05"):
        append_event(
            copy_dir,
            StatusEvent(
                event_id=f"stale-{wp_id}-approved",
                mission_slug=mission_slug,
                wp_id=wp_id,
                from_lane=Lane.GENESIS,
                to_lane=Lane.APPROVED,
                at="2026-01-01T00:00:00+00:00",
                actor="fixture",
                force=True,
                execution_mode="worktree",
            ),
        )


class TestOwnedMergedShortCircuit:
    """FR-007 (review cycle 2 finding 1): the committed-authority short-circuit
    must read the owned mission on P. A stale copy of M in R that looks merged
    (``mission_number`` set, every WP acceptable) must not declare the
    unmerged owned mission finished."""

    def test_stale_merged_copy_in_r_does_not_short_circuit_decide_next(self, owned_checkouts, stale_root_copy) -> None:
        from runtime.next import decision as decision_mod

        checkouts = owned_checkouts
        _provision_charter(checkouts)
        _merge_stale_copy_in_r(stale_root_copy(), checkouts.mission_slug)
        fact = _mint(checkouts)

        decision = decision_mod.decide_next("claude", checkouts.mission_slug, "success", checkouts.repository_root, owned=fact)

        assert decision.kind != "terminal", (decision.kind, decision.reason)
        assert decision.mission_state != "done"

    def test_stale_merged_copy_in_r_does_not_short_circuit_query(self, owned_checkouts, stale_root_copy) -> None:
        from runtime.next.runtime_bridge import query_current_state

        checkouts = owned_checkouts
        _provision_charter(checkouts)
        _merge_stale_copy_in_r(stale_root_copy(), checkouts.mission_slug)
        fact = _mint(checkouts)

        decision = query_current_state("claude", checkouts.mission_slug, checkouts.repository_root, owned=fact)

        assert decision.mission_state != "done", (decision.kind, decision.mission_state, decision.reason)

    def test_a_merged_owned_mission_on_p_still_short_circuits(self, owned_checkouts) -> None:
        """Positive control: the gate reads P, so a mission merged ON P is terminal."""
        from runtime.next import decision as decision_mod

        checkouts = owned_checkouts
        _provision_charter(checkouts)
        _merge_stale_copy_in_r(checkouts.mission_dir, checkouts.mission_slug)  # P's own mission dir this time
        fact = _mint(checkouts)

        decision = decision_mod.decide_next("claude", checkouts.mission_slug, "success", checkouts.repository_root, owned=fact)

        assert decision.kind == "terminal"

    def test_non_owned_control_still_short_circuits(self, tmp_path: Path) -> None:
        """Same entry, no ``owned=``: a merged plain mission is terminal."""
        from runtime.next import decision as decision_mod
        from tests.runtime._next_mission_scaffold import scaffold_software_dev

        repo = tmp_path / "control"
        slug = "042-merged-control"
        scaffold_software_dev(repo, slug, with_spec=True, with_plan=True, with_tasks_md=True, wps={"WP01": "planned"})
        _merge_stale_copy_in_r(repo / "kitty-specs" / slug, slug)

        decision = decision_mod.decide_next("claude", slug, "success", repo)

        assert decision.kind == "terminal"
