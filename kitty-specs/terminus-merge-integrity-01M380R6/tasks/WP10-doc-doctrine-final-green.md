---
work_package_id: WP10
title: Doc/doctrine correction + final green (FR-013)
dependencies:
- WP03
- WP04
- WP05
- WP09
requirement_refs:
- FR-013
planning_base_branch: fix/terminus-merge-integrity
merge_target_branch: fix/terminus-merge-integrity
branch_strategy: Planning artifacts for this mission were generated on fix/terminus-merge-integrity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/terminus-merge-integrity unless the human explicitly redirects the landing branch.
subtasks:
- T044
- T045
- T046
phase: Phase 4 - Integration
history:
- at: '2026-09-23T21:36:42Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: curator-carla
authoritative_surface: docs/architecture/status-model.md
create_intent: []
execution_mode: code_change
owned_files:
- CLAUDE.md
- docs/adr/2.x/2026-02-09-3-event-log-merge-semantics.md
- docs/architecture/status-model.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP10 – Doc/doctrine correction + final green (FR-013)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load `curator-carla` (frontmatter) before parsing the rest of
this prompt, and behave according to its guidance.

- **Profile**: `curator-carla` · **Role**: `implementer` · **Agent/tool**: `claude`

Apply the resolved boundaries (knowledge-base/doctrine correction; do NOT re-open code decisions) and
canonical-terminology discipline. State what you applied, then continue.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use fenced code-block language identifiers.

---

## Objectives & Success Criteria

Correct the docs/doctrine that assert guarantees the code lacked, and prove the whole mission green.
Success (FR-013; DIRECTIVE_010; C-005):

- CLAUDE.md's **false** compare-and-swap-advance claim and its "status.events.jsonl sole authority;
  reducer deterministic event→snapshot" claim are corrected to match the shipped code (CAS now real
  per WP02/WP06; the reducer split-brain #4990 remains **named-open**, NOT claimed fixed).
- ADR `2026-02-09-3` carries a reconciliation note that keeps **#4990 named-open** and reconciles the
  referenced guarantees with what this mission actually shipped.
- `docs/architecture/status-model.md` is corrected where it over-claims reducer determinism.
- The full blast-radius suite (quickstart.md commands) is green.

## Context & Constraints

- Spec: [../spec.md](../spec.md) FR-013, C-002 (do NOT claim #4990 fixed), C-005 (name the
  primary/merge/routing senses). DEBRIEF §6 (doc/code mismatch table). Contract §"#4990 stays
  named-open".
- **What to correct (grounded)**:
  - CLAUDE.md: the "update-ref advances are compare-and-swap" line was false pre-fix
    (`ref_advance.py:410` was 2-arg) — now TRUE after WP02; state it accurately and cite the CAS.
  - CLAUDE.md Status-model section: "status.events.jsonl sole authority; reducer deterministic
    event→snapshot" over-claims — two reducers ship (Lamport `materialize` vs LWW `reduce_parsed`);
    #4990 (the LWW split-brain) is a **separate, open** sibling mission. Correct the claim; keep
    #4990 named-open. Do NOT assert this mission fixed the reducer.
  - ADR `docs/adr/2.x/2026-02-09-3-event-log-merge-semantics.md`: add the reconciliation note.
  - `docs/architecture/status-model.md`: align the reducer-determinism wording.
- **Terminology guard (pre-push, mandatory when touching prose/CLAUDE.md)**: run
  `pytest tests/architectural/test_no_legacy_terminology.py -q` (≈0.1 s) — gates the two retired
  terms (canonical `status commit`, never `ceremony`/`status-writing`). Name the `primary`/`merge`/
  `routing` senses where they appear (C-005).
- Locality (C-004): only the three owned docs. No code edits (the code landed in WP02–WP09).

## Branch Strategy

- **Strategy**: integration, after WP03/WP04/WP05/WP09 (all fixes present so the docs describe
  shipped behavior and the final green run exercises everything).
- **Planning base branch / Merge target branch**: `fix/terminus-merge-integrity`.

## Subtasks & Detailed Guidance

### T044 – Correct CLAUDE.md false claims
- **Purpose**: DIRECTIVE_010 — docs must not assert guarantees the code lacked.
- **Steps**:
  1. Update the compare-and-swap-advance statement to reflect the now-real CAS in
     `advance_branch_ref` (WP02), citing the 3-arg `update-ref ref new old` shape.
  2. Correct the "sole-authority deterministic reducer" claim: note that two reducers ship (Lamport
     `materialize` vs LWW `reduce_parsed`), that the merge/reconciliation gate sources its claim
     through the **Lamport** wrapper, and that the LWW split-brain (#4990) is a **separate open**
     mission — not fixed here.
  3. Name the `primary`/`merge`/`routing` senses wherever the edited passages use them (C-005).
- **Files**: `CLAUDE.md`.
- **Notes**: any `CLAUDE.md` change that is NOT a version-bump-triggering `__init__.py` change still
  warrants a CHANGELOG line (close-out checklist) — but do not edit `__init__.py` or `pyproject.toml`.

### T045 – Correct ADR 2026-02-09-3 + status-model.md (keep #4990 named-open)
- **Purpose**: reconcile the referenced guarantees; keep the open sibling honest.
- **Steps**:
  1. In ADR `2026-02-09-3-event-log-merge-semantics.md`, add a reconciliation note: the merge gate is
     Lamport-sourced for its own claim; the general reducer LWW split-brain (#4990) remains open and
     is tracked as a separate mission. Do NOT mark #4990 resolved.
  2. In `docs/architecture/status-model.md`, align any reducer-determinism wording with reality
     (Lamport-primary per this ADR; LWW `reduce_parsed` still present pending #4990).
- **Files**: `docs/adr/2.x/2026-02-09-3-event-log-merge-semantics.md`,
  `docs/architecture/status-model.md`.

### T046 – Final green: full blast-radius suite
- **Purpose**: SC-002/SC-005 — 12/12 repros green, happy-path parity, gates clean.
- **Steps** (from [../quickstart.md](../quickstart.md)):
  1. Tier-0 property: `PWHEADLESS=1 .venv/bin/python -m pytest tests/terminus/ -k "terminus_reconciliation and property" -q`.
  2. 12 per-child repros: `PWHEADLESS=1 .venv/bin/python -m pytest tests/terminus tests/merge tests/coordination tests/git tests/lanes -q`.
  3. Shared baseline: `make test-fast`.
  4. Docs guard: `pytest tests/architectural/test_no_legacy_terminology.py -q`.
  5. Gates: `ruff check . && ruff format --check .`; `mypy src/specify_cli/{merge,coordination,git,lanes}`.
  Paste the actual terminal output (not hand-typed counts) into the WP/PR *Tests run* section.
- **Files**: none edited here — this is the verification gate. (Do NOT run `make test-full`/whole-repo
  — the CI agent owns that.)
- **Notes**: if any repro is still red, it is a real gap in an upstream WP — file it back, do NOT
  green-wash (red-main discipline).

## Test Strategy

- This WP's "tests" are the aggregate blast-radius run in T046; it authors no new test file.
- Docs-touch terminology guard is mandatory before push.

## Risks & Mitigations

- **Over-claiming verdict-integrity**: a green Tier-0 proves approved-WP commit reachability only —
  #4990 stays named-open; do not imply the reducer is fixed (PP-F4).
- **Legacy terminology regression**: run the terminology guard (it can pass a local prose run and only
  surface at CI).

## Definition of Done

- CLAUDE.md's compare-and-swap-advance claim matches the shipped 3-arg CAS; the "sole-authority
  deterministic reducer" claim is corrected with #4990 named-open (not claimed fixed).
- ADR `2026-02-09-3` + `status-model.md` carry reconciliation notes that keep #4990 open.
- `pytest tests/architectural/test_no_legacy_terminology.py -q` green (docs-touch guard); the
  `primary`/`merge`/`routing` senses are named where edited.
- The full blast-radius run (T046) is pasted: Tier-0 property GREEN, 12/12 per-child repros GREEN,
  `make test-fast` green, `ruff check .` + `ruff format --check .` clean,
  `mypy src/specify_cli/{merge,coordination,git,lanes}` clean.
- No code edited here; no `__init__.py`/`pyproject.toml` change; the CHANGELOG line is left to the
  close-out checklist.

## Review Guidance

- Confirm CLAUDE.md's CAS + reducer claims now match shipped code, #4990 named-open.
- Confirm the ADR + status-model reconciliation notes keep #4990 open.
- Confirm the final green run output is pasted (12/12 repros + property + gates).
- Confirm no verdict-integrity is over-claimed while #4990 is open (PP-F4).

## Activity Log

> **CRITICAL**: chronological order, append to END, current UTC time.

- 2026-09-23T21:36:42Z – system – Prompt created.

### Updating Status

`spec-kitty agent tasks move-task WP10 --to <lane>`.
