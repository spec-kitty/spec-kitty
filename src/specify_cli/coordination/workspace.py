"""Per-mission coordination worktree + lane sparse-checkout policy.

This module implements the contract documented in
``kitty-specs/mission-coordination-branch-atomic-event-log-01KSPTVW/contracts/coordination_workspace.md``.

Two responsibilities:

1. **Coordination worktree lifecycle.**
   :class:`CoordinationWorkspace` resolves (creates on demand) the
   per-mission worktree at ``.worktrees/<slug>-<mid8>-coord/`` checked
   out to the mission coordination branch ``kitty/mission-<slug>-<mid8>``.
   ``resolve()`` is idempotent: an existing worktree on the expected
   branch is returned as-is; a mismatched branch raises
   :class:`CoordinationWorkspaceBranchMismatch` (stable error code
   ``COORDINATION_WORKTREE_BRANCH_MISMATCH``) because automatic recovery
   could mask operator mistakes.

2. **Lane sparse-checkout policy.**
   :func:`register_lane_sparse_checkout` configures a lane worktree so
   that ``kitty-specs/<slug>-<mid8>/status.events.jsonl`` and
   ``status.json`` are absent from the lane filesystem. This is how
   lane processes are *physically prevented* from writing the event log
   — they cannot open a file that does not exist.

Important gotcha: in linked git worktrees, ``.git`` is a *file*
pointing to a per-worktree gitdir, not a directory. We therefore never
write literally to ``<lane>/.git/info/sparse-checkout``; we resolve the
real per-worktree gitdir path via
``git rev-parse --git-path info/sparse-checkout``.
"""

from __future__ import annotations

import functools
import subprocess
import threading
from pathlib import Path

from specify_cli.coordination.coherence import is_toolchain_generated_churn
from specify_cli.core.errors import StructuredError
from specify_cli.git.destructive_guard import guarded_worktree_remove
from specify_cli.lanes.branch_naming import (
    coord_dir_name as _seam_coord_dir_name,
    coord_mission_dir_name as _seam_coord_mission_dir_name,
    coord_reconstruct_branch as _seam_coord_reconstruct_branch,
)

# Sonar S1192: the ``worktree`` git subcommand literal recurs across every
# subprocess call this module makes (list/add/remove) — hoisted to one name.
_GIT_WORKTREE = "worktree"


# #1357: serialize concurrent ``CoordinationWorkspace.resolve`` calls so two
# callers cannot race the existence-check / ``git worktree add`` and materialize
# divergent surfaces. The lock is keyed by the resolved worktree path so resolves
# for *different* missions never contend, keeping the critical section minimal and
# deadlock-free (each ``resolve`` acquires exactly one lock and never nests).
_RESOLVE_LOCKS: dict[Path, threading.Lock] = {}
_RESOLVE_LOCKS_GUARD = threading.Lock()


def _resolve_lock_for(path: Path) -> threading.Lock:
    """Return the per-worktree-path lock, creating it on first use.

    The registry guard is held only for the dict lookup/insert, never across the
    git operations themselves, so distinct-mission resolves stay concurrent.
    """
    key = path.resolve(strict=False)
    with _RESOLVE_LOCKS_GUARD:
        lock = _RESOLVE_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _RESOLVE_LOCKS[key] = lock
        return lock


class CoordinationWorkspaceBranchMismatch(Exception):
    """The coordination worktree exists but is checked out to the wrong branch.

    Stable error code: ``COORDINATION_WORKTREE_BRANCH_MISMATCH``.

    This is **never** auto-recovered: a wrong checkout almost always
    means an operator ran ``git checkout`` inside the coord worktree by
    hand, and silently switching them back to the expected branch could
    discard their in-flight work.
    """

    error_code: str = "COORDINATION_WORKTREE_BRANCH_MISMATCH"

    def __init__(
        self, *, worktree_path: Path, expected_ref: str, actual_ref: str,
    ) -> None:
        self.worktree_path = worktree_path
        self.expected_ref = expected_ref
        self.actual_ref = actual_ref
        super().__init__(
            f"Coordination worktree at {worktree_path} is on {actual_ref!r}, "
            f"expected {expected_ref!r}. Manual intervention required."
        )


class CoordinationWorkspaceIdentityUnresolved(StructuredError):
    """Raised when composition is attempted with an empty ``mid8`` (#2091, M-1).

    An empty ``mid8`` cannot be composed into a coordination worktree
    directory or branch name without producing a malformed
    ``kitty/mission-<slug>-`` ref (trailing hyphen, dropped disambiguator).
    Left unguarded, that malformed name only surfaces later as an opaque
    ``git worktree add`` exit-128 far from the actual defect — the caller
    sees a low-level git failure instead of "mid8 is required".

    Guarded at the SINGLE composition seam (``worktree_path`` /
    ``branch_name``, and transitively ``resolve`` / ``is_present`` /
    ``teardown`` which all route through them) so every caller gets the
    fail-loud behavior for free (C-001) rather than each call site needing
    to remember its own empty-``mid8`` check. The ``runtime_bridge.py``
    guard (``coord_routing_topology and not _mid8``) remains as
    belt-and-suspenders for that one call path.
    """

    error_code: str = "COORDINATION_WORKSPACE_MID8_REQUIRED"

    def __init__(self, *, mission_slug: str) -> None:
        self.mission_slug = mission_slug
        super().__init__(
            "CoordinationWorkspace requires a non-empty mid8 to compose a "
            f"coordination worktree/branch name for mission {mission_slug!r}; "
            "refusing to build a malformed 'kitty/mission-<slug>-' ref "
            "(invariant M-1, #2091). Resolve the mission's mid8 (declared "
            "meta.mid8 -> resolve_mid8(mission_id) -> mid8_from_slug) before "
            "calling CoordinationWorkspace."
        )


def _require_mid8(mission_slug: str, mid8: str) -> None:
    """Fail loudly before composing with an empty ``mid8`` (#2091, M-1)."""
    if not mid8:
        raise CoordinationWorkspaceIdentityUnresolved(mission_slug=mission_slug)


def _normalize_ref(ref: str) -> str:
    """Strip ``refs/heads/`` prefix so HEAD comparisons use short names."""
    return ref.removeprefix("refs/heads/")


def _compose_mission_dir(mission_slug: str, mid8: str) -> str:
    """Return the ``<slug>-<mid8>`` mission directory name (no double-suffix).

    Delegates to the seam's VERBATIM coordination primitive
    (``lanes.branch_naming.coord_mission_dir_name``) so there is exactly ONE
    algorithm for the coordination grammar (FR-010), reconstructed byte-identical
    to the pre-WP06 body. The coordination read/transaction path consumes
    ``meta.json.mission_slug`` VERBATIM, including a legacy ``NNN-`` prefix; the
    seam primitive does NOT strip it, so the reconstructed dir matches the on-disk
    coord worktree (#1589). The canonical, NNN-stripping ``mission_dir_name`` is
    NOT used here — it would drift a legacy ``NNN-`` slug to a name never created.
    """
    return _seam_coord_mission_dir_name(mission_slug, mid8=mid8)


def _has_stale_worktree_registration(repo_root: Path, path: Path) -> bool:
    """Return whether git records ``path`` as prunable/missing."""
    output = subprocess.check_output(
        ["git", "-C", str(repo_root), _GIT_WORKTREE, "list", "--porcelain"],
        text=True,
    )
    expected = path.resolve(strict=False)
    current_path: Path | None = None
    current_prunable = False

    for line in output.splitlines() + [""]:
        if line.startswith("worktree "):
            current_path = Path(line.removeprefix("worktree ")).resolve(strict=False)
            current_prunable = False
            continue
        if line.startswith("prunable"):
            current_prunable = True
            continue
        if line == "" and current_path is not None:
            if current_path == expected and current_prunable:
                return True
            current_path = None
            current_prunable = False
    return False


def _remove_worktree_registration(repo_root: Path, path: Path) -> None:
    """Prune a stale/prunable worktree registration. GUARD-EXEMPT (C-003/NFR-006).

    Only ever called when ``path`` does NOT exist on disk (git already
    reports the registration ``prunable``): there is no working tree left to
    inspect, let alone user work to lose. The shared
    :func:`~specify_cli.git.destructive_guard.guarded_worktree_remove` seam
    cannot run here even in principle -- it resolves the repository root by
    executing git *inside* ``worktree`` (``git -C <worktree> rev-parse
    --git-common-dir``), which requires the directory to exist. This is
    therefore an explicit, inline-rationalized exemption from the guard (per
    the routing-invariant.md allowlist convention), not an unrouted/unexplained
    raw force-remove: the removal target is git's own administrative
    bookkeeping for an already-gone directory, never a live worktree that
    could hold local state.
    """
    subprocess.run(
        ["git", "-C", str(repo_root), _GIT_WORKTREE, "remove", "--force", str(path)],
        check=True,
    )


class CoordinationWorkspace:
    """Resolve / create / teardown a per-mission coordination worktree.

    The class is intentionally stateless (only ``@staticmethod`` /
    ``@classmethod``): callers pass ``repo_root``, ``mission_slug``, and
    ``mid8`` on every call so that there is no possibility of stale
    identity caching.

    ``mission_slug`` may be either the bare human slug (legacy callers)
    or the post-WP03 ``<human>-<mid8>`` slug; the helpers below
    transparently deduplicate the suffix.
    """

    @staticmethod
    def worktree_path(repo_root: Path, mission_slug: str, mid8: str) -> Path:
        """Return the canonical worktree path. Pure; no filesystem touch.

        The ``<slug>-<mid8>-coord`` directory name is composed by the seam's
        :func:`coord_dir_name` (single grammar, FR-010). Requires a non-empty
        ``mid8`` (invariant M-1, #2091) — see
        :class:`CoordinationWorkspaceIdentityUnresolved`.
        """
        _require_mid8(mission_slug, mid8)
        return repo_root / ".worktrees" / _seam_coord_dir_name(mission_slug, mid8=mid8)

    @staticmethod
    def branch_name(mission_slug: str, mid8: str) -> str:
        """Return the coordination branch name for an EXISTING coord worktree. Pure.

        Reconstructed VERBATIM via the seam's :func:`coord_reconstruct_branch`
        (no ``NNN-`` strip) so the coord branch and the coord/mission directory
        names stay byte-identical to what was created on disk (FR-010), including
        for legacy ``NNN-`` slugs (#1589). The canonical, NNN-stripping
        ``mission_branch_name`` is reserved for the merge path, not this read path.
        Requires a non-empty ``mid8`` (invariant M-1, #2091) — see
        :class:`CoordinationWorkspaceIdentityUnresolved`.
        """
        _require_mid8(mission_slug, mid8)
        return _seam_coord_reconstruct_branch(mission_slug, mid8=mid8)

    @classmethod
    def resolve(
        cls, repo_root: Path, mission_slug: str, mid8: str,
    ) -> Path:
        """Return the coordination worktree path, creating it on first call.

        Verifies ancestry on reuse: if the worktree already exists but
        is checked out to a different branch, raises
        :class:`CoordinationWorkspaceBranchMismatch`. The exception has
        a stable ``error_code`` field so callers can route on it without
        string parsing.
        """
        path = cls.worktree_path(repo_root, mission_slug, mid8)
        branch = cls.branch_name(mission_slug, mid8)

        # #1357: serialize the check-then-create against this worktree path so
        # concurrent resolves cannot both pass the ``not path.exists()`` guard and
        # race ``git worktree add`` into divergent surfaces. The critical section
        # holds exactly one path-keyed lock and never nests, so it is deadlock-free.
        with _resolve_lock_for(path):
            if path.exists():
                # Verify HEAD points at the expected branch.
                actual = subprocess.check_output(
                    ["git", "-C", str(path), "symbolic-ref", "HEAD"],
                    text=True,
                ).strip()
                # Canonical comparison: normalize via removeprefix.
                # Belt-and-suspenders fallback retained for transitional safety.
                if (
                    _normalize_ref(actual) != branch
                    and actual != f"refs/heads/{branch}"
                    and actual != branch
                ):
                    raise CoordinationWorkspaceBranchMismatch(
                        worktree_path=path, expected_ref=branch, actual_ref=actual,
                    )
                return path

            # Create the worktree pointing at the existing branch.
            # The caller is responsible for ensuring the branch already
            # exists (WP03's mission create does this).
            path.parent.mkdir(parents=True, exist_ok=True)
            if _has_stale_worktree_registration(repo_root, path):
                _remove_worktree_registration(repo_root, path)
            subprocess.run(
                ["git", "-C", str(repo_root), _GIT_WORKTREE, "add", str(path), branch],
                check=True,
                capture_output=True,
                text=True,
            )
            return path

    @classmethod
    def teardown(
        cls, repo_root: Path, mission_slug: str, mid8: str,
    ) -> None:
        """Remove the coordination worktree. Idempotent.

        Does NOT delete the coordination branch — branch deletion is the
        responsibility of ``spec-kitty merge`` (FR-016) once the merge
        has succeeded.

        Routes the live force-remove through the shared
        :func:`~specify_cli.git.destructive_guard.guarded_worktree_remove`
        chokepoint (#4753, C-003): a dirty coordination worktree raises
        :class:`~specify_cli.git.destructive_guard.DestructiveOpRefused`
        instead of being force-removed. This method owns ONLY the worktree
        leg of the coordination triple by design (it never deletes the
        branch), so the raise happens before any mutation and the branch +
        marker are left exactly as found -- FR-004's coupling holds because
        nothing downstream of the raise runs.
        """
        path = cls.worktree_path(repo_root, mission_slug, mid8)
        if not path.exists():
            if _has_stale_worktree_registration(repo_root, path):
                _remove_worktree_registration(repo_root, path)
            return
        guarded_worktree_remove(
            path,
            retain=False,
            is_residue=functools.partial(is_toolchain_generated_churn, mission_slug=mission_slug),
        )

    @classmethod
    def is_present(
        cls, repo_root: Path, mission_slug: str, mid8: str,
    ) -> bool:
        """Return whether the coordination worktree exists on disk."""
        return cls.worktree_path(repo_root, mission_slug, mid8).exists()


# ---------------------------------------------------------------------------
# Lane sparse-checkout policy
# ---------------------------------------------------------------------------


def lane_sparse_checkout_patterns(
    mission_slug: str, mid8: str,
) -> list[str]:
    """Return the lane sparse-checkout patterns (one per line).

    The list is in non-cone mode format:

    * ``/*`` — include everything by default
    * ``!kitty-specs/<dir>/status.events.jsonl`` — exclude event log
    * ``!kitty-specs/<dir>/status.json`` — exclude derived snapshot

    Cone mode does NOT support negation patterns, which is why callers
    MUST call ``git sparse-checkout init --no-cone`` before applying
    these patterns.

    Argument semantics: ``mission_slug`` must be the **full directory
    name** under ``kitty-specs/`` for the mission. In post-WP03 missions
    that name already encodes the mid8 (e.g. ``demo-feature-01J6XW9K``),
    so callers MUST NOT pass the bare human slug. The ``mid8`` parameter
    is kept in the signature for API symmetry with the rest of the
    package and is appended only when ``mission_slug`` does not already
    end with ``-<mid8>`` — protecting callers from double-suffixing.
    """
    mission_dir = _compose_mission_dir(mission_slug, mid8)
    return [
        "/*",
        f"!kitty-specs/{mission_dir}/status.events.jsonl",
        f"!kitty-specs/{mission_dir}/status.json",
    ]


def register_lane_sparse_checkout(
    lane_path: Path, mission_slug: str, mid8: str,
) -> None:
    """Configure a freshly-created lane worktree's sparse-checkout policy.

    Steps:

    1. ``git sparse-checkout init --no-cone`` — switch the worktree to
       non-cone sparse-checkout (negation patterns are not supported in
       cone mode).
    2. Resolve the *real* per-worktree ``info/sparse-checkout`` path via
       ``git rev-parse --git-path info/sparse-checkout``. In linked
       worktrees ``.git`` is a file, NOT a directory; the resolved path
       points into the per-worktree gitdir (typically under
       ``<repo>/.git/worktrees/<name>/info/sparse-checkout``).
    3. Write the patterns from :func:`lane_sparse_checkout_patterns`.
    4. ``git read-tree -mu HEAD`` — materialise the working tree against
       the new sparse-checkout rules so the excluded files actually
       disappear from disk.

    Idempotent: re-invoking on an already-configured lane simply
    rewrites the same file with the same content.
    """
    # Step 1: switch to non-cone sparse-checkout.
    subprocess.run(
        ["git", "-C", str(lane_path), "sparse-checkout", "init", "--no-cone"],
        check=True,
    )

    # Step 2: resolve the real per-worktree sparse-checkout file path.
    # `git rev-parse --git-path info/sparse-checkout` returns a path
    # that may be absolute or relative to the current git dir; resolve
    # it against the lane path to be safe.
    raw = subprocess.check_output(
        ["git", "-C", str(lane_path), "rev-parse", "--git-path",
         "info/sparse-checkout"],
        text=True,
    ).strip()
    sparse_file = Path(raw)
    if not sparse_file.is_absolute():
        sparse_file = lane_path / sparse_file
    sparse_file.parent.mkdir(parents=True, exist_ok=True)

    # Step 3: write the patterns.
    patterns = lane_sparse_checkout_patterns(mission_slug, mid8)
    sparse_file.write_text("\n".join(patterns) + "\n")

    # Step 4: materialise the working tree.
    subprocess.run(
        ["git", "-C", str(lane_path), "read-tree", "-mu", "HEAD"],
        check=True,
    )
