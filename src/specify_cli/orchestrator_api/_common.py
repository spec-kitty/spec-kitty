"""Shared helpers for the orchestrator-api commands (#5628).

Envelope emission, structured failures, policy parsing, and repository /
mission / work-package resolution used by more than one command module.
Command modules call the patch seams (``_get_main_repo_root``,
``_resolve_mission_dir_or_fail``, ``_mission_identity_payload``) through
this module's attribute so a single patch reaches every caller.
Every other helper here (``_emit``, ``_fail``, ...) is imported by name, so
patching it on this module only reaches calls made from inside this module.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn

if TYPE_CHECKING:
    pass

import typer

from specify_cli.mission_metadata import resolve_mission_identity

from .envelope import (
    make_envelope,
    parse_and_validate_policy,
    policy_to_dict,
)


# Boy Scout (DIRECTIVE_025): deduplicated CLI help strings.
_HELP_MISSION_SLUG = "Mission slug"
# Deduplicated genuine-not-found message (Sonar S1192: emitted by 8 endpoints).
_MISSION_NOT_FOUND_MESSAGE = "Mission '{mission}' not found in kitty-specs/"
_HELP_ACTOR = "Actor identity"
_HELP_POLICY = "Policy metadata JSON (required)"


def _emit(envelope: dict[str, Any]) -> None:
    """Print canonical JSON envelope to stdout."""
    print(json.dumps(envelope))


def _fail(command: str, error_code: str, message: str, data: dict[str, Any] | None = None) -> NoReturn:
    """Print failure envelope and exit non-zero.

    Typed ``NoReturn`` (FR-004 / S5747): this always raises ``typer.Exit``, so
    mypy proves any code after a ``_fail(...)`` call is unreachable — callers
    need no sentinel ``raise`` to satisfy their return type.
    """
    # #3548 (fail-loud / silent-drop, epics #3410/#3549): the retired
    # ``data or {"message": message}`` expression DROPPED the human-readable
    # ``message`` whenever a caller passed truthy structured ``data`` — silencing
    # 16 of 33 call sites, preferentially the most actionable errors. Merge the
    # explanation INTO the payload so BOTH reach the operator; ``message`` (the
    # param, the canonical explanation) is guaranteed present and last-wins over
    # any caller-supplied ``data["message"]``. The two callers that seed their own
    # ``data["message"]`` (the read-path seam, and the LANE_ALLOCATION_FAILED site
    # via ``StructuredError.to_dict()``) both pass the identical ``str(exc)`` the
    # param already carries, so param-wins never destroys distinct information — it
    # only guarantees the explanation is never dropped. The structured
    # ``data["error_code"]`` those callers carry is untouched (NFR-003).
    payload = {**(data or {}), "message": message}
    envelope = make_envelope(
        command=command,
        success=False,
        data=payload,
        error_code=error_code,
    )
    _emit(envelope)
    raise typer.Exit(1)


def _parse_policy_or_fail(cmd: str, policy: str) -> dict[str, Any]:
    """Parse+validate a ``--policy`` JSON string, or ``_fail`` (NoReturn) on invalid JSON.

    The ONE ``POLICY_VALIDATION_FAILED`` emission (WP03/#3281 campsite): before
    this extraction, ``start_implementation``'s required-policy parse and
    ``transition``'s two (required + optional) policy-parse blocks each
    duplicated the identical try/``parse_and_validate_policy``/except/``_fail``
    shape. Folding them into one call keeps ``transition`` at its pre-WP03
    complexity (14) after this WP adds the post-materialize ancestry gate,
    rather than pushing it over the Sonar S3776/Ruff C901 ceiling of 15.
    """
    try:
        policy_obj = parse_and_validate_policy(policy)
    except ValueError as exc:
        _fail(cmd, "POLICY_VALIDATION_FAILED", str(exc))
    policy_dict: dict[str, Any] = policy_to_dict(policy_obj)
    return policy_dict


def _get_main_repo_root() -> Path:
    """Resolve main repository root from current working directory."""
    from specify_cli.core.paths import get_main_repo_root, locate_project_root

    cwd = Path.cwd()
    root = locate_project_root(cwd)
    if root is None:
        # Fall back to canonical resolver for worktree-aware behavior.
        return get_main_repo_root(cwd)
    return root


def _resolve_mission_dir(main_repo_root: Path, mission_slug: str) -> Path | None:
    """Return the coord-aware mission status directory if it exists, else None.

    For modern missions (coord-branch topology), returns the coordination
    worktree path. For legacy missions, returns the primary checkout path.
    Falls back to ``None`` only when the mission genuinely does not exist.

    This is now a thin consumer of the ONE guarded read-side seam
    :func:`resolve_handle_to_read_path` (WP01 / IC-01 / NFR-004): the seam owns
    the prototype cascade this endpoint pioneered — ``assert_safe_path_segment``
    → primary-``meta.json`` probe → the single sanctioned ``resolve_declared_mid8``
    cascade (NFR-005) → fail-closed coord-declared gate → the existence-gated
    :func:`resolve_mission_read_path`. The orchestrator's old inline duplicate of
    that cascade is GONE; only this ``.exists() → None`` adapter (the endpoint's
    own "absent ⇒ None, not a path" contract) remains here.

    Read-path SAFETY (FR-011 / M3, #2016) and the M5 fail-closed semantics are
    UNCHANGED — they are exactly the seam's invariants (the seam was lifted from
    this very prototype). ``require_exists`` is left at its default ``False`` so
    the seam returns the best-known candidate; this adapter decides absence by a
    single ``.exists()`` stat, preserving the historical ``Path | None`` contract.

    Typed-error fidelity (FR-001 / M2): :class:`StatusReadPathNotFound` from the
    seam's fail-closed gate is NOT caught here — it propagates so the calling
    endpoint surfaces the resolver's typed ``error_code`` (+ ``coord_candidate`` /
    ``primary_candidate``) instead of flattening every miss to
    ``MISSION_NOT_FOUND``.
    """
    from specify_cli.missions._read_path_resolver import resolve_handle_to_read_path

    mission_dir = resolve_handle_to_read_path(main_repo_root, mission_slug)
    return mission_dir if mission_dir.exists() else None


def _resolve_mission_dir_or_fail(command: str, main_repo_root: Path, mission_slug: str) -> Path:
    """Resolve the mission status dir, emitting the correct failure envelope on a miss.

    PR-BOUNDARY-002: this is the ONE seam every mission-scoped
    orchestrator-api endpoint routes through to resolve an EXISTING
    mission's directory -- reads and MUTATING verbs alike
    (``record-analysis``, ``open-decision``/``resolve-decision``/
    ``defer-decision``/``cancel-decision``/``answer-decision``), not only
    reads. Deliberately NOT documented as a call-site count: a hardcoded
    number in this docstring has drifted twice already (an original "all 8
    read endpoints" framing, both undercounted and miscategorized once this
    mission added mutating call sites; then a "17 call sites" snapshot whose
    own suggested verification grep matched its own quoted example text and
    undercounted the true count by one). The invariant that matters is
    structural, not numeric, and is asserted directly -- re-derived from the
    live AST on every run, so it cannot silently drift the way a number in
    prose does -- by
    ``tests/specify_cli/orchestrator_api/test_resolve_mission_dir_or_fail_invariant.py``:
    every mission-scoped endpoint routes through this ONE seam, avoiding one
    divergent existence-resolution pattern per call site:

    * a typed :class:`StatusReadPathNotFound` (coord topology + stale/unaddressable
      primary) surfaces the resolver's real ``error_code`` plus the
      ``coord_candidate`` / ``primary_candidate`` paths — the M2 fidelity fix; the
      external envelope *shape* is unchanged, only the code/data fidelity is raised
      (C-IC02 applied to the external surface).
    * a genuine absence (no such mission, no coord topology) keeps the historical
      ``MISSION_NOT_FOUND`` envelope.

    ``_fail`` is typed ``NoReturn`` (always raises ``typer.Exit``), so mypy proves
    the post-call paths unreachable — no sentinel ``raise`` is needed to satisfy
    the ``Path`` return type.
    """
    from specify_cli.missions._read_path_resolver import StatusReadPathNotFound

    try:
        mission_dir = _resolve_mission_dir(main_repo_root, mission_slug)
    except StatusReadPathNotFound as exc:
        _fail(
            command,
            exc.error_code,
            str(exc),
            data={
                "message": str(exc),
                "mission_slug": exc.mission_slug,
                "mid8": exc.mid8,
                "coord_candidate": str(exc.coord_candidate),
                "primary_candidate": str(exc.primary_candidate),
            },
        )
    except ValueError as exc:
        # #2879 (machine contract): the read-side seam's traversal guard
        # (``assert_safe_path_segment``, the FIRST step — before any
        # ``KITTY_SPECS_DIR`` join or meta probe) raises ``ValueError`` for an
        # unsafe ``--mission`` value (``..``, ``../traversal``, separators,
        # leading dot, non-ASCII). Pre-fix that escaped to the top level and
        # was rendered as a raw Python traceback — NOT JSON — breaking every
        # programmatic consumer of this JSON-first surface. Fail closed with
        # the structured ``INVALID_MISSION`` envelope instead (non-zero exit,
        # parseable stdout), mirroring how the host CLI's ``merge`` renders the
        # same guard (``cli/commands/merge.py:_resolve_slug_or_exit``).
        # ``_fail`` merges the *message* param into ``data`` last-wins, so the
        # guard's own diagnostic travels under a distinct ``reason`` key rather
        # than being silently overwritten by the canonical message.
        _fail(
            command,
            "INVALID_MISSION",
            f"Mission slug is not a safe path segment: {mission_slug!r}",
            data={"reason": str(exc), "mission_slug": mission_slug},
        )
    if mission_dir is None:
        _fail(command, "MISSION_NOT_FOUND", _MISSION_NOT_FOUND_MESSAGE.format(mission=mission_slug))
    return mission_dir


def _planning_read_dir(main_repo_root: Path, mission_slug: str) -> Path:
    """Return the PRIMARY-surface mission dir for planning-artifact reads (#2118).

    PRIMARY-partition artifacts — ``lanes.json`` (``LANE_STATE``) and the WP
    ``tasks/`` files (``WORK_PACKAGE_TASK``) — live with their mission on the
    primary ``target_branch`` for EVERY topology since the write-surface-coherence
    work (#2090): planning never transits the coordination branch. The coord-aware
    :func:`_resolve_mission_dir` returns the *coordination worktree*, which carries
    ONLY the coordination-partition artifacts — the status views
    (``status.events.jsonl`` / ``status.json``) and the accept/review matrices
    (``acceptance-matrix.json`` / ``issue-matrix.md``). (``analysis-report.md`` was
    re-homed COORD→PRIMARY, FR-003 coord-commit-integrity, so it is NOT here.)
    Reading ``lanes.json`` or
    ``tasks/`` off that surface under coordination topology silently no-ops — the
    dependency graph comes back empty and the orchestrator stalls with every WP
    stuck at ``lane=planned`` (#2118).

    This routes PRIMARY-partition reads through the canonical kind-aware
    placement seam (:func:`mission_runtime.placement_seam`, coord-primary-
    partition-lock WP01 T004 — DRY-only repoint, out-of-map edit; this file is
    not a WP01 owned file), the read-side twin of the write-side partition
    (``mission_runtime.is_primary_artifact_kind``): a PRIMARY kind resolves the
    topology-blind primary dir, so both ``LANE_STATE`` and ``WORK_PACKAGE_TASK``
    co-resolve here. STATUS reads (``read_events`` / ``reduce`` / ``materialize``
    / status-event writes) MUST keep the coord-aware :func:`_resolve_mission_dir`
    — the append-only event log stays on coordination for coord-topology
    missions. This mirrors the meta.json treatment already in
    :func:`_resolve_merge_target_branch`.
    """
    from mission_runtime import MissionArtifactKind, placement_seam

    return placement_seam(main_repo_root, mission_slug).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)


def _mission_identity_payload(mission_dir: Path) -> dict[str, str]:
    """Return canonical mission identity fields for machine-facing payloads."""
    identity = resolve_mission_identity(mission_dir)
    return {
        "mission_slug": identity.mission_slug,
        "mission_number": identity.mission_number,
        "mission_type": identity.mission_type,
    }


_WP_ID_RE = re.compile(r"^(WP\d+)")


def _extract_wp_id(stem: str) -> str | None:
    """Extract canonical WP ID from a task filename stem.

    Examples:
        "WP07"                         -> "WP07"
        "WP07-adapter-implementations" -> "WP07"
        "README"                       -> None
    """
    m = _WP_ID_RE.match(stem)
    return m.group(1) if m else None
