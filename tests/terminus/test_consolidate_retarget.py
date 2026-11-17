"""``spec-kitty consolidate --target <b> --retarget`` end to end (#7692, WP04): the success arm.

A Mission recorded for ``main`` whose landing should go to ``develop``: ``--retarget`` adopts
``develop`` as the recorded target and commits that record (``meta.json``: ``target_branch`` and
one ``retarget_history`` entry) as the run's first mutation, inside the rollback door, so every
later write the run makes (the squash, the ``done`` transitions, the retrospective, the
coordination flatten, the mission number) lands on ``develop`` and nothing lands on ``main``.

Driven through the REAL ``spec-kitty consolidate`` CLI over real git on the #5783 fixtures
(``tests/terminus/test_target_override_recorded_target_unwritable.py``): ``main`` is declared
unprotected unless an arm says otherwise, and ``develop`` is cut from ``main`` and checked out in
the repository root checkout. The arms are split over five files so ``-n 6 --dist loadfile``
spreads them (NFR-003): this one (T018), ``_failure`` (T019 failure / abort), ``_resume``
(T019 resume / mismatch), ``_refusals`` (T020 refusals) and ``_landings`` (T020 admitted shapes).
Shared helpers: ``tests/terminus/retarget_support.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.core.constants import RETROSPECTIVE_FILENAME
from tests.terminus.conftest import blob_present_at
from tests.terminus.retarget_support import (
    CODE_FILE,
    DONE_SUBJECT,
    FLATTEN_SUBJECT,
    NEW,
    OLD,
    REASON,
    RETARGET,
    RETARGET_SUBJECT,
    RETRO_SUBJECT,
    dry_run,
    kitty_specs_status,
    lanes_at,
    log_subjects,
    meta_at,
    tip,
)
from tests.terminus.rollback_harness import flat
from tests.terminus.test_target_override_recorded_target_unwritable import (
    _branches,
    _check_out_override,
    _consolidate,
    _coord,
    _lanes,
    _merge_records,
    _reflogs,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


@pytest.mark.parametrize("build", [_lanes, _coord], ids=["lanes", "coord"])
def test_retarget_lands_every_write_on_the_new_target(tmp_path: Path, build) -> None:  # type: ignore[no-untyped-def]
    """SC-001: the record, done, retrospective, mission number and (coord) flatten all land on ``develop``.

    SC-004 on the same fixture first: ``--dry-run`` forecasts the retarget and moves nothing.
    """
    mission = build(tmp_path, "01M7692S")
    _check_out_override(mission)
    before, reflogs_before = _branches(mission), _reflogs(mission)
    pre_new, pre_old = tip(mission, NEW), tip(mission, OLD)
    coordinated = "coordination_branch" in meta_at(mission, NEW)

    forecast, payload = dry_run(mission, *RETARGET)
    assert forecast.returncode == 0, flat(forecast)
    assert payload.get("retarget") == {"from": OLD, "to": NEW}, payload
    assert _branches(mission) == before and _reflogs(mission) == reflogs_before and _merge_records(mission) == []

    result = _consolidate(mission, *RETARGET, "--retarget-reason", REASON)

    output = flat(result)
    assert result.returncode == 0, output
    assert "Traceback" not in result.stderr, result.stderr

    meta = meta_at(mission, NEW)
    assert meta["target_branch"] == NEW, meta
    history = meta.get("retarget_history")
    assert isinstance(history, list) and len(history) == 1, meta
    entry = history[0]
    assert (entry["from"], entry["to"], entry["reason"]) == (OLD, NEW, REASON), entry
    assert entry["actor"] and entry["at"], entry
    assert isinstance(meta.get("mission_number"), int), meta
    if coordinated:
        # ``mission_metadata.flatten_coordination_metadata``: pops coordination_branch and topology, sets flattened.
        assert "coordination_branch" not in meta and "topology" not in meta and meta.get("flattened") is True, meta

    lanes = lanes_at(mission, NEW, tmp_path / "events")
    assert lanes and set(lanes.values()) == {"done"}, lanes
    assert blob_present_at(mission.repo, NEW, f"kitty-specs/{mission.slug}/{RETROSPECTIVE_FILENAME}"), output

    landed = log_subjects(mission, f"{pre_new}..{NEW}")
    retarget = RETARGET_SUBJECT.format(slug=mission.slug)
    assert landed.count(retarget) == 1 and landed[0] == retarget, f"the retarget commit is the run's first. subjects={landed}"
    on_old = log_subjects(mission, OLD)
    for template in [DONE_SUBJECT, RETRO_SUBJECT] + ([FLATTEN_SUBJECT] if coordinated else []):
        subject = template.format(slug=mission.slug)
        assert subject in landed, f"{subject!r} missing on {NEW}. subjects={landed}"
        assert subject not in on_old, f"{subject!r} reached {OLD}"

    assert tip(mission, OLD) == pre_old and _reflogs(mission)[OLD] == reflogs_before[OLD], "the old target never moves"
    assert not blob_present_at(mission.repo, OLD, CODE_FILE), output
    assert kitty_specs_status(mission) == "", output
