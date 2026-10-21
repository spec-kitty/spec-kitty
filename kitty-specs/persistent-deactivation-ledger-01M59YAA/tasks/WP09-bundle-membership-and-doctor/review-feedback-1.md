# WP09 review cycle 1 - changes requested

Reviewer: claude (reviewer-renata). Base 73adc047, head 7a92bcc6.

What holds, verified: `tracked_files` is unchanged, so the rc35 migration and `charter generate` are unaffected. The ledger-less digest equals the base. I checked this by running the same fixture in a 73adc047 worktree: `sha256:4df8c0cc...` on both, and only head changes it when a ledger is present. An unreadable ledger gives `None`. The filename comes from `ACTIVATION_LEDGER` and no new literal or allowlist row was added. The validate, freshness and state-contract changes add fields and remove none. `ledger_findings` catches the error once and keeps earlier findings. `required_not_in_force` is the one reader behind both doctor and `charter list`, and the JSON key appears only when it has entries. Doctor RC wiring is correct. The 7 re-pinned rows in `test_remediation_effectiveness` are genuine shifts of the `remediation=` lines (+11/+14/+35). The 4 mypy campsite fixes are in touched files, so they are in scope. The dogfood restamp matches a fresh recompute. The 9 `REQUIRED_OMITTED_BY_ALLOW_LIST` warnings in this repo are genuine: 7 procedures and 2 toolguides that `packs/internal/org-charter.yaml` requires are missing from `.kittify/charter/activation.yaml`'s explicit lists.

## Findings

1. [MEDIUM] tests/doctor/test_doctor_activation_ledger.py:191-215 - The deny-warning tests assert only that a finding is present. None checks in the same fixture that a deny which should not trigger the finding is left alone. Two mutants survive the whole file (17/17 pass):
   - (a) `activation_ledger.py` `_deny_kind_findings`: `unknown = tuple(denied)`, so every deny is reported as `DENY_UNKNOWN_ID`.
   - (b) `_requiring`: `if True:`, so every deny is reported as `DENY_REQUIRED_ID` whenever any floor exists.

   Either bug would show users real exclusions as "stale, remove by hand". Required fix:
   - Add a known, non-required deny next to the unknown or required one in the same fixture. For example, deny `_OTHER` together with `no-such-directive`, and `_OTHER` together with `_REQUIRED_STEM` under the `acme` floor.
   - Assert that `_OTHER` is in no `DENY_UNKNOWN_ID` or `DENY_REQUIRED_ID` finding's `ids`.
   - Give `DENY_SELECTED_ID` the same treatment: deny two ids, select one, and assert that only the selected one is reported.
2. [LOW] src/charter/activation/activation_ledger.py:1205-1226 and 1001-1018 - Each org-requirable kind's floor is read up to three times:
   - `_require_floor_readable` reads it with `read_org_required_tokens`;
   - `required_not_in_force` reads it again per present allow list (`read_org_required_provenance`);
   - `_deny_findings` reads it again per deny kind.

   There is no cache, which contradicts traces/design-decisions.md ("read strictly once"). Required fix: read provenance strictly once per org-requirable kind into a mapping and pass it to the omission and deny helpers. The readability probe then comes for free. Otherwise, correct the trace claim.
3. [LOW] src/charter/activation/activation_ledger.py:1040-1050 `_legacy_keys_by_file` - The tolerant-mode fallback copies the kernel's `_legacy_keys_present` candidate scan (config.yaml plus the pointed charter.yaml), which gives a second copy of that rule. Required fix: take the per-file keys from one kernel helper (expose `legacy_keys_present(repo_root, legacy_keys)` from `kernel.activation_ledger_store`, or have the resolver carry `unmigrated_keys` on its tolerant LEGACY answer). If the kernel is out of scope here, record the duplication as a carry-forward note for WP14.
4. [LOW] tests/architectural/test_remediation_effectiveness.py:657-659 - The lineage comment still ends at the charter-pack-cutover re-pin. Required fix: add one sentence for this WP09 re-pin (517->528, 523->534, 604->618, 610->624, 715->750, 746->781, 759->794).

Not counted against WP09:
- The known WP08 red in `test_json_contract_enumeration`, which is assigned to WP10.
- 17 failures in `tests/acceptance/charter_pack_cutover/test_{upgrade_migration,rename_skills_glossary,promotion}.py` and `test_resynthesize_and_hotpath.py`. The same failure set also fails on base 73adc047, so these are pre-existing.

The timing tests are not vacuous. The context arm asserts that the denied id is not served, and the deactivate arm asserts that the pre-existing deny is kept. Expect the deactivate ratio to sit near 1, because both arms write a deny list.
