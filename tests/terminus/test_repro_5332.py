"""Repro #5332 -- a squash-projection refusal must roll back, and FR-011 must hold.

Pre-fix, ``_assert_squash_projected_content_landed`` exited non-zero AFTER the
mission->target squash had already advanced the target and (on the fresh PASS
path) after the reconciliation PASS anchor was persisted, but never rolled
anything back: the target and coordination branch stayed advanced past the
pre-run snapshot with the report claiming "Nothing was torn down".

Contract (FR-004/FR-006/FR-011, ``contracts/rollback-authority.md``):

* a projection refusal on a FRESH run restores the target AND the coordination
  branch to their pre-run SHAs, prints the rollback report, exits 1, and leaves
  ``reconciliation_passed_target_sha`` null (the run's OWN PASS anchor must not
  make the authority treat the fresh advance as an "earlier" verified landing --
  post-tasks BLOCKER 1);
* a landing verified by an EARLIER attempt (persisted anchor == current target
  tip) is KEPT on a resume whose projection then refuses, and the report says so.

Trigger for the fresh case (post-tasks finding 12, REAL, nothing mocked): a
projected path with NO merge driver -- ``kitty-specs/<slug>/notes/n.md``. It is
bookkeeping for the blob-attribution axis (the gate PASSes) and stays projected,
but has no ``.gitattributes`` driver, so the projection proof's
``driver_replay_expected_bytes`` raises ``GitProbeError`` and the proof returns
False. The lane edits line 1 and a non-overlapping line-6 change is committed on
the target before consolidating: stock squash merges cleanly while the pre-squash
target differs from the checkpoint, so the proof must driver-replay and REFUSEs.

The FR-011 control cannot be reached by a real trigger (a resume has nothing new
to project once the landing is verified), so it drives the production shell
in-process and stubs ONLY ``_assert_squash_projected_content_landed`` to refuse
(state and git are real).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.consolidation import executor
from tests.terminus.conftest import blob_present_at, build_coord_mission, run_terminus
from tests.terminus.conftest import _git as git
from tests.terminus.test_repro_5021 import _complete_squash_then_recreate_mid_teardown_state
from tests.terminus.test_repro_5318 import flat, ref_shas, restored_pairs, state_bookkeeping

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_NOTES_BASELINE = "l1\nl2\nl3\nl4\nl5\nl6\n"
_PROJECTION_REFUSE_TEXT = "projected coordination bookkeeping content did not land"


def _notes_rel(slug: str) -> str:
    return f"kitty-specs/{slug}/notes/n.md"


def _diverge_notes(mission_repo: Path, slug: str, target_branch: str, lane_branch: str) -> None:
    """Lane edits line 1; the target independently edits line 6 (non-overlapping)."""
    notes = mission_repo / _notes_rel(slug)
    git(mission_repo, "checkout", "-q", target_branch)
    notes.write_text(_NOTES_BASELINE.replace("l6", "l6 target"), encoding="utf-8")
    git(mission_repo, "commit", "-qam", "chore: target-side notes edit")
    git(mission_repo, "checkout", "-q", lane_branch)
    notes.write_text(_NOTES_BASELINE.replace("l1", "l1 lane"), encoding="utf-8")
    git(mission_repo, "commit", "-qam", "chore: lane notes edit")
    git(mission_repo, "checkout", "-q", target_branch)


def test_5332_fresh_projection_refusal_restores_target_and_coordination(tmp_path: Path) -> None:
    slug = "terminus-01M5332A"
    mission = build_coord_mission(tmp_path, wps=("WP01",), mid8="01M5332A", extra_base_files={_notes_rel(slug): _NOTES_BASELINE})
    _diverge_notes(mission.repo, mission.slug, mission.target_branch, mission.lane_branch("WP01"))
    before = ref_shas(mission)

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    output = flat(result)
    after = ref_shas(mission)

    assert result.returncode == 1, f"#5332: a projection refusal must exit 1. output={output}"
    assert _PROJECTION_REFUSE_TEXT in output, f"fixture precondition: the run must hit the projection refusal (real no-driver trigger). output={output}"
    assert after["target"] == before["target"], f"#5332: target left advanced ({before['target']} -> {after['target']}). output={output}"
    assert after["coord"] == before["coord"], f"#5332: coordination branch left advanced ({before['coord']} -> {after['coord']}). output={output}"
    assert not blob_present_at(mission.repo, mission.target_branch, "src/pkg/wp01.py"), "the refused squash content must be rolled back off the target"
    assert restored_pairs(output, mission.target_branch), f"the report must show the target RESTORED line. output={output}"
    assert restored_pairs(output, mission.coord_branch), f"the report must show the coordination-branch RESTORED line. output={output}"
    bookkeeping = state_bookkeeping(mission)
    assert bookkeeping is not None
    assert bookkeeping["reconciliation_passed_target_sha"] is None, f"BLOCKER 1: the refused run's own PASS anchor must not survive. {bookkeeping}"
    assert bookkeeping["mission_number_baked"] is False and bookkeeping["completed_wps"] == [], bookkeeping


def test_5332_earlier_verified_landing_is_kept_on_resume_projection_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """FR-011 control: a resume whose anchor (from an EARLIER attempt) equals the target tip keeps the landing."""
    mission = build_coord_mission(tmp_path, wps=("WP01",), mid8="01M5332B")
    anchored_tip = _complete_squash_then_recreate_mid_teardown_state(mission, "WP01", ["WP01"])
    before = ref_shas(mission)
    assert before["target"] == anchored_tip

    def _refuse(_run: object) -> None:
        raise executor.typer.Exit(1)

    monkeypatch.setattr(executor, "_assert_squash_projected_content_landed", _refuse)
    monkeypatch.setenv("HOME", str(mission.home))
    monkeypatch.chdir(mission.repo)

    with pytest.raises(executor.typer.Exit) as excinfo:
        executor._run_lane_based_consolidation(mission.repo, mission.slug, push=False, delete_branch=None, remove_worktree=None, assume_yes=True)

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert "Kept the landing verified by an earlier reconciliation" in " ".join((captured.out + captured.err).split())
    after = ref_shas(mission)
    assert after["target"] == anchored_tip, "FR-011: the landing verified by an earlier reconciliation must be KEPT"
    assert blob_present_at(mission.repo, mission.target_branch, "src/pkg/wp01.py")
    bookkeeping = state_bookkeeping(mission)
    assert bookkeeping is not None and bookkeeping["reconciliation_passed_target_sha"] == anchored_tip, "the earlier anchor must stay intact"
