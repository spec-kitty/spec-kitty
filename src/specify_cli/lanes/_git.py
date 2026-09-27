"""Shared low-level git existence-check plumbing for the lanes pipeline.

Consolidates the ``git rev-parse --verify`` branch/ref existence idiom that
was reimplemented across :mod:`specify_cli.coordination.status_transition`,
:mod:`specify_cli.missions._create`,
:mod:`specify_cli.lanes.worktree_allocator`, and
:mod:`specify_cli.lanes.consolidation` (issue #1904).

Scope is deliberately narrow: this is the existence-CHECK idiom only. Branch
*name* composition stays in :mod:`specify_cli.lanes.branch_naming` (topology
ratchet, mission #132) and is orthogonal to these helpers.

Behavior is byte-identical to the strictest pre-consolidation call site:
``git -C <repo> rev-parse --verify --quiet <refspec>`` with output captured and
``check=False`` (truthy iff returncode == 0). ``-C <repo>`` is equivalent to the
``cwd=<repo>`` form the lanes sites used. ``--quiet`` only suppresses stderr,
which was already swallowed by ``capture_output=True`` at every site, so adding
it changes no observable behavior. ``env`` is parameterized so the merge
pipeline's ``_make_merge_env()`` composes through rather than forking the
helper.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def _verify(repo_root: Path, refspec: str, *, env: dict[str, str] | None = None) -> bool:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "rev-parse",
            "--verify",
            "--quiet",
            "--end-of-options",
            refspec,
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    return result.returncode == 0


def branch_exists(repo_root: Path, branch: str, *, env: dict[str, str] | None = None) -> bool:
    """Return True iff a local branch ``branch`` exists in ``repo_root``.

    Resolves ``refs/heads/<branch>`` so only local branch refs (never tags,
    remotes, or arbitrary revspecs) count as existing.
    """
    return _verify(repo_root, f"refs/heads/{branch}", env=env)


def ref_exists(repo_root: Path, ref: str, *, env: dict[str, str] | None = None) -> bool:
    """Return True iff ``ref`` resolves to a commit object in ``repo_root``.

    Distinct from :func:`branch_exists` — this accepts any revspec
    (``main``, ``origin/main``, ``HEAD``, ``2.x``…) and only confirms that git
    can resolve it to a real commit (via the ``<ref>^{commit}`` peel form).
    """
    return _verify(repo_root, f"{ref}^{{commit}}", env=env)


def lane_has_commit_beyond_base(
    worktree_path: Path, base_ref: str, *, env: dict[str, str] | None = None
) -> bool:
    """Return True iff the lane worktree has at least one commit beyond ``base_ref``.

    Counts ``git rev-list --count <base_ref>..HEAD`` inside ``worktree_path``.
    This is the shared "an implementation commit exists" check behind the
    ``for_review`` commit gate — used by both ``agent tasks move-task`` and the
    orchestrator-api ``transition`` so the two enforce identical semantics (an
    external orchestrator could otherwise reach ``done`` with nothing committed).

    Fail-closed: a non-resolvable base/HEAD (returncode != 0) or unparseable
    count returns ``False``, so the gate rejects and asks for a commit rather
    than waving through an unverifiable worktree.
    """
    result = subprocess.run(
        ["git", "rev-list", "--count", f"{base_ref}..HEAD"],
        cwd=str(worktree_path),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if result.returncode != 0:
        return False
    try:
        return int(result.stdout.strip()) > 0
    except ValueError:
        return False
