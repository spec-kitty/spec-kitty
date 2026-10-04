"""Mission-aware ``spec-commit`` entrypoint (FR-001/002/003).

Closes the #1619 P0 specify-phase deadlock: unlike the generic ``safe-commit``
command (which is mission-blind), this command derives the mission slug from a
``kitty-specs/<slug>/`` path argument or ``--mission``, resolves the
:class:`~specify_cli.git.protection_policy.ProtectionPolicy` at the command
boundary, and routes the commit through
:func:`~specify_cli.coordination.commit_router.commit_for_mission`.

SPEC is a PRIMARY/planning artifact, so it lands on the mission's primary
target branch for every topology and NEVER routes through coordination
(write-surface-coherence WP02/WP03). On a PROTECTED primary the commit is
therefore refused — not silently transited to a coord worktree — with the two
real remedies: create/check out a non-protected feature branch, or set the
``SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS`` operator hatch (#2739 B01).

Design basis: WP02 / IC-02 / ADR ``2026-06-21-1``.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import cast

import typer
from specify_cli.cli.console import console

from mission_runtime import ActionContextError, MissionArtifactKind, OwnedCheckout
from specify_cli.cli.commands._commit_message import MESSAGE_OPTION_HELP, join_message_paragraphs
from specify_cli.cli.commands._owned_checkout import OwnedCheckoutOption, resolve_owned_or_refuse
from specify_cli.coordination import commit_outcome
from specify_cli.coordination.commit_outcome import (
    SurfaceOutcome,
    commit_outcome_payload,
    render_commit_outcome,
)
from specify_cli.coordination.commit_router import CommitRouterResult, commit_for_mission
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.owned_mission import LIFECYCLE_OWNED_TOPOLOGIES, require_unstaged_index
from specify_cli.git.protection_policy import ProtectionPolicy
from specify_cli.task_utils import find_repo_root

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _current_repo_root() -> Path:
    """Return the primary repo root (follows worktree links to main checkout)."""
    root: Path = find_repo_root()
    return root


def _derive_mission_slug(path_arg: str | None, mission_opt: str | None) -> str | None:
    """Derive the mission slug from a ``kitty-specs/<slug>/`` path or ``--mission``."""
    if mission_opt:
        return mission_opt.strip()
    if path_arg:
        # Accept either the slug directly or a ``kitty-specs/<slug>`` path.
        p = Path(path_arg)
        # If the path contains a ``kitty-specs`` component, take the part after it.
        parts = p.parts
        try:
            idx = next(i for i, part in enumerate(parts) if part == KITTY_SPECS_DIR)
            # slug is the component immediately after ``kitty-specs``
            if idx + 1 < len(parts):
                return parts[idx + 1]
        except StopIteration:
            pass
        # Otherwise treat the final component as the slug.
        return p.name or None
    return None


def _payload(
    *,
    success: bool,
    committed: bool = False,
    placement_ref: str | None = None,
    commit_hash: str | None = None,
    error: str | None = None,
    diagnostic: str | None = None,
    reason: str | None = None,
    surfaces: list[dict[str, object]] | None = None,
    arguments: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "result": "success" if success else "error",
        "success": success,
        "committed": committed,
    }
    if placement_ref is not None:
        result["placement_ref"] = placement_ref
    if commit_hash is not None:
        result["commit_hash"] = commit_hash
    if error is not None:
        result["error"] = error
    if diagnostic is not None:
        result["diagnostic"] = diagnostic
    if reason is not None:
        result["reason"] = reason
    # WP13 (FR-007 / FR-007a): additive-only -- every existing key above keeps
    # its exact meaning; these two are populated only once a
    # ``CommitRouterResult`` exists to render through the shared trio
    # (``commit_outcome.py``), never for the pre-commit refusal envelopes
    # (``_refusal_envelope``) that short-circuit before ``commit_for_mission``
    # is even called.
    if surfaces is not None:
        result["surfaces"] = surfaces
    if arguments is not None:
        result["arguments"] = arguments
    return result


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------


def _resolve_commit_inputs(
    repo_root: Path,
    files: list[Path],
    mission_slug: str | None,
    owned: OwnedCheckout | None,
) -> tuple[str | None, list[Path]]:
    """Resolve and validate the complete commit batch before any mutation.

    An owned run reads its slug and every path off the validated fact:
    ``owned.files`` (whose ``OwnedCheckoutPathRefused`` maps to
    ``OWNED_MISSION_PATH_REFUSED`` at the CLI edge) runs first, then
    ``require_unstaged_index``, so the whole batch is refused before staging.
    """
    if owned is not None:
        abs_files = owned.files(files)
        require_unstaged_index(owned)
        return owned.mission_slug, abs_files
    abs_files = [(repo_root / path).resolve() if not path.is_absolute() else path.resolve() for path in files]
    return mission_slug, abs_files


def _refusal_envelope(code: str, message: str) -> dict[str, object]:
    """This command's failure payload plus the owned refusal's ``error_code``."""
    return {**_payload(success=False, error=message), "error_code": code}


def _mission_slug_from_args(files: list[Path], mission: str | None) -> str | None:
    """The mission handle this invocation names: ``--mission``, else the first file's ``kitty-specs/<slug>/``."""
    return _derive_mission_slug(str(files[0]) if files else None, mission)


def _reject_directory_args(abs_files: list[Path], json_output: bool) -> None:
    """Fail fast on directory arguments with a clear, files-only message.

    #2739 B11: git stages a directory's files, but the safe-commit backstop
    compares literally against the requested path (the directory), so a directory
    arg would otherwise abort with the opaque "staging area contains unexpected
    paths" error. Reject early with actionable guidance instead.
    """
    directory_args = [f for f in abs_files if f.is_dir()]
    if not directory_args:
        return
    listed = ", ".join(str(d) for d in directory_args)
    _err(
        json_output,
        "spec-commit takes individual file paths, not directories. "
        f"Received director{'ies' if len(directory_args) > 1 else 'y'}: "
        f"{listed}. Pass the specific files to commit instead.",
    )
    raise typer.Exit(1)


def _commit_spec_files(
    repo_root: Path,
    mission_slug: str,
    abs_files: list[Path],
    message: str,
    target_branch: str | None,
    owned: OwnedCheckout | None,
) -> CommitRouterResult:
    """Boundary-resolve the protection policy, then route the commit (T002 extraction).

    The operator-facing ``spec-commit`` entry point commits the SPEC planning
    artifact (write-surface-coherence WP02 / T007). SPEC is a primary kind, so
    it lands on the primary target branch for every topology -- no
    planning→coord transit.
    """
    policy = ProtectionPolicy.resolve(repo_root)
    return commit_for_mission(
        repo_root=repo_root,
        mission_slug=mission_slug,
        files=tuple(abs_files),
        message=message,
        policy=policy,
        kind=MissionArtifactKind.SPEC,
        target_branch=target_branch,
        owned=owned,
    )


def _relpath(repo_root: Path, path: Path) -> str:
    """Render *path* repo-relative, as a :class:`~specify_cli.coordination.commit_outcome.PathFate` carries it.

    Falls back to the raw ``str(path)`` when *path* is not under *repo_root*
    (mirrors ``commit_router._relpath``'s own fallback, so an argument's
    computed key matches the keys :func:`_index_surface_fates` reads off
    ``result.surfaces``).
    """
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _fate_for_skip(reason: str) -> str:
    """Map a ``skipped`` :class:`PathFate` reason to its argument-level fate.

    Contract rule 3 (``commit-outcome.md``): ``skipped`` holds only genuine
    no-ops (``no_op_already_committed`` / ``no_op_no_changes`` -> argument
    fate ``unchanged``) or an actionable ``COORD_RECORD_IN_ROOT_CHECKOUT``
    skip (-> argument fate ``skipped``, since the operator's root-checkout
    edit never reaches the target and something IS actionable here).
    """
    return "skipped" if reason == commit_outcome.COORD_RECORD_IN_ROOT_CHECKOUT else "unchanged"


def _index_surface_fates(surfaces: tuple[SurfaceOutcome, ...]) -> list[tuple[str, dict[str, object]]]:
    """Every surface's committed/skipped/refused entries as ``(path, fate)`` pairs, in surface order.

    A COORD-kind path committed, skipped (``no_op_no_changes`` in particular
    -- review cycle 2 N3, confirmed by probing the real router's payload) or
    refused from its materialised coordination-worktree copy is recorded
    there under the WORKTREE-NESTED path (``.worktrees/<name>/kitty-specs/
    <slug>/...`` -- ``commit_router._relpath`` resolves the real on-disk
    path against ``repo_root``, and the coordination worktree lives under
    it), which differs from the CALLER's root-checkout argument. This is
    NOT limited to ``committed``: any of the three lists can carry the
    worktree-nested form, which is exactly why :func:`_find_fate_for_path`'s
    mission-relative SUFFIX fallback exists -- the router never fills
    ``PathFate.owning_path`` (contract rule 2) or maps a committed path back
    to the caller's own, so this heuristic is the only bridge available
    (N3: a WP05 follow-up should close this gap at the source). Returned as
    an ordered list, not a flat dict, so :func:`_find_fate_for_path` can try
    an exact match first and the suffix match second.
    """
    entries: list[tuple[str, dict[str, object]]] = []
    for outcome in surfaces:
        for path in outcome.committed:
            entries.append((path, {"fate": "committed", "surface": outcome.surface}))
        for fate in outcome.skipped:
            skip_entry: dict[str, object] = {"fate": _fate_for_skip(fate.reason), "surface": outcome.surface, "reason": fate.reason}
            entries.append((fate.path, skip_entry))
            if fate.owning_path:
                entries.append((fate.owning_path, skip_entry))
        for fate in outcome.refused:
            refused_entry: dict[str, object] = {"fate": "refused", "surface": outcome.surface, "reason": fate.reason}
            entries.append((fate.path, refused_entry))
            if fate.owning_path:
                entries.append((fate.owning_path, refused_entry))
    return entries


def _find_fate_for_path(entries: list[tuple[str, dict[str, object]]], rel: str) -> dict[str, object] | None:
    """Exact match first (the common, untranslated case), then a ``/``-boundary suffix match."""
    for path, entry in entries:
        if path == rel:
            return entry
    for path, entry in entries:
        if path.endswith(f"/{rel}"):
            return entry
    return None


def _argument_fates(abs_files: list[Path], result: CommitRouterResult, repo_root: Path) -> list[dict[str, object]]:
    """One fate entry per *abs_files* input, in order (FR-007a).

    Never drops an input silently (contract "JSON shape changes"): a path
    matching no surface entry is itself a contract violation, logged and
    reported as ``refused`` / ``PATH_UNROUTABLE`` rather than omitted.
    """
    entries = _index_surface_fates(result.surfaces)
    arguments: list[dict[str, object]] = []
    for abs_path in abs_files:
        rel = _relpath(repo_root, abs_path)
        matched = _find_fate_for_path(entries, rel)
        if matched is None:
            logger.warning("spec-commit: %s matched no commit surface; reporting PATH_UNROUTABLE", rel)
            matched = {"fate": "refused", "surface": None, "reason": commit_outcome.PATH_UNROUTABLE}
        entry: dict[str, object] = {"path": rel, "fate": matched["fate"], "surface": matched["surface"]}
        if matched["fate"] != "committed":
            entry["reason"] = matched.get("reason")
        arguments.append(entry)
    return arguments


def _compute_success(result: CommitRouterResult, arguments: list[dict[str, object]]) -> bool:
    """``success`` per contract rule 4 and T070 step 4 (B3, review cycle 2).

    Preserves today's per-status success (``committed``/``unchanged`` -> True,
    ``no_op_wrong_surface``/``error`` -> False) and ADDITIONALLY forces it
    False when either:

    - any populated surface is itself ``refused``/``error`` (the #5513
      masking shape: a mixed batch whose CALLER-partition group committed,
      so the legacy top-level status reads ``committed``, while another
      group's surface was refused); or
    - any argument's own fate is ``refused`` while ``result.surfaces`` is
      POPULATED -- this also catches the ``PATH_UNROUTABLE`` fallback (B3):
      an input matching NO surface entry at all (a foreign-worktree path
      staging dropped, or a legacy Mission whose coordination dir name
      differs) carries no ``SurfaceOutcome`` to inspect, so the
      surfaces-only check above cannot see it.

    Never the reverse in either case -- a populated surface or a refused
    argument can only push success toward False. Empty ``surfaces`` (a
    legacy construction site / test double that never populated the field,
    or an early argument-error return) falls back to the per-status rule
    UNCHANGED -- the argument check is gated on ``result.surfaces`` too,
    because a bare double with NO surface data at all makes EVERY argument
    ``PATH_UNROUTABLE`` by construction, which would otherwise flip a
    legacy caller's pinned ``success: true`` with nothing genuinely wrong.
    """
    base_success = result.status in (commit_outcome.STATUS_COMMITTED, commit_outcome.STATUS_UNCHANGED)
    if not result.surfaces:
        return base_success
    surface_failed = any(outcome.status in ("refused", "error") for outcome in result.surfaces)
    argument_refused = any(argument["fate"] == "refused" for argument in arguments)
    return base_success and not surface_failed and not argument_refused


def _build_spec_commit_payload(
    result: CommitRouterResult,
    *,
    success: bool,
    arguments: list[dict[str, object]],
) -> dict[str, object]:
    """Build the JSON payload: existing keys unchanged, ``surfaces``/``arguments`` additive (contract rule 6)."""
    surfaces_payload = cast("list[dict[str, object]]", commit_outcome_payload(result)["surfaces"])
    if result.status == commit_outcome.STATUS_COMMITTED:
        return _payload(
            success=success,
            committed=True,
            placement_ref=result.placement_ref,
            commit_hash=result.commit_hash,
            surfaces=surfaces_payload,
            arguments=arguments,
        )
    if result.status == commit_outcome.STATUS_UNCHANGED:
        # #2739 B03: a committed:false success must carry a machine-readable
        # reason so a caller can tell "nothing to do" from "silently wrong".
        return _payload(
            success=success,
            committed=False,
            placement_ref=result.placement_ref,
            reason=result.reason or "no_op",
            surfaces=surfaces_payload,
            arguments=arguments,
        )
    if result.status == commit_outcome.STATUS_NO_OP_WRONG_SURFACE:
        # T008: actionable refusal — the router's own diagnostic already names
        # the concrete remedy; no coordination-worktree retry hint is added
        # here since that transit no longer exists.
        actionable = result.diagnostic or "Artifact absent at resolved placement."
        return _payload(
            success=False,
            error=actionable,
            placement_ref=result.placement_ref,
            diagnostic=result.diagnostic,
            surfaces=surfaces_payload,
            arguments=arguments,
        )
    # "error"
    return _payload(
        success=False,
        error=result.diagnostic or "Commit failed.",
        placement_ref=result.placement_ref,
        surfaces=surfaces_payload,
        arguments=arguments,
    )


def _print_argument_fate_lines(arguments: list[dict[str, object]]) -> None:
    """One dim line per non-committed argument (T071 step 1), beyond the surface summary lines.

    ``markup=False`` (N1, review cycle 2): a path, branch name or router
    diagnostic can itself contain a literal ``[...]`` run; printed through
    rich's default markup mode that would be swallowed or mis-styled instead
    of shown verbatim.
    """
    for argument in arguments:
        if argument["fate"] == "committed":
            continue
        reason = argument.get("reason")
        suffix = f" ({reason})" if reason else ""
        console.print(f"{argument['path']}: {argument['fate']}{suffix}", markup=False)


def _print_legacy_success_text(result: CommitRouterResult) -> None:
    """The exact pre-WP13 ``committed``/``unchanged`` wording (empty-``surfaces`` fallback only)."""
    if result.status == commit_outcome.STATUS_COMMITTED:
        console.print(f"[green]✓[/green] Spec artifact(s) committed to {result.placement_ref}")
        if result.commit_hash:
            console.print(f"[dim]Commit: {result.commit_hash[:7]}[/dim]")
    else:
        console.print("[dim]Spec artifact(s) unchanged, no commit needed[/dim]")


def _print_spec_commit_text(result: CommitRouterResult, arguments: list[dict[str, object]]) -> None:
    """Render through the shared trio on EVERY arm when ``surfaces`` is populated (B2, review cycle 2).

    FR-007's "no consumer formats surface outcomes by hand" rule, and its own
    masking fix, both apply regardless of the legacy top-level ``status``: a
    mixed batch whose coordination group failed (lock held, say) reports the
    legacy status as ``error`` even though the PRIMARY group genuinely
    committed -- an operator reading only the old single-line ``Error:``
    message would never learn that. When ``result.surfaces`` is populated,
    the surface + non-committed-argument lines print FIRST, on every arm;
    the existing actionable single-line refusal/error (when the status calls
    for one) still follows them, unchanged. The legacy fallback (empty
    ``surfaces``, a pre-WP05 construction site or a test double) keeps the
    exact pre-WP13 wording so an unmigrated caller's text stays
    byte-identical.
    """
    if result.surfaces:
        for line in render_commit_outcome(result):
            console.print(line, markup=False)
        _print_argument_fate_lines(arguments)
    if result.status in (commit_outcome.STATUS_COMMITTED, commit_outcome.STATUS_UNCHANGED):
        if not result.surfaces:
            _print_legacy_success_text(result)
        return
    if result.status == commit_outcome.STATUS_NO_OP_WRONG_SURFACE:
        actionable = result.diagnostic or "Artifact absent at resolved placement."
        console.print(f"[red]Error:[/red] {actionable}")
        return
    console.print(f"[red]Error:[/red] {result.diagnostic or 'Commit failed.'}")


def _render_spec_commit_result(
    result: CommitRouterResult,
    *,
    json_output: bool,
    abs_files: list[Path],
    repo_root: Path,
) -> None:
    """Render *result* and raise ``typer.Exit(1)`` per the shared exit-code rule.

    Non-zero iff any populated surface is ``refused``/``error``, or any
    argument's own fate is ``refused`` (B3 -- the ``PATH_UNROUTABLE``
    fallback has no ``SurfaceOutcome`` to inspect) -- never zero while any
    such surface or argument is silently ignored (FR-007a).
    """
    arguments = _argument_fates(abs_files, result, repo_root)
    success = _compute_success(result, arguments)
    payload = _build_spec_commit_payload(result, success=success, arguments=arguments)

    if json_output:
        print(json.dumps(payload, indent=2))
    else:
        _print_spec_commit_text(result, arguments)

    if not success:
        raise typer.Exit(1)


def spec_commit_command(
    files: list[Path] = typer.Argument(
        ...,
        help=("Spec artifacts to commit (absolute or relative paths). Must belong to the mission resolved via --mission or the kitty-specs/<slug>/ path."),
    ),
    message: list[str] = typer.Option(..., "--message", "-m", help=MESSAGE_OPTION_HELP),
    mission: str | None = typer.Option(
        None,
        "--mission",
        help=("Mission slug (e.g. '001-my-mission'). When omitted, the slug is derived from the first file argument's kitty-specs/<slug>/ path."),
    ),
    target_branch: str | None = typer.Option(
        None,
        "--target-branch",
        help=(
            "Short TARGET branch name for this Mission (not the repository-root "
            "checkout). Passed to the commit router for placement resolution and, "
            "on an --owned-checkout run, as the owned checkout's target override. "
            "No longer used for a post-commit fast-forward -- that best-effort "
            "advance was retired (FR-008). Optional."
        ),
    ),
    json_output: bool = typer.Option(False, "--json", help="Output JSON."),
    owned_checkout: OwnedCheckoutOption = None,
) -> None:
    """Commit spec artifacts to the mission's resolved placement.

    SPEC is a primary/planning artifact: it lands on the mission's primary target
    branch for every topology. On an unprotected or flattened primary the commit
    is direct. On a PROTECTED primary the commit is refused (there is no fallback
    surface); recover by either creating/checking out a non-protected feature
    branch ('spec-kitty agent mission create --start-branch <feature-branch>') or
    setting SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS=1 to commit on the current
    branch.

    Pass individual FILES, not directories.
    """
    try:
        commit_message = join_message_paragraphs(message)
        repo_root = _current_repo_root()
        derived_slug = _mission_slug_from_args(files, mission)
        # Validate --owned-checkout (or adopt the caller's checkout) exactly once. A
        # refusal renders through emit_owned_refusal with this command's failure
        # envelope; the raw option value goes straight into the shared helper.
        owned = resolve_owned_or_refuse(
            repo_root,
            owned_checkout,
            derived_slug,
            cwd=Path.cwd(),
            allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES,
            json_output=json_output,
            envelope=_refusal_envelope,
            target_override=target_branch,
        )
        mission_slug, abs_files = _resolve_commit_inputs(repo_root, files, derived_slug, owned)
        _reject_directory_args(abs_files, json_output)
        if not mission_slug:
            _err(
                json_output,
                "Cannot resolve mission slug. Pass --mission <slug> or provide a kitty-specs/<slug>/ path as the first argument.",
            )
            raise typer.Exit(1)

        result = _commit_spec_files(repo_root, mission_slug, abs_files, commit_message, target_branch, owned)
        _render_spec_commit_result(result, json_output=json_output, abs_files=abs_files, repo_root=repo_root)

    except typer.Exit:
        raise
    except ActionContextError as exc:
        payload = {**_payload(success=False, error=str(exc)), "error_code": exc.code}
        if json_output:
            print(json.dumps(payload))
        else:
            console.print(f"[red]{exc.code}:[/red] {exc}")
        raise typer.Exit(1) from exc
    except (RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        payload = _payload(success=False, error=str(exc))
        if json_output:
            print(json.dumps(payload, indent=2))
        else:
            console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc


def _err(json_output: bool, message: str) -> None:
    if json_output:
        print(json.dumps(_payload(success=False, error=message), indent=2))
    else:
        console.print(f"[red]Error:[/red] {message}")
