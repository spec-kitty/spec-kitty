"""``consolidate`` consults origin before it lands anything (#5780, ADR 2026-07-17-1).

#5780 (P0): a teammate rejects WP02 in their clone and pushes the status event;
the operator's clone still holds the approval, so ``spec-kitty consolidate``
lands the rejected WP. Every arm drives the REAL CLI over real git with a real
bare remote and a second clone that pushes ahead of the operator's clone (A).

The check refuses with ``ORIGIN_STATUS_STALE`` / ``ORIGIN_LANE_STALE`` /
``ORIGIN_UNREACHABLE`` before any branch moves; ``--origin-check warn`` and
``SPEC_KITTY_ORIGIN_CHECK=warn`` downgrade to a warning naming the source.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.consolidation.state import ConsolidationState, get_state_path, save_state
from specify_cli.coordination.workspace import CoordinationWorkspace
from tests.terminus.conftest import CoordMission, _event, build_coord_mission, git_rev, run_terminus
from tests.terminus.lanes_fixture import build_lanes_mission
from tests._support.two_clone import attach_and_push, clone_from, isolated_git_env, make_bare_remote, unreachable_remote

pytestmark = [pytest.mark.regression, pytest.mark.integration, pytest.mark.git_repo]

_STATUS_LOG = "status.events.jsonl"
_UNRELATED = "src/unrelated.py"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _remote_tip(bare: Path, branch: str) -> str:
    return _git(bare, "rev-parse", f"refs/heads/{branch}")


def _publish(m: CoordMission, tmp_path: Path, *, head: str) -> Path:
    """Push every mission ref of *m* to a new bare remote ``origin`` and return it."""
    bare = make_bare_remote(tmp_path)
    _git(bare, "symbolic-ref", "HEAD", f"refs/heads/{head}")
    refs = list(dict.fromkeys([m.target_branch, m.coord_branch, *m.lane_branches.values()]))
    attach_and_push(m.repo, bare, refs)
    return bare


def _teammate_clone(bare: Path, tmp_path: Path, branch: str) -> Path:
    clone = clone_from(bare, tmp_path / "clone-b")
    _git(clone, "checkout", "-q", "-B", branch, f"origin/{branch}")
    return clone


def _push_rejection(m: CoordMission, bare: Path, tmp_path: Path, branch: str) -> None:
    """In clone B append a WP02 ``approved -> planned`` event to *branch* and push it."""
    clone = _teammate_clone(bare, tmp_path, branch)
    event = _event(m, "WP02", "approved", "planned")
    event.update({"force": True, "reason": "teammate rejected WP02", "actor": "reviewer-renata"})
    log = clone / "kitty-specs" / m.slug / _STATUS_LOG
    log.write_text(log.read_text(encoding="utf-8") + json.dumps(event, sort_keys=True) + "\n", encoding="utf-8")
    _git(clone, "add", str(log))
    _git(clone, "commit", "-qm", "teammate: reject WP02")
    _git(clone, "push", "-q", "origin", f"{branch}:{branch}")


def _push_commit(bare: Path, tmp_path: Path, branch: str, path: str) -> None:
    """In clone B commit *path* onto *branch* and push."""
    clone = _teammate_clone(bare, tmp_path, branch)
    target = clone / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("VALUE = 1\n", encoding="utf-8")
    _git(clone, "add", path)
    _git(clone, "commit", "-qm", f"teammate: {path}")
    _git(clone, "push", "-q", "origin", f"{branch}:{branch}")


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    isolated_git_env(monkeypatch, tmp_path)


@pytest.fixture
def coord(tmp_path: Path) -> tuple[CoordMission, Path]:
    m = build_coord_mission(tmp_path, wps=("WP01", "WP02"))
    return m, _publish(m, tmp_path, head=m.target_branch)


@pytest.fixture
def lanes(tmp_path: Path) -> tuple[CoordMission, Path]:
    m = build_lanes_mission(tmp_path, wps=("WP01", "WP02"))
    return m, _publish(m, tmp_path, head=m.target_branch)


def _consolidate(m: CoordMission, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return run_terminus(m, ["consolidate", "--mission", m.slug, *args], env=env)


def _out(result: subprocess.CompletedProcess[str]) -> str:
    """Output with whitespace collapsed: the rich console wraps long lines at 80 columns."""
    return " ".join((result.stdout + result.stderr).split())


def _assert_refused_untouched(m: CoordMission, result: subprocess.CompletedProcess[str], code: str, before: dict[str, str]) -> None:
    out = _out(result)
    assert result.returncode != 0, out
    assert code in out, out
    assert {ref: git_rev(m.repo, ref) for ref in before} == before, "a ref moved on refusal"


def _refs(m: CoordMission) -> dict[str, str]:
    return {ref: git_rev(m.repo, ref) for ref in [m.target_branch, m.coord_branch, *m.lane_branches.values()]}


# --- arm 1 + 2: coordination topology, teammate rejection on the coordination branch ----


def test_plain_consolidate_refuses_a_teammate_rejection(coord: tuple[CoordMission, Path], tmp_path: Path) -> None:
    m, bare = coord
    _push_rejection(m, bare, tmp_path, m.coord_branch)
    before = _refs(m)
    result = _consolidate(m)
    _assert_refused_untouched(m, result, "ORIGIN_STATUS_STALE", before)


def test_push_consolidate_refuses_and_pushes_nothing(coord: tuple[CoordMission, Path], tmp_path: Path) -> None:
    m, bare = coord
    _push_rejection(m, bare, tmp_path, m.coord_branch)
    before = _refs(m)
    remote_before = _remote_tip(bare, m.target_branch)
    result = _consolidate(m, "--push")
    _assert_refused_untouched(m, result, "ORIGIN_STATUS_STALE", before)
    assert _remote_tip(bare, m.target_branch) == remote_before


# --- arm 3 + 4: lanes topology (status lives on the target) -----------------------------


def test_lanes_consolidate_refuses_a_teammate_rejection(lanes: tuple[CoordMission, Path], tmp_path: Path) -> None:
    m, bare = lanes
    _push_rejection(m, bare, tmp_path, m.target_branch)
    before = _refs(m)
    result = _consolidate(m)
    _assert_refused_untouched(m, result, "ORIGIN_STATUS_STALE", before)


def test_lanes_push_names_the_origin_code_before_the_push_preflight(lanes: tuple[CoordMission, Path], tmp_path: Path) -> None:
    """SC-001 lanes + ``--push``: the code is the discriminator; the push preflight would only say "target behind"."""
    m, bare = lanes
    _push_rejection(m, bare, tmp_path, m.target_branch)
    before = _refs(m)
    remote_before = _remote_tip(bare, m.target_branch)
    result = _consolidate(m, "--push")
    _assert_refused_untouched(m, result, "ORIGIN_STATUS_STALE", before)
    assert _remote_tip(bare, m.target_branch) == remote_before


def test_target_behind_for_unrelated_commits_proceeds(lanes: tuple[CoordMission, Path], tmp_path: Path) -> None:
    """FR-015 positive control: an unrelated commit on the remote target is not a freshness failure."""
    m, bare = lanes
    _push_commit(bare, tmp_path, m.target_branch, _UNRELATED)
    result = _consolidate(m)
    assert "ORIGIN_" not in _out(result), _out(result)


# --- arm 5: control after the remedy ------------------------------------------------------


def test_after_pulling_the_coordination_worktree_the_ordinary_refusal_remains(coord: tuple[CoordMission, Path], tmp_path: Path) -> None:
    m, bare = coord
    _push_rejection(m, bare, tmp_path, m.coord_branch)
    worktree = CoordinationWorkspace.worktree_path(m.repo, m.slug, m.mid8)
    _git(worktree, "pull", "-q", "--ff-only", "origin", m.coord_branch)
    result = _consolidate(m)
    out = _out(result)
    assert result.returncode != 0, out
    assert "ORIGIN_" not in out, out
    assert "missing review approval: WP02" in out, out


# --- arm 6: stale approved lane ---------------------------------------------------------


def test_stale_approved_lane_refuses(coord: tuple[CoordMission, Path], tmp_path: Path) -> None:
    m, bare = coord
    lane = m.lane_branches["WP02"]
    _push_commit(bare, tmp_path, lane, "src/pkg/late_fix.py")
    before = _refs(m)
    result = _consolidate(m)
    _assert_refused_untouched(m, result, "ORIGIN_LANE_STALE", before)
    assert lane in _out(result)


def test_up_to_date_lane_is_not_refused(coord: tuple[CoordMission, Path]) -> None:
    m, _ = coord
    result = _consolidate(m)
    assert "ORIGIN_" not in _out(result), _out(result)
    assert result.returncode == 0, _out(result)


# --- arm 7: unreachable remote ----------------------------------------------------------


def test_unreachable_origin_refuses_and_names_the_opt_out(coord: tuple[CoordMission, Path]) -> None:
    m, _ = coord
    unreachable_remote(m.repo)
    before = _refs(m)
    result = _consolidate(m)
    _assert_refused_untouched(m, result, "ORIGIN_UNREACHABLE", before)
    assert "--origin-check warn" in _out(result)


# --- arm 8 + 9: the opt-out -------------------------------------------------------------


def test_origin_check_warn_flag_warns_and_continues(coord: tuple[CoordMission, Path], tmp_path: Path) -> None:
    m, bare = coord
    _push_rejection(m, bare, tmp_path, m.coord_branch)
    result = _consolidate(m, "--origin-check", "warn")
    out = _out(result)
    assert "ORIGIN_STATUS_STALE" in out and "source: flag" in out, out
    assert "Opt out (not recommended)" not in out, out
    assert result.returncode == 0, out


def test_origin_check_warn_environment_warns_and_names_the_environment(coord: tuple[CoordMission, Path], tmp_path: Path) -> None:
    m, bare = coord
    _push_rejection(m, bare, tmp_path, m.coord_branch)
    result = _consolidate(m, env={"SPEC_KITTY_ORIGIN_CHECK": "warn"})
    out = _out(result)
    assert "source: environment" in out, out
    assert result.returncode == 0, out


# --- arm 10: a merge record exists ------------------------------------------------------


def test_refusal_with_a_merge_record_starts_with_abort(coord: tuple[CoordMission, Path], tmp_path: Path) -> None:
    m, bare = coord
    _push_rejection(m, bare, tmp_path, m.coord_branch)
    state = ConsolidationState(mission_id=m.mission_id, mission_slug=m.slug, target_branch=m.target_branch, wp_order=["WP01", "WP02"])
    save_state(state, m.repo)
    assert get_state_path(m.repo, m.mission_id).exists()
    result = _consolidate(m, "--resume")
    out = _out(result)
    assert result.returncode != 0, out
    assert "ORIGIN_STATUS_STALE" in out, out
    record_at = out.index("A consolidation record exists")
    abort_at = out.index("spec-kitty consolidate --abort")
    update_at = out.index("git ", abort_at + 1)
    assert record_at < abort_at < update_at, out


# --- placement and pass-through on the production path -------------------------------------


def _remove_coordination_worktree(m: CoordMission) -> Path:
    worktree: Path = CoordinationWorkspace.worktree_path(m.repo, m.slug, m.mid8)
    _git(m.repo, "worktree", "remove", "--force", str(worktree))
    assert not worktree.exists()
    return worktree


def test_the_check_runs_before_the_status_dir_can_materialize_the_coordination_worktree(coord: tuple[CoordMission, Path], tmp_path: Path) -> None:
    """Placement (FR-001): ``_resolve_run_status_dir`` re-materializes a removed worktree; the refusal must come first."""
    m, bare = coord
    _push_rejection(m, bare, tmp_path, m.coord_branch)
    worktree = _remove_coordination_worktree(m)
    before = _refs(m)
    result = _consolidate(m)
    _assert_refused_untouched(m, result, "ORIGIN_STATUS_STALE", before)
    assert not worktree.exists(), "the coordination worktree was re-materialized before the origin check refused"


def test_coordination_branch_only_on_the_remote_is_left_to_the_unmaterialized_path(coord: tuple[CoordMission, Path]) -> None:
    """A coordination branch the clone never had is not an ``ORIGIN_`` refusal; the existing remedy handles it."""
    m, _ = coord
    _remove_coordination_worktree(m)
    _git(m.repo, "branch", "-D", m.coord_branch)
    _git(m.repo, "update-ref", "-d", f"refs/remotes/origin/{m.coord_branch}")
    before = {ref: git_rev(m.repo, ref) for ref in [m.target_branch, *m.lane_branches.values()]}
    result = _consolidate(m)
    out = _out(result)
    assert result.returncode != 0, out
    assert "ORIGIN_" not in out, out
    assert "unmaterialized" in out.lower() or "Create the local coordination branch" in out, out
    assert {ref: git_rev(m.repo, ref) for ref in before} == before
