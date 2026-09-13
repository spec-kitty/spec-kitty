"""Acceptance tests for the canonical hosted-server target resolver (issue #5).

Re-homed and slimmed down from the deleted ``tests/sync/test_target_authority.py``
(``specify_cli.sync.target_authority``) to match the surviving surface at
``specify_cli.auth.server_target``: no queue scope, no user/team identity, no
network. What remains is the precedence contract (env over config over the
packaged default, #3980 — D-5 revised) and the fail-closed split-brain guard.
#179's "no target at all" fail-closed died with the opt-in era: with neither
source naming a target the resolver answers the packaged default
``https://team.spec-kitty.ai``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.auth.config import DEFAULT_HOSTED_SAAS_URL
from specify_cli.auth.server_target import (
    SAAS_URL_ENV_VAR,
    OverrideMode,
    ResolvedServerTarget,
    ServerTargetSplitBrainError,
    resolve_server_target,
)

pytestmark = [pytest.mark.fast]

CONFIG_URL = "https://config.example.com"
ENV_URL = "https://env.example.com"


@pytest.fixture
def target_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Isolate config.toml under a throwaway ``SPEC_KITTY_HOME`` with no env leakage."""
    monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path))
    monkeypatch.delenv(SAAS_URL_ENV_VAR, raising=False)
    return tmp_path


def _write_config(root: Path, server_url: str) -> None:
    (root / "config.toml").write_text(f'[sync]\nserver_url = "{server_url}"\n', encoding="utf-8")


# ---------------------------------------------------------------------------
# Fields + JSON-safety
# ---------------------------------------------------------------------------


def test_all_fields_populated_under_env_equals_config(
    target_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(target_root, CONFIG_URL)
    monkeypatch.setenv(SAAS_URL_ENV_VAR, CONFIG_URL)  # env == config, no override

    target = resolve_server_target()

    assert isinstance(target, ResolvedServerTarget)
    assert target.configured_server_url == CONFIG_URL
    assert target.env_server_url == CONFIG_URL
    assert target.override_mode is OverrideMode.NONE
    assert target.resolved_server_url == CONFIG_URL


def test_to_diagnostics_dict_is_json_safe_with_all_keys(target_root: Path) -> None:
    _write_config(target_root, CONFIG_URL)
    target = resolve_server_target()

    diag = target.to_diagnostics_dict()
    assert set(diag) == {
        "configured_server_url",
        "env_server_url",
        "override_mode",
        "resolved_server_url",
    }
    assert diag["override_mode"] == "none"
    json.dumps(diag)  # must round-trip through JSON


def test_neither_config_nor_env_resolves_to_packaged_default(target_root: Path) -> None:
    """#3980 (D-5 revised): no env value and no config value resolves to the
    packaged default — the launch host — instead of failing closed."""
    target = resolve_server_target()

    assert target.configured_server_url is None
    assert target.env_server_url is None
    assert target.override_mode is OverrideMode.PACKAGED_DEFAULT
    assert target.resolved_server_url == DEFAULT_HOSTED_SAAS_URL


def test_corrupt_config_toml_with_no_env_resolves_to_packaged_default(target_root: Path) -> None:
    (target_root / "config.toml").write_text("this is = = not valid toml", encoding="utf-8")
    target = resolve_server_target()
    assert target.configured_server_url is None
    assert target.resolved_server_url == DEFAULT_HOSTED_SAAS_URL


def test_corrupt_config_toml_is_treated_as_no_configured_url(
    target_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (target_root / "config.toml").write_text("this is = = not valid toml", encoding="utf-8")
    monkeypatch.setenv(SAAS_URL_ENV_VAR, ENV_URL)
    target = resolve_server_target()
    assert target.configured_server_url is None
    assert target.resolved_server_url == ENV_URL


def test_non_table_sync_key_with_no_env_resolves_to_packaged_default(target_root: Path) -> None:
    (target_root / "config.toml").write_text('sync = "oops"\n', encoding="utf-8")
    target = resolve_server_target()
    assert target.resolved_server_url == DEFAULT_HOSTED_SAAS_URL


def test_blank_config_server_url_is_no_opinion_and_yields_packaged_default(target_root: Path) -> None:
    """A blank ``server_url`` is no opinion: with no env value the resolver
    answers the packaged default instead of resolving to an empty target."""
    (target_root / "config.toml").write_text('[sync]\nserver_url = "  "\n', encoding="utf-8")
    target = resolve_server_target()
    assert target.configured_server_url is None
    assert target.resolved_server_url == DEFAULT_HOSTED_SAAS_URL


def test_blank_config_server_url_defers_to_env(
    target_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (target_root / "config.toml").write_text('[sync]\nserver_url = ""\n', encoding="utf-8")
    monkeypatch.setenv(SAAS_URL_ENV_VAR, ENV_URL)
    target = resolve_server_target()
    assert target.configured_server_url is None
    assert target.override_mode is OverrideMode.PROCESS_OVERRIDE
    assert target.resolved_server_url == ENV_URL


def test_non_table_sync_key_is_treated_as_no_configured_url(
    target_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (target_root / "config.toml").write_text('sync = "oops"\n', encoding="utf-8")
    monkeypatch.setenv(SAAS_URL_ENV_VAR, ENV_URL)
    target = resolve_server_target()
    assert target.configured_server_url is None
    assert target.resolved_server_url == ENV_URL


def test_resolved_target_is_immutable(target_root: Path) -> None:
    _write_config(target_root, CONFIG_URL)
    target = resolve_server_target()
    with pytest.raises((AttributeError, TypeError)):
        target.resolved_server_url = "https://mutated.example.com"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# override_mode classification — env > config precedence
# ---------------------------------------------------------------------------


def test_env_equals_config_is_not_an_override(
    target_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(target_root, CONFIG_URL)
    monkeypatch.setenv(SAAS_URL_ENV_VAR, CONFIG_URL + "/")  # trailing slash only
    target = resolve_server_target()
    assert target.override_mode is OverrideMode.NONE
    assert target.resolved_server_url == CONFIG_URL


def test_missing_config_with_env_resolves_to_normalized_env_url(
    target_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing config key is no opinion, not a candidate target (#179)."""
    monkeypatch.setenv(SAAS_URL_ENV_VAR, ENV_URL + "/")
    target = resolve_server_target()
    assert target.configured_server_url is None
    assert target.override_mode is OverrideMode.PROCESS_OVERRIDE
    assert target.resolved_server_url == ENV_URL


def test_missing_config_with_differing_env_is_process_override(
    target_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(SAAS_URL_ENV_VAR, ENV_URL)
    target = resolve_server_target()
    assert target.configured_server_url is None
    assert target.override_mode is OverrideMode.PROCESS_OVERRIDE
    assert target.resolved_server_url == ENV_URL


def test_config_set_with_differing_env_and_process_override_env_wins(
    target_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(target_root, CONFIG_URL)
    monkeypatch.setenv(SAAS_URL_ENV_VAR, ENV_URL)  # disagrees with config
    target = resolve_server_target(process_wide_override=True)

    assert target.override_mode is OverrideMode.PROCESS_OVERRIDE
    assert target.resolved_server_url == ENV_URL


# ---------------------------------------------------------------------------
# Fail-closed split-brain guard (process_wide_override=False)
# ---------------------------------------------------------------------------


def test_ambiguous_setup_only_disagreement_fails_closed(
    target_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(target_root, CONFIG_URL)
    monkeypatch.setenv(SAAS_URL_ENV_VAR, ENV_URL)
    with pytest.raises(ServerTargetSplitBrainError) as excinfo:
        resolve_server_target(process_wide_override=False)

    message = str(excinfo.value)
    # Operator-actionable: both URLs and the env var name appear.
    assert CONFIG_URL in message
    assert ENV_URL in message
    assert SAAS_URL_ENV_VAR in message
    assert excinfo.value.configured_server_url == CONFIG_URL
    assert excinfo.value.env_server_url == ENV_URL


def test_env_equals_config_never_raises_even_with_process_wide_override_false(
    target_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(target_root, CONFIG_URL)
    monkeypatch.setenv(SAAS_URL_ENV_VAR, CONFIG_URL)
    target = resolve_server_target(process_wide_override=False)
    assert target.override_mode is OverrideMode.NONE
    assert target.resolved_server_url == CONFIG_URL


def test_no_env_never_raises_even_with_process_wide_override_false(target_root: Path) -> None:
    _write_config(target_root, CONFIG_URL)
    target = resolve_server_target(process_wide_override=False)
    assert target.override_mode is OverrideMode.NONE
    assert target.resolved_server_url == CONFIG_URL


def test_env_only_machine_resolves_cleanly_even_setup_only(
    target_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#179 follow-on: with no configured value there is nothing to disagree
    with, so an env-only machine is not a split brain in a setup context."""
    monkeypatch.setenv(SAAS_URL_ENV_VAR, ENV_URL)
    target = resolve_server_target(process_wide_override=False)
    assert target.configured_server_url is None
    assert target.override_mode is OverrideMode.PROCESS_OVERRIDE
    assert target.resolved_server_url == ENV_URL


# ---------------------------------------------------------------------------
# Process-override warning (#117): a whole-process override that redirects a
# *configured* target logs a warning; an env-only machine has no configured
# opinion to redirect, so it stays quiet.
# ---------------------------------------------------------------------------


def test_process_override_of_configured_target_logs_warning(
    target_root: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _write_config(target_root, CONFIG_URL)
    monkeypatch.setenv(SAAS_URL_ENV_VAR, ENV_URL)  # disagrees with config

    with caplog.at_level("WARNING", logger="specify_cli.auth.server_target"):
        target = resolve_server_target(process_wide_override=True)

    assert target.override_mode is OverrideMode.PROCESS_OVERRIDE
    [record] = caplog.records
    assert CONFIG_URL in record.getMessage()
    assert ENV_URL in record.getMessage()


def test_env_only_machine_does_not_log_warning(
    target_root: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """No configured value ⇒ nothing is being redirected ⇒ no warning."""
    monkeypatch.setenv(SAAS_URL_ENV_VAR, ENV_URL)

    with caplog.at_level("WARNING", logger="specify_cli.auth.server_target"):
        target = resolve_server_target(process_wide_override=True)

    assert target.override_mode is OverrideMode.PROCESS_OVERRIDE
    assert caplog.records == []


def test_env_equals_config_does_not_log_warning(
    target_root: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Agreement is not a redirection, even with a whole-process override enabled."""
    _write_config(target_root, CONFIG_URL)
    monkeypatch.setenv(SAAS_URL_ENV_VAR, CONFIG_URL)

    with caplog.at_level("WARNING", logger="specify_cli.auth.server_target"):
        target = resolve_server_target(process_wide_override=True)

    assert target.override_mode is OverrideMode.NONE
    assert caplog.records == []


# ---------------------------------------------------------------------------
# #3980 (D-5 revised) + #4259: an unset env is "no opinion"; an explicit one
# is a real opinion even when its value equals the packaged default
# ---------------------------------------------------------------------------


def test_env_naming_the_packaged_default_is_a_real_opinion_and_wins(
    target_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#4259 (restoring explicit env precedence): an env variable explicitly
    set to the packaged default is a real opinion — in a whole-process
    context it wins over a *different* configured target instead of letting
    the stale value through (the 4.0.0rc1 regression resolved the retired
    first-party ``app.spec-kitty.ai`` even with
    ``SPEC_KITTY_SAAS_URL=https://team.spec-kitty.ai`` set). In a setup-only
    context the same disagreement fails closed as a split-brain (tested
    below)."""
    _write_config(target_root, CONFIG_URL)
    monkeypatch.setenv(SAAS_URL_ENV_VAR, DEFAULT_HOSTED_SAAS_URL)

    target = resolve_server_target()

    assert target.override_mode is OverrideMode.PROCESS_OVERRIDE
    assert target.resolved_server_url == DEFAULT_HOSTED_SAAS_URL


def test_env_naming_the_packaged_default_with_no_config_resolves_to_default(
    target_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Explicit env (even == the packaged default) with nothing configured
    resolves to the env value with process-override provenance, not the
    packaged-default mode — the variable really was set."""
    monkeypatch.setenv(SAAS_URL_ENV_VAR, DEFAULT_HOSTED_SAAS_URL)
    target = resolve_server_target(process_wide_override=False)
    assert target.override_mode is OverrideMode.PROCESS_OVERRIDE
    assert target.resolved_server_url == DEFAULT_HOSTED_SAAS_URL


def test_explicit_canonical_env_overrides_stale_retired_saved_target(
    target_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The exact #4259 reproduction, now green: an explicit canonical
    ``SPEC_KITTY_SAAS_URL`` beats a stale ``config.toml [sync].server_url``
    naming the retired first-party endpoint — in the whole-process context
    ``auth login`` resolves with."""
    _write_config(target_root, "https://app.spec-kitty.ai")
    monkeypatch.setenv(SAAS_URL_ENV_VAR, DEFAULT_HOSTED_SAAS_URL)

    target = resolve_server_target()

    assert target.resolved_server_url == DEFAULT_HOSTED_SAAS_URL
    assert target.override_mode is OverrideMode.PROCESS_OVERRIDE


def test_explicit_canonical_env_vs_stale_retired_saved_target_fails_closed_setup_only(
    target_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same disagreement in a setup-only context (no whole-process
    override) fails closed as a split-brain, exactly like any other
    env/config disagreement — an explicit env value equal to the packaged
    default is no longer special-cased out of the guard (#4259)."""
    _write_config(target_root, "https://app.spec-kitty.ai")
    monkeypatch.setenv(SAAS_URL_ENV_VAR, DEFAULT_HOSTED_SAAS_URL)

    with pytest.raises(ServerTargetSplitBrainError):
        resolve_server_target(process_wide_override=False)


def test_env_equals_default_redirecting_configured_target_logs_warning(
    target_root: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """An explicit env value equal to the packaged default that redirects a
    *configured* target is a real redirection and logs the #117 warning."""
    _write_config(target_root, CONFIG_URL)
    monkeypatch.setenv(SAAS_URL_ENV_VAR, DEFAULT_HOSTED_SAAS_URL)

    with caplog.at_level("WARNING", logger="specify_cli.auth.server_target"):
        target = resolve_server_target(process_wide_override=True)

    assert target.override_mode is OverrideMode.PROCESS_OVERRIDE
    [record] = caplog.records
    assert CONFIG_URL in record.getMessage()
    assert DEFAULT_HOSTED_SAAS_URL in record.getMessage()


def test_configured_dev_host_with_no_env_resolves_to_dev_host(
    target_root: Path,
) -> None:
    """#3980 acceptance: a config.toml pointing at a dev host plus no env
    override resolves to the dev host without a split-brain error."""
    _write_config(target_root, "https://spec-kitty-dev.fly.dev")

    target = resolve_server_target(process_wide_override=False)

    assert target.override_mode is OverrideMode.NONE
    assert target.resolved_server_url == "https://spec-kitty-dev.fly.dev"
