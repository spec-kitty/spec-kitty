"""Mission handle resolver: maps user-supplied handles to canonical mission identity.

Resolution priority (most-specific → least-specific):

1. **Full mission_id** (26-char ULID): exact match on ``meta.json.mission_id``
2. **mid8 prefix** (8 chars): match on ``mission_id[:8]``
3. **Full slug with numeric prefix** (e.g. ``"083-foo-bar"``): directory name match
4. **Human slug without prefix** (e.g. ``"foo-bar"``): stripped slug match
5. **Numeric prefix alone** (e.g. ``"083"``): directory prefix match

If a handle unambiguously identifies one mission at any priority level, it is
returned immediately.  If it matches multiple missions, ``AmbiguousHandleError``
is raised with the full candidate list.  If it matches zero missions at any
level, the resolver falls through to the next level; if all levels are
exhausted without a match, ``MissionNotFoundError`` is raised.

Missions whose ``meta.json`` lacks a ``mission_id`` are silently skipped during
index construction (they cannot be resolved by identity).  To fix such missions,
run ``spec-kitty migrate backfill-identity``.

Implementation note: ``kitty-specs/`` is walked once per ``resolve_mission``
call.  The resulting in-memory index is not cached across calls because the
resolver is used in short-lived CLI commands; caching can be added later if
profiling shows it is needed.

``MissionResolver`` port (mission-resolver-port-01KX1C05 WP02, FR-001/FR-005):
this module hosts the two concrete adapters for the ``MissionResolver``
Protocol defined in ``mission_runtime.mission_resolver_port`` — the real
``FsMissionResolver`` (wrapping the walk below) and the in-memory
``FakeMissionResolver`` stub (zero filesystem access, for FS-free tests). The
free ``resolve_mission`` function accepts an optional ``resolver`` so the walk
is injectable at its single call site; existing callers that omit ``resolver``
get exactly the previous behavior via a default-constructed
``FsMissionResolver``. No adapter is cached at module or process scope
(C-005) — each is request-scoped and re-walks (or re-reads its in-memory list)
on every ``resolve``/``all_missions`` call.
"""

from __future__ import annotations

from specify_cli.core.constants import KITTY_SPECS_DIR
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from mission_runtime import MissionResolver
from specify_cli.lanes.branch_naming import resolve_mid8, strip_numeric_prefix
from specify_cli.mission_metadata import load_meta

# NOTE: this module deliberately declares no ``__all__``. The dead-symbol gate
# (``tests/architectural/test_no_dead_symbols.py``) treats an ``__all__`` member
# with no cross-file ``src/`` caller as dead and — critically — never rescues an
# ``__all__`` member via intra-module use. ``FakeMissionResolver`` is green today
# ONLY because it is grandfathered as a *widened* (non-``__all__``) name in
# ``_WIDENED_SCOPE_GRANDFATHERED_470``; promoting it into ``__all__`` would strip
# that rescue and regress a pre-existing public symbol. The selection seam below
# (``MissionListing`` / ``list_missions_for_selection`` /
# ``sole_mission_for_selection`` / ``MISSION_NOT_FOUND_MESSAGE`` /
# ``mission_not_found_message``) is green on its own real cross-file callers in
# ``next_cmd.py`` / ``research.py`` / ``merge.py``; it stays out of ``__all__``
# only to keep the widened-name posture consistent, not for lack of callers.

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ULID_RE = re.compile(r"^[0-9A-Z]{26}$")
_MID8_RE = re.compile(r"^[0-9A-Z]{8}$")
_PREFIX_RE = re.compile(r"^(\d{3})-")

# Canonical not-found message template (capital ``M``), matching the
# ``materialize.py`` exemplar. This is the SINGLE source the four fixed commands
# (plan, tasks, research, merge fresh/resume) adopt so a bad ``--mission`` handle
# reads identically across them. It is deliberately NOT applied to:
#   * :class:`MissionNotFoundError` -- keeps its FR-005 identity-aware
#     ``spec-kitty migrate backfill-identity`` remediation; collapsing it would
#     regress the identity model.
#   * ``reconcile`` -- its "mission dossier not found" wording is semantically
#     distinct (a dossier, not a mission directory).
#   * ``next``'s explicit-handle path -- its ``_emit_mission_not_found_error``
#     keeps a richer, *quoted* envelope (``Mission not found: '<handle>'`` plus a
#     remediation line). ``next`` was not in the four-command unification scope;
#     it consumes the shared *selection* helpers below, not this string constant.
MISSION_NOT_FOUND_MESSAGE = "Mission not found: {handle}"


def mission_not_found_message(handle: str) -> str:
    """Render the canonical :data:`MISSION_NOT_FOUND_MESSAGE` for *handle*.

    Thin wrapper over the template so callers never re-spell the format string
    (Sonar S1192); the *handle* is inserted verbatim.
    """
    return MISSION_NOT_FOUND_MESSAGE.format(handle=handle)


# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResolvedMission:
    """Canonical resolved identity for a single mission.

    Attributes:
        mission_id: Full 26-character ULID string from ``meta.json``.
        mission_slug: Directory name in ``kitty-specs/`` (e.g. ``"083-foo-bar"``).
        feature_dir: Absolute path to the mission directory.
        mid8: First 8 characters of ``mission_id`` (short disambiguator).
    """

    mission_id: str
    mission_slug: str
    feature_dir: Path
    mid8: str


@dataclass(frozen=True)
class MissionListing:
    """One row per existing mission, for selection/discovery surfaces.

    Distinct from :class:`ResolvedMission`: a listing is legacy-tolerant (it
    counts missions that lack a ``mission_id`` and so cannot be resolved by
    identity), and it carries the human ``friendly_name`` that
    :class:`ResolvedMission` does not.

    Attributes:
        mission_slug: Directory name in ``kitty-specs/`` -- the copy-pasteable
            handle.
        mid8: First 8 characters of ``mission_id`` (short disambiguator), or
            ``None`` for a legacy mission whose ``meta.json`` lacks a
            ``mission_id``.
        friendly_name: Human title from ``meta.json``; falls back to
            ``mission_slug`` when absent so a listing never blanks.
    """

    mission_slug: str
    mid8: str | None
    friendly_name: str


class AmbiguousHandleError(Exception):
    """Raised when a handle matches more than one mission.

    Attributes:
        handle: The user-supplied handle that was ambiguous.
        candidates: All missions matched by the handle.
    """

    def __init__(self, handle: str, candidates: list[ResolvedMission]) -> None:
        self.handle = handle
        self.candidates = candidates
        super().__init__(str(self))

    def __str__(self) -> str:
        lines = [
            f'Error: mission handle "{self.handle}" matches multiple missions.',
            "",
            "Candidates:",
        ]
        for c in self.candidates:
            lines.append(f"  {c.mission_slug} (mission_id {c.mission_id}, mid8 {c.mid8})")
        lines.append("")
        lines.append("Re-run with a more specific handle:")
        for c in self.candidates:
            lines.append(f"  spec-kitty <command> --mission {c.mid8}")
            lines.append(f"  spec-kitty <command> --mission {c.mission_slug}")
        lines.append("")
        lines.append("For JSON output of all candidates:")
        lines.append(f"  spec-kitty doctor identity --mission {self.handle} --json")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable error payload for ``--json`` callers."""
        return {
            "error": "MISSION_AMBIGUOUS_SELECTOR",
            "handle": self.handle,
            "candidates": [
                {
                    "mission_id": c.mission_id,
                    "mid8": c.mid8,
                    "slug": c.mission_slug,
                    "feature_dir": str(c.feature_dir),
                }
                for c in self.candidates
            ],
        }


class MissionNotFoundError(Exception):
    """Raised when no mission matches the supplied handle.

    Fail-closed-loud (FR-005): the message always names
    ``spec-kitty migrate backfill-identity`` as a candidate remediation,
    since a cold-miss is indistinguishable, from the resolver's viewpoint,
    from "the mission exists but was silently skipped during indexing because
    its ``meta.json`` lacks a ``mission_id``" (see :func:`_build_index`). There
    is deliberately no ``is None`` / ``or slug`` fallback here — a miss always
    raises.

    Attributes:
        handle: The user-supplied handle that matched nothing.
    """

    def __init__(self, handle: str) -> None:
        self.handle = handle
        super().__init__(
            f'No mission found for handle "{handle}". '
            "If this is a legacy mission whose meta.json lacks a mission_id, "
            "run `spec-kitty migrate backfill-identity` to backfill it."
        )


# ---------------------------------------------------------------------------
# Internal: index construction
# ---------------------------------------------------------------------------


def _iter_mission_dirs(repo_root: Path) -> Iterator[Path]:
    """Yield each ``kitty-specs/`` child directory once, in slug order.

    The SINGLE ``kitty-specs/`` enumeration primitive for this module: both the
    identity index (:func:`_build_index`) and the legacy-tolerant selection
    listing (:func:`list_missions_for_selection`) consume it, so there is no
    second independent scan to drift (or to trip
    ``tests/architectural/test_mission_resolver_walker_gate.py``). Non-directory
    entries (e.g. a stray ``README.md``) are skipped; the population/identity
    predicate is left to each caller.
    """
    specs_dir = repo_root / KITTY_SPECS_DIR
    if not specs_dir.exists():
        return
    for entry in sorted(specs_dir.iterdir()):
        if entry.is_dir():
            yield entry


def _build_index(repo_root: Path) -> list[ResolvedMission]:
    """Walk ``kitty-specs/`` and return a list of indexable missions.

    Missions whose ``meta.json`` lacks a ``mission_id`` are silently skipped.
    Non-directory entries (e.g. ``README.md``) are also skipped. A ``meta.json``
    that parses to a non-object (e.g. a JSON array) is skipped here rather than
    crashing the index: per-mission topology validation belongs to the consumer
    (``status.aggregate._read_meta``), which fails the *targeted* mission closed
    with ``MissionMetadataUnavailable``.
    """
    missions: list[ResolvedMission] = []
    for entry in _iter_mission_dirs(repo_root):
        data = load_meta(entry, on_malformed="none")
        if data is None:
            # Missing, malformed, or a non-object meta.json (e.g. a JSON array)
            # — not indexable by identity. The consumer validates and fails
            # the targeted mission closed.
            continue
        mission_id: str | None = data.get("mission_id") or None
        if not mission_id:
            # Legacy mission without mission_id — cannot be resolved by identity.
            # Operator must run `spec-kitty migrate backfill-identity`.
            continue
        missions.append(
            ResolvedMission(
                mission_id=mission_id,
                mission_slug=entry.name,
                feature_dir=entry,
                mid8=resolve_mid8(entry.name, mission_id=mission_id),
            )
        )
    return missions


# ---------------------------------------------------------------------------
# Public selection/discovery seam (mission-handle-resolution WP01, FR-006/012)
# ---------------------------------------------------------------------------


def list_missions_for_selection(main_repo: Path) -> list[MissionListing]:
    """List every existing mission for selection/discovery, legacy included.

    The population rule counts any ``kitty-specs/`` directory bearing
    ``spec.md`` **or** ``meta.json`` — the SAME rule the agent-layer
    ``_list_feature_spec_candidates`` uses — so ``next`` and plan/tasks never
    disagree on the count. It deliberately includes legacy missions whose
    ``meta.json`` lacks a ``mission_id`` (and missions with only a ``spec.md``),
    which :meth:`FsMissionResolver.all_missions` silently drops.

    ``mission_id`` / ``mid8`` / ``friendly_name`` are read best-effort via
    :func:`load_meta` (tolerating a missing, malformed, or non-object
    ``meta.json``); ``mid8`` is ``None`` when no ``mission_id`` can be
    authoritatively derived, and ``friendly_name`` falls back to the slug so a
    listing never blanks. Ordering is deterministic (by ``mission_slug``) via
    :func:`_iter_mission_dirs`.

    Args:
        main_repo: Repository root containing the ``kitty-specs/`` tree.

    Returns:
        The mission listings in ``mission_slug`` order; empty when
        ``kitty-specs/`` is absent or holds no spec/meta-bearing directory.
    """
    listings: list[MissionListing] = []
    for entry in _iter_mission_dirs(main_repo):
        if not (entry / "spec.md").exists() and not (entry / "meta.json").exists():
            continue
        data = load_meta(entry, on_malformed="none") or {}
        # A syntactically valid meta.json can carry a non-string ``mission_id``
        # (e.g. a JSON number); guard the type so ``resolve_mid8``'s ``len()``
        # never crashes discovery for the whole repo over one odd file. This
        # keeps the ``str | None`` annotation honest.
        raw_mission_id = data.get("mission_id")
        mission_id: str | None = raw_mission_id if isinstance(raw_mission_id, str) else None
        mid8 = resolve_mid8(entry.name, mission_id=mission_id) or None
        friendly_raw = data.get("friendly_name")
        friendly_name = str(friendly_raw) if friendly_raw else entry.name
        listings.append(MissionListing(mission_slug=entry.name, mid8=mid8, friendly_name=friendly_name))
    return listings


def sole_mission_for_selection(main_repo: Path) -> str | None:
    """Return the sole mission's slug, or ``None`` for zero or more than one.

    FR-004 convention: a command with a missing ``--mission`` may auto-select
    when exactly one mission exists, but must NEVER silently pick among
    several. Thin over :func:`list_missions_for_selection` so every consumer
    (``next`` and the plan/tasks/merge gates) shares one population definition.
    """
    listings = list_missions_for_selection(main_repo)
    if len(listings) == 1:
        return listings[0].mission_slug
    return None


# ---------------------------------------------------------------------------
# Internal: form classifiers
# ---------------------------------------------------------------------------


def _is_full_ulid(handle: str) -> bool:
    """Return True if the handle looks like a full 26-char ULID."""
    return bool(_ULID_RE.match(handle))


def _is_mid8(handle: str) -> bool:
    """Return True if the handle looks like a mid8 (8 uppercase alphanumeric chars)."""
    return bool(_MID8_RE.match(handle))


def _is_numeric_prefix(handle: str) -> bool:
    """Return True if the handle is a pure digit string (e.g. '083')."""
    return handle.isdigit()


# ---------------------------------------------------------------------------
# Public resolver
# ---------------------------------------------------------------------------


def _resolve_from_index(handle: str, missions: list[ResolvedMission]) -> ResolvedMission:
    """Resolve ``handle`` against an already-built in-memory mission index.

    This is the priority ladder shared by :class:`FsMissionResolver` (over a
    fresh ``_build_index`` walk) and :class:`FakeMissionResolver` (over a
    caller-supplied in-memory list) — the single fail-closed-loud resolution
    algorithm (FR-005), independent of where ``missions`` came from.

    Resolution priority (see module docstring):
    1. Full mission_id (26-char ULID)
    2. mid8 prefix (8 chars of upper alphanumeric)
    3. Full slug with numeric prefix (directory name)
    4. Human slug without prefix
    5. Numeric prefix alone (all-digits handle)

    Raises:
        AmbiguousHandleError: The handle matches more than one mission.
        MissionNotFoundError: The handle matches no mission.
    """
    # ------------------------------------------------------------------
    # Priority 1: Full mission_id (exact 26-char ULID)
    # ------------------------------------------------------------------
    if _is_full_ulid(handle):
        matches = [m for m in missions if m.mission_id == handle]
        return _resolve_or_raise(handle, matches)

    # ------------------------------------------------------------------
    # Priority 2: mid8 prefix (8 uppercase alphanum chars)
    # Note: also catches shorter unique prefixes (partial mid8) via startswith.
    # ------------------------------------------------------------------
    if _is_mid8(handle):
        matches = [m for m in missions if m.mission_id.startswith(handle)]
        return _resolve_or_raise(handle, matches)

    # ------------------------------------------------------------------
    # Priority 3: Full slug with numeric prefix (e.g. "083-foo-bar")
    # ------------------------------------------------------------------
    matches = [m for m in missions if m.mission_slug == handle]
    if matches:
        return _resolve_or_raise(handle, matches)

    # ------------------------------------------------------------------
    # Priority 4: Human slug without numeric prefix (e.g. "foo-bar")
    # ------------------------------------------------------------------
    if not _is_numeric_prefix(handle):
        human_matches = [m for m in missions if strip_numeric_prefix(m.mission_slug) == handle]
        if human_matches:
            return _resolve_or_raise(handle, human_matches)

    # ------------------------------------------------------------------
    # Priority 5: Numeric prefix (all-digits string, e.g. "083")
    # ------------------------------------------------------------------
    if _is_numeric_prefix(handle):
        prefix_matches = [
            m
            for m in missions
            if _PREFIX_RE.match(m.mission_slug) and _PREFIX_RE.match(m.mission_slug).group(1) == handle  # type: ignore[union-attr]
        ]
        return _resolve_or_raise(handle, prefix_matches)

    raise MissionNotFoundError(handle)


# ---------------------------------------------------------------------------
# MissionResolver port adapters (mission-resolver-port-01KX1C05 WP02)
# ---------------------------------------------------------------------------


class FsMissionResolver:
    """Real :class:`~mission_runtime.MissionResolver` adapter.

    Wraps the existing ``kitty-specs/`` walk (:func:`_build_index`) and the
    priority-ladder resolution (:func:`_resolve_from_index`). Bound to a
    single ``repo_root`` at construction so callers pass only the handle.

    Request-scoped: every call to :meth:`resolve` / :meth:`all_missions`
    re-walks ``kitty-specs/`` — there is no module or process-level cache
    (C-005); an instance may be reused across calls within one request without
    changing this contract, since the walk itself is not memoized.
    """

    def __init__(self, repo_root: Path) -> None:
        self._repo_root = repo_root

    def resolve(self, handle: str) -> ResolvedMission:
        """Resolve ``handle`` via a fresh walk of ``kitty-specs/``.

        Raises:
            AmbiguousHandleError: The handle matches more than one mission.
            MissionNotFoundError: The handle matches no mission. The error
                message names ``spec-kitty migrate backfill-identity`` for
                legacy missions missing ``mission_id``.
        """
        return _resolve_from_index(handle, _build_index(self._repo_root))

    def all_missions(self) -> list[ResolvedMission]:
        """Return every identity-bearing mission found by a fresh walk.

        Missions whose ``meta.json`` lacks a ``mission_id`` are silently
        skipped, exactly as :func:`_build_index` does today (C-001) — this
        preserves ``status/identity_audit.py``'s separate, non-routed walk as
        the only surface that finds them.
        """
        return _build_index(self._repo_root)


class FakeMissionResolver:
    """In-memory :class:`~mission_runtime.MissionResolver` stub.

    Constructed from a caller-supplied list of canonical-shaped
    :class:`ResolvedMission` fixtures. Performs **zero** filesystem access,
    enabling FS-free tests of consumers built against the ``MissionResolver``
    Protocol (NFR-001) — including with no ``kitty-specs/`` tree present at
    all.

    Applies the same fail-closed-loud priority ladder as
    :class:`FsMissionResolver` (:func:`_resolve_from_index`): ambiguous
    handles raise :class:`AmbiguousHandleError`; cold-misses raise
    :class:`MissionNotFoundError`.
    """

    def __init__(self, missions: list[ResolvedMission]) -> None:
        self._missions = list(missions)

    def resolve(self, handle: str) -> ResolvedMission:
        """Resolve ``handle`` against the in-memory fixture list."""
        return _resolve_from_index(handle, self._missions)

    def all_missions(self) -> list[ResolvedMission]:
        """Return the in-memory fixture list, unfiltered (already canonical)."""
        return list(self._missions)


def resolve_mission(
    handle: str,
    repo_root: Path,
    *,
    resolver: MissionResolver | None = None,
) -> ResolvedMission:
    """Resolve a user-supplied handle to a canonical mission.

    This is the single injection site for the ``MissionResolver`` port
    (mission-resolver-port-01KX1C05 WP02): callers that pass no ``resolver``
    get exactly the previous behavior (a fresh :class:`FsMissionResolver` over
    ``repo_root``); callers threading a resolver (e.g. a
    :class:`FakeMissionResolver` in a test) get theirs instead.

    Args:
        handle: A mission handle in any supported form (see module docstring
            for the full priority ladder).
        repo_root: Absolute path to the repository root. Ignored when
            ``resolver`` is supplied (the resolver owns its own scope).
        resolver: Optional :class:`~mission_runtime.MissionResolver` to
            delegate to. Defaults to a fresh ``FsMissionResolver(repo_root)``.

    Returns:
        The uniquely resolved :class:`ResolvedMission`.

    Raises:
        AmbiguousHandleError: The handle matches more than one mission.
        MissionNotFoundError: The handle matches no mission.
    """
    active_resolver: MissionResolver = resolver or FsMissionResolver(repo_root)
    # The Protocol return type is the structural ResolvedMissionLike (D-Q2):
    # mission_runtime cannot reference this module's concrete ResolvedMission.
    # Every MissionResolver implementation in this codebase (FsMissionResolver,
    # FakeMissionResolver — the only two that exist) is constructed here and
    # is known, by this module's own construction, to return ResolvedMission.
    return cast(ResolvedMission, active_resolver.resolve(handle))


# ---------------------------------------------------------------------------
# Internal: resolve-or-raise helper
# ---------------------------------------------------------------------------


def _resolve_or_raise(handle: str, matches: list[ResolvedMission]) -> ResolvedMission:
    """Return the single match, raise on zero or multiple matches."""
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise AmbiguousHandleError(handle, matches)
    raise MissionNotFoundError(handle)
