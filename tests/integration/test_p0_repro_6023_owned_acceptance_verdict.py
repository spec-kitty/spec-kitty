"""#6023 regression guard -- owned acceptance-verdict must resolve the owned mission.

Originally the red-first ``p0_repro`` reproduction for OPEN P0 #6023 (nightly lane
only); the ``p0_repro`` marker was removed when the fix landed (ADR 2026-07-17-1), so
this now runs per-PR as a standing regression guard.

A supported owned, PR-bound mission lives only in its owned checkout (P); primary
(the repository-root checkout, R) does not contain it. The
``agent mission acceptance-verdict`` command resolves its repo root with
``find_repo_root()`` and resolves the handle with no owned authority
(``cli/commands/agent/acceptance_verdict.py``: ``repo_root = find_repo_root()`` then
``resolve_mission_handle(mission, repo_root, ...)``, with no ``--owned-checkout``
option), so it searches primary, cannot find the owned mission and exits 1 with
``MISSION_NOT_FOUND``. The mission's acceptance criteria therefore cannot be recorded
through the owned-checkout route at all -- the first half of "owned missions cannot
record acceptance criteria and their code branch is rejected".

This drives the real CLI from the owned checkout against the allocator-faithful owned
R/P/S fixture (``make_owned_checkouts``): the mission is written into P only, and the
verdict command is run with P as the working directory.

Ideal, asserted here and RED until #6023 is fixed: run from the owned checkout, the
acceptance-verdict command must resolve the owned mission with validated ownership and
NOT fail with ``MISSION_NOT_FOUND`` (it may still fail for an unrelated reason such as a
criterion/matrix gap once resolution is fixed -- that is a different, non-blocking
outcome for this oracle). Before the fix it failed ``MISSION_NOT_FOUND``. See ADR
2026-07-17-1 and docs/development/reference/red-main-and-release-readiness.md.
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


def test_acceptance_verdict_from_owned_checkout_must_resolve_the_owned_mission(make_owned_checkouts: Callable[..., OwnedCheckouts], tmp_path: Path) -> None:
    co = make_owned_checkouts(topology="single_branch", wp_ids=("WP01",))

    junit = tmp_path / "junit.xml"
    junit.write_text("<testsuite tests='1' failures='0' errors='0'></testsuite>\n", encoding="utf-8")
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

    # Fixture invariant: the mission exists in the owned checkout P and NOT in primary R.
    assert (co.owned_root / "kitty-specs" / co.mission_slug / "meta.json").is_file(), "fixture: mission must be in the owned checkout P"
    assert not (co.repository_root / "kitty-specs" / co.mission_slug).exists(), "fixture: mission must NOT be in primary R"

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "specify_cli",
            "agent",
            "mission",
            "acceptance-verdict",
            "--mission",
            co.mission_slug,
            "--criterion",
            "FR-001",
            "--result",
            "pass",
            "--verification-method",
            "automated_test",
            "--actor",
            "codex",
            "--evidence",
            str(junit),
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
        error_code = json.loads(proc.stdout.strip().splitlines()[-1]).get("error_code")
    except Exception:
        error_code = f"<unparsed: {proc.stdout[-300:]!r}>"

    assert error_code != "MISSION_NOT_FOUND", (
        "ideal: acceptance-verdict run from the owned checkout must resolve the owned mission with validated "
        "ownership, not search primary and fail MISSION_NOT_FOUND; got MISSION_NOT_FOUND -- owned missions "
        f"cannot record acceptance criteria through the owned route (#6023). rc={proc.returncode}\n"
        f"stdout:\n{proc.stdout[-800:]}\nstderr:\n{proc.stderr[-400:]}"
    )
