# WP04 Review — Changes Requested (review-feedback-1)

Reviewer: reviewer-renata (independent). The substance of this WP is **correct and
verified** — see "What passed" below. There is exactly **one blocker**, and it is a
one-command fix. Everything else is approved on the merits.

## BLOCKER — Issue 1: newly-authored code fails the enforced `ruff format --check` gate

Per CLAUDE.md ("Formatting is a separate gate from linting", #3952): CI runs
`ruff format --check .` over the whole repo and `tests/architectural/test_ruff_format_enforcement.py`
enforces the same command in `make test-full`. `ruff check` passing (it does) says
nothing about format. The repo's `line-length = 164` (pyproject.toml), so `ruff format`
wants your multi-line splits collapsed onto single lines.

Two of the WP's **own new lines** fail the gate:

- `src/specify_cli/template/manager.py:86` — the `console.print(...)` in the new
  `back_up_operator_subtrees` helper (absent from base; introduced by this WP).
- `tests/cli/test_init_backup_then_proceed.py:130` — the `_find_backed_up_file(...)`
  call inside `test_copy_specify_base_from_local_...` (this file is 100% authored by
  this WP via `create_intent`).

The for_review note claimed "ruff+mypy clean"; that covered `ruff check` only. The
format gate is not clean on your own new file, so CI would go red.

**Fix:** run `./.venv/bin/ruff format src/specify_cli/template/manager.py tests/cli/test_init_backup_then_proceed.py`
then re-verify with `./.venv/bin/ruff format --check <owned files>`. `init.py` already
formats clean — leave it.

**In-scope campsite (do it while you're formatting manager.py):** the base
`manager.py` also carries a pre-existing format violation in `get_local_repo_root`
(the `_is_template_root` return expression, ~line 253) — not introduced by you, but
manager.py is an owned/touched file, so a plain `ruff format` of the whole file will
fold it and leave the file green. Please include it.

## What passed (verified — do not redo)

- **All 3 destructive sites route through the single canonical helper**
  `back_up_operator_subtrees` (grep of `shutil.rmtree` in both modules confirms no
  operator-subtree bypass): `copy_package_tree(preserve_existing=True)`,
  `copy_specify_base_from_local` (memory + missions), and the extracted
  `_discard_failed_project_scaffold`. The remaining `rmtree` sites operate only on
  regenerable scaffold/scratch (`templates/`, `.resolved-*`, `.scratch`, `.merged-*`) —
  acceptable per T014.
- **Each site triggered DIRECTLY** by a dedicated test (not one end-to-end init), each
  asserting operator bytes SURVIVE in a reported `.backup-<ts>/` — none assert "init
  exits 1". SC-003 satisfied.
- **Same-second collision test** present and genuine: monkeypatches the timestamp seam,
  produces `.backup-…Z` and `.backup-…Z-1`, asserts neither is overwritten. Exercises
  the real `mkdir(exist_ok=False)` retry loop in `_allocate_backup_dir`.
- **FR-007 predicate test** present and direct: `_has_operator_authored_content` True
  for populated `.kittify/` without `config.yaml`, with negative cases for blank / no
  `.kittify` / empty-subtree.
- **Backup vocabulary distinct** from `template_render/pipeline.py`'s transactional
  `.bak-{nonce}`: prefix is `.backup-`, no import/entanglement of the pipeline helper;
  C-006 called out in the module docstring.
- **Red-first evidence** present (for_review note: 10 tests, 9 failed pre-fix; the 1
  passing pre-fix is the unchanged-behavior regenerable-replace regression test —
  consistent). Re-ran on current code: **10 passed**.
- **Deviation adjudicated — accepted.** The `init.py` rollback `rmtree` is currently
  CLI-unreachable-with-operator-content (the upfront directory-conflict guard at
  init.py:863–872 refuses when a positional project dir already exists), so under the
  CLI's own guard it only removes a scaffold this run created. Fixing it anyway is
  correct: the "never rmtree operator content" invariant is unconditional and
  forward-compatible (a future guard change must not silently reintroduce the #4759
  class). The direct-call test is genuine coverage, not a no-op — it calls
  `_discard_failed_project_scaffold(here=False)` on a populated project_path and asserts
  the sibling backup survives; removing the backup call would fail it.
- **mypy clean**; complexity fine (the extraction reduces `init()` complexity).
- **Scope**: changes confined to owned_files (init.py, template/manager.py,
  template/__init__.py export, the test). No terminology-canon (`--feature`) issues.

## After the fix

Re-run `./.venv/bin/python -m pytest tests/cli/test_init_backup_then_proceed.py -q`
(should stay 10 passed) and confirm `ruff format --check` is clean on the owned files,
then move back to review.
