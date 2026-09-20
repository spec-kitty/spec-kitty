---
work_package_id: WP01
title: Shared terminal-readiness authority (tidy-first enabler, behavior-preserving)
dependencies: []
requirement_refs:
- FR-009
planning_base_branch: issue-4764-terminus-safety-invariant
merge_target_branch: issue-4764-terminus-safety-invariant
branch_strategy: Planning artifacts for this mission were generated on issue-4764-terminus-safety-invariant. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4764-terminus-safety-invariant unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
history:
- created by planner-priti at 2026-09-19T19:43:00Z
agent_profile: python-pedro
authoritative_surface: src/specify_cli/status_lanes.py
create_intent:
- tests/status/test_mission_terminal_acceptability.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/status_lanes.py
- src/specify_cli/status/doctor.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before ANY other action, load the `python-pedro` profile via `/ad-hoc-profile-load` (skill `spk-doctrine-profile-load`, or `spec-kitty charter context --action implement` + `spec-kitty agent profile show python-pedro`). Adopt its identity, boundaries (implementer only — no architectural redesign, no scope expansion), and TDD/type-safety discipline for the entire WP. Do not proceed until the profile is loaded.

## Objective

Add ONE pure, provenance-aware aggregate reader `mission_terminal_acceptability(work_packages) -> (ok, missing_wp_ids)` to the orchestration-free `status_lanes.py`, and retire the duplicate terminal-lane set in `doctor.py`. The aggregate is a **snapshot-shaped, provenance-aware mission-level reader** built for the merge/close merge-readiness consumers (WP02, WP06) — it does NOT replace accept's lane views (see the scope note below). This is a **behavior-preserving tidy-first enabler** (DIRECTIVE_025) that the functional work packages consume. It delivers **FR-009** and satisfies **C-001** (single canonical authority — reuse `is_acceptable_ending`/`TERMINAL_LANES`, add at most ONE aggregate, introduce no 6th "done/terminal" definition).

**FR-009 framing (post-squad correction — FOLD 2).** The single per-lane authority `is_acceptable_ending` (`status_lanes.py:42`) is ALREADY shared by all three terminus commands — merge, accept, and close all route their per-lane classification through it today. Accept's two lane-bucket views (`gates_core._all_work_packages_terminal` :66 and `summary_core` :226) are **deliberately provenance-BLIND** (`is_acceptable_ending(lane, has_provenance=False)`); the provenance-aware decision is made upstream in `collect_feature_summary` / `AcceptanceSummary.all_done`. They already consume the canonical per-lane predicate, so C-001 is already satisfied on the accept surface. Rerouting them onto the new snapshot-shaped provenance-aware aggregate would either flip accept's cancelled-WP verdict or be a cosmetic no-op — so this WP does **NOT** touch them. The new aggregate is the mission-level reader that gives merge (WP02) and close (WP06) a single provenance-aware "is every non-cancelled WP at an acceptable ending?" answer, avoiding a 6th inline loop there.

**This WP changes no observable command behavior.** Accept and doctor must produce byte-identical verdicts/output before and after; the value is the new shared mission-level reader plus the doctor dedup.

## Context

- **Spec**: FR-009 (single shared terminal-readiness authority; scoped to the three `specify_cli` terminus commands — runtime-side inline loops are intentionally NOT rewired, protecting the shrink-only `runtime → specify_cli` layer ledger). US4 (completion commands agree on what "ready" means): US4-1 (all three route through one authority — satisfied by the shared per-lane `is_acceptable_ending` today, plus the new mission-level aggregate for merge/close), US4-2 (a provenance-cancelled WP is an acceptable ending under every command).
- **Contract**: `contracts/terminus-safety-contract.md` → **C-SHARED-AUTHORITY** (FR-009): `merge`, `accept`, `mission close` in `specify_cli` all derive terminal readiness from the shared per-lane authority `is_acceptable_ending`; merge and close additionally route their mission-level readiness through the one new aggregate (rather than a fresh inline loop). Accept's provenance-blind lane views already consume `is_acceptable_ending` and are left untouched (rerouting them would change accept's verdict — out of scope).
- **Data model**: `data-model.md` → the NEW `mission_terminal_acceptability(work_packages) -> (ok, missing_wp_ids)` predicate; keeps `is_acceptable_ending` / `merged` / `completed` DISTINCT (D4).
- **Seam anchors** (verified on this branch):
  - `src/specify_cli/status_lanes.py:25` — `TERMINAL_LANES: frozenset[str] = frozenset({"done", "canceled"})`
  - `src/specify_cli/status_lanes.py:42` — `def is_acceptable_ending(lane, *, has_provenance) -> bool`
  - `src/specify_cli/status_lanes.py:70` — `def has_operator_provenance(wp_snapshot) -> bool`
  - `src/specify_cli/acceptance/gates_core.py:66` — `def _all_work_packages_terminal(lanes)` (lane-only, `has_provenance=False`) — **NOT owned / NOT rerouted**; cited only as evidence that accept already routes through `is_acceptable_ending`. The provenance-aware decision is made upstream in `collect_feature_summary` / `AcceptanceSummary.all_done`.
  - `src/specify_cli/acceptance/summary_core.py:226` — inline `is_acceptable_ending(...)` over active lanes — **NOT owned / NOT rerouted** (same rationale).
  - `src/specify_cli/status/doctor.py:28` — `_TERMINAL_LANES: frozenset[Lane] = frozenset({Lane.DONE, Lane.CANCELED})` (duplicate — owned, retire)
  - `src/specify_cli/status/doctor.py:270` — inline `terminal_lanes = {Lane.DONE, Lane.CANCELED}` (duplicate — owned, retire)
- **Boundary note (C-002)**: `status_lanes` is NOT part of the `specify_cli.status` facade — importing from it directly is facade-safe and correct. The aggregate MUST live in `status_lanes` (orchestration-free) so functional WPs can import it without dragging orchestration deps.

## Per-Subtask Guidance

### T001 — RED-first unit tests for the aggregate truth table

Create `tests/status/test_mission_terminal_acceptability.py`. Assert the truth table DIRECTLY (this is a pure function — no CLI needed):
- Every WP `approved` ⇒ `(True, [])`.
- Every WP `done` ⇒ `(True, [])`.
- A WP `canceled` **with** operator provenance ⇒ acceptable (contributes nothing to `missing_wp_ids`) — **US4-2**.
- A WP `canceled` **without** operator provenance ⇒ NOT ready; that WP id appears in `missing_wp_ids` — **US1-6** (the operator-provenance check is load-bearing and must not be dropped).
- A WP `in_progress`/`for_review`/`planned` ⇒ NOT ready; WP id in `missing_wp_ids`.
- Mixed mission (some approved, one unapproved) ⇒ `(False, [that one])`; `missing_wp_ids` is deterministic (sorted).
- Empty / all-cancelled-with-provenance boundary — state the expected result explicitly (matches the merge-ready boundary in spec Edge Cases).

These tests are RED until T002 lands the function.

### T002 — Add the aggregate to `status_lanes.py`

Add `mission_terminal_acceptability(work_packages) -> tuple[bool, list[str]]` (a pure function; return the sorted missing-WP-id list). It MUST:
- reuse `is_acceptable_ending(lane, has_provenance=has_operator_provenance(snapshot))` per WP — do NOT re-derive the acceptable-ending rule;
- be provenance-aware (thread `has_operator_provenance` through, never call with a hardcoded `has_provenance=False` for the cancelled case);
- take work-package **snapshots** in the shape the merge/close consumers already have (align the parameter type with what `merge` (`executor.py` run state) and `close` (`mission_type.py`) pass — inspect those call sites, NOT the accept lane-bucket views, before fixing the signature).
- Add it to `status_lanes.__all__` if that module declares one.

### T003 — Confirm the accept surface is already single-authority (no reroute) + parity guard

**Do NOT reroute `gates_core._all_work_packages_terminal` (:66) or `summary_core` (:226).** Per the FOLD 2 correction, those are deliberately provenance-BLIND lane-bucket views that already consume the canonical per-lane `is_acceptable_ending` — C-001 is already satisfied there, and the provenance-aware decision is made upstream in `collect_feature_summary` / `AcceptanceSummary.all_done`. Rerouting them onto the snapshot-shaped provenance-aware aggregate would flip accept's cancelled-WP verdict (a behavior change, forbidden) or be a cosmetic no-op. These files are NOT in this WP's owned_files.

Instead: add/keep a **parity test** (in `tests/status/` or the existing acceptance suite) proving accept's verdict/warnings/guidance are UNCHANGED by this WP — the enduring guard that the new aggregate did not leak into the accept surface. The new `mission_terminal_acceptability` aggregate is wired into merge (WP02) and close (WP06), not accept.

### T004 — Retire the `doctor.py` duplicate

Replace `doctor.py:28` `_TERMINAL_LANES` and `:270` inline `terminal_lanes = {Lane.DONE, Lane.CANCELED}` with `status_lanes.TERMINAL_LANES`. Reconcile the type: `doctor.py` compares against `Lane` enum members while `TERMINAL_LANES` is `frozenset[str]` — convert at the call site (compare `lane.value` / normalize) WITHOUT widening or narrowing which lanes count as terminal. Keep `doctor`'s output identical (parity).

## Branch Strategy

- **Planning base branch**: `issue-4764-terminus-safety-invariant`.
- **Merge target branch**: `issue-4764-terminus-safety-invariant`.
- This mission implements on **ONE branch** (`issue-4764-terminus-safety-invariant`) directly — NOT in lane worktrees. Commit here; the mission branch later opens a PR to `main`, which the operator merges.
- Commit the T001 red-first test as a distinct commit BEFORE the T002 implementation commit.

## ATDD / Test Strategy (red-first defect)

- **Red-first**: T001's truth-table tests (including the cancelled-WITHOUT-provenance ⇒ not-ready negative, US1-6, and provenance-cancelled ⇒ ready, US4-2) are RED before T002 and GREEN after.
- **Behavior-preserving**: accept (T003 parity guard) and doctor (T004) parity tests prove no observable change — these are the enduring guard that the new aggregate did not leak into the accept/doctor surfaces.
- Run the aggregate's own tests plus the blast-radius directories: `tests/status/`, the acceptance test files (parity — accept is not modified but must be proven unchanged), and the doctor tests. Record commands + counts.

## Definition of Done

- [ ] `mission_terminal_acceptability` lives in `status_lanes.py`, pure and provenance-aware, reusing `is_acceptable_ending`/`TERMINAL_LANES`; snapshot-shaped for the merge/close consumers.
- [ ] T001 truth-table tests green (incl. US1-6 negative and US4-2 positive).
- [ ] Accept's lane views (`gates_core`/`summary_core`) are NOT modified; a parity test proves accept's verdict/warnings/guidance are unchanged (FOLD 2).
- [ ] `doctor.py` duplicate terminal-set retired → `status_lanes.TERMINAL_LANES`; doctor parity green.
- [ ] No 6th "done/terminal" definition introduced (C-001); no change to observable accept/doctor behavior.
- [ ] `ruff check` + `ruff format --check` + `mypy` clean on touched files; touched/new functions C901 ≤ 15 (C-006).
- [ ] `[Unreleased]` CHANGELOG note (impact-first, no version number — C-005).

## Risks

- **Scope-creep into accept** — mistakenly rerouting the provenance-blind accept lane views (would flip the cancelled-WP verdict). Mitigation: accept files are un-owned; a parity test proves accept is unchanged (FOLD 2).
- **`Lane` enum vs `frozenset[str]` mismatch** in doctor — a naive swap can flip which lanes count as terminal. Mitigation: convert at the call site and assert doctor parity.
- **Signature over-reach** — inventing a snapshot shape the consumers do not have. Mitigation: read the merge (`executor.py` run state) and close (`mission_type.py`) call sites first; align the parameter to what they pass.

## Reviewer Guidance (reviewer-renata)

- Confirm the aggregate reuses `is_acceptable_ending` and does NOT re-inline the accept/cancel rule (C-001).
- Confirm provenance is threaded through (a cancelled-without-provenance WP is NOT ready) — this is the load-bearing check per US1-6.
- Confirm the accept lane views (`gates_core`/`summary_core`) are UNCHANGED (FOLD 2) — a parity test proves accept's verdict/warnings/guidance do not drift; those files are not owned by this WP.
- Confirm doctor produces identical output before/after (parity test present and meaningful).
- Confirm the import is from `status_lanes` directly (facade-safe) and the runtime-side loops are NOT touched (layer-ledger protection, C-002).
