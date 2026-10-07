"""Pre-accept Missions pass the cut-over guard (#5835).

A Mission driven only by canonical commands carries event-log runtime evidence
from its first claim, while the ``status_phase`` stamp is written only at
accept/consolidate (by design, #2917). The shared cut-over predicate exempts
such a pre-accept Mission, and stays strict for terminal evidence and legacy
frontmatter runtime.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.cli.commands.cutover_guard import evaluate_touched_missions
from specify_cli.status.cutover_eligibility import PRE_ACCEPT_EXEMPT_NOTE, is_cut_over
from specify_cli.status.emit import build_claim_policy_metadata
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event

pytestmark = pytest.mark.fast

_SLUG = "pre-accept-demo-01KZPREACC"
_MISSION_ID = "01KZPREACCEPT0000000000001"

# Verbatim from packs/built-in/missions/software-dev/templates/task-prompt-template.md:
# the shipped WP template carries EMPTY claim fields (agent/assignee/shell_pid).
_TEMPLATE_WP_FRONTMATTER = """---
work_package_id: "WP01"
subtasks:
  - "T001"
title: "Demo"
task_type: "implement"
phase: "Phase 1"
execution_mode: "code_change"
owned_files:
  - "src/demo.py"
authoritative_surface: "src/"
create_intent: []
agent_profile: ""
role: ""
agent: ""
model: ""
assignee: ""
shell_pid: ""
history:
  - at: "2026-01-01T00:00:00Z"
    actor: "system"
    action: "Prompt generated via /spec-kitty.tasks"
---

# Work Package Prompt: WP01
"""


def _event(
    event_id: str,
    from_lane: Lane,
    to_lane: Lane,
    *,
    reason: str | None = None,
    policy_metadata: dict[str, object] | None = None,
) -> StatusEvent:
    return StatusEvent(
        event_id=event_id,
        mission_slug=_SLUG,
        mission_id=_MISSION_ID,
        wp_id="WP01",
        from_lane=from_lane,
        to_lane=to_lane,
        at="2026-01-01T00:00:00+00:00",
        actor="claude",
        force=False,
        execution_mode="worktree",
        reason=reason,
        policy_metadata=policy_metadata,
    )


def build_pre_accept_mission(repo_root: Path) -> Path:
    """Build a claimed, never-accepted, natively-born Mission under *repo_root*."""
    mission_dir = repo_root / "kitty-specs" / _SLUG
    (mission_dir / "tasks").mkdir(parents=True)
    (mission_dir / "meta.json").write_text(
        json.dumps({"mission_id": _MISSION_ID, "mission_slug": _SLUG, "mission_type": "software-dev"}),
        encoding="utf-8",
    )
    (mission_dir / "tasks" / "WP01-demo.md").write_text(_TEMPLATE_WP_FRONTMATTER, encoding="utf-8")
    (mission_dir / "tasks.md").write_text(
        "# Tasks\n\n## WP01 Demo\n\n- [x] T001 Authoring reference row\n",
        encoding="utf-8",
    )
    append_event(mission_dir, _event("01KZPREACC00000000000000A1", Lane.GENESIS, Lane.PLANNED, reason="seed"))
    append_event(
        mission_dir,
        _event(
            "01KZPREACC00000000000000A2",
            Lane.PLANNED,
            Lane.CLAIMED,
            policy_metadata=build_claim_policy_metadata(
                shell_pid=1234,
                shell_pid_created_at="2026-01-01T00:00:30+00:00",
                agent="claude",
            ),
        ),
    )
    return mission_dir


def test_claimed_pre_accept_mission_passes_guard(tmp_path: Path) -> None:
    """#5835: a claimed Mission with no stamp and nothing legacy passes, with the note."""
    mission_dir = build_pre_accept_mission(tmp_path)
    changed = [f"kitty-specs/{_SLUG}/tasks/WP01-demo.md"]

    verdict = evaluate_touched_missions(tmp_path, changed)

    assert verdict.passed is True, [f.reasons for f in verdict.failures]
    assert is_cut_over(mission_dir).reasons == (PRE_ACCEPT_EXEMPT_NOTE,)
