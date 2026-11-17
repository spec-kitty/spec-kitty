"""``consolidate --target develop --retarget`` refusals and usage errors (#7692, WP04 T020).

Each refusal asserts the NFR-001 invariant set (``retarget_support.assert_refused_cleanly``) and,
where it has one, its ``--dry-run --json`` twin (SC-004). Positive controls on the same fixture
shape: ``test_consolidate_retarget.py`` (the success arm). ``RETARGET_WRITE_BRANCH_IS_RECORDED_TARGET``
is pinned end to end by ``tests/consolidation/test_retarget_record.py`` (WP03).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.terminus.conftest import _git as git
from tests.terminus.retarget_support import (
    NEW,
    OLD,
    RETARGET,
    RETARGET_RECORD_UNWRITABLE,
    assert_refused_cleanly,
    dry_run,
    kitty_specs_status,
    protect,
)
from tests.terminus.rollback_harness import flat
from tests.terminus.test_target_override_recorded_target_unwritable import _branches, _check_out_override, _consolidate, _lanes, _merge_records, _reflogs

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def test_a_protected_new_target_is_refused_with_dry_run_parity(tmp_path: Path) -> None:
    mission = _lanes(tmp_path, "01M7692P")
    protect(mission, f"protection:\n  protected_branches: [{NEW}]\n")
    _check_out_override(mission)
    before, reflogs_before = _branches(mission), _reflogs(mission)

    result = _consolidate(mission, *RETARGET)

    assert_refused_cleanly(mission, result, "PROTECTED_BRANCH_REFUSED", before, reflogs_before)
    forecast, payload = dry_run(mission, *RETARGET)
    assert forecast.returncode == 1 and payload.get("error_code") == "PROTECTED_BRANCH_REFUSED", payload
    assert _branches(mission) == before


def test_an_unwritable_record_on_the_new_target_is_refused_with_dry_run_parity(tmp_path: Path) -> None:
    """FR-011: ``develop`` carries ``meta.json`` but this run cannot commit it there: dirty, then untracked in the index."""
    mission = _lanes(tmp_path, "01M7692U")
    _check_out_override(mission)
    meta = mission.feature_dir / "meta.json"
    rel_meta = str(meta.relative_to(mission.repo))
    pristine = meta.read_text(encoding="utf-8")

    def _make_dirty() -> None:
        meta.write_text(pristine + "\n", encoding="utf-8")

    def _make_untracked() -> None:
        meta.write_text(pristine, encoding="utf-8")
        git(mission.repo, "rm", "-q", "--cached", rel_meta)

    for shape in (_make_dirty, _make_untracked):
        shape()
        before, reflogs_before, status_before = _branches(mission), _reflogs(mission), kitty_specs_status(mission)
        assert status_before, f"fixture precondition ({shape.__name__}): the record is not committable as is"

        result = _consolidate(mission, *RETARGET)

        assert_refused_cleanly(mission, result, RETARGET_RECORD_UNWRITABLE, before, reflogs_before, status_before=status_before)
        forecast, payload = dry_run(mission, *RETARGET)
        assert forecast.returncode == 1 and payload.get("error_code") == RETARGET_RECORD_UNWRITABLE, (shape.__name__, payload)
        assert _branches(mission) == before and kitty_specs_status(mission) == status_before


@pytest.mark.parametrize(("flag", "clear"), [("--skip-worktree", "--no-skip-worktree"), ("--assume-unchanged", "--no-assume-unchanged")])
def test_an_index_bit_on_the_new_targets_record_is_refused_with_dry_run_parity(tmp_path: Path, flag: str, clear: str) -> None:
    """FR-011: a skip-worktree or assume-unchanged bit on ``develop``'s ``meta.json``, with no edit, is refused up front.

    The bit hides the file from git: the record commit and the landing's checkout resync cannot
    be trusted with it (witnessed before the fold: the run failed in the landing and the rollback
    could not resync ``develop``, which stayed at the squash commit). The remedy names the bit.
    """
    mission = _lanes(tmp_path, "01M7692I")
    _check_out_override(mission)
    git(mission.repo, "update-index", flag, str((mission.feature_dir / "meta.json").relative_to(mission.repo)))
    before, reflogs_before = _branches(mission), _reflogs(mission)

    result = _consolidate(mission, *RETARGET)

    assert_refused_cleanly(mission, result, RETARGET_RECORD_UNWRITABLE, before, reflogs_before)
    assert f"git update-index {clear}" in flat(result), flat(result)
    forecast, payload = dry_run(mission, *RETARGET)
    assert forecast.returncode == 1 and payload.get("error_code") == RETARGET_RECORD_UNWRITABLE, payload
    assert _branches(mission) == before


def test_untracked_mission_copies_on_a_new_target_cut_before_the_mission_are_refused_with_dry_run_parity(tmp_path: Path) -> None:
    """``develop`` cut at the init commit, the Mission's files present in the root checkout only as untracked copies.

    ``develop`` is not a holder (the Mission branch carries ``meta.json``, plan D4), so the landing
    would write ``kitty-specs/<slug>/`` into a root checkout whose untracked copies it would
    overwrite. Refused up front with ``RETARGET_RECORD_UNWRITABLE`` (before the fold the run
    mutated, failed at the resync and rolled back, while ``--dry-run`` forecast a landing).
    Without the untracked copies the CLI cannot resolve the Mission at all ("Mission not found").
    """
    mission = _lanes(tmp_path, "01M7692B")
    init = git(mission.repo, "rev-list", "--max-parents=0", OLD).stdout.split()[0]
    git(mission.repo, "checkout", "-qb", NEW, init)
    git(mission.repo, "checkout", OLD, "--", "kitty-specs", ".kittify")
    git(mission.repo, "reset", "-q")
    before, reflogs_before, status_before = _branches(mission), _reflogs(mission), kitty_specs_status(mission)

    result = _consolidate(mission, *RETARGET)

    assert_refused_cleanly(mission, result, RETARGET_RECORD_UNWRITABLE, before, reflogs_before, status_before=status_before)
    assert "untracked" in flat(result) and "overwrite" in flat(result), flat(result)
    forecast, payload = dry_run(mission, *RETARGET)
    assert forecast.returncode == 1 and payload.get("error_code") == RETARGET_RECORD_UNWRITABLE, payload
    assert _branches(mission) == before and kitty_specs_status(mission) == status_before


def test_retarget_flag_misuse_is_a_usage_error(tmp_path: Path) -> None:
    """``--retarget`` without ``--target`` and ``--retarget-reason`` without ``--retarget``: exit 2, nothing moves."""
    mission = _lanes(tmp_path, "01M7692V")
    before, reflogs_before = _branches(mission), _reflogs(mission)

    for flags, message in ((("--retarget",), "--retarget requires --target"), (("--retarget-reason", "x"), "--retarget-reason requires --retarget")):
        result = _consolidate(mission, *flags)

        assert result.returncode == 2, flat(result)
        assert message in flat(result), flat(result)
        assert _branches(mission) == before and _reflogs(mission) == reflogs_before and _merge_records(mission) == []
