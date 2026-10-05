"""Test-side reference reader of the work package detail (FR-001 to FR-008, FR-016, FR-020, FR-022).

The executable form of the rules written in the ``mission-status`` contract for ``getWorkPackageDetail``: which
files make a work package (identity), where subtask titles and dependency titles come from, what a review cycle
is, where a work package runs, which of its owned files its code lane changed, and which artifacts it points to.
Nothing here is a test and nothing here writes. The module composes the public readers the projector helper
already uses (``reconstruct_wp_view``, ``read_authored_wp_frontmatter``, the snapshot) and the file system seam of
the artifact reader, and it never imports the writing ``materialize``.

Every entry point returns a ``DetailOutcome`` (a status and a body); a refusal is an outcome, never an exception.
A projection error (a strict field that holds an unrepresentable value) is a data defect and is raised, exactly as
the v1 builders do.

Two files are distinguished (spec Terminology, "two selectors"): the work package's **authored file**, which
supplies the frontmatter, the owned files and the subtask roster, and its **prompt file**, the name-keyed
definition that alone feeds ``artifactReferences.prompt`` and the ``tasks/<wp-slug>/`` review cycle directory.
"""

from __future__ import annotations

import fnmatch
import re
import stat
import subprocess
from collections.abc import Mapping, Sequence
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from kernel.errors import GuardedReadError
from kernel.git import GitCommandError, changed_paths
from specify_cli.core.git_ops import get_current_branch
from specify_cli.core.vcs.git import git_merge_base
from specify_cli.frontmatter import FrontmatterError
from specify_cli.lanes.branch_naming import lane_branch_name
from specify_cli.lanes.compute import PLANNING_LANE_ID
from specify_cli.lanes.persistence import MissingLanesError, read_lanes_json
from specify_cli.missions._read_path_resolver import MissionSelectorAmbiguous
from specify_cli.ownership.validation import is_glob_pattern
from specify_cli.review.artifacts import ReviewCycleArtifact
from specify_cli.review.cycle import ReviewCycleError, build_review_cycle_pointer, validate_review_cycle_pointer
from specify_cli.status.wp_metadata import WPMetadata, read_authored_wp_frontmatter, wp_task_files
from specify_cli.status.wp_view import reconstruct_wp_view
from specify_cli.workspace.context import resolve_workspace_for_wp
from tests.contract import _mission_status_artifacts as art
from tests.contract import _mission_status_payloads as helper
from tests.contract._mission_status_artifacts import ReaderContext

# ---------------------------------------------------------------------------
# Constants: refusal codes, patterns taken from the contract's own schemas, limits
# ---------------------------------------------------------------------------

NOT_FOUND = "not_found"
SOURCE_UNREADABLE = "source_unreadable"
OK = 200
# code -> (status, title, detail); the detail never repeats a path, a Mission directory or any content.
REFUSALS: dict[str, tuple[int, str, str]] = {
    NOT_FOUND: (404, "The work package was not found", "No work package with this identifier exists in the Mission."),
    SOURCE_UNREADABLE: (500, "A source of the work package could not be read", "A file the detail is built from could not be read."),
}
UNKNOWN = "unknown"
CHANGED = "changed"
UNCHANGED = "unchanged"
TASKS_MD = "tasks.md"
TASKS_DIR = "tasks"
MAX_TASKS_MD_BYTES = 4 * 1024 * 1024
GIT_TIMEOUT_SECONDS = 30.0  # the one bound the reader can put on a git call (changed_paths); the other two seams have none (accepted residual, D-P4)
# Everything a source read can raise that means "the source exists but cannot be read": a refusal, not an escaping exception.
_UNREADABLE = (OSError, ValueError, FrontmatterError, GuardedReadError, MissionSelectorAmbiguous)
# What the two git seams that do not go through ``run_git`` can raise (a vanished or replaced worktree directory, an embedded NUL byte),
# and what the change-set query raises (a timeout or OS error wrapped by the runner, a path git's output cannot parse): each means "not determined".
_GIT_SEAM_ERRORS = (OSError, subprocess.SubprocessError, ValueError)
_CHANGE_SET_ERRORS = (GitCommandError, ValueError)
_SCHEMAS = Path(__file__).resolve().parents[2] / "contracts" / "mission-status" / "schemas"


def _schema(name: str) -> dict[str, Any]:
    loaded = yaml.safe_load((_SCHEMAS / name).read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), name
    return loaded


_REF_SCHEMA = _schema("RelativeReference.yaml")
# The schema's own pattern and length, so the reader and the contract cannot drift (``.`` excludes a line break, ``\Z`` ends the string).
RELATIVE_REFERENCE = re.compile(rf"(?=.{{1,{_REF_SCHEMA['maxLength']}}}\Z)" + _REF_SCHEMA["pattern"])
_WP_ID = re.compile(helper.WP_ID_PATTERN)
_WORKSPACE_PROPERTIES = _schema("Workspace.yaml")["properties"]
_BRANCH = re.compile(_WORKSPACE_PROPERTIES["laneBranch"]["pattern"])
_BRANCH_MAX = int(_WORKSPACE_PROPERTIES["laneBranch"]["maxLength"])
_PLANNING_BRANCH_MAX = int(_WORKSPACE_PROPERTIES["planningBranch"]["maxLength"])
_LANE_ID = re.compile(_WORKSPACE_PROPERTIES["laneId"]["pattern"])
_LANE_ID_MAX = int(_WORKSPACE_PROPERTIES["laneId"]["maxLength"])
_REVIEW_CYCLE_PROPERTIES = _schema("ReviewCycle.yaml")["properties"]
_POINTER = re.compile(_REVIEW_CYCLE_PROPERTIES["feedbackReference"]["pattern"])
_CYCLE_NAME = re.compile(r"^review-cycle-(?P<number>[1-9][0-9]*)\.md$")
_VERDICTS = frozenset(_schema("ReviewVerdict.yaml")["enum"])

# ---------------------------------------------------------------------------
# Outcome, host capability, refusals
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HostCapability:
    """What the serving host can do: run git and have lane worktrees. Explicit, never discovered."""

    git: bool
    worktrees: bool


NO_WORKTREES = HostCapability(git=False, worktrees=False)


@dataclass(frozen=True)
class DetailOutcome:
    """What the detail operation answers: the status and the body (a detail for 200, a problem for a refusal)."""

    status: int
    body: dict[str, Any]


class SourceUnreadableError(Exception):
    """A source of the detail exists but cannot be read or decoded; the assembly turns it into the 500 refusal."""


def refusal(code: str) -> DetailOutcome:
    """The problem details outcome of ``code`` (status, title and detail are fixed by the code)."""
    status, title, detail = REFUSALS[code]
    return DetailOutcome(status, {"type": "about:blank", "title": title, "status": status, "code": code, "detail": detail})


# ---------------------------------------------------------------------------
# Work package identity: the universe and the authored file of each id
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuthoredFile:
    """The authored file of one work package: its name and its typed frontmatter."""

    name: str
    metadata: WPMetadata


def index_work_packages(ctx: ReaderContext, mission_dir: Path) -> dict[str, AuthoredFile]:
    """Work package id to its authored file: the first regular, non-symlink file of ``wp_task_files`` that holds the id, in byte order.

    A file is skipped like an unparseable one when it is a symlink, a directory or not an eligible path, when its
    frontmatter raises ``FrontmatterError`` or a pydantic ``ValidationError`` or cannot be decoded, or when it holds
    no valid id (never a 500, never an escaping exception). A file that cannot be read at all raises
    ``SourceUnreadableError``.
    """
    index: dict[str, AuthoredFile] = {}
    for path in sorted(wp_task_files(mission_dir / TASKS_DIR), key=lambda item: item.name.encode("utf-8")):
        try:
            eligible = art.is_eligible(ctx, mission_dir, f"{TASKS_DIR}/{path.name}")
        except OSError as error:
            raise SourceUnreadableError(path.name) from error
        if not eligible:
            continue
        try:
            metadata, _body = read_authored_wp_frontmatter(path)
        except (FrontmatterError, ValidationError, UnicodeDecodeError):
            continue
        except OSError as error:
            raise SourceUnreadableError(path.name) from error
        if helper.is_wp_id(metadata.work_package_id):
            index.setdefault(metadata.work_package_id, AuthoredFile(path.name, metadata))
    return index


def work_package_universe(ctx: ReaderContext, mission_dir: Path) -> list[str]:
    """The distinct valid work package ids of a Mission directory, in id order."""
    return sorted(index_work_packages(ctx, mission_dir))


# ---------------------------------------------------------------------------
# Subtask titles: the two row formats of tasks.md
# ---------------------------------------------------------------------------

_WP_TOKEN = re.compile(r"\bWP\d{2,}\b")
_HEADING = re.compile(r"^#{2,4}[^#]")
_CHECKBOX_ROW = re.compile(r"^-\s*\[[ xX]\]\s*(T\d{3,})\b(.*)$")
_TABLE_ID = re.compile(r"^T\d{3,}$")
_PARALLEL_TAG = "[P]"
_BOLD = "**"
_FENCES = ("```", "~~~")


def clean_title(raw: str) -> str | None:
    """A leading ``[P]`` tag is dropped, one pair of ``**`` markers is stripped, the result is trimmed; empty is ``None``."""
    text = raw.strip()
    if text.startswith(_PARALLEL_TAG):
        text = text[len(_PARALLEL_TAG) :].lstrip()
    if len(text) >= 2 * len(_BOLD) and text.startswith(_BOLD) and text.endswith(_BOLD):
        text = text[len(_BOLD) : -len(_BOLD)]
    return text.strip() or None


def _table_row(stripped: str) -> tuple[str, str, list[str]] | None:
    """``(id, title cell, the cells after the title)`` of a table row whose first cell is a subtask id, else ``None``."""
    if not stripped.startswith("|"):
        return None
    cells = [cell.strip() for cell in stripped.strip("|").split("|")]
    if len(cells) < 2 or not _TABLE_ID.fullmatch(cells[0]):
        return None
    return cells[0], cells[1], cells[2:]


class _SectionWalk:
    """The section rule of ``tasks.md``: a heading belongs to the work package of its first ``WP`` token.

    A section opens at the work package's heading and closes for good at the next heading of another work package
    (a re-appearing heading does not reopen it); lines inside a fenced block are never rows.
    """

    def __init__(self, wp_id: str) -> None:
        self.wp_id = wp_id
        self.open = False
        self.done = False
        self.fenced = False

    def feed(self, line: str) -> bool:
        """Advance over one line; True when the line is a row candidate (not a fence line, not inside a fence, not a heading)."""
        stripped = line.strip()
        if stripped.startswith(_FENCES):
            self.fenced = not self.fenced
            return False
        if self.fenced:
            return False
        if _HEADING.match(line):
            tokens = _WP_TOKEN.findall(line)
            if tokens and tokens[0] == self.wp_id and not self.done:
                self.open = True
            elif self.open and tokens:
                self.open, self.done = False, True
            return False
        return True


def title_rows(text: str, wp_id: str) -> dict[str, str | None]:
    """Subtask id to its cleaned title for the rows of ``wp_id`` in ``tasks.md``; the first row of an id wins.

    A checkbox row belongs to the work package whose section it lies in. A table row belongs to the work package
    its cells name (a ``WP`` token after the title cell), and, when its cells name none, to the section it lies in.
    """
    walk = _SectionWalk(wp_id)
    rows: dict[str, str | None] = {}
    for line in text.split("\n"):
        if not walk.feed(line):
            continue
        stripped = line.strip()
        checkbox = _CHECKBOX_ROW.match(stripped)
        if checkbox is not None:
            if walk.open:
                rows.setdefault(checkbox.group(1), clean_title(checkbox.group(2)))
            continue
        table = _table_row(stripped)
        if table is None:
            continue
        subtask_id, title, rest = table
        named = _WP_TOKEN.findall(" ".join(rest))
        if (wp_id in named) if named else walk.open:
            rows.setdefault(subtask_id, clean_title(title))
    return rows


def read_tasks_md(ctx: ReaderContext, mission_dir: Path) -> str | None:
    """The text of the Mission's ``tasks.md`` (``None`` when there is none); a file that cannot be read or decoded raises ``SourceUnreadableError``."""
    try:
        if not art.is_eligible(ctx, mission_dir, TASKS_MD):
            return None
        with closing(ctx.fs.open_binary(mission_dir / TASKS_MD)) as handle:
            data = handle.read(MAX_TASKS_MD_BYTES + 1)
    except OSError as error:
        raise SourceUnreadableError(TASKS_MD) from error
    if len(data) > MAX_TASKS_MD_BYTES:
        raise SourceUnreadableError(TASKS_MD)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise SourceUnreadableError(TASKS_MD) from error


def human_text(tools: helper.ContractTools, projector: helper.Projector, value: str, where: str) -> str | None:
    """A human text field: withheld (``None``) when it holds a credential, otherwise with host paths and e-mail addresses replaced."""
    if art.has_credential(tools, value):
        return None
    try:
        return projector.human(value, where)
    except helper.ProjectionError:
        return None  # a leak the substitution cannot remove is withheld like a credential, never forwarded


def subtask_entries(
    tools: helper.ContractTools,
    projector: helper.Projector,
    roster: Sequence[str],
    titles: Mapping[str, str | None],
    states: Mapping[str, str],
    wp_id: str,
) -> list[dict[str, Any]]:
    """``{id, title, statusLane}`` for each roster id in authored order; a lane is ``None`` when no state is recorded (never ``planned``)."""
    entries = []
    for subtask_id in roster:
        raw = titles.get(subtask_id)
        entries.append(
            {
                "id": str(projector.strict(subtask_id, f"{wp_id}.subtasks", nullable=False, pattern=RELATIVE_REFERENCE)),
                "title": None if raw is None else human_text(tools, projector, raw, f"{wp_id}.subtasks.title"),
                "statusLane": projector.lane(states.get(subtask_id), f"{wp_id}.subtasks.statusLane"),
            }
        )
    return entries


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def dependency_entries(
    tools: helper.ContractTools,
    projector: helper.Projector,
    dependencies: Sequence[str],
    index: Mapping[str, AuthoredFile],
    lanes: Mapping[str, str],
    wp_id: str,
) -> list[dict[str, Any]]:
    """``{wpId, title, statusLane}`` for each dependency in authored order.

    The title is the stripped display title when non-empty, else the id; the id also stands in for a title that holds
    a credential. A dependency that names no work package of the Mission keeps its id as title and has no lane.
    """
    entries = []
    for authored_id in projector.strict_list(list(dependencies), f"{wp_id}.dependencies", _WP_ID):
        known = index.get(authored_id)
        title = authored_id
        if known is not None:
            shown = known.metadata.display_title.strip()
            title = (human_text(tools, projector, shown, f"{wp_id}.dependencies.title") or authored_id) if shown else authored_id
        entries.append({"wpId": authored_id, "title": title, "statusLane": projector.lane(lanes.get(authored_id), f"{wp_id}.dependencies.statusLane")})
    return entries


# ---------------------------------------------------------------------------
# Review cycles (FR-005): files of the primary planning surface, verdicts from the status events
# ---------------------------------------------------------------------------


def cycle_pointer(mission_slug: str, wp_slug: str, name: str) -> str | None:
    """The canonical ``review-cycle://`` pointer of a cycle file, or ``None`` when the product builder or validator refuses a segment.

    The result is also held to the contract's own pattern, so no value that the schema would refuse is ever shown.
    """
    try:
        pointer = build_review_cycle_pointer(mission_slug, wp_slug, name)
        validate_review_cycle_pointer(pointer)
    except ReviewCycleError:
        return None
    return pointer if _POINTER.fullmatch(pointer) else None


def cycle_verdict(rows: Sequence[Mapping[str, Any]], wp_id: str, pointer: str | None) -> str | None:
    """The verdict of the last status event of ``wp_id`` whose trimmed review reference equals ``pointer``; ``None`` when none does.

    Never read from the cycle file. A reference that is no pointer, or names another cycle or another Mission segment, matches nothing.
    """
    if pointer is None:
        return None
    verdict: str | None = None
    for row in rows:
        result = row.get("review_result")
        if row.get("wp_id") != wp_id or "to_lane" not in row or not isinstance(result, Mapping):
            continue
        reference = result.get("reference")
        if isinstance(reference, str) and reference.strip() == pointer:
            value = result.get("verdict")
            verdict = value if value in _VERDICTS else None
    return verdict


def _cycle_names(ctx: ReaderContext, mission_dir: Path, wp_slug: str) -> list[str]:
    """The cycle file names of ``tasks/<wp-slug>/``; a symlinked ``tasks/`` or work package directory is never entered."""
    for relative in (TASKS_DIR, f"{TASKS_DIR}/{wp_slug}"):
        try:
            mode = ctx.fs.lstat(mission_dir / relative).st_mode
        except (FileNotFoundError, NotADirectoryError):
            return []
        if not stat.S_ISDIR(mode):
            return []
    return [name for name in ctx.fs.scandir(mission_dir / TASKS_DIR / wp_slug) if _CYCLE_NAME.fullmatch(name)]


def _cycle_number(name: str) -> int:
    match = _CYCLE_NAME.fullmatch(name)
    if match is None:
        raise ValueError(name)  # unreachable: only names that match the pattern are listed
    return int(match.group("number"))


def _parsed_cycle(path: Path) -> ReviewCycleArtifact | None:
    try:
        return ReviewCycleArtifact.from_file(path)
    except (ValueError, OSError):
        return None  # an unparseable file is still an entry, with null members (AD-13)


def _rfc3339_or_none(tools: helper.ContractTools, value: str | None) -> str | None:
    return value if isinstance(value, str) and tools.formats.is_rfc3339_date_time(value) else None


def review_cycles(ctx: ReaderContext, opened: OpenedMission, wp_id: str, projector: helper.Projector) -> list[dict[str, Any]]:
    """One entry per ``tasks/<wp-slug>/review-cycle-<N>.md`` of the primary directory, ascending by ``N``.

    ``<wp-slug>`` is the stem of the work package's prompt file; with no prompt file there is no cycle directory and
    the list is empty. A cycle held only on a coordination surface is not shown (AD-18); a stranded record in the
    primary directory is. The file is parsed only when it is an eligible file (a symlink is never followed).
    """
    mission_dir = opened.mission_dir
    prompt = art.prompt_file_name(ctx, mission_dir, wp_id)
    if prompt is None:
        return []
    wp_slug = prompt.removesuffix(".md")
    entries = []
    for name in sorted(_cycle_names(ctx, mission_dir, wp_slug), key=_cycle_number):
        relative = f"{TASKS_DIR}/{wp_slug}/{name}"
        eligible = art.is_eligible(ctx, mission_dir, relative)
        parsed = _parsed_cycle(mission_dir / relative) if eligible else None
        pointer = cycle_pointer(mission_dir.name, wp_slug, name)
        entries.append(
            {
                "cycleNumber": _cycle_number(name),
                "reviewedAt": _rfc3339_or_none(ctx.tools, None if parsed is None else parsed.reviewed_at),
                "reviewer": projector.handle(None if parsed is None else parsed.reviewer_agent),
                "verdict": cycle_verdict(opened.source.rows, wp_id, pointer),
                "feedbackReference": pointer,
                "artifactPath": relative if eligible else None,
            }
        )
    return entries


# ---------------------------------------------------------------------------
# Workspace (FR-006)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WorkspaceView:
    """The ``workspace`` member, with what the change states need and the contract does not show: the worktree and the target branch."""

    workspace: dict[str, Any]
    worktree: Path | None
    target_branch: str | None


def _fits(value: str, pattern: re.Pattern[str], maximum: int) -> str | None:
    return value if len(value) <= maximum and pattern.fullmatch(value) else None


def _lane_worktree(ctx: ReaderContext, slug: str, wp_id: str, host: HostCapability) -> Path | None:
    """The lane worktree directory when the host has worktrees and it runs in its own existing lane worktree, else ``None``.

    ``MissingLanesError`` and the ``ValueError`` of a work package in no lane mean no worktree; a corrupt manifest or an
    ambiguous handle are not caught here and fail the read.
    """
    if not host.worktrees:
        return None
    try:
        resolved = resolve_workspace_for_wp(ctx.repo_root, slug, wp_id)
    except (MissingLanesError, ValueError):
        return None
    return None if resolved.runs_in_checkout_root or not resolved.exists else Path(resolved.worktree_path)


def workspace_of(ctx: ReaderContext, opened: OpenedMission, wp_id: str, host: HostCapability, projector: helper.Projector) -> WorkspaceView:
    """Where the work package runs: code lane, lane branch, planning branch, and whether its own lane worktree exists on the host."""
    authored = opened.index[wp_id]
    manifest = read_lanes_json(opened.mission_dir)  # CorruptLanesError is a GuardedReadError: the read fails, never a silent fallback
    planning = projector.strict(authored.metadata.planning_base_branch, f"{wp_id}.workspace.planningBranch", nullable=True)
    planning = None if planning is not None and len(planning) > _PLANNING_BRANCH_MAX else planning
    lane = None if manifest is None else manifest.lane_for_wp(wp_id)
    if manifest is None or lane is None:
        return WorkspaceView({"laneId": None, "laneBranch": None, "planningBranch": planning, "worktreePresent": False}, None, None)
    slug = str(opened.source.identity.mission_slug)
    lane_id = _fits(lane.lane_id, _LANE_ID, _LANE_ID_MAX)
    branch = None
    if lane_id is not None and lane_id != PLANNING_LANE_ID:
        branch = _fits(lane_branch_name(slug, lane_id, target_branch=manifest.target_branch), _BRANCH, _BRANCH_MAX)
    worktree = _lane_worktree(ctx, slug, wp_id, host) if lane_id is not None else None
    workspace = {"laneId": lane_id, "laneBranch": branch, "planningBranch": planning, "worktreePresent": worktree is not None}
    return WorkspaceView(workspace, worktree, manifest.target_branch)


# ---------------------------------------------------------------------------
# Owned files and the change state (FR-007, AD-20)
# ---------------------------------------------------------------------------


def matches_owned_file(path: str, pattern: str) -> bool:
    """The repository's owned-files matching, reproduced once (D-P3): ``fnmatch`` or the directory-prefix rule.

    The path is normalised as ``_mt_matches_owned_file`` does (backslash to ``/``, one leading ``./`` removed); the
    pattern is used as authored. ``fnmatch.fnmatch`` (not ``fnmatchcase``) is what both repository copies call, so
    the parity with them is exact on every platform. A parity test runs both copies over the same cases.
    """
    normalized = path.replace("\\", "/").removeprefix("./")
    if fnmatch.fnmatch(normalized, pattern):
        return True
    prefix = pattern.replace("/**", "").replace("/*", "").rstrip("/")
    return bool(prefix) and normalized.startswith(prefix + "/")


def _matchable(pattern: str) -> bool:
    """False for a pattern holding ``{``: ``is_glob_pattern`` calls it a glob, but the repository's matcher has no brace expansion."""
    return "{" not in pattern


def _usable_target(target_branch: str | None) -> bool:
    """A manifest target branch is a bare string: it must pass the lane branch pattern and not look like an option before it reaches git."""
    return isinstance(target_branch, str) and _fits(target_branch, _BRANCH, _BRANCH_MAX) is not None and not target_branch.startswith("-")


def committed_change_set(worktree: Path, lane_branch: str, target_branch: str) -> tuple[str, ...] | None:
    """The paths the commits of the lane branch changed since its merge base with the target branch, or ``None`` when not determined.

    Only committed changes count (a staged, unstaged or untracked path never appears); a deletion is listed and a rename
    lists both names (``renames=False``). A HEAD that is not on the lane branch, a merge base that is not found, and any
    failure of a git call (``OSError``, ``SubprocessError``, ``ValueError``, ``GitCommandError``) is not determined.

    Accepted residual (plan D-P4): ``get_current_branch`` and ``git_merge_base`` take no timeout and cannot be
    given one without a change under ``src/``, so a wedged git process would hang the read inside them; only the change-set
    query is bounded (``GIT_TIMEOUT_SECONDS``).
    """
    try:
        if get_current_branch(worktree) != lane_branch:
            return None
        merge_base = git_merge_base(worktree, "HEAD", target_branch)
    except _GIT_SEAM_ERRORS:
        return None
    if merge_base is None:
        return None
    try:
        paths = changed_paths(worktree, merge_base, "HEAD", renames=False, timeout=GIT_TIMEOUT_SECONDS)
    except _CHANGE_SET_ERRORS:
        return None
    return tuple(path.as_posix() for path in paths)


def _determined_change_set(host: HostCapability, view: WorkspaceView) -> tuple[str, ...] | None:
    """The committed change set when every precondition of a determined state holds, else ``None`` (every entry is then ``unknown``)."""
    workspace = view.workspace
    lane_branch = workspace["laneBranch"]
    code_lane = workspace["laneId"] not in (None, PLANNING_LANE_ID)
    if not (host.git and host.worktrees and code_lane and workspace["worktreePresent"] and view.worktree is not None and lane_branch is not None):
        return None
    if not _usable_target(view.target_branch) or view.target_branch is None:
        return None
    return committed_change_set(view.worktree, lane_branch, view.target_branch)


def change_states(host: HostCapability, view: WorkspaceView, patterns: Sequence[str]) -> list[str]:
    """``changed``, ``unchanged`` or ``unknown`` for each owned-file pattern, derived once per work package.

    Never ``unchanged`` when the change set is not determined, and a pattern holding ``{`` is not matchable (the
    repository's matcher has no brace expansion, so guessing would risk a silent wrong ``unchanged``).
    """
    changed = _determined_change_set(host, view)
    states = []
    for pattern in patterns:
        if changed is None or not _matchable(pattern):
            states.append(UNKNOWN)
        else:
            states.append(CHANGED if any(matches_owned_file(path, pattern) for path in changed) else UNCHANGED)
    return states


def invariant_problems(detail: Mapping[str, Any]) -> list[str]:
    """The invariants asserted on every detail built: a determined change state needs a present worktree, and a planning lane has none."""
    workspace = detail["workspace"]
    problems = []
    if not workspace["worktreePresent"] and any(entry["changeState"] != UNKNOWN for entry in detail["ownedFiles"]):
        problems.append("an owned file is changed or unchanged although no worktree is present")
    if workspace["laneId"] == PLANNING_LANE_ID and workspace["worktreePresent"]:
        problems.append("a planning-lane work package reports a present worktree")
    if workspace["laneId"] is None and workspace["worktreePresent"]:
        problems.append("a work package in no lane reports a present worktree")
    return problems


# ---------------------------------------------------------------------------
# Reading one Mission and assembling one detail
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OpenedMission:
    """What reading one Mission once yields: its primary directory, the status source and the work package index."""

    mission_dir: Path
    source: helper.MissionSource
    index: dict[str, AuthoredFile]


def _mission_directory(ctx: ReaderContext, mission_id: str) -> Path | None:
    """The Mission's primary directory, ``None`` for an unknown Mission; a directory that cannot be statted raises ``SourceUnreadableError``."""
    mission_dir = art.resolve_mission(ctx, mission_id)
    if mission_dir is None:
        return None
    try:
        mode = ctx.fs.lstat(mission_dir).st_mode
    except (FileNotFoundError, NotADirectoryError):
        return None
    except OSError as error:
        raise SourceUnreadableError(mission_id) from error
    return mission_dir if stat.S_ISDIR(mode) else None


def open_mission(ctx: ReaderContext, mission_id: str) -> OpenedMission | DetailOutcome:
    """Read the Mission once (meta, snapshot, event rows, work package index), or the refusal: 404 for an unknown Mission, 500 for a source that cannot be read."""
    try:
        mission_dir = _mission_directory(ctx, mission_id)
        if mission_dir is None:
            return refusal(NOT_FOUND)
        source = helper.load_source(ctx.repo_root, mission_dir.name)
        index = index_work_packages(ctx, mission_dir)
    except (SourceUnreadableError, *_UNREADABLE):
        return refusal(SOURCE_UNREADABLE)
    return OpenedMission(mission_dir, source, index)


def _assemble(ctx: ReaderContext, opened: OpenedMission, wp_id: str, host: HostCapability) -> dict[str, Any]:
    source, authored = opened.source, opened.index[wp_id]
    tools = ctx.tools
    projector = helper.Projector(tools.leak, opened.mission_dir.name)
    view = reconstruct_wp_view(source.read_dir, wp_id, metadata=authored.metadata)
    lanes = {other: str(state.get("lane")) for other, state in source.snapshot.work_packages.items()}
    titles = title_rows(read_tasks_md(ctx, opened.mission_dir) or "", wp_id)
    owned = projector.strict_list(list(view.authored.owned_files), f"{wp_id}.ownedFiles", RELATIVE_REFERENCE)
    workspace = workspace_of(ctx, opened, wp_id, host, projector)
    return {
        "missionId": str(source.identity.mission_id),
        "wpId": wp_id,
        "subtasks": subtask_entries(tools, projector, view.authored.subtasks, titles, view.resolved.subtasks, wp_id),
        "dependencies": dependency_entries(tools, projector, view.authored.dependencies, opened.index, lanes, wp_id),
        "reviewCycles": review_cycles(ctx, opened, wp_id, projector),
        "workspace": workspace.workspace,
        "ownedFiles": [
            {"pattern": pattern, "isGlob": is_glob_pattern(pattern), "changeState": state}
            for pattern, state in zip(owned, change_states(host, workspace, owned), strict=True)
        ],
        "artifactReferences": art.artifact_references(ctx, opened.mission_dir, wp_id),
    }


def build_work_package_detail(
    ctx: ReaderContext,
    mission_id: str,
    wp_id: str,
    host: HostCapability,
    *,
    opened: OpenedMission | None = None,
) -> DetailOutcome:
    """``getWorkPackageDetail``: 404 for an unknown Mission or work package, 500 for a source that cannot be read, else 200.

    ``opened`` is a Mission already read by ``open_mission`` (a caller that builds many details passes it).
    """
    if not helper.is_wp_id(wp_id):
        return refusal(NOT_FOUND)
    if opened is None:
        result = open_mission(ctx, mission_id)
        if isinstance(result, DetailOutcome):
            return result
        opened = result
    if wp_id not in opened.index:
        return refusal(NOT_FOUND)
    try:
        return DetailOutcome(OK, _assemble(ctx, opened, wp_id, host))
    except (SourceUnreadableError, *_UNREADABLE):
        return refusal(SOURCE_UNREADABLE)
