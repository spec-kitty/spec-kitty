"""Test matrix for upgrade-readiness UX (WS3, issue Priivacy-ai/spec-kitty#1092).

Covers the pure preference, cadence and choice logic that ``spec-kitty
upgrade`` consumes (the prompt orchestrator was removed with the hosted
surfaces, #6164):

- Each of the four choices (Upgrade now, Always, Not now, Never).
- Snooze cadence per remote version (24h -> 48h -> 7d; new version resets).
- Backward read-compat for NagCacheRecord.
"""

from __future__ import annotations

from kernel.clock import UTC, datetime, timedelta
from typing import Any

import pytest

from specify_cli.compat._detect.install_method import (
    InstallMethod,
    is_safe_for_auto_upgrade,
)
from specify_cli.readiness.upgrade_ux import (
    ENV_UPGRADE_AUTO,
    ENV_UPGRADE_DISABLED,
    ENV_UPGRADE_NEVER_ASK,
    EffectivePreference,
    UpgradeChoice,
    advance_snooze,
    apply_choice,
    is_currently_snoozed,
    needs_reset,
    resolve_effective_preference,
)


pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# Pure-function unit tests
# ---------------------------------------------------------------------------


class TestAdvanceSnooze:
    """Cadence ladder: None → 24h → 48h → 7d → 7d (ceiling)."""

    def test_none_to_24h(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=UTC)
        step, until = advance_snooze(None, now=now)
        assert step == "24h"
        assert until == now + timedelta(hours=24)

    def test_24h_to_48h(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=UTC)
        step, until = advance_snooze("24h", now=now)
        assert step == "48h"
        assert until == now + timedelta(hours=48)

    def test_48h_to_7d(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=UTC)
        step, until = advance_snooze("48h", now=now)
        assert step == "7d"
        assert until == now + timedelta(days=7)

    def test_7d_stays_at_ceiling(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=UTC)
        step, until = advance_snooze("7d", now=now)
        assert step == "7d"
        assert until == now + timedelta(days=7)


class TestNeedsReset:
    def test_new_remote_resets(self) -> None:
        assert needs_reset(record_remote_version="1.0", current_latest="2.0") is True

    def test_same_remote_no_reset(self) -> None:
        assert needs_reset(record_remote_version="1.0", current_latest="1.0") is False

    def test_first_time_resets(self) -> None:
        # None remote_version_seen means "no prior cycle" — treat as a reset
        # so the new latest gets anchored.
        assert needs_reset(record_remote_version=None, current_latest="2.0") is True

    def test_no_remote_known_no_reset(self) -> None:
        # When the planner returns no latest, don't churn cadence.
        assert needs_reset(record_remote_version="1.0", current_latest=None) is False


class TestIsCurrentlySnoozed:
    def test_no_snooze_until(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=UTC)
        assert is_currently_snoozed(snoozed_until=None, now=now) is False

    def test_snooze_active(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=UTC)
        future = now + timedelta(hours=1)
        assert is_currently_snoozed(snoozed_until=future, now=now) is True

    def test_snooze_expired(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=UTC)
        past = now - timedelta(hours=1)
        assert is_currently_snoozed(snoozed_until=past, now=now) is False


class TestResolveEffectivePreference:
    def test_no_env_no_persisted(self) -> None:
        pref = resolve_effective_preference(
            persisted_never_ask=False, persisted_always_upgrade=False, env={}
        )
        assert pref == EffectivePreference(False, False, False)

    def test_persisted_never_ask(self) -> None:
        pref = resolve_effective_preference(
            persisted_never_ask=True, persisted_always_upgrade=False, env={}
        )
        assert pref.never_ask is True

    def test_env_overrides_to_never_ask(self) -> None:
        pref = resolve_effective_preference(
            persisted_never_ask=False,
            persisted_always_upgrade=False,
            env={ENV_UPGRADE_NEVER_ASK: "1"},
        )
        assert pref.never_ask is True

    def test_env_always_upgrade(self) -> None:
        pref = resolve_effective_preference(
            persisted_never_ask=False,
            persisted_always_upgrade=False,
            env={ENV_UPGRADE_AUTO: "true"},
        )
        assert pref.always_upgrade is True

    def test_disabled_kill_switch(self) -> None:
        pref = resolve_effective_preference(
            persisted_never_ask=False,
            persisted_always_upgrade=False,
            env={ENV_UPGRADE_DISABLED: "yes"},
        )
        assert pref.disabled is True

    def test_falsy_values_do_not_elevate(self) -> None:
        pref = resolve_effective_preference(
            persisted_never_ask=False,
            persisted_always_upgrade=False,
            env={
                ENV_UPGRADE_DISABLED: "0",
                ENV_UPGRADE_AUTO: "false",
                ENV_UPGRADE_NEVER_ASK: "no",
            },
        )
        assert pref == EffectivePreference(False, False, False)


class TestIsSafeForAutoUpgrade:
    """Acceptance criterion 5 — installer whitelist."""

    @pytest.mark.parametrize(
        "method",
        [
            InstallMethod.PIPX,
            InstallMethod.UV_TOOL,
            InstallMethod.BREW,
            InstallMethod.PIP_USER,
            InstallMethod.PIP_SYSTEM,
        ],
    )
    def test_safe_methods(self, method: InstallMethod) -> None:
        assert is_safe_for_auto_upgrade(method) is True

    @pytest.mark.parametrize(
        "method",
        [
            InstallMethod.SOURCE,
            InstallMethod.SYSTEM_PACKAGE,
            InstallMethod.UNKNOWN,
        ],
    )
    def test_unsafe_methods(self, method: InstallMethod) -> None:
        assert is_safe_for_auto_upgrade(method) is False


# ---------------------------------------------------------------------------
# apply_choice — four-choice mutation tests (acceptance criterion 3 + 8)
# ---------------------------------------------------------------------------


def _base_kwargs(now: datetime) -> dict[str, Any]:
    return {
        "cli_version_key": "1.0",
        "latest_version": "2.0",
        "latest_source": "pypi",
        "fetched_at": now,
        "last_shown_at": now,
        "remote_version_seen": None,
        "snooze_step": None,
        "snoozed_until": None,
        "always_upgrade": False,
        "never_ask": False,
    }


class TestApplyChoice:
    def test_upgrade_now_anchors_and_clears_snooze(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=UTC)
        kwargs = _base_kwargs(now)
        kwargs["snooze_step"] = "48h"
        kwargs["snoozed_until"] = now + timedelta(hours=48)
        updated = apply_choice(
            kwargs, choice=UpgradeChoice.UPGRADE_NOW, current_latest="2.0", now=now
        )
        assert updated["remote_version_seen"] == "2.0"
        assert updated["snooze_step"] is None
        assert updated["snoozed_until"] is None

    def test_always_sets_flag_and_clears(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=UTC)
        kwargs = _base_kwargs(now)
        updated = apply_choice(
            kwargs, choice=UpgradeChoice.ALWAYS, current_latest="2.0", now=now
        )
        assert updated["always_upgrade"] is True
        assert updated["snooze_step"] is None
        assert updated["snoozed_until"] is None

    def test_not_now_advances_cadence_first_time(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=UTC)
        kwargs = _base_kwargs(now)
        updated = apply_choice(
            kwargs, choice=UpgradeChoice.NOT_NOW, current_latest="2.0", now=now
        )
        assert updated["snooze_step"] == "24h"
        assert updated["snoozed_until"] == now + timedelta(hours=24)

    def test_not_now_cadence_progression(self) -> None:
        """Acceptance criterion 8: snooze cadence per remote version."""
        now = datetime(2026, 1, 1, tzinfo=UTC)
        kwargs = _base_kwargs(now)
        # Step 1: None → 24h
        kwargs = apply_choice(
            kwargs, choice=UpgradeChoice.NOT_NOW, current_latest="2.0", now=now
        )
        assert kwargs["snooze_step"] == "24h"
        # Step 2: 24h → 48h
        kwargs = apply_choice(
            kwargs, choice=UpgradeChoice.NOT_NOW, current_latest="2.0", now=now
        )
        assert kwargs["snooze_step"] == "48h"
        # Step 3: 48h → 7d
        kwargs = apply_choice(
            kwargs, choice=UpgradeChoice.NOT_NOW, current_latest="2.0", now=now
        )
        assert kwargs["snooze_step"] == "7d"
        # Step 4: 7d stays at 7d (ceiling)
        kwargs = apply_choice(
            kwargs, choice=UpgradeChoice.NOT_NOW, current_latest="2.0", now=now
        )
        assert kwargs["snooze_step"] == "7d"

    def test_never_ask_sets_flag(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=UTC)
        kwargs = _base_kwargs(now)
        updated = apply_choice(
            kwargs, choice=UpgradeChoice.NEVER_ASK, current_latest="2.0", now=now
        )
        assert updated["never_ask"] is True


# ---------------------------------------------------------------------------
# Backward read-compat for NagCacheRecord (acceptance criterion 1)
# ---------------------------------------------------------------------------


class TestNagCacheRecordBackwardCompat:
    def test_legacy_record_loads_with_defaults(self) -> None:
        from specify_cli.compat.cache import NagCacheRecord

        legacy = {
            "cli_version_key": "1.0",
            "latest_version": "2.0",
            "latest_source": "pypi",
            "fetched_at": "2026-01-01T00:00:00+00:00",
            "last_shown_at": None,
        }
        rec = NagCacheRecord.from_dict(legacy)
        assert rec.remote_version_seen is None
        assert rec.snooze_step is None
        assert rec.snoozed_until is None
        assert rec.always_upgrade is False
        assert rec.never_ask is False

    def test_round_trip_all_new_fields(self) -> None:
        from specify_cli.compat.cache import NagCacheRecord

        now = datetime(2026, 1, 1, tzinfo=UTC)
        rec = NagCacheRecord(
            cli_version_key="1.0",
            latest_version="2.0",
            latest_source="pypi",
            fetched_at=now,
            last_shown_at=now,
            remote_version_seen="2.0",
            snooze_step="48h",
            snoozed_until=now + timedelta(hours=48),
            always_upgrade=True,
            never_ask=False,
        )
        round_tripped = NagCacheRecord.from_dict(rec.to_dict())
        assert round_tripped == rec

    def test_invalid_snooze_step_rejected(self) -> None:
        from specify_cli.compat.cache import NagCacheRecord

        bad = {
            "cli_version_key": "1.0",
            "latest_version": "2.0",
            "latest_source": "pypi",
            "fetched_at": "2026-01-01T00:00:00+00:00",
            "last_shown_at": None,
            "snooze_step": "1h",  # not in the cadence
        }
        with pytest.raises(ValueError, match="snooze_step"):
            NagCacheRecord.from_dict(bad)
