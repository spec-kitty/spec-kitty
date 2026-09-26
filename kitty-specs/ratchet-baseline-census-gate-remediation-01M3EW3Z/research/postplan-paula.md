# Post-plan brownfield squad — Paula Patterns (split-brain / dual-authority / decomposition)

Mission `ratchet-baseline-census-gate-remediation-01M3EW3Z` · HEAD `5940b8ca` · read-only.

## Governance applied
- **Profile `paula-patterns`** (architecture-scout). I checked for boundary leaks, ownership confusion and whack-a-field risk. I separated must-fix-in-plan items from follow-up issues and wrote no code.
- **Directives:** profile refs 001, 003, 030, 032 and 041, plus the plan-action set. The load-bearing ones are DIRECTIVE_044 (single canonical authority), DIRECTIVE_043 (gate discipline) and DIRECTIVE_041/DIR-041 (content anchoring).
- **Tactics:** `paula-patterns-architecture-scout-review`, `anti-corruption-layer` and `review-intent-and-risk-first`. The charter plan context itself resolved no tactic IDs.
- **Charter:** Standing Order #2 (campsite applies only to touched files), SO #6 (canonical sources), RECONCILE_CHANGE_SCOPE_TENSIONS, and paradigm `deep-module-design`.
- **Method:** one reviewer, one lens. Five-scout fan-out was not justified at post-plan.

## Findings

### Q1 — Second authorities

**[HIGH] `_content_identity.py` (research §B1) — it becomes the N+1th descriptor-allowlist matcher, not the shared one.**
Research names only `test_trio_seam_only.py` as prior art. The live tree already has at least seven hand-rolled "resolve descriptors, then check membership" matchers over `_ratchet_keys.ContentDescriptor`/`resolve_descriptor`, and every one uses **set or dict semantics**, which is exactly the widening hole §B1 fixes with a `Counter`:
- `_sole_door_scan.py:587-602 resolve_exclusion_keys` returns `dict[CompositeKey, ContentDescriptor]`. It is shared by the 2 sole-door gates and is functionally identical to the proposed `resolve_allowlist`, minus the Counter and the lazy error capture.
- `test_trio_seam_only.py:528-564` and `test_single_mission_surface_resolver.py:389-403` narrow keys to a 2-tuple `(qualname, token_line)`. That drops `rel_path`, so these two can cross-bless between files.
- `test_no_read_side_bypass.py:796,972` (`frozenset[CompositeKey]`) and `test_no_write_side_rederivation.py:174-218,743-857` use `in` over a set, with staleness through `descriptor_still_live`.
- The census `_destructive_op_census.diff_against_allowlist` (L189-200) is a set-difference partitioner.
- `untrusted_path_audit/audit.py` has `check_undercount`/`check_overcount`, another partitioner over `composite_key` plus `truncate_token`.

**Recommendation:**
- (a) State in `_content_identity`'s docstring that it is **the** partition/resolve authority for content-keyed allowlists. List the siblings above as known non-adopters, each with a follow-up issue (FR-019-style).
- (b) Have `resolve_allowlist` replace `_sole_door_scan.resolve_exclusion_keys`, or have that function delegate to it. It is the same operation. This needs a small edit in a file no WP owns: assign it to WP02 or a follow-up.
- (c) Put a sentence in `_ratchet_keys.py`'s module docstring pointing to `_content_identity` as the matching half. Its docstring already calls itself "the designated home every WS1 gate imports", and WP07 is editing that docstring anyway (see Q2).

**[MEDIUM] `_destructive_op_census.diff_against_allowlist` / `drop_one_entry` (§C2) vs `_content_identity.partition_findings` — two partitioners for one concept (DIRECTIVE_044, C-004 spirit).**
§C2 generalises the census diff over `Hashable` while §B1 adds a Counter partition. `CensusKey.occurrence` makes census keys unique by construction, so `partition_findings` degenerates exactly to the set diff.
**Recommendation:** WP04 (which already depends on WP02) re-implements `diff_against_allowlist` as a thin call to `partition_findings`, or deletes it and calls the helper directly. The stale *policy* (fail vs warn) stays at the caller, and that is the only real difference between the two families. This leaves one matcher and two policies.

**[MEDIUM] `occurrence` means two different things (terminology split-brain).**
- `ContentDescriptor.occurrence` is the ordinal among lines *inside the qualname whose token line contains the substring* (`_ratchet_keys._select_occurrence`, L209-221).
- `CensusKey.occurrence` is the ordinal among *findings sharing the full `(rel, qualname, token_line, op)`* (data-model L31).

Both fields show up on the same allowlist-reading screens, and the ban's keyword carve-out lists `occurrence` once.
**Recommendation:** rename the census field `ordinal`, or document both definitions side by side in data-model.md and the `_content_identity` docstring. Renaming is cheap now and costly after 80 literals exist.

**[LOW] Three textual serialisations of one identity:**
- the os-detect text line `rel::qualname::token_substring[::occ]` (§B4);
- the census diagnostic `rel::qualname::op#occ (line N) tokens=…` (§C1);
- the "content line to add" printed by the os-detect gate failure.

**Recommendation:** put one `render`/`parse` pair in `_content_identity` and have `_os_detection_exemptions` call it.

**[LOW] `_surface_resolution_scan.py` (WP07, §E1) keeps its own `CompositeKey = tuple[str,str,str]` (audit.py:91).**
`_ratchet_keys.py` L47-59 re-declares that alias only to avoid a circular import from audit.py. Once audit.py is a normal module that already imports `_ratchet_keys`, WP07 should `from tests.architectural._ratchet_keys import CompositeKey`, delete the duplicate alias, and rewrite the `_ratchet_keys` docstring rationale. This is cheap and WP07 owns both files.

**[MEDIUM] `test_ratchet_baselines.py` (§D2) — the hoist removes 2 of 5 hand registries and leaves 3.**
In the file today:
- `BaselinesFile` pydantic fields (4 names, L113-116);
- `_REQUIRED_TOP_LEVEL_KEYS` (derived, per plan);
- `_GRANDFATHERED_UNREGISTERED_KEYS` (pinned empty);
- `_REQUIRED_NO_DEAD_MODULES_CATEGORIES` (L154-165);
- `test_no_unregistered_baseline_keys_are_added` (top-level only).

The new both-directions `_yaml_leaves == _enforced_leaves` test subsumes the unregistered-key check at leaf granularity.
**Recommendation:** also derive `_REQUIRED_NO_DEAD_MODULES_CATEGORIES` from `_SIZE_RATCHETS`. Then retire `_GRANDFATHERED_UNREGISTERED_KEYS` and fold `test_no_unregistered_baseline_keys_are_added` into the leaf test, keeping the test name if any doc references it. Otherwise there are still two authorities for "what keys may exist".
**Concession:** no *other* module enforces `_baselines.yaml`. The 12 other hits (`_gate_coverage.freeze_baselines`, `test_layer_rules`, `test_egress_consent_boundary`, etc.) are prose, or belong to an unrelated E3 node-ID baseline, so the "single comparison table" claim holds repo-wide for this file. Per-gate inline ceilings such as `_BASELINE_EXCLUDE_COUNT` and `BASELINE_FUNCTIONAL_ASSERTIONS` are a distributed baseline authority outside FR-011. That is INFO only, a possible follow-up.

**[INFO / concede] The exemption text form vs Python descriptors is not split-brain.**
§B4 loads text into `frozenset[ContentDescriptor]` and resolves through the same substrate. It is one entity with a file serialisation (see the LOW item above on the serialiser).

### Q2 — WP boundaries

**[HIGH] WP04 and WP05 both edit `test_mutation_ownership_routing.py`; the plan claims exclusive ownership.**
- WP04 deletes the tree-based `_destructive_op_census.enclosing_qualname(tree, lineno)` and re-exports `_ratchet_keys.enclosing_qualname(source, lineno)`, a different signature (§C2).
- `test_mutation_ownership_routing.py` (owned by WP05) imports it at L72 and calls `enclosing_qualname(tree, lineno)` at L779 (`test_enclosing_qualname_is_available_for_diagnostics`). So **WP04's lane head is red** unless WP04 edits the WP05-owned file.
- Research §C2's own call-site table already lists the mutation-file edits (L227-228, L526-546, L552, L641, L771-779) under the substrate change.

**Recommendation:** declare `test_mutation_ownership_routing.py` L771-779 plus the import line as a WP04 sequenced-hotspot edit (they are in the same lane L3, so this is safe), or move that diagnostics-test edit into WP04 explicitly. Do **not** keep a tree-accepting shim "until WP05", because that is the second qualname algorithm C-004 forbids. The same applies to `census-rekey-map.csv` and `research/census_rekey_equivalence.py`, which both WP04 and WP05 write. Add them to the hotspot table.

**[HIGH] `pyproject.toml` is a hotspot for far more than WP07→WP09.**
`test_ruff_format_exclude_ratchet.py::test_every_exclude_entry_still_genuinely_reformats` (L82) fails when an excluded file becomes format-clean. Format-excluded files these WPs rewrite heavily:
- `test_ratchet_positional_anchor_ban.py` (L1019; WP01, WP12);
- `test_ratchet_baselines.py` (L1018, WP06);
- `test_no_inert_schema_slots.py` (L1005, WP06);
- `test_bridge_parity.py` (L1909, WP11, which moves about 460 lines out);
- `_bridge_oracle.py` (L1902, WP11);
- `test_internal_runtime_parity.py` (L1809, WP08);
- `test_reference_enum_ratchet.py` (L1022, WP06);
- `test_example_round_trip.py` (L1278, WP06);
- `test_no_read_side_bypass.py` (L1009, WP12);
- `_ratchet_keys.py` (L948, WP07).

If any of these ends up clean, its lane must edit `pyproject.toml` in parallel with WP07 and WP09.

**Recommendation:** add a plan rule: "never reformat an excluded file. If a rewrite leaves it clean, the exclude-line removal is recorded as a WP12 closeout edit." Alternatively, list `pyproject.toml` as a WP12-sequenced hotspot for every lane.

**[MEDIUM] `_ratchet_keys.py` is owned by WP07 (docstrings, §G1), but WP02's helper relates to it and Q1(c) wants a pointer there.**
Keeping WP02's code in a *new* module is the right decomposition, since it avoids the conflict. Route any `_ratchet_keys` docstring sentence through WP07, or add the dependency WP02→WP07. Do not let WP02 touch it.

**[LOW] WP01 `test_real_kernel_gate_has_no_unexempted_line_pin` (§A3).**
It must assert *findings ⊆ exempted rows*, not "exactly 2 findings". WP03 lands in a parallel lane, and an equality on 2 reds at lane consolidation.

**[INFO / concede]**
- The WP01/WP12 ban file and the WP02→WP03/WP04 helper are correctly sequenced.
- WP06 reads `len(test_mutation_ownership_routing._ALLOWLIST)` but does not edit it, and the count of 56 is invariant.
- WP01's warn-only interim rows correctly avoid making WP02–05 edit the ban file.

### Q3 — Deep-module check

**[MEDIUM] Split the *authoring form*, unify the *matcher*.**
The split between `ContentDescriptor` (hand-curated, substring, resolved) and `CensusKey` (generated, full token line plus op plus ordinal) is justified:
- There are 80 machine-regenerated rows (the literal re-builders at mutation L641 and overwrite L436).
- Warn-on-stale forbids raising at resolve time.
- `resolve_descriptor` drops the ordinal for twins.

Fail vs warn is a caller *policy*, not a matching difference, so it does not justify two matchers.

**Recommended minimal API**, all in `_content_identity`:
- `resolve_allowlist(descriptors, source_for) -> (Counter[CompositeKey], errors)`;
- `partition_findings(findings, allowed: Counter[K]) -> (unexpected, unused)`, generic in `K`, which serves census with count-1 keys;
- the two drift mutators.

Census keeps `CensusKey` and `census_keys()` in its own helper. That gives a deep module with 4 functions and 2 consumer families. Merging everything onto one entry type would push the ordinal and op into hand-curated rows for no benefit, so I **concede the entry-type split** and ask only for the matcher unification.

**[LOW] Test placement.**
The resolver's unit tests live in `tests/unit/test_descriptor_resolver.py`, while the plan adds `tests/architectural/test_content_identity.py`. Either is fine, but say why they are split. Architectural-marker collection is a plausible reason.

### Q4 — Campsite vs defer

**[MEDIUM] Dormant line-shaped loaders survive at 0 entries.**
- The `_lock_ban_exemptions.py` (`lock-ban-wp0{4,5}.txt`) and clock `_exemptions/__init__.py` (`IMPORT:`/`CALL:`) loaders still parse `path:line` with 0 entries. This is D-OP-6.
- `os-detect-ban-wp0{3,4}.txt` are empty as well.

The widened ban refuses new line pins, but the loaders' docstrings still *teach* the line shape. A future author gets a red with no sanctioned content form.

**Recommendation:** WP03 (which owns the content-line parser) retargets both loaders to the same parser, or deletes the loaders and the empty files so the gates become pure zero-tolerance. Both are about 50–70 lines with no data migration. If deferred, at least rewrite the loader docstrings and file headers to point at the content form in WP03.

**[MEDIUM] The sole-door, trio, surface-resolver and read-/write-side gates.**
Adopting `partition_findings` there changes semantics (set→multiset, 2-tuple→3-tuple) and needs its own red-first work, so it is **not** campsite.
- **Defer**, with one follow-up issue listing the 7 sites and the concrete widening holes: the 2-tuple cross-file bless in trio and surface-resolver, and set collapse everywhere.
- **Exception:** `test_single_mission_surface_resolver.py` is already rewritten by WP07. Adopting there is optional and needs WP07→WP02. I lean toward deferring to keep WP07 deletion-only (D-OP-4).
- `_sole_door_scan.resolve_exclusion_keys` delegation (Q1b) is the one cheap adoption worth taking in this mission. It has no semantic change for unique keys.

## Verdict

**PASS WITH CHANGES (no blocker to tasks, but 2 HIGH items must be written into the WP ownership before `/spec-kitty.tasks` finalises):**
1. WP04 declares its edit of the WP05-owned mutation file, plus the shared CSV and script, as sequenced hotspots.
2. Add a `pyproject.toml` format-exclude rule or hotspot for WP01, WP06, WP08, WP11 and WP12.

The single-authority HIGH (Q1) is resolved by the recommendations there: docstring authority, census delegation, the sole-door delegation and one follow-up issue. It does not need re-planning. The rest are MEDIUM/LOW refinements.
