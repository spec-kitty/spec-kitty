"""Behaviour tests for the ``p0_repro`` plugin (``tests/_support/p0_repro.py``).

Open-P0 red-first reproductions must never run outside the nightly p0-repro
lane, must name their issue when they fail, and must be reported when they
start passing. The production path is pinned by driving pytest in a
*subprocess* over a synthetic test file with the real plugin loaded
(``pytester`` is not enabled in this repository); the pure helpers are called
directly.
"""

from __future__ import annotations

import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from tests._support.p0_repro import (
    RUN_P0_REPRO_ENV_VAR,
    failure_banner,
    p0_repro_opted_in,
    pinned_issue,
)

pytestmark = [pytest.mark.fast, pytest.mark.unit]

_REPO_ROOT = Path(__file__).resolve().parents[2]

_SYNTHETIC = """
import pytest

def test_plain():
    assert True

@pytest.mark.p0_repro(issue=4242)
def test_open_bug():
    assert 1 == 2, "bug still reproduces"

@pytest.mark.p0_repro(issue=4243)
def test_fixed_bug():
    assert True

@pytest.mark.p0_repro(issue=4244)
def test_skipped_bug():
    pytest.skip("cannot reproduce here")
"""


def _run(tmp_path: Path, source: str, *args: str, opt_in: bool) -> subprocess.CompletedProcess[str]:
    test_file = tmp_path / "test_synthetic.py"
    test_file.write_text(source, encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in {RUN_P0_REPRO_ENV_VAR, "PYTEST_ADDOPTS"}}
    env["PYTHONPATH"] = str(_REPO_ROOT)
    if opt_in:
        env[RUN_P0_REPRO_ENV_VAR] = "1"
    argv = [
        sys.executable,
        "-m",
        "pytest",
        "-c",
        os.devnull,
        "--rootdir",
        str(tmp_path),
        "-p",
        "tests._support.p0_repro",
        "-p",
        "no:cacheprovider",
        "-p",
        "no:randomly",
        "-q",
        str(test_file),
        *args,
    ]
    return subprocess.run(argv, cwd=_REPO_ROOT, env=env, capture_output=True, text=True, timeout=120, check=False)


def test_reproductions_are_deselected_without_the_opt_in(tmp_path: Path) -> None:
    proc = _run(tmp_path, _SYNTHETIC, opt_in=False)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "1 passed, 3 deselected" in proc.stdout


def test_a_per_pr_marker_expression_cannot_select_them_without_the_opt_in(tmp_path: Path) -> None:
    proc = _run(tmp_path, _SYNTHETIC, "-m", "p0_repro", opt_in=False)

    assert proc.returncode == 5, proc.stdout + proc.stderr  # nothing collected to run
    assert "4 deselected" in proc.stdout


@pytest.mark.parametrize("xdist_args", [(), ("-n", "2")], ids=["serial", "xdist"])
def test_nightly_lane_names_the_open_issue_and_reports_the_fixed_and_skipped_ones(tmp_path: Path, xdist_args: tuple[str, ...]) -> None:
    if xdist_args:
        pytest.importorskip("xdist")
    junit = tmp_path / "junit.xml"
    proc = _run(tmp_path, _SYNTHETIC, "-m", "p0_repro", f"--junitxml={junit}", *xdist_args, opt_in=True)

    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "1 failed, 1 passed, 1 skipped" in proc.stdout
    assert "[OPEN P0 #4242]" in proc.stdout
    # The passing / skipped notices come from the controller's terminal summary,
    # which under xdist only sees what the workers' reports carry.
    assert "[P0 #4243 REPRO PASSES]" in proc.stdout
    assert "test_fixed_bug" in proc.stdout
    assert "[P0 #4244 REPRO SKIPPED]" in proc.stdout
    assert "test_skipped_bug" in proc.stdout

    cases = {case.get("name"): case for case in ET.parse(junit).getroot().iter("testcase")}
    failure = cases["test_open_bug"].find("failure")
    assert failure is not None
    # The nightly summary (scripts/ci/nightly_xunit.py) surfaces the first
    # non-blank line of the failure: it must be the real assertion, not the banner.
    first_line = next(line for line in (failure.get("message") or failure.text or "").splitlines() if line.strip())
    assert "bug still reproduces" in first_line
    issue_props = [p.get("value") for p in cases["test_open_bug"].iter("property") if p.get("name") == "p0_issue"]
    assert issue_props == ["4242"]


def test_a_marker_without_an_issue_is_a_collection_error_even_when_deselected(tmp_path: Path) -> None:
    source = "import pytest\n\n@pytest.mark.p0_repro\ndef test_unpinned():\n    assert False\n"
    proc = _run(tmp_path, source, opt_in=False)

    assert proc.returncode == pytest.ExitCode.USAGE_ERROR, proc.stdout + proc.stderr
    assert "p0_repro marker must pin a positive issue number" in proc.stdout + proc.stderr
    assert "test_unpinned" in proc.stdout + proc.stderr


@pytest.mark.parametrize(
    ("args", "kwargs", "expected"),
    [
        ((), {"issue": 5613}, 5613),
        ((5613,), {}, 5613),
        ((), {}, None),
        ((), {"issue": 0}, None),
        ((), {"issue": -1}, None),
        ((), {"issue": "5613"}, None),
        ((), {"issue": True}, None),
    ],
)
def test_pinned_issue_accepts_only_a_positive_int(args: tuple[object, ...], kwargs: dict[str, object], expected: int | None) -> None:
    assert pinned_issue(pytest.mark.p0_repro(*args, **kwargs).mark) == expected


@pytest.mark.parametrize(("value", "expected"), [("1", True), ("0", False), ("true", False), ("", False)])
def test_opt_in_is_strictly_the_literal_one(value: str, expected: bool) -> None:
    assert p0_repro_opted_in({RUN_P0_REPRO_ENV_VAR: value}) is expected
    assert p0_repro_opted_in({}) is False


def test_failure_banner_links_the_issue() -> None:
    banner = failure_banner(5613)
    assert banner.startswith("[OPEN P0 #5613]")
    assert "https://github.com/spec-kitty/spec-kitty/issues/5613" in banner
