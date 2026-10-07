"""Audit engine: scan loop, classifier dispatch, repo-level findings, report assembly.

This module is the integration point for the read-only mission-state audit.  It:

1. Discovers mission directories under ``scan_root`` in lexicographic order.
2. Dispatches the 7 per-artifact classifiers for each mission.
3. Calls ``audit_repo()`` once and indexes ``IdentityState`` results by slug.
4. Calls ``find_duplicate_prefixes()`` and ``find_ambiguous_selectors()`` for
   repo-level findings.
5. Sorts findings by ``(artifact_path, code)`` within each mission.
6. Assembles ``RepoAuditReport`` with sorted missions and shape counters.

Determinism contract (D4):
- Missions processed in ``sorted(..., key=lambda p: p.name)`` order.
- Findings sorted by ``(artifact_path, code)`` before constructing ``MissionAuditResult``.
- ``json.dumps(sort_keys=True, indent=2)`` — enforced by ``serializer.py``.
- No timestamps, PIDs, or wall-clock values in output.
- ``shape_counters`` built with ``collections.Counter``, serialised with sorted keys.
"""

from __future__ import annotations

from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.utils import safe_is_dir
from collections import Counter
from pathlib import Path
from typing import Any

from specify_cli.context.mission_resolver import (
    AmbiguousHandleError,  # noqa: F401  (re-exported for CLI callers via engine)
    MissionNotFoundError,  # noqa: F401
    is_mission_dir,
    resolve_mission,
    tracked_mission_paths,
)
from specify_cli.status import IdentityState, audit_repo, find_ambiguous_selectors, find_duplicate_prefixes

from .classifiers.decisions_events import classify_decisions_events_jsonl
from .classifiers.handoff_events import classify_handoff_events_jsonl
from .classifiers.meta import classify_meta_json
from .classifiers.mission_events import classify_mission_events_jsonl
from .classifiers.status_events import classify_status_events_jsonl
from .classifiers.status_json import classify_status_json
from .classifiers.wp_files import classify_wp_files
from .identity_adapter import (
    identity_state_to_findings,
)
from .models import (
    AuditOptions,
    MissionAuditResult,
    MissionFinding,
    RESIDUE_DIRECTORY,
    RepoAuditReport,
    Severity,
    is_teamspace_blocker,
)

_META_JSON = "meta.json"


# ---------------------------------------------------------------------------
# Private: mission filter resolution
# ---------------------------------------------------------------------------


def _resolve_mission_filter(
    handle: str | None,
    repo_root: Path,
    scan_root: Path,
) -> frozenset[Path] | None:
    """Return the set of allowed directories for ``--mission`` scoping, or None for all.

    If *handle* is None, returns None — meaning all missions are scanned.

    If *handle* is provided, ``resolve_mission()`` is called against *repo_root*
    (which expects ``kitty-specs/`` to live there).  If the resolved slug
    corresponds to an existing directory under *scan_root*, a singleton
    ``frozenset`` is returned.  If the candidate directory is absent under
    *scan_root* (e.g. fixture-dir mode with a missing mission), an empty
    ``frozenset`` is returned so the scan yields an empty report.

    Raises:
        AmbiguousHandleError: The handle matches more than one mission.
        MissionNotFoundError: The handle matches no mission.

    Note: these exceptions propagate up to the CLI layer, which formats them
    as structured errors.
    """
    if handle is None:
        return None  # no filter: scan everything

    resolved = resolve_mission(handle, repo_root)
    candidate = scan_root / resolved.mission_slug
    if safe_is_dir(candidate):
        return frozenset({candidate})
    # Candidate not found under scan_root (fixture-dir mismatch).
    return frozenset()


# ---------------------------------------------------------------------------
# Private: per-mission scan loop
# ---------------------------------------------------------------------------


def _scan_missions(
    scan_root: Path,
    allowed_dirs: frozenset[Path] | None,
    identity_index: dict[str, Any],
    repo_root: Path | None = None,
) -> list[MissionAuditResult]:
    """Walk *scan_root* and classify each mission directory.

    Args:
        scan_root: Directory to walk (usually ``repo_root / KITTY_SPECS_DIR``).
        allowed_dirs: When not None, only directories in this set are processed.
            Pass ``frozenset()`` to produce an empty scan result.
        identity_index: Mapping of ``{mission_slug: IdentityState}`` built from
            ``audit_repo()``.  Used to call ``identity_state_to_findings()``
            without re-reading ``meta.json`` for each mission.
        repo_root: When given (the default ``kitty-specs/`` scan), a directory
            that is not a Mission per :func:`is_mission_dir` gets one INFO
            ``RESIDUE_DIRECTORY`` finding and is not classified (#5812).
            ``None`` (a custom scan root such as audit fixtures) treats every
            directory as a Mission.

    Returns:
        List of :class:`~specify_cli.audit.models.MissionAuditResult`, one per
        directory, in lexicographic order of directory name.  Each result's
        findings are sorted by ``(artifact_path, code)``.
    """
    try:
        if not safe_is_dir(scan_root):
            return []
        candidates = sorted(scan_root.iterdir(), key=lambda p: p.name)
    except OSError:
        # This audit engine is read-only and best-effort: an unreadable
        # ancestor of `scan_root` (or of `scan_root` itself) must not be
        # silently reported as "no missions" via the EACCES-divergent
        # `Path.exists()` (raises on 3.11-3.13, returns False on 3.14 — see
        # `specify_cli.core.utils.safe_is_dir`), but it also should not crash
        # the whole audit for a permission hiccup on one repo. Folding the
        # `safe_is_dir` probe into the same `except OSError` this function
        # already used for `iterdir()` failures keeps both failure sources on
        # one fail-soft path instead of adding a second, differently-shaped one.
        return []

    results: list[MissionAuditResult] = []
    tracked = tracked_mission_paths(repo_root) if repo_root is not None else None

    for candidate in candidates:
        try:
            candidate_is_dir = safe_is_dir(candidate)
        except OSError:
            # Same fail-soft posture as the `scan_root` probe above: one
            # unreadable candidate must not abort the audit for every other
            # mission in the corpus, and must not silently swap "unreadable"
            # for "not a directory" the way the bare `Path.is_dir()` this
            # replaces did on 3.14 (see `safe_is_dir`'s docstring).
            continue
        if not candidate_is_dir:
            continue

        if allowed_dirs is not None and candidate not in allowed_dirs:
            continue

        if repo_root is not None and not is_mission_dir(candidate, repo_root=repo_root, tracked=tracked):
            results.append(_residue_result(candidate))
            continue

        identity_state = identity_index.get(candidate.name)

        # Collect findings from all 7 classifiers in the documented order.
        all_findings: list[MissionFinding] = []

        # 1. meta.json
        all_findings.extend(classify_meta_json(candidate))

        # 2. status.events.jsonl — returns (findings, has_corrupt_jsonl)
        findings_events, has_corrupt = classify_status_events_jsonl(candidate)
        all_findings.extend(findings_events)

        # 3. status.json — skip drift check if events are corrupt
        all_findings.extend(classify_status_json(candidate, skip_drift=has_corrupt))

        # 4. mission-events.jsonl
        all_findings.extend(classify_mission_events_jsonl(candidate))

        # 5. decisions/events.jsonl
        all_findings.extend(classify_decisions_events_jsonl(candidate))

        # 6. handoff/events.jsonl
        all_findings.extend(classify_handoff_events_jsonl(candidate))

        # 7. WP*.md frontmatter
        all_findings.extend(classify_wp_files(candidate))

        # 8. Identity-state adapter (only when identity data is available)
        if identity_state is not None:
            all_findings.extend(identity_state_to_findings(identity_state, candidate))

        # Sort by (artifact_path, code) for determinism before constructing the result.
        sorted_findings = sorted(all_findings, key=lambda f: (f.artifact_path, f.code))

        results.append(
            MissionAuditResult(
                mission_slug=candidate.name,
                mission_dir=candidate,
                findings=sorted_findings,
            )
        )

    return results


def _residue_result(candidate: Path) -> MissionAuditResult:
    """The result for a directory that is not a Mission: one non-blocking finding."""
    finding = MissionFinding(
        code=RESIDUE_DIRECTORY,
        severity=Severity.INFO,
        artifact_path=".",
        detail=(
            "directory holds no tracked spec.md or meta.json and no mission_id; not a Mission. "
            "If this is a Mission created before identity existed, run "
            "`spec-kitty migrate backfill-identity` (or commit its spec.md)"
        ),
    )
    return MissionAuditResult(mission_slug=candidate.name, mission_dir=candidate, findings=[finding])


# ---------------------------------------------------------------------------
# Private: repo-level finding computation (slug-attributed)
# ---------------------------------------------------------------------------


def _compute_repo_findings_by_slug(
    repo_root: Path,
    identity_states: list[IdentityState],
    mission_results: list[MissionAuditResult],
) -> dict[str, list[MissionFinding]]:
    """Compute cross-mission (repo-level) findings, attributed by slug.

    Calls the three repo-level identity functions and returns a dict mapping
    each mission slug to any findings that belong to that mission.

    Three sources:
    - Duplicate 3-digit numeric prefixes (``DUPLICATE_PREFIX`` warning)
    - Ambiguous selector handles (``AMBIGUOUS_SELECTOR`` warning)
    - Duplicate ``mission_id`` values (``DUPLICATE_MISSION_ID`` error)

    All three identity functions use *repo_root* (not ``scan_root``) because
    they internally append ``/kitty-specs``.

    The adapter functions each emit one finding *per member* of a duplicate
    group. We attribute each finding to the correct mission by re-running the
    adapters and tracking which state generated which finding.

    Args:
        repo_root: Repository root.
        identity_states: All ``IdentityState`` objects from ``audit_repo()``.
        mission_results: Per-mission results (used to build ``slug_to_dir``).

    Returns:
        Dict mapping ``{mission_slug: [MissionFinding, ...]}`` for all
        missions that have any repo-level findings.
    """
    prefix_groups = find_duplicate_prefixes(repo_root)
    selector_groups = find_ambiguous_selectors(identity_states)
    slug_to_dir = {r.mission_slug: r.mission_dir for r in mission_results}

    attributed: dict[str, list[MissionFinding]] = {}

    # --- DUPLICATE_PREFIX: one finding per state in each prefix group -----------
    for prefix, states in prefix_groups.items():
        if len(states) < 2:
            continue
        all_slugs = sorted(s.slug for s in states)
        for state in states:
            other_slugs = ", ".join(s for s in all_slugs if s != state.slug)
            finding = MissionFinding(
                code="DUPLICATE_PREFIX",
                severity=_slug_to_finding_severity("DUPLICATE_PREFIX"),
                artifact_path=_META_JSON,
                detail=f"prefix {prefix!r} shared with: {other_slugs}",
            )
            if state.slug in slug_to_dir:
                attributed.setdefault(state.slug, []).append(finding)

    # --- AMBIGUOUS_SELECTOR: one finding per state in each selector group -------
    for handle, states in selector_groups.items():
        if len(states) < 2:
            continue
        all_slugs = sorted(s.slug for s in states)
        for state in states:
            other_slugs = ", ".join(s for s in all_slugs if s != state.slug)
            finding = MissionFinding(
                code="AMBIGUOUS_SELECTOR",
                severity=_slug_to_finding_severity("AMBIGUOUS_SELECTOR"),
                artifact_path=_META_JSON,
                detail=f"handle {handle!r} also matches: {other_slugs}",
            )
            if state.slug in slug_to_dir:
                attributed.setdefault(state.slug, []).append(finding)

    # --- DUPLICATE_MISSION_ID: one finding per mission sharing the same ID ------
    from collections import defaultdict

    by_id: dict[str, list[IdentityState]] = defaultdict(list)
    for state in identity_states:
        if state.mission_id is not None:
            by_id[state.mission_id].append(state)

    for mission_id, group in by_id.items():
        if len(group) < 2:
            continue
        all_slugs = sorted(s.slug for s in group)
        for state in group:
            other_slugs = ", ".join(s for s in all_slugs if s != state.slug)
            finding = MissionFinding(
                code="DUPLICATE_MISSION_ID",
                severity=_slug_to_finding_severity("DUPLICATE_MISSION_ID"),
                artifact_path=_META_JSON,
                detail=f"mission_id {mission_id!r} also used by: {other_slugs}",
            )
            if state.slug in slug_to_dir:
                attributed.setdefault(state.slug, []).append(finding)

    return attributed


def _merge_checkout_disagreements(
    mission_results: list[MissionAuditResult],
    resolved_root: Path,
    invoking_cwd: Path,
    allowed_dirs: frozenset[Path] | None,
) -> None:
    """Fold invoking-checkout-vs-primary disagreement into per-mission findings.

    From a foreign lane worktree, reading only ``resolved_root`` (the
    re-anchored primary) at both ends would report a false green even when
    the invoking checkout's own mission state disagrees with it.
    ``audit_invocation_disagreement`` (``migration.mission_state``'s
    ``--audit`` counterpart of ``enforce_primary_write_ownership``'s
    ``--fix`` refusal) is itself a no-op unless ``invoking_cwd`` really is a
    linked worktree of ``resolved_root``, so calling it from an owner
    invocation (the common case) never adds a finding.

    ``allowed_dirs`` is the already-resolved ``--mission`` scoping from
    :func:`_resolve_mission_filter` (a slug-named directory, or ``None`` for
    "scan everything") — never the raw ``--mission`` handle, which may be a
    ``mission_id``/``mid8`` that would never string-match a directory slug in
    ``_compare_checkout_mission_state``.
    """
    from specify_cli.migration.mission_state import audit_invocation_disagreement

    from .models import Severity

    mission_slug = next(iter(allowed_dirs)).name if allowed_dirs else None
    disagreements = audit_invocation_disagreement(
        invoking_cwd, resolved_root, mission=mission_slug
    )
    if not disagreements:
        return

    by_slug = {r.mission_slug: r for r in mission_results}
    for disagreement in disagreements:
        result = by_slug.get(disagreement.mission_slug)
        if result is None:
            continue
        result.findings.append(
            MissionFinding(
                code="CHECKOUT_DISAGREEMENT",
                severity=Severity.ERROR,
                artifact_path=disagreement.artifact,
                detail=(
                    f"{disagreement.artifact} disagrees with primary "
                    f"(invoking sha256 {disagreement.invoking_sha256 or 'missing'}, "
                    f"primary sha256 {disagreement.primary_sha256 or 'missing'})"
                ),
            )
        )
        result.findings.sort(key=lambda f: (f.artifact_path, f.code))


def _slug_to_finding_severity(code: str) -> Any:
    """Return the severity for a repo-level finding code."""
    from .models import Severity

    _MAP = {
        "DUPLICATE_PREFIX": Severity.WARNING,
        "AMBIGUOUS_SELECTOR": Severity.WARNING,
        "DUPLICATE_MISSION_ID": Severity.ERROR,
    }
    return _MAP.get(code, Severity.WARNING)


# ---------------------------------------------------------------------------
# Private: report assembly
# ---------------------------------------------------------------------------


def _build_report(mission_results: list[MissionAuditResult]) -> RepoAuditReport:
    """Assemble the final ``RepoAuditReport`` from per-mission results.

    Args:
        mission_results: Per-mission results, already merged with repo-level
            findings and individually sorted.

    Returns:
        :class:`~specify_cli.audit.models.RepoAuditReport` with:
        - ``missions`` sorted by ``mission_slug``
        - ``shape_counters`` built via ``Counter`` (serialised with sorted keys
          by ``RepoAuditReport.to_dict()``)
        - ``repo_summary`` with counts and severity breakdown
    """
    counter: Counter[str] = Counter(
        f.code for r in mission_results for f in r.findings
    )

    severity_counts: dict[str, int] = {"error": 0, "warning": 0, "info": 0}
    teamspace_blocker_count = 0
    for r in mission_results:
        for f in r.findings:
            severity_counts[f.severity.value] += 1
            if is_teamspace_blocker(f):
                teamspace_blocker_count += 1

    repo_summary: dict[str, Any] = {
        "total_missions": len(mission_results),
        "missions_with_errors": sum(1 for r in mission_results if r.has_errors),
        "missions_with_warnings": sum(1 for r in mission_results if r.has_warnings),
        "missions_with_teamspace_blockers": sum(
            1 for r in mission_results if r.has_teamspace_blockers
        ),
        "total_findings": sum(len(r.findings) for r in mission_results),
        "teamspace_blockers": teamspace_blocker_count,
        "findings_by_severity": severity_counts,
    }

    return RepoAuditReport(
        missions=sorted(mission_results, key=lambda r: r.mission_slug),
        shape_counters=dict(counter),
        repo_summary=repo_summary,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_audit(options: AuditOptions) -> RepoAuditReport:
    """Run the full mission-state audit and return a ``RepoAuditReport``.

    This function is the sole public entry point for the audit engine.  It
    is completely read-only: no files are written, no processes are spawned,
    and no network calls are made.

    Args:
        options: Engine configuration.  ``scan_root`` defaults to
            ``options.repo_root / KITTY_SPECS_DIR`` when None.

    Returns:
        :class:`~specify_cli.audit.models.RepoAuditReport` with all findings.

    Raises:
        AmbiguousHandleError: ``options.mission_filter`` matches > 1 mission.
        MissionNotFoundError: ``options.mission_filter`` matches 0 missions.
    """
    scan_root = options.scan_root or (options.repo_root / KITTY_SPECS_DIR)

    # CRITICAL: identity functions (audit_repo, find_duplicate_prefixes) take
    # repo_root and internally append /kitty-specs.  They must NOT receive
    # scan_root, which would cause them to look for scan_root/kitty-specs —
    # a path that does not exist — and silently return zero identity states.
    identity_states = audit_repo(options.repo_root)
    identity_index: dict[str, Any] = {s.slug: s for s in identity_states}

    # Mission filter: resolve handle → allowed_dirs set (may raise on bad handle)
    allowed_dirs = _resolve_mission_filter(
        options.mission_filter, options.repo_root, scan_root
    )

    # Per-mission classification
    default_scan = scan_root.resolve() == (options.repo_root / KITTY_SPECS_DIR).resolve()
    mission_results = _scan_missions(scan_root, allowed_dirs, identity_index, repo_root=options.repo_root if default_scan else None)

    # Repo-level findings with explicit slug attribution
    attributed = _compute_repo_findings_by_slug(
        options.repo_root, identity_states, mission_results
    )

    # Merge attributed repo-level findings into per-mission results
    if attributed:
        by_slug = {r.mission_slug: r for r in mission_results}
        for slug, findings in attributed.items():
            if slug in by_slug:
                by_slug[slug].findings.extend(findings)
                by_slug[slug].findings.sort(key=lambda f: (f.artifact_path, f.code))

    # Invoking-checkout-vs-primary disagreement (no-op unless invoking_cwd
    # is set and really is a linked worktree of repo_root).
    if options.invoking_cwd is not None:
        _merge_checkout_disagreements(
            mission_results, options.repo_root, options.invoking_cwd, allowed_dirs
        )

    # Build and return the final report
    return _build_report(mission_results)
