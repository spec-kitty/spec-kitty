---
work_package_id: WP01
title: Window-model ADR, glossary and closed-world amendment pointer
dependencies: []
requirement_refs:
- FR-001
- FR-006
- C-001
- C-010
- C-011
- C-012
planning_base_branch: feat/consolidation-window-provenance
merge_target_branch: feat/consolidation-window-provenance
branch_strategy: Planning artifacts for this mission were generated on feat/consolidation-window-provenance. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/consolidation-window-provenance unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Pin and decide
history:
- at: '2026-11-08T19:52:39Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: architect-alphonso
authoritative_surface: docs/adr/4.x/
create_intent:
- docs/adr/4.x/2026-11-08-2-work-package-windows-are-recorded-at-the-opening-transition.md
execution_mode: planning_artifact
model: ''
owned_files:
- docs/adr/4.x/2026-11-08-2-work-package-windows-are-recorded-at-the-opening-transition.md
- docs/adr/3.x/2026-09-29-1-closed-world-refuse-on-mixed-lanes.md
- docs/context/orchestration.md
role: implementer
tags: []
task_type: plan
tracker_refs: []
---

# Work Package Prompt: WP01 – Window-model ADR, glossary and closed-world amendment pointer

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `architect-alphonso`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status --mission consolidation-window-provenance-01M6Y84D`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

Write the one recorded rule that every later change to a consolidation check follows (FR-001). When you are done:

1. `docs/adr/4.x/2026-11-08-2-work-package-windows-are-recorded-at-the-opening-transition.md` exists, `status: Proposed`, with valid ADR frontmatter, and it **amends** `2026-10-04-5-approval-stamp-bounds-the-approved-claim` and `2026-09-29-1-closed-world-refuse-on-mixed-lanes` (cited by full slug, C-011).
2. The ADR states: where the window-open SHA is recorded, the typed window gap, the window opener (FR-021), the exemption anchors on the window path, `ClaimInputs` and its three sources, the durability horizon, the missing-window fallback, the frozen anchor set on resume, the two recording tiers, and a table mapping all nine base/window notions (research R-02) to the window model or to a named window variant.
3. The ADR links spec-kitty/spec-kitty-events#229 as the FR-006 cross-repository writer issue (context citation, non-gating).
4. `docs/context/orchestration.md` carries glossary entries for: work-package window, window-open SHA, window opener, window gap, gap report, exemption anchor, claim inputs, named window variant.
5. `docs/adr/3.x/2026-09-29-1-closed-world-refuse-on-mixed-lanes.md` carries a short amendment pointer to the new ADR.
6. The docs gates listed in the Definition of Done pass.

This is a **planning_artifact** work package: you edit only the three files above. You change no code.

## Context & Constraints

Read, in this order, before writing:

- `.kittify/charter/charter.md` (governance; DIRECTIVE_003 decision documentation, DIRECTIVE_042 Common Docs standard).
- `kitty-specs/consolidation-window-provenance-01M6Y84D/spec.md` — Domain Language table (use those terms exactly), FR-001..FR-023, Edge Cases, Assumptions, Out of Scope.
- `kitty-specs/consolidation-window-provenance-01M6Y84D/plan.md` — IC-01 (Purpose, Risks, "Post-plan rulings the ADR records", "Named residuals the ADR records").
- `kitty-specs/consolidation-window-provenance-01M6Y84D/research.md` — R-01..R-05, R-11, R-12, R-15..R-17 (decisions and rejected alternatives: reproduce the alternatives in the ADR's "Considered Options").
- `kitty-specs/consolidation-window-provenance-01M6Y84D/data-model.md` — sections 1-7 (the shapes and invariants the ADR must state).
- `kitty-specs/consolidation-window-provenance-01M6Y84D/contracts/status-event-wp-window.md` — the wire contract (the ADR links it; it does not copy the JSON Schema).
- `kitty-specs/consolidation-window-provenance-01M6Y84D/decisions/` — resolved Decision Moments; cite the post-plan ones by id: `01M6YAFYHT0RMVZB03THW1WWSE` (lane anchor set), `01M6YAFZVZAYR4G20Q2X4PN0FT` (resume anchor scope), `01M6YAG16WDVMM37HCJCHAC5YW` (window opener), `01M6YAG2HE6Q2XNQMGK6X3MBEK` (events issue filing).
- Format exemplar for ADR frontmatter and header block: `docs/adr/4.x/2026-11-08-1-upgrade-worktree-pass-is-plan-then-apply-and-migrations-must-converge.md` (frontmatter keys `title`, `description`, `status`, `doc_status`, `kind`, `date`, `updated`; then `**Status:**`, `**Date:**`, `**Deciders:**`, `**Technical Story:**`, `**Reader:**`).

Constraints:

- **C-011**: cite every ADR by its full slug (several share a date prefix, e.g. three `2026-09-29-1-*` files).
- **C-012**: "Mission", never "feature"; name the sense of "merge" and "primary" (`consolidate` is lane consolidation into the local target branch, never a publish).
- **R-09**: do **not** state whether `consolidate --dry-run` reports approved-bound refusals. WP02 settles it by test; WP21 writes the corrected sentence.
- Do **not** hand-edit the generated ADR index or docs inventory (they are bot-owned; docs lint fails PR edits).
- Do **not** touch `docs/adr/4.x/2026-10-04-5-approval-stamp-bounds-the-approved-claim.md` here: its amendment pointer and residual-list sync belong to WP21.
- The issue numbers you cite are context citations (non-gating): write them as "see #NNNN" / "Follow-up:" where the Mission owes them no work. #7403 is the Mission's own issue.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on kitty/mission-consolidation-window-provenance-01M6Y84D; completed changes must merge into feat/consolidation-window-provenance.
- **Planning base branch**: feat/consolidation-window-provenance
- **Merge target branch**: feat/consolidation-window-provenance

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Execution worktrees are allocated per computed lane from `lanes.json`. Start with:

```bash
spec-kitty agent action implement WP01 --agent <name> --mission consolidation-window-provenance-01M6Y84D
```

## Subtasks & Detailed Guidance

### Subtask T001 – ADR skeleton, frontmatter, context and decision drivers

- **Purpose**: A reader who knows ADR `2026-10-04-5-approval-stamp-bounds-the-approved-claim` must understand in one page why the gate needs a recorded window.
- **Steps**:
  1. Create the file with frontmatter: `title: 'ADR: work-package windows are recorded at the opening transition'`, a one-sentence `description`, `status: Proposed`, `doc_status: active`, `kind: ADR`, `date: '2026-11-08'`, `updated: '2026-11-08T00:00:00Z'`.
  2. Header block: `**Status:** Proposed (2026-11-08). The operator accepts or amends it on the pull request.`; `**Deciders:** Stijn Dejongh (operator).`; `**Technical Story:**` #7403 (this Mission), parent sub-epic #7358, related #5721 (the commit-between-two-approvals residual), #5048 (deletion inference), spec-kitty/spec-kitty-events#229 (writer issue), Follow-up: see #7359, #7362, #5703.
  3. `**Amends:**` line naming both amended ADRs by full slug.
  4. "Context and Problem Statement": the gate rebuilds each work package's span from branch history after the fact; nine base/window notions exist on `main`; forecast, fresh run and resume feed `build_approved_wp_set` different inputs; the commit-between-two-approvals residual (#5721) lands an unreviewed commit with exit 0.
  5. "Decision Drivers": event log is the only authority (C-001), status package stays git-free (C-002), no new refusal code (C-010), in-flight Missions keep their verdict (US3), one recorded rule for every check.
- **Files**: the new ADR only.
- **Notes**: Keep paragraphs short; the Writing doctrine in the charter applies.

### Subtask T002 – Decision: recording point, key, gap, opener, anchors, tiers

- **Purpose**: State the window model precisely enough that WP07, WP08 and WP19 can be reviewed against it.
- **Steps**:
  1. Recording point: on every non-migration move of a lane-mapped work package into `claimed` / `in_progress`, the status shells write `policy_metadata.wp_window` from the **same** lane-head reading as `lane_head` (zero extra git reads). Link `contracts/status-event-wp-window.md` for the schema; summarize writer rules W-1..W-7 in prose.
  2. Typed window gap: written reasons `capture_failed` (with `cause` `git_error`/`probe_error`) and `lane_branch_missing`; reader-only reasons `not_recorded` and `not_on_lane` (incl. a SHA that does not resolve in this clone, FR-022).
  3. Window opener (FR-021, Decision Moment `01M6YAG16WDVMM37HCJCHAC5YW`): the cycle starts after the last non-migration move to `planned` from a non-review lane; review rejections (out of `for_review`, `in_review`, `approved`, `done`) do not reset — state this as the **interpretation recorded for review**; leading `lane_branch_missing` openers are skipped; among SHA-bearing openers the topologically earliest wins, event-log order when unrelated; a first non-skippable opener without a usable value gives that gap.
  4. The window: `(window-open SHA, newest approval stamp]`; degraded window `(claim base, approval stamp]` for a gap.
  5. Exemption anchors on the window path (Decision Moment `01M6YAFYHT0RMVZB03THW1WWSE`): closed-world anchors plus approval stamps of **other** bounded lanes; never the lane's own. State the dependency-chain exception explicitly (a commit a dependent lane merged before its approval stays exempt on the source lane).
  6. All-gap lane: today's `check_lane` runs unchanged (FR-023), so verdict and text are byte-identical.
  7. Two recording tiers: work-package transition -> event log; run claim -> `state.json` (`ConsolidationState`). Rollback is out of scope (C-009, Follow-up: see #7359).
- **Files**: the new ADR.

### Subtask T003 – ClaimInputs, durability horizon, fallback, frozen anchors

- **Steps**:
  1. `ClaimInputs`: one frozen value, one constructor, three sources `LIVE` (forecast), `LIVE_THEN_SAVED` (fresh run), `SAVED` (resume). List the fields (data-model section 6). State that Phase 2 keeps per-mode quirks and Phase 4 aligns the forecast (FR-013).
  2. Durability horizon: one consolidation attempt (forecast, fresh run, resume, teardown); cite `2026-11-07-1-dossier-commit-shas-are-branch-relative-provenance`; the key is `BRANCH_RELATIVE` in `DOSSIER_SHA_FIELDS`.
  3. Missing-window fallback: never refused for the gap alone; listed in the gap report; `APPROVAL_STAMP_MISSING` unchanged (C-010).
  4. Frozen anchor set on resume (Decision Moment `01M6YAFZVZAYR4G20Q2X4PN0FT`): four consumers — mixed-lane resolver, approved bound, fully-canceled lane, approved-reviewed attestation. Fresh run reads live tips (equal to what the claim freezes on an unmutated state).
  5. Gap report surfaces: fresh run, resume, forecast (human block + `window_gaps` in dry-run JSON). `orchestrator-api` envelope unchanged; name the residual (a downgrade is invisible there until a later contract version).
- **Files**: the new ADR.

### Subtask T004 – Nine-notion table, named variants, residuals, degraded anchors, limits

- **Steps**:
  1. Reproduce research R-02's table (# / notion / home / disposition). Keep the homes as module + symbol names; line numbers are optional and drift, so prefer symbol names.
  2. Named window variants: "lane anchor" (`first_governed_open_stamp`, `blocked` opens — kept, unifying would change closed-world verdicts), "canceled-content windows" (`WorkWindow`), "owned-file evidence" (`wp_evidence`), the `single_branch` authorship window.
  3. Named residuals (plan IC-01): parallel claims on one lane and a claim parked without returning to `planned` (over-wide window, strict `xfail`); the rewind boundary is found in event-log order; degraded anchors on resume (pre-upgrade record; status surface unresolvable at capture, so no tip frozen); a full-restore re-baseline (#6770) makes the next resume a fresh capture by design; a canceled set that changes between capture and resume only refuses (H5) or drops anchors; the window downgrade is invisible on `orchestrator-api`.
  4. Limits: lane-id rebuild after execution began orphans recorded windows (Follow-up: see #5703); the Java writer must write or preserve the key (spec-kitty/spec-kitty-events#229).
  5. "Considered Options" with the rejected alternatives from R-01 (derive from stamps only; sidecar; new event type; write-once with history read), R-02 (full `WindowLedger` now), R-03 (refuse plus attest), R-06 (subpackage).
  6. "Consequences": positive / negative, incl. the accepted dependency-chain exception and the weaker check for a gap work package (US3-4, WW-7).
- **Files**: the new ADR.

### Subtask T005 – Glossary entries and closed-world amendment pointer [P]

- **Steps**:
  1. Open `docs/context/orchestration.md`; follow its existing entry format exactly (anchor heading, definition, "Do NOT use when" guard where the file uses them). Add the eight terms from Objectives item 4 with the spec's Domain Language meanings and "Avoid" columns turned into guards.
  2. Link each entry to the new ADR by relative path.
  3. In `docs/adr/3.x/2026-09-29-1-closed-world-refuse-on-mixed-lanes.md`, add an amendment pointer in the style the file already uses for amendments (search for "Amendment"): one dated paragraph "Amendment 2026-11-08: work-package windows are recorded at the opening transition; see `2026-11-08-2-work-package-windows-are-recorded-at-the-opening-transition`." Do not rewrite existing text.
- **Files**: `docs/context/orchestration.md`, `docs/adr/3.x/2026-09-29-1-closed-world-refuse-on-mixed-lanes.md`.

### Subtask T006 – Docs gates

- **Steps**: run every command in the Definition of Done; fix every finding in your files (spelling is US English).

## Test Strategy

No code changes. Validation is the docs gate set below.

## Definition of Done

Run from the repository root checkout (or your lane worktree) and record the pass/fail counts in the WP history note:

```bash
uv run --frozen pytest -q tests/architectural/test_no_legacy_terminology.py \
  tests/architectural/test_glossary_authority_parity.py \
  tests/docs/test_adr_content_invariance.py tests/docs/test_adr_readme_prose.py \
  tests/docs/test_architecture_docs_consistency.py
uv run --frozen python -m scripts.docs.check_spelling --pass typo
uv run --frozen python -m scripts.docs.check_spelling --pass us
```

- [ ] All three owned files edited; nothing else (the tracer append below is the only sanctioned out-of-map edit).
- [ ] Every ADR citation uses the full slug (`grep -n "ADR \`20" <new ADR>` shows only full slugs).
- [ ] No sentence states the `--dry-run` approved-bound behaviour (R-09).
- [ ] Every rule in plan IC-01 "Post-plan rulings the ADR records" and "Named residuals the ADR records" appears.
- [ ] **Tracer files**: append at least one dated entry to `kitty-specs/consolidation-window-provenance-01M6Y84D/traces/design-decisions.md` (format `- **[YYYY-MM-DD][implement WP01] <summary>.** <detail>`), and to `traces/tooling-friction.md` for any tooling friction you hit. If your checkout does not carry `kitty-specs/`, put the entry text in `spec-kitty agent tasks add-history WP01 --note "..."` and the orchestrator folds it.
- [ ] Never run `make test-full` (C-013).

## Risks & Mitigations

- **Over-claiming behaviour that WP19 has not built yet**: write the ADR as the decision ("the gate judges..."), not as a description of shipped code; WP21 syncs it with what shipped.
- **Inventing a rule**: every rule must trace to spec FR/Assumption, research R-xx or a Decision Moment. If you find a gap, record it in the tracer and the WP history; do not decide it yourself.

## Review Guidance

- Reviewer profile: `reviewer-renata`.
- **Model tier: top** (ADR authorship, design judgment).
- Check the nine-notion table against research R-02 row by row.
- Check the window opener text against FR-021 and contract R-1 word by word (review-rejection interpretation flagged as an interpretation).
- Check C-011 citations and C-012 terminology.
- Check that the ADR adds no refusal code (C-010) and does not touch rollback (C-009).

## Progress & Status

Progress, history, and status all live in the status event log (`status.events.jsonl`) — never in this prompt file.

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status --mission consolidation-window-provenance-01M6Y84D`
