"""The review range of a work package: one owner of its range, provenance and owned-file pathspecs (#7578, IC-03).

:func:`resolve_wp_review_range` yields a :class:`WpReviewRange` on every topology: the commits
between the work package's **window open** and its newest ``for_review`` **submission**, the
owned-file commit list, numstat and out-of-map split, and how far the branch has moved past the
submitted tip. Both review entry points render from this one value (FR-012, wired in WP05/WP07);
this module renders nothing.

Resolution (each derived anchor must be an ancestor of the tip, or it is skipped):

* **Tip**: the newest non-migration ``for_review`` event of the work package after its window
  opener (never the live head). Its ``policy_metadata.lane_head`` stamp
  (``RECORDED_SUBMISSION``); else, where event commits are used (below), the commit that
  introduced the event (``EVENT_COMMIT``); else unavailable.
* **Base**: the recorded window open (``status.window_open_of``, ``RECORDED_WINDOW``); else the
  opener event's own ``lane_head`` (``OPENER_LANE_HEAD``, lane Missions before #7403); else, where
  event commits are used, the ``wp-base`` claim-base ref (``CLAIM_BASE_REF``) and then the commit
  that introduced the opener event (``EVENT_COMMIT``); else unavailable.
* **Event commits are used** on ``single_branch`` and for a work package no lane branch stamps
  (``status.read_lane_head`` reads it as not applicable: the planning lane of a ``lanes`` or
  ``lanes_with_coord`` Mission, C-009, operator ruling Q10). A code-lane work package never uses
  them: its status log lives on the status branch, not its lane branch.
* ``gap`` names why the recorded value was not used (the first reason seen).

Listing (a constant number of git calls, NFR-002). Pathspecs use git's default wildcard matching
(``*`` crosses ``/``, like ``fnmatch``): never ``--literal-pathspecs`` and never the ``:(glob)``
magic, so the printed review command matches the same paths. The Mission's bookkeeping prefixes
follow the resolved Mission directory name, never the caller's handle (a mid8 or ULID works):

* ``commits``: ``git log --reverse base..tip -- <owned pathspecs>``, which is exactly what the
  printed review command lists. Merge commits follow git's default walk (no ``-m``, default
  history simplification): a merge is listed when its combined diff touches the owned files, so
  the list keeps equal to the printed command; ``files`` is the tree diff ``base..tip``, which
  includes merged-in content.
* ``files`` and ``out_of_map``: one ``numstat`` tree diff ``base..tip`` without the bookkeeping
  paths, split by ``ownership.matches_owned`` (the evidence axis' matcher, so review and
  ``IMPLEMENTATION_MISSING`` agree).
* ``out_of_map_only_commits``: the non-bookkeeping commits of the range that are not in ``commits``.
* ``moved_past``: non-bookkeeping commits on the write branch after the tip
  (``status.read_lane_head``), so the work package's own status commits never count.

Bookkeeping is ``lanes.for_review_gate.status_only_excluded_prefixes`` (``.kittify/`` included).
When an owned file lies under the Mission's own directory, ``owned_pathspecs`` also excludes the
Mission's ``tasks/``, ``tasks.md`` and status files, as the two retired review pathspec builders did.

Fail-soft (FR-013, NFR-004): nothing here raises. A status surface that cannot be read is an
``UNAVAILABLE`` range with gap ``status_unreadable``; a failed listing keeps the range, leaves that
list empty and names the step in ``listing_gap``.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from kernel.git import GitCommandError, numstat_entries, run_git
from mission_runtime import (
    ClaimCommitUnresolved,
    OwnedCheckout,
    StatusRef,
    commit_introducing_status_event,
    is_single_branch,
)
from specify_cli.lanes.claim_base import read_claim_base
from specify_cli.lanes.for_review_gate import status_only_excluded_prefixes
from specify_cli.ownership.matching import matches_owned, owned_patterns
from specify_cli.status import (
    Lane,
    OpenerSelection,
    StatusEvent,
    StatusReadSurface,
    WindowOpen,
    is_migration_event,
    read_lane_head,
    read_status_events,
    resolve_status_read,
    window_open_of,
    window_opener_events,
)

# ``RangeCommit`` stays a public module-level name outside ``__all__`` until a ``src/`` caller
# imports it: the dead-symbol gate counts an ``__all__`` member only through a caller outside this module.
__all__ = ["FileChange", "RangeSource", "RangeStatus", "WpReviewRange", "resolve_wp_review_range"]

logger = logging.getLogger(__name__)

_LANE_HEAD = "lane_head"
_EVENTS_FILENAME = "status.events.jsonl"
_EXCLUDE = ":(exclude)"
_ALL_PATHS = "."


class RangeSource(StrEnum):
    """Where an end of the range came from (data-model ``WpReviewRange``)."""

    RECORDED_WINDOW = "recorded_window"
    OPENER_LANE_HEAD = "opener_lane_head"
    CLAIM_BASE_REF = "claim_base_ref"
    EVENT_COMMIT = "event_commit"
    RECORDED_SUBMISSION = "recorded_submission"
    NONE = "none"


class RangeStatus(StrEnum):
    """``RECORDED``: both ends recorded; ``DERIVED``: either end derived; ``UNAVAILABLE``: no range."""

    RECORDED = "recorded"
    DERIVED = "derived"
    UNAVAILABLE = "unavailable"


class RangeGap(StrEnum):
    """Why a recorded value was not used (closed set; the window reasons reuse ``WindowGapReason``'s values)."""

    NOT_RECORDED = "not_recorded"
    LANE_BRANCH_MISSING = "lane_branch_missing"
    CAPTURE_FAILED = "capture_failed"
    NOT_ON_LANE = "not_on_lane"
    NO_SUBMISSION = "no_submission"
    UNRESOLVABLE_SHA = "unresolvable_sha"
    STATUS_UNREADABLE = "status_unreadable"


@dataclass(frozen=True, slots=True)
class RangeCommit:
    """One implementation commit of the range (full SHA)."""

    sha: str
    subject: str


@dataclass(frozen=True, slots=True)
class FileChange:
    """Added / removed line counts of one owned path; both ``None`` for a binary file."""

    path: str
    added: int | None
    removed: int | None


@dataclass(frozen=True, slots=True)
class WpReviewRange:
    """A work package's review range with provenance (data-model ``WpReviewRange``).

    Invariant: ``status is UNAVAILABLE`` iff ``base is None or tip is None`` (and then both are ``None``). Beyond the data
    model, ``listing_gap`` names a listing step that failed (the range itself still holds).
    """

    wp_id: str
    base: str | None
    tip: str | None
    base_source: RangeSource
    tip_source: RangeSource
    gap: str | None
    status: RangeStatus
    moved_past: int = 0
    commits: tuple[RangeCommit, ...] = ()
    out_of_map_only_commits: int = 0
    files: tuple[FileChange, ...] = ()
    out_of_map: tuple[str, ...] = ()
    owned_pathspecs: tuple[str, ...] = ()
    listing_gap: str | None = None

    def __post_init__(self) -> None:
        unavailable = self.status is RangeStatus.UNAVAILABLE
        ends = (self.base, self.tip)
        if (unavailable and ends != (None, None)) or (not unavailable and None in ends):
            raise ValueError(f"an UNAVAILABLE review range has neither end, any other has both: {self.status}, base={self.base}, tip={self.tip}")

    @classmethod
    def unavailable(cls, wp_id: str, gap: str, owned_pathspecs: tuple[str, ...] = ()) -> WpReviewRange:
        """A range that could not be determined, naming why."""
        return cls(
            wp_id=wp_id,
            base=None,
            tip=None,
            base_source=RangeSource.NONE,
            tip_source=RangeSource.NONE,
            gap=gap,
            status=RangeStatus.UNAVAILABLE,
            owned_pathspecs=owned_pathspecs,
        )


# --------------------------------------------------------------------------- pathspecs


def _owned_pathspecs(owned_files: Sequence[str], mission_dir_name: str) -> tuple[str, ...]:
    """The owned globs, plus the Mission-dir bookkeeping excludes when an owned path lies under the Mission dir."""
    patterns: tuple[str, ...] = owned_patterns(owned_files)
    root = f"kitty-specs/{mission_dir_name}/"
    if not any(pattern.startswith(root) for pattern in patterns):
        return patterns
    excludes = (f"{root}tasks/**", f"{root}tasks.md", f"{root}{_EVENTS_FILENAME}", f"{root}status.json")
    return (*patterns, *(f"{_EXCLUDE}{path}" for path in excludes))


def _bookkeeping_excludes(mission_slug: str) -> tuple[str, ...]:
    """``:(exclude)`` pathspecs for the status-only prefixes (git's default, non-literal matching)."""
    return tuple(f"{_EXCLUDE}{prefix}*" for prefix in status_only_excluded_prefixes(mission_slug))


# --------------------------------------------------------------------------- resolution


@dataclass
class _Context:
    """What one resolution reads: the events, the opener selection and a memoized ancestry probe."""

    repo_root: Path
    wp_id: str
    surface: StatusReadSurface
    events: list[StatusEvent]
    selection: OpenerSelection
    #: The write branch's live head (``status.read_lane_head``), ``None`` when it has none.
    live_head: str | None
    #: Whether a lane branch stamps this work package (``False`` for the planning lane, C-009).
    lane_stamped: bool
    ancestry: dict[tuple[str, str], bool] = field(default_factory=dict)

    @property
    def uses_event_commits(self) -> bool:
        """Event commits are derived ends on ``single_branch`` and for a work package no lane branch stamps (Q10)."""
        return bool(is_single_branch(self.surface.topology)) or not self.lane_stamped

    @property
    def first_opener(self) -> StatusEvent | None:
        """The cycle's earliest opener, a skipped ``lane_branch_missing`` one included: the tip comes after it."""
        openers = (*self.selection.skipped, *self.selection.candidates)
        return openers[0] if openers else None

    @property
    def base_opener(self) -> StatusEvent | None:
        """The opener the window binds to (the first candidate), else the first skipped one."""
        openers = (*self.selection.candidates, *self.selection.skipped)
        return openers[0] if openers else None

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        """Whether *ancestor* is an ancestor of (or equal to) *descendant*; a git failure reads as False."""
        if ancestor == descendant:
            return True
        key = (ancestor, descendant)
        if key not in self.ancestry:
            try:
                result = run_git(self.repo_root, "merge-base", "--is-ancestor", ancestor, descendant, check=False)
            except GitCommandError:
                logger.debug("ancestry probe %s..%s failed", ancestor, descendant, exc_info=True)
                self.ancestry[key] = False
            else:
                self.ancestry[key] = result.returncode == 0
        return self.ancestry[key]

    def event_surface(self) -> Path | StatusRef:
        path: Path | None = self.surface.path
        if path is not None:
            return path
        relpath = f"kitty-specs/{self.surface.mission_dir_name}/{_EVENTS_FILENAME}"
        return StatusRef(repo_root=self.surface.repo_root, ref=str(self.surface.ref), events_relpath=relpath)

    def event_commit(self, event: StatusEvent, *, rev: str | None = None) -> str | None:
        """The commit that introduced *event* (bounded by *rev*), or ``None`` when it cannot be proven."""
        try:
            return commit_introducing_status_event(self.event_surface(), self.wp_id, str(event.event_id), rev=rev)
        except ClaimCommitUnresolved as exc:
            logger.debug("no event commit for %s: %s", event.event_id, exc)
            return None


def _lane_head_of(event: StatusEvent) -> str | None:
    metadata = event.policy_metadata or {}
    value = metadata.get(_LANE_HEAD)
    return value if isinstance(value, str) and value else None


def _submission(ctx: _Context) -> StatusEvent | None:
    """The newest non-migration ``for_review`` event of the work package after its window opener (P14)."""
    opener = ctx.first_opener
    if opener is None:
        return None
    start = ctx.events.index(opener)
    submissions = [event for event in ctx.events[start + 1 :] if event.wp_id == ctx.wp_id and event.to_lane == Lane.FOR_REVIEW and not is_migration_event(event)]
    return submissions[-1] if submissions else None


def _select_tip(ctx: _Context) -> tuple[str | None, RangeSource, RangeGap | None]:
    submission = _submission(ctx)
    if submission is None:
        return None, RangeSource.NONE, RangeGap.NO_SUBMISSION
    stamped = _lane_head_of(submission)
    if stamped is not None:
        return stamped, RangeSource.RECORDED_SUBMISSION, None
    if not ctx.uses_event_commits:
        return None, RangeSource.NONE, RangeGap.NOT_RECORDED
    commit = ctx.event_commit(submission)
    if commit is None:
        return None, RangeSource.NONE, RangeGap.UNRESOLVABLE_SHA
    return commit, RangeSource.EVENT_COMMIT, None


def _claim_base(ctx: _Context) -> str | None:
    """The ``wp-base`` claim-base ref, or ``None`` (also when git cannot be started: NFR-004, never a raise)."""
    try:
        sha: str | None = read_claim_base(ctx.repo_root, ctx.surface.mission_dir_name, ctx.wp_id)
    except (OSError, subprocess.SubprocessError):
        logger.debug("review range: claim-base ref of %s unreadable", ctx.wp_id, exc_info=True)
        return None
    return sha


def _derived_bases(ctx: _Context, tip: str) -> Iterator[tuple[str, RangeSource]]:
    """The derived base candidates, in order, each already ancestry-guarded against *tip*."""
    opener = ctx.base_opener
    stamped = _lane_head_of(opener) if opener is not None else None
    if stamped is not None and ctx.is_ancestor(stamped, tip):
        yield stamped, RangeSource.OPENER_LANE_HEAD
    if not ctx.uses_event_commits:
        return
    claim_base = _claim_base(ctx)
    if claim_base is not None and ctx.is_ancestor(claim_base, tip):
        yield claim_base, RangeSource.CLAIM_BASE_REF
    if opener is not None:
        # ``rev=tip`` makes the lookup's own race guard the ancestry guard (one walk, no second probe).
        commit = ctx.event_commit(opener, rev=tip)
        if commit is not None:
            yield commit, RangeSource.EVENT_COMMIT


def _select_base(ctx: _Context, tip: str) -> tuple[str | None, RangeSource, RangeGap | None]:
    outcome = window_open_of(ctx.events, ctx.wp_id, on_lane=lambda sha: ctx.is_ancestor(sha, tip), is_ancestor=ctx.is_ancestor)
    if isinstance(outcome, WindowOpen):
        return outcome.sha, RangeSource.RECORDED_WINDOW, None
    gap = RangeGap(outcome.reason.value)
    for sha, source in _derived_bases(ctx, tip):
        return sha, source, gap
    return None, RangeSource.NONE, gap


# --------------------------------------------------------------------------- listing


@dataclass
class _Listing:
    commits: tuple[RangeCommit, ...] = ()
    out_of_map_only_commits: int = 0
    files: tuple[FileChange, ...] = ()
    out_of_map: tuple[str, ...] = ()
    moved_past: int = 0
    failed: list[str] = field(default_factory=list)

    def attempt(self, step: str, action: Callable[[], None]) -> None:
        """Run one listing step; a git failure leaves its fields at their defaults and names the step."""
        try:
            action()
        except GitCommandError as exc:
            logger.debug("review range listing step %s failed: %s", step, exc)
            self.failed.append(step)


def _log(repo_root: Path, rev_range: str, fmt: str, pathspecs: Sequence[str]) -> list[str]:
    result = run_git(repo_root, "log", "--reverse", "--no-show-signature", f"--format={fmt}", rev_range, "--", *pathspecs)
    return [line for line in result.stdout.decode("utf-8", "replace").splitlines() if line]


def _list_commits(repo_root: Path, rev_range: str, scope: Sequence[str]) -> tuple[RangeCommit, ...]:
    commits = []
    for line in _log(repo_root, rev_range, "%H %s", scope):
        sha, _, subject = line.partition(" ")
        commits.append(RangeCommit(sha=sha, subject=subject))
    return tuple(commits)


def _list_stat(repo_root: Path, base: str, tip: str, excludes: Sequence[str], patterns: tuple[str, ...]) -> tuple[tuple[FileChange, ...], tuple[str, ...]]:
    """One tree diff ``base..tip`` without bookkeeping, split into owned changes and out-of-map paths."""
    owned: list[FileChange] = []
    outside: set[str] = set()
    for entry in numstat_entries(repo_root, base, tip, pathspecs=(_ALL_PATHS, *excludes), glob=True):
        path = str(entry.path)
        if not patterns or matches_owned(path, patterns):
            owned.append(FileChange(path=path, added=entry.added, removed=entry.deleted))
        else:
            outside.add(path)
    return tuple(sorted(owned, key=lambda change: change.path)), tuple(sorted(outside))


def _count(repo_root: Path, rev_range: str, excludes: Sequence[str]) -> int:
    result = run_git(repo_root, "rev-list", "--count", rev_range, "--", _ALL_PATHS, *excludes)
    return int(result.stdout.decode("ascii", "replace").strip() or "0")


@dataclass(frozen=True)
class _ListingRequest:
    repo_root: Path
    base: str
    tip: str
    owned_pathspecs: tuple[str, ...]
    patterns: tuple[str, ...]
    bookkeeping: tuple[str, ...]
    head: str | None


def _listing(request: _ListingRequest) -> _Listing:
    """Fill the commit list, stat, out-of-map split and moved-past count at a constant git cost."""
    listing = _Listing()
    rev_range = f"{request.base}..{request.tip}"
    owned_excludes = tuple(spec for spec in request.owned_pathspecs if spec.startswith(_EXCLUDE))
    scope = request.owned_pathspecs or (_ALL_PATHS, *request.bookkeeping)

    def _commits() -> None:
        listing.commits = _list_commits(request.repo_root, rev_range, scope)

    def _out_of_map_only() -> None:
        if not request.patterns:
            return
        listed = {commit.sha for commit in listing.commits}
        relevant = _log(request.repo_root, rev_range, "%H", (_ALL_PATHS, *request.bookkeeping, *owned_excludes))
        listing.out_of_map_only_commits = len([sha for sha in relevant if sha not in listed])

    def _stat() -> None:
        listing.files, outside = _list_stat(request.repo_root, request.base, request.tip, (*request.bookkeeping, *owned_excludes), request.patterns)
        listing.out_of_map = outside if request.patterns else ()

    def _moved_past() -> None:
        if request.head is not None and request.head != request.tip:
            listing.moved_past = _count(request.repo_root, f"{request.tip}..{request.head}", request.bookkeeping)

    listing.attempt("commits", _commits)
    listing.attempt("out-of-map commits", _out_of_map_only)
    listing.attempt("numstat", _stat)
    listing.attempt("moved-past", _moved_past)
    return listing


# --------------------------------------------------------------------------- entry point


def _read_context(repo_root: Path, mission_slug: str, wp_id: str, owned: OwnedCheckout | None) -> _Context | None:
    """The door's events for *wp_id* (C-006), or ``None`` when the status surface cannot be read."""
    try:
        surface = resolve_status_read(repo_root, mission_slug, owned=owned)
        events = read_status_events(surface)
    except Exception:  # fail-soft (NFR-004): the door raises several types; any of them is an unavailable range, never a raise
        logger.debug("review range: status surface of %s unreadable", mission_slug, exc_info=True)
        return None
    selection = window_opener_events(events, wp_id, cycle=True)
    reading = read_lane_head(repo_root=repo_root, mission_slug=surface.mission_dir_name, wp_id=wp_id, owned=owned)
    return _Context(
        repo_root=repo_root,
        wp_id=wp_id,
        surface=surface,
        events=events,
        selection=selection,
        live_head=reading.sha,
        lane_stamped=bool(reading.applicable),
    )


def _status_of(base_source: RangeSource, tip_source: RangeSource) -> RangeStatus:
    recorded = base_source is RangeSource.RECORDED_WINDOW and tip_source is RangeSource.RECORDED_SUBMISSION
    return RangeStatus.RECORDED if recorded else RangeStatus.DERIVED


def resolve_wp_review_range(
    repo_root: Path,
    mission_slug: str,
    wp_id: str,
    *,
    owned_files: Sequence[str],
    owned: OwnedCheckout | None = None,
) -> WpReviewRange:
    """Resolve *wp_id*'s review range with provenance, its owned-file listing and moved-past count.

    Never raises: an undeterminable range is ``UNAVAILABLE`` with a named ``gap`` (FR-013).
    """
    ctx = _read_context(repo_root, mission_slug, wp_id, owned)
    if ctx is None:
        return WpReviewRange.unavailable(wp_id, RangeGap.STATUS_UNREADABLE, _owned_pathspecs(owned_files, mission_slug))
    owned_pathspecs = _owned_pathspecs(owned_files, ctx.surface.mission_dir_name)
    tip, tip_source, tip_gap = _select_tip(ctx)
    if tip is None:
        return WpReviewRange.unavailable(wp_id, tip_gap or RangeGap.UNRESOLVABLE_SHA, owned_pathspecs)
    base, base_source, base_gap = _select_base(ctx, tip)
    if base is None:
        return WpReviewRange.unavailable(wp_id, base_gap or RangeGap.UNRESOLVABLE_SHA, owned_pathspecs)
    listing = _listing(
        _ListingRequest(
            repo_root=repo_root,
            base=base,
            tip=tip,
            owned_pathspecs=owned_pathspecs,
            patterns=owned_patterns(owned_files),
            bookkeeping=_bookkeeping_excludes(ctx.surface.mission_dir_name),
            head=ctx.live_head,
        )
    )
    return WpReviewRange(
        wp_id=wp_id,
        base=base,
        tip=tip,
        base_source=base_source,
        tip_source=tip_source,
        gap=base_gap or tip_gap,
        status=_status_of(base_source, tip_source),
        moved_past=listing.moved_past,
        commits=listing.commits,
        out_of_map_only_commits=listing.out_of_map_only_commits,
        files=listing.files,
        out_of_map=listing.out_of_map,
        owned_pathspecs=owned_pathspecs,
        listing_gap=", ".join(listing.failed) or None,
    )
