---
work_package_id: WP03
title: Planning-artifact staging uses Git's clean view
dependencies: []
requirement_refs:
- FR-004
- FR-005
- NFR-001
- C-004
- C-005
planning_base_branch: kitty/upgrade-windows-drift
merge_target_branch: kitty/upgrade-windows-drift
branch_strategy: Planning artifacts for this mission were generated on kitty/upgrade-windows-drift. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into kitty/upgrade-windows-drift unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-upgrade-windows-drift-01M40959
base_commit: 54f8a479c18e0ed78f1385a664fff1f54a13b936
created_at: '2026-10-03T07:56:47.628545+00:00'
subtasks:
- T010
- T011
- T012
- T013
- T014
phase: Phase 2 - Planning artifacts
history:
- at: '2026-10-03T07:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/cli/commands/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5-5-high
owned_files:
- src/specify_cli/cli/commands/implement_cores.py
- tests/specify_cli/cli/commands/test_implement_cores.py
- tests/specify_cli/cli/commands/test_meta_bypass_diagnosability.py
- tests/specify_cli/cli/commands/test_implement_coord_idempotency.py
- tests/architectural/test_trio_seam_only.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Planning-artifact staging uses Git's clean view

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load `implementer-ivan` (role `implementer`) and behave according to its guidance before parsing the rest of this prompt.

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission upgrade-windows-drift-01M40959`) and the Activity Log below. Address every feedback item before completing.

---

## Objectives & Success Criteria

Closes **#5576**.

1. On a checkout where Git converts line endings (for example `.gitattributes` `* text=auto eol=crlf`, or `core.autocrlf=true` on Windows) and `git status --porcelain` is empty, `resolve_planning_artifact_staging(..., auto_commit=False)` returns an empty `files_to_commit`. `spec-kitty implement WP## --no-auto-commit` does not refuse, and the auto-commit path does not create an empty commit (FR-004, SC-003).
2. A planning file whose text really changed is still staged, alone, including when it is saved with CRLF line endings (FR-005, C-004, SC-004).
3. The decision uses the object id Git would store (`git hash-object`, clean filter applied) compared with the object id at the ref. Any git error keeps the file as changed (fail closed).

## Context & Constraints

- Read: `spec.md` (US3, FR-004, FR-005, C-004), `plan.md` (IC-03), `research.md` (D3), `data-model.md` (staging table), `contracts/planning-artifact-staging.md`.
- Anchors in `src/specify_cli/cli/commands/implement_cores.py`:
  - `GitPort` Protocol ~69-83 (`status_entries`, `show_blob`);
  - `_SubprocessGitPort` ~86-107, the only place in the module that shells out;
  - `DEFAULT_GIT_PORT` ~110;
  - `_files_changed_vs_ref` ~471-495, raw compare at ~493;
  - `_files_changed_vs_precondition_ref` ~498-542;
  - `resolve_planning_artifact_staging` ~566-656.
- `src/specify_cli/cli/commands/implement.py`:
  - imports `_files_changed_vs_ref` at ~80 but never uses it (grep `src/` and `tests/` to confirm; nothing patches `implement._files_changed_vs_ref`);
  - the refusal is at ~432 via `_ensure_planning_artifacts_committed_git` ~873-889.
- `tests/architectural/test_trio_seam_only.py` ~492-501 pins the token `source . read_bytes ( )` inside `_files_changed_vs_ref`. If you remove that read, re-pin the gate to the new shape. Do not delete the gate; keep its intent, which is a single working-tree read seam.
- **Do not change `show_blob`**. `_committed_meta_mapping` and `_is_self_write_only_diff` need raw blob bytes.
- `_is_self_write_only_diff` is out of scope. It decodes JSON, and parses WP frontmatter with `read_text` universal newlines, so CRLF does not affect it.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: `kitty/upgrade-windows-drift`
- **Merge target branch**: `kitty/upgrade-windows-drift`

Run `spec-kitty agent action implement WP03 --agent cursor --mission upgrade-windows-drift-01M40959` and work only in the workspace it prints.

## Subtasks & Detailed Guidance

### Subtask T010 – Red-first: Git-clean CRLF checkout yields an empty plan

- **Home**: `tests/specify_cli/cli/commands/test_implement_coord_idempotency.py`. It is a real-git harness: `_git` ~38, `_seed_coord_mission_real` ~44, `_claim` ~94.
- **Test** `test_crlf_clean_checkout_yields_an_empty_planning_artifact_staging_plan`:
  1. Seed a real repository and mission with the existing helpers.
  2. Commit `.gitattributes` containing `* text=auto eol=crlf`.
  3. Make the working tree CRLF the way a Windows clone would: unlink the planning files, then `git checkout -- .`.
  4. First `git add -A && git commit` everything the harness wrote at claim time (for example `status.events.jsonl`), then re-check out. Assert `git status --porcelain == ""` and that at least one planning file's bytes contain `b"\r\n"`. This checks the precondition.
  5. Call `resolve_planning_artifact_staging(repo_root, mission_dir, coord_branch, extra_file_paths, auto_commit=False)` with the same arguments the harness's claim path uses, and assert `plan.files_to_commit == []`.
- Run it red (today `files_to_commit` lists the CRLF files) and record that in the Activity Log.

### Subtask T011 – Ratchet: a real CRLF edit is still staged

- **Test** `test_crlf_worktree_with_a_real_token_change_is_still_staged`, with the same setup as T010:
  - write `plan.md` as `b"# Plan\r\nREVISED\r\n"`, or change one token in its existing CRLF content;
  - assert `files_to_commit == [f"kitty-specs/{slug}/plan.md"]`, so only that path is staged.
- It must be green before and after the change.

### Subtask T012 – GitPort object-id compare

- **Steps**:
  1. Add a Protocol method to `GitPort`, for example `changed_vs_ref(self, repo_root: Path, ref: str, repo_rel_paths: Sequence[str]) -> set[str]`. It returns the subset whose clean-filtered working object id differs from the object id at `ref`, or that is absent at `ref`. A batch API keeps the subprocess count constant.
  2. Implement it in `_SubprocessGitPort`:
     - **Working ids**: `git hash-object --stdin-paths`, with the paths on stdin one per line, relative to `repo_root` and run with `cwd=repo_root`. With `--stdin-paths`, Git applies each path's own filters (`.gitattributes`, `core.autocrlf`); do **not** pass `--no-filters`, and do not combine with `--path`. The output is one object id per input line, in order.
     - The caller must pre-filter paths to ones that exist: a single missing file aborts the whole `hash-object` batch. `git hash-object --path X --stdin-paths` is invalid (exit 129, verified on git 2.43).
     - **Ref ids**: `git ls-tree -z --full-tree <ref> -- <paths...>`. Parse the output by path name, because output order is not guaranteed. Parse `<mode> SP <type> SP <oid> TAB <path> NUL` and map path → oid; a path missing from the output is absent at the ref.
     - **Fail closed**: on any non-zero return code, length mismatch or parse error, return the whole input set as changed. Do not raise unless the module's existing error policy for this port says so (check how `status_entries` errors are treated, and keep the claim path's behavior).
     - `--stdin-paths` has no NUL mode, so a path containing a newline or carriage return is classified as changed without being sent.
     - An alternative is `git diff-index --name-only <ref> -- <paths>` in one call. If you choose it, justify the choice in the Activity Log: it compares index or working state, so verify it is CRLF-clean and fails closed.
     - Very long path lists: `ls-tree` paths go on argv. Chunk them (e.g. 500 per call) if needed.
  3. Keep `_SubprocessGitPort` the only shell-out site.
- **Tests** in `tests/specify_cli/cli/commands/test_implement_cores.py`:
  - update `_FakeGitPort` (and the `test_default_git_port_conforms_to_protocol` check) for the new method;
  - add adapter tests against a tiny real repository in `tmp_path`: CRLF-clean → unchanged; real edit → changed; path absent at the ref → changed; bogus ref → all changed (fail closed).

### Subtask T013 – Route `_files_changed_vs_ref` through it

- **Steps**:
  1. `_files_changed_vs_ref`:
     - keep the signature `(repo_root, files, ref, *, git=DEFAULT_GIT_PORT)` and its docstring intent;
     - keep `if not ref: return files`;
     - keep skipping non-existent paths;
     - compute `changed = git.changed_vs_ref(repo_root, ref, existing)`, then return the files in input order that are in `changed`.
  2. Update the existing `TestFilesChangedVsRef` unit tests (~478-491) to the port method. Keep their four behaviors: no ref → all; identical → dropped; differing → kept; missing source → skipped.
  3. Re-pin `tests/architectural/test_trio_seam_only.py` (~493-502). The descriptor resolves `source . read_bytes ( )` live at import, so once the read is removed it becomes unresolvable. Delete that descriptor and add one for the new adapter method's `subprocess . run (` site in `_SubprocessGitPort`. Explain the change in the Activity Log, and run that file alone.
  4. Leave `implement.py` (~75-91) untouched. The `_files_changed_vs_ref` import there is a deliberate `# noqa: F401` shim re-export, not dead code.
  5. Update the second fake port in `tests/specify_cli/cli/commands/test_meta_bypass_diagnosability.py` (~48-57) with the new method, so it stays a complete `GitPort`.
- Keep complexity ≤ 15 and mypy clean.

### Subtask T014 – Entry-point check

- **Purpose**: NFR-001 asks for proof through the product entry point.
- **Steps**:
  - Extend T010 or add a sibling test that drives `_ensure_planning_artifacts_committed_git(...)` in `implement.py` with `auto_commit=False`, using the harness's real repository, or the CLI `implement` path the harness already exercises through `_claim`, if it can run without network or SaaS.
  - Assert it does not raise `typer.Exit(1)` on the Git-clean CRLF checkout, and with auto-commit no new commit is created (`git rev-parse HEAD` is unchanged).
  - If the helper's arguments are awkward, use whatever entry point `_claim` already uses; do not hand-roll a different path.
  - It must be red before T013 and green after.

## Test Strategy

```bash
uv run pytest tests/specify_cli/cli/commands/test_implement_coord_idempotency.py \
  tests/specify_cli/cli/commands/test_implement_cores.py \
  tests/specify_cli/cli/commands/test_precondition_ref_unification.py \
  tests/specify_cli/cli/commands/test_meta_bypass_diagnosability.py -q
uv run pytest tests/architectural/test_trio_seam_only.py -q
make test-fast
uv run --frozen ruff check src/specify_cli/cli/commands/implement_cores.py src/specify_cli/cli/commands/implement.py tests/specify_cli/cli/commands tests/architectural/test_trio_seam_only.py
uv run --frozen ruff format --check --force-exclude <changed files>
uv run --frozen mypy src/specify_cli/cli/commands/implement_cores.py src/specify_cli/cli/commands/implement.py
```

Also run every test file that references `_files_changed_vs_ref` or `GitPort` (`rg -l "_files_changed_vs_ref|GitPort|_FakeGitPort" tests`). Record commands and counts in the Activity Log. Never `make test-full` or the whole `tests/architectural/`.

## Risks & Mitigations

- **Hiding a real edit** (C-004): T011 is the ratchet. On any git failure, fail closed.
- **Filter semantics**: `hash-object --stdin-paths` honors `.gitattributes` per path. A `-text` or binary path compares raw bytes, which is correct.
- **Symlinks / submodules** under `kitty-specs/` are unexpected; fail closed (changed) rather than guess.
- **Windows CI**: use `git` from PATH with `cwd=repo_root`; keep paths POSIX-relative.

## Review Guidance

- The red output of T010/T014 is recorded before the product change.
- `show_blob` is unchanged; there is exactly one shell-out class.
- The trio gate is re-pinned, not deleted, and its intent is preserved.
- mypy and ruff are clean; no new suppressions.

## Activity Log

- 2026-10-03T07:45:00Z – system – Prompt created.
