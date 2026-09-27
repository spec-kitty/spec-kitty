# Design Decisions

> Capture the rationale that would otherwise evaporate.

**Prompting questions**
- What decision was made?
- What alternatives were considered?
- What was the rationale — why this option over the others?

---

## Entries

<!-- YYYY-MM-DD — Decision: [what]. Alternatives: [what else]. Rationale: [why this one]. -->

## Seed (2026-09-27)
- Operator decisions (recorded as resolved Decision Moments): (1) fold #5171 review-gate + #4943 merge-gate partition legs into one mission; (2) deep fix — read the coordination branch ref when the worktree is unmaterialized; (3) fold #4943's verdict-terminality leg here too.
- Single canonical authority (C-001): no second partition resolver; any shared helper lands in the runtime seam module, not the CLI adapter.
- Topology choice: mission minted as `lanes` (branch-flat) deliberately, to avoid dogfooding the coord issue-matrix bug it repairs.

## Post-plan brownfield squad (2026-09-27)
- IC-01 split into IC-01a (git-ref content primitive) + IC-01b (reader content-source adoption); added IC-shared two-partition split helper (DRY) so review/merge don't re-author the split 3×.
- #4959 carve-out: UNMATERIALIZED→ref-read for ISSUE_MATRIX only; keep the CoordinationWorktreeUnmaterialized raise for other coord kinds (non-regression guard).
- IC-04 reuses `_issue_matrix_approval_blocker` (tasks_parsing_validation.py:206), covers the `unknown` half via the schema-validity gate too, and de-scopes done_bookkeeping (the gate mechanism already blocks/warns).
- IC-01a must not import specify_cli.* (shrink-only TestMissionRuntimeBoundary ledger).

## MAJOR-3 resolution — read surface = write's lifecycle-phase authority (2026-09-27)
- The write surface is chosen by `resolve_lifecycle_phase`, NOT coord-worktree materialization. E2 consolidated-primary routing fires only in PUBLISHED phase (Target Ref `meta.target_branch` DELETED + baseline + completion).
- #5171 is the CONSOLIDATED case → verdict on the coordination branch ref → read the coord branch ref. IC-01a resolves the read via the same phase authority so read/write can never diverge (PUBLISHED → consolidated-primary ref).
- Caveat: missions targeting a durable trunk (main) never delete the Target Ref → phase stays CONSOLIDATED → verdicts always on the coord branch; E2 never engages. Do not assume E2 fires on "merged".
- This refines (does not reverse) the operator's "deep fix: read the coord branch ref" decision — the coord branch ref IS correct for the #5171/CONSOLIDATED case; the phase-authority framing makes it robust for the PUBLISHED case too.
