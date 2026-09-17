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

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn, TypeAlias

import typer

from mission_runtime import MissionArtifactKind, placement_seam
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
    from charter.profiles import AgentProfileRepository

    from specify_cli.core.stale_detection import StaleCheckResult

    # WP02 (charter-sole-door-bypass-closure-01KZ3WAA, FR-001), narrowed by
    # the landing-fold regression fix (defect 1): this alias previously
    # admitted EITHER the activation-*gated* ``dict`` from
    # ``charter.activation.resolver.DoctrineService.agent_profiles`` OR the raw
    # ``AgentProfileRepository`` from ``.agent_profile_repository``, on the
    # theory that both shapes only ever see ``.get(profile_id)`` calls here.
    # That theory was wrong: ``profile.sentinel`` (read inside
    # ``_get_hic_marker``) is a *structural* property, not an
    # activation-gated one -- exactly like ``get_provenance()``, which is why
    # ``charter.activation.resolver.DoctrineService`` gives callers
    # ``agent_profile_repository`` / ``raw_repository()`` in the first place.
    # A project that narrows ``activated_agent_profiles`` to exclude
    # ``human-in-charge`` silently lost the 👤 marker when a gated dict was
    # read here (measured: ``gated_dict.get('human-in-charge') -> None``).
    # Every production call site now builds the lookup via
    # ``.agent_profile_repository`` (never ``.agent_profiles``), so the type
    # is narrowed to the single shape that is actually correct -- a reader
    # can no longer mistake this for "either shape is fine."
    # Explicit TypeAlias: charter.profiles is mypy-quarantined
    # (follow_imports=skip), so AgentProfileRepository resolves to ``Any``; the
    # annotation makes ProfileLookup a valid type alias rather than an Any-valued
    # variable.
    ProfileLookup: TypeAlias = AgentProfileRepository
from specify_cli.missions._read_path_resolver import (
    candidate_feature_dir_for_mission,
)
from specify_cli.status import (
    PROGRESS_SEMANTICS,
    Lane,
    StatusEvent,
    StatusSnapshot,
    resolve_lane_alias,
)
from specify_cli.frontmatter import SHELL_PID_BASELINE_FIELD
from specify_cli.task_utils import extract_scalar, split_frontmatter
from specify_cli.workspace.context import get_normalized_wp


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
    # --- phase A: resolved dirs ---
    cwd: Path = field(default_factory=Path)
    repo_root: Path = field(default_factory=Path)
    mission_slug: str = ""
    main_repo_root: Path = field(default_factory=Path)
    feature_dir: Path = field(default_factory=Path)
    tasks_dir: Path = field(default_factory=Path)
    # --- phase B: loaded work packages + reduced snapshot ---
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

    st.mission_slug = _tasks._find_mission_slug(
        explicit_mission=st.mission,
        json_output=st.json_output,
        repo_root=repo_root,
        error_handler=_status_selector_error if st.json_output else None,
    )
    st.main_repo_root, _ = _tasks._ensure_target_branch_checked_out(repo_root, st.mission_slug, st.json_output)

    # Route through the single guarded read-side seam (WP01/IC-01; FR-002, C-007).
    from specify_cli.missions._read_path_resolver import (
        resolve_handle_to_read_path,
    )

    feature_dir = resolve_handle_to_read_path(st.main_repo_root, st.mission_slug)
    if not feature_dir.exists():
        # Last-ditch fallback to the original worktree-aware path so tests /
        # projects that stand up status files in unusual places still work.
        # F2 (WP01, #2947): this CWD-derived candidate can be a stale
        # coordination checkout, but it can no longer leak a stale LANE onto
        # the board -- ``_st_load_work_packages`` sources each row's lane
        # from committed authority (the PRIMARY surface) whenever that is
        # available, regardless of which ``feature_dir`` this resolution
        # picks. This fallback's closure is that downstream committed-lane
        # override, not a change to the existence-fallback path itself (which
        # stays load-bearing for legacy/no-primary-status fixtures --
        # ``docs/development/reference/read-side-seam-classification.md``).
        status_read_root = _tasks.get_status_read_root(st.cwd)
        legacy_dir = candidate_feature_dir_for_mission(status_read_root, st.mission_slug)
        if legacy_dir.exists():
            feature_dir = legacy_dir
        else:
            _status_error(st.json_output, f"Mission directory not found: {feature_dir}")
            raise typer.Exit(1)
    st.feature_dir = feature_dir

    # PRIMARY leg — tasks/ is PRIMARY-partition (FR-001 / C-001 per-leg split —
    # WP03 T009). The STATUS leg stays on the coord-aware ``feature_dir`` above.
    st.tasks_dir = placement_seam(st.main_repo_root, st.mission_slug).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK) / "tasks"
    if not st.tasks_dir.exists():
        _status_error(st.json_output, f"Tasks directory not found: {st.tasks_dir}")
        raise typer.Exit(1)


def _st_runtime_row(feature_dir: Path, wp_id: str | None) -> dict[str, Any]:
    """Return the WP's runtime-identity row fields through the ONE canonical reader.

    Routes the snapshot read through
    :func:`specify_cli.status.reconstruct_wp_view` (SC-007) — the reduced
    event-log snapshot is the unconditional authority (#2093/IC-03). An
    unidentifiable WP (no ``work_package_id``) or an absent slot yields empty
    strings, never a frontmatter fallback (C-001 — the phase-1 flag and its
    fallback are retired with the unconditional cutover).

    ``resolved_agent_profile`` / ``resolved_role`` / ``resolved_model`` are the
    DISTINCT resolved-binding actuals (empty when unrecorded). The board's authored
    ``agent_profile`` row field stays separate and feeds the HiC marker — the two
    are never conflated (C-008).
    """
    from specify_cli.status import reconstruct_wp_view

    if wp_id:
        resolved = reconstruct_wp_view(feature_dir, wp_id).resolved
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


def _st_gated_runtime_fields(feature_dir: Path, wp_id: str | None) -> tuple[str, str]:
    """Return ``(agent, shell_pid)`` through the one reconstruction reader (#2093).

    Back-compat accessor (surface pinned by ``test_tasks_compat_surface``):
    delegates to :func:`_st_runtime_row` so the snapshot read routes through the
    one reconstruction reader (SC-007) and never bypasses the single authority the
    rest of the reader path honours. Mirrors ``WorkPackage.agent``/``.shell_pid``.
    """
    row = _st_runtime_row(feature_dir, wp_id)
    return str(row["agent"]), str(row["shell_pid"])


def _st_resolve_execution_mode(front: str, main_repo_root: Path, mission_slug: str, wp_id: str | None) -> tuple[str, str]:
    """Resolve ``(execution_mode, workspace_kind)`` for one WP row (verbatim fallbacks)."""
    from specify_cli.cli.commands.agent import tasks as _tasks

    if wp_id is None:
        # No work_package_id in frontmatter — the workspace resolvers require a
        # WP id, so classification is impossible. Take the same frontmatter →
        # default path as the "resolver could not classify" arm below.
        return extract_scalar(front, "execution_mode") or "code_change", "unknown"
    try:
        workspace = _tasks.resolve_workspace_for_wp(main_repo_root, mission_slug, wp_id)
        return workspace.execution_mode, workspace.resolution_kind
    except MissingLanesError:
        # Without lanes.json the resolver cannot return a workspace, but we still
        # want a meaningful execution_mode. Prefer the explicit frontmatter value,
        # then the normalized default, and only fall back to "code_change" if both
        # are missing — never blank.
        execution_mode = extract_scalar(front, "execution_mode") or ""
        if not execution_mode:
            try:
                normalized = get_normalized_wp(main_repo_root, mission_slug, wp_id)
                execution_mode = normalized.metadata.execution_mode or "code_change"
            except Exception:
                execution_mode = "code_change"
        return execution_mode, "unknown"
    except (ValueError, FileNotFoundError):
        # Resolver could not classify; fall back to frontmatter and default.
        return extract_scalar(front, "execution_mode") or "code_change", "unknown"


def _st_load_work_packages(st: _StatusState) -> None:
    """Phase B: reduce the event log + collect the per-WP status rows.

    Loads canonical lanes from the event log (lane is event-log-only), then reads
    each WP's frontmatter into a status row and freezes the declared dependencies
    for the pure ``build_status_view`` readiness map.

    #3829 item 3 — one committed reduction per board: when the committed
    PRIMARY surface is authoritative for this mission
    (:func:`committed_authority.committed_status_dir` — merged + committed
    log present), the WHOLE row comes from that one dir: the lane, the
    companion fields (``resolved_agent_profile``/``resolved_model``/
    ``agent``/``shell_pid`` via ``reconstruct_wp_view``) AND the
    events/readiness reduction. Before this, only the lane was committed-
    sourced while the companions and the snapshot still read the possibly-
    stale coordination ``feature_dir`` — a merged mission rendered the
    correct committed lane beside stale coordination companions. When the
    committed surface is NOT authoritative (not merged / no committed log),
    ``status_read_dir`` IS ``st.feature_dir`` and every read is
    byte-identical to the coordination-aware board of before.
    """
    from runtime.next.committed_authority import committed_status_dir

    committed_dir = committed_status_dir(st.main_repo_root, st.mission_slug)
    status_read_dir = committed_dir if committed_dir is not None else st.feature_dir

    def _read_events_and_snapshot(read_dir: Path) -> None:
        from specify_cli.status import read_events as _st_read_events
        from specify_cli.status import reduce as _st_reduce

        st.events = _st_read_events(read_dir)
        st.snapshot = _st_reduce(st.events) if st.events else None

    try:
        _read_events_and_snapshot(status_read_dir)
    except Exception:
        # The board must render, not crash. A corrupt log on the committed
        # surface falls back to the coordination read (the pre-#3829
        # degrade); a corrupt coordination log degrades to no events, as
        # before.
        st.events = []
        if status_read_dir != st.feature_dir:
            try:
                _read_events_and_snapshot(st.feature_dir)
            except Exception:
                st.events = []

    # WP05: declared dependencies per WP id, frozen from the SAME frontmatter parse
    # already performed here (no extra file read).
    for wp_file in sorted(st.tasks_dir.glob("WP*.md")):
        front, body, padding = split_frontmatter(wp_file.read_text(encoding="utf-8"))

        wp_id = extract_scalar(front, "work_package_id")
        title = extract_scalar(front, "title")
        deps_raw = extract_scalar(front, "dependencies")
        if isinstance(deps_raw, list):
            wp_deps = [str(dep) for dep in deps_raw]
        elif deps_raw:
            wp_deps = [str(deps_raw)]
        else:
            wp_deps = []
        st.wp_dependencies[wp_id or wp_file.stem] = wp_deps
        execution_mode, workspace_kind = _st_resolve_execution_mode(front, st.main_repo_root, st.mission_slug, wp_id)
        # Route agent/shell_pid + the resolved-binding actuals through the ONE
        # reconstruction reader (SC-007). The authored ``agent_profile`` stays
        # frontmatter-canonical (design intent for the HiC marker) and DISTINCT
        # from ``resolved_agent_profile`` (what actually ran) — C-008.
        # #3829 item 3: the reader is pointed at the SAME one reduction the
        # lane came from — ``status_read_dir`` (the committed dir when the
        # committed surface is authoritative, the coordination ``feature_dir``
        # otherwise) — so a merged mission's row never mixes a committed lane
        # with stale coordination companions. A corrupt committed log
        # degrades per-WP to the coordination row (render, not crash) — the
        # same degrade the lane read had.
        try:
            _st_row = _st_runtime_row(status_read_dir, wp_id)
        except Exception:
            if status_read_dir == st.feature_dir:
                raise
            _st_row = _st_runtime_row(st.feature_dir, wp_id)
        row_lane = str(_st_row["lane"] or "")
        if committed_dir is not None:
            # The whole row is committed-sourced: a WP absent from the
            # committed snapshot renders genesis — never the stale
            # coordination lane beside committed companions, and never the
            # non-display ``uninitialized`` sentinel.
            lane_source = row_lane if row_lane and row_lane != Lane.UNINITIALIZED else str(Lane.GENESIS)
        else:
            lane_source = row_lane or str(Lane.GENESIS)
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

    st.review_stall_threshold = _tasks._review_stall_threshold_minutes(st.main_repo_root)
    st.stale_verdicts, st.stalled_wps = _apply_review_status_flags(
        st.work_packages,
        feature_dir=st.feature_dir,
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
        )
    except MissingLanesError as exc:
        stale_results = build_stale_fallback_results(doing_wps, exc)

    for wp in st.work_packages:
        if wp["lane"] == Lane.IN_PROGRESS and wp["id"] in stale_results:
            _tasks._apply_stale_status_fields(wp, stale_results[wp["id"]])

    auto_commit_enabled = _tasks.get_auto_commit_default(st.main_repo_root)
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
    print(ports.render.json_envelope(result))


def _st_board_cell(wp: Any, lane: Lane, main_repo_root: Path, profile_repo: ProfileLookup | None) -> str:
    """Build one kanban cell string (marker + stale/claimed/review decoration)."""
    from specify_cli.cli.commands.agent import tasks as _tasks

    title_truncated = wp["title"][:22] + "..." if len(wp["title"]) > 22 else wp["title"]
    marker = _tasks._get_hic_marker(wp.get("agent_profile"), main_repo_root, repo=profile_repo)
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


def _st_render_board(ports: TasksPorts, st: _StatusState, view: StatusView, profile_repo: ProfileLookup | None) -> None:
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
                row.append(_st_board_cell(lane_list[i], lane, st.main_repo_root, profile_repo))
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
        from specify_cli.review.arbiter import get_arbiter_overrides_for_wp

        arbiter_lines: list[str] = []
        for wp in st.work_packages:
            wp_id_raw = wp.get("id")
            wp_id_val = wp_id_raw if isinstance(wp_id_raw, str) else ""
            if not wp_id_val:
                continue
            overrides = get_arbiter_overrides_for_wp(st.feature_dir, wp_id_val)
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


def _st_render_review_queues(ports: TasksPorts, st: _StatusState, view: StatusView, profile_repo: ProfileLookup | None) -> None:
    """Render the for_review / approved / done-with-stale-verdict sections."""
    from specify_cli.cli.commands.agent import tasks as _tasks

    by_lane = view.lanes
    if by_lane[Lane.FOR_REVIEW]:
        ports.render.human("[bold cyan]👀 Ready for Review:[/bold cyan]")
        for wp in by_lane[Lane.FOR_REVIEW]:
            marker = _tasks._get_hic_marker(wp.get("agent_profile"), st.main_repo_root, repo=profile_repo)
            ports.render.human(f"  • {marker}{wp['id']} - {wp['title']}")
        ports.render.human("")

    if by_lane[Lane.APPROVED]:
        ports.render.human("[bold magenta]👍 Approved (merge when all WPs approved):[/bold magenta]")
        for wp in by_lane[Lane.APPROVED]:
            marker = _tasks._get_hic_marker(wp.get("agent_profile"), st.main_repo_root, repo=profile_repo)
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
            marker = _tasks._get_hic_marker(wp.get("agent_profile"), st.main_repo_root, repo=profile_repo)
            ports.render.human(f"  • {marker}{wp['id']} - {wp['title']}  [bold yellow]⚠ review artifact: verdict=rejected[/bold yellow]")
        ports.render.human("")


def _st_render_active(
    ports: TasksPorts,
    st: _StatusState,
    view: StatusView,
    stale_results: Any,
    profile_repo: ProfileLookup | None,
) -> None:
    """Render the claimed / in_progress / in_review sections via the Render port."""
    from specify_cli.cli.commands.agent import tasks as _tasks

    by_lane = view.lanes
    if by_lane[Lane.CLAIMED]:
        ports.render.human("[bold blue]🔄 Claimed (shown in Doing column):[/bold blue]")
        for wp in by_lane[Lane.CLAIMED]:
            marker = _tasks._get_hic_marker(wp.get("agent_profile"), st.main_repo_root, repo=profile_repo)
            agent = wp.get("agent", "unknown")
            ports.render.human(f"  • {marker}{wp['id']} - {wp['title']} [dim](agent: {agent})[/dim]")
        ports.render.human("")

    if by_lane[Lane.IN_PROGRESS]:
        ports.render.human("[bold blue]🔄 In Progress:[/bold blue]")
        stale_wps = []
        for wp in by_lane[Lane.IN_PROGRESS]:
            marker = _tasks._get_hic_marker(wp.get("agent_profile"), st.main_repo_root, repo=profile_repo)
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
            marker = _tasks._get_hic_marker(wp.get("agent_profile"), st.main_repo_root, repo=profile_repo)
            line = f"  • {marker}{wp['id']} - {wp['title']}"
            if wp.get("_stall_label"):
                line += f"  [bold yellow]⚠ {wp['_stall_label']}[/bold yellow]"
            ports.render.human(line)
        ports.render.human("")


def _st_render_planned(ports: TasksPorts, st: _StatusState, view: StatusView, profile_repo: ProfileLookup | None) -> None:
    """Render the "Next Up (Planned)" section via the Render port."""
    from specify_cli.cli.commands.agent import tasks as _tasks

    by_lane = view.lanes
    if by_lane[Lane.PLANNED]:
        ports.render.human("[bold yellow]📋 Next Up (Planned):[/bold yellow]")
        for wp in by_lane[Lane.PLANNED][:3]:
            marker = _tasks._get_hic_marker(wp.get("agent_profile"), st.main_repo_root, repo=profile_repo)
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

    auto_commit_enabled = _tasks.get_auto_commit_default(st.main_repo_root)
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
        )
    except MissingLanesError as exc:
        stale_results = build_stale_fallback_results(by_lane[Lane.IN_PROGRESS], exc)

    profile_repo: ProfileLookup | None = None
    # Lazy construction (NFR-005): skip the factory build entirely when no
    # rendered WP carries an ``agent_profile`` -- e.g. a freshly-tasked
    # mission where nothing has been claimed yet. This does not change the
    # populated-board cost (measured in
    # kitty-specs/charter-sole-door-bypass-closure-01KZ3WAA/traces/
    # tooling-friction.md), but it is a genuine, free win for the empty/
    # not-yet-started case that the removed bare ``AgentProfileRepository()``
    # construction paid unconditionally.
    _needs_profile_lookup = any(row.get("agent_profile") for rows in by_lane.values() for row in rows)
    if _needs_profile_lookup:
        try:
            # WP02 (charter-sole-door-bypass-closure-01KZ3WAA, FR-001): routed
            # through ``charter.activation.resolver.DoctrineService`` instead of
            # constructing ``AgentProfileRepository`` directly. The comment
            # this replaces named a "runtime -> charter -> doctrine boundary
            # ratchet" concern; R3 (research.md) confirms that ratchet only
            # scans MODULE-LEVEL ``from charter.offering.*`` imports, and both the old
            # direct-construction import and this factory import are
            # function-local, so the gate does not trip either way -- the
            # concern does not reappear.
            #
            # Landing-fold regression fix (defect 1): this site reads
            # ``.agent_profile_repository`` (the raw, unfiltered
            # ``AgentProfileRepository``), NOT the gated ``.agent_profiles``
            # dict it used before. ``_get_hic_marker`` only ever calls
            # ``.get(profile_id)`` here, but that call reads
            # ``profile.sentinel`` -- a *structural* property, not an
            # activation-gated one, exactly like ``get_provenance()``
            # (``charter/resolver.py``'s documented rationale for exposing
            # this same raw accessor). Reading the gated dict silently lost
            # the 👤 human-in-charge marker on any project that narrows
            # ``activated_agent_profiles`` to a set excluding
            # ``human-in-charge``.
            from charter.activation.doctrine_service_builder import (  # noqa: PLC0415
                build_activation_aware_doctrine_service,
            )

            profile_repo = build_activation_aware_doctrine_service(st.main_repo_root).agent_profile_repository
        except ImportError:
            # Genuinely-absent-module case only: ``charter`` is first-party
            # and ships in the same wheel, so this can only fire under a
            # broken/partial install. Any other failure here -- most
            # notably ``charter.activation.pack_context.CharterPackConfigError`` raised
            # by ``PackContext.from_config()`` for a malformed
            # ``.kittify/config.yaml`` -- MUST propagate to ``_do_status``'s
            # outer ``except Exception as e`` handler and surface as a
            # structured error (FR-002's fail-closed contract), not degrade
            # this dashboard to an unfiltered/markerless render silently.
            profile_repo = None

    for wp in by_lane[Lane.IN_PROGRESS]:
        wp_id = wp["id"]
        if wp_id in stale_results:
            _tasks._apply_stale_status_fields(wp, stale_results[wp_id])
        else:
            wp["is_stale"] = False

    _st_render_overview(ports, st, view)
    _st_render_board(ports, st, view, profile_repo)
    _st_render_arbiter(ports, st)
    _st_render_review_queues(ports, st, view, profile_repo)
    _st_render_active(ports, st, view, stale_results, profile_repo)
    _st_render_planned(ports, st, view, profile_repo)
    _st_render_summary(ports, st, view)


def _do_status(
    mission: str | None,
    json_output: bool,
    stale_threshold: int,
    *,
    ports: TasksPorts | None = None,
) -> None:
    """Orchestrate ``status`` over the WP05 ``build_status_view`` core + the Render port.

    ``ports=None`` builds the production bundle (Render bound to the module
    ``console`` with an ``indent=2`` JSON envelope). Tests inject a Fake bundle to
    observe the rendered views/envelopes (T032). The phase helpers run in the SAME
    order as the original single body: resolve → load → flag → render — so the
    WP05 byte-identical aggregation and the git/clock staleness sequence are intact.
    """

    ports = ports or _default_status_ports()
    st = _StatusState(mission=mission, json_output=json_output, stale_threshold=stale_threshold)
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
    repo: ProfileLookup | None = None,
) -> str:
    """Return a marker when the work package profile is a human-run sentinel.

    Accepts ``object`` because the callers read ``agent_profile`` out of the
    heterogeneous ``dict[str, object]`` status rows; a non-``str`` (or falsy)
    value yields no marker, exactly as the historical ``if not agent_profile``
    guard did for ``None``/empty strings.

    ``repo_root`` is read again as of WP02 (charter-sole-door-bypass-closure-
    01KZ3WAA): the self-resolving fallback (``repo=None``) now builds the
    charter-mediated, activation-aware profile map for this repo root rather
    than a bare built-in-only ``AgentProfileRepository()`` (FR-001). All 8
    production call sites always pass ``repo=`` explicitly, so this fallback
    only matters for direct/external callers.

    Landing-fold regression fix (defect 1): both this fallback and the
    ``repo=`` value built by the sibling call site (``_st_render_human``)
    now read ``.agent_profile_repository`` -- the raw, unfiltered
    ``AgentProfileRepository`` -- rather than ``.agent_profiles``, the
    activation-*gated* dict. ``profile.sentinel`` below is a structural
    property, not an activation-gated one (exactly like
    ``get_provenance()``, which is why ``charter.activation.resolver.DoctrineService``
    exposes ``agent_profile_repository`` in the first place); reading the
    gated dict silently dropped the 👤 marker on any project that narrows
    ``activated_agent_profiles`` to a set excluding ``human-in-charge``.
    """
    if not isinstance(agent_profile, str) or not agent_profile:
        return ""

    try:
        profile_repo = repo
        if profile_repo is None:
            # WP02 (charter-sole-door-bypass-closure-01KZ3WAA, FR-001): routed
            # through ``charter.activation.resolver.DoctrineService`` rather than
            # constructing ``AgentProfileRepository`` directly. As with the
            # sibling call site (``_st_render_human``), the removed comment's
            # "boundary ratchet" concern is confirmed a red herring (R3,
            # research.md): the existing gate only scans module-level
            # ``from charter.offering.*`` imports, and this import is function-local,
            # same as the construction it replaces. All 8 production callers
            # in this module always pass ``repo=`` explicitly (built once per
            # render in ``_st_render_human``), so this self-resolving fallback
            # only fires for direct/external callers (e.g. unit tests).
            from charter.activation.doctrine_service_builder import (  # noqa: PLC0415
                build_activation_aware_doctrine_service,
            )

            profile_repo = build_activation_aware_doctrine_service(repo_root).agent_profile_repository

        profile = profile_repo.get(agent_profile)
        if profile and profile.sentinel:
            return "👤 "
    except ImportError:
        # Genuinely-absent-module case only, matching the sibling call site
        # (``_st_render_human``): ``charter`` is first-party and ships in the
        # same wheel, so this can only fire under a broken/partial install.
        # Any other failure -- most notably
        # ``charter.activation.pack_context.CharterPackConfigError`` for a malformed
        # ``.kittify/config.yaml`` -- MUST propagate to the caller rather
        # than degrade this marker to a silent "" (FR-002's fail-closed
        # contract).
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
