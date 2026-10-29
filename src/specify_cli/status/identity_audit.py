"""Mission-identity health audit (FR-010, FR-011, FR-012, FR-045, NFR-002).

Four Mission states plus ``residue``
------------------------------------
Every Mission in ``kitty-specs/`` is classified into one of four derived states
based on the presence / absence of ``mission_id`` and ``mission_number`` in
``meta.json`` (FR-045). A ``kitty-specs/`` child that is not a Mission at all
(:func:`~specify_cli.context.mission_resolver.is_selectable_mission_dir`
rejects it, so Mission selection does not list it) is ``residue`` (#5875):

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

``residue``
    Not a Mission: no ``meta.json`` on disk; or, in a git repository, a
    ``meta.json`` without a ``mission_id`` that git does not track (nor the
    ``spec.md``), or an unreadable one. Its ``residue_reason`` names which
    (:data:`RESIDUE_REASONS`). Set only by the walk, and
    only on request (``residue_aware=True``, ``doctor identity``), never by
    :func:`classify_mission`. Residue is left out of the duplicate-prefix and
    selector-ambiguity reports. The default walk keeps the pre-#5875 contract
    because the audit engine (``specify_cli.audit.engine``) consumes it and
    keeps its own, looser Mission rule, ``is_mission_dir`` (FR-008): there a
    tracked ``spec.md``, or any marker on a non-git root, makes a Mission, so
    its ``IDENTITY_MISSING`` / ``DUPLICATE_PREFIX`` / ``AMBIGUOUS_SELECTOR``
    findings must not disappear.

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
All I/O is synchronous file reads; a residue-aware walk adds at most one
batch ``git ls-files``, and none when every child carries a ``mission_id``. The probe is
:func:`~specify_cli.context.mission_resolver.tracked_mission_paths`, not the
hardened one: this is a read-only reporter, so a broken git index raises
:class:`~kernel.git.GitCommandError` rather than producing a silently weaker
answer (``doctor identity`` renders it as one error line).

Layering: the walk and the read-side Mission rule live in
``specify_cli.context.mission_resolver``, which imports ``specify_cli.status``
(through ``context.resolver``). They are imported inside the functions that
need them, so ``status`` keeps no module-level edge back into ``context``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from specify_cli.lanes.branch_naming import strip_numeric_prefix
from specify_cli.mission_metadata import _coerce_mission_number

if TYPE_CHECKING:
    from specify_cli.context.mission_resolver import TrackedMissionPaths

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

IdentityStateLabel = Literal["assigned", "pending", "legacy", "orphan", "residue"]

#: Every state label, in report order: the four Mission states, then ``residue``.
IDENTITY_STATES: tuple[IdentityStateLabel, ...] = ("assigned", "pending", "legacy", "orphan", "residue")

#: Why a ``kitty-specs/`` child is ``residue`` (#5875): no ``meta.json`` on disk; an untracked
#: ``meta.json`` without a ``mission_id`` (git repository); a ``meta.json`` that cannot be read (D5).
ResidueReason = Literal["no_meta", "untracked_idless_meta", "corrupt_meta"]

#: Every residue reason, in report order.
RESIDUE_REASONS: tuple[ResidueReason, ...] = ("no_meta", "untracked_idless_meta", "corrupt_meta")

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
        state: Four-state label per FR-045, or ``residue`` for a non-Mission folder (#5875).
        error: Non-empty when ``meta.json`` could not be read / parsed.
        residue_reason: Why a ``residue`` row is residue (:data:`RESIDUE_REASONS`); ``None`` otherwise.
    """

    path: Path
    slug: str
    mission_id: str | None
    mission_number: int | None
    state: IdentityStateLabel
    error: str | None = field(default=None)
    residue_reason: ResidueReason | None = field(default=None)

    def to_dict(self) -> dict[str, object]:
        """Serialise to a JSON-compatible dict."""
        return {
            "path": str(self.path),
            "slug": self.slug,
            "mission_id": self.mission_id,
            "mission_number": self.mission_number,
            "state": self.state,
            "error": self.error,
            "residue_reason": self.residue_reason,
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


def _residue_state(entry: Path) -> IdentityState:
    """The ``residue`` row for a ``kitty-specs/`` child that is not a Mission, with its reason (#5875, D5).

    ``corrupt_meta`` keeps the read error, so ``doctor identity`` can say the
    Mission content is corrupt instead of offering to delete it.
    """
    reason: ResidueReason = "no_meta"
    error: str | None = None
    if (entry / "meta.json").is_file():
        from specify_cli.core.paths import MissionMetaReadError, load_meta_fail_closed

        reason = "untracked_idless_meta"
        try:
            load_meta_fail_closed(entry)
        except (OSError, MissionMetaReadError) as exc:
            reason, error = "corrupt_meta", str(exc)
    return IdentityState(path=entry, slug=entry.name, mission_id=None, mission_number=None, state="residue", error=error, residue_reason=reason)


def classify_walk_entry(entry: Path, *, repo_root: Path, tracked: TrackedMissionPaths | None = None) -> IdentityState:
    """Classify one ``kitty-specs/`` child: ``residue`` when it is not a Mission, else :func:`classify_mission`.

    The rule is :func:`~specify_cli.context.mission_resolver.is_selectable_mission_dir`,
    called once. *tracked* is the walk's memo; ``None`` builds a fresh
    reporter memo (``probe=tracked_mission_paths``: a broken git index raises).
    The memo probes git only for a child whose answer depends on it, so the
    probe runs at most once per walk and not at all when every child carries
    a ``mission_id``.
    """
    from specify_cli.context.mission_resolver import TrackedMissionPaths, is_selectable_mission_dir, tracked_mission_paths

    memo = tracked if tracked is not None else TrackedMissionPaths(repo_root, probe=tracked_mission_paths)
    if is_selectable_mission_dir(entry, repo_root=repo_root, tracked=memo):
        return classify_mission(entry)
    return _residue_state(entry)


def _walk_classifier(repo_root: Path, *, residue_aware: bool) -> Callable[[Path], IdentityState]:
    """The per-child classifier of one walk: residue-aware (``doctor identity``) or plain :func:`classify_mission`."""
    if not residue_aware:
        return classify_mission
    from specify_cli.context.mission_resolver import TrackedMissionPaths, tracked_mission_paths

    tracked = TrackedMissionPaths(repo_root, probe=tracked_mission_paths)
    return lambda entry: classify_walk_entry(entry, repo_root=repo_root, tracked=tracked)


def _kitty_specs_children(repo_root: Path) -> list[Path]:
    """The doctor audits' one raw walk (:func:`~specify_cli.context.mission_resolver.iter_kitty_specs_children`)."""
    from specify_cli.context.mission_resolver import iter_kitty_specs_children

    return iter_kitty_specs_children(repo_root)


def audit_repo(repo_root: Path, *, residue_aware: bool = False) -> list[IdentityState]:
    """Walk ``kitty-specs/`` and classify every mission directory.

    By default every directory is classified by :func:`classify_mission`
    (one without a ``meta.json`` is ``orphan``): the audit engine consumes this
    and keeps its own, looser Mission rule (``is_mission_dir``, FR-008), so its
    findings must not change. With ``residue_aware=True`` (``doctor identity``
    only, #5875) a child that is not a Mission (no ``meta.json``, or an
    untracked id-less one in a git repository) is ``residue`` instead.
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
        residue_aware: Classify non-Missions as ``residue`` (``doctor identity``).

    Returns:
        Sorted list of :class:`IdentityState` objects, one per mission directory.
    """
    classify = _walk_classifier(repo_root, residue_aware=residue_aware)
    return [classify(entry) for entry in _kitty_specs_children(repo_root)]


# ---------------------------------------------------------------------------
# Summarise
# ---------------------------------------------------------------------------


def summarize(states: list[IdentityState]) -> dict[str, object]:
    """Aggregate a list of :class:`IdentityState` objects into a summary dict.

    Returns a dict with:
    - ``counts``: ``{state: int}`` for all five states (zero-filled)
    - ``legacy_paths``: list of ``str`` paths for legacy missions
    - ``orphan_paths``: list of ``str`` paths for orphan missions
    - ``residue_paths``: list of ``str`` paths for residue folders (#5875)

    Args:
        states: Flat list from :func:`audit_repo`.
    """
    counts: dict[str, int] = dict.fromkeys(IDENTITY_STATES, 0)
    paths: dict[str, list[str]] = {"legacy": [], "orphan": [], "residue": []}

    for s in states:
        counts[s.state] += 1
        if s.state in paths:
            paths[s.state].append(str(s.path))

    return {
        "counts": counts,
        "legacy_paths": paths["legacy"],
        "orphan_paths": paths["orphan"],
        "residue_paths": paths["residue"],
    }


# ---------------------------------------------------------------------------
# Duplicate-prefix report (FR-011)
# ---------------------------------------------------------------------------


def find_duplicate_prefixes(repo_root: Path, *, residue_aware: bool = False) -> dict[str, list[IdentityState]]:
    """Report every 3-digit numeric prefix shared by ≥ 2 mission directories.

    Walks ``kitty-specs/`` and groups directories by their leading ``NNN-``
    prefix (regex ``^(\\d{3})-``).  Only groups with size ≥ 2 are returned.

    Directories without a leading numeric prefix are silently skipped — as is,
    per `#3194`, an entry that cannot be examined at all (see the matching note
    on :func:`audit_repo`). With ``residue_aware=True`` (``doctor identity``
    only, #5875) a ``residue`` folder is skipped too: it is not a Mission, so
    it cannot collide with one. The default keeps the audit engine's findings
    unchanged (FR-008).

    Args:
        repo_root: Path to the repository root.
        residue_aware: Leave ``residue`` folders out (``doctor identity``).

    Returns:
        ``{"NNN": [<IdentityState>, ...]}`` for every duplicated prefix.
        Empty dict when no duplicates exist.
    """
    groups: dict[str, list[IdentityState]] = {}
    classify = _walk_classifier(repo_root, residue_aware=residue_aware)
    for entry in _kitty_specs_children(repo_root):
        m = _PREFIX_RE.match(entry.name)
        if not m:
            continue
        state = classify(entry)
        if state.state != "residue":
            groups.setdefault(m.group(1), []).append(state)

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

    Any handle that maps to ≥ 2 distinct missions is an ambiguity. ``residue``
    rows are skipped (#5875): Mission selection does not list them, so they
    cannot make a handle ambiguous. Only ``audit_repo(..., residue_aware=True)``
    produces them, so the audit engine's input, and its findings, are unchanged.

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
        if state.state == "residue":
            continue
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
