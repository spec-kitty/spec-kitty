"""Planted-violation tests for ``contracts/tools/gradle_pin_check.py`` (FR-018, NFR-003).

One committed fixture root, ``contracts/tools/fixtures/gradle_pin_check/``, holds a clean control (a manifest pinning Gradle and the
openapi-generator plugin, a ``build.gradle`` and verification metadata that agree with it) and one committed plant (``v_build_mismatch``).
The other plants are made at run time by copying the control and changing one value, so each rule is asserted on its own and the
control stays clean. The check never writes a file.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.contract._loader import load_tool

pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = REPO_ROOT / "contracts" / "tools"
FIXTURE_ROOT = TOOLS_DIR / "fixtures" / "gradle_pin_check"
SCRIPT = TOOLS_DIR / "gradle_pin_check.py"
WRAPPER = "contracts/gradle/wrapper/gradle-wrapper.properties"
WORKFLOW = ".github/workflows/contracts.yml"
GRADLE_PIN = "8.0.1"
PLUGIN_PIN = "7.1.0"


@pytest.fixture(scope="module")
def tool() -> Iterator[Any]:
    with pytest.MonkeyPatch.context() as mp:
        yield load_tool(mp, SCRIPT, "gradle_pin_check_under_test", syspath=TOOLS_DIR)


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *arguments], capture_output=True, text=True, check=False, cwd=REPO_ROOT)


def _copy(tmp_path: Path) -> Path:
    root = tmp_path / "root"
    shutil.copytree(FIXTURE_ROOT / "clean", root)
    return root


def _edit(root: Path, relative: str, old: str, new: str) -> None:
    path = root / relative
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_the_clean_control_has_no_finding_and_compares_every_value(tool: Any) -> None:
    report = tool.check(FIXTURE_ROOT / "clean")
    assert report.findings == []
    assert report.blocked == []
    assert report.exit_code == 0
    assert report.counts == {"pinned": 2, "compared": 5}


def test_the_committed_plant_gives_the_mismatch_code_naming_both_versions(tool: Any) -> None:
    report = tool.check(FIXTURE_ROOT / "v_build_mismatch")
    (finding,) = report.findings
    assert finding.code == "GRADLE_PIN_MISMATCH"
    assert finding.subject == "contracts/build.gradle"
    assert "7.0.9" in finding.detail
    assert PLUGIN_PIN in finding.detail
    assert report.exit_code == 1


def test_the_real_repository_build_agrees_with_its_pins(tool: Any) -> None:
    report = tool.check(REPO_ROOT)
    assert report.findings == []
    assert report.blocked == []
    assert report.counts["pinned"] == 2
    assert report.counts["compared"] >= 5


@pytest.mark.parametrize(
    ("relative", "old", "new", "subject"),
    [
        ("contracts/build.gradle", PLUGIN_PIN, "7.1.1", "contracts/build.gradle"),
        (
            "contracts/gradle/verification-metadata.xml",
            f'name="openapi-generator-gradle-plugin" version="{PLUGIN_PIN}"',
            'name="openapi-generator-gradle-plugin" version="7.0.0"',
            "contracts/gradle/verification-metadata.xml",
        ),
        ("contracts/tools/pins.json", f"gradle-{GRADLE_PIN}-bin.zip", "gradle-8.0.0-bin.zip", "contracts/tools/pins.json"),
    ],
    ids=["build-gradle", "verification-metadata", "manifest-url"],
)
def test_a_changed_value_is_a_mismatch(tool: Any, tmp_path: Path, relative: str, old: str, new: str, subject: str) -> None:
    root = _copy(tmp_path)
    _edit(root, relative, old, new)
    report = tool.check(root)
    assert [(f.code, f.subject) for f in report.findings] == [("GRADLE_PIN_MISMATCH", subject)]
    assert report.blocked == []


def test_a_pin_bumped_without_the_build_is_a_mismatch(tool: Any, tmp_path: Path) -> None:
    root = _copy(tmp_path)
    _edit(root, "contracts/tools/pins.json", f'"version": "{PLUGIN_PIN}"', '"version": "7.2.0"')
    codes = {f.code for f in tool.check(root).findings}
    assert codes == {"GRADLE_PIN_MISMATCH"}


def test_a_wrapper_distribution_is_compared_only_when_it_exists(tool: Any, tmp_path: Path) -> None:
    root = _copy(tmp_path)
    assert tool.check(root).counts["compared"] == 5
    _write(root, WRAPPER, f"distributionUrl=https\\://services.gradle.org/distributions/gradle-{GRADLE_PIN}-bin.zip\n")
    assert tool.check(root).findings == []
    _write(root, WRAPPER, "distributionUrl=https\\://services.gradle.org/distributions/gradle-8.0.0-bin.zip\n")
    report = tool.check(root)
    assert [(f.code, f.subject) for f in report.findings] == [("GRADLE_PIN_MISMATCH", WRAPPER)]


def test_a_workflow_gradle_version_input_is_compared(tool: Any, tmp_path: Path) -> None:
    root = _copy(tmp_path)
    workflow = "jobs:\n  build:\n    steps:\n      - uses: ./local\n        with:\n          gradle-version: '{}'\n"
    _write(root, WORKFLOW, workflow.format(GRADLE_PIN))
    assert tool.check(root).findings == []
    _write(root, WORKFLOW, workflow.format("8.0.0"))
    report = tool.check(root)
    assert [(f.code, f.subject) for f in report.findings] == [("GRADLE_PIN_MISMATCH", f"{WORKFLOW}:build")]


@pytest.mark.parametrize(
    ("relative", "text", "code"),
    [
        ("contracts/build.gradle", None, "GRADLE_PIN_UNREADABLE"),
        ("contracts/build.gradle", "plugins {\n}\n", "GRADLE_PIN_UNPARSEABLE"),
        ("contracts/gradle/verification-metadata.xml", None, "GRADLE_PIN_UNREADABLE"),
        ("contracts/gradle/verification-metadata.xml", "<verification-metadata", "GRADLE_PIN_UNREADABLE"),
        ("contracts/gradle/verification-metadata.xml", "<verification-metadata><components/></verification-metadata>", "GRADLE_PIN_UNPARSEABLE"),
        ("contracts/tools/pins.json", None, "GRADLE_PIN_UNREADABLE"),
        ("contracts/tools/pins.json", "{not json", "GRADLE_PIN_UNREADABLE"),
        ("contracts/tools/pins.json", '{"tools": []}', "GRADLE_PIN_UNREADABLE"),
        (WRAPPER, "distributionBase=GRADLE_USER_HOME\n", "GRADLE_PIN_UNPARSEABLE"),
        (WORKFLOW, "jobs: [unclosed\n  build: {\n", "GRADLE_PIN_UNREADABLE"),
    ],
    ids=[
        "build-missing",
        "build-no-version",
        "metadata-missing",
        "metadata-not-xml",
        "metadata-no-component",
        "pins-missing",
        "pins-not-json",
        "pins-no-tools",
        "wrapper-no-url",
        "workflow-not-yaml",
    ],
)
def test_a_file_that_cannot_be_judged_blocks_instead_of_passing(tool: Any, tmp_path: Path, relative: str, text: str | None, code: str) -> None:
    root = _copy(tmp_path)
    if text is None:
        (root / relative).unlink()
    else:
        _write(root, relative, text)
    report = tool.check(root)
    assert code in {f.code for f in report.blocked}
    assert report.exit_code == 2


def test_nothing_compared_is_not_a_pass(tool: Any, tmp_path: Path) -> None:
    root = _copy(tmp_path)
    _edit(
        root,
        "contracts/tools/pins.json",
        "https://example.invalid/m2/openapi-generator-gradle-plugin/7.1.0/openapi-generator-gradle-plugin-7.1.0.jar",
        "https://example.invalid/x",
    )
    (root / "contracts" / "build.gradle").unlink()
    assert tool.check(root).exit_code == 2


def test_the_script_prints_the_rendered_finding_the_counts_line_and_the_exit_code(tmp_path: Path) -> None:
    clean = _run("--root", str(FIXTURE_ROOT / "clean"))
    assert (clean.returncode, clean.stdout.strip()) == (0, "counts: pinned=2 compared=5")
    plant = _run("--root", str(FIXTURE_ROOT / "v_build_mismatch"))
    lines = plant.stdout.splitlines()
    assert plant.returncode == 1
    assert lines[0].startswith("CONTRACT-CHECK gradle_pin_check: GRADLE_PIN_MISMATCH: contracts/build.gradle: ")
    assert lines[-1] == "counts: pinned=2 compared=5"
    root = _copy(tmp_path)
    (root / "contracts" / "build.gradle").unlink()
    blocked = _run("--root", str(root))
    assert blocked.returncode == 2
    assert "GRADLE_PIN_UNREADABLE" in blocked.stdout
