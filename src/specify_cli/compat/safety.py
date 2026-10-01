# =============================================================================
# SAFETY REGISTRY — CLI command classification for schema-mismatch gate
#
# If you add a new CLI command, register it here (in SAFETY_REGISTRY) or it
# will be treated as UNSAFE under schema mismatch.
#
# Keys are command_path tuples, e.g. ("upgrade",) or ("agent", "mission",
# "branch-context").  A value of None means "always safe".  A callable value
# (SafetyPredicate) is consulted at classify() time; any exception it raises
# falls back to UNSAFE (fail-closed defensive behaviour).
# =============================================================================
"""Safety classification for CLI invocations under schema-mismatch conditions.

Design note — avoiding import cycles
--------------------------------------
``classify()`` needs to inspect an ``Invocation`` object, but the canonical
``Invocation`` dataclass lives in the planner package which has not been
implemented yet (later WP).  To avoid a forward-import cycle we define a
local ``Protocol`` describing only the two fields we actually read
(``command_path`` and ``raw_args``).  Any object that satisfies the protocol
— including ``types.SimpleNamespace`` in tests and the real ``Invocation``
at runtime — will work correctly.

Thread-safety note
------------------
``SAFETY_REGISTRY`` is a plain ``dict``.  CPython's GIL guarantees that
individual ``dict`` read/write operations are atomic, so concurrent calls to
``classify()`` and ``register_safety()`` from different threads are safe
without additional locking.  This is consistent with standard CPython dict
usage patterns.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from typing import Protocol, runtime_checkable


class Safety(StrEnum):
    """Classification of a CLI command path under schema-mismatch conditions."""

    SAFE = "safe"
    UNSAFE = "unsafe"


@runtime_checkable
class _InvocationProtocol(Protocol):
    """Structural protocol for objects that can be classified by safety.classify().

    This avoids importing from the planner package (not yet implemented) and
    prevents circular imports.  Any object with these two attributes satisfies
    the protocol — including SimpleNamespace in tests.
    """

    @property
    def command_path(self) -> tuple[str, ...]:
        """Command path segments for safety classification."""
        ...

    @property
    def raw_args(self) -> tuple[str, ...]:
        """Raw CLI arguments for predicate-based classification."""
        ...


_Invocation = _InvocationProtocol

# Public type alias — used by callers that want to register a predicate.
SafetyPredicate = Callable[[_InvocationProtocol], Safety]

# ---------------------------------------------------------------------------
# Predicate: the recommended runtime-state diagnostic (FR-003 / #3338)
# ---------------------------------------------------------------------------
# The failed ``backfill-runtime-state`` migration aborts recommending
# ``spec-kitty migrate backfill-runtime-state --mission <slug> --dry-run`` to
# inspect the cause (upgrade/migrations/m_zz_runtime_state_backfill.py).  That
# read-only ``--dry-run`` diagnostic must stay reachable on a wedged/LEGACY
# project, while the mutating form (no ``--dry-run``) stays UNSAFE under schema
# mismatch.  ``classify()`` already treats any predicate exception as UNSAFE, so
# this predicate is fail-closed by construction.
_DRY_RUN_FLAG = "--dry-run"


def _dry_run_is_safe(invocation: _InvocationProtocol) -> Safety:
    """SAFE iff ``--dry-run`` is present in ``raw_args``; UNSAFE otherwise.

    Any failure to read ``raw_args`` propagates as an exception, which
    ``classify()`` converts to UNSAFE — so the mutating migration path is never
    opened under a malformed or unexpected invocation (fail-closed).
    """
    return Safety.SAFE if _DRY_RUN_FLAG in invocation.raw_args else Safety.UNSAFE

# ---------------------------------------------------------------------------
# Central registry
# ---------------------------------------------------------------------------
# Keys   — command_path tuple matching Invocation.command_path
# Values — None (always safe) or SafetyPredicate (ask the predicate)
# Anything NOT in the registry is classified as UNSAFE (fail-closed).
#
# Seed entries cover all commands that must remain accessible when the CLI
# detects a schema mismatch.  Later mission packages may override entries
# for "doctor" with mode predicates.
# ---------------------------------------------------------------------------
SAFETY_REGISTRY: dict[tuple[str, ...], SafetyPredicate | None] = {
    # Remediation path — must always be reachable
    ("upgrade",): None,
    ("migrate",): None,
    # The recommended runtime-state diagnostic must be reachable on a wedged
    # project (FR-003 / #3338): SAFE only in its read-only ``--dry-run`` form;
    # the mutating form stays UNSAFE via the fail-closed predicate below.
    ("migrate", "backfill-runtime-state"): _dry_run_is_safe,
    # Creates project, no existing metadata to mismatch against
    ("init",): None,
    # Read-only introspection commands
    ("status",): None,
    # Doctor — initially unconditionally safe; a later mission package
    # replaces this with a mode predicate once mode-awareness is implemented.
    ("doctor",): None,
    # Help / version are short-circuited before the planner runs (handled in
    # the typer-callback wiring package) but registered here for completeness.
    ("help",): None,
    ("version",): None,
    # Agent sub-commands — read-only / diagnostic only.
    # NOTE: ("agent", "mission", "setup-plan") is intentionally absent — it
    # scaffolds plan.md and commits to the target branch (project mutation) and
    # must therefore be treated as UNSAFE under schema mismatch.
    ("agent", "check-prerequisites"): None,
    ("agent", "mission", "branch-context"): None,
    ("agent", "mission", "check-prerequisites"): None,
    ("agent", "context", "resolve"): None,
    ("agent", "tasks", "status"): None,
}


def register_safety(
    command_path: str | tuple[str, ...],
    predicate: SafetyPredicate | None = None,
) -> None:
    """Register (or override) a command_path entry in SAFETY_REGISTRY.

    Parameters
    ----------
    command_path:
        Either a bare string (normalised to a single-element tuple) or a
        tuple of path segments, e.g. ``("agent", "mission", "setup-plan")``.
    predicate:
        ``None`` — the command is unconditionally SAFE.
        ``SafetyPredicate`` — callable consulted at classify() time.

    Updating an existing entry replaces the prior predicate.  This is
    intentional: later mission packages use this to swap in mode-aware
    predicates for ``doctor``.
    """
    if isinstance(command_path, str):
        command_path = (command_path,)
    SAFETY_REGISTRY[command_path] = predicate


def classify(invocation: _InvocationProtocol) -> Safety:
    """Classify *invocation* as SAFE or UNSAFE.

    Lookup semantics:
    - Not found in registry → ``Safety.UNSAFE`` (fail-closed).
    - Found with ``None`` value → ``Safety.SAFE``.
    - Found with callable → call the predicate; any exception → ``Safety.UNSAFE``.
    """
    if invocation.command_path not in SAFETY_REGISTRY:
        # Missing registry entries must fail closed.
        return Safety.UNSAFE

    predicate = SAFETY_REGISTRY[invocation.command_path]

    if predicate is None:
        # Key present, value explicitly None → always safe
        return Safety.SAFE

    # Key present with a callable predicate
    try:
        return predicate(invocation)
    except Exception:  # noqa: BLE001 - defensive: any exception -> UNSAFE
        return Safety.UNSAFE


__all__ = [
    "Safety",
    # SafetyPredicate: demoted — no cross-module src/ callers; type alias
    # used only within this module (WP01 harden-dead-symbol-gate-01KW0RJR).
    # SAFETY_REGISTRY: demoted — global dict written via register_safety();
    # no cross-module src/ from-import callers (WP01).
    "classify",
    "register_safety",
]
