"""``consolidate --retarget`` shapes that are admitted and land (#7692, WP04 T020).

A protected recorded target (D2), a restated target (FR-012), a new target with its own commits,
and an attestation that follows the retarget (contract § Attestations). Scenario and fixtures:
``test_consolidate_retarget.py``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.terminus.conftest import _git as git
from tests.terminus.conftest import blob_present_at
from tests.terminus.lanes_fixture import build_lanes_mission
from tests.terminus.retarget_support import (
    CODE_FILE,
    NEW,
    OLD,
    REASON,
    RETARGET,
    assert_landed_on_new_target,
    events_at,
    log_subjects,
    meta_at,
    tip,
)
from tests.terminus.rollback_harness import flat
from tests.terminus.test_target_override_recorded_target_unwritable import _check_out_override, _consolidate, _lanes

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def test_a_retarget_away_from_a_protected_recorded_target_is_admitted(tmp_path: Path) -> None:
    """D2 / plan flag 1 (operator: no objection): a protected ``main`` does not stop a retarget to an unprotected ``develop``.

    The ``done`` bookkeeping goes to the NEW target, so the #5385 probe is re-pointed there and
    admits the run. This pins the consequence the operator was told about.
    """
    mission = build_lanes_mission(tmp_path, wps=("WP01", "WP02"), target_branch=OLD, mid8="01M7692D")
    _check_out_override(mission)
    pre_new, pre_old = tip(mission, NEW), tip(mission, OLD)

    result = _consolidate(mission, *RETARGET)

    assert_landed_on_new_target(mission, result, pre_new)
    assert tip(mission, OLD) == pre_old


def test_restating_the_recorded_target_is_not_a_retarget(tmp_path: Path) -> None:
    """FR-012: ``--target main --retarget`` runs like a plain run: it lands on ``main`` with no retarget commit."""
    mission = _lanes(tmp_path, "01M7692Q")
    pre_old = tip(mission, OLD)

    result = _consolidate(mission, "--target", OLD, "--retarget")

    output = flat(result)
    assert result.returncode == 0, output
    assert blob_present_at(mission.repo, OLD, CODE_FILE), output
    landed = log_subjects(mission, f"{pre_old}..{OLD}")
    assert landed and not any("retarget" in subject for subject in landed), landed
    assert "retarget_history" not in meta_at(mission, OLD)


def test_a_new_target_with_its_own_commits_keeps_them(tmp_path: Path) -> None:
    mission = _lanes(tmp_path, "01M7692G")
    _check_out_override(mission)
    (mission.repo / "docs").mkdir(exist_ok=True)
    (mission.repo / "docs" / "x.md").write_text("develop's own work\n", encoding="utf-8")
    git(mission.repo, "add", "docs/x.md")
    git(mission.repo, "commit", "-qm", "docs: develop's own commit")
    own = tip(mission, NEW)

    result = _consolidate(mission, *RETARGET)

    assert_landed_on_new_target(mission, result, own)
    assert subprocess.run(["git", "merge-base", "--is-ancestor", own, NEW], cwd=mission.repo, check=False).returncode == 0
    assert blob_present_at(mission.repo, NEW, "docs/x.md")


def test_an_attestation_follows_the_retarget_to_the_new_target(tmp_path: Path) -> None:
    """Contract § Attestations (operator ruling, option A): on a Mission without a coordination branch the
    attestation event lands on the new target's status surface, never on the old target.

    ``--attest-no-implementation`` is admissible on this fixture (a work package that already shows
    evidence accepts it as a fresh operator act); ``--attest-approved-reviewed`` is not (the fixture's
    WPs carry stamped review approvals, which that attestation refuses).
    """
    mission = _lanes(tmp_path, "01M7692T")
    _check_out_override(mission)
    pre_new, pre_old = tip(mission, NEW), tip(mission, OLD)
    old_events = events_at(mission, OLD)

    result = _consolidate(mission, *RETARGET, "--attest-no-implementation", "WP01", "--attest-reason", REASON)

    assert_landed_on_new_target(mission, result, pre_new)
    attested = [
        event
        for event in events_at(mission, NEW)
        if event.get("wp_id") == "WP01" and (event.get("policy_metadata") or {}).get("attestation") == "no_implementation"
    ]
    assert len(attested) == 1, f"the attestation lands on {NEW}. output={flat(result)}"
    assert tip(mission, OLD) == pre_old
    assert events_at(mission, OLD) == old_events
