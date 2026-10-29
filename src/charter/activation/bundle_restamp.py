"""Re-stamp the synthesis manifest's ``bundle_content_hash`` after a ``charter.yaml`` write.

``bundle_content_hash`` is the content identity of ``charter.yaml`` recorded in
``synthesis-manifest.yaml``. Activation and the compiled-charter refresh both
rewrite ``charter.yaml``; without a re-stamp the committed manifest drifts and
every fresh clone inherits a stale-bundle preflight (#6366).

The digest is always computed by :func:`charter.bundle.compute_bundle_content_hash`
(the single hash authority) and the manifest is persisted through
:func:`~charter.activation.synthesizer.manifest.finalize_manifest`, so only
``bundle_content_hash`` and the derived ``manifest_hash`` can change.
"""

from __future__ import annotations

import sys
from pathlib import Path

from charter.activation.synthesizer.manifest import MANIFEST_PATH, finalize_manifest, load_yaml
from charter.activation.synthesizer.synthesis_lock import (
    SynthesisLockHeldError,
    SynthesisLockUnavailableError,
    synthesis_lock,
    synthesis_lock_path,
)
from charter.activation.synthesizer.synthesize_pipeline import canonical_yaml
from charter.bundle import compute_bundle_content_hash

__all__ = ["restamp_bundle_hash"]

#: One stderr line when the restamp is skipped (``{reason}`` names why the lock was not taken).
_RESTAMP_SKIPPED_WARNING = (
    "Warning: the change was saved, but the synthesis manifest's bundle hash was not refreshed: {reason}. "
    "The next activation change or synthesis run will restamp it."
)
_HELD_REASON = "a `charter synthesize`/`resynthesize` run in this worktree holds {lock_path}"
_UNAVAILABLE_REASON = "git could not be invoked to place the synthesis lock"


def restamp_bundle_hash(repo_root: Path) -> bool:
    """Bring the manifest's ``bundle_content_hash`` in line with ``charter.yaml``.

    Returns ``True`` only when the manifest was rewritten. It is a no-op (``False``)
    when there is no manifest, when the manifest is a built-in-only seed or carries
    no stamp (nothing to keep in parity), when the bundle cannot be hashed, or when
    the stamp already matches.

    A non-synthesis caller has already saved its change when it restamps, so a lock it cannot
    take must not abort it: when a synthesis run holds the lock past the bounded wait
    (:class:`SynthesisLockHeldError`) or git cannot be invoked to place it
    (:class:`SynthesisLockUnavailableError`), print one warning line to stderr and return
    ``False`` (not restamped; the next activation change or synthesis run restamps). Nested
    calls inside a synthesis run re-enter the lock on the same thread and still restamp.
    """
    manifest_path = repo_root / MANIFEST_PATH
    if not manifest_path.is_file():
        return False
    # FR-011 (#6453): the read-modify-write is one unit under the run-wide synthesis lock
    # (re-entrant, so the call from inside a synthesize run nests).
    try:
        with synthesis_lock(repo_root):
            return _restamp_locked(repo_root, manifest_path)
    except SynthesisLockHeldError:
        reason = _HELD_REASON.format(lock_path=synthesis_lock_path(repo_root))
    except SynthesisLockUnavailableError:
        reason = _UNAVAILABLE_REASON
    print(_RESTAMP_SKIPPED_WARNING.format(reason=reason), file=sys.stderr)
    return False


def _restamp_locked(repo_root: Path, manifest_path: Path) -> bool:
    manifest = load_yaml(manifest_path)
    if manifest.built_in_only or manifest.bundle_content_hash is None:
        return False
    current = compute_bundle_content_hash(repo_root)
    if current is None or current == manifest.bundle_content_hash:
        return False
    restamped = finalize_manifest(manifest.model_copy(update={"bundle_content_hash": current}))
    manifest_path.write_text(canonical_yaml(restamped.model_dump(mode="python")).decode("utf-8"), encoding="utf-8")
    return True
