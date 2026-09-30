---
title: Friction Burn-Down Sequencing — false-red / manual-toll engines
description: 'Sequencing note for the 3.2.x dev-friction burn-down: what already landed, the narrow toll that actually remains, and which gates look like friction but must NOT be touched.'
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/archive/plans/testing/test-suite-friction-audit.md
- docs/plans/code-quality/targeted-cleanup-scoping.md
- docs/archive/plans/3-2-x-executive-overview.md
- docs/development/how-to/manage-issue-tracker.md
- docs/adr/3.x/2026-07-17-1-red-main-is-honest-ci-is-release-authority.md
---

# Friction Burn-Down Sequencing — false-red / manual-toll engines

> **Historical (3.2.x cycle).** Kept as a record. The test-friction epics this note served, #2071 (tests as scaffold, not friction) and its parent #1931, are closed, and the residual tolls listed below (#3458, #2625) closed in September 2026. The active cycle is 4.0.0 — see the [4.0.0 roadmap](../../../plans/4-0-0-milestone-roadmap.md).

Companion sequencing note to the [test-suite friction audit](test-suite-friction-audit.md)
(epic [#2071](https://github.com/Priivacy-ai/spec-kitty/issues/2071) / [#1931](https://github.com/Priivacy-ai/spec-kitty/issues/1931)).

> **⚠️ Read this first — the audit's premise is largely SPENT (verified against `main` HEAD `21c2d9966`, 2026-08-17).**
> The audit is dated 2026-06-22. Between then and now, **most of its systemic findings shipped.**
> A three-facet research pass (researcher-robbie ×3) verified this against the tree, not the prose.
> An earlier draft of *this* note repeated the June premise without re-checking — that was wrong.
> Do **not** author a mission around "re-key the two guards onto `composite_key`" or "retire the
> bridge-compat sentinels": those are done. What remains is narrow. See below.

## What already landed (verified, do NOT re-scope into a mission)

| Audit finding | State on `main` | Evidence |
|---|---|---|
| **CT1** — re-key `file:line` architectural ratchets onto `composite_key`; delete the private token copy | **DONE** | `0705404e6` "content-address the architectural ratchet allow-lists" (#2547/#2072/#2548/#2077); `9f98d89fe` (FR-008/#2017-B8); `ebcfce21b` (WP01/#3448). The two named guards build their allowlists from `ContentDescriptor`; the private `_code_tokens_by_line` copy is gone. |
| **CT1 §2** — drain `status_transition.py:336` `_current_branch` fallback, live-evidence-gated | **DONE** | Drained by #1716 (WP04/T017); `test_no_write_side_rederivation.py::test_ws1_descriptor_no_longer_seeded_after_the_1716_drain` now **asserts its absence**. This is exactly the "proven dead → drain + assert-absence" resolution the audit prescribed. |
| **`composite_key` adoption** — "only one test" | **REFUTED** | 9 architectural files construct `ContentDescriptor` directly; the primitive was promoted into `src/` (`specify_cli/contracts/anchoring`). |
| **CT4/CT6** — retire `test_bridge_compat_surface` round-trip sentinels; re-point the ~77 `specify_cli.next` shim importers | **DONE (deleted)** | `test_bridge_compat_surface.py` + `test_runtime_bridge_family_arch.py` deleted in `177e06269` (#3285); `src/specify_cli/next/` deleted (FR-003 unshim wave 2); `git ls-tree origin/main -- src/specify_cli/next/` is empty. The 5 remaining `specify_cli.next` mentions are **absence-pin guards** (keepers), not importers. |
| **CT7** — ban new raw `file.py:NNN` ratchet keys | **PARTIALLY LANDED** | `tests/architectural/test_ratchet_positional_anchor_ban.py` exists and stands watch (bans positional anchors, consumes `composite_key`). |

## What actually remains (the real, narrow scope)

1. **Golden-count classifier toll (CT5 / [#3458](https://github.com/Priivacy-ai/spec-kitty/issues/3458), P2 — the front-loadable facet of [#2853](https://github.com/Priivacy-ai/spec-kitty/issues/2853))** — the live toll.
   `test_golden_count_ban.py::classify_golden_count` defaults an ambiguous `len(x)==N` to
   `convert`, forcing a `# golden-count: cardinality-is-contract` annotation for **zero real
   catches** (PR #3456: 0 catches, 2 forced). This is the one systemic manual-toll engine the
   composite-key work did **not** touch (it solved line drift, not count baselines).
2. **Golden-count bulk conversion of excluded co-owned dirs ([#2625](https://github.com/Priivacy-ai/spec-kitty/issues/2625), P3)** — waits on ownership-collision clearing; bulk churn, not front-loadable.
3. **One genuine raw-tuple residual ([#3206](https://github.com/Priivacy-ai/spec-kitty/issues/3206))** — `kernel/schema_utils.py:88,96` import-lineno exemptions. A **different gate** (doctrine-import lineno ban, not a `composite_key` sink) and it needs an **architecture decision** (relocate schemas / inject root), not a mechanical re-key. Hand to architect-alphonso.
4. **CT7 completion** — extend the positional-anchor ban to also reject raw `("file.py", <int>)` 2-tuple ratchet keys (belt-and-suspenders now that composite-key adoption is broad), plus codify the anti-patterns as a test-hygiene directive.
5. **Truth reconciliation** — close/rescope the stale-open trackers (see below) and fold one cosmetic residual: the dangling `test_bridge_compat_surface.py` reference at `test_no_dead_symbols.py:874`.

## Recommended first mission slice (recalibrated)

Small, front-loadable, low-risk. Each WP carries a **non-vacuous** acceptance criterion.

- **WP-1 — Golden-count classifier default fix (#3458).** Stop defaulting ambiguous dynamic-result
  `len==N` to `convert` in `classify_golden_count()` / the `_DYNAMIC_RUNTIME_WORDS` vocabulary.
  **AC:** (a) a new test asserting `len(findings)==1` on a dynamically-produced list lands with **no**
  annotation and **no** ceiling bump (the #3456 false-positive); **and** (b) a regression proof that the
  gate STILL forces conversion on the real failure mode (a swap-tolerant `len(Enum)==N` on an
  enumerable domain — preserves the gate's value, per NFR-E). Both directions, or the fix is vacuous.
- **WP-2 — CT7 raw-tuple ratchet-key ban (extend, don't build fresh).** Extend
  `test_ratchet_positional_anchor_ban.py`. **AC:** a synthetic fixture introducing a raw
  `("some_file.py", 472)` 2-tuple key is detected **RED**; the same content via `composite_key` passes
  (anti-vacuity: prove it catches the bad form).
- **WP-3 — Truth reconciliation (campsite).** Fold the `test_no_dead_symbols.py:874` dangling ref;
  this note's corrections are already in. **AC:** no reference in `tests/` to the deleted
  `test_bridge_compat_surface.py`.

Bulk conversion (#2625) and the #3206 architecture decision are **explicitly out of the first slice.**

## Parallel track (independent) — gate-reliability, epic #3260

Not ratchet work; already parented under #3260. Cheapest high-frequency wins first:
**#3224** (pre-review baseline venv missing `hatchling` → spurious "new failure" every move-task),
then **#2803** (lane `.venv` missing pytest → false red/green), **#2927** (regression-tests
INTERNALERROR), **#2979 / #3241 / #3189 / #3265 / #3463** (coverage-integrity gaps),
**#2762 / #2801** (pre-review daemon leak / opt-out toggle). Do **not** fold into the ratchet mission.

## Counterweight — do NOT "fix" these (contracts, not friction)

- Convergence-invariant assertions (`read_dir == write_dir`, triple-equality collapse) — correct contracts.
- `test_execution_context_parity.py`, `tests/git/test_protection_preserved.py`, `tests/runtime/test_bridge_parity.py` — gold-standard real-outcome oracles with anti-vacuity proofs.
- The four `specify_cli.next` **absence-pin guards** (`test_import_paths.py`, `test_shim_registry_schema.py`, `test_layer_rules.py`, `session_presence/test_content.py`) — deleting them re-opens the retired-shim regression door.
- `_baselines.yaml` **count**-keyed ratchets — semantically meaningful burn-down accounting.
- `test_dogfood_corpus_backfilled` (#2917) — corpus drift, resolve by re-running the backfill, never by relaxing the predicate (ADR 2026-07-17-1).

## Tracker reconciliation (done 2026-08-17)

- **[#2633](https://github.com/Priivacy-ai/spec-kitty/issues/2633)** — **rescoped P0 → P2, retitled.** Its sentinel-retirement half is done (`177e06269` / #3285 deleted `test_bridge_compat_surface.py`); the remainder is deleting the 34 `runtime_bridge` delegates + repointing ~14 **live production callers** — a refactor gated on the 3.3.0 delegate cut, not test friction, not release-blocking.
- **[#2631](https://github.com/Priivacy-ai/spec-kitty/issues/2631)** — **NOT stale; left P3.** It is a bounded `*parity*`/`*equivalence*` discriminator audit over suites that still exist (`test_execution_context_parity`, `test_bridge_parity`, …). Only its dependency on the sentinel retirement resolved (noted on-issue); the audit stands.
- **[#2853](https://github.com/Priivacy-ai/spec-kitty/issues/2853) (P1)** — **NOT the `composite_key` issue; left P1.** It targets the **frozen-absolute-baseline family** (count/set/hash pins), a different axis from the file:line drift that `composite_key` (CT1) already fixed. **WP-1 below (#3458) is one facet of it**, not its closure; the broader ask (source-derived sets, warning-not-fail, run gates in the fast/local suite) remains open.
