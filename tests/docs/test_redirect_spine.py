"""Regen-reproduces-all guard for the redirect history, now held by the moves ledger.

The closed Common Docs Missions (``common-docs-structural-move-01KW3SBK``, then
``common-docs-convergence-01KZMTR9``) kept their redirects in Mission-scoped
``occurrence_map.yaml`` spines, re-collapsed by hand each time. Mission
``docsite-url-ledgers-01M6BRMR`` (#6927, absorbs #2358) moved that history into
the standing, append-only ledger ``site/moves.yaml``, and :func:`collapse` follows
its chains. The doc-kitty generator ``scripts/docs/site_redirects.py`` writes the
committed map ``site/legacy-redirects.json`` from it (#6933).

These tests keep the historical guarantees, derived from the ledger:

* :data:`FROZEN_PRIOR_REDIRECT_KEYS` is a frozen snapshot of the structural-move
  Mission's 149 redirect keys. Every one must still be derived, and still be a key
  of the committed doc-kitty map.
* The ``docs/archive`` -> ``docs/changelog`` twice-move stays composed: the
  ``1x``/``2x`` shadow URLs point at ``changelog/``, never at a dead ``archive/``.
* :func:`test_empty_ledger_regresses_coverage` proves the reproduce-all assertion
  has teeth.
* :func:`test_generator_default_is_the_standing_ledger` pins the closure of #2358:
  the generator's input is ``site/moves.yaml``, not a Mission's occurrence map.

Keys and values are in the ledger's legacy ``.html`` form without the leading slash,
as the closed Missions recorded them.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

import pytest

import scripts.docs.site_redirects as generator
from scripts.docs.moves_ledger import (
    DEFAULT_MOVES_LEDGER,
    Move,
    collapse,
    load_moves,
)

# Pure derivation, no git/subprocess. Fast developer shard.
pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMITTED_SITE_MAP = _REPO_ROOT / "site" / "legacy-redirects.json"


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
# redirect keys (the legacy site's map, retired in #6943). This is the historical
# coverage guarantee: every one of these baseline URLs must keep resolving to a LIVE
# final destination. Frozen (not read from a committed map) so the guard stays
# non-vacuous whatever the map's later shape.
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


def _derive(moves: Iterable[Move]) -> dict[str, str]:
    return {source.lstrip("/"): target.lstrip("/") for source, target in collapse(moves).items()}


def _derived() -> dict[str, str]:
    return _derive(load_moves(DEFAULT_MOVES_LEDGER))


# --- Frozen-snapshot integrity (anchors the non-vacuity of everything below) ---


def test_frozen_snapshot_is_the_closed_mission_149_key_census() -> None:
    assert len(FROZEN_PRIOR_REDIRECT_KEYS) == 149
    assert len(set(FROZEN_PRIOR_REDIRECT_KEYS)) == 149  # (no duplicates)


def test_every_prior_redirect_is_a_key_of_the_committed_site_map() -> None:
    committed = {key.lstrip("/") for key in json.loads(_COMMITTED_SITE_MAP.read_text(encoding="utf-8"))}
    assert committed, "site/legacy-redirects.json is empty — coverage denominator missing"
    missing = sorted(set(FROZEN_PRIOR_REDIRECT_KEYS) - committed)
    assert missing == [], f"prior redirects with no stub on the doc-kitty site: {missing[:10]}"


# --- The core guarantee: regen reproduces every prior baseline redirect ---


def test_regen_reproduces_every_prior_baseline_redirect() -> None:
    derived = _derived()
    missing = sorted(set(FROZEN_PRIOR_REDIRECT_KEYS) - set(derived))
    assert missing == [], f"{len(missing)} prior baseline redirect(s) dropped by the collapsed spine (coverage regression, NFR-010): {missing[:10]}"


def test_regen_is_a_strict_superset_adding_new_archive_entries() -> None:
    derived = _derived()
    # Strictly larger than the frozen prior set — later Missions added entries.
    assert len(derived) > len(FROZEN_PRIOR_REDIRECT_KEYS)
    for key in NEW_ARCHIVE_TO_CHANGELOG_KEYS:
        assert key in derived, f"new archive->changelog redirect missing: {key}"
        assert derived[key].startswith("changelog/"), f"{key} should redirect into changelog/, got {derived[key]}"


def test_archive_twice_move_is_composed_to_changelog() -> None:
    """The 1x/2x shadow redirects must point at their FINAL changelog home, never
    at the now-relocated (dead) ``archive/`` target."""
    derived = _derived()
    for key in COMPOSED_SHADOW_KEYS:
        assert key in derived
        assert derived[key].startswith("changelog/"), f"{key} still points at a dead archive/ target: {derived[key]}"
        assert not derived[key].startswith("archive/")


# --- Teeth: the reproduce-all assertion is not vacuous ---


def test_empty_ledger_regresses_coverage() -> None:
    """With no ledger entries, the frozen prior redirects are NOT reproduced — proving
    :func:`test_regen_reproduces_every_prior_baseline_redirect` can actually fail."""
    assert not set(FROZEN_PRIOR_REDIRECT_KEYS) <= set(_derive([]))


# --- #2358: the generator's input is the standing ledger, not a Mission's map ---


def test_generator_default_is_the_standing_ledger() -> None:
    assert DEFAULT_MOVES_LEDGER.parts[-2:] == ("site", "moves.yaml")
    module_paths = [value for value in vars(generator).values() if isinstance(value, Path)]
    assert DEFAULT_MOVES_LEDGER in module_paths
    assert not [value for value in module_paths if "kitty-specs" in value.parts]
    assert not hasattr(generator, "DEFAULT_OCCURRENCE_MAP")
