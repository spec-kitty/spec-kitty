"""Contract example round-trip CI gate (Slice F WP03, FR-140 + FR-141).

Walker: discovers every ``kitty-specs/*/contracts/*.md`` file, extracts
fenced ``yaml`` codeblocks that carry the frontmatter convention introduced
by Slice F, and asserts the expected parse outcome against the declared
Pydantic model.

Frontmatter convention (per ``contract-round-trip-frontmatter.md``)
--------------------------------------------------------------------
Every parseable YAML codeblock in a contracts/ file that should be exercised
by this gate MUST have the first two non-blank comment lines inside the
codeblock be::

    # pydantic_model: <module.dotted.path.ClassName>
    # expect: valid | invalid

Optionally::

    # expect_message: <substring>   (only meaningful with ``expect: invalid``)

Block-level discovery (non-legacy contracts)
--------------------------------------------
For a contract NOT in the legacy allowlist, discovery is **block-level**: EVERY
parseable YAML codeblock must be either tagged with ``# pydantic_model:``
frontmatter (executed against the model) OR carry an explicit non-executable
marker::

    # round-trip: skip: <reason>

A block carrying neither is a gate failure for that specific block — a tagged
sibling no longer masks a forgotten tag. The ``# round-trip: skip:`` marker is
the explicit home for illustrations, shape sketches, CI-wiring snippets, and
non-Pydantic operator config (e.g. a ``.kittify/config.yaml`` block whose
resolver reads raw YAML rather than a Pydantic model). The reason is mandatory.
This is a permanent, per-block exemption taxonomy — distinct from the legacy
burn-down allowlist below.

Legacy allowlist (FR-141)
-------------------------
Contracts from missions **predating** this convention are tracked file-level in
``_LEGACY_CONTRACT_ALLOWLIST``.  Files in the allowlist do not fail when their
YAML codeblocks lack frontmatter, and keep file-level leniency (a tagged block
does not force the rest to be tagged); a backfill nudge is instead recorded via
the built-in ``record_property`` fixture (surfaced in the JUnit/report output,
not the ``warnings`` channel — NFR-006) by
``test_legacy_contract_backfill_nudges_are_reported``. The
allowlist count is pinned in
``tests/architectural/_baselines.yaml::test_example_round_trip.legacy_contract_allowlist``
and MUST shrink over time as legacy contracts are backfilled (C-004 burn-down).
Post-convention files that are simply non-executable belong in a
``# round-trip: skip:`` marker, NOT this allowlist.

ATDD anchors
------------
* AC-10: ``test_contract_example_round_trip[*]`` (parametrised over every
  tagged codeblock)
* FR-140: walker discovers and exercises every tagged codeblock
* FR-141: legacy allowlist + baseline integration
"""

from __future__ import annotations

import importlib
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pydantic
import pytest
import yaml

from tests.contract import _module_relocations
from tests.contract._module_relocations import (
    HISTORICAL_TO_CANONICAL,
    import_contract_module,
)

pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]

# Type of the built-in ``record_property`` fixture: records a (name, value)
# pair into the JUnit/report output. Used to route the report-only legacy
# backfill nudge off the ``warnings`` channel (NFR-006) while preserving the
# signal — consistent with this repo's convention for report-only
# diagnostics (see ``test_migration_chain_integrity.py``,
# ``test_ci_collection_completeness.py``, ``test_retired_contracts_absent.py``).
RecordPropertyFn = Callable[[str, object], None]

# ---------------------------------------------------------------------------
# Repo root (resolve relative to this file: tests/contract/ -> tests/ -> root)
# ---------------------------------------------------------------------------
_REPO_ROOT: Path = Path(__file__).resolve().parents[2]
_KITTY_SPECS_ROOT: Path = _REPO_ROOT / "kitty-specs"

# ---------------------------------------------------------------------------
# This mission's slug — used to distinguish legacy from Slice F contracts
# ---------------------------------------------------------------------------
_SLICE_F_MISSION_SLUG: str = "slice-f-multi-context-extensibility-01KRX5C8"

# ---------------------------------------------------------------------------
# Legacy contract allowlist (FR-141)
# ---------------------------------------------------------------------------
# Contracts from missions predating the frontmatter convention.  Files in
# this set emit a warning (not a failure) when their YAML codeblocks lack
# ``# pydantic_model:`` frontmatter.  The count is pinned in
# ``tests/architectural/_baselines.yaml``.
#
# Populated by the WP03 discovery sweep.  Each entry is the path relative to
# the repo root (e.g. ``kitty-specs/002-lightweight-pypi-release/contracts/...``).
# ---------------------------------------------------------------------------
_LEGACY_CONTRACT_ALLOWLIST: frozenset[str] = frozenset(
    {
        "kitty-specs/002-lightweight-pypi-release/contracts/release-validation-cli.md",
        "kitty-specs/003-auto-protect-agent/contracts/test-contract.md",
        "kitty-specs/032-identity-aware-cli-event-sync/contracts/event-envelope.md",
        "kitty-specs/033-github-observability-event-metadata/contracts/event-envelope.md",
        "kitty-specs/039-cli-2x-readiness/contracts/lane-mapping.md",
        "kitty-specs/041-enable-plan-mission-runtime-support/contracts/command-template.md",
        "kitty-specs/041-mission-glossary-semantic-integrity/contracts/events.md",
        "kitty-specs/041-mission-glossary-semantic-integrity/contracts/middleware.md",
        "kitty-specs/047-namespace-aware-artifact-body-sync/contracts/push-content-api.md",
        "kitty-specs/048-tracker-publish-resource-routing/contracts/tracker-snapshot-publish.md",
        "kitty-specs/054-constitution-interview-compiler-and-bootstrap/contracts/constitution-cli-contract.md",
        "kitty-specs/058-mission-template-repository-refactor/contracts/mission-template-repository.md",
        "kitty-specs/062-tracker-binding-context-discovery/contracts/bind-confirm.md",
        "kitty-specs/062-tracker-binding-context-discovery/contracts/bind-resolve.md",
        "kitty-specs/062-tracker-binding-context-discovery/contracts/bind-validate.md",
        "kitty-specs/062-tracker-binding-context-discovery/contracts/existing-endpoint-evolution.md",
        "kitty-specs/062-tracker-binding-context-discovery/contracts/resources.md",
        "kitty-specs/064-complete-mission-identity-cutover/contracts/body-sync.md",
        "kitty-specs/064-complete-mission-identity-cutover/contracts/event-envelope.md",
        "kitty-specs/064-complete-mission-identity-cutover/contracts/orchestrator-api.md",
        "kitty-specs/064-complete-mission-identity-cutover/contracts/tracker-bind.md",
        "kitty-specs/068-post-merge-reliability-and-release-hardening/contracts/diff_coverage_policy.md",
        "kitty-specs/068-post-merge-reliability-and-release-hardening/contracts/merge_strategy.md",
        "kitty-specs/068-post-merge-reliability-and-release-hardening/contracts/recovery_extension.md",
        "kitty-specs/068-post-merge-reliability-and-release-hardening/contracts/release_prep.md",
        "kitty-specs/068-post-merge-reliability-and-release-hardening/contracts/stale_assertions.md",
        "kitty-specs/077-mission-terminology-cleanup/contracts/deprecation_warning.md",
        "kitty-specs/077-mission-terminology-cleanup/contracts/grep_guards.md",
        "kitty-specs/077-mission-terminology-cleanup/contracts/selector_resolver.md",
        "kitty-specs/078-planning-artifact-and-query-consistency/contracts/planning-artifact-lifecycle.md",
        "kitty-specs/078-planning-artifact-and-query-consistency/contracts/workspace-resolution.md",
        "kitty-specs/079-post-555-release-hardening/contracts/cli-contracts.md",
        "kitty-specs/079-post-555-release-hardening/contracts/file-format-contracts.md",
        "kitty-specs/079-post-555-release-hardening/contracts/test-contracts.md",
        "kitty-specs/080-browser-mediated-oauth-cli-auth/contracts/api-logout-endpoint.md",
        "kitty-specs/080-browser-mediated-oauth-cli-auth/contracts/api-ws-token-endpoint.md",
        "kitty-specs/080-browser-mediated-oauth-cli-auth/contracts/error-responses.md",
        "kitty-specs/080-browser-mediated-oauth-cli-auth/contracts/oauth-authorize-endpoint.md",
        "kitty-specs/080-browser-mediated-oauth-cli-auth/contracts/oauth-device-endpoint.md",
        "kitty-specs/080-browser-mediated-oauth-cli-auth/contracts/oauth-token-endpoint.md",
        "kitty-specs/080-browser-mediated-oauth-cli-auth/contracts/saas-amendment-refresh-ttl.md",
        "kitty-specs/080-wpstate-lane-consumer-strangler-fig-phase-2/contracts/consumer-interfaces.md",
        "kitty-specs/082-stealth-gated-saas-sync-hardening/contracts/background_daemon_policy.md",
        "kitty-specs/082-stealth-gated-saas-sync-hardening/contracts/hosted_readiness.md",
        "kitty-specs/082-stealth-gated-saas-sync-hardening/contracts/saas_rollout.md",
        "kitty-specs/083-agent-skills-codex-vibe/contracts/skill-renderer.contract.md",
        "kitty-specs/auth-local-trust-and-multi-process-hardening-01KQW587/contracts/ble001-guardrail.md",
        "kitty-specs/auth-local-trust-and-multi-process-hardening-01KQW587/contracts/diagnostic-classification.md",
        "kitty-specs/auth-local-trust-and-multi-process-hardening-01KQW587/contracts/refresh-lock-hermeticity.md",
        "kitty-specs/auth-local-trust-and-multi-process-hardening-01KQW587/contracts/session-hot-path.md",
        "kitty-specs/auth-tranche-2-5-cli-contract-consumption-01KQEJZK/contracts/refresh-replay.md",
        "kitty-specs/auth-tranche-2-5-cli-contract-consumption-01KQEJZK/contracts/revoke-call.md",
        "kitty-specs/auth-tranche-2-5-cli-contract-consumption-01KQEJZK/contracts/session-status-call.md",
        "kitty-specs/backward-transition-cli-emit-01KRV8GC/contracts/auto-promote-backward-emit.md",
        "kitty-specs/charter-contract-cleanup-tranche-1-01KQATS4/contracts/ci-job-mypy-availability.md",
        "kitty-specs/charter-contract-cleanup-tranche-1-01KQATS4/contracts/golden-path-envelope-assertions.md",
        "kitty-specs/charter-contract-cleanup-tranche-1-01KQATS4/contracts/README.md",
        "kitty-specs/charter-e2e-827-followups-01KQAJA0/contracts/dossier-snapshot-ownership.md",
        "kitty-specs/charter-e2e-827-followups-01KQAJA0/contracts/next-prompt-file-contract.md",
        "kitty-specs/charter-e2e-827-followups-01KQAJA0/contracts/specify-plan-commit-boundary.md",
        "kitty-specs/charter-golden-path-e2e-tranche-1-01KQ806X/contracts/cli-flow-contract.md",
        "kitty-specs/charter-mediated-doctrine-selection-01KRTZCA/contracts/activation-registry.md",
        "kitty-specs/charter-mediated-doctrine-selection-01KRTZCA/contracts/charter-facade-modules.md",
        "kitty-specs/charter-mediated-doctrine-selection-01KRTZCA/contracts/mission-type-profile.md",
        "kitty-specs/charter-mediated-doctrine-selection-01KRTZCA/contracts/selection-schema.md",
        "kitty-specs/charter-ownership-consolidation-and-neutrality-hardening-01KPD880/contracts/charter-ownership-invariant-contract.md",
        "kitty-specs/charter-ownership-consolidation-and-neutrality-hardening-01KPD880/contracts/charter-public-import-surface.md",
        "kitty-specs/charter-ownership-consolidation-and-neutrality-hardening-01KPD880/contracts/neutrality-lint-contract.md",
        "kitty-specs/charter-ownership-consolidation-and-neutrality-hardening-01KPD880/contracts/README.md",
        "kitty-specs/charter-ownership-consolidation-and-neutrality-hardening-01KPD880/contracts/shim-deprecation-contract.md",
        "kitty-specs/charter-p7-release-closure-01KQF9B9/contracts/validate-json-output.md",
        "kitty-specs/cli-interview-decision-moments-01KPWT8P/contracts/cli-contracts.md",
        "kitty-specs/cli-interview-decision-moments-01KPWT8P/contracts/README.md",
        "kitty-specs/cli-session-survival-daemon-singleton-01KQ9M3M/contracts/auth-doctor.md",
        "kitty-specs/cli-session-survival-daemon-singleton-01KQ9M3M/contracts/daemon-singleton.md",
        "kitty-specs/cli-session-survival-daemon-singleton-01KQ9M3M/contracts/refresh-lock.md",
        "kitty-specs/cli-widen-mode-and-write-back-01KPXFGJ/contracts/cli-contracts.md",
        "kitty-specs/cli-widen-mode-and-write-back-01KPXFGJ/contracts/README.md",
        "kitty-specs/documentation-mission-composition-rewrite-01KQ5M1Y/contracts/drg-shape.md",
        "kitty-specs/documentation-mission-composition-rewrite-01KQ5M1Y/contracts/step-contracts.md",
        "kitty-specs/excise-doctrine-curation-and-inline-references-01KP54J6/contracts/removed-cli-surface.md",
        "kitty-specs/excise-doctrine-curation-and-inline-references-01KP54J6/contracts/resolve-transitive-refs.contract.md",
        "kitty-specs/implement-review-retrospect-reliability-01KQQSCW/contracts/next-routing.md",
        "kitty-specs/implement-review-retrospect-reliability-01KQQSCW/contracts/retrospective-cli.md",
        "kitty-specs/implement-review-retrospect-reliability-01KQQSCW/contracts/review-cycle-domain.md",
        "kitty-specs/layered-doctrine-org-layer-01KRNPEE/contracts/org-doctrine-source-api-contract.md",
        "kitty-specs/layered-doctrine-org-layer-01KRNPEE/contracts/pack-layout.md",
        "kitty-specs/local-custom-mission-loader-01KQ2VNJ/contracts/mission-run-cli.md",
        "kitty-specs/local-custom-mission-loader-01KQ2VNJ/contracts/validation-errors.md",
        "kitty-specs/merge-review-status-hardening-sprint-01KQFF35/contracts/review-command-interface.md",
        "kitty-specs/migration-shim-ownership-rules-01KPDYDW/contracts/doctor-shim-registry-cli.md",
        "kitty-specs/mission-retrospective-learning-loop-01KQ6YEG/contracts/cli_surfaces.md",
        "kitty-specs/mission-retrospective-learning-loop-01KQ6YEG/contracts/gate_api.md",
        "kitty-specs/mission-retrospective-learning-loop-01KQ6YEG/contracts/retrospective_events_v1.md",
        "kitty-specs/mission-retrospective-learning-loop-01KQ6YEG/contracts/retrospective_yaml_v1.md",
        "kitty-specs/mission-retrospective-learning-loop-01KQ6YEG/contracts/synthesizer_hook.md",
        "kitty-specs/p1-dependency-cycle-cleanup-01KQFXVC/contracts/fan-out-adapter.md",
        "kitty-specs/phase-3-charter-synthesizer-pipeline-01KPE222/contracts/topic-selector.md",
        "kitty-specs/phase-4-closeout-host-surfaces-and-trail-01KPWA5X/contracts/host-surface-inventory.md",
        "kitty-specs/phase-4-closeout-host-surfaces-and-trail-01KPWA5X/contracts/profile-invocation-complete.md",
        "kitty-specs/phase-4-closeout-host-surfaces-and-trail-01KPWA5X/contracts/projection-policy.md",
        "kitty-specs/phase6-composition-stabilization-01KQ2JAS/contracts/invocation_executor_invoke.md",
        "kitty-specs/phase6-composition-stabilization-01KQ2JAS/contracts/runtime_bridge_dispatch.md",
        "kitty-specs/phase6-composition-stabilization-01KQ2JAS/contracts/step_contract_executor_lifecycle.md",
        "kitty-specs/private-teamspace-ingress-safeguards-01KQH03Y/contracts/api.md",
        "kitty-specs/quality-devex-hardening-3-2-01KRJGKH/contracts/canonicalization-rule-pipeline.md",
        "kitty-specs/quality-devex-hardening-3-2-01KRJGKH/contracts/stale-lane-auto-rebase-classifier-policy.md",
        "kitty-specs/quality-devex-hardening-3-2-01KRJGKH/contracts/upgrade-probe-and-notifier.md",
        "kitty-specs/release-3-2-0a5-tranche-1-01KQ7YXH/contracts/checklist_surface_removed.contract.md",
        "kitty-specs/release-3-2-0a5-tranche-1-01KQ7YXH/contracts/decision_command_help.contract.md",
        "kitty-specs/release-3-2-0a5-tranche-1-01KQ7YXH/contracts/feature_alias_hidden.contract.md",
        "kitty-specs/release-3-2-0a5-tranche-1-01KQ7YXH/contracts/init_non_git_message.contract.md",
        "kitty-specs/release-3-2-0a5-tranche-1-01KQ7YXH/contracts/mission_create_clean_output.contract.md",
        "kitty-specs/release-3-2-0a5-tranche-1-01KQ7YXH/contracts/status_event_reader_tolerates_decision_events.contract.md",
        "kitty-specs/release-3-2-0a5-tranche-1-01KQ7YXH/contracts/upgrade_post_state.contract.md",
        "kitty-specs/release-3-2-0a6-tranche-2-01KQ9MKP/contracts/invocation-lifecycle.md",
        "kitty-specs/release-3-2-0a6-tranche-2-01KQ9MKP/contracts/json-envelope.md",
        "kitty-specs/review-merge-gate-hardening-3-2-x-01KRC57C/contracts/charter-io-chokepoint.md",
        "kitty-specs/review-merge-gate-hardening-3-2-x-01KRC57C/contracts/encoding-provenance-schema.md",
        "kitty-specs/review-merge-gate-hardening-3-2-x-01KRC57C/contracts/issue-matrix-schema.md",
        "kitty-specs/review-merge-gate-hardening-3-2-x-01KRC57C/contracts/merge-state-idempotency.md",
        "kitty-specs/review-merge-gate-hardening-3-2-x-01KRC57C/contracts/review-mode-resolution.md",
        "kitty-specs/review-merge-gate-hardening-3-2-x-01KRC57C/contracts/status-read-worktree-resolution.md",
        "kitty-specs/shared-package-boundary-cutover-01KQ22DS/contracts/events_consumer_surface.md",
        "kitty-specs/shared-package-boundary-cutover-01KQ22DS/contracts/internal_runtime_surface.md",
        "kitty-specs/shared-package-boundary-cutover-01KQ22DS/contracts/tracker_consumer_surface.md",
        "kitty-specs/software-dev-composition-rewrite-01KQ26CY/contracts/runtime-bridge-composition-api.md",
        "kitty-specs/software-dev-composition-rewrite-01KQ26CY/contracts/tasks-step-contract-schema.md",
        "kitty-specs/spdd-reasons-doctrine-pack-01KQC4AX/contracts/activation.md",
        "kitty-specs/spdd-reasons-doctrine-pack-01KQC4AX/contracts/charter-context.md",
        "kitty-specs/spdd-reasons-doctrine-pack-01KQC4AX/contracts/prompt-fragment.md",
        "kitty-specs/spdd-reasons-doctrine-pack-01KQC4AX/contracts/review-gate.md",
        "kitty-specs/stability-and-hygiene-hardening-2026-04-01KQ4ARB/contracts/events-envelope.md",
        "kitty-specs/stability-and-hygiene-hardening-2026-04-01KQ4ARB/contracts/intake-source-provenance.md",
        "kitty-specs/stability-and-hygiene-hardening-2026-04-01KQ4ARB/contracts/runtime-decision-output.md",
        "kitty-specs/stability-and-hygiene-hardening-2026-04-01KQ4ARB/contracts/tracker-public-imports.md",
        "kitty-specs/stable-320-p0-cli-stabilization-01KQSNGY/contracts/command-surface-generation.md",
        "kitty-specs/stable-320-p0-cli-stabilization-01KQSNGY/contracts/review-verdict-consistency.md",
        "kitty-specs/stable-320-p0-cli-stabilization-01KQSNGY/contracts/status-test-boundedness.md",
        "kitty-specs/stable-320-p1-release-confidence-01KQTPZC/contracts/dependency-drift-guard.md",
        "kitty-specs/stable-320-p1-release-confidence-01KQTPZC/contracts/smoke-workflow-contract.md",
        "kitty-specs/stable-320-p1-release-confidence-01KQTPZC/contracts/task-progress-status.md",
        "kitty-specs/unified-charter-bundle-chokepoint-01KP5Q2G/contracts/bundle-validate-cli.contract.md",
        "kitty-specs/unified-charter-bundle-chokepoint-01KP5Q2G/contracts/canonical-root-resolver.contract.md",
        "kitty-specs/unified-charter-bundle-chokepoint-01KP5Q2G/contracts/chokepoint.contract.md",
        "kitty-specs/workflow-parity-988-989-991-01KRKTT5/contracts/lightweight-review-baseline.md",
        "kitty-specs/workflow-parity-988-989-991-01KRKTT5/contracts/merge-dry-run-review-artifact.md",
        "kitty-specs/workflow-parity-988-989-991-01KRKTT5/contracts/next-json-claimability.md",
        "kitty-specs/wp-prompt-governance-payload-01KRR8HS/contracts/charter-context-resolver.md",
        "kitty-specs/wp-prompt-governance-payload-01KRR8HS/contracts/charter-sync-cross-link.md",
        "kitty-specs/wp-prompt-governance-payload-01KRR8HS/contracts/runtime-template-governance-payload-contract.md",
        # NOTE: post-Slice-F files that are simply non-executable (CI-wiring
        # snippets, ``.kittify/config.yaml`` shape sketches, non-Pydantic config)
        # do NOT belong here — they carry a per-block ``# round-trip: skip: <reason>``
        # marker instead. This allowlist is *only* for pre-Slice-F legacy contracts
        # that still need backfilling (C-004 burn-down). See #2255.
    }
)

# ---------------------------------------------------------------------------
# Negative-fixture inline examples (T016 / AC-10 sanity check)
# ---------------------------------------------------------------------------
# This list proves the gate catches real divergence. Each entry is a
# (contract_label, model_path, expect, payload, expect_message) tuple.
# These are exercised as extra parametrize cases alongside the discovered ones.
# ---------------------------------------------------------------------------
_INLINE_NEGATIVE_FIXTURES: list[tuple[str, str, str, str, str | None]] = [
    # Sanity: a pydantic model with a required field, given an empty dict.
    # Uses charter.offering.drg.models.DRGNode (always available; part of core doctrine).
    (
        "<inline:sanity-negative-fixture>",
        "charter.offering.drg.models.DRGNode",
        "invalid",
        "{}",  # Missing required fields -> ValidationError
        None,
    ),
]

# ---------------------------------------------------------------------------
# Frontmatter regexes
# ---------------------------------------------------------------------------
# Matches the pydantic_model and expect lines at the START of a yaml codeblock.
# We search within the block content (not the full file) so anchors work per-block.
_FRONTMATTER_RE: re.Pattern[str] = re.compile(
    r"^# pydantic_model: (?P<model>[\w\.]+)\s*\n"
    r"# expect: (?P<expect>valid|invalid)",
    re.MULTILINE,
)
_EXPECT_MESSAGE_RE: re.Pattern[str] = re.compile(
    r"^# expect_message: (?P<msg>.+)$", re.MULTILINE
)

# Explicit per-block "this YAML block is intentionally non-executable" marker.
# In a NON-legacy contract every YAML codeblock must be either tagged with
# ``# pydantic_model:`` frontmatter (executed against that model) OR carry this
# marker with a mandatory reason. A block with neither fails the gate per-block
# (FR-140 block-level discovery). The marker is the explicit home for shape
# sketches, illustrations, CI-wiring snippets, and non-Pydantic operator config
# — distinct from the legacy burn-down allowlist (which is file-level and
# tracked in ``_baselines.yaml``). The reason is required: ``# round-trip: skip:``
# with no text does not match and the block is treated as missing frontmatter.
_SKIP_MARKER_RE: re.Pattern[str] = re.compile(
    # ``[ \t]*`` (not ``\s*``) so the reason cannot run onto the next line and a
    # bare ``# round-trip: skip:`` with no reason fails to match (forcing a reason).
    r"^# round-trip: skip:[ \t]*(?P<reason>\S.*)$", re.MULTILINE
)

# Fenced yaml codeblock (triple backtick, NOT preceded on the same line by a
# 4th backtick which would make it a nested illustration inside a markdown fence).
_YAML_BLOCK_RE: re.Pattern[str] = re.compile(
    r"^```yaml\n(?P<body>.*?)^```",
    re.MULTILINE | re.DOTALL,
)

# 4-backtick outer fence used in contracts to illustrate the convention.
# Blocks whose opening ``` is nested inside a ````...```` fence are
# ILLUSTRATION ONLY and must NOT be exercised by the round-trip gate.
_QUAD_FENCE_RE: re.Pattern[str] = re.compile(
    r"^````.*?^````",
    re.MULTILINE | re.DOTALL,
)


# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------

def _strip_frontmatter_comments(block_body: str) -> str:
    """Remove leading ``# pydantic_model:``, ``# expect:``, ``# expect_message:`` lines."""
    lines = block_body.splitlines(keepends=True)
    stripped: list[str] = []
    for line in lines:
        stripped_line = line.lstrip()
        if (
            stripped_line.startswith("# pydantic_model:")
            or stripped_line.startswith("# expect:")
            or stripped_line.startswith("# expect_message:")
        ):
            continue
        stripped.append(line)
    return "".join(stripped)


def _relative_path(path: Path) -> str:
    """Return path relative to repo root as a forward-slash string."""
    try:
        return str(path.relative_to(_REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def _is_legacy(contract_path: Path) -> bool:
    """True iff *contract_path* is in the legacy allowlist."""
    return _relative_path(contract_path) in _LEGACY_CONTRACT_ALLOWLIST


def _extract_yaml_blocks(text: str) -> list[str]:
    """Extract ```yaml codeblocks from *text*, skipping those inside 4-backtick fences.

    4-backtick outer fences (````markdown ... ````) are used in contracts to
    ILLUSTRATE the frontmatter convention itself; the inner ```yaml blocks are
    documentation illustrations, not round-trip tested examples.
    """
    # Blank out all 4-backtick fence regions so inner ```yaml blocks are hidden.
    scrubbed = _QUAD_FENCE_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    return _YAML_BLOCK_RE.findall(scrubbed)


def _parse_expect_message(raw: str) -> str:
    """Parse the expect_message value, stripping optional surrounding quotes.

    The frontmatter line may use YAML-style quoting::

        # expect_message: "unknown kind"   -> returns: unknown kind
        # expect_message: unknown kind     -> returns: unknown kind
    """
    stripped = raw.strip()
    if len(stripped) >= 2 and stripped[0] in ('"', "'") and stripped[-1] == stripped[0]:
        return stripped[1:-1]
    return stripped


def _classify_yaml_block(block_body: str) -> tuple[str, dict[str, Any]]:
    """Classify a single YAML codeblock for the round-trip gate.

    Returns ``(kind, info)`` where *kind* is one of:

    * ``"execute"`` — the block carries ``# pydantic_model:`` frontmatter; *info*
      holds ``model`` / ``expect`` / ``expect_message`` / ``payload``.
    * ``"skip"`` — the block carries a ``# round-trip: skip: <reason>`` marker;
      *info* holds ``reason``. The block is intentionally non-executable.
    * ``"missing"`` — the block carries neither; *info* is empty. For a
      non-legacy contract this is a gate failure (a forgotten tag).

    Frontmatter takes precedence over a skip marker when both are present, so a
    real example can never be silently disabled by a stray marker.
    """
    fm = _FRONTMATTER_RE.search(block_body)
    if fm is not None:
        msg_match = _EXPECT_MESSAGE_RE.search(block_body)
        return "execute", {
            "model": fm.group("model"),
            "expect": fm.group("expect"),
            "expect_message": (
                _parse_expect_message(msg_match.group("msg")) if msg_match else None
            ),
            "payload": _strip_frontmatter_comments(block_body),
        }
    skip = _SKIP_MARKER_RE.search(block_body)
    if skip is not None:
        return "skip", {"reason": skip.group("reason").strip()}
    return "missing", {}


# Report-only nudges collected during discovery (module-import time — see
# ``_DISCOVERED`` below), surfaced later by
# ``test_legacy_contract_backfill_nudges_are_reported`` via ``record_property``.
# Discovery runs before any test function/fixture context exists, so the
# diagnostic cannot go through ``record_property`` at collection time itself;
# collecting here and reporting from a dedicated test is the two-stage shape
# this repo uses whenever a report-only finding is produced outside a test
# body (NFR-006: no ``warnings.warn`` for report-only diagnostics).
_LEGACY_BACKFILL_NUDGES: list[tuple[str, str]] = []


def _collect_legacy_blocks(
    rel: str,
    yaml_blocks: list[str],
    examples: list[tuple[str, str, str, str, str | None]],
    nudges: list[tuple[str, str]] | None = None,
) -> None:
    """Collect executable cases from a legacy (pre-Slice-F) contract.

    Legacy contracts keep file-level burn-down leniency: tagged blocks still
    execute, but untagged blocks are tolerated. A backfill nudge is recorded
    only when the file carries NO frontmatter at all. Block-level strictness
    is deferred until the file is backfilled out of ``_LEGACY_CONTRACT_ALLOWLIST``.

    *nudges* defaults to the module-level ``_LEGACY_BACKFILL_NUDGES`` collector
    used by real discovery; tests pass their own list to keep the module-level
    collector — which real ``_discover_examples()`` also populates at import
    time — untouched by unit-test invocations.
    """
    found_any_frontmatter = False
    for block_idx, block_body in enumerate(yaml_blocks, start=1):
        kind, info = _classify_yaml_block(block_body)
        if kind != "execute":
            continue
        found_any_frontmatter = True
        examples.append(
            (
                f"{rel}::block-{block_idx}",
                info["model"],
                info["expect"],
                info["payload"],
                info["expect_message"],
            )
        )
    if not found_any_frontmatter:
        target = _LEGACY_BACKFILL_NUDGES if nudges is None else nudges
        target.append(
            (
                rel,
                f"Legacy contract '{rel}' has {len(yaml_blocks)} YAML codeblock(s) "
                f"but none carry ``# pydantic_model:`` frontmatter. "
                f"Consider backfilling the convention to shrink the legacy allowlist "
                f"(tests/architectural/_baselines.yaml::test_example_round_trip"
                f".legacy_contract_allowlist).",
            )
        )


def _collect_strict_blocks(
    rel: str,
    yaml_blocks: list[str],
    examples: list[tuple[str, str, str, str, str | None]],
) -> None:
    """Collect cases from a non-legacy contract under block-level strictness (FR-140).

    Every YAML block must be either tagged (executed against its model) or carry
    an explicit ``# round-trip: skip: <reason>`` marker. A block with neither is
    emitted as ``<MISSING_FRONTMATTER>`` so the parametrised gate fails on that
    specific block — a tagged sibling can no longer mask a forgotten tag.
    """
    for block_idx, block_body in enumerate(yaml_blocks, start=1):
        kind, info = _classify_yaml_block(block_body)
        if kind == "execute":
            examples.append(
                (
                    f"{rel}::block-{block_idx}",
                    info["model"],
                    info["expect"],
                    info["payload"],
                    info["expect_message"],
                )
            )
        elif kind == "missing":
            examples.append(
                (
                    f"{rel}::block-{block_idx}-MISSING_FRONTMATTER",
                    "<MISSING_FRONTMATTER>",
                    "valid",
                    "{}",
                    None,
                )
            )
        # kind == "skip": intentionally non-executable; nothing to add.


def _discover_examples() -> list[tuple[str, str, str, str, str | None]]:
    """Walk every ``kitty-specs/*/contracts/*.md`` and yield round-trip cases.

    Yields tuples of:
        (contract_label, model_dotted_path, expect, yaml_payload, expect_message_or_None)

    Discovery is **block-level** for non-legacy contracts: each YAML block must
    be tagged with ``# pydantic_model:`` frontmatter (executed) or carry a
    ``# round-trip: skip: <reason>`` marker (intentionally non-executable);
    otherwise the block is emitted as ``<MISSING_FRONTMATTER>`` and the gate
    fails on it. Legacy contracts (``_LEGACY_CONTRACT_ALLOWLIST``) keep
    file-level burn-down leniency and warn instead of failing.
    """
    examples: list[tuple[str, str, str, str, str | None]] = []

    if not _KITTY_SPECS_ROOT.exists():
        return examples

    for contract_md in sorted(_KITTY_SPECS_ROOT.glob("*/contracts/*.md")):
        text = contract_md.read_text(encoding="utf-8")
        rel = _relative_path(contract_md)

        yaml_blocks = _extract_yaml_blocks(text)
        if not yaml_blocks:
            # No YAML codeblocks at all — just a prose contract. Skip quietly.
            continue

        if _is_legacy(contract_md):
            _collect_legacy_blocks(rel, yaml_blocks, examples)
        else:
            _collect_strict_blocks(rel, yaml_blocks, examples)

    return examples


def _discover_skip_marked_blocks() -> frozenset[str]:
    """Return the ``rel::block-N`` labels of every ``# round-trip: skip:`` block.

    Restricted to NON-legacy contracts, where the skip marker is load-bearing
    (legacy contracts keep file-level leniency and do not need markers). The set
    is ratcheted in ``tests/architectural/_baselines.yaml`` so that adding a new
    permanently-non-executable block is an explicit, reviewable event — a new
    skip grows the count above its baseline and fails the ratchet until the
    baseline is bumped with a justification. Unlike the legacy allowlist, skip
    markers are permanent legitimate exemptions (no shrink mandate); the ratchet
    exists purely for growth VISIBILITY, not burn-down.
    """
    labels: set[str] = set()
    if not _KITTY_SPECS_ROOT.exists():
        return frozenset(labels)
    for contract_md in sorted(_KITTY_SPECS_ROOT.glob("*/contracts/*.md")):
        if _is_legacy(contract_md):
            continue
        rel = _relative_path(contract_md)
        blocks = _extract_yaml_blocks(contract_md.read_text(encoding="utf-8"))
        for block_idx, block_body in enumerate(blocks, start=1):
            kind, _ = _classify_yaml_block(block_body)
            if kind == "skip":
                labels.add(f"{rel}::block-{block_idx}")
    return frozenset(labels)


# ---------------------------------------------------------------------------
# Collect parametrize cases at module-import time (pytest requires this)
# ---------------------------------------------------------------------------
_DISCOVERED: list[tuple[str, str, str, str, str | None]] = _discover_examples()
_ALL_CASES: list[tuple[str, str, str, str, str | None]] = _DISCOVERED + _INLINE_NEGATIVE_FIXTURES

# Set of permanently-non-executable (``# round-trip: skip:``) blocks in
# non-legacy contracts (see ``_discover_skip_marked_blocks``). It carries no count
# baseline: the enforcer is the per-block ``_SKIP_MARKER_RE`` gate (a block with
# neither frontmatter nor a reasoned skip marker becomes a failing
# ``MISSING_FRONTMATTER`` case), and this set exists for the
# ``test_skip_marked_blocks_invariants`` self-test.
_SKIP_MARKED_BLOCKS: frozenset[str] = _discover_skip_marked_blocks()

# ---------------------------------------------------------------------------
# The parametrised gate (AC-10)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "contract_label,model_path,expect,payload,expect_message",
    _ALL_CASES,
    ids=[c[0] for c in _ALL_CASES],
)
def test_contract_example_round_trip(
    contract_label: str,
    model_path: str,
    expect: str,
    payload: str,
    expect_message: str | None,
) -> None:
    """FR-140 round-trip gate: every tagged codeblock validates against its model.

    Outcomes
    --------
    * ``expect: valid``   → ``model_validate`` MUST succeed.
    * ``expect: invalid`` → ``model_validate`` MUST raise ``ValidationError``.

    Failure messages match the shape documented in
    ``kitty-specs/slice-f-multi-context-extensibility-01KRX5C8/contracts/
    contract-round-trip-frontmatter.md``.
    """
    # --- Guard: a non-legacy YAML block carries neither frontmatter nor a skip marker ---
    if model_path == "<MISSING_FRONTMATTER>":
        pytest.fail(
            f"Contract block '{contract_label}' carries neither "
            f"``# pydantic_model:`` frontmatter nor a ``# round-trip: skip: <reason>`` "
            f"marker. Pick one: (1) add frontmatter to round-trip the block against "
            f"a Pydantic model; (2) add ``# round-trip: skip: <reason>`` if the block "
            f"is an illustration / shape sketch / non-Pydantic config or CI snippet; "
            f"or (3) for a pre-Slice-F file, add it to ``_LEGACY_CONTRACT_ALLOWLIST`` "
            f"in ``tests/contract/test_example_round_trip.py`` and bump "
            f"``tests/architectural/_baselines.yaml``."
        )

    # --- Import the model ---
    module_dotted, _, class_name = model_path.rpartition(".")
    if not module_dotted:
        pytest.fail(
            f"'{contract_label}': ``pydantic_model: {model_path}`` is not a valid "
            f"dotted import path (expected ``module.ClassName``)."
        )

    try:
        module = import_contract_module(module_dotted)
    except ImportError as exc:
        pytest.fail(f"'{contract_label}': pydantic_model module is not importable: {exc}")

    if not hasattr(module, class_name):
        pytest.fail(
            f"'{contract_label}': ``{module_dotted}`` has no attribute "
            f"``{class_name}``."
        )

    model_cls = getattr(module, class_name)

    # --- Parse the YAML payload ---
    try:
        parsed: Any = yaml.safe_load(payload)
    except yaml.YAMLError as exc:
        pytest.fail(
            f"'{contract_label}' YAML payload failed to parse: {exc}"
        )

    # --- Assert expected outcome ---
    if expect == "valid":
        try:
            model_cls.model_validate(parsed)
        except pydantic.ValidationError as exc:
            pytest.fail(
                f"'{contract_label}' declared ``pydantic_model: {model_path}, "
                f"expect: valid`` but ``model_validate`` raised:\n{exc}"
            )
    else:  # expect == "invalid"
        with pytest.raises(pydantic.ValidationError) as exc_info:
            model_cls.model_validate(parsed)
        if expect_message is not None:
            error_text = str(exc_info.value)
            assert expect_message in error_text, (
                f"'{contract_label}' declared ``expect_message: {expect_message!r}`` "
                f"but the ValidationError text does not contain it.\n"
                f"Actual error:\n{error_text}"
            )


# ---------------------------------------------------------------------------
# Unit coverage for block-level discovery (FR-140 block-level + skip marker, #2255)
# ---------------------------------------------------------------------------


def test_classify_block_executes_on_frontmatter() -> None:
    kind, info = _classify_yaml_block(
        "# pydantic_model: a.b.C\n# expect: invalid\n"
        "# expect_message: boom\nkey: value\n"
    )
    assert kind == "execute"
    assert info["model"] == "a.b.C"
    assert info["expect"] == "invalid"
    assert info["expect_message"] == "boom"
    # Frontmatter comment lines are stripped from the executable payload.
    assert info["payload"] == "key: value\n"


def test_classify_block_skips_on_marker_with_reason() -> None:
    kind, info = _classify_yaml_block(
        "# round-trip: skip: illustration only\nkey: value\n"
    )
    assert kind == "skip"
    assert info["reason"] == "illustration only"


def test_classify_block_missing_when_neither_present() -> None:
    kind, info = _classify_yaml_block("key: value\nother: 1\n")
    assert kind == "missing"
    assert info == {}


def test_classify_block_skip_marker_requires_a_reason() -> None:
    # An empty reason must NOT count as a skip — the block falls through to
    # ``missing`` so the gate forces an explicit rationale.
    kind, _ = _classify_yaml_block("# round-trip: skip:\nkey: value\n")
    assert kind == "missing"


def test_classify_block_frontmatter_wins_over_skip_marker() -> None:
    # A real example can never be silently disabled by a stray skip marker.
    kind, info = _classify_yaml_block(
        "# pydantic_model: a.b.C\n# expect: valid\n# round-trip: skip: nope\nk: v\n"
    )
    assert kind == "execute"
    assert info["model"] == "a.b.C"


def test_strict_collection_fails_untagged_block_per_block() -> None:
    out: list[tuple[str, str, str, str, str | None]] = []
    _collect_strict_blocks("x/contracts/y.md", ["a: 1\n", "b: 2\n"], out)
    # Both untagged blocks fail, each labelled with its own block index.
    assert [c[1] for c in out] == ["<MISSING_FRONTMATTER>", "<MISSING_FRONTMATTER>"]
    assert out[0][0] == "x/contracts/y.md::block-1-MISSING_FRONTMATTER"
    assert out[1][0] == "x/contracts/y.md::block-2-MISSING_FRONTMATTER"


def test_strict_collection_skips_marked_block() -> None:
    out: list[tuple[str, str, str, str, str | None]] = []
    _collect_strict_blocks(
        "x/contracts/y.md", ["# round-trip: skip: shape sketch\na: 1\n"], out
    )
    assert out == []


def test_strict_collection_executes_tagged_block() -> None:
    out: list[tuple[str, str, str, str, str | None]] = []
    _collect_strict_blocks(
        "x/contracts/y.md", ["# pydantic_model: a.b.C\n# expect: valid\nk: v\n"], out
    )
    assert len(out) == 1
    assert out[0][0] == "x/contracts/y.md::block-1"
    assert out[0][1] == "a.b.C"


def test_strict_collection_tagged_sibling_does_not_mask_untagged() -> None:
    # The core P1 regression (#2255): a tagged block in the same file must NOT
    # absorb an untagged sibling. The untagged block still fails.
    out: list[tuple[str, str, str, str, str | None]] = []
    _collect_strict_blocks(
        "x/contracts/y.md",
        ["# pydantic_model: a.b.C\n# expect: valid\nk: v\n", "untagged: true\n"],
        out,
    )
    kinds = {c[1] for c in out}
    assert "<MISSING_FRONTMATTER>" in kinds
    assert "a.b.C" in kinds


def test_legacy_collection_nudges_and_does_not_fail_when_untagged(
    recwarn: pytest.WarningsRecorder,
) -> None:
    out: list[tuple[str, str, str, str, str | None]] = []
    nudges: list[tuple[str, str]] = []
    _collect_legacy_blocks("x/contracts/y.md", ["a: 1\n"], out, nudges=nudges)
    # Legacy files never emit a MISSING_FRONTMATTER failure case.
    assert out == []
    # The nudge is recorded (for later record_property reporting), not warned
    # (NFR-006: the warnings channel stays first-party-clean).
    assert len(nudges) == 1
    assert nudges[0][0] == "x/contracts/y.md"
    assert "Legacy contract" in nudges[0][1]
    assert len(recwarn.list) == 0


def test_skip_marked_blocks_invariants() -> None:
    """The skip set holds only non-legacy, genuinely skip-marked blocks.

    Guards the two promises of ``_discover_skip_marked_blocks`` without pinning a
    count: each new skip is reviewed through its own mandatory
    ``# round-trip: skip: <reason>`` line, enforced per block by ``_SKIP_MARKER_RE``.
    It stays green when a future PR legitimately adds a reasoned marker.
    """
    assert isinstance(_SKIP_MARKED_BLOCKS, frozenset)
    for label in _SKIP_MARKED_BLOCKS:
        rel, _, suffix = label.partition("::block-")
        assert suffix, f"malformed skip label: {label!r}"
        # Invariant 1: skip markers are only ratcheted for NON-legacy contracts.
        assert rel not in _LEGACY_CONTRACT_ALLOWLIST, (
            f"{rel} is legacy-allowlisted; its blocks must not be counted as skips"
        )
        # Invariant 2: the referenced block actually classifies as a skip.
        block_idx = int(suffix)
        blocks = _extract_yaml_blocks((_REPO_ROOT / rel).read_text(encoding="utf-8"))
        kind, info = _classify_yaml_block(blocks[block_idx - 1])
        assert kind == "skip"
        assert info["reason"], f"skip marker in {label} must carry a reason"


def test_legacy_contract_backfill_nudges_are_reported(
    record_property: RecordPropertyFn,
) -> None:
    """Report-only: nudge maintainers to backfill ``# pydantic_model:`` frontmatter.

    Real discovery (``_discover_examples()``, module-import time) populates
    ``_LEGACY_BACKFILL_NUDGES`` with one entry per legacy-allowlisted contract
    whose YAML codeblocks carry no frontmatter at all. Discovery runs before
    any test function/fixture context exists, so it cannot call
    ``record_property`` directly — this test surfaces the collected nudges via
    ``record_property`` instead of ``warnings.warn``, consistent with this
    repo's convention for report-only diagnostics (NFR-006: the warnings
    channel stays first-party-clean; see ``test_migration_chain_integrity.py``,
    ``test_ci_collection_completeness.py``, ``test_retired_contracts_absent.py``). Never
    fails: the legacy allowlist shrinks over time (C-004 burn-down), tracked
    separately via the allowlist count baseline in
    ``tests/architectural/_baselines.yaml``.
    """
    for rel, message in _LEGACY_BACKFILL_NUDGES:
        record_property(f"legacy_contract_backfill_nudge[{rel}]", message)


# ---------------------------------------------------------------------------
# Module-relocation map self-tests (FR-004 masked-greens row 16, C-006)
# ---------------------------------------------------------------------------


def test_module_relocation_targets_are_importable() -> None:
    """Every canonical target in the relocation map actually imports.

    A dead-end row (a canonical name that itself does not exist) would let
    ``import_contract_module`` raise a misleading error blaming the wrong
    side of the relocation instead of the map. Pin importability at the map
    level so a future rename of a canonical target is caught here first.
    """
    for historical, canonical in HISTORICAL_TO_CANONICAL.items():
        try:
            importlib.import_module(canonical)
        except ImportError as exc:
            pytest.fail(
                f"relocation row {historical!r} -> {canonical!r} names a "
                f"canonical module that is not importable: {exc}"
            )


def test_module_relocation_keys_are_referenced_by_an_archived_contract() -> None:
    """Every relocation row exists because an archived contract still needs it.

    Reuses ``_DISCOVERED`` — the same discovery the parametrized round-trip
    test consumes — so the map's rows track the corpus of archived
    ``# pydantic_model:`` references. A row nobody references is a dead row:
    it should be deleted, not kept "just in case".
    """
    referenced_modules = {
        model_path.rpartition(".")[0] for _, model_path, *_ in _DISCOVERED
    }
    for key in HISTORICAL_TO_CANONICAL:
        assert any(
            module == key or module.startswith(f"{key}.")
            for module in referenced_modules
        ), f"relocation row {key!r} is a dead row: no archived contract references it"


def test_canonical_module_name_prefers_longest_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prefix matching is whole-segment only, and the longest key wins a tie.

    The live map has no nested/overlapping keys today, so this test installs
    a small synthetic map (via monkeypatch, restored automatically) to pin
    the tie-breaking and whole-segment-matching behavior directly. Only
    ``HISTORICAL_TO_CANONICAL`` is patched: the lookup order itself is
    derived from the map by the PRODUCTION sort inside
    ``canonical_module_name`` (there is no separate precomputed-order
    constant to patch around), so this test exercises the real ordering
    expression, not a copy of it.
    """
    synthetic = {
        "a.b": "canonical.coarse",
        "a.b.c": "canonical.fine",
    }
    monkeypatch.setattr(_module_relocations, "HISTORICAL_TO_CANONICAL", synthetic)

    # A nested module beneath the more specific key resolves against it, not
    # against its coarser ancestor.
    assert (
        _module_relocations.canonical_module_name("a.b.c.d") == "canonical.fine.d"
    )
    # A module that only extends the coarser row still resolves deterministically.
    assert (
        _module_relocations.canonical_module_name("a.b.other")
        == "canonical.coarse.other"
    )
    # A non-matching dotted path returns None.
    assert _module_relocations.canonical_module_name("z.y.x") is None
    # Whole-segment matching: "a.bc" must not match the "a.b" row.
    assert _module_relocations.canonical_module_name("a.bc") is None


def test_import_contract_module_names_no_relocation_row_when_unmapped() -> None:
    """An unmapped, non-importable module fails naming itself and the reason.

    Pins the ``canonical is None`` branch of ``import_contract_module``
    directly, rather than only exercising it via a planted break.
    """
    with pytest.raises(ImportError, match="no relocation row matches"):
        _module_relocations.import_contract_module("nonexistent_pkg_xyz.mod")


def test_import_contract_module_names_both_modules_when_canonical_also_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mapped row whose canonical target is itself missing names both sides.

    Pins the "neither X nor canonical Y is importable" branch directly,
    rather than only exercising it via a planted break.
    """
    monkeypatch.setattr(
        _module_relocations,
        "HISTORICAL_TO_CANONICAL",
        {"doctrine.drg": "charter.offering.drg_moved_away"},
    )
    with pytest.raises(ImportError, match=r"neither .* nor canonical .* is importable"):
        _module_relocations.import_contract_module("doctrine.drg.models")
