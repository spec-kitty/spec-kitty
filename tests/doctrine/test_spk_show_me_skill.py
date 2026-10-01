"""Contract pins for the compact visual-communication skill."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.tasks import app as status_app
from specify_cli.skills.installer import install_skills_for_agent
from specify_cli.skills.registry import SkillRegistry
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event
from tests.mocked_env import setup_mocked_env


pytestmark = [pytest.mark.doctrine, pytest.mark.fast]
REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = REPO_ROOT / "src" / "charter" / "offering" / "skills"
SKILL = SKILLS_ROOT / "spk-doctrine-show-me" / "SKILL.md"


@pytest.fixture(scope="module")
def skill_text() -> str:
    return SKILL.read_text(encoding="utf-8")


def test_skill_attributes_humanlayer_source_and_carries_mit_notice(
    skill_text: str,
) -> None:
    notice = SKILL.parent / "references" / "humanlayer-origin-and-license.md"

    assert "Dexter Horthy" in skill_text
    assert "HumanLayer" in skill_text
    assert "https://github.com/humanlayer/skills" in skill_text
    assert notice.is_file()
    notice_text = notice.read_text(encoding="utf-8")
    assert "MIT License" in notice_text
    assert "Copyright (c) 2026 HumanLayer" in notice_text
    assert "The above copyright notice and this permission notice" in notice_text


def test_skill_builds_on_canonical_diagram_doctrine(skill_text: str) -> None:
    sources = (SKILL.parent / "references" / "spec-kitty-diagram-sources.md").read_text(
        encoding="utf-8"
    )
    assert "spec-kitty charter" in skill_text
    assert "context --include" in skill_text
    assert "toolguide:mermaid-diagramming" in sources
    assert "toolguide:plantuml-diagramming" in sources
    assert "directive:USE_C4_MODEL_TECHNIQUES" in sources
    assert "tactic:architecture-diagram-review-checklist" in sources
    assert "--action <action> --mission-type <type> --json" in sources
    assert "inclusion alone does not" in sources
    assert "packs/built-in/toolguides/MERMAID_DIAGRAMMING.md" in sources
    assert "packs/built-in/toolguides/PLANTUML_DIAGRAMMING.md" in sources


def test_skill_pins_status_tui_rendering_contract(skill_text: str) -> None:
    lifecycle = " → ".join(
        lane.value
        for lane in (
            Lane.PLANNED,
            Lane.CLAIMED,
            Lane.IN_PROGRESS,
            Lane.FOR_REVIEW,
            Lane.IN_REVIEW,
            Lane.APPROVED,
            Lane.DONE,
        )
    )
    renderer = (
        REPO_ROOT / "src/specify_cli/cli/commands/agent/tasks_status_cmd.py"
    ).read_text(encoding="utf-8")

    assert "spec-kitty agent tasks status --json" in skill_text
    assert lifecycle in skill_text
    for heading in (
        "📋 Planned",
        "🔄 Doing",
        "👀 For Review",
        "👍 Approved",
        "✅ Done",
    ):
        assert f'table.add_column("{heading}"' in renderer
        assert heading.split(maxsplit=1)[1] in skill_text
    assert "Lane.CLAIMED" in renderer and "Lane.IN_REVIEW" in renderer
    assert "work_packages[].lane" in skill_text
    assert "JSON has no `next_action`" in skill_text
    assert "Done progress" in skill_text
    assert "Weighted readiness" in skill_text


def test_skill_documented_status_json_keys_match_live_emitter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, skill_text: str
) -> None:
    """Live-invoke ``spec-kitty agent tasks status --json`` and pin the
    documented JSON keys to what ``_st_emit_json`` actually constructs.

    The skill (lines ~61-68) tells a TUI consumer to read top-level
    ``done_count``, ``total_wps``, ``progress_percentage``, ``stalled_wps``,
    ``stale_verdicts``, ``mission_slug``, and per-WP ``work_packages[].lane``
    / ``work_packages[].is_stale``. Nothing previously coupled those literal
    names to the emitter's real output, so a future key rename there would
    let the skill silently document a JSON shape that no longer exists. This
    builds a small fixture mission (same shape as
    ``tests/specify_cli/cli/commands/agent/test_tasks_status_progress.py``),
    runs the real CLI ``--json`` path, and asserts the documented keys are
    present in the actual payload -- not merely re-grepped from the prose.
    """
    mission_slug = "show-me-json-contract"
    (tmp_path / ".kittify").mkdir()
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": mission_slug,
                "mission_number": "042",
                "mission_type": "software-dev",
            }
        ),
        encoding="utf-8",
    )

    lanes = {"WP01": "approved", "WP02": "in_progress"}
    for wp_id, lane in lanes.items():
        (tasks_dir / f"{wp_id}-test.md").write_text(
            textwrap.dedent(
                f"""\
                ---
                work_package_id: {wp_id}
                title: Test {wp_id}
                execution_mode: code_change
                ---
                # {wp_id}
                """
            ),
            encoding="utf-8",
        )
        append_event(
            feature_dir,
            StatusEvent(
                event_id=f"test-{wp_id}-{lane}",
                mission_slug=mission_slug,
                wp_id=wp_id,
                from_lane=Lane.PLANNED,
                to_lane=Lane(lane),
                at="2026-01-01T00:00:00+00:00",
                actor="test",
                force=True,
                execution_mode="worktree",
            ),
        )

    workspace = SimpleNamespace(execution_mode="code_change", resolution_kind="lane_workspace")
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    with setup_mocked_env(tmp_path, workspace_resolution=workspace):
        result = runner.invoke(status_app, ["status", "--mission", mission_slug, "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)

    documented_top_level_keys = (
        "done_count",
        "total_wps",
        "progress_percentage",
        "stalled_wps",
        "stale_verdicts",
        "mission_slug",
    )
    for documented_key in documented_top_level_keys:
        assert documented_key in skill_text, (
            f"expected SKILL.md to still document {documented_key!r}"
        )
        assert documented_key in payload, (
            f"SKILL.md documents top-level status-JSON key {documented_key!r}, "
            "but the live `_st_emit_json` payload does not contain it -- the "
            "skill's documented contract has drifted from the real emitter"
        )

    work_packages = payload["work_packages"]
    assert work_packages, "fixture must produce at least one WP row"
    assert "work_packages[].lane" in skill_text
    for wp in work_packages:
        assert "lane" in wp, (
            "SKILL.md documents `work_packages[].lane`, but a live WP row "
            "is missing the `lane` key"
        )

    in_progress_wp = next(wp for wp in work_packages if wp["id"] == "WP02")
    assert "work_packages[].is_stale" in skill_text
    assert "is_stale" in in_progress_wp, (
        "SKILL.md documents `work_packages[].is_stale`, but the live "
        "in-progress WP row is missing the `is_stale` key"
    )


def test_installed_skill_carries_portable_sources_and_themes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    project = tmp_path / "project"
    project.mkdir()
    skill = SkillRegistry.from_local_repo(REPO_ROOT).get_skill("spk-doctrine-show-me")
    assert skill is not None

    install_skills_for_agent(project, "codex", [skill])

    installed = project / ".agents" / "skills" / "spk-doctrine-show-me"
    assert (installed / "references" / "spec-kitty-diagram-sources.md").is_file()
    assert (installed / "assets" / "MERMAID_DIAGRAMMING.md").is_file()
    assert (installed / "assets" / "PLANTUML_DIAGRAMMING.md").is_file()
    assert (installed / "assets" / "mermaid-theme-common-template.md").is_file()
    assert (
        installed / "assets" / "mermaid-theme-bluegray-conversation-template.md"
    ).is_file()


@pytest.mark.parametrize(
    "filename",
    [
        "mermaid-theme-common-template.md",
        "mermaid-theme-bluegray-conversation-template.md",
    ],
)
def test_bundled_theme_matches_canonical_template(filename: str) -> None:
    bundled = SKILL.parent / "assets" / filename
    canonical = REPO_ROOT / "src" / "charter" / "offering" / "templates" / "diagrams" / "themes" / filename
    assert bundled.read_bytes() == canonical.read_bytes()


@pytest.mark.parametrize(
    "filename",
    ["MERMAID_DIAGRAMMING.md", "PLANTUML_DIAGRAMMING.md"],
)
def test_bundled_guide_matches_canonical_toolguide(filename: str) -> None:
    bundled = SKILL.parent / "assets" / filename
    canonical = REPO_ROOT / "packs" / "built-in" / "toolguides" / filename
    assert bundled.read_bytes() == canonical.read_bytes()


@pytest.mark.parametrize(
    "relative_path",
    [
        "src/charter/offering/skills/spec-kitty/SKILL.md",
        "src/charter/offering/skills/spk-mission-specify/SKILL.md",
        "src/charter/offering/skills/spk-mission-plan/SKILL.md",
        "packs/built-in/missions/mission-steps/software-dev/specify/prompt.md",
        "packs/built-in/missions/mission-steps/software-dev/plan/prompt.md",
        "packs/built-in/missions/mission-steps/plan/specify/prompt.md",
        "packs/built-in/missions/mission-steps/plan/plan/prompt.md",
    ],
)
def test_primary_surfaces_recommend_the_skill(relative_path: str) -> None:
    text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
    assert "spk-doctrine-show-me" in text


@pytest.mark.parametrize(
    "relative_path",
    [
        "tests/specify_cli/regression/_twelve_agent_baseline/claude/specify.md",
        "tests/specify_cli/regression/_twelve_agent_baseline/gemini/specify.toml",
    ],
)
def test_rendered_specify_command_preserves_exact_skill_name(relative_path: str) -> None:
    text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
    assert "`spk-doctrine-show-me`" in text
