"""Repro #5022 — the default-squash content axis skips deletions, so a canceled
WP's deletion of a pre-existing product file that no approved lane re-authors
rides a carrier lane onto the target and SHIPS at exit 0.

Mechanism: ``MergeOutcomeVerifier._unattributable_content_squash``
(``merge/reconciliation.py``) iterates ``git diff --name-status --no-renames
window_base..target`` and, at the pre-fix HEAD, unconditionally skips every ``D``
path (``if status.startswith("D"): continue``) — a deletion is treated as
"ships no content" and is never checked against any authorship authority. A
canceled WP's commit that DELETES a pre-existing product file, ridden onto the
target via an approved carrier lane's merge history, therefore ships silently:
the file is gone from the target and the squash content axis still PASSes at
exit 0.

RED-first, driven through the REAL ``spec-kitty merge`` CLI (no ``_run_git`` /
subprocess mocking): at the pre-fix HEAD the deletion lands and the merge exits
0 — the file is absent from the target — so the DESIRED post-fix assertions
(FAIL + the file still present, CAS-reverted to the pre-merge base) were RED
(pinned ``xfail(strict=True)`` while red). GREEN now that ``authored_deletions``
(T002) and the squash-axis deletion attribution (T003) have landed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.terminus.conftest import (
    blob_present_at,
    build_coord_mission,
    output_names_content_fail,
    plant_canceled_deletion,
    run_terminus,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_KEEP_ME_PATH = "src/product/keep_me.py"


def test_5022_default_squash_must_not_ship_unattributed_deletion(tmp_path: Path) -> None:
    mission = build_coord_mission(
        tmp_path,
        wps=("WP01",),
        mid8="01M5022A",
        extra_base_files={_KEEP_ME_PATH: '# keep me\ndef keep_me() -> str:\n    return "alive"\n'},
    )
    pre_target = mission.rev(mission.target_branch)
    assert blob_present_at(mission.repo, mission.target_branch, _KEEP_ME_PATH)
    plant_canceled_deletion(mission, canceled_wp="WP99", carrier_wp="WP01", path=_KEEP_ME_PATH)

    result = run_terminus(mission, ["merge", "--mission", mission.slug, "--yes"])

    assert result.returncode != 0, "default squash must FAIL the content axis on an unattributed deletion and exit non-zero"
    assert mission.rev(mission.target_branch) == pre_target, "on a content-axis FAIL the target must be CAS-reverted to its pre-merge base"
    assert blob_present_at(mission.repo, mission.target_branch, _KEEP_ME_PATH), (
        f"pre-existing file {_KEEP_ME_PATH} was silently DELETED from {mission.target_branch} by a canceled WP's "
        "commit riding a carrier lane onto the target under the DEFAULT squash (#5022 data loss)"
    )
    assert output_names_content_fail(result), "the merge output must name the un-attributable content / reconciliation FAIL"
