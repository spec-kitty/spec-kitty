# Tasks: Second clones reconcile with origin before every terminus gate

**Mission**: `second-clone-origin-reconciliation-01M48V8W` · **Topology**: lanes (no coordination branch)
**Planning base / merge target**: `claude/happy-keller-r38xig`
**Inputs**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/)

```
WP01 kernel remote owner ──┬── WP02 drain remote contact + census gate
                           ├── WP03 origin_freshness intent ──┬── WP04 consolidate (#5780)
                           │                                  ├── WP05 accept + orchestrator-api
                           │                                  └── WP06 review workspace (#5758)
                           └── WP07 init/upgrade merge drivers (#5759)
WP02 + WP04 + WP05 + WP06 + WP07 ── WP08 registry gate, ADR, docs
```

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first kernel tests against a real bare remote | WP01 | |
| T002 | `no_prompt_env`, `RemoteUnreachable`, timeouts | WP01 | |
| T003 | `resolve_remote`, `tracking_ref` | WP01 | |
| T004 | `remote_heads`, `fetch_branches`, `divergence` | WP01 | |
| T005 | `describe_remote_head`, doctrine clone/fetch wrappers, package exports | WP01 | |
| T006 | Shared two-clone + bare-remote test helper in `tests/terminus/` | WP01 | [P] |
| T007 | Census gate (red, lists today's 5 sites) + planted self-test | WP02 | |
| T008 | `remote_probes` on `kernel.git.remote` | WP02 | [P] |
| T009 | `push_preflight` fetch + ahead/behind on `kernel.git.remote` | WP02 | [P] |
| T010 | `protection_policy` + doctrine `git_source` on `kernel.git.remote` | WP02 | [P] |
| T011 | #4969 ref builders on `tracking_ref` / `resolve_remote` | WP02 | [P] |
| T012 | Gate green with empty allowlist; affected tests | WP02 | |
| T013 | Red-first verdict-matrix tests (real git) | WP03 | |
| T014 | Origin-check mode (flag / env / default / unknown) | WP03 | |
| T015 | `check_status_evidence` (seam ref, alias-scoped log, owned) | WP03 | |
| T016 | `check_branches` | WP03 | |
| T017 | `enforce_merge_gate`, `OriginFreshnessRefused`, refusal text | WP03 | |
| T018 | `plan_review_lane` | WP03 | |
| T019 | Red-first #5780 regression (coord + lanes, `--push`, FR-015 control) | WP04 | |
| T020 | Campsite: extract consolidate pre-phase helpers (behaviour-preserving) | WP04 | |
| T021 | Wire status-evidence + approved-lane checks into the executor | WP04 | |
| T022 | `consolidate --origin-check` | WP04 | |
| T023 | Affected consolidate test sweep | WP04 | |
| T024 | Red-first accept + orchestrator-api tests | WP05 | |
| T025 | `accept` wiring + `--origin-check` | WP05 | |
| T026 | orchestrator-api wiring, envelope data, contract 1.11.0 | WP05 | |
| T027 | Affected accept / orchestrator test sweep | WP05 | |
| T028 | Red-first #5758 regression (re-review loop; no local lane) | WP06 | |
| T029 | Campsite: extract `_create_review_worktree` | WP06 | |
| T030 | Wire `plan_review_lane` into `_prepare_review_workspace` | WP06 | |
| T031 | Focused review tests (diverged, dirty, live lock, unreachable, checkout-root skip) | WP06 | |
| T032 | Affected review test sweep | WP06 | |
| T033 | Red-first #5759 regression (clone + init → clean pull; upgrade arm) | WP07 | |
| T034 | Campsite: extract `_wire_merge_driver_best_effort` from `init` | WP07 | |
| T035 | Install merge-driver config on the already-initialized path | WP07 | |
| T036 | Upgrade finalizer step + `UpgradeOutcome` field | WP07 | |
| T037 | Affected init / upgrade test sweep | WP07 | |
| T038 | Registry gate: evidence gates run the freshness check | WP08 | |
| T039 | ADR 2026-10-06-3 amending ADR 2026-06-05-1 | WP08 | [P] |
| T040 | Env var, orchestrator-api and glossary docs | WP08 | [P] |
| T041 | CHANGELOG + AGENTS.md note | WP08 | [P] |
| T042 | Docs regeneration, freshness and terminology gates | WP08 | |

## Phase 1 — Foundation

### WP01 — Kernel: one owner of remote contact
**Prompt**: [tasks/WP01-kernel-remote-owner.md](tasks/WP01-kernel-remote-owner.md) · **Priority**: P0 (blocks everything) · **Est.** ~330 lines
**Goal**: `src/kernel/git/remote.py` — bounded, non-prompting, ref-level remote primitives on the existing `run_git`; plus the shared two-clone test helper.
**Independent test**: `tests/kernel/test_git_remote.py` against a real bare `file://` remote (reachable, unreachable, missing branch, non-`origin` remote).
**Dependencies**: none

T001 Red-first kernel tests against a real bare remote (WP01)
T002 `no_prompt_env`, `RemoteUnreachable`, timeouts (WP01)
T003 `resolve_remote`, `tracking_ref` (WP01)
T004 `remote_heads`, `fetch_branches`, `divergence` (WP01)
T005 `describe_remote_head`, doctrine clone/fetch wrappers, package exports (WP01)
T006 Shared two-clone + bare-remote test helper in `tests/terminus/` (WP01)

**Risks**: `test_no_dead_symbols` sees exported names without `src/` callers until WP02/WP03 land (expected interim red; verified green at consolidation).

### WP02 — Drain every remote contact into the owner; census gate
**Prompt**: [tasks/WP02-drain-remote-contact.md](tasks/WP02-drain-remote-contact.md) · **Priority**: P1 · **Est.** ~330 lines
**Goal**: no `fetch` / `ls-remote` / `pull` / `clone` / `remote show` git argv outside `src/kernel/git/`; an architectural gate with an empty allowlist proves it.
**Dependencies**: WP01

T007 Census gate (red, lists today's 5 sites) + planted self-test (WP02)
T008 `remote_probes` on `kernel.git.remote` (WP02)
T009 `push_preflight` fetch + ahead/behind on `kernel.git.remote` (WP02)
T010 `protection_policy` + doctrine `git_source` on `kernel.git.remote` (WP02)
T011 #4969 ref builders on `tracking_ref` / `resolve_remote` (WP02)
T012 Gate green with empty allowlist; affected tests (WP02)

**Risks**: mock-heavy `push_preflight` / `remote_probes` tests; keep public behaviour byte-identical.

## Phase 2 — Intent

### WP03 — `origin_freshness`: verdicts, policy, opt-out
**Prompt**: [tasks/WP03-origin-freshness-intent.md](tasks/WP03-origin-freshness-intent.md) · **Priority**: P0 · **Est.** ~380 lines
**Goal**: the application module every evidence gate calls.
**Dependencies**: WP01

T013 Red-first verdict-matrix tests (real git) (WP03)
T014 Origin-check mode (flag / env / default / unknown) (WP03)
T015 `check_status_evidence` (seam ref, alias-scoped log, owned) (WP03)
T016 `check_branches` (WP03)
T017 `enforce_merge_gate`, `OriginFreshnessRefused`, refusal text (WP03)
T018 `plan_review_lane` (WP03)

## Phase 3 — Gates (parallel after WP03)

### WP04 — consolidate refuses on stale evidence and lanes (#5780)
**Prompt**: [tasks/WP04-consolidate-gate.md](tasks/WP04-consolidate-gate.md) · **Priority**: P0 · **Est.** ~330 lines · **Dependencies**: WP03

T019 Red-first #5780 regression (coord + lanes, `--push`, FR-015 control) (WP04)
T020 Campsite: extract consolidate pre-phase helpers (behaviour-preserving) (WP04)
T021 Wire status-evidence + approved-lane checks into the executor (WP04)
T022 `consolidate --origin-check` (WP04)
T023 Affected consolidate test sweep (WP04)

### WP05 — accept and orchestrator-api gates
**Prompt**: [tasks/WP05-accept-orchestrator-gates.md](tasks/WP05-accept-orchestrator-gates.md) · **Priority**: P1 · **Est.** ~280 lines · **Dependencies**: WP03

T024 Red-first accept + orchestrator-api tests (WP05)
T025 `accept` wiring + `--origin-check` (WP05)
T026 orchestrator-api wiring, envelope data, contract 1.11.0 (WP05)
T027 Affected accept / orchestrator test sweep (WP05)

### WP06 — review prepares the lane from the remote (#5758)
**Prompt**: [tasks/WP06-review-workspace-from-remote.md](tasks/WP06-review-workspace-from-remote.md) · **Priority**: P0 · **Est.** ~350 lines · **Dependencies**: WP03

T028 Red-first #5758 regression (re-review loop; no local lane) (WP06)
T029 Campsite: extract `_create_review_worktree` (WP06)
T030 Wire `plan_review_lane` into `_prepare_review_workspace` (WP06)
T031 Focused review tests (diverged, dirty, live lock, unreachable, checkout-root skip) (WP06)
T032 Affected review test sweep (WP06)

### WP07 — init / upgrade install clone-local merge drivers (#5759)
**Prompt**: [tasks/WP07-clone-merge-driver-config.md](tasks/WP07-clone-merge-driver-config.md) · **Priority**: P1 · **Est.** ~280 lines · **Dependencies**: WP01

T033 Red-first #5759 regression (clone + init → clean pull; upgrade arm) (WP07)
T034 Campsite: extract `_wire_merge_driver_best_effort` from `init` (WP07)
T035 Install merge-driver config on the already-initialized path (WP07)
T036 Upgrade finalizer step + `UpgradeOutcome` field (WP07)
T037 Affected init / upgrade test sweep (WP07)

## Phase 4 — Close the class

### WP08 — Registry gate, ADR, docs
**Prompt**: [tasks/WP08-registry-gate-adr-docs.md](tasks/WP08-registry-gate-adr-docs.md) · **Priority**: P1 · **Est.** ~300 lines · **Dependencies**: WP02, WP04, WP05, WP06, WP07

T038 Registry gate: evidence gates run the freshness check (WP08)
T039 ADR 2026-10-06-3 amending ADR 2026-06-05-1 (WP08)
T040 Env var, orchestrator-api and glossary docs (WP08)
T041 CHANGELOG + AGENTS.md note (WP08)
T042 Docs regeneration, freshness and terminology gates (WP08)

## MVP

WP01 → WP03 → WP04 closes the first P0 (#5780); WP06 the second (#5758); WP07 is independent after WP01 (#5759).
