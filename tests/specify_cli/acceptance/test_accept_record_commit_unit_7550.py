"""#7550: the acceptance record commit has one path, a placement-true parent and a named refusal.

Narrow unit tests of ``specify_cli.acceptance``'s record-commit helpers. ``commit_for_mission`` is
monkeypatched at its import source; the parent-commit and branch probes run against a real git
repository. The end-to-end CLI behaviour is pinned by
``tests/integration/test_accept_record_commit_coord_7550.py``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import pytest

import specify_cli.acceptance as acceptance
from specify_cli.acceptance import (
    ACCEPT_RECORD_COMMIT_FAILED,
    AcceptanceError,
    AcceptanceRecordCommitError,
    _commit_acceptance_meta,
    _commit_acceptance_meta_via_router,
    _record_parent_commit,
    accept_primary_ref,
)
from specify_cli.coordination.commit_router import CommitRouterResult
from specify_cli.task_utils.support import TaskCliError

if TYPE_CHECKING:
    from specify_cli.acceptance import AcceptanceSummary

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_ROUTER = "specify_cli.coordination.commit_router.commit_for_mission"


class _Policy:
    def __init__(self, protected: frozenset[str] = frozenset()) -> None:
        self._protected = protected

    def is_protected(self, branch: str) -> bool:
        return branch in self._protected


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def _repo(tmp_path: Path, branch: str = "work") -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", branch)
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@x", "commit", "-q", "--allow-empty", "-m", "seed")
    return repo


def _meta(tmp_path: Path) -> Path:
    meta_path = tmp_path / "kitty-specs" / "m" / "meta.json"
    meta_path.parent.mkdir(parents=True)
    meta = {
        "mission_slug": "m",
        "slug": "m",
        "friendly_name": "m",
        "mission_type": "software-dev",
        "target_branch": "topic",
        "created_at": "2026-01-01T00:00:00Z",
        "acceptance_history": [{}],
    }
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    return meta_path


def _route(meta_path: Path) -> tuple[str | None, str | None, bool]:
    result: tuple[str | None, str | None, bool] = _commit_acceptance_meta_via_router(
        repo_root=meta_path.parents[2], mission_slug="m", meta_path=meta_path, policy=_Policy(), parent_commit="p0"
    )
    return result


# ---------------------------------------------------------------------------
# Named refusal: ACCEPT_RECORD_COMMIT_FAILED
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", ["error", "no_op_wrong_surface"])
def test_router_non_committed_status_is_the_named_refusal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: str) -> None:
    meta_path = _meta(tmp_path)
    monkeypatch.setattr(_ROUTER, lambda *_a, **_k: CommitRouterResult(status=status, placement_ref="topic", diagnostic="boom"))

    with pytest.raises(AcceptanceRecordCommitError) as excinfo:
        _route(meta_path)

    message = str(excinfo.value)
    assert message.startswith(f"{ACCEPT_RECORD_COMMIT_FAILED}:")
    assert "boom" in message and status in message
    assert str(meta_path) in message and "re-run `spec-kitty accept --mission m`" in message
    assert excinfo.value.error_code == ACCEPT_RECORD_COMMIT_FAILED
    assert isinstance(excinfo.value, AcceptanceError), "the accept command's AcceptanceError handler must render it"


@pytest.mark.parametrize("exc", [TaskCliError("The following paths are ignored: .worktrees"), OSError("disk"), RuntimeError("router")])
def test_router_exception_is_the_named_refusal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exc: Exception) -> None:
    meta_path = _meta(tmp_path)

    def _raise(*_a: object, **_k: object) -> CommitRouterResult:
        raise exc

    monkeypatch.setattr(_ROUTER, _raise)

    with pytest.raises(AcceptanceRecordCommitError, match=f"^{ACCEPT_RECORD_COMMIT_FAILED}:") as excinfo:
        _route(meta_path)
    assert excinfo.value.__cause__ is exc
    assert str(exc) in str(excinfo.value)


def test_corrupt_meta_keeps_its_typed_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.core.paths import MissionMetaReadError

    meta_path = _meta(tmp_path)
    corrupt = MissionMetaReadError(meta_path, ValueError("malformed"))

    def _raise(*_a: object, **_k: object) -> CommitRouterResult:
        raise corrupt

    monkeypatch.setattr(_ROUTER, _raise)
    with pytest.raises(MissionMetaReadError) as excinfo:
        _route(meta_path)
    assert excinfo.value is corrupt


def test_unchanged_record_creates_no_commit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    meta_path = _meta(tmp_path)
    monkeypatch.setattr(_ROUTER, lambda *_a, **_k: CommitRouterResult(status="unchanged", placement_ref="topic"))
    assert _route(meta_path) == ("p0", None, False)


def test_primary_ref_reaches_both_router_commits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    meta_path = _meta(tmp_path)
    seen: list[dict[str, Any]] = []

    def _record(*_a: object, **kwargs: Any) -> CommitRouterResult:
        seen.append(kwargs)
        return CommitRouterResult(status="committed", placement_ref="topic", commit_hash="abc1234")

    monkeypatch.setattr(_ROUTER, _record)
    result = _commit_acceptance_meta_via_router(
        repo_root=tmp_path, mission_slug="m", meta_path=meta_path, policy=_Policy(), parent_commit="p0", primary_ref="topic"
    )

    assert result == ("p0", "abc1234", True)
    assert [call["primary_ref"] for call in seen] == ["topic", "topic"]
    assert json.loads(meta_path.read_text(encoding="utf-8"))["accept_commit"] == "abc1234"


# ---------------------------------------------------------------------------
# One commit path; parent commit from the checkout that holds the record
# ---------------------------------------------------------------------------


def test_commit_acceptance_meta_has_no_raw_git_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The record is committed only through the router, with the parent read in the record's checkout."""
    record_repo = _repo(tmp_path)
    record_tip = _git(record_repo, "rev-parse", "HEAD")
    feature_dir = record_repo / "kitty-specs" / "m"
    feature_dir.mkdir(parents=True)
    other_root = tmp_path / "root"
    other_root.mkdir()
    summary = SimpleNamespace(repo_root=other_root, feature="m", feature_dir=feature_dir)

    git_calls: list[tuple[list[str], Path]] = []
    from specify_cli.task_utils import run_git as real_run_git

    def _spy(args: list[str], *, cwd: Path, check: bool = True) -> Any:
        git_calls.append((args, cwd))
        return real_run_git(args, cwd=cwd, check=check)

    router_calls: list[dict[str, Any]] = []

    def _router(*_a: object, **kwargs: Any) -> CommitRouterResult:
        router_calls.append(kwargs)
        return CommitRouterResult(status="unchanged", placement_ref="work")

    stamped: list[str | None] = []
    monkeypatch.setattr(acceptance, "run_git", _spy)
    monkeypatch.setattr(_ROUTER, _router)
    monkeypatch.setattr(acceptance, "_stamp_acceptance_record", lambda _s, _a, _m, parent, **_k: stamped.append(parent))
    monkeypatch.setattr("specify_cli.git.protection_policy.ProtectionPolicy.resolve", staticmethod(lambda _root: _Policy()))

    result = _commit_acceptance_meta(cast("AcceptanceSummary", summary), "qa", "local")

    assert result == (record_tip, None, False)
    assert stamped == [record_tip], "accepted_from_commit must be the tip of the branch the record is written on"
    assert not [args for args, _cwd in git_calls if args[0] in ("add", "commit")], "a raw git add/commit path is back"
    assert all(cwd == feature_dir for _args, cwd in git_calls), "git ran outside the checkout that holds the record"
    assert len(router_calls) == 1 and router_calls[0]["primary_ref"] == "work"
    assert router_calls[0]["files"] == (feature_dir / "meta.json",)


def test_record_parent_commit_reads_the_record_checkout(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    assert _record_parent_commit(repo) == _git(repo, "rev-parse", "HEAD")
    assert _record_parent_commit(tmp_path / "missing") is None


# ---------------------------------------------------------------------------
# accept_primary_ref: the branch checked out where the record is written
# ---------------------------------------------------------------------------


def test_accept_primary_ref_is_the_unprotected_record_branch(tmp_path: Path) -> None:
    repo = _repo(tmp_path, branch="kitty/mission-m")
    assert accept_primary_ref(repo, _Policy()) == "kitty/mission-m"


def test_accept_primary_ref_defers_to_the_router_on_a_protected_branch(tmp_path: Path) -> None:
    repo = _repo(tmp_path, branch="main")
    assert accept_primary_ref(repo, _Policy(frozenset({"main"}))) is None


def test_accept_primary_ref_defers_to_the_router_on_a_detached_or_missing_checkout(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _git(repo, "checkout", "-q", "--detach")
    assert accept_primary_ref(repo, _Policy()) is None
    assert accept_primary_ref(tmp_path / "missing", _Policy()) is None


# ---------------------------------------------------------------------------
# The accept command renders the refusal (no traceback)
# ---------------------------------------------------------------------------


def test_accept_command_renders_the_refusal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from specify_cli.cli.commands import accept as accept_cmd

    refusal = AcceptanceRecordCommitError("m", tmp_path / "meta.json", "TaskCliError: ignored")

    def _refuse(*_a: object, **_k: object) -> None:
        raise refusal

    monkeypatch.setattr(accept_cmd, "perform_acceptance", _refuse)
    outcome = accept_cmd._FinalizeOutcome()
    run = SimpleNamespace(commit_required=False, json_output=True, tracker=None, actual_mode="local", lenient=True, owned=None)

    accept_cmd._perform_acceptance_step(cast("accept_cmd._AcceptRun", run), cast("AcceptanceSummary", SimpleNamespace()), "qa", [], outcome)

    assert outcome.accept_exc is refusal
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"].startswith(f"{ACCEPT_RECORD_COMMIT_FAILED}:")


# ---------------------------------------------------------------------------
# Review folds: owned fact reaches the router; the second commit is best-effort
# ---------------------------------------------------------------------------


def test_owned_fact_reaches_both_router_commits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The commit resolves its placement against the owned fact the record was written with."""
    meta_path = _meta(tmp_path)
    owned = object()
    seen: list[Any] = []

    def _record(*_a: object, **kwargs: Any) -> CommitRouterResult:
        seen.append(kwargs["owned"])
        return CommitRouterResult(status="committed", placement_ref="topic", commit_hash="abc1234")

    monkeypatch.setattr(_ROUTER, _record)
    _commit_acceptance_meta_via_router(repo_root=tmp_path, mission_slug="m", meta_path=meta_path, policy=_Policy(), parent_commit="p0", owned=cast("Any", owned))

    assert seen == [owned, owned]


def test_failed_accept_commit_stamp_only_warns(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    """The acceptance commit landed; a failure of the follow-up stamp commit is not the refusal."""
    meta_path = _meta(tmp_path)
    calls: list[str] = []

    def _router(*_a: object, **kwargs: Any) -> CommitRouterResult:
        calls.append(str(kwargs["message"]))
        if len(calls) == 2:
            raise TaskCliError("index.lock exists")
        return CommitRouterResult(status="committed", placement_ref="topic", commit_hash="abc1234")

    monkeypatch.setattr(_ROUTER, _router)
    with caplog.at_level("WARNING"):
        result = _route(meta_path)

    assert result == ("p0", "abc1234", True)
    assert len(calls) == 2
    assert "did not land" in caplog.text and "ACCEPT_RECORD_COMMIT_FAILED" in caplog.text
