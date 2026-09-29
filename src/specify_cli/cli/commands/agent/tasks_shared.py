"""Cross-family shared helpers relocated out of ``tasks.py`` (WP02, #2058/#2305).

Mission ``tasks-py-degod-wave2-01KWH9EQ`` FR-002/FR-003: the ~20 helpers used
across the five ``agent tasks`` command families (or exported/patched as part
of the ``tasks`` compatibility surface) live here, moved VERBATIM from
``tasks.py``. Family-specific glue (``_mt_*``/``_mr_*``/``_st_*``/``_ms_*``/
``_ft_*``), the ``_do_*`` orchestrators, the port adapters, and the Typer
command bodies stay behind for their own relocation WPs.

**Seam bridge** (research.md D1, the ``mission_finalize.py`` template idiom):
``tasks.py`` re-imports every symbol defined here, so ``tasks.<name>`` remains
a module attribute and every historical ``@patch("...agent.tasks.<name>")`` /
``monkeypatch.setattr(tasks, "<name>")`` target keeps resolving. To make those
patches keep INTERCEPTING (not merely resolving), relocated bodies route every
call to a patched seam symbol — infra names from the D7 seam inventory
(``get_main_repo_root``, ``subprocess``, ``console``, ``ProtectionPolicy``,
``resolve_placement_only``, ``resolve_topology``,
``routes_through_coordination``, ``resolve_workspace_for_wp``, …) and moved
siblings — through a lazy in-function import of the ``tasks`` module
(``from specify_cli.cli.commands.agent import tasks as _tasks``) and call
``_tasks.<attr>(...)``. The lazy import is cycle-safe (never module scope).

Per-symbol routing/interception evidence:
``kitty-specs/tasks-py-degod-wave2-01KWH9EQ/seam-checklist.md`` (Layer 4 of
the parity contract); interception pins live in
``tests/specify_cli/cli/commands/agent/test_tasks_shared_seam.py``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, NoReturn, cast

import typer

from mission_runtime import (
    MissionArtifactKind,
    MissionTopology,
    kind_for_mission_file,
    kind_is_coordination_residue,
    placement_seam,
)
from specify_cli.agent_tasks_ports import Render
from specify_cli.coordination.surface_authority import (
    Refuse,
    RouteToCoord,
    resolve_surface_authority,
)
from specify_cli.cli.commands.agent.tasks_outline import TaskIdResolutionOutcome, TaskIdResult
from specify_cli.cli.commands.agent.tasks_parsing_validation import (
    _validate_ready_for_review as _seam_validate_ready_for_review,
)
from specify_cli.cli.commands.agent.tasks_handoff import (
    _canonical_final_head_status_replay,
    _fallback_planning_pin_is_trusted,
    _lane_commit_handoff_paths,
    _lane_history_commits,
    _unique_shared_snapshot,
)
from specify_cli.cli.selector_resolution import resolve_mission_handle
from specify_cli.core.constants import KITTY_SPECS_DIR, is_occurrence_map_path
from specify_cli.core.vcs.git import capture_branch_tip, git_diff_names_checked, git_merge_base
from specify_cli.mission_metadata import resolve_mission_identity
from specify_cli.missions._read_path_resolver import MissionSelectorAmbiguous
from specify_cli.status import is_dossier_snapshot as _is_dossier_snapshot

logger = logging.getLogger(__name__)


def _review_currency_check_branch(
    *,
    main_repo_root: Path,
    mission_slug: str,
    target_branch: str,
    workspace: object | None,
) -> str:
    from specify_cli.cli.commands.agent import tasks as _tasks

    context = getattr(workspace, "context", None)
    base_branch = getattr(context, "base_branch", None)
    if base_branch:
        return str(base_branch)

    try:
        # base-ref read under coord topology — coord kind preserves G-2
        # (write-surface-coherence WP02 / T031 site 3): review-currency compares
        # against the coordination BASE ref under coord topology. STATUS_STATE keeps
        # the coord ref; a primary kind would read the primary ref as the base and
        # corrupt the currency comparison.
        placement = _tasks.resolve_placement_only(
            main_repo_root, mission_slug, kind=MissionArtifactKind.STATUS_STATE
        )
    except Exception as exc:  # noqa: BLE001 -- legacy fixtures keep target-branch fallback
        logger.debug("Could not resolve review currency placement: %s", exc)
        return target_branch

    # FR-005 / FR-001b: the coord-vs-primary decision reads the WP02 STORED
    # topology via the ONE canonical predicate, never a per-ref ``.kind``.
    if _tasks.routes_through_coordination(_tasks.resolve_topology(main_repo_root, mission_slug)):
        coord_ref: str = placement.ref
        return coord_ref
    return target_branch


# ---------------------------------------------------------------------------
# FR-015 / C-003 / C-004: review-handoff runtime-state deny-list
# ---------------------------------------------------------------------------
# Spec-kitty writes review-lock.json and other ephemeral runtime state under
# ``.spec-kitty/`` inside each worktree, and merge/status metadata under
# ``.kittify/`` at the repo root. These directories are git-ignored but do
# show up in ``git status --porcelain`` as untracked noise, which historically
# tripped the "uncommitted changes in worktree" guard in
# ``_validate_ready_for_review`` when an external reviewer (the review lock)
# had only just done its job (issue #589).
#
# C-003: this is a *fixed named list*, NOT a pattern match. Do not add
# entries here without explicit spec coverage; re-opening the door to pattern
# matching lets untracked source files silently slip past the guard.
# C-004: paths OUTSIDE this list still reach the blocking branch unchanged,
# so genuine uncommitted implementation work continues to block review handoff.
_RUNTIME_STATE_DENY_LIST: tuple[str, ...] = (".spec-kitty/", ".kittify/")


# ---------------------------------------------------------------------------
# Mission charter-e2e-827-followups-01KQAJA0 / C-006: dossier snapshot exclude
# ---------------------------------------------------------------------------
# The dossier snapshot at <feature_dir>/.kittify/dossiers/<mission>/snapshot-
# latest.json is a mutable derived artifact. Per the EXCLUDE ownership policy
# (single policy — see ``specify_cli.status.preflight``), it must be filtered
# from any preflight that bypasses ``.gitignore`` so the writer's update does
# not self-block the next ``move-task`` transition.
def _filter_runtime_state_paths(porcelain_output: str) -> str:
    """Strip lines whose path falls under spec-kitty's own runtime-state dirs.

    Input is the raw ``git status --porcelain`` output. Each line has the
    format ``XY path`` where ``XY`` is a two-character status code followed by
    a single space. A ``startswith`` check against the fixed deny-list is
    used intentionally (C-003): no regex, no glob expansion, no fuzzy match.

    Dossier ``snapshot-latest.json`` paths are also stripped here per the
    EXCLUDE ownership policy (C-006); the snapshot writer must never
    self-block a transition.

    Returns a newline-joined string with deny-listed entries removed. Lines
    whose path is OUTSIDE the deny list are preserved verbatim so the
    downstream guard still blocks on genuine drift (C-004).
    """
    kept: list[str] = []
    for line in porcelain_output.splitlines():
        if not line.strip():
            continue
        # git status --porcelain format: first 3 chars are "XY " status prefix.
        path_part = line[3:] if len(line) > 3 else line.strip()
        if any(path_part.startswith(prefix) for prefix in _RUNTIME_STATE_DENY_LIST):
            continue
        if _is_dossier_snapshot(path_part):
            continue
        kept.append(line)
    return "\n".join(kept)


def _emit_sparse_session_warning(repo_root: Path, command: str) -> None:
    """Emit the FR-010/FR-019 sparse-checkout session warning once per process.

    Called from every state-mutating tasks handler at command entry so
    reviewers and implementers discover they are operating inside a
    sparse-checkout worktree before they commit partial work. The underlying
    ``warn_if_sparse_once`` helper from WP02 is self-memoizing (first caller
    wins the ``command`` label) and swallows detection errors, so this
    wrapper is safe to call unconditionally and never crashes the command.
    """
    try:
        from specify_cli.git.sparse_checkout import warn_if_sparse_once

        warn_if_sparse_once(repo_root, command=command)
    except Exception as _exc:  # noqa: BLE001 - defensive; must never break CLI
        # FR-010 contract: detection failures must never break the CLI command
        # that invoked this hook. Log to the module logger at debug level so
        # the failure is still traceable without tripping the ``S110`` lint.
        logging.getLogger(__name__).debug(
            "sparse-checkout session warning failed for %s: %s",
            command,
            _exc,
        )


def _ensure_target_branch_checked_out(
    repo_root: Path,
    mission_slug: str,
    json_output: bool,
) -> tuple[Path, str]:
    """Resolve branch context without auto-checkout (respects user's current branch).

    Returns:
        (main_repo_root, current_branch)
    """
    from specify_cli.cli.commands.agent import tasks as _tasks
    from specify_cli.core.git_ops import get_current_branch, resolve_target_branch

    # Write path: keep main-repo-root resolution so canonical serialization
    # pins to the primary checkout regardless of where the operator stands.
    main_repo_root = _tasks.get_main_repo_root(repo_root)

    # Check for detached HEAD using robust branch detection
    current_branch = get_current_branch(main_repo_root)
    if current_branch is None:
        raise RuntimeError("Detached HEAD — checkout a branch before continuing")

    # Resolve branch routing (unified logic, no auto-checkout)
    resolution = resolve_target_branch(mission_slug, main_repo_root, current_branch, respect_current=True)

    # Show consistent branch banner
    if not json_output:
        if not resolution.should_notify:
            _tasks.console.print(f"[bold cyan]Branch:[/bold cyan] {current_branch} (target for this mission)")
        else:
            _tasks.console.print(f"[bold yellow]Branch:[/bold yellow] on '{resolution.current}', mission targets '{resolution.target}'")

    # Return current branch (no checkout performed)
    return main_repo_root, resolution.current


def _find_mission_slug(
    explicit_mission: str | None = None,
    *,
    json_output: bool = False,
    repo_root: Path | None = None,
    render: Render | None = None,
    error_handler: Callable[[str, str, int, dict[str, object]], NoReturn] | None = None,
) -> str:
    """Require an explicit mission slug (no auto-detection).

    When repo_root is supplied the handle is resolved via the canonical
    mission resolver (resolve_mission_handle), which handles ambiguous
    numeric-prefix handles, mid8 prefixes, and full ULID forms.  The
    resolver calls sys.exit(2) on error so no try/except is needed.

    Args:
        explicit_mission: Mission slug provided via --mission.
        json_output: Propagate to resolver error rendering.
        repo_root: Repository root; if provided, enables canonical resolver.
        error_handler: Optional command-owned failure renderer/exit handler.
            Receives code, message, human exit code and selector details before
            output. Default preserves the legacy rendering of other families.

    Returns:
        Mission slug (e.g., "008-unified-python-cli")

    Raises:
        typer.Exit: If mission slug is not provided.
    """
    from specify_cli.cli.commands.agent import tasks as _tasks

    if not explicit_mission or not explicit_mission.strip():
        err = "--mission <slug> is required"
        if error_handler is not None:
            error_handler("mission_required", err, 1, {})
        if json_output:
            render = render or _tasks.RealRender()
            print(render.json_envelope({"error": err}))
        else:
            _tasks.console.print(f"[red]Error:[/red] {err}")
        raise typer.Exit(1)

    raw_handle = explicit_mission.strip()
    if repo_root is not None:
        # Write path: keep main-repo-root resolution so canonical serialization
        # pins to the primary checkout regardless of where the operator stands.
        # Note: repo_root from locate_project_root() already resolves to the main
        # checkout; get_main_repo_root() here guards against caller passing a
        # worktree path directly.
        try:
            legacy_dir = placement_seam(
                _tasks.get_main_repo_root(repo_root), raw_handle
            ).read_dir(MissionArtifactKind.PRIMARY_METADATA)
        except MissionSelectorAmbiguous as exc:
            if error_handler is not None:
                error_handler(exc.error_code, str(exc), 2, {"handle": exc.handle, "candidates": exc.candidates})
            # This read-path resolver family raises BEFORE resolve_mission_handle
            # ever runs (#241), so an ambiguous handle must map onto the SAME
            # shared {"success": False, "error_code": ..., "error": ...,
            # "handle": ..., "candidates": [...]} envelope resolve_mission_handle
            # emits below for AmbiguousHandleError/MissionNotFoundError — not the
            # bare {"error": str(exc)} the generic command-level exception
            # handler would otherwise produce.
            envelope = {
                "success": False,
                "error_code": exc.error_code,
                "error": str(exc),
                "handle": exc.handle,
                "candidates": exc.candidates,
            }
            if json_output:
                render = render or _tasks.RealRender()
                print(render.json_envelope(envelope))
                raise typer.Exit(1) from None
            _tasks.console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(2) from None
        if legacy_dir.exists():
            # F-001: the candidate resolver canonicalizes mid8/ULID/numeric
            # handles, so the resolved directory's NAME — not the raw operator
            # handle — is the canonical mission slug downstream consumers need.
            legacy_name: str = legacy_dir.name
            return legacy_name
        if error_handler is not None:
            from specify_cli.context.mission_resolver import AmbiguousHandleError, MissionNotFoundError, resolve_mission

            try:
                canonical_slug: str = resolve_mission(raw_handle, repo_root).mission_slug
                return canonical_slug
            except AmbiguousHandleError as exc:
                details = exc.to_dict()
                error_handler(str(details["error"]), str(exc), 2, {"handle": exc.handle, "candidates": details["candidates"]})
            except MissionNotFoundError as exc:
                error_handler("MISSION_NOT_FOUND", str(exc), 2, {"handle": exc.handle})
        try:
            resolved = resolve_mission_handle(raw_handle, repo_root, json_mode=json_output)
            resolved_slug: str = resolved.mission_slug
            return resolved_slug
        except (SystemExit, typer.Exit):
            if legacy_dir.exists():
                fallback_name: str = legacy_dir.name
                return fallback_name
            raise

    return raw_handle


def _output_result(
    json_mode: bool,
    data: dict[str, Any],
    success_message: str | None = None,
    *,
    render: Render | None = None,
) -> None:
    """Output result in JSON or human-readable format.

    Args:
        json_mode: If True, output JSON; else use Rich console
        data: Data to output (used for JSON mode)
        success_message: Message to display in human mode
        render: Optional Render seam; defaults to the compact production adapter
    """
    from specify_cli.cli.commands.agent import tasks as _tasks

    if json_mode:
        render = render or _tasks.RealRender()
        print(render.json_envelope(data))
    elif success_message:
        _tasks.console.print(success_message)


def _output_error(
    json_mode: bool,
    error_message: str,
    diagnostic: dict[str, Any] | None = None,
    *,
    render: Render | None = None,
) -> None:
    """Output error in JSON or human-readable format.

    Args:
        json_mode: If True, output JSON; else use Rich console
        error_message: Error message to display
        render: Optional Render seam; defaults to the compact production adapter
    """
    from specify_cli.cli.commands.agent import tasks as _tasks

    if json_mode:
        render = render or _tasks.RealRender()
        print(render.json_envelope(diagnostic if diagnostic is not None else {"error": error_message}))
    else:
        _tasks.console.print(f"[red]Error:[/red] {error_message}")


def _protected_branch_status_commit_error(branch: str, repo_root: Path, command: str) -> str | None:
    """Refuse a planning-kind status commit onto a protected primary (#2300).

    The map-requirements REFUSE arm (and the move-task no-coord-route fallback):
    the verdict is DERIVED from the single ``resolve_surface_authority`` rule
    (contract §2 rule 3), not hardcoded here. A planning/primary-kind commit onto
    a protected primary with no coordination route is a :class:`Refuse` (exit 1);
    an unprotected primary is committable (``None``). The kind is fixed to a
    PRIMARY-partition kind because a primary-kind's verdict keys ONLY on
    ``primary_protected`` (topology is verdict-irrelevant for a primary kind), so
    the stored topology is not resolved on this refuse-only leg. The operator
    hatch (``SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS=1``) folds through
    ``ProtectionPolicy.resolve`` into ``is_protected`` exactly as before.

    The remedy is UNIFIED to the shared ``REMEDY_PROTECTED_PRIMARY`` constant
    (carried on the verdict's :class:`Refuse`) — no per-command remedy drift.
    """
    from specify_cli.cli.commands.agent import tasks as _tasks

    # ProtectionPolicy.resolve is the sole I/O boundary (FR-007/NFR-003):
    # config+hatch reads happen once; is_protected() is I/O-free.
    primary_protected = _tasks.ProtectionPolicy.resolve(repo_root).is_protected(branch)
    verdict = resolve_surface_authority(
        topology=MissionTopology.SINGLE_BRANCH,
        primary_target=branch,
        primary_protected=primary_protected,
        current_branch=branch,
        artifact_kind=MissionArtifactKind.WORK_PACKAGE_TASK,
    )
    refusal = verdict.non_committable
    if not isinstance(refusal, Refuse):
        return None
    return (
        f"Refusing to run `{command}` with auto-commit on protected branch "
        f"'{branch}' before mutating status files. Run status commit "
        f"operations from an allowed coordination/lane branch, or unblock with: "
        f"{refusal.remedy}."
    )


def _coord_topology_active(repo_root: Path, mission_slug: str) -> bool:
    """Return True if the coordination worktree exists for this mission."""
    try:
        from specify_cli.coordination.workspace import CoordinationWorkspace
        from specify_cli.lanes.branch_naming import resolve_transaction_mid8
        # Authoritative topology resolver (FR-004/#1918): a coord-worktree lookup
        # needs the REAL mid8 to name its dir. With no declared mission_id/mid8 the
        # seam falls back to the embedded ``<slug>-<mid8>`` tail (genuine slug) and
        # returns "" only for a legacy/flattened mission with no coord topology —
        # exactly the historical mid8_from_slug behaviour for resolvable slugs.
        mid8 = resolve_transaction_mid8(
            mission_slug, mission_id=None, mid8=None, coordination_branch=None
        )
        path = CoordinationWorkspace.worktree_path(repo_root, mission_slug, mid8)
        exists: bool = path.exists()
        return exists
    except Exception:
        return False


def _skip_target_branch_commit(repo_root: Path, mission_slug: str, target_branch: str) -> bool:
    """Return True when the direct WP-file commit to a protected primary must be skipped.

    NOT a routing authority (write-surface-coherence WP02 / T032 / G-1): the
    commit DESTINATION for the WP file is owned solely by the kind authority
    (``resolve_placement_only(kind=WORK_PACKAGE_TASK)``). This flag only decides
    whether to SKIP the direct primary commit in the genuine protected-primary
    case — coord topology active AND the primary ``target_branch`` is protected —
    where committing directly to the protected ref is refused and the status
    transition committed to the coordination branch is authoritative. It selects
    no ref; it suppresses a commit that the protection policy would refuse anyway.

    The skip/no-skip verdict is DERIVED from the single ``resolve_surface_authority``
    rule (#2300 / contract §2 rule 1): a lifecycle/coordination kind under a
    coordination-routing topology with a protected primary yields
    :class:`RouteToCoord` (the redundant direct-to-protected-primary commit is
    suppressed; the coord commit is authoritative) → skip. The coord-worktree
    probe (``_coord_topology_active``) stands in for the coord-routing topology and
    is evaluated FIRST so the short-circuit keeps its no-policy-I/O-on-flat-missions
    contract (the ``ProtectionPolicy`` resolve is skipped entirely when no coord
    worktree exists).
    """
    from specify_cli.cli.commands.agent import tasks as _tasks

    # Short-circuit preserved: probe the coord worktree first; only a coord-routing
    # mission ever reaches the protection resolve (no policy I/O on flat missions).
    if not _tasks._coord_topology_active(repo_root, mission_slug):
        return False
    # ProtectionPolicy.resolve is the sole I/O boundary (FR-007/NFR-003):
    # config+hatch reads happen once; is_protected() is I/O-free.
    primary_protected = _tasks.ProtectionPolicy.resolve(repo_root).is_protected(target_branch)
    verdict = resolve_surface_authority(
        topology=MissionTopology.COORD,
        primary_target=target_branch,
        primary_protected=primary_protected,
        current_branch=target_branch,
        artifact_kind=MissionArtifactKind.STATUS_STATE,
    )
    return isinstance(verdict.non_committable, RouteToCoord)


def _mission_identity_payload(feature_dir: Path) -> dict[str, str | int | None]:
    # ``mission_number`` is ``int | None`` on ``MissionIdentity`` (display-only,
    # ``null`` pre-merge); slug/type are ``str``. The value is threaded verbatim
    # into machine-facing JSON payloads, so the return type carries the real
    # heterogeneity instead of coercing (byte-parity: no string-cast of the
    # number). Consumers spread this into ``dict[str, object]`` result maps.
    identity = resolve_mission_identity(feature_dir)
    return {
        "mission_slug": identity.mission_slug,
        "mission_number": identity.mission_number,
        "mission_type": identity.mission_type,
    }


def _resolve_git_common_dir(main_repo_root: Path) -> Path:
    """Resolve absolute git common-dir for the repository."""
    from specify_cli.cli.commands.agent import tasks as _tasks

    result = _tasks.subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        cwd=main_repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    raw_value = result.stdout.strip()
    if not raw_value:
        raise RuntimeError("Unable to resolve git common directory")
    common_dir = Path(raw_value)
    if not common_dir.is_absolute():
        common_dir = (main_repo_root / common_dir).resolve()
    return common_dir


def _check_unchecked_subtasks(
    repo_root: Path,
    mission_slug: str,
    wp_id: str,
    _force: bool,
    *,
    effective_root: Path | None = None,
) -> list[str]:
    """Return *wp_id*'s incomplete subtask ids, read from the reduced snapshot.

    The subtask **roster** (which task ids belong to ``wp_id``) is the authored
    ``subtasks:`` frontmatter list — static design intent (#2062), sourced via
    :func:`core.subtask_rows.authored_subtask_roster`, NOT ``tasks.md`` checkbox
    rows. **Completion** is resolved solely from the event-sourced reduced
    snapshot's ``subtasks`` slot (populated by ``mark-status``'s
    ``emit_inner_state_changed`` call) via
    :func:`core.subtask_rows.unchecked_subtask_ids_from_snapshot`.

    This is #2816 IC-10 (FR-016 / SC-010): the markdown checkbox is retired as
    the subtask-completion proxy — a raw checkbox edit without ``mark-status``
    no longer moves the gate (the D-13 incoherence is closed). Sourcing the
    roster from the frontmatter — not from re-parsing ``tasks.md`` — is what
    makes checkbox removal safe: an emptied ``tasks.md`` can no longer silently
    empty the roster and disable the guard.

    Fail-closed: a WP with an authored roster but an absent/silent snapshot slot
    blocks (every roster id reported incomplete), mirroring
    ``emit._infer_subtasks_complete``'s "unprovable completeness must block"
    rule. A WP with an empty authored roster is "nothing to block on" -> ``[]``.

    Args:
        repo_root: Repository root path
        mission_slug: Mission slug (e.g., "010-lane-only-runtime")
        wp_id: Work package ID (e.g., "WP01")
        _force: Unused here — the caller decides warn-vs-raise on a non-empty
            result; this reader always just reports the incomplete ids.

    Returns:
        List of incomplete task IDs (empty if all done or no authored roster).
    """
    from specify_cli.cli.commands.agent import tasks as _tasks

    # Write path: keep main-repo-root resolution so canonical serialization
    # pins to the primary checkout regardless of where the operator stands.
    main_repo_root = _tasks.get_main_repo_root(repo_root)
    # WP04 / FR-006: the authored WP roster is TASKS_INDEX and therefore lives
    # on the primary partition. Dynamic completion is STATUS_STATE and follows
    # the topology-routed status surface instead.
    feature_dir = placement_seam(
        main_repo_root, mission_slug, effective_root=effective_root
    ).read_dir(
        MissionArtifactKind.TASKS_INDEX
    )
    if not (feature_dir / "tasks").is_dir():
        return []
    from specify_cli.core.subtask_rows import (
        authored_subtask_roster,
        unchecked_subtask_ids_from_snapshot,
    )

    roster = authored_subtask_roster(feature_dir, wp_id)
    if not roster:
        return []
    if effective_root is not None:
        status_dir = placement_seam(
            main_repo_root, mission_slug, effective_root=effective_root
        ).read_dir(MissionArtifactKind.STATUS_STATE)
    else:
        from specify_cli.coordination import resolve_status_surface

        status_dir = resolve_status_surface(main_repo_root, mission_slug).parent
    return unchecked_subtask_ids_from_snapshot(status_dir, wp_id, roster)


def _validate_ready_for_review(
    repo_root: Path,
    mission_slug: str,
    wp_id: str,
    force: bool,
    target_lane: str = "for_review",
    *,
    effective_root: Path | None = None,
    workspace_override: object | None = None,
    review_base_ref: str | None = None,
    check_kitty_specs: bool = True,
) -> tuple[bool, list[str]]:
    """Validate that WP is ready for review by checking for uncommitted changes.

    Thin wrapper over the WP06 seam
    (:func:`tasks_parsing_validation._validate_ready_for_review`). The
    ``tasks``-resident collaborators are passed in from that module's live
    namespace at call time so the existing ``@patch("...agent.tasks.<name>")``
    contracts (e.g. ``get_main_repo_root``, ``get_mission_type``,
    ``get_feature_target_branch``, ``resolve_workspace_for_wp``, the git
    helpers, and ``console``) continue to apply unchanged. Behaviour,
    validation order, error strings, and the (bool, list[str]) return shape
    are preserved exactly.
    """
    from specify_cli.cli.commands.agent import tasks as _tasks

    verdict: tuple[bool, list[str]] = _seam_validate_ready_for_review(
        repo_root,
        mission_slug,
        wp_id,
        force,
        target_lane=target_lane,
        effective_root=effective_root,
        workspace_override=workspace_override,
        review_base_ref=review_base_ref,
        check_kitty_specs=check_kitty_specs,
        get_main_repo_root=_tasks.get_main_repo_root,
        get_mission_type=_tasks.get_mission_type,
        get_feature_target_branch=_tasks.get_feature_target_branch,
        resolve_workspace_for_wp=_tasks.resolve_workspace_for_wp,
        review_currency_check_branch=_tasks._review_currency_check_branch,
        behind_commits_touch_only_planning_artifacts=_tasks._behind_commits_touch_only_planning_artifacts,
        filter_runtime_state_paths=_tasks._filter_runtime_state_paths,
        list_wp_branch_specs_changes_for_guard=_tasks._list_wp_branch_specs_changes_for_guard,
        console=_tasks.console,
    )
    return verdict


def _wp_branch_merged_into_target(
    repo_root: Path,
    mission_slug: str,
    wp_id: str,
    target_branch: str,
) -> tuple[bool, str]:
    """Check whether a lane branch tip is reachable from the target branch.

    Returns:
        (is_merged, message)
    """
    from specify_cli.cli.commands.agent import tasks as _tasks

    workspace = _tasks.resolve_workspace_for_wp(repo_root, mission_slug, wp_id)
    wp_branch = workspace.branch_name
    if wp_branch is None:
        return (
            False,
            (
                "Cannot verify merge ancestry: no branch name resolved for "
                f"workspace of {wp_id}.\nEither merge and keep the branch ref "
                "available, or provide --done-override-reason."
            ),
        )

    branch_exists = _tasks.subprocess.run(
        ["git", "rev-parse", "--verify", wp_branch],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    if branch_exists.returncode != 0:
        return (
            False,
            (f"Cannot verify merge ancestry: branch '{wp_branch}' not found.\nEither merge and keep branch ref available, or provide --done-override-reason."),
        )

    merged_check = _tasks.subprocess.run(
        ["git", "merge-base", "--is-ancestor", wp_branch, target_branch],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    if merged_check.returncode == 0:
        return True, f"Merge ancestry verified: {wp_branch} is merged into {target_branch}."

    return (
        False,
        (
            f"Merge ancestry check failed: {wp_branch} is not merged into {target_branch}.\n"
            f"Merge first, or provide --done-override-reason to record a conscious exception."
        ),
    )


def _filter_by_planning_tip_content(worktree_path: Path, candidates: list[str], base_branch: str) -> list[str] | None:
    """Keep candidates that differ from a trusted snapshot (FR-007 / #2274).

    Compares the candidates against the planning tip through the canonical
    ``vcs.git`` seam — the same seam pass 1 uses (``merge_base_changed_files``)
    rather than a hand-rolled ``git diff`` subprocess. A candidate that does not
    appear in ``git diff <base_branch> HEAD -- kitty-specs/`` is byte-identical
    to the planning tip (e.g. after a planning-branch rebase that brought no
    content change) and must not be flagged as a lane-hygiene violation. On any
    git failure — including an unresolvable ``base_branch`` —
    ``git_diff_names_checked`` returns ``None`` so the caller can refuse the
    handoff instead of treating an unknown comparison as clean.
    """
    diverged = git_diff_names_checked(worktree_path, base_branch, "HEAD", pathspec=f"{KITTY_SPECS_DIR}/")
    if diverged is None:
        return None
    # ``git diff --name-only`` quotes paths containing tabs, quotes, or other
    # unusual characters. The caller cannot safely associate those entries
    # with a candidate path, so an unexpected prefix is unverifiable, not clean.
    if any(not path.startswith(f"{KITTY_SPECS_DIR}/") for path in diverged):
        return None
    diverged_set = set(diverged)
    return [path for path in candidates if path in diverged_set]


def _lane_hygiene_fork_point(worktree_path: Path, base_branch: str, workspace_base_commit: str | None) -> str | None:
    """Resolve the immutable lane fork commit, refusing a stale pin."""
    if workspace_base_commit is None:
        return cast(str | None, git_merge_base(worktree_path, "HEAD", base_branch))
    if git_merge_base(worktree_path, "HEAD", workspace_base_commit) != workspace_base_commit:
        return None
    return workspace_base_commit


def _lane_hygiene_candidates(changed: tuple[str, ...]) -> list[str] | None:
    """Validate diff path encoding and keep non-exempt kitty-specs candidates."""
    seen: set[str] = set()
    candidates: list[str] = []
    for path in changed:
        if not path.startswith(f"{KITTY_SPECS_DIR}/"):
            return None
        if path in seen or is_occurrence_map_path(path):
            continue
        seen.add(path)
        candidates.append(path)
    return candidates


def _trusted_handoff_snapshots(
    worktree_path: Path,
    planning_ref: str,
    planning_commit_sha: str | None,
    workspace_base_commit: str,
    coordination_ref: str | None,
) -> tuple[str, str | None, str | None] | None:
    """Resolve exact post-fork snapshots trusted by the handoff guard."""
    planning_tip = capture_branch_tip(worktree_path, planning_ref)
    if planning_tip is None:
        return None
    recorded_pin = planning_commit_sha
    if recorded_pin is None:
        recorded_pin = _unique_shared_snapshot(worktree_path, "HEAD", planning_tip)
        if recorded_pin is None or not _fallback_planning_pin_is_trusted(
            worktree_path,
            planning_tip,
            recorded_pin,
            workspace_base_commit,
            merge_base=git_merge_base,
            is_post_fork_ancestor=_commit_is_post_fork_lane_ancestor,
        ):
            return None
    else:
        # A context pin names planning provenance only when the authoritative
        # planning branch contains that exact commit. Lane reachability alone
        # cannot turn a lane-authored planning edit into a trusted snapshot.
        if git_merge_base(worktree_path, planning_tip, recorded_pin) != recorded_pin:
            return None
        # A fresh lane may start at its immutable claim-time planning pin (or a
        # later commit that already contains it). The explicit workspace pin
        # remains trustworthy in that topology even though no post-fork merge
        # is needed; legacy contexts without a pin still require post-fork
        # lane-history proof above.
        fork_contains_pin = git_merge_base(worktree_path, workspace_base_commit, recorded_pin) == recorded_pin
        if not fork_contains_pin and not _commit_is_post_fork_lane_ancestor(worktree_path, recorded_pin, workspace_base_commit):
            return None
        if git_merge_base(worktree_path, "HEAD", recorded_pin) != recorded_pin:
            return None

    # Trust the newest authoritative planning snapshot shared by this lane and
    # the planning ref. The planning ref may have advanced past a merged P2 to
    # P3 before handoff, so its current tip need not be present in the lane.
    merged_planning_tip = _unique_shared_snapshot(worktree_path, "HEAD", planning_tip)
    if merged_planning_tip is None:
        return None
    if merged_planning_tip is not None and not _commit_is_post_fork_lane_ancestor(worktree_path, merged_planning_tip, workspace_base_commit):
        merged_planning_tip = None
    coordination_snapshot = None
    if coordination_ref is not None:
        coordination_tip = capture_branch_tip(worktree_path, coordination_ref)
        if coordination_tip is None:
            return None
        snapshot = _unique_shared_snapshot(worktree_path, "HEAD", coordination_tip)
        if snapshot is None:
            return None
        if _commit_is_post_fork_lane_ancestor(worktree_path, snapshot, workspace_base_commit):
            coordination_snapshot = snapshot
    return recorded_pin, merged_planning_tip, coordination_snapshot


def _commit_in_trusted_snapshots(worktree_path: Path, commit: str, snapshots: tuple[str, ...]) -> bool | None:
    for snapshot in snapshots:
        merge_base = git_merge_base(worktree_path, commit, snapshot)
        if merge_base is None:
            return None
        if merge_base == commit:
            return True
    return False


def _kitty_specs_paths_changed(worktree_path: Path, base: str, commit: str) -> set[str] | None:
    changed = git_diff_names_checked(worktree_path, base, commit, pathspec=f"{KITTY_SPECS_DIR}/")
    return None if changed is None else set(changed)


def _merge_commit_authored_kitty_specs_paths(
    worktree_path: Path,
    parents: tuple[str, ...],
    result_paths_by_parent: list[set[str]],
) -> tuple[str, ...] | None:
    merge_base = _unique_shared_snapshot(worktree_path, parents[0], parents[1])
    if merge_base is None:
        return None
    parent_changes: list[set[str]] = []
    for parent in parents:
        changed_paths = _kitty_specs_paths_changed(worktree_path, merge_base, parent)
        if changed_paths is None:
            return None
        parent_changes.append(changed_paths)

    # A path changed from the merge base on both sides is not necessarily
    # merge-authored: identical inherited bytes remain clean when the result
    # matches both parents. Any resolution that differs from either parent
    # remains authored and is included here.
    both_parents_changed = parent_changes[0] & parent_changes[1]
    authored_paths = both_parents_changed & (result_paths_by_parent[0] | result_paths_by_parent[1])
    one_parent_changed = parent_changes[0] ^ parent_changes[1]
    for path in one_parent_changed:
        changed_parent = 0 if path in parent_changes[0] else 1
        if path in result_paths_by_parent[changed_parent]:
            authored_paths.add(path)

    # A merge result different from both parents is a novel resolution, even
    # if it happens to equal the fork or an older trusted snapshot.
    authored_paths.update(set.intersection(*result_paths_by_parent))
    return tuple(authored_paths)


def _lane_commit_authored_kitty_specs_paths(
    worktree_path: Path,
    commit: str,
    parents: tuple[str, ...],
) -> tuple[str, ...] | None:
    if len(parents) > 2:
        # Octopus merge semantics are harder to assign to one trusted source.
        return None
    result_paths_by_parent: list[set[str]] = []
    for parent in parents:
        changed_paths = _kitty_specs_paths_changed(worktree_path, parent, commit)
        if changed_paths is None:
            return None
        result_paths_by_parent.append(changed_paths)
    if len(parents) == 1:
        return tuple(result_paths_by_parent[0])
    return _merge_commit_authored_kitty_specs_paths(worktree_path, parents, result_paths_by_parent)


def _lane_authored_kitty_specs_paths(
    worktree_path: Path,
    fork_commit: str,
    trusted_snapshots: tuple[str, ...],
    *,
    mission_slug: str | None = None,
    planning_pin: str | None = None,
    planning_ref: str | None = None,
    merged_planning_tip: str | None = None,
    coordination_snapshot: str | None = None,
    coordination_ref: str | None = None,
    derived_status_paths: set[str] | None = None,
    candidate_paths: set[str] | None = None,
) -> tuple[str, ...] | None:
    """List kitty-specs paths touched by lane-history commits outside trust.

    The fork-to-tip tree diff cannot see a lane commit that restores a path to
    its fork bytes or deletes a file introduced by a later coordination merge.
    Walk every commit reachable from the lane tip so side-branch edits are
    visible too. Commits already present in exact planning or coordination
    snapshots are inherited; remaining changes represent lane path touches.
    """
    derived_paths = derived_status_paths if derived_status_paths is not None else set()
    commits = _lane_history_commits(worktree_path, fork_commit)
    if commits is None:
        return None
    status_snapshot_path = f"{KITTY_SPECS_DIR}/{mission_slug}/status.json" if mission_slug else None
    authored_paths: list[str] = []
    for commit_and_parents in commits:
        commit, *parent_items = commit_and_parents
        parents = tuple(parent_items)
        outcome = _lane_commit_handoff_paths(
            worktree_path,
            fork_commit,
            commit,
            parents,
            trusted_snapshots,
            status_snapshot_path,
            mission_slug,
            planning_pin,
            merged_planning_tip,
            coordination_snapshot,
        )
        if outcome is None:
            return None
        changed_paths, status_is_derived = outcome
        if status_is_derived and status_snapshot_path is not None:
            derived_paths.add(status_snapshot_path)
        authored_paths.extend(changed_paths)

    # Replay final status even when no merge commit changed status.json: a later
    # event-only merge can leave an inherited snapshot stale without changing it.
    if status_snapshot_path is not None and not _canonical_final_head_status_replay(
        worktree_path,
        fork_commit,
        mission_slug,
        planning_pin,
        planning_ref,
        merged_planning_tip,
        coordination_snapshot,
        coordination_ref,
        capture_branch_tip,
    ):
        derived_paths.discard(status_snapshot_path)
        status_events_path = f"{KITTY_SPECS_DIR}/{mission_slug}/status.events.jsonl"
        status_meta_path = f"{KITTY_SPECS_DIR}/{mission_slug}/meta.json"
        replay_inputs_changed = candidate_paths is not None and (
            status_snapshot_path in candidate_paths or status_events_path in candidate_paths or status_meta_path in candidate_paths
        )
        if replay_inputs_changed and status_snapshot_path not in authored_paths:
            authored_paths.append(status_snapshot_path)
    return tuple(authored_paths)


def _coordination_hygiene_candidates(candidates: list[str], mission_slug: str | None, topology: MissionTopology | None) -> set[str]:
    """Identify coordination-partition candidates that planning equality cannot clear."""
    if topology is None:
        return set()
    return {
        path for path in candidates if (kind := kind_for_mission_file(path, mission_slug=mission_slug)) is not None and kind_is_coordination_residue(kind, topology)
    }


def _coordination_candidate_violations(
    worktree_path: Path,
    candidates: set[str],
    authored_paths: set[str],
    coordination_snapshot: str | None,
    derived_status_paths: set[str] | None = None,
) -> set[str] | None:
    """Allow coordination files only when exact post-fork inherited bytes remain."""
    if not candidates:
        return set()
    if coordination_snapshot is None:
        return set(candidates)

    violations = set(candidates)
    from specify_cli.cli.commands.agent import tasks as _tasks

    divergence = _tasks._filter_by_planning_tip_content(worktree_path, sorted(candidates), coordination_snapshot)
    if divergence is None:
        return None
    violations.difference_update(set(candidates) - set(divergence))
    if derived_status_paths is not None:
        violations.difference_update((derived_status_paths & candidates) - authored_paths)
    violations.update(candidates & authored_paths)
    return violations


def _planning_candidate_violations(
    worktree_path: Path,
    candidates: list[str],
    planning_ref: str,
    workspace_base_commit: str | None,
    trusted_snapshots: tuple[str, str | None, str | None] | None,
) -> set[str] | None:
    """Keep candidates not explained by a verified inherited snapshot.

    P1 is the immutable claim-time planning pin from workspace context. Legacy
    contexts recover it from the lane/planning merge-base only when that commit
    entered lane history after the immutable workspace fork. Current P2 and
    coordination content are trusted only when their exact commits are likewise
    proven in post-fork lane history; matching a moving ref's bytes alone cannot
    erase a lane-authored edit.
    """
    from specify_cli.cli.commands.agent import tasks as _tasks

    if not candidates:
        return set()
    if workspace_base_commit is None:
        # Preserve the historical direct-helper contract for legacy callers.
        # The move-task guard always supplies the immutable workspace base
        # (or refuses before reaching this seam), so production handoff never
        # treats this moving-ref-only fallback as claim-time provenance.
        current = _tasks._filter_by_planning_tip_content(worktree_path, candidates, planning_ref)
        return None if current is None else set(current)

    if trusted_snapshots is None:
        return None
    recorded_pin, merged_planning_tip, coordination_snapshot = trusted_snapshots

    recorded_divergence = _tasks._filter_by_planning_tip_content(worktree_path, candidates, recorded_pin)
    if recorded_divergence is None:
        return None
    violations = set(recorded_divergence)

    # P2 can explain a changed candidate only when that exact primary tip is
    # present after the lane's fork. Otherwise its bytes are not lane history.
    if merged_planning_tip is not None:
        current_divergence = _tasks._filter_by_planning_tip_content(worktree_path, candidates, merged_planning_tip)
        if current_divergence is None:
            return None
        violations.intersection_update(current_divergence)

    # Unclassified coordination-owned artifacts (for example mission-events
    # and an existing WP prompt) can be inherited after lane birth. Compare
    # against the exact coordination snapshot already merged into this lane,
    # never a basename exemption or a newer unmerged coordinator tip.
    if coordination_snapshot is not None:
        coordination_divergence = _tasks._filter_by_planning_tip_content(worktree_path, candidates, coordination_snapshot)
        if coordination_divergence is None:
            return None
        violations.intersection_update(coordination_divergence)

    return violations


def _commit_is_post_fork_lane_ancestor(worktree_path: Path, commit: str, workspace_base_commit: str) -> bool:
    """Return whether ``commit`` entered lane history after its recorded fork."""
    if git_merge_base(worktree_path, "HEAD", workspace_base_commit) != workspace_base_commit:
        return False
    if git_merge_base(worktree_path, "HEAD", commit) != commit:
        return False
    fork_candidate_base = git_merge_base(worktree_path, workspace_base_commit, commit)
    return fork_candidate_base is not None and fork_candidate_base != commit


def _list_wp_branch_mission_specs_changes(
    worktree_path: Path,
    base_branch: str,
    *,
    planning_base_branch: str | None = None,
    workspace_base_commit: str | None = None,
    planning_commit_sha: str | None = None,
    coordination_ref: str | None = None,
    mission_slug: str | None = None,
    topology: MissionTopology | None = None,
) -> list[str] | None:
    """Return lane-authored ``kitty-specs/`` changes, or ``None`` if unknown.

    ``workspace_base_commit`` is the immutable claim-time fork snapshot;
    ``base_branch`` is the fallback for legacy workspaces. ``planning_base_branch``
    is the moving primary planning ref and ``planning_commit_sha`` is the
    immutable claim-time planning snapshot from workspace context. Legacy
    contexts need a planning pin provable from post-fork lane history.
    ``coordination_ref`` is the canonical status-placement ref for a
    coordination topology.

    Candidate paths are measured after the immutable lane fork snapshot. A
    planning candidate is clean only when it matches a claim-time planning
    snapshot, a current planning tip actually merged after the fork, or a
    coordination snapshot actually merged after the fork. Coordination-kind
    candidates require the exact coordination snapshot; a lane-history touch
    always remains a violation even if its final bytes match a snapshot.

    An unknown base, missing merge-base, or failed content diff is not evidence
    of a clean lane and returns ``None`` so the caller can fail closed.
    """
    planning_ref = planning_base_branch or base_branch
    merge_base = _lane_hygiene_fork_point(worktree_path, base_branch, workspace_base_commit)
    if merge_base is None:
        return None
    changed = git_diff_names_checked(
        worktree_path,
        merge_base,
        "HEAD",
        pathspec=f"{KITTY_SPECS_DIR}/",
    )
    if changed is None:
        return None

    trusted_snapshots: tuple[str, str | None, str | None] | None = None
    authored_changes: tuple[str, ...] = ()
    derived_status_paths: set[str] = set()
    if workspace_base_commit is not None:
        trusted_snapshots = _trusted_handoff_snapshots(
            worktree_path,
            planning_ref,
            planning_commit_sha,
            workspace_base_commit,
            coordination_ref,
        )
        if trusted_snapshots is None:
            return None
        trusted_commits = tuple(snapshot for snapshot in trusted_snapshots if snapshot is not None)
        resolved_authored_changes = _lane_authored_kitty_specs_paths(
            worktree_path,
            workspace_base_commit,
            trusted_commits,
            mission_slug=mission_slug,
            planning_pin=trusted_snapshots[0],
            planning_ref=planning_ref,
            merged_planning_tip=trusted_snapshots[1],
            coordination_snapshot=trusted_snapshots[2],
            coordination_ref=coordination_ref,
            derived_status_paths=derived_status_paths,
            candidate_paths=set(changed),
        )
        if resolved_authored_changes is None:
            return None
        authored_changes = resolved_authored_changes
    candidates = _lane_hygiene_candidates((*changed, *authored_changes))
    if candidates is None:
        return None
    authored_paths = {path for path in authored_changes if not is_occurrence_map_path(path)}

    coordination_candidates = _coordination_hygiene_candidates(candidates, mission_slug, topology)

    planning_candidates = [path for path in candidates if path not in coordination_candidates and path not in authored_paths]
    planning_violations = _planning_candidate_violations(
        worktree_path,
        planning_candidates,
        planning_ref,
        workspace_base_commit,
        trusted_snapshots,
    )
    if planning_violations is None:
        return None
    coordination_violations = _coordination_candidate_violations(
        worktree_path,
        coordination_candidates,
        authored_paths,
        trusted_snapshots[2] if trusted_snapshots is not None else None,
        derived_status_paths,
    )
    if coordination_violations is None:
        return None
    violations = authored_paths | planning_violations | coordination_violations
    return [path for path in candidates if path in violations]


def _list_wp_branch_specs_changes_for_guard(
    worktree_path: Path,
    base_branch: str,
    *,
    planning_base_branch: str | None = None,
    workspace_base_commit: str | None = None,
    planning_commit_sha: str | None = None,
    coordination_ref: str | None = None,
    mission_slug: str | None = None,
    topology: MissionTopology | None = None,
) -> list[str] | None:
    # The dynamically-named ``_list_wp_branch_<KITTY_SPECS_DIR>_changes`` alias
    # lives in the ``tasks`` namespace (assigned there next to the seam
    # re-imports) — reading it through ``_tasks`` at call time preserves the
    # historical ``tasks._list_wp_branch_kitty_specs_changes`` patch seam.
    from specify_cli.cli.commands.agent import tasks as _tasks

    patched_or_alias = getattr(_tasks, "_list_wp_branch_" + KITTY_SPECS_DIR.replace("-", "_") + "_changes")
    kwargs: dict[str, object] = {
        "worktree_path": worktree_path,
        "base_branch": base_branch,
    }
    if planning_base_branch is not None:
        kwargs["planning_base_branch"] = planning_base_branch
    if workspace_base_commit is not None:
        kwargs["workspace_base_commit"] = workspace_base_commit
    if planning_commit_sha is not None:
        kwargs["planning_commit_sha"] = planning_commit_sha
    if coordination_ref is not None:
        kwargs["coordination_ref"] = coordination_ref
    if mission_slug is not None:
        kwargs["mission_slug"] = mission_slug
    if topology is not None:
        kwargs["topology"] = topology
    changes: list[str] | None = patched_or_alias(**kwargs)
    return changes


def _mark_status_json_payload(results: list[TaskIdResult]) -> dict[str, object]:
    """Return the contracted mark-status --json payload."""
    summary = {
        "updated": sum(1 for result in results if result.outcome == TaskIdResolutionOutcome.UPDATED),
        "already_satisfied": sum(1 for result in results if result.outcome == TaskIdResolutionOutcome.ALREADY_SATISFIED),
        "not_found": sum(1 for result in results if result.outcome == TaskIdResolutionOutcome.NOT_FOUND),
    }
    return {
        "results": [
            {
                "id": result.id,
                "outcome": result.outcome.value,
                "format": result.format.value if result.format else None,
                "message": result.message,
            }
            for result in results
        ],
        "summary": summary,
    }
