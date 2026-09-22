"""Regression test for issue #4910: intake overwrite gate keys on existence.

``spec-kitty intake <doc>`` silently overwrote a hand-authored
``.kittify/mission-brief.md`` whenever the provenance sidecar
``.kittify/brief-source.yaml`` was absent. Both entry points
(``cli/commands/intake.py:296`` for the explicit/stdin path and ``:156`` for
``--auto``) gated the refusal on ``brief_path.exists() and
_source_path.exists() and not force`` — the ``and`` let a missing sidecar
(e.g. a brief a human authored by hand, or one whose sidecar was deleted)
bypass the refusal entirely, so ``_commit_brief`` silently clobbered it.

The fix drops the ``and _source_path.exists()`` conjunct so the gate is
``if brief_path.exists() and not force:`` at both sites: a missing sidecar
now means "unknown provenance -> refuse", not "safe to overwrite". This is a
pure refuse-without-``--force`` gate; no backup logic is introduced.

Spec IDs: FR-005
"""

from __future__ import annotations

from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.cli.commands.intake import intake
from specify_cli.mission_brief import BRIEF_SOURCE_FILENAME, MISSION_BRIEF_FILENAME
from tests.specify_cli.intake_test_helpers import patched_intake_command_environment

pytestmark = [pytest.mark.regression, pytest.mark.fast, pytest.mark.non_sandbox]

runner = CliRunner()

HAND_AUTHORED_BRIEF = "# Hand-authored brief\n\nDo not clobber me.\n"


@pytest.fixture()
def intake_app() -> typer.Typer:
    """Return a minimal Typer app with only the intake command."""
    app = typer.Typer()
    app.command()(intake)
    return app


def _make_plan_file(tmp_path: Path, rel: str = "plan.md", content: str = "# New Plan") -> Path:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def _seed_brief_without_sidecar(tmp_path: Path, content: str = HAND_AUTHORED_BRIEF) -> Path:
    """Write only the brief file — no sidecar — reproducing #4910's precondition."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    brief_path = kittify / MISSION_BRIEF_FILENAME
    brief_path.write_text(content, encoding="utf-8")
    assert not (kittify / BRIEF_SOURCE_FILENAME).exists()
    return brief_path


# ---------------------------------------------------------------------------
# T013a: explicit path entry point (:296) — brief present, sidecar absent,
# no --force -> refuse, brief byte-identical.
# ---------------------------------------------------------------------------


def test_explicit_path_refuses_when_brief_present_sidecar_absent(intake_app: typer.Typer, tmp_path: Path) -> None:
    """Explicit ``intake <doc>`` must refuse on brief-only state (#4910)."""
    brief_path = _seed_brief_without_sidecar(tmp_path)
    plan = _make_plan_file(tmp_path)

    with patched_intake_command_environment(tmp_path, patch_cwd=False):
        result = runner.invoke(intake_app, [str(plan)], catch_exceptions=False)

    assert result.exit_code != 0, f"output: {result.output}"
    assert "Use --force" in result.output, f"output: {result.output}"
    assert brief_path.read_text(encoding="utf-8") == HAND_AUTHORED_BRIEF, "brief must be byte-identical to the pre-existing hand-authored content"
    assert not (tmp_path / ".kittify" / BRIEF_SOURCE_FILENAME).exists(), "a refused intake must not mint a sidecar either"


# ---------------------------------------------------------------------------
# T013b: --auto entry point (:156) — same precondition, same refusal.
# ---------------------------------------------------------------------------


def test_auto_refuses_when_brief_present_sidecar_absent(intake_app: typer.Typer, tmp_path: Path) -> None:
    """``intake --auto`` must refuse on brief-only state (#4910), 2nd site."""
    brief_path = _seed_brief_without_sidecar(tmp_path)
    _make_plan_file(tmp_path, "opencode-plan.md")
    mock_sources = [("opencode", "opencode", ["opencode-plan.md"])]

    with patched_intake_command_environment(tmp_path, mock_sources):
        result = runner.invoke(intake_app, ["--auto"], catch_exceptions=False)

    assert result.exit_code != 0, f"output: {result.output}"
    assert "Use --force" in result.output, f"output: {result.output}"
    assert brief_path.read_text(encoding="utf-8") == HAND_AUTHORED_BRIEF, "brief must be byte-identical to the pre-existing hand-authored content"
    assert not (tmp_path / ".kittify" / BRIEF_SOURCE_FILENAME).exists(), "a refused intake must not mint a sidecar either"


# ---------------------------------------------------------------------------
# Anchors (must stay green on base and on fix): --force still overwrites a
# brief-only state at both entry points, and both-present already refuses.
# ---------------------------------------------------------------------------


def test_explicit_path_force_overwrites_brief_only_state(intake_app: typer.Typer, tmp_path: Path) -> None:
    """--force still overwrites when only the brief (no sidecar) exists."""
    _seed_brief_without_sidecar(tmp_path)
    plan = _make_plan_file(tmp_path, content="# Updated via force")

    with patched_intake_command_environment(tmp_path, patch_cwd=False):
        result = runner.invoke(intake_app, [str(plan), "--force"], catch_exceptions=False)

    assert result.exit_code == 0, f"output: {result.output}"
    new_content = (tmp_path / ".kittify" / MISSION_BRIEF_FILENAME).read_text(encoding="utf-8")
    assert "Updated via force" in new_content
    assert (tmp_path / ".kittify" / BRIEF_SOURCE_FILENAME).exists()


def test_auto_force_overwrites_brief_only_state(intake_app: typer.Typer, tmp_path: Path) -> None:
    """--auto --force still overwrites when only the brief (no sidecar) exists."""
    _seed_brief_without_sidecar(tmp_path)
    _make_plan_file(tmp_path, "opencode-plan.md", content="# Auto updated via force")
    mock_sources = [("opencode", "opencode", ["opencode-plan.md"])]

    with patched_intake_command_environment(tmp_path, mock_sources):
        result = runner.invoke(intake_app, ["--auto", "--force"], catch_exceptions=False)

    assert result.exit_code == 0, f"output: {result.output}"
    new_content = (tmp_path / ".kittify" / MISSION_BRIEF_FILENAME).read_text(encoding="utf-8")
    assert "Auto updated via force" in new_content
    assert (tmp_path / ".kittify" / BRIEF_SOURCE_FILENAME).exists()


def test_explicit_path_refuses_when_both_brief_and_sidecar_present(intake_app: typer.Typer, tmp_path: Path) -> None:
    """Both-present already refuses without --force (green-on-base anchor)."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    brief_path = kittify / MISSION_BRIEF_FILENAME
    brief_path.write_text(HAND_AUTHORED_BRIEF, encoding="utf-8")
    (kittify / BRIEF_SOURCE_FILENAME).write_text("source: manual\n", encoding="utf-8")
    plan = _make_plan_file(tmp_path)

    with patched_intake_command_environment(tmp_path, patch_cwd=False):
        result = runner.invoke(intake_app, [str(plan)], catch_exceptions=False)

    assert result.exit_code != 0, f"output: {result.output}"
    assert "Use --force" in result.output, f"output: {result.output}"
    assert brief_path.read_text(encoding="utf-8") == HAND_AUTHORED_BRIEF
