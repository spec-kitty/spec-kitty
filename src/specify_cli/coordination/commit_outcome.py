"""Per-surface commit outcome contract (mission coord-artifact-single-home-01M3V4BE, WP05).

The single canonical home for the per-surface commit-outcome shape every
``commit_for_mission`` consumer renders through — ``contracts/commit-outcome.md``
(FR-006 / FR-007 / FR-007a / FR-007b / FR-005; SC-003). ``commit_router.py``
populates :class:`SurfaceOutcome` instances on ``CommitRouterResult.surfaces``;
this module owns the TYPES, the REASON CODES, and the ONE renderer / JSON
payload builder / exit-code helper every consumer shares (contract rule 6 —
"no consumer formats surface outcomes by hand").

Ownership direction (brownfield scout round 3, T024 CORRECTION): this module
must NOT import ``commit_router`` (that would cycle — ``commit_router`` imports
THIS module for the ``SurfaceOutcome`` / ``PathFate`` types it constructs).
Instead this module is the single owner of the status/reason string literals;
``commit_router.py`` and ``surface_authority.py`` both import them from here
rather than each declaring their own copy (Sonar S1192 — the literals were
previously duplicated across both modules).

No ``specify_cli.cli`` import (the layering guard, ``test_commit_router_layering.py``
forbids it transitively through ``commit_router``): this module never touches a
console; :func:`render_commit_outcome` only returns plain ``str`` lines, so any
stream-encoding concern (e.g. a cp1252 Windows console choking on ``✓``/``✗``) is
the caller's responsibility, not this pure function's.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal, Protocol, runtime_checkable

from specify_cli.coordination.coord_seed import CoordSeedForkRefused
from specify_cli.coordination.surface_resolver import (
    CoordinationBranchDeleted,
    CoordinationWorktreeUnmaterialized,
)
from specify_cli.coordination.types import PROTECTED_BRANCH_REFUSED

__all__ = [
    "PathFate",
    "SurfaceOutcome",
    "REASON_ALREADY_COMMITTED",
    "REASON_NO_CHANGES",
    "COORD_RECORD_IN_ROOT_CHECKOUT",
    "STATUS_LOCK_HELD",
    "PATH_UNROUTABLE",
    "WRONG_SURFACE",
    "PROTECTED_BRANCH_REFUSED",
    "COORDINATION_BRANCH_DELETED",
    "COORDINATION_WORKTREE_UNMATERIALIZED",
    "COORD_SEED_FORK_REFUSED",
    "render_commit_outcome",
    "commit_outcome_payload",
    "commit_outcome_exit_code",
]


@dataclass(frozen=True)
class PathFate:
    """One path's disposition within a :class:`SurfaceOutcome`'s ``skipped``/``refused`` list.

    ``path`` is the path AS THE CALLER PASSED IT (repo-relative); ``owning_path``
    names the owning-surface counterpart when the caller's path was translated
    (contract rule 2) — ``None`` when the path IS its own owning-surface path.
    """

    path: str
    reason: str
    owning_path: str | None = None


@dataclass(frozen=True)
class SurfaceOutcome:
    """One partition group's commit outcome (contract rule 1).

    ``CommitRouterResult.surfaces`` carries one of these per partition group the
    request touched, ordered PRIMARY then coordination (rule 1).
    """

    surface: Literal["primary", "coordination"]
    branch: str
    status: Literal["committed", "unchanged", "refused", "error"]
    commit_hash: str | None
    committed: tuple[str, ...] = ()
    skipped: tuple[PathFate, ...] = ()
    refused: tuple[PathFate, ...] = ()
    diagnostic: str | None = None


# ---------------------------------------------------------------------------
# Canonical status / reason literals (single owner — S1192).
#
# ``commit_router.py`` and ``surface_authority.py`` both import these rather
# than each declaring their own copy of the same strings.
# ---------------------------------------------------------------------------

#: The router's legacy top-level ``CommitRouterResult.status`` vocabulary
#: (unchanged by this WP — additive only). Named here, once, so neither
#: ``commit_router`` nor ``surface_authority`` restates the raw literal.
#: Typed with a precise ``Literal`` (not plain ``str``) so a ``Final``
#: re-import (``commit_router``'s ``_STATUS_COMMITTED: Final = commit_outcome.
#: STATUS_COMMITTED``) keeps the narrow literal type mypy --strict needs to
#: satisfy ``CommitRouterResult.status: Literal[...]``.
STATUS_COMMITTED: Final[Literal["committed"]] = "committed"
STATUS_UNCHANGED: Final[Literal["unchanged"]] = "unchanged"
STATUS_NO_OP_WRONG_SURFACE: Final[Literal["no_op_wrong_surface"]] = "no_op_wrong_surface"
STATUS_ERROR: Final[Literal["error"]] = "error"

#: #2739 B03 ``unchanged``-reason disambiguators (existing vocabulary, contract
#: "Reason codes" table — ``no_op_already_committed`` / ``no_op_no_changes``).
REASON_ALREADY_COMMITTED: Final[str] = "no_op_already_committed"
REASON_NO_CHANGES: Final[str] = "no_op_no_changes"

#: New reason codes this contract introduces (contract "Reason codes" table).
COORD_RECORD_IN_ROOT_CHECKOUT: Final[str] = "COORD_RECORD_IN_ROOT_CHECKOUT"
STATUS_LOCK_HELD: Final[str] = "STATUS_LOCK_HELD"
PATH_UNROUTABLE: Final[str] = "PATH_UNROUTABLE"
#: "Today's ``no_op_wrong_surface`` situation" (contract table) — a DISTINCT
#: literal from :data:`STATUS_NO_OP_WRONG_SURFACE` (the legacy top-level
#: status string): this one is the ``surfaces[*].refused[*].reason`` the new
#: contract uses; the legacy status string is unchanged (rule 4).
WRONG_SURFACE: Final[str] = "WRONG_SURFACE"

#: Existing reason codes, re-exported from their single owning module (never
#: duplicated as a second literal here).
#:
#: ``PROTECTED_BRANCH_REFUSED`` already resolves via the ``from ... import``
#: above (``coordination/types.py``).
#:
#: ``COORDINATION_BRANCH_DELETED`` / ``COORDINATION_WORKTREE_UNMATERIALIZED``
#: are class attributes (T024 CORRECTION, brownfield scout round 3) — there is
#: no bare module constant upstream, so this module mints the ONE constant
#: name consumers import, backed by the class attribute value.
COORDINATION_BRANCH_DELETED: Final[str] = CoordinationBranchDeleted.error_code
COORDINATION_WORKTREE_UNMATERIALIZED: Final[str] = CoordinationWorktreeUnmaterialized.error_code
COORD_SEED_FORK_REFUSED: Final[str] = CoordSeedForkRefused.error_code


# ---------------------------------------------------------------------------
# Renderer / payload / exit-code (contract rule 6 — the ONE shared trio).
# ---------------------------------------------------------------------------


@runtime_checkable
class _ResultWithSurfaces(Protocol):
    """Structural protocol: anything exposing ``surfaces`` can be rendered.

    So the wrapper results WP07/WP10 introduce can reuse this trio without
    depending on the concrete ``CommitRouterResult`` type. ``surfaces`` is a
    read-only ``@property`` (not a plain attribute) so a frozen dataclass
    field — which mypy treats as read-only — satisfies this Protocol; a plain
    mutable-attribute declaration would reject it (structural typing requires
    the SAME mutability, not just the same type).
    """

    @property
    def surfaces(self) -> tuple[SurfaceOutcome, ...]: ...


_GLYPH_OK: Final[str] = "✓"  # "✓"
_GLYPH_REFUSED: Final[str] = "✗"  # "✗"
_OK_STATUSES: Final[frozenset[str]] = frozenset({"committed", "unchanged"})


def _surface_label(outcome: SurfaceOutcome) -> str:
    return f"{outcome.surface} ({outcome.branch})"


def _render_surface_summary(outcome: SurfaceOutcome) -> str | None:
    """The surface's own summary line, or ``None`` when the per-path lines already say it all.

    A ``refused``/``error`` surface with at least one named path (``refused``)
    renders ONLY the per-path line(s) — a bare "refused" line above them would
    be redundant noise (contract example format: ``✗ coordination (...): refused
    — status.events.jsonl: STATUS_LOCK_HELD`` is the ONLY line for that surface).
    A bare refusal with no named path still needs its own summary line.
    """
    label = _surface_label(outcome)
    glyph = _GLYPH_OK if outcome.status in _OK_STATUSES else _GLYPH_REFUSED
    if outcome.status == STATUS_COMMITTED:
        short_hash = (outcome.commit_hash or "")[:7]
        return f"{glyph} {label}: committed {short_hash} — {len(outcome.committed)} files"
    if outcome.status == STATUS_UNCHANGED:
        return f"{glyph} {label}: unchanged"
    if outcome.status == STATUS_ERROR and not outcome.refused:
        suffix = f" — {outcome.diagnostic}" if outcome.diagnostic else ""
        return f"{glyph} {label}: error{suffix}"
    if outcome.status == "refused" and not outcome.refused:
        # A bare refusal with no named path — still emit a summary line.
        return f"{glyph} {label}: refused"
    return None


def _render_surface_path_lines(outcome: SurfaceOutcome) -> list[str]:
    """One line per refused path, plus one per *actionable* skipped path.

    A genuine no-op skip (``REASON_ALREADY_COMMITTED`` / ``REASON_NO_CHANGES``)
    carries nothing an operator must act on, so it is not rendered as a
    separate line (the surface summary already says ``unchanged``). A
    ``COORD_RECORD_IN_ROOT_CHECKOUT`` skip IS actionable — the operator's root
    edit will never reach the target — so it is always rendered.
    """
    label = _surface_label(outcome)
    lines: list[str] = []
    for fate in outcome.refused:
        lines.append(f"{_GLYPH_REFUSED} {label}: refused — {fate.path}: {fate.reason}")
    for fate in outcome.skipped:
        if fate.reason == COORD_RECORD_IN_ROOT_CHECKOUT:
            lines.append(f"{_GLYPH_OK} {label}: skipped — {fate.path}: {fate.reason}")
    return lines


def render_commit_outcome(result: _ResultWithSurfaces) -> list[str]:
    """Render *result* as one line per surface, then one line per named path (contract example format).

    ``[]`` for the empty-surfaces legacy case (a caller that never populated
    ``surfaces``) — there is nothing to render, never a crash.
    """
    lines: list[str] = []
    for outcome in result.surfaces:
        summary = _render_surface_summary(outcome)
        if summary is not None:
            lines.append(summary)
        lines.extend(_render_surface_path_lines(outcome))
    return lines


def _fate_payload(fate: PathFate) -> dict[str, object]:
    return {"path": fate.path, "reason": fate.reason, "owning_path": fate.owning_path}


def _surface_payload(outcome: SurfaceOutcome) -> dict[str, object]:
    return {
        "surface": outcome.surface,
        "branch": outcome.branch,
        "status": outcome.status,
        "commit_hash": outcome.commit_hash,
        "committed": list(outcome.committed),
        "skipped": [_fate_payload(fate) for fate in outcome.skipped],
        "refused": [_fate_payload(fate) for fate in outcome.refused],
        "diagnostic": outcome.diagnostic,
    }


def commit_outcome_payload(result: _ResultWithSurfaces) -> dict[str, object]:
    """The additive JSON shape for *result* (contract "JSON shape changes")."""
    return {"surfaces": [_surface_payload(outcome) for outcome in result.surfaces]}


def commit_outcome_exit_code(result: _ResultWithSurfaces) -> int:
    """The canonical exit code for *result* (contract rule 5).

    Non-zero iff any surface is ``refused`` or ``error``; ``skipped`` /
    ``unchanged`` exit 0. The empty-surfaces legacy case exits 0.
    """
    return 1 if any(outcome.status in ("refused", "error") for outcome in result.surfaces) else 0
