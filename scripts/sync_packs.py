#!/usr/bin/env python3
"""Fetch, verify and place the pinned ``packs/built-in`` and ``packs/internal`` trees (#6451).

Thin argparse wrapper over :mod:`charter.offering.packs.pack_fetch`; it holds no
sync logic. ``make sync-packs`` runs ``--pack all``.

Exit 0 on success, 1 on any failure, with a stable ``PACK_*`` code on stderr.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

# Not the ``charter.packs`` facade: it imports charter.activation, which resolves
# packs/built-in at import time, so it cannot load before the tree is synced.
from charter.offering.packs.pack_fetch import (
    PACK_PIN_INVALID,
    PACK_TREE_STALE,
    PackSyncError,
    PackTreeStatus,
    check_pack,
    fetch_to_cache,
    place_pack,
)
from charter.offering.packs.pack_pin import PackPin, PackPinError, load_pack_pin
from kernel.pack_tiers import pin_filename

PACK_NAMES = ("built-in", "internal")
_ALL = "all"
_PLACEHOLDER_SHA = "0" * 40
_PACKS_DIR = "packs"


def _pin_path(root: Path, name: str) -> Path:
    return root / _PACKS_DIR / pin_filename(name)


def _load_pin(root: Path, name: str) -> PackPin:
    path = _pin_path(root, name)
    try:
        pin = load_pack_pin(path)
    except FileNotFoundError as exc:
        raise PackSyncError(PACK_PIN_INVALID, f"pack '{name}': pin file {path} not found") from exc
    except (PackPinError, OSError) as exc:
        raise PackSyncError(PACK_PIN_INVALID, f"pack '{name}': {exc}") from exc
    if pin.commit == _PLACEHOLDER_SHA:
        raise PackSyncError(
            PACK_PIN_INVALID,
            f"pack '{name}': {path} still holds the placeholder (all-zero) commit; bump it to a real spec-kitty-open-packs commit before syncing this pack",
        )
    return pin


def _sync_one(root: Path, name: str, *, offline: bool, check: bool) -> str:
    pin = _load_pin(root, name)
    dest = root / _PACKS_DIR / name
    if check:
        status = check_pack(pin, dest)
        if status is not PackTreeStatus.OK:
            raise PackSyncError(PACK_TREE_STALE, f"pack '{name}' tree at {dest} is {status.value}; run `make sync-packs`")
        return f"{name}: ok"
    cached = fetch_to_cache(pin, offline=offline)
    place_pack(cached, dest, pin)
    return f"{name}: synced {pin.commit[:12]}"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sync_packs", description=__doc__)
    parser.add_argument("--pack", choices=[*PACK_NAMES, _ALL], default=_ALL)
    parser.add_argument("--offline", action="store_true", help="use only the local cache; never touch the network")
    parser.add_argument("--check", action="store_true", help="verify placed trees against their pins; change nothing")
    return parser


def main(argv: Sequence[str] | None = None, *, repo_root: Path | None = None) -> int:
    """Run the sync; *repo_root* defaults to this script's repository."""
    args = _parser().parse_args(argv)
    root = Path(__file__).resolve().parents[1] if repo_root is None else Path(repo_root)
    names = PACK_NAMES if args.pack == _ALL else (args.pack,)
    failed = False
    for name in names:
        try:
            print(_sync_one(root, name, offline=args.offline, check=args.check))
        except PackSyncError as exc:
            failed = True
            print(str(exc), file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
