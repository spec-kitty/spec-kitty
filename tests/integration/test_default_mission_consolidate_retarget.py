"""``consolidate --target <b> --retarget`` on default-topology Missions (#7692, FR-003/FR-004/FR-006, C-006, SC-001).

Operator ruling (2026-11-17): ``--retarget`` works for Missions created without ``--topology``
(``topology_source: default``) in the same PR. Both settlement outcomes are driven through the
REAL ``spec-kitty`` CLI (the sibling module's shim, on this checkout's ``src``) over real git:

* ``lanes_with_coord`` (three code lanes): the topic branch is the Mission branch AND the
  coordination branch. The record is written on the topic branch only (``develop`` does not carry
  the Mission directory) and reaches ``develop`` with the landing.
* ``single_branch`` (two WPs): the topic branch is the Mission branch AND the write branch; the
  WPs run in the repository root checkout on it.

``develop`` is cut from the recorded ``work`` after the Mission was created. On the
``lanes_with_coord`` shape it is checked out in the root checkout before ``consolidate`` (the
off-target preflight requires the root checkout on the effective target). On the
``single_branch`` shape the root checkout stays on the topic branch, the way the product
requires: run from any other branch, ``consolidate`` (plain or retarget alike) refuses with
"lanes.json is not on the current checkout, but branch '<topic>' carries this mission ... Run
`git checkout <topic>`", and the landing then switches the write checkout onto the new target
(``_switch_write_checkout_after_single_branch_landing``).

The default ``squash`` strategy folds the record commit made on the topic branch into the
squash merge, so ``develop`` carries the record through the landing, not as a separate
``retarget`` commit; the one-record guarantee is pinned on ``retarget_history`` (one entry).

Control: a plain ``consolidate`` (no ``--target``) of the same fixture lands on the recorded
``work``; :mod:`tests.integration.test_default_mission_consolidate_lands_primary` proves that for
the ``lanes_with_coord`` shape, and :func:`test_single_branch_default_plain_consolidate_lands_on_recorded_target`
proves it for the ``single_branch`` shape (no sibling covers it).
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.integration.test_default_mission_consolidate_lands_primary import (
    _ANALYSIS,
    _SHIM,
    _TARGET,
    Built,
    _ok,
    _quiet,
    branch_exists,
    build,
    cli,
    consolidate,
)
from tests.specify_cli.cli.commands.agent.test_finalize_topology_settlement import (
    THREE_LANES,
    git,
    make_default_mission,
    run_finalize,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.slow]

_NEW = "develop"
_REASON = "e2e-default"
_TWO_WPS = ("src/one.py", "src/two.py")
_UNWRITABLE = "TARGET_OVERRIDE_RECORDED_TARGET_UNWRITABLE"
_RETARGET = ("--target", _NEW, "--retarget", "--retarget-reason", _REASON)


@dataclass(frozen=True)
class Run:
    """A retarget run and the tips read just before it."""

    built: Built
    proc: subprocess.CompletedProcess[str]
    work_tip: str


def _meta_on(built: Built, ref: str) -> dict[str, object]:
    meta: dict[str, object] = json.loads(git(built.root, "show", f"{ref}:{built.rel}/meta.json"))
    return meta


def _cut_develop(built: Built) -> None:
    """``develop`` cut from the recorded ``work`` after the Mission was created, checked out in the root checkout."""
    git(built.root, "checkout", "-q", "-b", _NEW, _TARGET)


def _commit(checkout: Path, *paths: str, message: str) -> None:
    git(checkout, "add", *paths)
    git(checkout, "-c", "user.name=e", "-c", "user.email=e@x", "commit", "-qm", message)


def _commit_all(checkout: Path, message: str) -> None:
    if git(checkout, "status", "--porcelain"):
        _commit(checkout, "-A", message=message)


def build_single_branch(tmp_path: Path) -> Built:
    """A two-WP default Mission settled to ``single_branch``, implemented and approved in the write checkout.

    The write checkout is the repository root checkout on the topic branch (the Mission branch);
    the WPs run there one after the other.
    """
    mission = make_default_mission(tmp_path, _TWO_WPS, standing_on=_TARGET)
    code, payload = run_finalize(mission)
    assert code == 0, payload
    decision = payload["topology_decision"]
    assert isinstance(decision, dict) and decision["settled_topology"] == "single_branch", payload
    shim = tmp_path / "wp20_shim.py"
    shim.write_text(_SHIM, encoding="utf-8")
    built = Built(mission, shim)
    root = built.root
    assert git(root, "branch", "--show-current") == mission.topic
    (root / built.rel / "plan.md").write_text("# Plan\n", encoding="utf-8")
    _commit_all(root, "plan")
    analysis = tmp_path / "analysis.md"
    analysis.write_text(_ANALYSIS, encoding="utf-8")
    _ok(cli(built, "agent", "mission", "record-analysis", "--mission", built.slug, "--input-file", str(analysis)))
    _commit_all(root, "analysis")
    for index, owned in enumerate(_TWO_WPS, start=1):
        wp = f"WP0{index}"
        _ok(cli(built, "agent", "action", "implement", wp, "--agent", "impl", "--mission", built.slug))
        (root / owned).parent.mkdir(parents=True, exist_ok=True)
        (root / owned).write_text(f"X = {index}\n", encoding="utf-8")
        _commit(root, owned, message=f"feat({wp})")
        for to, agent, force in (("for_review", "impl", ()), ("in_review", "rev", ()), ("approved", "rev", ("--force",))):
            _ok(cli(built, "agent", "tasks", "move-task", wp, "--to", to, "--mission", built.slug, "--agent", agent, *force, "--note", agent))
        _commit_all(root, "status")
    return built


def _retarget(built: Built, **hooks: str) -> Run:
    work_tip = git(built.root, "rev-parse", _TARGET)
    return Run(built, consolidate(built, *_RETARGET, hooks=hooks or None), work_tip)


def _assert_retargeted(run: Run, owned: tuple[str, ...]) -> None:
    built, proc = run.built, run.proc
    _ok(proc)
    assert f"Retarget recorded: {_TARGET} -> {_NEW}" in proc.stdout, proc.stdout[-3000:]
    for path in owned:
        git(built.root, "cat-file", "-e", f"{_NEW}:{path}")
    meta = _meta_on(built, _NEW)
    assert meta["target_branch"] == _NEW, meta
    history = meta.get("retarget_history")
    assert isinstance(history, list) and len(history) == 1, meta
    assert history[-1]["from"] == _TARGET and history[-1]["to"] == _NEW, history
    assert meta["mission_number"] == 1, meta
    assert not meta.get("coordination_branch"), meta
    events = git(built.root, "show", f"{_NEW}:{built.rel}/status.events.jsonl")
    lanes = _done_wps(events)
    assert lanes == {f"WP0{i}" for i in range(1, len(owned) + 1)}, events[-2000:]
    assert git(built.root, "rev-parse", _TARGET) == run.work_tip, "the old target moved"
    assert not git(built.root, "status", "--porcelain", "--", "kitty-specs"), git(built.root, "status", "--porcelain")
    assert not branch_exists(built, built.mission.topic)


def _done_wps(events_text: str) -> set[str]:
    """The WPs whose newest event (file order) moves them to ``done``."""
    last: dict[str, str] = {}
    for line in events_text.splitlines():
        if line.strip():
            event = json.loads(line)
            if "to_lane" in event and "wp_id" in event:
                last[event["wp_id"]] = event["to_lane"]
    return {wp for wp, lane in last.items() if lane == "done"}


@pytest.fixture(autouse=True)
def _quiet_status_fanout(monkeypatch: pytest.MonkeyPatch) -> None:
    _quiet(monkeypatch)


@pytest.fixture(scope="module")
def coord_retarget(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Run]:
    with pytest.MonkeyPatch.context() as mp:
        _quiet(mp)
        built = build(tmp_path_factory.mktemp("coord-retarget"))
        _cut_develop(built)
        yield _retarget(built)


@pytest.fixture(scope="module")
def single_retarget(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Run]:
    with pytest.MonkeyPatch.context() as mp:
        _quiet(mp)
        built = build_single_branch(tmp_path_factory.mktemp("single-retarget"))
        git(built.root, "branch", _NEW, _TARGET)
        yield _retarget(built)


# ---------------------------------------------------------------------------
# T025: default lanes_with_coord
# ---------------------------------------------------------------------------


def test_lanes_with_coord_default_retarget_lands_on_new_target(coord_retarget: Run) -> None:
    """Control: a plain ``consolidate`` of this fixture lands on ``work`` (the sibling module's tests)."""
    _assert_retargeted(coord_retarget, THREE_LANES)
    assert not coord_retarget.built.coord_worktree.exists()


# ---------------------------------------------------------------------------
# T026: default single_branch
# ---------------------------------------------------------------------------


def test_single_branch_default_retarget_lands_on_new_target(single_retarget: Run) -> None:
    _assert_retargeted(single_retarget, _TWO_WPS)
    # The landing switches the write checkout onto the new target.
    assert git(single_retarget.built.root, "branch", "--show-current") == _NEW
    assert not git(single_retarget.built.root, "status", "--porcelain"), "the write checkout is not clean"


def test_single_branch_default_plain_consolidate_lands_on_recorded_target(tmp_path: Path) -> None:
    """Control on the same shape: no ``--target`` lands on the recorded ``work``."""
    built = build_single_branch(tmp_path)
    _ok(consolidate(built))
    for path in _TWO_WPS:
        git(built.root, "cat-file", "-e", f"{_TARGET}:{path}")
    meta = _meta_on(built, _TARGET)
    assert meta["target_branch"] == _TARGET and not meta.get("retarget_history"), meta


# ---------------------------------------------------------------------------
# T027: failure and plain-override controls on the default shape
# ---------------------------------------------------------------------------


@pytest.mark.timeout(900)
def test_lanes_with_coord_default_retarget_failure_rolls_back_then_lands_once(tmp_path: Path) -> None:
    built = build(tmp_path)
    _cut_develop(built)
    topic_tip = git(built.root, "rev-parse", built.mission.topic)
    develop_tip = git(built.root, "rev-parse", _NEW)
    failed = _retarget(built, WP20_FAIL_BEFORE="_phase_merge_lanes")
    assert failed.proc.returncode != 0, failed.proc.stdout[-3000:]
    assert git(built.root, "rev-parse", built.mission.topic) == topic_tip, failed.proc.stdout[-3000:]
    assert _meta_on(built, built.mission.topic)["target_branch"] == _TARGET
    assert git(built.root, "rev-parse", _NEW) == develop_tip
    rerun = _retarget(built)
    # ``_assert_retargeted`` pins exactly ONE ``retarget_history`` entry: the rolled-back
    # attempt left no second record behind.
    _assert_retargeted(rerun, THREE_LANES)


def test_lanes_with_coord_default_plain_target_override_refuses(tmp_path: Path) -> None:
    built = build(tmp_path)
    _cut_develop(built)
    tips = git(built.root, "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads")
    proc = consolidate(built, "--target", _NEW)
    output = proc.stdout + proc.stderr
    assert proc.returncode != 0, output[-3000:]
    assert _UNWRITABLE in output, output[-3000:]
    assert "--retarget" in output, output[-3000:]
    assert git(built.root, "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads") == tips
    assert _meta_on(built, built.mission.topic)["target_branch"] == _TARGET
