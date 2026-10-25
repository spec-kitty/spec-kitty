# WP01 review feedback (cycle 1) — reviewer-renata

Verdict: changes requested. The core fix is right: the absent key is never written, the shipped module is byte-identical to origin/main, the supersession and manifest entry are in place, the #6629 reproduction goes red against origin/main's `supersession.py` and green with the fix, and the 10-file targeted suite passes (162 passed). One WP-named risk is not handled.

## MAJOR

**Issue 1: a malformed activation ledger crashes the upgrade instead of becoming a failed record.**
`src/specify_cli/upgrade/migrations/m_4_0_0rc8_promote_interview_selections.py:260` (`resolve_activation_write_target`) and `:180` (`load_activation_ledger`) let `ActiveCharterConfigError` escape `apply()`. `MigrationRunner._apply_migration` (`src/specify_cli/upgrade/runner.py:512-537`) catches only `NotInsideRepositoryError`, `GitCommonDirUnavailableError`, `GitignorePathError` and `MigrationStateUnreadableError`. So the exception goes up through `MigrationRunner.upgrade`: nothing is recorded as `failed`, `_finalize_main_metadata` (the version-stamp restore) never runs, and `spec-kitty upgrade` ends with a traceback.
Reproduced: a git project with a seeded activation ledger, `answers.yaml` selecting `DIRECTIVE_024`, and `activation.yaml` overwritten with `activated_directives: [unclosed`. Then `runner._apply_migration(<this migration>, meta, False)` raises `ActiveCharterConfigError ACTIVE_CHARTER_CONFIG_INVALID`.
This can happen in practice: on a project whose `4.0.0rc8_activation_ledger` is already settled, the earlier migration's own guard never runs again, so this successor is the first code to read the activation ledger.
The WP Risks section asks for exactly this case: "Let it surface as a failed result (an error string), never a silent pass."
Fix: follow the sibling `m_4_0_0rc8_activation_ledger.py:66-69`, which raises `MigrationStateUnreadableError(exc.body)` from `ActiveCharterConfigError`. The runner then records that as `failed`. Alternatively, return `MigrationResult(success=False, errors=[exc.body])`. Add a unit test that corrupts `activation.yaml` and asserts the failed result (or the `MigrationStateUnreadableError`), so the activation ledger is left unchanged and nothing passes silently.

## MINOR

**Issue 2: new branches with no test.** Branch coverage of the module is 97%. The following are not covered:
- `:130-131`, the `UnrepresentableDirectiveIdError` arm. T002 names it, and it should land in `unresolved`.
- `:253-254`, the doctrine-root failure that returns `success=False`.
- `:289->292`, a committed plan that activated nothing, so no restamp.
- `:147`, an answers duplicate that is deduplicated.

Add focused tests for the first two at least (CLAUDE.md: "Every new branch/helper needs tests in the same PR").

**Issue 3: the WP's narrow mypy command reports false errors.**
`mypy base.py <module> api.py` reports `:195 Returning Any` and, without `base.py`, `:226 cannot subclass BaseMigration`. Both come from the `charter.*` / `specify_cli.*` `follow_imports = "skip"` overrides (pyproject.toml, issue #3719). Adding `src/charter/activation/activation_engine.py` to the invocation makes it clean, so the code is fine. Record the clean invocation, with `activation_engine.py` included, in the PR *Tests run* section.

**Issue 4 (nit): `_load_answers` (`:103-106`) catches bare `Exception`.**
That includes `OSError` from a permission error, which then reads as "no selections" and skips the migration silently. Narrow it to `(OSError, UnicodeDecodeError, YAMLError)`, or keep the rationale and log at debug level. This is optional and matches the shipped helper.

## Checklist
1. Dead code: PASS. The module is auto-discovered and listed in `_CATEGORY_1_AUTO_DISCOVERED_MIGRATIONS`, and every new `api` re-export is used by it.
2. Synthetic-fixture test: PASS. The tests drive the real `apply()` and the runner.
3. Silent empty return: PASS with a note. `_load_answers` returns `{}` and the rationale is documented (see Issue 4).
4. FR coverage: PASS for FR-001 to FR-010. FR-009 uses the monkeypatch fallback that the WP allows.
5. Frozen surface: PASS. `git diff origin/main -- src/specify_cli/upgrade/migrations/m_unify_charter_activation.py` is empty.
6. Locked decision: PASS. No absent key enters `promotions`, because `_present_lists` filters on `is not None`.
7. Shared-file ownership: PASS. There is no overlap with WP02's owned files.
8. Production fragility: FAIL. See Issue 1: an unhandled `ActiveCharterConfigError` on the upgrade path.
