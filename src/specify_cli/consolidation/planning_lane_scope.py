"""Why a default Mission's planning lane credits nothing, and the owned-pattern breadth rule (#7860).

Before a default Mission lands, the reconciliation claim credits its planning lane's work on the
Mission branch only inside each approved work package's window and owned paths
(``reconciliation_authorship._planning_scope``). The lane credits nothing, fail closed, when any
of its work packages is not approved (operator ruling R1), when an ``owned_files`` list cannot be
read, when a pattern is too broad (:func:`is_whole_tree_pattern`), when a window start cannot be
proven, when a window cannot be read, or when every ``owned_files`` list is empty. The gate then
reports the lane's content as un-attributable, which on its own names neither the planning lane
nor the work package behind it.

:func:`planning_lane_notes` names them. It runs the claim's own scope decision first and explains
only a lane that decision left empty, so a note never disagrees with the verdict; the verifier
prints it with an un-attributable FAIL (``reconciliation_verifier._with_attribution_hint``). It
changes no verdict.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from specify_cli.consolidation.reconciliation_kernel import _is_approved_wp
from specify_cli.lanes.compute import is_planning_lane
from specify_cli.lanes.models import ExecutionLane, LanesManifest

_GLOB_CHARS = frozenset("*?[")
# A usable owned glob is led by at least this many literal path segments (#7860 review 3).
_MIN_LITERAL_SEGMENTS = 2
_PARENT_SEGMENT = ".."


def _normalized_pattern(pattern: str) -> str:
    """*pattern* as the ownership reader normalises it: ``\\`` to ``/`` and one leading ``./`` dropped."""
    return pattern.replace("\\", "/").removeprefix("./")


def _literal_prefix(pattern: str) -> tuple[str, ...] | None:
    """The literal leading path segments of *pattern* (those before the first ``*``, ``?`` or ``[``).

    A trailing ``/`` is stripped first. ``None`` for a pattern no prefix can bound: one with an empty
    segment (an empty pattern, ``a//b``, or an absolute path, whose first segment is empty) or any
    ``..`` segment.
    """
    segments = _normalized_pattern(pattern).rstrip("/").split("/")
    if any(segment in ("", _PARENT_SEGMENT) for segment in segments):
        return None
    literal: list[str] = []
    for segment in segments:
        if any(char in _GLOB_CHARS for char in segment):
            break
        literal.append(segment)
    return tuple(literal)


def _names_a_top_level_file(pattern: str, literal: tuple[str, ...]) -> bool:
    """True for one wildcard-free segment with an extension (``README.md``, ``pyproject.toml``) and no trailing ``/``.

    Kept simple on purpose (fail closed): a name with no ``.`` after its first character
    (``src``, ``.github``, ``.gitignore``) reads as a directory and is refused.
    """
    normalized = _normalized_pattern(pattern)
    return len(literal) == 1 and normalized == literal[0] and "." in literal[0][1:]


def is_whole_tree_pattern(pattern: str) -> bool:
    """True when an owned glob is too broad to scope the Mission-branch window (#7860 reviews 2 and 3).

    Judged on structure, not spelling: a usable pattern is led by at least two literal path segments
    (segments before the first one holding ``*``, ``?`` or ``[``, after dropping a leading ``./`` and
    a trailing ``/``), or names one top-level file (:func:`_names_a_top_level_file`). Everything
    else is refused: a wildcard in the first segment (``fnmatch``'s ``*`` crosses ``/``), the
    inference fallback ``src/**`` and every pattern as broad as it (``src``, ``src/``, ``src/*``,
    ``src/**/*``, ``src/*/**``, ``src/**/*.py``), and also ``docs/*.md`` or ``docs/**``; an absolute
    path, an empty segment and a ``..`` segment are refused outright. The matcher's prefix rule
    (:func:`matches_owned`) can reach a sibling of the last literal segment (``src/a/*b/**`` also owns
    ``src/ab/...``); with two literal segments that sibling is still under the first one, so the
    breadth stays bounded.
    """
    literal = _literal_prefix(pattern)
    if literal is None:
        return True
    return len(literal) < _MIN_LITERAL_SEGMENTS and not _names_a_top_level_file(pattern, literal)


_NO_STATUS_ROW = "no status row"
_RERUN = "then run `spec-kitty consolidate` again"

#: Ruling R1's remedy, each step driven end to end through the CLI (#7860 review 5).
_NOT_APPROVED_REMEDY = (
    "Every work package of the planning lane must be approved or done before its planning work counts; no attestation lifts this. "
    "An in-flight work package: finish its review and approval. "
    "A canceled work package that owes no work: if it was never claimed, first record its claim with "
    "`spec-kitty agent tasks move-task <WP> --to claimed --force` (that status commit on the Mission branch starts its window); then run "
    "`spec-kitty agent tasks move-task <WP> --to approved --force` and "
    '`spec-kitty consolidate --attest-no-implementation <WP> --attest-reason "<why>"`. '
    "A canceled work package that owes work: move it with `spec-kitty agent tasks move-task <WP> --to claimed --force`, "
    "claim it through `spec-kitty agent action implement <WP>`, commit its change, move it to for_review and have it reviewed and approved"
)


def _lane_state(wp: str, work_packages: Mapping[str, Mapping[str, object]]) -> str:
    row = work_packages.get(wp)
    return str(row.get("lane", "")) if row else _NO_STATUS_ROW


def _named(wp_ids: Sequence[str]) -> str:
    return ", ".join(wp_ids)


def _why_unscoped(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    lane: ExecutionLane,
    work_packages: Mapping[str, Mapping[str, object]],
    events: Callable[[], Sequence[Any] | None] | None,
) -> str:
    """The first reason, in the claim's own order, why *lane* credits nothing, with its remedy."""
    from specify_cli.consolidation import reconciliation_authorship as authorship
    from specify_cli.consolidation.wp_evidence import EVIDENCE_WINDOW_UNCOMPUTABLE, PLANNING_WINDOW_RECOVERY

    not_approved = [wp for wp in lane.wp_ids if not _is_approved_wp(wp, work_packages)]
    if not_approved:
        states = ", ".join(f"{wp} is {_lane_state(wp, work_packages)}" for wp in not_approved)
        return f"{states}. {_NOT_APPROVED_REMEDY}"
    owned = authorship._planning_ownership(repo_root, lanes_manifest.mission_slug, lane.wp_ids)
    unreadable = [wp for wp in lane.wp_ids if wp not in owned]
    if unreadable:
        return f"the owned_files of {_named(unreadable)} cannot be read. Restore each task file with its owned_files list, {_RERUN}"
    broad = [f"{wp} '{pattern}'" for wp in lane.wp_ids for pattern in owned[wp] if is_whole_tree_pattern(pattern)]
    if broad:
        return (
            f"an owned_files pattern is too broad ({', '.join(broad)}): a usable pattern is led by at least two literal path "
            f"segments or names one top-level file. Narrow it in the task file, {_RERUN}"
        )
    unproven = [wp for wp in lane.wp_ids if authorship._planning_window_starts(repo_root, lanes_manifest, lane, (wp,), events) is None]
    if unproven:
        return (
            f"the commit that introduced the claim of {_named(unproven)} on the Mission branch cannot be proven. "
            f"Recovery: {PLANNING_WINDOW_RECOVERY[EVIDENCE_WINDOW_UNCOMPUTABLE]}"
        )
    if not any(owned.values()):
        return f"every planning work package's owned_files list is empty. List the paths each one changes in its owned_files, {_RERUN}"
    return f"the commits of a work package's window on the Mission branch cannot be read. Make the Mission branch readable, {_RERUN}"


def planning_lane_notes(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    work_packages: Mapping[str, Mapping[str, object]],
    coord_base_ref: str,
    sb_window: tuple[str, str] | None,
    events: Callable[[], Sequence[Any] | None] | None,
) -> tuple[str, ...]:
    """One line per planning lane of a default, not-landed Mission that credits nothing, naming the reason, the work packages and the remedy.

    Empty for every other shape (a ``single_branch`` window, a landed or legacy Mission, no planning
    pin) and for a lane the claim's own scope decision credits. Looked up through the authorship
    module so a patch of its names reaches this read too.
    """
    from specify_cli.consolidation import reconciliation_authorship as authorship

    if sb_window is not None:
        return ()
    notes: list[str] = []
    for lane in lanes_manifest.lanes:
        if not is_planning_lane(lane) or not lane.wp_ids:
            continue
        if authorship._planning_lane_mission_branch_window(repo_root, lanes_manifest, coord_base_ref) is None:
            continue
        scope = authorship._planning_scope(repo_root, lanes_manifest, lane, work_packages, coord_base_ref, events)
        if scope is not None and scope.patterns:
            continue
        reason = _why_unscoped(repo_root, lanes_manifest, lane, work_packages, events)
        notes.append(f"The planning lane {lane.lane_id} credits none of its work on the Mission branch to any work package (#7860): {reason}.")
    return tuple(notes)


__all__ = ["is_whole_tree_pattern", "planning_lane_notes"]
