"""Test matrix for upgrade-readiness UX (WS3, issue Priivacy-ai/spec-kitty#1092).

Covers acceptance criterion 8 from spec.md:

- Each of the four choices (Upgrade now, Always, Not now, Never).
- Snooze cadence per remote version (24h → 48h → 7d; new version resets).
- Auto-upgrade refuses to run in each suppression context.
- Unknown installer → guidance only, no mutation.
- Hosted-off + no legacy nag → no upgrade output (covered by existing
  ``test_coordinator_caching.py::test_B_hosted_disabled_cached_after_first_call``
  and the ``test_coordinator_nag_passthrough.py`` matrix).
- Hosted-off + legacy nag triggers → legacy behavior preserved
  (covered by existing ``test_coordinator_nag_passthrough.py``).
- "Never ask again" persists.
- Backward read-compat for NagCacheRecord (covered by
  ``tests/specify_cli/compat/test_cache.py``; mirrored here for the new fields).
"""

from __future__ import annotations

import sys
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
    run_upgrade_ux,
)


pytestmark = [pytest.mark.unit, pytest.mark.fast]


@pytest.fixture(autouse=True)
def _neutralize_ambient_ci_detection(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the run_upgrade_ux tests hermetic w.r.t. ambient CI detection.

    ``run_upgrade_ux`` builds ``Invocation.from_argv()``, whose
    ``suppresses_nag()`` consults ``is_ci_env()`` — which reads
    ``os.environ["CI"]`` **directly**, bypassing the ``env=`` argument these
    tests inject. On GitHub Actions ``CI=true`` is always set, so the nag is
    (correctly) suppressed and the prompt never fires, yielding a
    ``choice=None`` / ``ran=False`` outcome that has nothing to do with the
    behaviour under test. Clearing the CI markers here lets each test exercise
    the interactive path it intends, identically on a developer laptop and on
    CI. The product's CI-suppression behaviour is covered by the dedicated
    suppression tests that set the env explicitly.
    """
    for var in ("CI", "GITHUB_ACTIONS", "CONTINUOUS_INTEGRATION"):
        monkeypatch.delenv(var, raising=False)


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


# ---------------------------------------------------------------------------
# Suppression matrix for the orchestrator (acceptance criterion 6 + 8)
# ---------------------------------------------------------------------------


class TestRunUpgradeUxSuppressed:
    """When `suppressed=True`, the function MUST short-circuit without
    prompting, invoking subprocess, or writing the cache."""

    def test_suppressed_short_circuits(self) -> None:
        def _fail_prompt() -> UpgradeChoice:
            pytest.fail("prompt invoked while suppressed")

        def _fail_runner() -> int:
            pytest.fail("subprocess invoked while suppressed")

        outcome = run_upgrade_ux(
            None,
            suppressed=True,
            prompt=_fail_prompt,
            upgrade_runner=_fail_runner,
        )
        assert outcome.ran is False
        assert outcome.prompted is False
        assert outcome.auto_upgrade_attempted is False
        assert outcome.choice is None


class TestRunUpgradeUxKillSwitch:
    def test_disabled_env_short_circuits(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _fail_prompt() -> UpgradeChoice:
            pytest.fail("prompt invoked while ENV_UPGRADE_DISABLED set")

        outcome = run_upgrade_ux(
            None,
            suppressed=False,
            env={ENV_UPGRADE_DISABLED: "1"},
            prompt=_fail_prompt,
            upgrade_runner=lambda: 0,
            installer_detector=lambda: InstallMethod.PIPX,
        )
        assert outcome.ran is False
        assert outcome.prompted is False


# ---------------------------------------------------------------------------
# Hosted-on coordinator integration
# ---------------------------------------------------------------------------


def _make_ctx() -> Any:
    import typer

    app = typer.Typer()

    @app.callback()
    def _root_cb(ctx: typer.Context) -> None:  # pragma: no cover
        pass

    cmd = typer.main.get_command(app)
    ctx = typer.Context(cmd)
    ctx.obj = None
    return ctx


def _make_planner_result(decision_token: str, latest: str = "2.0") -> Any:
    """Build a stub Plan-like object that matches the surface upgrade_ux reads."""
    from specify_cli.compat import Decision

    class _CLIStatus:
        installed_version = "1.0"
        latest_version = latest
        latest_source = "pypi"

    class _Result:
        decision = Decision[decision_token]
        cli_status = _CLIStatus()
        rendered_human = "stub"

    return _Result()


def _patch_planner(monkeypatch: pytest.MonkeyPatch, decision_token: str, latest: str = "2.0") -> None:
    import specify_cli.compat as compat_mod

    def _fake_plan(inv: Any) -> Any:
        return _make_planner_result(decision_token, latest=latest)

    monkeypatch.setattr(compat_mod, "plan", _fake_plan)


def _patch_cache_noop(monkeypatch: pytest.MonkeyPatch, existing: Any = None) -> dict[str, Any]:
    """Patch NagCache.default() to return an in-memory recorder.

    Returns a dict whose ``writes`` entry accumulates each NagCacheRecord
    instance written so tests can assert against the mutation.
    """
    import specify_cli.compat as compat_mod

    state: dict[str, Any] = {"writes": [], "existing": existing}

    class _MemCache:
        @staticmethod
        def default() -> _MemCache:
            return _MemCache()

        def read(self) -> Any:
            return state["existing"]

        def write(self, record: Any) -> None:
            state["writes"].append(record)

    monkeypatch.setattr(compat_mod, "NagCache", _MemCache)
    return state


class TestRunUpgradeUxNotAllowWithNag:
    """When planner returns ALLOW (not ALLOW_WITH_NAG), UX is a no-op."""

    def test_no_prompt_when_decision_is_allow(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "argv", ["spec-kitty", "status"])
        monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
        _patch_planner(monkeypatch, "ALLOW")

        def _fail_prompt() -> UpgradeChoice:
            pytest.fail("prompt should not fire when decision != ALLOW_WITH_NAG")

        outcome = run_upgrade_ux(
            None,
            suppressed=False,
            env={},
            prompt=_fail_prompt,
            upgrade_runner=lambda: 0,
            installer_detector=lambda: InstallMethod.PIPX,
        )
        assert outcome.ran is False


class TestRunUpgradeUxFourChoices:
    """Acceptance criterion 3 + 8 — each of the four choices wires through."""

    def _build_setup(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> dict[str, Any]:
        monkeypatch.setattr(sys, "argv", ["spec-kitty", "status"])
        monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
        _patch_planner(monkeypatch, "ALLOW_WITH_NAG", latest="2.0")
        return _patch_cache_noop(monkeypatch)

    def test_choice_upgrade_now_safe_installer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cache_state = self._build_setup(monkeypatch)
        runs: list[int] = []

        def _runner() -> int:
            runs.append(1)
            return 0

        outcome = run_upgrade_ux(
            None,
            suppressed=False,
            env={},
            prompt=lambda: UpgradeChoice.UPGRADE_NOW,
            upgrade_runner=_runner,
            installer_detector=lambda: InstallMethod.PIPX,
        )
        assert outcome.choice == UpgradeChoice.UPGRADE_NOW
        assert outcome.auto_upgrade_attempted is True
        assert outcome.auto_upgrade_exit_code == 0
        assert outcome.guidance_only is False
        assert runs == [1]
        # Cache mutated.
        assert len(cache_state["writes"]) == 1
        written = cache_state["writes"][0]
        assert written.remote_version_seen == "2.0"
        assert written.snooze_step is None

    def test_choice_always_persists(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cache_state = self._build_setup(monkeypatch)
        outcome = run_upgrade_ux(
            None,
            suppressed=False,
            env={},
            prompt=lambda: UpgradeChoice.ALWAYS,
            upgrade_runner=lambda: 0,
            installer_detector=lambda: InstallMethod.PIPX,
        )
        assert outcome.choice == UpgradeChoice.ALWAYS
        written = cache_state["writes"][0]
        assert written.always_upgrade is True

    def test_choice_not_now_advances_cadence(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cache_state = self._build_setup(monkeypatch)
        outcome = run_upgrade_ux(
            None,
            suppressed=False,
            env={},
            prompt=lambda: UpgradeChoice.NOT_NOW,
            upgrade_runner=lambda: pytest.fail("runner should not fire for not-now"),
            installer_detector=lambda: InstallMethod.PIPX,
        )
        assert outcome.choice == UpgradeChoice.NOT_NOW
        assert outcome.auto_upgrade_attempted is False
        written = cache_state["writes"][0]
        assert written.snooze_step == "24h"

    def test_choice_never_ask_persists(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cache_state = self._build_setup(monkeypatch)
        outcome = run_upgrade_ux(
            None,
            suppressed=False,
            env={},
            prompt=lambda: UpgradeChoice.NEVER_ASK,
            upgrade_runner=lambda: pytest.fail("runner should not fire for never-ask"),
            installer_detector=lambda: InstallMethod.PIPX,
        )
        assert outcome.choice == UpgradeChoice.NEVER_ASK
        written = cache_state["writes"][0]
        assert written.never_ask is True


class TestRunUpgradeUxUnknownInstaller:
    """Acceptance criterion 5 + 8 — UNKNOWN installer never auto-upgrades."""

    def test_upgrade_now_unknown_installer_is_guidance_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "argv", ["spec-kitty", "status"])
        monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
        _patch_planner(monkeypatch, "ALLOW_WITH_NAG")
        _patch_cache_noop(monkeypatch)

        def _runner() -> int:
            pytest.fail("subprocess must not fire for UNKNOWN installer")

        outcome = run_upgrade_ux(
            None,
            suppressed=False,
            env={},
            prompt=lambda: UpgradeChoice.UPGRADE_NOW,
            upgrade_runner=_runner,
            installer_detector=lambda: InstallMethod.UNKNOWN,
        )
        assert outcome.guidance_only is True
        assert outcome.auto_upgrade_attempted is False

    def test_always_unknown_installer_is_guidance_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "argv", ["spec-kitty", "status"])
        monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
        _patch_planner(monkeypatch, "ALLOW_WITH_NAG")
        _patch_cache_noop(monkeypatch)

        outcome = run_upgrade_ux(
            None,
            suppressed=False,
            env={ENV_UPGRADE_AUTO: "1"},
            prompt=lambda: pytest.fail("prompt should not fire on always-upgrade path"),
            upgrade_runner=lambda: pytest.fail("subprocess must not fire for SOURCE installer"),
            installer_detector=lambda: InstallMethod.SOURCE,
        )
        assert outcome.guidance_only is True
        assert outcome.auto_upgrade_attempted is False


class TestRunUpgradeUxNeverAskPersists:
    """Acceptance criterion 8 — Never ask again persists across invocations."""

    def test_persisted_never_ask_suppresses_prompt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from specify_cli.compat.cache import NagCacheRecord

        monkeypatch.setattr(sys, "argv", ["spec-kitty", "status"])
        monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
        _patch_planner(monkeypatch, "ALLOW_WITH_NAG", latest="2.0")

        existing = NagCacheRecord(
            cli_version_key="1.0",
            latest_version="2.0",
            latest_source="pypi",
            fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
            last_shown_at=None,
            remote_version_seen="2.0",
            never_ask=True,
        )
        _patch_cache_noop(monkeypatch, existing=existing)

        outcome = run_upgrade_ux(
            None,
            suppressed=False,
            env={},
            prompt=lambda: pytest.fail("prompt must not fire when never_ask persisted"),
            upgrade_runner=lambda: 0,
            installer_detector=lambda: InstallMethod.PIPX,
        )
        assert outcome.ran is True
        assert outcome.prompted is False
        assert outcome.choice is None


class TestRunUpgradeUxNewVersionResetsCadence:
    """Acceptance criterion 1 + 8 — new remote version resets cadence + never_ask."""

    def test_new_version_resets_never_ask_and_snooze(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from specify_cli.compat.cache import NagCacheRecord

        monkeypatch.setattr(sys, "argv", ["spec-kitty", "status"])
        monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
        _patch_planner(monkeypatch, "ALLOW_WITH_NAG", latest="3.0")

        existing = NagCacheRecord(
            cli_version_key="1.0",
            latest_version="2.0",
            latest_source="pypi",
            fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
            last_shown_at=datetime(2026, 1, 1, tzinfo=UTC),
            remote_version_seen="2.0",  # old anchor
            snooze_step="7d",
            snoozed_until=datetime(2099, 1, 1, tzinfo=UTC),
            never_ask=True,  # said "never" about 2.0
        )
        cache_state = _patch_cache_noop(monkeypatch, existing=existing)

        captured: dict[str, Any] = {}

        def _prompt() -> UpgradeChoice:
            captured["prompted"] = True
            return UpgradeChoice.NOT_NOW

        outcome = run_upgrade_ux(
            None,
            suppressed=False,
            env={},
            prompt=_prompt,
            upgrade_runner=lambda: 0,
            installer_detector=lambda: InstallMethod.PIPX,
        )
        # A new remote_version means the user gets re-prompted.
        assert captured.get("prompted") is True
        assert outcome.prompted is True
        # Cache is re-anchored.
        written = cache_state["writes"][0]
        assert written.remote_version_seen == "3.0"
        assert written.never_ask is False  # reset
        assert written.snooze_step == "24h"  # cadence restarted from None → 24h


class TestRunUpgradeUxAlwaysSafe:
    """Acceptance criterion 3 + 5 — always_upgrade + safe installer auto-runs."""

    def test_always_upgrade_safe_installer_subprocess_fires(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "argv", ["spec-kitty", "status"])
        monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
        _patch_planner(monkeypatch, "ALLOW_WITH_NAG", latest="2.0")
        _patch_cache_noop(monkeypatch)

        runs: list[int] = []

        def _runner() -> int:
            runs.append(1)
            return 0

        outcome = run_upgrade_ux(
            None,
            suppressed=False,
            env={ENV_UPGRADE_AUTO: "1"},
            prompt=lambda: pytest.fail("prompt must not fire on always-upgrade"),
            upgrade_runner=_runner,
            installer_detector=lambda: InstallMethod.PIPX,
        )
        assert runs == [1]
        assert outcome.auto_upgrade_attempted is True
        assert outcome.prompted is False

    def test_uv_tool_auto_upgrade_reinstalls_target_version(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(sys, "argv", ["spec-kitty", "status"])
        monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
        _patch_planner(monkeypatch, "ALLOW_WITH_NAG", latest="2.0")
        _patch_cache_noop(monkeypatch)

        calls: list[list[str]] = []

        class _Completed:
            returncode = 0

        def _run(argv: list[str], **_: object) -> _Completed:
            calls.append(argv)
            return _Completed()

        monkeypatch.setattr("specify_cli.readiness.upgrade_ux.subprocess.run", _run)

        outcome = run_upgrade_ux(
            None,
            suppressed=False,
            env={ENV_UPGRADE_AUTO: "1"},
            prompt=lambda: pytest.fail("prompt must not fire on always-upgrade"),
            installer_detector=lambda: InstallMethod.UV_TOOL,
        )
        assert calls == [["uv", "tool", "install", "--force", "spec-kitty-cli==2.0"]]
        assert outcome.auto_upgrade_attempted is True
        assert outcome.auto_upgrade_exit_code == 0

    def test_uv_tool_auto_upgrade_threads_receipt_python_and_tool_dir_to_subprocess(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """#2316: the receipt ``--python`` pin and a custom ``UV_TOOL_DIR`` must
        reach the ``uv tool install`` subprocess end-to-end.

        The argv/env assembly moved out of ``upgrade_ux`` into
        ``compat.remediation`` during the god-module decomposition; #2316's two
        original tests were pinned to the retired inline seam (deleted in
        177e062694) and their premise — that the behaviour was lost — is false
        against current code. This is the missing end-to-end pin that proves the
        ``run_upgrade_ux -> plan_remediation -> _default_upgrade_runner ->
        subprocess.run(env=...)`` chain still delivers both, so a future
        regression that drops the interpreter pin or the tool dir is caught.
        """
        from dataclasses import replace
        from pathlib import Path

        from specify_cli.compat._detect.runtime import detect_runtime

        monkeypatch.setattr(sys, "argv", ["spec-kitty", "status"])
        monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
        _patch_planner(monkeypatch, "ALLOW_WITH_NAG", latest="2.0")
        _patch_cache_noop(monkeypatch)

        # A uv-tool install whose receipt pins python 3.13 and a non-default
        # tools dir. ``_run_auto_upgrade_if_safe`` overrides only install_method;
        # the receipt-derived fields must survive into the argv and env.
        fake_runtime = replace(
            detect_runtime(),
            tool_dir=Path("/opt/uv"),
            is_default_tool_dir=False,
            python="3.13",
        )
        monkeypatch.setattr(
            "specify_cli.compat._detect.runtime.detect_runtime",
            lambda: fake_runtime,
        )

        calls: list[tuple[list[str], object]] = []

        class _Completed:
            returncode = 0

        def _run(argv: list[str], **kwargs: object) -> _Completed:
            calls.append((argv, kwargs.get("env")))
            return _Completed()

        monkeypatch.setattr("specify_cli.readiness.upgrade_ux.subprocess.run", _run)

        outcome = run_upgrade_ux(
            None,
            suppressed=False,
            env={ENV_UPGRADE_AUTO: "1"},
            prompt=lambda: pytest.fail("prompt must not fire on always-upgrade"),
            installer_detector=lambda: InstallMethod.UV_TOOL,
        )

        assert calls, "the uv-tool auto-upgrade subprocess must fire"
        argv, env = calls[0]
        assert argv == [
            "uv", "tool", "install", "--force",
            "--python", "3.13",
            "spec-kitty-cli==2.0",
        ], "receipt --python pin must be threaded into the install argv"
        assert env is not None, "UV_TOOL_DIR env must be passed to the subprocess, not dropped"
        assert env.get("UV_TOOL_DIR") == str(Path("/opt/uv"))
        assert outcome.auto_upgrade_attempted is True

class TestRunUpgradeUxActiveSnooze:
    def test_active_snooze_suppresses_prompt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from specify_cli.compat.cache import NagCacheRecord

        monkeypatch.setattr(sys, "argv", ["spec-kitty", "status"])
        monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
        _patch_planner(monkeypatch, "ALLOW_WITH_NAG", latest="2.0")

        existing = NagCacheRecord(
            cli_version_key="1.0",
            latest_version="2.0",
            latest_source="pypi",
            fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
            last_shown_at=datetime(2026, 1, 1, tzinfo=UTC),
            remote_version_seen="2.0",
            snooze_step="24h",
            snoozed_until=datetime(2099, 1, 1, tzinfo=UTC),
        )
        _patch_cache_noop(monkeypatch, existing=existing)

        outcome = run_upgrade_ux(
            None,
            suppressed=False,
            env={},
            prompt=lambda: pytest.fail("prompt must not fire under active snooze"),
            upgrade_runner=lambda: 0,
            installer_detector=lambda: InstallMethod.PIPX,
        )
        assert outcome.ran is True
        assert outcome.prompted is False


# ---------------------------------------------------------------------------
# Coordinator-level suppression matrix (acceptance criterion 6 + 8)
# ---------------------------------------------------------------------------


class TestCoordinatorSuppressionMatrix:
    """When the coordinator is invoked on the hosted-enabled path under any
    suppression condition, the upgrade UX MUST NOT prompt or run a subprocess.

    The single source of truth is ``_should_suppress_nag()`` (already tested
    in ``tests/readiness/test_coordinator_suppression_matrix.py`` for the nag
    seam); this test mirrors that surface for the new ``_invoke_upgrade_ux``
    seam.
    """

    @pytest.mark.parametrize(
        "argv,extra_env",
        [
            (["spec-kitty", "status", "--json"], {}),
            (["spec-kitty", "status", "--quiet"], {}),
            (["spec-kitty", "status", "--help"], {}),
            (["spec-kitty", "--version"], {}),
            (["spec-kitty", "status"], {"CI": "1"}),
        ],
    )
    def test_suppression_no_subprocess_no_prompt(
        self,
        monkeypatch: pytest.MonkeyPatch,
        argv: list[str],
        extra_env: dict[str, str],
    ) -> None:
        for k, v in extra_env.items():
            monkeypatch.setenv(k, v)
        monkeypatch.setattr(sys, "argv", argv)
        # Force suppress.
        from specify_cli.cli import helpers as helpers_mod

        # Confirm canonical predicate agrees.
        assert helpers_mod._should_suppress_nag(argv[1:]) is True

        # Patch suppression-aware run_upgrade_ux dependencies.
        outcome = run_upgrade_ux(
            None,
            suppressed=True,
            env=extra_env,
            prompt=lambda: pytest.fail(f"prompt fired under suppression argv={argv}"),
            upgrade_runner=lambda: pytest.fail(f"subprocess fired under suppression argv={argv}"),
            installer_detector=lambda: InstallMethod.PIPX,
        )
        assert outcome.ran is False

    def test_non_tty_suppresses(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "argv", ["spec-kitty", "status"])
        monkeypatch.delenv("CI", raising=False)
        monkeypatch.delenv("SPEC_KITTY_NO_NAG", raising=False)
        monkeypatch.setattr(sys.stdout, "isatty", lambda: False)

        from specify_cli.cli import helpers as helpers_mod

        assert helpers_mod._should_suppress_nag() is True

        outcome = run_upgrade_ux(
            None,
            suppressed=True,
            env={},
            prompt=lambda: pytest.fail("prompt fired on non-TTY"),
            upgrade_runner=lambda: pytest.fail("subprocess fired on non-TTY"),
        )
        assert outcome.ran is False
