"""#6715: ``orchestrator-api`` refuses an approved lanes/coord work package with no implementation.

``consolidate-mission`` merges lanes with no claim builder behind it, so the evidence axis the
``consolidate`` claim runs must precede its first lane merge: ``PREFLIGHT_FAILED`` with the codes
in ``data.preflight_error_code(s)`` and no branch moved. ``accept-mission`` refuses the same state
with ``MISSION_NOT_READY`` and ``data.evidence_error_codes``. The control (real owned commits, an
independent reviewer) accepts and consolidates.

Driven through the REAL CLI over real git, reusing the #6715 consolidate fixture.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tests.integration.test_6715_consolidate_lane_evidence import _commit_specs, _git, _sk, drive, on_target, setup_mission

# Each case drives ~50 real CLI calls over four work packages; the default 240 s budget is too
# tight on a loaded runner, so the cases carry their own (pytest.ini: mark, never raise the default).
pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.timeout(1200)]


def _envelope(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert lines, f"expected a JSON envelope on stdout. stdout={result.stdout!r} stderr={result.stderr[-1500:]!r}"
    envelope = json.loads(lines[-1])
    assert isinstance(envelope, dict)
    return envelope


def _mission(tmp_path: Path, topology: str, *, hollow: bool):
    mission = setup_mission(tmp_path, topology)
    research = f"kitty-specs/{mission.slug}/research/notes.md"
    drive(mission, "WP01", "T1", implementer="alice", reviewer="bob", owned_path="src/m1/real.py")
    drive(mission, "WP02", "T2", implementer="claude", reviewer="bob", owned_path=None if hollow else "tools/check.sh")
    drive(mission, "WP03", "T3", implementer="claude", reviewer="bob", owned_path="src/m3/real.py")
    drive(mission, "WP04", "T4", implementer="alice", reviewer="bob", owned_path=research)
    _sk(mission, "agent", "acceptance-verdict", "--mission", mission.slug, "--criterion", "FR-001", "--result", "pass", "--actor", "operator", "--evidence", "qa")
    # The software-dev path conventions ``accept-mission``'s readiness verdict checks before the
    # evidence axis, so a refusal here is the evidence axis's own.
    for convention_dir in ("tests", "docs", f"kitty-specs/{mission.slug}/contracts"):
        keep = mission.repo / convention_dir / ".gitkeep"
        keep.parent.mkdir(parents=True, exist_ok=True)
        keep.write_text("", encoding="utf-8")
        _git(mission.repo, "add", "-f", str(keep.relative_to(mission.repo)))
    _git(mission.repo, "commit", "-qm", "path conventions")
    _commit_specs(mission.repo)
    return mission


def _refs(mission) -> dict[str, str]:
    out = _git(mission.repo, "for-each-ref", "--format=%(refname) %(objectname)", "refs/heads")
    return dict(line.split(" ", 1) for line in out.splitlines() if line)


@pytest.mark.parametrize("topology", ["coord", "lanes"])
def test_hollow_work_package_is_refused_by_accept_and_consolidate_mission(tmp_path: Path, topology: str) -> None:
    mission = _mission(tmp_path, topology, hollow=True)

    accepted = _sk(mission, "orchestrator-api", "accept-mission", "--mission", mission.slug, "--actor", "operator")
    accept_env = _envelope(accepted)
    assert accept_env["success"] is False, accept_env
    assert accept_env["error_code"] == "MISSION_NOT_READY", accept_env
    accept_data = accept_env["data"]
    assert isinstance(accept_data, dict)
    assert accept_data.get("evidence_error_codes") == ["IMPLEMENTATION_MISSING"], accept_env

    before = _refs(mission)
    result = _sk(mission, "orchestrator-api", "consolidate-mission", "--mission", mission.slug, "--strategy", "squash")
    envelope = _envelope(result)
    assert result.returncode != 0, envelope
    assert envelope["success"] is False, envelope
    assert envelope["error_code"] == "PREFLIGHT_FAILED", envelope
    data = envelope["data"]
    assert isinstance(data, dict)
    assert data["preflight_error_code"] == "IMPLEMENTATION_MISSING", envelope
    assert data["preflight_error_codes"] == ["IMPLEMENTATION_MISSING"], envelope
    assert "WP02" in str(data.get("errors")), envelope
    assert _refs(mission) == before, "no branch may move before the refusal"
    assert not on_target(mission, "tools/check.sh")


def test_real_work_accepts_and_consolidates_through_orchestrator_api(tmp_path: Path) -> None:
    """Positive control: real owned commits and an independent reviewer pass the evidence axis on both commands."""
    mission = _mission(tmp_path, "coord", hollow=False)

    accept_env = _envelope(_sk(mission, "orchestrator-api", "accept-mission", "--mission", mission.slug, "--actor", "operator"))
    assert accept_env["success"] is True, accept_env
    _commit_specs(mission.repo)

    result = _sk(mission, "orchestrator-api", "consolidate-mission", "--mission", mission.slug, "--strategy", "squash")
    envelope = _envelope(result)
    assert envelope["success"] is True, envelope
    assert on_target(mission, "tools/check.sh")
