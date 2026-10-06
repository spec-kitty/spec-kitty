"""#4275 (second finding): the version-stamp boundary. A failed ``spec-kitty upgrade`` must not leave the new version stamped.

The runner (or the no-migrations stamp) writes ``version`` / ``last_upgraded_at`` /
``schema_version`` before the CLI's final surface repair runs. When that repair fails the
project must read exactly as it did before the run, so the next ``upgrade`` re-drives it.
"""

from __future__ import annotations

import contextlib
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.cli.commands import upgrade as upgrade_module
from specify_cli.migration.schema_version import MAX_SUPPORTED_SCHEMA
from specify_cli.upgrade import assessment
from specify_cli.upgrade.metadata import ProjectMetadata, VersionStamp
from specify_cli.upgrade.migrations.base import BaseMigration, MigrationResult
from specify_cli.upgrade.outcome import SurfaceRepairReport, UpgradeOutcome
from specify_cli.upgrade.registry import MigrationRegistry
from specify_cli.upgrade.runner import UpgradeResult
from specify_cli.upgrade.version_stamp_boundary import version_stamp_boundary

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_APPLY = "apply_upgrade_repairs"
_CURRENT_VERSION = "3.2.0rc37"
_NEXT_VERSION = "3.2.0rc38"
_STALE_VERSION = "3.2.0rc30"

_test_app = typer.Typer(add_completion=False)
_test_app.command()(upgrade_module.upgrade)
_runner = CliRunner()


def _write_project(project: Path, *, version: str) -> Path:
    kittify = project / ".kittify"
    kittify.mkdir(parents=True)
    metadata = kittify / "metadata.yaml"
    metadata.write_text(
        f'spec_kitty:\n  version: "{version}"\n  schema_version: {MAX_SUPPORTED_SCHEMA}\n'
        "  initialized_at: '2026-01-01T00:00:00+00:00'\n  last_upgraded_at: '2026-01-02T00:00:00+00:00'\n",
        encoding="utf-8",
    )
    (kittify / "config.yaml").write_text("vcs:\n  type: git\nmission_type_activations:\n  - software-development\n", encoding="utf-8")
    (project / "kitty-specs").mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=project, check=True)
    subprocess.run(["git", "add", "-A"], cwd=project, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=project, check=True)
    return metadata


@pytest.fixture
def succeeding_migration() -> Iterator[None]:
    """Exactly one migration that applies cleanly, so the run reaches the surface repair."""
    MigrationRegistry.clear()

    class _Stub(BaseMigration):
        migration_id = "test_4275_stub_success"
        description = "Stub migration that succeeds, for the #4275 version-restore repro"
        target_version = _CURRENT_VERSION

        def detect(self, project_path: Path) -> bool:  # noqa: ARG002
            return True

        def can_apply(self, project_path: Path) -> tuple[bool, str]:  # noqa: ARG002
            return True, ""

        def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:  # noqa: ARG002
            return MigrationResult(success=True)

    MigrationRegistry.register(_Stub)
    try:
        yield
    finally:
        MigrationRegistry.clear()


def _fail_surface_repair(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CI", "1")

    def _raise(*args: Any, **kwargs: Any) -> Any:
        raise OSError("surface repair exploded (#4275)")

    monkeypatch.setattr(assessment, _APPLY, _raise)


def _upgrade(project: Path, target: str) -> Any:
    with contextlib.chdir(project):
        return _runner.invoke(_test_app, ["--target", target, "--force", "--no-worktrees", "--no-nag"], catch_exceptions=True)


def _stamp(metadata: Path) -> tuple[str, object, int | None]:
    loaded = ProjectMetadata.load(metadata.parent)
    assert loaded is not None
    return loaded.version, loaded.last_upgraded_at, loaded.schema_version


def test_failed_surface_repair_restores_version_trio_after_migrations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, succeeding_migration: None) -> None:
    project = tmp_path / "project"
    project.mkdir()
    metadata = _write_project(project, version=_STALE_VERSION)
    before = _stamp(metadata)
    _fail_surface_repair(monkeypatch)

    result = _upgrade(project, _CURRENT_VERSION)

    assert result.exit_code != 0, result.output
    assert _stamp(metadata) == before


def test_failed_surface_repair_on_no_migration_path_leaves_metadata_byte_identical(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "project"
    project.mkdir()
    metadata = _write_project(project, version=_CURRENT_VERSION)
    before = metadata.read_bytes()
    _fail_surface_repair(monkeypatch)

    result = _upgrade(project, _NEXT_VERSION)

    assert result.exit_code != 0, result.output
    assert metadata.read_bytes() == before


def test_reported_surface_repair_failure_restores_version_trio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A repair that *reports* failure (no exception) is a failed run too."""
    project = tmp_path / "project"
    project.mkdir()
    metadata = _write_project(project, version=_CURRENT_VERSION)
    before = metadata.read_bytes()
    monkeypatch.setenv("CI", "1")
    monkeypatch.setattr(
        upgrade_module,
        "_apply_prepared_surface_repairs",
        lambda *a, **k: SurfaceRepairReport(failed=True, failure_messages=("boom",)),
    )

    result = _upgrade(project, _NEXT_VERSION)

    assert result.exit_code == 1, result.output
    assert metadata.read_bytes() == before


def test_successful_upgrade_keeps_the_new_stamp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = tmp_path / "project"
    project.mkdir()
    metadata = _write_project(project, version=_CURRENT_VERSION)
    monkeypatch.setenv("CI", "1")

    result = _upgrade(project, _NEXT_VERSION)

    assert result.exit_code == 0, result.output
    assert _stamp(metadata)[0] == _NEXT_VERSION


_BASE = (
    "spec_kitty:\n  version: '1.0.0'\n  initialized_at: '2026-01-01T00:00:00+00:00'\n"
    "  last_upgraded_at: '2026-01-02T00:00:00+00:00'\n  schema_version: 3\n"
    "environment:\n  python_version: '3.12'\nmigrations:\n  applied: []\n"
)


def _kittify(tmp_path: Path, text: str | None) -> Path:
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    if text is not None:
        (kittify / "metadata.yaml").write_text(text, encoding="utf-8")
    return kittify


# --- version_stamp_boundary -------------------------------------------------


def _outcome(*, success: bool, drift: bool = False) -> UpgradeOutcome:
    result = UpgradeResult(success=success, from_version="1.0.0", to_version="2.0.0", dry_run=False)
    return UpgradeOutcome(result=result, drifted_paths=[Path("x")] if drift else [])


def _bump(kittify: Path) -> None:
    (kittify / "metadata.yaml").write_text(_BASE.replace("1.0.0", "2.0.0"), encoding="utf-8")


def test_boundary_restores_when_the_settled_outcome_failed(tmp_path: Path) -> None:
    kittify = _kittify(tmp_path, _BASE)
    with version_stamp_boundary(kittify, dry_run=False) as settle:
        _bump(kittify)
        settle(_outcome(success=False))
    assert (kittify / "metadata.yaml").read_text(encoding="utf-8") == _BASE


def test_boundary_announces_an_actual_restore_of_a_failed_outcome(tmp_path: Path) -> None:
    kittify = _kittify(tmp_path, _BASE)
    notices: list[str] = []
    with version_stamp_boundary(kittify, dry_run=False, on_restored=notices.append) as settle:
        _bump(kittify)
        settle(_outcome(success=False))
    assert notices == [".kittify/metadata.yaml restored to 1.0.0; the change is uncommitted"]


def test_boundary_is_silent_when_a_failed_outcome_changed_nothing_to_restore(tmp_path: Path) -> None:
    kittify = _kittify(tmp_path, _BASE)
    notices: list[str] = []
    with version_stamp_boundary(kittify, dry_run=False, on_restored=notices.append) as settle:
        settle(_outcome(success=False))
    assert notices == []


def test_boundary_is_silent_when_the_outcome_succeeded(tmp_path: Path) -> None:
    kittify = _kittify(tmp_path, _BASE)
    notices: list[str] = []
    with version_stamp_boundary(kittify, dry_run=False, on_restored=notices.append) as settle:
        _bump(kittify)
        settle(_outcome(success=True))
    assert notices == []


@pytest.mark.parametrize("drift", [False, True], ids=["applied", "drift-unresolved"])
def test_boundary_keeps_the_stamp_when_the_run_did_not_fail(tmp_path: Path, drift: bool) -> None:
    kittify = _kittify(tmp_path, _BASE)
    with version_stamp_boundary(kittify, dry_run=False) as settle:
        _bump(kittify)
        settle(_outcome(success=True, drift=drift))
    assert "2.0.0" in (kittify / "metadata.yaml").read_text(encoding="utf-8")


def test_boundary_restores_and_reraises_when_the_body_raises(tmp_path: Path) -> None:
    kittify = _kittify(tmp_path, _BASE)

    def _body() -> None:
        with version_stamp_boundary(kittify, dry_run=False):
            _bump(kittify)
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        _body()
    assert (kittify / "metadata.yaml").read_text(encoding="utf-8") == _BASE


@pytest.mark.parametrize(
    "exc,restored",
    [
        (typer.Exit(0), False),
        (typer.Exit(1), True),
        (typer.Abort(), True),
        (KeyboardInterrupt(), True),
    ],
    ids=["exit-0-kept", "exit-1", "abort", "interrupt"],
)
def test_boundary_keeps_the_stamp_only_for_an_orderly_exit(tmp_path: Path, exc: BaseException, restored: bool) -> None:
    kittify = _kittify(tmp_path, _BASE)

    def _body() -> None:
        with version_stamp_boundary(kittify, dry_run=False):
            _bump(kittify)
            raise exc

    with pytest.raises(type(exc)):
        _body()
    assert ((kittify / "metadata.yaml").read_text(encoding="utf-8") == _BASE) is restored


def test_boundary_keeps_the_original_error_when_the_restore_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    kittify = _kittify(tmp_path, _BASE)

    def _restore_fails(self: object, _: Path) -> bool:
        raise OSError("read-only file system")

    monkeypatch.setattr(VersionStamp, "restore", _restore_fails)

    def _body() -> None:
        with version_stamp_boundary(kittify, dry_run=False):
            _bump(kittify)
            raise RuntimeError("boom")

    with caplog.at_level("WARNING"), pytest.raises(RuntimeError, match="boom"):
        _body()
    assert "Could not restore" in caplog.text


def test_boundary_logs_a_failed_restore_of_a_failed_outcome_without_raising(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    kittify = _kittify(tmp_path, _BASE)
    notices: list[str] = []

    def _restore_fails(self: object, _: Path) -> bool:
        raise OSError("read-only file system")

    monkeypatch.setattr(VersionStamp, "restore", _restore_fails)

    with caplog.at_level("WARNING"), version_stamp_boundary(kittify, dry_run=False, on_restored=notices.append) as settle:
        _bump(kittify)
        settle(_outcome(success=False))

    assert "Could not restore" in caplog.text
    assert notices == []


def test_boundary_never_restores_a_dry_run(tmp_path: Path) -> None:
    kittify = _kittify(tmp_path, _BASE)
    with version_stamp_boundary(kittify, dry_run=True) as settle:
        _bump(kittify)
        settle(_outcome(success=False))
    assert "2.0.0" in (kittify / "metadata.yaml").read_text(encoding="utf-8")

    def _dry_body() -> None:
        with version_stamp_boundary(kittify, dry_run=True):
            raise RuntimeError("dry")

    with pytest.raises(RuntimeError):
        _dry_body()
