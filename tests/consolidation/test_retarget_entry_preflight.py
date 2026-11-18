"""#7692 T008: the entry preflight's retarget arm (``consolidate --target <b> --retarget``).

The verdicts themselves are WP01's (``tests/consolidation/test_retarget_verdict.py``); this file
pins how ``entry_preflight`` composes them before anything moves:

* a retarget is judged against the NEW target (``target_override_verdict(retarget=True)``) and
  the #5385 probe is re-pointed (``retarget_to``), never skipped;
* a plain ``--target`` keeps today's chain and today's probe, byte-identically;
* a persisted retarget makes a bare ``--resume`` (or a re-run after a re-baselined failure) a
  retarget, and ``--retarget`` naming another target refuses ``RETARGET_RESUME_MISMATCH``;
* the admitted ``(recorded, new)`` pair is returned (the executor builds the run record from
  it) and announced once.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import typer

from specify_cli.consolidation import entry_preflight, executor, preflight, preflight_retarget
from specify_cli.consolidation.state import ConsolidationState, save_state
from specify_cli.coordination.types import Refused

pytestmark = pytest.mark.fast

_MISSION_ID = "01M7M5JA00000000000000000R"
_SLUG = "m"
_PROTECTED = Refused(error_code="PROTECTED_BRANCH_REFUSED", message="'develop' is protected.", destination_ref="develop", next_step="Use another target.")
_UNWRITABLE = Refused(
    error_code=preflight_retarget.RETARGET_RECORD_UNWRITABLE,
    message="meta.json is dirty on 'develop'.",
    destination_ref="develop",
    next_step="Commit or discard it.",
)
_OLD_UNWRITABLE = Refused(
    error_code=preflight.TARGET_OVERRIDE_RECORDED_TARGET_UNWRITABLE, message="'main' cannot be written.", destination_ref="main", next_step="Drop --target."
)


def _manifest(target: str = "develop") -> Any:
    return SimpleNamespace(target_branch=target, mission_branch="kitty/mission-m", lanes=[])


class _Probes:
    """Records every verdict call and answers with the configured refusals."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, *, recorded: str = "main") -> None:
        self.status_calls: list[dict[str, Any]] = []
        self.override_calls: list[dict[str, Any]] = []
        self.status_verdict: Refused | None = None
        self.override_verdict: Refused | None = None
        monkeypatch.setattr(entry_preflight, "resolve_merge_target_branch", lambda *_a, **_k: (recorded, "meta"))
        monkeypatch.setattr(entry_preflight, "refuse_protected_status_target", self._status)
        monkeypatch.setattr(entry_preflight, "target_override_verdict", self._override)

    def _status(self, *_a: object, **kwargs: Any) -> Refused | None:
        self.status_calls.append(kwargs)
        return self.status_verdict

    def _override(self, *_a: object, **kwargs: Any) -> Refused | None:
        self.override_calls.append(kwargs)
        return self.override_verdict


def _persist_retarget(repo: Path, source: str = "main", to: str = "develop", *, committed: bool = False) -> None:
    state = ConsolidationState(mission_id=_MISSION_ID, mission_slug=_SLUG, target_branch=to, wp_order=["WP01"])
    state.retarget = {"from": source, "to": to, "actor": "op", "at": "2026-11-17T09:00:00+00:00", "reason": "r", "committed": committed}
    save_state(state, repo)


def _run(repo: Path, *, retarget: bool, target: str = "develop") -> tuple[str, str] | None:
    pair: tuple[str, str] | None = executor._refuse_protected_status_target_or_continue(repo, _SLUG, _manifest(target), _MISSION_ID, retarget=retarget)
    return pair


def _out(capsys: pytest.CaptureFixture[str]) -> str:
    return " ".join(capsys.readouterr().out.split())


def test_retarget_admitted_on_a_clean_new_target_returns_the_pair_and_announces_it_once(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    probes = _Probes(monkeypatch)

    assert _run(tmp_path, retarget=True) == ("main", "develop")

    assert probes.status_calls == [{"retarget_to": "develop"}], "the #5385 probe is re-pointed at the new target, never skipped"
    assert probes.override_calls == [{"recorded_target": "main", "effective_target": "develop", "retarget": True}]
    out = _out(capsys)
    assert out.count("Retargeting m: main -> develop (recorded with this run).") == 1


def test_retarget_record_unwritable_refuses_with_the_footer(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    probes = _Probes(monkeypatch)
    probes.override_verdict = _UNWRITABLE

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, retarget=True)

    assert excinfo.value.exit_code == 1
    out = _out(capsys)
    assert f"Error: {preflight_retarget.RETARGET_RECORD_UNWRITABLE}: meta.json is dirty on 'develop'." in out
    assert "Next step: Commit or discard it." in out
    assert "Consolidation refused before any branch moved." in out
    assert "Retargeting" not in out


def test_protected_new_target_refuses_protected_branch_refused(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    probes = _Probes(monkeypatch)
    probes.override_verdict = _PROTECTED

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, retarget=True)

    assert excinfo.value.exit_code == 1
    assert "PROTECTED_BRANCH_REFUSED: 'develop' is protected." in _out(capsys)


def test_repointed_5385_refusal_is_rendered_and_stops_before_the_override_verdict(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    probes = _Probes(monkeypatch)
    probes.status_verdict = _PROTECTED

    with pytest.raises(typer.Exit):
        _run(tmp_path, retarget=True)

    assert probes.status_calls == [{"retarget_to": "develop"}]
    assert probes.override_calls == []
    assert "PROTECTED_BRANCH_REFUSED" in _out(capsys)


def test_plain_target_keeps_todays_chain_and_probe(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    probes = _Probes(monkeypatch)
    probes.override_verdict = _OLD_UNWRITABLE

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, retarget=False)

    assert excinfo.value.exit_code == 1
    assert probes.status_calls == [{}], "a plain --target probes the recorded target exactly as before"
    assert probes.override_calls == [{"recorded_target": "main", "effective_target": "develop", "retarget": False}]
    out = _out(capsys)
    assert f"Error: {preflight.TARGET_OVERRIDE_RECORDED_TARGET_UNWRITABLE}: 'main' cannot be written." in out
    assert "Retargeting" not in out


def test_plain_target_admitted_returns_none(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    _Probes(monkeypatch)

    assert _run(tmp_path, retarget=False) is None
    assert "Retargeting" not in _out(capsys)


def test_retarget_onto_the_recorded_target_is_not_a_retarget(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    """FR-012: ``--target <recorded> --retarget`` restates the record; no retarget, today's probes."""
    probes = _Probes(monkeypatch, recorded="develop")

    assert _run(tmp_path, retarget=True) is None
    assert probes.status_calls == [{}]
    assert probes.override_calls[0]["retarget"] is False
    assert "Retargeting" not in _out(capsys)


def test_persisted_retarget_makes_a_bare_resume_a_retarget(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    """A bare ``--resume`` (or a re-run after a re-baselined failure) carries the persisted target as its override."""
    _persist_retarget(tmp_path)
    probes = _Probes(monkeypatch)

    assert _run(tmp_path, retarget=False) == ("main", "develop")
    assert probes.status_calls == [{"retarget_to": "develop"}]
    assert probes.override_calls[0]["retarget"] is True
    assert "Retargeting m: main -> develop" in _out(capsys)


def test_committed_persisted_retarget_reads_the_new_record_as_plain(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Once the record names the new target, the resume has nothing left to retarget."""
    _persist_retarget(tmp_path, committed=True)
    probes = _Probes(monkeypatch, recorded="develop")

    assert _run(tmp_path, retarget=True) is None
    assert probes.status_calls == [{}]


def test_persisted_retarget_from_another_record_does_not_retarget_a_plain_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Only a persisted retarget FROM the recorded target TO the effective one counts."""
    _persist_retarget(tmp_path, source="release", to="develop")
    probes = _Probes(monkeypatch)

    assert _run(tmp_path, retarget=False) is None
    assert probes.status_calls == [{}]


def test_retarget_resume_mismatch_refuses(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    _persist_retarget(tmp_path, to="develop")
    probes = _Probes(monkeypatch)

    with pytest.raises(typer.Exit) as excinfo:
        _run(tmp_path, retarget=True, target="release")

    assert excinfo.value.exit_code == 1
    assert probes.status_calls == [] and probes.override_calls == [], "refused before any probe"
    out = _out(capsys)
    assert f"Error: {preflight_retarget.RETARGET_RESUME_MISMATCH}:" in out
    assert "'main'" in out and "'develop'" in out and "'--target release --retarget'" in out
    assert "--target develop --retarget" in out and "spec-kitty consolidate --abort" in out
    assert "an earlier attempt may have" in out


def test_unreadable_record_keeps_todays_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from specify_cli.consolidation.state import get_state_path

    record = get_state_path(tmp_path, _MISSION_ID)
    record.parent.mkdir(parents=True)
    record.write_text("{not json", encoding="utf-8")
    probes = _Probes(monkeypatch)

    assert _run(tmp_path, retarget=False) is None
    assert probes.status_calls == [{}]


def test_unreadable_meta_judges_no_retarget(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from specify_cli.core.paths import MissionMetaReadError

    probes = _Probes(monkeypatch)

    def _raise(*_a: object, **_k: object) -> None:
        raise MissionMetaReadError(Path("kitty-specs/m/meta.json"), ValueError("Expecting value"))

    monkeypatch.setattr(entry_preflight, "resolve_merge_target_branch", _raise)

    assert _run(tmp_path, retarget=True) is None
    assert probes.status_calls == [{}]
    assert probes.override_calls == []


def test_retarget_of_a_mission_written_on_its_recorded_target_refuses(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    """C-006: a commit-to-target ``single_branch`` Mission (``mission_branch`` == the recorded target) refuses up front."""
    probes = _Probes(monkeypatch)
    manifest = SimpleNamespace(target_branch="develop", mission_branch="main", lanes=[])

    with pytest.raises(typer.Exit) as excinfo:
        executor._refuse_protected_status_target_or_continue(tmp_path, _SLUG, manifest, _MISSION_ID, retarget=True)

    assert excinfo.value.exit_code == 1
    assert probes.status_calls == [] and probes.override_calls == []
    out = _out(capsys)
    assert f"Error: {preflight_retarget.RETARGET_WRITE_BRANCH_IS_RECORDED_TARGET}:" in out
    assert "drop '--target develop --retarget'" in out
    assert "Consolidation refused before any branch moved." in out


@pytest.mark.parametrize(
    ("mission_branch", "recorded", "effective", "refused"),
    [
        ("main", "main", "develop", True),
        ("kitty/mission-m", "main", "develop", False),
        (None, "main", "develop", False),
        ("main", "main", "main", False),
    ],
)
def test_retarget_write_branch_refusal_truth_table(mission_branch: str | None, recorded: str, effective: str, refused: bool) -> None:
    verdict = preflight_retarget.retarget_write_branch_refusal(mission_branch=mission_branch, recorded_target=recorded, effective_target=effective)
    assert (verdict is not None) is refused
    if verdict is not None:
        assert verdict.error_code == preflight_retarget.RETARGET_WRITE_BRANCH_IS_RECORDED_TARGET
        assert verdict.destination_ref == effective
