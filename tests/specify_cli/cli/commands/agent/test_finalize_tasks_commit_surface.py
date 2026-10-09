"""WP00 / FR-009(e) / site #14: the finalize-tasks COMMIT resolves target_branch.

The live dogfood repro (``research/dogfood-finalize-tasks-repro.md``):
``finalize-tasks`` REFUSED to commit its planning artifacts —

    Refusing to commit planning artifacts to the protected branch 'main'.

— because its commit path resolved the planning-commit surface to the protected repo
primary ``main`` instead of the mission's ``target_branch`` (``feat/...``). The
``finalize_tasks`` body commits the TASKS_INDEX artifact through the canonical
``commit_for_mission`` entry point (``mission.py`` ~line 3927, ``kind=TASKS_INDEX``).
``commit_for_mission`` resolves the placement via ``resolve_placement_only`` /
``_resolve_mission_target_branch``, BOTH of which read ``get_feature_target_branch``
internally. Under coord topology that resolver anchored on the coord candidate (no
``meta.json``) and fell back to ``main`` → the placement landed on protected ``main``
→ the #2106 FR-008 guard correctly refused. The resolution to ``main`` is the bug.

This drives the REAL commit machinery the finalize-tasks body uses (``commit_for_mission``
with the SAME ``kind=TASKS_INDEX``), NOT a private resolver. On the unfixed
``get_feature_target_branch`` it is RED (the commit is refused with the protected-``main``
diagnostic / the placement resolves ``main``); after re-pointing the resolver onto the
PRIMARY surface it is GREEN (the TASKS_INDEX placement / commit lands on ``target_branch``).
The #2106 protected-primary guard is preserved — the fix is the resolution, not the guard.

Uses git (a real coordination worktree is needed to reproduce the bug).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
import typer

from mission_runtime import MissionArtifactKind, MissionTopology, resolve_placement_only
from specify_cli.coordination.commit_router import commit_for_mission
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.git.protection_policy import ProtectionPolicy
from specify_cli.lanes.persistence import read_lanes_json
from tests._factories.coord_mission import COORD_TOPOLOGIES, CoordMission, make_coord_mission

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

MISSION_SLUG = "gate-read-surface-completion"
MID8 = "01KVW9B0"  # 8-char Crockford base32 mid8 (= mission_id[:8])
MISSION_ID = "01KVW9B0XFXPKTBE77QT3KRSW8"  # 26-char ULID
MISSION_DIRNAME = f"{MISSION_SLUG}-{MID8}"  # composed primary dir — never bare slug
COORD_BRANCH = f"kitty/mission-{MISSION_DIRNAME}"
TARGET = "feat/gate-read-surface-completion"
PROTECTED_REFUSAL = "Refusing to commit planning artifacts to the protected branch"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _set_origin_head_main(repo: Path) -> None:
    """Pin ``origin/HEAD`` → ``main`` so the resolver's primary fallback is ``main``.

    Production-shaped: a real clone has ``origin/HEAD`` set, so a buggy resolver falls
    back to the protected repo primary ``main`` even while the operator stands on
    ``feat`` (the dogfood state). Without it the fixture would fall through to the
    current branch and mask the bug.
    """
    _git(repo, "update-ref", "refs/remotes/origin/main", "refs/heads/main")
    _git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")


@pytest.fixture
def coord_repo(tmp_path: Path) -> Path:
    """Coord-topology mission on a non-protected feature branch.

    The primary checkout carries ``meta.json`` (``target_branch=feat/...``); the
    materialized coordination worktree's mission dir carries only the status surface
    (NO ``meta.json``). The working checkout is ``feat`` — exactly the live dogfood
    state (spec/plan committed to ``feat`` fine; finalize-tasks then refused).
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")

    feature_dir = repo / "kitty-specs" / MISSION_DIRNAME
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": MISSION_SLUG,
                "mission_id": MISSION_ID,
                "mid8": MID8,
                "coordination_branch": COORD_BRANCH,
                "target_branch": TARGET,
                "merge_target_branch": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "seed mission")
    _set_origin_head_main(repo)

    # Coord branch carries the mission dir without meta.json (the real shape).
    _git(repo, "checkout", "-q", "-b", COORD_BRANCH)
    (feature_dir / "meta.json").unlink()
    (feature_dir / "status.events.jsonl").write_text("", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "coord surface without meta")

    # Land on the mission's feature branch (where planning artifacts live), then
    # materialize the coord worktree so the topology-aware candidate prefers it.
    _git(repo, "checkout", "-q", "main")
    _git(repo, "checkout", "-q", "-b", TARGET)
    coord_worktree = CoordinationWorkspace.worktree_path(repo, MISSION_SLUG, MID8)
    _git(repo, "worktree", "add", "-q", str(coord_worktree), COORD_BRANCH)
    return repo


def test_finalize_tasks_index_placement_resolves_target_branch(coord_repo: Path) -> None:
    """The TASKS_INDEX placement (what finalize-tasks commits) resolves target_branch.

    RED on the unfixed resolver (placement.ref == 'main'); GREEN after re-pointing
    ``get_feature_target_branch`` onto the primary surface (placement.ref == feat/...).
    """
    placement = resolve_placement_only(coord_repo, MISSION_DIRNAME, kind=MissionArtifactKind.TASKS_INDEX)
    assert placement.ref == TARGET, (
        f"the finalize-tasks TASKS_INDEX commit must resolve the mission's target_branch, not the protected repo primary (got {placement.ref!r})"
    )


def test_finalize_tasks_commit_lands_on_target_not_refused(coord_repo: Path) -> None:
    """Drive the real commit machinery finalize-tasks uses; commit lands on target_branch.

    ``finalize_tasks`` commits its tasks artifacts via ``commit_for_mission(...,
    kind=TASKS_INDEX)``. On the unfixed resolver the placement is the protected
    ``main`` and the commit is REFUSED with the protected-branch diagnostic
    (``no_op_wrong_surface``). After the fix the placement is ``target_branch`` and the
    commit is created there. The #2106 protected-primary guard is unchanged.
    """
    feature_dir = coord_repo / "kitty-specs" / MISSION_DIRNAME
    tasks_file = feature_dir / "tasks.md"
    tasks_file.write_text("# Tasks\n\n- WP01\n", encoding="utf-8")

    result = commit_for_mission(
        repo_root=coord_repo,
        mission_slug=MISSION_DIRNAME,
        files=(tasks_file,),
        message=f"Add tasks for mission {MISSION_DIRNAME}",
        policy=ProtectionPolicy.resolve(coord_repo),
        kind=MissionArtifactKind.TASKS_INDEX,
        target_branch=TARGET,
    )

    # The commit must NOT be refused with the protected-main diagnostic.
    assert not (result.diagnostic and PROTECTED_REFUSAL in result.diagnostic), f"finalize-tasks commit was refused on protected main: {result.diagnostic!r}"
    # The placement landed on the mission's target_branch (not protected main).
    assert result.placement_ref == TARGET, f"finalize-tasks commit landed on {result.placement_ref!r}, expected {TARGET!r}"
    assert result.status == "committed", f"expected a real commit on {TARGET}, got status={result.status!r} diagnostic={result.diagnostic!r}"


# ---------------------------------------------------------------------------
# WP15 (coord-artifact-single-home-01M3V4BE): T079 red-first reproductions
# against a REAL coordination-routed Mission (tests._factories.coord_mission),
# driving the REAL finalize_tasks entry point end to end (no mocked
# commit_for_mission / bootstrap_canonical_state) — R10, R11 (finalize half),
# R17, the planning-pin "unchanged" control, US5.3 (both legs), and US2.2.
# ---------------------------------------------------------------------------

SEAM = "specify_cli.cli.commands.agent.mission_finalize"
_WP_FIXTURE_SLUG = "WP01"
_FR_FIXTURE = "FR-001"


def _write_coord_finalize_fixture(coord: CoordMission) -> None:
    """Scaffold a minimal, uncommitted spec/tasks for *coord* (two disjoint-owned WPs).

    Mirrors ``test_feature_finalize_bootstrap.py::_setup_lane_based_feature``'s
    proven shape (two WPs owning disjoint files -> ``compute_lanes`` yields
    real lanes). Each WP owns TWO files sharing a directory (never a single
    ``owned_files`` entry): ``infer_authoritative_surface``'s single-entry
    branch appends a trailing ``/`` (treating a lone literal path as a
    directory prefix), which then fails its own
    ``validate_authoritative_surface`` prefix check against that same literal
    path (a pre-existing inference quirk, out of this WP's scope — the
    existing ``_setup_lane_based_feature`` harness never hits it because its
    callers mock ``validate_ownership`` outright; this fixture drives the
    REAL validator end to end).

    Left UNCOMMITTED deliberately: the first ``finalize_tasks`` run's own
    commit is what lands tasks.md/the WP files/lanes.json/the bootstrapped
    status together, mirroring a real ``/spec-kitty.tasks`` -> ``finalize-tasks``
    hand-off.
    """
    mission_dir = coord.root_mission_dir
    tasks_dir = mission_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "spec.md").write_text(
        f"---\ntitle: Fixture Mission\n---\n\n## Requirements\n\n- {_FR_FIXTURE}: First requirement\n- FR-002: Second requirement\n",
        encoding="utf-8",
    )
    (mission_dir / "tasks.md").write_text(
        f"# Tasks\n\n## {_WP_FIXTURE_SLUG}\n\nNo dependencies.\n\n## WP02\n\nNo dependencies.\n",
        encoding="utf-8",
    )
    wp_specs = (
        (_WP_FIXTURE_SLUG, _FR_FIXTURE, ("src/alpha.py", "src/alpha2.py")),
        ("WP02", "FR-002", ("src/beta.py", "src/beta2.py")),
    )
    for wp_id, fr, owned in wp_specs:
        owned_yaml = "\n".join(f"  - {path}" for path in owned)
        (tasks_dir / f"{wp_id}-fixture.md").write_text(
            f'---\nwork_package_id: "{wp_id}"\ntitle: "Fixture {wp_id}"\n'
            f"requirement_refs:\n  - {fr}\n"
            f"owned_files:\n{owned_yaml}\n"
            f"dependencies: []\n---\n\n# {wp_id}\n",
            encoding="utf-8",
        )
    src_dir = coord.repo_root / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    for _wp_id, _fr, owned in wp_specs:
        for rel in owned:
            path = coord.repo_root / rel
            if not path.exists():
                path.write_text(f"# {rel}\n", encoding="utf-8")


_LAST_FINALIZE_EXIT_CODE: list[int | None] = []


def _run_real_finalize(
    monkeypatch: pytest.MonkeyPatch,
    coord: CoordMission,
    *,
    refresh: bool = False,
    allow_orphaned: bool = False,
    json_output: bool = True,
    _patch_commit_router_result: object | None = None,
) -> list[dict[str, object]]:
    """Drive the REAL ``finalize_tasks`` entry point against *coord*.

    ``_patch_commit_router_result``, when given, substitutes
    ``commit_router.commit_for_mission``'s RETURN VALUE (the router's own
    classification/partitioning still never runs) for exactly this call —
    used to deterministically exercise a refused-surface RENDERING without
    reproducing the underlying refusal's real-world timing (see
    ``test_finalize_reports_skipped_surface``). The exit code this run
    produced is recorded in :data:`_LAST_FINALIZE_EXIT_CODE` (cleared on
    every call) for callers that need it.
    """
    import contextlib

    from specify_cli.cli.commands.agent.mission_finalize import finalize_tasks

    monkeypatch.chdir(coord.repo_root)
    emitted: list[dict[str, object]] = []
    _LAST_FINALIZE_EXIT_CODE.clear()
    with contextlib.ExitStack() as stack:
        stack.enter_context(patch(f"{SEAM}._emit_json", emitted.append))
        if _patch_commit_router_result is not None:
            stack.enter_context(patch("specify_cli.coordination.commit_router.commit_for_mission", return_value=_patch_commit_router_result))
        try:
            finalize_tasks(
                feature=coord.mission_dir_name,
                json_output=json_output,
                validate_only=False,
                refresh_planning_commit=refresh,
                allow_orphaned=allow_orphaned,
            )
            _LAST_FINALIZE_EXIT_CODE.append(0)
        except typer.Exit as exc:
            _LAST_FINALIZE_EXIT_CODE.append(exc.exit_code)
        except SystemExit as exc:
            _LAST_FINALIZE_EXIT_CODE.append(int(exc.code or 0))
    return emitted


def _git_stdout(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _seed_execution_begun(coord: CoordMission, mission_dir_name: str) -> None:
    """Mint a WP-past-``planned`` status event directly on the coordination log.

    Uses the resolved WRITE location (the SAME authority finalize itself now
    uses, post-WP15) so the event lands wherever this Mission's first
    finalize run actually established the coordination surface — never a
    hand-guessed path. Stamped with the CURRENT wall-clock time: the
    wall-clock LWW reducer (``reduce_parsed``, sorting ``(at, event_id)``)
    would otherwise rank a stale hardcoded timestamp BEFORE the real
    bootstrap genesis event finalize's own first run just wrote (today's
    real time), silently losing this claim back to "planned".
    """
    from mission_runtime import MissionArtifactKind, placement_seam
    from kernel.clock import now_utc_iso
    from specify_cli.status.models import Lane, StatusEvent
    from specify_cli.status.store import append_event

    write_dir = placement_seam(coord.repo_root, mission_dir_name).write_dir(MissionArtifactKind.STATUS_STATE).path
    append_event(
        write_dir,
        StatusEvent(
            event_id="01HXYZWP15EXECUTIONBEGUNEVT",
            mission_slug=mission_dir_name,
            wp_id=_WP_FIXTURE_SLUG,
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at=now_utc_iso(),
            actor="claude-sonnet",
            force=False,
            execution_mode="worktree",
        ),
    )


def _commit_coord_worktree(coord: CoordMission, message: str) -> None:
    worktree = coord.coord_worktree_path
    _git_stdout(worktree, "add", "-A")
    _git_stdout(worktree, "commit", "-q", "-m", message)


def _success_payload(emitted: list[dict[str, object]]) -> dict[str, Any]:
    for payload in emitted:
        if payload.get("result") == "success":
            return cast("dict[str, Any]", payload)
    raise AssertionError(f"no success payload emitted: {emitted}")


def _errors(emitted: list[dict[str, object]]) -> list[str]:
    return [str(payload.get("error", "")) for payload in emitted if "error" in payload]


@pytest.mark.parametrize("topology", COORD_TOPOLOGIES)
def test_finalize_lifecycle_events_share_the_move_task_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, topology: MissionTopology) -> None:
    """US2.2: finalize's WPCreated/TasksCompleted land in the SAME coordination
    log ``move-task`` later appends to — never a second copy in the
    repository-root checkout. Red at base: ``_emit_local_canonical_events``
    writes into ``planning_dir`` (the repository-root checkout), so the two
    event kinds fork into two different logs.
    """
    coord = make_coord_mission(tmp_path, topology, slug="wp15-us22")
    _write_coord_finalize_fixture(coord)

    # Precondition: ``spec-kitty agent mission create`` (outside this WP's
    # scope -- WP21's SC-001 probe owns sweeping this residue) may ALREADY
    # have left a committed root-checkout copy of ``status.events.jsonl``
    # (MissionCreated/SpecifyStarted). Capture it before finalize runs so the
    # assertion below is "finalize added nothing new", not "no root copy can
    # ever exist" -- a stricter claim than FR-003 makes.
    root_log = coord.root_mission_dir / "status.events.jsonl"
    root_rows_before = root_log.read_text(encoding="utf-8") if root_log.exists() else None

    emitted = _run_real_finalize(monkeypatch, coord)
    success = _success_payload(emitted)
    assert success["bootstrap"]["newly_seeded"] >= 1

    coord_log = coord.coord_mission_dir / "status.events.jsonl"
    assert coord_log.exists(), "finalize's lifecycle events must land in the coordination Mission dir"
    coord_rows = [json.loads(line) for line in coord_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    coord_event_types = {row.get("event_type") for row in coord_rows}
    assert "WPCreated" in coord_event_types or any("WPCreated" in str(row) for row in coord_rows), (
        f"WPCreated must be recorded in the coordination log; rows={coord_rows}"
    )

    root_rows_after = root_log.read_text(encoding="utf-8") if root_log.exists() else None
    assert root_rows_after == root_rows_before, (
        f"finalize must add NO rows to the repository-root checkout's status log (FR-003 single home); before={root_rows_before!r} after={root_rows_after!r}"
    )
    if root_rows_after is not None:
        root_event_types = {json.loads(line).get("event_type") for line in root_rows_after.splitlines() if line.strip()}
        assert "WPCreated" not in root_event_types and "TasksCompleted" not in root_event_types and "TasksStarted" not in root_event_types, (
            f"finalize's OWN lifecycle events must never land in the root checkout; root_event_types={root_event_types}"
        )

    # move-task's own event (claim WP01) lands in the SAME log, with an
    # increasing lamport relative to the finalize-emitted rows.
    _seed_execution_begun(coord, coord.mission_dir_name)
    after_rows = [json.loads(line) for line in coord_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(after_rows) == len(coord_rows) + 1, "the claim event must append to the SAME coordination log finalize wrote"


@pytest.mark.parametrize("topology", COORD_TOPOLOGIES)
def test_finalize_sees_coord_only_lifecycle_dirt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, topology: MissionTopology) -> None:
    """R10: finalize's pre-commit dirtiness check must see COORD-only dirt.

    Precondition built directly (post-tasks squad R-M4): after the first
    finalize run establishes the coordination surface, append an EXTRA,
    UNCOMMITTED status row directly to the coordination copy of the log — the
    coordination copy is dirty, the repository-root checkout carries no
    status log at all (this Mission's whole point).

    B4 (cycle 2): this END-TO-END scenario is a sanity check, not the
    authoritative regression pin -- a full real finalize run's OWN side
    effects (bootstrap's ``materialize()`` writing a root ``status.json``; a
    re-finalize potentially rewriting ``lanes.json``) can leave the ROOT
    porcelain genuinely dirty too, so this test alone cannot distinguish
    "coordination-only dirt is honored" from "root happens to be dirty
    anyway". The authoritative, mutation-sensitive FR-007b pin is
    ``test_resolve_finalize_commit_candidates_sees_coord_only_dirt_with_clean_root``
    below, which commits every root residue first and calls
    ``_resolve_finalize_commit_candidates`` directly.
    """
    coord = make_coord_mission(tmp_path, topology, slug="wp15-r10")
    _write_coord_finalize_fixture(coord)
    _run_real_finalize(monkeypatch, coord)

    coord_log = coord.coord_mission_dir / "status.events.jsonl"
    assert coord_log.exists()
    # Precondition assertion (R-M4): the coordination copy must be clean
    # before we dirty it, so the red cannot come from a stale fixture.
    status = _git_stdout(coord.coord_worktree_path, "status", "--porcelain", "--", str(coord_log.relative_to(coord.coord_worktree_path)))
    assert status == "", f"precondition failed: coordination log must start clean; got {status!r}"

    _seed_execution_begun(coord, coord.mission_dir_name)
    status = _git_stdout(coord.coord_worktree_path, "status", "--porcelain", "--", str(coord_log.relative_to(coord.coord_worktree_path)))
    assert status != "", "precondition failed: the coordination log must be dirty after the direct append"
    # The root checkout's own status-log copy (if ``mission create`` left one
    # -- WP21's SC-001 probe owns sweeping that residue, out of this WP's
    # scope) must stay CLEAN: this WP's claim is that finalize sees the
    # COORD-only dirt, not that no root copy can ever exist.
    root_log = coord.root_mission_dir / "status.events.jsonl"
    if root_log.exists():
        root_status = _git_stdout(coord.repo_root, "status", "--porcelain", "--", str(root_log.relative_to(coord.repo_root)))
        assert root_status == "", f"precondition failed: the root checkout's status log must stay clean; got {root_status!r}"

    emitted = _run_real_finalize(monkeypatch, coord)
    success = _success_payload(emitted)
    assert success["commit_created"] is True or any(surface.get("status") == "committed" for surface in success.get("commit_surfaces", [])), (
        f"coordination-only dirt must not read as 'no changes'; success={success}"
    )

    status_after = _git_stdout(coord.coord_worktree_path, "status", "--porcelain", "--", str(coord_log.relative_to(coord.coord_worktree_path)))
    assert status_after == "", "the coordination-only dirt must have been committed to the coordination branch"


@pytest.mark.parametrize("topology", COORD_TOPOLOGIES)
def test_finalize_reports_skipped_surface(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, topology: MissionTopology) -> None:
    """R11 (finalize half): a refused surface is named, never masked.

    Drives the REAL finalize pipeline up to the commit step (real git, real
    lane computation, real bootstrap), then substitutes the router's own
    RESULT for the one call that actually lands commits
    (``commit_router.commit_for_mission``) with a synthetic
    ``CommitRouterResult`` whose top-level legacy ``status`` reads
    ``"committed"`` (the PRIMARY group landed) while its ``surfaces`` name a
    REFUSED coordination group (``STATUS_LOCK_HELD`` — the real, bounded
    refusal a genuine lock holder produces, contracts/commit-outcome.md).
    This isolates the ASSERTION under test (does finalize surface a refused
    partition, or does the legacy top-level status mask it?) from the
    inherently timing-sensitive mechanics of reproducing a real cross-process
    lock race. Red at base: ``_apply_finalize_commit_router_result`` read
    only the legacy top-level ``status``/``diagnostic`` fields, so this exact
    shape reported exit 0 with no trace of the refused coordination group.
    """
    from specify_cli.coordination.commit_outcome import PathFate, SurfaceOutcome
    from specify_cli.coordination.commit_router import CommitRouterResult

    coord = make_coord_mission(tmp_path, topology, slug="wp15-r11")
    _write_coord_finalize_fixture(coord)
    _run_real_finalize(monkeypatch, coord)
    _seed_execution_begun(coord, coord.mission_dir_name)

    # A genuine planning change, so the second run has something real to commit.
    (coord.root_mission_dir / "spec.md").write_text(
        f"---\ntitle: Fixture Mission\n---\n\n## Requirements\n\n- {_FR_FIXTURE}: First requirement (amended)\n- FR-002: Second requirement\n",
        encoding="utf-8",
    )
    _git_stdout(coord.repo_root, "add", "-A")
    _git_stdout(coord.repo_root, "commit", "-q", "-m", "planning amendment")

    synthetic_result = CommitRouterResult(
        status="committed",
        placement_ref="topic",
        commit_hash="abc1234",
        surfaces=(
            SurfaceOutcome(surface="primary", branch="topic", status="committed", commit_hash="abc1234", committed=("kitty-specs/fixture/tasks.md",)),
            SurfaceOutcome(
                surface="coordination",
                branch=f"kitty/mission-{coord.mission_dir_name}",
                status="refused",
                commit_hash=None,
                refused=(PathFate(path="status.events.jsonl", reason="STATUS_LOCK_HELD"),),
                diagnostic="status lock held by another writer",
            ),
        ),
    )

    emitted = _run_real_finalize(
        monkeypatch,
        coord,
        _patch_commit_router_result=synthetic_result,
    )
    success = _success_payload(emitted)
    surfaces = success.get("commit_surfaces", [])
    refused = [s for s in surfaces if s.get("status") == "refused"]
    assert refused, f"a refused coordination surface must be named in commit_surfaces; got {surfaces}"
    assert refused[0]["refused"][0]["reason"] == "STATUS_LOCK_HELD"
    assert _LAST_FINALIZE_EXIT_CODE and _LAST_FINALIZE_EXIT_CODE[-1] != 0, (
        f"a refused coordination surface must exit non-zero even though the legacy top-level status is 'committed'; got exit code {_LAST_FINALIZE_EXIT_CODE}"
    )


@pytest.mark.parametrize("topology", COORD_TOPOLOGIES)
def test_finalize_refreshes_planning_commit_sha_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, topology: MissionTopology) -> None:
    """R17: with no flag, a genuine PRIMARY planning change refreshes the pin.

    Red at base: ``planning_commit_sha`` stays pinned to the pre-execution
    capture forever; a legitimate planning amendment never reaches lanes.json
    without the explicit flag.
    """
    coord = make_coord_mission(tmp_path, topology, slug="wp15-r17")
    _write_coord_finalize_fixture(coord)
    _run_real_finalize(monkeypatch, coord)
    established = read_lanes_json(coord.root_mission_dir)
    assert established is not None
    recorded_tip = established.planning_commit_sha
    assert recorded_tip is not None

    _seed_execution_begun(coord, coord.mission_dir_name)
    (coord.root_mission_dir / "spec.md").write_text(
        f"---\ntitle: Fixture Mission\n---\n\n## Requirements\n\n- {_FR_FIXTURE}: First requirement (amended)\n- FR-002: Second requirement\n",
        encoding="utf-8",
    )
    _git_stdout(coord.repo_root, "add", "-A")
    new_tip = _git_stdout(coord.repo_root, "commit", "-q", "-m", "planning amendment") or _git_stdout(coord.repo_root, "rev-parse", "HEAD")

    emitted = _run_real_finalize(monkeypatch, coord)
    success = _success_payload(emitted)
    after = read_lanes_json(coord.root_mission_dir)
    assert after is not None
    assert after.planning_commit_sha == new_tip, (
        f"a no-flag re-finalize must refresh the pin by default after a genuine planning change; "
        f"planning_commit_sha went {recorded_tip!r} -> {after.planning_commit_sha!r} (expected {new_tip!r})"
    )
    refresh = success.get("planning_commit_refresh")
    assert refresh is not None and refresh.get("status") == "refreshed", f"planning_commit_refresh must report 'refreshed'; got {refresh!r}"
    # WP15 cycle 2 (C2-1): the recorded object IS present and an ancestor of
    # the tip, so it classifies ADVANCED -- the mutation "pin_class": None
    # must fail this assertion.
    assert refresh.get("pin_class") == "advanced", f"planning_commit_refresh.pin_class must report 'advanced'; got {refresh!r}"
    assert refresh.get("reason") is None, f"a successful 'refreshed' decision never names a refusal reason; got {refresh!r}"


@pytest.mark.parametrize("topology", COORD_TOPOLOGIES)
def test_finalize_keeps_planning_commit_sha_when_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, topology: MissionTopology) -> None:
    """Control for R17: no planning change -> the pin is unchanged (and stays green)."""
    coord = make_coord_mission(tmp_path, topology, slug="wp15-r17-control")
    _write_coord_finalize_fixture(coord)
    _run_real_finalize(monkeypatch, coord)
    established = read_lanes_json(coord.root_mission_dir)
    assert established is not None
    recorded_tip = established.planning_commit_sha
    assert recorded_tip is not None

    _seed_execution_begun(coord, coord.mission_dir_name)

    emitted = _run_real_finalize(monkeypatch, coord)
    success = _success_payload(emitted)
    after = read_lanes_json(coord.root_mission_dir)
    assert after is not None
    assert after.planning_commit_sha == recorded_tip, (
        f"with no planning change, the pin must stay unchanged; went {recorded_tip!r} -> {after.planning_commit_sha!r}"
    )
    refresh = success.get("planning_commit_refresh")
    assert refresh is not None and refresh.get("status") == "preserved", f"planning_commit_refresh must report 'preserved'; got {refresh!r}"
    # WP15 cycle 2 (C2-1): ADVANCED with no planning change still classifies
    # and reports ADVANCED (unlike the two kept_with_warning rows below, an
    # unchanged pin never names a refusal reason).
    assert refresh.get("pin_class") == "advanced", f"planning_commit_refresh.pin_class must report 'advanced'; got {refresh!r}"
    assert refresh.get("reason") is None, f"an unchanged/'preserved' decision never names a refusal reason; got {refresh!r}"


def test_finalize_warns_and_keeps_pin_when_auto_refresh_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """US5.3: a non-orphan refusal of the AUTOMATIC refresh warns and continues (exit 0).

    Uses a FOREIGN pin (the recorded object absent from the repository
    entirely) -- never the #4827 ORPHAN shape, which must keep failing closed
    (see ``test_issue_4827_repin_orphaned_planning_commit.py::
    test_plain_finalize_fails_closed_on_orphaned_pin``, unaffected by this
    WP). Also asserts the control: an EXPLICIT ``--refresh-planning-commit``
    against the SAME FOREIGN pin still fails (today's advance-only
    contract, unchanged).
    """
    from specify_cli.lanes.persistence import write_lanes_json

    coord = make_coord_mission(tmp_path, MissionTopology.COORD, slug="wp15-us53")
    _write_coord_finalize_fixture(coord)
    _run_real_finalize(monkeypatch, coord)
    established = read_lanes_json(coord.root_mission_dir)
    assert established is not None
    recorded_tip = established.planning_commit_sha
    assert recorded_tip is not None

    _seed_execution_begun(coord, coord.mission_dir_name)
    # A genuine planning amendment, so there IS something the automatic
    # refresh would otherwise want to advance to.
    (coord.root_mission_dir / "spec.md").write_text(
        f"---\ntitle: Fixture Mission\n---\n\n## Requirements\n\n- {_FR_FIXTURE}: First requirement (amended)\n- FR-002: Second requirement\n",
        encoding="utf-8",
    )
    _git_stdout(coord.repo_root, "add", "-A")
    _git_stdout(coord.repo_root, "commit", "-q", "-m", "planning amendment")

    # Corrupt the recorded pin into a FOREIGN SHA (never existed in this repo).
    foreign_sha = "0" * 40
    established.planning_commit_sha = foreign_sha
    write_lanes_json(coord.root_mission_dir, established)
    _git_stdout(coord.repo_root, "add", "-A")
    _git_stdout(coord.repo_root, "commit", "-q", "-m", "fixture: corrupt pin to a foreign SHA")

    # Automatic (no-flag) run: warn and continue, keep the old (foreign) pin, exit 0.
    emitted = _run_real_finalize(monkeypatch, coord)
    success = _success_payload(emitted)
    after = read_lanes_json(coord.root_mission_dir)
    assert after is not None
    assert after.planning_commit_sha == foreign_sha, (
        f"a non-orphan automatic-refresh refusal must keep the old pin; went {foreign_sha!r} -> {after.planning_commit_sha!r}"
    )
    refresh = success.get("planning_commit_refresh")
    assert refresh is not None and refresh.get("status") == "kept_with_warning", f"planning_commit_refresh must report 'kept_with_warning'; got {refresh!r}"
    # WP15 cycle 2 (C2-1): a classified FOREIGN refusal names its pin_class
    # and carries a reason (the pin_class value itself, distinct from
    # INDETERMINATE's dedicated reason code below).
    assert refresh.get("pin_class") == "foreign", f"planning_commit_refresh.pin_class must report 'foreign'; got {refresh!r}"
    assert refresh.get("reason") == "foreign", f"a FOREIGN kept_with_warning must name its reason; got {refresh!r}"

    # Control: an EXPLICIT --refresh-planning-commit against the same FOREIGN
    # pin still fails today (advance-only; a FOREIGN object cannot be
    # inspected at all).
    explicit_emitted = _run_real_finalize(monkeypatch, coord, refresh=True)
    assert _errors(explicit_emitted), f"an explicit --refresh-planning-commit must still fail against a FOREIGN pin; emitted={explicit_emitted}"
    after_explicit = read_lanes_json(coord.root_mission_dir)
    assert after_explicit is not None and after_explicit.planning_commit_sha == foreign_sha, "the explicit refusal must leave lanes.json untouched"


def test_finalize_warns_and_keeps_pin_when_recorded_sha_is_indeterminate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C2-1 (WP15 cycle 2): a legacy lanes.json with NO recorded pin classifies
    INDETERMINATE (``classify_recorded_pin`` returns INDETERMINATE whenever
    ``recorded_sha is None``) and must be a VISIBLE ``kept_with_warning``
    (exit 0), never a silent ``preserved`` -- the orchestrator's ruling on
    ``contracts/commit-outcome.md`` overrides the classifier's own
    "callers may degrade silently" docstring note for finalize specifically.
    """
    from specify_cli.lanes.persistence import write_lanes_json

    coord = make_coord_mission(tmp_path, MissionTopology.COORD, slug="wp15-c21-indeterminate")
    _write_coord_finalize_fixture(coord)
    _run_real_finalize(monkeypatch, coord)
    established = read_lanes_json(coord.root_mission_dir)
    assert established is not None

    _seed_execution_begun(coord, coord.mission_dir_name)

    # Blank the recorded pin -- the legacy "no provenance recorded" shape
    # ``test_preserve_or_capture_refresh_from_none_recorded_sha_is_a_safe_
    # advance`` already exercises for the EXPLICIT flag; here it drives the
    # AUTOMATIC (no-flag) path instead, which must classify INDETERMINATE.
    established.planning_commit_sha = None
    write_lanes_json(coord.root_mission_dir, established)
    _git_stdout(coord.repo_root, "add", "-A")
    _git_stdout(coord.repo_root, "commit", "-q", "-m", "fixture: blank the recorded pin")

    emitted = _run_real_finalize(monkeypatch, coord)
    success = _success_payload(emitted)
    after = read_lanes_json(coord.root_mission_dir)
    assert after is not None and after.planning_commit_sha is None, (
        f"an INDETERMINATE pin must stay unchanged (no SHA to advance from); got {after.planning_commit_sha!r}"
    )
    assert _LAST_FINALIZE_EXIT_CODE and _LAST_FINALIZE_EXIT_CODE[-1] == 0, (
        f"INDETERMINATE must be a non-fatal warning (exit 0), never a failure; got {_LAST_FINALIZE_EXIT_CODE}"
    )
    refresh = success.get("planning_commit_refresh")
    assert refresh is not None and refresh.get("status") == "kept_with_warning", (
        f"planning_commit_refresh must report 'kept_with_warning' for an INDETERMINATE pin, never a silent 'preserved'; got {refresh!r}"
    )
    assert refresh.get("pin_class") == "indeterminate", f"planning_commit_refresh.pin_class must report 'indeterminate'; got {refresh!r}"
    assert refresh.get("reason") == "indeterminate_tip_uncapturable", f"an INDETERMINATE kept_with_warning must name its own reason; got {refresh!r}"


# ---------------------------------------------------------------------------
# Diff-coverage closers: narrow unit tests for the remaining WP15 branches
# the end-to-end scenarios above don't reach (text-mode rendering arms, the
# ``_coord_candidate_dirt`` no-rel-files leg, the non-relative display-path
# fallback, and the non-"preserved/refreshed/kept_with_warning" refresh
# payload leg).
# ---------------------------------------------------------------------------


def test_planning_commit_refresh_payload_none_for_captured_action() -> None:
    """A pre-execution 'captured' run never populates ``planning_commit_refresh``."""
    from specify_cli.cli.commands.agent.mission_finalize import (
        PlanningCommitResolution,
        _planning_commit_refresh_payload,
    )

    captured = PlanningCommitResolution(sha="abc123", action="captured", previous_sha=None, branch_tip=None)
    assert _planning_commit_refresh_payload(captured) is None
    assert _planning_commit_refresh_payload(None) is None


def test_report_planning_sha_decision_prints_kept_with_warning_text(capsys: pytest.CaptureFixture[str]) -> None:
    """The text-mode ``kept_with_warning`` console line (US5.3, non-JSON callers)."""
    from specify_cli.cli.commands.agent.mission_finalize import (
        PlanningCommitResolution,
        _report_planning_sha_decision,
    )

    resolution = PlanningCommitResolution(sha="deadbeef", action="kept_with_warning", previous_sha="deadbeef", branch_tip="cafef00d")
    _report_planning_sha_decision("topic", resolution, json_output=False)
    output = capsys.readouterr().out
    assert "could not be safely auto-refreshed" in output
    assert "deadbeef" in output and "cafef00d" in output
    # B8 (cycle 2): the message must never recommend a remedy that is
    # guaranteed to fail for a FOREIGN pin (--allow-orphaned only lifts the
    # refusal for a proven ORPHAN, a different, inspectable shape).
    assert "--refresh-planning-commit --allow-orphaned" not in output


def test_report_planning_sha_decision_prints_indeterminate_kept_with_warning_text(capsys: pytest.CaptureFixture[str]) -> None:
    """C2-1 (WP15 cycle 3): the text-mode INDETERMINATE ``kept_with_warning``
    console line is distinct from the FOREIGN one above, and reads correctly
    even when BOTH ``previous_sha`` and ``branch_tip`` are ``None`` (exactly
    the shape that makes a pin INDETERMINATE in the first place).
    """
    from specify_cli.cli.commands.agent.mission_finalize import (
        PlanningCommitResolution,
        _report_planning_sha_decision,
    )

    resolution = PlanningCommitResolution(
        sha=None,
        action="kept_with_warning",
        previous_sha=None,
        branch_tip=None,
        pin_class="indeterminate",
        refusal_reason="indeterminate_tip_uncapturable",
    )
    _report_planning_sha_decision("topic", resolution, json_output=False)
    output = capsys.readouterr().out
    assert "could not be classified against" in output
    assert "no pin recorded yet" in output and "uncapturable" in output
    # Never the FOREIGN-specific text (a different root cause).
    assert "could not be safely auto-refreshed" not in output
    assert "object is absent from this repository" not in output


def test_finalize_candidate_display_path_falls_back_to_absolute(tmp_path: Path) -> None:
    """A candidate outside ``repo_root`` (a different worktree) renders as its absolute form."""
    from specify_cli.cli.commands.agent.mission_finalize import _finalize_candidate_display_path

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    foreign_path = tmp_path / "elsewhere" / "status.events.jsonl"
    assert _finalize_candidate_display_path(foreign_path, repo_root) == str(foreign_path)
    inside = repo_root / "kitty-specs" / "m" / "tasks.md"
    assert _finalize_candidate_display_path(inside, repo_root) == "kitty-specs/m/tasks.md"


def test_coord_candidate_dirt_skips_a_kind_directory_with_no_files(tmp_path: Path) -> None:
    """A COORD kind resolving to a directory with none of its own candidate files present
    contributes nothing to ``is_dirty`` (the ``if not rel_files: continue`` leg) while a
    SIBLING kind's directory with real dirt still flips it.
    """
    from mission_runtime import Establishment, TopologySurface, WriteLocation
    from specify_cli.cli.commands.agent.mission_finalize import _coord_candidate_dirt

    empty_dir = tmp_path / "empty-kind-dir"
    empty_dir.mkdir()
    dirty_dir = tmp_path / "dirty-kind-dir"
    dirty_dir.mkdir()
    (dirty_dir / "status.events.jsonl").write_text("{}\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=dirty_dir, check=True, capture_output=True)

    def _fake_write_dir(kind: MissionArtifactKind) -> WriteLocation:
        if kind is MissionArtifactKind.STATUS_STATE:
            return WriteLocation(path=dirty_dir, surface_root=dirty_dir, surface=TopologySurface.COORD, coord_state_before=None, establishment=Establishment.NONE)
        return WriteLocation(path=empty_dir, surface_root=empty_dir, surface=TopologySurface.COORD, coord_state_before=None, establishment=Establishment.NONE)

    mock_seam = MagicMock()
    mock_seam.write_dir.side_effect = _fake_write_dir

    with patch("mission_runtime.placement_seam", return_value=mock_seam):
        result = _coord_candidate_dirt(tmp_path, "fixture-mission", owned=None)

    assert result.is_dirty is True
    assert dirty_dir / "status.events.jsonl" in result.files


def test_coord_candidate_filenames_derive_from_the_artifact_classifier() -> None:
    """The three finalize COORD kinds list every basename the classifier maps to them.

    ``ISSUE_MATRIX`` carries BOTH the structured ``issue-matrix.json`` and the
    failover-read ``issue-matrix.md``; a hand-written map listed only the former.
    """
    from specify_cli.cli.commands.agent.mission_finalize import _COORD_CANDIDATE_KINDS, _coord_candidate_filenames

    assert set(_COORD_CANDIDATE_KINDS) == {
        MissionArtifactKind.STATUS_STATE,
        MissionArtifactKind.ISSUE_MATRIX,
        MissionArtifactKind.ACCEPTANCE_MATRIX,
    }
    assert _coord_candidate_filenames(MissionArtifactKind.STATUS_STATE) == ("status.events.jsonl", "status.json")
    assert _coord_candidate_filenames(MissionArtifactKind.ISSUE_MATRIX) == ("issue-matrix.json", "issue-matrix.md")
    assert _coord_candidate_filenames(MissionArtifactKind.ACCEPTANCE_MATRIX) == ("acceptance-matrix.json",)


def test_coord_candidate_dirt_sees_a_mission_still_on_issue_matrix_md(tmp_path: Path) -> None:
    """A mission that has not migrated off ``issue-matrix.md`` is visible to the COORD dirt probe."""
    from mission_runtime import Establishment, TopologySurface, WriteLocation
    from specify_cli.cli.commands.agent.mission_finalize import _coord_candidate_dirt

    matrix_dir = tmp_path / "issue-matrix-kind-dir"
    matrix_dir.mkdir()
    (matrix_dir / "issue-matrix.md").write_text("| issue | verdict |\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=matrix_dir, check=True, capture_output=True)
    empty_dir = tmp_path / "other-kind-dir"
    empty_dir.mkdir()

    def _fake_write_dir(kind: MissionArtifactKind) -> WriteLocation:
        directory = matrix_dir if kind is MissionArtifactKind.ISSUE_MATRIX else empty_dir
        return WriteLocation(path=directory, surface_root=directory, surface=TopologySurface.COORD, coord_state_before=None, establishment=Establishment.NONE)

    mock_seam = MagicMock()
    mock_seam.write_dir.side_effect = _fake_write_dir

    with patch("mission_runtime.placement_seam", return_value=mock_seam):
        result = _coord_candidate_dirt(tmp_path, "fixture-mission", owned=None)

    assert result.files == [matrix_dir / "issue-matrix.md"]
    assert result.is_dirty is True


def test_apply_finalize_commit_router_result_text_mode_renders_surfaces_on_unchanged(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Text mode, ``status="unchanged"`` with populated ``surfaces``: the surface lines
    render (never the bare "Tasks unchanged" fallback, which is only for the
    pre-``surfaces`` legacy empty case).
    """
    from specify_cli.coordination.commit_outcome import SurfaceOutcome
    from specify_cli.coordination.commit_router import CommitRouterResult
    from specify_cli.cli.commands.agent.mission_finalize import (
        _CommitOutcome,
        _apply_finalize_commit_router_result,
    )

    router_result = CommitRouterResult(
        status="unchanged",
        placement_ref="topic",
        surfaces=(SurfaceOutcome(surface="primary", branch="topic", status="unchanged", commit_hash=None),),
    )
    outcome = _CommitOutcome()
    _apply_finalize_commit_router_result(router_result, outcome, [], json_output=False, updated_count=0)
    output = capsys.readouterr().out
    assert "unchanged" in output
    assert outcome.commit_created is False


def test_apply_finalize_commit_router_result_text_mode_renders_surfaces_on_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Text mode, legacy-error arm: surface lines print FIRST, then the actionable
    error line -- never the bare diagnostic alone (WP13-review binding correction).
    """
    from specify_cli.coordination.commit_outcome import PathFate, SurfaceOutcome
    from specify_cli.coordination.commit_router import CommitRouterResult
    from specify_cli.cli.commands.agent.mission_finalize import (
        _CommitOutcome,
        _apply_finalize_commit_router_result,
    )

    router_result = CommitRouterResult(
        status="error",
        placement_ref="topic",
        diagnostic="boom",
        surfaces=(
            SurfaceOutcome(
                surface="coordination",
                branch="kitty/mission-x",
                status="error",
                commit_hash=None,
                refused=(PathFate(path="status.events.jsonl", reason="boom"),),
                diagnostic="boom",
            ),
        ),
    )
    outcome = _CommitOutcome()
    with pytest.raises(typer.Exit):
        _apply_finalize_commit_router_result(router_result, outcome, [], json_output=False, updated_count=0)
    output = capsys.readouterr().out
    surface_line_index = output.find("status.events.jsonl")
    error_line_index = output.find("Git commit failed")
    assert surface_line_index != -1 and error_line_index != -1
    assert surface_line_index < error_line_index, "surface lines must render BEFORE the legacy error line"


# ---------------------------------------------------------------------------
# B3 (cycle 2, HIGH, FR-003a): a named write-location refusal must fail
# finalize closed -- never a silently-swallowed "result: success" while
# WPCreated/TasksCompleted were written nowhere.
# ---------------------------------------------------------------------------


def test_finalize_fails_closed_on_remote_only_coordination_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A remote-only coordination branch refuses write_dir (COORDINATION_WORKTREE_UNMATERIALIZED).

    Before the fix, ``_emit_local_canonical_events``'s best-effort
    ``except Exception`` swallowed this refusal: finalize reported
    ``result: success`` and exited 0 while WPCreated/TasksCompleted were
    never written anywhere.
    """
    from tests._factories.coord_mission import make_prefix_coord_mission

    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, remote_only=True)
    _write_coord_finalize_fixture(coord)
    remote_tip_before = _git_stdout(coord.repo_root, "rev-parse", f"coord-remote/{coord.coordination_branch}")

    emitted = _run_real_finalize(monkeypatch, coord)

    assert not any(payload.get("result") == "success" for payload in emitted), f"a remote-only coordination branch must never report success; emitted={emitted}"
    errors = _errors(emitted)
    assert errors, f"a remote-only coordination branch must emit a clean error, not a silent swallow; emitted={emitted}"
    assert _LAST_FINALIZE_EXIT_CODE and _LAST_FINALIZE_EXIT_CODE[-1] != 0, "the refusal must exit non-zero"

    remote_tip_after = _git_stdout(coord.repo_root, "rev-parse", f"coord-remote/{coord.coordination_branch}")
    assert remote_tip_after == remote_tip_before, "nothing may be written to the coordination branch on refusal"


def test_finalize_fails_closed_on_coord_seed_fork_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A genuine fork (root and coordination status logs have diverged,
    uncommitted content on both sides) refuses ``write_dir`` with
    ``COORD_SEED_FORK_REFUSED`` -- must fail finalize closed, never swallow.
    """
    from tests._factories.coord_mission import make_fork_fixture

    fork = make_fork_fixture(tmp_path, "root_uncommitted_coord_untracked", MissionTopology.COORD, stream="status_log")
    _write_coord_finalize_fixture(fork)

    emitted = _run_real_finalize(monkeypatch, fork)

    assert not any(payload.get("result") == "success" for payload in emitted), f"a genuine fork must never report success; emitted={emitted}"
    assert _errors(emitted), f"a genuine fork must emit a clean error, not a silent swallow; emitted={emitted}"
    assert _LAST_FINALIZE_EXIT_CODE and _LAST_FINALIZE_EXIT_CODE[-1] != 0, "the refusal must exit non-zero"


# ---------------------------------------------------------------------------
# B4 (cycle 2, MEDIUM): R10 must be red for the right reason -- the root
# porcelain check for a FULL finalize run is always dirty on a
# coordination-routed Mission (bootstrap's own ``materialize()`` writes a
# root ``status.json``; a re-finalize can rewrite ``lanes.json``), which
# masks the ``has_relevant_changes = primary_dirty or coord_dirty`` mutation.
# A DIRECT unit test of ``_resolve_finalize_commit_candidates``, with every
# root PRIMARY candidate committed first, isolates the real FR-007b signal.
# ---------------------------------------------------------------------------


def test_resolve_finalize_commit_candidates_sees_coord_only_dirt_with_clean_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-007b, direct unit coverage: with every root PRIMARY candidate
    committed (clean), and ONLY the coordination copy dirty,
    ``has_relevant_changes`` must still be ``True``.

    Mutation-sensitive: changing ``has_relevant_changes=primary_dirty or
    coord_dirt.is_dirty`` to ``has_relevant_changes=primary_dirty`` must make
    this test fail (verified below by directly monkeypatching the coord-dirt
    probe to report clean, reproducing the mutation's effect).
    """
    from specify_cli.cli.commands.agent.mission_finalize import _resolve_finalize_commit_candidates

    coord = make_coord_mission(tmp_path, MissionTopology.COORD, slug="wp15-r10-unit")
    _write_coord_finalize_fixture(coord)
    _run_real_finalize(monkeypatch, coord)

    # Commit every remaining root residue so the PRIMARY porcelain check is
    # unambiguously clean (bootstrap's own materialize() can leave a root
    # status.json; a re-finalize can rewrite lanes.json -- neither is this
    # WP's concern, but both must not be allowed to mask the signal here).
    _git_stdout(coord.repo_root, "add", "-A")
    status = _git_stdout(coord.repo_root, "status", "--porcelain")
    if status:
        _git_stdout(coord.repo_root, "commit", "-q", "-m", "fixture: commit remaining root residue")
    assert _git_stdout(coord.repo_root, "status", "--porcelain") == "", "precondition failed: root checkout must be fully clean"

    _seed_execution_begun(coord, coord.mission_dir_name)
    coord_log = coord.coord_mission_dir / "status.events.jsonl"
    coord_status = _git_stdout(coord.coord_worktree_path, "status", "--porcelain", "--", str(coord_log.relative_to(coord.coord_worktree_path)))
    assert coord_status != "", "precondition failed: the coordination log must be dirty"

    planning_dir = coord.root_mission_dir
    tasks_dir = planning_dir / "tasks"
    lanes_path = planning_dir / "lanes.json"
    candidates = _resolve_finalize_commit_candidates(
        planning_dir,
        tasks_dir,
        coord.repo_root,
        lanes_path if lanes_path.exists() else None,
        mission_slug=coord.mission_dir_name,
        owned=None,
    )
    assert candidates.has_relevant_changes is True, "coordination-only dirt (root fully clean) must still be reported as a relevant change (FR-007b)"

    # Reproduce the M3 mutation's effect directly: if the coordination-dirt
    # leg were dropped from has_relevant_changes, a fully-clean root would
    # report no changes at all.
    with patch("specify_cli.cli.commands.agent.mission_finalize._coord_candidate_dirt") as mock_dirt:
        mock_dirt.return_value = SimpleNamespace(files=[], is_dirty=False)
        mutated = _resolve_finalize_commit_candidates(
            planning_dir,
            tasks_dir,
            coord.repo_root,
            lanes_path if lanes_path.exists() else None,
            mission_slug=coord.mission_dir_name,
            owned=None,
        )
    assert mutated.has_relevant_changes is False, "sanity: dropping the coordination-dirt leg must reproduce the masked defect"


# ---------------------------------------------------------------------------
# B6 (cycle 2, MEDIUM, Decision plan.design.translate-if-present-kinds):
# finalize's write leg for ACCEPTANCE_MATRIX uses write_dir (never a read
# resolver), and a stale root copy must never overwrite the owning
# coordination copy.
# ---------------------------------------------------------------------------


def test_finalize_never_lets_a_stale_root_acceptance_matrix_overwrite_the_coord_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A stale, divergent root-checkout copy of ``acceptance-matrix.json``
    (planted directly, simulating residue from before this WP) must never be
    staged into finalize's combined commit -- the owning coordination copy
    is untouched by it.
    """
    coord = make_coord_mission(tmp_path, MissionTopology.COORD, slug="wp15-b6")
    _write_coord_finalize_fixture(coord)
    _run_real_finalize(monkeypatch, coord)

    coord_matrix = coord.coord_mission_dir / "acceptance-matrix.json"
    assert coord_matrix.exists(), "the first finalize run must scaffold the owning coordination matrix"
    owning_content_before = coord_matrix.read_text(encoding="utf-8")

    # Plant a stale, DIVERGENT root copy directly (never through finalize) --
    # the shape a pre-WP15 root residue would have left behind.
    root_matrix = coord.root_mission_dir / "acceptance-matrix.json"
    root_matrix.write_text('{"mission_slug": "stale-root-residue", "criteria": []}', encoding="utf-8")

    _seed_execution_begun(coord, coord.mission_dir_name)
    emitted = _run_real_finalize(monkeypatch, coord)
    success = _success_payload(emitted)
    assert success.get("result") == "success", f"payload={emitted}"

    assert coord_matrix.read_text(encoding="utf-8") == owning_content_before, "the stale root copy must never overwrite the owning coordination copy"
    # The stale root copy is finalize's OWN scope concern no further than
    # "never staged" -- it is left on disk, untouched, for WP21's SC-001
    # residue sweep to handle.
    assert root_matrix.exists()


def test_refresh_planning_commit_help_never_advises_the_flag_for_a_foreign_pin() -> None:
    """C2-3 (WP15 cycle 3): the ``--refresh-planning-commit`` help text must
    never recommend a command sequence that is guaranteed to fail.

    Red at the lane base: the help text told the operator to use
    ``--refresh-planning-commit`` (implicitly with ``--allow-orphaned``) "to
    advance a pin the automatic path could not safely verify on its own and
    warned about instead (a recorded SHA whose object is absent from this
    repository)" -- but ``_resolve_refresh_planning_commit_decision`` refuses
    a FOREIGN pin UNCONDITIONALLY, so that remedy can never succeed (the B8
    defect, recurring in the help text rather than the console warning).
    """
    import typing

    from specify_cli.cli.commands.agent.mission_finalize import finalize_tasks

    hints = typing.get_type_hints(finalize_tasks, include_extras=True)
    refresh_hint = hints["refresh_planning_commit"]
    option = next(meta for meta in getattr(refresh_hint, "__metadata__", ()) if hasattr(meta, "help"))
    help_text = option.help
    assert help_text is not None

    # The forbidden B9/C2-3 advice: telling the operator this flag can
    # advance a pin the automatic path already warned about (a FOREIGN
    # object absent from the repository) -- it cannot; the FOREIGN refusal
    # is unconditional in ``_resolve_refresh_planning_commit_decision``.
    assert "to advance a pin the automatic" not in help_text, f"help text must not recommend this flag for a pin the automatic path refused; got: {help_text!r}"
    lowered = help_text.lower()
    # It must still name the FOREIGN/absent-object shape, so operators
    # recognize it, and it must point at the real remedy instead of a
    # doomed command.
    assert "foreign" in lowered and "absent from this repository" in lowered, f"help text must still name the FOREIGN/absent-object shape; got: {help_text!r}"
    assert "cannot" in lowered, f"help text must say the flag cannot help a FOREIGN/INDETERMINATE pin; got: {help_text!r}"
    assert "by hand" in lowered, f"help text must point at the real remedy (manual correction), not a doomed command; got: {help_text!r}"


def test_commit_finalize_artifacts_raises_named_error_when_owned_candidate_escapes_planning_dir(
    tmp_path: Path,
) -> None:
    """Non-blocking fold (cycle 2 -> cycle 3): the owned-checkout commit-candidate
    guard in ``_commit_finalize_artifacts`` must be a REAL, unconditional raise
    of a named error -- never a bare ``assert`` (stripped under ``python -O``).

    Drives the guard directly: mocks ``_resolve_finalize_commit_candidates`` to
    return a candidate OUTSIDE ``planning_dir`` (the shape only reachable today
    if ``LIFECYCLE_OWNED_TOPOLOGIES`` ever widens past single_branch), with a
    truthy ``owned`` object, and asserts the dedicated
    ``OwnedCheckoutCandidateOutsidePlanningError`` fires (surfacing its own
    message through the existing function-wide error-reporting shell).
    """
    from specify_cli.cli.commands.agent.mission_finalize import (
        _commit_finalize_artifacts,
        _FinalizeCommitCandidates,
    )

    planning_dir = tmp_path / "repo" / "kitty-specs" / "fixture"
    planning_dir.mkdir(parents=True)
    outside_path = tmp_path / "elsewhere" / "status.events.jsonl"
    outside_path.parent.mkdir(parents=True)
    outside_path.write_text("{}\n", encoding="utf-8")

    escaping_candidates = _FinalizeCommitCandidates(
        files_to_commit=[outside_path],
        files_to_commit_rel=[str(outside_path)],
        has_relevant_changes=True,
    )
    emitted: list[dict[str, object]] = []
    # The existing function-wide "except Exception -> typer.Exit(1)" shell
    # (the same defensive-CLI-error convention every other internal failure
    # in this function uses) still wraps the named error at this boundary --
    # the fix under test is that the guard is a REAL, unconditional raise
    # that this shell always SEES (never a bare ``assert``, which an
    # optimized interpreter would silently skip), so the request still
    # fails closed with the named error's own message.
    with (
        patch(
            "specify_cli.cli.commands.agent.mission_finalize._resolve_finalize_commit_candidates",
            return_value=escaping_candidates,
        ),
        # Isolates this test to the guard itself: resolving a REAL
        # ``ProtectionPolicy.resolve_for_owned`` needs a fully-shaped owned
        # checkout (real git config, a readable meta.json) this guard-only
        # scenario has no reason to construct.
        patch(
            "specify_cli.cli.commands.agent.mission_finalize._mission_protection_policy",
            return_value=ProtectionPolicy(protected_branches=frozenset(), operator_hatch_active=False),
        ),
        patch("specify_cli.cli.commands.agent.mission_finalize._emit_json", emitted.append),
        pytest.raises(typer.Exit),
    ):
        _commit_finalize_artifacts(
            planning_dir,
            planning_dir / "tasks",
            tmp_path / "repo",
            "fixture",
            "main",
            None,
            set(),
            json_output=True,
            updated_count=0,
            owned=MagicMock(),
        )
    assert emitted and "LIFECYCLE_OWNED_TOPOLOGIES widened" in str(emitted[0].get("error", "")), (
        f"the named OwnedCheckoutCandidateOutsidePlanningError must surface its own message; emitted={emitted!r}"
    )


# ---------------------------------------------------------------------------
# B3 independence (fold, cycle 3): the two end-to-end B3 tests above
# (remote-only coordination branch, coord-seed-fork-refused) make EVERY
# ``write_dir`` call for this Mission raise, so they cannot tell which of
# ``_emit_local_canonical_events`` and ``_emit_tasks_started`` actually
# caught the refusal -- swallowing either call site ALONE survives them
# (masked by the other site failing closed first); only swallowing BOTH is
# killed. These two tests drive each function DIRECTLY and in isolation, so
# each is sensitive to its OWN call site reverting to a swallowed refusal,
# independent of the other.
# ---------------------------------------------------------------------------


def test_emit_local_canonical_events_propagates_a_write_dir_refusal(tmp_path: Path) -> None:
    """``_emit_local_canonical_events``'s OWN ``write_dir`` call must propagate
    a refusal -- in isolation, never relying on ``_emit_tasks_started``
    having already failed closed first.
    """
    from specify_cli.cli.commands.agent.mission_finalize import _emit_local_canonical_events

    mock_seam = MagicMock()
    mock_seam.write_dir.side_effect = RuntimeError("COORDINATION_WORKTREE_UNMATERIALIZED (fixture)")
    planning_dir = tmp_path / "kitty-specs" / "fixture"
    planning_dir.mkdir(parents=True)

    with patch("mission_runtime.placement_seam", return_value=mock_seam), pytest.raises(RuntimeError, match="COORDINATION_WORKTREE_UNMATERIALIZED"):
        _emit_local_canonical_events(planning_dir, "fixture", tmp_path, [], json_output=True, owned=None)


def test_emit_tasks_started_propagates_a_write_dir_refusal(tmp_path: Path) -> None:
    """``_emit_tasks_started``'s OWN ``write_dir`` call must propagate a
    refusal -- in isolation, never relying on ``_emit_local_canonical_events``
    having already failed closed first.
    """
    from specify_cli.cli.commands.agent.mission_finalize import _BootstrapState, _emit_tasks_started

    mock_seam = MagicMock()
    mock_seam.write_dir.side_effect = RuntimeError("COORDINATION_WORKTREE_UNMATERIALIZED (fixture)")

    with patch("mission_runtime.placement_seam", return_value=mock_seam), pytest.raises(RuntimeError, match="COORDINATION_WORKTREE_UNMATERIALIZED"):
        _emit_tasks_started("fixture", _BootstrapState(), validate_only=False, repo_root=tmp_path, owned=None)


# ---------------------------------------------------------------------------
# WP10 / T061 (FR-012, #5885): the finalize-tasks CLI entry point writes a
# bookkeeping commit whose subject says "for mission", never "for feature".
# RED on the pre-fix tree (``_finalize_bookkeeping_commit_message`` returned
# "Add tasks for feature <slug>").
# ---------------------------------------------------------------------------


def test_finalize_tasks_cli_commit_subject_says_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Drive the REAL finalize-tasks entry point and read its commit subject."""
    coord = make_coord_mission(tmp_path, MissionTopology.COORD, slug="wp10-t061")
    _write_coord_finalize_fixture(coord)

    _run_real_finalize(monkeypatch, coord)

    subjects = _git_stdout(coord.repo_root, "log", "--all", "--format=%s")
    assert "Add tasks for mission " in subjects, f"finalize-tasks must write a 'for mission' bookkeeping subject; subjects=\n{subjects}"
    assert "Add tasks for feature " not in subjects, f"finalize-tasks must not emit the legacy 'for feature' subject; subjects=\n{subjects}"
