"""setup-plan command family for ``agent mission`` (#2056 WP06).

Hosts the ``setup-plan`` command, decomposed from its pre-decomposition 507-LOC
monolith into ≤15-CC phase helpers (SaaS/auth preflight → git preflight →
feature-dir resolution → spec gate → plan scaffold → lifecycle emit → plan
commit → documentation wiring → result emit), plus the planning-commit helpers
it owns: ``_commit_to_branch`` + ``CommitToBranchResult``, ``_kind_for_artifact``
(and its ``_ARTIFACT_TYPE_TO_KIND`` table),
``_print_artifact_unchanged``, ``_warn_commit_failed``. The heavyweight
``commit_for_mission`` import stays function-local (A-3 / NFR-005).

The command is defined here as a plain callable; ``mission`` registers it on its
Typer ``app`` and re-exports ``setup_plan`` / ``_commit_to_branch`` /
``CommitToBranchResult`` / ``_kind_for_artifact`` (imported by tests and by
``lifecycle.py``). The relocated body resolves test-patched cross-cutting symbols
(``locate_project_root`` / ``_enforce_git_preflight`` / ``_find_feature_directory``
/ ``_show_branch_context`` / ``get_current_branch`` / ``resolve_configured_template`` /
``_commit_to_branch``) through the ``mission`` module at call time so the
historical ``mission.<name>`` patch seams keep working without an import cycle.

One-way leaf (INV-8): imports lower layers + sibling Seam B/C/D leaves only at
module scope; the ``mission`` lookup inside the command is a deferred call-time
import. Behavior is preserved byte-for-byte from the pre-decomposition
``mission.py``; the WP01 golden harness is the regression net.
"""

from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass
import logging
from pathlib import Path
import shutil
from collections.abc import Mapping, Sequence
from typing import Annotated, Final, Literal, cast

from specify_cli.cli.commands._commit_recipes import safe_commit_recipe
from specify_cli.cli.console import console
import typer

from charter.activation.mission_type_profiles import resolve_mission_type_context
from charter.resolution import ResolutionResult
from mission_runtime import MissionArtifactKind, OwnedCheckout, WriteLocation, placement_seam
from specify_cli.cli.commands._owned_checkout import OwnedCheckoutOption
from specify_cli.coordination.commit_outcome import STATUS_COMMITTED, STATUS_UNCHANGED, SurfaceOutcome, commit_outcome_payload, render_commit_outcome
from specify_cli.coordination.commit_router import CommitRouterResult
from specify_cli.core.checkout_identity import Intent, resolve_checkout_identity
from specify_cli.core.constants import MISSION_TYPE_DOCUMENTATION
from specify_cli.doc_analysis.doc_state import GeneratorConfig
from specify_cli.mission import _canonical_meta_mission_type, get_mission_type
from specify_cli.core.paths import load_meta_fail_closed, read_target_branch_from_meta
from specify_cli.runtime.resolver import TemplateConfigurationError

from specify_cli.cli.commands.agent.mission_branch_context import (
    _inject_branch_contract,
    resolve_planning_checkout_verdict,
)
from specify_cli.cli.commands.agent.mission_feature_resolution import (
    _ARTIFACT_TYPE_TO_KIND as _ARTIFACT_TYPE_TO_KIND,
    _build_setup_plan_detection_error,
    _kind_for_artifact as _kind_for_artifact,
    _sole_mission_slug_or_none,
)


def _emit_json(payload: dict[str, object]) -> None:
    """Emit ``payload`` as JSON via the ``mission`` module's ``_emit_json``.

    Routing every setup-plan JSON emission through the ``mission`` module (rather
    than importing ``_emit_json`` directly) preserves the historical
    ``mission._emit_json`` patch seam exercised by callers that invoke
    ``mission.setup_plan`` directly (e.g. ``test_mission_planning_entry``).
    """
    from specify_cli.cli.commands.agent import mission as _mission

    _mission._emit_json(payload)


logger = logging.getLogger(__name__)

SETUP_PLAN_COMMAND_NAME = "spec-kitty agent mission setup-plan"
PROJECT_ROOT_NOT_FOUND = "Could not locate project root"
PROJECT_ROOT_NOT_FOUND_MESSAGE = f"{PROJECT_ROOT_NOT_FOUND}. Run from within spec-kitty repository."
#: FR-013: setup-plan refuses a spec.md that declares a malformed
#: kind-prefixed requirement ID in a declared position (WP05), or declares
#: the same ID twice (#5674).
SPEC_REQUIREMENT_IDS_INVALID = "SPEC_REQUIREMENT_IDS_INVALID"
SPEC_REQUIREMENT_IDS_INVALID_MESSAGE = "spec.md declares requirement IDs that are malformed or declared more than once"


# ---------------------------------------------------------------------------
# Planning-commit helpers (relocated from mission.py — WP06 / T023)
# ---------------------------------------------------------------------------


def _print_artifact_unchanged(artifact_type: str, json_output: bool) -> None:
    if not json_output:
        console.print(f"[dim]{artifact_type.capitalize()} unchanged, no commit needed[/dim]")


def _warn_on_incomplete_surfaces(result: CommitRouterResult, *, json_output: bool) -> None:
    """Print a line for every surface research D8 says is actionable.

    WP14 (contracts/commit-outcome.md rule 6): a best-effort commit whose
    result was previously discarded (the gap-analysis and generator-config
    sites below) renders through the shared :func:`render_commit_outcome`
    when, and only when, some surface is neither ``committed`` nor
    ``unchanged`` -- an all-success batch prints nothing (the common case).
    """
    if json_output:
        return
    if not any(outcome.status not in (STATUS_COMMITTED, STATUS_UNCHANGED) for outcome in result.surfaces):
        return
    for line in render_commit_outcome(result):
        # WP14 review correction (round 2 / WP13 precedent): a branch name,
        # path or diagnostic can carry literal `[...]` -- render as plain
        # text, never Rich markup.
        console.print(line, markup=False)


def _warn_commit_failed(
    artifact_type: str,
    file_path: Path,
    exc: BaseException,
    json_output: bool,
    *,
    commit_message: str,
    to_branch: str,
) -> None:
    if not json_output:
        console.print(f"[yellow]Warning:[/yellow] Failed to commit {artifact_type}: {exc}")
        recipe = safe_commit_recipe([str(file_path)], commit_message, to_branch)
        console.print(f"[yellow]You may need to commit manually:[/yellow] {recipe}")


@dataclass(frozen=True)
class CommitToBranchResult:
    """Typed outcome of :func:`_commit_to_branch` (FR-006 / D-5).

    Replaces the old ``-> None`` contract so the planning caller can surface the
    real commit hash on success and a typed diagnostic for a no-op against the
    wrong surface, instead of an opaque silent ``commit_created: None``.

    ``status`` is one of:

    * ``"committed"`` — ``safe_commit`` landed a real commit; ``commit_hash`` is
      the resolved SHA.
    * ``"unchanged"`` — genuine benign no-op: the artifact IS present at the
      resolved placement and already committed there (nothing to commit).
    * ``"no_op_wrong_surface"`` — the artifact is NOT present at the resolved
      placement (the commit would no-op against the wrong worktree/surface);
      ``diagnostic`` names the missing artifact + placement.

    ``surfaces`` (WP14, ``contracts/commit-outcome.md``): the router's own
    per-surface outcome, carried through additively so the setup-plan JSON
    envelope can render EVERY partition group this commit touched, not just
    the caller-surface projection the four fields above alone describe.
    """

    status: Literal["committed", "unchanged", "no_op_wrong_surface"]
    placement_ref: str
    commit_hash: str | None = None
    diagnostic: str | None = None
    surfaces: tuple[SurfaceOutcome, ...] = ()


@dataclass(frozen=True, slots=True)
class SetupPlanLocalOutcome:
    """Authoritative setup-plan payload and its pre-existing process exit."""

    payload: Mapping[str, object]
    exit_code: int
    render_kind: Literal["success", "scaffold", "blocked", "error"]


# write-surface-coherence WP02 (T007): the ``artifact_type`` → canonical
# :class:`~mission_runtime.MissionArtifactKind` map and its ``_kind_for_artifact``
# lookup were RELOCATED to ``mission_feature_resolution`` (the INV-8 one-way leaf)
# by #2113 / gate-read-surface-completion so the shared ``_planning_read_dir``
# chokepoint can name its kind without an import cycle. They are re-exported above
# (``_ARTIFACT_TYPE_TO_KIND`` / ``_kind_for_artifact``) to keep this module's public
# surface — consumed by ``_commit_to_branch`` below, ``lifecycle.py``, the
# ``mission`` shim, and the unit tests — unchanged.


def _commit_to_branch(
    file_path: Path,
    mission_slug: str,
    artifact_type: str,
    repo_root: Path,
    _target_branch: str,
    json_output: bool = False,
    *,
    owned: OwnedCheckout | None = None,
    extra_files: tuple[Path, ...] = (),
) -> CommitToBranchResult:
    """Commit a planning artifact to its single resolved placement.

    WP02 / T027 / IC-02 (#2056): now delegates to
    :func:`~specify_cli.coordination.commit_router.commit_for_mission`
    — the canonical single entry point for all planning-phase commits.
    This eliminates the final direct safe-commit call in this module and
    closes the C-001 "no duplicate" requirement.

    WP05 / FR-003 / C-GUARD-3a (#1784 catch-22 fix): the commit destination is
    the resolved placement :class:`CommitTarget` (``resolve_placement_only``
    → the SAME authority the full resolver computes), NOT ``git HEAD`` /
    ``current_branch``.

    WP03 / FR-006 / D-5: returns a typed :class:`CommitToBranchResult` so the
    caller surfaces the real commit hash on success and a typed diagnostic for a
    no-op-against-the-wrong-surface (artifact absent at the resolved placement).

    Args:
        file_path: Path to file being committed
        mission_slug: Feature slug (e.g., "001-my-feature")
        artifact_type: Type of artifact ("spec", "plan", "tasks")
        repo_root: Repository root path (ensures commits go to planning repo, not worktree)
        _target_branch: Branch the mission targets; passed to commit_for_mission
            for the post-commit ff-advance (WP09 / FR-010 / #1878).
        json_output: If True, suppress Rich console output
        owned: Validated ownership fact (owned-checkout-lifecycle-authority
            WP09). When set, protection and the router's own ``repo_root``
            resolve from ``owned.repository_root`` (R) regardless of the
            ``repo_root`` argument's own value -- "the linked checkout
            cannot weaken protection" -- while the actual write lands on
            ``owned.owned_root`` (P) via ``commit_for_mission``'s ``owned=``.
        extra_files: Files the same command wrote beside ``file_path`` that
            belong in the same commit (#3933: the lifecycle events setup-plan
            appends), so one phase transition is one commit.

    Returns:
        CommitToBranchResult: the typed commit outcome (see the class docstring).
    """
    from specify_cli.core.git_ops import get_current_branch

    if get_current_branch(repo_root) is None:
        raise RuntimeError("Not in a git repository")

    from specify_cli.coordination.commit_router import commit_for_mission
    from specify_cli.git.protection_policy import ProtectionPolicy

    commit_msg = f"Add {artifact_type} for mission {mission_slug}"
    protection_root = owned.repository_root if owned is not None else repo_root
    policy = ProtectionPolicy.resolve(protection_root)
    router_result = commit_for_mission(
        repo_root=protection_root,
        mission_slug=mission_slug,
        files=(file_path, *extra_files),
        message=commit_msg,
        policy=policy,
        kind=_kind_for_artifact(artifact_type),
        target_branch=_target_branch,
        owned=owned,
    )

    # WP14 review correction (round 2, binding -- the WP13 precedent this
    # mission's spec_commit_cmd.py consumer was rejected over): render EVERY
    # surface through the shared render_commit_outcome on every outcome arm
    # (committed, unchanged, no_op_wrong_surface, error) when the router
    # populated any, so a split batch's non-caller surface is never hidden
    # behind this arm's own caller-surface-only message. Additive, ahead of
    # each arm's existing (and still-firing) actionable line/behaviour.
    if not json_output and router_result.surfaces:
        for line in render_commit_outcome(router_result):
            console.print(line, markup=False)

    if router_result.status == "committed":
        if not json_output:
            console.print(f"[green]✓[/green] {artifact_type.capitalize()} committed to {router_result.placement_ref}")
            if router_result.commit_hash:
                console.print(f"[dim]Commit: {router_result.commit_hash[:7]}[/dim]")
        return CommitToBranchResult(
            status="committed",
            placement_ref=router_result.placement_ref,
            commit_hash=router_result.commit_hash,
            surfaces=router_result.surfaces,
        )
    elif router_result.status == "unchanged":
        _print_artifact_unchanged(artifact_type, json_output)
        return CommitToBranchResult(status="unchanged", placement_ref=router_result.placement_ref, surfaces=router_result.surfaces)
    elif router_result.status == "no_op_wrong_surface":
        if not json_output:
            console.print(f"[yellow]Warning:[/yellow] {router_result.diagnostic}")
        return CommitToBranchResult(
            status="no_op_wrong_surface",
            placement_ref=router_result.placement_ref,
            diagnostic=router_result.diagnostic,
            surfaces=router_result.surfaces,
        )
    else:
        # "error" status — surface via warn helper and re-raise as RuntimeError
        # so callers that catch RuntimeError still get the failure.
        _warn_commit_failed(
            artifact_type,
            file_path,
            RuntimeError(router_result.diagnostic or "commit failed"),
            json_output,
            commit_message=commit_msg,
            to_branch=_target_branch,
        )
        raise RuntimeError(router_result.diagnostic or f"commit_for_mission failed for {artifact_type}")


# ---------------------------------------------------------------------------
# setup-plan phase helpers (WP06 / T022)
# ---------------------------------------------------------------------------


def _resolve_setup_plan_feature_dir(repo_root: Path, feature: str | None, *, json_output: bool) -> Path:
    """Resolve the feature directory for setup-plan; exit 1 with a detection payload on failure.

    FR-004 / #4: when no ``--mission`` was given and exactly one substantive
    mission is resolvable, auto-select it before the shared
    ``_find_feature_directory`` call (which otherwise hard-requires an explicit
    handle). Zero or >1 missions → structured detection error (no silent fallback).
    """
    from specify_cli.cli.commands.agent import mission as _mission

    cwd = Path.cwd().resolve()
    resolved_feature = feature
    if resolved_feature is None:
        resolved_feature = _sole_mission_slug_or_none(repo_root)
    try:
        from mission_runtime import ActionContextError

        feature_dir: Path = _mission._find_feature_directory(
            repo_root,
            cwd,
            explicit_feature=resolved_feature,
        )
        return feature_dir
    except (ValueError, ActionContextError) as detection_error:
        payload = _build_setup_plan_detection_error(repo_root, str(detection_error), feature)
        if json_output:
            _emit_json(payload)
        else:
            console.print(f"[red]Error:[/red] {payload['error']}")
            for slug in cast(list[str], payload.get("available_missions", []))[:10]:
                console.print(f"  - {slug}")
            if "example_command" in payload:
                console.print(f"  {payload['example_command']}")
        raise typer.Exit(1) from None


def _enforce_spec_gate(
    spec_file: Path,
    feature_dir: Path,
    mission_slug: str,
    repo_root: Path,
    *,
    target_branch: str,
    current_branch: str,
    expected_checkout_branch: str | None = None,
    json_output: bool,
) -> bool:
    """Issue #846 entry gate: spec must exist + be committed + substantive.

    Returns ``True`` when the gate blocks (the caller must return early); emits
    the blocked payload as a side effect. Returns ``False`` when the spec passes.
    Raises ``typer.Exit(1)`` when the spec file is entirely missing.
    """
    outcome, human_message = _evaluate_spec_gate(
        spec_file,
        feature_dir,
        mission_slug,
        repo_root,
        target_branch=target_branch,
        current_branch=current_branch,
        expected_checkout_branch=expected_checkout_branch,
    )
    if outcome is None:
        return False
    if json_output:
        _emit_json(dict(outcome.payload))
    elif human_message is not None:
        console.print(human_message)
    if outcome.exit_code:
        raise typer.Exit(outcome.exit_code)
    return True


def _evaluate_spec_gate(
    spec_file: Path,
    feature_dir: Path,
    mission_slug: str,
    repo_root: Path,
    *,
    target_branch: str,
    current_branch: str,
    expected_checkout_branch: str | None = None,
) -> tuple[SetupPlanLocalOutcome | None, str | None]:
    """Build, but do not report, the authoritative local spec-gate result."""
    if not spec_file.exists():
        payload: dict[str, object] = {
            "error_code": "SPEC_FILE_MISSING",
            "error": f"Required spec not found for mission '{mission_slug}': {spec_file.resolve()}",
            "mission_slug": mission_slug,
            "mission_dir": str(feature_dir.resolve()),
            "feature_dir": str(feature_dir.resolve()),  # legacy alias of mission_dir (#5206)
            "spec_file": str(spec_file.resolve()),
            "remediation": [
                f"Restore the missing spec file at {spec_file.resolve()}",
                f"Or select another mission explicitly: {SETUP_PLAN_COMMAND_NAME} --mission <mission-slug> --json",
            ],
        }
        message = "\n".join([f"[red]Error:[/red] {payload['error']}"] + [f"  - {step}" for step in cast(list[str], payload["remediation"])])
        return SetupPlanLocalOutcome(payload, 1, "error"), message

    # FR-011: single read-surface commit check. ``spec_file`` is the
    # READ-resolved surface — since gate-read-surface-completion WP02 it is
    # resolved via the kind-aware chokepoint ``_planning_read_dir`` (SPEC is a
    # PRIMARY-partition kind → the primary ``target_branch`` dir for ALL
    # topologies), so ``is_committed`` checks ``spec_file`` against ``HEAD`` of
    # the primary surface it physically lives on. The #1848 coord-deleted case
    # never reaches here: ``_find_feature_directory`` raises
    # ``CoordinationBranchDeleted`` (a ``StatusReadPathNotFound``) above,
    # caught as ``ActionContextError`` → ``Exit(1)``.
    from specify_cli.missions._substantive import is_committed, is_substantive

    _commit_diagnostics: list[str] = []
    spec_is_committed = is_committed(spec_file, repo_root, diagnostics=_commit_diagnostics)
    mission_type = get_mission_type(feature_dir)
    spec_is_substantive = is_substantive(spec_file, "spec", mission_type=mission_type)
    if spec_is_committed and spec_is_substantive:
        return _evaluate_requirement_id_gate(spec_file, feature_dir, mission_slug)

    if mission_type == "research":
        blocked_reason = (
            "spec.md must be committed AND substantive before setup-plan can run. "
            "Under the exact 'Research Question & Scope' heading, populate the primary research "
            "question and a bare '**Scope**:' line with an in-scope boundary; author at least one "
            "substantive DR/AR/QR requirement each, replacing shipped template lines; "
            "commit spec.md, then re-run setup-plan."
        )
    else:
        blocked_reason = (
            "spec.md must be committed AND substantive before setup-plan can run. "
            "Populate the Functional Requirements (at least one FR-### row with "
            "real description content), commit spec.md, then re-run setup-plan."
        )
    payload = {
        "result": "blocked",
        "phase_complete": False,
        "blocked_reason": blocked_reason,
        "error_code": "SPEC_NOT_SUBSTANTIVE_OR_UNCOMMITTED",
        "mission_slug": mission_slug,
        "mission_dir": str(feature_dir.resolve()),
        "feature_dir": str(feature_dir.resolve()),  # legacy alias of mission_dir (#5206)
        "spec_file": str(spec_file.resolve()),
        "spec_committed": spec_is_committed,
        "spec_substantive": spec_is_substantive,
        "spec_commit_surfaces_checked": _commit_diagnostics,
    }
    rendered_payload = _inject_branch_contract(
        payload,
        target_branch=target_branch,
        current_branch=current_branch,
        expected_checkout_branch=expected_checkout_branch,
    )
    return (
        SetupPlanLocalOutcome(rendered_payload, 0, "blocked"),
        f"[yellow]Blocked:[/yellow] {blocked_reason}",
    )


def _requirement_id_gate_remediation() -> list[str]:
    """FR-013's remediation list: the kind vocabulary, the suffix rule, the
    foreign-citation form, the #5674 one-declaration rule, and the resolution step -- never a kind
    alternation literal (C-001)."""
    return [
        "Use one of the recognised requirement-ID kinds: FR, NFR, C or SC.",
        "Write the letter suffix in lowercase (e.g. FR-006a, not FR-006A).",
        "To cite another mission's ID, write <mission-slug>#<ID> instead of declaring it here.",
        "Declare each requirement ID once; renumber a repeated row.",
        "Commit spec.md and re-run setup-plan.",
    ]


def _render_requirement_id_gate_message(invalid_ids: list[dict[str, object]]) -> str:
    """The FR-013 refusal's human-readable rendering, ``SPEC_FILE_MISSING``-styled:
    one escaped line per offending ID. Escaping matters because
    ``grammar.RULE_TEXT`` contains ``[<lowercase letter>]``, which rich would
    otherwise parse as markup."""
    from rich.markup import escape

    lines = [f"[red]Error:[/red] {escape(SPEC_REQUIREMENT_IDS_INVALID_MESSAGE)}"]
    for entry in invalid_ids:
        token = escape(str(entry["token"]))
        rule = escape(str(entry["rule"]))
        lines.append(f"  - line {entry['line']}: {token} (rule: {rule})")
    return "\n".join(lines)


def _evaluate_requirement_id_gate(
    spec_file: Path,
    feature_dir: Path,
    mission_slug: str,
) -> tuple[SetupPlanLocalOutcome | None, str | None]:
    """FR-013: refuse a spec.md that declares a malformed requirement ID.

    Pure (builds, but does not report, the result), mirroring
    ``_evaluate_spec_gate``'s own 2-tuple contract -- returns ``(None,
    None)`` when the spec's declared IDs are all well-formed, so the caller
    (``_evaluate_spec_gate``) proceeds exactly as it did before this gate
    existed.
    """
    from specify_cli.requirement_mapping.lint import lint_spec_requirement_ids

    result = lint_spec_requirement_ids(spec_file.read_text(encoding="utf-8"), mission_type=get_mission_type(feature_dir))
    if not result.blocking:
        return None, None

    invalid_ids = [error.as_dict() for error in result.errors]
    payload: dict[str, object] = {
        "result": "error",
        "phase_complete": False,
        "error_code": SPEC_REQUIREMENT_IDS_INVALID,
        "error": SPEC_REQUIREMENT_IDS_INVALID_MESSAGE,
        "invalid_requirement_ids": invalid_ids,
        "mission_slug": mission_slug,
        "mission_dir": str(feature_dir.resolve()),
        "feature_dir": str(feature_dir.resolve()),  # legacy alias of mission_dir (#5206)
        "spec_file": str(spec_file.resolve()),
        "remediation": _requirement_id_gate_remediation(),
    }
    message = _render_requirement_id_gate_message(invalid_ids)
    return SetupPlanLocalOutcome(payload, 1, "error"), message


def _spec_requirement_id_warnings(spec_file: Path) -> list[dict[str, object]]:
    """FR-014: non-blocking prose-token warnings for the current spec.md.

    Returns ``[]`` when *spec_file* is not a file -- the spec gate owns
    existence, and several ``setup_plan`` unit tests patch
    ``_enforce_spec_gate`` to bypass it entirely, so ``spec_file`` may not
    sit at a real file in those tests.
    """
    if not spec_file.is_file():
        return []
    from specify_cli.requirement_mapping.lint import lint_spec_requirement_ids

    result = lint_spec_requirement_ids(spec_file.read_text(encoding="utf-8"), mission_type=get_mission_type(spec_file.parent))
    return [warning.as_dict() for warning in result.warnings]


def _resolve_plan_template(repo_root: Path, feature_dir: Path) -> ResolutionResult:
    """Resolve the activated mission's configured ``plan`` template once.

    Mission context comes from the canonical charter seam and configured
    artifact lookup remains routed through the historical ``mission`` shim.
    The effective winner is then shared by scaffolding and pristine comparison.

    The charter seam intentionally offers a best-effort metadata reader, but at
    this mutating boundary absence, corruption, and semantic invalidity are not
    equivalent.  Read metadata exactly once through the canonical strict-
    malformed reader.  Only an absent file may produce the neutral context used
    by the temporary #2660 selector.  Present metadata must carry a non-blank
    canonical ``mission_type`` field; the legacy ``mission`` field is retired
    (rc3 M5, FR-002) and is no longer read here -- a legacy-only meta.json must
    be backfilled via ``spec-kitty migrate backfill-mission-type`` before a
    plan template can resolve.  That captured value is passed explicitly into
    the charter seam so a subsequent filesystem mutation cannot change
    authority.
    """
    from specify_cli.cli.commands.agent import mission as _mission

    meta_path = feature_dir / "meta.json"
    # FR-007 route: ``route-unwrapped`` census site -- a corrupt meta.json
    # surfaces the typed ``MissionMetaReadError`` and PROPAGATES, rather than
    # being degraded into the "missing meta.json" branch below.
    meta = load_meta_fail_closed(feature_dir)
    if meta is None:
        # ``Path.exists()`` follows links, so the canonical reader reports None
        # for both a physically absent path and a broken/self-referential link.
        # Only the former is the temporary #2660 legacy condition.  is_symlink
        # uses lstat semantics and therefore detects both broken and loop links.
        if meta_path.is_symlink():
            raise TemplateConfigurationError(
                mission_type=None,
                artifact_kind="plan",
                reason=(f"cannot be resolved because {meta_path} is a symlink without readable mission metadata; repair or remove the link"),
            )
        resolved_mission_type = resolve_mission_type_context(repo_root)
    else:
        captured_mission_type = _canonical_meta_mission_type(meta)
        if captured_mission_type is None:
            raise TemplateConfigurationError(
                mission_type=None,
                artifact_kind="plan",
                reason=(
                    f"cannot be resolved because {feature_dir / 'meta.json'} must contain a non-blank "
                    "string field 'mission_type' (the legacy 'mission' field is retired and no longer "
                    "read -- run 'spec-kitty migrate backfill-mission-type' to populate 'mission_type')"
                ),
            )
        resolved_mission_type = resolve_mission_type_context(
            repo_root,
            mission_type=captured_mission_type,
        )
    if resolved_mission_type.mission_type is None:
        # C-005 compatibility boundary: existing typeless missions keep their
        # historical template until #2660 removes neutral-reader support.  This
        # is deliberately outside ``resolve_configured_template``; that new
        # seam must reject neutral contexts rather than invent software-dev.
        return _mission.resolve_template(
            "plan-template.md",
            repo_root,
            mission="software-dev",
        )
    return _mission.resolve_configured_template(
        "plan",
        repo_root,
        resolved_mission_type,
    )


def _scaffold_plan_template(
    plan_file: Path,
    plan_template: ResolutionResult,
) -> None:
    """Copy the plan template into ``plan_file`` when it does not yet exist (C-007).

    ``plan_template`` is the configured winner resolved once by
    :func:`_resolve_plan_template` and reused by pristine comparison.
    """
    if plan_file.exists():
        return
    shutil.copy2(plan_template.path, plan_file)


def _resolve_plan_result_state(*, is_substantive: bool, is_pristine: bool, committed: bool) -> tuple[Literal["success", "blocked"], bool]:
    """Pure state-resolution for the plan-scaffold result (FR-009 / #2566).

    Mirrors the shipped ``mission_create`` twin's ``scaffold_only`` flag
    (``mission_create.py`` ``_build_create_payload``, which sets
    ``"scaffold_only": True`` unconditionally at create time): the FIRST
    happy-path scaffold write is a non-error state, not ``blocked``. Does NOT
    introduce a new ``result`` value — ``setup-plan``'s JSON is a distinct
    contract from `next --result`'s fixed vocabulary
    (``next_cmd.py`` ``_valid_results()``), which never sees this field.

    Args:
        is_substantive: ``plan.md`` passes the #846 substantive-content gate.
        is_pristine: ``plan.md`` is byte-identical to the freshly-copied
            template (see
            :func:`specify_cli.missions._substantive.is_pristine_scaffold`).
        committed: ``plan.md`` is already committed at ``HEAD`` of its git
            surface.

    Returns:
        ``(result, scaffold_only)``:

        * substantive -> ``("success", False)`` — a real, committed plan.
        * pristine and not yet committed -> ``("success", True)`` — the first
          happy-path scaffold write; NOT the populated-but-insufficient case.
        * otherwise -> ``("blocked", False)`` — populated-but-insufficient
          content (K-1 / NFR-005 unchanged).
    """
    if is_substantive:
        return "success", False
    if is_pristine and not committed:
        return "success", True
    return "blocked", False


def _is_plan_pristine(
    plan_file: Path,
    plan_template: ResolutionResult,
) -> bool:
    """Return True iff ``plan_file`` is byte-identical to the freshly-copied template.

    Resolves the SAME template :func:`_scaffold_plan_template` would copy, so a
    file that has never been touched since scaffolding reads as pristine no
    matter how many times ``setup-plan`` re-runs against it. Configuration
    failures are raised before this helper, so missing mappings cannot silently
    degrade to the populated-but-insufficient path.
    """
    from specify_cli.missions._substantive import is_pristine_scaffold

    return bool(
        is_pristine_scaffold(
            plan_file.read_text(encoding="utf-8"),
            plan_template.path.read_text(encoding="utf-8"),
        )
    )


def _emit_spec_plan_phase_events(
    feature_dir: Path,
    mission_slug: str,
    spec_file: Path,
    repo_root: Path,
    *,
    owned: OwnedCheckout | None = None,
) -> None:
    """Record SpecifyCompleted + PlanStarted lifecycle markers (issue #1067).

    ``owned`` (review cycle 1 issue 3): forwarded as ``repo_root=`` to both
    ``emit_artifact_phase`` calls, so the lock-root resolution reads
    ``owned.repository_root`` directly instead of walking the worktree
    pointer back to R via ``get_main_repo_root``
    (``status/lifecycle_events.py``, out-of-map declared edit -- see that
    module's ``persist_lifecycle_event_local`` docstring).
    """
    from specify_cli.cli.commands.agent import mission as _mission

    try:
        from specify_cli.status import (
            emit_artifact_phase,
            SPECIFY_COMPLETED,
            PLAN_STARTED,
        )

        lifecycle_repo_root = owned.repository_root if owned is not None else None
        emit_artifact_phase(
            feature_dir,
            event_type=SPECIFY_COMPLETED,
            mission_slug=mission_slug,
            actor=SETUP_PLAN_COMMAND_NAME,
            artifact_path=_mission._branch_tree_relative_path(spec_file, repo_root),
            repo_root=lifecycle_repo_root,
        )
        emit_artifact_phase(
            feature_dir,
            event_type=PLAN_STARTED,
            mission_slug=mission_slug,
            actor=SETUP_PLAN_COMMAND_NAME,
            repo_root=lifecycle_repo_root,
        )
    except Exception as _phase_exc:  # noqa: BLE001
        logger.debug("Lifecycle phase emission skipped: %s", _phase_exc)


#: #3933 (Slice 1b): setup-plan's lifecycle events on a coordination Mission were
#: written to the coordination worktree's log but never committed there.
SETUP_PLAN_LIFECYCLE_UNCOMMITTED: Final = "SETUP_PLAN_LIFECYCLE_UNCOMMITTED"
#: The lifecycle event types setup-plan itself appends.
SETUP_PLAN_LIFECYCLE_EVENT_TYPES: Final = ("SpecifyCompleted", "PlanStarted", "PlanCompleted")


def _lifecycle_write_location(repo_root: Path, mission_slug: str, owned: OwnedCheckout | None) -> WriteLocation:
    """Where setup-plan appends its lifecycle events: the write location for status records (#3933).

    One write authority for the Mission's status log, as finalize-tasks uses
    (``_emit_tasks_started``): the coordination worktree's Mission directory on a
    coordination topology, the Mission directory everywhere else. Resolved by the
    caller outside any best-effort ``try`` so a named write-location refusal fails
    setup-plan closed instead of degrading to a debug line.
    """
    location: WriteLocation = placement_seam(repo_root, mission_slug, owned=owned).write_dir(MissionArtifactKind.STATUS_STATE)
    return location


#: ``CommitRouterResult.reason`` of a refusal where committing this checkout's log
#: would erase events the coordination branch holds (#3933 review cycle 2, B3).
_LIFECYCLE_LOSS_RISK: Final = "coordination_log_would_lose_events"


def _lifecycle_refusal(diagnostic: str, *, loss_risk: bool = False) -> CommitRouterResult:
    """A refused coordination commit of the lifecycle log, rendered by ``_refuse_uncommitted_lifecycle``.

    ``loss_risk`` marks a refusal where committing the checkout's log by hand
    would drop committed events, so the rendered remedy must never suggest it.
    """
    return CommitRouterResult(status="error", placement_ref="", diagnostic=diagnostic, reason=_LIFECYCLE_LOSS_RISK if loss_risk else None)


def _checkout_head(surface_root: Path) -> str | None:
    """The commit the coordination worktree's HEAD names, or ``None`` when it cannot be resolved."""
    from kernel.git import GitCommandError, run_git

    try:
        return run_git(surface_root, "rev-parse", "--verify", "HEAD").stdout.decode("utf-8").strip() or None
    except GitCommandError:
        return None


def _lifecycle_log_divergence(surface_root: Path, log: Path) -> CommitRouterResult | None:
    """Refuse when the worktree log lost events its branch HEAD committed (#3933 review B1).

    The log is committed whole, so committing a copy that lags the coordination
    branch would erase the missing events from the status authority. The same
    guard ``BookkeepingTransaction`` runs before a coordination status write
    (``committed_events_missing_from_worktree``) answers the question; its two
    named refusals become the diagnostic.
    """
    from specify_cli.coordination.status_surface_guard import committed_events_missing_from_worktree
    from specify_cli.coordination.transaction_errors import (
        BookkeepingStatusSurfaceDiverged,
        BookkeepingStatusSurfaceUnreadable,
    )

    try:
        missing = committed_events_missing_from_worktree(surface_root, log)
    except BookkeepingStatusSurfaceUnreadable as unreadable:
        return _lifecycle_refusal(str(unreadable), loss_risk=True)
    if not missing:
        return None
    diverged = BookkeepingStatusSurfaceDiverged(worktree_root=surface_root, events_path=log, missing_event_ids=missing)
    return _lifecycle_refusal(f"the coordination branch holds events this checkout's status log lacks. {diverged}", loss_risk=True)


def _commit_lifecycle_events_on_coordination(
    repo_root: Path,
    mission_slug: str,
    location: WriteLocation,
    owned: OwnedCheckout | None,
) -> CommitRouterResult | None:
    """Commit setup-plan's lifecycle log on the coordination branch (#3933, FR-002).

    Returns ``None`` only on a topology without a coordination branch: there the
    log already rides the plan commit (:func:`_lifecycle_log_for_plan_commit`). On
    a coordination topology the log is committed whole, once, through the mission
    commit entry point; the router answers ``unchanged`` when the branch already
    holds every line, so a re-run makes no commit (NFR-001). Every other outcome
    is a refusal (``status="error"``) the caller renders as
    ``SETUP_PLAN_LIFECYCLE_UNCOMMITTED`` (FR-004): no log where setup-plan just
    wrote its events, a worktree log that lost committed events (review B1), a
    router that raised (review S1), or a coordination branch that moved after
    the guard checked it (review B2): the commit is a compare-and-swap on the
    HEAD and the exact log bytes the guard read, so a writer landing in between
    is refused, never overwritten.
    """
    from mission_runtime import resolve_topology, routes_through_coordination
    from specify_cli.coordination.commit_router import commit_for_mission
    from specify_cli.git.protection_policy import ProtectionPolicy
    from specify_cli.status import mission_event_log_path

    topology = owned.topology if owned is not None else resolve_topology(repo_root, mission_slug)
    if not routes_through_coordination(topology):
        return None
    log = mission_event_log_path(location.path)
    if not log.is_file():
        return _lifecycle_refusal(f"no status log at {log}; the lifecycle events were not recorded")
    checked_head = _checkout_head(location.surface_root)
    if checked_head is None:
        return _lifecycle_refusal(f"the coordination worktree HEAD at {location.surface_root} could not be resolved", loss_risk=True)
    log_bytes = log.read_bytes()
    divergence = _lifecycle_log_divergence(location.surface_root, log)
    if divergence is not None:
        return divergence
    try:
        result = commit_for_mission(
            repo_root,
            mission_slug,
            files=(log,),
            message=f"chore({mission_slug}): record setup-plan lifecycle events",
            policy=ProtectionPolicy.resolve_for_mission(repo_root, mission_slug),
            kind=MissionArtifactKind.STATUS_STATE,
            expected_parent_sha=checked_head,
            expected_path_bytes={log: log_bytes},
        )
    except Exception as exc:  # noqa: BLE001 -- FR-004: any router failure must reach the named refusal, never the generic error arm
        result = _lifecycle_refusal(f"{type(exc).__name__}: {exc}")
    if _lifecycle_commit_refused(result) and _checkout_head(location.surface_root) != checked_head:
        # B2: the compare-and-swap lost; the branch moved after the guard checked it.
        if _lifecycle_events_landed(location.surface_root, log, log_bytes):
            # A concurrent status write committed the whole log, setup-plan's lines included.
            return CommitRouterResult(status=STATUS_UNCHANGED, placement_ref=result.placement_ref, diagnostic="another status write committed these events")
        moved = f"the coordination branch moved after setup-plan checked it (from {checked_head}); nothing was committed. {result.diagnostic or ''}"
        return _lifecycle_refusal(moved.strip(), loss_risk=True)
    return result


def _generic_error_payload(exc: Exception) -> dict[str, object]:
    """The JSON for setup-plan's generic error arm, keeping a named error's code.

    A write-location error (for example a coordination seed refusal) now ends the
    run before the plan commit (#3933), so its own ``error_code`` (or ``code``)
    must reach the operator instead of being dropped.
    """
    payload: dict[str, object] = {"error": str(exc)}
    for attr in ("error_code", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, str) and value:
            payload["error_code"] = value
            break
    return payload


def _setup_plan_event_ids(raw: str) -> set[str]:
    """Event ids of the setup-plan lifecycle lines in a status-log text (malformed lines are skipped)."""
    ids: set[str] = set()
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get("event_type") in SETUP_PLAN_LIFECYCLE_EVENT_TYPES and event.get("event_id"):
            ids.add(str(event["event_id"]))
    return ids


def _lifecycle_events_landed(surface_root: Path, log: Path, log_bytes: bytes) -> bool:
    """True when the coordination branch now holds every setup-plan event of the log setup-plan checked.

    Answers the squad finding on B2: a concurrent status write (``move-task``)
    commits the whole log under the status lock, setup-plan's lines included, and
    moves the branch; setup-plan's compare-and-swap then loses although nothing
    of its own is missing. Any read error answers ``False`` (the refusal stands).
    """
    from kernel.git import GitCommandError, blob_at

    ours = _setup_plan_event_ids(log_bytes.decode("utf-8", "replace"))
    try:
        committed = blob_at(surface_root, "HEAD", log.relative_to(surface_root).as_posix())
    except (GitCommandError, ValueError):
        return False
    return bool(ours) and committed is not None and ours <= _setup_plan_event_ids(committed.decode("utf-8", "replace"))


def _setup_plan_events_in_log(status_dir: Path) -> list[str]:
    """The setup-plan lifecycle event types present in ``status_dir``'s log, in log order, once each."""
    from specify_cli.status import mission_event_log_path

    log = mission_event_log_path(status_dir)
    found: list[str] = []
    try:
        lines = log.read_text(encoding="utf-8").splitlines()
    except (OSError, ValueError):  # ValueError: UnicodeDecodeError on a damaged log; the refusal must still render
        return found
    for line in lines:
        try:
            event_type = json.loads(line).get("event_type")
        except (ValueError, AttributeError):
            continue
        if event_type in SETUP_PLAN_LIFECYCLE_EVENT_TYPES and event_type not in found:
            found.append(event_type)
    return found


def _lifecycle_commit_payload(result: CommitRouterResult) -> dict[str, object]:
    """The ``lifecycle_commit`` JSON block for a coordination commit outcome."""
    return {"status": result.status, "commit_hash": result.commit_hash, "branch": result.placement_ref or None}


def _lifecycle_commit_refused(result: CommitRouterResult) -> bool:
    """True when the coordination commit neither landed nor was a no-op (FR-004)."""
    return result.status not in (STATUS_COMMITTED, STATUS_UNCHANGED)


def _lifecycle_log_for_plan_commit(feature_dir: Path, repo_root: Path, mission_slug: str, owned: OwnedCheckout | None) -> tuple[Path, ...]:
    """The Mission's lifecycle log to commit with ``plan.md``, when it shares the plan's partition (#3933).

    The lifecycle events are appended to ``feature_dir``'s ``status.events.jsonl``.
    On a topology without a coordination branch that log is a PRIMARY-partition
    file, committed beside the plan. On a coordination topology the log's kind
    routes to the coordination branch, whose own log the primary copy must never
    overwrite, so it is left out; :func:`_commit_lifecycle_events_on_coordination`
    commits it there instead (#3933). An owned run
    reads the topology off its validated fact, never re-resolving the repository.
    """
    from mission_runtime import resolve_topology, routes_through_coordination
    from specify_cli.status import mission_event_log_path

    log = mission_event_log_path(feature_dir)
    topology = owned.topology if owned is not None else resolve_topology(repo_root, mission_slug)
    if not log.is_file() or routes_through_coordination(topology):
        return ()
    return (log,)


def _commit_plan_if_substantive(
    plan_file: Path,
    feature_dir: Path,
    mission_slug: str,
    repo_root: Path,
    *,
    target_branch: str,
    json_output: bool,
    plan_template: ResolutionResult,
    owned: OwnedCheckout | None = None,
) -> tuple[CommitToBranchResult | None, str | None, bool]:
    """Commit plan.md when substantive; otherwise resolve blocked vs. scaffold_only.

    Returns ``(commit_result, blocked_reason, scaffold_only)``. Routes
    ``_commit_to_branch`` through the ``mission`` module so the
    ``mission._commit_to_branch`` patch seam keeps working.

    FR-009 / #2566: a freshly-scaffolded, byte-identical-to-template plan.md
    resolves to ``scaffold_only=True`` (``blocked_reason=None`` — a non-error
    state), NOT the populated-but-insufficient ``blocked`` path — see
    :func:`_resolve_plan_result_state`.
    """
    from specify_cli.cli.commands.agent import mission as _mission
    from specify_cli.missions._substantive import is_committed, is_substantive

    # Decision 5 (#3832): thread the SAME upstream-resolved ``plan_template``
    # into the now-mission-type-aware ``is_substantive`` call rather than
    # re-resolving the mission type independently at this call site.
    # ``project_dir=repo_root`` (#3830 FIX-1) lets an undeclared mission type
    # still pass via a PACK-PROVIDED declaration, resolved through the same
    # seam that resolved ``plan_template`` itself.
    mission_type = getattr(plan_template, "mission", None) or "software-dev"
    if is_substantive(plan_file, "plan", mission_type=mission_type, project_dir=repo_root):
        # #3933: record PlanCompleted BEFORE the commit so the plan and every lifecycle
        # event this command appended (SpecifyCompleted, PlanStarted, PlanCompleted)
        # land in one commit instead of leaving the log dirty for the next gate.
        try:
            from specify_cli.status import emit_artifact_phase, PLAN_COMPLETED

            emit_artifact_phase(
                feature_dir,
                event_type=PLAN_COMPLETED,
                mission_slug=mission_slug,
                actor=SETUP_PLAN_COMMAND_NAME,
                artifact_path=_mission._branch_tree_relative_path(plan_file, repo_root),
                repo_root=owned.repository_root if owned is not None else None,
            )
        except Exception as _plan_exc:  # noqa: BLE001
            logger.debug("PlanCompleted emission skipped: %s", _plan_exc)
        extra = _lifecycle_log_for_plan_commit(feature_dir, repo_root, mission_slug, owned)
        commit_result = _mission._commit_to_branch(plan_file, mission_slug, "plan", repo_root, target_branch, json_output, owned=owned, extra_files=extra)
        return commit_result, None, False

    _, scaffold_only = _resolve_plan_result_state(
        is_substantive=False,
        is_pristine=_is_plan_pristine(plan_file, plan_template),
        committed=is_committed(plan_file, repo_root),
    )
    # T007 (#3832): the scaffold/blocked-reason messages below read their
    # container heading / primary field / example peer field from the SAME
    # Decision 1/2 declaration ``is_substantive`` uses, instead of carrying
    # their own independently-maintained "Technical Context"/"Language/Version"
    # literals (TASKS-FRESH-001) — so a research/plan/pack-declared-type
    # operator sees guidance naming their own type's real fields.
    # ``project_dir=repo_root`` (#3830 FIX-1) reaches the same pack-provided
    # declaration ``is_substantive`` above just checked.
    from specify_cli.missions._substantive import (
        describe_plan_field_requirements,
        describe_technical_context_gap,
    )

    _field_info = describe_plan_field_requirements(mission_type, project_dir=repo_root)
    # FR-013 (#1896): name the offending Technical Context format.
    _plan_gap = describe_technical_context_gap(plan_file.read_text(encoding="utf-8"), mission_type, project_dir=repo_root)

    if _field_info is None:
        # #3830 severity-4 compounding-diagnostic fix: no field declaration
        # exists anywhere (built-in or pack-provided) for this mission
        # type — the REAL cause (``_plan_gap``, always non-None here — see
        # ``describe_technical_context_gap``) leads the message, instead of
        # being demoted to a trailing "Detail:" clause behind a hardcoded
        # "Technical Context"/"Language/Version" literal naming fields this
        # mission type's template may not even contain.
        blocked_reason = _plan_gap or f"No field declaration is registered for mission type {mission_type!r}."
        if not json_output:
            console.print(f"[yellow]Plan not committed:[/yellow] {blocked_reason}")
        return None, blocked_reason, False

    _heading, _primary_field, _example_peer = _field_info

    if scaffold_only:
        if not json_output:
            console.print(f"[cyan]→[/cyan] Plan scaffolded at {plan_file}; populate {_heading} and re-run setup-plan.")
        return None, None, True

    blocked_reason = (
        f"plan.md content is not substantive yet; populate {_heading} with real "
        f"values ({_primary_field} plus at least one peer field, such as {_example_peer}) — "
        "not template placeholders — and re-run setup-plan to commit."
    )
    if _plan_gap is not None:
        blocked_reason = f"{blocked_reason} Detail: {_plan_gap}"
    if not json_output:
        console.print(f"[yellow]Plan not committed:[/yellow] {blocked_reason}")
    return None, blocked_reason, False


def _run_documentation_gap_analysis(
    feature_dir: Path,
    mission_slug: str,
    repo_root: Path,
    meta_file: Path,
    *,
    target_branch: str,
    json_output: bool,
    owned: OwnedCheckout | None = None,
) -> str | None:
    """Run gap analysis for gap_filling/mission_specific doc missions; return its path or None."""
    from specify_cli.doc_analysis.doc_state import (
        canonical_iteration_mode,
        read_documentation_state,
        set_audit_metadata,
    )
    from specify_cli.doc_analysis.gap_analysis import generate_gap_analysis_report

    if not meta_file.exists():
        return None
    doc_state = read_documentation_state(meta_file)
    iteration_mode = canonical_iteration_mode(doc_state.get("iteration_mode", "initial")) if doc_state else "initial"
    if iteration_mode not in ("gap_filling", "mission_specific"):
        return None

    docs_dir = repo_root / "docs"
    if not docs_dir.exists():
        if not json_output:
            console.print("[yellow]Warning:[/yellow] No docs/ directory found, skipping gap analysis")
        return None

    gap_analysis_output = feature_dir / "gap-analysis.md"
    try:
        analysis = generate_gap_analysis_report(docs_dir, gap_analysis_output, project_root=repo_root)
        set_audit_metadata(
            meta_file,
            last_audit_date=analysis.analysis_date,
            coverage_percentage=analysis.coverage_matrix.get_coverage_percentage(),
        )
        with contextlib.suppress(Exception):  # Non-fatal: agent can commit separately
            from specify_cli.coordination.commit_router import commit_for_mission
            from specify_cli.git.protection_policy import ProtectionPolicy

            # owned-checkout-lifecycle-authority WP09: protection (and the
            # router's own repo_root) resolves from R when owned, matching
            # _commit_to_branch -- the linked checkout cannot weaken it. The
            # write itself still lands on P via commit_for_mission's owned=.
            _gap_protection_root = owned.repository_root if owned is not None else repo_root
            _gap_policy = ProtectionPolicy.resolve(_gap_protection_root)
            _gap_commit_result = commit_for_mission(
                repo_root=_gap_protection_root,
                mission_slug=mission_slug,
                files=(gap_analysis_output, meta_file),
                message=f"Add gap analysis for mission {mission_slug}",
                policy=_gap_policy,
                kind=MissionArtifactKind.PRIMARY_METADATA,
                target_branch=target_branch,
                owned=owned,
            )
            _warn_on_incomplete_surfaces(_gap_commit_result, json_output=json_output)
        if not json_output:
            coverage_pct = analysis.coverage_matrix.get_coverage_percentage() * 100
            console.print(f"[cyan]→ Gap analysis generated: {gap_analysis_output.name} (coverage: {coverage_pct:.1f}%)[/cyan]")
        return str(gap_analysis_output)
    except Exception as gap_err:
        if not json_output:
            console.print(f"[yellow]Warning:[/yellow] Gap analysis failed: {gap_err}")
        return None


def _detect_and_configure_generators(
    mission_slug: str,
    repo_root: Path,
    meta_file: Path,
    *,
    target_branch: str,
    json_output: bool,
    owned: OwnedCheckout | None = None,
) -> list[GeneratorConfig]:
    """Detect documentation generators, persist config to meta.json, return detected list."""
    from specify_cli.doc_analysis.doc_state import set_generators_configured
    from specify_cli.doc_analysis.doc_generators import (
        DocGenerator,
        JSDocGenerator,
        SphinxGenerator,
        RustdocGenerator,
    )

    generators_detected: list[GeneratorConfig] = []
    all_generators: list[DocGenerator] = [JSDocGenerator(), SphinxGenerator(), RustdocGenerator()]
    for gen in all_generators:
        with contextlib.suppress(Exception):  # Skip generators that fail detection
            if gen.detect(repo_root):
                generator_name = cast(Literal["sphinx", "jsdoc", "rustdoc"], gen.name)
                generators_detected.append({"name": generator_name, "language": gen.languages[0], "config_path": ""})
                if not json_output:
                    console.print(f"[cyan]→ Detected {gen.name} generator (languages: {', '.join(gen.languages)})[/cyan]")

    if generators_detected and meta_file.exists():
        try:
            set_generators_configured(meta_file, generators_detected)
            with contextlib.suppress(Exception):  # Non-fatal
                from specify_cli.coordination.commit_router import commit_for_mission
                from specify_cli.git.protection_policy import ProtectionPolicy

                # owned-checkout-lifecycle-authority WP09: same protection-
                # root rule as the gap-analysis commit above.
                _gen_protection_root = owned.repository_root if owned is not None else repo_root
                _gen_policy = ProtectionPolicy.resolve(_gen_protection_root)
                _gen_commit_result = commit_for_mission(
                    repo_root=_gen_protection_root,
                    mission_slug=mission_slug,
                    files=(meta_file,),
                    message=f"Update generator config for mission {mission_slug}",
                    policy=_gen_policy,
                    kind=MissionArtifactKind.PRIMARY_METADATA,
                    target_branch=target_branch,
                    owned=owned,
                )
                _warn_on_incomplete_surfaces(_gen_commit_result, json_output=json_output)
        except Exception as gen_err:
            if not json_output:
                console.print(f"[yellow]Warning:[/yellow] Failed to save generator config: {gen_err}")
    return generators_detected


def _run_documentation_wiring(
    mission_slug: str,
    repo_root: Path,
    *,
    target_branch: str,
    json_output: bool,
    owned: OwnedCheckout | None = None,
) -> tuple[str | None, list[GeneratorConfig]]:
    """Documentation-mission plan wiring (T014 + T016): gap analysis + generator detection.

    No-op (returns ``(None, [])``) for non-documentation missions. A
    documentation-type owned mission reaches both phase helpers below, which
    each accept ``owned=`` (owned-checkout-lifecycle-authority WP09, review
    cycle 1 issue 1): both commits land on P via ``commit_for_mission``'s
    ``owned=``, and protection resolves from ``owned.repository_root`` --
    covered by
    ``test_owned_lifecycle_acceptance_status.py::test_o2_flag_setup_plan_documentation_type_commits_gap_and_generators_in_p``
    (with and without a stale R copy).

    read-side-seam-primary-primitive-closure-01KYKMMT WP04 (FR-013, #2886):
    this used to take the caller's ``feature_dir`` (the STATUS/lifecycle-side
    coord-aware resolution -- see the comment at the call site) and read
    ``meta.json`` straight off it. Both metadata reads below (the mission-type
    check and the ``meta.json`` access ``_run_documentation_gap_analysis``/
    ``_detect_and_configure_generators`` perform) now route through a FRESH
    PRIMARY-partition seam read instead, and the gap-analysis WRITE that
    follows resolves through that SAME ``primary_dir`` (SC-007 scenario 2) --
    routing only one of the two reads would clear the #2214 pin while leaving
    the other bound to a possible coord husk (no ``meta.json`` since #2106),
    the exact honesty hole this subtask closes. The ``feature_dir`` parameter
    is therefore dropped: nothing in this function needs it any more.
    ``gap-analysis.md`` itself carries no ``MissionArtifactKind`` (WP02 T013's
    honest bound) -- it simply anchors on this resolved directory.
    """
    primary_dir = placement_seam(repo_root, mission_slug, owned=owned).read_dir(MissionArtifactKind.PRIMARY_METADATA)
    if get_mission_type(primary_dir) != MISSION_TYPE_DOCUMENTATION:
        return None, []
    meta_file = primary_dir / "meta.json"
    gap_analysis_path = _run_documentation_gap_analysis(
        primary_dir, mission_slug, repo_root, meta_file, target_branch=target_branch, json_output=json_output, owned=owned
    )
    generators_detected = _detect_and_configure_generators(mission_slug, repo_root, meta_file, target_branch=target_branch, json_output=json_output, owned=owned)
    return gap_analysis_path, generators_detected


def _build_setup_plan_result(
    *,
    plan_file: Path,
    spec_file: Path,
    feature_dir: Path,
    mission_slug: str,
    plan_is_substantive: bool,
    plan_blocked_reason: str | None,
    plan_commit_result: CommitToBranchResult | None,
    gap_analysis_path: str | None,
    generators_detected: list[GeneratorConfig],
    target_branch: str,
    current_branch: str,
    expected_checkout_branch: str | None = None,
    plan_scaffold_only: bool = False,
    requirement_id_warnings: Sequence[Mapping[str, object]] = (),
) -> SetupPlanLocalOutcome:
    """Build the authoritative setup-plan result without rendering it.

    FR-009 / #2566: ``plan_scaffold_only=True`` marks the first happy-path
    scaffold write (a pristine, byte-identical-to-template plan.md) as a
    non-error ``success`` + ``scaffold_only`` flag — mirroring the
    ``mission_create`` twin — instead of ``blocked``. ``phase_complete``
    stays tied to ``plan_is_substantive`` alone, so the scaffold_only case
    still reports ``phase_complete: false``.

    FR-014 / NFR-002: ``requirement_id_warnings`` is additive on every
    payload this builder produces (success, scaffold, and the
    plan-not-substantive blocked result) -- none of those carry an
    ``error_code`` key, unlike the FR-013 gate refusal built by
    ``_evaluate_requirement_id_gate``, which never reaches this builder.
    """
    result: dict[str, object] = {
        "result": "success" if (plan_is_substantive or plan_scaffold_only) else "blocked",
        "phase_complete": plan_is_substantive,
        "mission_slug": mission_slug,
        "plan_file": str(plan_file),
        "mission_dir": str(feature_dir),
        "feature_dir": str(feature_dir),  # legacy alias of mission_dir (#5206)
        "spec_file": str(spec_file),
        "plan_substantive": plan_is_substantive,
        "requirement_id_warnings": [dict(warning) for warning in requirement_id_warnings],
    }
    if plan_scaffold_only:
        result["scaffold_only"] = True
    if plan_blocked_reason is not None:
        result["blocked_reason"] = plan_blocked_reason
    # FR-006 / D-5: surface the real commit hash and the typed no-op
    # classification instead of an opaque ``commit_created: None``.
    if isinstance(plan_commit_result, CommitToBranchResult):
        result["commit_created"] = plan_commit_result.status == "committed"
        result["commit_hash"] = plan_commit_result.commit_hash
        result["commit_status"] = plan_commit_result.status
        if plan_commit_result.diagnostic is not None:
            result["commit_diagnostic"] = plan_commit_result.diagnostic
        if plan_commit_result.surfaces:
            result.update(commit_outcome_payload(plan_commit_result))
    if gap_analysis_path:
        result["gap_analysis"] = gap_analysis_path
    if generators_detected:
        result["generators_detected"] = generators_detected
    result = _inject_branch_contract(
        result,
        target_branch=target_branch,
        current_branch=current_branch,
        expected_checkout_branch=expected_checkout_branch,
    )
    render_kind: Literal["success", "scaffold", "blocked", "error"] = "scaffold" if plan_scaffold_only else "success" if plan_is_substantive else "blocked"
    return SetupPlanLocalOutcome(result, 0, render_kind)


def _emit_setup_plan_result(
    *,
    plan_file: Path,
    spec_file: Path,
    feature_dir: Path,
    mission_slug: str,
    plan_is_substantive: bool,
    plan_blocked_reason: str | None,
    plan_commit_result: CommitToBranchResult | None,
    gap_analysis_path: str | None,
    generators_detected: list[GeneratorConfig],
    target_branch: str,
    current_branch: str,
    expected_checkout_branch: str | None = None,
    json_output: bool,
    plan_scaffold_only: bool = False,
    owned: OwnedCheckout | None = None,
    requirement_id_warnings: Sequence[Mapping[str, object]] = (),
    lifecycle_result: CommitRouterResult | None = None,
    lifecycle_status_dir: Path | None = None,
) -> None:
    """Compatibility reporter backed by the side-effect-free result builder.

    ``lifecycle_result`` (#3933): the coordination commit of setup-plan's
    lifecycle events, ``None`` on a topology without a coordination branch (no
    key is added there). A refused or failed commit turns the result into a
    ``SETUP_PLAN_LIFECYCLE_UNCOMMITTED`` error and exits 1 after rendering, with
    the plan commit that already landed still reported (FR-004).
    """
    outcome = _build_setup_plan_result(
        plan_file=plan_file,
        spec_file=spec_file,
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        plan_is_substantive=plan_is_substantive,
        plan_blocked_reason=plan_blocked_reason,
        plan_commit_result=plan_commit_result,
        gap_analysis_path=gap_analysis_path,
        generators_detected=generators_detected,
        target_branch=target_branch,
        current_branch=current_branch,
        expected_checkout_branch=expected_checkout_branch,
        plan_scaffold_only=plan_scaffold_only,
        requirement_id_warnings=requirement_id_warnings,
    )
    payload = dict(outcome.payload)
    if lifecycle_result is not None:
        payload["lifecycle_commit"] = _lifecycle_commit_payload(lifecycle_result)
    if lifecycle_result is not None and _lifecycle_commit_refused(lifecycle_result):
        _refuse_uncommitted_lifecycle(payload, lifecycle_result, lifecycle_status_dir or feature_dir, json_output=json_output)
    if owned is not None:
        # FR-007: additive-only in owned runs; non-owned payloads never
        # carry this key (WP08's envelope rule).
        from specify_cli.cli.commands._owned_checkout import echo_stale_copy_warning, stale_copy_payload

        payload.update(stale_copy_payload(owned))
        if not json_output:
            echo_stale_copy_warning(owned)
    if not json_output:
        from rich.markup import escape

        for warning in requirement_id_warnings:
            token = escape(str(warning["token"]))
            message = escape(str(warning["message"]))
            console.print(f"[yellow]Warning:[/yellow] line {warning['line']}: {token} — {message}")
        console.print(f"[green]✓[/green] Plan scaffolded: {plan_file}")
        return
    _emit_json(payload)


def _refuse_uncommitted_lifecycle(
    payload: dict[str, object],
    result: CommitRouterResult,
    status_dir: Path,
    *,
    json_output: bool,
) -> None:
    """Render the ``SETUP_PLAN_LIFECYCLE_UNCOMMITTED`` refusal and exit 1 (#3933, FR-004)."""
    events = _setup_plan_events_in_log(status_dir)
    diagnostic = result.diagnostic or f"commit router status {result.status!r}"
    if result.reason == _LIFECYCLE_LOSS_RISK:
        # B3: committing this checkout's log would erase the events the branch holds.
        remedy = (
            "Do not commit this checkout's status log: it would erase events the coordination branch holds. "
            "Do what the diagnostic says (a moved branch needs nothing more), then re-run setup-plan to record its own lifecycle events again."
        )
    else:
        remedy = "They stay uncommitted there; commit them in that checkout or re-run setup-plan once the refusal is fixed."
    plan_commit = payload.get("commit_hash")
    kept = f" The plan commit {plan_commit} was kept." if plan_commit else ""
    message = (
        f"setup-plan could not commit its status log in {status_dir} on the coordination branch "
        f"(setup-plan lifecycle events present in the log: {', '.join(events) or 'none'}): {diagnostic} {remedy}{kept}"
    )
    payload.update(
        {
            "result": "error",
            "phase_complete": False,
            "error_code": SETUP_PLAN_LIFECYCLE_UNCOMMITTED,
            "error": message,
            "lifecycle_events_in_log": events,
            "lifecycle_diagnostic": diagnostic,
        }
    )
    if json_output:
        _emit_json(payload)
    else:
        console.print(f"Error: [{SETUP_PLAN_LIFECYCLE_UNCOMMITTED}] {message}", markup=False, style="red")
    raise typer.Exit(1)


@dataclass(frozen=True)
class _SetupPlanScope:
    """The resolved root/branch/feature-dir preamble for ``setup-plan`` (T046 campsite).

    Extracted so the owned-checkout arm (next commit) has a single place to
    branch: an owned run resolves every field from the fact instead of R,
    and skips ``_show_branch_context`` entirely (``target_branch`` comes
    straight from the fact).
    """

    repo_root: Path
    feature_dir: Path
    mission_slug: str
    target_branch: str
    owned: OwnedCheckout | None = None

    @property
    def git_root(self) -> Path:
        """The checkout every committed/governance read resolves from: P when owned, else R."""
        return self.owned.owned_root if self.owned is not None else self.repo_root


def _resolve_setup_plan_scope(feature: str | None, json_output: bool, *, owned_claim: Path | None = None) -> _SetupPlanScope:
    """Resolve the root/branch/feature-dir preamble; exit 1 on a missing project root.

    Behaviour-preserving for the non-owned path (locate the project root,
    enforce git preflight, resolve the feature dir, then read the branch
    context) -- byte-identical to the inline body it replaces. Owned
    (owned-checkout-lifecycle-authority WP09, FR-005): validates ownership
    exactly once via WP08's shared seam (G2: no direct
    ``resolve_owned_mission``/``adopt_owned_checkout`` call here), runs the
    git preflight against P (``owned.owned_root``) instead of R, and
    resolves every field straight from the fact -- ``_show_branch_context``
    never runs for an owned mission (``target_branch`` comes from the fact).
    """
    from mission_runtime import ActionContextError
    from specify_cli.cli.commands.agent import mission as _mission
    from specify_cli.cli.commands._owned_checkout import (
        emit_owned_refusal,
        resolve_owned_or_adopt,
    )
    from specify_cli.core.owned_mission import LIFECYCLE_OWNED_TOPOLOGIES

    repo_root = _mission.locate_project_root()
    if repo_root is None:
        error_msg = PROJECT_ROOT_NOT_FOUND_MESSAGE
        if json_output:
            _emit_json({"error": error_msg})
        else:
            console.print(f"[red]Error:[/red] {error_msg}")
        raise typer.Exit(1)

    try:
        owned = resolve_owned_or_adopt(repo_root, owned_claim, feature, cwd=Path.cwd(), allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES)
    except ActionContextError as exc:
        emit_owned_refusal(exc, json_output=json_output, context={"phase_complete": False}, stamp_version=True)

    if owned is not None:
        _mission._enforce_git_preflight(owned.owned_root, json_output=json_output, command_name=SETUP_PLAN_COMMAND_NAME)
        return _SetupPlanScope(
            repo_root=repo_root,
            feature_dir=owned.mission_dir,
            mission_slug=owned.mission_slug,
            # Landing branch for every display field (the non-owned contract),
            # read from the fact's own mission meta; the checkout/write branch
            # is ``owned.write_branch`` (``expected_checkout_branch``).
            target_branch=read_target_branch_from_meta(owned.mission_dir) or owned.write_branch,
            owned=owned,
        )

    _mission._enforce_git_preflight(
        repo_root,
        json_output=json_output,
        command_name=SETUP_PLAN_COMMAND_NAME,
    )

    feature_dir = _resolve_setup_plan_feature_dir(repo_root, feature, json_output=json_output)
    mission_slug = feature_dir.name
    _, target_branch = _mission._show_branch_context(repo_root, mission_slug, json_output)
    return _SetupPlanScope(repo_root=repo_root, feature_dir=feature_dir, mission_slug=mission_slug, target_branch=target_branch)


def setup_plan(
    feature: Annotated[str | None, typer.Option("--mission", help="Mission slug (e.g., '020-my-mission')")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output JSON format")] = False,
    owned_checkout: OwnedCheckoutOption = None,
) -> None:
    """Scaffold an implementation plan template in the repository root checkout or an owned checkout.

    This command is designed for AI agents to call programmatically.
    Creates plan.md and commits to target branch.

    Examples:
        spec-kitty agent mission setup-plan --json
        spec-kitty agent mission setup-plan --mission 020-my-feature --json

    ------------------------------------------------------------------
    The SaaS-sync boundary gates this command used to enforce (FR-011 auth
    refusal, boundary preflight, dossier push) were removed with the sync
    transport (issue #5); only local planning artifacts are produced here.
    ------------------------------------------------------------------
    """
    # Deferred import keeps this leaf free of an import cycle while honoring the
    # historical ``mission.<name>`` patch seams (``locate_project_root`` /
    # ``_enforce_git_preflight`` / ``_show_branch_context`` / ``get_current_branch`` /
    # ``_find_feature_directory`` / ``resolve_configured_template`` /
    # ``_commit_to_branch``).
    from specify_cli.cli.commands.agent import mission as _mission

    try:
        scope = _resolve_setup_plan_scope(feature, json_output, owned_claim=owned_checkout)
        repo_root = scope.repo_root
        feature_dir = scope.feature_dir
        mission_slug = scope.mission_slug
        target_branch = scope.target_branch
        owned = scope.owned
        git_root = scope.git_root

        # gate-read-surface-completion WP02 / FR-001 / #2107 (out-of-map edit —
        # WP01 owns ``mission.py``; rationale: re-point ``setup_plan``'s PLANNING
        # reads onto WP01's ``_planning_read_dir`` chokepoint). RESTORED after the
        # lane-d integration merge (32eb6df89) silently dropped the approved WP02
        # diff, reverting these joins to the coord-aware ``feature_dir`` — the
        # ratchet (FR-010) caught the regression. The driver bug: ``feature_dir``
        # comes from the coord-aware ``_find_feature_directory`` (→
        # ``resolve_handle_to_read_path`` → the coord worktree dir under a
        # materialized coordination topology). Since #2106 the planning artifacts
        # (spec.md, plan.md) live on the PRIMARY ``target_branch`` dir, so reading
        # them off ``feature_dir`` resolves to the coord husk and blocks with
        # ``SPEC_FILE_MISSING``. ``_planning_read_dir`` resolves SPEC / plan
        # (PRIMARY-partition kinds) to the primary dir for ALL topologies, so the
        # reads converge on the real artifact. Only the PLANNING reads move
        # (C-002): ``feature_dir`` stays the surface for STATUS/lifecycle emission
        # (``emit_artifact_phase``). Template context is
        # itself planning configuration, so it must resolve from ``plan_read_dir``
        # where the canonical ``meta.json`` lives; a coord husk may legitimately
        # be meta-less and must not turn a typed mission into the typeless
        # compatibility branch.
        # Routed through the ``mission`` shim (``_mission`` deferred-imported at the
        # top of this body) so the historical ``mission._planning_read_dir`` patch
        # seam — exercised by ``test_setup_plan_read_surface`` — reaches this caller.
        if owned is not None:
            # Both SPEC and PLAN are PRIMARY-partition kinds: every
            # PRIMARY-partition ``PlacementSeam.read_dir`` resolves to
            # ``owned.mission_dir`` for an owned run (WP04), so no seam call
            # is needed here -- using the fact's field directly is the
            # honest form (G4/G5).
            spec_read_dir = owned.mission_dir
            plan_read_dir = owned.mission_dir
        else:
            # Routed through the ``mission`` shim (``_mission`` deferred-imported at the
            # top of this body) so the historical ``mission._planning_read_dir`` patch
            # seam — exercised by ``test_setup_plan_read_surface`` — reaches this caller.
            spec_read_dir = _mission._planning_read_dir(repo_root, mission_slug, artifact_type="spec")
            plan_read_dir = _mission._planning_read_dir(repo_root, mission_slug, artifact_type="plan")
        spec_file = spec_read_dir / "spec.md"
        plan_file = plan_read_dir / "plan.md"

        # #7594: one planning checkout verdict, shared with check-prerequisites. The
        # expected checkout is the placement seam's planning write ref; the current branch
        # is the INVOKING checkout's HEAD (FR-006 / #3124), resolved once here at the
        # command entry point (#3786); the contract's ``target_branch`` is the landing
        # target from ``meta.json``. ``target_branch`` (above) still feeds the commit
        # helpers unchanged.
        invoking_root = owned.owned_root if owned is not None else resolve_checkout_identity(Path.cwd(), Intent.WRITE).invoking_root
        verdict = resolve_planning_checkout_verdict(
            repo_root,
            mission_slug,
            invoking_root=invoking_root,
            owned=owned,
            fallback_branch=target_branch,
        )
        current_branch = verdict.current_branch
        expected_checkout_branch = verdict.expected_checkout_branch
        contract_target_branch = verdict.target_branch

        if _enforce_spec_gate(
            spec_file,
            feature_dir,
            mission_slug,
            git_root,
            target_branch=contract_target_branch,
            current_branch=current_branch,
            expected_checkout_branch=expected_checkout_branch,
            json_output=json_output,
        ):
            return

        # FR-014: computed once, after the FR-013 gate has already passed --
        # every non-error setup-plan payload carries it additively.
        requirement_id_warnings = _spec_requirement_id_warnings(spec_file)

        try:
            plan_template = _resolve_plan_template(git_root, plan_read_dir)
        except FileNotFoundError as exc:
            raise FileNotFoundError("Plan template not found in repository or package") from exc
        _scaffold_plan_template(plan_file, plan_template)
        # #3933: the lifecycle events go to the write location for status records,
        # resolved here, outside every best-effort emission ``try``.
        lifecycle_location = _lifecycle_write_location(repo_root, mission_slug, owned)
        status_dir = lifecycle_location.path
        _emit_spec_plan_phase_events(status_dir, mission_slug, spec_file, git_root, owned=owned)

        from specify_cli.missions._substantive import is_substantive

        # Decision 5 (#3832): reuse the single upstream-resolved
        # ``plan_template`` (already in scope from ``_resolve_plan_template``
        # above) rather than re-resolving the mission type independently.
        # ``project_dir=git_root`` (#3830 FIX-1, owned-checkout-lifecycle-
        # authority WP09 FR-016): reach a pack-provided declaration through
        # the same seam that resolved ``plan_template`` -- P for an owned
        # run, R otherwise.
        plan_is_substantive = is_substantive(
            plan_file,
            "plan",
            mission_type=getattr(plan_template, "mission", None) or "software-dev",
            project_dir=git_root,
        )
        plan_commit_result, plan_blocked_reason, plan_scaffold_only = _commit_plan_if_substantive(
            plan_file,
            status_dir,
            mission_slug,
            git_root,
            target_branch=target_branch,
            json_output=json_output,
            plan_template=plan_template,
            owned=owned,
        )

        # #3933 (FR-002): one commit of the lifecycle log on the coordination branch,
        # after the plan commit and on a scaffold-only or blocked run alike.
        lifecycle_result = _commit_lifecycle_events_on_coordination(repo_root, mission_slug, lifecycle_location, owned)

        gap_analysis_path, generators_detected = _run_documentation_wiring(
            mission_slug, git_root, target_branch=target_branch, json_output=json_output, owned=owned
        )

        _emit_setup_plan_result(
            plan_file=plan_file,
            spec_file=spec_file,
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            plan_is_substantive=plan_is_substantive,
            plan_blocked_reason=plan_blocked_reason,
            plan_commit_result=plan_commit_result,
            gap_analysis_path=gap_analysis_path,
            generators_detected=generators_detected,
            target_branch=contract_target_branch,
            current_branch=current_branch,
            expected_checkout_branch=expected_checkout_branch,
            json_output=json_output,
            plan_scaffold_only=plan_scaffold_only,
            owned=owned,
            requirement_id_warnings=requirement_id_warnings,
            lifecycle_result=lifecycle_result,
            lifecycle_status_dir=status_dir,
        )

    except typer.Exit:
        raise
    except TemplateConfigurationError as e:
        payload: dict[str, object] = {
            "result": "error",
            "phase_complete": False,
            "error_code": "TEMPLATE_CONFIGURATION_ERROR",
            "error": str(e),
            "mission_type": e.mission_type,
            "artifact_kind": e.artifact_kind,
        }
        if e.mapped_filename is not None:
            payload["mapped_filename"] = e.mapped_filename
        if json_output:
            _emit_json(payload)
        else:
            console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None
    except Exception as e:
        if json_output:
            _emit_json(_generic_error_payload(e))
        else:
            console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None
