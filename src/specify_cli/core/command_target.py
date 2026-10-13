"""Declaration-first command repo_root/branch resolution entry (#6142, Increment 1).

ADR ``docs/adr/4.x/2026-10-10-1-scoped-shadow-workspace-write-boundary-layers-onto-the-partition.md``
(Option B, Increment 1). This module is the ONE typed producer of a mission-scoped
command's ``(repo_root, target_branch)`` target. It exists so that the Mission's **stored
declaration** -- not ambient location (the current working directory, the invoking
worktree, or the checked-out HEAD) -- is the source of truth for a command's write/read
target, and so that a newly-added mutating command obtains that target by calling one
typed entry rather than re-deriving it from ambient location and re-copying the
"never ``Path.cwd()``" folklore by hand.

Terminology (named explicitly per the ADR and the CLAUDE.md footguns):

* ``primary`` here means the PRIMARY partition / repository-root checkout -- **never** the
  Primary Branch ``main`` unless ``main`` is the actual resolved branch.
* ``merge`` means lane consolidation / branch integration -- this module performs
  **neither**; it only resolves a target, it does not integrate or publish.
* ``routing`` means branch-target routing (which branch/checkout a write lands on) and
  placement -- **never** dispatch/model/event routing.

The "never ``Path.cwd()``" invariant (C-003 / #2647) is held **by construction** here:

* the single ambient read is the documented ``cwd`` parameter default, taken exactly
  ONCE, at this boundary;
* the ``repo_root`` is always the canonical primary (worktree -> primary collapse, via the
  existing ``resolve_canonical_root`` / ``get_main_repo_root`` authorities), never a raw
  worktree;
* the ``target_branch`` is resolved declaration-first (``read_target_branch_from_meta``)
  with a non-ambient fallback (``resolve_primary_branch(..., bias=False)``, guarded against
  that function's cornerstone-less last-resort recursion -- see
  :func:`_validated_fallback_branch`) -- so the ambient checked-out branch is never
  **returned** as the target, and "the ambient branch never wins when it disagrees with the
  declaration" holds. The one ambient read on the fallback path is a defensive comparison
  (to exclude the HEAD), never a use of it as the target.

Scope (Increment 1): this resolves the canonical declaration-first target. The
worktree-preferring READ root stays owned by
:func:`specify_cli.core.paths.get_status_read_root` (C-003, "READ paths only") and is not
collapsed by this entry. The capability-scoped write handle in ``mission_runtime`` that
would generalise #3128 to the whole mutating surface is the deferred Increment 2.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.paths import (
    assert_safe_path_segment,
    get_main_repo_root,
    read_target_branch_from_meta,
    resolve_canonical_root,
)

__all__ = [
    "CommandRepoTarget",
    "TargetProvenance",
    "resolve_command_repo_target",
]


class TargetProvenance(Enum):
    """Where a :class:`CommandRepoTarget`'s ``target_branch`` came from.

    ``DECLARATION`` -- read from the Mission's ``meta.json`` ``target_branch`` field.
    ``VALIDATED_FALLBACK`` -- the field was absent, so the repository's configured primary
    branch was resolved non-ambiently (``origin/HEAD`` or the common-branch ladder via
    ``resolve_primary_branch(..., bias=False)``), and, in a cornerstone-less repository
    where even that has no answer, the conventional default -- never the ambient
    checked-out branch (see :func:`_validated_fallback_branch`). A marked, explicit
    fallback, never a silent default.
    """

    DECLARATION = "declaration"
    VALIDATED_FALLBACK = "validated_fallback"


@dataclass(frozen=True)
class CommandRepoTarget:
    """A mission-scoped command's declaration-first ``(repo_root, target_branch)`` target.

    ``repo_root`` is the canonical primary (repository-root) checkout; ``target_branch`` is
    the declaration-first resolved branch; ``provenance`` records whether the branch came
    from the stored declaration or the validated fallback.
    """

    repo_root: Path
    target_branch: str
    provenance: TargetProvenance


def resolve_command_repo_target(
    mission_slug: str,
    *,
    cwd: Path | None = None,
    repo_root: Path | None = None,
) -> CommandRepoTarget:
    """Resolve a mission-scoped command's declaration-first ``(repo_root, target_branch)``.

    This is the single command-entry producer of that target. Callers pass the stored
    Mission ``mission_slug`` (the ``kitty-specs/<slug>`` directory name). Resolution:

    ``mission_slug`` MUST be the stored mission DIRECTORY name (``kitty-specs/<slug>``),
    not a fuzzy operator handle (a bare ``mid8``, numeric prefix or human slug). Routing a
    fuzzy handle is deferred (it needs the read-path canonicalization this entry
    deliberately omits -- #6152); callers with a raw handle resolve it to the on-disk dir
    name first. The slug is validated as a safe single path segment, so a traversal payload
    (``../x``) is refused rather than composed.

    1. **repo_root** -- when ``repo_root`` is supplied it is collapsed to the canonical
       primary with :func:`get_main_repo_root`; otherwise it is resolved from ``cwd``
       (defaulting to :func:`Path.cwd` -- the ONE sanctioned ambient read, taken once)
       with :func:`resolve_canonical_root`, which already collapses a worktree to its
       primary. The result is always the canonical primary, never a raw worktree.
    2. **target_branch** -- declaration-first: :func:`read_target_branch_from_meta` reads
       ``meta.json`` ``target_branch`` from the primary mission directory. When present the
       provenance is :attr:`TargetProvenance.DECLARATION`. When absent, the configured
       primary branch is resolved with ``bias=False`` and then guarded so it is never the
       ambient checked-out branch (see :attr:`TargetProvenance.VALIDATED_FALLBACK`); the
       provenance is :attr:`TargetProvenance.VALIDATED_FALLBACK`.

    Fail-closed: a corrupt ``meta.json`` propagates ``MissionMetaReadError``; an unsafe
    ``mission_slug`` propagates ``UnsafePathSegmentError``; and, on the ``cwd`` path only, a
    location with no git marker propagates ``WorkspaceRootNotFound``. The explicit
    ``repo_root`` path collapses via :func:`get_main_repo_root`, which returns the resolved
    path for a non-repo input rather than raising (mirroring the resolver the routed call
    sites already relied on).
    """
    assert_safe_path_segment(mission_slug)
    if repo_root is not None:
        primary_root = get_main_repo_root(repo_root)
    else:
        # The ONE sanctioned ambient read, taken once, at this boundary.
        start = cwd if cwd is not None else Path.cwd()
        primary_root = resolve_canonical_root(start)

    feature_dir = primary_root / KITTY_SPECS_DIR / mission_slug
    declared = read_target_branch_from_meta(feature_dir)
    if declared is not None:
        return CommandRepoTarget(
            repo_root=primary_root,
            target_branch=declared,
            provenance=TargetProvenance.DECLARATION,
        )

    return CommandRepoTarget(
        repo_root=primary_root,
        target_branch=_validated_fallback_branch(primary_root),
        provenance=TargetProvenance.VALIDATED_FALLBACK,
    )


def _validated_fallback_branch(primary_root: Path) -> str:
    """Resolve the configured primary branch, never the ambient checked-out branch.

    ``resolve_primary_branch(bias=False)`` resolves ``origin/HEAD`` then the common-branch
    ladder (``main``/``master``/``develop``, local + origin), which is non-ambient. Its
    documented last resort, however, recurses into the ambient-biased cascade and would
    return the checked-out branch in a cornerstone-less repository (no ``origin/HEAD`` and
    no common branch). We close that one hole: if the resolved branch is the live HEAD and
    is not itself a common primary name, the configured primary is genuinely unknown, so we
    use the conventional default instead of the ambient feature branch -- keeping the
    :attr:`TargetProvenance.VALIDATED_FALLBACK` contract (never the ambient HEAD) true.
    """
    # Deferred import: core.paths loads very early and git_ops <-> core.paths form a
    # circular import at module scope (mirrors get_feature_target_branch's own deferral).
    from specify_cli.core.git_ops import (
        COMMON_PRIMARY_BRANCHES,
        get_current_branch,
        resolve_primary_branch,
    )

    fallback = str(resolve_primary_branch(primary_root, bias=False))
    if fallback not in COMMON_PRIMARY_BRANCHES and fallback == get_current_branch(primary_root):
        return str(COMMON_PRIMARY_BRANCHES[0])
    return fallback
