"""Central CLI startup readiness coordinator implementation.

See spec: kitty-specs/cli-startup-readiness-coordinator-skeleton-01KS7JRV/spec.md
See data model: kitty-specs/cli-startup-readiness-coordinator-skeleton-01KS7JRV/data-model.md
See contracts: kitty-specs/cli-startup-readiness-coordinator-skeleton-01KS7JRV/contracts/readiness-api.md

The hosted auth/sync readiness surface was removed from open-core (#6164), so
the coordinator no longer gates on a hosted flag: it derives the output policy,
runs the (non-hosted) upgrade UX, and returns a disabled ``ReadinessResult``
cached on ``ctx.obj``.

Tracking issue: https://github.com/Priivacy-ai/spec-kitty/issues/1093
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import StrEnum

import typer

_READINESS_CTX_KEY = "readiness"
_PROTOCOL_OUTPUT_SUBCOMMANDS = frozenset({"do", "next"})


class OutputPolicy(StrEnum):
    """Three-bucket suppression classification.

    See ``data-model.md`` for the precedence rules.
    """

    INTERACTIVE = "interactive"
    NON_INTERACTIVE = "non_interactive"
    MACHINE_OUTPUT = "machine_output"


class AuthStatus(StrEnum):
    """Coordinator's record of Teamspace-auth state.

    Wave 1 (issue #1093) shipped ``NOT_CHECKED`` and ``DISABLED``. WS2
    (issue #1094) extends this enum with the authoritative values produced
    by the readiness auth probe
    (``specify_cli.readiness.auth.probe_auth_status``):
    ``AUTHENTICATED``, ``LOGGED_OUT_IN_TEAMSPACE``, ``NOT_IN_TEAMSPACE``,
    ``UNKNOWN``.

    ``NOT_CHECKED`` is preserved for backward compatibility with the Wave 1
    public contract but is no longer produced by the coordinator: on the
    hosted-enabled path the probe always sets one of the four authoritative
    values (or ``UNKNOWN`` on internal error). On the hosted-disabled path
    the coordinator continues to set ``DISABLED``.
    """

    NOT_CHECKED = "not_checked"
    DISABLED = "disabled"
    AUTHENTICATED = "authenticated"
    LOGGED_OUT_IN_TEAMSPACE = "logged_out_in_teamspace"
    NOT_IN_TEAMSPACE = "not_in_teamspace"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ReadinessResult:
    """Cached readiness verdict for a single CLI invocation.

    Frozen and slotted: subcommands MUST NOT mutate fields. Field additions
    in future missions are allowed; removals require a mission-level
    deprecation per ``contracts/readiness-api.md``.
    """

    enabled: bool
    ran: bool
    output_policy: OutputPolicy
    auth_status: AuthStatus
    nag_invoked: bool


_NOOP_DISABLED: ReadinessResult = ReadinessResult(
    enabled=False,
    ran=False,
    output_policy=OutputPolicy.NON_INTERACTIVE,
    auth_status=AuthStatus.DISABLED,
    nag_invoked=False,
)


def _derive_output_policy(
    argv: list[str] | None = None,
    *,
    ctx: typer.Context | None = None,
) -> OutputPolicy:
    """Classify the active suppression conditions into the 3-bucket policy.

    Precedence (highest first):
      ``MACHINE_OUTPUT`` — ``--json`` or ``--quiet`` in argv.
      ``NON_INTERACTIVE`` — ``--help``/``-h``/``--version``/``-v`` in argv,
                            OR ``is_ci_env()`` true,
                            OR stdout is not a TTY.
      ``INTERACTIVE`` — otherwise.

    Mirrors the signal set consulted by
    ``specify_cli.cli.helpers._should_suppress_nag`` but produces a
    three-bucket value instead of a single boolean. The single source of
    truth for nag suppression remains ``_should_suppress_nag`` inside
    ``_render_nag_if_needed``; this function records the bucket for
    downstream consumers (WS2 auth, WS3 upgrade UX).
    """
    if ctx is not None and ctx.invoked_subcommand in _PROTOCOL_OUTPUT_SUBCOMMANDS:
        return OutputPolicy.MACHINE_OUTPUT

    if argv is None:
        argv = sys.argv[1:]

    if "--json" in argv or "--quiet" in argv:
        return OutputPolicy.MACHINE_OUTPUT

    help_flags = {"--help", "-h", "--version", "-v"}
    if any(tok in help_flags for tok in argv):
        return OutputPolicy.NON_INTERACTIVE

    # Lazy import: keeps coordinator import-time cheap.
    from specify_cli.compat.planner import is_ci_env  # noqa: PLC0415

    if is_ci_env():
        return OutputPolicy.NON_INTERACTIVE

    try:
        if not sys.stdout.isatty():
            return OutputPolicy.NON_INTERACTIVE
    except Exception:  # noqa: BLE001 — isatty() can raise on exotic stream objects; treat as non-tty.
        return OutputPolicy.NON_INTERACTIVE

    return OutputPolicy.INTERACTIVE


def _read_cached(ctx: typer.Context) -> ReadinessResult | None:
    """Return the cached readiness result if reachable, else ``None``.

    Never raises. Returns ``None`` (not ``_NOOP_DISABLED``) so callers can
    distinguish "no cache" from "cached no-op".
    """
    obj = ctx.obj
    if not isinstance(obj, dict):
        return None
    cached = obj.get(_READINESS_CTX_KEY)
    if isinstance(cached, ReadinessResult):
        return cached
    return None


def _write_cached(ctx: typer.Context, result: ReadinessResult) -> None:
    """Store ``result`` on ``ctx.obj`` under ``_READINESS_CTX_KEY``.

    If ``ctx.obj`` is ``None``, initialize it to ``{}``. If ``ctx.obj`` is
    already a dict, set the key (other keys like ``compat_plan_result``
    remain untouched). If ``ctx.obj`` is a non-dict, non-None object
    (defensive), skip caching silently — ``get_readiness`` will return
    ``_NOOP_DISABLED`` for that ``ctx``.
    """
    obj = ctx.obj
    if obj is None:
        ctx.obj = {_READINESS_CTX_KEY: result}
        return
    if isinstance(obj, dict):
        obj[_READINESS_CTX_KEY] = result


def _invoke_nag(ctx: typer.Context) -> None:
    """Invoke the existing upgrade-nag renderer through the coordinator.

    Lazy import: ``helpers.callback`` imports ``evaluate_readiness`` from
    ``specify_cli.readiness`` at call time. Importing ``_render_nag_if_needed``
    at module scope here would form an import cycle.

    ``_render_nag_if_needed`` already swallows its own exceptions and applies
    its own suppression checks; this wrapper adds no gating of its own. It
    preserves byte-for-byte the pre-coordinator inline call from ``callback()``.
    """
    from specify_cli.cli.helpers import _render_nag_if_needed  # noqa: PLC0415

    _render_nag_if_needed(ctx)


def _evaluate_uncached(ctx: typer.Context) -> ReadinessResult:
    """Compute a fresh ``ReadinessResult`` for the current invocation.

    The hosted auth/sync readiness surface was removed from open-core (#6164).
    That removed the ``is_saas_sync_enabled()`` branch and the hosted path
    (auth probe + render + the hosted-mode upgrade UX). What remains is the
    former *disabled* path, which every open-core invocation already took
    (hosted shipped off): derive the output policy, fire the legacy upgrade
    nag exactly as ``callback()`` used to, and return a disabled result.

    No network I/O.
    """
    output_policy = _derive_output_policy(ctx=ctx)

    # The non-hosted default path, preserved byte-for-byte: the legacy upgrade
    # nag (``_render_nag_if_needed``) applies its own suppression and never
    # raises out of the CLI startup path.
    _invoke_nag(ctx)
    return ReadinessResult(
        enabled=False,
        ran=False,
        output_policy=output_policy,
        auth_status=AuthStatus.DISABLED,
        nag_invoked=True,
    )


def evaluate_readiness(ctx: typer.Context) -> ReadinessResult:
    """Compute (or return the cached) readiness result for this CLI invocation.

    Idempotent: a second call on the same ``ctx`` returns the cached
    ``ReadinessResult`` without re-running any logic (FR-009).

    Never raises. Internal exceptions are swallowed and the caller receives
    ``_NOOP_DISABLED`` instead (FR-010). The CLI cannot crash because of
    readiness logic.

    Side effects:
      - On the first invocation, stores the result on
        ``ctx.obj['readiness']`` when ``ctx.obj`` is ``None`` or a dict.
      - Invokes ``_render_nag_if_needed(ctx)`` exactly once during the
        first invocation under both the disabled and enabled paths.
    """
    cached = _read_cached(ctx)
    if cached is not None:
        return cached

    try:
        result = _evaluate_uncached(ctx)
    except Exception:  # noqa: BLE001 — coordinator must never raise out of the CLI startup path.
        result = _NOOP_DISABLED

    _write_cached(ctx, result)
    return result


def get_readiness(ctx: typer.Context) -> ReadinessResult:
    """Return the cached readiness result, or ``_NOOP_DISABLED`` if none cached.

    Never re-runs ``evaluate_readiness``. Never raises. Safe to call from
    any subcommand handler regardless of ``ctx.obj`` state.
    """
    cached = _read_cached(ctx)
    return cached if cached is not None else _NOOP_DISABLED
