"""Regression checks for Codex dispatch flags in shipped doctrine skills."""

from __future__ import annotations

import pytest

from tests.charter_offering.conftest import OFFERING_SOURCE_ROOT

pytestmark = [pytest.mark.doctrine, pytest.mark.fast]


def test_implement_review_codex_dispatch_stays_sandboxed() -> None:
    """Codex dispatches keep ``workspace-write`` with no extra writable root (#6477).

    Its sandbox keeps ``.git`` read-only under every writable root, so widening
    the roots buys no commit ability; the orchestrator commits and runs the
    lifecycle commands instead of dropping the sandbox the way
    ``danger-full-access`` did.
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

    dispatches = [line for line in (skill + matrix).splitlines() if "codex exec --sandbox" in line]
    assert dispatches
    assert all("codex exec --sandbox workspace-write" in line for line in dispatches)
    assert "--add-dir" not in skill + matrix
