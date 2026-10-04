"""``finalize-tasks`` phase: spec/tasks validation gates.

Requirement-ID reads, the issue-matrix scaffold, dependency resolution and the
requirement-mapping gate.

Part of the ``mission_finalize`` decomposition (#5627); bodies moved verbatim.
``mission_finalize`` re-exports every name defined here, so historical
``mission_finalize.<name>`` imports and patch targets keep resolving. To keep
those patches *intercepting*, calls to a patched name or to a function owned by
another finalize module go through a lazy in-function
``from specify_cli.cli.commands.agent import mission_finalize as _mf`` import
(cycle-safe: never at module scope) -- the same seam-bridge idiom
``tasks_shared`` uses.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import typer


if TYPE_CHECKING:
    from specify_cli.git.protection_policy import ProtectionPolicy
from kernel._safe_re import re
from specify_cli.core.dependency_graph import detect_cycles, validate_dependencies
from mission_runtime import OwnedCheckout
from specify_cli.status import WPMetadata
from specify_cli.requirement_mapping import (
    FAILING_REASONS,
    grammar,
    read_all_wp_raw_requirement_refs,
)
from specify_cli.core.wps_manifest import (
    WpsManifest,
    dependencies_are_explicit,
    load_wps_manifest,
)
from specify_cli.cli.commands.agent.mission_parsing import (
    _find_undeclared_requirement_citations,
    _parse_requirement_ids_from_spec_md,
    _parse_requirement_refs_from_tasks_md,
)
from specify_cli.cli.commands.agent.mission_finalize_seams import ISSUE_MATRIX_FILENAME, TASKS_MD_FILENAME


def _read_spec_requirement_ids(planning_dir: Path, *, json_output: bool) -> tuple[set[str], set[str], list[str], str]:
    """Phase: parse spec.md requirement ids (all + functional) + #3394 F1 warnings.

    The third element is a (possibly empty) list of non-blocking warning
    messages from :func:`_find_undeclared_requirement_citations` -- surfaced
    so a spec whose Functional Requirements section matches none of the
    recognized declared shapes gets a loud (but never gate-failing) signal
    instead of silently reporting zero declared FRs as full coverage.

    WP06 (#3396) T031 plumbing fix: also returns the raw ``spec_content`` (the
    fourth element) so the caller can thread it into
    :func:`_validate_requirement_mapping` for the bare-prose requirement-id
    detector -- previously this text was read here and discarded, leaving
    that later phase with no access to it.
    """

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    spec_md = planning_dir / "spec.md"
    if not spec_md.exists():
        error_msg = f"spec.md not found: {spec_md}"
        if json_output:
            print(json.dumps({"error": error_msg}))
        else:
            _mf.console.print(f"[red]Error:[/red] {error_msg}")
        raise typer.Exit(1)
    spec_content = spec_md.read_text(encoding="utf-8")
    spec_requirement_ids = _parse_requirement_ids_from_spec_md(spec_content)
    extraction_warnings = _find_undeclared_requirement_citations(spec_content)
    return (
        set(spec_requirement_ids["all"]),
        set(spec_requirement_ids["functional"]),
        extraction_warnings,
        spec_content,
    )


def _mission_protection_policy(repo_root: Path, mission_slug: str, owned: OwnedCheckout | None) -> ProtectionPolicy:
    """The #5100 FR-008 mission-scoped protection policy for this finalize run.

    Non-owned: :meth:`ProtectionPolicy.resolve_for_mission` (the mission's
    primary ``meta.json``). Owned: the ONE owned authority,
    :meth:`ProtectionPolicy.resolve_for_owned`, folds the mission from the fact
    rather than re-deriving the repository root from the slug.
    """
    from specify_cli.git.protection_policy import ProtectionPolicy as _Policy

    if owned is None:
        return _Policy.resolve_for_mission(repo_root, mission_slug)
    return _Policy.resolve_for_owned(owned, mission_slug)


def _scaffold_issue_matrix_if_present(
    planning_dir: Path,
    repo_root: Path,
    mission_slug: str,
    *,
    target_branch: str | None,
    validate_only: bool,
    json_output: bool,
    owned: OwnedCheckout | None = None,
) -> None:
    """Phase: B3 / T021 issue-matrix.json scaffold (idempotent), routed COORD.

    write-side-seam-matrix-tracer-01KYP3MH WP05 (B3): authors
    ``issue-matrix.json`` via ``write_target(ISSUE_MATRIX)`` -- COORD for
    coord/lanes-with-coord topologies -- NEVER a stray ``issue-matrix.md`` on
    the planning (primary) dir. The former ``.md``-on-primary scaffold meant
    FR-013 migrate-on-write never fired for a greenfield mission.
    """

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    if validate_only:
        return
    try:
        from specify_cli.tasks.issue_matrix import scaffold_issue_matrix

        spec_md = planning_dir / "spec.md"
        issue_matrix_path = scaffold_issue_matrix(
            planning_dir,
            spec_md,
            repo_root=owned.repository_root if owned else repo_root,
            mission_slug=mission_slug,
            policy=_mf._mission_protection_policy(repo_root, mission_slug, owned),
            target_branch=target_branch,
            # FR-015/NFR-001 (review cycle 1, HIGH-2): when the matrix's declared
            # home is planning_dir the scaffold is a bare write that rides the
            # single final commit (``issue-matrix.json`` is a collected
            # candidate) -- it must not commit before the refusal gates ran.
            fold_into_caller_commit=True,
            owned=owned,
        )
    except Exception as issue_matrix_exc:  # noqa: BLE001 — convenience artifact never blocks finalize
        if owned:
            raise
        if not json_output:
            _mf.console.print(f"[yellow]Warning:[/yellow] could not scaffold issue-matrix.json: {issue_matrix_exc}")
        return
    if issue_matrix_path is not None and not json_output:
        try:
            rel: Path = issue_matrix_path.relative_to(repo_root)
        except ValueError:
            rel = issue_matrix_path
        _mf.console.print(f"[info] Scaffolded {rel}")


def _advisory_issue_matrix_lint(planning_dir: Path, *, json_output: bool) -> None:
    """Phase: FR-009 advisory (never-blocking) issue-matrix lint (#2223).

    Reuses the SAME exported ``validate_issue_matrix`` rule engine the approve
    gate calls (NFR-002 — one engine, two callers). Findings are surfaced as
    warnings only; a malformed matrix NEVER blocks ``finalize-tasks``. The
    completeness "row-for-every-#ref" scan in
    ``agent/tasks_parsing_validation.py::_issue_matrix_evaluation`` is OUT of
    scope here and intentionally not cross-imported (it would invert the
    command-module dependency direction; factor a shared pure helper first).

    The engine is imported at call time from the ``review`` package so the
    symbol resolves to the exact callable the approve gate uses (and stays
    monkeypatchable for call-identity tests) without an import cycle.

    C1 fix (write-side-seam-matrix-tracer-01KYP3MH WP05): the precheck is
    dir-based (:func:`issue_matrix_artifact_present`), not a ``.md``-only
    ``.exists()`` -- the prior precheck made a ``.json``-only mission (B3)
    return here BEFORE ``validate_issue_matrix`` ever ran, silently skipping
    the lint entirely (the same dead-code-behind-a-precheck class the reader
    migration fixes elsewhere).
    """

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    from specify_cli.tasks.issue_matrix import ISSUE_MATRIX_JSON_FILENAME
    from specify_cli.tasks.issue_matrix_migration import issue_matrix_artifact_present

    if not issue_matrix_artifact_present(planning_dir):
        return
    json_path = planning_dir / ISSUE_MATRIX_JSON_FILENAME
    matrix_path = json_path if json_path.exists() else planning_dir / ISSUE_MATRIX_FILENAME
    try:
        from specify_cli.cli.commands.review import validate_issue_matrix

        result = validate_issue_matrix(matrix_path)
    except Exception as lint_exc:  # noqa: BLE001 — advisory lint never blocks finalize
        if not json_output:
            _mf.console.print(f"[yellow]Warning:[/yellow] could not lint {ISSUE_MATRIX_FILENAME}: {lint_exc}")
        return
    if result.passed or json_output:
        return
    _mf.console.print(f"[yellow]Advisory:[/yellow] {ISSUE_MATRIX_FILENAME} has lint finding(s) (non-blocking — does not affect finalize):")
    for diagnostic in result.diagnostics:
        _mf.console.print(f"  - {diagnostic['diagnostic_code']}: {diagnostic['message']}")


def _load_manifest(planning_dir: Path, *, json_output: bool) -> WpsManifest | None:
    """Phase: TIER 0 — load the wps.yaml manifest (or None)."""

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    try:
        return load_wps_manifest(planning_dir)
    except typer.Exit:
        raise
    except Exception as exc:
        error_msg = f"wps.yaml is present but could not be loaded: {exc}"
        if json_output:
            _mf._emit_json({"error": error_msg})
        else:
            _mf.console.print(f"[red]Error:[/red] {error_msg}")
        raise typer.Exit(1) from exc


@dataclass
class _DependencyResolution:
    """Outcome of the 3-tier dependency + requirement-ref resolution phase."""

    wp_dependencies: dict[str, list[str]] = field(default_factory=dict)
    tasks_md_dependencies: dict[str, list[str]] = field(default_factory=dict)
    wp_requirement_refs: dict[str, list[str]] = field(default_factory=dict)
    #: T012 (FR-011): the additive requirement diagnostics
    #: (``parsed_spec_ids``/``rejected_requirement_refs``/
    #: ``success_criteria_coverage``) ``_validate_requirement_mapping``
    #: returns on success -- carried through to both success reports.
    requirement_diagnostics: dict[str, object] = field(default_factory=dict)


def _resolve_dependencies_and_refs(
    planning_dir: Path,
    wps_manifest: WpsManifest | None,
    wp_files: list[Path],
    expected_wp_ids: list[str],
    *,
    json_output: bool,
) -> _DependencyResolution:
    """Phase: TIER 1+ — 3-tier dependency + requirement-ref resolution.

    1. wps.yaml manifest when present
    2. non-empty WP frontmatter dependencies — an *empty* ``dependencies: []``
       is treated as absent (see below), not as an authoritative declaration
    3. tasks.md text parsing when frontmatter lacks a usable dependencies
       value (field absent entirely, or present-but-empty)

    Requirement refs (T011): the PRIMARY source is
    :func:`specify_cli.requirement_mapping.read_all_wp_raw_requirement_refs`
    -- the WP01 unified RAW reader (case-preserved, un-normalised tokens).
    Classification (FR-019, :func:`_classify_wp_requirement_refs`) needs the
    AUTHORED tokens, not a pre-filtered/canonicalised list, or a malformed or
    foreign-qualified ref would silently vanish before the grammar's verdict
    table ever sees it. WP04's runtime classifies the SAME reader's output,
    which is what keeps the two gates agreeing on malformed/foreign refs.

    An empty frontmatter ``dependencies: []`` is a serialization artifact, not
    a user declaration: ``agent tasks map-requirements`` rewrites WP frontmatter
    for its own purposes via ``WPMetadata.model_dump(exclude_none=True)`` and
    ``dependencies`` defaults to ``[]`` (never ``None``), so every WP that
    command touches gains a literal ``dependencies: []`` line the user never
    wrote. Treating that incidental empty list as TIER-2 authority silently
    discarded the tasks.md-declared chain (#4135) — every WP came out
    independent/parallel in lanes.json with no warning. Falling through to
    TIER-3 on empty is also lossless for a user who *does* want a WP declared
    dependency-free: tasks.md parsing yields ``[]`` for a WP with no
    ``depends on`` entries, so the resolved value is the same either way.
    """

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    tasks_md = planning_dir / TASKS_MD_FILENAME
    res = _DependencyResolution()

    if wps_manifest is not None:
        for entry in wps_manifest.work_packages:
            res.wp_dependencies[entry.id] = list(entry.dependencies) if dependencies_are_explicit(entry) else []

    # PRIMARY: WP frontmatter, raw authored tokens (map-requirements writes
    # here directly; see the docstring above for why this must be the raw
    # reader rather than a normalising one).
    res.wp_requirement_refs = read_all_wp_raw_requirement_refs(planning_dir / "tasks")

    if wps_manifest is None and tasks_md.exists():
        tasks_content = tasks_md.read_text(encoding="utf-8")
        from specify_cli.core.dependency_parser import parse_dependencies_from_tasks_md as _shared_parse_deps

        res.tasks_md_dependencies = _shared_parse_deps(tasks_content)
        _validate_tasks_md_coverage(res.tasks_md_dependencies, expected_wp_ids, json_output=json_output)

        # FALLBACK: tasks.md text (backward compat for pre-API projects)
        for wp_id, refs in _parse_requirement_refs_from_tasks_md(tasks_content).items():
            if refs and not res.wp_requirement_refs.get(wp_id):
                res.wp_requirement_refs[wp_id] = refs

        for wp_file in wp_files:
            wp_id_match = re.match(r"^(WP\d{2})(?:[-_.]|$)", wp_file.name)
            if not wp_id_match:
                continue
            wp_id = wp_id_match.group(1)
            wp_meta, _ = _mf._read_wp_frontmatter(wp_file)
            frontmatter_deps = list(wp_meta.dependencies)
            if frontmatter_deps:
                res.wp_dependencies[wp_id] = frontmatter_deps
            else:
                # FALLBACK: tasks.md text (backward compat for pre-API projects,
                # and for frontmatter ``dependencies: []`` — the map-requirements
                # serialization artifact, #4135)
                res.wp_dependencies[wp_id] = list(res.tasks_md_dependencies.get(wp_id, []))
    return res


def _validate_occurrence_map_ready(planning_dir: Path, *, json_output: bool) -> None:
    """Phase: bulk-edit occurrence-map gate (reuses the implement-time check).

    Reuses ``ensure_occurrence_classification_ready`` unchanged (C-001, FR-002):
    for non-bulk-edit missions it self-conditions to a no-op; for bulk-edit
    missions it blocks finalize-tasks when ``occurrence_map.yaml`` is missing,
    schema-invalid, or inadmissible, so the failure surfaces here instead of
    at the first ``implement WP##`` (FR-001). Read-only — preserves the
    ``--validate-only`` zero-mutation invariant (C-004).
    """

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    from specify_cli.bulk_edit.gate import (
        ensure_occurrence_classification_ready,
        finalize_tasks_gate_error_payload,
        render_gate_failure,
    )

    result = ensure_occurrence_classification_ready(planning_dir)
    if result.passed:
        return
    if json_output:
        _mf._emit_json(finalize_tasks_gate_error_payload(result))
    else:
        render_gate_failure(result, _mf.console)
    raise typer.Exit(1)


def _validate_tasks_md_coverage(tasks_md_dependencies: dict[str, list[str]], expected_wp_ids: list[str], *, json_output: bool) -> None:
    """Phase: verify every WP file matches a parsed tasks.md section."""

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    missing_wp_sections = [wp_id for wp_id in expected_wp_ids if wp_id not in tasks_md_dependencies]
    extra_wp_sections = sorted(set(tasks_md_dependencies) - set(expected_wp_ids))
    if not (missing_wp_sections or extra_wp_sections):
        return
    error_msg = (
        "tasks.md work package coverage is incomplete. finalize-tasks could not match all WP files to parsed sections, so dependency lanes would be unreliable."
    )
    payload: dict[str, object] = {
        "error": error_msg,
        "missing_wp_sections": missing_wp_sections,
        "extra_wp_sections": extra_wp_sections,
        "hint": "Use supported section headers such as '## WP01', '## Work Package WP01', or '## Work Package 1 — Title'.",
    }
    if json_output:
        _mf._emit_json(payload)
    else:
        _mf.console.print(f"[red]Error:[/red] {error_msg}")
        if missing_wp_sections:
            _mf.console.print(f"  Missing WP sections: {', '.join(missing_wp_sections)}")
        if extra_wp_sections:
            _mf.console.print(f"  Extra WP sections: {', '.join(extra_wp_sections)}")
        _mf.console.print(f"  {payload['hint']}")
    raise typer.Exit(1)


def _validate_dependency_graph(wp_dependencies: dict[str, list[str]], *, json_output: bool) -> None:
    """Phase: detect cycles + invalid references in the dependency graph."""

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    if not wp_dependencies:
        return
    cycles = detect_cycles(wp_dependencies)
    if cycles:
        error_msg = f"Circular dependencies detected: {cycles}"
        if json_output:
            _mf._emit_json({"error": error_msg, "cycles": cycles})
        else:
            _mf.console.print("[red]Error:[/red] Circular dependencies detected:")
            for cycle in cycles:
                _mf.console.print(f"  {' → '.join(cycle)}")
        raise typer.Exit(1)

    for wp_id, deps in wp_dependencies.items():
        is_valid, errors = validate_dependencies(wp_id, deps, wp_dependencies)
        if not is_valid:
            error_msg = f"Invalid dependencies for {wp_id}: {errors}"
            if json_output:
                _mf._emit_json({"error": error_msg, "wp_id": wp_id, "errors": errors})
            else:
                _mf.console.print(f"[red]Error:[/red] Invalid dependencies for {wp_id}:")
                for err in errors:
                    _mf.console.print(f"  - {err}")
            raise typer.Exit(1)


def _classify_one_wp(refs: list[str], declared: set[str]) -> tuple[set[str], list[dict[str, str]]]:
    """Classify one WP's raw refs via the grammar verdict table (FR-019).

    Returns the accepted refs' canonical ids (a set: duplicates collapse)
    and, in authored order, every rejection as ``{"ref": raw, "reason":
    reason}``. ``reason`` is one of :data:`grammar.MALFORMED`,
    :data:`grammar.UNKNOWN_SPEC_ID` or :data:`grammar.FOREIGN_QUALIFIED` --
    a ``foreign_qualified`` ref is a rejection (never accepted, and never
    resolved against *declared*) but is never a *failing* one (T011/FR-019).
    """
    accepted: set[str] = set()
    rejections: list[dict[str, str]] = []
    for raw in refs:
        verdict = grammar.classify(raw, declared)
        if isinstance(verdict, grammar.Accepted):
            accepted.add(verdict.requirement_id.canonical)
        else:
            rejections.append({"ref": verdict.raw, "reason": verdict.reason})
    return accepted, rejections


def _classify_wp_requirement_refs(
    wp_ids: list[str],
    wp_requirement_refs: dict[str, list[str]],
    all_spec_requirement_ids: set[str],
) -> tuple[list[str], dict[str, list[str]], set[str], dict[str, list[dict[str, str]]]]:
    """Bucket each WP's requirement refs into missing/unknown/mapped (FR-019, FR-010).

    Per-ref verdicts (T011): every raw ref is classified individually via
    :func:`_classify_one_wp` rather than an all-or-nothing rule -- a valid
    sibling ref always counts toward coverage even when another ref on the
    same WP is rejected.

    - ``missing_requirement_refs_wps``: WPs with NO accepted ref (Decision
      Moment ``01M3NYFZ1P6QBD2DX4DVDA323W``). A WP whose only accepted refs
      are success criteria still counts as having refs; a WP with only
      rejected refs (including an all-foreign WP) is missing AND is listed
      in ``rejected_requirement_refs`` with its rejections.
    - ``unknown_requirement_refs``: the sorted raw refs whose rejection
      reason is in :data:`FAILING_REASONS` -- never ``foreign_qualified``,
      which is a rejection but never a failing one.
    - the fourth element is every rejection (every reason, including
      ``foreign_qualified``), in authored order, for WPs that have at least
      one -- feeds the additive ``rejected_requirement_refs`` JSON key
      (FR-011, T012).
    """
    missing_requirement_refs_wps: list[str] = []
    unknown_requirement_refs: dict[str, list[str]] = {}
    mapped_requirement_ids: set[str] = set()
    rejected_requirement_refs: dict[str, list[dict[str, str]]] = {}

    for wp_id in sorted(set(wp_ids)):
        refs = wp_requirement_refs.get(wp_id, [])
        accepted, rejections = _classify_one_wp(refs, all_spec_requirement_ids)
        if rejections:
            rejected_requirement_refs[wp_id] = rejections
            failing_refs = sorted(entry["ref"] for entry in rejections if entry["reason"] in FAILING_REASONS)
            if failing_refs:
                unknown_requirement_refs[wp_id] = failing_refs
        if not accepted:
            missing_requirement_refs_wps.append(wp_id)
        mapped_requirement_ids.update(accepted)

    return missing_requirement_refs_wps, unknown_requirement_refs, mapped_requirement_ids, rejected_requirement_refs


def _detect_bare_prose_requirement_ids_fail_loud(spec_content: str) -> list[str]:
    """WP06 (#3396) T031/IC-04: fail-loud bare-prose requirement-id detection
    for ``finalize-tasks``'s requirement-mapping gate.

    ``find_bare_prose_requirement_ids`` catches a requirement id (e.g.
    ``FR-001``) written as bare, unbulleted, unbolded prose in a
    "Functional Requirements"-named section -- a gap the existing
    missing/unknown/unmapped buckets cannot see, since a bare-prose id was
    never counted as mapped OR as a declared functional requirement in the
    first place (Story 1 AC1/AC2).

    Deliberately NOT routed through ``_find_undeclared_requirement_citations``
    / its swallow-and-log advisory contract (that helper's "never fail the
    gate" intent is the opposite of this one) -- this is a textually separate
    wrapper: any classification exception is caught ONCE and converted into
    an explicit, non-empty failure entry (mirroring WP05/T023's
    ``BareProseRequirementFacts.classification_error`` contract) so the
    caller's blocking check below can never be silently satisfied by a
    swallowed "0 uncounted" (NFR-002).
    """
    try:
        from specify_cli.requirement_mapping import find_bare_prose_requirement_ids

        candidates = find_bare_prose_requirement_ids(spec_content)
        return sorted({req_id for candidate in candidates for req_id in candidate.ids})
    except Exception as exc:  # noqa: BLE001 -- fail-loud: converted below into an explicit, non-empty failure, never swallowed
        return [f"<bare-prose-detection-error: {exc!r} -- treating as blocking, never silently clean (NFR-002)>"]


def _build_success_criteria_coverage(
    declared_success_criteria: list[str],
    wp_requirement_refs: dict[str, list[str]],
    all_spec_requirement_ids: set[str],
) -> dict[str, object]:
    """FR-007: track (never gate) which declared SC ids each WP references.

    Success criteria are informational, not coverage-gating: an
    unreferenced declared SC never fails the run (unlike an unmapped FR).
    Matching is by canonical form (C-001), through the same grammar verdict
    table the coverage gate uses -- a rejected/foreign SC-shaped token is
    never counted as "referenced".
    """
    referenced: dict[str, list[str]] = {}
    for wp_id in sorted(wp_requirement_refs):
        for raw in wp_requirement_refs[wp_id]:
            verdict = grammar.classify(raw, all_spec_requirement_ids)
            if isinstance(verdict, grammar.Accepted) and verdict.requirement_id.is_success_criterion:
                wps_for_sc = referenced.setdefault(verdict.requirement_id.canonical, [])
                # A WP that lists the same SC twice (e.g. once bare, once
                # inside a scalar-string cell) must appear once, not once
                # per occurrence.
                if wp_id not in wps_for_sc:
                    wps_for_sc.append(wp_id)
    unreferenced = sorted(sc for sc in declared_success_criteria if sc not in referenced)
    return {"referenced": referenced, "unreferenced": unreferenced}


def _build_requirement_diagnostics(
    spec_content: str,
    wp_requirement_refs: dict[str, list[str]],
    all_spec_requirement_ids: set[str],
    rejected_requirement_refs: dict[str, list[dict[str, str]]],
) -> dict[str, object]:
    """Phase: build the three additive FR-011/FR-007/FR-008 diagnostic keys.

    One pure builder (T012), reused by the failure payload, the
    ``--validate-only`` success report and the real-run success report --
    every caller gets the SAME three keys with the SAME shape
    (``contracts/json-payload-deltas.md``).
    """
    buckets = _parse_requirement_ids_from_spec_md(spec_content)
    parsed_spec_ids = {
        "functional": buckets["functional"],
        "non_functional": buckets["non_functional"],
        "constraint": buckets["constraint"],
        "success_criteria": buckets["success_criteria"],
    }
    success_criteria_coverage = _build_success_criteria_coverage(buckets["success_criteria"], wp_requirement_refs, all_spec_requirement_ids)
    return {
        "parsed_spec_ids": parsed_spec_ids,
        "rejected_requirement_refs": rejected_requirement_refs,
        "success_criteria_coverage": success_criteria_coverage,
    }


def _build_requirement_mapping_failure_payload(
    *,
    missing_requirement_refs_wps: list[str],
    unknown_requirement_refs: dict[str, list[str]],
    unmapped_functional_requirements: list[str],
    bare_prose_requirement_ids: list[str],
    wp_dependencies: dict[str, list[str]],
    wp_requirement_refs: dict[str, list[str]],
    requirement_diagnostics: dict[str, object],
) -> dict[str, object]:
    """Phase: pure JSON payload builder for the requirement-mapping failure (T009).

    NFR-002: every pre-existing key keeps its name and type; the three
    ``requirement_diagnostics`` keys (``parsed_spec_ids``,
    ``rejected_requirement_refs``, ``success_criteria_coverage``) are purely
    additive.
    """
    return {
        "error": "Requirement mapping validation failed",
        "missing_requirement_refs_wps": missing_requirement_refs_wps,
        "unknown_requirement_refs": unknown_requirement_refs,
        "unmapped_functional_requirements": unmapped_functional_requirements,
        "bare_prose_requirement_ids": bare_prose_requirement_ids,
        "dependencies_parsed": wp_dependencies,
        "requirement_refs_parsed": wp_requirement_refs,
        **requirement_diagnostics,
    }


def _emit_requirement_mapping_report(
    *,
    json_output: bool,
    missing_requirement_refs_wps: list[str],
    unknown_requirement_refs: dict[str, list[str]],
    unmapped_functional_requirements: list[str],
    bare_prose_requirement_ids: list[str],
    wp_dependencies: dict[str, list[str]],
    wp_requirement_refs: dict[str, list[str]],
    requirement_diagnostics: dict[str, object] | None = None,
) -> None:
    """Phase: emit the requirement-mapping validation failure (JSON or console)."""

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    error_msg = "Requirement mapping validation failed"
    diagnostics = requirement_diagnostics or {}
    if json_output:
        payload = _build_requirement_mapping_failure_payload(
            missing_requirement_refs_wps=missing_requirement_refs_wps,
            unknown_requirement_refs=unknown_requirement_refs,
            unmapped_functional_requirements=unmapped_functional_requirements,
            bare_prose_requirement_ids=bare_prose_requirement_ids,
            wp_dependencies=wp_dependencies,
            wp_requirement_refs=wp_requirement_refs,
            requirement_diagnostics=diagnostics,
        )
        print(json.dumps(payload))
        return
    _mf.console.print(f"[red]Error:[/red] {error_msg}")
    if missing_requirement_refs_wps:
        _mf.console.print("[red]Missing requirement refs:[/red]")
        for wp_id in missing_requirement_refs_wps:
            _mf.console.print(f"  - {wp_id}")
    if unknown_requirement_refs:
        _mf.console.print("[red]Unknown requirement refs:[/red]")
        for wp_id, refs in unknown_requirement_refs.items():
            _mf.console.print(f"  - {wp_id}: {', '.join(refs)}")
    if unmapped_functional_requirements:
        _mf.console.print("[red]Unmapped functional requirements:[/red]")
        for req_id in unmapped_functional_requirements:
            _mf.console.print(f"  - {req_id}")
    if bare_prose_requirement_ids:
        _mf.console.print("[red]Bare-prose requirement id(s) found, uncounted:[/red]")
        for req_id in bare_prose_requirement_ids:
            _mf.console.print(f"  - {req_id}")
    rejected = diagnostics.get("rejected_requirement_refs")
    if isinstance(rejected, dict) and rejected:
        _mf.console.print("[red]Rejected requirement refs:[/red]")
        for wp_id, entries in rejected.items():
            for entry in entries:
                _mf.console.print(f"  - {wp_id}: {entry['ref']} ({entry['reason']})")


def _validate_requirement_mapping(
    wp_ids: list[str],
    wp_requirement_refs: dict[str, list[str]],
    all_spec_requirement_ids: set[str],
    functional_spec_requirement_ids: set[str],
    wp_dependencies: dict[str, list[str]],
    spec_content: str = "",
    *,
    json_output: bool,
) -> dict[str, object]:
    """Phase: validate every WP maps to known requirement ids (FR coverage).

    WP06 (#3396) T031: additionally surfaces ``bare_prose_requirement_ids`` --
    requirement ids written as bare, unbulleted, unbolded prose in spec.md's
    "Functional Requirements"-named section(s) -- as a distinct,
    separately-labeled failure alongside missing/unknown/unmapped. Never
    merged into ``unmapped_functional_requirements``: "declared but not yet
    mapped to a WP" and "never declared at all" are different remediation
    stories for an operator.

    T012 (FR-011): returns the requirement diagnostics
    (``parsed_spec_ids``/``rejected_requirement_refs``/
    ``success_criteria_coverage``) on success, so the caller can carry them
    into the ``--validate-only`` and real-run success reports. On failure the
    SAME diagnostics ride the failure JSON instead, and this still raises
    ``typer.Exit(1)``.
    """
    missing_requirement_refs_wps, unknown_requirement_refs, mapped_requirement_ids, rejected_requirement_refs = _classify_wp_requirement_refs(
        wp_ids, wp_requirement_refs, all_spec_requirement_ids
    )

    unmapped_functional_requirements = sorted(functional_spec_requirement_ids - mapped_requirement_ids)
    bare_prose_requirement_ids = _detect_bare_prose_requirement_ids_fail_loud(spec_content)
    requirement_diagnostics = _build_requirement_diagnostics(spec_content, wp_requirement_refs, all_spec_requirement_ids, rejected_requirement_refs)
    if not (missing_requirement_refs_wps or unknown_requirement_refs or unmapped_functional_requirements or bare_prose_requirement_ids):
        return requirement_diagnostics

    _emit_requirement_mapping_report(
        json_output=json_output,
        missing_requirement_refs_wps=missing_requirement_refs_wps,
        unknown_requirement_refs=unknown_requirement_refs,
        unmapped_functional_requirements=unmapped_functional_requirements,
        bare_prose_requirement_ids=bare_prose_requirement_ids,
        wp_dependencies=wp_dependencies,
        wp_requirement_refs=wp_requirement_refs,
        requirement_diagnostics=requirement_diagnostics,
    )
    raise typer.Exit(1)


def _detect_dependency_conflicts(wp_files: list[Path], wp_dependencies: dict[str, list[str]], *, json_output: bool) -> None:
    """Phase: T004 disagree-loud — frontmatter vs parsed deps conflict gate."""

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    existing_frontmatter: dict[str, WPMetadata] = {}
    for wp_file in wp_files:
        wp_id_match = re.match(r"^(WP\d{2})(?:[-_.]|$)", wp_file.name)
        if not wp_id_match:
            continue
        wp_id = wp_id_match.group(1)
        try:
            wp_meta, _ = _mf._read_wp_frontmatter(wp_file)
            existing_frontmatter[wp_id] = wp_meta
        except Exception:  # noqa: BLE001 — unreadable frontmatter degrades to a stub
            existing_frontmatter[wp_id] = WPMetadata(work_package_id=wp_id, title=wp_id)

    dep_conflict_errors: list[str] = []
    for wp_id_chk, parsed_deps in wp_dependencies.items():
        existing_meta = existing_frontmatter.get(wp_id_chk)
        existing_deps: list[str] = list(existing_meta.dependencies) if existing_meta else []
        if existing_deps and parsed_deps and set(existing_deps) != set(parsed_deps):
            dep_conflict_errors.append(
                f"{wp_id_chk}: frontmatter has {sorted(existing_deps)}, "
                f"tasks.md parsed {sorted(parsed_deps)}. "
                f"Resolve the disagreement in tasks.md or WP frontmatter before finalizing."
            )
    if dep_conflict_errors:
        error_msg = "Dependency disagreement detected:\n" + "\n".join(dep_conflict_errors)
        if json_output:
            _mf._emit_json({"error": error_msg, "dependency_conflicts": dep_conflict_errors})
        else:
            _mf.console.print(f"[red]Error:[/red] {error_msg}")
        raise typer.Exit(1)
