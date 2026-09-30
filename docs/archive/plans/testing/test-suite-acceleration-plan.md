---
title: Test Suite Acceleration — Final Remediation Plan
description: Final remediation plan for accelerating the test suite, including the HOME-isolation hazard (Path.home()/.spec-kitty in an autouse conftest) and its fixes.
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/development/testing/testing-parallel.md
- docs/archive/plans/testing/ci-job-timings.md
- docs/archive/plans/testing/ci-coverage-union-audit.md
---

## Status update (`ci-test-topology-performance-01KXBJRT`, 2026-07-12)

This plan predates and is **separate from** the `ci-test-topology-performance-01KXBJRT`
mission (its own Action Table below never names `integration-tests-next` —
the 69.2-min headline offender that later mission's spec is grounded in —
nor `slow-tests`, `fast-tests-core-misc`'s rebalance, the Sonar
coverage-denominator fix, or the UI-e2e coverage feed; those are that
mission's own scope, recorded in
[`docs/development/testing-parallel.md`](../../../development/testing/testing-parallel.md)'s "CI
shard topology" section and
[`ci-job-timings.md`](ci-job-timings.md)/[`ci-coverage-union-audit.md`](ci-coverage-union-audit.md)).
This mission's WP09 reconciles this document's own currency instead of
leaving it silently stale, per FR-009:

**Verified shipped** (direct evidence checked, not assumed from the plan's own age):
- **A2/PP-05 — per-worker HOME/XDG isolation** (Wave 2): live — see
  [`docs/development/testing-parallel.md`](../../../development/testing/testing-parallel.md)'s
  "Per-worker HOME isolation" section and `tests/conftest.py`.
- **R4/PP-06(a) — ULID volume env-gate** (Wave 1): live — see
  [`docs/development/testing-parallel.md`](../../../development/testing/testing-parallel.md)'s
  "Volume env gates" section (`SPEC_KITTY_ULID_VOLUME_FULL`).
- **R5/A4/PP-02 — charter `elapsed<0.1` → `@pytest.mark.timeout`** (Wave 1):
  live — `tests/charter/test_integration.py` lines 405 and 427 both carry
  `@pytest.mark.timeout(2)` (converted, not deleted).
- **R1/A5 — FSM parity matrix collapse** (Wave 3): live —
  `tests/status/test_transitions.py`'s `_PARITY_ROWS` accumulate-all loop
  with the anti-vacuity `assert checked == len(_PARITY_ROWS)` guard exactly
  as this plan's safeguard specified.
- **A1/PP-01/R6 — fast-* shard flips, charter first** (Wave 4): landed in
  `.github/workflows/ci-quality.yml` (`fast-tests-charter`,
  `fast-tests-doctrine`, `fast-tests-cli`, `fast-tests-agent`,
  `fast-tests-status`'s re-route all carry `-n auto --dist loadfile`), but
  **not yet 3×-green-ratchet-confirmed** — each still carries a
  `PENDING-CI` comment in the workflow file. See
  [`docs/development/testing-parallel.md`](../../../development/testing/testing-parallel.md)'s
  "Status: local default vs CI shard flips" section. **This is a distinct,
  still-open item — `ci-test-topology-performance-01KXBJRT` does not close
  it.**

**Not verified as part of this reconciliation** (Waves 3, 5 items not
directly checked by this WP — do not assume shipped or stale without
re-checking against the live code): R3 (migration read-only fixture
share), R7/PP-04(d) (AST/DRG cache), A3/PP-03 (templated git-repo fixture),
B2/PP-04(a) (collect-only consolidation), R9/R10(part2) (xfail
strictness/concurrency trim), A6/R8 (status re-route + xdist enablement —
though the `PENDING-CI (T022)` comments above suggest the re-route landed
and is itself mid-ratchet). A full audit of this plan's remaining Action
Table rows is out of `ci-test-topology-performance-01KXBJRT`'s scope; file
a dedicated follow-up if this plan's own currency needs a complete pass.

---

All load-bearing facts are confirmed. The HOME hazard is real (`Path.home() / ".spec-kitty"` at conftest.py:119, autouse in agent conftest with no HOME monkeypatch), the FSM parametrize is exactly as described, and the CI critical-path chain is verified. I have sufficient verified ground truth to produce the final synthesis report.

# Test Suite Acceleration — Final Remediation Plan

> **Historical (3.2.x cycle).** Kept as a record. The shard layout it analyses was replaced by the modular CI from #3995, and parallel local runs with per-worker HOME isolation are now standard (see [parallel testing](../../../development/testing/testing-parallel.md)). The active cycle is 4.0.0 — see the [4.0.0 roadmap](../../../plans/4-0-0-milestone-roadmap.md).

## 1. Executive Summary

**Operator's two direct questions, answered first:**

**(a) Can CI fast-shards be parallelized? — YES, but staged behind two safety gates.** The fast-* shards (charter, cli, sync, doctrine, agent, etc.) currently run **single-process** (verified: `ci-quality.yml` charter shard at line ~1337 has no `-n auto`; status fast shard line ~917 likewise). The identical `-n auto --dist loadfile` combo is **already in production** in this exact repo for `integration-tests-core-misc` (verified lines 1181, 1295, 1307), proving the topology and coverage-XML aggregation are safe here. So the flip is mechanically proven. It is **not safe to flip uniformly today** because of two real hazards: (1) the **charter shard contains wall-clock `elapsed < 0.1` asserts** (verified `test_integration.py:427,450`) that flake under CPU contention, and (2) the **agent shard's autouse `_autoclean_spec_kitty_queue` truncates the REAL `~/.spec-kitty/queue.db`** (verified `tests/agent/conftest.py:15-41` → `tests/conftest.py:119` `Path.home()/".spec-kitty"`, no HOME isolation). `--dist loadfile` pins files to workers but does **not** serialize cross-file access to a shared real HOME, so concurrent workers would clobber the same SQLite DB. **Gate the charter flip behind R5/A4; gate cli/sync/agent behind A2/PP-05 per-worker HOME isolation.**

**(b) Can the suite be parallelized locally across processes? — YES, after A2 lands**, and it is the single largest local win. ~48% of test files are pure-`tmp_path` with no subprocess/git (embarrassingly parallel), so a multi-core laptop realistically gets **2–4x** wall-clock. The blocker is the same shared-HOME queue hazard plus the charter timing asserts; bare `-n auto` today would corrupt the developer's real `~/.spec-kitty/queue.db`.

**Exact recommended local command (after A2 + A4/R5 land):**
```bash
PWHEADLESS=1 pytest tests/ -n auto --dist loadfile -p no:cacheprovider
```
Always `--dist loadfile` (never bare `--dist load`) — the status/charter conftests use file-local autouse registry/cache resets that assume same-file co-location. Run the daemon/real-port sync tests (`tests/sync/test_orphan_sweep.py`, ports 9400–9449) as a **separate serial pass** (`-n0`); HOME isolation does not protect OS-global port binds.

**The 3–5 highest-leverage moves and realistic wall-clock win:**

| Move | Mechanism | CI critical-path win | Local win |
| ------ | ----------- | --------------------- | ----------- |
| **A2/PP-05 — per-worker HOME isolation** | Pin `Path.home()`+`HOME/USERPROFILE/LOCALAPPDATA` to a per-xdist-worker tmp dir | $0 direct; **unblocks everything below** | gates the 2–4x local win |
| **A1/PP-01/R6 — flip fast-* shards to `-n auto --dist loadfile`** | charter 9.1m→~5m (2-core) / ~2–3m (4-core); cli 3.8m→~1.5m; core-misc 3.8m→~1.5m | **collapses the #1 critical path (charter) + its downstream chain (agent)** | n/a (CI) |
| **R5/A4/PP-02 — convert charter timing asserts to `@pytest.mark.timeout`** | removes flaky `elapsed<0.1` floors | **precondition** that unblocks charter flip | removes flakes locally |
| **R1/A5 — collapse 1701-item FSM parity matrix to one looped test** | removes 1700 of 2372 status collection items | unblocks effective status xdist (status was *slower* under `-n auto`: 31.5s vs 25.35s) | ~1s + cleaner logs |
| **R4/PP-06(a) — ULID volume n=100→n=25 (env-gated full path)** | ~0.49s × 75 iterations | **~36s off slow-tests job every push** | **~36s off local `pytest tests/`** |

**Realistic aggregate:** CI critical path drops from charter's ~9.1m-dominated path to ~3–5m once charter parallelizes (the largest single lever, since charter gates agent). Push-pipeline CPU drops a further ~28s (R2 migration dedup) + ~36s (R4 ULID) + ~100s (R3 migration-fixture share). **Local single-dev run: 2–4x** once A2 lands, plus ~36s flat from R4. The critical insight: **A2 is the master enabler** — almost every parallelization win is gated on it, and on its own it costs nothing and changes zero assertions.

---

## 2. Ranked Action Table (by speedup ÷ effort)

| Rank | Action | Owner-persona | Est. speedup | Effort | Risk | Required safeguards | Safe now? |
| ------ | -------- | --------------- | ------------- | -------- | ------ | --------------------- | ----------- |
| 1 | **R4/PP-06(a)** ULID n=100→25, env-gate n=100 (`SPEC_KITTY_ULID_VOLUME_FULL`) | Randy/Paula | ~36s/push + ~36s local | S | low | Keep both asserts (uniqueness + pairwise order); keep `@slow`; wire env-gated n=100 into nightly | **YES** (with env-gate shipped same change) |
| 2 | **R5/A4/PP-02** charter `elapsed<0.1` → `@pytest.mark.timeout(2)` | Randy/Architect/Paula | precondition (unblocks #4) | S | low | Keep `isinstance`+`len==2` asserts; convert (don't delete); sweep **all ~16** wall-clock floors in `tests/charter` before flip | **YES** (the assert conversion itself) |
| 3 | **R2/PP-07** stop double-running the migration perf `@slow` test | Randy/Paula | ~28s/push | S | low | Use `and not slow` on **specify-cli-heavy** shard ONLY (line 1305 region scoped to that step); **never** `--ignore=tests/specify_cli` on slow-tests (orphans 3 NFR guards); collection-count gate before/after | **YES** |
| 4 | **A1/PP-01/R6** flip fast-* shards to `-n auto --dist loadfile` (charter first) | Architect/Paula/Randy | charter 9.1m→2–5m; cli/core-misc 3–4x | M | medium | Gated on #2 (charter) and #8 (cli/sync/agent); exclude tiny `release` shard (14 items); run-twice ratchet per shard; `--dist loadfile` always | **NO** — gated |
| 5 | **R1/A5** collapse 1701-item FSM parity to one accumulate-all loop | Randy/Architect | unblocks status xdist; ~1s | S/M | low | Accumulate ALL mismatches (no break); assert count==`len(_PARITY_ROWS)`; keep `err==expected_err` exact-string; keep `test_baseline_fixture_is_non_trivial`; equivalence + mutation proof in PR | **NO** — needs the safeguarded rewrite |
| 6 | **R3/PP-04(b)** share ONE migrated-project fixture for the **3** identical read-only TestFullMigration asserts | Randy/Paula | ~50s off specify-cli-heavy | M | low | Only the 3 truly-identical read-only tests (`schema_version`/`gitignore`/`backup_cleaned`); **exclude both counter tests** (different inputs) and all rollback/dry-run; use `tmp_path_factory` (module scope), assert `report.success` in fixture | **NO** — gated on R2 |
| 7 | **R10(part1)** no-op sleeper for 2 `_guarded_final_sync` swallow tests | Randy | ~4s off fast-sync | S | low | Patch `specify_cli.sync.batch.time.sleep` (module-scoped, not global, no prod signature change); add `call_count==3` retry assertion | **YES** (part 1 only) |
| 8 | **A2/PP-05** per-worker HOME/XDG isolation autouse fixture | Architect/Paula | $0 direct; **master enabler** for #4 local+cli/sync/agent | M | medium | Key off xdist worker-id (NOT session-only); patch `Path.home`+env vars (mirror `test_sync_boundary_preflight.py:66-79`); **retain** the queue-wipe fixtures (intra-worker isolation); keep real-port sync tests serial; audit import-time `daemon.py:94 SPEC_KITTY_DIR` | **NO** — land isolation-only first |
| 9 | **R7/B2/PP-04(c,d)** cache full-tree AST (architectural) + DRG graph (doctrine) behind session/module fixtures | Randy/Architect/Paula | doctrine DRG ~18s→2s; architectural ~15–20s (LOCAL only) | M | low | **Exclude** `test_idempotent`, `test_graph_file_exists`, `test_shipped_graph_yaml_is_fresh` from cache; read-only AST guard; note architectural CI win is ~0 under loadfile (per-worker) — DRG win is real (single-process shard) | **NO** — needs carve-outs |
| 10 | **A6/R8** re-route status real-git/e2e tests off serial fast-shard (drop redundant fast overlay) | Architect/Randy | ~10–12s off fast-tests-status | M | medium | Implement as **INVERSION** (mark all fast EXCEPT git_repo/integration — never opt-in); collection-count gate (must drop exactly 85); widen `integration-tests-status` trigger to `(status OR sync)` to match fast shard; this is CI-only, **zero local win** | **NO** — gated on collection guard + trigger fix |
| 11 | **A3/PP-03** templated git-repo fixture; gate charter/agent-cli/dashboard autouse `git init` | Architect/Paula | charter ~2–6s (gating); coordination ~30s | L | medium | Gate by **execution-allowlist** (run with autouse removed, allowlist every NotInsideRepositoryError), NOT grep-by-symbol (misses 18 transitive callers); preserve `cache_clear()`; template = bare repo, NO worktrees; keep bespoke init for unborn/detached/--bare/worktree tests | **NO** — split into 2 commits, gating first |
| 12 | **R10(part2)/PP-06(c)** trim sync concurrency loops (50→20, 20→10) | Randy/Paula | ~2.5s off fast-sync | S | low-med | Keep a high-volume (≥50) variant `@slow`/nightly (corruption-catch power is volume-sensitive — don't silently weaken the stress guard); update loop range AND `4*count` assertion in lockstep; ≥4 threads | **NO** — needs nightly variant |
| 13 | **B2/PP-04(a)** collapse the 8× subprocess `pytest --collect-only` path-filter test | Architect/Paula | ~28s off architectural | M | low-med | Keep `legacy_nodes - new_nodes == {}` over IDENTICAL path universes; prefer parallelizing the distinct collections over merging (node→selector attribution must be unchanged) | **NO** — equivalence proof first |
| 14 | **B2/PP-07** drop `-v` from `pytest.ini` addopts | Architect/Paula | negligible (most CI jobs pass `-q` explicitly) | S | low | CI-only override; keep `-v` for local per CLAUDE.md; real lever is explicit CLI `-v` on lines 691/749/919/1449/1903 (follow-up) | **YES** (harmless) |
| 15 | **R9** flip 2 zero-value `xfail(strict=False)` guards (correctness hygiene) | Randy | ~0 (speedup claims refuted) | S | low-med | Case 1: flip to `strict=True` (currently genuinely xfails); Case 2: file real issue before skip; wheel/venv fixtures are session-scoped so saving is small | **NO** — needs tracked issue for case 2 |

---

## 3. "SAFE NOW" vs "FOLLOW-UP ISSUE"

### SAFE NOW (ship in the first PR wave — no parallelization dependency, coverage-neutral)

- **R4/PP-06(a)** — ULID n=100→25 with `SPEC_KITTY_ULID_VOLUME_FULL` env-gate shipped in the same change. Biggest flat win (~36s push + ~36s local).
- **R5/A4/PP-02 (assert conversion only)** — convert the 2 charter `elapsed<0.1` floors to `@pytest.mark.timeout(2)`. (The *charter flip* that this unblocks is a follow-up.)
- **R2/PP-07** — narrow `and not slow` dedup on the specify-cli-heavy shard.
- **R10 part 1** — no-op sleeper for the 2 sync swallow tests.
- **B2 part — drop `-v`** from `pytest.ini` addopts (CI-only override).

### FOLLOW-UP ISSUES (each scoped, behind safeguards)

**Issue A — "Per-worker HOME/XDG isolation fixture (A2/PP-05) — master parallelism enabler"**
Non-goals: do NOT flip any shard to `-n auto` in this PR; do NOT delete the queue-wipe fixtures; do NOT parallelize real-port daemon tests. Deliverable: worker-id-keyed `Path.home`+env redirect + a regression test asserting two workers get distinct homes and never touch real `~/.spec-kitty`.

**Issue B — "Flip fast-* CI shards to `-n auto --dist loadfile` (A1/PP-01/R6), charter first"**
Non-goals: do NOT flip cli/sync/agent before Issue A merges; do NOT flip the `release` shard (14 items, xdist overhead nets negative); do NOT flip status before Issue D; do NOT use bare `--dist load`. Per-shard run-twice ratchet required.

**Issue C — "Collapse FSM parity matrix + share migration read-only fixture (R1/A5, R3)"**
Non-goals: do NOT include the 2 counter tests in the shared migration fixture (different inputs); do NOT collapse `err==expected_err`; do NOT allow first-mismatch-only reporting.

**Issue D — "Re-route status git/e2e tests off serial fast-shard (A6/R8) + status xdist enablement"**
Non-goals: do NOT edit the integration-core-misc matrix (status is `--ignore`d there by design); do NOT implement marking as opt-in (inversion only); do NOT add `-n auto` to integration-status without auditing the `reset_handlers` adapter-registry tests under loadfile.

**Issue E — "Cache AST/DRG extraction + templated git-repo fixture (R7/A3/PP-03/PP-04)"**
Non-goals: do NOT route file-integrity/idempotency/freshness tests through caches; do NOT gate autouse `git init` by grep-for-symbol (use execution-allowlist); do NOT template worktree/unborn/--bare repos; split AST-cache and template-clone into separate reviewable commits.

**Issue F — "Sonar-style hygiene: trim sync concurrency loops + xfail strictness (R10p2/R9)"**
Non-goals: do NOT remove the high-volume corruption stress variant (keep `@slow`/nightly); do NOT convert case-2 xfail to skip without a tracked issue replacing the `#TBD` placeholder.

---

## 4. Coverage-Safety Statement

**The plan preserves coverage quality by construction.** Every accepted item is one of three coverage-neutral classes, with the adversarial verifier's carve-outs treated as binding:

1. **Pure execution-topology changes** (A1/PP-01/R6, A2/PP-05, B1) — same node set collected (identical `-m` selector + paths), same per-worker `--cov` XML merged. Proven in-repo: the exact `-n auto --dist loadfile` flags already ship on `integration-tests-core-misc`. Zero assertions touched.
2. **Item-explosion / redundant-execution removal** (R1/A5 parity collapse, R3 fixture share, R2 dedup, R7 AST/DRG cache, B2 collect-cache) — every assertion path still executes against the same golden/deterministic output; only pytest node granularity or redundant re-computation is removed.
3. **Semantic compression of over-scaled volume** (R4 ULID, R10 concurrency) — assertion code is identical; only iteration count drops, with the high-volume guard retained behind an env-gate/nightly variant.

**Regression/equivalence safeguards gating the risky items:**

- **FSM collapse (R1/A5):** accumulate-all-mismatches (no early exit) + `assert checked == len(_PARITY_ROWS)` (anti-vacuity) + keep `err==expected_err` exact-string (error-drift guard) + keep `test_baseline_fixture_is_non_trivial` verbatim + same-PR **mutation test** (flip one baseline row, confirm the loop fails and names it).
- **Migration fixture share (R3):** restricted to the 3 verifier-confirmed identical read-only tests; counter tests (`features_migrated==2`, `wps_backfilled==2`) and all rollback/dry-run/idempotency tests stay function-scoped on pristine state; fixture asserts `report.success`.
- **Parallelization flips (A1/A2):** per-shard collection-count equivalence (serial vs xdist must collect identical nodeids) + **run-twice/run-thrice ratchet** (mirroring the existing no-op-stability ratchet) + a CI/architectural guard that fails if any test mutates real `Path.home()/.spec-kitty` under xdist.
- **Slow dedup (R2/PP-07):** before/after collection gate proving the migration perf test is collected in **exactly one** job and the 3 specify_cli NFR guards (`test_list_performance_10k`, `test_sweep_nfr_002_10k_files_under_5s`, `test_assert_pytest_available_raises_when_pytest_missing`) remain reachable.
- **Charter timing (R5/A4):** convert to `@pytest.mark.timeout`, never delete — a generous ceiling still trips a pathological O(n) regression; functional `isinstance`/`len==2`/spy-call-count cache guards are kept verbatim.
- **AST/DRG cache (R7):** `test_idempotent`, `test_graph_file_exists`, `test_shipped_graph_yaml_is_fresh` excluded from cache; read-only AST guard.

No accepted item deletes a genuine assertion path or weakens a real regression guard. The one item where the verifier found a genuine volume-sensitivity (R10 part 2 concurrency stress) retains a high-volume nightly variant so corruption-catch power survives somewhere in CI.

---

## 5. Rejected Ideas

| Rejected idea | Why rejected (verifier finding) |
| --------------- | -------------------------------- |
| `--ignore=tests/specify_cli` on slow-tests job (R2 Option B) | Orphans 3 NFR/negative-path guards that run in NO other job → genuine coverage deletion |
| Add `not slow` to the shared core-misc marker expr (R2 Option A) | Line 1305 is shared by all 6 core-misc shards; strips slow+git_repo tests from cross_cutting (which slow-tests `--ignore`s) → orphan risk |
| Include the 2 migration counter tests in the shared fixture (R3) | Different inputs (2 features / 2 WPs); `==N` asserts would fail or be silently rewritten |
| Module-scope `_make_legacy_project` / `_setup_project` (B2/PP-04b) | `run_migration`/`rewrite_agent_shims` are destructive in-place mutations; distinct topologies + rollback/dry-run guards → state bleed destroys failure-path coverage |
| Flip the `release` fast shard to `-n auto` (A1) | 14 fast items; xdist worker-spawn + coverage-combine overhead nets **slower** |
| Flip agent shard relying on `--dist loadfile` alone (R6/A1) | loadfile pins files, not HOME; concurrent files clobber the same real `queue.db` → flaky exit-2 preflight refusals. Requires A2 first |
| Gate autouse `git init` by grep-for-`resolve_canonical_repo_root` (A3/PP-03) | Misses 18 transitive-caller files → NotInsideRepositoryError → silent breakage. Must use execution-allowlist |
| Claim status R8 moves tests "into the `-n auto` parallel matrix" | No such matrix exists for status (core-misc `--ignore`s it; integration-status is single-process). Real win is serial de-dup only, CI-only, zero local |
| Reduce R10 concurrency without a high-volume variant | Corruption-catch power scales with write volume; silent trim weakens a real stress guard |
| Session-scoped (not worker-scoped) HOME fixture (A2/PP-05) | Under `-n auto` all workers re-collide on one tmp HOME → reintroduces the exact hazard |

---

## 6. Sequencing (ordered rollout)

**Wave 1 — Quick wins, no dependencies (one PR, all SAFE NOW):**
1. R4 ULID n=100→25 + `SPEC_KITTY_ULID_VOLUME_FULL` env-gate (~36s push + ~36s local).
2. R5/A4/PP-02 charter `elapsed<0.1` → `@pytest.mark.timeout(2)` (assert conversion).
3. R2/PP-07 specify-cli-heavy `and not slow` dedup (~28s push).
4. R10 part 1 sync sleeper no-op (~4s).
5. Drop `-v` from `pytest.ini` addopts.
→ *Immediate ~64s+ push CPU + ~36s local, zero coverage risk, zero parallelization dependency.*

**Wave 2 — The master enabler (one isolation-only PR):**
6. A2/PP-05 per-worker HOME isolation fixture + regression test (worker-id-keyed). **No shard flips in this PR.** Lands the gate that everything below depends on.

**Wave 3 — Item-explosion + fixture sharing (behind equivalence proofs):**
7. R1/A5 FSM parity collapse (with mutation test).
8. R3 migration read-only fixture share (3 tests only).
9. R7/PP-04(d) DRG graph cache (doctrine, real CI win) + architectural AST cache (local win).

**Wave 4 — Parallelization flip, one shard at a time with run-twice ratchet:**
10. Charter fast shard → `-n auto --dist loadfile` (gated on Wave 1 #2). **This is the #1 critical-path collapse** — re-measure the 9.1m→2–5m claim, don't assume.
11. doctrine, then cli/sync (gated on A2). Run each 2–3× green before the next.
12. agent (only after A2 HOME-isolation regression test is green).
13. A6/R8 status re-route (inversion + collection gate + trigger widening), then status fast shard flip.

**Wave 5 — Structural, highest-effort, split commits:**
14. A3/PP-03 templated git-repo fixture (gating commit first, template-clone second).
15. B2/PP-04(a) collect-only consolidation; R10 part 2 + R9 hygiene.

**Wave 6 — Document the local default:**
16. B1 — update CLAUDE.md to `PWHEADLESS=1 pytest tests/ -n auto --dist loadfile -p no:cacheprovider` with the serial daemon-pass caveat, only after A2 + charter timing fixes are confirmed green under `-n auto`.

Rationale: quick coverage-neutral flat wins first (Wave 1), then the single fixture that unlocks all parallelism (Wave 2), then de-risk the collection/topology so xdist actually helps (Wave 3), then the high-leverage but contention-sensitive flips behind per-shard ratchets (Wave 4), structural last (Wave 5), and finally publish the local recipe once its preconditions are proven (Wave 6).

**Key file references (repo-relative):**
- CI: `.github/workflows/ci-quality.yml` — fast shards (charter ~1322, status ~891), proven xdist pattern (1181/1295/1307), slow-tests (~1895), specify-cli-heavy marker (~1305).
- HOME hazard: `tests/conftest.py:119` (`Path.home() / ".spec-kitty"`) + `tests/agent/conftest.py:15-41` (autouse wipe).
- FSM matrix: `tests/status/test_transitions.py:510-541`.
- Charter timing: `tests/charter/test_integration.py:427,450`.
- HOME-isolation template to copy: `tests/sync/test_sync_boundary_preflight.py:66-79`.
