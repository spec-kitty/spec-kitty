---
title: 'CaaCS: test↔production change-coupling analysis'
description: 'Change-coupling-as-a-code-smell mining of the architectural + core test suites to rank refactor-fragile tests for revision/rewrite/deletion.'
doc_status: deprecated
updated: '2026-09-30'
audience: docs/context/audience/internal/maintainer.md
related:
- docs/archive/plans/testing/test-suite-friction-audit.md
- docs/development/testing/testing-flakiness.md
---
# CaaCS: test↔production change-coupling analysis

> **Historical (3.2.x cycle).** Kept as a record. The test-friction epics this note served, #2071 (tests as scaffold, not friction) and its parent #1931, are closed. The active cycle is 4.0.0 — see the [4.0.0 roadmap](../../../plans/4-0-0-milestone-roadmap.md).

**Question.** Which test files change *because production code merely moved*,
rather than because behaviour changed? Those are the refactor-fragile,
form-coupled tests — the ones that tax every structural change (as the
coord-authority trio degod did: three separate allowlist re-anchor round-trips
for zero behaviour change). This is the friction #2071 exists to pay down.

## Method

`git log --no-merges --name-only` over **6282 non-merge commits**. Per test file:

- `changes` — commits touching the file.
- `co_src` — commits touching the file **and** ≥1 `src/**.py` file.
- `ratio = co_src / changes` — the share of the test's edits that rode along
  with a production edit. **ratio → 1.0 means the test never changes for its own
  reasons; it only tracks production.**
- `top partners` — the `src/` packages it most co-changes with.

**Two caveats that shape the reading:**

1. **`cli/commands×N` is inflated** — `cli/commands/` is the single most-churned
   production area (the god-module degod era). Coupling *to it* is partly an
   artifact of that churn, so weigh **ratio** (fragility) over raw **volume**
   (tax paid) when judging a test's design.
2. **Architectural tests ≠ integration tests.** An integration/command test
   *should* co-change with the command it exercises (high ratio is healthy). An
   **architectural invariant** test that co-changes constantly is the smell — it
   claims to pin an invariant but is actually pinning code *shape*. So the
   **architectural** list below is the priority hit-list; the core-package list
   is context.

## Architectural tests — the hit-list

Ranked by co-change **volume** (maintenance tax actually paid):

| test file | changes | co-src | ratio | top src partner |
| --- | --: | --: | --: | --- |
| `test_no_dead_symbols.py` | 54 | 45 | 0.83 | cli/commands×196 |
| `test_no_dead_modules.py` | 36 | 29 | 0.81 | cli/commands×116 |
| `test_single_mission_surface_resolver.py` | 21 | 16 | 0.76 | cli/commands×74 |
| `test_mission_runtime_surface.py` | 14 | 13 | 0.93 | mission_runtime×13 |
| `test_layer_rules.py` | 13 | 13 | **1.00** | cli/commands×54 |
| `test_ci_quality_path_filters.py` | 14 | 6 | 0.43 | cli/commands×26 |
| `test_no_write_side_rederivation.py` | 9 | 5 | 0.56 | cli/commands×42 |

Perfect-coupling (`ratio = 1.00`, ≥4 changes) — every edit driven by production:
`test_layer_rules`, `test_no_raw_mission_spec_paths`, `test_safe_commit_import_boundary`,
`test_template_governance_payload_contract`, `conftest`, `test_pytest_marker_convention`,
`test_auth_transport_singleton`, `test_status_module_boundary`, `test_tid251_enforcement`,
`test_wp05_write_target_drain`, `test_guard_capability_call_sites`,
`test_pytest_marker_correctness`, `test_charter_facades_reexport_doctrine`.

## Verdicts

### 🔴 Rewrite / replace — highest tax, inherently shape-coupled

- **`test_no_dead_symbols.py` (54 changes)** and **`test_no_dead_modules.py` (36)**.
  Whole-codebase symbol/module scanners driven by hand-maintained allowlists;
  they *must* be edited whenever any symbol moves — 90 edits between them, almost
  all pure churn. **Action:** evaluate replacing the bespoke scan with an
  off-the-shelf dead-code detector (`vulture`, ruff `F401`/`F811` families) plus
  a small curated exception file, or at minimum move the allowlists to the
  content-addressed key already available in-repo (see below). These two alone
  are the biggest single lever.

### 🟠 Harden the drift-proof key — the fix already exists, propagate it

- `tests/architectural/_ratchet_keys.py` already provides **`composite_key` /
  `code_tokens_by_line`**: a content-addressed `(enclosing_qualname, token_line)`
  key so a benign insertion above a guarded site does **not** flip the gate red.
  `test_no_write_side_rederivation.py` adopted it — yet it *still* cost a manual
  re-anchor this session because it retains a **line-number staleness twin-guard**
  (`_ALLOW_LIST_SEED` stores `(rel_path, line)` and asserts the seed line matches
  a live finding).
- **`test_trio_seam_only.py`** (new this cycle) did **not** adopt the pattern —
  its `_IO_ALLOWLIST_SITES` keys on raw `(rel_path, line_number)`, which is why a
  15-line insertion broke it twice.
  **Action:** (a) migrate `_IO_ALLOWLIST_SITES` to `composite_key`; (b) drop or
  content-address the residual line-number staleness twin-guards so *no* pure
  line drift can red these gates again.

### 🟡 Audit the `ratio = 1.00` cluster — keep-if-behavioural, else convert

Each of these changes *only* when production moves. Per the refactor-stable-tests
doctrine, that is acceptable **only** if the test pins a *behavioural / negative
invariant* (e.g. `test_safe_commit_import_boundary`, `test_layer_rules`,
`test_tid251_enforcement` plausibly do — import/layer bans). Where a "1.00" test
is really asserting a *positive literal code shape* (a symbol lives at a path, a
call reads a specific string), it should be **converted to a behavioural
assertion or deleted**, not re-pinned. This audit is one pass over ~13 files.

### 🟢 Leave — expected coupling

The **core-package** integration tests (`agent/test_implement_command.py` 23/23,
`agent/test_orchestrator_commands_integration.py` 21/21, `status/test_emit.py`
21/19, …) show high coupling *by design* — they exercise the very commands they
co-change with. High ratio here is health, not smell. No action.

Characterization tests register near-zero history (created this cycle) — nothing
to judge yet; the point is to keep them behaviour-pinned so they *stay* low-churn.

## Recommended sequence

1. Migrate `test_trio_seam_only._IO_ALLOWLIST_SITES` + the residual line-number
   staleness guards onto `_ratchet_keys.composite_key` (cheap, removes the exact
   friction this session hit).
2. Prototype replacing `test_no_dead_symbols` / `test_no_dead_modules` with
   `vulture` + a curated ignore file; compare signal vs the 90-edit maintenance
   cost.
3. One audit pass over the `ratio = 1.00` architectural set: behavioural-invariant
   (keep) vs positive-literal-shape (convert/delete).

Feeds **#2071** (test-QA friction epic) and enforces the refactor-stable
architectural-tests doctrine (pin invariants, not shape).

*Generated by `caacs_miner.py` (git-history mining, read-only).*
