# Research: Charter follow-ups tidy-up

The research is two read-only squad lenses run on `origin/main` `267afe207`: alignment (researcher-robbie) and scope (planner-priti). All five issues are still real.

## #6539: runner skips on NotInsideRepositoryError

- **Decision**: a declared `requires_git_repository` ClassVar, checked before `detect()`. The `apply()` catch is removed; the `detect()`/`can_apply()` catches stay. Operator decisions `migration_repo_requirement` and `migration_flag_ledger_drift`.
- **Evidence**:
  - `runner.py` catches the error at :387 (`detect`), :434 (`can_apply`) and :450 (`apply`), and all three go to `_not_inside_repository_skip` (:477). Its docstring admits the `apply()` hazard.
  - The only raiser is `charter.resolution.resolve_canonical_repo_root` (:134).
  - The direct migration caller is `m_3_2_0rc35_unified_bundle.apply` (:157), which resolves the root before it writes.
  - Transitive reach: `charter.activation.sync` :102 (`ensure_charter_bundle_fresh`) and :215 (`_charter_yaml_path`).
  - About 10 migrations import `charter.activation.*`.
- **Consequence**: an execution-based audit decides which migrations declare the flag. The audit runs the full registry upgrade on a non-git temp project with the `apply()` catch removed. It becomes a permanent regression test (SC-001).
- **Alternatives**:
  - `apply()`-raise as `failed`, without a flag. Rejected: it reports a failure for a migration that simply does not apply outside a repository.
  - A gate-only pin. Rejected as the weakest option.
  - A runner-side id list. Rejected: the fact would live apart from the migration.
- **Ledger**: the ClassVar edit changes each flagged module's `content_hash`, which shows up as audit-only drift (`ledger.py:257`). It is accepted and documented.

## #6540 + #6542: language settlement

- **Decision**: a new `charter.activation.language_settlement` module. It imports `language_authority` and `evidence.code_reader` at module level.
  - It holds: `LanguageSettlement`, `parse_language_answer`, the ask loop, the notices, the non-interactive decision and `settle_project_languages`, which becomes pure.
  - A new `store_language_settlement` does the write.
  - `interview.py` stores the settlement immediately after `write_interview_answers`. Operator decision `interview_language_write_order`.
- **Evidence**:
  - `code_reader.py:16` imports from `language_authority`.
  - `language_authority.py:449-451` has the uncommented deferred import.
  - `settle_project_languages` (:512-543) writes on both the interactive (:542-543) and non-interactive (:495-509) paths.
  - `interview.py` settles at :310, before the question loop (:316-388), and writes the answers at :420-421.
- **Pins to update**:
  - `tests/architectural/test_charter_activation_api_reexport.py:50-52`;
  - `test_language_excluded_dirs_cover_agent_dirs.py:15`. `EXCLUDED_DIRS` stays in `language_authority`.
- **Alternative**: inject a detector callable into `language_authority`. Rejected: the authority would still own the write side, and the operator's write-ordering decision needs the decide/write split anyway.
- **Write ordering**: the answers file is written before `config.yaml`. A `config.yaml` failure is surfaced, never swallowed. The two files are not written atomically; that is out of scope.

## #6541: LANGUAGES on the seam

- **Decision**: `LANGUAGES` only (operator decision `seam_language_catalog`).
- **Evidence**:
  - `offering/api.py` `__all__` (:69-80) has no language symbol.
  - `language_catalog` has no `DISPOSITION` entry (`test_doctrine_census.py:120`).
  - A `PUBLIC` symbol needs a facade re-export (`test_every_public_symbol_is_routed_through_a_facade`).
  - ADR 2026-10-03-1 and 2026-10-16-1 call the seam frozen, so an amendment note is needed.
- **Out of scope**: the corpus lives in spec-kitty-charter (ADR 2026-10-03-1:403). A case is filed against epic #6099.

## #6543: reconcile test gap

- **Evidence**:
  - `reconcile._classify_conflicts` (:671-707) uses `validation_gate.below_project_base` → `_with_shipped_endpoints` (:141-168).
  - The shipped-endpoint folding is tested only at the gate (`test_styleguide_reach_only.py:201`).
  - The reconcile tests cover only the org base (`test_synthesize_reconcile.py:631`, `:649`).
- **Decision**: add a positive and a negative case to `test_synthesize_reconcile.py`.
