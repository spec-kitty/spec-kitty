"""Planted-violation tests for ``contracts/tools/leak_scan.py`` (FR-012, NFR-004, FR-021, FR-025).

Leak-class plants are never committed: ``fixture_builder`` assembles them from fragments into a temporary
root next to a clean control, and the scan must report exactly the planted code there and nothing on the
control. Only clean controls and the exit-2 shapes are committed, under ``contracts/tools/fixtures/leak_scan/``.
The scan has no exempt directory: it also runs over the real ``contracts/tools`` tree (the self-reference
control) and over the whole real ``contracts`` tree, each with a floor on what it scanned.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from tests.contract._loader import load_tool

pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = REPO_ROOT / "contracts"
TOOLS_DIR = CONTRACTS / "tools"
FIXTURE_ROOT = TOOLS_DIR / "fixtures" / "leak_scan"
SCRIPT = TOOLS_DIR / "leak_scan.py"

SLASH = chr(47)
AT = chr(64)


@pytest.fixture(scope="module")
def scan() -> Iterator[Any]:
    with pytest.MonkeyPatch.context() as mp:
        yield load_tool(mp, SCRIPT, "leak_scan_under_test", syspath=TOOLS_DIR)


@pytest.fixture(scope="module")
def builder(scan: Any) -> ModuleType:
    return sys.modules["fixture_builder"]


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *arguments], capture_output=True, text=True, check=False, cwd=REPO_ROOT)


def _home(tail: str = "project") -> str:
    return SLASH + "home" + SLASH + "someone" + SLASH + tail


def _email() -> str:
    return "someone" + AT + "example.invalid"


# -- every planted kind is found, the control on the same root is not ---------------------------


@pytest.mark.parametrize("kind", ["host-path-strict", "host-path-human", "email", "forbidden-property"])
def test_each_leak_kind_is_found_and_the_control_on_the_same_root_is_not(scan: Any, builder: ModuleType, kind: str, tmp_path: Path) -> None:
    built = builder.build(kind, tmp_path)
    report = scan.check(tmp_path)
    planted = [f for f in report.findings if builder.PLANTED_FILE in f.subject]
    control = [f for f in report.findings if builder.CONTROL_FILE in f.subject]
    assert control == [], control
    assert set(built.expected_codes) <= {f.code for f in planted}, (kind, [f.render() for f in report.findings])
    assert {f.code for f in planted} <= set(built.expected_codes) | {"HOST_PATH", "EMAIL"}
    assert report.exit_code == 1


def test_a_finding_never_prints_the_leaked_value(scan: Any, builder: ModuleType, tmp_path: Path) -> None:
    builder.build("host-path-human", tmp_path)
    builder.build("email", tmp_path / "second")
    for finding in scan.check(tmp_path).findings:
        assert "someone" not in finding.render()


def test_the_strict_class_catches_a_tilde_path_that_the_human_text_pass_alone_would_not(scan: Any, builder: ModuleType, tmp_path: Path) -> None:
    builder.build("host-path-strict", tmp_path)
    codes = [(f.code, f.subject) for f in scan.check(tmp_path).findings]
    assert len(codes) == 1 and codes[0][0] == "HOST_PATH" and codes[0][1].endswith("targetBranch")


def test_the_forbidden_name_is_found_in_a_json_key_but_not_in_a_value(scan: Any, tmp_path: Path) -> None:
    name = "record" + "Path"
    (tmp_path / "a.json").write_text(json.dumps({"slug": "x", "title": "y", name: "relative/value"}), encoding="utf-8")
    (tmp_path / "b.json").write_text(json.dumps({"slug": "x", "title": name}), encoding="utf-8")
    codes = {f.subject.split(":")[0]: f.code for f in scan.check(tmp_path).findings}
    assert codes == {"a.json": "FORBIDDEN_PROPERTY_NAME"}


def test_the_text_pass_reads_every_file_type(scan: Any, tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(f"See {_home('notes')} for details.\n", encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text(f"Thanks {_email()}.\n", encoding="utf-8")
    (tmp_path / "tool.py").write_text(f'NOTE = "{_home()}"\n', encoding="utf-8")
    (tmp_path / "ok.yaml").write_text("slug: example\ntitle: Example\n", encoding="utf-8")
    found = {(f.subject.split(":")[0], f.code) for f in scan.check(tmp_path).findings}
    assert found == {("README.md", "HOST_PATH"), ("CHANGELOG.md", "EMAIL"), ("tool.py", "HOST_PATH")}


@pytest.mark.parametrize("directory", ["fixtures", "tools", "examples", "planted", "_shared"])
def test_no_directory_is_exempt(scan: Any, builder: ModuleType, tmp_path: Path, directory: str) -> None:
    builder.build("host-path-human", tmp_path / directory / "nested")
    assert [f.code for f in scan.check(tmp_path).findings if directory in f.subject] == ["HOST_PATH", "HOST_PATH"]


def test_a_planted_line_is_reported_with_its_line_number(scan: Any, tmp_path: Path) -> None:
    (tmp_path / "doc.md").write_text(f"first line\nsecond line\nthird {_home()} line\n", encoding="utf-8")
    assert [f.subject for f in scan.check(tmp_path).findings] == ["doc.md:3"]


# -- the real pass controls, and the clean control root ---------------------------------------------


def test_the_clean_control_passes_with_every_class_populated(scan: Any) -> None:
    report = scan.check(FIXTURE_ROOT / "clean")
    assert report.findings == [] and report.blocked == []
    assert report.counts["files"] == 3
    assert report.counts["values_strict"] >= 5 and report.counts["values_human"] >= 4 and report.counts["values_all"] >= 10


def test_the_two_real_pass_controls_are_not_leaks(scan: Any, tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text("slug: example\nfriendlyName: ~/.kittify Runtime Centralization\ntitle: '/tmp burn-down: sync'\n", encoding="utf-8")
    assert scan.check(tmp_path).findings == []


# -- a file the structured pass cannot parse ------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "content"),
    [
        pytest.param("broken.yaml", "slug: [unclosed\ntitle: x\n", id="yaml"),
        pytest.param("broken.yml", "a: b\n\tc: d\n", id="yml"),
        pytest.param("broken.json", '{"slug": "x",}', id="json"),
    ],
)
def test_a_yaml_or_json_file_that_fails_to_parse_is_a_parse_failed_finding(scan: Any, tmp_path: Path, name: str, content: str) -> None:
    (tmp_path / "ok.yaml").write_text("slug: example\ntitle: Example\n", encoding="utf-8")
    (tmp_path / name).write_text(content, encoding="utf-8")
    report = scan.check(tmp_path)
    parse_failed = [f for f in report.findings if f.code == "PARSE_FAILED"]
    assert [f.subject for f in parse_failed] == [name]
    assert report.exit_code == 1
    assert all(f.subject == name for f in report.findings)
    result = _run("--root", str(tmp_path))
    assert result.returncode == 1
    assert f"CONTRACT-CHECK leak_scan: PARSE_FAILED: {name}: " in result.stdout


def test_a_parse_failure_never_prints_the_file_content(scan: Any, tmp_path: Path) -> None:
    (tmp_path / "ok.yaml").write_text("slug: example\ntitle: Example\n", encoding="utf-8")
    (tmp_path / "bad.yaml").write_text(f"title: [{_home()}\n", encoding="utf-8")
    (finding,) = [f for f in scan.check(tmp_path).findings if f.code == "PARSE_FAILED"]
    assert "someone" not in finding.render()


# -- cannot do its job -----------------------------------------------------------------------------


def test_an_empty_root_exits_two_zero_files(scan: Any, tmp_path: Path) -> None:
    report = scan.check(tmp_path)
    assert [f.code for f in report.blocked][:1] == ["ZERO_FILES"] and report.exit_code == 2
    result = _run("--root", str(tmp_path))
    assert result.returncode == 2 and "CONTRACT-CHECK leak_scan: ZERO_FILES" in result.stdout
    assert result.stdout.splitlines()[-1].startswith("counts: files=0 ")


def test_a_missing_root_exits_two(scan: Any, tmp_path: Path) -> None:
    assert [f.code for f in scan.check(tmp_path / "absent").blocked][:1] == ["ZERO_FILES"]


@pytest.mark.parametrize(("case", "empty_class"), [("no_human_values", "human"), ("no_strict_values", "strict")])
def test_a_class_with_no_values_exits_two(scan: Any, case: str, empty_class: str) -> None:
    report = scan.check(FIXTURE_ROOT / "exit2" / case)
    assert [(f.code, f.subject) for f in report.blocked] == [("ZERO_VALUES_IN_CLASS", empty_class)]
    assert report.exit_code == 2


def test_a_scan_that_misses_every_plant_reports_planted_not_detected(scan: Any) -> None:
    def blind(_root: Path) -> list[Any]:
        return []

    findings = scan.run_self_test(blind)
    assert sorted(f.code for f in findings) == ["PLANTED_NOT_DETECTED"] * 4
    assert {f.subject for f in findings} == {"host-path-strict", "host-path-human", "email", "forbidden-property"}


def test_the_self_test_of_the_real_scan_passes(scan: Any) -> None:
    assert scan.run_self_test(scan.scan_tree) == []


def test_a_scan_that_flags_the_control_fails_the_self_test(scan: Any, builder: ModuleType) -> None:
    def paranoid(root: Path) -> list[Any]:
        return [scan.Finding("HOST_PATH", f"{builder.CONTROL_FILE}:1", "flagged")] + scan.scan_tree(root)

    codes = [f.code for f in scan.run_self_test(paranoid)]
    assert "CONTROL_FLAGGED" in codes


def test_planted_not_detected_is_a_failure_of_the_real_command(scan: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scan, "scan_tree", lambda _root: [])
    report = scan.check(FIXTURE_ROOT / "clean")
    assert report.exit_code == 1 and {f.code for f in report.findings} == {"PLANTED_NOT_DETECTED"}


# -- the real trees ----------------------------------------------------------------------------------


def test_the_self_reference_control_the_real_tools_tree_has_no_finding_and_a_floor(scan: Any) -> None:
    report = scan.check(TOOLS_DIR)
    assert report.findings == [], [f.render() for f in report.findings]
    assert report.blocked == []
    python_files = [p for p in TOOLS_DIR.rglob("*.py") if "__pycache__" not in p.parts]
    assert report.counts["files"] >= len(python_files) > 0


def test_the_whole_real_contracts_tree_has_no_finding() -> None:
    result = _run("--root", str(CONTRACTS))
    assert result.returncode == 0, result.stdout
    counts = dict(pair.split("=") for pair in result.stdout.splitlines()[-1].removeprefix("counts: ").split())
    assert int(counts["files"]) >= 100 and int(counts["values_strict"]) > 0 and int(counts["values_human"]) > 0 and int(counts["values_all"]) > 0


def test_command_line_exit_status_and_grammar_on_a_planted_root(tmp_path: Path, builder: ModuleType) -> None:
    builder.build("email", tmp_path)
    result = _run("--root", str(tmp_path))
    assert result.returncode == 1
    lines = result.stdout.splitlines()
    assert any(line.startswith("CONTRACT-CHECK leak_scan: EMAIL: ") for line in lines)
    assert all(key in lines[-1] for key in ("files=", "values_strict=", "values_human=", "values_all="))
