# Mission Specification: Nightly Suites Green — coord & charter rework fallout

**Mission Branch**: `fix/nightly-suites-green-rework`
**Created**: 2026-10-10
**Status**: Draft
**Input**: Restore the nightly suites to green after the large `next` coordination and doctrine-to-charter reworks (upstream nightly run 38021225055). Groups five P0 issues #5987–#5991 (25 failing tests).

## Intent Summary *(confirmed)*

- **Primary actors**: the nightly CI (the authoritative 4.0.0 release gate) and the maintainers who read it; and the agents that run *owned-checkout* missions, whose create/next walk regressed.
- **Trigger**: nightly run `38021225055` escalated five P0 issues (25 failing tests) after two large internal reworks — the `next` coordination/mission-lock seam and the doctrine-to-charter cutover.
- **Desired outcome**: all 25 tests pass; the five suites go green on the nightly runner, restoring an honest release gate — *without green-washing* (no reverting honest reds, no relaxing a check that guards real behavior).
- **Load-bearing rule**: the one genuine product regression (owned mission create/next re-derives the canonical/main repo root, breaching the owned-checkout boundary) is fixed in the **code**; the remaining failures are test-reality drift, CI-environment/corpus artifacts, a stale derived artifact, a doc-sync gap, and a perf import regression + an operator-owned calibration decision — each fixed at its true root.
- **Canonical boundary term**: *owned checkout* (`P`) is self-contained; the repository root / canonical root (`R`) must stay byte-identical and must not be re-derived from inside `P`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Owned mission create/next no longer touches the main repo root (Priority: P1)

An agent runs a mission in an *owned checkout* (`P`). Creating the mission and advancing its `next` walk must operate entirely within `P`; nothing may re-derive or read the canonical repo root `R`.

**Why this priority**: This is the only genuine product regression in the batch (introduced by the canonical mission-lock rework, commit `f815fc9b66` / #5883). It breaks the owned-checkout ownership boundary the whole `integration` acceptance suite exists to protect, and it is the heart of the operator's steer.

**Independent Test**: The owned-lifecycle acceptance suite (`tests/integration/test_owned_lifecycle_acceptance_{finalize,e2e,review}.py`) — the armed `get_main_repo_root` pin stays clean on an owned create, and the owned `next` walk reaches `implement`/`review` (not `analyze`).

**Acceptance Scenarios**:
1. **Given** an owned-checkout mission create, **When** the `meta.json` birth write acquires the mission write lock, **Then** no call resolves the canonical/main repo root (`passed_through == []`) and the birth write converges on the same lock root as its sibling create writers (seam A).
2. **Given** a finalized/claimed WP in an owned checkout, **When** `next` advances past the `analyze` gate (#5885), **Then** the walk reaches `implement`/`review` — the acceptance tests are primed for the analyze step (sibling pattern), with the ownership and R-unchanged pins intact.
3. **Given** the owned birth-write guard fixture, **When** a birth lock is taken in an owned checkout, **Then** it never resolves the main repo root, while the no-`birth` positive control on the same fixture does — proving the guard is non-vacuous.

---

### User Story 2 — Test/CI artifacts classify correctly without weakening production checks (Priority: P1)

Failures that are environment- or corpus-state dependent (not product bugs) are fixed by hardening the *test/oracle* to match correct production behavior — never by relaxing expected results.

**Why this priority**: These reds block the release gate but misattributing them to product code would either green-wash a real check or waste effort. Correctly classified, they are cheap, surgical test fixes.

**Independent Test**: `test_cli_boundary_context.py::test_non_project_context_errors_are_json` (×4) passes regardless of where pytest's basetemp lives; `test_mission_status_reality.py` corpus tests agree with the resolver when remotes are online.

**Acceptance Scenarios**:
1. **Given** the non-project context test, **When** it runs with a basetemp that happens to sit inside the repo checkout, **Then** it still proves `not_in_project` because the test guarantees its cwd has no enclosing project ancestor (production resolution is unchanged and correct).
2. **Given** a coordination branch that is absent locally but live on an online remote, **When** the corpus reality test compares scan vs oracle, **Then** the oracle mirrors the resolver's live-remote authority and both agree the branch is present (not a deleted-coordination fallback).

---

### User Story 3 — Drifted, stale, and undocumented surfaces realigned to reality (Priority: P2)

Tests, derived artifacts, and docs that drifted from current behavior are realigned at their true source.

**Why this priority**: Clear, low-risk corrections that restore the remaining suites; each still gets a red-first repro and keeps the quality bar.

**Independent Test**: the git-redaction, implement-template, pinning-inventory, and terminology-exemption tests pass, each exercising the real production/derivation path.

**Acceptance Scenarios**:
1. **Given** git stderr that carries an injected `oauth2:<token>@` URL on the actual clone seam, **When** a clone fails, **Then** the surfaced error shows `oauth2:<redacted>@` and never the raw token (positive control: with no token, no raw token leaks either).
2. **Given** the implement command-template, **When** the occurrence-classification verification runs, **Then** the template's verification guidance and its pinning test agree on the canonical `command-templates` path (fix at the SOURCE template).
3. **Given** the pinning-rule tree, **When** the inventory is re-derived, **Then** the committed inventory equals the fresh derivation with the new `retiring-step` rule explicitly dispositioned (not regenerated away).
4. **Given** `FORBIDDEN_SCAN_ROOTS`, **When** the terminology-exemption policy doc is checked, **Then** it documents every `docs/` exempt root including `docs/archive/`.

---

### User Story 4 — `spec-kitty --help` starts within budget, honestly (Priority: P2)

The `--help` startup path does not eagerly import the heavy charter-activation / runtime-schema / status chains it does not need.

**Why this priority**: A real import regression from the two named reworks ate the startup headroom; the fix shaves the imports at root. The final budget number is an operator/CI-owned calibration decision, measured on the nightly runner.

**Independent Test**: an import-absence test proves the named heavy modules are not imported on `spec-kitty --help`; the startup-budget test passes on the nightly runner.

**Acceptance Scenarios**:
1. **Given** `spec-kitty --help`, **When** the CLI app is built, **Then** the `runtime.next.decision` / `charter.activation.*` / `runtime.next._internal_runtime.schema` / `status.dup_key_repair` chains are not eagerly imported (deferred into command bodies).
2. **Given** the startup-budget test on the nightly runner, **When** it measures the `--help` ratio, **Then** it is within the operator-confirmed limit, and the limit was not merely raised to mask an un-shaved regression.

## Requirements

### Functional Requirements

| ID | Requirement | Status | Delivery | No-op passable? |
|----|-------------|--------|----------|-----------------|
| FR-001 | Owned-checkout mission create must anchor its `meta.json` birth-write lock on the owned checkout root and must not resolve the canonical/main repo root (`resolve_canonical_root`/`get_main_repo_root`) during create. (#5988 sub-cluster A) | Required | [build] | no |
| FR-002 | An owned-checkout `next` walk must see finalized/claimed WP progression (reach `implement`/`review`), not reset to `analyze`. Verified at implement: this was NOT a status write-target redirect (`canonicalize_feature_dir` is uninvolved) but acceptance tests not updated for the `analyze` DAG step added by #5885; re-primed to the sibling pattern with ownership / R-unchanged pins intact. (#5988) | Required | [ratchet] | no |
| FR-003 | Non-vacuous behavioral guards pin the owned birth-write seam: (a) `_write_create_meta` plumbs the owned `write_root` into its lock; (b) an owned-checkout birth lock never resolves the main repo root. Each carries a same-fixture positive control (the no-`write_root` / no-`birth` path DOES resolve it). (#5988) | Required | [build] | no |
| FR-004 | The git-source credential-redaction property is pinned through the real clone seam (`clone_repository`): an injected token never appears unredacted in a surfaced error, and `oauth2:<redacted>@` appears when git stderr carries the token. (#5987) | Required | [ratchet] | no |
| FR-005 | The non-project context CLI commands report `not_in_project` outside any project, pinned by a test that guarantees its cwd has no enclosing project ancestor independent of pytest basetemp location; expected error codes are not weakened. (#5989) | Required | [ratchet] | no |
| FR-006 | The mission-status reality corpus oracle mirrors the resolver's live-remote presence authority (the `ls-remote` arm) so scan and oracle agree on coordination-branch-deleted classification when remotes are online. (#5990) | Required | [ratchet] | no |
| FR-007 | The implement command-template verification guidance and its occurrence-classification pinning test agree on the canonical `src/specify_cli/missions/*/command-templates/` reference, fixed at the SOURCE template (not an agent copy). (#5989) | Required | [ratchet] | no |
| FR-008 | The pinning-rule inventory is reproducible: the committed `tests/release/pinning_rule_inventory.json` equals a fresh `derive_pinning_inventory.py` run, with the new `retiring-step` rule explicitly dispositioned. (#5989) | Required | [ratchet] | no |
| FR-009 | The terminology-exemption policy doc documents every `docs/` exempt root in `FORBIDDEN_SCAN_ROOTS`, including `docs/archive/`. (#5990) | Required | [ratchet] | no |
| FR-010 | The `spec-kitty --help` startup path defers the module-scope `runtime.next.decision` / `runtime.next._runtime_pkg_notice` imports (and the charter-activation / runtime-schema / status chains they pull), pinned by a test asserting those modules are absent from the `--help` import set. (#5991) | Required | [build] | no |
| FR-011 | The `spec-kitty --help` startup-budget test passes on the nightly runner at an operator-confirmed ratio limit. | Required | [ratchet] | yes — positive control: FR-010's import-absence assertion proves the shave is real, so the budget is not satisfied by a bare limit bump. |

### Non-Functional Requirements

| ID | Requirement | Status | Threshold |
|----|-------------|--------|-----------|
| NFR-001 | All originally-failing tests pass after the mission. | Required | 25/25 of the run-38021225055 failures green; the five suites (interpreter-3.13-shard-3/4/5, integration, performance) green on the nightly runner. |
| NFR-002 | No previously-passing test regresses. | Required | Targeted blast-radius + each owning subsystem directory green; zero new reds attributable to the diff (classified against the merge-base). |
| NFR-003 | `spec-kitty --help` startup stays within budget on the nightly runner. | Required | ratio ≤ the operator-confirmed limit (default `STARTUP_RATIO_LIMIT = 2.90`). |
| NFR-004 | Every defect fix is red-first. | Required | WP01 (#5988), WP02 (#5987), and WP08 (#5991) create genuine new issue-pinned `@pytest.mark.regression` repros, RED on the WP base and GREEN on the fix (transitional repros demoted after). The drift/CI/derived/doc WPs (WP03/WP04/WP05/WP06/WP07) legitimately use the **pre-existing failing nightly test as the red-first pin** — no new `@regression` marker is required; the obligation is to show it RED on the base for the right reason and GREEN after. |

### Constraints

| ID | Constraint | Status |
|----|------------|--------|
| C-001 | Fix the ownership-boundary regression (#5988) in the CODE; do not relax the owned-lifecycle acceptance pins — they guard a real boundary. | Required |
| C-002 | CI-environment and corpus artifacts (#5989 context-errors, #5990 corpus) are fixed by hardening the test/oracle to match correct production/resolver behavior — never by relaxing expected codes or pruning remotes. | Required |
| C-003 | The pinning inventory's new rule must be dispositioned, never regenerated-away. | Required |
| C-004 | Edit SOURCE templates under `packs/built-in/`, never generated agent copies. | Required |
| C-005 | The final perf budget value is an operator-owned calibration decision measured on CI; it is not set from a local timing series. | Required |
| C-006 | Terminology canon holds (Mission, not Feature); no retired terms (`ceremony`, `status-writing`) are introduced. | Required |

### Success Criteria

- **SC-001**: The nightly run for the mission branch is green across all five previously-red suites. — [ratchet] · no-op passable: no
- **SC-002**: Each of #5987–#5991 has a red-first regression repro committed that fails on the base and passes on the fix. — [build] · no-op passable: no
- **SC-003**: An owned mission create and `next` walk complete without resolving the main repo root (boundary guard holds under a self-mutation test). — [build] · no-op passable: no
- **SC-004**: No new terminology/legacy-term regression and docs freshness is clean after any doc/ADR change. — [ratchet] · no-op passable: no

## Key Entities

- **Nightly suite** — one CI shard/lane (`interpreter-3.13-shard-3/4/5`, `integration`, `performance`); each maps to one P0 issue and one or more failing tests.
- **Owned checkout (`P`) vs canonical root (`R`)** — the ownership boundary the #5988 fix restores.
- **Resolver vs oracle** — two independent derivations of mission-status reality whose remote-presence authority must agree (#5990).
- **Derived artifact** — the pinning-rule inventory, reproducible from the tree (#5989).

## Assumptions

- The five issues are all fallout of run `38021225055`; none is superseded (confirmed: all OPEN, P0, milestone 4.0.0, no closing PR/ADR).
- The ownership-boundary regression originates from the canonical mission-lock rework (commit `f815fc9b66`, context #5883); #5883 is a context-only reference (non-gating), not a work-owing issue for this mission.
- The `integration` cluster is one root cause (#5883) with two manifestation sub-clusters; sub-cluster B is attributed by commit provenance + shared symptom and will be line-traced during implement.
- The `performance` budget limit may need a CI-measured bump even after the import shave; that number is confirmed by the operator against the nightly runner, not set locally.

## Issue References

Gating (issue-matrix row + claim + verdict required): **#5987, #5988, #5989, #5990, #5991**.
Context-only (non-gating): #5883 (introducing rework), run 38021225055.
