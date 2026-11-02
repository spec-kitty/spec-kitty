# REASONS Canvas — CI speed and verdict hardening

## Requirements

The operator approved the CI review and requested implementation through an unmerged PR. spec.md is the intent contract. Preserve truthful test verdicts, source-bound evidence and verification strength while removing repeated work.

## Entities

Test identity, revision evidence, execution mode, cache identity and stable required check. Source code and workflow definitions remain the behavioral authority.

## Approach

Use disjoint implementation concerns, add focused red-first regressions, then integrate and independently review the complete diff. Favor reused immutable facts and exact content cache candidates over new queue barriers or unchecked skip switches.

## Structure

Extend existing script/action/test owners. Maintain the gate-selection authority; do not introduce another module routing map. Pure packaging selection is only a conservative wheel-work optimization, never test selection.

## Operations

1. Ground scope in live files and run evidence.
2. Commit executable failure regressions.
3. Implement test/measurement/cache/reporting concerns and workflow integration.
4. Run targeted tests, bounded baseline, formatting/types and independent review.
5. Open a draft PR, record limitations, do not merge.

## Norms

All delegated work uses DeepSeek V4.1 Flash 1017. Preserve historical git consumers, test isolation, cross-package coverage and no-full-heavy-local-suite discipline.

## Safeguards

Actual shipped shell exit-code tests; scratch mutation controls; exact revision coverage checks; identity-aware timing data; malformed/uncertain input fallback to real verification; live policy digest/HMAC validation even after cache restore.

### Deviations

A new per-run policy producer and extra consolidation shards are not introduced without whole-pipeline evidence. Independent review demonstrated that a co-cached HMAC key cannot authenticate against a malicious cache writer. Consequently cross-run policy caching is restricted to trusted default-branch events; PRs keep fresh local scans. Legacy positional timings cannot honestly be given inferred node IDs; migration retains explicit provenance and safe fallback.
