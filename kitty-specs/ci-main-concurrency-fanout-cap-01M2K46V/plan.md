# Implementation Plan: CI Main Concurrency + Fleet Fan-out Cap (Stage 1)

**Branch**: `fix/ci-main-concurrency-fanout-cap` | **Date**: 2026-09-15 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/ci-main-concurrency-fanout-cap-01M2K46V/spec.md`

## Summary

Stage 1 of the ratified main-tip verdict-topology cluster (#4437) lands two coupled GitHub-Actions levers as one PR to upstream `main`:

- **1a (#4347)** — key the `ci-router.yml` concurrency group **per-SHA on push→main** (per-ref on PRs), so a merge burst no longer cancel-cascades main runs and each landed tip gets its own terminal evaluation.
- **2a (#4371)** — add a **top-level per-tip `concurrency:` block** to `ci-fleet-verdict.yml`, **trim `workflow_run` `types:` to `[completed]`**, and make **`report-main` coalesce-with-survivor per tip** (not a single shared queue), collapsing the ~60-runs-per-tip fan-out toward one coalesced verdict. The verdict scripts' survivor-re-read (double-snapshot) guarantee — which coalescing now relies on — is **already correct** and is pinned by a new dedup test rather than a fabricated code change.

Technical approach is entirely config-level YAML plus golden-YAML/dedup pytest pins; the pipeline run on the **merged main tip** is the real acceptance test ("a gate never run is not a gate").

## Technical Context

**Language/Version**: GitHub Actions workflow YAML (`.github/workflows/*.yml`) + Python 3.11+ (`scripts/ci/fleet_verdict.py`, `scripts/ci/fleet_main.py`)
**Primary Dependencies**: GitHub Actions (`workflow_run` triggers, workflow- and job-level `concurrency`), `pytest` + `PyYAML` (`yaml.safe_load` golden-YAML shape assertions), the Actions jobs/runs REST API (`urllib`, `/attempts/` plural)
**Storage**: N/A — CI configuration and the fleet-verdict PR-comment / main-incident-issue ledger; no datastore
**Testing**: `pytest` (`tests/ci/`, `tests/architectural/test_dual_mode_contract.py`) — golden-YAML shape assertions + dedup/classify unit tests; `actionlint` + `shellcheck` run **manually** on touched workflows (no CI gate for them exists in this repo)
**Target Platform**: GitHub-hosted Actions runners (Linux); verification on the merged `main` tip via `gh run list`
**Project Type**: single (CI infrastructure — no application source structure)
**Performance Goals**: ≈1 coalesced `CI Fleet Verdict` run per landed main tip (down from ~60, LIVE_CI_GROUNDING); bounded time-to-green-proof for a landed tip
**Constraints**: green path never widened (aggregate fail-closed guard untouched); no dropped last-writer verdict (no false-red / permanent wedge); `actionlint`+`shellcheck` = 0 on touched workflows; 1a and 2a land in the **same** PR
**Scale/Scope**: 2 workflow files (`ci-router.yml`, `ci-fleet-verdict.yml`) + 0–minimal edits to 2 scripts (`fleet_verdict.py`, `fleet_main.py`, no behavior change) + `tests/ci/` and `tests/architectural/` golden-YAML pins; a small, tightly-coupled diff

## Constitution Check (Charter Gate)

*GATE: must pass before Phase 0. Re-checked after Phase 1.* Charter present at `.kittify/charter/charter.md`; context loaded via `spec-kitty charter context --action plan` (compact).

| Charter principle | Stage-1 posture | Verdict |
|---|---|---|
| Single canonical authority | One main-green source of truth; this stage does **not** introduce a second ledger — it caps fan-out and per-SHA-isolates main runs. The governing authority is ADR `2026-09-15-1` (PR #4534); this mission consumes it, never re-authors it. | ✅ |
| Architectural alignment / canonical sources | Uses the canonical CI surfaces (`ci-router.yml`, `ci-fleet-verdict.yml`, `fleet_*.py`) and the canonical golden-YAML test pattern (`test_dual_mode_contract.py`'s `_load_workflow` → assert). No improvised parallel machinery. | ✅ |
| ATDD-first / red-first | The genuine red-first pins are the golden-YAML shape updates (`test_fleet_verdict.py:125`, `test_fleet_main.py:166`) and a new top-level-concurrency wiring pin + a dedup survivor pin. Honest: YAML behavior is provable only by shape + dedup tests, not by pretending pytest exercises the runner (C-002). | ✅ |
| Quality standing orders (campsite, no green-wash) | Fail-closed aggregate guard untouched (NFR-001); never-green tests kept green; no `# noqa`/suppression. | ✅ |
| Terminology canon | No `feature*`/legacy terms introduced; "Mission" language preserved. | ✅ |
| Git/workflow discipline | Own `issue`/`fix` branch → PR to upstream `main`, **operator-merged** (never push main, never `spec-kitty merge --push`). | ✅ |

No violations → Complexity Tracking below is empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/ci-main-concurrency-fanout-cap-01M2K46V/
├── plan.md              # This file
├── research.md          # Phase 0 — mechanics + decisions
├── data-model.md        # Phase 1 — concurrency-key + verdict-state model
├── quickstart.md        # Phase 1 — merged-main-tip verification runbook
├── contracts/           # Phase 1 — YAML-shape + dedup-behavior + test-wiring contracts
└── tasks.md             # Phase 2 (/spec-kitty.tasks — NOT created here)
```

### Source Code (repository root)

```
.github/workflows/
├── ci-router.yml          # Lever 1a — main-push concurrency key (per-SHA on push, per-ref on PR)
└── ci-fleet-verdict.yml   # Lever 2a — top-level concurrency, types:[completed], report-main coalesce

scripts/ci/
├── fleet_verdict.py       # PR reporter — classify/dedup/double-snapshot survivor (NO behavior change; pinned)
└── fleet_main.py          # Main reporter — shares classify/comment_body; survivor re-read (NO behavior change; pinned)

tests/ci/
├── test_fleet_verdict.py  # UPDATE :125 types set; ADD top-level-concurrency + dedup-survivor pins
└── test_fleet_main.py     # UPDATE :166 report-main concurrency assertion
tests/architectural/
└── test_dual_mode_contract.py  # ADD ci-router.yml per-SHA-concurrency golden-YAML pin (mirror wiring-guard pattern)
```

**Structure Decision**: CI-infrastructure single-tree. All changes live under `.github/workflows/` and `scripts/ci/` with mirrored pins in `tests/ci/` and `tests/architectural/`. No application source layout applies.

## Implementation Approach (the two levers, exact shape)

### Lever 1a — `ci-router.yml` concurrency (per-SHA on push→main)

Current (`ci-router.yml:35-37`), one shared group for all of `main`:
```yaml
concurrency:
  group: ci-router-${{ github.ref }}
  cancel-in-progress: true
```
Target — per-SHA on push (singleton group, never cancelled), per-ref cancel on PR/dispatch:
```yaml
concurrency:
  group: ci-router-${{ github.event_name == 'push' && github.sha || github.ref }}
  cancel-in-progress: ${{ github.event_name != 'push' }}
```
- On `push:[main]`: group becomes `ci-router-<sha>` (unique per tip) and cancel is disabled → **no main tip cancels another** (FR-001).
- On `pull_request` / `workflow_dispatch`: group stays `ci-router-<ref>` with `cancel-in-progress: true` → **PR self-coalescing unchanged** (FR-002).
- `github.event_name`, `github.sha`, `github.ref` are all available in the top-level concurrency expression at trigger time (research §1).

### Lever 2a — `ci-fleet-verdict.yml` fan-out cap

1. **Trim event types** (`ci-fleet-verdict.yml:6`) — `[requested, in_progress, completed]` → `[completed]`. A verdict is a function of *terminal* upstream state; the other two are pure fan-out (FR-004). ~3× fewer triggers immediately.
2. **Add top-level per-tip concurrency** (new block after `on:`), keyed on the triggering run's head SHA so each tip coalesces to one surviving `identify`, and different tips never collide:
   ```yaml
   concurrency:
     group: ci-fleet-verdict-${{ github.event.workflow_run.head_sha }}
     cancel-in-progress: true
   ```
   `head_sha` uniquely identifies a tip for both main pushes and PR heads; `cancel-in-progress: true` coalesces redundant per-tip triggers to the **last** completion, which becomes the survivor (FR-003). It **never** cancels a different tip (different SHA → different group), so no landed tip's verdict is dropped (NFR-002).
3. **`report-main` LEFT UNCHANGED** — `ci-fleet-verdict.yml:71-73` stays `group: ci-fleet-verdict-main` / `cancel-in-progress: false`. The post-plan squad (architect-alphonso, MAJOR) showed that moving it to per-SHA coalesce opens an incident **create-create race** (two concurrent red tips both create a `from:ci` issue → `len>1` raise → P0 intake wedges). The queue-outgrows-drain failure (FR-005) is resolved **upstream instead**: the `types:[completed]` trim + the top-level per-SHA coalesce cut `report-main` inflow to ≈1 run/tip, so the single-group `cancel:false` queue now drains trivially (N tips → N fast sequential posts). Keeping the single group preserves cross-tip incident-issue serialization. **Documented deviation from ADR Axis-2a's literal text (operator-ratified 2026-09-15); see research D4.**
4. **`report` (PR) job comment refresh** — update the now-stale `cancel-in-progress: false` comment at `ci-fleet-verdict.yml:40-44` to note the top-level per-SHA key now owns same-head coalescing (C-YAML-6). No behavior change.

### Lever 2a (cont.) — dedup "reinforcement" = pin, not fabricate

The survivor-re-read is already correct: `fleet_verdict.report()` double-snapshots (`:317` then `:332-334`, raises "changed before publication; later event will reconcile" on drift) and `fleet_main.report()` re-reads at `:124`. Coalescing (cancel-in-progress: true) relies on exactly this. **No code change is required or invented.** Instead, ADD a focused dedup unit test proving the survivor re-reads live evidence and never posts a stale/dropped verdict (FR-006, C-002, SC-005). If — and only if — implementation review finds a real gap in the survivor guarantee under the new coalescing regime, a minimal reinforcement is added with its own red-first test.

### Test strategy (honest — C-002)

| Change | How it is proven | File |
|---|---|---|
| 1a router concurrency | golden-YAML **exact-equality** pin (NEW), mirror `test_dual_mode_contract.py` `_load_workflow`→assert (substring pins are fakeable — Renata HIGH) | `tests/architectural/test_dual_mode_contract.py` |
| 2a `types:` trim | UPDATE existing assertion `{requested,in_progress,completed}`→`{completed}` | `tests/ci/test_fleet_verdict.py:125` |
| 2a top-level concurrency | golden-YAML **exact-equality** pin (NEW): `workflow["concurrency"] == {group: "ci-fleet-verdict-${{ github.event.workflow_run.head_sha }}", cancel-in-progress: True}` | `tests/ci/test_fleet_verdict.py` |
| 2a report-main | **UNCHANGED** — existing exact assertion `{ci-fleet-verdict-main, cancel:False}` stays green; do **NOT** edit `:166` | `tests/ci/test_fleet_main.py:166` |
| dedup survivor guarantee | NEW unit test: double-snapshot re-read (drift via the `API()` stub, not by patching `snapshot` — non-tautology); newer verdict not suppressed; stale not posted | `tests/ci/test_fleet_verdict.py` |
| YAML lint | `actionlint` + `shellcheck` run **manually** on both workflows; **raw invocation+output pasted in PR** (no CI gate exists) | — |
| SC-006 terminal-verdict presence | merged-main-tip observation: each landed SHA has `[ci] green\|red @sha` (not stranded `running`) — detects the survivor-no-successor residual wedge | `quickstart.md` ledger |
| #4208 cross-coupling | verify `router_gate.py` classify unchanged (byte-identical policy tests stay green); observe on merged main tip that fewer external-cancel main runs do not mis-block | `tests/architectural/test_dual_mode_contract.py` (existing, kept green) + merged-tip observation |

## Complexity Tracking

*No Charter Check violations — table intentionally empty.*

## Parallel Work Analysis

### Dependency graph

```
The two levers are coupled (must land together) and their diffs overlap the same two files
(ci-fleet-verdict.yml + tests/ci/) — by the write-scope lane rule they collapse into ONE lane.
Suggested sequencing WITHIN that lane (for /spec-kitty.tasks to formalize):

  WP01  Lever 1a: ci-router.yml per-SHA concurrency + golden-YAML pin  ─┐
                                                                        ├─→  WP03 verify + linters + #4208 coupling
  WP02  Lever 2a: ci-fleet-verdict.yml (types + top-level + report-main) ┘        + dedup survivor pin
        + update test_fleet_verdict.py:125 / test_fleet_main.py:166
```

- **Not meaningfully parallel.** One lane; WP01 and WP02 are independent edits but share `tests/ci`; WP03 is the coupling/verification capstone. `/spec-kitty.tasks` will finalize; expect a single lane by the write-scope collapse rule.
- Whole-mission acceptance is the **merged-main-tip** observation (quickstart.md), not any per-WP unit test.

## Risks & Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Coalescing (`cancel-in-progress: true`) drops the last-writer verdict → false-red/wedge (NFR-002) | HIGH | Per-**SHA** keys only — a group never spans two tips; the survivor is always the last completion and re-reads live evidence (double-snapshot). Dedup survivor test pins it. |
| Softening the green path | HIGH | Aggregate fail-closed guard and source-eligibility untouched (Stage 2 owns 3a). NFR-001; never-green + guard tests kept green. |
| Concurrency expression syntax error passes review but breaks at runtime (no actionlint CI gate) | MED | Golden-YAML pins use **exact string/dict equality** (not fakeable substrings — Renata HIGH); run `actionlint`+`shellcheck` manually with raw output pasted in PR; final proof on the merged main tip. |
| 1a shifts #4208 `router_gate.py` input distribution (fewer `cancelled`) | MED | No `router_gate.py` code change needed (it treats `cancelled` as blocking regardless); verify byte-identical-policy tests stay green; observe on merged tip that legitimate cancels still classify. Missing #4208 wiring-guard recorded as follow-up. |
| Terminal survivor has no successor event → stranded `running` (missing verdict, NFR-002) | MED | **Residual, pre-existing in kind** (coalescing removes redundancy margin, not introduces the wedge). Detected on the merged tip by **SC-006** (terminal-verdict presence). Self-heal (running-sweep) deferred to Stage 3 / ADR 4b (operator-ratified). |
| `report-main` incident create-create race | RESOLVED | `report-main` kept **unchanged** (single-group `cancel:false`) → cross-tip serialization preserved; the fan-out cap is delivered upstream (types + top-level coalesce). Was the original plan's MAJOR finding; reversed post-plan squad. |
| ADR file absent on branch (governance authority via #4534) | LOW | Dependency recorded; operator merges #4534 first/concurrently; planning reads the identical DRAFT. |

## Branch Contract (restated)

- **Current branch**: `fix/ci-main-concurrency-fanout-cap`
- **Planning/base branch**: `fix/ci-main-concurrency-fanout-cap` (cut clean from `upstream/main`)
- **Final merge target**: upstream `main`, via a PR the **operator merges** — `branch_matches_target: true`.
- Never push to `main`; never `spec-kitty merge --push`.

## Cross-coupling register (out-of-scope issues this stage moves)

- **#4208** (`router_gate.py`, shipped) — 1a changes its live `cancelled`-input distribution; no code change, verified byte-identical + merged-tip observation. Missing wiring-guard = follow-up.
- **#4334** (`sonar-pr`, `continue-on-error`) — not touched by Stage 1 (aggregate source-eligibility is Stage 2); noted for Stage 2.
- **#4534** (ADR) — governing authority; independent PR; hard sequencing dependency for `main`.
- **Stage 2 / Stage 3** — source-eligibility (3a/#4360-A) and terminal-cancel verdict (4a/#4430) are separate missions, created only after this stage lands and is verified on the merged main tip.
