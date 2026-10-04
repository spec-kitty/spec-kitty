"""``finalize-tasks`` phase: target-branch resolution and branch-contract persistence.

Also owns the explicit ``--target-branch`` override.

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

from dataclasses import dataclass
from pathlib import Path

import typer

from specify_cli.core.checkout_identity import CheckoutIdentity
from specify_cli.core.paths import (
    get_status_read_root,
)
from specify_cli.missions._resolve_planning_branch import PlanningBranchResolutionFailed
from specify_cli.cli.commands.agent.mission_finalize_seams import META_JSON_FILENAME


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

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    try:
        declared_target: str = _mf._resolve_planning_branch_via_mission(repo_root, primary_dir, target_branch_override=target_branch_override)
    except PlanningBranchResolutionFailed as exc:
        if json_output:
            _mf._emit_json({"error": str(exc), "error_code": exc.error_code})
        else:
            _mf.console.print(f"[red]Error:[/red] {exc}")
            _mf.console.print("[yellow]Hint:[/yellow] re-run with [bold]--target-branch <ref>[/bold] to override.")
        raise typer.Exit(1) from exc

    meta = _mf.load_meta_fail_closed(primary_dir) or {}
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
        _mf._emit_json(
            {
                "error": message,
                "error_code": "PR_BOUND_PLANNING_BRANCH_REQUIRED",
            }
        )
    else:
        _mf.console.print(f"[red]Error:[/red] {message}")
    raise typer.Exit(1)


def _resolve_merge_target_branch(primary_dir: Path, planning_branch: str) -> str:
    """Resolve final landing without conflating it with planning placement."""

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    meta = _mf.load_meta_fail_closed(primary_dir) or {}
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

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    meta = _mf.load_meta_fail_closed(planning_dir) or {}
    if not meta.get("pr_bound") or meta.get("target_branch") == planning_branch:
        return
    meta_path = planning_dir / META_JSON_FILENAME
    if _mf._meta_json_delta_is_finalize_attributable(meta_path, repo_root):
        return

    message = (
        "Cannot recover the legacy PR-bound branch contract while foreign "
        "meta.json changes are pending. Commit or discard those changes, then "
        "run finalize-tasks again."
    )
    if json_output:
        _mf._emit_json(
            {
                "error": message,
                "error_code": "PR_BOUND_RECOVERY_FOREIGN_META_DELTA",
            }
        )
    else:
        _mf.console.print(f"[red]Error:[/red] {message}")
    raise typer.Exit(1)


def _persist_recovered_pr_bound_contract(
    planning_dir: Path,
    *,
    planning_branch: str,
    merge_target_branch: str,
) -> bool:
    """Normalize #2938 legacy metadata; return whether bytes were written."""

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    meta = _mf.load_meta_fail_closed(planning_dir) or {}
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

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    target_owner = get_status_read_root(primary_dir).resolve()
    target_repository = _mf.get_main_repo_root(target_owner).resolve()
    ambient_checkout = invocation_identity.invoking_root.resolve()
    ambient_repository = _mf.get_main_repo_root(ambient_checkout).resolve()
    invoking_checkout = ambient_checkout if ambient_repository == target_repository else target_owner
    if invoking_checkout == target_owner:
        return

    message = (
        "Refusing to write: this invocation does not own the target mission "
        f"checkout {target_owner}. Run the command from that checkout, or "
        "target a checkout this invocation owns."
    )
    if json_output:
        _mf._emit_json(
            {
                "error": message,
                "error_code": "CHECKOUT_WRITE_OWNERSHIP_REFUSED",
            }
        )
    else:
        _mf.console.print(f"[red]Error:[/red] {message}")
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

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    original_target = (_mf.load_meta_fail_closed(primary_dir) or {}).get("target_branch")
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

    from specify_cli.cli.commands.agent import mission_finalize as _mf

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
            _mf.console.print(f"[yellow]Warning:[/yellow] could not persist --target-branch override to meta.json: {error_detail}")
        else:
            # SK3466-R-002: without this, a --json caller gets ZERO
            # diagnostic — meta_json_persisted silently stays False and a
            # later PROTECTED_BRANCH_REFUSED (still reading the stale
            # on-disk value) reads as an unexplained recurrence of #3466
            # instead of a directly attributable persist failure.
            _mf._emit_json(
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
        _mf.console.print(f"[yellow]Note:[/yellow] target_branch override persisted to meta.json ({previous_value} -> {target_branch})")
    return TargetBranchPersistOutcome(persisted=True, previous_value=previous_value)
