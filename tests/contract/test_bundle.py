"""Planted-violation tests for ``contracts/tools/bundle.py`` (FR-014, FR-018).

There is no JVM in the unit-test environment, so the Gradle run is replaced by an
injected runner that writes a chosen fixture bundle where the real build would
(``<out>/bundle/<module>/openapi.yaml``) and returns the canned build output. The
real Gradle step is exercised only by the Contracts workflow. Each violation is
asserted on its own planted fixture with a clean control on the same module.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]

TOOLS_DIR = Path(__file__).resolve().parents[2] / "contracts" / "tools"
FIXTURES = TOOLS_DIR / "fixtures" / "bundle"
CLEAN_ROOT = FIXTURES / "roots" / "clean"
NO_ROOT = FIXTURES / "roots" / "no_root"
SCRIPT = TOOLS_DIR / "bundle.py"


@pytest.fixture(scope="module")
def bundler() -> ModuleType:
    sys.path.insert(0, str(TOOLS_DIR))
    try:
        spec = importlib.util.spec_from_file_location("bundle_under_test", SCRIPT)
        assert spec is not None and spec.loader is not None, f"cannot load {SCRIPT}"
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(TOOLS_DIR))
    return module


def _tool(name: str) -> str | None:
    return f"/fixture/bin/{name}"


def _fake_gradle(fixture: str | None, *, returncode: int = 0, output: str = "BUILD SUCCESSFUL") -> Callable[[list[str]], tuple[int, str]]:
    """A runner that writes ``fixture`` as the bundle of every module whose bundle task it is asked to run."""

    def run(command: list[str]) -> tuple[int, str]:
        out_dir = Path(next(part.split("=", 1)[1] for part in command if part.startswith("-PoutDir=")))
        for task in command:
            if task.startswith("bundle_") and fixture is not None:
                target = out_dir / "bundle" / task.removeprefix("bundle_") / "openapi.yaml"
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(FIXTURES / f"{fixture}.yaml", target)
        return returncode, output

    return run


def _run(
    bundler: ModuleType, root: Path, out: Path, runner: Callable[[list[str]], tuple[int, str]], *extra: str, which: Callable[[str], str | None] = _tool
) -> tuple[int, str]:
    lines: list[str] = []
    code = bundler.run(["--root", str(root), "--out", str(out), *extra], runner=runner, which=which, out=lines.append)
    return code, "\n".join(lines)


def test_clean_control_bundles_and_prints_counts(bundler: ModuleType, tmp_path: Path) -> None:
    code, output = _run(bundler, CLEAN_ROOT, tmp_path / "out", _fake_gradle("ok_bundle"))

    assert code == 0, output
    assert output.splitlines()[-1] == "counts: modules=1 bundles=1 path_items=5"


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [
        ("empty_bundle", "BUNDLE_EMPTY"),
        ("few_paths_bundle", "FEWER_THAN_FIVE_PATHS"),
        ("external_ref_bundle", "UNRESOLVED_REFERENCE_LEFT"),
        ("dangling_ref_bundle", "UNRESOLVED_REFERENCE_LEFT"),
    ],
)
def test_each_planted_bundle_fails_with_its_code_naming_the_module(bundler: ModuleType, tmp_path: Path, fixture: str, expected: str) -> None:
    code, output = _run(bundler, CLEAN_ROOT, tmp_path / "out", _fake_gradle(fixture))

    assert code == 1
    assert f"CONTRACT-CHECK bundle: {expected}: alpha" in output
    assert output.splitlines()[-1].startswith("counts: modules=1 ")


def test_a_missing_bundle_file_is_an_empty_bundle(bundler: ModuleType, tmp_path: Path) -> None:
    code, output = _run(bundler, CLEAN_ROOT, tmp_path / "out", _fake_gradle(None))

    assert code == 1
    assert "BUNDLE_EMPTY: alpha" in output


def test_the_floor_is_a_parameter_and_defaults_to_five(bundler: ModuleType, tmp_path: Path) -> None:
    code, output = _run(bundler, CLEAN_ROOT, tmp_path / "out", _fake_gradle("few_paths_bundle"), "--min-paths", "4")

    assert code == 0, output


def test_no_module_cannot_do_its_job(bundler: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()

    code, output = _run(bundler, tmp_path / "empty", tmp_path / "out", _fake_gradle("ok_bundle"))

    assert code == 2
    assert "NO_MODULE" in output
    assert output.splitlines()[-1] == "counts: modules=0 bundles=0 path_items=0"


def test_a_module_directory_without_a_root_document_cannot_do_its_job(bundler: ModuleType, tmp_path: Path) -> None:
    code, output = _run(bundler, NO_ROOT, tmp_path / "out", _fake_gradle("ok_bundle"))

    assert code == 2
    assert "MODULE_WITHOUT_ROOT: orphan" in output


@pytest.mark.parametrize(("missing", "expected"), [("java", "JVM_MISSING"), ("gradle", "GRADLE_MISSING")])
def test_a_missing_tool_cannot_do_its_job(bundler: ModuleType, tmp_path: Path, missing: str, expected: str) -> None:
    def which(name: str) -> str | None:
        return None if name == missing else _tool(name)

    code, output = _run(bundler, CLEAN_ROOT, tmp_path / "out", _fake_gradle("ok_bundle"), which=which)

    assert code == 2
    assert expected in output


@pytest.mark.parametrize(
    ("canned", "expected"),
    [
        ("gradle_plugin_failure.txt", "PLUGIN_RESOLUTION_FAILED"),
        ("gradle_verification_failure.txt", "DEPENDENCY_VERIFICATION_FAILED"),
    ],
)
def test_toolchain_failures_cannot_do_the_job(bundler: ModuleType, tmp_path: Path, canned: str, expected: str) -> None:
    text = (FIXTURES / canned).read_text(encoding="utf-8")

    code, output = _run(bundler, CLEAN_ROOT, tmp_path / "out", _fake_gradle(None, returncode=1, output=text))

    assert code == 2
    assert expected in output


def test_a_rejected_specification_is_a_violation_not_a_toolchain_failure(bundler: ModuleType, tmp_path: Path) -> None:
    text = (FIXTURES / "gradle_validation_failure.txt").read_text(encoding="utf-8")

    code, output = _run(bundler, CLEAN_ROOT, tmp_path / "out", _fake_gradle(None, returncode=1, output=text))

    assert code == 1
    assert "VALIDATION_FAILED: alpha" in output
    assert "attribute paths" in output, "the validator's own message is carried"


def test_output_inside_the_repository_is_refused(bundler: ModuleType) -> None:
    code, output = _run(bundler, CLEAN_ROOT, TOOLS_DIR / "bundle-output-must-not-be-here", _fake_gradle("ok_bundle"))

    assert code == 2
    assert "OUT_INSIDE_REPOSITORY" in output


def test_the_gradle_command_pins_the_inputs_and_never_uses_a_daemon(bundler: ModuleType, tmp_path: Path) -> None:
    seen: list[list[str]] = []

    def runner(command: list[str]) -> tuple[int, str]:
        seen.append(command)
        return _fake_gradle("ok_bundle")(command)

    _run(bundler, CLEAN_ROOT, tmp_path / "out", runner, "--write-verification-metadata")

    command = seen[0]
    assert command[0] == "/fixture/bin/gradle"
    assert "--no-daemon" in command and any(part.startswith("-PcontractsRoot=") for part in command)
    assert command[command.index("--write-verification-metadata") + 1] == "sha256"
    assert [part for part in command if part.startswith(("validate_", "bundle_"))] == ["validate_alpha", "bundle_alpha"]


def test_script_exits_2_with_a_counts_line_when_the_root_has_no_module(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "--out", str(tmp_path / "o")], capture_output=True, text=True, timeout=60, check=False
    )

    assert result.returncode == 2
    assert result.stdout.splitlines()[-1] == "counts: modules=0 bundles=0 path_items=0"


def test_verbose_prints_the_gradle_output_and_an_empty_bundle_lists_what_was_staged(bundler: ModuleType, tmp_path: Path) -> None:
    def runner(command: list[str]) -> tuple[int, str]:
        out_dir = Path(next(part.split("=", 1)[1] for part in command if part.startswith("-PoutDir=")))
        stray = out_dir / "bundle" / "alpha" / "openapi" / "openapi.yaml"
        stray.parent.mkdir(parents=True)
        stray.write_text("openapi: 3.1.0\n", encoding="utf-8")
        return 0, "GRADLE-TRANSCRIPT-LINE"

    code, output = _run(bundler, CLEAN_ROOT, tmp_path / "out", runner, "--verbose")

    assert code == 1
    assert "GRADLE-TRANSCRIPT-LINE" in output
    assert "BUNDLE_EMPTY: alpha" in output and "openapi/openapi.yaml" in output, "the file the generator did write is named"
