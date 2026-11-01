---
work_package_id: WP04
title: Contract, docs and changelog
dependencies:
- WP01
- WP02
- WP03
requirement_refs:
- FR-006
- SC-004
- C-001
planning_base_branch: issue-6385-retrospect-synthesize-generator-proposals
merge_target_branch: issue-6385-retrospect-synthesize-generator-proposals
branch_strategy: Planning artifacts for this mission were generated on issue-6385-retrospect-synthesize-generator-proposals. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6385-retrospect-synthesize-generator-proposals unless the human explicitly redirects the landing branch.
created_at: '2026-10-31T12:50:00Z'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 4 - Documentation
history:
- at: '2026-10-31T12:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- docs/api/retrospective-schema.md
- docs/guides/how-to/governance/use-retrospective-learning.md
- docs/changelog/CHANGELOG.md
- kitty-specs/retrospective-default-policy-01KS049J/contracts/retrospective-record.schema.json
role: documentarian
tags: []
task_type: implement
tracker_refs:
- '#6385'
---

# Work Package Prompt: WP04 – Contract, docs and changelog

## ⚡ Do This First: Load Agent Profile

- **Profile**: `scribe-sally` · **Role**: `documentarian`

```bash
spec-kitty agent profile show scribe-sally
spec-kitty charter context --action implement
```

---

## Context

WP01–WP03 ship the behaviour. This WP makes the contract and the documentation true, which is half
of the issue's own acceptable resolution: "the docs and `create` output say plainly that synthesize
is not usable on created records yet". The `create` output half is WP03; this is the docs half.

Facts to state, and to state plainly:

- `retrospect create` writes a **generator-shape** record whose `proposals` list is empty today;
  grading findings into proposals is tracked separately in #3947.
- A generator-shape proposal is planned only when it carries a `payload` block, which is validated by
  the same discriminated union `synthesize` applies (`synthesize_directive`, `synthesize_tactic`,
  `synthesize_procedure`, `rewire_edge`, `add_edge`, `remove_edge`, `add_glossary_term`,
  `update_glossary_term`, `flag_not_helpful`).
- A `synthesize` dry-run on a generator-shape record now reports a `diagnostics` block: record
  schema, finding counts, translated/planned counts, every untranslatable proposal with its reason,
  and the next action.
- Exit codes are unchanged; the empty batch is a diagnostic, not an error.

## Subtasks

- **T001** — `kitty-specs/retrospective-default-policy-01KS049J/contracts/retrospective-record.schema.json`:
  add the optional `payload` property to the proposal definition (an object; the nested `ProposalPayload`
  union in `src/specify_cli/retrospective/schema.py` remains the machine authority — say so in the
  property description rather than duplicating the union).
- **T002** — `docs/api/retrospective-schema.md`: a "Generator-shape records" subsection (what `create`
  writes, the `payload` seam, the `diagnostics` block, the unchanged exit codes) and the cross-link to
  #3947.
- **T003** — `docs/guides/how-to/governance/use-retrospective-learning.md`: the create → synthesize
  loop section, in operator terms: what works today, what a proposal needs to be plannable, and what
  the operator will see when a record plans nothing.
- **T004** — `docs/changelog/CHANGELOG.md` under `[Unreleased]`: bold impact-first lead with
  `(#6385)`, then before/after, under 1,200 characters, in the file's existing style.
- **T005** — `uv run python -m scripts.docs.check_docs_freshness --ci` (expect errors=0) and
  `uv run pytest tests/architectural/test_no_legacy_terminology.py -q`.

## Hard rules

- Root `CHANGELOG.md` is a **symlink** to `docs/changelog/CHANGELOG.md`: edit the target file, never
  replace the symlink.
- Do not rebuild the whole `docs/api/cli-commands.md` reference (shared machine state: other agents
  regenerate the same surface concurrently). Regenerate only what this diff changes.
- Divio discipline: reference content stays in the reference page, the walkthrough stays in the
  how-to. Do not duplicate the union's field tables into the how-to.
- No invented behaviour: every sentence must be true of the shipped code. If a claim needs a check,
  run the command.

## Definition of Done

- Contract JSON valid (`python -c "import json;json.load(open(...))"`) and the `payload` property
  present.
- Both doc pages describe the shipped behaviour and name #3947 for the generation half.
- Changelog entry present, under 1,200 characters, with the `(#6385)` reference.
- `check_docs_freshness --ci` errors=0; terminology test green.

## Branch strategy

Same planning branch and merge target as WP01–WP03; execution worktrees come from `lanes.json`.

## Reviewer guidance

- Does any page still promise that `create` → `synthesize` produces proposals today?
- Is the contract change additive and consistent with `schema.py`?
- Is the changelog entry impact-first and within the length cap?
