# Post-spec adversarial squad — Reviewer Renata (anti-laziness / fakeability lens)

Mission: `ratchet-baseline-census-gate-remediation-01M3EW3Z` · Spec: `kitty-specs/ratchet-baseline-census-gate-remediation-01M3EW3Z/spec.md`
Mode: READ-ONLY (no repo edits). Evidence base: spec.md, checklists/requirements.md, research/grounding-{5085,3011,3026,2631_2972}.md, plus two read-only probes of `tests/architectural/_baselines.yaml` and `test_ratchet_baselines.py`.

## Governance applied

- **Profile `reviewer-renata`**: initialization "quality gate, not implementer" (I identify and specify; I do not rewrite the spec); avoidance boundary respected (no product decisions: I propose wording/tests, the operator decides); directive refs 001/024/030/032/041/051; tactics used: `delete-the-assertion-not-the-test` (tests that encode the hole must be inverted, not deleted), `test-scaffolding-as-design-smell`, `reverse-speccing` (reading each FR as the implementer who wants the cheapest green), `test-readability-clarity-check`.
- **Charter `specify` context**: paradigms specification-by-example + BDD (every fix below is a concrete Given/When/Then or checkable predicate); Standing Order #5 architectural-gate non-vacuity (concrete floors + self-mutation), shrink-only baselines, ATDD-first (C-011), canonical sources (C-004 substrate), terminology canon (Mission, not feature — no violations found in the spec), `USE_MUTATION_TESTING_TO_VALIDATE_TEST_QUALITY`.

## Probe results used as evidence

- `_baselines.yaml` has 23 nested (depth-2) keys. 21 are named in `test_ratchet_baselines.py`; `unassigned_entries` and `masking_suppressions` are not. **But both names still appear in other `.py` files** (`test_reference_enum_ratchet.py:192` prose; `_inert_slots.py` comments). So an FR-011 implementation that defines "read" as "the key name occurs in some test file" is GREEN on HEAD, i.e. not red-first, i.e. vacuous. This is the single most concrete fake path found.
- `test_no_unregistered_baseline_keys_are_added` (`test_ratchet_baselines.py:654-690`) checks top-level keys only, against a hand-maintained `_REQUIRED_TOP_LEVEL_KEYS`. A nested analogue built the same way (hand list) is satisfiable by adding the two dead keys to the list.

## Findings

### Critical

**[CRITICAL] FR-003 + SC-001 + NFR-003 — the exemption list is unbounded and symbol-granular, so it can absorb all 88 entries in 5 rows.**
FR-003 exempts "by an explicit symbol-keyed exemption list"; SC-001 counts only entries "outside the enumerated exemption list"; the grounding (§5f) even proposes landing WP01 with the hits "temporarily enumerated as exemptions and shrink the list in WP02". Five rows (`_KNOWN_JOIN_ALLOWLIST`, kernel `_PRE_EXISTING_EXEMPTIONS`, three census `_ALLOWLIST`s) would exempt all 88 line pins, make SC-001 read "0", and — if NFR-003 counts exemption *rows* — make NFR-003 show a net decrease of ~83. Every letter met, no intent met. "Shrink-only" is asserted, not pinned.
*Recommendation* — tighten to:
> FR-003: "At mission acceptance the positional-anchor exemption list is **empty**, pinned by a frozenset-equality assertion (so re-widening is a visible diff). The only permitted interim row is the #3206 kernel row, and only if FR-005 is not delivered; any row must name an **open** issue, and a drift test fails when the row's symbol no longer exists **or no longer produces a finding**."
> SC-001: "0 line-pinned Python seed entries under `tests/architectural/`, **and** the exemption list is empty (or contains exactly the #3206 row)."
> NFR-003: "Counted per exempted **site** (one allowlist element = one entry), not per exemption-list row. Baseline: 88 line-pinned sites + N content-keyed sites on the planning base; after: ≤ base − 2, with 0 line-pinned."
Acceptance test: `test_positional_anchor_exemption_list_is_empty` (frozenset equality).

**[CRITICAL] FR-011 / SC-004 / US2-AS3 — "a nested key that no test reads" has no machine definition; the cheapest definitions pass vacuously on HEAD.**
Three fakes: (a) "read" = name grep ⇒ green on HEAD (see probe); (b) a hand registry of allowed nested keys ⇒ add the two dead keys to it; (c) "read" = some test loads the value ⇒ a test that does `assert "masking_suppressions" in data` "reads" it. None of these proves a comparison exists.
*Recommendation*:
> FR-011: "A nested `_baselines.yaml` key is **read** iff it is consumed by a ratchet comparison that fails when the live measurement exceeds the key's value. The set of nested keys in `_baselines.yaml` must equal (both directions) the set of keys **derived from the comparison tables themselves** (the `single_baselines` lists / reciprocal-assertion registry), not from a separately maintained name list."
Acceptance tests: (1) RED on planning base naming exactly `test_no_inert_schema_slots.unassigned_entries` and `…masking_suppressions`; (2) planted unread key in a tmp copy of the YAML ⇒ fails naming it; (3) **self-mutation**: for each registered nested key, lowering its value to (live − 1) in a tmp copy makes the ratchet fail — or, at minimum, a parametrized proof for a sample that includes every comparison mechanism (list-length, reciprocal assertion).

### High

**[HIGH] FR-006 / Edge case 1 — content re-keying can silently *widen* the census exemptions.**
A key like `rel::qualname::op` (the cheapest "content identity") blesses any *additional* identical op added to the same function. Also a one-shot regeneration script re-keys whatever is on HEAD, so a site that is currently blessed only by coincidence (the #5085 dead-entry class) gets laundered into a permanent content key.
*Recommendation*: promote the edge case to acceptance scenarios on each of the three census gates:
> "Given a migrated census gate, When a second identical `<op>` is added to an already-exempted qualname, Then the gate fails." and "The migration PR carries an 80-row old-key → new-key mapping; the set of sites suppressed on the planning base equals the set suppressed after migration (asserted by a one-shot equivalence check recorded in the PR), and each entry's rationale text is preserved verbatim."
Add: "`rsplit`/`drop_one_entry` shrink proofs continue to pass for 100% of entries."

**[HIGH] FR-007 — stale-entry detection passes vacuously when the allowlist is empty, and "resolves to a live construct" is weaker than "still exempts a live finding".**
An entry whose `token_substring` is `/` resolves to *something* forever. A staleness check iterating an empty tuple is green.
*Recommendation*:
> FR-007: "Every migrated entry must (a) resolve to exactly one site (`resolve_descriptor` exactly-one semantics) **and** (b) suppress at least one finding the owning gate's detector produces on the live tree. The staleness check asserts the number of entries it checked equals `len(allowlist)` and is ≥ the concrete count recorded in plan (e.g. 4 joins, 2 kernel, 80 census)."
Acceptance tests: delete the construct ⇒ fail naming it (already in US1-AS3); **rename** the enclosing function ⇒ fail (edge case 2, make it an AS); an entry that resolves but no longer produces a finding (e.g. the join rewritten without `/`) ⇒ fail.

**[HIGH] NFR-002 — self-mutation and floor are satisfiable by a fixture-only test and `>= 1`.**
A "self-mutation test" that feeds a synthetic string to a *reimplemented* helper, or that asserts a planted fixture fails but never proves the real scan path is load-bearing, meets the letter. "Concrete non-zero floor" is satisfied by `assert files`. "Retained bans in scope" is not enumerated.
*Recommendation*:
> NFR-002: "For each ban in the enumerated list [widened positional-anchor ban (each arm), FR-007 staleness checks, FR-011 unread-key check, FR-012 runtime-parity bans], there is (a) a planted-violation test that calls **the same function the production test calls** on a synthetic source and asserts ≥1 finding naming the plant; (b) a load-bearing proof: monkeypatching that arm's predicate to always-false turns (a) green; (c) a real-tree floor ≥ a concrete number recorded in plan and derived from the planning-base count (not `>= 1`)."
Machine check: a meta-test (or review checklist row) that each listed ban has all three.

**[HIGH] SC-002 / NFR-001 / US1-AS2 — drift tolerance testable on one file, with a blank line only, asserting only pass/fail.**
Fakes: parametrize over a single file; insert only a blank line (tokenizer-based keys ignore blank lines, but a key that accidentally encodes an intra-function offset breaks on a comment/statement insertion); assert "gate green" while the site silently disappeared from the scan (green because nothing matched).
*Recommendation*:
> NFR-001: "Parametrized over **every** distinct file referenced by any migrated allowlist (parameter count asserted equal to that file set, concrete number in plan). For each file, two mutations applied to an in-memory copy: (i) a blank line at the top, (ii) a comment and a no-op statement inserted inside the enclosing function directly above the exempted site. The owning gate's detection+allowlist function run on the mutated source yields the **identical suppressed-site set and identical unsuppressed-finding set** as on the unmutated source."

**[HIGH] FR-001 / FR-002 — shape enumeration invites a two-shape implementation that the next author evades.**
FR-002 lists exactly `(str|Path(...), int)` and `path:line[:suffix]`. Not covered: `Path("a") / "b.py"` BinOp, 3+-tuples `(path, qualname, int)`, keyword-constructed records (`Entry(path=..., line=12)`, `dict(path=..., line=...)`), `{path: int}` / `{path: [int, ...]}` maps, class-body or function-local allowlists, `"x.py#L12"`. FR-001 says "module-level", which exempts allowlists built inside a class body or a fixture function.
*Recommendation*: either state the property ("any data literal bound in module or class scope that pairs a path-ish value with an int used as a line comparand") or explicitly enumerate the additional shapes as in-scope/out-of-scope with fixtures. Minimum: add planted fixtures for 3-tuple, `Path(..)/".."` BinOp, class-attribute allowlist, `{path: int}` dict, and a negative fixture set from grounding §2b (exit codes, counts, arg indices, `"decision.py:401; empty stdout"` prose) asserting 0 findings.

**[HIGH] FR-001 (process) — tests that encode the hole may be deleted instead of inverted.**
`TestImportsRatchetSubstrate.test_ignores_non_substrate_file` (L876-879), `test_ct7_raw_tuple_in_non_substrate_file_stays_green` (L1086-1102), `test_ct7_real_3206_import_lineno_exemption_stays_green` (L1105-1120) encode the blind spot. Deleting them is the lazy path.
*Recommendation*: add to FR-001: "The three tests that encode the context gate are **inverted** (same fixture, assert ≥1 finding), not deleted" (tactic `delete-the-assertion-not-the-test`).

**[HIGH] NFR-006 / FR-013 — "scaffold, no invariant" is an unconditional escape hatch, and "relocated" is unproven.**
Any retirement can be labelled scaffold. "Relocated determinism and transition-matrix checks still run" is satisfied by moving tests that are already triplicated (grounding N2) or by moving them in a weakened form.
*Recommendation*:
> NFR-006: "A 'scaffold, no invariant' verdict must cite the concrete reason (the subsystem/module it pins is deleted, with commit SHA; or the assertion is on the test's own docstring). A 'named surviving test' verdict must carry a **mutation proof**: the mutation that fails the retired test also fails the survivor."
> FR-013 AS: "shuffling the reducer sort key, adding a `done → planned` matrix row, and adding a self-transition each turn the relocated/surviving test red (grounding N2 mutations), recorded in the PR."

**[HIGH] FR-016 / US3-AS3 — "split" can be a file move that still pays the oracle.**
Moving the 17 P0 tests into a new module that imports the same module-scoped fixture (391 s setup) satisfies "separated".
*Recommendation*:
> AS: "The P0 module collects exactly the 17 P0 test node IDs present on the planning base (nodeid list diffed in PR), imports no fixture or helper from the two-run oracle, and completes in < 120 s standalone; the oracle module is unchanged in assertion count (C-002)."

### Medium

**[MEDIUM] SC-003 / FR-008 / FR-010 — "0 references" is satisfiable by renaming, and "removed" by leaving dead helpers.**
Renaming `rekey_inventory.py` or moving the converter into another helper passes a name grep. FR-008 removes `audit.main()` but the inventory-parsing half of `audit.py` (from `:477`) can stay as dead code.
*Recommendation*: pin the grep token list in the spec (`rekey_inventory`, `_render_inventory`, `_parse_inventory_rows`, `inventory.md` within `surface_resolution_audit/`, `MAX_UNASSIGNED_ENTRIES`, `MAX_MASKING_SUPPRESSIONS`, `owner_exists`, `owner_is_complete`, `unresolved_by_completed_owners`, `find_code_only_suppressions`, `code_only_drift`, `load_code_only_record`, `code_producer_writes`, `MINIMUM_*_SLOT_NAMES`, `MINIMUM_*_BASELINE_ENTRIES_STILL_FOUND`, `unassigned_entries`, `masking_suppressions`); define "live" (everything except `kitty-specs/**`, `docs/reports/**`, `CHANGELOG.md`); add behavioural checks: "no module under `tests/architectural/surface_resolution_audit/` writes a file or defines `__main__`" and "every remaining top-level function in `audit.py` / `_inert_slots.py` has ≥1 importer outside its module".

**[MEDIUM] FR-009 — `audit.py` formatter exclusion.** `pyproject.toml:954-955` excludes both `audit.py` and `rekey_inventory.py` from `ruff format`. FR-009 only mentions exclusions "that reference the retired converter", so `audit.py` (kept, partly) may keep escaping the format gate. Recommend: "both exclusions removed; the kept `audit.py` passes `ruff format --check`". Note this touches `pyproject.toml` ⇒ cross-cutting ⇒ full `tests/architectural/` per test policy; say so in the spec's assumptions.

**[MEDIUM] US2-AS1 — kept-surface check names only one consumer.** Assumptions list three consumers (`test_single_mission_surface_resolver.py`, `test_no_worktree_name_guess.py`, `_ratchet_keys.py`) and grounding flags an unconfirmed hypothesis about `audited-surfaces.md` / `write_candidate_classification.yaml`. Recommend AS: "all three consumers pass, and plan records the confirmed status of the two sibling data files."

**[MEDIUM] FR-012 — floor and target undefined.** "Minimum-file floor" permits `>= 1`; the banned import names may themselves be stale (bans that can never fire even on a live package). Recommend: "scan target path asserted to exist; floor ≥ planning-base `.py` count under the runtime package minus a stated margin; a planted file under a tmp copy containing each banned import string produces a finding."

**[MEDIUM] FR-014 — "converted to an on-disk fixture" can still patch privates.** Recommend a checkable AS: "the converted module contains no `patch(` / `monkeypatch.setattr` whose target is a private name (`_x`) or a non-public module path; the relocation-changelog comment (:195-230) is deleted; mutating the on-disk fixture's pack content changes the assertion outcome."

**[MEDIUM] FR-015 — scope is 'named in the grounding report', which is unbounded and includes CONSOLIDATE verdicts.** Grounding also recommends CONSOLIDATE for `cross_branch/test_parity.py` and `test_wp02_seam_migration_equivalence.py`, which no FR claims. Enumerate the exact edits (surface-resolution-equivalence dead strict-xfail machinery; execution-context-parity xfail→WP docstring map and `missing_seams`; transition-gate-parity docstring meta-test at :280; …) and declare the CONSOLIDATE rows either in scope (with the same mutation-proof rule) or deferred via FR-018.

**[MEDIUM] FR-017 / SC-005 — verdict catalog completeness and "churn evidence" not machine-checkable.** Recommend: "catalog module set == output of `find tests -name '*parity*.py' -o -name '*equivalence*.py'` on the planning base minus the 4 `_support/coverage_safety` helpers (45 modules), checked by a script whose command and output are in the PR; each row carries the numeric columns all/src/mass/pcm/pcsrc and the git command window used." Otherwise verdicts are unsupported assertions.

**[MEDIUM] FR-010 / FR-018(b) — retirement deletes the only detector of a live defect.** `code_only_drift` currently finds the `model` suppression (grounding 3026 §2). It is uncalled, so nothing is "lost" in the enforced sense, but the follow-up issue is the only remaining record. Recommend FR-018(b) require the issue body to include the reproduction (file, slot, the detector's output) before the helper is deleted, and that the WP ordering files the issue first.

**[MEDIUM] Edge case 3 / SC-001 — YAML line-keyed data defers to plan while SC-001 says "under `tests/architectural/`".** `census/spec_kitty_home_pin_anchor.yaml` (40 `lineno`) and `charter_path_literal_allowlist.yaml` (50 `line:`) are under that tree. As worded, SC-001 is either false or forces them into the exemption list (feeding the CRITICAL above). Recommend: scope SC-001/FR-001 to **Python** seeds and state the two YAML files as out of scope with reasons (generated + SHA-pinned; declared non-authoritative), plus the dormant `tests/runtime/_bridge_oracle.py:602`.

### Low

**[LOW] US1-AS1 — "reports all 88" can be hard-coded.** Require the RED evidence to be the widened ban's actual output on the planning base with per-symbol breakdown 6/2/22/56/2, not an asserted constant.

**[LOW] NFR-004 — "< 10 s" lacks a measurement method.** State how: `pytest --durations` on the ban file in the `CI Modules` shard, reported in the PR; do not add a wall-clock assertion (flakiness policy).

**[LOW] FR-004 — "cannot bless a new join" should be an AS.** "Given the migrated allowlist, When a new `/` join is added to `src/kernel/paths.py` (or `runtime/home.py`) at the formerly pinned line, Then the gate fails."

**[LOW] FR-019 — "cleaned" undefined; can be zero.** Either say "may be zero; record each cleaned finding with before/after in the PR" or drop the campsite clause and keep only the matrix row.

**[LOW] C-001 for retirement WPs.** For deletion-only WPs the red-first test is naturally a symbol-absence grep — the rename-fakeable one. Tie it to the behavioural checks in the SC-003 recommendation.

**[INFO] Decision provenance.** Grounding for #3026 recommended Restore (A); DM-01M3EW4PB6 chose Retire. That is an operator product decision (outside this lens), but the spec's invariant line ("no negative invariant is lost") should acknowledge that the owner anti-weasel invariant was already lost in #3285 and is being formally abandoned, not preserved.

## Measurability summary

| Item | Machine-checkable as written? | After fix |
|---|---|---|
| SC-001 | Partly (exemption loophole) | Yes (empty-list frozenset pin) |
| SC-002 / NFR-001 | Partly (file set and mutation unspecified) | Yes |
| SC-003 | Grep only (rename-fakeable) | Yes (token list + behavioural checks) |
| SC-004 / FR-011 | No ("read" undefined) | Yes (derived from comparison tables + self-mutation) |
| SC-005 / FR-017 | Partly | Yes (set equality vs `find`) |
| SC-006 | Yes | — |
| NFR-002 | No ("in scope", floor value undefined) | Yes (enumerated bans, concrete floors) |
| NFR-003 | Ambiguous counting unit | Yes (per-site count) |
| NFR-004 | No method | Yes (durations report) |
| NFR-006 | Escape hatch | Yes (cited reason / mutation proof) |

## Verdict

**PROCEED-WITH-CHANGES.** The spec's intent, scoping and grounding are strong, and the RED-first facts (88 hits, 2 unread keys, 2 dead joins) are real. But two requirements (FR-003 exemption list, FR-011 "unread") can be met by an implementation that fixes nothing, and the non-vacuity/drift NFRs lack the definitions that make them checkable. Apply the two CRITICAL and the HIGH wording changes before plan; the MEDIUM/LOW items can be absorbed at plan as acceptance tests.
