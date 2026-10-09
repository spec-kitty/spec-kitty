# WP03 review feedback (round 1)

Reviewer: reviewer-renata (claude). Reviewed lane-c `3ee1c97a..26385aba` (12 WP03 commits).

## Verdict: changes requested

The write-side cutover itself is sound. Every project-layer writer goes through
`kernel.charter_pack_paths`. Nothing in `src/` can recreate `.kittify/doctrine/`: the
remaining legacy-name uses are reads (`service.py`, `runner.py`, the `manifest.py`
predicate). The gate fails on a planted `.kittify/doctrine` join in a real src file.
The WP03 acceptance tests are green. Three items must be fixed before approval:
a red lint gate, wrong allowlist owners, and a gate blind spot that hides a site
WP14 expects to find on the allowlist.

## Required changes

1. **`ruff check .` is red (CI lint gate).**
   `tests/acceptance/charter_pack_cutover/test_project_pack_root.py:17` still imports
   `pending_until`, which is unused (F401) since the red-first commit `e92ccab9` removed the three
   markers. A whole-repo `uv run --frozen ruff check .` reports exactly this one error, and the base
   (`3ee1c97a`) has none. Remove the unused name from the import. Removing an import does not change
   any assertion, so C-006 still holds. The Activity Log says "ruff check + format clean". That
   check covered the touched src/test files but not this acceptance file. Re-run `ruff check .`
   over the whole repo.

2. **Seven allowlist entries name an owner whose prompt does not cover them.**
   `tests/architectural/charter_pack_path_allowlist.yaml` gives seven research B.2 clause-(b)
   sites the owner `WP14`, with the rationale "handed to WP14 T070, which repoints it through
   kernel.charter_pack_paths". WP14's T070 has no such step: it repoints no `fragment.yaml` or
   `org-charter.yaml` literal (step 3 lists only the temporary legacy symbols). The seven sites are:
   - `_drg_helpers.py` `load_validated_graph`
   - `drg_activation.py` `load_org_drg`
   - `org_pack_loader.py` `load_org_pack`
   - `org_pack_discovery.py` `_iter_org_charter_docs` and `require_org_skill_policy_readable`
   - `mission_step_contracts/executor.py` `_org_root_folds_fragment`
   - `_doctrine_collect.py` `_summarize_org_charter`

   The WP03 prompt (T019) assigns these sites to **WP25**, "unless a WP touching the file removes
   them first". Change `owner` to `WP25` and correct each `rationale`. WP25 T113 drains the
   FR-016 allowlist to empty.

   Optional: `pack_manager.py` `_scan_layout_for` (`"doctrine/{}"`) is also given to WP14. WP14's
   prompt names only `kind_vocabulary.py` for the nested org layout. Either keep WP14 and add one
   line to the Activity Log ("same nested-layout decision as `kind_vocabulary.py`, WP14 T070
   step 3"), or assign the entry to WP25.

3. **The gate does not see a path segment that is iterated into a `/` join. That hides
   the site WP14 expects to delete.**
   - WP03 T019 lists `_doctrine_paths.py:32` (the flat built-in fallback) as an expected
     allowlist entry with owner WP14. WP14 T070 step 3 deletes "the two FR-016 allowlist entries
     assigned to WP14 (`kind_vocabulary.py:297`, `_doctrine_paths.py:32`; WP03 T019)".
   - The site is now `src/charter/activation/_doctrine_paths.py:37`. The tuple
     `_BUILT_IN_FALLBACK_CANDIDATES` contains `"doctrine"` and is joined at `:48` by
     `repo_root / candidate for candidate in _BUILT_IN_FALLBACK_CANDIDATES`.
   - The gate does not flag it, so the allowlist does not list it.
   - The same shape occurs at `src/specify_cli/tool_surface/providers/agent_profiles.py:582`:
     `root / p for p in (..., "doctrine", ...)`.

   By the gate's own docstring both are clause (a) findings ("any other `doctrine` directory a
   path is built through"), and the tuple elements are path parts.

   Required:
   - Extend the scan so that a tuple/list literal, or a module-level tuple/list name already
     resolved in `_Aliases.sequences`, used as the iterable of a `for` / comprehension, counts as
     path parts when the loop target is an operand of a `/` `BinOp` or a `Path()` / `joinpath()`
     argument inside that loop.
   - Add a planted test for each form: the inline iterable and the module alias.
   - Keep the existing non-path tuple and membership-tuple negatives green.
   - Allowlist the two live sites: `_doctrine_paths.py` with owner WP14, as the prompt says;
     `agent_profiles.py` with owner WP14 or WP25 and a rationale.
   - Raise the baseline to match the new entry count (27, if only the two new entries are added).
   - Record the new count in the Activity Log.

## Non-blocking observations (no change required; recorded for the orchestrator)

- **Shapes the gate does not catch.** Probed through `scan()` on planted files; no live src site
  uses any of them today:
  - a function-local alias (`seg = "doctrine"; root / ".kittify" / seg`)
  - `os.path.join(r, ".kittify", "doctrine")`
  - attribute access `p.LEGACY_PROJECT_PACK_DIRNAME` after `import kernel.charter_pack_paths as p`
  - string concatenation
  - a parameter default (`sub="doctrine"`)
  - a class attribute (`self.SEG`)

  Optionally list them as known limits in the gate's docstring.
- **Planted staleness test.** `test_stale_allowlist_entry_is_detected` only shows that a
  speculative key is absent from the live findings. The real staleness check is the exact
  accounting in `test_allowlist_accounts_for_every_live_finding`, which is correct. Optionally,
  make the planted twin call that accounting with a speculative key and assert that it fails.
- **`missions/repository.py`, seven WP25 entries.** These are `TemplateResult.origin` display
  labels (`doctrine/<mission>/...`). They are not filesystem paths and nothing persists them; they
  are flagged because they are path-shaped f-strings. Owner WP25 is right only through T113 (the
  FR-016 allowlist closes empty); WP25's prompt does not name them. The sibling label in
  `template_resolver._tier_to_origin` (`PACKAGE_DEFAULT: "doctrine"`) is not flagged, as the
  prompt intended. Whoever renames one must rename the other, or the two origin labels diverge.
- **Split-brain risk.** It exists only in unreleased intermediate state: OD-10 makes this one
  mission and one PR, WP11 adds the migration and WP14 the `LEGACY_CHARTER_STATE` fail-closed
  gate. No released code path exposes it. The risk: a project still on the legacy root, after
  synthesize or `new`, has a new root, and the read fallback then hides its legacy artifacts.
- **State surface rename.** `project_doctrine_graph` became `project_pack_graph`. `doctor` prints
  the name, so users can see it. WP24 T108 already lists it (WP24 prompt line 147). Nothing else
  in src, tests or docs still uses the old name.
- **Edits outside WP03's owned files.** All are legitimate: no other lane was active, and each
  touched file belongs to a later or dependent WP.
- **Drift for other WPs.** WP21's prompt still names `computer.py` `_doctrine_dir`, which WP03
  replaced with `_project_pack_read_root`. The shared `seed_graph` fixture
  (`tests/specify_cli/charter_preflight/_fixtures.py`) still seeds the legacy root. The
  implementer logged this; WP14 has to convert it.

## Verified green

- `uv run --frozen pytest tests/acceptance/charter_pack_cutover -q -n 4 --dist loadfile`: 87 passed,
  1 skipped (Windows-only), 265 xfailed, 0 failed, 0 xpassed.
- `test_project_pack_root.py`: 6 passed, including the three WP03 tests.
- FR-016 gate: 36 passed. It goes red on two planted sites in a real src file
  (`_fresh_doctrine.py`: a BinOp and an f-string); the file was reverted afterwards.
- Six gate files together: 233 passed. They are `test_charter_pack_path_authority`,
  `test_charter_path_literal_authority`, `test_no_stale_charter_path_literals`, `test_layer_rules`,
  `test_lifted_root_gitignore_contract` and `test_no_legacy_terminology`.
- `tests/charter/synthesizer`: 460 passed, 12 skipped.
- mypy on the 21 touched src files: the same 4 errors as on base `3ee1c97a`, none new.
- `ruff format --check --force-exclude`: clean.
- `tests/ci/test_corpus_blocking_home.py::test_every_corpus_test_has_a_blocking_per_pr_home` is
  red on base `3ee1c97a` as well, with the same 25 unhomed WP01 corpus tests. It is pre-existing
  and not caused by WP03.
