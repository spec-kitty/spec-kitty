"""#5113 / FR-014: every unmaterialized-coordination remedy is truthful.

Round-trip proof: for every emitter classified as *unmaterialized*
(branch present, worktree absent — never deleted/never-created, never
husk/EMPTY), the ``spec-kitty …`` command the emitted text names is extracted
via one shared regex, run through its real entry point, and asserted to leave
the coordination worktree materialized. Guards against any of these emitters
naming ``spec-kitty doctor workspaces --fix``, which only removes husks and
CANNOT create a worktree (#2240) -- the named command must actually
materialize the worktree, not merely run cleanly while it stays absent.

Classification:

* ``surface_resolver`` (``CoordinationWorktreeUnmaterialized.next_step``)
  — unmaterialized. IN this round trip.
* ``doctor coordination`` finding (``COORDINATION_WORKTREE_MISSING``) —
  unmaterialized by construction (that is the finding's whole purpose). IN.
* ``runtime_bridge`` (``_resolve_wp_board_action``'s ``CoordinationWorktree
  Unmaterialized`` arm) — unmaterialized. IN. The sibling
  ``CoordinationBranchDeleted`` arm is a DIFFERENT (deleted) classification
  and is NOT a case here (it now surfaces its own flatten-guidance
  ``next_step`` instead of "Materialize it" — see ``test_bridge_parity.py``).
* ``write_target_degrade.assert_coord_write_materialized`` — TWO arms both
  reach the same raise: (a) remote-only (branch not a local head — a
  MULTI-STEP remedy, exercised separately below, not in this parametrized
  round trip) and (b) a STALE local head (branch present, worktree absent) —
  unmaterialized. IN (single-command case).
* ``implement_cores.py::_resolve_placement_ref`` (consumed by
  ``implement()`` at the real ``_resolve_placement_ref(repo_root,
  mission_slug=..., wp_id=...)`` call site) routes through
  :func:`~mission_runtime.resolve_action_context`, whose status-surface leg
  resolves with ``for_write=False`` (the READ shape) — so it genuinely
  raises/degrades-to-``None`` for BOTH the unmaterialized AND the deleted/
  never-created classification. IN this round trip, called directly (the
  real production resolver, on a real fresh unmaterialized Mission) rather
  than through the full ``spec-kitty implement`` CLI, which additionally
  needs a seeded ``lanes.json``/task board unrelated to this remedy.
* ``mission_record_analysis.py::_resolve_record_analysis_placement_ref`` —
  investigated and found NOT reachable in the unmaterialized state: it
  resolves via ``placement_seam(...).write_target(...)`` ->
  ``resolve_placement_only(..., for_write=True)``, and the WRITE-shaped
  status-surface leg (``resolve_status_surface_with_anchor``) composes the
  coord path DIRECTLY for ``UNMATERIALIZED`` instead of raising (only
  ``DELETED`` still hard-fails there). So this site's ``placement_ref is
  None`` branch is deleted/never-created ONLY — NOT a case here (confirmed by
  running it directly: the dirty-tree preflight, not
  ``PlacementResolutionRequired``, was what actually fired). Its remedy text
  is corrected for the deleted/never-created command and pinned by
  ``test_record_analysis_placement.py``.
* ``implement.py``'s own inline ``PlacementResolutionRequired`` raise (inside
  ``_commit_planning_artifacts_transaction``, the known SC-002 duplicate of
  ``_resolve_claim_commit_target``) raises the byte-identical text (proven by
  ``test_implement_writeside.py``) via the SAME
  ``doctor coordination --fix`` command already round-trip-proven by the
  ``doctor_finding`` case above, so a second full-CLI round trip through it
  would exercise the identical fixer a second time without covering any new
  remedy text or command.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mission_runtime import ActionContextError, CommitTarget, MissionArtifactKind, MissionTopology, placement_seam
from mission_runtime.write_target_degrade import assert_coord_write_materialized
from specify_cli.coordination.surface_resolver import CoordinationWorktreeUnmaterialized
from specify_cli.coordination.workspace import CoordinationWorkspace
from tests.integration.test_placement_partition_golden_path import (
    _create_mission,
    _init_git_repo,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_CMD_RE = re.compile(r"`(spec-kitty doctor coordination --mission \S+ --fix)`")

#: Every backticked substring, in appearance order (the ordered-step
#: extraction for a multi-step remedy, e.g. the remote-only arm).
_BACKTICK_RE = re.compile(r"`([^`]+)`")


def _extract_command(text: str) -> list[str]:
    """Pull the backticked materializing ``doctor coordination --fix`` command
    out of *text* (one shared regex).

    Several emitters' text carries OTHER backticked ``spec-kitty …`` commands
    too (e.g. ``surface_resolver``'s own ``spec-kitty agent decision open``
    self-materialization example) -- this regex targets the specific FR-014
    remedy command, never just "the first backtick".
    """
    match = _CMD_RE.search(text)
    assert match, f"no backticked `spec-kitty doctor coordination --mission <slug> --fix` command found in: {text!r}"
    return match.group(1).split()


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _mid8_for(repo: Path, mission_slug: str) -> str:
    meta = json.loads((repo / "kitty-specs" / mission_slug / "meta.json").read_text(encoding="utf-8"))
    return str(meta["mission_id"])[:8]


def _worktree_path(repo: Path, mission_slug: str) -> Path:
    worktree: Path = CoordinationWorkspace.worktree_path(repo, mission_slug, _mid8_for(repo, mission_slug))
    return worktree


def _fresh_unmaterialized_coord_mission(tmp_path: Path, name: str) -> tuple[Path, str]:
    """A fresh COORD-topology Mission whose branch exists but worktree does not.

    A FRESH Mission per case: each case gets its OWN repo/slug so a
    materialization side effect in one case can never leak into another.
    """
    repo = tmp_path / name
    repo.mkdir()
    _init_git_repo(repo)
    slug = f"{name}-mission".replace("_", "-")
    result = _create_mission(repo, slug, MissionTopology.COORD)
    _unmaterialize_coord_worktree(repo, result.mission_slug)
    return repo, result.mission_slug


def _unmaterialize_coord_worktree(repo: Path, mission_slug: str) -> None:
    """Remove the coordination worktree create materialized, keeping the branch.

    #5440: create now seeds the status log in a materialized coordination
    worktree; remove it so the fixture keeps CoordState.UNMATERIALIZED.
    """
    _git(repo, "worktree", "remove", "--force", str(_worktree_path(repo, mission_slug)))


# ---------------------------------------------------------------------------
# Per-case triggers -- each fires the emitter through its REAL entry point and
# returns the emitted text containing the backticked remedy command.
# ---------------------------------------------------------------------------


def _run_surface_resolver(repo: Path, mission_slug: str) -> str:
    with pytest.raises(CoordinationWorktreeUnmaterialized) as excinfo:
        placement_seam(repo, mission_slug).read_dir(MissionArtifactKind.STATUS_STATE)
    return str(excinfo.value.next_step)


def _run_doctor_finding(repo: Path, mission_slug: str) -> str:
    from specify_cli.cli.commands.doctor import app as doctor_app

    result = CliRunner().invoke(doctor_app, ["coordination", "--mission", mission_slug, "--json"])
    assert result.exit_code == 0, result.output
    findings = json.loads(result.output)
    missing = [f for f in findings if f["error_code"] == "COORDINATION_WORKTREE_MISSING"]
    assert missing, findings
    return str(missing[0]["next_step"])


def _run_runtime_bridge(repo: Path, mission_slug: str) -> str:
    from runtime.next.runtime_bridge import _resolve_wp_board_action

    board = _resolve_wp_board_action(mission_slug=mission_slug, repo_root=repo)
    assert board.blocked_reason is not None, board
    assert "unmaterializ" in board.blocked_reason.lower(), board.blocked_reason
    return board.blocked_reason


def _make_stale_local_head(repo: Path, tmp_path: Path, mission_slug: str) -> str:
    """Commit an ISSUE_MATRIX artifact onto the coord branch (a STALE local
    head), without ever creating the CANONICAL coord worktree.

    Uses a THROWAWAY linked worktree at a non-``-coord`` path (so it never
    satisfies ``classify_worktree_topology``'s coord-suffix check) to commit
    onto ``coord_branch``, then removes it -- committing onto ``main``'s
    working directory in place (a plain ``git checkout``) would DELETE the
    fresh Mission's still-untracked ``meta.json`` et al. from disk, because
    git checkout drops paths tracked on the branch you're leaving but absent
    from the destination branch's tree.
    """
    coord_branch = f"kitty/mission-{mission_slug}"
    scratch = tmp_path / f"{mission_slug}-scratch-worktree"
    _git(repo, "worktree", "add", "-q", str(scratch), coord_branch)
    try:
        matrix_dir = scratch / "kitty-specs" / mission_slug
        matrix_dir.mkdir(parents=True, exist_ok=True)
        (matrix_dir / "issue-matrix.json").write_text(json.dumps({"rows": {}}), encoding="utf-8")
        _git(scratch, "add", "kitty-specs")
        _git(scratch, "commit", "-q", "-m", "seed stale coord matrix")
    finally:
        _git(repo, "worktree", "remove", "--force", str(scratch))
    return coord_branch


def _run_write_target_degrade_stale(repo: Path, tmp_path: Path, mission_slug: str) -> str:
    coord_branch = _make_stale_local_head(repo, tmp_path, mission_slug)
    with pytest.raises(ActionContextError) as excinfo:
        assert_coord_write_materialized(
            repo,
            mission_slug,
            MissionArtifactKind.ISSUE_MATRIX,
            CommitTarget(ref=coord_branch),
        )
    assert excinfo.value.code == "COORD_WRITE_SURFACE_UNMATERIALIZED"
    return str(excinfo.value)


def _run_implement_claim_commit_target(repo: Path, mission_slug: str) -> str:
    """The real ``implement()`` production resolver + fail-closed helper,
    not the private message builder read in isolation.

    ``_resolve_placement_ref`` is ``implement()``'s own call
    (``implement.py`` line ~1898: ``_resolve_placement_ref(repo_root,
    mission_slug=mission_slug, wp_id=wp_id)``) — it genuinely returns
    ``None`` on this fresh unmaterialized Mission, which is exactly the
    input ``_resolve_claim_commit_target`` fails closed on.
    """
    from specify_cli.cli.commands.implement_cores import (
        _resolve_claim_commit_target,
        _resolve_placement_ref,
    )
    from specify_cli.core.errors import PlacementResolutionRequired

    placement_ref = _resolve_placement_ref(repo, mission_slug=mission_slug, wp_id="WP01")
    assert placement_ref is None, f"expected the unmaterialized coord surface to degrade _resolve_placement_ref to None; got {placement_ref!r} instead"
    with pytest.raises(PlacementResolutionRequired) as excinfo:
        _resolve_claim_commit_target(placement_ref, mission_slug=mission_slug)
    return str(excinfo.value)


# ---------------------------------------------------------------------------
# The round trip
# ---------------------------------------------------------------------------

_CASE_NAMES = [
    "surface_resolver",
    "doctor_finding",
    "runtime_bridge",
    "write_target_degrade_stale_local_head",
    "implement_claim_commit_target",
]


@pytest.mark.parametrize("case_name", _CASE_NAMES)
def test_unmaterialized_remedy_round_trip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case_name: str,
) -> None:
    """Guards against the named command running while the worktree stays
    absent (`doctor workspaces --fix` only removes husks, #2240 -- it never
    creates one)."""
    repo, mission_slug = _fresh_unmaterialized_coord_mission(tmp_path, case_name)
    monkeypatch.chdir(repo)

    if case_name == "surface_resolver":
        text = _run_surface_resolver(repo, mission_slug)
    elif case_name == "doctor_finding":
        text = _run_doctor_finding(repo, mission_slug)
    elif case_name == "runtime_bridge":
        text = _run_runtime_bridge(repo, mission_slug)
    elif case_name == "write_target_degrade_stale_local_head":
        text = _run_write_target_degrade_stale(repo, tmp_path, mission_slug)
    else:
        assert case_name == "implement_claim_commit_target"
        text = _run_implement_claim_commit_target(repo, mission_slug)

    worktree = _worktree_path(repo, mission_slug)
    assert not worktree.exists(), "fixture setup bug: worktree already materialized"

    command = _extract_command(text)
    assert command == ["spec-kitty", "doctor", "coordination", "--mission", mission_slug, "--fix"], (
        f"expected the truthful materializing command with the real slug (no `<mission>` placeholder), got: {command!r} (from: {text!r})"
    )

    from specify_cli.cli.commands.doctor import app as doctor_app

    # ``doctor_app`` is already rooted at "doctor" -- strip "spec-kitty doctor".
    result = CliRunner().invoke(doctor_app, command[2:])
    # A non-zero exit is expected to be a plain `typer.Exit` (an ordinary
    # `error`-finding exit), never a crash. The exit CODE itself is not
    # asserted here: the fixture for the `write_target_degrade_stale_local_
    # head` case deliberately seeds the coord branch with content that
    # diverges from `target_branch`, which trips the UNRELATED Gap-1
    # coord-vs-target staleness `error` finding (fails loud, mutates nothing)
    # -- a real, working `--fix` still exits non-zero for that finding even
    # after materializing the worktree, which is the ONE thing this round
    # trip proves.
    if result.exception is not None:
        assert isinstance(result.exception, SystemExit), result.output

    assert worktree.exists(), f"the {case_name!r} remedy command did not materialize the coordination worktree: {command!r}"


def test_write_target_degrade_remote_only_round_trip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The remote-only arm's remedy is an ORDERED LIST of steps, not one command
    (the multi-step remedy): `git fetch`, create the local branch, then the doctor `--fix`
    command. Running them in order materializes the worktree; the coord
    branch has NO local head before this test runs any of them."""
    repo, mission_slug = _fresh_unmaterialized_coord_mission(tmp_path, "remote-only")
    coord_branch = f"kitty/mission-{mission_slug}"

    # Simulate a fresh clone: the coord branch exists only on `origin/<branch>`.
    remote = tmp_path / "remote-only-origin.git"
    subprocess.run(["git", "clone", "--bare", str(repo), str(remote)], check=True, capture_output=True)
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "fetch", "origin")
    _git(repo, "branch", "-D", coord_branch)

    monkeypatch.chdir(repo)
    with pytest.raises(ActionContextError) as excinfo:
        assert_coord_write_materialized(
            repo,
            mission_slug,
            MissionArtifactKind.ISSUE_MATRIX,
            CommitTarget(ref=coord_branch),
        )
    assert excinfo.value.code == "COORD_WRITE_SURFACE_UNMATERIALIZED"
    text = str(excinfo.value)

    worktree = _worktree_path(repo, mission_slug)
    assert not worktree.exists()

    # Extract EVERY backticked step from the text, IN ORDER, and run
    # exactly those (never hard-coded argv) -- had the text still said
    # `doctor workspaces --fix` as its last step, this would catch it.
    steps = _BACKTICK_RE.findall(text)
    command_steps = [s for s in steps if s.startswith(("git ", "spec-kitty "))]
    assert len(command_steps) == 3, f"expected exactly 3 ordered command steps (fetch, branch-create, doctor --fix), got {command_steps!r} from: {text!r}"
    fetch_step, branch_step, doctor_step = command_steps
    assert fetch_step.split() == ["git", "fetch"]
    assert branch_step.split() == ["git", "branch", coord_branch, f"origin/{coord_branch}"]
    assert doctor_step.split() == [
        "spec-kitty",
        "doctor",
        "coordination",
        "--mission",
        mission_slug,
        "--fix",
    ]

    # Run the extracted steps in order, exactly as named.
    subprocess.run(["git", "-C", str(repo), *fetch_step.split()[1:]], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), *branch_step.split()[1:]], check=True, capture_output=True)

    from specify_cli.cli.commands.doctor import app as doctor_app

    result = CliRunner().invoke(doctor_app, doctor_step.split()[2:])
    assert result.exit_code == 0, result.output
    assert worktree.exists()


# ---------------------------------------------------------------------------
# Other doctor-fixer tests
# ---------------------------------------------------------------------------


def test_doctor_fix_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, mission_slug = _fresh_unmaterialized_coord_mission(tmp_path, "idempotent")
    monkeypatch.chdir(repo)
    from specify_cli.cli.commands.doctor import app as doctor_app

    runner = CliRunner()
    first = runner.invoke(doctor_app, ["coordination", "--mission", mission_slug, "--fix"])
    assert first.exit_code == 0, first.output
    worktree = _worktree_path(repo, mission_slug)
    assert worktree.exists()

    second = runner.invoke(doctor_app, ["coordination", "--mission", mission_slug, "--fix"])
    assert second.exit_code == 0, second.output
    assert worktree.exists()


def test_doctor_fix_remote_only_does_not_materialize(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The `--fix` fixer must REFUSE to auto-materialize a remote-only branch —
    never crash, never silently fork a worktree from the wrong base -- and its
    warning must NOT loop the operator back to the same refused `--fix`
    command (#5113). This is the ONE test in this
    file that guards against a bare
    ``any(severity == warning)`` being satisfied by the pre-existing
    ``COORDINATION_WORKTREE_MISSING`` detector finding alone, even when the
    fixer emits nothing new."""
    repo, mission_slug = _fresh_unmaterialized_coord_mission(tmp_path, "doctor-remote-only")
    coord_branch = f"kitty/mission-{mission_slug}"

    remote = tmp_path / "doctor-remote-only-origin.git"
    subprocess.run(["git", "clone", "--bare", str(repo), str(remote)], check=True, capture_output=True)
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "fetch", "origin")
    _git(repo, "branch", "-D", coord_branch)
    meta_path = repo / "kitty-specs" / mission_slug / "meta.json"
    meta_before = meta_path.read_text(encoding="utf-8")

    monkeypatch.chdir(repo)
    from specify_cli.cli.commands.doctor import app as doctor_app

    result = CliRunner().invoke(doctor_app, ["coordination", "--mission", mission_slug, "--fix", "--json"])
    # Never a crash: the command completes and reports the state, whether or
    # not it treats the residual state as blocking overall.
    assert result.exception is None, result.output
    worktree = _worktree_path(repo, mission_slug)
    assert not worktree.exists(), "a remote-only branch must never be auto-materialized"
    # Never flattened either: a remote-only refusal is not a never-created one.
    assert meta_path.read_text(encoding="utf-8") == meta_before

    findings = json.loads(result.output)
    # Discriminating: the FIXER's own warning (not the pre-existing detector
    # finding, which is ALSO severity="warning" and would satisfy a bare
    # `any(severity == warning)`) must be present, and it must name the
    # fetch-and-branch-creation steps -- never just re-assert the same
    # `--fix` command that already refused.
    fixer_warnings = [f for f in findings if f["severity"] == "warning" and (f["message"] or "").startswith("Could not materialize the coordination worktree")]
    assert fixer_warnings, findings
    warning = fixer_warnings[0]
    next_step = warning["next_step"]
    steps = [s for s in _BACKTICK_RE.findall(next_step) if s.startswith(("git ", "spec-kitty "))]
    assert len(steps) == 3, f"expected 3 ordered backticked steps, got {steps!r} from: {next_step!r}"
    fetch_step, branch_step, doctor_step = steps
    assert "fetch" in fetch_step
    assert branch_step.split()[-3:] == ["branch", coord_branch, f"origin/{coord_branch}"]
    assert doctor_step.split() == [
        "spec-kitty",
        "doctor",
        "coordination",
        "--mission",
        mission_slug,
        "--fix",
    ]
    assert next_step.count("--fix") == 1, (
        "the remote-only warning must name --fix exactly once, as the LAST step after fetch+branch -- never as a standalone loop-back remedy"
    )


def test_missing_worktree_finding_leads_with_doctor_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo, mission_slug = _fresh_unmaterialized_coord_mission(tmp_path, "leads-with")
    monkeypatch.chdir(repo)
    from specify_cli.cli.commands.doctor import app as doctor_app

    result = CliRunner().invoke(doctor_app, ["coordination", "--mission", mission_slug, "--json"])
    assert result.exit_code == 0, result.output
    findings = json.loads(result.output)
    missing = [f for f in findings if f["error_code"] == "COORDINATION_WORKTREE_MISSING"]
    assert len(missing) == 1, findings
    finding = missing[0]

    assert finding["next_step"].startswith(f"Run: `spec-kitty doctor coordination --mission {mission_slug} --fix`"), finding["next_step"]
    assert finding["extra"]["mission_slug"] == mission_slug
    assert finding["extra"]["mid8"] == _mid8_for(repo, mission_slug)
    assert "recovery_args" in finding["extra"]


def test_missing_worktree_finding_remote_only_leads_with_ordered_steps(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#5113: the DETECTOR finding (no ``--fix``) is
    what an operator sees FIRST. For a remote-only branch it must lead with
    the truthful ORDERED fetch/branch/fix steps -- never the bare `--fix`
    command that loops -- independently of the fixer's
    own warning (``test_doctor_fix_remote_only_does_not_materialize`` only
    exercises the fixer's text, not the detector's).

    Kills MUT-A (``_check_coordination_worktree_health``: ``if is_local_head:``
    forced to ``if True:``), which every other remote-only test survives.
    """
    repo, mission_slug = _fresh_unmaterialized_coord_mission(tmp_path, "detector-remote-only")
    coord_branch = f"kitty/mission-{mission_slug}"

    remote = tmp_path / "detector-remote-only-origin.git"
    subprocess.run(["git", "clone", "--bare", str(repo), str(remote)], check=True, capture_output=True)
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "fetch", "origin")
    _git(repo, "branch", "-D", coord_branch)

    monkeypatch.chdir(repo)
    from specify_cli.cli.commands.doctor import app as doctor_app

    result = CliRunner().invoke(doctor_app, ["coordination", "--mission", mission_slug, "--json"])
    assert result.exit_code == 0, result.output
    findings = json.loads(result.output)
    missing = [f for f in findings if f["error_code"] == "COORDINATION_WORKTREE_MISSING"]
    assert len(missing) == 1, findings
    next_step = missing[0]["next_step"]

    # Extract every backticked step from the DETECTOR's own next_step,
    # in order, and assert it is EXACTLY the ordered fetch/branch/fix triple
    # -- never a bare leading `--fix` (the cycle-1 loop defect), and never
    # just re-asserting the recovery_args' `git worktree add` fallback either.
    steps = [s for s in _BACKTICK_RE.findall(next_step) if s.startswith(("git ", "spec-kitty "))]
    assert len(steps) == 3, f"expected 3 ordered steps, got {steps!r} from: {next_step!r}"
    fetch_step, branch_step, doctor_step = steps
    assert "fetch" in fetch_step
    assert branch_step.split()[-3:] == ["branch", coord_branch, f"origin/{coord_branch}"]
    assert doctor_step.split() == [
        "spec-kitty",
        "doctor",
        "coordination",
        "--mission",
        mission_slug,
        "--fix",
    ]

    worktree = _worktree_path(repo, mission_slug)
    assert not worktree.exists()

    # Round trip: run the extracted steps in order and prove they materialize.
    subprocess.run(["git", "-C", str(repo), *fetch_step.split()[1:]], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), *branch_step.split()[1:]], check=True, capture_output=True)
    fix_result = CliRunner().invoke(doctor_app, doctor_step.split()[2:])
    assert fix_result.exit_code == 0, fix_result.output
    assert worktree.exists()
