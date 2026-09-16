from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from textwrap import dedent
from types import ModuleType

import pytest

pytestmark = [pytest.mark.integration]

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "release" / "check_shared_package_drift.py"


def write_pyproject(path: Path, *, dependencies: list[str], overrides: list[str] | None = None) -> None:
    override_block = ""
    if overrides is not None:
        lines = "\n".join(f'    "{entry}",' for entry in overrides)
        override_block = f"\n[tool.uv]\noverride-dependencies = [\n{lines}\n]\n"

    path.write_text(
        dedent(
            f"""
            [project]
            name = "example"
            version = "1.0.0"
            dependencies = [
            {chr(10).join(f'    "{dep}",' for dep in dependencies)}
            ]
            {override_block}
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def write_lockfile(path: Path, *, versions: dict[str, str]) -> None:
    path.write_text(
        "\n".join(
            [
                "version = 1",
                "revision = 3",
                'requires-python = ">=3.11"',
                "",
                *[
                    f'[[package]]\nname = "{name}"\nversion = "{version}"\nsource = {{ registry = "https://pypi.org/simple" }}\n'
                    for name, version in versions.items()
                ],
            ]
        ),
        encoding="utf-8",
    )


def write_manifest(
    path: Path,
    *,
    events_range: str = ">=4.0.0,<5.0.0",
    events_version: str = "4.0.0",
    tracker_range: str = ">=0.4,<0.5",
    tracker_version: str = "0.4.2",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "release_train": "3.2.0",
                "authority": "test",
                "packages": [
                    {
                        "package": "spec-kitty-events",
                        "cli_range": events_range,
                        "locked_version": events_version,
                    },
                    {
                        "package": "spec-kitty-tracker",
                        "cli_range": tracker_range,
                        "locked_version": tracker_version,
                    },
                ],
                "retired_packages": [
                    {
                        "package": "spec-kitty-runtime",
                        "status": "retired-for-cli-release",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def run_check(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    manifest = tmp_path / ".kittify" / "release" / "shared-package-compatibility.json"
    if not manifest.exists():
        write_manifest(manifest)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )


def load_script_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_shared_package_drift", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_shared_package_drift_passes_with_aligned_sources(tmp_path: Path) -> None:
    cli = tmp_path / "pyproject.toml"
    lockfile = tmp_path / "uv.lock"
    runtime = tmp_path / "runtime.toml"

    write_pyproject(
        cli,
        dependencies=[
            "spec-kitty-events>=4.0.0,<5.0.0",
            "spec-kitty-tracker>=0.4,<0.5",
        ],
    )
    write_lockfile(
        lockfile,
        versions={
            "spec-kitty-events": "4.0.0",
            "spec-kitty-tracker": "0.4.2",
        },
    )
    write_pyproject(runtime, dependencies=["spec-kitty-events==3.3.0"])

    result = run_check(
        tmp_path,
        "--pyproject",
        str(cli),
        "--lockfile",
        str(lockfile),
        "--runtime-pyproject",
        str(runtime),
    )

    assert result.returncode == 0, result.stderr
    assert "Shared package drift check passed." in result.stdout


def test_shared_package_drift_fails_when_override_remains(tmp_path: Path) -> None:
    cli = tmp_path / "pyproject.toml"
    lockfile = tmp_path / "uv.lock"
    runtime = tmp_path / "runtime.toml"

    write_pyproject(
        cli,
        dependencies=[
            "spec-kitty-events>=4.0.0,<5.0.0",
            "spec-kitty-tracker>=0.4,<0.5",
        ],
        overrides=["spec-kitty-events==3.2.0"],
    )
    write_lockfile(
        lockfile,
        versions={
            "spec-kitty-events": "4.0.0",
            "spec-kitty-tracker": "0.4.2",
        },
    )
    write_pyproject(runtime, dependencies=["spec-kitty-events==3.2.0"])

    result = run_check(
        tmp_path,
        "--pyproject",
        str(cli),
        "--lockfile",
        str(lockfile),
        "--runtime-pyproject",
        str(runtime),
    )

    assert result.returncode == 1
    assert "Emergency override still present" in result.stdout


def test_shared_package_drift_fails_when_runtime_dependency_remains(tmp_path: Path) -> None:
    cli = tmp_path / "pyproject.toml"
    lockfile = tmp_path / "uv.lock"

    write_pyproject(
        cli,
        dependencies=[
            "spec-kitty-events>=4.0.0,<5.0.0",
            "spec-kitty-runtime==0.4.5",
            "spec-kitty-tracker>=0.4,<0.5",
        ],
    )
    write_lockfile(
        lockfile,
        versions={
            "spec-kitty-events": "4.0.0",
            "spec-kitty-tracker": "0.4.2",
        },
    )

    result = run_check(
        tmp_path,
        "--pyproject",
        str(cli),
        "--lockfile",
        str(lockfile),
    )

    assert result.returncode == 1
    assert "Retired runtime package must not be a CLI dependency" in result.stdout


def test_shared_package_drift_fails_when_cli_constraint_is_unbounded(tmp_path: Path) -> None:
    cli = tmp_path / "pyproject.toml"
    lockfile = tmp_path / "uv.lock"

    write_pyproject(
        cli,
        dependencies=[
            "spec-kitty-events>=4.0.0",
            "spec-kitty-tracker>=0.4,<0.5",
        ],
    )
    write_lockfile(
        lockfile,
        versions={
            "spec-kitty-events": "4.0.0",
            "spec-kitty-tracker": "0.4.2",
        },
    )

    result = run_check(
        tmp_path,
        "--pyproject",
        str(cli),
        "--lockfile",
        str(lockfile),
    )

    assert result.returncode == 1
    assert "spec-kitty-events: dependency must use a bounded compatible range" in result.stderr


def test_shared_package_drift_fails_when_cli_range_does_not_match_manifest(
    tmp_path: Path,
) -> None:
    cli = tmp_path / "pyproject.toml"
    lockfile = tmp_path / "uv.lock"
    write_manifest(
        tmp_path / ".kittify" / "release" / "shared-package-compatibility.json",
        events_range=">=5.2.0,<6.0.0",
        events_version="5.2.0",
        tracker_version="0.4.2",
    )

    write_pyproject(
        cli,
        dependencies=[
            "spec-kitty-events>=4.0.0,<5.0.0",
            "spec-kitty-tracker>=0.4,<0.5",
        ],
    )
    write_lockfile(
        lockfile,
        versions={
            "spec-kitty-events": "5.2.0",
            "spec-kitty-tracker": "0.4.2",
        },
    )

    result = run_check(
        tmp_path,
        "--pyproject",
        str(cli),
        "--lockfile",
        str(lockfile),
    )

    assert result.returncode == 1
    assert "spec-kitty-events CLI range <5.0.0,>=4.0.0 does not match release authority <6.0.0,>=5.2.0" in result.stdout


def test_shared_package_drift_fails_when_lock_does_not_match_manifest(
    tmp_path: Path,
) -> None:
    cli = tmp_path / "pyproject.toml"
    lockfile = tmp_path / "uv.lock"
    write_manifest(
        tmp_path / ".kittify" / "release" / "shared-package-compatibility.json",
        events_version="4.0.1",
    )

    write_pyproject(
        cli,
        dependencies=[
            "spec-kitty-events>=4.0.0,<5.0.0",
            "spec-kitty-tracker>=0.4,<0.5",
        ],
    )
    write_lockfile(
        lockfile,
        versions={
            "spec-kitty-events": "4.0.0",
            "spec-kitty-tracker": "0.4.2",
        },
    )

    result = run_check(
        tmp_path,
        "--pyproject",
        str(cli),
        "--lockfile",
        str(lockfile),
    )

    assert result.returncode == 1
    assert "spec-kitty-events uv.lock version 4.0.0 does not match release authority 4.0.1" in result.stdout


def test_shared_package_drift_fails_on_cli_direct_reference(
    tmp_path: Path,
) -> None:
    """CLI shared dependencies must resolve from public index ranges."""
    cli = tmp_path / "pyproject.toml"
    lockfile = tmp_path / "uv.lock"
    write_manifest(
        tmp_path / ".kittify" / "release" / "shared-package-compatibility.json",
        events_range=">=9,<10",
        events_version="9.1.4",
        tracker_range=">=0.5.2,<0.6",
        tracker_version="0.5.2",
    )

    write_pyproject(
        cli,
        dependencies=[
            "spec-kitty-events @ git+https://github.com/spec-kitty/spec-kitty-events@9fe707345469aaaf5d232247724a0e6a08925645",
            "spec-kitty-tracker>=0.5.2,<0.6",
        ],
    )
    write_lockfile(
        lockfile,
        versions={
            "spec-kitty-events": "9.1.4",
            "spec-kitty-tracker": "0.5.2",
        },
    )

    result = run_check(
        tmp_path,
        "--pyproject",
        str(cli),
        "--lockfile",
        str(lockfile),
    )

    assert result.returncode == 1
    assert "spec-kitty-events: direct references are forbidden" in result.stderr


def test_installed_version_guard_passes_when_installed_version_matches_lock() -> None:
    module = load_script_module()

    installed, issues = module.collect_installed_version_issues(
        {"spec-kitty-events": "4.1.0"},
        packages=("spec-kitty-events",),
        version_reader=lambda package: "4.1.0",
    )

    assert installed == {"spec-kitty-events": "4.1.0"}
    assert issues == []


def test_installed_version_guard_reports_mismatch_with_remediation() -> None:
    module = load_script_module()

    installed, issues = module.collect_installed_version_issues(
        {"spec-kitty-events": "4.1.0"},
        packages=("spec-kitty-events",),
        version_reader=lambda package: "4.0.0",
    )

    assert installed == {"spec-kitty-events": "4.0.0"}
    assert issues == [
        "spec-kitty-events installed version 4.0.0 does not match "
        "uv.lock version 4.1.0. "
        "Remediation: Run `uv sync --extra test --extra lint` before collecting release evidence."
    ]


def test_installed_version_guard_reports_missing_package_with_remediation() -> None:
    module = load_script_module()

    def missing_version(package: str) -> str:
        raise module.importlib.metadata.PackageNotFoundError(package)

    installed, issues = module.collect_installed_version_issues(
        {"spec-kitty-events": "4.1.0"},
        packages=("spec-kitty-events",),
        version_reader=missing_version,
    )

    assert installed == {}
    assert issues == [
        "spec-kitty-events is not installed in the active environment; "
        "uv.lock version is 4.1.0. "
        "Remediation: Run `uv sync --extra test --extra lint` before collecting release evidence."
    ]
