"""A skip-worktree entry the landing would overwrite is refused before any branch moves (#7692 follow-up).

Witnessed while building the retarget refusals (WP04): a PLAIN ``spec-kitty consolidate`` onto
``main``, with the skip-worktree bit set (and no edit) on the root checkout's
``kitty-specs/<slug>/meta.json``, landed, then failed the checkout resync ("Entry ... not
uptodate. Cannot merge") after the run's own ``meta.json`` write was left out of its bookkeeping
commit by the bit and the baseline validation failed. The rollback restored the branch tips but left the root checkout's
index holding the squash content and kept the merge record. The checkout resync contract is not
changed: the run now refuses up front, pre-lock and before any snapshot, with
``CHECKOUT_SKIP_WORKTREE_ENTRIES``; ``--dry-run`` and ``orchestrator-api consolidate-mission``
(contract 1.29.0) report the same code. An assume-unchanged bit lands fine and is not refused.
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


@pytest.mark.parametrize("name", ["meta.json", "status.events.jsonl"])
def test_consolidate_mission_refuses_with_the_same_code(tmp_path: Path, name: str) -> None:
    """``orchestrator-api consolidate-mission`` refuses too (contract 1.29.0), before any branch moves.

    Witnessed before the refusal: with the bit on ``status.events.jsonl`` the command squashed onto
    ``main``, then its ``done`` status commit failed (``BookkeepingCommitFailed`` traceback, empty
    stdout, exit 1) and, with no rollback door, the landing stayed without its bookkeeping. With the
    bit on ``meta.json`` (which this path never writes) it landed; the one helper refuses both.
    """
    from specify_cli.orchestrator_api.envelope import CONTRACT_VERSION
    from tests.orchestrator_api.test_consolidate_mission_protected_target import _envelope

    mission = _lanes(tmp_path, "01M7692X")
    path = f"kitty-specs/{mission.slug}/{name}"
    git(mission.repo, "update-index", "--skip-worktree", path)
    before = _snapshot(mission)

    result = run_terminus(mission, ["orchestrator-api", "consolidate-mission", "--mission", mission.slug, "--strategy", "squash"])

    envelope = _envelope(result)
    assert envelope["success"] is False and envelope["error_code"] == "PREFLIGHT_FAILED", envelope
    assert envelope["contract_version"] == CONTRACT_VERSION, envelope
    data = envelope["data"]
    assert isinstance(data, dict), envelope
    assert data.get("preflight_error_code") == _CODE and data.get("preflight_error_codes") == [_CODE], envelope
    assert path in " ".join(str(error) for error in data.get("errors", [])), envelope
    assert _snapshot(mission) == before, flat(result)
    assert not blob_present_at(mission.repo, _TARGET, CODE_FILE)
    assert _index_clean(mission)


def test_an_assume_unchanged_meta_json_still_lands(tmp_path: Path) -> None:
    mission = _lanes(tmp_path, "01M7692U")
    git(mission.repo, "update-index", "--assume-unchanged", _meta(mission))

    result = _consolidate(mission)

    assert result.returncode == 0, flat(result)
    assert blob_present_at(mission.repo, _TARGET, CODE_FILE)
