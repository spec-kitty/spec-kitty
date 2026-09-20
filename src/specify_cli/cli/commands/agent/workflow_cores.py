"""Pure(ish) cores for the ``agent/workflow.py`` decomposition (WP02, T007).

coord-authority-trio-degod-01KX7094: ``workflow.py`` grew into a
2997-LOC god-module with three functions (``implement`` CC78, ``review``
CC72, ``_resolve_review_context`` CC37) far past the Sonar S3776 gate of
15. This module holds the pieces of that module's logic that take
already-resolved inputs and return a value/render text without opening a
new git worktree, running a subprocess, or deciding mission placement —
request-dataclasses, review-feedback resolution, decision/classification
helpers, and the shared prompt renderers.

A few of the functions below (``_resolve_review_feedback_context`` and its
helpers) do read the canonical status-event log — a lightweight,
already-scoped filesystem read, not a git/subprocess/worktree operation.
They are grouped here because they are the WP's literal T007 extraction
list ("review-feedback resolution") and because none of their internal
calls touch a name any test monkeypatches at the ``workflow`` module level
(verified against the full test suite before this split) — moving them
here is behaviour-preserving by construction, not just by convention.

``implement``/``review``/``_resolve_review_context`` themselves stay
defined in ``workflow.py`` (the Typer-shell / orchestrator layer) and
import these helpers; see ``workflow_executor.py`` for the I/O-heavy
phase extractions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from specify_cli.review.cycle import is_non_resolvable_review_ref as _is_non_resolvable_review_ref
from specify_cli.status import AgentAssignment, Lane

if TYPE_CHECKING:
    from specify_cli.status import StatusEvent
    from specify_cli.workspace.context import ResolvedWorkspace

# ---------------------------------------------------------------------------
# Request dataclasses (T009/T010) -- the raw CLI-option surface for the two
# Typer commands, threaded through the extracted phase functions instead of
# a long positional-argument list.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ImplementRequest:
    """The raw ``agent action implement`` CLI options, unresolved."""

    wp_id: str | None
    mission: str | None
    agent: str | None
    allow_sparse_checkout: bool
    acknowledge_not_bulk_edit: bool


@dataclass(frozen=True, slots=True)
class ReviewRequest:
    """The raw ``agent action review`` CLI options, unresolved."""

    wp_id: str | None
    mission: str | None
    agent: str | None


# ---------------------------------------------------------------------------
# Shared prompt renderers (pure -- list[str] in, list[str] out)
# ---------------------------------------------------------------------------


def render_resolved_agent_identity(assignment: AgentAssignment) -> list[str]:
    """Render the resolved agent 4-tuple for inclusion in implement/review prompts.

    Surfaces ``tool``, ``model``, ``profile_id`` and ``role`` so the implement
    and review prompt-render path no longer silently drops the trailing fields
    of a colon-formatted ``--agent`` string. See WP03 / GitHub issue #833.
    """
    profile_display = assignment.profile_id if assignment.profile_id else "(default)"
    role_display = assignment.role if assignment.role else "(default)"
    return [
        "Resolved agent identity:",
        f"  tool       : {assignment.tool}",
        f"  model      : {assignment.model}",
        f"  profile_id : {profile_display}",
        f"  role       : {role_display}",
    ]


def render_isolation_banner(wp_id: str, mode: str) -> list[str]:
    """Render the WP-isolation warning box shared by ``implement``/``review``.

    Campsite SAFE item #2 (S1192, DIRECTIVE_025 tidy-first): extracts the
    9x-duplicated blank-box banner line out of the two inline blocks
    (``implement`` / ``review``). ``mode`` (``"implement"`` or ``"review"``)
    selects the verb line and the two mode-specific bullets — ``implement``
    additionally warns about subtask ownership, ``review`` additionally warns
    about review/approval ownership. The rendered lines are byte-identical to
    the blocks this replaces (behaviour-preserving extraction, no new text).
    """
    lines = [
        "╔" + "=" * 78 + "╗",
        "║  🚨 CRITICAL: WORK PACKAGE ISOLATION RULES                              ║",
        "╠" + "=" * 78 + "╣",
    ]
    if mode == "implement":
        lines.append(f"║  YOU ARE ASSIGNED TO: {wp_id:<55} ║")
    else:
        lines.append(f"║  YOU ARE REVIEWING: {wp_id:<56} ║")
    lines.append("║                                                                          ║")
    lines.append("║  ✅ DO:                                                                  ║")
    lines.append(f"║     • Only modify status of {wp_id:<47} ║")
    if mode == "implement":
        lines.append(f"║     • Only mark subtasks belonging to {wp_id:<36} ║")
    lines.append("║     • Ignore git commits and status changes from other agents           ║")
    lines.append("║                                                                          ║")
    lines.append("║  ❌ DO NOT:                                                              ║")
    lines.append(f"║     • Change status of any WP other than {wp_id:<34} ║")
    lines.append("║     • React to or investigate other WPs' status changes                 ║")
    if mode == "implement":
        lines.append(f"║     • Mark subtasks that don't belong to {wp_id:<33} ║")
    else:
        lines.append(f"║     • Review or approve any WP other than {wp_id:<32} ║")
    lines.append("║                                                                          ║")
    lines.append("║  WHY: Multiple agents work in parallel. Each owns exactly ONE WP.       ║")
    lines.append("║       Git commits from other WPs are other agents - ignore them.        ║")
    lines.append("╚" + "=" * 78 + "╝")
    return lines


def render_wp_prompt_wrapper(wp_text: str) -> list[str]:
    """Render the WP-prompt BEGIN/END marker wrapper shared by ``implement``/``review``.

    Campsite SAFE item #3 (DIRECTIVE_025 tidy-first): extracts the
    byte-identical 9-line block both commands use to wrap the raw WP file
    text between banner markers. Behaviour-preserving.
    """
    return [
        "╔" + "=" * 78 + "╗",
        "║  WORK PACKAGE PROMPT BEGINS                                            ║",
        "╚" + "=" * 78 + "╝",
        "",
        wp_text,
        "",
        "╔" + "=" * 78 + "╗",
        "║  WORK PACKAGE PROMPT ENDS                                              ║",
        "╚" + "=" * 78 + "╝",
        "",
    ]


def workspace_contract_description(workspace: ResolvedWorkspace, wp_id: str) -> str:
    """Describe the canonical execution workspace for prompt output."""
    if workspace.lane_id:
        shared = ", ".join(workspace.lane_wp_ids or [wp_id])
        return f"Workspace contract: lane {workspace.lane_id} shared by {shared}"
    return "Workspace contract: repository root planning workspace"


def shared_artifact_guidance(workspace: ResolvedWorkspace, repo_root: Path, mission_slug: str) -> list[str]:
    """Render workspace-specific guidance about where mission artifacts live."""
    if workspace.lane_id:
        return [
            "📚 SHARED MISSION ARTIFACTS:",
            f"   Spec, plan, and tasks are visible from the primary checkout: {repo_root}/kitty-specs/{mission_slug}/",
            "   Status authority resolves through the coordination worktree for modern missions.",
            "   Use this lane workspace for code/tests; do not expect shared mission artifacts here",
        ]

    return [
        "📚 PLANNING ARTIFACTS:",
        f"   This WP runs in the repository root: {repo_root}",
        f"   Mission artifacts for this WP live here too: {repo_root}/kitty-specs/{mission_slug}/",
        "   Do not look for a separate lane worktree or workspace context file",
    ]


# ---------------------------------------------------------------------------
# Status-error classification (T007 -- _is_missing_canonical_status_error)
# ---------------------------------------------------------------------------


def is_missing_canonical_status_error(exc: BaseException) -> bool:
    """Return True when *exc* indicates missing canonical status bootstrap.

    Uses a structured ``isinstance`` check against the typed
    :class:`CanonicalStatusNotFoundError` (exported from the status facade)
    rather than matching prose in the exception message. ``locate_work_package``
    raises this type unwrapped (via ``get_wp_lane`` → ``get_lane_from_frontmatter``),
    so the type is visible at the call sites; a substring gate on the message
    would silently break the moment the wording is reworded (Cluster D).
    """
    from specify_cli.status import CanonicalStatusNotFoundError

    return isinstance(exc, CanonicalStatusNotFoundError)


def missing_canonical_status_message(
    wp_id: str, mission_slug: str, feature_dir: Path | None = None
) -> str:
    """Return a consistent hard-fail message for missing canonical status.

    When *feature_dir* is provided, surface an unresolved WP dependency cycle as
    the actionable root cause (#1589) instead of a "run finalize-tasks" hint that
    loops while the cycle keeps aborting finalize.
    """
    if feature_dir is not None:
        from specify_cli.status import uninitialized_status_error

        result: str = uninitialized_status_error(mission_slug, wp_id, feature_dir)
        return result
    return f"WP {wp_id} has no canonical status. Run `spec-kitty agent mission finalize-tasks --mission {mission_slug}` to initialize."


def normalize_wp_id(wp_arg: str) -> str:
    """Normalize WP ID from various formats to standard WPxx format.

    Args:
        wp_arg: User input (e.g., "wp01", "WP01", "WP01-foo-bar")

    Returns:
        Normalized WP ID (e.g., "WP01")
    """
    # Handle formats: wp01 → WP01, WP01 → WP01, WP01-foo-bar → WP01
    wp_upper = wp_arg.upper()

    # Extract just the WPxx part
    if wp_upper.startswith("WP"):
        # Split on hyphen and take first part
        return wp_upper.split("-")[0]
    else:
        # Assume it's like "01" or "1", prefix with WP
        return f"WP{wp_upper.lstrip('WP')}"


def auto_claim_failure_message(preview: object | None) -> str:
    """Return the user-facing error when auto-claim has no selectable WP."""
    selection_reason = getattr(preview, "selection_reason", None)
    if selection_reason == "dependencies_not_satisfied":
        return (
            "dependencies_not_satisfied: planned work packages are waiting on "
            "dependencies; all dependencies must be approved or done before "
            "implementation can start"
        )
    return "No planned work packages found. Specify a WP ID explicitly."


# ---------------------------------------------------------------------------
# Review-feedback resolution (T007 -- _resolve_review_feedback_*)
# ---------------------------------------------------------------------------


def resolve_review_feedback_pointer(repo_root: Path, pointer: str) -> Path | None:
    """Resolve a review feedback pointer to a file path.

    Supports two pointer formats:
    - ``review-cycle://<mission_slug>/<wp_slug>/review-cycle-N.md``
      → ``kitty-specs/<mission_slug>/tasks/<wp_slug>/review-cycle-N.md``
    - ``feedback://<mission_slug>/<task_id>/<filename>``  (legacy)
      → ``.git/spec-kitty/feedback/<mission_slug>/<task_id>/<filename>``

    Also handles legacy absolute-path strings.
    Returns None for sentinel values such as ``"force-override"`` and
    ``"action-review-claim"``, or any
    unrecognised / non-existent pointer.
    """
    from specify_cli.review.cycle import resolve_review_cycle_pointer

    try:
        result: Path | None = resolve_review_cycle_pointer(repo_root, pointer).path
        return result
    except ValueError:
        return None


def review_feedback_root(feature_dir: Path) -> Path:
    """The tree root review-feedback pointers resolve against (READ-side only).

    coord-primary-partition-lock WP07 (T034 dedup): the SOLE ``parent.parent``
    navigation for review-feedback pointer resolution, so the write-side
    rederivation ratchet (``test_no_write_side_rederivation.py``) has exactly
    ONE line to allow-list here instead of two duplicate call sites. This is
    NOT an FR-005 write-target/identity derivation -- ``feature_dir`` is
    ``<root>/kitty-specs/<slug>/``, so ``parent.parent`` is the tree root
    (coord worktree or main repo) that review-feedback artifacts are read
    from, a purely structural READ-path navigation unrelated to mission_id /
    mid8 / primary_root or the placement seam.
    """
    return feature_dir.parent.parent


def read_wp_events(feature_dir: Path, wp_id: str) -> list[StatusEvent]:
    """Return canonical status events for a single work package.

    ``read_events`` returns ``[]`` for an absent log and raises ``StoreError``
    only for a corrupt/invalid event log (invalid JSON or event structure) — the
    single concrete status-store exception this read tolerates by degrading to an
    empty list. Any other (genuinely-unexpected) exception propagates rather than
    being swallowed by a broad handler (D-14 campsite / Sonar S110-S1181).
    """
    from specify_cli.status import StoreError
    from specify_cli.status import read_events as _read_status_events

    try:
        return [event for event in _read_status_events(feature_dir) if event.wp_id == wp_id]
    except StoreError:
        return []


def latest_review_feedback_reference(
    feature_dir: Path,
    wp_id: str,
) -> tuple[str | None, Path | None, int | None]:
    """Return the newest canonical review feedback reference for *wp_id*.

    Operational sentinels like ``action-review-claim`` are intentionally
    skipped so implement/fix handoff uses the persisted review artifact
    instead of the transient reviewer claim marker. #4327: the synthetic
    approval/rejection tokens (``review:<WP>``, ``approval:<WP>``,
    ``auto-approval:<WP>:<date>``) are skipped the same way -- they are markers
    for a verdict that left no feedback artifact (an approved WP was never
    rejected), not paths to resolve and then misreport as "missing".
    """
    # Review feedback artifacts are committed under kitty-specs/ inside
    # whichever tree feature_dir lives in (coord worktree or main repo).
    feedback_root = review_feedback_root(feature_dir)
    wp_events = read_wp_events(feature_dir, wp_id)
    for index in range(len(wp_events) - 1, -1, -1):
        event = wp_events[index]
        if event.review_ref is None:
            continue
        review_ref = event.review_ref.strip()
        if not review_ref or _is_non_resolvable_review_ref(review_ref):
            continue
        return review_ref, resolve_review_feedback_pointer(feedback_root, review_ref), index
    return None, None, None


def resolve_review_feedback_context(
    feature_dir: Path,
    wp_id: str,
    wp_frontmatter: str,
) -> tuple[bool, str | None, Path | None, str | None]:
    """Resolve review-feedback presence and the canonical readable artifact.

    IC-04 / FR-006a / FR-007: the canonical event read (``event.review_ref``,
    source ``"canonical"``) is the sole authority post-cutover — the review
    feedback pointer lives on ``event.review_ref``, so the legacy frontmatter
    fallback (``review_status``/``review_feedback``) is deleted. A mission with
    frontmatter ``review_status: has_feedback`` but NO canonical ``review_ref``
    event now correctly returns "no feedback present" ``(False, None, None,
    None)``; the frontmatter is no longer review authority.

    ``wp_frontmatter`` is retained for the stable public signature (callers,
    including ``workflow_executor``, pass it by keyword) but is no longer read.
    """
    del wp_frontmatter  # FR-006a/FR-007: frontmatter is no longer a review authority

    review_feedback_ref, review_feedback_file, _ = latest_review_feedback_reference(feature_dir, wp_id)
    if review_feedback_ref is not None:
        return True, review_feedback_ref, review_feedback_file, "canonical"

    return False, None, None, None


def _resolve_review_cycle_sub_artifact_dir(feature_dir: Path, wp_slug: str) -> Path:
    """Resolve the review-cycle artifact directory for *wp_slug* (T024).

    WP05 (verdict-seam-write-unification-01KZ9Q35): this used to be a RAW
    ``feature_dir / "tasks" / wp_slug`` join -- one of the three sites WP04's
    review flagged as unrouted (alongside
    ``workflow_executor.py::implement_try_render_fix_mode_prompt`` and
    ``workflow.py::review``). Now routes through
    :func:`~specify_cli.review.cycle._review_cycle_wp_dir` (the T058 owner
    function), at its default ``kind`` (``WORK_PACKAGE_TASK``) -- matching the
    WRITE seam exactly, per that function's own docstring. Degrades to the
    historical flat join when no workspace root is derivable (a bare test
    fixture with no git ancestor).
    """
    from specify_cli.core.paths import WorkspaceRootNotFound, resolve_canonical_root
    from specify_cli.review.cycle import _review_cycle_wp_dir

    try:
        main_repo_root = resolve_canonical_root(feature_dir)
    except WorkspaceRootNotFound:
        return feature_dir / "tasks" / wp_slug

    mission_slug = feature_dir.name
    resolved: Path = _review_cycle_wp_dir(main_repo_root, mission_slug, wp_slug)
    return resolved


def has_prior_rejection(
    feature_dir: Path,
    wp_slug: str,
    normalized_wp_id: str,
) -> bool:
    """Check if a WP has review-cycle artifacts from a prior rejection.

    A prior rejection is active when:
    1. Review-cycle artifact files exist in the sub-artifact directory.
    2. The newest canonical review feedback reference for this WP resolves to a
       readable artifact.
    3. The WP has not since resolved to an approved/done terminal state.

    Args:
        feature_dir: Path to kitty-specs/<mission>/ in the main repo.
        wp_slug: Full WP file stem, e.g. "WP01-some-title".
        normalized_wp_id: Canonical WP ID, e.g. "WP01".

    Returns:
        True iff both artifact files and a rejection event are present.
    """
    sub_artifact_dir = _resolve_review_cycle_sub_artifact_dir(feature_dir, wp_slug)
    if not sub_artifact_dir.exists():
        return False
    if not list(sub_artifact_dir.glob("review-cycle-*.md")):
        return False

    wp_events = read_wp_events(feature_dir, normalized_wp_id)
    if not wp_events:
        return False

    review_feedback_ref, review_feedback_file, review_feedback_index = latest_review_feedback_reference(
        feature_dir,
        normalized_wp_id,
    )
    if review_feedback_ref is None or review_feedback_file is None or review_feedback_index is None:
        return False

    if any(event.to_lane in {Lane.APPROVED, Lane.DONE} for event in wp_events[review_feedback_index + 1 :]):
        return False

    latest_event = wp_events[-1]
    return latest_event.to_lane not in {Lane.APPROVED, Lane.DONE}


# ---------------------------------------------------------------------------
# New pure helpers extracted from ``_resolve_review_context`` / ``review``
# (T011 -- reduces those two functions' branch count without moving them)
# ---------------------------------------------------------------------------


def pick_best_base_branch(scored_candidates: list[tuple[str, int]]) -> tuple[str | None, int]:
    """Pick the base-branch candidate with the FEWEST unique commits.

    Pure selection logic extracted from ``_resolve_review_context``'s
    unknown-base-ref fallback: given a list of ``(candidate, commit_count)``
    pairs already computed via ``git merge-base`` + ``git rev-list --count``,
    return the first candidate with the lowest count (ties keep the
    EARLIEST-scored candidate, matching the original ``count < best_count``
    strict-less-than comparison -- byte-identical selection behaviour).
    """
    best_base: str | None = None
    best_count = -1
    for candidate, count in scored_candidates:
        if best_count == -1 or count < best_count:
            best_count = count
            best_base = candidate
    return best_base, best_count


def parse_dependency_wp_ids(wp_frontmatter: str) -> list[str]:
    """Extract ``WPnn`` dependency ids from a WP's raw frontmatter text.

    Pure regex extraction lifted out of ``_resolve_review_context``'s
    unknown-base-ref fallback -- the frontmatter's ``dependencies: [...]``
    scalar is parsed here; resolving each id to an actual dependency
    workspace (I/O) stays with the caller.
    """
    dep_match = re.search(r"dependencies:\s*\[([^\]]*)\]", wp_frontmatter)
    if not dep_match:
        return []
    dep_content = dep_match.group(1).strip()
    if not dep_content:
        return []
    return re.findall(r'"?(WP\d+)"?', dep_content)


def build_owned_files_review_pathspecs(owned_files: list[str], mission_slug: str) -> list[str]:
    """Build the ``git diff``/``git log`` pathspec list for a repo-root review.

    Extracted from ``review()``'s two byte-identical inline blocks (S1192):
    when a WP's ``owned_files`` includes anything under the mission's own
    ``kitty-specs/<slug>/`` tree, the mission's ``tasks/``, ``tasks.md``,
    and status-artifact files are excluded from the reviewer's diff/log
    commands (they are lifecycle bookkeeping, not implementation content).
    Returns ``[]`` when *owned_files* is empty (matches both call sites'
    guard).
    """
    if not owned_files:
        return []
    from specify_cli.cli.commands.agent.workflow import _STATUS_EVENTS_FILENAME, _STATUS_FILENAME

    pathspecs = list(owned_files)
    mission_root = f"kitty-specs/{mission_slug}/"
    if any(path.startswith(mission_root) for path in pathspecs):
        pathspecs.extend(
            [
                f":(exclude){mission_root}tasks/**",
                f":(exclude){mission_root}tasks.md",
                f":(exclude){mission_root}{_STATUS_EVENTS_FILENAME}",
                f":(exclude){mission_root}{_STATUS_FILENAME}",
            ]
        )
    return pathspecs


def event_is_review_claim(event: StatusEvent) -> bool:
    """True when a status *event* represents a "claimed for review" transition.

    Shared predicate extracted from the byte-identical inline closures in
    ``_find_first_for_review_wp`` and ``review()`` (S1192): the NEW canonical
    shape is ``to_lane == IN_REVIEW``; the LEGACY shape is
    ``to_lane == IN_PROGRESS`` carrying the ``"action-review-claim"``
    ``review_ref`` sentinel.
    """
    return bool(
        event.to_lane == Lane.IN_REVIEW
        or (event.to_lane == Lane.IN_PROGRESS and event.review_ref == "action-review-claim")
    )
