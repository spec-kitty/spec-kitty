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
* the ``target_branch`` is the placement authority's answer
  (:func:`specify_cli.core.paths.get_feature_target_branch`, the resolution
  ``placement_seam(...).write_target(...)`` uses through ``resolve_placement_only``), so a
  command handed this target and a transaction that re-checks placement always agree.
  A declared ``meta.json`` ``target_branch`` wins over the checked-out branch. With no
  declaration, the fallback is whatever the placement authority resolves today, which in a
  repository without ``origin/HEAD`` can be the checked-out branch; making that fallback
  independent of the checked-out branch changes the placement seam itself and is
  follow-up #6152.

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

from specify_cli.core.paths import (
    assert_safe_path_segment,
    get_feature_target_branch,
    get_main_repo_root,
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
    ``VALIDATED_FALLBACK`` -- the field was absent, so the branch is the placement
    authority's fallback (:func:`~specify_cli.core.paths.get_feature_target_branch`), the
    same answer the placement seam gives for the write. Without ``origin/HEAD`` that can be
    the checked-out branch; the non-ambient fallback is follow-up #6152. A marked, explicit
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

    ``mission_slug`` is folded to its canonical on-disk directory name by the same
    read-path canonicalizer the placement authority uses, so a handle the placement seam
    accepts resolves to the same Mission directory here. The slug is validated as a safe
    single path segment first, so a traversal payload (``../x``) is refused rather than
    composed.

    1. **repo_root** -- when ``repo_root`` is supplied it is collapsed to the canonical
       primary with :func:`get_main_repo_root`; otherwise it is resolved from ``cwd``
       (defaulting to :func:`Path.cwd` -- the ONE sanctioned ambient read, taken once)
       with :func:`resolve_canonical_root`, which already collapses a worktree to its
       primary. The result is always the canonical primary, never a raw worktree.
    2. **target_branch** -- delegated to the placement authority,
       :func:`~specify_cli.core.paths.get_feature_target_branch`, so the entry and
       ``placement_seam(...).write_target(...)`` give ONE answer. That authority reads the
       declared ``meta.json`` ``target_branch`` from the canonical primary mission
       directory and falls back to the repository's primary branch when it is absent. The
       provenance is :attr:`TargetProvenance.DECLARATION` when the primary ``meta.json``
       declares a ``target_branch``, else :attr:`TargetProvenance.VALIDATED_FALLBACK`.
       Both reads canonicalize the handle through the sanctioned read-path resolver, so no
       mission path is composed here.

    Fail-closed: a corrupt ``meta.json`` propagates ``MissionMetaReadError``; an unsafe
    ``mission_slug`` propagates ``UnsafePathSegmentError``; and, on the ``cwd`` path only, a
    location with no git marker propagates ``WorkspaceRootNotFound``. The explicit
    ``repo_root`` path collapses via :func:`get_main_repo_root`, which returns the resolved
    path for a non-repo input rather than raising (mirroring the resolver the routed call
    sites already relied on).
    """
    # Deferred import: the missions read-path layer imports core.paths, which loads
    # very early (mirrors get_feature_target_branch's own deferral).
    from specify_cli.missions._read_path_resolver import read_primary_meta

    assert_safe_path_segment(mission_slug)
    if repo_root is not None:
        primary_root = get_main_repo_root(repo_root)
    else:
        # The ONE sanctioned ambient read, taken once, at this boundary.
        start = cwd if cwd is not None else Path.cwd()
        primary_root = resolve_canonical_root(start)

    primary_meta, _declares_coordination = read_primary_meta(primary_root, mission_slug)
    provenance = TargetProvenance.DECLARATION if primary_meta.get("target_branch") else TargetProvenance.VALIDATED_FALLBACK
    return CommandRepoTarget(
        repo_root=primary_root,
        target_branch=get_feature_target_branch(primary_root, mission_slug),
        provenance=provenance,
    )
