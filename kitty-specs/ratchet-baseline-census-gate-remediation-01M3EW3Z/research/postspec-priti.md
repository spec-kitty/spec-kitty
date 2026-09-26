# Post-spec adversarial squad — Planner Priti (scope / sizing / sequencing / tracker hygiene)

Mission: `ratchet-baseline-census-gate-remediation-01M3EW3Z` (epic #5104). HEAD `6f24a8d7`. Read-only; no repo or tracker writes.

## Governance applied
- **Profile planner-priti**: initialization (decompose into sequenced WPs with explicit dependencies/AC; optimise for parallel delivery; flag risks early); avoidance boundary respected (no implementation, no architecture decisions — design questions are routed to plan as ambiguities); directive ref 003.
- **Charter `specify` context** (DIRECTIVE_001/003/010/024+, DIR-001..013, RECONCILE_CHANGE_SCOPE_TENSIONS; no tactics resolved): applied Standing Orders #2 (campsite on touched files only), #4 (red-first), #5 (architectural-gate non-vacuity: floor + self-mutation), #6 canonical sources (single authority — duplicate-issue check), #8 mission hygiene/issue matrix; C-011 ATDD-first; test-policy blast radius (pyproject/_baselines are cross-cutting).

## Evidence gathered (beyond the grounding files)
- LOC on HEAD: ban 1185; location-authority 501; kernel gate 307; destructive 524 / mutation 779 / overwrite 620; `_destructive_op_census.py` 221; `_inert_slots.py` 791; `test_ratchet_baselines.py` 985; `audit.py` 808 (inventory half from :527), `rekey_inventory.py` 274, `inventory.md` 129, `RULESET.md` 144; `status/test_parity.py` 740; `charter/test_context_parity.py` 428; `runtime/test_bridge_parity.py` 1862; `next/test_internal_runtime_parity.py` 169.
- Census collision probe (scratchpad `collide.py`, uses the real `enclosing_qualname`): destructive 22 keys → 2 share (rel,qualname,op), 2 share token line; **mutation 56 keys → 26 share (rel,qualname,op), 4 share token line**; overwrite 2 → 0. So ~6 keys need an `occurrence` ordinal even with token-line identity, and qualname-only keying is not viable.
- `_baselines.yaml`: 12 top-level, 23 nested keys. Only `unassigned_entries`, `masking_suppressions` are unread by any `.py`. `test_example_round_trip.skip_marker_blocks` IS read but only drives `record_property` (non-failing). `test_mutation_ownership_routing.destructive_op_allowlist: 56` is registered against `len(_ALLOWLIST)` (test_ratchet_baselines.py:467/629) — FR-006 re-keying is coupled to it.
- **Line-pinned exemptions the grounding sweep missed**: `tests/architectural/_exemptions/os-detect-ban-*.txt` carry 6 authoritative `path:line` rows (`src/specify_cli/__init__.py:353,:521`, `paths/windows_paths.py:163`, `kernel/locks.py:96,:222,:234`), parsed into `(path, int)` by `_os_detection_exemptions.py:54-61` and consumed by `test_os_detection_ban.py:89,110`. The sweep only covered Python module-level containers + 2 YAMLs.
- `pyproject.toml [tool.ruff.format].exclude` names 14 of the files in scope (ban, no_inert, ratchet_baselines, audit.py, rekey, internal_runtime_parity, status/test_parity, bridge_parity, _bridge_oracle, surface_resolution_equivalence, execution_context_parity, transition_gate_parity, docs_cli_reference_parity, status/test_reducer, status/test_transitions). `tests/architectural/test_ruff_format_enforcement.py::test_formatter_debt_exclude_only_names_live_files` means **every file deletion/rename must edit pyproject.toml in the same commit**.
- FR-014 seam: `charter.offering.pack_paths` honours `SPEC_KITTY_PACKS_ROOT` (public env seam), but it redirects *all* kinds; the current test patches only directives + catalog so paradigms/procedures keep real content, and also patches private `_activation_aware_profile_map` and calls private `_reset_agent_profile_cache`.
- Same vacuous-scan class outside the #2631 sweep: `tests/contract/test_next_no_unknown_state.py:40` rglobs the deleted `src/specify_cli/next`.
- `test_bridge_parity.py` P0 block (:1383-1862) depends on shared helpers defined in the oracle half (`_seed_wp_lane` :85, `_write_wp_task_files` :105, `_reject_wp_on_status_surface` :370, late `_MissionTopology` import :321).

## Findings

[HIGH] Tracker / FR-010 — **Duplicate authority: open #3962 "Restore or delete the orphaned inert-slots owner gate"** (status:ready, good-first-issue, parent #1932, milestone 4.x Work) plans the exact change FR-010 makes (delete `_inert_slots.py` owner helpers + `unassigned_entries`). Spec and grounding never mention it. — **FOLD**: add #3962 to the mission's issue matrix as closed-by FR-010, reference it in the Epic/children header, re-parent or cross-link it under #5104, and pull it off the ready queue so the factory dispatcher does not pick it up in parallel.

[HIGH] SC-001 / FR-001 / NFR-001 — the "0 line-pinned entries under tests/architectural" claim is false-by-omission: 6 authoritative `path:line` rows in `_exemptions/os-detect-ban-*.txt` (plus 40 generated `lineno:` rows in `census/spec_kitty_home_pin_anchor.yaml`, and `file:line` locators in `untrusted_path_audit/inventory.md`) are not in any FR and the widened Python ban will not see them. — Either (a) add FR-006b: migrate `_os_detection_exemptions.py` to content identity (S, ~60-100 LOC, same substrate), or (b) narrow SC-001/NFR-001 to "module-level Python seeds" and record the data-file exemptions explicitly with reasons (FR-003). Recommend (a) for the .txt (authoritative, 6 rows) and (b) for the SHA-pinned YAML.

[HIGH] FR-006 sizing — undersized ~3x. Not "mechanical": 80 keys × rationale re-authoring (~320 allowlist lines across destructive :158-256, mutation :238-442, overwrite :267-283), 3 key builders (:147, :228, :256), 3 `rsplit(":",2)` sites (:286, :552, :360), 2 literal re-builders (mutation :641, overwrite :436), `drop_one_entry`/`diff_against_allowlist` in the shared helper, and ~6 occurrence ordinals (probe above). Mutation alone has 26 same-qualname-same-op keys, so reviewers must verify each ordinal against source. Estimate **+350/-300 lines, L**; split into WP-a (helper + destructive + overwrite, 24 keys) and WP-b (mutation, 56 keys). Shared-helper change ⇒ full `tests/architectural/` per test policy. Must preserve `destructive_op_allowlist: 56` count (or shrink it in the same commit with the ratchet).

[HIGH] FR-007 vs existing contract — `_destructive_op_census.diff_against_allowlist` documents stale entries as **WARN only: "legitimate cleanup must never be blocked"** (:189-200). FR-007 flips that to FAIL for the census gates, meaning any `src/` PR that deletes a destructive op reds an architectural gate it did not touch — the very "tax on unrelated changes" #5104 exists to remove. — Plan must decide per gate: fail-on-stale (location/kernel, where #5085 shows dead entries are latent wildcards) vs warn-on-stale (census, where content identity already prevents a wildcard re-bind because a new op will not match a dead content key). Recommend narrowing FR-007: fail only where a dead entry can bless a new violation; state the rationale.

[MEDIUM] C-001 vs FR-008/FR-010/FR-013/FR-015 — "each WP lands a failing-first acceptance test" plus US2's independent test ("grep the repo for retired symbols") invites committing **tombstone/absence tests** — the exact class #3285 retired and FR-013/FR-015 delete. — State in plan that retirement WPs' red-first evidence is (i) the FR-011 unread-key gate (for FR-010) and (ii) non-committed tracer evidence (grep output in the WP tracer) for FR-008/009; no new "symbol X is gone" tests.

[MEDIUM] FR-011 definition — "a nested key that no test reads" is ambiguous: text-grep vs registered comparison. `skip_marker_blocks` is read but never fails; a grep-based gate is satisfiable by a comment (both dead keys are mentioned in prose today: `test_reference_enum_ratchet.py:192`). — Specify it as an explicit `(top, sub)` registry in `test_ratchet_baselines.py` paired with the comparisons (extend `_REQUIRED_TOP_LEVEL_KEYS` pattern one level), with a self-mutation (plant an extra sub-key → red). Size S (+80-120 LOC). Sequence: FR-011 RED-first commit, then FR-010 deletes the two keys → GREEN; same WP.

[MEDIUM] FR-010 scope gap — retiring owner predicates leaves the per-entry `owner`/`provisional` fields in all 38 `_inert_slots_baseline.yaml` rows, the `code_only_suppressions` section (`_CODE_ONLY_KEY`, loaded at import :753) and `MINIMUM_*` constants (:453-454, :790-791) as unread data — the FR-011 defect class one level deeper, which FR-011 (only `_baselines.yaml`) will not catch. Also 2 baseline rows are already cleared (`styleguide-references`, `model`). — Enumerate the full dead surface in FR-010 (≈-300/-350 LOC of 791), and add a campsite shrink `baseline_entries 38→36` (shrink-only; NFR-003 friendly). Keep `test_live_tree_has_no_new_inert_slots` name (referenced by `test_gate_remedy_presence.py:174`).

[MEDIUM] FR-014 feasibility under C-005 — `SPEC_KITTY_PACKS_ROOT` redirects every kind, so the "on-disk fixture" must reconstruct a full packs tree (empty directives + real/linked other kinds) and replace the private profile-map patch with an on-disk profile; private cache reset remains. If caching or the loader resists, the only fix is a `src/` seam, which C-005 forbids. — Size M (not S), add an explicit fallback in plan: if no public seam suffices, stop and file a src-seam follow-up rather than re-patching privates.

[MEDIUM] FR-016 sizing — split needs shared helpers (:85, :105, :321, :370) extracted to a support module (or `_bridge_oracle.py`) used by both halves; `_bridge_oracle.py` also carries 8 `bridge:NNNN` anchors. Size M (~+120/-60 moved lines); new module must be added to the format regime (not exclude) and satisfies `test_module_length_agreement`. Coordinate with #2560 (runtime_bridge degod slice) which may touch the same tests.

[MEDIUM] FR-013 sizing — `TestReducerDeterminism`/`TestFullEventLogParity` (:213-690, ~480 LOC) are triplicated with `status/test_reducer.py:143,177,425,465` and `cross_branch/test_parity.py`; relocation = case-by-case dedup, not a move. Spec omits `cross_branch/test_parity.py` (grounding: CONSOLIDATE/delete). Size M. Both destination files are format-excluded; deleting `status/test_parity.py` edits pyproject.

[MEDIUM] Hot-file ownership — `pyproject.toml` (FR-008 excludes :954-955, FR-013 :2553, FR-012 :1809, FR-014 rename, FR-016 new file), `_baselines.yaml` (FR-006 count, FR-010/011 keys), `test_ratchet_baselines.py` (FR-011, FR-006 if count moves), and the ban file (FR-001-003 + exemption-row removals by FR-004/005/006) are shared. — Assign single owners: pyproject edits land in the WP that deletes/renames the file but serialize those WPs in one lane (or give one WP pyproject ownership and have others depend on it); `_baselines.yaml`+`test_ratchet_baselines.py` owned by the FR-010/011 WP, FR-006 WPs forbidden from changing the count.

[MEDIUM] FR-001 → FR-004/005/006 ordering — widened ban goes RED on 88 (94 with os-detect) until migrations land. No xfail (grounding §5f). — WP01 lands the widened ban with a temporary enumerated, reasoned exemption list naming the 5 (6) symbols, plus drift test; each migration WP deletes its row. This keeps lanes parallel after WP01 and satisfies FR-003/NFR-003.

[LOW] FR-012 — also fix `tests/contract/test_next_no_unknown_state.py:40` (same vacuous rglob of deleted `src/specify_cli/next`); outside the *parity* naming sweep but same defect class and trivially small. Fold as campsite or file under #5104.

[LOW] FR-009 coverage — include failure messages, not just docs: `test_single_mission_surface_resolver.py:508` instructs "Run `python .../audit.py`"; also `_ratchet_keys.py:49,124` docstrings, `test_no_worktree_name_guess.py:155`, `untrusted_path_audit/inventory.md:76` cross-reference, `RULESET.md:6`.

[LOW] NFR-005 vs format-excluded files — "changed files pass ruff format --check" is vacuous for 14 excluded files. Decide: leave excluded (and don't reformat — would bloat diffs, and #4506 drains the exclude list wholesale) or campsite-remove from exclude. Recommend leave excluded; coordinate with #4506.

[LOW] FR-017 — "#2620 catalog format" location is unstated; plan must name the canonical catalog path (not copy from an older mission, per canonical-sources rule).

[LOW] FR-018 — spec FR asks the mission to file issues; implementers are read/write-restricted in squads. Assign FR-018/019 to the operator-facing closeout WP, not a code WP.

## Foldable-issue triage (open unless noted)
| Issue | Verdict | Reason |
|---|---|---|
| #3962 orphaned inert-slots owner gate | **FOLD** | Same change as FR-010; duplicate authority, currently `status:ready` under #1932 |
| #3206 kernel/schema_utils exemption | COORDINATE | FR-005 migrates its 2 tuples; post comment that its AC "remove the two entries" becomes "remove the descriptors". Do not fold (src design decision, P2 triage) |
| #2633 delete 34 runtime_bridge delegates | COORDINATE | C-002 gate for oracle retirement; FR-018a follow-up hangs off it |
| #2560 runtime_bridge degod slice | COORDINATE | May touch bridge tests during FR-016 split |
| #4506 drain ruff-format-exclude ratchet | COORDINATE | Same pyproject exclude list and same 14 files; avoid concurrent reformat |
| #2972 census | per spec (campsite/deferred) | Correct; #1842 routing target closed → FR-018c |
| #3011 / #3026 / #5085 / #2631 | in scope | #3026 closes as superseded-by-retirement (its property fix is moot once caps are deleted) |
| #2625 golden-count excluded dirs | IGNORE | CLOSED 2026-09-14 (PR #4359) |
| #4167 import-ban battery CI scoping | IGNORE | CI gate-selection, different files |
| #2638 (surface_resolution_audit scanner victim) | IGNORE | Historical duplicate; gate already deleted |
| #1931 | note | CLOSED parent; #5104 is the live epic |
Note: GitHub search hit rate limits mid-sweep; searches for status/test_parity, context_parity, stale-allowlist returned no open hits; a residual miss is possible.

## Proposed WP decomposition and sizing (spec implies ~5 issue-sized WPs; realistic is 10)
| WP | FRs | Size | ~LOC (+/-) | Depends | Owned files |
|---|---|---|---|---|---|
| WP01 Widen ban + temp exemption list | 001, 002, 003 (+RED) | M | +250/-60 | — | ban file |
| WP02 Join + kernel migration | 004, 005, 007(loc/kernel) | S | +110/-130 | WP01 | location_authority, kernel gate, ban exemption rows |
| WP03 Census helper + destructive + overwrite | 006a, 007(policy) | M | +180/-150 | WP01 | `_destructive_op_census.py`, destructive, overwrite |
| WP04 Mutation census re-key | 006b | M-L | +220/-200 | WP03 | mutation gate |
| WP05 os-detect exemption migration (new) | 006c | S | +80/-40 | WP01 | `_os_detection_exemptions.py`, `_exemptions/os-detect-*` |
| WP06 Surface-resolution retirement | 008, 009 | S | +30/-750 | — | surface_resolution_audit/*, pyproject (excl), single_mission_surface_resolver msg |
| WP07 Unread-key gate + inert retirement (+#3962) | 011 then 010 | M | +120/-380 | — | test_ratchet_baselines, _baselines.yaml, _inert_slots*, no_inert |
| WP08 Runtime-parity bans + residue | 012, 015 | S | +60/-250 | — | internal_runtime_parity, surface_res_equivalence, exec_ctx_parity, transition_gate, docs_cli_ref |
| WP09 Status parity retire/relocate | 013 | M | +80/-600 | — | status/test_parity, test_reducer, test_transitions, cross_branch/test_parity |
| WP10 Context parity conversion | 014 | M | +150/-120 | — | charter/test_context_parity (rename) |
| WP11 Bridge parity split | 016 | M | +150/-80 | — | test_bridge_parity, new module, _bridge_oracle |
| WP12 Verdicts, follow-ups, matrix | 017, 018, 019 | S | docs | all | tracer, issue-matrix |
pyproject.toml: WP06, WP08, WP09, WP10, WP11 each touch the exclude list → put them in one lane, or sequence. Parallel lanes: {WP01→WP02, WP01→WP03→WP04, WP01→WP05}, {WP07}, {WP06/08/09/10/11 serialized on pyproject}, WP12 last.
Aggregate: roughly +1,700 / -3,300 touched lines; the net-deletion is what makes it look small in the spec.

## Cut / defer / add
- **Add**: #3962 fold; os-detect .txt migration (or explicit scoped exemption); `cross_branch/test_parity.py` into FR-013; `test_next_no_unknown_state.py:40` into FR-012; full FR-010 dead-surface list incl. baseline YAML owner/code-only sections and 38→36 shrink.
- **Defer candidate**: FR-014 (highest risk vs C-005, lowest value; one suite) — could go to a follow-up if the public seam proves insufficient. FR-015 residue is pure polish; keep only where the WP already touches the file.
- **Narrow**: FR-007 (fail-on-stale only where a dead entry is a wildcard). SC-001/NFR-001 wording to the actual scanned universe.
- **Keep**: C-002 oracle deferral, C-003 census deferral — correct.

## Concessions
- The grounding is unusually strong (probe-verified RED counts, per-hit migration plan, collision warning already raised); the spec faithfully reflects operator decisions.
- DM choices (retire #3011, retire #3026 machinery) reduce, not add, gate surface — consistent with #5104's intent.
- FR-004/005/008 really are small; undersizing concentrates in FR-006, FR-013, FR-014, FR-016 and hidden coupling (pyproject, baseline counts).

## Verdict: **PROCEED-WITH-CHANGES**
Blocking before plan: fold #3962; decide FR-007 stale policy for census gates; resolve SC-001 scope (os-detect .txt); pin FR-011's "read" definition. The rest are plan-phase sizing/ownership inputs.
