"""Project skills on Windows compare the read-only attribute (#4927, operator ruling 2026-11-20).

Before this Mission the project-skill planner ignored every Windows file mode,
so read-only drift -- the one permission NTFS can represent, and the one that
blocks later writes and deletes (#6228, #3771) -- was never repaired. Now a
managed skill file whose read-only state differs from the plan is repaired,
and a converged project still plans nothing.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from specify_cli.skills.installer import apply_project_skills, assess_project_skills, recheck_project_skills
from tests.specify_cli.skills.test_installer import _install_one_converged_skill
from tests.specify_cli.tool_surface.ntfs_emulation import emulate_ntfs

pytestmark = [pytest.mark.fast]


def _apply(inputs: object, registry: object) -> None:
    assessment = assess_project_skills(inputs, registry, ("claude",))
    assert assessment.complete, assessment.diagnostics
    with recheck_project_skills(assessment) as diagnostics:
        assert not diagnostics, diagnostics
        result = apply_project_skills(assessment, assessment.consent)
    assert result.outcome == "applied", result


def test_converged_project_plans_nothing_on_windows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _installed, inputs, registry = _install_one_converged_skill(tmp_path)
    emulate_ntfs(monkeypatch)

    assessment = assess_project_skills(inputs, registry, ("claude",))

    assert assessment.complete, assessment.diagnostics
    assert assessment.effects == ()


def test_writable_copy_of_a_read_only_skill_file_is_repaired_on_windows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    installed, inputs, registry = _install_one_converged_skill(tmp_path)
    assert not stat.S_IMODE(installed.stat().st_mode) & 0o200, "control: project skill files are planned read-only"
    emulate_ntfs(monkeypatch)
    os.chmod(installed, 0o644)  # clear the read-only attribute

    assessment = assess_project_skills(inputs, registry, ("claude",))

    assert [(Path(e.destination), e.action) for e in assessment.effects] == [(installed, "chmod")]
    _apply(inputs, registry)
    assert not installed.stat().st_mode & 0o200
    assert assess_project_skills(inputs, registry, ("claude",)).effects == ()
