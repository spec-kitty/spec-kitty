"""Real-git coverage for the CLI command sites that read paths through ``kernel.git`` (WP06).

Every test runs against a temporary repository (no git mocks) with a path git
would quote in porcelain text: one containing a space, or non-ASCII characters.
Before the migration these sites compared or committed the *quoted* spelling.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import typer

from kernel.git import GitCommandError
from specify_cli.acceptance import _accept_dirty_gate, _resolve_git_context, _staged_paths
from specify_cli.agent_tasks_ports import RealGitOps
from specify_cli.cli.commands._coordination_doctor import (
    _check_tracked_worktrees_content,
    _coord_worktree_dirty_finding,
)
from specify_cli.cli.commands.accept import _commit_residual_acceptance_artifacts, _dirty_paths_with_prefix
from specify_cli.cli.commands.charter_bundle import _is_git_tracked
from specify_cli.cli.commands.implement_planning_commit import _ensure_planning_artifacts_committed_git
from specify_cli.cli.commands.implement_cores import (
    _feature_dir_status_entries,
    detect_structural_planning_changes,
)
from specify_cli.cli.commands.mission_type import _meta_has_uncommitted_changes
from specify_cli.cli.commands.review._dead_code import _discover_changed_symbols
from specify_cli.cli.commands.safe_commit_cmd import _changed_paths_under, _has_candidate_changes
from specify_cli.task_utils import TaskCliError, git_status_entries

pytestmark = [pytest.mark.git_repo]

SPACED_DIR = "a b"
SPACED_FILE = "a b/f"
NON_ASCII_FILE = "é/g"
MISSION_DIR = "kitty-specs/my mission"


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True, encoding="utf-8")
    return done.stdout


def _write(repo: Path, rel: str, text: str = "x\n") -> Path:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    _git(root, "config", "commit.gpgsign", "false")
    _write(root, "README.md")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "init")
    return root


@pytest.fixture
def not_a_repo(tmp_path: Path) -> Path:
    plain = tmp_path / "plain"
    plain.mkdir()
    return plain


# ---------------------------------------------------------------------------
# safe-commit: decides what a directory argument commits
# ---------------------------------------------------------------------------


def test_safe_commit_expansion_sees_real_paths(repo: Path) -> None:
    _write(repo, SPACED_FILE)
    _write(repo, NON_ASCII_FILE)

    assert _changed_paths_under(repo, SPACED_DIR) == [SPACED_FILE]
    assert _changed_paths_under(repo, "é") == [NON_ASCII_FILE]


def test_safe_commit_expansion_uses_rename_destination(repo: Path) -> None:
    _write(repo, SPACED_FILE, "tracked\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed")
    _git(repo, "mv", SPACED_FILE, "a b/g h")

    assert _changed_paths_under(repo, SPACED_DIR) == ["a b/g h"]


def test_safe_commit_candidate_probe_sees_quoted_paths(repo: Path) -> None:
    _write(repo, SPACED_FILE)
    assert _has_candidate_changes(repo, [repo / SPACED_FILE]) is True
    assert _has_candidate_changes(repo, [repo / "README.md"]) is False


def test_safe_commit_probes_fail_closed_outside_a_repository(not_a_repo: Path) -> None:
    with pytest.raises(RuntimeError, match="Unable to inspect directory"):
        _changed_paths_under(not_a_repo, "x")
    with pytest.raises(RuntimeError, match="Unable to inspect requested files"):
        _has_candidate_changes(not_a_repo, [not_a_repo / "x"])


# ---------------------------------------------------------------------------
# implement: dirty classification of the mission directory
# ---------------------------------------------------------------------------


def test_implement_classifies_spaced_paths(repo: Path) -> None:
    feature_dir = repo / MISSION_DIR
    _write(repo, f"{MISSION_DIR}/tasks.md")
    _write(repo, f"{MISSION_DIR}/old name.md")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed mission")
    (repo / MISSION_DIR / "tasks.md").write_text("changed\n", encoding="utf-8")
    _git(repo, "rm", "-q", f"{MISSION_DIR}/old name.md")
    _write(repo, f"{MISSION_DIR}/é new.md")

    entries = {e.path: e for e in _feature_dir_status_entries(repo, feature_dir)}

    assert set(entries) == {f"{MISSION_DIR}/tasks.md", f"{MISSION_DIR}/old name.md", f"{MISSION_DIR}/é new.md"}
    assert entries[f"{MISSION_DIR}/tasks.md"].is_structural is False
    assert entries[f"{MISSION_DIR}/old name.md"].is_structural is True
    assert [e.path for e in detect_structural_planning_changes(repo, feature_dir)] == [f"{MISSION_DIR}/old name.md"]


def test_implement_rename_is_structural_and_reports_new_path(repo: Path) -> None:
    _write(repo, f"{MISSION_DIR}/a b.md")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed")
    _git(repo, "mv", f"{MISSION_DIR}/a b.md", f"{MISSION_DIR}/c d.md")

    structural = detect_structural_planning_changes(repo, repo / MISSION_DIR)

    assert [(e.path, e.is_structural) for e in structural] == [(f"{MISSION_DIR}/c d.md", True)]


def test_implement_status_probe_fails_closed(not_a_repo: Path) -> None:
    with pytest.raises(GitCommandError):
        detect_structural_planning_changes(not_a_repo, not_a_repo / "kitty-specs" / "m")


def test_implement_claim_refuses_when_planning_status_unreadable(not_a_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The implement git executor turns a failed ``git status`` into a refusal, not a traceback."""
    mission_dir = not_a_repo / "kitty-specs" / "m"
    mission_dir.mkdir(parents=True)

    with pytest.raises(typer.Exit) as excinfo:
        _ensure_planning_artifacts_committed_git(
            repo_root=not_a_repo,
            feature_dir=mission_dir,
            mission_slug="m",
            wp_id="WP01",
            planning_branch="main",
            auto_commit=True,
        )

    assert excinfo.value.exit_code == 1
    assert isinstance(excinfo.value.__cause__, GitCommandError)
    out = " ".join(capsys.readouterr().out.split())
    assert "Could not read git status for the planning artifacts" in out
    assert "the claim is refused" in out


# ---------------------------------------------------------------------------
# acceptance: staged listing, dirty gate, residual commit
# ---------------------------------------------------------------------------


def test_acceptance_staged_listing_keeps_non_ascii_path(repo: Path) -> None:
    _write(repo, NON_ASCII_FILE)
    _git(repo, "add", NON_ASCII_FILE)

    assert [str(p) for p in _staged_paths(repo, NON_ASCII_FILE)] == [NON_ASCII_FILE]
    assert _staged_paths(repo, "README.md") == ()


def test_acceptance_staged_listing_failure_is_a_task_error(not_a_repo: Path) -> None:
    with pytest.raises(TaskCliError):
        _staged_paths(not_a_repo, "x")


def test_acceptance_dirty_gate_blocks_spaced_source_and_ignores_own_write(repo: Path) -> None:
    _write(repo, "src/my pkg/mod.py")
    _write(repo, "kitty-specs/m/status.json")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed")
    (repo / "src/my pkg/mod.py").write_text("changed\n", encoding="utf-8")
    (repo / "kitty-specs/m/status.json").write_text("changed\n", encoding="utf-8")

    dirty = _accept_dirty_gate(git_status_entries(repo), repo_root=repo, feature="m")

    assert dirty == [" M src/my pkg/mod.py"]


def test_accept_dirty_prefix_filter_handles_spaced_paths(repo: Path) -> None:
    _write(repo, f"{MISSION_DIR}/spec.md")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed")
    (repo / MISSION_DIR / "spec.md").write_text("changed\n", encoding="utf-8")
    _write(repo, f"{MISSION_DIR}/untracked.md")

    assert _dirty_paths_with_prefix(git_status_entries(repo), f"{MISSION_DIR}/") == [f"{MISSION_DIR}/spec.md"]


def test_accept_residual_commit_stages_and_commits_non_ascii_artifact(repo: Path) -> None:
    rel = "kitty-specs/my-mission/é notes.md"
    _git(repo, "checkout", "-q", "-b", "feature")  # the router refuses residual commits on protected ``main``
    _write(repo, rel)
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed")
    (repo / rel).write_text("changed\n", encoding="utf-8")

    assert _commit_residual_acceptance_artifacts(repo, "my-mission") is True
    assert _git(repo, "ls-files", "-z", "--", rel).strip("\0") == rel
    assert _git(repo, "status", "--porcelain") == ""


def test_acceptance_git_context_fails_closed_when_status_unreadable(not_a_repo: Path) -> None:
    with pytest.raises(TaskCliError, match="clean working tree"):
        _resolve_git_context(not_a_repo)


def test_acceptance_git_context_fails_closed_on_broken_index(repo: Path) -> None:
    (repo / ".git" / "index").write_bytes(b"not an index")

    with pytest.raises(TaskCliError, match="git status failed"):
        _resolve_git_context(repo)


def test_support_status_failure_is_a_task_error(not_a_repo: Path) -> None:
    with pytest.raises(TaskCliError):
        git_status_entries(not_a_repo)


# ---------------------------------------------------------------------------
# mission_type / charter_bundle / doctor / ports / dead-code
# ---------------------------------------------------------------------------


def test_mission_type_meta_dirtiness_with_spaced_directory(repo: Path) -> None:
    meta = _write(repo, f"{MISSION_DIR}/meta.json", "{}\n")
    assert _meta_has_uncommitted_changes(repo, meta) is True
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "meta")
    assert _meta_has_uncommitted_changes(repo, meta) is False


def test_charter_bundle_tracking_with_quoted_path(repo: Path) -> None:
    _write(repo, ".kittify/charter/é doc.md")
    assert _is_git_tracked(repo, ".kittify/charter/é doc.md") is False
    _git(repo, "add", ".")
    assert _is_git_tracked(repo, ".kittify/charter/é doc.md") is True


def test_charter_bundle_tracking_degrades_to_untracked_outside_a_repository(not_a_repo: Path) -> None:
    assert _is_git_tracked(not_a_repo, "x") is False


def test_doctor_flags_tracked_worktree_content_with_spaced_path(repo: Path) -> None:
    _write(repo, ".worktrees/a b/f")
    _git(repo, "add", "-f", ".worktrees")

    [finding] = _check_tracked_worktrees_content(repo)

    assert finding.error_code == "TRACKED_WORKTREES_CONTENT"
    assert finding.extra["tracked"] == [".worktrees/a b/f"]


def test_doctor_reports_nothing_outside_a_repository(not_a_repo: Path) -> None:
    assert _check_tracked_worktrees_content(not_a_repo) == []
    assert _coord_worktree_dirty_finding(not_a_repo) is None


def test_doctor_coord_worktree_dirty_with_spaced_path(repo: Path) -> None:
    assert _coord_worktree_dirty_finding(repo) is None
    _write(repo, SPACED_FILE)
    finding = _coord_worktree_dirty_finding(repo)
    assert finding is not None
    assert finding.error_code == "COORDINATION_WORKTREE_DIRTY"


def test_real_git_ops_dirty_probe(repo: Path, not_a_repo: Path) -> None:
    ops = RealGitOps(repo)
    assert ops.is_dirty(repo) is False
    _write(repo, SPACED_FILE)
    assert ops.is_dirty(repo) is True
    with pytest.raises(GitCommandError):
        ops.is_dirty(not_a_repo)


def test_dead_code_discovery_lists_real_changed_paths(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD").strip()
    _write(repo, "src/my pkg/mod.py", "def public_name():\n    return 1\n")
    _write(repo, "docs/é guide.md")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "change")

    discovery = _discover_changed_symbols(repo, base)

    assert discovery.outcome == "scan"
    assert discovery.changed_paths == ("src/my pkg/mod.py",)
    assert discovery.unsupported_extensions == (".md",)
    assert discovery.symbols == (("public_name", "src/my pkg/mod.py"),)


@pytest.mark.parametrize("rel", ['src/q"x/m"od.py', "src/é ü/模块.py", "src/back\\slash/m.py"])
def test_dead_code_attributes_symbols_for_quoted_and_non_ascii_paths(repo: Path, rel: str) -> None:
    base = _git(repo, "rev-parse", "HEAD").strip()
    _write(repo, rel, "def public_name():\n    return 1\n\n\nclass PublicThing:\n    pass\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "change")

    discovery = _discover_changed_symbols(repo, base)

    assert discovery.outcome == "scan"
    assert discovery.symbols == (("public_name", rel), ("PublicThing", rel))


def test_dead_code_rename_reports_only_genuinely_added_symbols(repo: Path) -> None:
    _write(repo, "src/old name.py", "def kept():\n    return 1\n" * 1 + "\n".join(f"# pad {i}" for i in range(20)) + "\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed")
    base = _git(repo, "rev-parse", "HEAD").strip()
    _git(repo, "mv", "src/old name.py", "src/new name.py")
    with (repo / "src/new name.py").open("a", encoding="utf-8") as handle:
        handle.write("def added():\n    return 2\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "rename")

    discovery = _discover_changed_symbols(repo, base)

    assert discovery.symbols == (("added", "src/new name.py"),)


def test_dead_code_discovery_undeterminable_for_unknown_baseline(repo: Path) -> None:
    discovery = _discover_changed_symbols(repo, "0" * 40)

    assert discovery.outcome == "undeterminable"
    assert discovery.error == "git diff failed"
