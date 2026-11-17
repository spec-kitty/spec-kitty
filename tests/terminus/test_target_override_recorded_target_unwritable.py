"""A ``--target`` override whose recorded target cannot be written is refused up front (#5783).

``consolidate --target develop`` on a Mission recorded for ``main`` lands the
squash on ``develop`` (the EFFECTIVE target), but part of the bookkeeping the run
makes afterwards -- the per-WP ``done`` transitions on a coordination-less
Mission, the coordination flatten -- goes to the Mission's RECORDED target
(``meta.json``), never ``--target``. The repository root checkout is on
``develop`` (the off-target preflight requires it), so those commits cannot run
there (witnessed on ``main`` before the fix):

* lanes: the landing reaches ``develop``, then the ``done`` commit refuses
  ``STATUS_WRITE_CHECKOUT_NOT_ON_WRITE_BRANCH`` (released rc5:
  ``SafeCommitHeadMismatch``), the run rolls back and exits 1;
* coord: the flatten fails open, so the run exits 0 with ``develop`` carrying
  stale metadata (the deleted coordination branch, unflattened) and
  ``meta.json`` left modified.

Operator ruling (2026-11-16): the write target stays the recorded target, and a
retarget whose recorded target cannot be written refuses BEFORE the first
mutation with a named code; ``--dry-run`` forecasts the same refusal.

The Mission's ``main`` is declared unprotected (an empty protected-branch list),
so neither #5385 (recorded target protected) nor #6464 (override target
protected) decides these runs: only the new guard can. The controls run on the
same fixture shapes.

Driven through the REAL ``spec-kitty consolidate`` CLI over real git.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tests.terminus.conftest import CoordMission, blob_present_at, build_coord_mission, run_terminus
from tests.terminus.conftest import _git as git
from tests.terminus.lanes_fixture import build_lanes_mission
from tests.terminus.rollback_harness import flat, reflog_shas

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_CODE = "TARGET_OVERRIDE_RECORDED_TARGET_UNWRITABLE"
_PREFLIGHT_LINE = "Consolidation refused before any branch moved."
_RECORDED = "main"
_OVERRIDE = "develop"
_EMPTY_PROTECTION = "protection:\n  protected_branches: []\n"


def _unprotect_main(mission: CoordMission) -> None:
    """Commit an empty protected-branch list so the recorded ``main`` is writable by policy."""
    config = mission.repo / ".kittify" / "config.yaml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(_EMPTY_PROTECTION, encoding="utf-8")
    git(mission.repo, "add", str(config))
    git(mission.repo, "commit", "-qm", "chore: protection config")


def _lanes(tmp_path: Path, mid8: str, *, target: str = _RECORDED) -> CoordMission:
    mission = build_lanes_mission(tmp_path, wps=("WP01", "WP02"), target_branch=target, mid8=mid8)
    _unprotect_main(mission)
    return mission


def _coord(tmp_path: Path, mid8: str, *, target: str = _RECORDED) -> CoordMission:
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), target_branch=target, mid8=mid8)
    _unprotect_main(mission)
    return mission


def _check_out_override(mission: CoordMission) -> None:
    """The #5783 shape: ``develop`` cut from the recorded target and checked out in the root checkout."""
    git(mission.repo, "checkout", "-qb", _OVERRIDE, _RECORDED)


def _consolidate(mission: CoordMission, *extra: str) -> subprocess.CompletedProcess[str]:
    return run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes", *extra])


def _merge_records(mission: CoordMission) -> list[Path]:
    return sorted((mission.repo / ".kittify" / "runtime" / "merge").glob("*/state.json"))


def _branches(mission: CoordMission) -> dict[str, str]:
    """Every local branch tip, the override target included (``ref_shas`` covers the Mission's own)."""
    out = git(mission.repo, "for-each-ref", "--format=%(refname:short) %(objectname)", "refs/heads").stdout
    return dict(line.split(" ", 1) for line in out.splitlines() if line)


def _reflogs(mission: CoordMission) -> dict[str, list[str]]:
    return {branch: reflog_shas(mission, branch) for branch in (_RECORDED, _OVERRIDE)}


def _assert_refused_before_any_mutation(
    mission: CoordMission, result: subprocess.CompletedProcess[str], before: dict[str, str], reflogs_before: dict[str, list[str]]
) -> None:
    output = flat(result)
    assert result.returncode == 1, f"the retarget must be refused. output={output}"
    assert _CODE in output, f"the refusal must carry the named code. output={output}"
    assert _PREFLIGHT_LINE in output, f"the refusal must come from the up-front preflight. output={output}"
    assert f"--target {_OVERRIDE}" in output and f"'{_RECORDED}'" in output, f"the remedy must name the override and the recorded target. output={output}"
    assert "meta.json" in output, f"the remedy must offer correcting the record. output={output}"
    assert "--retarget" in output, f"the remedy must name the --retarget opt-in (#7692 FR-002). output={output}"
    assert "Traceback" not in result.stderr, f"a refusal is not a crash. stderr={result.stderr}"
    assert _branches(mission) == before, f"no branch tip may move. output={output}"
    assert _reflogs(mission) == reflogs_before, f"no branch may move and come back either. output={output}"
    assert _merge_records(mission) == [], f"no merge record may be written. output={output}"
    assert not blob_present_at(mission.repo, _OVERRIDE, "src/pkg/wp01.py"), f"no squashed content on the override target. output={output}"
    status = git(mission.repo, "status", "--porcelain", "--", "kitty-specs").stdout
    assert status == "", f"a refused run leaves the root checkout clean. status={status!r} output={output}"


@pytest.mark.regression
@pytest.mark.parametrize("build", [_lanes, _coord], ids=["lanes", "coord"])
def test_retarget_with_unwritable_recorded_target_is_refused_before_any_mutation(tmp_path: Path, build) -> None:  # type: ignore[no-untyped-def]
    """#5783: the override arm refuses with the named code; nothing moves, no merge record, exit 1."""
    mission = build(tmp_path, "01M5783O")
    _check_out_override(mission)
    before, reflogs_before = _branches(mission), _reflogs(mission)

    result = _consolidate(mission, "--target", _OVERRIDE)

    _assert_refused_before_any_mutation(mission, result, before, reflogs_before)


@pytest.mark.regression
@pytest.mark.parametrize("build", [_lanes, _coord], ids=["lanes", "coord"])
def test_dry_run_forecasts_the_retarget_refusal(tmp_path: Path, build) -> None:  # type: ignore[no-untyped-def]
    """``--dry-run`` may not promise a landing the real run refuses."""
    mission = build(tmp_path, "01M5783D")
    _check_out_override(mission)
    before = _branches(mission)

    result = run_terminus(mission, ["consolidate", "--dry-run", "--mission", mission.slug, "--json", "--target", _OVERRIDE])

    output = flat(result)
    assert result.returncode == 1, output
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload.get("error_code") == _CODE, payload
    assert f"'{_RECORDED}'" in str(payload.get("error")), payload
    assert _branches(mission) == before, "a refused forecast moves nothing"


@pytest.mark.parametrize("build", [_lanes, _coord], ids=["lanes", "coord"])
def test_control_without_override_lands_on_the_recorded_target(tmp_path: Path, build) -> None:  # type: ignore[no-untyped-def]
    """The control arm: the same Mission onto its recorded ``main`` lands cleanly."""
    mission = build(tmp_path, "01M5783C")

    result = _consolidate(mission)

    output = flat(result)
    assert result.returncode == 0, output
    assert _CODE not in output, output
    assert blob_present_at(mission.repo, _RECORDED, "src/pkg/wp01.py"), output
    assert git(mission.repo, "status", "--porcelain", "--", "kitty-specs").stdout == "", output


@pytest.mark.parametrize("build", [_lanes, _coord], ids=["lanes", "coord"])
def test_control_restating_the_recorded_target_is_not_refused(tmp_path: Path, build) -> None:  # type: ignore[no-untyped-def]
    """``--target <recorded>`` is not a retarget."""
    mission = build(tmp_path, "01M5783R")

    result = _consolidate(mission, "--target", _RECORDED)

    output = flat(result)
    assert result.returncode == 0, output
    assert _CODE not in output, output
    assert blob_present_at(mission.repo, _RECORDED, "src/pkg/wp01.py"), output


@pytest.mark.parametrize("build", [_lanes, _coord], ids=["lanes", "coord"])
def test_control_mission_created_for_develop_lands_there(tmp_path: Path, build) -> None:  # type: ignore[no-untyped-def]
    """The created / metadev arms: a Mission RECORDED for ``develop`` lands on it with no ``--target``."""
    mission = build(tmp_path, "01M5783K", target=_OVERRIDE)

    result = _consolidate(mission)

    output = flat(result)
    assert result.returncode == 0, output
    assert _CODE not in output, output
    assert blob_present_at(mission.repo, _OVERRIDE, "src/pkg/wp01.py"), output
    assert git(mission.repo, "status", "--porcelain", "--", "kitty-specs").stdout == "", output


@pytest.mark.regression
def test_a_retarget_never_leaves_the_recorded_bookkeeping_uncommitted(tmp_path: Path) -> None:
    """Proof of the defect the refusal retires (landing fold, #5783).

    Before the guard, ``consolidate --target develop`` on a coord Mission recorded for ``main``
    was admitted, exited 0, and left the recorded target's bookkeeping (``meta.json``)
    modified and uncommitted in the repository root checkout. The invariant holds for
    either outcome: a retarget run, admitted or refused, never leaves ``kitty-specs/``
    dirty. This test fails on the pre-fix source and passes with the up-front refusal.
    """
    mission = _coord(tmp_path, "01M5783P")
    _check_out_override(mission)

    result = _consolidate(mission, "--target", _OVERRIDE)

    status = git(mission.repo, "status", "--porcelain", "--", "kitty-specs").stdout
    assert status == "", f"a retarget left the recorded target's bookkeeping uncommitted: {status!r} rc={result.returncode} output={flat(result)}"
