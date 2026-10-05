"""Create-time roots: repository root, write root and current branch.

Moved verbatim from ``mission_creation.py`` (#5634). ``mission_creation`` re-exports
every name defined here. A call to a name tests patch on ``mission_creation``, or to a
function another ``mission_creation*`` module owns, goes through a lazy in-function
``from specify_cli.core import mission_creation as _mc`` import (never at module scope).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from specify_cli.core.git_ops import get_current_branch, has_unborn_head, is_git_repo
from specify_cli.core.owned_mission import OwnedCreateRoot
from specify_cli.core.paths import is_worktree_context, locate_project_root
from specify_cli.core.mission_creation_errors import MissionCreationError


@dataclass(frozen=True, slots=True)
class _CreateRoots:
    """Resolved roots + current branch for one ``create_mission_core`` call (T051).

    ``owned`` carries the caller-supplied, already-validated owned-checkout
    fact (WP02's :class:`OwnedCreateRoot`), or ``None`` for an unowned
    (repository root) create. Validation happens exactly once, in the
    caller that mints ``owned_create_root`` (FR-003 spirit); this function
    never re-validates a caller-supplied fact.
    """

    repository_root: Path
    write_root: Path
    owned: OwnedCreateRoot | None
    current_branch: str


def _resolve_create_roots(
    repo_root: Path | None,
    owned_create_root: OwnedCreateRoot | None,
    allow_worktree_context: bool,
) -> _CreateRoots:
    """Resolve the repository-root / write-root pair and validate context guards.

    Section 2 of the pre-decomposition body (FR-026 / T051; owned-checkout
    resolution re-expressed for FR-016 / T053, #5009 1f42f76ea; typed
    ``owned_create_root`` parameter T055): the worktree-context guard (skipped
    for an owned create, matching the pre-decomposition behaviour), the
    not-a-git-repo guard, the unborn-HEAD guard (checked against the WRITE
    root, since linked checkouts can have different HEAD states in the same
    repository), and the detached-HEAD guard. ``owned_create_root`` is minted
    ONCE by the caller through WP02's
    :func:`specify_cli.core.owned_mission.resolve_owned_create_root` -- which
    raises :class:`mission_runtime.ActionContextError` carrying the SAME error
    codes the pre-decomposition ``resolve_ownership_claim`` +
    ``error_for_claim`` call (a G1 floor offender) used to raise -- and is
    never re-validated here.
    """

    cwd = Path.cwd().resolve()
    resolved_root = repo_root

    if owned_create_root is None:
        if not allow_worktree_context and is_worktree_context(cwd):
            raise MissionCreationError("Cannot create missions from inside a worktree. Run from the project root checkout.")
        if resolved_root is None:
            resolved_root = locate_project_root()
    else:
        # HIGH-2 fix-cycle-1 regression repair: the already-validated fact is
        # the SINGLE source of the repository root on the owned path -- never
        # a caller-supplied `repo_root` left unresolved. Before this WP,
        # a supplied `repo_root` was `.resolve()`d before use; T055
        # accidentally left it as the caller's bare (possibly symlinked)
        # path when `repo_root` was not ``None``. Cross-check rather than
        # silently preferring one over the other: a caller-supplied
        # `repo_root` that resolves to a DIFFERENT path than the fact's own
        # `repository_root` is a caller bug (roots that disagree must never
        # be silently mixed) and fails closed.
        if resolved_root is not None and resolved_root.resolve() != owned_create_root.repository_root:
            raise MissionCreationError(
                f"Owned-create repository root mismatch: the supplied repo_root "
                f"({resolved_root.resolve()}) does not match the validated owned "
                f"checkout's repository root ({owned_create_root.repository_root})."
            )
        resolved_root = owned_create_root.repository_root

    if resolved_root is None:
        raise MissionCreationError("Could not locate project root. Run from within spec-kitty repository.")

    write_root = owned_create_root.checkout if owned_create_root is not None else resolved_root

    if not is_git_repo(resolved_root):
        raise MissionCreationError("Not in a git repository. Mission creation requires git.")
    # Every topology commits its scaffold. Inspect the selected write checkout:
    # linked checkouts can have different HEAD states in the same repository.
    if has_unborn_head(write_root):
        raise MissionCreationError(
            "This checkout has no commits yet, so Spec Kitty cannot commit the mission scaffold.\n\n"
            "Make an initial commit first, then create the mission:\n"
            "  git commit --allow-empty -m 'Initial commit'\n\n"
            "If the repository already has files staged, commit those instead."
        )

    current_branch = get_current_branch(write_root)
    if not current_branch or current_branch == "HEAD":
        raise MissionCreationError("Must be on a branch to create missions (detached HEAD detected).")

    return _CreateRoots(
        repository_root=resolved_root,
        write_root=write_root,
        owned=owned_create_root,
        current_branch=current_branch,
    )
