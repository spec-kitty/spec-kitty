"""Planted-violation tests for ``contracts/tools/event_mapping_check.py`` (FR-007, FR-021, FR-025).

One committed fixture root, ``contracts/tools/fixtures/event_mapping_check/``, holds a clean control
module (three event names, three schemas, one of them a lifecycle schema whose ``eventType`` enum is the
contract-owned allow-list) and one module per planted violation, plus a stand-in for the runtime's
lifecycle module under ``code/``. Each code is asserted on its own module while the control stays clean
in the same run. The informational ``LIFECYCLE_TYPE_NOT_FORWARDED`` lines never change the exit status.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest

pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = REPO_ROOT / "contracts"
TOOLS_DIR = CONTRACTS / "tools"
FIXTURE_ROOT = TOOLS_DIR / "fixtures" / "event_mapping_check"
LIFECYCLE_STAND_IN = FIXTURE_ROOT / "code" / "lifecycle_events.py"
SCRIPT = TOOLS_DIR / "event_mapping_check.py"

PLANTED = {
    "v_name_without_schema": ["NAME_WITHOUT_SCHEMA"],
    "v_schema_without_name": ["SCHEMA_WITHOUT_NAME"],
    "v_schema_multi_name": ["SCHEMA_MULTI_NAME"],
}
EXIT2 = {
    "zero_event_names": "ZERO_EVENT_NAMES",
    "no_stream": "ZERO_EVENT_NAMES",
    "resolve_failed": "RESOLVE_FAILED",
    "no_module": "NO_MODULE",
}


@pytest.fixture(scope="module")
def mapping() -> Any:
    sys.path.insert(0, str(TOOLS_DIR))
    try:
        spec = importlib.util.spec_from_file_location("event_mapping_check_under_test", SCRIPT)
        assert spec is not None and spec.loader is not None, f"cannot load {SCRIPT}"
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(TOOLS_DIR))
    return module


@pytest.fixture(scope="module")
def planted_report(mapping: Any) -> Any:
    return mapping.check(FIXTURE_ROOT, lifecycle_source=LIFECYCLE_STAND_IN)


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


def test_the_clean_control_has_no_finding(planted_report: Any) -> None:
    assert "clean" not in _by_module(planted_report.findings)
    assert planted_report.blocked == []


def test_each_finding_names_the_name_or_the_schema(planted_report: Any) -> None:
    subjects = {f.code: f.subject for f in planted_report.findings}
    assert subjects["NAME_WITHOUT_SCHEMA"] == "v_name_without_schema:ghost-event"
    assert subjects["SCHEMA_WITHOUT_NAME"] == "v_schema_without_name:LogTruncatedEvent"
    assert subjects["SCHEMA_MULTI_NAME"] == "v_schema_multi_name:LogTruncatedEvent"
    assert "log-truncated" in next(f.detail for f in planted_report.findings if f.code == "SCHEMA_MULTI_NAME")


def test_the_clean_module_is_counted_and_lists_the_types_the_contract_does_not_forward(mapping: Any) -> None:
    report = mapping.check(FIXTURE_ROOT, modules=("clean",), lifecycle_source=LIFECYCLE_STAND_IN)
    assert report.findings == [] and report.exit_code == 0
    assert report.counts == {"event_names": 3, "event_schemas": 3, "lifecycle_not_forwarded": 2}
    assert [(item.code, item.subject) for item in report.info] == [
        ("LIFECYCLE_TYPE_NOT_FORWARDED", "MissionReopened"),
        ("LIFECYCLE_TYPE_NOT_FORWARDED", "WPCreated"),
    ]


def test_informational_lines_do_not_change_the_exit_status() -> None:
    result = _run("--root", str(FIXTURE_ROOT), "--module", "clean", "--lifecycle-source", str(LIFECYCLE_STAND_IN))
    assert result.returncode == 0, result.stdout
    assert "CONTRACT-CHECK event_mapping_check: LIFECYCLE_TYPE_NOT_FORWARDED: WPCreated" in result.stdout
    assert result.stdout.splitlines()[-1] == "counts: event_names=3 event_schemas=3 lifecycle_not_forwarded=2"


@pytest.mark.parametrize(("case", "code"), sorted(EXIT2.items()))
def test_a_check_that_cannot_do_its_job_exits_two_with_its_code(mapping: Any, case: str, code: str) -> None:
    root = FIXTURE_ROOT / "exit2" / case
    report = mapping.check(root, lifecycle_source=LIFECYCLE_STAND_IN)
    assert [f.code for f in report.blocked][:1] == [code]
    assert report.exit_code == 2
    result = _run("--root", str(root), "--lifecycle-source", str(LIFECYCLE_STAND_IN))
    assert result.returncode == 2
    assert f"CONTRACT-CHECK event_mapping_check: {code}" in result.stdout
    assert result.stdout.rstrip().splitlines()[-1].startswith("counts: event_names=")


@pytest.mark.parametrize("source", [FIXTURE_ROOT / "code" / "no_constant.py", FIXTURE_ROOT / "code" / "absent.py"])
def test_an_unreadable_lifecycle_source_exits_two(mapping: Any, source: Path) -> None:
    report = mapping.check(FIXTURE_ROOT / "exit2" / "lifecycle_unreadable", lifecycle_source=source)
    assert [f.code for f in report.blocked] == ["LIFECYCLE_SOURCE_UNREADABLE"]
    assert report.exit_code == 2


def test_command_line_output_grammar_and_exit_status() -> None:
    result = _run("--root", str(FIXTURE_ROOT), "--lifecycle-source", str(LIFECYCLE_STAND_IN))
    assert result.returncode == 1
    lines = result.stdout.splitlines()
    assert lines[-1].startswith("counts: event_names=") and " event_schemas=" in lines[-1] and " lifecycle_not_forwarded=" in lines[-1]
    assert any(line.startswith("CONTRACT-CHECK event_mapping_check: NAME_WITHOUT_SCHEMA: v_name_without_schema:ghost-event") for line in lines)


def test_the_real_runtime_set_has_twelve_members_and_the_contract_forwards_seven(mapping: Any) -> None:
    types = mapping.read_lifecycle_types(REPO_ROOT / "src" / "specify_cli" / "status" / "lifecycle_events.py")
    assert len(types) == 12
    assert {"MissionCreated", "PlanCompleted", "WPCreated", "ReviewerSelfApproval", "MissionReopened", "FollowUpRecorded"} <= types


def test_the_real_mission_status_module_passes_with_its_three_names() -> None:
    result = _run("--root", str(CONTRACTS), "--module", "mission-status")
    assert result.returncode == 0, result.stdout
    assert result.stdout.splitlines()[-1] == "counts: event_names=3 event_schemas=3 lifecycle_not_forwarded=5"
    assert result.stdout.count("LIFECYCLE_TYPE_NOT_FORWARDED") == 5
