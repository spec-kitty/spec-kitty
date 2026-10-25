"""Op-record write custody for ``dispatch`` / ``profile-invocation complete`` (#6564).

Governance is discovered from the project (the primary checkout), but the Op
record belongs to the checkout the command runs in. From a linked worktree the
records land and commit there, and the primary checkout is never touched.
Where the auto-commit of the record would be refused (a protected branch that
tracks Op records), both commands refuse before anything is written.

Real git, real root resolvers, real protected-branch guard; only the
governance context is stubbed.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner, Result

from specify_cli import app as cli_app
from specify_cli.invocation.executor import ProfileInvocationExecutor
from specify_cli.invocation.writer import EVENTS_DIR
from tests.specify_cli.invocation._op_git import run_git, track_op_record_on_current_branch

pytestmark = [pytest.mark.non_sandbox, pytest.mark.fast]

runner = CliRunner()

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "profiles"
PROFILE = "implementer-fixture"

_COMPACT_CTX = MagicMock()
_COMPACT_CTX.mode = "compact"
_COMPACT_CTX.text = "compact governance context"


def _primary(tmp_path: Path, *, track_ops: bool) -> Path:
    """A primary checkout on ``main`` with committed fixture profiles."""
    primary = tmp_path / "primary"
    profiles_dir = primary / ".kittify" / "profiles"
    profiles_dir.mkdir(parents=True)
    for yaml_file in FIXTURES_DIR.glob("*.agent.yaml"):
        shutil.copy(yaml_file, profiles_dir / yaml_file.name)
    run_git(primary, "init", "-b", "main")
    run_git(primary, "config", "user.email", "t@example.com")
    run_git(primary, "config", "user.name", "T")
    run_git(primary, "add", ".kittify")
    run_git(primary, "commit", "-m", "init")
    if track_ops:
        track_op_record_on_current_branch(primary)
    return primary


def _linked_worktree(primary: Path, tmp_path: Path) -> Path:
    lane = tmp_path / "lane"
    run_git(primary, "worktree", "add", "-b", "topic/owned-session", str(lane))
    return lane


def _cli(*args: str) -> Result:
    with patch("specify_cli.invocation.executor.build_charter_context", return_value=_COMPACT_CTX):
        return runner.invoke(cli_app, list(args))


def _dispatch_json() -> Result:
    return _cli("dispatch", "implement the thing", "--profile", PROFILE, "--json")


def _porcelain(checkout: Path) -> str:
    return run_git(checkout, "status", "--porcelain", "--untracked-files=all")


def test_linked_worktree_keeps_op_records_out_of_the_primary_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The #6564 scenario: open and close from a feature worktree, primary on protected main."""
    primary = _primary(tmp_path, track_ops=True)
    lane = _linked_worktree(primary, tmp_path)
    main_before = run_git(primary, "rev-parse", "main")
    monkeypatch.chdir(lane)

    opened = _dispatch_json()

    assert opened.exit_code == 0, opened.output
    invocation_id = json.loads(opened.stdout)["invocation_id"]
    assert (lane / EVENTS_DIR / f"{invocation_id}.jsonl").is_file()
    assert not (primary / EVENTS_DIR / f"{invocation_id}.jsonl").exists()
    assert _porcelain(primary) == ""

    closed = _cli("profile-invocation", "complete", "--invocation-id", invocation_id, "--outcome", "done")

    assert closed.exit_code == 0, closed.output
    assert run_git(lane, "log", "-1", "--format=%s").startswith("op(")
    assert f"kitty-ops/{invocation_id}.jsonl" in run_git(lane, "show", "--name-only", "--format=", "HEAD")
    assert run_git(primary, "rev-parse", "main") == main_before
    assert _porcelain(primary) == ""


def test_dispatch_on_protected_branch_tracking_op_records_refuses_before_writing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    primary = _primary(tmp_path, track_ops=True)
    monkeypatch.chdir(primary)

    result = _dispatch_json()

    assert result.exit_code == 1, result.output
    error = json.loads(result.stderr)
    assert error["error"] == "op_write_refused"
    assert error["error_code"] == "OP_WRITE_PROTECTED_BRANCH"
    assert "'main'" in error["message"]
    assert "SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS" not in error["message"]
    assert _porcelain(primary) == ""


def test_dispatch_refusal_is_readable_without_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    primary = _primary(tmp_path, track_ops=True)
    monkeypatch.chdir(primary)

    result = _cli("dispatch", "implement the thing", "--profile", PROFILE)

    assert result.exit_code == 1, result.output
    text = " ".join(result.output.split())
    assert "Nothing was written" in text
    assert "protected branch 'main'" in text
    assert _porcelain(primary) == ""


def test_complete_on_protected_branch_tracking_op_records_refuses_before_writing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    primary = _primary(tmp_path, track_ops=True)
    # An Op opened directly through the executor (which itself admits any
    # caller), as an older CLI would have left it on main.
    with patch("specify_cli.invocation.executor.build_charter_context", return_value=_COMPACT_CTX):
        invocation_id = ProfileInvocationExecutor(primary).invoke("implement the thing", profile_hint=PROFILE).invocation_id
    record = primary / EVENTS_DIR / f"{invocation_id}.jsonl"
    before = record.read_bytes()
    monkeypatch.chdir(primary)

    result = _cli("profile-invocation", "complete", "--invocation-id", invocation_id, "--outcome", "done", "--json")

    assert result.exit_code == 1, result.output
    assert json.loads(result.stderr)["error_code"] == "OP_WRITE_PROTECTED_BRANCH"
    assert record.read_bytes() == before


def test_dispatch_on_primary_that_tracks_no_op_records_is_admitted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#6410's local-only path stays open: the record is kept, never committed."""
    primary = _primary(tmp_path, track_ops=False)
    monkeypatch.chdir(primary)

    result = _dispatch_json()

    assert result.exit_code == 0, result.output
    invocation_id = json.loads(result.stdout)["invocation_id"]
    assert (primary / EVENTS_DIR / f"{invocation_id}.jsonl").is_file()


def test_op_opened_in_a_worktree_closes_from_the_primary_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The close finds the checkout holding the record and commits there, not on protected main."""
    primary = _primary(tmp_path, track_ops=True)
    lane = _linked_worktree(primary, tmp_path)
    monkeypatch.chdir(lane)
    invocation_id = json.loads(_dispatch_json().stdout)["invocation_id"]
    monkeypatch.chdir(primary)

    closed = _cli("profile-invocation", "complete", "--invocation-id", invocation_id, "--outcome", "done")

    assert closed.exit_code == 0, closed.output
    assert run_git(lane, "log", "-1", "--format=%s").startswith("op(")
    assert _porcelain(primary) == ""


def test_unknown_op_on_protected_branch_is_not_found_not_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    primary = _primary(tmp_path, track_ops=True)
    monkeypatch.chdir(primary)

    result = _cli("profile-invocation", "complete", "--invocation-id", "01ARZ3NDEKTSV4RRFFQ69G5FAW", "--outcome", "done", "--json")

    assert result.exit_code == 1, result.output
    assert json.loads(result.stderr)["error"] == "complete_failed"
    assert _porcelain(primary) == ""


def test_unreadable_protection_config_refuses_dispatch_without_a_traceback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    primary = _primary(tmp_path, track_ops=True)
    (primary / ".kittify" / "config.yaml").write_text("protection:\n  protected_branches: main\n", encoding="utf-8")
    run_git(primary, "add", ".kittify/config.yaml")
    run_git(primary, "commit", "-m", "malformed protection")
    monkeypatch.chdir(primary)

    result = _dispatch_json()

    assert result.exit_code == 1, result.output
    assert json.loads(result.stderr)["error_code"] == "OP_WRITE_PROTECTION_CONFIG_INVALID"
    assert _porcelain(primary) == ""
