"""Cache-aware emitter for the "no upgrade available" UX (FR-007 / WP09).

This module is the rendering half of the WP09 feature. It:

1. Honours ``SPEC_KITTY_NO_UPGRADE_CHECK=1`` opt-out (checked on every call).
2. Reads / writes a per-user cache at ``~/.cache/spec-kitty/upgrade-check.json``
   (POSIX) or ``%LOCALAPPDATA%\\spec-kitty\\upgrade-check.json`` (Windows).
3. Probes PyPI via :mod:`upgrade_probe` only when the cache is missing or stale.
4. Suppresses identical-channel notices within the cache TTL window (AC #4).
5. Emits a single-line dim notice via Rich's ``Console.print``.

Cache TTL contract:

- Successful probes (channel != UNKNOWN): 24 h.
- Failed probes (channel == UNKNOWN): 1 h.

Performance contract (NFR-004): the cache-warm path completes in <= 100 ms
wall-clock. The cache file is small (~150 B JSON); the hot path performs one
JSON read, one freshness check, and one ``console.print``.

The notifier **never raises** to the caller. All exceptions inside the
function are caught at the boundary; see :func:`maybe_emit_upgrade_notice`.

This module applies the **secure-design-checklist** tactic to the new external
surface (the PyPI probe) — see :mod:`upgrade_probe` for the full audit.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from rich.console import Console

from kernel.clock import Clock, DEFAULT_CLOCK, datetime, parse_iso, timedelta
from kernel.paths import is_windows
from specify_cli.core.env import is_truthy
from specify_cli.core.upgrade_probe import (
    UpgradeChannel,
    UpgradeProbeResult,
    probe_pypi,
)

OPT_OUT_ENV_VAR = "SPEC_KITTY_NO_UPGRADE_CHECK"
"""Environment variable name; set to ``1`` to disable the probe entirely."""

TTL_SUCCESS_SECONDS = 24 * 60 * 60
"""Cache lifetime for successful probes (channel != UNKNOWN): 24 hours."""

TTL_UNKNOWN_SECONDS = 60 * 60
"""Cache lifetime for failed probes (channel == UNKNOWN): 1 hour."""


# ---------------------------------------------------------------------------
# Cache path resolution (POSIX + Windows)
# ---------------------------------------------------------------------------


_CACHE_FILENAME = "upgrade-check.json"
_CACHE_PARENT = "spec-kitty"


def _default_cache_path() -> Path:
    """Resolve the cache file location per platform conventions.

    POSIX: ``~/.cache/spec-kitty/upgrade-check.json``
    Windows: ``%LOCALAPPDATA%\\spec-kitty\\upgrade-check.json``

    Both honour ``XDG_CACHE_HOME`` on POSIX when set.
    """
    if is_windows():
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / _CACHE_PARENT / _CACHE_FILENAME
        # Fallback: user home (Windows without LOCALAPPDATA is unusual but possible)
        return Path.home() / "AppData" / "Local" / _CACHE_PARENT / _CACHE_FILENAME

    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        return Path(xdg) / _CACHE_PARENT / _CACHE_FILENAME
    return Path.home() / ".cache" / _CACHE_PARENT / _CACHE_FILENAME


# ---------------------------------------------------------------------------
# Cache serialization
# ---------------------------------------------------------------------------


def _serialize_result(result: UpgradeProbeResult, ttl_seconds: int) -> dict[str, Any]:
    """Convert an UpgradeProbeResult into a JSON-serializable dict."""
    data = asdict(result)
    data["channel"] = result.channel.value
    data["probed_at"] = result.probed_at.isoformat()
    data["releases"] = list(result.releases)
    data["ttl_seconds"] = ttl_seconds
    return data


def _deserialize_result(data: dict[str, Any]) -> UpgradeProbeResult | None:
    """Reconstruct an UpgradeProbeResult from cache JSON. Returns ``None`` on failure."""
    try:
        return UpgradeProbeResult(
            installed_version=str(data["installed_version"]),
            latest_pypi_version=(str(data["latest_pypi_version"]) if data.get("latest_pypi_version") is not None else None),
            channel=UpgradeChannel(data["channel"]),
            probed_at=parse_iso(data["probed_at"]),
            error=(str(data["error"]) if data.get("error") is not None else None),
            releases=tuple(data.get("releases") or ()),
        )
    except (KeyError, ValueError, TypeError):
        return None


def _load_cache(cache_path: Path) -> tuple[UpgradeProbeResult, int] | None:
    """Read and parse the cache file. Returns ``(result, ttl_seconds)`` or ``None``.

    Returns ``None`` for any read/parse failure — the caller treats this as a
    cache miss and re-probes.
    """
    try:
        raw = cache_path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(data, dict):
        return None

    result = _deserialize_result(data)
    if result is None:
        return None

    try:
        ttl = int(data.get("ttl_seconds", TTL_SUCCESS_SECONDS))
    except (TypeError, ValueError):
        ttl = TTL_SUCCESS_SECONDS

    return result, ttl


def _save_cache(cache_path: Path, result: UpgradeProbeResult, ttl_seconds: int) -> None:
    """Persist the probe result. Best-effort — silently swallows write errors."""
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = _serialize_result(result, ttl_seconds)
        cache_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    except OSError:
        # Disk full, permission denied, etc. — non-fatal per contract.
        return


# ---------------------------------------------------------------------------
# Freshness predicate
# ---------------------------------------------------------------------------


def _is_fresh(
    cached: UpgradeProbeResult,
    ttl_seconds: int,
    current_cli_version: str,
    now: datetime,
) -> bool:
    """Return True iff the cache entry is within TTL and pinned to the current CLI version.

    Per the contract:

        now - probed_at < ttl_seconds
        AND installed_version == get_cli_version()
    """
    if cached.installed_version != current_cli_version:
        return False
    age = now - cached.probed_at
    return age < timedelta(seconds=ttl_seconds)


# ---------------------------------------------------------------------------
# Notice rendering
# ---------------------------------------------------------------------------


_NOTICE_TEMPLATES: dict[UpgradeChannel, str] = {
    UpgradeChannel.ALREADY_CURRENT: ("[dim]spec-kitty-cli {version} — you are on the latest supported version.[/dim]"),
    UpgradeChannel.AHEAD_OF_PYPI: ("[dim]spec-kitty-cli {version} — build is ahead of the latest PyPI release ({latest}). No upgrade required.[/dim]"),
    UpgradeChannel.NO_UPGRADE_PATH: ("[dim]spec-kitty-cli {version} — installed from a non-PyPI build/channel. No PyPI upgrade path is available.[/dim]"),
    # UPGRADE_AVAILABLE intentionally emits no no-upgrade notice; the existing
    # upgrade nag owns that user-facing path.
    # UNKNOWN intentionally emits no notice (contract: "do not block on inability to probe").
}


def _render_notice(result: UpgradeProbeResult, console: Console) -> bool:
    """Render the channel-appropriate notice. Returns True if a notice was emitted."""
    template = _NOTICE_TEMPLATES.get(result.channel)
    if template is None:
        return False

    message = template.format(
        version=result.installed_version,
        latest=result.latest_pypi_version or "?",
    )
    console.print(message)
    return True


# ---------------------------------------------------------------------------
# Opt-out
# ---------------------------------------------------------------------------


def _is_opt_out_set() -> bool:
    """Return True iff the opt-out env var is set to a truthy value.

    Per the contract this is **checked on every invocation** — never cached.
    """
    return is_truthy(os.environ.get(OPT_OUT_ENV_VAR))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def maybe_emit_upgrade_notice(
    cli_version: str,
    *,
    console: Console | None = None,
    now: datetime | None = None,
    cache_path: Path | None = None,
    clock: Clock = DEFAULT_CLOCK,
) -> bool:
    """Emit a channel-appropriate notice if and only if one is warranted.

    The function is the single public entry point for the notifier. It:

    1. Returns ``False`` immediately if ``SPEC_KITTY_NO_UPGRADE_CHECK=1``.
    2. Loads the cache; if fresh and pinned to ``cli_version``, uses it.
    3. Otherwise probes PyPI (via :func:`upgrade_probe.probe_pypi`).
    4. Suppresses the notice if the previous cache entry within TTL was the
       same channel AND the channel is ALREADY_CURRENT (anti-noise rule).
    5. Renders the notice via ``console.print``.
    6. Persists the new result to cache (best-effort).

    Args:
        cli_version: Installed CLI version (from ``get_cli_version()``).
        console: Rich console; defaults to a fresh ``Console()`` on stdout.
        now: Current time; explicit-value test seam, takes precedence over
            ``clock`` when given.
        cache_path: Override cache file location. Test seam.
        clock: Injectable :class:`kernel.clock.Clock` (kernel-clock-single-door
            FR-009); defaults to :data:`kernel.clock.DEFAULT_CLOCK`, the
            sanctioned wall-clock read. Used only when ``now`` is omitted.

    Returns:
        ``True`` if a notice was emitted; ``False`` otherwise (opt-out,
        suppressed, UNKNOWN channel, or any internal failure).

    Notes:
        - This function **never raises**. All exceptions are caught at the
          outer ``try`` and resolved to ``False``.
        - The opt-out env var is consulted on every call.
    """
    try:
        if _is_opt_out_set():
            return False

        if console is None:
            console = Console()
        if now is None:
            now = clock.now()
        if cache_path is None:
            cache_path = _default_cache_path()

        cached_entry = _load_cache(cache_path)
        cached_result: UpgradeProbeResult | None = None
        cached_was_fresh = False

        if cached_entry is not None:
            cached_result, cached_ttl = cached_entry
            if _is_fresh(cached_result, cached_ttl, cli_version, now):
                cached_was_fresh = True

        if cached_was_fresh and cached_result is not None:
            result = cached_result
        else:
            # Probe and stamp the result with the caller-supplied ``now`` so
            # subsequent freshness checks use a single, consistent time source.
            # This matters for tests that thread ``now`` through both calls.
            result = probe_pypi(cli_version)
            result = replace(result, probed_at=now)

        # Anti-noise: suppress ALREADY_CURRENT when the previous cache entry
        # was also ALREADY_CURRENT within its TTL window. The user has already
        # been told they are on the latest version; saying it again on every
        # invocation is noise. We still refresh the cache so the TTL slides.
        suppress = False
        if (
            result.channel == UpgradeChannel.ALREADY_CURRENT
            and cached_result is not None
            and cached_result.channel == UpgradeChannel.ALREADY_CURRENT
            and cached_was_fresh
        ):
            suppress = True

        emitted = False
        if not suppress:
            emitted = _render_notice(result, console)

        # Persist the result (best-effort) regardless of whether we emitted.
        ttl = TTL_UNKNOWN_SECONDS if result.channel == UpgradeChannel.UNKNOWN else TTL_SUCCESS_SECONDS
        _save_cache(cache_path, result, ttl)

        return emitted

    except Exception:  # noqa: BLE001 — notifier must never block the CLI
        return False


__all__ = [
    # OPT_OUT_ENV_VAR, TTL_SUCCESS_SECONDS, TTL_UNKNOWN_SECONDS: demoted —
    # consumed only within this module; no cross-module src/ from-import
    # callers (WP01 harden-dead-symbol-gate-01KW0RJR).
    "maybe_emit_upgrade_notice",
]
