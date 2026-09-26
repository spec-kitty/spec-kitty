---
work_package_id: WP01
title: Red-first terminus harness
dependencies: []
requirement_refs:
- FR-001
planning_base_branch: fix/terminus-integrity-followups
merge_target_branch: fix/terminus-integrity-followups
branch_strategy: Planning artifacts for this mission were generated on fix/terminus-integrity-followups. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/terminus-integrity-followups unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-terminus-integrity-followups-01M393QR
base_commit: b5cb3a21e95381cc200c488b32f61c1e118d94a6
created_at: '2026-09-24T07:58:33.887234+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Parallel fan (file-isolated)
history:
- at: '2026-09-24T07:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: debugger-debbie
authoritative_surface: tests/terminus/
create_intent: []
execution_mode: code_change
owned_files:
- tests/terminus/conftest.py
- tests/terminus/test_repro_4945.py
- tests/terminus/test_repro_4977.py
- tests/terminus/test_repro_4981.py
- tests/terminus/test_terminus_reconciliation_property.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Red-first terminus harness

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile in the frontmatter before parsing the
rest of this prompt, and behave according to its guidance.

- **Profile**: `debugger-debbie`
- **Role**: `implementer`
- **Agent/tool**: `claude`

State which initialization/boundaries/directives you applied, then continue.

---

## Markdown Formatting
Wrap HTML/XML tags in backticks. Use language identifiers in fenced code blocks.

## Objectives & Success Criteria

Extend the mock-free real-CLI `tests/terminus/` harness so the WS1 (#5013) squash-content invariant
has a **red-first, squash-sound** reproduction BEFORE any fix lands. This is the ATDD foundation for
the mission (charter C-011). Success:

- A new `blob_present_at(...)` conftest helper lets repros assert **tree/blob presence** on the
  target — the only squash-sound observable (post-plan F4/renata: the existing `patch_ids_in_window`
  observable is vacuously green under squash).
- Default-squash variants of #4945/#4977/#4981 are RED at HEAD (the current squash path ships the
  removed file at exit 0) and will go GREEN only when WP03/WP05 land the content axis.
- A clean-squash positive param proves the axis will not false-fail a legitimate squash (NFR-003).
- The dirty variants pin the **FAIL cause** (unattributable-content signal / target rolled back to
  base), not mere file absence (post-plan renata: absence is trivially true on any abort).

**Read first**: `work/epic-5001-research/followup-architect.md` (§Red-first test plan), the mission
`contracts/invariants.md` (INV-1), and the existing `tests/terminus/conftest.py` +
`tests/terminus/test_repro_4977.py`. Run tests with
`PWHEADLESS=1 <repo>/.venv/bin/python -m pytest tests/terminus/... -o addopts="" -q` — never bare
`spec-kitty` (PATH points at a sibling checkout).

## Subtasks

### T001 — conftest helpers
- Add `blob_present_at(repo, ref: str, path: str) -> bool` to `tests/terminus/conftest.py`: returns
  True iff `git rev-parse <ref>:<path>` (or `git cat-file -e`) succeeds. Deterministic, subprocess,
  no mocking.
- Extend `plant_canceled_commit(...)` to **return the planted repo-relative path** (e.g.
  `src/pkg/<wp>_removed.py`) so a repro can assert its presence/absence. Keep existing callers green
  (return-value addition is backward compatible; update in-repo callers if they unpack).

### T002 — default-squash variant of #4977
- In `tests/terminus/test_repro_4977.py`, add a test that runs the SAME carrier-lane-smuggles-canceled-code
  scenario but with the **default** `spec-kitty merge` (NO `--strategy merge`).
- Mark `@pytest.mark.xfail(strict=True, reason="#5013: default squash skips the content axis; ships the canceled file at exit 0 until WP03/WP05 land the blob-attribution axis")`.
- Assert (the RED expectation the fix will flip): after the merge, `blob_present_at(target, planted_path)`
  is **False** AND the merge exited non-zero AND the target tip == pre-merge base (rolled back). Pin the
  FAIL cause: assert the CLI stderr/among the reconciliation output names the unattributable content or a
  reconciliation FAIL — not just absence.

### T003 — default-squash variants of #4945 and #4981
- Same pattern in `test_repro_4945.py` (re-letter ships removed WP) and `test_repro_4981.py`
  (teardown-without-projection carrier), each a default-squash variant, `xfail(strict)` with a specific
  reason, blob-presence + FAIL-cause observable.

### T004 — clean-squash positive param (no false-fail)
- In `tests/terminus/test_terminus_reconciliation_property.py`, add a `clean_squash` parametrization
  (mirroring the existing `clean_merge`) that runs a legitimate default squash where all approved work is
  present and nothing is excluded, asserting exit 0 and every approved file present. This is NOT xfail —
  it must pass today (a clean squash already passes) and must KEEP passing after the fix (guards against a
  "refuse-everything" fix). Hard-couple it: name it so the dirty variants' review references it.

### T005 — verify + record the RED baseline
- Confirm at HEAD that `test_repro_{4970,4982,4985,4991,4997}.py` and
  `test_terminus_reconciliation_property.py::...no_excluded_commit_reachable[squash]` are all
  `xfail(strict)` and RED (xfailed, 0 xpassed). Record the exact command + counts in the PR-notes scratch
  (`work/epic-5001-research/wp01-red-baseline.md`). Do NOT modify those files (they are removed-at-integration
  by the orchestrator).

## Definition of Done
- `blob_present_at` + `plant_canceled_commit` path-return in conftest; existing terminus tests still pass.
- 3 new default-squash `xfail(strict)` variants (RED now) + 1 clean-squash positive param (GREEN now).
- Each dirty variant pins the FAIL cause, not mere absence.
- RED baseline recorded. `ruff`/`mypy` clean on touched files.
- **Do NOT remove any xfail marker** — markers come off at integration when the fixes land.

## Risks / reviewer guidance
- Reviewer: confirm the dirty variants are RED for the RIGHT reason (run them; they must xfail because the
  file SHIPS, not because of an unrelated error) and that the clean-squash positive would catch a
  refuse-everything fix. Confirm mock-free (no subprocess patching).
- This WP writes only tests; no `src/` edits.
