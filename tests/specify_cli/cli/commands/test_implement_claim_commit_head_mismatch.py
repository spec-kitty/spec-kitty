"""#5738: a claim whose auto-commit cannot land on the checked-out branch is refused, visibly, up front.

The claim commit targets the mission's PRIMARY write home
(``placement_seam(...).write_target(WORK_PACKAGE_TASK)``, the target branch) and ``safe_commit``
asserts the repository root checkout's HEAD is that branch. Run from any other branch with
auto-commit on, the claim used to get all the way through allocation and the status write, then
die on ``SafeCommitHeadMismatch`` -- swallowed by ``_json_safe_output``'s generic handler, so the
command exited 1 with no error line and left a lane worktree plus uncommitted writes behind.

Every test drives the real command against a real git fixture; nothing is patched.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
import typer

from specify_cli.charter_runtime.preflight.ambient_warning import _reset_surfaced_for_testing
from specify_cli.cli.commands.implement import _json_safe_output
from tests.specify_cli.cli.commands.test_implement_characterization import (
    MISSION_ID,
    SLUG,
    Mission,
    activate_repo,
    build_mission,
    flat,
    git,
    implement_cli,
    init_repo,
    snapshot,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

COORDINATION_BRANCH = f"kitty/mission-{SLUG}-{MISSION_ID[:8].lower()}"
ARGS = ["WP01", "--mission", SLUG, "--actor", "tester"]
_ANSI = re.compile(r"\x1b\[[0-9;]*m")
PROTECTED_HINT = (
    "'main' is a protected branch, so the claim's status commit cannot land there either: "
    "rerun with --no-auto-commit to stage the claim's changes and commit them yourself."
)


@pytest.fixture(autouse=True)
def _fresh_charter_warning() -> Iterator[None]:
    _reset_surfaced_for_testing()
    yield
    _reset_surfaced_for_testing()


@pytest.fixture()
def off_target_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The #5738 reproduction: a lanes mission targeting the protected ``main``, checked out on the
    (unprotected) coordination-named branch the protected-branch preflight allows."""
    root = init_repo(tmp_path / "repo", "main")
    activate_repo(root, monkeypatch, tmp_path)
    monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)
    return root


def _seed(repo: Path, states: dict[str, str] | None = None) -> Mission:
    mission = build_mission(repo, SLUG, MISSION_ID, target="main", states=states)
    git(repo, "checkout", "-q", "-b", COORDINATION_BRANCH)
    return mission


def _mismatch_fragments(repo: Path) -> tuple[str, ...]:
    return (
        f"HEAD is '{COORDINATION_BRANCH}', expected 'main'.",
        f"Run `git -C {repo} checkout main` first.",
    )


def test_off_target_auto_commit_claim_is_refused_with_a_rendered_error_before_any_mutation(off_target_repo: Path) -> None:
    """Human mode: an ``Error:`` line names the mismatch and its remedy; nothing is mutated.

    Planted break (proven red): drop the claim-commit HEAD check from the ``allocate`` phase.
    """
    mission = _seed(off_target_repo)
    before = snapshot(mission)
    branches_before = git(off_target_repo, "branch", "--list")

    result = implement_cli(*ARGS, "--auto-commit")

    assert result.exit_code == 1, result.output
    text = flat(_ANSI.sub("", result.output))
    assert "Error:" in text
    for fragment in _mismatch_fragments(off_target_repo):
        assert fragment in text, f"{fragment!r} not in: {text}"
    assert snapshot(mission) == before
    assert git(off_target_repo, "branch", "--list") == branches_before
    assert "vcs" not in mission.meta()
    assert not (off_target_repo / ".worktrees").exists()


def test_off_target_auto_commit_claim_is_refused_in_json_mode_with_the_error_envelope(off_target_repo: Path) -> None:
    """``--json``: the command's usual ``{"status": "error", "error": ..., "wp_id": ...}`` envelope
    carries the mismatch and its remedy; nothing is mutated."""
    mission = _seed(off_target_repo)
    before = snapshot(mission)

    result = implement_cli(*ARGS, "--auto-commit", "--json")

    assert result.exit_code == 1, result.output
    # The once-per-run charter advisory (stderr) is mixed into the runner's output; the payload is
    # the one JSON line on stdout.
    (payload_line,) = [line for line in result.output.splitlines() if line.startswith("{")]
    payload = json.loads(payload_line)
    assert payload["status"] == "error"
    assert payload["wp_id"] == "WP01"
    error = flat(_ANSI.sub("", payload["error"]))
    assert "Error:" in error
    for fragment in _mismatch_fragments(off_target_repo):
        assert fragment in error, f"{fragment!r} not in: {error}"
    assert snapshot(mission) == before
    assert not (off_target_repo / ".worktrees").exists()


def test_a_protected_destination_names_the_no_auto_commit_way_out(off_target_repo: Path) -> None:
    """The checkout remedy alone loops for a protected destination: checking out ``main`` meets the
    protected-branch refusal. The refusal therefore also names ``--no-auto-commit``.

    Planted break (proven red): drop the protected-destination hint from the claim-commit HEAD check.
    """
    _seed(off_target_repo)

    result = implement_cli(*ARGS, "--auto-commit")

    assert result.exit_code == 1, result.output
    text = flat(_ANSI.sub("", result.output))
    assert PROTECTED_HINT in text, text
    for fragment in _mismatch_fragments(off_target_repo):
        assert fragment in text, f"{fragment!r} not in: {text}"


def test_an_unprotected_destination_gets_no_no_auto_commit_hint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Checking out an unprotected destination is a remedy that works, so it stays the only one named.

    Planted break (proven red): add the protected-destination hint unconditionally.
    """
    repo = init_repo(tmp_path / "repo")
    activate_repo(repo, monkeypatch, tmp_path)
    mission = build_mission(repo, SLUG, MISSION_ID)
    git(repo, "checkout", "-q", "-b", "elsewhere")
    before = snapshot(mission)

    result = implement_cli(*ARGS, "--auto-commit")

    assert result.exit_code == 1, result.output
    text = flat(_ANSI.sub("", result.output))
    assert "HEAD is 'elsewhere', expected 'trunk'." in text
    assert f"Run `git -C {repo} checkout trunk` first." in text
    assert "--no-auto-commit" not in text
    assert snapshot(mission) == before


def test_off_target_claim_without_auto_commit_is_not_refused(off_target_repo: Path) -> None:
    """The refusal is scoped to the auto-commit: ``--no-auto-commit`` commits nothing, so it proceeds."""
    _seed(off_target_repo)

    result = implement_cli(*ARGS, "--no-auto-commit")

    assert result.exit_code == 0, result.output
    assert (off_target_repo / ".worktrees" / f"{SLUG}-lane-a").is_dir()


def test_off_target_resume_of_an_in_progress_wp_is_not_refused(off_target_repo: Path) -> None:
    """A resume moves no lane, so no claim commit is attempted and nothing is refused.

    Planted break (proven red): drop the lane condition from the claim-commit HEAD check.
    """
    mission = _seed(off_target_repo, states={"WP01": "in_progress"})
    events_before = mission.event_count()

    result = implement_cli("WP01", "--mission", SLUG, "--actor", "system", "--auto-commit")

    assert result.exit_code == 0, result.output
    assert mission.event_count() == events_before
    assert git(off_target_repo, "rev-parse", "--abbrev-ref", "HEAD") == COORDINATION_BRANCH


# ---------------------------------------------------------------------------
# The generic handler of ``_json_safe_output``: never silent, exit code kept.
# ---------------------------------------------------------------------------


@_json_safe_output
def _raises_unexpected(wp_id: str, json_output: bool = False) -> None:
    raise RuntimeError(f"unexpected failure for {wp_id}; run `fix-it` first")


def test_an_unexpected_exception_is_rendered_in_human_mode(capsys: pytest.CaptureFixture[str]) -> None:
    """Planted break (proven red): remove the human-mode ``Error:`` print from the generic handler."""
    with pytest.raises(typer.Exit) as excinfo:
        _raises_unexpected("WP07")

    assert excinfo.value.exit_code == 1
    assert isinstance(excinfo.value.__cause__, RuntimeError)
    out = flat(_ANSI.sub("", capsys.readouterr().out))
    assert "Error: unexpected failure for WP07; run `fix-it` first" in out


def test_an_unexpected_exception_is_rendered_as_the_json_error_envelope(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(typer.Exit) as excinfo:
        _raises_unexpected("WP07", json_output=True)

    assert excinfo.value.exit_code == 1
    lines = capsys.readouterr().out.strip().splitlines()
    assert json.loads(lines[-1]) == {"status": "error", "error": "unexpected failure for WP07; run `fix-it` first", "wp_id": "WP07"}


# ---------------------------------------------------------------------------
# The check refuses only an off-target checkout: claims run from the claim commit's
# destination go through on every topology (N-2).
# ---------------------------------------------------------------------------


#: A coordination-topology mission: the slug embeds its mid8, as ``agent mission create`` names it.
COORD_SLUG = f"{SLUG}-{MISSION_ID[:8].lower()}"
COORD_MISSION_BRANCH = f"kitty/mission-{COORD_SLUG}"


@pytest.mark.parametrize("topology", ["coord", "lanes_with_coord"])
def test_a_coordination_topology_claim_from_the_destination_is_not_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, topology: str) -> None:
    """The claim commit's destination is the PRIMARY target, never the coordination branch: an
    auto-commit claim run from the target checkout goes through, its status transition lands on
    the coordination branch and the claim commit on the target.

    Planted break (proven red): judge the HEAD against the coordination branch instead of the
    claim commit's destination.
    """
    repo = init_repo(tmp_path / "repo")
    activate_repo(repo, monkeypatch, tmp_path)
    build_mission(repo, COORD_SLUG, MISSION_ID, topology=topology, meta_extra={"coordination_branch": COORD_MISSION_BRANCH})
    # The coordination branch and its worktree carry the finalized status, as finalize-tasks leaves them.
    git(repo, "branch", COORD_MISSION_BRANCH)
    git(repo, "worktree", "add", "-q", f".worktrees/{COORD_SLUG}-coord", COORD_MISSION_BRANCH)

    result = implement_cli("WP01", "--mission", COORD_SLUG, "--actor", "tester", "--auto-commit")

    assert result.exit_code == 0, result.output
    assert "HEAD is" not in flat(result.output)
    assert git(repo, "rev-parse", "--abbrev-ref", "HEAD") == "trunk"
    assert git(repo, "log", "-1", "--format=%s", "trunk") == "chore: WP01 claimed for implementation"
    assert git(repo, "log", "-1", "--format=%s", COORD_MISSION_BRANCH) == "chore(spec-kitty): status transition batch WP01"


def test_a_protected_single_branch_claim_from_the_minted_mission_branch_is_not_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A ``single_branch`` mission on the protected ``main`` writes to its minted mission branch: an
    auto-commit claim run from that branch goes through and commits the claim there.

    Planted break (proven red): judge the HEAD against the target branch instead of the claim
    commit's destination.
    """
    repo = init_repo(tmp_path / "repo", "main")
    activate_repo(repo, monkeypatch, tmp_path)
    monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)
    build_mission(repo, SLUG, MISSION_ID, topology="single_branch", target="main", meta_extra={"mission_branch": COORDINATION_BRANCH})
    git(repo, "checkout", "-q", "-b", COORDINATION_BRANCH)

    result = implement_cli(*ARGS, "--auto-commit")

    assert result.exit_code == 0, result.output
    assert "HEAD is" not in flat(result.output)
    assert git(repo, "log", "-1", "--format=%s", COORDINATION_BRANCH) == "chore: WP01 claimed for implementation"
    assert git(repo, "log", "-1", "--format=%s", "main") != "chore: WP01 claimed for implementation"
