"""Schema version gate for the Spec Kitty CLI.

``check_schema_version`` is called as a typer callback before every command
dispatch.  It delegates to ``compat.planner.plan()`` which decides whether the
project is compatible with this CLI build.

Exempted commands that always pass through:
  - ``upgrade``  (fixes the problem)
  - ``init``     (creates the project, no existing metadata yet)
  - ``--version`` / ``--help``  (handled by typer's eager options before our callback)
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer


def _build_command_path(invoked_subcommand: str | None = None) -> tuple[str, ...]:
    """Build the full command path from sys.argv, e.g. ('agent', 'mission', 'branch-context').

    Uses ``sys.argv[1:]`` to construct the full path by collecting positional
    tokens until the first flag (``--something`` or ``-x``).  When
    ``invoked_subcommand`` is given and *does not match* the first positional
    token in ``sys.argv`` (e.g. tests invoke the gate directly without setting
    ``sys.argv``), the function falls back to ``(invoked_subcommand,)`` so that
    the safety registry can still classify single-level commands correctly.

    This two-phase approach guarantees that:
    - Real CLI runs with nested subcommands (``spec-kitty agent mission
      branch-context``) produce the full tuple ``("agent", "mission",
      "branch-context")``, which the registry can match.
    - Direct gate-function calls in tests (or typer callbacks that only know
      the top-level ``invoked_subcommand``) still work without requiring every
      caller to monkeypatch ``sys.argv``.

    Args:
        invoked_subcommand: The top-level subcommand name reported by typer's
            ``ctx.invoked_subcommand``, or ``None`` when no subcommand was
            given (e.g. bare ``spec-kitty`` invocation).

    Returns:
        A tuple of positional command-path segments, e.g.
        ``("agent", "mission", "branch-context")``.  Empty when no subcommand
        is present.

    Examples::

        sys.argv = ["spec-kitty", "agent", "mission", "branch-context", "--json"]
        _build_command_path("agent") -> ("agent", "mission", "branch-context")

        sys.argv = ["spec-kitty", "--help"]
        _build_command_path("doctor") -> ("doctor",)  # fallback to invoked_subcommand

        _build_command_path(None) -> ()
    """
    argv_path: list[str] = []
    for arg in sys.argv[1:]:
        if arg.startswith("-"):
            break
        argv_path.append(arg)

    # If sys.argv agrees with the invoked_subcommand (first token matches),
    # trust the full argv path — it has the complete nested structure.
    if invoked_subcommand is not None and argv_path and argv_path[0] == invoked_subcommand:
        if invoked_subcommand == "orchestrator-api":
            # The orchestrator API owns JSON error formatting for parse and
            # usage failures. Keep the top-level command path so its
            # mode-aware safety predicate can inspect raw_args and decide.
            return (invoked_subcommand,)
        return tuple(argv_path)

    # Otherwise, fall back: use invoked_subcommand as a single-element tuple.
    if invoked_subcommand is not None:
        return (invoked_subcommand,)

    # No subcommand at all.
    return ()


# Commands that are allowed to run even when the schema version is incompatible.
# Kept for backward compatibility (some tests may import _EXEMPT_COMMANDS).
# The compat.safety registry is the authoritative source for exemption logic.
_EXEMPT_COMMANDS: frozenset[str] = frozenset({"upgrade", "init"})


def check_schema_version(
    repo_root: Path,
    invoked_subcommand: str | None = None,
) -> None:
    """Verify the project schema version before executing any CLI command.

    Behaviour:
    - If ``.kittify/`` does not exist: skip (uninitialized project, let ``init``
      handle it).
    - If the invoked subcommand is in ``_EXEMPT_COMMANDS``: skip (defense-in-depth;
      these are also SAFE in the compat.safety registry).
    - Otherwise: build an Invocation and delegate to ``compat.planner.plan()``.
      Block if the decision is BLOCK_PROJECT_MIGRATION, BLOCK_CLI_UPGRADE, or
      BLOCK_PROJECT_CORRUPT.

    Args:
        repo_root: Root of the project (parent of ``.kittify/``).
        invoked_subcommand: The subcommand name typer will dispatch to, or
            ``None`` when running without a subcommand (shows help).

    Raises:
        SystemExit: When the planner returns a blocking decision.
    """
    # Uninitialized project — no .kittify/ yet.  Let `init` run freely.
    kittify_dir = repo_root / ".kittify"
    if not kittify_dir.exists():
        return

    # Exempt upgrade / init so users can always fix or bootstrap the project.
    # Defense-in-depth: the compat.safety registry also marks these as SAFE.
    if invoked_subcommand in _EXEMPT_COMMANDS:
        return

    # Deferred import to avoid circular imports at module load time.
    # compat.planner imports from migration.schema_version (not from gate),
    # so the cycle only occurs if we import at the top level.
    from specify_cli.compat import Decision  # noqa: PLC0415
    from specify_cli.compat import Invocation  # noqa: PLC0415
    from specify_cli.compat import is_ci_env  # noqa: PLC0415
    from specify_cli.compat import plan as compat_plan  # noqa: PLC0415

    inv = Invocation(
        command_path=_build_command_path(invoked_subcommand),
        raw_args=tuple(sys.argv[1:]),
        is_help="--help" in sys.argv or "-h" in sys.argv,
        is_version=bool(sys.argv[1:2]) and sys.argv[1] in {"--version", "-v"},
        flag_no_nag="--no-nag" in sys.argv,
        env_ci=is_ci_env(),
        stdout_is_tty=sys.stdout.isatty(),
    )

    # Provide the known repo_root directly so the planner does not walk from cwd.
    _root = repo_root

    def _resolver(_cwd: Path) -> Path | None:
        return _root

    result = compat_plan(inv, project_root_resolver=_resolver)

    if result.decision in {
        Decision.BLOCK_PROJECT_MIGRATION,
        Decision.BLOCK_CLI_UPGRADE,
        Decision.BLOCK_PROJECT_CORRUPT,
    }:
        typer.echo(result.rendered_human, err=True)
        raise SystemExit(int(result.exit_code))
