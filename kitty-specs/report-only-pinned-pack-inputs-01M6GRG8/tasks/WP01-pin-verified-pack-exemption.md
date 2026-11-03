---
work_package_id: WP01
title: The pin-verified pack tree exemption
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
- C-003
- SC-001
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-7128-report-only-pinned-pack-inputs
merge_target_branch: issue-7128-report-only-pinned-pack-inputs
branch_strategy: Planning artifacts for this mission were generated on issue-7128-report-only-pinned-pack-inputs. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7128-report-only-pinned-pack-inputs unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Production change and proof
history:
- at: '2026-11-03T13:20:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/
create_intent:
- tests/specify_cli/test_analysis_inputs_pinned_packs.py
execution_mode: code_change
owned_files:
- src/specify_cli/analysis_inputs.py
- src/specify_cli/git/report_transaction.py
- tests/specify_cli/cli/commands/agent/test_analysis_report_transaction.py
- tests/specify_cli/test_analysis_inputs_pinned_packs.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#7128'
---

# Work Package Prompt: WP01 – The pin-verified pack tree exemption

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi` (implementation sub-agent)

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.

---

## Objectives & Success Criteria

`spec-kitty agent mission record-analysis --report-only` refuses with `DIRTY_ANALYSIS_INPUT` in any
clone that ran the documented `make sync-packs` step (#7128). The preflight's "material input with no
committed state" rule (`src/specify_cli/git/report_transaction.py`, the `relevant.update(...)` line
that scans `material_paths`) counts the gitignored, fetched `packs/<name>/` tree as dirty. That tree
*is* a material input — and it does have committed state: the tracked `packs/<name>.source.yaml`
records the open-packs `commit`, `subtree`, `tree_digest` and `snapshot_sha256`, and
`charter.offering.packs.pack_pin.verify_pack_pin` can prove, offline, that the tree on disk is
exactly that pinned tree.

This work package adds that one exemption and nothing else:

1. a predicate in `src/specify_cli/analysis_inputs.py` that returns the repo-relative roots of pack
   trees whose content the **committed** pin verifies;
2. a filter in the preflight that removes only those roots from the untracked-material dirty set;
3. the end-to-end and unit proof that it holds, with every negative control still refusing.

Definition of Done:

- The four new end-to-end cases pass; the positive one fails on the pre-change code with
  `DIRTY_ANALYSIS_INPUT` naming a `packs/internal/...` path (record that failure in the WP history
  or a tracer entry).
- Every pre-existing case in `tests/specify_cli/cli/commands/agent/test_analysis_report_transaction.py`
  passes **unedited** — in particular `test_dirty_material_input_refuses_before_write` and
  `test_unsafe_state_refuses_without_report_write[ignored_input]`.
- `ruff check`, `ruff format --check` and `mypy` are clean for the touched files.

## Context

Read, in this order:

1. `kitty-specs/report-only-pinned-pack-inputs-01M6GRG8/research.md` — D1–D6 are the measurements
   and the decisions this WP implements. D2 explains why "exclude ignored paths" is **rejected**.
2. `kitty-specs/report-only-pinned-pack-inputs-01M6GRG8/data-model.md` — the relation, its five
   conditions and its fail-closed arms.
3. `src/specify_cli/git/report_transaction.py` lines ~300-325 — the four dirty rules.
4. `src/specify_cli/analysis_inputs.py` — `collect_material_inputs` and how pack roots enter the
   manifest (`load_pack_registry(root).packs` → `pack.effective_root(root)`).
5. `src/charter/offering/packs/pack_pin.py` — `PackPin`, `load_pack_pin`, `verify_pack_pin`.
6. `scripts/sync_packs.py` — how the real tree is verified (`check_pack`) and how the pin path is
   named (`root / "packs" / pin_filename(name)`).

Measured facts you can rely on (do not re-derive): on a synced clone `_dirty_paths(repo)` is empty;
67 `packs/internal/*` material paths are untracked-by-design; `verify_pack_pin` on that tree costs
~8 ms; `packs/built-in/` never contributes per-file material paths (`_package_inputs()` digests it
as `package:built-in` with `path: null`).

## Detailed Guidance

### T001 — Red first, through the production entry point

Add to `tests/specify_cli/cli/commands/agent/test_analysis_report_transaction.py` (reuse its `repo`
fixture; keep the module's `pytestmark`):

- A fixture helper that, in the existing `repo`, writes a minimal org pack at `packs/internal/`:
  a valid `pack.yaml` (`pack_id` a 26-char ULID, `pack_version`, `parent_pack: null`,
  `name: spec-kitty-internal`, `pack_level: org`, `active_charter: org-charter.yaml`,
  `pack_drg: drg/fragment.yaml`), an `org-charter.yaml`, a `drg/fragment.yaml` with `nodes: []`,
  and one artifact file under a recognised artifact directory (for example
  `procedures/example.procedure.yaml`); writes `.gitignore` with `/packs/internal/`; writes
  `packs/internal.source.yaml` using `write_pack_pin` with
  `TreeDigest(algorithm=TREE_DIGEST_ALGORITHM, value=clean_tree_digest(tree, level="org"), level="org")`
  and `snapshot_sha256=full_tree_digest(tree)`; extends `.kittify/config.yaml` with
  `charter_packs.org.packs: [{name: internal, local_path: packs/internal}]`; then commits
  `.gitignore`, the pin and the config.
- Four cases, all through `invoke("--report-only")`:
  1. positive: exits 0, `commit_status == "committed"`, the commit's changed paths are exactly the
     report;
  2. a byte appended to the pack artifact file → exit 1, `DIRTY_ANALYSIS_INPUT`, the path named in
     the JSON `dirty_paths`, and no report on disk;
  3. the pin file edited and left uncommitted → exit 1, `DIRTY_ANALYSIS_INPUT`, naming the pin;
  4. with the pin intact, an ignored untracked file under `.kittify/templates/` still refuses
     (`DIRTY_ANALYSIS_INPUT`) — the same-fixture control that the exemption did not become
     "ignored is clean".
- Run them **before** touching `src/` and record the positive case's failure.

Do not weaken or edit any existing case. If the fixture needs the pack to be inert for the report
render, keep `org-charter.yaml` and `drg/fragment.yaml` minimal rather than pulling in the real
internal pack's contents.

### T002 — The predicate

Add to `src/specify_cli/analysis_inputs.py`:

```python
def pinned_pack_tree_roots(repo_root: Path) -> tuple[str, ...]:
    """Repo-relative roots of fetched pack trees whose COMMITTED pin content-verifies them."""
```

Rules (see `data-model.md`):

- candidate roots: `pack.effective_root(repo_root)` for each `load_pack_registry(repo_root).packs`;
- the root must be a directory inside the repository (`root.relative_to(repo_root)`) — otherwise
  skip it silently;
- the pin is `<root>.source.yaml` (a sibling **file** of the pack directory: `packs/internal` →
  `packs/internal.source.yaml`); it must be **tracked** (`kernel.git.tracked_paths`) and **clean**
  (`kernel.git.status_entries` reports no entry for it) — so the on-disk pin *is* the committed pin;
- `load_pack_pin(pin_path)` must succeed and `pin.subtree` must equal the root's repo-relative POSIX
  path;
- `verify_pack_pin(pin, root)` must be `True`;
- any exception from any of the above (`PackPinError`, `OSError`, `ValueError`,
  `pydantic.ValidationError`, the registry's env/subdir errors) means "not exempt" — never let it
  escape;
- return a sorted tuple of repo-relative POSIX strings.

Import the pack-pin helpers lazily inside the function if a module-level import would create an
import cycle or slow `analysis_inputs`' import; follow the file's existing style (`analysis_inputs`
already imports many things lazily).

Cost control: query the pin files' tracked/clean state with **one** `tracked_paths` and **one**
`status_entries` call over all candidate pin paths, not one call per pack.

Add a short module docstring/comment naming the invariant: a fetched tree's committed state is its
pin, so a tree that matches its committed pin is not an input "without committed state".

### T003 — The filter

In `record_report_transaction`, keep the four rules but scope the untracked-material one:

```python
tracked = {str(path) for path in tracked_paths(repo_root)}
untracked_material = {
    path for path in material_paths
    if path is not None and (repo_root / path).is_file() and path not in tracked
}
if untracked_material:
    untracked_material -= _under_roots(untracked_material, pinned_pack_tree_roots(repo_root))
relevant.update(untracked_material)
```

- Component-wise prefix only: `path == root or path.startswith(root + "/")` — `packs/intern` must
  never match a `packs/internal` exemption.
- Do **not** apply the exemption to `dirty & material_paths`, to the charter-dirt rule, or to
  `_working()`: a tracked file inside a pack tree is still ordinary dirt (data-model I-2).
- Keep the function's existing shape, ordering and error codes; the refusal payload is unchanged.
- Call the predicate only when `untracked_material` is non-empty (NFR-001: a clean clone pays
  nothing) and at most once.

### T004 — Fast unit cases

`tests/specify_cli/test_analysis_inputs_pinned_packs.py` (new file, keep it fast: `tmp_path` and a
`git init`-ed directory, no CLI invocation) covering:

- pin `subtree` naming a different root → not exempt;
- no pin file → not exempt;
- pin without `snapshot_sha256` (or an unknown `tree_digest.algorithm`) → not exempt;
- pack root that resolves outside the repository → not exempt, no exception;
- one fixture with both `packs/internal` (pinned, verified) and `packs/intern` (unpinned): only
  `packs/internal` is returned, and `packs/intern`'s files stay dirty.

Follow the existing unit-test style in `tests/charter_offering/test_pack_pin.py` for building pins.

### T005 — Verification

```bash
uv run --frozen pytest tests/specify_cli/cli/commands/agent/test_analysis_report_transaction.py -q
uv run --frozen pytest tests/specify_cli/test_analysis_inputs_pinned_packs.py -q
uv run --frozen ruff check src/specify_cli/analysis_inputs.py src/specify_cli/git/report_transaction.py tests/specify_cli/test_analysis_inputs_pinned_packs.py
uv run --frozen ruff format --check <the same files>
uv run --frozen mypy src/specify_cli/analysis_inputs.py src/specify_cli/git/report_transaction.py
```

No full heavy suite (NO_FULL_HEAVY_SUITES_IN_MISSION). If a pre-existing failure appears, prove it on
a pristine checkout before attributing it to this diff, and report it rather than editing it.

## Branch Strategy

Planning artifacts for this mission were generated on `issue-7128-report-only-pinned-pack-inputs`.
Execution worktrees are allocated per computed lane from `lanes.json`; completed changes must merge
back into `issue-7128-report-only-pinned-pack-inputs` unless the human redirects the landing branch.
Never push `main`.

## Test Strategy

- Red first through the real CLI (`CliRunner().invoke(app, ["record-analysis", ...])`), on a real git
  fixture — the production path, not a helper.
- One fixture, opposite outcomes: the exemption and its three refusals share the fixture so they
  cannot drift (acceptance-criteria non-vacuity).
- Do not delete an assertion to make a test pass; do not skip or xfail anything.

## Definition of Done

- [ ] T001 red failure recorded, then all four cases green.
- [ ] `pinned_pack_tree_roots` added, documented, and exported where the module keeps its public API.
- [ ] The preflight filter is prefix-scoped and applies to the untracked-material rule only.
- [ ] Every pre-existing test in the touched modules passes unedited.
- [ ] `ruff`/`format`/`mypy` clean for the touched files.
- [ ] No machine-local path, no personal data, no `main` push.

## Risks & Mitigations

| Risk | Mitigation |
| --- | --- |
| Exemption becomes "ignored is clean" | Returns roots, not a verdict; prefix-scoped; the same-fixture control (case 4) fails if it drifts |
| Pack fixture too permissive (a digest that passes for the wrong tree) | Build the pin with `clean_tree_digest`/`full_tree_digest`, never a literal; case 2 changes one byte inside the tree |
| Preflight slows down | Predicate runs only when untracked material exists; two git listings total |
| Silent exception turning into a refusal with no path | Exception handling in the predicate is explicit and total; a raised error would surface as exit 1 with an unexplained message, so keep the arms enumerated |

## Reviewer Guidance

- Confirm the diff touches only the untracked-material rule, and that `dirty & material_paths`,
  `_canonical_charter_dirt` and `_working` are untouched.
- Confirm the predicate proves "committed pin" (tracked + clean) rather than reading a `HEAD` blob
  through a new parser, and that no new digest or pin format exists.
- Confirm the positive case genuinely fails without the production change (revert T002/T003 only and
  watch it go red).
- Confirm nothing was skipped, xfailed, or relaxed.
