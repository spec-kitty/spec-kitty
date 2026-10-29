"""``dispatch`` / ``profile-invocation complete --owned-checkout P`` keep Op records in P (#6682 follow-up).

``spec-kitty next --owned-checkout P`` already writes the Op records of an owned
Mission into P (#6682). The two Op commands resolved the record root from the
working directory only, so running them from the repository root checkout R
for owned work wrote ``kitty-ops/`` into R, which an owned checkout must never
touch. ``--owned-checkout P`` pins the record root to the validated P.

Real git, real ownership validation; only the governance context is stubbed.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner, Result

from specify_cli import app as cli_app
from specify_cli.invocation.writer import EVENTS_DIR
from tests.specify_cli.invocation._op_git import run_git, track_op_record_on_current_branch

pytestmark = [pytest.mark.non_sandbox, pytest.mark.fast]

runner = CliRunner()

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "profiles"
PROFILE = "implementer-fixture"

_COMPACT_CTX = MagicMock()
_COMPACT_CTX.mode = "compact"
_COMPACT_CTX.text = "compact governance context"


def _repository_root(tmp_path: Path, *, track_ops: bool = False) -> Path:
    """R: the repository root checkout on ``main`` with committed fixture profiles.

    With ``track_ops``, ``main`` tracks an Op record, so a record written in R
    would be refused there and a record written in P is auto-committed on P's branch.
    """
    root = tmp_path / "repository-root"
    profiles_dir = root / ".kittify" / "profiles"
    profiles_dir.mkdir(parents=True)
    for yaml_file in FIXTURES_DIR.glob("*.agent.yaml"):
        shutil.copy(yaml_file, profiles_dir / yaml_file.name)
    run_git(root, "init", "-b", "main")
    run_git(root, "config", "user.email", "t@example.com")
    run_git(root, "config", "user.name", "T")
    run_git(root, "add", ".kittify")
    run_git(root, "commit", "-m", "init")
    if track_ops:
        track_op_record_on_current_branch(root)
    return root


def _owned(root: Path, tmp_path: Path) -> Path:
    """P: a linked checkout of R's repository on its own branch."""
    owned = tmp_path / "owned"
    run_git(root, "worktree", "add", "-b", "kitty/owned-session", str(owned))
    return owned


def _cli(*args: str) -> Result:
    with patch("specify_cli.invocation.executor.build_charter_context", return_value=_COMPACT_CTX):
        return runner.invoke(cli_app, list(args))


def _porcelain(checkout: Path) -> str:
    return run_git(checkout, "status", "--porcelain", "--untracked-files=all", "--ignored")


def _dispatch(*extra: str) -> Result:
    return _cli("dispatch", "implement the thing", "--profile", PROFILE, "--json", *extra)


def test_dispatch_and_complete_from_r_keep_the_op_in_the_owned_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repository_root(tmp_path, track_ops=True)
    owned = _owned(root, tmp_path)
    head_before = run_git(root, "rev-parse", "HEAD")
    monkeypatch.chdir(root)

    opened = _dispatch("--owned-checkout", str(owned))

    assert opened.exit_code == 0, opened.output
    invocation_id = json.loads(opened.stdout)["invocation_id"]
    assert (owned / EVENTS_DIR / f"{invocation_id}.jsonl").is_file()
    assert _porcelain(root) == ""

    closed = _cli(
        "profile-invocation",
        "complete",
        "--invocation-id",
        invocation_id,
        "--outcome",
        "done",
        "--owned-checkout",
        str(owned),
    )

    assert closed.exit_code == 0, closed.output
    assert f"kitty-ops/{invocation_id}.jsonl" in run_git(owned, "show", "--name-only", "--format=", "HEAD")
    assert run_git(root, "rev-parse", "HEAD") == head_before
    assert _porcelain(root) == ""


def test_complete_with_owned_checkout_closes_an_op_held_in_r_where_it_is(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An Op opened in R (no flag) is still closed in R: the record is never split across checkouts."""
    root = _repository_root(tmp_path)
    owned = _owned(root, tmp_path)
    monkeypatch.chdir(root)
    opened = _dispatch()
    assert opened.exit_code == 0, opened.output
    invocation_id = json.loads(opened.stdout)["invocation_id"]

    closed = _cli(
        "profile-invocation",
        "complete",
        "--invocation-id",
        invocation_id,
        "--outcome",
        "done",
        "--owned-checkout",
        str(owned),
    )

    assert closed.exit_code == 0, closed.output
    lines = (root / EVENTS_DIR / f"{invocation_id}.jsonl").read_text(encoding="utf-8").splitlines()
    assert "completed" in [json.loads(line)["event"] for line in lines]
    assert not (owned / EVENTS_DIR).exists()


@pytest.mark.parametrize("extra", [(), ("--dry-run",)], ids=["open", "dry-run"])
def test_dispatch_refuses_the_repository_root_as_owned_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, extra: tuple[str, ...]) -> None:
    root = _repository_root(tmp_path)
    monkeypatch.chdir(root)

    result = _dispatch("--owned-checkout", str(root), *extra)

    assert result.exit_code == 1, result.output
    assert json.loads(result.stdout)["error"]["code"] == "OWNED_CHECKOUT_IS_REPOSITORY_ROOT"
    assert _porcelain(root) == ""


def test_dispatch_refuses_a_checkout_of_another_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repository_root(tmp_path)
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    run_git(foreign, "init", "-b", "main")
    monkeypatch.chdir(root)

    result = _dispatch("--owned-checkout", str(foreign))

    assert result.exit_code == 1, result.output
    assert json.loads(result.stdout)["error"]["code"] == "OWNERSHIP_FOREIGN"
    assert _porcelain(root) == ""
    assert not (foreign / EVENTS_DIR).exists()


def test_complete_refuses_an_invalid_owned_checkout_before_closing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repository_root(tmp_path)
    owned = _owned(root, tmp_path)
    monkeypatch.chdir(owned)
    opened = _dispatch()
    assert opened.exit_code == 0, opened.output
    invocation_id = json.loads(opened.stdout)["invocation_id"]
    record = owned / EVENTS_DIR / f"{invocation_id}.jsonl"
    before = record.read_text(encoding="utf-8")

    result = _cli(
        "profile-invocation",
        "complete",
        "--invocation-id",
        invocation_id,
        "--outcome",
        "done",
        "--owned-checkout",
        str(root),
        "--json",
    )

    assert result.exit_code == 1, result.output
    assert json.loads(result.stdout)["error"]["code"] == "OWNED_CHECKOUT_IS_REPOSITORY_ROOT"
    assert record.read_text(encoding="utf-8") == before


def _listed_ids(result: Result) -> set[str]:
    assert result.exit_code == 0, result.output
    return {record["invocation_id"] for record in json.loads(result.stdout)}


def test_list_from_r_with_owned_checkout_shows_the_ops_kept_in_p(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repository_root(tmp_path)
    owned = _owned(root, tmp_path)
    monkeypatch.chdir(root)
    opened = _dispatch("--owned-checkout", str(owned))
    assert opened.exit_code == 0, opened.output
    invocation_id = json.loads(opened.stdout)["invocation_id"]
    before = _porcelain(root)

    listed = _listed_ids(_cli("invocations", "list", "--json", "--owned-checkout", str(owned)))

    assert invocation_id in listed
    assert invocation_id not in _listed_ids(_cli("invocations", "list", "--json"))
    assert _porcelain(root) == before


def test_list_refuses_the_repository_root_as_owned_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repository_root(tmp_path)
    monkeypatch.chdir(root)

    result = _cli("invocations", "list", "--json", "--owned-checkout", str(root))

    assert result.exit_code == 1, result.output
    assert json.loads(result.stdout)["error"]["code"] == "OWNED_CHECKOUT_IS_REPOSITORY_ROOT"
