---
work_package_id: WP01
title: Red-first engine contract and the collision-population split
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- SC-001
- SC-002
- SC-003
- SC-004
- SC-005
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
- T008
phase: Phase 1 - Fix
history:
- at: '2026-10-30T17:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/audit/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/audit/engine.py
- src/specify_cli/status/identity_audit.py
- tests/audit/test_engine_keeps_its_mission_rule.py
- tests/audit/test_audit_cli.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Red-first engine contract and the collision-population split

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in
the frontmatter, and behave according to its guidance before parsing the rest of
this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best
match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log
  (`spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress**: record each addressed item with
  `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Review Feedback

*None yet — this is the first implementation round.*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

---

## Objectives & Success Criteria

`spec-kitty doctor mission-state --audit` (engine: `src/specify_cli/audit/engine.py`)
must stop reporting `DUPLICATE_PREFIX` and `AMBIGUOUS_SELECTOR` between a healthy
Mission and a `kitty-specs/` folder that Mission selection, `doctor identity` and
`doctor mission-type` all treat as residue. It must keep reporting both codes for
two real Missions that share a prefix, keep reporting `IDENTITY_MISSING` on a
folder the engine's own `is_mission_dir` rule still counts as a Mission, and keep
`--fail-on error` exiting 1 on that folder.

Success criteria (from [spec.md](../spec.md)):
SC-001 (fake collision gone), SC-002 (real collisions kept), SC-003 (exit codes),
SC-004 (mission test selection green).

## Context & Constraints

Read these before editing:

- [spec.md](../spec.md) — FR-001…FR-006, NFR-001…NFR-003, C-001, C-002.
- [research.md](../research.md) — D-1…D-6 are binding decisions.
- [plan.md](../plan.md) — IC-01 and IC-02 describe exactly this work.
- `.kittify/charter/charter.md` — the charter wins over anything else here.

Ground rules:

- **Two populations, one code path.** The engine keeps
  `audit_repo(options.repo_root)` (the default, non-residue-aware walk) for the
  per-mission identity findings and for `DUPLICATE_MISSION_ID`. A second,
  residue-aware population (`audit_repo(options.repo_root, residue_aware=True)`)
  feeds **only** `find_duplicate_prefixes(repo_root, residue_aware=True)` and
  `find_ambiguous_selectors(selectable_states)`.
- **No new predicate and no new public surface.** `residue_aware` already exists
  on both helpers (`src/specify_cli/status/identity_audit.py`) and
  `find_ambiguous_selectors` already skips `state == "residue"` rows. Do not
  copy `is_selectable_mission_dir` logic into the engine.
- **Do not narrow `IDENTITY_MISSING`.** A committed `spec.md`-only folder keeps
  its `IDENTITY_MISSING` (error) finding — that is the #5875 contract and what
  keeps `--fail-on error` meaningful. Only the collision codes move.
- **Rebuild groups, never post-filter members.** If a residue folder joins a
  three-member prefix group, the two real Missions must still be reported
  against each other.
- **A pre-identity Mission still collides.** A folder with a tracked
  `meta.json` and no `mission_id` is selectable, so it participates in
  collisions. The filter is the residue rule, never "has a `mission_id`".
- **Read-only.** The engine writes nothing, spawns no non-git process, and keeps
  raising `GitCommandError` on a broken git index.
- Keep the comment block at the top of `run_audit()` truthful: update it to say
  which population each report uses.

## Branch Strategy

- **Strategy**: single-branch mission. Work happens on `kitty/mission-audit-collision-selectable-missions-only-01M66YHT`; the merge target is `main`.
- **Planning base branch**: `kitty/mission-audit-collision-selectable-missions-only-01M66YHT`
- **Merge target branch**: `main` (the operator merges; the agent never does)

> These fields are populated automatically by `spec-kitty agent mission
> finalize-tasks`. Do NOT change them manually unless you are certain the branch
> topology has changed.

## Subtasks & Detailed Guidance

### Subtask T001 – Rewrite the engine contract test around one shared fixture family

- **Purpose**: Turn the corrected contract into executable, non-vacuous tests
  and replace the #5875 pin that currently asserts the wrong collision
  behaviour.
- **Steps**:
  1. Keep the file `tests/audit/test_engine_keeps_its_mission_rule.py` (its
     name still describes the contract) and rewrite its module docstring to the
     corrected rule: the engine keeps its own Mission rule for identity
     findings, but judges collisions on the selectable population.
  2. Build one pair of fixture helpers used by every test: a git repo initialiser
     (`git init`, user config, commit) and a "make a real Mission" helper that
     writes `meta.json` with `mission_id`/`mission_slug`/`mission_number`.
  3. Pin **the defect direction** on the #6757 fixture — committed
     `001-real` (real `meta.json`) beside committed `001-tracked-spec-only`
     (only `spec.md`):
     - `001-real` has **no** findings at all;
     - `001-tracked-spec-only` has exactly `IDENTITY_MISSING`
       (`("IDENTITY_MISSING", "error", "meta.json", "meta.json absent")`).
  4. Pin **the positive control on the same fixture**: in the same test (or in a
     sibling test built by the same helper) make both folders real Missions and
     assert both codes appear on both folders with their existing detail text
     (`prefix '001' shared with: …`, `handle '001' also matches: …`). An
     absence-only assertion without this control is vacuous.
  5. Pin **a pre-identity Mission still collides**: `081-legacy` (tracked
     `meta.json` with `mission_number` but no `mission_id`) + `081-real` → both
     codes on both.
  6. Pin **the three-member group**: `082-alpha`, `082-beta` (real Missions) and
     `082-leftover` (only `spec.md`). Assert the two Missions carry
     `DUPLICATE_PREFIX` naming **each other** and `082-leftover` carries only
     `IDENTITY_MISSING`. This is the case a post-filter implementation would
     fail.
- **Files**: `tests/audit/test_engine_keeps_its_mission_rule.py`
- **Parallel?**: No (T002 extends the same helpers)
- **Notes**: Use `@pytest.mark.git_repo` for the git fixtures, as the file does
  today. Drive the **public entry point**
  (`run_audit(AuditOptions(repo_root=...))`), not the private helpers.

### Subtask T002 – Non-git-root and pre-identity edge cases

- **Purpose**: Cover the residue rule's non-git fallback and the shape a
  post-filter "has a `mission_id`" shortcut would break.
- **Steps**:
  1. Keep/extend the non-git test: `kitty-specs/002-spec-only` holding only
     `spec.md` next to a real `002-real` on a **non-git** root → `002-real` has
     no collision findings, `002-spec-only` keeps `IDENTITY_MISSING`.
  2. Confirm the existing non-git single-folder test still asserts
     `IDENTITY_MISSING` only (no collision codes).
- **Files**: `tests/audit/test_engine_keeps_its_mission_rule.py`
- **Parallel?**: Yes with T001 only after the helpers exist
- **Notes**: On a non-git root `is_selectable_mission_dir` falls back to
  `meta.json` presence, so a `spec.md`-only folder is residue for collisions
  while `is_mission_dir` (existence rule) still reports `IDENTITY_MISSING`.

### Subtask T003 – Record the red output before the fix

- **Purpose**: Prove the test fails through the pre-existing entry point before
  the production change (DIRECTIVE_034).
- **Steps**:
  1. With the tests from T001/T002 written and `engine.py` untouched, run
     `uv run pytest tests/audit/test_engine_keeps_its_mission_rule.py -q`.
  2. Confirm the failure is the fake-collision assertion on `001-real`, not a
     fixture error, and that the real-collision assertions already pass.
  3. Record the outcome:
     `spec-kitty agent tasks add-history WP01 --note "red: <test name> fails on main — 001-real reported AMBIGUOUS_SELECTOR/DUPLICATE_PREFIX from the spec.md-only neighbour"`
- **Files**: none (evidence only)
- **Notes**: Keep the exact failing assertion names for the PR body.

### Subtask T004 – Two-population split in the engine

- **Purpose**: The fix.
- **Steps**:
  1. In `run_audit()`: keep `identity_states = audit_repo(options.repo_root)` and
     add `selectable_states = audit_repo(options.repo_root, residue_aware=True)`.
  2. Pass the selectable states into `_compute_repo_findings_by_slug()` (add a
     parameter; the function is private, so no public contract changes).
  3. In that function: `prefix_groups = find_duplicate_prefixes(repo_root,
     residue_aware=True)`, `selector_groups = find_ambiguous_selectors(
     selectable_states)`, and leave the `DUPLICATE_MISSION_ID` grouping over
     `identity_states`.
  4. Update the docstrings: the `run_audit()` comment block must state, per
     report, which population it uses; `_compute_repo_findings_by_slug()`'s
     docstring must name the two populations and why.
- **Files**: `src/specify_cli/audit/engine.py`
- **Notes**: Keep the diff tight — no reformatting, no unrelated cleanup, no
  behaviour change to `_merge_checkout_disagreements` or `_build_report`.

### Subtask T005 – Correct the now-false contract prose

- **Purpose**: The population split makes four docstrings in
  `src/specify_cli/status/identity_audit.py` and one inline comment in
  `src/specify_cli/audit/engine.py` state the opposite of what the code now
  does. Correcting them in the same PR keeps one canonical description of the
  rule (C-003, single canonical authority).
- **Steps**:
  1. `identity_audit.py` module docstring: the paragraphs that say only
     `doctor identity` opts in to `residue`, and that the audit engine "keeps
     its own, looser Mission rule … so its IDENTITY_MISSING / DUPLICATE_PREFIX /
     AMBIGUOUS_SELECTOR findings must not disappear", must say: `IDENTITY_MISSING`
     keeps the engine population; the two collision reports use the
     residue-aware population.
  2. `audit_repo()` docstring: "``doctor identity`` only" → name both callers
     and which reports each consumes.
  3. `find_duplicate_prefixes()` docstring: same correction — the default keeps
     `doctor identity`'s pre-#5875 contract for any other caller, and the audit
     engine now passes `residue_aware=True`.
  4. `find_ambiguous_selectors()` docstring: drop the claim that "the audit
     engine's input, and its findings, are unchanged"; say the engine passes the
     residue-aware states.
  5. `engine.py` `run_audit()` inline `#5875 / FR-008` comment: it currently
     lists `DUPLICATE_PREFIX` / `AMBIGUOUS_SELECTOR` among the findings that
     "must stay". Replace it with the two-population statement.
- **Files**: `src/specify_cli/status/identity_audit.py`,
  `src/specify_cli/audit/engine.py`
- **Parallel?**: Yes, after T004 (it describes T004's code)
- **Notes**: Comments and docstrings only — **no** behaviour change in
  `identity_audit.py`, no signature change, no reformatting.

### Subtask T006 – Green run and blast radius

- **Purpose**: Prove the fix and that nothing adjacent regressed.
- **Steps**:
  1. `uv run pytest tests/audit/test_engine_keeps_its_mission_rule.py -q`
  2. `uv run pytest tests/audit/ -q`
  3. `uv run pytest tests/doctor/test_identity_audit.py -q`
  4. `uv run pytest tests/context/test_is_mission_dir.py -q`
  5. `uv run pytest tests/integration/test_colliding_mission_flow.py -q`
  6. `uv run ruff check src/specify_cli/audit/engine.py src/specify_cli/status/identity_audit.py tests/audit/test_engine_keeps_its_mission_rule.py`
  7. `uv run mypy src/specify_cli/audit/engine.py src/specify_cli/status/identity_audit.py`
     (or the repository's configured typecheck invocation)
- **Files**: none
- **Notes**: Do **not** run a full heavy suite (NO_FULL_HEAVY_SUITES_IN_MISSION).
  Record commands and counts for the PR body.

### Subtask T007 – Half-by-half revert proof

- **Purpose**: Prove the tests depend on **each** half of the fix
  (`acceptance-criteria-non-vacuity`, compound-fix rule).
- **Steps**:
  1. Temporarily revert only `find_duplicate_prefixes(..., residue_aware=True)`
     to the default call; run the test file; confirm the duplicate-prefix
     assertion on `001-real` goes red. Restore.
  2. Temporarily revert only `find_ambiguous_selectors(selectable_states)` to
     `find_ambiguous_selectors(identity_states)`; run; confirm the
     selector-ambiguity assertion goes red. Restore.
  3. Leave the working tree exactly as after T006 (`git diff` shows only the
     intended change).
- **Notes**: Record both observations in the WP history for the PR body.

### Subtask T008 – CLI exit-code proof

- **Purpose**: Prove the identity gate is unchanged for the operator.
- **Steps**:
  1. Build the #6757 fixture in a scratch temp git repo.
  2. `spec-kitty doctor mission-state --audit --fail-on error` from that repo →
     exit code 1, and the output names `001-tracked-spec-only`'s
     `IDENTITY_MISSING`, with no collision finding on `001-real`.
  3. On a repository with a single healthy Mission, the same command exits 0
     (the positive control that the gate can be passed).
- **Notes**: `--fail-on teamspace-blocker` is also affected by
  `IDENTITY_MISSING`; verify it still triggers rather than asserting a change.

## Test Strategy

- `uv run pytest tests/audit/test_engine_keeps_its_mission_rule.py -q` — the new
  contract, both directions.
- `uv run pytest tests/audit/ tests/doctor/test_identity_audit.py tests/context/test_is_mission_dir.py tests/integration/test_colliding_mission_flow.py -q`
  — blast radius.
- `uv run ruff check <changed files>` and the configured typecheck on the
  changed module.
- Fixtures are real `git` repositories built in `tmp_path`; no network, no
  shared state.

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Post-filtering a collision group silences a real collision | T001's three-member `082` case; groups are rebuilt by the helper |
| Narrowing `IDENTITY_MISSING` changes the operator gate | T001 keeps the folder's finding; T008 pins the exit code |
| Second walk is slower than the budget | Measured ~0.04 s on 210 missions; the identity-audit performance test stays in the blast radius |
| Accidentally changing `DUPLICATE_MISSION_ID` | Its grouping stays on `identity_states`; no test changes expected there |

## Review Guidance

- Confirm the engine keeps the default walk for identity findings and adds the
  residue-aware population **only** for the two collision codes.
- Confirm T005 left `identity_audit.py` behaviour untouched (docstrings only)
  and that no docstring still claims the engine's collision findings are
  unchanged.
- Confirm no post-filtering of group members and no new predicate.
- Confirm the new tests fail on the pre-fix engine (T003's recorded evidence)
  and that each half of the fix is load-bearing (T007).
- Confirm `tests/audit/test_engine_keeps_its_mission_rule.py` still pins the
  `IDENTITY_MISSING` half of the #5875 contract.
- Confirm the diff is limited to the three owned files.

## Progress & Status

Progress, history and status live in the status event log
(`status.events.jsonl`) — never in this prompt file.

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
