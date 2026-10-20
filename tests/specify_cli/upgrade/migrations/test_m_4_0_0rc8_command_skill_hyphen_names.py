"""Migration ``4.0.0rc8_command_skill_hyphen_names`` (#6475, FR-005 / FR-006, User Story 2).

Fixture provenance (R-M7): ``fixtures/command_skill_hyphen_names/`` holds genuine prior-release
bytes. ``spec-kitty.{plan,specify,status}/SKILL.md`` and their manifest entries were produced
once by the pre-#6475 installer itself:

    git worktree add --detach <tmp>/prior 885a7dd7~1      # the commit before WP02's rename
    ln -s <core>/packs/built-in <tmp>/prior/packs/built-in  # same pack pin at both commits
    printf 'agents:\\n  available:\\n    - codex\\n' > <tmp>/render/.kittify/config.yaml
    PYTHONPATH=<tmp>/prior/src python -c \\
        "from pathlib import Path; from specify_cli.skills import command_installer as ci; \\
         ci.install(Path('<tmp>/render'), 'codex')"

then the three folders were copied and the manifest trimmed to their three entries
(``installed_at`` rounded). The rendered bytes carry no version, so they stay the prior
release's rendering; ``test_fixture_bytes_are_the_prior_release_rendering`` pins that today's
``legacy_rendering`` still reproduces them (the A-M1 ownership proof).

Each case strips this migration's row from both ledger partitions, so the run under test is the
migration's own and not a seeded settle.
"""

from __future__ import annotations

import contextlib
import json
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

from specify_cli import app as root_app
from specify_cli.cli.commands import upgrade as upgrade_cmd
from specify_cli.cli.commands.upgrade import command_skill_rename_notice
from specify_cli.skills import command_installer, manifest_store
from specify_cli.skills.command_installer import CANONICAL_COMMANDS, collision_warning, legacy_kept_warning
from specify_cli.skills.command_skill_names import command_skill_rel_path, legacy_command_skill_rel_path
from specify_cli.tool_surface.operations import ApplyConsent, AssessmentInputs, OperationRoot
from specify_cli.upgrade.ledger import CLONE_LOCAL_LEDGER_RELPATH, TRACKED_LEDGER_RELPATH
from specify_cli.upgrade.runner import UpgradeResult
from specify_cli.upgrade.migrations.base import MigrationResult
from specify_cli.upgrade.migrations.m_4_0_0rc8_command_skill_hyphen_names import (
    CommandSkillHyphenNamesMigration,
    manifest_unreadable_warning,
    unconfigured_legacy_warning,
    unrecorded_legacy_warning,
)

pytestmark = [pytest.mark.unit]

_FIXTURES = Path(__file__).parent / "fixtures" / "command_skill_hyphen_names"
_FIXTURE_COMMANDS = ("plan", "specify", "status")
_MANIFEST = ".kittify/command-skills-manifest.json"
_MIGRATION_ID = "4.0.0rc8_command_skill_hyphen_names"
_EDITED = b"---\nname: spec-kitty.plan\n---\nmy own edits\n"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _strip_ledger_row(project: Path) -> None:
    """Remove this migration's record from both ledger partitions (R-M7)."""
    for rel in (TRACKED_LEDGER_RELPATH, CLONE_LOCAL_LEDGER_RELPATH):
        path = project / rel
        if not path.is_file():
            continue
        kept = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and json.loads(line).get("id") != _MIGRATION_ID]
        path.write_text("".join(f"{line}\n" for line in kept), encoding="utf-8")


def _seed_prior_release(project: Path) -> None:
    """Lay down the prior release's dotted skills and the manifest recording them."""
    for command in _FIXTURE_COMMANDS:
        rel = legacy_command_skill_rel_path(command)
        (project / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_FIXTURES / f"spec-kitty.{command}" / "SKILL.md", project / rel)
    shutil.copyfile(_FIXTURES / "command-skills-manifest.json", project / _MANIFEST)
    _strip_ledger_row(project)


def _project(root: Path, agents: tuple[str, ...] = ("codex",)) -> Path:
    kittify = root / ".kittify"
    kittify.mkdir(parents=True)
    listed = "".join(f"    - {agent}\n" for agent in agents)
    (kittify / "config.yaml").write_text(f"agents:\n  available:\n{listed}" if agents else "agents:\n  available: []\n", encoding="utf-8")
    return root


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    root = _project(tmp_path / "project")
    _seed_prior_release(root)
    return root


def _manifest_paths(project: Path) -> set[str]:
    return {entry.path for entry in manifest_store.load(project).entries}


def _canonical_rels() -> set[str]:
    return {command_skill_rel_path(command) for command in CANONICAL_COMMANDS}


def _tree(project: Path) -> dict[str, bytes]:
    return {p.relative_to(project).as_posix(): p.read_bytes() for p in sorted(project.rglob("*")) if p.is_file()}


# ---------------------------------------------------------------------------
# Fixture provenance and declaration
# ---------------------------------------------------------------------------


def test_fixture_bytes_are_the_prior_release_rendering(tmp_path: Path) -> None:
    """The committed dotted bytes equal today's render mapped back to the legacy name (A-M1)."""
    root = _project(tmp_path / "render")
    recorded = {e["path"]: e["content_hash"] for e in json.loads((_FIXTURES / "command-skills-manifest.json").read_text(encoding="utf-8"))["entries"]}
    for command in _FIXTURE_COMMANDS:
        prior = (_FIXTURES / f"spec-kitty.{command}" / "SKILL.md").read_bytes()
        assert prior.startswith(f"---\nname: spec-kitty.{command}\n".encode())
        assert recorded[legacy_command_skill_rel_path(command)] == manifest_store.fingerprint(prior)
        today = command_installer._render_command_skill(root, command, "codex", command_installer._get_version())
        assert command_installer.legacy_rendering(today, command) == prior


def test_declaration() -> None:
    migration = CommandSkillHyphenNamesMigration()
    assert migration.migration_id == _MIGRATION_ID
    assert migration.target_version == "4.0.0rc8"
    assert migration.clone_local_effect is True
    assert migration.runs_on_worktrees is True
    assert migration.requires_git_repository is False


# ---------------------------------------------------------------------------
# detect()
# ---------------------------------------------------------------------------


def test_detect_true_for_a_prior_release_project(project: Path) -> None:
    assert CommandSkillHyphenNamesMigration().detect(project) is True


def test_detect_false_without_kittify(tmp_path: Path) -> None:
    assert CommandSkillHyphenNamesMigration().detect(tmp_path) is False


def test_detect_false_for_a_fresh_hyphen_project(tmp_path: Path) -> None:
    root = _project(tmp_path / "fresh")
    command_installer.install(root, "codex")
    assert CommandSkillHyphenNamesMigration().detect(root) is False


def test_detect_true_for_an_unrecorded_dotted_folder(tmp_path: Path) -> None:
    root = _project(tmp_path / "p")
    (root / ".agents/skills/spec-kitty.plan").mkdir(parents=True)
    assert CommandSkillHyphenNamesMigration().detect(root) is True


def test_detect_ignores_dotted_folders_of_unknown_commands(tmp_path: Path) -> None:
    root = _project(tmp_path / "p")
    (root / ".agents/skills/spec-kitty.mine").mkdir(parents=True)
    assert CommandSkillHyphenNamesMigration().detect(root) is False


def test_detect_true_for_a_corrupt_manifest(tmp_path: Path) -> None:
    root = _project(tmp_path / "p")
    (root / _MANIFEST).write_text("{not json", encoding="utf-8")
    assert CommandSkillHyphenNamesMigration().detect(root) is True


# ---------------------------------------------------------------------------
# apply()
# ---------------------------------------------------------------------------


def test_owned_unmodified_dotted_skills_are_removed_and_hyphen_installed(project: Path) -> None:
    result = CommandSkillHyphenNamesMigration().apply(project)

    assert result.success, result.errors
    assert result.warnings == []
    for command in _FIXTURE_COMMANDS:
        assert not (project / legacy_command_skill_rel_path(command)).parent.exists()
        assert f"Removed legacy dotted command skill {legacy_command_skill_rel_path(command)}" in result.changes_made
    assert _manifest_paths(project) == _canonical_rels()
    assert all((project / rel).is_file() for rel in _canonical_rels())
    assert CommandSkillHyphenNamesMigration().detect(project) is False


def test_stale_recorded_hash_with_prior_release_bytes_is_still_owned(project: Path) -> None:
    """A-M1: bytes equal to the render under the legacy name are ours even when the hash moved."""
    manifest = manifest_store.load(project)
    rel = legacy_command_skill_rel_path("plan")
    entry = manifest.find(rel)
    assert entry is not None
    manifest.upsert(replace(entry, content_hash="0" * 64))
    manifest_store.save(project, manifest)

    result = CommandSkillHyphenNamesMigration().apply(project)

    assert result.success
    assert not (project / rel).exists()
    assert result.warnings == []


def test_edited_dotted_skill_is_kept_with_a_warning_and_dropped_from_the_manifest(project: Path) -> None:
    rel = legacy_command_skill_rel_path("plan")
    (project / rel).write_bytes(_EDITED)

    result = CommandSkillHyphenNamesMigration().apply(project)

    assert result.success
    assert (project / rel).read_bytes() == _EDITED
    assert rel not in _manifest_paths(project)
    assert result.warnings == [legacy_kept_warning(rel)]
    assert "has your edits, so it was kept; it is no longer managed" in result.warnings[0]
    assert result.preserved_paths == [rel]
    assert (project / command_skill_rel_path("plan")).is_file()


def test_unrecorded_dotted_folder_is_untouched(project: Path) -> None:
    mine = project / legacy_command_skill_rel_path("review")
    mine.parent.mkdir(parents=True)
    mine.write_bytes(b"user-authored\n")

    result = CommandSkillHyphenNamesMigration().apply(project)

    assert result.success
    assert mine.read_bytes() == b"user-authored\n"
    assert legacy_command_skill_rel_path("review") not in _manifest_paths(project)


def test_user_folder_at_a_canonical_path_is_a_collision_and_the_rest_installs(project: Path) -> None:
    rel = command_skill_rel_path("plan")
    (project / rel).parent.mkdir(parents=True)
    (project / rel).write_bytes(b"my own plan skill\n")

    result = CommandSkillHyphenNamesMigration().apply(project)

    assert result.success
    assert (project / rel).read_bytes() == b"my own plan skill\n"
    assert result.warnings == [collision_warning(rel)]
    assert rel in result.preserved_paths
    assert _manifest_paths(project) == _canonical_rels() - {rel}


def test_missing_manifest_is_success_with_a_warning_and_touches_nothing(project: Path) -> None:
    (project / _MANIFEST).unlink()
    before = _tree(project)

    result = CommandSkillHyphenNamesMigration().apply(project)

    assert result.success
    assert result.warnings == [unrecorded_legacy_warning(legacy_command_skill_rel_path(c)) for c in sorted(_FIXTURE_COMMANDS)]
    assert "spec-kitty doctor skills" in result.warnings[0]
    assert _tree(project) == before


def test_corrupt_manifest_is_success_with_a_warning(project: Path) -> None:
    (project / _MANIFEST).write_text("{not json", encoding="utf-8")
    before = _tree(project)

    result = CommandSkillHyphenNamesMigration().apply(project)

    assert result.success
    assert len(result.warnings) == 1
    assert result.warnings[0].startswith("Command-skill manifest .kittify/command-skills-manifest.json could not be read (")
    assert result.warnings[0].endswith(manifest_unreadable_warning("x").split("(x)", 1)[1])
    assert _tree(project) == before


def test_no_configured_command_skill_agent_creates_nothing(tmp_path: Path) -> None:
    root = _project(tmp_path / "p", agents=("claude",))
    _seed_prior_release(root)
    gone = legacy_command_skill_rel_path("status")
    (root / gone).unlink()
    (root / gone).parent.rmdir()

    result = CommandSkillHyphenNamesMigration().apply(root)

    assert result.success
    kept = sorted(legacy_command_skill_rel_path(c) for c in ("plan", "specify"))
    assert sorted(result.warnings) == sorted(unconfigured_legacy_warning(rel) for rel in kept)
    assert _manifest_paths(root) == set(kept)
    assert not any((root / ".agents/skills").glob("spec-kitty-*"))
    assert not (root / ".codex").exists()


def test_no_configured_agent_and_no_skills_root_never_mkdirs(tmp_path: Path) -> None:
    root = _project(tmp_path / "p", agents=())
    shutil.copyfile(_FIXTURES / "command-skills-manifest.json", root / _MANIFEST)

    result = CommandSkillHyphenNamesMigration().apply(root)

    assert result.success
    assert not (root / ".agents").exists()
    assert _manifest_paths(root) == set()


def test_dry_run_changes_nothing(project: Path) -> None:
    before = _tree(project)

    result = CommandSkillHyphenNamesMigration().apply(project, dry_run=True)

    assert result.success
    assert len(result.changes_made) == len(_FIXTURE_COMMANDS)
    assert all(line.startswith("Would retire legacy dotted command skill ") for line in result.changes_made)
    assert _tree(project) == before


def test_second_run_changes_nothing(project: Path) -> None:
    """NFR-002: a re-run reports nothing and writes nothing."""
    (project / legacy_command_skill_rel_path("plan")).write_bytes(_EDITED)
    CommandSkillHyphenNamesMigration().apply(project)
    before = _tree(project)

    result = CommandSkillHyphenNamesMigration().apply(project)

    assert result.success
    assert result.changes_made == result.warnings == []
    assert _tree(project) == before


def test_vibe_and_codex_share_one_batch(tmp_path: Path) -> None:
    root = _project(tmp_path / "p", agents=("codex", "vibe"))
    _seed_prior_release(root)

    result = CommandSkillHyphenNamesMigration().apply(root)

    assert result.success
    entries = manifest_store.load(root).entries
    assert {entry.path for entry in entries} == _canonical_rels()
    assert all(set(entry.agents) == {"codex", "vibe"} for entry in entries)


def test_lane_worktree_copy_is_migrated(project: Path) -> None:
    """``runs_on_worktrees``: a lane worktree holds its own git-ignored copy."""
    lane = project / ".worktrees" / "demo-lane-a"
    _project(lane)
    _seed_prior_release(lane)

    result = CommandSkillHyphenNamesMigration().apply(lane)

    assert result.success
    assert not (lane / legacy_command_skill_rel_path("plan")).exists()
    assert (lane / command_skill_rel_path("plan")).is_file()
    assert (project / legacy_command_skill_rel_path("plan")).is_file()  # the main checkout is its own run


def test_installer_refusal_is_a_failure_naming_doctor(project: Path) -> None:
    """A refusal the installer does not downgrade to a warning (a directory at SKILL.md) fails."""
    (project / command_skill_rel_path("plan")).mkdir(parents=True)

    result = CommandSkillHyphenNamesMigration().apply(project)

    assert result.success is False
    assert "Command-skill install for codex failed" in result.errors[0]
    assert "spec-kitty doctor skills" in result.errors[0]


# ---------------------------------------------------------------------------
# Notice
# ---------------------------------------------------------------------------


def test_rename_notice_names_each_harness_token() -> None:
    assert command_skill_rename_notice() == (
        "Command skills are now named spec-kitty-<command> (for example `$spec-kitty-specify` in Codex, "
        "`/spec-kitty-specify` in Vibe, Letta and Antigravity, `/skill:spec-kitty-specify` in Pi)."
    )


def _upgrade_result(migration_result: MigrationResult | None, *, dry_run: bool = False) -> UpgradeResult:
    result = UpgradeResult(success=True, from_version="4.0.0rc7", to_version="4.0.0rc8", dry_run=dry_run)
    if migration_result is not None:
        result.migration_results[_MIGRATION_ID] = migration_result
    return result


@pytest.mark.parametrize(
    ("migration_result", "dry_run", "expected"),
    [
        (MigrationResult(success=True, changes_made=["Removed legacy dotted command skill x"]), False, True),
        (MigrationResult(success=True, preserved_paths=["x"]), False, True),
        (MigrationResult(success=True), False, False),
        (MigrationResult(success=False, changes_made=["x"]), False, False),
        (MigrationResult(success=True, changes_made=["Would retire x"]), True, False),
        (None, False, False),
    ],
)
def test_rename_migration_ran(migration_result: MigrationResult | None, dry_run: bool, expected: bool) -> None:
    assert upgrade_cmd._rename_migration_ran(_upgrade_result(migration_result, dry_run=dry_run)) is expected


def _surface_repair(project: Path) -> Any:
    """The command-skill owner assessment the upgrade surface repair prepares, wrapped as its container."""
    inputs = AssessmentInputs(OperationRoot("project", "project", project), consent=ApplyConsent(automatic=True))
    return SimpleNamespace(owners=(command_installer.prepare_commands(inputs, ("codex",), prune=True),))


def test_surface_repair_warnings_and_rename_flag_for_a_prior_release_project(project: Path) -> None:
    """Upgrade prints the provider's warning for kept / colliding paths and flags the rename."""
    rel = legacy_command_skill_rel_path("plan")
    (project / rel).write_bytes(_EDITED)
    collided = command_skill_rel_path("status")
    (project / collided).parent.mkdir(parents=True)
    (project / collided).write_bytes(b"mine\n")

    prepared = _surface_repair(project)

    assert sorted(upgrade_cmd._command_skill_warnings(prepared)) == sorted([collision_warning(collided), legacy_kept_warning(rel)])
    assert upgrade_cmd._command_skill_legacy_retired(prepared) is True


def test_surface_repair_of_a_migrated_project_flags_nothing(project: Path) -> None:
    CommandSkillHyphenNamesMigration().apply(project)

    prepared = _surface_repair(project)

    assert upgrade_cmd._command_skill_warnings(prepared) == []
    assert upgrade_cmd._command_skill_legacy_retired(prepared) is False


# ---------------------------------------------------------------------------
# End to end: spec-kitty upgrade (US2 scenarios 1, 2, 4, 9)
# ---------------------------------------------------------------------------


def _git(project: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=project, check=True, capture_output=True)


def _ledger_ids(project: Path, rel: str) -> list[tuple[str, str]]:
    path = project / rel
    if not path.is_file():
        return []
    return [(record["id"], record["result"]) for record in map(json.loads, path.read_text(encoding="utf-8").splitlines()) if record.get("id") == _MIGRATION_ID]


@pytest.mark.integration
@pytest.mark.slow
def test_upgrade_migrates_a_prior_release_clone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("SPEC_KITTY_NO_NAG", "SPEC_KITTY_NO_UPGRADE_CHECK"):
        monkeypatch.delenv(name, raising=False)
    runner = CliRunner()
    root = tmp_path / "project"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    with contextlib.chdir(root):
        init = runner.invoke(root_app, ["init", "--ai", "codex", "--non-interactive"], catch_exceptions=False)
    assert init.exit_code == 0, init.output
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    # Downgrade this clone to the prior release's command-skill layout.
    for command in CANONICAL_COMMANDS:
        shutil.rmtree(root / command_skill_rel_path(command).rsplit("/", 1)[0])
    _seed_prior_release(root)
    (root / legacy_command_skill_rel_path("plan")).write_bytes(_EDITED)
    assert _ledger_ids(root, CLONE_LOCAL_LEDGER_RELPATH) == _ledger_ids(root, TRACKED_LEDGER_RELPATH) == []

    with contextlib.chdir(root):
        result = runner.invoke(root_app, ["upgrade", "--yes"], catch_exceptions=False)

    output = " ".join(result.output.split())
    assert result.exit_code == 0, result.output
    assert not (root / legacy_command_skill_rel_path("specify")).exists()
    assert (root / legacy_command_skill_rel_path("plan")).read_bytes() == _EDITED
    assert _manifest_paths(root) == _canonical_rels()
    assert legacy_kept_warning(legacy_command_skill_rel_path("plan")) in output
    assert command_skill_rename_notice() in output
    # Clone-local: recorded per clone, never in the committed ledger (scenario 9).
    assert _ledger_ids(root, CLONE_LOCAL_LEDGER_RELPATH) == [(_MIGRATION_ID, "success")]
    assert _ledger_ids(root, TRACKED_LEDGER_RELPATH) == []

    with contextlib.chdir(root):
        again = runner.invoke(root_app, ["upgrade", "--yes"], catch_exceptions=False)
    assert again.exit_code == 0, again.output
    assert command_skill_rename_notice() not in " ".join(again.output.split())
    assert _ledger_ids(root, CLONE_LOCAL_LEDGER_RELPATH) == [(_MIGRATION_ID, "success")]
