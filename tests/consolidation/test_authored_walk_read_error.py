"""#5048(b), FR-014: a history-read error in the authorship walk is never read as a deletion.

While collecting an approved lane's authored content, ``_final_authored_walk`` walks the lane's first-parent spine newest to
oldest and records, per path, the final blob or "deleted". A failed read of a path at its newest touching commit is not a
deletion: it must refuse the claim, before anything moves, naming the path. A path that is really absent at that commit is a
deletion and is still recorded as one (the positive controls below).

A real git history-read failure on exactly one path is hard to produce, so the probe is patched at its lookup home through
the reconciliation family helper, and only for the one ``(lane commit, path)`` pair the walk reads. The verifier's gate-time
reads of the target tree go through the same names; a wider fake would refuse at the gate and roll back, which can look like
the fix.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from specify_cli.consolidation.git_probes import GitProbeError
from specify_cli.consolidation.reconciliation import resolve_external_dependency_refs
from specify_cli.consolidation.reconciliation_closed_world import ExternalDependencyAttribution
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from tests.consolidation import characterization_support as cs
from tests.consolidation.reconciliation_family import family_modules_binding, setattr_reconciliation_family
from tests.terminus import rollback_harness
from tests.terminus.canceled_dependency_support import WP01_PATH, first_parent_shas
from tests.terminus.conftest import restamp_approvals_at_lane_tips
from tests.terminus.post_approval_support import lane_worktree

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

PROBES = ("blob_id_at", "path_state_at")
CLAIM_PROBE_REFUSAL = "a git probe failed while building the approved-WP claim"
NOTHING_MUTATED = "no refs/worktrees were mutated"
FORECAST_REFUSAL = "the closed-world reconciliation window could not be read"
FORECAST_FAIL_CLOSED = "the forecast cannot prove the landing is attributable (fail-closed)"
INJECTED = "injected history-read failure"
DELETED_PATH = "src/pkg/wp01_doomed.py"

Probe = Callable[[Path, str, str], "str | None"]


def _failing_probe(original: Probe, *, path: str, touch_sha: str) -> Probe:
    """A probe that raises ``GitProbeError`` for exactly ``(touch_sha, path)`` and delegates every other read."""

    def fake(repo_root: Path, ref: str, probed_path: str) -> str | None:
        if probed_path == path and ref == touch_sha:
            raise GitProbeError(f"{INJECTED} for {probed_path}")
        return original(repo_root, ref, probed_path)

    return fake


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


def _flat(text: str) -> str:
    """*text* with every whitespace run collapsed, so a console line wrap never splits an asserted phrase."""
    return " ".join(text.split())


def _lane_spine(mission: cs.ShapeMission, wp_id: str = "WP01") -> list[str]:
    return first_parent_shas(mission.repo, mission.mission_branch, mission.lane_branches[wp_id])


def _newest_touch(mission: cs.ShapeMission, path: str, wp_id: str = "WP01") -> str:
    """The newest first-parent lane commit touching *path*: the commit the walk reads *path* at."""
    spine = set(_lane_spine(mission, wp_id))
    for sha in _git(mission.repo, "rev-list", "--first-parent", mission.lane_branches[wp_id], "--", path).split():
        if sha in spine:
            return sha
    raise RuntimeError(f"fixture: no first-parent commit on the WP01 lane touches {path}")


def _require(condition: bool, message: str) -> None:
    """A fixture precondition: raises ``RuntimeError`` (never ``AssertionError``) so a broken fixture errors the test."""
    if not condition:
        raise RuntimeError(f"fixture precondition failed: {message}")


def _patch_walk_read(monkeypatch: pytest.MonkeyPatch, *, path: str, touch_sha: str) -> None:
    """Make every probe name the walk may read through fail for ``(touch_sha, path)`` only."""
    from specify_cli.consolidation import git_probes

    for name in PROBES:
        bound = family_modules_binding(name)
        _require(bool(bound), f"{name} is bound in no reconciliation family module, so a patch would never reach the walk")
        setattr_reconciliation_family(monkeypatch, name, _failing_probe(getattr(git_probes, name), path=path, touch_sha=touch_sha))


def _consolidate(mission: cs.ShapeMission) -> cs.CellResult:
    return cs.run_in_process(mission, ["consolidate", "--mission", mission.slug, "--yes"])


def _add_genuine_deletion(mission: cs.ShapeMission) -> None:
    """The WP01 lane adds :data:`DELETED_PATH`, then deletes it; review approves the new tip."""
    worktree = lane_worktree(mission.coord_mission(), "lane-a")
    target = worktree / DELETED_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("doomed = True\n", encoding="utf-8")
    _git(worktree, "add", DELETED_PATH)
    _git(worktree, "commit", "-qm", "feat: WP01 adds a helper it later drops")
    _git(worktree, "rm", "-q", DELETED_PATH)
    _git(worktree, "commit", "-qm", "refactor: WP01 drops the helper again")
    restamp_approvals_at_lane_tips(mission.coord_mission())


# --------------------------------------------------------------------------- T083: the entry point refuses, nothing moves


def test_history_read_error_refuses_the_claim_and_moves_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-014, US4-1: a failed read of P at its newest lane commit refuses at claim time, naming P, before any mutation."""
    mission = cs.build_shape(tmp_path, "single_lane")
    touch_sha = _newest_touch(mission, WP01_PATH)
    _require(_git(mission.repo, "cat-file", "-t", f"{mission.lane_branches['WP01']}:{WP01_PATH}") == "blob", f"{WP01_PATH} must exist at the lane tip")
    coordinated = mission.coord_mission()
    watched = (mission.target_branch, mission.mission_branch)
    refs_before = rollback_harness.ref_shas(coordinated)
    reflogs_before = {branch: rollback_harness.reflog_shas(coordinated, branch) for branch in watched}
    _require(rollback_harness.state_path(coordinated) is None, "no consolidation record may exist before the run")
    _patch_walk_read(monkeypatch, path=WP01_PATH, touch_sha=touch_sha)

    result = _consolidate(mission)

    output = _flat(result.output)
    assert result.exit_code == 1, result.output
    assert CLAIM_PROBE_REFUSAL in output, result.output
    assert WP01_PATH in output, f"the refusal must name the path:\n{result.output}"
    assert INJECTED in output, f"the refusal must carry the probe error:\n{result.output}"
    assert NOTHING_MUTATED in output, f"the refusal must be the claim-time, pre-mutation one:\n{result.output}"
    assert rollback_harness.ref_shas(coordinated) == refs_before, "no branch may have moved"
    reflogs_after = {branch: rollback_harness.reflog_shas(coordinated, branch) for branch in watched}
    assert reflogs_after == reflogs_before, "nothing may have been moved and rolled back (a restore leaves a reflog entry)"
    record = rollback_harness.state_path(coordinated)
    assert record is None or not json.loads(record.read_text(encoding="utf-8")).get("pre_mutation_refs"), "no pre-mutation snapshot may remain"


# --------------------------------------------------------------------------- T084: a genuine deletion is still a deletion


def test_genuine_deletion_is_still_recorded_and_lands(tmp_path: Path) -> None:
    """US4-2: a path the lane really deleted is recorded as deleted, the run lands, and the path is absent on the target."""
    mission = cs.build_shape(tmp_path, "single_lane")
    _add_genuine_deletion(mission)

    result = _consolidate(mission)

    assert result.exit_code == 0, result.output
    absent = subprocess.run(["git", "-C", str(mission.repo), "cat-file", "-e", f"{mission.target_branch}:{DELETED_PATH}"], capture_output=True, check=False)
    assert absent.returncode != 0, f"{DELETED_PATH} must not be on {mission.target_branch} after landing"
    assert _git(mission.repo, "cat-file", "-t", f"{mission.target_branch}:{WP01_PATH}") == "blob", "the lane's surviving content must land"


def test_final_authored_walk_records_an_absent_path_as_deleted(tmp_path: Path) -> None:
    """The walk records a path absent at its newest touching commit in ``deletions``, never in ``blobs``."""
    from specify_cli.consolidation.reconciliation import _final_authored_walk

    mission = cs.build_shape(tmp_path, "single_lane")
    _add_genuine_deletion(mission)

    blobs, deletions = _final_authored_walk(mission.repo, _lane_spine(mission))

    assert DELETED_PATH in deletions
    assert DELETED_PATH not in {path for path, _blob in blobs}
    assert WP01_PATH in {path for path, _blob in blobs}
    assert WP01_PATH not in deletions


def test_final_authored_walk_propagates_a_read_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed read is no deletion: the walk raises ``GitProbeError`` naming the path and the commit (#5048(b))."""
    from specify_cli.consolidation import git_probes
    from specify_cli.consolidation.reconciliation import _final_authored_walk

    mission = cs.build_shape(tmp_path, "single_lane")
    touch_sha = _newest_touch(mission, WP01_PATH)
    setattr_reconciliation_family(monkeypatch, "path_state_at", _failing_probe(git_probes.path_state_at, path=WP01_PATH, touch_sha=touch_sha))

    with pytest.raises(GitProbeError) as raised:
        _final_authored_walk(mission.repo, _lane_spine(mission))

    message = str(raised.value)
    assert WP01_PATH in message
    assert touch_sha[:10] in message
    assert INJECTED in message
    assert isinstance(raised.value.__cause__, GitProbeError), "the probe's own error must stay chained"


# --------------------------------------------------------------------------- the forecast refuses the same cause


def test_forecast_refuses_a_history_read_error_and_moves_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``consolidate --dry-run`` refuses with the forecast's own "window could not be read" text naming the path, never a clean forecast."""
    mission = cs.build_shape(tmp_path, "single_lane")
    touch_sha = _newest_touch(mission, WP01_PATH)
    coordinated = mission.coord_mission()
    refs_before = rollback_harness.ref_shas(coordinated)
    _patch_walk_read(monkeypatch, path=WP01_PATH, touch_sha=touch_sha)

    result = cs.run_in_process(mission, ["consolidate", "--mission", mission.slug, "--dry-run"])

    output = _flat(result.output)
    assert result.exit_code == 1, result.output
    assert FORECAST_REFUSAL in output, result.output
    assert FORECAST_FAIL_CLOSED in output, result.output
    assert WP01_PATH in output and INJECTED in output, f"the forecast must name the path and carry the probe error:\n{result.output}"
    assert rollback_harness.ref_shas(coordinated) == refs_before, "a dry run moves nothing"


# --------------------------------------------------------------------------- the declared-ref walk refuses the same cause

DEP_BRANCH = "dep-branch"
DEP_PATH = "src/dep/mod0.py"
MISSION_BRANCH = "kitty/mission-test-01M6771A"


def _repo_git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


def _commit_file(repo: Path, path: str, content: str) -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _repo_git(repo, "add", path)
    _repo_git(repo, "commit", "-qm", f"add {path}")


def _declared_ref_repo(tmp_path: Path) -> tuple[Path, str, LanesManifest]:
    """A base, one external dependency commit, and a lane that merged it: the minimal declared-ref shape (#6771)."""
    repo = tmp_path / "declared-ref-repo"
    repo.mkdir()
    _repo_git(repo, "init", "-q", "-b", "main")
    _repo_git(repo, "config", "user.name", "Test")
    _repo_git(repo, "config", "user.email", "test@example.com")
    _commit_file(repo, "src/app.py", "VALUE = 0\n")
    base = _repo_git(repo, "rev-parse", "HEAD")
    _repo_git(repo, "checkout", "-q", "-b", DEP_BRANCH, base)
    _commit_file(repo, DEP_PATH, "DEP = 0\n")
    _repo_git(repo, "checkout", "-q", "-b", "lane-a", base)
    _commit_file(repo, "src/lane.py", "LANE = 1\n")
    _repo_git(repo, "merge", "-q", "--no-ff", "--no-edit", DEP_BRANCH)
    _repo_git(repo, "branch", MISSION_BRANCH, "lane-a")
    lane = ExecutionLane(
        lane_id="lane-a",
        wp_ids=("WP01",),
        write_scope=("src/lane.py",),
        predicted_surfaces=("code",),
        depends_on_lanes=(),
        parallel_group=0,
    )
    manifest = LanesManifest(
        version=1,
        mission_slug="test-01M6771A",
        mission_id=None,
        mission_branch=MISSION_BRANCH,
        target_branch="main",
        lanes=[lane],
        computed_at="2026-10-30T00:00:00Z",
        computed_from="test",
    )
    return repo, base, manifest


def _resolve_declared(repo: Path, base: str, manifest: LanesManifest) -> ExternalDependencyAttribution:
    return resolve_external_dependency_refs(
        repo,
        refs=(DEP_BRANCH,),
        window_base=base,
        mission_branch=manifest.mission_branch,
        lanes_manifest=manifest,
        coord_base_ref=base,
    )


def test_declared_ref_walk_read_error_is_dependency_ref_unverifiable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed read inside the declared ref's authored walk refuses ``DEPENDENCY_REF_UNVERIFIABLE`` and exempts nothing.

    Before WP16 the same failed read was recorded as a deletion of the dependency's path, which a later squash axis would
    have treated as inherited history.
    """
    from specify_cli.consolidation import git_probes

    repo, base, manifest = _declared_ref_repo(tmp_path)
    clean = _resolve_declared(repo, base, manifest)
    _require(clean.refusal is None and bool(clean.shas), "fixture: the untouched declaration must verify and exempt the dependency commit")
    dep_commit = _repo_git(repo, "rev-parse", DEP_BRANCH)
    setattr_reconciliation_family(monkeypatch, "path_state_at", _failing_probe(git_probes.path_state_at, path=DEP_PATH, touch_sha=dep_commit))

    attribution = _resolve_declared(repo, base, manifest)

    assert attribution.refusal is not None
    refusal = _flat(attribution.refusal)
    assert "Error code: DEPENDENCY_REF_UNVERIFIABLE." in refusal
    assert f"verifying external dependency ref '{DEP_BRANCH}'" in refusal
    assert DEP_PATH in refusal and INJECTED in refusal
    assert (attribution.shas, attribution.blobs, attribution.deletions) == (frozenset(), frozenset(), frozenset()), "a refused declaration exempts nothing"
