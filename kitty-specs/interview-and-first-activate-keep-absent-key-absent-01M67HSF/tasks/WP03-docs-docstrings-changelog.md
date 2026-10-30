---
work_package_id: WP03
title: Docs, docstrings and the record
dependencies:
- WP01
- WP02
requirement_refs:
- FR-009
- FR-010
- NFR-003
- SC-001
- SC-002
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts were generated on main. The mission's implementation runs on issue-6685-interview-and-first-activate-keep-absent-key-absent and merges back into main through the operator's PR.
subtasks:
- T009
- T010
- T011
- T012
phase: Phase 3 - Docs, docstrings and the record
history:
- at: '2026-10-30T23:30:00Z'
  actor: system
  action: Prompt authored for the #6685 mission
agent_profile: python-pedro
authoritative_surface: docs/
create_intent:
- docs/changelog/CHANGELOG.md
execution_mode: code_change
model: ''
owned_files:
- docs/changelog/CHANGELOG.md
- docs/ (the operator pages for charter interview and charter activate)
- src/specify_cli/cli/commands/charter/interview.py
- src/charter/activation/pack_manager.py
- tests/acceptance/charter_pack_cutover/test_promotion.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6685'
---

# Work Package Prompt: WP03 – Docs, docstrings and the record

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?** Check the `review_ref` field in the event log (`spec-kitty agent tasks status`).
- Address every feedback item, and record each change with `spec-kitty agent tasks add-history WP03 --note "..."`.

---

## Objectives & Success Criteria

- No docstring still calls the interview seeding a residual: `interview.py` and `pack_manager.py` state the absent-key rule and name `--narrow-activation` / `--only` as the explicit path (FR-010).
- The operator docs for `charter interview` and `charter activate` say that an absent key is never filled, what happens instead, and how to choose a list (FR-010).
- `docs/changelog/CHANGELOG.md` has an `[Unreleased]` entry: bold impact-first lead with `(#6685)`, before/after, under 1,200 characters (FR-009).
- The targeted gates are green: terminology, effective-set seam, kind vocabulary, docs freshness with `errors=0` (NFR-003).

## Context & Constraints

- Find the operator pages first: `grep -rln "charter interview\|charter activate" docs/` — update only the pages this behaviour change invalidates.
- Regenerate only the docs surface this diff changes (other agents share the installed CLI's asset cache). Verify with `uv run python -m scripts.docs.check_docs_freshness --ci` and require `errors=0` rather than a clean full rebuild. If `docs/api/cli-commands.md` would need a whole-reference rebuild, say so in the PR's `## Deferred` instead of producing churn.
- The changelog entry follows the existing style: read the last few `[Unreleased]` entries before writing.
- Terminology: "activation ledger" vs "Migration Ledger", never bare "ledger"; "Mission", not "feature".

## Branch Strategy

- **Strategy**: planning artifacts were generated on `main`; implementation runs on `issue-6685-interview-and-first-activate-keep-absent-key-absent`.
- **Planning base branch**: `main`
- **Merge target branch**: `main` (via the operator's PR; never push `main`)

Implementation command:

```bash
spec-kitty agent action implement WP03 --agent pi --mission interview-and-first-activate-keep-absent-key-absent-01M67HSF
```

## Subtasks

### T009 — Docstrings that name the seeding as a residual

Sweep for `#6408 residual`, "absent-key parity", "Preserved N effective entries" and "This list is now explicit" wording that this change makes false, and update it.

### T010 — Operator docs for `charter interview` and `charter activate`

State the rule once per page where the operator meets it: an absent `activated_<kind>` key means the whole kind is in force, so neither the interview nor a first activation writes a list; `--narrow-activation` / `--only` writes one and names what stops being in force.

### T011 — CHANGELOG entry

Under `[Unreleased]`, one entry: impact first (a first `charter interview` or `charter activate` no longer blocks `charter synthesize`), then before/after, then `(#6685)`. Under 1,200 characters.

### T012 — Targeted gates: terminology, docs freshness, effective-set seam, kind vocabulary

Run, and record the counts:

```bash
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
uv run --frozen pytest tests/acceptance/charter_pack_cutover/test_promotion.py::test_fr015_effective_set_seam_is_public -q
uv run --frozen pytest tests/architectural/test_charter_kind_vocabulary_single_authority.py -q
uv run python -m scripts.docs.check_docs_freshness --ci
```

## Definition of Done

- Docs and changelog updated, gates recorded green with their counts, no unrelated regeneration in the diff.
