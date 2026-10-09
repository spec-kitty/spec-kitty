"""Assign immutable identity fields to all entities in a legacy project.

Three legacy entry points (preserved for backward compatibility):

- :func:`backfill_project_uuid` – write ``spec_kitty.project_uuid`` to
  ``.kittify/metadata.yaml``.
- :func:`backfill_mission_ids` – write ``mission_id`` to every feature
  ``meta.json`` under ``kitty-specs/``.
- :func:`backfill_wp_ids` – write ``work_package_id``, ``wp_code``, and
  ``mission_id`` to each WP frontmatter file under ``tasks/``.

WP04 additions (FR-013, FR-014, FR-050, FR-051):

- :class:`BackfillResult` – per-mission result dataclass.
- :func:`backfill_mission` – idempotent ULID write for a single mission.
- :func:`backfill_repo` – walk ``kitty-specs/`` and call
  :func:`backfill_mission` on each.

All functions are *idempotent*: if an ID already exists it is never
overwritten.
"""

from __future__ import annotations

import io
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import ulid as _ulid_mod
from ruamel.yaml import YAML

from specify_cli.core.atomic import atomic_write
from specify_cli.mission_metadata import _coerce_mission_number
from specify_cli.meta_keys import MISSION_ID_KEY, MISSION_NUMBER_KEY

logger = logging.getLogger(__name__)

# Pattern that matches WP filenames like "WP01-some-title.md" or "WP01.md"
_WP_CODE_RE = re.compile(r"^(WP\d{2,})")


def _generate_ulid() -> str:
    """Return a new ULID string, compatible with both ulid and python-ulid packages."""
    if hasattr(_ulid_mod, "new"):
        return str(_ulid_mod.new().str)
    return str(_ulid_mod.ULID())


def _make_yaml() -> YAML:
    """Return a ruamel.yaml instance configured for round-trip editing."""
    y = YAML()
    y.preserve_quotes = True
    y.width = 4096
    y.indent(mapping=2, sequence=2, offset=0)
    return y


# ---------------------------------------------------------------------------
# WP04: BackfillResult dataclass
# ---------------------------------------------------------------------------

BackfillAction = Literal["wrote", "skip", "error"]


@dataclass
class BackfillResult:
    """Per-mission result from :func:`backfill_mission`.

    Attributes:
        feature_dir: Absolute path to the mission directory.
        slug: Directory name used as mission slug.
        action: ``"wrote"`` – ULID minted and written; ``"skip"`` – field
            already present; ``"error"`` – unrecoverable per-mission error.
        mission_id: Newly minted ULID when *action* is ``"wrote"``, existing
            ULID when *action* is ``"skip"``, ``None`` on error.
        number_coerced: ``True`` when ``mission_number`` was rewritten from
            a string (e.g. ``"042"``) to an integer (``42``).
        reason: Human-readable explanation (populated on ``"skip"`` and
            ``"error"``).
    """

    feature_dir: Path
    slug: str
    action: BackfillAction
    mission_id: str | None = None
    number_coerced: bool = False
    reason: str | None = None


# ---------------------------------------------------------------------------
# WP04: idempotent single-mission backfill
# ---------------------------------------------------------------------------


def backfill_mission(feature_dir: Path, *, dry_run: bool = False) -> BackfillResult:
    """Idempotently write ``mission_id`` into ``<feature_dir>/meta.json``.

    If ``mission_id`` is already present and non-empty the call is a no-op
    (returns ``action="skip"``).  If missing or empty a fresh ULID is minted
    and written atomically.

    Also applies legacy ``mission_number`` type coercion (T020): a string
    value that parses as a positive integer (e.g. ``"042"``) is rewritten as
    the integer ``42``.  Sentinel strings such as ``"pending"`` raise
    :class:`ValueError` immediately — they are never silently discarded.

    Args:
        feature_dir: Absolute path to a single mission directory containing
            ``meta.json``.
        dry_run: When ``True``, compute the result without writing to disk.

    Returns:
        A :class:`BackfillResult` describing what happened.
    """
    slug = feature_dir.name
    meta_path = feature_dir / "meta.json"

    # --- missing meta.json ---------------------------------------------------
    if not meta_path.exists():
        logger.debug("Skipping %s (no meta.json)", slug)
        return BackfillResult(
            feature_dir=feature_dir,
            slug=slug,
            action="skip",
            reason="meta.json not found",
        )

    # --- read (post-#2091 canonical reader; existence already verified above) --
    from specify_cli.core.paths import load_meta_fail_closed, MissionMetaReadError
    try:
        meta_result = load_meta_fail_closed(feature_dir)
        meta: dict[str, Any] = meta_result or {}
    except MissionMetaReadError as exc:
        logger.warning("Corrupt meta.json in %s: %s", slug, exc)
        return BackfillResult(
            feature_dir=feature_dir,
            slug=slug,
            action="error",
            reason=f"corrupt json: {exc}",
        )

    changed = False

    # --- mission_id ----------------------------------------------------------
    existing_id: str | None = meta.get("mission_id") or None  # treat "" as None
    if existing_id is not None:
        skip_id = True
        new_id = existing_id
    else:
        skip_id = False
        new_id = _generate_ulid()
        meta[MISSION_ID_KEY] = new_id
        changed = True

    # --- mission_number coercion (T020) --------------------------------------
    number_coerced = False
    raw_number = meta.get("mission_number")
    if isinstance(raw_number, str) and raw_number.strip():
        try:
            coerced = _coerce_mission_number(raw_number)
        except (TypeError, ValueError) as exc:
            # Sentinel strings like "pending" — raise loudly, do not guess.
            raise ValueError(
                f"Cannot coerce mission_number {raw_number!r} in {slug}: {exc}"
            ) from exc
        if coerced is not None:
            meta[MISSION_NUMBER_KEY] = coerced
            number_coerced = True
            changed = True

    # --- write (sorted keys, standard format matching write_meta) ---------------
    if changed and not dry_run:
        content = json.dumps(meta, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
        meta_path.write_text(content, encoding="utf-8")

    if skip_id and not number_coerced:
        return BackfillResult(
            feature_dir=feature_dir,
            slug=slug,
            action="skip",
            mission_id=existing_id,
            number_coerced=False,
            reason="mission_id already present",
        )

    action: BackfillAction = "skip" if dry_run and skip_id else "wrote" if not skip_id else "skip"
    # If mission_id was already present but number was coerced, report "wrote"
    if number_coerced and not dry_run:
        action = "wrote"
    if dry_run and not skip_id:
        action = "wrote"  # dry-run would-write
    return BackfillResult(
        feature_dir=feature_dir,
        slug=slug,
        action=action,
        mission_id=new_id,
        number_coerced=number_coerced,
    )


# ---------------------------------------------------------------------------
# WP04: repo-level walk
# ---------------------------------------------------------------------------


def backfill_repo(
    repo_root: Path,
    *,
    dry_run: bool = False,
    mission_slug: str | None = None,
) -> list[BackfillResult]:
    """Walk ``kitty-specs/`` and idempotently backfill every mission.

    Args:
        repo_root: Absolute path to the repository root.
        dry_run: When ``True``, compute results without writing any files.
        mission_slug: When provided, scope the walk to a single mission
            directory (optional).

    Returns:
        List of :class:`BackfillResult`, one per mission directory visited.
    """
    kitty_specs = repo_root / "kitty-specs"
    results: list[BackfillResult] = []

    if not kitty_specs.is_dir():
        logger.warning("kitty-specs/ not found at %s", repo_root)
        return results

    if mission_slug is not None:
        # Scope to a single mission directory.
        candidates: list[Path] = []
        for entry in kitty_specs.iterdir():
            if entry.is_dir() and entry.name == mission_slug:
                candidates.append(entry)
        if not candidates:
            logger.warning("No mission directory found for slug %r", mission_slug)
            return results
    else:
        candidates = sorted(
            entry for entry in kitty_specs.iterdir() if entry.is_dir()
        )

    for feature_dir in candidates:
        result = backfill_mission(feature_dir, dry_run=dry_run)
        results.append(result)

    return results


def backfill_project_uuid(repo_root: Path) -> str:
    """Assign ``spec_kitty.project_uuid`` to ``.kittify/metadata.yaml``.

    If the field already exists the existing value is returned unchanged.

    Args:
        repo_root: Absolute path to the project root.

    Returns:
        The project UUID (ULID string), whether newly generated or pre-existing.

    Raises:
        FileNotFoundError: If ``.kittify/metadata.yaml`` does not exist.
    """
    metadata_path = repo_root / ".kittify" / "metadata.yaml"
    if not metadata_path.exists():
        raise FileNotFoundError(f"metadata.yaml not found: {metadata_path}")

    y = _make_yaml()
    with open(metadata_path, encoding="utf-8") as fh:
        data = y.load(fh)

    if data is None:
        data = {}

    spec_kitty: dict[str, Any] = data.setdefault("spec_kitty", {})

    if "project_uuid" in spec_kitty:
        existing: str = spec_kitty["project_uuid"]
        logger.debug("project_uuid already set: %s (skipping)", existing)
        return existing

    new_uuid = _generate_ulid()
    spec_kitty["project_uuid"] = new_uuid
    logger.info("Assigned project_uuid=%s", new_uuid)

    buf = io.StringIO()
    y.dump(data, buf)
    atomic_write(metadata_path, buf.getvalue())

    return new_uuid


def backfill_mission_ids(repo_root: Path) -> dict[str, str]:
    """Assign ``mission_id`` to every feature ``meta.json`` under ``kitty-specs/``.

    Scans ``<repo_root>/kitty-specs/`` for directories that contain a
    ``meta.json`` file.  Each feature directory whose ``meta.json`` does not
    yet have a ``mission_id`` key receives a freshly generated ULID.

    Args:
        repo_root: Absolute path to the project root.

    Returns:
        Mapping of ``feature_slug → mission_id`` for every feature processed.
        Features that already had a ``mission_id`` appear in the mapping with
        their existing value.
    """
    kitty_specs = repo_root / "kitty-specs"
    mapping: dict[str, str] = {}

    if not kitty_specs.is_dir():
        logger.warning("kitty-specs/ not found at %s — no mission IDs backfilled", repo_root)
        return mapping

    for feature_dir in sorted(kitty_specs.iterdir()):
        if not feature_dir.is_dir():
            continue

        meta_path = feature_dir / "meta.json"
        from specify_cli.core.paths import load_meta_fail_closed
        meta = load_meta_fail_closed(feature_dir)
        if meta is None:
            logger.debug("Skipping %s (no meta.json)", feature_dir.name)
            continue

        if "mission_id" in meta:
            mapping[feature_dir.name] = meta["mission_id"]
            logger.debug("mission_id already set for %s: %s", feature_dir.name, meta["mission_id"])
            continue

        new_id = _generate_ulid()
        meta[MISSION_ID_KEY] = new_id
        mapping[feature_dir.name] = new_id
        logger.info("Assigned mission_id=%s to feature %s", new_id, feature_dir.name)

        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=2, ensure_ascii=False)
            fh.write("\n")

    return mapping


def backfill_wp_ids(feature_dir: Path, mission_id: str) -> dict[str, str]:
    """Assign ``work_package_id``, ``wp_code``, and ``mission_id`` to each WP.

    Scans ``<feature_dir>/tasks/WP*.md`` for work-package frontmatter files.
    For each WP that does not already have a ``work_package_id``, a ULID is
    generated and written.  ``wp_code`` is derived from the filename (e.g.
    ``WP01-foo.md → "WP01"``).  ``mission_id`` is always written (it may
    already be correct but we set it explicitly for consistency).

    Uses the existing :class:`~specify_cli.frontmatter.FrontmatterManager` for
    round-trip-safe reading and writing.

    Args:
        feature_dir: Path to the feature directory (e.g. ``kitty-specs/057-…``).
        mission_id:  ULID string for the parent feature's ``mission_id``.

    Returns:
        Mapping of ``wp_code → work_package_id`` for every WP file found.
    """
    from specify_cli.frontmatter import FrontmatterManager

    tasks_dir = feature_dir / "tasks"
    mapping: dict[str, str] = {}

    if not tasks_dir.is_dir():
        logger.debug("No tasks/ directory in %s — skipping WP ID backfill", feature_dir.name)
        return mapping

    manager = FrontmatterManager()

    for wp_file in sorted(tasks_dir.glob("WP*.md")):
        # Derive wp_code from filename
        m = _WP_CODE_RE.match(wp_file.stem)
        if not m:
            logger.warning("Cannot derive wp_code from filename %s — skipping", wp_file.name)
            continue
        wp_code = m.group(1)

        try:
            frontmatter, body = manager.read(wp_file)
        except Exception as exc:
            logger.warning("Cannot read frontmatter from %s: %s — skipping", wp_file.name, exc)
            continue

        updates: dict[str, Any] = {}

        # mission_id — always propagate
        if frontmatter.get("mission_id") != mission_id:  # MIGRATION-ONLY: raw dict read-mutate-write
            updates["mission_id"] = mission_id

        # wp_code — set if missing
        if "wp_code" not in frontmatter:
            updates["wp_code"] = wp_code

        # work_package_id — only generate if absent
        if "work_package_id" not in frontmatter:
            new_wp_id = _generate_ulid()
            updates["work_package_id"] = new_wp_id
            logger.info("Assigned work_package_id=%s to %s", new_wp_id, wp_file.name)
        else:
            logger.debug(
                "work_package_id already set for %s: %s",
                wp_file.name,
                frontmatter["work_package_id"],
            )

        if updates:
            frontmatter.update(updates)
            manager.write(wp_file, frontmatter, body)

        mapping[wp_code] = frontmatter.get("work_package_id") or updates.get("work_package_id", "")  # MIGRATION-ONLY: raw dict read-mutate-write

    return mapping
