---
work_package_id: WP07
title: Accept guidance liveness (#2745 facet 2)
dependencies:
- WP01
requirement_refs:
- FR-014
planning_base_branch: issue-4764-terminus-safety-invariant
merge_target_branch: issue-4764-terminus-safety-invariant
branch_strategy: Planning artifacts for this mission were generated on issue-4764-terminus-safety-invariant. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4764-terminus-safety-invariant unless the human explicitly redirects the landing branch.
subtasks:
- T020
history:
- created by planner-priti at 2026-09-19T19:43:00Z
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/accept.py
create_intent:
- tests/specify_cli/cli/commands/test_accept_guidance_liveness.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/cli/commands/accept.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before ANY other action, load the `python-pedro` profile via `/ad-hoc-profile-load` (skill `spk-doctrine-profile-load`, or `spec-kitty charter context --action implement` + `spec-kitty agent profile show python-pedro`). Adopt its identity, implementer-only boundaries, and TDD/type-safety discipline. Do not proceed until the profile is loaded.

## Objective

Confirm `accept` gives **followable** guidance (it names the real escape hatch) rather than impossible "materialize-then-retry" instructions when a mission has no lane branch. Per FR-014 and the research, the protected-primary hard-reject **appears already removed** at `accept.py:1007`. This WP is a **liveness confirmation**: write a red-first probe; if it is GREEN on current main, document it as **verified-already-fixed** (do NOT fabricate a red). If it genuinely reproduces, fix it. Keep this WP small. Delivers **FR-014**.

## Context

- **Spec**: US5 tail / FR-014 (accept escape-hatch guidance is followable). FR-014 is explicitly a liveness confirmation — "the protected-primary hard-reject appears already removed (`accept.py`); verified-already-fixed if a red-first probe cannot reproduce it, otherwise fixed." SC-004 anti-fabrication clause: "Where a facet is verified-already-fixed (e.g. #2745 accept guidance), the red-first probe is documented as green-on-current-main rather than fabricated."
- **Contract**: `contracts/terminus-safety-contract.md` → **C-ACCEPT-GUIDANCE**: `accept` gives followable guidance (names the real escape hatch), not impossible "materialize-then-retry". Liveness: verified-already-fixed if a red-first probe is green on current main.
- **Research** (`research.md`): Facet-2 (accept guidance) — the protected-primary hard-reject was already removed (`accept.py:1007`); a red-first probe expected green-on-main.
- **Seam anchors** (verified on this branch):
  - `src/specify_cli/cli/commands/accept.py:1005-1012` — the comment recording that the protected-primary hard reject "is no longer a hard reject here" and the pre-flight raise-and-exit deadlock "has been removed" (T015/WP04/FR-001 / C-001/FR-003 of the earlier mission). This is the evidence the facet is already fixed.
  - `accept` is genuinely gate-then-mutate already (research disposition: accept is the precedent US4/FR-009 relies on).

## Per-Subtask Guidance

### T020 — Accept guidance liveness probe

Create `tests/specify_cli/cli/commands/test_accept_guidance_liveness.py`, `@pytest.mark.regression`, referencing #2745 (facet 2 / FR-014). Through the pre-existing `accept` CLI entry point, exercise a mission with no lane branch (the scenario that historically produced the impossible "materialize-then-retry" guidance / protected-primary hard reject). The probe MUST be **substantive, not tautological**: assert the accept output SUBSTANTIVELY NAMES the real escape hatch (the concrete followable command/flag an operator can run) and does NOT emit the impossible "materialize-then-retry" instruction — do NOT assert something vacuous like "exit code is 0" or "no exception". A reviewer must be able to see, from the assertion, that the guidance is genuinely followable.

Two honest outcomes (SC-004):
- **Verified-already-fixed** (expected): the probe is GREEN on current main (the hard-reject at :1007 is already gone). Document this in the WP notes/PR as verified-already-fixed with the `accept.py:1005-1012` evidence — do NOT fabricate a red-then-green cycle, and do NOT invent a code change to manufacture a diff. The probe stands as an enduring regression guard that the guidance stays followable.
- **Genuinely reproducible** (unexpected): if the probe is actually red on current main, fix `accept.py` so the guidance is followable, keeping the change minimal.

## Branch Strategy

- **Planning base branch** and **merge target branch**: `issue-4764-terminus-safety-invariant`.
- Implement on the **single mission branch** directly — NOT lane worktrees. PR to `main` opens later; the operator merges.
- If verified-already-fixed, the WP's diff is the probe test only (plus a CHANGELOG note).

## ATDD / Test Strategy (red-first defect)

- **Liveness probe** `@pytest.mark.regression` (T020): expected GREEN on current main ⇒ documented as verified-already-fixed. If genuinely red, fix and make green.
- Anti-fabrication is load-bearing (C-004 / SC-004): a green probe is documented honestly, never dressed up as a red-first cycle.
- Run the accept CLI tests (`tests/specify_cli/cli/commands/` accept files) plus the acceptance suites. Record commands + counts.

## Definition of Done

- [ ] A liveness probe SUBSTANTIVELY asserts `accept` names the real escape hatch (concrete followable command/flag) and omits the impossible "materialize-then-retry" instruction — not a tautological exit-0/no-exception check (FOLD 5). Committed as an enduring regression guard.
- [ ] The WP notes / PR body PASTE the ACTUAL green probe run — the exact command and its pass count (e.g. `... 1 passed`) — as the verified-already-fixed evidence (FOLD 5), alongside the `accept.py:1005-1012` code evidence.
- [ ] Outcome documented honestly: either verified-already-fixed (green on main) OR a minimal fix making a genuinely-red probe green — never a fabricated red-first cycle.
- [ ] `ruff` + `ruff format --check` + `mypy` clean on any touched code.
- [ ] `[Unreleased]` CHANGELOG note (impact-first, no version — C-005).

## Risks

- **Fabrication temptation** — inventing a code change or a fake red to manufacture a red-first cycle for an already-fixed facet. Mitigation: document verified-already-fixed honestly (SC-004); the probe is the deliverable.
- **Scope creep** — expanding accept beyond the guidance-liveness confirmation. Mitigation: keep the WP small; owned file is `accept.py` only.

## Reviewer Guidance (reviewer-renata)

- Confirm the probe genuinely exercises the no-lane-branch guidance path through the real `accept` CLI and asserts SUBSTANTIVELY (names the real escape hatch), not tautologically (FOLD 5).
- Confirm the WP notes/PR paste the actual green probe run (command + pass count) as evidence (FOLD 5).
- Confirm the outcome is documented honestly — verified-already-fixed (green on main) is acceptable and expected; a fabricated red-first cycle is not (SC-004).
- Confirm the probe is an enduring guard (guidance stays followable), not a throwaway.
