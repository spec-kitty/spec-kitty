> Hostname cleanup: `retired-host.example` redacts the former Team Kitty hostname in historical evidence; the current endpoint is `https://team.spec-kitty.ai`.

# R1b Convergence Plan — Closing #3121 (`SPEC_KITTY_HOME` pin census owner-adoption)

**Status:** SCOPING (read-only analysis). Nothing in the tree was mutated to produce this document.
**Checkout analysed:** `/home/stijn/Documents/_code/SDD/fork/SHADOW_CLONES/mission-3121-clone`
(branch `kitty/fix-home-pin-census-owner-adoption-3121`, rebased on `upstream/main`).
**Author lens:** structural equivalence to the canonical owner + the landed ablation adjudication.

---

## 0. Executive summary

The R1a guard/census landed and is GREEN. It is, by its own spec's words, a **"hard, shrink-only
ratchet"** enforcing three *joint* invariants
(`kitty-specs/home-pin-census-owner-adoption-01M05C50/spec.md:13-16`):

1. `census == anchor` — `test_spec_kitty_home_pin_census.py:364-371` (t023)
2. `discover(tests) − E == anchor` — `test_spec_kitty_home_pin_census.py:353-361` (t023)
3. `discover(tests) == census ∪ E` — `test_spec_kitty_home_pin_census.py:446-458` (t024)

The anchor is 40 rows frozen from an immutable evidence file
(`tests/architectural/census/spec_kitty_home_pin_anchor.yaml`, `resolved_at_sha: fe5d492ed…`,
`members.json`), and the census (`tests/architectural/census/spec_kitty_home_pin_R1a.yaml`,
40 rows) must equal it exactly.

**Two findings dominate everything else in this plan:**

- **FINDING A — the #3121 thesis is confirmed by the bodies.** The ~22 `_isolated_home`-style
  fixtures are *not* one seam. Reading all 40 member bodies (cited per row in §4) shows they split
  into at least six behaviourally-distinct shapes: pure `SPEC_KITTY_HOME=tmp_path/"home"`,
  `HOME`/`LOCALAPPDATA` co-pins (partitions B1/B2), counter-autouse `delenv SPEC_KITTY_ENABLE_SAAS_SYNC`,
  `setattr(is_saas_sync_enabled)` + `ProjectSyncStore` publishes, `SPEC_KITTY_SAAS_URL` pins, and
  inline test-body pins entangled with per-test directory setup. **The genuinely
  provable-equivalent-to-`canonical_home` class is only 2 members** (`body_queue_purge_differential`,
  `per_project_report`); a further ~12 are convergeable *with per-member confirmation*; the
  remaining ~26 are MUST-STAY (different seam) or DELETION-SCOPE (out of #3121).

- **FINDING B — a hard blocker: the tombstone burn-down path is NOT wired to the binding
  invariants.** The tombstone limb (`_home_pin_verdict.evaluate` → `census_hash_ok`,
  `with_tombstones`/`tombstone_keys`) feeds **only** the t024 hash limb
  (`_home_pin_verdict.py:140-144`). The two **t023 real-tree equalities compare the shrunken
  census/`discover` directly against the frozen 40-row anchor with no tombstone term**
  (`test_spec_kitty_home_pin_census.py:361,371`; `anchor()` at `:226` just loads the frozen file).
  Therefore **removing any real member reds t023×2 even with a correct tombstone.** The
  "shrink-only" ratchet, as landed, cannot actually shrink. Wiring t023 to the tombstone set is a
  **prerequisite guard-evolution op** (Op 0) that must land before *any* member is converged, and it
  edits a meta-test R1a froze — so it needs explicit architect/operator awareness even though it is
  sanctioned R1b work (the R1a record itself states `census == ∅` is R1b's DoD;
  issue #3121 "R1a — the guard half" comment, item 3).

**Net:** #3121 is *not* closeable by "converge + tombstone" ops alone in the guard's current shape.
It is closeable as a **two-phase mission**: Op 0 completes the shrink mechanism; Ops 1..n converge
the provable class and tombstone each removal. Full `census == ∅` is a *further* horizon requiring
deletion missions and a manifest-with-`reason` mechanism that does not yet exist (§5).

---

## 1. Authoritative record of the halt-set P (verified, not re-derived)

Source of truth: the pre-convergence ablation of the halted mission
`isolated-home-pin-convergence-01KZCTWC`, recorded at
`kitty-specs/isolated-home-pin-guard-r1a-01KZNMA3/research/m4_ablation_evidence/` — `VERDICT.md`,
`TABLES.md`, `RESIDUALS.md` — and the operator's **HALT AND RE-SCOPE** sign-off on issue #3121
(comment `#issuecomment` dated 2026-08-07).

- Ablation scope was a **28-member behaviour class** (the fixture-shaped subset), not the full
  40-row census. Partitions: **A = 17** (does not re-pin `HOME`), **B1 = 9** (`HOME → tmp_path/"home"`),
  **B2 = 2** (`HOME → tmp_path/"user-home"`) — `VERDICT.md:38-42`.
- `P` = members passing **arm 1** (pop `SPEC_KITTY_HOME`) *and* the **repeated/interleaved arm**.
  **`|P| = 5`** (`VERDICT.md:80`, `TABLES.md:37-42`):

  | # | member | arm2 | operator disposition |
  |---|--------|------|----------------------|
  | 1 | `tests/delivery/test_body_queue_purge_differential_3030.py::_isolated_home` | **RED** (dir load-bearing) | conversion candidate → **STAYS in adopting set** (converge to owner) |
  | 2 | `tests/sync/test_daemon_publish_consent_3030.py::_isolated_home` | **RED** (dir load-bearing) | conversion candidate → **STAYS in adopting set** (converge to owner) |
  | 3 | `tests/delivery/test_purge_all_body_uploads_3030.py::_isolated_home` | GREEN (neither load-bearing) | **deletion candidate — OUT OF SCOPE** |
  | 4 | `tests/delivery/test_purge_all_events_3030.py::_isolated_home` | GREEN | **deletion candidate — OUT OF SCOPE** |
  | 5 | `tests/specify_cli/identity/test_identity_value_faults_3030.py::TestThePolicyGate…_isolated_home` | GREEN (6 tests only — see caveat) | **deletion candidate — OUT OF SCOPE** |

- **Caveat on member 5** (`VERDICT.md:114-119`, `RESIDUALS.md:233-239`): its arm-2 `147/147` GREEN is
  a `self`-bound class-method fixture governing only the **6** tests in
  `TestThePolicyGateAnswersInsteadOfCrashing`; the other 141 nodes are not evidence about it.
- **The ablation is a DELETION study** ("is the pin redundant?"), *not* a convergence study. arm-1
  colour therefore does **not** decide convergence-to-`canonical_home`: a member can be arm-1-RED
  (pin load-bearing, cannot be *deleted*) yet still converge (because `canonical_home` supplies an
  equivalent per-test pin). Convergence is decided by **structural equivalence of the fixture body**
  to `canonical_home` + the behaviour tests staying green after the swap. §4 classifies on that basis.

---

## 2. The canonical owner, and what "provably equivalent" means

`tests/conftest.py:372-408` — `canonical_home(monkeypatch, tmp_path) -> None`:

```python
home = tmp_path / "home"
home.mkdir(parents=True, exist_ok=True)
monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
```

Function-scoped, **non-autouse**, returns `None`, sets **only** `SPEC_KITTY_HOME` (not
`HOME`/`USERPROFILE`/`LOCALAPPDATA`/XDG), creates the dir. It is exempt (`E`) and is the ONLY
exempt owner (`_home_pin_exempt.py:50-53`). A test that **requests** it (as a param or via
`usefixtures`) and writes no `setenv` of its own leaves `discover()` (the scanner keys on
`setenv("SPEC_KITTY_HOME", …)` write sites — `_home_pin_scan.CENSUS_PATH` walk; `OWNER_PARAM_NAMES`
at `_home_pin_scan.py:347` treats an owner-named param as `tmp_path`, adding no site).

**PROVABLE-CONVERGE ⇔** the member's body is behaviourally equivalent to the three lines above:
sets `SPEC_KITTY_HOME` to `tmp_path/"home"` (+ optional mkdir) and does **nothing else
load-bearing**. Anything more — a second env var, a `delenv`, a `setattr`, store setup, a returned
value, a non-`"home"` subdir — makes it a *different* seam.

**Autouse note (mechanism-relevant):** almost every `_isolated_home` fixture is
`@pytest.fixture(autouse=True)` (e.g. `test_body_queue_purge_differential_3030.py:17`,
`test_per_project_report_3030.py:44`). Convergence of an autouse fixture is therefore **not** a
param swap on consumers — it is: delete the local fixture, add
`pytestmark = pytest.mark.usefixtures("canonical_home")` at module level (canonical_home lives in
the root conftest, reachable from every test dir). The landed R1a fix used the param idiom instead
(`tasks.md:40-52`: `def test_...(canonical_home: None) -> None: del canonical_home`); both idioms
remove the `setenv` site.

---

## 3. FINDING B in detail — the tombstone path does not reach t023 (the blocker)

The removal mechanism the task assumes:

- `_home_pin_verdict.with_tombstones(baseline_text, keys)` writes `tombstones: [...]` into the
  baseline; `tombstone_keys()` reads them back (`_home_pin_verdict.py:191-198, 251-259`).
- `evaluate()` computes `census_hash_ok = hash_of_key_set(census | tombstone_keys) == baseline_hash`
  (`_home_pin_verdict.py:140-144`). So a row removed from the census **and** tombstoned keeps the
  **hash** limb green, and `unexpected`/`stale` also go quiet once the pin is gone from the tree.
- **t024 is fully tombstone-aware** and is proven on the real tree:
  `test_t024_a_real_row_removal_reds_even_with_a_tombstone_covering_the_hash`
  (`test_spec_kitty_home_pin_census.py:477-508`) confirms the ordering — a tombstone **without** the
  pin actually removed still reds (the site is still `discover`ed → `unexpected`). This is the t024/t025
  guarantee: **a tombstone must correspond to a real adjudication** (the definition must be GONE from
  the tree, not merely tombstoned). Confirmed. §6 respects this ordering.

**What is NOT wired:** the two t023 equalities bypass `evaluate` and compare directly to the frozen
anchor:

```python
# test_spec_kitty_home_pin_census.py
:361  assert repo_rooted(discovered_keys()) - repo_rooted(exempt_keys()) == anchor()   # discover − E == anchor(40)
:371  assert repo_rooted(verdict.census_keys(census_text())) == anchor()                # census == anchor(40)
:226  def anchor() -> ...:  # loads the frozen 40-row anchor, no tombstone subtraction
```

Converge one member → `discover` drops it (39) and the census row is dropped (39) → both `:361`
and `:371` red against `anchor() == 40`. **No tombstone term exists on either side.** And the anchor
cannot legitimately shrink: `test_t023_the_frozen_anchor_re_encodes_members_json_and_never_re_decides_it`
(`:384-410`) pins the anchor to `members.json`, which is "the one artefact this Mission must never
edit" (spec.md `C-001`; `tasks.md:56`); re-freezing the anchor is explicitly **disqualified**
(spec.md:45-47). Containment (`discover − E ⊆ anchor`) is also barred by design — t024's docstring
"SET EQUALITY, never containment" (`:446-452`) and spec §0.4.

**Op 0 (guard evolution) is therefore mandatory before any convergence:** extend the two t023
equalities to subtract the *adjudicated-and-removed* key set (the tombstones) from the anchor
target, i.e.

```
discover(tests) − E == anchor − tombstoned      (:361 evolved)
census             == anchor − tombstoned      (:371 evolved)
```

and add a t023-level meta-test mirroring t024's `:477` guarantee (a tombstone whose pin is still in
the tree must still red — so t023 cannot be bought off either). This edits the frozen meta-test file
but is *sanctioned* R1b work (the R1a record names `census == ∅` as R1b's DoD). It must preserve the
ratchet: a bare removal with no tombstone still reds; a tombstone with the pin still present still reds.

---

## 4. Per-member classification (all 40, cited)

Legend — **PC** = Provable-Converge (clean); **JC** = Judgement-Converge (convergeable after a named
1-line confirmation); **CR** = Converge-with-Residual (converge the home dimension, retain an extra
load-bearing pin); **DS** = Deletion-Scope (arm-2 GREEN; belongs to a deletion mission, not #3121);
**MS** = Must-Stay (genuinely different seam). Partition per `TABLES.md`; “extra” = load-bearing
behaviour beyond `canonical_home`.

### 4.1 PROVABLE-CONVERGE (clean) — 2

| # | member (file :: qualname) | body (cite) | part. | ablation | class |
|---|---|---|---|---|---|
| 10 | `tests/delivery/test_body_queue_purge_differential_3030.py::_isolated_home` | setenv `tmp_path/"home"` only, no mkdir (`:17-19`) | A | arm1 PASS, arm2 **RED**, **in P** → owner-convert | **PC** |
| 15 | `tests/delivery/test_per_project_report_3030.py::_home` | `home=tmp_path/"home"; setenv(home)` only, no mkdir (`:44-47`) | A | arm1 RED (wants pin), pure body | **PC** |

`canonical_home` additionally `mkdir`s the dir — strictly safer for #10 (arm-2-RED = dir is
load-bearing; production also re-creates it on demand, `VERDICT.md:334-336`).

### 4.2 JUDGEMENT-CONVERGE — ~11 (each needs the named confirmation)

| # | member | extra beyond owner | confirmation needed | class |
|---|---|---|---|---|
| 21 | `tests/sync/test_body_drain_consent_3030.py::_isolated_home` (`:49-55`) | redundant `setenv SPEC_KITTY_ENABLE_SAAS_SYNC "1"` | root autouse `_enable_saas_sync_feature_flag` (`conftest.py`) already sets it =1 ⇒ drop is behaviour-preserving | **JC** |
| 14 | `tests/delivery/test_nfr003_predicate_cost_3030.py::_consent` (`:70-79`) | redundant SAAS set (no store) | same autouse confirmation | **JC** |
| 22 | `tests/sync/test_body_upload_consent_3030.py::_isolated_home` (`:61-73`) | SAAS set + comment defends it for `locate_project_root` | confirm autouse covers it AND no test in file asserts the *fixture-scoped* set | **JC** |
| 20 | `tests/specify_cli/sync/test_local_commit_purge_3030.py::test_the_flush…` (inline `:434-436`) | **delenv SAAS** (counter-autouse) | ⚠ delenv is load-bearing — see MS note; likely **MS** not JC | **MS/JC** |
| 30 | `tests/sync/test_legacy_queue_precondition_3030.py::test_a_credentials_read_failure…` (inline `:89`) | pure home inline; sibling non-member pin at `:26` (`tmp_path/"runtime"`) must not be touched | surgical single-line convert (add `canonical_home` param, drop `:89`) | **JC** |
| 31 | `tests/sync/test_routing.py::test_opt_out_purge_targets…` (inline `:300`) | pure home inline; MANY sibling non-member pins (`home/".spec-kitty"` at `:131,158,182,328,388,424,525`) | surgical single-line convert of `:300` only | **JC** |
| 35 | `tests/upgrade/migrations/test_m_0_6_7_ensure_missions.py::test_detect_skips_when_global_runtime_is_configured` (`:24-27`) | inline; `home=tmp_path/"home"` reused for `home/cache/version.lock` writes | keep `home=` for cache writes, drop the setenv line; owner pins same path | **JC** |
| 36 | `…test_m_0_6_7_ensure_missions.py::test_detect_still_repairs_metadata_less_legacy_repo` (`:55-58`) | as #35 | as #35 | **JC** |
| 37 | `tests/upgrade/test_compat.py::test_uses_centralized_runtime_does_not_assume_metadata_less_repo_is_2x` (`:20-23`) | as #35 | as #35 | **JC** |
| 38 | `tests/upgrade/test_compat.py::test_uses_centralized_runtime_treats_metadata_less_worktree_as_runtime_managed` (`:45-48`) | as #35 | as #35 | **JC** |
| 39 | `tests/upgrade/test_m_0_12_0_documentation_mission_unit.py::test_detect_skips_when_global_runtime_is_configured` (`:58-61`) | as #35 | as #35 | **JC** |
| 40 | `…test_m_0_12_0_documentation_mission_unit.py::test_detect_still_repairs_metadata_less_legacy_repo` (`:80-83`) | as #35 | as #35 | **JC** |

(#20 listed here for adjacency but is really MS — its `delenv` is counter-autouse; do not convert.)

### 4.3 CONVERGE-WITH-RESIDUAL — 1

| # | member | extra | note | class |
|---|---|---|---|---|
| 29 | `tests/sync/test_daemon_publish_consent_3030.py::_isolated_home` (`:71-84`) | `SAAS set` + **`SPEC_KITTY_SAAS_URL="https://retired-host.example"`** | arm2 **RED**, **in P** ⇒ owner-convert the home dimension, but `SAAS_URL` is set by no autouse and must be retained (keep a one-line residual pin, or a tiny local `saas_url` fixture). Converting drops it silently otherwise. | **CR** |

### 4.4 DELETION-SCOPE (arm-2 GREEN; OUT OF #3121) — 3

| # | member | body | note | class |
|---|---|---|---|---|
| 16 | `tests/delivery/test_purge_all_body_uploads_3030.py::_isolated_home` (`:27-30`) | setenv only, pure | structurally PC, but arm2 GREEN ⇒ **does not need home** ⇒ operator ruled deletion candidate, "deletion out of this Mission's scope" | **DS** |
| 17 | `tests/delivery/test_purge_all_events_3030.py::_isolated_home` (`:40-43`) | setenv only, pure | same | **DS** |
| 18 | `tests/specify_cli/identity/test_identity_value_faults_3030.py::TestThePolicyGate…_isolated_home` (`:295-298`) | setenv + `os.makedirs`; class-scoped, 6 tests | same; DELETE via a deletion mission, not converge (see caveat §1) | **DS** |

Converging the DS trio would "adopt an owner they do not need" and pre-empt the deletion mission's
adjudication — leave them for the sequenced deletion follow-on (`RESIDUALS.md` R8).

### 4.5 MUST-STAY — counter-autouse `delenv` (owner would leave SAAS armed) — 4

| # | member | extra (cite) |
|---|---|---|
| 20 | `test_local_commit_purge_3030.py::test_the_flush…` inline | `delenv SPEC_KITTY_ENABLE_SAAS_SYNC` (`:436`) |
| 24 | `tests/sync/test_consent_read_fault_3030.py::_isolated_home` | setenv+mkdir + **`delenv SAAS`** (`:45-47`) — docstring says "arming env var deleted"; body confirms |
| 25 | `tests/sync/test_consent_resolver_3030.py::_isolated_home` | setenv + **`delenv SAAS`** (`:39-40`) |
| 19 | `tests/specify_cli/sync/test_local_commit_consent_3030.py::_isolated_home` | setenv+mkdir + **`delenv SAAS`** (`:47-49`) |

Dropping the `delenv` and adopting `canonical_home` leaves `SAAS=1` (from the autouse) → the test
now proves the opposite of what it asserts. MUST-STAY unless the `delenv` is preserved separately.

### 4.6 MUST-STAY — `setattr` / `ProjectSyncStore` publish setup — 3 (+2 above overlap)

| # | member | extra (cite) |
|---|---|---|
| 23 | `tests/sync/test_capture_gate_project_identity_3030.py::_isolated_home` | delenv SAAS + `setattr(is_saas_sync_enabled, True)` + `ProjectSyncStore.publish_project_only` (`:47-68`) |
| 32 | `tests/sync/test_ws_publish_consent_3030.py::_isolated_home` | delenv SAAS + `setattr` + store publish (`:51-72`) |
| 11 | `tests/delivery/test_dispatch_window_consent_3030.py::_consent_records` | SAAS set + `ProjectSyncStore` cutover loop (`:144-155`) |
| 12 | `tests/delivery/test_liveness_predicate_before_limit_3030.py::_consent` | SAAS set + store loop (`:71-80`) |
| 13 | `tests/delivery/test_nfr002_loop_permanence_3030.py::_consent_records` | SAAS set + store loop (`:98-107`) |

### 4.7 MUST-STAY — `HOME`/`USERPROFILE`/`LOCALAPPDATA` co-pin (different seam) — 13

| # | member | extra (cite) | part. |
|---|---|---|---|
| 1 | `tests/cli/commands/test_sync_commands.py::_isolated_home` | +`HOME`+`LOCALAPPDATA` (`:57-59`) | B1 |
| 2 | `…/test_sync_doctor_consent_health_3030.py::checkout` | +HOME+LOCALAPPDATA+`SPECIFY_REPO_ROOT`+`COLUMNS`, returns `Path` (`:106-114`) | B1 |
| 3 | `…/test_sync_doctor_per_project_3030.py::_isolated_home` | +HOME+LOCALAPPDATA+COLUMNS (`:106-113`) | B1 |
| 4 | `…/test_sync_doctor_tracker_egress_3108.py::doctor_environment` | +HOME+LOCALAPPDATA+COLUMNS, returns `Path` (`:127-132`) | B1 |
| 5 | `…/test_sync_migrate_backfills_h4.py::_isolated_home` | `SPEC_KITTY_HOME=tmp_path/"home"` + **`HOME=tmp_path/"user-home"`** (`:33-35`) | **B2** |
| 6 | `…/test_sync_now_empty_selection_t005.py::_now_machinery` | +`HOME=user-home`+SAAS+COLUMNS, returns `list` (`:83-88`) | **B2** |
| 7 | `…/test_sync_purge_3030.py::checkout` | +HOME+LOCALAPPDATA+REPO_ROOT+COLUMNS, returns `Path` (`:121-133`) | B1 |
| 8 | `…/test_sync_report_label_is_a_purge_selector_3030.py::checkout` | +HOME+LOCALAPPDATA+REPO_ROOT+COLUMNS, returns `Path` (`:78-90`) | B1 |
| 9 | `…/test_sync_status_per_project_3030.py::_isolated_home` | +HOME+LOCALAPPDATA+COLUMNS (`:113-120`) | B1 |
| 26 | `tests/sync/test_consent_fault_vocabulary_3030.py::home` | +HOME+LOCALAPPDATA, returns `Path` (`:58-64`) | B1 |
| 27 | `tests/sync/test_consent_field_fault_3030.py::_isolated_home` | +HOME (`:43-44`) | B1 |
| 28 | `tests/sync/test_consent_write_refusal_3030.py::home` | +HOME+LOCALAPPDATA, returns `Path` (`:40-45`) | B1 |
| 33 | `tests/sync/tracker/test_tracker_egress_refusal_3108.py::_isolated_home_and_arming` | +HOME+SAAS, returns `Path`, explicit arming (`:188-199`) | B1 |

Members 4 and 33 are the two that landed post-freeze via PR #3108 (issue #3121 "R1a — the guard
half" comment, item 4) — both partition-B1 traps, both genuinely different seams.

### 4.8 MUST-STAY — nested-context inline pin (no fixture form) — 1

| # | member | why (cite) |
|---|---|---|
| 34 | `tests/sync/tracker/test_tracker_egress_refusal_3108.py::test_bind_counter_wrapper…::_run_once` | pin lives inside a nested `with MonkeyPatch.context() as mp:` helper called twice, `mp.setenv(SPEC_KITTY_HOME…)` + SAAS (`:1122-1130`). A fixture (`canonical_home`) cannot be injected into a nested helper; this is the `:1165` drift-prone site the anchor header warns about. MUST-STAY. |

### 4.9 Tally

`PC 2 · JC 11 · CR 1 · DS 3 · MS(delenv) 4 · MS(store/setattr) 5 · MS(HOME) 13 · MS(nested) 1 = 40` ✓
(Member #20 counted once, in MS-delenv.)

**Convergence-eligible in #3121 = PC(2) + JC(11) + CR(1) = 14 maximum.** MUST-STAY(23) and
DELETION-SCOPE(3) do not converge here.

---

## 5. Definition of Done

**#3121 as re-scoped ("converge only the provable class") — the closeable DoD:**

1. **Op 0 landed:** t023 (`:361`, `:371`) subtracts the tombstoned set from the anchor; a new
   t023-level meta-test proves a tombstone whose pin is still in the tree still reds (ratchet
   preserved). t024/t025 unchanged and green.
2. **PC(2) converged and tombstoned:** `body_queue_purge_differential::_isolated_home` and
   `per_project_report::_home` request `canonical_home`, their local fixtures deleted, their pins
   gone from the tree, one tombstone each in the baseline. Census 40 → **38**.
3. Optionally JC/CR members folded in per §6, each behind its named confirmation. Best-case census
   40 → **26** (14 converged).
4. **Guard GREEN** on the full census suite; **ratchet still bites** (a re-injected spurious
   `SPEC_KITTY_HOME` pin reds; a tombstone without a real removal reds — the R1a `tasks.md:T003`
   red-injection proof, extended to the tombstone polarity).
5. Every removed member has a tombstone whose key is the exact anchor 3-tuple, and a recorded cause
   (convergence adjudication) in the mission record. MUST-STAY(23) and DS(3) are documented as
   out-of-scope with their reasons pointing at §4.

**Expected final census count under #3121:** **38** (strict provable minimum) to **26** (all JC/CR
folded). **NOT zero.**

**The far-horizon R1b DoD is `census == ∅`** (issue #3121 "R1a — the guard half", item 3), which is
**out of this plan's scope** and requires, additionally: (a) deletion missions for the DS trio and
any other now-dead pins (`RESIDUALS.md` R8 sequencing); (b) a **manifest-with-`reason` artefact** so
genuinely-load-bearing MUST-STAY members can be *promoted off the census* with a measured cause — a
mechanism that **does not exist today** (the census columns carry no `reason`;
`test_spec_kitty_home_pin_census.py:121-124`). Until that manifest exists, the 23 MUST-STAY members
**cannot** leave the census, so `census == ∅` is unreachable and #3121 should be closed on the
narrower "provable class converged" DoD, with a follow-on issue opened for the manifest mechanism.

---

## 6. Proposed op series (each op = one subagent = one commit)

Ordering keeps every invariant consistent after each commit. **Op 0 is a hard gate** for all others.

| Op | Scope | Mechanism | Model | Verify (must pass before commit) |
|----|-------|-----------|-------|----------------------------------|
| **0** | Guard evolution — wire t023 to tombstones | Edit `test_spec_kitty_home_pin_census.py:353-371` so both equalities compare against `anchor() − tombstoned`; add a t023 meta-test (tombstone + pin-still-present ⇒ red). No census/anchor/`members.json`/`E` edits. | **Strong** (judgement; edits a frozen meta-test; needs architect/operator sign-off per charter architectural-gate discipline) | Full `pytest tests/architectural/test_spec_kitty_home_pin_census.py` GREEN with `tombstones: []`; new meta-test RED-then-GREEN as designed; `test_home_pin_verdict_seam.py`, `test_home_pin_scan_limbs.py` unaffected |
| **1** | Converge `body_queue_purge_differential` (PC, flagship, ablation-certified) | Delete autouse `_isolated_home`; add `pytestmark = usefixtures("canonical_home")` (or param idiom); add its tombstone 3-tuple to the baseline via `with_tombstones` | **Mechanical** | `pytest tests/architectural/test_spec_kitty_home_pin_census.py` GREEN; `pytest tests/delivery/test_body_queue_purge_differential_3030.py` GREEN; census now 39 + 1 tombstone; `ruff`/`mypy` clean on edited file |
| **2** | Converge `per_project_report::_home` (PC) | as Op 1 | **Mechanical** | census suite GREEN; `pytest tests/delivery/test_per_project_report_3030.py` GREEN; census 38 + 2 tombstones |
| **3** | JC batch — the 6 `upgrade/` inline pins (#35-40) | Per test: add `canonical_home` param, delete the `setenv` line, keep `home=tmp_path/"home"` for the `cache/version.lock` writes; tombstone each | **Mechanical** (repetitive, low judgement — same shape ×6) | census suite GREEN; `pytest tests/upgrade/…` (the 3 files) GREEN; 6 tombstones added |
| **4** | JC surgical — `legacy_queue` (#30) + `routing` (#31) inline pins | Convert ONLY the census-member line; leave every sibling non-member pin untouched; tombstone each | **Strong** (surgical, sibling-pin hazard) | census suite GREEN; `pytest tests/sync/test_legacy_queue_precondition_3030.py tests/sync/test_routing.py` GREEN; `discover()` drops exactly 2 |
| **5** | JC SAAS-redundant — `body_drain` (#21), `nfr003` (#14) [+ `body_upload` #22 if confirmed] | Confirm the root autouse covers `SPEC_KITTY_ENABLE_SAAS_SYNC=1`; delete fixture, `usefixtures("canonical_home")`, drop the redundant SAAS set; tombstone | **Strong** (confirm redundancy first) | census suite GREEN; each file's behaviour tests GREEN; no test asserts the fixture-scoped SAAS set |
| **6** | CR — `daemon_publish` (#29) | Converge the home dimension to `canonical_home`; **retain** `SPEC_KITTY_SAAS_URL` as a one-line residual pin or a tiny local fixture; tombstone the `_isolated_home` member | **Strong** (partial converge, must not drop `SAAS_URL`) | census suite GREEN; `pytest tests/sync/test_daemon_publish_consent_3030.py` GREEN |
| — | **STOP.** DS trio + all MS members are out of scope. | Document in the mission record; open a follow-on issue for the manifest-with-`reason` mechanism and the deletion missions (RESIDUALS R8). | — | — |

Batching rationale: Op 3 is one commit over three sibling files sharing an identical inline shape
(cheap, mechanical). Op 4 is separated because its sibling-pin blast radius demands a strong model.
Op 5/6 each gate on a named confirmation. Every op re-runs the census suite so the census/tombstone
set stays mutually consistent after each commit (a half-applied op — pin removed, tombstone missing —
reds t024 `stale`; tombstone added, pin present — reds the new Op-0 t023 meta-test).

**Minimum viable close of #3121:** Op 0 + Op 1 + Op 2 (census 40 → 38, the two provable members).
Ops 3-6 are value-add within the same scope and can be folded incrementally.

---

## 7. Risks & things that could make this NOT closeable without operator input

1. **[BLOCKER] The tombstone path is scaffold, unexercised on the binding invariants (Finding B).**
   t023 is not tombstone-aware; the "shrink-only ratchet" cannot shrink until Op 0 lands. Op 0 edits
   a meta-test R1a *froze* — even though sanctioned (R1a names `census==∅` as R1b's DoD), it needs
   explicit architect/operator sign-off per the charter's architectural-gate discipline. **If the
   operator declines to evolve the guard, #3121 is not closeable at all** — the census is a permanent
   40-row freeze, not a burn-down.
2. **`census == ∅` is unreachable without a mechanism that does not exist.** 23 MUST-STAY members are
   genuinely different seams that must live forever; the census has no `reason` column and there is
   no manifest artefact to promote them into. The full R1b DoD therefore needs a *new* artefact +
   ratchet designed and approved. This plan closes #3121 on the narrower "provable class" DoD and
   recommends a follow-on issue for the manifest.
3. **The anchor's `resolved_at_sha` is old (`fe5d492ed…`) and the anchor is line-number-fragile.**
   The anchor header (`_home_pin_anchor.py:1-35`) warns that `members.json` line numbers only resolve
   at that SHA; upstream already drifted `test_sync_doctor_tracker_egress_3108.py` (+5 lines) and
   `:1165`/`:1124` in the tracker file. Op 0 must key tombstones by the **frozen anchor 3-tuple**
   (relpath, qualname, normalized token-line), never by live line number, or a rebase silently
   invalidates them.
4. **The DELETION-SCOPE trio must not be converged.** Converting arm-2-GREEN members onto an owner
   they do not need pre-empts the deletion mission's adjudication and violates the operator's
   "deletion is out of scope" ruling. Leave them (`RESIDUALS.md` R8: convergence-before-deletion
   sequencing — if deletion runs first the class shrinks 28→25 and stales SC-007).
5. **Counter-autouse `delenv` members are traps (4.5).** They read as "pure home" at a glance but the
   `delenv SPEC_KITTY_ENABLE_SAAS_SYNC` is load-bearing *against* the root autouse; converging them
   silently arms SAAS and inverts the test. `consent_read_fault` even carries a docstring ("arming
   env var deleted") that a hasty reader could mistake for canonical_home's contract. Do not convert.
6. **CR member `daemon_publish` will silently lose `SPEC_KITTY_SAAS_URL`** if converted naively; no
   autouse restores it. Op 6 must retain it explicitly.
7. **Autouse-vs-param idiom drift.** The landed R1a fix used the param idiom (`del canonical_home`);
   most convergence targets are autouse and are cleaner converted via module-level
   `usefixtures("canonical_home")`. Mixing idioms per file is fine but must be deliberate; a leftover
   `setenv` anywhere in the file keeps the member in `discover()` (the owner never overrides a
   self-pinning definition — `conftest.py:404-408`).
8. **Ratchet-bite regression.** Op 0 must be proven to still red on (a) a spurious new pin and (b) a
   tombstone whose pin is still present. Skipping either dulls the gate — exactly the R1a NFR-001
   failure mode.

---

## 8. Sources (all under the analysed checkout)

- Census/guard code: `tests/architectural/_home_pin_verdict.py`, `_home_pin_scan.py`,
  `_home_pin_anchor.py`, `_home_pin_exempt.py`; meta-tests `test_spec_kitty_home_pin_census.py`.
- Frozen artefacts: `tests/architectural/census/spec_kitty_home_pin_anchor.yaml` (40),
  `…/spec_kitty_home_pin_R1a.yaml` (40, mutable census), `tests/architectural/spec_kitty_home_pin_baseline.yaml`
  (`tombstones: []`). Owner: `tests/conftest.py:372`.
- Ablation record: `kitty-specs/isolated-home-pin-guard-r1a-01KZNMA3/research/m4_ablation_evidence/`
  (`VERDICT.md`, `TABLES.md`, `RESIDUALS.md`).
- Landed mission: `kitty-specs/home-pin-census-owner-adoption-01M05C50/` (`spec.md`, `tasks.md`).
- Issue #3121 comments: HALT-AND-RE-SCOPE operator sign-off (2026-08-07); "R1a — the guard half".
- Member bodies: the 35 test files enumerated per-row in §4.
