"""Canonical status-surface resolver for Spec Kitty missions.

This module is the **sole** canonical authority for coord-vs-primary
status-surface selection (FR-001 / FR-007). Every mission-surface read routes
through :func:`resolve_status_surface_with_anchor` — directly, or via the
blessed ``resolve_surface_dir_or_typed_error`` delegator (aggregate /
``mission_runtime``) — so no secondary fallback or parallel resolution
mechanism survives outside this seam. ``coordination/status_transition.py``'s
former path-shape topology predicates (the #1900 5th selection site) now
delegate to :func:`classify_worktree_topology` / :func:`is_registered_coord_worktree`
here; the C-002 topology-ratchet allowlist entry that reserved them is drained
(tests/architectural/test_topology_resolution_boundary.py). Any contributor
reaching for a parallel resolution path should treat this constraint as
load-bearing (NFR-003 compliance boundary).

The coord-empty case (a materialized-but-empty coordination worktree) is an
operator-decided **loud primary fallback** (Option B; FR-001 / FR-003 / #1716):
the resolver falls back to the primary checkout and proceeds. For a coord
mission WITH lanes (``MissionTopology.LANES_WITH_COORD`` — lane worktrees were
provisioned to write there), an empty coord root is genuinely unexpected, so
the fallback emits a single ``logging.WARNING``
(:data:`_COORD_EMPTY_FALLBACK_WARNING`) that names the stale-surface risk AND
both operator recovery paths — flatten (drop ``coordination_branch`` from
``meta.json``) OR run ``spec-kitty doctor workspaces --fix``. For a solo
coord mission with no lanes (``MissionTopology.COORD``), an empty coord root
is the EXPECTED steady state until the mission's first coordination-branch
write self-materializes it (#2533 / WP08 T029-T031): the fallback stays
quiet — no warning, no manual flatten prompted for a condition that is not an
error. It NEVER silently degrades for the genuinely unexpected case: the
warning makes that fallback observable so an operator or orchestrating agent
can intervene. The decision is recorded in
``docs/adr/3.x/2026-06-19-1-coord-empty-surface-fallback.md`` and bound
to this single resolver. (The sibling coord-*deleted* case stays a hard-fail —
:class:`CoordinationBranchDeleted`, #1848 — because a deleted branch carrying
unmerged status is data loss, not a degraded read.)

Coord-topology resolution happens **exactly once** (FR-036). The coord-aware
:func:`candidate_feature_dir_for_mission` resolver already returns the
coordination-worktree feature dir whenever that worktree is materialized on
disk; this module therefore never re-invokes that resolver on an
already-resolved root. The only remaining case it handles directly is the
transitional window where ``meta.json`` declares ``coordination_branch`` but
the coord worktree has not been materialized yet — there it composes the coord
path **once**, by hand, rather than resolving a second time. Re-running the
coord-aware resolver against a coord root nested
``.worktrees/<m>-coord/.worktrees/<m>-coord/…`` (the #1772 double-resolution
bug); building the path directly avoids that.
"""

from __future__ import annotations

import enum
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from mission_runtime import (
    CommitTarget,
    MissionArtifactKind,
    MissionTopology,
    classify_topology,
    resolve_write_target_or_degrade,
    routes_through_coordination,
)
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.lanes.branch_naming import mid8_from_slug, resolve_mid8
from specify_cli.missions._read_path_resolver import (
    CoordState,
    StatusReadPathNotFound,
    _canonicalize_primary_read_handle,
    _compose_primary_feature_dir,
    candidate_feature_dir_for_mission,
    coord_feature_dir,
    probe_coord_state,
    read_primary_meta,
    stored_topology_from_meta,
)

__all__ = [
    "CoordinationBranchDeleted",
    "CoordinationWorktreeUnmaterialized",
    "ResolvedStatusSurface",
    "WorktreeRegistryUnavailable",
    "WorktreeTopology",
    "classify_worktree_topology",
    "is_registered_coord_worktree",
    "is_under_worktrees_segment",
    "read_worktree_registry",
    "resolve_declared_mid8",
    "resolve_for_write",
    "resolve_status_surface",
    "resolve_status_surface_with_anchor",
]

logger = logging.getLogger(__name__)

_WORKTREES_SEGMENT = ".worktrees"
_COORD_SUFFIX = "-coord"
_STATUS_EVENTS_FILENAME = "status.events.jsonl"


def _topology_uses_coord_surface(topology: MissionTopology) -> bool:
    """True when *topology* places the status surface on a coordination ref.

    Thin call-through to the ONE canonical routing predicate
    (:func:`mission_runtime.routes_through_coordination`) over the ONE canonical
    coord-routing set — no second ``{COORD, LANES_WITH_COORD}`` set is restated
    here (FR-005 / SC-001). The surface-shape projection of the WP02 stored
    topology (FR-004): the PRIMARY-vs-coord decision is READ from the topology,
    not re-inferred from ``coordination_branch is None`` (the retired #2069 third
    derivation). Retained as a thin shim so the cross-module
    ``_read_path_resolver`` consumer keeps its import; WP17 collapses both onto
    the canonical predicate directly.
    """
    return routes_through_coordination(topology)


# Option B loud primary fallback (FR-001 / FR-003 / #1716): when the coordination
# worktree root is materialized but carries no mission dir, the resolver returns
# the PRIMARY checkout and emits this single ``logging.WARNING`` so the fallback
# is observable. The message names the stale-surface risk AND both operator
# recovery paths (flatten OR `spec-kitty doctor workspaces --fix`); it is built
# once (paula C-warning-dup) and reuses the ADR recovery text. The ``{slug}`` /
# ``{coord_root}`` fields are filled at emit time.
_COORD_EMPTY_FALLBACK_WARNING = (
    "Coordination worktree for mission %(slug)r is materialized but carries no "
    "mission dir (coord root %(coord_root)s): falling back to the PRIMARY "
    "checkout, which may expose a stale, split-brain status surface. Recover by "
    "EITHER (a) flattening the mission — remove the `coordination_branch` key "
    "from meta.json so the primary checkout becomes authoritative — OR "
    "(b) recreating/populating the coordination worktree by running "
    "`spec-kitty doctor workspaces --fix`."
)


class WorktreeTopology(enum.Enum):
    """How a worktree path relates to a mission's commit destination.

    Produced ONLY by :func:`classify_worktree_topology`. No consumer may derive
    topology from path shape directly (C-SEAM-1): the ``-coord`` suffix and the
    ``.worktrees`` segment merely *propose*; the ``git worktree list
    --porcelain`` registry *disposes*.
    """

    PRIMARY = "primary"
    """The main checkout (not under a registered ``.worktrees`` entry)."""
    COORD_WORKTREE = "coord_worktree"
    """A registered ``<slug>-<mid8>-coord`` worktree."""
    LANE_WORKTREE = "lane_worktree"
    """A registered lane worktree (registered, but NOT coord)."""
    UNREGISTERED = "unregistered"
    """Under ``.worktrees`` but absent from the git registry (husk, F-005)."""


class WorktreeRegistryUnavailable(RuntimeError):
    """Raised when the git worktree registry cannot be read.

    Name proposes coord/lane topology; without the registry to dispose, the
    seam fails closed rather than guessing from path shape (NFR-003). Carries a
    stable ``error_code`` so callers route without string parsing.
    """

    error_code: str = "WORKTREE_REGISTRY_UNAVAILABLE"

    def __init__(self, *, repo_root: Path, detail: str) -> None:
        self.repo_root = repo_root
        self.detail = detail
        super().__init__(f"Could not read the git worktree registry at {repo_root}: {detail}. Topology cannot be determined from path shape alone; fail closed.")


# ``StatusReadPathNotFound`` resolves to ``Any`` under this project's mypy
# config because ``src/specify_cli/missions/`` is in the mypy ``exclude`` list
# (pyproject ``[tool.mypy] exclude``), so mypy cannot see the real base class
# and reports ``cannot subclass "Any"``. The subclass is correct and intended:
# every existing ``except StatusReadPathNotFound`` handler must keep catching
# R3 (fail-closed), while the distinct ``error_code`` lets callers route on the
# deleted-branch recovery. The mypy error is a config artifact, not a code
# defect — narrowly suppressed here with rationale per the project's
# suppression policy. The CI-authoritative invocation
# (``mypy --strict src/specify_cli src/charter src/doctrine``) resolves the base
# class normally, so ``[misc]`` does not fire there and would be reported as
# ``unused-ignore``; pairing both codes keeps the suppression silent under BOTH
# the single-file run (``[misc]``) and the full-package CI run (``[unused-ignore]``).
class CoordinationBranchDeleted(StatusReadPathNotFound):  # type: ignore[misc, unused-ignore]
    """#1889 row R3: ``coordination_branch`` is declared in ``meta.json`` but the
    branch no longer exists in git (deleted), and the coord worktree is absent.

    A deleted coord branch carrying unmerged status is *data loss*, not a
    degraded read — surfaced loudly with an actionable ``next_step`` and a
    distinct ``error_code`` so the resolver NEVER silently falls back to the
    primary checkout (composes with the #1848 status-transition carve-out).

    Subclasses :class:`StatusReadPathNotFound` so existing fail-closed handlers
    still catch it, while the distinct ``error_code`` / type lets callers that
    care surface the deleted-branch recovery path.
    """

    error_code: str = "COORDINATION_BRANCH_DELETED"

    def __init__(
        self,
        *,
        repo_root: Path,
        mission_slug: str,
        mid8: str,
        coordination_branch: str,
        coord_candidate: Path,
        primary_candidate: Path,
    ) -> None:
        self.coordination_branch = coordination_branch
        self.next_step = (
            f"The coordination branch {coordination_branch!r} declared in "
            f"meta.json does not exist in git (never created or deleted). "
            f"Flatten the mission — drop the `coordination_branch` key from "
            f"meta.json — to recover: run `spec-kitty doctor coordination --fix` "
            f"to flatten automatically, or remove the key manually and run "
            f"`spec-kitty migrate backfill-topology`."
        )
        super().__init__(
            repo_root=repo_root,
            mission_slug=mission_slug,
            mid8=mid8,
            coord_candidate=coord_candidate,
            primary_candidate=primary_candidate,
        )

    def __str__(self) -> str:  # pragma: no cover - trivial formatting
        return f"Coordination branch {self.coordination_branch!r} for mission {self.mission_slug!r} is declared in meta.json but deleted from git. {self.next_step}"

    @classmethod
    def for_mission(
        cls,
        *,
        repo_root: Path,
        mission_slug: str,
        mid8: str,
        coordination_branch: str | None,
        primary_candidate: Path,
    ) -> CoordinationBranchDeleted:
        """Build the #1848 deleted-branch error payload from the probe's inputs.

        The ONE construction site for the ``DELETED`` → fail-closed policy
        (#4403): every consumer of
        :func:`~specify_cli.missions._read_path_resolver.probe_coord_state`
        that refuses a deleted coordination branch routes through this factory
        instead of hand-rebuilding the same 6-kwarg payload — this resolver's
        ``resolve_status_surface_with_anchor``, ``mission_runtime.resolution``'s
        ``_resolve_status_surface_dir`` effective-root arm and
        ``_classify_artifact_surface``, and ``_read_path_resolver``'s
        ``_resolve_not_found`` DELETED tail and ``resolve_handle_to_read_path``
        pre-probe tail. (The issue counted three sites; the two
        ``_read_path_resolver`` legs are the same policy and were consolidated
        in the same pass — the whack-a-field risk was two of five sites
        drifting on a ``CoordState``→policy contract change.)

        ``coord_candidate`` is composed here via WP01's
        :func:`~specify_cli.missions._read_path_resolver.coord_feature_dir`
        single grammar — the one value every site already built identically.
        ``primary_candidate`` stays a caller parameter because its PROVENANCE
        genuinely differs per site (the seam-resolved ``read_dir_for`` dir, a
        backfill-recovered bare dir, or the composed primary dir); each site's
        own in-hand value is the authoritative primary anchor.

        ``coordination_branch`` is ``str | None`` only defensively:
        ``probe_coord_state`` can answer ``DELETED`` only when a branch was
        supplied, so the ``or ""`` coercion below is unreachable on any real
        call path (kept so a future caller cannot crash the data-loss raise
        with a ``None`` branch).
        """
        return cls(
            repo_root=repo_root,
            mission_slug=mission_slug,
            mid8=mid8,
            coordination_branch=coordination_branch or "",
            coord_candidate=coord_feature_dir(repo_root, mission_slug, mid8),
            primary_candidate=primary_candidate,
        )


# See the ``CoordinationBranchDeleted`` comment above this class for why the
# ``StatusReadPathNotFound`` subclass triggers a mypy config artifact
# (``src/specify_cli/missions/`` is excluded from ``[tool.mypy] exclude``) that
# is narrowly suppressed here for the same reason, with the same pairing of
# codes for the single-file vs. full-package mypy invocations.
class CoordinationWorktreeUnmaterialized(StatusReadPathNotFound):  # type: ignore[misc, unused-ignore]
    """#4959 (mission ``coord-read-fail-closed``, DM-01M38VWD): ``coordination_branch``
    is declared in ``meta.json`` AND still exists in git, but the coordination
    worktree has never been materialized on disk (the fresh-clone / CI /
    removed-worktree window — :attr:`~specify_cli.missions._read_path_resolver.
    CoordState.UNMATERIALIZED`).

    Before this fix, a coord-partition read in this state silently substituted
    the empty PRIMARY checkout for the (not-yet-existing) coord surface —
    readers then acted on that emptiness as if it were the real document (a
    tracer writer would clobber from its default header; a no-catch reader
    would treat "no content" as "nothing was ever written"). The branch is NOT
    lost — unlike :class:`CoordinationBranchDeleted` — so the actionable
    recovery is to MATERIALIZE the coordination worktree, never to flatten the
    mission (flattening a coord branch that still carries real history would
    be destructive and is the wrong recovery here).

    Subclasses :class:`StatusReadPathNotFound` so every existing fail-closed
    handler keeps catching it (sanctioned read-only degraders such as
    ``mission_runtime.read_dir_degrade`` and ``review.cycle`` continue to
    degrade unchanged), while the distinct ``error_code`` lets a caller that
    cares route on the materialize-vs-flatten distinction.
    """

    error_code: str = "COORDINATION_WORKTREE_UNMATERIALIZED"

    def __init__(
        self,
        *,
        repo_root: Path,
        mission_slug: str,
        mid8: str,
        coordination_branch: str,
        coord_candidate: Path,
        primary_candidate: Path,
    ) -> None:
        self.coordination_branch = coordination_branch
        self.next_step = (
            f"The coordination branch {coordination_branch!r} declared in "
            f"meta.json exists in git, but its coordination worktree has not "
            f"been materialized yet. It will self-materialize on the "
            f"mission's first coordination-branch write, or you can "
            f"materialize it now by running "
            f"`spec-kitty doctor workspaces --fix`. Keep the "
            f"`coordination_branch` key in meta.json as-is — the branch is "
            f"not lost, only not yet checked out."
        )
        super().__init__(
            repo_root=repo_root,
            mission_slug=mission_slug,
            mid8=mid8,
            coord_candidate=coord_candidate,
            primary_candidate=primary_candidate,
        )

    def __str__(self) -> str:  # pragma: no cover - trivial formatting
        return f"Coordination branch {self.coordination_branch!r} for mission {self.mission_slug!r} is unmaterialized. {self.next_step}"

    @classmethod
    def for_mission(
        cls,
        *,
        repo_root: Path,
        mission_slug: str,
        mid8: str,
        coordination_branch: str | None,
        primary_candidate: Path,
    ) -> CoordinationWorktreeUnmaterialized:
        """Build the #4959 unmaterialized-worktree error payload.

        Mirrors :meth:`CoordinationBranchDeleted.for_mission` — the ONE
        construction site for the ``UNMATERIALIZED`` → fail-closed policy, so
        every seam consumer builds the same payload shape instead of
        hand-rolling it. ``coord_candidate`` is composed via the same
        :func:`~specify_cli.missions._read_path_resolver.coord_feature_dir`
        single grammar as the sibling; ``primary_candidate`` stays a caller
        parameter because its provenance genuinely differs per call site.

        ``coordination_branch`` is ``str | None`` only defensively:
        ``probe_coord_state`` can answer ``UNMATERIALIZED`` only when a
        branch was supplied, so the ``or ""`` coercion below is unreachable
        on any real call path (kept so a future caller cannot crash this
        raise with a ``None`` branch).
        """
        return cls(
            repo_root=repo_root,
            mission_slug=mission_slug,
            mid8=mid8,
            coordination_branch=coordination_branch or "",
            coord_candidate=coord_feature_dir(repo_root, mission_slug, mid8),
            primary_candidate=primary_candidate,
        )


def read_worktree_registry(repo_root: Path) -> frozenset[Path]:
    """Return resolved paths registered in ``git worktree list --porcelain``.

    The single authority for "is this path a registered worktree". Fails closed
    via :class:`WorktreeRegistryUnavailable` when git cannot be consulted —
    name-derived guessing is never substituted (NFR-003). Exemplar:
    ``cli/commands/doctor.py:~3063`` (the cache-once-per-pass pattern).

    Batch callers (dashboard scanner, status_service contract routing) read this
    once and pass the result as ``registry=`` to :func:`classify_worktree_topology`
    rather than re-shelling per path.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "worktree", "list", "--porcelain"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:  # git missing / not executable
        raise WorktreeRegistryUnavailable(repo_root=repo_root, detail=str(exc)) from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise WorktreeRegistryUnavailable(repo_root=repo_root, detail=detail)
    registered: set[Path] = set()
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            raw = line[len("worktree ") :].strip()
            try:
                registered.add(Path(raw).resolve())
            except OSError:
                continue
    return frozenset(registered)


def is_under_worktrees_segment(path: Path) -> bool:
    """Return whether *path* lives under a ``.worktrees`` segment (shape only).

    The blessed home for the ``".worktrees" in parts`` idiom (C-SEAM-1). This is
    a pure *shape proposal* — it answers "does this path's layout look like a
    worktree path", NOT "is it a registered coord worktree". Contract-label
    consistency guards (status_service) use this; topology *routing* decisions
    must use :func:`is_registered_coord_worktree` / :func:`classify_worktree_topology`,
    which additionally consult the git registry so a husk cannot spoof the
    authority.
    """
    return _WORKTREES_SEGMENT in path.parts


def _enclosing_worktree_root(path: Path) -> Path | None:
    """Return the ``.worktrees/<name>`` ancestor of *path*, or ``None``.

    Walks the resolved path's parents looking for the first directory whose
    parent is the ``.worktrees`` segment. ``path`` itself is included so a
    worktree-root argument resolves to itself.
    """
    resolved = path.resolve(strict=False)
    for candidate in (resolved, *resolved.parents):
        if candidate.parent.name == _WORKTREES_SEGMENT:
            return candidate
    return None


def classify_worktree_topology(
    path: Path,
    *,
    repo_root: Path | None = None,
    registry: frozenset[Path] | None = None,
) -> WorktreeTopology:
    """Classify *path* against the git worktree registry (C-SEAM-1).

    The ``-coord`` suffix and ``.worktrees`` segment only *propose* topology;
    the registry *disposes*:

    * a path with no ``.worktrees`` ancestor → :attr:`WorktreeTopology.PRIMARY`;
    * a ``.worktrees/<name>`` ancestor that git registers and whose name ends in
      ``-coord`` → :attr:`WorktreeTopology.COORD_WORKTREE`;
    * a registered ``.worktrees`` ancestor that is NOT coord →
      :attr:`WorktreeTopology.LANE_WORKTREE`;
    * a ``.worktrees`` ancestor absent from the registry (husk, F-005) →
      :attr:`WorktreeTopology.UNREGISTERED`.

    Single git-registry read per call (or none when *registry* is injected).
    Callers that route many paths in one pass (status_service) MUST pass the
    cached *registry* set rather than re-shelling per path.

    Args:
        path: The path whose topology is classified.
        repo_root: Repo root for the registry read. Defaults to the first git
            checkout enclosing *path* — but injecting it (and *registry*) is
            preferred for batch callers.
        registry: An already-parsed porcelain set. When provided, NO git is
            consulted (the path is matched against it directly).

    Raises:
        WorktreeRegistryUnavailable: when *registry* is omitted and the git
            registry cannot be read — fail closed, never guess.
    """
    worktree_root = _enclosing_worktree_root(path)
    if worktree_root is None:
        return WorktreeTopology.PRIMARY

    if registry is None:
        root_for_registry = repo_root if repo_root is not None else path
        registry = read_worktree_registry(root_for_registry)

    if worktree_root not in registry:
        # Name proposes a worktree; the registry disposes: a husk (F-005).
        return WorktreeTopology.UNREGISTERED
    if worktree_root.name.endswith(_COORD_SUFFIX):
        return WorktreeTopology.COORD_WORKTREE
    return WorktreeTopology.LANE_WORKTREE


def is_registered_coord_worktree(
    path: Path,
    *,
    repo_root: Path | None = None,
    registry: frozenset[Path] | None = None,
) -> bool:
    """True iff *path* is inside a worktree that BOTH ends in ``-coord`` AND is
    registered in ``git worktree list --porcelain``.

    The ``-coord`` suffix only *proposes* coord topology; the porcelain registry
    *disposes*. A lane worktree, the primary checkout, or a husk (suffix
    present, not registered) returns ``False`` — killing the split-brain where a
    lane/husk path silently receives coord write-contract routing (#1589/#1821,
    F-005 husks).

    Convenience predicate over :func:`classify_worktree_topology`; see it for
    the ``repo_root`` / ``registry`` semantics and the fail-closed posture.
    """
    return classify_worktree_topology(path, repo_root=repo_root, registry=registry) is WorktreeTopology.COORD_WORKTREE


def _roots_own_checkout(repo_root: Path) -> bool:
    """Return whether *repo_root* is itself the root of the repository git finds.

    ``git rev-parse`` answers for ANY directory inside a repository, so on a host
    where an ancestor of *repo_root* happens to be some unrelated checkout
    (#154), the walk-up finds THAT repo and a ref lookup below would judge this
    mission's declared coordination branch against a stranger's ref space. A
    linked worktree still roots its own checkout (``--show-toplevel`` names the
    worktree); a bare repo roots its git dir AT ``repo_root``.
    """
    try:
        top = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--show-toplevel"],
            check=False,
            capture_output=True,
            text=True,
        )
        if top.returncode == 0:
            return Path(top.stdout.strip()).resolve() == repo_root.resolve()
        # No work tree here: either not a repository at all, or a bare repo.
        gitdir = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--absolute-git-dir"],
            check=False,
            capture_output=True,
            text=True,
        )
        return gitdir.returncode == 0 and Path(gitdir.stdout.strip()).resolve() == repo_root.resolve()
    except OSError:
        return False


def _coord_branch_exists(repo_root: Path, coord_branch: str) -> bool:
    """Return whether *coord_branch* still exists in git (one rev-parse).

    Used to split #1889 row R2 (branch exists, worktree not yet materialized)
    from row R3 (branch DELETED). A registry read cannot tell these apart — only
    the ref existence does. Fails closed: when git is unreadable OR ``repo_root``
    is not the root of its own git repository — including an ad-hoc directory
    that merely sits INSIDE some enclosing checkout, where the enclosing repo's
    refs say nothing about this mission's branch (#154) — the branch is treated
    as present (R2/R2′ path), because the materialization guard one level up
    still fail-closes; we never *invent* a deleted-branch error from a
    non-repo / foreign-repo context.
    """
    try:
        inside = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--git-dir"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return True
    if inside.returncode != 0 or not _roots_own_checkout(repo_root):
        # Not a git repository (e.g. an ad-hoc tmp dir), or only a guest of an
        # enclosing one: we cannot assert the branch was deleted from THIS
        # mission's repo, so do not fire R3. Treat as present.
        return True
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--verify", "--quiet", f"refs/heads/{coord_branch}"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return True
    if result.returncode == 0:
        return True
    # Local head absent, but a coordination branch that lives only on a remote
    # (fresh clone, CI checkout, pruned local branch) is NOT "never created".
    # Firing R3 here lets `doctor coordination --fix` delete a genuinely-coord
    # mission's coordination_branch and silently flatten it (#2614 data-loss vector).
    try:
        remotes = subprocess.run(
            ["git", "-C", str(repo_root), "for-each-ref", "--format=%(refname)", "refs/remotes/"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return True
    if remotes.returncode == 0:
        prefix = "refs/remotes/"
        for line in remotes.stdout.splitlines():
            if not line.startswith(prefix):
                continue
            _, _, branch = line[len(prefix) :].partition("/")  # <remote>/<branch...>
            if branch == coord_branch:
                return True
    return False


def _coord_branch_is_local_head(repo_root: Path, coord_branch: str) -> bool:
    """Return whether *coord_branch* exists as a LOCAL head (``refs/heads/``).

    Distinct from :func:`_coord_branch_exists`, which treats a remote-only branch
    (``refs/remotes/origin/<branch>``) as present so the READ path never fires the
    #2614 deleted-branch false-positive on a fresh clone. The WRITE gate (S-C /
    #4970) needs the STRICTER signal: only a local head can be checked out into a
    coordination worktree without forking from the primary branch, so a WRITE that
    would otherwise self-materialize the coord surface is safe ONLY when the branch
    is a local head. Fails closed — an unreadable/foreign git context returns
    ``False`` (no local head proven ⇒ the WRITE must refuse rather than clobber).
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--verify", "--quiet", f"refs/heads/{coord_branch}"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return False
    return result.returncode == 0


def coord_branch_has_committed_artifact(
    repo_root: Path,
    coord_branch: str,
    mission_slug: str,
    kind: MissionArtifactKind,
) -> bool:
    """Return whether *coord_branch* carries a COMMITTED artifact of *kind*.

    The committed-content probe the S-C write gate consults before sanctioning a
    self-materialization write (FR-006 / #4970). A ``CoordState.UNMATERIALIZED``
    local-head coordination branch that ALREADY carries committed matrix content is
    a *stale* head, not a virgin first-write window: materializing over it would
    fork from the primary branch and clobber committed coordination state.

    The probe scans the WHOLE ``kitty-specs/<mission_slug>/`` subtree of
    *coord_branch* (``git ls-tree -r``) and matches on the artifact BASENAME, so a
    path-drifted committed matrix (one that migrated to a non-default sub-path) is
    still detected rather than mis-read as "absent" (post-plan F2). Both
    ``issue-matrix.json`` and ``issue-matrix.md`` map to ``ISSUE_MATRIX``, so a
    not-yet-migrated legacy mission is protected too.

    Fail-closed (mirrors :func:`_coord_branch_is_local_head`'s posture): an
    unreadable git context — a missing/foreign ref, or the git binary absent, i.e.
    anything other than a CLEAN, readable "subtree absent" — returns ``True``
    (treated as present ⇒ the caller REFUSEs). The pathspec form ``git ls-tree -r
    --name-only <branch> -- <subtree>`` returns exit 0 with EMPTY output for a
    readable branch whose subtree simply holds no such file (⇒ ``False``, a genuine
    first-write) and a non-zero exit for an unresolvable ref (⇒ fail-closed
    ``True``), so the two cases never collapse together.
    """
    basenames = _artifact_basenames_for_kind(kind)
    if not basenames:
        return False
    subtree = f"kitty-specs/{mission_slug}/"
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "ls-tree", "-r", "--name-only", coord_branch, "--", subtree],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return True
    if result.returncode != 0:
        return True
    return any(line.rsplit("/", 1)[-1] in basenames for line in result.stdout.splitlines())


def _artifact_basenames_for_kind(kind: MissionArtifactKind) -> frozenset[str]:
    """Return the committed basenames that classify to *kind* (placement authority).

    Derived by inverting ``mission_runtime.artifacts``'s basename→kind classifier —
    the SAME authority that resolves the artifact home — never a hardcoded
    ``issue-matrix.{json,md}`` literal, so the probe path can never drift out of
    sync with the classifier (post-plan F2).
    """
    from mission_runtime import _MISSION_FILE_KIND_BY_BASENAME

    return frozenset(name for name, mapped in _MISSION_FILE_KIND_BY_BASENAME.items() if mapped is kind)


def resolve_for_write(
    repo_root: Path,
    mission_slug: str,
    kind: MissionArtifactKind,
) -> CommitTarget:
    """Fail-closed WRITE-surface resolution — the thin write-side entry point (D1 / S-C).

    The companion of the loud-primary-fallback READ path
    (:func:`resolve_status_surface_with_anchor`, unchanged): one authority, two
    postures. Reads may degrade to the primary checkout; a terminus WRITE must
    NOT — on an unresolved/unmaterialized coordination surface it refuses rather
    than overwrite committed coordination state (#4970).

    Deliberately THIN (RN-F1): it does not re-implement resolution or the
    materialization decision. It delegates BOTH to the real degrade point,
    :func:`mission_runtime.resolve_write_target_or_degrade` in its
    ``terminus_write`` mode (which resolves via the ONE placement authority and
    then consults :func:`mission_runtime.assert_coord_write_materialized`), so the
    write chain and this helper can never drift.

    Returns the resolved :class:`~mission_runtime.CommitTarget`.

    Raises:
        ActionContextError: the mission cannot be resolved, or (code
            ``COORD_WRITE_SURFACE_UNMATERIALIZED``) a coord-routing write's
            coordination surface is unmaterialized/unresolved on this checkout.
    """
    return resolve_write_target_or_degrade(repo_root, mission_slug, kind, degrade_ref=None, terminus_write=True)


@dataclass(frozen=True)
class ResolvedStatusSurface:
    """Single-pass product of the canonical status-surface resolution.

    Carries both halves consumers need so neither re-derives the path (FR-005 /
    #1821):

    * ``surface_path`` — the canonical ``status.events.jsonl`` path (identical
      to :func:`resolve_status_surface`).
    * ``primary_anchor`` — the canonical primary feature-dir anchor
      (``candidate_feature_dir_for_mission``), the CWD-invariant authority the
      transaction-identity logic anchors on (#1737). Resolved exactly once and
      shared, so the historical validate-then-re-derive double resolution is
      gone.
    """

    surface_path: Path
    primary_anchor: Path

    @property
    def read_dir(self) -> Path:
        """Directory containing the resolved ``status.events.jsonl``."""
        return self.surface_path.parent


def resolve_declared_mid8(meta: dict[str, object], mission_slug: str) -> str:
    """Run the ONE sanctioned mid8 cascade; return ``""`` on exhaustion (no raise).

    This is the single canonical mid8-derivation seam (NFR-005, #1868): both
    :func:`_coord_mid8` and the orchestrator's ``_resolve_mission_dir`` consume it
    instead of re-deriving the tier logic. The *raise-on-exhaustion* decision is
    intentionally NOT made here — it belongs to each caller's topology gate (a
    coord-declared topology fails closed; a legacy non-coord mission keeps its
    primary-read path), so this helper returns ``""`` rather than raising.

    Cascade of declared sources (post-083 ``meta.json`` is authoritative):

    1. ``meta.mid8`` — an explicit declared disambiguator, used verbatim.
    2. :func:`resolve_mid8` keyed on the declared ``meta.mission_id`` — derives
       the mid8 from the declared identity (NOT a local ``[:8]`` slice, #1918) and
       trusts the slug's embedded tail only when it provably matches that declared
       identity.
    3. :func:`mid8_from_slug` — the seam's sanctioned best-effort heuristic, used
       ONLY as the final fallback once every *declared* source is exhausted. This
       layer fires for a mission whose canonical ``<slug>-<mid8>`` name embeds the
       real disambiguator but never persisted ``mid8`` / ``mission_id`` (e.g. a
       coord-only-with-tail topology).

    Returns:
        The 8-char mid8 when any tier resolves it, else ``""``.
    """
    raw_mid8 = meta.get("mid8")
    if raw_mid8:
        return str(raw_mid8)
    raw_mission_id = meta.get("mission_id")
    declared_mission_id = str(raw_mission_id) if raw_mission_id else None
    # Authoritative resolution: derive from the declared mission_id; declines a
    # coincidental slug tail when no declared identity confirms it.
    resolved: str = resolve_mid8(mission_slug, mission_id=declared_mission_id)
    if resolved:
        return resolved
    # Final fallback: no DECLARED source carries the disambiguator. The seam's
    # sanctioned heuristic reads the mid8 embedded in the canonical
    # ``<slug>-<mid8>`` name — the legitimate coord-topology mid8 for a mission
    # that declared a coordination_branch but never persisted mid8/mission_id.
    slug_mid8: str = mid8_from_slug(mission_slug)
    return slug_mid8


def _coord_mid8(meta: dict[str, object], mission_slug: str, repo_root: Path) -> str:
    """Derive the coord-worktree mid8 from declared authority, or fail closed.

    Runs the single sanctioned cascade (:func:`resolve_declared_mid8`) and applies
    THIS surface's own fail-closed contract: when every tier is exhausted the
    disambiguator is genuinely lost, and composing a coord path would mis-route to
    a wrong-but-plausible surface. Per the 3.x execution invariant ("raises rather
    than silently falling back on unresolvable context"; F-001), this raises
    :class:`StatusReadPathNotFound` instead of fabricating a mid8. (The
    orchestrator's read path makes its OWN topology-gated decision — see
    ``_resolve_mission_dir`` — so the raise lives here, not in the shared helper.)
    """
    mid8 = resolve_declared_mid8(meta, mission_slug)
    if mid8:
        return mid8
    # Cascade exhausted: no declared source carries the disambiguator. Fail
    # closed rather than fabricate a wrong-but-plausible mid8 (FR-005 / F-001).
    # ``coord_candidate`` here is diagnostic-only (never used to touch git), so
    # it is composed directly rather than via ``CoordinationWorkspace.worktree_path``
    # (#2091, invariant M-1): that seam now REQUIRES a non-empty mid8 and would
    # raise ``CoordinationWorkspaceIdentityUnresolved`` before this more specific
    # ``StatusReadPathNotFound`` could be raised with its own diagnostic message.
    raise StatusReadPathNotFound(
        repo_root=repo_root,
        mission_slug=mission_slug,
        mid8="",
        coord_candidate=repo_root / ".worktrees" / f"{mission_slug}-coord" / KITTY_SPECS_DIR / mission_slug,
        primary_candidate=repo_root / KITTY_SPECS_DIR / mission_slug,
    )


def _husk_is_authoritative_surface(repo_root: Path, mission_slug: str) -> bool:
    """True when a ``.worktrees`` husk MAY be the authoritative read surface.

    Gates the ``.worktrees`` short-circuit in
    :func:`resolve_status_surface_with_anchor` against the mission's STORED
    topology (FR-006, the structural #2062 surface read-leg close). The husk's own
    ``meta.json`` must NOT be trusted over the mission's stored shape:

    * a coord-less stored topology (``SINGLE_BRANCH`` / ``LANES``) → ``False``: the
      mission is flattened, so a lingering registered ``-coord`` husk is stale and
      structurally not consulted (the surface re-anchors on PRIMARY);
    * a coord-routing stored topology (``COORD`` / ``LANES_WITH_COORD``) → ``True``:
      a real coord worktree IS the authoritative read (C-006 preservation);
    * NO stored topology (un-backfilled legacy mission) → ``True``: preserve the
      historical husk-consulting behaviour exactly once (FR-003 shell contract),
      so legacy missions whose status genuinely lives on the coord worktree still
      resolve there.

    Reads the stored topology from the PRIMARY ``meta.json`` via the SAME
    :func:`read_primary_meta` / :func:`stored_topology_from_meta` seam the guarded
    read path uses (NFR-004 — one stored-topology authority, no re-inference). A
    malformed / unreadable primary meta degrades to ``True`` (the historical
    husk-consulting behaviour), since without a stored topology the husk short-
    circuit cannot be safely overridden — the downstream primary re-anchor still
    surfaces the malformed-meta diagnostic.
    """
    from specify_cli.core.paths import MissionMetaReadError

    try:
        primary_meta, _ = read_primary_meta(repo_root, mission_slug)
    except (ValueError, OSError, MissionMetaReadError):
        # MissionMetaReadError (FR-007 / #3162): read_primary_meta is routed
        # through the ONE fail-closed reader, so a corrupt/non-object primary
        # meta now emits the typed error instead of a raw ValueError -- the
        # documented degrade-to-True arm below must keep absorbing it.
        return True
    stored = stored_topology_from_meta(primary_meta)
    if stored is None:
        return True
    return _topology_uses_coord_surface(stored)


def _primary_mission_is_completed(primary_dir: Path) -> bool:
    """Return whether PRIMARY merge evidence makes that surface authoritative.

    Merge-marker only (squad pass 1 on PR #845): an unmerged coord mission
    whose WPs are all terminal keeps writing to its coord worktree, so
    re-anchoring reads to primary there would serve stale state. Non-raising:
    corrupt primary meta (``MissionMetaReadError``) reads as not-merged and the
    resolver falls through to its ordinary surface decision.
    """
    from specify_cli.core.paths import MissionMetaReadError
    from specify_cli.status import StoreError, is_mission_merged

    if not (primary_dir / "meta.json").is_file():
        return False
    try:
        return bool(is_mission_merged(primary_dir))
    except (StoreError, MissionMetaReadError):
        return False


def _effective_surface_topology(
    threaded: MissionTopology | None,
    meta: dict[str, object],
    coord_branch: str | None,
) -> MissionTopology:
    """Resolve the surface-SHAPE topology, preferring the STORED value (randy #2).

    The single disposal of the PRIMARY-vs-coordination surface shape for
    :func:`resolve_status_surface_with_anchor`. Precedence (FR-004 / SC-001):

    1. the ``threaded`` topology the caller supplied (the WP02 stored value the
       coord-aware read path already read) wins when present;
    2. otherwise the stored ``topology`` is READ from the in-hand PRIMARY ``meta``
       via the canonical :func:`stored_topology_from_meta` seam — so the relocated
       two-arg call sites READ the stored shape rather than relaying a parallel
       ``classify_topology(coord_branch, …)`` inference (the non-adoption randy
       flagged: a value-derivation surviving as a second inference);
    3. only an un-backfilled legacy mission (no stored ``topology``) derives the
       shape ONCE via WP01's :func:`classify_topology` SSOT from the value-read.

    Every arm lands on the same single topology authority; no arm re-implements
    the 2×2 grid.
    """
    if threaded is not None:
        return threaded
    stored: MissionTopology | None = stored_topology_from_meta(meta)
    if stored is not None:
        return stored
    derived: MissionTopology = classify_topology(coord_branch, has_lanes=False)
    return derived


def resolve_status_surface(
    repo_root: Path,
    mission_slug: str,
    topology: MissionTopology | None = None,
    *,
    for_write: bool = False,
) -> Path:
    """Return the canonical status.events.jsonl path for the given mission.

    Thin wrapper over :func:`resolve_status_surface_with_anchor` that discards
    the carried primary anchor. Retained as the canonical surface-path accessor;
    consumers that also need the CWD-invariant primary anchor (transaction
    identity, #1737) should call :func:`resolve_status_surface_with_anchor`
    instead of re-deriving it.

    ``topology`` (WP02 stored value) decides the PRIMARY-vs-coordination surface
    SHAPE when supplied (FR-004 / SC-001). It is optional only so the historical
    two-arg call sites keep resolving; when omitted the surface defaults to
    coord-routing (matching the legacy ``coordination_branch is not None``
    behaviour) and the per-state transient arms still discriminate via the probe.

    Raises FileNotFoundError when meta.json is absent.
    Raises ValueError when meta.json is malformed.
    """
    return resolve_status_surface_with_anchor(repo_root, mission_slug, topology, for_write=for_write).surface_path


def resolve_status_surface_with_anchor(
    repo_root: Path,
    mission_slug: str,
    topology: MissionTopology | None = None,
    *,
    for_write: bool = False,
) -> ResolvedStatusSurface:
    """Resolve the canonical status surface and primary anchor in one pass.

    Resolution is single-pass (FR-036): :func:`candidate_feature_dir_for_mission`
    — the coord-aware primitive that ``MissionStatus`` is also built on — is
    invoked **exactly once** and its result is carried as ``primary_anchor``.
    The surface path is derived from that same resolution:

    1. If the resolved dir is already inside a ``.worktrees/<m>-coord`` root, it
       is final — the surface lives there (never re-resolve; the #1772 nesting
       bug).
    2. Otherwise the resolver landed in the primary checkout. When that mission
       declares ``coordination_branch`` but the coord worktree is not yet
       materialized, compose the coord path **directly** (one derivation, via
       WP01's :func:`coord_feature_dir`). When the coord worktree root *is*
       materialized but lacks the mission dir (the coord-empty state), apply
       Option B: return the PRIMARY checkout surface. For a solo (no-lanes)
       coord mission (``MissionTopology.COORD``) this is the EXPECTED steady
       state pre-first-write, so the fallback is quiet — no warning (#2533 /
       WP08). For a mission WITH lanes (``MissionTopology.LANES_WITH_COORD``,
       lane worktrees were provisioned to write there) an empty coord root is
       genuinely unexpected, so the fallback still emits a single loud
       ``logging.WARNING`` (:data:`_COORD_EMPTY_FALLBACK_WARNING`) naming the
       stale-surface risk and both recovery paths (#1716 / FR-001 / FR-003).
       The coord-state decision routes through WP01's :func:`probe_coord_state`
       (adopted, not re-derived); the solo-vs-lanes split reuses the
       ``effective_topology`` already disposed above (no parallel derivation).
       The ``CoordState.DELETED`` case still hard-fails
       (:class:`CoordinationBranchDeleted`, #1848).

    ``for_write`` preserves coordination validation for placement callers. A
    completed mission's primary read authority does not grant write placement
    for artifact kinds excluded from post-consolidation writes (#4358).

    Raises FileNotFoundError when meta.json is absent.
    Raises ValueError when meta.json is malformed.
    Raises CoordinationBranchDeleted when the coord worktree is absent AND the
        declared coordination branch has been deleted from git (#1848 data-loss
        carve-out — never a silent fallback).
    Raises StatusReadPathNotFound when the coord-worktree mid8 cannot be derived
        from any declared source (fail closed — never fabricate a mid8).
    """
    try:
        feature_dir: Path = candidate_feature_dir_for_mission(repo_root, mission_slug)
    except StatusReadPathNotFound as exc:
        # Option B (#1716 / FR-001 / FR-003): for the ``<slug>-<mid8>`` handle the
        # canonicalizer derives mid8 from the slug, so a coord-empty topology fails
        # closed HERE (``_resolve_not_found``) before the topology branch below runs
        # — unlike the bare-slug handle, which canonicalizes to primary and reaches
        # the branch directly. Recover by re-anchoring on the fail-closed
        # diagnostic's primary candidate (the primary checkout carries meta.json);
        # the loud coord-empty fallback then fires uniformly for BOTH handle forms.
        # Any non-coord-empty fail-closed (e.g. a genuinely missing mission) keeps
        # propagating, so the not-found behaviour for unresolvable handles is
        # unchanged.
        feature_dir = exc.primary_candidate
    # F-001: the candidate resolution above is the single canonicalization
    # point — a mid8 / ULID / numeric-prefix handle lands on the real mission
    # directory, whose NAME is the canonical mission-dir name. Every downstream
    # composition (the primary re-anchor, the coord-path assembly) consumes
    # that canonical name; re-anchoring on the raw operator handle is exactly
    # the wrong-but-plausible ``kitty-specs/<mid8>/`` surface this resolver
    # must never hand back. (For unresolvable handles the candidate's name
    # equals the raw handle, so the not-found behaviour is unchanged.)
    mission_slug = feature_dir.name
    primary_dir: Path = _compose_primary_feature_dir(
        repo_root,
        _canonicalize_primary_read_handle(repo_root, mission_slug),
    )
    if not for_write and _primary_mission_is_completed(primary_dir):
        # Merge evidence makes primary authoritative — even when only the coord
        # husk carries a status.events.jsonl (pinned by
        # test_merged_primary_wins_even_when_only_coord_has_events): after a
        # merge the primary tree is the record; a stale coord log must not
        # resurrect husk reads. The primary-side empty-read seam the squad
        # flagged is accepted and documented here — the runtime bridge's own
        # merged gate returns terminal before any surface read matters.
        return ResolvedStatusSurface(
            surface_path=primary_dir / _STATUS_EVENTS_FILENAME,
            primary_anchor=primary_dir,
        )
    # FR-007: fail-closed reader routing. Malformed meta surfaces typed
    # MissionMetaReadError instead of raw ValueError.
    from specify_cli.core.paths import load_meta_fail_closed

    meta = load_meta_fail_closed(feature_dir)

    # FR-006 (structural #2062 — the surface read-leg close): the husk
    # short-circuit below trusts the worktree's OWN ``meta.json`` (which EVERY real
    # ``git worktree add`` checkout carries) and returns the husk surface BEFORE the
    # stored-topology shape decision further down ever runs. For a FLATTENED mission
    # (stored ``topology: single_branch`` / ``lanes``, NO ``coordination_branch``) a
    # lingering registered ``-coord`` husk would then leak its stale lane state and
    # re-open #2062. Read the mission's STORED topology from the PRIMARY meta (the
    # authoritative ``topology`` field, via the SAME ``stored_topology_from_meta``
    # seam the read path uses — NOT a fresh ``coordination_branch is None``
    # re-inference): when it is coord-less, the husk is structurally not the read
    # surface, so DO NOT short-circuit on it. Fall through to the primary re-anchor.
    # C-006: a genuine coord mission (stored topology COORD / LANES_WITH_COORD) OR an
    # un-backfilled legacy mission (no stored topology) keeps the husk short-circuit
    # — a real coord worktree is still the authoritative read.
    feature_dir_is_husk = any(part == _WORKTREES_SEGMENT for part in feature_dir.parts)
    if meta is not None and feature_dir_is_husk and _husk_is_authoritative_surface(repo_root, mission_slug):
        return ResolvedStatusSurface(
            surface_path=feature_dir / _STATUS_EVENTS_FILENAME,
            primary_anchor=feature_dir,
        )

    # FR-003 cascade layer 1: config must be readable BEFORE topology can be
    # resolved. ``coordination_branch`` lives in the PRIMARY-checkout meta.json;
    # the coord worktree's mission dir has none. When ``candidate_feature_dir``
    # prefers a materialized coord worktree, ``load_meta`` above silently
    # returns None and the resolver historically handed back the coord path as
    # ``primary_anchor`` with no coord/primary distinction — losing the config
    # signal and flipping topology classification (the #1589/#1821 split-brain
    # the write path then inherits via ``_identity_for_request``). Re-anchor the
    # config read on the canonical primary dir so the surface authority is
    # config-determined, never topology-determined-then-config-lost.
    #
    # read-side-seam-primary-primitive-closure-01KYKMMT WP07/WP08 (T034/T035,
    # FR-005): RECORDED FOUNDATION SITE 4/4, deliberately UNROUTED. This module
    # is the canonical surface authority the status read ultimately depends on
    # (``mission_runtime.resolution._resolve_status_surface_dir`` /
    # ``mission_context_for`` consume ``resolve_status_surface`` from this
    # module to assemble the execution-context workspace fragment): a raw
    # compose here produces the topology/config signal (``coordination_branch``,
    # husk-authority) that FEEDS that surface decision, so it must precede it,
    # not route through it. It does not literally recurse — ``PlacementSeam.
    # read_dir``'s ``resolve_artifact_surface`` / ``declared_read_surface``
    # classification chokepoint never calls into this module at all (a
    # separate call path), and this module is already whole-module sanctioned
    # via ``_READ_SANCTIONED_MODULES``. WP08 deleted the public wrapper this
    # site imported; calls the module-private ``_compose_primary_feature_dir``
    # leaf directly instead.
    #
    # Foundation-count note: this "4/4" in-code count (``core/paths.py`` x2,
    # ``core/git_ops.py``, this module) is a DIFFERENT grouping than the
    # 5-entry ``_FOUNDATION_SANCTION_SEED`` machine-checked table in
    # ``tests/architectural/test_no_read_side_bypass.py`` — that table swaps
    # this whole-module-sanctioned entry for two individually-tracked sites
    # (``retrospective/writer.py``, ``status/aggregate.py``) instead, per its
    # own reconciling comment above ``_FOUNDATION_SANCTIONED``. Six underlying
    # sites total, two different countable subsets by design — not a typo.
    if meta is None:
        # FR-007: fail-closed reader routing. Malformed meta surfaces typed
        # MissionMetaReadError instead of raw ValueError.
        from specify_cli.core.paths import load_meta_fail_closed

        meta = load_meta_fail_closed(primary_dir)
    if meta is None:
        if primary_dir.exists():
            return ResolvedStatusSurface(
                surface_path=primary_dir / _STATUS_EVENTS_FILENAME,
                primary_anchor=primary_dir,
            )
        if feature_dir.exists():
            return ResolvedStatusSurface(
                surface_path=feature_dir / _STATUS_EVENTS_FILENAME,
                primary_anchor=feature_dir,
            )
        raise FileNotFoundError(f"meta.json not found for mission {mission_slug!r} at {feature_dir}")

    # Config is now in hand. The canonical primary anchor is the topology-blind
    # primary dir (the create→first-write window authority the transaction
    # identity logic expects), not the coord-preferring candidate.
    feature_dir = primary_dir

    # ``coordination_branch`` is read here ONLY as the ref VALUE the coord probe
    # and the #1848 deleted-branch error need (it is never the surface-SHAPE
    # decision — that is the retired #2069 third derivation, SC-001). The
    # PRIMARY-vs-coordination SHAPE is decided from the WP02 stored ``topology``
    # (FR-004): when the caller threads it in, ``_topology_uses_coord_surface``
    # disposes; otherwise the stored ``topology`` is READ from the (already-in-hand
    # primary) ``meta`` via the SAME ``stored_topology_from_meta`` seam the read
    # path uses — the relocated read site now READS the stored shape rather than
    # relaying a parallel ``classify_topology(coord_branch, …)`` inference (randy
    # #2 / SC-001). Only an un-backfilled legacy mission (no stored ``topology``)
    # falls back to deriving the shape ONCE via WP01's ``classify_topology`` SSOT
    # from the value-read. Either path lands on the same single topology authority.
    raw_coord = meta.get("coordination_branch")
    coord_branch: str | None = str(raw_coord) if raw_coord else None
    effective_topology = _effective_surface_topology(topology, meta, coord_branch)
    if not _topology_uses_coord_surface(effective_topology) or coord_branch is None:
        # Non-coord topology → PRIMARY. The ``coord_branch is None`` arm here is a
        # VALUE guard, not a topology decision (the shape was already disposed by
        # ``effective_topology``): a coord-routing topology with no recoverable
        # branch ref cannot compose a coord path or the #1848 deleted-branch error,
        # so it degrades to the primary surface exactly as the coord-less cells do.
        return ResolvedStatusSurface(
            surface_path=feature_dir / _STATUS_EVENTS_FILENAME,
            primary_anchor=feature_dir,
        )

    # Coord-routing topology: classify the coord-worktree transient STATE via WP01's
    # shared probe (paula C2) — never re-derive the root/mission-dir/branch checks
    # inline. The stored topology decides the coord-vs-primary SHAPE above; the
    # probe still decides the orthogonal transient on-disk×git state (materialized
    # / empty / deleted) — C-006: the transients are NOT subsumed into the enum.
    # The composed coord feature dir is built once via WP01's ``coord_feature_dir``
    # (paula C1, single grammar). The primary anchor stays the canonical primary
    # candidate (the create→first-write window authority the transaction-identity
    # logic expects).
    mid8: str = _coord_mid8(meta, mission_slug, repo_root)
    composed_coord_dir: Path = coord_feature_dir(repo_root, mission_slug, mid8)
    coord_state = probe_coord_state(repo_root, mission_slug, mid8, coordination_branch=coord_branch)

    # #1889 row R3 / #1848: the coord worktree is absent AND the declared
    # coordination branch has been DELETED from git. A deleted coord branch with
    # unmerged status is data loss, not a degraded read — fail closed LOUDLY with
    # a distinct, actionable error rather than silently composing a coord path or
    # falling back to primary (FR-005 / FR-008). This stays a hard-fail (WP05).
    if coord_state is CoordState.DELETED:
        # #4403: the DELETED → build-and-raise policy routes through the ONE
        # ``CoordinationBranchDeleted.for_mission`` factory (single payload
        # authority); only the site-specific ``primary_candidate`` is threaded.
        raise CoordinationBranchDeleted.for_mission(
            repo_root=repo_root,
            mission_slug=mission_slug,
            mid8=mid8,
            coordination_branch=coord_branch,
            primary_candidate=feature_dir,
        )
    # Option B loud primary fallback (FR-001 / FR-003 / #1716): the coord worktree
    # root is materialized but its mission dir is absent (coord-empty). Reading the
    # primary checkout may expose a stale, split-brain status surface (#1589/#1821),
    # so emit a single loud ``logging.WARNING`` naming the risk AND both recovery
    # paths (flatten OR `spec-kitty doctor workspaces --fix`) — making the fallback
    # observable so an operator/orchestrating agent can intervene — then return the
    # PRIMARY surface and proceed. Before materialization (``UNMATERIALIZED``) the
    # composed coord path is returned as-is; the create→first-write window keeps the
    # primary checkout authoritative one level up (the aggregate's not-yet-
    # materialized gate).
    if coord_state is CoordState.EMPTY:
        # #2533: a solo (no-lanes) coord-topology mission whose coord worktree
        # never received a write is an EXPECTED empty state, not a stale
        # split-brain — routing it to PRIMARY is the correct, quiet outcome
        # (WP08 T029). Only ``MissionTopology.LANES_WITH_COORD`` implies real
        # lane worktrees were provisioned to write there; for THAT shape an
        # empty coord root is genuinely unexpected and the loud warning's
        # true-positive signal must survive (WP08 T031). ``effective_topology``
        # is the SAME value already disposed above (no re-derivation, no
        # parallel ``pr_bound`` signal) — solo ``COORD`` is the only other
        # coord-routing member (``_topology_uses_coord_surface`` gated this
        # branch to exactly {COORD, LANES_WITH_COORD} already).
        if effective_topology is MissionTopology.LANES_WITH_COORD:
            logger.warning(
                _COORD_EMPTY_FALLBACK_WARNING,
                {"slug": mission_slug, "coord_root": composed_coord_dir.parent.parent},
            )
        return ResolvedStatusSurface(
            surface_path=feature_dir / _STATUS_EVENTS_FILENAME,
            primary_anchor=feature_dir,
        )
    return ResolvedStatusSurface(
        surface_path=composed_coord_dir / _STATUS_EVENTS_FILENAME,
        primary_anchor=feature_dir,
    )
