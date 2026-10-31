---
work_package_id: WP02
title: Record the rule in the ADR and the changelog
dependencies:
- WP01
requirement_refs:
- FR-007
- SC-003
planning_base_branch: issue-6688-residue-successor-retry
merge_target_branch: issue-6688-residue-successor-retry
branch_strategy: Planning artifacts for this mission were generated on issue-6688-residue-successor-retry. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6688-residue-successor-retry unless the human explicitly redirects the landing branch.
subtasks:
- T009
- T010
- T011
phase: Phase 2 - Documentation
history:
- at: '2026-10-30T23:30:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/
create_intent: []
execution_mode: planning_artifact
owned_files:
- docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: documentation
tracker_refs:
- spec-kitty/spec-kitty#6688
---

# Work Package Prompt: WP02 – Record the rule in the ADR and the changelog

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (implementer) and behave
according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: implementer
- **Agent/tool**: claude

---

## Objectives & Success Criteria

The ledger ADR currently records `C-006` as an accepted residual: a successor is not retried on a
pre-ledger project whose predecessor never settled. WP01 removes that residual. This WP records the
replacement rule where a reader looks for it, and gives the fix a user-facing changelog entry.

Success means:

- `docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md` states the retry rule (a successor is
  settled by its predecessor's outcome, not by an adoption-baseline record), drops `C-006` from the
  accepted-residual list, and keeps the rejected-route reasoning;
- `docs/changelog/CHANGELOG.md` has an `[Unreleased]` entry with an impact-first bold lead and
  `(#6688)`, before/after, under 1,200 characters;
- `uv run python -m scripts.docs.check_docs_freshness --ci` reports errors=0 and
  `uv run pytest tests/architectural/test_no_legacy_terminology.py -q` is green.

## Context

Read first:

- `docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md` — the "selection view" section,
  Amendment 2026-10-25b (#6669) and its **Accepted residuals** list, where `C-006` sits.
- `docs/changelog/CHANGELOG.md` — the `[Unreleased]` block and the shape of neighbouring upgrade
  entries (impact-first bold lead, `(#NNNN)`, before/after, under 1,200 characters).
- `kitty-specs/residue-successor-retry-on-unsettled-predecessor-01M67J1B/spec.md` (Decision section)
  and `research.md` (decisions D1-D4, rejected routes).

## Subtasks

### T009 — the ADR amendment

Add an amendment (dated for this change, `(#6688)`) in the same style as 2026-10-25b:

- **Problem**: a pre-ledger project whose predecessor recorded `failed`/`skipped` has the successor
  stamped `success` by the adoption baseline, so the repair is never retried (`C-006`).
- **Decision**: the successor's settlement follows the predecessor's outcome. A migration that
  declares a `predecessor_id` is settled only when the predecessor is settled (`success`, or a
  pending adoption that will record one). Selection and the runner's skip gate both reach this
  through `reselect_when_recorded` → one registry predicate, so they cannot disagree. `detect()`
  stays the idempotency guard: a repaired project is re-evaluated, never re-applied.
- **Routes rejected**: route 1 (mark adoption-baseline records) edits the frozen backfill
  (DIRECTIVE_044) and needs a ledger schema addition; route 3 (raise each successor's
  `target_version`) changes manifest semantics and drops the repair from intermediate targets.
- **Residuals**: remove `C-006`; keep the others (a stale "pending" listing survives and is now
  slightly wider — name it: a successor whose predecessor never settled is re-evaluated on every
  run and re-skips, which is idempotent and harmless).

Update the "selection view" bullet so it no longer claims `detect()` is gated on the predecessor's
settlement alone; it is also the gate that keeps a completed repair from re-running.

### T010 — the changelog entry

Under `[Unreleased]`, impact first: upgrading a project that predates the migration ledger now
retries a residue-safe repair whose predecessor recorded `failed`/`skipped`. Before: first adoption
stamped the successor `success` and the repair was lost. After: the successor runs when the
predecessor's outcome does not prove the work was done, and never re-runs once `detect()` reports
the project clean. Reference `(#6688)`. Keep it under 1,200 characters and in the file's existing
voice.

### T011 — verify

```bash
uv run python -m scripts.docs.check_docs_freshness --ci
uv run pytest tests/architectural/test_no_legacy_terminology.py -q
```

Both must be green (errors=0). Do not rebuild the whole CLI reference; this diff adds no command
surface.

## Definition of Done

- [ ] ADR amendment present, `C-006` removed from accepted residuals, the replacement residual named.
- [ ] Changelog entry present under `[Unreleased]` with `(#6688)`, under 1,200 characters.
- [ ] Docs freshness and terminology gates green.

## Risks

- Restating the implementation instead of the decision: the ADR paragraph must say what is now true
  and which route was chosen, not walk through functions.
- Changelog churn against other in-flight PRs: keep the entry to its own bullet block and re-read the
  file before committing; keep both sides' entries on a rebase conflict.

## Reviewer Guidance

- Does the ADR now describe the rule a future maintainer needs, with the rejected routes?
- Is any residual still claimed that the code no longer has, or vice versa?
- Is the changelog entry impact-first and honest about the re-evaluation behaviour?
