"""Owned checkout x #5100 protected single_branch missions (architecture review ff666bbbe).

Two #5100 shapes whose target branch is protected, each minted into an owned
checkout ``P`` and driven end to end through the ONE owned fact:

* **protected mint** -- ``meta.json`` records a minted ``mission_branch``; ``P``
  sits on that branch and every write lands there, while the mission still
  LANDS on its protected ``target_branch``.
* **commit_to_target** -- ``meta.json`` opts in with ``commit_to_target: true``;
  ``P`` sits on the protected target itself and the mission-scoped hatch
  un-protects exactly that branch for this mission's own writes.

Each row checks the minter -> ``CommitTarget`` -> workspace ``branch_name`` ->
``agent context resolve`` chain and performs one real owned write. The
commit_to_target rows also pin finding F1: an owned commit whose repository and
write roots are both ``P`` (``next``'s persist commit, the verdict revert) must
fold ``P``'s own ``meta.json`` through the fact, never re-derive the repository
root and read its (absent) copy.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from mission_runtime import CommitTarget, MissionArtifactKind, OwnedCheckout, placement_seam, resolve_action_context
from specify_cli.core.owned_mission import resolve_owned_mission
from tests.integration.conftest import OwnedCheckouts

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_TARGET = "codex/owned"


@pytest.fixture(autouse=True)
def _hatch_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()


def _rewrite_meta(checkouts: OwnedCheckouts, **fields: Any) -> None:
    meta_path = checkouts.mission_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta.update(fields)
    meta_path.write_text(json.dumps(meta), encoding="utf-8")


def _commit_all(root: Path, message: str) -> None:
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", message)


def _mission_branch(checkouts: OwnedCheckouts) -> str:
    return f"kitty/mission-{checkouts.mission_slug}"


@pytest.fixture
def protected_mint(make_owned_checkouts: Callable[..., OwnedCheckouts]) -> OwnedCheckouts:
    """A protected-target single_branch mission whose create minted ``mission_branch``; P is on it."""
    checkouts = make_owned_checkouts(protected_target=True, target_branch=_TARGET)
    _git(checkouts.owned_root, "checkout", "-qb", _mission_branch(checkouts))
    _rewrite_meta(checkouts, mission_branch=_mission_branch(checkouts))
    _commit_all(checkouts.owned_root, "fixture: protected-target mint")
    return checkouts


@pytest.fixture
def commit_to_target(make_owned_checkouts: Callable[..., OwnedCheckouts]) -> OwnedCheckouts:
    """A protected-target single_branch mission opted into ``commit_to_target``; P is on the target."""
    checkouts = make_owned_checkouts(protected_target=True, target_branch=_TARGET)
    _rewrite_meta(checkouts, commit_to_target=True)
    _commit_all(checkouts.owned_root, "fixture: commit_to_target")
    return checkouts


def _mint(checkouts: OwnedCheckouts) -> OwnedCheckout:
    return resolve_owned_mission(checkouts.repository_root, checkouts.owned_root, checkouts.mission_slug)


def _context_resolve(checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    from specify_cli.cli.commands.agent.context import app as context_app

    monkeypatch.chdir(checkouts.sibling)
    result = CliRunner().invoke(
        context_app,
        [
            "--action",
            "implement",
            "--mission",
            checkouts.mission_slug,
            "--wp-id",
            "WP01",
            "--json",
            "--owned-checkout",
            str(checkouts.owned_root),
        ],
    )
    assert result.exit_code == 0, result.output
    payload: dict[str, Any] = json.loads(result.output)
    return payload


def _touch_mission_file(checkouts: OwnedCheckouts, name: str = "research.md") -> Path:
    path = checkouts.mission_dir / name
    path.write_text("# owned write\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# F1: owned commits fold the fact's own meta (repository root == write root == P)
# ---------------------------------------------------------------------------


def test_commit_to_target_next_persist_commit_lands_on_the_protected_target(commit_to_target: OwnedCheckouts) -> None:
    """F1 red row: ``next``'s owned persist commit (``repo_root=P, worktree_root=P``) was refused as protected."""
    from specify_cli.cli.commands.next_cmd import _commit_owned_next_mutations

    fact = _mint(commit_to_target)
    before = _git(commit_to_target.owned_root, "rev-parse", _TARGET)
    _touch_mission_file(commit_to_target)

    _commit_owned_next_mutations(fact)

    assert _git(commit_to_target.owned_root, "rev-parse", _TARGET) != before
    assert _git(commit_to_target.owned_root, "status", "--porcelain") == ""


def test_commit_to_target_owned_safe_commit_with_both_roots_on_p(commit_to_target: OwnedCheckouts) -> None:
    """The verdict-revert shape (``repo_root=owned.owned_root``): the fold reads P's meta through the fact."""
    from specify_cli.git.commit_helpers import safe_commit

    fact = _mint(commit_to_target)
    path = _touch_mission_file(commit_to_target, "verdict.md")

    result = safe_commit(
        repo_root=fact.owned_root,
        worktree_root=fact.owned_root,
        target=CommitTarget(ref=fact.write_branch),
        message="owned write",
        paths=(path,),
        owned=fact,
    )

    assert result.destination_ref == _TARGET


def test_owned_fact_grants_no_bypass_to_another_missions_paths(commit_to_target: OwnedCheckouts) -> None:
    """The owned fold is scoped to the fact's own mission: a foreign mission dir stays protected."""
    from specify_cli.git.commit_helpers import ProtectedBranchRefused, safe_commit

    fact = _mint(commit_to_target)
    foreign = commit_to_target.owned_root / "kitty-specs" / "foreign-mission" / "spec.md"
    foreign.parent.mkdir(parents=True)
    foreign.write_text("# foreign\n", encoding="utf-8")

    with pytest.raises(ProtectedBranchRefused):
        safe_commit(
            repo_root=fact.owned_root,
            worktree_root=fact.owned_root,
            target=CommitTarget(ref=fact.write_branch),
            message="foreign write",
            paths=(foreign,),
            owned=fact,
        )


# ---------------------------------------------------------------------------
# Item 4: minter -> CommitTarget -> workspace branch_name -> context resolve
# ---------------------------------------------------------------------------


def test_protected_mint_chain(protected_mint: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.workspace.context import resolve_workspace_for_wp

    minted = _mission_branch(protected_mint)
    fact = _mint(protected_mint)
    assert fact.write_branch == minted

    target = placement_seam(fact.repository_root, fact.mission_slug, owned=fact).write_target(MissionArtifactKind.SPEC)
    assert target.ref == minted

    workspace = resolve_workspace_for_wp(fact.repository_root, fact.mission_slug, "WP01", owned=fact)
    assert workspace.branch_name == minted

    payload = _context_resolve(protected_mint, monkeypatch)
    # Landing branch in target_branch (the non-owned contract); the checkout /
    # write branch in the WP's branch_name.
    assert payload["target_branch"] == _TARGET
    assert payload["branch_name"] == minted

    context = resolve_action_context(fact.repository_root, action="implement", feature=fact.mission_slug, wp_id="WP01", owned=fact)
    assert context.target_branch == _TARGET
    assert context.branch_ref is not None
    assert context.branch_ref.target_branch == _TARGET
    assert context.branch_ref.destination_ref.ref == minted


def test_protected_mint_owned_write_lands_on_the_minted_branch(protected_mint: OwnedCheckouts) -> None:
    from specify_cli.cli.commands.next_cmd import _commit_owned_next_mutations

    fact = _mint(protected_mint)
    before_target = _git(protected_mint.repository_root, "rev-parse", _TARGET)
    before_minted = _git(protected_mint.owned_root, "rev-parse", fact.write_branch)
    _touch_mission_file(protected_mint)

    _commit_owned_next_mutations(fact)

    assert _git(protected_mint.owned_root, "rev-parse", fact.write_branch) != before_minted
    assert _git(protected_mint.repository_root, "rev-parse", _TARGET) == before_target


def test_commit_to_target_chain(commit_to_target: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.workspace.context import resolve_workspace_for_wp

    fact = _mint(commit_to_target)
    assert fact.write_branch == _TARGET

    target = placement_seam(fact.repository_root, fact.mission_slug, owned=fact).write_target(MissionArtifactKind.SPEC)
    assert target.ref == _TARGET

    workspace = resolve_workspace_for_wp(fact.repository_root, fact.mission_slug, "WP01", owned=fact)
    assert workspace.branch_name == _TARGET

    payload = _context_resolve(commit_to_target, monkeypatch)
    assert payload["target_branch"] == _TARGET
    assert payload["branch_name"] == _TARGET


def test_protected_target_without_opt_out_is_still_refused_at_mint(make_owned_checkouts: Callable[..., OwnedCheckouts]) -> None:
    """Control: the same protected target with neither a mint nor the opt-out is refused by the minter."""
    from mission_runtime import ActionContextError

    checkouts = make_owned_checkouts(protected_target=True, target_branch=_TARGET)
    with pytest.raises(ActionContextError) as excinfo:
        _mint(checkouts)
    assert excinfo.value.code == "OWNED_BRANCH_REFUSED"


@pytest.mark.parametrize("paths_only", [False, True])
@pytest.mark.parametrize("explicit_owned", [False, True])
def test_protected_mint_prerequisites_use_validated_write_branch(
    protected_mint: OwnedCheckouts,
    monkeypatch: pytest.MonkeyPatch,
    paths_only: bool,
    explicit_owned: bool,
) -> None:
    """#5877: tasks must accept the minted checkout while retaining the protected landing target."""
    from specify_cli.cli.commands.agent.mission import app as mission_app
    from tests.integration.test_explicit_checkout_commands import snapshot

    monkeypatch.chdir(protected_mint.sibling if explicit_owned else protected_mint.owned_root)
    roots = (protected_mint.repository_root, protected_mint.owned_root, protected_mint.sibling)
    before = tuple(snapshot(root) for root in roots)
    args = ["check-prerequisites", "--mission", protected_mint.mission_slug, "--json", "--include-tasks"]
    if explicit_owned:
        args += ["--owned-checkout", str(protected_mint.owned_root)]
    if paths_only:
        args += ["--paths-only"]

    result = CliRunner().invoke(mission_app, args)

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    minted = _mission_branch(protected_mint)
    assert payload["current_branch"] == minted
    assert payload["target_branch"] == _TARGET
    assert payload["planning_base_branch"] == _TARGET
    assert payload["merge_target_branch"] == _TARGET
    assert payload["branch_matches_target"] is True
    assert payload["BRANCH_MATCHES_TARGET"] is True
    assert payload["runtime_vars"]["branch_matches_target"] is True
    assert payload["branch_context"]["matches_target"] is True
    assert payload["branch_context"]["expected_checkout_branch"] == minted
    paths = payload if paths_only else payload["paths"]
    assert Path(paths["feature_dir"]) == protected_mint.mission_dir
    assert tuple(snapshot(root) for root in roots) == before


@pytest.mark.parametrize("paths_only", [False, True])
def test_commit_to_target_prerequisites_keep_target_contract(commit_to_target: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch, paths_only: bool) -> None:
    """#5877 control: an explicitly authorized target checkout still matches that target."""
    from specify_cli.cli.commands.agent.mission import app as mission_app

    monkeypatch.chdir(commit_to_target.owned_root)
    args = ["check-prerequisites", "--mission", commit_to_target.mission_slug, "--json"]
    if paths_only:
        args += ["--paths-only"]
    result = CliRunner().invoke(mission_app, args)
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["branch_matches_target"] is True
    assert payload["target_branch"] == _TARGET
    assert payload["branch_context"]["expected_checkout_branch"] == _TARGET


def test_protected_mint_prerequisites_refuse_wrong_checkout_branch(protected_mint: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
    """#5877 must not turn an invalid owned checkout into a successful branch capsule."""
    from specify_cli.cli.commands.agent.mission import app as mission_app

    _git(protected_mint.owned_root, "checkout", "-qb", "codex/wrong-branch")
    monkeypatch.chdir(protected_mint.sibling)
    result = CliRunner().invoke(
        mission_app,
        ["check-prerequisites", "--mission", protected_mint.mission_slug, "--json", "--owned-checkout", str(protected_mint.owned_root)],
    )
    assert result.exit_code != 0
    assert json.loads(result.output)["error_code"] == "OWNED_BRANCH_REFUSED"
