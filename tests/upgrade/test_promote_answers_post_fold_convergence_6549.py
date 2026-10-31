"""#6549: the interview promotion must not re-fire after the charter fold.

The shipped ``unify_charter_activation_promote_answers`` step (3.2.6rc1) read only
``.kittify/config.yaml``. On a project upgraded from a pre-ledger build, the first
upgrade applied ``consolidate_charter_bundle_fold`` — which relocates the
``activated_*`` keys into ``charter.yaml`` and removes them from ``config.yaml`` —
and recorded the promotion ``skipped`` (it found nothing to promote). A ``skipped``
record does not settle a migration, so the second upgrade re-selected the promotion.
It now saw an emptied ``config.yaml``, seeded the absent key from the kind's whole
in-force set and wrote all 38 built-in directives back into ``config.yaml``,
contradicting ``charter.yaml``: a config delta plus an auto-commit on a project every
migration was supposed to have left alone.

#6629 fixed it: the shipped step is superseded (``SUPERSEDED_MIGRATIONS``, module bytes
untouched — DIRECTIVE_044) and ``4.0.0rc8_promote_interview_selections`` writes through
the resolved activation write target, never into an absent key. Nothing pinned either
half. ``tests/upgrade/test_activate_builtin_post_fold_dedup.py`` pins only the rc35
pair's post-fold dedup, and
``tests/upgrade/test_upgrade_keeps_absent_activation_6629.py`` pins the absent-key rule.

This module is that pin, on the project shape the defect needed: a pre-ledger project
whose ``config.yaml`` already mirrors its interview selection, so the shipped step finds
nothing to promote and is recorded ``skipped``.

The guard is proven able to fail: :func:`test_dropping_the_supersession_entry_reintroduces_the_config_copy`
removes the one table entry that holds the line, re-discovers the registry through the
production path and observes the #6549 symptom on the same fixture.

Boundary: the two-run claim covers the activation surfaces (``config.yaml``,
``charter.yaml``, the activation ledger and the applied activation migrations), which is
what #6549 corrupts. A project damaged on an older build keeps its divergent
``config.yaml`` copy — the runtime ignores it, ``spec-kitty doctor charter-packs`` reports
it as ``LEGACY_KEYS_PRESENT``, and stripping a tracked activation key is a maintainer
decision (see the PR's ``## Deferred``).
"""

from __future__ import annotations

import contextlib
import dataclasses
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
import typer
import yaml
from typer.testing import CliRunner

from charter.activation.interview import default_interview, write_interview_answers
from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.pack_paths import built_in_dir
from kernel.clock import now_utc
from specify_cli.cli.commands.upgrade import upgrade
from specify_cli.core.agent_config import AgentConfig, save_agent_config
from specify_cli.upgrade.metadata import ProjectMetadata
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.migrations.base import SupersededMigration
from specify_cli.upgrade.migrations.m_unify_charter_activation import UnifyCharterActivationMigration
from specify_cli.upgrade.migrations.m_unify_charter_activation_finalize import ConsolidateCharterBundleMigration
from specify_cli.upgrade.registry import MigrationRegistry
from specify_cli.upgrade.supersession import SUPERSEDED_MIGRATIONS

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

TARGET = "4.0.0rc8"

#: The shipped step whose post-fold re-fire is #6549.
SHIPPED_ID = "unify_charter_activation_promote_answers"

#: Every migration that writes an activation surface: none of them may re-run on the
#: second upgrade of a converged project.
ACTIVATION_MIGRATION_IDS = (
    SHIPPED_ID,
    "consolidate_charter_bundle_fold",
    "4.0.0rc8_activation_ledger",
    "4.0.0rc8_promote_interview_selections",
    "normalize_activation_absence",
)

#: A version below the fold and below the promotion's 3.2.6rc1, so both are selected and
#: the ledger-adoption backfill settles neither of them.
PRE_LEDGER_VERSION = "3.2.0rc30"

#: The one directive the fixture's interview selected, in both id forms.
SELECTED_STEM = "001-architectural-integrity-standard"
SELECTED_CANONICAL = "DIRECTIVE_001"

_CONFIG = Path(".kittify") / "config.yaml"
_ANSWERS = Path(".kittify") / "charter" / "interview" / "answers.yaml"
_ACTIVATION_LEDGER = Path(".kittify") / "charter" / "activation.yaml"


@pytest.fixture(autouse=True)
def _real_registry() -> Any:
    """Every test sees the registry ``auto_discover_migrations`` builds, before and after."""
    MigrationRegistry.clear()
    auto_discover_migrations()
    try:
        yield
    finally:
        MigrationRegistry.clear()
        auto_discover_migrations()


def _git(project: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(project), *args], check=True, capture_output=True, text=True).stdout


def _fold_crossing_project(tmp_path: Path) -> Path:
    """The #6549 shape: a pre-ledger project whose ``config.yaml`` mirrors its interview.

    Both preconditions matter. The version stamp keeps the fold and the promotion
    selected (and keeps the adoption backfill from settling them), and the mirrored
    selection is what makes the shipped promotion find nothing to promote — the
    ``skipped`` record that left it re-evaluable for the second pass.
    """
    subprocess.run(["git", "init", "-q", "-b", "work", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "--allow-empty", "-m", "root"], check=True)

    (tmp_path / ".kittify").mkdir()
    save_agent_config(tmp_path, AgentConfig(available=["claude"]))
    ProjectMetadata(version=PRE_LEDGER_VERSION, initialized_at=now_utc()).save(tmp_path / ".kittify")
    interview = dataclasses.replace(default_interview(mission="software-dev", profile="minimal"), selected_directives=[SELECTED_CANONICAL])
    write_interview_answers(tmp_path / _ANSWERS, interview)
    config = tmp_path / _CONFIG
    config.write_text(config.read_text(encoding="utf-8") + f"activated_directives:\n- {SELECTED_STEM}\n", encoding="utf-8")

    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "pre-ledger project with a mirrored interview selection")
    return tmp_path


def _snapshot(project: Path) -> dict[str, bytes]:
    """Every file under *project* except ``.git/`` — the whole state a convergence claim covers."""
    return {str(path.relative_to(project)): path.read_bytes() for path in project.rglob("*") if path.is_file() and ".git" not in path.parts}


def _config_activation_keys(project: Path) -> dict[str, Any]:
    """The ``activated_*`` keys ``config.yaml`` carries.

    Read through a plain ``safe_load`` so the answer is about the document, not about a
    round-trip writer's comments: an absent key and a key holding an empty list are
    different states, and both must be visible here.
    """
    data = yaml.safe_load((project / _CONFIG).read_text(encoding="utf-8")) or {}
    return {key: value for key, value in data.items() if key.startswith("activated_")}


def _ledger_record_ids(project: Path) -> list[str]:
    """The migration ids recorded in the tracked ledger, in order."""
    path = project / ".kittify" / "migration-ledger.jsonl"
    return [json.loads(line)["id"] for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.is_file() else []


def _builtin_directive_stems() -> set[str]:
    """Every built-in directive's file stem — the set the shipped step seeded (#6549)."""
    return {path.name.split(".directive.yaml")[0] for path in built_in_dir(ArtifactKind.DIRECTIVE).glob("*.directive.yaml")}


def _upgrade_app() -> typer.Typer:
    app = typer.Typer(add_completion=False)
    app.command()(upgrade)
    return app


def _run_upgrade(project: Path) -> None:
    """The production entry point #6549's reproduction uses (``spec-kitty upgrade --yes``)."""
    with contextlib.chdir(project):
        result = CliRunner().invoke(_upgrade_app(), ["--yes", "--no-worktrees"], catch_exceptions=False)
    assert result.exit_code == 0, result.output


def test_a_second_upgrade_changes_nothing_for_a_fold_crossing_project(tmp_path: Path) -> None:
    """FR-001: the first upgrade settles the activation surfaces; a second one leaves them alone.

    This is #6549's own reproduction, replayed through the CLI (``upgrade --yes``): pass 1
    applies the fold, the ledger move and the promotion, and pass 2 must not write the
    whole-kind directive list into ``config.yaml``, re-run an activation migration, or
    commit a change to an activation surface.

    The claim is deliberately about the activation contract, not about every byte: a bare
    fixture (no agent surface for run 1 to find) lets the *session-presence* refresh land
    on the second run, which is unrelated to #6549 and is not asserted either way here.
    """
    project = _fold_crossing_project(tmp_path)

    _run_upgrade(project)
    after_first = _snapshot(project)

    # Positive control for the assertion below: the run really did produce a folded
    # project with an activation ledger, so "no config copy" is a visible state.
    assert (project / _ACTIVATION_LEDGER).is_file(), "the first upgrade did not write the activation ledger"
    assert not _config_activation_keys(project), f"the first upgrade left an activation key in config.yaml: {_config_activation_keys(project)}"
    assert SELECTED_STEM in (project / _ACTIVATION_LEDGER).read_text(encoding="utf-8"), "the interview selection was not promoted into the ledger"

    head_after_first = _git(project, "rev-parse", "HEAD").strip()
    records_after_first = len(_ledger_record_ids(project))

    _run_upgrade(project)

    # The activation surfaces — the ones #6549 corrupts — are byte-identical.
    after_second = _snapshot(project)
    for surface in (_CONFIG, Path(".kittify") / "charter" / "charter.yaml", _ACTIVATION_LEDGER):
        assert after_second.get(str(surface)) == after_first.get(str(surface)), f"a second upgrade rewrote {surface} (#6549)"
    assert not _config_activation_keys(project), f"a second upgrade wrote an activation copy back into config.yaml: {_config_activation_keys(project)}"

    # No activation migration ran again, and no commit touched the activation surface.
    # (A bare fixture without an agent surface lets the session-presence refresh land on
    # the second run; that write is unrelated to activation and is deliberately not
    # claimed as convergent here — see the module docstring.)
    replayed = [record for record in _ledger_record_ids(project)[records_after_first:] if record in ACTIVATION_MIGRATION_IDS]
    assert replayed == [], f"a second upgrade re-applied an activation migration: {replayed}"

    touched = _git(project, "diff", "--name-only", f"{head_after_first}..HEAD").split()
    assert ".kittify/config.yaml" not in touched, "a second upgrade committed a change to config.yaml (#6549)"
    assert not any(path.startswith(".kittify/charter/") for path in touched), f"a second upgrade committed a change to the charter surfaces: {touched}"


def test_the_registered_promotion_is_a_no_op_after_the_fold(tmp_path: Path) -> None:
    """FR-002 + FR-004: the fold empties the surface the shipped step read; the registry
    answers "not needed", while the shipped class itself still reports "needed".

    The second half is the control that keeps the first half non-vacuous: ``detect() is
    False`` means the substitute is registered, not that the probe cannot see the state
    the shipped step would have called promotable.
    """
    project = _fold_crossing_project(tmp_path)
    fold = ConsolidateCharterBundleMigration()
    assert fold.detect(project) is True, "the fixture does not straddle the fold"
    assert fold.apply(project).success
    assert not _config_activation_keys(project), "the fold did not relocate the activation keys off config.yaml"

    registered = MigrationRegistry.get_all()
    by_id = {migration.migration_id: migration for migration in registered}
    assert SHIPPED_ID in by_id, f"{SHIPPED_ID} is no longer registered"
    substitute = by_id[SHIPPED_ID]
    assert isinstance(substitute, SupersededMigration), f"{SHIPPED_ID} is registered as {type(substitute).__name__}, not a superseded no-op"

    before = _snapshot(project)
    assert substitute.detect(project) is False, f"{SHIPPED_ID} re-selects on a post-fold project — it would write the stale copy back (#6549)"
    applied = substitute.apply(project)
    assert applied.success, applied.errors
    assert _snapshot(project) == before, "the superseded substitute wrote to a post-fold project"

    # Control: the shipped class still answers True on the same fixture, so the False
    # above comes from the registry's substitution and not from a blind probe.
    assert UnifyCharterActivationMigration().detect(project) is True, (
        "the shipped class no longer detects the post-fold state — the registry assertion above is now vacuous"
    )


def test_dropping_the_supersession_entry_reintroduces_the_config_copy(tmp_path: Path) -> None:
    """FR-003: the supersession entry, not the successor, is what stops the re-fire.

    Without the entry, ``auto_discover_migrations`` registers the shipped class again
    and the second upgrade writes every built-in directive into ``config.yaml`` — the
    exact #6549 symptom, on the same fixture the two assertions above call converged.
    """
    saved = dict(SUPERSEDED_MIGRATIONS)
    SUPERSEDED_MIGRATIONS.pop(SHIPPED_ID, None)
    try:
        MigrationRegistry.clear()
        auto_discover_migrations()
        by_id = {migration.migration_id: migration for migration in MigrationRegistry.get_all()}
        shipped_again = by_id[SHIPPED_ID]
        assert not isinstance(shipped_again, SupersededMigration), "dropping the entry did not re-register the shipped class"
        # ``auto_discover_migrations`` reloads the module, so the registered class is not
        # the same object as this module's import; assert its identity by name and
        # behaviour instead.
        assert type(shipped_again).__name__ == "UnifyCharterActivationMigration"

        project = _fold_crossing_project(tmp_path)
        _run_upgrade(project)
        assert not _config_activation_keys(project), "the first upgrade left an activation key in config.yaml"

        _run_upgrade(project)

        written = _config_activation_keys(project)
        assert "activated_directives" in written, "the defect did not reappear without the supersession entry — this probe cannot see #6549"
        assert set(written["activated_directives"]) == _builtin_directive_stems(), (
            "the re-fired step did not write the whole built-in directive set, so this bite proof is not #6549's symptom"
        )
    finally:
        SUPERSEDED_MIGRATIONS.clear()
        SUPERSEDED_MIGRATIONS.update(saved)
