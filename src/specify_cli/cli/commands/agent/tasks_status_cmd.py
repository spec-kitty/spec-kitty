"""The ``status`` command family, relocated out of ``tasks.py`` (WP07, #2058).

Mission ``tasks-py-degod-wave2-01KWH9EQ`` FR-001/FR-012: ``_do_status`` + the
14 ``_st_*`` phase helpers + ``_StatusState`` + ``_default_status_ports`` live
here, moved VERBATIM from ``tasks.py``. The module is named
``tasks_status_cmd`` (``_cmd`` suffix) to keep it distinct from the existing
``tasks_status_view`` module, which holds the WP05 PURE aggregation core
(``build_status_view`` / ``build_stale_fallback_results``) this command
orchestrates over. The ``@app.command`` Typer wrapper (``status``) stays in
``tasks.py`` and delegates to :func:`_do_status` (the byte-frozen ``--help``
surface is the registration shim's).

**Orchestration shape** (unchanged): the phase helpers run in the SAME order
as the original single body — resolve → load → flag → render — so the WP05
byte-identical aggregation and the git/clock staleness I/O sequence are intact
(NFR-002). ``_default_status_ports`` constructs ``RealRender(console=console,
indent=2)`` — the ONE indent=2 ``--json`` envelope (WP04 render-seam
unification, C-004); the ``print(ports.render.json_envelope(result))`` emission
moved verbatim inside ``_st_emit_json``.

**Seam bridge** (research.md D1/D7): the relocated bodies reach every patched
seam symbol through a lazy in-function import of the ``tasks`` module
(``from specify_cli.cli.commands.agent import tasks as _tasks``) and call
``_tasks.<attr>(...)``, so every historical ``@patch("...agent.tasks.<sym>")``
/ ``monkeypatch.setattr(tasks, ...)`` keeps INTERCEPTING after the move —
including the ``build_status_view`` sentinel seam
(test_tasks_status_view.py ×2), the conftest ``console`` rebinding, and the
port-adapter construction inside ``_default_status_ports``. ``tasks.py``
re-imports the family in the explicit ``as`` re-export form, so
``tasks.<name>`` stays a module attribute. Symbols with ZERO patch sites and a
canonical home outside ``tasks.py`` are imported directly at module scope
(cycle-safe: none of those modules import ``tasks``).

Per-symbol routing/interception evidence:
``kitty-specs/tasks-py-degod-wave2-01KWH9EQ/seam-checklist.md`` (Layer 4 of
the parity contract).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn, TypeAlias

import typer

from mission_runtime import MissionArtifactKind, OwnedCheckout, placement_seam
from specify_cli.agent_tasks_ports import TasksPorts
from specify_cli.cli.commands.agent.tasks_parsing_validation import (
    _apply_review_status_flags,
)
from specify_cli.cli.commands.agent.tasks_status_view import (
    StatusRequest,
    StatusView,
    build_stale_fallback_results,
)
from specify_cli.lanes.persistence import MissingLanesError

if TYPE_CHECKING:
    from specify_cli.core.stale_detection import StaleCheckResult
    from specify_cli.status import StatusReadSurface

from specify_cli.missions._read_path_resolver import (
    StatusReadPathNotFound,
    candidate_feature_dir_for_mission,
)
from specify_cli.status import (
    PROGRESS_SEMANTICS,
    Lane,
    StatusEvent,
    StatusSnapshot,
    read_authored_wp_frontmatter_lenient,
    resolve_lane_alias,
)
from specify_cli.frontmatter import SHELL_PID_BASELINE_FIELD, FrontmatterError
from specify_cli.task_utils import extract_scalar, split_frontmatter
from specify_cli.workspace.context import get_normalized_wp

logger = logging.getLogger(__name__)

#: The 👤 sentinel map one render builds for the profile ids its rows name
#: (#6917): ``{profile_id: profile.sentinel}``, produced once per render by
#: ``charter.activation.active_charter_service_builder.build_agent_profile_sentinels``
#: and read by ``_get_hic_marker``. Keyed exactly on the ids the board names, so a
#: render never materialises the profile catalogue.
SentinelMap: TypeAlias = "Mapping[str, bool]"


def _default_status_ports() -> TasksPorts:
    """Production port bundle for ``status`` (render bound to the module console).

    The ``--json`` leg is the ONE indent=2 envelope, absorbed by the single
    production adapter's constructor (WP04 render-seam unification; C-004
    one-adapter-per-port). Binding the module ``console`` keeps the byte-frozen
    human render AND the ``@patch("...tasks.console.print")`` seams intercepting.
    """
    from specify_cli.cli.commands.agent import tasks as _tasks

    return TasksPorts(
        fs=_tasks.RealFsReader(),
        coord=_tasks.RealCoordCommitRouter(),
        git=_tasks.RealGitOps(),
        render=_tasks.RealRender(console=_tasks.console, indent=2),
    )


@dataclass
class _StatusState:
    """Mutable orchestration state threaded through ``status``'s phases.

    The single-body command tracked ~20 loose locals across resolve → load →
    flag → render; the phase helpers exchange this one value object instead. Not
    frozen: each phase fills its own slice in the SAME order the original body
    did, so the git/clock staleness I/O — and its exact sequence — stays inside
    the shell (WP05 aggregation parity, NFR-002).
    """

    # --- raw command inputs ---
    mission: str | None
    json_output: bool
    stale_threshold: int
    owned_claim: Path | None = None
    # --- phase A: resolved dirs ---
    cwd: Path = field(default_factory=Path)
    repo_root: Path = field(default_factory=Path)
    # The validated ownership fact (owned-checkout-lifecycle-authority WP09).
    # Owned reads carry this and use ONLY its fields (``owned_root`` /
    # ``mission_dir`` / ``target_branch``) -- never a bare Path derived from
    # it (G4/G5). ``None`` for every non-owned run.
    owned: OwnedCheckout | None = None
    mission_slug: str = ""
    main_repo_root: Path = field(default_factory=Path)
    feature_dir: Path = field(default_factory=Path)
    tasks_dir: Path = field(default_factory=Path)
    # --- phase B: loaded work packages + reduced snapshot ---
    # The one declared status source (ADR 2026-11-06-2, #7335): every status
    # field on the board (lanes, companions, review verdict, arbiter override)
    # comes from this surface's ONE reduction, held in ``wp_states``.
    status_surface: StatusReadSurface | None = None
    wp_states: dict[str, dict[str, Any]] = field(default_factory=dict)
    events: list[StatusEvent] = field(default_factory=list)
    snapshot: StatusSnapshot | None = None
    work_packages: list[dict[str, object]] = field(default_factory=list)
    wp_dependencies: dict[str, list[str]] = field(default_factory=dict)
    # --- phase C: review-status flags ---
    review_stall_threshold: int = 0
    stale_verdicts: list[dict[str, object]] = field(default_factory=list)
    stalled_wps: list[dict[str, object]] = field(default_factory=list)


def _status_error(json_output: bool, message: str) -> None:
    """Render status failures at the command boundary."""
    from specify_cli.cli.commands.agent import tasks as _tasks
    from specify_cli.cli.json_contract import json_error

    if json_output:
        _tasks.console.emit_json(json_error("status_failed", message))
    else:
        _tasks._output_error(False, message)


def _status_selector_error(code: str, message: str, exit_code: int, details: dict[str, object]) -> NoReturn:
    """Adapt selector diagnostics before legacy delegates render any output."""
    from specify_cli.cli.commands.agent import tasks as _tasks
    from specify_cli.cli.json_contract import json_error

    _tasks.console.emit_json({**json_error(code, message), **details})
    raise typer.Exit(exit_code)


def _st_resolve_owned(st: _StatusState, repo_root: Path, explicit_mission: str | None) -> bool:
    """Resolve the owned-checkout fact (owned-checkout-lifecycle-authority WP09, FR-004).

    Returns ``True`` when the caller holds (or was adopted into) an owned
    checkout and ``st``'s dir fields are fully populated from the fact --
    the caller must return immediately, skipping
    ``_ensure_target_branch_checked_out`` (R's branch is irrelevant to an
    owned run) and the ``get_status_read_root`` fallback below it entirely.
    Returns ``False`` for the ordinary (non-owned, non-adopted) path, which
    proceeds exactly as before this WP (G2: no direct
    ``resolve_owned_mission`` / ``adopt_owned_checkout`` call here -- only
    the shared ``resolve_owned_or_adopt`` seam).
    """
    from mission_runtime import ActionContextError
    from specify_cli.cli.commands._owned_checkout import (
        emit_owned_refusal,
        resolve_owned_or_adopt,
    )
    from specify_cli.core.owned_mission import LIFECYCLE_OWNED_TOPOLOGIES

    try:
        owned = resolve_owned_or_adopt(
            repo_root,
            st.owned_claim,
            explicit_mission,
            cwd=st.cwd,
            allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES,
        )
    except ActionContextError as exc:
        emit_owned_refusal(exc, json_output=st.json_output)

    if owned is None:
        return False

    st.owned = owned
    st.mission_slug = owned.mission_slug
    st.main_repo_root = owned.repository_root
    st.feature_dir = owned.mission_dir
    st.tasks_dir = placement_seam(owned.repository_root, owned.mission_slug, owned=owned).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK) / "tasks"
    return True


def _st_resolve_dirs(st: _StatusState) -> None:
    """Phase A: repo/mission resolution + the CWD-independent read-dir resolution.

    Write path keeps main-repo-root resolution so canonical serialization pins to
    the primary checkout; the read path routes through the canonical resolver
    (WP08 T037, FR-030) with the legacy worktree-aware fallback preserved.
    """
    from specify_cli.cli.commands.agent import tasks as _tasks

    st.cwd = Path.cwd().resolve()
    repo_root = _tasks.locate_project_root(st.cwd)
    if repo_root is None:
        _status_error(st.json_output, "Not in a spec-kitty project")
        raise typer.Exit(1)
    st.repo_root = repo_root

    # owned-checkout-lifecycle-authority WP09 review cycle 1 issue 4: owned
    # resolution runs on the RAW (possibly ``None``) ``--mission`` value,
    # before the #4677 R-scoped sole-active-mission default below ever
    # computes anything. Two failure modes this closes:
    #   - ``--owned-checkout P`` without ``--mission`` used to have R's sole
    #     active mission silently substituted in, then resolved against P --
    #     it must instead reach ``resolve_owned_mission``'s own
    #     "--owned-checkout requires an explicit --mission" refusal.
    #   - flagless adoption (no ``--owned-checkout``) from a foreign checkout
    #     without ``--mission`` used to fall through to R's default and
    #     render R's UNRELATED mission -- adoption needs a handle
    #     (``adopt_owned_checkout`` returns ``None`` without one), so it is
    #     never triggered by this reordering alone.
    if _st_resolve_owned(st, repo_root, st.mission):
        return

    # #4677: an omitted --mission defaults to the sole active mission (maintainer
    # decision on the issue); zero or several active missions fall through to
    # the existing "--mission <slug> is required" error in ``_find_mission_slug``.
    # Issue 4 (cycle 3): the default is skipped ONLY when the invoking
    # checkout would be adopted as an owned checkout -- asked of the single
    # adoption authority (``invoking_checkout_would_adopt``), over the
    # checkout's own missions. R, lane/coordination worktrees (listed or
    # stale) and plain linked checkouts adopt nothing and keep #4677's behaviour.
    explicit_mission = st.mission
    if not (explicit_mission and explicit_mission.strip()):
        from specify_cli.cli.commands.agent.mission_feature_resolution import _sole_active_mission_slug_or_none
        from specify_cli.core.owned_mission import invoking_checkout_would_adopt

        candidate = _sole_active_mission_slug_or_none(repo_root)
        if candidate is not None and not invoking_checkout_would_adopt(repo_root, st.cwd):
            explicit_mission = candidate

    st.mission_slug = _tasks._find_mission_slug(
        explicit_mission=explicit_mission,
        json_output=st.json_output,
        repo_root=repo_root,
        error_handler=_status_selector_error if st.json_output else None,
    )
    st.main_repo_root, _ = _tasks._ensure_target_branch_checked_out(repo_root, st.mission_slug, st.json_output)

    # ``feature_dir`` is the Mission identity anchor (``_mission_identity_payload``)
    # and the "Mission directory not found" check only. It is NOT a status source:
    # every status field reads the read door's surface (``_st_status_surface``,
    # ADR 2026-11-06-2, #7335), so neither this resolution nor its CWD fallback
    # can put another log on the board.
    from specify_cli.missions._read_path_resolver import (
        resolve_handle_to_read_path,
    )

    feature_dir = resolve_handle_to_read_path(st.main_repo_root, st.mission_slug)
    if not feature_dir.exists():
        # Last-ditch fallback to the original worktree-aware path for the
        # identity anchor (legacy/no-primary-status fixtures --
        # ``docs/development/reference/read-side-seam-classification.md``).
        # It feeds no status read (#7335).
        status_read_root = _tasks.get_status_read_root(st.cwd)
        legacy_dir = candidate_feature_dir_for_mission(status_read_root, st.mission_slug)
        if legacy_dir.exists():
            feature_dir = legacy_dir
        else:
            _status_error(st.json_output, f"Mission directory not found: {feature_dir}")
            raise typer.Exit(1)
    st.feature_dir = feature_dir

    # PRIMARY leg — tasks/ is PRIMARY-partition (FR-001 / C-001 per-leg split —
    # WP03 T009). The STATUS leg is the read door's surface (``_st_status_surface``).
    st.tasks_dir = placement_seam(st.main_repo_root, st.mission_slug).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK) / "tasks"
    if not st.tasks_dir.exists():
        _status_error(st.json_output, f"Tasks directory not found: {st.tasks_dir}")
        raise typer.Exit(1)


def _st_runtime_row(state: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return the WP's runtime-identity row fields from its ONE reduced state.

    *state* is ``snapshot.work_packages[wp_id]`` of the board's single reduction
    of the door's surface (:func:`_st_load_work_packages`, #7335), assembled
    through the same resolved-group builder as
    :func:`specify_cli.status.reconstruct_wp_view` (SC-007) — the reduced
    event-log snapshot is the unconditional authority (#2093/IC-03). An
    unidentifiable WP (no ``work_package_id``) or an absent slot (``None``)
    yields empty strings, never a frontmatter fallback (C-001 — the phase-1 flag
    and its fallback are retired with the unconditional cutover).

    ``resolved_agent_profile`` / ``resolved_role`` / ``resolved_model`` are the
    DISTINCT resolved-binding actuals (empty when unrecorded). The board's authored
    ``agent_profile`` row field stays separate and feeds the HiC marker — the two
    are never conflated (C-008).
    """
    from specify_cli.status import resolved_group_from_state

    if state is not None:
        resolved = resolved_group_from_state(state)
        return {
            "lane": resolved.lane or "",
            "agent": resolved.agent or "",
            "assignee": resolved.assignee or "",
            "shell_pid": resolved.shell_pid or "",
            "shell_pid_created_at": resolved.shell_pid_created_at or "",
            "subtasks": dict(resolved.subtasks),
            "review": resolved.review,
            "resolved_agent_profile": resolved.agent_profile or "",
            "resolved_agent_profile_version": resolved.agent_profile_version or "",
            "resolved_role": resolved.role or "",
            "resolved_model": resolved.model or "",
            "resolved_provider": resolved.provider or "",
        }
    return {
        "lane": "",
        "agent": "",
        "assignee": "",
        "shell_pid": "",
        "shell_pid_created_at": "",
        "subtasks": {},
        "review": None,
        "resolved_agent_profile": "",
        "resolved_agent_profile_version": "",
        "resolved_role": "",
        "resolved_model": "",
        "resolved_provider": "",
    }


def _st_resolve_execution_mode(front: str, main_repo_root: Path, mission_slug: str, wp_id: str | None, *, owned: OwnedCheckout | None = None) -> tuple[str, str]:
    """Resolve ``(execution_mode, workspace_kind)`` for one WP row (verbatim fallbacks)."""
    from specify_cli.cli.commands.agent import tasks as _tasks

    if wp_id is None:
        # No work_package_id in frontmatter — the workspace resolvers require a
        # WP id, so classification is impossible. Take the same frontmatter →
        # default path as the "resolver could not classify" arm below.
        return extract_scalar(front, "execution_mode") or "code_change", "unknown"
    try:
        # Keep the ``_tasks.`` attribute route (module docstring): historical
        # ``@patch("...agent.tasks.resolve_workspace_for_wp")`` seams must
        # keep intercepting.
        workspace = _tasks.resolve_workspace_for_wp(main_repo_root, mission_slug, wp_id, owned=owned)
        return workspace.execution_mode, workspace.resolution_kind
    except MissingLanesError:
        # Without lanes.json the resolver cannot return a workspace, but we still
        # want a meaningful execution_mode. Prefer the explicit frontmatter value,
        # then the normalized default, and only fall back to "code_change" if both
        # are missing — never blank.
        execution_mode = extract_scalar(front, "execution_mode") or ""
        if not execution_mode:
            try:
                normalized = get_normalized_wp(main_repo_root, mission_slug, wp_id, owned=owned)
                execution_mode = normalized.metadata.execution_mode or "code_change"
            except Exception:
                execution_mode = "code_change"
        return execution_mode, "unknown"
    except (ValueError, FileNotFoundError):
        # Resolver could not classify; fall back to frontmatter and default.
        return extract_scalar(front, "execution_mode") or "code_change", "unknown"


def _st_status_surface(st: _StatusState) -> StatusReadSurface:
    """The board's one declared status source (ADR 2026-11-06-2, #7335, #7408).

    The read door decides the source for every topology and coordination state:
    a landed Mission reads ``CONSOLIDATED_TARGET`` (the one landed signal, which
    replaced the board's own ``committed_status_dir`` probe), an unmaterialized
    coordination worktree reads the committed coordination branch (where the
    board used to read the PRIMARY copy), and an owned run reads the validated
    owned checkout. A door refusal (deleted coordination branch, unreadable ref,
    unreadable worktree registry) fails the command closed instead of rendering
    a board from another source.
    """
    from specify_cli.status import resolve_status_read

    try:
        return resolve_status_read(st.main_repo_root, st.mission_slug, owned=st.owned)
    except (OSError, ValueError, RuntimeError, StatusReadPathNotFound) as exc:
        _status_error(st.json_output, f"Cannot resolve the status source for {st.mission_slug}: {exc}")
        raise typer.Exit(1) from exc


def _st_reduce_surface(st: _StatusState, surface: StatusReadSurface) -> None:
    """Read the surface once; every status field of the board reads the result.

    ``st.events`` / ``st.snapshot`` keep their lane-transition-only shape (the
    readiness reduction); ``st.wp_states`` is the full reduction (transitions and
    annotations) the row companions, review verdict and arbiter override read.
    A log that cannot be read or parsed fails the command closed (exit 1): an
    empty board would read as "no progress", and the board has no second source
    to fall back to. An unreadable ref is the door's typed refusal and propagates
    (never an empty history).
    """
    from specify_cli.status import StoreError, read_status_stream, reduce

    try:
        stream = read_status_stream(surface)
    except (StoreError, OSError, ValueError) as exc:
        _status_error(st.json_output, f"The status log of {st.mission_slug} cannot be read: {exc}")
        raise typer.Exit(1) from exc
    st.events = list(stream.transitions)
    st.snapshot = reduce(st.events) if st.events else None
    st.wp_states = {wp_id: dict(state) for wp_id, state in reduce(stream.transitions, stream.annotations).work_packages.items()}


def _st_config_root(st: _StatusState) -> Path:
    """The checkout every configuration/doctrine read resolves from (WP09, FR-004).

    ``st.owned.owned_root`` (P) for an owned run, ``st.main_repo_root`` (R)
    otherwise. A derived helper, not a new ``Path`` field on
    :class:`_StatusState` -- gate G5 bans a bare owned root stored
    independently of the fact, and this is the honest form: every owned
    config/doctrine read resolves from P.
    """
    return st.owned.owned_root if st.owned is not None else st.main_repo_root


def _st_declared_dependencies(wp_file: Path) -> list[str]:
    """Read one WP's declared dependencies through the canonical typed parser (#5435).

    ``WPMetadata.dependencies`` is the field the dependency gate reads
    (``core.dependency_graph.parse_wp_dependencies``), and it answers ``[]`` for
    an empty flow list (``dependencies: []``) and expands every entry of a flow
    list and of a block list. The previous raw ``extract_scalar`` read reported
    the literal ``"[]"`` as one dependency named ``"[]"`` and fused a flow list
    into one string.

    The reader is the AUTHORED one (no runtime-field re-point): ``dependencies``
    is frontmatter-canonical, and a board over a corrupt status log must not
    crash on a dependency read when it already degrades that log. A WP file the
    typed parser refuses degrades to "no declared dependencies" for the same
    reason. The LENIENT authored reader is used so an unknown frontmatter key
    (the strict schema forbids extras) does not erase real dependencies and
    show a gated WP as ready; known fields are still validated, so only
    genuinely malformed frontmatter degrades.
    """
    try:
        meta, _body = read_authored_wp_frontmatter_lenient(wp_file)
    except (FrontmatterError, OSError, ValueError) as exc:  # pydantic.ValidationError is a ValueError
        logger.debug("status: unparseable frontmatter in %s: %s", wp_file, exc)
        return []
    return list(meta.dependencies)


def _st_load_work_packages(st: _StatusState) -> None:
    """Phase B: reduce the event log + collect the per-WP status rows.

    Loads canonical lanes from the event log (lane is event-log-only), then reads
    each WP's frontmatter into a status row and freezes the declared dependencies
    for the pure ``build_status_view`` readiness map.

    One source, read once per board (#3829 item 3, #7335): the read door
    (:func:`_st_status_surface`) declares the source and
    :func:`_st_reduce_surface` reads it once; the lane, the companion fields
    (``resolved_agent_profile``/``resolved_model``/``agent``/``shell_pid``), the
    review verdict and the arbiter override all read that reduction, so a row
    never mixes two sources. A landed Mission's source is
    ``CONSOLIDATED_TARGET``, where a WP absent from the snapshot renders genesis.
    """
    from specify_cli.status import StatusReadSource

    st.status_surface = _st_status_surface(st)
    _st_reduce_surface(st, st.status_surface)
    committed_authoritative = st.status_surface.source is StatusReadSource.CONSOLIDATED_TARGET

    # WP05: declared dependencies per WP id, read through the canonical parser the
    # dependency gate enforces (#5435) so the readiness map matches the gate.
    for wp_file in sorted(st.tasks_dir.glob("WP*.md")):
        front, body, padding = split_frontmatter(wp_file.read_text(encoding="utf-8"))

        wp_id = extract_scalar(front, "work_package_id")
        title = extract_scalar(front, "title")
        st.wp_dependencies[wp_id or wp_file.stem] = _st_declared_dependencies(wp_file)
        execution_mode, workspace_kind = _st_resolve_execution_mode(front, st.main_repo_root, st.mission_slug, wp_id, owned=st.owned)
        # agent/shell_pid + the resolved-binding actuals come from the SAME one
        # reduction the lane came from (SC-007, #3829 item 3, #7335), so a row
        # never mixes two sources. The authored ``agent_profile`` stays
        # frontmatter-canonical (design intent for the HiC marker) and DISTINCT
        # from ``resolved_agent_profile`` (what actually ran) — C-008.
        _st_row = _st_runtime_row(st.wp_states.get(wp_id) if wp_id else None)
        row_lane = str(_st_row["lane"] or "")
        # The whole row is committed-sourced when authoritative: a WP absent
        # from the committed snapshot renders genesis — never the stale
        # coordination lane beside committed companions, and never the
        # non-display ``uninitialized`` sentinel.
        lane_source = (row_lane if row_lane and row_lane != Lane.UNINITIALIZED else str(Lane.GENESIS)) if committed_authoritative else row_lane or str(Lane.GENESIS)
        lane = resolve_lane_alias(lane_source)
        st.work_packages.append(
            {
                "id": wp_id,
                "title": title,
                "lane": lane,
                "phase": extract_scalar(front, "phase") or "Unknown Phase",
                "file": wp_file.name,
                "agent": _st_row["agent"],
                "agent_profile": extract_scalar(front, "agent_profile") or "",
                "resolved_agent_profile": _st_row["resolved_agent_profile"],
                "resolved_role": _st_row["resolved_role"],
                "resolved_model": _st_row["resolved_model"],
                "shell_pid": _st_row["shell_pid"],
                # PID-reuse identity baseline (FR-005/#2575), co-written with
                # shell_pid at claim time. Post-#2816 it is a runtime slot sourced
                # from the reduced snapshot through the SAME reconstruction reader
                # as ``shell_pid`` (never frontmatter) — the two doors stay
                # consistent. Threaded here so check_doing_wps_for_staleness can
                # compare it (recycled-PID -> stale-eligible). Both the JSON
                # (_st_emit_json) and human (_st_render_human) staleness paths read
                # this same dict object -- _kanban_rollup groups by reference, so a
                # single addition here feeds both consumers. ``or None`` preserves
                # the additive-degradation contract (absent baseline -> None, D3a).
                SHELL_PID_BASELINE_FIELD: _st_row["shell_pid_created_at"] or None,
                "execution_mode": execution_mode,
                "workspace_kind": workspace_kind,
            }
        )


def _st_apply_review_flags(st: _StatusState) -> None:
    """Phase C: annotate rows with stale-verdict + stalled-review warnings."""
    from specify_cli.cli.commands.agent import tasks as _tasks

    st.review_stall_threshold = _tasks._review_stall_threshold_minutes(_st_config_root(st))
    st.stale_verdicts, st.stalled_wps = _apply_review_status_flags(
        st.work_packages,
        wp_states=st.wp_states,
        events=st.events,
        stall_threshold_minutes=st.review_stall_threshold,
    )


def _st_emit_json(st: _StatusState, ports: TasksPorts) -> None:
    """JSON leg: apply the git-staleness I/O, run the WP05 core, emit via the Render port.

    T031: the ``--json`` envelope is assembled from the pure ``build_status_view``
    aggregation and serialised through ``ports.render.json_envelope`` (``indent=2``
    for ``status``'s own render binding — byte-identical to the pre-rewire dump).
    """
    from specify_cli.cli.commands.agent import tasks as _tasks
    from specify_cli.core.stale_detection import check_doing_wps_for_staleness

    doing_wps = [wp for wp in st.work_packages if wp["lane"] == Lane.IN_PROGRESS]
    try:
        stale_results = check_doing_wps_for_staleness(
            main_repo_root=st.main_repo_root,
            mission_slug=st.mission_slug,
            doing_wps=doing_wps,
            threshold_minutes=st.stale_threshold,
            owned=st.owned,
        )
    except MissingLanesError as exc:
        stale_results = build_stale_fallback_results(doing_wps, exc)

    for wp in st.work_packages:
        if wp["lane"] == Lane.IN_PROGRESS and wp["id"] in stale_results:
            _tasks._apply_stale_status_fields(wp, stale_results[wp["id"]])

    auto_commit_enabled = _tasks.get_auto_commit_default(_st_config_root(st))
    # WP05: the pure aggregation core owns the kanban rollup + counts + percentages.
    view = _tasks.build_status_view(
        StatusRequest(
            work_packages=st.work_packages,
            snapshot=st.snapshot,
            wp_dependencies=st.wp_dependencies,
        )
    )
    result: dict[str, object] = {
        **_tasks._mission_identity_payload(st.feature_dir),
        "total_wps": view.total_wps,
        "by_lane": dict(view.lane_counts),
        "work_packages": st.work_packages,
        "progress_percentage": view.progress_percentage,
        "progress_semantics": PROGRESS_SEMANTICS,
        "weighted_percentage": view.progress_percentage,
        "done_count": view.done_count,
        "done_percentage": view.done_percentage,
        "stale_wps": view.stale_count,
        "stale_verdicts": st.stale_verdicts,
        "stalled_wps": st.stalled_wps,
        "auto_commit": auto_commit_enabled,
    }
    if st.owned is not None:
        # FR-007: additive-only in owned runs; non-owned payloads never carry
        # this key (WP08's envelope rule).
        from specify_cli.cli.commands._owned_checkout import stale_copy_payload

        result.update(stale_copy_payload(st.owned))
    print(ports.render.json_envelope(result))


def _st_board_cell(wp: Any, lane: Lane, main_repo_root: Path, sentinels: SentinelMap | None) -> str:
    """Build one kanban cell string (marker + stale/claimed/review decoration)."""
    from specify_cli.cli.commands.agent import tasks as _tasks

    title_truncated = wp["title"][:22] + "..." if len(wp["title"]) > 22 else wp["title"]
    marker = _tasks._get_hic_marker(wp.get("agent_profile"), main_repo_root, sentinels=sentinels)
    display_id = f"{marker}{wp['id']}"
    if wp.get("_stale_verdict"):
        return f"[yellow]⚠ {display_id}[/yellow]\n{title_truncated}"
    if lane == Lane.IN_PROGRESS and wp.get("is_stale"):
        return f"[red]⚠️ {display_id}[/red]\n{title_truncated}"
    if wp.get("_stall_label"):
        return f"[yellow]⚠ {display_id} (review)[/yellow]\n{title_truncated}"
    if wp.get("_display_claimed"):
        return f"[blue]{display_id} (claimed)[/blue]\n{title_truncated}"
    if wp.get("_display_in_review"):
        return f"[bright_cyan]{display_id} (review)[/bright_cyan]\n{title_truncated}"
    return f"{display_id}\n{title_truncated}"


def _st_render_overview(ports: TasksPorts, st: _StatusState, view: StatusView) -> None:
    """Render the title panel + done/weighted progress bar via the Render port."""
    from rich.panel import Panel
    from rich.text import Text

    title_text = Text()
    title_text.append("📊 Work Package Status: ", style="bold cyan")
    title_text.append(st.mission_slug, style="bold white")

    ports.render.human("")
    ports.render.human(Panel(title_text, border_style="cyan"))

    progress_text = Text()
    progress_text.append("Done progress: ", style="bold")
    progress_text.append(f"{view.done_count}/{view.total_wps}", style="bold green")
    progress_text.append(f" ({view.done_percentage}%)", style="dim")
    progress_text.append("\nWeighted readiness: ", style="bold")
    progress_text.append(f"{view.progress_percentage}%", style="bold cyan")

    bar_width = 40
    filled = int(bar_width * view.progress_percentage / 100)
    bar = "█" * filled + "░" * (bar_width - filled)
    progress_text.append(f"\n{bar}", style="green")

    ports.render.human(progress_text)
    ports.render.human("")


def _st_render_board(ports: TasksPorts, st: _StatusState, view: StatusView, sentinels: SentinelMap | None) -> None:
    """Render the kanban board table via the Render port.

    Folds claimed + in_review WPs into the "Doing" column with markers; the row
    objects are the SAME ``view.lanes`` objects, so display-marker mutations
    propagate. GENESIS is excluded; off-board rows land in the "other" bucket.
    """
    from rich.table import Table

    by_lane = view.lanes
    display_in_progress = []
    for wp in by_lane[Lane.CLAIMED]:
        wp["_display_claimed"] = True
        display_in_progress.append(wp)
    display_in_progress.extend(by_lane[Lane.IN_PROGRESS])
    for wp in by_lane.get(Lane.IN_REVIEW, []):
        wp["_display_in_review"] = True
        display_in_progress.append(wp)

    table = Table(title="Kanban Board", show_header=True, header_style="bold magenta", border_style="dim")
    table.add_column("📋 Planned", style="yellow", no_wrap=False, width=25)
    table.add_column("🔄 Doing", style="blue", no_wrap=False, width=25)
    table.add_column("👀 For Review", style="cyan", no_wrap=False, width=25)
    table.add_column("👍 Approved", style="magenta", no_wrap=False, width=25)
    table.add_column("✅ Done", style="green", no_wrap=False, width=25)

    max_rows = max(len(by_lane[Lane.PLANNED]), len(display_in_progress), len(by_lane[Lane.FOR_REVIEW]), len(by_lane[Lane.APPROVED]), len(by_lane[Lane.DONE]))

    display_columns = [
        (Lane.PLANNED, by_lane[Lane.PLANNED]),
        (Lane.IN_PROGRESS, display_in_progress),
        (Lane.FOR_REVIEW, by_lane[Lane.FOR_REVIEW]),
        (Lane.APPROVED, by_lane[Lane.APPROVED]),
        (Lane.DONE, by_lane[Lane.DONE]),
    ]

    for i in range(max_rows):
        row = []
        for lane, lane_list in display_columns:
            if i < len(lane_list):
                row.append(_st_board_cell(lane_list[i], lane, st.main_repo_root, sentinels))
            else:
                row.append("")
        table.add_row(*row)

    table.add_row(
        f"[bold]{len(by_lane[Lane.PLANNED])} WPs[/bold]",
        f"[bold]{len(display_in_progress)} WPs[/bold]",
        f"[bold]{len(by_lane[Lane.FOR_REVIEW])} WPs[/bold]",
        f"[bold]{len(by_lane[Lane.APPROVED])} WPs[/bold]",
        f"[bold]{len(by_lane[Lane.DONE])} WPs[/bold]",
        style="dim",
    )

    ports.render.human(table)
    ports.render.human("")


def _st_render_arbiter(ports: TasksPorts, st: _StatusState) -> None:
    """Render the arbiter-override history section via the Render port (T034)."""
    try:
        from specify_cli.review.arbiter import arbiter_overrides_from_state

        arbiter_lines: list[str] = []
        for wp in st.work_packages:
            wp_id_raw = wp.get("id")
            wp_id_val = wp_id_raw if isinstance(wp_id_raw, str) else ""
            if not wp_id_val:
                continue
            overrides = arbiter_overrides_from_state(st.wp_states.get(wp_id_val))
            for idx, override in enumerate(overrides, start=1):
                cat = override.get("category", "custom")
                arbiter_lines.append(f"  • {wp_id_val} Cycle {idx}: rejected → [yellow]overridden[/yellow] ({cat})")

        if arbiter_lines:
            ports.render.human("[bold yellow]⚖️  Arbiter Override History:[/bold yellow]")
            for line in arbiter_lines:
                ports.render.human(line)
            ports.render.human("")
    except ImportError:
        pass  # review package not yet available


def _st_render_review_queues(ports: TasksPorts, st: _StatusState, view: StatusView, sentinels: SentinelMap | None) -> None:
    """Render the for_review / approved / done-with-stale-verdict sections."""
    from specify_cli.cli.commands.agent import tasks as _tasks

    by_lane = view.lanes
    if by_lane[Lane.FOR_REVIEW]:
        ports.render.human("[bold cyan]👀 Ready for Review:[/bold cyan]")
        for wp in by_lane[Lane.FOR_REVIEW]:
            marker = _tasks._get_hic_marker(wp.get("agent_profile"), st.main_repo_root, sentinels=sentinels)
            ports.render.human(f"  • {marker}{wp['id']} - {wp['title']}")
        ports.render.human("")

    if by_lane[Lane.APPROVED]:
        ports.render.human("[bold magenta]👍 Approved (merge when all WPs approved):[/bold magenta]")
        for wp in by_lane[Lane.APPROVED]:
            marker = _tasks._get_hic_marker(wp.get("agent_profile"), st.main_repo_root, sentinels=sentinels)
            line = f"  • {marker}{wp['id']} - {wp['title']}"
            if wp.get("_stale_verdict"):
                line += "  [bold yellow]⚠ review artifact: verdict=rejected[/bold yellow]"
            ports.render.human(line)
        ports.render.human("[dim]   Approved WPs stay here until feature merge. Dependents can start immediately.[/dim]")
        ports.render.human("")

    done_stale = [wp for wp in by_lane[Lane.DONE] if wp.get("_stale_verdict")]
    if done_stale:
        ports.render.human("[bold green]✅ Done (with stale verdict warnings):[/bold green]")
        for wp in done_stale:
            marker = _tasks._get_hic_marker(wp.get("agent_profile"), st.main_repo_root, sentinels=sentinels)
            ports.render.human(f"  • {marker}{wp['id']} - {wp['title']}  [bold yellow]⚠ review artifact: verdict=rejected[/bold yellow]")
        ports.render.human("")


def _st_render_active(
    ports: TasksPorts,
    st: _StatusState,
    view: StatusView,
    stale_results: Any,
    sentinels: SentinelMap | None,
) -> None:
    """Render the claimed / in_progress / in_review sections via the Render port."""
    from specify_cli.cli.commands.agent import tasks as _tasks

    by_lane = view.lanes
    if by_lane[Lane.CLAIMED]:
        ports.render.human("[bold blue]🔄 Claimed (shown in Doing column):[/bold blue]")
        for wp in by_lane[Lane.CLAIMED]:
            marker = _tasks._get_hic_marker(wp.get("agent_profile"), st.main_repo_root, sentinels=sentinels)
            agent = wp.get("agent", "unknown")
            ports.render.human(f"  • {marker}{wp['id']} - {wp['title']} [dim](agent: {agent})[/dim]")
        ports.render.human("")

    if by_lane[Lane.IN_PROGRESS]:
        ports.render.human("[bold blue]🔄 In Progress:[/bold blue]")
        stale_wps = []
        for wp in by_lane[Lane.IN_PROGRESS]:
            marker = _tasks._get_hic_marker(wp.get("agent_profile"), st.main_repo_root, sentinels=sentinels)
            stale_label = _tasks._render_stale_status(stale_results.get(wp["id"]))
            agent = wp.get("agent", "unknown")
            if wp.get("is_stale"):
                ports.render.human(f"  • [red]⚠️ {marker}{wp['id']}[/red] - {wp['title']} [dim]({stale_label}, agent: {agent})[/dim]")
                stale_wps.append(wp)
            elif stale_label:
                ports.render.human(f"  • {marker}{wp['id']} - {wp['title']} [dim]({stale_label}, agent: {agent})[/dim]")
            else:
                ports.render.human(f"  • {marker}{wp['id']} - {wp['title']}")
        ports.render.human("")

        if stale_wps:
            ports.render.human(f"[yellow]⚠️  {len(stale_wps)} stale WP(s) detected - agents may have stopped without transitioning[/yellow]")
            ports.render.human("[dim]   Run: spec-kitty agent tasks move-task <WP_ID> --to for_review[/dim]")
            ports.render.human("")

    if by_lane.get(Lane.IN_REVIEW):
        ports.render.human("[bold bright_cyan]🔍 In Review (shown in Doing column):[/bold bright_cyan]")
        for wp in by_lane[Lane.IN_REVIEW]:
            marker = _tasks._get_hic_marker(wp.get("agent_profile"), st.main_repo_root, sentinels=sentinels)
            line = f"  • {marker}{wp['id']} - {wp['title']}"
            if wp.get("_stall_label"):
                line += f"  [bold yellow]⚠ {wp['_stall_label']}[/bold yellow]"
            ports.render.human(line)
        ports.render.human("")


def _st_render_planned(ports: TasksPorts, st: _StatusState, view: StatusView, sentinels: SentinelMap | None) -> None:
    """Render the "Next Up (Planned)" section via the Render port."""
    from specify_cli.cli.commands.agent import tasks as _tasks

    by_lane = view.lanes
    if by_lane[Lane.PLANNED]:
        ports.render.human("[bold yellow]📋 Next Up (Planned):[/bold yellow]")
        for wp in by_lane[Lane.PLANNED][:3]:
            marker = _tasks._get_hic_marker(wp.get("agent_profile"), st.main_repo_root, sentinels=sentinels)
            ports.render.human(f"  • {marker}{wp['id']} - {wp['title']}")
        if len(by_lane[Lane.PLANNED]) > 3:
            ports.render.human(f"  [dim]... and {len(by_lane[Lane.PLANNED]) - 3} more[/dim]")
        ports.render.human("")


def _st_render_summary(ports: TasksPorts, st: _StatusState, view: StatusView) -> None:
    """Render the summary panel + the "Next action" hint via the Render port."""
    from specify_cli.cli.commands.agent import tasks as _tasks
    from rich.panel import Panel
    from rich.table import Table

    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold")
    summary.add_column()
    summary.add_row("Total WPs:", str(view.total_wps))
    summary.add_row("Completed:", f"[green]{view.done_count}[/green] ({view.done_percentage}%)")
    summary.add_row("Weighted readiness:", f"[cyan]{view.progress_percentage}%[/cyan]")
    summary.add_row("In Progress:", f"[blue]{view.in_progress_count}[/blue]")
    summary.add_row("Planned:", f"[yellow]{view.planned_count}[/yellow]")

    auto_commit_enabled = _tasks.get_auto_commit_default(_st_config_root(st))
    auto_commit_label = "[green]enabled[/green]" if auto_commit_enabled else "[yellow]disabled[/yellow]"
    summary.add_row("Auto-commit:", auto_commit_label)

    ports.render.human(Panel(summary, title="[bold]Summary[/bold]", border_style="dim"))

    ports.render.human("[bold]▶ Next action:[/bold]")
    ports.render.human(f"  [cyan]spec-kitty next --agent <your-name> --mission {st.mission_slug}[/cyan]")
    ports.render.human("[dim]  This command tells you exactly what to do next based on the dependency graph.[/dim]")
    ports.render.human("")


def _st_render_human(st: _StatusState, ports: TasksPorts) -> None:
    """Human leg: run the WP05 core, apply staleness, render the board via the Render port.

    T031: every emission routes through ``ports.render.human`` (bound to the module
    ``console`` in production — byte-identical + patch-seam-preserving). The pure
    ``build_status_view`` owns the rollup/counts; the shell owns only the
    git/clock staleness I/O and the drawing.
    """
    from specify_cli.cli.commands.agent import tasks as _tasks
    from specify_cli.core.stale_detection import check_doing_wps_for_staleness

    if st.owned is not None:
        # FR-007: human mode's stale-copy warning goes to stderr; non-owned
        # runs never call this (WP08's envelope rule).
        from specify_cli.cli.commands._owned_checkout import echo_stale_copy_warning

        echo_stale_copy_warning(st.owned)

    view = _tasks.build_status_view(
        StatusRequest(
            work_packages=st.work_packages,
            snapshot=st.snapshot,
            wp_dependencies=st.wp_dependencies,
        )
    )
    by_lane = view.lanes

    try:
        stale_results = check_doing_wps_for_staleness(
            main_repo_root=st.main_repo_root,
            mission_slug=st.mission_slug,
            doing_wps=by_lane[Lane.IN_PROGRESS],
            threshold_minutes=st.stale_threshold,
            owned=st.owned,
        )
    except MissingLanesError as exc:
        stale_results = build_stale_fallback_results(by_lane[Lane.IN_PROGRESS], exc)

    # Lazy read (#6917): skip the lookup entirely when no rendered WP carries an
    # ``agent_profile`` -- e.g. a freshly-tasked mission where nothing has been
    # claimed yet.
    sentinels: SentinelMap | None = None
    _profile_ids = sorted(
        {row["agent_profile"] for rows in by_lane.values() for row in rows if isinstance(row.get("agent_profile"), str) and row.get("agent_profile")}
    )
    if _profile_ids:
        try:
            # ISSUE #6917: one id-scoped structural read replaces the whole
            # ``ActiveCharterService`` build plus the complete
            # ``AgentProfileRepository`` (26 shipped profile documents and the
            # lineage graph) this site used to pay for one boolean per row.
            # ``build_agent_profile_sentinels`` resolves only the ids below,
            # through the same built-in → org → project layers and the same
            # loader, and consults no activation *state* because ``sentinel`` is
            # a *structural* property, not an activation-gated one (the
            # charter-sole-door-bypass-closure-01KZ3WAA rationale for
            # ``agent_profile_repository``); it does build a ``PackContext`` for
            # its side effect of validating the config. The marker therefore
            # still survives a narrowed or denied ``activated_agent_profiles``.
            from charter.activation.active_charter_service_builder import (  # noqa: PLC0415
                build_agent_profile_sentinels,
            )

            sentinels = build_agent_profile_sentinels(_st_config_root(st), _profile_ids)
        except ImportError:
            # Genuinely-absent-module case only: ``charter`` is first-party
            # and ships in the same wheel, so this can only fire under a
            # broken/partial install. Any other failure here -- most
            # notably the charter configuration error the builder raises for a
            # malformed or invalid ``.kittify/config.yaml`` --
            # MUST propagate to ``_do_status``'s outer ``except Exception``
            # handler and surface as a structured error (FR-002's fail-closed
            # contract), not degrade this dashboard to a markerless render.
            # The builder validates ``.kittify/config.yaml`` through the charter
            # configuration authority before it reads any layer, so an unreadable
            # or invalid config raises here exactly as the activation-aware
            # service build did.
            sentinels = None

    for wp in by_lane[Lane.IN_PROGRESS]:
        wp_id = wp["id"]
        if wp_id in stale_results:
            _tasks._apply_stale_status_fields(wp, stale_results[wp_id])
        else:
            wp["is_stale"] = False

    _st_render_overview(ports, st, view)
    _st_render_board(ports, st, view, sentinels)
    _st_render_arbiter(ports, st)
    _st_render_review_queues(ports, st, view, sentinels)
    _st_render_active(ports, st, view, stale_results, sentinels)
    _st_render_planned(ports, st, view, sentinels)
    _st_render_summary(ports, st, view)


def _do_status(
    mission: str | None,
    json_output: bool,
    stale_threshold: int,
    *,
    ports: TasksPorts | None = None,
    owned_claim: Path | None = None,
) -> None:
    """Orchestrate ``status`` over the WP05 ``build_status_view`` core + the Render port.

    ``ports=None`` builds the production bundle (Render bound to the module
    ``console`` with an ``indent=2`` JSON envelope). Tests inject a Fake bundle to
    observe the rendered views/envelopes (T032). The phase helpers run in the SAME
    order as the original single body: resolve → load → flag → render — so the
    WP05 byte-identical aggregation and the git/clock staleness sequence are intact.
    """

    ports = ports or _default_status_ports()
    st = _StatusState(mission=mission, json_output=json_output, stale_threshold=stale_threshold, owned_claim=owned_claim)
    try:
        _st_resolve_dirs(st)
        _st_load_work_packages(st)
        _st_apply_review_flags(st)
        if st.json_output:
            _st_emit_json(st, ports)
            return
        if not st.work_packages:
            ports.render.human(f"[yellow]No work packages found in {st.tasks_dir}[/yellow]")
            return
        _st_render_human(st, ports)
    except typer.Exit:
        raise
    except Exception as e:
        _status_error(json_output, str(e))
        raise typer.Exit(1) from None


# ===========================================================================
# WP09 (tasks-py-degod-wave2-01KWH9EQ / FR-008, IC-07): the final
# registration-shim sweep relocates the status-family stragglers that remained
# ``tasks.py``-resident after WP07 — the review-stall threshold reader
# (``_review_stall_threshold_minutes``), the human-in-charge marker
# (``_get_hic_marker``) and the staleness shapers
# (``_apply_stale_status_fields`` / ``_render_stale_status``). Moved VERBATIM
# (no patched seam symbol appears in their bodies — the lazy ``yaml`` /
# doctrine-repository imports stay in-function). The family call sites above
# keep routing through ``_tasks.<attr>``, so the historical
# ``@patch("...agent.tasks.<sym>")`` contracts keep INTERCEPTING; ``tasks.py``
# re-imports each name in the explicit ``as`` re-export form (NFR-002).
# ===========================================================================


def _review_stall_threshold_minutes(repo_root: Path) -> int:
    """Read review.stall_threshold_minutes from .kittify/config.yaml."""
    config_file = repo_root / ".kittify" / "config.yaml"
    if not config_file.exists():
        return 30
    try:
        import yaml  # noqa: PLC0415

        config: dict[str, Any] = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
        value = config.get("review", {}).get("stall_threshold_minutes", 30)
        return int(value)
    except (AttributeError, OSError, TypeError, ValueError):
        return 30


def _get_hic_marker(
    agent_profile: object,
    repo_root: Path,
    *,
    sentinels: SentinelMap | None = None,
) -> str:
    """Return the 👤 marker when the work package profile is a human-run sentinel.

    Accepts ``object`` because the callers read ``agent_profile`` out of the
    heterogeneous ``dict[str, object]`` status rows; a non-``str`` (or falsy)
    value yields no marker, exactly as the historical ``if not agent_profile``
    guard did for ``None``/empty strings.

    ``sentinels`` is the per-render map built by ``_st_render_human`` from the
    ids the board's rows name (issue #6917). All production call sites pass it,
    so a render parses only those profile documents instead of the whole
    catalogue. ``sentinels=None`` is the self-resolving fallback for
    direct/external callers: it resolves this one id through
    ``build_agent_profile_sentinels``, which stays inside the charter sole door,
    answers ``profile.sentinel`` (a *structural* property, never
    activation-gated), and consults no activation state.
    """
    if not isinstance(agent_profile, str) or not agent_profile:
        return ""

    try:
        if sentinels is None:
            from charter.activation.active_charter_service_builder import (  # noqa: PLC0415
                build_agent_profile_sentinels,
            )

            sentinels = build_agent_profile_sentinels(repo_root, [agent_profile])

        if sentinels.get(agent_profile, False):
            return "👤 "
    except ImportError:
        # Genuinely-absent-module case only, matching the sibling call site
        # (``_st_render_human``): ``charter`` is first-party and ships in the
        # same wheel, so this can only fire under a broken/partial install.
        # Any other failure -- most notably the charter configuration error the
        # builder's layer resolution raises for a malformed
        # ``.kittify/config.yaml`` -- MUST propagate to the caller rather than
        # degrade this marker to a silent "" (FR-002's fail-closed contract).
        return ""

    return ""


def _apply_stale_status_fields(wp: dict[str, Any], stale_result: StaleCheckResult) -> None:
    """Populate canonical and deprecated stale fields from one source of truth."""
    stale_payload = stale_result.stale.to_dict()
    wp["stale"] = stale_payload
    wp["is_stale"] = stale_result.is_stale
    wp["minutes_since_commit"] = stale_payload["minutes_since_commit"]
    wp["worktree_exists"] = stale_result.worktree_exists


def _render_stale_status(stale_result: StaleCheckResult | None) -> str | None:
    """Return a human-readable stale label for in-progress work packages."""
    if stale_result is None:
        return None

    if stale_result.stale.status == "not_applicable" and stale_result.stale.reason == "planning_artifact_repo_root_shared_workspace":
        return "stale: n/a (repo-root planning work)"

    if getattr(stale_result, "error", None):
        return "stale: unavailable"

    if stale_result.is_stale:
        mins = stale_result.minutes_since_commit
        return f"stale: {mins}m"

    return None
