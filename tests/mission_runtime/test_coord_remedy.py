"""#5287: the one remote-only remedy builder (``mission_runtime.coord_remedy``)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from mission_runtime.coord_remedy import (
    RemoteOnlyBranch,
    coordination_doctor_command,
    remote_only_branch,
    remote_only_steps,
)

_BRANCH = "kitty/mission-demo-01ABCDEF"
_ROOT = Path("/work/repo")
_DOCTOR = coordination_doctor_command("demo-01ABCDEF")


# ---------------------------------------------------------------------------
# Pure rendering (no git)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_tracking_ref_present_skips_the_fetch_step() -> None:
    facts = RemoteOnlyBranch(branch=_BRANCH, remote="upstream", tracking_ref_present=True, remotes=("upstream",))

    text = remote_only_steps(facts, _ROOT, _DOCTOR)

    assert text == (
        f"Run in order: `git -C {_ROOT} branch {_BRANCH} refs/remotes/upstream/{_BRANCH}`, then `spec-kitty doctor coordination --mission demo-01ABCDEF --fix`."
    )


@pytest.mark.unit
def test_tracking_ref_absent_leads_with_a_targeted_fetch() -> None:
    facts = RemoteOnlyBranch(branch=_BRANCH, remote="origin", tracking_ref_present=False, remotes=("origin",))

    text = remote_only_steps(facts, _ROOT, "re-run the command")

    assert text == (
        f"Run in order: `git -C {_ROOT} fetch origin {_BRANCH}:refs/remotes/origin/{_BRANCH}`, "
        f"then `git -C {_ROOT} branch {_BRANCH} refs/remotes/origin/{_BRANCH}`, then re-run the command."
    )


@pytest.mark.unit
def test_ambiguous_remote_is_a_placeholder_that_lists_the_candidates() -> None:
    facts = RemoteOnlyBranch(branch=_BRANCH, remote=None, tracking_ref_present=False, remotes=("fork", "upstream"))

    text = remote_only_steps(facts, _ROOT, _DOCTOR)

    assert f"fetch REMOTE {_BRANCH}:refs/remotes/REMOTE/{_BRANCH}" in text
    assert f"branch {_BRANCH} refs/remotes/REMOTE/{_BRANCH}" in text
    assert text.endswith("(REMOTE is the remote that holds the branch, one of: fork, upstream)")
    assert "origin" not in text


@pytest.mark.unit
def test_no_remote_configured_says_so() -> None:
    facts = RemoteOnlyBranch(branch=_BRANCH, remote=None, tracking_ref_present=False, remotes=())

    assert remote_only_steps(facts, _ROOT, _DOCTOR).endswith("(no remote is configured: add one with `git remote add NAME URL`)")


@pytest.mark.unit
def test_an_unconfirmed_default_remote_names_the_other_candidates() -> None:
    facts = RemoteOnlyBranch(branch=_BRANCH, remote="origin", tracking_ref_present=False, remotes=("coord-remote", "origin"))

    text = remote_only_steps(facts, _ROOT, _DOCTOR)

    assert f"fetch origin {_BRANCH}" in text
    assert text.endswith("(if origin does not hold the branch, use the remote that does: coord-remote)")


@pytest.mark.unit
def test_a_confirmed_remote_carries_no_note() -> None:
    facts = RemoteOnlyBranch(branch=_BRANCH, remote="origin", tracking_ref_present=True, remotes=("coord-remote", "origin"))

    assert remote_only_steps(facts, _ROOT, _DOCTOR).endswith("--fix`.")


@pytest.mark.unit
def test_a_present_tracking_ref_names_its_remote() -> None:
    with pytest.raises(ValueError, match="names its remote"):
        RemoteOnlyBranch(branch=_BRANCH, remote=None, tracking_ref_present=True)


# ---------------------------------------------------------------------------
# Resolution from local git state (no network)
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "--allow-empty", "-m", "init")
    return root


def _add_remote(repo: Path, name: str, *, tracking: bool) -> None:
    _git(repo, "remote", "add", name, f"/nonexistent/{name}.git")
    if tracking:
        _git(repo, "update-ref", f"refs/remotes/{name}/{_BRANCH}", "HEAD")


@pytest.mark.git_repo
def test_the_only_remote_owns_the_branch_whatever_its_name(repo: Path) -> None:
    _add_remote(repo, "coord-remote", tracking=True)

    assert remote_only_branch(repo, _BRANCH) == RemoteOnlyBranch(branch=_BRANCH, remote="coord-remote", tracking_ref_present=True, remotes=("coord-remote",))


@pytest.mark.git_repo
def test_origin_wins_among_several_remotes(repo: Path) -> None:
    _add_remote(repo, "fork", tracking=False)
    _add_remote(repo, "origin", tracking=False)

    facts = remote_only_branch(repo, _BRANCH)

    assert facts.remote == "origin"
    assert facts.tracking_ref_present is False


@pytest.mark.git_repo
def test_several_remotes_without_origin_or_tracking_ref_is_ambiguous(repo: Path) -> None:
    _add_remote(repo, "fork", tracking=False)
    _add_remote(repo, "upstream", tracking=False)

    facts = remote_only_branch(repo, _BRANCH)

    assert facts.remote is None
    assert facts.remotes == ("fork", "upstream")


@pytest.mark.git_repo
def test_the_one_remote_holding_a_tracking_ref_is_preferred(repo: Path) -> None:
    _add_remote(repo, "origin", tracking=False)
    _add_remote(repo, "upstream", tracking=True)

    facts = remote_only_branch(repo, _BRANCH)

    assert facts.remote == "upstream"
    assert facts.tracking_ref_present is True


@pytest.mark.git_repo
def test_branch_remote_config_is_honoured(repo: Path) -> None:
    _add_remote(repo, "fork", tracking=False)
    _add_remote(repo, "origin", tracking=False)
    _git(repo, "config", f"branch.{_BRANCH}.remote", "fork")

    assert remote_only_branch(repo, _BRANCH).remote == "fork"


@pytest.mark.git_repo
def test_outside_a_repository_nothing_is_present(tmp_path: Path) -> None:
    facts = remote_only_branch(tmp_path, _BRANCH)

    assert facts.tracking_ref_present is False
    assert facts.remote is None


@pytest.mark.unit
def test_a_root_with_spaces_is_quoted() -> None:
    facts = RemoteOnlyBranch(branch=_BRANCH, remote="origin", tracking_ref_present=True, remotes=("origin",))

    assert f"`git -C '/work/my repo' branch {_BRANCH} refs/remotes/origin/{_BRANCH}`" in remote_only_steps(facts, Path("/work/my repo"), _DOCTOR)


@pytest.mark.git_repo
def test_a_branch_remote_that_names_no_configured_remote_is_unresolved(repo: Path) -> None:
    """Squad fold: ``branch.<b>.remote`` may hold a URL; ``refs/remotes/<url>/<b>`` is no ref."""
    _add_remote(repo, "fork", tracking=False)
    _add_remote(repo, "upstream", tracking=False)
    _git(repo, "config", f"branch.{_BRANCH}.remote", "https://example.invalid/repo.git")

    assert remote_only_branch(repo, _BRANCH).remote is None


@pytest.mark.git_repo
def test_an_unrunnable_git_reads_as_no_tracking_ref(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import mission_runtime.coord_remedy as coord_remedy
    from kernel.git.runner import GitCommandError

    _add_remote(repo, "origin", tracking=True)

    def _fail(*args: object, **kwargs: object) -> object:
        raise GitCommandError(argv=("rev-parse",), cwd=repo, returncode=-1, stderr="git missing")

    monkeypatch.setattr(coord_remedy, "run_git", _fail)

    facts = remote_only_branch(repo, _BRANCH)

    assert facts.remote == "origin"
    assert facts.tracking_ref_present is False


@pytest.mark.unit
def test_a_root_git_cannot_run_in_knows_nothing(tmp_path: Path) -> None:
    """CI fold: ``run_git`` raises on an absent root even with ``check=False``; never let that escape."""
    facts = remote_only_branch(tmp_path / "does-not-exist", _BRANCH)

    assert facts.remote is None
    assert facts.tracking_ref_present is False


@pytest.mark.unit
def test_the_placeholder_is_never_shell_special() -> None:
    """PR review nit: a pasted ``<remote>`` is a shell redirect."""
    facts = RemoteOnlyBranch(branch=_BRANCH, remote=None, tracking_ref_present=False, remotes=("fork", "upstream"))

    text = remote_only_steps(facts, _ROOT, _DOCTOR)

    assert "<" not in text
    assert ">" not in text


@pytest.mark.git_repo
def test_a_url_branch_remote_falls_back_to_the_only_configured_remote(repo: Path) -> None:
    """PR review nit: with one remote configured there is no ambiguity to report."""
    _add_remote(repo, "upstream", tracking=False)
    _git(repo, "config", f"branch.{_BRANCH}.remote", "https://example.invalid/repo.git")

    assert remote_only_branch(repo, _BRANCH).remote == "upstream"


@pytest.mark.unit
def test_an_unreadable_checkout_is_not_reported_as_having_no_remote(tmp_path: Path) -> None:
    """PR review nit: git could not run there, which is not the same as "no remote is configured"."""
    facts = remote_only_branch(tmp_path / "does-not-exist", _BRANCH)

    text = remote_only_steps(facts, tmp_path, _DOCTOR)

    assert "no remote is configured" not in text
    assert "could not read" in text
