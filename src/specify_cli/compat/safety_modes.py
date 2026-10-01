"""Mode-aware safety predicates for ``doctor`` and ``orchestrator-api`` commands.

This module registers predicates that classify ``doctor`` and
``orchestrator-api`` invocations as SAFE or UNSAFE based on the presence of mutating flags in
``raw_args``.  Read-only invocations (no mutating flags) are always SAFE;
write/kill/fix invocations are UNSAFE under schema mismatch.

Flag discovery (2026-04-27)
---------------------------
``doctor`` subcommands and flags inspected:
  - ``command-files``              read-only — SAFE
  - ``skills``                     read-only unless ``--fix`` — mode-aware
  - ``state-roots``                read-only — SAFE
  - ``identity``                   read-only — SAFE
    - ``--json``                   read-only output — SAFE
    - ``--mission``                scoping — SAFE
    - ``--fail-on``                read-only exit-code control — SAFE
  - ``shim-registry``              read-only — SAFE
    - ``--json``                   read-only output — SAFE
  - ``sparse-checkout``            read-only in detection-only mode — SAFE
    - ``--fix``                    UNSAFE: applies git remediation to disk

Adding new mutating flags in the future
---------------------------------------
If a future version of ``doctor`` adds new mutating flags, append them to
``_DOCTOR_UNSAFE_FLAGS``.

The predicate is non-breaking by default: an invocation without any of the
listed flags returns SAFE, preserving today's gate behaviour.

Doctor subcommand registration (FIX B, P2)
------------------------------------------
Each doctor subcommand is registered explicitly so that the full command path
(e.g. ``("doctor", "identity")``) matches in the SAFETY_REGISTRY.  Without
explicit entries a subcommand invocation falls through to UNSAFE (fail-closed),
which broke read-only diagnostics under schema mismatch.

Idempotent registration
-----------------------
``register_mode_predicates()`` can be called multiple times safely.
``register_safety`` stores predicates in a plain ``dict``; re-registering a
command path replaces the prior entry without duplication.
"""

from __future__ import annotations

from .safety import Safety, _InvocationProtocol, register_safety

# ---------------------------------------------------------------------------
# Doctor
# ---------------------------------------------------------------------------
# sparse-checkout --fix applies git remediation (disk mutation).
# All other doctor flags are read-only diagnostic output controls.
_DOCTOR_UNSAFE_FLAGS: frozenset[str] = frozenset(
    {
        "--fix",
    }
)


def _doctor_predicate(invocation: _InvocationProtocol) -> Safety:
    """Return UNSAFE if any doctor mutating flag is present, else SAFE.

    Used for bare ``doctor`` invocations (no subcommand — prints help/version
    and exits; no disk mutation).  Each subcommand is registered separately
    via ``register_mode_predicates()`` so the full command path matches.
    """
    if any(flag in invocation.raw_args for flag in _DOCTOR_UNSAFE_FLAGS):
        return Safety.UNSAFE
    return Safety.SAFE


def _sparse_checkout_predicate(invocation: _InvocationProtocol) -> Safety:
    """Return UNSAFE if ``--fix`` is present (disk mutation), else SAFE.

    ``doctor sparse-checkout`` without ``--fix`` is detection-only (read-only).
    ``doctor sparse-checkout --fix`` applies git remediation to disk.
    """
    if "--fix" in invocation.raw_args:
        return Safety.UNSAFE
    return Safety.SAFE


def _mission_state_predicate(invocation: _InvocationProtocol) -> Safety:
    """Return UNSAFE for mission-state repair, SAFE for audit/dry-run modes."""
    if "--fix" in invocation.raw_args:
        return Safety.UNSAFE
    return Safety.SAFE


# ---------------------------------------------------------------------------
# Orchestrator API
# ---------------------------------------------------------------------------
# Read-only API verbs and parser/usage errors must keep their JSON contract.
# Known state-mutating verbs remain unsafe under schema mismatch.
_ORCHESTRATOR_API_UNSAFE_SUBCOMMANDS: frozenset[str] = frozenset(
    {
        "start-implementation",
        "start-review",
        "transition",
        "append-history",
        "accept-mission",
        "merge-mission",
    }
)


def _orchestrator_api_predicate(invocation: _InvocationProtocol) -> Safety:
    """Classify orchestrator-api by its concrete API verb.

    Unknown or missing verbs are treated as SAFE so the command group can emit
    its JSON usage-error envelope instead of root prose.
    """
    args = list(invocation.raw_args)
    try:
        idx = args.index("orchestrator-api")
    except ValueError:
        return Safety.SAFE

    if len(args) <= idx + 1:
        return Safety.SAFE

    if args[idx + 1] in _ORCHESTRATOR_API_UNSAFE_SUBCOMMANDS:
        return Safety.UNSAFE

    return Safety.SAFE


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register_mode_predicates() -> None:
    """Register doctor and orchestrator-api mode-aware safety predicates.

    Replaces the unconditional ``None`` (always-SAFE) entries seeded in
    ``SAFETY_REGISTRY`` by WP04 with predicates that inspect ``raw_args``
    at classify-time.  Safe by default (no mutating flags → SAFE); only
    the flags listed in ``_DOCTOR_UNSAFE_FLAGS`` trigger UNSAFE classification.

    Doctor subcommands are registered explicitly (FIX B, P2) so that the full
    command path (e.g. ``("doctor", "identity")``) matches in the registry.
    Without these entries a subcommand invocation falls through to UNSAFE
    (fail-closed), blocking read-only diagnostics under schema mismatch.

    Calling this function multiple times is safe: each call replaces the
    prior predicate in-place (no duplicate registrations).
    """
    # Bare ``doctor`` (no subcommand — prints help, no disk mutation)
    register_safety(("doctor",), predicate=_doctor_predicate)
    # Doctor subcommands — all read-only except mode-aware repair commands.
    register_safety(("doctor", "command-files"), predicate=None)  # read-only
    register_safety(("doctor", "skills"), predicate=_doctor_predicate)  # mode-aware
    register_safety(("doctor", "state-roots"), predicate=None)  # read-only
    register_safety(("doctor", "identity"), predicate=None)  # read-only
    register_safety(("doctor", "mission-state"), predicate=_mission_state_predicate)  # mode-aware
    register_safety(("doctor", "shim-registry"), predicate=None)  # read-only
    register_safety(("doctor", "sparse-checkout"), predicate=_sparse_checkout_predicate)  # mode-aware
    # Orchestrator API — JSON parser/read-only paths safe; state transitions unsafe.
    register_safety(("orchestrator-api",), predicate=_orchestrator_api_predicate)


# Public re-exports for callers that want to import from this module directly.
# WP01 (harden-dead-symbol-gate-01KW0RJR): private/test-only symbols removed
# from __all__ (demoted to unexported internals). They remain importable by
# tests via the full qualified name; they are not runtime cross-module API.
__all__ = [
    "register_mode_predicates",
]
