"""The forecast reports the claim verdict the fresh run reaches (FR-013, US5, NFR-010; WP17).

``consolidate --dry-run --json`` builds the same reconciliation claim the fresh run builds. These
tests run both on one unmutated Mission (two copies of one template) and compare their claim-time
verdicts through the entry point, not through the claim inputs (the field-level parity lives in
``test_claim_inputs_parity.py``).

It also pins the one state where the forecast's claim inputs cannot equal the fresh run's without
seeding: a pre-fix Mission whose coordination branch holds no status log yet (the read door's
declared pre-seed fallback). That is a named legacy residual, see
:func:`test_pre_seed_forecast_status_dir_and_coord_base_equal_fresh_run`.

A fixture that cannot reach the state under test raises :class:`FixtureNotReached` (a
``RuntimeError``), never an ``AssertionError``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from specify_cli.consolidation import forecast as forecast_module
from specify_cli.consolidation import phase_claim
from specify_cli.consolidation.claim_inputs import ClaimInputs
from specify_cli.status.read_surface import StatusReadSource, resolve_status_read
from tests.consolidation import characterization_support as cs
from tests.consolidation.test_claim_inputs_parity import _approved, _captured_inputs, _status_dir_identity
from tests.terminus import rollback_harness
from tests.terminus.canceled_dependency_support import WP01_PATH
from tests.terminus.conftest import PlantedChange, build_coord_mission_mixed_lane_canceled

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

CLAIM_REFUSED_FORECAST = "CLAIM_REFUSED_FORECAST"
CANCELED_REFUSAL = "canceled WP02 cannot be attributed"


class FixtureNotReached(RuntimeError):
    """The fixture never reached the state under test: an error, never the asserted divergence."""


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-c", "core.hooksPath=/dev/null", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _canceled_wp_without_attribution(tmp_path: Path) -> cs.ShapeMission:
    """A mixed lane (approved WP01 + WP02 canceled with operator provenance) whose canceled WP has no commit attribution."""
    built = build_coord_mission_mixed_lane_canceled(
        tmp_path / "m",
        canceled_changes=(PlantedChange("src/canceled/c.py", "CANCELED = True\n"),),
        survivor_before=(PlantedChange(WP01_PATH, "def wp01() -> int:\n    return 1\n"),),
        stamp_attribution=False,
        mid8="01M6Y8F1",
    )
    return cs._from_coord(built, "coord", subject_wp="WP01", window_wps=("WP01",))


def _forecast_payload(result: cs.CellResult) -> dict[str, Any]:
    """The forecast's ``--json`` refusal object (its last JSON line)."""
    for line in reversed(result.output.splitlines()):
        if line.startswith("{"):
            payload: dict[str, Any] = json.loads(line)
            return payload
    raise FixtureNotReached(f"the forecast printed no JSON object:\n{result.output}")


def _observable_state(mission: cs.ShapeMission) -> tuple[dict[str, str], str, str]:
    """Every branch the run could move, the worktree list, and the coordination branch's commit count."""
    refs = rollback_harness.ref_shas(mission.coord_mission())
    worktrees = _git(mission.repo, "worktree", "list", "--porcelain")
    coord_commits = _git(mission.repo, "rev-list", "--count", mission.mission_branch)
    return refs, worktrees, coord_commits


def test_forecast_reports_the_fresh_runs_claim_verdict_with_an_excluded_canceled_wp(tmp_path: Path) -> None:
    """US5-3: the fresh run excludes the canceled WP02 and refuses its attribution at claim time; the forecast must too.

    Before WP17 the forecast passed no excluded canceled work packages, so WP02 was invisible to its claim and it never
    named the refusal the real run reaches.
    """
    template = _canceled_wp_without_attribution(tmp_path)
    fresh = cs.copy_mission(template, tmp_path / "fresh")
    forecast = cs.copy_mission(template, tmp_path / "forecast")

    fresh_result = cs.run_in_process(fresh, cs.consolidate_args(fresh, "fresh"))
    if fresh_result.exit_code == 0 or fresh_result.status != "refuse" or CANCELED_REFUSAL not in fresh_result.output:
        raise FixtureNotReached(f"the fresh run must refuse WP02's attribution at claim time:\n{fresh_result.output}")

    before = _observable_state(forecast)
    forecast_result = cs.run_in_process(forecast, cs.consolidate_args(forecast, "forecast"))
    after = _observable_state(forecast)
    payload = _forecast_payload(forecast_result)

    assert forecast_result.exit_code != 0, forecast_result.output
    assert payload.get("error_code") == CLAIM_REFUSED_FORECAST, payload
    assert CANCELED_REFUSAL in str(payload.get("error", "")), f"the forecast must report the fresh run's claim-time refusal: {payload}"
    assert set(cs.refusal_codes(str(payload.get("error", "")))) == set(fresh_result.codes), (payload, fresh_result.codes)
    assert after == before, "the dry run must move no branch, add no worktree and commit nothing to the coordination branch"


# --------------------------------------------------------------------------- pre-seed: the coordination branch holds no log yet

_STATUS_FILES = ("status.events.jsonl", "status.json")
_PRE_SEED_RESIDUAL = (
    "named legacy residual (WP17, recorded for the WP21 ADR text): before the first seed the fresh run's write accessor "
    "seeds the coordination worktree and reads it there, measuring its claim from the seed commit; the read-only forecast "
    "reads the same log bytes from the write checkout (the read door's declared pre-seed fallback) at the commit before the "
    "seed. Equal paths and SHAs would need the forecast to seed. Pre-fix Missions only; the first real run removes the state"
)


@pytest.fixture(scope="module")
def pre_seed_template(tmp_path_factory: pytest.TempPathFactory) -> cs.ShapeMission:
    """The approved dependency chain, turned pre-fix: the primary dir holds the log, the coordination branch none.

    The coordination branch drops the Mission dir in one commit (its worktree is then EMPTY) and the repository root
    checkout's copy of the log is overwritten, uncommitted, with the coordination log it held, as a pre-fix Mission keeps it.
    """
    mission = _approved(tmp_path_factory.mktemp("pre_seed"), "dependency_chain")
    coord_dir = resolve_status_read(mission.repo, mission.slug).path
    if coord_dir is None:
        raise FixtureNotReached("the chain's status must be read from the coordination worktree")
    primary_dir = mission.repo / "kitty-specs" / coord_dir.name
    for name in _STATUS_FILES:
        shutil.copy2(coord_dir / name, primary_dir / name)
    coord_worktree = coord_dir.parent.parent
    _git(coord_worktree, "rm", "-r", "-q", f"kitty-specs/{coord_dir.name}")
    _git(coord_worktree, "commit", "-q", "-m", "test: the coordination branch holds no status log yet (pre-fix)")
    surface = resolve_status_read(mission.repo, mission.slug)
    if surface.source is not StatusReadSource.WRITE_CHECKOUT or not surface.fallback_reason:
        raise FixtureNotReached(f"the read door must take the pre-seed fallback, it resolved {surface}")
    return mission


def _pre_seed_inputs(template: cs.ShapeMission, scratch: Path) -> tuple[ClaimInputs, tuple[Path, str], ClaimInputs, tuple[Path, str], cs.ShapeMission]:
    """Forecast and fresh-run claim inputs on two copies of *template*, each status identity read right after its own run."""
    forecast = cs.copy_mission(template, scratch / "forecast")
    fresh = cs.copy_mission(template, scratch / "fresh")
    before = _observable_state(forecast)
    live = _captured_inputs(forecast, "forecast", forecast_module)
    live_identity = _status_dir_identity(live.status_dir)
    if _observable_state(forecast) != before or (forecast.repo / ".worktrees" / f"{forecast.slug}-coord" / "kitty-specs" / live.status_dir.name).exists():
        raise FixtureNotReached("the forecast seeded or moved something; the comparison below would be meaningless")
    saved = _captured_inputs(fresh, "fresh", phase_claim)
    return live, live_identity, saved, _status_dir_identity(saved.status_dir), fresh


def test_pre_seed_forecast_reads_the_log_the_fresh_run_seeds(pre_seed_template: cs.ShapeMission, tmp_path: Path) -> None:
    """Before the first seed the forecast reads the same log bytes and the same tips the fresh run claims from.

    The fresh run measures from its own seed commit, which touches only the Mission's status files and sits directly on the
    coordination tip the forecast measures from: no lane, target or content input differs.
    """
    live, live_identity, fresh, fresh_identity, fresh_mission = _pre_seed_inputs(pre_seed_template, tmp_path)
    seeded = _git(fresh_mission.repo, "show", "--name-only", "--format=", fresh.coord_base).split()

    assert live_identity[1] == fresh_identity[1], "the seed carries the write checkout's log byte for byte"
    assert live.excluded_canceled_wp_ids == fresh.excluded_canceled_wp_ids
    assert dict(live.lane_tips) == dict(fresh.lane_tips)
    assert live.target_base == fresh.target_base
    assert _git(fresh_mission.repo, "rev-parse", f"{fresh.coord_base}^") == live.coord_base, "the fresh run's base is the seed commit on the forecast's base"
    assert sorted(seeded) == sorted(f"kitty-specs/{fresh.status_dir.name}/{name}" for name in _STATUS_FILES), seeded


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=_PRE_SEED_RESIDUAL)
def test_pre_seed_forecast_status_dir_and_coord_base_equal_fresh_run(pre_seed_template: cs.ShapeMission, tmp_path: Path) -> None:
    """Ideal FR-013 parity before the first seed: the same status directory and the same coordination SHA (never flipped here)."""
    live, live_identity, fresh, fresh_identity, _ = _pre_seed_inputs(pre_seed_template, tmp_path)

    assert live_identity == fresh_identity
    assert live.coord_base == fresh.coord_base
