"""Coord-commit integrity — misroute guard (T003), porcelain root (T004), and
the real-repo e2e (T005) for coord-commit-integrity WP01 (FR-002, NFR-001).

**Landing note (2026-08, `tests/regression/` campsite clean).** These
invariants are already fixed and green; this is a permanent regression guard,
not a red-first reproduction, so it carries no `regression` marker and lives
with its sibling coord-commit / workflow tests here rather than in
`tests/regression/`. FR-002/NFR-001 kept as history below.

Scope (WP01-owned invariants only — paula): the misroute-to-legacy fail-loud
guard, the legacy porcelain pre-check running in the checkout the commit runs in
(the placement seam's status checkout since #7633, never a directory picked by existence), a
status event committing to the coord worktree (not the target branch), the
``SafeCommitHeadMismatch`` negative case, and a regression proving the MODERN
transaction path still threads the coord worktree root with ZERO code change.

The review-cycle-PRIMARY placement assertion is WP03-owned and deliberately NOT
here (an xfail would never flip inside WP01's lane).

Anti-stub guard (renata, binding): this module contains NO monkeypatch/Mock of
``safe_commit``, ``CoordinationWorkspace.resolve``, or git plumbing in the e2e
tests, and performs NO test-side commit of mission artifacts — every commit is
driven through the real CLI / production helpers, asserted via ``git show``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mission_runtime import CommitTarget, MissionArtifactKind
from specify_cli import app as root_app
from specify_cli.cli.commands.agent import workflow
from specify_cli.core.commit_guard import GuardCapability
from specify_cli.git.commit_helpers import SafeCommitHeadMismatch, SafeCommitPathPolicyError, safe_commit
from specify_cli.status import RollbackPoint
from tests.characterization.test_trio_json_envelope import _build_mission_repo

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _git_show(repo: Path, ref: str, path: str) -> str | None:
    """Return ``git show <ref>:<path>`` content, or ``None`` if the path is
    absent on that ref. Reads committed tree state — NOT the filesystem."""
    result = subprocess.run(
        ["git", "-C", str(repo), "show", f"{ref}:{path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout


# ---------------------------------------------------------------------------
# T003 — FR-002(a) misroute-to-legacy fail-loud guard
# ---------------------------------------------------------------------------


def test_incomplete_triple_coord_topology_fails_loud_never_reaches_legacy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A coord-routed topology with an INCOMPLETE identity triple fails loud.

    RED-first: pre-guard, ``_commit_workflow_change`` falls through to
    ``_commit_via_legacy_safe_commit`` (committing coord paths from
    ``repo_root``) whenever ``_load_coord_branch_meta`` returns a partial
    triple. This stubs the seam + meta so ``coord_branch`` is present but
    ``mission_id``/``mid8`` are ``None`` and asserts the commit fails loud
    WITHOUT reaching the legacy leaf.
    """
    import mission_runtime

    feature_dir = tmp_path / "kitty-specs" / "001-demo"
    feature_dir.mkdir(parents=True)
    events_path = feature_dir / "status.events.jsonl"
    status_path = feature_dir / "status.json"
    events_path.write_text('{"event_id":"before"}\n', encoding="utf-8")
    status_path.write_text('{"before":true}\n', encoding="utf-8")

    class _StubSeam:
        def __init__(self, repo_root: Path, mission_slug: str) -> None:
            del repo_root, mission_slug

        def write_target(self, kind: MissionArtifactKind) -> CommitTarget:
            return CommitTarget(ref="kitty/mission-demo-coord")

        def read_dir(self, kind: MissionArtifactKind) -> Path:
            return tmp_path / "primary-meta-dir"

    monkeypatch.setattr(mission_runtime, "placement_seam", _StubSeam)
    # Coord topology declared, but identity is incomplete (id/mid8 unresolved).
    monkeypatch.setattr(
        workflow, "_load_coord_branch_meta", lambda _fd: ("kitty/mission-demo-coord", None, None)
    )

    legacy_calls: list[dict[str, object]] = []

    def _spy_legacy(**kwargs: object) -> None:
        legacy_calls.append(kwargs)

    monkeypatch.setattr(workflow, "_commit_via_legacy_safe_commit", _spy_legacy)
    workflow._reset_workflow_receipts()

    import typer

    with pytest.raises(typer.Exit) as exc_info:
        workflow._commit_workflow_change(
            repo_root=tmp_path,
            mission_slug="001-demo",
            target_branch="whatever",
            paths=[events_path, status_path],
            message="chore: WP01 review claim",
            operation="for_review -> in_review for WP01",
            wp_id="WP01",
            rollback_point=RollbackPoint(
                events_path=events_path,
                status_path=status_path,
                pre_event_size=len('{"event_id":"before"}\n'),
                pre_status_bytes=b'{"before":true}\n',
                events_existed=True,
            ),
        )

    assert exc_info.value.exit_code == 1
    assert legacy_calls == [], (
        "misroute guard failed: a coord-routed topology with an incomplete triple "
        "reached _commit_via_legacy_safe_commit and would commit coord paths from "
        "repo_root (the #2861 silent-misroute class)."
    )


def test_complete_triple_still_routes_modern_not_guarded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guard is narrow: a COMPLETE coord triple still routes to the modern
    transaction path (the guard only fires on the incomplete-triple misroute)."""
    import mission_runtime

    feature_dir = tmp_path / "kitty-specs" / "001-demo"
    feature_dir.mkdir(parents=True)
    (feature_dir / "status.events.jsonl").write_text("{}\n", encoding="utf-8")
    (feature_dir / "status.json").write_text("{}\n", encoding="utf-8")

    class _StubSeam:
        def __init__(self, repo_root: Path, mission_slug: str) -> None:
            del repo_root, mission_slug

        def write_target(self, kind: MissionArtifactKind) -> CommitTarget:
            return CommitTarget(ref="kitty/mission-demo-coord")

        def read_dir(self, kind: MissionArtifactKind) -> Path:
            return tmp_path / "primary-meta-dir"

    monkeypatch.setattr(mission_runtime, "placement_seam", _StubSeam)
    monkeypatch.setattr(
        workflow,
        "_load_coord_branch_meta",
        lambda _fd: ("kitty/mission-demo-coord", "01KY5JS8ABCDEFGHJKMNPQRSTV", "01KY5JS8"),
    )

    modern_calls: list[dict[str, object]] = []

    class _Receipt:
        commit_sha = "deadbeef"

    def _spy_modern(**kwargs: object) -> _Receipt:
        modern_calls.append(kwargs)
        return _Receipt()

    monkeypatch.setattr(workflow, "_commit_via_coordination_transaction", _spy_modern)
    workflow._reset_workflow_receipts()

    workflow._commit_workflow_change(
        repo_root=tmp_path,
        mission_slug="001-demo",
        target_branch="whatever",
        paths=[feature_dir / "status.events.jsonl"],
        message="chore: WP01 review claim",
        operation="for_review -> in_review for WP01",
        wp_id="WP01",
        rollback_point=RollbackPoint(
            events_path=feature_dir / "status.events.jsonl",
            status_path=feature_dir / "status.json",
            pre_event_size=3,
            pre_status_bytes=b"{}\n",
            events_existed=True,
        ),
    )

    assert len(modern_calls) == 1, "a complete coord triple must route to the modern path"


# ---------------------------------------------------------------------------
# T004 — FR-002(b) legacy pre-check asks the checkout the commit runs in (#7633)
# ---------------------------------------------------------------------------


def _commit_in(checkout: Path, path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    _git(checkout, "add", "-f", str(path))
    _git(checkout, "commit", "-q", "-m", "status already committed")
    return _git(checkout, "rev-parse", "HEAD").stdout.strip()


@pytest.mark.non_sandbox
def test_legacy_leaf_commits_in_the_seam_checkout_holding_the_topic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#7633: the legacy leaf's pre-check and commit run in the placement seam's status checkout.

    A default Mission whose topic branch another (non-lane) checkout holds, with its Mission
    directory: the transactional emit committed the status rows there. The follow-up must find
    them committed in that checkout and record that commit; it must not ask, or commit in, the
    repository root checkout (which is not on the topic branch: a HEAD mismatch before #7633).
    """
    from tests.specify_cli.cli.commands.agent.test_finalize_topology_settlement import make_default_mission

    monkeypatch.chdir(Path(__file__).resolve().parents[5])
    mission = make_default_mission(tmp_path, ("src/one.py", "src/two.py"))
    holder = tmp_path / "operator"
    _git(mission.root, "checkout", "-q", "--detach")
    _git(mission.root, "worktree", "add", "-q", str(holder), mission.topic)
    events = holder / "kitty-specs" / mission.slug / "status.events.jsonl"
    expected = _commit_in(holder, events, '{"event_id":"claim-already-committed"}\n')

    workflow._reset_workflow_receipts()
    workflow._commit_via_legacy_safe_commit(
        repo_root=mission.root,
        target_branch=mission.topic,
        paths=[events],
        message="chore: Start WP01 review [claude]",
        wp_id="WP01",
        mission_slug=mission.slug,
    )

    receipts = workflow._WORKFLOW_COMMIT_RECEIPTS
    assert [(r["outcome"], r["destination_ref"], r["sha"]) for r in receipts] == [("committed", mission.topic, expected)]
    assert _git(holder, "rev-parse", "HEAD").stdout.strip() == expected, "no empty commit may land"
    workflow._reset_workflow_receipts()


def test_legacy_precheck_never_reports_a_nested_checkout_path_as_committed(tmp_path: Path) -> None:
    """#2684 phantom guard, kept without a directory probe: a path inside a nested registered
    checkout reads CLEAN from the repository root checkout, so the pre-check must not short-cut
    on it; the commit then runs and fails loudly instead of recording a receipt for state that
    never landed on the target."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "target")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "T")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")
    nested = repo / ".worktrees" / "elsewhere"
    _git(repo, "worktree", "add", "-q", "-b", "elsewhere", str(nested))
    fresh = nested / "kitty-specs" / "m" / "status.events.jsonl"
    fresh.parent.mkdir(parents=True)
    fresh.write_text('{"event":"fresh-write"}\n', encoding="utf-8")
    head_before = _git(repo, "rev-parse", "HEAD").stdout.strip()

    workflow._reset_workflow_receipts()
    with pytest.raises(SafeCommitPathPolicyError):
        workflow._commit_via_legacy_safe_commit(
            repo_root=repo,
            target_branch="target",
            paths=[fresh],
            message="chore: WP01 claimed [claude]",
            wp_id="WP01",
        )
    assert not [r for r in workflow._WORKFLOW_COMMIT_RECEIPTS if r["outcome"] == "committed"]
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == head_before
    workflow._reset_workflow_receipts()


# ---------------------------------------------------------------------------
# T005 — NFR-001 real-repo e2e (no stubbed safe_commit)
# ---------------------------------------------------------------------------


@pytest.mark.git_repo
def test_safe_commit_rejects_worktree_destination_mismatch(tmp_path: Path) -> None:
    """NFR-001 negative case: ``safe_commit`` with ``worktree_root`` HEAD !=
    ``destination_ref`` raises ``SafeCommitHeadMismatch`` — the misroute
    (committing a coord ref from a repo_root checked out to the target branch)
    is unrepresentable at commit. Real git; no stubs."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "target-branch")
    _git(repo, "config", "user.email", "e2e@example.invalid")
    _git(repo, "config", "user.name", "E2E")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")
    # A coord-style destination ref that exists but is NOT the checked-out HEAD.
    _git(repo, "branch", "kitty/mission-demo-coord")

    payload = repo / "kitty-specs" / "demo" / "status.events.jsonl"
    payload.parent.mkdir(parents=True)
    payload.write_text('{"event":"x"}\n', encoding="utf-8")

    with pytest.raises(SafeCommitHeadMismatch):
        safe_commit(
            repo_root=repo,
            worktree_root=repo,  # HEAD == target-branch, NOT the destination
            target=CommitTarget(ref="kitty/mission-demo-coord"),
            message="chore: misrouted coord commit",
            paths=(payload,),
            capability=GuardCapability.STANDARD,
        )


@pytest.mark.git_repo
def test_status_event_commits_to_coord_not_target_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Modern-path regression (NO code change): a coord-topology status
    transition commits to the COORD worktree/branch — proving the modern
    transaction threads the coord worktree root — and is ABSENT on the target
    branch. Asserted via ``git show <ref>:<path>``, not filesystem state."""
    monkeypatch.setenv("SPEC_KITTY_SYNC_MINIMAL_IMPORT", "1")
    repo_root, mission_dirname = _build_mission_repo(
        tmp_path,
        monkeypatch,
        coord=True,
        mission_slug="trio-coord-review",
        wp_lane="for_review",
        materialize_coord=True,
    )
    mid8 = mission_dirname.rsplit("-", 1)[1]
    coord_branch = f"kitty/mission-trio-coord-review-{mid8}"
    target_branch = "trio-integration"
    events_rel = f"kitty-specs/{mission_dirname}/status.events.jsonl"

    # Drive the REAL review claim (for_review -> in_review). The transactional
    # emit commits the transition to the coord worktree before the follow-up
    # workflow commit; the modern path threading the coord root is what lands
    # the event on the coord branch.
    runner.invoke(
        root_app,
        [
            "agent",
            "action",
            "review",
            "WP01",
            "--mission",
            mission_dirname,
            "--agent",
            "claude:opus:reviewer-renata:reviewer",
        ],
    )

    coord_events = _git_show(repo_root, coord_branch, events_rel)
    target_events = _git_show(repo_root, target_branch, events_rel)

    assert coord_events is not None, "status.events.jsonl must exist on the coord branch"
    assert "in_review" in coord_events, (
        "the review claim's in_review transition must be committed to the COORD "
        "branch (modern path threads the coord worktree root)"
    )
    assert target_events is not None, "the seeded events file exists on the target branch"
    assert "in_review" not in target_events, (
        "the coord status transition leaked onto the target branch — the modern "
        "path must commit status state to the coord worktree only"
    )
