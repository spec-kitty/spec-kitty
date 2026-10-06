"""``spec-kitty consolidate`` renders the fold's event-preservation refusal instead of a traceback (#5750).

The one-directory fold of a bare-slug coordination Mission proves every event of the composed
``<slug>-<mid8>`` directory's log present in the primary Mission directory's event log before it
removes the composed pair. When it cannot, the run is rolled back, nothing is deleted, and the
command prints the refusal with ``ALIAS_STATUS_EVENTS_NOT_PRESERVED`` and exits 1. The same path is
driven by an integration test (``tests/integration/test_merge_lane_planning_data_loss.py``, which does
not run per pull request); this copy lives in the per-PR ``consolidation`` home and reuses that
file's fixture builder by import. No product code is patched.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import pytest

from specify_cli.consolidation.bookkeeping_projection import AliasStatusEventsNotPreserved
from tests.integration.test_merge_lane_planning_data_loss import (
    _RETENTION_MID8,
    _branch_exists,
    _build_bare_slug_coord_mission,
    _git,
    _invoke_merge_cli,
)

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.regression]

_FOREIGN_EVENT_ID = "01KX0000000FOREIGNEVENT0001"


def test_a_foreign_event_in_the_composed_log_is_a_rendered_refusal_with_its_code_and_exit_1(tmp_path: Path) -> None:
    slug, mission_branch, _pre_run_event_ids = _build_bare_slug_coord_mission(tmp_path, alias_pair_on_target=True)
    composed_log = tmp_path / "kitty-specs" / f"{slug}-{_RETENTION_MID8}" / "status.events.jsonl"
    foreign = json.loads(composed_log.read_text(encoding="utf-8").splitlines()[0])
    foreign["event_id"] = _FOREIGN_EVENT_ID
    # Head-of-file, so the target's change and the run's own appended ``done`` event merge cleanly.
    composed_log.write_text(json.dumps(foreign, sort_keys=True) + "\n" + composed_log.read_text(encoding="utf-8"), encoding="utf-8")
    _git(tmp_path, "add", "-f", str(composed_log))
    _git(tmp_path, "commit", "-m", "chore: the target gains an event in the composed log")
    target_before = _git(tmp_path, "rev-parse", "main").stdout.strip()

    result = _invoke_merge_cli(tmp_path, ["--mission", slug, "--yes", "--allow-sparse-checkout"])

    output = getattr(result, "output", "")
    flat = " ".join(output.split())
    assert getattr(result, "exit_code", None) == 1, output
    assert not isinstance(getattr(result, "exception", None), AliasStatusEventsNotPreserved), "the refusal must be rendered, not raised"
    assert f"Mission {slug}: the composed coordination directory kitty-specs/{slug}-{_RETENTION_MID8} was not removed" in flat, output
    assert f"the primary Mission directory's event log lacks: {_FOREIGN_EVENT_ID}" in flat, output
    assert "merged primary log" not in flat
    assert flat.endswith("Error code: ALIAS_STATUS_EVENTS_NOT_PRESERVED."), output
    assert _git(tmp_path, "rev-parse", "main").stdout.strip() == target_before, "the target must be rolled back"
    assert _branch_exists(tmp_path, mission_branch), "nothing may be torn down"
    assert composed_log.exists(), "the composed directory's status files must not be deleted"


def test_the_fixture_merge_base_carries_the_approval_stamp_whatever_the_clock_reads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The test above needs the target and the coordination branch to share the stamp commit.

    The fixture stamps the ``approved`` event in place, which rewrites its payload. When the merge
    base predates that stamp, the event-log merge driver refuses the rewritten event, and the run
    stops at ``TARGET_BRANCH_CONTENT_CONFLICT`` before it reaches the refusal under test. Before
    the fix, the two branches shared the stamp only when their two stamp commits landed in the same
    wall-clock second. Here every stamp call commits at its own date, so the shared history must
    come from the fixture's construction, not from the clock.
    """
    import tests.integration.test_merge_lane_planning_data_loss as fixture_module
    from tests.consolidation.approval_stamps import restamp_log_at_lane_tips as stamp

    calls = itertools.count(1)

    def stamp_at_a_new_date(repo: Path, feature_dir: Path, *, coord_branch: str | None = None) -> None:
        date = f"2030-01-{next(calls):02d}T00:00:00+00:00"
        monkeypatch.setenv("GIT_AUTHOR_DATE", date)
        monkeypatch.setenv("GIT_COMMITTER_DATE", date)
        stamp(repo, feature_dir, coord_branch=coord_branch)

    monkeypatch.setattr(fixture_module, "restamp_log_at_lane_tips", stamp_at_a_new_date)
    slug, mission_branch, _pre_run_event_ids = _build_bare_slug_coord_mission(tmp_path, alias_pair_on_target=True)

    composed_log = f"kitty-specs/{slug}-{_RETENTION_MID8}/status.events.jsonl"
    merge_base = _git(tmp_path, "merge-base", "main", mission_branch).stdout.strip()
    on_target = _git(tmp_path, "show", f"main:{composed_log}").stdout
    assert '"lane_head"' in on_target, "the fixture must stamp the target's composed log"
    assert _git(tmp_path, "show", f"{merge_base}:{composed_log}").stdout == on_target, "the merge base must carry the target's stamped composed log"
