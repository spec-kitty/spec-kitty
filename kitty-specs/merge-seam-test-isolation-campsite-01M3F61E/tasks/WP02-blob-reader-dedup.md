---
work_package_id: WP02
title: Single raw git blob reader in the merge domain (#5119)
dependencies: []
requirement_refs:
- FR-001
- NFR-006
planning_base_branch: issue-5119-merge-seam-test-isolation
merge_target_branch: issue-5119-merge-seam-test-isolation
branch_strategy: Planning artifacts for this mission were generated on issue-5119-merge-seam-test-isolation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5119-merge-seam-test-isolation unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-merge-seam-test-isolation-campsite-01M3F61E
base_commit: 77feb9f366b8fe89d709401ced87a2bb4c56ac06
created_at: '2026-09-26T16:56:32.313421+00:00'
subtasks:
- T007
- T008
- T009
phase: Phase 1 - Foundations
history:
- at: '2026-09-26T16:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/merge/
create_intent:
- tests/merge/test_single_blob_reader.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/merge/bookkeeping_projection.py
- tests/architectural/tool_artifact_enrolment/inventory.md
- tests/merge/test_single_blob_reader.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Single raw git blob reader in the merge domain (#5119)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro` (read `packs/built-in/agent_profiles/python-pedro.agent.yaml`)
- **Role**: `implementer`
- **Agent/tool**: `claude`

Also read `.kittify/charter/charter.md` (Governing Principles + Quality Standing Orders) before touching code.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

Issue **#5119** (MINOR part — SSOT): the merge domain carries two byte-identical raw git blob readers. Collapse them to ONE.

Done when:

1. `src/specify_cli/merge/bookkeeping_projection.py` no longer defines `_git_show_blob_bytes`; every former caller uses `_read_git_blob_bytes` imported from `specify_cli.merge.git_probes`.
2. The now-unused `import subprocess` in `bookkeeping_projection.py` is gone (only if it has no other use — verify).
3. Exactly ONE function in `src/specify_cli/merge/` shells `git show <ref>:<path>` to read raw blob bytes — pinned by a new guard test (`tests/merge/test_single_blob_reader.py`) that fails if a second copy appears.
4. Semantics unchanged: any non-zero `git show` exit → `None`; otherwise `stdout` bytes (spec Edge Case "Blob reader semantics"; no path-absent vs git-error split).
5. The line-keyed census pin `tests/architectural/test_destructive_op_routing.py:172` (`git_probes.py:236:reset_hard`) is untouched and still green (this WP does not edit `git_probes.py` at all).
6. `tests/merge`, the projection seam tests and the architectural enrolment inventory test are green; ruff, ruff format, mypy clean.

Requirement refs: **FR-001**, SC-002, NFR-006.

- **No manual global-state mutation in new/changed tests** (the census gate is not in this lane until consolidation): no hand writes to `os.environ` / cwd / `sys.path` / `sys.modules` / `sys.argv` — use `monkeypatch.*` / `contextlib.chdir` / `mock.patch.*`. Verify zero sites for your changed test files: `.venv/bin/python kitty-specs/merge-seam-test-isolation-campsite-01M3F61E/research/global_state_scan_prototype.py | grep -E '<your test files>'` (expect no output) — record it in the Activity Log.

## Context & Constraints

- Spec: `kitty-specs/merge-seam-test-isolation-campsite-01M3F61E/spec.md` (FR-001, User Story 1 scenario 5, Edge Cases).
- Research: `kitty-specs/merge-seam-test-isolation-campsite-01M3F61E/research.md` **R1** (all file:line facts below come from there, re-verify before editing).
- Plan: `plan.md` → Implementation Concern Map row "Blob-reader dedup".
- **Ownership boundary**: `src/specify_cli/merge/git_probes.py` is owned by **WP04**. Do NOT edit it here — not even the stale docstring at `git_probes.py:~609` that mentions the bookkeeping copy. That docstring fix is folded into WP04's T018 (the resolver subtask). Record this hand-off in the Activity Log.
- Import direction already runs `bookkeeping_projection → git_probes` (`bookkeeping_projection.py:28` imports `GitProbeError, driver_replay_expected_bytes`). Extending that import creates no new edge and no cycle.
- Do NOT touch `src/specify_cli/merge/__init__.py` (the `__init__` change rule forces a version bump).
- Ratchet mission `01M3EW3Z` owns `tests/architectural/test_destructive_op_routing.py` and `_destructive_op_census.py` — never edit them (C-002).

## Branch Strategy

- **Strategy**: lane-based execution from `lanes.json` (computed by `finalize-tasks`).
- **Planning base branch**: `issue-5119-merge-seam-test-isolation`
- **Merge target branch**: `issue-5119-merge-seam-test-isolation`
- Prepare the workspace ONLY via `.venv/bin/spec-kitty agent action implement WP02 --agent claude` (never `git worktree add` by hand; never the `spec-kitty` on PATH — it resolves to another checkout). Work inside the lane worktree the command prints.

## Subtasks & Detailed Guidance

### Subtask T007 – Delete the duplicate reader; import and use the canonical one

- **Purpose**: FR-001 — one authority for raw blob reads so the two copies cannot diverge (e.g. one later distinguishing path-absent from git-error).
- **Facts (verify first)**:
  - Duplicate: `src/specify_cli/merge/bookkeeping_projection.py:484-499` `_git_show_blob_bytes(main_repo, ref, path)`.
  - Canonical: `src/specify_cli/merge/git_probes.py:605-622` `_read_git_blob_bytes(repo_root, ref, path)`.
  - Bodies are byte-identical: `subprocess.run(["git", "show", f"{ref}:{path}"], cwd=…, capture_output=True, check=False)` → `None` on non-zero, else `stdout`. Only the first parameter name and the docstring differ. Diff them yourself before deleting (`sed -n` both ranges) and STOP + report if the bodies differ in any behavior.
  - Callers of the duplicate: `bookkeeping_projection.py:537`, `:555` (inside `project_post_checkpoint_commits_to_target`) and `:597-602` (`_projected_path_content_matches`).
- **Steps**:
  1. Extend the existing `from specify_cli.merge.git_probes import (...)` at `bookkeeping_projection.py:28` with `_read_git_blob_bytes`. It is a private name imported across modules of the same package — acceptable (same domain, the import edge already exists); do NOT rename it public in this WP (git_probes is WP04's file).
  2. Replace every `_git_show_blob_bytes(` call with `_read_git_blob_bytes(`, keeping positional argument order `(repo, ref, path)`. Check whether any call passes keyword `main_repo=` — if so switch to positional or `repo_root=`.
  3. Delete the `_git_show_blob_bytes` definition.
  4. Remove `import subprocess` (L16) only if `grep -n "subprocess" bookkeeping_projection.py` shows no remaining use.
  5. `grep -rn "_git_show_blob_bytes" src tests` must return nothing afterwards (research found no test references/patches; re-verify — `test_ordering_bake_seam.py` patches the global `subprocess.run`, which still works because the canonical reader also calls `subprocess.run`).
- **Files**: `src/specify_cli/merge/bookkeeping_projection.py`.
- **Parallel?**: No (T008/T009 depend on the final line layout).
- **Notes**: Keep the diff minimal — no unrelated reformatting (ruff format may reflow only what you touched).

### Subtask T008 – Refresh the enrolment inventory's navigation lines

- **Purpose**: Tidiness inside the touched surface (DIRECTIVE_025 boy-scout, strictly inside the WP's file set).
- **Facts**: `tests/architectural/tool_artifact_enrolment/inventory.md:44-48` carries rows locating sinks in `bookkeeping_projection.py` by line (rows for `:177`, `:304`, `:305`, `:311`, `:559`). Its header states rows are compared by the composite `(file, qualname, …)` key and **line numbers are navigation only, never compared**. Removing `import subprocess` (L16) shifts **every** row by −1, and deleting the ~17-line duplicate shifts the rows below it further — refresh **all five** rows (177, 304, 305, 311, 559).
- **Steps**:
  1. After T007, locate each listed sink's new line (`grep -n` the sink expression in `bookkeeping_projection.py`).
  2. Update only the line numbers in all five rows. Do not reorder, re-key or re-word rows.
  3. Run `.venv/bin/python -m pytest tests/architectural/tool_artifact_enrolment -q` (the enrolment inventory test self-asserts both directions; it must stay green — if it goes red, the composite key changed, which means you changed more than intended).
- **Files**: `tests/architectural/tool_artifact_enrolment/inventory.md`.
- **Parallel?**: Yes, once T007's final layout exists.
- **Notes**: If a row does not actually point at `bookkeeping_projection.py`, leave it alone.

### Subtask T009 – Single-definition guard test + blast radius

- **Purpose**: Make "exactly one raw blob reader in the merge domain" a non-vacuous, checked invariant (SC-002), not just a one-off cleanup.
- **Steps**:
  1. Create `tests/merge/test_single_blob_reader.py` (mark `pytestmark = [pytest.mark.fast, pytest.mark.unit]` — pure AST scan, no subprocess; check `pytest.ini` markers).
  2. Implement an AST scan over `src/specify_cli/merge/*.py` that finds every function whose body contains a `subprocess.run`/`subprocess.check_output` call whose first argument is a list literal starting with `"git", "show"` (and an f-string `ref:path` argument). Collect `(rel_path, qualname)`.
  3. Assert the found set == `{("specify_cli/merge/git_probes.py", "_read_git_blob_bytes")}` with a message telling the reader to import the canonical helper instead.
  4. **Non-vacuity**: add a self-mutation test that writes a planted module into `tmp_path` containing a second `git show` blob reader and asserts the scanner (factor it as a function taking a root `Path`) reports it; and a negative control (a `git show --stat` or non-`show` git call is NOT reported — decide and document the exact match rule).
  5. Add a behavior test for the canonical reader's two outcomes using a real temp git repo (mark `git_repo`): committed file → bytes; missing path → `None`. Put it in the same file only if the markers stay honest (a git-repo test is not `fast`/`unit`); otherwise use separate marked test functions with per-function markers.
- **Files**: `tests/merge/test_single_blob_reader.py` (new).
- **Parallel?**: No.
- **Notes**: Keep complexity ≤15; type-annotate the scanner (mypy strict-clean).

- **Tracer**: **Tracer append**: add dated 1–3 sentence entries, as they occur, to the mission's `tracer-tooling-friction.md` / `tracer-approach.md` / `tracer-design-decisions.md` (`kitty-specs/merge-seam-test-isolation-campsite-01M3F61E/`); do not commit them from the lane — the orchestrator commits them in the lifecycle trail.

## Test Strategy

Run from the lane worktree with `.venv/bin/python` (never bare `uv run`):

```bash
.venv/bin/python -m pytest tests/merge/test_single_blob_reader.py -q
.venv/bin/python -m pytest tests/merge -q -n auto --dist loadfile
.venv/bin/python -m pytest tests/architectural/test_destructive_op_routing.py tests/architectural/tool_artifact_enrolment -q
grep -rln "bookkeeping_projection" tests --include="*.py" | xargs .venv/bin/python -m pytest -q
make test-fast
uv run --frozen ruff check src/specify_cli/merge/bookkeeping_projection.py tests/merge/test_single_blob_reader.py
uv run --frozen ruff format --check src/specify_cli/merge/bookkeeping_projection.py tests/merge/test_single_blob_reader.py
.venv/bin/python -m mypy src/specify_cli/merge/bookkeeping_projection.py tests/merge/test_single_blob_reader.py
```

Record commands + pass/fail counts in the Activity Log. Classify any red per CLAUDE.md "baseline-red gotcha" (re-run on the base before calling it yours).

## Risks & Mitigations

- **Hidden behavior difference between the two copies** → diff the bodies first; stop and report if not identical.
- **Census pin drift** → this WP never edits `git_probes.py`; `test_destructive_op_routing.py` must stay green unchanged.
- **Scanner vacuity** (guard matches nothing and passes) → the explicit "found set == {canonical}" equality plus the planted self-mutation test.
- **Out-of-map temptation** (fixing the git_probes docstring) → do NOT; it is WP04's T018.

## Review Guidance

- Confirm `_git_show_blob_bytes` is gone repo-wide and callers pass the same arguments.
- Confirm no file outside `owned_files` changed (`git diff --stat` against the lane base).
- Confirm the guard test fails on the planted second reader and passes on the real tree.
- Confirm ruff, ruff format and **mypy** were run and are clean, and `make test-fast` + `tests/merge` counts are in the Activity Log.
- Confirm `test_destructive_op_routing.py` untouched and green.
- **Tracer append** evidence: dated 1–3 sentence entries in the mission's `tracer-tooling-friction.md` / `tracer-approach.md` / `tracer-design-decisions.md` for anything non-obvious (the orchestrator commits them in the lifecycle trail).

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)

**Initial entry**:

- 2026-09-26T16:40:00Z – system – Prompt created. Note: git_probes.py docstring (L~609) fix is owned by WP04/T018, not this WP.
- 2026-09-26T17:25:03Z – claude (python-pedro) – T007: diffed both bodies (byte-identical, only the first-param name differed) before deleting; extended the `git_probes` import at `bookkeeping_projection.py:28` with `_read_git_blob_bytes`; replaced all 6 positional call sites; deleted `_git_show_blob_bytes` (L484-499) and the now-unused `import subprocess` (L16); `grep -rn "_git_show_blob_bytes" src tests` returns only the WP04-owned stale docstring at `git_probes.py:609` (left untouched, hand-off recorded). T008: refreshed all 5 `tool_artifact_enrolment/inventory.md` navigation lines (177→218, 304→358, 305→359, 311→365, 559→545); `pytest tests/architectural/tool_artifact_enrolment -q` → 1 passed. T009: added `tests/merge/test_single_blob_reader.py` (pure-AST scanner, `fast`/`unit`) asserting the found set == `{("specify_cli/merge/git_probes.py", "_read_git_blob_bytes")}`; discovered a pre-existing THIRD `git show <stage>:<path>` reader (`merge/conflict_resolver.py::_read_conflict_sides`, index-stage `:2:`/`:3:` reads, decodes to text) that the naive "any colon in an f-string" rule over-matched — tightened the match rule to require an f-string shaped exactly `FormattedValue, Constant(':'), FormattedValue` (two interpolations sandwiching a bare colon), which correctly excludes it; added that shape as a third negative control. Added self-mutation (planted second reader), negative controls (`git show --stat`, non-`show`, stage-index colon-shape), and two `integration`/`git_repo`-marked behavior tests (real temp repo: committed file → bytes, missing path → `None`) — deliberately NOT `fast`/`unit` since they shell real `git`. Global-state scan: `python kitty-specs/.../research/global_state_scan_prototype.py | grep test_single_blob_reader.py` → no output (zero manual `os.environ`/cwd/`sys.*` mutation sites). **Unplanned but necessary fix**: extending the `git_probes` import (T007) made two comparisons in `_projected_path_content_matches` (`target_bytes == coord_bytes` at the old L?, now L589) resolve as `Any == Any` under the repo's `specify_cli.*` `follow_imports="skip"` mypy override (cross-module private-name imports resolve to `Any` for narrow-file `--strict` checks) — a genuine NEW `no-any-return` finding introduced by my own diff (confirmed via before/after mypy on `git show HEAD:...`). Fixed in-file (no pyproject.toml edit) by adding explicit `bytes | None` annotations to `coord_bytes`/`target_bytes`/`base_bytes`/`pre_squash_target_bytes`, which pins the concrete type past the `Any`-returning import. One PRE-EXISTING mypy finding remains at the (now-shifted) `target_bytes == expected_bytes` line — confirmed present on `git show HEAD:src/specify_cli/merge/bookkeeping_projection.py` before any of my edits (same `driver_replay_expected_bytes` Any-return shape) — left alone as baseline-red, not mine to fix. Also found: my T007 body edit changed the AST content-hash of `project_post_checkpoint_commits_to_target` (its two `git show` call sites are inside that function), causing `tests/architectural/test_no_dead_symbols.py::test_no_public_symbol_in_all_is_unimported` to red on a stale `SymbolKey` body_hash allowlist entry (confirmed green on `git show HEAD:...`, red on my diff). Re-keyed that one entry using the gate's own `resolve_symbol_key`/`key_tier` resolver (never hand-guessed), following the exact "RE-KEYED" precedent already in that file for `lane_integrated_by_tree_or_ancestry`; commented with mission/issue rationale. **Tests run**: `pytest tests/merge/test_single_blob_reader.py -q` → 5 passed. `pytest tests/architectural/tool_artifact_enrolment -q` → 1 passed. `pytest tests/architectural/test_destructive_op_routing.py tests/architectural/tool_artifact_enrolment -q` → 13 passed. `pytest tests/architectural/test_no_dead_symbols.py -q` → 34 passed (0 red after re-key). `pytest tests/merge -q -n auto --dist loadfile` → 981 passed, 1 xfailed, 1 failed (`test_profile_charter_e2e.py::test_local_support_declarations_end_to_end` — "Refusing charter write from linked git worktree"; reproduced identically with my diff stashed out, so pre-existing/environment baseline-red, not mine). `pytest tests/unit tests/status tests/cli tests/specify_cli/runtime tests/architectural/test_no_retired_subsystems.py -m "(fast or unit) and ..."` (test-fast-equivalent, run via `.venv/bin/python -m pytest` per lane instructions rather than `make test-fast`'s `uv run`) → 2045 passed, 5 skipped, 3 failed (`tests/cli/commands/test_charter_json_error_contract.py`, same linked-worktree charter-write refusal, reproduced identically with the diff stashed out — pre-existing). `ruff check` / `ruff format --check` on all touched files → clean. `mypy --strict` on `bookkeeping_projection.py` + `test_single_blob_reader.py` → 1 pre-existing baseline-red finding only (confirmed via before/after on `git show HEAD:...`), 0 new. `git diff --stat -- src/specify_cli/merge/git_probes.py` → empty (file untouched; the `test_destructive_op_routing.py:172` `git_probes.py:236:reset_hard` pin is unaffected). Files touched beyond the WP's `owned_files`: `tests/architectural/test_no_dead_symbols.py` (one `SymbolKey` re-key, required by T007's body edit, resolver-recomputed per house precedent — flagged here for reviewer visibility since it is not in `owned_files`).

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `.venv/bin/spec-kitty agent tasks move-task WP02 --to <status>` to change WP status.
