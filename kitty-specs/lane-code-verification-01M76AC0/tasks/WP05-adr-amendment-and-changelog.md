---
work_package_id: WP05
title: ADR amendment and changelog
dependencies:
- WP04
- WP06
requirement_refs:
- C-004
- C-005
- C-001
- NFR-003
planning_base_branch: fix/7547-lane-code-verification
merge_target_branch: fix/7547-lane-code-verification
branch_strategy: Planning artifacts for this mission were generated on fix/7547-lane-code-verification. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7547-lane-code-verification unless the human explicitly redirects the landing branch.
subtasks:
- T019
- T020
phase: Phase 4 - Close-out
history:
- at: '2026-11-12T05:35:56Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: scribe-sally
authoritative_surface: docs/
create_intent:
- docs/changelog/unreleased/7554.fixed.md
execution_mode: planning_artifact
model: ''
owned_files:
- docs/adr/3.x/2026-08-13-6-gate-outcomes-carry-severity-operator-strategy-decides-effect.md
- docs/changelog/unreleased/7554.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – ADR amendment and changelog

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `scribe-sally`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Then load `spec-kitty charter context --action implement`; read `CLAUDE.md`, the charter's
"Writing, Communication & Diagramming Doctrine", and `docs/changelog/unreleased/README.md`.

---

## ⚠️ IMPORTANT: Review Feedback

- Check `review_ref` via `spec-kitty agent tasks status --mission lane-code-verification-01M76AC0`.

## Review Feedback

*[Filled from the status event log when this WP returns from review.]*

---

## Objectives & Success Criteria

1. ADR `docs/adr/3.x/2026-08-13-6-gate-outcomes-carry-severity-operator-strategy-decides-effect.md`
   gains an **Amendment (2026-11-12)** recording the operator ruling (decision
   `01M7733YYK1615ERKAY41C2M7C`): the pre-review gate's `foreign_tree` outcome is a
   **provenance refusal** — code `EVIDENCE_TREE_MISMATCH`, exit 1, regardless of
   `review.fail_on_pre_review_regression`, bypassable with `--force` (recorded as
   `force_bypassed` + `bypassed_refusal`). It is distinct from pack-trust failures (which
   stay non-bypassable `BLOCKING`). Carve-out from the "gate evaluation faults never refuse
   `move-task`" rule: only a **proven** foreign tree refuses; probe faults, timeouts and
   unprobe-able projects are `unverified` and proceed. Cite #7554/#7547 and the Mission.
   Update the ADR's frontmatter `updated:`/status line conventions as the file already does
   (it was "amended in place" before — follow that pattern).
2. `docs/changelog/unreleased/7554.fixed.md`, one entry in the house style:

```markdown
- **Lane test runs prove they test the lane's own code** (#7554, #7547). **Before:** a test run or `spec-kitty` call inside a lane worktree loaded the repository root checkout's source through its editable install, so a review could pass on unfixed code. **After:** `spec-kitty implement` and the implement/review prompts give each lane a test invocation and report whether it loads the lane's code (`verified`, `foreign` or `unverified`); the pre-review gate runs through the same invocation, records the evidence tree with its verdict, and refuses a lane whose environment loads code from elsewhere with `EVIDENCE_TREE_MISMATCH` (bypass with `--force`, which is recorded).
```

   Adjust wording to what actually shipped (read WP02/WP04 diffs first). Plain language, no
   internal module names in the changelog.

## Context & Constraints

- `docs/` pages carry frontmatter and an `updated:` date per the docs-freshness styleguide;
  changelog fragments are exempt (README).
- Do not edit `docs/changelog/CHANGELOG.md`.

## Branch Strategy

- **Planning base branch**: `fix/7547-lane-code-verification` · **Merge target branch**: `fix/7547-lane-code-verification`

```bash
spec-kitty agent action implement WP05 --agent claude --mission lane-code-verification-01M76AC0
```

## Subtasks & Detailed Guidance

### Subtask T019 – ADR amendment
- Read the whole ADR; add the amendment section after the existing "Amendment note
  (2026-09-27)"; add the new outcome to the severity table if the table lists gate outcomes.

### Subtask T020 – Changelog fragment
- As above; validate the name pattern against the README.

## Test Strategy

```bash
uv run --frozen python -m pytest tests/architectural/test_no_legacy_terminology.py -q
uv run --frozen python -m pytest tests/docs -q -k "frontmatter or changelog or adr" 2>/dev/null || true   # run whatever docs checks exist; record
```

## Review Guidance

- The amendment states the ruling, the bypass, and the carve-out precisely; nothing claims a
  stronger guarantee than shipped (the skip flag still skips everything).

## Activity Log

- 2026-11-12T05:35:56Z – system – Prompt generated via /spec-kitty.tasks
