# WP25 review feedback: cycle 1

**Reviewer:** architect-alphonso (claude), 2026-10-09
**Reviewed:** lane-y at 220bb317 (head b3556b3a), diff `444f7a5a..220bb317` (100 files)
**Verdict:** rejected (changes requested). One blocking item: a red gate. Everything else passes review.

## Blocking

### B1. `tests/architectural/test_no_manual_global_state_mutation.py::test_no_unallowlisted_sites` is red. A red gate cannot ship in the PR.

It flags three sites in the acceptance suite:

- `tests/acceptance/charter_pack_cutover/generate_golden_before.py:85` `_isolated_home` assigns to `os.environ[...]`.
- `tests/acceptance/charter_pack_cutover/test_gates_latency_messaging.py:53` `load_gate` assigns to `sys.modules[...]`.
- `tests/acceptance/charter_pack_cutover/test_project_pack_root.py:29` `load_module_by_path` assigns to `sys.modules[...]`.

WP25 did not cause this. I ran the gate at the lane base `444f7a5a` and it is red there too (1 failed, 43 passed). WP01 introduced all three sites, on lane-a: `e83018e2` and `a80e8ecd` for `generate_golden_before.py`, and `3da251d3` for the other two. The target branch has none of these files, so the mission introduced the red. WP25 is the closeout WP and the fix is small, so it goes to this rework (a closeout follow-up in a WP01-owned file; log it):

- `_isolated_home`: use `unittest.mock.patch.dict(os.environ, {...})`. Delete the keys that were unset, as today.
- `load_gate` / `load_module_by_path`: the module only needs to be in `sys.modules` while `exec_module` runs, so `dataclasses` can resolve it. Wrap that call in `mock.patch.dict(sys.modules, {spec.name: module})`. Alternatively, add an allowlist row in the shard YAML that owns these files, with the rationale; the gate supports that. Do not add a blanket suppression.
- Show the gate green afterwards, and confirm the acceptance suite stays 0 failed / 0 xfailed / 0 xpassed.

## Non-blocking (fold into the same rework)

- N1. `src/charter/activation/manifest_loader.py:238`: the docstring example still says `"doctrine/software-dev/expected-artifacts.yaml"`. The label is now `built-in/...`. Update it so docs and code match.
- N2 (advisory). `_FILE_FLOOR = 2392` follows WP01's acceptance rule (`--no-renames`), so it is legitimate. With rename detection only 15 of the 67 deletions are real deletions, which would give a floor of 2444 against 2455 scanned. Tightening is optional and not required. If you tighten it, keep the WP01 acceptance computation unchanged.

## Verified (no action)

- **FR-018 gate.** The 25 tokens match the spec's closed list exactly: 10 prose tokens, the `spk-doctrine-` prefix, 5 folded skill ids and 9 identifiers including `doctrine_pack_id`. The exemptions are the spec's FR-018 list plus the two ratified ones: the glossary pack by file, and the retrieval index by section. `FORBIDDEN_SCAN_ROOTS` does not include `packs/built-in/glossary_packs/`, so the explicit glossary-pack exemption is needed. The archive rule excludes nothing outside the historical prefixes. The live run scanned 2455 files (src 1514, packs 556, docs 351, workflows 20, agent copies, CLAUDE.md, AGENTS.md, Makefile) and found 0 hits.
- **Non-vacuity checks I ran.**
  - Removing a token from `_PATTERNS` leaves its planted file unreported, so that token's planted test fails.
  - Planting `doctor doctrine` in a copy of a real living file (`src/specify_cli/cli/commands/doctor.py`) is reported.
  - On the live CHANGELOG, 10 of 93 Unreleased entries are `Charter pack cutover:` entries and are exempt (30 exempt lines carry tokens). The other 105 Unreleased lines are scanned.
- **Floor provenance.** WP01's helper measures 2459 at `fcf7a827`. 67 living files were deleted under `--no-renames`, giving 2392. This is not derived from the gate's own scope function.
- **FR-014 (T112).** I re-measured every pin at HEAD with the base module's literals: D1 75→72 (+3/−6), D2 54→52 (+2/−4), PROFILE_UNREACHABLE 56→54 (+2/−4), PROFILE_RESCUES 26→25, spread 23→20. All of these match the docstring. FR-014 allows deletion when each deletion is listed with its reason, and every deletion is reasoned. Nothing remaining references `default.yaml`, `default_pack` or `charter_pack_registry`.
- **Facade gate.** The key moved to `charter.offering` prefixes. The planted `functools.wraps` wrapper is reported. All 14 newly tabled re-exports pass the identity table test.
- **batch-api-contract §8.** Marked historical. `sync_publish` raises in both `saas_service.py:646` and `local_service.py:286`, and `service.py` only delegates.
- **Test renames.** 218 tests collected at both base and head. No stale references remain outside the historical roots.

## Commands run (shared clone at b3556b3a)

- `pytest tests/acceptance/charter_pack_cutover -n 4 --dist loadfile -k "not nfr003"`: 352 passed, 1 skipped, 0 failed, 0 xfailed, 0 xpassed. The nfr003 test, run with `-n0`: 1 passed.
- I ran 15 gate files together: FR-018, FR-016, facade, census, lifted retirement, dead doctrine paths, kind vocabulary, boundary, legacy terminology, dead modules, ruff-format, shard registry, gate selection, CI collection, and global-state. I also ran the `4836` gates, reachability, template resolver, repository and `tests/upgrade/migrations`. Result: 979 passed, 3 skipped, **1 failed** (`test_no_unallowlisted_sites`, see B1).
- The global-state gate at lane base `444f7a5a`: 1 failed, 43 passed (it was already red there).
- `make test-fast`: 2281 passed, 8 skipped.
- `ruff check .`: clean. `ruff format --check .`: 3450 files formatted.
- mypy on the 47 changed src files: 52 errors at both base and head, identical sets, so 0 new. `mypy --strict` on the new gate: clean.
