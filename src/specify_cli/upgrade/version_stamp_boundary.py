"""One failure boundary around every write of the project version stamp (#4275).

``spec-kitty upgrade`` stamps ``.kittify/metadata.yaml`` (``version``,
``last_upgraded_at``, ``schema_version``) in the runner or the no-migrations
path, but the CLI's final surface repair runs afterwards and can still fail.
This boundary snapshots the stamp before the first write and puts it back
when the run fails or raises, via :class:`~specify_cli.upgrade.metadata.VersionStamp`
-- the same restore authority the runner uses for a failed migration (#3334).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from click.exceptions import Exit

from .metadata import VersionStamp
from .outcome import UpgradeOutcome, UpgradeOutcomeKind

logger = logging.getLogger(__name__)


def restored_notice(old_version: str | None) -> str:
    """The one-line notice printed when a failed upgrade's version stamp was put back."""
    return f".kittify/metadata.yaml restored to {old_version or 'its previous version'}; the change is uncommitted"


@contextmanager
def version_stamp_boundary(
    kittify_dir: Path,
    *,
    dry_run: bool,
    on_restored: Callable[[str], None] | None = None,
) -> Iterator[Callable[[UpgradeOutcome], None]]:
    """Snapshot the version stamp; restore it when the body raises or the settled outcome failed.

    Yields ``settle(outcome)``: call it once the outcome is final. A failed
    outcome (``UpgradeOutcomeKind.FAILED``) restores the snapshot; a success, a
    no-op and an unresolved-drift outcome keep what was stamped. A dry run
    never writes, so it takes no snapshot and nothing is ever restored.

    ``on_restored`` is called with the restore notice when a failed outcome's
    restore actually rewrote ``metadata.yaml``: the restore is uncommitted.
    """
    # This outer snapshot is authoritative over the MigrationRunner's own inner
    # ``VersionStamp.capture`` (runner.py): it is taken before any stamp write.
    stamp = None if dry_run else VersionStamp.capture(kittify_dir)

    def settle(outcome: UpgradeOutcome) -> None:
        if stamp is None or outcome.kind is not UpgradeOutcomeKind.FAILED:
            return
        if stamp.restore(kittify_dir) and on_restored is not None:
            on_restored(restored_notice(stamp.version))

    try:
        yield settle
    except BaseException as exc:
        # ``Exit(0)`` is an orderly early finish, not a failure: keep the stamp.
        if stamp is not None and not (isinstance(exc, Exit) and exc.exit_code == 0):
            _restore_keeping_original_error(stamp, kittify_dir)
        raise


def _restore_keeping_original_error(stamp: VersionStamp, kittify_dir: Path) -> None:
    """Restore the stamp for a raising body without masking the body's own exception."""
    try:
        stamp.restore(kittify_dir)
    except OSError as exc:
        logger.warning("Could not restore %s/metadata.yaml after a failed upgrade: %s", kittify_dir, exc)
