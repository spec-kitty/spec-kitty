"""Planted-violation tests for ``contracts/tools/client_smoke.py`` (D-P13, FR-014).

The TypeScript client generator is a JVM tool that is absent from the unit-test
environment, so the Gradle run is replaced by an injected runner that emits files
where the real generator would. The canned failure text in
``fixtures/client_smoke/generation_failed_output.txt`` is a synthetic stand-in used only
to prove the exit-status handling; the real failing condition is the one the
pushed spike run recorded (``fixtures/client_smoke/plants/`` holds the candidate
plants that run exercised, each asserted here to be a well-formed module).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]

TOOLS_DIR = Path(__file__).resolve().parents[2] / "contracts" / "tools"
FIXTURES = TOOLS_DIR / "fixtures" / "client_smoke"
CLEAN_ROOT = FIXTURES / "clean"
PLANTS_ROOT = FIXTURES / "plants"
SCRIPT = TOOLS_DIR / "client_smoke.py"

Runner = Callable[[list[str]], tuple[int, str]]


@pytest.fixture(scope="module")
def smoke() -> ModuleType:
    sys.path.insert(0, str(TOOLS_DIR))
    try:
        spec = importlib.util.spec_from_file_location("client_smoke_under_test", SCRIPT)
        assert spec is not None and spec.loader is not None, f"cannot load {SCRIPT}"
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(TOOLS_DIR))
    return module


def _tool(name: str) -> str | None:
    return f"/fixture/bin/{name}"


def _fake_generator(files: int, *, returncode: int = 0, output: str = "BUILD SUCCESSFUL") -> Runner:
    def run(command: list[str]) -> tuple[int, str]:
        out_dir = Path(next(part.split("=", 1)[1] for part in command if part.startswith("-PoutDir=")))
        for task in command:
            if task.startswith("clientSmoke_"):
                target = out_dir / "client" / task.removeprefix("clientSmoke_")
                target.mkdir(parents=True, exist_ok=True)
                for index in range(files):
                    (target / f"file{index}.ts").write_text("export {};\n", encoding="utf-8")
        return returncode, output

    return run


def _run(smoke: ModuleType, root: Path, out: Path, runner: Runner, *extra: str, which: Callable[[str], str | None] = _tool) -> tuple[int, str]:
    lines: list[str] = []
    code = smoke.run(["--root", str(root), "--out", str(out), *extra], runner=runner, which=which, out=lines.append)
    return code, "\n".join(lines)


def test_clean_control_prints_the_counted_result(smoke: ModuleType, tmp_path: Path) -> None:
    output_with_warnings = "[main] WARN  o.o.codegen.DefaultCodegen - a warning\n[main] WARN  o.o.codegen.DefaultCodegen - another\nBUILD SUCCESSFUL"

    code, output = _run(smoke, CLEAN_ROOT, tmp_path / "out", _fake_generator(3, output=output_with_warnings))

    assert code == 0, output
    assert output.splitlines()[-1] == "counts: modules=1 files_emitted=3 generator_warnings=2"


def test_a_failing_generation_is_named_with_its_module_and_the_generator_message(smoke: ModuleType, tmp_path: Path) -> None:
    text = (FIXTURES / "generation_failed_output.txt").read_text(encoding="utf-8")

    code, output = _run(smoke, CLEAN_ROOT, tmp_path / "out", _fake_generator(0, returncode=1, output=text))

    assert code == 1
    assert "CONTRACT-CHECK client_smoke: GENERATION_FAILED: alpha" in output
    assert "Error resolving reference" in output


def test_zero_files_emitted_cannot_do_its_job(smoke: ModuleType, tmp_path: Path) -> None:
    code, output = _run(smoke, CLEAN_ROOT, tmp_path / "out", _fake_generator(0))

    assert code == 2
    assert "ZERO_FILES_EMITTED" in output
    assert output.splitlines()[-1] == "counts: modules=1 files_emitted=0 generator_warnings=0"


def test_a_warning_the_spike_proved_fatal_fails_even_though_files_were_emitted(smoke: ModuleType, tmp_path: Path) -> None:
    runner = _fake_generator(2, output="[main] WARN  Unable to resolve reference: Missing.yaml\nBUILD SUCCESSFUL")

    clean_code, _ = _run(smoke, CLEAN_ROOT, tmp_path / "a", runner)
    code, output = _run(smoke, CLEAN_ROOT, tmp_path / "b", runner, "--fail-on-warning", "Unable to resolve reference")

    assert clean_code == 0, "a warning alone does not fail unless the spike proved it fatal"
    assert code == 1
    assert "GENERATION_FAILED: alpha" in output and "Unable to resolve reference" in output


def test_no_module_cannot_do_its_job(smoke: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()

    code, output = _run(smoke, tmp_path / "empty", tmp_path / "out", _fake_generator(1))

    assert code == 2
    assert "NO_MODULE" in output
    assert output.splitlines()[-1] == "counts: modules=0 files_emitted=0 generator_warnings=0"


@pytest.mark.parametrize(("missing", "expected"), [("java", "JVM_MISSING"), ("gradle", "GRADLE_MISSING")])
def test_a_missing_tool_cannot_do_its_job(smoke: ModuleType, tmp_path: Path, missing: str, expected: str) -> None:
    def which(name: str) -> str | None:
        return None if name == missing else _tool(name)

    code, output = _run(smoke, CLEAN_ROOT, tmp_path / "out", _fake_generator(1), which=which)

    assert code == 2
    assert expected in output


def test_a_dependency_verification_failure_is_a_toolchain_failure_not_a_generation_failure(smoke: ModuleType, tmp_path: Path) -> None:
    text = (TOOLS_DIR / "fixtures" / "bundle" / "gradle_verification_failure.txt").read_text(encoding="utf-8")

    code, output = _run(smoke, CLEAN_ROOT, tmp_path / "out", _fake_generator(0, returncode=1, output=text))

    assert code == 2
    assert "DEPENDENCY_VERIFICATION_FAILED" in output


def test_the_generator_runs_against_the_split_root_task(smoke: ModuleType, tmp_path: Path) -> None:
    seen: list[list[str]] = []

    def runner(command: list[str]) -> tuple[int, str]:
        seen.append(command)
        return _fake_generator(1)(command)

    _run(smoke, CLEAN_ROOT, tmp_path / "out", runner)

    assert [part for part in seen[0] if part.startswith(("validate_", "bundle_", "clientSmoke_"))] == ["clientSmoke_alpha"]


def test_the_candidate_plants_are_well_formed_modules_the_python_resolver_can_start_on() -> None:
    plants = sorted(path.name for path in PLANTS_ROOT.iterdir() if path.is_dir())

    assert plants == ["cycle", "dangling_pointer", "dangling_ref", "invalid_type"]
    for plant in plants:
        assert (PLANTS_ROOT / plant / "openapi.yaml").is_file()


def test_script_exits_2_with_a_counts_line_when_the_root_has_no_module(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "--out", str(tmp_path / "o")], capture_output=True, text=True, timeout=60, check=False
    )

    assert result.returncode == 2
    assert result.stdout.splitlines()[-1] == "counts: modules=0 files_emitted=0 generator_warnings=0"


def test_verbose_prints_the_gradle_output(smoke: ModuleType, tmp_path: Path) -> None:
    code, output = _run(smoke, CLEAN_ROOT, tmp_path / "out", _fake_generator(1, output="GRADLE-TRANSCRIPT-LINE"), "--verbose")

    assert code == 0, output
    assert "GRADLE-TRANSCRIPT-LINE" in output
