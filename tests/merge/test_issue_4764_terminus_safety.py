"""Scope: #4764 — merge warn-mode consolidates+bakes an unapproved lane, no rollback.

Mission ``terminus-safety-invariant-01M2XFT7`` / WP02 (FR-001, FR-002, FR-003,
FR-006). Today (before this WP's fix), with the DEFAULT
``policy.merge_gates.mode: warn``, the missing-approval finding inside
``_evaluate_evidence_gate`` (``policy/merge_gates.py``) is only a non-blocking
warning (``blocking = mode == "block"``) — so ``executor.py``'s
``if not gate_eval.overall_pass:`` stop never fires. ``spec-kitty merge`` then
consolidates the lane branch onto the coordination/mission branch and bakes
``mission_number`` into the coordination ``meta.json`` BEFORE the post-merge
done-bookkeeping backstop discovers the missing approval and exits 1 — with
nothing rolled back. The lane is left with zero commits beyond coordination
(the ``for_review`` gate then rejects it forever), and coordination vs primary
``meta.json`` split-brain on ``mission_number``.

The fix (T006/T007) de-conflates the terminal-lane invariant out of the
mode-softened evidence gate and adds an UNCONDITIONAL merge-ready precondition
(``executor._assert_mission_terminal_ready``) at the TOP of
``_phase_gates_and_state`` — strictly before ``_phase_merge_lanes`` (the first
mutating phase) — built on the shared aggregate
``status_lanes.mission_terminal_acceptability`` (WP01).

These tests drive the REAL, pre-existing CLI entry point
(``specify_cli.cli.commands.merge._run_lane_based_merge`` ->
``specify_cli.merge.executor._run_lane_based_merge_locked``, C-004) against an
on-disk coordination-topology git repository — modeled on the proven harness
in ``tests/merge/test_issue_2711_merge_rollback_resume_coherence.py`` and
``tests/merge/test_merge_canceled_wp.py`` (this module's local fusion helpers
are duplicated here rather than importing those modules' private helpers, per
those modules' own "shared harness files are never edited in place" note).

``evaluate_merge_gates`` is deliberately mocked to always PASS (simulating
"gates say the merge is fine" under the default ``warn`` config) so these
tests isolate the NEW, separate, unconditional precondition — never
conflating it with the evidence gate's own (separately unit-tested in
``tests/policy/test_merge_gates.py``) internal softening behavior.

RED before the WP02 fix (the unapproved WP is consolidated + baked, exits 0 or
fails only much later with state already mutated); GREEN after (refuses before
any mutation).
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from kernel.clock import now_utc_iso

# Import the status package before any coordination submodule (production import
# order) to avoid the known ``coordination -> transaction -> status`` cycle when a
# test module imports ``merge`` first under ``PYTHONPATH=src``.
import specify_cli.status  # noqa: F401  # import-order guard (see comment above)

from specify_cli.cli.commands.merge import _run_lane_based_merge
from specify_cli.coordination.status_service import (
    EventLogReadContract,
    read_event_log,
    wp_lane_actor_from_events,
)
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.merge.config import MergeStrategy
from specify_cli.merge.state import get_state_path
from specify_cli.status import Lane, StatusEvent

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]


# ---------------------------------------------------------------------------
# Mission identity (slug ends with ``-<mid8>`` so the coordination branch IS the
# lanes-manifest mission branch — the production 083+ coord-topology layout).
# ---------------------------------------------------------------------------

MID8 = "01M2XFT7"
MISSION_ID = "01M2XFT7000000000000004764"
MISSION_SLUG = f"terminus-4764-{MID8}"
COORD_BRANCH = f"kitty/mission-{MISSION_SLUG}"
WP_ID = "WP01"
LANE_ID = "lane-a"
LANE_CODE = "src/unapproved_feature.py"


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True, capture_output=True, text=True)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run(["git", "-C", str(repo), *args])


def _init_git_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-qb", "main", str(repo)])
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")


def _file_on_branch(repo: Path, branch: str, relpath: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo), "ls-tree", "--name-only", "-r", branch, "--", relpath],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and relpath in result.stdout.splitlines()


def _branch_tip(repo: Path, branch: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", branch],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


# ---------------------------------------------------------------------------
# Coord-topology fixture (local fusion helpers — see module docstring)
# ---------------------------------------------------------------------------


def _write_meta(feature_dir: Path) -> None:
    meta = {
        "mission_slug": MISSION_SLUG,
        "mission_id": MISSION_ID,
        "mid8": MID8,
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": "main",
        "coordination_branch": COORD_BRANCH,
        "purpose_tldr": "#4764 merge-refuses-unapproved-mission regression",
        "purpose_context": "warn mode must not fail-open an unapproved WP",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_manifest(feature_dir: Path) -> LanesManifest:
    manifest = LanesManifest(
        version=1,
        mission_slug=MISSION_SLUG,
        mission_id=MISSION_SLUG,
        mission_branch=COORD_BRANCH,
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id=LANE_ID,
                wp_ids=(WP_ID,),
                write_scope=(LANE_CODE,),
                predicted_surfaces=("code",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at=now_utc_iso(),
        computed_from="test-fixture",
    )
    write_lanes_json(feature_dir, manifest)
    return manifest


def _write_wp_file(feature_dir: Path) -> None:
    (feature_dir / "tasks" / f"{WP_ID}-work.md").write_text(
        f"---\nwork_package_id: {WP_ID}\ntitle: {WP_ID} work\nagent: implementer-bot\n---\n# {WP_ID}\n",
        encoding="utf-8",
    )


def _in_progress_event() -> dict[str, object]:
    """WP01 is IN PROGRESS — unapproved, not cancelled: the #4764 shape."""
    return {
        "actor": "implementer-bot",
        "at": now_utc_iso(),
        "event_id": "01HXYZ4764000000000000001",
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": MISSION_SLUG,
        "force": False,
        "from_lane": "claimed",
        "reason": None,
        "review_ref": None,
        "to_lane": "in_progress",
        "wp_id": WP_ID,
    }


def _approved_event() -> dict[str, object]:
    return {
        "actor": "reviewer-renata",
        "at": now_utc_iso(),
        "event_id": "01HXYZ4764000000000000002",
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": MISSION_SLUG,
        "force": False,
        "from_lane": "in_review",
        "reason": None,
        "review_ref": f"review-{WP_ID}",
        "to_lane": "approved",
        "wp_id": WP_ID,
    }


def _bootstrap_coord_mission(repo: Path, *, wp_event: dict[str, object]) -> Path:
    """Bootstrap a coord-topology mission with WP01 at the state ``wp_event`` sets.

    Returns the primary-checkout feature_dir.
    """
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    _write_meta(feature_dir)
    _write_manifest(feature_dir)
    _write_wp_file(feature_dir)

    (feature_dir / "status.events.jsonl").write_text(json.dumps(wp_event, sort_keys=True) + "\n", encoding="utf-8")

    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({MISSION_SLUG}): bootstrap coord mission")

    # Coordination/mission branch at the current tip.
    _git(repo, "branch", COORD_BRANCH)

    # Lane branch with a REAL code diff not on the mission branch nor main —
    # the exact #4764 shape: unreviewed code sitting in a lane, ready to be
    # (wrongly) consolidated if the invariant fails open.
    lane_branch = f"kitty/mission-{MISSION_SLUG}-{LANE_ID}"
    _git(repo, "branch", lane_branch, COORD_BRANCH)
    _git(repo, "checkout", lane_branch)
    code_path = repo / LANE_CODE
    code_path.parent.mkdir(parents=True, exist_ok=True)
    code_path.write_text("def unapproved() -> int:\n    return 4764\n", encoding="utf-8")
    _git(repo, "add", LANE_CODE)
    _git(repo, "commit", "-m", f"feat({MISSION_SLUG}): lane code for {WP_ID}")
    _git(repo, "checkout", "main")

    # Materialize the coordination worktree with the mission branch checked out
    # (the production topology).
    CoordinationWorkspace.resolve(repo, MISSION_SLUG, MID8)

    return feature_dir


@contextlib.contextmanager
def _merge_external_mocks() -> Iterator[dict[str, MagicMock]]:
    """Mock ONLY side effects outside the precondition + git/status bookkeeping.

    ``evaluate_merge_gates`` is mocked to always PASS — simulating "the (old)
    gates say it's fine" under the default ``warn`` config — so these tests
    isolate the NEW, separate, unconditional ``_assert_mission_terminal_ready``
    precondition, never conflating it with the evidence gate's own softening
    behavior (unit-tested separately in ``tests/policy/test_merge_gates.py``).
    """
    patches = {
        "run_check": patch("specify_cli.merge.executor.run_check"),
        "sparse": patch("specify_cli.merge.executor.require_no_sparse_checkout"),
        "preflight": patch("specify_cli.cli.commands.merge._enforce_git_preflight"),
        "review_consistency": patch("specify_cli.merge.executor._enforce_review_artifact_consistency"),
        "status_history": patch("specify_cli.merge.executor._enforce_canonical_status_history"),
        "hollow": patch("specify_cli.merge.executor._warn_or_confirm_hollow_reviews"),
        "bake": patch("specify_cli.merge.executor._bake_mission_number_into_mission_branch", return_value=None),
        "baseline_record": patch("specify_cli.merge.executor._record_baseline_merge_commit", return_value=None),
        "baseline_assert": patch("specify_cli.merge.executor._assert_baseline_merge_commit_on_target"),
        "done_on_target": patch("specify_cli.merge.executor._assert_merged_wps_done_on_target"),
        "safe_commit": patch("specify_cli.merge.executor.commit_merge_bookkeeping"),
        "refresh_primary": patch("specify_cli.merge.executor._refresh_primary_checkout_after_merge"),
        "porcelain": patch("specify_cli.merge.executor._classify_porcelain_lines", return_value=([], 0)),
        "gates": patch("specify_cli.policy.merge_gates.evaluate_merge_gates"),
        "policy": patch("specify_cli.policy.config.load_policy_config"),
        "remote": patch("specify_cli.merge.executor.has_remote", return_value=False),
    }
    with contextlib.ExitStack() as stack:
        mocks = {name: stack.enter_context(p) for name, p in patches.items()}
        gate_eval = MagicMock()
        gate_eval.overall_pass = True
        gate_eval.gates = []
        mocks["gates"].return_value = gate_eval
        policy = MagicMock()
        policy.merge_gates = MagicMock(mode="warn")
        mocks["policy"].return_value = policy
        stale_report = MagicMock()
        stale_report.findings = []
        mocks["run_check"].return_value = stale_report
        yield mocks


def _run_merge(repo: Path, *, push: bool = False) -> BaseException | None:
    """Run one merge pass; return the raised exception, or None on success."""
    with _merge_external_mocks():
        try:
            _run_lane_based_merge(
                repo_root=repo,
                mission_slug=MISSION_SLUG,
                push=push,
                delete_branch=False,
                remove_worktree=False,
                strategy=MergeStrategy.SQUASH,
                assume_yes=True,
            )
        except BaseException as exc:  # noqa: BLE001 — captured for assertion, not swallowed
            return exc
    return None


def _committed_coord_events(repo: Path, feature_dir: Path) -> list[StatusEvent]:
    return cast(
        "list[StatusEvent]",
        read_event_log(
            EventLogReadContract.coordination_branch_ref(
                repo_root=repo,
                destination_ref=COORD_BRANCH,
                feature_dir=feature_dir,
                parser_feature_dir=feature_dir,
            )
        ),
    )


# ---------------------------------------------------------------------------
# #4764 core (US1-1, US1-2, NFR-003)
# ---------------------------------------------------------------------------


def test_4764_unapproved_wp_refuses_before_any_mutation_under_warn_mode(tmp_path: Path) -> None:
    """A mission with a non-cancelled WP still ``in_progress`` (unapproved) must
    refuse under the DEFAULT ``warn`` gate mode — before any lane consolidation
    or ``mission_number`` bake, leaving the lane, coordination ref, and primary
    ``meta.json`` byte-for-byte unchanged, and the WP still reviewable."""
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    feature_dir = _bootstrap_coord_mission(repo, wp_event=_in_progress_event())

    lane_branch = f"kitty/mission-{MISSION_SLUG}-{LANE_ID}"
    pre_lane_tip = _branch_tip(repo, lane_branch)
    pre_coord_tip = _branch_tip(repo, COORD_BRANCH)
    pre_primary_meta = (feature_dir / "meta.json").read_text(encoding="utf-8")

    exc = _run_merge(repo)

    assert exc is not None, "merge must refuse (non-zero exit), not succeed"
    exit_code = getattr(exc, "exit_code", None)
    assert exit_code not in (0, None), f"merge must exit non-zero, got exit_code={exit_code} ({exc!r})"

    # -- no mutation: lane, coordination ref, primary meta.json unchanged --
    assert _branch_tip(repo, lane_branch) == pre_lane_tip, "the lane branch must be byte-for-byte unchanged — no consolidation occurred"
    assert _branch_tip(repo, COORD_BRANCH) == pre_coord_tip, "the coordination/mission branch must be unchanged — no bake, no done write"
    assert (feature_dir / "meta.json").read_text(encoding="utf-8") == pre_primary_meta, "primary meta.json must be unchanged — mission_number still unassigned"
    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["mission_number"] is None, "mission_number must still be unassigned"

    # -- the WP can still move to for_review: its lane in the committed log is
    #    still ``in_progress`` (not stranded at some half-terminated state) --
    events = _committed_coord_events(repo, feature_dir)
    wp_state = wp_lane_actor_from_events(events, WP_ID)
    assert wp_state.lane == Lane.IN_PROGRESS, f"WP{WP_ID} must still be reviewable (in_progress), got lane={wp_state.lane!r}"


def test_4764_refusal_names_the_missing_wp_and_originates_from_precondition(tmp_path: Path) -> None:
    """The refusal message must name the missing WP (operator-actionable), and
    must not be a generic/unrelated failure."""
    import typer

    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _bootstrap_coord_mission(repo, wp_event=_in_progress_event())

    with _merge_external_mocks(), patch("specify_cli.cli.console.console.print") as mock_print, pytest.raises(typer.Exit):
        _run_lane_based_merge(
            repo_root=repo,
            mission_slug=MISSION_SLUG,
            push=False,
            delete_branch=False,
            remove_worktree=False,
            strategy=MergeStrategy.SQUASH,
            assume_yes=True,
        )
    printed = " ".join(str(call.args[0]) for call in mock_print.call_args_list if call.args)
    assert WP_ID in printed, f"refusal must name the missing WP {WP_ID}: {printed!r}"
    assert "merge-ready" in printed.lower() or "review approval" in printed.lower()


# ---------------------------------------------------------------------------
# US1-5 — a ``--resume``d merge re-evaluates LIVE readiness, never vacuous
# ---------------------------------------------------------------------------


def test_4764_resume_reevaluates_live_readiness_not_vacuous_on_stale_baseline(
    tmp_path: Path,
) -> None:
    """A ``--resume``d merge must re-read the CURRENT event log every time — it
    must never short-circuit on a cached/stale "merged" marker. Simulated by
    running the merge twice: attempt 1 creates ``state.json`` (is_resume=False
    the first time round) and refuses; attempt 2 (now is_resume=True, reading
    the SAME still-unapproved WP) must ALSO refuse via the same live
    precondition — never passing merely because state.json already exists."""
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    feature_dir = _bootstrap_coord_mission(repo, wp_event=_in_progress_event())

    exc1 = _run_merge(repo)
    assert exc1 is not None, "first (fresh) attempt must refuse"

    pre_coord_tip = _branch_tip(repo, COORD_BRANCH)

    exc2 = _run_merge(repo)
    assert exc2 is not None, "resumed attempt must ALSO refuse — the WP is still unapproved"
    assert getattr(exc2, "exit_code", None) not in (0, None)
    assert _branch_tip(repo, COORD_BRANCH) == pre_coord_tip, "resume must not mutate the coordination ref either"
    events = _committed_coord_events(repo, feature_dir)
    wp_state = wp_lane_actor_from_events(events, WP_ID)
    assert wp_state.lane == Lane.IN_PROGRESS


# ---------------------------------------------------------------------------
# US1-3 / US1-4 non-regression — a merge-ready mission still proceeds
# ---------------------------------------------------------------------------


def test_merge_ready_mission_still_proceeds_under_warn_mode(tmp_path: Path) -> None:
    """A normal merge-ready mission (WP approved) must NOT be false-blocked by
    the new precondition (US1-3): the precondition passes and the (mocked)
    remainder of the merge is reached."""
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _bootstrap_coord_mission(repo, wp_event=_approved_event())

    with _merge_external_mocks() as mocks:
        _run_lane_based_merge(
            repo_root=repo,
            mission_slug=MISSION_SLUG,
            push=False,
            delete_branch=False,
            remove_worktree=False,
            strategy=MergeStrategy.SQUASH,
            assume_yes=True,
        )
    # Reaching the (mocked) bake call proves the precondition did not
    # false-block a merge-ready mission.
    assert mocks["bake"].called, "a merge-ready mission must proceed past the precondition"


# ---------------------------------------------------------------------------
# FOLD-B (landing-pass remediation) — a not-ready FRESH refusal must not leave
# a stale merge-state.json behind
# ---------------------------------------------------------------------------
#
# ``_load_or_create_merge_state`` (``merge/resolve.py``) persists a fresh
# ``state.json`` to disk BEFORE ``_phase_gates_and_state`` even runs
# ``_assert_mission_terminal_ready``. When the precondition then refuses (the
# WP is not merge-ready), that just-created state.json is left on disk — so
# the NEXT plain ``spec-kitty merge`` attempt is mislabeled a ``--resume`` off
# a stale ``wp_order``, contradicting the refusal's own "the mission is
# unchanged" message. Only a FRESH merge's OWN just-created state must be
# cleared here — a pre-existing ``--resume``'s state must never be destroyed
# by a later, still-not-ready re-run.


def test_4764_not_ready_fresh_refusal_leaves_no_stale_merge_state(tmp_path: Path) -> None:
    """A not-ready FRESH merge attempt must refuse via ``typer.Exit(1)`` AND
    leave no ``state.json`` behind — the refusal's "the mission is unchanged"
    claim must hold for merge state, not just for git refs."""
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _bootstrap_coord_mission(repo, wp_event=_in_progress_event())

    state_path = get_state_path(repo, MISSION_ID)
    assert not state_path.exists(), "precondition: no merge state before the first attempt"

    exc = _run_merge(repo)

    assert exc is not None, "merge must refuse (non-zero exit), not succeed"
    exit_code = getattr(exc, "exit_code", None)
    assert exit_code not in (0, None), f"merge must exit non-zero, got exit_code={exit_code} ({exc!r})"

    assert not state_path.exists(), (
        "a not-ready FRESH refusal must not leave a stale state.json behind — "
        "the next plain `spec-kitty merge` would otherwise be mislabeled a "
        "--resume off a stale wp_order"
    )


def test_4764_not_ready_resume_refusal_preserves_existing_merge_state(tmp_path: Path) -> None:
    """A not-ready RESUMED refusal must NEVER destroy the pre-existing resume
    state — only a fresh merge's own just-created state is cleared on
    refusal."""
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _bootstrap_coord_mission(repo, wp_event=_in_progress_event())

    state_path = get_state_path(repo, MISSION_ID)

    # First attempt: fresh, refuses, and (per the fix above) clears its own
    # just-created state.
    exc1 = _run_merge(repo)
    assert exc1 is not None
    assert not state_path.exists()

    # Manually materialize a "resume" state the way a real interrupted merge
    # would have left one (e.g. from an earlier PARTIALLY-progressed attempt
    # that got interrupted after state creation but the WP is STILL
    # not-ready on a later re-run). This must survive the second refusal.
    from specify_cli.merge.state import MergeState, save_state

    resume_state = MergeState(
        mission_id=MISSION_ID,
        mission_slug=MISSION_SLUG,
        target_branch="main",
        wp_order=[WP_ID],
        push_requested=False,
    )
    resume_state.current_wp = WP_ID
    save_state(resume_state, repo)
    assert state_path.exists()

    exc2 = _run_merge(repo)
    assert exc2 is not None, "the still-not-ready mission must refuse again"
    assert state_path.exists(), "a pre-existing --resume's merge state must never be destroyed by a later not-ready refusal"
