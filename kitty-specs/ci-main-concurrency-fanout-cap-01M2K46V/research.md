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

## D4 — `report-main` coalesce-with-survivor, per tip (Lever 2a.3)

- **Decision**: `report-main` concurrency (`:71-73`) `group: ci-fleet-verdict-main` / `cancel-in-progress: false` → `group: ci-fleet-verdict-main-${{ github.event.workflow_run.head_sha }}` / `cancel-in-progress: true`.
- **Rationale**: The current single group across **all** main tips with `cancel-in-progress: false` makes main-verdict runs *queue* — during a burst the queue grows faster than it drains (#4371: 96→183 in ~5 min). Coalesce-with-survivor drains it. Crucially the group must be **per-SHA**: a single-group coalesce would let the newest tip cancel *older tips' unposted* verdicts — the exact false-red NFR-002 forbids. Per-SHA coalesces only redundant runs of the *same* tip.
- **Cross-tip incident-issue safety**: `fleet_main.report()` (`:99-138`) finds/dedups a single open `from:ci` incident issue, fingerprint-suppresses (`:113-120`), and re-reads before commenting (`:124`, raises on drift). So two different tips' `report-main` running concurrently is idempotent and fail-closed — the single-group serialization it replaces was belt-and-suspenders, not a correctness requirement.
- **Alternatives**: *Remove the job-level block entirely (rely on top-level)* — top-level per-SHA already guarantees one run per tip, so the job-level block is technically redundant; kept explicit per-SHA for readability and to give the golden-YAML pin a stable target. Acceptable either way; chose explicit.

## D5 — Dedup "reinforcement" is a pin, not a code change (Lever 2a.4)

- **Decision**: Do **not** modify `classify`/`report` behavior. Add a focused dedup unit test asserting the survivor re-reads live evidence and never drops/staleposts the last-writer verdict; only if review finds a real gap under coalescing add a minimal, red-first reinforcement.
- **Rationale**: `fleet_verdict.report()` already double-snapshots (`:317`, `:332-334`) and refuses to publish stale evidence ("changed before publication; later event will reconcile"); `fleet_main.report()` re-reads at `:124`. Coalescing relies on exactly this already-correct behavior. Inventing a code change to look busy would violate campsite honesty. The ADR wording "keep/reinforce the dedup" is satisfied by pinning the invariant the fan-out cap now depends on.
- **Alternatives**: *Add a bespoke lock/lease* — unnecessary; the double-read is the correct mechanism and is already present. Rejected.

## D6 — YAML lint posture (no CI gate exists)

- **Decision**: Run `actionlint` and `shellcheck` **manually** on both touched workflows during implement; record the 0-finding result in the PR body. Do not add a new CI lint gate in Stage 1.
- **Rationale**: The repo has **no** actionlint/shellcheck Makefile target, CI job, or test (verified: they appear only as dev-tool installs in `scripts/tool_configs/*.sh`). Adding a lint gate is out of ADR scope for this cluster. The golden-YAML pytest pins assert the resolved shape; the merged-main-tip run is the ultimate proof. (An actionlint CI gate could be a future hardening ticket — recorded, not folded.)
- **Alternatives**: *Add an actionlint CI job in this PR* — scope creep beyond the ADR bundle; deferred as a follow-up.

## D7 — #4208 cross-coupling (input-distribution shift only)

- **Decision**: No `router_gate.py` change. Verify the byte-identical-policy tests stay green and observe on the merged main tip that legitimate `cancelled` runs still classify correctly.
- **Rationale**: `router_gate.py` treats `cancelled` as a **blocking** conclusion (`NON_BLOCKING_CONCLUSIONS = {"success","skipped"}`, `:46`; `classify` `:76-92`). 1a removes *push-cancellation-cascade* cancels on main, so fewer external-cancel main runs reach the gate — a live input-distribution shift, not a logic change. Pinned tests pass synthetic dicts and remain valid. The research (Lens B) flags this coupling explicitly; the missing #4208 wiring-guard (research MINOR-1) is recorded as a **follow-up**, not folded into this cluster stage.
- **Adversarial evidence disposition**: No dependency added/upgraded/removed → supply-chain section N/A. The one contested design point (report-main single-group vs per-SHA) was resolved in favor of per-SHA (D4) — disposition **changed** from the naive "coalesce the shared group" reading to per-SHA to preserve NFR-002. No contested finding dropped.

## Live grounding (baseline to beat)

- Current main tip alone: **60** `CI Fleet Verdict` runs in the last-60 window (LIVE_CI_GROUNDING). Recent-25 main mix: Fleet Verdict 19 success / 3 in_progress / 2 cancelled; CI Aggregate 1 failure.
- Target after Stage 1 lands: ≈1 coalesced verdict per landed tip; 0 unevaluated tips in a merge burst.
