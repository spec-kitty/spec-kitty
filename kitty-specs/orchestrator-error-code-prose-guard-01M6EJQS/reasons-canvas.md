# REASONS Canvas — Orchestrator error-code prose guard

> Mission: orchestrator-error-code-prose-guard-01M6EJQS
> Generated: 2026-11-02
> Charter activation: structured-prompt-driven-development (paradigm)
> Audience: software-engineer and automation-agent

## Requirements
- Problem: `orchestrator_api.allowed_error_codes` has 80 codes; the two prose surfaces that claim to enumerate them list 58 and 57, and nothing compares the three. The docs list is 22 codes behind, the shipped skill table 23 ([research.md](research.md), D-1).
- Acceptance: [spec.md](spec.md) FR-001..FR-010, SC-001..SC-005. Both surfaces enumerate all 80; one contract test asserts set equality per surface in both directions; a missing anchor or empty region fails the check.
- Definition of done: failing-first contract test, complete enumerations, targeted green evidence (guard + docs freshness + markdownlint), one independent review round, changelog fragment, draft PR flipped to ready. No merge by an implementation agent.

## Entities
- **Contract authority**: `orchestrator_api.allowed_error_codes` in the installed `upstream_contract.json`. Read at test time; never copied ([spec.md](spec.md#key-entities)).
- **Prose enumeration surface**: a delimited Markdown region that claims to list the codes. Two instances, one anchor pair each.
- **Enumeration anchor**: `<!-- orchestrator-error-codes:begin -->` / `:end`; its absence is a failure, not a skip.
- Out of scope and deliberately outside the regions: `data.preflight_error_code`, `data.teardown_error_code` and origin-freshness codes — a different namespace that rides inside `data`.

## Approach
- Restate the missing families as enumerable entries (the user-visible fix) *and* wrap each enumeration in explicit anchors the test parses — the issue's two options fused, with no third mapping file to drift.
- Compare `allowed_error_codes` against each surface's region as sets in both directions, plus a duplicate check, reporting sorted per-surface diffs.
- Rejected: parsing everything under `## Error Codes` (it finds 21 non-contract sub-codes, [research.md](research.md) D-1); a separate `documented-in-prose.yaml` mapping (a third surface that can drift); a `scripts/docs/check_*` gate (needs CI wiring the contract shard already has).

## Structure
- Docs: `docs/api/orchestrator-api.md` (`## Error Codes` region), `src/charter/offering/skills/spec-kitty-orchestrator-api-operator/references/orchestrator-api-contract.md` (`## Error Code Summary` table).
- Test: `tests/contract/test_orchestrator_api.py`, a sibling class to `TestAllowedErrorCodes`; contract read through `specify_cli.core` package resources.
- No source change, no contract change, no new module.

## Operations
1. Campsite check the two docs surfaces and the contract test module; confirm the measured drift before editing.
2. Write the guard first and demonstrate RED on the unmodified docs (both surfaces, named codes), then commit the red step.
3. Apply the docs enumeration fix; show the guard green; verify each surface independently and the anchor-absence failure.
4. Revert one surface at a time to prove the guard, not the docs edit, is what closes the issue (half-by-half).
5. Run the contract test module, markdownlint on the touched docs, `check_docs_freshness --ci`, ruff/format on the test file.
6. Changelog fragment, draft PR, CI to green, flip to ready. The operator merges.

## Norms
- Canonical sources only: the contract JSON is the authority; the docs enumeration is the human view; the test is the only comparison point.
- Targeted staging, explicit `--mission` handle, clean linear history, no machine-local paths in commits.
- Evidence reported as commands plus results, not summaries.

## Safeguards
- No gate, marker, deselection or xfail may be relaxed to land this (spec C-002); `TestAllowedErrorCodes` keeps both existing assertions (C-003).
- The `upstream_contract.json` vendored file is not edited (C-001).
- Sub-code tables must not be pulled into the checked region (C-005), or the guard will demand `LANE_MOVED_AFTER_APPROVAL` in the contract.
- No `main` push, no merge, no auto-merge, no full heavy suite in-mission.

## Deviations (append-only)
