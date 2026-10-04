"""Pack-skill doctor health dimension (FR-015)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands._doctrine_collect import _collect_pack_skill_health, _parse_skipped_pack_skill_warning
from specify_cli.cli.commands._doctrine_health import DoctrineHealthReport, PackHealth, PackSkillHealth, SkippedPackSkill
from specify_cli.cli.commands.doctor import app as doctor_app

from .conftest import prompt_skill, write_skill

pytestmark = [pytest.mark.unit, pytest.mark.fast]

runner = CliRunner()


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    (root / ".kittify").mkdir(parents=True)
    (root / ".kittify" / "config.yaml").write_text("agents:\n  available:\n    - claude\n", encoding="utf-8")
    return root


def _project_skills(root: Path) -> Path:
    return root / ".kittify" / "doctrine" / "skills"


def test_model_health_flags() -> None:
    assert PackSkillHealth(skill_count=0).healthy is True
    unhealthy = PackSkillHealth(skill_count=1, invalid_skills=[SkippedPackSkill("org", "x.skill.yaml", "boom")])
    assert unhealthy.healthy is False
    assert unhealthy.to_dict() == {
        "skill_count": 1,
        "loaded": 1,
        "skipped": 1,
        "healthy": False,
        "invalid_skills": [{"layer": "org", "path": "x.skill.yaml", "error_summary": "boom"}],
    }


def test_report_folds_skill_health_into_aggregate() -> None:
    pack = PackHealth(pack_id="builtin", layer="builtin", discovered_count=1, valid_count=1)
    assert DoctrineHealthReport(packs=[pack]).healthy is True
    bad = PackSkillHealth(skill_count=0, invalid_skills=[SkippedPackSkill("org", "x", "y")])
    report = DoctrineHealthReport(packs=[pack], skills=bad)
    assert report.healthy is False
    assert report.to_dict()["skills"]["healthy"] is False


def test_parse_warning_shapes() -> None:
    parsed = _parse_skipped_pack_skill_warning("Skipping invalid org pack-skill a.skill.yaml: nope")
    assert (parsed.layer, parsed.path, parsed.error_summary) == ("org", "a.skill.yaml", "nope")
    fallback = _parse_skipped_pack_skill_warning("something else")
    assert (fallback.layer, fallback.path, fallback.error_summary) == ("unknown", "unknown", "something else")


def test_collect_reports_loaded_and_healthy(repo_root: Path) -> None:
    write_skill(_project_skills(repo_root), prompt_skill("land-pr"))
    health = _collect_pack_skill_health(repo_root)
    assert health.healthy is True
    assert health.skill_count == 1
    assert health.invalid_skills == []


def test_collect_reports_malformed_skill_as_skipped(repo_root: Path) -> None:
    write_skill(_project_skills(repo_root), prompt_skill("land-pr"))
    write_skill(_project_skills(repo_root), prompt_skill("spk-bad"))
    health = _collect_pack_skill_health(repo_root)
    assert health.healthy is False
    assert health.skill_count == 1
    assert len(health.invalid_skills) == 1
    assert health.invalid_skills[0].layer == "project"
    assert health.invalid_skills[0].path == "spk-bad.skill.yaml"


def test_collect_degrades_on_hard_load_failure(repo_root: Path) -> None:
    with patch(
        "charter.activation.doctrine_service_builder.build_activation_aware_doctrine_service",
        side_effect=RuntimeError("boom"),
    ):
        health = _collect_pack_skill_health(repo_root)
    assert health.healthy is False
    assert health.invalid_skills[0].error_summary == "pack-skill health load error: boom"


def _doctor_json(root: Path) -> tuple[int, dict[str, Any]]:
    with patch("specify_cli.cli.commands.doctor.locate_project_root", return_value=root):
        result = runner.invoke(doctor_app, ["doctrine", "--json"])
    return result.exit_code, json.loads(result.output)


def test_doctor_json_has_skill_health_key(repo_root: Path) -> None:
    exit_code, payload = _doctor_json(repo_root)
    skills = payload["profile_health"]["skills"]
    assert skills["healthy"] is True
    assert skills["skill_count"] == 0
    assert exit_code == 0


def test_doctor_json_unhealthy_when_malformed_skill_skipped(repo_root: Path) -> None:
    write_skill(_project_skills(repo_root), prompt_skill("land-pr", body_path="missing.md"), body=None)
    exit_code, payload = _doctor_json(repo_root)
    health = payload["profile_health"]
    assert health["skills"]["healthy"] is False
    assert health["skills"]["invalid_skills"][0]["path"] == "land-pr.skill.yaml"
    assert health["healthy"] is False
    assert exit_code == 1
