"""Injected capability ports for the ``agent tasks`` command surface (WP02).

Co-designed capability boundary for the ``tasks.py`` de-god program
(``tasks-py-degod-01KWF08S``) and reused by Wave 2. The four ports are
**stratified** (research D2):

* **Program-reference ports** (Wave 2 reuses these):
  - :class:`FsReader` — coordination **READ** authority (C-001). Never conflates
    with the write authority.
  - :class:`CoordCommitRouter` — coordination **WRITE** authority, exposing
    **two capability methods over two structurally disjoint real seams**
    (:meth:`~CoordCommitRouter.commit_status` over
    ``emit_status_transition_transactional`` and
    :meth:`~CoordCommitRouter.commit_artifact` over ``commit_for_mission``).
    NOT a fused ``commit()`` — the Wave-2 consumers use disjoint halves
    (``implement.py`` = status only; ``acceptance`` = artifact only; ``move_task``
    = both), so a single fused method is re-cut in Wave 2 (the C-006 failure).
* **Mission-local seams** (scaffolding for ``tasks.py`` testability only; #2173
  DROPs both, so they are explicitly NOT advertised as program-reference ports):
  - :class:`GitOps` — porcelain reads.
  - :class:`Render` — dual-arm output (``human`` + ``json_envelope``).

Injection contract (C-005 / research D5): every orchestrator is
``_do_<cmd>(..., *, ports: TasksPorts | None = None)``; ``None`` builds the Real
bundle via :func:`default_ports`. The Typer ``@app.command`` never sees ``ports``
(a Protocol-typed parameter on a decorated command collides with Typer
introspection). This WP delivers the boundary + the FR-010 dir-equivalence proof;
it does NOT thin the command bodies (that is WP06+).

Note: ``__all__`` is intentionally omitted. This module is imported directly by
the thin orchestrators and tests, while the former CLI-local path remains a
compatibility shim.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TypedDict, runtime_checkable

from rich.console import Console

from kernel.git import status_entries

from mission_runtime import (
    MissionArtifactKind,
    OwnedCheckout,
    PlacementSeam,
    placement_seam,
)
from specify_cli.core.commit_guard import GuardCapability
from specify_cli.core.paths import locate_project_root
from specify_cli.coordination.commit_router import (
    CommitRouterResult,
    commit_for_mission,
)
from specify_cli.coordination.status_transition import (
    emit_status_transition_transactional,
)
from specify_cli.git.protection_policy import ProtectionPolicy
from specify_cli.missions._read_path_resolver import (
    resolve_feature_dir_for_mission,
)
from specify_cli.status import StatusEvent, TransitionRequest

# ---------------------------------------------------------------------------
# Mission identity value object
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MissionHandle:
    """Repository/mission identity plus an optional owned working checkout.

    The canonical resolvers take ``(repo_root, mission_slug)``; this frozen pair
    threads them through the ports as one value so the orchestrators pass a single
    handle instead of re-plumbing both arguments at every call.
    """

    repo_root: Path
    mission_slug: str
    owned: OwnedCheckout | None = None


# ---------------------------------------------------------------------------
# Result value objects
# ---------------------------------------------------------------------------
# Renamed off ``CommitResult`` — that name is taken by ``git/commit_helpers.py``
# (line 424); reusing it here would collide (research D10).


@dataclass(frozen=True)
class CommitStatusResult:
    """Outcome of :meth:`CoordCommitRouter.commit_status`.

    ``event`` is the ``StatusEvent`` the transactional emitter persisted (``None``
    only when the transition was skipped). ``skipped`` carries the coord
    skip-exit-0 decision so the caller reads a field instead of forking on a
    side-effect (data-model §Ports).
    """

    event: StatusEvent | None
    skipped: bool = False


@dataclass(frozen=True)
class CommitArtifactResult:
    """Outcome of :meth:`CoordCommitRouter.commit_artifact`.

    Mirrors the useful surface of ``commit_router.CommitRouterResult`` while
    keeping the port result decoupled from that concrete type (and off the
    ``CommitResult`` name).
    """

    status: str
    placement_ref: str
    commit_hash: str | None = None
    diagnostic: str | None = None


# ---------------------------------------------------------------------------
# Port protocols (T008)
# ---------------------------------------------------------------------------


@runtime_checkable
class FsReader(Protocol):
    """Coordination **READ** authority (C-001, PROGRAM-REFERENCE).

    Wraps the kind-aware read seam; never conflates with the write authority.
    """

    def planning_read_dir(
        self, mission: MissionHandle, *, kind: MissionArtifactKind
    ) -> Path:
        """Resolve the read dir for one artifact ``kind`` (per-kind partition)."""
        ...

    def wp_tasks_dir(self, mission: MissionHandle) -> Path:
        """Resolve the ``tasks/`` WP-prompt directory (PRIMARY partition)."""
        ...

    def primary_anchor_dir(self, mission: MissionHandle) -> Path:
        """Resolve the topology-blind PRIMARY anchor dir.

        Routes through the kind-aware placement seam
        (``placement_seam(...).read_dir(PRIMARY_METADATA)``, read-side-seam-
        primary-primitive-closure-01KYKMMT WP04/WP08), which folds the handle
        to its canonical form internally -- no caller-side canonicalizer fold
        is co-located here (C-002; drained WP08 T036).
        """
        ...


@runtime_checkable
class CoordCommitRouter(Protocol):
    """Coordination **WRITE** authority (C-001, PROGRAM-REFERENCE).

    Two capability methods over two structurally disjoint real seams
    (research D2) — NOT a fused ``commit()``.
    """

    def feature_write_dir(self, mission: MissionHandle) -> Path:
        """The kind-blind coord-husk write leg (``resolve_feature_dir_for_mission``)."""
        ...

    def commit_status(
        self,
        request: TransitionRequest,
        *,
        capability: GuardCapability,
    ) -> CommitStatusResult:
        """Commit a status transition over ``emit_status_transition_transactional``.

        Keyed on :class:`GuardCapability`; self-atomic via
        ``BookkeepingTransaction`` inside the emitter. The ``TransitionRequest``
        is the SINGLE identity source (it already carries ``repo_root`` /
        ``mission_slug`` / ``feature_dir`` — see the ``move_task`` call site) — so
        this leg takes NO separate ``MissionHandle``: a second identity source
        would be exactly the split-brain this program removes (binding refinement
        of the indicative Phase-1 contract). The persisted ``StatusEvent`` is
        carried back on :attr:`CommitStatusResult.event`. Used by ``implement.py``
        and ``move_task``.
        """
        ...

    def commit_artifact(
        self,
        mission: MissionHandle,
        paths: Sequence[Path],
        message: str,
        *,
        kind: MissionArtifactKind,
        policy: ProtectionPolicy,
    ) -> CommitArtifactResult:
        """Commit an artifact over ``commit_for_mission`` (event-LESS).

        Keyed on :class:`MissionArtifactKind` + a ``ProtectionPolicy``. Used by
        ``acceptance`` (protected-primary routing) and ``move_task``.
        """
        ...


@runtime_checkable
class GitOps(Protocol):
    """Porcelain reads used by ``tasks.py`` only (MISSION-LOCAL; #2173 DROP)."""

    def is_dirty(self, path: Path) -> bool:
        """True when the working tree at ``path`` has uncommitted changes."""
        ...

    def current_branch(self, path: Path) -> str:
        """The current branch name at ``path``."""
        ...

    def is_protected(self, branch: str) -> bool:
        """True when ``branch`` is a protected ref."""
        ...


@runtime_checkable
class Render(Protocol):
    """Output surface (MISSION-LOCAL; #2173 DROP). Dual-arm: human + JSON."""

    def human(self, view: object) -> None:
        """Render ``view`` for a human (rich tables/panels)."""
        ...

    def json_envelope(self, payload: Mapping[str, object]) -> str:
        """Return the ``--json`` envelope string for ``payload``."""
        ...


# ---------------------------------------------------------------------------
# Real adapters (T009) — wrap the canonical seams, never stubs
# ---------------------------------------------------------------------------


class _OwnedKwargs(TypedDict, total=False):
    owned: OwnedCheckout


def _owned_kwargs(mission: MissionHandle) -> _OwnedKwargs:
    """``{"owned": mission.owned}`` or ``{}`` (C-001 byte-parity).

    A non-owned handle must produce NO extra keyword on the injected
    ``commit_fn`` (several tests assert the exact mock call shape).
    """
    return {"owned": mission.owned} if mission.owned is not None else {}


def _placement_for(mission: MissionHandle) -> PlacementSeam:
    """Resolve one shared :class:`PlacementSeam` for ``mission`` (T036).

    Routes through the fact when the handle holds one; otherwise the
    non-owned seam.
    """
    return placement_seam(mission.repo_root, mission.mission_slug, owned=mission.owned)


class RealFsReader:
    """Real :class:`FsReader` over the canonical read-path resolvers."""

    def planning_read_dir(
        self, mission: MissionHandle, *, kind: MissionArtifactKind
    ) -> Path:
        # read-side-placement-seam-migration WP07: a direct 1:1 swap onto the
        # kind-aware seam (fail-loud on a deleted-coord mismatch, NFR-002) —
        # ``resolve_planning_read_dir(root, slug, kind=kind)`` →
        # ``PlacementSeam(root, slug).read_dir(kind)``.
        # Annotated local: the project runs mypy with ``follow_imports = "skip"``,
        # so the imported (typed ``-> Path``) resolver surfaces as ``Any`` here;
        # the annotation re-pins the known concrete type without a suppression.
        read_dir: Path = _placement_for(mission).read_dir(kind)
        return read_dir

    def wp_tasks_dir(self, mission: MissionHandle) -> Path:
        feature_dir: Path = _placement_for(mission).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)
        return feature_dir / "tasks"

    def primary_anchor_dir(self, mission: MissionHandle) -> Path:
        # read-side-seam-primary-primitive-closure-01KYKMMT WP04 (FR-004):
        # routed through the kind-aware placement seam directly rather than
        # the now-bypassed ``primary_feature_dir_for_mission`` wrapper -- every
        # PRIMARY-partition kind resolves to the identical anchor (P-1), so
        # ``PRIMARY_METADATA`` stands in for this port's own topology-blind
        # answer (the wrapper's own body was exactly this seam call).
        # WP08 (T036): the caller-side canonicalizer fold DROPPED -- it is
        # redundant with the seam's OWN internal fold. For a PRIMARY-partition
        # kind, ``read_dir`` folds the handle through this SAME
        # ``_canonicalize_primary_read_handle`` primitive before composing
        # (see ``resolve_planning_read_dir``'s PRIMARY leg), so pre-folding an
        # already-canonical or already-raw handle here achieves nothing the
        # seam does not already do — folding twice is idempotent, not merely
        # equivalent (the fold's own no-op leg for an unresolvable handle
        # returns it unchanged either way).
        anchor: Path = _placement_for(mission).read_dir(MissionArtifactKind.PRIMARY_METADATA)
        return anchor


#: Seam callable that wraps ``commit_for_mission`` — injected so a caller can
#: route the resolution through a different namespace (the coord families point
#: it at the ``tasks`` module so ``@patch("...agent.tasks.commit_for_mission")``
#: intercepts at CALL time, not construction time). Loosely typed on purpose:
#: under the project's ``follow_imports = "skip"`` the callee already surfaces as
#: ``Any`` and the family seam-wrappers use ``*args, **kwargs`` passthroughs.
_CommitForMissionFn = Callable[..., CommitRouterResult]

#: Seam callable that wraps ``emit_status_transition_transactional`` — injected
#: for the same late-binding reason as :data:`_CommitForMissionFn`.
_EmitTransactionalFn = Callable[..., StatusEvent]


class RealCoordCommitRouter:
    """Real :class:`CoordCommitRouter` over the two disjoint write seams.

    The two WRITE seams (``commit_for_mission`` / ``emit_status_transition_
    transactional``) and the optional ``target_branch`` are **constructor-
    injected** rather than subclassed (C-004, one adapter per port). The three
    coord families that previously subclassed this router — to (a) re-route their
    seams through the ``tasks`` module namespace so the historical
    ``@patch("...agent.tasks.<sym>")`` seams keep INTERCEPTING after the port
    rewire, and (b) thread ``target_branch`` (``map_requirements`` only) — now
    pass those behaviours in at construction via
    :func:`~specify_cli.cli.commands.agent.tasks_command_adapters.seam_coord_router`.

    The ``None`` defaults reproduce the base production behaviour byte-for-byte:
    the module-bound ``agent_tasks_ports`` seams and NO ff-advance. Late binding
    is preserved because the injected callables resolve their target at CALL
    time (the family wrappers do a lazy ``from ...agent import tasks`` import),
    so a ``@patch`` applied AFTER construction still intercepts.
    """

    def __init__(
        self,
        *,
        target_branch: str | None = None,
        thread_target_branch: bool = False,
        commit_fn: _CommitForMissionFn | None = None,
        emit_fn: _EmitTransactionalFn | None = None,
    ) -> None:
        self._target_branch = target_branch
        # ``thread_target_branch`` is a SEPARATE flag from the value (not
        # ``target_branch is not None``): it preserves the exact pre-collapse
        # call shape. ``map_requirements`` ALWAYS passed ``target_branch=<value>``
        # (even when the resolved value was ``None``); ``move_task`` /
        # ``mark_status`` NEVER passed the kwarg at all. Deriving the flag from
        # the value would collapse those two byte-distinct call shapes (C-001).
        self._thread_target_branch = thread_target_branch
        self._commit_fn = commit_fn or commit_for_mission
        self._emit_fn = emit_fn or emit_status_transition_transactional

    def feature_write_dir(self, mission: MissionHandle) -> Path:
        if mission.owned is not None:
            write_dir: Path = _placement_for(mission).read_dir(MissionArtifactKind.STATUS_STATE)
            return write_dir
        # Non-owned handles keep calling this resolver, byte-identical.
        write_dir = resolve_feature_dir_for_mission(
            mission.repo_root, mission.mission_slug
        )
        return write_dir

    def commit_status(
        self,
        request: TransitionRequest,
        *,
        capability: GuardCapability,
    ) -> CommitStatusResult:
        event: StatusEvent = self._emit_fn(request, capability=capability)
        return CommitStatusResult(event=event, skipped=False)

    def commit_artifact(
        self,
        mission: MissionHandle,
        paths: Sequence[Path],
        message: str,
        *,
        kind: MissionArtifactKind,
        policy: ProtectionPolicy,
    ) -> CommitArtifactResult:
        # C-001 byte-parity: thread ``target_branch`` ONLY when the family opted
        # in (map_requirements). The others omit the kwarg entirely so the mock
        # call shape stays identical to the pre-collapse inline call.
        # Owned kwargs (T036): pass ``owned=`` only when the handle holds a fact
        # (C-001 byte-parity).
        owned_kwargs = _owned_kwargs(mission)
        if self._thread_target_branch:
            result = self._commit_fn(
                mission.repo_root,
                mission.mission_slug,
                tuple(paths),
                message,
                policy,
                kind=kind,
                target_branch=self._target_branch,
                **owned_kwargs,
            )
        else:
            result = self._commit_fn(
                mission.repo_root,
                mission.mission_slug,
                tuple(paths),
                message,
                policy,
                kind=kind,
                **owned_kwargs,
            )
        return CommitArtifactResult(
            status=result.status,
            placement_ref=result.placement_ref,
            commit_hash=result.commit_hash,
            diagnostic=result.diagnostic,
        )


class RealGitOps:
    """Real :class:`GitOps` over ``git`` porcelain + the resolved protection policy."""

    def __init__(self, repo_root: Path | None = None) -> None:
        self._repo_root = repo_root or locate_project_root() or Path.cwd()

    def is_dirty(self, path: Path) -> bool:
        # Guard: a failed probe raises GitCommandError rather than reading as "clean".
        return bool(status_entries(path, untracked=None))

    def current_branch(self, path: Path) -> str:
        completed = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        return completed.stdout.strip()

    def is_protected(self, branch: str) -> bool:
        protected: bool = ProtectionPolicy.resolve(self._repo_root).is_protected(branch)
        return protected


class RealRender:
    """Real :class:`Render` over rich + ``json.dumps`` (default separators).

    ``indent`` is a constructor parameter, NOT a Protocol change (Wave-2 research
    D2 / C-004): the default ``None`` keeps the compact form byte-identical to
    the historical inline ``json.dumps(data)`` sites, while ``indent=2`` absorbs
    the ``status --json`` indented envelope without a second adapter class.
    """

    def __init__(
        self, console: Console | None = None, indent: int | None = None
    ) -> None:
        self._console = console or Console()
        self._indent = indent

    def human(self, view: object) -> None:
        self._console.print(view)

    def json_envelope(self, payload: Mapping[str, object]) -> str:
        # Default separators — ``json.dumps(payload, indent=None)`` is
        # byte-identical to ``json.dumps(payload)``, so the compact sites in
        # tasks.py stay byte-frozen (research D2/D10; parity obligation for
        # Render). NEVER add ``separators=``.
        return json.dumps(payload, indent=self._indent)


# ---------------------------------------------------------------------------
# Bundle + Real builder (T011)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TasksPorts:
    """The injected capability bundle (exactly four ports)."""

    fs: FsReader
    coord: CoordCommitRouter
    git: GitOps
    render: Render


def default_ports() -> TasksPorts:
    """Build the production (Real-adapter) bundle.

    This is what an orchestrator constructs when ``ports is None`` at the
    ``_do_<cmd>(*, ports=None)`` injection seam (C-005).
    """
    return TasksPorts(
        fs=RealFsReader(),
        coord=RealCoordCommitRouter(),
        git=RealGitOps(),
        render=RealRender(),
    )
