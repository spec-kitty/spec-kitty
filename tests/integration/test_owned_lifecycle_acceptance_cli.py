"""Acceptance tests: owned-checkout ``agent action implement`` / ``review`` (WP09, US6).

owned-checkout-lifecycle-authority WP09 (FR-018, FR-020, NFR-004). Red-first
(C-007): reproduces US6 through the pre-existing entry points (``agent action
implement`` / ``agent action review``, run exactly as an operator hits them
today) before any WP09 fix.

Observed base (pre-WP09) behaviour: neither command accepts
``--owned-checkout`` at all, so the base is a Typer usage error, exit 2,
"No such option: --owned-checkout". The target is a typed, non-zero refusal
(``OWNED_ACTION_UNSUPPORTED``) with no worktree/branch side effects, per
FR-018 and the NFR-004 carve-out (there is no ``--json`` flag on these
commands; the refusal renders on stderr as ``Error: [<CODE>] ...``).
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from mission_runtime import OwnedRefusalCode
from specify_cli.cli.commands.agent.context import app as context_app
from specify_cli.cli.commands.agent.mission import app as mission_app
from specify_cli.cli.commands.agent.tasks import app as tasks_app
from specify_cli.cli.commands.agent.workflow import app as action_app
from tests.integration.conftest import OwnedCheckouts

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _worktree_and_branch_lists(repo_root: Path) -> tuple[str, str]:
    worktrees = subprocess.run(
        ["git", "-C", str(repo_root), "worktree", "list", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    branches = subprocess.run(
        ["git", "-C", str(repo_root), "branch", "--list"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return worktrees, branches


@pytest.mark.parametrize("command", ["implement", "review"])
@pytest.mark.parametrize("with_mission", [True, False])
def test_owned_action_refuses_with_owned_action_unsupported(
    owned_checkouts: OwnedCheckouts,
    r_snapshot: Any,
    command: str,
    with_mission: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """US6 (target): both commands refuse a valid P with OWNED_ACTION_UNSUPPORTED, no side effects."""
    p_root = owned_checkouts.owned_root
    r_root = owned_checkouts.repository_root
    monkeypatch.chdir(r_root)

    before_worktrees, before_branches = _worktree_and_branch_lists(r_root)
    before_snapshot = r_snapshot.take()

    args = [command, "WP01", "--owned-checkout", str(p_root)]
    if with_mission:
        args += ["--mission", owned_checkouts.mission_slug]

    runner = CliRunner()
    result = runner.invoke(action_app, args)
    combined = (result.stdout or "") + (result.output or "")

    assert result.exit_code == 1, combined
    assert OwnedRefusalCode.OWNED_ACTION_UNSUPPORTED.value in combined, combined
    assert OwnedRefusalCode.OWNED_ACTION_UNSUPPORTED.value in _registered_codes()
    normalized = " ".join(combined.split())
    assert "spec-kitty next --owned-checkout" in normalized, normalized
    assert "spec-kitty agent tasks move-task --owned-checkout" in normalized, normalized

    after_worktrees, after_branches = _worktree_and_branch_lists(r_root)
    assert after_worktrees == before_worktrees
    assert after_branches == before_branches
    r_snapshot.assert_unchanged(before_snapshot, r_snapshot.take())


def _registered_codes() -> frozenset[str]:
    return frozenset({member.value for member in OwnedRefusalCode})


@pytest.mark.parametrize("command", ["implement", "review"])
def test_owned_action_refuses_before_side_effects(
    owned_checkouts: OwnedCheckouts,
    command: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """US6: the refusal fires before ``_reset_workflow_receipts`` / the sparse-checkout preflight."""
    from specify_cli.cli.commands.agent import workflow as workflow_module

    monkeypatch.chdir(owned_checkouts.repository_root)

    def _boom(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"{command} must not run this before the owned refusal")

    monkeypatch.setattr(workflow_module, "_reset_workflow_receipts", _boom)
    if command == "implement":
        monkeypatch.setattr(
            workflow_module._executor,
            "implement_sparse_checkout_preflight",
            _boom,
        )

    runner = CliRunner()
    result = runner.invoke(
        action_app,
        [command, "WP01", "--owned-checkout", str(owned_checkouts.owned_root)],
    )
    combined = (result.stdout or "") + (result.output or "")
    assert result.exit_code == 1, combined
    assert OwnedRefusalCode.OWNED_ACTION_UNSUPPORTED.value in combined, combined


@pytest.mark.parametrize("command", ["implement", "review"])
def test_owned_action_repository_root_gets_more_specific_refusal(
    owned_checkouts: OwnedCheckouts,
    command: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Edge case: ``--owned-checkout R`` with ``--mission`` yields the more specific refusal."""
    monkeypatch.chdir(owned_checkouts.repository_root)
    runner = CliRunner()
    result = runner.invoke(
        action_app,
        [
            command,
            "WP01",
            "--owned-checkout",
            str(owned_checkouts.repository_root),
            "--mission",
            owned_checkouts.mission_slug,
        ],
    )
    combined = (result.stdout or "") + (result.output or "")
    assert result.exit_code == 1, combined
    assert OwnedRefusalCode.OWNED_CHECKOUT_IS_REPOSITORY_ROOT.value in combined, combined
    assert OwnedRefusalCode.OWNED_ACTION_UNSUPPORTED.value not in combined, combined


@pytest.mark.parametrize("command", ["implement", "review"])
def test_owned_action_flagless_untouched(command: str) -> None:
    """Positive control (c): without ``--owned-checkout`` the flag-free CLI parse is untouched."""
    runner = CliRunner()
    result = runner.invoke(action_app, [command, "--help"])
    assert result.exit_code == 0, result.output
    assert "--owned-checkout" in result.output


# ---------------------------------------------------------------------------
# T049 / FR-020 / US1-AS3 / NFR-004: the invalid-``--owned-checkout``-path
# matrix, across all five newly-wired flags. Every invalid case is paired
# with the valid-P control on the SAME fixture instance (never shared across
# cases -- each case builds its own fresh ``make_owned_checkouts()``
# instance), and every expected code is sourced from the ONE canonical
# registry (:class:`OwnedRefusalCode`) or a WP02-pinned test, never repeated
# here as a string literal (Sonar S1192, data-model.md's registry).
# ---------------------------------------------------------------------------

_COMMANDS: tuple[str, ...] = ("status", "setup-plan", "context-resolve", "action-implement", "action-review")


def _invoke_result(command: str, owned_checkout: Path, mission_slug: str) -> Any:
    """Invoke ``command`` with ``--owned-checkout`` + ``--mission``; return the raw ``click`` result."""
    runner = CliRunner()
    if command == "status":
        return runner.invoke(tasks_app, ["status", "--owned-checkout", str(owned_checkout), "--mission", mission_slug, "--json"])
    if command == "setup-plan":
        return runner.invoke(mission_app, ["setup-plan", "--owned-checkout", str(owned_checkout), "--mission", mission_slug, "--json"])
    if command == "context-resolve":
        return runner.invoke(
            context_app,
            ["--action", "implement", "--mission", mission_slug, "--wp-id", "WP01", "--json", "--owned-checkout", str(owned_checkout)],
        )
    if command == "action-implement":
        return runner.invoke(action_app, ["implement", "WP01", "--owned-checkout", str(owned_checkout), "--mission", mission_slug])
    if command == "action-review":
        return runner.invoke(action_app, ["review", "WP01", "--owned-checkout", str(owned_checkout), "--mission", mission_slug])
    raise AssertionError(command)  # pragma: no cover -- exhaustive over _COMMANDS


def _invoke_command(command: str, owned_checkout: Path, mission_slug: str) -> tuple[int, str]:
    """Invoke ``command``; return ``(exit_code, combined_output)``."""
    result = _invoke_result(command, owned_checkout, mission_slug)
    return result.exit_code, result.output


def _extract_code(command: str, exit_code: int, combined: str) -> str:
    """Extract the ``error_code`` from a refused invocation's output, per the command's envelope."""
    if command in ("status", "setup-plan", "context-resolve"):
        payload = json.loads(combined)
        return str(payload["error_code"])
    # implement/review: human-only "Error: [<CODE>] ..." on stderr (NFR-004 carve-out).
    import re

    match = re.search(r"Error: \[([A-Z_]+)\]", combined)
    assert match is not None, combined
    return match.group(1)


def _worktree_and_branch_snapshot(repo_root: Path) -> tuple[str, str]:
    return _worktree_and_branch_lists(repo_root)


def _p_snapshotter(checkouts: OwnedCheckouts) -> Any:
    """A snapshotter over P itself (the refused path must leave P untouched too)."""
    from tests._owned_fixtures import RSnapshotter
    from tests.integration.conftest import _home_for_snapshot

    return RSnapshotter(checkouts.owned_root, checkouts.repository_root, _home_for_snapshot())


def _assert_refused(
    command: str,
    checkouts: OwnedCheckouts,
    make_r_snapshot: Callable[[OwnedCheckouts], Any],
    path: Path,
    expected_code: OwnedRefusalCode,
) -> None:
    """One invalid-path row (T049 step 3): exit 1, clean typed refusal, and NO side effects anywhere.

    Asserts, in order: ``result.exception`` is a clean ``SystemExit`` (never a
    traceback), the exact registry code, R's full snapshot unchanged, P's full
    snapshot unchanged, R's worktree/branch lists unchanged, and -- for
    ``setup-plan`` -- that no ``plan.md`` was created in R.
    """
    r_snap = make_r_snapshot(checkouts)
    p_snap = _p_snapshotter(checkouts)
    r_before, p_before = r_snap.take(), p_snap.take()
    lists_before = _worktree_and_branch_snapshot(checkouts.repository_root)
    r_plan = checkouts.repository_root / "kitty-specs" / checkouts.mission_slug / "plan.md"
    r_plan_existed = r_plan.exists()
    result = _invoke_result(command, path, checkouts.mission_slug)
    assert result.exit_code == 1, result.output
    assert result.exception is None or isinstance(result.exception, SystemExit), repr(result.exception)
    assert _extract_code(command, result.exit_code, result.output) == expected_code.value
    r_snap.assert_unchanged(r_before, r_snap.take())
    p_snap.assert_unchanged(p_before, p_snap.take())
    assert _worktree_and_branch_snapshot(checkouts.repository_root) == lists_before
    if command == "setup-plan":
        # The refused run scaffolded no plan.md in R (rows that seed R with its
        # own mission copy start with one; the rest start, and must stay, without).
        assert r_plan.exists() == r_plan_existed


@pytest.mark.parametrize("command", _COMMANDS)
def test_fr020_missing_path_is_refused(
    command: str, make_owned_checkouts: Callable[..., OwnedCheckouts], make_r_snapshot: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    checkouts = make_owned_checkouts()
    monkeypatch.chdir(checkouts.repository_root)
    bad_path = checkouts.repository_root.parent / "does-not-exist"
    _assert_refused(command, checkouts, make_r_snapshot, bad_path, OwnedRefusalCode.OWNERSHIP_BROKEN_POINTER)


@pytest.mark.parametrize("command", _COMMANDS)
def test_fr020_directory_outside_any_repository_is_refused(
    command: str,
    make_owned_checkouts: Callable[..., OwnedCheckouts],
    make_r_snapshot: Callable[..., Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkouts = make_owned_checkouts()
    monkeypatch.chdir(checkouts.repository_root)
    plain_dir = tmp_path / f"plain-dir-{command}"
    plain_dir.mkdir()
    _assert_refused(command, checkouts, make_r_snapshot, plain_dir, OwnedRefusalCode.OWNERSHIP_BROKEN_POINTER)


@pytest.mark.parametrize("command", _COMMANDS)
def test_fr020_non_worktree_directory_inside_r_is_refused(
    command: str, make_owned_checkouts: Callable[..., OwnedCheckouts], make_r_snapshot: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    checkouts = make_owned_checkouts()
    monkeypatch.chdir(checkouts.repository_root)
    docs_dir = checkouts.repository_root / "docs"
    docs_dir.mkdir()
    _assert_refused(command, checkouts, make_r_snapshot, docs_dir, OwnedRefusalCode.OWNERSHIP_NESTED)


@pytest.mark.parametrize("command", _COMMANDS)
def test_fr020_foreign_repository_is_refused(
    command: str,
    make_owned_checkouts: Callable[..., OwnedCheckouts],
    make_r_snapshot: Callable[..., Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkouts = make_owned_checkouts()
    monkeypatch.chdir(checkouts.repository_root)
    foreign = tmp_path / f"foreign-{command}"
    foreign.mkdir()
    subprocess.run(["git", "init", "-q", str(foreign)], check=True)
    _assert_refused(command, checkouts, make_r_snapshot, foreign, OwnedRefusalCode.OWNERSHIP_FOREIGN)


@pytest.mark.parametrize("command", _COMMANDS)
def test_fr020_repository_root_itself_is_refused(
    command: str, make_owned_checkouts: Callable[..., OwnedCheckouts], make_r_snapshot: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    checkouts = make_owned_checkouts()
    monkeypatch.chdir(checkouts.repository_root)
    _assert_refused(command, checkouts, make_r_snapshot, checkouts.repository_root, OwnedRefusalCode.OWNED_CHECKOUT_IS_REPOSITORY_ROOT)


@pytest.mark.parametrize("command", _COMMANDS)
def test_fr020_lane_worktree_is_refused(
    command: str, make_owned_checkouts: Callable[..., OwnedCheckouts], make_r_snapshot: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    from specify_cli.lanes.worktree_allocator import predict_lane_worktree
    from tests.integration.conftest import _git, _write_mission, _write_single_lane_manifest

    checkouts = make_owned_checkouts()
    monkeypatch.chdir(checkouts.repository_root)
    # The lane-worktree-of-mission check needs the mission's ``lanes.json``
    # resolvable from R itself (WP02's own minter test,
    # ``test_lane_worktree_of_mission_is_refused``, builds R's OWN mission
    # copy for exactly this reason). ``owned_checkouts``' mission lives only
    # in P by default, so this row seeds R with the same mission id/lane-a
    # shape (mirrors ``stale_root_copy``, without depending on that fixture
    # being bound to THIS ``make_owned_checkouts()`` instance).
    r_mission_dir = checkouts.repository_root / "kitty-specs" / checkouts.mission_slug
    _write_mission(
        r_mission_dir,
        mission_id=checkouts.mission_id,
        slug=checkouts.mission_slug,
        topology="single_branch",
        target_branch=checkouts.target_branch,
        wp_ids=("WP01", "WP02"),
    )
    # #5100 (Invariant T-1): a ``single_branch`` manifest now defaults to the
    # repo-root ``lane-planning`` lane, which has no worktree; this row needs
    # the pre-#5100 (unmigrated) ``lane-a`` code-lane shape the lane-worktree
    # exclusion must still refuse.
    _write_single_lane_manifest(
        r_mission_dir,
        mission_slug=checkouts.mission_slug,
        mission_id=checkouts.mission_id,
        target_branch=checkouts.target_branch,
        wp_ids=("WP01", "WP02"),
        topology="lanes",
    )
    _git(checkouts.repository_root, "add", ".")
    _git(checkouts.repository_root, "commit", "-qm", "R's own mission copy for the lane-worktree check")
    lane_path, lane_branch = predict_lane_worktree(checkouts.repository_root, checkouts.mission_slug, "lane-a")
    _git(checkouts.repository_root, "worktree", "add", "-qb", lane_branch, str(lane_path))
    _assert_refused(command, checkouts, make_r_snapshot, lane_path, OwnedRefusalCode.OWNED_CHECKOUT_IS_MISSION_WORKTREE)


@pytest.mark.parametrize("command", _COMMANDS)
def test_fr020_coordination_worktree_is_refused(
    command: str, make_owned_checkouts: Callable[..., OwnedCheckouts], make_r_snapshot: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.integration.conftest import _git

    checkouts = make_owned_checkouts()
    monkeypatch.chdir(checkouts.repository_root)
    coord_path = checkouts.repository_root / ".worktrees" / f"{checkouts.mission_slug}-coord"
    _git(checkouts.repository_root, "worktree", "add", "-qb", f"codex/{checkouts.mission_slug}-coord", str(coord_path))
    _assert_refused(command, checkouts, make_r_snapshot, coord_path, OwnedRefusalCode.OWNED_CHECKOUT_IS_MISSION_WORKTREE)


@pytest.mark.parametrize("command", _COMMANDS)
def test_fr020_mismatched_branch_is_refused(
    command: str, make_owned_checkouts: Callable[..., OwnedCheckouts], make_r_snapshot: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.integration.conftest import _git

    checkouts = make_owned_checkouts()
    monkeypatch.chdir(checkouts.repository_root)
    _git(checkouts.owned_root, "checkout", "-qb", "other")
    _assert_refused(command, checkouts, make_r_snapshot, checkouts.owned_root, OwnedRefusalCode.OWNED_BRANCH_REFUSED)


@pytest.mark.parametrize("command", _COMMANDS)
def test_fr020_detached_head_is_refused(
    command: str, make_owned_checkouts: Callable[..., OwnedCheckouts], make_r_snapshot: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.integration.conftest import _git

    checkouts = make_owned_checkouts()
    monkeypatch.chdir(checkouts.repository_root)
    _git(checkouts.owned_root, "checkout", "--detach", "-q")
    _assert_refused(command, checkouts, make_r_snapshot, checkouts.owned_root, OwnedRefusalCode.OWNED_BRANCH_REFUSED)


@pytest.mark.parametrize("command", _COMMANDS)
def test_fr020_protected_target_is_refused(
    command: str, make_owned_checkouts: Callable[..., OwnedCheckouts], make_r_snapshot: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    checkouts = make_owned_checkouts(protected_target=True)
    monkeypatch.chdir(checkouts.repository_root)
    _assert_refused(command, checkouts, make_r_snapshot, checkouts.owned_root, OwnedRefusalCode.OWNED_BRANCH_REFUSED)


@pytest.mark.parametrize("command", _COMMANDS)
def test_fr020_non_single_branch_topology_is_refused(
    command: str, make_owned_checkouts: Callable[..., OwnedCheckouts], make_r_snapshot: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    checkouts = make_owned_checkouts(topology="lanes_with_coord")
    monkeypatch.chdir(checkouts.repository_root)
    _assert_refused(command, checkouts, make_r_snapshot, checkouts.owned_root, OwnedRefusalCode.OWNED_TOPOLOGY_UNSUPPORTED)


@pytest.mark.parametrize("command", _COMMANDS)
def test_fr020_valid_p_control(
    command: str, make_owned_checkouts: Callable[..., OwnedCheckouts], make_r_snapshot: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The valid-P control paired with every invalid row above (US1-AS3).

    Beyond the exit code: the success commands must yield a non-error payload
    naming the mission (and, for ``status``, exactly P's WPs), and every
    command must leave R's snapshot unchanged (the one named NFR-001 status
    mutex tolerated) and R's worktree/branch lists untouched.
    """
    checkouts = make_owned_checkouts()
    if command == "setup-plan":
        # setup-plan's mission-type-aware template resolution needs
        # "software-dev" activated in P's own .kittify/config.yaml -- this
        # fixture repo never runs `spec-kitty init` (see
        # test_owned_lifecycle_acceptance_status.py's _activate_mission_type
        # for the full rationale).
        config_path = checkouts.owned_root / ".kittify" / "config.yaml"
        text = config_path.read_text(encoding="utf-8")
        config_path.write_text(f"{text}mission_type_activations: [software-dev]\n", encoding="utf-8")
        subprocess.run(["git", "add", ".kittify/config.yaml"], cwd=checkouts.owned_root, check=True)
        subprocess.run(["git", "commit", "-qm", "activate software-dev"], cwd=checkouts.owned_root, check=True)
    monkeypatch.chdir(checkouts.repository_root)
    r_snap = make_r_snapshot(checkouts)
    r_before = r_snap.take()
    lists_before = _worktree_and_branch_snapshot(checkouts.repository_root)
    result = _invoke_result(command, checkouts.owned_root, checkouts.mission_slug)
    combined = result.output
    if command in ("action-implement", "action-review"):
        assert result.exit_code == 1, combined
        assert OwnedRefusalCode.OWNED_ACTION_UNSUPPORTED.value in combined, combined
    else:
        assert result.exit_code == 0, combined
        assert result.exception is None, repr(result.exception)
        payload = json.loads(combined)
        assert "error_code" not in payload, payload
        assert payload.get("result") != "error", payload
        if command == "status":
            assert payload["mission_slug"] == checkouts.mission_slug, payload
            assert sorted(wp["id"] for wp in payload["work_packages"]) == ["WP01", "WP02"], payload
        elif command == "setup-plan":
            assert payload.get("mission_slug", checkouts.mission_slug) == checkouts.mission_slug, payload
    r_snap.assert_unchanged(r_before, r_snap.take(), tolerate_status_mutex_for=checkouts.mission_slug)
    assert _worktree_and_branch_snapshot(checkouts.repository_root) == lists_before


@pytest.mark.parametrize("command", _COMMANDS)
def test_fr020_mutation_check_r_row_goes_red_when_claim_validator_accepts_r(
    command: str,
    make_owned_checkouts: Callable[..., OwnedCheckouts],
    make_r_snapshot: Callable[..., Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-vacuity (T049 step 4), for ALL five commands.

    Mutates the ONE shared claim validator (``claims_repository_root`` ->
    always ``False``, so R is no longer recognised as the repository root)
    and re-runs the very same row helper the real R row uses: it MUST fail.
    If it still passed under the mutant, the R-refusal assertions would be
    vacuous.
    """
    checkouts = make_owned_checkouts()
    monkeypatch.chdir(checkouts.repository_root)
    import specify_cli.core.checkout_ownership as ownership_module

    monkeypatch.setattr(ownership_module, "claims_repository_root", lambda claim: False)
    with pytest.raises(AssertionError):
        _assert_refused(command, checkouts, make_r_snapshot, checkouts.repository_root, OwnedRefusalCode.OWNED_CHECKOUT_IS_REPOSITORY_ROOT)
