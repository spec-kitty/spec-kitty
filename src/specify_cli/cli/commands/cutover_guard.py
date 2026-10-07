"""``spec-kitty cutover-guard`` — diff-scoped, fail-closed cut-over gate.

Realises contracts/pre-merge-guard.md (IC-03 / IC-04; FR-002, FR-003, FR-008,
FR-009, NFR-002, NFR-003) for mission runtime-state-birth-cutover-all-paths.

For every mission whose ``kitty-specs/<mission>/`` corpus appears in a PR
diff, decides "cut over" via the SAME event-log-evidence authority the
dogfood corpus lock uses
(:mod:`specify_cli.status.cutover_eligibility` — never a fork of it), fails
closed on any un-cut-over mission (printing the mission slug(s) and the
exact remedy command), and fails closed on verify error, ambiguity, or an
undeterminable diff. It never passes on uncertainty (NFR-003).

One touched slug is outside the guard's domain rather than uncertain: a
directory the diff relocates OUT of ``kitty-specs/`` that carried neither a
``meta.json`` nor a ``status.events.jsonl`` at the merge-base (never a
mission, never any runtime state to cut over — e.g. the FR-007 relocation of
non-mission program evidence). With ``--base-ref`` the guard reads that base
tree and reports such a slug as a removed non-mission directory; without
a base tree (``--paths-from``) a vanished directory stays a closed failure.

Usage::

    spec-kitty cutover-guard --base-ref origin/main
    spec-kitty cutover-guard --paths-from changed-files.txt
    spec-kitty cutover-guard --base-ref origin/main --json

Exit codes:

* ``0`` — every diff-touched mission is cut over (or none were touched).
* ``1`` — one or more diff-touched missions are un-cut-over, OR the diff
  itself could not be determined (unknown ``--base-ref``, unreadable
  ``--paths-from`` file, missing project root).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Annotated

import typer

from specify_cli.cli.console import console, err_console
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.paths import assert_safe_path_segment, locate_project_root
from specify_cli.core.vcs.git import (
    git_diff_names_checked,
    git_ls_tree_names_checked,
    git_merge_base,
)
from specify_cli.status import (
    PRE_ACCEPT_EXEMPT_NOTE,
    REASON_ABSENT_MISSION_ID,
    REASON_LEGACY_FRONTMATTER,
    REASON_LEGACY_UNDECIDABLE,
    REASON_PHASE_MALFORMED,
    REASON_TERMINAL_MALFORMED,
    REASON_TERMINAL_UNSTAMPED,
    CutOverVerdict,
    is_cut_over,
)

#: FR-003: the exact remedy string printed for every un-cut-over mission.
_REMEDY_TEMPLATE = "spec-kitty migrate backfill-runtime-state --mission {slug}"

#: Reason-specific remedies (FR-007), keyed by the first reason of a failing
#: verdict. Reasons not listed (including the legacy generic
#: ``status_phase not flipped...`` prefix) fall back to :data:`_REMEDY_TEMPLATE`.
_REMEDY_BY_REASON: dict[str, str] = {
    REASON_TERMINAL_UNSTAMPED: _REMEDY_TEMPLATE,
    REASON_LEGACY_FRONTMATTER: _REMEDY_TEMPLATE,
    REASON_PHASE_MALFORMED: 'fix meta.json status_phase in kitty-specs/{slug}/ (expected an integer, e.g. "1"), then rerun',
    REASON_TERMINAL_MALFORMED: "set accepted_at / merged_at in kitty-specs/{slug}/meta.json to an ISO-8601 string (or remove the key), then rerun",
    REASON_LEGACY_UNDECIDABLE: "repair the unreadable WP file under kitty-specs/{slug}/tasks/, then rerun",
    REASON_ABSENT_MISSION_ID: "repair kitty-specs/{slug}/meta.json if it is missing or not valid JSON; otherwise run spec-kitty migrate backfill-identity",
}

#: The artifacts whose presence at the merge-base places a directory INSIDE
#: the guard's domain: mission identity (``meta.json``, read by the shared
#: ``is_cut_over`` authority) and the event-log runtime evidence it keys on.
_MISSION_ARTIFACT_NAMES: frozenset[str] = frozenset({"meta.json", "status.events.jsonl"})


class CutoverGuardError(Exception):
    """Raised when the diff to evaluate cannot be determined (fail-closed)."""


@dataclass(frozen=True)
class GuardVerdict:
    """The guard's decision over every mission touched by a diff.

    ``passed`` is True iff every touched mission is cut over (including the
    vacuous case of zero touched missions). ``failures`` carries one
    :class:`~specify_cli.status.cutover_eligibility.CutOverVerdict` per
    un-cut-over / undecidable mission, in slug order.
    """

    passed: bool
    touched_slugs: tuple[str, ...]
    failures: tuple[CutOverVerdict, ...]
    #: Touched slugs whose directory the diff removed from the corpus and
    #: which carried no mission artifact anywhere below it at the merge-base
    #: (a relocation or deletion of non-mission content) — outside the
    #: guard's domain, reported for transparency, never counted as failures.
    non_mission_slugs: tuple[str, ...] = ()
    #: Touched Missions that pass only through the pre-accept exemption
    #: (#5835): not yet accepted, no ``status_phase`` stamp by design. They
    #: are not failures and are not claimed to be cut over.
    exempt: tuple[CutOverVerdict, ...] = ()


@dataclass(frozen=True)
class GitDiffScope:
    """The ``kitty-specs``-scoped diff the guard evaluates, plus its base tree."""

    paths: tuple[str, ...]
    merge_base: str


def touched_mission_slugs(paths: list[str]) -> tuple[str, ...]:
    """Return the sorted, deduplicated ``kitty-specs/<slug>`` slugs touched by *paths*.

    Reads the first two path segments only (``kitty-specs/<slug>/...``);
    non-``kitty-specs`` paths are ignored. Every mission whose corpus is
    touched anywhere is included, not merely the "current" mission (R3).
    """
    slugs: set[str] = set()
    for raw in paths:
        parts = PurePosixPath(raw).parts
        if len(parts) >= 2 and parts[0] == KITTY_SPECS_DIR:
            slugs.add(parts[1])
    return tuple(sorted(slugs))


def changed_paths_from_git(repo_root: Path, base_ref: str) -> GitDiffScope:
    """Return the ``kitty-specs``-scoped diff between *base_ref* and ``HEAD``.

    The result carries the merge-base SHA alongside the paths so the
    evaluator can consult the base tree for a directory the diff removed.

    Composes the canonical merge-base + name-only diff primitives
    (``specify_cli.core.vcs.git``) directly rather than the tolerant
    ``merge_base_changed_files`` convenience, because that convenience
    degrades to an EMPTY tuple on any git failure — which this fail-closed
    guard must never read as "nothing touched, pass". A failed merge-base or
    diff instead raises :class:`CutoverGuardError`.
    """
    merge_base = git_merge_base(repo_root, base_ref, "HEAD")
    if merge_base is None:
        raise CutoverGuardError(f"could not resolve a merge-base between {base_ref!r} and HEAD (unknown ref, or the repository has no common ancestor)")
    changed = git_diff_names_checked(repo_root, merge_base, "HEAD", pathspec=KITTY_SPECS_DIR)
    if changed is None:
        raise CutoverGuardError(f"git diff failed against merge-base {merge_base}")
    return GitDiffScope(paths=changed, merge_base=merge_base)


def _removed_directory_verdict(repo_root: Path, mission_dir: Path, slug: str, merge_base: str | None) -> CutOverVerdict | None:
    """Classify a touched slug whose directory no longer exists at HEAD.

    Returns ``None`` when the slug is outside the guard's domain — the
    directory existed at *merge_base* and carried no mission artifact
    (:data:`_MISSION_ARTIFACT_NAMES`) at any depth below it, so the diff
    relocated or deleted non-mission content and there is nothing to cut
    over. Every other case is a closed failure: no base tree to consult, an
    unreadable base tree, a slug absent from the base too (ambiguous), or a
    removed directory that WAS a mission. The base listing is recursive so a
    nested artifact keeps the directory inside the domain (fail-closed).
    """
    removed_reason = "mission directory not found in corpus (ambiguous or removed)"
    if merge_base is None:
        return CutOverVerdict(mission_dir=mission_dir, mission_slug=slug, cut_over=False, reasons=(removed_reason,))
    entries = git_ls_tree_names_checked(repo_root, merge_base, f"{KITTY_SPECS_DIR}/{slug}/")
    if entries is None:
        return CutOverVerdict(
            mission_dir=mission_dir,
            mission_slug=slug,
            cut_over=False,
            reasons=(f"could not read merge-base tree {merge_base} for the removed directory",),
        )
    if not entries:
        return CutOverVerdict(mission_dir=mission_dir, mission_slug=slug, cut_over=False, reasons=(removed_reason,))
    carried = sorted(name for name in (PurePosixPath(entry).name for entry in entries) if name in _MISSION_ARTIFACT_NAMES)
    if carried:
        return CutOverVerdict(
            mission_dir=mission_dir,
            mission_slug=slug,
            cut_over=False,
            reasons=(f"mission directory removed from corpus but carried {', '.join(carried)} at merge-base {merge_base[:12]}",),
        )
    return None


def evaluate_touched_missions(
    repo_root: Path,
    changed_paths: list[str],
    *,
    merge_base: str | None = None,
) -> GuardVerdict:
    """Decide cut-over for every mission named by *changed_paths*.

    Fails closed per-mission: a missing mission directory (ambiguous/removed
    corpus) or ANY exception raised while deciding cut-over is recorded as a
    failure rather than silently skipped (NFR-003) — the guard never passes
    on uncertainty.

    *merge_base* (the SHA ``changed_paths`` was diffed from) lets the guard
    tell a removed non-mission directory apart from a removed mission —
    see :func:`_removed_directory_verdict`. ``None`` keeps every vanished
    directory a closed failure.
    """
    corpus = repo_root / KITTY_SPECS_DIR
    slugs = touched_mission_slugs(changed_paths)

    failures: list[CutOverVerdict] = []
    exempt: list[CutOverVerdict] = []
    non_mission: list[str] = []
    for slug in slugs:
        # ``slug`` is diff-derived (``touched_mission_slugs`` takes it verbatim
        # from ``parts[1]`` of a changed path), so it is untrusted input reaching
        # a filesystem sink. Guard the segment before the join and fail CLOSED on
        # a rejected one -- consistent with how every other uncertainty in this
        # loop is handled, and never silently skipped.
        try:
            assert_safe_path_segment(slug)
        except ValueError as exc:
            failures.append(
                CutOverVerdict(
                    mission_dir=corpus,
                    mission_slug=slug,
                    cut_over=False,
                    reasons=(f"unsafe mission slug in diff: {exc}",),
                )
            )
            continue
        mission_dir = corpus / slug
        if not mission_dir.is_dir():
            removed = _removed_directory_verdict(repo_root, mission_dir, slug, merge_base)
            if removed is None:
                non_mission.append(slug)
            else:
                failures.append(removed)
            continue
        try:
            verdict = is_cut_over(mission_dir)
        except Exception as exc:  # noqa: BLE001 — fail closed, never pass on uncertainty
            failures.append(
                CutOverVerdict(
                    mission_dir=mission_dir,
                    mission_slug=slug,
                    cut_over=False,
                    reasons=(f"guard evaluation errored: {exc}",),
                )
            )
            continue
        if not verdict.cut_over:
            failures.append(verdict)
        elif verdict.exempt:
            exempt.append(verdict)

    return GuardVerdict(
        passed=not failures,
        touched_slugs=slugs,
        failures=tuple(failures),
        non_mission_slugs=tuple(non_mission),
        exempt=tuple(exempt),
    )


def remedy_command(slug: str) -> str:
    """The exact FR-003 remedy command for an un-cut-over mission *slug*."""
    return _REMEDY_TEMPLATE.format(slug=slug)


def remedy_for(verdict: CutOverVerdict) -> str:
    """The reason-specific remedy for a failing *verdict* (FR-007).

    Maps the first reason; anything unrecognised keeps the backfill remedy.
    """
    template = _REMEDY_BY_REASON.get(verdict.reasons[0] if verdict.reasons else "")
    if template is None:
        return remedy_command(verdict.mission_slug)
    return template.format(slug=verdict.mission_slug)


def _error(message: str) -> None:
    err_console.print(f"[red]Error:[/red] {message}")


def _print_report(verdict: GuardVerdict) -> None:
    console.print("\n[bold]cutover-guard report[/bold]")
    console.print(f"  Missions touched by diff : {len(verdict.touched_slugs)}")
    console.print(f"  Pre-accept (exempt)      : {len(verdict.exempt)}")
    console.print(f"  Un-cut-over              : {len(verdict.failures)}")
    if verdict.non_mission_slugs:
        console.print(f"  Removed non-mission dirs : {', '.join(verdict.non_mission_slugs)}")

    if not verdict.touched_slugs:
        console.print("\n[green]No kitty-specs/ missions touched by this diff.[/green]")
        return

    _print_exempt(verdict)

    if verdict.passed:
        console.print("\n[green]All diff-touched Missions pass the cut-over check.[/green]")
        return

    console.print("\n[red]Un-cut-over Mission(s) block this diff:[/red]")
    for failure in verdict.failures:
        reason = "; ".join(failure.reasons) or "not cut over"
        console.print(f"  [red]{failure.mission_slug}[/red]: {reason}")
        console.print(f"    remedy: {remedy_for(failure)}")


def _print_exempt(verdict: GuardVerdict) -> None:
    if not verdict.exempt:
        return
    console.print("\n[bold]Pre-accept Mission(s), exempt from the stamp check:[/bold]")
    for exempt in verdict.exempt:
        console.print(f"  {exempt.mission_slug}: {PRE_ACCEPT_EXEMPT_NOTE}")


def _payload(verdict: GuardVerdict) -> dict[str, object]:
    return {
        "passed": verdict.passed,
        "touched_slugs": list(verdict.touched_slugs),
        "non_mission_slugs": list(verdict.non_mission_slugs),
        "failures": [
            {
                "slug": failure.mission_slug,
                "reasons": list(failure.reasons),
                "remedy": remedy_for(failure),
            }
            for failure in verdict.failures
        ],
        "exempt": [{"slug": item.mission_slug, "reasons": list(item.reasons)} for item in verdict.exempt],
    }


def cutover_guard(
    base_ref: Annotated[
        str | None,
        typer.Option(
            "--base-ref",
            help=("Diff HEAD against the merge-base with this ref to discover touched kitty-specs/<mission> paths (e.g. origin/main)."),
        ),
    ] = None,
    paths_from: Annotated[
        Path | None,
        typer.Option(
            "--paths-from",
            help=(
                "Read already-known changed paths from this file (one per "
                "line) instead of running git diff. Use when the CI host "
                "already provides the diff (e.g. a PR file list)."
            ),
            metavar="PATH",
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit the guard verdict as structured JSON."),
    ] = False,
) -> None:
    """Fail closed unless every kitty-specs/ mission touched by this diff is cut over.

    Exactly one of ``--base-ref`` / ``--paths-from`` must be given — a diff
    the guard cannot determine is treated the same as an un-cut-over mission
    (never pass on uncertainty).

    Examples:

        spec-kitty cutover-guard --base-ref origin/main

        spec-kitty cutover-guard --paths-from changed-files.txt --json
    """
    if (base_ref is None) == (paths_from is None):
        _error("exactly one of --base-ref or --paths-from is required.")
        raise typer.Exit(1)

    repo_root = locate_project_root()
    if repo_root is None:
        _error("Could not locate project root. No .kittify/ directory found in any parent directory.")
        raise typer.Exit(1)

    merge_base: str | None = None
    if paths_from is not None:
        try:
            text = paths_from.read_text(encoding="utf-8")
        except OSError as exc:
            _error(f"could not read --paths-from file {paths_from}: {exc}")
            raise typer.Exit(1) from exc
        changed_paths = [line.strip() for line in text.splitlines() if line.strip()]
    else:
        assert base_ref is not None  # narrowed by the exactly-one-of check above
        try:
            scope = changed_paths_from_git(repo_root, base_ref)
        except CutoverGuardError as exc:
            _error(str(exc))
            raise typer.Exit(1) from exc
        changed_paths = list(scope.paths)
        merge_base = scope.merge_base

    verdict = evaluate_touched_missions(repo_root, changed_paths, merge_base=merge_base)

    if json_output:
        print(json.dumps(_payload(verdict), indent=2))
    else:
        _print_report(verdict)

    if not verdict.passed:
        raise typer.Exit(1)
