---
title: 'ADR: Census-Floor Ratchets — Per-Ratchet Adjudication (Tripwire, Retire, Retire, Keep-Property)'
description: 'Per-ratchet verdicts on the #4315 census-floor ratchets: the routed-meta floor is deleted outright, golden-count and shard markers retire, property gates stay.'
status: Accepted
date: '2026-09-14'
---

## Context and Problem Statement

Issue [#4315](https://github.com/spec-kitty/spec-kitty/issues/4315) (parent epic
[#1931](https://github.com/spec-kitty/spec-kitty/issues/1931)) asks whether a
**census count** is the right instrument for four architectural gates that
demand a manual baseline re-pin on ordinary changes:

1. `tests/architectural/test_inline_meta_read_gate.py::test_routed_load_meta_floor`
   (`ROUTED_LOAD_META_FLOOR`);
2. `tests/architectural/test_golden_count_ban.py` (`_golden_count_baseline.json`);
3. `tests/architectural/marker_baseline.txt`;
4. the `tests/_arch_shard_map.py` / `tests/_next_shard_map.py` completeness counts.

The trigger was the PR [#4257](https://github.com/spec-kitty/spec-kitty/pull/4257)
landing pass: a ~277-line single-feature change tripped two of them. The routed
floor went red because a new function, `record_discard`, read `meta.json`
**through the canonical `_require_meta` seam** — precisely the behaviour the gate
exists to reward. As #4315 puts it: *"The gate punished the behavior it exists to
encourage."*

#4315 requires a **per-ratchet** decision — keep-hard / demote-advisory /
replace-with-property-check / auto-maintain / retire — *"Not a blanket removal
without that adjudication."* This ADR is that adjudication.

### Two scope corrections

Measured against the tree at `2222506cc5`, two of #4315's four items are not what
the ticket assumed:

- **`marker_baseline.txt` does not exist.** `tests/architectural/test_marker_baseline.py`
  was deleted by `177e062694` (*"test: assertively sanitize low-signal suite
  cruft"*, [#3285](https://github.com/spec-kitty/spec-kitty/issues/3285),
  2026-08-12); only a stale `.pyc` remains. It is already retired.
- **The shard-map "completeness counts" are not counts.** Both live tests are
  set-partition properties over a freshly collected corpus. There is no pinned
  integer anywhere in the shard machinery. The friction is the hand-maintained
  **assignment table**, and it is confined to one of the two groups.

### The governing constraint: what doctrine actually requires

`DIRECTIVE_043` *Close Defect Classes by Construction* carries
`enforcement: required`, and its integrity rules bind here:

> A gate that trivially passes when the relevant call-site count is zero
> (vacuous gate) is non-compliant — **the gate must have a concrete floor**.

The companion `tactic:architectural-gate-non-vacuity` states the floor's purpose
precisely, and its own worked examples set the scale:

> A route-or-allowlist gate is **vacuously satisfiable** if all existing calls are
> allowlisted and the count through the sanctioned surface **drops to zero**.
> Assert separately that the count of calls through the canonical (routed) surface
> is above a minimum.
>
> — examples: `assert canonical_call_count >= 1` · `assert len(...) >= MIN_ROUTED_FILES`

**Nothing in doctrine requires a *separate routed-count floor* on this gate at
all.** DIRECTIVE_043's mandate is that the gate not pass vacuously; for the
inline-read gate that guarantee is already carried by mechanic 2 — the ceiling's
`MARGIN` clause (`INLINE_META_READ_FLOOR - live <= MARGIN`, so the live count must
stay near the ceiling and a broken or empty scan reds) — and by the FR-010
single-decoder gate. The routed-count floor measured routing *through* the
canonical reader — a reward signal, not the gate's non-vacuity guard — and a
tighter, floor-independent de-routing detector already exists (`_ACCOUNTED_SITES`
in `test_meta_fail_closed_full_census_contract.py`, exact-equality, keyed on
`load_meta_fail_closed`). The routed floor therefore added no non-vacuity
protection the gate did not already have; deleting it leaves DIRECTIVE_043 and the
tactic fully satisfied. This ADR records the point explicitly so no future
reviewer reads the deletion below as weakening DIRECTIVE_043.

Two further facts bound how much authority the current shape carries:

- The tactic's own `notes` audit (T007) labels **three of its four elements
  ASPIRATIONAL**, including the concrete floor and the routed-count floor: *"it is
  aspirational relative to the current exemplar."*
- `tactic:frozen-baseline-shrink-only-ratchet` — the canonical maintenance
  discipline — governs **debt ceilings**: *"CI fails if the live count **grows**
  beyond the committed baseline, and warns (but does not fail) if it shrinks,"*
  with a burn-down target of zero. Every entry in the canonical
  `tests/architectural/_baselines.yaml` has that shape: a count of *bad* things
  that must shrink.

That distinction is the analytical core of this ADR. A **debt ceiling** has a
natural fixed point (zero) and stabilises as the debt drains. A **goodness floor**
— a minimum count of *good* call sites, pinned within a margin of live — has no
fixed point: good call sites grow with the codebase, so the pin must be chased
forever. The doctrine sanctions the former. The latter is an invention of one
gate.

## Decision Drivers

- **Measured catch record vs. measured landing friction**, per gate — not opinion.
- **Doctrinal compliance**: DIRECTIVE_043 is `required`; no verdict may leave a
  route-or-allowlist gate vacuously satisfiable.
- **Single canonical authority** (charter governing principle): one baseline
  authority, not two.
- **The #2913 operator ruling** binds this class of change: *"because the outcome
  may alter or remove a blocking, shared CI gate — land the CaaCS tally and your
  recommendation first, and get maintainer concurrence on the chosen decision-menu
  option before implementing it."* Concurrence for every verdict below was
  obtained 2026-09-14 before any gate change was authored.

## Evidence

All figures measured against `main` @ `2222506cc5` on 2026-09-14.

### Gate 1 — `ROUTED_LOAD_META_FLOOR`

| Bucket | Count | Meaning |
|---|---|---|
| A. False red | 2 (self-reported as *"the third recurrence"*) | Routing coverage did not regress; the census moved on a delegation/dedup/rename shape change |
| B. Drift re-pin | 6 | Genuine drift accumulated by unrelated merges; the landing PR added no routed sites |
| C. Legitimate own-diff re-pin | 15 | The PR correctly added routed sites — the gate demanded manual work for doing the right thing |
| **D. Real catch** | **0** | — |

**23 value-moving commits in 63 days** (2026-07-08 → 2026-09-09). Bucket D is
empty: the floor has never once blocked a genuine de-routing.

Three further facts decide this gate:

- **Zero headroom today.** Live routed census = **157**, floor = **153**, margin =
  **4**. The permitted band is `154 ≤ live ≤ 157`; the repo sits on its upper
  edge. The next PR anywhere that adds one canonical `load_meta*` call reds the
  gate.
- **The attack the floor deters was never attempted.**
  `inline_meta_read_allowlist.yaml` has **3 commits ever** — creation, one
  qualname freshening, one path rewrite for the `src/charter/` move — and **net
  zero entries added in 68 days**. `INLINE_META_READ_FLOOR` has never moved off
  **7**. Mass-allow-listing is in any case visible in review as N new
  `{key, rationale, issue}` entries *plus* a ceiling raise.
- **The one real defect this file ever caught belongs to the ceiling, not the
  floor.** `0df0dbd59e` (*"route cut-over meta reads through load_meta (BOM
  fail-closed inversion)"*) drained two hand-rolled `json.loads` reads — a
  fail-closed verdict inverted in the wrong direction. That commit is explicit
  about which half fired: *"`INLINE_META_READ_FLOOR` is deliberately NOT bumped:
  draining these two reads put the inline census back under the existing ceiling
  on its own."* The routed floor was re-pinned only as collateral.

Cost: **1,551 exclusive lines**, of which ~100 are a hand-written dated re-pin
ledger inside one constant's comment block. Of 32 commits touching the file, 9 are
pure re-pins, 5 are genuine logic changes, and 18 are unrelated changes forced to
carry a floor bump.

### Gate 2 — `test_golden_count_ban`

Already demoted to advisory by
[#3458](https://github.com/spec-kitty/spec-kitty/issues/3458) / mission
`ci-pipeline-reinstatement-01M1X35E` WP16, on this recorded evidence:

> a single benign symbol addition anywhere in `tests/` was forcing either a
> spurious escape-hatch annotation or a whole-tree re-freeze on every unrelated
> PR, **for zero real catches** (#3458's own evidence: **0 catches, 2 forced
> annotations**).

Since the demotion (2026-09-07 → 2026-09-14): **zero** conversions, **zero**
baseline actions — and **three PRs still paid the annotation toll**, the most
recent `71d4282521` (#4306) on 2026-09-14. Contributors keep paying a charge the
gate no longer levies.

Lifetime baseline history: 15 commits — **13 whole-tree re-freezes forced by
unrelated additions**, 2 genuine burn-downs, **0 real catches**. The escape-hatch
toll is larger still: **127 commits** adding annotations, **387 live annotation
sites across 194 files**. The classifier also needed a correctness fix of its own
(`f54c14e945`, *"stop golden-count gate taxing honest dynamic-result cardinality
asserts"*) — it was demonstrably taxing correct code.

It is currently **stale-advisory in five directories** untouched by any recent
work: `tests/auth` +1, `tests/ci` +1, `tests/doctrine` +4, `tests/retrospective`
24 vs 21, `tests/specify_cli` 240 vs 238. Nobody has acted on the warning.

Cost: **993 exclusive lines**. `_golden_count_baseline.json` is also a **second
baseline authority** outside the canonical `tests/architectural/_baselines.yaml`,
against the charter's single-canonical-authority principle.

**Correction (post-spec adversarial squad, 2026-09-14).** An earlier draft of this
ADR counted `test_shape_guard_membership.py` (191 lines) as machinery that "exists
only to police the demotion". That is **false**, and the error would have caused a
real enforcement loss. Of its six tests only
`test_shape_guard_demotion_does_not_raise_under_a_manufactured_breach` is
golden-count-specific. Two others hold the **C-007 enforcement canon**:
`test_enforcement_allowlist_set_is_exactly_the_c007_canon` pins the four
always-on allowlists by set-equality against a tuple held in test *code* (so a
yaml-only edit can neither demote a member out nor promote one in), and
`test_enforcement_allowlists_still_carry_real_blocking_assertions` AST-proves each
still contains a real `assert` inside a `test_*` function — an anti-silent-demotion
guard. Its subjects are exactly the four gates this ADR promises to leave
untouched.

Two further facts make the loss concrete. `test_p1_planted_regression.py:242`
branches on `_MEMBERSHIP_PATH.exists()` and **returns early** on a substring check,
so deleting the governing test while keeping the yaml would degrade P1's T080 to
"these three names appear somewhere in a YAML file no test governs". And its
`_ENFORCEMENT_GATE_NAMES` lists only **three** gates — `test_integration_boundary.py`
is in the yaml canon but absent from that fallback, so the membership test is its
only machine cover.

### Gate 3 — marker baseline

Already retired by `177e062694` (#3285). No action.

### Gate 4 — shard-map completeness

The two live tests are **properties, not counts**:

```python
# test_arch_shard_marker_completeness.py:44
invalid = {r["nodeid"]: ... for r in records if len(set(r["markers"]) & markers) != 1}
assert not invalid   # every collected node carries exactly one shard marker
```

`test_fast_tier_marker_completeness.py` has the same shape and parses its roots
and vocabulary **live out of the `Makefile`**, never a hand-copied list.

The friction is the hand-maintained assignment table, and it is asymmetric.
`arch` sets `default_fallback=True` (`tests/_arch_shard_map.py:370`), so an
unregistered file gets a deterministic hash bucket and needs no edit; **120 of its
181 files (66%) ride the fallback with zero maintenance commits**. `next`
deliberately did not opt in, and generated **25 of the last 28** maintenance
commits.

But the decisive fact is that the markers select nothing. `pytest.ini` says so in
its own marker help text, for all six:

> `arch_shard_1: … (history: minted for the arch-adversarial CI pole … **that pole
> no longer exists and no live CI job selects the shard**)`

Verified independently: `arch_shard_*` / `next_shard_*` appear in no workflow, no
`Makefile` target, and no script. Live CI sharding is a **different, independent**
mechanism — `.github/ci-module-registry.yml` → `ci-modules.yml` expands 17 module
rows into 34 matrix leaves, selecting by **directory**, not by marker.

The defect class was real until `e8cc2f444f` (2026-08-27) deleted the
pre-programme workflows that ran these markers as matrix legs. Every registration
commit before that date was a genuine catch; every one after is pure bookkeeping.

The gate cannot even keep its own table healthy: `tests/_next_shard_map.py` holds
**two duplicate rows** — `tests/runtime/test_upgrade_preview_bootstrap.py` at
`:114` and `:126`, `tests/runtime/next/test_cli_guard_family.py` at `:98` and
`:131` — which `dict.fromkeys` silently resolves to shard 2. The completeness test
inspects *applied markers* (always exactly one, by construction of the merged
dict), so it is structurally blind to the corruption.

## Decision Outcome

**Per-ratchet, not blanket.** Each verdict below carries maintainer concurrence
obtained 2026-09-14 per the #2913 ruling.

### 1. `ROUTED_LOAD_META_FLOOR` → **delete the count-floor outright**

Delete the routed-count floor entirely — do not re-pin it. Re-pinning, even to a
low and stable value, keeps the concept, the vocabulary and this ADR alive as
load-bearing, so the next person to move the count reads *"DIRECTIVE_043 collapse
tripwire"* and treats it as protective. It was re-pinned 23 times in 63 days,
caught zero regressions, and once failed a build for reading `meta.json` through
the canonical reader the gate exists to reward (KISS audit, R. Douglass,
2026-09-14).

Remove, in one commit: the `ROUTED_LOAD_META_FLOOR` constant,
`ROUTED_LOAD_META_FLOOR_MARGIN` and its margin assertion, the strict
`assert len(routed) > ROUTED_LOAD_META_FLOOR` anti-vacuity clause,
`EXCLUDED_REL_PATHS`, the `scan_routed_load_meta_calls` scanner and the
`ROUTED_CALLEES` set that fed only it, and all four routed-floor tests (the
predicate, its non-vacuity canary, the real-tree floor, and the mass-allow-list
self-test).

The **real invariant stays a hard gate, unchanged**: the inline-read ceiling
(`INLINE_META_READ_FLOOR = 7`), its margin (mechanic 2 — the actual non-vacuity
guard: the live count must stay within `MARGIN` of the ceiling, so a broken or
empty scan reds), the allowlist's composite-key `{key, rationale, issue}`
requirement, and its stale-entry detection (`allowlist_keys - live_keys` non-empty
fails). That trio *is* #4315's option 3 — "no inline `json.load` of `meta.json`
outside the reader family" — and it already exists, already passes, and has cost
nothing to maintain. The FR-010 single-decoder gate and the independent
`_ACCOUNTED_SITES` census (`test_meta_fail_closed_full_census_contract.py`) retain
the de-routing cover the routed floor claimed.

Doctrinal note: the gate remains non-vacuous under DIRECTIVE_043 after deletion —
its non-vacuity was always carried by the ceiling's margin (mechanic 2), never by
the routed floor. Nothing that prevents vacuous passage is removed.

### 2. `test_golden_count_ban` → **retire, and sweep the annotations**

Delete `tests/architectural/test_golden_count_ban.py` **in full** — the ceiling
guard, the classifier, the scanner, their unit tests and the `--emit-inventory`
entrypoint — together with `_golden_count_baseline.json`, the module's
`shape_guard_membership.yaml` row, and
`test_shape_guard_demotion_does_not_raise_under_a_manufactured_breach` (which
asserts the `shape-guard` class is non-empty and so cannot outlive the row).

**Operator decision, 2026-09-14:** an earlier draft of this verdict retained the
classifier behind `--emit-inventory`. The operator chose wholesale deletion — if
the annotations are swept, the vocabulary that produced them goes too; the
inventory is reconstructible from git history and nothing in-tree consumes it.
This ADR records the reversal rather than letting the decision record and the code
disagree.

**Explicitly NOT deleted**, against the earlier draft:

- `shape_guard_membership.yaml` and the rest of `test_shape_guard_membership.py` —
  see the Correction above. Only the golden-count row and the one demotion-specific
  test go. The `shape-guard` class is left defined but empty.
- `kitty-specs/test-suite-friction-remediation-01KXDKBX/golden-count-inventory.md` —
  it lives in a **prior mission's committed dossier**, which the charter treats as
  an immutable snapshot. Retiring live machinery and rewriting a landed mission's
  artifacts are different acts.

One fold wholesale deletion forces that retaining the scanner would not:
`test_gate_remedy_presence.py:188` registers
`tests/architectural/test_golden_count_ban.py::ratchet_violations` as a
**known-good remedy exemplar** — deliberately chosen as one "this WP did not
author" — and reads the file with `read_text()` at `:200`, so deletion raises
`FileNotFoundError` rather than failing an assertion. Repoint that entry at another
unauthored content-anchored remedy; do not simply drop it, or the property check
loses the independence the entry exists to provide.

Sweep the **387 `# golden-count: cardinality-is-contract` annotations across 194
test files** in the same mission. Leaving them would preserve a toll contributors
demonstrably keep paying after the charge is gone — three PRs did so in the seven
days after the demotion alone.

This supersedes [#3977](https://github.com/spec-kitty/spec-kitty/issues/3977) and
[#3927](https://github.com/spec-kitty/spec-kitty/issues/3927), both of which
report the pre-demotion hard-red that no longer occurs. #3977's own disposition —
*"Do not re-freeze the baseline"* — is honoured: the baseline is removed, not
re-frozen.

### 3. Marker baseline → **already retired; no action**

Recorded so #4315 can close its scope item rather than leaving it open against a
file that has not existed since 2026-08-12.

### 4. Shard maps → **keep the partition properties; retire the `arch`/`next` marker family**

The completeness *properties* are the right instrument and stay. What is retired
is the substrate they police, because nothing selects it:

- `tests/_arch_shard_map.py`, `tests/_next_shard_map.py`, `tests/_shard_registry.py`;
- `tests/test_shard_registry_fallback.py`;
- `tests/architectural/test_arch_shard_marker_completeness.py`;
- the six `arch_shard_*` / `next_shard_*` registrations in `pytest.ini`;
- the registration + marker-application block in `tests/conftest.py`;
- `test_exemption_registry_ratchet.py::test_new_arch_test_files_are_shard_registered`,
  a T057/C-006 check of a property that ceases to exist.

**Explicitly retained**, as different mechanisms with live consumers:

- `tests/architectural/test_fast_tier_marker_completeness.py` — tier markers,
  derived live from the `Makefile`, genuinely select `make test-fast`;
- `tests/architectural/test_module_shard_registry.py` and
  `.github/ci-module-registry.yml` — the live directory-based CI sharding, whose
  own non-vacuity floor is *derived* (`ceiling // 2`), not pinned.

**Folds the deletions force — corrected count and corrected mechanics.** An earlier
draft named "two folds", one of them wrongly. The real shape, measured in
`pyproject.toml`:

`[tool.ruff.format].exclude` carries an entry for **four** of the files these two
verdicts delete — `tests/architectural/test_golden_count_ban.py` (`:1087`),
`tests/_shard_registry.py` (`:974`),
`tests/test_shard_registry_fallback.py` (`:2757`) and
`tests/architectural/test_arch_shard_marker_completeness.py` (`:1060`). All four
entries must be removed, or `test_ruff_format_exclude_ratchet.py::test_every_exclude_entry_exists_on_disk`
reds. The earlier draft named only the last of the four.

The pinned-count coupling was also stated backwards. `_BASELINE_EXCLUDE_COUNT`
(2809) is enforced as `len(entries) <= baseline`, so **removal never requires
touching it** — only growth does. The mandatory half is the entry removal; the
count edit is optional. Stating it the other way round would have sent an
implementer looking for a coupling that does not exist in the direction this work
moves, while leaving the one that does bite unnamed for three of four entries.

`tests/_arch_shard_map.py` and `tests/_next_shard_map.py` carry no exclude entry.
The two duplicate `next` rows and the dead `_gate_read_callshape.py` row disappear
with the tables.

## Consequences

**Good**

- Removes a hard gate sitting at **zero headroom** whose failure mode is punishing
  correct behaviour, and that has never caught a regression in 23 re-pins.
- Removes ~2,500 lines of gate machinery and ~390 annotation sites with a measured
  lifetime catch record of zero.
- Eliminates an estimated ~40 of the last ~70 baseline-maintenance commits across
  these gates.
- Restores single-canonical-authority: `tests/architectural/_baselines.yaml`
  becomes the only frozen-baseline authority.
- Closes #3977 and #3927 as superseded; resolves #4315's four scope items.

**Bad / accepted risk**

- The routed census may now drift far from its floor unobserved. Accepted: the
  *defect* — inline reads regrowing outside the reader family — is caught by the
  retained ceiling + allowlist, which is the gate with the real catch record. A
  falling routed count with a flat inline ceiling is a refactor, not a regression.
- **Deleting the routed floor removes the routing-evidence signal entirely —
  recorded, not papered over (adversarial squad, 2026-09-14).** The pre-deletion
  gate had `EXCLUDED_REL_PATHS` remove `src/specify_cli/mission_metadata.py` and
  `src/specify_cli/task_utils/support.py` from the *inline* scan; those two files
  held 17 of the ~157 routed sites, and inside them the routed floor had been the
  only cover. With the floor deleted — and `EXCLUDED_REL_PATHS` gone with it,
  having measured to hide zero *inline* sites — there is no routed-count
  enforcement anywhere. Accepted: the de-routing defect (replacing canonical-reader
  delegations with hand-rolled parsing) is covered by the independent
  `_ACCOUNTED_SITES` exact-equality census in
  `test_meta_fail_closed_full_census_contract.py` (keyed on `load_meta_fail_closed`,
  floor-independent) plus review; and the routed floor's own record is 23 re-pins,
  zero regression catches, both historical drops answered by lowering the pin
  rather than investigating. An earlier draft planned to keep a small pinned
  decode-count *inside* the two files; outright deletion abandons that mitigation
  as more of the vocabulary the audit calls to remove.
- Retiring the golden-count ceiling means a future `len(X) == N` regrowth is caught
  by review rather than CI. Accepted: it has always been caught by review, since
  the gate caught nothing in its lifetime and has been advisory since 2026-09-07.
- Retiring the shard markers discards the balance-control substrate if
  marker-based sharding is ever reinstated. Accepted: the current substrate is
  demonstrably unmaintained (two duplicate rows it cannot see), and live sharding
  has moved to a directory-based registry. Reinstating would start from that
  registry, not from these tables.
- The annotation sweep touches 194 test files. Accepted deliberately, to stop the
  cargo-culted toll; it is comment-only and behaviour-preserving.

**Corrections to this ADR's own claims (post-spec adversarial squad, 2026-09-14)**

- **"The real invariant stays a hard gate" overstates the retained scanner.** A
  squad lens built a scratch `src/` tree and ran the real `scan_inline_meta_reads`
  against eight plausible new inline reads plus one canonical control: **one
  caught, eight evaded.** The evasions include `json.loads(path.read_bytes())`
  (the read-base matcher only knows `read_text`/`open`), `Path(dir, "meta.json")`
  and `os.path.join(...)` (the join matcher requires a `/` `BinOp`), a module-level
  `META_NAME` constant (it requires a literal), an interprocedural one-line helper,
  and `yaml.safe_load(...)` — which parses JSON correctly and is idiomatic in this
  codebase. **None of this is a regression introduced here** — all eight pass today
  with the margin intact — but the retained gate closes one AST *spelling* of the
  defect class, not the class. The verdicts stand; the confidence behind them is
  hereby narrowed to what was measured.
- **A second, tighter de-routing detector already exists and was unnamed.**
  `tests/specify_cli/test_meta_fail_closed_full_census_contract.py` keeps an
  independent `_ACCOUNTED_SITES` ledger checked for **exact equality** against a
  live scan, keyed on `load_meta_fail_closed`. It does not depend on
  `ROUTED_LOAD_META_FLOOR` and is unaffected by this ADR — so the de-routing class
  retains cover this ADR did not credit.
- **Sequencing dependency (discharged).** This ADR landed first (#4323) and the
  implementing mission (#4359) rebased onto it, so the mission branch carries this
  file and flips it `Proposed` → `Accepted` in a dedicated commit, separate from
  its three workstream commits. Accepted on the operator's direction to land the
  flip with the implementation rather than as a follow-up.

**Neutral**

- The ~2,500-line reduction is not itself the justification — the catch record is.
- This ADR changes no doctrine. DIRECTIVE_043 and both tactics remain in force and
  unedited; verdict 1 deletes a redundant floor whose non-vacuity role the ceiling's margin already carries, and verdicts 2 and 4
  retire gates whose defect classes no longer exist.

## Follow-through

Implementation runs as a governed mission, sequenced so `main` stays green at
every intermediate commit: the routed-floor deletion and each retirement are independent
and land separately. If any verdict's implementation surfaces a consumer this ADR
did not name, that is a finding against this ADR, not a licence to improvise
around it.

## References

- Issues: [#4315](https://github.com/spec-kitty/spec-kitty/issues/4315) (primary),
  [#1931](https://github.com/spec-kitty/spec-kitty/issues/1931) (epic),
  [#2913](https://github.com/spec-kitty/spec-kitty/issues/2913) (sibling +
  binding operator ruling), [#3458](https://github.com/spec-kitty/spec-kitty/issues/3458)
  (demotion precedent), [#3977](https://github.com/spec-kitty/spec-kitty/issues/3977)
  and [#3927](https://github.com/spec-kitty/spec-kitty/issues/3927) (superseded),
  [#3285](https://github.com/spec-kitty/spec-kitty/issues/3285) (marker-baseline
  retirement).
- Doctrine: `packs/built-in/directives/043-close-defect-class-by-construction.directive.yaml`,
  `packs/built-in/tactics/architectural-gate-non-vacuity.tactic.yaml`,
  `packs/built-in/tactics/frozen-baseline-shrink-only-ratchet.tactic.yaml`,
  `packs/built-in/procedures/post-merge-arch-gate-adjudication.procedure.yaml`.
