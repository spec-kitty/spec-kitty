"""Planted-violation tests for ``contracts/tools/enum_pin_check.py`` (FR-008, FR-021, FR-025).

One committed fixture root, ``contracts/tools/fixtures/enum_pin_check/``, holds a clean control module
and one module per planted violation (a value added, removed or swapped; a board-grouping schema or
property), with ``pins.json`` keyed by module. The real pin file ``contracts/tools/enum_pins.json`` is
the default of the script and is checked against the real ``mission-status`` module.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.contract._loader import load_tool

pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = REPO_ROOT / "contracts"
TOOLS_DIR = CONTRACTS / "tools"
FIXTURE_ROOT = TOOLS_DIR / "fixtures" / "enum_pin_check"
PINS = FIXTURE_ROOT / "pins.json"
REAL_PINS = TOOLS_DIR / "enum_pins.json"
SCRIPT = TOOLS_DIR / "enum_pin_check.py"

PLANTED = {
    "v_value_added": ["ENUM_VALUE_ADDED"],
    "v_value_removed": ["ENUM_VALUE_REMOVED"],
    "v_value_swapped": ["ENUM_VALUE_ADDED", "ENUM_VALUE_REMOVED"],
    "v_board_columns_schema": ["BOARD_GROUPING_PRESENT"],
    "v_board_columns_property": ["BOARD_GROUPING_PRESENT"],
}
EXIT2 = {
    "pin_empty": "PIN_EMPTY",
    "pin_list_empty": "PIN_EMPTY",
    "no_pinned_module": "PIN_EMPTY",
    "enum_unreadable": "ENUM_UNREADABLE",
    "enum_not_an_enum": "ENUM_UNREADABLE",
    "pins_unreadable": "PINS_UNREADABLE",
    "resolve_failed": "RESOLVE_FAILED",
    "no_module": "NO_MODULE",
}
STATUS_LANES = ["planned", "claimed", "in_progress", "for_review", "in_review", "approved", "done", "blocked", "canceled"]


@pytest.fixture(scope="module")
def pin() -> Iterator[Any]:
    with pytest.MonkeyPatch.context() as mp:
        yield load_tool(mp, SCRIPT, "enum_pin_check_under_test", syspath=TOOLS_DIR)


@pytest.fixture(scope="module")
def planted_report(pin: Any) -> Any:
    return pin.check(FIXTURE_ROOT, PINS)


def _by_module(findings: list[Any]) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = defaultdict(list)
    for finding in findings:
        grouped[finding.subject.split(":")[0]].append(finding)
    return grouped


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *arguments], capture_output=True, text=True, check=False, cwd=REPO_ROOT)


@pytest.mark.parametrize(("module", "codes"), sorted(PLANTED.items()))
def test_each_planted_violation_gives_its_stable_code(planted_report: Any, module: str, codes: list[str]) -> None:
    grouped = _by_module(planted_report.findings)
    assert sorted(f.code for f in grouped.get(module, [])) == codes


def test_the_clean_controls_have_no_finding(planted_report: Any) -> None:
    grouped = _by_module(planted_report.findings)
    assert "clean" not in grouped
    assert "clean_dashboard_word" not in grouped, "a name that merely contains the letters of board is not a board grouping"
    assert planted_report.blocked == []


def test_a_finding_names_the_enum_and_the_value(planted_report: Any) -> None:
    by_code = {f.code: f for f in planted_report.findings if f.subject.startswith(("v_value_added:", "v_value_removed:"))}
    assert by_code["ENUM_VALUE_ADDED"].subject == "v_value_added:Color" and "violet" in by_code["ENUM_VALUE_ADDED"].detail
    assert by_code["ENUM_VALUE_REMOVED"].subject == "v_value_removed:Color" and "blue" in by_code["ENUM_VALUE_REMOVED"].detail


def test_the_counts_are_the_pinned_enums_and_their_current_values(pin: Any) -> None:
    report = pin.check(FIXTURE_ROOT, PINS, modules=("clean",))
    assert report.findings == [] and report.counts == {"enums": 2, "values": 5}


@pytest.mark.parametrize(("case", "code"), sorted(EXIT2.items()))
def test_a_check_that_cannot_do_its_job_exits_two_with_its_code(pin: Any, case: str, code: str, tmp_path: Path) -> None:
    root = FIXTURE_ROOT / "exit2" / case
    if case == "pins_unreadable":
        # the invalid pin file is written at run time: the leak scan parses every committed .json
        root = tmp_path / case
        shutil.copytree(FIXTURE_ROOT / "exit2" / case, root)
        (root / "pins.json").write_text("{not json", encoding="utf-8")
    report = pin.check(root, root / "pins.json")
    assert [f.code for f in report.blocked][:1] == [code]
    assert report.exit_code == 2
    result = _run("--root", str(root), "--pins", str(root / "pins.json"))
    assert result.returncode == 2
    assert f"CONTRACT-CHECK enum_pin_check: {code}" in result.stdout
    assert result.stdout.rstrip().splitlines()[-1].startswith("counts: enums=")


def test_a_missing_pin_file_exits_two(pin: Any, tmp_path: Path) -> None:
    assert [f.code for f in pin.check(FIXTURE_ROOT, tmp_path / "absent.json").blocked] == ["PINS_UNREADABLE"]


def test_command_line_output_grammar_and_exit_status() -> None:
    result = _run("--root", str(FIXTURE_ROOT), "--pins", str(PINS))
    assert result.returncode == 1
    lines = result.stdout.splitlines()
    assert lines[-1].startswith("counts: enums=") and " values=" in lines[-1]
    assert any(line.startswith("CONTRACT-CHECK enum_pin_check: ENUM_VALUE_ADDED: v_value_added:Color") for line in lines)
    clean = _run("--root", str(FIXTURE_ROOT), "--pins", str(PINS), "--module", "clean")
    assert clean.returncode == 0, clean.stdout
    assert clean.stdout.splitlines()[-1] == "counts: enums=2 values=5"


# -- the real pin file and the real module ---------------------------------------


def _real_pins() -> dict[str, dict[str, list[str]]]:
    document: dict[str, dict[str, list[str]]] = json.loads(REAL_PINS.read_text(encoding="utf-8"))
    return document


def test_the_real_pin_file_pins_the_three_vocabularies() -> None:
    pins = _real_pins()["mission-status"]
    assert pins["StatusLane"] == STATUS_LANES
    assert pins["LifecycleStatus"] == ["active", "planned", "done", "draft", "discarded"]
    assert sorted(pins["Topology"]) == sorted(["lanes", "single_branch", "coord", "lanes_with_coord", "unknown"])
    assert len(pins["StatusLane"]) == 9 and len(pins["LifecycleStatus"]) == 5 and len(pins["Topology"]) == 5


def test_the_real_mission_status_module_passes_against_the_default_pin_file() -> None:
    result = _run("--root", str(CONTRACTS), "--module", "mission-status")
    assert result.returncode == 0, result.stdout
    assert result.stdout.splitlines()[-1] == "counts: enums=7 values=43"


@pytest.fixture
def module_copy(tmp_path: Path) -> Path:
    shutil.copytree(CONTRACTS / "mission-status", tmp_path / "contracts" / "mission-status")
    shutil.copytree(CONTRACTS / "_shared", tmp_path / "contracts" / "_shared")
    return tmp_path / "contracts"


def test_a_real_copy_with_a_tenth_status_lane_fails(module_copy: Path) -> None:
    target = module_copy / "mission-status" / "schemas" / "StatusLane.yaml"
    document = yaml.safe_load(target.read_text(encoding="utf-8"))
    document["enum"].append("genesis")
    target.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    result = _run("--root", str(module_copy), "--module", "mission-status")
    assert result.returncode == 1
    assert "ENUM_VALUE_ADDED: mission-status:StatusLane" in result.stdout and "genesis" in result.stdout


def test_a_real_copy_without_a_topology_value_fails(module_copy: Path) -> None:
    target = module_copy / "mission-status" / "schemas" / "Topology.yaml"
    document = yaml.safe_load(target.read_text(encoding="utf-8"))
    document["enum"].remove("unknown")
    target.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    result = _run("--root", str(module_copy), "--module", "mission-status")
    assert result.returncode == 1
    assert "ENUM_VALUE_REMOVED: mission-status:Topology" in result.stdout
