"""#6954 — three upgrade migrations and the operator's home.

#6551 was reported (and, in unmerged PR #6946, fixed) for the two legacy mission
migrations that ask :func:`~specify_cli.upgrade.compat.uses_centralized_runtime`
whether the project uses the centralized runtime. Three further migrations read the
operator's home **directly**, not through that predicate, and the #6551 report did not
measure them:

* ``m_2_1_3_restore_prompt_commands._get_runtime_command_templates_dir()``
* ``m_2_1_4_enforce_command_file_state._get_runtime_command_templates_dir()``
* ``m_3_1_2_globalize_commands._SafeGlobalizeCommandsBase`` (superseded by
  ``m_4_0_0rc8_stamp_globalize_commands``)

This module measures all three at the **real** ``upgrade`` command (the same
``typer.Typer`` test app + ``CliRunner`` harness as ``test_upgrade_integration.py``),
under a ``SPEC_KITTY_HOME`` that was never bootstrapped — the state a second machine or
a fresh CI runner is in when ``upgrade`` is the first spec-kitty command there.

Why the fixture seeds ``skipped`` records
-----------------------------------------
Ledger-diff re-evaluates a ``skipped`` record on every run, while ``success`` settles a
migration (``MigrationRegistry.get_applicable``; ADR
``docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md`` §3). Measured on a converged
project, all three of the migrations above carry ``success``, so the ledger never calls
``detect()`` on them again and a converged fixture cannot measure them at all. The
fixture therefore seeds exactly these three as ``skipped`` — the only shape in which the
behaviour under an empty home is reachable — and asserts the resulting record.

The two command-file migrations are pinned, not changed: their template resolution asks
the packaged doctrine tree first and reaches the home only as a last-resort fallback, so
a working install never consults it. ``3.1.2`` is different: its shipped implementation decides *keep* versus
*remove* from ``~/.kittify/missions`` and from ``Path.home()/<agent_root>/<subdir>``, so
the same commit can take two paths on two machines. Its project-stamped successor
carries the repair while the shipped module stays byte-frozen.
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

#: The three migrations #6954 names, in ledger-record form.
TARGET_MIGRATIONS = (
    "2.1.3_restore_prompt_commands",
    "2.1.4_enforce_command_file_state",
    "3.1.2_globalize_commands",
)

#: Migration ids that decide whether to delete a project-local command file. The
#: ``3.2.0a4`` shape is the residue-safe sibling of ``3.1.2`` and shares the base class,
#: so it must be re-evaluated too for the removal to be reachable.
GLOBALIZATION_MIGRATIONS = ("3.1.2_globalize_commands", "3.2.0a4_safe_globalize_commands")
GLOBALIZATION_SUCCESSOR = "4.0.0rc8_stamp_globalize_commands"

_COMMAND_FILE = "spec-kitty.specify.md"


def _marker() -> str:
    return f"<!-- spec-kitty-command-version: {current_cli_version()} -->"


def _marked_command_file() -> str:
    """Return a project-local command file that the migration accepts as generated."""
    return f"{_marker()}\n\n# /spec-kitty.specify\n\nBody rendered by the CLI.\n"


def _unmarked_command_file() -> str:
    """Return a project-local command file with no version marker (user-authored)."""
    return "# my own /spec-kitty.specify\n\nHand-written by the operator.\n"


def _seed_ledger(root: Path, *, skipped: tuple[str, ...]) -> None:
    """Seed a converged ledger, leaving exactly *skipped* re-evaluable."""
    auto_discover_migrations()
    ledger = MigrationLedger(root)
    for migration in MigrationRegistry.get_all():
        result = "skipped" if migration.migration_id in skipped else "success"
        ledger.append(build_record(migration, result))


def _default_skipped() -> tuple[str, ...]:
    """Leave the targets, sibling and successor re-evaluable.

    The successor's own ``success`` settles it now that its predecessor is superseded by it
    (#7429), so it is seeded ``skipped`` to stay selected rather than relying on the
    predecessor's ``skipped``.
    """
    return tuple(dict.fromkeys((*TARGET_MIGRATIONS, *GLOBALIZATION_MIGRATIONS, GLOBALIZATION_SUCCESSOR)))


def _write_metadata(root: Path, *, version: str | None) -> None:
    kittify = root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    if version is not None:
        (kittify / "metadata.yaml").write_text(_METADATA_YAML.format(version=version), encoding="utf-8")


def _make_project(
    root: Path,
    *,
    version: str | None,
    command_file: str | None = None,
    skipped: tuple[str, ...] | None = None,
) -> Path:
    """A minimal but real git-backed project with a converged ledger."""
    root.mkdir(parents=True, exist_ok=True)
    _write_metadata(root, version=version)
    _seed_ledger(root, skipped=skipped if skipped is not None else _default_skipped())
    if command_file is not None:
        agent_dir = root / ".claude" / "commands"
        agent_dir.mkdir(parents=True)
        (agent_dir / _COMMAND_FILE).write_text(command_file, encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True)
    return root


def _run_upgrade(cwd: Path):
    with contextlib.chdir(cwd):
        return _runner.invoke(_test_app, ["--project", "--yes", "--no-worktrees"], catch_exceptions=False)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


def _head(root: Path) -> str:
    return _git(root, "rev-parse", "HEAD")


def _porcelain(root: Path) -> list[str]:
    return [line for line in _git(root, "status", "--porcelain").splitlines() if line]


def _changed_paths(root: Path, base: str) -> list[str]:
    """Return the ``status<TAB>path`` rows between *base* and HEAD."""
    return [line for line in _git(root, "diff", "--name-status", base, "HEAD").splitlines() if line]


def _ledger_results(root: Path) -> dict[str, str]:
    return {record.id: record.result for record in MigrationLedger(root).read_all()}


def _bootstrap(home: Path) -> None:
    """Mark *home* bootstrapped and give it a populated mission tree (a user home)."""
    (home / "cache").mkdir(parents=True, exist_ok=True)
    (home / "cache" / "version.lock").write_text(current_cli_version(), encoding="utf-8")
    mission = home / "missions" / "software-dev"
    mission.mkdir(parents=True, exist_ok=True)
    (mission / "mission.yaml").write_text("mission:\n  key: software-dev\n", encoding="utf-8")


def _assert_empty_home(home: Path) -> None:
    """Assert the fixture really is an un-bootstrapped home."""
    assert not (home / "cache" / "version.lock").exists(), "fixture must not bootstrap the home"
    assert not (home / "missions").exists(), "fixture must not ship a mission tree"


def _unbootstrap(home: Path) -> None:
    """Return *home* to never-bootstrapped: a second machine, or a fresh CI runner."""
    (home / "cache" / "version.lock").unlink(missing_ok=True)
    assert not (home / "cache" / "version.lock").exists(), "fixture must not leave the home bootstrapped"


@pytest.mark.usefixtures("canonical_home")  # R1b (#3121): the ONE owner of SPEC_KITTY_HOME
def test_dated_project_removes_marked_command_file_under_an_empty_home(tmp_path: Path) -> None:
    """#6954, at the real entry point: a dated project's answer must not need the home.

    The project is stamped at the running CLI version — the CLI that globalizes commands
    — and carries one generated (version-marked) project-local command file. A machine
    whose home was never bootstrapped must still recognize that the file is ours and
    obsolete, remove it, and auto-commit the removal.

    Before the fix ``_classify()`` asked ``_global_runtime_present()`` first, which
    answers "no" on this machine, so the file was kept and the ledger recorded
    ``success`` — freezing the wrong decision for good.
    """
    home = tmp_path / "home"
    project = _make_project(tmp_path / "proj", version=current_cli_version(), command_file=_marked_command_file())
    target = project / ".claude" / "commands" / _COMMAND_FILE

    _assert_empty_home(home)
    base = _head(project)
    before = _ledger_results(project)
    assert target.is_file(), "fixture must carry the generated project-local command file"
    assert [before[migration_id] for migration_id in GLOBALIZATION_MIGRATIONS] == [
        "skipped",
        "skipped",
    ]

    result = _run_upgrade(project)

    assert result.exit_code == 0, result.output
    assert not target.exists(), (
        "the dated project's generated project-local command file must be removed even though this machine's home was never bootstrapped (#6954)"
    )
    assert _porcelain(project) == [], "the removal must be auto-committed, not left dirty"
    assert _head(project) != base, "the auto-commit must carry the removal"
    assert any(row.split("\t")[-1].endswith(_COMMAND_FILE) for row in _changed_paths(project, base)), f"removal of {_COMMAND_FILE} must appear in the auto-commit"
    after = _ledger_results(project)
    assert after[GLOBALIZATION_SUCCESSOR] == "success"
    assert after["3.1.2_globalize_commands"] == "skipped", "the superseded predecessor stays a recorded no-op"


@pytest.mark.usefixtures("canonical_home")  # R1b (#3121): the ONE owner of SPEC_KITTY_HOME
def test_same_commit_leaves_the_same_tracked_state_in_both_homes(tmp_path: Path) -> None:
    """Same project, same commit, two machines: one outcome (tactic non-vacuity).

    Two copies of one fixture shape are upgraded — one with an un-bootstrapped home, one
    with a bootstrapped home carrying a populated mission tree. Both must remove the
    generated file and record the same ledger result; the set of paths they change must
    match, so the answer is a function of the project and not of the operator.

    The bootstrapped arm is also the positive control for
    ``test_dated_project_removes_marked_command_file_under_an_empty_home``: removal is
    observable on this fixture shape, so an empty-home "nothing was removed" is a real
    difference and not a probe that cannot see anything.
    """
    home = tmp_path / "home"
    empty_arm = _make_project(tmp_path / "empty-arm", version=current_cli_version(), command_file=_marked_command_file())
    bootstrapped_arm = _make_project(
        tmp_path / "bootstrapped-arm",
        version=current_cli_version(),
        command_file=_marked_command_file(),
    )

    empty_base = _head(empty_arm)
    empty_result = _run_upgrade(empty_arm)

    _bootstrap(home)
    bootstrapped_base = _head(bootstrapped_arm)
    bootstrapped_result = _run_upgrade(bootstrapped_arm)

    assert empty_result.exit_code == 0, empty_result.output
    assert bootstrapped_result.exit_code == 0, bootstrapped_result.output

    empty_file = empty_arm / ".claude" / "commands" / _COMMAND_FILE
    bootstrapped_file = bootstrapped_arm / ".claude" / "commands" / _COMMAND_FILE
    assert not bootstrapped_file.exists(), "the bootstrapped arm must remove the generated file"
    assert not empty_file.exists(), "the empty-home arm must reach the same decision"

    assert _porcelain(empty_arm) == []
    assert _porcelain(bootstrapped_arm) == []
    assert _ledger_results(empty_arm) == _ledger_results(bootstrapped_arm)
    assert _changed_paths(empty_arm, empty_base) == _changed_paths(bootstrapped_arm, bootstrapped_base), "the two homes must change the same project paths"


@pytest.mark.usefixtures("canonical_home")  # R1b (#3121): the ONE owner of SPEC_KITTY_HOME
def test_undated_project_keeps_the_file_in_both_homes(tmp_path: Path) -> None:
    """A project with no usable stamp keeps the historical home-driven answer.

    This is the legacy-repair shape: no ``metadata.yaml``, so the project cannot be
    dated. The home check must still decide, and on both machines it must keep the
    generated file (no global replacement is visible), so the fix does not turn the
    legacy path into a removal.
    """
    home = tmp_path / "home"
    project = _make_project(tmp_path / "proj", version=None, command_file=_marked_command_file())
    target = project / ".claude" / "commands" / _COMMAND_FILE

    _assert_empty_home(home)
    result = _run_upgrade(project)

    assert result.exit_code == 0, result.output
    assert target.is_file(), "an undated project must not lose its command file"


@pytest.mark.usefixtures("canonical_home")  # R1b (#3121): the ONE owner of SPEC_KITTY_HOME
def test_unmarked_command_file_is_held_in_both_homes(tmp_path: Path) -> None:
    """A file with no version marker is user-authored and is never removed (NFR-003).

    The stamped project would otherwise be past the globalization boundary; the marker
    check must keep its precedence, so the user-customisation guarantee survives the fix.
    """
    home = tmp_path / "home"
    project = _make_project(tmp_path / "proj", version=current_cli_version(), command_file=_unmarked_command_file())
    target = project / ".claude" / "commands" / _COMMAND_FILE

    empty_result = _run_upgrade(project)

    assert empty_result.exit_code == 0, empty_result.output
    assert target.is_file(), "a file without a version marker must be preserved"

    _bootstrap(home)
    bootstrapped_result = _run_upgrade(project)

    assert bootstrapped_result.exit_code == 0, bootstrapped_result.output
    assert target.is_file(), "the hold rule must not depend on which machine runs it"


@pytest.mark.usefixtures("canonical_home")  # R1b (#3121): the ONE owner of SPEC_KITTY_HOME
@pytest.mark.parametrize(
    "module_name",
    ["m_2_1_3_restore_prompt_commands", "m_2_1_4_enforce_command_file_state"],
)
def test_template_source_is_home_independent(module_name: str, tmp_path: Path) -> None:
    """The two command-file migrations resolve packaged templates, not the home.

    Grounding (``research.md``): the shared resolver's last tier is
    ``~/.kittify/missions/<type>/command-templates``, but the packaged doctrine tree wins
    first on any working install. Pin that: an empty home and a bootstrapped home must
    resolve the same directory, and it must not be below the home at all.
    """
    import importlib

    home = tmp_path / "home"
    module = importlib.import_module(f"specify_cli.upgrade.migrations.{module_name}")

    _assert_empty_home(home)
    empty_home_source = module._get_runtime_command_templates_dir()
    assert empty_home_source is not None, "the packaged templates must resolve without a home"
    assert empty_home_source.is_dir()
    assert home not in empty_home_source.parents, f"{module_name} resolved its templates from the operator's home: {empty_home_source}"

    _bootstrap(home)
    bootstrapped_source = module._get_runtime_command_templates_dir()
    assert bootstrapped_source == empty_home_source, "bootstrapping the home must not change the template source"


@pytest.mark.usefixtures("canonical_home")  # R1b (#3121): the ONE owner of SPEC_KITTY_HOME
def test_converged_upgrade_does_not_touch_a_re_evaluated_record(tmp_path: Path) -> None:
    """The issue's converged-project shape, scoped to the three migrations.

    A converged project carries ``success`` for these three, so the ledger settles them
    and an empty-home re-run must not produce anything attributable to them: no
    project-local command file appears or disappears, and their records stay as they are.

    The ``0.6.7_ensure_missions`` / ``0.12.0_documentation_mission`` half of the converged
    assertion belongs to the predicate in ``compat.py`` (issue #6551, unmerged PR #6946)
    and is deliberately not asserted here (C-001).
    """
    home = tmp_path / "home"
    project = _make_project(tmp_path / "proj", version=current_cli_version(), skipped=())
    _bootstrap(home)

    assert _run_upgrade(project).exit_code == 0
    converged_head = _head(project)
    assert _run_upgrade(project).exit_code == 0
    assert _head(project) == converged_head, "the second converged pass must change nothing"

    _unbootstrap(home)

    result = _run_upgrade(project)

    assert result.exit_code == 0, result.output
    changed = _changed_paths(project, converged_head)
    assert not [row for row in changed if _COMMAND_FILE in row], "no project-local command file may appear or disappear on a settled record"
    assert not [row for row in changed if row.split("\t")[-1] == ".kittify/missions"], "the three migrations must not copy missions into the project"
    after = _ledger_results(project)
    assert all(after[migration_id] == "success" for migration_id in TARGET_MIGRATIONS)
