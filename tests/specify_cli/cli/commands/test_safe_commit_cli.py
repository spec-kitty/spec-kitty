"""Integration tests for the post-#1348 ``spec-kitty safe-commit`` CLI.

These tests exercise the CLI modes specified by WP02 / T009 (and WP04 / T016 —
the ``SPEC_KITTY_INFER_DESTINATION_REF`` env-var inference path is retired):

1. ``--to-branch <ref>`` happy path — succeeds when HEAD matches.
2. Missing ``--to-branch`` — infers HEAD for compatibility and warns.
3. ``--to-branch`` pointing at a non-HEAD branch — exits non-zero with the
   ``SafeCommitHeadMismatch`` error surface (stable error code from WP01).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli import app as cli_app
from specify_cli.cli.commands._commit_message import join_message_paragraphs


pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

# Newer click/typer ships separate stdout/stderr on Result by default; older
# versions accept ``mix_stderr=False``. We construct conservatively for both.
try:
    runner = CliRunner(mix_stderr=False)  # type: ignore[call-arg]
except TypeError:
    runner = CliRunner()


def _init_lane_repo(repo: Path, *, branch: str = "kitty/mission-test-01ABCDEF") -> None:
    """Initialize a tmp git repo checked out to a non-protected lane branch."""
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", f"--initial-branch={branch}"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True)
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.json").write_text("{}\n", encoding="utf-8")
    (repo / "README.md").write_text("# Test Repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md", ".kittify/config.json"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial commit"], cwd=repo, check=True, capture_output=True)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


# ---------------------------------------------------------------------------
# T009 — CLI mode tests
# ---------------------------------------------------------------------------


def test_cli_with_to_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`--to-branch <ref>` succeeds when HEAD matches the declared branch."""
    monkeypatch.delenv("SPEC_KITTY_TEST_MODE", raising=False)
    _init_lane_repo(tmp_path, branch="kitty/mission-test-01ABCDEF")

    target = tmp_path / "alpha.txt"
    target.write_text("alpha v1\n", encoding="utf-8")

    head_before = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()

    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli_app,
        [
            "safe-commit",
            "--to-branch",
            "kitty/mission-test-01ABCDEF",
            "--message",
            "T009: add alpha",
            "--json",
            "alpha.txt",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["committed"] is True

    head_after = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()
    assert head_after != head_before, "expected a new commit on HEAD"
    last_message = _git(tmp_path, "log", "-1", "--format=%s").stdout.strip()
    assert last_message == "T009: add alpha"


def test_cli_without_to_branch_infers_head_with_warning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No `--to-branch` → infer HEAD for compatibility and warn on stderr."""
    monkeypatch.delenv("SPEC_KITTY_TEST_MODE", raising=False)
    _init_lane_repo(tmp_path, branch="kitty/mission-test-01ABCDEF")

    target = tmp_path / "beta.txt"
    target.write_text("beta v1\n", encoding="utf-8")

    head_before = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()

    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli_app,
        ["safe-commit", "--message", "T009: no flag", "--json", "beta.txt"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["committed"] is True
    stderr_text = result.stderr or ""
    assert "warning:" in stderr_text
    assert "--to-branch will be required in v3.3" in stderr_text

    head_after = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()
    assert head_after != head_before, "expected a new commit through HEAD inference"


def test_cli_head_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`--to-branch` for a branch that isn't HEAD → exits non-zero with HEAD-mismatch surface."""
    monkeypatch.delenv("SPEC_KITTY_TEST_MODE", raising=False)
    _init_lane_repo(tmp_path, branch="kitty/mission-test-01ABCDEF")

    # Create a second branch so destination_ref is a real ref, not a missing one.
    _git(tmp_path, "branch", "kitty/mission-other-02ZZZZZZ")

    target = tmp_path / "delta.txt"
    target.write_text("delta v1\n", encoding="utf-8")

    head_before = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()

    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli_app,
        [
            "safe-commit",
            "--to-branch",
            "kitty/mission-other-02ZZZZZZ",
            "--message",
            "T009: head mismatch",
            "--json",
            "delta.txt",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["success"] is False

    # The error must surface the destination-ref-aware HEAD assertion (NFR-007:
    # stable error code from SafeCommitHeadMismatch in WP01).
    err_msg = payload["error"]
    head_mismatch_signals = (
        "SAFE_COMMIT_HEAD_MISMATCH",
        "head_mismatch",
        "HEAD does not match",
        "destination_ref",
        "HEAD",
    )
    assert any(signal in err_msg for signal in head_mismatch_signals), f"expected HEAD-mismatch signal in error message, got: {err_msg!r}"

    head_after = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()
    assert head_after == head_before, "no commit must be created on HEAD-mismatch"


# ---------------------------------------------------------------------------
# T017 — WP04 ergonomics regressions (#1820 / #1330 / F-002)
# ---------------------------------------------------------------------------


def test_cli_dir_arg_mixed_modified_and_untracked_commits_all_with_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """(a) A directory argument with mixed modified + untracked contents commits
    every contained file and prints the explicit expansion report (no
    'unexpected paths' backstop refusal — F-002)."""
    monkeypatch.delenv("SPEC_KITTY_TEST_MODE", raising=False)
    branch = "kitty/mission-test-01ABCDEF"
    _init_lane_repo(tmp_path, branch=branch)

    # A tracked file we will MODIFY, plus a NEW untracked file, both under dir/.
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    tracked = pkg / "tracked.txt"
    tracked.write_text("v1\n", encoding="utf-8")
    _git(tmp_path, "add", "pkg/tracked.txt")
    _git(tmp_path, "commit", "-q", "-m", "seed tracked file")

    tracked.write_text("v2\n", encoding="utf-8")  # modified
    (pkg / "untracked.txt").write_text("new\n", encoding="utf-8")  # untracked

    head_before = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()

    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli_app,
        ["safe-commit", "--to-branch", branch, "--message", "T017: dir expand", "--json", "pkg"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, (result.stdout or "") + (result.stderr or "")
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["committed"] is True

    # The expansion report is present and names both contained files.
    expansion = payload.get("expansion")
    assert expansion is not None, "expected an expansion report for the dir arg"
    expansion_text = "\n".join(expansion)
    assert "Expanding pkg/ → 2 files" in expansion_text
    assert "pkg/tracked.txt" in expansion_text
    assert "pkg/untracked.txt" in expansion_text

    head_after = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()
    assert head_after != head_before, "expected a new commit for the expanded dir"

    # Both files actually landed in the commit.
    committed_files = _git(tmp_path, "show", "--name-only", "--format=", "HEAD").stdout
    assert "pkg/tracked.txt" in committed_files
    assert "pkg/untracked.txt" in committed_files


def test_cli_to_branch_honored_from_non_target_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """(b) `--to-branch <branch>` is honored: the explicit value is the single
    destination authority. Invoked from a subdirectory CWD (not the repo root)."""
    monkeypatch.delenv("SPEC_KITTY_TEST_MODE", raising=False)
    branch = "kitty/mission-test-01ABCDEF"
    _init_lane_repo(tmp_path, branch=branch)

    sub = tmp_path / "nested"
    sub.mkdir()
    (sub / "epsilon.txt").write_text("epsilon v1\n", encoding="utf-8")

    head_before = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()

    monkeypatch.chdir(sub)  # non-target CWD inside the worktree
    # Paths resolve against the worktree root (repo-relative), so pass the
    # repo-relative path while CWD is the nested subdirectory.
    result = runner.invoke(
        cli_app,
        ["safe-commit", "--to-branch", branch, "--message", "T017: to-branch honored", "--json", "nested/epsilon.txt"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, (result.stdout or "") + (result.stderr or "")
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["committed"] is True
    # No deprecation warning when --to-branch is explicit.
    assert "warning:" not in (result.stderr or "")

    head_after = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()
    assert head_after != head_before
    # The commit landed on the requested branch.
    assert _git(tmp_path, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == branch


def test_cli_retired_env_var_has_no_effect(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """(c) The retired `SPEC_KITTY_INFER_DESTINATION_REF` env var has NO effect:
    setting it does not suppress the no-flag deprecation warning (T016)."""
    monkeypatch.setenv("SPEC_KITTY_INFER_DESTINATION_REF", "1")
    monkeypatch.delenv("SPEC_KITTY_TEST_MODE", raising=False)
    _init_lane_repo(tmp_path, branch="kitty/mission-test-01ABCDEF")

    (tmp_path / "zeta.txt").write_text("zeta v1\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        cli_app,
        ["safe-commit", "--message", "T017: retired env var", "--json", "zeta.txt"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, (result.stdout or "") + (result.stderr or "")
    payload = json.loads(result.stdout)
    assert payload["committed"] is True
    # The env var no longer suppresses anything — the deprecation warning fires.
    assert "warning:" in (result.stderr or "")
    assert "--to-branch will be required in v3.3" in (result.stderr or "")


def test_cli_genuinely_different_file_never_reports_no_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """(d) A file genuinely differing from HEAD is never reported 'No requested
    changes' — the F-002 misfire repro (passed via a dir arg)."""
    monkeypatch.delenv("SPEC_KITTY_TEST_MODE", raising=False)
    branch = "kitty/mission-test-01ABCDEF"
    _init_lane_repo(tmp_path, branch=branch)

    docs = tmp_path / "docs"
    docs.mkdir()
    spec = docs / "spec.md"
    spec.write_text("# Spec v1\n", encoding="utf-8")
    _git(tmp_path, "add", "docs/spec.md")
    _git(tmp_path, "commit", "-q", "-m", "seed spec")

    spec.write_text("# Spec v2 (genuinely changed)\n", encoding="utf-8")

    head_before = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()

    monkeypatch.chdir(tmp_path)
    # Plain (non --json) so we can assert the human-facing message.
    result = runner.invoke(
        cli_app,
        ["safe-commit", "--to-branch", branch, "--message", "T017: F-002 misfire", "docs"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, (result.stdout or "") + (result.stderr or "")
    assert "No requested changes" not in result.stdout
    assert "Requested files committed" in result.stdout

    head_after = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()
    assert head_after != head_before, "the genuinely-changed file must be committed"


# ---------------------------------------------------------------------------
# #5647 -- repeated ``-m`` builds a multi-paragraph message, as ``git commit`` does
# ---------------------------------------------------------------------------


def test_cli_keeps_every_repeated_message(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#5647: ``-m subject -m body -m trailer`` kept only the trailer and exited 0."""
    branch = "kitty/mission-test-01ABCDEF"
    trailer = "Co-Authored-By: Name <name@example.invalid>"
    _init_lane_repo(tmp_path, branch=branch)
    (tmp_path / "x.py").write_text("X = 1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        cli_app,
        ["safe-commit", "x.py", "-m", "test(x): subject", "-m", "Body paragraph.", "-m", trailer, "--to-branch", branch],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    assert _git(tmp_path, "log", "-1", "--format=%B").stdout.strip() == f"test(x): subject\n\nBody paragraph.\n\n{trailer}"


def test_cli_refuses_an_empty_message(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    branch = "kitty/mission-test-01ABCDEF"
    _init_lane_repo(tmp_path, branch=branch)
    (tmp_path / "x.py").write_text("X = 1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    head = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()

    result = runner.invoke(cli_app, ["safe-commit", "x.py", "-m", "  ", "--to-branch", branch], catch_exceptions=False)

    assert result.exit_code == 1
    assert "Commit message is empty" in result.stdout + (result.stderr or "")
    assert _git(tmp_path, "rev-parse", "HEAD").stdout.strip() == head


def test_join_message_paragraphs_drops_empty_values_and_strips() -> None:
    """The one helper case the CLI tests do not reach: blank values vanish, the rest are stripped."""
    assert join_message_paragraphs(["a", "", "  ", "b\n"]) == "a\n\nb"
