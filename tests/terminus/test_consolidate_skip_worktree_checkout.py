"""A skip-worktree entry the landing would overwrite is refused before any branch moves (#7692 follow-up).

Witnessed while building the retarget refusals (WP04): a PLAIN ``spec-kitty consolidate`` onto
``main``, with the skip-worktree bit set (and no edit) on the root checkout's
``kitty-specs/<slug>/meta.json``, landed, then failed the checkout resync ("Entry ... not
uptodate. Cannot merge"). The rollback restored the branch tips but left the root checkout's
index holding the squash content and kept the merge record. The checkout resync contract is not
changed: the run now refuses up front, pre-lock and before any snapshot, with
``CHECKOUT_SKIP_WORKTREE_ENTRIES``, and ``--dry-run`` reports the same code. An assume-unchanged
bit lands fine and is not refused; ``orchestrator-api consolidate-mission`` lands through its own
path, which this resync never fails, and is left unrefused.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.terminus.conftest import CoordMission, blob_present_at, run_terminus
from tests.terminus.conftest import _git as git
from tests.terminus.retarget_support import CODE_FILE, PREFLIGHT_LINE, dry_run
from tests.terminus.rollback_harness import flat, reflog_shas
from tests.terminus.test_target_override_recorded_target_unwritable import _branches, _consolidate, _lanes, _merge_records

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_CODE = "CHECKOUT_SKIP_WORKTREE_ENTRIES"
_TARGET = "main"


def _meta(mission: CoordMission) -> str:
    return f"kitty-specs/{mission.slug}/meta.json"


def _index_clean(mission: CoordMission) -> bool:
    return subprocess.run(["git", "-C", str(mission.repo), "diff", "--cached", "--quiet"], check=False).returncode == 0


def _snapshot(mission: CoordMission) -> tuple[dict[str, str], dict[str, list[str]]]:
    return _branches(mission), {b: reflog_shas(mission, b) for b in (_TARGET, mission.coord_branch)}


def test_a_skip_worktree_meta_json_is_refused_before_any_branch_moves(tmp_path: Path) -> None:
    mission = _lanes(tmp_path, "01M7692Y")
    git(mission.repo, "update-index", "--skip-worktree", _meta(mission))
    before = _snapshot(mission)

    forecast, payload = dry_run(mission)
    assert forecast.returncode == 1, flat(forecast)
    assert payload.get("error_code") == _CODE, payload

    result = _consolidate(mission)

    output = flat(result)
    assert result.returncode == 1, output
    assert _CODE in output and PREFLIGHT_LINE in output, output
    assert _meta(mission) in output and f"git update-index --no-skip-worktree {_meta(mission)}" in output, output
    assert "Traceback" not in result.stderr, result.stderr
    assert _snapshot(mission) == before, f"no branch may move, nor move and come back. output={output}"
    assert _merge_records(mission) == [], output
    assert _index_clean(mission), git(mission.repo, "status", "--porcelain").stdout
    assert not blob_present_at(mission.repo, _TARGET, CODE_FILE), output

    git(mission.repo, "update-index", "--no-skip-worktree", _meta(mission))
    landed = _consolidate(mission)
    assert landed.returncode == 0, flat(landed)
    assert blob_present_at(mission.repo, _TARGET, CODE_FILE)


def test_consolidate_mission_lands_with_the_bit_set_and_is_not_refused(tmp_path: Path) -> None:
    """``orchestrator-api consolidate-mission`` lands through its own path, which never fails this resync.

    Witnessed before the refusal was added: exit 0, landed, clean index, no merge record. Refusing it
    would turn a working call into a refusal (a contract change), so the command is left as it is.
    """
    from tests.orchestrator_api.test_consolidate_mission_protected_target import _envelope

    mission = _lanes(tmp_path, "01M7692X")
    git(mission.repo, "update-index", "--skip-worktree", _meta(mission))

    result = run_terminus(mission, ["orchestrator-api", "consolidate-mission", "--mission", mission.slug, "--strategy", "squash"])

    envelope = _envelope(result)
    assert envelope["success"] is True, envelope
    assert blob_present_at(mission.repo, _TARGET, CODE_FILE)
    assert _merge_records(mission) == []
    assert _index_clean(mission)


def test_an_assume_unchanged_meta_json_still_lands(tmp_path: Path) -> None:
    mission = _lanes(tmp_path, "01M7692U")
    git(mission.repo, "update-index", "--assume-unchanged", _meta(mission))

    result = _consolidate(mission)

    assert result.returncode == 0, flat(result)
    assert blob_present_at(mission.repo, _TARGET, CODE_FILE)
