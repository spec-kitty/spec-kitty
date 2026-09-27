"""Runtime-root isolation for ``config.toml`` (issue #2171, inverted).

This mirrors the reproduction from GitHub issue #2171 turned into a *passing*
assertion (``contracts/state-surface-map.md`` → "End-to-end CLI contract"):
with distinct ``HOME`` and ``SPEC_KITTY_HOME``, the hosted-server target stored
in ``config.toml`` is read **only** under ``SPEC_KITTY_HOME`` — the default
``$HOME/.spec-kitty`` layout stays out of the way
(SC-001 / SC-002 / FR-001).

A second case pins backward compatibility: with ``SPEC_KITTY_HOME`` unset the
POSIX default ``~/.spec-kitty`` layout is preserved (SC-003 / NFR-001).

The original reproduction drove the deleted ``spec-kitty sync server <url>``
command (issue #5); the surviving surface with the same root-selection
contract is :func:`specify_cli.auth.server_target.resolve_server_target`,
which reads ``[sync].server_url`` from the runtime root's ``config.toml``.
The command under test only touched a local TOML file — no daemon, no real
ports, no network — so this stays a lightweight test and needs no serial
(``-n0``) marker.

Spec IDs: SC-001, SC-002, SC-003, FR-001, NFR-001
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from specify_cli.auth.server_target import HostedEndpointUnconfigured, resolve_server_target

pytestmark = pytest.mark.integration

# A syntactically valid HTTPS URL that performs no network I/O when set.
_ISOLATED_URL = "https://isolated.example.invalid"
_DECOY_URL = "https://decoy.example.invalid"


def _write_config(config_dir: Path, server_url: str) -> Path:
    """Seed a ``config.toml`` carrying ``[sync] server_url`` under *config_dir*."""
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.toml"
    config_file.write_text(
        f'[sync]\nserver_url = "{server_url}"\n',
        encoding="utf-8",
    )
    return config_file


def test_spec_kitty_home_isolates_sync_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Distinct HOME + SPEC_KITTY_HOME ⇒ config resolves ONLY under the latter.

    This is the literal issue #2171 reproduction, inverted into the assertion
    that ``<SPEC_KITTY_HOME>/config.toml`` is the consulted surface and
    ``<HOME>/.spec-kitty/config.toml`` is not (FR-001 / SC-001 / SC-002).
    """
    default_home = tmp_path / "default-home"
    isolated_root = tmp_path / "isolated-root"
    default_home.mkdir()
    isolated_root.mkdir()

    monkeypatch.setenv("HOME", str(default_home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(isolated_root))
    monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)

    # The isolated runtime root carries the real target; the default home
    # carries a decoy that must never be consulted.
    _write_config(isolated_root, _ISOLATED_URL)
    _write_config(default_home / ".spec-kitty", _DECOY_URL)

    resolved = resolve_server_target()

    # FR-001 / SC-001: the isolated runtime root's config wins ...
    assert resolved.configured_server_url == _ISOLATED_URL
    assert resolved.resolved_server_url == _ISOLATED_URL
    # ... and NOT the decoy under the default home (inverted #2171 / SC-002).
    assert resolved.configured_server_url != _DECOY_URL


def test_unset_spec_kitty_home_preserves_posix_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SC-003 / NFR-001: with the variable unset, config resolves at ``~/.spec-kitty``.

    Backward compatibility — the byte-identical POSIX layout is preserved when no
    isolation root is selected.
    """
    default_home = tmp_path / "posix-home"
    default_home.mkdir()

    monkeypatch.setenv("HOME", str(default_home))
    monkeypatch.delenv("SPEC_KITTY_HOME", raising=False)
    monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
    _write_config(default_home / ".spec-kitty", _ISOLATED_URL)

    resolved = resolve_server_target()

    assert resolved.configured_server_url == _ISOLATED_URL
    assert resolved.resolved_server_url == _ISOLATED_URL


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="POSIX-only default-home fallback (~/.spec-kitty) assertions.",
)
def test_absent_config_raises_hosted_endpoint_unconfigured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No ``config.toml`` anywhere and no env value ⇒ fails closed.

    #179's fail-closed corollary, restored by endpoint opt-in (mission
    ``hosted-opt-in-drain-ledger``, FR-011, reversing #3980 D-5): an
    unconfigured machine neither reads the default home nor invents a
    target from ambient state — WP06 removed the packaged-default fallback
    ``resolve_server_target()`` used to resolve here, so it now raises
    :class:`HostedEndpointUnconfigured` instead. Re-pinned per
    DIRECTIVE_041 from the retired "resolves to the packaged default"
    assumption this test previously asserted; the isolation contract this
    test module exists to prove (neither home is consulted) is unchanged.
    """
    default_home = tmp_path / "empty-home"
    isolated_root = tmp_path / "empty-root"
    default_home.mkdir()
    isolated_root.mkdir()

    monkeypatch.setenv("HOME", str(default_home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(isolated_root))
    monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)

    assert not (default_home / ".spec-kitty" / "config.toml").exists()
    assert not (isolated_root / "config.toml").exists()

    with pytest.raises(HostedEndpointUnconfigured):
        resolve_server_target()
