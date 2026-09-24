"""coord-read-fail-closed-01M38VVH WP04 (FR-004 / NFR-002) — caller blast-radius.

WP01 made a coord-partition ``read_dir`` on ``CoordState.UNMATERIALIZED`` raise
``CoordinationWorktreeUnmaterialized`` instead of silently substituting the
empty PRIMARY checkout (see ``test_coord_read_seam.py``). That flips ~25
no-catch coord ``STATUS_STATE`` readers from silent-wrong-data to fail-loud —
the *desired* outcome — but each caller must land at a sane, operator-facing
boundary (the sibling's ``next_step``), never a raw/opaque traceback.

This module pins three things (Phase-0 audit in ``research.md`` §blast-radius):

* **T012** — the two SANCTIONED read-only degraders
  (``mission_runtime.read_dir_degrade.resolve_read_dir_or_degrade`` and
  ``review.cycle._review_cycle_wp_dir(kind=REVIEW_CYCLE)``) still degrade: their
  ``except (..., StatusReadPathNotFound)`` absorbs the new sibling unchanged
  (NFR-002 no-regression). A representative ALREADY-SAFE catcher
  (``status.aggregate.MissionStatus.load``) is unaffected because it resolves
  through a completely different, untouched resolver
  (``missions._read_path_resolver.resolve_surface_dir_or_typed_error``), not
  the ``mission_runtime.resolution`` seam WP01 changed.
* **T013** — three of the four named no-catch readers
  (``decisions.emit._mission_dir``, ``agent_utils.status.build_kanban_status``,
  ``lanes.recovery.scan_recovery_state``) already land at a sane boundary: the
  reader's own code does nothing between the seam call and its return/raise
  that could replace the well-formed ``CoordinationWorktreeUnmaterialized``
  (informative ``next_step``, distinct ``error_code``) with a less-informative
  exception. The fourth
  (``agent_tasks_ports.RealCoordCommitRouter.feature_write_dir:339``) is
  verified NOT REACHABLE with the new sibling at all — its seam-calling arm
  requires ``MissionTopology.SINGLE_BRANCH`` (an existing, unrelated
  ``ActionContextError`` gate), which structurally never has an UNMATERIALIZED
  coordination branch; its other arm resolves through a completely different,
  untouched resolver. No caller edit was needed in any of the four owned
  readers.
* **T014** — the SAME four readers produce NO new raise on a non-coord
  (SINGLE_BRANCH) mission — the seam change is scoped to coord-partition reads
  only (regression pin).

Real-git fixtures reuse the golden-path scaffolding verbatim (do NOT duplicate
the git/mission-creation primitives) — same pattern as
``test_coord_read_seam.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mission_runtime import (
    MissionArtifactKind,
    MissionTopology,
    ReadDegradeStrategy,
    resolve_read_dir_or_degrade,
)
from specify_cli.agent_tasks_ports import MissionHandle, RealCoordCommitRouter
from specify_cli.coordination.surface_resolver import (
    CoordinationBranchDeleted,
    CoordinationWorktreeUnmaterialized,
)
from specify_cli.core.mission_creation import MissionCreationResult
from specify_cli.missions._read_path_resolver import StatusReadPathNotFound
from specify_cli.status.aggregate import MissionStatus

from tests.integration.test_placement_partition_golden_path import (
    _create_mission,
    _init_git_repo,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_WORK_BRANCH = "coord-read-seam-callers-work"


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo, branch=_WORK_BRANCH)
    return repo


def _unmaterialized_coord_mission(tmp_path: Path, slug: str) -> tuple[Path, MissionCreationResult]:
    """A COORD-topology mission whose coordination branch exists in git but
    whose worktree was never materialized — ``CoordState.UNMATERIALIZED``."""
    repo = _repo(tmp_path)
    result = _create_mission(repo, slug, MissionTopology.COORD)
    # Deliberately no `_materialize_coord_worktree` call.
    return repo, result


def _single_branch_mission(tmp_path: Path, slug: str) -> tuple[Path, MissionCreationResult]:
    """A coord-less (SINGLE_BRANCH) mission — the seam never raises here."""
    repo = _repo(tmp_path)
    result = _create_mission(repo, slug, MissionTopology.SINGLE_BRANCH)
    return repo, result


# ===========================================================================
# T012 — sanctioned degraders keep degrading; a representative already-safe
# catcher is unaffected (NFR-002)
# ===========================================================================


def test_read_dir_degrade_absorbs_unmaterialized_sibling(tmp_path: Path) -> None:
    """``resolve_read_dir_or_degrade`` (the sanctioned degrade helper) degrades
    on the new sibling exactly as it already does for ``CoordinationBranchDeleted``
    — mirroring the real ``retrospective/generator.py`` call shape
    (``caught=(CoordinationBranchDeleted, StatusReadPathNotFound)``,
    ``ZERO_EVIDENCE``): its ``except ... StatusReadPathNotFound`` absorbs the
    new ``CoordinationWorktreeUnmaterialized`` sibling unchanged."""
    repo, result = _unmaterialized_coord_mission(tmp_path, "coord-degrade-demo")

    decision = resolve_read_dir_or_degrade(
        repo,
        result.mission_slug,
        MissionArtifactKind.TRACER_FILE,
        strategy=ReadDegradeStrategy.ZERO_EVIDENCE,
        caught=(CoordinationBranchDeleted, StatusReadPathNotFound),
        degrade_target=result.feature_dir,
    )

    assert decision.degraded is True
    assert decision.read_dir == result.feature_dir


def test_review_cycle_wp_dir_degrades_to_primary_on_unmaterialized(
    tmp_path: Path,
) -> None:
    """``review/cycle.py``'s designed ``kind=REVIEW_CYCLE`` absorption branch
    (line ~294, ``except StatusReadPathNotFound``) falls back to the PRIMARY
    ``WORK_PACKAGE_TASK`` dir on UNMATERIALIZED, exactly as it does for a
    deleted coordination branch — the sibling is absorbed, not raised."""
    from specify_cli.review.cycle import _review_cycle_wp_dir

    repo, result = _unmaterialized_coord_mission(tmp_path, "coord-review-cycle-demo")

    resolved = _review_cycle_wp_dir(
        repo,
        result.mission_slug,
        "WP01",
        kind=MissionArtifactKind.REVIEW_CYCLE,
    )

    expected = result.feature_dir / "tasks" / "WP01"
    assert resolved.resolve() == expected.resolve()


def test_mission_status_load_unaffected_by_unmaterialized_seam(
    tmp_path: Path,
) -> None:
    """Representative already-safe catcher: ``MissionStatus.load`` resolves
    through ``missions._read_path_resolver.resolve_surface_dir_or_typed_error``
    — a DIFFERENT, untouched resolver than the ``mission_runtime.resolution``
    seam WP01 changed — so its historical UNMATERIALIZED behavior (primary
    checkout stays authoritative until first write) is unaffected by this
    mission's fix. No ``CoordinationWorktreeUnmaterialized`` reaches here."""
    repo, result = _unmaterialized_coord_mission(tmp_path, "coord-aggregate-demo")

    status = MissionStatus.load(repo, result.mission_slug)

    assert status.mission_slug == result.mission_slug
    # The coord worktree was never materialized, so the primary checkout is
    # still authoritative — the same historical create-window contract this
    # mission's fix does not touch.
    assert status.read_dir.resolve() == result.feature_dir.resolve()


# ===========================================================================
# T013 — named no-catch readers already fail loud at a sane boundary
# ===========================================================================


def test_decisions_emit_mission_dir_fails_loud_sanely(tmp_path: Path) -> None:
    """``decisions/emit.py:88`` (``_mission_dir``): the seam call is a clean
    pass-through — nothing between it and the return could replace the
    well-formed sibling with something worse. Calling it directly on an
    UNMATERIALIZED coord mission raises ``CoordinationWorktreeUnmaterialized``
    itself, carrying an operator-facing ``next_step`` (not a bare/opaque
    exception a raw traceback would leave undiagnosable)."""
    from specify_cli.decisions.emit import _mission_dir

    repo, result = _unmaterialized_coord_mission(tmp_path, "coord-emit-demo")

    with pytest.raises(CoordinationWorktreeUnmaterialized) as excinfo:
        _mission_dir(repo, result.mission_slug)

    assert excinfo.value.error_code == "COORDINATION_WORKTREE_UNMATERIALIZED"
    assert "materializ" in excinfo.value.next_step.lower()
    assert result.mission_slug in str(excinfo.value)


def test_agent_utils_status_build_kanban_fails_loud_sanely(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``agent_utils/status.py:103`` (``build_kanban_status``): the raw reader
    raises the well-formed sibling directly (sane boundary — see docstring
    above); its public wrapper ``show_kanban_status`` (same module, already
    catches ``Exception`` broadly) converts that into a printed operator
    message and a structured ``{"error": ...}`` return — never a raw
    traceback, never a fabricated success."""
    from specify_cli.agent_utils import status as status_mod

    repo, result = _unmaterialized_coord_mission(tmp_path, "coord-kanban-demo")
    monkeypatch.chdir(repo)
    monkeypatch.setattr("specify_cli.agent_utils.status.locate_project_root", lambda cwd: repo)
    monkeypatch.setattr("specify_cli.agent_utils.status.get_status_read_root", lambda: repo)

    with pytest.raises(CoordinationWorktreeUnmaterialized) as excinfo:
        status_mod.build_kanban_status(result.mission_slug)
    assert excinfo.value.error_code == "COORDINATION_WORKTREE_UNMATERIALIZED"

    # The public wrapper already absorbs it into a sane, non-fabricated result.
    outcome = status_mod.show_kanban_status(result.mission_slug)
    assert "error" in outcome
    assert "materializ" in outcome["error"].lower()


def test_lanes_recovery_scan_recovery_state_fails_loud_sanely(
    tmp_path: Path,
) -> None:
    """``lanes/recovery.py:615`` (``scan_recovery_state``): the coord STATUS_STATE
    leg is a documented deliberate fail-loud site (`#2185`/#2155`` comment
    above the call) — the seam raise now covers UNMATERIALIZED the same way it
    already covered DELETED, with the same sane, informative exception."""
    from specify_cli.lanes.recovery import scan_recovery_state

    repo, result = _unmaterialized_coord_mission(tmp_path, "coord-recovery-demo")

    with pytest.raises(CoordinationWorktreeUnmaterialized) as excinfo:
        scan_recovery_state(repo, result.mission_slug)

    assert excinfo.value.error_code == "COORDINATION_WORKTREE_UNMATERIALIZED"
    assert "materializ" in excinfo.value.next_step.lower()


def test_agent_tasks_ports_feature_write_dir_fails_loud_sanely(
    tmp_path: Path,
) -> None:
    """``agent_tasks_ports.py:339`` (``RealCoordCommitRouter.feature_write_dir``):
    verified NOT reachable with ``CoordinationWorktreeUnmaterialized`` at all.

    The ``effective_root is not None`` arm that calls the modified seam is the
    ``--owned-checkout`` leg, gated upstream by ``resolve_artifact_surface``'s
    ``_require_owned_single_branch`` to ``MissionTopology.SINGLE_BRANCH`` only
    (``ActionContextError("OWNED_TOPOLOGY_UNSUPPORTED")`` otherwise) —
    single_branch missions never declare a ``coordination_branch``, so
    ``CoordState.UNMATERIALIZED`` can never be reported for them. This test
    pins that a COORD mission hitting this arm fails loud with the EXISTING,
    already-typed ``ActionContextError`` (sane boundary, unrelated to this
    mission's fix) rather than ever reaching the coord seam.

    The default (``effective_root is None``, both real callers' non-owned
    case) arm calls ``resolve_feature_dir_for_mission`` -> ``resolve_action_
    context`` — a DIFFERENT, untouched resolver (see the sibling
    ``..._no_raise_on_single_branch`` test and the module docstring) that
    always resolves to the PRIMARY dir regardless of coord materialization;
    it is unaffected by WP01's fix and cannot surface the new sibling either."""
    from mission_runtime import ActionContextError

    repo, result = _unmaterialized_coord_mission(tmp_path, "coord-ports-demo")

    router = RealCoordCommitRouter()
    handle = MissionHandle(repo_root=repo, mission_slug=result.mission_slug, effective_root=repo)

    with pytest.raises(ActionContextError) as excinfo:
        router.feature_write_dir(handle)
    assert excinfo.value.code == "OWNED_TOPOLOGY_UNSUPPORTED"

    # The realistic (non-owned) default path never reaches the modified seam,
    # so it never raises on UNMATERIALIZED either — pinned explicitly so a
    # future change to this resolver is caught here, not silently.
    default_handle = MissionHandle(repo_root=repo, mission_slug=result.mission_slug, effective_root=None)
    resolved = router.feature_write_dir(default_handle)
    assert resolved.resolve() == result.feature_dir.resolve()


# ===========================================================================
# T014 — same four readers: NO new raise on a non-coord (SINGLE_BRANCH)
# mission (NFR-002 scope pin — the seam change never touches coord-less reads)
# ===========================================================================


def test_decisions_emit_mission_dir_no_raise_on_single_branch(
    tmp_path: Path,
) -> None:
    from specify_cli.decisions.emit import _mission_dir

    repo, result = _single_branch_mission(tmp_path, "single-emit-demo")

    resolved = _mission_dir(repo, result.mission_slug)
    assert resolved.resolve() == result.feature_dir.resolve()


def test_agent_utils_status_build_kanban_no_raise_on_single_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.agent_utils import status as status_mod

    repo, result = _single_branch_mission(tmp_path, "single-kanban-demo")
    monkeypatch.chdir(repo)
    monkeypatch.setattr("specify_cli.agent_utils.status.locate_project_root", lambda cwd: repo)
    monkeypatch.setattr("specify_cli.agent_utils.status.get_status_read_root", lambda: repo)
    # A SINGLE_BRANCH mission has no tasks.md / lanes.json seeded by
    # ``_create_mission`` alone; only the STATUS_STATE leg (the one the seam
    # change touches) matters for this pin, so seed the minimal tasks dir the
    # PRIMARY leg needs to avoid an unrelated FileNotFoundError masking the
    # assertion.
    (result.feature_dir / "tasks").mkdir(exist_ok=True)

    outcome = status_mod.build_kanban_status(result.mission_slug)
    assert "error" not in outcome


def test_lanes_recovery_scan_recovery_state_no_raise_on_single_branch(
    tmp_path: Path,
) -> None:
    from specify_cli.lanes.recovery import scan_recovery_state

    repo, result = _single_branch_mission(tmp_path, "single-recovery-demo")

    # No live branches / no lanes.json — the scan should just report no
    # recovery-relevant state, never raise.
    states = scan_recovery_state(repo, result.mission_slug, consult_status_events=False)
    assert states == []


def test_agent_tasks_ports_feature_write_dir_no_raise_on_single_branch(
    tmp_path: Path,
) -> None:
    repo, result = _single_branch_mission(tmp_path, "single-ports-demo")

    router = RealCoordCommitRouter()
    handle = MissionHandle(repo_root=repo, mission_slug=result.mission_slug, effective_root=repo)

    resolved = router.feature_write_dir(handle)
    assert resolved.resolve() == result.feature_dir.resolve()


# ===========================================================================
# Mid-mission coordinator referral (out-of-map, WP02 review finding): the
# ``tracer-append`` CLI wrapper (``src/specify_cli/cli/commands/agent/
# tracer_append.py``, NOT in this WP's ``owned_files``) only caught
# ``TracerAttributionError``/``TracerCategoryError`` around
# ``append_tracer_finding``. WP02 narrows the tracer read's absorption
# (``retrospective/tracer_writer.py::_read_current_coord_content``) so a
# coord-topology read on an UNMATERIALIZED coordination worktree now
# PROPAGATES ``CoordinationWorktreeUnmaterialized`` out of
# ``append_tracer_finding`` instead of degrading to ``""`` — without a wrap,
# that would have surfaced as a raw traceback at this CLI boundary. Added a
# minimal ``except CoordinationWorktreeUnmaterialized`` arm there (same
# structured ``{"ok": false, ...}`` refusal shape the sibling error branches
# already use, carrying ``next_step`` verbatim) per the coordinator's
# referral. WP02's OWN seam fix is not present in this lane yet, so the
# regression below drives the CLI wrapper's exception handling in isolation
# (mocks ``append_tracer_finding`` to raise the sibling directly) rather than
# depending on WP02's landing.
# ===========================================================================


def test_tracer_append_cli_structured_refusal_on_unmaterialized(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``tracer-append --json`` on a propagated ``CoordinationWorktreeUnmaterialized``
    returns the structured ``{"ok": false, ...}`` refusal (with ``next_step``),
    never a raw traceback."""
    import importlib

    import typer
    from typer.testing import CliRunner

    # ``specify_cli.cli.commands.agent.__init__`` does
    # ``from .tracer_append import tracer_append``, which rebinds the
    # ``agent.tracer_append`` package ATTRIBUTE to the function — so a plain
    # ``import specify_cli.cli.commands.agent.tracer_append as m`` (which
    # resolves via that attribute, per the language's ``import a.b as c``
    # desugaring) would hand back the function, not the module.
    # ``importlib.import_module`` reads ``sys.modules`` directly instead.
    tracer_append_mod = importlib.import_module("specify_cli.cli.commands.agent.tracer_append")

    repo = _repo(tmp_path)
    monkeypatch.chdir(repo)

    sibling = CoordinationWorktreeUnmaterialized(
        repo_root=repo,
        mission_slug="tracer-unmat-demo",
        mid8="01ABCDEF",
        coordination_branch="kitty/mission-tracer-unmat-demo-01ABCDEF",
        coord_candidate=repo / ".worktrees" / "tracer-unmat-demo-01ABCDEF-coord",
        primary_candidate=repo / "kitty-specs" / "tracer-unmat-demo-01ABCDEF",
    )
    monkeypatch.setattr(
        tracer_append_mod,
        "append_tracer_finding",
        lambda **_kwargs: (_ for _ in ()).throw(sibling),
    )

    app = typer.Typer()
    app.command()(tracer_append_mod.tracer_append)
    result = CliRunner().invoke(
        app,
        [
            "--mission",
            "tracer-unmat-demo",
            "--category",
            "decisions",
            "--entry",
            "irrelevant",
            "--actor",
            "test-actor",
            "--json",
        ],
    )

    assert result.exit_code == 1
    # A raw traceback would show as an unhandled exception on ``result.exception``
    # (CliRunner re-raises unless the command itself caught it) — asserting a
    # clean, parseable JSON payload on stdout is the sane-boundary proof.
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["kind"] == "TRACER_FILE"
    assert "materializ" in payload["next_step"].lower()
    assert "tracer-unmat-demo" in payload["error"]
