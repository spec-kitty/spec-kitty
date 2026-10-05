"""Shared coordination-routed Mission fixture harness (WP02, FR-016 / C-005).

Every red-first reproduction in Mission ``coord-artifact-single-home-01M3V4BE``
builds its preconditions from this module instead of hand-rolling git/coord
fixtures per test file. Each builder constructs its documented shape through
the **production create path** (``create_mission_core`` / the
``spec-kitty agent mission create`` CLI) or, where the production path no
longer produces a pre-fix shape (or where the write path under test would
otherwise decide the fixture's own shape), by explicit low-level appends into
chosen paths -- each self-checked against the production probe or the
documented invariant before returning (fail loud, never silently).

This WP ships no reproduction: it is the harness only, and its own tests
(``tests/coordination/test_coord_mission_factory.py``) are green at the
current base.

Public API
----------
- :func:`make_coord_mission` -- production create path, both coordination
  topologies, three ``via`` variants (``core`` / ``cli_topology`` /
  ``cli_pr_bound``), optional ``materialized=True`` for a deterministic
  MATERIALIZED coordination surface. ``topology=None`` is accepted only for
  ``via="cli_pr_bound"`` (the real WP06 default-resolution path: no
  ``--topology``, topology comes back from ``meta.json``).
- :func:`make_prefix_coord_mission` -- the **pre-fix shape**: a committed
  root-checkout status log, a coordination branch cut *without* the Mission
  dir, and an absent/empty coordination worktree. Built EXPLICITLY (never by
  trusting create's current placement): after create returns, the result is
  rewritten into the pre-fix shape, so the builder keeps working once WP06
  makes create seed the coordination branch and stop writing the root log.
- :func:`make_fork_fixture` -- the four NFR-002 fork shapes shared by WP03,
  WP17 and WP21, with a per-stream selector (``status_log`` /
  ``decision_log`` / ``both``) for shapes (a)/(b)/(c).
- Pure git-plumbing probes: :func:`event_ids`, :func:`lamports`,
  :func:`commits_touching`, :func:`coord_tree_has`, :func:`index_entry_ids`.

How later WPs use this (research red-first list)
-------------------------------------------------
- R1/R1b/R6/R20 (WP06) -- :func:`make_prefix_coord_mission`.
- R2 (WP05) -- :func:`make_coord_mission`.
- R3/R14/R15/R16 (WP17) -- :func:`make_fork_fixture` (shapes b/c/d).
- R4 (WP09) -- :func:`make_prefix_coord_mission` + :func:`commits_touching`.
- R22/R23/R24 (WP18) -- :func:`make_coord_mission` / :func:`event_ids`.

Caller contract: every builder clones a **fresh** git repo under the
``tmp_path`` it is given (via ``tests._support.git_template.clone_template``).
Two builder calls must never share the same ``tmp_path`` -- pass distinct
subdirectories (``tmp_path / "a"``, ``tmp_path / "b"``) when a single test
needs more than one Mission.

Downstream notes (no action needed in WP02, recorded for later WPs):
    - ``make_fork_fixture(..., "fresh_clone")``'s ``ForkFixture.repo_root`` /
      ``coord_worktree_path`` point at the **base** repo, not the clone.
      Consumers must read ``.clone_root``.
    - Fork fixture (d) (``ledger_only_on_coordination``) carries no companion
      ``DecisionPointOpened`` row in the coordination status log. A pre-fix
      ``open_decision`` call would also have written one; WP17's
      union-orphan rule may classify the ledger-only decision as orphaned.
      Left for WP17 to decide whether (d) needs that companion row.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from unittest.mock import patch

import ulid as _ulid_mod
from typer.testing import CliRunner

from kernel.clock import now_utc, now_utc_iso
from mission_runtime import MissionTopology
from spec_kitty_events.decision_moment import OriginFlow as _EventOriginFlow, OriginSurface
from spec_kitty_events.decisionpoint import DECISION_POINT_OPENED, DecisionPointOpenedInterviewPayload
from spec_kitty_events.mission_next import (
    DECISION_INPUT_REQUESTED,
    DecisionInputRequestedPayload,
    RuntimeActorIdentity,
)
from specify_cli.cli.commands.agent.mission import app as _mission_app
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.mission_creation import create_mission_core
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.decisions import store as decision_store
from specify_cli.decisions.models import DecisionStatus, IndexEntry, OriginFlow
from specify_cli.missions._read_path_resolver import CoordState, probe_coord_state
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event, append_raw_rows_atomic
from tests._factories import provision_test_charter
from tests._support.git_template import clone_template

# Explicitly re-annotated: ``specify_cli.*`` is configured ``follow_imports =
# "skip"`` for narrow-file mypy --strict runs (pyproject.toml), which collapses
# the imported constant to ``Any``. A bare ``Path / KITTY_SPECS_DIR`` would
# therefore make every property below return ``Any`` under ``--strict``
# (``no-any-return``); this one annotated re-binding narrows it back to ``str``.
_KITTY_SPECS_DIR: str = KITTY_SPECS_DIR

__all__ = [
    "COORD_TOPOLOGIES",
    "CoordMission",
    "ForkFixture",
    "coord_tree_has",
    "commits_touching",
    "event_ids",
    "index_entry_ids",
    "lamports",
    "make_coord_mission",
    "make_fork_fixture",
    "make_prefix_coord_mission",
]

#: Both coordination topologies, for ``pytest.mark.parametrize``.
COORD_TOPOLOGIES: tuple[MissionTopology, ...] = (
    MissionTopology.COORD,
    MissionTopology.LANES_WITH_COORD,
)

_TOPIC_BRANCH = "topic"
_PRIMARY_BRANCH = "main"
#: Nit (S1192): the two event-log filenames recur across construction, commit
#: and probe call sites -- hoisted once rather than restated as literals.
_STATUS_LOG_FILENAME = "status.events.jsonl"
_DECISION_LOG_FILENAME = "decisions.events.jsonl"
_DECISION_MISSION_TYPE = "software-dev"
_PrefixWorktree = Literal["absent", "empty"]
_ForkShape = Literal[
    "root_uncommitted_coord_untracked",
    "both_committed",
    "fresh_clone",
    "ledger_only_on_coordination",
]
#: Which event log a fork fixture diverges in (H2 binding correction: "Fork
#: fixtures (a) and (b) must say which stream diverges; provide per-stream
#: variants, because WP03's prefix rule runs per stream").
_ForkStream = Literal["status_log", "decision_log", "both"]
#: A probe source is either a file on disk, or ``(repo, ref, relpath)`` read
#: via ``git show`` (used for refs that have no checked-out worktree, e.g. a
#: ``fresh_clone`` fork fixture).
ProbeSource = Path | tuple[Path, str, str]


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CoordMission:
    """A coordination-routed Mission built through the production create path."""

    repo_root: Path
    mission_slug: str
    mid8: str
    mission_dir_name: str
    topology: MissionTopology
    target_branch: str
    coordination_branch: str
    coord_worktree_path: Path
    creation_base_sha: str

    @property
    def root_mission_dir(self) -> Path:
        """``<repo_root>/kitty-specs/<mission_dir_name>/``."""
        return self.repo_root / _KITTY_SPECS_DIR / self.mission_dir_name

    @property
    def coord_mission_dir(self) -> Path:
        """``<coord_worktree_path>/kitty-specs/<mission_dir_name>/``."""
        return self.coord_worktree_path / _KITTY_SPECS_DIR / self.mission_dir_name


@dataclass(frozen=True)
class ForkFixture(CoordMission):
    """A :class:`CoordMission` plus the NFR-002 fork-detection evidence.

    For ``shape="fresh_clone"``, ``repo_root`` / ``coord_worktree_path`` still
    point at the BASE repo the clone was made from -- read the clone via
    ``clone_root`` instead.
    """

    decision_ids_root: tuple[str, ...] = ()
    decision_ids_coord: tuple[str, ...] = ()
    clone_root: Path | None = None


# ---------------------------------------------------------------------------
# Small git helpers
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )


def _git_rev_parse(repo: Path, rev: str) -> str:
    return _git(repo, "rev-parse", rev).stdout.strip()


def _write_protected_branches(repo: Path, branches: tuple[str, ...]) -> None:
    """Append ``protection.protected_branches: [...]`` to ``.kittify/config.yaml``.

    Mirrors the shape ``ProtectionPolicy.resolve`` reads (see
    ``tests/git/test_protection_config_honoring.py``). Appended as a
    SEPARATE top-level YAML key after ``provision_test_charter``'s
    ``mission_type_activations`` block, which keeps both blocks valid YAML
    without needing a round-trip parse/merge.
    """
    config_path = repo / ".kittify" / "config.yaml"
    existing = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    protected_lines = "".join(f"    - {branch}\n" for branch in branches)
    block = f"\nprotection:\n  protected_branches:\n{protected_lines}"
    config_path.write_text(existing + block, encoding="utf-8")


def _init_repo_with_target(tmp_path: Path, *, target_branch: str, protected_primary: bool) -> Path:
    """Clone the fast git template, provision + commit the charter, and check out *target_branch*.

    ``protected_primary=True`` always protects the **Primary Branch**
    (``main``) -- not ``target_branch`` -- regardless of ``via`` (M2: the
    parameter name says "primary", and WP06's US1.4 needs the Primary Branch
    protected the same way for every create path).
    """
    repo = clone_template(tmp_path / "repo")
    provision_test_charter(repo)
    if protected_primary:
        _write_protected_branches(repo, (_PRIMARY_BRANCH,))
    # L4: commit the provisioned charter rather than leaving it untracked, as
    # T008 asks ("provision the charter, commit"). Lands on `main` (before any
    # target-branch checkout below), since `.kittify/` is project-level, not
    # Mission-specific.
    _git(repo, "add", ".kittify")
    _git(repo, "commit", "-m", "chore(fixture): provision charter")
    if target_branch != _PRIMARY_BRANCH:
        _git(repo, "checkout", "-b", target_branch)
    return repo


def _set_up_bare_remote(repo: Path) -> None:
    """Push *repo*'s current ``origin`` history to a fresh bare remote and set ``origin/HEAD``.

    ``clone_template`` already configures an ``origin`` pointing at the
    process-local template cache, so this re-points ``origin`` (rather than
    adding a second remote) and sets ``origin/HEAD`` -- required for
    ``--pr-bound``'s default-topology resolution (CLAUDE.md "Create-time
    topology").
    """
    bare = repo.parent / f"{repo.name}-origin.git"
    subprocess.run(
        ["git", "init", "--bare", "-b", _PRIMARY_BRANCH, str(bare)],
        capture_output=True,
        text=True,
        check=True,
    )
    _git(repo, "remote", "set-url", "origin", str(bare))
    _git(repo, "push", "origin", _PRIMARY_BRANCH)
    _git(repo, "remote", "set-head", "origin", _PRIMARY_BRANCH)


# ---------------------------------------------------------------------------
# T008 -- production-path factory
# ---------------------------------------------------------------------------


def _require_topology_match(actual: str, expected: MissionTopology) -> None:
    if actual != expected.value:
        raise AssertionError(f"meta.json topology {actual!r} != requested {expected.value!r}")


def _coord_mission_from_meta(
    repo: Path,
    *,
    slug: str,
    meta: dict[str, object],
    topology: MissionTopology | None,
    creation_base_sha: str,
) -> CoordMission:
    """Build a :class:`CoordMission` from a create outcome's ``meta.json``.

    ``topology=None`` (M1, WP06's real default path) skips the requested-
    topology assertion entirely and resolves ``topology`` from ``meta.json``
    instead -- the caller asserts the product default itself (e.g.
    ``coord.topology is MissionTopology.COORD``).
    """
    topology_value = meta["topology"]
    if not isinstance(topology_value, str):
        raise AssertionError(f"meta.json topology is not a string: {topology_value!r}")
    if topology is not None:
        _require_topology_match(topology_value, topology)
    resolved_topology = MissionTopology(topology_value)

    coordination_branch = meta.get("coordination_branch")
    if not isinstance(coordination_branch, str):
        raise AssertionError("expected a coordination branch for a coord-routed topology")

    mid8 = meta["mid8"]
    mission_dir_name = meta["mission_slug"]
    target_branch = meta["target_branch"]
    if not (isinstance(mid8, str) and isinstance(mission_dir_name, str) and isinstance(target_branch, str)):
        raise AssertionError(f"unexpected meta.json field types: {meta!r}")

    worktree_path: Path = CoordinationWorkspace.worktree_path(repo, mission_dir_name, mid8)
    return CoordMission(
        repo_root=repo,
        mission_slug=slug,
        mid8=mid8,
        mission_dir_name=mission_dir_name,
        topology=resolved_topology,
        target_branch=target_branch,
        coordination_branch=coordination_branch,
        coord_worktree_path=worktree_path,
        creation_base_sha=creation_base_sha,
    )


def _make_coord_mission_via_core(tmp_path: Path, topology: MissionTopology, *, slug: str, protected_primary: bool) -> CoordMission:
    repo = _init_repo_with_target(tmp_path, target_branch=_TOPIC_BRANCH, protected_primary=protected_primary)
    creation_base_sha = _git_rev_parse(repo, _TOPIC_BRANCH)
    result = create_mission_core(
        repo,
        slug,
        topology=topology,
        target_branch=_TOPIC_BRANCH,
        allow_worktree_context=True,
    )
    meta: dict[str, object] = result.meta
    return _coord_mission_from_meta(repo, slug=slug, meta=meta, topology=topology, creation_base_sha=creation_base_sha)


def _first_json_line(output: str) -> dict[str, object]:
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload: dict[str, object] = json.loads(line)
        except json.JSONDecodeError:
            continue
        return payload
    raise AssertionError(f"No JSON payload in CLI output: {output!r}")


def _invoke_mission_create_cli(repo: Path, args: list[str]) -> dict[str, object]:
    runner = CliRunner()
    # The create's worktree guard reads the real process cwd: run it from the
    # fixture repository, not from the lane worktree pytest may be started in.
    with (
        contextlib.chdir(repo),
        patch("specify_cli.cli.commands.agent.mission.locate_project_root", return_value=repo),
    ):
        result = runner.invoke(_mission_app, ["create", *args], input="")
    if result.exit_code != 0:
        raise AssertionError(f"mission create CLI failed (exit {result.exit_code}): {result.output}")
    return _first_json_line(result.output)


def _cli_create_args(slug: str, topology: MissionTopology | None, *extra: str) -> list[str]:
    """Build the ``agent mission create`` arg list.

    ``topology=None`` omits ``--topology`` entirely (M1): the real WP06
    default path for ``--pr-bound`` from a protected primary branch, where
    the product itself resolves the topology rather than the caller.
    """
    topology_args = ["--topology", topology.value] if topology is not None else []
    return [
        slug,
        *topology_args,
        "--branch-strategy",
        "already-confirmed",
        "--json",
        *extra,
        "--friendly-name",
        f"{slug} fixture",
        "--purpose-tldr",
        f"Fixture mission for {slug}.",
        "--purpose-context",
        f"Fixture mission for {slug}, built by the coordination test factory.",
    ]


def _coord_mission_from_cli_payload(
    repo: Path,
    payload: dict[str, object],
    *,
    slug: str,
    topology: MissionTopology | None,
    creation_base_sha: str,
) -> CoordMission:
    meta_file = payload["meta_file"]
    if not isinstance(meta_file, str):
        raise AssertionError(f"CLI payload missing a string 'meta_file': {payload!r}")
    meta: dict[str, object] = json.loads(Path(meta_file).read_text(encoding="utf-8"))
    return _coord_mission_from_meta(repo, slug=slug, meta=meta, topology=topology, creation_base_sha=creation_base_sha)


def _make_coord_mission_via_cli_topology(tmp_path: Path, topology: MissionTopology, *, slug: str, protected_primary: bool) -> CoordMission:
    repo = _init_repo_with_target(tmp_path, target_branch=_TOPIC_BRANCH, protected_primary=protected_primary)
    creation_base_sha = _git_rev_parse(repo, _TOPIC_BRANCH)
    payload = _invoke_mission_create_cli(repo, _cli_create_args(slug, topology, "--target-branch", _TOPIC_BRANCH))
    return _coord_mission_from_cli_payload(repo, payload, slug=slug, topology=topology, creation_base_sha=creation_base_sha)


def _make_coord_mission_via_cli_pr_bound(tmp_path: Path, topology: MissionTopology | None, *, slug: str, protected_primary: bool) -> CoordMission:
    repo = _init_repo_with_target(tmp_path, target_branch=_PRIMARY_BRANCH, protected_primary=protected_primary)
    _set_up_bare_remote(repo)
    creation_base_sha = _git_rev_parse(repo, _PRIMARY_BRANCH)
    payload = _invoke_mission_create_cli(
        repo,
        _cli_create_args(slug, topology, "--pr-bound", "--start-branch", _TOPIC_BRANCH),
    )
    return _coord_mission_from_cli_payload(repo, payload, slug=slug, topology=topology, creation_base_sha=creation_base_sha)


def _materialize_coord_surface(coord: CoordMission) -> CoordMission:
    """Force a real, production-probe-verified MATERIALIZED coordination surface.

    Uses an actual ``git worktree add`` (never a bare ``mkdir``, which the
    production probe would still read as EMPTY -- see R-M4 / "Shape caveat
    round 5, X2" in the WP). The seeded commit carries no
    ``Spec-Kitty-Coordination-Seed`` trailer: this is a **pre-fix-shaped**
    MATERIALIZED surface, not a post-fix seed (WP03 owns that trailer).
    """
    worktree_path: Path = CoordinationWorkspace.resolve(coord.repo_root, coord.mission_dir_name, coord.mid8)
    coord_dir = coord.coord_mission_dir
    if not coord_dir.exists():
        coord_dir.mkdir(parents=True, exist_ok=True)
        root_events = coord.root_mission_dir / _STATUS_LOG_FILENAME
        coord_events = coord_dir / _STATUS_LOG_FILENAME
        coord_events.write_text(
            root_events.read_text(encoding="utf-8") if root_events.exists() else "",
            encoding="utf-8",
        )
        _git(worktree_path, "add", _KITTY_SPECS_DIR)
        _git(worktree_path, "commit", "-m", f"chore({coord.mission_dir_name}): fixture seed")

    state = probe_coord_state(
        coord.repo_root,
        coord.mission_dir_name,
        coord.mid8,
        coordination_branch=coord.coordination_branch,
    )
    if state is not CoordState.MATERIALIZED:
        raise AssertionError(f"materialized=True failed to reach MATERIALIZED (got {state})")
    return coord


def make_coord_mission(
    tmp_path: Path,
    topology: MissionTopology | None,
    *,
    via: Literal["core", "cli_topology", "cli_pr_bound"] = "core",
    slug: str = "demo",
    protected_primary: bool = False,
    materialized: bool = False,
) -> CoordMission:
    """Create a coordination-routed Mission through the production create path.

    ``via``:
      - ``"core"`` (default): ``create_mission_core`` on a fresh ``topic`` branch.
      - ``"cli_topology"``: ``spec-kitty agent mission create --topology <t>``
        on a fresh ``topic`` branch.
      - ``"cli_pr_bound"``: ``spec-kitty agent mission create --pr-bound
        --start-branch topic`` from ``main``, with a bare ``origin`` and
        ``origin/HEAD`` set (required for default-topology resolution).

    ``topology``: required (non-``None``) for ``via="core"``/``"cli_topology"``.
    ``via="cli_pr_bound"`` additionally accepts ``topology=None`` (M1): this
    is WP06's real default path -- ``--topology`` is omitted entirely and the
    resulting ``coord.topology`` is read back from ``meta.json`` (the caller
    asserts the product default, e.g. ``is MissionTopology.COORD``, itself).

    ``protected_primary=True`` configures the Primary Branch (``main``) as
    protected (``protection.protected_branches``) -- the SAME meaning for
    every ``via`` (M2), for WP06's US1.4 test.

    ``materialized=True`` additionally forces a real, production-probe-
    verified MATERIALIZED coordination surface (see
    :func:`_materialize_coord_surface` for the pre-fix-shape caveat).

    The returned shape otherwise carries only shape-agnostic invariants: it
    does NOT assume whether the coordination worktree is materialized by
    ``create`` itself, because that changes once WP06 lands. Tests that need
    a specific coordination topology state should assert it explicitly via
    :func:`~specify_cli.missions._read_path_resolver.probe_coord_state`, or
    use :func:`make_prefix_coord_mission` for the explicit pre-fix shape.
    """
    if via == "core":
        coord = _make_coord_mission_via_core(tmp_path, _require_topology(topology, via), slug=slug, protected_primary=protected_primary)
    elif via == "cli_topology":
        coord = _make_coord_mission_via_cli_topology(tmp_path, _require_topology(topology, via), slug=slug, protected_primary=protected_primary)
    elif via == "cli_pr_bound":
        coord = _make_coord_mission_via_cli_pr_bound(tmp_path, topology, slug=slug, protected_primary=protected_primary)
    else:
        raise ValueError(f"Unknown via={via!r}")
    if materialized:
        coord = _materialize_coord_surface(coord)
    return coord


def _require_topology(topology: MissionTopology | None, via: str) -> MissionTopology:
    if topology is None:
        raise ValueError(f"topology=None is only supported for via='cli_pr_bound' (got via={via!r})")
    return topology


# ---------------------------------------------------------------------------
# T009 -- pre-fix shape builder (H1: built explicitly, independent of create)
# ---------------------------------------------------------------------------


def _mission_dir_relpath(coord: CoordMission) -> str:
    return f"{_KITTY_SPECS_DIR}/{coord.mission_dir_name}"


def _read_mission_id(coord: CoordMission) -> str:
    meta: dict[str, object] = json.loads((coord.root_mission_dir / "meta.json").read_text(encoding="utf-8"))
    mission_id = meta["mission_id"]
    if not isinstance(mission_id, str):
        raise AssertionError(f"meta.json missing a string mission_id: {meta!r}")
    return mission_id


def _read_coordination_log_blob(coord: CoordMission) -> str | None:
    """Read ``status.events.jsonl`` from the coordination branch tree, or ``None`` if absent."""
    relpath = f"{_mission_dir_relpath(coord)}/{_STATUS_LOG_FILENAME}"
    result = subprocess.run(
        ["git", "-C", str(coord.repo_root), "show", f"{coord.coordination_branch}:{relpath}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def _ensure_root_log_committed(coord: CoordMission) -> None:
    """Ensure the root checkout carries the creation events, committed on the target branch.

    Independent of where create actually put them (H1): if the root checkout
    already has them (today's base), this only commits them when they are
    not yet committed. If create instead seeded the coordination branch and
    skipped the root log (WP06's future shape), the content is carried over
    from the coordination copy.
    """
    root_log = coord.root_mission_dir / _STATUS_LOG_FILENAME
    already_committed = coord_tree_has(coord.repo_root, coord.target_branch, f"{_mission_dir_relpath(coord)}/{_STATUS_LOG_FILENAME}")
    if root_log.exists() and event_ids(root_log):
        if not already_committed:
            _commit_root_events(coord, f"chore({coord.mission_dir_name}): fixture root log")
        return

    content = _read_coordination_log_blob(coord)
    if content is None:
        raise AssertionError("neither the root checkout nor the coordination branch carries the creation events")
    root_log.parent.mkdir(parents=True, exist_ok=True)
    root_log.write_text(content, encoding="utf-8")
    _commit_root_events(coord, f"chore({coord.mission_dir_name}): fixture root log (carried from coordination)")


def _reset_coordination_branch_to_precreate(coord: CoordMission) -> None:
    """Tear down any coordination worktree and reset the branch to the pre-create tip.

    No-op when the coordination branch already excludes the Mission dir
    (today's base, where create already cuts the branch before the scaffold
    commit).
    """
    if not coord_tree_has(coord.repo_root, coord.coordination_branch, _mission_dir_relpath(coord)):
        return
    if coord.coord_worktree_path.exists():
        _git(coord.repo_root, "worktree", "remove", "--force", str(coord.coord_worktree_path))
    _git(coord.repo_root, "worktree", "prune")
    _git(
        coord.repo_root,
        "update-ref",
        f"refs/heads/{coord.coordination_branch}",
        coord.creation_base_sha,
    )


def _rewrite_into_prefix_shape(coord: CoordMission) -> None:
    """Transform *coord* (whatever create produced) into the explicit pre-fix shape.

    H1 (blocking): built explicitly rather than trusted from create's current
    placement, so this keeps producing the documented shape whether create
    already cuts the coordination branch before the scaffold commit (today),
    or seeds the coordination branch with the Mission dir and skips the root
    log entirely (WP06's future shape) -- see
    ``test_rewrite_into_prefix_shape_is_independent_of_create_placement`` for
    the proof against a simulated post-fix create output.
    """
    _ensure_root_log_committed(coord)
    _reset_coordination_branch_to_precreate(coord)


def _append_extra_root_events(coord: CoordMission, count: int) -> None:
    """Append *count* uncommitted lane-transition events to the root checkout's log."""
    for _ in range(count):
        event = StatusEvent(
            event_id=str(_ulid_mod.ULID()),
            mission_slug=coord.mission_dir_name,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at=now_utc_iso(),
            actor="fixture",
            force=False,
            execution_mode="direct_repo",
        )
        append_event(coord.root_mission_dir, event)


def _convert_branch_to_remote_only(coord: CoordMission) -> None:
    """Push the coordination branch to a bare remote, then delete the local head.

    #4970: the branch stays reachable only via ``refs/remotes/<remote>/...``.
    """
    remote_dir = coord.repo_root.parent / f"{coord.repo_root.name}-coord-remote.git"
    subprocess.run(
        ["git", "init", "--bare", "-b", _PRIMARY_BRANCH, str(remote_dir)],
        capture_output=True,
        text=True,
        check=True,
    )
    _git(coord.repo_root, "remote", "add", "coord-remote", str(remote_dir))
    _git(coord.repo_root, "push", "coord-remote", coord.coordination_branch)
    _git(coord.repo_root, "fetch", "coord-remote", coord.coordination_branch)
    _git(coord.repo_root, "branch", "-D", coord.coordination_branch)


def _expected_prefix_state(*, worktree: _PrefixWorktree, remote_only: bool, branch_deleted: bool) -> CoordState:
    if branch_deleted:
        return CoordState.DELETED
    if remote_only:
        return CoordState.UNMATERIALIZED
    if worktree == "empty":
        return CoordState.EMPTY
    return CoordState.UNMATERIALIZED


def _assert_prefix_shape(
    coord: CoordMission,
    *,
    worktree: _PrefixWorktree,
    remote_only: bool,
    branch_deleted: bool,
) -> None:
    expected = _expected_prefix_state(worktree=worktree, remote_only=remote_only, branch_deleted=branch_deleted)
    actual = probe_coord_state(
        coord.repo_root,
        coord.mission_dir_name,
        coord.mid8,
        coordination_branch=coord.coordination_branch,
    )
    if actual is not expected:
        raise AssertionError(
            f"make_prefix_coord_mission built {actual} but expected {expected} (worktree={worktree!r}, remote_only={remote_only}, branch_deleted={branch_deleted})"
        )
    if not branch_deleted and coord_tree_has(coord.repo_root, coord.coordination_branch, _mission_dir_relpath(coord)):
        raise AssertionError("coordination branch unexpectedly contains the mission dir")


def make_prefix_coord_mission(
    tmp_path: Path,
    topology: MissionTopology,
    *,
    worktree: _PrefixWorktree = "empty",
    remote_only: bool = False,
    branch_deleted: bool = False,
    extra_events: int = 0,
) -> CoordMission:
    """Build the **pre-fix shape**: Mission created before this fix.

    The root checkout's ``status.events.jsonl`` (``MissionCreated`` +
    ``SpecifyStarted``) is committed on the target branch; the coordination
    branch is cut at the commit BEFORE that scaffold commit, so it never
    contains the Mission dir. This shape is built EXPLICITLY via
    :func:`_rewrite_into_prefix_shape` (H1) -- never merely asserted from
    whatever ``create_mission_core`` happened to produce -- so it keeps
    working after WP06 changes create's placement, then validated against
    the production probe (NFR-002 "fail loud").

    ``worktree="empty"`` (default) materializes the coordination worktree
    (its Mission dir stays absent -> ``EMPTY``). ``worktree="absent"`` never
    touches the worktree (-> ``UNMATERIALIZED``). ``remote_only=True`` and
    ``branch_deleted=True`` override the worktree variant (a deleted/
    remote-only branch cannot have a materialized worktree).
    """
    coord = _make_coord_mission_via_core(tmp_path, topology, slug="prefix", protected_primary=False)
    _rewrite_into_prefix_shape(coord)
    if extra_events:
        _append_extra_root_events(coord, extra_events)
    if remote_only:
        _convert_branch_to_remote_only(coord)
    elif branch_deleted:
        _git(coord.repo_root, "branch", "-D", coord.coordination_branch)
    elif worktree == "empty":
        CoordinationWorkspace.resolve(coord.repo_root, coord.mission_dir_name, coord.mid8)
    _assert_prefix_shape(coord, worktree=worktree, remote_only=remote_only, branch_deleted=branch_deleted)
    return coord


# ---------------------------------------------------------------------------
# T010 -- NFR-002 fork fixtures
# ---------------------------------------------------------------------------


def _to_fork_fixture(
    coord: CoordMission,
    *,
    decision_ids_root: tuple[str, ...] = (),
    decision_ids_coord: tuple[str, ...] = (),
    clone_root: Path | None = None,
) -> ForkFixture:
    return ForkFixture(
        repo_root=coord.repo_root,
        mission_slug=coord.mission_slug,
        mid8=coord.mid8,
        mission_dir_name=coord.mission_dir_name,
        topology=coord.topology,
        target_branch=coord.target_branch,
        coordination_branch=coord.coordination_branch,
        coord_worktree_path=coord.coord_worktree_path,
        creation_base_sha=coord.creation_base_sha,
        decision_ids_root=decision_ids_root,
        decision_ids_coord=decision_ids_coord,
        clone_root=clone_root,
    )


def _append_row(path: Path, row: dict[str, object]) -> None:
    """Append one production-shaped event dict directly to an explicit *path*.

    H3: the fixture, not the live surface resolver, decides where each row
    lands. Uses the public, envelope-agnostic, atomic-write primitive
    (``append_raw_rows_atomic``) -- the same durability mechanism production
    code uses for both ``status.events.jsonl`` and sibling logs.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    append_raw_rows_atomic(path, [row])


def _decision_point_opened_row(*, decision_id: str, mission_id: str, mission_slug: str, input_key: str, question: str, actor: str) -> dict[str, object]:
    """Build a production-shaped ``DecisionPointOpened`` row (the ``status.events.jsonl`` stream).

    Mirrors ``specify_cli.decisions.emit.emit_decision_opened``'s wire shape
    exactly (same payload model, same envelope keys), but never calls it --
    H3 requires the fixture to choose placement, not the live write path.
    """
    now = now_utc()
    payload = DecisionPointOpenedInterviewPayload(
        origin_surface=OriginSurface.PLANNING_INTERVIEW,
        decision_point_id=decision_id,
        mission_id=mission_id,
        run_id=decision_id,
        mission_slug=mission_slug,
        mission_type=_DECISION_MISSION_TYPE,
        phase=OriginFlow.SPECIFY.value.upper(),
        origin_flow=_EventOriginFlow(OriginFlow.SPECIFY.value),
        question=question,
        options=(),
        input_key=input_key,
        step_id=input_key,
        actor_id=actor,
        actor_type="human",
        state_entered_at=now,
        recorded_at=now,
    )
    return {
        "event_id": str(_ulid_mod.ULID()),
        "at": now.isoformat(),
        "event_type": DECISION_POINT_OPENED,
        "payload": json.loads(payload.model_dump_json()),
    }


def _decision_input_requested_row(*, decision_id: str, mission_id: str, mission_slug: str, input_key: str, question: str, actor: str) -> dict[str, object]:
    """Build a production-shaped ``DecisionInputRequested`` row (the ``decisions.events.jsonl`` stream).

    Mirrors ``specify_cli.events.decision_log.DecisionGitLog``'s wire shape
    (same payload model, same envelope keys), written directly to an explicit
    path instead of through that class's commit-triggering machinery (H3).
    """
    actor_identity = RuntimeActorIdentity(
        actor_id=actor,
        actor_type="human",
        display_name="",
        provider=None,
        model=None,
        tool=None,
    )
    payload = DecisionInputRequestedPayload(
        run_id=decision_id,
        decision_id=decision_id,
        step_id=input_key,
        question=question,
        options=(),
        input_key=input_key,
        actor=actor_identity,
        mission_id=mission_id,
        mission_slug=mission_slug,
    )
    return {
        "at": now_utc_iso(),
        "event_id": str(_ulid_mod.ULID()),
        "event_type": DECISION_INPUT_REQUESTED,
        "mission_id": mission_id,
        "payload": payload.model_dump(mode="json"),
    }


def _stream_filename(stream: Literal["status_log", "decision_log"]) -> str:
    return _STATUS_LOG_FILENAME if stream == "status_log" else _DECISION_LOG_FILENAME


def _append_diverging_rows_for_stream(coord: CoordMission, stream: Literal["status_log", "decision_log"], *, mission_id: str) -> tuple[str, str]:
    """Append one row to the root Mission dir and a different row to the coordination
    Mission dir, for the named *stream*. Returns ``(root_decision_id, coord_decision_id)``.
    """
    root_id = str(_ulid_mod.ULID())
    coord_id = str(_ulid_mod.ULID())
    filename = _stream_filename(stream)
    root_row: dict[str, object]
    coord_row: dict[str, object]
    if stream == "status_log":
        root_row = _decision_point_opened_row(
            decision_id=root_id,
            mission_id=mission_id,
            mission_slug=coord.mission_dir_name,
            input_key="root-slot",
            question="Root decision?",
            actor="fixture-root",
        )
        coord_row = _decision_point_opened_row(
            decision_id=coord_id,
            mission_id=mission_id,
            mission_slug=coord.mission_dir_name,
            input_key="coord-slot",
            question="Coord decision?",
            actor="fixture-coord",
        )
    else:
        root_row = _decision_input_requested_row(
            decision_id=root_id,
            mission_id=mission_id,
            mission_slug=coord.mission_dir_name,
            input_key="root-slot",
            question="Root decision?",
            actor="fixture-root",
        )
        coord_row = _decision_input_requested_row(
            decision_id=coord_id,
            mission_id=mission_id,
            mission_slug=coord.mission_dir_name,
            input_key="coord-slot",
            question="Coord decision?",
            actor="fixture-coord",
        )
    _append_row(coord.root_mission_dir / filename, root_row)
    _append_row(coord.coord_mission_dir / filename, coord_row)
    return root_id, coord_id


def _assert_fork_pair_diverges(coord: CoordMission, streams: tuple[Literal["status_log", "decision_log"], ...]) -> None:
    """H3: the builder self-checks its own fork shape rather than trusting the self-tests."""
    for stream in streams:
        filename = _stream_filename(stream)
        root_ids = event_ids(coord.root_mission_dir / filename)
        coord_ids = event_ids(coord.coord_mission_dir / filename)
        if not root_ids or not coord_ids:
            raise AssertionError(f"fork fixture stream {stream!r} did not diverge: root={root_ids!r} coord={coord_ids!r}")
        root_set, coord_set = set(root_ids), set(coord_ids)
        if root_set <= coord_set or coord_set <= root_set:
            raise AssertionError(f"fork fixture stream {stream!r} is not a true fork: root={root_ids!r} coord={coord_ids!r}")


def _commit_root_events(coord: CoordMission, message: str) -> None:
    rel = coord.root_mission_dir.relative_to(coord.repo_root)
    _git(coord.repo_root, "add", "-A", str(rel))
    _git(coord.repo_root, "commit", "-m", message)


def _commit_coord_events(coord: CoordMission, message: str) -> None:
    rel = coord.coord_mission_dir.relative_to(coord.coord_worktree_path)
    _git(coord.coord_worktree_path, "add", "-A", str(rel))
    _git(coord.coord_worktree_path, "commit", "-m", message)


def _fork_streams(stream: _ForkStream) -> tuple[Literal["status_log", "decision_log"], ...]:
    return ("status_log", "decision_log") if stream == "both" else (stream,)


def _build_diverging_decision_pair(
    tmp_path: Path, topology: MissionTopology, *, commit: bool, stream: _ForkStream
) -> tuple[CoordMission, tuple[str, ...], tuple[str, ...]]:
    """Build the (a)/(b) fork shapes for the chosen *stream* (H2/H3 binding correction).

    Appends production-shaped rows via low-level primitives directly into
    explicitly chosen paths -- the root Mission dir and the coordination
    Mission dir -- rather than through ``open_decision``/the live surface
    resolver (H3), so the fixture's shape never depends on how later WPs
    (seed-on-write, fork refusal, ``write_dir``) change that routing. The
    builder asserts its own fork shape before returning (H3).
    """
    coord = make_prefix_coord_mission(tmp_path, topology, worktree="absent")
    mission_id = _read_mission_id(coord)
    CoordinationWorkspace.resolve(coord.repo_root, coord.mission_dir_name, coord.mid8)
    coord.coord_mission_dir.mkdir(parents=True, exist_ok=True)

    streams = _fork_streams(stream)
    root_ids: list[str] = []
    coord_ids: list[str] = []
    for one_stream in streams:
        root_id, coord_id = _append_diverging_rows_for_stream(coord, one_stream, mission_id=mission_id)
        root_ids.append(root_id)
        coord_ids.append(coord_id)

    _assert_fork_pair_diverges(coord, streams)

    if commit:
        _commit_root_events(coord, f"chore({coord.mission_dir_name}): fixture root decision ({stream})")
        _commit_coord_events(coord, f"chore({coord.mission_dir_name}): fixture coord decision ({stream})")
    return coord, tuple(root_ids), tuple(coord_ids)


def _clone_repo_with_branches(repo: Path, clone_root: Path, branches: tuple[str, ...]) -> None:
    """Clone *repo* and ensure each of *branches* exists locally, tracking ``origin/<branch>``.

    ``git clone`` already materializes a local branch for the source repo's
    checked-out HEAD branch (tracking its ``origin/<branch>``); only the
    remaining branches need an explicit local head created from their
    fetched remote-tracking ref.
    """
    subprocess.run(
        ["git", "clone", str(repo), str(clone_root)],
        capture_output=True,
        text=True,
        check=True,
    )
    existing = {line.strip().lstrip("* ") for line in _git(clone_root, "branch", "--format=%(refname:short)").stdout.splitlines() if line.strip()}
    for branch in branches:
        if branch not in existing:
            _git(clone_root, "branch", branch, f"origin/{branch}")


def _seed_ledger_only_fixture(coord: CoordMission) -> str:
    """Write the decision ledger directly onto the coordination branch (pre-fix #3928).

    Uses the production ``decisions.store`` read/write primitives, pointed
    explicitly at the coordination worktree's Mission dir -- never through
    ``placement_seam``, which (post #4966 AC-D2) routes the ledger to the
    PRIMARY partition. Built with git plumbing because the current
    production routing cannot reproduce this placement any more.
    """
    CoordinationWorkspace.resolve(coord.repo_root, coord.mission_dir_name, coord.mid8)
    coord_dir = coord.coord_mission_dir
    coord_dir.mkdir(parents=True, exist_ok=True)
    mission_id = _read_mission_id(coord)

    entry = IndexEntry(
        decision_id=str(_ulid_mod.ULID()),
        origin_flow=OriginFlow.SPECIFY,
        slot_key="ledger-only-slot",
        input_key="ledger-only-key",
        question="Ledger-only fixture question?",
        status=DecisionStatus.OPEN,
        created_at=now_utc(),
        mission_id=mission_id,
        mission_slug=coord.mission_dir_name,
    )
    decision_store.append_entry(coord_dir, entry)
    decision_store.write_artifact(coord_dir, entry)
    _commit_coord_events(coord, f"chore({coord.mission_dir_name}): ledger-only fixture")
    decision_id: str = entry.decision_id
    return decision_id


def _fork_fixture_root_uncommitted(tmp_path: Path, topology: MissionTopology, *, stream: _ForkStream) -> ForkFixture:
    coord, root_ids, coord_ids = _build_diverging_decision_pair(tmp_path, topology, commit=False, stream=stream)
    return _to_fork_fixture(coord, decision_ids_root=root_ids, decision_ids_coord=coord_ids)


def _fork_fixture_both_committed(tmp_path: Path, topology: MissionTopology, *, stream: _ForkStream) -> ForkFixture:
    coord, root_ids, coord_ids = _build_diverging_decision_pair(tmp_path, topology, commit=True, stream=stream)
    return _to_fork_fixture(coord, decision_ids_root=root_ids, decision_ids_coord=coord_ids)


def _fork_fixture_fresh_clone(tmp_path: Path, topology: MissionTopology, *, stream: _ForkStream) -> ForkFixture:
    base = _fork_fixture_both_committed(tmp_path / "base", topology, stream=stream)
    clone_root = tmp_path / "clone"
    _clone_repo_with_branches(base.repo_root, clone_root, (base.target_branch, base.coordination_branch))
    return _to_fork_fixture(
        base,
        decision_ids_root=base.decision_ids_root,
        decision_ids_coord=base.decision_ids_coord,
        clone_root=clone_root,
    )


def _fork_fixture_ledger_only(tmp_path: Path, topology: MissionTopology) -> ForkFixture:
    coord = make_prefix_coord_mission(tmp_path, topology, worktree="absent")
    decision_id = _seed_ledger_only_fixture(coord)
    return _to_fork_fixture(coord, decision_ids_coord=(decision_id,))


def make_fork_fixture(
    tmp_path: Path,
    shape: _ForkShape,
    topology: MissionTopology = MissionTopology.COORD,
    *,
    stream: _ForkStream = "status_log",
) -> ForkFixture:
    """Build one of the four NFR-002 fork shapes (SC-004: 0 entries/events lost, no id twice).

    - ``"root_uncommitted_coord_untracked"`` (the #5519 shape): a decision
      row appended to the root checkout (uncommitted), then a second,
      diverging row appended once the coordination Mission dir exists
      (untracked in the coordination worktree).
    - ``"both_committed"``: like (a), but both copies are committed on their
      respective branches.
    - ``"fresh_clone"``: a ``git clone`` of (b), with both branches fetched
      as local branches and no coordination worktree.
    - ``"ledger_only_on_coordination"``: ``decisions/index.json`` +
      ``decisions/DM-<id>.md`` committed only on the coordination branch
      (the pre-fix #3928 placement), absent from the root checkout.

    ``stream`` (H2 binding correction; shapes (a)/(b)/(c) only -- ignored for
    (d), whose divergence is about the ledger, not an event stream):
      - ``"status_log"`` (default): the divergence is in ``status.events.jsonl``.
      - ``"decision_log"``: the divergence is in ``decisions.events.jsonl``
        (the ``DecisionGitLog`` stream).
      - ``"both"``: both streams diverge independently.
    """
    if shape == "root_uncommitted_coord_untracked":
        return _fork_fixture_root_uncommitted(tmp_path, topology, stream=stream)
    if shape == "both_committed":
        return _fork_fixture_both_committed(tmp_path, topology, stream=stream)
    if shape == "fresh_clone":
        return _fork_fixture_fresh_clone(tmp_path, topology, stream=stream)
    if shape == "ledger_only_on_coordination":
        return _fork_fixture_ledger_only(tmp_path, topology)
    raise ValueError(f"Unknown fork fixture shape: {shape!r}")


# ---------------------------------------------------------------------------
# T010 -- pure probes
# ---------------------------------------------------------------------------


def _read_source(source: ProbeSource) -> str:
    """Return the text content a probe source names, or ``""`` when absent."""
    if isinstance(source, Path):
        return source.read_text(encoding="utf-8") if source.exists() else ""
    repo, ref, relpath = source
    result = subprocess.run(
        ["git", "-C", str(repo), "show", f"{ref}:{relpath}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else ""


def _jsonl_rows(content: str) -> list[dict[str, object]]:
    return [json.loads(line) for line in content.splitlines() if line.strip()]


def event_ids(source: ProbeSource) -> tuple[str, ...]:
    """Return the ``event_id`` of every row in a JSONL event log."""
    return tuple(str(row["event_id"]) for row in _jsonl_rows(_read_source(source)))


def _row_lamport(row: dict[str, object]) -> int | None:
    """Extract a row's logical clock, tolerating its absence (brownfield CORRECTION).

    Status rows may carry ``lamport_clock`` (lifecycle envelope); decision
    rows may carry ``event_lamport`` under ``payload``; ``MissionCreated``
    and plain lane-transition rows carry neither.
    """
    if "lamport_clock" in row:
        value = row["lamport_clock"]
        return int(value) if isinstance(value, int) else None
    payload = row.get("payload")
    if isinstance(payload, dict) and "event_lamport" in payload:
        value = payload["event_lamport"]
        return int(value) if isinstance(value, int) else None
    return None


def lamports(source: ProbeSource) -> tuple[int | None, ...]:
    """Return each row's logical clock (``None`` where the row carries none)."""
    return tuple(_row_lamport(row) for row in _jsonl_rows(_read_source(source)))


def commits_touching(repo: Path, rev_range: str, relpath: str) -> list[str]:
    """Return the commit SHAs in *rev_range* that touched *relpath*, newest first."""
    result = subprocess.run(
        ["git", "-C", str(repo), "log", "--format=%H", rev_range, "--", relpath],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def coord_tree_has(repo: Path, branch: str, relpath: str) -> bool:
    """Return whether *branch*'s tree contains *relpath* (file or directory)."""
    result = subprocess.run(
        ["git", "-C", str(repo), "ls-tree", branch, "--", relpath],
        capture_output=True,
        text=True,
        check=False,
    )
    return bool(result.stdout.strip())


def index_entry_ids(source: ProbeSource) -> set[str]:
    """Return every ``decision_id`` in a ``decisions/index.json`` document."""
    content = _read_source(source)
    if not content.strip():
        return set()
    data = json.loads(content)
    return {str(entry["decision_id"]) for entry in data.get("entries", [])}
