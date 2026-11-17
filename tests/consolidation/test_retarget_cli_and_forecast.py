"""#7692 WP02: the ``consolidate --retarget`` CLI flags and the ``--dry-run`` forecast's retarget arm.

* Misuse is a usage error (exit 2) before any work runs: ``--retarget`` without ``--target``,
  ``--retarget-reason`` without ``--retarget``, ``--abort --retarget``. A blank reason is absent.
* The flags reach the executor (``_run_lane_based_consolidation(retarget=, retarget_reason=)``),
  on a fresh run and on ``--resume``, and the forecast (``run_dry_run_forecast(retarget=)``).
* The forecast mirrors the entry preflight (FR-009): ``RETARGET_RESUME_MISMATCH`` (only with a
  merge record), then the write-branch refusal, then the re-pointed #5385 probe, then
  ``target_override_verdict(retarget=True)``; each refusal carries the verdict's own
  ``error_code``. A clean retarget forecast carries ``"retarget": {"from", "to"}``; restating the
  recorded target is no retarget (FR-012: no ``retarget`` object, ``retarget=False``).
* Claim parity: the forecast's LIVE claim reads the status surface swapped the way the run's is.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.cli.commands import consolidate as consolidate_mod
from specify_cli.cli.commands.consolidate import ConsolidateOptions, _validated_retarget_flags, run_consolidate
from specify_cli.consolidation import claim_inputs as claim_inputs_mod
from specify_cli.consolidation import forecast, preflight
from specify_cli.consolidation.claim_inputs import ClaimInputContext
from specify_cli.consolidation.state import ConsolidationState
from specify_cli.coordination.types import Refused
from specify_cli.status.models import Lane
from tests.reliability.fixtures import WorkPackageSpec, append_status_event, create_mission_fixture, write_work_package
from tests.specify_cli.cli.commands.test_merge_cli_golden import _build_merge_app, _patch_dry_run_git_boundaries, _write_lanes_json

pytestmark = pytest.mark.fast

_UNWRITABLE = Refused(
    error_code=preflight.RETARGET_RECORD_UNWRITABLE, message="meta.json is dirty on 'develop'.", destination_ref="develop", next_step="Commit or discard it."
)
_PROTECTED = Refused(error_code="PROTECTED_BRANCH_REFUSED", message="'main' is protected.", destination_ref="main", next_step="Open a PR.")


class _Sentinel(Exception):
    """Raised by a stub to stop the run once it captured what it needed."""


def _no_work(monkeypatch: pytest.MonkeyPatch) -> None:
    """A usage refusal must come before any repository work."""

    def _boom() -> Path:
        raise AssertionError("usage misuse must refuse before any work runs")

    monkeypatch.setattr(consolidate_mod, "find_repo_root", _boom)


# --------------------------------------------------------------------------- #
# T007: flag validation (exit 2, nothing runs)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("options", "fragment"),
    [
        (ConsolidateOptions(retarget=True), "--retarget requires --target"),
        (ConsolidateOptions(retarget=True, target_branch="   "), "--retarget requires --target"),
        (ConsolidateOptions(retarget_reason="why", target_branch="develop"), "--retarget-reason requires --retarget"),
        (ConsolidateOptions(abort=True, retarget=True, target_branch="develop"), "--retarget does not apply to"),
    ],
)
def test_retarget_misuse_exits_2_before_any_work(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], options: ConsolidateOptions, fragment: str
) -> None:
    _no_work(monkeypatch)
    with pytest.raises(typer.Exit) as excinfo:
        run_consolidate(options)
    assert excinfo.value.exit_code == 2
    out = " ".join(capsys.readouterr().out.split())
    assert fragment in out
    assert "Nothing was changed" in out


def test_the_cli_parses_the_flags_and_refuses_misuse_with_exit_2(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    _no_work(monkeypatch)
    result = CliRunner().invoke(_build_merge_app(), ["--retarget"])
    assert result.exit_code == 2, result.output
    assert "--retarget requires --target" in " ".join(result.output.split())


def test_validated_flags_treat_a_blank_reason_as_absent() -> None:
    assert _validated_retarget_flags(False, "   ", None, abort=False) == (False, None)
    assert _validated_retarget_flags(True, "  ", "develop", abort=False) == (True, None)
    assert _validated_retarget_flags(True, " moved to develop ", "develop", abort=False) == (True, "moved to develop")


def test_validated_flags_tolerate_the_unresolved_option_sentinels() -> None:
    """A direct Python call that leaves the ``typer.Option`` sentinels in place asks for no retarget."""
    assert _validated_retarget_flags(typer.Option(False), typer.Option(None), None, abort=False) == (False, None)


# --------------------------------------------------------------------------- #
# T007: threading into the executor and the forecast
# --------------------------------------------------------------------------- #


def _stub_run_entry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, target: str = "develop") -> None:
    monkeypatch.setattr(consolidate_mod, "show_banner", lambda: None)
    monkeypatch.setattr(consolidate_mod, "find_repo_root", lambda: tmp_path)
    monkeypatch.setattr(consolidate_mod, "_enforce_git_preflight", lambda *_a, **_k: None)
    monkeypatch.setattr(consolidate_mod, "_resolve_slug_or_exit", lambda *_a, **_k: "m")
    monkeypatch.setattr(consolidate_mod, "_resolved_mission_dir_exists", lambda *_a, **_k: True)
    monkeypatch.setattr(consolidate_mod, "load_state", lambda *_a, **_k: None)
    monkeypatch.setattr(consolidate_mod, "_resolve_target_branch", lambda *_a, **_k: (target, "cli"))
    monkeypatch.setattr(consolidate_mod, "_validate_target_branch", lambda *_a, **_k: None)
    monkeypatch.setattr(consolidate_mod, "_enforce_retention_cleanup", lambda *_a, **_k: None)
    monkeypatch.setattr(consolidate_mod, "_dispatch_resume", lambda *_a, **_k: "m")
    monkeypatch.setattr(consolidate_mod, "_load_merge_state_for_mission", lambda *_a, **_k: None)


def _capture(calls: list[dict[str, Any]]) -> Any:
    def _fake(*_a: object, **kwargs: Any) -> None:
        calls.append(kwargs)
        raise _Sentinel

    return _fake


@pytest.mark.parametrize("resume", [False, True])
def test_the_flags_reach_the_executor(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, resume: bool) -> None:
    _stub_run_entry(monkeypatch, tmp_path)
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(consolidate_mod, "_run_lane_based_consolidation", _capture(calls))

    with pytest.raises(_Sentinel):
        run_consolidate(ConsolidateOptions(target_branch="develop", retarget=True, retarget_reason=" moved ", resume=resume))

    assert len(calls) == 1
    assert calls[0]["target_override"] == "develop"
    assert calls[0]["retarget"] is True
    assert calls[0]["retarget_reason"] == "moved"


def test_a_plain_target_threads_no_retarget(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _stub_run_entry(monkeypatch, tmp_path)
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(consolidate_mod, "_run_lane_based_consolidation", _capture(calls))

    with pytest.raises(_Sentinel):
        run_consolidate(ConsolidateOptions(target_branch="develop"))

    assert calls[0]["retarget"] is False
    assert calls[0]["retarget_reason"] is None


def test_the_flag_reaches_the_forecast(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _stub_run_entry(monkeypatch, tmp_path)
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(consolidate_mod, "run_dry_run_forecast", _capture(calls))

    with pytest.raises(_Sentinel):
        run_consolidate(ConsolidateOptions(target_branch="develop", retarget=True, dry_run=True, json_output=True))

    assert calls[0]["retarget"] is True
    assert calls[0]["resolved_target_branch"] == "develop"


# --------------------------------------------------------------------------- #
# T009: the forecast's retarget arm, through the real CLI on a fixture Mission
# --------------------------------------------------------------------------- #


class _Verdicts:
    """Stubs the forecast's verdict calls and records how they were asked."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, *, recorded: str = "main") -> None:
        self.status_calls: list[dict[str, Any]] = []
        self.override_calls: list[dict[str, Any]] = []
        self.status_verdict: Refused | None = None
        self.override_verdict: Refused | None = None
        monkeypatch.setattr(forecast, "_forecast_recorded_target", lambda *_a, **_k: recorded)
        monkeypatch.setattr(forecast, "refuse_protected_status_target", self._status)
        monkeypatch.setattr(forecast, "target_override_verdict", self._override)

    def _status(self, *_a: object, **kwargs: Any) -> Refused | None:
        self.status_calls.append(kwargs)
        return self.status_verdict

    def _override(self, *_a: object, **kwargs: Any) -> Refused | None:
        self.override_calls.append(kwargs)
        return self.override_verdict


def _fixture_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, target: str) -> Any:
    mission = create_mission_fixture(tmp_path)
    write_work_package(mission, WorkPackageSpec(lane="approved"))
    append_status_event(mission, from_lane=Lane.FOR_REVIEW, to_lane=Lane.APPROVED, event_id="01M7M5JAWP02FORECAST00001")
    _write_lanes_json(mission)
    monkeypatch.chdir(mission.repo_root)
    _patch_dry_run_git_boundaries(monkeypatch, mission)
    monkeypatch.setattr(consolidate_mod, "_resolve_target_branch", lambda *_a, **_k: (target, "cli"))
    # The fixture repository has no ``develop``; the content forecast is not under test here.
    monkeypatch.setattr(forecast, "_refuse_unattributable_in_forecast", lambda **_k: None)
    monkeypatch.setattr(forecast, "preview_mission_target_integration", lambda *_a, **_k: SimpleNamespace(conflicting_paths=(), squashed_tree=None))
    return mission


def _dry_run(mission: Any, *extra: str) -> Any:
    return CliRunner().invoke(_build_merge_app(), ["--mission", mission.mission_slug, "--dry-run", *extra])


def _payload(result: Any) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(result.stdout.strip().splitlines()[-1])
    return payload


def test_a_clean_retarget_forecast_carries_the_retarget_object(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission = _fixture_mission(tmp_path, monkeypatch, target="develop")
    verdicts = _Verdicts(monkeypatch)

    result = _dry_run(mission, "--json", "--target", "develop", "--retarget")

    assert result.exit_code == 0, result.stdout
    assert _payload(result)["retarget"] == {"from": "main", "to": "develop"}
    assert verdicts.override_calls == [{"recorded_target": "main", "effective_target": "develop", "retarget": True}]
    assert verdicts.status_calls[0].get("retarget_to") == "develop", "the #5385 probe is re-pointed, never skipped"


def test_a_clean_retarget_forecast_prints_one_human_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission = _fixture_mission(tmp_path, monkeypatch, target="develop")
    _Verdicts(monkeypatch)

    result = _dry_run(mission, "--target", "develop", "--retarget")

    assert result.exit_code == 0, result.stdout
    assert "Retarget: main -> develop (would be recorded first)" in result.stdout


def test_restating_the_recorded_target_is_no_retarget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-012: ``--target <recorded> --retarget`` forecasts exactly as without the flag."""
    mission = _fixture_mission(tmp_path, monkeypatch, target="main")
    verdicts = _Verdicts(monkeypatch)

    result = _dry_run(mission, "--json", "--target", "main", "--retarget")

    assert result.exit_code == 0, result.stdout
    assert "retarget" not in _payload(result)
    assert verdicts.override_calls == [{"recorded_target": "main", "effective_target": "main", "retarget": False}]
    assert "retarget_to" not in verdicts.status_calls[0]


def test_a_plain_target_forecast_keeps_todays_chain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission = _fixture_mission(tmp_path, monkeypatch, target="develop")
    verdicts = _Verdicts(monkeypatch)
    verdicts.override_verdict = Refused(
        error_code=preflight.TARGET_OVERRIDE_RECORDED_TARGET_UNWRITABLE, message="'main' cannot be written.", destination_ref="main", next_step="Drop --target."
    )

    result = _dry_run(mission, "--json", "--target", "develop")

    assert result.exit_code == 1
    assert _payload(result)["error_code"] == preflight.TARGET_OVERRIDE_RECORDED_TARGET_UNWRITABLE
    assert verdicts.override_calls[0]["retarget"] is False
    assert "retarget_to" not in verdicts.status_calls[0]


@pytest.mark.parametrize("refusal", [_UNWRITABLE, _PROTECTED])
def test_a_retarget_verdict_refusal_carries_its_own_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, refusal: Refused) -> None:
    mission = _fixture_mission(tmp_path, monkeypatch, target="develop")
    verdicts = _Verdicts(monkeypatch)
    verdicts.override_verdict = refusal

    result = _dry_run(mission, "--json", "--target", "develop", "--retarget")

    assert result.exit_code == 1
    payload = _payload(result)
    assert payload["error_code"] == refusal.error_code
    assert "retarget" not in payload


def test_the_re_pointed_status_probe_refusal_carries_its_own_code(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mission = _fixture_mission(tmp_path, monkeypatch, target="develop")
    verdicts = _Verdicts(monkeypatch)
    verdicts.status_verdict = _PROTECTED

    result = _dry_run(mission, "--json", "--target", "develop", "--retarget")

    assert result.exit_code == 1
    assert _payload(result)["error_code"] == "PROTECTED_BRANCH_REFUSED"
    assert verdicts.override_calls == [], "the #5385 probe refuses before the override verdict, as in the run"


# --------------------------------------------------------------------------- #
# T009: the forecast helpers (entry-preflight order)
# --------------------------------------------------------------------------- #


def _manifest(mission_branch: str = "kitty/mission-m") -> Any:
    return SimpleNamespace(mission_branch=mission_branch, mission_id="01M7M5JA00000000000000000F", target_branch="main", lanes=[])


def _persist(monkeypatch: pytest.MonkeyPatch, pair: tuple[str, str] | None) -> None:
    state = ConsolidationState(mission_id="01M7M5JA00000000000000000F", mission_slug="m", target_branch="main", wp_order=[])
    if pair is not None:
        state.retarget = {"from": pair[0], "to": pair[1], "actor": "op", "at": "2026-11-17T09:00:00+00:00", "reason": "r", "committed": False}
    monkeypatch.setattr(preflight, "load_state", lambda *_a, **_k: state)


def _pair(tmp_path: Path, *, retarget: bool, effective: str = "develop") -> tuple[str, str] | None:
    result: tuple[str, str] | None = forecast._forecast_retarget_pair(
        tmp_path, "m", _manifest(), retarget=retarget, recorded_target="main", effective_target=effective, json_output=True
    )
    return result


def test_a_retarget_naming_another_target_than_the_persisted_one_refuses_resume_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _persist(monkeypatch, ("main", "release"))

    with pytest.raises(typer.Exit) as excinfo:
        _pair(tmp_path, retarget=True)

    assert excinfo.value.exit_code == 1
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["error_code"] == preflight.RETARGET_RESUME_MISMATCH
    assert "'release'" in payload["error"] and "'develop'" in payload["error"]


def test_a_persisted_retarget_is_judged_as_a_retarget_without_the_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _persist(monkeypatch, ("main", "develop"))
    assert _pair(tmp_path, retarget=False) == ("main", "develop")


def test_no_merge_record_means_no_resume_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preflight, "load_state", lambda *_a, **_k: None)
    assert _pair(tmp_path, retarget=True) == ("main", "develop")
    assert _pair(tmp_path, retarget=False) is None
    assert _pair(tmp_path, retarget=True, effective="main") is None


def test_an_unreadable_merge_record_reads_as_no_persisted_retarget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.consolidation.state import ConsolidationStateReadError

    def _raise(*_a: object, **_k: object) -> None:
        raise ConsolidationStateReadError("corrupt")

    monkeypatch.setattr(preflight, "load_state", _raise)
    assert _pair(tmp_path, retarget=True) == ("main", "develop")


def test_the_write_branch_refusal_comes_before_the_status_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """A commit-to-target Mission (its write branch IS the recorded target) refuses with the run's code."""
    probed: list[object] = []
    monkeypatch.setattr(forecast, "refuse_protected_status_target", lambda *_a, **_k: probed.append(_k))

    with pytest.raises(typer.Exit):
        forecast._refuse_protected_status_target_in_forecast(tmp_path, "m", _manifest(mission_branch="main"), json_output=True, retarget_pair=("main", "develop"))

    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["error_code"] == preflight.RETARGET_WRITE_BRANCH_IS_RECORDED_TARGET
    assert probed == []


# --------------------------------------------------------------------------- #
# T009 step 5: claim parity
# --------------------------------------------------------------------------- #


def test_the_live_claim_reads_the_retargeted_status_surface(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[object] = []

    def _tip(*_a: object, **kwargs: Any) -> tuple[str, str]:
        seen.append(kwargs.get("retarget"))
        return "develop", "abc123"

    monkeypatch.setattr(claim_inputs_mod, "status_surface_tip", _tip)
    context = ClaimInputContext(
        repo_root=tmp_path, manifest=_manifest(), status_dir=tmp_path, strategy="squash", resolved_target_base=None, mission_slug="m", retarget=("main", "develop")
    )

    assert claim_inputs_mod._live_coord_base(context) == "abc123"
    assert seen == [("main", "develop")]


def test_the_forecast_builds_its_claim_with_the_retarget_pair(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    contexts: list[ClaimInputContext] = []

    def _inputs(_source: object, context: ClaimInputContext) -> None:
        contexts.append(context)
        raise _Sentinel

    monkeypatch.setattr(forecast, "get_main_repo_root", lambda repo: repo)
    monkeypatch.setattr(forecast, "_declared_with_recorded", lambda *_a, **_k: ((), {}))
    monkeypatch.setattr(forecast, "resolve_commit", lambda *_a, **_k: "base")
    monkeypatch.setattr(forecast, "_forecast_claim_status_dir", lambda *_a, **_k: tmp_path)
    monkeypatch.setattr(forecast, "claim_inputs", _inputs)

    with pytest.raises(_Sentinel):
        forecast._refuse_unattributable_in_forecast(
            repo_root=tmp_path,
            resolved_feature="m",
            resolved_target_branch="develop",
            lanes_manifest=_manifest(),
            dependency_refs=(),
            json_output=True,
            retarget=("main", "develop"),
        )

    assert contexts[0].retarget == ("main", "develop")
