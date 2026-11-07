# Research

The research input is the 2026-11-07 research squad debrief (reproduced every node RED on `origin/main` `13f873afb7`):

- #7177, #7178, #7111: research-A
- #7181, #7182: research-B
- #7183 (five sub-items, six nodes): research-C

These files live in the operator's scratchpad, not in the repository. The decisions they support are restated here so the Mission stands alone.

## Decisions

| Issue | Decision | Rationale | Alternatives rejected |
|---|---|---|---|
| #7177 | Add `--dependency-ref` to `EXPECTED_PARSER_LONG_FLAGS` | #6771 (`9c2881c6`) added a visible repeatable flag; the golden is a hand-maintained strict set | Editing the historical kitty-specs contract doc (drift, not a living pin) |
| #7178 | New `checkout_file_recipe` in `_git_remedies.py`; notice uses it via deferred import | Gate is correct, allowlist stays empty; checkout semantics are required by the `staged_differs` and `index_only` branches | `restore_recipe` (drops staged edit; fails index-only); allowlist entry (forbidden) |
| #7111 | Seed the `migration:` actor in-process with `build_system_actor` (role `system`); keep three seed predicates | #6754 (`f22a7b6275`) refuses caller-supplied seeds; refusal already covered elsewhere | Asserting the refusal here (redundant, orphans the stored-whole pin) |
| #7181 | Re-pin to `{ok:false,error:{code,message}}`; unparseable-yaml test asserts exit 1 `ACTIVE_CHARTER_CONFIG_INVALID` | #6557 (`9bee2389`) typed envelope + soundness gate before freshness | Deleting the test (loses the integration guard) |
| #7182 | 6 nodes: seed PRESENT empty lists via `seed_activation_ledger`; 2 nodes: assert the file-name-collision refusal in the interview's `_emit_error` JSON | #6685 (`09bca55275`) absent key stays implicit; `a8dd1812` collision refusal | Using the status envelope for the interview (would go red) |
| #7183 n1 | Assert the full four-key system actor | #6722 (`3c0a8f3453`) | Subset or `!=` check (weaker) |
| #7183 n2 | Add distinct `mission_id` in `_make_mission` | #5875 (`7634075bd5`) read-side residue | Tracking files in git instead (not the canonical identity shape) |
| #7183 n3 | Budget `2 + 4 x real`; file follow-up for the per-Mission cost | #6673 (`d8829074b7`) adds 4 git calls per real Mission | Raising the old constant blindly |
| #7183 n4 | Ignore `.kittify/runtime/locks` in both snapshots; assert the lock file exists | #6719 (`d4be7a1940`); same pattern as `test_activation_json_6525.py` | Unlinking the lock on release (races) |
| #7183 n5 | Drop the dead tracked-and-modified `kitty-ops/` clause; assert the Mission events file tracked-modified and `?? kitty-ops/lifecycle/` untracked | #7003 (`8f3149ae5b`) one file per record | Including untracked files in the `modified` query (weakens the discrimination) |
