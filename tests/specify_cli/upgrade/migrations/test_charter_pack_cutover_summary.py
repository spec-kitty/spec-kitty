"""Charter-pack cutover: the upgrade summary, human and ``--json`` (#3732, T064).

The rendering helper is tested directly; one legacy project is then upgraded
through ``spec-kitty upgrade`` (human dry run, human real run, ``--json``).
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from rich.console import Console

from kernel.clock import now_utc
from specify_cli.upgrade.migrations._charter_pack_cutover_report import CutoverReport
from specify_cli.upgrade.migrations.base import MigrationResult
from specify_cli.upgrade.runner import UpgradeResult

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

CUTOVER = "charter_pack_cutover"
CONFIG = ".kittify/config.yaml"
EIGHT_KINDS = "activated_kinds: [directives, tactics, styleguides, toolguides, paradigms, procedures, agent_profiles, mission_step_contracts]\n"
LEGACY_CONFIG = (
    "vcs:\n  type: git\n"
    "agents:\n  available: []\n"
    "governance:\n  doctrine:\n    selected_directives: [003-decision-documentation-requirement]\n" + EIGHT_KINDS + "activated_glossary_packs: []\n"
    "activated_tactics: [my-custom-tactic]\n"
    "mission_type_activations: [software-dev]\n"
)


@contextlib.contextmanager
def _captured_console() -> Iterator[Console]:
    from specify_cli.cli.commands import upgrade as upgrade_module

    recorder = Console(record=True, width=400, color_system=None)
    original = upgrade_module.console
    upgrade_module.console = recorder
    try:
        yield recorder
    finally:
        upgrade_module.console = original


def _result(**migrations: MigrationResult) -> UpgradeResult:
    return UpgradeResult(success=True, from_version="4.0.0rc5", to_version="4.0.0rc6", migration_results=dict(migrations))


# --------------------------------------------------------------------------- #
# The rendering helper
# --------------------------------------------------------------------------- #


def test_summary_prints_the_change_lines_of_a_structured_report() -> None:
    from specify_cli.cli.commands.upgrade import _print_migration_summaries

    report = CutoverReport(reset=[".kittify/config.yaml: activated_kinds [x]"], kept_for_review=["kept"])
    result = _result(**{CUTOVER: report.to_migration_result(dry_run=False)})
    with _captured_console() as recorder:
        _print_migration_summaries(result)
    text = recorder.export_text()
    assert f"{CUTOVER}:" in text
    assert "Reset .kittify/config.yaml: activated_kinds [x]" in text, "markup-like text is printed literally"
    assert "kept" not in text, "kept lines are warnings, printed in the Warnings section"


def test_summary_skips_plain_migrations_and_empty_reports() -> None:
    from specify_cli.cli.commands.upgrade import _print_migration_summaries

    result = _result(
        plain=MigrationResult(success=True, changes_made=["Updated a file"]),
        listing=MigrationResult(success=True, changes_made=["[1, 2]"]),
        empty=MigrationResult(success=True, changes_made=[]),
        quiet=CutoverReport().to_migration_result(dry_run=True),
    )
    with _captured_console() as recorder:
        _print_migration_summaries(result)
    assert recorder.export_text() == ""


def test_dry_run_preview_text_has_one_period() -> None:
    from specify_cli.cli.commands.upgrade import _clause

    assert _clause("re-run the command.") == "re-run the command"
    assert _clause("no period ") == "no period"
    assert f"{_clause('x.')}. Use --plan-json" == "x. Use --plan-json"


# --------------------------------------------------------------------------- #
# Through spec-kitty upgrade
# --------------------------------------------------------------------------- #


def _git(project: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=project, check=True, capture_output=True)


def _legacy_project(project: Path) -> Path:
    from specify_cli.migration.schema_version import MAX_SUPPORTED_SCHEMA
    from specify_cli.upgrade.metadata import ProjectMetadata
    from specify_cli.upgrade.runner import MigrationRunner

    kittify = project / ".kittify"
    kittify.mkdir(parents=True)
    (kittify / "config.yaml").write_text(LEGACY_CONFIG, encoding="utf-8")
    ProjectMetadata(version="4.0.0rc5", initialized_at=now_utc(), python_version="3.11", platform="test", platform_version="test").save(kittify)
    MigrationRunner._stamp_schema_version(kittify, MAX_SUPPORTED_SCHEMA)
    _git(project, "init", "-q", "-b", "main")
    _git(project, "-c", "user.email=t@example.com", "-c", "user.name=t", "add", "-A")
    _git(project, "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-q", "--no-verify", "-m", "fixture")
    return project


def _upgrade(project: Path, *flags: str) -> tuple[int, str]:
    from typer.testing import CliRunner

    from specify_cli import app

    with contextlib.chdir(project):
        result = CliRunner().invoke(app, ["upgrade", "--yes", "--no-worktrees", *flags], catch_exceptions=False)
    return result.exit_code, result.output


def _tree(project: Path) -> dict[str, bytes]:
    return {p.relative_to(project).as_posix(): p.read_bytes() for p in sorted(project.rglob("*")) if p.is_file() and ".git" not in p.parts}


def test_human_dry_run_shows_every_category_and_writes_nothing(tmp_path: Path) -> None:
    project = _legacy_project(tmp_path / "project")
    before = _tree(project)
    code, output = _upgrade(project, "--dry-run")
    assert code == 0, output
    assert _tree(project) == before
    flat = " ".join(output.split())
    assert f"{CUTOVER}:" in flat
    assert "Would rewrite .kittify/config.yaml: governance.doctrine -> governance.charter" in flat
    assert "Would reset .kittify/config.yaml: activated_kinds (matched the released default kind gate; now absent)" in flat
    assert "Would reset .kittify/config.yaml: activated_glossary_packs was []" in flat
    assert "Would keep for review: .kittify/config.yaml: activated_tactics customised; not changed" in flat
    assert "To switch the kind off again, set activated_glossary_packs: [] in .kittify/config.yaml." in flat


def test_real_run_human_and_json_summaries(tmp_path: Path) -> None:
    human = _legacy_project(tmp_path / "human")
    code, output = _upgrade(human)
    assert code == 0, output
    flat = " ".join(output.split())
    assert "Rewrote .kittify/config.yaml: governance.doctrine -> governance.charter" in flat
    assert "Reset .kittify/config.yaml: activated_kinds" in flat
    assert "Kept for review: .kittify/config.yaml: activated_tactics customised; not changed" in flat
    config = (human / CONFIG).read_text(encoding="utf-8")
    assert "activated_kinds" not in config and "activated_glossary_packs" not in config and "my-custom-tactic" in config

    machine = _legacy_project(tmp_path / "machine")
    code, output = _upgrade(machine, "--json")
    assert code == 0, output
    payload = json.loads(output[output.index("{") :])
    report = payload["migration_reports"][CUTOVER]
    assert report["reset"] == [
        ".kittify/config.yaml: activated_kinds (matched the released default kind gate; now absent)",
        ".kittify/config.yaml: activated_glossary_packs was [] (nothing active); now absent (all glossary packs available)",
    ]
    assert report["kept_for_review"] == [".kittify/config.yaml: activated_tactics customised; not changed"]
    assert any("To switch the kind off again, set activated_glossary_packs: []" in w for w in payload["warnings"]), payload["warnings"]
    migration = next(m for m in payload["migrations"] if m["id"] == CUTOVER)
    assert migration["manual_review_required"] is True
