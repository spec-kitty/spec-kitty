"""WP09 (terminus-merge-integrity-01M380R6) — MergeState authority tests.

Covers the two split-brains WP09 collapses to a single persisted authority each:

* **C-1 single merge target (FR-007, #4985/#4991)** — the landing branch is
  resolved once with precedence ``explicit --target`` > persisted
  ``MergeState.target_branch`` > ``meta.json`` > primary branch. A crashed
  ``merge --target develop`` then a bare ``--resume`` must resolve ``develop``
  (persisted), never re-derive ``main`` from stale meta.
* **C-2 owned merge lock (FR-008, #4996 second half)** — the merge lock carries
  ``owner_token = merge-state-id`` (stable across resume, never a pid); an
  ``--abort`` frees only a lock whose owner matches the aborting invocation and
  can never unlink a *different* mission's still-live merge lock.

Real fixtures throughout: on-disk git repos, ``meta.json`` written to the
PRIMARY partition, and ``save_state`` for persisted merge state — no mocking of
the resolvers or the lock primitives.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.cli.commands.merge import _dispatch_abort
from specify_cli.core.paths import resolve_merge_target_branch
from specify_cli.merge.resolve import _resolve_target_branch
from specify_cli.merge.state import (
    MergeState,
    acquire_merge_lock,
    get_merge_runtime_dir,
    is_merge_locked,
    read_merge_lock_owner,
    release_merge_lock_if_owned,
    save_state,
)

_GLOBAL_LOCK_ID = "__global_merge__"

# Real-fixture tests that build throwaway git repos and shell out to the git
# binary via subprocess -- git_repo for the real-repo tier, non_sandbox because
# the tests invoke the git subprocess directly (mirrors the sibling merge suite).
pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]


# ---------------------------------------------------------------------------
# Real-fixture helpers (no mocking)
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(root: Path, *, default_branch: str = "main") -> Path:
    """Initialise a real git repo with a single commit on *default_branch*."""
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-qb", default_branch, str(root)],
        check=True,
        capture_output=True,
        text=True,
    )
    _git(root, "config", "user.email", "t@t.com")
    _git(root, "config", "user.name", "T")
    _git(root, "config", "commit.gpgsign", "false")
    (root / "README.md").write_text("init\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "init")
    return root


def _write_mission_meta(
    repo: Path,
    *,
    slug: str,
    mission_id: str,
    mid8: str,
    target_branch: str | None,
) -> Path:
    """Write a minimal PRIMARY-partition ``meta.json`` for a mission.

    When *target_branch* is ``None`` the ``target_branch`` key is omitted so the
    resolver must fall through to the repo's primary branch.
    """
    feature_dir = repo / "kitty-specs" / slug
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, object] = {
        "mission_slug": slug,
        "mission_id": mission_id,
        "mid8": mid8,
        "mission_number": None,
        "mission_type": "software-dev",
    }
    if target_branch is not None:
        meta["target_branch"] = target_branch
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return feature_dir


def _persist_state(
    repo: Path,
    *,
    slug: str,
    mission_id: str,
    target_branch: str,
    remaining: bool = True,
) -> None:
    """Persist a merge state as an interrupted (``remaining``) or done merge."""
    state = MergeState(
        mission_id=mission_id,
        mission_slug=slug,
        target_branch=target_branch,
        wp_order=["WP01"],
        completed_wps=[] if remaining else ["WP01"],
    )
    if remaining:
        state.current_wp = "WP01"
    save_state(state, repo)


# ---------------------------------------------------------------------------
# C-1 — single persisted merge target
# ---------------------------------------------------------------------------


class TestResolveMergeTargetPrecedence:
    """``resolve_merge_target_branch`` precedence, unit-tested per branch (D5)."""

    def test_explicit_flag_beats_persisted_and_meta(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        _write_mission_meta(repo, slug="m", mission_id="01M" + "0" * 23, mid8="01M00000", target_branch="from-meta")
        branch, source = resolve_merge_target_branch(repo, "m", "from-flag", persisted_target="from-persisted")
        assert (branch, source) == ("from-flag", "flag")

    def test_persisted_beats_meta(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        _write_mission_meta(repo, slug="m", mission_id="01M" + "0" * 23, mid8="01M00000", target_branch="from-meta")
        branch, source = resolve_merge_target_branch(repo, "m", None, persisted_target="from-persisted")
        assert (branch, source) == ("from-persisted", "merge_state")

    def test_meta_used_when_no_flag_or_persisted(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        _write_mission_meta(repo, slug="m", mission_id="01M" + "0" * 23, mid8="01M00000", target_branch="from-meta")
        branch, source = resolve_merge_target_branch(repo, "m", None, persisted_target=None)
        assert (branch, source) == ("from-meta", "meta.json")

    def test_primary_fallback_when_nothing(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo", default_branch="main")
        _write_mission_meta(repo, slug="m", mission_id="01M" + "0" * 23, mid8="01M00000", target_branch=None)
        branch, source = resolve_merge_target_branch(repo, "m", None, persisted_target=None)
        assert (branch, source) == ("main", "primary_branch")

    def test_persisted_empty_string_ignored(self, tmp_path: Path) -> None:
        """An empty persisted value is not authoritative — meta still wins."""
        repo = _init_repo(tmp_path / "repo")
        _write_mission_meta(repo, slug="m", mission_id="01M" + "0" * 23, mid8="01M00000", target_branch="from-meta")
        branch, source = resolve_merge_target_branch(repo, "m", None, persisted_target="")
        assert (branch, source) == ("from-meta", "meta.json")


class TestResolveTargetBranchReadsPersistedState:
    """``merge/resolve.py`` consults persisted MergeState (#4985/#4991)."""

    def test_resume_honors_persisted_target_over_stale_meta(self, tmp_path: Path) -> None:
        # #4991: meta declares main, persisted state declares develop, no --target.
        repo = _init_repo(tmp_path / "repo")
        mission_id = "01M4991A" + "0" * 18
        _write_mission_meta(repo, slug="m", mission_id=mission_id, mid8="01M4991A", target_branch="main")
        _persist_state(repo, slug="m", mission_id=mission_id, target_branch="develop")

        branch, source = _resolve_target_branch(repo, "m", None)

        assert branch == "develop", "resume must honor persisted target, not stale meta (#4991)"
        assert source == "merge_state"

    def test_explicit_target_beats_stale_persisted_and_meta(self, tmp_path: Path) -> None:
        # #4985: explicit --target wins over both persisted and stale meta.
        repo = _init_repo(tmp_path / "repo")
        mission_id = "01M4985A" + "0" * 18
        _write_mission_meta(repo, slug="m", mission_id=mission_id, mid8="01M4985A", target_branch="main")
        _persist_state(repo, slug="m", mission_id=mission_id, target_branch="stale-persisted")

        branch, source = _resolve_target_branch(repo, "m", "develop")

        assert (branch, source) == ("develop", "flag")

    def test_fresh_merge_no_state_falls_through_to_meta(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        _write_mission_meta(repo, slug="m", mission_id="01M" + "0" * 23, mid8="01M00000", target_branch="main")
        branch, source = _resolve_target_branch(repo, "m", None)
        assert (branch, source) == ("main", "meta.json")


# ---------------------------------------------------------------------------
# C-2 — owned merge lock
# ---------------------------------------------------------------------------


class TestOwnedMergeLock:
    """``owner_token = merge-state-id`` and owner-gated release (D7/PP-F2)."""

    def test_acquire_records_owner_token(self, tmp_path: Path) -> None:
        acquired = acquire_merge_lock(_GLOBAL_LOCK_ID, tmp_path, owner_token="mission-A")
        assert acquired is True
        assert read_merge_lock_owner(_GLOBAL_LOCK_ID, tmp_path) == "mission-A"

    def test_owner_token_is_state_id_stable_across_new_pid(self, tmp_path: Path, monkeypatch) -> None:
        # PP-F2: owner_token is the merge-state-id, NOT a pid — a pid cannot
        # survive the crash the lock protects (--resume is a new process).
        acquire_merge_lock(_GLOBAL_LOCK_ID, tmp_path, owner_token="01MSTATEID")
        # Simulate a resume in a brand-new process (different pid).
        monkeypatch.setattr("os.getpid", lambda: 999_999)
        assert read_merge_lock_owner(_GLOBAL_LOCK_ID, tmp_path) == "01MSTATEID"

    def test_legacy_lock_without_owner_reads_none(self, tmp_path: Path) -> None:
        # A pre-fix lock body is a bare timestamp (not JSON with owner_token).
        lock_path = get_merge_runtime_dir(_GLOBAL_LOCK_ID, tmp_path) / "lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text("2026-09-24T00:00:00+00:00", encoding="utf-8")
        assert read_merge_lock_owner(_GLOBAL_LOCK_ID, tmp_path) is None

    def test_release_if_owned_frees_own_lock(self, tmp_path: Path) -> None:
        acquire_merge_lock(_GLOBAL_LOCK_ID, tmp_path, owner_token="mission-A")
        outcome = release_merge_lock_if_owned(_GLOBAL_LOCK_ID, tmp_path, owner_token="mission-A")
        assert outcome == "released_owned"
        assert not is_merge_locked(_GLOBAL_LOCK_ID, tmp_path)

    def test_release_if_owned_leaves_other_missions_live_lock(self, tmp_path: Path) -> None:
        # #4996: mission B holds the global lock and is LIVE (remaining WPs).
        # Mission A's --abort must NOT free B's live merge lock.
        b_id = "01MMISSIONB" + "0" * 15
        _persist_state(tmp_path, slug="b", mission_id=b_id, target_branch="main", remaining=True)
        acquire_merge_lock(_GLOBAL_LOCK_ID, tmp_path, owner_token=b_id)

        outcome = release_merge_lock_if_owned(_GLOBAL_LOCK_ID, tmp_path, owner_token="01MMISSIONA" + "0" * 15)

        assert outcome == "left_live", "a DIFFERENT mission's live lock must be untouched (#4996)"
        assert is_merge_locked(_GLOBAL_LOCK_ID, tmp_path)
        assert read_merge_lock_owner(_GLOBAL_LOCK_ID, tmp_path) == b_id

    def test_release_if_owned_reclaims_dead_owner(self, tmp_path: Path) -> None:
        # Owner mission has no active merge state (dead) — reclaimable via liveness.
        acquire_merge_lock(_GLOBAL_LOCK_ID, tmp_path, owner_token="01MDEADOWNER")
        outcome = release_merge_lock_if_owned(_GLOBAL_LOCK_ID, tmp_path, owner_token="01MABORTER" + "0" * 16)
        assert outcome == "released_stale"
        assert not is_merge_locked(_GLOBAL_LOCK_ID, tmp_path)

    def test_release_if_owned_absent(self, tmp_path: Path) -> None:
        outcome = release_merge_lock_if_owned(_GLOBAL_LOCK_ID, tmp_path, owner_token="mission-A")
        assert outcome == "absent"

    def test_release_if_owned_leaves_legacy_lock_when_a_merge_is_live(self, tmp_path: Path) -> None:
        # A no-owner legacy lock is only reclaimed when no merge is active.
        b_id = "01MMISSIONB" + "0" * 15
        _persist_state(tmp_path, slug="b", mission_id=b_id, target_branch="main", remaining=True)
        lock_path = get_merge_runtime_dir(_GLOBAL_LOCK_ID, tmp_path) / "lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text("legacy-timestamp", encoding="utf-8")

        outcome = release_merge_lock_if_owned(_GLOBAL_LOCK_ID, tmp_path, owner_token="01MABORTER")

        assert outcome == "left_live"
        assert is_merge_locked(_GLOBAL_LOCK_ID, tmp_path)


class TestAbortHonorsLockOwnership:
    """End-to-end ``merge --abort`` owner-gating over the real CLI dispatch (#4996)."""

    def test_abort_of_other_mission_leaves_live_global_lock(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        a_id = "01MABORTA" + "0" * 17
        b_id = "01MLIVEBB" + "0" * 17
        _write_mission_meta(repo, slug="mission-a", mission_id=a_id, mid8="01MABORTA", target_branch="main")
        _write_mission_meta(repo, slug="mission-b", mission_id=b_id, mid8="01MLIVEBB", target_branch="main")
        # Mission A has its own interrupted state; mission B is the LIVE merge
        # holding the global lock.
        _persist_state(repo, slug="mission-a", mission_id=a_id, target_branch="main", remaining=True)
        _persist_state(repo, slug="mission-b", mission_id=b_id, target_branch="main", remaining=True)
        acquire_merge_lock(_GLOBAL_LOCK_ID, repo, owner_token=b_id)

        _dispatch_abort(repo, "mission-a")

        assert is_merge_locked(_GLOBAL_LOCK_ID, repo), "abort of mission A must not free mission B's live global lock (#4996)"
        assert read_merge_lock_owner(_GLOBAL_LOCK_ID, repo) == b_id

    def test_abort_of_owning_mission_frees_global_lock(self, tmp_path: Path) -> None:
        repo = _init_repo(tmp_path / "repo")
        a_id = "01MOWNERA" + "0" * 17
        _write_mission_meta(repo, slug="mission-a", mission_id=a_id, mid8="01MOWNERA", target_branch="main")
        _persist_state(repo, slug="mission-a", mission_id=a_id, target_branch="main", remaining=True)
        acquire_merge_lock(_GLOBAL_LOCK_ID, repo, owner_token=a_id)

        _dispatch_abort(repo, "mission-a")

        assert not is_merge_locked(_GLOBAL_LOCK_ID, repo), "abort of the owning mission must free its own global lock"


# ---------------------------------------------------------------------------
# C-1 companion — the terminus housekeeping commit targets the RESOLVED branch
# (#4985/#4991): threading the resolved merge target into the bookkeeping
# commit's destination_ref, not the stale meta ``target_branch``.
# ---------------------------------------------------------------------------


class TestHousekeepingCommitTargetsResolvedBranch:
    """``commit_merge_bookkeeping(destination_ref_override=...)`` (#4985/#4991).

    On a non-default-target merge the post-merge checkout HEAD is on the RESOLVED
    target (e.g. ``develop``), while the mission ``meta.json`` still records the
    stale ``target_branch`` (``main``). The placement port resolves
    ``PRIMARY_METADATA`` from that stale meta, so the housekeeping commit's
    destination would mismatch HEAD and raise ``SafeCommitHeadMismatch`` — aborting
    before the work durably lands. Threading the resolved target as
    ``destination_ref_override`` makes the commit target the branch HEAD is on.
    """

    def _mission_on_develop(self, tmp_path: Path) -> tuple[Path, str, Path]:
        """A repo whose meta records target_branch=main but HEAD is on develop."""
        repo = _init_repo(tmp_path / "repo", default_branch="main")
        slug = "m"
        feature_dir = _write_mission_meta(repo, slug=slug, mission_id="01M4985A" + "0" * 18, mid8="01M4985A", target_branch="main")
        _git(repo, "branch", "develop", "main")
        _git(repo, "checkout", "-q", "develop")
        # A real bookkeeping change to commit (status.json on the planning surface).
        (feature_dir / "status.json").write_text('{"done": ["WP01"]}\n', encoding="utf-8")
        return repo, slug, feature_dir

    def test_stale_meta_destination_mismatches_head_without_override(self, tmp_path: Path) -> None:
        from specify_cli.git.bookkeeping_commit import commit_merge_bookkeeping
        from specify_cli.git.commit_helpers import SafeCommitHeadMismatch

        repo, slug, feature_dir = self._mission_on_develop(tmp_path)
        # No override: the placement port resolves the STALE meta 'main' while HEAD
        # is 'develop' → SafeCommitHeadMismatch (the #4985/#4991 abort).
        with pytest.raises(SafeCommitHeadMismatch) as excinfo:
            commit_merge_bookkeeping(
                repo_root=repo,
                worktree_root=repo,
                mission_slug=slug,
                message="chore(m): record done transitions for merged WPs",
                paths=(feature_dir / "status.json",),
            )
        assert excinfo.value.destination_ref == "main"

    def test_resolved_override_lands_on_head_branch(self, tmp_path: Path) -> None:
        from specify_cli.git.bookkeeping_commit import commit_merge_bookkeeping

        repo, slug, feature_dir = self._mission_on_develop(tmp_path)
        # Threading the RESOLVED target (develop) as destination_ref_override makes
        # the housekeeping commit target the branch HEAD is on — no mismatch, and
        # the done-bookkeeping durably lands on develop, never on stale meta 'main'.
        result = commit_merge_bookkeeping(
            repo_root=repo,
            worktree_root=repo,
            mission_slug=slug,
            message="chore(m): record done transitions for merged WPs",
            paths=(feature_dir / "status.json",),
            destination_ref_override="develop",
        )
        assert result.destination_ref == "develop"
        # The bookkeeping commit is on develop's tip; main never received it.
        develop_head = subprocess.run(
            ["git", "-C", str(repo), "log", "-1", "--format=%s", "develop"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert "record done transitions" in develop_head
        main_head = subprocess.run(
            ["git", "-C", str(repo), "log", "-1", "--format=%s", "main"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert "record done transitions" not in main_head


# ---------------------------------------------------------------------------
# Pre-merge hardening (#5001 FOLD-2/FOLD-4/FOLD-5) — honest squash message,
# resume window-base preservation, and the rollback-helper guard.
# ---------------------------------------------------------------------------


def _rev(repo: Path, ref: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", ref],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _commit_on(repo: Path, branch: str, filename: str, body: str) -> str:
    """Add a commit on *branch* (checks it out) and return the new tip SHA."""
    _git(repo, "checkout", "-q", branch)
    (repo / filename).write_text(body, encoding="utf-8")
    _git(repo, "add", filename)
    _git(repo, "commit", "-qm", f"work: {filename}")
    return _rev(repo, branch)


class TestReconciliationPassMessageHonesty:
    """FOLD-2: the PASS line must NOT claim excluded-reachability was checked under
    squash (it is deferred), while merge/rebase keep the full-verification line."""

    def test_squash_message_defers_and_does_not_claim_excluded_checked(self) -> None:
        from specify_cli.merge.config import MergeStrategy
        from specify_cli.merge.executor import _reconciliation_pass_message

        msg = _reconciliation_pass_message(MergeStrategy.SQUASH)
        assert "deferred under squash" in msg
        assert "no excluded commit reachable" not in msg

    def test_merge_message_reports_full_verification(self) -> None:
        from specify_cli.merge.config import MergeStrategy
        from specify_cli.merge.executor import _reconciliation_pass_message

        for strategy in (MergeStrategy.MERGE, MergeStrategy.REBASE):
            msg = _reconciliation_pass_message(strategy)
            assert "no excluded commit reachable" in msg


class TestPreMutationTargetShaPersistence:
    """FOLD-4: the excluded/closed-world window base is the TRANSACTION-START target
    tip. A fresh capture persists it into MergeState; a resume re-reads the
    persisted original instead of the (already-advanced) live tip — otherwise the
    window collapses to empty and the excluded axes false-PASS on resume."""

    def _state(self, repo: Path, mission_id: str, target: str) -> MergeState:
        state = MergeState(
            mission_id=mission_id,
            mission_slug="m",
            target_branch=target,
            wp_order=["WP01"],
        )
        save_state(state, repo)
        return state

    def test_merge_state_has_pre_mutation_target_field(self, tmp_path: Path) -> None:
        state = MergeState(mission_id="01M" + "0" * 23, mission_slug="m", target_branch="main", wp_order=["WP01"])
        assert state.pre_mutation_target_sha is None
        # round-trips through the known-fields filter like the other resume fields.
        rehydrated = MergeState.from_dict({**state.to_dict(), "pre_mutation_target_sha": "abc123"})
        assert rehydrated.pre_mutation_target_sha == "abc123"

    def test_fresh_capture_persists_live_tip(self, tmp_path: Path) -> None:
        from specify_cli.merge.executor import _resolve_pre_mutation_target_sha
        from specify_cli.merge.state import load_state

        repo = _init_repo(tmp_path / "repo", default_branch="main")
        mission_id = "01M5001F" + "0" * 18
        state = self._state(repo, mission_id, "main")
        live = _rev(repo, "main")

        got = _resolve_pre_mutation_target_sha(repo, "main", state)

        assert got == live
        assert state.pre_mutation_target_sha == live
        reloaded = load_state(repo, mission_id)
        assert reloaded is not None
        assert reloaded.pre_mutation_target_sha == live

    def test_resume_reads_persisted_original_not_advanced_tip(self, tmp_path: Path) -> None:
        from specify_cli.merge.executor import _resolve_pre_mutation_target_sha

        repo = _init_repo(tmp_path / "repo", default_branch="main")
        mission_id = "01M5001R" + "0" * 18
        state = self._state(repo, mission_id, "main")
        original = _rev(repo, "main")
        # attempt-1 captures the pre-mutation tip.
        assert _resolve_pre_mutation_target_sha(repo, "main", state) == original
        # attempt-1 then advances the target before crashing.
        advanced = _commit_on(repo, "main", "landed.py", "attempt-1 advance\n")
        assert advanced != original
        # RESUME: must re-read the ORIGINAL persisted tip, not the advanced live tip
        # (so the excluded/closed-world window still spans attempt-1's advance).
        resumed = _resolve_pre_mutation_target_sha(repo, "main", state)
        assert resumed == original
        assert resumed != advanced

    def test_unresolvable_target_yields_none_and_persists_nothing(self, tmp_path: Path) -> None:
        from specify_cli.merge.executor import _resolve_pre_mutation_target_sha

        repo = _init_repo(tmp_path / "repo", default_branch="main")
        state = self._state(repo, "01M5001N" + "0" * 18, "no-such-branch")
        assert _resolve_pre_mutation_target_sha(repo, "no-such-branch", state) is None
        assert state.pre_mutation_target_sha is None


class TestRollbackTargetAfterFailedReconciliation:
    """FOLD-5: direct coverage for ``_rollback_target_after_failed_reconciliation``
    (previously untested) — a real CAS revert of the target to its pre-mutation
    tip, and the fixed ``not current_sha`` guard for an unresolvable ref."""

    def _run(self, repo: Path, *, target: str, pre_sha: str | None):
        from specify_cli.lanes.models import ExecutionLane, LanesManifest
        from specify_cli.merge.config import MergeStrategy
        from specify_cli.merge.executor import _MergeRunState

        manifest = LanesManifest(
            version=1,
            mission_slug="m",
            mission_id="01M5001B" + "0" * 18,
            mission_branch="kitty/mission-m",
            target_branch=target,
            lanes=[
                ExecutionLane(
                    lane_id="lane-a",
                    wp_ids=("WP01",),
                    write_scope=("src/wp01.py",),
                    predicted_surfaces=("code",),
                    depends_on_lanes=(),
                    parallel_group=0,
                )
            ],
            computed_at="2026-01-01T00:00:00+00:00",
            computed_from="test",
        )
        state = MergeState(mission_id=manifest.mission_id, mission_slug="m", target_branch=target, wp_order=["WP01"])
        run = _MergeRunState(
            main_repo=repo,
            mission_slug="m",
            canonical_id=manifest.mission_id,
            canonical_mission_id=manifest.mission_id,
            feature_dir=repo / "kitty-specs" / "m",
            target_feature_dir=repo / "kitty-specs" / "m",
            lanes_manifest=manifest,
            all_wp_ids=["WP01"],
            push=False,
            delete_branch=False,
            remove_worktree=False,
            strategy=MergeStrategy.MERGE,
            assume_yes=True,
            planning_artifact_only=False,
            state=state,
            is_resume=False,
        )
        run.target_expected_old_sha = pre_sha
        return run

    def test_reverts_target_to_pre_mutation_tip(self, tmp_path: Path) -> None:
        from specify_cli.merge.executor import _rollback_target_after_failed_reconciliation

        repo = _init_repo(tmp_path / "repo", default_branch="main")
        pre_sha = _rev(repo, "main")
        advanced = _commit_on(repo, "main", "bad.py", "divergent content\n")
        assert advanced != pre_sha
        run = self._run(repo, target="main", pre_sha=pre_sha)

        _rollback_target_after_failed_reconciliation(run)

        assert _rev(repo, "main") == pre_sha  # CAS-restored to the pre-mutation tip

    def test_noop_when_pre_sha_unknown(self, tmp_path: Path) -> None:
        from specify_cli.merge.executor import _rollback_target_after_failed_reconciliation

        repo = _init_repo(tmp_path / "repo", default_branch="main")
        before = _rev(repo, "main")
        run = self._run(repo, target="main", pre_sha=None)
        _rollback_target_after_failed_reconciliation(run)  # must not raise
        assert _rev(repo, "main") == before

    def test_noop_when_already_at_pre_sha(self, tmp_path: Path) -> None:
        from specify_cli.merge.executor import _rollback_target_after_failed_reconciliation

        repo = _init_repo(tmp_path / "repo", default_branch="main")
        pre_sha = _rev(repo, "main")
        run = self._run(repo, target="main", pre_sha=pre_sha)
        reflog_before = subprocess.run(["git", "-C", str(repo), "reflog", "--format=%H"], capture_output=True, text=True, check=True).stdout
        _rollback_target_after_failed_reconciliation(run)  # target already at pre-tip
        assert _rev(repo, "main") == pre_sha
        reflog_after = subprocess.run(["git", "-C", str(repo), "reflog", "--format=%H"], capture_output=True, text=True, check=True).stdout
        assert reflog_after == reflog_before  # no ref move at all

    def test_guard_skips_when_target_ref_unresolvable(self, tmp_path: Path) -> None:
        from specify_cli.merge.executor import _rollback_target_after_failed_reconciliation

        repo = _init_repo(tmp_path / "repo", default_branch="main")
        # target branch does not exist -> _resolve_ref_sha returns "" -> the fixed
        # ``not current_sha`` guard skips cleanly (pre-fix the dead ``is None`` guard
        # fell through to a restore with expected_current_sha="" and warned).
        run = self._run(repo, target="ghost-branch", pre_sha=_rev(repo, "main"))
        _rollback_target_after_failed_reconciliation(run)  # must not raise
