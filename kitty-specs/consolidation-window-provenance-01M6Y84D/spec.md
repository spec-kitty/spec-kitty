# Mission Specification: Consolidation window provenance and reconciliation split

**Mission Branch**: `kitty/mission-consolidation-window-provenance-01M6Y84D`  
**Created**: 2026-11-08  
**Status**: Draft  
**Input**: Confirmed intent (operator, 2026-11-08) for #7403, parent sub-epic #7358: the consolidation gate judges each approved work package against its recorded review window, and the forecast (`consolidate --dry-run`), a fresh run and a resume (`consolidate --resume`) feed the gate the same inputs, so they reach the same verdict on the same state. The window-open SHA is recorded on status transition events; the lane path adopts the window model; a work package with no recorded window falls back to today's approval-stamp bound and is reported as a window gap; two fail-open defects are fixed red-first; and the 4,096-line reconciliation module is split by verification check without changing a verdict.

## User Scenarios & Testing *(mandatory)*

The actor in every story is a maintainer or an orchestrator running `spec-kitty consolidate` (fresh run), `spec-kitty consolidate --dry-run` (forecast) or `spec-kitty consolidate --resume` (resume) on a Mission, or moving a work package through its lifecycle with the status commands.

### User Story 1 - The work-package window is recorded when it opens (Priority: P1)

When a work package on a lane starts work, the status event that records the move also records the window-open SHA: the head of the work package's lane at that moment. When the SHA cannot be read, the event records an explicit window gap with a reason instead of leaving the value out. The move itself always succeeds.

**Why this priority**: Every other behaviour change in this Mission reads this recorded value. Without it, the gate keeps reconstructing windows from branch history after the fact, which is the root cause of the recurring fixes in the reconciliation module.

**Independent Test**: Move a work package of a lane Mission from `planned` to `claimed` and `in_progress`, then read the status event log. The opening event carries the window-open SHA under the namespaced key. Repeat with the lane branch deleted: the event carries a typed window gap with a reason, and the move still succeeds.

**Acceptance Scenarios**:

1. **Given** a lane Mission whose lane branch exists, **When** a work package makes its first non-migration move into `claimed` or `in_progress`, **Then** that status event records the lane head as the window-open SHA under the namespaced key, and the value equals the lane branch tip at that moment.
2. **Given** a lane Mission whose lane branch cannot be read, **When** a work package makes the same move, **Then** the move succeeds, and the status event records a window gap with a reason naming why the SHA could not be read.
3. **Given** a work package moved to `blocked` before any work started, **When** the event log is read, **Then** the `blocked` move has opened no window (the approval-window opener rule), and a later move into `in_progress` opens it.
4. **Given** a status event written by a migration actor (`migration:` prefix), **When** it records a lifecycle move, **Then** it opens no window and records no window-open SHA.

---

### User Story 2 - A commit made between two approvals on a lane is refused (Priority: P1)

A lane carries two work packages. WP01 is approved, then someone commits to the lane, then WP02 starts work and is approved. Today the gate accepts the stray commit because WP02's approval stamp reaches it. With the window model applied to lanes, each approved work package covers only its own window, so the stray commit lies in no window and the gate refuses it before anything lands (closes the commit-between-two-approvals residual of #5721).

**Why this priority**: This is the soundness gap the window model exists to close. An unreviewed commit can land today with exit 0.

**Independent Test**: Build a lane Mission with the WP01-approve / stray-commit / WP02-open / WP02-approve history and run `consolidate`. It refuses with `LANE_MOVED_AFTER_APPROVAL`, names the stray commit and WP01 (the work package approved before it), and moves no branch. Remove the stray commit from the same fixture: the run passes.

**Acceptance Scenarios**:

1. **Given** a lane whose WP01 was approved, followed by a commit, followed by WP02 opening its window and being approved, **When** `consolidate` runs, **Then** it refuses with `LANE_MOVED_AFTER_APPROVAL`, names the commit and WP01, and the target branch is unchanged.
2. **Given** the same fixture without the stray commit, **When** `consolidate` runs, **Then** no window refusal is raised.
3. **Given** a lane where a reviewer committed a fix while WP02 was `in_review` and WP02 was then approved, **When** `consolidate` runs, **Then** the fix lies inside WP02's window and is not refused (unchanged from today).
4. **Given** a WP that was rejected and re-approved, **When** `consolidate` runs, **Then** its window runs from its window-open SHA to its newest approval stamp, and commits inside it are not refused.
5. **Given** the same stray-commit fixture, **When** `consolidate --dry-run` runs, **Then** the forecast reports the same refusal and code as the fresh run.

---

### User Story 3 - A work package without a recorded window still consolidates and is reported (Priority: P1)

Missions that were in flight when this ships, and work packages whose capture failed, have no recorded window. The gate judges such a work package with today's approval-stamp bound and the output names it as a window gap. It is never refused for the missing window alone.

**Why this priority**: The upgrade must not strand Missions that are mid-flight or mid-consolidation, and the operator must be able to see which work packages got the weaker check.

**Independent Test**: Take a lane Mission whose events carry no window-open SHA (written before this Mission ships) and run `consolidate`. The verdict equals today's verdict on the same fixture, and the output lists each work package judged by the fallback with the reason "not recorded". Repeat with a typed window gap: the reason shown is the recorded one.

**Acceptance Scenarios**:

1. **Given** a lane Mission with no recorded windows and no post-approval commits, **When** `consolidate` runs, **Then** it passes, and the output lists every approved work package as a window gap with reason "not recorded".
2. **Given** a lane Mission with no recorded windows and a commit after WP01's approval stamp that no approval stamp reaches, **When** `consolidate` runs, **Then** it refuses with today's `LANE_MOVED_AFTER_APPROVAL`, exactly as before this Mission.
3. **Given** a Mission whose consolidation was interrupted before this Mission shipped, **When** the operator runs `consolidate --resume` after upgrading, **Then** the resume reaches the verdict it would have reached before the upgrade, and the output adds the window-gap report.
4. **Given** one work package with a recorded window and one without on the same lane, **When** `consolidate` runs, **Then** the first is judged by its window, the second by the approval-stamp bound, and only the second is listed as a window gap.

---

### User Story 4 - Two fail-open defects now fail closed (Priority: P1)

Two known defects let the gate pass something it should refuse:

- (a) While collecting a lane's authored content, any error from a history read is taken to mean "the file was deleted" (the deletion-inference defect of #5048). The gate then trusts a deletion that never happened.
- (b) On `--resume`, the closed-world check reads the dependency lanes' tips from the live branches, not from the tips frozen when the claim was first captured. A dependency lane that moved after the interruption widens the set of exempt commits.

**Why this priority**: Both are soundness defects on the landing path; the operator ruled to fix them in this Mission.

**Independent Test**: For (a), inject a history-read error for one changed path on a lane's spine and run the claim: it refuses and names the read error; a genuine deletion on the same fixture is still recorded as a deletion. For (b), interrupt a consolidation, advance a dependency lane, then resume: the commits added to the dependency lane after the interruption are not exempt; a fresh run on the same fixture without the advance is unchanged.

**Acceptance Scenarios**:

1. **Given** a lane spine where reading one path's content fails with a history-read error, **When** the claim is built, **Then** the run refuses (fail closed), names the path and the read error, and records no deletion for that path.
2. **Given** the same fixture where the path is genuinely deleted at its newest touching commit, **When** the claim is built, **Then** the path is recorded as a deletion (positive control).
3. **Given** a consolidation interrupted after its claim was captured, and a dependency lane that gained a commit afterwards, **When** `consolidate --resume` runs, **Then** the closed-world anchors are the dependency-lane tips frozen at claim capture, and the commit added after the interruption is not exempt.
4. **Given** the same Mission without the post-interruption commit, **When** `consolidate --resume` runs, **Then** the verdict equals the fresh run's verdict.

---

### User Story 5 - Forecast, fresh run and resume reach the same verdict on the same state (Priority: P2)

All three modes build the gate's claim from one set of claim inputs with one construction point and three sources: live (forecast), live then saved (fresh run), and saved (resume). On a repository state that nothing has mutated, the three produce equal claim inputs and the same claim-time verdict.

**Why this priority**: The forecast today passes a live coordination base and no excluded canceled work packages, and resume reads saved anchors, so the three can disagree on the same state. Parity is what lets an operator trust a forecast.

**Independent Test**: For each scenario of the characterization corpus where all three modes apply, run the forecast, a fresh run, and a resume of an interrupted run started on the same state. Compare their claim inputs and claim-time verdicts.

**Acceptance Scenarios**:

1. **Given** an unmutated Mission state, **When** the forecast and a fresh run build their claim inputs, **Then** the inputs are equal field by field.
2. **Given** a fresh run that saved its claim inputs and was interrupted before any branch moved, **When** `consolidate --resume` runs, **Then** it reads the saved inputs, and its claim-time verdict equals the fresh run's.
3. **Given** a Mission with an excluded canceled work package, **When** the forecast runs, **Then** it uses the same excluded set as the fresh run, and reports the same claim-time refusal or pass.

---

### User Story 6 - The reconciliation module is split by check without changing a verdict (Priority: P2)

A maintainer who needs to change one verification check finds it in one module. The split happens behind a re-exporting facade after a characterization corpus, a refusal-precedence matrix and a surface pin are in place, and none of them changes.

**Why this priority**: 75% of the module's recent commits are fixes, and every new check was added by editing one orchestrating function. The split is what lets later Missions switch one check at a time. It is P2 because it delivers no new behaviour by itself.

**Independent Test**: Run the characterization corpus, the refusal-precedence matrix and the surface pin before and after the split; outputs are identical. Run a seeded mutation in each moved check: at least one corpus scenario goes red for each.

**Acceptance Scenarios**:

1. **Given** the characterization corpus recorded before the split, **When** it runs after the split, **Then** every scenario's verdict status, refusal code, divergence fields and exit code are byte-identical.
2. **Given** the surface pin recorded before the split, **When** it runs after the split, **Then** every name importable from the reconciliation module is still importable and is the same object as at its new home.
3. **Given** a test that replaces a reconciliation-family name to intercept a call, **When** the name has moved, **Then** the replacement is applied where the name is looked up, and a guard fails if a replaced name is not looked up in the module replaced.
4. **Given** any two claim-time refusals that can occur together, **When** both conditions are present, **Then** the refusal text and its order equal the pre-split precedence matrix.

---

### Edge Cases

- **Mission mid-consolidation at ship time**: saved state, no recorded windows. Resume falls back to the approval-stamp bound for every work package, reports each as a window gap, and is never refused for that alone (US3-3).
- **Window opened before upgrade, approved after**: the opening event carries no window-open SHA, so the work package has no recorded window and falls back, reason "not recorded". The window-open SHA is never re-derived from older stamps on the lane path.
- **Capture failure**: lane branch missing or the history read fails at the opening move. The event records a typed window gap; the move succeeds; the gate falls back and shows the recorded reason.
- **Recorded window-open SHA not on the lane's history** (lane rewritten): treated as a window gap with reason "not on lane"; the fallback approval-stamp bound then applies its existing rewritten-lane refusal. No new refusal code.
- **Migration events**: never open or close a window (the migration-actor rule of ADR `2026-09-29-1-closed-world-refuse-on-mixed-lanes` stays binding).
- **`blocked` before work started**: opens no approval window. The closed-world lane anchor still counts `blocked` as an opener; the ADR names this as a deliberate variant and neither verdict changes.
- **Rework**: a rejected then re-approved work package keeps its first window-open SHA and closes at its newest approval stamp.
- **Attested approval** (`--attest-approved-reviewed`): its lane head stays the work package's approval stamp; the window runs from the recorded window-open SHA to it.
- **Mixed lane with a canceled work package**: the canceled work package's commits keep today's mixed-lane rules; the window model covers approved work packages only.
- **Planning lanes**: not windowed and not bounded (unchanged).
- **`single_branch` Missions**: already judged by approval windows derived from stamps. They read the recorded window-open SHA when present, keep today's derivation when absent, and report the absence as a window gap.
- **Lane-id rebuild** after execution began would orphan recorded windows; out of scope (see #5703).

## Domain Language

| Canonical term | Meaning in this Mission | Avoid |
|----------------|------------------------|-------|
| Mission | The unit of planned work that is specified, implemented and consolidated. | "feature" |
| Consolidate / lane consolidation | `spec-kitty consolidate`: lands approved lane work onto the local target branch. | bare "merge" (name the sense); "publish" |
| Fresh run | A `consolidate` run that starts with no saved consolidation record. | "real run", "normal merge" |
| Forecast | `consolidate --dry-run`: computes the verdict without mutating anything. | "preview", "simulation" |
| Resume | `consolidate --resume`: continues an interrupted run from its saved record. | "retry", "re-run" |
| Work-package window | The span of lane history a work package is accountable for: from its window-open SHA (exclusive) to its newest approval stamp (inclusive). | "work window" for this sense (the canceled-content implementation/review windows are a named variant), "WP range" |
| Window-open SHA | The lane head recorded on the status event of a work package's first non-migration move into `claimed` or `in_progress`. | "open stamp", "base SHA", "fork point" |
| Approval stamp | The lane head recorded on a work package's newest non-migration approval transition (existing term, ADR `2026-10-04-5-approval-stamp-bounds-the-approved-claim`). | "lane_head" when the approval sense is meant |
| Window gap | The explicit, typed absence of a recorded window for a work package: "not recorded" (no value on the event), "capture failed" (with the recorded reason) or "not on lane". | "missing stamp" (that is `APPROVAL_STAMP_MISSING`, a different refusal) |
| Gap report | The part of the consolidate output that lists every work package judged by the fallback and its window-gap reason. | "warning list" |
| Claim inputs (`ClaimInputs`) | The one set of values the gate's claim is built from: target base, coordination base, frozen lane tips, frozen dependency anchors, dependency pins, excluded canceled work packages and strategy. | "claim args", "gate params" |
| Claim base | The target branch's tip before the run mutated anything; the lower bound of the approved claim. | "merge base", "coord base" (a different input) |
| Named window variant | A deliberate difference between window definitions that the ADR records by name (e.g. whether `blocked` opens a window). | "exception", "special case" |
| Characterization corpus | The table of scenarios with their recorded verdict (status, refusal code, divergence fields, exit code) per mode, pinned before the split. | "golden tests" without the verdict fields |

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | ADR records the window model | As a maintainer, I want an ADR amending `2026-10-04-5-approval-stamp-bounds-the-approved-claim` and `2026-09-29-1-closed-world-refuse-on-mixed-lanes` that states where the window-open SHA is recorded (a namespaced key on status transition events), the typed window gap, the claim inputs and their three sources, the durability horizon (one consolidation attempt, not after landing), the missing-window fallback, and a table mapping every existing window definition to the one window model or to a named window variant, so that later changes to a check follow one recorded rule. | High | Open | [build] | no |
| FR-002 | Window-open SHA recorded on the opening event | As an orchestrator, I want the status event of a lane-mapped work package's first non-migration move into `claimed` or `in_progress` to record the lane head as the window-open SHA under the namespaced key, so that the gate reads the window instead of reconstructing it. | High | Open | [build] | no |
| FR-003 | Failed capture is a typed window gap | As an orchestrator, I want a capture that cannot read the lane head to record a window gap value with a reason on the same event, and the move to succeed, so that "capture failed" is distinguishable from "never recorded". | High | Open | [build] | no |
| FR-004 | Readers accept mixed event logs | As an operator, I want an event without the namespaced key read as window gap "not recorded", per event, so that a Mission whose log straddles the upgrade still consolidates. | High | Open | [build] | no |
| FR-005 | Recorded SHA is classified as branch-relative | As a maintainer, I want the new SHA-bearing key classified as branch-relative provenance in the dossier SHA registry, so that the architectural SHA-provenance gate passes and the key is never treated as a post-landing record. | Medium | Open | [build] | no |
| FR-006 | Cross-repository writer issue filed | As a maintainer, I want a spec-kitty-events issue that asks the write service to adopt and type the same key, linked from the ADR, so that the second writer does not drop or rename it. | Medium | Open | [build] | no |
| FR-007 | Lane path judges approved work packages by their windows | As an operator, I want each approved work package on a code lane with a recorded window covered only by its window, and a lane commit outside every approved window refused with `LANE_MOVED_AFTER_APPROVAL` naming the commit and the work package approved before it, so that a commit made between two approvals cannot land (#5721). | High | Open | [build] | no |
| FR-008 | Commits inside windows still pass | As an operator, I want a lane whose commits all lie inside approved windows (including a reviewer's fix during review and rework before re-approval) to raise no window refusal, on the same fixture as FR-007 minus the stray commit, so that the window model does not over-refuse. | High | Open | [ratchet] | yes — paired with FR-007 on the same fixture |
| FR-009 | Missing window falls back to the approval-stamp bound | As an operator, I want a work package with a window gap judged by today's approval-stamp bound and never refused for the gap alone, so that in-flight Missions and failed captures still consolidate with today's verdict. | High | Open | [build] | no |
| FR-010 | Gap report in the consolidate output | As an operator, I want the fresh-run, resume and forecast output (human and machine-readable) to list every work package judged by the fallback with its window-gap reason, so that I can see which work packages got the weaker check. | High | Open | [build] | no |
| FR-011 | `single_branch` reads the recorded window when present | As an operator, I want a `single_branch` Mission to use the recorded window-open SHA when present and keep today's derivation (reported as a window gap) when absent, so that both topologies use one window model without changing today's `single_branch` verdicts. | Medium | Open | [build] | no |
| FR-012 | One construction point for claim inputs | As an operator, I want the forecast, the fresh run and the resume to obtain their claim inputs from one construction point with three sources (live; live then saved; saved), so that the three modes cannot feed the gate different inputs. | High | Open | [build] | no |
| FR-013 | Forecast, fresh run and resume parity | As an operator, I want equal claim inputs and the same claim-time verdict from the forecast, a fresh run, and a resume of an interrupted fresh run on the same unmutated state, for every characterization scenario where all three apply, so that I can trust the forecast. | High | Open | [build] | no |
| FR-014 | History-read error is never a deletion | As an operator, I want a history-read error while collecting a lane's authored content to refuse the claim, naming the path and error, instead of recording a deletion, while a genuine deletion on the same fixture is still recorded (#5048), so that a read failure cannot pass the gate. | High | Open | [build] | no |
| FR-015 | Resume uses frozen dependency-lane tips | As an operator, I want the closed-world check on `--resume` to anchor on the dependency-lane tips frozen at claim capture, so that a dependency lane that moved after the interruption does not widen the exempt commits; a fresh run on the same fixture keeps its verdict. | High | Open | [build] | no |
| FR-016 | Characterization corpus lands first | As a maintainer, I want a verdict matrix over the existing scenario builders (mode × lane shape × stamp state, including the known strict-`xfail` residuals) that records verdict status, refusal code, divergence fields and exit code, merged before any code moves, so that the split has a byte-level witness. | High | Open | [ratchet] | yes — paired with NFR-008 seeded mutations on the same fixtures |
| FR-017 | Refusal-precedence matrix lands first | As a maintainer, I want a table-driven pin of the claim-time refusal text and order for every pair of refusals that can occur together, merged before any code moves, so that the split cannot reorder refusals unnoticed. | High | Open | [ratchet] | yes — paired with a deliberately swapped-order control on the same fixture |
| FR-018 | Surface pin lands first | As a maintainer, I want a pin of every name importable from the reconciliation module (public names and the private names reached by source and tests) and of each name's object identity, merged before any code moves, so that a missed re-export fails in one place. | High | Open | [ratchet] | yes — paired with a control asserting a removed name fails the pin |
| FR-019 | Split by verification check behind a facade | As a maintainer, I want the reconciliation logic divided into one module per verification check, a shared kernel, and the verifier and claim orchestration, with the reconciliation module re-exporting every pinned name, so that one check can be changed in one module. | High | Open | [build] | no |
| FR-020 | Test interception follows moved names | As a maintainer, I want every test that replaces a reconciliation-family name to replace it where it is looked up, guarded by a check that fails when a replaced name is not looked up in the replaced module, so that no test goes silently vacuous after the split. | High | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Split changes no verdict | 0 differences in verdict status, refusal code, divergence fields or exit code across 100% of characterization-corpus scenarios between the pre-split and post-split runs. | Reliability | High | Open |
| NFR-002 | Behaviour changes are bounded and red-first | Corpus verdicts change only in scenarios covered by FR-007, FR-014, FR-015 or the forecast input alignment of FR-013; each such change has a test committed failing before its fix and passing after; 0 other corpus verdicts change. | Reliability | High | Open |
| NFR-003 | Module size after the split | The reconciliation facade defines no verification logic (re-exports and the module docstring only); no module produced by the split exceeds 1,200 lines; the largest is at most 30% of the original 4,096 lines. | Maintainability | High | Open |
| NFR-004 | Complexity ceiling | 0 functions added or changed by this Mission exceed cyclomatic complexity 15; no moved function's complexity increases. | Maintainability | High | Open |
| NFR-005 | No new allowlist entries or suppressions | Net 0 new entries in architectural allowlists and exemption registries, and 0 new lint or type-check suppressions, across the Mission diff; formatter and lint gates pass with 0 findings. | Maintainability | High | Open |
| NFR-006 | Capture never blocks a move | 0 status moves refused or failed because the window-open SHA could not be read; recording adds at most 1 lane-head read per status move. | Reliability | High | Open |
| NFR-007 | Window check cost is bounded | The lane window check issues at most 2 history queries per approved work package (one per window edge), independent of the number of commits on the lane, verified by counting queries on a fixture with at least 3 approved work packages. | Performance | Medium | Open |
| NFR-008 | Characterization pins can fail | For each verification check moved by the split, at least 1 seeded mutation of its verdict logic turns at least 1 characterization-corpus scenario red. | Reliability | High | Open |
| NFR-009 | Changed-line coverage | Changed-line coverage of the Mission diff is at least 90%. | Maintainability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Event log is the single authority | Window provenance lives only on status transition events; no separate provenance file, sidecar or second store is introduced. | Technical | High | Open |
| C-002 | Status package stays git-free | The window-open SHA is read by an injected probe at the point where the approval stamp is stamped today; the status transition pipeline itself performs no git reads. | Technical | High | Open |
| C-003 | Python writes now, Java writer out of scope | The Python status shells write the namespaced key in this Mission; changing the Java write service is out of scope beyond filing the issue (FR-006). | Technical | High | Open |
| C-004 | Only named behaviour changes | The split, the claim-inputs extraction and the ADR are behaviour-preserving; only the behaviour changes listed in NFR-002 may change a verdict, each red-first. | Technical | High | Open |
| C-005 | Facade keeps every name | For the life of this Mission, the reconciliation module keeps every name pinned by FR-018 importable by re-export; source consumers and existing tests do not need import edits. | Technical | High | Open |
| C-006 | Claim type and refusal order stay whole | The approved-claim record stays one type, the claim orchestration keeps its refusal order in one place unchanged, and the divergence record with its clause text and order stays whole. | Technical | High | Open |
| C-007 | Authorship and presence move as one slice | The authored-content and approved-content-presence checks move together, keeping their single shared history walk. | Technical | High | Open |
| C-008 | Characterization before movement | FR-016, FR-017 and FR-018 merge before any code moves out of the reconciliation module. | Technical | High | Open |
| C-009 | Rollback authority untouched | No module gains a rollback or branch-restore caller outside the existing rollback authority, and the rollback caller pin stays green (see #7359). | Technical | High | Open |
| C-010 | No new refusal code for a missing window | A window gap introduces no refusal code; existing codes, remedies and attestation flags keep their meaning. | Technical | High | Open |
| C-011 | ADR citations by slug | The ADR and spec cite ADRs by full slug, because several ADRs share a date prefix. | Technical | Medium | Open |
| C-012 | Terminology canon | User-facing text uses "Mission" (never "feature"), and names the sense of "merge" and "primary"; `consolidate` is lane consolidation into the local target branch, never a publish. | Business | Medium | Open |
| C-013 | Targeted test runs only | Mission work runs the changed tests, their owning subsystem directories and the specific architectural gate files implicated; no full heavy suites (NO_FULL_HEAVY_SUITES_IN_MISSION). | Technical | Medium | Open |
| C-014 | Code quality gates | New and moved code passes lint, format and type checks with zero findings, without new suppressions. | Technical | High | Open |

### Key Entities *(include if the mission involves data)*

- **Work-package window**: the span of lane history one approved work package is accountable for; bounded by its window-open SHA and its newest approval stamp; belongs to one work package on one lane.
- **Window-open SHA**: a lane head recorded once per work package, on the event of its first non-migration move into `claimed` or `in_progress`; branch-relative provenance, valid for one consolidation attempt.
- **Approval stamp**: existing lane head recorded on the newest non-migration approval transition; the closing edge of the window and the fallback bound.
- **Window gap**: a typed value meaning "no usable window" with a reason (not recorded, capture failed with reason, not on lane); drives the fallback and the gap report.
- **Claim inputs**: one value built once per run from one of three sources; holds target base, coordination base, frozen lane tips, frozen dependency anchors, dependency pins, excluded canceled work packages and strategy; consumed by claim building and verification.
- **Gap report**: the per-run list of work packages judged by the fallback, each with its window-gap reason, in human and machine-readable output.
- **Characterization corpus**: the scenario-to-verdict table recorded before the split, with the refusal-precedence matrix and the surface pin as companions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of reproduction scenarios where a commit is made on a lane between two approvals, consolidation refuses before any branch moves (0% today). — [build] · no-op passable: no
- **SC-002**: 0 Missions in flight at upgrade are refused solely because their windows were not recorded, and 100% of work packages judged by the fallback are named with a reason in the run output. — [build] · no-op passable: no
- **SC-003**: For 100% of characterization scenarios where all three modes apply, the forecast, a fresh run and a resume reach the same claim-time verdict on the same state. — [build] · no-op passable: no
- **SC-004**: 0 scenarios remain where a failed history read is accepted as a deletion, or where a dependency lane that moved after an interruption widens what a resume exempts. — [build] · no-op passable: no
- **SC-005**: The split changes 0 verdicts across the characterization corpus, while each moved check is shown to be guarded by at least one scenario that fails when the check is broken. — [ratchet] · no-op passable: yes — paired with the deliberately-broken-check control of NFR-008 on the same scenarios
- **SC-006**: The logic of any single verification check is found in one place of at most 1,200 lines, down from one shared 4,096-line place today. — [build] · no-op passable: no

## Assumptions

- **Window opener rule for lanes**: lanes adopt the approval-window opener rule that `single_branch` already uses (first non-migration move into `claimed` or `in_progress`; `blocked` opens nothing). The closed-world anchor's different rule (`blocked` counts) stays as a named window variant, so no closed-world verdict changes.
- **No re-derivation on the lane path**: when the opening event lacks the namespaced key, the lane path falls back to the approval-stamp bound rather than deriving the window-open SHA from older lane-head stamps. This follows the operator's missing-window ruling literally.
- **Rewritten lane**: a recorded window-open SHA that is not on the lane's history is a window gap ("not on lane"); the fallback bound's existing rewritten-lane refusal still applies.
- **`single_branch` gap reporting**: the gap report also covers `single_branch` work packages whose window-open SHA is not recorded, although their verdict comes from today's derived window, not the approval-stamp bound.
- **Forecast scope of parity**: parity is required for the claim inputs and the claim-time verdict, plus every verify-side check the forecast already evaluates. Making the forecast evaluate the verify-side checks it does not run today (presence, canceled content, canceled dependency, the gate's lane re-check) is not in scope. Follow-up: see #7362.
- **Forecast input alignment**: where the forecast derives an input differently from the fresh run on an unmutated state (it passes no excluded canceled work packages today), aligning it is part of FR-012/FR-013. If characterization shows this changes a forecast verdict, that change is handled red-first under NFR-002.
- **orchestrator-api**: `orchestrator-api consolidate-mission` shares the approved-bound refusal and so inherits the lane window check; adding the gap report to its envelope is not in scope (no contract-version change).
- **Durability horizon**: recorded SHAs are valid within one consolidation attempt (forecast, fresh run, resume, teardown), consistent with ADR `2026-11-07-1-dossier-commit-shas-are-branch-relative-provenance`; surviving a rebase landing is not a goal.
- **Dependency on frozen lane membership**: recorded windows rely on the lane id to lane branch binding that ADR `2026-10-04-2-started-work-package-lane-membership-is-frozen` guarantees.
- **Size threshold**: the 1,200-line ceiling in NFR-003 is derived from the current region sizes (verifier with its divergence record about 800 lines; the authorship-and-presence slice and the two canceled checks each under 1,000 lines).

## Out of Scope

- Changing the Java write service to write or type the key (only the issue is filed, FR-006).
- Residuals the window model does not touch: content inside merge commits, forced approvals and re-approvals, planning lanes and `--commit-to-target`, blob identity across lanes, and misattribution to the wrong canceled work package. Follow-up: see #5721 for the remaining bullets.
- Interrupted-run recovery and teardown honesty (see #7359), and the forecast evaluating every verify-side check (see #7362).
- Lane-id rebuilds that orphan recorded windows (see #5703).
- Reducing the complexity of functions that move unchanged in the split.
- Migrating callers and tests off the facade to the new module homes.
