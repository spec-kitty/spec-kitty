"""Select installable release versions from PyPI JSON metadata."""

from __future__ import annotations


def installable_release_versions(payload: object) -> tuple[str, ...]:
    """Exclude releases with no files or only yanked files (PEP 592)."""
    if not isinstance(payload, dict):
        return ()
    releases = payload.get("releases")
    if not isinstance(releases, dict):
        return ()
    return tuple(
        version
        for version, files in releases.items()
        if isinstance(version, str) and isinstance(files, list) and any(isinstance(file, dict) and not file.get("yanked", False) for file in files)
    )
