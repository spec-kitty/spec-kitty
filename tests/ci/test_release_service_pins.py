"""The release verifies the service pins and proves the wheel ships pins only (#6915 gap 11, ADR 2026-10-29-1 D-4).

``release.yml`` fetches the pinned service assets and checks them against their pins before it builds, so a digest
mismatch fails the release before a distribution exists; after the build it asserts the wheel carries the read-service
pin and no service binary. ``RELEASE_CHECKLIST.md`` names the same checks for a maintainer.
"""

from __future__ import annotations

import fnmatch
import re
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


@pytest.mark.parametrize(
    ("members", "ok"),
    [
        ([PIN_MEMBER, "specify_cli/__init__.py"], True),
        (["specify_cli/__init__.py"], False),
        ([PIN_MEMBER, "specify_cli/_bin/mission-status-api-0.1.0-linux-x64"], False),
        ([PIN_MEMBER, "x/command-cli-1.0-darwin-arm64"], False),
        ([PIN_MEMBER, "x/service.jar"], False),
        ([PIN_MEMBER, "x/tool.exe"], False),
    ],
)
def test_the_wheel_rule_the_step_states(members: list[str], ok: bool) -> None:
    """The rule the release step applies, run on planted member lists (the step's own Python is the same rule)."""
    names = {Path(member).name for member in members}
    passes = PIN_MEMBER in members and not any(fnmatch.fnmatch(name, pattern) for name in names for pattern in BINARY_PATTERNS)
    assert passes is ok


def test_the_checklist_names_the_service_pin_checks() -> None:
    text = CHECKLIST.read_text(encoding="utf-8")
    assert "spec-kitty service vendor --service read-service --check" in text
    assert "make sync-services ARGS=--check" in text
    assert re.search(r"^\s*make sync-services\s*$", text, re.MULTILINE), "the checklist fetches with a bare `make sync-services` first"
    assert "never a service binary" in text
