---
title: 'ADR: work-package windows are recorded at the opening transition'
description: 'The window-open SHA is recorded on the status event that opens a work package, the consolidation gate judges each approved work package against its recorded window, and forecast, fresh run and resume build the gate claim from one set of claim inputs.'
status: Proposed
doc_status: active
kind: ADR
date: '2026-11-08'
updated: '2026-11-09T00:00:00Z'
---

# Work-package windows are recorded at the opening transition

**Status:** Proposed (2026-11-08). The operator accepts or amends it on the pull request.

**Date:** 2026-11-08

**Deciders:** Stijn Dejongh (operator).

**Amends:**
- `2026-10-04-5-approval-stamp-bounds-the-approved-claim` (the approval stamp stays the closing edge of the window and the fallback bound; the lane's own approval stamps stop exempting its commits on the window path).
- `2026-09-29-1-closed-world-refuse-on-mixed-lanes` (the closed-world anchors are read from one frozen anchor set on resume; the lane anchor stays a named window variant).

**Technical Story:**
- #7403: this Mission (consolidation window provenance and reconciliation split).
- #7358: parent sub-epic.
- #5721: the commit-between-two-approvals residual this ADR closes.
- #5048: the deletion-inference defect (fail-open history read), fixed in the same Mission.
- spec-kitty/spec-kitty-events#229: the cross-repository writer issue (FR-006), a context citation, not a gate.
- Follow-up: see #7359 (interrupted-run recovery and teardown honesty), #7362 (the forecast evaluating every verify-side check), #5703 (lane-id rebuild orphans recorded windows).

**Reader:** a maintainer who changes a consolidation check, the status transition pipeline, or the
forecast, and an agent doing either. It assumes you know the approval-stamp bound
(`2026-10-04-5-approval-stamp-bounds-the-approved-claim`) and the closed-world rule
(`2026-09-29-1-closed-world-refuse-on-mixed-lanes`).

## Context and Problem Statement

The consolidation gate rebuilds each work package's span of work from branch history after the
fact. Every check keeps its own idea of that span. Nine base or window notions exist on `main`
(see the table under Decision Outcome), and a fix to one check has repeatedly had to reason about
the others. Of the 57 commits that touched `consolidation/reconciliation.py` on `main` before this
Mission, 43 carry a `fix` subject (`git log --oneline main -- src/specify_cli/consolidation/reconciliation.py`).

Three problems follow:

1. **No recorded window.** The gate never knows where a work package's work began. It infers the
   window from stamps and branch history, so each check infers it differently.
2. **Different inputs per mode.** `spec-kitty consolidate --dry-run` (the forecast), a fresh run
   and `spec-kitty consolidate --resume` call the same claim builder, `build_approved_wp_set`,
   with different inputs. The forecast passes no excluded canceled work packages and a live
   coordination base name; a resume reads some anchors from saved state and others from live
   branches. The three can disagree on the same repository state.
3. **An unreviewed commit lands with exit 0.** A lane carries two work packages. WP01 is approved,
   someone commits to the lane, WP02 opens and is approved. WP02's approval stamp reaches the
   stray commit, and the approval-stamp bound exempts everything an approval stamp of the lane
   reaches. The gate accepts the commit (#5721, residual "a commit between two approvals on one
   lane").

`consolidate` here is lane consolidation: the local landing of approved lane work onto the local
target branch. It never publishes to a remote. "Primary" is not used in this record.

## Decision Drivers

- The status event log is the only provenance authority (C-001). No second file, sidecar or store.
- The status package stays git-free (C-002). It reads git only through an injected probe.
- A missing window must never refuse a Mission by itself, and no refusal code is added (C-010).
- Missions in flight when this ships keep the verdict they would have had (user story 3).
- One recorded rule: every later change to a consolidation check follows the same window model.
- Forecast, fresh run and resume must feed the gate the same inputs, so an operator can trust a
  forecast.

## Considered Options

For where the window is recorded (research R-01):

- **A.** Derive the window from existing `lane_head` stamps only, with no new key.
- **B.** A separate provenance file or sidecar.
- **C.** A new canonical event type that records the window.
- **D.** Write the key only on the first opening move, with the status shell reading history to
  decide.
- **E.** A namespaced key on the status transition event, written on every non-migration move into
  `claimed` or `in_progress`, with the reader picking the window opener.

For how far to unify the nine notions (R-02):

- **F.** One `WindowLedger` substrate for all nine notions now.
- **G.** One window model, plus a table that maps every other notion to it or to a named window
  variant.

For a work package with no recorded window (R-03):

- **H.** Refuse, with an operator attestation as the escape hatch (what `single_branch` did).
- **I.** Fall back to the approval-stamp bound and report the gap.

For the shape of the split of the reconciliation module (R-06), which this ADR constrains but does
not describe:

- **J.** A subpackage. **K.** Flat sibling modules behind a re-exporting facade.

## Decision Outcome

**Chosen options:** E, G, I and K.

### 1. Where the window-open SHA is recorded

On every non-migration move of a lane-mapped work package into `claimed` or `in_progress`, the
status shells write `policy_metadata.wp_window` on the transition event. The value comes from the
**same lane-head reading** that produces `lane_head` (`status/lane_head.py`: `read_lane_head`
returns a `LaneHeadReading`), so recording adds no extra git read. The status transition pipeline
(`status/transition_pipeline.py`) stays git-free: the reading comes from the injected reader.

The wire shape and the writer and reader rules (W-1 to W-7, R-1 to R-7) live in the contract
`kitty-specs/consolidation-window-provenance-01M6Y84D/contracts/status-event-wp-window.md`. This
record does not copy the JSON Schema. In prose, the writer rules are:

- Write only for a non-migration actor, a move into `claimed` or `in_progress`, and a work package
  mapped to a non-planning execution lane (or a `single_branch` Mission with a minted Mission
  branch). `blocked` opens nothing.
- Take the value from the one lane-head reading. When both keys are written, `open_sha` equals
  `lane_head`.
- A reading with a SHA writes `open_sha`. A reading of a mapped work package whose lane branch does
  not exist writes the gap `lane_branch_missing`. Any other failed reading writes the gap
  `capture_failed` with a cause of `git_error` or `probe_error`. A reading that does not apply
  (planning lane, unassigned work package, no `lanes.json`) writes nothing.
- Never refuse, delay or retry a move because of the key. Never change another key. Never backfill
  past rows (the log is append-only).
- A second writer, the Java write service, must write the same shape or preserve the key verbatim.
  spec-kitty/spec-kitty-events#229 asks for that. A writer that drops the key turns later windows
  into "not recorded" gaps, which is a weaker check and never a refusal.

The key is additive. An event that does not qualify is byte-identical to today's row.

### 2. The typed window gap

A window gap is the explicit, typed absence of a usable window for a work package. Four reasons
exist:

| Reason | Origin | Meaning |
|---|---|---|
| `capture_failed` (with `cause`) | written | The lane branch exists but the head could not be read (`git_error` or `probe_error`). |
| `lane_branch_missing` | written | The lane branch did not exist at the opening move. This is normal before `implement` creates the lane. |
| `not_recorded` | reader only | The window opener carries no key (written before the upgrade, or by a writer that drops it), or the key is malformed. |
| `not_on_lane` | reader only | The recorded SHA is not an ancestor of the lane tip (a rewritten lane), **or does not resolve in this clone** (another clone, a collected object) (FR-022). Never a probe error; a git failure on a SHA that is in the clone is one, and the bound refuses on it (pre-PR fold M2). |

The gap is a fact about what the writer observed (written reasons) or about the log and the lane at
read time (reader-only reasons). A missing approval stamp is not a window gap:
`APPROVAL_STAMP_MISSING` and `APPROVAL_STAMP_NOT_ON_LANE` keep their meaning and remedies.

### 3. The window opener (FR-021)

The recorded window binds to the **window opener**, found by one shared selector:

1. The cycle starts after the work package's last non-migration move to `planned` from a
   non-review lane. Moves out of `for_review`, `in_review`, `approved` and `done` are review
   rejections and do **not** reset the cycle (the genesis seed counts as a start).
2. The candidates are the cycle's non-migration moves into `claimed` or `in_progress`, in event-log
   order.
3. Leading candidates that recorded `lane_branch_missing` are skipped: they prove no lane commit
   existed at that instant.
4. If the first remaining candidate has no usable value, that is the gap. An unrecorded opener is
   never replaced by a later recorded one. Otherwise, among the SHA-bearing candidates, the
   topologically earliest wins (the SHA that is an ancestor of every other), and event-log order
   decides when the SHAs are unrelated.
5. If only skipped candidates exist, the gap is `lane_branch_missing`. With no candidate at all,
   the gap is `not_recorded`.

**Interpretation recorded for review.** The operator ruling (Decision Moment
`01M6YAG16WDVMM37HCJCHAC5YW`) says the window opens after the work package "last returned to
`planned`". This ADR reads a review rejection as rework, not as a return: review rejections move a
work package `in_review -> planned` today, and resetting the window there would put the work
package's own earlier commits outside its window, refused with no attestation route. A move to
`planned` out of `for_review`, `in_review`, `approved` or `done` is therefore rework. Any other
move to `planned` (today `in_progress -> planned`) is a rewind and starts a new cycle. The `force`
flag is not read: a forced `approved -> planned` or `done -> planned` is rework like its unforced
twin, and a forced move to `planned` out of any other lane is a rewind. The operator can overturn
this reading in review.

The same selector (`consolidation/wp_attribution.py`: `window_opener_events`, `window_open_of`)
serves the `single_branch` derivation when no window is recorded, with its legacy first-claim rule
(`cycle=False`). The opener rule lives once. The review-rejection reading above stays an
interpretation the operator may overturn; the shipped selector implements it and
`tests/consolidation/test_window_opener.py` pins it.

### 4. The window and its exemption anchors

The **work-package window** is `(window-open SHA, newest approval stamp]`. A work package with a
gap gets a **degraded window**, `(claim base, approval stamp]`, which is exactly today's
approval-stamp coverage for it.

On a code lane with at least one recorded window, a lane commit that lies in no window and is
reached by no **exemption anchor** is refused with `LANE_MOVED_AFTER_APPROVAL`, naming the commit
and the work package approved before it. The stamp refusals come first, as today, and merge
commits and bookkeeping-only commits are dropped exactly as today.

The exemption anchors on the window path (Decision Moment `01M6YAFYHT0RMVZB03THW1WWSE`) are the
closed-world anchors (the dependency-lane tips of lanes that are not fully canceled, and the
target's pre-consolidation tip) plus the approval stamps of **other** bounded lanes. A lane's own
approval stamps are **not** anchors on this path: the windows replace them. That is what makes the
commit-between-two-approvals refusal possible.

**Dependency-chain exception.** A commit another lane's approval stamp reaches is content inside
that lane's reviewed tip, so it stays exempt. If lane B depends on lane A, merged lane A's tip with
a stray commit, and B's work package was then approved, the stray commit is exempt on lane A. The
exception is deliberate and pinned by a dependency-chain fixture. The own-lane variant, where the
stray commit is reachable only from the lane's own stamp, refuses.

**Two tiers.** The lane check runs in two tiers (`consolidation/write_branch_bound.py`:
`bind_lane_predicates`, `classify_windows`, `check_lane_windows`). Tier 1 is today's approval-stamp
check, `check_lane`, unchanged and first: the stamp refusals and content after a lane's own
approval stamps keep today's whole-lane text. Tier 2 runs only when tier 1 passed and refuses each
content commit in `claim base..tip` that no window covers and no exemption anchor reaches, one
refusal per commit, with the new per-commit text (`render_lane_window_refusals`), printed after
every lane's tier-1 refusals. So the new text appears only for commits tier 1 cannot see (between
two approvals, or work abandoned before a rewind); a claim with no tier-2 refusal renders
byte-identical to today. The exempt set is computed once per lane and handed to both tiers.

**Canceled work packages (operator ruling 2026-11-09).** A canceled work package gets no window, so
its commits on a lane with recorded windows would otherwise refuse in tier 2 although the mixed-lane
rules already judge them. The commits the mixed-lane resolution attributed to the lane's canceled
work packages are therefore exempt from tier 2 (`reconciliation_bound._canceled_window_exempt`);
the mixed-lane and canceled-content rules are their only judge. Tier 1 is unchanged: a canceled
work package's commit after an approval stamp still refuses (#5720). The `orchestrator-api` door
(`approved_bound_refusal`) resolves the same exemption.

**Declared dependency refs (pre-PR fold M9).** A lane can carry content inherited before its first
window: an external ref merged into it before the work package's claim, or a lane cut from another
ref. Before windows were recorded, the lane's own approval stamp exempted that content; with a
recorded window it lies before the window. The commits of the operator's declared, pinned
`--dependency-ref` refs (#6771; exactly the verified set the closed world exempts) are therefore
exempt from tier 2 as well, so such a lane keeps its pre-window verdict. Tier 1 still never reads the
declaration, the `single_branch` Mission-branch check is unchanged, and an undeclared external commit
before the window still refuses. Corpus cell `fresh|single_lane|...|dependency_ref_merged_before_window`
pins it.

**Refusal text (pre-PR fold M8).** The tier-2 line names the commit and the work package approved
before it, and the recovery is to send that work package back for review and approve it again: its
window keeps its start and the new approval stamp moves its end past the commit. A commit that no
work package's newest approval precedes (it lies before the named work package's window, for example
work abandoned before a rewind) gets its own text and recovery: approving again moves a window's end,
never its start, so no approval covers it and it has to come off the branch. A revert is never
advised: it is new content of its own and clears no window refusal.

**All-gap lane.** A lane on which every approved work package has a gap runs today's
approval-stamp check (`check_lane`) unchanged, with today's anchors, own stamps included. Its
verdict and refusal text are byte-identical to today's (FR-023).

### 5. Claim inputs and their three sources

`ClaimInputs` is one frozen value (`consolidation/claim_inputs.py`), built by one constructor
(`build_claim`), consumed by claim building and by the gate. Its source is a `ClaimInputSource`. Its fields are: the target base, the coordination base, the frozen lane tips, the frozen
dependency anchors, the dependency refs and their pins, the excluded canceled work packages, the
strategy, the status directory read, and its source.

| Source | Mode | Meaning |
|---|---|---|
| `LIVE` | forecast (`--dry-run`) | Every value read from live branches. |
| `LIVE_THEN_SAVED` | fresh run | Read live, then saved to `state.json` (`ConsolidationState`) at claim capture. |
| `SAVED` | resume (`--resume`) | Read from the saved record. A value that was saved is never re-read live. |

Equality compares refs by the SHA they resolve to, and the status directory by its resolved path
and the digest of its event log. Phase 2 of the Mission keeps every per-mode quirk exactly. Phase 4
aligns the forecast's excluded canceled work packages and its coordination base (resolved to a SHA)
with the fresh run's (FR-013). The forecast keeps the status read door; it resolves the same status
directory as the fresh run's write accessor on every topology the corpus builds, so no status
directory change was needed (one residual, below).

### 6. Durability horizon

A recorded SHA is valid for one consolidation attempt: the forecast, a fresh run, a resume and the
teardown. It is **branch-relative provenance**, consistent with
`2026-11-07-1-dossier-commit-shas-are-branch-relative-provenance`. After a rebase landing it may
not resolve, and no reader after the landing may require it. The key
`policy_metadata.wp_window.open_sha` is classified `BRANCH_RELATIVE` in `DOSSIER_SHA_FIELDS`
(`tests/architectural/test_dossier_sha_provenance.py`).

### 7. Missing-window fallback

A work package with a window gap is judged by the approval-stamp bound with the degraded window and
is **never refused for the gap alone**. No refusal code is added, and existing codes, remedies and
attestation flags keep their meaning. Every work package judged by the fallback is listed in the
**gap report** with its reason. `APPROVAL_STAMP_MISSING` is unchanged. Missions in flight at
upgrade therefore reach the verdict they would have reached before it.

Gap-report surfaces: the fresh run, the resume and the forecast (a human block headed "Window gaps
(judged by the approval-stamp bound)", and `window_gaps` in the dry-run JSON, also on a refusal).
Each entry is a `GapEntry` (`consolidation/wp_attribution.py`), rendered by
`consolidation/window_gap_report.py`; the block prints before a claim-time refusal. The
`orchestrator-api` envelope is unchanged (no contract version change); see the residual below.

**The forecast reports the approved-bound refusals** (research R-09, settled by the corpus).
`consolidate --dry-run` builds the full claim, so a post-approval commit is forecast as
`CLAIM_REFUSED_FORECAST` naming `LANE_MOVED_AFTER_APPROVAL` (cell
`forecast|single_lane|post_approval_commit`), and a missing or rewritten stamp as
`APPROVAL_STAMP_MISSING` or `APPROVAL_STAMP_NOT_ON_LANE`. The window refusals reach it the same way.

### 8. The frozen anchor set on resume

On `--resume`, one frozen claim-time anchor set, built from the dependency-lane tips frozen at
claim capture, feeds every consumer of the closed-world anchors (Decision Moment
`01M6YAFZVZAYR4G20Q2X4PN0FT`). There are four consumers:

1. the mixed-lane resolver;
2. the approved bound;
3. the fully-canceled lane's own commits;
4. the approved-reviewed attestation check.

A dependency lane that moved after the interruption no longer widens what is exempt on any axis.
A fresh run reads live tips, which equal what the claim freezes on an unmutated state, so its
verdict is unchanged. A dependency lane the record froze no tip for is read live, listed in
`ClaimInputs.degraded_dependency_anchors`, and named in a note on the resume. Only the coordination
topology freezes lane tips, so a resume of a `LANES` or `single_branch` Mission with a dependency
lane always prints that note.

### 9. The two recording tiers

| Tier | What it records | Where |
|---|---|---|
| Work-package transition | the window-open SHA or the gap, the approval stamp | the status event log |
| Run claim | the claim inputs: bases, frozen lane tips, pins, excluded set, strategy | `state.json` (`ConsolidationState`) |

`ClaimInputs` is run-level provenance. It never writes to the event log and never touches the
rollback snapshot. Rollback is out of scope: no module gains a rollback or branch-restore caller
outside the existing rollback authority (Follow-up: see #7359).

### 10. The nine base and window notions

Every notion on `main` maps to the one window model or to a named window variant. Homes are module
and symbol names after the split of `reconciliation.py` (now a re-exporting facade); line numbers
drift.

| # | Notion | Home | Disposition in the window model |
|---|---|---|---|
| 1 | Coordination base (the lane-tip range base) | `consolidation/phase_claim.py`, `coord_base_ref` | `ClaimInputs.coord_base`. |
| 2 | Excluded window base (the target's pre-mutation tip) | `consolidation/phase_claim.py`, `excluded_window_base` | `ClaimInputs.target_base` (a claim-base input). |
| 3 | The bound's claim base | `consolidation/reconciliation_bound.py`, `_bound_claim_base` | Derived from 1 and 2, unchanged. It is the degraded window's opening edge. |
| 4 | Presence lane bases | `consolidation/wp_attribution.py`, `first_governed_open_stamp` | **Named variant "lane anchor"**: `blocked` counts as an opener. Kept, because unifying it would change closed-world verdicts. |
| 5 | Implementation and review windows | `consolidation/wp_attribution.py`, `WorkWindow` | **Named variant "canceled-content windows"**: class-change windows of mixed lanes. Unchanged. |
| 6 | The approval stamp | `consolidation/approved_bound.py`, `approval_stamp` | The window's closing edge, and the fallback bound. |
| 7 | The owned-file evidence window (`planning_commit_sha..tip`) | `consolidation/wp_evidence.py` | **Named variant "owned-file evidence"**: not stamp-based. Unchanged. |
| 8 | The `single_branch` authorship window (`merge-base(target, mission)..mission`) | `lanes/single_branch_landing.py` | **Named variant "`single_branch` authorship window"**, unchanged. `single_branch` approval windows read the recorded window-open SHA when present (FR-011) and keep today's derivation, reported as a gap, when absent. |
| 9 | The closed-world anchors (dependency-lane tips and the target base) | `consolidation/reconciliation_kernel.py`, `_closed_world_anchors` | Anchor SHAs come from `ClaimInputs`. Frozen on resume (decision 8). |

The `blocked` asymmetry is a named window variant, not drift: the approval-window opener ignores
`blocked`, the closed-world lane anchor counts it. Neither verdict changes.

### 11. Named residuals

These are accepted and named, so a later reader does not rediscover them:

- **Parallel claims on one lane**, and a claim parked without returning to `planned`: the window
  opens early and also covers the other work package's commits and any stray commit between them.
  Over-wide window, pinned as a strict `xfail`.
- **A review rejection to `planned` followed by another work package on the same lane.** WP01 is
  rejected to `planned` (rework: its cycle continues), WP02 is claimed, worked and approved on the
  same lane, then WP01 is claimed again and approved. WP01's window still opens at its first opener,
  so it covers WP02's commits and any stray commit made between them. Over-wide window, a consequence
  of reading a review rejection as rework (section 3).
- **The rewind boundary is found in event-log order.** Clock skew across the boundary itself is not
  topology-corrected. (Skew between openers inside a cycle is corrected by topology order.)
- **Degraded anchors on resume.** A record written before the upgrade has no frozen tip for a
  dependency lane, and a record whose status surface did not resolve at capture froze no tip. Both
  keep today's live read.
- **A full-restore re-baseline** (#6770) drops the frozen tips on `LANES` and `single_branch`, so
  the next resume is a fresh capture by design.
- **A canceled set that changes between capture and resume** only refuses or drops anchors, both
  safe.
- **The forecast before the first status seed** (FR-013). A Mission whose coordination branch holds
  no `status.events.jsonl` yet: the forecast reads the log through the read door's pre-seed
  fallback (the write checkout), while the fresh run seeds the coordination worktree and measures
  its claim from that seed commit. Same log bytes, excluded set, lane tips and target base, but a
  different status directory and coordination SHA. Pinned as the strict `xfail`
  `test_pre_seed_forecast_status_dir_and_coord_base_equal_fresh_run`
  (`tests/consolidation/test_forecast_fresh_run_parity.py`).
- **The presence scope reads canceled lanes live on resume.** `reconciliation_authorship._presence_scope`
  is not one of the four frozen-anchor consumers. Its live read can only shrink the subtracted
  canceled set, which makes the presence axis stricter, never looser.
- **Compound refusals exempt no canceled commit.** The canceled-dependency compound refusal evaluates
  the bound before the mixed lanes are resolved, so the bound text it appends exempts no canceled
  work package's commit from tier 2. A canceled work package that is unattributable, attested
  (`--attest-canceled-superseded`) or not, exempts nothing either. Both fail closed.
- **The window downgrade is invisible on `orchestrator-api`.** The envelope carries no gap report,
  so a second writer that drops the key, or any other downgrade, is not visible to an orchestrator
  until a later contract version carries the gap report.

### 12. Limits

- **Lane-id rebuild.** Recorded windows rely on the lane id to lane branch binding that
  `2026-10-04-2-started-work-package-lane-membership-is-frozen` guarantees. A lane-id rebuild after
  execution began orphans recorded windows (Follow-up: see #5703).
- **The Java writer** must write or preserve the key (spec-kitty/spec-kitty-events#229). Until it
  does, work packages opened through it have no window.

## Consequences

### Positive

- A commit made between two approvals on a lane with recorded windows is refused before any branch
  moves (closes the #5721 residual).
- Every consolidation check has one place to ask where a work package's window begins.
- Forecast, fresh run and resume build the claim from one construction point, so the forecast and
  the fresh run can be compared on the same state.
- In-flight Missions are never refused for lacking a window, and the operator can see exactly which
  work packages got the weaker check.
- The status package stays git-free, and recording adds no git read.

### Negative

- **The accepted dependency-chain exception.** A stray commit that a dependent lane merged before
  its own approval stays exempt on the source lane.
- **A weaker check for a gap work package.** A gap work package's degraded window covers a stray
  commit between an earlier recorded work package's approval and its own opening. The run passes
  and the gap report names it. A gap work package followed by a recorded one, with a stray commit
  between them, is newly refused.
- **A rewound window can still be over-wide** (residuals above).
- **A second writer can silently downgrade windows** until it writes the key and the envelope
  carries the gap report.
- One more key on every opening event, and one more reader rule to keep in step with the Java
  writer.

### Neutral

- No refusal code, allowlist entry, suppression or `orchestrator-api` contract version is added.
- The split of the reconciliation module follows this record but is behaviour-preserving, and the
  only verdict changes are the named, red-first ones in the Mission.

### Confirmation

The characterization corpus, the refusal-precedence matrix and the surface pin landed first and
stayed unchanged across the split. Each behaviour change in this Mission is a named corpus cell
(NFR-002) with a test committed failing before its fix and passing after. As landed:

- (a), (b): a commit between two approvals refuses, naming the commit and the work package approved
  before it (WP19). (c): a rewound work package's window opens after the rewind, on lanes (WP19) and
  `single_branch` (WP20).
- (d): a history-read error in the authored-content walk refuses the claim instead of counting the
  path as deleted (#5048(b), WP16).
- (e), (f): on resume the closed world and the approved bound read the frozen anchors (WP18). On the
  corpus (e) shape the new refusal is carried by the approved bound, because the closed world walks
  only the non-merge commits of the first-parent spine and the dependency commit sits behind a
  merge; the closed world's own read of the frozen set is pinned by
  `test_resume_closed_world_does_not_exempt_a_post_interrupt_dependency_commit`.
- (g): recorded unreachable. A fully-canceled lane has no frozen tip and is never an anchor, so any
  route that brings its advance into the claim reaches a dependency lane after that lane's approval
  stamp, which the approved bound refuses with live or frozen anchors alike.
  `test_resume_fully_canceled_lane_flip_is_unreachable` pins the reachable consequence.
- (h): the forecast excludes the fresh run's canceled work packages (verdict-visible) and resolves
  the coordination base to a SHA (field-level only) (WP17).

The evidence: `tests/status/test_wp_window_capture.py`, `tests/consolidation/test_window_opener.py`,
`test_claim_inputs_parity.py`, `test_forecast_fresh_run_parity.py`, `test_lane_approval_windows.py`,
`test_refusal_precedence_matrix_windows.py`, `test_lane_window_query_count.py`,
`test_window_gap_report.py`, `test_window_gap_report_entry_points.py`,
`test_authored_walk_read_error.py`, `test_resume_frozen_anchors.py`,
`test_reconciliation_characterization.py`, `test_reconciliation_intended_verdicts.py` and
`test_reconciliation_seeded_mutations.py` (all under `tests/consolidation/` unless named), and
`tests/integration/test_single_branch_approval_windows.py`.

## Pros and Cons of the Options

### A. Derive from `lane_head` stamps only

**Pros:**

- No new key.

**Cons:**

- It cannot express a typed gap, so "capture failed" and "never recorded" look the same.
- The lane path would re-derive an opening from older stamps, which the operator ruled out.

### B. A separate file or sidecar

**Pros:**

- Free-form shape.

**Cons:**

- A second authority and a second read door. Already rejected twice (ADRs
  `2026-09-29-1-closed-world-refuse-on-mixed-lanes` and
  `2026-10-04-5-approval-stamp-bounds-the-approved-claim`).

### C. A new canonical event type

**Pros:**

- A typed, versioned record.

**Cons:**

- It duplicates the transition, adds an atomicity obligation, and is blocked on a spec-kitty-events
  release.

### D. Write on the first opening move only

**Pros:**

- One row carries the key.

**Cons:**

- The shell must read history on every move, which moves window logic into the shell.

### E. A namespaced key on every opening move (chosen)

**Pros:**

- Ships from core alone: `policy_metadata` is an open mapping in the events payload.
- Reuses the lane-head reading already taken, so no extra git read.
- The reader, not the writer, decides which opener binds, so the status pipeline stays history-free.

**Cons:**

- Several rows can carry the key, so the reader must choose (the window opener rule).

### F. A full `WindowLedger` now

**Pros:**

- The right end state for all nine notions.

**Cons:**

- It would turn a behaviour-preserving split into a redesign. Deferred.

### G. One model plus named variants (chosen)

**Pros:**

- Every notion is mapped, and no variant's verdict changes outside the named lane change.

**Cons:**

- Variants remain, including the `blocked` asymmetry.

### H. Refuse with attestation

**Pros:**

- A missing window is never silent.

**Cons:**

- It would strand every Mission in flight at upgrade.

### I. Fall back and report (chosen)

**Pros:**

- Missions in flight keep their verdict, and the gap is named in the output.

**Cons:**

- The fallback is a weaker check.

### J. A subpackage

**Cons:**

- It cannot share a name with the facade module, and a new `__init__.py` brings in the version-bump
  rule.

### K. Flat sibling modules (chosen)

**Pros:**

- No new package, and module ownership by directory glob stays unchanged.

## References

- Contract: `kitty-specs/consolidation-window-provenance-01M6Y84D/contracts/status-event-wp-window.md`.
- Amends: `2026-10-04-5-approval-stamp-bounds-the-approved-claim`,
  `2026-09-29-1-closed-world-refuse-on-mixed-lanes`.
- Related: `2026-11-07-1-dossier-commit-shas-are-branch-relative-provenance`,
  `2026-10-04-2-started-work-package-lane-membership-is-frozen`,
  `2026-10-14-1-event-native-core-one-canonical-event-writer`.
- Decision Moments: `01M6YAFYHT0RMVZB03THW1WWSE` (lane anchor set), `01M6YAFZVZAYR4G20Q2X4PN0FT`
  (resume anchor scope), `01M6YAG16WDVMM37HCJCHAC5YW` (window opener),
  `01M6YAG2HE6Q2XNQMGK6X3MBEK` (events issue filing).
- [spec-kitty/spec-kitty-events#229](https://github.com/spec-kitty/spec-kitty-events/issues/229):
  the Java write service adopts and types `policy_metadata.wp_window` (context citation, FR-006).
- Issues: #7403, #7358, #5721, #5048, #7359, #7362, #5703.
