"""Finding-1 remediation: fresh init seeds the migration ledger (NFR-002).

Mission ``migration-ledger-01M55SFA`` closeout finding 1.

Under ledger-diff selection (ADR 2026-10-17-1 §3) the two-partition ledger is
the "already applied" authority. A fresh ``spec-kitty init`` used to write NO
ledger, so the first ``spec-kitty upgrade`` diffed an empty ledger against the
full declared set and re-selected every historical migration. Two of them
disagree over ``mission_type_activations`` (the rc35 activation migration adds
it to ``config.yaml``; the charter-bundle fold moves it into ``charter.yaml``),
so the first upgrade mutated config, and -- because the activation migration
records a non-settling ``skipped`` while the fold strips the key it inspects --
the *second* upgrade re-selected the activation migration, whose ``detect()``
had flipped True, and re-applied it: a config delta, a ledger delta and an
auto-commit on an already-current project.

The fix seeds the ledger at init, so the first upgrade SELECTS NOTHING and the
co-selection that triggers the drift never happens.

These tests drive a REAL ``spec-kitty init`` (through the same harness as
``tests/specify_cli/cli/commands/test_init_provisioning.py``) and then observe
selection / upgrade idempotency. Both FAIL on the pre-fix HEAD (no init seed).
"""

from __future__ import annotations

import io
import shutil
import subprocess
from pathlib import Path

import pytest
from rich.console import Console
from typer import Typer
from typer.testing import CliRunner

from specify_cli.cli.commands import init as init_module
from specify_cli.cli.commands.init import register_init_command
from specify_cli.template.manager import TemplateCopyResult

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_BUILT_IN = Path(__file__).resolve().parents[2] / "packs" / "built-in"

_MISSION_TYPE_MIGRATION_IDS = (
    "3.2.0rc35_activate_builtin_mission_types",
    "consolidate_charter_bundle_fold",
)


def _copied_pack(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A tmp copy of ``packs/built-in`` resolved through ``SPEC_KITTY_PACKS_ROOT``."""
    packs_root = tmp_path / "packs-root"
    shutil.copytree(_BUILT_IN, packs_root / "built-in")
    monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(packs_root))
    return packs_root / "built-in"


def _fake_copy_package(project_path: Path) -> TemplateCopyResult:
    kittify = project_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    return TemplateCopyResult(kittify / "templates" / "command-templates", templates_created=True)


def _patch_common_init_seams(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)


@pytest.fixture()
def cli_app() -> tuple[Typer, Console]:
    console = Console(file=io.StringIO(), force_terminal=False)
    app = Typer()
    register_init_command(
        app,
        console=console,
        show_banner=lambda: None,
        activate_mission=lambda proj, mtype, mdisplay, _con: mdisplay,
        ensure_executable_scripts=lambda path, tracker=None: None,
    )
    return app, console


def _init_fresh_project(app: Typer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str) -> Path:
    monkeypatch.chdir(tmp_path)
    _patch_common_init_seams(monkeypatch)
    _copied_pack(tmp_path, monkeypatch)
    result = CliRunner().invoke(app, ["init", name, "--ai", "claude", "--non-interactive"], catch_exceptions=True)
    assert result.exit_code == 0, result.output
    return tmp_path / name


def test_fresh_init_seeds_ledger_so_no_migration_is_selected(cli_app: tuple[Typer, Console], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A freshly initialized project selects NO migrations on its first upgrade.

    This is the precondition the drift needs: on the pre-fix HEAD the empty
    ledger makes ``get_applicable`` return the full declared set -- including
    both ``mission_type_activations`` migrations whose co-run is the defect.
    After the init seed, neither is selected.

    The honest invariant: no TRACKED-effect migration is selected (those are
    seeded unconditionally and their effect travels with the commit). Only a
    clone-local migration whose local effect is not yet present on this checkout
    may remain pending (it re-applies idempotently, and a pulled clone must also
    re-apply it, #6233) -- so the conflicting charter pair, both tracked, is gone.
    """
    from specify_cli.upgrade.migrations import auto_discover_migrations
    from specify_cli.upgrade.registry import MigrationRegistry

    project = _init_fresh_project(cli_app[0], tmp_path, monkeypatch, "fresh-select")

    auto_discover_migrations()
    selected = list(MigrationRegistry.get_applicable("0.0.0", "99.0.0", project))
    selected_ids = {m.migration_id for m in selected}

    # The co-selected conflicting pair is what triggers finding-1; it must be gone.
    assert not (set(_MISSION_TYPE_MIGRATION_IDS) & selected_ids), f"conflicting mission_type_activations migrations still selected on a fresh init: {selected_ids}"
    # No tracked-effect migration may remain selected on a fresh init.
    leaked_tracked = {m.migration_id for m in selected if not bool(getattr(m, "clone_local_effect", False))}
    assert leaked_tracked == set(), f"fresh init left tracked-effect migrations selected (not a no-op): {sorted(leaked_tracked)}"

    # #6233 leak guard: a clone-local migration's record must NEVER land in the
    # tracked (committed) ledger -- that would travel to a pulled clone and
    # wrongly suppress the clone's re-apply of the clone-local effect.
    from specify_cli.upgrade.ledger import MigrationLedger

    ledger = MigrationLedger(project)
    clone_local_ids = {m.migration_id for m in MigrationRegistry.get_all() if bool(getattr(m, "clone_local_effect", False))}
    tracked_ids = {r.id for r in ledger.read_tracked()}
    assert not (tracked_ids & clone_local_ids), f"clone-local migration leaked into the tracked ledger (#6233): {tracked_ids & clone_local_ids}"


def test_fresh_init_second_upgrade_is_pure_no_op(cli_app: tuple[Typer, Console], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The exact finding-1 repro: fresh init + two ``upgrade --yes`` runs; the
    second must not change ``config.yaml``, the ledger, or create a commit."""
    import typer
    from specify_cli.cli.commands.upgrade import upgrade

    project = _init_fresh_project(cli_app[0], tmp_path, monkeypatch, "fresh-upgrade")

    # Fresh init does not `git init`; upgrade's auto-commit needs a repo.
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=project, check=True)
    subprocess.run(["git", "add", "-A"], cwd=project, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=project, check=True)

    upgrade_app = typer.Typer(add_completion=False)
    upgrade_app.command()(upgrade)
    runner = CliRunner()

    def _run_upgrade() -> None:
        import contextlib

        with contextlib.chdir(project):
            res = runner.invoke(upgrade_app, ["--yes", "--no-worktrees"], catch_exceptions=True)
        assert res.exit_code == 0, res.output

    config_path = project / ".kittify" / "config.yaml"
    tracked_ledger = project / ".kittify" / "migration-ledger.jsonl"

    def _commit_count() -> int:
        out = subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=project, check=True, capture_output=True, text=True)
        return int(out.stdout.strip())

    _run_upgrade()
    config_after_first = config_path.read_bytes()
    ledger_after_first = tracked_ledger.read_bytes() if tracked_ledger.exists() else b""
    commits_after_first = _commit_count()

    _run_upgrade()
    assert config_path.read_bytes() == config_after_first, "second upgrade mutated config.yaml (re-application)"
    ledger_after_second = tracked_ledger.read_bytes() if tracked_ledger.exists() else b""
    assert ledger_after_second == ledger_after_first, "second upgrade appended to the ledger (re-application)"
    assert _commit_count() == commits_after_first, "second upgrade created an auto-commit on an already-current project"
