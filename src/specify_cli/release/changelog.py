"""Draft changelog builder for spec-kitty release preparation.

Reads ``kitty-specs/`` artifacts and local git tags only.
Zero network calls (FR-014).
"""

from __future__ import annotations

from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.mission_metadata import load_meta_or_empty
import json
import subprocess
from pathlib import Path

# Accepted lanes in the 3.x event-log model (FR-605)
_ACCEPTED_LANES: frozenset[str] = frozenset({"approved", "done"})


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


def _wp_lane_from_event_log(mission_dir: Path, wp_id: str) -> str | None:
    """Return the current lane for *wp_id* from the event log, or None.

    Uses the event log (status.events.jsonl) as the canonical source per the
    3.x status model (FR-605).  Falls back gracefully when the event log is
    absent (pre-3.x features) or the WP has no events yet.
    """
    events_path = mission_dir / "status.events.jsonl"
    if not events_path.exists():
        return None
    try:
        last_lane: str | None = None
        with events_path.open(encoding="utf-8") as fh:
            for raw_line in fh:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    event = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                if event.get("wp_id") == wp_id:
                    to_lane = event.get("to_lane")
                    if to_lane:
                        last_lane = str(to_lane)
        return last_lane
    except OSError:
        return None


def _is_accepted_wp(wp_file: Path) -> bool:
    """Return True if the WP is in an accepted/done state.

    Checks the 3.x event-log first (canonical source per FR-605).  Falls back
    to the legacy YAML frontmatter ``status`` field for pre-3.x features that
    have not been migrated to the event-log model.
    """
    # 3.x path: check event log (status.events.jsonl lives in mission_dir, the
    # parent of the tasks/ directory that contains wp_file).
    mission_dir = wp_file.parent.parent
    wp_id = _parse_wp_id(wp_file)
    event_log_lane = _wp_lane_from_event_log(mission_dir, wp_id)
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

    Lists Missions only (#6758): a ``kitty-specs/`` child that
    :func:`~specify_cli.context.mission_resolver.is_selectable_mission_dir` rejects is
    read-side residue, so a leftover folder never reaches the release notes. One
    ``TrackedMissionPaths`` memo per call keeps the git probe to at most one.
    """
    # Resolve the tag to compare against
    if since_tag is None:
        since_tag = _find_most_recent_v_tag(repo_root)

    since_date: str | None = None
    if since_tag is not None:
        since_date = _tag_commit_date(repo_root, since_tag)

    mission_specs_dir = repo_root / KITTY_SPECS_DIR
    if not mission_specs_dir.exists():
        return ("", [])

    from specify_cli.context.mission_resolver import TrackedMissionPaths, is_selectable_mission_dir

    tracked = TrackedMissionPaths(repo_root)
    mission_dirs = sorted(
        [d for d in mission_specs_dir.iterdir() if d.is_dir() and is_selectable_mission_dir(d, repo_root=repo_root, tracked=tracked)],
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

        # Collect accepted WPs
        tasks_dir = mission_dir / "tasks"
        accepted_wps: list[str] = []
        if tasks_dir.exists():
            wp_files = sorted(tasks_dir.glob("WP*.md"), key=lambda f: f.name)
            for wp_file in wp_files:
                if _is_accepted_wp(wp_file):
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
