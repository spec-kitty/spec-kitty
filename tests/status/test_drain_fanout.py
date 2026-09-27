"""Drain gates the three status fan-out wrappers, the runtime-moment
producer, and the bridge's outcome logging.

``fire_saas_fanout``, ``fire_resolved_binding_fanout`` and
``fire_lifecycle_saas_fanout`` must spawn no thread and call no handler when
drain is off, while the import-time ``moment_handlers_disabled_reason()``
registration gate stays untouched and still composes with the new per-call
gate. The runtime-moment producer must publish nothing under drain-off
without even looking up the run journal. ``zeitgeist_bridge._log_offer_outcome``
must log a ``drain_disabled`` outcome at debug, never WARNING.
"""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from specify_cli.events.runtime_moments import RuntimeMomentProducer
from specify_cli.status import adapters, zeitgeist_bridge

pytestmark = pytest.mark.fast


@pytest.fixture(autouse=True)
def _clean_registry() -> Any:
    adapters.reset_handlers()
    yield
    adapters.reset_handlers()


# ---------------------------------------------------------------------------
# fire_saas_fanout / fire_resolved_binding_fanout / fire_lifecycle_saas_fanout
# ---------------------------------------------------------------------------


class TestFireSaasFanoutDrainGate:
    def test_no_handler_invoked_under_drain_off(self, drain_off: None, monkeypatch: pytest.MonkeyPatch) -> None:
        spy = Mock(name="saas-handler")
        adapters.register_saas_fanout_handler(spy)
        bounded = Mock(name="_run_fanout_handler_bounded")
        monkeypatch.setattr(adapters, "_run_fanout_handler_bounded", bounded)

        adapters.fire_saas_fanout(wp_id="WP01", from_lane="planned", to_lane="claimed")

        bounded.assert_not_called()
        spy.assert_not_called()

    def test_handler_invoked_exactly_once_under_drain_on(self) -> None:
        """Baseline regression guard (root fixture: drain on)."""
        spy = Mock(name="saas-handler")
        adapters.register_saas_fanout_handler(spy)

        adapters.fire_saas_fanout(wp_id="WP01", from_lane="planned", to_lane="claimed")

        spy.assert_called_once()


class TestFireResolvedBindingFanoutDrainGate:
    def test_no_handler_invoked_under_drain_off(self, drain_off: None, monkeypatch: pytest.MonkeyPatch) -> None:
        spy = Mock(name="resolved-binding-handler")
        adapters.register_resolved_binding_fanout_handler(spy)
        bounded = Mock(name="_run_fanout_handler_bounded")
        monkeypatch.setattr(adapters, "_run_fanout_handler_bounded", bounded)

        adapters.fire_resolved_binding_fanout(wp_id="WP01", mission_slug="demo")

        bounded.assert_not_called()
        spy.assert_not_called()

    def test_handler_invoked_exactly_once_under_drain_on(self) -> None:
        spy = Mock(name="resolved-binding-handler")
        adapters.register_resolved_binding_fanout_handler(spy)

        adapters.fire_resolved_binding_fanout(wp_id="WP01", mission_slug="demo")

        spy.assert_called_once()


class TestFireLifecycleSaasFanoutDrainGate:
    def test_no_handler_invoked_under_drain_off(self, drain_off: None, monkeypatch: pytest.MonkeyPatch) -> None:
        spy = Mock(name="lifecycle-handler")
        adapters.register_lifecycle_saas_fanout_handler(spy)
        bounded = Mock(name="_run_fanout_handler_bounded")
        monkeypatch.setattr(adapters, "_run_fanout_handler_bounded", bounded)

        adapters.fire_lifecycle_saas_fanout(event_type="MissionRunStarted")

        bounded.assert_not_called()
        spy.assert_not_called()

    def test_handler_invoked_exactly_once_under_drain_on(self) -> None:
        spy = Mock(name="lifecycle-handler")
        adapters.register_lifecycle_saas_fanout_handler(spy)

        adapters.fire_lifecycle_saas_fanout(event_type="MissionRunStarted")

        spy.assert_called_once()


# ---------------------------------------------------------------------------
# Runtime-moment producer: publishes nothing under drain-off
# ---------------------------------------------------------------------------


class TestRuntimeMomentProducerDrainGate:
    def test_publish_skips_the_journal_lookup_under_drain_off(self, tmp_path: Path, drain_off: None, monkeypatch: pytest.MonkeyPatch) -> None:
        from specify_cli.events import runtime_moments as rm

        find_run_journal = Mock(name="find_run_journal")
        monkeypatch.setattr(rm, "find_run_journal", find_run_journal)

        producer = RuntimeMomentProducer(feature_dir=tmp_path, mission_slug="demo")
        payload = SimpleNamespace(model_dump=lambda mode: {"run_id": "r1"})
        producer._publish("MissionRunStarted", payload)  # type: ignore[arg-type]

        find_run_journal.assert_not_called()


# ---------------------------------------------------------------------------
# zeitgeist_bridge._log_offer_outcome: drain_disabled logs at debug, not WARNING
# ---------------------------------------------------------------------------


class TestLogOfferOutcomeDrainDisabled:
    def test_drain_disabled_outcome_logs_debug_never_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """A ``DRAIN_DISABLED`` offer result is a silent debug skip."""
        from specify_cli.zeitgeist_client.transport import OfferOutcome, OfferResult

        caplog.set_level(logging.DEBUG, logger="specify_cli.status.zeitgeist_bridge")
        result = OfferResult(outcome=OfferOutcome.DRAIN_DISABLED, request_id="req-1", elapsed_s=0.0)

        zeitgeist_bridge._log_offer_outcome("test", result)

        assert not any(record.levelno >= logging.WARNING for record in caplog.records)
        assert any(record.levelno == logging.DEBUG and "drain off" in record.message for record in caplog.records)
