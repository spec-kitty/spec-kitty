"""Migration ``4.0.0rc8_retire_antigravity_workflows`` (#6470, FR-010, User Story 3 scenario 2).

Spec Kitty-generated ``.agent/workflows/spec-kitty.<cmd>.md`` files are archived into
``.kittify/backups/antigravity-workflows/`` (operator ruling 2026-10-20: archive, never delete);
foreign, marker-less and symlinked entries stay; a symlinked or escaping ``.agent`` /
``.agent/workflows`` / backup folder is refused.

Fixture bytes: the "prior-release" workflow file is rendered by today's
``render_command_template`` for ``antigravity`` with an explicit old version. That is the
renderer the pre-#6470 project writer called with this agent key (``.agent/workflows`` +
``md`` + ``$ARGUMENTS``); the shape that matters for the proof (the exact marker line within
the first 20 lines) has not changed since the marker was introduced.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from specify_cli.core.agent_config import AgentConfigError
from specify_cli.runtime.agent_commands import _get_command_templates_dir
from specify_cli.skills import command_installer
from specify_cli.skills.command_installer import CANONICAL_COMMANDS, InstallerError
from specify_cli.skills.command_skill_names import command_skill_rel_path
from specify_cli.template.asset_generator import render_command_template
from specify_cli.upgrade.migrations import m_4_0_0rc8_retire_antigravity_workflows as migration_module
from specify_cli.upgrade.migrations.m_4_0_0rc8_retire_antigravity_workflows import (
    ARCHIVE_REL,
    HISTORICAL_COMMANDS,
    WORKFLOWS_REL,
    RetireAntigravityWorkflowsMigration,
    command_of,
    has_marker_line,
    install_refused_warning,
    kept_warning,
    refused_warning,
)

pytestmark = [pytest.mark.unit]

_OLD_VERSION = "3.0.3"
_MARKER = f"<!-- spec-kitty-command-version: {_OLD_VERSION} -->"


def _rendered(command: str = "plan") -> bytes:
    template = _get_command_templates_dir() / command / "prompt.md"
    text = render_command_template(
        template_path=template,
        script_type="sh",
        agent_key="antigravity",
        arg_format="$ARGUMENTS",
        extension="md",
        version=_OLD_VERSION,
    )
    return text.encode("utf-8")


def _project(root: Path, agents: tuple[str, ...] | None = ("antigravity",)) -> Path:
    kittify = root / ".kittify"
    kittify.mkdir(parents=True)
    if agents is not None:
        listed = "".join(f"    - {agent}\n" for agent in agents)
        (kittify / "config.yaml").write_text(f"agents:\n  available:\n{listed}" if agents else "agents:\n  available: []\n", encoding="utf-8")
    return root


def _workflows(project: Path) -> Path:
    path = project / WORKFLOWS_REL
    path.mkdir(parents=True, exist_ok=True)
    return path


def _archived(project: Path) -> dict[str, bytes]:
    root = project / ARCHIVE_REL
    if not root.exists():
        return {}
    return {p.name: p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    return _project(tmp_path / "project")


@pytest.fixture()
def no_install(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Stub the installer so archive cases stay fast; records the agents it was called for."""
    calls: list[str] = []

    def fake_install(repo_root: Path, agent_key: str, *, dry_run: bool = False) -> command_installer.InstallReport:
        calls.append(agent_key)
        return command_installer.InstallReport()

    monkeypatch.setattr(migration_module.command_installer, "install", fake_install)
    return calls


# ---------------------------------------------------------------------------
# Declaration and proof helpers
# ---------------------------------------------------------------------------


def test_declaration() -> None:
    migration = RetireAntigravityWorkflowsMigration()
    assert migration.migration_id == "4.0.0rc8_retire_antigravity_workflows"
    assert migration.target_version == "4.0.0rc8"
    assert migration.clone_local_effect is True
    assert migration.runs_on_worktrees is True
    assert migration.requires_git_repository is False


def test_historical_commands_cover_every_canonical_and_retired_command() -> None:
    assert set(CANONICAL_COMMANDS) <= HISTORICAL_COMMANDS
    assert {"checklist", "clarify", "constitution", "dashboard", "merge", "profile-context"} <= HISTORICAL_COMMANDS


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("spec-kitty.plan.md", "plan"),
        ("spec-kitty.tasks-outline.md", "tasks-outline"),
        ("spec-kitty.clarify.md", "clarify"),
        ("spec-kitty.mine.md", None),
        ("spec-kitty.plan.toml", None),
        ("plan.md", None),
        ("spec-kitty..md", None),
    ],
)
def test_command_of(name: str, expected: str | None) -> None:
    assert command_of(name) == expected


def test_rendered_fixture_carries_the_marker_line() -> None:
    assert _MARKER.encode() in _rendered()


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (f"{_MARKER}\nbody\n", True),
        (f"---\ndescription: x\n---\n{_MARKER}\r\nbody\n", True),
        (f"text {_MARKER} more\n", False),
        (f" {_MARKER}\n", False),
        ("<!-- spec-kitty-command-version:  -->\n", False),
        ("\n" * 20 + f"{_MARKER}\n", False),
        ("", False),
    ],
)
def test_has_marker_line_is_exact_and_bounded(tmp_path: Path, body: str, expected: bool) -> None:
    path = tmp_path / "f.md"
    path.write_text(body, encoding="utf-8")
    assert has_marker_line(path) is expected


def test_has_marker_line_false_for_unreadable(tmp_path: Path) -> None:
    assert has_marker_line(tmp_path / "absent.md") is False


# ---------------------------------------------------------------------------
# detect()
# ---------------------------------------------------------------------------


def test_detect_true_for_a_spec_kitty_workflow(project: Path) -> None:
    (_workflows(project) / "spec-kitty.plan.md").write_bytes(_rendered())
    assert RetireAntigravityWorkflowsMigration().detect(project) is True


def test_detect_false_without_workflows_dir(project: Path) -> None:
    assert RetireAntigravityWorkflowsMigration().detect(project) is False
    assert not (project / ".agent").exists()


def test_detect_false_when_only_foreign_files(project: Path) -> None:
    (_workflows(project) / "my-flow.md").write_text("mine\n", encoding="utf-8")
    assert RetireAntigravityWorkflowsMigration().detect(project) is False


def test_detect_false_when_antigravity_not_configured(tmp_path: Path) -> None:
    root = _project(tmp_path / "p", agents=("claude",))
    (_workflows(root) / "spec-kitty.plan.md").write_bytes(_rendered())
    assert RetireAntigravityWorkflowsMigration().detect(root) is False


@pytest.mark.parametrize("agents", [None, ()], ids=["no-config", "empty-list"])
def test_detect_true_for_a_legacy_project(tmp_path: Path, agents: tuple[str, ...] | None) -> None:
    root = _project(tmp_path / "p", agents=agents)
    (_workflows(root) / "spec-kitty.plan.md").write_bytes(_rendered())
    assert RetireAntigravityWorkflowsMigration().detect(root) is True


def test_detect_true_for_a_symlinked_workflows_dir(project: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (project / ".agent").mkdir()
    (project / WORKFLOWS_REL).symlink_to(outside, target_is_directory=True)
    assert RetireAntigravityWorkflowsMigration().detect(project) is True


# ---------------------------------------------------------------------------
# apply(): archive
# ---------------------------------------------------------------------------


def test_owned_file_is_archived_and_foreign_file_kept(project: Path, no_install: list[str]) -> None:
    workflows = _workflows(project)
    owned = _rendered()
    (workflows / "spec-kitty.plan.md").write_bytes(owned)
    (workflows / "my-flow.md").write_text("mine\n", encoding="utf-8")

    result = RetireAntigravityWorkflowsMigration().apply(project)

    assert result.success, result.errors
    assert not (workflows / "spec-kitty.plan.md").exists()
    assert (workflows / "my-flow.md").read_text(encoding="utf-8") == "mine\n"
    assert workflows.is_dir()
    assert _archived(project) == {"spec-kitty.plan.md": owned}
    assert result.warnings == []
    assert any(change.startswith(f"Archived {WORKFLOWS_REL}/spec-kitty.plan.md to {ARCHIVE_REL}/") for change in result.changes_made)
    assert no_install == ["antigravity"]


def test_archive_keeps_the_origin_path_under_a_timestamped_folder(project: Path, no_install: list[str]) -> None:
    (_workflows(project) / "spec-kitty.plan.md").write_bytes(_rendered())
    RetireAntigravityWorkflowsMigration().apply(project)
    [archived] = [p for p in (project / ARCHIVE_REL).rglob("*") if p.is_file()]
    rel = archived.relative_to(project / ARCHIVE_REL).as_posix()
    assert rel.startswith(".backup-")
    assert rel.endswith(f"/{WORKFLOWS_REL}/spec-kitty.plan.md")


def test_edited_marked_file_is_archived_with_the_edit(project: Path, no_install: list[str]) -> None:
    edited = _rendered() + b"\nmy local edit\n"
    (_workflows(project) / "spec-kitty.plan.md").write_bytes(edited)

    RetireAntigravityWorkflowsMigration().apply(project)

    assert _archived(project) == {"spec-kitty.plan.md": edited}


def test_retired_command_files_are_archived(project: Path, no_install: list[str]) -> None:
    workflows = _workflows(project)
    for command in ("clarify", "constitution", "dashboard"):
        (workflows / f"spec-kitty.{command}.md").write_text(f"---\n---\n{_MARKER}\nold\n", encoding="utf-8")

    RetireAntigravityWorkflowsMigration().apply(project)

    assert set(_archived(project)) == {"spec-kitty.clarify.md", "spec-kitty.constitution.md", "spec-kitty.dashboard.md"}
    assert list(workflows.iterdir()) == []


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("spec-kitty.plan.md", "no marker here\n"),
        ("spec-kitty.mine.md", f"{_MARKER}\nunknown command\n"),
        ("spec-kitty.plan.md", f"inline {_MARKER}\n"),
    ],
    ids=["marker-less", "unknown-command", "inline-marker"],
)
def test_unproven_spec_kitty_file_is_kept_with_a_warning(project: Path, no_install: list[str], name: str, content: str) -> None:
    path = _workflows(project) / name
    path.write_text(content, encoding="utf-8")

    result = RetireAntigravityWorkflowsMigration().apply(project)

    assert path.read_text(encoding="utf-8") == content
    rel = f"{WORKFLOWS_REL}/{name}"
    assert result.warnings == [kept_warning(rel)]
    assert result.preserved_paths == [rel]
    assert _archived(project) == {}


def test_symlinked_file_is_kept(project: Path, tmp_path: Path, no_install: list[str]) -> None:
    target = tmp_path / "target.md"
    target.write_bytes(_rendered())
    link = _workflows(project) / "spec-kitty.plan.md"
    link.symlink_to(target)

    result = RetireAntigravityWorkflowsMigration().apply(project)

    assert link.is_symlink()
    assert target.read_bytes() == _rendered()
    assert result.warnings == [kept_warning(f"{WORKFLOWS_REL}/spec-kitty.plan.md")]


def test_directory_named_like_a_command_is_kept(project: Path, no_install: list[str]) -> None:
    folder = _workflows(project) / "spec-kitty.plan.md"
    folder.mkdir()
    result = RetireAntigravityWorkflowsMigration().apply(project)
    assert folder.is_dir()
    assert result.preserved_paths == [f"{WORKFLOWS_REL}/spec-kitty.plan.md"]


@pytest.mark.parametrize("which", [".agent", WORKFLOWS_REL])
def test_symlinked_agent_or_workflows_dir_is_refused(project: Path, tmp_path: Path, no_install: list[str], which: str) -> None:
    outside = tmp_path / "outside"
    (outside / "workflows").mkdir(parents=True)
    victim = (outside / "workflows" / "spec-kitty.plan.md") if which == ".agent" else (outside / "spec-kitty.plan.md")
    victim.parent.mkdir(parents=True, exist_ok=True)
    victim.write_bytes(_rendered())
    if which == ".agent":
        (project / ".agent").symlink_to(outside, target_is_directory=True)
    else:
        (project / ".agent").mkdir()
        (project / WORKFLOWS_REL).symlink_to(outside, target_is_directory=True)

    result = RetireAntigravityWorkflowsMigration().apply(project)

    assert victim.read_bytes() == _rendered()
    assert result.warnings == [refused_warning(which, "is a symlink")]
    assert result.changes_made == []
    assert not (project / ARCHIVE_REL).exists()


def test_symlinked_backups_dir_is_refused(project: Path, tmp_path: Path, no_install: list[str]) -> None:
    outside = tmp_path / "backups-elsewhere"
    outside.mkdir()
    (project / ".kittify" / "backups").symlink_to(outside, target_is_directory=True)
    owned = _workflows(project) / "spec-kitty.plan.md"
    owned.write_bytes(_rendered())

    result = RetireAntigravityWorkflowsMigration().apply(project)

    assert owned.exists()
    assert list(outside.iterdir()) == []
    assert result.warnings == [refused_warning(".kittify/backups", "is a symlink")]


def test_relative_symlink_into_the_project_is_still_refused(project: Path, no_install: list[str]) -> None:
    inside = project / "elsewhere"
    inside.mkdir()
    (project / ".agent").mkdir()
    os.symlink(os.path.relpath(inside, project / ".agent"), project / WORKFLOWS_REL)
    result = RetireAntigravityWorkflowsMigration().apply(project)
    assert result.warnings == [refused_warning(WORKFLOWS_REL, "is a symlink")]


def test_workflows_path_that_is_a_file_is_refused(project: Path, no_install: list[str]) -> None:
    (project / ".agent").mkdir()
    (project / WORKFLOWS_REL).write_text("not a dir\n", encoding="utf-8")
    migration = RetireAntigravityWorkflowsMigration()
    assert migration.detect(project) is True
    result = migration.apply(project)
    assert (project / WORKFLOWS_REL).read_text(encoding="utf-8") == "not a dir\n"
    assert result.warnings == [refused_warning(WORKFLOWS_REL, "is not a directory")]


def test_no_workflows_dir_is_a_noop_without_mkdir(project: Path, no_install: list[str]) -> None:
    result = RetireAntigravityWorkflowsMigration().apply(project)
    assert result.success
    assert result.changes_made == []
    assert result.warnings == []
    assert not (project / ".agent").exists()
    assert not (project / ARCHIVE_REL).exists()


def test_second_run_is_idempotent_and_never_overwrites_a_backup(project: Path, no_install: list[str]) -> None:
    workflows = _workflows(project)
    first = _rendered()
    (workflows / "spec-kitty.plan.md").write_bytes(first)
    RetireAntigravityWorkflowsMigration().apply(project)

    again = RetireAntigravityWorkflowsMigration().apply(project)
    assert again.changes_made == []
    assert RetireAntigravityWorkflowsMigration().detect(project) is False

    second = first + b"\nreappeared\n"
    (workflows / "spec-kitty.plan.md").write_bytes(second)
    RetireAntigravityWorkflowsMigration().apply(project)

    backups = sorted(p.read_bytes() for p in (project / ARCHIVE_REL).rglob("*") if p.is_file())
    assert backups == sorted([first, second])


def test_dry_run_writes_nothing(project: Path, no_install: list[str]) -> None:
    owned = _workflows(project) / "spec-kitty.plan.md"
    owned.write_bytes(_rendered())

    result = RetireAntigravityWorkflowsMigration().apply(project, dry_run=True)

    assert owned.exists()
    assert not (project / ARCHIVE_REL).exists()
    assert result.changes_made == [f"Would archive {WORKFLOWS_REL}/spec-kitty.plan.md to {ARCHIVE_REL}/"]
    assert no_install == []


def test_antigravity_not_configured_leaves_workflows_alone(tmp_path: Path, no_install: list[str]) -> None:
    root = _project(tmp_path / "p", agents=("claude",))
    owned = _workflows(root) / "spec-kitty.plan.md"
    owned.write_bytes(_rendered())

    result = RetireAntigravityWorkflowsMigration().apply(root)

    assert owned.exists()
    assert result.changes_made == []
    assert no_install == []


def test_legacy_project_without_config_is_archived_but_nothing_installed(tmp_path: Path, no_install: list[str]) -> None:
    root = _project(tmp_path / "p", agents=None)
    (_workflows(root) / "spec-kitty.plan.md").write_bytes(_rendered())

    RetireAntigravityWorkflowsMigration().apply(root)

    assert set(_archived(root)) == {"spec-kitty.plan.md"}
    assert no_install == []


def test_unreadable_agent_config_is_a_warning(project: Path, monkeypatch: pytest.MonkeyPatch, no_install: list[str]) -> None:
    def boom(_root: Path) -> list[str]:
        raise AgentConfigError("bad yaml")

    monkeypatch.setattr(migration_module, "get_configured_agents", boom)
    owned = _workflows(project) / "spec-kitty.plan.md"
    owned.write_bytes(_rendered())

    migration = RetireAntigravityWorkflowsMigration()
    assert migration.detect(project) is True
    result = migration.apply(project)

    assert result.success
    assert owned.exists()
    assert result.warnings == [migration_module.agent_config_warning("bad yaml")]


def test_can_apply_requires_the_project(tmp_path: Path) -> None:
    assert RetireAntigravityWorkflowsMigration().can_apply(tmp_path)[0] is True
    assert RetireAntigravityWorkflowsMigration().can_apply(tmp_path / "missing")[0] is False


# ---------------------------------------------------------------------------
# apply(): command skills
# ---------------------------------------------------------------------------


def test_configured_antigravity_gets_the_command_skills(project: Path) -> None:
    (_workflows(project) / "spec-kitty.plan.md").write_bytes(_rendered())

    result = RetireAntigravityWorkflowsMigration().apply(project)

    assert result.success, result.errors
    for command in CANONICAL_COMMANDS:
        assert (project / command_skill_rel_path(command)).is_file()
    assert f"Installed command skill {command_skill_rel_path('plan')}" in result.changes_made
    assert not (project / WORKFLOWS_REL / "spec-kitty.plan.md").exists()


def test_installer_refusal_is_a_warning(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    error = InstallerError("a directory sits at a canonical SKILL.md")

    def refuse(repo_root: Path, agent_key: str, *, dry_run: bool = False) -> command_installer.InstallReport:
        raise error

    monkeypatch.setattr(migration_module.command_installer, "install", refuse)

    result = RetireAntigravityWorkflowsMigration().apply(project)

    assert result.success
    assert result.warnings == [install_refused_warning(str(error))]


def test_installer_collisions_are_reported(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rel = command_skill_rel_path("plan")

    def collide(repo_root: Path, agent_key: str, *, dry_run: bool = False) -> command_installer.InstallReport:
        return command_installer.InstallReport(collisions=[rel])

    monkeypatch.setattr(migration_module.command_installer, "install", collide)

    result = RetireAntigravityWorkflowsMigration().apply(project)

    assert result.warnings == [command_installer.collision_warning(rel)]
    assert result.preserved_paths == [rel]
