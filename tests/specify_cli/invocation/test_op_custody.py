"""Unit tests for Op-record write custody (#6564).

``resolve_op_record_root`` picks the checkout that owns the Op records,
``locate_op_record_root`` finds the checkout holding an existing record, and
``ProfileInvocationExecutor.op_write_refusal`` decides, before any write,
whether that checkout can take one.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from specify_cli import app as cli_app
from specify_cli.git.commit_helpers import SafeCommitDestinationNotFound
from specify_cli.invocation.executor import ProfileInvocationExecutor
from specify_cli.invocation.op_custody import (
    OP_WRITE_PROTECTED_BRANCH,
    OpWriteRefusal,
    OpWriteRefused,
    locate_op_record_root,
    resolve_op_record_root,
)
from specify_cli.invocation.writer import EVENTS_DIR
from tests.specify_cli.invocation._op_git import run_git, track_op_record_on_current_branch

pytestmark = [pytest.mark.non_sandbox, pytest.mark.fast]

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "profiles"
PROFILE = "implementer-fixture"

_COMPACT_CTX = MagicMock()
_COMPACT_CTX.mode = "compact"
_COMPACT_CTX.text = "compact governance context"


def _repo(path: Path) -> Path:
    path.mkdir(parents=True)
    run_git(path, "init", "-b", "main")
    run_git(path, "config", "user.email", "t@example.com")
    run_git(path, "config", "user.name", "T")
    run_git(path, "commit", "--allow-empty", "-m", "init")
    return path


def _with_profiles(project: Path) -> Path:
    profiles_dir = project / ".kittify" / "profiles"
    profiles_dir.mkdir(parents=True)
    for yaml_file in FIXTURES_DIR.glob("*.agent.yaml"):
        shutil.copy(yaml_file, profiles_dir / yaml_file.name)
    return project


# ---------------------------------------------------------------------------
# resolve_op_record_root
# ---------------------------------------------------------------------------


def test_linked_worktree_owns_its_op_records(tmp_path: Path) -> None:
    primary = _repo(tmp_path / "primary")
    lane = tmp_path / "lane"
    run_git(primary, "worktree", "add", "-b", "topic", str(lane))
    subdir = lane / "sub"
    subdir.mkdir()

    assert resolve_op_record_root(primary, subdir) == lane.resolve()


def test_repository_root_checkout_owns_its_op_records(tmp_path: Path) -> None:
    primary = _repo(tmp_path / "primary")

    assert resolve_op_record_root(primary, primary) == primary.resolve()


def test_checkout_of_another_repository_falls_back_to_the_project(tmp_path: Path) -> None:
    project = _repo(tmp_path / "project")
    other = _repo(tmp_path / "other")

    assert resolve_op_record_root(project, other) == project


def test_directory_outside_any_checkout_falls_back_to_the_project(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()

    with patch.dict("os.environ", {"GIT_CEILING_DIRECTORIES": str(tmp_path)}):
        assert resolve_op_record_root(project, outside) == project


def test_relative_worktree_gitdir_still_resolves_to_the_worktree(tmp_path: Path) -> None:
    """git 2.48 can write a worktree's ``gitdir:`` pointer relative; a subdirectory must still resolve."""
    primary = _repo(tmp_path / "primary")
    lane = tmp_path / "lane"
    run_git(primary, "worktree", "add", "-b", "topic", str(lane))
    (lane / ".git").write_text("gitdir: ../primary/.git/worktrees/lane\n", encoding="utf-8")
    subdir = lane / "deep" / "sub"
    subdir.mkdir(parents=True)

    assert resolve_op_record_root(primary, subdir) == lane.resolve()


def test_working_directory_is_the_default_start(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    primary = _repo(tmp_path / "primary")
    monkeypatch.chdir(primary)

    assert resolve_op_record_root(primary) == primary.resolve()


# ---------------------------------------------------------------------------
# ProfileInvocationExecutor.op_write_refusal
# ---------------------------------------------------------------------------


def test_not_a_git_checkout_is_admitted(tmp_path: Path) -> None:
    """No branch to commit on: the close reports it afterwards, as before."""
    assert ProfileInvocationExecutor(tmp_path).op_write_refusal() is None


def test_detached_head_is_admitted(tmp_path: Path) -> None:
    primary = _repo(tmp_path / "primary")
    track_op_record_on_current_branch(primary)
    run_git(primary, "checkout", "--detach")

    assert ProfileInvocationExecutor(primary).op_write_refusal() is None


def test_branch_protected_only_by_the_primary_config_is_refused(tmp_path: Path) -> None:
    """The project root's protection policy applies to a worktree's Op record too."""
    primary = _repo(tmp_path / "primary")
    track_op_record_on_current_branch(primary)
    lane = tmp_path / "lane"
    run_git(primary, "worktree", "add", "-b", "release", str(lane))
    config = primary / ".kittify" / "config.yaml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text("protection:\n  protected_branches: [main, release]\n", encoding="utf-8")

    refusal = ProfileInvocationExecutor(primary, record_root=lane.resolve()).op_write_refusal()

    assert refusal == OpWriteRefusal(OP_WRITE_PROTECTED_BRANCH, "protected branch 'release'")


def test_invoke_refuses_by_itself_before_writing_anything(tmp_path: Path) -> None:
    """Any caller of the executor is admitted, or refused with nothing written (#6564)."""
    primary = _with_profiles(_repo(tmp_path / "primary"))
    track_op_record_on_current_branch(primary)
    before = sorted((primary / EVENTS_DIR).glob("*.jsonl"))

    with patch("specify_cli.invocation.executor.build_charter_context", return_value=_COMPACT_CTX), pytest.raises(OpWriteRefused) as refused:
        ProfileInvocationExecutor(primary).invoke("implement it", profile_hint=PROFILE)

    assert refused.value.refusal == OpWriteRefusal(OP_WRITE_PROTECTED_BRANCH, "protected branch 'main'")
    assert sorted((primary / EVENTS_DIR).glob("*.jsonl")) == before


def test_unprotected_branch_is_admitted(tmp_path: Path) -> None:
    primary = _repo(tmp_path / "primary")
    track_op_record_on_current_branch(primary)
    run_git(primary, "checkout", "-b", "topic")

    assert ProfileInvocationExecutor(primary).op_write_refusal() is None


def test_other_commit_problems_are_left_to_the_close(tmp_path: Path) -> None:
    primary = _repo(tmp_path / "primary")
    track_op_record_on_current_branch(primary)
    refusal = SafeCommitDestinationNotFound(destination_ref="main", worktree_root=primary)

    with patch("specify_cli.invocation.executor.preflight_commit", side_effect=refusal):
        assert ProfileInvocationExecutor(primary).op_write_refusal() is None


# ---------------------------------------------------------------------------
# GlossaryChokepoint events_root
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("events_root_name", [None, "lane"])
def test_chokepoint_emits_events_under_its_events_root(tmp_path: Path, events_root_name: str | None) -> None:
    from glossary.chokepoint import GlossaryChokepoint

    events_root = tmp_path / events_root_name if events_root_name else None
    chokepoint = GlossaryChokepoint(tmp_path, events_root=events_root)

    with patch("glossary.events.emit_term_candidate_observed") as emit:
        chokepoint._emit_unknown_term_candidate(MagicMock(), event_context=MagicMock())

    assert emit.call_args.kwargs["repo_root"] == (events_root or tmp_path)


# ---------------------------------------------------------------------------
# invocations list reads the same checkout dispatch writes to
# ---------------------------------------------------------------------------


def test_invocations_list_reads_the_worktree_records(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    primary = _with_profiles(tmp_path / "primary")
    run_git(primary, "init", "-b", "main")
    run_git(primary, "config", "user.email", "t@example.com")
    run_git(primary, "config", "user.name", "T")
    run_git(primary, "add", ".kittify")
    run_git(primary, "commit", "-m", "init")
    lane = tmp_path / "lane"
    run_git(primary, "worktree", "add", "-b", "topic", str(lane))
    with patch("specify_cli.invocation.executor.build_charter_context", return_value=_COMPACT_CTX):
        invocation_id = ProfileInvocationExecutor(primary, record_root=lane.resolve()).invoke("implement it", profile_hint=PROFILE).invocation_id
    monkeypatch.chdir(lane)

    listed = CliRunner().invoke(cli_app, ["invocations", "list", "--json"])

    assert listed.exit_code == 0, listed.output
    assert invocation_id in {row["invocation_id"] for row in json.loads(listed.stdout)}


# ---------------------------------------------------------------------------
# locate_op_record_root
# ---------------------------------------------------------------------------


def _record(checkout: Path, invocation_id: str) -> None:
    (checkout / EVENTS_DIR).mkdir(parents=True, exist_ok=True)
    (checkout / EVENTS_DIR / f"{invocation_id}.jsonl").write_text("{}\n", encoding="utf-8")


_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAW"


def test_locate_prefers_the_invoking_checkout(tmp_path: Path) -> None:
    primary = _repo(tmp_path / "primary")
    lane = tmp_path / "lane"
    run_git(primary, "worktree", "add", "-b", "topic", str(lane))
    _record(primary, _ID)
    _record(lane, _ID)

    assert locate_op_record_root(primary, _ID, preferred=lane) == lane


@pytest.mark.parametrize(
    ("holder", "preferred"),
    [("lane", "primary"), ("primary", "lane")],
    ids=["record-in-another-worktree", "older-record-in-the-root-checkout"],
)
def test_locate_finds_a_record_held_by_another_checkout(tmp_path: Path, holder: str, preferred: str) -> None:
    primary = _repo(tmp_path / "primary")
    lane = tmp_path / "lane"
    run_git(primary, "worktree", "add", "-b", "topic", str(lane))
    checkouts = {"primary": primary, "lane": lane.resolve()}
    _record(checkouts[holder], _ID)

    assert locate_op_record_root(primary, _ID, preferred=checkouts[preferred]) == checkouts[holder]


@pytest.mark.parametrize("invocation_id", [_ID, "../../etc/passwd"])
def test_locate_returns_none_when_no_checkout_holds_the_record(tmp_path: Path, invocation_id: str) -> None:
    primary = _repo(tmp_path / "primary")

    assert locate_op_record_root(primary, invocation_id) is None


@pytest.mark.parametrize("error", [OSError("git missing"), subprocess.TimeoutExpired(["git"], 30)])
def test_locate_without_git_still_checks_the_known_checkouts(tmp_path: Path, error: Exception) -> None:
    _record(tmp_path, _ID)

    with patch("specify_cli.invocation.op_custody.subprocess.run", side_effect=error):
        assert locate_op_record_root(tmp_path / "missing", _ID, preferred=tmp_path) == tmp_path
        assert locate_op_record_root(tmp_path / "missing", "01ARZ3NDEKTSV4RRFFQ69G5FAX") is None


def test_claim_seam_reads_a_record_held_by_a_worktree(tmp_path: Path) -> None:
    from specify_cli.cli.commands.agent.workflow import _read_op_started_event

    primary = _with_profiles(_repo(tmp_path / "primary"))
    lane = tmp_path / "lane"
    run_git(primary, "worktree", "add", "-b", "topic", str(lane))
    with patch("specify_cli.invocation.executor.build_charter_context", return_value=_COMPACT_CTX):
        invocation_id = ProfileInvocationExecutor(primary, record_root=lane.resolve()).invoke("implement it", profile_hint=PROFILE).invocation_id

    assert _read_op_started_event(invocation_id, primary).invocation_id == invocation_id
