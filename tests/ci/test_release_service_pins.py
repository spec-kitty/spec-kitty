"""The release verifies the service pins and proves the wheel ships pins only (#6915 gap 11, ADR 2026-10-29-1 D-4).

``release.yml`` fetches the pinned service assets and checks them against their pins before it builds, so a digest
mismatch fails the release before a distribution exists; after the build it asserts the wheel carries the read-service
pin and no service binary. ``RELEASE_CHECKLIST.md`` names the same checks for a maintainer.
"""

from __future__ import annotations

import re
import subprocess
import sys
import textwrap
import zipfile
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = [pytest.mark.fast]

REPO_ROOT = Path(__file__).resolve().parents[2]
RELEASE = REPO_ROOT / ".github" / "workflows" / "release.yml"
CHECKLIST = REPO_ROOT / "RELEASE_CHECKLIST.md"
JOB = "build-release"
PIN_MEMBER = "specify_cli/_pins/read-service.source.yaml"
BINARY_PATTERNS = ("mission-status-api-*", "command-cli-*", "*.jar", "*.exe")


def _steps() -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = yaml.safe_load(RELEASE.read_text(encoding="utf-8"))["jobs"][JOB]["steps"]
    return steps


def _index(predicate: Any, what: str) -> int:
    hits = [i for i, step in enumerate(_steps()) if predicate(str(step.get("run") or ""))]
    assert len(hits) == 1, f"expected exactly one {JOB} step that {what}, found {len(hits)}"
    return hits[0]


def _fetches_services(run: str) -> bool:
    return bool(re.search(r"scripts/sync_services\.py --service all(?!\S)(?! --check)", run)) and "--extras-only" not in run


def test_the_release_fetches_and_checks_the_service_assets_before_the_build() -> None:
    fetch = _index(_fetches_services, "fetches the service assets")
    check = _index(lambda run: "scripts/sync_services.py --service all --check" in run, "checks the service assets")
    packs_check = _index(lambda run: "scripts/sync_packs.py --pack all --check" in run, "checks the packs")
    build = _index(lambda run: run.strip() == "python -m build", "builds the distributions")
    assert fetch < check < build
    assert abs(check - packs_check) <= 2, "the service check sits beside the packs check"
    assert not _steps()[check].get("continue-on-error"), "a pin mismatch must fail the release"


def _wheel_check_step() -> str:
    run = str(_steps()[_index(lambda run: PIN_MEMBER in run, "checks the wheel's pins")]["run"])
    return run


def test_a_wheel_content_check_requires_the_pin_and_refuses_every_binary_pattern() -> None:
    run = _wheel_check_step()
    assert "zipfile" in run and "dist/*.whl" in run
    for pattern in BINARY_PATTERNS:
        assert pattern in run, f"the wheel check must refuse {pattern}"
    build = _index(lambda text: text.strip() == "python -m build", "builds the distributions")
    assert _index(lambda text: PIN_MEMBER in text, "checks the wheel's pins") > build


def _wheel_rule_snippet() -> str:
    """The Python the release's wheel-content step runs (between ``python - <<'PY'`` and ``PY``), exactly as written."""
    snippets = re.findall(r"python - <<'PY'\n(.*?)\n\s*PY\n", _wheel_check_step(), re.DOTALL)
    assert len(snippets) == 1, f"expected exactly one embedded Python snippet in the wheel check, found {len(snippets)}"
    return textwrap.dedent(snippets[0])


def _run_on_planted_wheel(tmp_path: Path, members: list[str]) -> subprocess.CompletedProcess[str]:
    dist = tmp_path / "dist"
    dist.mkdir()
    with zipfile.ZipFile(dist / "spec_kitty_cli-0.0.0-py3-none-any.whl", "w") as wheel:
        for member in members:
            wheel.writestr(member, "x")
    return subprocess.run([sys.executable, "-c", _wheel_rule_snippet()], cwd=tmp_path, capture_output=True, text=True, check=False)


def test_the_release_wheel_check_passes_a_clean_wheel(tmp_path: Path) -> None:
    result = _run_on_planted_wheel(tmp_path, [PIN_MEMBER, "specify_cli/__init__.py", "specify_cli/_pins/README.md"])
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_release_wheel_check_refuses_a_wheel_without_the_pin(tmp_path: Path) -> None:
    result = _run_on_planted_wheel(tmp_path, ["specify_cli/__init__.py"])
    assert result.returncode != 0
    assert PIN_MEMBER in result.stdout + result.stderr


@pytest.mark.parametrize(
    "binary",
    [
        "mission-status-api-0.1.0-linux-x64",
        "specify_cli/_bin/mission-status-api-0.1.0-darwin-arm64",
        "command-cli-1.0.0-linux-x64",
        "specify_cli/services/mission-status-api.jar",
        "specify_cli/tools/read-service.exe",
    ],
    ids=["mission-status-api", "nested-mission-status-api", "command-cli", "jar", "exe"],
)
def test_the_release_wheel_check_refuses_every_binary_pattern_and_names_the_member(tmp_path: Path, binary: str) -> None:
    result = _run_on_planted_wheel(tmp_path, [PIN_MEMBER, "specify_cli/__init__.py", binary])
    assert result.returncode != 0
    assert binary in result.stdout + result.stderr


def test_the_checklist_names_the_service_pin_checks() -> None:
    text = CHECKLIST.read_text(encoding="utf-8")
    assert "spec-kitty service vendor --service read-service --check" in text
    assert "make sync-services ARGS=--check" in text
    assert re.search(r"^\s*make sync-services\s*$", text, re.MULTILINE), "the checklist fetches with a bare `make sync-services` first"
    assert "never a service binary" in text
