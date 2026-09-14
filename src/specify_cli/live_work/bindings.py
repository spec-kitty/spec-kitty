"""Live Work binding resolution — repository, mission, session (spec-kitty#4268).

The attribution honesty rules (LIVE-WORK.md §3.1, glossary "Attribution" /
"Work binding"):

* a mission binding is set only when it is actually determinable — for
  harness-hook capture that means the observation's own working directory
  is a mission *worktree* (``.worktrees/<slug>-<mid8>-lane-<id>``), whose
  name declares its mission identity; a plain repository checkout carries
  many missions and is never silently resolved to one;
* repository identity is the git-truth remote slug, resolved through the
  client's own :mod:`zeitgeist_client.repo_identity` under one shared
  deadline — the authenticated principal and the admitted-repository
  generation are derived server-side from the credential, never asserted
  here;
* a capture session keeps the harness's own session id; a delegated child
  session names its parent, and a retry is a new linked session (LW-01).

Overlapping-worktree attribution falls out of the identity dimensions: two
agents in two worktrees of one repository hold distinct session ids and
distinct mission bindings (or an explicit unknown), so the same-file case
is attributed per session — exactly, never merged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .models import MissionBinding, RepositoryBinding

__all__ = [
    "ResolvedBindings",
    "resolve_bindings",
]


_WORKTREE_DIR_RE: Final = re.compile(r"^(?P<slug>.+)-(?P<mid8>[0-9A-HJKMNP-TV-Z]{8})-lane-(?P<lane_id>[0-9A-Za-z-]+)$")
"""``.worktrees/<slug>-<mid8>-lane-<id>`` — the canonical mission worktree name."""


@dataclass(frozen=True)
class ResolvedBindings:
    """The bindings one capture observation carries."""

    repository: RepositoryBinding | None
    mission: MissionBinding | None
    repo_root: Path | None
    mission_source: str = "none"


def _repo_slug(cwd: Path) -> str | None:
    """The git-truth ``owner/name`` slug for *cwd*, or ``None`` outside a repo."""
    from specify_cli.zeitgeist_client import repo_identity  # noqa: PLC0415

    try:
        slug: str | None = repo_identity.repo_name(str(cwd))
    except Exception:  # repo_identity fails closed outside a git checkout
        return None
    return slug


def _branch_name(cwd: Path) -> str | None:
    from specify_cli.zeitgeist_client import repo_identity  # noqa: PLC0415

    try:
        branch: str | None = repo_identity.branch_name(str(cwd))
    except Exception:
        return None
    return branch


def _resolve_mission_from_worktree(worktree_dir: Path, main_repo_root: Path) -> MissionBinding | None:
    """Resolve a mission worktree's own declared identity, or ``None``.

    The worktree directory name declares ``(slug, mid8)``; the binding is
    confirmed against the repository's mission metadata (the ULID whose
    first 8 characters match) so a stale or hand-renamed directory never
    mints a mission identity. The sanctioned discovery boundary is the
    mission resolver, never a raw ``kitty-specs/`` walk.
    """
    from specify_cli.context.mission_resolver import FsMissionResolver  # noqa: PLC0415

    match = _WORKTREE_DIR_RE.match(worktree_dir.name)
    if match is None:
        return None
    slug, mid8 = match.group("slug"), match.group("mid8")
    try:
        missions = FsMissionResolver(main_repo_root).all_missions()
    except Exception:
        return None
    for mission in missions:
        mission_id = getattr(mission, "mission_id", None)
        if isinstance(mission_id, str) and mission_id.startswith(mid8):
            return MissionBinding(
                mission_id=mission_id,
                display_label=getattr(mission, "mission_slug", None) or slug,
            )
    return None


def resolve_bindings(cwd: Path) -> ResolvedBindings:
    """Resolve the repository and mission bindings for one capture cwd.

    ``mission`` is set only when *cwd* sits inside a mission worktree whose
    declared identity confirms against the repository's mission metadata;
    otherwise the observation stays repository-bound (or fully unbound
    outside a git checkout) — visible as such, never guessed.
    """
    if cwd is None:
        return ResolvedBindings(repository=None, mission=None, repo_root=None)

    cwd = Path(cwd).resolve()
    # Walk up to the repository root (the first ancestor with a .git entry).
    repo_root = cwd if (cwd / ".git").exists() else None
    if repo_root is None:
        for ancestor in cwd.parents:
            if (ancestor / ".git").exists():
                repo_root = ancestor
                break
    if repo_root is None:
        return ResolvedBindings(repository=None, mission=None, repo_root=None)

    slug = _repo_slug(cwd)
    if slug is None:
        return ResolvedBindings(repository=None, mission=None, repo_root=repo_root)
    branch = _branch_name(cwd)
    # branch_name degrades quietly to "" (detached/unavailable); an empty
    # branch is simply absent, never an invalid one-character-short value.
    repository = RepositoryBinding(slug=slug, branch=branch or None)

    # A mission worktree sits under <repo_root>/.worktrees/<name>/… and
    # carries its own .git file, so the walk above resolves repo_root to the
    # *worktree* root whenever cwd is inside one — the binding then comes
    # from the worktree's own declared name, confirmed against the main
    # repository's mission metadata.
    mission: MissionBinding | None = None
    mission_source = "none"
    if repo_root.parent.name == ".worktrees":
        mission = _resolve_mission_from_worktree(repo_root, repo_root.parent.parent)
        mission_source = "worktree" if mission is not None else "unconfirmed"

    return ResolvedBindings(repository=repository, mission=mission, repo_root=repo_root, mission_source=mission_source)
