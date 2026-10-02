"""Planted-violation tests for ``contracts/tools/provisional_check.py`` (FR-011, D-7, FR-021, FR-025).

One committed fixture root, ``contracts/tools/fixtures/provisional_check/``, holds a clean control
module (``clean``: staleness and next action marked and nullable, a schema, a parameter and an
operation marked, every element named in the module CHANGELOG's Provisional section) and one
module per planted violation. Each rule is asserted by its stable code on its own module while the
control stays clean in the same run.
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
TOOLS_DIR = REPO_ROOT / "contracts" / "tools"
FIXTURE_ROOT = TOOLS_DIR / "fixtures" / "provisional_check"
SCRIPT = TOOLS_DIR / "provisional_check.py"

# module directory in the fixture root -> exactly the codes it must produce, sorted
PLANTED = {
    "v_missing_marker_staleness": ["MISSING_MARKER"],
    "v_missing_marker_next_action": ["MISSING_MARKER"],
    "v_undescribed_true": ["UNDESCRIBED_MARKER"],
    "v_undescribed_empty": ["UNDESCRIBED_MARKER"],
    "v_undescribed_short": ["UNDESCRIBED_MARKER"],
    "v_undescribed_no_key": ["UNDESCRIBED_MARKER"],
    "v_not_nullable": ["NOT_NULLABLE"],
    "v_not_in_changelog": ["NOT_IN_CHANGELOG"],
    "v_no_changelog_section": ["NOT_IN_CHANGELOG"] * 5,
    "v_no_changelog_file": ["NOT_IN_CHANGELOG"] * 5,
}
EXIT2 = {"zero_provisional": "ZERO_PROVISIONAL", "resolve_failed": "RESOLVE_FAILED", "no_module": "NO_MODULE"}


@pytest.fixture(scope="module")
def provisional() -> Any:
    sys.path.insert(0, str(TOOLS_DIR))
    try:
        spec = importlib.util.spec_from_file_location("provisional_check_under_test", SCRIPT)
        assert spec is not None and spec.loader is not None, f"cannot load {SCRIPT}"
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(TOOLS_DIR))
    return module


@pytest.fixture(scope="module")
def planted_report(provisional: Any) -> Any:
    return provisional.check(FIXTURE_ROOT)


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


def test_the_clean_control_has_no_finding_and_the_floor_is_met(planted_report: Any) -> None:
    assert "clean" not in _by_module(planted_report.findings)
    assert planted_report.blocked == []
    assert planted_report.counts["provisional_elements"] >= 4


def test_the_clean_module_counts_each_element_kind_once(provisional: Any) -> None:
    report = provisional.check(FIXTURE_ROOT, modules=("clean",))
    assert report.findings == []
    # nextAction, staleness, the Cursor schema, the streamCursor parameter and the operation
    assert report.counts["provisional_elements"] == 5


def test_a_missing_marker_names_the_property(planted_report: Any) -> None:
    subjects = {f.subject for f in planted_report.findings if f.code == "MISSING_MARKER"}
    assert subjects == {"v_missing_marker_staleness:Thing.staleness", "v_missing_marker_next_action:Thing.nextAction"}


def test_a_nullable_provisional_field_may_use_a_type_array_or_a_null_branch(provisional: Any) -> None:
    assert provisional.is_nullable({"type": ["string", "null"]})
    assert provisional.is_nullable({"oneOf": [{"type": "object"}, {"type": "null"}]})
    assert provisional.is_nullable({"anyOf": [{"type": "string"}, {"type": ["null"]}]})
    assert not provisional.is_nullable({"type": "string"})
    assert not provisional.is_nullable({"oneOf": [{"type": "object"}, {"type": "string"}]})


@pytest.mark.parametrize(("case", "code"), sorted(EXIT2.items()))
def test_a_check_that_cannot_do_its_job_exits_two_with_its_code(provisional: Any, case: str, code: str) -> None:
    root = FIXTURE_ROOT / "exit2" / case
    report = provisional.check(root)
    assert [f.code for f in report.blocked][:1] == [code]
    assert report.exit_code == 2
    result = _run("--root", str(root))
    assert result.returncode == 2
    assert f"CONTRACT-CHECK provisional_check: {code}" in result.stdout
    assert result.stdout.rstrip().splitlines()[-1].startswith("counts: provisional_elements=")


def test_command_line_output_grammar_and_exit_status() -> None:
    result = _run("--root", str(FIXTURE_ROOT))
    assert result.returncode == 1
    lines = result.stdout.splitlines()
    assert lines[-1].startswith("counts: provisional_elements=")
    assert any(line.startswith("CONTRACT-CHECK provisional_check: UNDESCRIBED_MARKER: v_undescribed_true:") for line in lines)
    clean = _run("--root", str(FIXTURE_ROOT), "--module", "clean")
    assert clean.returncode == 0, clean.stdout
    assert clean.stdout.splitlines()[-1] == "counts: provisional_elements=5"


def test_the_real_mission_status_module_passes_with_a_floor() -> None:
    result = _run("--root", str(REPO_ROOT / "contracts"), "--module", "mission-status")
    assert result.returncode == 0, result.stdout
    counts = dict(pair.split("=") for pair in result.stdout.splitlines()[-1].removeprefix("counts: ").split())
    assert int(counts["provisional_elements"]) >= 7
