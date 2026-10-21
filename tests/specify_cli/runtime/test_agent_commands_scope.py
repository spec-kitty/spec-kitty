"""WP06 (#6470, #3048 context): the home-folder command writer is scoped and cleans up.

* Startup (``ensure_global_agent_commands()`` with no keys) writes only the
  slash-command agents configured in the project at the working directory,
  and none outside a project; an empty key list never means "all".
* The schema-2 freshness stamp records healthy keys, so a scoped call
  short-circuits with no ``AssetPreparation``; a schema-1 stamp forces one
  build.
* Every build removes Spec Kitty's own ``spec-kitty.*.md`` files from the
  retired ``~/.agent/workflows`` (inventory proof, or current-version marker
  plus byte equality with the frozen render), never other files, never the
  folder, never through a symlink.
* ``agent config add <slash agent>`` writes that agent's global commands.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

import specify_cli.runtime.agent_commands as ac
from specify_cli.core import config as core_config
from specify_cli.runtime.asset_preparation import AssetPreparation

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_WORKFLOWS = Path(".agent") / "workflows"


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[Path, Path, Path]]:
    """Isolated HOME / SPEC_KITTY_HOME, a fake template tree, CWD outside any project."""
    home = tmp_path / "home"
    kittify_home = tmp_path / "kittify"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(kittify_home))
    for name in ("OPENCODE_CONFIG_DIR", "XDG_CONFIG_HOME", "LLXPRT_CONFIG_HOME", "SPECIFY_REPO_ROOT"):
        monkeypatch.delenv(name, raising=False)
    templates = tmp_path / "templates"
    from specify_cli.shims.registry import PROMPT_DRIVEN_COMMANDS

    for command in PROMPT_DRIVEN_COMMANDS:
        (templates / command).mkdir(parents=True)
        (templates / command / "prompt.md").write_text(f"---\ndescription: {command}\n---\n# {command}\nRun __AGENT__ with $ARGUMENTS\n", encoding="utf-8")
    monkeypatch.setattr(ac, "_get_command_templates_dir", lambda: templates)
    outside = tmp_path / "outside"
    outside.mkdir()
    with contextlib.chdir(outside):
        yield home, kittify_home, tmp_path


def _project(root: Path, agents: list[str]) -> Path:
    (root / ".kittify").mkdir(parents=True)
    lines = ["agents:", "  available:", *(f"    - {agent}" for agent in agents)] if agents else ["agents:", "  available: []"]
    (root / ".kittify" / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return root


def _count_preparations(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    calls = {"n": 0}
    original = AssetPreparation.__init__

    def _counting(self: AssetPreparation, *args: object, **kwargs: object) -> None:
        calls["n"] += 1
        original(self, *args, **kwargs)  # type: ignore[arg-type]  # forwarding the real signature

    monkeypatch.setattr(AssetPreparation, "__init__", _counting)
    return calls


def _stamp(kittify_home: Path) -> dict[str, object]:
    payload: dict[str, object] = json.loads((kittify_home / "cache" / ac._FRESHNESS_STAMP_FILENAME).read_text(encoding="utf-8"))
    return payload


def _write_old_antigravity_workflows(monkeypatch: pytest.MonkeyPatch) -> Path:
    """Reproduce the pre-WP05 writer: antigravity with its slash-command row."""
    with monkeypatch.context() as patched:
        patched.setitem(core_config.AGENT_COMMAND_CONFIG, "antigravity", dict(ac._RETIRED_ANTIGRAVITY_ROW))
        ac.ensure_global_agent_commands(agent_keys=["antigravity"])
    workflows = Path.home() / _WORKFLOWS
    assert sorted(workflows.glob("spec-kitty.*.md")), "fixture: the old writer must have written workflow files"
    return workflows


def _drop_inventory_entries(kittify_home: Path, prefix: str) -> None:
    inventory = kittify_home / "cache" / "slash_commands-assets.json"
    payload = json.loads(inventory.read_text(encoding="utf-8"))
    payload["entries"] = {key: value for key, value in payload["entries"].items() if prefix not in key}
    inventory.write_text(json.dumps(payload), encoding="utf-8")


def _force_rebuild(kittify_home: Path) -> None:
    (kittify_home / "cache" / ac._FRESHNESS_STAMP_FILENAME).unlink()


# ---------------------------------------------------------------------------
# T022: startup scope
# ---------------------------------------------------------------------------


def test_project_configured_for_claude_writes_only_claude(env: tuple[Path, Path, Path]) -> None:
    home, _kittify_home, tmp_path = env
    project = _project(tmp_path / "project", ["claude", "codex"])
    with contextlib.chdir(project):
        ac.ensure_global_agent_commands()
    assert sorted(p.name for p in home.iterdir()) == [".claude"]
    assert sorted((home / ".claude" / "commands").glob("spec-kitty.*.md"))


def test_outside_a_project_nothing_is_written(env: tuple[Path, Path, Path]) -> None:
    home, kittify_home, _tmp_path = env
    ac.ensure_global_agent_commands()
    assert list(home.iterdir()) == []
    assert _stamp(kittify_home)["healthy_keys"] == []


def test_project_without_config_or_with_unreadable_config_writes_nothing(env: tuple[Path, Path, Path]) -> None:
    home, _kittify_home, tmp_path = env
    bare = tmp_path / "bare"
    (bare / ".kittify").mkdir(parents=True)
    with contextlib.chdir(bare):
        assert ac._project_slash_agent_scope() == []
    broken = _project(tmp_path / "broken", [])
    (broken / ".kittify" / "config.yaml").write_text("agents:\n  available:\n    - not-an-agent\n", encoding="utf-8")
    with contextlib.chdir(broken):
        assert ac._project_slash_agent_scope() == []
        ac.ensure_global_agent_commands()
    assert list(home.iterdir()) == []


def test_skill_only_project_scope_is_empty(env: tuple[Path, Path, Path]) -> None:
    _home, _kittify_home, tmp_path = env
    project = _project(tmp_path / "project", ["codex", "antigravity"])
    with contextlib.chdir(project):
        assert ac._project_slash_agent_scope() == []


def test_empty_key_list_is_none_not_all(env: tuple[Path, Path, Path]) -> None:
    home, _kittify_home, _tmp_path = env
    assessment = ac.assess_global_agent_commands(agent_keys=[])
    assert assessment.complete
    assert not [effect for effect in assessment.effects if str(home) in str(effect.destination)]
    ac.ensure_global_agent_commands(agent_keys=[])
    assert list(home.iterdir()) == []


# ---------------------------------------------------------------------------
# T023: per-key freshness stamp
# ---------------------------------------------------------------------------


def test_scoped_stamp_short_circuits_second_call(env: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    _home, kittify_home, _tmp_path = env
    ac.ensure_global_agent_commands(agent_keys=["claude"])
    stamp = _stamp(kittify_home)
    assert stamp["schema"] == ac._FRESHNESS_SCHEMA
    assert stamp["healthy_keys"] == ["claude"]
    assert stamp["retired_surfaces_cleaned"] is True

    calls = _count_preparations(monkeypatch)
    ac.ensure_global_agent_commands(agent_keys=["claude"])
    assert calls["n"] == 0, "a fresh scoped stamp must short-circuit without AssetPreparation (SK-243)"


def test_scoped_call_for_a_new_key_builds_and_unions(env: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    _home, kittify_home, _tmp_path = env
    ac.ensure_global_agent_commands(agent_keys=["claude"])
    calls = _count_preparations(monkeypatch)
    ac.ensure_global_agent_commands(agent_keys=["cursor"])
    assert calls["n"] > 0, "a key not in healthy_keys must build"
    assert _stamp(kittify_home)["healthy_keys"] == ["claude", "cursor"]


def test_version_change_replaces_prior_healthy_keys(env: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    _home, kittify_home, _tmp_path = env
    ac.ensure_global_agent_commands(agent_keys=["claude"])
    monkeypatch.setattr(ac, "_get_cli_version", lambda: "99.0.0-wp06")
    ac.ensure_global_agent_commands(agent_keys=["cursor"])
    assert _stamp(kittify_home)["healthy_keys"] == ["cursor"]


def test_unhealthy_requested_key_forces_build(env: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    home, _kittify_home, _tmp_path = env
    ac.ensure_global_agent_commands(agent_keys=["claude"])
    target = next((home / ".claude" / "commands").glob("spec-kitty.*.md"))
    target.chmod(0o644)
    target.unlink()
    calls = _count_preparations(monkeypatch)
    ac.ensure_global_agent_commands(agent_keys=["claude"])
    assert calls["n"] > 0
    assert target.exists()


def test_schema_one_stamp_forces_one_build(env: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    _home, kittify_home, _tmp_path = env
    ac.ensure_global_agent_commands(agent_keys=["claude"])
    stamp_path = kittify_home / "cache" / ac._FRESHNESS_STAMP_FILENAME
    current = _stamp(kittify_home)
    stamp_path.write_text(
        json.dumps({"cli_version": current["cli_version"], "template_source_signature": current["template_source_signature"], "agent_keys": ["claude"]}),
        encoding="utf-8",
    )
    assert ac._read_freshness_stamp(stamp_path) is None
    calls = _count_preparations(monkeypatch)
    ac.ensure_global_agent_commands(agent_keys=["claude"])
    assert calls["n"] > 0, "a schema-1 stamp must force a build"
    assert _stamp(kittify_home)["schema"] == ac._FRESHNESS_SCHEMA
    calls["n"] = 0
    ac.ensure_global_agent_commands(agent_keys=["claude"])
    assert calls["n"] == 0, "the rebuild writes a schema-2 stamp, so the next call is warm"


def test_unopted_scoped_assess_always_builds(env: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    """The tool-surface provider rechecks the returned assessment, so it must carry a build."""
    ac.ensure_global_agent_commands(agent_keys=["claude"])
    calls = _count_preparations(monkeypatch)
    assessment = ac.assess_global_agent_commands(agent_keys=["claude"])
    assert calls["n"] > 0
    assert assessment.complete and not assessment.effects


# ---------------------------------------------------------------------------
# T024: ~/.agent/workflows cleanup
# ---------------------------------------------------------------------------


def test_frozen_render_matches_the_old_writer_bytes(env: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    _home, _kittify_home, tmp_path = env
    templates = tmp_path / "templates"
    monkeypatch.setitem(core_config.AGENT_COMMAND_CONFIG, "antigravity", dict(ac._RETIRED_ANTIGRAVITY_ROW))
    old = dict(ac._render_agent_commands("antigravity", templates, "sh"))
    monkeypatch.delitem(core_config.AGENT_COMMAND_CONFIG, "antigravity")
    for name, content in old.items():
        command = name.removeprefix("spec-kitty.").removesuffix(".md")
        assert ac._retired_antigravity_command_bytes(command, templates, "sh") == content, name
    assert ac._retired_antigravity_command_bytes("not-a-command", templates, "sh") is None


def test_upgrade_check_reinsertion_leaves_marker_less_text_alone() -> None:
    assert ac._with_agent_upgrade_check("no marker here\n") == "no marker here\n"


def test_inventory_owned_workflow_files_are_removed_user_files_kept(env: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    _home, kittify_home, _tmp_path = env
    workflows = _write_old_antigravity_workflows(monkeypatch)
    (workflows / "my-flow.md").write_text("mine\n", encoding="utf-8")
    (workflows / "spec-kitty.custom.md").write_text("my own spec-kitty-named flow\n", encoding="utf-8")
    edited = workflows / "spec-kitty.plan.md"
    edited.chmod(0o644)
    edited.write_text(edited.read_text(encoding="utf-8") + "\nmy edit\n", encoding="utf-8")
    _force_rebuild(kittify_home)

    ac.ensure_global_agent_commands(agent_keys=["claude"])

    assert workflows.is_dir(), "the folder itself is never removed"
    assert sorted(p.name for p in workflows.iterdir()) == ["my-flow.md", "spec-kitty.custom.md", "spec-kitty.plan.md"]


def test_startup_removes_old_writer_files_and_keeps_user_file(env: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    """The acceptance scenario: a schema-1 install upgraded to this version, then any CLI command."""
    _home, kittify_home, tmp_path = env
    workflows = _write_old_antigravity_workflows(monkeypatch)
    (workflows / "notes.md").write_text("user file\n", encoding="utf-8")
    stamp_path = kittify_home / "cache" / ac._FRESHNESS_STAMP_FILENAME
    stamp_path.write_text(json.dumps({"cli_version": "x", "template_source_signature": "y", "agent_keys": ["antigravity"]}), encoding="utf-8")
    project = _project(tmp_path / "project", ["claude"])
    with contextlib.chdir(project):
        ac.ensure_global_agent_commands()
    assert sorted(p.name for p in workflows.iterdir()) == ["notes.md"]


def test_pre_inventory_file_removed_only_on_current_marker_and_bytes(env: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    _home, kittify_home, _tmp_path = env
    workflows = _write_old_antigravity_workflows(monkeypatch)
    _drop_inventory_entries(kittify_home, ".agent/workflows/")
    # current marker, edited body: kept
    edited = workflows / "spec-kitty.plan.md"
    edited.chmod(0o644)
    edited.write_text(edited.read_text(encoding="utf-8") + "edited\n", encoding="utf-8")
    # canonical body under a DIFFERENT version marker: kept (R-M5, never the predecessor branch)
    other_version = workflows / "spec-kitty.specify.md"
    other_version.chmod(0o644)
    current_marker = f"<!-- spec-kitty-command-version: {ac._get_cli_version()} -->"
    other_version.write_text(other_version.read_text(encoding="utf-8").replace(current_marker, "<!-- spec-kitty-command-version: 0.0.1 -->"), encoding="utf-8")
    # current marker, but not a current command name: kept (no render can prove it)
    (workflows / "spec-kitty.retired-cmd.md").write_text(f"{current_marker}\nold command\n", encoding="utf-8")
    # no marker at all: kept
    (workflows / "spec-kitty.review.md").chmod(0o644)
    (workflows / "spec-kitty.review.md").write_text("no marker\n", encoding="utf-8")
    _force_rebuild(kittify_home)

    ac.ensure_global_agent_commands(agent_keys=["claude"])

    assert sorted(p.name for p in workflows.iterdir()) == ["spec-kitty.plan.md", "spec-kitty.retired-cmd.md", "spec-kitty.review.md", "spec-kitty.specify.md"]


def test_symlinked_workflows_folder_is_refused(env: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    home, kittify_home, tmp_path = env
    workflows = _write_old_antigravity_workflows(monkeypatch)
    elsewhere = tmp_path / "elsewhere"
    workflows.rename(elsewhere)
    workflows.symlink_to(elsewhere, target_is_directory=True)
    before = sorted(p.name for p in elsewhere.iterdir())
    _force_rebuild(kittify_home)

    ac.ensure_global_agent_commands(agent_keys=["claude"])

    assert workflows.is_symlink()
    assert sorted(p.name for p in elsewhere.iterdir()) == before
    # a symlinked ~/.agent is refused the same way
    workflows.unlink()
    (home / ".agent").rmdir()
    agent_elsewhere = tmp_path / "agent-elsewhere"
    (agent_elsewhere / "workflows").mkdir(parents=True)
    (home / ".agent").symlink_to(agent_elsewhere, target_is_directory=True)
    assert not ac._is_real_directory_below_home(Path.home() / _WORKFLOWS)


def test_warm_run_never_lists_the_workflows_folder(env: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    _home, kittify_home, _tmp_path = env
    workflows = _write_old_antigravity_workflows(monkeypatch)
    _force_rebuild(kittify_home)
    ac.ensure_global_agent_commands(agent_keys=["claude"])  # cold: cleans

    listed: list[Path] = []
    original = Path.iterdir

    def _recording(self: Path) -> Iterator[Path]:
        listed.append(self)
        return original(self)

    monkeypatch.setattr(Path, "iterdir", _recording)
    ac.ensure_global_agent_commands(agent_keys=["claude"])  # warm
    assert workflows not in listed


def test_cleanup_preserves_are_not_reported_as_unmigrated(env: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    _home, kittify_home, _tmp_path = env
    workflows = _write_old_antigravity_workflows(monkeypatch)
    edited = workflows / "spec-kitty.plan.md"
    edited.chmod(0o644)
    edited.write_text("edited\n", encoding="utf-8")
    _force_rebuild(kittify_home)
    with caplog.at_level("WARNING", logger=ac.logger.name):
        ac.ensure_global_agent_commands(agent_keys=["claude"])
    assert not [record for record in caplog.records if "could not migrate" in record.getMessage()]


# ---------------------------------------------------------------------------
# agent config add triggers the agent's global write
# ---------------------------------------------------------------------------


def test_agent_config_add_writes_the_added_agents_global_commands(env: tuple[Path, Path, Path]) -> None:
    from specify_cli.cli.commands.agent.config import app

    home, _kittify_home, tmp_path = env
    project = _project(tmp_path / "project", ["claude"])
    with patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=project):
        result = CliRunner().invoke(app, ["add", "cursor", "codex"])
    assert result.exit_code == 0, result.output
    assert sorted((home / ".cursor" / "commands").glob("spec-kitty.*.md"))
    assert not (home / ".claude").exists(), "only the added slash agent is written"


def test_agent_config_add_reports_a_global_write_failure(env: tuple[Path, Path, Path]) -> None:
    from specify_cli.cli.commands.agent.config import app

    _home, _kittify_home, tmp_path = env
    project = _project(tmp_path / "project", [])
    with (
        patch("specify_cli.cli.commands.agent.config.find_repo_root", return_value=project),
        patch("specify_cli.runtime.agent_commands.ensure_global_agent_commands", side_effect=RuntimeError("boom")),
    ):
        result = CliRunner().invoke(app, ["add", "cursor"])
    assert result.exit_code == 0, result.output
    assert "could not write global commands for cursor" in result.output
