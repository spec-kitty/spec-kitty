"""create command family for ``agent mission`` (#2056 WP05).

Hosts the ``create`` command, decomposed from its pre-decomposition 281-LOC
monolith into ≤15-CC phase helpers: start-branch resolution, mission-type
selector resolution, the PR-bound branch-strategy gate, the core-creation
error funnel, the ``pr_bound`` meta write-back, and the JSON / human output
builders. Each phase helper is a small deterministic unit with focused tests
(``test_mission_create_phases.py``).

The command is defined here as a plain callable; ``mission`` registers it on its
Typer ``app`` and re-exports the name so ``mission.create_mission`` keeps
resolving — ``lifecycle.py`` binds ``agent.mission as agent_feature`` and calls
``agent_feature.create_mission``. To honor the established
``mission.locate_project_root`` / ``mission.get_current_branch`` patch targets
the command resolves those (and the relocated ``_switch_to_start_branch``)
through the ``mission`` module at call time.

One-way leaf (INV-8): imports lower layers + sibling Seam B/C leaves only, never
back into ``mission`` at module scope (the ``mission`` lookup inside the command
is a deferred, call-time import). Behavior is preserved byte-for-byte from the
pre-decomposition ``mission.py``; the WP01 golden harness is the regression net.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, NoReturn, cast

from mission_runtime import MissionTopology
from specify_cli.cli.console import console
import typer

from specify_cli.cli.commands._owned_checkout import OwnedCheckoutOption
from specify_cli.cli.selector_resolution import resolve_selector
from specify_cli.core.constants import MISSION_TYPE_DOCUMENTATION
from specify_cli.diagnostics import mark_invocation_succeeded
from specify_cli.git.ref_advance import RefRestoreError, restore_branch_ref

from specify_cli.cli.commands.agent.mission_branch_context import (
    _inject_branch_contract,
)
from specify_cli.cli.commands.agent.mission_parsing import _emit_json

if TYPE_CHECKING:
    from specify_cli.core.mission_creation import MissionCreationResult
    from specify_cli.core.owned_mission import OwnedCreateRoot


# ``--start-branch`` / ``--target-branch`` must name the same branch because
# mission creation stores exactly one planning branch.
START_TARGET_MISMATCH_MESSAGE = (
    "--start-branch and --target-branch must match because mission "
    "creation stores one planning branch. Omit --target-branch for "
    "the recommended PR-bound feature-branch flow."
)


@dataclass(frozen=True)
class _StartBranchRollbackState:
    """Git state captured before ``--start-branch`` changes the checkout."""

    repo_root: Path
    start_branch: str
    start_branch_preexisted: bool
    start_branch_original_commit: str | None
    original_branch: str | None
    original_commit: str
    original_index_tree: str | None


def _capture_start_branch_rollback_state(
    repo_root: Path | None,
    start_branch: str | None,
) -> _StartBranchRollbackState | None:
    """Capture enough state to undo a failed early-create branch switch."""
    if repo_root is None or start_branch is None:
        return None

    normalized_start_branch = start_branch.strip()
    if not normalized_start_branch:
        return None

    try:
        original_commit = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        original_index_result = subprocess.run(
            ["git", "-C", str(repo_root), "write-tree"],
            capture_output=True,
            text=True,
            check=False,
        )
        branch_result = subprocess.run(
            ["git", "-C", str(repo_root), "symbolic-ref", "--quiet", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        start_branch_result = subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                "show-ref",
                "--verify",
                "--quiet",
                f"refs/heads/{normalized_start_branch}",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        start_branch_commit_result = subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                "rev-parse",
                "--verify",
                f"refs/heads/{normalized_start_branch}",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.CalledProcessError):
        # Preserve the established structured error path when the checkout is
        # not a usable git repository; the branch-switch phase reports it.
        return None

    return _StartBranchRollbackState(
        repo_root=repo_root,
        start_branch=normalized_start_branch,
        start_branch_preexisted=start_branch_result.returncode == 0,
        start_branch_original_commit=(start_branch_commit_result.stdout.strip() if start_branch_commit_result.returncode == 0 else None),
        original_branch=branch_result.stdout.strip() if branch_result.returncode == 0 else None,
        original_commit=original_commit,
        original_index_tree=(original_index_result.stdout.strip() if original_index_result.returncode == 0 else None),
    )


def _restore_start_branch_after_failure(state: _StartBranchRollbackState) -> None:
    """Restore the original checkout and delete only a newly created branch."""
    restore_args = ["switch", state.original_branch] if state.original_branch is not None else ["switch", "--detach", state.original_commit]
    subprocess.run(
        ["git", "-C", str(state.repo_root), *restore_args],
        capture_output=True,
        text=True,
        check=True,
    )

    if state.start_branch_preexisted:
        original_tip = state.start_branch_original_commit
        if original_tip is not None:
            current_tip_result = subprocess.run(
                [
                    "git",
                    "-C",
                    str(state.repo_root),
                    "rev-parse",
                    "--verify",
                    f"refs/heads/{state.start_branch}",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            current_tip = current_tip_result.stdout.strip()
            if current_tip != original_tip:
                restore_branch_ref(
                    state.repo_root,
                    state.start_branch,
                    original_tip,
                    expected_current_sha=current_tip,
                )
    elif state.start_branch != state.original_branch:
        branch_result = subprocess.run(
            [
                "git",
                "-C",
                str(state.repo_root),
                "show-ref",
                "--verify",
                "--quiet",
                f"refs/heads/{state.start_branch}",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if branch_result.returncode == 0:
            subprocess.run(
                ["git", "-C", str(state.repo_root), "branch", "-D", state.start_branch],
                capture_output=True,
                text=True,
                check=True,
            )

    if state.original_index_tree is not None:
        subprocess.run(
            ["git", "-C", str(state.repo_root), "read-tree", state.original_index_tree],
            capture_output=True,
            text=True,
            check=True,
        )


@contextmanager
def _rollback_start_branch_on_failure(
    repo_root: Path | None,
    start_branch: str | None,
) -> Iterator[None]:
    """Make ``--start-branch`` failure-atomic across the CLI pre-core phases."""
    state = _capture_start_branch_rollback_state(repo_root, start_branch)
    try:
        yield
    except BaseException as error:
        if state is not None:
            try:
                _restore_start_branch_after_failure(state)
            except (OSError, subprocess.CalledProcessError, RefRestoreError) as rollback_error:
                error.add_note(f"Failed to restore checkout after create failure: {rollback_error}")
        raise


def _resolve_start_branch_phase(
    *,
    repo_root: Path | None,
    start_branch: str | None,
    target_branch: str | None,
    json_output: bool,
) -> None:
    """Validate start/target branch coherence and switch to ``--start-branch``.

    No-op when ``--start-branch`` is omitted. Exits 1 with a structured payload
    on a start/target mismatch or a branch-switch failure. The branch switch
    routes through ``mission._switch_to_start_branch`` to preserve the historical
    monkeypatch seam.
    """
    if start_branch is None:
        return

    from specify_cli.cli.commands.agent import mission as _mission

    normalized_start_branch = start_branch.strip()
    normalized_target_branch = target_branch.strip() if target_branch else None
    if normalized_target_branch and normalized_target_branch != normalized_start_branch:
        if json_output:
            _emit_json(
                {
                    "error_code": "START_BRANCH_TARGET_MISMATCH",
                    "error": START_TARGET_MISMATCH_MESSAGE,
                    "start_branch": start_branch,
                    "target_branch": target_branch,
                }
            )
        else:
            console.print(f"[bold red]Error:[/bold red] {START_TARGET_MISMATCH_MESSAGE}")
        raise typer.Exit(1)

    try:
        _mission._switch_to_start_branch(repo_root, start_branch)
    except Exception as exc:
        if json_output:
            _emit_json(
                {
                    "error_code": "START_BRANCH_FAILED",
                    "error": str(exc),
                    "start_branch": start_branch,
                }
            )
        else:
            console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1) from exc


def _resolve_mission_type_phase(
    *,
    mission_type: str | None,
    mission: str | None,
    json_output: bool,
) -> str | None:
    """Resolve the canonical mission type from the ``--mission-type``/``--mission`` pair.

    Returns the resolved mission type (``mission_type`` unchanged when neither
    flag is supplied). Exits 1 on a selector conflict.
    """
    if mission_type is None and mission is None:
        return mission_type
    try:
        resolved = resolve_selector(
            canonical_value=mission_type,
            canonical_flag="--mission-type",
            alias_value=mission,
            alias_flag="--mission",
            suppress_env_var="SPEC_KITTY_SUPPRESS_MISSION_TYPE_DEPRECATION",
            command_hint="--mission-type <name>",
        )
        return cast("str | None", resolved.canonical_value)
    except typer.BadParameter as exc:
        if json_output:
            _emit_json({"error": str(exc)})
        else:
            console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1) from exc


def _enforce_branch_strategy_gate_phase(
    *,
    pr_bound: bool,
    current_branch: str | None,
    target_branch: str | None,
    branch_strategy: str | None,
    start_branch: str | None,
    json_output: bool,
) -> None:
    """Run the FR-033 PR-bound branch-strategy gate (WP07/T040).

    When the mission is PR-bound and the operator is on the merge target branch,
    prompt for confirmation unless ``--branch-strategy already-confirmed`` is
    supplied. Exits 1 when confirmation is required in ``--json`` mode or the
    operator declines the interactive prompt.
    """
    from specify_cli.cli.commands._branch_strategy_gate import (
        ALREADY_CONFIRMED,
        BranchStrategyGateError,
        evaluate_branch_strategy,
    )

    effective_merge_target = target_branch or current_branch
    gate_branch_strategy = branch_strategy or (ALREADY_CONFIRMED if start_branch is not None else None)
    try:
        gate_outcome = evaluate_branch_strategy(
            pr_bound=pr_bound,
            current_branch=current_branch,
            merge_target_branch=effective_merge_target,
            branch_strategy=gate_branch_strategy,
            prompt=None if json_output else lambda message: typer.confirm(message, default=False),
        )
    except BranchStrategyGateError as exc:
        if json_output:
            _emit_json(
                {
                    "error_code": "BRANCH_STRATEGY_CONFIRMATION_REQUIRED",
                    "error": ("PR-bound mission creation requires explicit branch-strategy confirmation in --json mode."),
                    "branch_strategy_gate": "confirmation_required",
                    "current_branch": current_branch,
                    "merge_target_branch": effective_merge_target,
                    "remediation": "Pass `--branch-strategy already-confirmed` or run without --json to confirm interactively.",
                }
            )
        else:
            console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1) from exc

    if gate_outcome.prompted and not gate_outcome.decision.proceed:
        message = "Mission creation aborted by operator at branch-strategy gate. Switch to a topic branch or pass `--branch-strategy already-confirmed`."
        if json_output:
            _emit_json({"error": message, "branch_strategy_gate": "aborted"})
        else:
            console.print(f"[yellow]Aborted:[/yellow] {message}")
        raise typer.Exit(1)


def _resolve_default_topology_phase(
    *,
    explicit_topology: MissionTopology | None,
    repo_root: Path | None,
    current_branch: str | None,
    pr_bound: bool,
    owned_create_root: OwnedCreateRoot | None = None,
) -> MissionTopology:
    """Derive the create-time topology default from branch/pr-bound context (#2581, #2533, #2602).

    ``single_branch`` is explicit-only (binding decision on #5100, comment
    5870360497): it is produced ONLY by an explicit ``--topology
    single_branch`` or by ``--owned-checkout`` — never as an implicit
    default. Every other implicit arm below resolves to either ``coord`` or
    ``lanes``, so default users on the ordinary create path keep worktree
    isolation (US4/FR-013).

    - An explicit ``--topology`` always wins.
    - ``--owned-checkout`` is itself an explicit request for an isolated,
      operator-managed write surface (ADR 2026-09-03-1: owned mode supports
      ``single_branch`` only), so it also wins outright — before any
      branch/pr-bound context is consulted. This is a genuine BEHAVIOUR
      CHANGE, not a preservation of prior implicit routing: an owned
      checkout with no configured ``origin`` has no protection/reachability
      signal of its own, so ``resolve_primary_branch`` falls back to
      reading the checkout's OWN current branch — making
      ``current_branch == primary_branch`` true for that checkout
      regardless of which branch it is on. Pre-WP06 that fallback quirk
      routed a real owned-checkout create with no ``--topology`` to the
      *primary-branch* ``coord`` arm, never to the non-primary arm's
      (then-implicit) ``single_branch`` (#5100 review cycle 1, nit 3).
    - Otherwise the default keys on *topology honesty* (INV-2): a
      coordination topology is minted only when coordination routing is
      actually reachable, never as pure overhead.
    - ``--pr-bound`` missions consult :func:`coord_topology_reachable` — coord
      is reachable iff ``primary_protected or current_is_primary``. A pr-bound
      mission on an **unprotected** primary target (e.g. created with
      ``--start-branch <topic-branch>``) therefore defaults to ``lanes``,
      eliminating the stranded coord branch behind the #2533 split-brain
      without falling back to the no-longer-implicit ``single_branch``.
      Protection is keyed on the **primary TARGET branch** (``ProtectionPolicy``
      + ``resolve_primary_branch``), NOT the current checkout (the tripwire in
      ``test_mission_create.py`` proves this).
    - A non-pr-bound mission created on the repository's primary branch keeps the
      historical ``coord`` default; one created on a non-primary feature/fork
      branch defaults to ``lanes`` — minting a coordination branch there just
      to have the operator manually flatten it is the friction #2581 closed,
      and #2602 keeps that friction closed via worktree isolation rather than
      an implicit ``single_branch``.
    """
    if explicit_topology is not None:
        return explicit_topology
    if owned_create_root is not None:
        return MissionTopology.SINGLE_BRANCH
    # Fail-safe: without a resolvable repo/checkout we cannot key on target
    # protection, so keep the historical ``coord`` default. Hoisted ahead of the
    # pr-bound arm because that arm now needs a resolvable ``repo_root`` to read
    # the primary target branch's protection.
    if repo_root is None or current_branch is None:
        return MissionTopology.COORD

    from specify_cli.core.git_ops import resolve_primary_branch

    primary_branch = resolve_primary_branch(repo_root)
    if pr_bound:
        from specify_cli.coordination.surface_authority import coord_topology_reachable
        from specify_cli.git.protection_policy import ProtectionPolicy

        primary_protected = ProtectionPolicy.resolve(repo_root).is_protected(primary_branch)
        current_is_primary = current_branch == primary_branch
        return MissionTopology.COORD if coord_topology_reachable(pr_bound, primary_protected, current_is_primary) else MissionTopology.LANES
    if current_branch == primary_branch:
        return MissionTopology.COORD
    return MissionTopology.LANES


def _print_worktree_navigation_hint(mission_slug: str, error_msg: str) -> None:
    """Print the 'run from main repo' hint when a worktree error blocked creation."""
    if "worktree" not in error_msg.lower():
        return
    # Route through the ``mission`` module so the ``mission.locate_project_root``
    # patch seam keeps reaching this branch after relocation.
    from specify_cli.cli.commands.agent import mission as _mission

    cwd = Path.cwd().resolve()
    main_repo = _mission.locate_project_root(cwd)
    if main_repo is None:
        # Fallback: try .worktrees path heuristic.
        for i, part in enumerate(cwd.parts):
            if part == ".worktrees":
                main_repo = Path(*cwd.parts[:i])
                break
    if main_repo is not None:
        console.print("\n[cyan]Run from the main repository instead:[/cyan]")
        console.print(f"  cd {main_repo}")
        console.print(f"  spec-kitty agent mission create {mission_slug}")


def _emit_create_core_error_and_exit(
    exc: Exception,
    *,
    mission_slug: str,
    json_output: bool,
) -> NoReturn:
    """Classify a ``create_mission_core`` failure and emit its CLI payload.

    MEDIUM-6 fix-cycle-1 extraction: the error-classification logic used to
    live as five ``except`` clauses directly in ``_run_create_core_phase``,
    which pushed that function's complexity from 12 to 14 once T055 touched
    its body. Extracted here (a single ``isinstance`` dispatch, still one
    branch per documented failure class) so the caller's own try/except goes
    back to a single generic ``except Exception`` -- unchanged behaviour,
    lower complexity at the call site.

    Exits 1 (with the appropriate structured payload) on the four documented
    failure classes: an owned-checkout claim refusal (typed error code),
    coordination-branch divergence (NFR-007 stable error_code), a
    ``MissionCreationError`` (with worktree navigation hint), or any other
    unexpected exception.
    """
    from charter.activation.pack_context import CharterPackConfigError
    from mission_runtime import ActionContextError
    from specify_cli.core.mission_creation import MissionCreationError
    from specify_cli.missions._create import CoordinationBranchDiverged

    if isinstance(exc, CoordinationBranchDiverged):
        # Structured error path (NFR-007): emit a stable error_code payload
        # so scripted callers (CI, doctor) can detect this case unambiguously.
        if json_output:
            _emit_json({"error": str(exc), **exc.to_dict()})
        else:
            console.print(f"[bold red]Error:[/bold red] {exc}")
    elif isinstance(exc, ActionContextError):
        # MEDIUM-5 fix-cycle-1: the former `except CheckoutOwnershipError`
        # arm was dead code after T053 -- create_mission_core no longer calls
        # error_for_claim (resolve_owned_create_root converts every claim
        # refusal to this single ActionContextError type instead), so it was
        # deleted rather than kept unreachable. This branch carries the SAME
        # registered error codes (including OWNED_CHECKOUT_IS_REPOSITORY_ROOT)
        # the old CheckoutOwnershipError branch handled, so the --json
        # envelope is unchanged.
        error_msg = str(exc)
        if json_output:
            # Shared ownership refusal contract (mirrors
            # _owned_checkout.emit_owned_refusal): exactly
            # {success, error_code, error} — no redundant `message` key from
            # StructuredError.to_dict().
            _emit_json(
                {
                    "success": False,
                    "error_code": exc.code,
                    "error": error_msg,
                }
            )
        else:
            console.print(f"[bold red]Error:[/bold red] {error_msg}")
    elif isinstance(exc, MissionCreationError):
        error_msg = str(exc)
        if json_output:
            # #3861: carry the delegate's TYPED failure reason (e.g.
            # ``MissionAlreadyExistsError.error_code``) into the --json
            # envelope so scripted callers (the orchestrator-api ``specify``
            # verb) classify on the structured code, never on message prose.
            error_payload: dict[str, object] = {"error": error_msg}
            if exc.error_code is not None:
                error_payload["error_code"] = exc.error_code
            _emit_json(error_payload)
        else:
            console.print(f"[bold red]Error:[/bold red] {error_msg}")
            _print_worktree_navigation_hint(mission_slug, error_msg)
    elif isinstance(exc, CharterPackConfigError):
        # FR-010 (#3337): the fail-closed charter-pack gate raises a
        # ``KittyInternalConsistencyError`` whose ``str(exc)`` is only the
        # stable ``.code`` — the actionable remediation lives on ``.body``. The
        # generic branch below would emit ``{"error": "<CODE>"}`` and drop the
        # remediation entirely, so carry both the code and the body into the
        # --json envelope for scripted callers.
        if json_output:
            _emit_json(
                {
                    "error_code": exc.code,
                    "error": exc.body,
                    "remediation": exc.body,
                }
            )
        else:
            console.print(f"[bold red]Error:[/bold red] {exc.body}")
    else:
        if json_output:
            _emit_json({"error": str(exc)})
        else:
            console.print(f"[red]Error:[/red] {exc}")
    raise typer.Exit(1) from exc


def _mint_owned_create_root(
    repo_root: Path | None,
    owned_checkout: OwnedCheckoutOption,
    *,
    mission_slug: str,
    json_output: bool,
) -> OwnedCreateRoot | None:
    """Mint the owned-checkout fact ONCE, before ANY git operation (fix-cycle-2 HIGH).

    Review cycle 2's fail-open: pre-fix, ``create_mission`` computed
    ``command_checkout = owned_checkout.resolve()`` straight from the RAW,
    UNVALIDATED ``--owned-checkout`` claim, then ran
    ``_rollback_start_branch_on_failure`` / ``_resolve_start_branch_phase``
    (which calls ``_switch_to_start_branch``) / ``get_current_branch`` /
    ``_resolve_default_topology_phase`` against it -- git mutations (a branch
    switch) of a checkout the validator would go on to REFUSE (the
    repository root itself, or a foreign repository entirely), landing before
    validation ever ran. This function is called FIRST in ``create_mission``,
    before any of those phases, so a claim is validated -- or refused -- before
    a single git command touches the claimed path.

    Returns ``None`` when no claim was given (``owned_checkout is None``).
    With a claim: fails closed with the SAME typed ``MissionCreationError``
    the unowned-create path uses when ``repo_root`` could not be located
    (HIGH-3 fix-cycle-1); otherwise mints via WP02's
    :func:`specify_cli.core.owned_mission.resolve_owned_create_root`. Any
    failure (either raise) is routed through
    :func:`_emit_create_core_error_and_exit`, so the ``--json`` envelope is
    byte-identical to the funnel's own classification of the same errors.
    """
    if owned_checkout is None:
        return None

    from specify_cli.core.mission_creation import MissionCreationError
    from specify_cli.core.owned_mission import resolve_owned_create_root

    if repo_root is None:
        _emit_create_core_error_and_exit(
            MissionCreationError("Could not locate project root. Run from within spec-kitty repository."),
            mission_slug=mission_slug,
            json_output=json_output,
        )
    try:
        return resolve_owned_create_root(repo_root, owned_checkout)
    except Exception as exc:  # classified and re-raised as typer.Exit by the helper below
        _emit_create_core_error_and_exit(exc, mission_slug=mission_slug, json_output=json_output)


def _run_create_core_phase(
    *,
    repo_root: Path | None,
    mission_slug: str,
    resolved_mission_type: str | None,
    target_branch: str | None,
    friendly_name: str | None,
    purpose_tldr: str | None,
    purpose_context: str | None,
    pr_bound: bool,
    force_recreate_coordination_branch: bool,
    owned_create_root: OwnedCreateRoot | None = None,
    json_output: bool,
    topology: MissionTopology = MissionTopology.COORD,
    retain_branches: bool = False,
    retain_worktrees: bool = False,
    commit_to_target: bool = False,
    allow_duplicate: bool = False,
) -> MissionCreationResult:
    """Invoke ``create_mission_core`` with the deterministic error funnel.

    ``owned_create_root`` is the already-validated owned-checkout fact
    (fix-cycle-2 HIGH: minted ONCE by :func:`_mint_owned_create_root`, at the
    very top of ``create_mission``, before any git operation the command's
    earlier phases perform -- never re-validated here). ``None`` means an
    unowned (repository root) create.

    Exits 1 (with the appropriate structured payload) on the three documented
    failure classes: coordination-branch divergence (NFR-007 stable
    error_code), a ``MissionCreationError`` (with worktree navigation hint),
    or any other unexpected exception. See :func:`_emit_create_core_error_and_exit`.
    """
    from specify_cli.core.mission_creation import create_mission_core

    try:
        return create_mission_core(
            repo_root=repo_root,
            mission_slug=mission_slug,
            mission=resolved_mission_type,
            target_branch=target_branch,
            friendly_name=friendly_name,
            purpose_tldr=purpose_tldr,
            purpose_context=purpose_context,
            pr_bound=pr_bound,
            topology=topology,
            force_recreate_coordination_branch=force_recreate_coordination_branch,
            owned_create_root=owned_create_root,
            retain_branches=retain_branches,
            retain_worktrees=retain_worktrees,
            commit_to_target=commit_to_target,
            allow_duplicate=allow_duplicate,
        )
    except Exception as exc:
        _emit_create_core_error_and_exit(exc, mission_slug=mission_slug, json_output=json_output)


def _build_create_payload(result: MissionCreationResult) -> dict[str, object]:
    """Build the ``--json`` success payload (pre-branch-contract enrichment)."""
    feature_dir = result.feature_dir
    spec_file = feature_dir / "spec.md"
    meta_file = feature_dir / "meta.json"
    payload: dict[str, object] = {
        "result": "success",
        "mission_slug": result.mission_slug,
        "mission_number": result.mission_number,
        "mission_id": str(result.meta.get("mission_id", "")),
        # rc3 M5 (FR-002): echo the canonical field only — the legacy `mission`
        # echo is retired (a just-created mission always carries `mission_type`).
        "mission_type": str(result.meta.get("mission_type", "")),
        "slug": str(result.meta.get("slug", "")),
        "friendly_name": str(result.meta.get("friendly_name", "")),
        "purpose_tldr": str(result.meta.get("purpose_tldr", "")),
        "purpose_context": str(result.meta.get("purpose_context", "")),
        "mission_dir": str(feature_dir),
        "feature_dir": str(feature_dir),  # legacy alias of mission_dir (#5206)
        "spec_file": str(spec_file),
        "meta_file": str(meta_file),
        "created_at": str(result.meta.get("created_at", "")),
        "created_files": [str(path) for path in result.created_files],
        # #5100 FR-007/FR-008 (WP08): the protected-target single_branch mint,
        # when it fired, or the explicit `commit_to_target` override, when
        # set. `None` for every other mission (never a written empty string).
        "mission_branch": result.meta.get("mission_branch"),
        "commit_to_target": result.meta.get("commit_to_target"),
        # #2693: spec.md is scaffolded empty and left uncommitted on purpose
        # (#846) — it is committed later by /spec-kitty.specify once it holds
        # substantive content. Disclose it as a structured uncommitted artifact
        # (with the command responsible for committing it) so a generated file
        # is never both untracked in the working tree AND undisclosed to the
        # caller. meta.json, status.events.jsonl, and the tasks/ scaffold are
        # committed transactionally at create time, so they are NOT listed here.
        "uncommitted_artifacts": [
            {
                "path": str(path),
                "reason": (
                    "Scaffolded empty at create time; populated and committed with substantive content later (#846)."
                    if path == spec_file
                    else "Generated scaffold could not be committed to the protected or unavailable target branch."
                ),
                "responsible_command": ("/spec-kitty.specify" if path == spec_file else "commit from a non-protected topic branch"),
            }
            for path in result.uncommitted_files
        ],
        "write_mode": "update_existing_files",
        "scaffold_only": True,
        "requires_agent_authoring": True,
        "plan_guard": "SPEC_NOT_SUBSTANTIVE_OR_UNCOMMITTED",
        "next_step": ("Created scaffold only. Run `/spec-kitty.specify <intent>` in your agent or edit and commit spec_file before `spec-kitty plan`."),
        "origin_binding": {
            "attempted": result.origin_binding_attempted,
            "succeeded": result.origin_binding_succeeded,
            "error": result.origin_binding_error,
        },
        # Coordination branch (WP03 / issue #1348) — top-level field so
        # downstream tooling (lane allocator, BookkeepingTransaction, merge)
        # can read the canonical ref without re-deriving it.
        "coordination_branch": getattr(result, "coordination_branch", None),
        "coordination_branch_created": getattr(result, "coordination_branch_created", False),
        # Mission topology (WP03 / #2218) — the operator's create-time shape,
        # surfaced so `specify --json` callers can read it without re-deriving.
        "topology": str(result.meta.get("topology", "")),
    }
    if result.owned_checkout is not None:
        # Serialized key stays byte-identical (occurrence_map serialized_keys:
        # do_not_change): "owned_checkout", holding the owned checkout path.
        payload["owned_checkout"] = str(result.owned_checkout.checkout)
        payload["canonical_repo_root"] = str(result.canonical_repo_root)
    return payload


def _minted_mission_branch(result: MissionCreationResult) -> str | None:
    """The protected-target mission branch the create left checked out, if one was minted."""
    minted = result.meta.get("mission_branch")
    return minted if isinstance(minted, str) and minted else None


def _print_branch_line(result: MissionCreationResult, mission_branch: str | None) -> None:
    """Human ``Branch:`` line -- the minted mission branch when create switched onto one."""
    if mission_branch:
        console.print(f"[bold cyan]Branch:[/bold cyan] {mission_branch} (mission branch; merges into {result.target_branch})")
    else:
        console.print(f"[bold cyan]Branch:[/bold cyan] {result.target_branch} (target for this mission)")


def _print_meta_outcome(result: MissionCreationResult, mission_branch: str | None) -> None:
    """Report where ``meta.json`` landed (or that it did not), naming the real branch."""
    landed_branch = mission_branch or result.target_branch
    meta_committed = (result.feature_dir / "meta.json") not in result.uncommitted_files
    if mission_branch:
        suffix = "; meta committed there" if meta_committed else ""
        console.print(f"   Switched checkout to {mission_branch} (was {result.current_branch}){suffix}")
    if meta_committed:
        tail = "spec.md scaffold left untracked" if mission_branch else f"Meta committed to {result.target_branch}; spec.md scaffold left untracked"
        console.print(f"   {tail}")
        return
    console.print(
        f"   [yellow]Meta not committed:[/yellow] the scaffold commit to "
        f"{landed_branch} was refused (protected or unavailable target "
        f"branch); kitty-specs/{result.mission_slug}/ is left on disk, untracked"
    )
    console.print(
        "   Planning artifacts must land on a topic branch, or land via the mission lane worktree "
        "— switch to a topic branch first, or re-run 'agent mission create --start-branch <topic-branch>'."
    )


def _emit_create_result_phase(
    result: MissionCreationResult,
    *,
    resolved_mission_type: str | None,
    json_output: bool,
) -> None:
    """Emit the create result in JSON or human form (output stays in the CLI layer)."""
    mission_branch = _minted_mission_branch(result)
    if not json_output:
        _print_branch_line(result, mission_branch)
        if resolved_mission_type == MISSION_TYPE_DOCUMENTATION:
            console.print("[cyan]→ Documentation state initialized in meta.json[/cyan]")

    if json_output:
        _emit_json(
            _inject_branch_contract(
                _build_create_payload(result),
                target_branch=result.target_branch,
                # A minted mission branch is the real checkout after create
                # (``result.current_branch`` is the pre-mint branch), so the
                # contract describes it, not the protected merge target.
                current_branch=mission_branch or result.current_branch,
                expected_checkout_branch=mission_branch,
            )
        )
        # FR-008: signal atexit handlers that this invocation succeeded so
        # post-success shutdown warnings (sync/runtime stop) are silenced.
        # Scoped intentionally to the JSON success path of `agent mission
        # create`; auditing other JSON-emitting commands is OUT OF SCOPE
        # for WP06 (see contracts/mission_create_clean_output.contract.md).
        mark_invocation_succeeded()
    else:
        console.print(f"[green]✓[/green] Mission created: {result.mission_slug}")
        console.print(f"   Title: {result.meta.get('friendly_name', '')}")
        console.print(f"   TLDR: {result.meta.get('purpose_tldr', '')}")
        console.print(f"   Context: {result.meta.get('purpose_context', '')}")
        console.print(f"   Directory: {result.feature_dir}")
        # Issue #846: spec.md is no longer auto-committed at create time.
        # The agent commits it from /spec-kitty.specify after writing substantive content.
        # Issue #4608: the meta line must report what actually landed. When the
        # transactional scaffold commit was refused (protected or unavailable
        # target branch), meta.json sits in ``result.uncommitted_files`` — the
        # same evidence the ``--json`` envelope discloses via
        # ``uncommitted_artifacts`` — and claiming a commit would be false.
        _print_meta_outcome(result, mission_branch)
        console.print("   [yellow]Scaffold only:[/yellow] run [cyan]/spec-kitty.specify <intent>[/cyan] in your agent, or edit and commit spec.md before planning.")


def create_mission(
    mission_slug: Annotated[str, typer.Argument(help="Mission slug (e.g., 'user-auth')")],
    mission_type: Annotated[
        str | None,
        typer.Option("--mission-type", help="Mission type (e.g., 'documentation', 'software-dev')"),
    ] = None,
    mission: Annotated[
        str | None,
        typer.Option("--mission", hidden=True, help="(deprecated) Use --mission-type"),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output JSON format")] = False,
    target_branch: Annotated[str | None, typer.Option("--target-branch", help="Target branch (defaults to current branch)")] = None,
    friendly_name: Annotated[str | None, typer.Option("--friendly-name", help="Human-friendly mission title")] = None,
    purpose_tldr: Annotated[str | None, typer.Option("--purpose-tldr", help="One-line stakeholder TLDR for the mission")] = None,
    purpose_context: Annotated[str | None, typer.Option("--purpose-context", help="Short stakeholder-facing paragraph for the mission")] = None,
    pr_bound: Annotated[bool, typer.Option("--pr-bound/--no-pr-bound", help="Mark mission as PR-bound (gate fires on merge_target_branch)")] = False,
    topology: Annotated[
        MissionTopology | None,
        typer.Option(
            "--topology",
            help=(
                "Create-time mission shape: single_branch | lanes | coord | "
                "lanes_with_coord. Coordination-bearing shapes (coord, "
                "lanes_with_coord) mint a coordination branch and "
                "materialize its worktree immediately, seeding it with the "
                "mission's creation events (MissionCreated, SpecifyStarted) "
                "so the coordination surface is live from birth (#5440); "
                "branch-flat shapes (single_branch, lanes) do neither. "
                "Default: context-derived (#2581, #2602) — coord on the "
                "primary branch or with --pr-bound when coordination is "
                "reachable; lanes otherwise. single_branch only when "
                "requested explicitly (or via --owned-checkout)."
            ),
        ),
    ] = None,
    branch_strategy: Annotated[
        str | None,
        typer.Option(
            "--branch-strategy",
            help="Branch-strategy gate control (e.g., 'already-confirmed' to bypass the prompt)",
        ),
    ] = None,
    start_branch: Annotated[
        str | None,
        typer.Option(
            "--start-branch",
            help="Create or switch to this branch before mission files are written",
        ),
    ] = None,
    force_recreate_coordination_branch: Annotated[
        bool,
        typer.Option(
            "--force-recreate-coordination-branch",
            help=(
                "Delete and recreate the per-mission coordination branch if it "
                "already exists and has diverged from the target. Operator "
                "escape hatch; never used by automation."
            ),
        ),
    ] = False,
    owned_checkout: OwnedCheckoutOption = None,
    retain_branches: Annotated[
        bool,
        typer.Option(
            "--retain-branches",
            help="Opt this mission's branches out of post-merge cleanup deletion.",
        ),
    ] = False,
    retain_worktrees: Annotated[
        bool,
        typer.Option(
            "--retain-worktrees",
            help="Opt this mission's worktrees out of post-merge cleanup deletion.",
        ),
    ] = False,
    commit_to_target: Annotated[
        bool,
        typer.Option(
            "--commit-to-target/--no-commit-to-target",
            help=(
                "single_branch only: skip the protected-target mission-branch "
                "mint (#5100 FR-008) and commit directly onto --target-branch, "
                "even when it is protected. Persisted; honoured through "
                "ProtectionPolicy for every later write."
            ),
        ),
    ] = False,
    allow_duplicate: Annotated[
        bool,
        typer.Option(
            "--allow-duplicate",
            "--allow-dup",
            help=(
                "Escape hatch for the idempotency guard (#4033): create a "
                "second mission even though a LIVE prior mission shares this "
                "slug and mission type. Abandoned priors (canceled, genesis, "
                "or spec never committed) never need this flag."
            ),
        ),
    ] = False,
) -> None:
    """Create new mission directory structure in the project root checkout.

    This command is designed for AI agents to call programmatically.
    Creates mission directory in kitty-specs/ and commits to the current branch.

    Examples:
        spec-kitty agent mission create "new-dashboard" --json
    """
    # Deferred import keeps this leaf free of an import cycle while honoring the
    # ``mission.locate_project_root`` / ``mission.get_current_branch`` /
    # ``mission._switch_to_start_branch`` patch targets the tests rely on.
    from specify_cli.cli.commands.agent import mission as _mission

    repo_root = _mission.locate_project_root()
    # fix-cycle-2 HIGH: mint the owned-checkout fact ONCE, here, before any of
    # the phases below run a git operation against it (start-branch switch,
    # get_current_branch, topology derivation). None when no claim was given.
    owned_create_root = _mint_owned_create_root(repo_root, owned_checkout, mission_slug=mission_slug, json_output=json_output)
    command_checkout = owned_create_root.checkout if owned_create_root is not None else repo_root

    with _rollback_start_branch_on_failure(command_checkout, start_branch):
        _resolve_start_branch_phase(
            repo_root=command_checkout,
            start_branch=start_branch,
            target_branch=target_branch,
            json_output=json_output,
        )

        resolved_mission_type = _resolve_mission_type_phase(
            mission_type=mission_type,
            mission=mission,
            json_output=json_output,
        )

        current_branch = _mission.get_current_branch(command_checkout)
        _enforce_branch_strategy_gate_phase(
            pr_bound=pr_bound,
            current_branch=current_branch,
            target_branch=target_branch,
            branch_strategy=branch_strategy,
            start_branch=start_branch,
            json_output=json_output,
        )

        resolved_topology = _resolve_default_topology_phase(
            explicit_topology=topology,
            repo_root=command_checkout,
            current_branch=current_branch,
            pr_bound=pr_bound,
            owned_create_root=owned_create_root,
        )

        # Import the tracker package here (NOT at module scope) so ``tracker/__init__.py``
        # registers ``consume_pending_origin_impl`` with ``core.adapters`` BEFORE
        # ``create_mission_core`` runs ``consume_pending_origin`` (register-before-use,
        # T012). Keeping this import inside the command body — rather than at module
        # scope — keeps the whole tracker/sync/SaaS stack off the CLI cold-start path
        # (NFR-003), while preserving the CLI-layer placement so no CORE→INTEGRATION
        # import edge is introduced in ``core/mission_creation.py`` (#614 leak fix).
        import specify_cli.tracker  # noqa: F401  (import side-effect: origin-consumer registration)

        result = _run_create_core_phase(
            repo_root=repo_root,
            mission_slug=mission_slug,
            resolved_mission_type=resolved_mission_type,
            target_branch=target_branch,
            friendly_name=friendly_name,
            purpose_tldr=purpose_tldr,
            purpose_context=purpose_context,
            pr_bound=pr_bound,
            topology=resolved_topology,
            force_recreate_coordination_branch=force_recreate_coordination_branch,
            owned_create_root=owned_create_root,
            json_output=json_output,
            retain_branches=retain_branches,
            retain_worktrees=retain_worktrees,
            commit_to_target=commit_to_target,
            allow_duplicate=allow_duplicate,
        )
    _emit_create_result_phase(
        result,
        resolved_mission_type=resolved_mission_type,
        json_output=json_output,
    )
