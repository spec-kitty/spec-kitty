"""The review-context block both review entry points print (#7578, FR-012, contract ``review-context-block.md``).

:func:`render_review_context` turns one :class:`~specify_cli.review.wp_range.WpReviewRange` and the
work package's cited requirements into the block's lines. It is pure and deterministic: no git, no
filesystem, no clock. Inputs in, lines out.

Shape (``?`` lines are optional; an optional line renders with the two-space item indent)::

    REVIEW RANGE (WP02): <base12>..<tip12>  [recorded | derived]
      base: <base12> (<provenance>)
    ? note: recorded window not used: <gap reason>
    ? scope: unscoped (no owned_files declared)
      tip:  <tip12> (<provenance>)
    ? note: <branch> has moved <N> commit(s) past the submitted tip
    IMPLEMENTATION COMMITS (<n>; = output of the git log command below):
      <sha12> <subject>
    ? … <k> more (see git log command)
    CHANGED FILES (owned files, +added -removed):
      +<a> -<r>  <path>
    ? … <k> more files
    ? OUTSIDE OWNED FILES (<p> path(s) in <q> commit(s) touching only those paths; review rationale required): <path>, …
    REVIEW COMMANDS:
      git log --oneline <base>..<tip> [-- <owned pathspecs>]
      git diff <base>..<tip> [-- <owned pathspecs>]
    CITED REQUIREMENTS:
      <ref> — <text>

Rules: commands carry full SHAs and ``shlex``-quoted pathspecs (they run as printed in ``bash``);
labels carry 12-character SHAs. The block without CITED REQUIREMENTS stays within
:data:`BYTE_BUDGET` bytes (NFR-001): the header, provenance and command lines are always kept, and
the commit list, the file list and the out-of-map paths are filled in that order until the budget
is reached, the rest of each replaced by one ``… <k> more`` line. No patch text is ever rendered
(C-001): only command strings, commit subjects and numstat counts.
"""

from __future__ import annotations

import shlex
from collections.abc import Callable, Sequence

from specify_cli.requirement_mapping.text import TEXT_LIMIT, TRUNCATION_MARKER, CitedRequirement, Resolution
from specify_cli.review.wp_range import FileChange, RangeSource, RangeStatus, WpReviewRange

__all__ = ["render_review_context"]

#: The block without CITED REQUIREMENTS is at most this many UTF-8 bytes, newlines included (NFR-001).
BYTE_BUDGET = 4096
#: SHA length in labels; commands carry full SHAs.
LABEL_LEN = 12

_INDENT = "  "
_ELLIPSIS = "…"
_REQUIREMENT_SEPARATOR = " — "

UNSCOPED_LINE = f"{_INDENT}scope: unscoped (no owned_files declared)"
UNAVAILABLE_COMMAND_LINE = f"{_INDENT}(no deterministic range; inspect `spec-kitty agent tasks status` and the WP's commits)"

_COMMANDS_HEADING = "REVIEW COMMANDS:"
_FILES_HEADING = "CHANGED FILES (owned files, +added -removed):"
_REQUIREMENTS_HEADING = "CITED REQUIREMENTS:"
_DEFAULT_BRANCH_LABEL = "the branch"

_BASE_LABELS: dict[RangeSource, str] = {
    RangeSource.RECORDED_WINDOW: "window open",
    RangeSource.OPENER_LANE_HEAD: "opener lane_head stamp",
    RangeSource.CLAIM_BASE_REF: "claim base ref",
    RangeSource.EVENT_COMMIT: "claim event commit",
}
_TIP_LABELS: dict[RangeSource, str] = {
    RangeSource.RECORDED_SUBMISSION: "for_review submission",
    RangeSource.EVENT_COMMIT: "for_review event commit",
}
_GAP_DESCRIPTIONS: dict[str, str] = {
    "not_recorded": "no window or submission stamp was recorded",
    "lane_branch_missing": "the lane branch was missing when the window opened",
    "capture_failed": "the window capture failed",
    "not_on_lane": "the recorded commit is not on the branch",
    "no_submission": "the work package has no for_review submission",
    "unresolvable_sha": "no commit could be resolved for an end of the range",
    "status_unreadable": "the status surface could not be read",
}
_REQUIREMENT_NOTES: dict[Resolution, str] = {
    Resolution.NOT_DECLARED: "not declared in this Mission's spec",
    Resolution.OTHER_MISSION: "cites another Mission (not resolved here)",
    Resolution.AMBIGUOUS: "declared more than once in this Mission's spec; see spec.md",
}


# --------------------------------------------------------------------------- small pieces


def _size(line: str) -> int:
    """The bytes *line* adds to the block (its UTF-8 bytes plus the newline)."""
    return len(line.encode("utf-8")) + 1


def _label(sha: str | None) -> str:
    return (sha or "")[:LABEL_LEN]


def _gap_reason(gap: str | None) -> str:
    """A reader-facing reason for *gap*, ending with the gap's own value in parentheses."""
    value = gap or "unknown"
    description = _GAP_DESCRIPTIONS.get(value)
    return f"{description} ({value})" if description else value


def _more_commits(hidden: int) -> str:
    return f"{_INDENT}{_ELLIPSIS} {hidden} more (see git log command)"


def _more_files(hidden: int) -> str:
    return f"{_INDENT}{_ELLIPSIS} {hidden} more files"


def _file_line(change: FileChange) -> str:
    added = "-" if change.added is None else str(change.added)
    removed = "-" if change.removed is None else str(change.removed)
    return f"{_INDENT}+{added} -{removed}  {change.path}"


# --------------------------------------------------------------------------- sections


def _header_lines(review_range: WpReviewRange, branch: str | None) -> list[str]:
    """The REVIEW RANGE header, provenance, optional gap / scope notes and the optional moved-past note."""
    base, tip = _label(review_range.base), _label(review_range.tip)
    lines = [
        f"REVIEW RANGE ({review_range.wp_id}): {base}..{tip}  [{review_range.status.value}]",
        f"{_INDENT}base: {base} ({_BASE_LABELS.get(review_range.base_source, review_range.base_source.value)})",
    ]
    if review_range.gap is not None:
        lines.append(f"{_INDENT}note: recorded window not used: {_gap_reason(review_range.gap)}")
    if not review_range.owned_pathspecs:
        lines.append(UNSCOPED_LINE)
    lines.append(f"{_INDENT}tip:  {tip} ({_TIP_LABELS.get(review_range.tip_source, review_range.tip_source.value)})")
    if review_range.moved_past > 0:
        lines.append(f"{_INDENT}note: {branch or _DEFAULT_BRANCH_LABEL} has moved {review_range.moved_past} commit(s) past the submitted tip")
    return lines


def _command_lines(review_range: WpReviewRange) -> list[str]:
    """``git log`` / ``git diff`` over the full-SHA range, scoped to the quoted owned pathspecs when there are any."""
    rev_range = f"{review_range.base}..{review_range.tip}"
    scope = " -- " + " ".join(shlex.quote(spec) for spec in review_range.owned_pathspecs) if review_range.owned_pathspecs else ""
    return [
        _COMMANDS_HEADING,
        f"{_INDENT}git log --oneline {rev_range}{scope}",
        f"{_INDENT}git diff {rev_range}{scope}",
    ]


def _fill_list(items: Sequence[str], more: Callable[[int], str], remaining: int) -> tuple[list[str], int]:
    """Take *items* while they fit in *remaining* bytes, then one *more* line naming how many were left out.

    Returns the lines and the bytes they use. Room for the closing *more* line is reserved before
    each item is taken, so the result never exceeds *remaining* unless even that line cannot fit.
    """
    total = sum(_size(item) for item in items)
    if total <= remaining:
        return list(items), total
    taken: list[str] = []
    used = 0
    for index, item in enumerate(items):
        if used + _size(item) + _size(more(len(items) - index - 1)) > remaining:
            break
        taken.append(item)
        used += _size(item)
    tail = more(len(items) - len(taken))
    return [*taken, tail], used + _size(tail)


def _out_of_map_prefix(review_range: WpReviewRange) -> str:
    return (
        f"{_INDENT}OUTSIDE OWNED FILES ({len(review_range.out_of_map)} path(s) in {review_range.out_of_map_only_commits} commit(s) "
        "touching only those paths; review rationale required): "
    )


def _out_of_map_floor(review_range: WpReviewRange) -> int:
    """The bytes of the shortest OUTSIDE OWNED FILES line (every path counted, none named); 0 when nothing is out of map."""
    if not review_range.out_of_map:
        return 0
    return _size(f"{_out_of_map_prefix(review_range)}{_ELLIPSIS} {len(review_range.out_of_map)} more")


def _out_of_map_line(review_range: WpReviewRange, remaining: int) -> list[str]:
    """The OUTSIDE OWNED FILES line (omitted when nothing is out of map), its path list cut to *remaining* bytes."""
    paths = sorted(review_range.out_of_map)
    if not paths:
        return []
    prefix = _out_of_map_prefix(review_range)
    shown = list(paths)
    while shown:
        hidden = len(paths) - len(shown)
        line = prefix + ", ".join(shown) + (f", {_ELLIPSIS} {hidden} more" if hidden else "")
        if _size(line) <= remaining:
            return [line]
        shown.pop()
    return [f"{prefix}{_ELLIPSIS} {len(paths)} more"]


def _capped(text: str) -> str:
    """*text* held to the contract's per-requirement cap (NFR-003): :data:`TEXT_LIMIT` characters plus the marker.

    ``resolve_requirement_texts`` already caps what it resolves; this keeps the rule for any
    ``CitedRequirement`` the renderer is handed, so the block's requirement section stays bounded.
    """
    if len(text) <= TEXT_LIMIT + len(TRUNCATION_MARKER):
        return text
    capped: str = text[:TEXT_LIMIT] + TRUNCATION_MARKER
    return capped


def _requirement_line(cited: CitedRequirement) -> str:
    if cited.resolution is Resolution.DECLARED and cited.text:
        text = cited.text if cited.text.startswith(cited.ref) else f"{cited.ref}{_REQUIREMENT_SEPARATOR}{cited.text}"
        return f"{_INDENT}{_capped(text)}"
    note = _REQUIREMENT_NOTES.get(cited.resolution, cited.resolution.value)
    return f"{_INDENT}{cited.ref}{_REQUIREMENT_SEPARATOR}{note}"


def _requirement_lines(cited: Sequence[CitedRequirement]) -> list[str]:
    """The CITED REQUIREMENTS section, one line per cited ID, never dropping one (outside the byte budget)."""
    items = [_requirement_line(item) for item in cited] or [f"{_INDENT}(none cited)"]
    return [_REQUIREMENTS_HEADING, *items]


def _unavailable_lines(review_range: WpReviewRange) -> list[str]:
    return [
        f"REVIEW RANGE ({review_range.wp_id}): unavailable{_REQUIREMENT_SEPARATOR}{_gap_reason(review_range.gap)}",
        _COMMANDS_HEADING,
        UNAVAILABLE_COMMAND_LINE,
    ]


# --------------------------------------------------------------------------- entry point


def render_review_context(
    review_range: WpReviewRange,
    cited: Sequence[CitedRequirement],
    *,
    branch: str | None = None,
) -> list[str]:
    """Render the review-context block for *review_range* and its *cited* requirements.

    *branch* names the write branch in the moved-past note (``the branch`` when unknown).
    """
    if review_range.status is RangeStatus.UNAVAILABLE:
        return [*_unavailable_lines(review_range), *_requirement_lines(cited)]
    header = _header_lines(review_range, branch)
    commands = _command_lines(review_range)
    commits_heading = f"IMPLEMENTATION COMMITS ({len(review_range.commits)}; = output of the git log command below):"
    fixed = [*header, commits_heading, _FILES_HEADING, *commands]
    remaining = BYTE_BUDGET - sum(_size(line) for line in fixed)

    # Each later section's shortest form is reserved before an earlier list fills, so all three always fit.
    outside_floor = _out_of_map_floor(review_range)
    files_floor = _size(_more_files(len(review_range.files))) if review_range.files else 0

    commit_items = [f"{_INDENT}{_label(commit.sha)} {commit.subject}" for commit in review_range.commits]
    commits, used = _fill_list(commit_items, _more_commits, remaining - files_floor - outside_floor)
    remaining -= used
    file_items = [_file_line(change) for change in sorted(review_range.files, key=lambda change: change.path)]
    files, used = _fill_list(file_items, _more_files, remaining - outside_floor)
    remaining -= used
    outside = _out_of_map_line(review_range, remaining)

    return [
        *header,
        commits_heading,
        *commits,
        _FILES_HEADING,
        *files,
        *outside,
        *commands,
        *_requirement_lines(cited),
    ]
