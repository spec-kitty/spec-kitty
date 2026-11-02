#!/usr/bin/env python3
"""Resolve the ``spec-kitty-events`` revision the warmup environment must carry.

``.github/actions/warmup`` builds one editable test environment per run and keys its
dependency cache on the revision it resolved. That revision used to be an input with
an explicit default, which drifted from ``uv.lock`` (``>=11.3.0,<12``) and became a
second authority that lied: ``uv sync --frozen`` installs the locked version whatever
the input said, so the cache key advertised an environment nobody built. This script
is the one resolver instead:

* ``pr``: the version ``uv.lock`` locks. The lock is *the* authority a frozen sync
  follows, so a lock bump (and only a lock bump) changes the key.
* ``full``: the newest release published on PyPI. Full mode exists to notice
  upstream drift; resolving it from the lock would make it a no-op.

It prints exactly the version to stdout and a stable ``WARMUP_*`` code on stderr,
exiting 1 on refusal (2 for an unknown mode, argparse's own contract). It imports
only the standard library so it runs on the bare runner interpreter, before uv or
the project environment exist.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
import urllib.request
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

EVENTS_PACKAGE = "spec-kitty-events"
PYPI_JSON_URL = "https://pypi.org/pypi/{package}/json"

WARMUP_MODE_INVALID = "WARMUP_MODE_INVALID"
WARMUP_EVENTS_UNLOCKED = "WARMUP_EVENTS_UNLOCKED"
WARMUP_EVENTS_INVALID = "WARMUP_EVENTS_INVALID"
WARMUP_EVENTS_LOOKUP_FAILED = "WARMUP_EVENTS_LOOKUP_FAILED"

_MODES = ("pr", "full")
# A PEP 440-ish release identifier: it becomes `uv sync --upgrade-package <pkg>==<rev>`
# and part of a cache key, so anything else (empty, whitespace, a path, a range) is refused.
_VERSION_RE = re.compile(r"[0-9][0-9A-Za-z.+-]*")
_DEFAULT_LOCK = Path("uv.lock")

Fetcher = Callable[[str], dict[str, Any]]


class EventsRevError(RuntimeError):
    """One refusal: a stable ``WARMUP_*`` code and a message naming the source."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code} {message}")
        self.code = code


def _version(value: Any, source: str, code: str) -> str:
    """*value* as a usable revision, or a coded refusal naming *source*."""
    if not isinstance(value, str) or not _VERSION_RE.fullmatch(value):
        raise EventsRevError(code, f"{source} does not record a usable {EVENTS_PACKAGE} version: {value!r}")
    return value


def locked_version(lock_path: Path = _DEFAULT_LOCK, *, package: str = EVENTS_PACKAGE) -> str:
    """The version *lock_path* locks for *package* — the one a frozen sync installs."""
    path = Path(lock_path)
    try:
        lock = tomllib.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise EventsRevError(WARMUP_EVENTS_UNLOCKED, f"cannot read {path}: {exc}; run `uv lock` in the checkout") from exc
    except tomllib.TOMLDecodeError as exc:
        raise EventsRevError(WARMUP_EVENTS_INVALID, f"{path} is not valid TOML: {exc}") from exc

    entries = [entry for entry in lock.get("package", []) if isinstance(entry, dict) and entry.get("name") == package]
    if not entries:
        raise EventsRevError(
            WARMUP_EVENTS_UNLOCKED,
            f"{path} locks no {package}; pr mode has no revision to install (run `uv lock` in the checkout)",
        )
    versions = {_version(entry.get("version"), str(path), WARMUP_EVENTS_INVALID) for entry in entries}
    if len(versions) > 1:
        names = ", ".join(sorted(versions))
        raise EventsRevError(WARMUP_EVENTS_INVALID, f"{path} locks {package} at more than one version ({names}); the warmup environment cannot name one revision")
    return versions.pop()


def _fetch_pypi(package: str) -> dict[str, Any]:
    url = PYPI_JSON_URL.format(package=package)
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise EventsRevError(WARMUP_EVENTS_LOOKUP_FAILED, f"cannot read {url}: {exc}") from exc
    if not isinstance(payload, dict):
        raise EventsRevError(WARMUP_EVENTS_LOOKUP_FAILED, f"{url} did not return a JSON object")
    return payload


def latest_published_version(package: str = EVENTS_PACKAGE, *, fetch: Fetcher | None = None) -> str:
    """The newest release PyPI publishes for *package*."""
    payload = (_fetch_pypi if fetch is None else fetch)(package)
    info = payload.get("info")
    if not isinstance(info, dict) or "version" not in info:
        raise EventsRevError(WARMUP_EVENTS_LOOKUP_FAILED, f"the PyPI payload for {package} carries no info.version")
    return _version(info["version"], f"PyPI {package}", WARMUP_EVENTS_LOOKUP_FAILED)


def resolve(
    mode: str,
    *,
    lock_path: Path = _DEFAULT_LOCK,
    latest: Fetcher | None = None,
) -> str:
    """The revision *mode* requires: the lock's version for ``pr``, the newest release for ``full``."""
    if mode == "pr":
        return locked_version(lock_path)
    if mode == "full":
        return latest_published_version(fetch=latest)
    raise EventsRevError(WARMUP_MODE_INVALID, f"unknown warmup mode {mode!r} (expected one of: {', '.join(_MODES)})")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="warmup_events_rev", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", required=True, choices=_MODES, help="pr: the version uv.lock pins; full: the newest PyPI release")
    parser.add_argument("--lock", default=str(_DEFAULT_LOCK), help="path to uv.lock (relative to the working directory)")
    args = parser.parse_args(argv)
    try:
        print(resolve(args.mode, lock_path=Path(args.lock)))
    except EventsRevError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
