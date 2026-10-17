"""#6320 regression guard (was the red-first p0_repro reproduction): owned-mission ``issue-verdict`` authority.

``agent issue-verdict`` resolves the mission against the repository root and has
no ``--owned-checkout`` option, so an owned-only mission (present in P, absent
from R) cannot have its issue-matrix verdicts recorded. Run from the owned
checkout the command must resolve the owned mission, not fail MISSION_NOT_FOUND.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.integration.conftest import OwnedCheckouts

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def test_issue_verdict_from_owned_checkout_must_resolve_the_owned_mission(make_owned_checkouts: Callable[..., OwnedCheckouts], tmp_path: Path) -> None:
    co = make_owned_checkouts(topology="single_branch", wp_ids=("WP01",))
    env = dict(os.environ)
    env.update(
        HOME=str(tmp_path / "h"),
        SPEC_KITTY_HOME=str(tmp_path / "skh"),
        XDG_CONFIG_HOME=str(tmp_path / "xc"),
        SPEC_KITTY_NO_UPGRADE_CHECK="1",
        SPEC_KITTY_ENABLE_SAAS_SYNC="0",
    )
    for key in ("h", "skh", "xc"):
        (tmp_path / key).mkdir(parents=True, exist_ok=True)

    assert (co.owned_root / "kitty-specs" / co.mission_slug / "meta.json").is_file(), "fixture: mission must be in the owned checkout P"
    assert not (co.repository_root / "kitty-specs" / co.mission_slug).exists(), "fixture: mission must NOT be in primary R"

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "specify_cli",
            "agent",
            "issue-verdict",
            "--mission",
            co.mission_slug,
            "--issue",
            "#6320",
            "--verdict",
            "fixed",
            "--actor",
            "codex",
            "--evidence-ref",
            "PR #1",
            "--json",
        ],
        cwd=co.owned_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )

    error_code = None
    try:
        parsed = json.loads(proc.stdout.strip().splitlines()[-1])
        error_code = parsed.get("error_code") or parsed.get("code")
    except Exception:
        error_code = f"<unparsed: {proc.stdout[-300:]!r}>"

    assert error_code != "MISSION_NOT_FOUND" and proc.returncode == 0, (
        f"issue-verdict run from the owned checkout must resolve the owned mission and record the verdict (#6320). rc={proc.returncode}\n"
        f"stdout:\n{proc.stdout[-800:]}\nstderr:\n{proc.stderr[-400:]}"
    )
    matrix = co.owned_root / "kitty-specs" / co.mission_slug / "issue-matrix.json"
    assert matrix.is_file() and "#6320" in matrix.read_text(encoding="utf-8")
