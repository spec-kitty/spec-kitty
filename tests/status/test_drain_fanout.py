"""Drain gates the three status fan-out wrappers, the runtime-moment
producer, and the bridge's outcome logging.

``fire_saas_fanout``, ``fire_resolved_binding_fanout`` and
``fire_lifecycle_saas_fanout`` must spawn no thread and call no handler when
drain is off, while the import-time ``moment_handlers_disabled_reason()``
registration gate stays untouched and still composes with the new per-call
gate. The runtime-moment producer must publish nothing under drain-off
without even looking up the run journal. ``zeitgeist_bridge._log_offer_outcome``
must log a ``drain_disabled`` outcome at debug, never WARNING.

``TestRepoScopedGateReadsTheEmittingRepo`` (issue #5181) pins the
repository-scoped half of the gate: the drain posture consulted by each
``fire_*`` wrapper must be the EMITTING repo's own ``.kittify/config.yaml``,
never the process's current working directory. Those tests carry
``real_drain_posture`` (no mocked ``drain_posture``) and construct two real
on-disk repos with divergent ``hosted.drain`` values.
"""

from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from specify_cli.core.env import MOMENT_HANDLER_DISABLE_ENV_VARS
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
# Repo-scoped gate (#5181): the EMITTING repo's posture, never the CWD's.
# ---------------------------------------------------------------------------


def _repo_with_drain(tmp_path: Path, name: str, *, drain: bool | None) -> Path:
    """A tmp-path repo with a ``.kittify/config.yaml`` (present iff *drain* is not ``None``)."""
    root = tmp_path / name
    kittify = root / ".kittify"
    kittify.mkdir(parents=True)
    if drain is not None:
        (kittify / "config.yaml").write_text(f"hosted:\n  drain: {'true' if drain else 'false'}\n", encoding="utf-8")
    return root


@pytest.fixture(autouse=True)
def _clear_moment_handler_env_for_real_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hermetic against an ambient env narrower for the ``real_drain_posture`` tests below.

    Mirrors ``tests/specify_cli/core/test_hosted_posture.py``'s module-local
    fixture of the same purpose: only a test's own explicit ``setenv`` should
    narrow drain here, never whatever the orchestrator's own process
    environment happens to carry.
    """
    for name in MOMENT_HANDLER_DISABLE_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.mark.real_drain_posture
class TestRepoScopedGateReadsTheEmittingRepo:
    """#5181: each ``fire_*`` gate must read the emitting repo's own posture.

    Two real repos on disk, drain configured oppositely, with the process CWD
    pointed at the OTHER repo from the one passed as ``repo_root`` -- the
    bug this closes read ``drain_posture()`` with no ``project_root``, which
    falls back to ``locate_project_root()`` i.e. the CWD, so a transition for
    repo A was gated on repo B's config whenever CWD was repo B.
    """

    def test_fire_saas_fanout_publishes_for_the_emitting_repo_even_when_cwd_is_a_drain_off_repo(
        self,
        tmp_path: Path,
        canonical_home: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        repo_a = _repo_with_drain(tmp_path, "repo_a", drain=True)
        repo_b = _repo_with_drain(tmp_path, "repo_b", drain=False)
        ((tmp_path / "home") / "config.toml").write_text("[hosted]\ndrain = true\n", encoding="utf-8")
        monkeypatch.chdir(repo_b)

        spy = Mock(name="saas-handler")
        adapters.register_saas_fanout_handler(spy)

        adapters.fire_saas_fanout(wp_id="WP01", from_lane="planned", to_lane="claimed", repo_root=repo_a)

        spy.assert_called_once()

    def test_fire_saas_fanout_skips_for_the_emitting_repo_even_when_cwd_is_a_drain_on_repo(
        self,
        tmp_path: Path,
        canonical_home: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        repo_a = _repo_with_drain(tmp_path, "repo_a", drain=False)
        repo_b = _repo_with_drain(tmp_path, "repo_b", drain=True)
        ((tmp_path / "home") / "config.toml").write_text("[hosted]\ndrain = true\n", encoding="utf-8")
        monkeypatch.chdir(repo_b)

        spy = Mock(name="saas-handler")
        adapters.register_saas_fanout_handler(spy)

        adapters.fire_saas_fanout(wp_id="WP01", from_lane="planned", to_lane="claimed", repo_root=repo_a)

        spy.assert_not_called()

    def test_fire_resolved_binding_fanout_reads_the_emitting_repo(
        self,
        tmp_path: Path,
        canonical_home: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        repo_a = _repo_with_drain(tmp_path, "repo_a", drain=True)
        repo_b = _repo_with_drain(tmp_path, "repo_b", drain=False)
        ((tmp_path / "home") / "config.toml").write_text("[hosted]\ndrain = true\n", encoding="utf-8")
        monkeypatch.chdir(repo_b)

        spy = Mock(name="resolved-binding-handler")
        adapters.register_resolved_binding_fanout_handler(spy)

        adapters.fire_resolved_binding_fanout(wp_id="WP01", mission_slug="demo", repo_root=repo_a)

        spy.assert_called_once()

    def test_fire_lifecycle_saas_fanout_reads_the_emitting_repo(
        self,
        tmp_path: Path,
        canonical_home: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        repo_a = _repo_with_drain(tmp_path, "repo_a", drain=True)
        repo_b = _repo_with_drain(tmp_path, "repo_b", drain=False)
        ((tmp_path / "home") / "config.toml").write_text("[hosted]\ndrain = true\n", encoding="utf-8")
        monkeypatch.chdir(repo_b)

        spy = Mock(name="lifecycle-handler")
        adapters.register_lifecycle_saas_fanout_handler(spy)

        adapters.fire_lifecycle_saas_fanout(event_type="MissionRunStarted", repo_root=repo_a)

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
