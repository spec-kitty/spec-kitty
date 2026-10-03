"""Unit tests for ``specify_cli.feedback.eligibility``."""

from __future__ import annotations

import multiprocessing
import time
from pathlib import Path
from typing import Any

import pytest

from kernel.clock import UTC, datetime, now_utc, timedelta
from kernel.locks import machine_file_lock
from specify_cli.feedback import eligibility as eligibility_module
from specify_cli.feedback.eligibility import THROTTLE_WINDOW, claim_offer, decide_offer
from specify_cli.feedback.models import OfferAction, OfferDecision, OfferReason, SurveyTrigger
from specify_cli.feedback.preferences import (
    PREFERENCES_FILENAME,
    SurveyPreferences,
    Unreadable,
    load_preferences,
    lock_path_for,
    save_preferences,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
AUTO = SurveyTrigger.MISSION_END
ON_DEMAND = SurveyTrigger.ON_DEMAND
DEFAULTS = SurveyPreferences()
BROKEN = Unreadable("test")


def _shown(delta: timedelta) -> SurveyPreferences:
    return SurveyPreferences(last_shown_at=NOW - delta)


# (id, trigger, prefs, endpoint_available, interactive, ci, expected action, expected reason)
DECISION_TABLE: list[tuple[str, SurveyTrigger, SurveyPreferences | Unreadable, bool, bool, bool, OfferAction, OfferReason]] = [
    ("no-endpoint-beats-everything", AUTO, DEFAULTS, False, True, False, "none", OfferReason.NO_ENDPOINT),
    ("no-endpoint-beats-on-demand", ON_DEMAND, DEFAULTS, False, True, False, "none", OfferReason.NO_ENDPOINT),
    ("on-demand-bypasses-ci", ON_DEMAND, DEFAULTS, True, True, True, "prompt", OfferReason.ELIGIBLE),
    ("on-demand-bypasses-non-interactive", ON_DEMAND, DEFAULTS, True, False, False, "prompt", OfferReason.ELIGIBLE),
    ("on-demand-bypasses-unreadable", ON_DEMAND, BROKEN, True, True, False, "prompt", OfferReason.ELIGIBLE),
    ("on-demand-bypasses-prompts-off", ON_DEMAND, SurveyPreferences(automatic_prompts=False), True, True, False, "prompt", OfferReason.ELIGIBLE),
    ("on-demand-bypasses-throttle", ON_DEMAND, _shown(timedelta(hours=1)), True, True, False, "prompt", OfferReason.ELIGIBLE),
    ("ci-beats-non-interactive", AUTO, DEFAULTS, True, False, True, "none", OfferReason.CI),
    ("non-interactive-beats-unreadable", AUTO, BROKEN, True, False, False, "none", OfferReason.NON_INTERACTIVE),
    ("unreadable", AUTO, BROKEN, True, True, False, "none", OfferReason.PREFERENCES_UNREADABLE),
    (
        "prompts-off-beats-clock-skew",
        AUTO,
        SurveyPreferences(automatic_prompts=False, last_shown_at=NOW + timedelta(days=1)),
        True,
        True,
        False,
        "none",
        OfferReason.PROMPTS_OFF,
    ),
    ("clock-skew", AUTO, _shown(-timedelta(seconds=1)), True, True, False, "none", OfferReason.CLOCK_SKEW),
    ("throttled-just-inside-window", AUTO, _shown(THROTTLE_WINDOW - timedelta(seconds=1)), True, True, False, "none", OfferReason.THROTTLED),
    ("throttled-same-instant", AUTO, _shown(timedelta(0)), True, True, False, "none", OfferReason.THROTTLED),
    ("eligible-at-exactly-seven-days", AUTO, _shown(THROTTLE_WINDOW), True, True, False, "prompt", OfferReason.ELIGIBLE),
    ("eligible-after-seven-days", AUTO, _shown(timedelta(days=30)), True, True, False, "prompt", OfferReason.ELIGIBLE),
    ("eligible-never-shown", AUTO, DEFAULTS, True, True, False, "prompt", OfferReason.ELIGIBLE),
]


@pytest.mark.parametrize(
    ("trigger", "prefs", "endpoint_available", "interactive", "ci", "action", "reason"),
    [row[1:] for row in DECISION_TABLE],
    ids=[row[0] for row in DECISION_TABLE],
)
def test_decide_offer_rule_order(
    trigger: SurveyTrigger,
    prefs: SurveyPreferences | Unreadable,
    endpoint_available: bool,
    interactive: bool,
    ci: bool,
    action: OfferAction,
    reason: OfferReason,
) -> None:
    decision = decide_offer(
        trigger=trigger,
        prefs=prefs,
        now=NOW,
        endpoint_available=endpoint_available,
        interactive=interactive,
        ci=ci,
    )

    assert decision == OfferDecision(action, reason, trigger)


def test_throttle_window_is_seven_days() -> None:
    assert timedelta(days=7) == THROTTLE_WINDOW


# --- claim_offer -------------------------------------------------------------


def _claim(path: Path, *, trigger: SurveyTrigger = AUTO, now: datetime = NOW, **overrides: bool) -> OfferDecision:
    flags = {"endpoint_available": True, "interactive": True, "ci": False, **overrides}
    return claim_offer(trigger, now=now, path=path, **flags)


@pytest.fixture
def prefs_file(feedback_config_dir: Path) -> Path:
    return feedback_config_dir / PREFERENCES_FILENAME


def test_claim_writes_last_shown_at_on_prompt_and_keeps_other_fields(prefs_file: Path) -> None:
    assert save_preferences(prefs_file, SurveyPreferences(endpoint_override="https://example.invalid/fb")) is True

    assert _claim(prefs_file).action == "prompt"

    assert load_preferences(prefs_file) == SurveyPreferences(last_shown_at=NOW, endpoint_override="https://example.invalid/fb")


def test_claim_does_not_write_on_none(prefs_file: Path) -> None:
    earlier = NOW - timedelta(days=1)
    assert save_preferences(prefs_file, SurveyPreferences(last_shown_at=earlier)) is True

    assert _claim(prefs_file).reason is OfferReason.THROTTLED

    assert load_preferences(prefs_file) == SurveyPreferences(last_shown_at=earlier)


@pytest.mark.parametrize(
    ("endpoint_available", "interactive", "ci", "reason"),
    [
        (False, True, False, OfferReason.NO_ENDPOINT),
        (True, True, True, OfferReason.CI),
        (True, False, False, OfferReason.NON_INTERACTIVE),
    ],
)
def test_environment_refusals_never_touch_the_config_dir(
    feedback_config_dir: Path,
    endpoint_available: bool,
    interactive: bool,
    ci: bool,
    reason: OfferReason,
) -> None:
    decision = _claim(feedback_config_dir / PREFERENCES_FILENAME, endpoint_available=endpoint_available, interactive=interactive, ci=ci)

    assert decision.reason is reason
    assert not feedback_config_dir.exists()


def test_on_demand_never_writes(prefs_file: Path) -> None:
    decision = _claim(prefs_file, trigger=ON_DEMAND)

    assert decision == OfferDecision("prompt", OfferReason.ELIGIBLE, ON_DEMAND)
    assert not prefs_file.parent.exists()


def test_claim_with_unreadable_preferences_offers_nothing_and_keeps_the_file(prefs_file: Path) -> None:
    prefs_file.parent.mkdir(parents=True)
    prefs_file.write_text("{corrupt", encoding="utf-8")
    prefs_file.chmod(0o600)

    assert _claim(prefs_file).reason is OfferReason.PREFERENCES_UNREADABLE
    assert prefs_file.read_text(encoding="utf-8") == "{corrupt"


def test_claim_returns_unreadable_when_the_mark_cannot_be_saved(prefs_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(eligibility_module, "save_preferences", lambda _path, _prefs: False)

    assert _claim(prefs_file) == OfferDecision("none", OfferReason.PREFERENCES_UNREADABLE, AUTO)


def test_claim_contains_unexpected_errors_inside_the_lock(prefs_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(_path: Path) -> SurveyPreferences:
        raise RuntimeError("unexpected")

    monkeypatch.setattr(eligibility_module, "load_preferences", _boom)

    assert _claim(prefs_file) == OfferDecision("none", OfferReason.PREFERENCES_UNREADABLE, AUTO)


def test_claim_contains_an_unresolvable_preferences_path(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom() -> Path:
        raise RuntimeError("no home directory")

    monkeypatch.setattr(eligibility_module, "preferences_path", _boom)

    decision = claim_offer(AUTO, endpoint_available=True, interactive=True, ci=False, now=NOW)

    assert decision == OfferDecision("none", OfferReason.PREFERENCES_UNREADABLE, AUTO)


def test_claim_defaults_to_the_resolved_path_and_the_real_clock(prefs_file: Path) -> None:
    before = now_utc()

    decision = claim_offer(AUTO, endpoint_available=True, interactive=True, ci=False)

    loaded = load_preferences(prefs_file)
    assert decision.action == "prompt"
    assert isinstance(loaded, SurveyPreferences)
    assert loaded.last_shown_at is not None
    assert before <= loaded.last_shown_at <= now_utc()


def test_lock_contention_yields_lock_busy_without_writing(prefs_file: Path) -> None:
    with machine_file_lock(lock_path_for(prefs_file), blocking=False):
        busy = _claim(prefs_file)

    assert busy == OfferDecision("none", OfferReason.LOCK_BUSY, AUTO)
    assert not prefs_file.exists()

    # Positive control on the same fixture: once released, the claim succeeds.
    assert _claim(prefs_file).action == "prompt"


def test_any_lock_failure_yields_lock_busy(prefs_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _broken_lock(*_args: object, **_kwargs: object) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(eligibility_module, "machine_file_lock", _broken_lock)

    assert _claim(prefs_file) == OfferDecision("none", OfferReason.LOCK_BUSY, AUTO)


@pytest.mark.timing
def test_eligibility_check_is_fast(prefs_file: Path) -> None:
    assert save_preferences(prefs_file, SurveyPreferences(last_shown_at=NOW - timedelta(days=1))) is True

    started = time.perf_counter()
    decision = _claim(prefs_file)
    elapsed = time.perf_counter() - started

    assert decision.reason is OfferReason.THROTTLED
    assert elapsed < 0.1


# --- cross-process race (NFR-005) --------------------------------------------

_RACE_WORKERS = 4
_RACE_TIMEOUT_S = 60


def _race_worker(path: str, barrier: Any, results: Any) -> None:
    barrier.wait(timeout=_RACE_TIMEOUT_S)
    decision = claim_offer(AUTO, endpoint_available=True, interactive=True, ci=False, now=NOW, path=Path(path))
    results.put((decision.action, decision.reason.value))


@pytest.mark.stress
def test_concurrent_processes_get_exactly_one_prompt(prefs_file: Path) -> None:
    ctx = multiprocessing.get_context("spawn")
    barrier = ctx.Barrier(_RACE_WORKERS)
    results = ctx.Queue()
    workers = [ctx.Process(target=_race_worker, args=(str(prefs_file), barrier, results)) for _ in range(_RACE_WORKERS)]
    for worker in workers:
        worker.start()
    outcomes = [results.get(timeout=_RACE_TIMEOUT_S) for _ in workers]
    for worker in workers:
        worker.join(timeout=_RACE_TIMEOUT_S)

    assert [w.exitcode for w in workers] == [0] * _RACE_WORKERS
    assert [action for action, _ in outcomes].count("prompt") == 1
    assert {reason for action, reason in outcomes if action == "none"} <= {OfferReason.LOCK_BUSY.value, OfferReason.THROTTLED.value}
    assert load_preferences(prefs_file) == SurveyPreferences(last_shown_at=NOW)
