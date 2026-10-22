from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    process_env = os.environ.copy()
    if env:
        process_env.update(env)
    result = subprocess.run(cmd, cwd=cwd, env=process_env, text=True, capture_output=True)
    result.check_returncode()
    return result


def run_python_script(
    script: Path, args: list[str], *, cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess:
    process_env = os.environ.copy()
    if env:
        process_env.update(env)
    command = [sys.executable, str(script), *args]
    return subprocess.run(command, cwd=cwd, env=process_env, text=True, capture_output=True)


def _canonical_lane(lane: str) -> str:
    return {"doing": "in_progress"}.get(lane, lane)


def _event_timestamp(timestamp: str) -> str:
    return timestamp[:-1] + "+00:00" if timestamp.endswith("Z") else timestamp


def _seed_canonical_wp_state(
    repo_root: Path,
    feature: str,
    wp_id: str,
    lane: str,
    *,
    actor: str,
    assignee: str,
    shell_pid: str,
    timestamp: str,
) -> None:
    from specify_cli.status.models import InnerStateChanged, Lane, StatusEvent, WPInnerStateDelta
    from specify_cli.status.reducer import materialize, reduce
    from specify_cli.status.store import (
        append_annotations_atomic_verified,
        read_event_stream,
        read_events,
    )
    from tests._support.status_seed import seed_status_event

    feature_dir = repo_root / "kitty-specs" / feature
    canonical_target = _canonical_lane(lane)
    existing_events = read_events(feature_dir)
    snapshot = reduce(existing_events)
    current_lane = snapshot.work_packages.get(wp_id, {}).get("lane")

    if current_lane != canonical_target:
        event = StatusEvent(
            event_id=f"TEST{wp_id}{len(existing_events) + 1:020d}",
            mission_slug=feature,
            wp_id=wp_id,
            # T028: use "genesis" as the default (not "planned") so an unseeded WP
            # gets a legal genesis->target event instead of an illegal planned->planned.
            from_lane=Lane(current_lane or "genesis"),
            to_lane=Lane(canonical_target),
            at=_event_timestamp(timestamp),
            actor=actor,
            force=True,
            execution_mode="direct_repo",
            reason="test fixture bootstrap",
        )
        seed_status_event(feature_dir, event)

    event_stream = read_event_stream(feature_dir)
    runtime_state = reduce(
        event_stream.transitions,
        event_stream.annotations,
    ).work_packages.get(wp_id, {})
    shell_pid_value = int(shell_pid) if shell_pid else None
    if (
        runtime_state.get("agent") != actor
        or runtime_state.get("assignee") != assignee
        or runtime_state.get("shell_pid") != shell_pid_value
    ):
        append_annotations_atomic_verified(
            feature_dir,
            [
                InnerStateChanged(
                    event_id=(
                        f"01H{len(event_stream.transitions) + len(event_stream.annotations) + 1:023d}"
                    ),
                    wp_id=wp_id,
                    at=_event_timestamp(timestamp),
                    actor="test-fixture",
                    delta=WPInnerStateDelta(
                        agent=actor,
                        assignee=assignee,
                        shell_pid=shell_pid_value,
                        shell_pid_created_at=_event_timestamp(timestamp),
                    ),
                )
            ],
        )
    materialize(feature_dir)


def write_wp(
    repo_root: Path,
    feature: str,
    lane: str,
    wp_id: str,
    *,
    agent: str = "system",
    assignee: str = "Owner",
    shell_pid: str = "1234",
    note: str = "Created",
    timestamp: str = "2025-01-01T00:00:00Z",
    legacy: bool = False,
    seed_canonical: bool = True,
) -> Path:
    """Create a work package file for testing.

    Args:
        legacy: If True, create in subdirectory (tasks/planned/WP01.md).
                If False (default), create in flat structure (tasks/WP01.md).
    """
    from specify_cli.task_utils.support import (
        append_activity_log,
        build_document,
        split_frontmatter,
    )

    if legacy:
        # Legacy format: tasks/<lane>/WP01.md
        lane_dir = repo_root / "kitty-specs" / feature / "tasks" / lane
        lane_dir.mkdir(parents=True, exist_ok=True)
        path = lane_dir / f"{wp_id}.md"
    else:
        # New format: flat tasks/WP01.md with lane in frontmatter
        tasks_dir = repo_root / "kitty-specs" / feature / "tasks"
        tasks_dir.mkdir(parents=True, exist_ok=True)
        path = tasks_dir / f"{wp_id}.md"

    frontmatter_lines = [f'work_package_id: "{wp_id}"']
    if legacy:
        frontmatter_lines.append(f'lane: "{lane}"')
    frontmatter_lines.extend(
        [
            f'agent: "{agent}"',
            f'assignee: "{assignee}"',
            f'shell_pid: "{shell_pid}"',
            "subtasks: []",
        ]
    )
    frontmatter = "\n".join(frontmatter_lines)
    document = build_document(frontmatter, "", "\n")
    path.write_text(document, encoding="utf-8")

    front, body, padding = split_frontmatter(path.read_text(encoding="utf-8"))
    updated_body = append_activity_log(
        body,
        f"- {timestamp} – {agent} – shell_pid={shell_pid} – {note}",
    )
    # FR-006 (WP08): ``set_scalar`` is retired for append-on-miss and only
    # updates existing keys. ``lane``/``agent``/``assignee``/``shell_pid`` are
    # already composed into ``frontmatter`` above at their final values, so the
    # former ``set_scalar`` re-writes were byte-neutral no-ops; drop them and
    # rely solely on ``build_document`` (a supported writer).
    path.write_text(build_document(front, updated_body, padding), encoding="utf-8")
    if seed_canonical and not legacy:
        _seed_canonical_wp_state(
            repo_root,
            feature,
            wp_id,
            lane,
            actor=agent,
            assignee=assignee,
            shell_pid=shell_pid,
            timestamp=timestamp,
        )
    return path
