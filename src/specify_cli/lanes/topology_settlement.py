"""S7 settlement of a provisional Mission's topology at its first finalize (#7282).

ADR 2026-11-06-3. A Mission created without ``--topology`` is provisional
(``topology_source: default``, ``topology_settled: false``): it is stored as a
minted ``single_branch`` Mission whose write checkout holds the Mission topic
branch. Its first ``finalize-tasks`` settles the topology once, by size, before
the run's first status write and before any work package is claimed:

* :func:`decide_topology_by_size` is the pure size rule (FR-053): ``single_branch``
  when at most two non-canceled WPs or at most one code lane, else
  ``lanes_with_coord`` with the topic branch as the coordination branch, on every
  target. It answers ``None`` for every settled Mission (FR-054 / FR-057).
* :func:`settle_topology` applies the decision. ``single_branch`` writes only the
  settled keys. ``lanes_with_coord`` runs a plan of reversible steps (FR-055):
  commit the Mission directory on the topic branch, move the repository root
  checkout to ``create_return_branch``, materialize the coordination worktree on
  the topic branch, re-stamp ``meta.json`` there and write ``lanes.json``. Any
  failure runs the undo stack in reverse and raises
  :class:`TopologySettlementRefused` (FR-056 / NFR-003): ``meta.json``
  byte-identical, every branch tip unchanged, no coordination worktree, the root
  checkout back on the topic branch.

Git forbids one branch checked out in two worktrees, so the root checkout moves
before the coordination worktree is added. The ``meta.json`` re-stamp therefore
runs in the coordination worktree, the only checkout of the topic branch once the
root has moved; the finalize commit later carries it.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kernel.git import GitPath, status_entries
from specify_cli.lanes.branch_naming import lane_branch_ref_glob

logger = logging.getLogger(__name__)

__all__ = [
    "SettlementHandle",
    "TopologyDecision",
    "TopologySettlementRefused",
    "decide_topology_by_size",
    "decision_payload",
    "settle_topology",
]

TOPOLOGY_SETTLEMENT_REFUSED = "TOPOLOGY_SETTLEMENT_REFUSED"
RULE_WP_COUNT_LE_2 = "wp_count_le_2"
RULE_CODE_LANES_LE_1 = "code_lanes_le_1"
RULE_LANES_WITH_COORD = "lanes_with_coord"

_SINGLE_BRANCH = "single_branch"
_LANES_WITH_COORD = "lanes_with_coord"
_DEFAULT_SOURCE = "default"
_WP_COUNT_LIMIT = 2
_CODE_LANE_LIMIT = 1
_KITTY_SPECS = "kitty-specs"


class TopologySettlementRefused(Exception):
    """Settlement could not complete; it was compensated and the Mission stays provisional."""

    error_code: str = TOPOLOGY_SETTLEMENT_REFUSED

    def __init__(self, message: str) -> None:
        super().__init__(f"{TOPOLOGY_SETTLEMENT_REFUSED}: {message}")


@dataclass(frozen=True)
class TopologyDecision:
    """The size rule's answer for one provisional Mission (FR-053)."""

    rule: str
    wp_count: int
    code_lane_count: int
    from_topology: str
    to_topology: str
    target_protected: bool

    def as_meta(self) -> dict[str, Any]:
        """The ``topology_decision`` value recorded in ``meta.json``."""
        return {
            "rule": self.rule,
            "wp_count": self.wp_count,
            "code_lane_count": self.code_lane_count,
            "from": self.from_topology,
            "to": self.to_topology,
            "target_protected": self.target_protected,
        }


def is_provisional(meta: Mapping[str, object]) -> bool:
    """True only for a ``topology_source: default`` Mission that has not settled yet."""
    return meta.get("topology_source") == _DEFAULT_SOURCE and meta.get("topology_settled") is False


def decide_topology_by_size(
    meta: Mapping[str, object],
    *,
    wp_count: int,
    code_lane_count: int,
    target_protected: bool,
) -> TopologyDecision | None:
    """The FR-053 size rule, or ``None`` when the Mission is already settled (FR-054 / FR-057).

    Pure. ``wp_count`` counts the non-canceled WPs, planning-artifact WPs included;
    ``code_lane_count`` excludes ``lane-planning``. Two WPs or two code lanes is a
    tie and settles ``single_branch``; zero code lanes settles ``single_branch``.
    """
    if not is_provisional(meta):
        return None
    if wp_count <= _WP_COUNT_LIMIT:
        rule, to_topology = RULE_WP_COUNT_LE_2, _SINGLE_BRANCH
    elif code_lane_count <= _CODE_LANE_LIMIT:
        rule, to_topology = RULE_CODE_LANES_LE_1, _SINGLE_BRANCH
    else:
        rule, to_topology = RULE_LANES_WITH_COORD, _LANES_WITH_COORD
    return TopologyDecision(
        rule=rule,
        wp_count=wp_count,
        code_lane_count=code_lane_count,
        from_topology=str(meta.get("topology") or _SINGLE_BRANCH),
        to_topology=to_topology,
        target_protected=target_protected,
    )


def decision_payload(
    meta: Mapping[str, object] | None,
    decision: TopologyDecision | None,
    *,
    settled_this_run: bool,
    preview: bool,
) -> dict[str, Any]:
    """The ``topology_decision`` JSON object (``contracts/finalize-tasks-json.md``)."""
    source = (meta or {}).get("topology_source")
    if decision is None:
        return {
            "settled_this_run": False,
            "topology_source": source,
            "provisional_topology": None,
            "settled_topology": (meta or {}).get("topology"),
            "rule": None,
            "wp_count": None,
            "code_lane_count": None,
            "target_protected": None,
            "preview": preview,
        }
    return {
        "settled_this_run": settled_this_run,
        "topology_source": source,
        "provisional_topology": decision.from_topology,
        "settled_topology": decision.to_topology,
        "rule": decision.rule,
        "wp_count": decision.wp_count,
        "code_lane_count": decision.code_lane_count,
        "target_protected": decision.target_protected,
        "preview": preview,
    }


# ---------------------------------------------------------------------------
# The reversible plan
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SettlementStep:
    """One reversible settlement step: ``apply`` it, and ``undo`` it on a later failure."""

    name: str
    apply: Callable[[], None]
    undo: Callable[[], None]


def _undo_all(done: list[SettlementStep]) -> list[str]:
    """Run the undos in reverse; return the names whose undo itself failed (logged, never raised)."""
    failed: list[str] = []
    for step in reversed(done):
        try:
            step.undo()
        except Exception:  # noqa: BLE001 -- every undo must run; a failed one is reported by name
            logger.exception("topology settlement: undo of step %r failed", step.name)
            failed.append(step.name)
    return failed


def run_settlement_plan(steps: list[SettlementStep], *, remedy: str) -> list[SettlementStep]:
    """Apply *steps* in order; on any failure undo the applied ones in reverse and refuse.

    Returns the applied steps (the undo stack a later finalize failure compensates
    with). Raises :class:`TopologySettlementRefused` naming the failed step, the
    cause and *remedy*; an undo that itself fails is named too.
    """
    done: list[SettlementStep] = []
    for step in steps:
        try:
            step.apply()
        except Exception as exc:
            # The failed step may have taken effect before it raised: its undo runs too
            # (every undo is idempotent and does nothing for an effect that is absent).
            failed_undos = _undo_all([*done, step])
            detail = f" Compensation could not undo: {', '.join(failed_undos)}." if failed_undos else ""
            raise TopologySettlementRefused(f"step {step.name!r} failed: {exc}. {remedy}{detail}") from exc
        done.append(step)
    return done


@dataclass
class SettlementHandle:
    """What one settlement did, so a later failure of the same finalize run can undo it.

    ``planning_dir`` is the Mission directory every later phase of the run reads and
    writes: unchanged for ``single_branch``, the coordination worktree's copy for
    ``lanes_with_coord``.
    """

    decision: TopologyDecision
    planning_dir: Path
    applied: list[SettlementStep] = field(default_factory=list)
    coord_snapshot: dict[Path, bytes] | None = None

    def compensate(self) -> list[str]:
        """Undo the settlement after a later failure of the run; return undos that failed.

        The coordination worktree's Mission directory first goes back to the bytes it
        held when settlement finished (the run's later writes are discarded with the
        settlement), so the guarded worktree removal finds it clean.
        """
        if self.coord_snapshot is not None:
            _restore_dir(self.planning_dir, self.coord_snapshot)
        failed = _undo_all(self.applied)
        self.applied = []
        return failed


def _snapshot_dir(directory: Path) -> dict[Path, bytes]:
    return {path: path.read_bytes() for path in directory.rglob("*") if path.is_file()}


def _restore_dir(directory: Path, snapshot: Mapping[Path, bytes]) -> None:
    for path in [p for p in directory.rglob("*") if p.is_file()]:
        if path not in snapshot:
            path.unlink()
    for path, data in snapshot.items():
        if not path.is_file() or path.read_bytes() != data:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)


# ---------------------------------------------------------------------------
# Git primitives
# ---------------------------------------------------------------------------


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)


def _git_ok(root: Path, *args: str) -> str:
    result = _git(root, *args)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {(result.stderr or result.stdout).strip()}")
    return result.stdout.strip()


def _branch_tip(root: Path, branch: str) -> str | None:
    result = _git(root, "rev-parse", "--verify", "-q", f"refs/heads/{branch}")
    return result.stdout.strip() if result.returncode == 0 else None


def _current_branch(root: Path) -> str | None:
    result = _git(root, "symbolic-ref", "-q", "--short", "HEAD")
    return result.stdout.strip() if result.returncode == 0 else None


def _checkouts_holding(root: Path, branch: str) -> list[Path]:
    porcelain = _git_ok(root, "worktree", "list", "--porcelain")
    holders: list[Path] = []
    current: Path | None = None
    for line in porcelain.splitlines():
        if line.startswith("worktree "):
            current = Path(line[len("worktree ") :])
        elif line == f"branch refs/heads/{branch}" and current is not None:
            holders.append(current)
    return holders


# ---------------------------------------------------------------------------
# Preconditions (checked before step 1; nothing is changed by a refusal)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _SettlementContext:
    repo_root: Path
    mission_dir_name: str
    mid8: str
    topic: str
    return_branch: str

    @property
    def mission_rel(self) -> str:
        return f"{_KITTY_SPECS}/{self.mission_dir_name}"


def _refuse(message: str) -> TopologySettlementRefused:
    return TopologySettlementRefused(message)


def _required_text(meta: Mapping[str, object], key: str, dir_name: str) -> str:
    value = meta.get(key)
    if not isinstance(value, str) or not value.strip():
        raise _refuse(f"{dir_name}: meta.json records no {key}; the Mission cannot settle to lanes_with_coord.")
    return value.strip()


def _context_from(repo_root: Path, planning_dir: Path, meta: Mapping[str, object]) -> _SettlementContext:
    from specify_cli.mission_metadata import recorded_mid8

    dir_name = planning_dir.name
    return _SettlementContext(
        repo_root=repo_root,
        mission_dir_name=dir_name,
        mid8=recorded_mid8(meta),
        topic=_required_text(meta, "mission_branch", dir_name),
        return_branch=_required_text(meta, "create_return_branch", dir_name),
    )


def _check_write_checkout(ctx: _SettlementContext) -> None:
    """``WRITE_CHECKOUT_OCCUPIED`` / ``WRITE_CHECKOUT_DIRTY`` through the switch core's rules (#5676)."""
    from specify_cli.core.mission_creation_errors import WriteCheckoutSwitchDirtyError, WriteCheckoutSwitchOccupiedError
    from specify_cli.lanes.checkout_occupancy import in_progress_wps_in_write_checkout

    occupants = in_progress_wps_in_write_checkout(ctx.repo_root, ctx.repo_root)
    if occupants:
        named = ", ".join(f"{slug}/{wp_id}" for slug, wp_id in occupants)
        raise WriteCheckoutSwitchOccupiedError(
            f"{WriteCheckoutSwitchOccupiedError.error_code}: cannot settle the topology: {named} is in_progress in the write checkout "
            f"{ctx.repo_root}. Finish or move that work package first, then retry."
        )
    owned = GitPath.parse(ctx.mission_rel)
    dirty = [str(entry.path) for entry in status_entries(ctx.repo_root, untracked=None) if not owned.overlaps(entry.path)]
    if dirty:
        raise WriteCheckoutSwitchDirtyError(
            f"{WriteCheckoutSwitchDirtyError.error_code}: cannot settle the topology: the write checkout {ctx.repo_root} has "
            f"uncommitted changes: {', '.join(dirty)}. Commit or discard them, then retry."
        )


def _check_branches(ctx: _SettlementContext) -> None:
    if _current_branch(ctx.repo_root) != ctx.topic:
        raise _refuse(f"the repository root checkout is not on the Mission topic branch {ctx.topic!r}. Check it out, then retry.")
    if _branch_tip(ctx.repo_root, ctx.return_branch) is None:
        raise _refuse(f"create_return_branch {ctx.return_branch!r} does not exist. Recreate it (git branch {ctx.return_branch} <commit>), then retry.")
    holders = _checkouts_holding(ctx.repo_root, ctx.return_branch)
    if holders:
        raise _refuse(f"create_return_branch {ctx.return_branch!r} is checked out in {holders[0]}. Switch that checkout to another branch, then retry.")
    lane_refs = _git_ok(ctx.repo_root, "for-each-ref", "--format=%(refname)", lane_branch_ref_glob(ctx.topic))
    if lane_refs:
        raise _refuse(f"lane branches already exist for {ctx.topic!r} ({lane_refs.splitlines()[0]}); a started Mission never re-settles.")


def _check_not_started(planning_dir: Path) -> None:
    from specify_cli.status import read_events

    started = sorted({str(event.wp_id) for event in read_events(planning_dir) if str(event.to_lane) != "planned"})
    if started:
        raise _refuse(f"work packages already moved past planned ({', '.join(started)}); a started Mission never re-settles.")


def _check_coord_worktree_absent(ctx: _SettlementContext) -> None:
    from specify_cli.coordination.workspace import CoordinationWorkspace

    path = CoordinationWorkspace.worktree_path(ctx.repo_root, ctx.mission_dir_name, ctx.mid8)
    if path.exists():
        raise _refuse(f"a coordination worktree already exists at {path}. Remove it (spec-kitty context cleanup), then retry.")


# ---------------------------------------------------------------------------
# The lanes_with_coord steps
# ---------------------------------------------------------------------------


@dataclass
class _CoordPlan:
    ctx: _SettlementContext
    decision: TopologyDecision
    write_lanes: Callable[[Path], None]
    topic_tip_before: str = ""
    settlement_commit: str = ""
    committed: bool = False
    coord_dir: Path | None = None
    coord_meta_before: bytes | None = None
    lanes_before: bytes | None = None

    def commit_mission_dir(self) -> None:
        root = self.ctx.repo_root
        self.topic_tip_before = _git_ok(root, "rev-parse", "HEAD")
        _git_ok(root, "add", "-A", "--", self.ctx.mission_rel)
        if _git(root, "diff", "--cached", "--quiet").returncode == 0:
            return
        _git_ok(root, "commit", "-q", "--no-verify", "-m", f"chore({self.ctx.mission_dir_name}): planning state before topology settlement")
        self.settlement_commit = _git_ok(root, "rev-parse", "HEAD")
        self.committed = True

    def uncommit_mission_dir(self) -> None:
        root = self.ctx.repo_root
        if self.committed:
            ref = f"refs/heads/{self.ctx.topic}"
            live_tip = _git_ok(root, "rev-parse", ref)
            if live_tip != self.settlement_commit:
                # #7276: never rewind past commits made after the settlement commit.
                raise _refuse(
                    f"the topic branch {self.ctx.topic!r} moved past the settlement commit "
                    f"{self.settlement_commit} (now {live_tip}); it was kept. Revert the settlement "
                    "commit by hand if it must go."
                )
            # Compare-and-swap on the commit this run made: a concurrent move still fails closed.
            _git_ok(root, "update-ref", ref, self.topic_tip_before, self.settlement_commit)
            self.committed = False
        _git_ok(root, "reset", "-q")

    def move_root_checkout(self) -> None:
        from specify_cli.core.write_checkout_switch import switch_write_checkout

        switch_write_checkout(
            self.ctx.repo_root,
            self.ctx.return_branch,
            start_point=None,
            repository_root=self.ctx.repo_root,
            owned_paths=(self.ctx.mission_rel,),
        )

    def return_root_checkout(self) -> None:
        if _current_branch(self.ctx.repo_root) != self.ctx.topic:
            _git_ok(self.ctx.repo_root, "checkout", "-q", self.ctx.topic)

    def materialize_coord_worktree(self) -> None:
        from specify_cli.coordination.workspace import CoordinationWorkspace

        worktree = CoordinationWorkspace.resolve(self.ctx.repo_root, self.ctx.mission_dir_name, self.ctx.mid8)
        self.coord_dir = worktree / _KITTY_SPECS / self.ctx.mission_dir_name

    def remove_coord_worktree(self) -> None:
        from specify_cli.coordination.workspace import CoordinationWorkspace

        CoordinationWorkspace.teardown(self.ctx.repo_root, self.ctx.mission_dir_name, self.ctx.mid8)

    def restamp_meta(self) -> None:
        from specify_cli.mission_metadata import restamp_topic_branch_as_coordination

        coord_dir = self._coord_dir()
        self.coord_meta_before = (coord_dir / "meta.json").read_bytes()
        restamp_topic_branch_as_coordination(coord_dir, topology_decision=self.decision.as_meta())

    def restore_meta(self) -> None:
        if self.coord_meta_before is not None and self.coord_dir is not None:
            (self._coord_dir() / "meta.json").write_bytes(self.coord_meta_before)

    def write_lanes_json(self) -> None:
        lanes = self._coord_dir() / "lanes.json"
        self.lanes_before = lanes.read_bytes() if lanes.is_file() else None
        self.write_lanes(self._coord_dir())

    def restore_lanes_json(self) -> None:
        if self.coord_dir is None:
            return
        lanes = self.coord_dir / "lanes.json"
        if self.lanes_before is None:
            lanes.unlink(missing_ok=True)
        else:
            lanes.write_bytes(self.lanes_before)

    def _coord_dir(self) -> Path:
        if self.coord_dir is None:
            raise RuntimeError("the coordination worktree is not materialized")
        return self.coord_dir

    def steps(self) -> list[SettlementStep]:
        return [
            SettlementStep("commit", self.commit_mission_dir, self.uncommit_mission_dir),
            SettlementStep("root_checkout_move", self.move_root_checkout, self.return_root_checkout),
            SettlementStep("coord_worktree_materialize", self.materialize_coord_worktree, self.remove_coord_worktree),
            SettlementStep("meta_restamp", self.restamp_meta, self.restore_meta),
            SettlementStep("lanes_json_write", self.write_lanes_json, self.restore_lanes_json),
        ]


def _settle_single_branch(planning_dir: Path, decision: TopologyDecision) -> SettlementHandle:
    """No git step: write ``topology_settled: true`` and ``topology_decision`` (FR-055)."""
    from specify_cli.meta_keys import TOPOLOGY_DECISION_KEY, TOPOLOGY_SETTLED_KEY
    from specify_cli.mission_metadata import locked_update_meta

    meta_path = planning_dir / "meta.json"
    before = meta_path.read_bytes()

    def _mark(meta: dict[str, Any]) -> None:
        meta[TOPOLOGY_SETTLED_KEY] = True
        meta[TOPOLOGY_DECISION_KEY] = decision.as_meta()

    locked_update_meta(planning_dir, _mark, validate=False)

    def _restore() -> None:
        meta_path.write_bytes(before)

    step = SettlementStep("meta_restamp", lambda: None, _restore)
    return SettlementHandle(decision=decision, planning_dir=planning_dir, applied=[step])


def settle_topology(
    repo_root: Path,
    planning_dir: Path,
    meta: Mapping[str, object],
    decision: TopologyDecision,
    *,
    write_lanes: Callable[[Path], None],
) -> SettlementHandle:
    """Apply *decision* to the provisional Mission at *planning_dir* (FR-055 / FR-056).

    *write_lanes* writes ``lanes.json`` for the settled topology into the Mission
    directory it is given (the coordination worktree's copy). Raises
    ``WriteCheckoutSwitchOccupiedError`` / ``WriteCheckoutSwitchDirtyError`` or
    :class:`TopologySettlementRefused` with nothing changed.
    """
    if decision.to_topology == _SINGLE_BRANCH:
        return _settle_single_branch(planning_dir, decision)
    ctx = _context_from(repo_root, planning_dir, meta)
    _check_branches(ctx)
    _check_coord_worktree_absent(ctx)
    _check_not_started(planning_dir)
    _check_write_checkout(ctx)
    plan = _CoordPlan(ctx=ctx, decision=decision, write_lanes=write_lanes)
    remedy = f"The Mission stays provisional and the repository root checkout is back on {ctx.topic!r}; fix the cause and re-run finalize-tasks."
    applied = run_settlement_plan(plan.steps(), remedy=remedy)
    coord_dir = plan._coord_dir()
    return SettlementHandle(decision=decision, planning_dir=coord_dir, applied=applied, coord_snapshot=_snapshot_dir(coord_dir))
