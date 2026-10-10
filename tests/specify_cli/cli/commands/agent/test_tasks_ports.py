"""WP02 — TasksPorts co-design: Fake adapters, injection proof, stratification
invariants, and the FR-010 dir-equivalence proof artifact.

Covers subtasks:

* **T010** — pure, deterministic Fake adapters for all four ports.
* **T011** — ``TasksPorts`` bundle + ``default_ports`` builder; a
  registration-introspection proof that the Typer ``agent tasks`` surface exposes
  NO ``--ports`` flag, and that the ``_do_<cmd>(*, ports=None)`` injection idiom
  is sound (C-005).
* **T012** — stratification invariants (C-001 / research D2): READ ≠ WRITE ports;
  ``commit_status`` / ``commit_artifact`` are co-equal methods over disjoint
  seams; the canonicalizer fold is intra-adapter (C-002); exactly four ports.
* **T013** — FR-010 pre30-guard dir-equivalence proof on the WP01 coord fixture.

FR-010 FINDING (see ``test_fr010_*`` below): on a coord topology the kind-blind
``resolve_feature_dir_for_mission`` and the kind-aware ``resolve_planning_read_dir``
for a PRIMARY-partition kind resolve DIFFERENT dirs **by construction** — that is
the split-brain FR-010 closes, so a literal path-equality proof is impossible for
the pinned primary kinds. The parity that actually holds (and that de-risks the
WP06/WP08 rewire) is the pre30 **guard-outcome** equivalence: ``check_pre30_layout``
is byte-identically a no-op on both legs for a modern mission. Both facts are
pinned below.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from typer.main import get_command

from mission_runtime import MissionArtifactKind
from specify_cli.agent_tasks_ports import (
    CommitArtifactResult,
    CommitStatusResult,
    CoordCommitRouter,
    FsReader,
    GitOps,
    MissionHandle,
    RealCoordCommitRouter,
    RealFsReader,
    RealGitOps,
    RealRender,
    Render,
    TasksPorts,
    default_ports,
)
from specify_cli.cli.commands.agent.tasks import app
from specify_cli.core.commit_guard import GuardCapability
from specify_cli.git.protection_policy import ProtectionPolicy
from specify_cli.missions._read_path_resolver import (
    resolve_feature_dir_for_mission,
    resolve_planning_read_dir,
)
from specify_cli.status.models import TransitionRequest
from specify_cli.upgrade.pre30_guard import Pre30LayoutError, check_pre30_layout
from tests import _click_universe as typer_click
from tests.integration.coord_topology_fixture import (
    CoordTopologyContext,
    _build_coord_topology,
)

pytestmark = pytest.mark.fast

# Production-shaped identity (real 26-char Crockford ULID / composed slug).
_MISSION_ID = "01KWF08S0000000000000000AB"
_MID8 = "01KWF08S"
_SLUG = f"tasks-py-degod-{_MID8}"


def _handle(repo_root: Path) -> MissionHandle:
    return MissionHandle(repo_root=repo_root, mission_slug=_SLUG)


# ===========================================================================
# T010 — Fake adapters (pure, deterministic, record calls, seeded returns)
# ===========================================================================


@dataclass
class FakeFsReader:
    """Pure in-memory :class:`FsReader`. No filesystem access."""

    planning_dirs: dict[MissionArtifactKind, Path] = field(default_factory=dict)
    default_planning_dir: Path = Path("/fake/primary/kitty-specs/mission")
    tasks_dir: Path = Path("/fake/primary/kitty-specs/mission/tasks")
    anchor_dir: Path = Path("/fake/primary/kitty-specs/mission")
    calls: list[tuple[str, object]] = field(default_factory=list)

    def planning_read_dir(
        self, mission: MissionHandle, *, kind: MissionArtifactKind
    ) -> Path:
        self.calls.append(("planning_read_dir", kind))
        return self.planning_dirs.get(kind, self.default_planning_dir)

    def wp_tasks_dir(self, mission: MissionHandle) -> Path:
        self.calls.append(("wp_tasks_dir", mission.mission_slug))
        return self.tasks_dir

    def primary_anchor_dir(self, mission: MissionHandle) -> Path:
        self.calls.append(("primary_anchor_dir", mission.mission_slug))
        return self.anchor_dir


@dataclass
class FakeCoordCommitRouter:
    """Pure in-memory :class:`CoordCommitRouter`.

    ``commit_status`` and ``commit_artifact`` append to SEPARATE call logs so a
    disjoint-seam test can prove neither method silently drives the other.
    """

    write_dir: Path = Path("/fake/coord/.worktrees/mission-coord/kitty-specs/mission")
    status_result: CommitStatusResult = CommitStatusResult(event=None, skipped=False)
    artifact_result: CommitArtifactResult = CommitArtifactResult(
        status="committed", placement_ref="primary", commit_hash="0" * 40
    )
    status_calls: list[tuple[str, GuardCapability]] = field(default_factory=list)
    artifact_calls: list[tuple[str, tuple[Path, ...], str, MissionArtifactKind]] = (
        field(default_factory=list)
    )

    def feature_write_dir(self, mission: MissionHandle) -> Path:
        return self.write_dir

    def commit_status(
        self,
        request: TransitionRequest,
        *,
        capability: GuardCapability,
    ) -> CommitStatusResult:
        self.status_calls.append((request.mission_slug or "", capability))
        return self.status_result

    def commit_artifact(
        self,
        mission: MissionHandle,
        paths: Sequence[Path],
        message: str,
        *,
        kind: MissionArtifactKind,
        policy: ProtectionPolicy,
    ) -> CommitArtifactResult:
        self.artifact_calls.append(
            (mission.mission_slug, tuple(paths), message, kind)
        )
        return self.artifact_result


@dataclass
class FakeGitOps:
    """Pure in-memory :class:`GitOps`. No subprocess/git access."""

    dirty: bool = False
    branch: str = f"kitty/mission-{_SLUG}-lane-b"
    protected_branches: frozenset[str] = frozenset({"main", "design/degod-tasks-2116"})
    calls: list[tuple[str, object]] = field(default_factory=list)

    def is_dirty(self, path: Path) -> bool:
        self.calls.append(("is_dirty", path))
        return self.dirty

    def current_branch(self, path: Path) -> str:
        self.calls.append(("current_branch", path))
        return self.branch

    def is_protected(self, branch: str) -> bool:
        self.calls.append(("is_protected", branch))
        return branch in self.protected_branches


@dataclass
class FakeRender:
    """Pure in-memory :class:`Render`. Records views + envelopes; no console I/O."""

    views: list[object] = field(default_factory=list)
    envelopes: list[Mapping[str, object]] = field(default_factory=list)

    def human(self, view: object) -> None:
        self.views.append(view)

    def json_envelope(self, payload: Mapping[str, object]) -> str:
        self.envelopes.append(payload)
        # Deterministic, pure — mirrors the Real adapter's default separators.
        import json

        return json.dumps(payload)


def _fake_ports() -> TasksPorts:
    return TasksPorts(
        fs=FakeFsReader(),
        coord=FakeCoordCommitRouter(),
        git=FakeGitOps(),
        render=FakeRender(),
    )


# ---------------------------------------------------------------------------
# T010 — Fakes structurally satisfy the protocols + are pure
# ---------------------------------------------------------------------------


def test_fakes_satisfy_protocols_runtime_checkable() -> None:
    """Each Fake is a structural instance of its port protocol (T010)."""
    assert isinstance(FakeFsReader(), FsReader)
    assert isinstance(FakeCoordCommitRouter(), CoordCommitRouter)
    assert isinstance(FakeGitOps(), GitOps)
    assert isinstance(FakeRender(), Render)


def test_fakes_are_deterministic_and_record_calls() -> None:
    """Fakes return seeded values and record every call (T010)."""
    handle = _handle(Path("/does/not/exist"))
    fs = FakeFsReader(
        planning_dirs={MissionArtifactKind.WORK_PACKAGE_TASK: Path("/seed/wp")}
    )
    assert (
        fs.planning_read_dir(handle, kind=MissionArtifactKind.WORK_PACKAGE_TASK)
        == Path("/seed/wp")
    )
    assert fs.wp_tasks_dir(handle) == fs.tasks_dir
    assert fs.primary_anchor_dir(handle) == fs.anchor_dir
    assert fs.calls == [
        ("planning_read_dir", MissionArtifactKind.WORK_PACKAGE_TASK),
        ("wp_tasks_dir", _SLUG),
        ("primary_anchor_dir", _SLUG),
    ]

    render = FakeRender()
    assert render.json_envelope({"a": 1}) == '{"a": 1}'
    render.human({"table": "rows"})
    assert render.views == [{"table": "rows"}]
    assert render.envelopes == [{"a": 1}]


# ---------------------------------------------------------------------------
# T016 (WP04) — RealRender indent seam: one adapter, constructor-configured
# ---------------------------------------------------------------------------


def test_real_render_default_is_compact_bytes() -> None:
    """Default ``RealRender()`` emits ``json.dumps`` DEFAULT-separator bytes (T016).

    ``indent=None`` must be byte-identical to a bare ``json.dumps(payload)``
    (research D2) — the compact emission sites in tasks.py are byte-frozen on it.
    """
    import json

    payload = {"result": "success", "wp_id": "WP04", "count": 2}
    assert RealRender().json_envelope(payload) == json.dumps(payload)
    assert (
        RealRender().json_envelope(payload)
        == '{"result": "success", "wp_id": "WP04", "count": 2}'
    )


def test_real_render_indent_two_is_indented_bytes() -> None:
    """``RealRender(indent=2)`` emits the ``status --json`` indented form (T016).

    Byte-identical to ``json.dumps(payload, indent=2)`` — the seam that replaced
    the deleted status-specific Render subclass (one adapter per port, C-004).
    """
    import json

    payload = {"result": "success", "wp_id": "WP04", "count": 2}
    assert RealRender(indent=2).json_envelope(payload) == json.dumps(
        payload, indent=2
    )
    assert RealRender(indent=2).json_envelope(payload) == (
        '{\n  "result": "success",\n  "wp_id": "WP04",\n  "count": 2\n}'
    )


# ===========================================================================
# T011 — Bundle + injection proof
# ===========================================================================


def test_default_ports_builds_real_bundle() -> None:
    """``default_ports`` wires the Real adapters (T011)."""
    ports = default_ports()
    assert isinstance(ports, TasksPorts)
    assert isinstance(ports.fs, RealFsReader)
    assert isinstance(ports.coord, RealCoordCommitRouter)
    assert isinstance(ports.git, RealGitOps)
    assert isinstance(ports.render, RealRender)


def test_tasks_ports_is_frozen() -> None:
    """The bundle is an immutable value object (T011)."""
    import dataclasses

    ports = _fake_ports()
    with pytest.raises(dataclasses.FrozenInstanceError):
        # Intentionally illegal assignment: the test EXISTS to prove the frozen
        # dataclass rejects it at runtime, so mypy's static rejection is the
        # same contract — suppressed narrowly, not a defect.
        ports.fs = FakeFsReader()


def _do_demo(*, ports: TasksPorts | None = None) -> str:
    """Reference orchestrator helper demonstrating the C-005 injection idiom.

    ``None`` builds the Real bundle via ``default_ports``; a caller (or a test)
    may inject a Fake bundle. This is the ``_do_<cmd>(*, ports=None)`` pattern the
    WP06+ rewire applies to the real command bodies — NOT wired here.
    """
    ports = ports or default_ports()
    return type(ports.fs).__name__


def test_injection_idiom_defaults_to_real_bundle() -> None:
    """C-005: ``ports=None`` resolves to the Real bundle (T011)."""
    assert _do_demo() == "RealFsReader"


def test_injection_idiom_accepts_injected_fake_bundle() -> None:
    """C-005: an injected Fake bundle is used verbatim (T011)."""
    assert _do_demo(ports=_fake_ports()) == "FakeFsReader"


def _iter_command_param_opts() -> list[tuple[str, str]]:
    """Return ``(command_name, option)`` for every param opt on the tasks surface."""
    group = get_command(app)
    assert isinstance(group, typer_click.Group)
    pairs: list[tuple[str, str]] = []
    for name, command in group.commands.items():
        for param in command.params:
            for opt in param.opts:
                pairs.append((name, opt))
    return pairs


def test_no_ports_flag_on_tasks_command_surface() -> None:
    """C-005: NO Typer command exposes a ``--ports`` flag (T011).

    A Protocol-typed parameter on a decorated command would collide with Typer
    introspection and surface as an unwanted ``--ports`` option. Proving its
    absence proves the injection stays on the extracted orchestrator helper.
    """
    offenders = [
        (cmd, opt)
        for cmd, opt in _iter_command_param_opts()
        if "ports" in opt.lower()
    ]
    assert offenders == [], (
        f"Unexpected ports-like flag on the tasks command surface: {offenders}. "
        "Injection must stay on _do_<cmd>(*, ports=None), never the @app.command."
    )


# ===========================================================================
# T012 — Stratification invariants (C-001 / research D2)
# ===========================================================================


def test_read_and_write_ports_are_distinct_types() -> None:
    """INV-1 / C-001: the coord READ and WRITE authorities are distinct ports."""
    assert id(FsReader) != id(CoordCommitRouter)
    read_methods = {"planning_read_dir", "wp_tasks_dir", "primary_anchor_dir"}
    write_methods = {"feature_write_dir", "commit_status", "commit_artifact"}
    # No method-name overlap — the authorities do not conflate.
    assert read_methods.isdisjoint(write_methods)
    assert read_methods <= set(dir(FsReader))
    assert write_methods <= set(dir(CoordCommitRouter))


def test_write_port_exposes_two_coequal_capability_methods() -> None:
    """research D2: the WRITE port carries TWO methods, not a fused ``commit()``."""
    router = CoordCommitRouter
    assert hasattr(router, "commit_status")
    assert hasattr(router, "commit_artifact")
    # A fused single-verb ``commit`` would be the C-006 mis-cut — assert it is absent.
    assert not hasattr(router, "commit")


def test_commit_status_and_commit_artifact_route_to_disjoint_seams() -> None:
    """D2: the two capabilities drive two separate seams (proved via the Fake).

    ``commit_status`` records ONLY on the status log; ``commit_artifact`` records
    ONLY on the artifact log. Neither leaks into the other — the structural proof
    that they are disjoint capabilities, not one hidden sub-step of the other.
    """
    coord = FakeCoordCommitRouter()
    handle = _handle(Path("/repo"))

    coord.commit_status(
        TransitionRequest(
            mission_slug=_SLUG, wp_id="WP02", to_lane="claimed", actor="randy-reducer"
        ),
        capability=GuardCapability.STANDARD,
    )
    assert coord.status_calls == [(_SLUG, GuardCapability.STANDARD)]
    assert coord.artifact_calls == []  # commit_status did NOT touch the artifact seam

    coord.commit_artifact(
        handle,
        [Path("kitty-specs/mission/tasks/WP02.md")],
        "chore: artifact",
        kind=MissionArtifactKind.WORK_PACKAGE_TASK,
        policy=ProtectionPolicy(protected_branches=frozenset(), operator_hatch_active=False),
    )
    assert len(coord.artifact_calls) == 1
    assert coord.artifact_calls[0][3] == MissionArtifactKind.WORK_PACKAGE_TASK
    # commit_artifact did NOT emit a status event.
    assert coord.status_calls == [(_SLUG, GuardCapability.STANDARD)]


def test_capability_keys_are_disjoint_types() -> None:
    """D2: status is keyed on GuardCapability; artifact on MissionArtifactKind."""
    import inspect
    from typing import get_type_hints

    status_sig = inspect.signature(CoordCommitRouter.commit_status)
    artifact_sig = inspect.signature(CoordCommitRouter.commit_artifact)
    # Resolve string annotations (the module uses ``from __future__ import
    # annotations``) so the key TYPES are compared, not their names.
    status_hints = get_type_hints(CoordCommitRouter.commit_status)
    artifact_hints = get_type_hints(CoordCommitRouter.commit_artifact)
    assert status_hints["capability"] is GuardCapability
    assert artifact_hints["kind"] is MissionArtifactKind
    # The artifact leg is event-LESS: it takes no capability, and the status leg
    # takes no kind/policy — proving the two seams are keyed disjointly.
    assert "capability" not in artifact_sig.parameters
    assert "kind" not in status_sig.parameters
    assert "policy" not in status_sig.parameters


def test_exactly_four_ports_in_bundle() -> None:
    """research D2: the bundle is exactly four ports (2 program-reference + 2 local)."""
    fields = TasksPorts.__dataclass_fields__
    assert set(fields) == {"fs", "coord", "git", "render"}
    assert len(fields) == 4


def test_primary_anchor_dir_has_no_separate_canonicalizer_fold() -> None:
    """C-002 (WP08 T036 update): no caller-side canonicalizer fold is
    co-located in ``RealFsReader.primary_anchor_dir`` any more — the fold is
    now entirely internal to the seam.

    read-side-seam-primary-primitive-closure-01KYKMMT WP04 (FR-004) first
    routed this method off the topology-blind ``primary_feature_dir_for_mission``
    wrapper onto ``placement_seam(...).read_dir(PRIMARY_METADATA)`` — the
    wrapper's own body was exactly this seam call. This test used to also pin
    a co-located ``_canonicalize_primary_read_handle`` fold call PRECEDING the
    seam call (the C-002 "the fold and the primitive call must live in the
    same function" invariant), but that invariant's subject was the primitive
    call itself — since ``primary_anchor_dir`` calls ``read_dir``, never the
    canonicalizer primitive directly, there was nothing left for a co-located
    fold to feed. WP08 (T036) drained the redundant caller-side fold (the
    seam's PRIMARY leg already folds the handle internally via the SAME
    ``_canonicalize_primary_read_handle`` primitive before composing), so this
    test now pins the drained shape: exactly one seam call, no separate fold.
    """
    import inspect

    source = inspect.getsource(RealFsReader.primary_anchor_dir)
    # A CALL, not a bare textual mention -- the method's own comment names the
    # primitive in prose to explain why the fold was dropped (redundant with
    # the seam's internal fold); only an actual call would mean it was not.
    assert "_canonicalize_primary_read_handle(" not in source, (
        "primary_anchor_dir should no longer pre-fold the handle -- the seam's "
        "PRIMARY leg already does so internally (WP08 T036)"
    )
    # T036: the per-call inline ``placement_seam(...)`` was folded into the
    # shared ``_placement_for(mission)`` helper (G4 -- one call site instead of
    # three repeated inline seam constructions); the seam call now lives there.
    assert "_placement_for(mission)" in source
    assert "MissionArtifactKind.PRIMARY_METADATA" in source


# ===========================================================================
# T013 — FR-010 pre30-guard dir-equivalence proof (WP01 coord fixture)
# ===========================================================================
#
# PINNED KINDS per FR-010 site (for WP06/WP08 — verified against tasks.py):
#
#   GUARD-ONLY sites (the coord-husk var feeds ONLY ``check_pre30_layout`` and is
#   then REASSIGNED to a primary read) — safe to repoint to a PRIMARY kind:
#   * finalize_tasks : guard at tasks.py:2373 (var reassigned :2453) -> WORK_PACKAGE_TASK
#   * list_dependents: guard at tasks.py:3568 (var reassigned :3578) -> WORK_PACKAGE_TASK
#
#   SHARED COORD-STATUS site (the coord-husk var is NOT guard-only — it also feeds
#   authoritative coord-authority reads) — the STATUS read MUST stay on the coord
#   husk (STATUS partition); do NOT repoint the shared variable to a primary kind:
#   * move_task      : guard at tasks.py:1138 -> STATUS_STATE (coord-husk-preserving)
#
# Rationale (guard-only sites): both feed ``check_pre30_layout`` before a WP
# mutation, then the var is reassigned to the primary read. The shipped
# ``add_history`` precedent (tasks.py:2285, guard-only var ``_ah_feature_dir``)
# migrated ITS guard to a PRIMARY-partition kind (TASKS_INDEX), rejecting the
# kind-blind coord-husk read as "a coord-authority violation". WORK_PACKAGE_TASK
# and TASKS_INDEX resolve to the SAME primary dir, so the guard outcome is
# identical either way; WORK_PACKAGE_TASK matches each site's adjacent primary
# read (finalize_tasks:2384, list_dependents:3578).
#
# Rationale (move_task): ``_mt_feature_dir`` (tasks.py:1138) is NOT reassigned —
# the SAME value feeds ``check_pre30_layout`` (:1140), the authoritative
# event-log lane read ``_read_transactional_wp_lane(feature_dir=_mt_feature_dir)``
# (:1149, STATUS partition), and ``_persist_review_artifact_override_in_coord(
# coord_feature_dir=_mt_feature_dir)`` (:1216). Repointing this shared variable to
# a PRIMARY kind (WORK_PACKAGE_TASK) would move the status/event-log read off the
# coord husk onto the primary ``kitty-specs/`` — which on a coord mission does NOT
# hold the authoritative event log => wrong/empty lane => reintroduces the exact
# split-brain FR-010 exists to close. The STATUS read must therefore stay on the
# coord husk; ``STATUS_STATE`` is the path-equal (coord-husk-preserving) kind, as
# ``test_fr010_only_status_partition_kind_matches_the_blind_dir`` proves. WP06
# MUST NOT wholesale-repoint tasks.py:1138: ``_mt_feature_dir`` stays on
# ``resolve_feature_dir_for_mission`` (coord husk) for :1149/:1216; only a
# SEPARATE guard-only variable may go kind-aware. The hazard is pinned red-first
# by ``test_fr010_move_task_status_read_must_stay_on_coord_husk`` below.


# The primary-partition kinds each FR-010 guard site may pin (all resolve PRIMARY).
_PRIMARY_GUARD_KINDS = (
    MissionArtifactKind.WORK_PACKAGE_TASK,
    MissionArtifactKind.TASKS_INDEX,
)


@pytest.fixture()
def coord_ctx(tmp_path: Path) -> CoordTopologyContext:
    """The WP01 coord-topology fixture, driven directly (T013 reuse)."""
    return _build_coord_topology(tmp_path, write_husk_meta=False)


def test_fr010_split_brain_is_real_blind_resolves_coord_husk(
    coord_ctx: CoordTopologyContext,
) -> None:
    """FR-010: the kind-blind resolver lands on the coord husk (the split-brain).

    This is the *current* pre30-guard read that WP06/WP08 migrate away from.
    """
    blind = resolve_feature_dir_for_mission(coord_ctx.repo, coord_ctx.slug)
    assert blind == coord_ctx.coord_feature_dir
    assert blind != coord_ctx.primary_feature_dir


def test_fr010_primary_kinds_resolve_primary_not_the_blind_dir(
    coord_ctx: CoordTopologyContext,
) -> None:
    """FR-010 FINDING: for a PRIMARY-partition kind the kind-aware resolver lands
    on the PRIMARY dir — which DIFFERS from the kind-blind coord-husk dir BY
    CONSTRUCTION (that is the split-brain being closed).

    Consequently a literal ``blind == kind_aware`` path-equality proof is
    IMPOSSIBLE for the pinned primary kinds; the real parity is the guard-outcome
    equivalence pinned in ``test_fr010_guard_outcome_is_byte_identical_...``.
    """
    blind = resolve_feature_dir_for_mission(coord_ctx.repo, coord_ctx.slug)
    for kind in _PRIMARY_GUARD_KINDS:
        resolved = resolve_planning_read_dir(coord_ctx.repo, coord_ctx.slug, kind=kind)
        assert resolved == coord_ctx.primary_feature_dir, kind
        assert resolved != blind, kind


def test_fr010_only_status_partition_kind_matches_the_blind_dir(
    coord_ctx: CoordTopologyContext,
) -> None:
    """FR-010 FINDING: the ONLY kind whose kind-aware read equals the kind-blind
    dir is a STATUS-partition kind (STATUS_STATE → coord husk).

    Pinning STATUS_STATE would preserve the split-brain (keep reading the husk)
    and contradict the shipped ``add_history`` precedent — so it is the WRONG
    choice for the pre30 guard even though it is the only path-equal one.
    """
    blind = resolve_feature_dir_for_mission(coord_ctx.repo, coord_ctx.slug)
    status_dir = resolve_planning_read_dir(
        coord_ctx.repo, coord_ctx.slug, kind=MissionArtifactKind.STATUS_STATE
    )
    assert status_dir == blind == coord_ctx.coord_feature_dir


def _guard_outcome(path: Path) -> str:
    """Reduce ``check_pre30_layout`` to a comparable outcome token."""
    try:
        check_pre30_layout(path)
        return "no-op"
    except Pre30LayoutError as exc:  # pragma: no cover - not hit on modern fixture
        return f"raise:{sorted(exc.detected_dirs)}"


def test_fr010_guard_outcome_is_byte_identical_across_legs(
    coord_ctx: CoordTopologyContext,
) -> None:
    """FR-010 (the real NFR-001 parity): ``check_pre30_layout`` produces the
    IDENTICAL outcome whether fed the current kind-blind coord-husk dir or the
    pinned PRIMARY-partition dir, on the modern WP01 coord fixture.

    This is the parity that de-risks the WP06/WP08 rewire: the guard is a no-op on
    a modern mission regardless of leg, so migrating the read from the coord husk
    to the primary anchor is observationally byte-identical (SC-002 / NFR-001).
    """
    blind = resolve_feature_dir_for_mission(coord_ctx.repo, coord_ctx.slug)
    blind_outcome = _guard_outcome(blind)
    assert blind_outcome == "no-op"  # sanity: modern fixture, guard does not fire

    for kind in _PRIMARY_GUARD_KINDS:
        primary_dir = resolve_planning_read_dir(
            coord_ctx.repo, coord_ctx.slug, kind=kind
        )
        assert _guard_outcome(primary_dir) == blind_outcome, kind


def test_fr010_guard_does_not_mutate_either_leg(
    coord_ctx: CoordTopologyContext,
) -> None:
    """FR-010: the guard is a pure no-op — it mutates neither the husk nor the
    primary tree (non-fakeable: snapshot rglob before/after)."""
    blind = resolve_feature_dir_for_mission(coord_ctx.repo, coord_ctx.slug)
    primary = resolve_planning_read_dir(
        coord_ctx.repo, coord_ctx.slug, kind=MissionArtifactKind.WORK_PACKAGE_TASK
    )
    for leg in (blind, primary):
        before = set(leg.rglob("*"))
        check_pre30_layout(leg)
        assert set(leg.rglob("*")) == before, leg


def test_fr010_move_task_status_read_must_stay_on_coord_husk(
    coord_ctx: CoordTopologyContext,
) -> None:
    """FR-010 HAZARD (move_task, tasks.py:1138) — red-first regression guard.

    Unlike the two GUARD-ONLY sites (finalize_tasks/list_dependents, whose
    coord-husk var is reassigned right after the pre30 guard), move_task's
    ``_mt_feature_dir`` is NOT guard-only: the SAME value also feeds the
    authoritative event-log lane read (``_read_transactional_wp_lane`` :1149) and
    the coord persist (``_persist_review_artifact_override_in_coord`` :1216) —
    both STATUS-partition, coord-authority reads that MUST land on the coord husk.

    This test pins the hazard structurally: for a coord mission the STATUS read
    (coord husk) and a PRIMARY-partition kind (WORK_PACKAGE_TASK) resolve
    DIFFERENT dirs — they are NOT byte-identical. Therefore a future WP06 that
    "byte-identically migrates tasks.py:1138" by collapsing the shared status
    read onto WORK_PACKAGE_TASK would silently move the event-log read off the
    coord husk onto the primary ``kitty-specs/`` (wrong/empty lane on a coord
    mission = the split-brain FR-010 closes). The status read stays path-equal to
    the coord husk ONLY under a STATUS-partition kind (STATUS_STATE).

    Passing today (dirs differ) is the assertion; it goes RED the moment WP06
    repoints move_task's shared coord-status variable to a primary kind.
    """
    coord_husk = resolve_feature_dir_for_mission(coord_ctx.repo, coord_ctx.slug)
    # The coord-husk read is where move_task's shared status/event-log read lands.
    assert coord_husk == coord_ctx.coord_feature_dir

    # A PRIMARY-partition kind resolves a DIFFERENT dir — collapsing the shared
    # status read onto it would break the coord-authority event-log read.
    primary_read = resolve_planning_read_dir(
        coord_ctx.repo, coord_ctx.slug, kind=MissionArtifactKind.WORK_PACKAGE_TASK
    )
    assert primary_read != coord_husk
    assert primary_read == coord_ctx.primary_feature_dir

    # The ONLY coord-husk-preserving kind for the shared status read is a
    # STATUS-partition kind — this is the pin move_task's guard may adopt while
    # keeping the event-log read byte-identical to the coord husk.
    status_read = resolve_planning_read_dir(
        coord_ctx.repo, coord_ctx.slug, kind=MissionArtifactKind.STATUS_STATE
    )
    assert status_read == coord_husk
