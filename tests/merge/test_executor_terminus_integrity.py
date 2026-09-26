"""WP05 (terminus-integrity-followups) executor-integration unit tests — red-first.

Covers the WP05 seams the executor owns (T019–T023), against the WP03
reconciliation API and WP04 ``MergeState`` fields already stacked in this lane:

* **T019 (FR-002)** — the squash reconciliation PASS message is honest (it never
  asserts excluded-commit reachability the squash axis did not compute), and the
  squash claim handed to the gate keeps ``enforce_closed_world`` set: stripping it
  would silently no-op the P0 #5013 content axis.
* **T020 (FR-003)** — the executor persists the strategy attempt-1 ACTUALLY
  executes into ``MergeState`` so a ``--resume`` reads a truthful value (F14), and
  a resume never overwrites the persisted authority.
* **T021/T022 (FR-004/FR-005)** — the reconciliation claim's coord base and the
  per-lane pre-interrupt tips are read-persisted-first (never re-poisoned on a
  resume, F3/F9), and a resume fails closed on an absent required base (H4) or a
  truly-divergent lane tip (H3) while tolerating the behind-HEAD #4982 window.

The heavy real-subprocess deviation-3 verification (does the squash content axis
ATTRIBUTE on a real coord-topology PRODUCTION merge?) reuses the terminus harness.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import typer

import specify_cli.status  # noqa: F401  # import-order guard (see #2711 harness)
from specify_cli.lanes.branch_naming import lane_branch_name
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.merge import executor as ex
from specify_cli.merge.config import MergeStrategy
from specify_cli.merge.reconciliation import ApprovedWpCommitSet
from specify_cli.merge.state import MergeState, load_state, save_state

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]

MISSION_SLUG = "termfollowups"
# 26-char ULID-shaped id (uppercase ULID charset, no I/L/O/U); mid8 == "01TESTAA".
MISSION_ID = "01TESTAA000000000000000000"
TARGET = "main"


# ---------------------------------------------------------------------------
# Light real-git harness (no mocking of git; O(#lanes), never O(history))
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _git_out(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _branch_for(lane_id: str) -> str:
    branch: str = lane_branch_name(MISSION_SLUG, lane_id, planning_base_branch=TARGET, mission_id=MISSION_ID)
    return branch


def _make_repo(tmp_path: Path, *, lane_ids: tuple[str, ...] = ("lane-a",)) -> tuple[Path, str, dict[str, str]]:
    """Real repo: an ``init`` commit as the coord base + one commit per lane branch.

    Returns ``(repo, base_sha, {lane_branch: tip_sha})``.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-qb", TARGET)
    _git(repo, "config", "user.email", "t@t.com")
    _git(repo, "config", "user.name", "Terminus Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "init")
    base = _git_out(repo, "rev-parse", "HEAD")

    lane_tips: dict[str, str] = {}
    for idx, lane_id in enumerate(lane_ids):
        branch = _branch_for(lane_id)
        _git(repo, "branch", branch, TARGET)
        _git(repo, "checkout", "-q", branch)
        code = repo / "src" / f"{lane_id}.py"
        code.parent.mkdir(parents=True, exist_ok=True)
        code.write_text(f"value = {idx}\n", encoding="utf-8")
        _git(repo, "add", str(code))
        _git(repo, "commit", "-qm", f"feat: {lane_id}")
        lane_tips[branch] = _git_out(repo, "rev-parse", "HEAD")
        _git(repo, "checkout", "-q", TARGET)
    return repo, base, lane_tips


def _manifest(lane_ids: tuple[str, ...] = ("lane-a",)) -> LanesManifest:
    lanes = [
        ExecutionLane(
            lane_id=lane_id,
            wp_ids=(f"WP0{idx + 1}",),
            write_scope=(),
            predicted_surfaces=(),
            depends_on_lanes=(),
            parallel_group=0,
        )
        for idx, lane_id in enumerate(lane_ids)
    ]
    return LanesManifest(
        version=1,
        mission_slug=MISSION_SLUG,
        mission_id=MISSION_ID,
        mission_branch=f"kitty/mission-{MISSION_SLUG}",
        target_branch=TARGET,
        lanes=lanes,
        computed_at="2026-01-01T00:00:00+00:00",
        computed_from="test",
    )


def _state(repo: Path, **overrides: object) -> MergeState:
    state = MergeState(
        mission_id=MISSION_ID,
        mission_slug=MISSION_SLUG,
        target_branch=TARGET,
        wp_order=["WP01"],
    )
    for key, value in overrides.items():
        setattr(state, key, value)
    return state


def _run(
    repo: Path,
    state: MergeState,
    manifest: LanesManifest,
    *,
    is_resume: bool = False,
    strategy: MergeStrategy = MergeStrategy.MERGE,
) -> ex._MergeRunState:
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    return ex._MergeRunState(
        main_repo=repo,
        mission_slug=MISSION_SLUG,
        canonical_id=MISSION_ID,
        canonical_mission_id=MISSION_ID,
        feature_dir=feature_dir,
        target_feature_dir=feature_dir,
        lanes_manifest=manifest,
        all_wp_ids=[wp for lane in manifest.lanes for wp in lane.wp_ids],
        push=False,
        delete_branch=True,
        remove_worktree=True,
        strategy=strategy,
        assume_yes=True,
        planning_artifact_only=False,
        state=state,
        is_resume=is_resume,
    )


# ---------------------------------------------------------------------------
# T020 — strategy reseed persist (FR-003)
# ---------------------------------------------------------------------------


def test_persist_executed_strategy_fresh_overwrites_dead_default(tmp_path: Path) -> None:
    """A fresh state carries the inert ``"merge"`` default; the executor must stamp
    the strategy attempt-1 actually executes so a resume never silently upgrades a
    squash operator to merge (the #4982/#4985/#4991 dead-field root)."""
    repo, _base, _tips = _make_repo(tmp_path)
    state = _state(repo)
    assert state.strategy == "merge"  # the inert dataclass default
    ex._persist_executed_strategy(state, MergeStrategy.SQUASH, is_resume=False, main_repo=repo)
    assert state.strategy == "squash"
    reloaded = load_state(repo, MISSION_ID)
    assert reloaded is not None and reloaded.strategy == "squash"


def test_persist_executed_strategy_fresh_merge_roundtrips(tmp_path: Path) -> None:
    """F14: a fresh ``--strategy merge`` persists ``merge`` so a no-``--strategy``
    resume reads ``merge`` (not the executor default SQUASH)."""
    repo, _base, _tips = _make_repo(tmp_path)
    state = _state(repo)
    ex._persist_executed_strategy(state, MergeStrategy.MERGE, is_resume=False, main_repo=repo)
    reloaded = load_state(repo, MISSION_ID)
    assert reloaded is not None and reloaded.strategy == "merge"


def test_persist_executed_strategy_resume_never_overwrites(tmp_path: Path) -> None:
    """A resume's persisted strategy is the authority (F14/H1): the executor must
    NOT re-stamp it from the resolved run value, so it can never be clobbered."""
    repo, _base, _tips = _make_repo(tmp_path)
    state = _state(repo, strategy="merge")
    save_state(state, repo)
    ex._persist_executed_strategy(state, MergeStrategy.SQUASH, is_resume=True, main_repo=repo)
    assert state.strategy == "merge"
    reloaded = load_state(repo, MISSION_ID)
    assert reloaded is not None and reloaded.strategy == "merge"


# ---------------------------------------------------------------------------
# T021 — read-persisted-first coord/lane-tip anchors (FR-004; F3/F9)
# ---------------------------------------------------------------------------


def test_resolve_pre_mutation_coord_sha_read_persisted_first(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A resume MUST return the persisted pre-mutation coord tip and NEVER capture
    the live checkpoint (which already contains attempt-1's consolidation — the F3/F9
    re-poison). Holds across a resume-of-a-resume."""
    repo, _base, _tips = _make_repo(tmp_path)
    state = _state(
        repo,
        pre_mutation_coord_sha="PERSISTEDCOORDSHA",
        pre_mutation_coord_ref="refs/heads/coord",
        pre_interrupt_lane_tips={"br": "TIP"},
    )
    run = _run(repo, state, _manifest(), is_resume=True)

    def _boom(_run: ex._MergeRunState) -> None:
        raise AssertionError("live coord checkpoint captured on a persisted resume (re-poison!)")

    monkeypatch.setattr(ex, "_capture_coord_checkpoint", _boom)
    assert ex._resolve_pre_mutation_coord_sha(state, run) == "PERSISTEDCOORDSHA"
    # resume-of-a-resume: still stable, still never captures live.
    assert ex._resolve_pre_mutation_coord_sha(state, run) == "PERSISTEDCOORDSHA"
    assert state.pre_mutation_coord_sha == "PERSISTEDCOORDSHA"
    assert state.pre_interrupt_lane_tips == {"br": "TIP"}


def test_resolve_pre_mutation_coord_sha_captures_and_persists_on_fresh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """On a fresh merge the coord tip and per-lane pre-interrupt tips are captured
    ONCE and persisted, so a later resume can read them back."""
    lane_ids = ("lane-a", "lane-b")
    repo, _base, tips = _make_repo(tmp_path, lane_ids=lane_ids)
    state = _state(repo)  # no persisted coord base
    run = _run(repo, state, _manifest(lane_ids), is_resume=False)
    checkpoint = ex._CoordCheckpoint(ref="refs/heads/coord", sha="FRESHCOORDSHA")
    monkeypatch.setattr(ex, "_capture_coord_checkpoint", lambda _run: checkpoint)

    assert ex._resolve_pre_mutation_coord_sha(state, run) == "FRESHCOORDSHA"
    assert state.pre_mutation_coord_sha == "FRESHCOORDSHA"
    assert state.pre_mutation_coord_ref == "refs/heads/coord"
    assert state.pre_interrupt_lane_tips == tips  # both lane branches captured by name

    reloaded = load_state(repo, MISSION_ID)
    assert reloaded is not None
    assert reloaded.pre_mutation_coord_sha == "FRESHCOORDSHA"
    assert reloaded.pre_interrupt_lane_tips == tips


def test_resolve_pre_mutation_coord_sha_none_when_not_coord_topology(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-coord/legacy mission has no checkpoint; the resolver returns ``None``
    and persists nothing (the claim then falls back to the mission branch ref)."""
    repo, _base, _tips = _make_repo(tmp_path)
    state = _state(repo)
    run = _run(repo, state, _manifest(), is_resume=False)
    monkeypatch.setattr(ex, "_capture_coord_checkpoint", lambda _run: None)
    assert ex._resolve_pre_mutation_coord_sha(state, run) is None
    assert state.pre_mutation_coord_sha is None
    assert state.pre_interrupt_lane_tips == {}


# ---------------------------------------------------------------------------
# T022 — resume anchor integrity: fail-closed CAS (FR-004/FR-005; H3/H4)
# ---------------------------------------------------------------------------


def test_enforce_resume_anchor_absent_base_when_consolidated_refuses(tmp_path: Path) -> None:
    """H4: a coord resume whose prior attempt already consolidated (``completed_wps``)
    but did NOT persist the coord base REFUSES (exit 1) — the live checkpoint is
    poisoned by that consolidation, so anchoring to it would be the vacuous-claim false
    PASS. (Post-fix code never emits this state; it is a corruption/residue guard.)"""
    repo, _base, _tips = _make_repo(tmp_path)
    state = _state(repo, pre_mutation_coord_sha=None, completed_wps=["WP01"])
    run = _run(repo, state, _manifest(), is_resume=True)
    with pytest.raises(typer.Exit) as exc:
        ex._enforce_resume_anchor_integrity(run, coord_topology=True)
    assert exc.value.exit_code == 1


def test_enforce_resume_anchor_absent_base_without_consolidation_is_noop(tmp_path: Path) -> None:
    """A resume interrupted BEFORE any consolidation (``completed_wps`` empty) has a
    pristine live checkpoint; H4 must NOT refuse it (the resolver safely captures the
    still-pristine tip). Refusing here regressed #4985/#4991, whose fixtures write a
    post-fix marker + ``strategy`` but never consolidated and never persisted a base."""
    repo, _base, _tips = _make_repo(tmp_path)
    state = _state(repo, pre_mutation_coord_sha=None, completed_wps=[])
    run = _run(repo, state, _manifest(), is_resume=True)
    ex._enforce_resume_anchor_integrity(run, coord_topology=True)  # no raise


def test_enforce_resume_anchor_fresh_is_noop(tmp_path: Path) -> None:
    """A fresh merge has nothing persisted yet; the guard must never fire on it."""
    repo, _base, _tips = _make_repo(tmp_path)
    state = _state(repo, pre_mutation_coord_sha=None)
    run = _run(repo, state, _manifest(), is_resume=False)
    ex._enforce_resume_anchor_integrity(run, coord_topology=True)  # no raise


def test_enforce_resume_anchor_non_coord_is_noop(tmp_path: Path) -> None:
    """A non-coord resume (no coord checkpoint) never requires a persisted base."""
    repo, _base, _tips = _make_repo(tmp_path)
    state = _state(repo, pre_mutation_coord_sha=None)
    run = _run(repo, state, _manifest(), is_resume=True)
    ex._enforce_resume_anchor_integrity(run, coord_topology=False)  # no raise


def test_enforce_resume_anchor_lane_tip_divergence_refuses(tmp_path: Path) -> None:
    """H3: a persisted lane tip that is neither equal, ancestor, nor descendant of
    the live tip (true divergence) REFUSES rather than dropping newer work."""
    repo, _base, tips = _make_repo(tmp_path)
    branch = next(iter(tips))
    # An orphan commit: unrelated to the lane tip (no ancestry either direction).
    _git(repo, "checkout", "-q", "--orphan", "orphan")
    (repo / "z.py").write_text("z\n", encoding="utf-8")
    _git(repo, "add", "z.py")
    _git(repo, "commit", "-qm", "orphan")
    orphan_sha = _git_out(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", TARGET)

    state = _state(
        repo,
        pre_mutation_coord_sha="somebase",
        pre_interrupt_lane_tips={branch: orphan_sha},
    )
    run = _run(repo, state, _manifest(), is_resume=True)
    with pytest.raises(typer.Exit) as exc:
        ex._enforce_resume_anchor_integrity(run, coord_topology=True)
    assert exc.value.exit_code == 1


def test_enforce_resume_anchor_behind_head_does_not_refuse(tmp_path: Path) -> None:
    """The #4982 window: a persisted tip that is a strict ANCESTOR of the live tip
    (the interrupted advance left the ref behind its HEAD) must NOT refuse."""
    repo, base, tips = _make_repo(tmp_path)
    branch = next(iter(tips))
    state = _state(
        repo,
        pre_mutation_coord_sha="somebase",
        pre_interrupt_lane_tips={branch: base},  # ancestor of the lane tip
    )
    run = _run(repo, state, _manifest(), is_resume=True)
    ex._enforce_resume_anchor_integrity(run, coord_topology=True)  # no raise


# ---------------------------------------------------------------------------
# T019 — honest squash pass-message + enforce_closed_world survives (FR-002)
# ---------------------------------------------------------------------------


def test_reconciliation_pass_message_squash_is_honest() -> None:
    """Under squash the gate defers content reachability; the message must NOT claim
    "no excluded commit reachable" (which was never checked under squash)."""
    msg = ex._reconciliation_pass_message(MergeStrategy.SQUASH)
    assert "no excluded commit reachable" not in msg
    assert "deferred" in msg


def test_reconciliation_pass_message_merge_asserts_full_verification() -> None:
    """Merge/rebase ran the full per-SHA reachability + excluded checks."""
    msg = ex._reconciliation_pass_message(MergeStrategy.MERGE)
    assert "no excluded commit reachable" in msg


def test_squash_claim_preserves_enforce_closed_world(tmp_path: Path) -> None:
    """CRITICAL (T019): the squash ``replace`` may only relax ``verify_reachability``.
    Stripping ``enforce_closed_world`` (or the ``authored_blobs``) silently no-ops the
    P0 #5013 content axis — the squash gate would then pass vacuously."""
    repo, _base, _tips = _make_repo(tmp_path)
    captured = ApprovedWpCommitSet(
        approved={"WP01": ("abc123",)},
        manifest_wp_ids=frozenset({"WP01"}),
        excluded_window_base="base",
        enforce_closed_world=True,
        authored_blobs=frozenset({("src/a.py", "blob1")}),
        verify_reachability=True,
    )
    state = _state(repo)
    run = _run(repo, state, _manifest(), strategy=MergeStrategy.SQUASH)
    run.approved_wp_set = captured

    claim = ex._reconciliation_claim_for_gate(run)
    assert claim.verify_reachability is False  # squash defers SHA/patch-id reachability
    assert claim.enforce_closed_world is True  # the P0 content axis stays armed
    assert claim.authored_blobs == captured.authored_blobs


def test_merge_claim_keeps_verify_reachability(tmp_path: Path) -> None:
    """Merge/rebase use the captured per-SHA claim verbatim (Tier-0 clean merge)."""
    repo, _base, _tips = _make_repo(tmp_path)
    captured = ApprovedWpCommitSet(
        approved={"WP01": ("abc123",)},
        manifest_wp_ids=frozenset({"WP01"}),
        excluded_window_base="base",
        enforce_closed_world=True,
        verify_reachability=True,
    )
    state = _state(repo)
    run = _run(repo, state, _manifest(), strategy=MergeStrategy.MERGE)
    run.approved_wp_set = captured
    claim = ex._reconciliation_claim_for_gate(run)
    assert claim.verify_reachability is True
    assert claim.enforce_closed_world is True


# ---------------------------------------------------------------------------
# Deviation-3 P0 verification — does the squash content axis ATTRIBUTE on a REAL
# coord-topology PRODUCTION merge? (reuses the terminus real-CLI harness)
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_squash_axis_attributes_on_real_coord_production_merge(tmp_path: Path) -> None:
    """WP03 deviation-3: on a REAL coord-topology mission driven through the REAL
    ``spec-kitty merge --strategy squash`` CLI, a canceled WP's blob riding a
    carrier lane MUST be attributed (not deferred): the #5013 content axis FAILs,
    the target is rolled back, the command exits non-zero, and the leaked commit is
    NOT reachable from the target. A deferral (the feared production hole) would exit
    0 with the blob shipped, failing this test."""
    from tests.terminus.conftest import (
        build_coord_mission,
        plant_canceled_commit,
        run_terminus,
        sha_reachable,
    )

    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M5WP05")
    canceled_sha, _pid, _planted_path = plant_canceled_commit(mission, canceled_wp="WP99", carrier_wp="WP01")

    result = run_terminus(mission, ["merge", "--mission", mission.slug, "--strategy", "squash", "--yes"])

    assert result.returncode != 0, (
        "a squash merge that would ship a canceled WP's blob must REFUSE/FAIL "
        f"(axis attributed) — instead it exited 0.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert not sha_reachable(mission.repo, canceled_sha, mission.target_branch), (
        "the canceled commit is reachable from the target after a non-zero merge — rollback did not fire"
    )
