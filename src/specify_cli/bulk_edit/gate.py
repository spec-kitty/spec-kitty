"""Gate function for bulk edit occurrence classification.

Blocks implementation and review for missions marked change_mode: bulk_edit
when the occurrence_map.yaml is missing or structurally incomplete.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

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
    """
    try:
        return feature_dir.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return None


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


def _git_diff_files(
    repo_root: Path,
    base_ref: str,
    head_ref: str,
) -> GitDiffFilesResult:
    """Return the list of files changed between *base_ref* and *head_ref*.

    Uses ``git diff --name-only <base>..<head>`` and returns one path per
    line, relative to *repo_root*. Git failures are returned explicitly so
    callers can fail closed instead of confusing them with valid empty diffs.
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
        completed = subprocess.run(
            ["git", "diff", "--name-only", f"{base_ref}..{head_ref}"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        return GitDiffFilesResult(
            ok=False,
            stderr=str(exc),
            returncode=None,
        )
    if completed.returncode != 0:
        return GitDiffFilesResult(
            ok=False,
            stderr=completed.stderr.strip(),
            returncode=completed.returncode,
        )
    return GitDiffFilesResult(
        ok=True,
        files=[line.strip() for line in completed.stdout.splitlines() if line.strip()],
        stderr=completed.stderr.strip(),
        returncode=completed.returncode,
    )


def check_review_diff_compliance(
    feature_dir: Path,
    repo_root: Path,
    base_ref: str,
    head_ref: str,
) -> DiffCheckResult | None:
    """Run the review-time diff compliance check (FR-007 + FR-008).

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

    diff_files = _git_diff_files(repo_root, base_ref, head_ref)
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
    return check_diff_compliance(diff_files.files, omap, feature_dir_rel)


def render_diff_check_failure(
    result: DiffCheckResult,
    console: Console,
) -> None:
    """Display a diff compliance failure with a Rich table of assessments."""
    table = Table(title="Bulk Edit Review: Diff Compliance", show_lines=False)
    table.add_column("File", overflow="fold")
    table.add_column("Category", no_wrap=True)
    table.add_column("Action", no_wrap=True)
    table.add_column("Verdict", no_wrap=True)
    for a in result.assessments:
        verdict = "[bold red]BLOCK[/]" if a.violation else (
            "[yellow]review[/]" if a.action == "manual_review" else "[green]ok[/]"
        )
        table.add_row(
            a.path,
            a.category or "(unclassified)",
            a.action or "(none)",
            verdict,
        )
    console.print(table)

    if result.errors:
        panel = Panel(
            "\n".join(f"  \u2022 {e}" for e in result.errors),
            title="[bold red]Review Rejected: Diff Compliance Violations[/]",
            subtitle="FR-007/FR-008 — forbidden or unclassified surfaces touched",
            border_style="red",
        )
        console.print(panel)
