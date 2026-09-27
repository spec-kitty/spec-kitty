"""Fail-closed hosted-target tests for the tracker surfaces (#179, #117).

``server_target.DEFAULT_SERVER_URL`` pointed at ``https://spec-kitty-dev.fly.dev``,
a host that no longer exists (Fly hosting left the programme). Deleting the
default means every hosted path fails closed on an unconfigured machine:

* :class:`~specify_cli.tracker.saas_client.SaaSTrackerClient` construction
  raises :class:`ConfigurationError` instead of silently binding a dead host;
* :func:`~specify_cli.tracker.saas_readiness.evaluate_readiness` yields
  ``MISSING_HOST_CONFIG`` (its no-raise representation of the same condition).

Neither case may open a network connection — that is asserted here by arming
the network seams with failures.

#117 adds the ambiguous-split-brain case (env and ``config.toml`` naming
*different* servers, with no whole-process override): both surfaces resolve
with ``process_wide_override=False``, so that disagreement is now reachable
and fails closed too, the same way an unconfigured machine does.

#305: the readiness evaluator's split-brain case is *not* the same
``MISSING_HOST_CONFIG`` state an unconfigured machine yields — it has its own
``AMBIGUOUS_HOST_CONFIG`` state, because on a split-brain machine
``SPEC_KITTY_SAAS_URL`` is already set, so telling the operator to set it
(``MISSING_HOST_CONFIG``'s remedy) is a dead end. The client-construction case
still raises :class:`ServerTargetSplitBrainError` directly, which already
names both URLs.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from specify_cli.auth.server_target import SAAS_URL_ENV_VAR, ServerTargetSplitBrainError
from specify_cli.tracker.saas_client import SaaSTrackerClient, SaaSTrackerClientError
from specify_cli.tracker.saas_readiness import ReadinessState, evaluate_readiness

pytestmark = pytest.mark.fast


@pytest.fixture
def unconfigured_host(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """No env value, no ``config.toml`` — nothing names a server."""
    monkeypatch.delenv(SAAS_URL_ENV_VAR, raising=False)
    home = tmp_path / "empty-home"
    home.mkdir()
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
    return tmp_path


def _refuse_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("a network call was attempted on an unconfigured machine")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    monkeypatch.setattr(
        "specify_cli.tracker.saas_client.httpx.Client",
        MagicMock(side_effect=_boom),
    )


def test_saas_client_construction_without_host_raises_hosted_endpoint_unconfigured(unconfigured_host: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Endpoint opt-in (mission ``hosted-opt-in-drain-ledger``, FR-011/FR-012,
    reversing #3980 D-5): WP06 removed the packaged-default fallback from
    ``resolve_server_target()``, so construction on an unconfigured machine
    now raises instead of silently binding a live host — re-pinned per
    DIRECTIVE_041 from the retired "binds packaged default" assumption this
    test previously asserted. Construction still opens no network
    connection either way."""
    _refuse_network(monkeypatch)

    with pytest.raises(SaaSTrackerClientError, match="hosted_endpoint_unconfigured|No hosted endpoint configured"):
        SaaSTrackerClient(project_root=unconfigured_host / "repo")


def test_evaluate_readiness_without_host_yields_missing_host_config(unconfigured_host: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Endpoint opt-in (reversing #3980 D-5): with no packaged default any
    more, ``_probe_host_config``'s tolerant except degrades
    ``HostedEndpointUnconfigured`` to ``None``, so an unconfigured machine
    once again yields ``MISSING_HOST_CONFIG`` — re-pinned per DIRECTIVE_041
    from the retired "resolves packaged default" assumption this test
    previously asserted (the reachability probe is never reached)."""
    _refuse_network(monkeypatch)
    # Order: rollout gate → auth → host config → reachability. Pass the first
    # two so the evaluation reaches the host-config check under test.
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "1")
    monkeypatch.setattr("specify_cli.tracker.saas_readiness._probe_auth", lambda _repo_root: True)

    result = evaluate_readiness(
        repo_root=unconfigured_host / "repo",
        probe_reachability=True,
    )

    assert result.state is ReadinessState.MISSING_HOST_CONFIG
    assert not result.is_ready


def test_evaluate_readiness_yields_missing_host_config_only_when_resolver_degrades(unconfigured_host: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``MISSING_HOST_CONFIG`` survives only for a resolver that itself
    degrades (its no-raise representation of an unresolvable target)."""
    _refuse_network(monkeypatch)
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "1")
    monkeypatch.setattr("specify_cli.tracker.saas_readiness._probe_auth", lambda _repo_root: True)

    def _degraded(**_kwargs: object) -> str | None:
        return None

    monkeypatch.setattr("specify_cli.tracker.saas_readiness._probe_host_config", _degraded)

    result = evaluate_readiness(
        repo_root=unconfigured_host / "repo",
        probe_reachability=True,
    )

    assert result.state is ReadinessState.MISSING_HOST_CONFIG
    assert not result.is_ready


# ---------------------------------------------------------------------------
# Ambiguous split-brain (#117): env and config.toml name different servers,
# with no whole-process override. Both surfaces below are security-relevant
# (they carry a bearer token with no human confirming the target at call
# time), so they resolve with ``process_wide_override=False`` and must fail
# closed on the disagreement rather than silently trusting the env value.
# ---------------------------------------------------------------------------


@pytest.fixture
def split_brain_host(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """``config.toml`` names one server; ``SPEC_KITTY_SAAS_URL`` names another."""
    home = tmp_path / "split-brain-home"
    home.mkdir()
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
    (home / "config.toml").write_text('[sync]\nserver_url = "https://configured.example.com"\n', encoding="utf-8")
    monkeypatch.setenv(SAAS_URL_ENV_VAR, "https://env-override.example.com")
    return tmp_path


def test_saas_client_construction_with_split_brain_target_fails_closed(split_brain_host: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An ambiguous env/config disagreement must not silently bind the env host."""
    _refuse_network(monkeypatch)

    with pytest.raises(ServerTargetSplitBrainError) as excinfo:
        SaaSTrackerClient(project_root=split_brain_host / "repo")

    message = str(excinfo.value)
    assert "configured.example.com" in message
    assert "env-override.example.com" in message


def test_evaluate_readiness_with_split_brain_target_yields_ambiguous_host_config(split_brain_host: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The readiness evaluator's no-raise contract degrades the same ambiguity
    to a dedicated ``AMBIGUOUS_HOST_CONFIG`` state (#305) — not
    ``MISSING_HOST_CONFIG``, whose remedy ("set `SPEC_KITTY_SAAS_URL`") is a
    dead end on a split-brain machine where that var is already set — and
    names both disagreeing URLs so the operator can reconcile them."""
    _refuse_network(monkeypatch)
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "1")
    monkeypatch.setattr("specify_cli.tracker.saas_readiness._probe_auth", lambda _repo_root: True)

    result = evaluate_readiness(
        repo_root=split_brain_host / "repo",
        probe_reachability=True,
    )

    assert result.state is ReadinessState.AMBIGUOUS_HOST_CONFIG
    assert result.state.value == "ambiguous_host_config"
    assert not result.is_ready
    assert result.message == (
        "SaaS host configuration is ambiguous: `config.toml` names "
        "`https://configured.example.com` while `SPEC_KITTY_SAAS_URL` names "
        "`https://env-override.example.com`."
    )
    assert result.next_action == (
        "Reconcile the two: update `config.toml`'s `[sync].server_url` to match, or change/unset `SPEC_KITTY_SAAS_URL`, so both name the same host."
    )
