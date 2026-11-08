"""Every registered migration converges: a second run changes nothing (#7405, epic #3347).

Two checks, on representative fixture projects:

* **Per migration.** Each registered migration runs twice on its own copy of a
  fixture, the way the runner runs it (``detect()``, then ``can_apply()``, then
  ``apply()``, inside the upgrade-only legacy activation scope). The second run
  must leave the project byte-for-byte as the first run left it. The ledger is
  not consulted here on purpose: a clone-local record never travels, a failed or
  skipped record does not settle, and a structural reselection re-runs a recorded
  migration, so the ``detect()`` guard is what keeps a re-run safe (ADR
  ``2026-10-17-1``; C-003).
* **Per run.** ``MigrationRunner.upgrade`` runs twice; the second run applies
  nothing and changes nothing (#6549 is the defect class: a migration that is not
  needed on pass 1 and applied on pass 2).

A migration that does not converge is pinned, with a reason and a follow-up
issue, never fixed in its shipped module (DIRECTIVE_044): per migration on
:data:`NOT_CONVERGENT` (a strict ``xfail``), per run on
:data:`KNOWN_EXTRA_PASS` (the exact migrations the second run still applies; the
third run must then change nothing). Either pin fails once the migration starts
converging, so the entry is removed with the fix.

Neither check is vacuous: :func:`test_fixtures_exercise_the_apply_path` holds a
floor on how many migrations each fixture drives into ``apply()``, and checks that
``detect()`` writes nothing.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import stat
import subprocess
from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from specify_cli import __version__
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.migrations.base import BaseMigration, legacy_upgrade_scope
from specify_cli.upgrade.registry import MigrationRegistry
from specify_cli.upgrade.runner import MigrationRunner

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

#: Fixture name -> builder. Every builder makes a committed git repository.
FIXTURES = ("fresh_init", "legacy_2_1_0")

#: Git state a migration may legitimately write (clone-local effects); everything
#: else under ``.git/`` is object/ref storage the snapshot ignores.
_GIT_STATE = ("config", "info", "hooks")


def _registered() -> list[BaseMigration]:
    auto_discover_migrations()
    return sorted(MigrationRegistry.get_all(), key=lambda migration: migration.migration_id)


#: (fixture, migration_id) -> why a second run of the migration alone changes the
#: project, with its follow-up issue. Empty: every registered migration converges on
#: its own on every fixture.
NOT_CONVERGENT: Mapping[tuple[str, str], str] = {}

#: fixture -> {migration_id: why} for the migrations a second whole ``upgrade`` still
#: applies. Strict both ways: the second run must apply exactly these.
KNOWN_EXTRA_PASS: Mapping[str, Mapping[str, str]] = {
    "legacy_2_1_0": {
        "4.0.0rc8_stamp_globalize_commands": (
            "#7429: never settled (its predecessor is superseded and only records skipped, #6688), "
            "and its verdict reads the version stamp the run moves only after the loop: pass 1 keeps "
            "the generated .claude/commands files, pass 2 deletes all of them"
        ),
    },
}

#: fixture -> the fewest registered migrations whose first run must reach ``apply()``
#: (13 and 38 when this floor was set), so the per-migration check is never vacuous.
APPLY_PATH_FLOOR: Mapping[str, int] = {"fresh_init": 10, "legacy_2_1_0": 30}


def _git(project: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=project, check=True, capture_output=True, text=True).stdout


def _commit_all(project: Path, message: str) -> None:
    _git(project, "add", "-A")
    _git(project, "commit", "-q", "--allow-empty", "-m", message)


def _init_git(project: Path) -> None:
    project.mkdir(parents=True)
    _git(project, "init", "-q", "--template=", "-b", "work")
    _git(project, "config", "user.email", "convergence@example.com")
    _git(project, "config", "user.name", "Convergence")
    _git(project, "config", "commit.gpgsign", "false")


def _build_fresh_init(project: Path) -> None:
    """A project ``spec-kitty init`` just set up, committed."""
    from specify_cli import app as root_app

    _init_git(project)
    (project / "README.md").write_text("seed\n", encoding="utf-8")
    _commit_all(project, "seed")
    with contextlib.chdir(project):
        result = CliRunner().invoke(root_app, ["init", "--non-interactive", "--ai", "claude"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    _commit_all(project, "init")


_LEGACY_COMMAND = "<!-- spec-kitty-command-version: 2.1.0 -->\n# spec-kitty.implement\n"


def _build_legacy_2_1_0(project: Path) -> None:
    """A schema-less 2.1.0 project with no ledger, no charter, a mission and generated agent commands."""
    _init_git(project)
    files = {
        ".kittify/metadata.yaml": yaml.safe_dump({"spec_kitty": {"version": "2.1.0", "initialized_at": "2026-01-01T00:00:00"}}),
        ".kittify/config.yaml": yaml.safe_dump({"agents": {"available": ["claude", "codex"]}}),
        ".claude/commands/spec-kitty.implement.md": _LEGACY_COMMAND,
        ".gitignore": ".worktrees/\n.claude/\n",
        "kitty-specs/001-demo/meta.json": '{"mission_slug": "001-demo", "title": "Demo"}\n',
        "kitty-specs/001-demo/spec.md": "# Demo\n",
        "kitty-specs/001-demo/tasks/WP01-title.md": (
            "---\nwork_package_id: ''\nwp_code: 'WP01'\ntitle: WP01 Title\nlane: 'planned'\ndependencies: []\nsubtasks: []\n---\n\n# WP01\n"
        ),
        "src/app.py": "A = 1\n",
    }
    for rel, content in files.items():
        target = project / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    _commit_all(project, "legacy 2.1.0")


_BUILDERS = {"fresh_init": _build_fresh_init, "legacy_2_1_0": _build_legacy_2_1_0}


@pytest.fixture(scope="module")
def templates(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    root = tmp_path_factory.mktemp("convergence-templates")
    built: dict[str, Path] = {}
    for name in FIXTURES:
        project = root / name
        _BUILDERS[name](project)
        built[name] = project
    return built


#: Every path -> (kind, content): "f"/"x" (file, executable) with its bytes, "link" with its target, "dir".
Snapshot = dict[str, tuple[str, bytes]]


def snapshot(project: Path) -> Snapshot:
    """Every path in *project* with its kind and content; ``.git/`` object and ref storage excluded."""
    out: Snapshot = {}
    for dirpath, dirnames, filenames in os.walk(project, followlinks=False):
        here = Path(dirpath)
        rel_dir = here.relative_to(project).as_posix()
        if rel_dir == "." and ".git" in dirnames:
            dirnames.remove(".git")
            for entry in _GIT_STATE:
                _snapshot_git_entry(project, project / ".git" / entry, out)
        for name in dirnames:
            path = here / name
            if path.is_symlink():
                out[path.relative_to(project).as_posix()] = ("link", os.readlink(path).encode())
            else:
                out[path.relative_to(project).as_posix()] = ("dir", b"")
        for name in filenames:
            _snapshot_file(project, here / name, out)
    return out


def _snapshot_git_entry(project: Path, path: Path, out: Snapshot) -> None:
    if path.is_file():
        _snapshot_file(project, path, out)
    elif path.is_dir():
        for child in sorted(path.rglob("*")):
            if child.is_file():
                _snapshot_file(project, child, out)


def _snapshot_file(project: Path, path: Path, out: Snapshot) -> None:
    rel = path.relative_to(project).as_posix()
    if path.is_symlink():
        out[rel] = ("link", os.readlink(path).encode())
        return
    mode = "x" if path.stat().st_mode & stat.S_IXUSR else "f"
    out[rel] = (mode, path.read_bytes())


def _diff(before: Snapshot, after: Snapshot) -> list[str]:
    changed = sorted(set(before) ^ set(after) | {key for key in set(before) & set(after) if before[key] != after[key]})
    return [f"{'+' if key not in before else '-' if key not in after else '~'} {key}" for key in changed]


@pytest.fixture()
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A fresh HOME per case, so one migration's global write never feeds another's ``detect()``."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    for var in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME"):
        monkeypatch.setenv(var, str(home / var.lower()))
    yield home


def run_like_the_runner(migration: BaseMigration, project: Path) -> str:
    """One run of *migration* as the runner performs it; returns what happened, for the failure message."""
    with legacy_upgrade_scope(project):
        try:
            if not migration.detect(project):
                return "not needed"
            can_apply, reason = migration.can_apply(project)
            if not can_apply:
                return f"cannot apply ({reason})"
            result = migration.apply(project, dry_run=False)
        except Exception as exc:
            # The harness reports any outcome for the failure message; it never decides on it.
            return f"raised {type(exc).__name__}: {exc}"
    return "applied" if result.success else f"apply failed: {result.errors}"


def _cases() -> list[object]:
    cases: list[object] = []
    for fixture in FIXTURES:
        for migration in _registered():
            key = (fixture, migration.migration_id)
            marks = [pytest.mark.xfail(strict=True, reason=NOT_CONVERGENT[key])] if key in NOT_CONVERGENT else []
            cases.append(pytest.param(fixture, migration.migration_id, id=f"{fixture}-{migration.migration_id}", marks=marks))
    return cases


@pytest.mark.parametrize(("fixture", "migration_id"), _cases())
def test_second_run_of_a_migration_changes_nothing(
    fixture: str, migration_id: str, templates: dict[str, Path], tmp_path: Path, isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "project"
    shutil.copytree(templates[fixture], project, symlinks=True)
    monkeypatch.chdir(project)
    migration = next(m for m in _registered() if m.migration_id == migration_id)

    first = run_like_the_runner(migration, project)
    after_first = snapshot(project)
    second = run_like_the_runner(migration, project)
    after_second = snapshot(project)

    assert after_second == after_first, f"{migration_id} on {fixture}: first run {first!r}, second run {second!r}, second run changed:\n" + "\n".join(
        _diff(after_first, after_second)
    )


@pytest.mark.parametrize("fixture", FIXTURES)
def test_fixtures_exercise_the_apply_path(fixture: str, templates: dict[str, Path], tmp_path: Path, isolated_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "project"
    shutil.copytree(templates[fixture], project, symlinks=True)
    monkeypatch.chdir(project)
    before = snapshot(project)

    with legacy_upgrade_scope(project):
        selected = [migration.migration_id for migration in _registered() if migration.detect(project)]

    assert len(selected) >= APPLY_PATH_FLOOR[fixture], selected
    assert snapshot(project) == before, "detect() must not write"


def _older_lanes_project(tmp_path: Path) -> Path:
    """A project recorded at an older version with one live lane worktree (built in place: worktrees do not copy)."""
    from tests.integration.target_owned_fixtures import build_older_version_lanes_project

    return build_older_version_lanes_project(tmp_path / "lanes", topology="lanes", lanes=1).repo


@pytest.mark.parametrize("fixture", [*FIXTURES, "older_lanes"])
def test_second_upgrade_applies_and_changes_nothing(
    fixture: str, templates: dict[str, Path], tmp_path: Path, isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if fixture == "older_lanes":
        project = _older_lanes_project(tmp_path)
    else:
        project = tmp_path / "project"
        shutil.copytree(templates[fixture], project, symlinks=True)
    monkeypatch.chdir(project)
    known = KNOWN_EXTRA_PASS.get(fixture, {})

    first = MigrationRunner(project).upgrade(__version__)
    assert first.success, first.errors
    after_first = snapshot(project)
    second = MigrationRunner(project).upgrade(__version__)
    after_second = snapshot(project)

    assert sorted(second.migrations_applied) == sorted(known), f"first run applied {first.migrations_applied}; pinned extra pass: {sorted(known)}"
    if not known:
        assert after_second == after_first, "\n".join(_diff(after_first, after_second))
        return
    third = MigrationRunner(project).upgrade(__version__)
    assert third.migrations_applied == []
    assert snapshot(project) == after_second, "\n".join(_diff(after_second, snapshot(project)))
