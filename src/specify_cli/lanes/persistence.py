"""Read and write lanes.json for a feature directory.

The lanes.json file lives at kitty-specs/{mission_slug}/lanes.json
and is the sole persistence location for lane assignments.

Read is fail-closed: a corrupt or malformed lanes.json raises
CorruptLanesError rather than silently falling back to no-lanes mode.
Write uses atomic rename to prevent truncated files.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from kernel.errors import GuardedReadError
from specify_cli.lanes.models import LanesManifest

LANES_FILENAME = "lanes.json"


def resolve_lanes_dir(feature_dir: Path) -> Path:
    """Return the canonical ``lanes.json`` path for a feature directory.

    Single pure seam (#1993): the one place that knows how the lanes file
    path is composed from a feature dir. Pure path composition — no I/O, no
    topology semantics. Route every ``feature_dir / lanes.json`` derivation
    through here so the join is defined exactly once.
    """
    return feature_dir / LANES_FILENAME


class CorruptLanesError(GuardedReadError):
    """Raised when lanes.json exists but cannot be parsed.

    Re-parented together with :class:`MissingLanesError` (mission
    cli-error-surface-seam) — the caller census treats them as one coupled
    unit since many callers tuple-catch both.
    """


class MissingLanesError(GuardedReadError):
    """Raised when lanes.json is required but missing.

    Re-parented together with :class:`CorruptLanesError` (mission
    cli-error-surface-seam) — see that class's docstring.
    """


def write_lanes_json(feature_dir: Path, manifest: LanesManifest) -> Path:
    """Write lanes.json atomically to the feature directory.

    Uses write-to-temp + rename to prevent truncated files on crash.

    Args:
        feature_dir: Path to kitty-specs/{mission_slug}/.
        manifest: The LanesManifest to persist.

    Returns:
        Path to the written lanes.json file.
    """
    lanes_path = resolve_lanes_dir(feature_dir)
    content = json.dumps(manifest.to_dict(), indent=2, sort_keys=False) + "\n"

    fd, tmp_path = tempfile.mkstemp(
        dir=str(feature_dir), prefix=".lanes-", suffix=".tmp"
    )
    try:
        os.write(fd, content.encode("utf-8"))
        os.close(fd)
        os.replace(tmp_path, str(lanes_path))
    except BaseException:
        os.close(fd) if not os.get_inheritable(fd) else None  # noqa: E501
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    return lanes_path


def read_lanes_json(feature_dir: Path) -> LanesManifest | None:
    """Read lanes.json from the feature directory.

    Returns None only when the file does not exist (no lanes computed).
    Raises CorruptLanesError if the file exists but is malformed — this
    prevents silent fallback to legacy no-lanes mode.

    Args:
        feature_dir: Path to kitty-specs/{mission_slug}/.

    Returns:
        A LanesManifest if the file exists, None if absent.

    Raises:
        CorruptLanesError: If the file exists but cannot be parsed.
    """
    lanes_path = resolve_lanes_dir(feature_dir)
    if not lanes_path.exists():
        return None
    try:
        data = json.loads(lanes_path.read_text(encoding="utf-8"))
        return LanesManifest.from_dict(data)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise CorruptLanesError(
            f"lanes.json at {lanes_path} is corrupt or malformed: {exc}"
        ) from exc


def require_lanes_json(feature_dir: Path) -> LanesManifest:
    """Read lanes.json or raise a deterministic missing-manifest error."""
    manifest = read_lanes_json(feature_dir)
    if manifest is None:
        raise MissingLanesError(
            f"lanes.json is required for {feature_dir}. "
            "Run the task-finalization step to compute execution lanes."
        )
    return manifest
