"""Planted-file tests of ``scripts/ci/mission_status_gate_checks.py`` (mission mission-status-read-api-overview, WP04).

The script holds the two non-Gradle guards of ``mission-status-api.yml``: ``native-tag-floor`` (the native test binary executed
at least the committed number of tests) and ``digests`` (the four native legs answered the same bodies). Every failure path is
proved on planted files; the script is also run by path from another working directory, as the workflow does.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = pytest.mark.fast

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "ci" / "mission_status_gate_checks.py"

PASS, FAIL, CANNOT = 0, 1, 2
TARGETS = ("linux-x64", "linux-arm64", "macos-arm64", "windows-x64")
GOOD_SHA = "a" * 64


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("mission_status_gate_checks", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Registered only while the module body runs (dataclasses resolve their own module there), then restored.
    with pytest.MonkeyPatch.context() as patch:
        patch.setitem(sys.modules, spec.name, module)
        spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def checks() -> ModuleType:
    return _load()


# --- native-tag-floor ---------------------------------------------------------------------------------------------------------


def _junit(directory: Path, name: str, executed: int, skipped: int = 0, failed: int = 0) -> None:
    cases = [f'<testcase classname="c" name="ok{i}" time="0.1"/>' for i in range(executed)]
    cases += [f'<testcase classname="c" name="skip{i}"><skipped/></testcase>' for i in range(skipped)]
    cases += [f'<testcase classname="c" name="bad{i}"><failure message="x"/></testcase>' for i in range(failed)]
    body = "".join(cases)
    (directory / name).write_text(f'<?xml version="1.0"?><testsuite name="s" tests="{len(cases)}">{body}</testsuite>', encoding="utf-8")


def _floor(checks: ModuleType, directory: Path, floor: int) -> int:
    return int(checks.main(["native-tag-floor", "--junit-dir", str(directory), "--floor", str(floor)]))


def test_the_floor_is_met_exactly(checks: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _junit(tmp_path, "TEST-a.xml", 3)
    assert _floor(checks, tmp_path, 3) == PASS
    assert "3" in capsys.readouterr().out


def test_tests_spread_over_several_xml_files_are_summed(checks: ModuleType, tmp_path: Path) -> None:
    _junit(tmp_path, "TEST-a.xml", 2)
    _junit(tmp_path, "TEST-b.xml", 1)
    assert _floor(checks, tmp_path, 3) == PASS


def test_fewer_tests_than_the_floor_fail_and_the_count_and_floor_are_printed(checks: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _junit(tmp_path, "TEST-a.xml", 2)
    assert _floor(checks, tmp_path, 3) == FAIL
    out = capsys.readouterr()
    assert "2" in out.out + out.err and "3" in out.out + out.err


def test_skipped_tests_are_not_counted(checks: ModuleType, tmp_path: Path) -> None:
    _junit(tmp_path, "TEST-a.xml", 2, skipped=5)
    assert _floor(checks, tmp_path, 3) == FAIL


def test_failed_tests_do_not_inflate_the_executed_count_below_the_floor(checks: ModuleType, tmp_path: Path) -> None:
    # A failing test was executed, so it counts; the Gradle task fails on it, this guard only proves the binary ran enough tests.
    _junit(tmp_path, "TEST-a.xml", 2, failed=1)
    assert _floor(checks, tmp_path, 3) == PASS


def test_an_empty_directory_fails(checks: ModuleType, tmp_path: Path) -> None:
    assert _floor(checks, tmp_path, 3) == FAIL


def test_a_directory_with_only_non_xml_files_fails(checks: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("3 tests", encoding="utf-8")
    assert _floor(checks, tmp_path, 1) == FAIL


def test_an_xml_file_with_zero_testcases_fails(checks: ModuleType, tmp_path: Path) -> None:
    _junit(tmp_path, "TEST-a.xml", 0)
    assert _floor(checks, tmp_path, 1) == FAIL


def test_malformed_xml_fails(checks: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "TEST-a.xml").write_text("<testsuite><testcase", encoding="utf-8")
    assert _floor(checks, tmp_path, 1) == FAIL


def test_a_missing_directory_cannot_be_checked(checks: ModuleType, tmp_path: Path) -> None:
    assert _floor(checks, tmp_path / "absent", 3) == CANNOT


def test_a_floor_below_one_is_refused(checks: ModuleType, tmp_path: Path) -> None:
    _junit(tmp_path, "TEST-a.xml", 3)
    assert _floor(checks, tmp_path, 0) == CANNOT


# --- digests ------------------------------------------------------------------------------------------------------------------


def _digest(directory: Path, target: str, **overrides: object) -> None:
    os_name, arch = target.split("-")
    record: dict[str, object] = {"os": os_name, "arch": arch, "requestCount": 40, "bodyCount": 40, "sha256": GOOD_SHA}
    record.update(overrides)
    (directory / f"digest-{target}.json").write_text(json.dumps(record), encoding="utf-8")


def _plant_all(directory: Path) -> None:
    for target in TARGETS:
        _digest(directory, target)


def _run_digests(checks: ModuleType, directory: Path, floor: int = 40) -> int:
    return int(checks.main(["digests", "--dir", str(directory), "--expected-count", "4", "--request-floor", str(floor)]))


def test_four_equal_digests_pass(checks: ModuleType, tmp_path: Path) -> None:
    _plant_all(tmp_path)
    assert _run_digests(checks, tmp_path) == PASS


def test_one_altered_sha256_fails_and_all_four_digests_are_printed(checks: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _plant_all(tmp_path)
    _digest(tmp_path, "macos-arm64", sha256="b" * 64)
    assert _run_digests(checks, tmp_path) == FAIL
    out = capsys.readouterr()
    text = out.out + out.err
    assert text.count(GOOD_SHA) == 3 and "b" * 64 in text
    for target in TARGETS:
        assert target in text


def test_a_missing_file_fails_on_exactly_four(checks: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _plant_all(tmp_path)
    (tmp_path / "digest-windows-x64.json").unlink()
    assert _run_digests(checks, tmp_path) == FAIL
    out = capsys.readouterr()
    assert "exactly 4" in (out.out + out.err)


def test_a_fifth_file_fails(checks: ModuleType, tmp_path: Path) -> None:
    _plant_all(tmp_path)
    _digest(tmp_path, "freebsd-x64")
    assert _run_digests(checks, tmp_path) == FAIL


def test_a_wrong_name_set_of_four_fails(checks: ModuleType, tmp_path: Path) -> None:
    for target in ("linux-x64", "linux-arm64", "macos-arm64", "macos-x64"):
        _digest(tmp_path, target)
    assert _run_digests(checks, tmp_path) == FAIL


def test_a_file_whose_content_names_another_target_fails(checks: ModuleType, tmp_path: Path) -> None:
    _plant_all(tmp_path)
    _digest(tmp_path, "windows-x64", os="linux")
    assert _run_digests(checks, tmp_path) == FAIL


def test_a_request_count_below_the_floor_fails(checks: ModuleType, tmp_path: Path) -> None:
    for target in TARGETS:
        _digest(tmp_path, target, requestCount=39)
    assert _run_digests(checks, tmp_path) == FAIL


def test_unequal_request_counts_fail(checks: ModuleType, tmp_path: Path) -> None:
    _plant_all(tmp_path)
    _digest(tmp_path, "linux-arm64", requestCount=41)
    assert _run_digests(checks, tmp_path) == FAIL


def test_a_zero_body_count_fails(checks: ModuleType, tmp_path: Path) -> None:
    _plant_all(tmp_path)
    _digest(tmp_path, "linux-x64", bodyCount=0)
    assert _run_digests(checks, tmp_path) == FAIL


def test_malformed_json_fails(checks: ModuleType, tmp_path: Path) -> None:
    _plant_all(tmp_path)
    (tmp_path / "digest-linux-x64.json").write_text("{not json", encoding="utf-8")
    assert _run_digests(checks, tmp_path) == FAIL


def test_a_non_object_json_value_fails(checks: ModuleType, tmp_path: Path) -> None:
    _plant_all(tmp_path)
    (tmp_path / "digest-linux-x64.json").write_text("[1, 2]", encoding="utf-8")
    assert _run_digests(checks, tmp_path) == FAIL


def test_a_missing_field_fails(checks: ModuleType, tmp_path: Path) -> None:
    _plant_all(tmp_path)
    (tmp_path / "digest-linux-x64.json").write_text(json.dumps({"os": "linux", "arch": "x64"}), encoding="utf-8")
    assert _run_digests(checks, tmp_path) == FAIL


def test_a_boolean_request_count_is_not_a_number(checks: ModuleType, tmp_path: Path) -> None:
    for target in TARGETS:
        _digest(tmp_path, target, requestCount=True)
    assert _run_digests(checks, tmp_path, floor=1) == FAIL


def test_an_empty_directory_fails_and_a_missing_one_cannot_be_checked(checks: ModuleType, tmp_path: Path) -> None:
    assert _run_digests(checks, tmp_path) == FAIL
    assert _run_digests(checks, tmp_path / "absent") == CANNOT


def test_an_expected_count_other_than_four_is_refused(checks: ModuleType, tmp_path: Path) -> None:
    _plant_all(tmp_path)
    assert checks.main(["digests", "--dir", str(tmp_path), "--expected-count", "3", "--request-floor", "1"]) == CANNOT


def test_the_digest_covers_bodies_only_so_os_and_arch_may_differ_while_sha256_is_equal(checks: ModuleType, tmp_path: Path) -> None:
    _plant_all(tmp_path)
    records = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(tmp_path.glob("digest-*.json"))]
    assert {(r["os"], r["arch"]) for r in records} == {("linux", "x64"), ("linux", "arm64"), ("macos", "arm64"), ("windows", "x64")}
    assert len({r["sha256"] for r in records}) == 1


# --- by path, from another working directory ---------------------------------------------------------------------------------


def _by_path(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd, capture_output=True, text=True, check=False)


def test_the_script_runs_by_path_from_another_directory(tmp_path: Path) -> None:
    planted = tmp_path / "junit"
    planted.mkdir()
    _junit(planted, "TEST-a.xml", 3)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    assert _by_path(elsewhere, "native-tag-floor", "--junit-dir", str(planted), "--floor", "3").returncode == PASS
    assert _by_path(elsewhere, "native-tag-floor", "--junit-dir", str(planted), "--floor", "4").returncode == FAIL
    assert _by_path(elsewhere, "native-tag-floor", "--junit-dir", str(tmp_path / "absent"), "--floor", "4").returncode == CANNOT
    assert _by_path(elsewhere, "--help").returncode == PASS


def test_the_script_imports_nothing_from_the_repository() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "from scripts" not in text and "import scripts" not in text and "from tests" not in text and "from specify_cli" not in text
