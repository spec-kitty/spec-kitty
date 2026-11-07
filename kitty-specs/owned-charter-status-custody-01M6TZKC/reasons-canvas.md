# REASONS Canvas: Owned Mission coordination status charter custody

## Requirements

Valid owned `lanes_with_coord` advances must accept the same Mission's canonical coordination status directory as well as its primary Mission directory. Every other directory remains refused, and charter governance remains anchored to the validated owned primary Mission. Done means red-first canonical-status and installed-CLI reproductions turn green, focused owned integration surfaces remain green, and no main-recovery claim precedes a green merged-commit nightly.

## Approach

Preserve the custody projector and primary fast path. On inequality only, use the canonical Mission placement facade to compare the input against this owned Mission's status read directory. Rejected alternatives are hardcoded worktree paths, unconditional primary-path substitution, guard removal, and wider runtime signatures.

## Structure

The change is limited to `src/specify_cli/core/owned_charter.py`, focused coverage in `tests/integration/test_owned_prompt_charter_scope.py`, and `docs/changelog/unreleased/6788.fixed.md`. Existing owned runtime and installed-CLI entry points provide blast-radius and public-path validation without modification.

## Operations

1. Reproduce installed-CLI `[0]` red, then add and commit the canonical-status positive plus foreign-path negative before production code.
2. Change only the unequal custody arm, add the narrow changelog fragment, rerun both owned integration surfaces and the exact e2e, then run the ordinary fast baseline and scoped quality checks.
3. Review the aggregate diff under a distinct reviewer role and publish a draft PR without claiming nightly recovery.

## WP Boundaries

WP01 owns `src/specify_cli/core/owned_charter.py`, `tests/integration/test_owned_prompt_charter_scope.py`, and `docs/changelog/unreleased/6788.fixed.md`. It must not touch runtime_bridge, the owned-worktree e2e, startup/performance files, #7206 assets, or another WP/PR's scope.

## Entities

- **Owned Mission**: the validated checkout identity that owns one Mission and its primary charter.
- **Primary Mission directory**: the owned Mission's stable planning and charter directory.
- **Canonical coordination status directory**: the same owned Mission's status read surface, which may legitimately differ from the primary Mission directory.
- **Foreign directory**: any path other than those two canonical same-Mission surfaces; custody must refuse it.
