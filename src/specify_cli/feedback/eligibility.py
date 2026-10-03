"""Offer eligibility: may a Feedback Survey be offered now?

:func:`decide_offer` is the single pure decision (no I/O). :func:`claim_offer`
wraps it in one check-and-mark transaction under a non-blocking machine-wide
lock, so two concurrent processes can never both be told to prompt inside the
same throttle window (NFR-005). The check does no network I/O (NFR-003).
"""

from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path

from kernel.clock import datetime, now_utc, timedelta
from kernel.locks import machine_file_lock
from specify_cli.feedback.models import OfferDecision, OfferReason, SurveyTrigger
from specify_cli.feedback.preferences import (
    SurveyPreferences,
    Unreadable,
    load_preferences,
    lock_path_for,
    preferences_path,
    save_preferences,
)

__all__ = ["THROTTLE_WINDOW", "claim_offer", "decide_offer"]

_LOG = logging.getLogger(__name__)

THROTTLE_WINDOW = timedelta(days=7)


def _none(reason: OfferReason, trigger: SurveyTrigger) -> OfferDecision:
    return OfferDecision("none", reason, trigger)


def _environment_gate(
    trigger: SurveyTrigger,
    *,
    endpoint_available: bool,
    interactive: bool,
    ci: bool,
) -> OfferDecision | None:
    """Rules 1-4 of :func:`decide_offer`, which never depend on stored preferences."""
    if not endpoint_available:
        return _none(OfferReason.NO_ENDPOINT, trigger)
    if not trigger.is_automatic:
        return OfferDecision("prompt", OfferReason.ELIGIBLE, trigger)
    if ci:
        return _none(OfferReason.CI, trigger)
    if not interactive:
        return _none(OfferReason.NON_INTERACTIVE, trigger)
    return None


def decide_offer(
    *,
    trigger: SurveyTrigger,
    prefs: SurveyPreferences | Unreadable,
    now: datetime,
    endpoint_available: bool,
    interactive: bool,
    ci: bool,
) -> OfferDecision:
    """Decide whether to offer a Feedback Survey; the first matching rule wins.

    The rule order is part of the contract (``reason`` values are stable):
    no endpoint, on-demand bypass, CI, non-interactive, unreadable
    preferences, prompts off, clock skew, throttled, eligible. ``now`` and
    ``prefs.last_shown_at`` must both be timezone-aware.
    """
    gate = _environment_gate(trigger, endpoint_available=endpoint_available, interactive=interactive, ci=ci)
    if gate is not None:
        return gate
    if isinstance(prefs, Unreadable):
        return _none(OfferReason.PREFERENCES_UNREADABLE, trigger)
    if not prefs.automatic_prompts:
        return _none(OfferReason.PROMPTS_OFF, trigger)
    last_shown_at = prefs.last_shown_at
    if last_shown_at is not None and last_shown_at > now:
        return _none(OfferReason.CLOCK_SKEW, trigger)
    if last_shown_at is not None and now - last_shown_at < THROTTLE_WINDOW:
        return _none(OfferReason.THROTTLED, trigger)
    return OfferDecision("prompt", OfferReason.ELIGIBLE, trigger)


def _decide_and_mark(
    trigger: SurveyTrigger,
    *,
    path: Path,
    now: datetime,
    endpoint_available: bool,
    interactive: bool,
    ci: bool,
) -> OfferDecision:
    """Load, decide, and record ``last_shown_at`` on a prompt. Runs inside the lock; never raises."""
    try:
        prefs = load_preferences(path)
        decision = decide_offer(
            trigger=trigger,
            prefs=prefs,
            now=now,
            endpoint_available=endpoint_available,
            interactive=interactive,
            ci=ci,
        )
        if decision.action != "prompt" or isinstance(prefs, Unreadable):
            return decision
        if not save_preferences(path, replace(prefs, last_shown_at=now)):
            return _none(OfferReason.PREFERENCES_UNREADABLE, trigger)
        return decision
    except Exception as exc:
        _LOG.debug("feedback offer claim failed: %s", exc)
        return _none(OfferReason.PREFERENCES_UNREADABLE, trigger)


def claim_offer(
    trigger: SurveyTrigger,
    *,
    endpoint_available: bool,
    interactive: bool,
    ci: bool,
    now: datetime | None = None,
    path: Path | None = None,
) -> OfferDecision:
    """Atomically decide an offer and, for an automatic prompt, mark it shown. Never raises.

    Decisions that do not depend on stored preferences (no endpoint,
    ``on_demand``, CI, non-interactive) are returned without touching the
    filesystem, so ``on_demand`` never writes ``last_shown_at``. Otherwise a
    non-blocking lock is taken around the read-decide-write sequence;
    contention (or any lock failure) yields ``none`` / ``lock_busy`` rather
    than a wait. If the mark cannot be saved, the result is ``none`` /
    ``preferences_unreadable`` so a prompt is never shown without its mark.
    """
    gate = _environment_gate(trigger, endpoint_available=endpoint_available, interactive=interactive, ci=ci)
    if gate is not None:
        return gate
    try:
        target = path if path is not None else preferences_path()
    except Exception as exc:
        _LOG.debug("feedback preferences path unresolved: %s", exc)
        return _none(OfferReason.PREFERENCES_UNREADABLE, trigger)
    moment = now if now is not None else now_utc()
    try:
        with machine_file_lock(lock_path_for(target), blocking=False):
            return _decide_and_mark(
                trigger,
                path=target,
                now=moment,
                endpoint_available=endpoint_available,
                interactive=interactive,
                ci=ci,
            )
    except Exception as exc:
        _LOG.debug("feedback offer lock unavailable: %s", exc)
        return _none(OfferReason.LOCK_BUSY, trigger)
