"""``spec-kitty events tail`` -- the thin CLI shell for the events push/watch channel.

Mission ``event-push-watch-channel-01M1K6W2``, WP04. Per the mission's corrected
architecture (spec.md FR-011/NFR-001/NFR-002, plan.md's "Architectural Seam: Core
vs. Shell" section): the CORE (``src/specify_cli/status/tail_reader.py``, shipped by
WP01-03) owns the poll-then-sleep loop via an injectable ``sleep_fn``. This module is
the OPPOSITE of a loop-owner -- it holds no ``while True`` and makes no direct
``time.sleep`` call of its own anywhere. ``--once`` calls ``poll_once()`` directly,
once, with no loop and no sleep at all. The streaming case is a plain ``for`` loop
over ``tail_events()`` (optionally bounded via ``itertools.islice`` when
``--max-events`` is given).

C-001 scope lock: this module builds ONLY ``spec-kitty events tail --mission <slug>
--json`` (Option 1 from issue #3841's Clarifications). No daemon, no socket/SSE
endpoint, no network listener, no fleet aggregation.

The shell does exactly four things, none of them novel domain logic (plan.md's CLI
Surface section):

1. FR-004's own-flag-combo usage check (``--from-invariant`` without ``--from-offset``).
2. Resolve the mission slug via the existing ``resolve_mission_handle()`` (FR-009 --
   zero new resolution code), then the log's directory through the shared
   ``resolve_surface_dir_or_typed_error()`` delegator over
   ``resolve_status_surface()``, the resolver every status writer uses (#5466).
3. If ``--from-offset`` is given, call ``validate_resume_cursor()`` and turn a
   ``ResumeRefused`` into the FR-013 stderr envelope + non-zero exit.
4. Drive the core -- ``--once`` calls ``poll_once()`` directly, once; otherwise it
   iterates ``tail_events()``.

Every error/usage/refusal signal (``usage_error``, ``mission_not_found``,
``status_surface_unavailable``, ``invalid_resume_offset``,
``resume_content_mismatch``) goes through ``_err_console``
(STDERR), never ``_console`` -- modeled on ``agent_retrospect.py:593``/``:600``'s
pattern: ``_err_console.print_json(json.dumps({"error": ..., "detail": ...}))`` +
``raise typer.Exit(<n>)`` (one helper, ``_refuse``), NOT ``typer.BadParameter``. No Tail envelope is ever
printed to stderr.

``--mission``, never ``--feature*`` (C-003, charter Terminology Canon).

``__all__`` (C-007/C-002) does NOT apply here: this module lives under
``src/specify_cli/cli/commands/``, not ``src/charter/``/``src/kernel/``.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import typer

from specify_cli.cli.console import err_console as _err_console
from specify_cli.cli.selector_resolution import resolve_mission_handle
from specify_cli.context.mission_resolver import ResolvedMission
from specify_cli.coordination.surface_resolver import StatusReadPathNotFound, WorktreeRegistryUnavailable
from specify_cli.coordination.workspace import CoordinationWorkspaceBranchMismatch
from specify_cli.core.paths import locate_project_root
from specify_cli.missions._read_path_resolver import resolve_surface_dir_or_typed_error
from specify_cli.status import (
    EMPTY_DIGEST,
    ResumeRefused,
    TailCursor,
    mission_event_log_path,
    poll_once,
    tail_events,
    validate_resume_cursor,
)

app = typer.Typer(help="Event log tailing commands")


def _refuse(error: str, detail: str, exit_code: int) -> typer.Exit:
    """Print the ``{"error", "detail"}`` envelope on STDERR; return the exit to raise.

    Returned rather than raised so each call site reads ``raise _refuse(...)``
    and the type checker sees the branch end.
    """
    _err_console.print_json(json.dumps({"error": error, "detail": detail}))
    return typer.Exit(exit_code)


def _resolve_event_log_dir(repo_root: Path, resolved: ResolvedMission) -> Path:
    """Return the directory holding the Mission's resolved status surface (#5466).

    On a coordination-routed Mission the work package transitions live in the
    coordination worktree, not in ``resolved.feature_dir`` (the repository root
    checkout), so the directory comes from the shared
    :func:`resolve_surface_dir_or_typed_error` delegator over
    :func:`resolve_status_surface`, the resolver every status writer uses. It
    falls back to the handed mission dir when ``meta.json`` cannot be read.

    When the surface cannot be resolved -- the resolver fails closed
    (``StatusReadPathNotFound``, e.g. a deleted coordination branch), the
    coordination worktree is on another branch, or git cannot list worktrees --
    the command refuses rather than tail the root checkout's copy.

    An UNMATERIALIZED coordination surface (branch present, no worktree) resolves
    to the coordination path, which does not exist yet: ``--once`` prints nothing
    and a stream starts once the first write materializes it.

    Returns the directory rather than the file so a later log selector (#6611)
    can join another log name onto the same resolution.
    """
    try:
        surface_dir: Path = resolve_surface_dir_or_typed_error(repo_root, resolved.mission_slug, on_missing_meta=resolved.feature_dir)
    except (StatusReadPathNotFound, CoordinationWorkspaceBranchMismatch, WorktreeRegistryUnavailable) as exc:
        raise _refuse("status_surface_unavailable", str(exc), 1) from exc
    return surface_dir


@app.command("tail")
def tail_command(
    mission: str = typer.Option(
        ...,
        "--mission",
        help="Mission slug/handle whose status.events.jsonl to tail (no legacy feature-alias flag, C-003).",
    ),
    json_output: bool = typer.Option(  # noqa: ARG001 -- accepted-but-unused flag, matches decision.py's --json precedent
        True,
        "--json",
        help=(
            "JSON output. Currently the only supported mode (accepted for parity "
            "with the issue's invocation and with `docs query --json`; no "
            "human-readable mode exists, so this flag has no observable effect "
            "either way)."
        ),
    ),
    once: bool = typer.Option(
        False,
        "--once",
        help="Poll exactly once and exit -- no generator, no sleep, ever.",
    ),
    max_events: int | None = typer.Option(
        None,
        "--max-events",
        help="Stop the stream after emitting this many events/signals.",
    ),
    from_offset: int | None = typer.Option(
        None,
        "--from-offset",
        help="Resume from this byte offset in status.events.jsonl (FR-004/FR-013).",
    ),
    from_invariant: str | None = typer.Option(
        None,
        "--from-invariant",
        help=(
            "Content invariant (SHA-256 hex digest) paired with --from-offset for "
            "cross-restart content verification (FR-004/FR-013). Requires "
            "--from-offset; supplying this alone is a usage error."
        ),
    ),
) -> None:
    """Tail a mission's event log (``status.events.jsonl``) as JSON lines on stdout.

    Ordered dispatch (plan.md's CLI Surface section -- "exactly four things, none of
    them novel domain logic"):

    1. FR-004 usage check: ``--from-invariant`` without ``--from-offset``.
    2. FR-009 mission resolve.
    3. FR-013 resume validation (only when ``--from-offset`` is given).
    4. Drive the core.
    """
    # ------------------------------------------------------------------
    # 1. FR-004 usage check -- before ANY file/mission access.
    # ------------------------------------------------------------------
    if from_invariant is not None and from_offset is None:
        raise _refuse("usage_error", "--from-invariant requires --from-offset to anchor it", 2)

    # ------------------------------------------------------------------
    # 2. FR-009 mission resolve -- zero new resolution code. On an
    #    unresolvable slug resolve_mission_handle already emits the
    #    JSON-mode {"error": "mission_not_found", "handle": ...} shape on
    #    stderr and raises SystemExit(2); let that propagate as-is rather
    #    than re-wrapping it. The log itself lives on the resolved status
    #    surface, not necessarily in resolved.feature_dir (#5466).
    # ------------------------------------------------------------------
    repo_root = locate_project_root()
    if repo_root is None:
        raise _refuse(
            "repo_root_not_found",
            "Could not locate project root. Ensure you are inside a spec-kitty project (has .kittify/ or kitty-specs/).",
            1,
        )

    resolved = resolve_mission_handle(mission, repo_root, json_mode=True)
    log_path = mission_event_log_path(_resolve_event_log_dir(repo_root, resolved))

    # ------------------------------------------------------------------
    # 3. FR-013 resume validation -- only when --from-offset is supplied,
    #    called exactly once, before any streaming begins. Zero Tail
    #    envelopes are emitted for a refused invocation.
    # ------------------------------------------------------------------
    if from_offset is not None:
        try:
            cursor = validate_resume_cursor(log_path, from_offset, from_invariant)
        except ResumeRefused as exc:
            code = "resume_content_mismatch" if exc.reason == "content_mismatch" else "invalid_resume_offset"
            raise _refuse(code, str(exc), 2) from exc
    else:
        cursor = TailCursor(offset=0, content_invariant=EMPTY_DIGEST)

    # ------------------------------------------------------------------
    # 4. Drive the core. --once calls poll_once() directly, once -- no
    #    generator, no sleep at all (this is why "exits 0 without
    #    blocking", User Story 1 AC1, is trivially true). Otherwise iterate
    #    tail_events() (the core's own bounded-generator, injectable
    #    sleep_fn) in a plain `for` loop, optionally bounded by
    #    itertools.islice when --max-events is given. Neither branch ever
    #    opens log_path for writing (FR-010) -- both poll_once() and
    #    tail_events() are pure readers.
    # ------------------------------------------------------------------
    if once:
        result = poll_once(log_path, cursor)
        for event in result.events:
            print(json.dumps(event))
        return

    stream = tail_events(log_path, cursor)
    if max_events is not None:
        stream = itertools.islice(stream, max_events)
    for event in stream:
        print(json.dumps(event))
