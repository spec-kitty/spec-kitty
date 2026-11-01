"""#6551 — a converged project's upgrade is a no-op on a machine with no ``~/.kittify``.

The defect: ``uses_centralized_runtime`` gated its "this project uses the 2.x
centralized runtime" answer on ``~/.kittify/cache/version.lock`` existing for the
*operator*, not on the project's own ``metadata.yaml`` stamp. ``upgrade``
deliberately does not bootstrap the home before running migrations (#3900), so on
a machine where ``upgrade`` is the first spec-kitty command the two legacy mission
migrations answered ``detect() is True`` for a 4.x project, copied the packaged
missions in, let ``2.0.6_consistency_sweep`` reclassify them as overrides, and
auto-committed 23 files.

This module drives the **real** ``upgrade`` command (the same ``typer.Typer`` test
app + ``CliRunner`` harness as ``test_upgrade_integration.py``) against a project
in exactly the converged state the issue measured: ``metadata.yaml`` at the
running CLI version and the two legacy mission migrations recorded ``skipped`` in
the ledger — which is what a first upgrade under a bootstrapped home leaves
behind, and which ledger-diff re-evaluates on every later run.

The positive control lives beside the regression on the **same fixture shape**: a
project stamped ``1.2.0`` under the same empty home must still receive the repair
(``.kittify/missions/software-dev/mission.yaml`` appears, the ledger gains a
``success`` record). Without it, "nothing changed" could be a probe that cannot
see anything (tactic ``acceptance-criteria-non-vacuity``).
"""

from __future__ import annotations

import contextlib
import subprocess
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.cli.commands.upgrade import upgrade
from specify_cli.upgrade.ledger import MigrationLedger, build_record, current_cli_version
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.registry import MigrationRegistry

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_test_app = typer.Typer(add_completion=False)
_test_app.command()(upgrade)
_runner = CliRunner()

_METADATA_YAML = (
    "spec_kitty:\n"
    "  version: '{version}'\n"
    "  initialized_at: '2026-01-01T00:00:00'\n"
    "  schema_version: 3\n"
    "environment:\n"
    "  python_version: '3.12'\n"
    "  platform: linux\n"
    "  platform_version: ''\n"
)

#: The two migrations over user-global state whose ``detect()`` decides whether the
#: packaged missions are copied into the project (the 22-file override commit).
LEGACY_MISSION_MIGRATIONS = ("0.6.7_ensure_missions", "0.12.0_documentation_mission")


def _seed_converged_ledger(root: Path) -> None:
    """Seed the ledger a converged project carries.

    Every declared migration gets a ``success`` record — except the two legacy
    mission migrations, which get a ``skipped`` record. That is the state the
    issue measured under user A (``0.6.7_ensure_missions = skipped``,
    ``0.12.0_documentation_mission = skipped``), and unlike ``success`` a
    ``skipped`` record does not settle a migration, so ledger-diff re-selects
    both on every later run (``registry.get_applicable``).
    """
    auto_discover_migrations()
    ledger = MigrationLedger(root)
    for migration in MigrationRegistry.get_all():
        if migration.migration_id in LEGACY_MISSION_MIGRATIONS:
            ledger.append(build_record(migration, "skipped"))
        else:
            ledger.append(build_record(migration, "success"))


def _init_project(root: Path, *, version: str) -> None:
    """A minimal, real git-backed project already recorded as up to date."""
    root.mkdir(parents=True, exist_ok=True)
    kittify = root / ".kittify"
    kittify.mkdir()
    (kittify / "metadata.yaml").write_text(_METADATA_YAML.format(version=version), encoding="utf-8")
    _seed_converged_ledger(root)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True)


def _run_upgrade(args: list[str], cwd: Path):
    """Invoke the real ``upgrade`` command from *cwd* (mirrors the sibling harness)."""
    with contextlib.chdir(cwd):
        return _runner.invoke(_test_app, args, catch_exceptions=False)


def _head(root: Path) -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


def _porcelain(root: Path) -> list[str]:
    return [line for line in subprocess.run(["git", "status", "--porcelain"], cwd=root, check=True, capture_output=True, text=True).stdout.splitlines() if line]


def _ledger_results(root: Path) -> dict[str, str]:
    return {record.id: record.result for record in MigrationLedger(root).read_all()}


def _bootstrap(home: Path) -> None:
    """Mark *home* as bootstrapped, the way any non-upgrade command does."""
    (home / "cache").mkdir(parents=True, exist_ok=True)
    (home / "cache" / "version.lock").write_text(current_cli_version(), encoding="utf-8")


def _unbootstrap(home: Path) -> None:
    """Return *home* to never-bootstrapped: a second machine, or a fresh CI runner."""
    lock = home / "cache" / "version.lock"
    lock.unlink(missing_ok=True)
    assert not lock.exists(), "fixture must not leave the home bootstrapped"


@pytest.mark.usefixtures("canonical_home")  # R1b (#3121): the ONE owner of SPEC_KITTY_HOME
def test_converged_upgrade_makes_no_tracked_change_without_a_bootstrapped_home(tmp_path: Path) -> None:
    """#6551: the reported defect, at the real entry point — user A, then user B.

    The fixture first converges the project the way user A did (a bootstrapped
    home, then a second pass that commits nothing), then hands the same commit to
    "user B": the same project, an empty ``SPEC_KITTY_HOME``, ``upgrade`` as the
    first spec-kitty command there.

    Before the fix this second run copied the packaged missions into the project
    (they exist after the run and the upgrade auto-commits them), because
    ``uses_centralized_runtime`` answered from the operator's home instead of the
    project's 4.x stamp. After the fix both migrations skip and the head does not
    move.
    """
    home = tmp_path / "home"
    project = tmp_path / "proj"
    _init_project(project, version=current_cli_version())

    # Assumption check: the fixture reproduces the issue's converged shape.
    before = _ledger_results(project)
    assert [before[migration_id] for migration_id in LEGACY_MISSION_MIGRATIONS] == ["skipped", "skipped"]
    assert not (project / ".kittify" / "missions").exists()
    assert not (project / ".kittify" / "overrides").exists()

    # user A: a machine whose home has been bootstrapped. The home itself is
    # pinned by the canonical owner fixture (`canonical_home`), never here -- the
    # R1a home-pin ratchet treats a local `SPEC_KITTY_HOME` pin as a new owner.
    _bootstrap(home)

    assert _run_upgrade(["--project", "--yes", "--no-worktrees"], cwd=project).exit_code == 0
    converged_head = _head(project)
    assert _run_upgrade(["--project", "--yes", "--no-worktrees"], cwd=project).exit_code == 0
    assert _head(project) == converged_head, "user A's second pass must already be a no-op"

    # user B: the same commit, a fresh machine, a home that was never bootstrapped.
    _unbootstrap(home)

    result = _run_upgrade(["--project", "--yes", "--no-worktrees"], cwd=project)

    assert result.exit_code == 0, result.output
    assert "Upgrade complete" in result.output, result.output

    # The regression itself. The upgrade auto-commits whatever it touched, so a
    # clean ``git status`` alone would miss the defect: the head must not move.
    assert _porcelain(project) == []
    assert _head(project) == converged_head
    assert not (project / ".kittify" / "missions").exists()
    assert not (project / ".kittify" / "overrides").exists()

    # Same-fixture positive control (a): the absence probe can see the records it
    # claims are unchanged, so "no change" is not "the probe saw nothing".
    after = _ledger_results(project)
    assert [after[migration_id] for migration_id in LEGACY_MISSION_MIGRATIONS] == ["skipped", "skipped"]
    assert set(LEGACY_MISSION_MIGRATIONS) <= set(after)


@pytest.mark.usefixtures("canonical_home")  # R1b (#3121): the ONE owner of SPEC_KITTY_HOME
def test_pre_two_x_project_under_the_same_empty_home_still_repairs(tmp_path: Path) -> None:
    """Same fixture shape, opposite outcome — the positive control for the regression.

    A project stamped *below* the ``2.0.0`` boundary the predicate reads is not a
    centralized-runtime project, so the legacy mission migration must still run:
    the missions land in the project and the ledger records a ``success``. If this
    test cannot observe a change, the absence assertion in the regression above
    proves nothing (tactic ``acceptance-criteria-non-vacuity``).

    The ``schema_version: 3`` stamp is carried by the shared fixture so the
    *unrelated* admission gate admits the run; it is not what the predicate under
    test reads. ``1.9.0`` is the discriminator.
    """
    project = tmp_path / "proj"
    assert not (tmp_path / "home" / "cache" / "version.lock").exists(), "the home must not be bootstrapped"
    _init_project(project, version="1.9.0")

    result = _run_upgrade(["--project", "--yes", "--no-worktrees"], cwd=project)

    assert result.exit_code == 0, result.output
    assert (project / ".kittify" / "missions" / "software-dev" / "mission.yaml").exists()
    assert _ledger_results(project)["0.6.7_ensure_missions"] == "success"
