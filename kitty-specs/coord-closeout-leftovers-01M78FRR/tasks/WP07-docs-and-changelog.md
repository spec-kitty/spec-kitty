---
work_package_id: WP07
title: Reference docs and changelog
dependencies:
- WP02
- WP03
- WP04
- WP05
- WP06
requirement_refs:
- C-007
planning_base_branch: fix/7598-coord-closeout-leftovers
merge_target_branch: fix/7598-coord-closeout-leftovers
branch_strategy: Planning artifacts for this mission were generated on fix/7598-coord-closeout-leftovers. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7598-coord-closeout-leftovers unless the human explicitly redirects the landing branch.
subtasks:
- T025
- T026
phase: Phase 3 - Polish
history:
- at: '2026-11-12T18:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- docs/api/cli-commands.md
- docs/changelog/unreleased/**
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP07 – Reference docs and changelog

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter before reading further.

- **Profile**: `scribe-sally` · **Role**: `implementer` · **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` via `spec-kitty agent tasks status`; address all feedback; record progress with `add-history`.

---

## Objectives & Success Criteria

The operator reference and the changelog describe exactly what WP02-WP06 shipped. Audience:
an operator of the CLI (software-engineer persona). Code is the source of truth: read the merged
lane code, not the plan, before writing.

Done when:
- `docs/api/cli-commands.md`: the `COORD_LATE_PROJECTION_REFUSED` row (`:127`) says a resume with a verified landing judges commits after the verified coordination tip (else since the merge began); new rows for `SQUASH_PROJECTION_NOT_LANDED`, `RECLAIM_NOT_ARCHIVED`, `RECLAIM_NO_COORDINATION`, `RECLAIM_UNABSORBED`; the `archive reclaim` command documented where `archive create` is; the page's `updated:` date bumped.
- One changelog fragment per delivered issue in `docs/changelog/unreleased/` following `docs/changelog/unreleased/README.md` (`<id>.<section>.md`); never edit `CHANGELOG.md`.
- `uv run python -m scripts.docs.check_changelog_style` and `uv run python -m scripts.docs.check_spelling --pass unreleased` report 0 errors.

## Context & Constraints

- C-007 terminology: Mission, not feature; name the sense of "primary" and "merge".
- Divio: `cli-commands.md` is Reference; keep the table shape.
- `pytest tests/architectural/test_no_legacy_terminology.py` before pushing prose.

## Branch Strategy

Planning base / merge target: `fix/7598-coord-closeout-leftovers`.

```bash
spec-kitty agent action implement WP07 --agent claude --mission coord-closeout-leftovers-01M78FRR
```

## Subtasks & Detailed Guidance

### Subtask T025 – `docs/api/cli-commands.md` rows

- **Steps**: read each code's message and exit code in the shipped source (`grep -rn "<CODE>" src/`), then write the rows: meaning, exit code, remedy (copy the remedy semantics the code prints). Add the `archive reclaim` command entry with one example.

### Subtask T026 – Changelog fragments

- **Steps**: read `docs/changelog/unreleased/README.md`; write fragments for #7491, #4041, #5867, #7599, #7600 (Fixed / Added sections as the README defines), one or two sentences each, operator-facing; run the two checkers.

## Test Strategy

```bash
uv run python -m scripts.docs.check_changelog_style
uv run python -m scripts.docs.check_spelling --pass unreleased
.venv/bin/python -m pytest -q tests/architectural/test_no_legacy_terminology.py
```

## Review Guidance

- Every row matches the shipped text and exit code.

## Progress & Status

Event log only.
