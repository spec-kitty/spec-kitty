"""Cross-process hash-seed proof for canonical finalization diagnostics."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from charter.hasher import hash_content

from tests.specify_cli.cli.commands.agent.test_finalize_lane_dependency_cycle import (
    _MISSION_SLUG,
    _write_cyclic_mission,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.git_repo,
    pytest.mark.non_sandbox,
    pytest.mark.regression,
]

_CHILD = r"""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner
from tests.specify_cli.cli.commands.agent.test_feature_finalize_bootstrap import (
    MODULE,
    _common_patches,
    _make_bootstrap_result,
)

repo_root = Path(os.environ["CYCLE_FIXTURE_ROOT"])
mission_slug = os.environ["CYCLE_MISSION_SLUG"]
patches = _common_patches(repo_root, mission_slug)
patches[f"{MODULE}.bootstrap_canonical_state"] = MagicMock(
    return_value=_make_bootstrap_result(total=4, seeded=4)
)
active = [patch(target, value) for target, value in patches.items()]
for item in active:
    item.start()
try:
    from specify_cli.cli.commands.agent import mission
    result = CliRunner().invoke(
        mission.app,
        ["finalize-tasks", "--mission", mission_slug, "--validate-only", "--json"],
    )
    sys.stdout.write(result.stdout)
    if result.exception is not None and result.exit_code == 0:
        raise result.exception
    raise SystemExit(result.exit_code)
finally:
    for item in active:
        item.stop()
"""


def _stable_fields(stdout: str) -> bytes:
    payloads = [json.loads(line) for line in stdout.splitlines() if line.strip()]
    assert len(payloads) == 1
    payload = payloads[0]
    selected = {
        "error_code": payload["error_code"],
        "cycle_path": payload["cycle_path"],
        "cycle_lanes": payload["cycle_lanes"],
    }
    return json.dumps(selected, sort_keys=True, separators=(",", ":")).encode()


def test_canonical_finalize_cycle_fields_are_stable_across_hash_seeds(
    tmp_path: Path,
) -> None:
    """Seeds 1, 7, and 97 produce byte-identical terminal cycle facts."""
    _write_cyclic_mission(tmp_path)
    checkout_root = Path(__file__).resolve().parents[3]
    python_path = os.pathsep.join((str(checkout_root / "src"), str(checkout_root)))
    captures: list[bytes] = []

    for seed in ("1", "7", "97"):
        env = os.environ.copy()
        env.update(
            {
                "PYTHONHASHSEED": seed,
                "PYTHONPATH": python_path,
                "CYCLE_FIXTURE_ROOT": str(tmp_path),
                "CYCLE_MISSION_SLUG": _MISSION_SLUG,
                "SPEC_KITTY_SYNC_DISABLE": "1",
            }
        )
        env["SPEC_KITTY_ENABLE_SAAS_SYNC"] = "0"
        result = subprocess.run(
            [sys.executable, "-c", _CHILD],
            cwd=checkout_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode != 0, (seed, result.stdout, result.stderr)
        assert "Traceback" not in result.stdout
        assert "Traceback" not in result.stderr
        captures.append(_stable_fields(result.stdout))

    assert set(captures) == {captures[0]}
    assert hash_content(captures[0].decode("utf-8")).startswith("sha256:")
