# Grounding: #6527 local slice (+ #6433, #6435)

Repo `/home/user/spec-kitty`, root checkout (HEAD be106ab4 on `issue-6457-activate-output-identity`, base origin/main 581b5c46). Read-only. Experiments live in
`/tmp/claude-0/-home-user-spec-kitty/a2f65514-bbcc-5e59-8af7-d2f7cbbf45c4/scratchpad/exp/` (e1..e8.py), run with `.venv/bin/python`.
Tags: **[V]** = verified by running code; **[C]** = read from code; **[I]** = inferred.

Issue #6527 (read via GitHub): local acceptance = "Every stored activation list holds stems only (test over all writers)"; the inputs accept a declared id or a URN; presets are normalised to stems; compile and the consistency check go through `IdentityIndex` (#6433); the effective-set union stops mixing spellings (#6435). ACL `to_contract` and `activation_invalid` belong to #6520 (out of scope).

---

## 0. Root cause in one line

`effective_set._resolve_one` (src/charter/activation/effective_set.py:150-156) builds the union `_scanned_ids` (file **stems**, via `pack_manager.list_available_detailed` → `_config_stem`, pack_manager.py:1393) **∪** `_service_ids` (service mapping keys = **declared ids**, effective_set.py:134-139) for every non-directive kind. `_fallback_ids` does the same (effective_set.py:195-208). Every writer that seeds an absent key from this set therefore stores **both** spellings of an org/project artifact whose stem ≠ id. [V e1: toolguides 20 entries for 19 artifacts, the extra one is `acme-tool-id`]

Built-in non-directive artifacts all have stem == id today, so only org/project artifacts show the defect. [V e1: 0 non-stem entries for built-in tactics, styleguides, paradigms, procedures and agent profiles] Directives are scan-only (stems). [C effective_set.py:154]

The historical reason for adding the service keys is #4399 MAJOR 2: the resolver filtered by plain declared-id membership (tests/charter/test_activation_preserves_effective_4253.py:249-268). That reason is gone: `resolver._gated` (src/charter/activation/resolver.py:217-243) now maps every token through `IdentityIndex.activation_id`, so a stored stem gates correctly. [C]

---

## 1. Writer inventory (`activated_<kind>` / `deactivated_<kind>`)

| # | Writer | file:line | Stored spelling today | Evidence |
|---|---|---|---|---|
| W1 | `charter activate <kind> <id>` (explicit id) | pack_manager.py:1009-1128, `_identity_normalised` :949-972 | **stem**: a declared id becomes its stem (#6423, shipped); a present list is collapsed to stems in place when any entry is not a known stem | [C] + tests/specify_cli/cli/commands/charter/test_activate_declared_id_identity.py:52-90 |
| W2 | activate, absent-key materialisation (`_preservation_ids`) | pack_manager.py:482-510 (`return sorted(effective.ids)` :500; fallback `sorted(effective.fallback_ids \| available)` :501) → engine `_materialise_absent` activation_engine.py:299-317 | **MIXED**: a stem≠id org or project artifact is written twice | [V e1] org toolguide: list holds `acme-tool-file` **and** `acme-tool-id`. [V e7] project tactic: `proj-tac` and `proj-tac-id` |
| W3 | activate `--only` (`_narrow_inputs`) | pack_manager.py:581-619 → `plan_narrowed_list` activation_engine.py:331-347 | **stem**: base from `org_required_stems` (org_charter.py:354-379); `previous` and the id are mapped through `IdentityIndex.stem` (:616-619) to compensate for the mixed effective set | [C] + test_activate_only_6408.py:86 |
| W4 | cascade activate | specify_cli/cli/commands/charter/activate.py:297-329 → `manager.activate` per target. The id comes from `drg_urn_to_config_id` (_cascade_shared.py:55) | stem for the target; **MIXED** when the target kind's key was absent (goes through W2) | [C] |
| W5 | `charter deactivate` (and cascade deactivate, `record_exclusion=False`) | pack_manager.py:1130-1219, `_deactivation_inputs` :923-941, `plan_deactivation` activation_engine.py:513-571 | **stem** written to `deactivated_<kind>`. Allow-list removal matches stem + declared id (`also_matches`). An absent allow key is never materialised | [C] |
| W6 | presets `charter activate --preset` | preset_application.py:616-659 (`_target_state` :505-515, `_union` :494-502, `_org_required` :478-491), write `_write` :702-708 | **verbatim**: listed ids keep the preset author's spelling, and the org `required_*` ids are unioned **unnormalised** (declared ids). `--force` deny clearing (`_cleared_deny` :585-588) is stem-aware | [V e4] an org preset listing `DIRECTIVE_024` stored `activated_directives: [DIRECTIVE_024]`; `activated_toolguides: [gherkin, acme-tool-id]` (org-required declared id). Built-in presets list stems (packs/built-in/presets/minimal.yaml) |
| W7 | interview promotion `_promote_interview_selections` | specify_cli/cli/commands/charter/interview.py:113-215 | selections → stems (`resolve_selected_id_to_stem`). An absent key is seeded from the effective set → **MIXED** without `--narrow-activation`. With narrow → stem (compensated by `_stem_spelled_effective` :64-81 and `_stem_spelled_config` :84-100) | [V e3] non-narrow: `activated_tactics` 123 entries (121 built-in + `qa-tactic-seven` + `qa-seven`); narrow: stems only |
| W8 | org-required union `_promote_org_required_to_config` (via `apply_org_charter_to_interview`, org_charter.py:961) | org_charter.py:404-492; promoted ids normalised by `_normalize_required_ids` :294-340; seed `_effective_sets_for_absent_keys` :382-401 | promoted ids: stem, or kept raw when unresolvable. Seed: **MIXED** | [V e2] `activated_toolguides` 20 entries, holds `acme-tool-id` |
| W9 | `promote_activations` primitive | activation_engine.py:780-876, `_plan_promotion` :715-777 (absent seed `sorted(effective.ids)` :755) | passes through whatever callers and the seam give it (no normalisation of its own) | [C] |
| W10 | reach-only synthesiser append | synthesizer/reach_only.py:265-327 (`_promote`, `effective_sets={}`, present keys only) | slugs of created artifacts; **stem** [I: slug = file stem of the synthesized artifact; not run] | [C] |
| W11 | migration `4.0.0rc8_promote_interview_selections` | specify_cli/upgrade/migrations/m_4_0_0rc8_promote_interview_selections.py:180-360 | **stem**, present keys only, built-in-only `_StemResolver` (:135-153). Never seeds an absent key | [C] |
| W12 | `m_unify_charter_activation` | m_unify_charter_activation.py:273-283 | superseded shipped migration (recorded no-op through `SUPERSEDED_MIGRATIONS`). Historical writes were MIXED [I]. Do not edit (DIRECTIVE_044) | [C] |
| W13 | ledger move `4.0.0rc8_activation_ledger` | activation_ledger.py:965-990 `apply_ledger_migration` | **verbatim copy** of the legacy lists (preserves whatever spelling was stored) | [C] |
| W14 | cutover reset | specify_cli/upgrade/migrations/_charter_pack_cutover_resets.py:235 | removes keys only | [C] |
| W15 | init / `provision_default_mission_type_activations` | init.py:1412-1419 → compiler.py:699-712 | only `mission_type_activations` (no stem/id split) | [C] |

**Summary of non-stem writers:** W2 (and W4 through it), W6, W7 non-narrow and W8 store declared ids. W3 and W7-narrow already compensate locally. W13 propagates historical content.

---

## 2. Reader / resolver inventory

`IdentityIndex` (src/charter/activation/identity_index.py) behaviour [V e5]:

| Input | Result |
|---|---|
| stem | `stem()` → itself; `declared_id()` → declared id |
| declared id | stem / declared id |
| directive normalised id | accepted (:241-242) |
| URN (`directive:DIRECTIVE_024`) | **None**: URNs are NOT accepted today |
| unknown token | None. `activation_id()` warns and keeps (:311-325) |

**Blind spot [V]:** built-in `mission_step_contract` files (`packs/built-in/missions/built_in_step_contracts/*.step-contract.yaml`) are indexed by neither `IdentityIndex` nor `resolve_artifact_urn`. `kind_vocabulary._built_in_scan_dir(MISSION_STEP_CONTRACT)` returns None. `list_available` does find them (21 entries).

### `resolve_artifact_urn` (kind_vocabulary.py:421-496)

- stem → URN.
- declared id → URN (non-directive `_declares_id`; directive round-trip through `resolve_config_id`).
- URN input → **raises**.
- unknown → **raises** `UnknownArtifactIdError`. [V e5]

### Call sites

| Site | What it does | Unknown token |
|---|---|---|
| compiler.py:186-188 `_resolve_config_activated_ids` (#6433) | stem / declared id → bare id | raise → re-raised with the activation store named (:297-303). **Compile fails**. URN entry also fails [V e5] |
| consistency_check.py:791 forward parity | resolve; only `org_roots` (no project layer) | skipped (`continue`) |
| consistency_check.py:860 graph-kind parity | same roots | `verification_errors` |
| drg_activation.py:337-346 | `IdentityIndex.declared_id` first, then `resolve_artifact_urn` fallback | skip (by design: "this gate must never raise") |
| preset_application.py:365-382 `_artifact_id_resolves` | stem / declared id / directive id accepted | the preset refuses (`PresetIdUnresolvedError`), which is correct for an input surface |
| activate.py:155-186 `_source_urn` (cascade source) | resolve | returns None |
| deactivate.py:107, :153 | resolve | returns None |
| _resynthesis_preflight.py:64 | resolve | raises |
| kind_vocabulary.py:573 | internal round-trip | — |

The runtime gate `resolver._gated` (resolver.py:217-243) maps every token through `IdentityIndex`; an unknown token is warned and kept. This is the operator-chosen model for compile and the consistency check.

### Consistency check defects (beyond #6433's call sites)

- `_collect_all_offering_ids` (consistency_check.py:380-405) uses `list_available(..., org_root_chain=...)`. That returns **stems only** and covers **no project layer**. `_check_unknown_references` (:422-437) then compares the stored tokens raw. [V e6] A declared id the writer W2 itself stored (`acme-tool-id`) is reported as `unknown_references`. [V e7] Both spellings of a **project-layer** artifact are reported as unknown_references **and** as verification_errors, because the 791/860 calls pass no `layer_roots`.
- `_check_reference_id_reverse_parity` (:805-831) compares compiled paradigm **declared ids** with stored paradigm **stems** raw [C]. This is a false positive for an org paradigm whose stem ≠ id.
- An unknown token is reported twice (unknown_references + verification_errors) [V e6].

### Activate input

A URN is refused [V e6]: `manager.activate(ctx, "toolguide", "toolguide:gherkin")` raises `UnknownActivationIdError`, and the same holds for directives. Deactivate behaves the same [I: `_deactivation_inputs` uses `IdentityIndex.stem`, which returns None for a URN].

### Effective-set consumers

| Consumer | Location | Compensates? |
|---|---|---|
| pack_manager `_preservation_ids` | :498 | no → W2 |
| pack_manager `_narrow_inputs` | :616-619 | yes |
| org_charter `_effective_sets_for_absent_keys` | :397 | no → W8 |
| interview | :196-199 | narrow path only (`_stem_spelled_effective`) |
| `_resynthesis_preflight._future_selections` | :30-56 | no; comparison only, not a write [I harmless] |
| `m_4_0_0rc8._seeded_list_hints` | :195-215 | via the built-in-only `_StemResolver`, so the org spelling is not collapsed [I: minor; hint only] |
| activation_engine `_plan_promotion` | :744-755 | no |
| activation_engine `_skipped_ids` | :910-915 | no |

---

## 3. #6435 concrete defect (experiment e1/e2/e3/e7)

Fixture: org pack `acme` with `toolguides/acme-tool-file.toolguide.yaml` declaring `id: acme-tool-id` (the same fixture as test_activate_only_6408.py:28-41).

- `resolve_effective_sets(root, ["activated_toolguides"])` → `resolved=True`, 20 ids for 19 distinct artifacts. The only non-stem entry is `acme-tool-id`; `acme-tool-file` is present too. [V]
- `ActiveCharterManager().activate(ctx, "toolguide", "gherkin")` on an absent key writes both `acme-tool-file` and `acme-tool-id`. [V]
- The org-required union (W8) and the non-narrow interview (W7, tactic `qa-tactic-seven`/`qa-seven`) store both spellings the same way. [V]
- Project layer: tactic `proj-tac`/`proj-tac-id` → both stored. [V e7]

Compensators to delete or simplify once the seam emits stems:

- `pack_manager._narrow_inputs` stem mapping (:602-619; docstring :590-594 says so explicitly).
- `interview._stem_spelled_effective` (:64-81). `_stem_spelled_config` (:84-100) still matters for present lists holding legacy declared ids.
- The DenySet three-spelling membership (activation_ledger.py:274-306) is tolerant by design. Keep it.

---

## 4. Tests: carve-outs to re-pin, and coverage to reuse

### Re-pin (they encode the mixed spelling)

- tests/charter/activation/test_effective_set.py:119-124 `test_procedure_whose_id_differs_from_its_stem_appears_in_id_spelling`: asserts `ORG2_PROCEDURE_ID` (`acme-release-procedure`) ∈ ids. Re-pin to the stem `release-procedure` and assert the declared id is absent (mirror :107 for directives). The fixture constants are at :31-34.
- tests/specify_cli/cli/commands/charter/test_activate_only_6408.py:
  - :93 `... and a != _ORG_ID`
  - :128 `set(available) <= set(written) | {_ORG_ID}`
  - :157 `available_other - {_ORG_ID}`

  These become "no `_ORG_ID` anywhere in the written list". Note: `_available()` there is built-in-only (`list_available` with no roots), so the carve-outs are about the extra declared id being written, not about availability.
- tests/specify_cli/cli/commands/charter/test_activate_stem_writes_stem.py:48-51: the comment "the materialised effective set may also list the org tactic by declared id". Tighten to assert `qa-seven` ∉ the list. The module docstring :4-5 is also stale ("refused today ... strict xfail against #6423"; that test is no longer xfail).
- tests/specify_cli/cli/commands/test_charter_interview_promotion.py:327: tests `_stem_spelled_effective` (declared → stem). It becomes redundant or needs a re-pin if the helper is removed.

### Keep as regression guards (must stay green unchanged)

- tests/charter/test_activation_preserves_effective_4253.py:249-268: asserts the **service output** (`_effective_procedures` :216-219) keeps the stem≠id procedure after activation. It must keep passing with stems stored; it proves the gate resolves stems.
- tests/acceptance/charter_pack_cutover/_effective_set.py measures the service keys (runtime). It is unaffected by the stored spelling [I]. Do not edit (digest-pinned, :3-6).

### Reuse

- tests/charter/activation/test_identity_index.py
- test_deny_identity_space.py
- test_activate_declared_id_identity.py (#6423)
- tests/charter/org_pack_identity_support.py and test_directive_identity_mapping.py
- test_drg_activation_gate.py, test_resolver_directive_activation_keying.py
- tests/charter/test_consistency_check.py, test_compiler.py
- tests/charter/presets/
- tests/charter/skill_pack_support.py, tests/_factories/activation_ledger.py
- The e1/e4/e6/e7 fixtures above. They are small, and adding a **project-layer** stem≠id artifact catches the consistency-check layer gap.

---

## 5. Minimal design proposal (no code), tidy-first sequence

**T0 (tidy, no behaviour change).** Add URN acceptance to `IdentityIndex._lookup`: strip a `"<kind.value>:"` prefix when it matches the kind. This one place gives every input surface URN support (activate and deactivate already go through `IdentityIndex.stem`). Add unit tests in test_identity_index.py.

**T1 (#6435, the seam).** In `effective_set._resolve_one` and `_fallback_ids`, emit stems: map service keys through `IdentityIndex.stem(kind, key) or key`, or drop `_service_ids` entirely because the scan already covers every service key after stem mapping [V e8: zero service-only keys for every kind]. Prefer mapping over dropping, so a service-only artifact cannot disappear (fail-safe). Update the module docstring (:20-26) and the `EffectiveSet.ids` docstring (activation_engine.py:691-693, "in the spelling the activation filter compares against" → "activation stems"). This alone fixes W2, W4, W7 and W8. Then delete the `_narrow_inputs` stem mapping and `_stem_spelled_effective` (or keep them as no-ops and delete in a follow-up).

**T2 (presets, W6).** In `plan_preset_application` / `_target_state`, normalise listed ids and org-required ids to stems through the `IdentityIndex` that is already built (:629). `_union` already de-duplicates by `lookup_key`. Store `identity.stem(kind, x) or x`. Anti-patterns and mission types are unaffected.

**T3 (#6433, compile).** `compiler._resolve_config_activated_ids` (:146-189) should resolve through an `IdentityIndex` built from the same roots (`IdentityIndex.build(repo_root, org_roots=...)`, or `from_pack_context`), with `activation_id`-style **warn-and-keep** for unknown tokens instead of raising. This is the operator decision. It retires the raise at :297-303. **This is a behaviour change**: today an unknown stem fails compile. Existing tests asserting the C-006 "raise, never silently drop" contract (docstring :174-178) need re-pinning; keep is not drop, so C-006 still holds. Thread the index in, because `_resolve_config_activated_roots` calls this 7 times.

**T4 (#6433, consistency check).** Use one `IdentityIndex.build(repo_root)` (which covers the project layer) for:
- `_check_unknown_references` (known = `index.knows`);
- forward parity (:791);
- graph-kind parity (:860);
- reverse paradigm parity (compare `index.stem(ref_id)` against stored stems).

Unknown tokens warn (report) and are kept. Drop the double report of an unknown token from verification_errors, or keep it per the operator rule (decision below). This also fixes the verified project-layer false "unknown" and the self-inflicted declared-id "unknown".

**T5 (drg_activation / preset fallback cleanup).** The `resolve_artifact_urn` fallback in drg_activation.py:343 and preset_application.py:374 exists only for tokens the index misses. After T0, the only remaining misses are the step-contract blind spot and real unknowns. Remove the fallbacks only after the blind spot is fixed (see risks below); otherwise leave them.

**T6 (acceptance test).** An "all writers store stems" test, parametrised over W1-W3, W4 (cascade), W5 (deny), W6 (preset incl. org-required), W7 (both modes), W8 and W11, on an org **and** a project stem≠id fixture plus a built-in directive (`024-locality-of-change`/`DIRECTIVE_024`).

### Decisions and risks to flag to the operator

1. **Stored content of existing projects (migration question).** Projects that already hold mixed or declared-id lists (from W2/W6/W7/W8, carried by W13) keep them. Readers stay tolerant (gate, DenySet, the IdentityIndex-based compile and check). `_identity_normalised` collapses a present list opportunistically on the next `activate` of that kind (pack_manager.py:964-971). A normalising migration would rewrite stored content: needs an operator decision, and clone_local_effect=False (ledger tracked). "Every stored list holds stems only" is strictly about new writes unless the operator wants the migration.
2. **Compile behaviour change.** An unknown token stops failing compile and becomes warn+keep (T3). The operator already ruled warn-and-keep; confirm that the compile exit code and `UnknownArtifactIdError` surfacing (CLI messaging) change accordingly.
3. **Directive id-first vs stem-first.** `IdentityIndex.stem` is id-first for directives (:265-268) and refuses ambiguous stems (`_representable_stem` returns None). With `or token`, an unrepresentable directive id is stored raw. Today `org_charter._normalize_required_ids` instead *skips* it with a warning (:332-336). Pick one rule.
4. **Step-contract blind spot [V].** `IdentityIndex` and `resolve_artifact_urn` both miss built-in `mission_step_contract` files. With warn-and-keep in compile/check, any stored step-contract id would warn. The compiler does not read step contracts (ConfigActivatedRoots has no field), but `_check_unknown_references` iterates every `YAML_KEY_MAP` kind. Today's check uses `list_available`, which does see them. Either fix `kind_vocabulary._scan_roots` for step contracts or keep `list_available` as an extra known-set for that kind.
5. **URN storage.** T0 accepts URNs on input; writers must store `stem`, never the URN. `deny` already uses DenySet URN membership.

### Complexity hotspots (C901 ceiling 15)

Measured with ruff at threshold 9 [V]:

| Function | Location | Score | Note |
|---|---|---|---|
| `_promote_interview_selections` | interview.py:113 | 10 | removing the narrow compensation lowers it |
| `apply_org_charter_to_interview` | org_charter.py:910 | 11 | not touched by the plan |
| `_render_directives` | compiler.py:2221 | 10 | not touched |

Everything else touched is ≤9. `pack_manager.py` is 1442 lines, but `activate` stays ≤9.

### Concurrency note

Another agent is editing `pack_manager.py`, `activation_engine.py` and `activate.py` (output text). T1 touches `pack_manager._narrow_inputs` (deletion only) and docstrings in `activation_engine.py`. Sequence T1's pack_manager deletion after that work lands, or keep it in a separate commit.

---

## 6. Related history

- Shipped in base: #6423 (declared-id `activate` writes stem; `_identity_normalised`, `_collapse_spellings`, `also_matches` in deactivate; tests test_activate_declared_id_identity.py); #6406 (`IdentityIndex.lookup_key`, drg_activation identity-first); #6408 (`--only`, `_narrow_inputs`, interview narrow); #6629 (rc8 interview migration never seeds an absent key).
- `git log origin/main -400` shows no commit referencing #6433/#6435/#6527 [V]. No open PR was checked beyond the issue read.
- #6527 is open, claimed, milestone 4.0.0. #6520 holds the ACL `to_contract` / `activation_invalid` part.
