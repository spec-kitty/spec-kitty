"""An upgrade leaves an absent activation key absent, so ``charter synthesize`` keeps working (#6629).

A project that ran the charter interview before the activation ledger existed
has ``answers.yaml`` selections and no ``activated_<kind>`` key, so every
built-in artifact of those kinds is in force. ``unify_charter_activation_promote_answers``
seeded the absent key with that whole set (38 directives) before appending the
selections. Runtime governance did not change, but ``charter synthesize`` then
treated the list as an operator's activation: it demanded one companion tactic
per directive and skipped the fresh-project seed, so ``implement`` refused
every work package with ``synthesized_drg missing``.
"""

from __future__ import annotations

import contextlib
import dataclasses
import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from charter.activation.activation_ledger import load_activation_ledger
from charter.activation.interview import default_interview, write_interview_answers
from charter.offering.artifact_kinds import ArtifactKind
from kernel.clock import now_utc
from specify_cli.cli.commands.charter import charter_app
from specify_cli.cli.commands.charter._synthesis import _build_synthesis_request, _catalog_is_established
from specify_cli.core.agent_config import AgentConfig, save_agent_config
from specify_cli.upgrade.metadata import ProjectMetadata
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.migrations.m_4_0_0rc8_promote_interview_selections import MIGRATION_ID
from specify_cli.upgrade.registry import MigrationRegistry
from specify_cli.upgrade.runner import MigrationRunner
from tests._factories.activation_ledger import read_activation_ledger, seed_activation_ledger

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

TARGET = "4.0.0rc8"

#: A version at or below the promotion's 3.2.6rc1, so the ledger-adoption backfill does not settle it.
PRE_PROMOTION_VERSION = "3.2.0rc30"

#: The kinds the promotion covers; none of them may gain an ``activated_<kind>`` key.
PROMOTABLE_KINDS = (
    ArtifactKind.DIRECTIVE,
    ArtifactKind.TACTIC,
    ArtifactKind.STYLEGUIDE,
    ArtifactKind.TOOLGUIDE,
    ArtifactKind.PARADIGM,
    ArtifactKind.PROCEDURE,
    ArtifactKind.AGENT_PROFILE,
    ArtifactKind.MISSION_STEP_CONTRACT,
)

#: Built-in ids the reporter's interview names: every one is in force while the key is absent.
SELECTED_DIRECTIVES = ["DIRECTIVE_001", "DIRECTIVE_010", "DIRECTIVE_024"]
SELECTED_PARADIGMS = ["domain-driven-design"]


@pytest.fixture(autouse=True)
def _real_registry() -> None:
    MigrationRegistry.clear()
    auto_discover_migrations()


def _pre_ledger_interviewed_project(tmp_path: Path) -> Path:
    """The #6629 shape: a pre-activation-ledger project with interview selections and no ``activated_*`` key anywhere."""
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    (tmp_path / ".kittify").mkdir()
    save_agent_config(tmp_path, AgentConfig(available=["claude"]))
    ProjectMetadata(version=PRE_PROMOTION_VERSION, initialized_at=now_utc()).save(tmp_path / ".kittify")
    interview = dataclasses.replace(
        default_interview(mission="software-dev", profile="minimal"),
        selected_directives=SELECTED_DIRECTIVES,
        selected_paradigms=SELECTED_PARADIGMS,
    )
    write_interview_answers(tmp_path / ".kittify" / "charter" / "interview" / "answers.yaml", interview)
    return tmp_path


def test_upgrade_leaves_absent_keys_absent_and_synthesis_fresh(tmp_path: Path) -> None:
    project = _pre_ledger_interviewed_project(tmp_path)

    result = MigrationRunner(project).upgrade(TARGET, include_worktrees=False)
    assert result.success, result.errors

    ledger = load_activation_ledger(project)
    assert {kind: ledger.allow_for(kind) for kind in PROMOTABLE_KINDS if ledger.allow_for(kind) is not None} == {}
    for legacy in (project / ".kittify" / "config.yaml", project / ".kittify" / "charter" / "charter.yaml"):
        if legacy.is_file():
            assert "activated_" not in legacy.read_text(encoding="utf-8"), legacy

    request, _adapter = _build_synthesis_request(project, "fixture")
    assert request.interview_snapshot["selected_directives"] == []
    assert _catalog_is_established(project) is False

    with contextlib.chdir(project):
        synthesized = CliRunner().invoke(charter_app, ["synthesize", "--dry-run", "--json"], catch_exceptions=False)
    assert synthesized.exit_code == 0, synthesized.stdout
    assert json.loads(synthesized.stdout)["mode"] == "fresh_project_seed_dry_run"


def test_a_later_upgrade_never_undoes_an_operator_narrowing(tmp_path: Path) -> None:
    """The promotion settles on its first run, so it never appends interview ids back after ``--only``."""
    project = _pre_ledger_interviewed_project(tmp_path)
    first = MigrationRunner(project).upgrade(TARGET, include_worktrees=False)
    assert first.success, first.errors
    assert MIGRATION_ID in first.migrations_applied

    narrowed = ["024-locality-of-change"]
    seed_activation_ledger(project, activated_directives=narrowed)
    for _ in range(2):
        later = MigrationRunner(project).upgrade(TARGET, include_worktrees=False)
        assert later.success, later.errors
        assert MIGRATION_ID not in later.migrations_applied
        assert read_activation_ledger(project)["activated_directives"] == narrowed


def test_a_project_the_shipped_promotion_already_settled_keeps_its_narrowed_list(tmp_path: Path) -> None:
    """An rc7 project: ledger adoption settles the shipped promotion, so ids the operator removed stay out (#6499)."""
    project = _pre_ledger_interviewed_project(tmp_path)
    ProjectMetadata(version="4.0.0rc7", initialized_at=now_utc()).save(project / ".kittify")
    narrowed = ["024-locality-of-change"]
    seed_activation_ledger(project, activated_directives=narrowed)

    result = MigrationRunner(project).upgrade(TARGET, include_worktrees=False)

    assert result.success, result.errors
    assert MIGRATION_ID in result.migrations_applied
    assert read_activation_ledger(project)["activated_directives"] == narrowed


def test_a_project_without_an_interview_settles_on_its_first_upgrade(tmp_path: Path) -> None:
    """Interview and narrowing after the upgrade: a later upgrade does not re-run the promotion."""
    project = _pre_ledger_interviewed_project(tmp_path)
    (project / ".kittify" / "charter" / "interview" / "answers.yaml").unlink()
    first = MigrationRunner(project).upgrade(TARGET, include_worktrees=False)
    assert first.success, first.errors
    assert MIGRATION_ID in first.migrations_applied

    interview = dataclasses.replace(default_interview(mission="software-dev", profile="minimal"), selected_directives=SELECTED_DIRECTIVES)
    write_interview_answers(project / ".kittify" / "charter" / "interview" / "answers.yaml", interview)
    narrowed = ["024-locality-of-change"]
    seed_activation_ledger(project, activated_directives=narrowed)
    later = MigrationRunner(project).upgrade(TARGET, include_worktrees=False)

    assert later.success, later.errors
    assert MIGRATION_ID not in later.migrations_applied
    assert read_activation_ledger(project)["activated_directives"] == narrowed
