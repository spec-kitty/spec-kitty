"""Acceptance tests: owned-checkout ``agent context resolve`` (WP08).

owned-checkout-lifecycle-authority WP08 (FR-006/FR-007/FR-020/FR-021,
NFR-002/NFR-004, US2/US7). Red-first (C-007): reproduces O3, O4, O10 and the
US2/US7 rows through the pre-existing entry point (``agent context resolve``,
run exactly as an operator hits it today -- flagless, from the owned
checkout) before any WP08 fix. Every red row has a same-fixture positive
control (below) that is green on both the planning base and the fix, so
nothing here can pass vacuously.

Observed base (pre-WP08) behaviour, recorded from real runs against the
planning-base commit (``5ff83a621``) in a scratch detached worktree, review
cycle 1 finding 12 corrected the previous (inaccurate) note here:

* O3 (flagless from P, no stale copy): an uncaught ``ValueError`` from
  ``workspace/context.py`` -- ``"Work package WP01 was not found under
  <R>/kitty-specs/owned-fixture-.../tasks"``. The base's caller-preference
  probe picks P as the anchor root for mission *identity*, but WP-workspace
  resolution still walks from the primary root's own (mission-less)
  ``tasks/`` dir, so the base crashes here -- it never reaches an
  ``exit 0`` result at all.
* O4 (same, with ``stale_root_copy()`` active so R also carries a copy):
  exit 0, but ``resolution_kind == "lane_workspace"`` with ``lane_id`` and
  ``workspace_path`` derived from R's stale copy's OWN (two-lane, foreign)
  ``lanes.json`` -- the base-tree-fold bug FR-007/O4 describes. The stale
  copy's presence is what lets WP01's lookup succeed at all (unlike plain
  O3 above), and it succeeds against the WRONG (R's) lane manifest.
* O10 (an unregistered ``.git``-pointer checkout that merely *looks* linked):
  the same uncaught ``ValueError`` as plain O3 -- exactly the NFR-004 defect
  (a refusal must never surface as an uncaught exception).
* O10, the real registered-checkout-on-a-mismatched-branch row: the base
  ADOPTS it unvalidated -- ``mission_dir``/``wp_file`` come from the caller's
  own checkout, not R, with no branch check at all.
* US7-AS2 / US7-AS4 (a lane worktree / coordination worktree that holds M):
  the base ADOPTS it unvalidated too -- ``mission_dir`` is reported under
  ``.worktrees/<slug>-lane-a`` / ``.worktrees/<slug>-coord`` instead of R,
  which is exactly the over-adoption FR-021 forbids.
* FR-020 R (``--owned-checkout`` on the base, which has no such flag):
  Typer usage error, exit 2, "No such option: --owned-checkout".
* US2-AS2 / US7-AS5: already match the target on this fixture (the base's
  naive caller-root preference happens to coincide with the validated one
  when the caller IS a real registered worktree); kept here as **positive
  controls**, not red rows -- FR-021's point is exactly that the base
  degrades once the caller checkout is *not* a registered worktree, or is
  a registered worktree the mission does not actually own (O10, US7-AS2/AS4).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from mission_runtime import OwnedRefusalCode
from specify_cli.cli.commands.agent.context import app as context_app
from specify_cli.coordination.surface_resolver import WorktreeRegistryUnavailable
from specify_cli.core.owned_mission import FEATURE_CONTEXT_UNRESOLVED, MISSION_CONTEXT_CONFLICT
from tests.integration.conftest import OwnedCheckouts

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

# NFR-004: the full data-model.md Error code registry ``context resolve`` may
# surface for an owned run, sourced from the one canonical enum plus the
# handful of pre-existing wire codes -- never repeated as fresh literals here
# (review cycle 1 finding 6).
_REGISTERED_ERROR_CODES: frozenset[str] = frozenset({member.value for member in OwnedRefusalCode}) | {
    WorktreeRegistryUnavailable.error_code,
    FEATURE_CONTEXT_UNRESOLVED,
    MISSION_CONTEXT_CONFLICT,
    # Non-owned-registry codes this command can also raise (control rows only);
    # no canonical named constant exists for these pre-existing generic codes.
    "MISSION_NOT_FOUND",
    "MISSION_AMBIGUOUS_SELECTOR",
    "INVALID_ACTION",
    "PROJECT_ROOT_UNRESOLVED",
    "MISSING_MISSION",
}


@pytest.fixture
def runner() -> CliRunner:
    """Return a typer CliRunner. typer >=0.13 separates stdout/stderr by default."""
    return CliRunner()


def _resolve(runner: CliRunner, *args: str) -> Any:
    """Invoke ``agent context resolve`` directly on its app.

    Typer collapses a single-command app: ``["resolve", ...]`` would be an
    unexpected-extra-argument usage error, so every call here omits the
    ``"resolve"`` token (confirmed against this base, ``test_json_envelope_strict.py``).
    """
    return runner.invoke(context_app, list(args))


def _assert_no_uncaught_exception(result: Any) -> None:
    assert result.exception is None or isinstance(result.exception, SystemExit), f"uncaught exception: {result.exception!r}\n{result.output}"


def _payload(result: Any) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(result.output)
    assert isinstance(data, dict), f"expected a JSON object, got {type(data).__name__}: {result.output!r}"
    return data


def _assert_registered_refusal(result: Any) -> dict[str, Any]:
    _assert_no_uncaught_exception(result)
    assert result.exit_code == 1, result.output
    payload = _payload(result)
    assert payload["error_code"] in _REGISTERED_ERROR_CODES, payload["error_code"]
    return payload


@pytest.fixture(autouse=True)
def _clear_repo_root_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """``locate_project_root`` honours ``SPECIFY_REPO_ROOT``; unset it so cwd governs (T038 edge case)."""
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)


def _under(path: str | None, ancestor: Path) -> bool:
    assert path is not None
    return Path(path).resolve().is_relative_to(ancestor.resolve())


def _p_code_lane_id(owned_checkouts: OwnedCheckouts) -> str:
    """Give P's own ``lanes.json`` a legacy CODE lane (committed on P) and return its id.

    Since #5100 (Invariant T-1) the default ``single_branch`` fixture writes
    only the repo-root ``lane-planning`` lane, which has no worktree -- so a
    "lane worktree of the mission" row needs the pre-#5100 (unmigrated)
    ``lane-a`` code-lane shape, which the lane-worktree exclusion predicate
    must still refuse.
    """
    from specify_cli.lanes.compute import is_repo_root_lane
    from specify_cli.lanes.persistence import read_lanes_json
    from tests.integration.conftest import _git, _write_single_lane_manifest

    _write_single_lane_manifest(
        owned_checkouts.mission_dir,
        mission_slug=owned_checkouts.mission_slug,
        mission_id=owned_checkouts.mission_id,
        target_branch=owned_checkouts.target_branch,
        wp_ids=("WP01", "WP02"),
        topology="lanes",
    )
    _git(owned_checkouts.owned_root, "add", ".")
    _git(owned_checkouts.owned_root, "commit", "-qm", "legacy code-lane manifest")
    manifest = read_lanes_json(owned_checkouts.mission_dir)
    assert manifest is not None and manifest.lanes and not is_repo_root_lane(manifest.lanes[0])
    return str(manifest.lanes[0].lane_id)


def _branch_worktree_holding_mission(owned_checkouts: OwnedCheckouts, path: Path, branch: str) -> None:
    """Create a REAL, registered git worktree at ``path`` that holds mission M.

    Branches from ``owned_checkouts.target_branch``'s own tip commit (never
    that branch name itself, which is already checked out at ``owned_root``)
    so the new worktree's working tree is byte-identical to P's, including
    the committed ``kitty-specs/<slug>`` mission directory (review cycle 1
    finding 1: the lane/coordination no-adoption controls must hold M, not
    branch from R's mission-less HEAD).

    Used where the worktree's checked-out branch identity does not matter to
    the assertion (O10's mismatched-branch row deliberately wants a *different*
    branch than ``target_branch``).
    """
    subprocess.run(
        ["git", "worktree", "add", "-qb", branch, str(path), owned_checkouts.target_branch],
        cwd=owned_checkouts.repository_root,
        check=True,
    )


def _target_branch_worktree_holding_mission(owned_checkouts: OwnedCheckouts, path: Path) -> None:
    """Create a REAL, registered git worktree at ``path`` checked out ON ``target_branch`` itself, holding M.

    Review cycle 1 finding 1 (HIGH), mutation-proof follow-up: the lane- and
    coordination-worktree no-adoption rows must isolate the
    ``_is_lane_worktree_of_mission`` / ``_is_coordination_worktree`` exclusion
    predicates as the ONLY reason adoption is refused. A worktree branched
    onto a *new* branch name (as :func:`_branch_worktree_holding_mission`
    does) also fails the downstream ``resolve_owned_mission`` branch check
    (``current != target_branch``) -- ``adopt_owned_checkout`` catches that
    ``ActionContextError`` and returns ``None`` regardless of whether the
    exclusion predicate ran, so mutating the predicate away had no observable
    effect (confirmed by a scratch-worktree mutation probe: both mutants left
    the old rows green). Checking the new worktree out directly on
    ``target_branch`` removes that confound: git forbids two worktrees on the
    same branch simultaneously, so this first frees the branch by removing
    ``owned_root``'s worktree (safe here -- neither test that calls this
    reads ``owned_root`` again afterward).
    """
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(owned_checkouts.owned_root)],
        cwd=owned_checkouts.repository_root,
        check=True,
    )
    subprocess.run(
        ["git", "worktree", "add", "-q", str(path), owned_checkouts.target_branch],
        cwd=owned_checkouts.repository_root,
        check=True,
    )


# ---------------------------------------------------------------------------
# O3 / FR-006 / US2-AS1: flagless resolution from the owned checkout.
# ---------------------------------------------------------------------------


def test_o3_flagless_from_owned_root_resolves_under_p(runner: CliRunner, owned_checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(owned_checkouts.owned_root)
    result = _resolve(runner, "--action", "implement", "--mission", owned_checkouts.mission_slug, "--wp-id", "WP01", "--json")
    _assert_no_uncaught_exception(result)
    assert result.exit_code == 0, result.output
    payload = _payload(result)
    assert payload["resolution_kind"] == "owned_checkout"
    assert payload["lane_id"] is None
    assert _under(payload["wp_file"], owned_checkouts.owned_root)
    assert _under(payload["workspace_path"], owned_checkouts.owned_root)
    assert payload["commands"]
    assert payload["stale_repository_root_copy"] is None


def test_o3_explicit_owned_checkout_flag(runner: CliRunner, owned_checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
    """O3-flag: explicit ``--owned-checkout P`` from a sibling checkout of the SAME repo behaves like flagless-from-P.

    cwd must still resolve to the repository (``locate_project_root`` is a
    plain filesystem walk from cwd, independent of ``--owned-checkout``), so
    this uses the fixture's sibling worktree rather than an unrelated
    ``tmp_path`` outside the repo entirely.
    """
    monkeypatch.chdir(owned_checkouts.sibling)
    result = _resolve(
        runner,
        "--action",
        "implement",
        "--mission",
        owned_checkouts.mission_slug,
        "--wp-id",
        "WP01",
        "--json",
        "--owned-checkout",
        str(owned_checkouts.owned_root),
    )
    _assert_no_uncaught_exception(result)
    assert result.exit_code == 0, result.output
    payload = _payload(result)
    assert payload["resolution_kind"] == "owned_checkout"
    assert payload["lane_id"] is None
    assert _under(payload["wp_file"], owned_checkouts.owned_root)


def test_o3_flagless_from_owned_root_parametrised_handle(
    runner: CliRunner, owned_checkouts: OwnedCheckouts, owned_handle: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O3 over every handle form (slug, mid8, mission id -- ``owned_handle``)."""
    monkeypatch.chdir(owned_checkouts.owned_root)
    result = _resolve(runner, "--action", "implement", "--mission", owned_handle, "--wp-id", "WP01", "--json")
    assert result.exit_code == 0, result.output
    payload = _payload(result)
    assert payload["resolution_kind"] == "owned_checkout"


# ---------------------------------------------------------------------------
# O4 / FR-007 / US2-AS3: a stale repository-root copy.
# ---------------------------------------------------------------------------


def test_o4_stale_root_copy_paths_under_p_and_flagged(
    runner: CliRunner,
    owned_checkouts: OwnedCheckouts,
    stale_root_copy: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    r_copy_dir = stale_root_copy()
    monkeypatch.chdir(owned_checkouts.owned_root)
    result = _resolve(runner, "--action", "implement", "--mission", owned_checkouts.mission_slug, "--wp-id", "WP01", "--json")
    assert result.exit_code == 0, result.output
    payload = _payload(result)
    assert _under(payload["wp_file"], owned_checkouts.owned_root)
    assert _under(payload["workspace_path"], owned_checkouts.owned_root)
    assert payload["stale_repository_root_copy"] == {
        "path": str(r_copy_dir),
        "mission_id": owned_checkouts.mission_id,
    }
    assert any(str(r_copy_dir) in w for w in payload["warnings"])


def test_us2_as3_human_mode_warns_on_stderr(
    runner: CliRunner,
    owned_checkouts: OwnedCheckouts,
    stale_root_copy: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    r_copy_dir = stale_root_copy()
    monkeypatch.chdir(owned_checkouts.owned_root)
    result = _resolve(runner, "--action", "implement", "--mission", owned_checkouts.mission_slug, "--wp-id", "WP01")
    assert result.exit_code == 0, result.output
    # Rich hard-wraps a long console line (including inside an unbroken path
    # token) at the terminal width; strip ALL whitespace before substring
    # matching so the assertion is robust to where exactly it folds.
    unwrapped_stdout = "".join(result.stdout.split())
    unwrapped_stderr = "".join(result.stderr.split())
    assert "".join(str(r_copy_dir).split()) not in unwrapped_stdout
    assert "".join(str(r_copy_dir).split()) in unwrapped_stderr


def test_no_stale_copy_gives_null_and_no_warning(runner: CliRunner, owned_checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-vacuity sibling of O4: no copy in R -> ``null``, no stale text."""
    monkeypatch.chdir(owned_checkouts.owned_root)
    result = _resolve(runner, "--action", "implement", "--mission", owned_checkouts.mission_slug, "--wp-id", "WP01", "--json")
    payload = _payload(result)
    assert payload["stale_repository_root_copy"] is None
    assert not any("stale copy" in w for w in payload["warnings"])


def test_us2_as2_wp_absent_from_p_present_in_r_copy(
    runner: CliRunner,
    owned_checkouts: OwnedCheckouts,
    stale_root_copy: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """WP09 exists only in R's stale copy: refuse, naming P, never a path under R."""
    stale_root_copy()
    monkeypatch.chdir(owned_checkouts.owned_root)
    result = _resolve(runner, "--action", "implement", "--mission", owned_checkouts.mission_slug, "--wp-id", "WP09", "--json")
    payload = _assert_registered_refusal(result)
    assert payload["error_code"] == OwnedRefusalCode.WORK_PACKAGE_UNRESOLVED
    assert str(owned_checkouts.owned_root) in payload["error"]
    assert str(owned_checkouts.repository_root) not in payload["error"]


# ---------------------------------------------------------------------------
# O10 / FR-021 / US7: no adoption for a lane worktree, a coordination
# worktree, a validator-rejected (unregistered or mismatched-branch) linked
# checkout, or R itself.
# ---------------------------------------------------------------------------


def _r_only_payload(runner: CliRunner, owned_checkouts: OwnedCheckouts, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.chdir(owned_checkouts.repository_root)
    result = _resolve(runner, "--action", "implement", "--mission", owned_checkouts.mission_slug, "--wp-id", "WP01", "--json")
    return _payload(result)


def test_o10_unregistered_pointer_checkout_matches_r(
    runner: CliRunner,
    owned_checkouts: OwnedCheckouts,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A hand-written ``.git`` pointer that merely *looks* linked is refused adoption (extra row; kept from T038)."""
    caller = tmp_path / "lookalike"
    caller.mkdir()
    gitdir = owned_checkouts.repository_root / ".git" / "worktrees" / "lookalike"
    gitdir.mkdir(parents=True)
    gitdir.joinpath("HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    caller.joinpath(".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")
    shutil.copytree(owned_checkouts.mission_dir, caller / "kitty-specs" / owned_checkouts.mission_slug)

    r_payload = _r_only_payload(runner, owned_checkouts, monkeypatch)
    monkeypatch.chdir(caller)
    result = _resolve(runner, "--action", "implement", "--mission", owned_checkouts.mission_slug, "--wp-id", "WP01", "--json")
    _assert_no_uncaught_exception(result)
    # Review cycle 1 finding 2: always equal to R's payload, whatever the exit
    # code -- never a disjunction that a registered-but-wrong error could slip
    # through.
    assert _payload(result) == r_payload


def test_o10_real_registered_checkout_on_mismatched_branch_matches_r(
    runner: CliRunner,
    owned_checkouts: OwnedCheckouts,
    stale_root_copy: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The spec's actual O10 row: a REAL, registered linked checkout on a mismatched branch that holds M.

    ``stale_root_copy()`` gives R a real copy too, so "equals cwd = R"
    compares two SUCCESS payloads -- non-vacuous (review cycle 1 finding 2).
    """
    stale_root_copy()
    mismatched_branch = "codex/mismatched-branch"
    mismatched_dir = tmp_path / "mismatched-branch-checkout"
    _branch_worktree_holding_mission(owned_checkouts, mismatched_dir, mismatched_branch)

    r_payload = _r_only_payload(runner, owned_checkouts, monkeypatch)
    assert r_payload["success"] is True

    monkeypatch.chdir(mismatched_dir)
    result = _resolve(runner, "--action", "implement", "--mission", owned_checkouts.mission_slug, "--wp-id", "WP01", "--json")
    _assert_no_uncaught_exception(result)
    assert _payload(result) == r_payload


def test_us7_as1_flagless_from_p_equals_explicit_flag(
    runner: CliRunner,
    owned_checkouts: OwnedCheckouts,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(owned_checkouts.owned_root)
    flagless = _resolve(runner, "--action", "tasks_outline", "--mission", owned_checkouts.mission_slug, "--json")
    monkeypatch.chdir(owned_checkouts.sibling)
    flagged = _resolve(
        runner,
        "--action",
        "tasks_outline",
        "--mission",
        owned_checkouts.mission_slug,
        "--json",
        "--owned-checkout",
        str(owned_checkouts.owned_root),
    )
    assert flagless.exit_code == 0, flagless.output
    assert _payload(flagless) == _payload(flagged)


def test_us7_as1_flagless_equals_flagged_with_stale_copy(
    runner: CliRunner,
    owned_checkouts: OwnedCheckouts,
    stale_root_copy: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T041 step 3a: US7-AS1 must also hold with the stale-copy channel active (review cycle 1 finding 9)."""
    stale_root_copy()
    monkeypatch.chdir(owned_checkouts.owned_root)
    flagless = _resolve(runner, "--action", "implement", "--mission", owned_checkouts.mission_slug, "--wp-id", "WP01", "--json")
    monkeypatch.chdir(owned_checkouts.sibling)
    flagged = _resolve(
        runner,
        "--action",
        "implement",
        "--mission",
        owned_checkouts.mission_slug,
        "--wp-id",
        "WP01",
        "--json",
        "--owned-checkout",
        str(owned_checkouts.owned_root),
    )
    assert flagless.exit_code == 0, flagless.output
    flagless_payload = _payload(flagless)
    assert flagless_payload == _payload(flagged)
    assert flagless_payload["stale_repository_root_copy"] is not None


def test_us7_as2_lane_worktree_cwd_matches_r(
    runner: CliRunner,
    owned_checkouts: OwnedCheckouts,
    stale_root_copy: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A lane worktree of the mission -- holding M, per P's own ``lanes.json`` -- is never adopted; matches cwd=R.

    Review cycle 1 finding 1 (HIGH): the previous version branched from R's
    HEAD, which does not carry M, so ``adopt_owned_checkout`` returned
    ``None`` at "mission absent from toplevel" before either exclusion
    predicate ran -- the row was vacuous. A later fix held M by branching from
    ``target_branch``'s tip onto a NEW branch name, but that also failed
    non-vacuously: the new worktree's branch never matched ``target_branch``,
    so ``resolve_owned_mission``'s branch check refused it independently,
    again masking whether ``_is_lane_worktree_of_mission`` ran (confirmed red
    by a scratch-worktree mutation probe that left the row green under both
    mutants). This version checks the lane worktree out directly ON
    ``target_branch`` itself (freeing it by removing ``owned_root`` first),
    so the branch check cannot fire and the mutation proof isolates
    ``_is_lane_worktree_of_mission`` as the sole guard.
    """
    from specify_cli.lanes.worktree_allocator import predict_lane_worktree

    stale_root_copy()
    lane_id = _p_code_lane_id(owned_checkouts)
    lane_dir, _lane_branch = predict_lane_worktree(owned_checkouts.repository_root, owned_checkouts.mission_slug, lane_id)
    _target_branch_worktree_holding_mission(owned_checkouts, lane_dir)

    r_payload = _r_only_payload(runner, owned_checkouts, monkeypatch)
    assert r_payload["success"] is True

    monkeypatch.chdir(lane_dir)
    result = _resolve(runner, "--action", "implement", "--mission", owned_checkouts.mission_slug, "--wp-id", "WP01", "--json")
    assert _payload(result) == r_payload


def test_us7_as4_coordination_worktree_cwd_matches_r(
    runner: CliRunner,
    owned_checkouts: OwnedCheckouts,
    stale_root_copy: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A coordination worktree -- holding M -- is never adopted; matches cwd=R.

    Same finding-1 fix as the lane-worktree row above, including the
    mutation-proof follow-up: the worktree is checked out directly on
    ``target_branch`` (not a new branch name) so the branch check inside
    ``resolve_owned_mission`` cannot independently refuse it and mask whether
    ``_is_coordination_worktree`` ran.
    """
    stale_root_copy()
    coord_dir = owned_checkouts.repository_root / ".worktrees" / f"{owned_checkouts.mission_slug}-coord"
    _target_branch_worktree_holding_mission(owned_checkouts, coord_dir)

    r_payload = _r_only_payload(runner, owned_checkouts, monkeypatch)
    assert r_payload["success"] is True

    monkeypatch.chdir(coord_dir)
    result = _resolve(runner, "--action", "implement", "--mission", owned_checkouts.mission_slug, "--wp-id", "WP01", "--json")
    assert _payload(result) == r_payload


def test_us7_as5_conflicting_ids_refuse(
    runner: CliRunner,
    owned_checkouts: OwnedCheckouts,
    stale_root_copy: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stale_root_copy(different_id=True)
    monkeypatch.chdir(owned_checkouts.owned_root)
    result = _resolve(runner, "--action", "implement", "--mission", owned_checkouts.mission_slug, "--wp-id", "WP01", "--json")
    payload = _assert_registered_refusal(result)
    assert payload["error_code"] == MISSION_CONTEXT_CONFLICT


# ---------------------------------------------------------------------------
# FR-020: ``--owned-checkout`` rows for ``context resolve`` (the full matrix
# is WP09 T049; this WP lands only what applies to this command).
# ---------------------------------------------------------------------------


def test_fr020_owned_checkout_is_repository_root(
    runner: CliRunner,
    owned_checkouts: OwnedCheckouts,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(owned_checkouts.owned_root)
    result = _resolve(
        runner,
        "--action",
        "implement",
        "--mission",
        owned_checkouts.mission_slug,
        "--wp-id",
        "WP01",
        "--json",
        "--owned-checkout",
        str(owned_checkouts.repository_root),
    )
    payload = _assert_registered_refusal(result)
    assert payload["error_code"] == OwnedRefusalCode.OWNED_CHECKOUT_IS_REPOSITORY_ROOT


def test_nfr004_no_lanes_stale_copy_never_uncaught(
    runner: CliRunner,
    owned_checkouts: OwnedCheckouts,
    stale_root_copy: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stale copy missing ``lanes.json``: a typed refusal or exit 0 with P paths, never a traceback."""
    stale_root_copy(with_lanes=False)
    monkeypatch.chdir(owned_checkouts.owned_root)
    result = _resolve(runner, "--action", "implement", "--mission", owned_checkouts.mission_slug, "--wp-id", "WP01", "--json")
    _assert_no_uncaught_exception(result)
    if result.exit_code == 0:
        payload = _payload(result)
        assert _under(payload["wp_file"], owned_checkouts.owned_root)
    else:
        payload = _assert_registered_refusal(result)
        assert payload["error_code"] in _REGISTERED_ERROR_CODES


# ---------------------------------------------------------------------------
# Positive controls (must stay green on both base and fix; NFR-001).
# ---------------------------------------------------------------------------


def test_control_a_non_owned_mission_in_r_is_unchanged(
    runner: CliRunner,
    owned_checkouts: OwnedCheckouts,
    stale_root_copy: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T038's byte-equality pin: the FULL non-owned payload, captured inline (review cycle 1 finding 8).

    Confirmed identical on both the planning base (``5ff83a621``) and this
    WP's head for ``tasks_outline``/``implement WP01``/``implement WP04``/
    ``specify`` from cwd = R with an R copy -- reviewer-verified in cycle 1.
    Dynamic fixture-derived values (``mission_slug``, ``target_branch``, the
    computed ``feature_dir``) are threaded in by reference; every other key
    and the full shape are pinned literally, not sampled.
    """
    stale_root_copy()  # gives R its own kitty-specs/<slug> copy to resolve directly
    monkeypatch.chdir(owned_checkouts.repository_root)
    result = _resolve(runner, "--action", "tasks_outline", "--mission", owned_checkouts.mission_slug, "--json")
    assert result.exit_code == 0, result.output
    payload = _payload(result)

    feature_dir = str(owned_checkouts.repository_root / "kitty-specs" / owned_checkouts.mission_slug)
    expected = {
        "success": True,
        "action": "tasks_outline",
        "mission_slug": owned_checkouts.mission_slug,
        "feature_dir": feature_dir,
        "target_branch": owned_checkouts.target_branch,
        "detection_method": "explicit",
        "wp_id": None,
        "wp_file": None,
        "lane": None,
        "lane_id": None,
        "branch_name": None,
        "execution_mode": None,
        "resolution_kind": None,
        "dependencies": [],
        "resolved_base": None,
        "auto_merge": False,
        "workspace_path": None,
        "commands": {
            "check_prerequisites": f"spec-kitty agent mission check-prerequisites --json --paths-only --include-tasks --mission {owned_checkouts.mission_slug}",
            "finalize_tasks": f"spec-kitty agent mission finalize-tasks --mission {owned_checkouts.mission_slug} --json",
        },
        "warnings": [],
        "mission_dir": feature_dir,
    }
    assert payload == expected
    assert "stale_repository_root_copy" not in payload


@pytest.mark.parametrize("cwd_choice", ["repository_root", "owned_checkout", "elsewhere"])
def test_control_c_r_snapshot_unchanged_around_every_invocation(
    runner: CliRunner,
    owned_checkouts: OwnedCheckouts,
    r_snapshot: Any,
    monkeypatch: pytest.MonkeyPatch,
    cwd_choice: str,
) -> None:
    target = {
        "repository_root": owned_checkouts.repository_root,
        "owned_checkout": owned_checkouts.owned_root,
        "elsewhere": owned_checkouts.sibling,
    }[cwd_choice]
    monkeypatch.chdir(target)
    before = r_snapshot.take()
    _resolve(runner, "--action", "implement", "--mission", owned_checkouts.mission_slug, "--wp-id", "WP01", "--json")
    after = r_snapshot.take()
    r_snapshot.assert_unchanged(before, after)


# ---------------------------------------------------------------------------
# NFR-002: exactly one ownership validation per invocation.
# ---------------------------------------------------------------------------


def test_nfr002_exactly_one_ownership_validation(
    runner: CliRunner,
    owned_checkouts: OwnedCheckouts,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.core import checkout_ownership
    from specify_cli.workspace.context import clear_workspace_resolution_caches

    calls: list[int] = []
    original = checkout_ownership.resolve_ownership_claim

    def _counting(*args: Any, **kwargs: Any) -> Any:
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(checkout_ownership, "resolve_ownership_claim", _counting)

    clear_workspace_resolution_caches()
    monkeypatch.chdir(owned_checkouts.sibling)
    _resolve(
        runner,
        "--action",
        "implement",
        "--mission",
        owned_checkouts.mission_slug,
        "--wp-id",
        "WP01",
        "--json",
        "--owned-checkout",
        str(owned_checkouts.owned_root),
    )
    assert len(calls) == 1
    calls.clear()

    clear_workspace_resolution_caches()
    monkeypatch.chdir(owned_checkouts.owned_root)
    _resolve(runner, "--action", "implement", "--mission", owned_checkouts.mission_slug, "--wp-id", "WP01", "--json")
    assert len(calls) == 1
    calls.clear()

    clear_workspace_resolution_caches()
    monkeypatch.chdir(owned_checkouts.repository_root)
    _resolve(runner, "--action", "implement", "--mission", owned_checkouts.mission_slug, "--wp-id", "WP01", "--json")
    assert len(calls) == 0
