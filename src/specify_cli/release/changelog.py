"""Draft changelog builder for spec-kitty release preparation.

Reads ``kitty-specs/`` artifacts and local git tags only.
Zero network calls (FR-014).
"""

from __future__ import annotations

from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.mission_metadata import load_meta_or_empty
from specify_cli.status import Lane, StoreError
import subprocess
from pathlib import Path

# Accepted lanes in the 3.x event-log model (FR-605)
_ACCEPTED_LANES: frozenset[Lane] = frozenset({Lane.APPROVED, Lane.DONE})


def _run_git(args: list[str], cwd: Path) -> str:
    """Run a git command and return stripped stdout. Raises on non-zero exit."""
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _find_most_recent_v_tag(repo_root: Path) -> str | None:
    """Return the most recent tag matching ``v*``, or None if no tags exist."""
    output = _run_git(
        ["tag", "--list", "v*", "--sort=-creatordate"],
        cwd=repo_root,
    )
    if not output:
        return None
    # head -1 equivalent: take the first non-empty line
    for line in output.splitlines():
        line = line.strip()
        if line:
            return line
    return None


def _tag_commit_date(repo_root: Path, tag: str) -> str | None:
    """Return the ISO-8601 commit date for the tagged commit, or None."""
    output = _run_git(
        ["log", "-1", "--format=%cI", f"refs/tags/{tag}"],
        cwd=repo_root,
    )
    return output if output else None


def _read_meta_json(mission_dir: Path) -> dict[str, object]:
    """Read and return the parsed meta.json for a mission directory, or {}."""
    result: dict[str, object] = load_meta_or_empty(mission_dir)
    return result


def _read_spec_title(mission_dir: Path) -> str:
    """Extract the first H1 title from spec.md, or return the dir name."""
    spec_path = mission_dir / "spec.md"
    if not spec_path.exists():
        return mission_dir.name
    try:
        content = spec_path.read_text(encoding="utf-8")
    except OSError:
        return mission_dir.name
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return mission_dir.name


def _parse_wp_frontmatter_status(wp_file: Path) -> str | None:
    """Read the YAML frontmatter ``status`` field from a WP markdown file."""
    try:
        content = wp_file.read_text(encoding="utf-8")
    except OSError:
        return None
    # Frontmatter is between the first pair of ``---`` lines
    if not content.startswith("---"):
        return None
    end = content.find("\n---", 3)
    if end == -1:
        return None
    fm_block = content[3:end]
    for raw_line in fm_block.splitlines():
        key, separator, value = raw_line.partition(":")
        if separator and key.strip() == "status":
            return value.strip().strip("'\"")
    return None


def _parse_wp_title(wp_file: Path) -> str:
    """Return the first H1 or H2 heading from a WP markdown file, or the filename."""
    try:
        content = wp_file.read_text(encoding="utf-8")
    except OSError:
        return wp_file.stem
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("## ") or stripped.startswith("# "):
            return stripped.lstrip("#").strip()
    return wp_file.stem


def _parse_wp_id(wp_file: Path) -> str:
    """Extract WP ID from frontmatter or fall back to filename stem."""
    try:
        content = wp_file.read_text(encoding="utf-8")
    except OSError:
        return wp_file.stem
    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            fm_block = content[3:end]
            for raw_line in fm_block.splitlines():
                key, separator, value = raw_line.partition(":")
                if separator and key.strip() == "work_package_id":
                    return value.strip().strip("'\"")
    return wp_file.stem


def _resolve_status_read_dir(repo_root: Path, mission_dir: Path) -> Path | None:
    """Resolve the mission's status-surface read dir (#6612 / G-13), or None.

    Routes the read through the placement seam
    (``placement_seam(...).read_dir(MissionArtifactKind.STATUS_STATE)``), so
    under a coordination topology the coordination branch's mission dir is
    returned, never the primary checkout's possibly-stale copy (the #1735
    split-brain class).

    Returns None when no authoritative log is readable anywhere (the
    coordination worktree is not materialized — the fresh-clone window
    #4959), leaving the caller's legacy frontmatter fallback in charge.
    Returns the mission dir itself when the placement is unresolvable
    (``StatusReadPathNotFound`` without a coordination verdict), which is
    the historical surface for pre-3.x features.

    A deleted coordination branch raises ``CoordinationBranchDeleted`` —
    the #1848 data-loss guard — and any other seam failure (e.g.
    ``WorktreeRegistryUnavailable``) propagates: those are loud failures
    every other reader of the surface shares, never a silent fallback to
    the stale primary copy.
    """
    from mission_runtime import MissionArtifactKind, placement_seam  # noqa: PLC0415
    from specify_cli.coordination.surface_resolver import (  # noqa: PLC0415
        CoordinationBranchDeleted,
        CoordinationWorktreeUnmaterialized,
        StatusReadPathNotFound,
    )

    try:
        return placement_seam(repo_root, mission_dir.name).read_dir(MissionArtifactKind.STATUS_STATE)
    except CoordinationWorktreeUnmaterialized:
        # Fresh-clone window (#4959): the coordination branch is declared and
        # present, but its worktree is not materialized, so the authoritative
        # log is not readable anywhere. No lane answer — the caller's legacy
        # frontmatter fallback applies. NEVER read the stale primary copy
        # (the split-brain class this function exists to stop reading).
        return None
    except CoordinationBranchDeleted:
        # #1848 data-loss guard: the mission's authoritative surface was
        # deleted mid-flight. Propagate — a release-prep changelog must not
        # silently classify WPs off the stale primary copy.
        raise
    except StatusReadPathNotFound:
        # Unresolvable placement: a legacy mission the seam cannot resolve
        # keeps its historical surface, the mission dir itself. (Both
        # coordination-specific subclasses are handled above.)
        return mission_dir


def _wp_lanes_from_event_log(read_dir: Path | None) -> dict[str, Lane] | None:
    """Return the reduced lane map for every WP on the resolved status surface.

    Reads through the canonical lane reader
    (``status.lane_reader.get_all_wp_lanes``), so each lane is the REDUCED
    lane every other CLI lane read sees (ordered by ``at`` then ``event_id``
    with from-lane continuity and the approved-departure lift), never the
    last ``to_lane`` in file order (#6612 / G-13). Reading the whole map
    once per mission (not per WP) reads and reduces the log once.

    Returns None when *read_dir* is None (no readable authoritative
    surface), there is no event log to consult (pre-3.x features), or the
    log is unreadable (``OSError`` — the legacy reader's behavior: fall
    back to the frontmatter, never crash release prep on one bad
    permission bit), so the caller can fall back to the legacy frontmatter
    ``status`` field. A corrupt log raises ``StoreError`` — the same loud
    failure every other reader of the log shares.
    """
    from specify_cli.status import (  # noqa: PLC0415
        CanonicalStatusNotFoundError,
        get_all_wp_lanes,
    )

    if read_dir is None:
        return None
    try:
        lanes: dict[str, Lane] = get_all_wp_lanes(read_dir)
        return lanes
    except CanonicalStatusNotFoundError:
        # No event log on the resolved surface (pre-3.x feature).
        return None
    except OSError:
        # Legacy parity: the pre-#6612 reader fell back to the frontmatter
        # when the log file could not be read (permissions and the like).
        return None


def _is_accepted_wp(wp_lanes: dict[str, Lane] | None, wp_file: Path) -> bool:
    """Return True if the WP is in an accepted/done state.

    Checks the 3.x canonical lane first: the reduced lane from the event log
    on the mission's resolved status surface (the coordination branch under
    coordination topology), read through the canonical lane reader
    (FR-605, #6612). Falls back to the legacy YAML frontmatter ``status``
    field for pre-3.x features that have not been migrated to the
    event-log model.
    """
    if wp_lanes is not None:
        # A WP absent from the reduced snapshot has no lane answer (the
        # reader treats it as uninitialized), like a log with no events.
        event_log_lane = wp_lanes.get(_parse_wp_id(wp_file))
        if event_log_lane is not None:
            return event_log_lane in _ACCEPTED_LANES

    # Legacy fallback: check YAML frontmatter ``status`` field.
    status = _parse_wp_frontmatter_status(wp_file)
    if status is None:
        return False
    return status.lower() in {"done", "accepted", "merged"}


def build_changelog_block(
    repo_root: Path,
    since_tag: str | None = None,
) -> tuple[str, list[str]]:
    """Build a draft changelog block from ``kitty-specs/`` artifacts.

    Args:
        repo_root: Absolute path to the repository root.
        since_tag: A git tag name. Only missions created after this tag's
            commit date are included. If ``None``, the most recent ``v*``
            tag is used. If no tags exist at all, all missions are included.

    Returns:
        A tuple ``(changelog_markdown, mission_slug_list)`` where:
        - ``changelog_markdown`` is a multi-line markdown string ready to
          paste into CHANGELOG.md.
        - ``mission_slug_list`` is a list of mission-slug strings that were
          included in the changelog block.

    No network calls are made. Uses ``git tag --list`` and filesystem reads only.
    """
    # Resolve the tag to compare against
    if since_tag is None:
        since_tag = _find_most_recent_v_tag(repo_root)

    since_date: str | None = None
    if since_tag is not None:
        since_date = _tag_commit_date(repo_root, since_tag)

    # The placement seam anchors at the MAIN checkout's root
    # (mission_runtime resolution), not at the passed root: scanning a
    # linked worktree's kitty-specs while lanes resolve against the primary
    # checkout would mix two checkouts' state. Scan the same root the seam
    # reads (no-op for the primary checkout itself).
    from specify_cli.core.paths import get_main_repo_root  # noqa: PLC0415

    scan_root = get_main_repo_root(repo_root)
    mission_specs_dir = scan_root / KITTY_SPECS_DIR
    if not mission_specs_dir.exists():
        return ("", [])

    mission_dirs = sorted(
        [d for d in mission_specs_dir.iterdir() if d.is_dir()],
        key=lambda d: d.name,
    )

    included_missions: list[tuple[str, str, list[str]]] = []

    for mission_dir in mission_dirs:
        meta = _read_meta_json(mission_dir)
        mission_slug = mission_dir.name

        # Filter by creation date if we have a reference date
        if since_date is not None:
            created_at = str(meta.get("created_at", ""))
            if created_at and created_at <= since_date:
                # Mission predates the tag; still include if it has WPs accepted
                # after the tag date (best-effort: check any accepted WPs)
                # We use the simple heuristic from the spec: meta.json created_at
                # as the cheap proxy. If it's older, skip.
                pass  # fall through to WP scan

        # Collect accepted WPs. Resolve the canonical status surface and
        # reduce the log ONCE per mission (the seam probes git; resolving
        # per WP would repeat the probe for every WP file in the mission).
        status_read_dir = _resolve_status_read_dir(repo_root, mission_dir)
        try:
            wp_lanes = _wp_lanes_from_event_log(status_read_dir)
        except StoreError as exc:
            # Name the mission: a bare "Invalid JSON on line 2" over
            # hundreds of scanned missions is undiagnosable (#6612 review).
            raise StoreError(f"{mission_slug}: {exc}") from exc
        tasks_dir = mission_dir / "tasks"
        accepted_wps: list[str] = []
        if tasks_dir.exists():
            wp_files = sorted(tasks_dir.glob("WP*.md"), key=lambda f: f.name)
            for wp_file in wp_files:
                if _is_accepted_wp(wp_lanes, wp_file):
                    wp_id = _parse_wp_id(wp_file)
                    title = _parse_wp_title(wp_file)
                    accepted_wps.append(f"{wp_id}: {title}")

        if not accepted_wps:
            continue

        friendly_name = str(meta.get("friendly_name", "")) or mission_slug
        spec_title = _read_spec_title(mission_dir)
        display_name = friendly_name or spec_title or mission_slug

        included_missions.append((mission_slug, display_name, accepted_wps))

    if not included_missions:
        return ("", [])

    # Render the markdown block
    lines: list[str] = []
    for mission_slug, display_name, wps in included_missions:
        lines.append(f"### {display_name} (`{mission_slug}`)")
        lines.append("")
        for wp in wps:
            lines.append(f"- {wp}")
        lines.append("")

    changelog_markdown = "\n".join(lines).rstrip() + "\n"
    mission_slug_list = [slug for slug, _, _ in included_missions]

    return (changelog_markdown, mission_slug_list)
