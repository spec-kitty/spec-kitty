---
work_package_id: WP04
title: 'Docs & tracker close-out: CHANGELOG + #4993 correction'
dependencies:
- WP01
- WP02
- WP03
requirement_refs:
- C-005
- FR-007
planning_base_branch: fix/silent-write-hardening-residuals
merge_target_branch: fix/silent-write-hardening-residuals
branch_strategy: Planning artifacts for this mission were generated on fix/silent-write-hardening-residuals. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/silent-write-hardening-residuals unless the human explicitly redirects the landing branch.
subtasks:
- T015
- T016
- T017
history:
- event: created
  at: '2026-09-23T19:24:56Z'
  actor: architect-alphonso
agent_profile: scribe-sally
authoritative_surface: docs/changelog/
create_intent: []
execution_mode: planning_artifact
owned_files:
- docs/changelog/CHANGELOG.md
- docs/adr/3.x/index.md
- docs/development/3-2-page-inventory.yaml
- docs/development/3-2-docs-retrieval-index.yaml
role: implementer
tags: []
tracker_refs:
- '#4993'
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else in this prompt, load your assigned agent profile:

```
/ad-hoc-profile-load scribe-sally
```

This profile governs your writing style, boundaries, and quality standards for this work package.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``. Use language identifiers in code blocks.

---

## Objective

Close out the mission's user-facing record: a consumer-focused CHANGELOG entry, the #4993 close-out with the
reader-count correction (3→2), and the terminology + docs-freshness gates. This WP depends on WP01–WP03 so the
changelog describes **landed** behavior.

## Subtasks

### T015 — CHANGELOG entry

**Steps**: Add one entry to the canonical `docs/changelog/CHANGELOG.md` (the root `CHANGELOG.md` is a symlink —
edit the canonical one) under `[Unreleased] → Fixed`. Match the existing style exactly: a **bold lead sentence
stating the user-facing impact with a (mission; `#4993`) ref**, then a plain-language before→after. Lead with
the operator symptom, e.g.: *"`spec-kitty doctor mission-state --fix` no longer silently drops an authoritative
mission record whose type a newer subsystem introduced (mission; `#4993`)."* Then briefly note the two adjacent
hardenings (one charter-config reader; traces merge of unusual markdown). No internal jargon in the lead.
⚠️ Editing this file subjects its whole markdownlint violation set to the gate — budget for the file, not just
your lines; run the repo's own markdownlint invocation.

### T016 — #4993 close-out + reader-count correction

**Steps**: Draft the close-out text for the PR body / issue-matrix: this mission resolves #4993 (epic #2720),
and **corrects #4993's "three `catalog.mission` readers" to two** (the claimed third reads `catalog.languages`).
Ensure the PR body will carry `Closes #4993`. (The actual issue comment/close is an operator/landing action;
this subtask produces the text and the issue-matrix note so approval is not gated by a bare `#4993`.)

### T017 — Regenerate ADR-index surfaces + terminology/docs-freshness gates

> **Squad fold (architect-alphonso, blocking MAJOR):** WP01's new ADR
> (`docs/adr/3.x/2026-09-23-2-mission-state-repair-preserve-by-default.md`) forces edits to three
> committed docs-index surfaces that **this WP now owns**. WP04 runs after WP01 (dependency), so it is
> the correct owner — it sees the landed ADR and regenerates against it. Do NOT leave this as "coordinate."

**Steps**:
1. Regenerate/append the ADR-index surfaces so the new ADR is registered (else error-severity, blocking
   `LEAK-MISSING-INVENTORY` / `INVENTORY-LOCKFILE-DRIFT` / `DOCS-INDEX-DRIFT`):
   - `PYTHONPATH=. uv run python -m scripts.docs.freshen_adr_inventory` (updates `docs/development/3-2-page-inventory.yaml`)
   - `PYTHONPATH=. uv run python -m scripts.docs.docs_index --write` (updates `docs/development/3-2-docs-retrieval-index.yaml`)
   - Add the new ADR row to the curated `docs/adr/3.x/index.md` table (spaced pipes, MD060).
   Verify against the exact script names/paths in the tree before running; use the invocation the freshness
   gate itself uses.
2. Add the CHANGELOG entry (T015) and #4993 close-out text (T016) must already be in place.
3. Run the terminology guard (`tests/architectural/test_no_legacy_terminology.py`) and
   `scripts/docs/check_docs_freshness.py --ci` (expect `errors=0`; external-URL link-health WARNINGS are fine).
   This WP's DoD (`errors=0`) is now satisfiable because it owns and regenerates the index surfaces —
   no lane-scope pollution.

## Branch Strategy

Planning base and final merge target: `fix/silent-write-hardening-residuals`. Execution worktree allocated per
`lanes.json` lane during `/spec-kitty.implement`; do not hand-create branches.

## Definition of Done

- Consumer-focused CHANGELOG entry under `[Unreleased] → Fixed`, style-matched, markdownlint-clean for the file (FR-007).
- #4993 close-out text + reader-count correction ready for the PR body / issue-matrix (FR-007).
- New ADR registered in `docs/development/3-2-page-inventory.yaml`, `docs/development/3-2-docs-retrieval-index.yaml`, and `docs/adr/3.x/index.md` (squad fold — no LEAK-MISSING-INVENTORY / DOCS-INDEX-DRIFT).
- Terminology guard green; `check_docs_freshness --ci` errors=0.
- Mission terminology only (C-005).

## Reviewer guidance

Confirm the changelog lead is operator-legible (symptom-first, no jargon) and the (`#4993`) ref is present.
Confirm the 3→2 correction is stated. Confirm freshness/terminology gates pass.
