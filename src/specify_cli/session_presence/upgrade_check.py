"""Version cache management for the upgrade check mechanism.

Background refresh only — never blocks the foreground. Never raises on any failure.

Cache location: ``~/.kittify/last-cli-check.json``
TTL: 3600 seconds (1 hour)

The refresh path resolves the upgrade provider and CLI package name via
``specify_cli.distribution`` so packager entry points take effect without
rewriting this module.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from kernel.clock import now_utc, now_utc_iso, parse_iso, timedelta
from pathlib import Path

from specify_cli.core.env import is_truthy

__all__ = [
    "CACHE_PATH",
    "TTL_SECONDS",
    "UpgradeChecker",
]

# ``refresh_cache_once`` is invoked dynamically via a detached subprocess
# (``python -m specify_cli.session_presence.upgrade_check``, this module's
# own ``__main__`` guard below), which the static dead-code gate cannot
# trace — kept importable but not exported so the gate does not flag it as
# unused.

CACHE_PATH: Path = Path.home() / ".kittify" / "last-cli-check.json"
TTL_SECONDS: int = 3600
OPT_OUT_ENV_VAR: str = "SPEC_KITTY_NO_UPGRADE_CHECK"


def _is_opt_out_set() -> bool:
    """Return True when upgrade checks are disabled by environment."""
    return bool(is_truthy(os.environ.get(OPT_OUT_ENV_VAR)))


def refresh_cache_once() -> None:
    """Refresh the upgrade cache using the resolved provider. Never raises.

    Intended for foreground tests and the background subprocess entry.
    """
    if _is_opt_out_set():
        return

    latest: str | None = None
    prerelease = False
    try:
        from specify_cli.distribution.package_name import resolve_cli_package_name
        from specify_cli.distribution.upgrade_provider import resolve_upgrade_provider
        from specify_cli.compat.planner import _call_provider_get_latest
        from specify_cli.core.channel import prerelease_enabled

        package = resolve_cli_package_name()
        prerelease = prerelease_enabled()
        result = _call_provider_get_latest(resolve_upgrade_provider(), package, prerelease=prerelease)
        if isinstance(result.version, str) and result.version:
            latest = result.version
    except Exception:
        latest = None

    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_PATH.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(
                {
                    "checked_at": now_utc_iso(),
                    "latest_version": latest,
                    "prerelease": prerelease,
                }
            ),
            encoding="utf-8",
        )
        os.replace(tmp, CACHE_PATH)
    except Exception:
        return


class UpgradeChecker:
    """Manage the version cache at ``~/.kittify/last-cli-check.json``.

    All public methods are safe to call unconditionally — any I/O or subprocess
    error is swallowed so callers never need to guard against exceptions.
    """

    def get_available_version(self) -> str | None:
        """Return the cached latest version string, or ``None`` if unavailable."""
        if _is_opt_out_set():
            return None

        try:
            text = CACHE_PATH.read_text(encoding="utf-8")
        except OSError:
            return None

        try:
            data: dict[str, object] = json.loads(text)
        except json.JSONDecodeError:
            return None

        latest_version = data.get("latest_version")
        if not isinstance(latest_version, str):
            return None

        from specify_cli.core.channel import prerelease_enabled

        # An old cache without a channel marker was written for stable only.
        if data.get("prerelease", False) != prerelease_enabled():
            return None

        checked_at_raw = data.get("checked_at")
        if not isinstance(checked_at_raw, str):
            return None
        try:
            checked_at = parse_iso(checked_at_raw)
        except ValueError:
            return None
        if now_utc() - checked_at > timedelta(seconds=TTL_SECONDS):
            self.check_in_background()

        return latest_version

    def check_in_background(self) -> None:
        """Spawn a background subprocess to refresh the version cache.

        Fire-and-forget — returns immediately.  Any failure is silently swallowed.
        """
        if _is_opt_out_set():
            return

        try:
            CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            argv = [sys.executable, "-m", "specify_cli.session_presence.upgrade_check"]
            if os.name == "nt":
                subprocess.Popen(
                    argv,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
                )
            else:
                subprocess.Popen(
                    argv,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
        except Exception:  # intentionally silent — background task must never raise
            pass


if __name__ == "__main__":
    # Entry point for the detached background subprocess launched by
    # `check_in_background` above, run as `python -m
    # specify_cli.session_presence.upgrade_check` (not `python -c <codegen>`
    # — see #4125: a `-c` child has no `__main__.__file__`, and a
    # transitive import reading it crashes on Windows before this ever
    # gets a chance to run). Legitimately fire-and-forget: `refresh_cache_once`
    # already never raises, so no readiness probe or log routing is needed
    # here the way the dashboard's detached child requires.
    refresh_cache_once()
