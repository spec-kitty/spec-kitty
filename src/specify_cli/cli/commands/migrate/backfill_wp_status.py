"""``spec-kitty migrate backfill-wp-status`` — operator surface for #5579.

The reduced status snapshot omits every WP that has no *lane* event, so a
Mission whose log never seeded some ``tasks/WP*.md`` file under-counts on every
read surface that lists WPs from the files. WP01 owns the repair
(:func:`~specify_cli.migration.backfill_runtime_state.apply_wp_status_backfill`);
this module is the thin CLI layer around it:

* resolve ``--mission`` through the canonical Mission resolver;
* load and validate the ``--evidence-manifest`` **before any write** (fail
  closed: a bad manifest or an unresolvable Mission slug exits 1, nothing is
  written);
* run the repair over the corpus (or the one Mission);
* render a human summary or a stable ``--json`` payload, and map per-Mission
  errors to exit 1.

Evidence manifest (YAML)::

    missions:
      <exact kitty-specs directory name>:
        reason: "PR #NNNN merged <date>; <why the Mission is finished>"

Terminal evidence only applies to WPs seeded in the *same* run: a WP seeded
``planned`` by an earlier run is no longer a gap, so evidence supplied later is a
silent no-op in the planner. The CLI therefore warns for every manifest entry
that had nothing to seed, and the help states the manifest must be complete on
the first live run.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from rich.markup import escape
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from specify_cli.cli.console import console
from specify_cli.context.mission_resolver import (
    AmbiguousHandleError,
    MissionNotFoundError,
    list_missions_for_selection,
    resolve_mission,
)
from specify_cli.migration.backfill_runtime_state import (
    WpStatusBackfillResult,
    apply_wp_status_backfill_repo,
)
from specify_cli.migration.wp_status_backfill import COORD_SURFACE_LIVE, COORD_SURFACE_LIVE_MESSAGE

#: Top-level manifest key holding the ``{slug: {reason: ...}}`` mapping.
MANIFEST_MISSIONS_KEY = "missions"
#: The only key an entry may carry.
MANIFEST_REASON_KEY = "reason"

#: ``manifest.unused[].reason`` values (stable JSON vocabulary).
UNUSED_NOT_IN_SCOPE = "not in scope"
UNUSED_NOTHING_TO_SEED = "nothing to seed"
UNUSED_COORD_SURFACE_LIVE = "coordination surface live"

#: JSON ``result`` values.
RESULT_SUCCESS = "success"
RESULT_ERRORS = "errors_present"

#: Error codes of the fail-closed envelope ``{"success": false, "error_code", "error"}``.
ERR_MANIFEST_INVALID = "EVIDENCE_MANIFEST_INVALID"
ERR_MANIFEST_UNREADABLE = "EVIDENCE_MANIFEST_UNREADABLE"
ERR_MISSION_NOT_FOUND = "MISSION_NOT_FOUND"
ERR_MISSION_AMBIGUOUS = "MISSION_AMBIGUOUS"
ERR_BAD_SELECTOR = "MISSION_SELECTOR_REJECTED"

#: Appended to every unused-manifest warning: why a late manifest does nothing.
_COMPLETE_FIRST_RUN_NOTE = (
    "Terminal evidence only applies to WPs seeded in the same run; WPs a previous run seeded `planned` "
    "are not driven to done later. The evidence manifest must be complete on the first live run."
)


class BackfillWpStatusError(Exception):
    """A fail-closed CLI error raised before any write; maps to exit 1."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# ---------------------------------------------------------------------------
# Evidence manifest (T008)
# ---------------------------------------------------------------------------


def _entry_problems(slug: object, entry: object) -> list[str]:
    """Return every reason *slug* / *entry* is not a valid manifest row."""
    if not isinstance(slug, str) or not slug.strip():
        return [f"Mission key {slug!r} must be a non-empty string (the exact kitty-specs directory name)"]
    if not isinstance(entry, Mapping):
        return [f"{slug}: entry must be a mapping with a {MANIFEST_REASON_KEY!r} key"]
    problems = [f"{slug}: unknown key {key!r} (only {MANIFEST_REASON_KEY!r} is allowed)" for key in entry if key != MANIFEST_REASON_KEY]
    reason = entry.get(MANIFEST_REASON_KEY)
    if not isinstance(reason, str) or not reason.strip():
        problems.append(f"{slug}: {MANIFEST_REASON_KEY!r} is required and must be a non-empty string")
    return problems


def parse_evidence_manifest(data: object) -> dict[str, str]:
    """Validate a loaded manifest document and return ``{slug: reason}``.

    Every problem is collected so the operator can fix the file in one pass.

    Raises:
        BackfillWpStatusError: the document is not a ``missions:`` mapping of
            ``{slug: {reason: <non-empty text>}}``.
    """
    if not isinstance(data, Mapping):
        raise BackfillWpStatusError(ERR_MANIFEST_INVALID, f"Evidence manifest must be a mapping with a {MANIFEST_MISSIONS_KEY!r} key")
    problems = [f"unknown top-level key {key!r} (only {MANIFEST_MISSIONS_KEY!r} is allowed)" for key in data if key != MANIFEST_MISSIONS_KEY]
    missions = data.get(MANIFEST_MISSIONS_KEY)
    if not isinstance(missions, Mapping):
        problems.append(f"{MANIFEST_MISSIONS_KEY!r} must be a mapping of Mission slug to {{{MANIFEST_REASON_KEY}: <text>}}")
        missions = {}
    manifest: dict[str, str] = {}
    for slug, entry in missions.items():
        found = _entry_problems(slug, entry)
        problems.extend(found)
        if not found:
            manifest[slug] = str(entry[MANIFEST_REASON_KEY]).strip()
    if problems:
        raise BackfillWpStatusError(ERR_MANIFEST_INVALID, "Invalid evidence manifest: " + "; ".join(problems))
    return manifest


def load_evidence_manifest(path: Path) -> dict[str, str]:
    """Read and validate the evidence manifest at *path*.

    Raises:
        BackfillWpStatusError: unreadable file, invalid YAML, or invalid shape.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise BackfillWpStatusError(ERR_MANIFEST_UNREADABLE, f"Cannot read evidence manifest {path}: {exc}") from exc
    try:
        data = YAML(typ="safe").load(text)
    except YAMLError as exc:
        raise BackfillWpStatusError(ERR_MANIFEST_INVALID, f"Evidence manifest {path} is not valid YAML: {exc}") from exc
    return parse_evidence_manifest(data)


def check_manifest_slugs(manifest: Mapping[str, str], known_slugs: Sequence[str]) -> None:
    """Refuse a manifest naming a Mission directory that does not exist.

    The planner keys the manifest on the Mission directory name, so only exact
    names can ever take effect; a typo would otherwise be a silent no-op.

    Raises:
        BackfillWpStatusError: at least one slug is not a ``kitty-specs/`` Mission.
    """
    unknown = sorted(set(manifest) - set(known_slugs))
    if unknown:
        raise BackfillWpStatusError(
            ERR_MANIFEST_INVALID,
            f"Evidence manifest names Mission(s) that do not resolve: {', '.join(unknown)}. Use the exact kitty-specs directory name.",
        )


# ---------------------------------------------------------------------------
# Mission scope (T007)
# ---------------------------------------------------------------------------


def known_mission_slugs(repo_root: Path) -> list[str]:
    """Every ``kitty-specs/`` Mission directory name, legacy (no ``mission_id``) included."""
    return [listing.mission_slug for listing in list_missions_for_selection(repo_root)]


def resolve_scope(handle: str, repo_root: Path) -> str:
    """Resolve ``--mission`` (mission_id / mid8 / slug) to a Mission directory name.

    Goes through the canonical resolver first; a legacy Mission without a
    ``mission_id`` (which the identity resolver cannot index) still resolves by
    its exact directory name.

    Raises:
        BackfillWpStatusError: unknown or ambiguous handle.
    """
    try:
        return str(resolve_mission(handle, repo_root).mission_slug)
    except AmbiguousHandleError as exc:
        raise BackfillWpStatusError(ERR_MISSION_AMBIGUOUS, str(exc)) from exc
    except MissionNotFoundError as exc:
        if handle in known_mission_slugs(repo_root):
            return handle
        raise BackfillWpStatusError(
            ERR_MISSION_NOT_FOUND,
            f'No mission found for handle "{handle}". Check that the handle is correct and that the mission exists in kitty-specs/.',
        ) from exc


# ---------------------------------------------------------------------------
# Result aggregation / payload (T009)
# ---------------------------------------------------------------------------


def _new_events(result: WpStatusBackfillResult) -> int:
    """Events this run wrote (live) or would write (dry-run) for *result*."""
    return int(max(result.seeded, result.would_seed))


def unused_manifest_entries(manifest: Mapping[str, str], results: Sequence[WpStatusBackfillResult]) -> list[dict[str, str]]:
    """Manifest entries that cannot have driven anything to ``done`` in this run.

    ``not in scope``: the Mission was not visited (``--mission`` named another).
    ``nothing to seed``: the Mission had no WP gap — typically because an earlier
    run already seeded it ``planned``, so the evidence is a silent no-op.
    ``coordination surface live``: the Mission was refused (``COORD_SURFACE_LIVE``),
    so nothing was or could be seeded for it.
    A Mission that errored is reported as an error, not as unused.
    """
    by_slug = {result.slug: result for result in results}
    unused: list[dict[str, str]] = []
    for slug in sorted(manifest):
        result = by_slug.get(slug)
        if result is None:
            unused.append({"mission": slug, "reason": UNUSED_NOT_IN_SCOPE})
        elif result.skip_reason == COORD_SURFACE_LIVE:
            unused.append({"mission": slug, "reason": UNUSED_COORD_SURFACE_LIVE})
        elif result.error is None and _new_events(result) == 0:
            unused.append({"mission": slug, "reason": UNUSED_NOTHING_TO_SEED})
    return unused


def build_summary(results: Sequence[WpStatusBackfillResult]) -> dict[str, int]:
    """Aggregate counters. ``events_*`` count events; ``missions_*`` count Missions."""
    return {
        "scanned": len(results),
        "missions_seeded": sum(1 for r in results if r.seeded > 0),
        "missions_would_seed": sum(1 for r in results if r.would_seed > 0 and r.seeded == 0),
        "events_seeded": sum(r.seeded for r in results),
        "events_would_seed": sum(r.would_seed for r in results if r.seeded == 0),
        "finished_missions": sum(1 for r in results if r.terminal_reason is not None and _new_events(r) > 0),
        "snapshot_only_missions": sum(1 for r in results if r.snapshot_only),
        "malformed_missions": sum(1 for r in results if r.malformed),
        "coord_surface_live_missions": sum(1 for r in results if r.skip_reason == COORD_SURFACE_LIVE),
        "skipped": sum(1 for r in results if r.error is None and _new_events(r) == 0),
        "errors": sum(1 for r in results if r.error is not None),
    }


def _mission_row(result: WpStatusBackfillResult) -> dict[str, Any]:
    return {
        "slug": result.slug,
        "seeded": result.seeded,
        "would_seed": result.would_seed,
        "files_only": list(result.files_only),
        "snapshot_only": list(result.snapshot_only),
        "malformed": list(result.malformed),
        "terminal_reason": result.terminal_reason,
        "status_json_refreshed": result.status_json_refreshed,
        "skip_reason": result.skip_reason,
        "error": result.error,
    }


def build_payload(
    results: Sequence[WpStatusBackfillResult],
    *,
    dry_run: bool,
    mission: str | None,
    manifest_path: Path | None,
    manifest: Mapping[str, str],
) -> dict[str, Any]:
    """The stable ``--json`` payload (keys are pinned by ``tests/cli``)."""
    summary = build_summary(results)
    return {
        "dry_run": dry_run,
        "result": RESULT_ERRORS if summary["errors"] else RESULT_SUCCESS,
        "mission": mission,
        "summary": summary,
        "manifest": {
            "path": str(manifest_path) if manifest_path is not None else None,
            "entries": len(manifest),
            "unused": unused_manifest_entries(manifest, results),
        },
        "missions": [_mission_row(result) for result in results],
    }


# ---------------------------------------------------------------------------
# Human rendering (T009)
# ---------------------------------------------------------------------------


def _print_counters(summary: Mapping[str, int], *, dry_run: bool) -> None:
    title = "backfill-wp-status summary" + (" (dry-run)" if dry_run else "")
    console.print(f"[bold]{title}[/bold]")
    rows = (
        ("Scanned", f"{summary['scanned']} mission(s)"),
        ("Seeded", f"{summary['events_seeded']} event(s) in {summary['missions_seeded']} mission(s)"),
        ("Would seed", f"{summary['events_would_seed']} event(s) in {summary['missions_would_seed']} mission(s)"),
        ("Finished (WPs seeded -> done)", f"{summary['finished_missions']} mission(s)"),
        ("Snapshot-only WPs reported", f"{summary['snapshot_only_missions']} mission(s)"),
        ("Malformed WP files", f"{summary['malformed_missions']} mission(s)"),
        ("Refused (live coord surface)", f"{summary['coord_surface_live_missions']} mission(s)"),
        ("Skipped (nothing to seed)", str(summary["skipped"])),
        ("Errors", str(summary["errors"])),
    )
    for label, value in rows:
        console.print(f"  {label:<31}: {value}")


def _print_mission_lines(results: Sequence[WpStatusBackfillResult], *, dry_run: bool) -> None:
    verb = "would seed" if dry_run else "seeded"
    for result in results:
        if result.error is not None:
            console.print(f"  [red]error[/red] {escape(result.slug)}: {escape(result.error)}")
        elif result.skip_reason == COORD_SURFACE_LIVE:
            console.print(f"  [yellow]refused[/yellow] {escape(result.slug)}: {COORD_SURFACE_LIVE} -- {escape(COORD_SURFACE_LIVE_MESSAGE)}")
        elif _new_events(result) > 0:
            done = f" -> done ({escape(result.terminal_reason or '')})" if result.terminal_reason else ""
            console.print(f"  [green]{verb}[/green] {escape(result.slug)}: {_new_events(result)} event(s) for {', '.join(result.files_only)}{done}")
        if result.snapshot_only:
            console.print(f"  [yellow]snapshot-only[/yellow] {escape(result.slug)}: {', '.join(result.snapshot_only)} (no WP file; not repaired)")
        if result.malformed:
            console.print(f"  [yellow]malformed[/yellow] {escape(result.slug)}: {', '.join(result.malformed)} (skipped)")


def _print_unused_warnings(unused: Sequence[Mapping[str, str]]) -> None:
    for entry in unused:
        console.print(f"[yellow]WARNING:[/yellow] evidence manifest entry for {escape(entry['mission'])} had no effect ({entry['reason']}).")
    if unused:
        console.print(_COMPLETE_FIRST_RUN_NOTE)


def render_summary(payload: Mapping[str, Any], results: Sequence[WpStatusBackfillResult]) -> None:
    """Print the human summary for a completed run."""
    dry_run = bool(payload["dry_run"])
    _print_counters(payload["summary"], dry_run=dry_run)
    _print_mission_lines(results, dry_run=dry_run)
    _print_unused_warnings(payload["manifest"]["unused"])
    if dry_run:
        console.print("\n[dim]Dry run — no files were modified.[/dim]")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _emit_failure(error: BackfillWpStatusError, *, json_output: bool) -> None:
    if json_output:
        console.emit_json({"success": False, "error_code": error.code, "error": error.message})
    else:
        console.print(f"[red]Error:[/red] {escape(error.message)}")


def _prepare(repo_root: Path, mission: str | None, manifest_path: Path | None) -> tuple[str | None, dict[str, str]]:
    """Validate every input before the first write; return ``(scope, manifest)``."""
    manifest = load_evidence_manifest(manifest_path) if manifest_path is not None else {}
    check_manifest_slugs(manifest, known_mission_slugs(repo_root))
    scope = resolve_scope(mission, repo_root) if mission is not None else None
    return scope, manifest


def run_backfill_wp_status(
    repo_root: Path,
    *,
    mission: str | None,
    dry_run: bool,
    evidence_manifest: Path | None,
    json_output: bool,
) -> int:
    """Run the repair and render it; return the process exit code (0 ok, 1 error).

    Inputs are validated first (fail closed: nothing is written on a bad
    manifest, an unresolvable slug or an unknown ``--mission``). After that,
    per-Mission failures never abort the walk; any of them yields exit 1.
    """
    try:
        scope, manifest = _prepare(repo_root, mission, evidence_manifest)
        results = apply_wp_status_backfill_repo(repo_root, mission=scope, dry_run=dry_run, evidence=manifest or None)
    except BackfillWpStatusError as exc:
        _emit_failure(exc, json_output=json_output)
        return 1
    except ValueError as exc:
        _emit_failure(BackfillWpStatusError(ERR_BAD_SELECTOR, str(exc)), json_output=json_output)
        return 1

    payload = build_payload(results, dry_run=dry_run, mission=mission, manifest_path=evidence_manifest, manifest=manifest)
    if json_output:
        console.emit_json(payload)
    else:
        render_summary(payload, results)
    return 1 if payload["result"] == RESULT_ERRORS else 0
