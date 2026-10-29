"""Mission-identity health audit (FR-010, FR-011, FR-012, FR-045, NFR-002).

Four-state classifier
---------------------
Every mission in ``kitty-specs/`` is classified into one of four derived states
based on the presence / absence of ``mission_id`` and ``mission_number`` in
``meta.json`` (FR-045):

``assigned``
    ``mission_id`` is present AND ``mission_number`` is non-null.
    Fully migrated / post-merge.

``pending``
    ``mission_id`` is present AND ``mission_number`` is null.
    Pre-merge, waiting for merge-to-main number assignment.

``legacy``
    ``mission_id`` is missing AND ``mission_number`` is present.
    Pre-migration artifact; requires backfill.

``orphan``
    Both fields missing (or meta.json unreadable).
    Requires manual triage.

Duplicate-prefix report (FR-011)
---------------------------------
:func:`find_duplicate_prefixes` walks ``kitty-specs/`` and groups mission
directories by their 3-digit leading numeric prefix.  Any group with ≥ 2
members is reported.

Selector-ambiguity report (FR-012)
------------------------------------
:func:`find_ambiguous_selectors` computes every handle form for each mission
(full slug, numeric prefix, human slug) and flags handles that map to ≥ 2
missions.

Performance: the full audit over 200 missions must complete in < 3 s (NFR-002).
All I/O is synchronous file reads; no subprocesses are spawned.
"""

from __future__ import annotations

from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.utils import safe_is_dir
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from specify_cli.lanes.branch_naming import strip_numeric_prefix
from specify_cli.mission_metadata import _coerce_mission_number

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

IdentityStateLabel = Literal["assigned", "pending", "legacy", "orphan"]

# Regex to extract exactly 3-digit leading prefix from a directory name.
_PREFIX_RE = re.compile(r"^(\d{3})-")


@dataclass
class IdentityState:
    """Audit result for a single mission directory.

    Attributes:
        path: Absolute path to the mission directory (e.g. ``kitty-specs/083-foo``).
        slug: Directory name used as the mission slug.
        mission_id: ULID string from ``meta.json``, or ``None`` if missing.
        mission_number: Integer from ``meta.json`` (after coercion), or ``None``.
        state: Four-state label per FR-045.
        error: Non-empty when ``meta.json`` could not be read / parsed.
    """

    path: Path
    slug: str
    mission_id: str | None
    mission_number: int | None
    state: IdentityStateLabel
    error: str | None = field(default=None)

    def to_dict(self) -> dict[str, object]:
        """Serialise to a JSON-compatible dict."""
        return {
            "path": str(self.path),
            "slug": self.slug,
            "mission_id": self.mission_id,
            "mission_number": self.mission_number,
            "state": self.state,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------


def classify_mission(feature_dir: Path) -> IdentityState:
    """Classify a single mission directory into one of the four identity states.

    Reads ``meta.json`` from *feature_dir*.  A corrupt or unreadable
    ``meta.json`` is classified as ``orphan`` with the ``error`` field
    populated — it does **not** propagate an exception.

    Args:
        feature_dir: Absolute path to a mission directory (must contain
            ``meta.json`` or be classifiable as an orphan without one).

    Returns:
        An :class:`IdentityState` for the mission.
    """
    slug = feature_dir.name
    meta_path = feature_dir / "meta.json"

    # --- Try to read meta.json -------------------------------------------------
    if not meta_path.exists():
        return IdentityState(
            path=feature_dir,
            slug=slug,
            mission_id=None,
            mission_number=None,
            state="orphan",
            error="meta.json not found",
        )

    try:
        # Canonical reader (FR-005/WP12): on_malformed="raise" folds the JSON-
        # syntax AND non-dict-shape checks into ONE ValueError (replacing the
        # hand-rolled isinstance guard); allow_missing=True keeps this call
        # FR-007: fail-closed reader routing. Malformed meta surfaces typed
        # MissionMetaReadError instead of raw ValueError. Never-crashing (matches
        # the never-raise contract of classify_mission).
        # ``or {}`` narrows the ``dict | None`` return type for the type checker.
        from specify_cli.core.paths import load_meta_fail_closed, MissionMetaReadError
        raw = load_meta_fail_closed(feature_dir) or {}
    except (OSError, MissionMetaReadError) as exc:
        return IdentityState(
            path=feature_dir,
            slug=slug,
            mission_id=None,
            mission_number=None,
            state="orphan",
            error=str(exc),
        )

    # --- Extract fields --------------------------------------------------------
    mission_id: str | None = raw.get("mission_id") or None  # treat "" as None
    raw_number = raw.get("mission_number")
    try:
        mission_number: int | None = _coerce_mission_number(raw_number)
    except (TypeError, ValueError) as exc:
        # Sentinel string like "pending" or bad type — treat as None for classification.
        logger.debug("mission_number coercion error for %s: %s", feature_dir, exc)
        mission_number = None

    # --- Four-state matrix (FR-045) -------------------------------------------
    if mission_id is not None and mission_number is not None:
        state: IdentityStateLabel = "assigned"
    elif mission_id is not None and mission_number is None:
        state = "pending"
    elif mission_id is None and mission_number is not None:
        state = "legacy"
    else:
        state = "orphan"

    return IdentityState(
        path=feature_dir,
        slug=slug,
        mission_id=mission_id,
        mission_number=mission_number,
        state=state,
    )


# ---------------------------------------------------------------------------
# Repo-level audit
# ---------------------------------------------------------------------------


def iter_kitty_specs_children(repo_root: Path) -> list[Path]:
    """Return the sorted directory children of ``kitty-specs/`` (the doctor audits' one raw walk).

    Shared by :func:`audit_repo`, :func:`find_duplicate_prefixes` and
    ``doctor mission-type``'s ``audit_mission_types``. An absent
    ``kitty-specs/``, or an ``OSError`` while listing it (an unreadable
    ancestor), yields ``[]``: a read-only, best-effort survey must not crash on
    an unreadable ancestor any more than on an absent one, the same posture as
    ``specify_cli.audit.engine._scan_missions``. Entries that are not
    directories (``README.md``, templates) are skipped, and so, per `#3194`,
    is an entry that cannot be examined at all (most commonly ``EACCES``
    behind a symlink): it is folded into the SAME "not a directory" skip
    rather than raising or silently vanishing depending on interpreter (see
    ``safe_is_dir``'s docstring for why ``Path.is_dir()``/``Path.exists()``
    cannot be used here unguarded).
    """
    specs_dir = repo_root / KITTY_SPECS_DIR
    try:
        if not safe_is_dir(specs_dir):
            return []
        entries = sorted(specs_dir.iterdir())
    except OSError:
        return []

    children: list[Path] = []
    for entry in entries:
        try:
            is_dir = safe_is_dir(entry)
        except OSError:
            continue  # unstattable entry: same skip as "not a directory"
        if is_dir:
            children.append(entry)
    return children


def audit_repo(repo_root: Path) -> list[IdentityState]:
    """Walk ``kitty-specs/`` and classify every mission directory.

    Directories without a ``meta.json`` are classified as ``orphan``.
    Entries that are not directories (e.g. ``README.md``) are silently skipped —
    including entries that cannot be examined at all (`#3194`: an unreadable
    ancestor or an unstattable candidate, most commonly `EACCES` behind a
    symlink, is folded into the SAME "not a directory" skip rather than raising
    or silently vanishing depending on interpreter — see `safe_is_dir`'s
    docstring for why `Path.is_dir()`/`Path.exists()` cannot be used here
    unguarded).
    An empty or absent ``kitty-specs/`` directory returns an empty list.

    Args:
        repo_root: Path to the repository root (contains ``kitty-specs/``).

    Returns:
        Sorted list of :class:`IdentityState` objects, one per mission directory.
    """
    return [classify_mission(entry) for entry in iter_kitty_specs_children(repo_root)]


# ---------------------------------------------------------------------------
# Summarise
# ---------------------------------------------------------------------------


def summarize(states: list[IdentityState]) -> dict[str, object]:
    """Aggregate a list of :class:`IdentityState` objects into a summary dict.

    Returns a dict with:
    - ``counts``: ``{state: int}`` for all four states (zero-filled)
    - ``legacy_paths``: list of ``str`` paths for legacy missions
    - ``orphan_paths``: list of ``str`` paths for orphan missions

    Args:
        states: Flat list from :func:`audit_repo`.
    """
    counts: dict[str, int] = {"assigned": 0, "pending": 0, "legacy": 0, "orphan": 0}
    legacy_paths: list[str] = []
    orphan_paths: list[str] = []

    for s in states:
        counts[s.state] += 1
        if s.state == "legacy":
            legacy_paths.append(str(s.path))
        elif s.state == "orphan":
            orphan_paths.append(str(s.path))

    return {
        "counts": counts,
        "legacy_paths": legacy_paths,
        "orphan_paths": orphan_paths,
    }


# ---------------------------------------------------------------------------
# Duplicate-prefix report (FR-011)
# ---------------------------------------------------------------------------


def find_duplicate_prefixes(repo_root: Path) -> dict[str, list[IdentityState]]:
    """Report every 3-digit numeric prefix shared by ≥ 2 mission directories.

    Walks ``kitty-specs/`` and groups directories by their leading ``NNN-``
    prefix (regex ``^(\\d{3})-``).  Only groups with size ≥ 2 are returned.

    Directories without a leading numeric prefix are silently skipped — as is,
    per `#3194`, an entry that cannot be examined at all (see the matching note
    on :func:`audit_repo`).

    Args:
        repo_root: Path to the repository root.

    Returns:
        ``{"NNN": [<IdentityState>, ...]}`` for every duplicated prefix.
        Empty dict when no duplicates exist.
    """
    groups: dict[str, list[IdentityState]] = {}
    for entry in iter_kitty_specs_children(repo_root):
        m = _PREFIX_RE.match(entry.name)
        if not m:
            continue
        prefix = m.group(1)
        state = classify_mission(entry)
        groups.setdefault(prefix, []).append(state)

    return {prefix: items for prefix, items in groups.items() if len(items) >= 2}


# ---------------------------------------------------------------------------
# Selector-ambiguity report (FR-012)
# ---------------------------------------------------------------------------


def find_ambiguous_selectors(
    states: list[IdentityState],
) -> dict[str, list[IdentityState]]:
    """Report every selector handle that would resolve to ≥ 2 missions.

    For each mission, three handle forms are computed:
    - **Full slug** — the directory name (e.g. ``"083-foo-bar"``)
    - **Numeric prefix** — the leading 3-digit token (e.g. ``"083"``)
    - **Human slug** — the slug with its numeric prefix stripped (e.g. ``"foo-bar"``)

    Any handle that maps to ≥ 2 distinct missions is an ambiguity.

    A handle is an *exact* match — the handle ``"foo"`` does not ambiguate
    with ``"foobar"`` unless ``"foobar"`` is itself used as a full-slug
    handle (which it is not, since full-slug is the directory name).

    Args:
        states: Flat list from :func:`audit_repo`.

    Returns:
        ``{"handle": [<IdentityState>, ...]}`` for every ambiguous handle.
        Empty dict when every handle resolves to exactly one mission.
    """
    handle_map: dict[str, list[IdentityState]] = {}

    for state in states:
        slug = state.slug
        handles: set[str] = set()

        # Full slug handle
        handles.add(slug)

        # Numeric prefix handle
        m = _PREFIX_RE.match(slug)
        if m:
            handles.add(m.group(1))

        # Human slug handle (strip exactly NNN- prefix)
        human = strip_numeric_prefix(slug)
        if human != slug:
            handles.add(human)

        for handle in handles:
            handle_map.setdefault(handle, []).append(state)

    return {h: items for h, items in handle_map.items() if len(items) >= 2}
