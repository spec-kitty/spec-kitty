"""Scope: #1826 coord-worktree resync after merge-pipeline ref advances (WP03).

ATDD-first (C-011) regression pin for #1826 / FR-001. Stage-1 lane→mission
merges and mission-number baking advance ``refs/heads/<mission-branch>`` via
``git update-ref`` from detached temp worktrees. ``update-ref`` bypasses git's
checked-out-branch protection, so the coordination worktree (which has that
branch checked out) is left with an index/working tree *behind its own HEAD*.
The next bookkeeping safe-commit through that worktree
(``_record_merged_wps_done_for_merge`` → ``BookkeepingTransaction`` →
``safe_commit``) then sees phantom staged deletions and aborts with
``SafeCommitBackstopError`` — breaking every unattended coord-topology merge
with more than one ref advance before bookkeeping.

Covered acceptance criteria (contracts/class-b-ref-advance-resync.md):

* **AC-B1** — an end-to-end coord-topology merge (≥2 lane WPs + mission-number
  baking) completes unattended: the real ``_record_merged_wps_done_for_merge``
  commits with NO ``SafeCommitBackstopError`` and zero manual git
  interventions (NFR-001).
* **AC-B2** — after the merge pipeline's ref advances, the coordination
  worktree's HEAD equals the branch tip AND ``git status --porcelain`` is
  clean (direct unit assertions on ``advance_branch_ref`` plus end-state
  assertions on the integration fixture).
* **AC-B4** — a dirty coordination worktree produces a loud structured
  refusal (``RefAdvanceDirtyWorktreeError``), no data is discarded
  (NFR-002/NFR-003), and the merge stays resumable.

These tests drive the REAL ``consolidate_lane_into_mission`` /
``integrate_mission_into_target`` / ``_merge_branch_into`` /
``_bake_mission_number_into_mission_branch`` /
``_record_merged_wps_done_for_merge`` functions against a real on-disk git
repository with a real coordination worktree. They mock ONLY side effects
that touch state outside git (dossier sync, SaaS emit, stale-assertion check,
sparse-checkout preflight, merge gates, post-merge working-tree invariant).
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from kernel.clock import now_utc_iso
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

# Import the status package before any coordination submodule. The production
# CLI entrypoint (``specify_cli/__init__``) imports ``status`` before ``merge``;
# importing ``merge`` first (as a test module does) would otherwise reach
# ``coordination/__init__`` -> ``transaction`` -> ``status`` mid-initialization
# and trip a known import-order cycle. Mirroring the production order here keeps
# this regression test importable under ``PYTHONPATH=src``.
import specify_cli.status  # noqa: F401  # import-order guard (see comment above)

from specify_cli.cli.commands.merge import _run_lane_based_merge
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.git.ref_advance import (
    RefAdvanceDirtyWorktreeError,
    advance_branch_ref,
)
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.merge.config import MergeStrategy

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=True,
        capture_output=True,
        text=True,
    )


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
    """Return True iff *relpath* exists on *branch* (via ``git ls-tree``)."""
    result = subprocess.run(
        ["git", "-C", str(repo), "ls-tree", "--name-only", "-r", branch, "--", relpath],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and relpath in result.stdout.splitlines()


def _rev_parse(repo: Path, ref: str) -> str:
    return _git(repo, "rev-parse", ref).stdout.strip()


def _porcelain(worktree: Path) -> str:
    return _git(worktree, "status", "--porcelain").stdout


# ---------------------------------------------------------------------------
# Coord-topology fixture (#1826: slug ends with -<mid8> so the coordination
# branch IS the lanes-manifest mission branch — the production 083+ layout)
# ---------------------------------------------------------------------------

MID8 = "01HXRESY"
MISSION_ID = "01HXRESYNC0000000000001826"
MISSION_SLUG = f"coord-resync-1826-{MID8}"
COORD_BRANCH = f"kitty/mission-{MISSION_SLUG}"

_WP_IDS = ("WP01", "WP02")
_LANE_FILES = {
    "lane-a": "src/feature_a.py",
    "lane-b": "src/feature_b.py",
}


def _write_meta(feature_dir: Path) -> None:
    """meta.json declaring a coordination_branch (coord-topology mission)."""
    meta = {
        "mission_slug": MISSION_SLUG,
        "mission_id": MISSION_ID,
        "mid8": MID8,
        "mission_number": None,  # pre-merge: baking assigns it during merge
        "mission_type": "software-dev",
        "target_branch": "main",
        "coordination_branch": COORD_BRANCH,
        "purpose_tldr": "coord-worktree resync regression (#1826)",
        "purpose_context": "unattended merge must survive >1 ref advance",
    }
    (feature_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_manifest(feature_dir: Path) -> LanesManifest:
    """Two code lanes (≥2 Stage-1 ref advances before bookkeeping)."""
    manifest = LanesManifest(
        version=1,
        mission_slug=MISSION_SLUG,
        # mission_id == slug => legacy lane_branch_name form
        # ``kitty/mission-<slug>-lane-<id>`` which consolidate_lane_into_mission constructs.
        mission_id=MISSION_SLUG,
        mission_branch=COORD_BRANCH,
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=("WP01",),
                write_scope=(_LANE_FILES["lane-a"],),
                predicted_surfaces=("code",),
                depends_on_lanes=(),
                parallel_group=0,
            ),
            ExecutionLane(
                lane_id="lane-b",
                wp_ids=("WP02",),
                write_scope=(_LANE_FILES["lane-b"],),
                predicted_surfaces=("code",),
                depends_on_lanes=(),
                parallel_group=0,
            ),
        ],
        computed_at=now_utc_iso(),
        computed_from="test-fixture",
    )
    write_lanes_json(feature_dir, manifest)
    return manifest


def _write_wp_file(feature_dir: Path, wp_id: str) -> None:
    (feature_dir / "tasks" / f"{wp_id}-work.md").write_text(
        "---\n"
        f"work_package_id: {wp_id}\n"
        f"title: {wp_id} work\n"
        "agent: implementer-bot\n"
        "review_status: approved\n"
        "reviewed_by: reviewer-bot\n"
        "---\n"
        f"# {wp_id}\n",
        encoding="utf-8",
    )


def _approved_event(wp_id: str, suffix: str) -> dict[str, object]:
    return {
        "actor": "reviewer-bot",
        "at": now_utc_iso(),
        "event_id": f"01HXYZAPPR00000000000000{suffix}",
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": MISSION_SLUG,
        "force": False,
        "from_lane": "in_review",
        "reason": None,
        "review_ref": f"review-{wp_id}",
        "to_lane": "approved",
        "wp_id": wp_id,
    }


def _bootstrap_coord_mission(repo: Path) -> Path:
    """Bootstrap a coord-topology mission with two code lanes + coord worktree.

    Returns the primary-checkout feature_dir.
    """
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    _write_meta(feature_dir)
    _write_manifest(feature_dir)
    for wp_id in _WP_IDS:
        _write_wp_file(feature_dir, wp_id)

    # Pre-record per-WP APPROVED events (not done) so the real bookkeeping pass
    # has real done transitions to emit through the coordination worktree.
    (feature_dir / "status.events.jsonl").write_text(
        "".join(
            json.dumps(_approved_event(wp_id, str(idx + 1)), sort_keys=True) + "\n"
            for idx, wp_id in enumerate(_WP_IDS)
        ),
        encoding="utf-8",
    )

    # A tracked file the dirty-refusal test can modify inside the coord worktree.
    (feature_dir / "notes.md").write_text("clean\n", encoding="utf-8")

    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({MISSION_SLUG}): bootstrap coord mission")

    # Coordination/mission branch at the current tip.
    _git(repo, "branch", COORD_BRANCH)

    # Two lane branches, each with a REAL code diff not on the mission branch.
    for lane_id, relpath in _LANE_FILES.items():
        lane_branch = f"kitty/mission-{MISSION_SLUG}-{lane_id}"
        _git(repo, "branch", lane_branch, COORD_BRANCH)
        _git(repo, "checkout", lane_branch)
        code_path = repo / relpath
        code_path.parent.mkdir(parents=True, exist_ok=True)
        code_path.write_text(
            f"def feature_{lane_id.replace('-', '_')}() -> int:\n    return 1826\n",
            encoding="utf-8",
        )
        _git(repo, "add", relpath)
        _git(repo, "commit", "-m", f"feat({MISSION_SLUG}): {lane_id} code")
        _git(repo, "checkout", "main")

    # The coordination worktree with the mission branch CHECKED OUT — the
    # production topology in which #1826 reproduces. Every Stage-1 ref advance
    # and the mission-number bake move this branch underneath the worktree.
    CoordinationWorkspace.resolve(repo, MISSION_SLUG, MID8)

    return feature_dir


def _coord_worktree(repo: Path) -> Path:
    return CoordinationWorkspace.worktree_path(repo, MISSION_SLUG, MID8)


@contextlib.contextmanager
def _merge_external_mocks():
    """Mock ONLY side effects outside git/status bookkeeping.

    Deliberately REAL (unlike test_merge_coord_topology_1772):
    ``_bake_mission_number_into_mission_branch`` (third update-ref site),
    ``_record_merged_wps_done_for_merge`` / ``_mark_wp_merged_done`` (the
    bookkeeping pass whose safe-commit backstop trips on #1826), and
    ``_assert_merged_wps_reached_done``.
    """
    patches = {
        "run_check": patch("specify_cli.merge.executor.run_check"),
        "sparse": patch("specify_cli.merge.executor.require_no_sparse_checkout"),
        "preflight": patch("specify_cli.cli.commands.merge._enforce_git_preflight"),
        "review_consistency": patch(
            "specify_cli.merge.executor._enforce_review_artifact_consistency"
        ),
        "status_history": patch(
            "specify_cli.merge.executor._enforce_canonical_status_history"
        ),
        "hollow": patch("specify_cli.merge.executor._warn_or_confirm_hollow_reviews"),
        "baseline_record": patch(
            "specify_cli.merge.executor._record_baseline_merge_commit",
        ),
        "baseline_assert": patch(
            "specify_cli.merge.executor._assert_baseline_merge_commit_on_target"
        ),
        "done_on_target": patch(
            "specify_cli.merge.executor._assert_merged_wps_done_on_target"
        ),
        "safe_commit": patch("specify_cli.merge.executor.commit_merge_bookkeeping"),
        "refresh_primary": patch(
            "specify_cli.merge.executor._refresh_primary_checkout_after_merge"
        ),
        # Post-merge working-tree invariant fires on test-only files; the merge
        # has already run through real git by the time this would raise.
        "porcelain": patch(
            "specify_cli.merge.executor._classify_porcelain_lines",
            return_value=([], 0),
        ),
        "gates": patch("specify_cli.policy.merge_gates.evaluate_merge_gates"),
        "policy": patch("specify_cli.policy.config.load_policy_config"),
        "remote": patch("specify_cli.merge.executor.has_remote", return_value=False),
    }
    with contextlib.ExitStack() as stack:
        mocks = {name: stack.enter_context(p) for name, p in patches.items()}

        def _record_baseline_merge_commit(
            feature_dir: Path,
            baseline_commit: str,
            *,
            mission_id: str | None = None,
        ) -> Path:
            meta_path = feature_dir / "meta.json"
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["baseline_merge_commit"] = baseline_commit
            if mission_id is not None:
                meta["mission_id"] = mission_id
            meta_path.write_text(
                json.dumps(meta, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            return meta_path

        def _safe_commit_no_worktrees_paths(**kwargs: object) -> MagicMock:
            paths = kwargs.get("paths", ())
            assert isinstance(paths, tuple)
            offending = [str(path) for path in paths if ".worktrees" in Path(path).parts]
            assert offending == [], (
                "final target bookkeeping safe_commit must not stage "
                f"coordination-worktree paths: {offending!r}"
            )
            result = MagicMock()
            result.sha = "0" * 40
            return result

        mocks["baseline_record"].side_effect = _record_baseline_merge_commit
        mocks["safe_commit"].side_effect = _safe_commit_no_worktrees_paths
        gate_eval = MagicMock()
        gate_eval.overall_pass = True
        gate_eval.gates = []
        mocks["gates"].return_value = gate_eval
        policy = MagicMock()
        policy.merge_gates = []
        mocks["policy"].return_value = policy
        stale_report = MagicMock()
        stale_report.findings = []
        mocks["run_check"].return_value = stale_report
        yield mocks


def _run_merge(repo: Path) -> None:
    _run_lane_based_merge(
        repo_root=repo,
        mission_slug=MISSION_SLUG,
        push=False,
        delete_branch=False,
        remove_worktree=False,
        strategy=MergeStrategy.SQUASH,
        allow_sparse_checkout=True,
    )


# ---------------------------------------------------------------------------
# AC-B1 / AC-B2 — unattended end-to-end merge with a live coordination worktree
# ---------------------------------------------------------------------------


def test_merge_with_coord_worktree_completes_unattended(tmp_path: Path) -> None:
    """#1826 / AC-B1 / NFR-001: ≥2 Stage-1 ref advances + mission-number baking
    before bookkeeping must NOT abort with ``SafeCommitBackstopError``.

    On pre-fix code the lane merges and the bake advance ``COORD_BRANCH`` via
    raw ``git update-ref`` while the coordination worktree has it checked out;
    the real ``_record_merged_wps_done_for_merge`` then fails its safe-commit
    backstop with phantom staged deletions. The fix (``advance_branch_ref``)
    resyncs the coordination worktree after each advance, so the merge
    completes with zero manual git interventions.
    """
    _init_git_repo(tmp_path)
    _bootstrap_coord_mission(tmp_path)

    with _merge_external_mocks():
        _run_merge(tmp_path)  # must not raise (no SafeCommitBackstopError)

    # Both lanes' code reached the target branch.
    for relpath in _LANE_FILES.values():
        assert _file_on_branch(tmp_path, "main", relpath), (
            f"lane code {relpath} did not reach the target branch"
        )

    # AC-B2 (end state): the coordination worktree is CONSISTENT — HEAD equals
    # the branch tip and the working tree is clean.
    coord_wt = _coord_worktree(tmp_path)
    assert coord_wt.exists(), "fixture invariant: coord worktree retained"
    assert _rev_parse(coord_wt, "HEAD") == _rev_parse(tmp_path, COORD_BRANCH), (
        "#1826 regression: coordination worktree HEAD is behind its own "
        "checked-out branch after the merge pipeline's ref advances"
    )
    assert _porcelain(coord_wt) == "", (
        "#1826 regression: coordination worktree is not clean after merge — "
        f"phantom divergence remains:\n{_porcelain(coord_wt)}"
    )

    # The bake (third update-ref site) really ran: mission_number landed.
    baked = json.loads(
        _git(
            tmp_path, "show", f"main:kitty-specs/{MISSION_SLUG}/meta.json"
        ).stdout
    )
    assert baked["mission_number"] == 1, "mission-number baking did not land on target"


def test_final_bookkeeping_commit_failure_restores_uncommitted_surfaces(
    tmp_path: Path,
) -> None:
    """Final target bookkeeping failure must not leave dirty done/baseline state."""
    _init_git_repo(tmp_path)
    feature_dir = _bootstrap_coord_mission(tmp_path)
    coord_feature_dir = _coord_worktree(tmp_path) / "kitty-specs" / MISSION_SLUG

    primary_events = feature_dir / "status.events.jsonl"
    primary_status = feature_dir / "status.json"
    primary_meta = feature_dir / "meta.json"
    coord_events = coord_feature_dir / "status.events.jsonl"
    coord_status = coord_feature_dir / "status.json"

    with _merge_external_mocks() as mocks:
        mocks["safe_commit"].side_effect = RuntimeError("final bookkeeping refused")
        with pytest.raises(RuntimeError, match="final bookkeeping refused"):
            _run_merge(tmp_path)

    committed_events = _git(
        tmp_path, "show", f"HEAD:kitty-specs/{MISSION_SLUG}/status.events.jsonl"
    ).stdout.encode()
    committed_status = _git(
        tmp_path, "show", f"HEAD:kitty-specs/{MISSION_SLUG}/status.json"
    ).stdout.encode()
    committed_meta = json.loads(
        _git(tmp_path, "show", f"HEAD:kitty-specs/{MISSION_SLUG}/meta.json").stdout
    )

    assert primary_events.read_bytes() == committed_events
    assert primary_status.read_bytes() == committed_status
    assert json.loads(primary_meta.read_text(encoding="utf-8")) == committed_meta
    assert "baseline_merge_commit" not in committed_meta
    assert b'"to_lane": "done"' in coord_events.read_bytes()
    assert coord_status.exists()
    assert _git(_coord_worktree(tmp_path), "status", "--porcelain").stdout == ""

    from specify_cli.merge.state import load_state

    state = load_state(tmp_path, MISSION_ID)
    assert state is not None
    assert state.completed_wps == list(_WP_IDS)
    assert _git(
        tmp_path, "status", "--porcelain", "--", f"kitty-specs/{MISSION_SLUG}"
    ).stdout == ""


def test_post_target_invariant_failure_keeps_coord_resume_state_truthful(
    tmp_path: Path,
) -> None:
    """After target advances, rollback must not rewind committed coord done state."""
    _init_git_repo(tmp_path)
    feature_dir = _bootstrap_coord_mission(tmp_path)
    coord_feature_dir = _coord_worktree(tmp_path) / "kitty-specs" / MISSION_SLUG

    primary_events = feature_dir / "status.events.jsonl"
    primary_status = feature_dir / "status.json"
    primary_meta = feature_dir / "meta.json"
    coord_events = coord_feature_dir / "status.events.jsonl"
    coord_status = coord_feature_dir / "status.json"

    with _merge_external_mocks() as mocks:
        mocks["porcelain"].return_value = ([" M src/unexpected.py"], 0)
        with pytest.raises(typer.Exit):
            _run_merge(tmp_path)
        mocks["safe_commit"].assert_not_called()

    committed_events = _git(
        tmp_path, "show", f"HEAD:kitty-specs/{MISSION_SLUG}/status.events.jsonl"
    ).stdout.encode()
    committed_status = _git(
        tmp_path, "show", f"HEAD:kitty-specs/{MISSION_SLUG}/status.json"
    ).stdout.encode()
    committed_meta = json.loads(
        _git(tmp_path, "show", f"HEAD:kitty-specs/{MISSION_SLUG}/meta.json").stdout
    )

    assert primary_events.read_bytes() == committed_events
    assert primary_status.read_bytes() == committed_status
    assert json.loads(primary_meta.read_text(encoding="utf-8")) == committed_meta
    assert "baseline_merge_commit" not in committed_meta
    assert b'"to_lane": "done"' in coord_events.read_bytes()
    assert coord_status.exists()
    assert _git(_coord_worktree(tmp_path), "status", "--porcelain").stdout == ""

    from specify_cli.merge.state import load_state

    state = load_state(tmp_path, MISSION_ID)
    assert state is not None
    assert state.completed_wps == list(_WP_IDS)


# ---------------------------------------------------------------------------
# AC-B4 — dirty coordination worktree: loud, named, data-preserving, resumable
# ---------------------------------------------------------------------------


def test_dirty_coord_worktree_refuses_loudly_and_preserves_data(tmp_path: Path) -> None:
    """#1826 / AC-B4 / NFR-002/NFR-003: a dirty coordination worktree must
    produce a structured refusal (no ``reset --hard``), preserve the dirty
    bytes untouched, keep the merge resumable, and succeed after cleanup."""
    _init_git_repo(tmp_path)
    _bootstrap_coord_mission(tmp_path)

    coord_wt = _coord_worktree(tmp_path)
    planted = coord_wt / "kitty-specs" / MISSION_SLUG / "notes.md"
    planted.write_text("operator-evidence: do not discard\n", encoding="utf-8")

    with _merge_external_mocks(), pytest.raises(typer.Exit) as excinfo:
        _run_merge(tmp_path)
    assert excinfo.value.exit_code != 0, "dirty coord worktree must fail the merge loudly"

    # NFR-002: the dirty bytes survive untouched (no silent data discard).
    assert planted.read_text(encoding="utf-8") == "operator-evidence: do not discard\n", (
        "#1826 NFR-002 regression: dirty coordination worktree content was discarded"
    )

    # The merge stays resumable: the persisted merge state was preserved.
    from specify_cli.merge.state import load_state

    resumable = load_state(tmp_path)
    assert resumable is not None and resumable.mission_slug == MISSION_SLUG, (
        "dirty-worktree refusal must leave the merge state resumable"
    )

    # Operator cleans the worktree; the resumed merge completes.
    _git(coord_wt, "checkout", "--", f"kitty-specs/{MISSION_SLUG}/notes.md")
    with _merge_external_mocks():
        _run_merge(tmp_path)
    for relpath in _LANE_FILES.values():
        assert _file_on_branch(tmp_path, "main", relpath), (
            f"resumed merge did not integrate lane code {relpath}"
        )


# ---------------------------------------------------------------------------
# AC-B2 / AC-B4 unit coverage — advance_branch_ref invariant helper
# ---------------------------------------------------------------------------


def _setup_branch_with_worktree(repo: Path) -> tuple[str, Path, str]:
    """Create branch ``topic`` checked out in a linked worktree; return
    (branch, worktree_path, advanced_sha) where advanced_sha is a new commit
    on ``topic`` created from a detached temp worktree (the merge-pipeline
    pattern)."""
    branch = "topic"
    _git(repo, "branch", branch)
    wt = repo / ".worktrees" / "topic-wt"
    wt.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "worktree", "add", str(wt), branch)

    detached = repo / ".worktrees" / "detached-tmp"
    _git(repo, "worktree", "add", "--detach", str(detached), branch)
    (detached / "advanced.txt").write_text("advanced\n", encoding="utf-8")
    _git(detached, "add", "advanced.txt")
    _git(detached, "commit", "-m", "advance")
    new_sha = _rev_parse(detached, "HEAD")
    _git(repo, "worktree", "remove", str(detached), "--force")
    return branch, wt, new_sha


def test_advance_branch_ref_resyncs_clean_checked_out_worktree(tmp_path: Path) -> None:
    """AC-B2: after the advance, the checked-out worktree's HEAD, index, and
    working tree match the new branch tip."""
    _init_git_repo(tmp_path)
    branch, wt, new_sha = _setup_branch_with_worktree(tmp_path)

    advance_branch_ref(tmp_path, branch, new_sha)

    assert _rev_parse(tmp_path, branch) == new_sha
    assert _rev_parse(wt, "HEAD") == new_sha, "worktree HEAD must match the new tip"
    assert (wt / "advanced.txt").exists(), "working tree must carry the advanced content"
    assert _porcelain(wt) == "", "worktree must be CONSISTENT (clean) after resync"


def test_advance_branch_ref_dirty_worktree_refuses_with_structured_error(
    tmp_path: Path,
) -> None:
    """AC-B4: tracked local modifications refuse the advance with a structured
    error naming worktree/ref/SHAs/dirty entries; nothing is reset."""
    _init_git_repo(tmp_path)
    branch, wt, new_sha = _setup_branch_with_worktree(tmp_path)
    old_sha = _rev_parse(tmp_path, branch)
    (wt / "README.md").write_text("local uncommitted evidence\n", encoding="utf-8")

    with pytest.raises(RefAdvanceDirtyWorktreeError) as excinfo:
        advance_branch_ref(tmp_path, branch, new_sha)

    err = excinfo.value
    assert err.worktree_path == wt.resolve()
    assert err.branch == branch
    assert err.old_sha == old_sha
    assert err.new_sha == new_sha
    assert any("README.md" in entry for entry in err.dirty_entries)
    message = str(err)
    assert str(wt.resolve()) in message
    assert branch in message
    assert "README.md" in message

    # NFR-002: nothing was reset — the ref did not advance and the dirty
    # bytes are untouched.
    assert _rev_parse(tmp_path, branch) == old_sha, (
        "refusal must leave the ref un-advanced (atomic refusal)"
    )
    assert (wt / "README.md").read_text(encoding="utf-8") == (
        "local uncommitted evidence\n"
    )


def test_advance_branch_ref_untracked_files_do_not_block_or_vanish(
    tmp_path: Path,
) -> None:
    """Non-obstructing untracked files survive ``reset --hard`` and do not block."""
    _init_git_repo(tmp_path)
    branch, wt, new_sha = _setup_branch_with_worktree(tmp_path)
    untracked = wt / "scratch.txt"
    untracked.write_text("scratch\n", encoding="utf-8")

    advance_branch_ref(tmp_path, branch, new_sha)

    assert _rev_parse(wt, "HEAD") == new_sha
    assert untracked.read_text(encoding="utf-8") == "scratch\n", (
        "untracked content must survive the resync"
    )


def test_advance_branch_ref_obstructing_untracked_file_refuses_before_reset(
    tmp_path: Path,
) -> None:
    """NFR-002: ``reset --hard`` overwrites untracked paths that obstruct the
    target tree, so the helper must refuse before advancing the ref."""
    _init_git_repo(tmp_path)
    branch, wt, new_sha = _setup_branch_with_worktree(tmp_path)
    old_sha = _rev_parse(tmp_path, branch)
    obstruction = wt / "advanced.txt"
    obstruction.write_text("operator evidence must survive\n", encoding="utf-8")

    with pytest.raises(RefAdvanceDirtyWorktreeError) as excinfo:
        advance_branch_ref(tmp_path, branch, new_sha)

    assert _rev_parse(tmp_path, branch) == old_sha, (
        "refusal must leave the ref un-advanced"
    )
    assert obstruction.read_text(encoding="utf-8") == (
        "operator evidence must survive\n"
    )
    assert any("advanced.txt" in entry for entry in excinfo.value.dirty_entries)
    assert "would be overwritten" in str(excinfo.value)


def _setup_branch_with_dossier_snapshot_drift(
    repo: Path,
) -> tuple[str, Path, str, Path]:
    """Branch ``topic`` checked out in a worktree carrying dossier-snapshot drift.

    Reproduces the FIX-M2-05 ``spec-kitty merge`` failure shape: the
    coordination worktree's checked-out branch already has a committed
    ``.kittify/dossiers/<mission>/snapshot-latest.json`` (the state a
    pre-fix ``finalize-tasks`` -- see ``mission_finalize.py`` --
    ``_collect_finalize_artifacts`` produced by treating the dossier snapshot
    as a commit candidate, violating ``contracts/dossier-snapshot-ownership.md``
    D1), and a later fire-and-forget dossier-sync write
    (``save_snapshot()``, never staged/committed by design) leaves that
    worktree's copy locally modified when the merge pipeline tries to
    fast-forward the branch underneath it.
    """
    branch = "topic"
    _git(repo, "branch", branch)
    wt = repo / ".worktrees" / "topic-wt"
    wt.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "worktree", "add", str(wt), branch)

    snapshot_rel = Path(
        "kitty-specs/some-mission/.kittify/dossiers/some-mission/snapshot-latest.json"
    )
    (wt / snapshot_rel).parent.mkdir(parents=True, exist_ok=True)
    (wt / snapshot_rel).write_text('{"v": 1}\n', encoding="utf-8")
    _git(wt, "add", str(snapshot_rel))
    _git(wt, "commit", "-m", "chore: seed dossier snapshot (pre-fix committed state)")

    detached = repo / ".worktrees" / "detached-tmp"
    _git(repo, "worktree", "add", "--detach", str(detached), branch)
    (detached / "advanced.txt").write_text("advanced\n", encoding="utf-8")
    _git(detached, "add", "advanced.txt")
    _git(detached, "commit", "-m", "advance")
    new_sha = _rev_parse(detached, "HEAD")
    _git(repo, "worktree", "remove", str(detached), "--force")

    # A subsequent dossier-sync re-write (mark-status/move-task/merge all
    # trigger it) leaves the checked-out worktree's copy locally modified —
    # save_snapshot() never stages or commits its own write (D1/D2).
    (wt / snapshot_rel).write_text('{"v": 2}\n', encoding="utf-8")
    return branch, wt, new_sha, snapshot_rel


def test_advance_branch_ref_dossier_snapshot_drift_blocks_without_residue_exemption(
    tmp_path: Path,
) -> None:
    """RED baseline: without an injected ``is_residue``, dossier-snapshot drift
    in the checked-out worktree blocks the advance like any other tracked
    modification -- documents WHY the exemption is needed, not a claim that
    production callers omit it (they all inject
    ``is_toolchain_generated_churn`` -- see the GREEN test below)."""
    _init_git_repo(tmp_path)
    branch, wt, new_sha, snapshot_rel = _setup_branch_with_dossier_snapshot_drift(
        tmp_path
    )

    with pytest.raises(RefAdvanceDirtyWorktreeError) as excinfo:
        advance_branch_ref(tmp_path, branch, new_sha)

    assert any(
        snapshot_rel.name in entry for entry in excinfo.value.dirty_entries
    )


def test_advance_branch_ref_dossier_snapshot_drift_does_not_block_with_residue_exemption(
    tmp_path: Path,
) -> None:
    """FIX-M2-05 / GREEN: with the real production ``is_residue`` injection
    (``is_toolchain_generated_churn``, exactly as every ``advance_branch_ref``
    call site in the merge pipeline passes it -- ``lanes/merge.py``,
    ``merge/ordering.py``, ``coordination/commit_router.py``), dossier-snapshot
    drift in the checked-out worktree does NOT block the advance. Closes the
    reported ``spec-kitty merge`` failure: 'Refusing to advance branch ...
    the worktree at .../-coord has it checked out and holds uncommitted local
    changes ... snapshot-latest.json' (#1826 / FIX-M2-05)."""
    from specify_cli.coordination.coherence import is_toolchain_generated_churn

    _init_git_repo(tmp_path)
    branch, wt, new_sha, snapshot_rel = _setup_branch_with_dossier_snapshot_drift(
        tmp_path
    )

    advance_branch_ref(tmp_path, branch, new_sha, is_residue=is_toolchain_generated_churn)

    assert _rev_parse(tmp_path, branch) == new_sha
    assert _rev_parse(wt, "HEAD") == new_sha
    assert _porcelain(wt) == "", "worktree must be CONSISTENT (clean) after resync"
    # Residue exemption means "don't REFUSE the advance over it" -- the tracked
    # entry is still a REAL git object, so `reset --hard` still resyncs it to
    # the new tip's committed byte content (same discard semantics the
    # meta.json VCS-lock exemption already documents: "the resync discards it
    # and the next claim rewrites it"). Toolchain-generated churn is, by
    # definition, regenerable -- the next dossier-sync write recomputes it.
    assert (wt / snapshot_rel).read_text(encoding="utf-8") == '{"v": 1}\n'


def test_advance_branch_ref_no_checkout_is_plain_update_ref(tmp_path: Path) -> None:
    """With no worktree checkout of the branch, behavior is identical to a raw
    ``update-ref`` (plus the worktree scan)."""
    _init_git_repo(tmp_path)
    branch = "no-checkout"
    _git(tmp_path, "branch", branch)
    detached = tmp_path / ".worktrees" / "detached-tmp"
    detached.parent.mkdir(parents=True, exist_ok=True)
    _git(tmp_path, "worktree", "add", "--detach", str(detached), branch)
    (detached / "advanced.txt").write_text("advanced\n", encoding="utf-8")
    _git(detached, "add", "advanced.txt")
    _git(detached, "commit", "-m", "advance")
    new_sha = _rev_parse(detached, "HEAD")
    _git(tmp_path, "worktree", "remove", str(detached), "--force")

    advance_branch_ref(tmp_path, branch, new_sha)

    assert _rev_parse(tmp_path, branch) == new_sha
