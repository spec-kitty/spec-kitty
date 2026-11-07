"""``agent tasks status`` defaults ``--mission`` to the sole active mission (#4677).

Issue-pinned reproduction: the command's own first help example (a bare
``spec-kitty agent tasks status``) exited 1 with ``--mission <slug> is
required`` in a project holding exactly one mission. Maintainer decision on
the issue: when exactly one *active* (not completed / canceled) mission exists,
it is the default; zero or several keep the error.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.tasks import app

pytestmark = [pytest.mark.regression, pytest.mark.git_repo]

_REQUIRED = "--mission <slug> is required"


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify/config.yaml").write_text("{}\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _make_mission(project: Path, slug: str, *, merged: bool = False) -> None:
    mission = project / "kitty-specs" / slug
    (mission / "tasks").mkdir(parents=True)
    # #5875 (7634075bd5): a ``kitty-specs/`` child is a selectable Mission only when its meta.json carries a
    # non-empty ``mission_id`` (or git tracks it); without one it is read-side residue and the sole-active default
    # finds no candidate. The id is distinct per slug (built on the slug's mid8) so several Missions stay several.
    meta: dict[str, str] = {
        "mission_id": slug.rsplit("-", 1)[-1].ljust(26, "0"),
        "mission_slug": slug,
        "mission_type": "software-dev",
        "target_branch": "main",
    }
    if merged:
        # ``merged_at`` is the explicit completion marker ``is_mission_completed`` honours.
        meta["merged_at"] = "2026-01-01T00:00:00+00:00"
    (mission / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def test_bare_status_defaults_to_the_only_mission(project: Path) -> None:
    """The help's first example works verbatim when one mission exists."""
    _make_mission(project, "only-mission-01M2GH0R")

    result = CliRunner().invoke(app, ["status", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert "error" not in payload
    assert payload["mission_slug"] == "only-mission-01M2GH0R"


def test_bare_status_skips_completed_missions(project: Path) -> None:
    """A merged mission does not make the project ambiguous."""
    _make_mission(project, "shipped-mission-01M2GH0S", merged=True)
    _make_mission(project, "live-mission-01M2GH0T")

    result = CliRunner().invoke(app, ["status", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["mission_slug"] == "live-mission-01M2GH0T"


def test_bare_status_still_errors_with_several_active_missions(project: Path) -> None:
    _make_mission(project, "alpha-mission-01M2GH0U")
    _make_mission(project, "beta-mission-01M2GH0V")

    result = CliRunner().invoke(app, ["status", "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert _REQUIRED in payload["error"]["message"]


def test_bare_status_still_errors_with_no_active_mission(project: Path) -> None:
    _make_mission(project, "shipped-mission-01M2GH0S", merged=True)

    result = CliRunner().invoke(app, ["status"])

    assert result.exit_code == 1
    assert _REQUIRED in result.output


def test_explicit_mission_still_wins(project: Path) -> None:
    _make_mission(project, "alpha-mission-01M2GH0U")
    _make_mission(project, "beta-mission-01M2GH0V")

    result = CliRunner().invoke(app, ["status", "--mission", "beta-mission-01M2GH0V", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["mission_slug"] == "beta-mission-01M2GH0V"
