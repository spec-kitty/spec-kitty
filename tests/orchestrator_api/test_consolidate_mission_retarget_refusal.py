"""#7692 FR-010: ``orchestrator-api consolidate-mission`` has no ``--retarget`` and keeps its envelope.

The command now asks the CLI's ONE override verdict (``target_override_verdict(retarget=False)``)
instead of chaining #6464 and #5783 itself. Its envelope does not change: a differing target whose
recorded target cannot be written stays ``PREFLIGHT_FAILED`` with
``data.preflight_error_code == TARGET_OVERRIDE_RECORDED_TARGET_UNWRITABLE``; the only visible change
is the shared next step, which now also names ``spec-kitty consolidate --target <b> --retarget``.
The #6464 refusal stays a plain ``RuntimeError`` and ``CONTRACT_VERSION`` is unchanged (its one
pin lives in ``tests/specify_cli/orchestrator_api/test_contract_version.py``).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import pytest

from specify_cli.consolidation import preflight
from specify_cli.coordination.types import Refused
from specify_cli.orchestrator_api import consolidation as orch
from specify_cli.orchestrator_api.consolidation import CodedPreflightRefused
from specify_cli.orchestrator_api.envelope import CONTRACT_VERSION
from tests.orchestrator_api.test_consolidate_mission_protected_target import _envelope, _unprotected_main_mission
from tests.terminus.conftest import _git as git
from tests.terminus.conftest import blob_present_at, run_terminus
from tests.terminus.rollback_harness import flat, ref_shas

if TYPE_CHECKING:
    from specify_cli.lanes.models import LanesManifest

_UNWRITABLE = preflight.TARGET_OVERRIDE_RECORDED_TARGET_UNWRITABLE
# FR-010: #7692 does not bump ``CONTRACT_VERSION``. Its value is pinned in ONE place,
# ``tests/specify_cli/orchestrator_api/test_contract_version.py`` (the gate there forbids a second
# literal), which this change leaves untouched; this file asserts the envelope carries it.


def _manifest() -> LanesManifest:
    """A duck-typed manifest: the guard reads only ``target_branch``."""
    return cast("LanesManifest", SimpleNamespace(target_branch="develop"))


def _ask(monkeypatch: pytest.MonkeyPatch, verdict: Refused | None) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def _verdict(*_a: object, **kwargs: Any) -> Refused | None:
        calls.append(kwargs)
        return verdict

    monkeypatch.setattr("specify_cli.core.paths.resolve_merge_target_branch", lambda *_a, **_k: ("main", "meta"))
    monkeypatch.setattr(preflight, "target_override_verdict", _verdict)
    return calls


@pytest.mark.fast
def test_the_command_asks_the_one_verdict_without_a_retarget(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls = _ask(monkeypatch, None)
    orch._refuse_protected_target_override(tmp_path, "m", _manifest())
    assert calls == [{"recorded_target": "main", "effective_target": "develop", "retarget": False}]


@pytest.mark.fast
def test_a_protected_override_stays_a_plain_runtime_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _ask(monkeypatch, Refused(error_code="PROTECTED_BRANCH_REFUSED", message="'develop' is protected.", destination_ref="develop", next_step="Open a PR."))
    with pytest.raises(RuntimeError) as excinfo:
        orch._refuse_protected_target_override(tmp_path, "m", _manifest())
    assert type(excinfo.value) is RuntimeError
    assert str(excinfo.value) == "PROTECTED_BRANCH_REFUSED: 'develop' is protected. Next step: Open a PR."


@pytest.mark.fast
def test_an_unwritable_recorded_target_stays_a_coded_refusal(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _ask(monkeypatch, Refused(error_code=_UNWRITABLE, message="'main' cannot be written.", destination_ref="main", next_step="Drop --target."))
    with pytest.raises(CodedPreflightRefused) as excinfo:
        orch._refuse_protected_target_override(tmp_path, "m", _manifest())
    assert type(excinfo.value) is CodedPreflightRefused
    assert excinfo.value.error_code == _UNWRITABLE


@pytest.mark.integration
@pytest.mark.git_repo
@pytest.mark.regression
def test_a_differing_target_keeps_the_envelope_and_names_retarget(tmp_path: Path) -> None:
    mission = _unprotected_main_mission(tmp_path, "01M7692O", "lanes")
    git(mission.repo, "checkout", "-qb", "develop", "main")
    before = ref_shas(mission)

    result = run_terminus(
        mission,
        ["orchestrator-api", "consolidate-mission", "--mission", mission.slug, "--target", "develop", "--strategy", "squash"],
    )

    output = flat(result)
    assert result.returncode != 0, output
    envelope = _envelope(result)
    assert envelope["success"] is False, envelope
    assert envelope["error_code"] == "PREFLIGHT_FAILED", envelope
    assert envelope["contract_version"] == CONTRACT_VERSION, envelope
    data = envelope["data"]
    assert isinstance(data, dict), envelope
    assert data.get("preflight_error_code") == _UNWRITABLE, envelope
    assert data.get("preflight_error_codes") == [_UNWRITABLE], envelope
    assert "spec-kitty consolidate --target develop --retarget" in " ".join(str(error) for error in data.get("errors", [])), envelope
    assert ref_shas(mission) == before, f"no branch tip may move. output={output}"
    assert not blob_present_at(mission.repo, "develop", "src/pkg/wp01.py"), output


# --- mission review RISK-1: a persisted retarget is never executed by this command ---------------

_MISMATCH = preflight.RETARGET_RESUME_MISMATCH
_MISSION_ID = "01M7M5JA00000000000000000Q"


def _persist_retarget(repo: Path) -> None:
    from specify_cli.consolidation.state import ConsolidationState, save_state

    state = ConsolidationState(mission_id=_MISSION_ID, mission_slug="m", target_branch="develop", wp_order=["WP01"])
    state.retarget = {"from": "main", "to": "develop", "actor": "op", "at": "2026-11-17T09:00:00+00:00", "reason": "r", "committed": False}
    save_state(state, repo)


@pytest.mark.fast
@pytest.mark.parametrize("target", ["main", "develop", "release"])
def test_a_persisted_retarget_is_refused_whatever_the_target(tmp_path: Path, target: str) -> None:
    """``consolidate-mission`` has no ``--retarget``: it neither re-lands nor silently finishes a persisted one."""
    _persist_retarget(tmp_path)
    manifest = cast("LanesManifest", SimpleNamespace(target_branch=target, mission_id=_MISSION_ID))
    with pytest.raises(CodedPreflightRefused) as excinfo:
        orch._refuse_persisted_retarget(tmp_path, "m", manifest)
    assert excinfo.value.error_code == _MISMATCH
    text = str(excinfo.value)
    assert "'main' to 'develop'" in text and "spec-kitty consolidate --mission m --resume" in text and "--abort" in text, text


@pytest.mark.fast
def test_no_persisted_retarget_is_not_refused(tmp_path: Path) -> None:
    orch._refuse_persisted_retarget(tmp_path, "m", cast("LanesManifest", SimpleNamespace(target_branch="main", mission_id=_MISSION_ID)))


@pytest.mark.integration
@pytest.mark.git_repo
@pytest.mark.regression
def test_a_failed_retarget_is_not_executed_by_consolidate_mission(tmp_path: Path) -> None:
    """After a failed ``consolidate --target develop --retarget``, the command refuses before any branch moves."""
    from tests.terminus.retarget_support import RETARGET, merge_record, run_patched
    from tests.terminus.rollback_harness import reflog_shas

    mission = _unprotected_main_mission(tmp_path, "01M7692Q", "lanes")
    git(mission.repo, "checkout", "-qb", "develop", "main")
    failed = run_patched(mission, "executor", "_phase_merge_lanes", *RETARGET, kill=False)
    assert failed.returncode != 0, flat(failed)
    record = merge_record(mission)
    assert record is not None and record["retarget"]["to"] == "develop", record
    git(mission.repo, "checkout", "-q", "main")
    before = ref_shas(mission)
    reflogs = {b: reflog_shas(mission, b) for b in ("main", "develop", mission.coord_branch)}

    result = run_terminus(mission, ["orchestrator-api", "consolidate-mission", "--mission", mission.slug, "--strategy", "squash"])

    envelope = _envelope(result)
    assert envelope["success"] is False and envelope["error_code"] == "PREFLIGHT_FAILED", envelope
    assert envelope["contract_version"] == CONTRACT_VERSION, envelope
    data = envelope["data"]
    assert isinstance(data, dict), envelope
    assert data.get("preflight_error_code") == _MISMATCH and data.get("preflight_error_codes") == [_MISMATCH], envelope
    assert ref_shas(mission) == before, flat(result)
    assert {b: reflog_shas(mission, b) for b in ("main", "develop", mission.coord_branch)} == reflogs, flat(result)
    assert merge_record(mission) == record
    assert not blob_present_at(mission.repo, "main", "src/pkg/wp01.py")
    assert not blob_present_at(mission.repo, "develop", "src/pkg/wp01.py")
