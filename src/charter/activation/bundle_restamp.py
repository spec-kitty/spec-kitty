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

from pathlib import Path

from charter.activation.synthesizer.manifest import MANIFEST_PATH, finalize_manifest, load_yaml
from charter.activation.synthesizer.synthesize_pipeline import canonical_yaml
from charter.bundle import compute_bundle_content_hash

__all__ = ["restamp_bundle_hash"]


def restamp_bundle_hash(repo_root: Path) -> bool:
    """Bring the manifest's ``bundle_content_hash`` in line with ``charter.yaml``.

    Returns ``True`` only when the manifest was rewritten. It is a no-op (``False``)
    when there is no manifest, when the manifest is a built-in-only seed or carries
    no stamp (nothing to keep in parity), when the bundle cannot be hashed, or when
    the stamp already matches.
    """
    manifest_path = repo_root / MANIFEST_PATH
    if not manifest_path.is_file():
        return False
    manifest = load_yaml(manifest_path)
    if manifest.built_in_only or manifest.bundle_content_hash is None:
        return False
    current = compute_bundle_content_hash(repo_root)
    if current is None or current == manifest.bundle_content_hash:
        return False
    restamped = finalize_manifest(manifest.model_copy(update={"bundle_content_hash": current}))
    manifest_path.write_text(canonical_yaml(restamped.model_dump(mode="python")).decode("utf-8"), encoding="utf-8")
    return True
