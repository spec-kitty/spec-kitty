"""Regen-reproduces-all guard for the collapsed cumulative redirect spine.

WP03 / IC-02 / OB-1 of the Common Docs Convergence mission
(``common-docs-convergence-01KZMTR9``). This mission authors its
``occurrence_map.yaml`` as a **collapsed cumulative spine**: it carries the closed
``common-docs-structural-move-01KW3SBK`` mission's redirect entries forward so a
single ``regenerate-map`` run (the tool OVERWRITES the whole map from ONE
occurrence-map and ``_relocate`` is single-move — no additive merge, no transitive
closure) reproduces **every** prior baseline redirect PLUS the new ones, with **no
coverage regression** (NFR-010).

These tests are the "regen reproduces all 149" guard from plan OB-1. They are
deliberately **non-vacuous**:

* :data:`FROZEN_PRIOR_REDIRECT_KEYS` is a frozen snapshot of the closed mission's
  149 redirect keys — a historical guarantee that does **not** move even after
  WP13 (IC-11) regenerates the committed ``redirect_map.yaml`` to the collapsed
  163-entry shape. Every one of those baseline URLs MUST remain covered.
* :func:`test_empty_moves_regresses_coverage` proves the reproduce-all assertion
  has teeth: with an empty move spine the frozen keys are **not** reproduced.

The one intentional value shift is the **archive twice-move**: this mission
relocates ``docs/archive/`` -> ``docs/changelog`` (WP12), and the prior spine had
redirected the ``1x``/``2x`` shadow URLs *into* ``docs/archive``. Carrying those
verbatim would point 13 redirects at a now-dead ``archive/`` target, so the spine
collapses them one hop further to ``changelog/{1x,2x}`` (baseline path -> FINAL
dest). :func:`test_archive_twice_move_is_composed_to_changelog` locks that in.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.docs.redirect_stub_generator import (
    DEFAULT_BASELINE,
    DEFAULT_OCCURRENCE_MAP,
    MISSION_SLUG,
    Move,
    check_coverage,
    derive_redirect_map,
    generate,
    load_baseline,
    load_moves,
    load_redirect_map,
)

# Pure derivation + tmp_path staging — no git/subprocess. Fast developer shard.
pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMITTED_REDIRECT_MAP = _REPO_ROOT / "scripts" / "docs" / "redirect_map.yaml"

# This mission's slug — the tool default must point here (WP03 T009), never at the
# closed structural-move mission.
_THIS_MISSION_SLUG = "common-docs-convergence-01KZMTR9"

# The 14 currently-live ``archive/*`` baseline pages the ``docs/archive`` ->
# ``docs/changelog`` move (WP12) relocates — brand-new redirect keys this mission
# adds on top of the carried prior spine.
NEW_ARCHIVE_TO_CHANGELOG_KEYS = (
    "archive/1x/artifacts-and-commands.html",
    "archive/1x/branches-and-workspaces.html",
    "archive/1x/index.html",
    "archive/1x/orchestration-and-api.html",
    "archive/1x/workflow.html",
    "archive/2x/adr-coverage.html",
    "archive/2x/doctrine-and-charter.html",
    "archive/2x/glossary-system.html",
    "archive/2x/index.html",
    "archive/2x/model-discipline-routing.html",
    "archive/2x/model-to-task_type.html",
    "archive/2x/orchestration-and-api.html",
    "archive/2x/runtime-and-missions.html",
    "archive/index.html",
)

# The 13 prior redirect keys whose FINAL destination shifts from ``archive/`` to
# ``changelog/`` because this mission relocates ``docs/archive`` -> ``docs/changelog``
# (the twice-move composed in the spine, NOT a coverage regression).
COMPOSED_SHADOW_KEYS = (
    "1x/artifacts-and-commands.html",
    "1x/branches-and-workspaces.html",
    "1x/index.html",
    "1x/orchestration-and-api.html",
    "1x/workflow.html",
    "2x/adr-coverage.html",
    "2x/doctrine-and-charter.html",
    "2x/glossary-system.html",
    "2x/index.html",
    "2x/model-discipline-routing.html",
    "2x/model-to-task_type.html",
    "2x/orchestration-and-api.html",
    "2x/runtime-and-missions.html",
)

# Frozen snapshot of the closed common-docs-structural-move-01KW3SBK mission's 149
# redirect_map.yaml keys. This is the historical coverage guarantee: every one of
# these baseline URLs must keep resolving to a LIVE final destination after this
# mission's moves. Frozen (not read from the committed map) so the guard stays
# non-vacuous even after WP13 regenerates redirect_map.yaml to the 163-entry shape.
FROZEN_PRIOR_REDIRECT_KEYS: tuple[str, ...] = (
    "1x/artifacts-and-commands.html",
    "1x/branches-and-workspaces.html",
    "1x/index.html",
    "1x/orchestration-and-api.html",
    "1x/workflow.html",
    "2x/adr-coverage.html",
    "2x/doctrine-and-charter.html",
    "2x/glossary-system.html",
    "2x/index.html",
    "2x/model-discipline-routing.html",
    "2x/model-to-task_type.html",
    "2x/orchestration-and-api.html",
    "2x/runtime-and-missions.html",
    "3x/charter-overview.html",
    "3x/governance-files.html",
    "3x/index.html",
    "explanation/ai-agent-architecture.html",
    "explanation/branch-target-routing.html",
    "explanation/charter-synthesis-drg.html",
    "explanation/divio-documentation.html",
    "explanation/doctrine-relationships.html",
    "explanation/documentation-mission.html",
    "explanation/execution-lanes.html",
    "explanation/git-workflow.html",
    "explanation/git-worktrees.html",
    "explanation/governed-profile-invocation.html",
    "explanation/index.html",
    "explanation/kanban-workflow.html",
    "explanation/launch-readiness-future.html",
    "explanation/mission-system.html",
    "explanation/multi-agent-orchestration.html",
    "explanation/org-doctrine-layer.html",
    "explanation/pip-vs-pipx-vs-uv.html",
    "explanation/retrospective-learning-loop.html",
    "explanation/runtime-loop.html",
    "explanation/spec-driven-development.html",
    "guides/contract-pinning.html",
    "guides/contributing.html",
    "guides/coverage-signals.html",
    "guides/internal-hosted-readiness.html",
    "guides/local-overrides.html",
    "guides/manage-issue-tracker.html",
    "guides/pr-landing.html",
    "guides/red-main-and-release-readiness.html",
    "guides/review-gates.html",
    "guides/run-mutation-tests.html",
    "guides/testing-flakiness.html",
    "guides/testing-parallel.html",
    "guides/write-time-dependent-tests.html",
    "how-to/accept-and-merge.html",
    "how-to/adhoc-specialist-session.html",
    "how-to/build-custom-orchestrator.html",
    "how-to/create-an-org-doctrine-pack.html",
    "how-to/create-plan.html",
    "how-to/create-specification.html",
    "how-to/diagnose-installation.html",
    "how-to/generate-tasks.html",
    "how-to/gstack-glossary-observations.html",
    "how-to/handle-dependencies.html",
    "how-to/harnesses/amazon-q.html",
    "how-to/harnesses/antigravity.html",
    "how-to/harnesses/augment.html",
    "how-to/harnesses/claude-code.html",
    "how-to/harnesses/codex.html",
    "how-to/harnesses/copilot.html",
    "how-to/harnesses/cursor.html",
    "how-to/harnesses/gemini.html",
    "how-to/harnesses/kilocode.html",
    "how-to/harnesses/kiro.html",
    "how-to/harnesses/letta.html",
    "how-to/harnesses/opencode.html",
    "how-to/harnesses/pi-tui.html",
    "how-to/harnesses/qwen.html",
    "how-to/harnesses/roo.html",
    "how-to/harnesses/setup-lint-hooks.html",
    "how-to/harnesses/windsurf.html",
    "how-to/implement-work-package.html",
    "how-to/index.html",
    "how-to/install-and-upgrade.html",
    "how-to/install-claude-code-plugin.html",
    "how-to/install-linux.html",
    "how-to/install-macos.html",
    "how-to/install-spec-kitty.html",
    "how-to/install-windows.html",
    "how-to/internal-hosted-readiness.html",
    "how-to/keep-main-clean.html",
    "how-to/manage-agents.html",
    "how-to/manage-glossary.html",
    "how-to/merge-feature.html",
    "how-to/non-interactive-init.html",
    "how-to/parallel-development.html",
    "how-to/recover-from-implementation-crash.html",
    "how-to/recover-from-interrupted-merge.html",
    "how-to/review-artifacts-with-planbridge.html",
    "how-to/review-work-package.html",
    "how-to/run-an-autonomous-mission.html",
    "how-to/run-external-orchestrator.html",
    "how-to/run-governed-mission.html",
    "how-to/run-mutation-tests.html",
    "how-to/setup-codex-spec-kitty-launcher.html",
    "how-to/setup-governance.html",
    "how-to/switch-missions.html",
    "how-to/sync-workspaces.html",
    "how-to/synthesize-doctrine.html",
    "how-to/tool-surface-upgrade-and-repair.html",
    "how-to/troubleshoot-charter.html",
    "how-to/troubleshoot-merge.html",
    "how-to/uninstall.html",
    "how-to/upgrade-cli.html",
    "how-to/upgrade-project.html",
    "how-to/use-dashboard.html",
    "how-to/use-operation-history.html",
    "how-to/use-retrospective-learning.html",
    "how-to/use-wps-yaml-manifest.html",
    "how-to/worktrees-with-mcp-agents.html",
    "how-to/write-time-dependent-tests.html",
    "recovery/index.html",
    "recovery/logged-out-teamspace.html",
    "reference/README.html",
    "reference/agent-plan-artifacts.html",
    "reference/agent-subcommands.html",
    "reference/bulk-edit-gate.html",
    "reference/charter-commands.html",
    "reference/cli-commands.html",
    "reference/configuration.html",
    "reference/environment-variables.html",
    "reference/event-envelope.html",
    "reference/file-structure.html",
    "reference/finalize-tasks-internals.html",
    "reference/index.html",
    "reference/init-lifecycle.html",
    "reference/missions.html",
    "reference/orchestrator-api.html",
    "reference/profile-invocation.html",
    "reference/retrospective-schema.html",
    "reference/slash-commands.html",
    "reference/supported-agents.html",
    "reference/supported-harnesses.html",
    "reference/terminology.html",
    "reference/upgrade-lifecycle.html",
    "tutorials/charter-governed-workflow.html",
    "tutorials/claude-code-integration.html",
    "tutorials/claude-code-workflow.html",
    "tutorials/getting-started.html",
    "tutorials/index.html",
    "tutorials/missions-overview.html",
    "tutorials/multi-agent-workflow.html",
    "tutorials/orchestrator-quickstart.html",
    "tutorials/your-first-feature.html",
)


def _baseline() -> list[str]:
    _, paths = load_baseline(DEFAULT_BASELINE)
    return paths


def _mission_moves() -> list[Move]:
    return load_moves(DEFAULT_OCCURRENCE_MAP)


def _derived() -> dict[str, str]:
    """Regenerate the redirect map from the immutable baseline + THIS spine."""
    return derive_redirect_map(_baseline(), _mission_moves())


def _stage_full_site(tmp_path: Path, baseline: list[str], derived: dict[str, str]) -> Path:
    """Stage a ``_site`` where every redirect target and every un-redirected
    baseline page is a live file — the post-move published tree."""
    site = tmp_path / "_site"
    targets = set(derived.values())
    direct = set(baseline) - set(derived)
    for rel in targets | direct:
        page = site / rel
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text("<html></html>", encoding="utf-8")
    return site


# --- Frozen-snapshot integrity (anchors the non-vacuity of everything below) ---


def test_frozen_snapshot_is_the_closed_mission_149_key_census() -> None:
    assert len(FROZEN_PRIOR_REDIRECT_KEYS) == 149
    assert len(set(FROZEN_PRIOR_REDIRECT_KEYS)) == 149  # (no duplicates)
    # The frozen snapshot must match the closed mission's committed keys AT LEAST
    # as a subset of what is committed today (WP13 only ever grows the map).
    committed = load_redirect_map(_COMMITTED_REDIRECT_MAP)
    assert committed, "committed redirect_map.yaml is empty — coverage denominator missing"
    assert set(FROZEN_PRIOR_REDIRECT_KEYS) <= set(committed)


# --- The core guarantee: regen reproduces every prior baseline redirect ---


def test_regen_reproduces_every_prior_baseline_redirect() -> None:
    derived = _derived()
    missing = sorted(set(FROZEN_PRIOR_REDIRECT_KEYS) - set(derived))
    assert missing == [], (
        f"{len(missing)} prior baseline redirect(s) dropped by the collapsed spine "
        f"(coverage regression, NFR-010): {missing[:10]}"
    )


def test_regen_is_a_strict_superset_adding_new_archive_entries() -> None:
    derived = _derived()
    # Strictly larger than the frozen prior set — this mission adds entries.
    assert len(derived) > len(FROZEN_PRIOR_REDIRECT_KEYS)
    for key in NEW_ARCHIVE_TO_CHANGELOG_KEYS:
        assert key in derived, f"new archive->changelog redirect missing: {key}"
        assert derived[key].startswith("changelog/"), (
            f"{key} should redirect into changelog/, got {derived[key]}"
        )


def test_archive_twice_move_is_composed_to_changelog() -> None:
    """The 1x/2x shadow redirects must point at their FINAL changelog home, never
    at the now-relocated (dead) ``archive/`` target."""
    derived = _derived()
    for key in COMPOSED_SHADOW_KEYS:
        assert key in derived
        assert derived[key].startswith("changelog/"), (
            f"{key} still points at a dead archive/ target: {derived[key]}"
        )
        assert not derived[key].startswith("archive/")


def test_non_archive_prior_values_are_stable() -> None:
    """Every carried prior redirect whose target this mission does NOT relocate
    keeps its exact destination (only the archive twice-move shifts values)."""
    derived = _derived()
    committed = load_redirect_map(_COMMITTED_REDIRECT_MAP)
    for key in FROZEN_PRIOR_REDIRECT_KEYS:
        expected = committed.get(key)
        if expected is None or expected.startswith("archive/"):
            continue  # archive-origin keys are intentionally composed to changelog/
        assert derived[key] == expected, (
            f"carried redirect {key} drifted: expected {expected}, got {derived[key]}"
        )


# --- NFR-010: no dead redirect targets on the built site ---


def test_coverage_reports_zero_dead_targets(tmp_path: Path) -> None:
    baseline = _baseline()
    derived = _derived()
    site = _stage_full_site(tmp_path, baseline, derived)

    result = generate(derived, site)
    assert result.dead_targets == [], (
        f"redirect stubs point at missing targets (no-404 invariant): "
        f"{result.dead_targets[:10]}"
    )

    uncovered = check_coverage(baseline, derived, site)
    assert uncovered == [], f"uncovered baseline URLs (NFR-010): {uncovered[:10]}"


# --- Teeth: the reproduce-all assertion is not vacuous ---


def test_empty_moves_regresses_coverage() -> None:
    """With no move spine, the frozen prior redirects are NOT reproduced — proving
    :func:`test_regen_reproduces_every_prior_baseline_redirect` can actually fail."""
    empty = derive_redirect_map(_baseline(), [])
    assert not set(FROZEN_PRIOR_REDIRECT_KEYS) <= set(empty)


# --- WP03 T009: the tool default no longer points at the closed mission ---


def test_tool_default_targets_this_convergence_mission() -> None:
    assert MISSION_SLUG == _THIS_MISSION_SLUG
    assert MISSION_SLUG != "common-docs-structural-move-01KW3SBK"
    assert DEFAULT_OCCURRENCE_MAP.name == "occurrence_map.yaml"
    assert _THIS_MISSION_SLUG in str(DEFAULT_OCCURRENCE_MAP)
