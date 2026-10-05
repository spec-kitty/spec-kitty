"""``spec-kitty consolidate`` folds EVERY coordination-kind file of the composed directory into the primary one (#5651).

A bare-slug coordination Mission keeps its primary directory at ``kitty-specs/<slug>`` while the
coordination seed carries every coordination-kind file of that directory (traces, matrices, the
decision log, review cycles, the status pair) into the composed ``kitty-specs/<slug>-<mid8>``
directory, and the squash lands that directory on the target. The consolidation must end with ONE
Mission directory on the target (FR-019). These cases drive the REAL consolidation CLI over the
fixture builder of ``tests/integration/test_merge_lane_planning_data_loss.py`` (imported, so the
per-PR ``consolidation`` home pins the contract the nightly-only integration directory cannot).
No product code is patched.

Mutation notes (revert one change, a case goes red): reverting the fold's generalisation leaves the
composed ``traces/`` file on the target (``test_a_seed_carried_coordination_file_is_folded...``);
reverting the per-file proof lets the fold delete a file the primary directory lacks
(``test_a_coordination_file_the_primary_directory_lacks_is_a_rendered_refusal...``); reverting the
gate leg turns the ``--strategy merge`` variant of the first red.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.consolidation.bookkeeping_projection import AliasFoldRefusal
from tests.integration.test_merge_lane_planning_data_loss import (
    _RETENTION_MID8,
    _assert_bare_slug_end_state,
    _branch_exists,
    _build_bare_slug_coord_mission,
    _git,
    _invoke_merge_cli,
)

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.regression]

_STRATEGIES = pytest.mark.parametrize("strategy_args", [[], ["--strategy", "merge"]], ids=["squash", "merge"])

_CARRIED = {
    "traces/mission-trace.md": "# Mission trace\n\nsection written on the target before the run\n",
    "traces/nested/deeper/step.md": "a nested trace\n",
    "issue-matrix.json": '{"rows": []}\n',
    "acceptance-matrix.json": '{"criteria": []}\n',
    "decisions.events.jsonl": '{"event_id": "01KX0000000000000000DECISN"}\n',
    "tasks/WP01-x/review-cycle-1.md": "# review cycle 1\n",
}
_WRITTEN_AFTER_THE_SEED = {"traces/written-during-the-mission.md": "a trace the primary directory never held\n"}


@_STRATEGIES
def test_a_seed_carried_coordination_file_is_folded_into_the_primary_directory(tmp_path: Path, strategy_args: list[str]) -> None:
    """The seed copies the primary directory's coordination files under the composed name; the fold removes the copies, not the originals."""
    slug, mission_branch, pre_run_event_ids = _build_bare_slug_coord_mission(tmp_path, primary_dir_files=_CARRIED)

    result = _invoke_merge_cli(tmp_path, ["--mission", slug, "--yes", "--allow-sparse-checkout", *strategy_args])

    output = getattr(result, "output", None)
    assert getattr(result, "exit_code", None) == 0, f"output: {output!r}, exception: {getattr(result, 'exception', None)!r}"
    _assert_bare_slug_end_state(tmp_path, slug, mission_branch, pre_run_event_ids)
    for relpath, content in _CARRIED.items():
        assert _git(tmp_path, "show", f"main:kitty-specs/{slug}/{relpath}").stdout == content, relpath
    assert not (tmp_path / "kitty-specs" / f"{slug}-{_RETENTION_MID8}").exists(), "no composed directory, empty or not, on the target checkout"


@_STRATEGIES
def test_a_coordination_file_the_primary_directory_lacks_is_a_rendered_refusal_and_nothing_is_deleted(tmp_path: Path, strategy_args: list[str]) -> None:
    """A coordination file written under the composed name that the primary directory does not hold is never deleted: the run is refused and rolled back."""
    slug, mission_branch, _pre_run_event_ids = _build_bare_slug_coord_mission(tmp_path, alias_dir_files=_WRITTEN_AFTER_THE_SEED)
    target_before = _git(tmp_path, "rev-parse", "main").stdout.strip()

    result = _invoke_merge_cli(tmp_path, ["--mission", slug, "--yes", "--allow-sparse-checkout", *strategy_args])

    output = getattr(result, "output", "")
    flat = " ".join(output.split())
    assert getattr(result, "exit_code", None) == 1, output
    assert not isinstance(getattr(result, "exception", None), AliasFoldRefusal), "the refusal must be rendered, not raised"
    assert f"Mission {slug}: the composed coordination directory kitty-specs/{slug}-{_RETENTION_MID8} was not removed" in flat, output
    assert "traces/written-during-the-mission.md" in flat, output
    assert "Nothing was deleted and the run was rolled back." in flat, output
    assert flat.endswith("Error code: ALIAS_FILE_NOT_PRESERVED."), output
    assert _git(tmp_path, "rev-parse", "main").stdout.strip() == target_before, "the target must be rolled back"
    assert _branch_exists(tmp_path, mission_branch), "nothing may be torn down"
    composed_path = f"kitty-specs/{slug}-{_RETENTION_MID8}/traces/written-during-the-mission.md"
    assert _git(tmp_path, "show", f"{mission_branch}:{composed_path}").stdout == _WRITTEN_AFTER_THE_SEED["traces/written-during-the-mission.md"]
    assert _git(tmp_path, "status", "--porcelain", "--untracked-files=no").stdout == "", "the root checkout is clean after the rollback"
