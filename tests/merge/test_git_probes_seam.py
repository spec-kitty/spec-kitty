"""Seam test for ``specify_cli.merge.git_probes`` (mission #2057, WP03).

Covers the relocated low-level git primitives (porcelain classification,
linear-history detection, worktree-path predicate, branch/tree probes,
post-merge refresh). The re-export-identity and one-way-import guards for this
seam live in the consolidated ``tests/merge/test_merge_compat_surface.py``
(WP04, dev-assist-retire-path-hardening-01KXAVR0 / #2565) — this file keeps
only the functional coverage.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.merge import git_probes

# The subprocess-backed probes below spawn real ``git`` on a tmp repo, so this
# file is an integration test that requires a git repo (Rule 1) and must NOT
# carry ``fast`` (Rule 2 — subprocess work would poison the inner-loop profile).
pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


# --- path_is_under_worktrees -----------------------------------------------


def test_path_is_under_worktrees_true_and_false() -> None:
    assert git_probes.path_is_under_worktrees(Path(".worktrees/mission-lane-a/x"))
    assert git_probes.path_is_under_worktrees(Path("repo/.worktrees/m/file.py"))
    assert not git_probes.path_is_under_worktrees(Path("src/specify_cli/x.py"))


# --- _is_linear_history_rejection ------------------------------------------


@pytest.mark.parametrize(
    "stderr",
    [
        "remote: error: GH006 Protected branch update failed",
        "Updates were rejected because the remote contains work (non-fast-forward)",
        "branch requires linear history",
        "merge commits are not allowed",
        "fast-forward only",
    ],
)
def test_linear_history_rejection_detects_locked_tokens(stderr: str) -> None:
    assert git_probes._is_linear_history_rejection(stderr)


def test_linear_history_rejection_is_fail_open() -> None:
    assert not git_probes._is_linear_history_rejection("some unrelated push error")
    # Case-insensitive match.
    assert git_probes._is_linear_history_rejection("LINEAR HISTORY required")


# --- _classify_porcelain_lines ---------------------------------------------


def test_classify_porcelain_lines_buckets_correctly() -> None:
    lines = [
        " M src/changed.py",  # tracked modification -> offending
        "?? untracked.txt",  # untracked -> skipped, counted
        "M  kitty-specs/x.md",  # staged, but expected -> dropped
        "",  # blank -> ignored
        "bad",  # malformed shape -> ignored
        " D removed.py",  # deletion -> offending
    ]
    offending, skipped = git_probes._classify_porcelain_lines(lines, expected_paths={"kitty-specs/x.md"})
    assert offending == [" M src/changed.py", " D removed.py"]
    assert skipped == 1


def test_classify_porcelain_lines_residue_predicate_drops_residue() -> None:
    lines = [" M kitty-specs/m/status.json", " M src/real.py"]
    offending, skipped = git_probes._classify_porcelain_lines(
        lines,
        expected_paths=set(),
        residue_predicate=lambda p: p.startswith("kitty-specs/"),
    )
    assert offending == [" M src/real.py"]
    assert skipped == 0


# --- _emit_remediation_hint ------------------------------------------------


def test_emit_remediation_hint_prints_squash_guidance() -> None:
    captured: list[str] = []

    class _FakeConsole:
        def print(self, msg: str) -> None:
            captured.append(msg)

    git_probes._emit_remediation_hint(_FakeConsole())
    assert any("--strategy squash" in line for line in captured)
    assert any("linear-history" in line for line in captured)


# --- run_command-backed probes (mocked) ------------------------------------


def test_lane_already_integrated_reads_rev_list_count() -> None:
    with patch.object(git_probes, "run_command", return_value=(0, "0", "")):
        assert git_probes._lane_already_integrated(Path("/r"), "lane", "mission")
    with patch.object(git_probes, "run_command", return_value=(0, "3", "")):
        assert not git_probes._lane_already_integrated(Path("/r"), "lane", "mission")
    # git error -> conservative False (run the merge).
    with patch.object(git_probes, "run_command", return_value=(128, "", "err")):
        assert not git_probes._lane_already_integrated(Path("/r"), "lane", "mission")


def test_branch_trees_equal_uses_diff_quiet() -> None:
    with patch.object(git_probes, "run_command", return_value=(0, "", "")):
        assert git_probes._branch_trees_equal(Path("/r"), "a", "b")
    with patch.object(git_probes, "run_command", return_value=(1, "", "")):
        assert not git_probes._branch_trees_equal(Path("/r"), "a", "b")


def test_has_branch_ref_true_false() -> None:
    with patch.object(git_probes, "run_command", return_value=(0, "sha", "")):
        assert git_probes._has_branch_ref(Path("/r"), "main")
    with patch.object(git_probes, "run_command", return_value=(128, "", "bad")):
        assert not git_probes._has_branch_ref(Path("/r"), "nope")


def test_paths_have_status_changes_detects_dirty_and_clean(tmp_path: Path) -> None:
    with patch.object(git_probes, "run_command", return_value=(0, " M a.py\n", "")):
        assert git_probes._paths_have_status_changes(tmp_path, [tmp_path / "a.py"])
    with patch.object(git_probes, "run_command", return_value=(0, "", "")):
        assert not git_probes._paths_have_status_changes(tmp_path, [tmp_path / "a.py"])
    # git failure -> conservative True.
    with patch.object(git_probes, "run_command", return_value=(1, "", "err")):
        assert git_probes._paths_have_status_changes(tmp_path, [tmp_path / "a.py"])


def test_refresh_primary_checkout_warns_on_reset_failure() -> None:
    printed: list[str] = []
    with (
        patch.object(git_probes, "run_command", return_value=(1, "", "reset boom")),
        patch("specify_cli.merge.git_probes.console.print", side_effect=lambda m: printed.append(m)),
    ):
        git_probes._refresh_primary_checkout_after_merge(Path("/r"))
    assert any("refresh failed" in line for line in printed)


def test_refresh_primary_checkout_reset_then_refresh() -> None:
    calls: list[list[str]] = []

    def _fake(cmd: list[str], **_kw: object) -> tuple[int, str, str]:
        calls.append(cmd)
        return (0, "", "")

    with patch.object(git_probes, "run_command", side_effect=_fake):
        git_probes._refresh_primary_checkout_after_merge(Path("/r"))
    assert calls[0][:3] == ["git", "reset", "--hard"]
    assert calls[1][:2] == ["git", "update-index"]


# --- subprocess-backed probes (real git on a tmp repo) ----------------------


def _init_repo(path: Path) -> None:
    import subprocess

    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)


def test_is_git_repo_true_inside_false_outside(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    assert git_probes._is_git_repo(repo)
    outside = tmp_path / "plain"
    outside.mkdir()
    assert not git_probes._is_git_repo(outside)


def test_raw_porcelain_status_preserves_leading_column(tmp_path: Path) -> None:
    import subprocess

    repo = tmp_path / "repo"
    _init_repo(repo)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / "a.txt").write_text("one\n", encoding="utf-8")
    subprocess.run(["git", "add", "a.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True)
    # Modify the tracked file without staging -> porcelain " M a.txt".
    (repo / "a.txt").write_text("two\n", encoding="utf-8")
    rc, out = git_probes._raw_porcelain_status(repo)
    assert rc == 0
    assert out.startswith(" M a.txt"), repr(out)


# --- squash-content probes (T015 / #5013) — blob_id_at, changed_paths_in_range,
#     first_parent_commits_in_range raise-on-error ------------------------------


def _git_seam(repo: Path, *args: str) -> str:
    import subprocess

    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _init_committed_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    import subprocess

    subprocess.run(["git", "init", "-qb", "main", str(repo)], check=True)
    _git_seam(repo, "config", "user.email", "t@t.co")
    _git_seam(repo, "config", "user.name", "Probe Test")
    _git_seam(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _git_seam(repo, "add", ".")
    _git_seam(repo, "commit", "-qm", "init")
    return repo


def _commit_file(repo: Path, rel: str, body: str, message: str) -> str:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    _git_seam(repo, "add", rel)
    _git_seam(repo, "commit", "-qm", message)
    return _git_seam(repo, "rev-parse", "HEAD")


def test_blob_id_at_returns_blob_for_existing_path(tmp_path: Path) -> None:
    repo = _init_committed_repo(tmp_path)
    _commit_file(repo, "src/x.py", "content\n", "add x")
    expected = _git_seam(repo, "rev-parse", "HEAD:src/x.py")
    assert git_probes.blob_id_at(repo, "HEAD", "src/x.py") == expected
    assert git_probes.blob_id_at(repo, "HEAD", "src/x.py") != ""


def test_blob_id_at_raises_on_missing_path(tmp_path: Path) -> None:
    repo = _init_committed_repo(tmp_path)
    with pytest.raises(git_probes.GitProbeError):
        git_probes.blob_id_at(repo, "HEAD", "src/absent.py")


def test_blob_id_at_raises_on_bad_ref(tmp_path: Path) -> None:
    repo = _init_committed_repo(tmp_path)
    _commit_file(repo, "src/x.py", "content\n", "add x")
    with pytest.raises(git_probes.GitProbeError):
        git_probes.blob_id_at(repo, "no-such-ref-xyz", "src/x.py")


def test_changed_paths_in_range_reports_status_and_path(tmp_path: Path) -> None:
    repo = _init_committed_repo(tmp_path)
    _commit_file(repo, "keep.py", "v1\n", "add keep")
    _commit_file(repo, "gone.py", "bye\n", "add gone")
    base = _git_seam(repo, "rev-parse", "HEAD")
    # Add, modify, delete across base..tip.
    (repo / "added.py").write_text("new\n", encoding="utf-8")
    (repo / "keep.py").write_text("v2\n", encoding="utf-8")
    (repo / "gone.py").unlink()
    _git_seam(repo, "add", "-A")
    _git_seam(repo, "commit", "-qm", "mix")
    tip = _git_seam(repo, "rev-parse", "HEAD")
    changes = {path: status for status, path in git_probes.changed_paths_in_range(repo, base, tip)}
    assert changes["added.py"] == "A"
    assert changes["keep.py"] == "M"
    assert changes["gone.py"] == "D"


def test_changed_paths_in_range_no_renames_shows_delete_add(tmp_path: Path) -> None:
    repo = _init_committed_repo(tmp_path)
    _commit_file(repo, "old.py", "same-content-so-rename-would-detect\n", "add old")
    base = _git_seam(repo, "rev-parse", "HEAD")
    _git_seam(repo, "mv", "old.py", "new.py")
    _git_seam(repo, "commit", "-qm", "rename old->new")
    tip = _git_seam(repo, "rev-parse", "HEAD")
    changes = {path: status for status, path in git_probes.changed_paths_in_range(repo, base, tip)}
    # --no-renames: a rename surfaces as delete + add, never an R status.
    assert changes.get("old.py") == "D"
    assert changes.get("new.py") == "A"
    assert not any(status.startswith("R") for status in changes.values())


def test_changed_paths_in_range_raises_on_git_error(tmp_path: Path) -> None:
    repo = _init_committed_repo(tmp_path)
    with pytest.raises(git_probes.GitProbeError):
        git_probes.changed_paths_in_range(repo, "no-such-ref-xyz", "HEAD")


def test_first_parent_commits_in_range_raises_on_git_error(tmp_path: Path) -> None:
    """F7 regression: an unresolvable ref is a git ERROR, not an empty range."""
    repo = _init_committed_repo(tmp_path)
    with pytest.raises(git_probes.GitProbeError):
        git_probes.first_parent_commits_in_range(repo, "no-such-ref-xyz", "HEAD")


def test_first_parent_commits_in_range_excludes_second_parent(tmp_path: Path) -> None:
    """Positive arm: a merged-in second parent is NOT on the first-parent spine."""
    repo = _init_committed_repo(tmp_path)
    base = _git_seam(repo, "rev-parse", "HEAD")
    # side branch with its own commit
    _git_seam(repo, "checkout", "-qb", "side")
    side_sha = _commit_file(repo, "side.py", "side\n", "side work")
    _git_seam(repo, "checkout", "-q", "main")
    _commit_file(repo, "main.py", "main\n", "main work")
    _git_seam(repo, "merge", "-q", "--no-edit", "--no-ff", "side")
    first_parent = git_probes.first_parent_commits_in_range(repo, base, "main")
    assert side_sha not in first_parent
