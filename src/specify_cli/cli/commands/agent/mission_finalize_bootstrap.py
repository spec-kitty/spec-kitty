"""``finalize-tasks`` phase: per-WP frontmatter bootstrap and ownership gates.

Also owns lane-input projection, the ``--validate-only`` report and the local
canonical status events.

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

import contextlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, cast

import typer

from kernel._safe_re import re
from mission_runtime import MissionArtifactKind
from mission_runtime import OwnedCheckout
from specify_cli.frontmatter import locked_update_frontmatter, write_frontmatter
from specify_cli.ownership import infer_ownership
from specify_cli.ownership.audit_targets import validate_audit_coverage
from specify_cli.ownership.inference import detect_post_integration_acceptance
from specify_cli.ownership.models import OwnershipManifest
from specify_cli.ownership.validation import (
    GlobValidationResult,
    validate_glob_matches,
)
from specify_cli.status import Lane, WPMetadata, _Builder
from specify_cli.status.mission_write import locked_rewrite_text, mission_write_lock
from specify_cli.core.wps_manifest import (
    WpsManifest,
    generate_tasks_md_from_manifest,
)
from specify_cli.cli.commands.agent.finalization_eligibility import (
    FinalizationEligibility,
    filter_by_wp_ids,
    project_finalization_eligibility,
)
from specify_cli.cli.commands.agent.mission_parsing import (
    _invalid_mission_specs_owned_files,
    _owned_files_yaml_is_explicit_empty_list,
    _raw_frontmatter_dependencies_is_string_form,
    _raw_frontmatter_has_field,
)

if TYPE_CHECKING:
    from specify_cli.cli.commands.agent.mission_finalize_planning_pin import PlanningCommitResolution
    from specify_cli.cli.commands.agent.mission_finalize_validation import _DependencyResolution
    from specify_cli.lanes.frozen_membership import FrozenLaneMembership
from specify_cli.cli.commands.agent.mission_finalize_seams import (
    FINALIZE_TASKS_COMMAND_NAME,
    INVALID_WP_OWNED_FILES_KITTY_SPECS,
    LANE_COMPUTATION_ABORTED_EMPTY_INPUTS,
    OWNERSHIP_CONTRADICTION_CODE_CHANGE_EMPTY_OWNED_FILES,
    TASKS_MD_FILENAME,
)


def _enforce_charter_activation_gate(wp_meta: WPMetadata, wp_id: str, repo_root: Path) -> None:
    """Phase: T044 / FR-017 charter activation gate (fires before any write)."""

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    profile = wp_meta.agent_profile
    if not profile:
        return
    from charter.activation.exceptions import CharterActivationError
    from charter.activation.invocation_context import ProjectContext

    pack_ctx = ProjectContext.from_repo(repo_root).require_pack_context()
    activated_profiles = pack_ctx.activated_agent_profiles
    if activated_profiles is not None and profile not in activated_profiles:
        activated_list = ", ".join(sorted(activated_profiles)) or "(none)"
        resolution_cmd = f"spec-kitty charter activate agent-profile {profile}"
        _mf.console.print(
            f"[red]✗ Charter activation gate FAILED[/red]\n"
            f"  WP {wp_id} assigns profile: [bold]{profile}[/bold]\n"
            f"  '{profile}' is not in the activated agent-profile set.\n"
            f"  Currently activated: {activated_list}\n"
            f"  Resolution: {resolution_cmd}"
        )
        raise CharterActivationError(f"artifact={profile!r}, activated={activated_list!r}, resolution={resolution_cmd!r}")


@dataclass
class _BootstrapState:
    """Accumulated in-memory state from the 8-field bootstrap-mutation loop."""

    updated_count: int = 0
    work_packages: list[dict[str, object]] = field(default_factory=list)
    modified_wps: list[str] = field(default_factory=list)
    unchanged_wps: list[str] = field(default_factory=list)
    preserved_wps: list[str] = field(default_factory=list)
    would_modify: list[dict[str, object]] = field(default_factory=list)
    inmemory_frontmatter: dict[str, WPMetadata] = field(default_factory=dict)
    inmemory_bodies: dict[str, str] = field(default_factory=dict)
    pending_writes: list[tuple[Path, WPMetadata, str]] = field(default_factory=list)
    #: The fields bootstrap decided to set on each queued work package (its ``changed_fields``). The flush
    #: re-applies exactly these to the frontmatter and body it reads under the lock, never the in-memory
    #: model, so a field or note another writer landed since the read survives (FR-003).
    pending_deltas: dict[Path, dict[str, object]] = field(default_factory=dict)
    ownership_warnings: list[str] = field(default_factory=list)
    ownership_contradictions: list[str] = field(default_factory=list)
    #: #3394 review F1 -- non-blocking signal, kept distinct from
    #: ``ownership_warnings`` so the JSON payload names the concern precisely
    #: (raw requirement tokens that matched no declared shape) rather than
    #: folding it into an unrelated bucket.
    requirement_extraction_warnings: list[str] = field(default_factory=list)
    post_integration_acceptance_warnings: list[str] = field(default_factory=list)
    #: T012 (FR-011): the additive requirement diagnostics, copied through
    #: from ``_DependencyResolution.requirement_diagnostics`` so both success
    #: reports can spread it without threading a second parameter.
    requirement_diagnostics: dict[str, object] = field(default_factory=dict)


def _branch_strategy_text(target_branch: str, merge_target_branch: str | None = None) -> str:
    """Compute the long-form branch-strategy frontmatter value."""
    final_target = merge_target_branch or target_branch
    return (
        f"Planning artifacts for this mission were generated on {target_branch}. "
        f"During /spec-kitty.implement this WP may branch from a dependency-specific base, "
        f"but completed changes must merge back into {final_target} unless the human explicitly redirects the landing branch."
    )


def _apply_bootstrap_fields(
    bld: _Builder,
    wp_meta: WPMetadata,
    *,
    deps: list[str],
    has_dependencies_line: bool,
    requirement_refs: list[str],
    target_branch: str,
    merge_target_branch: str | None = None,
    dependencies_string_form: bool = False,
) -> tuple[bool, dict[str, object]]:
    """Apply the always-evaluated bootstrap fields, returning (changed, fields).

    Covers dependencies, planning_base_branch, merge_target_branch,
    branch_strategy. Ownership fields are applied separately.

    ``requirement_refs`` (FR-004, #2991) is deliberately NOT an
    always-evaluated field: an authored ``requirement_refs`` list is never
    rewritten, whatever the resolved/classified value looks like. The only
    write this function ever makes to ``requirement_refs`` is a narrow
    populate-when-empty one -- when ``wp_meta.requirement_refs`` is empty
    AND the resolved *requirement_refs* is non-empty (the legacy
    tasks.md-fallback case: a pre-``wps.yaml`` WP with no authored refs at
    all). Populating an empty list erases nothing; an authored list -- even
    one the grammar would reject -- is preserved byte-for-byte. When some
    OTHER field on this WP changes, ``_flush_frontmatter_writes`` re-dumps
    the whole ``WPMetadata`` model regardless, which is also what turns a
    legacy scalar-string ``requirement_refs`` into its canonical YAML list
    form (items, order and spelling unchanged) without a second write path
    here.

    ``dependencies_string_form`` (set by the bootstrap loop when the raw
    frontmatter stores ``dependencies`` as a legacy string — ``"[]"``,
    ``"WP01, WP02"``, bare ``WP01``, #3941) forces the dependencies rewrite
    even when the coerced value already equals *deps*: the canonical list
    form must reach the tree, and ``WPMetadata``'s read-time coercion hides
    the string form from the value comparison above.
    """
    final_target = merge_target_branch or target_branch
    branch_strategy = _branch_strategy_text(target_branch, final_target)
    changed_fields: dict[str, object] = {}
    frontmatter_changed = False

    if dependencies_string_form or not has_dependencies_line or list(wp_meta.dependencies) != deps:
        changed_fields["dependencies"] = deps
        bld.set(dependencies=deps)
        frontmatter_changed = True
    if wp_meta.planning_base_branch != target_branch:
        changed_fields["planning_base_branch"] = target_branch
        bld.set(planning_base_branch=target_branch)
        frontmatter_changed = True
    if wp_meta.merge_target_branch != final_target:
        changed_fields["merge_target_branch"] = final_target
        bld.set(merge_target_branch=final_target)
        frontmatter_changed = True
    if wp_meta.branch_strategy != branch_strategy:
        changed_fields["branch_strategy"] = branch_strategy
        bld.set(branch_strategy=branch_strategy)
        frontmatter_changed = True
    # FR-004 (#2991): populate-when-empty ONLY -- an authored (non-empty)
    # requirement_refs is never touched, even when the resolved refs differ.
    if not wp_meta.requirement_refs and requirement_refs:
        changed_fields["requirement_refs"] = requirement_refs
        bld.set(requirement_refs=requirement_refs)
        frontmatter_changed = True
    return frontmatter_changed, changed_fields


def _apply_ownership_inference(
    bld: _Builder,
    wp_meta: WPMetadata,
    wp_raw_content: str,
    mission_slug: str,
    changed_fields: dict[str, object],
) -> tuple[bool, list[str], str | None]:
    """Apply inferred ownership fields, returning changed, warnings, and contradiction.

    Respects an explicit ``owned_files: []`` (planning-artifact WPs).
    """
    owned_files_explicitly_empty = _owned_files_yaml_is_explicit_empty_list(wp_raw_content)
    if wp_meta.execution_mode == "code_change" and owned_files_explicitly_empty:
        contradiction = (
            f"{wp_meta.work_package_id}: code_change WP declares no owned files "
            "(execution_mode: code_change with an explicit owned_files: [] is an authoring contradiction)"
        )
        return False, [], contradiction

    need_execution_mode = not wp_meta.execution_mode
    need_owned_files = not wp_meta.owned_files and not owned_files_explicitly_empty
    if not (need_execution_mode or need_owned_files):
        return False, [], None

    ownership, infer_warnings = infer_ownership(wp_raw_content, mission_slug)
    changed = False
    if need_execution_mode:
        changed_fields["execution_mode"] = str(ownership.execution_mode)
        bld.set(execution_mode=str(ownership.execution_mode))
        changed = True
    if need_owned_files:
        changed_fields["owned_files"] = list(ownership.owned_files)
        bld.set(owned_files=list(ownership.owned_files))
        changed = True
    if not wp_meta.authoritative_surface:
        changed_fields["authoritative_surface"] = ownership.authoritative_surface
        bld.set(authoritative_surface=ownership.authoritative_surface)
        changed = True
    return changed, infer_warnings, None


def _bootstrap_one_wp(
    wp_file: Path,
    state: _BootstrapState,
    wp_dependencies: dict[str, list[str]],
    wp_requirement_refs: dict[str, list[str]],
    wps_manifest: WpsManifest | None,
    mission_slug: str,
    repo_root: Path,
    target_branch: str,
    *,
    merge_target_branch: str | None,
    validate_only: bool,
    json_output: bool,
) -> str | None:
    """Phase: bootstrap ONE WP's 8-field inference in memory, mutating ``state`` (T071).

    Extracted from :func:`_run_bootstrap_loop`'s per-file body, unchanged
    behaviourally: writes are still only queued (``state.pending_writes``),
    never performed here (INV-6).

    Returns:
        The WP id when an ownership contradiction was recorded for it (the
        caller collects these across the whole scan and raises once,
        :func:`_raise_ownership_contradictions_if_any`); ``None`` otherwise,
        including when the filename does not match a WP id or the file is
        unreadable (both skip silently, as before).
    """

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    wp_id_match = re.match(r"^(WP\d{2})(?:[-_.]|$)", wp_file.name)
    if not wp_id_match:
        return None
    wp_id: str = wp_id_match.group(1)

    raw_content = wp_file.read_text(encoding="utf-8")
    has_dependencies_line = _raw_frontmatter_has_field(raw_content, "dependencies")
    # #3941: a legacy string-form dependencies value ("[]", "WP01, WP02",
    # bare WP01) parses to the same list WPMetadata would write, so the
    # value comparison alone never flags it — normalize it to the
    # canonical list form on this run's write.
    dependencies_string_form = has_dependencies_line and _raw_frontmatter_dependencies_is_string_form(wp_file)
    try:
        wp_meta, body = _mf._read_wp_frontmatter(wp_file)
    except Exception as e:  # noqa: BLE001 — surface but skip unreadable WPs
        if not json_output:
            _mf.console.print(f"[yellow]Warning:[/yellow] Could not read {wp_file.name}: {e}")
        return None

    _enforce_charter_activation_gate(wp_meta, wp_id, repo_root)

    parsed_deps = wp_dependencies.get(wp_id, [])
    existing_deps = list(wp_meta.dependencies)
    if wps_manifest is None and not parsed_deps and existing_deps:
        deps = existing_deps
        state.preserved_wps.append(wp_id)
    else:
        deps = parsed_deps

    requirement_refs = wp_requirement_refs.get(wp_id, [])
    state.work_packages.append({"id": wp_id, "title": wp_meta.display_title, "dependencies": deps, "requirement_refs": requirement_refs})

    bld = wp_meta.builder()
    frontmatter_changed, changed_fields = _apply_bootstrap_fields(
        bld,
        wp_meta,
        deps=deps,
        has_dependencies_line=has_dependencies_line,
        requirement_refs=requirement_refs,
        target_branch=target_branch,
        merge_target_branch=merge_target_branch,
        dependencies_string_form=dependencies_string_form,
    )
    own_changed, infer_warnings, ownership_contradiction = _apply_ownership_inference(
        bld, wp_meta, wp_file.read_text(encoding="utf-8"), mission_slug, changed_fields
    )
    if ownership_contradiction is not None:
        state.ownership_contradictions.append(ownership_contradiction)
        return wp_id
    state.ownership_warnings.extend(infer_warnings)
    frontmatter_changed = frontmatter_changed or own_changed

    updated_meta = bld.build() if frontmatter_changed else wp_meta
    state.inmemory_frontmatter[wp_id] = updated_meta
    state.inmemory_bodies[wp_id] = body

    for warning in detect_post_integration_acceptance(raw_content, list(updated_meta.owned_files)):
        state.post_integration_acceptance_warnings.append(f"{wp_id}: {warning}")

    if frontmatter_changed:
        if not validate_only:
            state.pending_writes.append((wp_file, updated_meta, body))
            state.pending_deltas[wp_file] = dict(changed_fields)
        else:
            state.would_modify.append({"wp_id": wp_id, "changes": changed_fields})
        state.updated_count += 1
        if wp_id not in state.preserved_wps:
            state.modified_wps.append(wp_id)
    elif wp_id not in state.preserved_wps:
        state.unchanged_wps.append(wp_id)
    return None


def _run_bootstrap_loop(
    wp_files: list[Path],
    dep_resolution: _DependencyResolution,
    wps_manifest: WpsManifest | None,
    mission_slug: str,
    repo_root: Path,
    target_branch: str,
    concern_coverage_warnings: list[str],
    requirement_extraction_warnings: list[str],
    *,
    merge_target_branch: str | None = None,
    validate_only: bool,
    json_output: bool,
) -> _BootstrapState:
    """Phase: the 8-field bootstrap-mutation loop (INV-6 write-guarded).

    Infers all 8 fields in memory for every WP so downstream validation runs
    against post-bootstrap state; disk writes are deferred to
    ``pending_writes`` and only flushed when ``not validate_only``.
    """
    state = _BootstrapState(
        ownership_warnings=list(concern_coverage_warnings),
        requirement_extraction_warnings=list(requirement_extraction_warnings),
        requirement_diagnostics=dep_resolution.requirement_diagnostics,
    )
    wp_dependencies = dep_resolution.wp_dependencies
    wp_requirement_refs = dep_resolution.wp_requirement_refs
    contradicting_wp_ids: list[str] = []

    for wp_file in wp_files:
        contradicting_wp_id = _bootstrap_one_wp(
            wp_file,
            state,
            wp_dependencies,
            wp_requirement_refs,
            wps_manifest,
            mission_slug,
            repo_root,
            target_branch,
            merge_target_branch=merge_target_branch,
            validate_only=validate_only,
            json_output=json_output,
        )
        if contradicting_wp_id is not None:
            contradicting_wp_ids.append(contradicting_wp_id)
    _raise_ownership_contradictions_if_any(state, contradicting_wp_ids, json_output=json_output)
    return state


def _surface_post_integration_acceptance_warnings(state: _BootstrapState, *, json_output: bool) -> None:
    """Mirror post-integration acceptance warnings to human output."""

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    if state.post_integration_acceptance_warnings and not json_output:
        for warning in state.post_integration_acceptance_warnings:
            _mf.console.print(f"[yellow]Warning:[/yellow] {warning}")


def _raise_ownership_contradictions_if_any(state: _BootstrapState, contradicting_wp_ids: list[str], *, json_output: bool) -> None:
    """Raise once after the bootstrap scan when ownership contradictions exist."""

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    if not state.ownership_contradictions:
        return
    error_msg = "Ownership contradiction detected for WP(s) " + ", ".join(contradicting_wp_ids) + ": " + "; ".join(state.ownership_contradictions)
    if json_output:
        _mf._emit_json(
            {
                "error": error_msg,
                "error_code": OWNERSHIP_CONTRADICTION_CODE_CHANGE_EMPTY_OWNED_FILES,
                "ownership_contradiction_wp_ids": contradicting_wp_ids,
                "ownership_contradictions": list(state.ownership_contradictions),
            }
        )
    else:
        _mf.console.print(f"[red]Error:[/red] {error_msg}")
        for msg in state.ownership_contradictions:
            _mf.console.print(f"  - {msg}")
    raise typer.Exit(1) from None


def _assert_no_write_in_validate_only(state: _BootstrapState, *, validate_only: bool) -> None:
    """INV-6 reinforcement: in validate-only mode the write queue MUST be empty.

    The bootstrap loop never appends to ``pending_writes`` under
    ``validate_only`` — this assertion makes the zero-mutation invariant
    explicit (#2056 WP07 / T029).
    """
    if validate_only:
        assert not state.pending_writes, "INV-6 violated: pending frontmatter writes in --validate-only mode"


def _validate_owned_files_not_in_mission_specs(inmemory_frontmatter: dict[str, WPMetadata], *, json_output: bool) -> None:
    """Phase: reject owned_files paths under the mission-specs dir."""

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    invalid_owned_files = _invalid_mission_specs_owned_files(inmemory_frontmatter)
    if not invalid_owned_files:
        return
    error_msg = "WP owned_files cannot include paths under kitty-specs/"
    payload: dict[str, object] = {
        "error": error_msg,
        "error_code": INVALID_WP_OWNED_FILES_KITTY_SPECS,
        "invalid_owned_files": invalid_owned_files,
    }
    if json_output:
        _mf._emit_json(payload)
    else:
        _mf.console.print(f"[red]Error:[/red] {error_msg}")
        for invalid in invalid_owned_files:
            _mf.console.print(f"  - {invalid['wp_id']}: {invalid['path']}")
    raise typer.Exit(1) from None


def _apply_finalize_delta(frontmatter: dict[str, object], wp_file: Path, delta: dict[str, object]) -> None:
    """Apply finalize's field *delta* to the frontmatter just read under the lock (edited in place).

    The base is the work package as it is NOW, through the same typed read bootstrap used, so a field
    another writer landed since (a map-requirements ref) is kept and the legacy-form normalisation of
    the model dump still happens. ``requirement_refs`` keeps its populate-when-empty rule (FR-004,
    #2991), judged on the fresh value: refs another writer set meanwhile are never overwritten.
    """
    from specify_cli.cli.commands.agent import mission_finalize as _mf

    fresh, _body = _mf._read_wp_frontmatter(wp_file)
    effective = {key: value for key, value in delta.items() if not (key == "requirement_refs" and fresh.requirement_refs)}
    merged = fresh.builder().set(**effective).build() if effective else fresh
    frontmatter.clear()
    frontmatter.update(merged.model_dump(exclude_none=True, mode="json"))


def _flush_one_frontmatter_write(wp_file: Path, updated_meta: WPMetadata, body: str, delta: dict[str, object] | None, *, repo_root: Path | None = None) -> None:
    """Write one queued work package: *delta* onto the file as it is under the lock, else the queued model."""
    feature_dir = wp_file.parent.parent
    if delta is None or not wp_file.exists():
        # Nothing recorded to re-apply, or the file does not exist yet: the queued model is all there is.
        with mission_write_lock(feature_dir, repo_root=repo_root):
            write_frontmatter(wp_file, updated_meta.model_dump(exclude_none=True, mode="json"), body)
        return
    locked_update_frontmatter(wp_file, lambda frontmatter: _apply_finalize_delta(frontmatter, wp_file, delta), feature_dir=feature_dir, repo_root=repo_root)


def _flush_frontmatter_writes(state: _BootstrapState, *, validate_only: bool, repo_root: Path | None = None) -> None:
    """Phase: write pending frontmatter to disk (gated on not validate_only).

    Finalize reads every work package long before it flushes, so each write applies its field delta to the
    frontmatter and body read again under the Mission write lock and never writes the in-memory model back
    (mission-writer-followups plan D2, A9).
    """
    if validate_only:
        return
    for wp_file, updated_meta, body in state.pending_writes:
        _flush_one_frontmatter_write(wp_file, updated_meta, body, state.pending_deltas.get(wp_file), repo_root=repo_root)


def _gather_validation_frontmatter(wp_files: list[Path], state: _BootstrapState) -> tuple[dict[str, WPMetadata], dict[str, str]]:
    """Phase: prefer-in-memory-then-disk frontmatter acquisition (FR-031)."""

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    wp_frontmatters: dict[str, WPMetadata] = {}
    wp_bodies: dict[str, str] = {}
    for wp_file in wp_files:
        wp_id_match = re.match(r"^(WP\d{2})(?:[-_.]|$)", wp_file.name)
        if not wp_id_match:
            continue
        wp_id = wp_id_match.group(1)
        with contextlib.suppress(Exception):
            if wp_id in state.inmemory_frontmatter:
                fm_meta = state.inmemory_frontmatter[wp_id]
                wp_body = state.inmemory_bodies[wp_id]
            else:
                fm_meta, wp_body = _mf._read_wp_frontmatter(wp_file)
            wp_bodies[wp_id] = wp_body
            wp_frontmatters[wp_id] = fm_meta
    return wp_frontmatters, wp_bodies


def _validate_ownership_manifests(
    wp_manifests: dict[str, OwnershipManifest],
    wp_frontmatters: dict[str, WPMetadata],
    repo_root: Path,
    state: _BootstrapState,
    *,
    json_output: bool,
) -> None:
    """Phase: ownership overlap + glob-match + audit-coverage validation."""

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    if not wp_manifests:
        return
    wp_dependencies = {wp_id: list(fm.dependencies) for wp_id, fm in wp_frontmatters.items() if getattr(fm, "dependencies", None)}
    ownership_result = _mf._validate_ownership_via_mission(wp_manifests, wp_dependencies)
    for warning in ownership_result.warnings:
        if not json_output:
            _mf.console.print(f"[yellow]Ownership warning:[/yellow] {warning}")
    if not ownership_result.passed:
        error_msg = "Ownership validation failed"
        if json_output:
            _mf._emit_json({"error": error_msg, "ownership_errors": ownership_result.errors})
        else:
            _mf.console.print(f"[red]Error:[/red] {error_msg}")
            for err in ownership_result.errors:
                _mf.console.print(f"  - {err}")
        raise typer.Exit(1) from None

    create_intent = {wp_id: list(fm.create_intent) for wp_id, fm in wp_frontmatters.items() if fm.create_intent}
    glob_result = validate_glob_matches(wp_manifests, repo_root, create_intent=create_intent)
    _record_ownership_glob_diagnostics(glob_result, state, json_output=json_output)
    if not glob_result.passed:
        error_msg = "Ownership validation failed: literal-path owned_files entries match zero files. Fix the paths or add them to 'create_intent'."
        if json_output:
            _mf._emit_json({"error": error_msg, "ownership_literal_path_errors": glob_result.errors})
        else:
            _mf.console.print(f"[red]Error:[/red] {error_msg}")
        raise typer.Exit(1) from None

    codebase_wide = [list(m.owned_files) for m in wp_manifests.values() if m.is_codebase_wide]
    audit_warnings = validate_audit_coverage(codebase_wide, repo_root)
    state.ownership_warnings.extend(audit_warnings)
    if not json_output:
        for warning in audit_warnings:
            _mf.console.print(f"[yellow]Audit coverage warning:[/yellow] {warning}")


def _project_lane_inputs(
    wp_manifests: dict[str, OwnershipManifest],
    wp_dependencies: dict[str, list[str]],
    wp_frontmatters: dict[str, WPMetadata],
    wp_bodies: dict[str, str],
) -> tuple[FinalizationEligibility, dict[str, OwnershipManifest], dict[str, list[str]], dict[str, str]]:
    """Exclude canceled WPs from lane computation inputs."""
    lifecycle_lanes = {wp_id: (fm.lane if fm.lane is not None else Lane.PLANNED) for wp_id, fm in wp_frontmatters.items()}
    eligibility = project_finalization_eligibility(wp_frontmatters.keys(), wp_dependencies, lifecycle_lanes)
    eligible_wp_ids = eligibility.eligible_wp_ids
    eligible_dependencies = {wp_id: list(dependencies) for wp_id, dependencies in eligibility.eligible_dependencies.items()}
    return (
        eligibility,
        filter_by_wp_ids(wp_manifests, eligible_wp_ids),
        eligible_dependencies,
        filter_by_wp_ids(wp_bodies, eligible_wp_ids),
    )


def _raise_stale_canceled_dependencies_if_any(eligibility: FinalizationEligibility, *, json_output: bool) -> None:
    """Reject executable WPs that still depend on canceled prerequisites."""

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    if not eligibility.stale_dependencies:
        return
    records = [stale.to_dict() for stale in eligibility.stale_dependencies]
    error_msg = "Cannot finalize execution lanes: eligible work depends on canceled work packages."
    if json_output:
        _mf._emit_json(
            {
                "error": error_msg,
                "error_code": "STALE_CANCELED_DEPENDENCIES",
                "stale_canceled_dependencies": records,
            }
        )
    else:
        _mf.console.print(f"[red]Error:[/red] {error_msg}")
        for record in records:
            _mf.console.print(f"  - {record['dependent_wp_id']} depends on canceled {record['canceled_dependency_wp_id']}: {record['recovery']}")
    raise typer.Exit(1) from None


def _lane_computation_empty_input_error(
    wp_manifests: dict[str, OwnershipManifest],
    wp_dependencies: dict[str, list[str]],
    wp_frontmatters: dict[str, WPMetadata],
    *,
    all_canceled: bool,
) -> str | None:
    """Return an error for live code-change WPs with missing lane inputs."""
    if all_canceled or (wp_manifests and wp_dependencies):
        return None
    code_change_wp_ids = sorted(
        wp_id
        for wp_id, fm in wp_frontmatters.items()
        if (fm.execution_mode or "code_change") == "code_change" and (fm.lane if fm.lane is not None else Lane.PLANNED) is not Lane.CANCELED
    )
    if not code_change_wp_ids:
        return None
    missing = []
    if not wp_manifests:
        missing.append("ownership manifests")
    if not wp_dependencies:
        missing.append("WP dependencies")
    return "Lane computation aborted: missing " + " and ".join(missing) + ". finalize-tasks cannot write lanes.json without complete tasks and ownership metadata."


def _raise_lane_computation_empty_input_if_needed(
    wp_manifests: dict[str, OwnershipManifest],
    wp_dependencies: dict[str, list[str]],
    wp_frontmatters: dict[str, WPMetadata],
    *,
    all_canceled: bool,
    json_output: bool,
) -> None:
    from specify_cli.cli.commands.agent import mission_finalize as _mf

    error_msg = _lane_computation_empty_input_error(wp_manifests, wp_dependencies, wp_frontmatters, all_canceled=all_canceled)
    if error_msg is None:
        return
    if json_output:
        _mf._emit_json({"error": error_msg, "error_code": LANE_COMPUTATION_ABORTED_EMPTY_INPUTS})
    else:
        _mf.console.print(f"[red]Error:[/red] {error_msg}")
    raise typer.Exit(1) from None


def _record_ownership_glob_diagnostics(
    glob_result: GlobValidationResult,
    state: _BootstrapState,
    *,
    json_output: bool,
) -> None:
    """Record glob diagnostics, rendering them only for human output."""

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    state.ownership_warnings.extend(glob_result.warnings)
    if json_output:
        return
    stderr_console = _mf.err_console
    for note in glob_result.info:
        stderr_console.print(f"[blue]INFO:[/blue] {note}")
    for warning in glob_result.warnings:
        stderr_console.print(f"[yellow]WARNING:[/yellow] Ownership: {warning}")
    if not glob_result.passed:
        for err in glob_result.errors:
            stderr_console.print(f"[red]ERROR:[/red] Ownership: {err}")


def _regenerate_or_report_tasks_md(
    planning_dir: Path,
    wps_manifest: WpsManifest | None,
    mission_slug: str,
    *,
    validate_only: bool,
    json_output: bool,
    repo_root: Path | None = None,
) -> bool:
    """Phase: T017 tasks.md regeneration from wps.yaml (FR-008, FR-011) — #3221.

    In the commit phase this regenerates ``tasks.md`` from the wps.yaml
    manifest. In ``--validate-only`` mode the regeneration is a WRITE to a
    tracked file, so it is skipped (INV-6: zero mutation on disk) and the
    staleness it would repair is REPORTED instead — turning what used to be a
    silent side effect into a diagnostic, so a pre-flight still gets the
    signal without mutating the tree. Returns whether ``tasks.md`` is stale
    relative to wps.yaml (computed from an in-memory regeneration, never from
    a write); always ``False`` when there is no manifest or when the file was
    just (re)written by the commit phase.
    """

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    if wps_manifest is None:
        return False
    generated = generate_tasks_md_from_manifest(wps_manifest, mission_slug)
    tasks_md = planning_dir / TASKS_MD_FILENAME
    if validate_only:
        try:
            on_disk = tasks_md.read_text(encoding="utf-8") if tasks_md.exists() else None
        except (OSError, UnicodeDecodeError):
            # Unreadable tasks.md — the commit-phase regeneration would replace
            # it wholesale, so report it stale rather than crashing a read-only
            # pre-flight on a file it must not touch.
            on_disk = None
        stale: bool = on_disk != generated
        if stale and not json_output:
            _mf.console.print("[yellow]⚠[/yellow] tasks.md is stale relative to wps.yaml; run finalize-tasks without --validate-only to regenerate")
        return stale
    # The manifest decides the content; the write takes the Mission lock like every other tasks.md writer (A10).
    locked_rewrite_text(tasks_md, lambda _current: generated, feature_dir=planning_dir, repo_root=repo_root)
    if not json_output:
        _mf.console.print(f"[green]Regenerated[/green] tasks.md from wps.yaml ({len(wps_manifest.work_packages)} WPs)")
    return False


def _emit_validate_only_report(
    planning_dir: Path,
    mission_slug: str,
    meta: dict[str, object] | None,
    state: _BootstrapState,
    wp_manifests: dict[str, OwnershipManifest],
    wp_dependencies: dict[str, list[str]],
    wp_bodies: dict[str, str],
    target_branch: str,
    *,
    all_canceled: bool = False,
    tasks_md_stale: bool = False,
    json_output: bool,
    owned: OwnedCheckout | None = None,
    planning_sha: PlanningCommitResolution | None = None,
    refresh_status_findings: list[str] | None = None,
    frozen: FrozenLaneMembership | None = None,
) -> None:
    """Phase: emit the --validate-only report (INV-6: zero mutation).

    Runs bootstrap + lane computation in dry-run mode only. The lane preview
    reads back the previous ``lanes.json`` and honours *frozen* (#5573), so its
    ``lane_ids`` match what a real run would write.
    """

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    bootstrap_result = _mf._bootstrap_canonical_state_via_mission(
        planning_dir,
        mission_slug,
        dry_run=True,
        **({"owned": owned} if owned else {}),
    )
    bootstrap_stats = {
        "total_wps": bootstrap_result.total_wps,
        "newly_seeded": bootstrap_result.newly_seeded,
        "already_initialized": bootstrap_result.already_initialized,
    }

    lanes_stats: dict[str, object] = {"computed": False}
    _raise_lane_computation_empty_input_if_needed(
        wp_manifests,
        wp_dependencies,
        state.inmemory_frontmatter,
        all_canceled=all_canceled,
        json_output=json_output,
    )
    if (wp_manifests and wp_dependencies) or all_canceled:
        from specify_cli.lanes.compute import compute_lanes as _compute_lanes_validate
        from specify_cli.lanes.persistence import read_lanes_json

        raw_mission_id = meta.get("mission_id") if meta else None
        mission_id = raw_mission_id if isinstance(raw_mission_id, str) else None
        lanes_manifest_dry = _compute_lanes_validate(
            dependency_graph=wp_dependencies,
            ownership_manifests=wp_manifests,
            mission_slug=mission_slug,
            target_branch=target_branch,
            wp_bodies=wp_bodies,
            mission_id=mission_id,
            previous_lanes=read_lanes_json(planning_dir),
            frozen=frozen,
        )
        cr_dry = lanes_manifest_dry.collapse_report
        lanes_stats = {
            "computed": True,
            "count": len(lanes_manifest_dry.lanes),
            "lane_ids": [lane.lane_id for lane in lanes_manifest_dry.lanes],
            "planning_artifact_wps": lanes_manifest_dry.planning_artifact_wps,
            "collapse_report": cr_dry.to_dict() if cr_dry else None,
        }

    would_modify, pin_change = _mf._validate_only_planning_preview(
        planning_dir,
        state.would_modify,
        planning_sha,
    )

    if json_output:
        report: dict[str, object] = {
            "result": "validation_passed",
            "mission_slug": mission_slug,
            "wp_count": len(state.work_packages),
            "validate_only": True,
            "would_modify": would_modify,
            "would_preserve": state.preserved_wps,
            "unchanged": state.unchanged_wps,
            "updated_wp_count": state.updated_count,
            "tasks_md_stale": tasks_md_stale,
            "ownership_warnings": state.ownership_warnings,
            "requirement_extraction_warnings": state.requirement_extraction_warnings,
            "post_integration_acceptance_warnings": state.post_integration_acceptance_warnings,
            "validation": {"bootstrap_preview": bootstrap_stats, "lanes_preview": lanes_stats},
            "message": (
                "All validations passed. A mutating refresh would refuse on the listed status preflight findings."
                if planning_sha is not None and refresh_status_findings
                else (
                    "All validations passed. This is a planning-pin preview; a mutating refresh repeats its safety preflight."
                    if planning_sha is not None
                    else "All validations passed. Run without --validate-only to commit."
                )
            ),
            **state.requirement_diagnostics,
        }
        _mf._add_planning_commit_to_validation_report(report, planning_sha)
        if planning_sha is not None:
            findings = refresh_status_findings or []
            report["planning_refresh_preflight"] = {
                "mutating_refresh_would_refuse_for_status_preflight": bool(findings),
                "status_findings": findings,
            }
        _mf._emit_json(report)
        return
    _mf.console.print("[green]✓[/green] All validations passed (--validate-only mode, no commit)")
    _mf.console.print(f"  Mission: {mission_slug}")
    _mf.console.print(f"  WPs validated: {len(state.work_packages)}")
    _mf.console.print(f"  Would modify: {len(state.would_modify)} WP(s), preserve: {len(state.preserved_wps)}, unchanged: {len(state.unchanged_wps)}")
    _mf._report_validate_only_pin_change(pin_change, planning_sha)
    _mf._report_refresh_status_findings(refresh_status_findings, planning_sha)
    _mf.console.print(f"  Bootstrap: {bootstrap_result.newly_seeded} WPs would be seeded, {bootstrap_result.already_initialized} already initialized")
    if lanes_stats.get("computed"):
        _mf.console.print(f"  Lanes: {lanes_stats['count']} lane(s) would be computed")
        cr_info = lanes_stats.get("collapse_report")
        collapse_report = cr_info if isinstance(cr_info, dict) else {}
        if collapse_report.get("independent_wps_collapsed", 0) > 0:
            _mf.console.print(
                f"[yellow]⚠[/yellow] {collapse_report['independent_wps_collapsed']} independent WP pair(s) "
                f"collapsed into same lane. Run with --json to see details."
            )


def _emit_local_canonical_events(
    planning_dir: Path,
    mission_slug: str,
    repo_root: Path,
    work_packages: list[dict[str, object]],
    *,
    json_output: bool,
    owned: OwnedCheckout | None = None,
) -> None:
    """Phase: persist local WPCreated + TasksCompleted before bootstrap seeding.

    ``owned`` (item 6): when a fact is held, WPCreated and TasksCompleted are written against
    ``owned.repository_root`` directly instead of re-deriving R from the log
    path (``get_main_repo_root`` walk) after the fact was minted.

    WP15/T080 (FR-003): the write directory is resolved through
    ``PlacementSeam.write_dir(STATUS_STATE)`` — the single write-location
    authority — so these two lifecycle events land in the SAME coordination
    log ``move-task`` later appends to, never forked into a second copy under
    the repository-root checkout's ``planning_dir``. ``planning_dir`` stays
    the anchor for the PRIMARY-partition reads below (the WP task-file glob,
    the ``tasks.md`` existence check) — only the WRITE target moves.

    WP15 cycle 2 (B3, HIGH, FR-003a): ``write_dir`` is resolved OUTSIDE the
    best-effort ``try`` below and its exceptions are NEVER caught here. A
    named write-location refusal (a deleted or remote-only coordination
    branch, a seed fork, a held status lock) must fail finalize closed with
    the refusal's own recovery hint, in both text and JSON mode -- not
    report ``result: success`` while WPCreated/TasksCompleted were written
    nowhere. The best-effort ``except Exception`` below stays scoped to the
    ACTUAL emission calls, which were always non-blocking by design (a
    genuinely unexpected emission failure, e.g. a malformed WP dict, still
    degrades to a console warning rather than aborting finalize).
    """

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    from mission_runtime import placement_seam

    status_write_dir = placement_seam(repo_root, mission_slug, owned=owned).write_dir(MissionArtifactKind.STATUS_STATE).path
    try:
        from specify_cli.status import TASKS_COMPLETED, emit_artifact_phase, emit_wp_created_local

        for wp in work_packages:
            wp_id = str(wp["id"])
            wp_path: str | None = None
            try:
                candidate = next(iter(sorted((planning_dir / "tasks").glob(f"{wp_id}*.md"))), None)
                if candidate is not None:
                    wp_path = str(candidate.relative_to(repo_root))
            except Exception:  # noqa: BLE001 — best-effort path resolution
                wp_path = None
            emit_wp_created_local(
                status_write_dir,
                mission_slug=mission_slug,
                wp_id=wp_id,
                wp_title=str(wp.get("title") or wp_id),
                wp_path=wp_path,
                depends_on=list(cast(list[str], wp.get("dependencies") or [])),
                actor=FINALIZE_TASKS_COMMAND_NAME,
                repo_root=owned.repository_root if owned else None,
            )

        tasks_artifact = planning_dir / TASKS_MD_FILENAME
        tasks_artifact_rel: str | None = None
        if tasks_artifact.exists():
            try:
                tasks_artifact_rel = str(tasks_artifact.relative_to(repo_root))
            except ValueError:
                tasks_artifact_rel = str(tasks_artifact)
        emit_artifact_phase(
            status_write_dir,
            event_type=TASKS_COMPLETED,
            mission_slug=mission_slug,
            actor=FINALIZE_TASKS_COMMAND_NAME,
            artifact_path=tasks_artifact_rel or TASKS_MD_FILENAME,
            wp_count=len(work_packages),
            repo_root=owned.repository_root if owned else None,
        )
    except Exception as local_wp_exc:  # noqa: BLE001 — non-blocking emission
        if not json_output:
            _mf.console.print(f"[yellow]Warning:[/yellow] Local canonical WPCreated/TasksCompleted persistence failed: {local_wp_exc}")
