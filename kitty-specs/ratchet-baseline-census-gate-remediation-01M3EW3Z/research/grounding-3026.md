# #3026 grounding — inert-slot unfireable-owner cap (Architect Alphonso, read-only)

HEAD `34f19c6f` (shallow clone, 50 commits; older history via GitHub API). Issue filed 2026-07-28 against PR #3007.

## TL;DR — the issue's premise ("the gate holds") is false on HEAD

Squash commit `177e0626` (#3285, *assertive-test-suite-sanitation-01KZME3P*, 2026-08-12) cut
`tests/architectural/test_no_inert_schema_slots.py` from ~26 tests to **3** (file is 79 lines today).
Its new docstring says so: "The frozen ledger remains migration debt, not a second test surface. This file
keeps only the live shrink-only gate and a two-sided controlled fault" (`test_no_inert_schema_slots.py:1-6`).
The tests the issue cites (`test_the_unassigned_cap_is_registered_with_the_charter_ratchet`,
`test_the_masking_cap_is_registered_with_the_charter_ratchet`,
`test_a_specified_but_unplanned_mission_resolves_yet_is_not_complete`, the anti-weasel test, the floor tests,
the code-only drift test) **no longer exist anywhere in the repo**.

`grep -rl` over `tests/ src/ scripts/`, excluding `_inert_slots.py` itself, finds **zero consumers** of:
`owner_exists`, `owner_is_complete`, `unresolved_by_completed_owners`, `MAX_UNASSIGNED_ENTRIES`,
`MAX_MASKING_SUPPRESSIONS`, `find_code_only_suppressions`, `code_only_drift`, `load_code_only_record`,
`code_producer_writes`, `MINIMUM_SCHEMA_SLOT_NAMES`/`MINIMUM_MODEL_SLOT_NAMES`, `MINIMUM_*_BASELINE_ENTRIES_STILL_FOUND`.
The only live assertions are: scanner two-sided fault (`:42`), schema `definitions` exclusion (`:52`), and
`new == []` against the baseline (`:62`). The only charter-ratchet link is `baseline_entries` vs
`BASELINE_SLOTS` (`test_ratchet_baselines.py:419-424` and `:581-586`).

So the problem is no longer only that the cap covers a token instead of a property. **No cap is enforced at
all**: not `unassigned`, not masking, and not the anti-weasel owner-completion check. That is a charter §5
*architectural-gate-non-vacuity* breach, because the gate *declares* protections it does not execute.

## 1. `_inert_slots.py` on HEAD (issue line numbers are stale)

| Symbol | Issue cites | HEAD | Behavior still as described? |
|---|---|---|---|
| `MAX_UNASSIGNED_ENTRIES` | :386, `= 23` | `:431`, **`= 9`** (comment `:419-430`: 23→19→9) | Value lowered. Nothing asserts it: **dead** |
| `owner_exists` | :546-564 | `:576-594` | Yes. `mission:<slug>` exists iff `kitty-specs/<slug>/status.events.jsonl` exists (`:557-559`, `:592`). Uncalled |
| `owner_is_complete` | :567-584 | `:597-612` | Yes. `bool(states) and all(lane in COMPLETED_LANES)` (`:610`), so a zero-WP mission is always `False`. Uncalled |
| `unresolved_by_completed_owners` | — | `:615-633` | Anti-weasel check. Uncalled |
| `COMPLETED_LANES` | — | `:460` `{"approved","done"}` | **`canceled` is excluded** (see §2) |
| `MAX_MASKING_SUPPRESSIONS` comment | :635-643, "NOT YET REGISTERED" | `:644-664`, `= 13` | **Finding 2 is already fixed.** The comment now reads "Registered with the charter ratchet: `masking_suppressions` under `test_no_inert_schema_slots` in `_baselines.yaml`, checked by `test_the_masking_cap_is_registered_with_the_charter_ratchet`" (`:660-662`). Commit `2dbd8cb4` (2026-07-27) did it. The comment is stale again in a **new** way: the test it names was deleted by #3285 |
| `_parse_entry` provisional rule | — | `:511-515` | Live (runs at import via `BASELINE_SLOTS`, `:749`). `provisional` implies `owner == unassigned` |

## 2. Baseline census (`_inert_slots_baseline.yaml`, parsed with `load_baseline()`)

The baseline has **38 entries** (not 51). Its `mission:` is `doctrine-silence-guards-01KYFV7Q`. There are no `WP##` owners.

| Owner | Entries | WPs (materialize_snapshot) | `owner_exists` | `owner_is_complete` | Fireable? |
|---|---|---|---|---|---|
| `unassigned` (all 9 `provisional`) | 9 | — | True | False (by construction) | **never** |
| `mission:foundational-values-creed-band-01KYFV8N` | 26 | **0** (event log = 2 lines, SpecifyStarted only, 2026-07-26; spec.md + tasks/README.md only) | True | False | **not while undecomposed** |
| `mission:drg-edge-migration-extractor-retirement-01KYFV8C` | 2 | **0** (same shape, 2026-07-26) | True | False | **not while undecomposed** |
| `mission:mission-type-canonical-source-01M302V9` | 1 (`path_conventions`) | 6: WP01/02/03/06 `approved`, **WP04/05 `canceled`** | True | **False** | **never, a third variant** |

The real unfireable set is 9 + 26 + 2 = **37 of 38** under the issue's zero-WP definition. Under the current
`owner_is_complete` it is **38 of 38**: every row in the baseline is permanently exempt from the anti-weasel check.

**New finding (not in the issue): canceled WPs make a mission owner un-completable.** `COMPLETED_LANES`
excludes `canceled` (`:460`), and `canceled` is terminal (CLAUDE.md status model). So any mission that cancels even one
WP can never satisfy `all(...)` at `:610`. mission-type-canonical-source has finished all its work
(4 approved, 2 canceled), yet its entry is safe forever. The predicate has to treat the terminal set
`{approved, done, canceled}` as complete, with a guard so that an **all-canceled** mission is not "complete".
Whether that guard is needed is an operator ambiguity, Q3.

Other live observations from the probe (these would be red if the deleted tests still existed):
- `ratchet` finds new=0, cleared=`['styleguide-references', 'model']`. Two baseline rows are stale and only produce a warning.
- `code_only_drift` gives **new=[`model` @ `src/charter/offering/schemas/agent-profile.schema.yaml`]**. The slot
  `model` left the findings list because a code producer names it. The likely cause is `Field(..., alias="model")` in
  `src/charter/offering/agent_profiles/profile.py:266` and `schema_models.py:217`; that is a kwarg the code-producer rule scores as a write.
  The code-only record does not list it. This is **exactly the silent-suppression hole** that `8d01e533` closed and #3285
  reopened. Masking rows sit at 13/13, cap 13.
- The anti-weasel check returns `{}` today. It would also return `{}` forever, per the table above.

## 3. Charter-ratchet registration

- `_baselines.yaml:277-298`: `baseline_entries: 38` (`:278`), `unassigned_entries: 9` (`:284`), `masking_suppressions: 13` (`:298`).
- `test_ratchet_baselines.py`: `_REQUIRED_TOP_LEVEL_KEYS` includes `test_no_inert_schema_slots` (`:131`). The `single_baselines` lists
  (`:365`, `:530`) register **only** `baseline_entries`, against `BASELINE_SLOTS`.
- `test_no_unregistered_baseline_keys_are_added` (`:654-690`) checks **top-level keys only**. That means
  `unassigned_entries` and `masking_suppressions` are now **inert sub-keys, read by no comparison**. This is the RL-030
  `test_no_dead_symbols` failure class the ratchet suite was written to kill, one level down. The only
  mention of `unassigned_entries` elsewhere is prose in `test_reference_enum_ratchet.py:192`.
- Finding 2 is **not stale in its original sense** (registration is done and the comment says so). It **is stale in a new sense**,
  because the named reciprocal-assertion test is gone.

## 4. Fix design

### 4a. Precondition: an operator decision on #3285 (blocking)

The code is in an unstable half-state: helpers and `_baselines.yaml` sub-keys advertise protections that nothing executes.
There are two honest end states.

- **(A) Restore.** Re-enable owner-existence, anti-weasel, the cap(s), the code-only drift check and the floors, *then* fix #3026 on top.
- **(B) Retire.** If #3285 deliberately judged the owner/cap machinery low-signal, delete the dead helpers and constants,
  delete the `unassigned_entries`/`masking_suppressions` sub-keys and their comments, fix the baseline header prose
  (`_inert_slots_baseline.yaml:30,70`), and close #3026 as superseded.

This report recommends **(A)**, scoped as below. Under (B) the whole ledger reduces to the single `baseline_entries`
count. With every row unfireable, the baseline would then be a plain allowlist, which is exactly the "allowlist with
better manners" the module docstring warns against (`:620-622`).

### 4b. The #3026 change (assumes A)

```python
TERMINAL_LANES = frozenset({"approved", "done", "canceled"})

def owner_can_complete(owner, *, root, mission) -> bool:
    """Can the anti-weasel check ever fire for *owner* in the tree as it stands?"""
    if owner == UNASSIGNED_OWNER:
        return False
    if owner.startswith(_MISSION_OWNER_PREFIX):
        return bool(_mission_work_packages(root, owner.removeprefix(_MISSION_OWNER_PREFIX)))
    return owner in _mission_work_packages(root, mission)   # WP## owner

def unfireable_entries(baseline, *, root) -> list[BaselineEntry]: ...
MAX_UNFIREABLE_ENTRIES = 37   # or 38, see Q3
```

- Name it `owner_can_complete` (or `_owner_is_fireable`), **not** `_can_ever_complete`. A zero-WP mission *can* gain WPs,
  so the predicate describes the current tree, not all time. It should be public, because the tests import it (the `__all__` convention, charter §`__all__`).
- Also redefine `owner_is_complete` over terminal lanes: `states and all(lane in TERMINAL_LANES) and any(lane != "canceled")`.
  This closes the canceled-WP variant.
- Delete `MAX_UNASSIGNED_ENTRIES` (and its `__all__` entry `:46`). Keep the `provisional ⇒ unassigned` rule.
- `_baselines.yaml`: replace `unassigned_entries: 9` with `unfireable_entries: 37  # justification: ...`, carrying the per-owner breakdown in the comment.
- Registration uses the reciprocal-assertion pattern, as `2dbd8cb4` did. It is **not** a `single_baselines` row: that list compares
  `len(collection)`. You *could* register a module-level `UNFIREABLE_SLOTS` frozenset computed at import, like `BASELINE_SLOTS`,
  but that runs `materialize_snapshot` over kitty-specs at import time for every importer, so it is not recommended.
- Harden `test_no_unregistered_baseline_keys_are_added` to cover **sub-keys**. Each sub-key under
  `test_no_inert_schema_slots` must be in an explicit allowed set, each paired with an asserting test. This stops the next inert sub-key.

### 4c. Shrink-only semantics and time-dependence

- **Shrink direction.** When a zero-WP mission runs `/spec-kitty.tasks` and gains WPs, its rows leave the unfireable set: count 37 → 11.
  The assertion must be `len(unfireable) <= cap`, green on shrink, with a `record_property` nudge to lower the cap. It must not be `==`,
  because then the *owning mission's* `finalize-tasks` would red an architectural gate it does not touch.
- **Growth without a baseline edit (the flakiness risk).** The count depends on kitty-specs event logs, not on the baseline file, so it can
  **grow** through a status change in an *unrelated* mission. Examples:
  - With the old `COMPLETED_LANES`, a WP owner or mission gets a WP canceled. The terminal-lanes fix removes this case.
  - A mission's event log is deleted or moved. `owner_exists` catches that loudly, which is correct.
  - A future "reset WPs" operation.

  After the terminal-lanes fix, the only growth path is adding rows, which also requires a `baseline_entries` bump. That is good: growth is
  attributable to the diff that caused it.
- **Branch and partition skew.** Status for coord-topology missions lives on the coord branch (CLAUDE.md "Status source of truth").
  The primary checkout's `kitty-specs/<slug>/status.events.jsonl` can lag. The result is deterministic per commit (no wall clock),
  but it reflects *merged* status, so it will not lead to flakiness, only to lag. Document it.
- **No wall-clock dependence.** `materialize_snapshot` is the Lamport reducer, which is read-only per the docstring at `:562-568`.
- **Performance.** Three to four `materialize_snapshot` calls, memoize per owner as `unresolved_by_completed_owners` already does. Negligible.

### 4d. Non-vacuity and self-mutation (charter §5, architectural-gate-non-vacuity)

- A `tmp_path` fixture: `kitty-specs/probe-<ulid>/status.events.jsonl` holding a single SpecifyStarted line. Verified on HEAD: with the file copied from
  foundational-values-creed-band, `owner_exists` returns True, WPs are `{}`, and `owner_is_complete` returns False. Plus a baseline with one `mission:probe-…` row.
  Assert that `unfireable_entries` includes it. Then append one WP `planned→approved` transition and assert that the row **leaves** the set (two-sided).
- A mission whose WPs are {approved, canceled}: assert that `owner_is_complete` returns True. A mission whose WPs are all canceled: assert False.
- Live-tree floor: `len(unfireable_entries(live)) >= 1`, or pin that `unassigned` rows are counted, so that a predicate collapsing to "nothing is unfireable" reds.
- A mutation on a copy of the live baseline, plus one zero-WP mission row, reds the cap assertion.

## 5. RED-first acceptance (ATDD, C-011)

**File:** `tests/architectural/test_no_inert_schema_slots.py`

1. `test_a_zero_wp_mission_owner_counts_against_the_unfireable_cap(tmp_path)`.
   Builds the fixture above and asserts `[e.owner for e in unfireable_entries(bl, root=tmp_path)] == ["mission:probe-01AAAAAA"]`.
   **Red today.** Confirmed: `ImportError: cannot import name 'MAX_UNFIREABLE_ENTRIES'` (the same is true of `unfireable_entries`).
2. `test_live_unfireable_entries_do_not_exceed_the_registered_cap()`.
   Asserts `len(unfireable_entries(load_baseline(), root=_REPO_ROOT)) <= _baselines["test_no_inert_schema_slots"]["unfireable_entries"] == MAX_UNFIREABLE_ENTRIES`.
   Red today with a KeyError or ImportError.
3. `test_a_mission_with_canceled_wps_can_complete(tmp_path)`.
   A **behavioral** red on HEAD: `owner_is_complete` returns False for {approved, canceled} (demonstrated live on mission-type-canonical-source).
4. Plus the restorations, if the operator picks (A): owner-exists over the live baseline, `unresolved_by_completed_owners(...) == {}`, `code_only_drift == ([], [])`
   (**red today** on `model`), and the two floor tests.

**Blast radius (per CLAUDE.md §6).** Cross-cutting, because it touches `_baselines.yaml`:
```
make test-fast
.venv/bin/python -m pytest tests/architectural/test_no_inert_schema_slots.py tests/architectural/test_ratchet_baselines.py tests/architectural/test_reference_enum_ratchet.py -q
.venv/bin/python -m pytest tests/architectural/ -q          # _baselines.yaml is cross-cutting
.venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q
ruff check tests/architectural && ruff format --check tests/architectural && mypy tests/architectural/_inert_slots.py
```
Measured on HEAD: `test_no_inert_schema_slots.py` + `test_ratchet_baselines.py` gave 24 passed, 1 warning, in 112 s.

**Size.**
- #3026 alone (predicate, terminal-lanes fix, cap, registration, sub-key hardening, 3-4 tests, comment fixes): **one small WP**, about 150-250 LOC including tests.
- Restoring the #3285-deleted checks (option A): a **second WP**. It must first disposition `model` (add a code-only record row, and/or re-baseline it) and delete the two
  cleared baseline rows (`styleguide-references`, `model`) with a `baseline_entries` 38 → 36 or 37 adjustment. Order: WP-restore first, then WP-#3026.
  The two WPs can also be one squashed PR.

## Operator ambiguities

- **Q1 (blocking).** Was #3285's removal of the owner/cap/code-only tests intentional (option B: retire the machinery) or collateral damage (option A: restore)?
  Its docstring reads as deliberate. The dead helpers, and the `_baselines.yaml` sub-keys still labeled "registered", read as accidental.
- **Q2.** One cap (`MAX_UNFIREABLE_ENTRIES`, as the issue proposes) or keep `unassigned` as a tighter sub-cap too? `unassigned` rows are all
  `provisional`, meaning nobody owns them. Mission rows at least have an accountable spec. A single cap lets 26 foundational-values rows be "traded" for 26 new `unassigned` rows.
- **Q3.** Does `canceled` count as complete? If it does, mission-type-canonical-source's `path_conventions` row **immediately trips** the anti-weasel check.
  That row needs re-owning (#2652 is deferred), and the cap becomes 37. If it does not, the cap is 38 and the variant stays latent.
- **Q4.** foundational-values-creed-band and drg-edge-migration have sat specified-only since 2026-07-26 (two months) and hold 28/38 rows. Should a
  zero-WP owner also carry an age limit or tracker link, or should those rows be re-owned to `unassigned`? That would blow the 9-cap, which is the issue's point.
- **Q5.** Parent epic #5104 ("Test suite friction — ratchet, baseline & census gates") pulls toward fewer gates. Restoring the checks in option A adds gate surface, so it should be squared with that epic's intent.
