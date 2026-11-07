"""FR-076 (#7283): ``orchestrator-api consolidate-mission`` reports the S8 bound with the reused codes.

A ``single_branch`` Mission with a minted Mission branch, holding content committed after the
last approval, is refused as today's ``PREFLIGHT_FAILED`` envelope with the reused code in
``data.preflight_error_code`` / ``data.preflight_error_codes``, and no branch moves. No new code
or contract field is introduced (C-012).

Driven through the REAL ``spec-kitty orchestrator-api`` CLI over real git; the Mission is built
with the shared fixture of ``tests/integration/test_single_branch_approval_windows.py``.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.integration.test_single_branch_approval_windows import (
    TARGET,
    Mission,
    build_and_approve,
    build_template,
    checkout,
    commit_file,
    on_target,
    tip,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_CODE = "LANE_MOVED_AFTER_APPROVAL"


@pytest.fixture(scope="module")
def minted_template(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, str]:
    return build_template(tmp_path_factory.mktemp("minted"), commit_to_target=False)


def _consolidate_mission(m: Mission) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "specify_cli", "orchestrator-api", "consolidate-mission", "--mission", m.slug, "--strategy", "squash", "--origin-check", "off"],
        cwd=m.repo,
        env=m.env,
        capture_output=True,
        text=True,
        timeout=400,
    )


def _envelope(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert lines, f"expected a JSON envelope on stdout:\n{result.stdout}\n{result.stderr}"
    envelope = json.loads(lines[-1])
    assert isinstance(envelope, dict)
    return envelope


def test_orchestrator_preflight_failed_carries_reused_code(minted_template: tuple[Path, str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    m = checkout(minted_template, tmp_path, monkeypatch)
    build_and_approve(m, "WP01")
    build_and_approve(m, "WP02")
    late = commit_file(m, "src/m1/late.py", "LATE = 1\n", "feat: unreviewed change after the last approval")
    before = {ref: tip(m, ref) for ref in (TARGET, m.mission_branch)}

    result = _consolidate_mission(m)

    envelope = _envelope(result)
    assert envelope["success"] is False, envelope
    assert envelope["error_code"] == "PREFLIGHT_FAILED", envelope
    data = envelope["data"]
    assert isinstance(data, dict)
    assert data["preflight_error_code"] == _CODE, envelope
    assert data["preflight_error_codes"] == [_CODE], envelope
    assert late[:7] in str(data["errors"]), envelope
    assert {ref: tip(m, ref) for ref in before} == before, "no branch may move"
    assert not on_target(m, "src/m1/late.py")
