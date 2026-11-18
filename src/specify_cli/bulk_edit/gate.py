"""Gate function for bulk edit occurrence classification.

Blocks implementation and review for missions marked change_mode: bulk_edit
when the occurrence_map.yaml is missing or structurally incomplete.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from kernel.git import GitCommandError, changed_entries, run_git
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from specify_cli.bulk_edit.diff_check import (
    DiffCheckResult,
    check_diff_compliance,
)
from specify_cli.bulk_edit.occurrence_map import (
    check_admissibility,
    load_occurrence_map,
    validate_occurrence_map,
)
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.paths import load_meta_fail_closed


@dataclass(frozen=True)
class GateResult:
    """Outcome of the occurrence classification gate check."""

    passed: bool
    change_mode: str | None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GitDiffFilesResult:
    """Outcome of resolving the review-time file diff."""

    ok: bool
    files: list[str] = field(default_factory=list)
    stderr: str = ""
    returncode: int | None = None
    # Per-path git change status (``A``/``M``/``D``/``R``), from
    # ``--name-status``. An occurrence map constrains what may happen to
    # content that already exists, so the gate cannot judge a path without
    # knowing whether this diff created it or edited it.
    statuses: dict[str, str] = field(default_factory=dict)


def _is_bulk_edit_mission(feature_dir: Path) -> bool:
    """Return ``True`` iff *feature_dir* belongs to a ``change_mode: bulk_edit`` mission.

    Centralizes the guard that used to be duplicated between
    :func:`ensure_occurrence_classification_ready` and
    :func:`check_review_diff_compliance`, so "what counts as bulk_edit"
    cannot drift between the two gate entry points.

    FR-007 / #3162: routed through the ONE fail-closed reader — a corrupt or
    non-object ``meta.json`` raises the typed :class:`MissionMetaReadError`
    instead of a raw ``ValueError``; a missing file still reads as ``None``
    (not a bulk_edit mission).
    """
    meta = load_meta_fail_closed(feature_dir)
    return meta is not None and meta.get("change_mode") == "bulk_edit"


def _feature_dir_rel(feature_dir: Path, repo_root: Path) -> str | None:
    """Return *feature_dir* relative to *repo_root* as a POSIX path, or ``None``.

    ``None`` means *feature_dir* is not nested under *repo_root* (e.g. a
    test double built from unrelated temp directories) — callers treat that
    as "cannot anchor the runtime-state exemption" and fall back to the
    ordinary classifier for every file.

    The result is normalised to the mission's CANONICAL planning path,
    ``kitty-specs/<slug>``, whenever *feature_dir* names one. On a
    coord-topology mission the resolved ``feature_dir`` is the STATUS-only
    ``-coord`` worktree husk, so the raw relative path is
    ``.worktrees/<mission>-coord/kitty-specs/<slug>`` — a prefix that never
    appears in a diff taken against the main repo root. Anchoring on that
    silently disabled the runtime-state exemption for exactly the topology
    that needs it, so a mission's own status.json and status.events.jsonl
    blocked its own reviews: diff paths are relative to the partition they
    live in, not to wherever the husk sits on disk.
    """
    try:
        relative = feature_dir.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return None
    parts = relative.parts
    # Rightmost ``kitty-specs/<slug>`` wins: that is the canonical form the
    # diff uses regardless of which worktree the husk lives in.
    for index in range(len(parts) - 2, -1, -1):
        if parts[index] == KITTY_SPECS_DIR:
            return Path(*parts[index : index + 2]).as_posix()
    return relative.as_posix()


def ensure_occurrence_classification_ready(feature_dir: Path) -> GateResult:
    """Check if a bulk_edit mission has a valid occurrence map.

    For non-bulk-edit missions, always passes (zero cost).

    FR-007 / #3162: routed through the ONE fail-closed reader — a corrupt or
    non-object ``meta.json`` raises the typed :class:`MissionMetaReadError`
    instead of a raw ``ValueError``; a missing file still reads as ``None``.
    """
    meta = load_meta_fail_closed(feature_dir)
    if meta is None:
        return GateResult(passed=True, change_mode=None)

    if not _is_bulk_edit_mission(feature_dir):
        # FR-012 / NFR-001: never propagate a raw legacy value. The invariant is
        # ``GateResult.change_mode in {"bulk_edit", None}`` — a non-bulk-edit
        # mission collapses to ``None`` so downstream readers keying on the ONE
        # canonical ``== "bulk_edit"`` check treat legacy value and absence alike.
        return GateResult(passed=True, change_mode=None)

    # Load and validate occurrence map
    omap = load_occurrence_map(feature_dir)
    if omap is None:
        return GateResult(
            passed=False,
            change_mode="bulk_edit",
            errors=[
                "Occurrence map required for bulk_edit missions. "
                f"Create {feature_dir}/occurrence_map.yaml with target, categories, and actions."
            ],
        )

    validation = validate_occurrence_map(omap)
    if not validation.valid:
        return GateResult(
            passed=False,
            change_mode="bulk_edit",
            errors=validation.errors,
            warnings=validation.warnings,
        )

    admissibility = check_admissibility(omap)
    if not admissibility.valid:
        return GateResult(
            passed=False,
            change_mode="bulk_edit",
            errors=admissibility.errors,
            warnings=admissibility.warnings,
        )

    return GateResult(
        passed=True,
        change_mode="bulk_edit",
        warnings=validation.warnings + admissibility.warnings,
    )


def render_gate_failure(result: GateResult, console: Console) -> None:
    """Display gate failure with Rich formatting."""
    panel = Panel(
        "\n".join(f"  \u2022 {e}" for e in result.errors),
        title="[bold red]Bulk Edit Gate: BLOCKED[/]",
        subtitle="Create or fix occurrence_map.yaml before proceeding",
        border_style="red",
    )
    console.print(panel)


FINALIZE_TASKS_GATE_BLOCKED_MESSAGE = "Bulk edit occurrence-map gate blocked finalize-tasks."


def finalize_tasks_gate_error_payload(result: GateResult) -> dict[str, object]:
    """Build the standard JSON error payload for a failed finalize-tasks occurrence gate.

    Shared by every ``finalize-tasks`` call site (``mission_finalize`` and the
    legacy ``tasks_finalize``) so the error message and payload shape cannot
    drift between the two independently-dispatched commands that both enforce
    this gate at the same point in the finalize-tasks flow.
    """
    return {"error": FINALIZE_TASKS_GATE_BLOCKED_MESSAGE, "gate_errors": list(result.errors)}


# ---------------------------------------------------------------------------
# Review-time diff compliance (FR-007 + FR-008)
# ---------------------------------------------------------------------------


def _first_parent_paths(repo_root: Path, base_ref: str, head_ref: str) -> set[str]:
    """The paths the non-merge commits on the first-parent chain of ``base..head`` touch (#7726, ruling B).

    Content a merge brings in (another branch's commits) is not in the set; a rebase or a
    fast-forward puts foreign commits on the first-parent chain, so they stay. Raises
    :class:`GitCommandError` on a git failure, which the caller turns into a refusal.
    """
    result = run_git(
        repo_root, "log", "-z", "--first-parent", "--no-merges", "--name-only", "--format=", f"{base_ref}..{head_ref}", timeout=30
    )
    # NUL-delimited (``-z``), so a path git would quote is exact, like ``changed_entries``.
    return {path.strip("\n") for path in result.stdout.decode("utf-8", "replace").split("\0") if path.strip("\n")}


def _git_diff_files(
    repo_root: Path,
    base_ref: str,
    head_ref: str,
    exclude_pathspecs: tuple[str, ...] = (),
    *,
    first_parent_only: bool = False,
) -> GitDiffFilesResult:
    """Return the files changed between *base_ref* and *head_ref*, with status.

    Uses ``git diff --name-status <base>..<head>`` and returns one path per
    entry, relative to *repo_root*, alongside each path's change status.
    Git failures are returned explicitly so callers can fail closed instead
    of confusing them with valid empty diffs.

    The status matters: an occurrence map says what may happen to content
    that already exists, so a path the diff CREATED cannot violate it. Using
    ``--name-only`` here (as this function originally did) discards that
    distinction and makes the gate read every added file as though its
    protected content had been edited.
    """
    for label, ref in (("base_ref", base_ref), ("head_ref", head_ref)):
        if not ref.strip():
            return GitDiffFilesResult(
                ok=False,
                stderr=f"{label} is empty",
                returncode=None,
            )
        try:
            verified = subprocess.run(
                ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            return GitDiffFilesResult(
                ok=False,
                stderr=f"failed to verify {label} {ref!r}: {exc}",
                returncode=None,
            )
        if verified.returncode != 0:
            stderr = verified.stderr.strip() or f"{label} {ref!r} could not be resolved"
            return GitDiffFilesResult(
                ok=False,
                stderr=stderr,
                returncode=verified.returncode,
            )

    try:
        # Default rename detection: only the new path of a rename is listed.
        # NUL-delimited, so a quoted path is exact. ``changed_entries``
        # carries each path's status alongside it, which the occurrence
        # check needs to tell creation from modification.
        # ``exclude_pathspecs`` (#7726) drops the Mission's own bookkeeping, the same set the
        # review range excludes, so the gate and the range agree on what the work package changed.
        # ``glob=True`` keeps git's default (non-literal) matching, which the excludes need.
        pathspecs = (".", *exclude_pathspecs) if exclude_pathspecs else ()
        entries = changed_entries(
            repo_root, f"{base_ref}..{head_ref}", renames=True, pathspecs=pathspecs, glob=True, timeout=30
        )
    except GitCommandError as exc:
        return GitDiffFilesResult(
            ok=False,
            stderr=exc.stderr.strip() or str(exc),
            returncode=exc.returncode if exc.returncode > 0 else None,
        )
    if first_parent_only:
        # The net change of every path a work package's own commit touched; a path only a
        # merge touched is left out. Each kept path keeps its net status (A/M/D) from the diff.
        try:
            own = _first_parent_paths(repo_root, base_ref, head_ref)
        except GitCommandError as exc:
            return GitDiffFilesResult(ok=False, stderr=exc.stderr.strip() or str(exc), returncode=exc.returncode if exc.returncode > 0 else None)
        entries = tuple(entry for entry in entries if str(entry.path) in own)
    files = [str(entry.path) for entry in entries]
    # Normalise ``R100``/``C075`` to their leading letter: the occurrence
    # check cares about the KIND of change, not the similarity score.
    statuses = {
        str(entry.path): (entry.status[:1].upper() if entry.status else "")
        for entry in entries
    }
    return GitDiffFilesResult(
        ok=True, files=files, stderr="", returncode=0, statuses=statuses
    )


#: #7726: the review gate's range refusals. The range comes from the one review-range owner
#: (``review.wp_range.resolve_wp_review_range``): a range that cannot be determined, or that holds
#: no commit, leaves the gate nothing to judge, so it refuses instead of passing.
BULK_EDIT_REVIEW_RANGE_UNAVAILABLE = "BULK_EDIT_REVIEW_RANGE_UNAVAILABLE"
BULK_EDIT_REVIEW_RANGE_EMPTY = "BULK_EDIT_REVIEW_RANGE_EMPTY"
BULK_EDIT_REVIEW_TIP_REWRITTEN = "BULK_EDIT_REVIEW_TIP_REWRITTEN"


def resubmit_command(wp_id: str, mission_slug: str) -> str:
    """The command that hands *wp_id* to review again, so its submission is recorded afresh."""
    return f"spec-kitty agent tasks move-task {wp_id} --to for_review --mission {mission_slug}"


@dataclass(frozen=True)
class ReviewRangeFacts:
    """What the gate needs of a ``WpReviewRange`` (kept primitive so this module stays free of the review package).

    ``commit_count`` counts the range's commits outside Mission bookkeeping.
    """

    base: str | None
    tip: str | None
    gap: str | None
    commit_count: int
    listing_gap: str | None
    tip_off_branch: bool = False


def _unavailable_remedy(facts: ReviewRangeFacts, wp_id: str, mission_slug: str) -> str:
    to_review = resubmit_command(wp_id, mission_slug)
    if facts.gap == "no_submission":
        return f"Hand the work package to review first: {to_review}"
    if facts.gap == "status_unreadable":
        return f"Run `spec-kitty agent tasks status --mission {mission_slug}` to see why the status surface cannot be read, fix it, then retry."
    return (
        "The recorded window open or submission does not resolve to a commit here. Fetch the commits the "
        "work package was written on (for a pull request, its head), then retry; if they no longer exist, "
        f"move the work package back to in_progress and re-submit it ({to_review}) so the submission is recorded again."
    )


def review_range_refusal(facts: ReviewRangeFacts, *, wp_id: str, mission_slug: str) -> str | None:
    """The gate's refusal for a review range it cannot judge, or ``None`` when the range is judgeable.

    A range of status commits only is empty (the claim and the submission commit bookkeeping, so
    ``base`` rarely equals ``tip``). Never demands a local branch: every end is a recorded commit,
    and the remedies name status moves or a fetch.
    """
    base, tip = facts.base, facts.tip
    if base is None or tip is None:
        return (
            f"{BULK_EDIT_REVIEW_RANGE_UNAVAILABLE}: the bulk-edit review gate cannot judge {wp_id}: its review range "
            f"is unavailable (gap: {facts.gap or 'unknown'}). {_unavailable_remedy(facts, wp_id, mission_slug)}"
        )
    if facts.listing_gap is not None and "commits" in facts.listing_gap.split(", "):
        return (
            f"{BULK_EDIT_REVIEW_RANGE_UNAVAILABLE}: the bulk-edit review gate cannot judge {wp_id}: the commits of its "
            f"review range {base[:12]}..{tip[:12]} could not be listed. Check that the repository is readable, then retry."
        )
    if facts.tip_off_branch:
        return (
            f"{BULK_EDIT_REVIEW_TIP_REWRITTEN}: {wp_id}'s submitted tip {tip[:12]} is no longer on its branch (the branch "
            f"was rewritten after the submission), so the work under review is not the work submitted. Re-submit it: "
            f"{resubmit_command(wp_id, mission_slug)}"
        )
    if base == tip or facts.commit_count == 0:
        return (
            f"{BULK_EDIT_REVIEW_RANGE_EMPTY}: the bulk-edit review gate has nothing to judge for {wp_id}: its review "
            f"range {base[:12]}..{tip[:12]} holds no commit outside Mission bookkeeping. Commit the work package's "
            f"change, then re-submit it: {resubmit_command(wp_id, mission_slug)}"
        )
    return None


def check_review_diff_compliance(
    feature_dir: Path,
    repo_root: Path,
    base_ref: str,
    head_ref: str,
    exclude_pathspecs: tuple[str, ...] = (),
    *,
    first_parent_only: bool = False,
) -> DiffCheckResult | None:
    """Run the review-time diff compliance check (FR-007 + FR-008).

    *exclude_pathspecs* (``:(exclude)`` pathspecs, #7726) leave paths out of the diff: the review
    gate passes the review range's bookkeeping excludes. *first_parent_only* (#7726, ruling B)
    judges only the paths the non-merge first-parent commits touched, so content a merge pulled
    into a shared branch is not judged; a rebased or fast-forwarded foreign commit still is.

    Returns ``None`` when the mission is not a bulk_edit — callers should
    skip any further review-time checks in that case.

    Returns a :class:`DiffCheckResult` with ``passed`` set according to
    whether the diff respects the occurrence map's category actions and
    exceptions. Callers are expected to render the result via
    :func:`render_diff_check_failure` and ``raise typer.Exit(1)`` when
    ``passed`` is False.
    """
    if not _is_bulk_edit_mission(feature_dir):
        return None

    omap = load_occurrence_map(feature_dir)
    if omap is None:
        # The artifact-admissibility gate should have rejected this case
        # already; if we got here, something is off — fall through and
        # surface the error.
        return DiffCheckResult(
            passed=False,
            errors=[
                "Review diff check cannot run: occurrence_map.yaml is missing "
                "despite change_mode: bulk_edit."
            ],
        )

    diff_files = _git_diff_files(repo_root, base_ref, head_ref, exclude_pathspecs, first_parent_only=first_parent_only)
    if not diff_files.ok:
        details = [
            "Review diff check cannot run: git diff failed.",
            f"base_ref={base_ref!r}",
            f"head_ref={head_ref!r}",
            f"returncode={diff_files.returncode!r}",
        ]
        if diff_files.stderr:
            details.append(f"stderr={diff_files.stderr}")
        return DiffCheckResult(passed=False, errors=["; ".join(details)])

    feature_dir_rel = _feature_dir_rel(feature_dir, repo_root)
    return check_diff_compliance(
        diff_files.files, omap, feature_dir_rel, diff_files.statuses
    )


# How each FileAssessment.source reads in the operator-facing table, where
# `category` is None because the verdict came from an exemption rather than
# the path heuristic. "(unclassified)" was shown for all of these, which
# describes only the last one.
_SOURCE_LABELS: dict[str, str] = {
    "added": "created here",
    "non-occurrence": "no occurrences",
    "runtime-state": "own bookkeeping",
    "exception": "map exception",
    "move": "declared move",
    "structural-target": "structural target",
    "path-heuristic": "(unclassified)",
}


def _source_label(source: str) -> str:
    return _SOURCE_LABELS.get(source, source)


def render_diff_check_failure(
    result: DiffCheckResult,
    console: Console,
) -> None:
    """Display a diff compliance failure with a Rich table of assessments.

    Lists the rows that BLOCK and the rows asking for manual review; the
    rest are summarised by the reason they passed.

    Listing every assessment meant a work package touching hundreds of
    files printed hundreds of rows to report a handful of violations — on a
    415-file ingest, ~550 lines of ``ok`` around 3 ``BLOCK``s — and each
    exempted row read as ``(unclassified) | (none)``, which looks like a
    complaint rather than a pass.
    """
    blocking = [a for a in result.assessments if a.violation]
    reviewable = [
        a for a in result.assessments
        if not a.violation and a.action == "manual_review"
    ]

    table = Table(title="Bulk Edit Review: Diff Compliance", show_lines=False)
    table.add_column("File", overflow="fold")
    table.add_column("Category", no_wrap=True)
    table.add_column("Action", no_wrap=True)
    table.add_column("Verdict", no_wrap=True)
    for assessment, verdict in (
        *((a, "[bold red]BLOCK[/]") for a in blocking),
        *((a, "[yellow]review[/]") for a in reviewable),
    ):
        table.add_row(
            assessment.path,
            assessment.category or _source_label(assessment.source),
            assessment.action or "(none)",
            verdict,
        )
    console.print(table)

    others = [
        a for a in result.assessments
        if not a.violation and a.action != "manual_review"
    ]
    if others:
        counts: dict[str, int] = {}
        for a in others:
            counts[a.source] = counts.get(a.source, 0) + 1
        summary = ", ".join(
            f"{count} {_source_label(source)}"
            for source, count in sorted(counts.items(), key=lambda kv: -kv[1])
        )
        console.print(f"[green]{len(others)} further files passed[/]: {summary}")

    if result.errors:
        panel = Panel(
            "\n".join(f"  \u2022 {e}" for e in result.errors),
            title="[bold red]Review Rejected: Diff Compliance Violations[/]",
            subtitle="FR-007/FR-008 — forbidden or unclassified surfaces touched",
            border_style="red",
        )
        console.print(panel)
