"""Unit tests for ``scripts/ci/sonar_project_version.py`` (WP01, FR-001/FR-002).

The Sonar-analysing CI jobs derive ``sonar.projectVersion`` from ``pyproject.toml``
via this extraction module. ``ci-aggregate.yml``'s ``sonar-pr`` job is its
only caller (``sonar.yml`` stamps the same value from an inline heredoc rather
than calling this script). The original caller, ``ci-quality.yml``'s
``sonarcloud`` job, was retired by mission ``sonar-per-pr-coverage-reuse``, #4334. These tests pin the contract BEFORE (red-first) the
workflow wiring exists:

- ``read_project_version`` returns EXACTLY ``pyproject.toml``'s
  ``[project].version`` string;
- it **raises loudly** (never returns an empty string) when the version key is
  absent, the ``[project]`` table is missing, the version is blank, the file is
  missing / unreadable, or the TOML is malformed;
- ``main`` prints the version to stdout on success and emits NOTHING to stdout
  on failure (so a shell ``$(...)`` capture is empty and the step fails rather
  than silently stamping ``sonar.projectVersion=``).

The module is loaded by file path (``scripts/ci`` is not an importable
package), mirroring ``tests/scripts/test_quality_gate_decision.py``.
"""

from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "ci" / "sonar_project_version.py"
_PYPROJECT = _REPO_ROOT / "pyproject.toml"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("sonar_project_version", _SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot build an import spec for {_SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def module() -> ModuleType:
    return _load_module()


def _expected_version() -> str:
    with _PYPROJECT.open("rb") as handle:
        data = tomllib.load(handle)
    version = data["project"]["version"]
    assert isinstance(version, str)
    return version


def _write_pyproject(tmp_path: Path, body: str) -> Path:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(body, encoding="utf-8")
    return pyproject


def test_returns_exact_pyproject_version(module: ModuleType) -> None:
    assert module.read_project_version(_PYPROJECT) == _expected_version()


def test_returned_version_is_nonempty_and_trimmed(module: ModuleType) -> None:
    version = module.read_project_version(_PYPROJECT)
    assert version
    assert version.strip() == version


def test_reads_arbitrary_version(module: ModuleType, tmp_path: Path) -> None:
    pyproject = _write_pyproject(tmp_path, '[project]\nname = "x"\nversion = "9.9.9-rc1"\n')
    assert module.read_project_version(pyproject) == "9.9.9-rc1"


def test_raises_when_version_key_absent(module: ModuleType, tmp_path: Path) -> None:
    # The failure mode this guards: an inline ``... || echo ""`` that emits an
    # empty version. The module must RAISE, never quietly yield "".
    pyproject = _write_pyproject(tmp_path, '[project]\nname = "x"\n')
    with pytest.raises(module.ProjectVersionError):
        module.read_project_version(pyproject)


def test_raises_when_project_table_absent(module: ModuleType, tmp_path: Path) -> None:
    pyproject = _write_pyproject(tmp_path, "[tool.ruff]\nline-length = 100\n")
    with pytest.raises(module.ProjectVersionError):
        module.read_project_version(pyproject)


def test_raises_when_version_blank(module: ModuleType, tmp_path: Path) -> None:
    pyproject = _write_pyproject(tmp_path, '[project]\nname = "x"\nversion = "   "\n')
    with pytest.raises(module.ProjectVersionError):
        module.read_project_version(pyproject)


def test_raises_when_version_not_a_string(module: ModuleType, tmp_path: Path) -> None:
    pyproject = _write_pyproject(tmp_path, '[project]\nname = "x"\nversion = 3\n')
    with pytest.raises(module.ProjectVersionError):
        module.read_project_version(pyproject)


def test_raises_when_file_missing(module: ModuleType, tmp_path: Path) -> None:
    with pytest.raises(module.ProjectVersionError):
        module.read_project_version(tmp_path / "nope.toml")


def test_raises_on_malformed_toml(module: ModuleType, tmp_path: Path) -> None:
    pyproject = _write_pyproject(tmp_path, "this is = not [[ valid toml")
    with pytest.raises(module.ProjectVersionError):
        module.read_project_version(pyproject)


def test_main_prints_only_the_version(module: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = module.main(["--pyproject", str(_PYPROJECT)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == _expected_version()


def test_main_errors_and_prints_no_version_when_absent(module: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pyproject = _write_pyproject(tmp_path, '[project]\nname = "x"\n')
    exit_code = module.main(["--pyproject", str(pyproject)])
    assert exit_code != 0
    # Never emit an empty (or any) version on stdout on failure.
    assert capsys.readouterr().out.strip() == ""
