---
work_package_id: WP02
title: One llms.txt, and the record
dependencies:
- WP01
requirement_refs:
- FR-007
- FR-008
- C-001
- C-003
planning_base_branch: issue-6938-docsite-cutover
merge_target_branch: issue-6938-docsite-cutover
branch_strategy: Planning artifacts for this mission were generated on issue-6938-docsite-cutover. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6938-docsite-cutover unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
- T010
- T011
phase: Phase 2 - Record
history:
- at: '2026-11-11T16:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: docs/
create_intent:
- docs/changelog/unreleased/6938-docsite-cutover.changed.md
execution_mode: code_change
model: ''
owned_files:
- docs/llms.txt
- docs/docfx.json
- tests/docs/test_docs_seo.py
- tests/docs/test_dockitty_contract.py
- scripts/docs/_dockitty_contract.py
- docs/development/reference/ci-gate-mechanics.md
- docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md
- docs/changelog/unreleased/6938-docsite-cutover.changed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – One llms.txt, and the record

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Record progress with `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Objectives & Success Criteria

- `docs/llms.txt` is deleted; no live test, script or config reads it (FR-007, SC-004).
- ADR 2026-10-31-1 gains an amendment only (C-003) recording the cutover, the canary evidence, the smoketest, the deletion and exactly what a revert restores (FR-008).
- A changelog fragment passes `check_changelog_style` and `check_spelling --pass unreleased`.
- The CI reference page describes the deploy as it now is.

## Context & Constraints

- Plan table "docs/llms.txt references" in `plan.md` lists each reference and its action.
- Immutable history (ADR bodies, `docs/plans`, `docs/reports`, `docs/changelog` other than the new fragment, `docs/archive`, `kitty-specs/`, `kitty-ops/`) stays untouched.
- C-001: keep every DocFX source; `docs/docfx.json` only loses its `llms.txt` resource entry.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: issue-6938-docsite-cutover
- **Merge target branch**: issue-6938-docsite-cutover

## Subtasks & Detailed Guidance

### Subtask T007 – Delete `docs/llms.txt`

- Red first: replace `test_the_hand_written_llms_txt_still_carries_the_stance` in `tests/docs/test_dockitty_contract.py` with a test that `docs/llms.txt` does not exist (the generated route is the one source); see it fail; then delete the file.
- `tests/docs/test_docs_seo.py::test_static_seo_files_exist`: drop `llms.txt`.
- `docs/docfx.json`: drop the `llms.txt` resource entry.
- `scripts/docs/_dockitty_contract.py` `LLMS_STANCE` comment: no hand copy remains.
- Keep `scripts/docs/bulk_ref_rewrite.py` (its sets name a historical moves-file path and a generic basename filter).

### Subtask T008 – CI reference page

- `docs/development/reference/ci-gate-mechanics.md` "Where the docs site deploys from": the shared doc-kitty build, the deploy, the smoketest, the rollback. "The GitHub Pages docsite build needs `PYTHONPATH`": still true for the smoketest and the shared build's Python steps; drop the DocFX-render wording.

### Subtask T009 – ADR amendment

- Append `## Amendment 2026-11-11 (cutover)` to `docs/adr/4.x/2026-10-31-1-the-docsite-is-built-with-doc-kitty.md` after the existing 2026-11-11 amendment. Do not edit the body or earlier amendments. Record: the cutover (D-13 step 3, D-11 now true), the canary evidence (run 43027580608 and the #6938 comment link), the smoketest (#2361; no alert issue), the retired canary, the deletion of `docs/llms.txt` (D-9), the token permissions, and exactly what a revert restores.

### Subtask T010 – Changelog fragment

- `docs/changelog/unreleased/6938-docsite-cutover.changed.md`, one entry in the README's style.

### Subtask T011 – Verify

```bash
uv run --frozen pytest tests/docs -n 4 --dist loadfile --tb=line -q
uv run --frozen python -m scripts.docs.check_changelog_style
uv run --frozen python -m scripts.docs.check_spelling --pass unreleased
uv run --frozen ruff check scripts/docs/_dockitty_contract.py tests/docs/test_docs_seo.py tests/docs/test_dockitty_contract.py
uv run --frozen mypy --strict -m scripts.docs._dockitty_contract
```

## Risks & Mitigations

- A docs gate that walks `docs/` could still expect `llms.txt`: run the whole `tests/docs` subsystem.

## Review Guidance

- Confirm the ADR change is an appended amendment only, and the revert statement is complete.
- Confirm no immutable-history file changed.

## Progress & Status

Progress lives in `status.events.jsonl`. Use `spec-kitty agent tasks add-history`, `move-task` and `status`.
