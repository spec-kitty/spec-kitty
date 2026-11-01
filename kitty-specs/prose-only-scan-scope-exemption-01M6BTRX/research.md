# Discovery: prose-only down-route scan-scope exemption (#6999)

## Decision 1 — The defect is real and reproduces on current `main` (287a226cfe)

Evidence, run in the clone at `287a226cfe` with `uv run --frozen python`:

- A docstring-only base→head pair for `scripts/release/extract_changelog.py`
  yields `prose_only_pr_verdict([path], blobs, doc_globs) is True` — the #4842
  verdict fires.
- `select_gates([path]).matched_groups == {'arch_scan_scope'}` — the #6996
  router group does select the heavy battery for that path.
- `gate_selection.select_battery_gates([path])` returns the five declared
  `scripts/**` scanners: `test_clock_call_ban.py`, `test_clock_import_ban.py`,
  `test_first_party_hosts_are_owned.py`,
  `test_no_deprecated_doctrine_command_in_guidance.py`,
  `test_no_retired_subsystems.py`.
- Evaluating the real `architectural-heavy` `if:` with
  `changes.arch_scan_scope=true, prose-scan.prose_only=true` gives `False`
  (the trailing `&& needs.prose-scan.outputs.prose_only != 'true'` subtracts
  the whole battery), while `prose_only=false` gives `True`.

So every declared `scripts/**`/`tests/**`/`docs/**`/`packs/**` scanner is
dropped for exactly the prose diffs it guards. Confirmed, not superseded: no
merged PR references #6999, `git log -S "prose_only"` since 2026-10-25 has no
follow-up commit, and the #4842 goldens
(`test_golden_prose_only_pr_down_routes_matrix_arch_battery_and_code_shards`,
`test_battery_if_keeps_the_prose_only_conjunct_as_the_single_outer_and`) pin the
current subtract-whole-battery behaviour.

## Decision 2 — Fix shape: two seams, no new job and no new group

1. **Router `if:` (`.github/workflows/ci-router.yml`, `architectural-heavy`).**
   Keep the subtraction as the outer `&&` but make it conditional on the diff
   *not* touching declared scan scopes:
   `(prose_only != 'true' || changes.arch_scan_scope == 'true')`.
   The OR term is already present in the battery's group OR, so the
   `needs.changes.outputs.<group>` model and
   `HEAVY_BATTERY_NON_SRC_GROUPS` keep their member sets (C-002).
2. **Scoped selection (`scripts/ci/battery_scope.py` + `gate_selection.select_battery_gates`).**
   The prose verdict is content, not path, so it enters the selection as an
   explicit input (`--prose-only`, from the `prose-scan` job output), never by
   re-deriving content inside the pure router. Under `prose_only=True` the
   selection returns only the gates whose declared `scan_scopes` match, and
   never `None` (whole battery) for a code-group match or a battery-code-helper
   touch — prose-only proves no behaviour change, so those widenings are
   unnecessary; the declarations remain the single source (NFR-002).

**Rejected alternative:** derive prose-ness inside `select_battery_gates` (git
blobs + `is_prose_only`). That duplicates the prose-scan verdict, adds IO to a
pure selection path, and gives two sources for one fact.

**Rejected alternative:** make `prose-scan` publish a new "scan-scope match"
output. `changes.arch_scan_scope` is already the test-pinned transcription of
`battery_scope_router_globs()`, which is derived from the same declarations, so
a second output would be a second source for the same fact (NFR-002).

## Decision 3 — Fail-safe direction is unchanged

`battery_scope.decide` already answers `mode=full, run=true` for no base, a git
error or a selection error, and the step's `||` fallback does the same. Prose
mode must not narrow on doubt: full mode and an unusable diff still run the
whole leg. Running too much is safe; running too little is the bug.

## Decision 4 — Scope limit: declared scopes only

A gate that reads comment text under a path it does not declare stays out of
this fix. #7000 (filed from #6996) owns a mechanical completeness scan of the
declarations. Note this in the changelog/docs wording so the limit is explicit.

## Open questions for specify/plan

- None blocking. The mission is a single focused change: two workflow lines
  worth of routing semantics, one selection parameter, the CLI flag, the golden
  updates with the ruling citation, and a planted regression pin.

## Evidence kept

- Issue #6999 body (operator ruling 2026-11-01), issue #6994 / PR #6996 body
  (scoped-leg mechanism and its Deferred note naming this issue).
- The reproduction commands above are re-runnable from the clone root.
