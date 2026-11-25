"""A converged global home re-plans no permission repair on Windows (#4927).

Reported on Windows: every CLI start (the global skill sync) and every
``upgrade --dry-run`` (``global_bootstrap``) re-planned the same 253 ``chmod``
effects -- each skill directory at NTFS's ``0o777`` against a planned
``0o755`` -- and applying them never changed anything. These tests run that
scenario on Linux through the NTFS emulation, and pin the POSIX twins: mode
drift there must still be planned and still converge.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest

from specify_cli.core.config import CLAUDE_CONFIG_DIR_ENV
from specify_cli.runtime.agent_skills import assess_global_agent_skills, ensure_global_agent_skills
from specify_cli.runtime.asset_preparation import apply_with_reassess, assess_global_assets
from specify_cli.tool_surface.operations import ApplyConsent, OwnerAssessment, PhysicalEffect
from tests.specify_cli.tool_surface.ntfs_emulation import emulate_ntfs

pytestmark = [pytest.mark.fast]


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))
    monkeypatch.delenv(CLAUDE_CONFIG_DIR_ENV, raising=False)
    return home


@pytest.fixture
def posix(monkeypatch: pytest.MonkeyPatch) -> None:
    from kernel import paths as kernel_paths

    monkeypatch.setattr(kernel_paths, "is_windows", lambda: False)


def _apply(assessment: OwnerAssessment, rebuild: Callable[[], OwnerAssessment]) -> None:
    assert assessment.complete, assessment.diagnostics
    if not assessment.effects:
        return
    result = apply_with_reassess(assessment, rebuild, ApplyConsent(automatic=True), converged_log_message="converged")
    assert result.outcome != "failed", result.diagnostics


def _all_global_assets() -> OwnerAssessment:
    return assess_global_assets()


def _chmods(assessment: OwnerAssessment) -> list[PhysicalEffect]:
    return [effect for effect in assessment.effects if effect.action == "chmod"]


def _managed_skill_dir(home: Path) -> Path:
    assessment = assess_global_agent_skills()
    assert not assessment.effects, "control: the home must be converged first"
    roots = sorted({path.parent for path in (home / ".agents" / "skills").glob("*/SKILL.md")})
    assert roots, "control: global skills were materialized under ~/.agents/skills"
    return roots[0]


def test_global_skills_converge_under_emulated_windows(home: Path, posix: None, monkeypatch: pytest.MonkeyPatch) -> None:
    ensure_global_agent_skills()
    assert not assess_global_agent_skills().effects, "control: the POSIX home is converged"

    emulate_ntfs(monkeypatch)

    assert [(e.path, e.action) for e in assess_global_agent_skills().effects] == []
    ensure_global_agent_skills()
    assert [(e.path, e.action) for e in assess_global_agent_skills().effects] == []


def test_fresh_home_converges_in_one_pass_under_emulated_windows(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    emulate_ntfs(monkeypatch)

    ensure_global_agent_skills()

    assert [(e.path, e.action) for e in assess_global_agent_skills().effects] == []


def test_combined_global_assets_plan_no_chmod_under_emulated_windows(home: Path, posix: None, monkeypatch: pytest.MonkeyPatch) -> None:
    _apply(_all_global_assets(), _all_global_assets)
    assert not _all_global_assets().effects, "control: the POSIX home is converged"

    emulate_ntfs(monkeypatch)

    assert [(e.owner, e.path) for e in _chmods(_all_global_assets())] == []


def test_posix_loosened_skill_directory_is_still_repaired(home: Path, posix: None) -> None:
    ensure_global_agent_skills()
    skill_dir = _managed_skill_dir(home)
    os.chmod(skill_dir, 0o777)

    chmods = _chmods(assess_global_agent_skills())

    assert [(Path(e.destination), e.after.mode) for e in chmods] == [(skill_dir, 0o755)]
    ensure_global_agent_skills()
    assert not assess_global_agent_skills().effects
    assert skill_dir.stat().st_mode & 0o777 == 0o755


def test_posix_execute_bit_drift_is_still_repaired(home: Path, posix: None) -> None:
    """No packaged asset is executable today, so the drift runs the other way: a gained exec bit."""
    ensure_global_agent_skills()
    skill_file = _managed_skill_dir(home) / "SKILL.md"
    planned = skill_file.stat().st_mode & 0o777
    os.chmod(skill_file, planned | 0o111)

    chmods = _chmods(assess_global_agent_skills())

    assert [(Path(e.destination), e.after.mode) for e in chmods] == [(skill_file, planned)]
    ensure_global_agent_skills()
    assert not assess_global_agent_skills().effects
    assert skill_file.stat().st_mode & 0o777 == planned


def test_windows_read_only_drift_is_still_repaired(home: Path, posix: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Global skill files are planned read-only; a writable copy is drift Windows can represent."""
    ensure_global_agent_skills()
    skill_file = _managed_skill_dir(home) / "SKILL.md"
    assert not skill_file.stat().st_mode & 0o200, "control: the planned skill file is read-only"
    emulate_ntfs(monkeypatch)
    os.chmod(skill_file, 0o644)  # clear the read-only attribute

    chmods = _chmods(assess_global_agent_skills())

    assert [Path(e.destination) for e in chmods] == [skill_file]
    ensure_global_agent_skills()
    assert not assess_global_agent_skills().effects
    assert not skill_file.stat().st_mode & 0o200
