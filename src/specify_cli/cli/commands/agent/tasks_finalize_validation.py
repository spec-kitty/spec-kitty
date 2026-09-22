"""Dependency/cycle validation, lane-metadata helpers, and the validation
core of ``finalize_tasks``.

Behaviour-preserving seam extracted from ``tasks.py`` (issue #2058, WP04).
This module owns:

* the lane-metadata helpers (``_is_backward_transition``,
  ``_lane_targets_for_emit``, ``_wp_lane_from_status_events``,
  ``_read_transactional_wp_lane``), moved verbatim; and
* the dependency-graph validation core of ``finalize_tasks`` — WP coverage,
  cycle detection, the *disagree-loud* dependency-conflict detection, and the
  frontmatter-update computation — exposed as **pure** functions that take
  explicit inputs (parsed deps / tasks_dir / existing frontmatter) and return
  results, so they are testable without the CLI.

One-way import rule (INV-2): this module MUST NOT import from
``specify_cli.cli.commands.agent.tasks``. ``tasks.py`` imports from here. It may
import from ``tasks_outline``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re

from specify_cli.coordination.status_transition import read_events_transactional
from specify_cli.core.owned_mission import effective_root_kwargs
from specify_cli.status import (
    Lane,
    StatusEvent,
    WPMetadata,
    read_wp_frontmatter,
    resolve_lane_alias,
)

# ---------------------------------------------------------------------------
# WP01: Backward transition detection (lane-metadata helpers, moved verbatim)
# ---------------------------------------------------------------------------
# Canonical forward progression of work-package lanes. A move from lane X to
# lane Y is "backward" iff both lanes are in this list and Y precedes X. Lanes
# outside this list (blocked, canceled) are not part of the directional axis
# and are never classified as backward by `_is_backward_transition`.
_FORWARD_ORDER: list[str] = [
    Lane.PLANNED,
    Lane.CLAIMED,
    Lane.IN_PROGRESS,
    Lane.FOR_REVIEW,
    Lane.IN_REVIEW,
    Lane.APPROVED,
    Lane.DONE,
]


def _is_backward_transition(current_lane: str, target_lane: str) -> bool:
    """Return True iff target precedes current in the canonical forward order.

    Purely directional: terminal-lane exit semantics (e.g. leaving ``done``)
    are enforced upstream by ``validate_transition``; this helper does not
    re-impose them. Lanes outside ``_FORWARD_ORDER`` (``blocked``,
    ``canceled``) always return False.
    """
    c = resolve_lane_alias(current_lane)
    t = resolve_lane_alias(target_lane)
    if c not in _FORWARD_ORDER or t not in _FORWARD_ORDER:
        return False
    return _FORWARD_ORDER.index(t) < _FORWARD_ORDER.index(c)


def _lane_targets_for_emit(current_lane: str, requested_lane: str) -> list[str]:
    """Return forward intermediate lane hops from current to requested lane."""
    current = resolve_lane_alias(current_lane)
    target = resolve_lane_alias(requested_lane)
    if current in _FORWARD_ORDER and target in _FORWARD_ORDER:
        current_idx = _FORWARD_ORDER.index(current)
        target_idx = _FORWARD_ORDER.index(target)
        if target_idx > current_idx:
            return _FORWARD_ORDER[current_idx + 1 : target_idx + 1]
    return [target]


def _wp_lane_from_status_events(events: list[StatusEvent], wp_id: str) -> Lane:
    """Return a WP's current lane from canonical status events."""
    if not events:
        return Lane.GENESIS
    from specify_cli.status import reduce as _reduce_status_events

    snapshot = _reduce_status_events(events)
    state = snapshot.work_packages.get(wp_id)
    if not state:
        return Lane.GENESIS
    return Lane(state.get("lane", Lane.GENESIS))


def _read_transactional_wp_lane(
    *,
    feature_dir: Path,
    mission_slug: str,
    wp_id: str,
    repo_root: Path,
    effective_root: Path | None = None,
) -> Lane:
    """Read the WP lane from the same status target transactional writes use."""
    return _wp_lane_from_status_events(
        read_events_transactional(
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            repo_root=repo_root,
            **effective_root_kwargs(effective_root),
        ),
        wp_id,
    )


# ---------------------------------------------------------------------------
# WP04: finalize_tasks dependency-graph validation core (pure functions)
# ---------------------------------------------------------------------------

# A bare ``WP##`` work-package id (two digits). Used to identify WP files in the
# tasks directory by their filename stem prefix.
_WP_ID_PATTERN = r"^WP\d{2}$"


@dataclass(frozen=True)
class CoverageResult:
    """WP-coverage check between parsed tasks.md sections and WP files.

    ``ok`` is True only when every WP file is matched by a parsed section and
    no parsed section lacks a WP file.
    """

    expected_wp_ids: list[str]
    missing_wp_sections: list[str]
    extra_wp_sections: list[str]

    @property
    def ok(self) -> bool:
        return not self.missing_wp_sections and not self.extra_wp_sections


@dataclass
class FrontmatterUpdatePlan:
    """Computed (pure) plan for updating WP frontmatter dependencies.

    Side-effect-free: ``writes`` lists the files that must be rewritten with
    new dependency values; the caller performs (or, in validate-only mode,
    skips) the actual writes. Bookkeeping mirrors the legacy inline loop.

    ``effective_dependencies`` (#4890) is the EFFECTIVE PERSISTED graph: for
    every WP this plan resolved, the dependency list that will actually be on
    disk once the plan's writes are applied -- tasks.md-parsed deps for a WP
    the parser found something for, or the PRESERVED existing frontmatter
    deps for a WP the parser found nothing for. Callers must validate this
    map (not the raw tasks.md-parsed map) before applying any write, since a
    cycle/self-ref/unknown-WP can live entirely in preserved frontmatter.
    """

    writes: list[FrontmatterWrite] = field(default_factory=list)
    modified_wps: list[str] = field(default_factory=list)
    unchanged_wps: list[str] = field(default_factory=list)
    preserved_wps: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    effective_dependencies: dict[str, list[str]] = field(default_factory=dict)

    @property
    def updated_count(self) -> int:
        return len(self.writes)


@dataclass(frozen=True)
class FrontmatterWrite:
    """A single resolved frontmatter rewrite: file + new metadata + body."""

    wp_id: str
    wp_file: Path
    updated_meta: WPMetadata
    body: str
    dependencies: list[str]


def _is_wp_id(candidate: str) -> bool:
    return bool(re.match(_WP_ID_PATTERN, candidate))


def _wp_id_from_file(wp_file: Path) -> str:
    return wp_file.stem.split("-")[0]


def compute_expected_wp_ids(tasks_dir: Path) -> list[str]:
    """Return the sorted set of ``WP##`` ids that own a file in *tasks_dir*."""
    return sorted(_wp_id_from_file(wp_file) for wp_file in tasks_dir.glob("WP*.md") if _is_wp_id(_wp_id_from_file(wp_file)))


def validate_wp_coverage(dependencies_map: dict[str, list[str]], tasks_dir: Path) -> CoverageResult:
    """Check that parsed tasks.md WP sections match the WP files on disk.

    Behaviour preserved from the inline ``finalize_tasks`` coverage check: a WP
    file with no parsed section is *missing*; a parsed section with no WP file
    is *extra*. Either makes dependency lanes unreliable.
    """
    expected_wp_ids = compute_expected_wp_ids(tasks_dir)
    missing_wp_sections = [wp_id for wp_id in expected_wp_ids if wp_id not in dependencies_map]
    extra_wp_sections = sorted(set(dependencies_map) - set(expected_wp_ids))
    return CoverageResult(
        expected_wp_ids=expected_wp_ids,
        missing_wp_sections=missing_wp_sections,
        extra_wp_sections=extra_wp_sections,
    )


def detect_dependency_cycles(
    dependencies_map: dict[str, list[str]],
) -> list[list[str]] | None:
    """Return circular dependency chains, or ``None``/empty when acyclic."""
    from specify_cli.core.dependency_graph import detect_cycles

    cycles: list[list[str]] | None = detect_cycles(dependencies_map)
    return cycles


def read_existing_frontmatter(tasks_dir: Path) -> dict[str, WPMetadata]:
    """Read existing WP frontmatter for conflict detection (T004).

    Unreadable files fall back to a minimal ``WPMetadata`` so conflict
    detection still has an entry — matching the legacy inline behaviour.
    """
    existing_frontmatter: dict[str, WPMetadata] = {}
    for wp_file in tasks_dir.glob("WP*.md"):
        wp_id = _wp_id_from_file(wp_file)
        if not _is_wp_id(wp_id):
            continue
        try:
            fm_meta, _ = read_wp_frontmatter(wp_file)
            existing_frontmatter[wp_id] = fm_meta
        except Exception:
            existing_frontmatter[wp_id] = WPMetadata(work_package_id=wp_id, title=wp_id)
    return existing_frontmatter


def detect_dependency_conflicts(
    dependencies_map: dict[str, list[str]],
    existing_frontmatter: dict[str, WPMetadata],
) -> list[str]:
    """Return *disagree-loud* dependency-conflict messages (T004).

    Precedence guarantee for FR-302/FR-303: when frontmatter already declares
    explicit dependencies AND the parser also finds deps but they disagree, we
    surface the conflict loudly instead of silently overwriting frontmatter.
    This is intentional — the operator must resolve the disagreement before
    finalizing.  The preserve-existing path (when the parser finds nothing) is
    also part of this guarantee and is handled in
    ``compute_wp_frontmatter_updates``.
    """
    dep_conflict_errors: list[str] = []
    for wp_id_chk, parsed_deps in dependencies_map.items():
        existing_meta = existing_frontmatter.get(wp_id_chk, WPMetadata(work_package_id=wp_id_chk, title=wp_id_chk))
        existing_deps: list[str] = list(existing_meta.dependencies)
        if existing_deps and parsed_deps and set(existing_deps) != set(parsed_deps):
            dep_conflict_errors.append(
                f"{wp_id_chk}: frontmatter has {sorted(existing_deps)}, "
                f"tasks.md parsed {sorted(parsed_deps)}. "
                f"Resolve the disagreement in tasks.md or WP frontmatter before finalizing."
            )
    return dep_conflict_errors


def compute_wp_frontmatter_updates(dependencies_map: dict[str, list[str]], tasks_dir: Path) -> FrontmatterUpdatePlan:
    """Compute (side-effect-free) the frontmatter rewrites finalize needs.

    Mirrors the legacy inline write loop (T004/T005) without performing any
    file writes:

    * Resolve each WP's deps, preserving existing frontmatter deps when the
      parser found none (preserve-existing path).
    * A changed dependency list produces a ``FrontmatterWrite``; unchanged WPs
      are recorded as unchanged. Missing/unreadable files emit a warning and
      are skipped — exactly as the original loop did.

    The caller decides whether to actually write (live) or skip (validate-only).
    """
    plan = FrontmatterUpdatePlan()
    for wp_id, parsed_deps in sorted(dependencies_map.items()):
        wp_files = list(tasks_dir.glob(f"{wp_id}-*.md")) + list(tasks_dir.glob(f"{wp_id}.md"))
        if not wp_files:
            plan.warnings.append(f"No file found for {wp_id}")
            continue

        wp_file = wp_files[0]
        try:
            wp_meta, body = read_wp_frontmatter(wp_file)
        except Exception as e:
            plan.warnings.append(f"Could not read {wp_file.name}: {e}")
            continue

        existing_deps = list(wp_meta.dependencies)
        if not parsed_deps and existing_deps:
            # Parser found nothing but frontmatter has deps — preserve existing.
            deps = existing_deps
            plan.preserved_wps.append(wp_id)
        else:
            deps = parsed_deps

        # #4890: record the EFFECTIVE persisted value for every resolved WP,
        # not just the ones whose deps changed — a cycle/self-ref/unknown-WP
        # hiding in a PRESERVED (unchanged) frontmatter value must still be
        # visible to the caller's pre-write graph validation.
        plan.effective_dependencies[wp_id] = deps

        old_deps_list = list(wp_meta.dependencies)
        deps_changed = old_deps_list != deps

        if deps_changed:
            updated_meta = wp_meta.update(dependencies=deps)
            plan.writes.append(
                FrontmatterWrite(
                    wp_id=wp_id,
                    wp_file=wp_file,
                    updated_meta=updated_meta,
                    body=body,
                    dependencies=deps,
                )
            )
            if wp_id not in plan.preserved_wps:
                plan.modified_wps.append(wp_id)
        else:
            if wp_id not in plan.preserved_wps:
                plan.unchanged_wps.append(wp_id)
    return plan
