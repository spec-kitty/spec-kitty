"""The shipped approve guidance names the approver's identity (FR-011, #7569).

Since #7569 an approval records one reviewer of record: the asserted ``--agent``, else the
review claimant, never the git user. Guidance that prints an approve command without
``--agent`` teaches the shape that is refused or recorded as a placeholder, so both
surfaces that ship that command are pinned here:

* the ``spec-kitty next`` merged-Mission straggler hint
  (``runtime_bridge_decision_mapping``), in advancing and query mode;
* the core ``spk-run-verdict-capture`` skill.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.status.models import Lane
from tests.runtime.next.test_merged_mission_terminal import _build_repo, _mission_context_for_coord

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SKILL = Path(__file__).resolve().parents[3] / "src" / "charter" / "offering" / "skills" / "spk-run-verdict-capture" / "SKILL.md"


def _approve_hint(mission_slug: str) -> str:
    return f"--to approved --mission {mission_slug} --agent"


def test_advancing_straggler_hint_names_the_approver(tmp_path: Path) -> None:
    from runtime.next.runtime_bridge import decide_next_via_runtime

    mission_slug = "042-approve-hint-identity"
    repo_root, primary_dir, coord_dir = _build_repo(tmp_path, mission_slug, mission_number=9, wps={"WP01": Lane.DONE, "WP02": Lane.PLANNED})

    with (
        patch("runtime.next.runtime_bridge_identity._primary_runtime_feature_dir", return_value=primary_dir),
        patch("runtime.next.runtime_bridge_identity._resolve_runtime_feature_dir", return_value=coord_dir),
    ):
        decision = decide_next_via_runtime("claude", mission_slug, "success", repo_root)

    assert decision.kind == "blocked"
    assert _approve_hint(mission_slug) in (decision.reason or ""), decision.reason


def test_query_straggler_hint_names_the_approver(tmp_path: Path) -> None:
    from runtime.next.runtime_bridge import query_current_state

    mission_slug = "042-approve-hint-identity-query"
    repo_root, primary_dir, coord_dir = _build_repo(tmp_path, mission_slug, mission_number=9, wps={"WP01": Lane.DONE, "WP02": Lane.PLANNED})

    with (
        patch("runtime.next.runtime_bridge_identity._primary_runtime_feature_dir", return_value=primary_dir),
        patch("mission_runtime.mission_context_for", return_value=_mission_context_for_coord(mission_slug, coord_dir)),
    ):
        decision = query_current_state("claude", mission_slug, repo_root)

    assert decision.mission_state == "blocked"
    assert _approve_hint(mission_slug) in (decision.reason or ""), decision.reason


def test_verdict_capture_skill_approve_line_names_the_approver() -> None:
    text = _SKILL.read_text(encoding="utf-8")
    approve_lines = [line for line in text.splitlines() if "move-task" in line and "--to approved" in line]

    assert approve_lines, "the skill must show the approve command"
    assert all("--agent" in line for line in approve_lines), approve_lines


def test_verdict_capture_skill_names_the_claimant_rule_and_codes() -> None:
    text = " ".join(_SKILL.read_text(encoding="utf-8").split())

    assert "never taken from git" in text
    for code in ("APPROVER_NOT_CLAIMANT", "REVIEW_CYCLE_CITATION_MISSING", "REVIEW_CYCLE_NOT_ADOPTABLE"):
        assert code in text, code
