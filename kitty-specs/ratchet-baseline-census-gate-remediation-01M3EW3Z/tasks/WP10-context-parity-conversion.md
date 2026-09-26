---
work_package_id: WP10
title: Context parity conversion to an on-disk packs fixture
dependencies: []
requirement_refs:
- C-005
- FR-015
- NFR-002
- NFR-005
- NFR-006
planning_base_branch: claude/spec-kitty-remediation-wfje22
merge_target_branch: claude/spec-kitty-remediation-wfje22
branch_strategy: Planning artifacts for this mission were generated on claude/spec-kitty-remediation-wfje22. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/spec-kitty-remediation-wfje22 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-ratchet-baseline-census-gate-remediation-01M3EW3Z
base_commit: 036eacf346dd4b5ccd08ea16f472bdbc84fc397c
created_at: '2026-09-26T16:06:41.055692+00:00'
subtasks:
- T054
- T055
- T056
- T057
- T058
phase: Phase 3 - Parity remediation
history:
- at: '2026-09-26T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
- at: '2026-09-26T17:00:00Z'
  actor: planner-priti
  action: Folded post-tasks squad findings
agent_profile: python-pedro
authoritative_surface: tests/charter/test_context_bootstrap_markers.py
create_intent:
- tests/charter/test_context_bootstrap_markers.py
execution_mode: code_change
model: ''
owned_files:
- tests/charter/test_context_parity.py
- tests/charter/test_context_bootstrap_markers.py
- tests/charter/test_context_render_seams.py
- tests/charter/test_context_leaf_seams.py
- tests/charter/test_procedures_json_array.py
- src/charter/activation/context_contract.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP10 – Context parity conversion to an on-disk packs fixture

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Then load the action-scoped governance: `spec-kitty charter context --action implement --json`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`) or the Activity Log below.
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

`tests/charter/test_context_parity.py` asserts real behavioural markers. However, it drives them by patching `src/` internals, which is why it co-changed with `src/` on 6 of its 6 post-creation modifications (grounding N3). Convert it to an on-disk project plus a mirrored packs tree, reached through public entry points and the public `SPEC_KITTY_PACKS_ROOT` env knob. Then rename it to `tests/charter/test_context_bootstrap_markers.py` (FR-015).

Done means:

1. `test_context_markers_use_no_src_patch_targets` exists and is GREEN. It was RED on the planning base with **6 `patch(` sites + 2 private calls** (post-plan Debbie HIGH; the plan's earlier figure of "4 private targets" was wrong).
2. The converted module contains **zero** `patch`, `patch.object` or `monkeypatch.setattr` targets under any first-party `src/` package, and **zero** imports or calls of `_`-prefixed first-party names. The four behavioural markers still hold:
   - `first_load is True` and `context-state.json` is written;
   - `directive:DIRECTIVE_998` together with `Cause: missing_artifact`;
   - `_LONG_BODY_NEEDLE` is swapped out, and `section:terminology-canon` plus `# Governance payload:` are present;
   - the include, JSON and empty-charter markers are unchanged.
3. There is a control test in which mutating the fixture (a real, non-empty directives mirror) changes the outcome. The miss cause is then no longer `missing_artifact`.
4. The packs mirror is **always copied, never symlinked** (D-OP-10). The test asserts that the resolved built-in pack root is under `tmp_path`, and that no `SPEC_KITTY_PACKS_ROOT` fallback `UserWarning` fires.
5. The old path's references are updated, and the module is formatted. It is not format-excluded.

## Context & Constraints

- Mission `ratchet-baseline-census-gate-remediation-01M3EW3Z`. Read these first:
  - `spec.md` (FR-015 and its Assumptions: defer rather than breach C-005);
  - `plan.md` (the WP10 row, D-OP-5, D-OP-10);
  - `research.md` §F3;
  - `research/postplan-debbie.md` (the WP10 HIGH finding, and the LOW Windows/cache finding);
  - `research/postplan-priti.md` (the WP10 LOW finding on #3251);
  - `research/grounding-2631_2972.md` §N3.
- **Mechanism (prototyped in `research.md` §F3, witnessed by Debbie in both cache orders):**
  - `kernel.paths.get_built_in_pack_root()` (`src/kernel/paths.py:235`) returns `$SPEC_KITTY_PACKS_ROOT/built-in` when that directory exists.
  - Build `<tmp>/packs/built-in` as a **copy** of the real `packs/built-in`, with two changes:
    - `directives/` is an **empty real directory**. This replaces both `built_in_dir` patches and the `resolve_doctrine_root` patch.
    - `agent_profiles/` holds copies of every real profile plus one on-disk `parity-fixture-agent.agent.yaml`, authored as literal YAML in the test. This replaces the private `_activation_aware_profile_map` patch.
  - `_ACTIVATION_AWARE_PROFILE_MAPS` is keyed by `repo_root`, which is a unique `tmp_path`, so the private `_reset_agent_profile_cache()` call is not needed.
  - The copy costs about 0.05 s (513 files, 3.7 MB).
- **C-005.** No `src/` behaviour change. The single `src/` edit is a comment in `src/charter/activation/context_contract.py:68`, and it needs an AST-equality proof (D-OP-3; see T057).
- **Deferral clause.** If the markers cannot be reproduced without patching `src/`, stop. Defer FR-015 per the spec assumption, file a `src/` seam follow-up, and record it in the tracer. **Never re-patch privates** to get green.
- **#3251** (`SPEC_KITTY_PACKS_ROOT` set-but-invalid currently fails open with a `UserWarning`, `paths.py:246-254`). A broken mirror would silently resolve the real catalog, so the positive `missing_artifact` assertion plus the "pack root under `tmp_path`" assertion are both load-bearing.
- `tests/charter/test_context_parity.py` is **not** format-excluded, so the renamed file must pass `ruff format --check`. The referencing files `test_context_render_seams.py` (pyproject L1166) and `test_context_leaf_seams.py` (L1161) **are** excluded: make docstring-only edits there and do not format them.
- Campsite (FR-020): clean S5778/S5779/S8997 findings in the converted module only.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> These fields are populated automatically by `spec-kitty agent mission tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Commit in your lane worktree. Never push and never merge.

## Subtasks & Detailed Guidance

### Subtask T054 – RED-first: `test_context_markers_use_no_src_patch_targets` (commit alone)

- **Purpose**: A behavioural, AST-level acceptance check (Renata MEDIUM, FR-015 AS) that fails for exactly the defect being fixed. It is not a tombstone.
- **Steps**:
  1. In `tests/charter/test_context_parity.py` (still at its old path), add a pure helper `_src_coupling_offenders(source: str) -> list[str]`. It parses the source with `ast` and returns one entry per offender:
     - a `Call` whose callee is `patch`, `mock.patch`, `unittest.mock.patch`, `patch.object` or `monkeypatch.setattr`, where the first argument is a string constant starting with a first-party package prefix (`charter.`, `kernel.`, `specify_cli.`, `runtime.`, `mission_runtime.`, `glossary.`, `doctrine.`). For `patch.object` and `monkeypatch.setattr` with a non-string target, treat it as an offender when the target expression is a first-party module name. `monkeypatch.setenv` and `delenv` are **allowed**, because they are public knobs.
     - an `ImportFrom` from a first-party package that imports a `_`-prefixed name;
     - a `Call` to a `_`-prefixed name that was imported from a first-party package.
     Keep it at complexity ≤ 15 by splitting it into `_patch_offenders` and `_private_import_offenders` helpers.
     Entry format (fixed, so the RED can be checked against an exact list): `"patch:<dotted target>"`, `"private-import:<module>.<name>"`, `"private-call:<name>"`. There is one entry per `ImportFrom` of a `_` name **and** one per call of it; no deduplication.
  2. Add `test_context_markers_use_no_src_patch_targets`:
     - read `Path(__file__)`;
     - assert non-vacuity: at least 6 `def test_` functions, and at least 1 call to `build_charter_context`;
     - assert `_src_coupling_offenders(source) == []`, with a message listing the offenders.
  3. Add a self-mutation test, `test_src_coupling_scan_flags_planted_offenders`. Feed the **same helper** a planted source string that contains `patch("charter.activation.catalog.built_in_dir")`, `monkeypatch.setattr(mod, "x", 1)` with `mod` imported from `charter`, and `from charter.activation.profile_resolution import _reset_agent_profile_cache`, plus the alias case `from unittest import mock as m` followed by `m.patch("charter.x")`. Assert all four are flagged. Also feed it a negative source containing `monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", ...)`, and assert it yields `[]`.
  4. Run the module on the planning base. `test_context_markers_use_no_src_patch_targets` must fail and list exactly these **10 entries** (sorted; duplicates are real, because the same target is patched in two tests):
     ```text
     patch:charter.activation.catalog.built_in_dir
     patch:charter.activation.catalog.resolve_doctrine_root
     patch:charter.activation.catalog.resolve_doctrine_root
     patch:charter.activation.profile_resolution._activation_aware_profile_map
     patch:charter.activation.profile_resolution._activation_aware_profile_map
     patch:charter.offering.directives.repository.built_in_dir
     private-call:_reset_agent_profile_cache
     private-call:_reset_agent_profile_cache
     private-import:charter.activation.profile_resolution._reset_agent_profile_cache
     private-import:charter.activation.profile_resolution._reset_agent_profile_cache
     ```
     That is the 4 patches in `TestBootstrapCorpusParity._render` plus the 2 in `test_first_load_marker` (6), and 2 imports plus 2 calls of `_reset_agent_profile_cache` (4). An earlier draft said "8 offenders" by counting each import+call pair once; the helper spec emits them separately, so 10 is correct. Do not tune the dedup to hit a number: compare against this exact list.
     Copy the failure text into the Activity Log (#5068: "red for the intended reason").
  5. Commit **only** these tests: `test(WP10): red-first src-coupling scan for context markers`.
- **Files**: `tests/charter/test_context_parity.py`.
- **Validation**: the planted test is green, the offender test is RED with exactly the 10 listed entries, and the other tests are unchanged and green.

### Subtask T055 – `_mirror_packs` fixture and the on-disk fixture profile

- **Purpose**: Replace every `src/` patch with filesystem state that the public resolvers read.
- **Steps**:
  1. Add `_mirror_packs(tmp_path: Path, *, empty_directives: bool = True) -> Path`:
     - locate the real pack root once, through the public `kernel.paths.get_built_in_pack_root()` called **before** the env var is set;
     - `shutil.copytree` each child of `packs/built-in` into `tmp_path / "packs" / "built-in"`, **never** `symlink_to` (D-OP-10);
     - when `empty_directives` is set, create `directives/` as an empty directory instead of copying it;
     - write `agent_profiles/parity-fixture-agent.agent.yaml` as literal YAML: `profile-id`, `name`, `roles`, `purpose`, `specialization.primary-focus`, and `directive-references` with code `"998"`. Mirror the fields of the current `_ghost_directive_profile()`;
     - return `tmp_path / "packs"`.
  2. Delete `_ghost_directive_profile()`, the `AgentProfile` import and `_empty_doctrine_root()`. The profile is now data on disk, which is a public format.
  3. Add a pytest fixture, `packs_mirror(tmp_path, monkeypatch)`, that calls `_mirror_packs` and `monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(root))`.
  4. Put the charter project and the packs mirror under distinct subdirectories of `tmp_path` (for example `tmp_path / "repo"` and `tmp_path / "packs"`), so the packs tree is not inside `.kittify`.
- **Files**: `tests/charter/test_context_parity.py`.
- **Parallel?**: No. It is sequenced before T056.
- **Validation**: `.venv/bin/python -c` smoke test, or the tests in T056.

### Subtask T056 – Convert the marker tests; add the pack-root and control assertions

- **Purpose**: Keep every behavioural assertion, and drop every patch.
- **Steps**:
  1. Rewrite `TestBootstrapCorpusParity._render` and `test_first_load_marker` to:
     - use the `packs_mirror` fixture;
     - write the charter files under the repo dir (`_write_common_charter_files` unchanged);
     - call `build_charter_context(repo, profile="parity-fixture-agent", action="implement", mark_loaded=True)`.
     Remove both `with (patch(...))` blocks, the `_reset_agent_profile_cache` import and calls, and the 36-line relocation-changelog comment (L195-230).
  2. Keep these assertions **byte-for-byte**:
     - `result.first_load is True`, the state file exists, and `"implement" in state["actions"]`;
     - `directive:DIRECTIVE_998` and `Cause: missing_artifact`;
     - `_LONG_BODY_NEEDLE not in text`, `section:terminology-canon`, and `# Governance payload:`.
     `TestIncludeEntryPointParity`, `TestJsonEntryPointParity` and `TestEmptyCharterProvenance` need no patch today. Leave their bodies unchanged apart from moving the repo into a subdirectory, if you do that for all tests.
  3. Add `test_packs_mirror_is_the_resolved_built_in_root`:
     - under `packs_mirror`, `kernel.paths.get_built_in_pack_root()` resolves inside `tmp_path`;
     - rendering under `warnings.catch_warnings(record=True)` records no `UserWarning` whose message mentions `SPEC_KITTY_PACKS_ROOT` (#3251 guard).
  4. Add the control test, `test_real_directive_catalog_changes_the_miss_cause`: `_mirror_packs(..., empty_directives=False)` plus the same render gives `"Cause: missing_artifact" not in text`, while `directive:DIRECTIVE_998` is still present. Do **not** assert the suggested directive ID; that would re-couple to the live catalog. This proves the empty-directives mirror is load-bearing.
  5. Keep the class and test **names** unchanged (`TestJsonEntryPointParity::test_json_entry_point_is_valid_bootstrap_payload` is cited by `context_contract.py`). The module docstring is rewritten to describe the on-disk fixture. Drop the "byte-parity" and "RETIRED byte-parity goldens" narrative, but keep one sentence pointing to `tests/charter/test_context_noop_stability.py` for render determinism.
  6. Run the order-dependence check from D-OP-5, in both orders: `.venv/bin/python -m pytest tests/charter tests/doctrine -q -p no:randomly`, then the same with `-n auto --dist loadfile`.
- **Files**: `tests/charter/test_context_parity.py`.
- **Validation**: all tests in the module are green, including T054's scan. Temporarily revert step 1 for one test and confirm the scan reds.

### Subtask T057 – Rename to `test_context_bootstrap_markers.py` and update references

- **Purpose**: The module is not a byte-parity test, so name it for the behaviour it checks. SC-003 then requires that no reference points at the old path.
- **Steps**:
  1. Run `git mv tests/charter/test_context_parity.py tests/charter/test_context_bootstrap_markers.py` as its own commit, with no content change, so `git log --follow` keeps history.
  2. Update the references. These are docstring or comment edits only:
     - `tests/charter/test_context_render_seams.py:7` (format-excluded, so do not format it);
     - `tests/charter/test_context_leaf_seams.py:6` (format-excluded);
     - `tests/charter/test_procedures_json_array.py:49` ("mirrors test_context_parity");
     - `src/charter/activation/context_contract.py:68` (`#:` comment).
  3. D-OP-3 proof for the `src/` comment. Save the output in the PR notes or the tracer.
     ```bash
     git show <base>:src/charter/activation/context_contract.py > /tmp/old.py
     .venv/bin/python - <<'EOF'
     import ast, pathlib
     old = ast.dump(ast.parse(pathlib.Path("/tmp/old.py").read_text()))
     new = ast.dump(ast.parse(pathlib.Path("src/charter/activation/context_contract.py").read_text()))
     assert old == new, "context_contract.py AST changed"
     print("AST equal")
     EOF
     ```
     Use the scratchpad instead of `/tmp` if your harness requires it.
  4. Search for leftovers, excluding `kitty-specs/**`, `docs/reports/**`, `docs/archive/**` and `CHANGELOG.md`: `grep -rn "test_context_parity" --include=*.py --include=*.md --include=*.yaml --include=*.toml . | grep -v '^./kitty-specs\|^./.worktrees'`. The result must be empty.
  5. Run `uv run --frozen ruff format tests/charter/test_context_bootstrap_markers.py` as a separate commit if it changes anything.
- **Files**: the four referencing files and the renamed module.
- **Validation**: `uv run --frozen ruff format --check tests/charter/test_context_bootstrap_markers.py` passes, and the leftover grep is empty.

### Subtask T058 – Blast radius, tracer and deferral decision record

- **Purpose**: Close out with evidence.
- **Steps**:
  1. Run the Test Strategy commands and record the counts.
  2. Append a tracer entry with `spec-kitty agent tracer-append --mission ratchet-baseline-census-gate-remediation-01M3EW3Z --category design-decisions --actor <you>`. It records:
     - RED 10 → GREEN 0 offenders (the exact list from T054 step 4);
     - copy mirror, no symlinks (D-OP-10);
     - the control test result;
     - the cache-order check in both orders;
     - "FR-015 delivered, not deferred" (or the deferral reason and follow-up issue, if T056 failed).
  3. Confirm that the `ci-windows.yml` lane is irrelevant. The module is `fast`, not `windows_ci`, and the copy mirror has no platform dependency.
- **Validation**: the tracer entry exists, and all commands are green.

## Test Strategy

```bash
.venv/bin/python -m pytest tests/charter/test_context_bootstrap_markers.py -q --durations=5
.venv/bin/python -m pytest tests/charter/ tests/doctrine/ -q -p no:randomly
.venv/bin/python -m pytest tests/charter/ tests/doctrine/ -q -n auto --dist loadfile
.venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q
make test-fast
uv run --frozen ruff check tests/charter/test_context_bootstrap_markers.py tests/charter/test_procedures_json_array.py src/charter/activation/context_contract.py
uv run --frozen ruff format --check tests/charter/test_context_bootstrap_markers.py tests/charter/test_procedures_json_array.py
uv run --frozen mypy tests/charter/test_context_bootstrap_markers.py
```

- Complexity ≤ 15, and no new `# noqa` or `# type: ignore`.
- **Pre-existing failure rule**: classify any base-red failure; if it is pre-existing, file or locate a GitHub issue before continuing.

## Risks & Mitigations

- **Process-wide caches leak between tests.** `builtin_mission_type_ids()` is `functools.cache`d but benign, because the missions are copied unchanged. The profile map is keyed by `repo_root`. Verify with the two-order run in T056.
- **The mirror goes stale against a future pack layout change.** The mirror copies whatever `packs/built-in` holds at run time, so it is self-updating. Only `directives/` and the fixture profile are synthetic.
- **#3251 flips to fail-closed later.** A valid mirror is unaffected, and the pack-root assertion stays true.
- **The scan is fooled by an alias** (`from unittest import mock as m; m.patch(...)`). Resolve the callee's final attribute name `patch`/`setattr` regardless of the base. The alias case is part of the committed planted set (T054 step 3).

## Review Guidance

Non-fakeable checks (from `research/postspec-renata.md`, FR-015 MEDIUM, and Debbie's post-plan HIGH):

- The RED evidence shows exactly the **10** entries listed in T054 step 4 (6 patch sites + 2 private imports + 2 private calls), not 4 and not a tuned 8. The predicate covers **all** first-party patch targets, including the non-underscore `charter.activation.catalog.built_in_dir`, `charter.activation.catalog.resolve_doctrine_root` and `charter.offering.directives.repository.built_in_dir`.
- The self-mutation test calls the same `_src_coupling_offenders` function that the real check uses.
- The four marker assertions are unchanged, compared with a diff against base.
- The control test demonstrates that mutating the fixture changes the outcome. The pack root is asserted to be under `tmp_path`.
- There is no `symlink_to` anywhere, and no `src/` behaviour diff (the AST-equality output is recorded).
- Old path references: 0 live hits.
- The committed planted set includes the `mock as m` alias case.

**Reviewer RED reproduction** (mechanical; run in the lane worktree; `<lane-base>` is the lane's base commit, e.g. `git merge-base HEAD claude/spec-kitty-remediation-wfje22`):

```bash
RED=$(git log --reverse --format=%H <lane-base>..HEAD | head -1)
git stash -u; git checkout "$RED"
.venv/bin/python -m pytest tests/charter/test_context_parity.py -q -k no_src_patch_targets
git checkout -; git stash pop
```

It must fail with an assertion listing exactly the 10 entries of T054 step 4 (the RED commit precedes the file rename, so use the old path). An `ImportError`, `NameError` or collection error is not a valid RED.

**Requirement coverage** (prose; frontmatter is regenerated by the orchestrator): FR-015, NFR-002 (non-vacuity floor + planted offenders), NFR-005, NFR-006 (private-patch coupling replaced, invariants kept), C-001, C-005; contributes to SC-005.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

**Format**: `- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>` (append at the END; UTC timestamps via `date -u "+%Y-%m-%dT%H:%M:%SZ"`).

- 2026-09-26T15:00:00Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task WP10 --to <status>` to change WP status.
