"""Regression checks for Codex dispatch flags in shipped doctrine skills."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.charter_offering.conftest import OFFERING_SOURCE_ROOT, REPO_ROOT

pytestmark = [pytest.mark.doctrine, pytest.mark.fast]


def _skill_markdown_files() -> list[Path]:
    return sorted((OFFERING_SOURCE_ROOT / "skills").rglob("*.md"))


def test_shipped_charter_skills_do_not_dispatch_codex_with_full_auto() -> None:
    """Codex --full-auto aliases workspace-write and breaks terminal move-task."""
    violations: list[str] = []
    for path in _skill_markdown_files():
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if "codex exec --full-auto" in line:
                violations.append(f"{path.relative_to(REPO_ROOT)}:{line_number}: {line.strip()}")

    assert violations == []


def test_implement_review_codex_dispatch_stays_sandboxed_with_repo_root_writable() -> None:
    """Codex keeps workspace-write and adds the repository root as a writable root (#6477).

    ``move-task`` writes git/status locks in the shared ``.git`` directory and the
    coordination worktree, outside the lane worktree; ``--add-dir`` covers them
    without dropping the sandbox the way ``danger-full-access`` did.
    """
    skill_path = OFFERING_SOURCE_ROOT / "skills" / "spec-kitty-implement-review" / "SKILL.md"
    matrix_path = (
        OFFERING_SOURCE_ROOT
        / "skills"
        / "spec-kitty-implement-review"
        / "references"
        / "agent-dispatch-matrix.md"
    )

    skill = skill_path.read_text(encoding="utf-8")
    matrix = matrix_path.read_text(encoding="utf-8")

    assert "codex exec --full-auto" not in skill
    assert "codex exec --full-auto" not in matrix
    assert "danger-full-access" not in skill
    assert "danger-full-access" not in matrix
    dispatches = [line for line in (skill + matrix).splitlines() if "codex exec --sandbox" in line]
    assert len(dispatches) == 4
    assert all("codex exec --sandbox workspace-write" in line for line in dispatches)
    assert skill.count('--add-dir "$REPO_ROOT" -C "$WORKSPACE" -') == 1
    assert skill.count('--add-dir "$(git rev-parse --show-toplevel)"') == 1
    assert matrix.count("--add-dir <repo-root>") == 1
