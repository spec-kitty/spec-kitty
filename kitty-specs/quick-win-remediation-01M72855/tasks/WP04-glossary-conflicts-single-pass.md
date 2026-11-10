---
work_package_id: WP04
title: Glossary conflict listing in one pass
dependencies: []
requirement_refs:
- FR-014
- FR-015
- FR-016
- NFR-001
- NFR-002
- NFR-004
- C-006
- SC-006
planning_base_branch: fix/quick-win-remediation
merge_target_branch: fix/quick-win-remediation
branch_strategy: Planning artifacts for this mission were generated on fix/quick-win-remediation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/quick-win-remediation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-quick-win-remediation-01M72855
base_commit: c331acbc4576566c703551feb86643bf827a6279
created_at: '2026-11-10T08:30:16.495388+00:00'
subtasks:
- T017
- T018
- T019
phase: Phase 1 - Independent fixes
history:
- at: '2026-11-10T08:19:33Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/glossary.py
create_intent:
- docs/changelog/unreleased/7463-glossary-conflicts-linear.fixed.md
execution_mode: code_change
model: glm-5.3
owned_files:
- src/specify_cli/cli/commands/glossary.py
- tests/agent/cli/commands/test_glossary.py
- docs/changelog/unreleased/7463-glossary-conflicts-linear.fixed.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Glossary conflict listing in one pass

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `opencode`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history <WPID> --note "..."` (stored in the status event log).

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

**#7463.** `_extract_conflicts_from_events` (`src/specify_cli/cli/commands/glossary.py:183`) rebuilds `existing_ids = {c["conflict_id"] for c in conflict_events}` inside the second `for event in events` loop, once per resolved event (`:273`). The cost is O(resolved × conflicts): measured 500 → 5.8 ms, 1000 → 27 ms, 2000 → 101 ms, 4000 → 553 ms (≈×4 per doubling). The fix builds the set once and **adds each appended id** to it.

Done means:
- Output is identical for every input (same records, same order, same de-duplication) (FR-015).
- Three resolved-only events with the same `conflict_id` still yield exactly one conflict.
- n requested + n resolved-only events with distinct ids yield 2n conflicts in event order.
- Before/after timings at n = 500, 1000, 2000, 4000 recorded in the WP history for the PR body (NFR-001). **No wall-clock assertion in any test** (C-006, operator decision `01M72874ECYSTEJVVRZNCD2M7E`).
- Fragment written; ruff / format / mypy clean.

**Red-first exception (documented in spec NFR-003):** the deterministic tests below pass on the base too (the defect is speed, not output). That is expected and recorded; the de-duplication test is the control that catches the "hoist without add" mistake.

## Context & Constraints

- Spec: `kitty-specs/quick-win-remediation-01M72855/spec.md` (User Story 7, FR-014, NFR-001, C-006). Plan: `plan.md` IC-08. Research: `research.md` "#7463".
- **Trap**: a bare hoist (set built once, never updated) changes behaviour. Today a repeated resolved event for the same id is de-duplicated *because* the first one is appended to `conflict_events` and the next rebuild sees it. Without `existing_ids.add(cid)`, 3 identical resolved events would produce 3 records. The issue's own suggested fix includes the `add` — keep it.
- Do not change filters, ordering, record shape, or the existing `# noqa: C901` on the function; no new helper is needed.
- Only production caller: the `conflicts` command (`glossary.py:~412`). Tests: `tests/agent/cli/commands/test_glossary.py` class `TestExtractConflicts` (`:892` onward; module `pytestmark = pytest.mark.fast`; the helper is imported lazily per test — follow that pattern), e.g. `test_immediately_resolved_without_requested` (`:1008`) shows the resolved-only event shape.
- No `make test-fast`, no `make test-full`, no bare directories.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: populated by finalize-tasks
- **Merge target branch**: populated by finalize-tasks

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.
> Execution worktrees are allocated per computed lane from `lanes.json`. Start with:
> `spec-kitty agent action implement WP04 --agent opencode --mission quick-win-remediation-01M72855`

## Subtasks & Detailed Guidance

### Subtask T017 – Characterisation + scale tests

- **Purpose**: pin output so the refactor provably changes nothing but cost.
- **Steps** (in `TestExtractConflicts`):
  1. `test_repeated_resolved_only_events_yield_one_conflict`: three `EVT_GLOSSARY_CLARIFICATION_RESOLVED` events with the same `conflict_id` and no Requested event → exactly one record, `status == "resolved"`.
  2. `test_two_distinct_resolved_only_ids_yield_two_conflicts_in_order`: same-fixture positive control (proves the probe can see more than one).
  3. `test_scale_requested_plus_resolved_only_counts`: build the issue's synthetic log — n Requested events (ids `req-0…req-{n-1}`, shaped like the existing Requested tests) plus n resolved-only events with distinct ids `res-0…` — for n = 2000; assert `len(result) == 2 * n` and the ids appear in event order. No timing assertion.
  4. Run on the base: all green (expected — record "T017 characterisation green on base, as designed" with `add-history`). Commit: `test(glossary): pin conflict extraction de-duplication and scale counts (#7463)`.
- **Files**: `tests/agent/cli/commands/test_glossary.py`.

### Subtask T018 – Hoist + add

- **Steps**:
  1. Before the second `for event in events:` loop (`:267`), add `existing_ids = {c["conflict_id"] for c in conflict_events}`.
  2. Delete the in-loop rebuild at `:273`.
  3. Immediately after `conflict_events.append({...})` in that loop, add `existing_ids.add(cid)`.
  4. Update the comment above the loop if it mentions per-event scanning (it does not today; leave it otherwise).
  5. Run T017 + the whole `TestExtractConflicts` class → green. Mutation check (do it, then revert): delete the `add` line and confirm `test_repeated_resolved_only_events_yield_one_conflict` goes red; record that in the WP history.
  6. Commit: `perf(glossary): build the known conflict-id set once (#7463)`.
- **Files**: `src/specify_cli/cli/commands/glossary.py`.

### Subtask T019 – Timings, fragment, validation

- **Steps**:
  1. Measure before/after with a throwaway script **in your scratchpad, not in the repo** (it calls the existing private function on a synthetic log; this is measurement, not prototyping the fix): n = 500, 1000, 2000, 4000, best of 3 with `time.perf_counter`. Record both tables in `spec-kitty agent tasks add-history WP04 --note "..."` so the PR author can paste them. Expect roughly linear growth after the fix.
  2. `docs/changelog/unreleased/7463-glossary-conflicts-linear.fixed.md`: **Before:** `spec-kitty glossary conflicts` slowed quadratically on long glossary event logs. **After:** one pass; output unchanged (#7463).
  3. `uv run --frozen python -m scripts.docs.check_changelog_style` and `uv run --frozen python -m scripts.docs.check_spelling --pass unreleased`.
  4. Tracer: one `approach` entry (deterministic tests + recorded timings instead of a perf test) via `spec-kitty agent tracer-append --mission quick-win-remediation-01M72855 --category approach --actor "<agent:model:profile>" --entry "**[YYYY-MM-DD][implement] ...**"`.
  5. Commit: `docs(changelog): fragment for #7463`.

## Test Strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/agent/cli/commands/test_glossary.py -q -p no:cacheprovider
ruff check src/specify_cli/cli/commands/glossary.py tests/agent/cli/commands/test_glossary.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/cli/commands/glossary.py tests/agent/cli/commands/test_glossary.py
uv run --frozen mypy src/specify_cli/cli/commands/glossary.py
```

No architectural gate names this module.

## Risks & Mitigations

- Hoist-without-add → caught by T017 test 1 and the T018 mutation check.
- Flaky perf assertions → none written; timings live in the PR body.

## Review Guidance

- Diff in `glossary.py` is exactly: one set built before the loop, one in-loop line removed, one `add` added.
- The de-duplication test exists and goes red when the `add` is removed (implementer's recorded mutation check; reviewer may repeat it).
- Timing table present in the WP history.

## Progress & Status

Progress, history, and status all live in the status event log
(`status.events.jsonl`) — never in this prompt file. Do **not** hand-edit a
history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history <WPID> --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task <WPID> --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
