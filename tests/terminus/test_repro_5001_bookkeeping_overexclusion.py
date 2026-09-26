"""Repro (Epic #5001, maintainer-landing PR #5020) — bookkeeping over-exclusion
ships a removed WP's code when it is named like a mission/toolchain artifact.

Mechanism: ``MergeOutcomeVerifier._is_bookkeeping_path`` (``merge/reconciliation.py``)
delegated to ``is_toolchain_generated_churn`` (``coordination/coherence.py``), a
DIRTY-STATE-gate classifier that matches bookkeeping by BARE BASENAME anywhere in
the repository — ``PurePosixPath(path).name == "meta.json"`` matches
``src/config/meta.json`` just as readily as the mission's own
``kitty-specs/<slug>/meta.json``. In the squash content axis
(``_unattributable_content_squash`` / ``_commit_is_content``) a path the
classifier calls bookkeeping is skipped BEFORE authored-blob attribution — so a
removed/canceled WP's commit touching a product-source file merely NAMED like
bookkeeping rides a carrier lane onto the target and SHIPS at exit 0 under the
DEFAULT squash strategy.

RED-first, driven through the REAL ``spec-kitty merge`` CLI (no ``_run_git`` /
subprocess mocking), mirroring ``test_repro_4945.py``'s default-squash shape:
RED at HEAD (the removed content ships, exit 0); GREEN once
``_is_bookkeeping_path`` is anchored to the mission's own planning/toolchain
surface instead of a global basename match.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.terminus.conftest import (
    blob_present_at,
    build_coord_mission,
    output_names_content_fail,
    plant_canceled_commit,
    run_terminus,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def test_default_squash_must_not_ship_removed_wp_code_named_like_bookkeeping(tmp_path: Path) -> None:
    """A removed WP's file at ``src/config/meta.json`` (product source, NOT the
    mission's own ``kitty-specs/<slug>/meta.json``) must not ride a carrier lane
    into the target under the default squash — even though its basename matches
    the toolchain-churn denylist's ``meta.json`` self-bookkeeping leg."""
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M5020B")
    pre_target = mission.rev(mission.target_branch)
    _removed_sha, _removed_pid, planted_path = plant_canceled_commit(
        mission,
        canceled_wp="WP03",
        carrier_wp="WP02",
        path="src/config/meta.json",
    )

    result = run_terminus(mission, ["merge", "--mission", mission.slug, "--yes"])

    assert not blob_present_at(mission.repo, mission.target_branch, planted_path), (
        f"removed WP03 file {planted_path} SHIPPED to {mission.target_branch} at exit "
        f"{result.returncode} — bookkeeping classification over-excluded a product-source "
        "path merely NAMED like a toolchain artifact (Epic #5001)"
    )
    assert result.returncode != 0, "default squash must FAIL the content axis and exit non-zero"
    assert mission.rev(mission.target_branch) == pre_target, "on a content-axis FAIL the target must be CAS-reverted to its pre-merge base"
    assert output_names_content_fail(result), "the merge output must name the un-attributable content / reconciliation FAIL"
