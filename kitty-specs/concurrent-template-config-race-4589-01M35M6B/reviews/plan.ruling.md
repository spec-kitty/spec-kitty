# Arbiter ruling: plan phase, round 3 HALT

| Field | Value |
|---|---|
| Mission | `concurrent-template-config-race-4589-01M35M6B` |
| Phase | `plan` |
| Round | 3 (post-HALT ruling; replaces the acceptance bar for the findings below) |
| Plan under review | `plan.md` at `807a3a9a7` (1009 lines); trail at `ad55fa7ac` |
| Arbiter profile | `paula-patterns` (`packs/built-in/agent_profiles/paula-patterns.agent.yaml`) |
| Inputs read | `spec.md`, `plan.md` (full), `research.md` (the parts on the mechanism and the forced trial), every `reviews/plan.*` file (rounds 1 to 3), `.kittify/charter/charter.md` (C-011 ATDD-first, standing orders 2, 4, 5), `tk/references/review-protocol.md`, `sk/references/review-overlay.md`, `sk-design/references/design-pipeline.md` §2a |
| Source checked (read-only) | `src/charter/offering/missions/mission_step_repository.py`, `mission_type_repository.py`, `src/charter/activation/mission_type_profiles.py`, `.github/ci-module-registry.yml`, `scripts/ci/gate_selection.py` (`select_modules` was executed read-only), `tests/doctrine/missions/`, `tests/core/test_mission_creation_identity.py` |

## Directives applied

- **001 Architectural Integrity.** Before ruling on any finding, I decided which artifact
  owns it. The plan owns the fix-design contract (§6), the claims made about each site
  (§7), the gate set and baseline (§9/§10), and the test obligations. Tasks, the WPs and
  the test code own the harness mechanics. Every disposition below follows that line.
- **003 Decision Documentation.** This file records the ruling so the question "plan versus
  WP granularity for §8" is not argued again. The ruling replaces the acceptance bar for
  each finding it covers (review-protocol §R6, "Re-entering after a HALT ruling").
- **030 Test and Typecheck Quality Gate.** The required tests are stated as a revert
  matrix: the smallest set of tests that shows each fix half is necessary and sufficient
  on both sites.
- **032 Conceptual Alignment.** The recurring drift is conceptual. "Cache key",
  "cache-miss body" and "same key" have been used as if the two sites share one meaning,
  and they do not. The ruling requires a per-site fact table so the terms stay bound to
  each site.
- **041 Tests as Scaffold, Not Friction.** Obligations assert observable contracts: result
  correctness, how many populations happen per key, no deadlock. Exact patch targets are
  scaffolding and belong next to the test code.
- **Tactic `review-intent-and-risk-first`, and the release-versus-long-term split.** 6a
  (thread-local YAML) is the fix that makes results correct. 6b (per-key lock) is extra
  value on top of it, and as written it is internally inconsistent (ARB-001). The smallest
  safe release keeps 6a unconditional and makes 6b either coherent or explicitly dropped.
- **Scout dispatch not performed.** This is adjudication of an existing trail, not a fresh
  architecture review, so I did not dispatch the five scouts. I applied the contract lens
  (§6b's stated property against its mechanism) and the layered/ownership lens (registry
  module ownership) inline, and recorded both below.

## Recurrence diagnosis (Paula framing)

The same smell has come back in every round. The plan asserts that the two fix sites have
an "identical shape" and then writes primary-site facts into shared text:

| Round | Finding | What leaked |
|---|---|---|
| 1 | PLAN-ARCH-001 | Second site treated as having the same shape as the primary site |
| 1 fresh | PLAN-FRESH-001 / -002 | Wrong cache-clear seam, and a wrong failure mode, at the second site |
| 2 fresh | PLAN-FRESH2-001 / -003 | Cold-cache list and the NFR-003 test missing the second site |
| 3 fresh | DEBBIE-001 / ARCH-003 / ARCH-002 | Per-miss unit and key shape copied from the primary site onto the second |

Round 3's parametrization fixed "did we remember the second site" by construction. It did
not fix the missing boundary underneath: the **per-site facts** that the shared
parametrization consumes. Those facts are key granularity, how keys are shared under
`create_mission_core`, what one cache miss contains, and how the loader catches errors.
They are plan-level. Harness names derived from them are not.

**The orchestrator's hypothesis, tested.** It is **partly confirmed**.
DEBBIE-001/ARCH-003 (the counting target) and DEBBIE-002 (the pause predicate), plus all
three round-2 findings, are harness mechanics. A red-first test run red, then green, then
reverted checks them itself, and the plan can only restate them. The hypothesis misses
two points:

1. The churn in the mechanics has been hiding a **plan-level contradiction between §6b and
   §8** (ARB-001, ARB-002 below).
2. That contradiction means round 1's PLAN-VERIFY-003 was marked resolved on a test (§8f)
   that cannot reach green against the §6b the plan specifies.

## Finding rulings

### PLAN-FRESH3-DEBBIE-001 (sev 4), merged with its duplicate PLAN-FRESH3-ARCH-003 (sev 4)

1. **Valid: yes.** It is also deeper than either reviewer stated.
   - `plan.md:511` sets SECOND_SITE `cache_miss_body` to `_load_layered_mission_type_file`.
     That is a per-file function: `scan_mission_types_dir` calls it once for each `*.yaml`
     file (`mission_type_repository.py:471-474`), and four files ship (`documentation`,
     `plan`, `research`, `software-dev`). A single, correctly serialized miss therefore
     counts at least 4, so "exactly once" (`plan.md:742-743`) cannot hold at that site.
   - **Arbiter extension (ARB-001):** even with the right target, "exactly once" cannot be
     reached at **either** site with §6b as specified. §6b takes `_lock_for(key)` *inside*
     the `functools.cache`-wrapped body (`plan.md:334-345`) and has no re-check under the
     lock. `functools.cache`'s miss path stores the result only after the body returns
     (`plan.md:310` cites this itself). Both §8f threads are pinned past the cache lookup
     (`plan.md:740-742`). Thread A walks and releases the lock, and the wrapper stores the
     result. Thread B then gets the lock and walks again, so the count is 2 with 6b
     present.
   - §8f is therefore red with 6b present and red with 6b reverted, and cannot tell the two
     apart. §6b's stated purpose ("closes the redundant-work window", `plan.md:303-316`) is
     not delivered by the mechanism it describes. The source confirms the shape: the cached
     body delegates straight to the uncached walk (`mission_step_repository.py:446-470`,
     `335-364`).
2. **Severity: 4, confirmed.** The acceptance criterion cannot be tested, and the plan
   contradicts its own fix mechanism.
3. **Level: split.**
   - Which function to count is WP-level.
   - The property 6b guarantees, and therefore what §8f can assert, is plan-level (§6b).
4. **Disposition.**
   - Fix §6b so its stated property matches its mechanism. Either:
     - (a) make it single-flight: at most one population per key per cold episode, and
       every concurrent waiter gets that population's result. Choose and name the
       structure (for example, a re-check under the lock, or the lock taken around the
       cached call). Then reconcile §5's `cache_clear` claims and §7's "a warm hit never
       touches a lock" claim with that choice; or
     - (b) drop 6b and state what then satisfies SC-006. Dropping 6b likely needs a spec
       touch by the operator, because SC-006 presumes a new lock or cache failure path.
   - Restate §8f as an obligation: count populations of the unit `functools.cache`
     memoizes, never a per-file helper. Delete the `cache_miss_body` naming from the plan.

### PLAN-FRESH3-DEBBIE-002 (sev 4)

1. **Valid: yes, as a statement about the plan as written.**
   - The named patch boundary `pre_fix_load_call` is `.load(text)`
     (`plan.md:497,507`; source `mission_step_repository.py:133`,
     `mission_type_repository.py:389`). It receives no path, so it cannot recognize
     `race_target_a` without content sniffing, which the plan never mentions.
   - At the primary site, the walk iterates over an unsorted `set`
     (`mission_step_repository.py:344,360`). Its order depends on the per-process hash
     seed.
   - At the second site, the order is sorted (`:471`), and `software-dev.yaml` comes last.
   - **Arbiter additions, same class:**
     - A wrapper around `.load` can pause only before or after the real call, never
       "after it has started" (`plan.md:574-575`). research.md's mechanism needs the pause
       *between* `self.reader.stream = stream` and the end of composition. research.md
       itself says no forced trial was run (research.md line 45).
     - The pre-fix target (`_YAML.load`) no longer exists after the fix. That conflicts
       with the requirement that the test pass "unmodified, after the fix commit"
       (`plan.md:662-666`).
     - NFR-001's "50 runs" check, if done inside one pytest process, keeps one hash seed
       and would not detect a test whose verdict depends on the seed.
2. **Severity: 4, confirmed.** A pin that depends on the hash seed can ship a test whose
   verdict varies across CI processes, and that breaks NFR-001.
3. **Level: the obligation is plan-level; the mechanics are WP-level.**
4. **Disposition.**
   - Replace §8b's construction prose with these obligations:
     - the pin is keyed on file identity, never on call order or iteration order;
     - the pause lies strictly inside the shared instance's load window (after the reader
       stream is assigned, before composition completes);
     - the timing seam exists at both the red commit and the green commit, so the test is
       committed once and never edited;
     - NFR-001 determinism is verified across separate processes with varied
       `PYTHONHASHSEED`.
   - Choosing the seam (for example, a path-aware predicate at `_load_step_yaml` /
     `_load_layered_mission_type_file`, combined with a class-level ruamel pipeline hook)
     is a binding WP note, and needs a spike before the red commit.

### PLAN-FRESH3-ARCH-001 (sev 4)

1. **Valid: yes, and understated.**
   - `plan.md:842-848` declares `charter` "NOT selected". That contradicts the registry and
     the selector: `charter` has roots `src/charter/**` and
     `test_dirs: tests/charter, tests/doctrine` (`ci-module-registry.yml:143-160`).
   - The plan also contradicts itself: its own §10 says `architectural-heavy` fires
     *because* `needs.changes.outputs.charter == 'true'` (`plan.md:887-891`).
   - Executing `scripts/ci/gate_selection.select_modules` (read-only) on the planned diff
     gives **`charter, core_misc, missions, specify_cli_runtime, unit`**, five modules. The
     plan names two. `unit` (`ci-module-registry.yml:244-267`, `tests/unit`) and
     `specify_cli_runtime` (`:269-285`, `tests/specify_cli/runtime`) both list
     `src/charter/offering/missions/**` as a root.
   - §9's baseline (`plan.md:749-803`) runs none of `tests/doctrine`, `tests/charter`,
     `tests/unit` or `tests/specify_cli/runtime`. `tests/doctrine/missions/` holds the
     dedicated suites for both fix sites (`test_mission_step_resolver.py`,
     `test_mission_type_repository.py`, including `test_same_key_is_a_cache_hit` at
     `:660`). That last test pins a cache-staleness contract which 6b's change to
     `resolve_layered_mission_types` could plausibly disturb.
2. **Severity: 4, confirmed.**
   - The gate statement contradicts existing code (the registry and selector).
   - The CL-005/FR-007 baseline is empty exactly where attribution matters most.
3. **Level: plan-level.** The gate set and baseline are required plan content under
   design-pipeline §2a.
4. **Disposition.**
   - Replace §10's module list with the recorded output of `select_modules` for the planned
     file set, citing the command.
   - Extend §9's fresh baseline to every selected module's `test_dirs`. At minimum run
     `tests/doctrine/missions`, `tests/charter`, `tests/unit` and
     `tests/specify_cli/runtime`, recording results (or "not run and why") so pre-existing
     red can be told apart from red the mission introduces.

### PLAN-FRESH3-ARCH-002 (sev 3)

1. **Valid: yes.**
   - `plan.md:419-422` describes the lock key as `mission_type_id + pack_context` and
     says different mission types never contend.
   - The second site's key is `(mission_types_dirs, pack_context)`, one per roster
     (`mission_type_repository.py:477-481`). `_resolve_action_slot` always passes the same
     fixed `mission_types_dirs` (`mission_type_profiles.py:952-953`). Every concurrent
     `create_mission_core` in one project therefore shares one second-site key, whatever
     its mission type.
   - The same error sits in §8b's claim that "the narrower same-key case" at the second
     site is special (`plan.md:585-591`). There, same-key is the default.
2. **Severity: 3, confirmed.** The NFR-002 conclusion probably still holds, but a false
   per-site premise feeds directly into test design (see ARB-002). This is rework inside
   one WP, not a wrong fix.
3. **Level: plan-level** (§7 NFR-002 reasoning, and the per-site fact table).
4. **Disposition.**
   - Rewrite §7 with each site's actual key shape and contention surface. Re-derive the
     NFR-002 "rare contention" conclusion separately for the second site.
   - Carry the key facts into the new per-site fact table (global ruling, item 1).

### ARB-001 (arbiter observation, sev 4, plan-level). Reopens PLAN-VERIFY-003

Stated under DEBBIE-001 above. §6b as specified does not prevent redundant population, so
§8f has no green state. **PLAN-VERIFY-003** (round 1: "no test fails if 6b is reverted
while 6a is kept") was marked `resolved` in `plan.verify.yaml` on the strength of §8f. That
resolution does not hold, so **PLAN-VERIFY-003 is REOPENED**. It is closed by the same fix
as DEBBIE-001/ARCH-003: a coherent §6b plus an obligation-level §8f.

### ARB-002 (arbiter observation, sev 4, plan-level). §8b is inconsistent with §6b

1. **Post-fix deadlock or false red.**
   - §8b races both threads on the **same** key (`plan.md:585-591`) and pauses the
     "paused" thread inside the walk while it waits for the other thread's load to finish
     (`plan.md:572-581`).
   - After the fix, the paused thread holds `_lock_for(key)` (§6b takes it around the
     walk). The other thread, on the same key, blocks on that lock and never reaches its
     load.
   - The result is a deadlock, or a broken barrier that the paused thread captures as an
     exception, which turns the test red. Either way, the claim that §8b "passes,
     unmodified, after the fix" while exercising the same interleaving
     (`plan.md:543-544,662-666`) is false.
2. **6a has no revert proof.**
   - With 6b present and 6a reverted, a same-key race is serialized by the lock, so §8b
     stays green. No test then shows 6a is necessary.
   - At the primary site, distinct keys (different mission types) still share `_YAML`. At
     the second site, the unsynchronized `_LAYERED_YAML` is also reached outside the cache,
     through `pack_manager.py:1014` → `scan_mission_types_dir`.
3. **Disposition.**
   - §8's obligations must say which fix half each test isolates.
   - The 6a proof must race a configuration the per-key lock does not serialize (distinct
     cache keys, or a path the lock does not guard). It must never hold a lock across the
     barrier that the other thread needs.
   - The same-key, no-deadlock edge case (spec Edge Cases) is covered by the 6b test, not
     by the 6a test.
   - WP caution, recorded now so it is not rediscovered: `_run_create` uses process-global
     `unittest.mock.patch` (`tests/core/test_mission_creation_identity.py:54-70`).
     Distinct project roots in two threads through that helper are unsafe. For a
     distinct-`pack_context` race, CL-004's "or the resolver path it drives" allows driving
     the resolver path directly.

### Arbiter nit (sev 1, non-blocking, fix-everything rule applies)

The plan and research.md cite pure-Python `functools.py:549-562` for the miss path. The
runtime uses the C `_functools` wrapper. The conclusion (the body is not serialized, and
the store happens after the body returns) is unchanged. Say which implementation runs.

## Global ruling: §8 becomes obligations; mechanics move to tasks as binding notes

**Ruling:** reduce §8 to test obligations, add the per-site fact table and the revert matrix
the obligations depend on, and move harness mechanics to tasks/WPs as binding notes.

**Why, in terms of the protocol and the charter:**

- **Protocol.** The plan-phase `verify` lens asks for three things: a concrete strategy per
  AC, the gates, and **revert discipline** ("every changed behaviour gets a test that fails
  when reverted"). The tasks-phase `verify` lens asks for "per-AC test strategy concrete;
  red-first stated per WP". Design-pipeline §2a lists no harness mechanics.
- **The trail.** Three rounds show that each mechanic the plan pins becomes new review
  surface, sampled differently in every fresh sweep. That is the non-determinism the
  early-stop rule warns about, and it is why the sev≥3 count does not fall.
- **Charter C-011, standing orders 4 and 5.** A red-first test is its own proof. It must be
  red on the base, green on the final commit, and red again with each fix half reverted.
  The WP reviewer checks that by running it, and that check is stronger than a reviewer
  reading prose about patch targets. What the plan must fix is the **contract** such a test
  is checked against. ARB-001/002 show that contract is currently inconsistent, and no
  amount of mechanics in the plan would have fixed that.
- **Keeping mechanics in the plan and patching them** would repeat the loop. Every patch is
  new surface that has never been executed.

**What §8 must still contain, so that "under-specified" cannot legitimately be re-raised:**

1. **A per-site fact table** (§6 or §8a), with one row per site:
   - the cache key shape;
   - whether concurrent `create_mission_core` calls share that key;
   - what one cache-miss population contains (the whole walk, not one file);
   - the loader's catch semantics (swallow versus re-raise);
   - the site's own cache-clear seam;
   - other unguarded users of the site's YAML instance.
2. **A test obligation table** with one row per test (8b, 8c, 8d, 8e, 8f) and these columns:
   - AC/FR/NFR/SC traced;
   - the observable property asserted;
   - the fix half it isolates (6a, 6b, 6c, or none);
   - why it is red at the red-first commit, stated per site;
   - its expected state for each revert cell.
3. **The revert matrix:**

   | State | Required result |
   |---|---|
   | Base | 8b red at both sites |
   | 6a+6b applied | all tests green, both sites, no deadlock |
   | 6a reverted, 6b kept | at least one test red per site where 6a is reachable |
   | 6b reverted, 6a kept | 8f red, if 6b is kept in any form |

   If 6a truly cannot be reached outside the lock at the second site under the chosen 6b,
   the plan says so and names what proves 6a there. `pack_manager` is a candidate.
4. **Binding constraints on any harness**, stated as constraints and not as code:
   - the pin is by file identity inside the shared load window;
   - the seam survives both commits;
   - no lock is held across a barrier that the other thread needs;
   - teardown is function-scoped;
   - the count guards a count of populations, never files;
   - determinism is verified across processes and hash seeds (NFR-001);
   - CL-004's outer-call rule holds.
5. **Commit phasing (§13)** consistent with the table: which tests are in the red-first
   commit, and which are red there for a real reason and which only trivially.
6. **Removed from the plan and moved to tasks input as binding WP notes:**
   - the `_FixSiteCase` field values;
   - patch-target dotted paths;
   - the `_cold_cache()` body (keep the obligation "each test starts with every cache it
     races provably cold, via the public seams in §5");
   - barrier choreography;
   - predicates;
   - the ruamel hook choice.

   The plan may keep an *illustrative* sketch only if it is labelled non-normative.

**Earlier findings reopened by this ruling:** **PLAN-VERIFY-003** (see ARB-001). No other
earlier finding is reopened. The round-2 resolutions (PLAN-FRESH2-001/002/003) stay
resolved as obligations: cold caches on both sites, per-thread captured assertions, and
NFR-003 coverage on both sites. The next author must keep them in obligation form when
removing the mechanics. PLAN-ARCH-001 (round 1) stays resolved. ARCH-002 is its residue in
§7 and is closed by the fact table.

## Convergence criterion for the next round

**The verifier (R5a) checks, against this ruling as the replaced acceptance bar:**

1. ARCH-001: §10 matches the recorded `select_modules` output, and §9 covers every selected
   module's `test_dirs`.
2. ARCH-002: §7 is re-derived per site.
3. DEBBIE-001/ARCH-003 + ARB-001 + PLAN-VERIFY-003: §6b's stated property matches its
   mechanism, or 6b is dropped with SC-006 handled explicitly. §8f's obligation is
   reachable in both its green and its reverted state.
4. DEBBIE-002: the obligations in item 4 are present.
5. ARB-002: the revert matrix exists, the 6a proof isolates 6a, and no post-fix deadlock is
   possible by construction.
6. The nit is fixed.
7. §8 contains items 1 to 5 of the global ruling and no normative mechanics.

**The fresh sweep (R5b) MAY raise as new plan-level findings:**

- a contradiction between the plan and the source, spec, registry or charter;
- an obligation that is unsatisfiable, or that cannot tell its revert cells apart;
- a changed behaviour with no obligation;
- a per-site fact that is wrong;
- a gate-set or baseline error;
- a commit-phasing inconsistency.

**The fresh sweep may NOT raise at plan level** (any such item goes to a `tasks`-input list,
capped at severity 2, and is not counted for early-stop):

- choice of patch target, predicate, hook, counting seam or fixture shape;
- barrier choreography;
- walk-order handling;
- the claim that §8 is "under-specified" when items 1 to 5 are present.

**Early-stop baseline for the next round:** 5 plan-level items at sev≥3:

- ARCH-001
- ARCH-002
- DEBBIE-001/ARCH-003 merged with ARB-001 and PLAN-VERIFY-003
- DEBBIE-002 (obligation)
- ARB-002

The nit is not counted. The next round must reduce that count.

complete: true
