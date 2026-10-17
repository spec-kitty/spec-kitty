"""A WP-driven custom family keeps the WP-advance guard at implement/review (FR-003/FR-004).

Before the fix the composed guard set ``wp_advance_ready`` only for the literal
``software-dev`` family, and the unregistered custom family degraded to a neutral
empty result, so the guard was silently skipped with work packages pending.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.runtime._next_mission_scaffold import (
    CUSTOM_ANALYZE_FAMILY,
    scaffold_custom_analyze_mission,
    scaffold_software_dev,
)

pytestmark = [pytest.mark.git_repo]

_PENDING = "Not all work packages have required status (for_review, approved, or done)"
_PLAN_FAMILY = "acme-plan"
_PLAN_STEPS = ("specify", "research", "plan", "review")


def _guard(repo: Path, slug: str, family: str, action: str) -> list[str]:
    from runtime.next.runtime_bridge import get_or_start_run
    from runtime.next.runtime_bridge_composition import _check_composed_action_guard

    get_or_start_run(slug, repo, family)
    return _check_composed_action_guard(action, repo / "kitty-specs" / slug, mission=family, repo_root=repo)


def test_wp_driven_custom_family_holds_at_implement_with_a_pending_wp(tmp_path: Path) -> None:
    slug = scaffold_custom_analyze_mission(tmp_path)

    assert _guard(tmp_path, slug, CUSTOM_ANALYZE_FAMILY, "implement") == [_PENDING]


def test_software_dev_still_holds_at_implement_with_a_pending_wp(tmp_path: Path) -> None:
    scaffold_software_dev(tmp_path, "042-ctl", with_spec=True, with_plan=True, with_tasks_md=True, wps={"WP01": "planned"})

    assert _guard(tmp_path, "042-ctl", "software-dev", "implement") == [_PENDING]


def test_non_wp_driven_family_is_unaffected(tmp_path: Path) -> None:
    from runtime.next.runtime_bridge import get_or_start_run
    from runtime.next.runtime_bridge_io import mission_declares_wp_iteration

    slug = scaffold_custom_analyze_mission(tmp_path, family=_PLAN_FAMILY, steps=_PLAN_STEPS)

    run_ref = get_or_start_run(slug, tmp_path, _PLAN_FAMILY)
    assert mission_declares_wp_iteration(Path(run_ref.run_dir)) is False
    assert _guard(tmp_path, slug, _PLAN_FAMILY, "review") == []
