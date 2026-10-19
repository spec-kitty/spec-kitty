"""Fail the session when the placed ``packs/built-in`` tree no longer matches its pin (#6451).

After a ``git pull`` that bumps ``packs/built-in.source.yaml``, the tree synced from the old
pin would otherwise be used silently. The guard is read-only (``check_pack`` never repairs or
writes), so it is safe in every xdist worker. It is a no-op when the checkout has no pin or
the tree is absent: an absent tree is ``BuiltInPackMissing``'s job.
"""

from pathlib import Path

import pytest

_PIN = Path("packs") / "built-in.source.yaml"
_TREE = Path("packs") / "built-in"


def assert_pack_tree_current(checkout: Path) -> None:
    pin_path = checkout / _PIN
    tree = checkout / _TREE
    if not pin_path.is_file() or not tree.is_dir():
        return
    from charter.offering.packs.pack_fetch import PackSyncError, PackTreeStatus, check_pack
    from charter.offering.packs.pack_pin import PackPinError, load_pack_pin

    try:
        status = check_pack(load_pack_pin(pin_path), tree)
    except (PackPinError, PackSyncError) as exc:
        raise pytest.UsageError(f"{_PIN} cannot be verified against {_TREE}: {exc}") from exc
    if status is PackTreeStatus.STALE:
        raise pytest.UsageError(f"{_TREE} does not match the digests pinned in {_PIN} (the pin moved or the tree was edited). Run `make sync-packs` to refetch it.")
