"""Tests for ProfileInvocationExecutor."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from charter.offering.model_task_routing.evaluator import RoutingCandidate, RoutingRecommendation
from specify_cli.invocation.errors import InvocationWriteError, ProfileNotFoundError
from specify_cli.invocation.executor import InvocationPayload, ProfileInvocationExecutor
from specify_cli.invocation.writer import EVENTS_DIR
from tests.specify_cli.invocation._op_git import checkout_issue_branch, run_git, track_op_record_on_current_branch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "profiles"

_COMPACT_CTX = MagicMock()
_COMPACT_CTX.mode = "compact"
_COMPACT_CTX.text = "compact governance context"

_MISSING_CTX = MagicMock()
_MISSING_CTX.mode = "missing"
_MISSING_CTX.text = ""


def _setup_fixture_profiles(tmp_path: Path) -> None:
    """Copy fixture profiles into simulated project structure."""
    profiles_dir = tmp_path / ".kittify" / "profiles"
    profiles_dir.mkdir(parents=True)
    for yaml_file in FIXTURES_DIR.glob("*.agent.yaml"):
        shutil.copy(yaml_file, profiles_dir / yaml_file.name)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestInvokeWithProfileHint:
    def test_invoke_with_profile_hint_returns_payload(self, tmp_path: Path) -> None:
        _setup_fixture_profiles(tmp_path)
        with patch(
            "specify_cli.invocation.executor.build_charter_context",
            return_value=_COMPACT_CTX,
        ) as mock_ctx:
            executor = ProfileInvocationExecutor(tmp_path)
            payload = executor.invoke("implement the feature", profile_hint="implementer-fixture")

        assert isinstance(payload, InvocationPayload)
        assert payload.profile_id == "implementer-fixture"
        assert payload.profile_friendly_name == "Implementer (fixture)"
        assert payload.action is not None
        # mark_loaded=False is critical — verify it was passed
        mock_ctx.assert_called_once()
        _, kwargs = mock_ctx.call_args
        assert kwargs.get("mark_loaded") is False

    def test_invoke_creates_jsonl_file(self, tmp_path: Path) -> None:
        _setup_fixture_profiles(tmp_path)
        with patch(
            "specify_cli.invocation.executor.build_charter_context",
            return_value=_COMPACT_CTX,
        ):
            executor = ProfileInvocationExecutor(tmp_path)
            payload = executor.invoke("implement feature", profile_hint="implementer-fixture")

        events_dir = tmp_path / EVENTS_DIR
        # Filter out ops-index.jsonl — it is the O(n) index aide, not an invocation file.
        invocation_files = [
            f for f in events_dir.glob("*.jsonl")
            if f.name != "ops-index.jsonl"
        ]
        assert len(invocation_files) == 1
        assert invocation_files[0].name == f"{payload.invocation_id}.jsonl"

    def test_invoke_writes_started_event_to_jsonl(self, tmp_path: Path) -> None:
        _setup_fixture_profiles(tmp_path)
        with patch(
            "specify_cli.invocation.executor.build_charter_context",
            return_value=_COMPACT_CTX,
        ):
            executor = ProfileInvocationExecutor(tmp_path)
            payload = executor.invoke("test", profile_hint="implementer-fixture")

        events_dir = tmp_path / EVENTS_DIR
        jsonl_file = events_dir / f"{payload.invocation_id}.jsonl"
        lines = [line for line in jsonl_file.read_text().splitlines() if line.strip()]
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["event"] == "started"
        assert data["profile_id"] == "implementer-fixture"

    def test_invoke_persists_catalog_winning_model_in_started_event(
        self,
        tmp_path: Path,
    ) -> None:
        _setup_fixture_profiles(tmp_path)
        recommendation = RoutingRecommendation(
            task_type="implementation",
            objective="quality_first",
            override_mode="advisory",
            candidates=(
                RoutingCandidate(
                    model_id="claude-opus-4-6",
                    source="catalog",
                    score=0.99,
                ),
            ),
        )
        with patch(
            "specify_cli.invocation.executor.build_charter_context",
            return_value=_COMPACT_CTX,
        ), patch(
            "specify_cli.invocation.executor._compute_recommendation",
            return_value=recommendation,
        ):
            payload = ProfileInvocationExecutor(tmp_path).invoke(
                "implement WP01",
                profile_hint="implementer-fixture",
                action_hint="implement",
                mission_id="01KTK5JBD69FQ8XVRFV1J630MJ",
                wp_id="WP01",
            )

        record = json.loads(
            (tmp_path / EVENTS_DIR / f"{payload.invocation_id}.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()[0]
        )
        assert record["model_id"] == "claude-opus-4-6"


class TestInvokeNoRouterNoHintRaises:
    def test_invoke_without_router_or_hint_raises_runtime_error(self, tmp_path: Path) -> None:
        _setup_fixture_profiles(tmp_path)
        executor = ProfileInvocationExecutor(tmp_path, router=None)
        with pytest.raises(RuntimeError, match="No profile_hint and no router"):
            executor.invoke("some request")


class TestInvokeMissingProfileHintRaises:
    def test_invoke_with_unknown_profile_hint_raises_profile_not_found_error(
        self, tmp_path: Path
    ) -> None:
        executor = ProfileInvocationExecutor(tmp_path)
        with patch(
            "specify_cli.invocation.executor.build_charter_context",
            return_value=_COMPACT_CTX,
        ):
            with pytest.raises(ProfileNotFoundError):
                executor.invoke("test", profile_hint="no-such-profile")


class TestInvokeDegradedCharter:
    def test_invoke_missing_charter_sets_context_unavailable(self, tmp_path: Path) -> None:
        """When charter is missing, governance_context_available=False, JSONL still written."""
        _setup_fixture_profiles(tmp_path)
        with patch(
            "specify_cli.invocation.executor.build_charter_context",
            return_value=_MISSING_CTX,
        ):
            executor = ProfileInvocationExecutor(tmp_path)
            payload = executor.invoke("test", profile_hint="implementer-fixture")

        assert payload.governance_context_available is False
        # JSONL must still be written even when charter is missing
        events_dir = tmp_path / EVENTS_DIR
        # Filter out ops-index.jsonl — it is the O(n) index aide, not an invocation file.
        invocation_files = [
            f for f in events_dir.glob("*.jsonl")
            if f.name != "ops-index.jsonl"
        ]
        assert len(invocation_files) == 1


class TestInvokeMarkLoadedFalse:
    def test_context_state_json_not_modified_after_invoke(self, tmp_path: Path) -> None:
        """context-state.json must NOT be modified after invoke — mark_loaded=False is critical."""
        _setup_fixture_profiles(tmp_path)
        # Ensure context-state.json directory exists
        state_dir = tmp_path / ".kittify" / "charter"
        state_dir.mkdir(parents=True)
        state_file = state_dir / "context-state.json"
        state_file.write_text('{"specify": {"first_load": true}}', encoding="utf-8")

        initial_content = state_file.read_text(encoding="utf-8")

        with patch(
            "specify_cli.invocation.executor.build_charter_context",
            return_value=_COMPACT_CTX,
        ) as mock_ctx:
            executor = ProfileInvocationExecutor(tmp_path)
            executor.invoke("test", profile_hint="implementer-fixture")

        # mark_loaded=False must have been passed to prevent state mutation
        _, kwargs = mock_ctx.call_args
        assert kwargs.get("mark_loaded") is False

        # State file must remain unmodified
        assert state_file.read_text(encoding="utf-8") == initial_content


class TestInvokeWriteFailureRaises:
    def test_invoke_propagates_invocation_write_error(self, tmp_path: Path) -> None:
        _setup_fixture_profiles(tmp_path)
        with patch(
            "specify_cli.invocation.executor.build_charter_context",
            return_value=_COMPACT_CTX,
        ), patch(
            "specify_cli.invocation.executor.InvocationWriter.write_started",
            side_effect=InvocationWriteError("disk full"),
        ):
            executor = ProfileInvocationExecutor(tmp_path)
            with pytest.raises(InvocationWriteError):
                executor.invoke("test", profile_hint="implementer-fixture")


# ---------------------------------------------------------------------------
# Git fixture helper
# ---------------------------------------------------------------------------


def _init_git_repo(path: Path, *, track_ops: bool = False) -> None:
    """Initialise a minimal git repo at ``path`` with an initial commit.

    ``track_ops=True`` also commits one ULID-shaped Op record on ``main``: the
    Op-record auto-commit only happens where the primary branch tracks Op
    records (#6410), so commit-asserting tests opt in and then work from an
    issue branch.
    """
    subprocess.run(["git", "init", "-b", "main", str(path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "test@example.com"],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "Test"],
        check=True, capture_output=True,
    )
    # Create an initial commit so HEAD exists (required for git add + commit).
    readme = path / "README.md"
    readme.write_text("test repo\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(path), "add", "README.md"],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "commit", "--no-verify", "-m", "init"],
        check=True, capture_output=True,
    )
    if track_ops:
        track_op_record_on_current_branch(path)


# ---------------------------------------------------------------------------
# T-003 – T-007: Auto-commit tests
# ---------------------------------------------------------------------------


class TestAutoCommitOnCompleteInvocation:
    """T-003: commit appears in git log after complete_invocation()."""

    def test_commit_appears_after_complete_invocation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("SPEC_KITTY_TEST_MODE", raising=False)
        _init_git_repo(tmp_path, track_ops=True)
        checkout_issue_branch(tmp_path)
        _setup_fixture_profiles(tmp_path)

        with patch(
            "specify_cli.invocation.executor.build_charter_context",
            return_value=_COMPACT_CTX,
        ):
            executor = ProfileInvocationExecutor(tmp_path)
            payload = executor.invoke("implement feature", profile_hint="implementer-fixture")
            executor.complete_invocation(payload.invocation_id, outcome="done", closed_by="agent")

        result = subprocess.run(
            ["git", "-C", str(tmp_path), "log", "--oneline"],
            capture_output=True, text=True, check=True,
        )
        log_lines = result.stdout.strip().splitlines()
        # At least 2 commits: init + op commit
        assert len(log_lines) >= 2
        # Most recent commit should mention the op
        assert "op(" in log_lines[0]

    def test_op_file_restorable_after_git_clean(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """T-004: op file is in git and can be restored after deletion."""
        monkeypatch.delenv("SPEC_KITTY_TEST_MODE", raising=False)
        _init_git_repo(tmp_path, track_ops=True)
        checkout_issue_branch(tmp_path)
        _setup_fixture_profiles(tmp_path)

        with patch(
            "specify_cli.invocation.executor.build_charter_context",
            return_value=_COMPACT_CTX,
        ):
            executor = ProfileInvocationExecutor(tmp_path)
            payload = executor.invoke("test", profile_hint="implementer-fixture")
            executor.complete_invocation(payload.invocation_id, outcome="done", closed_by="agent")

        op_file = tmp_path / EVENTS_DIR / f"{payload.invocation_id}.jsonl"
        assert op_file.exists()

        # Delete the file and restore from git
        op_file.unlink()
        assert not op_file.exists()

        subprocess.run(
            ["git", "-C", str(tmp_path), "checkout", "HEAD", "--",
             f"{EVENTS_DIR}/{payload.invocation_id}.jsonl"],
            check=True, capture_output=True,
        )
        assert op_file.exists()

    def test_complete_invocation_commits_with_safe_commit(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path, track_ops=True)
        checkout_issue_branch(tmp_path)
        _setup_fixture_profiles(tmp_path)

        with patch(
            "specify_cli.invocation.executor.build_charter_context",
            return_value=_COMPACT_CTX,
        ):
            executor = ProfileInvocationExecutor(tmp_path)
            payload = executor.invoke("implement mission", profile_hint="implementer-fixture")

        with patch("specify_cli.invocation.executor.safe_commit") as mock_safe_commit:
            executor.complete_invocation(payload.invocation_id, outcome="done", closed_by="agent")

        call_kwargs = mock_safe_commit.call_args.kwargs
        assert call_kwargs["repo_root"] == tmp_path
        assert call_kwargs["worktree_root"] == tmp_path
        # WP02: executor now passes a CommitTarget (mission_runtime.context) rather
        # than a bare destination_ref string; ref echoes the resolved branch.
        assert call_kwargs["target"].ref == "issue-topic"
        assert call_kwargs["message"].startswith("op(implementer-fixture):")
        assert call_kwargs["paths"] == (Path(f"{EVENTS_DIR}/{payload.invocation_id}.jsonl"),)
        # Op-record bookkeeping asserts STANDARD: it is not the merge flow, so
        # a protected destination is refused (and swallowed into a warning)
        # unless the operator hatch declares the branch unprotected.
        from specify_cli.core.commit_guard import GuardCapability

        assert call_kwargs["capability"] is GuardCapability.STANDARD

    def test_complete_invocation_refused_on_protected_branch_without_hatch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Env-clean op-record close on a protected branch: no commit, no crash.

        ``STANDARD`` authorizes no protected-branch flow, so the auto-commit is
        refused by the guard and swallowed into a warning; the Op record stays
        on disk and the close itself succeeds (PR #1850 guard-bypass regression
        fix). The reported refusal names the branch but never the guard's
        override advice, which agents must not follow (#6410).
        """
        monkeypatch.delenv("SPEC_KITTY_TEST_MODE", raising=False)
        monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)
        _init_git_repo(tmp_path, track_ops=True)
        _setup_fixture_profiles(tmp_path)

        with patch(
            "specify_cli.invocation.executor.build_charter_context",
            return_value=_COMPACT_CTX,
        ):
            executor = ProfileInvocationExecutor(tmp_path)
            payload = executor.invoke("implement feature", profile_hint="implementer-fixture")
            executor.complete_invocation(payload.invocation_id, outcome="done", closed_by="agent")

        # The close succeeded and the Op record is on disk...
        assert (tmp_path / EVENTS_DIR / f"{payload.invocation_id}.jsonl").exists()
        # ...but nothing landed on the protected branch (init + seeded record only).
        log_lines = subprocess.run(
            ["git", "-C", str(tmp_path), "log", "--oneline"],
            capture_output=True, text=True, check=True,
        ).stdout.strip().splitlines()
        assert len(log_lines) == 2, (
            f"op-record commit landed on a protected branch: {log_lines}"
        )
        outcome = executor.last_op_commit
        assert outcome is not None
        assert outcome.refusal == "protected branch 'main'"
        assert "SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS" not in (outcome.refusal or "")

    def test_complete_invocation_on_issue_branch_preserves_unrelated_staging(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("SPEC_KITTY_TEST_MODE", raising=False)
        _init_git_repo(tmp_path, track_ops=True)
        checkout_issue_branch(tmp_path)
        _setup_fixture_profiles(tmp_path)

        unrelated = tmp_path / "unrelated.txt"
        unrelated.write_text("keep me staged\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(tmp_path), "add", "unrelated.txt"],
            check=True,
            capture_output=True,
        )

        with patch(
            "specify_cli.invocation.executor.build_charter_context",
            return_value=_COMPACT_CTX,
        ):
            executor = ProfileInvocationExecutor(tmp_path)
            payload = executor.invoke("implement mission", profile_hint="implementer-fixture")
            executor.complete_invocation(payload.invocation_id, outcome="done", closed_by="agent")

        committed_files = subprocess.run(
            ["git", "-C", str(tmp_path), "show", "--name-only", "--format=", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        assert f"{EVENTS_DIR}/{payload.invocation_id}.jsonl" in committed_files
        assert "unrelated.txt" not in committed_files

        staged_files = subprocess.run(
            ["git", "-C", str(tmp_path), "diff", "--cached", "--name-only"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        assert "unrelated.txt" in staged_files

    def test_completed_commit_excludes_ops_index_and_orphan_metadata(
        self, tmp_path: Path
    ) -> None:
        _init_git_repo(tmp_path, track_ops=True)
        subprocess.run(
            ["git", "-C", str(tmp_path), "checkout", "-b", "ops-work"],
            check=True,
            capture_output=True,
        )
        _setup_fixture_profiles(tmp_path)

        with patch(
            "specify_cli.invocation.executor.build_charter_context",
            return_value=_COMPACT_CTX,
        ):
            executor = ProfileInvocationExecutor(tmp_path)
            orphan = executor.invoke("orphan op", profile_hint="implementer-fixture")
            completed = executor.invoke("completed op", profile_hint="implementer-fixture")
            executor.complete_invocation(completed.invocation_id, outcome="done", closed_by="agent")

        tracked_files = subprocess.run(
            ["git", "-C", str(tmp_path), "ls-tree", "-r", "--name-only", "HEAD", EVENTS_DIR],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        assert f"{EVENTS_DIR}/{completed.invocation_id}.jsonl" in tracked_files
        assert f"{EVENTS_DIR}/{orphan.invocation_id}.jsonl" not in tracked_files
        assert f"{EVENTS_DIR}/ops-index.jsonl" not in tracked_files
        assert (tmp_path / EVENTS_DIR / "ops-index.jsonl").exists()

    def test_orphan_op_not_committed(self, tmp_path: Path) -> None:
        """T-005: a started-only (orphan) op is NOT in git log."""
        _init_git_repo(tmp_path)
        _setup_fixture_profiles(tmp_path)

        with patch(
            "specify_cli.invocation.executor.build_charter_context",
            return_value=_COMPACT_CTX,
        ):
            executor = ProfileInvocationExecutor(tmp_path)
            executor.invoke("test", profile_hint="implementer-fixture")
            # Do NOT call complete_invocation — leave it as an orphan.

        result = subprocess.run(
            ["git", "-C", str(tmp_path), "log", "--oneline"],
            capture_output=True, text=True, check=True,
        )
        log_lines = result.stdout.strip().splitlines()
        # Only the init commit should be present
        assert len(log_lines) == 1
        assert "init" in log_lines[0]

    def test_mission_id_and_wp_id_preserved(self, tmp_path: Path) -> None:
        """T-007a: mission_id/wp_id are absent from the started record for standalone invocations."""
        _setup_fixture_profiles(tmp_path)

        with patch(
            "specify_cli.invocation.executor.build_charter_context",
            return_value=_COMPACT_CTX,
        ):
            executor = ProfileInvocationExecutor(tmp_path)
            payload = executor.invoke("test", profile_hint="implementer-fixture")

        events_dir = tmp_path / EVENTS_DIR
        jsonl_file = events_dir / f"{payload.invocation_id}.jsonl"
        data = json.loads(jsonl_file.read_text().splitlines()[0])
        assert data.get("mission_id") is None
        assert data.get("wp_id") is None

    def test_mission_id_and_wp_id_written_when_supplied(self, tmp_path: Path) -> None:
        """T-007b: mission_id/wp_id appear in the started record when supplied by caller."""
        _setup_fixture_profiles(tmp_path)

        with patch(
            "specify_cli.invocation.executor.build_charter_context",
            return_value=_COMPACT_CTX,
        ):
            executor = ProfileInvocationExecutor(tmp_path)
            payload = executor.invoke(
                "test",
                profile_hint="implementer-fixture",
                mission_id="01KTB49KJKRJ71YR8KERVDMHHA",
                wp_id="WP01",
            )

        events_dir = tmp_path / EVENTS_DIR
        jsonl_file = events_dir / f"{payload.invocation_id}.jsonl"
        data = json.loads(jsonl_file.read_text().splitlines()[0])
        assert data["mission_id"] == "01KTB49KJKRJ71YR8KERVDMHHA"
        assert data["wp_id"] == "WP01"

    def test_commit_failure_does_not_raise(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Best-effort: git failure must not block the invocation response."""
        import logging

        _init_git_repo(tmp_path, track_ops=True)
        checkout_issue_branch(tmp_path)
        _setup_fixture_profiles(tmp_path)

        with patch(
            "specify_cli.invocation.executor.build_charter_context",
            return_value=_COMPACT_CTX,
        ):
            executor = ProfileInvocationExecutor(tmp_path)
            payload = executor.invoke("test request", profile_hint="implementer-fixture")

        with patch("specify_cli.invocation.executor.safe_commit", side_effect=RuntimeError("git not found")):
            with caplog.at_level(logging.WARNING):
                result = executor.complete_invocation(payload.invocation_id, outcome="done", closed_by="agent")

        assert result is not None
        warning_messages = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
        assert any("commit" in m.lower() or "auto" in m.lower() for m in warning_messages)


# ---------------------------------------------------------------------------
# #6410: skip the Op-record auto-commit where kitty-ops is untracked or ignored
# ---------------------------------------------------------------------------


def _git_out(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _open_op(executor: ProfileInvocationExecutor) -> str:
    with patch(
        "specify_cli.invocation.executor.build_charter_context",
        return_value=_COMPACT_CTX,
    ):
        return executor.invoke("implement feature", profile_hint="implementer-fixture").invocation_id


class TestOpCommitSkip:
    """The commit is kept where Op records are tracked and skipped otherwise."""

    def test_skips_when_primary_tracks_no_op_records(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        checkout_issue_branch(tmp_path)
        _setup_fixture_profiles(tmp_path)
        executor = ProfileInvocationExecutor(tmp_path)
        invocation_id = _open_op(executor)

        with patch("specify_cli.invocation.executor.safe_commit") as mock_safe_commit:
            executor.complete_invocation(invocation_id, outcome="done", closed_by="agent")

        mock_safe_commit.assert_not_called()
        outcome = executor.last_op_commit
        assert outcome is not None
        assert outcome.committed is False
        assert outcome.refusal is None
        assert outcome.skipped is not None
        assert "primary branch (main)" in outcome.skipped
        assert (tmp_path / EVENTS_DIR / f"{invocation_id}.jsonl").exists()

    def test_detached_head_skips_quietly_when_primary_tracks_no_op_records(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        run_git(tmp_path, "checkout", "--detach")
        _setup_fixture_profiles(tmp_path)
        executor = ProfileInvocationExecutor(tmp_path)
        invocation_id = _open_op(executor)

        executor.complete_invocation(invocation_id, outcome="done", closed_by="agent")

        outcome = executor.last_op_commit
        assert outcome is not None
        assert outcome.refusal is None
        assert outcome.skipped is not None

    def test_detached_head_is_refused_when_primary_tracks_op_records(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path, track_ops=True)
        run_git(tmp_path, "checkout", "--detach")
        _setup_fixture_profiles(tmp_path)
        executor = ProfileInvocationExecutor(tmp_path)
        invocation_id = _open_op(executor)

        executor.complete_invocation(invocation_id, outcome="done", closed_by="agent")

        outcome = executor.last_op_commit
        assert outcome is not None
        assert outcome.refusal == "detached HEAD"
        assert outcome.skipped is None

    def test_skips_when_record_path_is_gitignored_even_if_primary_tracks(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path, track_ops=True)
        (tmp_path / ".gitignore").write_text("kitty-ops/\n", encoding="utf-8")
        checkout_issue_branch(tmp_path)
        _setup_fixture_profiles(tmp_path)
        executor = ProfileInvocationExecutor(tmp_path)
        invocation_id = _open_op(executor)

        with patch("specify_cli.invocation.executor.safe_commit") as mock_safe_commit:
            executor.complete_invocation(invocation_id, outcome="done", closed_by="agent")

        mock_safe_commit.assert_not_called()
        assert executor.last_op_commit is not None
        assert executor.last_op_commit.skipped is not None
        assert "matches an ignore rule" in executor.last_op_commit.skipped

    def test_commits_exactly_one_record_when_primary_tracks_op_records(self, tmp_path: Path) -> None:
        """Positive control: same fixture as the skip test, one change (a tracked record)."""
        _init_git_repo(tmp_path, track_ops=True)
        checkout_issue_branch(tmp_path)
        _setup_fixture_profiles(tmp_path)
        executor = ProfileInvocationExecutor(tmp_path)
        invocation_id = _open_op(executor)
        before = _git_out(tmp_path, "rev-list", "--count", "HEAD")

        executor.complete_invocation(invocation_id, outcome="done", closed_by="agent")

        assert executor.last_op_commit is not None
        assert executor.last_op_commit.committed is True
        assert executor.last_op_commit.skipped is None
        assert int(_git_out(tmp_path, "rev-list", "--count", "HEAD")) == int(before) + 1
        assert _git_out(tmp_path, "log", "-1", "--format=%s").startswith("op(")
        assert _git_out(tmp_path, "show", "--name-only", "--format=", "HEAD").splitlines() == [
            f"{EVENTS_DIR}/{invocation_id}.jsonl"
        ]

    def test_probe_error_skips_without_raising(self, tmp_path: Path) -> None:
        from specify_cli.invocation.op_commit_policy import OpCommitProbeError

        _init_git_repo(tmp_path, track_ops=True)
        checkout_issue_branch(tmp_path)
        _setup_fixture_profiles(tmp_path)
        executor = ProfileInvocationExecutor(tmp_path)
        invocation_id = _open_op(executor)

        with (
            patch("specify_cli.invocation.executor.safe_commit") as mock_safe_commit,
            patch(
                "specify_cli.invocation.executor.probe_primary_tracking",
                side_effect=OpCommitProbeError("git ls-tree failed"),
            ),
        ):
            executor.complete_invocation(invocation_id, outcome="done", closed_by="agent")

        mock_safe_commit.assert_not_called()
        assert executor.last_op_commit is not None
        assert executor.last_op_commit.skipped is not None
        assert "git probe failed" in executor.last_op_commit.skipped
        assert "git ls-tree failed" in executor.last_op_commit.skipped

    def test_second_close_costs_one_extra_git_call_for_the_decision(self, tmp_path: Path) -> None:
        """NFR-001: the primary-tracks decision is cached per executor."""
        import types

        from specify_cli.invocation import op_commit_policy

        _init_git_repo(tmp_path, track_ops=True)
        checkout_issue_branch(tmp_path)
        _setup_fixture_profiles(tmp_path)
        executor = ProfileInvocationExecutor(tmp_path)
        first_id = _open_op(executor)
        second_id = _open_op(executor)
        calls: list[object] = []

        def spy(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
            calls.append(args[0])
            return subprocess.run(*args, **kwargs)  # type: ignore[call-overload, no-any-return]  # spy forwards the policy's own subprocess.run call verbatim

        # Count the policy's own probes AND the tree listing it delegates to
        # kernel.git.runner; the executor's branch probes are not counted.
        from kernel.git import runner as kernel_runner

        spy_module = types.SimpleNamespace(
            run=spy, SubprocessError=subprocess.SubprocessError, TimeoutExpired=subprocess.TimeoutExpired
        )
        with (
            patch.object(op_commit_policy, "subprocess", spy_module),
            patch.object(kernel_runner, "subprocess", spy_module),
            patch("specify_cli.invocation.executor.safe_commit"),
        ):
            executor.complete_invocation(first_id, outcome="done", closed_by="agent")
            first_close = len(calls)
            executor.complete_invocation(second_id, outcome="done", closed_by="agent")
            second_close = len(calls) - first_close

        assert 2 < first_close <= 12  # symbolic-ref + ref probes + ls-tree + check-ignore
        assert second_close == 1
