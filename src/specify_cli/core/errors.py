"""Shared base for structured exceptions carrying a stable ``error_code``.

Several exception families across the codebase expose a machine-readable
``error_code`` so consumers branch on the typed value rather than
substring-matching human-readable messages (NFR-007). Before this base
those families re-decided the idiom each time (class-attr constant,
``__init__`` parameter, or full contextual ``to_dict()``), producing the
divergence flagged in #1893.

:class:`StructuredError` is the minimal shared contract: a default
``error_code`` class attribute and a default :meth:`to_dict`. New error
families subclass it and override ``error_code``; families predating this
base adopt it on next touch (no big-bang migration).
"""

from __future__ import annotations

from typing import Any

__all__ = ["StructuredError"]


class StructuredError(RuntimeError):
    """Base for exceptions carrying a stable, machine-readable ``error_code``.

    Subclasses override ``error_code`` with a stable identifier so consumers
    branch on the typed value rather than substring-matching the message
    (NFR-007, #1893). :meth:`to_dict` returns a JSON-serializable envelope;
    subclasses that carry extra contextual fields override it and extend the
    base payload.
    """

    error_code: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation for tooling."""
        return {"error_code": self.error_code, "message": str(self)}


class PlacementResolutionRequired(StructuredError):
    """Raised when a write site cannot resolve its canonical placement (D11).

    Fail-closed replacement for the forbidden checkout-derived commit grammars
    (``_get_current_branch() or planning_branch`` / the silent "conservative
    legacy preflight" degradation) — coord-primary-partition-lock WP03 / D11,
    contracts/seam-api.md. A genuine placement-resolution failure (an
    unmaterialized coordination worktree, or a ``coordination_branch`` declared
    in meta.json but torn down / never created in git, ...) must never silently
    commit to whatever branch the operator happens to have checked out. A
    genuinely-legacy, coordination-less mission resolves successfully; this
    error fires only on a REAL failure, which must be fixed via
    ``spec-kitty doctor coordination --fix`` (#5113 / FR-014 — it materializes
    a present branch and flattens a never-created one) or migration/backfill,
    never papered over with a silent runtime fallback.

    Single canonical home (consolidated from the two identical per-command
    copies formerly in implement.py + agent/mission_record_analysis.py, which
    shared this exact ``error_code``).
    """

    error_code = "PLACEMENT_RESOLUTION_REQUIRED"
