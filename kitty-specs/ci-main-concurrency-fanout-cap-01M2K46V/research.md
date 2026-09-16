# Research: CI Main Concurrency + Fleet Fan-out Cap (Stage 1)

Mechanics verified against the live tree on `fix/ci-main-concurrency-fanout-cap` (at `upstream/main` tip). Governing authority: ADR `2026-09-15-1` (DRAFT at `work/ci-honesty-4437/DRAFT-ADR-ci-main-verdict-topology.md`, ratified via PR #4534). All `file:line` re-verified post-#4360-B/#4454/#4208.

## D1 — Main-push concurrency key (Lever 1a)

- **Decision**: `ci-router.yml` concurrency becomes `group: ci-router-${{ github.event_name == 'push' && github.sha || github.ref }}` with `cancel-in-progress: ${{ github.event_name != 'push' }}`.
- **Rationale**: The single top-level `concurrency:` block (`:35-37`) applies to all three triggers (`pull_request` `:20-21`, `push:[main]` `:22-23`, `workflow_dispatch` `:24-33`). Keying push on `github.sha` makes each landed tip its own singleton group (nothing to cancel); PR/dispatch keep the per-ref group with cancel enabled, so PR self-coalescing is byte-unchanged. All three context values are available in the concurrency expression at trigger time.
- **Alternatives considered**:
  - *Drop `cancel-in-progress` globally* — would stop PR self-coalescing too (waste + slower PR feedback). Rejected.
  - *Separate workflows for push vs PR* — large surface, duplicates the whole router. Rejected (ADR 1b/1c heavier alternatives).
  - *`github.run_id` in the key* — never coalesces anything (every run unique); defeats the purpose. Rejected.

## D2 — Fleet-verdict event-type trim (Lever 2a.1)

- **Decision**: `on.workflow_run.types` (`ci-fleet-verdict.yml:6`) `[requested, in_progress, completed]` → `[completed]`.
- **Rationale**: A verdict is a pure function of *terminal* upstream conclusions; `requested`/`in_progress` transitions carry no verdict information and only multiply triggers (8 workflows × 3 types → × 1). Immediate ~3× fan-out cut with zero information loss.
- **Alternatives**: *Keep `completed` + `requested` for an early "running" post* — the reporter already posts `running` from any completion and dedups repeats; the early post adds fan-out for no honest signal. Rejected.

## D3 — Top-level per-tip concurrency (Lever 2a.2)

- **Decision**: Add a top-level `concurrency:` block: `group: ci-fleet-verdict-${{ github.event.workflow_run.head_sha }}`, `cancel-in-progress: true`.
- **Rationale**: `ci-fleet-verdict.yml` has **no** top-level concurrency today; the `identify` entry job (`:9`) has none, so every trigger spawns a fresh `identify` (the #4371 root — 60 runs for one tip). Keying on `github.event.workflow_run.head_sha` coalesces all remaining `completed` triggers for one tip to a single surviving run; the survivor is the **last** completion and re-reads live evidence, so it computes and posts the terminal verdict. Different tips have different SHAs → different groups → never collide, so **no tip's verdict is dropped** (NFR-002). `head_sha` is the identity both `fleet_verdict.py` (`:405-420`) and `fleet_main.py` (`:50-62`) already key on.
- **Alternatives considered**:
  - *Branch/event ternary key* (`head_branch=='main' && event=='push' && head_sha || format('pr-{0}', head_branch)`) — equivalent but more complex; `head_sha` alone is per-tip for both main and PR. Rejected for simplicity.
  - *`cancel-in-progress: false` (queue) at top level* — reproduces the queue-outgrows-drain problem. Rejected.
  - *Concurrency on the `identify` job only* — leaves `report`/`report-main` uncapped. Rejected; top-level covers the whole run.

## D4 — `report-main` left UNCHANGED (Lever 2a.3) — **reversed by post-plan squad**

- **Decision (final, operator-ratified 2026-09-15)**: **Do not change `report-main`'s concurrency.** Keep `group: ci-fleet-verdict-main` / `cancel-in-progress: false` (`:71-73`).
- **Rationale**: The original plan proposed moving `report-main` to per-SHA coalesce (matching the ADR's literal Axis-2a text). The post-plan adversarial squad (architect-alphonso, MAJOR) showed this **opens a create-create race** on the single `from:ci` incident issue: two different red main tips (different `head_sha` → different group → genuinely concurrent) both run `report()`, both find no incident (TOCTOU between the scan at `fleet_main.py:106` and create at `:131` — the `:124` re-read only detects *that tip's own* evidence drift, not a *peer run's* concurrent create), and both create an issue → then `if len(incidents) > 1: raise` (`:110`) fails closed **after** the duplicate exists, persistently wedging the P0 incident intake until a human reconciles. `fleet_main`'s single-open-incident dedup is a resource *outside* the concurrency-group system, so per-SHA keying cannot serialize it.
- **Why the fan-out cap still holds without touching `report-main`**: the #4371 queue-outgrows-drain pathology was *caused by* the ~60-runs/tip **inflow**. D2 (`types:[completed]`) + D3 (top-level per-SHA coalesce) cut that inflow to ≈1 run/tip, so the original single-group `cancel:false` queue now carries N fast sequential posts for N tips — it drains trivially and no longer outgrows. The ADR's *goal* (queue cannot outgrow drain) is met upstream; the literal *mechanism* (change report-main) is unnecessary and harmful.
- **ADR deviation (flagged, not silent)**: this is a documented deviation from ADR Axis-2a's literal "report-main must move toward coalesce", recorded as a finding against that mechanic and ratified by the operator. Within the mission's delegated "exact YAML mechanics" latitude (ADR Confirmation: medium confidence there).
- **Alternatives considered**: *per-SHA + add idempotent-create logic to `fleet_main`* — closes the race but adds new production logic the mission otherwise avoids (D5 honesty) and defends a bug we can simply not create. Rejected. *Keep single-group but coalesce (cancel:true on the shared group)* — would let the newest tip cancel *older tips'* unposted verdicts (false-red/wedge). Rejected.

## D5 — Dedup "reinforcement" is a pin, not a code change (Lever 2a.4)

- **Decision**: Do **not** modify `classify`/`report` behavior. Add a focused dedup unit test asserting the survivor re-reads live evidence and never drops/staleposts the last-writer verdict; only if review finds a real gap under coalescing add a minimal, red-first reinforcement.
- **Rationale**: `fleet_verdict.report()` already double-snapshots (`:317`, `:332-334`) and refuses to publish stale evidence ("changed before publication; later event will reconcile"); `fleet_main.report()` re-reads at `:124`. Coalescing relies on exactly this already-correct behavior. Inventing a code change to look busy would violate campsite honesty. The ADR wording "keep/reinforce the dedup" is satisfied by pinning the invariant the fan-out cap now depends on.
- **Alternatives**: *Add a bespoke lock/lease* — unnecessary; the double-read is the correct mechanism and is already present. Rejected.

## D6 — YAML lint posture (no CI gate exists)

- **Decision**: Run `actionlint` and `shellcheck` **manually** on both touched workflows during implement; **paste the raw tool invocation + full output** into the PR body (not a bare self-reported "0 findings" — Renata MED). Do not add a new CI lint gate in Stage 1.
- **Rationale**: The repo has **no** actionlint/shellcheck Makefile target, CI job, or test (verified: they appear only as dev-tool installs in `scripts/tool_configs/*.sh`). Adding a lint gate is out of ADR scope for this cluster. The now-**exact-equality** golden-YAML pins catch the highest-risk syntactic item (the router ternary + the top-level per-SHA key); actionlint covers the remainder rather than being the sole proof; the merged-main-tip run is the ultimate proof. An actionlint CI gate is a **proposed follow-up to be filed with the PR — not yet tracked** (Renata LOW; do not claim it is "recorded").
- **Alternatives**: *Add an actionlint CI job in this PR* — scope creep beyond the ADR bundle; deferred as a follow-up.

## D7 — #4208 cross-coupling (input-distribution shift only)

- **Decision**: No `router_gate.py` change. Verify the byte-identical-policy tests stay green and observe on the merged main tip that legitimate `cancelled` runs still classify correctly.
- **Rationale**: `router_gate.py` treats `cancelled` as a **blocking** conclusion (`NON_BLOCKING_CONCLUSIONS = {"success","skipped"}`, `:46`; `classify` `:76-92`). 1a removes *push-cancellation-cascade* cancels on main, so fewer external-cancel main runs reach the gate — a live input-distribution shift, not a logic change. Pinned tests pass synthetic dicts and remain valid. The research (Lens B) flags this coupling explicitly; the missing #4208 wiring-guard (research MINOR-1) is recorded as a **follow-up**, not folded into this cluster stage.
- **Adversarial evidence disposition**: No dependency added/upgraded/removed → supply-chain section N/A. The one contested design point (report-main single-group vs per-SHA) was resolved in favor of per-SHA (D4) — disposition **changed** from the naive "coalesce the shared group" reading to per-SHA to preserve NFR-002. No contested finding dropped.

## D8 — Survivor-no-successor residual wedge: detect now, self-heal in Stage 3

- **Decision (operator-ratified 2026-09-15)**: Document the residual wedge as a named risk, add **SC-006** so the merged-tip acceptance ledger *detects* a stranded `running`, and **defer the self-heal** (a running-sweep) to Stage 3 — it is ADR lever **4b**.
- **Rationale**: debugger-debbie (MED) showed the terminal survivor under `types:[completed]` + coalescing has no successor event; on genuine drift or GitHub API-lag it can post `running`/nothing with no reconciler → a *missing* terminal verdict (never false-green, never blocking-false-red). She concedes it is **pre-existing in kind** — coalescing removes redundancy margin rather than introducing the wedge. Building the sweep now would pull ADR 4b scope into the concurrency stage. The correct Stage-1 posture is to make it *visible*.
- **Alternatives**: *retry-on-running in the report job* — a partial self-heal, still Stage-3-shaped; deferred whole.

## D9 — Top-level fleet key is subject-safe, not bare `head_sha` — **reversed by pre-merge squad (fix round 1)**

- **Decision (fix round 1, 2026-09-15)**: the top-level `concurrency.group` becomes `ci-fleet-verdict-${{ github.event.workflow_run.path == '.github/workflows/ci-aggregate.yml' && format('aggregate-{0}', github.event.workflow_run.id) || github.event.workflow_run.head_sha }}` (still `cancel-in-progress: true`); contracts C-YAML-3 and the exact-equality pin updated with it.
- **Rationale**: the pre-merge squad (MAJOR @0568119) showed D3's bare-`head_sha` key conflates verdict subjects on the **CI Aggregate** trigger path: a `workflow_run` child always executes on the default branch, so an aggregate completion's `head_sha` is the *current main tip*, not the PR head it verified (verified live: aggregate run 35021478369 `head_branch=main`/`head_sha=8e7e3519fd4c` while its source CI Modules run sits at PR head `0568119ce4`). Under `cancel-in-progress: true` every PR's aggregate completion landed in the current tip's group and cancel-cascaded (a) other PRs' aggregate-triggered runs → the #4430 stranding wedge, and (b) that tip's main-scope runs → lost `report-main`/red-main P0 intake. A cancelled run's subject is never recomputed by the survivor (`identify` scopes strictly by the source run's event, `fleet_verdict.py:405-420`). The aggregate path therefore keys on the aggregate run's own `id`: its `display_title` binds it to exactly one source CI Modules run, hence one PR head, so the group is a per-subject singleton — only a re-run of the same aggregate run shares it (same-subject newer evidence). Direct producers keep `head_sha`, which *is* their subject.
- **Why not `cancel-in-progress: false`** (the squad's alternative): D3 already rejected the queue posture, and it does not close the pending channel anyway — a newly queued run in a group **replaces any existing pending run by default**, regardless of `cancel-in-progress` (GitHub concurrency docs); PR #A's pending aggregate-triggered run would still be displaced by PR #B's trigger in the shared main-tip group. Only a subject-safe *key* closes both channels.
- **ADR deviation**: none — the ADR delegates "exact YAML mechanics"; the per-subject guarantee strengthens its Axis-2a mitigation ("the dedup keeps the survivor… never drops the last writer"), which D3's key silently falsified on the aggregate path.

## Post-plan adversarial squad — findings & dispositions (adversarial-evidence contract)

Squad at the post-plan point-cut; 3 profile-loaded read-only lenses; all returned **SHIP-WITH-FIXES**; convergent core: mechanism sound, no false-green, no blocking-false-red.

| # | Finding (lens) | Severity | Disposition |
|---|---|---|---|
| 1 | `report-main` per-SHA opens incident create-create race (architect-alphonso) | MAJOR | **changed** — keep `report-main` unchanged; ADR-literal deviation ratified (D4) |
| 2 | golden-YAML substring pins fakeable in the FR-breaking direction (reviewer-renata HIGH; debugger-debbie LOW) | HIGH | **changed** — C-YAML-1/3 now exact string/dict equality |
| 3 | acceptance ledger blind to a stranded `running` (debugger-debbie MED) | MED | **changed** — added SC-006 (terminal-verdict presence); D8 |
| 4 | terminal survivor has no successor → soft wedge (debugger-debbie MED) | MED | **changed→deferred** — documented residual + SC-006 detects; self-heal → Stage 3/4b (D8) |
| 5 | CK-1 over-broad; could be "fixed" into a PR-ref FR-002 regression (architect-alphonso MINOR) | MINOR | **changed** — CK-1 rescoped to landed-main-tip; PR-ref coalescing carved out |
| 6 | manual `actionlint`/`shellcheck` self-report is a fakeable green (reviewer-renata MED) | MED | **changed** — PR must paste raw tool invocation+output, not "0 findings" (D6) |
| 7 | actionlint-CI follow-up "recorded" but untracked (reviewer-renata LOW) | LOW | **changed** — reworded to "proposed follow-up, to be filed with the PR; not yet tracked" |
| 8 | VI-1 dedup test could be a tautology if `snapshot` is patched (reviewer-renata LOW) | LOW | **accepted** — non-tautology guard added to VI-1 for implement-review |
| 9 | coalescing depends on `types:[completed]` staying present (reviewer-renata LOW) | LOW | **accepted** — VI-6 documents the dependency |
| 10 | `report`(PR) job `cancel:false` comment now stale (alphonso/debbie INFO) | INFO | **accepted** — C-YAML-6 implement task to refresh the comment |
| 11 | diff-scope of NFR-001 is prose-only (reviewer-renata LOW) | LOW | **accepted** — quickstart adds a `git diff --name-only` scope check |
| 12 | #4208 needs no change; byte-identical tests valid (all three) | INFO | **accepted** — D7 confirmed; missing #4208 wiring-guard = separate follow-up |

No contested finding dropped. The one genuine steelman conflict (report-main per-SHA vs single-group) was adjudicated from GitHub Actions semantics + `fleet_main.py` source, not averaged.

## Live grounding (baseline to beat)

- Current main tip alone: **60** `CI Fleet Verdict` runs in the last-60 window (LIVE_CI_GROUNDING). Recent-25 main mix: Fleet Verdict 19 success / 3 in_progress / 2 cancelled; CI Aggregate 1 failure.
- Target after Stage 1 lands: ≈1 coalesced verdict per landed tip; 0 unevaluated tips in a merge burst.
