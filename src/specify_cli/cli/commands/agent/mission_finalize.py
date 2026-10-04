"""finalize-tasks command family for ``agent mission`` (#2056 WP07).

This leaf module owns ``finalize_tasks`` — the largest single function in the
pre-decomposition ``mission.py`` (1227 LOC) — plus its two dedicated helpers
``_collect_finalize_artifacts`` and ``_branch_tree_relative_path``. The body is
decomposed into ≤15-CC phase helpers, each with focused tests in
``test_mission_finalize_phases.py``.

INV-6 (the ``--validate-only`` zero-mutation invariant) is preserved exactly:
the bootstrap loop infers all 8 fields in memory but the disk-write phase is
guarded by ``frontmatter_changed and not validate_only`` and the validate-only
report path returns BEFORE any committing/seeding writer runs. An explicit
assertion (``_assert_no_write_in_validate_only``) reinforces the guard. The
T017 tasks.md regeneration — a tracked-file write that bypassed the
frontmatter queue (#3221) — is likewise skipped in validate-only mode, with
its staleness reported instead of repaired, so the invariant covers every
tracked-file write the command performs.

One-way leaf (INV-8): imports lower layers + sibling Seam B/C/D leaves only at
module scope. The cross-cutting symbols the finalize tests patch on the
``mission`` module (``locate_project_root`` /
``_find_feature_directory`` / ``run_command``) are resolved
THROUGH the ``mission`` module at call time so the historical
``mission.<name>`` patch seams keep working without an import cycle. The
command is defined here as a plain callable; ``mission`` registers it on its
Typer ``app`` and re-exports the public names (WP09 finalizes the sweep).

Behavior is preserved byte-for-byte from the pre-decomposition ``mission.py``;
the WP01 golden harness is the regression net. ``_stage_finalize_artifacts_in_
coord_worktree`` / ``_resolve_planning_placement`` / ``_planning_commit_worktree``
are NOT relocated here — WP08 moves them to ``commit_router``.
"""

from __future__ import annotations

import contextlib
import contextvars
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Annotated, Final, NoReturn, cast

import typer

if TYPE_CHECKING:
    from specify_cli.coordination.commit_router import CommitRouterResult
    from specify_cli.git.protection_policy import ProtectionPolicy
from specify_cli.cli.console import console
from specify_cli.cli.console import err_console

from kernel._safe_re import re
from kernel.git import GitCommandError, StatusEntry, changed_paths, status_entries
from kernel.paths import repo_tree_path
from mission_runtime import ActionContextError, MissionArtifactKind, TopologyManifestMismatch, mission_file_basenames_for_kind
from specify_cli.core.checkout_identity import CheckoutIdentity, Intent, resolve_checkout_identity
from specify_cli.core.commit_guard import GuardCapability
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.dependency_graph import detect_cycles, validate_dependencies
from specify_cli.core.vcs.git import capture_branch_tip
from specify_cli.core.paths import (
    get_main_repo_root,
    get_status_read_root,
    load_meta_fail_closed,
)
from mission_runtime import OwnedCheckout
from specify_cli.cli.commands._owned_checkout import (
    OwnedCheckoutOption,
    emit_owned_refusal,
    owned_checkout_option,
    resolve_owned_or_adopt,
    stale_copy_payload,
)
from specify_cli.core.owned_mission import LIFECYCLE_OWNED_TOPOLOGIES, require_unstaged_index
from specify_cli.frontmatter import write_frontmatter
from specify_cli.missions._resolve_planning_branch import PlanningBranchResolutionFailed
from specify_cli.lanes.models import LanesManifest
from specify_cli.lanes.planning_commit_classify import PinClass, classify_recorded_pin
from specify_cli.ownership import infer_ownership
from specify_cli.ownership.audit_targets import validate_audit_coverage
from specify_cli.ownership.inference import detect_post_integration_acceptance
from specify_cli.ownership.frontmatter_source import (
    FinalizeFrontmatterSource,
    resolve_wp_manifests,
)
from specify_cli.ownership.models import OwnershipManifest
from specify_cli.ownership.validation import (
    GlobValidationResult,
    ValidationResult,
    validate_glob_matches,
)
from specify_cli.status import BootstrapResult, Lane, WPMetadata, _Builder
from specify_cli.requirement_mapping import (
    FAILING_REASONS,
    grammar,
    read_all_wp_raw_requirement_refs,
)
from specify_cli.core.wps_manifest import (
    WpsManifest,
    check_concern_refs_coverage,
    dependencies_are_explicit,
    generate_tasks_md_from_manifest,
    load_wps_manifest,
)

from specify_cli.cli.commands.agent.mission_check_prerequisites import (
    _read_meta_for_emission,
)
from specify_cli.cli.commands.agent.mission_feature_resolution import (
    _build_setup_plan_detection_error,
    _resolve_mission_dir_name_primary_anchored,
)
from specify_cli.cli.commands.agent.finalize_status_surface import StatusSurfaceGuard, StatusSurfaceLeftover
from specify_cli.cli.commands.agent.finalization_eligibility import (
    FinalizationEligibility,
    filter_by_wp_ids,
    project_finalization_eligibility,
)
from specify_cli.cli.commands.agent.mission_parsing import (
    _with_cli_version,
    _extract_wp_ids_from_task_files,
    _find_undeclared_requirement_citations,
    _invalid_mission_specs_owned_files,
    _owned_files_yaml_is_explicit_empty_list,
    _parse_requirement_ids_from_spec_md,
    _parse_requirement_refs_from_tasks_md,
    _raw_frontmatter_dependencies_is_string_form,
    _raw_frontmatter_has_field,
)

logger = logging.getLogger(__name__)

TASKS_MD_FILENAME = "tasks.md"
ISSUE_MATRIX_FILENAME = "issue-matrix.md"
META_JSON_FILENAME = "meta.json"
FINALIZE_TASKS_COMMAND_NAME = "spec-kitty agent mission finalize-tasks"
INVALID_WP_OWNED_FILES_KITTY_SPECS = "INVALID_WP_OWNED_FILES_KITTY_SPECS"
PROJECT_ROOT_NOT_FOUND = "Could not locate project root"
OWNERSHIP_CONTRADICTION_CODE_CHANGE_EMPTY_OWNED_FILES = "OWNERSHIP_CONTRADICTION_CODE_CHANGE_EMPTY_OWNED_FILES"
LANE_COMPUTATION_ABORTED_EMPTY_INPUTS = "LANE_COMPUTATION_ABORTED_EMPTY_INPUTS"

# SK3466-REV-001 / #2938: the ONLY meta.json fields finalize-tasks itself writes
# (via the explicit override or legacy PR-bound normalization). A pending
# meta.json delta confined to these fields —
# whether produced by THIS invocation's own persist call or dangling from an
# earlier crashed finalize-tasks run (SK3466-RR-001) — is finalize-tasks'
# business regardless of which run produced it. A delta touching any OTHER
# field (e.g. ``vcs``/``vcs_locked_at``, written by ``implement``'s
# ``_ensure_vcs_in_meta`` -> ``set_vcs_lock`` even under ``--no-auto-commit``)
# belongs to a different command and must not silently ride finalize-tasks'
# commit. See ``_meta_json_delta_is_finalize_attributable``.
FINALIZE_ATTRIBUTABLE_META_FIELDS = frozenset({"target_branch", "merge_target_branch"})

# Dynamic alias mirror of the canonical ``mission-specs`` validator (the
# KITTY_SPECS_DIR identifier form, built via ``.replace("-", "_")`` to avoid a
# raw mission-spec literal in source). Mirrors mission.py's globals() injection
# so the same symbol is resolvable here too.
globals()["_invalid_" + KITTY_SPECS_DIR.replace("-", "_") + "_owned_files"] = _invalid_mission_specs_owned_files


# FR-007/R-12 (WP13 T074): the additive ``stale_repository_root_copy`` envelope
# key for the CURRENT owned invocation, or ``None`` (non-owned / not yet
# resolved). Bound by ``finalize_tasks`` after the owned fact resolves and
# merged into EVERY payload ``_emit_json`` prints -- success, validate-only, the
# generic error envelope AND the many gate-specific ``typer.Exit`` refusals that
# emit their own JSON -- so no emitter has to remember it. An explicitly
# supplied key in a payload stays authoritative.
#
# Why a scoped ContextVar and not threading ``owned`` through the emitters:
# roughly 30 gate helpers (dependency graph, requirement mapping, ownership,
# lane compute, ...) emit their own refusal JSON and have no other reason to
# know about an owned checkout; adding an ``owned`` parameter to each would
# widen ~30 signatures and let one forgotten call site silently drop the key
# again (the FR-007 defect this replaced). The binding is invocation-scoped:
# ``finalize_tasks`` sets it under a ``token`` and ``reset``s it in a
# ``finally``, so it can never outlive the owned run that bound it.
_OWNED_ENVELOPE_EXTRAS: contextvars.ContextVar[dict[str, object] | None] = contextvars.ContextVar("finalize_owned_envelope_extras", default=None)


def _emit_json(payload: dict[str, object]) -> None:
    """Emit ``payload`` as JSON via the ``mission`` module's ``_emit_json``.

    Routing every finalize JSON emission through the ``mission`` module (rather
    than importing ``_emit_json`` directly) preserves the historical
    ``mission._emit_json`` patch seam exercised by callers that invoke
    ``mission.finalize_tasks`` directly.
    """
    from specify_cli.cli.commands.agent import mission as _mission

    extras = _OWNED_ENVELOPE_EXTRAS.get()
    if extras:
        payload = {**{key: value for key, value in extras.items() if key not in payload}, **payload}
    _mission._emit_json(payload)


# ---------------------------------------------------------------------------
# Cross-cutting indirection (#2056 WP07): resolve the symbols the finalize test
# suites patch on the ``mission`` module THROUGH that module at call time, so the
# historical ``mission.<name>`` patch seams keep working after the relocation
# without an import cycle. The direct module-scope imports above are kept for the
# type annotations + non-patched call sites; these wrappers are used wherever a
# test patches the name (``read_wp_frontmatter`` / ``bootstrap_canonical_state``
# / ``validate_ownership`` / ``_resolve_planning_branch`` are spied/replaced by
# ``test_feature_finalize_bootstrap.py`` and friends).
# ---------------------------------------------------------------------------


def _read_wp_frontmatter(wp_file: Path) -> tuple[WPMetadata, str]:
    """Route ``read_wp_frontmatter`` through ``mission`` (patch seam)."""
    from specify_cli.cli.commands.agent import mission as _mission

    frontmatter: tuple[WPMetadata, str] = _mission.read_wp_frontmatter(wp_file)
    return frontmatter


def _resolve_planning_branch_via_mission(repo_root: Path, primary_dir: Path, *, target_branch_override: str | None) -> str:
    """Route ``_resolve_planning_branch`` through ``mission`` (patch seam)."""
    from specify_cli.cli.commands.agent import mission as _mission

    return _mission._resolve_planning_branch(repo_root, primary_dir, target_branch_override=target_branch_override)


def _bootstrap_canonical_state_via_mission(
    planning_dir: Path,
    mission_slug: str,
    *,
    dry_run: bool,
    capability: GuardCapability | None = None,
    owned: OwnedCheckout | None = None,
) -> BootstrapResult:
    """Route ``bootstrap_canonical_state`` through ``mission`` (patch seam)."""
    from specify_cli.cli.commands.agent import mission as _mission

    if owned is not None:
        # T073 (WP13): threads the ``owned=`` fact -- the same value object
        # every per-WP seed in the loop below reuses instead of re-running the
        # ownership claim (#3866).
        return _mission.bootstrap_canonical_state(
            planning_dir,
            mission_slug,
            dry_run=dry_run,
            capability=capability or GuardCapability.STANDARD,
            repo_root=owned.repository_root,
            owned=owned,
        )
    if capability is None:
        return _mission.bootstrap_canonical_state(planning_dir, mission_slug, dry_run=dry_run)
    return _mission.bootstrap_canonical_state(planning_dir, mission_slug, dry_run=dry_run, capability=capability)


def _validate_ownership_via_mission(wp_manifests: dict[str, OwnershipManifest], wp_dependencies: dict[str, list[str]]) -> ValidationResult:
    """Route ``validate_ownership`` through ``mission`` (patch seam)."""
    from specify_cli.cli.commands.agent import mission as _mission

    return _mission.validate_ownership(wp_manifests, wp_dependencies)


# ---------------------------------------------------------------------------
# Finalize artifact helpers (relocated verbatim from mission.py — WP07 / T027)
# ---------------------------------------------------------------------------


def _branch_tree_relative_path(file_path: Path, repo_root: Path) -> str:
    """Return the path as it appears in the current branch tree.

    Delegates to the canonical worktree-aware seam
    (:func:`specify_cli.missions._substantive.repo_tree_path`) so the
    worktree-strip and POSIX-normalization logic (#2836) lives in exactly one
    place rather than being maintained as a second copy here. Raises
    ``ValueError`` when ``file_path`` is not under ``repo_root`` (unchanged).
    """
    return repo_tree_path(file_path, repo_root)[1]


def _collect_finalize_artifacts(
    feature_dir: Path,
    tasks_dir: Path,
    lanes_path: Path | None = None,
) -> list[Path]:
    """Return all deterministic artifacts finalize-tasks may need to commit.

    FIX-M2-05: dropped the ``mission_slug`` parameter (positional 3rd arg in
    prior revisions). It existed solely to build the dossier snapshot's path
    (``feature_dir / ".kittify" / "dossiers" / mission_slug / "snapshot-latest.json"``)
    for inclusion as a commit candidate -- an inclusion that itself violated
    ``contracts/dossier-snapshot-ownership.md`` (D1) and is removed below.
    None of the remaining deterministic candidates need the mission slug
    (they resolve entirely from ``feature_dir`` / ``tasks_dir`` /
    ``lanes_path``), so the parameter is genuinely dead, not merely unused —
    callers pass only what this function still reads.

    ``meta.json`` (SK3466-RR-001) is an UNCONDITIONAL CANDIDATE here — not
    gated on whether THIS invocation's own ``--target-branch`` persist call
    fired. A prior, crashed finalize-tasks run can leave meta.json rewritten
    on disk but never committed; a later run whose override happens to match
    that dangling value reads as a no-op from
    ``_persist_target_branch_override``'s point of view (``previous_value ==
    target_branch``) and would never re-fold it into a commit if inclusion
    depended on that call's own outcome. Making meta.json a first-class,
    always-considered CANDIDATE closes that half of the defect class by
    construction (DIRECTIVE_043).

    UNLIKE ``tasks.md`` / ``status.json`` / the lane manifest, meta.json has a
    writer OUTSIDE finalize-tasks: ``implement --no-auto-commit`` can leave
    its own unrelated meta.json edit (``vcs``/``vcs_locked_at``) staged but
    deliberately uncommitted (SK3466-REV-001). Being a candidate here does
    NOT mean meta.json is unconditionally committed — ``_commit_finalize_
    artifacts`` additionally attributes any pending delta by WHICH FIELDS
    changed (:func:`_meta_json_delta_is_finalize_attributable`) before
    folding it in, so a foreign writer's edit is not silently swept into this
    commit just because it happens to be dirty at the same time.
    """
    candidates: list[Path] = [
        feature_dir / "status.events.jsonl",
        feature_dir / "status.json",
        feature_dir / TASKS_MD_FILENAME,
        # partition-authority-residuals-01M021K9 WP06 (#2937 / FR-009 / D-001
        # default): the wps.yaml manifest is the finalize INPUT that tasks.md is
        # regenerated from. Version it here so the finalized checkpoint can
        # reproduce its own state (INV-5) — it classifies to the PRIMARY-partition
        # TASKS_INDEX kind, so the commit router routes it to target_branch with
        # tasks.md.
        feature_dir / "wps.yaml",
        feature_dir / META_JSON_FILENAME,
        # coord-artifact-single-home-01M3V4BE WP15 (B6, cycle 2): the root copy
        # of ``acceptance-matrix.json`` is DELIBERATELY NOT a candidate here
        # any more -- the owning copy (COORD for a coordination-routed
        # Mission, PRIMARY otherwise) is resolved exclusively through
        # ``_coord_candidate_dirt`` (``write_dir(ACCEPTANCE_MATRIX)``, T081).
        # Including a stale root copy here would feed it into the SAME
        # combined ``files`` tuple the coordination copy rides, and the
        # router's still-unflipped ACCEPTANCE_MATRIX legacy ``copy2`` (the
        # "owning copy wins" flip is WP20's commit_router.py change, out of
        # this WP's owned_files) would then overwrite the real coordination
        # content with root residue (Decision `plan.design.translate-if-
        # present-kinds`).
        # write-surface-coherence WP08 (#2804 / #2404 T043 / G3): sweep the
        # terminal ``issue-matrix.json`` — the retired ``issue-matrix.md`` is
        # never authored by any canonical path any more (WP05), so it is no
        # longer a finalize-commit candidate.
        feature_dir / "issue-matrix.json",
        # FIX-M2-05: the dossier snapshot is DELIBERATELY NOT a candidate here.
        # ``contracts/dossier-snapshot-ownership.md`` (D1, mission
        # charter-e2e-827-followups-01KQAJA0 / #845) ratifies
        # ``.kittify/dossiers/<slug>/snapshot-latest.json`` as excluded from
        # version control -- "save_snapshot() ... No staging, no committing,
        # no special branch interaction. The file is just a file." Committing
        # it here (as a prior revision of this function did) violated that
        # contract: once tracked on one branch it is inherited by every lane
        # and coordination worktree that branch touches, and every later
        # fire-and-forget dossier-sync write (mark-status, move-task, merge,
        # …) then leaves that worktree's copy locally modified/uncommitted —
        # exactly the drift ``git/ref_advance.py``'s merge-time
        # dirty-checked-out-worktree resync (#1826) refuses to silently
        # discard. Leaving it off this list keeps every producer honoring the
        # same "just a file" contract move-task's dirty-state preflight
        # already enforces (``status/preflight.py::is_dossier_snapshot``).
    ]
    candidates.extend(sorted(path for path in tasks_dir.iterdir() if path.is_file()))
    if lanes_path is not None:
        candidates.append(lanes_path)

    seen: set[Path] = set()
    artifacts: list[Path] = []
    for candidate in candidates:
        if candidate.exists() and candidate not in seen:
            artifacts.append(candidate)
            seen.add(candidate)
    return artifacts


def _meta_json_delta_is_finalize_attributable(meta_path: Path, repo_root: Path) -> bool:
    """Decide whether a pending meta.json edit is finalize-tasks' own business (SK3466-REV-001).

    ``_collect_finalize_artifacts`` treats meta.json as an unconditional
    CANDIDATE (SK3466-RR-001) so a dangling write from an earlier CRASHED
    finalize-tasks run still gets folded into this run's commit even though
    it wasn't produced by THIS invocation's own persist call. But
    ``implement --no-auto-commit`` can ALSO leave meta.json dirty — via
    ``_ensure_vcs_in_meta`` -> ``set_vcs_lock`` writing ``vcs``/``vcs_locked_
    at`` unconditionally on a WP's first claim, deliberately left uncommitted
    when auto-commit is disabled — and that edit belongs to a DIFFERENT
    command, not to finalize-tasks.

    Rather than attributing a pending edit to a particular PRIOR INVOCATION
    (unrecoverable — no invocation identity survives a crash, and a
    dangling write and a foreign write look identical on disk), this
    attributes by WHICH FIELDS changed: finalize-tasks is the sole writer of
    ``target_branch`` in meta.json (:func:`specify_cli.mission_metadata.
    set_target_branch`), so a delta confined to
    ``FINALIZE_ATTRIBUTABLE_META_FIELDS`` — whichever run produced it — is
    finalize-tasks' business. A delta touching any OTHER field is a foreign
    writer's business and must not silently ride this commit.

    Mixed case: when BOTH a dangling ``target_branch`` write and a foreign
    field write are pending simultaneously, this returns ``False`` — the
    WHOLE file is excluded from this commit, not just the foreign field.
    meta.json is a single JSON blob; there is no way to commit "only the
    target_branch part" of a working-tree file without finalize-tasks
    hand-constructing and writing a synthetic merged meta.json itself, which
    would make it a second writer of fields (``vcs``) it does not own —
    reintroducing exactly the kind of implicit cross-command coupling this
    fix closes. Excluding the whole file is the smallest-blast-radius choice:
    the dangling ``target_branch`` fix simply waits for a future run where
    the foreign field is no longer pending (e.g. once ``implement`` itself
    commits it).

    Both sides of the diff are decoded via :func:`kernel.meta_decode.
    decode_meta` — the single canonical meta.json decode primitive (FR-010) —
    rather than a hand-rolled ``json.loads``, so this function does not
    become a second, independent meta.json decoder.

    Returns ``True`` (attributable — keep as a commit candidate) when:
    - meta.json is not tracked at ``HEAD`` yet (nothing to diff against — the
      whole file is new content), or
    - the committed (``HEAD``) side fails to parse as JSON while the working-tree
      copy is valid (our fix supersedes a malformed committed copy), or
    - the changed-field set is empty or a subset of
      ``FINALIZE_ATTRIBUTABLE_META_FIELDS``.

    Returns ``False`` (exclude the whole file) when the working-tree copy is
    unreadable or malformed. finalize-tasks did NOT commit meta.json before
    #3466, so the conservative default for a corrupt on-disk file is to never
    commit it -- committing a truncated meta.json would break every fail-closed
    reader.
    """
    from kernel.meta_decode import decode_meta
    from specify_cli.cli.commands.agent import mission as _mission

    try:
        rel_path = _branch_tree_relative_path(meta_path, repo_root)
    except ValueError:
        return True

    return_code, committed_text, _stderr = _mission.run_command(
        ["git", "show", f"HEAD:{rel_path}"],
        check_return=False,
        capture=True,
        cwd=repo_root,
    )
    if return_code != 0:
        # Not tracked at HEAD (brand-new meta.json) -- the whole file is new
        # content, not a foreign edit riding alongside ours.
        return True

    try:
        current_text = meta_path.read_text(encoding="utf-8")
    except OSError as read_exc:
        # #3466 landing: a working-tree meta.json that cannot be read is
        # EXCLUDED, not committed. finalize-tasks never committed meta.json
        # before this change, so an unreadable on-disk copy must not be swept
        # into the finalize commit -- doing so risks committing a truncated or
        # corrupt file over readers that fail closed on it.
        logger.warning(
            "#3466: could not read %s to compute finalize-commit attribution (%s); excluding meta.json from the finalize commit",
            meta_path,
            read_exc,
        )
        return False
    committed_meta = decode_meta(committed_text, on_malformed="none")
    current_meta = decode_meta(current_text, on_malformed="none")
    if current_meta is None:
        # #3466 landing: the working-tree meta.json is malformed (e.g. truncated
        # by a crash mid-write). finalize-tasks did NOT commit meta.json before
        # this change, so the conservative default is to EXCLUDE a corrupt
        # on-disk file -- committing it would break every fail-closed reader.
        logger.warning(
            "#3466: working-tree %s failed to decode as JSON while computing finalize-commit attribution for %s; excluding meta.json from the finalize commit",
            META_JSON_FILENAME,
            meta_path,
        )
        return False
    if committed_meta is None:
        # The committed (HEAD) copy is malformed but our working-tree copy is
        # valid: include it -- committing the good file over a bad HEAD is safe
        # and is exactly the corrective write finalize-tasks exists to make.
        logger.warning(
            "#3466: HEAD %s failed to decode as JSON while computing "
            "finalize-commit attribution for %s; including the valid "
            "working-tree meta.json in the finalize commit",
            META_JSON_FILENAME,
            meta_path,
        )
        return True

    changed_keys = {key for key in {*committed_meta.keys(), *current_meta.keys()} if committed_meta.get(key) != current_meta.get(key)}
    return changed_keys <= FINALIZE_ATTRIBUTABLE_META_FIELDS


# ---------------------------------------------------------------------------
# Phase helpers (each ≤15 CC — #2056 WP07 / T028)
# ---------------------------------------------------------------------------


def _resolve_repo_root(json_output: bool) -> Path:
    """Phase: locate the project root or exit with the canonical error.

    Routes ``locate_project_root`` through the ``mission`` module so the
    ``mission.locate_project_root`` patch seam keeps working.
    """
    from specify_cli.cli.commands.agent import mission as _mission

    repo_root: Path | None = _mission.locate_project_root()
    if repo_root is None:
        if json_output:
            _emit_json({"error": PROJECT_ROOT_NOT_FOUND})
        else:
            console.print(f"[red]Error:[/red] {PROJECT_ROOT_NOT_FOUND}")
        raise typer.Exit(1)
    return repo_root


def _resolve_mission_slug(repo_root: Path, feature: str | None, *, json_output: bool) -> str:
    """Phase: resolve the mission slug, primary-anchored (Seam D).

    #11 / #1718 / #1692: anchor primary-first (no coord-existence gate); only
    when the primary surface also cannot resolve the handle do we surface the
    structured detection error. Routes ``_find_feature_directory`` through the
    ``mission`` module to preserve the patch seam.
    """
    from specify_cli.cli.commands.agent import mission as _mission
    from specify_cli.missions._read_path_resolver import MissionSelectorAmbiguous

    cwd = Path.cwd().resolve()
    ambiguous: ActionContextError | None
    try:
        mission_dir_name: str | None = _resolve_mission_dir_name_primary_anchored(repo_root, feature)
    except MissionSelectorAmbiguous as ambiguous_error:
        ambiguous = ActionContextError(ambiguous_error.error_code, str(ambiguous_error))
    else:
        ambiguous = None

    if mission_dir_name is not None:
        return mission_dir_name

    try:
        feature_dir: Path = _mission._find_feature_directory(repo_root, cwd, explicit_feature=feature)
    except (ValueError, ActionContextError) as detection_error:
        payload = _build_setup_plan_detection_error(
            repo_root,
            str(ambiguous or detection_error),
            feature,
            error_code=(ambiguous.code if ambiguous is not None else "FEATURE_CONTEXT_UNRESOLVED"),
            command_name="finalize-tasks",
            command_args=["--json"] if json_output else [],
        )
        if json_output:
            _emit_json(payload)
        else:
            console.print(f"[red]Error:[/red] {payload['error']}")
            for slug in cast(list[str], payload.get("available_missions", []))[:10]:
                console.print(f"  - {slug}")
            if "example_command" in payload:
                console.print(f"  {payload['example_command']}")
        raise typer.Exit(1) from None
    return feature_dir.name


def _resolve_target_branch(
    repo_root: Path,
    primary_dir: Path,
    *,
    target_branch_override: str | None,
    json_output: bool,
) -> str:
    """Resolve the planning branch, including the narrow #2938 legacy repair.

    Normal resolution remains metadata-only. A PR-bound legacy mission that
    conflated its protected final target with the planning branch cannot prove
    the original planning branch from current checkout state, so recovery
    requires the operator to name it explicitly with ``--target-branch``.
    """
    try:
        declared_target = _resolve_planning_branch_via_mission(repo_root, primary_dir, target_branch_override=target_branch_override)
    except PlanningBranchResolutionFailed as exc:
        if json_output:
            _emit_json({"error": str(exc), "error_code": exc.error_code})
        else:
            console.print(f"[red]Error:[/red] {exc}")
            console.print("[yellow]Hint:[/yellow] re-run with [bold]--target-branch <ref>[/bold] to override.")
        raise typer.Exit(1) from exc

    meta = load_meta_fail_closed(primary_dir) or {}
    if not meta.get("pr_bound") or meta.get("merge_target_branch"):
        return declared_target
    if target_branch_override and target_branch_override.strip():
        return declared_target

    from specify_cli.git.protection_policy import ProtectionPolicy

    policy = ProtectionPolicy.resolve(repo_root)
    if not policy.is_protected(declared_target):
        return declared_target

    message = (
        "Legacy PR-bound metadata records a protected merge target as its "
        "planning branch, but the original planning branch cannot be proven "
        "from the current checkout. Re-run with --target-branch <planning-ref> "
        "to repair the branch contract explicitly."
    )
    if json_output:
        _emit_json(
            {
                "error": message,
                "error_code": "PR_BOUND_PLANNING_BRANCH_REQUIRED",
            }
        )
    else:
        console.print(f"[red]Error:[/red] {message}")
    raise typer.Exit(1)


def _resolve_merge_target_branch(primary_dir: Path, planning_branch: str) -> str:
    """Resolve final landing without conflating it with planning placement."""
    meta = load_meta_fail_closed(primary_dir) or {}
    explicit_target = meta.get("merge_target_branch")
    if isinstance(explicit_target, str) and explicit_target.strip():
        return explicit_target.strip()

    declared_target = meta.get("target_branch")
    if meta.get("pr_bound") and isinstance(declared_target, str) and declared_target.strip() and declared_target.strip() != planning_branch:
        return declared_target.strip()
    return planning_branch


def _preflight_recovered_pr_bound_contract(
    repo_root: Path,
    planning_dir: Path,
    *,
    planning_branch: str,
    json_output: bool,
) -> None:
    """Refuse #2938 recovery when foreign meta.json changes are pending.

    Recovery rewrites two canonical branch fields. Mixing that write with an
    unrelated dirty field would make the attribution guard exclude meta.json
    from the finalize commit, leaving the repair dangling. Refuse before the
    first finalize mutation so the operator can commit or discard the foreign
    edit explicitly.
    """
    meta = load_meta_fail_closed(planning_dir) or {}
    if not meta.get("pr_bound") or meta.get("target_branch") == planning_branch:
        return
    meta_path = planning_dir / META_JSON_FILENAME
    if _meta_json_delta_is_finalize_attributable(meta_path, repo_root):
        return

    message = (
        "Cannot recover the legacy PR-bound branch contract while foreign "
        "meta.json changes are pending. Commit or discard those changes, then "
        "run finalize-tasks again."
    )
    if json_output:
        _emit_json(
            {
                "error": message,
                "error_code": "PR_BOUND_RECOVERY_FOREIGN_META_DELTA",
            }
        )
    else:
        console.print(f"[red]Error:[/red] {message}")
    raise typer.Exit(1)


def _persist_recovered_pr_bound_contract(
    planning_dir: Path,
    *,
    planning_branch: str,
    merge_target_branch: str,
) -> bool:
    """Normalize #2938 legacy metadata; return whether bytes were written."""
    meta = load_meta_fail_closed(planning_dir) or {}
    if not meta.get("pr_bound") or meta.get("target_branch") == planning_branch:
        return False

    meta["target_branch"] = planning_branch
    meta["merge_target_branch"] = merge_target_branch
    from specify_cli.mission_metadata import write_meta

    write_meta(planning_dir, meta)
    return True


def _enforce_branch_contract_write_ownership(
    primary_dir: Path,
    *,
    invocation_identity: CheckoutIdentity,
    json_output: bool,
) -> None:
    """Refuse branch-contract writes from a checkout that does not own the mission.

    #3786: the invoking checkout arrives as an injected :class:`CheckoutIdentity`
    value object, resolved ONCE at the ``finalize_tasks`` entrypoint (the single
    boundary that legitimately reads ambient state) — this guard never reads
    ``Path.cwd()`` itself. ``invocation_identity.invoking_root`` is the honest
    ambient anchor: the lane worktree itself for a linked worktree, the checkout
    root for an owner invocation — the same root ``get_status_read_root`` yields
    for every linked-worktree/own-root topology, so #812's repository-anchored
    ownership comparison is unchanged for those topologies.
    """
    target_owner = get_status_read_root(primary_dir).resolve()
    target_repository = get_main_repo_root(target_owner).resolve()
    ambient_checkout = invocation_identity.invoking_root.resolve()
    ambient_repository = get_main_repo_root(ambient_checkout).resolve()
    invoking_checkout = ambient_checkout if ambient_repository == target_repository else target_owner
    if invoking_checkout == target_owner:
        return

    message = (
        "Refusing to write: this invocation does not own the target mission "
        f"checkout {target_owner}. Run the command from that checkout, or "
        "target a checkout this invocation owns."
    )
    if json_output:
        _emit_json(
            {
                "error": message,
                "error_code": "CHECKOUT_WRITE_OWNERSHIP_REFUSED",
            }
        )
    else:
        console.print(f"[red]Error:[/red] {message}")
    raise typer.Exit(1)


def _persist_branch_contract_for_finalize(
    primary_dir: Path,
    *,
    planning_branch: str,
    merge_target_branch: str,
    target_branch_override: str | None,
    invocation_identity: CheckoutIdentity,
    json_output: bool,
) -> TargetBranchPersistOutcome:
    """Persist an explicit branch repair atomically and only from its owner."""
    original_target = (load_meta_fail_closed(primary_dir) or {}).get("target_branch")
    needs_write = bool(target_branch_override and target_branch_override.strip() and original_target != planning_branch)
    if needs_write:
        _enforce_branch_contract_write_ownership(
            primary_dir,
            invocation_identity=invocation_identity,
            json_output=json_output,
        )
    recovered = _persist_recovered_pr_bound_contract(
        primary_dir,
        planning_branch=planning_branch,
        merge_target_branch=merge_target_branch,
    )
    if recovered:
        return TargetBranchPersistOutcome(
            persisted=True,
            previous_value=(str(original_target) if original_target is not None else None),
        )
    return _persist_target_branch_override(
        primary_dir,
        planning_branch,
        target_branch_override=target_branch_override,
        json_output=json_output,
    )


@dataclass(frozen=True)
class TargetBranchPersistOutcome:
    """Result of attempting to persist a ``--target-branch`` override (#3466).

    A plain ``bool`` return could not distinguish "no-op: override already
    matched meta.json" from "no-op: the write was attempted and FAILED" —
    SK3466-R-002 found that ambiguity meant a ``--json`` caller had zero
    diagnostic when the write failed, so a subsequent ``PROTECTED_BRANCH_
    REFUSED`` (still reading the stale on-disk value) looked like an
    unexplained recurrence of #3466 rather than a directly attributable
    persist failure. This type makes every arm explicit for callers AND for
    the terminal JSON payload (SK3466-R-003 traceability).

    Attributes:
        persisted: ``True`` only when meta.json was actually rewritten this
            call.
        previous_value: The ``target_branch`` value read from meta.json
            BEFORE this call (``None`` when meta.json was absent/unreadable
            or no override was supplied).
        persist_error: Set only when a write was attempted and raised
            (``ValueError``/``FileNotFoundError``/``MissionMetaReadError``
            from ``set_target_branch`` — SK3466-RR-002 added the last);
            ``None`` for every no-op or successful arm.
    """

    persisted: bool
    previous_value: str | None = None
    persist_error: str | None = None


def _persist_target_branch_override(
    primary_dir: Path,
    target_branch: str,
    *,
    target_branch_override: str | None,
    json_output: bool,
) -> TargetBranchPersistOutcome:
    """Persist an explicit ``--target-branch`` override into meta.json (#3466).

    Every ``target_branch`` reader downstream of finalize-tasks — chiefly the
    WP-status-transition bookkeeping (:func:`specify_cli.status.bootstrap.
    bootstrap_canonical_state`, via :func:`specify_cli.core.paths.
    get_feature_target_branch` / :func:`mission_runtime.resolution.
    resolve_placement_only`) — resolves the mission's ``target_branch`` by
    reading the PRIMARY ``meta.json`` directly. It has no awareness of
    ``target_branch_override``: that value previously lived only in this
    command's own local ``target_branch`` variable, so a mission whose
    meta.json still recorded ``target_branch: "main"`` kept sending WP-status
    bookkeeping at "main" — the protected-branch guard refused it — even when
    the operator passed ``--target-branch <real-branch>`` (the documented
    FR-012 escape hatch never reached that consumer).

    Rather than threading a second override parameter through the shared
    placement/status-transition resolvers (``resolve_placement_only`` /
    ``resolve_write_target_or_degrade`` / ``TransitionRequest`` — a much wider
    blast radius across ~15 call sites in implement/merge/review/sync that have
    no override concept of their own — DIRECTIVE_024 locality-of-change), this
    persists the corrected value through the existing canonical mutation
    helper (:func:`specify_cli.mission_metadata.set_target_branch`), built and
    unit-tested for exactly this purpose but never wired to this CLI flag.
    Every downstream reader then converges on the SAME corrected field with no
    further code changes — DIRECTIVE_044 single canonical authority / 043
    close-the-defect-class-by-construction, rather than a second fallback
    branch.

    A no-op when no override was supplied, when it matches the value already
    on disk (idempotent re-runs), or when meta.json is absent (the rarer
    pre-meta.json legacy case the escape hatch also nominally covers — the
    override still applies in-process via ``target_branch``; there is simply
    no canonical file yet to persist it into). Only ever called from the
    non-``--validate-only`` commit pipeline (INV-6: validate-only performs
    zero writes).

    A failed run must not leave this write dangling in the working tree
    (SK3466-R-001): the caller captures meta.json's pre-call content and
    restores it if a downstream validation gate raises ``typer.Exit`` before
    ``_commit_finalize_artifacts`` folds the (still on-disk) write into the
    finalize commit — see ``_revert_unpersisted_target_branch_override`` in
    ``finalize_tasks``.

    Returns:
        A :class:`TargetBranchPersistOutcome`. ``persisted=True`` only when
        meta.json was actually rewritten this call. :func:`_collect_finalize_
        artifacts` (SK3466-RR-001) treats meta.json as a commit candidate,
        and :func:`_meta_json_delta_is_finalize_attributable` (SK3466-REV-001)
        folds any pending ``target_branch``-only delta into the finalize
        commit — this run's own write, or one dangling from a prior crashed
        run — rather than letting it survive as a dangling working-tree edit;
        this function no longer has to get that right on its own. (A delta
        that ALSO touches a foreign field, e.g. a concurrent ``implement
        --no-auto-commit`` write, is excluded from the commit entirely —
        see that function's docstring for the mixed-case rationale.) Every
        no-op/failure arm carries ``persisted=False`` plus ``previous_
        value``/``persist_error`` so the caller (and the terminal JSON
        payload) can distinguish "already correct" from "write failed"
        (SK3466-R-002/R-003).
    """
    if target_branch_override is None or not target_branch_override.strip():
        return TargetBranchPersistOutcome(persisted=False)
    from specify_cli.core.paths import MissionMetaReadError
    from specify_cli.mission_metadata import load_meta_or_empty, set_target_branch

    meta_path = primary_dir / META_JSON_FILENAME
    if not meta_path.exists():
        return TargetBranchPersistOutcome(persisted=False)
    previous_value_raw = load_meta_or_empty(primary_dir).get("target_branch")
    previous_value = str(previous_value_raw) if previous_value_raw else None
    if previous_value == target_branch:
        return TargetBranchPersistOutcome(persisted=False, previous_value=previous_value)
    try:
        set_target_branch(primary_dir, target_branch)
    except (FileNotFoundError, ValueError, MissionMetaReadError) as persist_exc:
        # FileNotFoundError is a TOCTOU guard only (SK3466-R-004): the
        # ``meta_path.exists()`` check above already returns early on a
        # missing meta.json, so this arm fires only if meta.json is deleted
        # out from under us between that check and set_target_branch's own
        # read — not reachable in the single-process, single-invocation path.
        # MissionMetaReadError (SK3466-RR-002) IS reachable: it fires when
        # meta.json EXISTS but is corrupt/malformed JSON — a realistic shape
        # for the legacy-mission population this --target-branch escape
        # hatch is documented to serve. set_target_branch -> _require_meta ->
        # _load_meta_fail_closed raises this typed RuntimeError subclass
        # (core/paths.py) rather than ValueError; without it here, a corrupt
        # meta.json bypassed this function's structured warning/JSON contract
        # entirely and fell through to finalize_tasks's generic outer
        # ``except Exception`` as an unstructured ``{"error": str(e)}``.
        error_detail = str(persist_exc)
        if not json_output:
            console.print(f"[yellow]Warning:[/yellow] could not persist --target-branch override to meta.json: {error_detail}")
        else:
            # SK3466-R-002: without this, a --json caller gets ZERO
            # diagnostic — meta_json_persisted silently stays False and a
            # later PROTECTED_BRANCH_REFUSED (still reading the stale
            # on-disk value) reads as an unexplained recurrence of #3466
            # instead of a directly attributable persist failure.
            _emit_json(
                {
                    "warning": "target_branch_override_not_persisted",
                    "target_branch_override": target_branch,
                    "detail": error_detail,
                }
            )
        return TargetBranchPersistOutcome(persisted=False, previous_value=previous_value, persist_error=error_detail)
    if not json_output and previous_value is not None:
        # SK3466-R-003: a distinct (non-cyan) notice that a repeat
        # finalize-tasks invocation just permanently rewrote the mission's
        # canonical merge destination — finalize-tasks is documented as
        # repeatable, so a stale/mistaken --target-branch on a routine
        # re-run is otherwise a silent, unflagged overwrite.
        console.print(f"[yellow]Note:[/yellow] target_branch override persisted to meta.json ({previous_value} -> {target_branch})")
    return TargetBranchPersistOutcome(persisted=True, previous_value=previous_value)


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
    spec_md = planning_dir / "spec.md"
    if not spec_md.exists():
        error_msg = f"spec.md not found: {spec_md}"
        if json_output:
            print(json.dumps({"error": error_msg}))
        else:
            console.print(f"[red]Error:[/red] {error_msg}")
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
            policy=_mission_protection_policy(repo_root, mission_slug, owned),
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
            console.print(f"[yellow]Warning:[/yellow] could not scaffold issue-matrix.json: {issue_matrix_exc}")
        return
    if issue_matrix_path is not None and not json_output:
        try:
            rel: Path = issue_matrix_path.relative_to(repo_root)
        except ValueError:
            rel = issue_matrix_path
        console.print(f"[info] Scaffolded {rel}")


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
            console.print(f"[yellow]Warning:[/yellow] could not lint {ISSUE_MATRIX_FILENAME}: {lint_exc}")
        return
    if result.passed or json_output:
        return
    console.print(f"[yellow]Advisory:[/yellow] {ISSUE_MATRIX_FILENAME} has lint finding(s) (non-blocking — does not affect finalize):")
    for diagnostic in result.diagnostics:
        console.print(f"  - {diagnostic['diagnostic_code']}: {diagnostic['message']}")


def _load_manifest(planning_dir: Path, *, json_output: bool) -> WpsManifest | None:
    """Phase: TIER 0 — load the wps.yaml manifest (or None)."""
    try:
        return load_wps_manifest(planning_dir)
    except typer.Exit:
        raise
    except Exception as exc:
        error_msg = f"wps.yaml is present but could not be loaded: {exc}"
        if json_output:
            _emit_json({"error": error_msg})
        else:
            console.print(f"[red]Error:[/red] {error_msg}")
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
            wp_meta, _ = _read_wp_frontmatter(wp_file)
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
    from specify_cli.bulk_edit.gate import (
        ensure_occurrence_classification_ready,
        finalize_tasks_gate_error_payload,
        render_gate_failure,
    )

    result = ensure_occurrence_classification_ready(planning_dir)
    if result.passed:
        return
    if json_output:
        _emit_json(finalize_tasks_gate_error_payload(result))
    else:
        render_gate_failure(result, console)
    raise typer.Exit(1)


def _validate_tasks_md_coverage(tasks_md_dependencies: dict[str, list[str]], expected_wp_ids: list[str], *, json_output: bool) -> None:
    """Phase: verify every WP file matches a parsed tasks.md section."""
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
        _emit_json(payload)
    else:
        console.print(f"[red]Error:[/red] {error_msg}")
        if missing_wp_sections:
            console.print(f"  Missing WP sections: {', '.join(missing_wp_sections)}")
        if extra_wp_sections:
            console.print(f"  Extra WP sections: {', '.join(extra_wp_sections)}")
        console.print(f"  {payload['hint']}")
    raise typer.Exit(1)


def _validate_dependency_graph(wp_dependencies: dict[str, list[str]], *, json_output: bool) -> None:
    """Phase: detect cycles + invalid references in the dependency graph."""
    if not wp_dependencies:
        return
    cycles = detect_cycles(wp_dependencies)
    if cycles:
        error_msg = f"Circular dependencies detected: {cycles}"
        if json_output:
            _emit_json({"error": error_msg, "cycles": cycles})
        else:
            console.print("[red]Error:[/red] Circular dependencies detected:")
            for cycle in cycles:
                console.print(f"  {' → '.join(cycle)}")
        raise typer.Exit(1)

    for wp_id, deps in wp_dependencies.items():
        is_valid, errors = validate_dependencies(wp_id, deps, wp_dependencies)
        if not is_valid:
            error_msg = f"Invalid dependencies for {wp_id}: {errors}"
            if json_output:
                _emit_json({"error": error_msg, "wp_id": wp_id, "errors": errors})
            else:
                console.print(f"[red]Error:[/red] Invalid dependencies for {wp_id}:")
                for err in errors:
                    console.print(f"  - {err}")
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
    console.print(f"[red]Error:[/red] {error_msg}")
    if missing_requirement_refs_wps:
        console.print("[red]Missing requirement refs:[/red]")
        for wp_id in missing_requirement_refs_wps:
            console.print(f"  - {wp_id}")
    if unknown_requirement_refs:
        console.print("[red]Unknown requirement refs:[/red]")
        for wp_id, refs in unknown_requirement_refs.items():
            console.print(f"  - {wp_id}: {', '.join(refs)}")
    if unmapped_functional_requirements:
        console.print("[red]Unmapped functional requirements:[/red]")
        for req_id in unmapped_functional_requirements:
            console.print(f"  - {req_id}")
    if bare_prose_requirement_ids:
        console.print("[red]Bare-prose requirement id(s) found, uncounted:[/red]")
        for req_id in bare_prose_requirement_ids:
            console.print(f"  - {req_id}")
    rejected = diagnostics.get("rejected_requirement_refs")
    if isinstance(rejected, dict) and rejected:
        console.print("[red]Rejected requirement refs:[/red]")
        for wp_id, entries in rejected.items():
            for entry in entries:
                console.print(f"  - {wp_id}: {entry['ref']} ({entry['reason']})")


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
    existing_frontmatter: dict[str, WPMetadata] = {}
    for wp_file in wp_files:
        wp_id_match = re.match(r"^(WP\d{2})(?:[-_.]|$)", wp_file.name)
        if not wp_id_match:
            continue
        wp_id = wp_id_match.group(1)
        try:
            wp_meta, _ = _read_wp_frontmatter(wp_file)
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
            _emit_json({"error": error_msg, "dependency_conflicts": dep_conflict_errors})
        else:
            console.print(f"[red]Error:[/red] {error_msg}")
        raise typer.Exit(1)


def _enforce_charter_activation_gate(wp_meta: WPMetadata, wp_id: str, repo_root: Path) -> None:
    """Phase: T044 / FR-017 charter activation gate (fires before any write)."""
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
        console.print(
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
        wp_meta, body = _read_wp_frontmatter(wp_file)
    except Exception as e:  # noqa: BLE001 — surface but skip unreadable WPs
        if not json_output:
            console.print(f"[yellow]Warning:[/yellow] Could not read {wp_file.name}: {e}")
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
    if state.post_integration_acceptance_warnings and not json_output:
        for warning in state.post_integration_acceptance_warnings:
            console.print(f"[yellow]Warning:[/yellow] {warning}")


def _raise_ownership_contradictions_if_any(state: _BootstrapState, contradicting_wp_ids: list[str], *, json_output: bool) -> None:
    """Raise once after the bootstrap scan when ownership contradictions exist."""
    if not state.ownership_contradictions:
        return
    error_msg = "Ownership contradiction detected for WP(s) " + ", ".join(contradicting_wp_ids) + ": " + "; ".join(state.ownership_contradictions)
    if json_output:
        _emit_json(
            {
                "error": error_msg,
                "error_code": OWNERSHIP_CONTRADICTION_CODE_CHANGE_EMPTY_OWNED_FILES,
                "ownership_contradiction_wp_ids": contradicting_wp_ids,
                "ownership_contradictions": list(state.ownership_contradictions),
            }
        )
    else:
        console.print(f"[red]Error:[/red] {error_msg}")
        for msg in state.ownership_contradictions:
            console.print(f"  - {msg}")
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
        _emit_json(payload)
    else:
        console.print(f"[red]Error:[/red] {error_msg}")
        for invalid in invalid_owned_files:
            console.print(f"  - {invalid['wp_id']}: {invalid['path']}")
    raise typer.Exit(1) from None


def _flush_frontmatter_writes(state: _BootstrapState, *, validate_only: bool) -> None:
    """Phase: write pending frontmatter to disk (gated on not validate_only)."""
    if validate_only:
        return
    for wp_file, updated_meta, body in state.pending_writes:
        write_frontmatter(wp_file, updated_meta.model_dump(exclude_none=True, mode="json"), body)


def _gather_validation_frontmatter(wp_files: list[Path], state: _BootstrapState) -> tuple[dict[str, WPMetadata], dict[str, str]]:
    """Phase: prefer-in-memory-then-disk frontmatter acquisition (FR-031)."""
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
                fm_meta, wp_body = _read_wp_frontmatter(wp_file)
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
    if not wp_manifests:
        return
    wp_dependencies = {wp_id: list(fm.dependencies) for wp_id, fm in wp_frontmatters.items() if getattr(fm, "dependencies", None)}
    ownership_result = _validate_ownership_via_mission(wp_manifests, wp_dependencies)
    for warning in ownership_result.warnings:
        if not json_output:
            console.print(f"[yellow]Ownership warning:[/yellow] {warning}")
    if not ownership_result.passed:
        error_msg = "Ownership validation failed"
        if json_output:
            _emit_json({"error": error_msg, "ownership_errors": ownership_result.errors})
        else:
            console.print(f"[red]Error:[/red] {error_msg}")
            for err in ownership_result.errors:
                console.print(f"  - {err}")
        raise typer.Exit(1) from None

    create_intent = {wp_id: list(fm.create_intent) for wp_id, fm in wp_frontmatters.items() if fm.create_intent}
    glob_result = validate_glob_matches(wp_manifests, repo_root, create_intent=create_intent)
    _record_ownership_glob_diagnostics(glob_result, state, json_output=json_output)
    if not glob_result.passed:
        error_msg = "Ownership validation failed: literal-path owned_files entries match zero files. Fix the paths or add them to 'create_intent'."
        if json_output:
            _emit_json({"error": error_msg, "ownership_literal_path_errors": glob_result.errors})
        else:
            console.print(f"[red]Error:[/red] {error_msg}")
        raise typer.Exit(1) from None

    codebase_wide = [list(m.owned_files) for m in wp_manifests.values() if m.is_codebase_wide]
    audit_warnings = validate_audit_coverage(codebase_wide, repo_root)
    state.ownership_warnings.extend(audit_warnings)
    if not json_output:
        for warning in audit_warnings:
            console.print(f"[yellow]Audit coverage warning:[/yellow] {warning}")


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
    if not eligibility.stale_dependencies:
        return
    records = [stale.to_dict() for stale in eligibility.stale_dependencies]
    error_msg = "Cannot finalize execution lanes: eligible work depends on canceled work packages."
    if json_output:
        _emit_json(
            {
                "error": error_msg,
                "error_code": "STALE_CANCELED_DEPENDENCIES",
                "stale_canceled_dependencies": records,
            }
        )
    else:
        console.print(f"[red]Error:[/red] {error_msg}")
        for record in records:
            console.print(f"  - {record['dependent_wp_id']} depends on canceled {record['canceled_dependency_wp_id']}: {record['recovery']}")
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
    error_msg = _lane_computation_empty_input_error(wp_manifests, wp_dependencies, wp_frontmatters, all_canceled=all_canceled)
    if error_msg is None:
        return
    if json_output:
        _emit_json({"error": error_msg, "error_code": LANE_COMPUTATION_ABORTED_EMPTY_INPUTS})
    else:
        console.print(f"[red]Error:[/red] {error_msg}")
    raise typer.Exit(1) from None


def _record_ownership_glob_diagnostics(
    glob_result: GlobValidationResult,
    state: _BootstrapState,
    *,
    json_output: bool,
) -> None:
    """Record glob diagnostics, rendering them only for human output."""
    state.ownership_warnings.extend(glob_result.warnings)
    if json_output:
        return
    stderr_console = err_console
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
            console.print("[yellow]⚠[/yellow] tasks.md is stale relative to wps.yaml; run finalize-tasks without --validate-only to regenerate")
        return stale
    tasks_md.write_text(generated, encoding="utf-8")
    if not json_output:
        console.print(f"[green]Regenerated[/green] tasks.md from wps.yaml ({len(wps_manifest.work_packages)} WPs)")
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
) -> None:
    """Phase: emit the --validate-only report (INV-6: zero mutation).

    Runs bootstrap + lane computation in dry-run mode only.
    """
    bootstrap_result = _bootstrap_canonical_state_via_mission(
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

        raw_mission_id = meta.get("mission_id") if meta else None
        mission_id = raw_mission_id if isinstance(raw_mission_id, str) else None
        lanes_manifest_dry = _compute_lanes_validate(
            dependency_graph=wp_dependencies,
            ownership_manifests=wp_manifests,
            mission_slug=mission_slug,
            target_branch=target_branch,
            wp_bodies=wp_bodies,
            mission_id=mission_id,
        )
        cr_dry = lanes_manifest_dry.collapse_report
        lanes_stats = {
            "computed": True,
            "count": len(lanes_manifest_dry.lanes),
            "lane_ids": [lane.lane_id for lane in lanes_manifest_dry.lanes],
            "planning_artifact_wps": lanes_manifest_dry.planning_artifact_wps,
            "collapse_report": cr_dry.to_dict() if cr_dry else None,
        }

    would_modify, pin_change = _validate_only_planning_preview(
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
        _add_planning_commit_to_validation_report(report, planning_sha)
        if planning_sha is not None:
            findings = refresh_status_findings or []
            report["planning_refresh_preflight"] = {
                "mutating_refresh_would_refuse_for_status_preflight": bool(findings),
                "status_findings": findings,
            }
        _emit_json(report)
        return
    console.print("[green]✓[/green] All validations passed (--validate-only mode, no commit)")
    console.print(f"  Mission: {mission_slug}")
    console.print(f"  WPs validated: {len(state.work_packages)}")
    console.print(f"  Would modify: {len(state.would_modify)} WP(s), preserve: {len(state.preserved_wps)}, unchanged: {len(state.unchanged_wps)}")
    _report_validate_only_pin_change(pin_change, planning_sha)
    _report_refresh_status_findings(refresh_status_findings, planning_sha)
    console.print(f"  Bootstrap: {bootstrap_result.newly_seeded} WPs would be seeded, {bootstrap_result.already_initialized} already initialized")
    if lanes_stats.get("computed"):
        console.print(f"  Lanes: {lanes_stats['count']} lane(s) would be computed")
        cr_info = lanes_stats.get("collapse_report")
        collapse_report = cr_info if isinstance(cr_info, dict) else {}
        if collapse_report.get("independent_wps_collapsed", 0) > 0:
            console.print(
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
            console.print(f"[yellow]Warning:[/yellow] Local canonical WPCreated/TasksCompleted persistence failed: {local_wp_exc}")


def _execution_has_begun(
    repo_root: Path,
    mission_slug: str,
    *,
    owned: OwnedCheckout | None = None,
) -> bool:
    """#3311 T014: read-only "has execution begun" signal for the finalize gate.

    MANDATORY reader recipe: resolve the coord-aware status read dir via
    :func:`resolve_status_surface_with_anchor` (the same authority
    ``implement.py`` uses, ``implement.py:1668-1680``), then read lanes
    read-only through :func:`get_all_wp_lanes`. **Never calls
    ``reducer.materialize()``** — that WRITES ``status.json`` to disk, which a
    "read" helper for a gate check must never do (C-005 / the
    read-does-not-write invariant this WP is guarded against).

    ``has_event_log`` gates first: an absent event log means the mission has
    never been finalized/bootstrapped, so execution categorically has not
    begun (a fresh mission, or the very first finalize run).

    Returns:
        ``True`` iff any WP's current lane is something other than
        ``planned`` (claimed, in_progress, for_review, ..., done, blocked,
        canceled). ``False`` when the event log is absent, empty, every
        seeded WP is still ``planned``, or the surface/event log cannot be
        read at all (degrades gracefully like this module's sibling
        ``capture_branch_tip`` — a signal-computation helper must
        never crash the whole ``finalize-tasks`` command over an unreadable
        read-only surface; a corrupted event log is a pre-existing store
        problem `status doctor` surfaces separately, not something this gate
        should newly turn into a hard finalize failure).
    """
    from specify_cli.coordination.surface_resolver import (
        CoordinationBranchDeleted,
        StatusReadPathNotFound,
        resolve_status_surface_with_anchor,
    )
    from specify_cli.status import Lane, StoreError, get_all_wp_lanes, has_event_log

    try:
        if owned is not None:
            from mission_runtime import placement_seam

            read_dir = placement_seam(
                owned.repository_root,
                mission_slug,
                owned=owned,
            ).read_dir(MissionArtifactKind.STATUS_STATE)
        else:
            read_dir = resolve_status_surface_with_anchor(repo_root, mission_slug).read_dir
    except (FileNotFoundError, ValueError, StatusReadPathNotFound, CoordinationBranchDeleted):
        # Surface resolution failed closed (no meta.json / malformed meta / an
        # unresolvable coord surface). No event log can be read from an
        # unresolvable surface either, so this degrades to the same
        # "not begun" answer ``has_event_log``'s absence produces below.
        return False
    if not has_event_log(read_dir):
        return False
    try:
        lanes = get_all_wp_lanes(read_dir)
    except StoreError:
        # Corrupted/malformed event log content. Degrade to "not begun"
        # rather than raise — see the docstring's graceful-degradation note.
        return False
    return any(lane != Lane.PLANNED for lane in lanes.values())


@dataclass(frozen=True)
class PlanningCommitResolution:
    """#4141: the outcome of this run's ``planning_commit_sha`` decision.

    Carries the resolved SHA plus the provenance a refresh decision needs —
    the previously recorded SHA and the ``target_branch`` tip it was compared
    against — so ``_compute_and_write_lanes`` can report the decision on the
    console and ``_emit_success_report`` can carry it in the ``--json``
    payload without re-reading git or ``lanes.json`` a second time.

    ``action`` is one of:

    * ``"captured"`` — execution has not begun; the branch tip was captured
      (the historical pre-execution behavior, unchanged by #4141).
    * ``"preserved"`` — execution has begun and no ``--refresh-planning-commit``
      was supplied; the previously recorded SHA is preserved (#3311).
    * ``"refreshed"`` — the operator explicitly requested
      ``--refresh-planning-commit`` and the recorded pin is being re-pointed
      to the target-branch tip. Before execution begins, the old pin is kept
      as the compare-and-swap expectation; after execution begins, the tip is
      captured only after the advance-only ancestor check passes (orphaned
      pins require the separate ``--allow-orphaned`` path).
    * ``"repinned"`` — execution has begun and the operator supplied both
      ``--refresh-planning-commit --allow-orphaned``; the recorded SHA was a
      proven ORPHAN (present, not an ancestor — the mid-mission-rebase
      shape, #4827) and was re-pointed to the target-branch tip.
    """

    sha: str | None
    action: str
    previous_sha: str | None = None
    branch_tip: str | None = None
    #: WP15 cycle 2 (B7, contracts/commit-outcome.md): the
    #: ``planning_commit_classify.PinClass`` value (as its ``str`` form) the
    #: no-flag AUTOMATIC decision classified the recorded pin as, when that
    #: path ran. ``None`` for the pre-execution ``"captured"`` action (no
    #: pin was classified) and for the explicit ``--refresh-planning-commit``
    #: path (classified by a DIFFERENT decision function,
    #: ``_resolve_refresh_planning_commit_decision``, not surfaced here).
    pin_class: str | None = None
    #: A short, machine-readable reason code for why the AUTOMATIC decision
    #: landed on its action -- currently only populated for
    #: ``"kept_with_warning"`` (the pin class name, e.g. ``"foreign"``).
    refusal_reason: str | None = None


@dataclass(frozen=True)
class _PrimaryPinRefreshCommit:
    """Preflighted inputs for one primary-only planning-pin commit."""

    primary_root: Path
    worktree_root: Path
    owned: OwnedCheckout | None
    lanes_path: Path
    files: tuple[Path, ...]
    message: str
    new_sha: str
    expected_parent_sha: str


def _planning_pin_change(
    planning_dir: Path,
    planning_sha: PlanningCommitResolution | None,
) -> dict[str, object] | None:
    """Describe the lanes.json pin delta a refresh would write, if any."""
    if planning_sha is None:
        return None

    from specify_cli.lanes.persistence import read_lanes_json

    existing = read_lanes_json(planning_dir)
    previous = existing.planning_commit_sha if existing is not None else None
    if previous == planning_sha.sha:
        return None
    return {
        "artifact": "lanes.json",
        "changes": {"planning_commit_sha": {"from": previous, "to": planning_sha.sha}},
    }


_PLANNING_REFRESH_STATUS_BY_ACTION: Final[dict[str, str]] = {
    "preserved": "preserved",
    "refreshed": "refreshed",
    "kept_with_warning": "kept_with_warning",
}


def _planning_commit_refresh_payload(
    planning_sha: PlanningCommitResolution | None,
) -> dict[str, object] | None:
    """Build the additive ``planning_commit_refresh`` JSON field (FR-012, contracts/commit-outcome.md).

    Populated only for the three actions the AUTOMATIC (no-flag) decision
    path can resolve once execution has begun (preserved/refreshed/
    kept_with_warning) — ``None`` for a pre-execution ``"captured"`` run (no
    pin was yet recorded to refresh) and for the explicit
    ``--refresh-planning-commit``/``--allow-orphaned`` path (``"refreshed"``/
    ``"repinned"``), which keeps reporting through the pre-existing
    ``planning_commit`` field only (contract: "An explicit
    --refresh-planning-commit keeps its existing refusals"). An orphaned pin
    never reaches here — it fails closed before any write (#4827).

    WP15 cycle 2 (B7/C2-1, contracts/commit-outcome.md): the payload also
    carries ``pin_class`` (the recorded pin's ``PinClass``, as classified by
    the automatic decision) and ``reason`` (populated only for
    ``kept_with_warning``, where it names WHY the automatic refresh could not
    proceed). The contract's INDETERMINATE row (``kept_with_warning`` for an
    uncapturable tip) is implemented exactly as the contract states, per the
    orchestrator's C2-1 ruling: INDETERMINATE is reported as a VISIBLE
    ``kept_with_warning`` with ``reason="indeterminate_tip_uncapturable"``,
    never a silent ``preserved``.
    """
    if planning_sha is None:
        return None
    status = _PLANNING_REFRESH_STATUS_BY_ACTION.get(planning_sha.action)
    if status is None:
        return None
    return {
        "status": status,
        "recorded": planning_sha.previous_sha,
        "candidate": planning_sha.branch_tip,
        "pin_class": planning_sha.pin_class,
        "reason": planning_sha.refusal_reason,
    }


def _planning_commit_payload(
    planning_sha: PlanningCommitResolution | None,
    lanes_manifest: LanesManifest | None,
) -> dict[str, object]:
    """Build the one JSON representation of finalize's planning-pin decision."""
    resolved_sha = planning_sha.sha if planning_sha is not None else (lanes_manifest.planning_commit_sha if lanes_manifest is not None else None)
    return {
        "sha": resolved_sha,
        "action": planning_sha.action if planning_sha is not None else None,
        "previous_sha": planning_sha.previous_sha if planning_sha is not None else None,
        "branch_tip": planning_sha.branch_tip if planning_sha is not None else None,
    }


def _validate_only_planning_preview(
    planning_dir: Path,
    existing_changes: list[dict[str, object]],
    planning_sha: PlanningCommitResolution | None,
) -> tuple[list[dict[str, object]], dict[str, object] | None]:
    """Combine bootstrap changes with the lanes pin delta for dry-run output."""
    pin_change = _planning_pin_change(planning_dir, planning_sha)
    would_modify = [*existing_changes]
    if pin_change is not None:
        would_modify.append(pin_change)
    return would_modify, pin_change


def _add_planning_commit_to_validation_report(
    report: dict[str, object],
    planning_sha: PlanningCommitResolution | None,
) -> None:
    """Add the canonical pin decision to validate-only JSON when requested."""
    if planning_sha is not None:
        report["planning_commit"] = _planning_commit_payload(planning_sha, None)


def _report_validate_only_pin_change(
    pin_change: dict[str, object] | None,
    planning_sha: PlanningCommitResolution | None,
) -> None:
    """Show the lanes pin delta in human-mode validate-only output."""
    if pin_change is None or planning_sha is None:
        return
    console.print(f"  Would refresh planning_commit_sha in lanes.json: {planning_sha.previous_sha or '<unset>'} -> {planning_sha.sha or '<unset>'}")


def _refuse_planning_sha_refresh(error_msg: str, *, json_output: bool) -> NoReturn:
    """#4141: emit a refresh refusal diagnostic and exit before any write.

    Raised from inside :func:`_preserve_or_capture_planning_commit_sha`
    BEFORE ``write_lanes_json`` runs, so a refused refresh leaves the on-disk
    ``lanes.json`` (and its recorded ``planning_commit_sha``) untouched.
    Never returns — always raises ``typer.Exit(1)``.
    """
    if json_output:
        _emit_json({"error": error_msg})
    else:
        console.print(f"[red]Error:[/red] {error_msg}")
    raise typer.Exit(1)


def _resolve_refresh_planning_commit_decision(
    *,
    repo_root: Path,
    mission_slug: str,
    target_branch: str,
    recorded: str | None,
    tip: str | None,
    allow_orphaned: bool,
    json_output: bool,
) -> PlanningCommitResolution:
    """#4141/#4827: resolve the ``--refresh-planning-commit`` branch.

    Advance-only by default (the #4141 contract, unchanged): an ADVANCED
    recorded SHA (an ancestor of the tip, or no recorded SHA at all to
    compare) refreshes unconditionally. ``--allow-orphaned`` additionally
    permits re-pointing a PROVEN ORPHANED pin (present in the object store,
    unreachable from the tip — the mid-mission-rebase shape, #4827); without
    it an orphan is refused with a message that still contains the substring
    "not an ancestor" (keeps the #4141
    ``test_refresh_refused_when_recorded_sha_not_ancestor`` fixture green — it
    exercises exactly this shape per research.md D3). A FOREIGN (absent)
    object is refused regardless of ``--allow-orphaned`` — there is nothing
    to re-point to; the operator must investigate how it was recorded.
    """
    if tip is None:
        _refuse_planning_sha_refresh(
            f"Cannot refresh planning_commit_sha for mission {mission_slug!r}: "
            f"the tip of target branch {target_branch!r} could not be captured. "
            "Refusing to refresh rather than silently preserve or guess.",
            json_output=json_output,
        )
    pin_class = classify_recorded_pin(repo_root, recorded, tip)
    if pin_class is PinClass.FOREIGN:
        _refuse_planning_sha_refresh(
            f"Cannot refresh planning_commit_sha for mission {mission_slug!r}: the recorded "
            f"SHA {recorded} is not present in this repository (object absent, not merely "
            "unreachable). Refusing to re-point to a SHA that cannot be inspected; investigate "
            "how it was recorded.",
            json_output=json_output,
        )
    if pin_class is PinClass.ORPHANED and not allow_orphaned:
        _refuse_planning_sha_refresh(
            f"Cannot refresh planning_commit_sha for mission {mission_slug!r}: the recorded "
            f"SHA {recorded} is not an ancestor of the {target_branch!r} tip {tip}. If this is a "
            "deliberate mid-mission rebase (the recorded commit is still present, just no longer "
            "reachable from the tip), re-run with --refresh-planning-commit --allow-orphaned to "
            "re-point to the live tip. Otherwise the planning history was rewritten/diverged "
            "rather than advanced by an amendment; resolve the divergence manually. Refusing to "
            "re-point.",
            json_output=json_output,
        )
    action = "repinned" if pin_class is PinClass.ORPHANED else "refreshed"
    return PlanningCommitResolution(sha=tip, action=action, previous_sha=recorded, branch_tip=tip)


def _refuse_planning_pin_refresh(reason: str, *, json_output: bool) -> NoReturn:
    """Fail closed before or during a primary-only pin refresh."""
    message = f"Cannot refresh planning_commit_sha safely: {reason}"
    if json_output:
        _emit_json({"error": message, "error_code": "PLANNING_REFRESH_FAIL_CLOSED"})
    else:
        console.print(f"[red]Error:[/red] {message}")
    raise typer.Exit(1)


def _refresh_worktree_status_findings(
    primary_root: Path,
    primary_worktree: Path,
    mission_slug: str,
) -> list[str]:
    """Inspect both partitions without materializing a coordination worktree."""
    findings: list[str] = []
    primary_status, status_error = _read_refresh_worktree_status(primary_worktree)
    if status_error is not None:
        findings.append(f"primary worktree status could not be inspected: {status_error}")
    elif primary_status:
        findings.append(f"primary worktree has pending changes: {_render_pending_entries(primary_status)}")

    from mission_runtime import placement_seam, routes_through_coordination, resolve_mid8, resolve_topology

    if not routes_through_coordination(resolve_topology(primary_root, mission_slug)):
        return findings

    meta_dir = placement_seam(primary_root, mission_slug).read_dir(MissionArtifactKind.PRIMARY_METADATA)
    meta = load_meta_fail_closed(meta_dir) or {}
    raw_mission_id = meta.get("mission_id")
    if not isinstance(raw_mission_id, str):
        findings.append("coordination worktree status could not be inspected without writing mission metadata")
        return findings
    mid8 = resolve_mid8(mission_slug, mission_id=raw_mission_id)
    from specify_cli.coordination.workspace import CoordinationWorkspace

    coord_worktree = CoordinationWorkspace.worktree_path(primary_root, mission_slug, mid8)
    if not coord_worktree.exists():
        return findings
    coord_status, status_error = _read_refresh_worktree_status(coord_worktree)
    if status_error is not None:
        findings.append(f"coordination worktree status could not be inspected: {status_error}")
    elif coord_status:
        findings.append(f"coordination worktree has pending status/history changes: {_render_pending_entries(coord_status)}")
    return findings


def _refresh_worktree_status_error(
    primary_root: Path,
    primary_worktree: Path,
    mission_slug: str,
) -> str | None:
    """Return the first blocker from a read-only status inspection of both partitions."""
    findings = _refresh_worktree_status_findings(primary_root, primary_worktree, mission_slug)
    return findings[0] if findings else None


def _report_refresh_status_findings(
    findings: list[str] | None,
    planning_sha: PlanningCommitResolution | None,
) -> None:
    """Explain when pending partition status will block a mutating refresh."""
    if planning_sha is None:
        return
    if findings:
        console.print("[yellow]⚠[/yellow] Mutating refresh would refuse on status preflight findings:")
        for finding in findings:
            console.print(f"  - {finding}")
        return
    console.print("  Mutating refresh status preflight: no pending primary or coordination changes")


def _render_pending_entries(entries: tuple[StatusEntry, ...]) -> str:
    """One display line per pending entry (for a finding message; never parsed back)."""
    return "\n".join(entry.display() for entry in entries)


def _read_refresh_worktree_status(worktree: Path) -> tuple[tuple[StatusEntry, ...] | None, str | None]:
    """Return the pending status entries and any diagnostic from a read-only Git probe."""
    try:
        # ``optional_locks=False``: a read-only probe must not refresh (write) the index.
        return status_entries(worktree, untracked="all", optional_locks=False), None
    except GitCommandError as exc:
        # Guard: a failed probe is reported as a blocking finding, never as "clean".
        detail = exc.stderr.strip()
        return None, f"refresh could not inspect worktree {worktree}: {detail or 'git status failed'}"


def _refresh_branch_contract_error(
    planning_dir: Path,
    target_branch: str,
    target_branch_override: str | None,
) -> str | None:
    """Refuse refresh when ordinary finalize would need a meta.json mutation."""
    meta = load_meta_fail_closed(planning_dir) or {}
    existing_target = meta.get("target_branch")
    if target_branch_override and target_branch_override.strip() and existing_target != target_branch:
        return "a target-branch override would also change primary meta.json"
    if meta.get("pr_bound") and existing_target != target_branch:
        return "legacy PR-bound metadata needs a primary meta.json repair"
    return None


def _preflight_refresh_planning_commit(
    repo_root: Path,
    planning_dir: Path,
    mission_slug: str,
    target_branch: str,
    *,
    target_branch_override: str | None,
    owned: OwnedCheckout | None,
    json_output: bool,
) -> None:
    """Read-only guard run before finalize can write files or lifecycle events."""
    contract_error = _refresh_branch_contract_error(planning_dir, target_branch, target_branch_override)
    if contract_error is not None:
        _refuse_planning_pin_refresh(contract_error, json_output=json_output)
    primary_root = owned.repository_root if owned else repo_root
    primary_worktree = owned.owned_root if owned else repo_root
    surface_error = _refresh_worktree_status_error(primary_root, primary_worktree, mission_slug)
    if surface_error is not None:
        _refuse_planning_pin_refresh(surface_error, json_output=json_output)


def _prepare_primary_pin_refresh_commit(
    planning_dir: Path,
    repo_root: Path,
    mission_slug: str,
    target_branch: str,
    planning_sha: PlanningCommitResolution,
    new_sha: str,
    *,
    json_output: bool,
    owned: OwnedCheckout | None,
) -> _PrimaryPinRefreshCommit:
    """Resolve, preflight, and tip-check the one primary candidate commit."""
    from mission_runtime import is_primary_artifact_kind, placement_seam
    from specify_cli.git.commit_helpers import preflight_commit

    primary_root = owned.repository_root if owned else repo_root
    worktree_root = owned.owned_root if owned else repo_root
    lanes_path = planning_dir / "lanes.json"
    destination = placement_seam(
        primary_root,
        mission_slug,
        owned=owned,
    ).write_target(MissionArtifactKind.LANE_STATE)
    if not is_primary_artifact_kind(MissionArtifactKind.LANE_STATE) or destination.ref != target_branch:
        _refuse_planning_pin_refresh("lanes.json does not resolve to the planning target branch", json_output=json_output)

    files = tuple(owned.files([lanes_path])) if owned else (lanes_path,)
    message = _finalize_bookkeeping_commit_message(mission_slug)
    surface_error = _refresh_worktree_status_error(primary_root, worktree_root, mission_slug)
    if surface_error is not None:
        _refuse_planning_pin_refresh(surface_error, json_output=json_output)
    try:
        preflight_commit(
            repo_root=primary_root,
            worktree_root=worktree_root,
            target=destination,
            message=message,
            paths=files,
            owned=owned,
        )
    except Exception as exc:  # noqa: BLE001 — fail before the lanes manifest write
        _refuse_planning_pin_refresh(f"primary lanes.json commit preflight failed: {exc}", json_output=json_output)

    expected_tip = planning_sha.branch_tip or planning_sha.sha
    if expected_tip is None:
        _refuse_planning_pin_refresh("the captured planning parent SHA is missing", json_output=json_output)
    current_tip = capture_branch_tip(primary_root, target_branch)
    if current_tip != expected_tip:
        _refuse_planning_pin_refresh(
            f"planning target {target_branch!r} moved after pin capture ({expected_tip} -> {current_tip}); retry against the new tip",
            json_output=json_output,
        )

    return _PrimaryPinRefreshCommit(
        primary_root=primary_root,
        worktree_root=worktree_root,
        owned=owned,
        lanes_path=lanes_path,
        files=files,
        message=message,
        new_sha=new_sha,
        expected_parent_sha=expected_tip,
    )


def _commit_planning_pin_refresh(
    planning_dir: Path,
    repo_root: Path,
    mission_slug: str,
    target_branch: str,
    planning_sha: PlanningCommitResolution,
    state: _BootstrapState,
    dep_resolution: _DependencyResolution,
    bootstrap_result: BootstrapResult,
    *,
    tasks_md_stale: bool,
    json_output: bool,
    owned: OwnedCheckout | None,
) -> None:
    """Commit a clean refresh as a single primary lanes.json write."""
    if state.would_modify:
        _refuse_planning_pin_refresh("WP frontmatter also needs finalization", json_output=json_output)
    if tasks_md_stale:
        _refuse_planning_pin_refresh("tasks.md would need regeneration", json_output=json_output)
    if bootstrap_result.newly_seeded:
        _refuse_planning_pin_refresh("canonical coordination status would need bootstrap writes", json_output=json_output)

    from specify_cli.lanes.persistence import lanes_json_lock

    with lanes_json_lock(planning_dir):
        _commit_planning_pin_refresh_locked(
            planning_dir,
            repo_root,
            mission_slug,
            target_branch,
            planning_sha,
            state,
            dep_resolution,
            bootstrap_result,
            json_output=json_output,
            owned=owned,
        )


def _guard_lanes_bytes_unchanged_before_commit(lanes_path: Path, expected_bytes: bytes) -> None:
    """WP15/T004 campsite: the final compare-and-swap guard before the pin-refresh commit.

    Extracted verbatim from :func:`_commit_planning_pin_refresh_locked` (the
    tidy-first first commit) -- the LAST read of ``lanes_path`` before
    ``commit_for_mission`` runs, so a concurrent writer that landed between
    ``write_lanes_json`` and this exact instant is caught instead of silently
    overwritten. Preserves compare-and-swap semantics exactly: raises
    ``RuntimeError`` (never returns a status) so the caller's existing
    ``except Exception`` handler restores the original bytes and reports one
    real, single-ref outcome -- this helper has no restore/report
    responsibility of its own.
    """
    if lanes_path.read_bytes() != expected_bytes:
        raise RuntimeError("lanes.json changed before the conditional commit; concurrent content was left untouched")


def _finalize_pin_refresh_commit_outcome(
    result: CommitRouterResult,
    plan: _PrimaryPinRefreshCommit,
    *,
    old_lanes_bytes: bytes,
    candidate_lanes_bytes: bytes,
    json_output: bool,
) -> _CommitOutcome:
    """WP15/T082/T004 (cycle 2 B10 campsite): interpret ``commit_for_mission``'s
    result for the pin-only refresh commit -- extracted out of
    :func:`_commit_planning_pin_refresh_locked` to keep it under the C901
    ceiling. Renders the shared commit-outcome surfaces (contract rule 6) on
    EVERY outcome arm, success or refusal, and derives the refusal decision
    from :func:`~specify_cli.coordination.commit_outcome.commit_outcome_exit_code`
    (never the legacy ``result.status`` alone) -- except for the
    pin-refresh-SPECIFIC ``"unchanged"`` anomaly (see the inline note below),
    which is a LOCAL invariant this single-ref commit owns, not something the
    shared exit-code rule governs. Never returns on a refusal
    (:func:`_refuse_planning_pin_refresh` is ``NoReturn``).
    """
    from specify_cli.coordination.commit_outcome import commit_outcome_exit_code, commit_outcome_payload, render_commit_outcome

    commit_outcome = _CommitOutcome()
    commit_outcome.commit_surfaces = cast("list[dict[str, object]]", commit_outcome_payload(result)["surfaces"])
    commit_outcome.rendered_lines = render_commit_outcome(result)
    if not json_output:
        for line in commit_outcome.rendered_lines:
            console.print(line, markup=False)

    # This single-ref pin commit has exactly one PRIMARY surface, so
    # ``commit_outcome_exit_code`` (contract rule 5: nonzero iff any surface
    # is refused/error) is the correct outcome-consumer decision for a
    # genuine router refusal/error. ``"unchanged"`` is handled as its OWN,
    # LOCAL anomaly first: this call just wrote a NEW sha to lanes.json, so
    # the router reporting no diff means a concurrent writer raced us --
    # that is refused regardless of what the shared exit-code rule would say
    # about an "unchanged" status (which is a legitimate success elsewhere).
    if result.status == "unchanged":
        restore_error = _restore_planning_pin_candidate(plan.lanes_path, candidate_lanes_bytes, old_lanes_bytes)
        detail = "primary lanes.json changed but the commit seam reported unchanged"
        if restore_error is not None:
            detail = f"{detail}; {restore_error}"
        _refuse_planning_pin_refresh(detail, json_output=json_output)
    if commit_outcome_exit_code(result) != 0:
        restore_error = _restore_planning_pin_candidate(plan.lanes_path, candidate_lanes_bytes, old_lanes_bytes)
        detail = result.diagnostic or "primary lanes.json commit was refused"
        if restore_error is not None:
            detail = f"{detail}; {restore_error}"
        _refuse_planning_pin_refresh(detail, json_output=json_output)

    commit_outcome.commit_created = True
    commit_outcome.commit_hash = result.commit_hash
    commit_outcome.commit_hashes = [{"branch": ref, "hash": sha} for ref, sha in result.commit_hashes]
    commit_outcome.diagnostic = result.diagnostic
    committed_root = plan.worktree_root
    commit_outcome.files_committed = [str(path.relative_to(committed_root)) for path in plan.files]
    if result.diagnostic is not None and not json_output:
        console.print(f"[yellow]Warning:[/yellow] {result.diagnostic}")
    return commit_outcome


def _commit_planning_pin_refresh_locked(
    planning_dir: Path,
    repo_root: Path,
    mission_slug: str,
    target_branch: str,
    planning_sha: PlanningCommitResolution,
    state: _BootstrapState,
    dep_resolution: _DependencyResolution,
    bootstrap_result: BootstrapResult,
    *,
    json_output: bool,
    owned: OwnedCheckout | None,
) -> None:
    """Validate byte identity and commit while holding the lanes writer lock."""
    from specify_cli.coordination.commit_router import commit_for_mission
    from specify_cli.git.protection_policy import ProtectionPolicy
    from specify_cli.lanes.persistence import read_lanes_json, write_lanes_json

    lanes_path = planning_dir / "lanes.json"
    try:
        old_lanes_bytes = lanes_path.read_bytes()
    except OSError as exc:
        _refuse_planning_pin_refresh(f"lanes.json could not be read: {exc}", json_output=json_output)
    lanes_manifest = read_lanes_json(planning_dir)
    if lanes_manifest is None:
        _refuse_planning_pin_refresh("lanes.json is missing or unreadable", json_output=json_output)
    if lanes_path.read_bytes() != old_lanes_bytes:
        _refuse_planning_pin_refresh("lanes.json changed while its manifest was being read", json_output=json_output)
    if lanes_manifest.planning_commit_sha != planning_sha.previous_sha:
        _refuse_planning_pin_refresh("lanes.json changed after the planning pin was captured", json_output=json_output)
    if planning_sha.sha is None:
        _refuse_planning_pin_refresh("the target branch tip could not be captured", json_output=json_output)

    if lanes_manifest.planning_commit_sha == planning_sha.sha:
        _report_planning_pin_refresh_success(
            planning_dir,
            target_branch,
            planning_sha,
            state,
            dep_resolution,
            bootstrap_result,
            lanes_manifest,
            _CommitOutcome(),
            json_output=json_output,
            unchanged=True,
        )
        return

    plan = _prepare_primary_pin_refresh_commit(
        planning_dir,
        repo_root,
        mission_slug,
        target_branch,
        planning_sha,
        planning_sha.sha,
        json_output=json_output,
        owned=owned,
    )

    if plan.lanes_path.read_bytes() != old_lanes_bytes:
        _refuse_planning_pin_refresh("lanes.json changed after refresh preparation; concurrent content was left untouched", json_output=json_output)
    lanes_manifest.planning_commit_sha = plan.new_sha
    write_lanes_json(planning_dir, lanes_manifest)
    candidate_lanes_bytes = plan.lanes_path.read_bytes()
    try:
        _guard_lanes_bytes_unchanged_before_commit(plan.lanes_path, candidate_lanes_bytes)
        result = commit_for_mission(
            repo_root=plan.primary_root,
            mission_slug=mission_slug,
            files=plan.files,
            message=plan.message,
            policy=ProtectionPolicy.resolve(plan.primary_root),
            kind=MissionArtifactKind.LANE_STATE,
            target_branch=target_branch,
            owned=plan.owned,
            expected_parent_sha=plan.expected_parent_sha,
            expected_path_bytes={plan.lanes_path: candidate_lanes_bytes},
        )
    except Exception as exc:  # noqa: BLE001 — report the real one-ref outcome
        restore_error = _restore_planning_pin_candidate(plan.lanes_path, candidate_lanes_bytes, old_lanes_bytes)
        detail = f"primary lanes.json commit failed: {exc}"
        if restore_error is not None:
            detail = f"{detail}; {restore_error}"
        _refuse_planning_pin_refresh(detail, json_output=json_output)

    commit_outcome = _finalize_pin_refresh_commit_outcome(
        result,
        plan,
        old_lanes_bytes=old_lanes_bytes,
        candidate_lanes_bytes=candidate_lanes_bytes,
        json_output=json_output,
    )

    _report_planning_pin_refresh_success(
        planning_dir,
        target_branch,
        planning_sha,
        state,
        dep_resolution,
        bootstrap_result,
        lanes_manifest,
        commit_outcome,
        json_output=json_output,
        unchanged=False,
    )


def _report_planning_pin_refresh_success(
    planning_dir: Path,
    target_branch: str,
    planning_sha: PlanningCommitResolution,
    state: _BootstrapState,
    dep_resolution: _DependencyResolution,
    bootstrap_result: BootstrapResult,
    lanes_manifest: LanesManifest,
    commit_outcome: _CommitOutcome,
    *,
    json_output: bool,
    unchanged: bool,
) -> None:
    """Report a pin refresh in the selected output mode.

    WP13-review binding correction (applied here too): when
    ``commit_outcome.commit_surfaces`` is populated, render it through the
    SAME shared trio the main commit pipeline uses.

    WP15 cycle 2 (B10): the text-mode, ``not unchanged`` (real commit
    attempt) surface lines are printed by the CALLER
    (:func:`_commit_planning_pin_refresh_locked`) BEFORE this function runs
    at all -- on EVERY outcome arm, success or refusal -- so they are never
    printed twice here.
    """
    if json_output:
        _emit_success_report(
            planning_dir / "tasks",
            state,
            commit_outcome,
            dep_resolution,
            bootstrap_result,
            lanes_manifest,
            target_branch_persist=TargetBranchPersistOutcome(persisted=False),
            planning_sha=planning_sha,
        )
    elif unchanged:
        console.print(f"[green]✓[/green] planning_commit_sha already matches the {target_branch} tip ({planning_sha.sha}); no commit needed")
    else:
        _report_planning_sha_decision(target_branch, planning_sha, json_output=False)


def _restore_planning_pin_candidate(
    lanes_path: Path,
    candidate_bytes: bytes,
    original_bytes: bytes,
) -> str | None:
    """CAS-restore our lanes candidate without overwriting concurrent edits."""
    from specify_cli.lanes.persistence import lanes_json_lock, write_lanes_json_if_bytes_match

    with lanes_json_lock(lanes_path.parent):
        try:
            current_bytes = lanes_path.read_bytes()
        except OSError as exc:
            return f"could not inspect lanes.json for rollback: {exc}"
        if current_bytes != candidate_bytes:
            return "lanes.json changed during the failed commit and was left untouched"
        try:
            if not write_lanes_json_if_bytes_match(lanes_path.parent, candidate_bytes, original_bytes):
                return "lanes.json changed during rollback and was left untouched"
        except OSError as exc:
            return f"could not restore the original lanes.json: {exc}"
    return None


def _planning_changed_since_pin(
    repo_root: Path,
    mission_slug: str,
    recorded_sha: str | None,
    target_tip: str | None,
) -> bool:
    """FR-012 (T083): True iff a PRIMARY-partition planning file changed between ``recorded_sha`` and ``target_tip``.

    Scoped to this Mission's own directory (``kitty-specs/<mission_slug>``)
    and classified per changed path via the single file->kind authority
    (:func:`~mission_runtime.kind_for_mission_file`) so only genuine
    PRIMARY-partition planning content (spec/plan/tasks/WP files, …) counts —
    never a COORD-kind residual (status/matrices) that might incidentally
    live under the same directory tree. ``lanes.json`` is explicitly excluded
    even though it classifies PRIMARY: it is finalize's OWN pin-refresh
    output, so counting it would make the automatic refresh re-trigger itself
    on its own prior commit (research D16's self-trigger hazard).

    Returns ``False`` (nothing to compare) when either endpoint is missing or
    the two endpoints are identical — never raises on a git probe failure,
    degrading to "no change detected" (the safe default: callers only use
    this to decide whether to ATTEMPT a refresh, never to skip a safety
    check).
    """
    if recorded_sha is None or target_tip is None or recorded_sha == target_tip:
        return False
    from mission_runtime import is_primary_artifact_kind, kind_for_mission_file

    try:
        changed = changed_paths(repo_root, recorded_sha, target_tip, pathspecs=(f"{KITTY_SPECS_DIR}/{mission_slug}",))
    except GitCommandError:
        return False
    for git_path in changed:
        changed_path = str(git_path)
        if not changed_path or PurePosixPath(changed_path).name == "lanes.json":
            continue
        kind = kind_for_mission_file(changed_path, mission_slug=mission_slug)
        if kind is not None and is_primary_artifact_kind(kind):
            return True
    return False


def _resolve_preserve_planning_commit_decision(
    *,
    repo_root: Path,
    mission_slug: str,
    target_branch: str,
    recorded: str | None,
    tip: str | None,
    json_output: bool,
) -> PlanningCommitResolution:
    """#3311/#4827/FR-012 (T083/T084): resolve the no-flag (preserve/auto-refresh) branch.

    Fails closed BEFORE any write only for a PROVEN ORPHAN against a
    capturable tip (D3/D4): the tool must not silently keep every
    subsequently allocated lane merging a dead base (#4827, unchanged by this
    WP — ``test_plain_finalize_fails_closed_on_orphaned_pin`` stays green).

    For every other pin class, FR-012's default automatic refresh applies:
    when a PRIMARY planning file changed since the recorded pin for a reason
    OTHER than finalize's own prior bookkeeping commits
    (:func:`_planning_changed_since_pin` AND NOT
    :func:`_drift_is_finalize_bookkeeping_only` — the SAME #4178/D7(b)
    distinction the preserve-path drift WARN already relies on, reused here
    rather than re-implemented: without it, finalize's OWN first
    ``tasks.md``/``meta.json``/WP-frontmatter bookkeeping commit — landed
    AFTER the tip was captured for ``"captured"`` — would look like a
    "planning change" on every subsequent re-finalize with zero operator
    amendment), an ADVANCED pin (a provable safe advance -- the recorded
    object IS present and diffable) is refreshed to the tip
    (``action="refreshed"``). A FOREIGN pin's recorded object is absent
    entirely, so no path-scoped diff can even run against it; the automatic
    refresh cannot prove anything about it, so ANY tip advance over a FOREIGN
    pin is reported with a WARNING rather than failing closed or silently
    refreshing (ruling Q6, ``action="kept_with_warning"`` — the warning
    itself is printed later by :func:`_report_planning_sha_decision`, AFTER
    the write, per the #4178 print-after-write convention). An INDETERMINATE
    pin (an uncapturable tip, e.g. a non-git workspace, or no recorded SHA at
    all) is ALSO reported as ``action="kept_with_warning"`` (WP15 cycle 2,
    C2-1, orchestrator ruling): the classifier's own docstring says callers
    "degrade to their own historical preserve behavior", but finalize
    specifically must not silently swallow an uncapturable tip — it gets a
    dedicated ``refusal_reason="indeterminate_tip_uncapturable"`` distinct
    from a classified FOREIGN refusal. No genuine planning change at all
    degrades to the historical #3311 preserve (``action="preserved"``).
    """
    pin_class = classify_recorded_pin(repo_root, recorded, tip)
    if pin_class is PinClass.ORPHANED:
        error_msg = (
            f"Cannot re-finalize mission {mission_slug!r}: the recorded planning_commit_sha "
            f"{recorded} is orphaned — present in this repository but not an ancestor of the "
            f"{target_branch!r} tip {tip} (a mid-mission rebase). Lanes would keep merging a dead "
            "base. Re-run with --refresh-planning-commit --allow-orphaned to re-point the "
            "recorded SHA to the live tip, or investigate the divergence manually. Refusing to "
            "write lanes.json."
        )
        if json_output:
            _emit_json({"error": error_msg})
        else:
            console.print(f"[red]Error:[/red] {error_msg}")
        raise typer.Exit(1)
    if pin_class is PinClass.ADVANCED:
        planning_changed = (
            recorded is not None
            and tip is not None
            and _planning_changed_since_pin(repo_root, mission_slug, recorded, tip)
            and not _drift_is_finalize_bookkeeping_only(repo_root, mission_slug, recorded, tip)
        )
        if planning_changed:
            return PlanningCommitResolution(sha=tip, action="refreshed", previous_sha=recorded, branch_tip=tip, pin_class=pin_class.value)
    elif pin_class is PinClass.FOREIGN and recorded != tip:
        return PlanningCommitResolution(
            sha=recorded,
            action="kept_with_warning",
            previous_sha=recorded,
            branch_tip=tip,
            pin_class=pin_class.value,
            refusal_reason=pin_class.value,
        )
    elif pin_class is PinClass.INDETERMINATE:
        # WP15 cycle 2 (C2-1, orchestrator ruling on contracts/commit-outcome.md):
        # the classifier's OWN docstring says callers may degrade silently
        # for INDETERMINATE ("nothing about it can be inspected at all"), but
        # the ruling overrides that for finalize specifically -- a silent
        # `preserved` here would mask a genuinely uncapturable target-branch
        # tip from the operator. Report it as a VISIBLE, non-fatal warning
        # (exit 0) instead, with a dedicated reason code distinct from the
        # bare pin_class value so a consumer can tell "could not classify at
        # all" apart from "classified as FOREIGN and refused".
        return PlanningCommitResolution(
            sha=recorded,
            action="kept_with_warning",
            previous_sha=recorded,
            branch_tip=tip,
            pin_class=pin_class.value,
            refusal_reason="indeterminate_tip_uncapturable",
        )
    return PlanningCommitResolution(sha=recorded, action="preserved", previous_sha=recorded, branch_tip=tip, pin_class=pin_class.value)


def _preserve_or_capture_planning_commit_sha(
    planning_dir: Path,
    repo_root: Path,
    mission_slug: str,
    target_branch: str,
    *,
    json_output: bool,
    owned: OwnedCheckout | None = None,
    refresh_planning_commit: bool = False,
    allow_orphaned: bool = False,
) -> PlanningCommitResolution:
    """#3311 T015 / #4141 / #4827: resolve this run's ``planning_commit_sha`` decision.

    ADR ``2026-07-29-1`` / FR-009 freezes the recorded planning-artifact SHA
    into the SAME write ``_compute_and_write_lanes`` performs — no second
    commit, no re-read at lane-allocation time. #3311: once execution has
    begun (:func:`_execution_has_begun` — any WP past ``planned``), a
    re-finalize triggered by an ownership-only amendment must PRESERVE that
    frozen SHA instead of silently re-capturing the CURRENT branch tip, which
    would clobber the established planning provenance a lane worktree may
    already carry a merge-base against. Before execution begins, the
    historical no-flag recompute + re-capture behavior is unchanged — every
    pre-execution re-finalize keeps regenerating freely (C-005). An explicit
    refresh instead retains the existing lanes pin as the compare-and-swap
    expectation and captures the current branch tip, allowing the clean
    primary-only refresh path to report and commit the old-to-new transition.

    Once execution has begun, the recorded SHA is classified against the
    target-branch tip with the shared WP01 authority
    (:func:`specify_cli.lanes.planning_commit_classify.classify_recorded_pin`
    — never a lane worktree HEAD, see that module's C-006 note) and the
    decision is delegated to
    :func:`_resolve_refresh_planning_commit_decision` (``--refresh-planning-
    commit`` supplied) or :func:`_resolve_preserve_planning_commit_decision`
    (the no-flag default). ``--allow-orphaned`` (#4827) is the explicit
    operator assertion required to re-pin a PROVEN ORPHAN (present, not
    reachable — a mid-mission rebase) to the live tip; without it the
    no-flag path fails closed before any write and bare
    ``--refresh-planning-commit`` refuses (advance-only, unchanged #4141
    contract).

    Refuse (raise ``typer.Exit(1)`` before writing any bytes) when the
    requested resolution cannot be done safely: execution has begun yet no
    on-disk ``lanes.json`` exists to read the recorded SHA from (an
    inconsistent state finalize should never reach, since bootstrapping the
    event log itself requires a prior successful finalize run that already
    wrote ``lanes.json``); a refresh was requested but the branch tip could
    not be captured; an execution-begun refresh was requested whose recorded
    SHA is orphaned or foreign; or the no-flag default hit a proven orphan.
    """
    execution_has_begun = _execution_has_begun(repo_root, mission_slug, owned=owned)
    if not execution_has_begun:
        previous_sha: str | None = None
        action = "captured"
        if refresh_planning_commit:
            from specify_cli.lanes.persistence import read_lanes_json

            existing = read_lanes_json(planning_dir)
            previous_sha = existing.planning_commit_sha if existing is not None else None
            action = "refreshed"
        tip = capture_branch_tip(repo_root, target_branch)
        return PlanningCommitResolution(
            sha=tip,
            action=action,
            previous_sha=previous_sha,
            branch_tip=tip if refresh_planning_commit else None,
        )

    from specify_cli.lanes.persistence import is_execution_wedged, read_lanes_json

    existing: LanesManifest | None = read_lanes_json(planning_dir)
    if is_execution_wedged(execution_has_begun=execution_has_begun, lanes_present=existing is not None):
        error_msg = (
            f"Cannot re-finalize mission {mission_slug!r}: execution has begun "
            "(a WP is past 'planned') but no lanes.json exists on disk to "
            "preserve planning provenance from. Refusing to write a new "
            "lanes.json rather than guess a planning_commit_sha. Run "
            "'spec-kitty doctor mission-state --fix --mission "
            f"{mission_slug}' to rebuild lanes.json from the event log."
        )
        if json_output:
            _emit_json({"error": error_msg})
        else:
            console.print(f"[red]Error:[/red] {error_msg}")
        raise typer.Exit(1)
    # Narrowing note (not a suppression): ``is_execution_wedged`` is opaque to
    # mypy, so unlike the pre-WP01 inline ``if existing is None: raise`` it
    # narrows nothing on its own. We are past the raise above with
    # ``execution_has_begun`` True, so ``is_execution_wedged(...)`` being
    # False here can only mean ``lanes_present`` was True, i.e. ``existing``
    # is not None — assert makes that logical necessity visible to mypy.
    assert existing is not None
    # Type note (not a suppression): this module's [[tool.mypy.overrides]]
    # sets ``follow_imports = "skip"`` for all ``specify_cli.*`` modules (to
    # avoid walking the CLI bootstrap graph), so a single-file mypy invocation
    # loses ``LanesManifest``'s real field types across that import boundary
    # and sees ``existing.planning_commit_sha`` as ``Any`` — assigning ``Any``
    # to ``str | None`` is not an error, so no ignore is needed (the
    # pre-#4141 ``no-any-return`` ignore on the old ``return`` site became
    # unused when this became an assignment). ``planning_commit_sha`` is
    # genuinely ``str | None`` (specify_cli/lanes/models.py); `mypy
    # src/specify_cli/lanes/models.py src/specify_cli/lanes/persistence.py` in
    # isolation reports zero issues.
    recorded: str | None = existing.planning_commit_sha
    # #4827: captured once here (rather than separately inside each resolve_*
    # helper, the pre-#4827 shape) -- both the refresh and preserve branches
    # need the SAME tip snapshot to classify against (C-006).
    tip = capture_branch_tip(repo_root, target_branch)
    if refresh_planning_commit:
        return _resolve_refresh_planning_commit_decision(
            repo_root=repo_root,
            mission_slug=mission_slug,
            target_branch=target_branch,
            recorded=recorded,
            tip=tip,
            allow_orphaned=allow_orphaned,
            json_output=json_output,
        )
    return _resolve_preserve_planning_commit_decision(
        repo_root=repo_root,
        mission_slug=mission_slug,
        target_branch=target_branch,
        recorded=recorded,
        tip=tip,
        json_output=json_output,
    )


def _finalize_bookkeeping_commit_message(mission_slug: str) -> str:
    """Single source for finalize's own bookkeeping commit subject line.

    Used both as the ACTUAL commit message (:func:`_commit_finalize_
    artifacts`) and as the signature :func:`_drift_is_finalize_bookkeeping_
    only` checks for when distinguishing a real planning amendment from
    finalize's own prior re-run commits (#4178 / research.md D7(b)).
    """
    return f"Add tasks for feature {mission_slug}"


def _drift_is_finalize_bookkeeping_only(
    repo_root: Path,
    mission_slug: str,
    recorded_sha: str,
    branch_tip: str,
) -> bool:
    """#4178 / D7(b): True iff every commit between ``recorded_sha`` and
    ``branch_tip`` is finalize's OWN bookkeeping commit for this mission.

    The preserve-path drift WARN exists to catch a genuine planning
    amendment landing mid-execution — not finalize's own prior bookkeeping
    commits advancing the tip on every re-run, which happens unconditionally
    once execution has begun (``planning_commit_sha`` stays frozen while the
    branch keeps moving under finalize's own ``"Add tasks for feature ..."``
    commits). Verified (research.md D7): ``_compute_and_write_lanes``
    resolves this run's decision before ``_commit_finalize_artifacts`` lands
    that commit, so a re-finalize with no operator amendment in between still
    sees ``branch_tip != sha`` purely from a PRIOR run's own bookkeeping
    commit — a false positive this check exists to suppress.

    Fails OPEN (returns ``False`` — "real drift, keep warning") on any git
    error or an empty range: this only gates a non-blocking console WARN, and
    hiding a genuine drift signal is worse than an occasional over-warn.
    """
    import subprocess

    expected = _finalize_bookkeeping_commit_message(mission_slug)
    result = subprocess.run(
        ["git", "log", "--format=%s", f"{recorded_sha}..{branch_tip}"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return False
    subjects = [line for line in result.stdout.splitlines() if line]
    return bool(subjects) and all(subject == expected for subject in subjects)


def _report_planning_sha_decision(
    target_branch: str,
    planning_sha: PlanningCommitResolution | None,
    *,
    json_output: bool,
    repo_root: Path | None = None,
    mission_slug: str | None = None,
) -> None:
    """#4141/#4827: surface the ``planning_commit_sha`` decision on the console.

    Human-mode only: the ``--json`` success report carries the same decision
    structurally (``planning_commit`` in the payload), and a console print
    would corrupt the machine-readable payload (the same reason the
    coord-staleness WARN is gated on ``not json_output``). ``None`` (the
    historical monkeypatched test seam) reports nothing.

    Always called AFTER ``write_lanes_json`` has already run (#4178
    print-before-write; the caller -- :func:`_compute_and_write_lanes` --
    only reaches this call once ``compute_and_write_lanes`` has returned).

    ``repo_root``/``mission_slug`` are optional (keyword-only, default
    ``None``): when supplied, the preserve-path drift WARN additionally
    suppresses itself when the ONLY commits between the recorded SHA and the
    branch tip are finalize's own bookkeeping commits (#4178 / D7(b), via
    :func:`_drift_is_finalize_bookkeeping_only`). Omitting them keeps the
    pre-#4827 "any drift" behavior for direct unit-level callers of this
    function.
    """
    if json_output or planning_sha is None:
        return
    if planning_sha.action == "repinned":
        console.print(
            f"[green]✓[/green] Re-pinned orphaned planning_commit_sha "
            f"{planning_sha.previous_sha or '(none)'} -> {planning_sha.sha} "
            f"(lanes merge the {target_branch} tip at their next allocation)"
        )
        return
    if planning_sha.action == "refreshed":
        console.print(
            f"[green]✓[/green] Refreshed planning_commit_sha "
            f"{planning_sha.previous_sha or '(none)'} -> {planning_sha.sha} "
            f"(lanes merge the {target_branch} tip at their next allocation)"
        )
        return
    if planning_sha.action == "kept_with_warning":
        # Ruling Q6 (FR-012/T084): the AUTOMATIC refresh could not prove a
        # safe advance for a non-orphan FOREIGN pin (the recorded object is
        # absent from the repository entirely) or classify an INDETERMINATE
        # one (WP15 cycle 2 C2-1 — an uncapturable tip or no recorded SHA at
        # all, also now reported here rather than degrading silently) — warn
        # and keep the old pin rather than fail closed. Printed here (after
        # ``write_lanes_json`` already ran with the OLD sha unchanged) per
        # the #4178 print-after-write convention this function's docstring
        # documents.
        if planning_sha.refusal_reason == "indeterminate_tip_uncapturable":
            # WP15 cycle 2 (C2-1): both pieces may be missing (that is
            # exactly what makes the pin INDETERMINATE), so the message
            # names whichever is actually absent instead of assuming either
            # is present.
            recorded_desc = planning_sha.previous_sha or "(no pin recorded yet)"
            tip_desc = planning_sha.branch_tip or "(uncapturable)"
            console.print(
                f"[yellow]⚠[/yellow] planning_commit_sha could not be classified against the "
                f"{target_branch!r} tip: recorded={recorded_desc}, tip={tip_desc} (the target "
                "branch tip could not be resolved -- e.g. a non-git workspace, or the branch "
                "does not exist yet -- or there is no recorded pin to classify); keeping the "
                "recorded pin unchanged. No action is needed unless the target branch is "
                "expected to exist."
            )
            return
        # WP15 cycle 2 (B8): the remedy named below must actually work. A
        # FOREIGN pin's object cannot be inspected at all, so
        # ``--refresh-planning-commit --allow-orphaned`` is REFUSED for it
        # too (``_resolve_refresh_planning_commit_decision`` refuses FOREIGN
        # unconditionally -- ``--allow-orphaned`` only lifts the refusal for
        # a proven ORPHAN, a different, inspectable shape). There is no
        # automated recovery for a genuinely absent object; the message says
        # so instead of pointing at a command that is guaranteed to fail.
        console.print(
            f"[yellow]⚠[/yellow] planning_commit_sha {planning_sha.previous_sha!r} could not be "
            f"safely auto-refreshed to the {target_branch} tip {planning_sha.branch_tip} "
            "(the recorded commit object is absent from this repository, so it cannot be "
            "verified at all); keeping the recorded pin. This object cannot be re-pointed "
            "automatically -- investigate how it was recorded (e.g. a stale clone or a "
            "pruned object), then correct lanes.json's planning_commit_sha manually once "
            "you have confirmed the right pin."
        )
        return
    if planning_sha.action == "preserved" and planning_sha.sha is not None and planning_sha.branch_tip is not None and planning_sha.branch_tip != planning_sha.sha:
        if (
            repo_root is not None
            and mission_slug is not None
            and _drift_is_finalize_bookkeeping_only(repo_root, mission_slug, planning_sha.sha, planning_sha.branch_tip)
        ):
            return
        console.print(
            f"[yellow]⚠[/yellow] Planning branch {target_branch} has advanced since "
            f"planning_commit_sha was recorded ({planning_sha.sha} -> tip {planning_sha.branch_tip}); "
            "lanes keep merging the recorded snapshot. If that advance is a legitimate "
            "planning amendment, re-run finalize-tasks with --refresh-planning-commit to re-point it."
        )


def _compute_and_write_lanes(
    planning_dir: Path,
    repo_root: Path,
    mission_slug: str,
    wp_manifests: dict[str, OwnershipManifest],
    wp_dependencies: dict[str, list[str]],
    wp_frontmatters: dict[str, WPMetadata],
    wp_bodies: dict[str, str],
    meta: dict[str, object] | None,
    target_branch: str,
    *,
    all_canceled: bool = False,
    json_output: bool,
    owned: OwnedCheckout | None = None,
    refresh_planning_commit: bool = False,
    allow_orphaned: bool = False,
    planning_sha: PlanningCommitResolution | None = None,
) -> tuple[Path | None, LanesManifest | None, PlanningCommitResolution | None]:
    """Phase: compute execution lanes + write lanes.json + risk report.

    Thin CLI wrapper (WP01, #4758) around the pure
    :func:`specify_cli.lanes.compute_and_persist.compute_and_write_lanes`
    core: this function resolves the two CLI/status-partition inputs the
    core needs already-resolved (``planning_commit_sha`` via the
    still-local :func:`_preserve_or_capture_planning_commit_sha`, and
    ``mission_id`` from ``meta.json``), calls the core, then reports the
    outcome on the console / in ``--json`` and runs the (``policy``-backed)
    parallelization-risk report -- none of which the pure core may import.
    Behavior is unchanged for the healthy path (NFR-003-style
    behavior-preservation): only the glob-revalidation-failure /
    lane-computation bodies moved, verbatim, into the core.
    """
    _raise_lane_computation_empty_input_if_needed(
        wp_manifests,
        wp_dependencies,
        wp_frontmatters,
        all_canceled=all_canceled,
        json_output=json_output,
    )
    from specify_cli.lanes.compute_and_persist import LaneGlobValidationError, compute_and_write_lanes
    from specify_cli.migration.backfill_topology import topology_from_meta

    raw_mission_id = meta.get("mission_id") if meta else None
    mission_id = raw_mission_id if isinstance(raw_mission_id, str) else None
    # FR-009 / ADR 2026-07-29-1 (T002): freeze the recorded planning-artifact SHA
    # into the SAME write as the rest of lanes.json — no second commit, no
    # chicken-and-egg with this invocation's own finalize commit hash.
    # #3311 T015: once execution has begun, PRESERVE the previously-recorded
    # SHA instead of re-capturing the current branch tip — unless the operator
    # explicitly re-pointed it with --refresh-planning-commit (#4141). See
    # ``_preserve_or_capture_planning_commit_sha``.
    if planning_sha is None:
        planning_sha = _preserve_or_capture_planning_commit_sha(
            planning_dir,
            repo_root,
            mission_slug,
            target_branch,
            json_output=json_output,
            owned=owned,
            refresh_planning_commit=refresh_planning_commit,
            allow_orphaned=allow_orphaned,
        )
    # Tolerate a ``None`` resolution: the historical test seam in
    # ``test_mission_finalize_phases.py`` monkeypatches this helper to return
    # ``None``, the pre-#4141 shape's value the manifest was assigned verbatim.
    resolved_sha = planning_sha.sha if planning_sha is not None else None
    # #5100 M3 (review cycle-1 nit 3): derived from the ALREADY-loaded,
    # tolerant `meta` parameter this wrapper already accepts (never a
    # second, stricter meta.json read) -- mirrors tasks_finalize.py's
    # identical fix. Read-only (C-003): the fail-closed writer check now
    # lives inside compute_and_write_lanes itself (WP05).
    topology = topology_from_meta(meta or {}, planning_dir)
    raw_mission_branch = meta.get("mission_branch") if meta else None
    resolved_mission_branch = raw_mission_branch if isinstance(raw_mission_branch, str) else None
    try:
        lanes_path, lanes_manifest = compute_and_write_lanes(
            planning_dir,
            repo_root,
            mission_slug,
            wp_manifests,
            wp_dependencies,
            wp_frontmatters,
            wp_bodies,
            target_branch,
            planning_commit_sha=resolved_sha,
            mission_id=mission_id,
            topology=topology,
            mission_branch=resolved_mission_branch,
        )
    except LaneGlobValidationError as exc:
        glob_result = exc.result
        if not json_output:
            lane_stderr = err_console
            for err in glob_result.errors:
                lane_stderr.print(f"[red]ERROR:[/red] Lane-compute re-validation: {err}")
        # Single-source the abort message through the exception the pure core
        # raises (lanes.compute_and_persist.LaneGlobValidationError) rather than
        # re-hardcoding the identical literal here (SSOT — squad MINOR).
        error_msg = str(exc)
        if json_output:
            _emit_json({"error": error_msg, "ownership_literal_path_errors": glob_result.errors})
        else:
            console.print(f"[red]Error:[/red] {error_msg}")
        raise typer.Exit(1) from None
    except TopologyManifestMismatch as exc:
        # #5100 WP05: a single_branch mission whose on-disk lanes.json still
        # has a code lane (never re-stamped after #5100) -- the manifest
        # write is refused, so no lanes.json changed. Reported the same way
        # the sibling LaneGlobValidationError branch above is: JSON envelope
        # or console, never a raw traceback.
        error_msg = str(exc)
        if json_output:
            _emit_json({"error": error_msg, "error_code": exc.error_code})
        else:
            console.print(f"[red]Error:[/red] {error_msg}")
        raise typer.Exit(1) from None
    _report_planning_sha_decision(
        target_branch,
        planning_sha,
        json_output=json_output,
        repo_root=repo_root,
        mission_slug=mission_slug,
    )
    if not json_output:
        console.print(f"[green]✓[/green] Computed {len(lanes_manifest.lanes)} execution lane(s)")
        if lanes_manifest.collapse_report and lanes_manifest.collapse_report.independent_wps_collapsed > 0:
            console.print(
                f"[yellow]⚠[/yellow] {lanes_manifest.collapse_report.independent_wps_collapsed} "
                f"independent WP pair(s) collapsed into same lane. Run with --json to see details."
            )
    _report_parallelization_risk(repo_root, lanes_manifest, wp_bodies, json_output=json_output)
    return lanes_path, lanes_manifest, planning_sha


def _report_parallelization_risk(repo_root: Path, lanes_manifest: LanesManifest, wp_bodies: dict[str, str], *, json_output: bool) -> None:
    """Phase: compute + (optionally block on) the parallelization risk report."""
    from specify_cli.policy.config import load_policy_config
    from specify_cli.policy.risk_scorer import compute_risk_report

    policy = load_policy_config(repo_root)
    risk_report = compute_risk_report(lanes_manifest, wp_bodies=wp_bodies, policy=policy.risk)
    if risk_report.overall_score > 0 and not json_output:
        console.print(f"[yellow]⚠[/yellow] Parallelization risk: {risk_report.overall_score:.2f} (threshold: {risk_report.threshold:.2f})")
        for pr in risk_report.lane_pair_risks:
            if pr.score > 0:
                console.print(f"  {pr.lane_a} ↔ {pr.lane_b}: {pr.score:.2f}")
                for d in pr.shared_parent_dirs[:3]:
                    console.print(f"    shared dir: {d}")
                for c in pr.import_coupling[:3]:
                    console.print(f"    coupling: {c}")
    if risk_report.exceeds_threshold and policy.risk.mode == "block":
        error_msg = f"Parallelization risk {risk_report.overall_score:.2f} exceeds threshold {risk_report.threshold:.2f}. Adjust the risk policy to proceed."
        if json_output:
            _emit_json(
                {
                    "error": error_msg,
                    "risk_report": {"overall_score": risk_report.overall_score, "threshold": risk_report.threshold},
                }
            )
        else:
            console.print(f"[red]Error:[/red] {error_msg}")
        raise typer.Exit(1)


def _resolve_acceptance_matrix_home(repo_root: Path, planning_dir: Path, mission_slug: str, *, owned: OwnedCheckout | None = None) -> Path:
    """Resolve the acceptance matrix's declared home dir AND establish it (FR-010 / C8 / B6 cycle 2).

    WP15 (Decision ``plan.design.translate-if-present-kinds``): resolves
    through ``write_dir(ACCEPTANCE_MATRIX)`` -- the single write-location
    authority -- never the gate's READ-side resolver
    (``_acceptance_matrix_read_dir`` / ``read_dir``). The DoD line "no
    finalize write leg uses a read resolver for a COORD kind" applies here
    too: a READ resolver's EMPTY/UNMATERIALIZED -> PRIMARY degrade (C-002)
    would misclassify a never-seeded coordination Mission's home as
    ``planning_dir``, routing the scaffold's bare write there instead of
    establishing the real coordination surface first. A ``DELETED``
    coordination branch has no writable home at all, so we fall back to the
    primary ``planning_dir`` -- the scaffold is a convenience artifact and
    must never fail finalize (the caller's own ``except Exception`` is the
    broader safety net for every OTHER write_dir refusal, e.g. a remote-only
    branch).
    """
    from mission_runtime import placement_seam
    from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted

    if owned:
        return placement_seam(owned.repository_root, owned.mission_slug, owned=owned).write_dir(MissionArtifactKind.ACCEPTANCE_MATRIX).path
    try:
        return placement_seam(repo_root, mission_slug).write_dir(MissionArtifactKind.ACCEPTANCE_MATRIX).path
    except CoordinationBranchDeleted:
        return planning_dir


def _scaffold_acceptance_matrix_if_lane_based(
    planning_dir: Path,
    repo_root: Path,
    mission_slug: str,
    lanes_manifest: LanesManifest | None,
    functional_spec_requirement_ids: set[str],
    *,
    validate_only: bool,
    json_output: bool,
    owned: OwnedCheckout | None = None,
) -> None:
    """Phase: Finding 6 — scaffold acceptance-matrix.json for lane-based missions."""
    if lanes_manifest is None or validate_only:
        return
    try:
        from specify_cli.acceptance.matrix import scaffold_acceptance_matrix

        # FR-010 / C8: resolve the matrix's DECLARED HOME through the same surface
        # resolver the accept gate reads from, so the scaffolder's idempotency check
        # sees an existing coord-homed matrix and never authors a divergent second
        # primary copy (#2882). A deleted coord branch (fail-loud) falls back to the
        # primary planning dir — the scaffold is a convenience artifact, never a gate.
        home_dir = _resolve_acceptance_matrix_home(repo_root, planning_dir, mission_slug, **({"owned": owned} if owned else {}))
        # write-surface-coherence WP08 (#2804 / #2404 T040/T041): thread
        # ``repo_root`` so the WRITE (not just the idempotency check) routes
        # through the coord-aware write-seam — never a stray PRIMARY husk
        # under coord topology, mirroring the sibling issue-matrix scaffold.
        #
        # FR-015/NFR-001 (WP13 T072/T073): when the declared home IS
        # ``planning_dir`` -- every topology this mission's atomic-finalize
        # mandate covers (``LIFECYCLE_OWNED_TOPOLOGIES`` is single_branch-only,
        # and a flat/non-coord repository-root mission resolves here too) --
        # there is no separate coordination surface for a write-seam commit to
        # route to. Omitting ``repo_root`` takes ``scaffold_acceptance_
        # matrix``'s bare-write branch (``write_acceptance_matrix``, no
        # commit): `_collect_finalize_artifacts` already lists
        # ``acceptance-matrix.json`` as a TASKS_INDEX candidate, so the write
        # rides the SAME single combined commit ``_commit_finalize_
        # artifacts`` makes for frontmatter/tasks.md/lanes.json below --
        # closing the separate-commit atomicity gap T070 pinned (a failure
        # inside that later, single commit now leaves NO acceptance-matrix
        # commit stranded, because none was ever made separately). A
        # genuinely coord-routed home (a LANES/coord-topology repository-root
        # mission, outside this WP's single_branch-owned mandate) keeps
        # today's write-seam-routed, separately-committed scaffold unchanged.
        writes_to_planning_dir = home_dir.resolve() == planning_dir.resolve()
        acceptance_matrix_path = scaffold_acceptance_matrix(
            planning_dir,
            mission_slug,
            requirement_ids=sorted(functional_spec_requirement_ids),
            home_dir=home_dir,
            repo_root=None if writes_to_planning_dir else (owned.repository_root if owned else repo_root),
            policy=_mission_protection_policy(repo_root, mission_slug, owned),
            owned=owned,
        )
    except Exception as acc_matrix_exc:  # noqa: BLE001 — convenience artifact never blocks finalize
        if owned:
            raise
        if not json_output:
            console.print(f"[yellow]Warning:[/yellow] could not scaffold acceptance-matrix.json: {acc_matrix_exc}")
            console.print(f"[yellow]Hint:[/yellow] create it manually before acceptance:\n  spec-kitty agent mission finalize-tasks --mission {mission_slug}")
        return
    if acceptance_matrix_path is not None and not json_output:
        try:
            rel: Path = acceptance_matrix_path.relative_to(repo_root)
        except ValueError:
            rel = acceptance_matrix_path
        console.print(f"[info] Scaffolded {rel}")


@dataclass
class _CommitOutcome:
    """Outcome of the finalize commit phase.

    ``commit_hash`` remains the historical single-value projection (the
    feature-branch commit for the common case) for backward compatibility.
    ``commit_hashes`` (#2549 facet B) additionally carries the FULL per-branch
    commit set the router actually issued — under coord topology this includes
    BOTH the feature-branch commit (primary-partition artifacts: tasks.md,
    lanes.json, tasks/WP*) AND the coordination-branch commit (placement-
    partition artifacts: status.events.jsonl, status.json, acceptance-
    matrix.json, issue-matrix.md), which ``commit_hash`` alone cannot express.
    """

    commit_created: bool = False
    commit_hash: str | None = None
    commit_hashes: list[dict[str, str]] = field(default_factory=list)
    files_committed: list[str] = field(default_factory=list)
    diagnostic: str | None = None
    #: WP15/FR-007 (contracts/commit-outcome.md): the serialized per-surface
    #: outcome -- ``commit_outcome_payload(router_result)["surfaces"]``, never
    #: hand-formatted (rule 6). Empty for the pre-``surfaces`` legacy case
    #: (no commit attempted) or any caller that never reached the router.
    commit_surfaces: list[dict[str, object]] = field(default_factory=list)
    #: True iff any surface in ``commit_surfaces`` is ``refused``/``error``
    #: (:func:`~specify_cli.coordination.commit_outcome.commit_outcome_exit_code`
    #: contract rule 5) -- the caller raises after rendering, never before.
    surface_refusal: bool = False
    #: WP13-review binding correction: ``render_commit_outcome(router_result)``'s
    #: plain text lines, computed once alongside ``commit_surfaces`` from the
    #: SAME real router result -- never re-derived from the serialized
    #: ``commit_surfaces`` payload. Printed with ``markup=False`` by every
    #: text-mode consumer (untrusted path/diagnostic content, never Rich markup).
    rendered_lines: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _FinalizeCommitCandidates:
    """T071 campsite: the resolved commit-candidate file list plus whether any are dirty."""

    files_to_commit: list[Path]
    files_to_commit_rel: list[str]
    has_relevant_changes: bool


def _finalize_candidates_dirty(repo_root: Path, files_to_commit_rel: list[str]) -> bool:
    """True when any finalize candidate path has a pending change.

    A failed probe propagates (``GitCommandError``) rather than reading as "no
    changes", which would silently skip the finalize commit.
    """
    return bool(status_entries(repo_root, pathspecs=files_to_commit_rel, untracked=None))


#: WP15/T081 (FR-007b): the COORD-partition kinds whose files finalize may itself
#: write, each resolved through its own ``write_dir``. ``STATUS_STATE`` covers the
#: event-log/snapshot files; ``ISSUE_MATRIX``/``ACCEPTANCE_MATRIX`` each resolve
#: their own kind-specific directory (identical to the STATUS_STATE one for a
#: coordination-routed Mission's single Mission dir, but resolved independently
#: so a kind-specific routing exception -- e.g. the PUBLISHED/E2 short-circuit --
#: is honored per kind rather than assumed). The FILENAMES are never listed here:
#: :func:`_coord_candidate_filenames` derives them from the artifact classifier,
#: so a classifier entry (e.g. the failover-read ``issue-matrix.md``) can never be
#: invisible to this probe.
_COORD_CANDIDATE_KINDS: Final[tuple[MissionArtifactKind, ...]] = (
    MissionArtifactKind.STATUS_STATE,
    MissionArtifactKind.ISSUE_MATRIX,
    MissionArtifactKind.ACCEPTANCE_MATRIX,
)


def _coord_candidate_filenames(kind: MissionArtifactKind) -> tuple[str, ...]:
    """The basenames the artifact classifier maps to *kind*, in a stable order."""
    return tuple(sorted(mission_file_basenames_for_kind(kind)))


@dataclass(frozen=True)
class _CoordCandidateDirt:
    """WP15/T081: resolved COORD-kind commit candidates plus whether any are dirty."""

    files: list[Path]
    is_dirty: bool


def _coord_candidate_dirt(
    repo_root: Path,
    mission_slug: str,
    *,
    owned: OwnedCheckout | None,
) -> _CoordCandidateDirt:
    """Resolve finalize's COORD-kind commit candidates and probe them for dirt (FR-007b).

    ``_resolve_finalize_commit_candidates``'s own porcelain check runs only in
    the repository-root checkout, so a coordination-routed Mission's
    lifecycle records -- which land in the coordination worktree after
    WP15/T080 -- read as "no changes" even while genuinely dirty there. This
    helper resolves each COORD kind's write location FIRST (write-before-check,
    research D2): a pending seed is committed by ``write_dir`` before the
    porcelain probe ever runs, so a never-seeded pre-fix Mission reports real
    dirt instead of silently reading clean. Deduplicates resolved
    directories: under ``lanes``/``single_branch`` topology (C-008) every
    kind's ``write_dir`` returns the SAME ``planning_dir`` the PRIMARY
    candidates already cover, so this never double-reports or double-commits
    those paths.
    """
    from mission_runtime import placement_seam

    seam = placement_seam(repo_root, mission_slug, owned=owned)
    checkout_roots_by_dir: dict[Path, Path] = {}
    candidates: list[Path] = []
    for kind in _COORD_CANDIDATE_KINDS:
        location = seam.write_dir(kind)
        checkout_roots_by_dir.setdefault(location.path, location.surface_root)
        for filename in _coord_candidate_filenames(kind):
            candidate = location.path / filename
            if candidate.exists():
                candidates.append(candidate)

    seen: set[Path] = set()
    files: list[Path] = []
    for candidate in candidates:
        if candidate not in seen:
            files.append(candidate)
            seen.add(candidate)

    is_dirty = False
    for directory, checkout_root in checkout_roots_by_dir.items():
        rel_files = [str(path.relative_to(checkout_root)) for path in files if path.is_relative_to(directory)]
        if not rel_files:
            continue
        # A failed probe propagates (``GitCommandError``) -- see ``_finalize_candidates_dirty``.
        if _finalize_candidates_dirty(checkout_root, rel_files):
            is_dirty = True

    return _CoordCandidateDirt(files=files, is_dirty=is_dirty)


def _resolve_finalize_commit_candidates(
    planning_dir: Path,
    tasks_dir: Path,
    repo_root: Path,
    lanes_path: Path | None,
    *,
    mission_slug: str,
    owned: OwnedCheckout | None = None,
) -> _FinalizeCommitCandidates:
    """Phase: collect and porcelain-check the finalize commit-candidate file list (T071/WP15-T081).

    meta.json (#3466 / SK3466-RR-001) needs no special-cased ``extra_paths``
    threading here: :func:`_collect_finalize_artifacts` already includes it as
    a candidate, so a ``--target-branch`` correction rides the same ``git
    status --porcelain`` gate as every other tracked artifact. But unlike
    those other artifacts, meta.json can ALSO carry a pending edit
    finalize-tasks did not make (SK3466-REV-001, e.g. ``implement
    --no-auto-commit``'s ``vcs``/``vcs_locked_at`` write) — so it is
    additionally checked with :func:`_meta_json_delta_is_finalize_attributable`
    and dropped entirely when the pending delta is not confined to the
    fields finalize-tasks itself owns.

    WP15/T081 (FR-007b): ``has_relevant_changes`` additionally honors
    :func:`_coord_candidate_dirt` -- the COORD-kind commit candidates
    (resolved via ``write_dir``, never the PRIMARY-anchored porcelain check
    below) -- so coordination-only dirt is never reported as "no changes".
    """
    files_to_commit = _collect_finalize_artifacts(planning_dir, tasks_dir, lanes_path=lanes_path)
    meta_json_path = planning_dir / META_JSON_FILENAME
    if meta_json_path in files_to_commit and not _meta_json_delta_is_finalize_attributable(meta_json_path, repo_root):
        files_to_commit = [path for path in files_to_commit if path != meta_json_path]

    primary_files_rel = [str(path.relative_to(repo_root)) for path in files_to_commit]
    primary_dirty = bool(primary_files_rel) and _finalize_candidates_dirty(repo_root, primary_files_rel)

    coord_dirt = _coord_candidate_dirt(repo_root, mission_slug, owned=owned)
    seen_files = set(files_to_commit)
    for candidate in coord_dirt.files:
        if candidate not in seen_files:
            files_to_commit.append(candidate)
            seen_files.add(candidate)

    files_to_commit_rel = [_finalize_candidate_display_path(path, repo_root) for path in files_to_commit]
    return _FinalizeCommitCandidates(
        files_to_commit=files_to_commit,
        files_to_commit_rel=files_to_commit_rel,
        has_relevant_changes=primary_dirty or coord_dirt.is_dirty,
    )


def _finalize_candidate_display_path(path: Path, repo_root: Path) -> str:
    """Repo-root-relative display form of a candidate, or an absolute fallback.

    A COORD-kind candidate resolved via ``write_dir`` may live inside a
    SEPARATE coordination worktree checkout, never under ``repo_root`` — this
    is display-only (JSON ``files_committed`` / the console summary), never
    fed back into a git invocation, so an absolute fallback is honest rather
    than a crash or a misleading synthetic relative path.
    """
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def _apply_finalize_commit_router_result(
    router_result: CommitRouterResult,
    outcome: _CommitOutcome,
    files_to_commit_rel: list[str],
    *,
    json_output: bool,
    updated_count: int,
) -> None:
    """Phase: fold ``commit_for_mission``'s result into ``outcome``, or refuse (T071/WP15-T082).

    Every status leg populates ``outcome.commit_surfaces``/``surface_refusal``
    (contract rule 6: the shared trio is the ONLY renderer) so a refused
    coordination surface is visible even when the top-level legacy
    ``status`` still reads ``committed`` (the PRIMARY group landed fine) --
    the caller (:func:`_run_commit_pipeline`) raises on ``surface_refusal``
    AFTER the JSON/text report has already rendered it (FR-007 exit-code
    rule: a refused/error surface must still be REPORTED, not swallowed by
    an early raise).

    WP13-review binding corrections (applied here too, first consumer):
    when ``surfaces`` is populated, :func:`render_commit_outcome`'s lines are
    printed on EVERY outcome arm -- including the legacy-error arm below --
    THEN any existing actionable error line, never the legacy diagnostic
    alone. Every rendered line is printed with ``markup=False``:
    :func:`render_commit_outcome` returns plain, untrusted-content-bearing
    strings (file paths, diagnostics), never Rich markup, so a literal ``[``
    in a path/reason must not be interpreted as a markup tag.
    """
    from specify_cli.coordination.commit_outcome import (
        commit_outcome_exit_code,
        commit_outcome_payload,
        render_commit_outcome,
    )

    outcome.commit_surfaces = cast("list[dict[str, object]]", commit_outcome_payload(router_result)["surfaces"])
    outcome.surface_refusal = commit_outcome_exit_code(router_result) != 0
    outcome.rendered_lines = render_commit_outcome(router_result)

    def _print_surfaces() -> None:
        for line in outcome.rendered_lines:
            console.print(line, markup=False)

    if router_result.status == "committed":
        outcome.commit_hash = router_result.commit_hash
        outcome.commit_created = True
        # WP06 (#2937 / FR-009): only now is the committed set real.
        outcome.files_committed = list(files_to_commit_rel)
        outcome.commit_hashes = [{"branch": ref, "hash": commit_hash} for ref, commit_hash in router_result.commit_hashes]
        if not json_output:
            _print_surfaces()
            console.print(f"[dim]Updated {updated_count} WP files with dependencies[/dim]")
    elif router_result.status == "unchanged":
        outcome.commit_created = False
        if not json_output:
            if outcome.rendered_lines:
                _print_surfaces()
            else:
                console.print("[dim]Tasks unchanged, no commit needed[/dim]")
    else:
        error_output = router_result.diagnostic or "Failed to commit tasks updates"
        if json_output:
            print(json.dumps({"error": f"Git commit failed: {error_output}"}))
        else:
            _print_surfaces()
            console.print(f"[red]Error:[/red] Git commit failed: {error_output}")
        raise typer.Exit(1)


class OwnedCheckoutCandidateOutsidePlanningError(RuntimeError):
    """WP15 cycle 3 (fold): an owned-checkout commit candidate resolved outside
    ``planning_dir`` -- the invariant ``_commit_finalize_artifacts`` relies on
    to rewrite candidates onto the owned checkout root safely. Today this can
    only happen if ``LIFECYCLE_OWNED_TOPOLOGIES`` widens beyond
    single_branch to include a coordination-routing topology without this
    call site being updated to match.
    """


def _commit_finalize_artifacts(
    planning_dir: Path,
    tasks_dir: Path,
    repo_root: Path,
    mission_slug: str,
    target_branch: str,
    lanes_path: Path | None,
    preexisting_primary_files: set[Path],
    *,
    json_output: bool,
    updated_count: int,
    owned: OwnedCheckout | None = None,
) -> _CommitOutcome:
    """Phase: commit finalize artifacts through commit_for_mission.

    Routes ``run_command`` through the ``mission`` module to preserve the
    ``mission.run_command`` patch seam. T027 / WP02: collapsed to the
    ``commit_for_mission`` entry point (TASKS_INDEX → primary target branch for
    every topology).
    """
    outcome = _CommitOutcome()
    try:
        candidates = _resolve_finalize_commit_candidates(planning_dir, tasks_dir, repo_root, lanes_path, mission_slug=mission_slug, owned=owned)
        # partition-authority-residuals-01M021K9 WP06 (#2937 / FR-009): report the
        # TRUE committed set — ``files_committed`` is populated ONLY once the router
        # actually lands a commit (below), never up front. Reporting the full
        # candidate set here regardless of outcome misled automated callers on the
        # no-change / "unchanged" paths (nothing was committed, yet every candidate
        # was named as committed).
        if not candidates.has_relevant_changes:
            if not json_output:
                console.print("[dim]Tasks unchanged, no commit needed[/dim]")
            return outcome

        from specify_cli.coordination.commit_router import commit_for_mission

        files_to_commit = candidates.files_to_commit
        tasks_policy = _mission_protection_policy(repo_root, mission_slug, owned)
        if owned:
            # WP15 cycle 3 (fold, non-blocking from cycle 2): ``owned.files()``
            # rewrites candidates onto the OWNED checkout root, which is sound
            # only because ``LIFECYCLE_OWNED_TOPOLOGIES`` is single_branch-only
            # today (``routes_through_coordination`` is False for it, so
            # ``_resolve_finalize_commit_candidates`` never resolves a
            # COORD-kind candidate via ``write_dir`` for an owned mission). If
            # that set ever widens to include a coordination-routing topology,
            # this guard fails loudly here instead of silently rewriting a
            # coordination path onto the wrong checkout. A bare ``assert`` is
            # stripped under ``python -O``, so this is a real, unconditional
            # raise instead.
            non_planning = [path for path in files_to_commit if not path.is_relative_to(planning_dir)]
            if non_planning:
                raise OwnedCheckoutCandidateOutsidePlanningError(
                    "owned checkout commit candidates must all resolve under planning_dir; "
                    f"LIFECYCLE_OWNED_TOPOLOGIES widened to a coordination-routing topology "
                    f"without updating this guard (offending paths: {non_planning!r})"
                )
            files_to_commit = owned.files(files_to_commit)
        # WP15/T081: ``primary_paths_created_this_invocation`` is, by name, a
        # PRIMARY-partition residue-cleanup signal -- a COORD-kind candidate
        # (resolved via ``write_dir``, never under ``planning_dir``) is never
        # "preexisting" by the ``preexisting_primary_files`` snapshot (which
        # only ever scanned ``planning_dir``), so it would otherwise be
        # misclassified as newly-created PRIMARY residue on every run.
        primary_created = frozenset(path for path in files_to_commit if path not in preexisting_primary_files and path.is_relative_to(planning_dir))
        router_result = commit_for_mission(
            repo_root=owned.repository_root if owned else repo_root,
            mission_slug=mission_slug,
            files=tuple(files_to_commit),
            message=_finalize_bookkeeping_commit_message(mission_slug),
            policy=tasks_policy,
            kind=MissionArtifactKind.TASKS_INDEX,
            primary_paths_created_this_invocation=primary_created,
            target_branch=target_branch,
            owned=owned,
        )
        _apply_finalize_commit_router_result(
            router_result,
            outcome,
            candidates.files_to_commit_rel,
            json_output=json_output,
            updated_count=updated_count,
        )
    except typer.Exit:
        raise
    except Exception as e:
        if json_output:
            _emit_json({"error": str(e)})
        else:
            console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None
    return outcome


def _emit_success_report(
    tasks_dir: Path,
    state: _BootstrapState,
    commit_outcome: _CommitOutcome,
    dep_resolution: _DependencyResolution,
    bootstrap_result: BootstrapResult,
    lanes_manifest: LanesManifest | None,
    *,
    target_branch_override: str | None = None,
    target_branch_persist: TargetBranchPersistOutcome | None = None,
    meta_committed_this_run: bool = False,
    planning_sha: PlanningCommitResolution | None = None,
    planning_commit_refresh: dict[str, object] | None = None,
) -> None:
    """Phase: emit the terminal JSON success report.

    ``target_branch_override`` / ``target_branch_persist`` (SK3466-R-003):
    a ``--target-branch`` override durably rewrites meta.json's canonical
    merge destination, but the payload previously carried no signal that a
    mutation occurred or what the previous value was — the only observable
    trace for a ``--json`` caller was "meta.json" appearing in
    ``files_committed``, indistinguishable from any other artifact commit.
    ``target_branch_override`` is only non-``None`` when the flag was
    actually supplied this run.

    ``planning_sha`` (#4141): the ``planning_commit_sha`` decision this run
    made (captured / preserved / refreshed, the previous SHA, and the branch
    tip it was compared against), so a ``--json`` caller can see that the
    recorded SHA was preserved against a moved branch tip — and re-run with
    ``--refresh-planning-commit`` — without diffing ``lanes.json`` by hand.

    ``meta_committed_this_run`` (SK3466-REV2-002): ``persist.persisted=True``
    only means meta.json was rewritten to disk this call — it says nothing
    about whether that write survived ``_commit_finalize_artifacts``'s
    attribution check (``_meta_json_delta_is_finalize_attributable`` excludes
    meta.json entirely when a foreign field is pending alongside our
    ``target_branch`` write). A ``--json`` caller checking ``persisted``
    alone — its documented use — could not tell "durably committed" from
    "written but left dangling because it was excluded from this commit".
    Computed once by ``_run_commit_pipeline`` from ``commit_outcome.
    files_committed`` (the same value that already gates the revert-safety
    marker for SK3466-REV2-001) and passed through here rather than
    re-derived, so both corrections share one source of truth.
    """
    persist = target_branch_persist or TargetBranchPersistOutcome(persisted=False)
    # #4141: the planning_commit_sha decision. Falls back to the manifest's
    # own SHA when no resolution was threaded through (defensive only — the
    # commit pipeline always passes one).
    _emit_json(
        {
            "result": "success",
            "wp_count": len(state.work_packages),
            "updated_wp_count": state.updated_count,
            "modified_wps": state.modified_wps,
            "unchanged_wps": state.unchanged_wps,
            "preserved_wps": state.preserved_wps,
            "tasks_dir": str(tasks_dir),
            "commit_created": commit_outcome.commit_created,
            "commit_hash": commit_outcome.commit_hash,
            "commit_hashes": commit_outcome.commit_hashes,
            # WP15/FR-007 (contracts/commit-outcome.md): per-surface outcome,
            # beside the legacy caller-surface-only fields above.
            "commit_surfaces": commit_outcome.commit_surfaces,
            "files_committed": commit_outcome.files_committed,
            "dependencies_parsed": dep_resolution.wp_dependencies,
            "requirement_refs_parsed": dep_resolution.wp_requirement_refs,
            "bootstrap": {
                "total_wps": bootstrap_result.total_wps,
                "newly_seeded": bootstrap_result.newly_seeded,
                "already_initialized": bootstrap_result.already_initialized,
            },
            "lanes": {
                "computed": lanes_manifest is not None,
                "count": len(lanes_manifest.lanes) if lanes_manifest else 0,
                "lane_ids": [lane.lane_id for lane in lanes_manifest.lanes] if lanes_manifest else [],
                "planning_artifact_wps": lanes_manifest.planning_artifact_wps if lanes_manifest else [],
                "collapse_report": (lanes_manifest.collapse_report.to_dict() if lanes_manifest and lanes_manifest.collapse_report else None),
            },
            "ownership_warnings": state.ownership_warnings,
            "requirement_extraction_warnings": state.requirement_extraction_warnings,
            "post_integration_acceptance_warnings": state.post_integration_acceptance_warnings,
            "target_branch_override": {
                "requested": target_branch_override,
                "persisted": persist.persisted,
                # SK3466-REV2-002: distinct from ``persisted`` -- ``True``
                # only when meta.json's delta actually rode this commit.
                # ``persisted and not committed`` means the override is
                # written to disk but excluded from this run's commit and
                # left dangling in the working tree (mixed with a foreign
                # meta.json field also pending).
                "committed": persist.persisted and meta_committed_this_run,
                "previous_value": persist.previous_value,
                "persist_error": persist.persist_error,
            },
            "planning_commit": _planning_commit_payload(planning_sha, lanes_manifest),
            # WP15/FR-012 (contracts/commit-outcome.md): the AUTOMATIC
            # refresh decision, additive and distinct from the legacy
            # ``planning_commit`` projection above.
            "planning_commit_refresh": planning_commit_refresh,
            **({"commit_diagnostic": commit_outcome.diagnostic} if commit_outcome.diagnostic is not None else {}),
            **state.requirement_diagnostics,
        }
    )


def _warn_missing_meta(planning_dir: Path, meta: dict[str, object] | None, *, json_output: bool) -> None:
    """Phase: warn (non-blocking) when meta.json is missing/malformed."""
    if meta is not None or json_output:
        return
    if (planning_dir / META_JSON_FILENAME).exists():
        console.print("[yellow]Warning:[/yellow] Failed to read meta.json for event emission (missing or malformed); skipping MissionCreated emission")
    else:
        console.print("[yellow]Warning:[/yellow] meta.json missing; skipping MissionCreated emission")


def _emit_tasks_started(
    mission_slug: str,
    state: _BootstrapState,
    *,
    validate_only: bool,
    repo_root: Path,
    owned: OwnedCheckout | None = None,
    status_surface: StatusSurfaceGuard | None = None,
    planning_dir: Path | None = None,
) -> None:
    """Phase: local canonical TasksStarted (idempotent; skipped in validate-only).

    ``owned`` (item 6): passes ``owned.repository_root`` so the event is written
    against the fact's repository root, never re-derived via ``get_main_repo_root``.

    WP15/T080 (FR-003, finalize bootstrap writer family): writes through
    ``PlacementSeam.write_dir(STATUS_STATE)`` — the SAME single write-location
    authority :func:`_emit_local_canonical_events` uses — rather than
    ``planning_dir`` directly. Without this, ``TasksStarted`` forked into a
    SECOND copy of the lifecycle log on the repository-root checkout even
    after the ``WPCreated``/``TasksCompleted`` leg was fixed.

    WP15 cycle 2 (B3, HIGH, FR-003a): ``write_dir`` is resolved OUTSIDE the
    best-effort ``try`` below (see :func:`_emit_local_canonical_events`'s
    identical cycle-2 fix for the full rationale) -- a named write-location
    refusal must fail finalize closed, never degrade to a silent
    ``logger.debug`` line while the event is written nowhere.

    ``status_surface`` (#5641): this is the run's first status write, so the
    guard is captured here, against the directory just resolved.
    """
    if validate_only:
        return
    from mission_runtime import placement_seam

    status_write_dir = placement_seam(repo_root, mission_slug, owned=owned).write_dir(MissionArtifactKind.STATUS_STATE).path
    if status_surface is not None and planning_dir is not None:
        _capture_status_surface(status_surface, status_write_dir, planning_dir)
    try:
        from specify_cli.status import TASKS_STARTED, emit_artifact_phase

        emit_artifact_phase(
            status_write_dir,
            event_type=TASKS_STARTED,
            mission_slug=mission_slug,
            actor=FINALIZE_TASKS_COMMAND_NAME,
            wp_count=len(state.work_packages),
            repo_root=owned.repository_root if owned else None,
        )
    except Exception as tasks_started_exc:  # noqa: BLE001 — non-blocking emission call (not the write-location resolution above)
        logger.debug("TasksStarted emission skipped: %s", tasks_started_exc)


def _run_commit_pipeline(
    planning_dir: Path,
    tasks_dir: Path,
    repo_root: Path,
    mission_slug: str,
    target_branch: str,
    state: _BootstrapState,
    dep_resolution: _DependencyResolution,
    wp_manifests: dict[str, OwnershipManifest],
    wp_frontmatters: dict[str, WPMetadata],
    wp_bodies: dict[str, str],
    meta: dict[str, object] | None,
    functional_spec_requirement_ids: set[str],
    preexisting_primary_files: set[Path],
    *,
    validate_only: bool,
    json_output: bool,
    target_branch_override: str | None = None,
    target_branch_persist: TargetBranchPersistOutcome | None = None,
    meta_commit_progress: _MetaBranchOverrideProgress | None = None,
    commit_landed: _FinalizeCommitLanded | None = None,
    lane_wp_dependencies: dict[str, list[str]] | None = None,
    all_canceled: bool = False,
    owned: OwnedCheckout | None = None,
    refresh_planning_commit: bool = False,
    allow_orphaned: bool = False,
    planning_sha: PlanningCommitResolution | None = None,
    status_surface: StatusSurfaceGuard | None = None,
) -> None:
    """Phase: the post-validate-only commit pipeline.

    Seeds canonical state, computes lanes, scaffolds acceptance-matrix, syncs the
    dossier, commits artifacts, emits SaaS WPCreated, and reports success. Only
    ever reached when ``not validate_only`` (INV-6).

    A ``--target-branch`` override that just rewrote meta.json
    (:func:`_persist_target_branch_override`) — or one dangling from a prior
    crashed run (SK3466-RR-001) — is folded into the SAME finalize commit as
    tasks.md / WP files below, because :func:`_collect_finalize_artifacts`
    treats meta.json as a commit candidate and :func:`_commit_finalize_
    artifacts` attributes any pending delta by field
    (SK3466-REV-001: a delta confined to ``target_branch`` rides this commit
    regardless of which run produced it; a delta ALSO touching a foreign
    field, e.g. a concurrent ``implement --no-auto-commit`` write, is
    excluded from this commit entirely). Nothing in this phase needs to know
    whether THIS invocation's own persist call fired.

    ``target_branch_override`` / ``target_branch_persist`` are threaded
    through only to ``_emit_success_report`` (SK3466-R-003 JSON traceability)
    and do not affect this phase's own behavior.

    ``meta_commit_progress`` (SK3466-R-001, corrected SK3466-REV2-001): once
    ``_commit_finalize_artifacts`` below returns, flipped to
    ``committed=True`` only when meta.json's own relative path actually
    appears in ``commit_outcome.files_committed`` -- NOT unconditionally.
    ``_meta_json_delta_is_finalize_attributable`` can exclude meta.json from
    this commit entirely (a foreign field, e.g. ``implement
    --no-auto-commit``'s ``vcs``/``vcs_locked_at`` write, is pending
    alongside our ``target_branch`` write); an unconditional flip in that
    case fooled ``_revert_unpersisted_target_branch_override``'s ``not
    meta_commit_progress.committed`` guard into skipping a real revert when a
    LATER step in this function (SaaS emission, the JSON report) goes on to
    raise, leaving a permanently dangling meta.json write. Reading
    ``commit_outcome.files_committed`` -- a value ``_commit_finalize_
    artifacts`` already computes -- needs no new state to close this.

    ``commit_landed`` (review cycle 1, HIGH-1): flipped the moment
    ``_commit_finalize_artifacts`` returns with a real commit, regardless of
    whether meta.json rode it. The FR-015/NFR-001 atomicity guards in
    ``finalize_tasks`` key off this marker, NOT ``meta_commit_progress``.

    ``status_surface`` (#5641): captured by ``_emit_tasks_started`` before the
    run's first status write; its tip is recorded when the status-write window below
    closes (also on an error, so a bootstrap that raises part-way is covered);
    ``finalize_tasks`` restores it when the finalize commit never lands.
    """
    # #5641: every status-surface commit before the final commit -- the per-WP
    # seeds, and on a coordination surface the acceptance-matrix scaffold -- lands
    # inside this window, so the guard records the tip once it closes.
    with status_surface.recording() if status_surface is not None else contextlib.nullcontext():
        _emit_local_canonical_events(planning_dir, mission_slug, repo_root, state.work_packages, json_output=json_output, owned=owned)

        bootstrap_result = _bootstrap_canonical_state_via_mission(
            planning_dir,
            mission_slug,
            dry_run=False,
            capability=GuardCapability.STANDARD,
            **({"owned": owned} if owned else {}),
        )
        if not json_output and bootstrap_result.newly_seeded:
            console.print(f"[green]✓[/green] Bootstrapped canonical status: {bootstrap_result.newly_seeded} WPs seeded")

        lanes_path, lanes_manifest, planning_sha = _compute_and_write_lanes(
            planning_dir,
            repo_root,
            mission_slug,
            wp_manifests,
            lane_wp_dependencies if lane_wp_dependencies is not None else dep_resolution.wp_dependencies,
            wp_frontmatters,
            wp_bodies,
            meta,
            target_branch,
            all_canceled=all_canceled,
            json_output=json_output,
            owned=owned,
            refresh_planning_commit=refresh_planning_commit,
            allow_orphaned=allow_orphaned,
            planning_sha=planning_sha,
        )

        _scaffold_acceptance_matrix_if_lane_based(
            planning_dir,
            repo_root,
            mission_slug,
            lanes_manifest,
            functional_spec_requirement_ids,
            validate_only=validate_only,
            json_output=json_output,
            **({"owned": owned} if owned else {}),
        )

    commit_outcome = _commit_finalize_artifacts(
        planning_dir,
        tasks_dir,
        repo_root,
        mission_slug,
        target_branch,
        lanes_path,
        preexisting_primary_files,
        json_output=json_output,
        updated_count=state.updated_count,
        **({"owned": owned} if owned else {}),
    )
    # SK3466-REV2-001/002: whether meta.json's own delta actually rode this
    # commit -- NOT "the phase returned without raising". Computed once here
    # (the exact same relative-path form _commit_finalize_artifacts used to
    # build ``commit_outcome.files_committed``) and reused below for both the
    # revert-safety marker and the terminal report, so the two call sites
    # this Op's round 3 left behind learn about the same third outcome state
    # from a single source rather than two independent guesses.
    if commit_landed is not None:
        # Independent of meta.json attribution: the atomicity guards must see
        # a landed commit even when meta.json was excluded from it.
        commit_landed.landed = commit_outcome.commit_created
    meta_json_rel = str((planning_dir / META_JSON_FILENAME).relative_to(repo_root))
    meta_committed_this_run = meta_json_rel in commit_outcome.files_committed
    if meta_commit_progress is not None:
        # SK3466-R-001, corrected SK3466-REV2-001: only durable once
        # meta.json's delta actually folded into this commit -- an
        # unconditional flip here fooled the revert guard below
        # (``not meta_commit_progress.committed``) into skipping a real
        # revert when ``_meta_json_delta_is_finalize_attributable`` excluded
        # meta.json for being mixed with a foreign field.
        meta_commit_progress.committed = meta_committed_this_run
    if not json_output and target_branch_persist is not None and target_branch_persist.persisted and not meta_committed_this_run:
        # SK3466-REV2-002: the "persisted to meta.json" note already printed
        # by ``_persist_target_branch_override`` ran before this commit's
        # attribution decision was known, so a mixed-delta exclusion left no
        # console trace distinguishing "committed" from "written but still
        # dangling". This corrective note fires only in that gap.
        console.print(
            "[yellow]Note:[/yellow] the --target-branch override written to meta.json "
            "was excluded from this commit (a foreign meta.json edit is pending "
            "alongside it) and remains an uncommitted working-tree change."
        )

    if json_output:
        _emit_success_report(
            tasks_dir,
            state,
            commit_outcome,
            dep_resolution,
            bootstrap_result,
            lanes_manifest,
            target_branch_override=target_branch_override,
            target_branch_persist=target_branch_persist,
            meta_committed_this_run=meta_committed_this_run,
            planning_sha=planning_sha,
            planning_commit_refresh=_planning_commit_refresh_payload(planning_sha),
        )
    # Non-JSON mode: the refresh decision (including a ``kept_with_warning``
    # console WARN) was already reported inside ``_compute_and_write_lanes``
    # via ``_report_planning_sha_decision`` -- nothing further to print here.

    # WP15/T082 (FR-007 exit-code rule): a refused/error coordination surface
    # exits non-zero even though the top-level legacy status above may have
    # reported "committed" (the PRIMARY group landed). Raised AFTER the
    # success report so a refused surface is reported, never swallowed.
    if commit_outcome.surface_refusal:
        raise typer.Exit(1)


@dataclass
class _FinalizeCommitLanded:
    """Mutable marker: the single final finalize commit has landed (FR-015/NFR-001).

    Deliberately SEPARATE from :attr:`_MetaBranchOverrideProgress.committed`,
    which only says "meta.json's delta rode the commit" (SK3466 attribution).
    When a foreign field (e.g. ``implement --no-auto-commit``'s ``vcs``) is
    pending in meta.json, that file is excluded from the commit, so that flag
    stays ``False`` although the commit DID land. The mission-directory /
    derived-cache / HEAD atomicity guards must key off THIS marker: a later
    failure after a durable commit must never unwind it. Mutated in place from
    ``_run_commit_pipeline`` for the same reason the sibling marker is.
    """

    landed: bool = False


@dataclass
class _MetaBranchOverrideProgress:
    """Mutable revert-safety marker for a persisted ``--target-branch`` write (SK3466-R-001).

    Mutated in place from inside ``_run_commit_pipeline`` (not communicated
    via a return value) so its state survives even when a LATER, unrelated
    phase raises AFTER the meta.json write has already been folded into the
    finalize commit. A return value alone cannot do this: if
    ``_emit_success_report`` raised after
    ``_commit_finalize_artifacts`` had already committed successfully, but
    before ``_run_commit_pipeline`` returned, the caller would never observe
    an "already committed" return and would incorrectly revert meta.json —
    reintroducing a fresh, uncommitted diff on top of an already-green
    commit. Mutating this shared object instead means the caller's
    ``except`` handler still sees ``committed=True`` no matter where past
    that point the exception originated.
    """

    committed: bool = False


def _revert_unpersisted_target_branch_override(
    meta_path: Path | None,
    original_text: str | None,
    *,
    meta_json_persisted: bool,
    meta_commit_progress: _MetaBranchOverrideProgress,
) -> str | None:
    """Undo an applied-but-uncommitted ``--target-branch`` meta.json write (SK3466-R-001).

    ``_persist_target_branch_override`` writes meta.json to disk as soon as
    the override differs from the on-disk value — well before roughly eight
    downstream validation gates (missing ``tasks_dir``, dependency-cycle,
    requirement-mapping, ownership, ...) that can still raise
    ``typer.Exit(1)``. Without this guard, a run that failed one of those
    gates left meta.json mutated and uncommitted in the working tree,
    contradicting the invariant :func:`_collect_finalize_artifacts` exists to
    uphold: a persisted override lands in the SAME commit as tasks.md / the
    WP files, or not at all — never as a dangling, uncommitted edit.

    A no-op unless the write actually happened this run (``meta_json_
    persisted``) AND it was never folded into the finalize commit
    (``not meta_commit_progress.committed``) AND the pre-write content was
    captured.

    Returns:
        ``None`` on success or on a no-op. A non-``None`` string
        (SK3466-RR-003) describes the revert WRITE's OWN failure — e.g. a
        permission change, a full disk, or the same TOCTOU class this
        function's caller already reasons about (meta.json deleted/replaced
        between the persist and this revert attempt). Without this, a
        SECOND, unrelated exception raised from inside ``mission_metadata.
        restore_meta_text``'s own write would propagate out of one of
        ``finalize_tasks``'s ``except`` handlers uncaught — replacing the
        graceful ``{"error": str(e)}``
        JSON-output contract the rest of this fix guarantees with an
        unhandled Python traceback for a ``--json`` caller. Callers report
        the ORIGINAL exception regardless; this is a best-effort ADDITIONAL
        note.
    """
    if not (meta_json_persisted and not meta_commit_progress.committed and original_text is not None and meta_path is not None):
        return None
    from specify_cli.mission_metadata import restore_meta_text

    try:
        # Routed through mission_metadata.py's byte-exact rollback primitive
        # (T025 single-writer gate) rather than a direct ``meta_path.
        # write_text`` here -- this module must not become a second writer of
        # meta.json, the very defect class this fix's history (SK3466-R-001)
        # exists to close. ``restore_meta_text`` guarantees the SAME
        # byte-exact restore this call site always relied on; see its
        # docstring for why ``write_meta`` (re-serialize from a parsed dict)
        # cannot make that guarantee.
        restore_meta_text(meta_path.parent, original_text)
    except OSError as revert_exc:
        logger.warning(
            "SK3466-RR-003: failed to revert unpersisted target_branch override in %s: %s",
            meta_path,
            revert_exc,
        )
        return str(revert_exc)
    return None


def _report_target_branch_revert_failure(revert_error: str | None, *, json_output: bool) -> None:
    """Phase: best-effort surfacing of a failed meta.json revert (SK3466-RR-003).

    A no-op unless the revert write itself failed. Used from ``finalize_
    tasks``'s ``except typer.Exit`` handler, where the ORIGINAL error already
    emitted its own diagnostic before raising — this is purely an additional
    note, never a substitute for it.
    """
    if not revert_error:
        return
    if json_output:
        _emit_json({"warning": "target_branch_override_revert_failed", "detail": revert_error})
    else:
        console.print(f"[yellow]Warning:[/yellow] failed to revert unpersisted --target-branch override in meta.json: {revert_error}")


def _emit_finalize_error_with_revert_note(
    error: Exception,
    revert_error: str | None,
    *,
    json_output: bool,
    status_leftover: StatusSurfaceLeftover | None = None,
) -> None:
    """Phase: emit finalize_tasks's terminal error, folding in a revert-failure note (SK3466-RR-003).

    Preserves the existing ``{"error": str(e)}`` / ``[red]Error:[/red]``
    diagnostic contract for the ORIGINAL exception unconditionally; the
    meta.json-revert failure (if any) is added as a SECOND, clearly-labelled
    field/line rather than replacing it.
    """
    from specify_cli.lanes.compute import LaneDependencyCycleError

    if json_output:
        error_payload: dict[str, object] = {"error": str(error)}
        if isinstance(error, ActionContextError):
            error_payload["error_code"] = error.code
        if isinstance(error, LaneDependencyCycleError):
            error_payload.update(
                {
                    "error_code": error.error_code,
                    "cycle_path": list(error.cycle_path),
                    "cycle_lanes": [
                        {
                            "lane_id": lane.lane_id,
                            "wp_ids": list(lane.wp_ids),
                        }
                        for lane in error.cycle_lanes
                    ],
                }
            )
        if revert_error:
            error_payload["target_branch_override_revert_error"] = revert_error
        if status_leftover is not None:
            # #5641: one envelope on this path, like the meta.json revert note.
            error_payload["status_commits_not_undone"] = status_leftover.as_payload()
        _emit_json(error_payload)
        return
    console.print(f"[red]Error:[/red] {error}")
    if isinstance(error, LaneDependencyCycleError):
        console.print(f"  Cycle path: {' -> '.join(error.cycle_path)}")
        for lane in error.cycle_lanes:
            console.print(f"  {lane.lane_id}: {', '.join(lane.wp_ids)}")
    if revert_error:
        console.print(f"[yellow]Warning:[/yellow] failed to revert unpersisted --target-branch override in meta.json: {revert_error}")
    _report_status_surface_leftover(status_leftover, json_output=False)


def _mission_write_scope_files(mission_dir: Path) -> set[Path]:
    """Every file under ``mission_dir`` this guard tracks, excluding ``meta.json``.

    ``meta.json`` is excluded deliberately: it already has its own
    byte-exact, single-writer-gated revert path
    (:func:`_revert_unpersisted_target_branch_override`, routed through
    ``mission_metadata.restore_meta_text``), and a second writer here would
    contradict that primitive's single-writer guarantee (T025).
    """
    if not mission_dir.exists():
        return set()
    return {path for path in mission_dir.rglob("*") if path.is_file() and path.name != META_JSON_FILENAME}


def _snapshot_mission_write_scope(mission_dir: Path) -> dict[Path, bytes]:
    """Byte-snapshot every tracked file under ``mission_dir`` (FR-015/NFR-001).

    Read by :func:`_restore_mission_write_scope` so a failed
    ``finalize_tasks`` run leaves the mission directory exactly as it found
    it, even though several writes (WP frontmatter, ``tasks.md``, the issue
    matrix, canonical status events) land on disk before every ordered
    fail-closed gate has run (R-07). A not-yet-existing ``mission_dir``
    snapshots as empty rather than raising.
    """
    return {path: path.read_bytes() for path in _mission_write_scope_files(mission_dir)}


def _restore_mission_write_scope(
    before: dict[Path, bytes],
    mission_dir: Path,
    *,
    keep: frozenset[Path] = frozenset(),
    keep_under: Path | None = None,
) -> None:
    """Undo every tracked write under ``mission_dir`` since the matching snapshot (FR-015/NFR-001).

    A file present in ``before`` is rewritten to its original bytes; a file
    that now exists under ``mission_dir`` but was absent from ``before``
    (created by the failed attempt) is deleted. A file in ``keep`` (resolved
    paths a commit left on the status branch changed), or anywhere under
    ``keep_under`` (the status directory, when those paths could not be listed),
    is neither rewritten nor deleted: it is that commit's, not this attempt's.
    Each path is restored independently and a failure is logged, never raised --
    this is best-effort cleanup alongside the ORIGINAL exception that triggered
    it, never a replacement diagnostic for it.
    """
    keep_root = keep_under.resolve() if keep_under is not None else None

    def _is_kept(path: Path) -> bool:
        resolved = path.resolve()
        return resolved in keep or (keep_root is not None and resolved.is_relative_to(keep_root))

    current = _mission_write_scope_files(mission_dir)
    for path, original in before.items():
        if _is_kept(path):
            continue
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(original)
        except OSError as exc:
            logger.warning("finalize atomicity: failed to restore %s: %s", path, exc)
    for path in current - before.keys():
        if _is_kept(path):
            continue
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("finalize atomicity: failed to remove %s: %s", path, exc)


def _restore_mission_write_scope_beside_status(guard: StatusSurfaceGuard, before: dict[Path, bytes], mission_dir: Path) -> None:
    """:func:`_restore_mission_write_scope`, leaving what the status branch kept as it is (#5641).

    The files a kept commit changed stay; when git cannot list them, so does
    everything under the status directory -- fail closed, never the rewrite.
    """
    kept = guard.kept_paths()
    _restore_mission_write_scope(before, mission_dir, keep=kept or frozenset(), keep_under=guard.status_dir if kept is None else None)


def _capture_status_surface(guard: StatusSurfaceGuard, status_dir: Path, planning_dir: Path) -> None:
    """Capture the status surface just before the run's first status write (#5641).

    ``status_dir`` is the directory the writer itself just resolved through
    ``PlacementSeam.write_dir(STATUS_STATE)``, so capturing costs no second
    resolution. Its bytes are snapshotted here only when it lies outside
    ``planning_dir`` (the coordination worktree); otherwise the Mission
    directory snapshot already holds them.
    """
    inside_mission_dir = status_dir.resolve().is_relative_to(planning_dir.resolve())
    guard.capture(status_dir, None if inside_mission_dir else _snapshot_mission_write_scope(status_dir))


def _restore_status_surface(guard: StatusSurfaceGuard) -> StatusSurfaceLeftover | None:
    """Undo the status commits of a run whose finalize commit never landed (FR-015/NFR-001, #5641).

    Runs BEFORE :func:`_restore_mission_write_scope_beside_status`, which then skips the files
    of any commit the guard kept (``guard.kept_paths()``): on a repository-root
    status surface (``lanes`` / ``single_branch``, an owned checkout) the status
    files either go back with the branch or stay exactly as the kept commits
    left them, never modified against their own HEAD. A status directory outside
    the Mission directory (the coordination worktree) gets its bytes back only
    once its branch did, so a refused restore never leaves that worktree
    diverged from its own HEAD. Best-effort like the other restore helpers:
    returns what it could not undo, never raises.
    """
    leftover = guard.restore()
    if guard.status_bytes is not None and guard.status_dir is not None and guard.is_at_tip_before():
        _restore_mission_write_scope(guard.status_bytes, guard.status_dir)
    return leftover


def _report_status_surface_leftover(leftover: StatusSurfaceLeftover | None, *, json_output: bool) -> None:
    """Name the status commits a failed run could not undo (#5641); an additional note, never the error itself."""
    if leftover is None:
        return
    if json_output:
        _emit_json(leftover.as_payload())
        return
    for line in leftover.lines():
        console.print(f"[yellow]Warning:[/yellow] {line}" if not line.startswith(" ") else line)


def _finalize_refusal_envelope(code: str, message: str) -> dict[str, object]:
    """finalize-tasks' own error envelope shape for an owned refusal.

    ``error`` + ``error_code``, plus ``spec_kitty_version`` -- the key every
    other finalize JSON payload carries (``mission._emit_json`` attaches it via
    ``_with_cli_version``), which ``emit_owned_refusal`` bypasses by printing
    directly.
    """
    envelope: dict[str, object] = _with_cli_version({"error": message, "error_code": code})
    return envelope


@dataclass(frozen=True)
class _FinalizeContext:
    """T071 campsite: identity, repo root, owned resolution and mission dirs."""

    invocation_identity: CheckoutIdentity
    repo_root: Path
    owned: OwnedCheckout | None
    mission_slug: str
    primary_dir: Path
    planning_dir: Path


def _resolve_finalize_context(
    mission_handle: str | None,
    owned_checkout: OwnedCheckoutOption,
    target_branch_override: str | None,
    *,
    validate_only: bool,
    json_output: bool,
) -> _FinalizeContext:
    """Phase: resolve identity, repo root, owned checkout and mission dirs (T071)."""
    # #3786: the ONE ambient identity read for this command — resolved here,
    # at the entrypoint boundary, and injected into the write-ownership
    # guard below. Nothing below this point reads ``Path.cwd()`` for
    # identity: ``_enforce_branch_contract_write_ownership`` consumes the
    # injected value object instead of re-reading the ambient checkout.
    invocation_identity = resolve_checkout_identity(Path.cwd(), Intent.WRITE)
    repo_root = _resolve_repo_root(json_output)
    # G2 (WP13): the direct ``resolve_owned_mission`` call is retired in
    # favour of WP08's single shared validation surface
    # (``resolve_owned_or_adopt``), which performs exactly the same
    # explicit-checkout resolution here (``target_override`` forwarded,
    # ``LIFECYCLE_OWNED_TOPOLOGIES`` enforced) while remaining the one CLI
    # caller other owned-capable commands also route through. Called
    # unconditionally -- not gated on ``owned_checkout is not None`` -- so
    # flagless adoption (FR-021) applies here too: running from inside a
    # valid owned checkout P without ``--owned-checkout`` adopts P, while a
    # lane or coordination worktree, or a plain repository-root checkout,
    # keeps today's repository-root behaviour (``adopt_owned_checkout``
    # returns ``None`` for both). Without a ``--mission`` handle,
    # ``adopt_owned_checkout`` returns ``None`` immediately -- a cheap no-op
    # that never touches disk or git, so this call is inert for every
    # ordinary, non-owned finalize invocation. A refused claim renders through
    # ``emit_owned_refusal`` (registry-validated code, ``Error: [<code>]``
    # human line); the JSON envelope keeps finalize's ``error`` +
    # ``error_code`` keys.
    try:
        owned = resolve_owned_or_adopt(
            repo_root,
            owned_checkout,
            mission_handle or "",
            cwd=Path.cwd(),
            allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES,
            target_override=target_branch_override,
        )
    except ActionContextError as refusal:
        emit_owned_refusal(refusal, json_output=json_output, envelope=_finalize_refusal_envelope)
    if owned is not None:
        if not validate_only:
            require_unstaged_index(owned)
        repo_root = owned.owned_root
    mission_slug = owned.mission_slug if owned else _resolve_mission_slug(repo_root, mission_handle, json_output=json_output)

    from mission_runtime import placement_seam

    # WP05/FR-005: _resolve_mission_slug may return a raw operator-supplied
    # handle (the raw_handle fast-path in _resolve_mission_dir_name_primary_anchored
    # at line 258). The seam folds every handle form to the composed primary
    # dir internally (WP08 T036: the caller no longer pre-canonicalizes with
    # _canonicalize_primary_read_handle — redundant with that internal fold).
    # read-side-seam-primary-primitive-closure-01KYKMMT WP06 (T029): routed off
    # the retiring ``primary_feature_dir_for_mission`` wrapper onto the seam
    # directly — WORK_PACKAGE_TASK, since this finalize-tasks flow reads/writes
    # the ``tasks/`` WP files, ``wps.yaml``, and ``tasks.md`` under this dir.
    primary_dir = placement_seam(
        owned.repository_root if owned else repo_root,
        mission_slug,
        owned=owned,
    ).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)
    return _FinalizeContext(
        invocation_identity=invocation_identity,
        repo_root=repo_root,
        owned=owned,
        # The seam folds every handle form to the composed primary dir, so its
        # name is the canonical slug every later phase keys on.
        mission_slug=primary_dir.name,
        primary_dir=primary_dir,
        planning_dir=primary_dir,
    )


def _require_refresh_pin_decision(
    planning_sha: PlanningCommitResolution | None,
    refresh_bootstrap_result: BootstrapResult | None,
    *,
    json_output: bool,
) -> None:
    """Fail closed when the mutating refresh's own read-only preflight didn't run.

    Extracted (#5445 landing fix) to keep ``finalize_tasks``'s own cyclomatic
    complexity under the C901 ceiling; both checks are defensive
    (``refresh_bootstrap_result is None`` is unreachable in the normal flow --
    the non-validate-only refresh preflight above always computes this
    dry-run plan -- fail closed rather than re-planning a second time, mirrors
    ``planning_sha``).
    """
    if planning_sha is None:
        _refuse_planning_pin_refresh("the planning pin decision is missing", json_output=json_output)
    if refresh_bootstrap_result is None:
        _refuse_planning_pin_refresh("the canonical bootstrap plan is missing", json_output=json_output)


def _refresh_bootstrap_dry_run_or_refuse(
    planning_dir: Path,
    mission_slug: str,
    *,
    owned: OwnedCheckout | None,
    json_output: bool,
) -> BootstrapResult:
    """Dry-run the canonical bootstrap for a mutating refresh, refusing a would-write result.

    Extracted (#5445 landing fix) purely to keep ``finalize_tasks``'s own
    cyclomatic complexity under the C901 ceiling -- the caller still makes the
    ``_preflight_refresh_planning_commit`` guard call directly (the
    architecturally-significant one), this helper only wraps the read-only
    dry-run + its refusal, which the guard does not need to inspect.
    """
    bootstrap_result = _bootstrap_canonical_state_via_mission(
        planning_dir,
        mission_slug,
        dry_run=True,
        owned=owned,
    )
    if bootstrap_result.newly_seeded:
        _refuse_planning_pin_refresh(
            "canonical coordination status would need bootstrap writes",
            json_output=json_output,
        )
    return bootstrap_result


@dataclass(frozen=True)
class _FinalizeBranchSetup:
    """T071 campsite: the branch-contract gate plus the pre-write snapshot/persist step."""

    target_branch: str
    merge_target_branch: str
    mission_write_scope_snapshot: dict[Path, bytes]
    mission_write_scope_dir: Path | None
    meta_path_for_revert: Path | None
    meta_original_text: str | None
    target_branch_persist: TargetBranchPersistOutcome
    meta_json_persisted: bool
    owned_derived_dir: Path | None
    owned_derived_snapshot: dict[Path, bytes]


def _run_finalize_branch_setup(
    ctx: _FinalizeContext,
    *,
    target_branch_override: str | None,
    validate_only: bool,
    json_output: bool,
    refresh_planning_commit: bool = False,
) -> _FinalizeBranchSetup:
    """Phase: occurrence-map/target-branch/preflight gates, then the meta.json persist (T071).

    The write-scope snapshot is taken here too, immediately before the
    meta.json persist -- the first write ``finalize_tasks`` can make -- so
    it covers every subsequent write this invocation performs (FR-015/
    NFR-001, T070/T073).
    """
    # Bulk edit occurrence-map gate (FR-001/002/003/004): fail-fast, before
    # the (potentially expensive) requirement-mapping/dependency-graph
    # validators, and before the `if validate_only:` split so it fires in
    # both normal and --validate-only modes (C-005/IC-01).
    _validate_occurrence_map_ready(ctx.planning_dir, json_output=json_output)

    target_branch = _resolve_target_branch(
        ctx.repo_root,
        ctx.primary_dir,
        target_branch_override=target_branch_override,
        json_output=json_output,
    )
    merge_target_branch = _resolve_merge_target_branch(ctx.primary_dir, target_branch)
    _preflight_recovered_pr_bound_contract(
        ctx.repo_root,
        ctx.primary_dir,
        planning_branch=target_branch,
        json_output=json_output,
    )
    # #5445 landing fix: the --refresh-planning-commit preflight (the read-only
    # planning-pin decision + branch-contract/bootstrap guards) is NOT run here
    # any more -- it is called directly from ``finalize_tasks`` itself, right
    # after this phase returns, so the canonical
    # ``_preserve_or_capture_planning_commit_sha`` authority and its
    # ``_preflight_refresh_planning_commit`` guard stay visible as direct calls
    # in the entrypoint's own body (see
    # ``tests/architectural/test_finalize_refresh_pin_authority.py``). Nothing
    # written above this point depends on the refresh decision, and the
    # meta.json snapshot/persist below is unconditionally skipped for a
    # refresh run (``not refresh_planning_commit`` guard), so moving the
    # refresh preflight to run immediately after this function returns is a
    # pure reordering against the read-only checks above (behavior-preserving).
    if not json_output:
        console.print(f"[bold cyan]Branch:[/bold cyan] {target_branch} (target for this mission)")

    mission_write_scope_snapshot: dict[Path, bytes] = {}
    mission_write_scope_dir: Path | None = None
    meta_path_for_revert: Path | None = None
    meta_original_text: str | None = None
    target_branch_persist = TargetBranchPersistOutcome(persisted=False)
    owned_derived_dir: Path | None = None
    owned_derived_snapshot: dict[Path, bytes] = {}
    # A --refresh-planning-commit run writes only lanes.json, through its own
    # compare-and-swap restore (``_restore_planning_pin_candidate``), and never
    # persists meta.json -- so neither the snapshot nor the persist applies.
    if not validate_only and not refresh_planning_commit:
        # Snapshot before ANY write below (INV-6 already guarantees
        # ``--validate-only`` performs none, so this is skipped there).
        mission_write_scope_dir = ctx.planning_dir
        mission_write_scope_snapshot = _snapshot_mission_write_scope(ctx.planning_dir)
        if ctx.owned is not None:
            # FR-015/NFR-001 (T070): the ignored, non-authoritative status
            # derived-cache view (``.kittify/derived/<slug>/``,
            # ``status/views.py``'s ``materialize()`` output) lives OUTSIDE
            # planning_dir -- at the owned checkout's OWN root, not under
            # ``kitty-specs/`` -- so it needs its own snapshot/restore pass;
            # reuses the same generic byte-guard primitives (harmless: no
            # ``meta.json`` ever lives here).
            owned_derived_dir = ctx.owned.owned_root / ".kittify" / "derived" / ctx.mission_slug
            owned_derived_snapshot = _snapshot_mission_write_scope(owned_derived_dir)
        meta_path_for_revert = ctx.primary_dir / META_JSON_FILENAME
        meta_original_text = meta_path_for_revert.read_text(encoding="utf-8") if meta_path_for_revert.exists() else None
        target_branch_persist = _persist_branch_contract_for_finalize(
            ctx.primary_dir,
            planning_branch=target_branch,
            merge_target_branch=merge_target_branch,
            target_branch_override=target_branch_override,
            invocation_identity=ctx.invocation_identity,
            json_output=json_output,
        )
    return _FinalizeBranchSetup(
        target_branch=target_branch,
        merge_target_branch=merge_target_branch,
        mission_write_scope_snapshot=mission_write_scope_snapshot,
        mission_write_scope_dir=mission_write_scope_dir,
        owned_derived_dir=owned_derived_dir,
        owned_derived_snapshot=owned_derived_snapshot,
        meta_path_for_revert=meta_path_for_revert,
        meta_original_text=meta_original_text,
        target_branch_persist=target_branch_persist,
        meta_json_persisted=target_branch_persist.persisted,
    )


@dataclass(frozen=True)
class _FinalizeRequirementGates:
    """T071 campsite: the requirement/dependency-graph validation gates."""

    tasks_dir: Path
    wp_files: list[Path]
    expected_wp_ids: list[str]
    all_spec_requirement_ids: set[str]
    functional_spec_requirement_ids: set[str]
    requirement_extraction_warnings: list[str]
    spec_content: str
    preexisting_primary_files: set[Path]
    wps_manifest: WpsManifest | None
    concern_coverage_warnings: list[str]
    dep_resolution: _DependencyResolution


def _run_finalize_validation_gates(
    ctx: _FinalizeContext,
    target_branch: str,
    *,
    validate_only: bool,
    json_output: bool,
    refresh_planning_commit: bool = False,
) -> _FinalizeRequirementGates:
    """Phase: requirement/dependency-graph validation gates (T071).

    Every gate here can still refuse (missing ``tasks_dir``, a dependency
    cycle, a requirement-mapping gap, a dependency conflict); none of them
    write anything themselves other than the issue-matrix scaffold, which is
    itself INV-6-guarded (skipped under ``--validate-only``).
    """
    planning_dir = ctx.planning_dir
    tasks_dir = planning_dir / "tasks"
    if not tasks_dir.exists():
        error_msg = f"Tasks directory not found: {tasks_dir}"
        if json_output:
            _emit_json({"error": error_msg})
        else:
            console.print(f"[red]Error:[/red] {error_msg}")
        raise typer.Exit(1)
    wp_files = list(tasks_dir.glob("WP*.md"))
    expected_wp_ids = _extract_wp_ids_from_task_files(wp_files)

    (
        all_spec_requirement_ids,
        functional_spec_requirement_ids,
        requirement_extraction_warnings,
        spec_content,
    ) = _read_spec_requirement_ids(planning_dir, json_output=json_output)

    # Snapshot pre-existing primary-side files BEFORE any finalize writer runs
    # (WP02 / FR-006 / A-r1 — residue cleanup scoping, research R6).
    preexisting_primary_files: set[Path] = {p for p in planning_dir.rglob("*") if p.is_file()}

    if not refresh_planning_commit:
        _scaffold_issue_matrix_if_present(
            planning_dir,
            ctx.repo_root,
            ctx.mission_slug,
            target_branch=target_branch,
            validate_only=validate_only,
            json_output=json_output,
            owned=ctx.owned,
        )
    _advisory_issue_matrix_lint(planning_dir, json_output=json_output)

    wps_manifest = _load_manifest(planning_dir, json_output=json_output)
    concern_coverage_warnings = check_concern_refs_coverage(wps_manifest) if wps_manifest is not None else []

    dep_resolution = _resolve_dependencies_and_refs(planning_dir, wps_manifest, wp_files, expected_wp_ids, json_output=json_output)
    _validate_dependency_graph(dep_resolution.wp_dependencies, json_output=json_output)

    wp_files = list(tasks_dir.glob("WP*.md"))
    wp_ids = _extract_wp_ids_from_task_files(wp_files)
    dep_resolution.requirement_diagnostics = _validate_requirement_mapping(
        wp_ids,
        dep_resolution.wp_requirement_refs,
        all_spec_requirement_ids,
        functional_spec_requirement_ids,
        dep_resolution.wp_dependencies,
        spec_content,
        json_output=json_output,
    )

    _detect_dependency_conflicts(wp_files, dep_resolution.wp_dependencies, json_output=json_output)

    if concern_coverage_warnings and not json_output:
        for warning in concern_coverage_warnings:
            console.print(f"[yellow]Warning:[/yellow] {warning}")

    if requirement_extraction_warnings and not json_output:
        for warning in requirement_extraction_warnings:
            console.print(f"[yellow]Warning:[/yellow] {warning}")

    return _FinalizeRequirementGates(
        tasks_dir=tasks_dir,
        wp_files=wp_files,
        expected_wp_ids=expected_wp_ids,
        all_spec_requirement_ids=all_spec_requirement_ids,
        functional_spec_requirement_ids=functional_spec_requirement_ids,
        requirement_extraction_warnings=requirement_extraction_warnings,
        spec_content=spec_content,
        preexisting_primary_files=preexisting_primary_files,
        wps_manifest=wps_manifest,
        concern_coverage_warnings=concern_coverage_warnings,
        dep_resolution=dep_resolution,
    )


@dataclass(frozen=True)
class _FinalizeOwnershipGates:
    """T071 campsite: the bootstrap loop plus the ownership/lane-eligibility gates."""

    state: _BootstrapState
    tasks_md_stale: bool
    wp_frontmatters: dict[str, WPMetadata]
    wp_bodies: dict[str, str]
    wp_manifests: dict[str, OwnershipManifest]
    eligibility: FinalizationEligibility
    lane_wp_manifests: dict[str, OwnershipManifest]
    lane_wp_dependencies: dict[str, list[str]]
    lane_wp_bodies: dict[str, str]


def _run_finalize_ownership_gates(
    ctx: _FinalizeContext,
    gates: _FinalizeRequirementGates,
    target_branch: str,
    merge_target_branch: str,
    *,
    validate_only: bool,
    json_output: bool,
) -> _FinalizeOwnershipGates:
    """Phase: the 8-field bootstrap loop, frontmatter/tasks.md writes, and the ownership gates (T071).

    ``_flush_frontmatter_writes`` and ``_regenerate_or_report_tasks_md`` are
    the first WRITES after :func:`_run_finalize_branch_setup`'s meta.json
    persist -- both INV-6-guarded (skipped under ``--validate-only``) and
    covered by that same function's write-scope snapshot.
    """
    state = _run_bootstrap_loop(
        gates.wp_files,
        gates.dep_resolution,
        gates.wps_manifest,
        ctx.mission_slug,
        ctx.repo_root,
        target_branch,
        gates.concern_coverage_warnings,
        gates.requirement_extraction_warnings,
        merge_target_branch=merge_target_branch,
        validate_only=validate_only,
        json_output=json_output,
    )
    _assert_no_write_in_validate_only(state, validate_only=validate_only)
    _surface_post_integration_acceptance_warnings(state, json_output=json_output)

    _validate_owned_files_not_in_mission_specs(state.inmemory_frontmatter, json_output=json_output)
    _flush_frontmatter_writes(state, validate_only=validate_only)

    # T017: Regenerate tasks.md from wps.yaml manifest (FR-008, FR-011).
    # #3221: the regeneration is a write to a tracked file, so in
    # --validate-only mode it is skipped and staleness is reported
    # instead (INV-6: zero mutation) — never silently repaired.
    tasks_md_stale = _regenerate_or_report_tasks_md(
        ctx.planning_dir,
        gates.wps_manifest,
        ctx.mission_slug,
        validate_only=validate_only,
        json_output=json_output,
    )

    wp_frontmatters, wp_bodies = _gather_validation_frontmatter(gates.wp_files, state)
    ownership_source = FinalizeFrontmatterSource(wp_files=list(gates.wp_files), inmemory=state.inmemory_frontmatter)
    wp_manifests = resolve_wp_manifests(ownership_source)
    _validate_ownership_manifests(wp_manifests, wp_frontmatters, ctx.repo_root, state, json_output=json_output)
    (
        eligibility,
        lane_wp_manifests,
        lane_wp_dependencies,
        lane_wp_bodies,
    ) = _project_lane_inputs(
        wp_manifests,
        gates.dep_resolution.wp_dependencies,
        wp_frontmatters,
        wp_bodies,
    )
    _raise_stale_canceled_dependencies_if_any(eligibility, json_output=json_output)

    return _FinalizeOwnershipGates(
        state=state,
        tasks_md_stale=tasks_md_stale,
        wp_frontmatters=wp_frontmatters,
        wp_bodies=wp_bodies,
        wp_manifests=wp_manifests,
        eligibility=eligibility,
        lane_wp_manifests=lane_wp_manifests,
        lane_wp_dependencies=lane_wp_dependencies,
        lane_wp_bodies=lane_wp_bodies,
    )


def finalize_tasks(
    feature: Annotated[str | None, typer.Option("--mission", help="Mission slug (e.g., '020-my-mission')")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output JSON format")] = False,
    validate_only: Annotated[
        bool, typer.Option("--validate-only", help="Run all validations without committing. Reports issues that would block finalization.")
    ] = False,
    target_branch_override: Annotated[
        str | None,
        typer.Option(
            "--target-branch",
            help=(
                "Override the canonical planning target branch read from meta.json. "
                "Use this for legacy missions created before WP07 persisted "
                "target_branch in meta.json, or to correct a mission whose "
                "target_branch is stale (FR-012 escape hatch). The override is "
                "persisted into the primary meta.json as part of this run, so "
                "every other target_branch consumer converges on it too (#3466)."
            ),
        ),
    ] = None,
    owned_checkout: Annotated[Path | None, owned_checkout_option(help="Explicit owned checkout for a single-branch mission.")] = None,
    refresh_planning_commit: Annotated[
        bool,
        typer.Option(
            "--refresh-planning-commit",
            help=(
                "Force a refresh-ONLY run: re-point the recorded planning_commit_sha in "
                "lanes.json to the current target-branch tip and exit, without running the "
                "rest of finalize-tasks (#4141). By default (no flag needed) a normal "
                "re-finalize already advances the pin automatically whenever a PRIMARY "
                "planning file genuinely changed since it was recorded (FR-012); use this "
                "flag only to force JUST the pin refresh for an ADVANCED pin (the common "
                "case) or to re-point a deliberate mid-mission rebase with --allow-orphaned "
                "(#4827). It is advance-only and REFUSES when the recorded SHA is not an "
                "ancestor of the tip without --allow-orphaned, and it CANNOT help a pin the "
                "automatic path already warned about and kept unchanged (a FOREIGN object "
                "absent from this repository entirely, or an INDETERMINATE pin whose target "
                "tip could not even be resolved) -- WP15 cycle 2/3: neither shape is "
                "inspectable, so --refresh-planning-commit --allow-orphaned refuses both the "
                "same as a bare --refresh-planning-commit would; correct lanes.json's "
                "planning_commit_sha by hand instead, per that warning's own text."
            ),
        ),
    ] = False,
    allow_orphaned: Annotated[
        bool,
        typer.Option(
            "--allow-orphaned",
            help=(
                "Only meaningful with --refresh-planning-commit (#4827). Permits the "
                "re-pin to re-point a recorded planning_commit_sha that is ORPHANED -- "
                "present in the repository but no longer an ancestor of the target-branch "
                "tip, the mid-mission-rebase shape. Without it, an orphaned pin is refused "
                "(a bare --refresh-planning-commit stays advance-only; a plain finalize "
                "fails closed before writing lanes.json). Still refused regardless for a "
                "FOREIGN (absent) object -- investigate that divergence manually."
            ),
        ),
    ] = False,
) -> None:
    """Parse dependencies from tasks.md and update WP frontmatter, then commit to target branch.

    This command is designed to be called after LLM generates WP files via /spec-kitty.tasks.
    It post-processes the generated files to add dependency information and commits everything.

    Use --validate-only to check for issues (missing requirement mappings, ownership overlaps,
    dependency cycles) without making any changes or committing.

    Use --refresh-planning-commit once execution has begun and a legitimate planning
    amendment has landed on the target branch: it advances the recorded
    planning_commit_sha in lanes.json to the current tip so lanes merge the amended
    planning state instead of a stale snapshot (#4141). It is refused when the recorded
    SHA is not an ancestor of the tip (a history rewrite, not an amendment) -- unless
    that non-ancestor SHA is a proven ORPHAN (present, just unreachable -- a mid-mission
    rebase), in which case add --allow-orphaned to re-point to the live tip (#4827).

    Bootstrap Mutation Surface (FR-003 / SC-002)
    =============================================
    The 8 frontmatter fields below may be written or overwritten by this command.
    When ``--validate-only`` is active, ALL writes are skipped — the
    ``frontmatter_changed and not validate_only`` guard ensures zero bytes of
    mutation on disk (INV-6). In validate-only mode the bootstrap loop still
    infers all 8 fields in memory so downstream validation operates against the
    post-bootstrap state — not the stale on-disk frontmatter. The T017 tasks.md
    regeneration is likewise skipped (its staleness relative to wps.yaml is
    reported instead of repaired — #3221), so INV-6 covers every tracked-file
    write the command performs.

    See also: ``tasks.py:finalize-tasks()`` which writes ``dependencies`` via
    ``build_document() + write_text()`` — guarded the same way (T002).

    Examples:
        spec-kitty agent mission finalize-tasks --mission 020-my-feature --json
        spec-kitty agent mission finalize-tasks --mission 020-my-feature --validate-only --json
        spec-kitty agent mission finalize-tasks --mission 020-my-feature --refresh-planning-commit
        spec-kitty agent mission finalize-tasks --mission 020-my-feature --refresh-planning-commit --allow-orphaned
    """
    # SK3466-R-001: tracked across the whole try body (not just the persist
    # call site) so the except blocks below can undo an already-applied
    # meta.json write if any later validation gate bails with typer.Exit
    # before the finalize commit actually lands it. Declared before ``try``
    # so a failure BEFORE the persist call (nothing written yet) still leaves
    # these names bound.
    meta_json_persisted = False
    meta_commit_progress = _MetaBranchOverrideProgress()
    commit_landed = _FinalizeCommitLanded()
    meta_path_for_revert: Path | None = None
    meta_original_text: str | None = None
    # FR-015/NFR-001: the write-then-restore atomicity guard (T070/T073;
    # operator decision on T072/T073, follow-up: #5343 -- a true plan/apply
    # split is NOT implemented). What a refused run is guaranteed to leave
    # behind, exactly:
    #   * COVERED: the mission directory (bytes restored, new files removed;
    #     meta.json via the SK3466 single-writer revert); for EVERY topology,
    #     the status surface the transactional status emitter commits to
    #     (#5641: the coordination branch and worktree for ``coord`` /
    #     ``lanes_with_coord``, the current branch for ``lanes`` /
    #     ``single_branch``, P's branch for an owned run) -- branch tip
    #     restored by compare-and-swap, index by ``read-tree``, status files by
    #     bytes, see ``finalize_status_surface.StatusSurfaceGuard``; and, owned
    #     runs only, P's ``.kittify/derived/<slug>``.
    #   * NOT UNDONE, REPORTED: status commits on a branch that gained a
    #     commit the run did not make -- after its last status write (a
    #     foreign commit on top), or inside the status-write window (every
    #     commit in ``tip_before..tip_after`` must be a non-merge commit
    #     touching only this Mission's status files and the acceptance-matrix
    #     scaffold, else the range is not provably the run's own). The branch
    #     is never forced, the files those commits changed are left as they
    #     left them, and the run names the commits it left. The window holds
    #     the Mission's status lock, so another process's status write waits
    #     for it; residual: a committer that takes no status lock, or one that
    #     lands between the capture and the window opening, is
    #     indistinguishable from the run's own. On a ``lanes`` /
    #     ``single_branch`` surface the finalize commit itself shares that
    #     branch, so a failure after it lands but before ``commit_landed`` is
    #     set reads as "moved" too (same safe outcome).
    #   * NOT COVERED (tracked in #5343): a status surface the guard cannot
    #     capture at the run's first status write -- a coordination worktree
    #     the run itself materializes, a detached HEAD -- whose status commits
    #     are then neither undone nor reported (logged only); and the
    #     non-owned ``R/.kittify/derived/<slug>`` view (untracked).
    #   * Like any restore-on-failure guard it does not survive a hard process
    #     kill mid-run (nor would a literal plan/apply without git-object
    #     staging); it also never runs once ``commit_landed`` is set.
    # Populated just before the first write below and restored from every
    # terminal ``except`` handler, in addition to (not instead of) the
    # pre-existing meta.json-only SK3466 guard above.
    mission_write_scope_snapshot: dict[Path, bytes] = {}
    mission_write_scope_dir: Path | None = None
    # FR-015/NFR-001 (#5641): captured by ``_emit_tasks_started`` just before
    # the run's first status write; restored from the except handlers below.
    status_surface = StatusSurfaceGuard()
    status_leftover: StatusSurfaceLeftover | None = None
    owned_derived_dir: Path | None = None
    owned_derived_snapshot: dict[Path, bytes] = {}
    # FR-007 (WP13 T074): bound before ``try`` so the except handlers below
    # can thread it into the refusal envelope's ``stale_repository_root_copy``
    # even when the exception fires before ``_resolve_finalize_context``
    # itself returns (nothing resolved yet -- stays ``None``, so the refusal
    # envelope omits the key exactly as a non-owned run's does).
    owned: OwnedCheckout | None = None
    envelope_token = _OWNED_ENVELOPE_EXTRAS.set(None)
    try:
        ctx = _resolve_finalize_context(
            feature,
            owned_checkout,
            target_branch_override,
            validate_only=validate_only,
            json_output=json_output,
        )
        owned = ctx.owned
        if owned is not None:
            _OWNED_ENVELOPE_EXTRAS.set(stale_copy_payload(owned))
        repo_root = ctx.repo_root
        mission_slug = ctx.mission_slug
        planning_dir = ctx.planning_dir

        branch_setup = _run_finalize_branch_setup(
            ctx,
            target_branch_override=target_branch_override,
            validate_only=validate_only,
            json_output=json_output,
            refresh_planning_commit=refresh_planning_commit,
        )
        target_branch = branch_setup.target_branch
        merge_target_branch = branch_setup.merge_target_branch
        mission_write_scope_snapshot = branch_setup.mission_write_scope_snapshot
        mission_write_scope_dir = branch_setup.mission_write_scope_dir
        owned_derived_dir = branch_setup.owned_derived_dir
        owned_derived_snapshot = branch_setup.owned_derived_snapshot
        meta_path_for_revert = branch_setup.meta_path_for_revert
        meta_original_text = branch_setup.meta_original_text
        target_branch_persist = branch_setup.target_branch_persist
        meta_json_persisted = branch_setup.meta_json_persisted

        # #5445 landing fix: the single canonical planning-pin authority
        # (``_preserve_or_capture_planning_commit_sha``) and its read-only
        # branch-contract/bootstrap guard (``_preflight_refresh_planning_commit``)
        # are called directly here -- not nested inside a helper -- so both
        # stay visible as one-shot calls in this entrypoint's own body
        # (tests/architectural/test_finalize_refresh_pin_authority.py). Runs
        # before every finalize writer/event-emitter below.
        planning_sha: PlanningCommitResolution | None = None
        refresh_bootstrap_result: BootstrapResult | None = None
        refresh_status_findings: list[str] = []
        if refresh_planning_commit:
            planning_sha = _preserve_or_capture_planning_commit_sha(
                planning_dir,
                repo_root,
                mission_slug,
                target_branch,
                json_output=json_output,
                owned=owned,
                refresh_planning_commit=True,
                allow_orphaned=allow_orphaned,
            )
            if not validate_only:
                _preflight_refresh_planning_commit(
                    repo_root,
                    planning_dir,
                    mission_slug,
                    target_branch,
                    target_branch_override=target_branch_override,
                    owned=owned,
                    json_output=json_output,
                )
                refresh_bootstrap_result = _refresh_bootstrap_dry_run_or_refuse(
                    planning_dir,
                    mission_slug,
                    owned=owned,
                    json_output=json_output,
                )
            else:
                refresh_status_findings = _refresh_worktree_status_findings(
                    owned.repository_root if owned else repo_root,
                    owned.owned_root if owned else repo_root,
                    mission_slug,
                )

        req_gates = _run_finalize_validation_gates(
            ctx,
            target_branch,
            validate_only=validate_only,
            json_output=json_output,
            refresh_planning_commit=refresh_planning_commit,
        )
        tasks_dir = req_gates.tasks_dir
        functional_spec_requirement_ids = req_gates.functional_spec_requirement_ids
        preexisting_primary_files = req_gates.preexisting_primary_files

        # #5100 / planning-refresh: a --refresh-planning-commit run is a
        # primary-only lanes.json pin write, so every frontmatter/tasks.md
        # writer below runs in its INV-6 zero-mutation mode.
        own_gates = _run_finalize_ownership_gates(
            ctx,
            req_gates,
            target_branch,
            merge_target_branch,
            validate_only=validate_only or refresh_planning_commit,
            json_output=json_output,
        )
        state = own_gates.state
        wp_frontmatters = own_gates.wp_frontmatters
        eligibility = own_gates.eligibility
        lane_wp_manifests = own_gates.lane_wp_manifests
        lane_wp_dependencies = own_gates.lane_wp_dependencies
        lane_wp_bodies = own_gates.lane_wp_bodies

        meta = _read_meta_for_emission(planning_dir)
        _warn_missing_meta(planning_dir, meta, json_output=json_output)
        if not refresh_planning_commit:
            _emit_tasks_started(
                mission_slug,
                state,
                validate_only=validate_only,
                repo_root=repo_root,
                owned=owned,
                status_surface=status_surface,
                planning_dir=planning_dir,
            )

        if validate_only:
            _emit_validate_only_report(
                planning_dir,
                mission_slug,
                meta,
                state,
                lane_wp_manifests,
                lane_wp_dependencies,
                lane_wp_bodies,
                target_branch,
                all_canceled=eligibility.all_canceled,
                tasks_md_stale=own_gates.tasks_md_stale,
                json_output=json_output,
                **({"owned": owned} if owned else {}),
                planning_sha=planning_sha,
                refresh_status_findings=refresh_status_findings,
            )
            return

        if refresh_planning_commit:
            _require_refresh_pin_decision(planning_sha, refresh_bootstrap_result, json_output=json_output)
            # _require_refresh_pin_decision raises (NoReturn) on either None --
            # mypy cannot see that across the function boundary, so narrow
            # explicitly for the calls below (behavior unchanged).
            assert planning_sha is not None
            assert refresh_bootstrap_result is not None
            _commit_planning_pin_refresh(
                planning_dir,
                repo_root,
                mission_slug,
                target_branch,
                planning_sha,
                state,
                req_gates.dep_resolution,
                refresh_bootstrap_result,
                tasks_md_stale=own_gates.tasks_md_stale,
                json_output=json_output,
                owned=owned,
            )
            return

        if meta_json_persisted:
            meta = _read_meta_for_emission(planning_dir)

        _run_commit_pipeline(
            planning_dir,
            tasks_dir,
            repo_root,
            mission_slug,
            target_branch,
            state,
            req_gates.dep_resolution,
            lane_wp_manifests,
            wp_frontmatters,
            lane_wp_bodies,
            meta,
            functional_spec_requirement_ids,
            preexisting_primary_files,
            lane_wp_dependencies=lane_wp_dependencies,
            all_canceled=eligibility.all_canceled,
            validate_only=validate_only,
            json_output=json_output,
            target_branch_override=target_branch_override,
            target_branch_persist=target_branch_persist,
            meta_commit_progress=meta_commit_progress,
            commit_landed=commit_landed,
            refresh_planning_commit=refresh_planning_commit,
            allow_orphaned=allow_orphaned,
            planning_sha=planning_sha,
            status_surface=status_surface,
            **({"owned": owned} if owned else {}),
        )

    except typer.Exit:
        revert_error = _revert_unpersisted_target_branch_override(
            meta_path_for_revert,
            meta_original_text,
            meta_json_persisted=meta_json_persisted,
            meta_commit_progress=meta_commit_progress,
        )
        # FR-015/NFR-001: only undo the mission-directory writes when the
        # finalize commit never landed. ``commit_landed`` (set inside
        # ``_run_commit_pipeline`` the instant the commit succeeds) is the
        # guards' OWN marker; ``meta_commit_progress.committed`` only means
        # "meta.json rode the commit" and stays False when a foreign meta.json
        # field excludes it. A LATER, unrelated failure after a real commit
        # must never unwind an already-durable finalize.
        if mission_write_scope_dir is not None and not commit_landed.landed:
            status_leftover = _restore_status_surface(status_surface)
            _restore_mission_write_scope_beside_status(status_surface, mission_write_scope_snapshot, mission_write_scope_dir)
            if owned_derived_dir is not None:
                _restore_mission_write_scope(owned_derived_snapshot, owned_derived_dir)
        # SK3466-RR-003: the ORIGINAL error already emitted its own
        # diagnostic before raising typer.Exit above; this is a best-effort,
        # ADDITIONAL note if the meta.json revert itself also failed.
        _report_target_branch_revert_failure(revert_error, json_output=json_output)
        _report_status_surface_leftover(status_leftover, json_output=json_output)
        raise
    except Exception as e:
        revert_error = _revert_unpersisted_target_branch_override(
            meta_path_for_revert,
            meta_original_text,
            meta_json_persisted=meta_json_persisted,
            meta_commit_progress=meta_commit_progress,
        )
        if mission_write_scope_dir is not None and not commit_landed.landed:
            status_leftover = _restore_status_surface(status_surface)
            _restore_mission_write_scope_beside_status(status_surface, mission_write_scope_snapshot, mission_write_scope_dir)
            if owned_derived_dir is not None:
                _restore_mission_write_scope(owned_derived_snapshot, owned_derived_dir)
        _emit_finalize_error_with_revert_note(e, revert_error, json_output=json_output, status_leftover=status_leftover)
        raise typer.Exit(1) from None
    finally:
        _OWNED_ENVELOPE_EXTRAS.reset(envelope_token)
