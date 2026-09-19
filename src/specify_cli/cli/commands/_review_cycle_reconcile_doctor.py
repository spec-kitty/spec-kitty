"""``doctor review-cycle-reconcile`` sibling (WP08, FR-008, T035-T039).

Per the doctor per-subcommand-module convention (``_cutover_doctor.py`` /
``_coordination_doctor.py``): the ``review-cycle-reconcile`` ``@app.command``
shell in ``doctor.py`` stays a thin delegator; all detection/reporting logic
lives here.

**What this detects.** WP01's verdict-seam review enumerated every review-cycle
writer/resolver/reader. WP08's reviewed retirement set marks five of those
resolvers ``status: retire`` -- locations WP10's writer-atomicity rework
(FR-003), WP12's arbiter-override retirement (FR-009), and WP13's
consumer-unification (FR-007) each stop resolving once landed. Between this
WP landing and WP13's narrowing, a record already written under one of those
soon-to-be-orphaned paths must be found and reported, or the merge gate opens
a fail-open window the moment the fan-out that used to (accidentally) find it
is removed (FR-008). "Retired path" is WP01's/this WP's census call, not
re-derived here -- :data:`_RETIRED_RESOLVER_SHAPES` below is a direct
transcription of WP08's reviewed rows.

**The migration shape is exception absorption, not an empty-directory check**
(ADR ``docs/adr/3.x/2026-08-03-1-review-cycle-artifacts-are-coord-partition.md``,
"Migration: exception absorption, not empty-directory fallback"). Measured:
102 missions in this repository carry review cycles; 45 declare a
``coordination_branch`` in ``meta.json``; zero of those 45 branches still
exist in git (``spec-kitty merge`` deletes the mission branch -- the
coordination branch *is* the mission branch -- and nothing clears the stale
``meta.json`` key). Resolving ``MissionArtifactKind.REVIEW_CYCLE`` for one of
those 45 therefore raises :class:`~specify_cli.coordination.surface_resolver
.CoordinationBranchDeleted` **before any read happens**, unconditionally.
:func:`_resolve_canonical_review_cycle_dir` is the ONE owner function that
catches that exception (and the more general
:class:`~specify_cli.missions._read_path_resolver.StatusReadPathNotFound`)
and falls through to the PRIMARY feature dir -- once, here, never per
retired-resolver replica and never inside the seam itself.

**Two stranded classes, always reported distinctly (T037 / T039):**

- ``deleted_coord_branch_absorption`` -- the coordination branch declared in
  ``meta.json`` no longer exists in git (T037's measured 45-mission corpus).
  This is a *steady-state* migration case: it will exist for every merged
  coord mission until a separate ``meta.json``-flatten migration retires the
  stale key, per the ADR's own "Negative, accepted" consequences.
- ``live_coord_pre_adr_primary_record`` -- the mission's coordination branch
  is alive, and canonical ``REVIEW_CYCLE`` resolution genuinely lands on the
  coord worktree, but a record still sits on PRIMARY from before this
  mission's ADR moved review cycles onto the coord partition (the
  create-window split documented by WP04: a coord
  mission's *first* review cycle lands PRIMARY because the coord worktree
  materialises lazily at the commit boundary).

Every finding names its mission, WP, retired resolver (+ its retiring FR),
stranded class, and the resolved-fallback directory -- never a bare count
(FR-008 / this WP's own DoD). A mission with **zero** stranded records still
gets a report entry marked clean, so "0 found" is always distinguishable from
"never looked".

**Not a duplicate of ``migrate backfill-runtime-state``.** That command
(``cli/commands/migrate_cmd.py::backfill_runtime_state_cmd``, backed by
``migration/runtime_state_cutover.py``) seeds a WP's frontmatter/checkbox
*runtime state* (claim, assignee, subtask completion, override annotations)
into the event log -- a fully-shipped, unrelated corpus. It never reads or
writes a ``review-cycle-*.md`` / ``arbiter-override-*.json`` *artifact file*,
so this sibling is a genuinely distinct reconciliation target, not a second
mechanism layered over the same ground.

**Report-only.** No ``--fix``: a stranded record is evidence to surface, not
something safe to move automatically -- two divergent copies can legitimately
both exist (the two-sided ``tasks/`` hazard the ADR also names), and picking a
winner is an operator judgment call this WP does not make.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import typer

from mission_runtime import MissionArtifactKind, placement_seam
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.mission_metadata import load_meta

from ._doctor_shared import console

#: ``MissionReconciliationReport`` and ``StrandedRecordFinding`` are this
#: module's own internals (tests reach them by direct attribute access, the
#: same ``_cutover_doctor.py`` precedent) -- exporting them tripped the
#: symbol-level dead-code gate (``tests/architectural/test_no_dead_symbols.py``)
#: since nothing outside this module imports them.
__all__ = [
    "run_review_cycle_reconciliation",
]

_REVIEW_CYCLE_GLOB = "review-cycle-*.md"
_ARBITER_JSON_GLOB = "arbiter-override-*.json"
_WP_ID_RE = re.compile(r"^(WP\d+)")

#: T037 -- the coordination branch declared in ``meta.json`` no longer exists.
_DELETED_COORD_BRANCH_CLASS = "deleted_coord_branch_absorption"
#: T039 -- coord branch alive, canonical resolution is COORD, but a record
#: predating this mission's ADR still sits on PRIMARY.
_LIVE_COORD_PRE_ADR_CLASS = "live_coord_pre_adr_primary_record"

_ShapeFn = Callable[[Path, str, str], "list[Path]"]


def _shape_artifact_dirs_for_wp(
    primary_feature_dir: Path,
    wp_id: str,
    _wp_slug: str,
) -> list[Path]:
    """Replicates ``post_merge/review_artifact_consistency.py::_artifact_dirs_for_wp``
    (retired under FR-007, WP13 consumer-unification).

    Deliberately NOT calling the live function: WP13 may rewrite or delete it
    once consumer-unification lands, and this reconciliation detector must
    keep working against historical repository state independent of that.
    Mirrors its exact fan-out: the bare ``tasks/<wp_id>`` dir plus every
    ``tasks/<wp_id>-*`` sibling -- the divergence-tolerating fan-out IC-06b
    narrows to one resolved directory.
    """
    tasks_dir = primary_feature_dir / "tasks"
    if not tasks_dir.exists():
        return []
    exact = tasks_dir / wp_id
    candidates: list[Path] = [exact] if exact.is_dir() else []
    candidates.extend(sorted(p for p in tasks_dir.iterdir() if p.is_dir() and p.name.startswith(f"{wp_id}-") and p not in candidates))
    return candidates


def _shape_review_cycle_wp_dir(
    primary_feature_dir: Path,
    _wp_id: str,
    wp_slug: str,
) -> list[Path]:
    """Replicates ``review/cycle.py::_review_cycle_wp_dir`` (retired under
    FR-003, WP10's writer-atomicity rework -- ground truth: WP04's
    ``WP04-XWP-01`` cross-WP-dependency entry
    names this exact function/line as WP10's fix target).

    ``MissionArtifactKind.WORK_PACKAGE_TASK`` is PRIMARY for every topology
    (P-1) -- this resolver's OWN directory computation never changes; what
    stops resolving is the review-cycle *content* that used to be written
    here before the partition-aware ``REVIEW_CYCLE`` seam existed.
    """
    candidate = primary_feature_dir / "tasks" / wp_slug
    return [candidate] if candidate.is_dir() else []


def _shape_arbiter_bare_wp_id_dir(
    primary_feature_dir: Path,
    wp_id: str,
    _wp_slug: str,
) -> list[Path]:
    """Replicates ``review/arbiter.py``'s three bare
    ``feature_dir / "tasks" / wp_id`` joins (``_find_review_cycle_artifact``,
    ``persist_arbiter_decision``, ``get_arbiter_overrides_for_wp`` -- all
    retired under FR-009, WP12's arbiter-override retirement). None of the
    three resolve any kind/partition at all -- plan.md's IC-09 risk note:
    "the arbiter's resolver reads ``feature_dir/'tasks'/wp_id`` (bare id)" --
    so the directory is identical across all three and keyed on the BARE
    ``wp_id``, not ``wp_slug`` (the divergence IC-09 itself diagnoses).
    """
    candidate = primary_feature_dir / "tasks" / wp_id
    return [candidate] if candidate.is_dir() else []


#: T035 -- direct transcription of WP08's five reviewed
#: ``status: retire`` resolver rows: (resolver name, retiring FR, shape fn).
_RETIRED_RESOLVER_SHAPES: tuple[tuple[str, str, _ShapeFn], ...] = (
    (
        "post_merge/review_artifact_consistency.py::_artifact_dirs_for_wp",
        "FR-007",
        _shape_artifact_dirs_for_wp,
    ),
    (
        "review/cycle.py::_review_cycle_wp_dir",
        "FR-003",
        _shape_review_cycle_wp_dir,
    ),
    (
        "review/arbiter.py::_find_review_cycle_artifact",
        "FR-009",
        _shape_arbiter_bare_wp_id_dir,
    ),
    (
        "review/arbiter.py::persist_arbiter_decision",
        "FR-009",
        _shape_arbiter_bare_wp_id_dir,
    ),
    (
        "review/arbiter.py::get_arbiter_overrides_for_wp",
        "FR-009",
        _shape_arbiter_bare_wp_id_dir,
    ),
)


@dataclass(frozen=True)
class StrandedRecordFinding:
    """One stranded review-cycle / arbiter-override record (T035 shape)."""

    mission_slug: str
    wp_id: str
    retired_resolver: str
    retiring_fr: str
    stranded_class: str
    resolved_directory: str
    record_paths: list[str] = field(default_factory=list)


@dataclass
class MissionReconciliationReport:
    """One mission's reconciliation result -- emitted even when clean.

    ``stranded_class`` is ``None`` for a mission with nothing to reconcile (a
    non-coord topology, or canonical resolution already lands on PRIMARY);
    such missions are not surfaced as findings at all (see
    :func:`_collect_reports`), matching "nothing to report" rather than
    "reported clean" -- reserving the clean/non-clean distinction for missions
    that DO carry one of the two stranded classes.
    """

    mission_slug: str
    stranded_class: str | None
    findings: list[StrandedRecordFinding] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.findings


def _primary_feature_dir(repo_root: Path, mission_slug: str) -> Path:
    """Resolve the PRIMARY ``kitty-specs/<mission_slug>`` dir through the
    kind-AWARE placement seam, never a kind-blind bypass
    (``tests/architectural/test_no_read_side_bypass.py`` /
    ``test_resolution_authority_gates.py``).

    ``MissionArtifactKind.WORK_PACKAGE_TASK`` is a PRIMARY-partition kind
    (P-1): :func:`~mission_runtime.resolve_artifact_surface` resolves it to
    the primary mission dir for EVERY topology and coord state (AH-1/AH-3 --
    it never transits coordination), which is exactly the PRIMARY anchor this
    detector needs -- resolved through the SAME seam
    :func:`_resolve_canonical_review_cycle_dir` uses for ``REVIEW_CYCLE``,
    not a second, ad-hoc ``KITTY_SPECS_DIR`` join.
    """
    primary_dir: Path = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)
    return primary_dir


def _resolve_canonical_review_cycle_dir(
    repo_root: Path,
    mission_slug: str,
    primary_feature_dir: Path,
) -> tuple[Path, str | None]:
    """T035's ONE owner function: resolve ``REVIEW_CYCLE``'s canonical read
    dir, absorbing ``CoordinationBranchDeleted`` / ``StatusReadPathNotFound``
    to PRIMARY -- exactly once, here, never per retired-resolver shape and
    never inside the seam itself (ADR's "exception absorption, not
    empty-directory fallback" migration rule).

    Returns ``(resolved_dir, stranded_class)`` -- see the module docstring for
    the two ``stranded_class`` values, or ``None`` when canonical resolution
    already lands on PRIMARY (nothing left to reconcile for this mission).
    """
    # Function-local: avoids a module-load cycle between the doctor cluster
    # and coordination/missions modules (H2/I-6 precedent, ``_coordination_doctor.py``).
    from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted
    from specify_cli.missions._read_path_resolver import StatusReadPathNotFound

    try:
        resolved = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.REVIEW_CYCLE)
    except (CoordinationBranchDeleted, StatusReadPathNotFound):
        return primary_feature_dir, _DELETED_COORD_BRANCH_CLASS

    try:
        same_dir = resolved.resolve() == primary_feature_dir.resolve()
    except OSError:
        same_dir = resolved == primary_feature_dir
    if same_dir:
        return resolved, None
    return resolved, _LIVE_COORD_PRE_ADR_CLASS


def _wp_ids_under_tasks(primary_feature_dir: Path) -> list[tuple[str, str]]:
    """Return ``(wp_id, wp_slug)`` pairs for every WP subdirectory under
    ``tasks/`` -- ``wp_slug`` is the on-disk directory name (identical to
    ``wp_id`` when the directory itself is the bare id)."""
    tasks_dir = primary_feature_dir / "tasks"
    if not tasks_dir.exists():
        return []
    pairs: list[tuple[str, str]] = []
    for candidate in sorted(tasks_dir.iterdir()):
        if not candidate.is_dir():
            continue
        match = _WP_ID_RE.match(candidate.name)
        if match is None:
            continue
        pairs.append((match.group(1), candidate.name))
    return pairs


def _records_at(candidate_dir: Path) -> list[Path]:
    records = sorted(candidate_dir.glob(_REVIEW_CYCLE_GLOB))
    records.extend(sorted(candidate_dir.glob(_ARBITER_JSON_GLOB)))
    return records


def _findings_for_wp(
    *,
    mission_slug: str,
    wp_id: str,
    wp_slug: str,
    primary_feature_dir: Path,
    stranded_class: str,
    resolved_dir: Path,
) -> list[StrandedRecordFinding]:
    """T035 detection loop for one WP: run every retired-resolver shape and
    emit a finding for each candidate directory that still carries a record."""
    findings: list[StrandedRecordFinding] = []
    for resolver_name, retiring_fr, compute in _RETIRED_RESOLVER_SHAPES:
        for candidate_dir in compute(primary_feature_dir, wp_id, wp_slug):
            records = _records_at(candidate_dir)
            if not records:
                continue
            findings.append(
                StrandedRecordFinding(
                    mission_slug=mission_slug,
                    wp_id=wp_id,
                    retired_resolver=resolver_name,
                    retiring_fr=retiring_fr,
                    stranded_class=stranded_class,
                    resolved_directory=str(resolved_dir),
                    record_paths=[str(p) for p in records],
                )
            )
    return findings


def _report_for_mission(
    repo_root: Path,
    mission_dir: Path,
) -> MissionReconciliationReport | None:
    """Return this mission's report, or ``None`` when it has nothing to
    reconcile (unreadable ``meta.json``, or canonical resolution already
    lands on PRIMARY)."""
    mission_slug = mission_dir.name
    meta = load_meta(mission_dir, on_malformed="none")
    if meta is None:
        return None

    primary_feature_dir = _primary_feature_dir(repo_root, mission_slug)
    resolved_dir, stranded_class = _resolve_canonical_review_cycle_dir(
        repo_root,
        mission_slug,
        primary_feature_dir,
    )
    if stranded_class is None:
        return None

    findings: list[StrandedRecordFinding] = []
    for wp_id, wp_slug in _wp_ids_under_tasks(primary_feature_dir):
        findings.extend(
            _findings_for_wp(
                mission_slug=mission_slug,
                wp_id=wp_id,
                wp_slug=wp_slug,
                primary_feature_dir=primary_feature_dir,
                stranded_class=stranded_class,
                resolved_dir=resolved_dir,
            )
        )
    return MissionReconciliationReport(
        mission_slug=mission_slug,
        stranded_class=stranded_class,
        findings=findings,
    )


def _mission_dirs_for(
    repo_root: Path,
    mission: str | None,
    *,
    json_mode: bool = False,
) -> list[Path]:
    if mission is not None:
        # Function-local (H2/I-6 precedent): resolves --mission via the
        # canonical handle resolver (mission_id / mid8 / slug), matching
        # every other doctor/migrate subcommand's --mission behaviour.
        # #4723: tries the shared bare-modern-slug primitive first, so a
        # bare human slug matching >1 composed "<slug>-<mid8>" primary dir
        # raises the structured ambiguity error instead of the identity
        # resolver's misleading MISSION_NOT_FOUND (it has no fold for a
        # composed dir name).
        from specify_cli.cli.selector_resolution import (
            resolve_mission_dir_with_bare_modern_fold,
        )

        return [resolve_mission_dir_with_bare_modern_fold(mission, repo_root, json_mode=json_mode)]
    specs_dir = repo_root / KITTY_SPECS_DIR
    if not specs_dir.exists():
        return []
    return [p for p in sorted(specs_dir.iterdir()) if p.is_dir()]


def _collect_reports(
    repo_root: Path,
    mission: str | None,
    *,
    json_mode: bool = False,
) -> list[MissionReconciliationReport]:
    reports = (_report_for_mission(repo_root, mission_dir) for mission_dir in _mission_dirs_for(repo_root, mission, json_mode=json_mode))
    return [report for report in reports if report is not None]


def _emit_human(reports: list[MissionReconciliationReport]) -> None:
    if not reports:
        console.print("[green]ok[/green]: no coordination-topology review-cycle mission needs reconciliation.")
        return
    for report in reports:
        if report.clean:
            console.print(f"[green]ok[/green]: {report.mission_slug} ({report.stranded_class}) -- no stranded records found.")
            continue
        for finding in report.findings:
            console.print(
                f"[yellow]warning[/yellow]: {finding.mission_slug} {finding.wp_id} -- "
                f"{len(finding.record_paths)} record(s) stranded under "
                f"{finding.retired_resolver} (retired by {finding.retiring_fr}, "
                f"class={finding.stranded_class}); canonical directory is now "
                f"{finding.resolved_directory}"
            )
            for path in finding.record_paths:
                console.print(f"    -> {path}")


def _emit_json(reports: list[MissionReconciliationReport]) -> None:
    payload = [
        {
            "mission_slug": report.mission_slug,
            "stranded_class": report.stranded_class,
            "clean": report.clean,
            "findings": [
                {
                    "mission_slug": finding.mission_slug,
                    "wp_id": finding.wp_id,
                    "retired_resolver": finding.retired_resolver,
                    "retiring_fr": finding.retiring_fr,
                    "stranded_class": finding.stranded_class,
                    "resolved_directory": finding.resolved_directory,
                    "record_paths": finding.record_paths,
                }
                for finding in report.findings
            ],
        }
        for report in reports
    ]
    console.print_json(json.dumps(payload, indent=2))


def run_review_cycle_reconciliation(
    repo_root: Path,
    *,
    json_output: bool,
    mission: str | None = None,
) -> None:
    """Entry point for ``doctor review-cycle-reconcile`` (FR-008, T035-T039).

    Reports, never silently drops, every stranded review-cycle /
    arbiter-override record living under a path WP08 marks for retirement --
    across both
    stranded classes (T037's deleted-coord-branch absorption, T039's
    live-coord-branch pre-ADR PRIMARY record), independently classified per
    finding, never conflated.

    Informational only, matching the ``doctor cutover`` precedent (WP05):
    always exits 0. This reconciliation surfaces evidence for an operator or a
    later WP's merge-gate check to act on; it does not itself gate anything,
    and carries no ``--fix`` (see module docstring: a stranded record may
    legitimately have a divergent sibling, and picking a winner is not this
    WP's call to make automatically).
    """
    reports = _collect_reports(repo_root, mission, json_mode=json_output)
    if json_output:
        _emit_json(reports)
    else:
        _emit_human(reports)
    raise typer.Exit(0)
