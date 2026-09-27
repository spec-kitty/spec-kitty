"""#5160 friction 3: `spec-kitty agent context resolve --action tasks` must report
the SAME primary-anchored `feature_dir` as `check-prerequisites`.

The command routed the reported `feature_dir` through the coord-aware read
resolver, so on a materialized coord-topology mission a planning action (`tasks`,
`plan`, `specify`) reported the coordination worktree while `check-prerequisites`
(and `finalize-tasks`) anchored to primary. An agent authoring tasks at the
reported dir would then write to coord while finalize reads an empty primary
`tasks/`. Planning actions must primary-anchor (matching #2017/#2101); the
shared coord-husk resolver used by status/move-task stays unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.context import app as context_app

from tests.integration.coord_topology_fixture import _build_coord_topology

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()


def _resolve(repo: Path, monkeypatch: pytest.MonkeyPatch, *, action: str, slug: str) -> dict:
    monkeypatch.chdir(repo)
    result = runner.invoke(
        context_app,
        ["--action", action, "--mission", slug, "--json"],
    )
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


@pytest.mark.parametrize("action", ["tasks", "plan", "specify", "tasks_finalize"])
def test_planning_actions_report_primary_feature_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, action: str) -> None:
    ctx = _build_coord_topology(tmp_path, write_husk_meta=False)

    payload = _resolve(ctx.repo, monkeypatch, action=action, slug=ctx.slug)

    assert Path(payload["feature_dir"]) == ctx.primary_feature_dir
    assert Path(payload["feature_dir"]) != ctx.coord_feature_dir


def test_status_action_keeps_coord_read_surface(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: a status-reading action still resolves the coord surface — the
    primary anchor is scoped to planning/authoring actions only, so the shared
    coord-husk resolver (move-task / FR-010 guards) is unaffected."""
    ctx = _build_coord_topology(tmp_path, write_husk_meta=False)

    payload = _resolve(ctx.repo, monkeypatch, action="status", slug=ctx.slug)

    assert Path(payload["feature_dir"]) == ctx.coord_feature_dir
