"""Planted-violation tests for ``contracts/tools/example_check.py`` (FR-013, FR-021, FR-025).

One committed fixture root, ``contracts/tools/fixtures/example_check/``, holds a clean control module
(``clean``: a file example and an inline example, both valid, one with a ``date-time``) and one module
per planted violation, plus ``manifest.json`` listing the examples each module is required to carry.
Every code is asserted on its own module while the control stays clean in the same run. The real
``mission-status`` module is then checked against the committed required-example manifest, and a
copy of it with one planted defect at a time must fail loudly.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = REPO_ROOT / "contracts"
TOOLS_DIR = CONTRACTS / "tools"
FIXTURE_ROOT = TOOLS_DIR / "fixtures" / "example_check"
MANIFEST = FIXTURE_ROOT / "manifest.json"
REAL_MANIFEST = FIXTURE_ROOT / "required_examples.json"
SCRIPT = TOOLS_DIR / "example_check.py"
MODULE = CONTRACTS / "mission-status"

PLANTED = {
    "v_invalid": ["EXAMPLE_INVALID"],
    "v_extra_property": ["EXAMPLE_INVALID"],
    "v_bad_date_time": ["EXAMPLE_INVALID"],
    "v_orphan": ["ORPHAN_EXAMPLE"],
    "v_validates_nothing": ["EXAMPLE_VALIDATES_NOTHING"],
    "v_unreachable": ["EXAMPLE_VALIDATES_NOTHING"],
    "v_non_schema_reference": ["EXAMPLE_VALIDATES_NOTHING"],
    "v_required_missing": ["REQUIRED_EXAMPLE_MISSING"],
    "v_required_wrong_schema": ["REQUIRED_EXAMPLE_MISSING"],
}
EXIT2 = {
    "zero_examples": "ZERO_EXAMPLES",
    "manifest_missing_module": "MANIFEST_MODULE_MISSING",
    "manifest_empty": "MANIFEST_EMPTY",
    "manifest_unreadable": "MANIFEST_UNREADABLE",
    "resolve_failed": "RESOLVE_FAILED",
    "no_module": "NO_MODULE",
}


@pytest.fixture(scope="module")
def examples() -> Any:
    sys.path.insert(0, str(TOOLS_DIR))
    try:
        spec = importlib.util.spec_from_file_location("example_check_under_test", SCRIPT)
        assert spec is not None and spec.loader is not None, f"cannot load {SCRIPT}"
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(TOOLS_DIR))
    return module


@pytest.fixture(scope="module")
def planted_report(examples: Any) -> Any:
    return examples.check(FIXTURE_ROOT, MANIFEST)


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


def test_the_clean_control_has_no_finding_and_is_counted(examples: Any, planted_report: Any) -> None:
    assert "clean" not in _by_module(planted_report.findings)
    assert planted_report.blocked == []
    clean = examples.check(FIXTURE_ROOT, MANIFEST, modules=("clean",))
    assert clean.findings == [] and clean.exit_code == 0
    assert clean.counts == {"examples": 2, "validated": 2}


def test_a_malformed_date_time_is_rejected_by_the_one_format_policy(planted_report: Any) -> None:
    finding = next(f for f in planted_report.findings if f.subject.startswith("v_bad_date_time:"))
    assert "date-time" in finding.detail and "Thing.date.yaml" in finding.subject


def test_an_extra_property_names_the_property(planted_report: Any) -> None:
    finding = next(f for f in planted_report.findings if f.subject.startswith("v_extra_property:"))
    assert "surplus" in finding.detail


def test_findings_name_the_example(planted_report: Any) -> None:
    orphan = next(f for f in planted_report.findings if f.code == "ORPHAN_EXAMPLE")
    assert orphan.subject == "v_orphan:examples/Thing.unused.yaml"
    missing = [f.subject for f in planted_report.findings if f.code == "REQUIRED_EXAMPLE_MISSING"]
    assert sorted(missing) == ["v_required_missing:Thing:Thing.discarded.yaml", "v_required_wrong_schema:Other:Thing.ok.yaml"]


@pytest.mark.parametrize(("case", "code"), sorted(EXIT2.items()))
def test_a_check_that_cannot_do_its_job_exits_two_with_its_code(examples: Any, case: str, code: str) -> None:
    root = FIXTURE_ROOT / "exit2" / case
    report = examples.check(root, root / "manifest.json")
    assert [f.code for f in report.blocked][:1] == [code]
    assert report.exit_code == 2
    result = _run("--root", str(root), "--manifest", str(root / "manifest.json"))
    assert result.returncode == 2
    assert f"CONTRACT-CHECK example_check: {code}" in result.stdout
    assert result.stdout.rstrip().splitlines()[-1].startswith("counts: examples=")


def test_a_missing_manifest_file_exits_two(examples: Any, tmp_path: Path) -> None:
    report = examples.check(FIXTURE_ROOT, tmp_path / "absent.json")
    assert [f.code for f in report.blocked] == ["MANIFEST_UNREADABLE"]


def test_command_line_output_grammar_and_exit_status() -> None:
    result = _run("--root", str(FIXTURE_ROOT), "--manifest", str(MANIFEST))
    assert result.returncode == 1
    lines = result.stdout.splitlines()
    assert lines[-1].startswith("counts: examples=") and " validated=" in lines[-1]
    assert any(line.startswith("CONTRACT-CHECK example_check: EXAMPLE_INVALID: v_invalid:") for line in lines)
    clean = _run("--root", str(FIXTURE_ROOT), "--manifest", str(MANIFEST), "--module", "clean")
    assert clean.returncode == 0, clean.stdout
    assert clean.stdout.splitlines()[-1] == "counts: examples=2 validated=2"


# -- the real module and its required-example manifest -------------------------


def _real_manifest() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(REAL_MANIFEST.read_text(encoding="utf-8"))
    return document


def test_the_real_manifest_asks_for_a_case_per_resource_event_kind_and_page_position() -> None:
    required = {(entry["schema"], entry["example"]) for entry in _real_manifest()["modules"]["mission-status"]}
    schemas = {schema for schema, _ in required}
    for resource in ("Project", "MissionOverview", "MissionOverviewPage", "MissionDetail", "WorkPackage"):
        assert resource in schemas, resource
    for kind in ("StatusTransitionEvent", "MissionLifecycleEvent", "LogTruncatedEvent", "StreamRefusal"):
        assert kind in schemas, kind
    assert ("MissionOverview", "MissionOverview.discarded.yaml") in required
    assert ("MissionOverview", "MissionOverview.provisional.yaml") in required
    assert ("WorkPackage", "WorkPackage.provisional.yaml") in required
    for position in ("first", "middle", "last"):
        assert ("MissionOverviewPage", f"MissionOverviewPage.{position}.yaml") in required


def test_the_real_mission_status_module_passes_with_a_floor() -> None:
    result = _run("--root", str(CONTRACTS), "--module", "mission-status")
    assert result.returncode == 0, result.stdout
    counts = dict(pair.split("=") for pair in result.stdout.splitlines()[-1].removeprefix("counts: ").split())
    assert int(counts["examples"]) >= 30 and counts["examples"] == counts["validated"]


@pytest.fixture
def module_copy(tmp_path: Path) -> Path:
    shutil.copytree(MODULE, tmp_path / "contracts" / "mission-status")
    shutil.copytree(CONTRACTS / "_shared", tmp_path / "contracts" / "_shared")
    return tmp_path / "contracts"


def _check_copy(root: Path) -> subprocess.CompletedProcess[str]:
    return _run("--root", str(root), "--module", "mission-status")


def test_a_real_copy_without_the_discarded_example_fails_the_manifest(module_copy: Path) -> None:
    schema = module_copy / "mission-status" / "schemas" / "MissionOverview.yaml"
    document = yaml.safe_load(schema.read_text(encoding="utf-8"))
    document["examples"] = [entry for entry in document["examples"] if "discarded" not in entry["$ref"]]
    schema.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    (module_copy / "mission-status" / "examples" / "MissionOverview.discarded.yaml").unlink()
    index = module_copy / "mission-status" / "examples" / "_index.yaml"
    index.write_text(index.read_text(encoding="utf-8").replace("  - MissionOverview.discarded.yaml\n", ""), encoding="utf-8")
    result = _check_copy(module_copy)
    assert result.returncode == 1
    assert "REQUIRED_EXAMPLE_MISSING: mission-status:MissionOverview:MissionOverview.discarded.yaml" in result.stdout


def test_a_real_copy_with_a_malformed_timestamp_fails(module_copy: Path) -> None:
    target = module_copy / "mission-status" / "examples" / "MissionOverview.populated.yaml"
    document = yaml.safe_load(target.read_text(encoding="utf-8"))
    document["createdAt"] = "2026-13-45T25:61:00Z"
    target.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    result = _check_copy(module_copy)
    assert result.returncode == 1
    assert "EXAMPLE_INVALID: mission-status:examples/MissionOverview.populated.yaml" in result.stdout


def test_a_real_copy_with_an_unreferenced_example_fails(module_copy: Path) -> None:
    (module_copy / "mission-status" / "examples" / "Stray.yaml").write_text("a: 1\n", encoding="utf-8")
    result = _check_copy(module_copy)
    assert result.returncode == 1
    assert "ORPHAN_EXAMPLE: mission-status:examples/Stray.yaml" in result.stdout
