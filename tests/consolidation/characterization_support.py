"""Characterization corpus support: today's consolidation verdict per scenario cell (FR-016, NFR-001, C-008).

Before any code moves out of ``specify_cli.consolidation.reconciliation``, the verdict matrix
``characterization/verdict_corpus.json`` pins today's actual verdict for every cell: verdict
status, refusal codes, the ``Divergence`` fields the gate reported, and the exit code. Known-wrong
verdicts are recorded as they are today; intended verdicts live in separate strict ``xfail`` tests.

Pieces (each reused by later work packages, so each is importable on its own):

* :func:`run_in_process` -- runs ``spec-kitty consolidate`` through the Typer app in THIS process
  (``CliRunner``), with the per-mission HOME the subprocess harness gives (``_cli_env``). A seeded
  mutation applied with ``monkeypatch`` before the call reaches the verdict computation; a
  subprocess (``run_terminus``) could not be reached.
* :func:`interrupt_after_claim` -- a real interrupted state for resume cells: a forked child of
  this process runs the real CLI and SIGKILLs itself right after the claim anchors are saved and
  before the first lane merge (hook: ``executor._phase_merge_lanes``, see its docstring). No
  hand-written ``state.json``.
* :func:`build_shape` / :class:`ShapeMission` -- one builder per lane shape of IC-02, composed from
  the terminus builders and the promoted ``single_branch`` builder.
* :func:`apply_stamp` and :func:`set_window_state` -- the approval-stamp and window-state axes,
  set explicitly after the builder runs (IC-02: never left to which builder wrote the events).
* :func:`compute_cells`, :func:`assert_cells_match`, :func:`regenerate_cells`,
  :func:`changed_cells` -- the golden-file machinery. A Phase 4 work package regenerates only its
  named cells and checks its diff with :func:`changed_cells`.

Cell values hold codes and field names, never raw prose, except the cells that pin text (FR-023
all-gap cell, NFR-002 (b)); pinned text is normalized (SHAs and temporary paths become labels).
"""

from __future__ import annotations

import contextlib
import difflib
import json
import multiprocessing
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import warnings
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, fields, is_dataclass, replace
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from kernel.clock import parse_iso, timedelta

from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import read_lanes_json, write_lanes_json
from specify_cli.lanes.worktree_allocator import allocate_lane_worktree
from specify_cli.status import WP_WINDOW_KEY
from tests.integration import single_branch_window_support as sb
from tests.terminus.canceled_dependency_support import (
    ACTOR,
    WP01_PATH,
    WP02_PATH,
    _approve,
    _commit_in,
    _wp_file,
    build_canceled_dependency_mission,
)
from tests.terminus.conftest import (
    CoordMission,
    PlantedChange,
    _bootstrapped_home_template,
    _commit_planning_artifacts,
    _cut_coord_branch,
    _finish_coord_mission,
    _init_fixture_repo,
    _now_iso,
    _STATUS_EVENTS_FILENAME,
    _write_meta,
    build_coord_mission_mixed_lane_canceled,
    build_coord_mission_mixed_lane_with_dependency,
    pin_planning_commit,
)
from tests.terminus.lanes_fixture import build_lanes_mission
from tests.terminus.mixed_lane_support import transition
from tests.terminus.post_approval_support import add_post_approval_commit, build_post_approval_coord_mission, rework_and_reapprove, strip_approval_stamps
from tests.consolidation.reconciliation_family import setattr_reconciliation_family

# --------------------------------------------------------------------------- vocabulary

WINDOW_SCHEMA_VERSION = 1

GOLDEN_PATH = Path(__file__).resolve().parent / "characterization" / "verdict_corpus.json"
GOLDEN_REPO_PATH = "tests/consolidation/characterization/verdict_corpus.json"
REGEN_ENV = "SPEC_KITTY_REGEN_VERDICT_CORPUS"

MODES = ("forecast", "fresh", "resume")
LANE_SHAPES = ("single_lane", "two_wp_lane", "mixed_lane_canceled_wp", "fully_canceled_dependency", "dependency_chain")
FLAT_SHAPES = ("planning_lane", "single_branch")
SHAPES = (*LANE_SHAPES, *FLAT_SHAPES)
STAMPS = ("present", "missing", "rewritten")
WINDOWS = ("recorded", "not_recorded", "capture_failed", "lane_branch_missing", "not_on_lane")
WINDOW_ANY = "any"

MODE_NA_RESUME = "no frozen tips without a coordination checkpoint (phase_claim.py _resolve_pre_mutation_coord_sha)"
NA_PLANNING_STAMP = "planning lanes are never stamped (status/lane_head.py: no lane branch), so no approval stamp can be missing or rewritten"

_OPENING_LANES = ("claimed", "in_progress")
_MIGRATION_PREFIX = "migration:"
_GLOBAL_MERGE_LOCK = Path(".kittify") / "runtime" / "merge" / "__global_merge__" / "lock"
_NO_HOOKS = ("-c", "core.hooksPath=/dev/null")
_CODE_TOKEN = re.compile(r"(?<![A-Za-z0-9_])([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)(?![A-Za-z0-9_])")
_JSON_ESCAPE = re.compile(r"\\[nrt]")  # a literal backslash + letter in raw --json output: it would otherwise glue to the next code
_CODE_NOISE_PREFIXES = ("SPEC_KITTY_", "GIT_", "XDG_")
_HEX = re.compile(r"(?<![0-9a-zA-Z])(?=[0-9a-f]*[0-9])[0-9a-f]{7,40}(?![0-9a-zA-Z])")
_ISO_TS = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?")
_ULID = re.compile(r"(?<![0-9A-Z])[0-9A-HJKMNP-TV-Z]{26}(?![0-9A-Z])")


# --------------------------------------------------------------------------- git helpers


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *_NO_HOOKS, *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


def _try_git(repo: Path, *args: str) -> str | None:
    proc = subprocess.run(["git", *_NO_HOOKS, *args], cwd=repo, capture_output=True, text=True, check=False)
    return proc.stdout.strip() if proc.returncode == 0 else None


def _worktree_of(repo: Path, branch: str) -> Path | None:
    """The checkout that has *branch* checked out, or ``None``."""
    current: Path | None = None
    for line in _git(repo, "worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            current = Path(line[len("worktree ") :])
        elif line == f"branch refs/heads/{branch}":
            return current
    return None


@contextlib.contextmanager
def deterministic_commit_dates(repo: Path) -> Iterator[None]:
    """Pin every git commit made inside the block to the newest committer date among *repo*'s refs.

    The axes rewrite each copy of the event log (the repository root checkout and the
    coordination worktree) and commit each copy where it lives. Two such commits on the same
    parent with the same tree and message are one commit only when their dates match; with
    wall-clock dates they diverge whenever the two commits straddle a second boundary, the target
    branch then carries a commit the Mission branch does not, and the landing refuses with
    ``TARGET_BRANCH_CONTENT_CONFLICT`` on the status log (the WP02 corpus flake). A date taken
    from the repository makes the commit identity a function of the repository alone. The newest
    date keeps every new commit no older than its parent (git's merge-base walk relies on dates).
    """
    newest = _git(repo, "for-each-ref", "--sort=-committerdate", "--count=1", "--format=%(committerdate:raw)")
    if not newest:
        raise AssertionError(f"deterministic_commit_dates: {repo} has no ref to take a date from")
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("GIT_AUTHOR_DATE", newest)
        patch.setenv("GIT_COMMITTER_DATE", newest)
        yield


# --------------------------------------------------------------------------- the mission a cell runs on


@dataclass(frozen=True)
class ShapeMission:
    """What the runner and the axes need from a built mission, on any topology.

    ``root`` is the directory that holds ``repo`` (and ``home``); it is the unit
    :func:`copy_mission` copies. ``topology`` is ``"coord"``, ``"lanes"`` or
    ``"single_branch"``. ``subject_wp`` is the work package the approval-stamp axis acts on;
    ``window_wps`` are the approved code-lane work packages the window-state axis acts on.
    ``env`` holds extra CLI environment the builder's own harness sets (the ``single_branch``
    builder's XDG/origin-check isolation).
    """

    root: Path
    repo: Path
    home: Path
    slug: str
    mission_id: str
    mid8: str
    target_branch: str
    mission_branch: str
    topology: str
    lane_branches: Mapping[str, str] = field(default_factory=dict)
    canceled_wps: frozenset[str] = frozenset()
    subject_wp: str = "WP01"
    window_wps: tuple[str, ...] = ()
    env: Mapping[str, str] = field(default_factory=dict)

    @property
    def feature_dir(self) -> Path:
        return self.repo / "kitty-specs" / self.slug

    def coord_mission(self) -> CoordMission:
        """The terminus :class:`CoordMission` view, for helpers that take one (lane topologies only)."""
        return CoordMission(
            repo=self.repo,
            home=self.home,
            feature_dir=self.feature_dir,
            slug=self.slug,
            mission_id=self.mission_id,
            mid8=self.mid8,
            coord_branch=self.mission_branch,
            target_branch=self.target_branch,
            lane_branches=dict(self.lane_branches),
            canceled_wps=set(self.canceled_wps),
        )


def _from_coord(mission: CoordMission, topology: str, *, subject_wp: str, window_wps: tuple[str, ...]) -> ShapeMission:
    return ShapeMission(
        root=mission.repo.parent,
        repo=mission.repo,
        home=mission.home,
        slug=mission.slug,
        mission_id=mission.mission_id,
        mid8=mission.mid8,
        target_branch=mission.target_branch,
        mission_branch=mission.coord_branch,
        topology=topology,
        lane_branches=dict(mission.lane_branches),
        canceled_wps=frozenset(mission.canceled_wps),
        subject_wp=subject_wp,
        window_wps=window_wps,
    )


def _rebase_path(path: Path, old_root: Path, new_root: Path) -> Path:
    return new_root / path.relative_to(old_root)


def _repair_worktree_links(repo: Path, old_root: Path, new_root: Path) -> None:
    """Point every copied linked worktree and its admin entry at the copy, never at the original."""
    admin_root = repo / ".git" / "worktrees"
    if not admin_root.is_dir():
        return
    old_prefix = str(old_root)
    for admin in sorted(admin_root.iterdir()):
        gitdir_file = admin / "gitdir"
        if not gitdir_file.is_file():
            continue
        old_dotgit = gitdir_file.read_text(encoding="utf-8").strip()
        if not old_dotgit.startswith(old_prefix):
            raise AssertionError(f"copy precondition: worktree {admin.name} lives outside the copied root: {old_dotgit}")
        new_dotgit = Path(str(new_root) + old_dotgit[len(old_prefix) :])
        gitdir_file.write_text(f"{new_dotgit}\n", encoding="utf-8")
        if new_dotgit.parent.is_dir():
            new_dotgit.write_text(f"gitdir: {admin}\n", encoding="utf-8")


def copy_mission(mission: ShapeMission, dest_root: Path) -> ShapeMission:
    """Copy *mission*'s whole root to *dest_root* and return the mission rebased onto the copy.

    Linked worktrees are re-pointed at the copy, so a run on the copy can never touch the
    original (the original stays a read-only template shared across cells).
    """
    shutil.copytree(mission.root, dest_root, symlinks=True)
    copied = replace(
        mission,
        root=dest_root,
        repo=_rebase_path(mission.repo, mission.root, dest_root),
        home=_rebase_path(mission.home, mission.root, dest_root),
        env={key: value.replace(str(mission.root), str(dest_root)) for key, value in mission.env.items()},
    )
    _repair_worktree_links(copied.repo, mission.root, dest_root)
    return copied


def _ensure_bootstrapped_home(home: Path) -> None:
    """An empty HOME would make the first in-process command install the global runtime (~25s): copy the bootstrapped template."""
    home.mkdir(parents=True, exist_ok=True)
    if not any(home.iterdir()):
        shutil.copytree(_bootstrapped_home_template(), home, dirs_exist_ok=True)


@contextlib.contextmanager
def mission_environment(mission: ShapeMission) -> Iterator[pytest.MonkeyPatch]:
    """``chdir`` into the mission repo with the CLI environment ``_cli_env(mission.home)`` builds; restored on exit."""
    with pytest.MonkeyPatch.context() as patch:
        patch.chdir(mission.repo)
        patch.setenv("HOME", str(mission.home))
        patch.setenv("SPEC_KITTY_NO_UPGRADE_CHECK", "1")
        patch.delenv("SPEC_KITTY_ORIGIN_CHECK", raising=False)
        patch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)
        for key, value in mission.env.items():
            patch.setenv(key, value)
        yield patch


# --------------------------------------------------------------------------- the in-process runner


@dataclass(frozen=True)
class CellResult:
    """One CLI run, reduced to what the corpus records.

    ``status`` is ``pass`` (exit 0), ``fail`` / ``refuse`` (the reconciliation verdict the
    verifier returned, or ``refuse`` for an exit before any verifier call: a claim-time or
    preflight refusal), or ``error`` (an unexpected exception, named in ``exception``).
    """

    exit_code: int
    output: str
    status: str
    codes: tuple[str, ...]
    divergence_fields: tuple[str, ...]
    exception: str | None = None

    def cell(self) -> dict[str, Any]:
        value: dict[str, Any] = {"status": self.status, "exit_code": self.exit_code, "codes": list(self.codes), "divergence_fields": list(self.divergence_fields)}
        if self.exception is not None:
            value["exception"] = self.exception
        return value


def refusal_codes(text: str) -> tuple[str, ...]:
    """Every upper-snake code token in *text* (``LANE_MOVED_AFTER_APPROVAL`` style), sorted and unique.

    The JSON escapes ``\\n``, ``\\r`` and ``\\t`` read as spaces, so a code right after one is still found.
    """
    readable = _JSON_ESCAPE.sub(" ", text)
    return tuple(sorted({token for token in _CODE_TOKEN.findall(readable) if not token.startswith(_CODE_NOISE_PREFIXES)}))


def _divergence_fields(divergence: object | None) -> tuple[str, ...]:
    if divergence is None or not is_dataclass(divergence):
        return ()
    return tuple(sorted(f.name for f in fields(divergence) if getattr(divergence, f.name)))


def run_in_process(mission: ShapeMission, args: Sequence[str]) -> CellResult:
    """Run ``spec-kitty <args>`` in THIS process and reduce the run to a :class:`CellResult`.

    The verifier's verdicts are observed by wrapping ``MergeOutcomeVerifier.verify`` and
    ``forecast_content_verdict`` for the duration of the call (the wrappers call whatever the
    class holds at that moment, so a seeded mutation applied before the call stays in force).
    """
    from specify_cli import app as cli_app
    from specify_cli.consolidation.reconciliation import MergeOutcomeVerifier, VerifyStatus

    _ensure_bootstrapped_home(mission.home)
    observed: list[Any] = []
    with mission_environment(mission) as patch:
        for name in ("verify", "forecast_content_verdict"):
            original = getattr(MergeOutcomeVerifier, name)

            def _observing(self: Any, *a: Any, _original: Any = original, **k: Any) -> Any:
                result = _original(self, *a, **k)
                observed.append(result)
                return result

            patch.setattr(MergeOutcomeVerifier, name, _observing)
        result = CliRunner().invoke(cli_app, list(args))
    output = result.output + (result.stderr if result.stderr_bytes is not None else "")
    exception = None
    if result.exception is not None and not isinstance(result.exception, SystemExit):
        exception = type(result.exception).__name__
        output += f"\n{exception}: {result.exception}"
    verdicts = [r for r in observed if r.status is not VerifyStatus.PASS]
    if exception is not None:
        status = "error"
    elif result.exit_code == 0:
        status = "pass"
    elif verdicts:
        status = "fail" if verdicts[-1].status is VerifyStatus.FAIL else "refuse"
    else:
        status = "refuse"
    divergence = _divergence_fields(verdicts[-1].divergence) if verdicts else ()
    return CellResult(exit_code=result.exit_code, output=output, status=status, codes=refusal_codes(output), divergence_fields=divergence, exception=exception)


def consolidate_args(mission: ShapeMission, mode: str, *extra: str) -> list[str]:
    """The ``consolidate`` argv of *mode* (``forecast`` = ``--dry-run --json``, ``resume`` = ``--resume``)."""
    base = ["consolidate", "--mission", mission.slug]
    if mode == "forecast":
        return [*base, "--dry-run", "--json", *extra]
    if mode == "resume":
        return [*base, "--resume", "--yes", *extra]
    return [*base, "--yes", *extra]


# --------------------------------------------------------------------------- the interrupted state for resume cells


def _state_json(mission: ShapeMission) -> Path | None:
    found = sorted((mission.repo / ".kittify" / "runtime" / "merge").glob("*/state.json"))
    return found[0] if found else None


class ResumeUnreachableError(AssertionError):
    """The fresh run ended before its first lane merge (a claim-time or preflight refusal): no interrupted state exists."""

    def __init__(self, interrupted_run: Mapping[str, Any]) -> None:
        super().__init__(f"the consolidate child ended before its first lane merge: {dict(interrupted_run)}")
        self.interrupted_run = dict(interrupted_run)


RESUME_UNREACHABLE = "the fresh run ends before its first lane merge (claim-time or preflight refusal), so no interrupted state exists to resume"


def interrupt_after_claim(mission: ShapeMission, *extra: str) -> dict[str, Any]:
    """SIGKILL a real ``consolidate`` right after the claim anchors were saved; return the persisted record.

    Hook point: ``executor._phase_merge_lanes``. In ``_run_lane_based_consolidation_locked`` the
    claim phase (``phase_claim._capture_reconciliation_claim``) runs first: it persists
    ``pre_mutation_coord_sha`` and ``pre_interrupt_lane_tips`` (``_resolve_pre_mutation_coord_sha``)
    and then the pre-mutation snapshot (``_capture_snapshot_and_begin_attempt``). The next call is
    ``_phase_merge_lanes(run)``, the first mutating phase. Replacing the executor's binding of it
    with a self-SIGKILL stops the run exactly between those points, with no branch moved and no
    exception exit (an exception exit would clear or re-baseline the record, #6770).

    The child is a fork of this process, so any patch applied here also governs the claim the
    child persists. The global merge lock the killed run leaves is removed, as the operator is told
    to (``InterruptedConsolidate.operator_clears_stale_locks``). Only the coordination topology
    persists frozen tips; the caller asserts ``pre_interrupt_lane_tips`` is present. A child that
    ends before the merge writes ``interrupt-not-reached.json`` (exit code, codes, and the
    exception name of a crash), which :class:`ResumeUnreachableError` carries.
    """
    _ensure_bootstrapped_home(mission.home)
    with warnings.catch_warnings():
        # Python 3.12+ warns that fork() in a multi-threaded process may deadlock; the child only
        # runs git subprocesses and file I/O and never touches the parent's threads' locks.
        warnings.simplefilter("ignore", DeprecationWarning)
        pid = os.fork()
    report = mission.root / "interrupt-not-reached.json"
    report.unlink(missing_ok=True)
    if pid == 0:  # pragma: no cover - the child never returns; it is SIGKILLed or exits 3
        stop_inherited_tracing()
        try:
            report.write_text(json.dumps(_interrupted_child_report(mission, extra)), encoding="utf-8")
        except BaseException as crashed:  # the child must never return into the parent's stack
            report.write_text(json.dumps({"exception": type(crashed).__name__}), encoding="utf-8")
        finally:
            os._exit(3)
    _, status = os.waitpid(pid, 0)
    if not (os.WIFSIGNALED(status) and os.WTERMSIG(status) == signal.SIGKILL):
        interrupted = json.loads(report.read_text(encoding="utf-8")) if report.exists() else {"wait_status": status}
        raise ResumeUnreachableError(interrupted)
    state = _state_json(mission)
    if state is None:
        raise AssertionError("the killed run left no state.json")
    record: dict[str, Any] = json.loads(state.read_text(encoding="utf-8"))
    (mission.repo / _GLOBAL_MERGE_LOCK).unlink(missing_ok=True)
    return record


def _interrupted_child_report(mission: ShapeMission, extra: Sequence[str]) -> dict[str, Any]:
    """Run the fresh consolidate in the forked child; the report of a run that ended before its first lane merge.

    A run that crashed carries the exception name (``exception``) beside its exit code and codes.
    """
    from specify_cli import app as cli_app
    from specify_cli.consolidation import executor

    with mission_environment(mission) as patch:
        patch.setattr(executor, "_phase_merge_lanes", lambda _run: os.kill(os.getpid(), signal.SIGKILL))
        result = CliRunner().invoke(cli_app, consolidate_args(mission, "fresh", *extra))
    output = result.output + (result.stderr if result.stderr_bytes is not None else "")
    reported: dict[str, Any] = {"exit_code": result.exit_code, "codes": list(refusal_codes(output))}
    if result.exception is not None and not isinstance(result.exception, SystemExit):
        reported["exception"] = type(result.exception).__name__
    return reported


def resume_after_interrupt(mission: ShapeMission, *, between: Callable[[ShapeMission], None] | None = None, extra: Sequence[str] = ()) -> CellResult:
    """Interrupt after the claim, assert the frozen tips exist, optionally act, then resume in process."""
    record = interrupt_after_claim(mission, *extra)
    if not record.get("pre_interrupt_lane_tips"):
        raise AssertionError(f"resume precondition: the record holds no pre_interrupt_lane_tips (the resume would be a fresh run): {sorted(record)}")
    if between is not None:
        between(mission)
    return run_in_process(mission, consolidate_args(mission, "resume", *extra))


# --------------------------------------------------------------------------- the event-log axes


def _event_logs(repo: Path) -> list[Path]:
    logs: list[Path] = []
    for directory, subdirectories, files in os.walk(repo):
        subdirectories[:] = sorted(name for name in subdirectories if name != ".git")
        if _STATUS_EVENTS_FILENAME in files:
            logs.append(Path(directory) / _STATUS_EVENTS_FILENAME)
    return logs


def rewrite_events(mission: ShapeMission, edit: Callable[[dict[str, Any]], dict[str, Any] | None], message: str) -> None:
    """Rewrite every copy of the mission's event log with *edit* and commit each copy where it lives.

    *edit* returns the replacement event or ``None`` to keep it unchanged (its bytes are kept). A
    copy whose bytes do not change is not committed. Modelled on
    ``canceled_dependency_support.strip_lane_head_stamps``.
    """
    with deterministic_commit_dates(mission.repo):
        for log in _event_logs(mission.repo):
            _rewrite_one(log, edit, message)


def _is_opening(event: Mapping[str, Any], wp_id: str) -> bool:
    return event.get("wp_id") == wp_id and event.get("to_lane") in _OPENING_LANES and not str(event.get("actor", "")).startswith(_MIGRATION_PREFIX)


def _window_branch(mission: ShapeMission, wp_id: str) -> str:
    return mission.lane_branches.get(wp_id) or mission.mission_branch


def _lane_base(mission: ShapeMission, wp_id: str) -> str:
    branch = _window_branch(mission, wp_id)
    base_ref = mission.target_branch if mission.topology == "single_branch" else mission.mission_branch
    if branch == base_ref:
        base_ref = mission.target_branch
    return _git(mission.repo, "merge-base", branch, base_ref)


def _not_on_lane_sha(mission: ShapeMission, wp_id: str) -> str:
    """A commit that is on no lane, kept reachable from ``refs/test/not-on-lane/<wp>`` so no ``gc`` can make it unresolvable."""
    ref = f"refs/test/not-on-lane/{wp_id}"
    existing = _try_git(mission.repo, "rev-parse", "--verify", "-q", ref)
    if existing:
        return existing
    base = _lane_base(mission, wp_id)
    sha = _git(mission.repo, "commit-tree", f"{base}^{{tree}}", "-p", base, "-m", f"test: a commit not on {wp_id}'s lane")
    _git(mission.repo, "update-ref", ref, sha)
    return sha


def _window_value(mission: ShapeMission, wp_id: str, state: str, event: Mapping[str, Any]) -> dict[str, Any] | None:
    if state == "recorded":
        metadata = event.get("policy_metadata") or {}
        return {"schema_version": WINDOW_SCHEMA_VERSION, "open_sha": metadata.get("lane_head") or _lane_base(mission, wp_id)}
    if state == "capture_failed":
        return {"schema_version": WINDOW_SCHEMA_VERSION, "gap": {"reason": "capture_failed", "cause": "git_error", "detail": "test"}}
    if state == "lane_branch_missing":
        return {"schema_version": WINDOW_SCHEMA_VERSION, "gap": {"reason": "lane_branch_missing", "detail": "test"}}
    if state == "not_on_lane":
        return {"schema_version": WINDOW_SCHEMA_VERSION, "open_sha": _not_on_lane_sha(mission, wp_id)}
    if state == "not_recorded":
        return None
    raise ValueError(f"unknown window state {state!r}")


def set_window_state(mission: ShapeMission, wp_id: str, state: str, *, openers: Sequence[int] | None = None) -> None:
    """Set ``policy_metadata.wp_window`` on *wp_id*'s opening events to *state*, in every event-log copy.

    The opening events are the work package's non-migration moves into ``claimed`` /
    ``in_progress``, in log order. *openers* selects some of them by index (all by default).
    ``recorded`` -> ``open_sha`` = that event's ``lane_head`` (or the lane base);
    ``capture_failed`` / ``lane_branch_missing`` -> a typed gap; ``not_on_lane`` -> ``open_sha`` of
    a commit off the lane; ``not_recorded`` -> the key removed.
    """
    counter = {"n": 0}
    wanted = None if openers is None else set(openers)

    def _edit(event: dict[str, Any]) -> dict[str, Any] | None:
        if not _is_opening(event, wp_id):
            return None
        index = counter["n"]
        counter["n"] += 1
        if wanted is not None and index not in wanted:
            return None
        metadata = dict(event.get("policy_metadata") or {})
        value = _window_value(mission, wp_id, state, event)
        if value is None:
            if WP_WINDOW_KEY not in metadata:
                return None
            metadata.pop(WP_WINDOW_KEY)
        else:
            metadata[WP_WINDOW_KEY] = value
        return {**event, "policy_metadata": metadata or None}

    # The counter restarts per log copy: every copy holds the same history. Pinned dates: two
    # copies on one parent must stay one commit (see deterministic_commit_dates).
    with deterministic_commit_dates(mission.repo):
        for log in _event_logs(mission.repo):
            counter["n"] = 0
            _rewrite_one(log, _edit, f"test: wp_window={state} for {wp_id}")


def _rewrite_one(log: Path, edit: Callable[[dict[str, Any]], dict[str, Any] | None], message: str) -> None:
    lines: list[str] = []
    changed = False
    for line in log.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        edited = edit(event)
        # An edit that restates the event is no change: since WP07 the status writer records
        # the very ``wp_window`` a ``recorded`` state asks for, so there is nothing to commit.
        if edited is None or edited == event:
            lines.append(line)
            continue
        changed = True
        lines.append(json.dumps(edited, sort_keys=True))
    if not changed:
        return
    log.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
    _git(log.parent, "add", str(log))
    _git(log.parent, "commit", "-qm", message)


def set_window_states(mission: ShapeMission, window: str) -> None:
    """The generic window axis: *window* on every approved code-lane work package of the shape.

    ``window=any`` (the P1/P2 collapsed axis) is set explicitly to ``not_recorded``: any window a
    builder wrote is stripped, so the cell never depends on which builder wrote the events (IC-02).
    """
    state = "not_recorded" if window == WINDOW_ANY else window
    for wp_id in mission.window_wps:
        set_window_state(mission, wp_id, state)


def _rewrite_lane_tip(mission: ShapeMission, branch: str) -> None:
    """Replace *branch*'s tip with an equivalent commit, so no approval stamp that named the old tip is on it."""
    worktree = _worktree_of(mission.repo, branch)
    if worktree is not None:
        _git(worktree, "commit", "-q", "--amend", "-m", "rewritten after approval")
        return
    tip = _git(mission.repo, "rev-parse", branch)
    rewritten = _git(mission.repo, "commit-tree", f"{tip}^{{tree}}", "-p", f"{tip}^", "-m", "rewritten after approval")
    _git(mission.repo, "update-ref", f"refs/heads/{branch}", rewritten, tip)


def _rebase_single_branch(mission: ShapeMission) -> None:
    """The ``single_branch`` rewrite: an unrelated target commit, then the Mission branch rebased onto it (S8 fixture)."""
    repo = mission.repo
    _git(repo, "checkout", "-q", mission.target_branch)
    (repo / "docs").mkdir(exist_ok=True)
    (repo / "docs" / "unrelated.md").write_text("unrelated\n", encoding="utf-8")
    _git(repo, "add", "docs/unrelated.md")
    _git(repo, "commit", "-qm", "docs: an unrelated change on the target")
    _git(repo, "checkout", "-q", mission.mission_branch)
    _git(repo, "rebase", "-q", mission.target_branch)


def apply_stamp(mission: ShapeMission, stamp: str) -> None:
    """The approval-stamp axis on the shape's subject work package: ``present`` (builder default), ``missing``, ``rewritten``."""
    if stamp == "present":
        return
    if stamp == "missing":
        # strip_approval_stamps commits each event-log copy where it lives: pin the dates.
        with deterministic_commit_dates(mission.repo):
            strip_approval_stamps(mission.coord_mission(), mission.subject_wp)
        return
    if stamp == "rewritten":
        if mission.topology == "single_branch":
            _rebase_single_branch(mission)
        else:
            _rewrite_lane_tip(mission, mission.lane_branches[mission.subject_wp])
        return
    raise ValueError(f"unknown stamp state {stamp!r}")


# --------------------------------------------------------------------------- lane-shape builders


def _bootstrap_one_lane_coord(tmp_path: Path, *, mid8: str, wps: tuple[str, ...]) -> tuple[CoordMission, LanesManifest]:
    """A coordination mission whose ONE code lane ``lane-a`` holds *wps* (planning committed, coordination branch cut)."""
    slug = f"terminus-{mid8}"
    mission = _init_fixture_repo(tmp_path, mid8=mid8, slug=slug, target_branch="main")
    (mission.feature_dir / "tasks").mkdir(parents=True)
    _write_meta(mission)
    manifest = LanesManifest(
        version=1,
        mission_slug=slug,
        mission_id=mission.mission_id,
        mission_branch=mission.coord_branch,
        target_branch=mission.target_branch,
        lanes=[ExecutionLane(lane_id="lane-a", wp_ids=wps, write_scope=("src/pkg",), predicted_surfaces=("code",), depends_on_lanes=(), parallel_group=0)],
        computed_at=_now_iso(),
        computed_from="characterization-one-lane-fixture",
    )
    write_lanes_json(mission.feature_dir, manifest)
    pin_planning_commit(mission.repo, mission.feature_dir)
    for wp in wps:
        (mission.feature_dir / "tasks" / f"{wp}-work.md").write_text(_wp_file(wp, dependencies=()), encoding="utf-8")
    (mission.feature_dir / _STATUS_EVENTS_FILENAME).write_text("", encoding="utf-8")
    _commit_planning_artifacts(mission, f"chore({slug}): bootstrap one-lane mission")
    _cut_coord_branch(mission)
    _finish_coord_mission(mission)
    return mission, read_lanes_json(mission.feature_dir) or manifest


STRAY_PATH = "src/pkg/stray.py"
ABANDONED_PATH = "src/pkg/abandoned.py"


def build_two_wp_lane(tmp_path: Path, *, mid8: str = "01M6Y2W0", stray_between: bool = False, rewound: bool = False) -> ShapeMission:
    """Two approved work packages on ONE lane, the lane worktree reused for the second.

    ``stray_between``: a content commit on the lane after WP01's approval and before WP02 opens
    (the NFR-002 (a) commit between two approvals). ``rewound``: WP02 commits abandoned work, is
    moved back to ``planned`` (a rewind, not a review rejection) and claimed again before its real
    work (NFR-002 (c)).
    """
    mission, manifest = _bootstrap_one_lane_coord(tmp_path, mid8=mid8, wps=("WP01", "WP02"))
    slug = mission.slug
    tree, branch = allocate_lane_worktree(mission.repo, slug, "WP01", manifest)
    for lane in ("planned", "claimed", "in_progress"):
        transition(mission, "WP01", lane, actor=ACTOR)
    _commit_in(tree, WP01_PATH, "def wp01() -> int:\n    return 1\n", f"feat({slug}): WP01 work")
    _approve(mission, "WP01", reference="review-WP01")
    if stray_between:
        _commit_in(tree, STRAY_PATH, "STRAY = True\n", f"feat({slug}): unreviewed change between two approvals")
    transition(mission, "WP02", "planned", actor=ACTOR)
    transition(mission, "WP02", "claimed", actor=ACTOR)
    tree, branch = allocate_lane_worktree(mission.repo, slug, "WP02", manifest)
    transition(mission, "WP02", "in_progress", actor=ACTOR)
    if rewound:
        _commit_in(tree, ABANDONED_PATH, "ABANDONED = True\n", f"feat({slug}): WP02 abandoned attempt")
        transition(mission, "WP02", "planned", actor=ACTOR, reason="rewound: the attempt is abandoned")
        transition(mission, "WP02", "claimed", actor=ACTOR)
        transition(mission, "WP02", "in_progress", actor=ACTOR)
    _commit_in(tree, WP02_PATH, "def wp02() -> int:\n    return 2\n", f"feat({slug}): WP02 work")
    _approve(mission, "WP02", reference="review-WP02")
    mission.lane_branches.update({"WP01": branch, "WP02": branch})
    return _from_coord(mission, "coord", subject_wp="WP02", window_wps=("WP01", "WP02"))


def build_dependency_ref_before_window(tmp_path: Path, *, mid8: str = "01M6Y2R1") -> ShapeMission:
    """M9: an external branch merged into ``lane-a`` BEFORE WP01's window opens, then WP01 claimed, worked and approved.

    The lane is allocated, :data:`DEP_BRANCH` (one commit off the root, never Mission work) is merged
    into it, and only then does WP01 move to ``claimed`` / ``in_progress``, so the status shell records
    an ``open_sha`` that already reaches the dependency's commit: that commit lies before WP01's window.
    """
    mission, manifest = _bootstrap_one_lane_coord(tmp_path, mid8=mid8, wps=("WP01",))
    slug = mission.slug
    tree, branch = allocate_lane_worktree(mission.repo, slug, "WP01", manifest)
    root_commit = _git(mission.repo, "rev-list", "--max-parents=0", mission.target_branch)
    _git(mission.repo, "branch", DEP_BRANCH, root_commit)
    dep_wt = tmp_path / "dep-wt"
    _git(mission.repo, "worktree", "add", "-q", str(dep_wt), DEP_BRANCH)
    _commit_in(dep_wt, "src/dep/mod0.py", "DEP = 0\n", "feat(dep): mod0")
    _git(mission.repo, "worktree", "remove", str(dep_wt))
    _git(tree, "merge", "-q", "--no-ff", "--no-edit", DEP_BRANCH)
    for lane in ("planned", "claimed", "in_progress"):
        transition(mission, "WP01", lane, actor=ACTOR)
    _commit_in(tree, WP01_PATH, "def wp01() -> int:\n    return 1\n", f"feat({slug}): WP01 work")
    _approve(mission, "WP01", reference="review-WP01")
    mission.lane_branches.update({"WP01": branch})
    return _from_coord(mission, "coord", subject_wp="WP01", window_wps=("WP01",))


def build_dependency_chain_with_stray(tmp_path: Path, *, mid8: str = "01M6Y2D5") -> ShapeMission:
    """The FR-007 exception: a stray commit on lane A after WP01's approval, merged into lane B, then WP02 approved."""
    from tests.terminus.canceled_dependency_support import _bootstrap_coord_mission

    mission, manifest = _bootstrap_coord_mission(tmp_path, mid8=mid8, depends=True, target_branch="main")
    slug = mission.slug
    lane_a_tree, lane_a_branch = allocate_lane_worktree(mission.repo, slug, "WP01", manifest)
    allocate_lane_worktree(mission.repo, slug, "WP02", manifest)
    for lane in ("planned", "claimed", "in_progress"):
        transition(mission, "WP01", lane, actor=ACTOR)
    _commit_in(lane_a_tree, WP01_PATH, "def wp01() -> int:\n    return 1\n", f"feat({slug}): WP01 work")
    _approve(mission, "WP01", reference="review-WP01")
    _commit_in(lane_a_tree, STRAY_PATH, "STRAY = True\n", f"feat({slug}): unreviewed change on lane-a after WP01's approval")
    transition(mission, "WP02", "planned", actor=ACTOR)
    transition(mission, "WP02", "claimed", actor=ACTOR)
    lane_b_tree, lane_b_branch = allocate_lane_worktree(mission.repo, slug, "WP02", manifest)  # REUSE: merges lane-a's tip (with the stray)
    transition(mission, "WP02", "in_progress", actor=ACTOR)
    _commit_in(lane_b_tree, WP02_PATH, "def wp02() -> int:\n    return 2\n", f"feat({slug}): WP02 work")
    _approve(mission, "WP02", reference="review-WP02")
    mission.lane_branches.update({"WP01": lane_a_branch, "WP02": lane_b_branch})
    return _from_coord(mission, "coord", subject_wp="WP02", window_wps=("WP01", "WP02"))


SHELL_CANCELED_PATH = "src/pkg/canceled.py"
#: Every line of WP02's canceled file rewritten by WP01's approved work, so nothing of it survives (#6309).
SHELL_SUPERSEDING_BODY = "SUPERSEDED_BY_WP01 = True\n"


def build_mixed_lane_through_the_shell(tmp_path: Path, *, mid8: str, supersede: bool = False) -> CoordMission:
    """One lane: WP02 claimed, commits C, is canceled; then WP01 claimed, commits, approved; every move through the production shell.

    The status pipeline records every window (``wp_window``); WP03's ``build_coord_mission_mixed_lane_canceled``
    writes its events by hand, without one, so its lane is all-gap and never reaches the window check (tier 2).
    C predates WP01's claim, so it lies in no approved work package's window. ``supersede``: WP01's work also
    rewrites every line of C's file, so C's content is superseded by approved work.
    """
    mission, manifest = _bootstrap_one_lane_coord(tmp_path, mid8=mid8, wps=("WP01", "WP02"))
    slug = mission.slug
    tree, branch = allocate_lane_worktree(mission.repo, slug, "WP01", manifest)
    for lane in ("planned", "claimed", "in_progress"):
        transition(mission, "WP02", lane, actor=ACTOR)
    _commit_in(tree, SHELL_CANCELED_PATH, "CANCELED = True\n", f"feat({slug}): WP02 work, later canceled")
    transition(mission, "WP02", "canceled", actor=ACTOR, reason_source="operator", reason="operator: scope removed from mission")
    for lane in ("planned", "claimed", "in_progress"):
        transition(mission, "WP01", lane, actor=ACTOR)
    _commit_in(tree, WP01_PATH, "def wp01() -> int:\n    return 1\n", f"feat({slug}): WP01 work")
    if supersede:
        _commit_in(tree, SHELL_CANCELED_PATH, SHELL_SUPERSEDING_BODY, f"feat({slug}): WP01 rewrites the canceled file")
    _approve(mission, "WP01", reference="review-WP01")
    mission.lane_branches.update({"WP01": branch, "WP02": branch})
    mission.canceled_wps.add("WP02")
    return mission


def build_mixed_lane_shell_shape(tmp_path: Path, *, mid8: str, supersede: bool = False) -> ShapeMission:
    """:func:`build_mixed_lane_through_the_shell` as a corpus shape: WP01 is the subject and the one windowed work package."""
    return _from_coord(build_mixed_lane_through_the_shell(tmp_path, mid8=mid8, supersede=supersede), "coord", subject_wp="WP01", window_wps=("WP01",))


_CANCELED_PATH = "src/canceled/c.py"


def _build_single_lane(tmp_path: Path) -> ShapeMission:
    return _from_coord(build_post_approval_coord_mission(tmp_path, mid8="01M6Y2S1"), "coord", subject_wp="WP01", window_wps=("WP01", "WP02"))


def _build_mixed_lane(tmp_path: Path) -> ShapeMission:
    mission = build_coord_mission_mixed_lane_canceled(
        tmp_path,
        canceled_changes=(PlantedChange(_CANCELED_PATH, "CANCELED = True\n"),),
        survivor_before=(PlantedChange(WP01_PATH, "def wp01() -> int:\n    return 1\n"),),
        survivor_after=(PlantedChange(_CANCELED_PATH, None),),
        mid8="01M6Y2M1",
    )
    return _from_coord(mission, "coord", subject_wp="WP01", window_wps=("WP01",))


def _build_fully_canceled_dependency(tmp_path: Path) -> ShapeMission:
    built = build_canceled_dependency_mission(tmp_path, wp01_final="canceled", depends=True, wp02_overwrites_wp01=True, mid8="01M6Y2F1")
    return _from_coord(built.mission, "coord", subject_wp="WP02", window_wps=("WP02",))


def _build_dependency_chain(tmp_path: Path) -> ShapeMission:
    built = build_canceled_dependency_mission(tmp_path, wp01_final="approved", depends=True, mid8="01M6Y2D1")
    return _from_coord(built.mission, "coord", subject_wp="WP02", window_wps=("WP01", "WP02"))


def _build_planning_lane(tmp_path: Path) -> ShapeMission:
    mission = build_lanes_mission(tmp_path, wps=(), with_planning_lane_wp=True, planning_depends_on_code=False, mid8="01M6Y2P1")
    _ensure_bootstrapped_home(mission.home)
    return _from_coord(mission, "lanes", subject_wp="WP01", window_wps=())


def _single_branch_env(base: Path) -> dict[str, str]:
    env = sb.cli_env(base)
    return {key: env[key] for key in ("XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "SPEC_KITTY_WORKTREE_REMOVAL_DELAY", "SPEC_KITTY_ORIGIN_CHECK")}


def build_single_branch_base(tmp_path: Path) -> ShapeMission:
    """The promoted S8 ``single_branch`` builder (real CLI, protected ``main``, minted Mission branch), nothing approved yet."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    repo, slug = sb.build_template(tmp_path, commit_to_target=False)
    meta = json.loads((repo / "kitty-specs" / slug / "meta.json").read_text(encoding="utf-8"))
    return ShapeMission(
        root=tmp_path,
        repo=repo,
        home=tmp_path / "home",
        slug=slug,
        mission_id=str(meta["mission_id"]),
        mid8=str(meta["mission_id"])[:8],
        target_branch=sb.TARGET,
        mission_branch=str(meta["mission_branch"]),
        topology="single_branch",
        subject_wp="WP02",
        window_wps=(),
        env=_single_branch_env(tmp_path),
    )


def _sb_mission(mission: ShapeMission) -> sb.Mission:
    return sb.Mission(mission.repo, mission.slug, mission.root)


def approve_single_branch(mission: ShapeMission, *, rewound: bool = False) -> None:
    """WP01 then WP02 approved on the ``single_branch`` Mission (``rewound``: WP02 abandons work, returns to ``planned``, restarts)."""
    with mission_environment(mission):
        m = _sb_mission(mission)
        sb.build_and_approve(m, "WP01")
        if rewound:
            sb.claim(m, "WP02")
            sb.commit_file(m, "src/m2/abandoned.py", "ABANDONED = True\n", "feat(WP02): abandoned attempt")
            sb.emit(m, "WP02", "planned", "alice", "--reason", "rewound: the attempt is abandoned")
        sb.build_and_approve(m, "WP02")


def build_shape(tmp_path: Path, shape: str) -> ShapeMission:
    """One builder per lane shape of IC-02."""
    if shape == "single_lane":
        return _build_single_lane(tmp_path)
    if shape == "two_wp_lane":
        return build_two_wp_lane(tmp_path)
    if shape == "mixed_lane_canceled_wp":
        return _build_mixed_lane(tmp_path)
    if shape == "fully_canceled_dependency":
        return _build_fully_canceled_dependency(tmp_path)
    if shape == "dependency_chain":
        return _build_dependency_chain(tmp_path)
    if shape == "planning_lane":
        return _build_planning_lane(tmp_path)
    if shape == "single_branch":
        mission = build_single_branch_base(tmp_path)
        approve_single_branch(mission)
        return mission
    raise ValueError(f"unknown shape {shape!r}")


# --------------------------------------------------------------------------- templates (built once, copied per cell)


def _derive_single_branch(base: ShapeMission, dest: Path, *, rewound: bool) -> ShapeMission:
    mission = copy_mission(base, dest)
    approve_single_branch(mission, rewound=rewound)
    return mission


def _build_mixed_with_dependency(tmp_path: Path) -> ShapeMission:
    mission = build_coord_mission_mixed_lane_with_dependency(tmp_path, canceled_leaks=False, mid8="01M6Y2E1")
    _ensure_bootstrapped_home(mission.home)
    return _from_coord(mission, "coord", subject_wp="WP01", window_wps=tuple(wp for wp in sorted(mission.lane_branches) if wp not in mission.canceled_wps))


def _build_mixed_lane_canceled_leaks(tmp_path: Path) -> ShapeMission:
    """The mixed lane with the canceled WP's change SURVIVING on the lane (no ``survivor_after`` deletion); WP01 re-approved as it stands."""
    mission = build_coord_mission_mixed_lane_canceled(
        tmp_path,
        canceled_changes=(PlantedChange(_CANCELED_PATH, "CANCELED = True\n"),),
        survivor_before=(PlantedChange(WP01_PATH, "def wp01() -> int:\n    return 1\n"),),
        survivor_reapproved=True,
        mid8="01M6Y2K1",
    )
    return _from_coord(mission, "coord", subject_wp="WP01", window_wps=("WP01",))


def _build_fully_canceled_dependency_reachable(tmp_path: Path) -> ShapeMission:
    """The fully-canceled dependency whose content approved WP02 does NOT overwrite, so it stays live on the target."""
    built = build_canceled_dependency_mission(tmp_path, wp01_final="canceled", depends=True, wp02_overwrites_wp01=False, mid8="01M6Y2G1")
    return _from_coord(built.mission, "coord", subject_wp="WP02", window_wps=("WP02",))


#: name -> (dependency template or None, builder). A builder takes (destination, dependency).
TemplateBuilder = Callable[[Path, "ShapeMission | None"], ShapeMission]
TEMPLATES: dict[str, tuple[str | None, TemplateBuilder]] = {
    "single_lane": (None, lambda d, _b: _build_single_lane(d)),
    "two_wp_lane": (None, lambda d, _b: build_two_wp_lane(d)),
    "mixed_lane_canceled_wp": (None, lambda d, _b: _build_mixed_lane(d)),
    "fully_canceled_dependency": (None, lambda d, _b: _build_fully_canceled_dependency(d)),
    "dependency_chain": (None, lambda d, _b: _build_dependency_chain(d)),
    "planning_lane": (None, lambda d, _b: _build_planning_lane(d)),
    "single_branch_base": (None, lambda d, _b: build_single_branch_base(d)),
    "single_branch": ("single_branch_base", lambda d, b: _derive_single_branch(_need(b), d, rewound=False)),
    "single_branch_rewound": ("single_branch_base", lambda d, b: _derive_single_branch(_need(b), d, rewound=True)),
    "two_wp_lane_stray": (None, lambda d, _b: build_two_wp_lane(d, mid8="01M6Y2W1", stray_between=True)),
    "two_wp_lane_rewound": (None, lambda d, _b: build_two_wp_lane(d, mid8="01M6Y2W2", rewound=True)),
    "dependency_chain_stray": (None, lambda d, _b: build_dependency_chain_with_stray(d)),
    "mixed_lane_with_dependency": (None, lambda d, _b: _build_mixed_with_dependency(d)),
    "mixed_lane_canceled_leaks": (None, lambda d, _b: _build_mixed_lane_canceled_leaks(d)),
    "fully_canceled_dependency_reachable": (None, lambda d, _b: _build_fully_canceled_dependency_reachable(d)),
    "mixed_lane_shell": (None, lambda d, _b: build_mixed_lane_shell_shape(d, mid8="01M6Y2C1")),
    "mixed_lane_shell_superseded": (None, lambda d, _b: build_mixed_lane_shell_shape(d, mid8="01M6Y2C2", supersede=True)),
    "dependency_ref_before_window": (None, lambda d, _b: build_dependency_ref_before_window(d)),
}


def _need(mission: ShapeMission | None) -> ShapeMission:
    if mission is None:
        raise AssertionError("template dependency missing")
    return mission


# --------------------------------------------------------------------------- cells


CellValue = dict[str, Any]


@dataclass
class CellContext:
    """Where a cell computes: the shared templates and a scratch directory of its own."""

    templates: Mapping[str, ShapeMission]
    scratch: Path

    def copy(self, template: str, label: str = "m") -> ShapeMission:
        return copy_mission(self.templates[template], self.scratch / label)


@dataclass(frozen=True)
class Cell:
    """One corpus cell: its key, the templates it copies, and how it computes its value."""

    key: str
    templates: tuple[str, ...]
    compute: Callable[[CellContext], CellValue]


def cell_key(mode: str, shape: str, stamp: str, window: str, variant: str | None = None) -> str:
    key = f"{mode}|{shape}|stamp={stamp}|window={window}"
    return f"{key}|{variant}" if variant else key


def normalize_text(text: str, roots: Sequence[Path] = ()) -> str:
    """Collapse whitespace and backticks, replace temporary roots, SHAs, ULIDs and timestamps by stable labels."""
    for index, root in enumerate(roots):
        text = text.replace(str(root), f"<root{index}>")
    labels: dict[str, str] = {}

    def _label(match: re.Match[str]) -> str:
        token = match.group(0)
        return labels.setdefault(token, f"<sha:{len(labels) + 1}>")

    text = _HEX.sub(_label, text)
    text = _ULID.sub("<ulid>", text)
    text = _ISO_TS.sub("<ts>", text)
    return " ".join(text.replace("`", "").split())


_REFUSAL_MARKERS = ("Reconciliation refused", "Reconciliation FAILED", "Error:")
_PASS_MARKER = "Reconciliation verified"
_ROLLBACK_MARKER = "Rollback to the pre-consolidation snapshot"


def _verdict_text(result: CellResult, mission: ShapeMission) -> str:
    """The operator-facing verdict, normalized.

    Forecast (``--json``): the payload's ``error``. Otherwise the refusal or failure block, from its
    header to the rollback report (exclusive), or the one ``Reconciliation verified`` line of a pass.
    """
    roots = (mission.root,)
    stripped = result.output.strip()
    with contextlib.suppress(ValueError):
        payload = json.loads(stripped.splitlines()[-1]) if stripped else {}
        if isinstance(payload, dict) and "error" in payload:
            return normalize_text(str(payload["error"]), roots)
    lines = result.output.splitlines()
    for index, line in enumerate(lines):
        if any(marker in line for marker in _REFUSAL_MARKERS):
            block: list[str] = []
            for candidate in lines[index:]:
                if _ROLLBACK_MARKER in candidate:
                    break
                block.append(candidate)
            return normalize_text("\n".join(block), roots)
    return normalize_text(next((line for line in lines if _PASS_MARKER in line), ""), roots)


def _run_cell(mission: ShapeMission, mode: str, *extra: str, pin_text: bool = False) -> CellValue:
    result = run_in_process(mission, consolidate_args(mission, mode, *extra))
    value = result.cell()
    if pin_text:
        value["text"] = _verdict_text(result, mission)
    return value


def _generic_state(ctx: CellContext, shape: str, stamp: str, window: str, label: str) -> ShapeMission:
    mission = ctx.copy(shape, label)
    apply_stamp(mission, stamp)
    set_window_states(mission, window)
    return mission


def _generic_compute(mode: str, shape: str, stamp: str, window: str) -> Callable[[CellContext], CellValue]:
    def _compute(ctx: CellContext) -> CellValue:
        mission = _generic_state(ctx, shape, stamp, window, mode)
        if mode == "resume":
            try:
                return resume_after_interrupt(mission).cell()
            except ResumeUnreachableError as unreachable:
                return {"mode_not_applicable": RESUME_UNREACHABLE, "interrupted_run": unreachable.interrupted_run}
        return _run_cell(mission, mode)

    return _compute


def _static(value: CellValue) -> Callable[[CellContext], CellValue]:
    return lambda _ctx: dict(value)


def _shape_topology(shape: str) -> str:
    return {"planning_lane": "lanes", "single_branch": "single_branch"}.get(shape, "coord")


def generic_cells() -> list[Cell]:
    """Mode x shape x stamp x window, pruned by P1-P3 (see the test module docstring)."""
    cells: list[Cell] = []
    for mode in MODES:
        for shape in SHAPES:
            for stamp in STAMPS:
                windows = WINDOWS if (stamp == "present" and shape in LANE_SHAPES) else (WINDOW_ANY,)  # P1, P2
                for window in windows:
                    key = cell_key(mode, shape, stamp, window)
                    if mode == "resume" and _shape_topology(shape) != "coord":  # P3
                        cells.append(Cell(key, (), _static({"mode_not_applicable": MODE_NA_RESUME})))
                    elif shape == "planning_lane" and stamp != "present":
                        cells.append(Cell(key, (), _static({"not_applicable": NA_PLANNING_STAMP})))
                    else:
                        cells.append(Cell(key, (shape,), _generic_compute(mode, shape, stamp, window)))
    return cells


# ---- named cells: NFR-002 (a)-(h)


def _two_wp_windows(first: str, second: str) -> Callable[[ShapeMission], None]:
    def _apply(mission: ShapeMission) -> None:
        set_window_state(mission, "WP01", first)
        set_window_state(mission, "WP02", second)

    return _apply


def _windowed(
    template: str, mode: str, windows: Callable[[ShapeMission], None], *, pin_text: bool = False, extra: Sequence[str] = ()
) -> Callable[[CellContext], CellValue]:
    def _compute(ctx: CellContext) -> CellValue:
        mission = ctx.copy(template, mode)
        windows(mission)
        return _run_cell(mission, mode, *extra, pin_text=pin_text)

    return _compute


def _all_windows(state: str) -> Callable[[ShapeMission], None]:
    return lambda mission: set_window_states(mission, state)


def _recorded_by_the_shell(_mission: ShapeMission) -> None:
    """Keep the windows the production status shell recorded: the cell's events are the pipeline's own, never rewritten."""


def _single_branch_recorded(mission: ShapeMission) -> None:
    for wp_id in ("WP01", "WP02"):
        set_window_state(mission, wp_id, "recorded")


def _fault_history_read_error(ctx: CellContext) -> CellValue:
    """(d) FR-014: a history read of WP01's authored file fails while the claim collects lane-a's authored content.

    Both probe names fail for that one ``(commit, path)`` pair: the walk read it with ``blob_id_at`` before WP16 and reads it
    with ``path_state_at`` since, so the fault reaches the walk on either side of the fix. Every other read is untouched.
    """
    from specify_cli.consolidation import git_probes
    from specify_cli.consolidation.git_probes import GitProbeError

    mission = ctx.copy("single_lane", "fresh")
    set_window_states(mission, "recorded")
    authored = _git(mission.repo, "rev-list", "-1", mission.lane_branches["WP01"], "--", WP01_PATH)

    def _failing_for(real: Callable[[Path, str, str], str | None]) -> Callable[[Path, str, str], str | None]:
        def _failing(repo_root: Path, ref: str, path: str) -> str | None:
            if ref == authored and path == WP01_PATH:
                raise GitProbeError(f"injected history-read error for {path} at {ref}")
            return real(repo_root, ref, path)

        return _failing

    with pytest.MonkeyPatch.context() as patch:
        for name in ("blob_id_at", "path_state_at"):
            setattr_reconciliation_family(patch, name, _failing_for(getattr(git_probes, name)))
        return _run_cell(mission, "fresh")


@contextlib.contextmanager
def lane_checkout(mission: ShapeMission, branch: str) -> Iterator[Path]:
    """The checkout holding *branch*, or a temporary worktree of it (removed afterwards) when none does."""
    existing = _worktree_of(mission.repo, branch)
    if existing is not None:
        yield existing
        return
    temporary = mission.root / f"tmp-wt-{branch.replace('/', '_')}"
    _git(mission.repo, "worktree", "add", "-q", str(temporary), branch)
    try:
        yield temporary
    finally:
        _git(mission.repo, "worktree", "remove", "--force", str(temporary))


def _advance_lane(mission: ShapeMission, wp_id: str, path: str, message: str) -> str:
    with lane_checkout(mission, mission.lane_branches[wp_id]) as checkout:
        return _commit_in(checkout, path, f"ADVANCED = {path!r}\n", message)


def _resume_with(template: str, between: Callable[[ShapeMission], None]) -> Callable[[CellContext], CellValue]:
    """A resume cell whose dependency lane moves between the interruption and the resume; the verdict text is pinned.

    The codes alone may not change when the anchors do (the dependency lane's own check can refuse
    either way), so the pinned text carries the per-lane refusals an anchor change would alter.
    """

    def _compute(ctx: CellContext) -> CellValue:
        mission = ctx.copy(template, "resume")
        set_window_states(mission, "recorded")
        result = resume_after_interrupt(mission, between=between)
        return {**result.cell(), "text": _verdict_text(result, mission)}

    return _compute


def _mixed_dependency_advances(mission: ShapeMission) -> None:
    """(e): the dependency lane of the mixed lane gains a commit after the interruption, and the mixed lane merges it."""
    dependency = sorted({wp for wp in mission.lane_branches if wp not in mission.canceled_wps and wp != mission.subject_wp})
    dependency_wp = next((wp for wp in dependency if mission.lane_branches[wp] != mission.lane_branches[mission.subject_wp]), dependency[0])
    _advance_lane(mission, dependency_wp, "src/advanced/after_interrupt.py", "feat: dependency lane advanced after the interruption")
    with lane_checkout(mission, mission.lane_branches[mission.subject_wp]) as mixed_lane:
        _git(mixed_lane, "merge", "-q", "--no-ff", "--no-edit", mission.lane_branches[dependency_wp])


def _chain_dependency_advances_and_merges(mission: ShapeMission) -> None:
    """(f): lane-a gains a commit after the interruption and lane-b merges it."""
    _advance_lane(mission, "WP01", "src/advanced/after_interrupt.py", "feat: dependency lane advanced after the interruption")
    with lane_checkout(mission, mission.lane_branches["WP02"]) as lane_b:
        _git(lane_b, "merge", "-q", "--no-ff", "--no-edit", mission.lane_branches["WP01"])


def _canceled_lane_advances(mission: ShapeMission) -> None:
    """(g): the fully-canceled dependency lane gains a commit after the interruption."""
    _advance_lane(mission, "WP01", "src/advanced/after_interrupt.py", "feat: canceled dependency lane advanced after the interruption")


# ---- mutation-target cells (WP06)


def _lane_commit_during_run(ctx: CellContext) -> CellValue:
    """A lane commit lands after the claim and before the gate (wraps the first lane-merge step, ``_inject_then_merge`` model)."""
    from specify_cli.consolidation import executor
    from specify_cli.consolidation.phase_advance import _phase_merge_lanes as real

    mission = ctx.copy("single_lane", "fresh")

    def _inject_then_merge(run: Any) -> None:
        _advance_lane(mission, "WP01", "src/pkg/during_run.py", "feat: unreviewed change added during consolidate")
        real(run)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(executor, "_phase_merge_lanes", _inject_then_merge)
        return _run_cell(mission, "fresh")


DEP_BRANCH = "dep-branch"


def _dependency_ref(ctx: CellContext) -> CellValue:
    """``--dependency-ref`` naming an external branch merged into lane-a, lane re-approved (the #6771 model)."""
    from tests.terminus.conftest import restamp_approvals_at_lane_tips

    mission = ctx.copy("single_lane", "fresh")
    repo = mission.repo
    root_commit = _git(repo, "rev-list", "--max-parents=0", mission.target_branch)
    _git(repo, "branch", DEP_BRANCH, root_commit)
    dep_wt = ctx.scratch / "dep-wt"
    _git(repo, "worktree", "add", "-q", str(dep_wt), DEP_BRANCH)
    _commit_in(dep_wt, "src/dep/mod0.py", "DEP = 0\n", "feat(dep): mod0")
    _git(repo, "worktree", "remove", str(dep_wt))
    with lane_checkout(mission, mission.lane_branches["WP01"]) as lane_a:
        _git(lane_a, "merge", "-q", "--no-ff", "--no-edit", DEP_BRANCH)
    restamp_approvals_at_lane_tips(mission.coord_mission())
    return _run_cell(mission, "fresh", "--dependency-ref", DEP_BRANCH)


def _unattributable_squash_path(ctx: CellContext) -> CellValue:
    """A content commit on the mission (coordination) branch outside every lane before the gate (default squash)."""
    mission = ctx.copy("single_lane", "fresh")
    coord = _worktree_of(mission.repo, mission.mission_branch)
    if coord is None:
        raise AssertionError("no checkout holds the coordination branch")
    _commit_in(coord, "src/outside/unowned.py", "UNOWNED = True\n", "feat: content outside every lane")
    return _run_cell(mission, "fresh")


def _staged_deletions_interrupted(ctx: CellContext) -> tuple[Any, ShapeMission]:
    from tests.terminus.approved_content_support import InterruptedConsolidate

    run = InterruptedConsolidate(ctx.scratch, "kill_coord", "squash", mid8="01M6Y2A1")
    mission = _from_coord(run.mission, "coord", subject_wp="WP01", window_wps=("WP01", "WP02"))
    state = _state_json(mission)
    if state is None or not json.loads(state.read_text(encoding="utf-8")).get("pre_interrupt_lane_tips"):
        raise AssertionError("resume precondition: the killed run left no record with pre_interrupt_lane_tips")
    _git(run.lagging, "commit", "-qm", "operator: commit the staged changes")
    run.operator_clears_stale_locks()
    return run, mission


def _resume_approved_content_missing(ctx: CellContext) -> CellValue:
    """The lagging checkout's staged deletions committed, then ``--resume`` (``test_resume_refuses_committed_staged_deletions``)."""
    _run, mission = _staged_deletions_interrupted(ctx)
    return run_in_process(mission, consolidate_args(mission, "resume")).cell()


def _fresh_approved_content_missing_released(ctx: CellContext) -> CellValue:
    """The same committed deletions kept with ``--abort --release-branch``, then a fresh run: the path that reaches the presence axis (#5788)."""
    _run, mission = _staged_deletions_interrupted(ctx)
    released = run_in_process(
        mission, ["consolidate", "--abort", "--mission", mission.slug, "--release-branch", mission.mission_branch, "--release-reason", "keep the operator commit"]
    )
    if released.exit_code != 0:
        raise AssertionError(f"precondition: the release clears the record:\n{released.output}")
    return _run_cell(mission, "fresh")


def _dependency_ref_names_mission_work(ctx: CellContext) -> CellValue:
    """``--dependency-ref`` naming the Mission's own lane branch: the declaration must be refused as Mission work (#6771 namespace guard)."""
    mission = ctx.copy("single_lane", "fresh")
    return _run_cell(mission, "fresh", "--dependency-ref", mission.lane_branches["WP01"])


# ---- exception and weaker-check cells (pinned as passing today)


def _all_gap_post_approval(ctx: CellContext) -> CellValue:
    """FR-023: every work package of the lane has a window gap and a commit lands after WP01's approval; refusal text pinned."""
    mission = ctx.copy("single_lane", "fresh")
    set_window_states(mission, "capture_failed")
    add_post_approval_commit(mission.coord_mission())
    return _run_cell(mission, "fresh", pin_text=True)


def _skewed_clock_rework(ctx: CellContext) -> CellValue:
    """WP01 reworked and re-approved; the rework opener's clock runs an hour behind the first approval."""
    mission = ctx.copy("single_lane", "fresh")
    coord = mission.coord_mission()
    rework_and_reapprove(coord, "WP01")
    approvals = [e for e in _events(mission) if e.get("wp_id") == "WP01" and e.get("to_lane") == "approved"]
    first_approval_at = str(approvals[0]["at"])
    skewed = _shift_iso(first_approval_at, hours=-1)

    def _skew(event: dict[str, Any]) -> dict[str, Any] | None:
        if event.get("wp_id") == "WP01" and event.get("from_lane") == "approved" and event.get("to_lane") == "in_progress":
            return {**event, "at": skewed}
        return None

    rewrite_events(mission, _skew, "test: skew the rework opener's clock")
    set_window_states(mission, "recorded")
    return _run_cell(mission, "fresh")


def _leading_branch_missing(ctx: CellContext) -> CellValue:
    """WP01's first opener recorded ``lane_branch_missing``, its later opener a recorded SHA."""
    mission = ctx.copy("single_lane", "fresh")
    set_window_state(mission, "WP01", "lane_branch_missing", openers=(0,))
    set_window_state(mission, "WP01", "recorded", openers=(1,))
    set_window_state(mission, "WP02", "recorded")
    return _run_cell(mission, "fresh")


def _r09_post_approval_forecast(ctx: CellContext) -> CellValue:
    """R-09: the ``--dry-run`` verdict on the post-approval-commit fixture."""
    mission = ctx.copy("single_lane", "forecast")
    add_post_approval_commit(mission.coord_mission())
    return _run_cell(mission, "forecast", pin_text=True)


def _events(mission: ShapeMission) -> list[dict[str, Any]]:
    log = mission.feature_dir / _STATUS_EVENTS_FILENAME
    coord_logs = [p for p in _event_logs(mission.repo) if p != log]
    source = coord_logs[0] if coord_logs else log
    return [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]


def _shift_iso(stamp: str, *, hours: int) -> str:
    parsed = parse_iso(stamp.replace("Z", "+00:00"))
    return (parsed + timedelta(hours=hours)).isoformat()


NAMED_KEYS = {
    "a_commit_between_approvals": cell_key("fresh", "two_wp_lane", "present", "recorded", "commit_between_approvals"),
    "a_gap_then_recorded": cell_key("fresh", "two_wp_lane", "present", "gap_then_recorded", "commit_between_approvals"),
    "b_refusal_text": cell_key("fresh", "two_wp_lane", "present", "recorded", "commit_between_approvals_text"),
    "c_rewound_lanes": cell_key("fresh", "two_wp_lane", "present", "recorded", "rewound"),
    "c_rewound_single_branch": cell_key("fresh", "single_branch", "present", "recorded", "rewound"),
    "c_rewound_single_branch_forecast": cell_key("forecast", "single_branch", "present", "recorded", "rewound"),
    "d_history_read_error": cell_key("fresh", "single_lane", "present", "recorded", "history_read_error"),
    "e_resume_closed_world": cell_key("resume", "mixed_lane_canceled_wp", "present", "recorded", "dependency_lane_advanced"),
    "f_resume_approved_bound": cell_key("resume", "dependency_chain", "present", "recorded", "dependency_lane_advanced_and_merged"),
    "g_resume_fully_canceled": cell_key("resume", "fully_canceled_dependency", "present", "recorded", "canceled_lane_advanced"),
    "h_forecast_excluded_canceled": cell_key("forecast", "mixed_lane_canceled_wp", "present", "recorded", "excluded_canceled"),
    "mut_lane_commit_during_run": "fresh|single_lane|lane_commit_during_run",
    "mut_dependency_ref": "fresh|single_lane|dependency_ref",
    "mut_approved_content_missing": "resume|single_lane|approved_content_missing",
    "mut_approved_content_missing_released": "fresh|single_lane|approved_content_missing_released",
    "mut_unattributable_squash_path": "fresh|single_lane|unattributable_squash_path",
    "mut_canceled_content_leaks": "fresh|mixed_lane_canceled_wp|canceled_content_leaks",
    "mut_canceled_dependency_reachable": "fresh|fully_canceled_dependency|canceled_content_reachable",
    "mut_canceled_dependency_reachable_merge": "fresh|fully_canceled_dependency|canceled_content_reachable|strategy=merge",
    "mut_dependency_ref_mission_work": "fresh|single_lane|dependency_ref_names_mission_work",
    "x_dependency_chain_exception": cell_key("fresh", "dependency_chain", "present", "recorded", "fr007_exception"),
    "x_gap_covers_stray": cell_key("fresh", "two_wp_lane", "present", "recorded_then_gap", "commit_between_approvals"),
    "x_all_gap_post_approval": cell_key("fresh", "single_lane", "present", "capture_failed", "all_gap_post_approval_commit"),
    "x_skewed_clock_rework": cell_key("fresh", "single_lane", "present", "recorded", "skewed_clock_rework"),
    "x_leading_branch_missing": cell_key("fresh", "single_lane", "present", "lane_branch_missing_then_recorded", "leading_branch_missing"),
    "r09_post_approval_forecast": "forecast|single_lane|post_approval_commit",
    "x_canceled_commit_before_window": cell_key("fresh", "mixed_lane_canceled_wp", "present", "recorded", "canceled_commit_before_window"),
    "x_canceled_commit_before_window_superseded": cell_key("fresh", "mixed_lane_canceled_wp", "present", "recorded", "canceled_commit_before_window_superseded"),
    # Pre-PR fold M9: a declared, pinned external ref merged into the lane before its first window (#6771 x FR-007).
    "x_dependency_ref_before_window": cell_key("fresh", "single_lane", "present", "recorded", "dependency_ref_merged_before_window"),
}


def named_cells() -> list[Cell]:
    """The NFR-002 cells (a)-(h), the WP06 mutation targets, the exception cells and R-09, each addressable by key."""
    k = NAMED_KEYS
    recorded = _all_windows("recorded")
    return [
        Cell(k["a_commit_between_approvals"], ("two_wp_lane_stray",), _windowed("two_wp_lane_stray", "fresh", recorded)),
        Cell(k["a_gap_then_recorded"], ("two_wp_lane_stray",), _windowed("two_wp_lane_stray", "fresh", _two_wp_windows("capture_failed", "recorded"))),
        Cell(k["b_refusal_text"], ("two_wp_lane_stray",), _windowed("two_wp_lane_stray", "fresh", recorded, pin_text=True)),
        Cell(k["c_rewound_lanes"], ("two_wp_lane_rewound",), _windowed("two_wp_lane_rewound", "fresh", recorded)),
        Cell(k["c_rewound_single_branch"], ("single_branch_rewound",), _windowed("single_branch_rewound", "fresh", _single_branch_recorded)),
        Cell(k["c_rewound_single_branch_forecast"], ("single_branch_rewound",), _windowed("single_branch_rewound", "forecast", _single_branch_recorded)),
        Cell(k["d_history_read_error"], ("single_lane",), _fault_history_read_error),
        Cell(k["e_resume_closed_world"], ("mixed_lane_with_dependency",), _resume_with("mixed_lane_with_dependency", _mixed_dependency_advances)),
        Cell(k["f_resume_approved_bound"], ("dependency_chain",), _resume_with("dependency_chain", _chain_dependency_advances_and_merges)),
        Cell(k["g_resume_fully_canceled"], ("fully_canceled_dependency",), _resume_with("fully_canceled_dependency", _canceled_lane_advances)),
        Cell(k["h_forecast_excluded_canceled"], ("mixed_lane_canceled_wp",), _windowed("mixed_lane_canceled_wp", "forecast", recorded)),
        Cell(k["mut_lane_commit_during_run"], ("single_lane",), _lane_commit_during_run),
        Cell(k["mut_dependency_ref"], ("single_lane",), _dependency_ref),
        Cell(k["mut_approved_content_missing"], (), _resume_approved_content_missing),
        Cell(k["mut_approved_content_missing_released"], (), _fresh_approved_content_missing_released),
        Cell(k["mut_unattributable_squash_path"], ("single_lane",), _unattributable_squash_path),
        Cell(k["mut_canceled_content_leaks"], ("mixed_lane_canceled_leaks",), _windowed("mixed_lane_canceled_leaks", "fresh", recorded)),
        Cell(k["mut_canceled_dependency_reachable"], ("fully_canceled_dependency_reachable",), _windowed("fully_canceled_dependency_reachable", "fresh", recorded)),
        Cell(
            k["mut_canceled_dependency_reachable_merge"],
            ("fully_canceled_dependency_reachable",),
            _windowed("fully_canceled_dependency_reachable", "fresh", recorded, extra=("--strategy", "merge")),
        ),
        Cell(k["mut_dependency_ref_mission_work"], ("single_lane",), _dependency_ref_names_mission_work),
        Cell(k["x_dependency_chain_exception"], ("dependency_chain_stray",), _windowed("dependency_chain_stray", "fresh", recorded)),
        Cell(k["x_gap_covers_stray"], ("two_wp_lane_stray",), _windowed("two_wp_lane_stray", "fresh", _two_wp_windows("recorded", "not_recorded"))),
        Cell(k["x_all_gap_post_approval"], ("single_lane",), _all_gap_post_approval),
        Cell(k["x_skewed_clock_rework"], ("single_lane",), _skewed_clock_rework),
        Cell(k["x_leading_branch_missing"], ("single_lane",), _leading_branch_missing),
        Cell(k["r09_post_approval_forecast"], ("single_lane",), _r09_post_approval_forecast),
        # Operator ruling 2026-11-09 (WP19 R1): canceled WP02's own commit before WP01's recorded window is judged by the
        # mixed-lane / canceled-content rules alone, never by the window check (windows recorded by the status shell).
        Cell(k["x_canceled_commit_before_window"], ("mixed_lane_shell",), _windowed("mixed_lane_shell", "fresh", _recorded_by_the_shell)),
        Cell(
            k["x_canceled_commit_before_window_superseded"],
            ("mixed_lane_shell_superseded",),
            _windowed("mixed_lane_shell_superseded", "fresh", _recorded_by_the_shell),
        ),
        Cell(
            k["x_dependency_ref_before_window"],
            ("dependency_ref_before_window",),
            _windowed("dependency_ref_before_window", "fresh", _recorded_by_the_shell, extra=("--dependency-ref", DEP_BRANCH), pin_text=True),
        ),
    ]


def all_cells() -> dict[str, Cell]:
    cells = [*generic_cells(), *named_cells()]
    registry = {cell.key: cell for cell in cells}
    if len(registry) != len(cells):
        raise AssertionError("duplicate corpus cell keys")
    return dict(sorted(registry.items()))


# --------------------------------------------------------------------------- computing cells


def _template_order(names: Sequence[str]) -> list[list[str]]:
    """*names* plus their dependencies, as build levels (each level depends only on earlier ones)."""
    wanted: set[str] = set()
    pending = list(names)
    while pending:
        name = pending.pop()
        if name in wanted:
            continue
        wanted.add(name)
        dependency = TEMPLATES[name][0]
        if dependency is not None:
            pending.append(dependency)
    levels: list[list[str]] = []
    built: set[str] = set()
    while wanted - built:
        level = sorted(n for n in wanted - built if TEMPLATES[n][0] is None or TEMPLATES[n][0] in built)
        levels.append(level)
        built.update(level)
    return levels


def _build_template(args: tuple[str, Path, ShapeMission | None]) -> tuple[str, ShapeMission]:
    name, dest, dependency = args
    return name, TEMPLATES[name][1](dest, dependency)


def _compute_one(args: tuple[str, Mapping[str, ShapeMission], Path]) -> tuple[str, CellValue]:
    key, templates, scratch = args
    cell = all_cells()[key]
    scratch.mkdir(parents=True, exist_ok=True)
    return key, cell.compute(CellContext(templates=templates, scratch=scratch))


def stop_inherited_tracing() -> None:
    """Stop, in a forked child, the coverage measurement and trace hooks it inherited from the parent.

    A forked child exits through ``os._exit``, so whatever a ``pytest --cov`` tracer records in it is
    never saved; left running, the tracer only slows every line the child executes (the full corpus
    under ``--cov`` on a 4-vCPU runner took ~590 s of its 600 s budget). Nothing is saved here either:
    ``Coverage.stop`` only detaches the collector. Module state, so a monkeypatch applied in the parent
    before the fork, is untouched. Without a running tracer this is a no-op.
    """
    coverage = sys.modules.get("coverage")  # a running tracer has imported it; never import it here
    while coverage is not None and (running := coverage.Coverage.current()) is not None:
        running.stop()
    sys.settrace(None)
    threading.settrace(None)


def _map(function: Callable[[Any], Any], items: Sequence[Any], workers: int) -> list[Any]:
    if workers <= 1 or len(items) <= 1:
        return [function(item) for item in items]
    with warnings.catch_warnings():
        # Python 3.12+ warns on fork() from a multi-threaded process (an xdist worker); the forked
        # workers only build repositories and run the CLI, and each returns a plain value.
        warnings.simplefilter("ignore", DeprecationWarning)
        context = multiprocessing.get_context("fork")
        with context.Pool(processes=min(workers, len(items)), initializer=stop_inherited_tracing) as pool:
            return pool.map(function, items, chunksize=1)


def compute_cells(names: Sequence[str], workdir: Path, *, workers: int = 1) -> dict[str, CellValue]:
    """Compute the corpus cells *names* under *workdir* and return their values.

    ``workers=1`` computes every cell in THIS process. ``workers>1`` forks worker processes from
    this process (``multiprocessing`` ``fork`` context), so a patch applied here before the call is
    inherited by every worker; the templates are built once and copied per cell either way.
    """
    registry = all_cells()
    unknown = sorted(set(names) - set(registry))
    if unknown:
        raise KeyError(f"unknown corpus cells: {unknown}")
    templates: dict[str, ShapeMission] = {}
    needed = sorted({t for name in names for t in registry[name].templates})
    for level in _template_order(needed):
        jobs = [(name, workdir / "templates" / name, templates.get(TEMPLATES[name][0] or "")) for name in level]
        for name, mission in _map(_build_template, jobs, workers):
            templates[name] = mission
    jobs2 = [(name, templates, workdir / "cells" / f"{index:04d}") for index, name in enumerate(names)]
    return dict(sorted(_map(_compute_one, jobs2, workers)))


WORKERS_ENV = "SPEC_KITTY_VERDICT_CORPUS_WORKERS"


#: Set by ``pytest-xdist`` in each of its worker processes.
_XDIST_WORKER_ENV = "PYTEST_XDIST_WORKER"


def corpus_workers() -> int:
    """Forked workers for the full corpus.

    ``$SPEC_KITTY_VERDICT_CORPUS_WORKERS`` when set (``1`` = all in this process); else ``1`` inside a
    ``pytest-xdist`` worker (``-n auto`` already runs one worker per core, so forking up to 8 more per
    worker would oversubscribe the machine); else up to 8.
    """
    configured = os.environ.get(WORKERS_ENV, "").strip()
    if configured:
        return max(1, int(configured))
    if os.environ.get(_XDIST_WORKER_ENV):
        return 1
    return max(1, min(8, (os.cpu_count() or 1)))


# --------------------------------------------------------------------------- the golden file


def dump_golden(cells: Mapping[str, CellValue]) -> str:
    return json.dumps(dict(sorted(cells.items())), indent=2, sort_keys=True) + "\n"


def load_golden(path: Path = GOLDEN_PATH) -> dict[str, CellValue]:
    if not path.exists():
        return {}
    loaded: dict[str, CellValue] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def write_golden(cells: Mapping[str, CellValue], path: Path = GOLDEN_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_golden(cells), encoding="utf-8")


def cell_diff(expected: Mapping[str, CellValue], actual: Mapping[str, CellValue]) -> str:
    """A unified diff of the cells whose values differ (added and removed keys included)."""
    chunks: list[str] = []
    for key in sorted(set(expected) | set(actual)):
        if expected.get(key) == actual.get(key):
            continue
        before = json.dumps(expected.get(key), indent=2, sort_keys=True).splitlines() if key in expected else []
        after = json.dumps(actual.get(key), indent=2, sort_keys=True).splitlines() if key in actual else []
        chunks.extend(difflib.unified_diff(before, after, f"golden {key}", f"actual {key}", lineterm=""))
    return "\n".join(chunks)


def assert_cells_match(cells: Mapping[str, CellValue], golden: Mapping[str, CellValue] | None = None) -> None:
    """Every computed cell equals its golden value (only the keys of *cells* are compared)."""
    reference = load_golden() if golden is None else golden
    subset = {key: reference[key] for key in cells if key in reference}
    diff = cell_diff(subset, cells)
    if diff:
        raise AssertionError(
            f"verdict corpus differs from the golden file ({len(cells)} cells compared); regenerate with {REGEN_ENV}=1 only for named cells:\n{diff}"
        )


def regenerate_cells(names: Sequence[str], workdir: Path, *, workers: int = 1) -> dict[str, CellValue]:
    """Recompute only *names* and write them into the golden file, every other cell untouched."""
    computed = compute_cells(names, workdir, workers=workers)
    golden = load_golden()
    golden.update(computed)
    write_golden(golden)
    return computed


def changed_cells(base_ref: str, *, repo: Path | None = None, golden_path: Path = GOLDEN_PATH) -> list[str]:
    """Sorted cell keys whose value differs between the golden file at *base_ref* and the working tree.

    Reads ``git show <base_ref>:tests/consolidation/characterization/verdict_corpus.json``; a key
    added or removed counts as changed. *base_ref* must resolve to a commit (``ValueError``
    otherwise: a typo must never read as "every cell added"); only a golden file absent at a valid
    *base_ref* reads as empty.
    """
    root = repo if repo is not None else Path(_git(golden_path.parent, "rev-parse", "--show-toplevel"))
    if _try_git(root, "rev-parse", "--verify", "-q", f"{base_ref}^{{commit}}") is None:
        raise ValueError(f"changed_cells: {base_ref!r} does not resolve to a commit in {root}")
    relative = golden_path.resolve().relative_to(root.resolve()).as_posix()
    present = _try_git(root, "cat-file", "-e", f"{base_ref}:{relative}") is not None
    before: dict[str, CellValue] = json.loads(_git(root, "show", f"{base_ref}:{relative}")) if present else {}
    after = load_golden(golden_path)
    return sorted(key for key in set(before) | set(after) if before.get(key) != after.get(key))
