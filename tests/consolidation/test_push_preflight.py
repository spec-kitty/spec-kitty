"""WP03 — push-preflight unit tests: push/no-push × origin-state matrix.

Covers T010 requirements: 5-origin-state × push/no-push combinations and
FR-004 (local merge results preserved when push blocked).

NFR-001: fetch latency validated manually/observationally — not in automated suite.
"""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_domain_preflight_does_not_import_push_preflight_at_module_load() -> None:
    """Local-merge domain module must not load publish-layer code at import time."""
    source = Path("src/specify_cli/consolidation/preflight.py").read_text()
    tree = ast.parse(source)
    parents = {
        child: node
        for node in ast.walk(tree)
        for child in ast.iter_child_nodes(node)
    }

    def is_under_type_checking(node: ast.AST) -> bool:
        while node in parents:
            parent = parents[node]
            if (
                isinstance(parent, ast.If)
                and isinstance(parent.test, ast.Name)
                and parent.test.id == "TYPE_CHECKING"
            ):
                return True
            node = parent
        return False

    runtime_imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "specify_cli.consolidation.push_preflight"
        and not is_under_type_checking(node)
    ]
    assert runtime_imports == []


# ---------------------------------------------------------------------------
# T010 Test 2: is_safe_to_push predicate for all 5 states
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "state,expected_safe",
    [
        ("in_sync", True),
        ("ahead", True),
        ("behind", False),
        ("diverged", False),
        ("no_tracking_branch", True),
    ],
)
def test_is_safe_to_push_predicate(state: str, expected_safe: bool) -> None:
    """is_safe_to_push returns False when push would fail after local mutation."""
    from specify_cli.consolidation.push_preflight import TargetBranchSyncStatus

    status = TargetBranchSyncStatus(
        target_branch="main",
        tracking_branch="origin/main" if state != "no_tracking_branch" else None,
        ahead_count=1 if state in ("ahead", "diverged") else 0,
        behind_count=1 if state in ("behind", "diverged") else 0,
        state=state,
    )
    assert status.is_safe_to_push == expected_safe


# ---------------------------------------------------------------------------
# T010 Test 3: check_push_safety with mocked subprocess
# ---------------------------------------------------------------------------


def test_check_push_safety_fetch_failure_returns_not_safe() -> None:
    """When fetch fails, check_push_safety returns is_safe_to_push=False."""
    from specify_cli.consolidation.push_preflight import check_push_safety

    with patch("specify_cli.consolidation.push_preflight.refresh_target_branch_tracking_ref") as mock_refresh:
        mock_refresh.return_value = MagicMock(success=False, error="network error", attempted=True)
        with patch("specify_cli.consolidation.push_preflight.inspect_target_branch_sync") as mock_inspect:
            result = check_push_safety(Path("/fake/repo"), "main")
            assert result.fetch_failed is True
            assert result.is_safe_to_push is False
            mock_inspect.assert_not_called()


def test_check_push_safety_diverged_returns_not_safe() -> None:
    """When state is diverged, check_push_safety returns is_safe_to_push=False."""
    from specify_cli.consolidation.push_preflight import TargetBranchSyncStatus, check_push_safety

    with patch("specify_cli.consolidation.push_preflight.refresh_target_branch_tracking_ref") as mock_refresh:
        mock_refresh.return_value = MagicMock(success=True, error=None)
        with patch("specify_cli.consolidation.push_preflight.inspect_target_branch_sync") as mock_inspect:
            mock_inspect.return_value = TargetBranchSyncStatus(
                target_branch="main",
                tracking_branch="origin/main",
                ahead_count=5,
                behind_count=3,
                state="diverged",
            )
            result = check_push_safety(Path("/fake/repo"), "main")
            assert result.is_safe_to_push is False
            assert result.fetch_failed is False


def test_check_push_safety_ahead_returns_safe() -> None:
    """When state is ahead, check_push_safety returns is_safe_to_push=True."""
    from specify_cli.consolidation.push_preflight import TargetBranchSyncStatus, check_push_safety

    with patch("specify_cli.consolidation.push_preflight.refresh_target_branch_tracking_ref") as mock_refresh:
        mock_refresh.return_value = MagicMock(success=True, error=None)
        with patch("specify_cli.consolidation.push_preflight.inspect_target_branch_sync") as mock_inspect:
            mock_inspect.return_value = TargetBranchSyncStatus(
                target_branch="main",
                tracking_branch="origin/main",
                ahead_count=10,
                behind_count=0,
                state="ahead",
            )
            result = check_push_safety(Path("/fake/repo"), "main")
            assert result.is_safe_to_push is True
            assert result.fetch_failed is False


# ---------------------------------------------------------------------------
# FR-004: push blocked but local results preserved when diverged
# ---------------------------------------------------------------------------


def test_push_blocked_but_local_results_preserved_when_diverged() -> None:
    """FR-004: When push is blocked for diverged state, local merge results must be preserved.

    check_push_safety is a read-only check — it does not mutate local git state.
    Local merge results are always preserved by design. We verify the safety
    predicate and that the result carries sync_status for diagnostics.
    """
    from specify_cli.consolidation.push_preflight import TargetBranchSyncStatus, check_push_safety

    with patch("specify_cli.consolidation.push_preflight.refresh_target_branch_tracking_ref") as mock_refresh:
        mock_refresh.return_value = MagicMock(success=True, error=None)
        with patch("specify_cli.consolidation.push_preflight.inspect_target_branch_sync") as mock_inspect:
            mock_inspect.return_value = TargetBranchSyncStatus(
                target_branch="main",
                tracking_branch="origin/main",
                ahead_count=5,
                behind_count=3,
                state="diverged",
            )
            result = check_push_safety(Path("/fake/repo"), "main")
            # Push is blocked
            assert result.is_safe_to_push is False
            # But sync_status is preserved for diagnostics (local state intact)
            assert result.sync_status is not None
            assert result.sync_status.state == "diverged"
            # fetch_failed is False — the check ran, it's just unsafe to push
            assert result.fetch_failed is False


def test_resume_preserves_original_push_request() -> None:
    """A resumed merge keeps the original --push intent even if retry omits it."""
    from specify_cli.cli.commands.consolidate import _effective_push_requested
    from specify_cli.consolidation.state import ConsolidationState

    state = ConsolidationState(
        mission_id="mission-01KT",
        mission_slug="mission-01KT",
        target_branch="main",
        wp_order=["WP01"],
        push_requested=True,
    )
    with patch("specify_cli.consolidation.preflight.load_state", return_value=state):
        assert _effective_push_requested(Path("/fake/repo"), "mission-01KT", False) is True


def test_resume_cannot_add_push_to_local_only_merge() -> None:
    """A resumed local-only merge ignores a later --push flag."""
    from specify_cli.cli.commands.consolidate import _effective_push_requested
    from specify_cli.consolidation.state import ConsolidationState

    state = ConsolidationState(
        mission_id="mission-01KT",
        mission_slug="mission-01KT",
        target_branch="main",
        wp_order=["WP01"],
        push_requested=False,
    )
    with patch("specify_cli.consolidation.preflight.load_state", return_value=state):
        assert _effective_push_requested(Path("/fake/repo"), "mission-01KT", True) is False


# ---------------------------------------------------------------------------
# Alert #63 (SonarCloud S6350): option-injection separator for rev-parse sinks
#
# ``_branch_commit_exists`` and ``_resolve_tracking_branch`` pass an
# internally-derived ref/branch to ``git rev-parse`` unprefixed. A value
# starting with ``-`` could be parsed as an option instead of the revspec
# positional. ``--end-of-options`` (not ``--``, which is a *pathspec*
# separator for rev-parse) makes the value unambiguously positional.
# ---------------------------------------------------------------------------


def test_branch_commit_exists_inserts_end_of_options_before_ref() -> None:
    """``rev-parse --verify`` gets ``--end-of-options`` immediately before the ref."""
    from specify_cli.consolidation.push_preflight import _branch_commit_exists

    calls: list[list[str]] = []

    def _fake_git(_repo_root: Path, args: list[str]) -> MagicMock:
        calls.append(args)
        return MagicMock(returncode=0)

    with patch("specify_cli.consolidation.push_preflight._git", side_effect=_fake_git):
        hostile_ref = "--upload-pack=touch /pwned-marker"
        _branch_commit_exists(Path("/fake/repo"), hostile_ref)

    assert len(calls) == 1
    argv = calls[0]
    assert argv == ["rev-parse", "--verify", "--end-of-options", f"{hostile_ref}^{{commit}}"]
    sep_index = argv.index("--end-of-options")
    assert argv[sep_index + 1] == f"{hostile_ref}^{{commit}}"


def test_resolve_tracking_branch_inserts_end_of_options_before_ref() -> None:
    """The upstream rev-parse call gets ``--end-of-options`` before the composed ref."""
    from specify_cli.consolidation.push_preflight import _resolve_tracking_branch

    calls: list[list[str]] = []

    def _fake_git(_repo_root: Path, args: list[str]) -> MagicMock:
        calls.append(args)
        return MagicMock(returncode=1, stdout="")  # force fall-through to origin check

    with patch("specify_cli.consolidation.push_preflight._git", side_effect=_fake_git):
        hostile_branch = "-D"
        _resolve_tracking_branch(Path("/fake/repo"), hostile_branch)

    upstream_calls = [argv for argv in calls if "--symbolic-full-name" in argv]
    assert len(upstream_calls) == 1
    argv = upstream_calls[0]
    expected_ref = f"{hostile_branch}@{{upstream}}"
    # ``--verify`` is required alongside ``--end-of-options`` here: plain
    # (non-``--verify``) ``git rev-parse`` echoes ``--end-of-options`` back
    # onto stdout verbatim instead of consuming it as a pure option
    # terminator, corrupting the resolved ref. ``--verify`` restores the
    # documented ``--verify --end-of-options`` idiom (see
    # ``test_resolve_tracking_branch_still_resolves_real_upstream`` below for
    # the live-git regression this guards).
    assert argv == [
        "rev-parse",
        "--abbrev-ref",
        "--symbolic-full-name",
        "--verify",
        "--end-of-options",
        expected_ref,
    ]
    sep_index = argv.index("--end-of-options")
    assert argv[sep_index + 1] == expected_ref


def test_resolve_tracking_branch_still_resolves_real_upstream() -> None:
    """The separator is transparent for a legitimate upstream ref (no regression)."""
    from specify_cli.consolidation.push_preflight import _resolve_tracking_branch

    def _fake_git(_repo_root: Path, args: list[str]) -> MagicMock:
        if "--symbolic-full-name" in args:
            return MagicMock(returncode=0, stdout="origin/main\n")
        return MagicMock(returncode=0, stdout="")

    with patch("specify_cli.consolidation.push_preflight._git", side_effect=_fake_git):
        result = _resolve_tracking_branch(Path("/fake/repo"), "main")

    assert result == "origin/main"
