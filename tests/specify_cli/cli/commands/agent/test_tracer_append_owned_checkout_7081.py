"""Real CLI proof of owned tracer writes and refuse-before-write (#7081).

The existing shared fixtures mint real R/P/S checkouts. Positive cases inspect
committed content and clean worktrees, not only the command's success payload;
invalid claims must leave the roots, index, HEAD, lock root and home unchanged.
"""

from __future__ import annotations

import importlib
import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest
import typer
from typer.testing import CliRunner, Result

from tests._owned_fixtures import RSnapshotter, claim_counter
from tests.integration.conftest import OwnedCheckouts, make_owned_checkouts, make_r_snapshot

__all__ = ["claim_counter", "make_owned_checkouts", "make_r_snapshot"]

pytestmark = [pytest.mark.git_repo, pytest.mark.regression]

SLUG = "tracer-owned-01M6G9FW"
BRANCH = "kitty/mission-tracer-owned-01M6G9FW"
MID = "01M6G9FWJDPXEKG88H3968Y7GG"
CATEGORY = "approach"
ENTRY = "owned routing probe"
ACTOR = "tester"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()


@pytest.fixture
def tracer_module() -> ModuleType:
    return importlib.import_module("specify_cli.cli.commands.agent.tracer_append")


def _invoke(module: ModuleType, handle: str, extra: list[str]) -> Result:
    app = typer.Typer()
    app.command()(module.tracer_append)
    return CliRunner().invoke(app, ["--mission", handle, "--category", CATEGORY, "--entry", ENTRY, "--actor", ACTOR, "--json", *extra], catch_exceptions=False)


def _json_payload(output: str) -> dict[str, object]:
    start = output.find("{")
    assert start >= 0, output
    payload, _end = json.JSONDecoder().raw_decode(output[start:])
    assert isinstance(payload, dict), payload
    return payload


def _checkouts(make: Callable[..., OwnedCheckouts], *, protected_alias: bool = False) -> OwnedCheckouts:
    checkouts = make(
        mission_slug=SLUG,
        mission_id=MID,
        target_branch="codex/owned" if protected_alias else "main",
        mission_branch=None if protected_alias else BRANCH,
        protected_target=protected_alias,
    )
    if protected_alias:
        # Exercise the spec's real mission-scoped opt-in, not an environment
        # override: the minter admits P, and the eventual commit must agree.
        meta_path = checkouts.mission_dir / "meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["commit_to_target"] = True
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
        _git(checkouts.owned_root, "add", ".")
        _git(checkouts.owned_root, "commit", "-qm", "fixture: mission-scoped protected target opt-in")
    return checkouts


def _assert_committed(result: Result, checkouts: OwnedCheckouts, expected_branch: str) -> None:
    assert result.exit_code == 0, result.output
    payload = _json_payload(result.output)
    assert payload["ok"] is True, payload
    assert _git(checkouts.owned_root, "branch", "--show-current") == expected_branch
    assert payload["commit_ref"] == expected_branch
    relative = f"kitty-specs/{SLUG}/traces/{CATEGORY}.md"
    committed = _git(checkouts.owned_root, "show", f"{expected_branch}:{relative}")
    assert ENTRY in committed and ACTOR in committed
    assert _git(checkouts.owned_root, "status", "--porcelain") == ""
    assert _git(checkouts.repository_root, "status", "--porcelain") == ""
    assert not list(checkouts.repository_root.rglob("traces/*.md"))


@pytest.mark.parametrize("protected_alias", [False, True], ids=["minted-topic", "protected-target-mid8"])
def test_flagless_invocation_from_the_owned_checkout_writes_into_it(
    make_owned_checkouts: Callable[..., OwnedCheckouts],
    make_r_snapshot: Callable[[OwnedCheckouts], RSnapshotter],
    tracer_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    claim_counter: list[Path | None],
    protected_alias: bool,
) -> None:
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)
    checkouts = _checkouts(make_owned_checkouts, protected_alias=protected_alias)
    expected_branch = _git(checkouts.owned_root, "branch", "--show-current")
    snapshotter = make_r_snapshot(checkouts)
    before = snapshotter.take()
    monkeypatch.chdir(checkouts.mission_dir)
    claim_counter.clear()

    result = _invoke(tracer_module, checkouts.mid8 if protected_alias else SLUG, [])

    _assert_committed(result, checkouts, expected_branch)
    assert len(claim_counter) == 1, claim_counter
    snapshotter.assert_unchanged(before, snapshotter.take(), tolerate_status_mutex_for=SLUG)


def test_explicit_selector_from_the_repository_root_writes_into_the_owned_checkout(
    make_owned_checkouts: Callable[..., OwnedCheckouts],
    make_r_snapshot: Callable[[OwnedCheckouts], RSnapshotter],
    tracer_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    checkouts = _checkouts(make_owned_checkouts)
    snapshotter = make_r_snapshot(checkouts)
    before = snapshotter.take()
    monkeypatch.chdir(checkouts.repository_root)
    expected_branch = _git(checkouts.owned_root, "branch", "--show-current")

    result = _invoke(tracer_module, SLUG, ["--owned-checkout", str(checkouts.owned_root)])

    _assert_committed(result, checkouts, expected_branch)
    snapshotter.assert_unchanged(before, snapshotter.take(), tolerate_status_mutex_for=SLUG)


def test_repository_root_claim_refuses_before_writing(
    make_owned_checkouts: Callable[..., OwnedCheckouts],
    make_r_snapshot: Callable[[OwnedCheckouts], RSnapshotter],
    tracer_module: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    checkouts = _checkouts(make_owned_checkouts)
    r_snapshot = make_r_snapshot(checkouts)
    p_snapshot = RSnapshotter(checkouts.owned_root, checkouts.repository_root, None)
    before_r, before_p = r_snapshot.take(), p_snapshot.take()
    monkeypatch.chdir(checkouts.repository_root)

    result = _invoke(tracer_module, SLUG, ["--owned-checkout", str(checkouts.repository_root)])

    assert result.exit_code == 1, result.output
    payload = _json_payload(result.output)
    assert payload["ok"] is False
    error = payload["error"]
    assert isinstance(error, dict)
    assert error["code"] == "OWNED_CHECKOUT_IS_REPOSITORY_ROOT"
    r_snapshot.assert_unchanged(before_r, r_snapshot.take())
    p_snapshot.assert_unchanged(before_p, p_snapshot.take())
