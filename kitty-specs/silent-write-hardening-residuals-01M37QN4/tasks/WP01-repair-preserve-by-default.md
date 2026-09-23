---
work_package_id: WP01
title: 'Finding A: preserve-by-default mission-state repair + guard + ADR'
dependencies: []
requirement_refs:
- C-001
- C-003
- FR-001
- FR-002
- FR-003
- NFR-001
- NFR-002
planning_base_branch: fix/silent-write-hardening-residuals
merge_target_branch: fix/silent-write-hardening-residuals
branch_strategy: Planning artifacts for this mission were generated on fix/silent-write-hardening-residuals. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/silent-write-hardening-residuals unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-silent-write-hardening-residuals-01M37QN4
base_commit: 72b6fc86ceaf63f53e1363311d5b14f8be2f2bae
created_at: '2026-09-23T19:44:47.963989+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
history:
- event: created
  at: '2026-09-23T19:24:56Z'
  actor: architect-alphonso
agent_profile: python-pedro
authoritative_surface: src/specify_cli/migration/
create_intent:
- docs/adr/3.x/2026-09-23-2-mission-state-repair-preserve-by-default.md
execution_mode: code_change
owned_files:
- src/specify_cli/migration/mission_state.py
- src/specify_cli/status/lifecycle_events.py
- src/specify_cli/status/__init__.py
- tests/migration/test_mission_state_repair.py
- tests/status/test_authoritative_non_lane_registry_4897.py
- tests/integration/migration/test_lifecycle_events_preserved.py
- tests/unit/migration/test_canonicalization_rules.py
- docs/adr/3.x/2026-09-23-2-mission-state-repair-preserve-by-default.md
role: implementer
tags: []
tracker_refs:
- '#4993'
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else in this prompt, load your assigned agent profile:

```
/ad-hoc-profile-load python-pedro
```

This profile governs your implementation style, boundaries, and quality standards for this work package.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``. Use language identifiers in code blocks.

---

## Objective

Invert `doctor mission-state --fix`'s non-lane preservation from a registry **allowlist** to
**preserve-by-default with an EMPTY denylist**, so an authoritative non-lane `event_type` written by a
future subsystem *before it is added to the registry* is never silently quarantined. Strengthen the
fail-closed guard to the full **reader==repair** invariant, and record the behavioral change in an ADR.

This closes the recurring whack-a-field class (#2376 → #3066 → #3541 → #4897 → the unregistered-future
case) at the root by making the repair preserve exactly what the durable reader preserves.

**Do read** `research.md` and `contracts/repair-preservation-contract.md` in the mission dir first — the
denylist=EMPTY determination and the #3066 guardrail are settled there.

## Key context (verified on current main)

- Reader `status/store.py::is_non_lane_event` (~597-645) is presence-permissive: after the annotation,
  retrospective, and registry branches, its catch-all is `return "event_type" in obj` (~645). It returns
  False only for annotations (own path) and rows with no `event_type`/retrospective `event_name` (genuine
  lane rows). **You read this as the reference contract; you do not change store.py.**
- Repair `migration/mission_state.py::_is_preserved_non_lane_row` (~1943-2016) is the allowlist to invert.
  Its docstring currently states the asymmetry as deliberate — update it to state the new preserve-by-default rule.
- `_rule_reject_non_status_event` (~2127-2159) order: (1) `_is_legacy_typed_lane_transition` passthrough,
  (2) `_is_preserved_non_lane_row` → `preserved_non_lane_event`, (3) `if "event_name" in row or "event_type" in row:` → `quarantined_non_status_event`, (4) else passthrough.
- `_is_legacy_typed_lane_transition` (~2094-2124): `event_type == "WPStatusChanged"` + top-level
  `wp_id`/`from_lane`/`to_lane`. **This passthrough MUST stay FIRST** — a `WPStatusChanged` lane row is
  a lane transition (canonicalized into `status.json`), NOT a prunable mirror. Regressing this reintroduces #3066.
- Guard `_registry_authoritative_quarantine_violations` (~2019-2091): fail-closed backstop, currently
  powered by the registry (so it structurally cannot catch an unregistered type). It already excludes
  duplicate-`event_id` survivors via `surviving_event_ids` — **preserve that carve-out** (folded in #4938).
- Registry `status/lifecycle_events.py::AUTHORITATIVE_NON_LANE_EVENT_TYPES` (line 165). Empirically, no
  `event_type` written to `status.events.jsonl` is a prunable mirror (`decisions/index.json` is a derived
  fold in a separate file; `review_result` is a nested field, not a row). ⇒ **denylist = EMPTY.**

## Subtasks

### T001 — Red-first: unregistered authoritative row is quarantined (proves the bug)

**Purpose**: Capture the defect before fixing it.
**Steps**:
1. In `tests/status/test_authoritative_non_lane_registry_4897.py` (and/or `tests/migration/test_mission_state_repair.py`), add a test that builds a mission `status.events.jsonl` containing an authoritative-shaped **non-lane** row whose `event_type` is deliberately NOT in `AUTHORITATIVE_NON_LANE_EVENT_TYPES` (e.g. a synthetic `"FutureAuthoritativeThing"` with no lane fields).
2. Run `--fix`/`_repair_mission` and assert the row is **quarantined/dropped** — this MUST FAIL after the fix (it is the red-first proof). Mark it clearly (comment referencing #4993/#4897).
3. Confirm it FAILS on the current (pre-fix) code — run it now and paste the failure into the review notes.

### T002 — Invert `_is_preserved_non_lane_row` to preserve-by-default by **DELEGATING** to the reader (EMPTY denylist)

**Purpose**: Make the repair preserve exactly what the reader treats as non-lane — by delegating to the reader, NOT by re-enumerating its branches.

> **Squad fold (paula-patterns, primary SSOT):** do **not** hand-copy the reader's branches
> (annotation / retrospective-`event_name` / retrospective-type / `event_type` catch-all) into the
> repair — that recreates the *two-classifiers-kept-in-lockstep-by-hand* mechanism that GENERATED
> the #2376→#3066→#3541→#4897 class. **Delegate to the reader so it is the single authority.**

**Steps**:
1. Add a named, documented **empty** denylist constant (e.g. `PRUNABLE_MIRROR_EVENT_TYPES: frozenset[str] = frozenset()`) — in `lifecycle_events.py` beside the registry, or in `mission_state.py` — with a docstring explaining that a future entry is a *deliberate, reviewed* decision, and that it is empty because no `event_type`-bearing row in the authoritative log is a prunable mirror.
2. Rewrite `_is_preserved_non_lane_row` to **DELEGATE**:
   `_is_preserved_non_lane_row(row) := (row.get("kind") == ANNOTATION_KIND) or (is_non_lane_event(row) and <not on the empty denylist>)`.
   The annotation OR-clause is the ONLY intended divergence from the reader (the reader returns False
   for annotations to route them to their own partition; the repair must return True to KEEP them on
   disk). Export `is_non_lane_event` on the `specify_cli.status` facade (`status/__init__.py`) — it lives
   in `store.py` today; `mission_state.py` already imports the sibling predicates from that facade, so the
   import boundary is unchanged. Update the docstring to state the reader==repair contract and that the
   repair is now a *delegate*, not a parallel classifier.
   - **Bonus (paula):** `_scan_raw_status_rows` shares `_is_preserved_non_lane_row`, so the dry-run
     scanner is fixed by the same edit — verify, no second site.
3. **Keep `_is_legacy_typed_lane_transition` passthrough evaluated FIRST** in `_rule_reject_non_status_event` — do not let a flat `WPStatusChanged` lane row reach the delegated preserve call. Add an inline comment naming #3066. (Delegation is behavior-identical for the flat lane row precisely because this passthrough runs first.)

### T003 — Strengthen the fail-closed guard to reader==repair

**Purpose**: Make the guard catch the unregistered-future case it structurally could not before.
**Steps**:
1. Key the guard on the **reader predicate**: flag any quarantined line where `is_non_lane_event(obj)` is True (NOT merely `"event_type" in obj`). This makes it a genuine reader==repair invariant check that ALSO covers reader-preserved rows with no `event_type` (retrospective `event_name` rows). *(Squad fold, paula: keying on `"event_type" in obj` would silently omit the `event_name`-envelope class and be a tautological inverse of the preserve gate.)*
2. **Preserve** the duplicate-`event_id` carve-out (a quarantined row whose survivor stays in `canonical_rows` via `surviving_event_ids` is benign — do not flag it). Every duplicate has a prior survivor by construction, so the carve-out is provably sufficient; keep `--fix` from reporting `errors=0` when a genuine violation exists.
3. Keep the message/telemetry shape consistent with the existing guard.

### T004 — Regression coverage

**Purpose**: Prove no preserved class regressed and both prior fixes hold.
**Steps**:
1. Assert every previously-preserved class still round-trips: annotation, retrospective (`event_name` + type-envelope), lifecycle, DecisionPoint, `review_result` (nested field on a lane row), and `WPStatusChanged`-as-lane (canonicalized into `status.json`, not preserved verbatim — the #3066 pin).
2. Assert the #4938 carve-out: a mission with two same-`event_id` authoritative rows dedupes without the guard hard-erroring.
3. **Squad-added ACs (paula):**
   - **Nested-payload `WPStatusChanged` replay envelope** (top-level `aggregate_id`/`aggregate_type`, lane fields under `payload`): disposition changes quarantine→preserve-verbatim under the inversion. This is SAFE — the reader already skip-preserves it via the same catch-all, so the inversion *aligns* repair with reader. Add an assertion + a docstring note so a reviewer does not misread the disposition change as a regression.
   - **Partial-field `WPStatusChanged`** (e.g. `wp_id`+`to_lane`, missing `from_lane` — a corruption shape no writer emits): now falls through to preserve-by-default → retained-but-inert (reader also skips it). Acceptable fail-closed-toward-retention tradeoff; pin it with an AC + docstring note that repair no longer flags it.
4. Extend `tests/integration/migration/test_lifecycle_events_preserved.py` / `tests/unit/migration/test_canonicalization_rules.py` as needed. Run the full set and paste counts.

### T005 — ADR (FR-003)

**Purpose**: Record the behavioral change to `--fix` pruning.
**Steps**:
1. Create `docs/adr/3.x/2026-09-23-2-mission-state-repair-preserve-by-default.md`, status **Accepted**. Content: context (the reader/repair asymmetry + unregistered-future silent-loss), decision (preserve-by-default + EMPTY denylist + strengthened guard), consequences (what `--fix` now prunes vs before — only genuinely non-status no-`event_type` rows), and the #3066 lane-passthrough invariant.
2. Frontmatter `description` MUST be **50–180 chars AND unique + non-boilerplate** (SEO gate `scripts/docs/description_length_check.py` checks length *and* uniqueness/non-boilerplate — squad fold, architect). Any markdown table uses **spaced pipes** (`| --- |`, MD060). Cross-reference #4993 and PR #4938.
3. Do NOT regenerate the docs retrieval index / ADR inventory here — **WP04 owns those docs-index surfaces and regenerates them after this ADR lands** (see the WP04 ownership fold). Just author a well-formed ADR `.md`.

## Branch Strategy

Planning base and final merge target: `fix/silent-write-hardening-residuals`. The execution worktree for
this WP is allocated per the computed lane in `lanes.json` during `/spec-kitty.implement`; do not hand-create
branches. Completed changes merge back into `fix/silent-write-hardening-residuals` unless the operator redirects.

## Definition of Done

- T001 red-first test fails pre-fix, passes post-fix (SC-001).
- `_is_preserved_non_lane_row` preserves any `event_type`-bearing non-lane row; denylist constant is empty and documented (FR-001).
- Guard flags any quarantined `event_type`-bearing row; duplicate-`event_id` carve-out intact (FR-002, SC-005).
- `_is_legacy_typed_lane_transition` passthrough still FIRST (no #3066 regression).
- ADR present, description 50–180 chars, MD060-clean (FR-003).
- `ruff check` + `ruff format --check` clean on owned files; `mypy` clean on changed modules.
- Do NOT route through `asset_preservation` (C-001). Fail-closed toward retention (C-003).

## Reviewer guidance

Verify the reader==repair invariant against `store.py::is_non_lane_event` directly (don't trust the summary).
Confirm the lane-passthrough ordering and the duplicate-`event_id` carve-out. Re-run the red-first swap.
