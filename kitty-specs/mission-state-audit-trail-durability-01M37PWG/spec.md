# Mission Specification: Mission-State Repair Audit-Trail Durability

**Mission Branch**: `fix/mission-state-audit-trail-durability`
**Created**: 2026-09-23
**Status**: Draft
**Input**: GitHub #4928 — the placement/visibility half of the silent-destructive-write class. Sibling of #4897 (row-canonicality), which landed via PR #4938 / mission `silent-destructive-write-hardening-01M355VK`. Scope confirmed by a four-lens brownfield squad: placement/visibility seam only.

## Problem

`spec-kitty doctor mission-state --fix` (reachable directly and via `upgrade`) records a destructive repair in two artifacts: a **per-run manifest** (`MANIFEST_ROOT/<run_id>.json`, written on *every* run — `mission_state.py:713,752`) and, when it evicts rows, a **quarantine tree** holding the removed rows verbatim (`MANIFEST_ROOT/quarantine/<run_id>/<slug>/status.events.jsonl` — `mission_state.py:1712-1715`). `MANIFEST_ROOT` is `.kittify/migrations/mission-state` (`mission_state.py:77`), which sits under the shipped `.gitignore:76` entry `.kittify/migrations/`. So both the record of what a destructive repair did and the only verbatim copy of any rows it removed live **outside version control**: `git clean -xfd` destroys both, and nothing in the `--fix` output tells the operator the artifacts are untracked. An operator reaching for a repair tool is plausibly about to clean their tree — the moment the record matters most is the moment it is most likely to be lost.

The code's own intent already contradicts the gitignore: `_POLICY_TRACKED` (`mission_state.py:85-89`) lists `.kittify/migrations/mission-state/*.json` as a **tracked** policy pattern, while `.gitignore:76` ignores the whole tree.

A second repair flow — the duplicate-key repair (`mission_state.py:904-913`, `_DUP_KEY_MANIFEST_PREFIX`) — writes its manifest under the same gitignored `MANIFEST_ROOT`, so the defect is not unique to the mission-state repair path.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The audit trail of a destructive repair survives a working-tree clean (Priority: P1)

An operator runs `doctor mission-state --fix`, which quarantines one or more rows, then later runs `git clean -xfd` (or the repair itself is run in a tree they subsequently clean). The record of the repair, and the verbatim removed rows, are still present at a version-controllable path and are recoverable.

**Why this priority**: This is the core defect. Without durability the audit trail is a defence-in-depth guarantee that silently evaporates under an ordinary git operation, turning a "recoverable" repair into real data loss.

**Independent Test**: Run `--fix` on a fixture mission whose repair quarantines a row; assert the manifest and quarantine artifacts are written under a **non-gitignored** path (`git check-ignore` reports them as *not* ignored); run `git clean -xfd`; assert both artifacts still exist.

**Acceptance Scenarios**:

1. **Given** a mission whose `--fix` run quarantines ≥1 row, **When** `--fix` completes, **Then** the manifest and the quarantine copy of the removed rows are written to a path that `git check-ignore` reports as **not ignored**.
2. **Given** a completed `--fix` run whose audit artifacts are uncommitted, **When** the operator runs `git clean -xfd`, **Then** the manifest and quarantine artifacts still exist on disk.
3. **Given** a `--fix` run that quarantines **zero** rows, **When** it completes, **Then** a manifest recording the (no-op) repair is still written to the tracked path — every repair leaves a record.

### User Story 2 - The operator is told, at repair time, what was written and that it must be committed (Priority: P1)

When `--fix` finishes, its output names the audit artifacts it wrote, states they are tracked-but-uncommitted, and tells the operator to commit them to preserve the record.

**Why this priority**: Durability by relocation is only realized when the operator commits. Silence at exit is exactly how the current defect hides; a visible summary closes the loop and is independently valuable even before anyone runs `git clean`.

**Independent Test**: Capture `--fix` stdout on a run that quarantines a row and on a run that does not; assert both name the manifest path, and the quarantining run additionally names the quarantine path and the removed-row count, with an explicit "commit to preserve" instruction.

**Acceptance Scenarios**:

1. **Given** a `--fix` run that quarantines ≥1 row, **When** it completes, **Then** the output names the manifest path, the quarantine path, the count of quarantined rows, and instructs the operator to commit them.
2. **Given** a `--fix` run that quarantines zero rows, **When** it completes, **Then** the output names the manifest path and states it is tracked-but-uncommitted.
3. **Given** `--fix --json`, **When** it completes, **Then** the machine-readable output carries the audit-trail paths and quarantined-row count (parity with the human summary).

### Edge Cases

- **Repair runs on a dirty tree**: `--fix` writes only; it never commits and never stages, so it cannot entangle with the operator's in-progress work. Two distinct guards are involved and were conflated in early grounding: the **repo-boundary** guard is `_anchor_repair_root` (`mission_state.py:~506-526`, the "would drag the roots onto an enclosing real repo" logic) — it must keep holding for the new path (NFR-003a); the **dirty-path refusal** is `_assert_git_safe` (`mission_state.py:~2611`) — once the root is tracked, the manifest root must be dropped from its checked path-set or a second `--fix` refuses on its own prior output (FR-009/NFR-003b).
- **#2384 interaction (governing)**: the artifacts were *deliberately* gitignored (`state/contract.py` `migration_state_ledger` surface, `git_class=IGNORED`, note: "Ignored so a repair run does not dirty the tree or gate accept (#2384)"). `.gitignore` is *derived from* that contract. Making the root tracked reverses that decision, so it is only safe when the root is simultaneously classified self-bookkeeping churn (FR-008) so `accept`/`merge` still do not gate on a repair's output.
- **The duplicate-key repair flow** (`mission_state.py:904-913`) writes its manifest under the same root and must move with the mission-state repair, or the defect persists on that path.
- **Legacy artifacts already at the old gitignored path**: pre-existing `.kittify/migrations/mission-state/` content is not migrated by this mission; the old path is retired for *new* writes (not dual-written). Out-of-scope for automated migration; noted as an assumption.
- **A custom `--manifest-path`** (the `manifest_path` parameter, `mission_state.py:713`) supplied by a caller is honored as-is and not forced under the tracked root.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Relocate manifest to a tracked path | As an operator, I want the per-run repair manifest written to a version-controllable path (not under gitignored `.kittify/migrations/`) so that it survives `git clean`. | High | Open |
| FR-002 | Relocate quarantine tree to a tracked path | As an operator, I want the verbatim quarantined rows written under the same tracked audit root so that removed data survives `git clean`. | High | Open |
| FR-003 | Retire the gitignored write for these artifacts | As an operator, I want the mission-state and duplicate-key repair flows to stop writing these artifacts to a gitignored location so that no repair record can land where git will discard it. | High | Open |
| FR-004 | Exit summary naming written artifacts | As an operator, I want `--fix` to print, on completion, the manifest path (always) and the quarantine path + quarantined-row count (when rows were quarantined), marked tracked-but-uncommitted with a commit instruction. | High | Open |
| FR-005 | `--json` parity for audit-trail paths | As a tooling author, I want the audit-trail paths and quarantined-row count in `--fix --json` output so that automation has the same visibility as the terminal summary. | Medium | Open |
| FR-006 | Cover the duplicate-key repair flow | As an operator, I want the duplicate-key repair manifest relocated on the same terms so that the durability guarantee is not path-specific. | Medium | Open |
| FR-007 | Update the canonical state contract | As a maintainer, I want the `migration_state_ledger` StateSurface in `state/contract.py` re-pointed to the tracked audit root with git-class `TRACKED` (or `INSIDE_REPO_NOT_IGNORED`) so that the SSOT that *derives* `.gitignore` and drives traceability tests matches reality — not a `.gitignore` hand-edit (the ignore is generated from the contract). | High | Open |
| FR-008 | Register the audit root as self-bookkeeping churn | As an operator, I want a `--fix` run's tracked-but-uncommitted audit artifacts recognized as self-bookkeeping churn by the accept/merge/record-analysis dirty-tree preflight (`is_self_bookkeeping_churn` + the acceptance/merge filters that consult it) so that a repair never gates `accept` or `merge` — preserving the workflow property #2384 established, now via classification instead of a gitignore. | High | Open |
| FR-009 | Remove the audit root from the `_assert_git_safe` checked set | As an operator, I want the manifest root dropped from the paths passed to `_assert_git_safe` (`mission_state.py:716,908`) so that a second consecutive `--fix` does not refuse on its own prior uncommitted output once that output is tracked (the append is inert only while the path is ignored). | High | Open |
| FR-010 | Repoint the architectural archive/exclusion ratchets | As a maintainer, I want the three ratchets that pin the old quarantine root as an immutable/shrink-only/upgrade-preserved archive (`test_archive_root_byte_identical.py`, `test_transition_guard_shrink_only.py`, `test_upgrade_recovery_preservation.py`) updated to the new root, with a conscious decision recorded on whether the relocated, reviewable trail inherits DM-governed immutable-audit status (default: no — it is operator-committed/reviewable). | Medium | Open |
| FR-011 | Reconcile `_POLICY_TRACKED` | As a maintainer, I want `_POLICY_TRACKED` (`mission_state.py:85-89`) re-pointed off the previously-ignored path to the tracked audit root so that the repair's own tracked-policy declaration is coherent. | Medium | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Repair remains non-git-mutating | `--fix` performs zero git operations (no add, stage, or commit) as part of writing the audit trail; a repair run leaves the git index unchanged apart from the new untracked/tracked-location files on disk. | Reliability | High | Open |
| NFR-002 | No canonicality regression | This mission changes no row-classification behavior: `AUTHORITATIVE_NON_LANE_EVENT_TYPES`, `is_non_lane_event`, and `_is_preserved_non_lane_row` are untouched; the #4897 regression tests remain green. | Reliability | High | Open |
| NFR-003a | Repo-boundary anchoring preserved | The repo-boundary guard `_anchor_repair_root` (`mission_state.py:~506-526`) continues to prevent the audit roots being written onto an enclosing real repository, verified for the new tracked path. | Security | High | Open |
| NFR-003b | Dirty-path refusal behavior corrected | `_assert_git_safe` (`mission_state.py:~2611`, `git status --porcelain -- <paths>`) must not refuse a repair because of the repair's own prior uncommitted audit output on the now-tracked root; two consecutive `--fix` runs succeed without `--allow-dirty`. | Reliability | High | Open |
| NFR-005 | Accept/merge remain ungated by a repair | After a `--fix` run that writes tracked-but-uncommitted audit artifacts, `spec-kitty accept` / `merge` / `agent mission record-analysis` do not refuse on those artifacts (they are classified self-bookkeeping churn) — the #2384 property holds. | Reliability | High | Open |
| NFR-004 | Exit-summary overhead | The added summary and `--json` fields impose no measurable wall-clock regression on a repair run (no extra filesystem scan; data already computed by the repair). | Performance | Low | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Placement/visibility seam only | The change touches only WHERE artifacts are written and HOW the operator is told; it must not alter WHICH rows are preserved or quarantined (the #4897 registry seam). | Technical | High | Open |
| C-002 | Write-only, operator commits | `--fix` writes the audit trail to the tracked path but does not commit it; durability is realized when the operator commits, as instructed by the exit summary. | Technical | High | Open |
| C-003 | No automated migration of legacy artifacts | Pre-existing artifacts under the old gitignored path are left in place; this mission points *new* writes at the tracked root only. | Technical | Medium | Open |
| C-004 | Ground on post-#4938 main | Implementation branches off `main` after PR #4938 merged, to avoid a same-file rebase against `mission_state.py`. | Process | Medium | Open |
| C-005 | Keep the legacy `.kittify/migrations/` ignore | The existing `.kittify/migrations/` gitignore entry (and the `m_3_2_4` runtime-dirs backfill migration that emits it) must remain so legacy projects' old ignored trails stay ignored; this mission *adds* a tracked root, it does not un-ignore the old tree. | Technical | High | Open |
| C-006 | #2384 property preserved via classification | Reversing #2384's gitignore is only acceptable because the tracked root is simultaneously classified self-bookkeeping churn (FR-008); a repair must never gate `accept`/`merge`. Losing that classification is a regression, not a simplification. | Technical | High | Open |

### Key Entities

- **Repair manifest**: the per-run record (`run_id`, per-mission slug + reason, quarantined-row count, file changes) describing what a `--fix` run did. Written every run.
- **Quarantine artifact**: the verbatim copy of rows the repair removed from `status.events.jsonl`, keyed by `run_id` and mission slug. Written only when rows are quarantined.
- **Audit root**: the version-controllable directory that replaces the gitignored `MANIFEST_ROOT` as the home for both artifact classes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After any `--fix` run, `git check-ignore` reports the written manifest (and quarantine artifacts, when present) as **not ignored** — 100% of runs, both the mission-state and duplicate-key flows.
- **SC-002**: After a `--fix` run followed by `git clean -xfd` on the fixture, the manifest and quarantine artifacts still exist — 100% of runs (the current behavior is 0%).
- **SC-003**: Every `--fix` completion (quarantining or not) emits an operator-visible line naming the manifest path; every quarantining run additionally names the quarantine path and count with a commit instruction — verified for both human and `--json` output.
- **SC-004**: The #4897 canonicality regression suite (`tests/status/test_authoritative_non_lane_registry_4897.py`, `tests/integration/migration/test_lifecycle_events_preserved.py`) remains green, confirming zero canonicality regression.
- **SC-005**: After a `--fix` run that writes tracked-but-uncommitted audit artifacts, `spec-kitty accept` and `spec-kitty merge` do not refuse on those artifacts (100% of runs) — the #2384 non-gating property holds via self-bookkeeping-churn classification, and two consecutive `--fix` runs succeed without `--allow-dirty`.
