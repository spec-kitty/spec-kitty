"""Section-scoped guards for the built-in software-dev mission-step prompts (WP16, FR-022).

Red-first independent test for the WP16 cleanup of the shipped software-dev
prompts. Each assertion pins one corrected item from the mission's plan
amendments C3/C4/C5/C10 and the R7 inventory, so a regression that reintroduces
a refusal-triggering instruction or a retired path fails here.

Edits go to ``packs/built-in/missions/mission-steps/software-dev/<step>/prompt.md``
(the canonical source; generated agent copies are never edited — C-003). These
tests read those sources directly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_STEPS_ROOT = _REPO_ROOT / "packs" / "built-in" / "missions" / "mission-steps" / "software-dev"

# The nine software-dev prompts C3 covers. Seven carry the one-line
# "pass --mission to every spec-kitty command" boilerplate that is reworded;
# plan and specify instead use a "Mission Handle Rule" section that already
# scopes --mission correctly, so they only need to stay clean of the
# over-broad wording.
_C3_BOILERPLATE_PROMPTS = (
    "analyze",
    "accept",
    "implement",
    "review",
    "tasks",
    "tasks-outline",
    "tasks-packages",
)
_C3_ALL_PROMPTS = _C3_BOILERPLATE_PROMPTS + ("plan", "specify")

_C3_WORDING = "every command that accepts `--mission`"


def _prompt(step: str) -> str:
    return (_STEPS_ROOT / step / "prompt.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# C3: the --mission boilerplate names "every command that accepts --mission"
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("step", _C3_BOILERPLATE_PROMPTS)
def test_mission_boilerplate_reworded(step: str) -> None:
    content = _prompt(step)
    assert _C3_WORDING in content, f"{step}/prompt.md must reword the --mission boilerplate to '{_C3_WORDING}' (C3)."
    # test_has_feature_flag_guidance stays green: the reworded line keeps --mission.
    assert "--mission" in content


@pytest.mark.parametrize("step", _C3_ALL_PROMPTS)
def test_mission_boilerplate_drops_every_spec_kitty_command(step: str) -> None:
    content = _prompt(step)
    assert "to every spec-kitty command" not in content, (
        f"{step}/prompt.md still tells the agent to pass --mission 'to every spec-kitty command'; many spec-kitty commands reject --mission (C3)."
    )


# ---------------------------------------------------------------------------
# C4 / R7 accept: repository root checkout resolves correctly from a worktree
# ---------------------------------------------------------------------------


def test_accept_resolves_repo_root_checkout_not_worktree_root() -> None:
    content = _prompt("accept")
    assert "git rev-parse --show-toplevel" not in content, (
        "accept/prompt.md must not resolve the repository root checkout with "
        "`git rev-parse --show-toplevel` — inside a worktree that returns the "
        "worktree root (R7 accept bug)."
    )
    assert "--git-common-dir" in content, (
        "accept/prompt.md must resolve the repository root checkout from the git common directory so it is correct from inside a worktree."
    )


def test_accept_does_not_claim_next_advances_to_consolidate() -> None:
    content = _prompt("accept")
    assert "will advance to consolidate" not in content, (
        "accept/prompt.md must not claim `spec-kitty next` advances to a consolidate step — there is no consolidate step (C4)."
    )
    assert "spec-kitty consolidate --mission" in content


# ---------------------------------------------------------------------------
# C5 / FR-022 implement: analysis-report gate named, no retired paths
# ---------------------------------------------------------------------------


def test_implement_names_analysis_report_gate() -> None:
    content = _prompt("implement")
    assert "analysis-report.md" in content, (
        "implement/prompt.md must name the analysis-report gate so the agent knows implement refuses without a current analysis report (FR-022)."
    )
    assert "analysis_report_required" in content


def test_implement_has_no_retired_command_templates_path() -> None:
    content = _prompt("implement")
    assert "command-templates/" not in content, "implement/prompt.md must not grep the retired `src/specify_cli/missions/*/command-templates/` path (C5 / R7)."
    assert "src/specify_cli/missions" not in content


def test_implement_lint_check_is_project_command_not_hardcoded_venv_ruff() -> None:
    content = _prompt("implement")
    assert ".venv/bin/ruff" not in content, (
        "implement/prompt.md must not mandate a repo-local `.venv/bin/ruff` invocation; it names the project's own lint and format commands (C5)."
    )


def test_implement_merge_base_uses_target_branch_not_main() -> None:
    content = _prompt("implement")
    assert "git merge-base HEAD main" not in content, (
        "implement/prompt.md must compute the merge-base against the mission's target branch, not a hardcoded `main` (C5)."
    )


def test_implement_points_at_agent_config_list_not_hardcoded_agent_dirs() -> None:
    content = _prompt("implement")
    assert "spec-kitty agent config list" in content, (
        "implement/prompt.md must point at `spec-kitty agent config list` instead of a hardcoded agent-directory grep list (C5)."
    )


# ---------------------------------------------------------------------------
# C10 / FR-022 analyze: staleness rule + recovery recipe outside the checkout
# ---------------------------------------------------------------------------


def test_analyze_states_staleness_rule() -> None:
    content = _prompt("analyze").lower()
    assert "stale" in content, "analyze/prompt.md must state the staleness rule."
    # The report goes stale when a planning input changes after it is recorded.
    assert "charter" in content
    for token in ("spec", "plan", "tasks"):
        assert token in content


def test_analyze_recovery_recipe_writes_outside_the_checkout() -> None:
    content = _prompt("analyze")
    assert "DIRTY_WORKTREE" in content, (
        "analyze/prompt.md must warn that writing the report into the checkout makes the worktree dirty and record-analysis refuses with DIRTY_WORKTREE (C10)."
    )
    assert "outside the repository checkout" in content, "analyze/prompt.md recovery recipe must write the report to a path outside the repository checkout (C10)."
    # The buggy recovery form passed the in-checkout analysis-report.md path.
    assert "--input-file analysis-report.md" not in content, (
        "analyze/prompt.md must not recover by passing the in-checkout `analysis-report.md` to record-analysis (that trips DIRTY_WORKTREE)."
    )


def test_analyze_keeps_record_analysis_command() -> None:
    content = _prompt("analyze")
    assert "agent mission record-analysis" in content


# ---------------------------------------------------------------------------
# C4: --mission on the next / move-task hand-off lines
# ---------------------------------------------------------------------------


def test_review_next_step_carries_mission() -> None:
    content = _prompt("review")
    assert "spec-kitty next --agent <name> --mission" in content, "review/prompt.md Next step must carry --mission (C4)."


def test_review_drops_hosted_sync_wording() -> None:
    content = _prompt("review")
    assert "propagates to the team" not in content, "review/prompt.md must drop the hosted-sync 'never propagates to the team' wording (C4)."


def test_implement_next_step_carries_mission() -> None:
    content = _prompt("implement")
    assert "spec-kitty next --agent <name> --mission" in content, "implement/prompt.md Next step must carry --mission (C4)."


def test_specify_handoff_names_analyze_before_implement() -> None:
    content = _prompt("specify")
    assert "analyze" in content.lower(), "specify/prompt.md hand-off must say that after tasks `next` issues the analyze step before implement (C4)."


# ---------------------------------------------------------------------------
# C-003: no concrete Mission slug provenance in the touched prompts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("step", ("plan", "specify"))
def test_no_concrete_mission_slug_citation(step: str) -> None:
    content = _prompt(step)
    assert "charter-e2e-827-followups-01KQAJA0" not in content, (
        f"{step}/prompt.md must not cite the concrete internal Mission slug `charter-e2e-827-followups-01KQAJA0` (C-003)."
    )
