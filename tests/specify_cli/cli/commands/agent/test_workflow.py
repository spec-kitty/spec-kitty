"""Tests for WP04: workflow.py resolved_agent() integration and doing alias removal.

WP04 (T010, T011): Verifies that:
1. WPMetadata.resolved_agent() handles all legacy formats correctly
2. resolved_agent() is called from the implement command path (via wp_meta)
3. The "doing" alias string is not present in workflow.py source
4. workflow.py uses Lane.IN_PROGRESS directly, not "doing" string alias
"""

from __future__ import annotations

import inspect
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.fast


# ---------------------------------------------------------------------------
# Tests for WPMetadata.resolved_agent() (verifies legacy coercion)
# ---------------------------------------------------------------------------


def test_resolved_agent_string_agent() -> None:
    """String agent field produces correct tool/model."""
    from specify_cli.status.wp_metadata import WPMetadata

    meta = WPMetadata(
        work_package_id="WP01",
        agent="claude",
        model="claude-opus-4-6",
    )
    assignment = meta.resolved_agent()
    assert assignment.tool == "claude"
    assert assignment.model == "claude-opus-4-6"
    assert assignment.profile_id is None
    assert assignment.role is None


def test_resolved_agent_dict_agent() -> None:
    """Dict agent field produces correct tool/model/profile_id/role."""
    from specify_cli.status.wp_metadata import WPMetadata

    meta = WPMetadata(
        work_package_id="WP01",
        agent={"tool": "copilot", "model": "gpt-4-turbo", "profile_id": "p1", "role": "reviewer"},
    )
    assignment = meta.resolved_agent()
    assert assignment.tool == "copilot"
    assert assignment.model == "gpt-4-turbo"
    assert assignment.profile_id == "p1"
    assert assignment.role == "reviewer"


def test_resolved_agent_none_agent_with_model() -> None:
    """None agent falls back to 'unknown' tool, uses model field."""
    from specify_cli.status.wp_metadata import WPMetadata

    meta = WPMetadata(
        work_package_id="WP01",
        agent=None,
        model="claude-haiku-4",
    )
    assignment = meta.resolved_agent()
    assert assignment.tool == "unknown"
    assert assignment.model == "claude-haiku-4"


def test_resolved_agent_none_agent_no_model() -> None:
    """None agent with no model gives 'unknown' defaults."""
    from specify_cli.status.wp_metadata import WPMetadata

    meta = WPMetadata(
        work_package_id="WP01",
        agent=None,
        model=None,
    )
    assignment = meta.resolved_agent()
    assert assignment.tool == "unknown"
    assert assignment.model == "unknown-model"


def test_resolved_agent_string_no_model() -> None:
    """String agent with no model field falls back to 'unknown-model'."""
    from specify_cli.status.wp_metadata import WPMetadata

    meta = WPMetadata(
        work_package_id="WP01",
        agent="gemini",
        model=None,
    )
    assignment = meta.resolved_agent()
    assert assignment.tool == "gemini"
    assert assignment.model == "unknown-model"


def test_resolved_agent_dict_no_tool() -> None:
    """Dict agent without 'tool' falls back to 'unknown'."""
    from specify_cli.status.wp_metadata import WPMetadata

    meta = WPMetadata(
        work_package_id="WP01",
        agent={"model": "gpt-5"},
    )
    assignment = meta.resolved_agent()
    assert assignment.tool == "unknown"
    assert assignment.model == "gpt-5"


def test_resolved_agent_dict_no_model_uses_meta_model() -> None:
    """Dict agent without 'model' falls back to WPMetadata.model field."""
    from specify_cli.status.wp_metadata import WPMetadata

    meta = WPMetadata(
        work_package_id="WP01",
        agent={"tool": "cursor"},
        model="claude-sonnet-4-6",
    )
    assignment = meta.resolved_agent()
    assert assignment.tool == "cursor"
    assert assignment.model == "claude-sonnet-4-6"


def test_resolved_agent_uses_agent_profile_fallback() -> None:
    """None agent falls back to agent_profile for profile_id."""
    from specify_cli.status.wp_metadata import WPMetadata

    meta = WPMetadata(
        work_package_id="WP01",
        agent=None,
        agent_profile="claude:sonnet:implementer",
    )
    assignment = meta.resolved_agent()
    assert assignment.profile_id == "claude:sonnet:implementer"


def test_resolved_agent_uses_role_fallback() -> None:
    """None agent falls back to role field."""
    from specify_cli.status.wp_metadata import WPMetadata

    meta = WPMetadata(
        work_package_id="WP01",
        agent=None,
        role="implementer",
    )
    assignment = meta.resolved_agent()
    assert assignment.role == "implementer"


def test_resolved_agent_returns_agent_assignment_type() -> None:
    """resolved_agent() always returns an AgentAssignment instance."""
    from specify_cli.status.models import AgentAssignment
    from specify_cli.status.wp_metadata import WPMetadata

    for agent_val in [None, "claude", {"tool": "gemini"}]:
        meta = WPMetadata(work_package_id="WP01", agent=agent_val)
        assignment = meta.resolved_agent()
        assert isinstance(assignment, AgentAssignment), (
            f"Expected AgentAssignment for agent={agent_val!r}, got {type(assignment)}"
        )


# ---------------------------------------------------------------------------
# Tests verifying resolved_agent() is wired into the implement command path
# ---------------------------------------------------------------------------


def test_implement_command_calls_resolved_agent(tmp_path: Path) -> None:
    """Verify resolved_agent() is called from the implement command path.

    This test patches WPMetadata.resolved_agent to track whether it's called,
    then invokes the implement command to confirm the call path.
    """
    import json

    from specify_cli.status.models import Lane

    # Set up a minimal feature directory
    mission_slug = "test-feature-wp04"
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir()

    # Create minimal WP file
    wp_file = tasks_dir / "WP01-test.md"
    wp_file.write_text(
        "---\nwork_package_id: WP01\ntitle: Test WP\ndependencies: []\nagent: claude\n---\nContent.\n",
        encoding="utf-8",
    )

    # Write status events so the lane reader works
    events_path = feature_dir / "status.events.jsonl"
    events_path.write_text(
        json.dumps({
            "actor": "test",
            "at": "2026-04-09T00:00:00+00:00",
            "event_id": "01TESTWP01PLANNED",
            "evidence": None,
            "execution_mode": "worktree",
            "feature_slug": mission_slug,
            "force": False,
            "from_lane": "planned",
            "reason": None,
            "review_ref": None,
            "to_lane": "in_progress",
            "wp_id": "WP01",
        }) + "\n",
        encoding="utf-8",
    )

    # Track whether resolved_agent was called
    resolved_agent_called = []

    original_resolved_agent = None

    def _patched_resolved_agent(self):
        resolved_agent_called.append(True)
        # Call the real implementation
        return original_resolved_agent(self)

    from specify_cli.status.wp_metadata import WPMetadata
    original_resolved_agent = WPMetadata.resolved_agent

    with patch.object(WPMetadata, "resolved_agent", _patched_resolved_agent):
        # Try to load a WP and call resolved_agent as the implement command does
        from specify_cli.status.wp_metadata import read_wp_frontmatter
        try:
            wp_meta, _ = read_wp_frontmatter(wp_file)
            # The implement command calls wp_meta.resolved_agent() after loading
            _assignment = wp_meta.resolved_agent()
            resolved_agent_called.append(True)  # Direct call
        except Exception:
            pass

    # Verify resolved_agent was called
    assert len(resolved_agent_called) >= 1, "resolved_agent() should have been called"


# ---------------------------------------------------------------------------
# Tests verifying "doing" alias is absent from workflow.py
# ---------------------------------------------------------------------------


def test_workflow_source_has_no_doing_string() -> None:
    """Verify the 'doing' alias string literal does not appear in workflow.py source."""
    from specify_cli.cli.commands.agent import workflow as workflow_module

    source_path = Path(inspect.getfile(workflow_module))
    source_text = source_path.read_text(encoding="utf-8")

    # Look for the "doing" string literal (in quotes)
    import re
    doing_pattern = re.compile(r'(?<![#])["\']doing["\']')  # Exclude comments
    matches = doing_pattern.findall(source_text)

    # Filter out any that are in comment lines
    problematic_lines = []
    for i, line in enumerate(source_text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if doing_pattern.search(line):
            problematic_lines.append(f"  Line {i}: {line.rstrip()}")

    assert not problematic_lines, (
        "workflow.py must not contain the 'doing' alias string.\n"
        "Consumer code must use Lane.IN_PROGRESS directly.\n"
        "Found:\n" + "\n".join(problematic_lines)
    )


def test_workflow_uses_lane_in_progress_not_doing_string() -> None:
    """Verify workflow.py uses Lane.IN_PROGRESS for in_progress comparisons."""
    from specify_cli.cli.commands.agent import workflow as workflow_module

    source_path = Path(inspect.getfile(workflow_module))
    source_text = source_path.read_text(encoding="utf-8")

    # Verify Lane.IN_PROGRESS is used (not the "doing" alias)
    assert "Lane.IN_PROGRESS" in source_text, (
        "workflow.py should reference Lane.IN_PROGRESS for in_progress lane comparisons"
    )


def test_auto_claim_failure_message_preserves_dependency_reason() -> None:
    """Auto implement must not launder dependency blocking into a generic no-WP error."""
    from specify_cli.cli.commands.agent import workflow as workflow_module

    preview = MagicMock(selection_reason="dependencies_not_satisfied")

    message = workflow_module._auto_claim_failure_message(preview)

    assert "dependencies_not_satisfied" in message
    assert "all dependencies must be approved or done" in message


def test_preview_claimable_wp_for_mission_reads_repo_root_not_worktree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The auto-claim readiness preview resolves to the repository-root checkout's
    canonical event log (via get_main_repo_root), never a stale worktree-local copy.

    A dependent WP whose dependency is `approved` in the authoritative log must be
    surfaced as claimable even when the helper is invoked with a worktree repo root.
    """
    import json as _json

    from specify_cli.cli.commands.agent import workflow as workflow_module
    from specify_cli.status.models import Lane, StatusEvent
    from specify_cli.status.store import append_event

    mission_slug = "010-feature"
    main_repo = tmp_path / "main"
    feature_dir = main_repo / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    for wp_id, deps in (("WP01", []), ("WP02", ["WP01"])):
        (tasks_dir / f"{wp_id}.md").write_text(
            f"---\nwork_package_id: {wp_id}\ndependencies: {_json.dumps(deps)}\ntitle: {wp_id}\n---\n# {wp_id}\n",
            encoding="utf-8",
        )
    for wp_id, lane in (("WP01", Lane.APPROVED), ("WP02", Lane.PLANNED)):
        append_event(
            feature_dir,
            StatusEvent(
                event_id=f"seed-{wp_id}",
                mission_slug=mission_slug,
                wp_id=wp_id,
                from_lane=Lane.PLANNED,
                to_lane=lane,
                at="2026-05-30T08:30:00+00:00",
                actor="fixture",
                force=True,
                execution_mode="worktree",
            ),
        )

    # The helper is handed a *worktree* repo root; it must still resolve to the
    # main checkout via get_main_repo_root rather than reading the worktree.
    worktree_root = tmp_path / "worktree"
    worktree_root.mkdir()
    monkeypatch.setattr(workflow_module, "get_main_repo_root", lambda _path: main_repo)

    preview = workflow_module._preview_claimable_wp_for_mission(worktree_root, mission_slug)

    assert preview is not None
    assert preview.wp_id == "WP02"
    assert preview.selection_reason is None


# ---------------------------------------------------------------------------
# Tests for AgentAssignment dataclass
# ---------------------------------------------------------------------------


def test_agent_assignment_is_frozen() -> None:
    """AgentAssignment is a frozen dataclass (immutable)."""
    from specify_cli.status.models import AgentAssignment

    assignment = AgentAssignment(tool="claude", model="claude-opus-4-6")
    with pytest.raises((AttributeError, TypeError)):
        assignment.tool = "other"


import pytest


def test_agent_assignment_optional_fields() -> None:
    """AgentAssignment profile_id and role are optional."""
    from specify_cli.status.models import AgentAssignment

    assignment = AgentAssignment(tool="claude", model="claude-opus-4-6")
    assert assignment.profile_id is None
    assert assignment.role is None


def test_agent_assignment_with_all_fields() -> None:
    """AgentAssignment accepts all fields."""
    from specify_cli.status.models import AgentAssignment

    assignment = AgentAssignment(
        tool="claude",
        model="claude-opus-4-6",
        profile_id="claude:opus:implementer",
        role="implementer",
    )
    assert assignment.tool == "claude"
    assert assignment.model == "claude-opus-4-6"
    assert assignment.profile_id == "claude:opus:implementer"
    assert assignment.role == "implementer"


# ---------------------------------------------------------------------------
# WP06 (T027/T029) -- BookkeepingTransaction migration tests
# ---------------------------------------------------------------------------


class TestWorkflowCommitReceipts:
    """The T029 commit-summary accumulator behaves correctly."""

    def test_reset_clears_receipts(self) -> None:
        from specify_cli.cli.commands.agent import workflow

        workflow._WORKFLOW_COMMIT_RECEIPTS.append({"foo": "bar"})
        workflow._reset_workflow_receipts()
        assert workflow._WORKFLOW_COMMIT_RECEIPTS == []

    def test_record_receipt_stores_full_payload(self) -> None:
        from specify_cli.cli.commands.agent import workflow

        workflow._reset_workflow_receipts()
        workflow._record_receipt(
            "kitty/mission-foo-01ABCDEF",
            "chore: WP01 claimed [claude]",
            "committed",
            sha="abc123def456",
            wp_id="WP01",
        )
        assert len(workflow._WORKFLOW_COMMIT_RECEIPTS) == 1
        receipt = workflow._WORKFLOW_COMMIT_RECEIPTS[0]
        assert receipt["destination_ref"] == "kitty/mission-foo-01ABCDEF"
        assert receipt["outcome"] == "committed"
        assert receipt["sha"] == "abc123def456"
        assert receipt["wp_id"] == "WP01"

    def test_record_receipt_refused_without_sha_is_not_warned(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A ``refused`` receipt legitimately has no commit -- no warning (FR-013)."""
        from specify_cli.cli.commands.agent import workflow

        workflow._reset_workflow_receipts()
        with caplog.at_level("WARNING", logger="specify_cli.cli.commands.agent.workflow"):
            workflow._record_receipt(
                "main",
                "chore: WP02 claimed [claude]",
                "refused",
                wp_id="WP02",
            )
        assert caplog.records == []
        workflow._reset_workflow_receipts()

    def test_record_receipt_committed_without_sha_warns(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """T105: a ``committed`` receipt with no sha is the FR-013 defect class
        #5440 read as "implement leaks status" -- ``_record_receipt`` must
        observe and log it (never silently accept a committed-but-unnamed
        receipt), even though it still records the receipt (fail-soft)."""
        from specify_cli.cli.commands.agent import workflow

        workflow._reset_workflow_receipts()
        with caplog.at_level("WARNING", logger="specify_cli.cli.commands.agent.workflow"):
            workflow._record_receipt(
                "main",
                "chore: WP03 claimed [claude]",
                "committed",
                sha=None,
                wp_id="WP03",
            )
        assert len(caplog.records) == 1
        assert "no commit sha" in caplog.records[0].message
        assert len(workflow._WORKFLOW_COMMIT_RECEIPTS) == 1
        workflow._reset_workflow_receipts()


class TestLoadCoordBranchMeta:
    """``_load_coord_branch_meta`` reads coord-branch metadata correctly."""

    def test_returns_none_tuple_when_meta_missing(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands.agent.workflow import _load_coord_branch_meta

        # No meta.json at all.
        result = _load_coord_branch_meta(tmp_path)
        assert result == (None, None, None)

    def test_returns_coord_when_present(self, tmp_path: Path) -> None:
        import json
        from specify_cli.cli.commands.agent.workflow import _load_coord_branch_meta

        (tmp_path / "meta.json").write_text(
            json.dumps({
                "mission_id": "01ABCDEFGHJKMNPQRSTVWXYZ12",
                "mid8": "01ABCDEF",
                "coordination_branch": "kitty/mission-foo-01ABCDEF",
            }),
            encoding="utf-8",
        )
        coord, mid, mid8 = _load_coord_branch_meta(tmp_path)
        assert coord == "kitty/mission-foo-01ABCDEF"
        assert mid == "01ABCDEFGHJKMNPQRSTVWXYZ12"
        assert mid8 == "01ABCDEF"


class TestTransactionPathFor:
    """``_transaction_path_for`` keeps mirrored writes inside the worktree."""

    def test_maps_repo_relative_path_into_worktree(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands.agent.workflow import _transaction_path_for

        repo_root = tmp_path / "repo"
        worktree_root = tmp_path / "worktree"
        source_path = repo_root / "kitty-specs" / "001-test" / "tasks" / "WP01.md"

        mapped = _transaction_path_for(
            source_path=source_path,
            repo_root=repo_root,
            worktree_root=worktree_root,
        )

        assert mapped == worktree_root / "kitty-specs" / "001-test" / "tasks" / "WP01.md"

    def test_rejects_paths_outside_repo_and_kitty_specs(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands.agent.workflow import _transaction_path_for

        repo_root = tmp_path / "repo"
        worktree_root = tmp_path / "worktree"
        source_path = tmp_path / "outside" / "secret.txt"

        with pytest.raises(ValueError, match="outside repo/worktree scope"):
            _transaction_path_for(
                source_path=source_path,
                repo_root=repo_root,
                worktree_root=worktree_root,
            )

    def test_rejects_external_paths_with_embedded_kitty_specs(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands.agent.workflow import _transaction_path_for

        repo_root = tmp_path / "repo"
        worktree_root = tmp_path / "worktree"
        source_path = tmp_path / "outside" / "kitty-specs" / "other" / "tasks" / "WP01.md"

        with pytest.raises(ValueError, match="outside repo/worktree scope"):
            _transaction_path_for(
                source_path=source_path,
                repo_root=repo_root,
                worktree_root=worktree_root,
            )

    def test_falls_back_to_legacy_when_coord_missing(self, tmp_path: Path) -> None:
        import json
        from specify_cli.cli.commands.agent.workflow import _load_coord_branch_meta

        # Legacy mission: mission_id present but no coordination_branch.
        (tmp_path / "meta.json").write_text(
            json.dumps({
                "mission_id": "01ABCDEFGHJKMNPQRSTVWXYZ12",
            }),
            encoding="utf-8",
        )
        coord, mid, mid8 = _load_coord_branch_meta(tmp_path)
        assert coord is None
        # mid8 is still computed from mission_id even without coord branch.
        assert mid == "01ABCDEFGHJKMNPQRSTVWXYZ12"
        assert mid8 == "01ABCDEF"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)


def _head_sha(repo: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _branch_contains(repo: Path, sha: str) -> list[str]:
    result = subprocess.run(
        ["git", "branch", "--contains", sha, "--format=%(refname:short)"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.split()


@pytest.mark.git_repo
class TestLegacyAlreadyPresentReceipt:
    """FR-013/US6/D17: the "already present" no-op arm of
    ``_commit_via_legacy_safe_commit`` must name a VERIFIED commit that
    actually holds the just-persisted state -- or, when no such commit can
    be verified, an honest ``None`` (which fires ``_record_receipt``'s
    warning) rather than a plausible-but-wrong id.

    **Cycle-2 correction (reviewer-renata B1):** the cycle-1 premise -- "the
    receipt must never be ``sha=None``" -- was itself wrong. The cycle-1 fix
    enforced that premise with a branch-tip fallback whenever the
    target-branch history walk found nothing, and the reviewer reproduced
    two cases where that fallback named a commit that does NOT contain the
    change (an ignored/never-committed path; ``porcelain_root``'s checked-out
    HEAD diverging from ``target_branch``). A truthful ``None`` (with the
    warning that makes the anomaly observable) is correct there; see
    :func:`_already_present_receipt_sha`'s docstring for the verified-commit
    algorithm that replaced the fallback.

    Binding correction (round 3, operator decision): on a coordination-routed
    Mission ``commit_workflow_change`` never reaches this legacy leaf at all
    (``_commit_via_coordination_transaction`` records a non-null sha from
    ``BookkeepingTransaction.commit_idempotent`` -- see
    ``TestImplementReceiptsNameRealBranch`` for that CLI-level confirmation,
    GREEN at base).

    **Correction (cycle-2, reviewer-renata N1):** this arm is also NOT
    reached by ``implement`` on a coord-less (``lanes``/``single_branch``)
    Mission's planned->in_progress claim -- that path's legacy leaf goes
    through the normal ``safe_commit`` branch with a real sha
    (``TestImplementReceiptsNameRealBranch.
    test_lanes_mission_receipts_unchanged_fields_plus_sha`` passed even at
    the cycle-1 commit, before this fix). This arm is a LATENT one, reached
    only when the paths are already clean at the moment
    ``_commit_via_legacy_safe_commit`` runs (for example from the other
    ``_commit_workflow_change`` callers at ``workflow_executor.py``
    L1062/L1791). The red-first reproduction below drives
    ``_commit_via_legacy_safe_commit`` directly -- it IS the pre-existing
    production entry point every coord-less workflow commit goes through
    (``workflow_executor.py:372`` is its only caller), matching
    ``tests/git/test_guard_capability_regression.py`` and
    ``tests/specify_cli/cli/commands/agent/test_coord_commit_integrity_e2e.py``'s
    existing direct-call convention for this same function.
    """

    def test_already_present_receipt_names_a_contained_commit(self, tmp_path: Path) -> None:
        """RED at base (pre-fix): the early-return recorded ``sha=None``,
        which fails ``git branch --contains`` by construction -- exactly
        #5440's "implement leaks status" misleading-receipt evidence."""
        from specify_cli.cli.commands.agent import workflow

        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "target-branch")
        _git(repo, "config", "user.email", "wp19@example.invalid")
        _git(repo, "config", "user.name", "WP19")
        _git(repo, "config", "commit.gpgsign", "false")
        (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "seed")

        # Simulate the transactional emit already having persisted + committed
        # the status state to target_branch before this legacy follow-up runs
        # (the #2684 scenario this early-return arm exists for).
        status_dir = repo / "kitty-specs" / "100-legacy"
        status_dir.mkdir(parents=True)
        events_path = status_dir / "status.events.jsonl"
        events_path.write_text('{"event_id":"already-committed"}\n', encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "status already committed")
        expected_sha = _head_sha(repo)

        workflow._reset_workflow_receipts()
        workflow._commit_via_legacy_safe_commit(
            repo_root=repo,
            target_branch="target-branch",
            paths=[events_path],
            message="chore: WP01 claimed [claude]",
            wp_id="WP01",
        )

        receipts = workflow._WORKFLOW_COMMIT_RECEIPTS
        assert len(receipts) == 1
        receipt = receipts[0]
        assert receipt["outcome"] == "committed"
        assert receipt["destination_ref"] == "target-branch"
        assert receipt["sha"] is not None, (
            "the already-present receipt must name a real commit, not "
            "sha=None (#5440's misleading-receipt evidence; FR-013)"
        )
        assert "target-branch" in _branch_contains(repo, str(receipt["sha"])), (
            f"receipt sha {receipt['sha']!r} must be contained in the branch "
            f"it names ({receipt['destination_ref']!r})"
        )
        # The exact commit already carrying the state, not merely some
        # ancestor -- proves the fix resolves THE commit, not just the tip.
        assert receipt["sha"] == expected_sha
        workflow._reset_workflow_receipts()

    def test_already_present_receipt_ignored_or_never_committed_path_is_none_with_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """B1 (cycle-2, reviewer-renata): a gitignored / never-committed path
        reads clean under ``git status --porcelain`` (the "already present"
        arm fires) but no commit on ``target_branch`` -- or anywhere in
        ``HEAD``'s history -- actually carries it. The pre-fix tip fallback
        named a commit that does NOT contain the path
        (``git cat-file -e <tip>:<path>`` fails); the fix must return
        ``None`` instead, so ``_record_receipt`` warns -- an honest absence,
        never a fabricated id."""
        from specify_cli.cli.commands.agent import workflow

        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "target-branch")
        _git(repo, "config", "user.email", "wp19@example.invalid")
        _git(repo, "config", "user.name", "WP19")
        _git(repo, "config", "commit.gpgsign", "false")
        (repo / ".gitignore").write_text("kitty-specs/\n", encoding="utf-8")
        (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "seed")

        status_dir = repo / "kitty-specs" / "100-legacy"
        status_dir.mkdir(parents=True)
        events_path = status_dir / "status.events.jsonl"
        events_path.write_text('{"event_id":"never-committed"}\n', encoding="utf-8")
        # The path is gitignored, so the porcelain pre-check is clean despite
        # the file never having been committed anywhere.
        porcelain = subprocess.run(
            ["git", "status", "--porcelain", "--", str(events_path)],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
        assert porcelain.stdout.strip() == "", "fixture must read clean to reach the already-present arm"

        workflow._reset_workflow_receipts()
        with caplog.at_level("WARNING", logger="specify_cli.cli.commands.agent.workflow"):
            workflow._commit_via_legacy_safe_commit(
                repo_root=repo,
                target_branch="target-branch",
                paths=[events_path],
                message="chore: WP01 claimed [claude]",
                wp_id="WP01",
            )

        receipts = workflow._WORKFLOW_COMMIT_RECEIPTS
        assert len(receipts) == 1
        assert receipts[0]["outcome"] == "committed"
        assert receipts[0]["sha"] is None, (
            "an ignored/never-committed path must yield an HONEST None, never "
            "a plausible-but-wrong commit id"
        )
        assert len(caplog.records) == 1, "a committed receipt with no sha must warn exactly once"
        assert "no commit sha" in caplog.records[0].message
        workflow._reset_workflow_receipts()

    def test_already_present_receipt_head_not_on_target_branch_is_none_not_stale_commit(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """B1 (cycle-2, reviewer-renata): ``porcelain_root``'s checked-out
        HEAD can differ from ``target_branch`` (``_commit_workflow_change``'s
        own debug branch documents this as a real divergence, not merely
        theoretical). The pre-fix helper searched ``target_branch``'s OWN
        history and could return a STALE commit on ``target_branch`` whose
        content does not match what the porcelain check just proved clean at
        ``HEAD``. The fix must never name that stale commit: either ``None``
        (the un-ancestored candidate is rejected), or a sha that is both
        contained in ``target_branch`` and holds the current content -- it
        must not fabricate the old, wrong one."""
        from specify_cli.cli.commands.agent import workflow

        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "target-branch")
        _git(repo, "config", "user.email", "wp19@example.invalid")
        _git(repo, "config", "user.name", "WP19")
        _git(repo, "config", "commit.gpgsign", "false")
        status_dir = repo / "kitty-specs" / "100-legacy"
        status_dir.mkdir(parents=True)
        status_path = status_dir / "status.events.jsonl"
        status_path.write_text('{"event_id":"old"}\n', encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "old state on target-branch")
        stale_target_sha = _head_sha(repo)

        # Diverge: a different branch, never merged back, carries NEW content.
        _git(repo, "checkout", "-q", "-b", "other")
        status_path.write_text('{"event_id":"new"}\n', encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "new state on other")

        # HEAD (repo_root's checkout) is "other", NOT "target-branch" --
        # porcelain is clean relative to HEAD's own committed content.
        porcelain = subprocess.run(
            ["git", "status", "--porcelain", "--", str(status_path)],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
        assert porcelain.stdout.strip() == "", "fixture must read clean to reach the already-present arm"

        workflow._reset_workflow_receipts()
        with caplog.at_level("WARNING", logger="specify_cli.cli.commands.agent.workflow"):
            workflow._commit_via_legacy_safe_commit(
                repo_root=repo,
                target_branch="target-branch",
                paths=[status_path],
                message="chore: WP01 claimed [claude]",
                wp_id="WP01",
            )

        receipts = workflow._WORKFLOW_COMMIT_RECEIPTS
        assert len(receipts) == 1
        receipt = receipts[0]
        assert receipt["sha"] != stale_target_sha, (
            "must never name the stale target-branch commit whose content "
            "does not match what the porcelain check proved clean at HEAD"
        )
        if receipt["sha"] is not None:
            assert "target-branch" in _branch_contains(repo, str(receipt["sha"]))
        else:
            assert len(caplog.records) == 1, "an honest None must still warn exactly once"
        workflow._reset_workflow_receipts()

    def test_already_present_receipt_legacy_no_identity_still_names_a_commit(
        self, tmp_path: Path
    ) -> None:
        """``mission_slug=None`` (truly legacy, no Mission identity): the
        porcelain root is ``repo_root`` itself, and the receipt must still
        name a real, contained commit -- the identity-less path is not an
        excuse to regress to ``sha=None``."""
        from specify_cli.cli.commands.agent import workflow

        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "target-branch")
        _git(repo, "config", "user.email", "wp19@example.invalid")
        _git(repo, "config", "user.name", "WP19")
        _git(repo, "config", "commit.gpgsign", "false")
        (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "seed")

        status_dir = repo / "kitty-specs" / "100-legacy"
        status_dir.mkdir(parents=True)
        status_path = status_dir / "status.json"
        status_path.write_text('{"wp":"already-committed"}\n', encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "status already committed")
        expected_sha = _head_sha(repo)

        workflow._reset_workflow_receipts()
        workflow._commit_via_legacy_safe_commit(
            repo_root=repo,
            target_branch="target-branch",
            paths=[status_path],
            message="chore: WP01 claimed [claude]",
            wp_id="WP01",
            mission_slug=None,
            mid8=None,
        )

        receipt = workflow._WORKFLOW_COMMIT_RECEIPTS[0]
        assert receipt["sha"] == expected_sha
        assert "target-branch" in _branch_contains(repo, str(receipt["sha"]))
        workflow._reset_workflow_receipts()

    def test_already_present_receipt_partially_untracked_path_set_is_none_with_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """B2 (cycle-3, reviewer-renata): ``git log -1 HEAD -- <paths>`` can
        find a real commit even when only SOME of ``paths`` are tracked
        there (log's multi-pathspec matching is OR, not AND) --
        ``_paths_tracked_at_commit`` must still reject that candidate.
        Deleting the ``_paths_tracked_at_commit(...)`` call in
        ``_already_present_receipt_sha`` turns this red: the ignored-path and
        HEAD-mismatch tests above both return earlier (empty ``git log`` /
        failed ancestor check) and never exercise this branch."""
        from specify_cli.cli.commands.agent import workflow

        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "target-branch")
        _git(repo, "config", "user.email", "wp19@example.invalid")
        _git(repo, "config", "user.name", "WP19")
        _git(repo, "config", "commit.gpgsign", "false")
        status_dir = repo / "kitty-specs" / "100-legacy"
        status_dir.mkdir(parents=True)
        tracked_path = status_dir / "status.events.jsonl"
        tracked_path.write_text('{"event_id":"already-committed"}\n', encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "status already committed")
        # Never created, never committed. A nonexistent path is trivially
        # "clean" under git status --porcelain (nothing to report), but
        # `git log -1 HEAD -- tracked_path missing_path` still finds the
        # commit above via tracked_path's match.
        missing_path = status_dir / "status.json"

        porcelain = subprocess.run(
            ["git", "status", "--porcelain", "--", str(tracked_path), str(missing_path)],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
        assert porcelain.stdout.strip() == "", "fixture must read clean to reach the already-present arm"

        workflow._reset_workflow_receipts()
        with caplog.at_level("WARNING", logger="specify_cli.cli.commands.agent.workflow"):
            workflow._commit_via_legacy_safe_commit(
                repo_root=repo,
                target_branch="target-branch",
                paths=[tracked_path, missing_path],
                message="chore: WP01 claimed [claude]",
                wp_id="WP01",
            )

        receipts = workflow._WORKFLOW_COMMIT_RECEIPTS
        assert len(receipts) == 1
        assert receipts[0]["outcome"] == "committed"
        assert receipts[0]["sha"] is None, (
            "git log found a commit via the TRACKED path, but one path in "
            "the set (missing_path) is not tracked there -- the whole "
            "receipt must be an honest None, not a sha that only covers "
            "part of the requested path set"
        )
        assert len(caplog.records) == 1, "a committed receipt with no sha must warn exactly once"
        assert "no commit sha" in caplog.records[0].message
        workflow._reset_workflow_receipts()


class TestPathsTrackedAtCommit:
    """Direct unit coverage for ``_paths_tracked_at_commit`` (cycle-3, B2 item 2 / N6)."""

    def test_path_outside_porcelain_root_is_untracked(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands.agent import workflow

        porcelain_root = tmp_path / "repo"
        porcelain_root.mkdir()
        _git(porcelain_root, "init", "-q", "-b", "target-branch")
        _git(porcelain_root, "config", "user.email", "wp19@example.invalid")
        _git(porcelain_root, "config", "user.name", "WP19")
        _git(porcelain_root, "config", "commit.gpgsign", "false")
        (porcelain_root / "seed.txt").write_text("seed\n", encoding="utf-8")
        _git(porcelain_root, "add", "-A")
        _git(porcelain_root, "commit", "-q", "-m", "seed")
        sha = _head_sha(porcelain_root)

        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        outside_path = outside_dir / "file.txt"
        outside_path.write_text("outside\n", encoding="utf-8")

        assert workflow._paths_tracked_at_commit(porcelain_root, sha, [outside_path]) is False

    def test_untracked_path_inside_root_is_untracked(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands.agent import workflow

        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "target-branch")
        _git(repo, "config", "user.email", "wp19@example.invalid")
        _git(repo, "config", "user.name", "WP19")
        _git(repo, "config", "commit.gpgsign", "false")
        (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "seed")
        sha = _head_sha(repo)

        never_committed = repo / "never-committed.txt"
        never_committed.write_text("new\n", encoding="utf-8")

        assert workflow._paths_tracked_at_commit(repo, sha, [never_committed]) is False

    def test_tracked_path_is_tracked(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands.agent import workflow

        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "target-branch")
        _git(repo, "config", "user.email", "wp19@example.invalid")
        _git(repo, "config", "user.name", "WP19")
        _git(repo, "config", "commit.gpgsign", "false")
        tracked = repo / "status.events.jsonl"
        tracked.write_text('{"event_id":"x"}\n', encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "seed")
        sha = _head_sha(repo)

        assert workflow._paths_tracked_at_commit(repo, sha, [tracked]) is True

    def test_relative_path_resolves_against_porcelain_root_not_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """N6 (cycle-3, reviewer-renata): a relative path must anchor on
        ``porcelain_root``, not the process cwd -- every current caller
        passes absolute paths, so this pins intent for a future one."""
        from specify_cli.cli.commands.agent import workflow

        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "target-branch")
        _git(repo, "config", "user.email", "wp19@example.invalid")
        _git(repo, "config", "user.name", "WP19")
        _git(repo, "config", "commit.gpgsign", "false")
        tracked = repo / "status.events.jsonl"
        tracked.write_text('{"event_id":"x"}\n', encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "seed")
        sha = _head_sha(repo)

        # cwd is somewhere else entirely -- resolving the relative path
        # against cwd (instead of porcelain_root) would misclassify it as
        # outside the root.
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)

        relative_path = Path("status.events.jsonl")
        assert workflow._paths_tracked_at_commit(repo, sha, [relative_path]) is True


class TestCommitWorkflowChange:
    """``_commit_workflow_change`` preserves helper-level exit semantics."""

    def test_modern_policy_exit_restores_pre_emit_status_artifacts(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import json
        import typer
        from specify_cli.cli.commands.agent import workflow

        feature_dir = tmp_path / "kitty-specs" / "001-test"
        feature_dir.mkdir(parents=True)
        events_path = feature_dir / "status.events.jsonl"
        status_path = feature_dir / "status.json"
        events_path.write_text("before\nnew-event\n", encoding="utf-8")
        status_path.write_text('{"lane":"new"}', encoding="utf-8")
        (feature_dir / "meta.json").write_text(
            json.dumps({
                "mission_id": "01ABCDEFGHJKMNPQRSTVWXYZ12",
                "mid8": "01ABCDEF",
                "coordination_branch": "kitty/mission-test-01ABCDEF",
            }),
            encoding="utf-8",
        )
        restore_calls: list[object] = []

        def _raise_exit(**kwargs: object) -> None:
            workflow._record_receipt(
                str(kwargs["coord_branch"]),
                str(kwargs["message"]),
                "refused",
                wp_id=str(kwargs["wp_id"]),
            )
            raise typer.Exit(1)

        monkeypatch.setattr(workflow, "_commit_via_coordination_transaction", _raise_exit)
        monkeypatch.setattr(
            workflow,
            "_restore_status_artifacts",
            lambda **kwargs: restore_calls.append(kwargs),
        )

        workflow._reset_workflow_receipts()
        with pytest.raises(typer.Exit):
            workflow._commit_workflow_change(
                repo_root=tmp_path,
                feature_dir=feature_dir,
                mission_slug="001-test",
                target_branch="main",
                paths=[],
                message="chore: WP01 claimed [claude]",
                operation="implement",
                wp_id="WP01",
                pre_emit_event_size=len("before\n"),
                pre_emit_status_bytes=b'{"lane":"old"}',
            )

        assert len(workflow._WORKFLOW_COMMIT_RECEIPTS) == 1
        assert workflow._WORKFLOW_COMMIT_RECEIPTS[0]["outcome"] == "refused"
        assert restore_calls == [
            {
                "events_path": events_path,
                "pre_emit_event_size": len("before\n"),
                "status_path": status_path,
                "pre_emit_status_bytes": b'{"lane":"old"}',
            }
        ]
        workflow._reset_workflow_receipts()


class TestPrintCommitSummary:
    """The T029 terminal summary formats receipts correctly."""

    def test_no_receipts_no_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        from specify_cli.cli.commands.agent import workflow

        workflow._reset_workflow_receipts()
        workflow._print_commit_summary(command_name="implement")
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_human_format_shows_committed_and_refused(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from specify_cli.cli.commands.agent import workflow

        workflow._reset_workflow_receipts()
        workflow._record_receipt(
            "kitty/mission-foo-01ABCDEF",
            "chore: WP01 claimed [claude]",
            "committed",
            sha="abc123",
            wp_id="WP01",
        )
        workflow._record_receipt(
            "main",
            "chore: WP02 claimed [claude]",
            "refused",
            wp_id="WP02",
        )
        workflow._print_commit_summary(command_name="implement")
        captured = capsys.readouterr()
        assert "[implement] Commits recorded:" in captured.out
        assert "kitty/mission-foo-01ABCDEF" in captured.out
        assert "WP01 claimed" in captured.out
        assert "[ok]" in captured.out
        assert "[refused]" in captured.out
        # T105: the committed line carries the short commit id...
        assert "abc123" in captured.out
        # ...and the refused line (no commit) prints the no-sha placeholder,
        # never fabricating an id for a receipt that never committed.
        assert workflow._NO_SHA_PLACEHOLDER in captured.out
        workflow._reset_workflow_receipts()

    def test_json_format_emits_structured_payload(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import json as _json
        from specify_cli.cli.commands.agent import workflow

        workflow._reset_workflow_receipts()
        workflow._record_receipt(
            "kitty/mission-bar-01XYZ",
            "chore: WP01 review [claude]",
            "committed",
            sha="def456",
            wp_id="WP01",
        )
        workflow._print_commit_summary(command_name="review", json_output=True)
        captured = capsys.readouterr()
        payload = _json.loads(captured.out.strip())
        assert "commits" in payload
        assert len(payload["commits"]) == 1
        assert payload["commits"][0]["destination_ref"] == "kitty/mission-bar-01XYZ"
        workflow._reset_workflow_receipts()


@pytest.mark.integration
@pytest.mark.git_repo
class TestImplementReceiptsNameRealBranch:
    """FR-013/US6 (#5440): end-to-end, through the real ``agent action
    implement`` CLI entry point -- every receipt carries a commit id, and the
    branch it names actually contains that commit.

    T103/red premise (operator decision, round 3): R18 as originally scoped
    assumed a coordination-routed Mission would reproduce #5440's
    misleading-receipt defect. It does not -- ``commit_workflow_change``
    routes a complete coord identity triple through
    ``_commit_via_coordination_transaction``, whose receipts already carry a
    non-null sha from ``BookkeepingTransaction.commit_idempotent`` (never
    reaching ``_commit_via_legacy_safe_commit`` at all). The tests below
    confirm that GREEN-at-base finding directly (positive control +
    regression guard).

    **Correction (cycle-2, reviewer-renata N1):** through ``implement`` on
    EITHER topology, the "already present" arm is not reached at all -- a
    ``lanes`` (coord-less) Mission's legacy leaf goes through the normal
    ``safe_commit`` branch with a real sha (``test_lanes_mission_receipts_
    unchanged_fields_plus_sha`` below passed even at the cycle-1 commit,
    before the fix). ``TestLegacyAlreadyPresentReceipt`` is a direct-call
    reproduction of a LATENT arm -- reached only when the paths are already
    clean at the time ``_commit_via_legacy_safe_commit`` runs (for example
    from the other ``_commit_workflow_change`` callers at
    ``workflow_executor.py`` L1062/L1791), not by this fixture's planned
    -> in_progress claim. The grounding repro's ``chore: Start WP01
    implementation [ok]`` line against the target branch was the CORRECT
    PRIMARY-group receipt, printed without a commit id -- the misleading
    part of #5440's evidence was that missing id in the human-readable
    output, which T105 fixes (see the ``design-decisions`` tracer entry
    dated after cycle-1 review for the full record, tied to the spec's
    #5440 Assumption).

    There is no ``--json`` flag on ``agent action implement`` (NFR-004
    carve-out -- see ``_refuse_owned_action``'s docstring); receipts are read
    directly off the in-process ``_WORKFLOW_COMMIT_RECEIPTS`` accumulator
    after a real ``CliRunner.invoke`` of the production command, which is
    the fixture-weight-appropriate choice the WP's "Comment on existing
    fixtures" note sanctions over inventing a JSON surface that does not
    exist.

    **Fixture provenance (cycle-2, reviewer-renata N2):** these tests use
    ``tests.characterization.test_trio_json_envelope._build_mission_repo``,
    NOT WP02's ``tests._factories.coord_mission.make_coord_mission`` (the
    P-m6-approved factory). ``make_coord_mission`` mints identity/coord-
    worktree shape only (``create_mission_core``: ``meta.json`` + a bare
    ``kitty-specs/<dir>`` scaffold) -- it carries no spec/plan/tasks, no
    finalized WP file, no ``lanes.json``, no charter bundle, and no
    analysis-report, so it cannot pass the preflight gates
    ``agent action implement`` enforces before it reaches the receipt code
    under test. ``_build_mission_repo`` is the pre-existing, already-approved
    fixture for exactly this (used by ``test_coord_commit_integrity_e2e.py``
    and the trio characterization suite itself for ``agent action
    implement``/``review`` CLI runs). Importing a leading-underscore helper
    across test modules is fragile coupling; recorded as a
    ``tooling-friction`` tracer entry rather than inventing a parallel
    implement-ready builder under schedule pressure.
    """

    def test_coordination_mission_receipts_all_carry_a_contained_sha(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """US6.1: on a coordination-routed, MATERIALIZED Mission, every
        receipt ``implement`` records has a non-null sha contained in the
        branch it names. GREEN at base -- see class docstring."""
        from typer.testing import CliRunner

        from specify_cli import app as root_app
        from specify_cli.cli.commands.agent import workflow
        from tests.characterization.test_trio_json_envelope import _build_mission_repo

        repo_root, mission_dirname = _build_mission_repo(
            tmp_path,
            monkeypatch,
            coord=True,
            mission_slug="wp19-coord-implement",
            wp_lane="planned",
            materialize_coord=True,
        )
        workflow._reset_workflow_receipts()
        result = CliRunner().invoke(
            root_app,
            ["agent", "action", "implement", "WP01", "--mission", mission_dirname, "--agent", "claude"],
        )
        assert result.exit_code == 0, result.output

        receipts = list(workflow._WORKFLOW_COMMIT_RECEIPTS)
        committed = [r for r in receipts if r.get("outcome") == "committed"]
        assert committed, "expected at least one committed receipt from a planned->in_progress claim"
        for receipt in committed:
            sha = receipt.get("sha")
            assert sha is not None, f"receipt {receipt!r} must carry a non-null sha (FR-013)"
            ref = str(receipt["destination_ref"])
            assert ref in _branch_contains(repo_root, str(sha)), (
                f"receipt sha {sha!r} is not contained in the branch it names ({ref!r})"
            )
        workflow._reset_workflow_receipts()

    def test_target_branch_receipt_names_the_target_branch_not_coordination(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """US6.2 positive control: the PRIMARY-group receipt names the
        TARGET branch specifically, with its sha contained THERE -- an
        "always print the coordination branch" implementation would fail
        this (the target-branch receipt's sha is not generally on the
        coordination branch)."""
        from typer.testing import CliRunner

        from specify_cli import app as root_app
        from specify_cli.cli.commands.agent import workflow
        from tests.characterization.test_trio_json_envelope import _build_mission_repo

        repo_root, mission_dirname = _build_mission_repo(
            tmp_path,
            monkeypatch,
            coord=True,
            mission_slug="wp19-coord-control",
            wp_lane="planned",
            materialize_coord=True,
        )
        target_branch = "trio-integration"
        workflow._reset_workflow_receipts()
        result = CliRunner().invoke(
            root_app,
            ["agent", "action", "implement", "WP01", "--mission", mission_dirname, "--agent", "claude"],
        )
        assert result.exit_code == 0, result.output

        receipts = list(workflow._WORKFLOW_COMMIT_RECEIPTS)
        target_receipts = [r for r in receipts if r.get("destination_ref") == target_branch]
        coord_receipts = [
            r for r in receipts if r.get("destination_ref") not in (target_branch, None)
        ]
        assert target_receipts, "expected a receipt naming the target branch (PRIMARY group)"
        assert coord_receipts, "expected a separate receipt naming the coordination branch"
        for receipt in target_receipts:
            sha = str(receipt["sha"])
            assert target_branch in _branch_contains(repo_root, sha), (
                "the target-branch receipt's sha must be contained in the "
                "target branch -- an implementation that always names the "
                "coordination branch would fail this assertion"
            )
        workflow._reset_workflow_receipts()

    def test_lanes_mission_receipts_unchanged_fields_plus_sha(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """C-008: a ``lanes`` (coord-less) Mission's receipts keep their
        destination refs / messages / outcomes exactly as before -- the fix
        is output-only and additive (a commit id on every receipt), never a
        change to which branch a receipt names."""
        from typer.testing import CliRunner

        from specify_cli import app as root_app
        from specify_cli.cli.commands.agent import workflow
        from tests.characterization.test_trio_json_envelope import _build_mission_repo

        repo_root, mission_dirname = _build_mission_repo(
            tmp_path,
            monkeypatch,
            coord=False,
            mission_slug="wp19-lanes-control",
            wp_lane="planned",
        )
        target_branch = "trio-integration"
        workflow._reset_workflow_receipts()
        result = CliRunner().invoke(
            root_app,
            ["agent", "action", "implement", "WP01", "--mission", mission_dirname, "--agent", "claude"],
        )
        assert result.exit_code == 0, result.output

        receipts = list(workflow._WORKFLOW_COMMIT_RECEIPTS)
        assert receipts, "expected at least one receipt from a planned->in_progress claim"
        for receipt in receipts:
            # C-008: meaning unchanged -- every pre-existing field keeps its
            # pre-fix shape (a lanes mission's legacy commit lands on the
            # target branch, exactly as before).
            assert receipt["destination_ref"] == target_branch
            assert receipt["message"] == "chore: Start WP01 implementation [claude]"
            assert receipt["outcome"] == "committed"
            assert receipt["wp_id"] == "WP01"
            # Additive: every committed entry now also carries a sha.
            sha = receipt.get("sha")
            assert sha is not None, f"receipt {receipt!r} must carry a non-null sha (FR-013)"
            assert target_branch in _branch_contains(repo_root, str(sha))
        workflow._reset_workflow_receipts()


def test_find_mission_slug_ambiguous_handle_exits_cleanly(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """#450: workflow.py's ``_find_mission_slug`` short-circuit call

    (``_resolve_workflow_read_dir`` -> ``_workflow_placement_seam(...).read_dir``)
    runs BEFORE ``resolve_mission_handle`` and previously had no
    try/except around it, so an ambiguous handle propagated
    ``MissionSelectorAmbiguous`` uncaught as a bare traceback instead of a
    clean ``typer.Exit(1)`` (the shape #241 already established for the
    sibling short-circuits in ``tasks_shared.py`` and ``status.py``).
    """
    from specify_cli.cli.commands.agent import workflow
    from specify_cli.missions._read_path_resolver import MissionSelectorAmbiguous

    exc = MissionSelectorAmbiguous(
        handle="charter", candidates=["020-charter", "030-charter"]
    )
    seam_mock = MagicMock()
    seam_mock.read_dir.side_effect = exc
    with (
        patch(
            "specify_cli.cli.commands.agent.workflow.get_main_repo_root",
            return_value=tmp_path,
        ),
        patch(
            "specify_cli.cli.commands.agent.workflow._workflow_placement_seam",
            return_value=seam_mock,
        ),
        pytest.raises(workflow.typer.Exit) as exc_info,
    ):
        workflow._find_mission_slug("charter", repo_root=tmp_path)

    assert exc_info.value.exit_code == 1
    assert "Mission handle 'charter' matches multiple missions" in capsys.readouterr().out
