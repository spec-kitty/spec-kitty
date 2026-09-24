"""Real-git committed-tree proof for the ``tracer-append`` command (WP10 / T038, FR-006).

Split out of ``test_tracer_writer.py`` (which stays pure-logic/``fast``) because
this file drives a REAL ``git`` repo via ``subprocess`` -- ``git worktree add``
for a real lane worktree, the production ``CoordinationWorkspace``/
``commit_for_mission`` machinery (no stubbed ``safe_commit``), and ``git show`` /
``git rev-parse`` on the resulting commits. Per the marker-correctness
architectural gate (``tests/architectural/test_pytest_marker_correctness.py``),
a subprocess-driven git test file MUST carry ``git_repo`` and MUST NOT carry
``fast`` -- CI selects it with ``-m git_repo``.

Proves, on committed git trees (not config/mock assertions):

1. A ``tracer-append`` invoked from a LANE worktree lands its commit on the
   COORDINATION branch (I-T1 / FR-006) -- ``git show <coord_branch>:...``
   succeeds and carries the entry.
2. The LANE branch receives **zero** new commits (its HEAD sha is byte-for-byte
   unchanged before/after) -- the literal #2980/#2549 barrier this WP closes.
3. The lane worktree's working tree stays clean (``git status --porcelain``
   empty) after the append -- the direct mechanism that previously blocked a
   subsequent ``move-task`` (a dirty lane checkout); re-driving the full
   ``move-task`` state machine is out of this WP's owned surface
   (``retrospective/`` + ``cli/commands/agent/tracer_append.py`` only).
4. Re-appending byte-identical content is a no-op: the coord branch gets no
   SECOND commit and the persisted file carries the entry line exactly once
   (I-T3 / FR-012 idempotency).
5. A blank ``--actor`` is guarded -- no commit lands anywhere (#2960).
6. AC-T1 (#4959 / WP02): an UNMATERIALIZED coord surface (branch declared +
   present in git, worktree torn down again) carrying a REAL, already
   committed ``traces/<cat>.md`` fails closed -- the coord-committed content
   stays byte-intact, never clobbered by a from-scratch header.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import typer
from click.testing import Result
from typer.testing import CliRunner
from unittest.mock import patch

from mission_runtime import MissionTopology
from specify_cli.cli.commands.agent.tracer_append import tracer_append
from specify_cli.coordination.surface_resolver import CoordinationWorktreeUnmaterialized
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.retrospective.tracer_writer import append_tracer_finding
from tests.integration.coord_topology_fixture import _build_coord_topology
from tests.integration.test_placement_partition_golden_path import (
    _create_mission,
    _init_git_repo,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

RUNNER = CliRunner()

_APP = typer.Typer()
_APP.command()(tracer_append)

_TRACER_MODULE = "specify_cli.cli.commands.agent.tracer_append"


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _git_probe(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def _create_lane_worktree(repo: Path, slug: str, *, lane_id: str = "lane-a") -> tuple[Path, str]:
    """Create a real lane branch + worktree off ``main`` (post-finalize shape)."""
    lane_branch = f"kitty/mission-{slug}-{lane_id}"
    lane_path = repo / ".worktrees" / f"{slug}-{lane_id}"
    lane_path.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "worktree", "add", "-b", lane_branch, str(lane_path), "main")
    return lane_path, lane_branch


def _invoke_from_lane(lane_path: Path, *args: str) -> Result:
    with patch(f"{_TRACER_MODULE}.locate_project_root", return_value=lane_path):
        return RUNNER.invoke(_APP, list(args))


# ---------------------------------------------------------------------------
# 1-3: lane-origin append lands on coord, zero lane commit, clean lane tree
# ---------------------------------------------------------------------------


def test_lane_origin_append_lands_on_coord_with_zero_lane_commit(tmp_path: Path) -> None:
    ctx = _build_coord_topology(tmp_path, write_husk_meta=False)
    lane_path, lane_branch = _create_lane_worktree(ctx.repo, ctx.slug)
    lane_sha_before = _git(ctx.repo, "rev-parse", lane_branch)

    result = _invoke_from_lane(
        lane_path,
        "--mission", ctx.slug,
        "--category", "tooling-friction",
        "--entry", "The daemon hung mid-decode on a 3MB payload.",
        "--actor", "claude",
        "--json",
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["kind"] == "TRACER_FILE"
    assert payload["destination_surface"] == "coord"
    assert payload["row_or_entry_ref"]
    assert payload["status"] == "committed"

    # (1) Committed-tree proof: the entry lands on the COORD ref.
    rel = f"kitty-specs/{ctx.slug}/traces/tooling-friction.md"
    coord_show = _git_probe(ctx.repo, "show", f"{ctx.coord_branch}:{rel}")
    assert coord_show.returncode == 0, (
        f"tracer entry not found on coord ref {ctx.coord_branch!r}: {coord_show.stderr}"
    )
    assert "claude" in coord_show.stdout
    assert "The daemon hung mid-decode on a 3MB payload." in coord_show.stdout

    # (2) Zero new commits on the LANE branch -- the #2980/#2549 barrier.
    lane_sha_after = _git(ctx.repo, "rev-parse", lane_branch)
    assert lane_sha_after == lane_sha_before, (
        "tracer-append must not add any commit to the lane branch; "
        f"before={lane_sha_before} after={lane_sha_after}"
    )

    # (3) The lane worktree's own working tree stays clean (the direct
    # mechanism that previously blocked a subsequent move-task).
    lane_status = _git(lane_path, "status", "--porcelain")
    assert lane_status == "", f"lane worktree must stay clean; git status:\n{lane_status}"

    # Residue cleanup: the local staging copy on the PRIMARY checkout does not
    # linger as an untracked file, and the primary checkout itself stays clean.
    staged_local = ctx.repo / "kitty-specs" / ctx.slug / "traces" / "tooling-friction.md"
    assert not staged_local.exists(), "residue cleanup must remove the staged local copy"
    primary_status = _git(ctx.repo, "status", "--porcelain", "--", "kitty-specs")
    assert primary_status == "", (
        f"primary checkout's kitty-specs/ must stay clean; git status:\n{primary_status}"
    )


# ---------------------------------------------------------------------------
# 4: idempotent re-append (I-T3 / FR-012)
# ---------------------------------------------------------------------------


def test_identical_reappend_is_a_no_op_no_duplicate(tmp_path: Path) -> None:
    ctx = _build_coord_topology(tmp_path, write_husk_meta=False)
    lane_path, _lane_branch = _create_lane_worktree(ctx.repo, ctx.slug)

    args = (
        "--mission", ctx.slug,
        "--category", "approach",
        "--entry", "Adopted the seam over a bespoke commit path.",
        "--actor", "architect-alphonso",
        "--json",
    )

    first = _invoke_from_lane(lane_path, *args)
    assert first.exit_code == 0, first.output
    first_payload = json.loads(first.output)
    assert first_payload["status"] == "committed"

    coord_sha_after_first = _git(ctx.repo, "rev-parse", ctx.coord_branch)

    second = _invoke_from_lane(lane_path, *args)
    assert second.exit_code == 0, second.output
    second_payload = json.loads(second.output)
    assert second_payload["status"] == "unchanged"
    assert second_payload["row_or_entry_ref"] == first_payload["row_or_entry_ref"]

    coord_sha_after_second = _git(ctx.repo, "rev-parse", ctx.coord_branch)
    assert coord_sha_after_second == coord_sha_after_first, (
        "an identical re-append must not create a second commit on the coord branch"
    )

    rel = f"kitty-specs/{ctx.slug}/traces/approach.md"
    content = _git(ctx.repo, "show", f"{ctx.coord_branch}:{rel}")
    assert content.count("Adopted the seam over a bespoke commit path.") == 1, (
        "the entry must appear exactly once -- a re-append must not duplicate it"
    )


# ---------------------------------------------------------------------------
# 5: blank --actor is guarded, never a blanked commit (#2960)
# ---------------------------------------------------------------------------


def test_blank_actor_guarded_no_commit_lands_anywhere(tmp_path: Path) -> None:
    ctx = _build_coord_topology(tmp_path, write_husk_meta=False)
    lane_path, lane_branch = _create_lane_worktree(ctx.repo, ctx.slug)
    lane_sha_before = _git(ctx.repo, "rev-parse", lane_branch)

    result = _invoke_from_lane(
        lane_path,
        "--mission", ctx.slug,
        "--category", "tooling-friction",
        "--entry", "should never be persisted",
        "--actor", "   ",
        "--json",
    )

    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["ok"] is False
    assert "actor" in payload["error"].lower() or "attribution" in payload["error"].lower()

    # No commit landed anywhere: the coord branch never even got a tracer file.
    rel = f"kitty-specs/{ctx.slug}/traces/tooling-friction.md"
    coord_show = _git_probe(ctx.repo, "show", f"{ctx.coord_branch}:{rel}")
    assert coord_show.returncode != 0, (
        "a blank actor must never produce a committed (blank-attributed) entry"
    )
    lane_sha_after = _git(ctx.repo, "rev-parse", lane_branch)
    assert lane_sha_after == lane_sha_before


# ---------------------------------------------------------------------------
# 6: AC-T1 (#4959 / WP02) -- unmaterialised coord fails closed, no clobber
# ---------------------------------------------------------------------------


class _FixedPolicy:
    """Duck-typed ``is_protected(ref) -> bool`` stub -- fixed "never protected"
    answer, matching the pure-logic test module's ``_policy()`` shape."""

    def is_protected(self, ref: str) -> bool:  # noqa: ARG002 - fixed-answer stub
        return False


def _build_unmaterialized_coord_mission_with_populated_traces(
    tmp_path: Path, *, category_filename: str, original_content: str
) -> tuple[Path, str, str]:
    """A real COORD-topology mission whose coordination branch already carries
    a committed, populated ``traces/<cat>.md`` -- but whose coord worktree is
    torn back down (``CoordState.UNMATERIALIZED``: branch declared + present
    in git, worktree absent on disk). This is the exact #4959 danger window:
    real findings exist on the coord branch while the local worktree is not
    (yet, or no longer) materialised.

    Returns ``(repo, mission_slug, coordination_branch)``.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo, branch="main")
    result = _create_mission(repo, "unmat-tracer-demo", MissionTopology.COORD)
    coordination_branch = result.coordination_branch
    assert coordination_branch, "fixture must mint a coordination branch"

    meta = json.loads((result.feature_dir / "meta.json").read_text(encoding="utf-8"))
    mid8 = str(meta["mission_id"])[:8]

    # Materialise ONCE to commit real, pre-existing findings onto the coord
    # branch, then tear the worktree back down -- landing on UNMATERIALIZED
    # with a genuinely populated coord-committed file (not a fixture stub).
    coord_root = CoordinationWorkspace.resolve(repo, result.mission_slug, mid8)
    coord_traces_dir = coord_root / "kitty-specs" / result.mission_slug / "traces"
    coord_traces_dir.mkdir(parents=True)
    (coord_traces_dir / category_filename).write_text(
        original_content, encoding="utf-8"
    )
    _git(coord_root, "add", ".")
    _git(coord_root, "commit", "-m", "seed: pre-existing tracer finding")
    CoordinationWorkspace.teardown(repo, result.mission_slug, mid8)
    assert not coord_root.exists(), (
        "fixture invariant violated: coord worktree must be torn down "
        "(unmaterialized) for this scenario"
    )

    return repo, result.mission_slug, coordination_branch


def test_unmaterialized_coord_tracer_append_fails_closed_and_preserves_findings(
    tmp_path: Path,
) -> None:
    """AC-T1: an UNMATERIALIZED coord surface with a REAL, already-committed
    ``traces/<cat>.md`` must be left byte-intact when ``tracer-append`` is
    invoked -- the write fails closed (raises) instead of silently clobbering
    the real findings with a from-scratch header + the new entry.

    Pre-fix (red): ``_read_current_coord_content`` swallows
    ``CoordinationWorktreeUnmaterialized`` into ``""``, the write proceeds
    (self-materialising the coord worktree at the commit boundary per
    ``commit_router``'s NFR-001), and the coord-committed file is
    OVERWRITTEN with header+new-entry-only -- the original finding is lost.
    """
    original_content = (
        "# Tracer: tooling-friction\n\n"
        "One entry per finding: `YYYY-MM-DD · actor · <text>`.\n\n"
        "---\n\n"
        "2026-01-01 · architect-alphonso · The daemon hung mid-decode on a 3MB payload.\n"
    )
    repo, slug, coord_branch = _build_unmaterialized_coord_mission_with_populated_traces(
        tmp_path,
        category_filename="tooling-friction.md",
        original_content=original_content,
    )
    rel = f"kitty-specs/{slug}/traces/tooling-friction.md"

    with pytest.raises(CoordinationWorktreeUnmaterialized):
        append_tracer_finding(
            repo_root=repo,
            mission_slug=slug,
            category="tooling-friction",
            entry="A NEW finding that must never silently clobber the old one.",
            actor="claude",
            policy=_FixedPolicy(),
        )

    # (AC-T1) The coord-committed file is byte-intact -- 0 findings lost.
    coord_show = _git_probe(repo, "show", f"{coord_branch}:{rel}")
    assert coord_show.returncode == 0, (
        f"the pre-existing coord-committed file must still exist: {coord_show.stderr}"
    )
    assert coord_show.stdout == original_content, (
        "the coord-committed traces file must be byte-unchanged after a "
        "fail-closed tracer-append -- 0 findings may be lost.\n"
        f"  Expected: {original_content!r}\n"
        f"  Got     : {coord_show.stdout!r}"
    )
    assert "NEW finding" not in coord_show.stdout, (
        "a fail-closed write must never land the new entry either"
    )

    # No local staging residue on the primary checkout.
    staged_local = repo / "kitty-specs" / slug / "traces" / "tooling-friction.md"
    assert not staged_local.exists(), (
        "a fail-closed read must never materialize the local staging file"
    )
