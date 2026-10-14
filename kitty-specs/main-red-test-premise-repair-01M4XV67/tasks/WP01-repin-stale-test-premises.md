---
work_package_id: WP01
title: 'Re-pin the two stale test premises (#6240, #6238)'
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- NFR-001
- C-001
- C-002
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-6240-main-red-test-premise-repair
merge_target_branch: issue-6240-main-red-test-premise-repair
branch_strategy: Planning artifacts for this mission were generated on issue-6240-main-red-test-premise-repair. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6240-main-red-test-premise-repair unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Restore green
history:
- at: '2026-10-14T18:41:26Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- tests/specify_cli/test_requirement_id_lint.py
- tests/architectural/test_upgrade_recovery_preservation.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Re-pin the two stale test premises (#6240, #6238)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter, and behave according to its guidance before reading the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission main-red-test-premise-repair-01M4XV67`). Address every item before you finish.

## Objectives & Success Criteria

- `tests/specify_cli/test_requirement_id_lint.py` passes in full (5 failures today → 0). Covers FR-001, FR-002, SC-001.
- `tests/upgrade/test_mission_corpus_recovery.py` passes IN FULL (not only the 3 `test_full_corpus_audit_rejects_real_scanner_membership_faults` variants: the other `full=True` tests at about :159 and :350 also consume the fixture), under spec-kitty-events 10.4.6. The same holds for `tests/architectural/test_upgrade_recovery_preservation.py`. Covers FR-003, NFR-001, C-002, SC-002.
- No src/ change (C-001). No new allowlist, tolerance or skip (NFR-001).

## Context & Constraints

- Charter: `.kittify/charter/charter.md` (Standing Order 4: judge the test; red-first). Plan: `kitty-specs/main-red-test-premise-repair-01M4XV67/plan.md`. Research: `research.md` R-1 and R-2.
- Use the repo venv: `.venv/bin/python -m pytest -n0 ...`. Never a bare `uv run` (it re-syncs the venv). If `uv.lock` gets rewritten to artifactory URLs, run `git checkout uv.lock` before you stage.
- Do NOT run `make test-full` or whole `tests/architectural/`. Targeted files only.

## Branch Strategy

- **Strategy**: single_branch. The WP runs in the write checkout (repository root) on `issue-6240-main-red-test-premise-repair`.
- **Planning base branch**: issue-6240-main-red-test-premise-repair
- **Merge target branch**: issue-6240-main-red-test-premise-repair (the PR from it targets `main`)
- Implement command: `spec-kitty agent action implement WP01 --agent claude --mission main-red-test-premise-repair-01M4XV67`

## Subtasks

### T001 – Red-first proof

Before editing, run and record the counts in the WP history (`spec-kitty agent tasks add-history WP01 --note ...`):

```bash
.venv/bin/python -m pytest -n0 -q tests/specify_cli/test_requirement_id_lint.py          # expect 5 failed, 40 passed
.venv/bin/python -m pytest -n0 -q "tests/upgrade/test_mission_corpus_recovery.py::test_full_corpus_audit_rejects_real_scanner_membership_faults"   # expect 3 failed
```

These existing tests ARE the issue-pinned repros. Do not add a `@pytest.mark.regression` copy.

### T002 – Re-pin the well-formedness test (#6240)

Current test, at about `tests/specify_cli/test_requirement_id_lint.py:313-325`:

```python
@pytest.mark.parametrize(("token", "expected"), [("FR-001", True), ("fr-006a", True), ("SC-002b", True), ("FR-006A", False), ("FR-008-mandated", False)])
def test_is_well_formed_declaration(token: str, expected: bool) -> None:
    assert _is_well_formed_declaration(token) is expected
```

The helper is `_is_well_formed_declaration(token: str, mission_type: str) -> bool` (`src/specify_cli/requirement_mapping/lint.py:116`). Re-parametrize over `("token", "mission_type", "expected")`. Pass `"software-dev"` for the 5 existing rows (the public entry point's default). Keep the expected values unchanged.

### T003 – New-branch coverage (c0f455d068)

Add rows for the following. Verify each against the grammar before you assert it, and adjust only if the grammar disagrees, recording why:
- `("DR-001", "research", True)` and `("DR-001", "software-dev", False)`: a research-only kind (DR/AR/QR, `grammar._RESEARCH_KINDS`).
- `("QR-2", "research", True)` (optional, a second kind).
- `("FR-00N", "software-dev", False)` and `("FR-00N", "research", False)`: a template placeholder is never well-formed.
- `("FR-001", "research", True)`: the base kinds stay valid under research.

Use readable `ids=` if the parametrize ids get ambiguous.

### T004 – Sanctioned-correction overlay (#6238)

Root cause (research R-2): `build_recovery_repo(full=True)` (`tests/architectural/test_upgrade_recovery_preservation.py:341`) exports pinned `c0054153b9…`. Its `kitty-specs/079-post-555-release-hardening/status.json` predates the operator-sanctioned re-materialization under events 10.4.6 (commit 2ff2f1deb5; rationale at `tests/architectural/test_archive_root_byte_identical.py:238-249`; set `_OPERATOR_SANCTIONED_CORRECTIONS` at about `:250`). The module already imports that file as `gate`.

**Scope correction (post-tasks review):** 25 of the sanctioned paths exist in the c0054153b9 export, not just 079. They are: 079 status.json (sanctioned in 2ff2f1deb5), the 025 WP01 .md (2d56615a82), and 23 status.json / status.events.jsonl files of 12 missions (the #5579 backfill, 01714f0206). 01714f0206 is an ancestor of 2ff2f1deb5. At 2ff2f1deb5 all 25 carry their final sanctioned bytes. None of them overlaps gate.CYCLIC/OLD_BUNDLE/SPINE/SNAPSHOTS/MOVES/RECEIPT/NEW_BUNDLE.

Steps:
1. Add a module constant pinning where the sanctioned bytes are read from, NOT HEAD (HEAD can legitimately re-edit a sanctioned file, which would silently change the fixture): `SANCTIONED_AT = "<full sha of 2ff2f1deb5>"` (resolve it with `git rev-parse 2ff2f1deb5`), with a comment citing #6061/#6205/#6238.
2. Add a small helper, e.g. `_apply_sanctioned_corrections(repo) -> list[str]`. For each `path in sorted(gate._OPERATOR_SANCTIONED_CORRECTIONS)` that exists in the exported tree, write `git show SANCTIONED_AT:<path>` bytes (use the module's `git(REPO_ROOT, ...)` helper; check that it returns bytes). Skip absent paths and never create them. Return the applied list.
3. In `build_recovery_repo`, after `commit -m "Original historical corpus"`, call it and, if it applied anything, commit separately (`"Operator-sanctioned corrections (#6061, #6205)"`), then `update-ref refs/remotes/origin/main HEAD` (the order is settled: no test asserts origin/main == historical commit; `run_gate` skips sanctioned paths either way).
4. Pin the count so a new sanctioned path cannot change the fixture silently: assert the full-corpus overlay applies exactly 25 paths (an assertion in the helper for `full=True`, or a dedicated focused test in this file). This, with iterating the gate set, enforces C-002/NFR-001.
5. Non-full fixture: confirm whether any of the 25 fall inside its narrower path set. If none do, the overlay applies 0 there and is harmless. Say so in a comment.
6. Campsite (in-file, optional): replace the hard-coded `c0054153b9…` SHA in `build_recovery_repo` with `gate.ORIGINAL` if that constant equals it.
7. If running the whole `tests/upgrade/test_mission_corpus_recovery.py` reveals that the #5579-backfilled files change another full-corpus test's expected findings, STOP and report it to the orchestrator with the diff. Do not adjust expectations silently.

### T005 – Targeted verification

```bash
.venv/bin/python -m pytest -n0 -q tests/specify_cli/test_requirement_id_lint.py
.venv/bin/python -m pytest -n0 -q tests/upgrade/test_mission_corpus_recovery.py
.venv/bin/python -m pytest -n0 -q tests/architectural/test_upgrade_recovery_preservation.py tests/architectural/test_archive_root_byte_identical.py
ruff check <changed files> && uv run --no-sync ruff format --check --force-exclude <changed files>
```

Every test must be green. Record the commands and counts in the WP history. Append any friction to `kitty-specs/main-red-test-premise-repair-01M4XV67/tracer/tooling-friction.md` (tracer files are mission planning artifacts; commit them separately through `spec-kitty spec-commit` or leave them for the orchestrator).

## Definition of Done

- T001–T005 recorded with `spec-kitty agent tasks mark-status T001 ... --status done`.
- Commits: one for #6240 (`test(requirements): ...`), one for #6238 (`test(upgrade): ...`), each ending with the Co-Authored-By/Claude-Session trailers in use for this session.
- Move the WP to for_review.

## Reviewer Guidance

- Confirm red at base and green after, for both tests.
- Confirm the overlay reads from the pinned SANCTIONED_AT commit, asserts its 25-path count, and reads `gate._OPERATOR_SANCTIONED_CORRECTIONS` (no duplicated path list) and adds no tolerance.
- Confirm the research and placeholder rows are real assertions of the grammar, not tautologies.
