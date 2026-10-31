---
work_package_id: WP02
title: Say what the gate lints, and why
dependencies:
- WP01
requirement_refs:
- FR-007
- FR-008
- NFR-002
- SC-003
planning_base_branch: issue-6724-companion-tactic-neutrality-scope
merge_target_branch: issue-6724-companion-tactic-neutrality-scope
branch_strategy: Planning artifacts for this mission were generated on issue-6724-companion-tactic-neutrality-scope. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6724-companion-tactic-neutrality-scope unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
phase: Phase 2 - Contract text and release notes
history:
- at: '2026-10-30T23:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/charter/activation/synthesizer/write_pipeline.py
- docs/adr/3.x/2026-04-19-6-harness-owned-generated-artifact-charter-handoff.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Say what the gate lints, and why

## ⚡ Do This First: Load Agent Profile

```bash
spec-kitty agent profile show python-pedro
spec-kitty charter context --action implement --include agent-profile:python-pedro
```

## Objective

Leave the rule where the next reader will look for it: in the gate's own contract
text, in the governed ADR that owns the harness handoff, and in the changelog a
user reads.

## Subtasks

### T006 — Gate contract text (FR-007)

`src/charter/activation/neutrality/lint.py`'s module docstring and
`write_pipeline._is_generic_scoped`'s docstring are the gate's contract. State, in
each place that needs it and nowhere else (no duplication):

- scope is the artifact's audience: a "generic-scoped" artifact addresses every
  project, so a language term in it is an unstated assumption;
- a companion tactic (`how-we-apply-<directive-id>`) has no cross-project
  audience — it is the project's own application note — so its scope is the
  project's observed/declared languages;
- when no scope is known the artifact stays generic, which keeps the
  unconfigured-project refusal.

Add the two new worked examples to `_is_generic_scoped`'s existing example block
(known-scope companion → language-scoped; unknown-scope companion → generic).
Keep the prose in the artifact's own voice; do not restate the changelog.

### T007 — ADR amendment (FR-008)

`docs/adr/3.x/2026-04-19-6-harness-owned-generated-artifact-charter-handoff.md`
says `spec-kitty` owns "validation, neutrality gating, provenance, staging, and
promotion" without saying what the gate judges. Append an amendment section in
the file's existing style (`## Amendment 2026-10-30: what the neutrality gate
judges`): the scope-not-vocabulary rule, the companion case, the
unconfigured-project case, and a pointer to `#6724`. Do not rewrite earlier
sections.

### T008 — Changelog entry (FR-008)

`docs/changelog/CHANGELOG.md`, under `[Unreleased]`, in the section style already
used there: a bold impact-first lead with `(#6724)`, then **Before** and
**After**, under 1,200 characters. Lead with what an operator sees:
`charter synthesize` no longer refuses a companion tactic that names the
project's own test runner. Mention that an unconfigured project is still refused,
because that is the half a reader will ask about.

### T009 — Docs freshness and terminology guard

```bash
uv run python -m scripts.docs.check_docs_freshness --ci
uv run pytest tests/architectural/test_no_legacy_terminology.py -q
```

Regenerate only the index surface this diff touches if the freshness check asks
for it (`scripts.docs.docs_index --write`); the shared install cache is not ours to
rebuild concurrently (MISSION-BRIEF §Shared machine state). Record the exact
commands and results.

## Definition of Done

- A maintainer reading only `_is_generic_scoped` can state why a companion is
  skipped and why the unconfigured case is not.
- The ADR carries the amendment, dated, naming #6724.
- The changelog entry is impact-first, has before/after, and is under 1,200
  characters.
- Freshness check reports `errors=0`; the terminology guard passes.
