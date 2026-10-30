---
work_package_id: WP01
title: One reader answers what git holds for a Mission's meta.json
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-007
- NFR-001
- NFR-002
- C-003
planning_base_branch: issue-6673-upgrade-tracked-meta-identity
merge_target_branch: issue-6673-upgrade-tracked-meta-identity
branch_strategy: Planning artifacts for this mission were generated on issue-6673-upgrade-tracked-meta-identity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6673-upgrade-tracked-meta-identity unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-issue-6673-upgrade-tracked-meta-identity-01M66YQ9
base_commit: d1c0d3d5c3b980b5039edc51b9cf96a1b706f00a
created_at: '2026-10-30T17:58:12.900497+00:00'
subtasks:
- T001
- T002
- T003
phase: Phase 1 - The owned read of the tracked meta.json
history:
- at: '2026-10-30T17:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/
create_intent:
- tests/specify_cli/upgrade/test_read_tracked_meta_6673.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/mission_metadata.py
- src/specify_cli/upgrade/feature_meta.py
- tests/specify_cli/upgrade/test_read_tracked_meta_6673.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6673'
---

# Work Package Prompt: WP01 – One reader answers what git holds for a Mission's `meta.json`

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: pi

---

## ⚠️ IMPORTANT: Review Feedback

- Check `review_ref` in the event log (`spec-kitty agent tasks status`). Address every item and record it with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

- `specify_cli.mission_metadata` gains the single read of the metadata git holds for a Mission whose working-tree `meta.json` is missing: `TrackedMeta` (a frozen dataclass) and `read_tracked_meta(feature_dir)`.
- The reader distinguishes the answers the seams need, and never conflates them:
  - `meta=<dict>` — git holds a parseable `meta.json` for this path (`HEAD`'s blob — the content `git checkout -- <path>` would restore).
  - `meta=None, unavailable=False` — git holds nothing for this path: the pre-identity Mission case (#6673 notes) and any non-git checkout. Callers keep today's repair.
  - `meta=None, unavailable=True` — git knows the path (the index or `HEAD` has it) but the content cannot be produced, or is not a JSON object. Callers must refuse; **never** mint an identity. `index_only=True` marks the sub-case where the only copy is staged and never committed, so the refusal text can say so instead of claiming git holds nothing.
- `specify_cli.upgrade.feature_meta.build_baseline_feature_meta` seeds `existing_meta` from the tracked copy when the caller has no on-disk metadata, and gives a *present* copy its tracked `mission_id` back when that copy has lost it, so a Mission's `mission_id`, `created_at`, `target_branch` and `mission_type` survive a rebuild of a deleted `meta.json`.
- No behaviour change for a Mission whose `meta.json` is present and carries its identity, or whose folder git does not track a `meta.json` for.

## Context & Constraints

- The defect: `spec-kitty upgrade` reads `meta.json` from the working tree only. If the file is tracked but absent (an accidental `rm`, a sparse checkout), the `2.0.6` sweep writes a baseline built from the directory name (no `mission_id`) and the `3.2.0a4` normalization mints a fresh ULID into it. Working tree identity silently diverges from history's.
- **Read-only.** This WP adds a reader and seeds a builder. It writes no file and does not touch the write seams (WP02 owns those). `mission_metadata.write_meta` stays the only writer (C-002).
- **`kernel.git` is the only path owner (C-003).** Use `run_git`, `blob_at` and `is_tracked` from `kernel.git`. Do not build a `git ls-files`/`ls-tree`/`status` argv, and do not split git output (the `tests/architectural/test_git_path_listing_owner.py` gate has an empty allowlist).
- **Do not import `specify_cli.context.mission_resolver` at module level.** It imports `mission_metadata.load_meta`, so that would be a circular import. If you need `is_kitty_specs_residue` or a git prefix helper, keep the local import deferred (the module already does this for `mission_write_lock`), or use the plain `kernel.git` calls below.
- **Path resolution.** `run_git(feature_dir, "rev-parse", "--show-prefix")` returns the checkout-relative prefix **with a trailing newline** (`b'kitty-specs/x/\n'`; `b'\n'` at the root). Decode and `.strip()` it, then `blob_at(feature_dir, "HEAD", prefix + "meta.json")`. `--full-tree` semantics are why the prefix is needed. **If you skip the strip, `blob_at` silently returns `None` and every case degrades to a refusal** — the unit test in T003 must catch that. Outside a work tree, `rev-parse` fails: that is "nothing tracked", not an error.
- **Unborn `HEAD`.** `blob_at(..., "HEAD", ...)` raises `GitCommandError` (`fatal: Not a valid object name HEAD`) on a repository with no commit. Probe first: `run_git(feature_dir, "rev-parse", "--verify", "--quiet", "HEAD", check=False)`; a non-zero exit means unborn, so `HEAD` contributes nothing and the index decides.
- **Parsing.** Parse the blob with the kernel's malformed authority, `kernel.meta_decode.decode_meta(raw, on_malformed="raise")` (already imported in `mission_metadata` as `decode_meta`); `MetaDecodeError` is the `unavailable=True` branch. Do not add a second `json.loads` call site for `meta.json` content.
- **No new warnings on healthy projects (NFR-003).** The reader is called only when a caller has no on-disk metadata, so nothing runs for a normal project.
- Keep the module's existing docstring style; this module is the documented single owner of `meta.json` reads and writes, so the new function's docstring must say it is the one answer to "what does git hold for this file".

## Branch Strategy

- **Strategy**: Planning artifacts were generated on `main`; completed changes must merge back into `main` unless the human explicitly redirects the landing branch.
- **Planning base branch**: `main`
- **Merge target branch**: `main`
- Execution worktrees are allocated per computed lane from `lanes.json`; never hand-build a workspace path.

```bash
spec-kitty agent action implement WP01 --agent python-pedro --mission issue-6673-upgrade-tracked-meta-identity-01M66YQ9
```

## Subtasks

### T001 — Add the read of the tracked `meta.json`

- In `src/specify_cli/mission_metadata.py`, next to the other readers (`load_meta`, `load_meta_fail_closed` is in `core/paths.py`, do not move it), add:

  ```python
  @dataclass(frozen=True)
  class TrackedMeta:
      """What git holds for a Mission's meta.json when the working tree has lost it (#6673)."""
      meta: dict[str, Any] | None
      unavailable: bool
      index_only: bool = False
  ```

  and `read_tracked_meta(feature_dir: Path) -> TrackedMeta`.
- Algorithm (keep it in one function, ~30 lines, no helpers unless a branch needs its own docstring):
  1. `rev-parse --show-prefix` from `feature_dir`; `GitCommandError`/non-zero → `TrackedMeta(None, unavailable=False)` (not a git work tree: nothing is tracked). **Do not swallow a timeout**: re-raise when `exc.timed_out` (the `probe_tracked_mission_paths` policy, NFR-002).
  2. Probe `HEAD` with `rev-parse --verify --quiet HEAD` (`check=False`). If `HEAD` is valid, `blob_at(feature_dir, "HEAD", prefix.strip() + META_FILENAME)`:
     - bytes → parse with `decode_meta`; a `MetaDecodeError` → `TrackedMeta(None, unavailable=True)`; a parsed mapping → `TrackedMeta(meta, unavailable=False)`.
     - `None` → `HEAD` does not track the path; fall through to step 3.
  3. `is_tracked(feature_dir, META_FILENAME)` (index copy, what `git checkout --` would restore). `True` → `TrackedMeta(None, unavailable=True, index_only=True)` (git holds the file only in the index); `False` → `TrackedMeta(None, unavailable=False)`.
  4. Any `GitCommandError` raised while git *does* know something (steps 2–3, after the work-tree probe succeeded) → `TrackedMeta(None, unavailable=True)`; a timeout is re-raised. Never swallow a failure into "nothing tracked" (NFR-002).
- Document the three answers and the invariant in the docstring: "a Mission whose tracked `meta.json` is absent on disk is never given a fresh identity; it is rebuilt from this content or refused."
- Do not add a timeout parameter or a cache: one call per Mission folder, only when the file is absent from disk (NFR-001).

### T002 — Seed `build_baseline_feature_meta` from the tracked copy

- In `src/specify_cli/upgrade/feature_meta.py::build_baseline_feature_meta`, before the residue check's result is used for a dict:
  - **only when the working-tree `meta.json` is absent** (`not (feature_dir / META_FILENAME).exists()`), set `existing_meta = read_tracked_meta(feature_dir).meta`. Gating on the file's absence matters: `load_feature_meta` returns `None` for a *present but corrupt* file too, and silently replacing a file the operator can see with git's copy is not this mission's contract (the sweep already warns about the corrupt copy).
  - when the file **is** present, parses, and has no non-empty `mission_id`, while the tracked copy has one, take only that value back: `existing_meta["mission_id"] = tracked.meta["mission_id"]`. Never copy any other field over a present copy (an uncommitted baseline written over a real identity is exactly the damage #6673 describes, and this is the recovery).
  - leave the residue branch first (a residue folder is not a Mission and must keep returning `existing_meta` unchanged, #6627/#6669);
  - an `unavailable` tracked copy must not be turned into a baseline: return `existing_meta` (i.e. `None` for the absent case) so the caller writes nothing. Add one sentence to the docstring naming the #6673 case and why `None` is the honest answer there.
- Import `META_FILENAME` from `mission_metadata` rather than re-spelling `"meta.json"` in the new branches.
- Update the module docstring's list of what stays upgrade-specific, if the new import changes it.
- Both callers of this builder (`_feature_requires_repair` and `_repair_feature_meta` in the frozen `m_2_0_6_consistency_sweep.py`) are unchanged: this WP must not edit a shipped migration module.

### T003 — Unit tests: HEAD copy, index-only copy, corrupt copy, unborn HEAD, nothing tracked

- New file `tests/specify_cli/upgrade/test_read_tracked_meta_6673.py`, `pytestmark = [pytest.mark.unit, pytest.mark.git_repo]`, using `tmp_path` and real `git init` (see `tests/integration/migration/test_upgrade_residue_with_mission_files_6669.py` for the scratch-repo helper style; keep this file's helper local and small).
- Cover, one test each, with a same-fixture positive control where the assertion is an absence:
  1. **HEAD copy**: committed `meta.json` (commit a known literal id, the `_REAL_ID` style of the #6669 test), file deleted from disk → `meta["mission_id"]` equals the committed id, `unavailable is False`. Positive control: the same fixture with the file restored returns the same id (proves the reader can see the content it claims).
  2. **Index-only copy** (staged, never committed): `git add` a mission `meta.json` in a repo whose `HEAD` has one commit that does not contain it, delete the file → `unavailable is True`, `index_only is True`, `meta is None`. Positive control: commit it and the same read returns the mapping with `index_only is False`.
  3. **Corrupt committed copy**: commit `{not json`, delete → `unavailable is True`, `meta is None`, `index_only is False`.
  4. **Unborn HEAD**: `git init`, stage a mission `meta.json`, delete it → `unavailable is True` (git knows the path, `HEAD` has no identity) and no exception escapes.
  5. **Nothing tracked**: mission folder with `spec.md` only, committed → `TrackedMeta(None, unavailable=False)`; and a folder outside any git repository → the same.
  6. **Nested path**: the mission lives at `kitty-specs/x` while the git root is two levels up (or under a subdirectory of the repo) → the reader still returns the tracked mapping (proves the prefix handling **and the newline strip**; assert the mapping, not just `unavailable is False`).
  7. **Builder seeding**: `build_baseline_feature_meta` on the HEAD-copy fixture (file absent) returns a mapping whose `mission_id` is the tracked one and whose blank fields are filled; on the corrupt fixture it returns `None`; on the nothing-tracked fixture it returns a baseline without `mission_id` (today's behaviour, positive control for the two refusals).
  8. **Lost identity in a present copy**: a working-tree `meta.json` that parses but has no `mission_id` (or an empty one) while the tracked copy has one → the builder returns the tracked `mission_id` and leaves the other working-tree fields alone; a present copy that already has an id is untouched (positive control).
- Keep every assertion factual (compare to the id read back from git), never to a hard-coded ULID literal that could pass vacuously.

## Test Strategy

```bash
uv run pytest tests/specify_cli/upgrade/test_read_tracked_meta_6673.py -q
uv run pytest tests/specify_cli/upgrade/test_residue_safe_successors_6669.py tests/specify_cli/upgrade/test_residue_successor_plumbing_6669.py -q
uv run pytest tests/architectural/test_git_path_listing_owner.py -q
```

The first command must fail (at least the HEAD-copy and builder-seeding cases) before T001/T002 land, and pass after.

## Definition of Done

- The three commands above are green (the first was red before the change).
- `git diff` touches only the three owned files.
- No shipped migration module is modified.
- The new function's docstring states the invariant and the three answers; no TODO, no `# type: ignore`, no broad `except Exception`.

## Risks & Reviewer Guidance

- **Vacuous refusal test**: a test asserting `unavailable is True` must also prove the reader can return content on the same fixture (the positive control above), or it proves nothing.
- **Silent absence**: any `except GitCommandError: return TrackedMeta(None, False)` after the work-tree probe is a defect — it re-enables the mint. Reviewers: grep the new function for each `except`.
- **Circular import**: importing `mission_resolver` at module level here breaks `import specify_cli`, because `mission_resolver` imports `mission_metadata`.
